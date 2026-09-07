"""Reproduce the Phase 1 gate check for one wallet: print its live,
index-adjusted position set across Aave v3 and Compound v3, plus the block
each subgraph was synced to. Rule 3 (reproducible): same wallet in, same
numbers out, every run.

Usage: python scripts/reconcile_wallet.py 0x62bc66de718645a1f605638132a57213119aa5e1
"""

import sys

from faultline import aave, compound
from faultline.config import AAVE_V3_ETHEREUM_SUBGRAPH_ID, COMPOUND_V3_ETHEREUM_SUBGRAPH_ID
from faultline.graphql_client import current_block


def human(amount_wei: int, decimals: int) -> str:
    return f"{amount_wei / (10 ** decimals):,.6f}"


def main(wallet: str) -> None:
    aave_block = current_block(AAVE_V3_ETHEREUM_SUBGRAPH_ID)
    compound_block = current_block(COMPOUND_V3_ETHEREUM_SUBGRAPH_ID)

    print(f"wallet: {wallet}")
    print(f"aave v3 subgraph block: {aave_block}")
    print(f"compound v3 subgraph block: {compound_block}")
    print()

    records = aave.fetch_wallet_positions(wallet) + compound.fetch_wallet_positions(wallet)

    if not records:
        print("no positions found on either protocol")
        return

    for r in records:
        amount = human(r["amount_wei"], r["asset_decimals"])
        collateral_flag = " [collateral]" if r["usage_as_collateral"] else ""
        print(
            f"{r['protocol']:12} {r['side']:6} {amount:>18} {r['asset_symbol']}{collateral_flag}"
        )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python scripts/reconcile_wallet.py <wallet_address>")
        sys.exit(1)
    main(sys.argv[1])
