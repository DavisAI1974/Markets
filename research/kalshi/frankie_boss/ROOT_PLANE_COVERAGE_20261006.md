# ROOT frame wiring and the full registry — 2026-10-06

Source-built, runtime-unverified. No AWS action, data/scientific run, installation, test suite or E2E. This continuation
starts at `c75a805a`. CCode owns the separate Step #4 assignment; its scientific-teacher files are unchanged here.

## Direct answer to Greg's 99-plane question

No: neither the prior ROOT nor this frame-section patch demonstrates computation of every applicable plane.
The authoritative pinned registry has **99 union layers**, not 99 raw/calculation planes. Its content identity is
`239a14808850d9cc9ba589165e4263c0e3f11a0c574052f39bfaa133adf296b1`. It is available at producer commit
`2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134` as
`research/kalshi/agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json`. The retained
`audits/CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json` names the same registry and all 99 identities.
`audits/FRANKIE_FEED_AUDIT_SUNDAY_CYCLE0_20260916.md` explains that the former 105 became 99 after six helper-architecture
layers were removed. Its historical delivery results are evidence about that earlier run, not the present experiment.

| Registry groups | Layers | Role in this experiment |
| --- | ---: | --- |
| Canonical raw DBN MBO | 6 | Source messages, bootstrap, provenance and integrity; journal reads alone do not prove every field reaches search/model computation |
| Lifecycle, FIFO/full-book, microstructure, legacy crosswalk, geometry, prebirth and clocks | 49 | Existing calculation/clock inventory; the Step #3 map covers this subset, with partial and missing paths explicitly named |
| Common controls, current brain, learned structure, carry-forward, A-memory/A-clean overlays | 23 | Knowledge/control inputs; audit their actual applicable learner/teacher consumers under Step #2, not numeric ROOT series by default |
| Sealed Step-1 and timing answers | 9 | Preserve the lawful answer boundaries; do not expose these as live discovery inputs |
| Provisional shadow | 2 | Disabled by the existing policy; not activated here |
| Append-only outputs | 10 | Outputs, including Frankie's private reasoning; not all lawful teacher inputs |
| **Total** | **99** | No claim of current all-layer computation |

The 49 calculation/clock layers plus six canonical-source layers are 55. This inventory accounting does not prove
55/55 active computational coverage. Dipole columns, external tables, scalar leaves and the full registry's layer
identities are different units; do not add their counts into an invented completeness figure.

The target remains all applicable normal ingest/calculation evidence reaching Frankie and both teachers, alongside
accumulated knowledge, while preserving private trade-logic, host-answer and Jev boundaries. The BOSS retains its
broader original representation/target/mask/control/training role. A list, source read or retained file is not proof
of consumption. This patch does not complete Step #2 or #3.

## Verified gap and the source connection built here

The pinned adapter's `event_frame` already returns `book`, `activity` and `integrity`. `book_snapshot` is called with
`depth_levels=10, include_full_depth=False, include_order_ids=False`. It supplies top-ten level summaries and aggregate
full-depth quantities; it does not supply the full FIFO identity/order observation. The original scientific summaries,
including queue-age quantiles and activity windows, are retained as produced; their mathematics are not changed.

`Session.derive(retain_frame_sections=True)` now carries those three original sections into each existing
`.rows/frames.jsonl` row beside the unchanged legacy scalar/transition columns. The experiment's ROOT caller opts in;
other Session callers keep the old default. There is no extra adapter/teacher pass, full-book reconstruction, new depth
cap, new statistic or bedrock activation. Every leaf the selected sections actually contain is retained without a
field whitelist, rounding, pooling or truncation. Legacy scalar aliases and nested values remain representations of
the same evidence, not extra independent observations.

The existing data export already includes `.rows/*.jsonl` and the five legacy layer files. The existing search
`columns()` flattens all scalar/list/nested leaves; `frames.*` is placed directly on its own F_LAST frame axis, including
equal receive timestamps. Those channels reach `_step_job` -> `_cell_job` -> `couple`, with unchanged transforms,
cell rule, lag units and circular-shift statistic. No search-side re-read/recalculation was necessary. Frame receipts
now list the numeric/text fields actually found in each section; old exports lacking them remain visible as such.

`FRANKIE_ROOT_FRAME_SECTIONS_V1` is pinned in the experiment source binding, unfinished legacy state identity, layer
metadata and derivation/calculation receipts. Resume refuses a changed projection instead of mixing old and new row
shapes. The finished-derivation resume path checks the same version before reuse. Existing completed ROOT artifacts
are not rewritten or silently replayed; an older reused export does not gain these fields merely because code changed.

## Still open

- Every intermediate INPUT field, the complete APPLIED envelope, every resting order/FIFO identity and deeper per-level
  rows are not all connected to the current search. The existing full-evidence/native-ordinal reader is built but the
  preserved axis-changing draft remains unapplied. Frame summaries are not a replacement for that evidence.
- Cross-group family/D geometry, prebirth, ancestry, identity/lifecycle and other full-capture projections require the
  existing producers disabled by the current experiment's bedrock-off configuration. This patch does not activate them.
  The pinned `native_full_capture_adapter._window_extras` belongs to that separate producer; its former classification
  as an omitted ordinary V4 event-frame field was corrected to not-produced on this path.
- Dipole row states/reasons are retained but not search cells; the pinned DState itself is not retained as a separate
  surface. Existing six-column teacher projections do not prove full D-state consumption.
- The 23 knowledge/control/arm layers still need their applicable current consumer reconciliation under Step #2.
  No sealed answer, disabled shadow or private output is reclassified as public teacher evidence to inflate coverage.
- CCode's Step #4 handles scientific candidate/check/survivor connections. Cross-owner coordination remains a separate
  #4/#8 integration gap; giant evidence stays on the owning lane.

AWS CPU only; exactly two main and one Linux held 16-CPU lanes, 15 workers plus coordinator; same owner ROOT through
completion. No explicit AWS go. Stop and discuss before workflow #5; Granite is with another chat and Jev CPU remains
discussion pending. One real E2E only after wiring/discussions and AWS go; 30 days need separate authorization.

Checks for this slice: Python syntax compilation of the changed modules and `git diff --check`, plus direct source
review of the pinned producer, exporter, search consumer and both ROOT resume paths. No runtime verification.
