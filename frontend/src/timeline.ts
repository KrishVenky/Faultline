import type { DepthProfile, ReferenceCascade } from "./types";

// Every value here is read directly off the fixture. No pacing/duration
// choice invents a data value -- durations are presentation, prices and
// wallet IDs are not (per the instruction: "nothing invented for effect").

export interface Keyframe {
  id: string;
  label: string;
  detail: string;
  priceUsd: number;
  activeWalletId: string | null;
  isLiquidationEvent: boolean;
  depthNote: string | null;
  // The one number this whole cascade is building toward -- gets a
  // dedicated reveal treatment (section 9 step 3) rather than ticking
  // past it like any other keyframe transition.
  isMoneyShot: boolean;
}

// NON-NEGOTIABLE (CLAUDE.md section 9, added 2026-09-06): the price
// collapse must never appear without this explanation in the same beat.
// Built from the fixture's own pool.depth_profile, not an invented figure
// -- see BUILDLOG.md, "Reference cascade locked: two findings, layered".
function buildDepthNote(depthProfile: DepthProfile | undefined): string | null {
  if (!depthProfile) return null;
  const ticksTo5pct = depthProfile.ticks_to_depletion_pct["5"];
  if (ticksTo5pct === undefined) return null;
  return (
    `Pool liquidity here drops to 5% of its starting value after just ` +
    `${ticksTo5pct} tick${ticksTo5pct === 1 ? "" : "s"} crossed -- this sale finds ` +
    `almost nothing left to absorb it. Verified against Uniswap's own QuoterV2 contract.`
  );
}

export function buildTimeline(data: ReferenceCascade): Keyframe[] {
  const depthNote = buildDepthNote(data.pool.depth_profile);

  const keyframes: Keyframe[] = [
    {
      id: "before",
      label: "Before shock",
      detail: `${data.shock.asset_symbol} at ${formatUsd(data.shock.price_before_usd)}`,
      priceUsd: data.shock.price_before_usd,
      activeWalletId: null,
      isLiquidationEvent: false,
      depthNote: null,
      isMoneyShot: false,
    },
    {
      id: "shock",
      label: "Oracle shock",
      detail: `${data.shock.asset_symbol} drops ${data.shock.shock_pct.toFixed(2)}% to ${formatUsd(data.shock.price_after_oracle_shock_usd)}`,
      priceUsd: data.shock.price_after_oracle_shock_usd,
      activeWalletId: null,
      isLiquidationEvent: false,
      depthNote: null,
      isMoneyShot: false,
    },
  ];

  data.cascade.passes.forEach((pass, passIndex) => {
    pass.events.forEach((event, eventIndex) => {
      keyframes.push({
        id: `pass-${passIndex}-event-${eventIndex}`,
        label: `Pass ${passIndex + 1}: liquidation`,
        detail: `${shortAddr(event.wallet)} liquidated -- sold ${event.collateral_sold.toFixed(2)} ${data.shock.asset_symbol}, price -> ${formatUsd(event.price_after)}`,
        priceUsd: event.price_after,
        // solver events carry a bare address; graph node IDs are
        // "wallet:0x..." (faultline/graph.py's convention) -- prefix here
        // so the two actually match, caught live: without this, the
        // active-wallet highlight in Scene.tsx never fired.
        activeWalletId: `wallet:${event.wallet.toLowerCase()}`,
        isLiquidationEvent: true,
        // Both liquidations in this fixture hit the same repriced,
        // near-empty pool -- the explanation applies to both, not just
        // the final number.
        depthNote,
        isMoneyShot: false,
      });
    });
  });

  keyframes.push({
    id: "converged",
    label: "Converged",
    detail: `Final ${data.shock.asset_symbol} price ${formatUsd(data.cascade.final_price_usd)} -- ${data.cascade.liquidated_wallets.length} wallet(s) liquidated`,
    priceUsd: data.cascade.final_price_usd,
    activeWalletId: null,
    isLiquidationEvent: false,
    depthNote,
    isMoneyShot: true,
  });

  return keyframes;
}

export function shortAddr(addr: string): string {
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
}

// A plain toFixed(2) would show "$0.00" for a real $0.0028 -- rounding
// away the actual finding. Show more precision for sub-dollar values.
export function formatUsd(value: number): string {
  if (value === 0) return "$0.00";
  if (Math.abs(value) < 1) return `$${value.toFixed(4)}`;
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}
