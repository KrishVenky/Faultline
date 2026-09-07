import type { GraphNode } from "./types";

// Deterministic layout, not force-directed -- with this few nodes (2
// wallets, 4 assets in the frozen fixture) a fixed ring layout is more
// legible than a physics sim settling into an arbitrary shape, and it's
// the same shape every time the fixture is re-synced.

export type Position = [number, number, number];

export function layoutNodes(nodes: GraphNode[]): Map<string, Position> {
  const positions = new Map<string, Position>();
  const assets = nodes.filter((n) => n.kind === "asset");
  const wallets = nodes.filter((n) => n.kind === "wallet");

  const assetRadius = 3;
  assets.forEach((node, i) => {
    const angle = (i / assets.length) * Math.PI * 2;
    positions.set(node.id, [Math.cos(angle) * assetRadius, 0, Math.sin(angle) * assetRadius]);
  });

  const walletRadius = 7;
  wallets.forEach((node, i) => {
    const angle = (i / wallets.length) * Math.PI * 2 + Math.PI / wallets.length;
    positions.set(node.id, [
      Math.cos(angle) * walletRadius,
      2,
      Math.sin(angle) * walletRadius,
    ]);
  });

  return positions;
}
