"""Phase 2: the fixed-point cascade solver. Shape approved 2026-09-05
(BUILDLOG.md): apply shock -> compute HF for every wallet -> any wallet
below 1.0 gets liquidated sequentially, worst-HF-first, each one's forced
sale updating the shocked asset's market price before the next wallet in
the same pass is evaluated -> repeat until a full pass produces zero new
liquidations.

Scope, stated not discovered (BUILDLOG.md, "Two assumptions stated before
the solver loop is built"):
- Only the shocked asset's own collateral is sold in a liquidation. A real
  liquidator could choose a wallet's other collateral; not modeled.
- Each wallet is liquidated at most once across the whole run, at whatever
  close factor its HF implies at the moment it first crosses 1.0. Real Aave
  allows repeat liquidation calls on the same position over time; modeling
  that is a further refinement not needed by either reference case.
- All non-shocked-asset prices are held fixed at their live oracle values
  for the whole run.
"""

from faultline.health_factor import compute_health_factor
from faultline.liquidation import compute_seizure
from faultline.uniswap import walk_token0_sell


def run_cascade(
    shocked_asset_address: str,
    shocked_asset_price_start: float,
    quote_asset_price_usd: float,
    wallets: dict[str, list[dict]],
    prices_usd: dict[str, float],
    pool_sqrt_p: float,
    pool_liquidity: float,
    pool_ticks_below: list[dict],
) -> dict:
    """`wallets`: {wallet_address: position_records}. `prices_usd`: base
    USD prices for every asset EXCEPT the shocked one, which starts at
    `shocked_asset_price_start` (USD) and moves as liquidations sell it
    through the pool -- the pool quotes the shocked asset against a quote
    asset (token1, e.g. WETH), not directly in USD, so every pool price is
    converted via `quote_asset_price_usd` (held fixed -- this shock never
    touches the quote asset's own price). Pool state/ticks must already be
    human-scale (see uniswap.human_scale_liquidity) and only cover the
    region below the starting price -- if the shock itself needs to move
    price further than the caller already has ticks for, walking there is
    the caller's job before calling this."""
    shocked_asset_address = shocked_asset_address.lower()
    current_price = shocked_asset_price_start
    sqrt_p = pool_sqrt_p
    liquidity = pool_liquidity
    remaining_ticks = pool_ticks_below

    liquidated: set[str] = set()
    passes: list[dict] = []

    while True:
        prices = {**prices_usd, shocked_asset_address: current_price}
        hf_by_wallet = {
            w: compute_health_factor(records, prices)["health_factor"]
            for w, records in wallets.items()
            if w not in liquidated
        }
        crossed = sorted(
            (w for w, hf in hf_by_wallet.items() if hf < 1.0),
            key=lambda w: hf_by_wallet[w],
        )

        if not crossed:
            break

        pass_events = []
        for wallet in crossed:
            records = wallets[wallet]
            debt = next(r for r in records if r["side"] == "borrow")
            collateral = next(
                r for r in records
                if r["side"] == "supply"
                and r["usage_as_collateral"]
                and r["asset_address"].lower() == shocked_asset_address
            )
            debt_amount = debt["amount_wei"] / 10 ** debt["asset_decimals"]
            collateral_amount = collateral["amount_wei"] / 10 ** collateral["asset_decimals"]

            seizure = compute_seizure(
                total_debt_amount=debt_amount,
                debt_asset_price=prices[debt["asset_address"].lower()],
                collateral_asset_price=current_price,
                liquidation_bonus_bps=collateral["liquidation_bonus_bps"],
                liquidation_protocol_fee_bps=collateral.get("liquidation_protocol_fee_bps", 0),
                user_collateral_balance=collateral_amount,
                health_factor=hf_by_wallet[wallet],
            )

            swap = walk_token0_sell(
                sqrt_p, liquidity, remaining_ticks,
                amount0_budget=seizure["liquidator_receives"], target_sqrt_p=None,
            )
            sqrt_p = swap["final_sqrt_p"]
            liquidity = swap["final_liquidity"]
            remaining_ticks = remaining_ticks[swap["ticks_crossed"]:]
            price_before = current_price
            current_price = swap["final_price_token1_per_token0"] * quote_asset_price_usd

            liquidated.add(wallet)
            pass_events.append({
                "wallet": wallet,
                "health_factor_at_trigger": hf_by_wallet[wallet],
                "close_factor": seizure["close_factor"],
                "collateral_sold": seizure["liquidator_receives"],
                "price_before": price_before,
                "price_after": current_price,
                "depth_exhausted": swap["depth_exhausted"],
            })

        passes.append({"price_at_start_of_pass": prices[shocked_asset_address], "events": pass_events})

    return {
        "final_price": current_price,
        "liquidated_wallets": list(liquidated),
        "passes": passes,
        "converged": True,
    }
