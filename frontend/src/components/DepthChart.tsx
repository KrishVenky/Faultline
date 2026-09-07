import type { DepthProfile } from "../types";

// Section 9 step 3, priority item: makes the liquidity-cliff finding
// something a judge sees rather than takes on faith. Plain SVG, no
// charting library -- "doesn't need to be elaborate, the shape itself is
// the argument." Linear scale, deliberately: a log scale would soften the
// real cliff into a smooth decline and undersell how empty the tail
// actually is (BUILDLOG.md, "Reference cascade locked: two findings,
// layered" -- liquidity to <=5% of starting value in 4 ticks). Every bar
// height is a real value from pool.depth_profile.curve, nothing smoothed
// or sampled.
export function DepthChart({ profile }: { profile: DepthProfile }) {
  const curve = profile.curve;
  if (curve.length < 2) return null;

  const width = 380;
  const height = 64;
  const padding = { top: 4, right: 4, bottom: 16, left: 4 };
  const plotW = width - padding.left - padding.right;
  const plotH = height - padding.top - padding.bottom;

  const maxLiquidity = profile.starting_liquidity;
  const barW = plotW / curve.length;

  return (
    <svg width={width} height={height} style={{ display: "block" }}>
      {curve.map((point, i) => {
        const barH = Math.max(0.5, (point.liquidity / maxLiquidity) * plotH);
        const x = padding.left + i * barW;
        const y = padding.top + (plotH - barH);
        return (
          <rect
            key={point.ticks_crossed}
            x={x}
            y={y}
            width={Math.max(1, barW - 0.5)}
            height={barH}
            fill="#ff6b6b"
            opacity={0.85}
          />
        );
      })}
      <line
        x1={padding.left}
        y1={height - padding.bottom}
        x2={width - padding.right}
        y2={height - padding.bottom}
        stroke="#3a3f5c"
        strokeWidth={1}
      />
      <text x={padding.left} y={height - 4} fontSize={10} fill="#8892b0">
        current price
      </text>
      <text x={width - padding.right} y={height - 4} fontSize={10} fill="#8892b0" textAnchor="end">
        shocked price
      </text>
    </svg>
  );
}
