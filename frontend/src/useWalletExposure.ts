import { useRef, useState } from "react";
import type { WalletExposureResult } from "./types";

const API_BASE = "http://localhost:8000";

// Section 14 (CLAUDE.md, 2026-09-08): arbitrary wallet lookup on the live
// solver. Triggered explicitly on submit, not debounced on keystroke --
// unlike the shock slider, there's no "drag" gesture to coalesce, and
// firing a request per keystroke against a real address input would be
// wasteful and confusing (stale results flashing mid-typing).
export function useWalletExposure() {
  const [data, setData] = useState<WalletExposureResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestIdRef = useRef(0);

  function lookup(address: string) {
    const trimmed = address.trim();
    if (!trimmed) return;

    const requestId = ++requestIdRef.current;
    setLoading(true);
    setError(null);
    setData(null);

    fetch(`${API_BASE}/wallet/${trimmed}/exposure`)
      .then((res) => {
        if (!res.ok) throw new Error(`wallet lookup failed: ${res.status}`);
        return res.json();
      })
      .then((json) => {
        if (requestId !== requestIdRef.current) return; // superseded by a newer lookup
        setData(json);
        setLoading(false);
      })
      .catch((e) => {
        if (requestId !== requestIdRef.current) return;
        setError(String(e));
        setLoading(false);
      });
  }

  return { data, loading, error, lookup };
}
