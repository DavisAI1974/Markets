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
