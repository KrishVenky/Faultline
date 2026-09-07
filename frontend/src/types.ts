// Mirrors faultline/fixtures/reference_cascade.json exactly -- see
// scripts/generate_reference_fixture.py for the producing side. Kept flat,
// matching the backend's own wire-format decision.
//
// NOTE: amount_wei values in the fixture are raw Python ints (up to ~1e21
// for an 18-decimal token) serialized as bare JSON numbers, not strings.
// JS numbers only carry full precision up to 2^53 (~9e15), so these lose
// precision past roughly the 15th significant digit once parsed. Immaterial
// here -- every use of amount_wei in this app divides by 10**decimals for
// display, and the resulting error is far below one screen-pixel's worth of
// a number ticker. Flagging it rather than pretending the precision is
// exact.

export interface Shock {
  asset_symbol: string;
  asset_address: string;
  price_before_usd: number;
  price_after_oracle_shock_usd: number;
  shock_pct: number;
}

export interface DepthCurvePoint {
  ticks_crossed: number;
  tick_idx: number | null;
  liquidity: number;
}

export interface DepthProfile {
  starting_liquidity: number;
  // key is a percentage threshold as a string (e.g. "50", "5", "0.1"),
  // value is how many ticks were crossed before liquidity first fell to
  // or below that fraction of its starting value. Real, computed from
  // the same tick data the reposition step walks (BUILDLOG.md,
  // 2026-09-06, "Reference cascade locked: two findings, layered").
  ticks_to_depletion_pct: Record<string, number>;
  // Real per-tick liquidity trace for the depth-chart inset (section 9
  // step 3) -- not a sampled/smoothed approximation, the actual values
  // the reposition walk computed crossing each real tick.
  curve: DepthCurvePoint[];
}

export interface PoolInfo {
  address: string;
  pair: string;
  fee_tier_bps: number;
  depth_profile?: DepthProfile;
  liquidity_at_shocked_price?: number;
}

export interface GraphNode {
  id: string;
  kind: "wallet" | "asset";
  address: string;
  symbol?: string;
}

export interface GraphEdge {
  source: string;
  target: string;
  protocol: string;
  side: "supply" | "borrow";
  amount_wei: number;
  asset_decimals: number;
  usage_as_collateral: boolean;
  market?: string | null;
  liquidation_threshold_bps?: number | null;
  liquidation_bonus_bps?: number | null;
  liquidation_factor?: string | null;
  liquidate_collateral_factor?: string | null;
}

export interface LiquidationEvent {
  wallet: string;
  health_factor_at_trigger: number;
  close_factor: number;
  collateral_sold: number;
  price_before: number;
  price_after: number;
  depth_exhausted: boolean;
}

export interface CascadePass {
  price_at_start_of_pass: number;
  events: LiquidationEvent[];
}

export interface ReferenceCascade {
  description: string;
  shock: Shock;
  pool: PoolInfo;
  graph_before: { nodes: GraphNode[]; edges: GraphEdge[] };
  cascade: {
    converged: boolean;
    pass_count: number;
    final_price_usd: number;
    liquidated_wallets: string[];
    passes: CascadePass[];
  };
}

// Mirrors faultline/wallet_lookup.py's return shape exactly (section 14,
// CLAUDE.md, 2026-09-08). Every field is either real data from the live
// pipeline or an honest, named reason it's missing -- never a fabricated
// number filling a gap.

export interface WalletExposurePosition {
  protocol: string;
  asset_symbol: string;
  asset_address: string;
  side: "supply" | "borrow";
  amount: number;
  usage_as_collateral: boolean;
  price_usd: number | null;
}

export interface WalletShockTarget {
  asset_symbol: string;
  asset_address: string;
  pool_address: string | null;
  pool_pair_other_token?: string;
  pool_tvl_usd?: number;
  reason?: string;
}

export interface WalletNotFound {
  address: string;
  found: false;
  message: string;
}

export interface WalletExposureIncomplete {
  address: string;
  found: true;
  health_factor_computable: false;
  reason: string;
  positions: WalletExposurePosition[];
}

export interface WalletExposureComplete {
  address: string;
  found: true;
  health_factor_computable: true;
  health_factor: number;
  collateral_value_usd: number;
  debt_value_usd: number;
  positions: WalletExposurePosition[];
  shock_target: WalletShockTarget | null;
}

export type WalletExposureResult =
  | WalletNotFound
  | WalletExposureIncomplete
  | WalletExposureComplete;
