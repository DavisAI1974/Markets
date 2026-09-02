# Frankie: built but not wired and fed - the S121 search record (2026-09-02)

Greg, verbatim: *"i feel like this stuff has been built but just not wired and fed. we need a
search for the stuff that you think we should be building, all of it and have the Engineer agent
persona agents do the wiring and feeding of what has been built."*

This is the record of that search. Three read-only search agents swept the repository at the
development tip `bfb4e43` (branch `chatgpt/frankie-raw-mbo-benchmark-20260828`), one per area,
and reported what exists, who calls it, and what is missing. Line numbers are as read at that
tip. Callers were established by repo-wide grep excluding tests. The wiring itself is done by
test-engineer personas in isolated worktrees, one per area, each committing and pushing per
slice (D84); the arm is A_MEMORY (D86).

The finding, in one sentence: **every validator, receipt, renderer and gate needed for the
spawn path exists and is tested; almost none of it has a production caller. The one function
that does not exist anywhere is the sealed-absence proof producer.**

## A. Retained knowledge to the principal, with a receipt and a read gate

| existing piece | file:line | callers today |
|---|---|---|
| `build_context_bundle` (context receipt over a profile's artifacts) | `native_frankie_knowledge_registry.py:236` | own CLI, tests |
| `build_model_visible_context` (hash-bound retrieval index, external proofs) | `native_frankie_knowledge_registry.py:282` | tests |
| `bind_principal_knowledge_use` (per-artifact INSPECTED / UNINSPECTED disposition; THE READ GATE) | `native_frankie_knowledge_registry.py:349`, rule at 388-400 | tests only |
| `load_and_validate_manifest` (`ALLOWED_KINDS` = MARKDOWN, JSON, DIRECTORY_PROOF) | `native_frankie_knowledge_registry.py:106`, kinds at :21 | refresh, tests |
| `refresh_native_frankie_knowledge.refresh` (regenerates the manifest from the sources) | `refresh_native_frankie_knowledge.py:154` | own CLI |
| `classify_inventory` (63 KEEP paths: 31 md, 17 json, 15 py) | `native_knowledge_delivery.py:309` | rebind script, addendum render |
| `rebind_knowledge_layers` (14 knowledge layers rebound to real KEEP files; APPLIED) | `rebind_registry_knowledge_layers.py:88` | own CLI |
| `brain_view.build` (served / withheld manifest per call) and `brain_schema` statuses | `brain_view.py:189`; `brain_schema.py:57-58, 698` | the weekly forecaster, not the benchmark |

Measured: the knowledge manifest holds 12 artifacts; overlap with the 63 KEEP paths is ZERO.
Nothing on the spawn path imports `native_frankie_knowledge_registry`. No producer of
`FRANKIE_KNOWLEDGE_DELIVERY_RECEIPT_V1` exists. `native_layer_crosswalk.LAYER_PRODUCERS` still
carries a static bound-to-inventory flag for the 14 rebound layers (stale).

**Missing to wire:** register the KEEP set (and the seed memory, D86) as manifest artifacts,
one kind added for Python source; call the existing pipeline from the emitter; translate the
manifest state into the per-layer receipt the crosswalk consumes; read bound-ness off the
registry. Wired by the knowledge-and-gates persona.

## B. Proving the nine sealed layers absent

| existing piece | file:line | callers today |
|---|---|---|
| `validate_rt_surface_inventory` (`step1_sealed` over 9 `SEALED_SURFACES`) | `corrected_a_arm_execution_gate_20260828.py:283`, surfaces 124-136 | `run_pre_traversal_gates`, both launch workflows |
| `SEALED_LAYER_IDS` | `native_ingestion_layer_registry.py:81-93` | `validate_registry`, launch, crosswalk |
| crosswalk consumer of `FRANKIE_SEALED_ABSENCE_PROOF_V1` | `native_layer_crosswalk.py:1216-1229` | `crosswalk()` |
| the scan-and-hard-fail pattern | `brain_view.py:127 context_leak`, `:169 assert_no_context_leak` | the weekly forecaster |
| section K's object names | `NG_EXHAUSTION_FRANKIE_SOURCE_FILE_INVENTORY_20260824.md:195-203` | classified SEALED |

`odcore/leakage.py`, `frankie_causal_capture_gate_s126.py` and
`frankie_s114_separation_metadata_s126.py` were checked and are false leads for this shape
(numeric-series leakage and weather-data gates).

**Missing to build (the one new function):** `sealed_object_set` and `prove_sealed_absent`
producing the four-key proof the crosswalk already consumes, modelled on `context_leak`.

## C. The spawn gate

| existing piece | file:line | callers today |
|---|---|---|
| `crosswalk` (computed status, 99 rows) | `native_layer_crosswalk.py:1149` | own CLI, fixture render |
| `gate_applicable_inputs` ("the gate the coordinator wires at spawn") | `native_layer_crosswalk.py:1314` | own CLI, tests |
| `observed_carriers` (field census, section row counts, legacy keys) | `native_layer_crosswalk.py:942` | `crosswalk()` |
| `run_pre_traversal_gates` (registry, pre-call, RT surface) | `native_a_arm_launch.py:267` | launch, workflows |
| `fetch_frankie_ledgers.fetch` receipt | `fetch_frankie_ledgers.py:228` | `emit_frankie_spawn._load_delivery_receipt` |
| `emit_frankie_spawn.emit` (requires only the delivery receipt) | `emit_frankie_spawn.py:133`, arm at :161 | own CLI; NO workflow |

**Missing to wire:** the call at `emit()` after the arm lookup; the knowledge receipt it needs
(A); honest fixtures - `_census` has `fields: []`, `_result` sets no `ledger_retention`, the
legacy fixture carries only `ts_recv`, and the crosswalk's own gate test hand-sets DELIVERED,
so no fixture in the repo proves the gate can pass honestly. Production code already feeds
`observed_carriers` (the census at `native_calculation_runner.py:786`, the sinks at
`native_row_sink.py:206` via `native_a_arm_launch.py:544`).

## G. The output ledgers and their read-back

| existing piece | file:line | callers today |
|---|---|---|
| `AppendOnlyLedger`, `OutputBundle`, `write_bundle`, `load_bundle`, `bundle_receipt` | `native_principal_outputs.py:184-498` | tests |
| `required_ledger_ids` (derived, no count) | `native_principal_outputs.py:107-139` | `validate_output_bundle` |
| ten per-ledger validators | `native_principal_outputs.py:743-1230` | `validate_ledger_entries` |
| `validate_output_bundle`, `validate_output_bundle_dir` | `native_principal_outputs.py:1323, 1426` | tests, own CLI |
| `stage_spawn_request` / `SpawnStager` | `native_staging.py:61-108, 274-306` | `native_a_arm_launch.launch` (WIRED) |
| `load_principal_artifact` | `native_staging.py:126-250` | tests only |
| `attach_principal_findings`, `_admit_finding` | `native_calculation_runner.py:460-506` | tests only |
| `write_report` | `render_frankie_report.py:158-175` | `_render_report_beside` only |
| the V2 workmode handoff, lock and context manifest (produced by the coordinator of the prior reduced run) | `ng_exhaustion_two_frankies_workmode_coordinate_2day_20260825.py:313, 553, 845, 1117, 1222` | its own main |

The prior artifacts in `prior_memory/workmode-32851909748-1/` are a DAG of self-hashing
receipts with an artifact manifest, not a per-entry chain; they attest no API was called
(D70 predates this session). They came from the wrong data and are seed memory under D86.

**Missing to wire:** `load_principal_artifact` calls `validate_output_bundle_dir`; a read-back
driver and a CLI chain load and attach; the report at the choke point carries the crosswalk
table; the handoff machinery is re-fed from the bundle. Wired by the outputs-and-staging persona.

## H. How the principal is spawned and read back

No new coordinator. Staging is wired; read-back exists and is uncalled. The walk's coordinators
(`spawn.py`, `RUN_SOP.md`, `group_coordinate_*`, `archive_blind.py`, `merge_gate.py`,
`decision_trace.py`) do not mention Frankie and do not apply; their discipline (hard-fail on a
missing or stale artifact) is already in `load_principal_artifact`. `emit()` is called by no
workflow; one step in `frankie_ledger_delivery_20260902.yml` closes that. `native_staging.py`
is the only sibling without a CLI.

## I. The report and the renders

`render_crosswalk_table` (`native_layer_crosswalk.py:1367-1437`) already renders the per-layer
delivery table with knowledge, outputs and sealed status; its only callers are its CLI and the
fixture render. Least-new-code surfacing: inside `_render_report_beside` (the choke point) and in
the emitted prompt. `report_ledger_size.py` wired into `frankie_run_size_report_20260902.yml` is
the working precedent for a workflow step that runs a renderer.

## D, E, F. Clocks, event-anchored windows, horizons

The third search report. Orienting fact: Frankie's live path is the one package
`research/kalshi/frankie_raw_mbo_benchmark/`, and three universes of clock code never touch it:
the V4 universe (`ng_exhaustion_v4_causal_clock.py`, `ng_exhaustion_v4_mechanics.py`, the
runtime contracts, all real and tested, callers only within that universe; the runtime contracts
also carry the retired four-helper architecture, D64), the pre-V4 frozen runway clock
(`ng_exhaustion_live_clock.py`, `ng_exhaustion_runway_clock.py`), and the sealed Step-1 universe,
which sits on the SAME hash-locked adapter Frankie's wrapper wraps and whose clock design is the
most developed (`research/ng_exhaustion_mbo_2day_full_mbo_step1_20260825.py`: per-event
`causal_clocks` with `event_known_by_ts_recv_ns` as the receive time of the next confirming record,
`max_contributing_ts_recv_ns`, `feature_cutoff_ts_recv_ns`, `threshold_crossing_ts_recv_ns`, a
post-lock `outcome_availability` clock, the set hashed at :884-891).

### D. The seven clocks, one by one

| clock | producer today | file:line | status |
|---|---|---|---|
| clock_event_time | `member_clock_row` `first_component_ts_event_ns`; receipt `event_time_ns` | `native_clocks.py:199`; `native_causal_stream.py:496` | FULL, needs a naming wrapper by registry id |
| clock_receive_time | `first_component_ts_recv_ns`; the package's `CAUSAL_CLOCK`; ordering invariant | `native_clocks.py:200`; `native_causal_stream.py:467-471` | FULL, naming wrapper |
| clock_event_known_by | `f_last_ts_recv_ns` = `first_lawful_availability_ns`, the cutoff every sidecar row is gated on | `native_clocks.py:201-202`; `native_causal_stream.py:464, 473-474` | FULL at group level; identical by construction to feature availability |
| clock_feature_availability | same field reused; lifecycle rows by declared rule (`lifecycle_availability`, four rules) | `native_clocks.py:202`; `native_causal_stream.py:170-190` | PARTIAL: a basis label at least; the per-component recv list at `native_clocks.py:153` is the ingredient for a real max-of-contributing value (Step-1's pattern) |
| clock_prospective_discovery_confirmation | `CandidateRecognition.record_call` `recognized_recv_ns` | `native_recognition.py:83-100`, reached from `native_replay_driver.py:411, 842` | PARTIAL: lifecycle rows only; same call frame as the cutoff group, so a field copy onto the member row |
| clock_model_evaluation | F_LAST adopted as the decision instant by convention (`decision_basis`) | `native_clocks.py:113-131, 203`; the driver's cadence cutoff dict; `native_staging.REQUIRED_CUTOFF_KEYS` :41-48 | PARTIAL: one key on the cutoff dict, copied unconditionally by `stage_spawn_request` |
| clock_lock_time | none | `a_clean_rt_replay_20260828.py:430-454` carries no time field | NO_PRODUCER_FOUND, correctly: it is his own first-lock entry |

The pre-call and RT-surface gates mandate all seven clock surface ids
(`corrected_a_arm_execution_gate_20260828.py:24-118, 137-195`) while their evidence hash is the
feed-inventory document; once the producers are named, the registry's `source_paths` repoint to
code. The crosswalk's own `SEVEN_CLOCKS` diagnostic (`native_layer_crosswalk.py:679-729`) already
answers this question and has no caller outside its tests.

### E. The fixed windows against the event-anchored measures that exist

`ACTIVITY_WINDOWS_S = (1, 5, 20, 60, 300)` (`ng_exhaustion_mbo_v4_state_adapter_20260820.py:51`,
hash-locked) reaches the row through `native_full_capture_adapter.py:53, 188` and the resume path
`mbo_resume_state.py:19, 300`. All ten native sections are wired in the driver and carry
event-anchored measures: ladder touch migration (`native_ladder.py:129-148`), session open as an
exact instant (`native_session`, `native_replay_driver.py:117-134`), the per-completed-second flow
substrate (`native_flow_substrate.py:181-349`), exact recurrence gaps (`native_recurrence.py:72-177`),
time to restoration (`native_replenishment.py:204-209`), dipole reversals (`native_dipole.py:215-244`),
queue age (`native_queue.py:255-257`), absorption disposition (`native_absorption.py:156-177`),
exhaustion durations only once observed (`native_exhaustion.py:244-256`), book regime snapshots.
`odcore/incremental.RollingFlow` and `odcore/info_dipole` are proven in a sibling strategy stack and
never called from Frankie's path; `RollingFlow` still takes a fixed `window_s`. NOT existing: an
`activity_since` recomposition of the twelve-field activity vocabulary on anchors (zero hits),
`last_book_reset` and `last_f_last_same_side` accumulators, a published elapsed-since-last-trade.
Two of the five proposed anchors (last touch change, session open) already have full producers.

### F. 4.16 and 4.11

`HORIZON_SETS` (`native_response.py:146-166`), `horizons_for_version` (:190-198) consumed at
`native_a_arm_launch.py:59, 455-456` into `native_calculation_runner.py:283-284, 349-352`;
`open_track` / `advance` mature at `first_lawful_recv_ns + horizon` (:546-647). The event-driven half
`observe_change_point` (:649-673) IS wired at `native_replay_driver.py:702-717` and gated OFF by
default (`emit_change_points` False at :335; CLI `native_a_arm_launch.py:386, 600-604`), which is why
the canonical Sunday run produced zero change points. 4.11 has NO ladder: `record_call` computes the
real elapsed time; its real gap is that `precursor_for` (`native_candidate_adapter.py:217-227, 302,
580`) has no caller, so PRIOR is unreachable. `native_clocks.RecognitionLabel` (:53-91) has no
production caller. `WARMUP_SECONDS` in the October shards is on the sealed Step-1 side, not in
Frankie's path: no action.

**Missing to wire:** naming wrappers for three clocks, a basis label and a max-of-contributing
value for the fourth, a same-frame field copy for the fifth, one cutoff-dict key for the sixth; the
seventh is his output. `activity_since` on event anchors in the wrapper and the removal of the
fixed-seconds blocks under D83. Change points on by default and the ladder retired (the packet's
slice c). A caller for `precursor_for` from an existing prebirth-state producer and a caller for
`RecognitionLabel`. Wired by the clocks-and-windows persona.
