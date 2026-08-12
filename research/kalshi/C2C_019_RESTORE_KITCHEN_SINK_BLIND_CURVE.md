# C2C-019 — Restore kitchen-sink blind curve methodology

Owner: Claude terminal/AWS implementation, coordinated by ChatGPT
Status: OPEN
Predecessor: C2C-018 COMPLETE at d8e8c04

## Why this exists

C2C-018 proved the Sol backend, full 90-play brain serving, A-82 isolation, lossless packet compaction, and structural validation. It did NOT prove the intended forecasting methodology. The S120 canary adapter introduced a fixed 2-hour clock and whole-day ABSTAIN=flat-zero semantics. Greg has corrected this explicitly.

The canonical shared directive already states the load-bearing data doctrine: BOTH blind and refine get the KITCHEN SINK; blind's ONLY deliberate mask is the PRICE CURVE. The coordinator selects owners and never averages. Preserve that doctrine.

## Governing contract

For a historical blind recreation at cutoff T:

1. If information existed by T and DavisAI possesses it, Frankie can access it. Do not handicap him.
2. Hide only the target/future realized price curve and anything derived from future information relative to T.
3. Serve the complete brain/schema and all 90 play bodies. `play_index` may annotate/navigation-assist but must not remove access.
4. Serve all causal market/fundamental data families actually available for that cutoff, including rich Databento data and derived states, storage/EIA state, weather, fundamentals, positioning/flows, volatility, options, basis/contract structure, calendar/events, prior price history and historical analogues, plus every other causal family already built/ingested.
5. Frankie decides what matters and how to forecast. The harness must not preselect signals, average forecasts, smooth, fit, interpolate, force event choices, or impose a fixed clock grid.
6. Output is Frankie's blind high-resolution expected price path for the full session. Point count/timestamps are endogenous to his forecast and should be dense enough to represent the expected market evolution. Do not manufacture points after inference.
7. Daily curves concatenate chronologically into the week/two-week forecast. No pooled/averaged daily forecast substitutes for event/path structure.
8. Freeze the raw forecast before any target actual/RT curve is opened. Only then may a later explicit scoring task overlay/compare forecast vs actual. This task MUST NOT score or open the target actual/RT curve.

## Immediate implementation/audit work — NO PAID MODEL CALL

A. Restore the established methodology rather than inventing a new one.
- Trace the pre-S120 blind historical forecast/render path and its schema/contracts.
- Remove S120 `_EXPECTED_CLOCK`/fixed-interval enforcement from the canary boundary.
- Remove the rule that whole-day `ABSTAIN` implies an all-zero day curve.
- Keep explicit trade/no-call disposition if useful, but it must not erase the required market-path forecast.
- Preserve A-86's purpose: reject decorative/fabricated paths. Re-express it without fixed timestamps or averaging.
- Do not edit `research/kalshi/spawn.py`.

B. Build a causal-data completeness audit for the target cell before any next inference.
- Enumerate every data family DavisAI has built/ingested that could legally be available at the cutoff.
- For each family record: source/artifact, available-by-cutoff?, included/accessibly referenced in Frankie packet?, freshness/vintage, causal proof, and if absent the concrete reason.
- Distinguish truly unavailable historical data from data we possess but failed to serve.
- A packet is NOT ready if possessed causal data is silently omitted.
- The only deliberate target-period mask is the future/actual PRICE CURVE and future-derived information.

C. Token/access architecture.
- C2C-018 actual Sol input was 477,817 tokens, too close to 500k TPM.
- Do not solve this by dropping information access.
- Lossless serialization remains allowed. If the kitchen sink cannot fit inline, design an access/retrieval/chunking mechanism that preserves Frankie's ability to inspect every causal data family without exposing the target curve. Do not make a paid inference in C2C-019.
- Nova may be used only where semantics/capabilities are proven preserved; no lossy key truncation on canonical Frankie fields.

D. Regression tests.
Add tests that fail if:
- a fixed timestamp grid is required;
- a valid variable-timestamp dense path is rejected merely for not matching a clock template;
- a whole-day ABSTAIN is automatically converted to/requires a flat zero market path;
- any averaging/pooling/smoothing/interpolation is performed by the coordinator/harness;
- any of 90 plays is dropped;
- a possessed causal data family is silently omitted from the completeness manifest;
- target/future actual curve data leaks through A-82.

## Repo-truth notes

`research/kalshi/agents/mbo_refine_shared.md` currently says: "both agents get the KITCHEN SINK; blind's only mask is PRICE" and "coordinator SELECTS the owner per day — it never averages." Treat those as load-bearing.

`research/kalshi/store/sop_templates.json` currently contains the historical 2-hour BLD-1 output-clock language. Greg has now explicitly superseded that output-grid behavior for Frankie: do not edit protected `spawn.py`; identify the proper canonical contract migration seam and document it. Do not silently mutate old immutable blind artifacts.

`research/kalshi/forecasts/grp24.json` is an example of the older fixed-grid blind artifact and is provenance, not the desired new Frankie path constraint.

## Deliverable back to ChatGPT

Append C2C-019 COMPLETE/STOPPED to `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` using append-only ledger discipline. Report:
- exact files changed and commits;
- methodology authority traced;
- fixed-grid/flat-abstain removal status;
- completeness-manifest results by data family;
- any possessed-but-unserved data discovered;
- token/access design for the full kitchen sink;
- regression results/CI;
- `spawn.py` blob before/after;
- explicit confirmation: NO paid model invocation, NO target actual/RT opened, NO scoring.

Stop after offline/CI readiness. Do not run another Sol canary without a new C2C task and Greg/ChatGPT approval.