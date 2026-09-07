import { OrbitControls, Line, Text } from "@react-three/drei";
import { useMemo, useRef } from "react";
import * as THREE from "three";
import { useFrame } from "@react-three/fiber";
import type { ReferenceCascade } from "../types";
import { layoutNodes } from "../layout";
import { shortAddr } from "../timeline";

interface SceneProps {
  data: ReferenceCascade;
  activeWalletId: string | null;
  interpolatedPrice: number;
}

function severityColor(priceUsd: number, before: number, floor: number): THREE.Color {
  // Real data drives this: 0 = pre-shock price, 1 = the lowest price this
  // specific run ever reaches. Not a fixed palette applied regardless of
  // the numbers.
  const t = THREE.MathUtils.clamp((before - priceUsd) / (before - floor), 0, 1);
  return new THREE.Color().setHSL(THREE.MathUtils.lerp(0.55, 0.0, t), 0.75, 0.55);
}

// Entrance transitions (section 9 step 3, last item): nodes ease in from
// nothing rather than popping into existence on mount/remount -- fires
// every time Scene remounts (a fresh fixture load, or a new live-solver
// result), which is exactly when a "new scene" reveal reads right.
function useEntranceScale(delaySeconds: number) {
  const scaleRef = useRef(0);
  const startRef = useRef<number | null>(null);
  useFrame((state) => {
    if (startRef.current === null) startRef.current = state.clock.elapsedTime;
    const elapsed = state.clock.elapsedTime - startRef.current - delaySeconds;
    const duration = 0.5;
    const t = THREE.MathUtils.clamp(elapsed / duration, 0, 1);
    scaleRef.current = 1 - Math.pow(1 - t, 3); // ease-out cubic
  });
  return scaleRef;
}

function WalletNode({
  id,
  position,
  active,
  entranceDelay,
}: {
  id: string;
  position: [number, number, number];
  active: boolean;
  entranceDelay: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const entranceRef = useEntranceScale(entranceDelay);
  useFrame((state) => {
    if (!meshRef.current) return;
    const pulse = active ? 1 + Math.sin(state.clock.elapsedTime * 8) * 0.15 : 1;
    meshRef.current.scale.setScalar(pulse * entranceRef.current);
  });
  const address = id.split(":")[1] ?? id;
  return (
    <group position={position}>
      <mesh ref={meshRef}>
        <sphereGeometry args={[0.6, 32, 32]} />
        <meshStandardMaterial
          color={active ? "#ff3b3b" : "#4a6cf7"}
          emissive={active ? "#ff3b3b" : "#000000"}
          emissiveIntensity={active ? 1.2 : 0}
        />
      </mesh>
      <Text position={[0, 1, 0]} fontSize={0.35} color="#dfe6ff" anchorX="center">
        {shortAddr(address)}
      </Text>
    </group>
  );
}

function AssetNode({
  id,
  symbol,
  position,
  color,
  isShocked,
  entranceDelay,
}: {
  id: string;
  symbol: string;
  position: [number, number, number];
  color: THREE.Color;
  isShocked: boolean;
  entranceDelay: number;
}) {
  const meshRef = useRef<THREE.Mesh>(null);
  const entranceRef = useEntranceScale(entranceDelay);
  useFrame(() => {
    if (!meshRef.current) return;
    meshRef.current.scale.setScalar(entranceRef.current);
  });
  return (
    <group position={position}>
      <mesh ref={meshRef}>
        <sphereGeometry args={[isShocked ? 0.9 : 0.5, 32, 32]} />
        <meshStandardMaterial color={color} emissive={color} emissiveIntensity={isShocked ? 0.6 : 0.1} />
      </mesh>
      <Text position={[0, isShocked ? 1.4 : 0.9, 0]} fontSize={0.4} color="#ffffff" anchorX="center">
        {symbol}
      </Text>
    </group>
  );
}

export function Scene({ data, activeWalletId, interpolatedPrice }: SceneProps) {
  const positions = useMemo(() => layoutNodes(data.graph_before.nodes), [data]);
  const lowestPrice = Math.min(
    data.cascade.final_price_usd,
    ...data.cascade.passes.flatMap((p) => p.events.map((e) => e.price_after)),
  );
  const shockedColor = severityColor(interpolatedPrice, data.shock.price_before_usd, lowestPrice);

  return (
    <>
      <ambientLight intensity={0.4} />
      <pointLight position={[10, 10, 10]} intensity={1.2} />
      <pointLight position={[-10, 5, -10]} intensity={0.5} color="#5566ff" />
      <OrbitControls enablePan={false} minDistance={5} maxDistance={25} />

      {data.graph_before.edges.map((edge, i) => {
        const from = positions.get(edge.source);
        const to = positions.get(edge.target);
        if (!from || !to) return null;
        const walletId = edge.source.startsWith("wallet:") ? edge.source : edge.target;
        const isActive = walletId === activeWalletId;
        return (
          <Line
            key={i}
            points={[from, to]}
            color={isActive ? "#ff3b3b" : edge.usage_as_collateral ? "#4a6cf7" : "#555b70"}
            lineWidth={isActive ? 3 : 1}
            transparent
            opacity={isActive ? 1 : 0.5}
          />
        );
      })}

      {data.graph_before.nodes.map((node, i) => {
        const pos = positions.get(node.id);
        if (!pos) return null;
        // Staggered, not simultaneous -- reads as a scene assembling
        // itself rather than everything blinking on at once.
        const entranceDelay = i * 0.06;
        if (node.kind === "wallet") {
          return (
            <WalletNode
              key={node.id}
              id={node.id}
              position={pos}
              active={node.id === activeWalletId}
              entranceDelay={entranceDelay}
            />
          );
        }
        const isShocked = node.address.toLowerCase() === data.shock.asset_address.toLowerCase();
        return (
          <AssetNode
            key={node.id}
            id={node.id}
            symbol={node.symbol ?? "?"}
            position={pos}
            color={isShocked ? shockedColor : new THREE.Color("#8892b0")}
            isShocked={isShocked}
            entranceDelay={entranceDelay}
          />
        );
      })}
    </>
  );
}
