"""Full-cohort run: does the cascade go past the isolated primary ->
0xcc997fe9... pair once the whole real, known wstETH-linked cohort is in
play? Answers BUILDLOG.md's open question directly, rather than assuming
the isolated 2-wallet run was the complete picture.
"""

import json

from faultline import aave
from faultline.solver import run_cascade
from faultline.uniswap import human_scale_liquidity, walk_token0_sell

WSTETH = "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
WEETH = "0xcd5fe23c85820f7b72d0926fc9b05b43e359b7ee"
RSETH = "0xa1290d69c65a6fe4df752f95823fae25cb99e5a7"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
CBBTC = "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"

PRICES_USD = {
    WETH: 2464.1308, WEETH: 2711.6605, RSETH: 2653.6721,
    USDC: 1.0, CBBTC: 79661.5488, USDT: 1.00004389,
}

WSTETH_FLOOR = 1718.7752
SHOCK_START_PRICE = WSTETH_FLOOR * (1 - 1e-6)

EXTRA_WALLETS = [
    "0xf7462251c14d2fb83c7ab96367a7985423c83010",  # wallet 3 (near-miss shape)
    "0xd8495b95a3a6a85f4e3baa003e8b7ed1ed85562d",  # wallet 4 (no wstETH collateral)
    "0xc1914872a1dd8e7a39ac6d5ee0d6fa9fcecf001e",  # wallet 5 (no wstETH collateral)
]

if __name__ == "__main__":
    cohort = json.load(open("research/clean_chain_wallets.json"))
    all_wallets = list(dict.fromkeys(cohort + EXTRA_WALLETS))
    print(f"full cohort: {len(all_wallets)} wallets")

    wallets = {}
    for w in all_wallets:
        wallets[w] = aave.fetch_wallet_positions(w)

    ticks = json.load(open("research/scratch_ticks.json"))
    ticks_below = sorted([t for t in ticks if t["tick_idx"] <= 2176], key=lambda t: -t["tick_idx"])
    ticks_human = [{**t, "liquidity_net": t["liquidity_net"] / 1e18} for t in ticks_below]
    liquidity_human = human_scale_liquidity(5237117975045374818884027, 18, 18)

    price_before_pool = 1.243123112164817732024467071464814
    target_sqrt_p = (price_before_pool * (WSTETH_FLOOR / 3051.4799)) ** 0.5
    phase_a = walk_token0_sell(
        88335781225215123956856795714 / 2**96, liquidity_human, ticks_human,
        amount0_budget=float("inf"), target_sqrt_p=target_sqrt_p,
    )
    remaining_ticks = ticks_human[phase_a["ticks_crossed"]:]

    result = run_cascade(
        shocked_asset_address=WSTETH,
        shocked_asset_price_start=SHOCK_START_PRICE,
        quote_asset_price_usd=2464.1308,
        wallets=wallets,
        prices_usd=PRICES_USD,
        pool_sqrt_p=phase_a["final_sqrt_p"],
        pool_liquidity=phase_a["final_liquidity"],
        pool_ticks_below=remaining_ticks,
    )

    print(f"converged: {result['converged']}, {len(result['passes'])} pass(es)")
    print(f"final wstETH price: ${result['final_price']:.4f}")
    print(f"total liquidated: {len(result['liquidated_wallets'])} of {len(all_wallets)}")
    print()
    for i, p in enumerate(result["passes"], 1):
        print(f"--- pass {i} (price at start: ${p['price_at_start_of_pass']:.4f}) ---")
        for e in p["events"]:
            print(f"  {e['wallet']}: HF={e['health_factor_at_trigger']:.6f}, "
                  f"close_factor={e['close_factor']:.0%}, sold={e['collateral_sold']:.4f} wstETH, "
                  f"price ${e['price_before']:.4f} -> ${e['price_after']:.4f}, "
                  f"depth_exhausted={e['depth_exhausted']}")
