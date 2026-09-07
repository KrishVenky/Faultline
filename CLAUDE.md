# Faultline

Cross-protocol liquidation contagion solver. ETHOnline 2026 (ETHGlobal,
online, async-judged). Read this entire file before writing anything.

Sections are numbered below specifically so they can be referenced
unambiguously later (`section 3`, `section 9`, etc.). If an instruction
references a section, decision, or rule that isn't actually here or in
BUILDLOG.md, the answer is to ask for it to be added, not to proceed on
trust and log the gap. See section 10.

## 1. Artifact declaration

The exposure graph and the deterministic cascade solver are the product.
The visualization is a view over them.

Every lending protocol reports solvency in isolation. Systemic risk lives in
the collateral assets shared between them. A wallet leveraged against an
asset on one protocol and a different, unrelated wallet leveraged against
the same asset on another protocol are exposed to each other through the
market, with no direct link between them. A forced liquidation sale on the
first protocol moves that asset's price against real pool depth, and the
price move can liquidate the second wallet, which has no position on the
first protocol at all. Nothing in the onchain stack answers "if this
protocol cracks, who else falls?"

Faultline builds that graph from indexed chain data, applies a shock,
recomputes health factors across all protocols, liquidates breaches, applies
the price impact of forced sales against real pool depth, and iterates to a
fixed point. Output: propagation path, which protocols absorb collateral
shortfalls, total systemic loss.

## 2. Architectural rules (non-negotiable)

1. DETERMINISTIC SOLVER. No graph neural network, no learned model, no LLM in
   the solve path. Liquidation mechanics are published parameters and the
   cascade is a solvable system. We solve it, we do not predict it. If you
   find yourself reaching for a model, the answer is a better solver. We will
   defend this choice explicitly in the writeup.
2. NOTHING MOCKED. Every number in the demo comes from live chain state at a
   stated block. The Graph's tooling track disqualifies mocked or static
   datasets. If real data is unavailable, we cut the feature. We never fake it.
3. REPRODUCIBLE. Same inputs, same outputs, always. Log block number and the
   full input parameter set with every run.
4. ASSUMPTIONS STATED OUT LOUD, IMMEDIATELY. Every simplification goes into
   BUILDLOG.md the moment it is made, with the reason. One honest stated
   limitation is worth more than three paragraphs of feature description.

## 3. Stack

- Data: EXISTING Aave v3 and Compound subgraphs via The Graph, plus Uniswap
  v3 pool state for tick-level depth. DO NOT AUTHOR NEW SUBGRAPHS. It will
  consume the entire window. Official Uniswap v3 subgraph only (ID
  `5zvR82QoaXYFyDEKLZ9t6v9adgnptxYpKpSbxtgVENFV`, corrected 2026-09-05 after
  live verification found the previous ID dead — see BUILDLOG.md) — Uniswap
  confirmed on the
  2026-09-05 kickoff call that their Substreams tooling is community-
  maintained, not Labs-owned, same caution as the Compound subgraph. Check
  `_meta.block.number` before trusting any path other than the official one.
- Solver: Python. Decided 2026-09-05 — single runtime with the eventual
  FastAPI boundary (see below), no serialization boundary between a Python
  backend and a JS frontend to debug under deadline pressure.
- Onchain write: none required. Chainlink dropped as a sponsor track,
  confirmed 2026-09-05 — no remaining prize requires an onchain state
  change. Phase 3 is dropped accordingly, see section 6.
- API boundary: FastAPI, decided 2026-09-05. Flat JSON wire records only —
  no nested class serialization at this boundary, nothing to debug through
  a class layer later.
- Visualization: react-three-fiber + React Bits, decided 2026-09-05. View
  layer. Do not gold-plate it. Was parked until the Phase 2 hand-walked
  cascade passed (it has — see BUILDLOG.md, "Reference cascade reconciled
  and frozen"); build order and scope are in section 9.

## 4. Sponsor slots (2 locked, no forced third)

Do not add a partner integration that isn't already load-bearing to the
solver or graph. If a genuine third fit emerges during the build, it must be
something the project would want even without a prize attached.

- LOCKED: The Graph, track "Best Use of Composable or Standardized Graph
  Products" ($5k pool). NOT the AI Tooling track. Justification: the exposure
  graph composes Aave v3 and Compound v3 subgraphs (and Uniswap v3 for depth)
  into one query pattern spanning multiple protocols, which is exactly what
  this track scores. Requires live data from a Graph provider, mocked data
  disqualifies, already covered by rule 2 in section 2.

- LOCKED: Uniswap Foundation, track "Best Uniswap Stack Contribution" ($3k
  pool). Justification: v3 tick-level depth is load-bearing for the price
  impact function in the solver (Phase 2), not added for the prize. Requires
  a public repo, a FEEDBACK.md file, and a completed submission to Uniswap's
  developer feedback form (https://developers.uniswap.org/hackathon-feedback)
  linking that file. Do this at Phase 4, not Phase 8, it's a five-minute task
  easy to forget under deadline pressure. Angela Cando (Uniswap Labs DevRel)
  said directly on the 2026-09-05 kickoff call that her team personally
  audits submissions for real protocol integration versus a token import
  that's never actually called — make FEEDBACK.md specific and accurate,
  not boilerplate.

  Same call: no frontend is required for this prize specifically — her
  words, "if you have an amazing idea you want to run on the terminal, just
  explain that well." This relaxes only the Uniswap prize's own criteria. It
  does not relax ETHGlobal's general demo/usability expectations — the
  visualization (force-directed graph, shock, cascade) is still the plan for
  the general demo. If visual work runs short, the Uniswap prize path
  specifically isn't blocked by that; it is not license to skip the
  visualization generally.

- DROPPED: Chainlink. The previous plan assumed a generic "publish a value
  onchain" track. That track no longer exists. The current main Chainlink
  track requires a Confidential Workflow via CRE, privacy-preserving
  computation, with requirements still listed as "coming soon" on the prize
  page. Faultline has no confidentiality requirement as designed. Do not
  retrofit one to chase this prize. Only revisit if a real confidentiality
  need surfaces organically, for example an institutional user not wanting to
  reveal which wallets it is stress-testing, and only after the CRE
  requirements actually publish.

- DROPPED: Hedera, Arc, 1inch, ENS, World, Privy, Bazantic. None map to what
  the solver or graph actually does. Do not integrate any of these to fill a
  third slot.

Submit with 2 partner prizes selected, not 3.

## 5. Repo requirements

Public from the first commit (rule 3 in section 2). These files are graded
artifacts, not housekeeping:

- CLAUDE.md — this file. Event rules permit spec-driven AI workflows but
  require spec files and prompts to be in the repo.
- BUILDLOG.md — append same-day, never reconstruct at the end. Record every
  schema surprise, every simplifying assumption and why, every workaround,
  block numbers used, anything that broke and how it was fixed. This file
  becomes the "How it's made" submission, which is the highest-weight artifact
  for partner prizes at an async-judged event. You will not remember which
  subgraph field was missing at hour 33.

Commits are judged. Rule: commit frequently, no small commits carrying large
changes. Messages must match the actual diff. The history should read as a
build log. Free credibility, do not waste it.

## 6. Phase plan

Each phase has a gate. Do not start the next until the current gate passes.
Tell me when a gate passes and when one fails.

PHASE 0 — VERIFICATION. Notes only, no code. Can run before the window opens.
Read the Aave v3 and Compound subgraph schemas directly. Answer concretely:
- Which entities carry user position state, exact field names as they appear
- Are liquidation thresholds and bonuses in the subgraph, or do they require
  contract reads? If contract reads: which contract, which function, which
  network. THIS IS THE HIGHEST-VALUE UNKNOWN IN THE PROJECT.
- Full position set for one wallet in a single query, or pagination and joins?
  Show the query you ran.
- What exactly is exposed for tick-level Uniswap v3 depth
- Which Chainlink service, and what the write path looks like
GATE: a written schema map with real field names, plus an explicit list of
everything assumed to exist that does not. Be pessimistic. This phase is the
most likely to blow up the project.
STATUS: passed. See BUILDLOG.md.

PHASE 1 — EXPOSURE GRAPH
Positions from two lending protocols, linked through shared collateral
assets and priced against Uniswap v3 depth. Wallet-protocol graph: nodes are
wallets and protocol markets, edges are lending positions (supply/borrow)
typed by asset and protocol. No direct wallet-to-wallet or LP-collateral
edge; the contagion channel is the shared asset under price pressure, not a
position link.
GATE: print one real wallet's full cross-protocol position set and reconcile
it by hand against the protocol UIs. Do not proceed until one wallet
reconciles exactly. If it does not reconcile, every downstream number is junk.
STATUS: passed. See BUILDLOG.md.

PHASE 2 — SOLVER
Fixed-point iteration: apply shock, recompute health factors, liquidate
breaches, apply price impact from pool depth, repeat until no new breaches.
State the convergence condition explicitly. Handle depth exhaustion.
GATE: a shock large enough to liquidate a known-leveraged wallet does so, and
intermediate numbers are hand-checkable. Walk me through one cascade by hand
before we trust it.
STATUS: passed and closed. Reference cascade externally reconciled against
DeBank on both wallets, solver-verified, frozen. See BUILDLOG.md,
"Reference cascade reconciled and frozen."

PHASE 3 — DROPPED (was ONCHAIN WRITE)
Chainlink dropped as a sponsor track 2026-09-05 (see section 4); no
remaining prize requires an onchain state change. Nothing to build here.
Skip from Phase 2 straight to Phase 4. Kept as a marker instead of deleted
so the phase numbering and the reasoning both stay visible in history.

PHASE 4 — VISUALIZATION AND SUBMISSION
Two parts: the visualization build itself (build order and scope in
section 9) and the submission deliverables. Video (HARD 4 minute cap;
speeding up video is disqualifying and manually verified) and the "How
it's made" writeup assembled from BUILDLOG.md. Precompute the demo
scenario so nothing loads cold on screen.
GATE (visualization): the core cascade animation renders correctly, bound
to the real reference-cascade fixture, tested on the actual recording
hardware (section 9).
GATE (submission): video runs under 4 minutes with no dead air waiting on
a query.
STATUS: visualization step 1 (core cascade, fixture-bound) built and
verified live in-browser 2026-09-06. Steps 2-4 of section 9 not started.

## 7. Build toward these three screenshots

Decided in advance so we do not scramble at hour 34. Minimum three required,
and the first doubles as the cover image in the showcase grid.

1. THE COUNTERINTUITIVE RESULT. Shock hits protocol A; a wallet leveraged
   there gets liquidated; the forced sale moves the shared collateral
   asset's price against real Uniswap v3 depth; that price move liquidates a
   second, unrelated wallet on protocol B, which had no exposure to protocol
   A at all. This is the whole product in one image. Make sure the UI can
   render it clearly. This is now a real, reconciled result, not a target —
   see the reference cascade in BUILDLOG.md. Two layered findings, not one:
   the shared-collateral link (the original thesis) AND a second, real,
   independently-verified finding that surfaced getting the first one
   right — this specific pool has almost no depth outside a narrow band,
   so the price move is a near-total collapse, not a moderate haircut. The
   collapse number must never appear without the depth explanation in the
   same beat (section 9).
2. The exposure graph before the shock, clean, so the after-image contrasts.
3. Solver output as data: propagation path with wallets, protocols, and a
   dollar figure. Proves it is a model, not a visualization.

Demo narration must name real protocols, a real asset, and a real dollar
figure. Abstract metrics read as academic. A dollar figure reads as a finding.

## 8. Scope sliders, pull in this order

1. Wallet count: top 500 to top 100 to top 20
2. Protocol count: three to two
3. Price impact: depth-based to a fixed haircut
NEVER cut: video and writeup time.

## 9. Visualization build plan

Build order for the Phase 4 UI (react-three-fiber + React Bits, section 3),
decided 2026-09-06. Nothing here starts before the Phase 2 gate passes
(section 6) — it has.

1. Core cascade visualization first, bound directly to
   `faultline/fixtures/reference_cascade.json`'s actual pass sequence, not
   synthetic or eyeballed timing. The rupture/price-crash moment is driven
   by the real price points and real wallet events in that fixture, nothing
   invented for effect. Presentation choices (tween duration, camera
   easing, layout geometry) are fine to invent; data values are not.
2. Live shock slider once the core renders correctly. Wire it to the real
   solver endpoint, not just replaying the fixture, so a judge dragging it
   is looking at a live computation. The fixture stays as the guaranteed-
   clean fallback path for the recorded video specifically, in case a live
   call is slow or flaky during recording — edit out the wait, do not speed
   up the video (the PHASE 4 submission gate already requires no dead air;
   speeding up the video is separately and independently disqualifying).
3. React Bits for polish only: dollar-figure reveal at the moment the
   second wallet crosses HF 1.0, entrance transitions, number tickers.
   Nothing structural.
4. Do not build the 26-wallet oracle-correlation finding or the
   scale-mismatch finding into the primary visualization. Both are real
   findings (BUILDLOG.md, 2026-09-05/06) and belong in narration and the
   writeup, not the animated cascade itself. One clean cascade animated
   well beats two cascades animated half as well.

NON-NEGOTIABLE, added 2026-09-06: the reference cascade's price collapse
(wstETH to fractions of a cent) must never appear on screen or in
narration without the liquidity-depth explanation in the same beat. This
is a real, verified second finding (BUILDLOG.md, "Reference cascade
locked: two findings, layered, neither hidden"), not a rounding artifact
-- a bare crashed number with no context reads as broken even though it
isn't. When a liquidation event's price update fires, the caption states
both the number and why (e.g. "liquidity here drops below 5% of its
starting value after 4 ticks -- this sale finds almost nothing to absorb
it"), using the fixture's own `pool.depth_profile` data, not an invented
figure. A depth-chart inset showing the real liquidity cliff (dense near
the old price, flat near the new one) is a strong addition if there's
room for it; not required if time is tight, but the caption pairing is
required regardless.

Performance rule: test on the actual recording hardware early, not the
last day. If frame rate is a problem on that specific machine, fall back
to a fixed, pre-rendered camera path over the fixture rather than cutting
the 3D entirely.

## 10. Working style

- Terse. No preamble, no "great question," no restating what I just said.
- NO EM DASHES anywhere: code comments, docs, commits, submission copy.
- No inflated or fabricated claims. Everything defensible under review
  scrutiny. No "first ever." No accuracy claims we have not measured.
- Push back if I am wrong. Say so directly and say why.
- ASK before: solver language, third sponsor, any scope change.
  DECIDE ALONE on: file layout, library choices, naming.
- Flag immediately if a gate is going to fail. Never work around a broken
  gate quietly.
- When I ask for a readback, tag every factual claim [VERIFIED] with the query
  and raw output, [DOCUMENTED] with the URL, or [ASSUMED] with what would
  confirm it. Untagged claims are treated as fabricated.
- Subgraph/contract IDs come from the protocol's own docs or README, never
  from a search result, and get verified against a live query before being
  trusted. Learned the hard way in Phase 0/1 verification: three separate
  IDs sourced from search results were wrong (dead, or a different schema
  entirely) despite a plausible-looking display name.
- If an instruction references a decision, rule, or prior conversation that
  isn't actually in this file or in BUILDLOG.md, ask for it to be added
  here before proceeding, rather than proceeding on trust and noting the
  gap afterward. This file and BUILDLOG.md are the source of truth, not
  chat history I can't re-read. Fixed 2026-09-06 after the same reference-
  drift pattern (section numbers, a "UI planning conversation," a "scoping
  call") recurred multiple times.

## 11. Do not

- Do not add a GNN or any ML component. If it seems appealing, reread rule 1
  in section 2.
- Do not author subgraphs.
- Do not build the visualization before the solver works. (Solver works —
  see section 6. Visualization build order is section 9.)
- Do not mock data to unblock yourself. Report the blocker instead.
- Do not write project code before I confirm the hackathon window is open.
  Only in-window work is judged. (Window confirmed open 2026-09-05.)
