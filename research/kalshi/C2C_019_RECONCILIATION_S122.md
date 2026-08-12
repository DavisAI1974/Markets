# C2C-019 Registry / Frankie Reconciliation — S122

Status authority for this report: current branch code and CI first; `research/kalshi/OPEN_ITEMS.json` second; generated `store/data_points.json` only when fresh. Historical handoffs are provenance, not status authority.

## Why this reconciliation exists

`OPEN_ITEMS.json` still declares `current_session: S114`, while Frankie work continued through S115-S121. Therefore an `OPEN` label in that file is not sufficient evidence that a build remains undone. Likewise the committed `store/data_points.json` is a generated snapshot at 1,717 served / 1,113 unread and is older than the live 44-block registry rebuild reported during C2C-019. Do not convert either stale count into a build queue.

## S115 items that are already built but still appear OPEN in the stale work registry

| item | stale registry status | current code evidence | reconciled classification | remaining action |
|---|---|---|---|---|
| M-16 | OPEN | `databento_backfill_s115.py` guarded root-relative entry, landing-byte assertion, n-roll default | PARTIALLY_FIXED | physical EC2/S3/data-plane repair and verified landing still required |
| A-61 | OPEN | `frankie_s115.pin_snapshot()` / `verify_snapshot()` | FIXED | no rebuild; use the gate |
| A-50 | OPEN | `assert_no_narrative_leak()` plus A-67 narrative seal | FIXED_AS_GATE | production/training runs must pass it; no architecture rebuild |
| A-66 | OPEN | `frankie_s115.OWNERSHIP` + collision hard-fail | FIXED | no rebuild |
| A-59 | OPEN | `frankie_render_s115.py`, `FrankieAgentObject`, typed posterior, canonical render-byte check | FIXED | no rebuild |
| A-68 | OPEN | append-only per-lens JSONL book + strictly-earlier `causal_lens_view()` | FIXED_AS_CONTRACT | retention effect still requires A-67 arm 2 evidence |
| A-62 | OPEN | generated `build_specialist_track_records()` from posteriors + actuals | FIXED_AS_CONTRACT | empirical effect still needs measured run |
| A-65 | OPEN | `validate_compaction()` same-cell posterior diff | FIXED_AS_CONTRACT | validate each proposed view change per cell; C2C-018 additionally proved lossless whitespace compaction for the full 90-play packet |
| A-67 | OPEN | `frankie_validation_s115.py`, sealed substrate, noncanonical namespaces, fixed per-event metrics | FIXED_AS_HARNESS | arm 1 and arm 2 experiments remain evidence operations |
| A-69 | OPEN | `TrainingSplit.validate()`, `grade_fj1()`, `training_release_gate()` | FIXED_AS_HARNESS | train/score on reconstructed walked corpus, then held-out test |
| A-42 | OPEN | FJ-1 adapter wired to frozen `failure_localization.py` taxonomy | FIXED_AS_HARNESS | first production grading run remains evidence |

This table is evidence that the stale S114 registry must not be read as “all OPEN items are unbuilt.”

## Later Frankie work already completed after the S115 implementation record

- C2C-018: full 90-play Sol packet passed the S120 structural/full-brain canary after lossless whitespace compaction. 90/90 play bodies, play index, A-82 and no-outcome invariants survived semantic round-trip; no play was dropped.
- S121: `frankie_s121_curve_restore.py` removed the fixed 2-hour output grid. Frankie chooses its own path timestamps. The harness does not average, smooth or interpolate the forecast.
- S121: ABSTAIN is a trade/no-call disposition and no longer forces a flat market forecast.
- S121: `frankie_kitchen_sink_audit_s121.py` hard-stops when DavisAI possesses causal-by-cutoff, non-future-contaminated information that Frankie cannot access.
- S121/C2C-019: the omission error has priority over weaker status-consistency diagnostics, so stale labels cannot hide a silent serving failure.
- A-87: `system_inventory.py` was added specifically to retain DONE/SUPERSEDED history and stop completed work from being rediscovered as missing.

## Historical data-gap claims reconciled against current registry evidence

| historical gap / family | item | current evidence | classification | canary consequence |
|---|---|---|---|---|
| Hydro WAT dropped by serving list | A-16 | registry itself says DONE S113, execution-verified; `hydro_mwh`, PS, BAT, unnamed generation, hydro share/change served | FIXED | do not call hydro unbuilt; still account for per-BA PS separability and A-20 forward-water mechanism |
| Forward wind/solar absent | G-4 / S114 forward-forcing item | registry says DONE S114 through `weather_forcing_forecast`; wind and solar served separately | FIXED | do not reopen as a missing feed; verify target-cell causal vintage/accessibility |
| Ensemble density absent | G-5 | registry says DONE S114: 31-member GEFS density through gas-weighted station weighting, 10/10 g24 vintage audit | FIXED_FOR_GEFS | ECMWF 51-member availability is not proof that Frankie lacks ensemble density; audit exact target-cell access rather than demanding a duplicate feed |
| Battery absent | G-19 | registry says DONE S113; BAT served, with negative-while-charging semantics documented | FIXED | target-cell audit only |
| Wind 7d change absent | A-52 | registry says DONE S114 | FIXED | target-cell audit only |
| Zero-change / seasonal-naive baselines absent | A-1 | registry says DONE S113; zero-change, seasonal-naive and persistence wired and causal | FIXED | use as registered benchmarks |
| Chain state absent | A-11 | registry remains OPEN | STILL_OPEN | if possessed and causal for the target cell but inaccessible to Frankie, kitchen-sink gate must STOP |
| Thermal stack served but unread | A-15 | registry remains OPEN on play consumption; WAT/BAT serving work landed separately | PARTIALLY_FIXED | reader count is diagnostic only; kitchen-sink access may satisfy Frankie even if old plays have zero readers |
| Southeast BA coverage | A-18 | registry remains OPEN | STILL_OPEN | target-cell relevance/causality must be explicit; do not claim complete family coverage from US48/SOCO alone |
| Unread-point triage | A-23 | registry remains OPEN | STILL_OPEN | 1,222 live unread fields are a diagnostic workload, not 1,222 missing Frankie inputs; actual packet access is the canary criterion |
| LNG feedgas EBBs | G-7 | source research delivered, scraper/feed remains OPEN; existing feed described stale/null | STILL_OPEN | if a causal historical value was possessed for target cutoff, serve it; otherwise mark concrete unavailable evidence |
| Coal headroom / 860M + outage aggregates | M-6 | registry remains OPEN | STILL_OPEN | do not synthesize capacity/headroom from unrelated served generation |
| Unit-level forward nuclear calendar | A-17 | research refuted the original “public exact schedule” premise; public aggregate ISO products and some commission filings are separate | PARTIALLY_FIXED / MEASURED_PUBLIC_GAP | do not invent unit-level calendar; account for available aggregate/filing data by cutoff |

## Claude live-registry numbers: how to use them

Claude reported a dry live rebuild of 44 decision-state blocks with 1,914 served leaves, 1,222 unread, 5 held-not-served, 7 named absent and 124 planned. Those numbers are plausible as a live generator result but are NOT equivalent to “124 unbuilt things.” `data_registry.py` derives planned/status material from a work registry whose session marker is still S114. The committed machine store is demonstrably stale at 1,717 served / 1,113 unread.

Until the live generator is written on the real data plane, record the live counts as **UNCOMMITTED_MEASUREMENT** and the committed counts as **STALE_SNAPSHOT**. Neither is sufficient by itself to authorize new implementation work.

## Current hard boundary before another paid canary

C2C-019 remains the controlling task. A new paid model invocation is NOT authorized by this reconciliation. Readiness requires:

1. regenerate/write the data registry on the real data plane;
2. produce the exact target-cell causal inventory, not a family-level hand list;
3. pass `frankie_kitchen_sink_audit_s121.validate_inventory()` and required-domain accounting;
4. prove every possessed + causal-by-cutoff + non-future-contaminated field/family is accessible to Frankie, even when old brain reader count is zero;
5. explicitly classify unavailable fields with evidence instead of silently dropping them;
6. preserve all 90 plays, A-82 future/actual price-curve wall, endogenous curve timestamps, no harness interpolation, and no execution authority;
7. keep `research/kalshi/spawn.py` untouched.

## What actually remains vs what must not be rebuilt

**Do not rebuild:** A-61, A-50 gate, A-66, A-59, A-68 mechanism, A-62 mechanism, A-65 mechanism, A-67 harness, A-69 harness, A-42 adapter, A-16 hydro serving, G-5 GEFS density, forward wind/solar serving, battery serving, A-52 wind change, A-1 baselines, S121 endogenous curve contract, S121 kitchen-sink omission gate, A-87 inventory machinery.

**Evidence/data operations still required:** M-16 physical data-plane repair/landing proof; exact target-cell kitchen-sink manifest; reconstruction of missing old actuals on their original basis where needed; A-67 arm 1; A-69 training/held-out scoring; A-67 arm 2 retention; first production FJ-1 run.

**Genuinely unresolved data/capability work still represented in the stale registry:** A-11 chain state, A-15 traditional play consumption of stack terms, A-18 Southeast BA completeness, A-23 unread-field triage, G-7 LNG feedgas EBB ingest, M-6 coal headroom, and the public-data-limited portion of A-17. These are not automatically prerequisites for every historical target cell; the causal kitchen-sink audit decides that per cutoff.

This is the S122 status bridge until `OPEN_ITEMS.json` and the generated data-point store are refreshed from the real data plane with evidence.