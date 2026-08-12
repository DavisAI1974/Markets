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

### B1. Registry-first reconciliation — REQUIRED

Greg supplied the historical generated `DATA_POINTS.md` master-list snapshot. Do NOT treat its counts or hole list as current truth and do NOT reopen work merely because that snapshot says it was missing.

Use the repository registries as the current status authority:
- root `OPEN_ITEMS.md` is a generated view only;
- `research/kalshi/OPEN_ITEMS.json` is the canonical mutable work/status registry behind that view;
- regenerate the current data-point registry from the current `research/kalshi/data_registry.py`/registered build path on the terminal/data plane if present; if the generator or generated output moved, trace the current equivalent rather than inventing a hand list.

Produce a reconciliation table for every material gap/family in the historical `DATA_POINTS.md` and every relevant current OPEN item with these columns:

`historical_gap_or_field | historical_item_id | current_open_item/status | current_code_or_data_evidence | served_now? | Frankie_accessible_now? | causal_at_target_cutoff? | classification | action`

Allowed `classification` values:
- `FIXED` — prove with current code/data/serving evidence;
- `PARTIALLY_FIXED` — name exactly what landed and what remains;
- `STILL_OPEN` — current registry/evidence says unresolved;
- `SUPERSEDED` — name the replacement item/mechanism and prove it;
- `NOT_APPLICABLE_TO_TARGET_CUTOFF` — data did not legally exist by cutoff;
- `UNKNOWN_STOP` — evidence is insufficient; this blocks readiness rather than being guessed away.

Important current-registry examples that MUST be reconciled rather than assumed fixed: A-11 chain state, A-15 thermal-stack consumption, A-17 forward nuclear schedule, A-18 Southeast BA coverage, A-23 unread-point triage, G-4 forward wind/solar net-load half, G-7 LNG feedgas EBBs, and M-6 coal headroom. The current OPEN registry still carries these as unresolved as of this task's creation. If terminal truth proves otherwise, update the canonical registry with evidence rather than silently overriding it in the canary packet.

The historical `DATA_POINTS.md` "READ BY NOTHING" count is diagnostic, not a model-access definition. A field with zero `ng_brain.json` readers can still be available to Frankie if the raw/derived causal field is actually exposed to the reasoning backend. Therefore audit both separately:
1. traditional play/brain reader coverage; and
2. actual Frankie reasoning accessibility in the kitchen-sink packet/access layer.

Do not claim completeness from a family-level label alone. The regenerated registry/current state must be diffed against what the exact target-cell packet or retrieval layer exposes. Preserve fields even when no current play mentions them: Frankie is allowed to discover usefulness himself.

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
- current OPEN_ITEMS status and the generated data registry disagree without an explicit evidence-backed reconciliation;
- a historical DATA_POINTS gap is marked FIXED solely because it disappeared from a view/filename;
- a zero traditional brain-reader count is incorrectly treated as proof that Frankie cannot access a field through the kitchen-sink reasoning layer;
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
- regenerated data-registry identity/counts and its diff against Greg's historical DATA_POINTS snapshot;
- OPEN_ITEMS reconciliation, including FIXED/PARTIALLY_FIXED/STILL_OPEN/SUPERSEDED classifications with evidence;
- completeness-manifest results by data family and actual Frankie accessibility;
- any possessed-but-unserved or served-but-inaccessible data discovered;
- token/access design for the full kitchen sink;
- regression results/CI;
- `spawn.py` blob before/after;
- explicit confirmation: NO paid model invocation, NO target actual/RT opened, NO scoring.

Stop after offline/CI readiness. Do not run another Sol canary without a new C2C task and Greg/ChatGPT approval.