# CCode Step 8 remainder return, 2026-10-07

Assignment: `CCODE_STEP8_REMAINDER_ASSIGNMENT_20261007.md` (Greg, 2026-10-07 01:49-01:51 ET; the 02:35 ET addendum of
its section 4) through `CCODE_HANDOFF_STEP8_REMAINDER_20261007.md`. Branch `ccode/teacher-tasks-20261006b`, rebased onto
Codex's CURRENT `d6af990c` (ccr-5fce7de3-xa4hfg; its eight commits since the assignment touch none of the owned files),
pushed. Tip: the docs commit (reported in chat). The six 8A commits are preserved (rebased: `40cbc1d0` `57d619f2` `c134e0db` `a3603af9` `6bad3d22`
`373f58ed`); above them, one `[skip ci]` commit per group:

| commit | group |
|---|---|
| `456a006a` | the three 8A integration findings (section 1) |
| `23e3afae` | the main/class save-resume owner contract (section 2) |
| `4272f949` | every queue worker, kick and handover bound to an authorized run/day scope; the controller's `--days` (section 3) |
| `8af0a0b8` | `Run.previous_of` persisted before first dispatch; teacher knowledge bound to its producer identities (section 4) |
| `d8ec096b` `2634e5ee` `157c84ff` `83081b64` | four code-review passes over the above (46 findings; section 7) |
| `bfae4460` | the school consumer on the checked chain, the `waiting_school` recovery, Jev's day on the held CPU lane (section 4, the addendum) |
| `b4c60a4d` | the class acknowledgment bound to the save request's identity; the kick's scope comparison (sections 2 and 3, the assignment's later lines) |
| `df51afb0` | the review pass over the two addendum commits (section 7a) |
| `cf1f1f2c` | the shared-market policy of a NEW run on `Run.root`/plan and `Run.teacher` (section 4; Codex's producer published at `d6af990c`) |
| `24df7810` | the review pass over the policy commit (section 7b) |
| the docs commit (tip) | this file; the handoffs, drop-ins and the file index |

SOURCE-BUILT / RUNTIME-UNVERIFIED, every line: `ast.parse` without project imports on every changed Python file, `sh -n` /
`bash -n` on the shell files, `yaml.safe_load` on the workflow, `git diff --check`; the code-review skill (adversarial, high
effort) over each range before the push. Nothing ran: no test, synthetic stream, install, project/model/data/scientific run,
historical reproduction, AWS inspection or action, start, dispatch, canary or E2E. Both boxes untouched. No credential
workaround. Exactly three held 16-CPU lanes (two main, one Linux), 15 workers plus coordinator each; no Pod, host, booking or
lane added. No new mathematical mapping, objective, lag policy, model lineage or producer activation. Pins and threads null
unchanged. Integration and runtime success are not claimed; Codex's independent reviewer checks this diff.

Changed files (all owned or granted): `research/kalshi/frankie_boss/pod_root/controller.py`,
`deploy/aws/box/frankie_box_cpu_controller.sh`, `.github/workflows/frankie_box_run.yml` (the `DAYS` input and `--days`),
`deploy/aws/box/frankie_box_frankie_queue.py` and `.sh`, `deploy/aws/box/frankie_box_cores.py`,
`deploy/aws/box/frankie_box_experiment.py` and `.sh` (the two Jev plan arguments), and the one granted branch of
`deploy/aws/box/frankie_box_successor_dispatch.py` (`drain`, the `waiting_school` case; nothing else in that module).

## 1. The three 8A integration findings (`456a006a`; `pod_root/controller.py`)

1. **Lease freshness at effects.** `lease_fresh_at` is the time of the last successful conditional write. `lease_established
   (boundary)` is asked at every effect boundary: the claim (by its caller before `claim`), the submission after an export,
   the renewal, the coordination reply, the save relay and the resume. Fresh = within `LEASE_FRESH_SECONDS` (600 s); not
   fresh = one synchronous conditional write is tried now; 412 = `lease_lost`, any other failure = `lease_unestablished`.
   When ownership cannot be established the effect is NOT made: the claim, the exported inputs and any outstanding job
   stay exactly as they are, nothing is released or retried, and the loop ends with that outcome. A failure inside
   `submit` or `relay_save` is neither counted as a start failure nor sealed as a result (`LeaseNotEstablished`).
2. **Resume uncertainty.** `check_resume` refuses before any transport step when the request cannot be served (claim not
   this worker's, job live or complete, a stop pending, lease not established: refused, not unknown). A transport failure
   AFTER `renew(resume)` may have launched: `resume-pending.json` is written durably (job, request, the worker's status
   before, the error, since) and nothing is acknowledged yet. `reconcile_resume` settles it through the worker's status:
   the job live, `day_complete` or advanced = resumed; unchanged for a whole lease freshness = no launch observed. Either
   way the ORIGINAL attempt is the one acknowledged; nothing is redispatched; the request evidence is archived only with
   its acknowledgment. A pending record left by a previous controller is loaded before any new request is read; an
   unreadable one ends the service by name (nothing is guessed about a launch that may have happened).
3. **Exit outcome.** `UNSUCCESSFUL = failed, refused, lease_lost, lease_unestablished, blocked_by_start_failures,
   worker_unreachable, terminated_by_signal` end `run_serving` with `SystemExit(1)` (and `start` of the launcher exits 3 on
   them). `budget_expired`, `stop_acknowledged`, `no_remaining_work`, `resumed_job_complete`, `resumed_job_retained` exit
   zero and remain what they were: never scientific day completion (`complete` is always false in the outcome record).

## 2. The main/class save-resume owner contract (`23e3afae`; the queue, the ledger, the runner)

One owner binding per ROOT-line day, `FRANKIE_QUEUE_OWNER_V1`, written into the queue entry by `_bind_owner` BEFORE the
day's thread starts (`_take_root` / the finish take): run, day, host, the exact ROOT attempt name (a completed ROOT's, else
the next after the day's interrupted attempts: `_next_attempt`), commit and staged checkout, the exact 16-CPU set and
booking, and the day-bound marker `frankie-queue/save/<run>-<day>.save-request.json`. The ledger booking is marked owned
(`cores.own`). `Run.bind_owner` reads it; `Run.root` resumes exactly `owned_attempt` (first dispatch and resume alike; a
completed ROOT is reused whatever its name; a conflicting interrupted directory is refused). `Run.save_requested` reads the
Run's OWN marker; `Run.child` hands exactly that marker to its children (`FRANKIE_LANE_STOP_FILE` per child environment,
never the process environment: the two main lanes are threads of one process). The class entry carries the same owner
(`_after_root`), so the class worker's child reads the same marker.

The save protocol:

| action | what happens | record |
|---|---|---|
| `ACTION=save RUN DAY` | `request_save`: the marker written create-only (`FRANKIE_QUEUE_SAVE_REQUEST_V1`: attempt, booking, CPUs, requested_at, by), allowed while the day's owner runs (ROOT running, or done with its finish running); the entry records the request and its identity (sha256 of the marker's bytes + requested_at) | the marker; `save_request` on the entry; event `save_requested` |
| the owner | stops at its next boundary (`check_save` -> exit 75); `_thread_end` classifies exit 75 on the day's OWN standing marker as saved (`_save_result`), anything else as the caller's failure | the entry `saved` (ROOT phase) or `finish.state = saved`; the booking retained in place (`cores.retain`, pids moved aside: no live process, the CPUs stay booked) |
| the class child | the class worker sees the owner's marker (same `Run.save_requested`), ends the class saved and writes `FRANKIE_QUEUE_SAVE_ACK_V1` beside the marker (`<marker>.class-ack.json`, create-only): run, day, marker, the save request's identity, the owner's attempt, the booking, its pid/attempt/school day/stages | `_child_save_verdict`: acknowledged only when marker, attempt, booking AND the standing request's identity match; `done`/`failed` when the class ended on its own; `unknown` when the child is gone without one or the ack binds elsewhere (an earlier save) |
| a class-arm day in its class phase | `_finish_day` waits for that verdict before the day ends saved; a child gone without it makes the day UNKNOWN, never saved | `facts.child` |
| the holder dies (SIGKILL, host reboot) | the ledger's reaping RETAINS an owned booking for its owner instead of releasing it (`reap_locked` -> `_retain_locked`); `_sync_root` marks the day `unknown` (ROOT phase or finish phase) and asks the ledger to retain quietly | the entry `unknown`; the booking retained |
| `ACTION=status RUN DAY` | `owner_status`: the owner, the marker (standing, identity), the class acknowledgment, the ledger booking (live / retained / released and why), both line entries, the worker, a verdict word | read-only |
| `ACTION=resume RUN DAY [REBOOK=on]` | `resume_owner`: only a saved/unknown day; the marker and ack archived (never deleted); the ROOT entry (and its class entry) back to `queued` at its own place WITH the same owner binding; the next admission books exactly the retained CPUs (`book_locked` takes the retained booking over IN PLACE for its owner, before the free count, refusing while an orphan of the dead holder still runs on them) and resumes the same attempt; a retained booking gone from the ledger is refused unless `REBOOK=on` (the same attempt on any free 16 CPUs: an explicit decision, recorded) | events `resume`; `resumes` on the entry |

`STATES` gained `saved` and `unknown` (`OWNER_STATES`): such a day is never admitted, retried, requeued or reconciled on its
own (the root worker's admission skips them; the class worker waits at the front with `waiting_owner`, exit 5); no
replacement attempt is minted for an owned day; a failed (never saved) day gives its binding up as history
(`_release_owner`, its stale marker archived) so the once-per-worker retry binds afresh, as before the contract. A save
after a finished ROOT is a done entry with a saved finish (`_end_slot`). A save never bypasses an unfinished Jev dependency:
`_finish_day` stops at the boundary with Jev still waiting (its `jev` fact, not finished). The Linux lane keeps its own
protocol (`pod_agent`'s per-job marker; `FRANKIE_LANE_ATTEMPT`); `Run.root` honours it unchanged.

## 3. The scoped-dispatch contract (`4272f949`)

`--scope RUN:D1,D2,...` (`parse_scope`, `in_scope`) is required for `worker`, `kick` and `handover` on both lines; a kick
without one starts nothing (`started=False`, event `kick_refused_no_scope`): there is never an unscoped worker. A worker
admits, reconciles, receipts and ends ONLY entries of its scope; everything else in the line is left exactly as it is
(never deleted, relabelled or requeued). FIFO holds within the line: an out-of-scope predecessor at the front makes an
eligible day wait (`waiting_out_of_scope`, exit 5 at the bound) and is never started by that worker. The submitted
randomized day order is the line's arrival order, untouched. Retained owner claims (`saved`/`unknown`, remote claims) are
untouched by any worker. `Run.scope_text()` is the run's saved plan's days, exactly (a one-day plan is a one-day scope):
`Run.start` / `Run.kick` / the enqueue kick / the class-wait kick in `_finish_day` all pass it; the queue shell requires
`SCOPE` for worker/kick/handover. The running worker's scope is persisted in `<line>-worker.json` on every status write;
`kick` compares the requested scope with it before saying "already running" (`covered` = same run and the requested days
a subset): the process-lock fast path never bypasses the scope (`b4c60a4d`). The Linux controller carries `--days`
(`frankie_box_run.yml` input `DAYS`, the launcher's `DAYS`): `authorized(day)` refuses a claim, a start or a resume of a
day outside it, naming it once in the events; without `--days` the controller's scope is the saved plan's days. No second
scheduler: the plan and the ROOT line decide readiness as before.

## 4. The small integrations and the addendum callers

- `Run.previous_of` (`8af0a0b8`): the non-queue predecessor selection, including an explicit none, is persisted as
  `days/<day>/previous.json` (`FRANKIE_PREVIOUS_SELECTION_V1`) before the first child dispatch and read back on every later
  call (`previous_kept`); a retry never repicks a newer classroom. The queue's pinning (`queue_previous`) stays as it was.
- `Run.teacher_knowledge` (`8af0a0b8`): a new summary is bound to `teacher_producer_identity()` = the sha256 of each module
  in `TEACHER_KNOWLEDGE_PRODUCERS` (`made_at_commit` recorded informationally). A retained summary whose producer identity
  differs or is unestablished is preserved and refused (`ValueError`, named per day on the batch as `refused_days`; the
  batch's other days are not held back); an explicit checked successor is required; nothing is regenerated.
- **The school consumer** (`bfae4460`; Codex's helper `retained_school` fetched at `7f08d76e` and read with
  `SCHOOL_RECOVERY_CONTINUATION_20261007.md` before wiring). `Run.school` calls `SK.retained_school(brain, day)` instead of
  reading the bare index row: a `complete` chain of THIS run is reused as its latest checked school (`file` =
  `original['path']`, `row` = `dict(row, **original)`, `school_sha256`, `corrections`); another run's same-day school is
  refused, never reused; a `requires_successor` chain goes through the existing school child, whose CLI runs the owner
  operation, and the child's `successor`, `correction` and `corrections` fields reach the run's school receipt. A corrupt
  chain raises; it is never read as absence. When the school's discussion is bound to a replaced exchange the successor
  needs the completed corrected meeting: until the day's voice is done or reused the school stage records `waiting`
  (never a failed child, never a requeue). `successor_dispatch.drain` (the one granted branch) answers
  `rebuild_dependents`' `waiting_school` by calling `Run.recover_school(day, recovery_intent)`: the existing voice then
  school on the same owner/day/held lane, the nested inbox drain skipped for exactly that recovery (`Run.successors`
  returns at once while `_school_recovery` names the day; `drain` holds its lock), then `rebuild_dependents` again verifies
  the checked chain before the acknowledgment. A meeting that is not complete leaves the recovery `waiting` with the
  voice's reason; a save stops it like any step. `Run.finished('school'|'reports')` and `reports_stale` treat a done/reused
  school superseded by a checked successor as unfinished (`school_current`): the school stage runs again through the owner
  operation and the reports get their revision under the same number; a chain that still requires a successor supersedes
  the school stage only (the reports wait on it, never re-rendered on a stale school meanwhile). Old artifacts stay; the
  reports receipt now records the school it was rendered on.
- **Jev's day on the held CPU lane** (`bfae4460`; Codex's `frankie_box_jev_cpu.py`/`.sh` at `523336f1`, read with
  `STEP7_CPU_CONTINUATION_20261007.md` and the caller supplement). `jev` is in `cores.DAY_RUN_STAGES`: the child runs
  through `cores run --inside` with exactly the day's retained 16 CPUs and the day's own marker. `Run.jev` builds
  `JEV_CPU_REQUEST_V1` from retained facts only (run, day, `day_role=discovery`, the stamp, the original ROOT attempt:
  the owner binding's, else `FRANKIE_LANE_ATTEMPT`, else the finished ROOT's directory name; the owner binding; host;
  plan sha256; the live held booking and its exact CPU list; commit and code root; the marker; output
  `days/<day>/jev/<stamp>`; the brains; the existing report number; the classroom PRODUCER's receipt pin, the owning day's
  search `MANIFEST.json` pin and the runtime file's pin) and persists it create-only as `days/<day>/jev-request-<stamp>.json`
  BEFORE the first dispatch; later calls reuse that file byte for byte, and a retained request that binds another identity
  (any of schema, run, day, role, stamp, attempt, host, plan, source, output, brains, report number, booking, CPUs) is
  `refused` with the differing fields named: never re-minted, an explicit owner recovery decides. Not dispatched: a holdout
  day (`waiting`: no authorized route), an incomplete classroom or search, no runtime configuration (`waiting`: a missing
  runtime choice is never skipped or done), no marker, no live held booking (never a rebook), an unestablished attempt, a
  retained `status.json` listing unresolved model calls (`waiting`: none is retried or erased). After the child, only a
  receipt whose `owner.request_pin` or a status whose `request` is this request's pin (as given or resolved: the helper
  writes both) counts: exit 0 with a bound `JEV_CPU_RECEIPT_V1` `done` = done; a bound receipt `waiting` or exit 5 = waiting
  with its pending dispositions; exit 75 with a bound `JEV_CPU_STATUS_V1` `saved`, no unresolved call and the marker
  witness equal to the marker standing now = `saved` (the day's own save classifies the thread; this keeps the child's
  side); anything else bound = waiting (5/75) or failed; nothing bound = failed (or waiting on 5/75). Once a bound receipt
  shows both local deliveries, the existing knowledge boundary (`lane_state.boundary(day, 'jev')`) runs again whatever the
  comparison disposition (`knowledge_after_delivery`), and `Run.child` ran it before the dispatch. The runtime file comes
  from the plan (`--jev-runtime` / `JEV_RUNTIME` at the run's FIRST start; a run keeps one plan) or from
  `<run>/jev-runtime.json`; Jev's brain from the plan (`--jev-brain` / `JEV_BRAIN`) or `/opt/frankie-box/jev-brain`.
  `prior_brain` is not supplied: the helper selects peer Jev knowledge from the synced roots itself (the supplement).
  Nothing of the helper's science, seal, transport or report is touched.
- **The shared-market policy of a NEW run** (`cf1f1f2c`; Codex's `frankie_box_market_timeline.py`, the ROOT and teacher
  wrappers' flags and `SHARED_MARKET_TIMELINE_20261007.md`, published at `d6af990c` and read before wiring). The policy
  `FRANKIE_SHARED_MARKET_TIMELINE_V1` is saved with the plan at the run's FIRST start (`--shared-market-policy` /
  `SHARED_MARKET_POLICY`; a run keeps one plan, so an omitted legacy policy stays omitted and is never presented as the
  new view; the Linux lane runs the same saved plan, so its ROOT and teacher run under the same policy). `Run.root`
  passes `SHARED_MARKET_POLICY` to the ROOT child (the wrapper forwards `--bedrock on --shared-market-policy`) and,
  before the retained fast path, requires a completed ROOT's `shared_market_policy.schema` to be the plan's: a legacy or
  other-policy ROOT is `refused` and preserved (one finished ROOT per day, `root_of`, so the successor is explicit; nothing
  is recomputed or relabelled); a legacy plan reuses any completed ROOT and records the ROOT's own policy beside its
  `plan_policy` of none. `Run.teacher` under the policy reads each day's completed OWNER-LOCAL ROOT (`shared_root_of`:
  a remote owner's ROOT is that lane's, never a caller-local alias; a day without its completed ROOT waits; a ROOT under
  another policy refuses the day) and passes `SHARED_MARKET_POLICY` + `CALCULATION_ROOTS` aligned with `DAYS` and
  `INGESTION_RECEIPTS`; a retained teacher result is reused only when `shared_teacher_compatible` holds: the rows receipt's
  `shared_market_identity` (the policy's schema, the day, the exact `calculations-receipt.json` witness of that ROOT), its
  `shared_market_read` (the same identity, `complete`), the same ingestion receipt and the same external publication as
  the attached day file; a legacy teacher receipt, the plan's rows or a launch run's never satisfy it (refused per day,
  preserved, the batch's other days unaffected; an explicit compatible successor is required). The classroom's own
  detection of a shared-policy ROOT and the V2 equality checks are Codex's (the report's item 4), not touched.

## 5. What is NOT wired, by name (dependencies, not hidden assumptions)

1. **The `Run.voice` remote (GitHub) admission caller** (`STEP6_COMPLETION_20261007.md`). `Run.voice` runs the LOCAL
   configured meeting child (`frankie_box_granite_meeting.sh`) and nothing in the runner dispatches the GitHub workflow;
   the report itself says no remote admission operation exists in the runner/lane interface yet. Not invented. The caller
   side, once the acknowledgment interface is agreed with the Granite runner owner: an immutable dispatch intent under
   `days/<day>/voice-dispatch/<exchange sha256>/` (exchange bytes/source, run/day, config, meeting input, owner, the
   complete prior-state witness when any) written before any dispatch; the exact GitHub run identity retained after it;
   an uncertain dispatch reconciled to that intent through the runner's state, never resent; the runner admitted only on
   the owning lane's acknowledgment of that exact run and predecessor (a predecessor's complete state and stopped process
   established first); the return through the existing owner importer (`frankie_box_granite_runner.py import`) and
   recorded before any successor attempt. Request: the acknowledgment's shape and where the runner reads it.
2. **Jev's runtime configuration** (`JEV_CPU_RUNTIME_V1`: binary and model pins with quantization identity, the worker
   subset of the held lane, context/output/chunk/time budgets, the completion policy): a setup decision, not a value to
   borrow from Granite; Jev waits until it is supplied (section 4).
3. **A REBOOK'd day and its Jev request**: the retained request binds the original booking id and CPU list; after
   `REBOOK=on` (a different booking) the helper refuses that request and `Run.jev` reports the differing fields as
   `refused`. An explicit owner recovery (a new stamp is NOT minted by code) is the only way on; named, not hidden.
4. **`frankie_box_lane_state.py:619`** (Codex's): `Q.kick('class', ...)` after a remote class completion passes no scope,
   so that kick now returns `started=False` ("no scope given") instead of starting an unscoped worker; the owning day's
   own class-wait kick (`_finish_day`, scoped to the run's plan) covers the class line meanwhile. Request: pass
   `scope='%s:%s' % (run, day)` (or the run's plan scope) there.
5. The 8A dependencies stand (`CCODE_STEP8_CPU_CONTROLLER_20261007.md` section 4): the main box's instance profile (Greg's
   decision), the signing window, the saved main plan, the claim store, the worker box, systemd-run and the venv, Jev's
   completion dependency.
6. Earlier requests to Codex-owned functions stand (that report's section 6: the coordination gap tolerance, the worker's
   input-URL refresh, new queue day-state words: the queue now carries `saved` and `unknown`; `frankie_box_pod_root.py`'s
   `day_state` was not changed).

## 6. Source checks

Per changed Python file: `ast.parse` without project imports; a read of every attribute and key used against the module it
comes from (the helper's request fields and pin shape, `retained_school`'s result, `durable.witness`, the ledger's booking
fields, `parse_scope`'s keys). `sh -n` and `bash -n` on `frankie_box_experiment.sh`, `frankie_box_frankie_queue.sh`,
`frankie_box_cpu_controller.sh`; `yaml.safe_load` on `frankie_box_run.yml`; `git diff --check` on every commit. The
code-review skill run adversarially at high effort: four passes over the main contract/scope/integration commits (section
7), one over the two addendum commits (`df51afb0`), one over the policy commit (`24df7810`). No test, validator
framework, synthetic stream or execution of any
kind; no AWS call; the scratchpad left empty.

## 7. What the review passes fixed and kept

The four passes over `456a006a..8af0a0b8` (46 findings), the gravest: a retained booking counted as alive through the dead
worker's pid (pids are moved aside on retain); the free-count check refusing the owner's own takeover (the takeover
precedes it); a failed day keeping its exact CPUs as if saved (the binding released on every non-saved end); a dead FINISH
holder unreachable by reconciliation (`_sync_root`'s done-entry branch); a stale save marker surviving a non-saved end (archived
with the binding); a lease failure in a resume classed as unknown (refused); a batch refusal blocking the other days
(recorded per day); the enqueue kick scoped to one day stranding the plan's others (the run's plan scope); an unreadable
pending resume silently ignored (named, the service ends); a resume with its booking gone silently rebooking (refused
unless `REBOOK=on`). Kept as they are: the controller's own `write_json`/`read_json`; the once-per-worker retry of a FAILED
(never saved) day, exactly as before the contract; the class worker's SIGTERM `Bound` path, which is still not an
acknowledgment (only the written ack is). The pass over `bfae4460`/`b4c60a4d`: section 7a below.

### 7a. The addendum review pass (`df51afb0`)

The pass (REQUEST CHANGES, 2 critical, 4 required, 7 optional) and what was done: (critical) the `waiting_school` branch re-entered `rebuild_dependents` -> `recover_school` -> `Run.voice` every 5 s while the meeting was not complete, a model child re-dispatched without bound on the held lane: the branch now BREAKS out of the operation's loop when the recovery is not complete (the operation stays unacknowledged; the next boundary's drain tries it once more), and `recover_school` re-runs the voice child only when no receipt, a blocking wait or a failure stands (a non-blocking refused meeting is the owner's decision, not re-dispatched); (critical) the recovery state embedded the voice/school receipt bodies, so every poll rewrote the successors receipt: it carries receipt paths and statuses only; (required) the reports' currentness compared the school receipt with the chain, so reports rendered on the old school were reused once the school stage had re-recorded: `reports_school_stale` compares the reports' recorded school sha256 with the school stage's; (required) an exception in the recovery's voice/school became the operation's `failure.json` (a failure substitute): it is an explicit waiting recovery now, `SystemExit(75)` still propagating; (required) the Jev `saved` branch was unreachable on a standing marker (`child()` raises first) and would have labelled the helper's signal path as saved: removed, exit 75 without a standing marker is waiting with the child's reason; (required) a relative or symlinked `JEV_RUNTIME`/`JEV_BRAIN` would have poisoned the immutable request: refused before the request is written, and the launcher requires both under `/opt/frankie-box`; (optional, done) a bound receipt whose dispositions await the owner is not re-dispatched; the class worker's `passed('school')` resolves school currentness through `Run.finished`; the recovery marker is a per-day set (thread-safe across the pools). Kept, named: `finished()` on a corrupt school chain raises out of `Run.start` (per the contract: never read as absence; the queue paths record it as the day's failure); an acknowledgment from a class worker still on the previous commit carries no request identity and reads `unknown` (roll both workers together); the kick's fast path may read the previous worker's status file in the window before the new worker's first status write; `retained_school` is read on every currentness check (every correction record of every knowledge root per day per call).

### 7b. The policy review pass (`24df7810`)

The pass (REQUEST CHANGES, 1 critical, 6 required, 3 optional) and what was done in `24df7810`: (critical) a legacy teacher result refused by `Run.teacher` was still consumed by every other reader of the day's rows (classroom_ready, the classroom's knowledge publication, school, data, the lane's finish) and the batch was recorded `skipped`/`done`: one gate now, `Run.day_rows`, which every consumer passes (rows the plan's policy refuses are none, with the reason), and a batch with a refused day is `refused` (never FINISHED; its other days ran), the lane's `_finish_day` reads the same gate; (required) a refused ROOT was classed as waiting by `shared_root_of` (refused now); a waiting ROOT or an unsealed ingest was relabelled a permanent refusal of a valid teacher result (`shared_teacher_compatible` is three-way: ok, waiting, refused; waiting days are `root_waiting`, never refused); the external witness came from an in-process cache that is empty under `EXTERNAL_WAIT=off` (read beside the sealed ingest, `attached_day_file`, what the ROOT and the teacher both saw); only the policy's schema was compared where the reader requires the full binding, implementation sha included (`shared_policy_mismatch` against the staged `frankie_box_market_timeline.binding()`, in the ROOT fast path, before the teacher and through it for a retained teacher result); a stale partial legacy publication under `experiment-teacher-rows/<day>` was dispatched under the policy and failed deterministically every start (refused before dispatch); (optional, done) a refused ROOT is not re-recorded on every start (`root_enqueue` returns the prior refusal) and every refusal names the successor route: a new run name (a run keeps one plan, one finished ROOT per day). Confirmed by the pass, kept: the Linux lane runs the same saved plan (`pod_agent.run_full_day` writes `job['plan']`), so its ROOT and teacher carry the policy identically; `CALCULATION_ROOTS` is built from the same list as `DAYS` and `INGESTION_RECEIPTS`, and the teacher wrapper enforces the alignment independently.

## 8. What remains of Step 8 and of the workflow (not this return)

The remote voice admission (section 5) once its acknowledgment interface is agreed; Jev's runtime configuration; the lane_state kick scope (Codex's line); the 8A dependencies; the
exact operating sequence for a real launch, written into the runbook only after a real E2E has been authorized and
observed. Steps 2-7 are not closed by this return. Nothing here is runtime evidence; the first real dispatch of any of it
needs Greg's explicit AWS go, then ONE day with inspection, review, then THREE days; thirty remain a separate decision.
