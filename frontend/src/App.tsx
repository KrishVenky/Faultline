import { Canvas } from "@react-three/fiber";
import { useEffect, useState } from "react";
import { DepthChart } from "./components/DepthChart";
import { Scene } from "./components/Scene";
import { WalletLookup } from "./components/WalletLookup";
import { buildTimeline, formatUsd } from "./timeline";
import { usePlayback } from "./usePlayback";
import { useLiveCascade } from "./useLiveCascade";
import { useWalletExposure } from "./useWalletExposure";
import type { DepthProfile, ReferenceCascade } from "./types";

export default function App() {
  const [fixtureData, setFixtureData] = useState<ReferenceCascade | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<"fixture" | "live">("fixture");
  const [shockPct, setShockPct] = useState(40);

  useEffect(() => {
    fetch("/data/reference_cascade.json")
      .then((res) => {
        if (!res.ok) throw new Error(`fixture fetch failed: ${res.status}`);
        return res.json();
      })
      .then(setFixtureData)
      .catch((e) => setError(String(e)));
  }, []);

  const live = useLiveCascade(shockPct, mode === "live");
  const walletExposure = useWalletExposure();

  if (error) {
    return (
      <Centered>
        Failed to load reference_cascade.json -- run{" "}
        <code>npm run sync-fixture</code> in frontend/, or{" "}
        <code>python -m scripts.generate_reference_fixture</code> from the repo
        root first. ({error})
      </Centered>
    );
  }
  if (!fixtureData) return <Centered>Loading reference cascade...</Centered>;

  const activeData = mode === "live" ? live.data : fixtureData;
  // Remount Cascade (and reset its playback) whenever the underlying
  // computation actually changes -- a new shock_pct is a new result, not
  // a continuation of the last play-through.
  const cascadeKey = mode === "live" ? `live-${shockPct}` : "fixture";

  return (
    <div style={{ position: "relative", width: "100vw", height: "100vh" }}>
      {activeData ? (
        <Cascade key={cascadeKey} data={activeData} />
      ) : (
        <Centered>{mode === "live" ? "Computing live cascade..." : "Loading..."}</Centered>
      )}

      <ShockControls
        mode={mode}
        onModeChange={setMode}
        shockPct={shockPct}
        onShockPctChange={setShockPct}
        liveLoading={live.loading}
        liveError={live.error}
        walletExposure={walletExposure}
      />
    </div>
  );
}

function ShockControls(props: {
  mode: "fixture" | "live";
  onModeChange: (m: "fixture" | "live") => void;
  shockPct: number;
  onShockPctChange: (v: number) => void;
  liveLoading: boolean;
  liveError: string | null;
  walletExposure: ReturnType<typeof useWalletExposure>;
}) {
  return (
    <div
      style={{
        position: "absolute",
        top: 24,
        right: 24,
        pointerEvents: "auto",
        background: "rgba(10, 11, 18, 0.85)",
        border: "1px solid #3a3f5c",
        borderRadius: 10,
        padding: "16px 20px",
        fontFamily: "system-ui, sans-serif",
        color: "#e6e9f5",
        minWidth: 260,
      }}
    >
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <ModeButton active={props.mode === "fixture"} onClick={() => props.onModeChange("fixture")}>
          Fixture (recorded)
        </ModeButton>
        <ModeButton active={props.mode === "live"} onClick={() => props.onModeChange("live")}>
          Live solver
        </ModeButton>
      </div>

      {props.mode === "live" && (
        <>
          <div style={{ fontSize: 13, opacity: 0.75, marginBottom: 6 }}>
            wstETH shock: <strong>{props.shockPct.toFixed(1)}%</strong>
            {props.liveLoading && <span style={{ opacity: 0.6 }}> -- computing...</span>}
          </div>
          <input
            type="range"
            min={0}
            max={90}
            step={0.5}
            value={props.shockPct}
            onChange={(e) => props.onShockPctChange(parseFloat(e.target.value))}
            style={{ width: "100%" }}
          />
          {props.liveError && (
            <div style={{ fontSize: 12, color: "#ff8080", marginTop: 8 }}>
              Live solver call failed: {props.liveError}. Is the API running
              (<code>uvicorn faultline.api:app --port 8000</code>)?
            </div>
          )}

          <WalletLookup
            onLookup={props.walletExposure.lookup}
            loading={props.walletExposure.loading}
            error={props.walletExposure.error}
            data={props.walletExposure.data}
          />
        </>
      )}
    </div>
  );
}

function ModeButton(props: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      onClick={props.onClick}
      style={{
        flex: 1,
        background: props.active ? "#4a6cf7" : "#1a1d2e",
        border: "1px solid #3a3f5c",
        color: "#e6e9f5",
        padding: "8px 10px",
        borderRadius: 6,
        cursor: "pointer",
        fontSize: 13,
      }}
    >
      {props.children}
    </button>
  );
}

function Cascade({ data }: { data: ReferenceCascade }) {
  const timeline = buildTimeline(data);
  const playback = usePlayback(timeline);

  return (
    <>
      <Canvas camera={{ position: [9, 6, 9], fov: 45 }}>
        <color attach="background" args={["#05060a"]} />
        <Scene
          data={data}
          activeWalletId={playback.activeWalletId}
          interpolatedPrice={playback.interpolatedPrice}
        />
      </Canvas>

      <Overlay
        priceUsd={playback.interpolatedPrice}
        symbol={data.shock.asset_symbol}
        label={playback.next?.label ?? ""}
        detail={playback.next?.detail ?? ""}
        depthNote={playback.next?.depthNote ?? null}
        depthProfile={data.pool.depth_profile}
        isMoneyShot={(playback.next?.isMoneyShot && playback.progress > 0.1) ?? false}
        isPlaying={playback.isPlaying}
        onPlay={playback.play}
        onPause={playback.pause}
        onReset={playback.reset}
      />
    </>
  );
}

function Overlay(props: {
  priceUsd: number;
  symbol: string;
  label: string;
  detail: string;
  depthNote: string | null;
  depthProfile?: DepthProfile;
  isMoneyShot: boolean;
  isPlaying: boolean;
  onPlay: () => void;
  onPause: () => void;
  onReset: () => void;
}) {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        pointerEvents: "none",
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: "32px",
        fontFamily: "system-ui, sans-serif",
        color: "#e6e9f5",
      }}
    >
      <div>
        <div style={{ fontSize: 14, letterSpacing: 2, opacity: 0.6, textTransform: "uppercase" }}>
          Faultline -- reference cascade
        </div>
        {/* The money shot (section 9 step 3): the number this whole
            cascade builds toward gets a dedicated reveal -- grows, glows,
            rather than ticking past like any other transition. The value
            itself is still the same real interpolation, nothing invented. */}
        <div
          className={props.isMoneyShot ? "money-shot-price" : undefined}
          style={{
            fontSize: props.isMoneyShot ? 64 : 48,
            fontWeight: 700,
            marginTop: 8,
            transition: "font-size 0.4s ease-out",
            color: props.isMoneyShot ? "#ff5c5c" : "#e6e9f5",
            textShadow: props.isMoneyShot ? "0 0 24px rgba(255, 92, 92, 0.6)" : "none",
          }}
        >
          {props.symbol} {formatUsd(props.priceUsd)}
        </div>
      </div>

      <div style={{ maxWidth: 560 }}>
        {/* Non-negotiable (CLAUDE.md section 9): a price collapse never
            appears without this explanation in the same beat. Chart
            first, priority over the reveal styling above per instruction. */}
        {props.depthNote && (
          <div
            style={{
              background: "rgba(20, 8, 10, 0.88)",
              border: "1px solid rgba(255, 59, 59, 0.4)",
              borderRadius: 8,
              padding: "12px 16px",
              marginBottom: 12,
              fontSize: 14,
              lineHeight: 1.5,
              color: "#ffb3b3",
            }}
          >
            {props.depthProfile && (
              <div style={{ marginBottom: 8 }}>
                <DepthChart profile={props.depthProfile} />
              </div>
            )}
            {props.depthNote}
          </div>
        )}
        <div style={{ fontSize: 18, fontWeight: 600, opacity: 0.9 }}>{props.label}</div>
        <div style={{ fontSize: 15, opacity: 0.75, marginTop: 4 }}>{props.detail}</div>
        <div style={{ marginTop: 16, pointerEvents: "auto", display: "flex", gap: 8 }}>
          <button onClick={props.isPlaying ? props.onPause : props.onPlay} style={buttonStyle}>
            {props.isPlaying ? "Pause" : "Play"}
          </button>
          <button onClick={props.onReset} style={buttonStyle}>
            Reset
          </button>
        </div>
      </div>
    </div>
  );
}

const buttonStyle: React.CSSProperties = {
  background: "#1a1d2e",
  border: "1px solid #3a3f5c",
  color: "#e6e9f5",
  padding: "8px 18px",
  borderRadius: 6,
  cursor: "pointer",
  fontSize: 14,
};

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        width: "100vw",
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "#05060a",
        color: "#e6e9f5",
        fontFamily: "system-ui, sans-serif",
        padding: 32,
        textAlign: "center",
      }}
    >
      {children}
    </div>
  );
}
