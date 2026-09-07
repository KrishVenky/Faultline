"""One-off hand-walk verification script, NOT the Phase 2 solver. Simulates
selling the primary demo wallet's liquidated wstETH collateral through the
real wstETH/WETH pool, tick by tick, using the actual Uniswap v3 swap
invariant -- not a flat slippage assumption. Reference calculation for the
Phase 2 fixed-point loop to be checked against once written.

Pool state, tick data, and oracle prices are the live values fetched and
logged in BUILDLOG.md, 2026-09-05 ("Cascade test: floor shock through the
real pool"). Not reproducible byte-for-byte on a later run (pool state
moves every block) -- this file documents the METHOD; BUILDLOG.md has the
actual numbers from this run, block-stamped.
"""

import json

Q96 = 2**96


def walk_token0_sell(sqrt_p_start: float, L_start: float, ticks_below: list[dict],
                      amount0_budget: float, target_sqrt_p: float | None = None) -> dict:
    """zeroForOne walk: consumes token0 (wstETH) selling downward through
    the real tick structure, stopping at whichever comes first --
    `amount0_budget` exhausted, `target_sqrt_p` reached, or real liquidity
    runs out (depth exhausted). Setting amount0_budget=inf with a
    target_sqrt_p answers 'how much volume does it take the pool to reach
    this price', independent of any specific wallet's sale size."""
    sqrt_p = sqrt_p_start
    L = L_start
    amount0_remaining = amount0_budget
    amount0_used = 0.0
    total_amount1_out = 0.0
    ticks_crossed = 0

    for t in ticks_below:
        tick_sqrt_p = 1.0001 ** (t["tick_idx"] / 2)
        if target_sqrt_p is not None and tick_sqrt_p <= target_sqrt_p:
            # target price falls within the current range, before this tick
            sqrt_p_new = target_sqrt_p
            amount0_needed = L * (1 / sqrt_p_new - 1 / sqrt_p)
            if amount0_needed <= amount0_remaining:
                total_amount1_out += L * (sqrt_p - sqrt_p_new)
                amount0_used += amount0_needed
                amount0_remaining -= amount0_needed
                sqrt_p = sqrt_p_new
                return _result(sqrt_p, L, amount0_used, amount0_remaining, total_amount1_out,
                                ticks_crossed, "target_reached")

        amount0_to_boundary = L * (1 / tick_sqrt_p - 1 / sqrt_p)

        if amount0_to_boundary >= amount0_remaining:
            sqrt_p_new = 1 / (1 / sqrt_p + amount0_remaining / L)
            total_amount1_out += L * (sqrt_p - sqrt_p_new)
            amount0_used += amount0_remaining
            amount0_remaining = 0
            sqrt_p = sqrt_p_new
            return _result(sqrt_p, L, amount0_used, amount0_remaining, total_amount1_out,
                            ticks_crossed, "budget_filled")

        total_amount1_out += L * (sqrt_p - tick_sqrt_p)
        amount0_used += amount0_to_boundary
        amount0_remaining -= amount0_to_boundary
        sqrt_p = tick_sqrt_p
        L = L - t["liquidity_net"]
        ticks_crossed += 1

    # ran out of real, initialized-tick liquidity before satisfying the
    # budget or reaching the target -- this is the actual depth-exhaustion
    # case, distinct from "budget was infinite so remaining is always > 0".
    return _result(sqrt_p, L, amount0_used, amount0_remaining, total_amount1_out,
                    ticks_crossed, "ticks_exhausted")


def _result(sqrt_p, L, amount0_used, amount0_remaining, amount1_out, ticks_crossed, stop_reason):
    return {
        "stop_reason": stop_reason,
        "depth_exhausted": stop_reason == "ticks_exhausted",
        "amount0_used": amount0_used,
        "amount0_unfilled": amount0_remaining if amount0_remaining != float("inf") else None,
        "amount1_out": amount1_out,
        "ticks_crossed": ticks_crossed,
        "final_price_token1_per_token0": sqrt_p ** 2,
        "final_sqrt_p": sqrt_p,
        "final_liquidity": L,
    }


if __name__ == "__main__":
    ticks = json.load(open("research/scratch_ticks.json"))
    ticks_below = sorted(
        [t for t in ticks if t["tick_idx"] <= 2176], key=lambda t: -t["tick_idx"]
    )

    SQRT_PRICE_X96 = 88335781225215123956856795714
    LIQUIDITY_RAW = 5237117975045374818884027
    DECIMALS0 = 18  # wstETH
    DECIMALS1 = 18  # WETH
    FEE_TIER = 100
    WSTETH_TO_SELL = 415.589657415625690252

    WSTETH_ORACLE_BEFORE = 3051.4799  # $, AaveOracle, this session
    WSTETH_ORACLE_FLOOR = 1718.7752   # $, floor shock (BUILDLOG "Floor shock, hand-computed")
    WETH_ORACLE = 2464.1308           # $, AaveOracle, unaffected by this shock

    scale = 10 ** ((DECIMALS0 + DECIMALS1) / 2)
    liquidity_human = LIQUIDITY_RAW / scale
    ticks_below_human = [
        {**t, "liquidity_net": t["liquidity_net"] / scale} for t in ticks_below
    ]

    price_before_pool = 1.243123112164817732024467071464814  # token1Price, WETH per wstETH
    shock_ratio = WSTETH_ORACLE_FLOOR / WSTETH_ORACLE_BEFORE
    price_shocked_pool = price_before_pool * shock_ratio
    target_sqrt_p = price_shocked_pool ** 0.5

    sqrt_p_start = SQRT_PRICE_X96 / Q96

    # Phase A: how much of THIS pool's own depth would arbitrage have to
    # consume to bring it down to the shocked (oracle-implied) price on its
    # own, before wallet #1's specific liquidation sale adds anything.
    # amount0_budget=inf: stop only at the target price or when real ticks
    # run out (depth exhausted), not at any fixed sale size.
    phase_a = walk_token0_sell(
        sqrt_p_start, liquidity_human, ticks_below_human,
        amount0_budget=float("inf"), target_sqrt_p=target_sqrt_p,
    )

    print("=== Phase A: pool re-pricing to the 43.6740% oracle shock ===")
    print(f"target: {price_shocked_pool:.6f} WETH/wstETH ({shock_ratio:.6f}x of {price_before_pool:.6f})")
    print(f"ticks crossed to get there: {phase_a['ticks_crossed']}")
    print(f"depth exhausted before reaching target: {phase_a['depth_exhausted']}")
    print(f"implied wstETH sold by arbitrage to reach it: {phase_a['amount0_used']:.6f}")
    print(f"price actually reached: {phase_a['final_price_token1_per_token0']:.6f} WETH/wstETH")
    print()

    if phase_a["depth_exhausted"]:
        print("Pool ran out of real, initialized-tick liquidity before reaching the")
        print("43.67% shocked price on its own. This pool cannot absorb that large a")
        print("re-pricing through its own depth alone -- the shock has to be an")
        print("external/market-wide event, not something this pool's own arbitrage")
        print("volume could cause by itself. Continuing wallet #1's sale from")
        print("wherever the walk actually stopped.")
        print()

    # Phase B: wallet #1's actual liquidated collateral, sold on top of
    # whatever state phase A left the pool in.
    remaining_ticks = ticks_below_human[phase_a["ticks_crossed"]:]
    phase_b = walk_token0_sell(
        phase_a["final_sqrt_p"], phase_a["final_liquidity"], remaining_ticks,
        amount0_budget=WSTETH_TO_SELL, target_sqrt_p=None,
    )

    price_final_pool = phase_b["final_price_token1_per_token0"]
    wsteth_usd_final = price_final_pool * WETH_ORACLE

    print("=== Phase B: selling wallet #1's 415.589657 wstETH on top of that ===")
    print(f"ticks crossed: {phase_b['ticks_crossed']}")
    print(f"depth exhausted: {phase_b['depth_exhausted']} (unfilled: {phase_b['amount0_unfilled']:.6f} wstETH)")
    print(f"WETH received: {phase_b['amount1_out']:.6f}")
    print(f"pool price before phase B: {phase_a['final_price_token1_per_token0']:.6f} WETH/wstETH")
    print(f"pool price after phase B:  {price_final_pool:.6f} WETH/wstETH")
    incremental_move_pct = (
        (phase_a["final_price_token1_per_token0"] - price_final_pool)
        / phase_a["final_price_token1_per_token0"] * 100
    )
    print(f"incremental move from wallet #1's sale alone: -{incremental_move_pct:.4f}%")
    print()
    print(f"=== resulting wstETH market price (post-impact, via WETH oracle ${WETH_ORACLE}) ===")
    print(f"${wsteth_usd_final:.4f} (vs oracle-shocked ${WSTETH_ORACLE_FLOOR}, vs pre-shock ${WSTETH_ORACLE_BEFORE})")
