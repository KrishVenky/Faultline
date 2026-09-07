"""Live version of scripts/generate_reference_fixture.py: same wallets,
same pool, same solver, but every price and every piece of pool state is
fetched fresh at call time instead of using the values logged in
BUILDLOG.md. This is what the interactive slider (section 9, step 2) calls
-- a judge dragging it is looking at a real computation, not a replay.

Scope, deliberately narrow, matching the frozen reference pair (not the
wider 26-wallet cohort -- section 9 step 4 keeps that out of the primary
visualization): the shock is always applied to wstETH, and the wallet
universe is always {primary trigger, genuine victim}. A shock too small to
liquidate the trigger wallet correctly produces an empty cascade (nobody
liquidated) -- that's a real result, not an error.
"""

from faultline import aave
from faultline.graph import build_graph
from faultline.oracle import fetch_chain_head, fetch_oracle_price_usd
from faultline.solver import run_cascade
from faultline.uniswap import (
    compute_depth_profile,
    fetch_pool_state,
    fetch_pool_ticks,
    human_scale_liquidity,
    walk_token0_sell,
)

WSTETH = "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
CBBTC = "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf"

PRIMARY_WALLET = "0x86aef245207e2f93fba083d51852c91a7e711eb6"
VICTIM_WALLET = "0xcc997fe9fdd5957ca3060af68318f754d75016d3"

POOL_ADDRESS = "0x109830a1aaad605bbf02a9dfa7b0b92ec2fb7daa"


def compute_live_cascade(shock_pct: float) -> dict:
    """shock_pct: 0-100, percent drop applied to wstETH's live oracle
    price. Returns the same shape as the frozen fixture (flat JSON, no
    nested classes) so the frontend's existing timeline/rendering code
    doesn't need a second code path for live vs. precomputed."""
    block_number = fetch_chain_head()

    wsteth_price_before = fetch_oracle_price_usd(WSTETH)
    weth_price = fetch_oracle_price_usd(WETH)
    prices_usd = {
        WETH: weth_price,
        USDC: fetch_oracle_price_usd(USDC),
        USDT: fetch_oracle_price_usd(USDT),
        CBBTC: fetch_oracle_price_usd(CBBTC),
    }
    shocked_price = wsteth_price_before * (1 - shock_pct / 100)

    wallets = {
        PRIMARY_WALLET: aave.fetch_wallet_positions(PRIMARY_WALLET),
        VICTIM_WALLET: aave.fetch_wallet_positions(VICTIM_WALLET),
    }
    graph_before = build_graph(wallets[PRIMARY_WALLET] + wallets[VICTIM_WALLET])

    pool = fetch_pool_state(POOL_ADDRESS)
    ticks = fetch_pool_ticks(POOL_ADDRESS)
    ticks_below = sorted(
        [t for t in ticks if t["tick_idx"] <= pool["tick"]], key=lambda t: -t["tick_idx"]
    )
    scale = 10 ** ((pool["token0_decimals"] + pool["token1_decimals"]) / 2)
    ticks_human = [{**t, "liquidity_net": t["liquidity_net"] / scale} for t in ticks_below]
    liquidity_human = human_scale_liquidity(pool["liquidity_raw"], pool["token0_decimals"], pool["token1_decimals"])

    # Reposition (not a modeled trade -- BUILDLOG.md, 2026-09-06, "Phase A
    # methodology corrected"): assume market-wide arbitrage across many
    # venues has already brought this pool to the oracle-shocked fair
    # value, rather than modeling this one pool as absorbing the entire
    # repricing volume itself. walk_token0_sell is reused only to compute
    # which LP ranges are active at the new price (a structural fact of
    # the tick data, independent of how the price got there) -- its
    # amount0_used from this step is not a real trade size and is
    # discarded, not reported.
    target_ratio = pool["price_token1_per_token0"] * (shocked_price / wsteth_price_before)
    target_sqrt_p = target_ratio**0.5
    sqrt_p_start = pool["sqrt_price_x96"] / 2**96

    if target_sqrt_p < sqrt_p_start:
        reposition = walk_token0_sell(
            sqrt_p_start, liquidity_human, ticks_human,
            amount0_budget=float("inf"), target_sqrt_p=target_sqrt_p,
        )
        remaining_ticks = ticks_human[reposition["ticks_crossed"]:]
        pool_sqrt_p, pool_liquidity = reposition["final_sqrt_p"], reposition["final_liquidity"]
        reposition_depth_exhausted = reposition["depth_exhausted"]
        depth_profile = compute_depth_profile(liquidity_human, ticks_human[: reposition["ticks_crossed"]])
    else:
        # shock_pct <= 0 (or rounding): no downward repricing needed
        remaining_ticks = ticks_human
        pool_sqrt_p, pool_liquidity = sqrt_p_start, liquidity_human
        reposition_depth_exhausted = False
        depth_profile = {"starting_liquidity": liquidity_human, "ticks_to_depletion_pct": {}}

    result = run_cascade(
        shocked_asset_address=WSTETH,
        shocked_asset_price_start=shocked_price,
        quote_asset_price_usd=weth_price,
        wallets=wallets,
        prices_usd=prices_usd,
        pool_sqrt_p=pool_sqrt_p,
        pool_liquidity=pool_liquidity,
        pool_ticks_below=remaining_ticks,
    )

    return {
        "live": True,
        "block_number": block_number,
        "shock": {
            "asset_symbol": "wstETH",
            "asset_address": WSTETH,
            "price_before_usd": wsteth_price_before,
            "price_after_oracle_shock_usd": shocked_price,
            "shock_pct": shock_pct,
        },
        "pool": {
            "address": POOL_ADDRESS,
            "pair": "wstETH/WETH",
            "reposition_depth_exhausted": reposition_depth_exhausted,
            "depth_profile": depth_profile,
            "liquidity_at_shocked_price": pool_liquidity,
        },
        "graph_before": {
            "nodes": [{"id": f"{n[0]}:{n[1]}", **d} for n, d in graph_before.nodes(data=True)],
            "edges": [
                {"source": f"{u[0]}:{u[1]}", "target": f"{v[0]}:{v[1]}", **d}
                for u, v, d in graph_before.edges(data=True)
            ],
        },
        "cascade": {
            "converged": result["converged"],
            "pass_count": len(result["passes"]),
            "final_price_usd": round(result["final_price"], 4),
            "liquidated_wallets": result["liquidated_wallets"],
            "passes": result["passes"],
        },
    }
