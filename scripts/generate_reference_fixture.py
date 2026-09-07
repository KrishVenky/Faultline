"""Generates the canonical reference-cascade fixture: the frozen, externally
reconciled, solver-verified 2-hop cascade (primary wallet ->
0xcc997fe9...). This is what the FastAPI boundary serves and the frontend
renders -- per the sequencing rule, nothing in the visualization layer
starts before this fixture exists. Flat JSON throughout, no nested class
serialization (the wire-format decision, 2026-09-05).

Reproducible in shape, not byte-for-byte (rule 3): the shock parameters,
wallets, and pool are fixed inputs; live position amounts drift block to
block from interest accrual the same small amount every reconciliation
this session has shown. Re-running regenerates a fixture that matches in
every respect that matters -- HF crossing 1.0, the liquidation event, the
final price -- not necessarily to the last wei.
"""

import json

from faultline import aave
from faultline.graph import build_graph
from faultline.solver import run_cascade
from faultline.uniswap import compute_depth_profile, human_scale_liquidity, walk_token0_sell

WSTETH = "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"
CBBTC = "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf"

PRIMARY_WALLET = "0x86aef245207e2f93fba083d51852c91a7e711eb6"
VICTIM_WALLET = "0xcc997fe9fdd5957ca3060af68318f754d75016d3"

PRICES_USD = {WETH: 2464.1308, USDC: 1.0, USDT: 1.00004389, CBBTC: 79661.5488}
WSTETH_PRE_SHOCK = 3051.4799
WSTETH_FLOOR = 1718.7752
SHOCK_START_PRICE = WSTETH_FLOOR * (1 - 1e-6)

POOL_ADDRESS = "0x109830a1aaad605bbf02a9dfa7b0b92ec2fb7daa"
POOL_LIQUIDITY_RAW = 5237117975045374818884027
POOL_SQRT_PRICE_X96 = 88335781225215123956856795714
POOL_PRICE_TOKEN1_PER_TOKEN0 = 1.243123112164817732024467071464814

if __name__ == "__main__":
    wallets = {
        PRIMARY_WALLET: aave.fetch_wallet_positions(PRIMARY_WALLET),
        VICTIM_WALLET: aave.fetch_wallet_positions(VICTIM_WALLET),
    }

    all_records = wallets[PRIMARY_WALLET] + wallets[VICTIM_WALLET]
    graph_before = build_graph(all_records)

    ticks = json.load(open("research/scratch_ticks.json"))
    ticks_below = sorted([t for t in ticks if t["tick_idx"] <= 2176], key=lambda t: -t["tick_idx"])
    ticks_human = [{**t, "liquidity_net": t["liquidity_net"] / 1e18} for t in ticks_below]
    liquidity_human = human_scale_liquidity(POOL_LIQUIDITY_RAW, 18, 18)

    # Reposition (not a modeled trade -- BUILDLOG.md, 2026-09-06, "Phase A
    # methodology corrected"): the pool is assumed to already reflect the
    # oracle-shocked fair value via market-wide arbitrage across many
    # venues, not this one pool absorbing the whole repricing volume.
    # walk_token0_sell is reused only to compute which LP ranges are
    # active at the new price (a structural fact of the tick data); its
    # amount0_used is not a real trade size and is discarded, not reported.
    target_sqrt_p = (POOL_PRICE_TOKEN1_PER_TOKEN0 * (WSTETH_FLOOR / WSTETH_PRE_SHOCK)) ** 0.5
    reposition = walk_token0_sell(
        POOL_SQRT_PRICE_X96 / 2**96, liquidity_human, ticks_human,
        amount0_budget=float("inf"), target_sqrt_p=target_sqrt_p,
    )
    remaining_ticks = ticks_human[reposition["ticks_crossed"]:]
    depth_profile = compute_depth_profile(liquidity_human, ticks_human[: reposition["ticks_crossed"]])

    result = run_cascade(
        shocked_asset_address=WSTETH,
        shocked_asset_price_start=SHOCK_START_PRICE,
        quote_asset_price_usd=PRICES_USD[WETH],
        wallets=wallets,
        prices_usd=PRICES_USD,
        pool_sqrt_p=reposition["final_sqrt_p"],
        pool_liquidity=reposition["final_liquidity"],
        pool_ticks_below=remaining_ticks,
    )

    fixture = {
        "description": "Reference cascade: primary wallet's oracle-shock liquidation "
                        "forces a wstETH sale through real Uniswap v3 depth, moving the "
                        "market price enough to independently liquidate a second wallet "
                        "with no shared protocol or debt asset.",
        "shock": {
            "asset_symbol": "wstETH",
            "asset_address": WSTETH,
            "price_before_usd": WSTETH_PRE_SHOCK,
            "price_after_oracle_shock_usd": WSTETH_FLOOR,
            "shock_pct": round((1 - WSTETH_FLOOR / WSTETH_PRE_SHOCK) * 100, 4),
        },
        "pool": {
            "address": POOL_ADDRESS,
            "pair": "wstETH/WETH",
            "fee_tier_bps": 1,
            "depth_profile": depth_profile,
            "liquidity_at_shocked_price": reposition["final_liquidity"],
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

    with open("faultline/fixtures/reference_cascade.json", "w") as f:
        json.dump(fixture, f, indent=2, default=str)

    print("wrote faultline/fixtures/reference_cascade.json")
    print(f"converged={result['converged']}, passes={len(result['passes'])}, "
          f"final_price=${result['final_price']:.4f}")
