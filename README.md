# Faultline

Cross-protocol liquidation contagion solver, built for ETHOnline 2026.

Every lending protocol reports solvency in isolation. Systemic risk lives
in the collateral assets shared between them: a wallet leveraged against
an asset on one protocol and a different, unrelated wallet leveraged
against the same asset on another protocol are exposed to each other
through the market, with no direct link between them. A forced liquidation
sale on the first protocol moves that asset's price against real pool
depth, and the price move can liquidate the second wallet, which has no
position on the first protocol at all.

Faultline builds the exposure graph from indexed chain data (Aave v3,
Compound v3 via The Graph), applies a price shock, recomputes health
factors, liquidates breaches, prices the resulting forced sale against
real Uniswap v3 tick liquidity, and iterates to a fixed point. It is a
deterministic solver, not a model: no ML, no prediction, every liquidation
mechanic is a published protocol parameter.

This repo is one commit. The incremental record lives in BUILDLOG.md
instead, timestamped across the actual build (Sept 5-6), including every
wrong number, every bug, and how each was caught. We chose an honest
single commit over a reconstructed history that would carry today's date
on commits describing work done days earlier.

**[Read BUILDLOG.md](BUILDLOG.md).**

The project spec and working rules are in [`CLAUDE.md`](CLAUDE.md). This
file is the quick-start and architecture overview; those two are the
source of truth for everything else.

## The headline result

A real wallet on Aave v3 gets liquidated by a 43.67% oracle-level shock to
wstETH. Its seized collateral is sold through the real wstETH/WETH Uniswap
v3 pool. That forced sale collapses the pool's price -- because this pool's
liquidity is concentrated in a narrow band and has almost nothing beyond
it (independently verified against Uniswap's own deployed QuoterV2
contract) -- and the resulting price move liquidates a second wallet with
no shared protocol and no shared debt asset. Two real findings, layered:
the shared-collateral contagion mechanism, and a concentrated-liquidity
fragility finding that surfaced while getting the first one exactly right.
Both wallets' positions are externally reconciled against DeBank. See
BUILDLOG.md, "Reference cascade locked: two findings, layered" for the
full numbers and verification trail.

## Architecture

```
faultline/              Python backend (the solver, the graph, the data layer)
  config.py             Subgraph IDs, RAY/BASE_INDEX_SCALE constants -- every ID
                         verified live against the protocol's own docs, never a
                         search result (see CLAUDE.md section 10)
  graphql_client.py      Generic Graph gateway query client
  aave.py                 Aave v3 position fetch: index-adjusted balances (never
                         the subgraph's stale current* snapshot fields), eMode-
                         aware liquidation thresholds
  compound.py             Compound v3 position fetch: present-value formula
                         sourced from Comet's own contracts (CometCore.sol)
  oracle.py               Live AaveOracle.getAssetPrice reads -- not the
                         subgraph's oracle mirror, which is stale by months
  uniswap.py               Pool/tick fetch, the tick-walk swap simulation
                         (verified against Uniswap's real QuoterV2 contract),
                         and the liquidity depth-profile computation
  liquidation.py          Aave's close factor and collateral-seizure formula,
                         sourced from LiquidationLogic.sol
  health_factor.py        The one function everything computes HF through
  graph.py                Wallet<->asset exposure graph (never wallet<->wallet)
  solver.py               The fixed-point cascade loop
  live_cascade.py          Live version of the reference cascade: same wallets,
                         same pool, fresh prices/positions every call
  api.py                  FastAPI boundary, flat JSON, no nested models
  fixtures/reference_cascade.json   The frozen, reconciled reference case

frontend/                React + TypeScript + react-three-fiber
  src/App.tsx             Fixture/Live mode toggle, the shock% slider, the
                         price ticker and liquidity-explanation overlay
  src/components/Scene.tsx     3D wallet/asset graph, entrance transitions
  src/components/DepthChart.tsx  Real liquidity-cliff chart from pool.depth_profile
  src/timeline.ts          Turns a cascade result into keyframes -- every
                         price and wallet ID comes from the data, never invented
  src/usePlayback.ts        Playback engine (real data, invented tween timing)
  src/useLiveCascade.ts      Debounced live-solver API calls for the slider

scripts/                  Reproducible one-off runs (rule 3: same inputs,
                         same outputs). generate_reference_fixture.py is the
                         one that produces fixtures/reference_cascade.json;
                         the rest are the verification trail (reconciliation,
                         regression tests, the wider-cohort search) -- see
                         BUILDLOG.md for what each one found.

research/                 Raw intermediate data pulled during the Phase 2
                         wallet search (not code, kept for reproducibility)
```

## Setup

Requires Python 3.11+, Node 18+, and a free
[Graph Studio API key](https://thegraph.com/studio/).

```bash
# backend
pip install -e .
cp .env.example .env   # then fill in GRAPH_API_KEY

# frontend
cd frontend
npm install
```

## Running it

**Backend API** (serves the frozen fixture and the live solver endpoint):

```bash
python -m uvicorn faultline.api:app --port 8000
```

**Frontend**, in a second terminal:

```bash
cd frontend
npm run sync-fixture   # copies faultline/fixtures/reference_cascade.json into place
npm run dev
```

Open `http://localhost:5173`. The **Fixture (recorded)** toggle plays back
the frozen, externally-reconciled reference cascade. The **Live solver**
toggle calls the real backend (`GET /cascade/live?shock_pct=...`) on every
slider drag -- a genuinely fresh computation each time: live AaveOracle
prices, live wallet balances, live pool/tick state, walked through the
same solver.

**Regenerating the reference fixture** (after any solver/data change):

```bash
python -m scripts.generate_reference_fixture
```

**Reproducing the Phase 1 reconciliation gate** (one real wallet's
cross-protocol position set, hand-checkable against the protocol UIs):

```bash
python -m scripts.reconcile_wallet 0x86aef245207e2f93fba083d51852c91a7e711eb6
```

**Regression test** (confirms the solver reproduces both hand-verified
reference numbers through the real code path, not just a one-off script):

```bash
python -m scripts.regression_test_cascade
```

## Data sources

- **The Graph**: Aave v3 (`Cd2gEDVeqnjBn1hSeqFMitw8Q1iiyV9FYUZkLNRcL87g`),
  Compound v3 (`5nwMCSHaTqG3Kd2gHznbTXEnZ9QNWsssQfbHhDqQSQFp`), Uniswap v3
  (`5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV`) -- all IDs pulled from
  the protocols' own docs/READMEs and verified live before use (see
  BUILDLOG.md's live-verification entries; three IDs sourced from search
  results turned out wrong before these were confirmed correct).
- **Uniswap v3**: tick-level pool depth is load-bearing for the price-impact
  half of the solver, not decorative -- see [`FEEDBACK.md`](FEEDBACK.md)
  for the integration writeup.
- **Live contract reads**: `AaveOracle.getAssetPrice` and Uniswap's
  `QuoterV2.quoteExactInputSingle`, both called directly via `eth_call`
  against a public RPC, no subgraph in between for these two.

## What this doesn't cover

Two protocols (Aave v3, Compound v3), one collateral asset in the reference
case (wstETH), one pool per asset. Stated scope limits, and two related
findings kept honest rather than smoothed over, are in BUILDLOG.md: a
wider 26-wallet check found roughly a fifth of a real cohort already
fails on the oracle shock alone (no pool mechanism needed), and letting
the cascade run past the reconciled reference pair produces an
uneconomical result once wallets larger than a single pool's real depth
get involved. Both are real, both are documented, neither is built into
the primary visualization -- narration and writeup material only.
