# Bedrock shared calculation/evidence route — 2026-10-06

Source review only; runtime-unverified. Steps #2/#3 remain open. This report does not activate a producer, change mathematics, establish full 99-layer computation, or authorize AWS execution.

## Current direction

Greg's latest instruction requires bedrock information and supersedes the earlier experiment exclusion of that information. The giant table is not required. Working assumption: retain every exact owner-local evidence row and necessary calculation state, omit giant rendered tables and avoid redundant expanded copies. Removing scientific evidence is not part of this change.

Use the existing framework: calculate once in Frankie's reusable historical/live pipeline; let Frankie and both teachers read the same lawful results and evidence. Their different learning/checking roles do not require separate raw ingestion. Preserve the explicitly authorized learner-owned second Dipole walk and its answer boundary; same-instrument remeasurement is not independent confirmation.

The pinned native producer is `2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134`. Its incremental calculations already exist. The smaller initial change is connection and representation work, not replacement scientific formulas.

## Reusable source map

Pinned paths below are under `research/kalshi/frankie_raw_mbo_benchmark/`; box paths are under `deploy/aws/box/`.

| Source / function | Existing behavior and implication |
| --- | --- |
| Pinned `native_replay_driver.NativeReplayDriver.consume`, `_on_group`, `_feed_sections` | Advances native records/groups and feeds existing full-book, lifecycle, geometry, recurrence, exhaustion, recognition, Dipole and response calculations. Calculations do not require a rendered whole-day table. |
| Pinned `native_full_capture_adapter.FullCaptureAdapter` | Preserves per-record book effects, FIFO identities, deeper book, event-anchored activity and integrity evidence when those facts exist. Wraps the locked adapter rather than changing its bytes. |
| Pinned `native_calculation_runner.NativeCalculationRun.note_member_row`, `note_lifecycle_row` | Writes exact rows to supplied sinks instead of collecting the entire evidence table in RAM. `finalize` retains section summaries, denominators and evidence receipts. Its `add_finding` refuses to substitute calculation output for principal-authored findings. |
| `frankie_box_bedrock.run` | Runs the pinned driver on the verified journal, with exact member/lifecycle/legacy sinks, original arguments, reconciliation and full-state checkpoints. Performs no DBN ingestion. `NeverInvoke` prevents traversal from making BOSS calls. |
| `frankie_box_parallel_evidence.RuntimeSections` | Existing encoding batches preserve pinned serialization and original order. Batch thresholds are not scientific-output caps. |
| `frankie_box_native_checkpoint.FullCheckpointer`, `restore_driver`, `consume_recovery` | Saves/restores the driver object graph and ledger extents; full-state continuation skips previously processed source records without recalculating them. |
| `frankie_box_segmented_ledger` | Preserves frozen prefixes and new append segments on recovery. Currently assembles ordinary final JSONL files for existing downstream consumers. |
| `frankie_box_projection.project` | Creates resumable compressed layer representations from sealed exact ledgers and the existing crosswalk. This is downstream representation, not another scientific calculation. |
| `frankie_box_boss_session.Session._derive_bedrock`, `_write_digest` | Traversal, projection and digest are identifiable stages. `_derive_bedrock` currently always follows traversal with projection; `digest=False` already avoids Markdown digest rendering. |

The historical learning/serving framework also exists: `research/kalshi/frankie_boss/context_session.py` (`ContextSessionRunner`), `native_forecast_refresh.py` (`NativeForecastRefresh`), and `native_forecast_learning.py` (`NativeForecastLearner`). Production bindings and Sunday execution connect these existing components. The current experiment does not establish that this model-learning/serving route consumes its new shared calculation surfaces. Reuse and reconcile these consumers; do not invent a second learner framework.

`research/kalshi/frankie_boss/teacher.py` already provides `TeacherHead`, targets and controls. Preserve the BOSS teacher's broader original representation/target/mask/control/training role. Computing a quantity, storing it, finding an association, supervising a representation and using it live are distinct connections; none is proved by the others. Frankie's private trade-decision logic remains excluded from shared teacher evidence.

## Lawful availability and exact state

Publish each result on its original availability boundary. `_advance_candidates` judges completed seconds, never an unfinished current second. Response and replenishment observations mature in stream time. `_close_lineage` emits observed-node properties at continuity boundaries; finalization emits terminal/censored rows. Later-completed properties cannot become earlier live inputs through a shared reader.

Full book/FIFO state, queues, anchored accumulators, candidate/episode state, lineage and unresolved horizons remain necessary. Streaming storage does not prove bounded scientific memory or adequate live latency. Preserve native row identity, order, units, masks, missing/censored reasons, clock basis, denominators and scientific treatment of single occurrences. The 99 union registry includes controls, sealed answers and outputs; it is not 99 interchangeable numeric live columns.

## Concrete gaps before activation

| Gap | Required connection |
| --- | --- |
| `Session.derive` explicitly rejects `recovery=True, bedrock=True` | Integrate complete native stage recovery before removing this guard. |
| `_derive_bedrock` receives a checkpoint only if its caller sets `native_resume_checkpoint`; Monday does, experiment ROOT does not | Bind and discover the exact owning-run checkpoint; distinguish unfinished traversal, finalized native output, projection and published derivation. Preserve previous artifacts. |
| Experiment save requests reach legacy recovery but not the native traversal's cooperative stop path | Route them through the existing complete-state save at a lawful closed-group boundary. Do not stop with undocumented open-group state or replace continuation with replay. |
| Experiment ROOT provides opening-book state only to its legacy pass; `bedrock.run` currently constructs the driver with a fresh default adapter | Give the native path the same lawful initial book and explicit provenance. Preserve the distinction between known book state and unknown prior activity anchors. |
| Experiment source binding carries abbreviated manifest information because bedrock was off | Supply the complete day manifest/count identity required by the native runner. |
| `frankie_box_experiment_data.py` explicitly excludes native bedrock artifacts | Replace obsolete blanket exclusion with lawful shared surfaces while retaining sealed-answer/private-output boundaries. |
| Current search/teacher connections do not establish every native row/section's consumption | Reuse the existing full-evidence reader where its identity/axis contract applies, and connect each applicable learner/teacher consumer. The preserved axis-changing draft remains unapplied; no event-axis lag substitution is implied. A manifest or retained file is not consumption. Coordinate scientific candidate/check routes with CCode's Step #4 owner. |
| Segment receipts/readback and finalization/projection expect consolidated ledger paths | Retain exact local JSONL for the first connection slice. Eliminating consolidated files requires a separate segmented-reader/finalizer/projection change. |

## Staged source implementation scope

1. **Shared representation, inactive by default:** in `frankie_box_boss_session.py`, separate native traversal receipts/surfaces from optional projection/rendering. Bind the selected representation and crosswalk identity. Reuse existing exact member/lifecycle/legacy ledgers and section results, without a second calculation or giant digest.
2. **Complete recovery:** in `frankie_box_experiment_root.py`, `frankie_box_bedrock.py` and the existing native checkpoint integration, bind full source/opening state, save requests and native stage checkpoints. Resume completed stages in place and preserve unfinished evidence. Do not remove the recovery guard ahead of these connections.
3. **Actual shared consumers:** update existing export/full-evidence/search and applicable BOSS/learner knowledge consumers. Preserve original native timing and scientific transformations. Connect useful completed knowledge at applicable execution boundaries across random-order days; trading-date chronology does not gate learning. CCode-owned Step #4 files stay with CCode.
4. **Later storage optimization, only if needed:** replace repeated wide projections with exact crosswalk-backed views/references. If eliminating consolidated JSONL is required, adapt segmented readers and current reconciliation/projection contracts without altering logical row bytes/order/counts or dropping evidence. This is not a prerequisite to omitting a giant rendered table.

This report adds no validator framework or tests. Source changes, once made, remain source-built until the authorized real E2E. No AWS go has been given: CPU only, exactly two main and one Linux held 16-CPU lanes, 15 workers plus coordinator, same owner ROOT through completion, giant evidence local. Stop and discuss before workflow #5; its preserved draft stays unapplied. Greg is assigning CCode the smaller-model facilitator integration, based on the other chat's report; its exact selected model must come from that report. This assignment does not apply the preserved freeze/evaluation draft or authorize AWS execution. Jev CPU remains discussion pending. Thirty days require separate authorization.

## Memory MCP status

The user explicitly authorized a local codebase-memory-mcp installation during this continuation. The installer/CLI was blocked by its process-fingerprint check because `getpid` and `/proc` identities did not match in this environment. No memory graph review occurred. Findings in this report come from direct source inspection; this installation authorization is not AWS compute authorization.
