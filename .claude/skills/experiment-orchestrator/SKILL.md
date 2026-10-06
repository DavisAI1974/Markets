---
name: experiment-orchestrator
description: Canonical runbook for the Frankie 30-day experiment: retained ingest -> ROOT -> BOSS teacher -> Frankie classroom on arm days -> data/search -> scientific-teacher evidence -> meeting/end -> Jev, with immediate brain updates, 16-CPU held day lanes, survivor batches and later frozen confirmation.
---

# Experiment orchestrator

Greg: "a stripped down version of today's run." Its own workflow, calling ONLY the pieces of the
full run the experiment needs (reused, never copied), with a new search engine attached behind
it. Frankie's cycle (context, teacher, principal, Granite, classroom) is NOT called, except the
teacher and the code classroom on the three classroom-arm days. Everything is code on the box's CPUs.

**As of 2026-09-29 (late) - read before anything below:**
- **Granite is decoupled.** It is ONLY the full run's B2 shadow critic (C21-C24) on the Pod, plus one
  labelled self-assessment (`SPEC-decouple-granite.md`, DECISION + BUILT). **The experiment makes no
  Granite call anywhere**: not in the search, not over the survivors, not in the classroom arm. The
  classroom is Frankie's code (`deploy/aws/box/frankie_box_classroom_code.py`) under the confirmed
  rules file `research/kalshi/frankie_boss/knowledge/CLASSROOM_RULES_V1.json` (R01-R17; R17 = no model
  voice in the classroom).
- **The teachers are tied** (`SPEC-scientific-teacher.md`, confirmed): three seats, none a model -
  Frankie (learner, his findings are claims, R11), the BOSS teacher (JournalTeacherR3 + classroom
  package + teacher key), and the **scientific teacher = this experiment's search** (its
  classroom-facing side: claim -> tests -> counts, challenges worded "the data is showing this
  instead" (R07), untested combinations listed). The two teachers keep separate roles (R12) and never
  see Frankie's decision process or graded outcomes (R09, R10). Reuse `dipole_teacher_discussion.py`
  and `dipole_scientific_review.py` schemas (a turn becomes a test result, not a model prompt); swap
  out `frankie_box_scientific_dialogue.py` (it sends turns to Granite). Until the search exists the
  tied teachers stay unwired (`classroom_scientific_dialogue: false`).

**Source of truth: `research/kalshi/frankie_boss/SPEC-experiment-orchestrator.md`** on the active run branch. The
canonical workflow was reconciled 2026-10-06. Older September tables below are provenance only when they conflict with
the canonical section. If code disagrees with the canonical spec, fix the code rather than silently following stale text.

**Shared mechanics live in `full-run-orchestrator`**: HOLD/go per step, dispatch through
`frankie_box_run.yml`, stage-then-no-push, probes, receipts-not-green-checks, `[skip ci]`,
the never-bend rules. Read its sections 0, 3, 5 and 7 first. They all apply here.

## 0. CANONICAL 30-DAY WORKFLOW (reconciled 2026-10-06)

Greg's execution rule: **one real ROOT-to-finish end-to-end run, then fix actual failures. Do not build a validator,
canary or test framework for this workflow.**

### Immediate brain rule

Frankie runs with the newest knowledge as soon as it exists. A knowledge-producing stage is not complete until its
new knowledge is durably filed into Frankie's brain and is available to later applicable stages. Do **not** wait for
the end-of-day school/retention step.

This means:
- ROOT calculation findings -> brain immediately after ROOT.
- BOSS-teacher measured knowledge -> brain immediately after the teacher read, before Frankie classroom.
- Frankie classroom findings/corrections -> brain immediately when classroom completes (already built).
- Search/coupling discoveries -> brain immediately after the causal search.
- Scientific-teacher tests of Frankie's claims -> brain immediately (already built as <day>-lessons).
- Three-way exchange/teachers' findings -> brain immediately (already built as <day>-exchange).
- Jev remains blind only until his own claims are sealed. Once his claims are tested, the resulting tested knowledge
  may enter Frankie's brain immediately; independence is not a reason to keep useful knowledge from Frankie afterward.
- Survivor/candidate updates and confirmation findings -> brain immediately when those cross-day stages produce them.

Packaging/movement steps (fetch transfer, data export, manifests) do not manufacture a fake lesson. Their exact
evidence remains reachable by path/hash. Causal/future leakage walls remain hard: "latest knowledge" means latest
**legally available** knowledge, never future information.

### Lane rule

A day that enters ROOT owns one 16-CPU booking until its last applicable stage finishes. The stage changes; the box,
CPU affinity, worker allocation, work directory, cache/state and receipts stay with the day. Existing
`frankie_box_cores.py` is authoritative: 16 CPUs, 15 worker CPUs plus the parent/coordinator CPU, no double booking.

### Execution order

1. Existing sealed ingest + receipt (fetch/ingest only when genuinely missing; never redo a finished ingest).
2. Day file, causally stamped and shared by permitted readers.
3. ROOT (bedrock/model calls off) -> immediate ROOT brain commit.
4. BOSS teacher whole-journal read -> immediate teacher-knowledge brain commit.
5. **Frankie classroom immediately after BOSS teacher** on classroom-arm discovery days -> immediate classroom brain commit.
6. Data export (packaging of already-computed evidence).
7. Causal series + search -> immediate search-knowledge brain commit. **The scientific teacher owns the search/evidence role.**
8. Scientific teacher tests historical/prior claims and then today's new Frankie findings -> immediate lessons brain commit.
9. Survivor/candidate update at a cross-day/batch boundary; not a per-day lane blocker -> immediate survivor brain commit.
10. Three-way meeting: Frankie + BOSS teacher + scientific teacher; Granite may only voice their code-generated turns ->
    immediate exchange brain commit.
11. Frankie end-of-day school/report synthesis. This is a consolidation of knowledge already written during the day,
    not the first time Frankie learns it.
12. Jev blind comparison on classroom-arm discovery days. After Jev's claims are sealed/tested, tested Jev knowledge
    may enter Frankie immediately.
13. After discovery is complete, freeze survivors once.
14. Only then run untouched 2024-2025 confirmation days against the frozen list, per cell and net of maker/taker costs;
    confirmation findings enter the brain after each completed confirmation calculation without changing the frozen list.

Non-classroom discovery days run ROOT -> BOSS teacher -> data/search -> scientific-teacher carried-claim work and skip
the classroom/meeting/school/Jev pieces.

Cross-day rules:
- A classroom may consume only survivor material completed before that classroom; no same-day circular promotion.
- Jev's claims are labelled hypotheses; the blind wall ends only after his own claims are sealed.
- Confirmation stays untouched until the survivor freeze.
- Every retained record/field in scope must reach computation. The current search is only a first slice and is not the
  scientifically complete endpoint.

Current implementation:
- Built/reuse: orchestrator, CPU ledger, held slots on main, FIFO ROOT/class queues, receipts/resume, ROOT, teacher,
  classroom, data export, first-slice search, scientific teacher, exchange, school/reports and Jev relay.
- Immediate brain already built: classroom, Frankie's scientific-teacher lessons, exchange, school synthesis.
- Missing immediate brain glue: ROOT, BOSS teacher, search, tested Jev results, future survivor/confirmation outputs.
- Incomplete science/runtime: full search surface, survivor production/freeze, confirmation, Granite voice transport,
  and the remote Linux worker's ROOT-to-finish path (its agent is still ROOT-only).

The September 29 build-status material below is retained for provenance. Do not use stale "NOT built" labels as
present-tense execution authority.

### Granite decision still open (2026-10-06)

Do not treat an older Granite role as final for the 30-day workflow yet. The repo contains both the September 29
critic/self-assessment design (`SPEC-decouple-granite.md`) and the later post-class voice/coordinator charter
(`knowledge/GRANITE_DISCUSSION_VOICE_ROLE_V1.md`). Greg will settle Granite's final experiment role before the workflow
is declared launch-ready. Until then Granite performs no calculation, search, grading, survivor selection or trading
decision in this experiment.


## 1. Historical pipeline/build inventory (September 29; provenance, not current execution authority)

| # | Step | Piece | Status |
|---|---|---|---|
| 1 | fetch | `frankie_box_ingest_block.sh ACTION=fetch MANIFEST=...` (presigned map, sha256 + size verified) | built (full run's) |
| 2 | ingest | `frankie_box_ingest_block.sh ACTION=canary\|ingest\|status` - sealed compact journal + receipt | built (full run's) |
| 3 | ROOT | the calculations root (`frankie_box_monday_calculations.py`) WITHOUT bedrock: `derive.json`, 5 legacy layers, row spools `work/derived/.rows/*.jsonl` (every INPUT record decoded), pin, source binding, receipt (Greg: "we forgot root in the experiment") | **switch built 2026-09-29, not run**: `Session.derive(bedrock=False, digest=False)`, `frankie_box_monday_calculations.sh BEDROCK=off DIGEST=off` skip ROOT processes 2+3 (traversal, projection) and 4 (digest); skipped layers recorded `not_derived` with the reason; the receipt's `root_processes` / `not_run` say what ran. For any other day: `frankie_box_experiment_root.sh INGESTION_RECEIPT INGESTION_RECEIPT_SHA256 DAY DAY_ROLE OUTPUT_ROOT [DIGEST=on for a classroom-arm day]` (built 2026-09-29, not run): the day's sealed ingest read in place (journal bytes + sha256 checked against the receipt), the same whole-day pin (shared `whole_day_pin_document`), `derive` with bedrock off, no authorship; output under `/opt/frankie-box/work/experiment-roots/`; confirmation days refused without a frozen survivor list. A bedrock-off receipt carries no bedrock result/ledgers, so the principal-inputs step (full run only) must not read one |
| 4 | export (day data) | `frankie_box_experiment_data.sh ACTION=plan\|export DAY CYCLE CALCULATIONS [PREPARATION PRINCIPAL_INPUTS HOST_CONFIG RUN]`: every data JSON of the day from ROOT, CONFIG and CYCLE, hard-linked under `/opt/frankie-box/work/experiment-data/<day>/cycle-<NN>/`; MANIFEST lists files, excluded (R09, R10, bedrock, mixed, other models, each with reason), missing, unclaimed. The older calc-only export (`frankie_box_export_calcs.sh`, also from `brain_entry()`) remains and no longer leaks the two bedrock section files | **built 2026-09-29, not run** |
| - | orchestrator | `frankie_box_experiment.py` + `frankie_experiment.yml` (`ACTION=start\|status\|stop`) | **NOT built** |
| 5 | series | one causal axis per day (F_LAST group closes, running-max receive time) from the exported day data: ROOT frame/structure/trade spools (decoded by the journal's codec, never re-derived) + per-second signed flow and roll20 (second s known at s+1), placed by DuckDB ASOF; leakage gate (odcore) on each source's REAL alignment | **first slice built 2026-09-29, not run** (`frankie_box_experiment_search.py`) |
| 6 | search | first slice: sign-of-step couplings, every ordered pair x cell x lag -L..L, the joined teacher's statistic + circular-shift chance check, counts per pair/cell/lag/day; workers share the arrays by fork; parts under `experiment-search/<day>/cycle-<NN>/<role>/couplings/`. Transforms (2026-09-29, `frankie_box_experiment_transforms.py`): sign_of_step, run_length, magnitude_class, level_crossing, acceleration (causal, running lower medians, no caps); pairs = x under T vs y under T, and x under T vs y's sign_of_step; rows carry x_transform / y_transform; `TRANSFORMS=` picks a subset. Listed as NOT yet searched (in the MANIFEST): the INPUT spool's per-event fields, other transform pairs, conditions, targets | **first slice built, not run**: `frankie_box_experiment_search.sh DAY CYCLE DAY_ROLE [LAGS WORKERS FROZEN_SURVIVORS]` on the `box-experiment-*` lock; needs `frankie_box_venv_duckdb.sh ACTION=install` first (box change, Greg's go) |
| 6b | scientific teacher | the search's classroom-facing turn: claims (Frankie's, labelled) -> tests -> counts + challenges + untested combinations, tied to the BOSS teacher | **built 2026-09-29, not run**: `frankie_box_scientific_teacher.sh SEARCHES=<discovery-day search dirs> [JEV_STAMP] [FRANKIE_LEDGERS FRANKIE_DAY] [HISTORICAL_CLAIMS=research/kalshi/frankie_boss/knowledge/HISTORICAL_CLAIMS_V1-9b2ca9849e4f.json]` (box-experiment lock). Marks only rows on the claim's own transform pair (others `counts_only`); a claim's condition is listed as untested. Historical claims (`frankie_box_historical_claims.py`, committed output): the Dipole catalog's 127 sources read at their revisions (sha256 checked, 0 unreadable), 4,806 candidate statements enumerated, 10 turned into testable claims by a declared, anchored crosswalk (H01-H10: info-dipole divergence/exhaustion, the NG brain's flow nowcast and book contrarian, Memory A's withdrawal/accumulation strata and absorption, far-side thinning as noise), every other candidate listed not_testable with its reason; HISTORICAL_LESSONS_V1 kept under experiment-teacher/historical/, into nobody's brain. Reads Jev's JEV_CLAIMS_V1 and ONLY Frankie's novel findings (R09); matches claim series to search series; per day: counts, held / shown_otherwise / unresolved, the challenge "the data is showing this instead", untested and cannot-test-yet listed; writes JEV_LESSONS_V1 (uploaded to Jev's brain) and FRANKIE_LESSONS_V1. Until the teacher's Dipole measurements are a search source, Dipole-component claims come back "not in the search" |
| 7 | survivors | symbolic regression (`odcore/symbolic.py`); no Granite pass, no model | NOT built |
| J | Jev | blind outside student (Qwen3-8B, his own Pod, classroom-arm days only): files labelled CLAIMS the search tests; never sees Frankie's answers first, never in the classroom | **built 2026-09-29, not run**: `clm_sidecar/sit_in.py`, `frankie_box_jev_relay.sh ACTION=material\|frankie`, `launch.py --jev`, `frankie_box_jev_pod.sh`, his brain on S3 `clm-sidecar/jev-brain/` (entries + the teacher's lessons, read whole on his next day; never Frankie's answers) (spec section "Jev"; dispatch order in `clm_sidecar/README.md`) |
| 8 | confirmation | frozen survivor list on confirmation days, per cell, net of fees maker AND taker | NOT built |
| C | classroom arm | teacher + `prepare_integrated_cycle` + the principal's classroom stage answered by Frankie's code (no Granite) + the scientific teacher's turn (6b) | reuses the full run; waits on r10 showing the code classroom end to end |

## 2. Build order - each step on Greg's go

1. **Greg adds the track to the Excel build plan** (`artifacts/Frankie_BOSS_Build_Plan_R4_20260921.xlsx`),
   with the scientific teacher and the rules file, BEFORE anything is built. Unplanned = unwired.
2. `bedrock=False` switch in the derive stage. Frankie's cycle keeps its bedrock, so the default stays unchanged.
3. Orchestrator for steps 1-4, first on Tue 2021-10-05 and Wed 2021-10-06, plus the Monday export.
4. Series + search (5-6), attached to the orchestrator.
5. The scientific teacher's turn on the search (6b); the tied teachers switch on.
6. Survivors + confirmation (7-8).
7. Jev (J), after Greg adds him to the build plan.
8. Classroom arm (after r10 runs the code classroom end to end).

## 3. What can be dispatched today (each on Greg's go)

- **Monday calc export** (read-only on the root, no model call, hard links so no extra disk):
  `frankie_box_export_calcs.sh CODE_ROOT=<staged> WORK=/opt/frankie-box/work/monday-calculations/<root>/work DAY=20211004 CYCLE=00`
  -> `/opt/frankie-box/work/experiment-calcs/20211004/cycle-00/` + MANIFEST (bytes, sha256).
  Take `<root>` from the current drop-in (as of 2026-09-29 `full-20211004-20260927-r1-48`).
- **Tue/Wed fetch/ingest**: the committed manifest is
  `research/kalshi/frankie_boss/blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json`.
  **It includes Monday 20211004, whose ingest is the gold standard and is never rebuilt.** Before
  any `ACTION=ingest` on it, confirm with Greg whether it re-ingests Monday. The likely answer
  is a Tue/Wed-only manifest. `ACTION=status` is read-only and safe.
- **Tue/Wed calculations: not dispatchable as-is.** `frankie_box_monday_calculations.sh` demands
  a Monday `AUTHORSHIP` receipt. Adapting it is part of build step 3.

- **Monday day data** (built 2026-09-29): `frankie_box_experiment_data.sh ACTION=plan` first (read-only: what would
  be linked, excluded, missing, unclaimed), then `ACTION=export`, with `DAY=20211004 CYCLE=00
  CALCULATIONS=/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48` plus whichever of
  INGEST (as of 2026-09-29 `/opt/frankie-box/work/ingest-20211004-ingest-1790057801`), LAUNCH (authorship,
  `/opt/frankie-box/work/monday-launch/full-20211004-20260923-r4`), PREPARATION / PRINCIPAL_INPUTS / HOST_CONFIG / RUN
  exist (ONE run directory; runs are never merged). The five processes before the cycle, in order: ingest,
  authorship, ROOT calculations, trading-day preparation, principal inputs (+ host config). Hard links, so
  the root and the export must be on the same filesystem (the script refuses rather than copy).

## 4. Walls that never bend (experiment-specific)

- **Day classes never mix; every day is reported on its own.** Midweek Tue/Wed first; Thursday
  (EIA print) is its own class, later; Monday its own class.
- **Discovery = October days of 2021-2023. Confirmation = October days of 2024-2025.** Then widen
  to every year, reported per season. Confirmation days stay UNTOUCHED by the search, the teacher
  and Frankie until the survivor list is frozen. Never fetch-and-peek, never "just check one".
- **Classroom arm: days 1 and 2 of every five discovery days** (Greg, 2026-09-29, revised: on 1-2, off 3-5, repeat;
  he may go to all five if their part is quick). Orchestrator `--classroom-arm-cycle 2/5` (default). Never on a
  confirmation day (R15). The classroom itself is code and the launch is not called: no critic, no Granite. The only Pod
  on these days is Jev's own.
- **The loop (three seats)**: search survivors go to the BOSS teacher and the classroom as material.
  Frankie's findings come back as HYPOTHESES (claims, never truth, R11); the search, as the
  scientific teacher, tests them across every discovery day with the chance check and hands back
  counts; the BOSS teacher answers within its own role (R12). A survivor is reported as a scoped
  finding with its days named.
- **Jev (Greg, 2026-09-29: "yes, include him")**: the blind outside student, NOT a classroom seat
  (R17 stands). Qwen3-8B on his own Pod, classroom-arm days only. Sees what Frankie sees (classroom
  package + survivors), never Frankie's answers before filing his own. Files labelled CLAIMS only;
  the search tests them like Frankie's and reports counts with his name and the days. Never touches
  Frankie's session, the teachers, grading or confirmation days. Keeps his seat by counts: his
  surviving claims per day beside Frankie's; no better than chance and he comes out.
- **Every test gets its own circular-shift chance check. The finding is COUNTS, never an average**
  (D37; an R2, a pooled correlation or a fitted slope is an average - use `per_event.py`).
  Coefficients are kept where they are read per pair/cell/day with their overlap count (Greg: "We
  want the coefficients, just not a bunch of dipole results flattened or normalized"); never pooled.
- **Leakage gate (`odcore/leakage.py`) on every target.** Every series row carries only what was
  knowable at that moment (causal clocks).
- **Zero data dropped**: every event, every book level, fills, FIFO, and unknown-side trades carried.
- **Source**: the 5-year NG MBO pull on S3 (`nymex/ng_mbo_5y_v0`). **List it to confirm coverage
  before assigning days.** Nothing here charges Databento.

## 5. How the orchestrator runs (BUILT 2026-09-29, not run: `frankie_box_experiment.py` + `.sh`)

- `frankie_box_experiment.sh ACTION=plan|start|status RUN=<name> DAYS=<list> DAY_CLASS=<class> [CLASSROOM_ARM PLAN
  FROZEN_SURVIVORS HISTORICAL_CLAIMS WITHOUT_DIPOLE STAGES LAGS TRANSFORMS *_WORKERS PARALLEL_DAYS DISK_FLOOR_GB MAP_URL]`.
  `ACTION=plan` is read-only (what each day and step would do). Stages in fixed order: fetch, ingest, root, teacher,
  data, search, lessons. Fetch is its own dispatch (`STAGES=fetch`, presigned partitions) while the URLs are live.
- NO DATA DROPPED (Greg, 2026-09-29): a gap skips over the calculation that needs it, never the day or the run. A day
  with no committed per-day manifest (`blocks/BLOCK_<day>_SOURCE_MANIFEST.json`, trading_day = the day) and no sealed
  ingest stays in the run, its steps WAIT (listed); no Dipole rows -> exported and searched without them (listed);
  ROOT producer failures -> `calculations_retained_with_failures` (listed), the day goes on.
- Only rule breaks refuse the plan (a day listed twice, a malformed day). A day of another class, outside October
  2021-2025, or an unfrozen confirmation day is LEFT OUT of that run with its reasons.
- Per-day manifests: 20211003, 20211004, and (2026-09-29, tail take) 20211005 and 20211006. A midweek day opens at the
  prior halt: its manifest has a `tail_members` entry. Its ingest opens with the prior day's closing book when given
  `OPENING_RECEIPT` (`opening_book.py`; Monday's = `/opt/frankie-box/work/sealed-recovery-35796793428/recovery-receipt.json`),
  and otherwise WARMS its own book from the tail partition (its 00:00Z snapshot to the halt, book only, not journaled):
  no Monday ingest is needed. The opening book is written beside the journal (`opening-book.c15.json`) and the ROOT
  replays the day onto it. `frankie_box_ingest_block.sh ACTION=ingest` takes a
  comma list of manifests (Tue,Wed: each its own journal, each opening from the one before). Handoff section "Later
  still: Tuesday and Wednesday built".
- Monday 20211004 is never re-ingested; two sealed ingests or two finished ROOTs of one day decline (duplicate data):
  name the one to use in a PLAN file (`{"class": "monday", "days": [{"day": "20211004", "ingest": ..., "calculations":
  ..., "run": ...}]}`).
- Teacher batches of 5 per role; data and search wait on the batch (1 day in 5); lessons after each discovery batch.
  While `frankie_box_experiment_teacher.sh` is not built the batch records `not_built` and its days are exported and
  searched without Dipole rows (listed missing in the receipts).

- **Frankie's FIFO queue (built 2026-09-29, not run: `frankie_box_frankie_queue.py` + `.sh`).** Two arrival-order lines
  under `/opt/frankie-box/work/frankie-queue/` (enqueued_at then a monotonic seq; nothing dropped, skipped or reordered):
  the ROOT line (`ROOT_QUEUE=on`, default: a day enters when its sealed ingest + day file are there, leaves in arrival
  order to the next free day-run slot, box or Pod via the root claims; Pod claims are gated by `root_gate`) and the CLASS
  line (`FRANKIE_QUEUE=on`, default: an arm day enters when ROOT + teacher rows + day file are there; ONE class at a time;
  class k carries class k-1; school day = position in the line = report number N). Workers are kicked by every
  orchestrator start and every enqueue (detached, bounded, one per line) and poll a waiting day instead of ending.
  Probe: `frankie_box_frankie_queue.sh ACTION=show` (box-progress lock). Dispatches: `ACTION=enqueue LINE RUN DAY`,
  `ACTION=worker LINE [MAX_SECONDS]`, `ACTION=kick LINE` (each its own concurrency group). Open for Greg: the school
  knowledge base still reads earlier school days by TRADING DATE (`school_rows before_day`), while PREVIOUS follows the
  class line (flagged `previous_trade_date_later`). A box slot = 16 CPUs free in the CPU ledger (`box_slots` reads
  `frankie_box_cores.usage`; the ROOT step books them itself; a step that cannot book waits and keeps its place).
- One dispatch starts `frankie_box_experiment.py` on its own lock `box-experiment-*`, so it runs
  beside Frankie's runs and never queues behind them.
- Per-day, per-step receipt in `/opt/frankie-box/work/experiment/<run>/`. A restart skips finished
  steps. Save progress on every stop, and stop-and-save at a disk floor.
- Days run in parallel across CPUs where steps allow; the ingest's causal parent stays one per day.
- **CPU booking (Greg, 2026-09-29: "Correct 16 and no double booking")**: every day-run step books EXACTLY 16 CPUs in
  `/opt/frankie-box/cpu-bookings/` (`frankie_box_cores.py`) and runs under `taskset -c` of them with 15 workers; fewer
  than 16 free = the step records `waiting: N free of 16 needed` and a later start retries. Each ingest day process
  books 8 (inline verify needs WORKERS x 2 + 1, deferred WORKERS + 1; above 8 is refused). On a 32-CPU box that is two
  day-run steps at once, so `PARALLEL_DAYS=2` avoids planned waits. Probe: `frankie_box_cores.sh ACTION=show`.
- Workflow inputs: day list, class, discovery/confirmation assignment, stage range.
- Probe every run: `frankie_box_progress.sh DIRECTORY=/opt/frankie-box/work/experiment/<run>`.
- **Disk: measure the first day's bytes (journal + calc JSON) and extrapolate before queueing
  many days.** The Monday journal alone is ~23.7 GB.
- For quick data checks off the box, DuckDB is in the session setup script (SQL over gz
  JSON/CSV/Parquet, including on S3 with credentials).

## 6. Open / contradictory - ask Greg, do not resolve

- **END-OF-BUILD CODE INSPECTION (Greg, 2026-09-29: "We'll do all that at the end").** Code on this branch was changed
  during runs to relaunch or to do truncated runs. Before any result from the experiment or the full run is trusted,
  inspect all of it for leftovers of that: caps, truncation, sampling, resume/relaunch shortcuts, hard-coded days or
  cycles, and switches left in a run-time position. Not now; at the end, as its own step.

- The day-data catalog leaves three kinds of file out for Greg's call, each listed in the MANIFEST: MIXED
  (`session-request.json`, `comparison.json`, `principal-inputs-receipt.json`: data together with Frankie's brain;
  a filter would let the data part through), OTHER_MODEL (the Granite critic, its self-assessment, and the BOSS
  native/controller journals and forecast records in `handoff-*`: the native system's own forecasts - Frankie's
  decision process, or data?), and the teacher's JSON: JournalTeacherR3 / parallel_teacher write no JSON of their own
  (memory and pickles); the teacher's measurements reach disk as JSON only inside `host-dipole-classroom-source`.

- The spec calls a 1-2 minute canary "the standing rule for measurements". The drop-in and
  CLAUDE.md say "no canaries". Ask which applies to the disk measurement.
- **Do not confuse with `SPEC-experiment-locks.md` / `SPEC-experiment-runner.md`**: those are the
  paired-arm experiment for BOSS models (plan G20-G22: arm locks, reveal ledger, scoring). That is
  a different "experiment", not this orchestrator.
