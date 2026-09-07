import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from faultline import aave, compound
from faultline.graph import build_graph
from faultline.live_cascade import compute_live_cascade

app = FastAPI(title="Faultline")

# Local dev only: the frontend (vite, localhost:5173) calls this API
# (uvicorn, a different port) directly for the live slider. Not a
# public-facing deployment concern for a hackathon demo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

REFERENCE_CASCADE_PATH = Path(__file__).parent / "fixtures" / "reference_cascade.json"

# Wire format: every endpoint returns plain dicts/lists straight from the
# fetch and graph modules, no Pydantic response models. Decided 2026-09-05:
# flat JSON records at this boundary, nothing to debug through a nested
# class layer later.


@app.get("/wallets/{address}/positions")
def wallet_positions(address: str) -> list[dict]:
    return aave.fetch_wallet_positions(address) + compound.fetch_wallet_positions(address)


def _node_id(node: tuple[str, str]) -> str:
    kind, addr = node
    return f"{kind}:{addr}"


@app.get("/graph")
def exposure_graph(wallets: str) -> dict:
    """wallets: comma-separated addresses."""
    addresses = [w.strip().lower() for w in wallets.split(",") if w.strip()]

    records = []
    for w in addresses:
        records += aave.fetch_wallet_positions(w)
        records += compound.fetch_wallet_positions(w)

    g = build_graph(records)

    nodes = [
        {"id": _node_id(n), **data}
        for n, data in g.nodes(data=True)
    ]
    edges = [
        {"source": _node_id(u), "target": _node_id(v), **data}
        for u, v, data in g.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}


@app.get("/reference-cascade")
def reference_cascade() -> dict:
    """The frozen, externally reconciled, solver-verified reference case
    (BUILDLOG.md, 2026-09-06, "Reference cascade locked: two findings,
    layered"): primary wallet -> 0xcc997fe9..., 2 passes, converges at
    $0.0028 (a genuine, QuoterV2-verified near-total wipeout, not a typo --
    see the depth_profile finding in the same fixture). Precomputed by
    scripts/generate_reference_fixture.py, served as-is -- not regenerated
    per-request, so the demo never depends on a live query landing
    correctly under time pressure. This is the guaranteed-clean fallback
    for the recorded video specifically (section 9 step 2); the
    interactive slider a judge can touch calls /cascade/live instead."""
    return json.loads(REFERENCE_CASCADE_PATH.read_text())


@app.get("/cascade/live")
def cascade_live(shock_pct: float) -> dict:
    """Section 9 step 2: the real solver, called fresh, not a fixture
    replay. `shock_pct` (0-100) is the percent drop applied to wstETH's
    live AaveOracle price; the wallet pair and pool are fixed, matching
    the frozen reference case. A shock too small to liquidate the trigger
    wallet correctly returns an empty cascade (0 passes) -- that's a real
    result of live, current prices and balances, not an error. Clamped to
    [0, 90] -- degenerate at the edges (0 = no shock, 100 = the shocked
    price is exactly zero, breaks the swap math) aren't useful stress
    scenarios for a judge to land on."""
    shock_pct = max(0.0, min(90.0, shock_pct))
    return compute_live_cascade(shock_pct)
