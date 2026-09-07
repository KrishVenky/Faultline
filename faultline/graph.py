import networkx as nx

# Design constraint (from the user, 2026-09-05, tied to CLAUDE.md's artifact
# declaration): the contagion channel is a wallet leaning on a shared
# collateral asset, not a link between wallets, and not "same wallet, two
# protocols" (that's real and useful but a different thing -- see the
# 0x86aef2...1eb6 BUILDLOG entry, which is an example of the latter, not
# the former). This graph never has a wallet-to-wallet edge. Every edge is
# wallet <-> asset. Two different wallets that both lean on the same asset
# are linked only by fact of sharing that one asset node as a neighbor --
# there is no shorter path between them than wallet -> asset -> wallet, and
# that's deliberate, not a missing feature.


def build_graph(records: list[dict]) -> nx.MultiGraph:
    """One graph across both protocols. Nodes are ('wallet', address) or
    ('asset', address) tuples -- asset nodes are keyed by contract address
    so the same underlying token supplied/borrowed on Aave and Compound
    both land on the same node (see the pool-selection-rule reasoning in
    BUILDLOG.md: address, never symbol). Edges carry everything Phase 2's
    solver needs: protocol, side, live amount, collateral flag, and
    whichever liquidation parameters that record has."""
    g = nx.MultiGraph()
    for r in records:
        wallet_node = ("wallet", r["wallet"].lower())
        asset_node = ("asset", r["asset_address"].lower())

        g.add_node(wallet_node, kind="wallet", address=r["wallet"].lower())
        g.add_node(
            asset_node,
            kind="asset",
            address=r["asset_address"].lower(),
            symbol=r["asset_symbol"],
        )

        g.add_edge(
            wallet_node,
            asset_node,
            protocol=r["protocol"],
            side=r["side"],
            amount_wei=r["amount_wei"],
            asset_decimals=r["asset_decimals"],
            usage_as_collateral=r["usage_as_collateral"],
            market=r.get("market"),
            liquidation_threshold_bps=r.get("liquidation_threshold_bps"),
            liquidation_bonus_bps=r.get("liquidation_bonus_bps"),
            liquidation_factor=r.get("liquidation_factor"),
            liquidate_collateral_factor=r.get("liquidate_collateral_factor"),
        )
    return g


def wallets_sharing_collateral(g: nx.MultiGraph, wallet: str) -> dict[str, list[str]]:
    """For each asset this wallet posts as collateral, every OTHER wallet
    also exposed to that same asset (as collateral or debt, on either
    protocol) -- the exact walk Phase 2's shock propagation needs: this
    wallet gets liquidated, its collateral asset's price moves, who else on
    the graph is touching that asset node. Never touches another wallet
    node directly; always goes through the shared asset node."""
    wallet_node = ("wallet", wallet.lower())
    result: dict[str, list[str]] = {}

    for _, asset_node, data in g.edges(wallet_node, data=True):
        if not data.get("usage_as_collateral"):
            continue
        asset_address = asset_node[1]
        neighbors = [
            n[1]
            for n in g.neighbors(asset_node)
            if n[0] == "wallet" and n[1] != wallet.lower()
        ]
        if neighbors:
            result.setdefault(asset_address, [])
            for n in neighbors:
                if n not in result[asset_address]:
                    result[asset_address].append(n)

    return result
