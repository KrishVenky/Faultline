from faultline.config import AAVE_V3_ETHEREUM_SUBGRAPH_ID, RAY
from faultline.graphql_client import query_subgraph

# CAUTION (BUILDLOG.md, 2026-09-05 "Phase 1 gate: reconciled"): Aave's
# UserReserve.currentVariableDebt / currentATokenBalance are snapshots
# written only when the user last interacted with that reserve. A dormant
# position understates its true balance. Always derive live amounts from
# the position's scaled amount times the RESERVE's current index (which
# updates on every interaction by anyone), never from the current* fields
# directly. Verified against DeBank on wallet
# 0x62bc66de718645a1f605638132a57213119aa5e1 (5054.621205 computed vs
# 5054.6214 reported, WETH variable debt).

# eMode (BUILDLOG.md, 2026-09-05 "Cascade test", "A third, bigger bug: eMode
# was never accounted for"): a wallet in an eMode category gets that
# category's liquidationThreshold/liquidationBonus INSTEAD OF a reserve's
# base values, but only for assets the category actually lists as
# eMode-eligible collateral -- any other asset the wallet holds as
# collateral still uses its own base reserve threshold. Confirmed live:
# category "ETH correlated" and category "rsETH__ETH_wstETH_ETHx" both
# carry a 95% threshold vs. 75-81% base reserve values for the same assets.
# Getting this wrong doesn't fail loudly -- it produces a plausible-looking
# wrong health factor, which is worse than an error. This is the one path
# everything (hand_walk_cascade.py's regression test, and the Phase 2
# solver) computes it through; do not reimplement this logic elsewhere.

USER_QUERY = """
query($wallet: ID!) {
  user(id: $wallet) {
    eModeCategoryId {
      id
      liquidationThreshold
      liquidationBonus
    }
    reserves {
      usageAsCollateralEnabledOnUser
      scaledATokenBalance
      scaledVariableDebt
      currentStableDebt
      reserve {
        symbol
        underlyingAsset
        decimals
        liquidityIndex
        variableBorrowIndex
        reserveLiquidationThreshold
        reserveLiquidationBonus
        liquidationProtocolFee
      }
    }
  }
}
"""

# Deliberately a separate, category-filtered query, not a single combined
# one. `emodeCategoryConfigs` with no filter defaults to GraphQL's first-100
# rows across ALL categories/assets in the whole deployment (there are
# >100) -- caught live: category 3's rsETH row silently wasn't in that
# arbitrary first 100, so rsETH read as not-eMode-eligible when it is.
# Filtering server-side to just the wallet's own category avoids relying on
# pagination ever reaching the right row.
EMODE_CATEGORY_ASSETS_QUERY = """
query($categoryId: String!) {
  emodeCategoryConfigs(where: {category: $categoryId}, first: 1000) {
    asset
    collateral
  }
}
"""


TOP_BORROWERS_QUERY = """
query($symbol: String!, $n: Int!) {
  userReserves(
    first: $n
    orderBy: currentVariableDebt
    orderDirection: desc
    where: {reserve_: {symbol: $symbol}, currentVariableDebt_gt: "0"}
  ) {
    user { id }
  }
}
"""


def fetch_top_borrower_wallets(symbol: str, n: int) -> list[str]:
    """Real wallet cohort for Phase 1 wiring: the top N current borrowers
    of a given reserve asset. Real, live, not a hand-picked list."""
    data = query_subgraph(
        AAVE_V3_ETHEREUM_SUBGRAPH_ID, TOP_BORROWERS_QUERY, {"symbol": symbol, "n": n}
    )
    return [ur["user"]["id"] for ur in data["userReserves"]]


def _index_adjust(scaled: str, index: str) -> int:
    return int(scaled) * int(index) // RAY


def _emode_collateral_assets(category_id: str) -> set[str]:
    data = query_subgraph(
        AAVE_V3_ETHEREUM_SUBGRAPH_ID, EMODE_CATEGORY_ASSETS_QUERY, {"categoryId": category_id}
    )
    return {cfg["asset"].lower() for cfg in data["emodeCategoryConfigs"] if cfg["collateral"]}


def _effective_liquidation_params(
    asset_address: str, reserve: dict, emode: dict | None, emode_collateral_assets: set[str]
) -> tuple[int, int, bool]:
    """Returns (liquidation_threshold_bps, liquidation_bonus_bps,
    emode_applied). eMode's category threshold applies only if the wallet
    is in an eMode category AND this specific asset is eMode-eligible
    collateral in that category -- otherwise the asset's own base reserve
    threshold applies, even for a wallet that IS in eMode for other
    assets (Aave's real mixed-collateral rule, confirmed live)."""
    if emode is not None and asset_address.lower() in emode_collateral_assets:
        return int(emode["liquidationThreshold"]), int(emode["liquidationBonus"]), True
    return int(reserve["reserveLiquidationThreshold"]), int(reserve["reserveLiquidationBonus"]), False


def fetch_wallet_positions(wallet: str) -> list[dict]:
    """Flat records, one per (wallet, asset, side). Amounts are live,
    index-adjusted wei integers, not the raw current* snapshot fields.
    Liquidation threshold/bonus are eMode-aware."""
    data = query_subgraph(
        AAVE_V3_ETHEREUM_SUBGRAPH_ID, USER_QUERY, {"wallet": wallet.lower()}
    )
    user = data.get("user")
    if user is None:
        return []

    emode = user.get("eModeCategoryId")
    emode_collateral_assets = _emode_collateral_assets(emode["id"]) if emode is not None else set()

    records = []
    for ur in user["reserves"]:
        reserve = ur["reserve"]
        asset_address = reserve["underlyingAsset"]
        lt_bps, lb_bps, emode_applied = _effective_liquidation_params(
            asset_address, reserve, emode, emode_collateral_assets
        )
        common = {
            "wallet": wallet.lower(),
            "protocol": "aave_v3",
            "asset_symbol": reserve["symbol"],
            "asset_address": asset_address,
            "asset_decimals": reserve["decimals"],
            "liquidation_threshold_bps": lt_bps,
            "liquidation_bonus_bps": lb_bps,
            "liquidation_protocol_fee_bps": int(reserve["liquidationProtocolFee"] or 0),
            "emode_category_id": emode["id"] if emode is not None else None,
            "emode_applied": emode_applied,
        }

        supply_wei = _index_adjust(ur["scaledATokenBalance"], reserve["liquidityIndex"])
        if supply_wei > 0:
            records.append(
                {
                    **common,
                    "side": "supply",
                    "amount_wei": supply_wei,
                    "usage_as_collateral": ur["usageAsCollateralEnabledOnUser"],
                }
            )

        debt_wei = _index_adjust(ur["scaledVariableDebt"], reserve["variableBorrowIndex"])
        # currentStableDebt is NOT index-adjusted here. [ASSUMED] Aave v3's
        # stable-rate borrow compounds off a per-position rate, not a shared
        # reserve index; the live-adjustment formula for it hasn't been
        # derived or verified. Every wallet checked so far has 0 stable
        # debt. If a real position ever shows nonzero stable debt, this
        # will understate it the same way the unadjusted variable field did
        # -- fix before trusting it, don't ship it silently wrong twice.
        stable_wei = int(ur["currentStableDebt"])
        total_debt_wei = debt_wei + stable_wei
        if total_debt_wei > 0:
            records.append(
                {
                    **common,
                    "side": "borrow",
                    "amount_wei": total_debt_wei,
                    "usage_as_collateral": False,
                }
            )

    return records
