"""Regression test: re-run the primary wallet's floor shock and the
five-wallet cascade check THROUGH faultline.aave.fetch_wallet_positions
(now eMode-aware) and faultline.health_factor.compute_health_factor, and
confirm they reproduce the numbers computed by hand in BUILDLOG.md,
2026-09-05 ("Floor shock, hand-computed" and "Cascade test: floor shock
through the real pool" / "A third, bigger bug").

Deliberately uses the SAME price snapshot as the hand calc (hardcoded
below, not re-fetched live) -- the point of this test is to confirm the
fetch + HF-computation code path matches the hand math, not to re-verify
prices that were already verified live earlier this session. Re-fetching
live prices here would let ordinary price drift masquerade as a logic
mismatch or vice versa.
"""

from faultline import aave
from faultline.health_factor import compute_health_factor

WSTETH = "0x7f39c581f595b53c5cb19bd0b3f8da6c935e2ca0"
WETH = "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"
WEETH = "0xcd5fe23c85820f7b72d0926fc9b05b43e359b7ee"
RSETH = "0xa1290d69c65a6fe4df752f95823fae25cb99e5a7"
USDC = "0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48"
CBBTC = "0xcbb7c0000ab88b473b1f5afd9ef808440eed33bf"
USDT = "0xdac17f958d2ee523a2206206994597c13d831ec7"

BASE_PRICES = {
    WETH: 2464.1308,
    WEETH: 2711.6605,
    RSETH: 2653.6721,
    USDC: 1.0,
    CBBTC: 79661.5488,
    USDT: 1.00004389,
}
WSTETH_PRE = 3051.4799
WSTETH_FLOOR = 1718.7752   # HF = 1.0 for the primary wallet, by construction
WSTETH_POST_IMPACT = 1638.5444  # after the real pool's tick walk


def prices(wsteth_price: float) -> dict[str, float]:
    return {**BASE_PRICES, WSTETH: wsteth_price}


CASES = [
    ("0x86aef245207e2f93fba083d51852c91a7e711eb6", "primary, pre-shock", WSTETH_PRE, 1.700187),
    ("0x86aef245207e2f93fba083d51852c91a7e711eb6", "primary, at floor", WSTETH_FLOOR, 1.000000),
    ("0x9600a48ed0f931d0c422d574e3275a90d8b22745", "wallet 1, pre-shock", WSTETH_PRE, 1.028910),
    ("0x9600a48ed0f931d0c422d574e3275a90d8b22745", "wallet 1, post-impact", WSTETH_POST_IMPACT, 0.993578),
    ("0x893aa69fbaa1ee81b536f0fbe3a3453e86290080", "wallet 2, pre-shock", WSTETH_PRE, 1.055050),
    ("0x893aa69fbaa1ee81b536f0fbe3a3453e86290080", "wallet 2, post-impact", WSTETH_POST_IMPACT, 0.566527),
    ("0xf7462251c14d2fb83c7ab96367a7985423c83010", "wallet 3, pre-shock", WSTETH_PRE, 1.027820),
    ("0xf7462251c14d2fb83c7ab96367a7985423c83010", "wallet 3, post-impact", WSTETH_POST_IMPACT, 1.026219),
    ("0xd8495b95a3a6a85f4e3baa003e8b7ed1ed85562d", "wallet 4, unaffected", WSTETH_POST_IMPACT, 1.020707),
    ("0xc1914872a1dd8e7a39ac6d5ee0d6fa9fcecf001e", "wallet 5, unaffected", WSTETH_POST_IMPACT, 1.124908),
]

TOLERANCE = 0.001  # relative

if __name__ == "__main__":
    all_passed = True
    for wallet, label, wsteth_price, expected_hf in CASES:
        records = aave.fetch_wallet_positions(wallet)
        result = compute_health_factor(records, prices(wsteth_price))
        hf = result["health_factor"]
        rel_error = abs(hf - expected_hf) / expected_hf
        passed = rel_error <= TOLERANCE
        all_passed &= passed
        status = "PASS" if passed else "FAIL"
        print(f"[{status}] {label:24} computed={hf:.6f}  hand={expected_hf:.6f}  rel_err={rel_error:.6f}")

    print()
    print("ALL PASSED" if all_passed else "SOME FAILED -- do not trust the solver on this yet")
