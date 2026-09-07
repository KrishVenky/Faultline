from faultline.config import BASE_INDEX_SCALE, COMPOUND_V3_ETHEREUM_SUBGRAPH_ID
from faultline.graphql_client import query_subgraph

# RESOLVED 2026-09-05 (see BUILDLOG.md "Compound baseBalance: closed"):
# PositionAccounting.baseBalance is the same kind of stale snapshot Aave's
# currentVariableDebt was -- accurate only as of the position's own last
# interaction, not continuously accrued. Confirmed against wallet
# 0x86aef245207e2f93fba083d51852c91a7e711eb6's real USDS debt on DeBank:
# stale baseBalance was off by ~0.19% (2,363 USDS), the formula below lands
# within ~0.0024% (30 USDS, pure query-timing drift, same order as the Aave
# residual). Formula verified straight from Comet's own source
# (CometCore.sol, compound-finance/comet): presentValue = principal *
# (baseSupplyIndex if principal > 0 else baseBorrowIndex) / BASE_INDEX_SCALE
# (1e15). basePrincipal and the market's current indices are what's used
# here, never position.accounting.baseBalance directly.
#
# Collateral balances are NOT index-adjusted: Compound v3 collateral assets
# don't earn yield in the base protocol, PositionCollateralBalance.balance
# is a plain stored amount updated on every collateral-affecting tx, no
# continuous accrual applies. Confirmed: wstETH/cbBTC balances on this same
# wallet matched DeBank exactly with no adjustment.

ACCOUNT_QUERY = """
query($wallet: ID!) {
  account(id: $wallet) {
    positions {
      market {
        id
        configuration {
          symbol
          baseToken { token { id symbol decimals } }
        }
        accounting {
          baseSupplyIndex
          baseBorrowIndex
        }
      }
      accounting {
        basePrincipal
        collateralBalances {
          balance
          collateralToken {
            liquidateCollateralFactor
            liquidationFactor
            token { id symbol decimals }
          }
        }
      }
    }
  }
}
"""


def _present_value(principal: str, base_supply_index: str, base_borrow_index: str) -> int:
    principal = int(principal)
    index = int(base_supply_index) if principal >= 0 else int(base_borrow_index)
    return principal * index // BASE_INDEX_SCALE  # signed: + supply, - borrow


def fetch_wallet_positions(wallet: str) -> list[dict]:
    """Flat records, one per (wallet, market, asset, side)."""
    data = query_subgraph(
        COMPOUND_V3_ETHEREUM_SUBGRAPH_ID, ACCOUNT_QUERY, {"wallet": wallet.lower()}
    )
    account = data.get("account")
    if account is None:
        return []

    records = []
    for position in account["positions"]:
        market = position["market"]
        base_token = market["configuration"]["baseToken"]["token"]
        market_accounting = market["accounting"]

        base_value_wei = _present_value(
            position["accounting"]["basePrincipal"],
            market_accounting["baseSupplyIndex"],
            market_accounting["baseBorrowIndex"],
        )

        if base_value_wei != 0:
            records.append(
                {
                    "wallet": wallet.lower(),
                    "protocol": "compound_v3",
                    "market": market["id"],
                    "asset_symbol": base_token["symbol"],
                    "asset_address": base_token["id"],
                    "asset_decimals": base_token["decimals"],
                    "side": "supply" if base_value_wei > 0 else "borrow",
                    "amount_wei": abs(base_value_wei),
                    "usage_as_collateral": base_value_wei > 0,
                }
            )

        for cb in position["accounting"]["collateralBalances"]:
            if int(cb["balance"]) == 0:
                continue
            token = cb["collateralToken"]["token"]
            records.append(
                {
                    "wallet": wallet.lower(),
                    "protocol": "compound_v3",
                    "market": market["id"],
                    "asset_symbol": token["symbol"],
                    "asset_address": token["id"],
                    "asset_decimals": token["decimals"],
                    "side": "supply",
                    "amount_wei": int(cb["balance"]),
                    "usage_as_collateral": True,
                    "liquidation_factor": cb["collateralToken"]["liquidationFactor"],
                    "liquidate_collateral_factor": cb["collateralToken"][
                        "liquidateCollateralFactor"
                    ],
                }
            )

    return records
