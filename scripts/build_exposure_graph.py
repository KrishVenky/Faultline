"""Phase 1 closer: wire fetch + graph together over a real wallet set and
print the result. Rule 3 (reproducible): real wallets, live query, same
code path as everything already verified this session.

Anchor wallets (BUILDLOG.md, 2026-09-05 "Demo wallet decision"):
- primary: 0x86aef245207e2f93fba083d51852c91a7e711eb6 (cross-protocol,
  wstETH/cbBTC shared collateral, USDT on Aave + USDS on Compound)
- secondary reconciliation reference: 0x62bc66de718645a1f605638132a57213119aa5e1
  (osETH/WETH, the original Phase 1 gate wallet)

Plus a real cohort (top WETH borrowers on Aave, scope-slider tier: 20) so
the pipeline is shown working over more than two hand-picked wallets.
"""

from faultline import aave, compound, graph, uniswap

PRIMARY_DEMO_WALLET = "0x86aef245207e2f93fba083d51852c91a7e711eb6"
SECONDARY_REFERENCE_WALLET = "0x62bc66de718645a1f605638132a57213119aa5e1"
COHORT_SIZE = 20


def main() -> None:
    cohort = aave.fetch_top_borrower_wallets("WETH", COHORT_SIZE)
    wallets = list(dict.fromkeys([PRIMARY_DEMO_WALLET, SECONDARY_REFERENCE_WALLET, *cohort]))
    print(f"wallet set: {len(wallets)} wallets ({PRIMARY_DEMO_WALLET} primary, "
          f"{SECONDARY_REFERENCE_WALLET} secondary, {len(cohort)} top WETH borrowers)")

    records = []
    for w in wallets:
        records += aave.fetch_wallet_positions(w)
        records += compound.fetch_wallet_positions(w)
    print(f"{len(records)} position records fetched")

    g = graph.build_graph(records)
    n_wallets = sum(1 for _, d in g.nodes(data=True) if d["kind"] == "wallet")
    n_assets = sum(1 for _, d in g.nodes(data=True) if d["kind"] == "asset")
    print(f"graph: {n_wallets} wallet nodes, {n_assets} asset nodes, {g.number_of_edges()} edges")
    print()

    print(f"shared-collateral links for primary demo wallet ({PRIMARY_DEMO_WALLET}):")
    shared = graph.wallets_sharing_collateral(g, PRIMARY_DEMO_WALLET)
    if not shared:
        print("  none found in this wallet set")
    for asset_address, other_wallets in shared.items():
        symbol = g.nodes[("asset", asset_address)]["symbol"]
        print(f"  {symbol} ({asset_address}): shared with {other_wallets}")
    print()

    known_asset_addresses = {r["asset_address"].lower() for r in records}
    wsteth = next(a for a in known_asset_addresses if g.nodes[("asset", a)]["symbol"] == "wstETH")
    pools = uniswap.eligible_pools_for_asset(wsteth, known_asset_addresses)
    print(f"Uniswap v3 depth for the shared wstETH link ({len(pools)} eligible pool(s)):")
    if pools:
        top = pools[0]
        ticks = uniswap.fetch_pool_ticks(top["pool_address"])
        print(f"  top: {top['pool_address']} (wstETH/{top['other_token_symbol']}, "
              f"${top['total_value_locked_usd']:,.0f} TVL, {len(ticks)} initialized ticks)")


if __name__ == "__main__":
    main()
