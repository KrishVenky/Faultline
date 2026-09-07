"""Section 14 (CLAUDE.md, 2026-09-08): arbitrary wallet lookup on the live
solver. Real address in, the actual pipeline run against whatever it
actually holds -- not the fixed demo pair. Every failure mode stated
honestly: a missing price, an unpriceable asset, no positions at all, a
collateral asset with no queryable pool. Nothing here fakes a number to
fill a gap (rule 2, section 2)."""

from faultline import aave, compound
from faultline.health_factor import compute_health_factor
from faultline.oracle import fetch_oracle_price_usd
from faultline.uniswap import eligible_pools_for_asset

# Assets Faultline already has a verified oracle-adjacent story for --
# used only to prioritize which unpriced assets are worth calling out by
# name in an honest gap message versus a generic "no oracle price found."
_KNOWN_ASSET_SYMBOLS: dict[str, str] = {}


def _try_fetch_price(asset_address: str) -> float | None:
    """AaveOracle.getAssetPrice for an arbitrary asset. Returns None,
    not a fabricated number, if the call reverts or returns 0 (Aave's
    oracle returning 0 means the asset isn't configured there -- a real
    signal, not an error to paper over)."""
    try:
        price = fetch_oracle_price_usd(asset_address)
    except Exception:
        return None
    return price if price > 0 else None


def fetch_wallet_exposure(address: str) -> dict:
    """The honest version of 'run the pipeline on this wallet': real
    positions, real prices where they exist, explicit gaps where they
    don't. No HF is reported unless every collateral/debt asset in it has
    a real price -- a partial HF presented as complete would be worse
    than no HF at all."""
    address = address.lower()
    records = aave.fetch_wallet_positions(address) + compound.fetch_wallet_positions(address)

    if not records:
        return {
            "address": address,
            "found": False,
            "message": "No open Aave v3 or Compound v3 positions found for this address.",
        }

    relevant = [r for r in records if r["side"] == "borrow" or r.get("usage_as_collateral")]
    unique_assets = {(r["asset_address"].lower(), r["asset_symbol"]) for r in relevant}

    prices: dict[str, float] = {}
    missing_prices: list[dict] = []
    for asset_address, symbol in unique_assets:
        price = _try_fetch_price(asset_address)
        if price is None:
            missing_prices.append({"asset_address": asset_address, "asset_symbol": symbol})
        else:
            prices[asset_address] = price

    positions_out = [
        {
            "protocol": r["protocol"],
            "asset_symbol": r["asset_symbol"],
            "asset_address": r["asset_address"].lower(),
            "side": r["side"],
            "amount": r["amount_wei"] / 10 ** r["asset_decimals"],
            "usage_as_collateral": bool(r.get("usage_as_collateral")),
            "price_usd": prices.get(r["asset_address"].lower()),
        }
        for r in records
    ]

    if missing_prices:
        return {
            "address": address,
            "found": True,
            "health_factor_computable": False,
            "reason": (
                "No live oracle price available for "
                + ", ".join(f"{m['asset_symbol']} ({m['asset_address']})" for m in missing_prices)
                + " -- Aave's oracle doesn't have this asset configured. "
                "Health factor is not shown rather than computed on incomplete prices."
            ),
            "positions": positions_out,
        }

    hf_result = compute_health_factor(relevant, prices)

    # Shock-modeling eligibility: the wallet's largest collateral position
    # by USD value, only if a real, address-filtered pool exists for it
    # (BUILDLOG.md, "Pool selection rule for price impact") -- if not,
    # say so, don't force a shock scenario that has no real depth data.
    collateral_positions = [
        r for r in relevant if r["side"] == "supply" and r.get("usage_as_collateral")
    ]
    shock_target = None
    if collateral_positions:
        largest = max(
            collateral_positions,
            key=lambda r: (r["amount_wei"] / 10 ** r["asset_decimals"]) * prices[r["asset_address"].lower()],
        )
        # Broader than this wallet's own holdings on purpose -- the
        # deepest real pool for a collateral asset is very often paired
        # against WETH/USDC/USDT, not necessarily something this specific
        # wallet also holds. Still real, address-verified, governance-
        # listed assets, just scoped to all of Aave's reserves instead of
        # one wallet's own asset set (see aave.fetch_all_reserve_addresses).
        known_assets = aave.fetch_all_reserve_addresses()
        pools = eligible_pools_for_asset(largest["asset_address"], known_assets)
        if pools:
            shock_target = {
                "asset_symbol": largest["asset_symbol"],
                "asset_address": largest["asset_address"].lower(),
                "pool_address": pools[0]["pool_address"],
                "pool_pair_other_token": pools[0]["other_token_symbol"],
                "pool_tvl_usd": pools[0]["total_value_locked_usd"],
            }
        else:
            shock_target = {
                "asset_symbol": largest["asset_symbol"],
                "asset_address": largest["asset_address"].lower(),
                "pool_address": None,
                "reason": "No eligible Uniswap v3 pool found for this asset against a "
                "known reserve asset -- shock modeling isn't available for this wallet.",
            }

    return {
        "address": address,
        "found": True,
        "health_factor_computable": True,
        "health_factor": hf_result["health_factor"],
        "collateral_value_usd": hf_result["collateral_value_usd"],
        "debt_value_usd": hf_result["debt_value_usd"],
        "positions": positions_out,
        "shock_target": shock_target,
    }
