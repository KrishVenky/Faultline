import { useCallback, useEffect, useRef, useState } from "react";
import type { Keyframe } from "./timeline";

// Playback engine: steps through real keyframes with a fixed on-screen
// duration per step (presentation choice) and linearly interpolates price
// between each keyframe's real value and the next (also presentation --
// the two endpoints of every interpolation are real fixture numbers, only
// the tween is invented, for the "rupture" to read as a price move rather
// than a jump-cut).

const MS_PER_STEP = 2600;

export function usePlayback(keyframes: Keyframe[]) {
  const [stepIndex, setStepIndex] = useState(0);
  const [progress, setProgress] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const rafRef = useRef<number>();
  const stepStartRef = useRef<number>(0);

  const play = useCallback(() => setIsPlaying(true), []);
  const pause = useCallback(() => setIsPlaying(false), []);
  const reset = useCallback(() => {
    setStepIndex(0);
    setProgress(0);
    setIsPlaying(false);
  }, []);

  useEffect(() => {
    if (!isPlaying) return;
    stepStartRef.current = performance.now();

    const tick = (now: number) => {
      const elapsed = now - stepStartRef.current;
      const p = Math.min(1, elapsed / MS_PER_STEP);
      setProgress(p);

      if (p >= 1) {
        setStepIndex((i) => {
          const next = i + 1;
          if (next >= keyframes.length - 1) {
            setIsPlaying(false);
            return keyframes.length - 2 >= 0 ? keyframes.length - 2 : 0;
          }
          stepStartRef.current = now;
          return next;
        });
      } else {
        rafRef.current = requestAnimationFrame(tick);
      }
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isPlaying, stepIndex, keyframes.length]);

  const from = keyframes[stepIndex];
  const to = keyframes[Math.min(stepIndex + 1, keyframes.length - 1)];
  const interpolatedPrice = from && to ? from.priceUsd + (to.priceUsd - from.priceUsd) * progress : 0;

  return {
    stepIndex,
    progress,
    isPlaying,
    play,
    pause,
    reset,
    current: from,
    next: to,
    interpolatedPrice,
    activeWalletId: progress > 0.15 && progress < 0.95 ? to?.activeWalletId ?? null : null,
    isAtEnd: stepIndex >= keyframes.length - 2 && progress >= 1,
  };
}
