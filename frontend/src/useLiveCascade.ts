import { useEffect, useRef, useState } from "react";
import type { ReferenceCascade } from "./types";

const API_BASE = "http://localhost:8000";
const DEBOUNCE_MS = 400;

// Section 9 step 2: calls the real solver endpoint, not a fixture replay
// -- a judge dragging the slider is looking at a live computation
// (BUILDLOG.md, "Reference cascade locked"). Debounced so dragging the
// slider doesn't fire a request per pixel.
export function useLiveCascade(shockPct: number, enabled: boolean) {
  const [data, setData] = useState<ReferenceCascade | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const requestIdRef = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    if (timeoutRef.current) clearTimeout(timeoutRef.current);

    timeoutRef.current = setTimeout(() => {
      const requestId = ++requestIdRef.current;
      setLoading(true);
      setError(null);
      fetch(`${API_BASE}/cascade/live?shock_pct=${shockPct}`)
        .then((res) => {
          if (!res.ok) throw new Error(`live solver call failed: ${res.status}`);
          return res.json();
        })
        .then((json) => {
          if (requestId !== requestIdRef.current) return; // stale response, a newer drag superseded it
          setData(json);
          setLoading(false);
        })
        .catch((e) => {
          if (requestId !== requestIdRef.current) return;
          setError(String(e));
          setLoading(false);
        });
    }, DEBOUNCE_MS);

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [shockPct, enabled]);

  return { data, loading, error };
}
