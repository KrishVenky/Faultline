import { useState } from "react";
import type { WalletExposureResult } from "../types";

// Section 14 (CLAUDE.md, 2026-09-08): input field plus result display,
// nothing more -- no dashboard, no wallet-connect. Lives inside the Live
// solver panel only; does not touch the frozen core cascade visualization.
export function WalletLookup(props: {
  onLookup: (address: string) => void;
  loading: boolean;
  error: string | null;
  data: WalletExposureResult | null;
}) {
  const [address, setAddress] = useState("");

  return (
    <div style={{ marginTop: 16, borderTop: "1px solid #3a3f5c", paddingTop: 14 }}>
      <div style={{ fontSize: 13, opacity: 0.75, marginBottom: 6 }}>
        Look up any wallet
      </div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          props.onLookup(address);
        }}
        style={{ display: "flex", gap: 6 }}
      >
        <input
          type="text"
          value={address}
          onChange={(e) => setAddress(e.target.value)}
          placeholder="0x..."
          spellCheck={false}
          style={{
            flex: 1,
            background: "#1a1d2e",
            border: "1px solid #3a3f5c",
            color: "#e6e9f5",
            padding: "7px 9px",
            borderRadius: 6,
            fontSize: 13,
            fontFamily: "monospace",
            minWidth: 0,
          }}
        />
        <button
          type="submit"
          disabled={props.loading}
          style={{
            background: "#4a6cf7",
            border: "1px solid #3a3f5c",
            color: "#e6e9f5",
            padding: "7px 14px",
            borderRadius: 6,
            cursor: props.loading ? "default" : "pointer",
            fontSize: 13,
            opacity: props.loading ? 0.6 : 1,
          }}
        >
          {props.loading ? "..." : "Go"}
        </button>
      </form>

      {props.error && (
        <div style={{ fontSize: 12, color: "#ff8080", marginTop: 8 }}>
          Lookup failed: {props.error}
        </div>
      )}

      {props.data && <WalletResult data={props.data} />}
    </div>
  );
}

function WalletResult({ data }: { data: WalletExposureResult }) {
  if (!data.found) {
    return (
      <div style={{ fontSize: 13, opacity: 0.8, marginTop: 10 }}>{data.message}</div>
    );
  }

  return (
    <div style={{ fontSize: 13, marginTop: 10 }}>
      {data.health_factor_computable ? (
        <div style={{ marginBottom: 8 }}>
          <span style={{ opacity: 0.75 }}>Health factor: </span>
          <strong style={{ color: data.health_factor < 1 ? "#ff5c5c" : "#e6e9f5" }}>
            {data.health_factor.toFixed(4)}
          </strong>
          <div style={{ opacity: 0.75, marginTop: 4, fontSize: 12 }}>
            Collateral ${data.collateral_value_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            {" / "}
            Debt ${data.debt_value_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          {data.shock_target ? (
            data.shock_target.pool_address ? (
              <div style={{ opacity: 0.65, marginTop: 4, fontSize: 12 }}>
                Shock target: {data.shock_target.asset_symbol} via{" "}
                {data.shock_target.asset_symbol}/{data.shock_target.pool_pair_other_token} pool ($
                {Math.round(data.shock_target.pool_tvl_usd ?? 0).toLocaleString()} TVL)
              </div>
            ) : (
              <div style={{ opacity: 0.65, marginTop: 4, fontSize: 12, fontStyle: "italic" }}>
                {data.shock_target.reason}
              </div>
            )
          ) : null}
        </div>
      ) : (
        <div
          style={{
            color: "#ffb3b3",
            background: "rgba(20, 8, 10, 0.6)",
            border: "1px solid rgba(255, 59, 59, 0.35)",
            borderRadius: 6,
            padding: "8px 10px",
            marginBottom: 8,
            fontSize: 12,
            lineHeight: 1.5,
          }}
        >
          {data.reason}
        </div>
      )}

      <div style={{ maxHeight: 160, overflowY: "auto" }}>
        {data.positions.map((p, i) => (
          <div
            key={i}
            style={{
              display: "flex",
              justifyContent: "space-between",
              fontSize: 12,
              opacity: 0.85,
              padding: "3px 0",
              borderTop: i > 0 ? "1px solid rgba(255,255,255,0.06)" : undefined,
            }}
          >
            <span>
              {p.side === "borrow" ? "Borrow" : p.usage_as_collateral ? "Collateral" : "Supply"}{" "}
              {p.asset_symbol}
            </span>
            <span style={{ fontFamily: "monospace" }}>
              {p.amount.toLocaleString(undefined, { maximumFractionDigits: 4 })}
              {p.price_usd == null && " (unpriced)"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
