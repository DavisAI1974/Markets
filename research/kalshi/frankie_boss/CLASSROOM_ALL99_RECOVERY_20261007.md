# Classroom (stage 5) source report: main_recovery role

Role: `frankie-main-recovery`. Owned files: `deploy/aws/box/frankie_box_classroom_reader.py`,
`frankie_box_classroom_code.py`, `frankie_box_experiment_classroom_v2.py`, `.sh` (and `frankie_box_classroom_staged.py`,
unchanged: it is the Granite-era staged transport, pinned by bytes in `frankie_box_classroom_cache.identity` and not on
the experiment path). The earlier classroom section of 2026-10-07 (commit `5103ed6`) was written into the core author's
`SHARED_MARKET_TIMELINE_20261007.md`; that file is now edited by workflow_reports, so this role's report lives here.

Everything below is SOURCE-BUILT / RUNTIME-UNVERIFIED. Nothing ran. A fresh independent review is required before
integration. Nothing here calls Steps 5-8, all-99 computation, live ingestion or the full historical adviser done.

## 2026-10-07 evening: all-99 routed into the classroom; nothing silent; efficiency; day-quantity agnostic

### 1. The 99 layers combined for Frankie first (Greg's redirect, item 1)

The authoritative registry is the retained crosswalk `audits/CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json`
(bytes 112545, sha256 `ece9c624...`, naming registry content `239a1480...`; pinned in `knowledge/CYCLE_CALCULATION_PINS.json`).
Its 99 `layer_id`s group exactly as the handoff says: 6 raw, 49 calculation/clock, 23 control/knowledge/arm, 9 sealed,
2 disabled shadows, 10 append-only outputs (checked against the file: 99 routed, 0 missing, 0 extra, 0 group mismatches).

Built, `frankie_box_classroom_code.py`:
- `ALL99_REGISTRY`, `ALL99_ROLES`, `ALL99_DISPOSITIONS`, `ALL99_ROUTES`: one route per entry. Route kinds: 51 `picture`
  (the element of `SharedMarketTimeline.iter_pictures()` that carries it, the core layer it depends on, an arrivals
  probe, and a partial carrier when the native producer is absent), 2 `completed` (the per-second aggregates:
  completed-only), 1 `dipole` (the teacher rows: the classroom's own operand), 1 `stamped` (`clock_lock_time` = the
  binding cutoff), 5 `consumer` / 1 `control` / 13 `not_read` / 4 `retired` (the control/knowledge/arm entries reach
  their own consumer here or are named not read / retired; Memory A and A-clean retired by Greg 2026-09-27),
  9 `sealed`, 2 `disabled`, 10 `output` (5 with an analogue output of this piece, pinned at receipt time).
- `_Arrivals` (hot path of the one full pass in `market_context`): per-day counts of what the pictures carried:
  exact clocks, readable records, normalized actions by letter, invalidations by reason (reset / source_scope_changed),
  updates per layer, updates with `known_at_ns`, availability bases, frame sections present (book, activity,
  integrity, native_frame, observation, input_records, input_record_indices), frames with full depth and with FIFO
  queues, price row kinds and origins (V2 provenance), publications, top-level field names seen per layer (capped at
  256 per layer, overflow counted). `market_context` returns them as `arrivals` beside `opening_book` (from the
  ingestion receipt) and `journal_witness` (the core's `input_verification`).
- `all99_coverage(shared, consumers, repo_root)`: reads and witnesses the crosswalk (a byte difference is a visible
  integrity line, never hidden; the route table is this code's own), lists every entry with role, route, registry
  status/policy, consumer and this day's disposition: `arrived` (count), `arrived_no_event` (carrier present, zero
  events over the exhausted source: a measurement, not a filled-in zero), `thin` (named producer absent, partial
  carrier named), `absent` (reason from the core's own layer record), `completed_only`, `stamped`,
  `knowledge_consumer`, `control_of_orchestrator`, `not_read_by_this_piece`, `retired`, `sealed`, `disabled`,
  `output_analogue`, `output_not_produced_here`. Plus `requests` to the core author, `native_layers_absent_or_thin`
  (18 entries are carried only by the native member/lifecycle ledgers, which the experiment ROOT does not produce
  with bedrock off: a plan/policy decision for Greg, never a silent activation), `unrouted_in_file` / `routed_not_in_file`.
- Static evaluation on an empty arrivals record (no run): with frames/prices/structures/external present and native
  absent, 31 `arrived_no_event`, 10 `thin`, 10 `absent`, 2 `completed_only`, 1 `arrived` (Dipole), 1 `stamped`, 5
  `knowledge_consumer`, 1 `control_of_orchestrator`, 4 `retired`, 13 `not_read_by_this_piece`, 9 `sealed`,
  2 `disabled`, 5 + 5 outputs = 99. On a legacy no-policy source every picture-routed entry is `absent` with the reason.

`frankie_box_experiment_classroom_v2.py`: new phase `all99_coverage` (after the shared-market, knowledge and school
phases; consumers = directive and rules witnesses, the ROOT policies, the learner documents/versions/school days and
check counts, the PREVIOUS carry, the binding, the mode, 19 Dipole components). It lands on `receipt.json` as
`all99_coverage` and under `received.all99` (the reporter projects `received` whole, so the inspection markdown shows it
today), in `code-answers.json`, and in the refusal receipt when it was computed before the refusal.

What this does and does not claim: a counted arrival is evidence yielded to the pictures that the component answers
carry untrimmed at their anchors (and to the full reader), not proof that a Dipole equation used it; the Dipole
arithmetic uses the teacher rows only. Sealed answers stay sealed (no timeline path exists; the host key is never read).

### 2. Day-quantity agnostic (item 2)

The owned files carry no day-count literal, no "three days" and no "single day" branch; the only wording was the
docstrings' "for ONE day", meaning one invocation per day. Reworded in `classroom_v2.py` and `.sh`: one day of a run of
any length; the run's day count is the plan's and is never assumed here. Nothing removed because nothing gated.

### 3. Stage 5 row review and the earlier correction (items 1-2 of the original assignment)

Verified on the branch (`5103ed6` plus this pass): lawful partial shared evidence (anchor pictures retained with their
source status, failed/unpaired instants kept, unavailable anchors listed); no fabricated answers or operands; source
exhaustion separate from field/layer coverage (`coverage_disposition`, now also carrying the core's `completeness`,
`outputs`, `input_verification`, `stopped` and `integrity_failure` verbatim); the full ordered reader exposed
(`ClassroomMarketContext.iter_pictures`); untrimmed anchor pictures in every component answer. Standing rules: no
same-day circular teaching (lane_state excludes same-day teacher/school/later-stage entries: `learner_knowledge` lines
321-325, `learner_school` 512-514); immediate brain commit (`brain_publication` phase before the receipt); the lane is
recorded on the receipt (`received.lane`, affinity count against 16; the SOCRATIC/VERIFY walk refuses on a wrong lane);
no Pods; single-occurrence equal treatment in the findings text (R06).

Nothing silent (Greg): `run()` writes `receipt.json` status `failed` (or `refused` for a named `SystemExit` refusal)
with error type, reason, exit code, saved phases, timings and `received` before any uncaught error propagates
(`_failure_receipt`; a complete receipt is never overwritten); a `TeacherSaved` stop writes `phase-progress.json`
`last_event` (also written on every save); the brain-publication rebuild after an interrupted staging entry records the
swallowed error (`outputs.brain_publication.rebuilt_from_interrupted_staging`; phase value `FRANKIE_CLASSROOM_BRAIN_PUBLICATION_V1`,
older saved phases read as before); the day-external receipt absence is said (`s3_key_basis`); the legacy no-policy
fallback is listed (`received.shared_market_disposition`); the teacher-read exhaustion basis is recorded
(`received.teacher_shared_read`); the refusal receipt now pins its package outputs and carries `shared_market_use`.

### 4. Efficiency (item 3), with the AWS list applied

Used (code now):
- The core's retained fast path `input_witness` (eff34d5): the classroom measures the sealed journal once with
  `frankie_box_filehash.witness` (streamed, per-process cache keyed on path/device/inode/size/mtime/ctime) on a daemon
  thread overlapping the cheap identity checks, hands it to the core, and `ClassroomMarketContext.iter_pictures` and the
  SOCRATIC/VERIFY learner walk hit the same cache. Invariants: the core still compares to its pin and raises on a
  mismatch; chained head hash unchanged. Estimated effect from the data shape (Monday journal ~23.7 GB; sha256 at
  roughly 0.5-1.5 GB/s): one journal pass, ~25-100 s, saved per extra reader open and per SOCRATIC/VERIFY day; zero net
  on the first TEACH/GUIDED open (the pass moves to a thread). Recorded: `received.journal_witness` (seconds, overlap).
- Stop-file polling once per second instead of once per picture (`STOP_POLL_SECONDS`; SIGTERM immediate): removes
  ~2-4 million stat syscalls per day on the hot path, ~2-8 s; recorded `received.stop_polling`.
- 16-CPU lane: the core reader keeps `workers=15`; the lane affinity is recorded. Save/resume: the existing phases.
- Cost: this piece spends nothing on the account and makes no account call.
Added cost, said: `_Arrivals.note` on the hot path (a few dict increments per picture, per-update field names):
estimated +1-3 s per 4 million pictures; the pass records its `hot_path` so the one-to-two-minute canary
(`read.seconds`, `read.pictures_seen`, `journal_witness.seconds`) can measure and extrapolate before the day runs.
Rejected, with reasons: S3 byte-range / conditional reads, parallel transfer (the classroom reads owner-local pinned
bytes on the lane: ROOT spools, the sealed journal, teacher rows, the day file beside the ingest; a remote read adds a
transfer and cannot change a pinned identity; transfer belongs to stage 1); S3 Select / Athena over the shared source
(the source is a sealed compact journal with a chained head hash verified as read, plus jsonl spools; SQL over a copy
cannot verify the chain and would be a second read of the source outside the one-owner iterator); S3 Metadata /
Storage Lens (no list/head at scale in this piece). No shortening of the full ordered read: the published guarantee stands.

### 5. Skills and account calls

Skill tool: `api-and-interface-design` (first), `context-engineering`, `experiment-orchestrator`,
`performance-optimization`, `observability-and-instrumentation`. AWS connector (`mcp__Aws__aws___*`):
`search_documentation` (topics agent_skills); `retrieve_skill` `querying-aws-s3`, `aws-storage`, `aws-compute`,
`querying-data-lake`, `aws-billing-and-cost-management`. One account call: `sts GetCallerIdentity`, us-east-1,
read-only (account ending 4170, root); nothing changed in the account.

### 6. Checks

`python3 -I` AST parse without project imports on the three changed `.py` files: ok. `git diff --check` on the four
scoped files: clean. The route table was compared to the pinned crosswalk with a stdlib-only script (no project run).
No tests, no validator framework, no runs, no installs, no dispatch, no Pods.

### 7. Cross-owner requests (file, function, what, why)

1. workflow_reports, `deploy/aws/box/frankie_box_workflow_inspection.py`, `classroom_projection`: project
   `receipt['all99_coverage']` (registry, counts, by_role, entries, requests, decision_open) as its own section; show
   `reason`, `listed`, `saved_phases` when `status` is `failed` (only `refused` is shown today); show
   `phase-progress.json.last_event`. Today the list reaches the markdown through `received.all99`.
2. workflow_reports, `deploy/aws/box/frankie_box_market_timeline.py`, `SharedMarketTimeline.__init__` / `iter_pictures`:
   yield the opening adapter state (opening-book pin, seeded / absent) as an identity element and the initial
   `last_observed_state` disposition (`canonical_predecessor_bootstrap_objects` is read from the ingestion receipt here);
   the per-second aggregates `legacy_native_signed_flow` / `legacy_per_second_roll20` stay completed-only until an exact
   contributing-cursor provenance exists (blocked on provenance, not on the reader).
3. Greg, via the parent: 18 of the 99 are carried only by the native member/lifecycle ledgers, absent with bedrock off
   in the experiment ROOT; producing them is a plan/policy decision, never activated silently by this piece.
4. frankie-ccode-step8, `frankie_box_experiment.py` classroom step: a `receipt.json` with status `failed`/`refused` and
   exit code other than 3 is now written; the Run could carry its `reason` instead of "no completion.json" (low priority).

### 8. Open

Runtime unverified everywhere. The canary measurement of the pass and the witness overlap. The all-99 list is an
account of yielded evidence and consumers, not proof of computation on every field; the native-only 18 wait on Greg.
Fresh independent review (frankie-school-recovery or frankie-ccode-review) required before integration.

## 2026-10-07 night: the classroom INGESTS the 99 (computed / context / absent), the native-only 18

Greg resumed the role (relayed by the parent): "We need to get the other 18 of the 99 in and Frankie needs to ingest
them." SOURCE-BUILT / RUNTIME-UNVERIFIED / UNREVIEWED. Nothing ran. Skills: `api-and-interface-design` (first),
`experiment-orchestrator`. No AWS account call in this pass (the earlier survey stands).

### What changed (owned files only; the ALL99_REGISTRY / ALL99_ROUTES block was not edited)

`deploy/aws/box/frankie_box_classroom_code.py`
- `exhaustion_d_facts(calculations, brain)`: invokes the EXISTING exhaustion/D classroom computation
  `frankie_box_teach.facts` (built 2026-09-21; code only; not invoked on the experiment path since the 09-28 priming
  became text-only). Inputs are checked first: derive.json against the ROOT receipt's derivation pin; the bedrock block
  present and not skipped; the producers checkout (from bedrock.crosswalk) at the pinned commit
  (`frankie_box_bedrock.producers_commit`), loaded with `load_producers`. Outcomes: `computed`, `unavailable` (no native
  pass, missing input, frozen entry absent), `integrity_failure` (pin or digest mismatch, vocabulary outside the pin),
  `failed` (a worker error). Never raises for coverage: only these facts go missing, the Dipole classroom and the day go on.
- `_facts_attribution`: per registry entry, which operand of facts it supplied and how many rows. Sections per entry come
  from `work/native-layer-records.json` when bound to the same derive.json bytes (correction_consumer's file), else from
  the pinned crosswalk. Forms: `own_rows` (lineage / recurrence rows; the clock, family and legacy-structure layer files),
  `section_counts` (the candidate lane reads only the traversal's candidate/episode counts). An operand with zero rows
  is `absent` with the reason, never `computed`. The four frozen learned-structure layers read whole as text are `context`.
- `TEACHER_FORM_COMPONENTS`: the Dipole components that carry an entry's computed form, copied from existing tables
  only (`frankie_box_experiment_teacher.TEACHER_FORMS`, `frankie_box_experiment_search.PLANE_COVERAGE`): roll20/dipole
  state, depletion, resilience, chain trajectory, chain extension, fills, modifies, queue concentration, missingness.
  No new mapping.
- `dipole_operands(visible)`: observations / PRESENT / states per component that the Dipole arithmetic takes today.
- `_classroom_use`: every one of the 99 gets `use` (computed / context / absent), `use_reason` and `computations`
  (computation, form, operands). `all99_coverage` applies it to every entry, returns `use_counts`, `use_vocabulary`,
  `computations`, `native_only_ingestion` (the 18: computation or closest existing consumer, and `searched`) and
  `exhaustion_d` (without the facts body). The shared field rows carry `use` / `use_reason` / `computations`, and
  `canonical`: picture-only entries read `exposed` (not `arrived`), a teacher form or a count reads `thin`, own rows read
  `arrived` (review N4).
- `component_answer(..., exhaustion_d=None)`: on a component that is the teacher form of an entry whose own native rows
  facts computed (the chain columns), the evidence carries those operands and row counts; no relation is claimed.
- `summary_answer(..., exhaustion_d=None)`: the cycle summary carries the facts summary (lineage, ancestry gaps, clocks,
  families, candidate lane, frozen sources) and the pin of the whole facts file, or the reason they were not computed.
- `_NATIVE_ABSENT` and `decision_open` no longer say "bedrock off". The native pass runs by default, so absence means an
  override or an incomplete pass, with the core's reason. The opening route reads the core's `report.opening_state`
  first.

`deploy/aws/box/frankie_box_experiment_classroom_v2.py`
- New phase `exhaustion_d_facts` after the shared market reading (saved/resumed like every phase). Writes
  `exhaustion-d-facts.json` (pinned; listed when not computed). `received.exhaustion_d`, `exhaustion_d` on the receipt,
  the refusal receipt and code-answers.json. The consumers of the all-99 list carry `dipole_operands` and
  `exhaustion_d`. Component and summary answers get `exhaustion_d`. The identity pins `frankie_box_teach.py` and
  `frankie_box_bedrock.py` (`exhaustion_d_code`).

`deploy/aws/box/frankie_box_classroom_reader.py`: unchanged. The SOCRATIC/VERIFY learner walk computes the same
teacher forms on Frankie's own reading, so `dipole_operands` reads the learner evidence in those modes.

### The 18 native-only entries: what ingests each (native pass on, a full day)

| Entry | Computation | Form |
|---|---|---|
| order_lifecycle_fills | Dipole arithmetic on far_absorption_share_64/1024 | teacher_form; native fill_disposition rows: closest consumer named |
| order_lifecycle_clears | none in the classroom (context) | closest: timeline reset invalidation; joined-teacher couplings |
| contract_session_roll_state | none (context) | closest: timeline source_scope_changed; joined-teacher cells session_phase / continuity_segment |
| complete_state_reset_bootstrap_receipts | none (context) | closest: timeline reset invalidation and opening_state |
| depletion_and_replenishment | Dipole arithmetic on far_replenish_* and far_absorption_share_* | teacher_form |
| resilience_and_recovery | Dipole arithmetic on far_identity_survival_* and far_size_retention_* | teacher_form |
| price_and_book_path | none (context) | closest: bedrock_section_4_2 (book-regime companion), the search axis |
| derived_ancestry_gaps | facts: ancestry gaps (recurrence) and D-depth (lineage) | own_rows |
| derived_unresolved_age_chain_trajectory | facts (lineage; episode count) and Dipole arithmetic on the six chain columns | own_rows + teacher_form |
| derived_price_flow_book_paths | none (context) | closest: joined teacher (flow_substrate), the search |
| derived_v4_mechanics_fifo_features | none (context) | closest: the search (V4 frame sections), joined teacher |
| prebirth_predecessor_at_risk_state | facts candidate lane (candidate/episode counts) | section_counts |
| prebirth_unresolved_chain_extension_state | facts (lineage) and Dipole arithmetic on extension_count / step_ratio / pullback_* | own_rows + teacher_form |
| prebirth_ancestry_successor_opportunity | facts (lineage) | own_rows |
| prebirth_stopped_chain_false_context_controls | facts candidate lane (episode count) | section_counts |
| prebirth_negative_opportunity_cases | facts candidate lane (episode count) | section_counts |
| clock_prospective_discovery_confirmation | facts candidate lane (episode/candidate counts); discovery time only | section_counts |
| clock_model_evaluation | facts clock order check (decision_ts_recv_ns, decision_basis) | own_rows; every value null under NeverInvoke, so every group reads unknown (limit carried) |

Searched before naming "none": `frankie_box_bedrock.py`, the pin's bedrock and projection layers,
`native-layer-records.json` / NATIVE_ONLY_*, `frankie_box_teach.py`, TEACHER_FORMS, PLANE_COVERAGE,
`frankie_box_experiment_native.py`, `frankie_box_joined_teacher.py`, `frankie_box_compare.py`,
`frankie_box_digest_render.py`, `dipole_classroom.py`, this module and the reader (`NATIVE_SEARCHED` in the code).
The six with no classroom computation are not wired: that would be a new equation in the classroom. Greg decides.

### Counts over the 99 (by reading the route table; not run)

- A full day with the native pass on, facts computed, the candidate lane fired and learner checks present: 22 computed,
  41 context, 36 absent. The 36 are 9 sealed, 2 disabled, 10 outputs, 4 overlays (Memory A / A-clean), 6 frozen /
  carry-forward entries not read, 3 current-brain entries and the 2 completed-only aggregates.
- The same day without a native pass (override): 11 computed (9 teacher forms + 2 learner checks). The native-only
  entries are thin context or absent with the core's reason.
- An entry whose computed carrier held no row on the day reads absent with the reason. A day without an event of a kind
  reads absent ("no event, a measurement"). Neither rejects the day.

### Efficiency

The facts run its six layer streams in six spawn processes (its own design), after the market pass, inside the day's
16-CPU lane. The phase is saved, so a resume never repeats it. Measured seconds go to `exhaustion_d.seconds` and
`phase_timings` for the one-day canary. Nothing re-reads the journal. Pins, hashes, cursors and event order are untouched.

### Checks

`python3 -I` AST parse on the three .py files: ok. `git diff --check` on the four scoped files: clean.

### Cross-owner requests

1. workflow_reports, `frankie_box_workflow_inspection.py` classroom FIELDS: project `exhaustion_d` (status, reason,
   inputs, attribution, file pin) and `all99_coverage.use_counts` / `native_only_ingestion`. Today they reach the
   markdown through `received.exhaustion_d` and `received.all99`.
2. Owner of `deploy/aws/box/frankie_box_teach.py` (unassigned; the parent): `facts()` refuses as a whole when the brain's
   frozen entry lacks a file for one of its four layers. Under the missing-coverage rule that file should only thin the
   frozen text, not block the lineage/gap/clock arithmetic. Split that requirement out, with no change to the arithmetic.
3. workflow_reports, `frankie_box_experiment_teacher.py`: TEACHER_FORMS could name order_lifecycle_fills,
   order_lifecycle_modifies, queue_concentration and missingness_and_integrity_flags, which the search's PLANE_COVERAGE
   already names. The classroom copies both tables; one shared table would keep them from drifting.
4. Greg (via the parent): whether the six native-only entries with no classroom computation should get one. Each
   entry's closest existing consumer is named.

Fresh independent review (frankie-school-recovery or frankie-ccode-review) required before integration.

## 2026-10-07 night (continued): the 13 external points, facts without frozen files, no same-batch survivor teaching

SOURCE-BUILT / RUNTIME-UNVERIFIED / UNREVIEWED. Nothing ran. The ALL99_REGISTRY / ALL99_ROUTES block was not edited.

### 1. The 13 external points (FRANKIE_DAY_EXTERNAL_V1), tied to the 99

The classroom already ingests the day file through an existing computation: its external section (the
`dipole_classroom_external` key; Frankie's code answers in `frankie_box_classroom_external_code`, transcribed in TEACH,
computed in GUIDED, on the learner-owned reading in SOCRATIC/VERIFY). For each series it computes values known at the
cutoff, first/last/extremes, state counts over the Dipole rows, terminal state and direction. For each pair against the
19 Dipole columns and every other series it computes the relation, Pearson with its overlap and the co-movement counts.
Each Dipole row takes the latest value stamped at or before its own ts_recv_ns. A later stamp is a hard AsOfViolation, and
a value published after the cutoff is never read.

New in `frankie_box_classroom_code.py`: `external_points_use(ext_ledgers, day_file, day_file_sha256, cutoff_ns=)`
(FRANKIE_CLASSROOM_EXTERNAL_POINTS_USE_V1). For each point it records:
- `use`, with the series that entered the arithmetic and their PRESENT row counts. `computed` means a value was
  published at or before a Dipole row. `context` is point 12: no numeric series, captures carried whole. `absent` covers
  no published value, no series, Greg's deferral (point 6 and the front-next spread) or an integrity finding.
- The 99 entries the day file declares the point feeds, with the mapping basis (exact / closest), its reason, the event
  time basis and the note ("this is not a time-specific event"). These come through workflow_reports' contract
  `frankie_box_all99_coverage.external_point_mapping`. No mapping is invented here. A point with no declaration is listed
  `unmapped`, as a request to the day-file agent.
- `placement`. A readable row whose reader stamp is EARLIER than its declared event time (Greg: 14:00 ET of its trading
  day, or its publication time when later) would let the arithmetic read it before Greg's placement. Such a point reads
  `absent` with an integrity reason and a finding, never `computed`.

The all-99 list now adds `external_section_arithmetic` to each entry a computed point feeds: own_rows for an exact
mapping, external_closest (thin) for a closest one. The list returns `external_points`.
`frankie_box_experiment_classroom_v2.py`: new saved phase `external_points` after the external answers. The
`all99_coverage` phase now runs after every answer. A refusal still writes the list.

Per point, when its value is published at or before the window's rows: 1, 3, 4 (COT net pctile 1y, weekly change, 3y),
2 (MOS forecast gw_hdd), 5 (EIA-930 wind), 7 (estimated gas burn), 8 (ICE LD1 pctile), 9 (MOS spread), 10 (observed
gw_hdd and station temperatures), 11 (EIA storage) and 13 (curve shape) are computed. 12 (storage estimate vs actual) is
context. 6 (squeeze) is absent, deferred by Greg. Today the day file's builder declares no entries, so every point reads
unmapped until the day-file agent's declarations land.

### 2. `frankie_box_teach.facts`: a missing frozen file drops only its text

`facts()` no longer refuses when the brain's frozen entry lacks a file for one of the four layers. A file not named or
not present is listed in `frozen_missing`. A file whose bytes differ from the manifest digest, or a name outside the
frozen directory, is listed in `frozen_integrity` and its text is not used. The lineage, gap, clock, family and
candidate-lane arithmetic still computes; it never read those files. With every file present and matching, the returned
dict and `facts_text` are byte-identical (both keys and their text lines are added only when non-empty). It still refuses
when there is no bedrock. The classroom carries both lists in its facts summary and attribution (`absent`, with the
reason).

### 3. `frankie_box_lane_state.learner_knowledge`: no same-batch survivor teaching

A FRANKIE_SURVIVOR_UPDATE_V1 document is withheld from every day listed in its `boundary.batch_days`, not only the
boundary day, whatever the stage. It is listed (disposition `withheld_same_batch`, with boundary, batch_days and the
reason) in the selection's `listed`. That list lands on the classroom receipt (`stage_knowledge.selection_listed`,
learner-knowledge.json), the exchange receipt and the teacher-knowledge receipt. ccode_step8's per-document ValueError
handling (listed, not raised) is unchanged.

### Checks

`python3 -I` AST parse on the five .py files (classroom_code, classroom_v2, classroom_reader, teach, lane_state): ok.
`git diff --check` on them and the .sh: clean.

### Cross-owner requests

1. Day-file agent (`operations/frankie_day_external.py`, `frankie_box_day_external.py`): declare each point's 99 entry
   and mapping basis under `external_point_mapping`'s keys. Make the reader stamp of a non-time-specific row its event
   time (14:00 ET, or its publication when later): `stamp_column`, or `published_ns` as handed out by `AsOfReader`. The
   external section aligns on that stamp. Until then, a point whose stamp precedes its event time reads absent
   (integrity), not computed.
2. Owner of `frankie_box_granite_meeting.py` (the voice path, about line 1429): it calls `learner_knowledge(..., 'voice')`
   and keeps only `documents`. Record `selected['listed']` on its receipt so the same-batch survivor exclusion is visible
   there, as the exchange and teacher-knowledge already do.

## 2026-10-07 night, session 2: 18 of 18 (the six context entries computed)

Greg (relayed): "Why is he only reading 12 of 18? We want 18 of 18." Settles open call 5(a). SOURCE-BUILT /
RUNTIME-UNVERIFIED / UNREVIEWED. Nothing ran. No AWS call. Skills: `api-and-interface-design` (first),
`context-engineering`, `experiment-orchestrator`, `incremental-implementation`.

### The computation: `native_entry_arithmetic` (FRANKIE_CLASSROOM_NATIVE_ENTRY_ARITHMETIC_V1)

No new equation. The operands are the native producers' own per-group values; the equations are the classroom's
existing external-section arithmetic (`dipole_classroom_external`: value in force per Dipole row, `_direction`, `_pair`).
- Where: inside the classroom's own one full ordered pass (`market_context`), class `_NativeEntryArithmetic`. The shared
  reader already yields every native member row (and lifecycle row) at its GROUP_CLOSE emission cursor; `note()` takes
  the six entries' carrier fields there, in source order. No extra file pass, no re-sort.
- Member rows: the entry's carrier heads (the core's `native_carriers`, i.e. the ROOT projection plan's crosswalk, else
  `frankie_box_all99_coverage.NATIVE_SERIES`), flattened by the joined teacher's leaf rule (`frankie_box_joined_teacher._flatten`:
  mapping by dotted key, number/boolean kept, string = category, list = its length). Per instrument (never pooled).
- Lifecycle rows of the entry's sections (ladder, flow_substrate, queue): rows counted per Dipole interval (the joined
  teacher's count-of-rows-in-the-window form); their fields stay in the pictures.
- INPUT-envelope carriers (every day, native pass or not; form `thin_carrier`): R actions per Dipole interval
  (clears, reset receipts); (source_member_index, session_id) changes per Dipole interval and session_id /
  source_member_index as categories (contract/session roll).
- Per numeric series: value in force at each Dipole row (from its own cursor on, never backfilled; a leaf missing from
  the instrument's latest member row reads MISSING; rows carried forward counted apart from rows with an update), state
  counts, terminal state, first-to-last direction, facts (first/last/lowest/highest with cursors), and against each of the
  19 Dipole components: relation, Pearson over both-PRESENT rows, co-movement counts. Per category: runs over the
  Dipole rows and per value a cell with each component's rows, PRESENT count and direction inside the cell
  (identifiers above the joined teacher's CATEGORY_LIMIT get runs only).

| Entry | Own rows (native present) | Thin carrier (every day) |
|---|---|---|
| order_lifecycle_clears | capture_observations, integrity_delta, raw_actions (#len) | picture.reset_inputs |
| contract_session_roll_state | session_phase, continuity_segment, raw_symbol (categories), instrument_id | picture.session_scope_changes, picture.at.session_id, picture.at.source_member_index |
| complete_state_reset_bootstrap_receipts | integrity_delta, capture_observations, snapshot_bootstrap_only | picture.reset_inputs |
| price_and_book_path | book_full, book_regime, structure.price_raw_min/max/span; lifecycle ladder count | none |
| derived_price_flow_book_paths | book_regime, book_full; lifecycle flow_substrate and ladder counts | none |
| derived_v4_mechanics_fifo_features | activity_full, activity_since, book_full, capture_observations; lifecycle queue count | none |

Use record: each of the six reads `computed` with computation `native_entry_arithmetic`, form `own_rows` or
`thin_carrier`, its series and pair counts, relation counts and the unavailable carriers with reasons. Missing
operands: native ledger absent, no Dipole row, an integrity finding (adapter cursor backwards, Dipole rosters differ)
or a failure each block only this computation, named; the instant and the day stay. Integrity stays `integrity_failure`.

Limits said in the record: a list carrier (FIFO queues, levels, raw actions) enters as its length, not entry by entry;
lifecycle rows enter as counts; numbers are float64 in the arithmetic (an integer above 2**53 is not exact there);
descriptive only, no outcome, no fees, no P&L.

Outputs: `native-entry-arithmetic.json` (every series, pair and cell; pinned in outputs), `received.native_entries`,
`receipt.native_entries`, the refusal receipt and code-answers.json (compact + pin), the all-99 list
(`native_entries`, per-entry computations), the summary answer (per-entry counts + pin) and each component answer
(per-entry relation counts against that component). Timing: `native_entries.hot_path_seconds` (inside the pass) and
`native_entries.seconds` (pairs after it), for the one-day canary. Identity pins `frankie_box_joined_teacher.py`
(`native_entry_code`).

Requests: workflow_reports, `frankie_box_workflow_inspection.py` classroom FIELDS: project `native_entries` (status,
reason, per-entry use/form/series/pairs/unavailable, file pin, timings); today it reaches the markdown via `received`.

Fresh independent review (frankie-school-recovery or frankie-ccode-review) required before integration.
