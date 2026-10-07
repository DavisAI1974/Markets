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
| `35718474` | the third pass, over `24df7810` (section 7b) |
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
7), one over the two addendum commits (`df51afb0`), one over the policy commit (`24df7810`) and one over that
correction (`35718474`). No test, validator
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

### 7b. The policy review passes (`24df7810`, `35718474`)

The pass (REQUEST CHANGES, 1 critical, 6 required, 3 optional) and what was done in `24df7810`: (critical) a legacy teacher result refused by `Run.teacher` was still consumed by every other reader of the day's rows (classroom_ready, the classroom's knowledge publication, school, data, the lane's finish) and the batch was recorded `skipped`/`done`: one gate now, `Run.day_rows`, which every consumer passes (rows the plan's policy refuses are none, with the reason), and a batch with a refused day is `refused` (never FINISHED; its other days ran), the lane's `_finish_day` reads the same gate; (required) a refused ROOT was classed as waiting by `shared_root_of` (refused now); a waiting ROOT or an unsealed ingest was relabelled a permanent refusal of a valid teacher result (`shared_teacher_compatible` is three-way: ok, waiting, refused; waiting days are `root_waiting`, never refused); the external witness came from an in-process cache that is empty under `EXTERNAL_WAIT=off` (read beside the sealed ingest, `attached_day_file`, what the ROOT and the teacher both saw); only the policy's schema was compared where the reader requires the full binding, implementation sha included (`shared_policy_mismatch` against the staged `frankie_box_market_timeline.binding()`, in the ROOT fast path, before the teacher and through it for a retained teacher result); a stale partial legacy publication under `experiment-teacher-rows/<day>` was dispatched under the policy and failed deterministically every start (refused before dispatch); (optional, done) a refused ROOT is not re-recorded on every start (`root_enqueue` returns the prior refusal) and every refusal names the successor route: a new run name (a run keeps one plan, one finished ROOT per day). Confirmed by the pass, kept: the Linux lane runs the same saved plan (`pod_agent.run_full_day` writes `job['plan']`), so its ROOT and teacher carry the policy identically; `CALCULATION_ROOTS` is built from the same list as `DAYS` and `INGESTION_RECEIPTS`, and the teacher wrapper enforces the alignment independently.

A third pass over `24df7810` (REQUEST CHANGES, 5 required, 5 optional), fixed in `35718474`: the refusal reasons for teacher rows named a successor route that does not exist (the teacher rows under `experiment-teacher-rows/<day>` are not run-scoped, so a new run name finds the same refused publication): the one route is named truthfully (the retained publication moved aside with a receipt; no code mints a replacement), and a day refused by the policy is recorded `refused` by `enqueue_classroom` instead of entering the class line it would block for every day behind it; a refused ROOT was still `waiting` in `classroom_ready` and `data` (refused now, only for the policy refusal, which carries `retained_policy`; a queue-door refusal keeps waiting); the prior ROOT refusal is returned by `Run.root` itself when the mismatch is unchanged (the `root_enqueue` pin is gone, so a checkout whose timeline module matches again re-evaluates); the stale-publication check runs after the ROOT is established, on the exact ROOT and ingestion witnesses, and an unreadable receipt is a refusal, never an exception out of `teacher()`; a producer-identity refusal (`teacher_knowledge`) leaves the batch's status as it was (only a policy refusal makes the batch `refused`); the exchange refuses or waits on refused or waiting rows instead of running without them; the post-child brain publication passes the one gate; the day file's sha256 is read once per Run and an unreadable one is `waiting`, not an exception. Kept, named: the plan's own `teacher_rows` never satisfy the policy (by design: the policy's rows are the teacher-only step's); `enqueue_classroom` records the string 'None' for absent rows (pre-existing).

## 8. What remains of Step 8 and of the workflow (not this return)

The remote voice admission (section 5) once its acknowledgment interface is agreed; Jev's runtime configuration; the lane_state kick scope (Codex's line); the 8A dependencies; the
exact operating sequence for a real launch, written into the runbook only after a real E2E has been authorized and
observed. Steps 2-7 are not closed by this return. Nothing here is runtime evidence; the first real dispatch of any of it
needs Greg's explicit AWS go, then ONE day with inspection, review, then THREE days; thirty remain a separate decision.

## 9. Account actions, 2026-10-07 evening (the 8A dependencies a-d; Greg's explicit authorization in session)

Authorized by Greg in the parent session ("Yes for the account work", "Root", write enabled). Caller: the account root of
568968024170 through the `Aws` connector (`run_script` only; no Bash AWS CLI, no git write commands). Skills used before
acting: `api-and-interface-design` (intent recorded before every call; success/failure/unknown kept distinct; additive policy),
then through `retrieve_skill`: `aws-compute` (`references/systems-manager.md`), `setting-up-ec2-instance-profiles`
(`references/ec2-instance-profile-setup.md`: reuse the existing role, inline least-privilege over managed, never detach),
`aws-storage`, `aws-billing-and-cost-management` (prices from the Pricing API, arithmetic by script). Every call below ran
once; each result is the API's own return. Nothing here launched the experiment, dispatched a workflow, called a model,
rotated a key, created or terminated an instance, or deleted anything. The `llama-server` binary was never executed: the
gate check reads files only.

### a. EC2 state and SSM registration (read-only)

- `sts:GetCallerIdentity`: `arn:aws:iam::568968024170:root`.
- `ec2:DescribeInstances` us-east-1 and us-east-2, `ssm:DescribeInstanceInformation` both regions, 12:5xZ, BEFORE:
  - main `i-035994afa8bdf66a5` r7i.8xlarge us-east-1d, `stopped`, instance profile `arn:aws:iam::568968024170:instance-profile/Ssm`,
    tags Name=frankie-ingest32-20260917, KeepRunning=true;
  - worker `i-0d17573dbce871520` r7i.4xlarge us-east-1d, `stopped`, instance profile `Ssm`, tags Name=frankie-linux-r7i4xl,
    Owner=frankie-boss, no KeepRunning tag;
  - `i-08cee7171c0a76a04` r6i.2xlarge us-east-2b, `stopped`, profile `Ssm` (not touched);
  - SSM `InstanceInformationList` empty in both regions (nothing running).
- After `ec2:StartInstances` (12:58:11Z, both us-east-1 boxes, `stopped -> pending`), polled `ssm:DescribeInstanceInformation`:
  both `Online` by 12:58:28Z, SSM Agent 3.3.4793.0, Ubuntu 24.04.
- The main box resolves as the instance carrying profile `Ssm` in us-east-1 with the 32-CPU type and the controller's
  `MAIN` constant; the worker as `i-0d17573dbce871520` (controller `--boxes`).

### b. Inline least-privilege policy on role `Ssm` (the main box's instance profile; shared by both boxes and the us-east-2 box)

Before: `iam:GetInstanceProfile Ssm` -> role `Ssm`; `iam:GetRole` trust = `ec2.amazonaws.com sts:AssumeRole`, no permissions
boundary; `iam:ListAttachedRolePolicies` = `arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore` only; `iam:ListRolePolicies`
= none. The statements were derived from the calls the box modules make (grep of `deploy/aws/box` and `pod_root`, 5f111885):
`pod_root/controller.py` list/get/put/delete under `pod-root/*` and `box-runs/*` of `frankie-granite42-568968024170-us-east-1`
(lease, journals, presigned map, exports; presigned URLs act with the signer's own permissions) and list/head under
`frankie/ingest/*` and `frankie/day_external/*` of `bento-568968024170-us-east-2-an`; `frankie_box_heartbeat.py`,
`frankie_box_offload.py` (`upload_file`, multipart), `frankie_box_clm_sidecar_extract.sh`, `frankie_box_brain.py` get/put
under `host-deliveries/*` of the transfer bucket; `ssm_run_sh.py` SendCommand `AWS-RunShellScript` to the worker and
`GetCommandInvocation`; the controller preflight's `DescribeInstanceInformation`; `GetParameter` on the four named
parameters (already inside the managed policy; restated for intent); `GetCallerIdentity`. No CloudWatch/logs call exists in
either tree, so none is granted. `AbortMultipartUpload` is the one action not literally named in source: `upload_file`
needs it to clean up a failed multipart part set. Written with `iam:PutRolePolicy` (inline, additive; the managed policy was
NOT detached), read back with `iam:GetRolePolicy` (document equal), after: attached = `AmazonSSMManagedInstanceCore`,
inline = `FrankieBoxStep8A-20261007`.

Policy name `FrankieBoxStep8A-20261007` on role `Ssm`, verbatim:

```json
{"Version": "2012-10-17", "Statement": [
 {"Sid": "TransferBucketList", "Effect": "Allow", "Action": ["s3:ListBucket"],
  "Resource": "arn:aws:s3:::frankie-granite42-568968024170-us-east-1",
  "Condition": {"StringLike": {"s3:prefix": ["pod-root/*", "box-runs/*", "host-deliveries/*"]}}},
 {"Sid": "ControllerTransferObjects", "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
  "Resource": ["arn:aws:s3:::frankie-granite42-568968024170-us-east-1/pod-root/*",
               "arn:aws:s3:::frankie-granite42-568968024170-us-east-1/box-runs/*"]},
 {"Sid": "HostDeliveriesObjects", "Effect": "Allow", "Action": ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload"],
  "Resource": "arn:aws:s3:::frankie-granite42-568968024170-us-east-1/host-deliveries/*"},
 {"Sid": "IngestBucketList", "Effect": "Allow", "Action": ["s3:ListBucket"],
  "Resource": "arn:aws:s3:::bento-568968024170-us-east-2-an",
  "Condition": {"StringLike": {"s3:prefix": ["frankie/ingest/*", "frankie/day_external/*"]}}},
 {"Sid": "IngestBucketRead", "Effect": "Allow", "Action": ["s3:GetObject"],
  "Resource": ["arn:aws:s3:::bento-568968024170-us-east-2-an/frankie/ingest/*",
               "arn:aws:s3:::bento-568968024170-us-east-2-an/frankie/day_external/*"]},
 {"Sid": "WorkerRunShellScript", "Effect": "Allow", "Action": ["ssm:SendCommand"],
  "Resource": ["arn:aws:ec2:us-east-1:568968024170:instance/i-0d17573dbce871520",
               "arn:aws:ssm:us-east-1::document/AWS-RunShellScript"]},
 {"Sid": "WorkerCommandStatus", "Effect": "Allow", "Action": ["ssm:GetCommandInvocation", "ssm:DescribeInstanceInformation"],
  "Resource": "*"},
 {"Sid": "BoxParameters", "Effect": "Allow", "Action": ["ssm:GetParameter"],
  "Resource": ["arn:aws:ssm:us-east-2:568968024170:parameter/markets/frankie/github-token",
               "arn:aws:ssm:us-east-2:568968024170:parameter/markets/frankie/granite-service",
               "arn:aws:ssm:us-east-2:568968024170:parameter/markets/frankie/runpod-serverless",
               "arn:aws:ssm:us-east-1:568968024170:parameter/markets/DATABENTO_API_KEY"]},
 {"Sid": "Identity", "Effect": "Allow", "Action": ["sts:GetCallerIdentity"], "Resource": "*"}]}
```

Not proven by this section: the policy's effect at run time (the controller preflight and the first lease write are the
proof, per section 4 of `CCODE_STEP8_CPU_CONTROLLER_20261007.md`); `GetCommandInvocation`/`DescribeInstanceInformation`
carry `Resource: *` because SSM defines no resource type for them.

### c. Worker box setup and the main-box systemd-run/venv check (SSM Run Command)

- `ssm:SendCommand` to `i-0d17573dbce871520`, `AWS-RunShellScript`, command `dcf13b26-bc56-4b6a-8d8d-e6683934a510`, sent
  13:01:38Z, executionTimeout 3600: `deploy/aws/box/frankie_box_worker_setup.sh` at `5f111885` delivered verbatim through a
  quoted heredoc, hashed ON THE BOX before running (`sha256sum` = the worktree's
  `d2570592809672b8f11c3ed10eb834c1eb86c3b70cb739cb88a916da69d22553`, refused otherwise), `MARKETS_SHA` prepended as the
  single-quoted literal `ssm_run_sh.preamble` makes, stdout kept whole at `/var/tmp/ssm-output/worker-setup.out`.
  `ssm:GetCommandInvocation`: `Success`. Output: ip-172-31-46-110, Ubuntu 24.04.4 LTS, 16 CPUs, 123 GB; Python 3.13.15;
  "freeze matches the main box's 75 pins"; checkout `5f111885` detached, ingest worktree
  `/opt/frankie-box/ingest-code/5f111885c23eb056f2769f3fa835a73709f727a0`; receipt `FRANKIE_WORKER_SETUP_V1`
  (`freeze_matches_main: true`, cpus 16) under `/opt/frankie-box/receipts/worker-setup-<utc>.json`. Disk after: 19 GB free
  of 116 GB (84% used): named, not changed.
- `ssm:SendCommand` to `i-035994afa8bdf66a5`, command `02f6b8ef-e79b-41c9-a1d4-86842ef498d3`, executionTimeout 300,
  `GetCommandInvocation`: `Success`. ip-172-31-39-59, Ubuntu 24.04.4 LTS, 32 CPUs, 247 GB, 1.1 TB free of 2.0 TB;
  `/usr/bin/systemd-run` present (systemd 255, 255.4-1ubuntu8.17); `/opt/frankie-box/venv/bin/python` 3.13.15 imports
  boto3 1.42.23 / botocore 1.42.97; the box role is `arn:aws:sts::568968024170:assumed-role/Ssm/i-035994afa8bdf66a5`;
  claim store `/opt/frankie-box/work/root-claims` exists; experiment runs present: days-20260929-1, days-20260929-3,
  days-20260930-1, pairs2-20260929-1; `/opt/frankie-box/markets` was at `25b30d9` (left there; the pinned commit was added
  as an ingest worktree in d, the main checkout was not moved).

### d. The one pinned CPU install on the main box (serves Granite and, by Greg's decision today, Jev: the same weights, build and runtime)

- Before the box: the pinned asset was fetched into the session scratchpad through the proxy from
  `https://github.com/ggml-org/llama.cpp/releases/download/b11440/llama-b11440-bin-ubuntu-x64.tar.gz`: 17,693,628 bytes,
  sha256 `5e6dcc9178743c49de36e5e1b77f38453e820647782a738856b1e3fd73b1fb2b` = pin `llama_cpp_sha256`; one top directory
  `llama-b11440`, so the gate's binary path is `$GRANITE_DIR/llama-b11440/llama-server`.
- `ssm:SendCommand` to `i-035994afa8bdf66a5`, command `7e8f2cb5-791b-408f-9696-ceb11f90de2c`, sent 13:02:26Z,
  executionTimeout 3600, `GetCommandInvocation`: `Success`, setup wall 55 s. The command: `git fetch --depth 1` of
  `5f111885c23eb056f2769f3fa835a73709f727a0` into `/opt/frankie-box/markets` and `worktree add` at
  `/opt/frankie-box/ingest-code/5f111885c23eb056f2769f3fa835a73709f727a0` (the box's existing pattern; CODE_ROOT);
  `GRANITE_MEETING_RUNTIME_V1.json` there hashed `aee197b48ad37d1ba4c8e892c08ba0c84b615a25f4751414862312247d9dd032` and
  `frankie_box_granite_meeting_setup.sh` `2e2b80d3b8d74ce737e5bc1ab77bc8eed22c54e7a83477aa04a793e7c176b01d` (both equal the
  worktree; refused otherwise); then `CODE_ROOT=<that> GRANITE_DIR=/opt/frankie-box/granite sh frankie_box_granite_meeting_setup.sh`.
- Installed, hashed on the box after the script (sources: the GitHub release asset above; the model from
  `https://huggingface.co/ibm-granite/granite-4.2-3b-GGUF/resolve/main/granite-4.2-3b-Q4_K_M.gguf`):
  - `/opt/frankie-box/granite/llama-b11440-bin-ubuntu-x64.tar.gz` 17,693,628 bytes,
    sha256 `5e6dcc9178743c49de36e5e1b77f38453e820647782a738856b1e3fd73b1fb2b` (= `llama_cpp_sha256`);
  - `/opt/frankie-box/granite/llama-b11440/llama-server`
    sha256 `b30ec35b37e15c7365e61c6d269c5a184448f8ad342ed577999964a037abc3db` (= `llama_server_sha256`); the 50 files of
    `llama_cpp_files` verified beside it (61 directory entries including the 10 .so symlinks and `provenance.json`);
  - `/opt/frankie-box/granite/granite-4.2-3b-Q4_K_M.gguf` 2,244,011,552 bytes,
    sha256 `e0406663965846ae22a403456eb826ccce5f450840491f71952f18a7cb78e7d5` (= `model_sha256`);
  - `/opt/frankie-box/granite/llama-b11440/provenance.json` = `FRANKIE_GRANITE_RUNTIME_PROVENANCE_V1` (release b11440,
    files_verified 50, host_cpus 32, verified_every_run true).
- The Python gate, run read-only from the pinned checkout with the venv (`frankie_box_granite_meeting.gate(config,
  binary=..., model=...)`, zero model calls, `llama-server` never executed): `gate reasons: []` -> "runtime may start".
  That is the gate's file-level verdict only; no meeting, E2E or model call ran or is authorized by it.
- No second install: Jev uses this same directory per Greg's decision; `JEV_CPU_RUNTIME_V1` (Codex's) still has to NAME
  these paths and pins before a Jev child can start; until then `Run.jev` waits, as before.

### Box states, instance-hours and cost

- `ec2:StopInstances i-0d17573dbce871520` 13:03:32Z (`running -> stopping`); `ec2:DescribeInstances` 13:04:02Z: worker
  `stopped` (returned to its prior state; no KeepRunning tag). Worker running time 12:58:11Z-13:03:32Z = 0.0892 h.
- Main `i-035994afa8bdf66a5` is `running` and was LEFT RUNNING because its tag says KeepRunning=true (the parent's rule for
  this work: return to prior state unless KeepRunning=true). Its prior state was `stopped`. 0.0975 h at 13:04:02Z and
  counting. Stopping it is one call (`ec2:StopInstances`, us-east-1) if Greg wants the prior state back.
- Prices from `pricing:GetProducts` (us-east-1 endpoint; Linux, shared tenancy, on-demand, US East N. Virginia):
  r7i.4xlarge 1.0584 USD/h, r7i.8xlarge 2.1168 USD/h. Worker: 0.0944 USD. Main: 0.2064 USD at 13:04:02Z; 50.80 USD per
  day if left running. Data transfer for the 2.2 GB model download in is not charged by EC2 (inbound).

### What did not complete

Nothing in a-d failed. Not done because not in scope: the signing-window limit (section 4.2) is a design limit, not a
provisioning item; the saved main plan and the claim-store activation are written by the orchestrator at its first start;
the B1 duckdb/pyarrow Linux dependency named in the step-1 handoff was not examined. The policy's run-time effect and the
installed runtime's behaviour under a real meeting stay RUNTIME-UNVERIFIED until the one authorized E2E.

## 9. The restart pass of 2026-10-07 evening (Greg's redirect: the 99 layers first; source only, read-only account inspection)

Branch `ccode/teacher-tasks-20261006b-step8-corrections` over `5f111885` (the independent review's corrections `9cd1e2aa` and
the restart pass `5f111885` taken as the work list's current state, not redone). Worktree only; nothing committed by this
role (the parent commits). Changed files: `deploy/aws/box/frankie_box_experiment.py` (+451/-35 incl. this section's code),
`deploy/aws/box/frankie_box_experiment.sh` (+6/-6), `deploy/aws/box/frankie_box_frankie_queue.py` (+8/-1),
`deploy/aws/box/frankie_box_successor_dispatch.py` (+15, the `waiting_school` branch only), this file.
`frankie_box_workflow_inspection.py` NOT edited (the work branch's union copy wins at the merge; projections requested below).
SOURCE-BUILT / RUNTIME-UNVERIFIED: AST without project imports, `bash -n`/`sh -n`, `git diff --check` only; nothing ran.

### 9.1 The 99 layers combined for Frankie (Greg's first priority)

The retained 99-entry crosswalk is `research/kalshi/frankie_boss/audits/CROSSWALK_SUNDAY_CYCLE0_FEED_33746436209_20260916.json`
(schema `FRANKIE_NATIVE_RAW_MBO_LAYER_CROSSWALK_V1`, 99 `layers`, each with `group_id`, `layer_id`, `policy`, `producer`
{file, symbol, kind}), pinned by `knowledge/CYCLE_CALCULATION_PINS.json` (`crosswalk.sha256 ece9c624...`, `registry_sha256
239a1480...`; the registry JSON itself is not in this tree, the crosswalk carries all 99 identities). The ROOT's
`work/derive.json` already records EVERY registry layer of the whole-day pin by id (`layers[<layer_id>].status` = derived /
not_derived (bedrock off) / could_not (no producer), with producer and reason; `bedrock.skipped`/`not_derived`); the
timeline (`frankie_box_market_timeline.SharedMarketTimeline`, work branch) admits six carrying layers: `root.frames`,
`root.prices`, `root.structures` (the ROOT's `shared_market_sources` spool pins), `native.member`, `native.lifecycle`
(`frankie_box_experiment_native.selected_files`), `external`, and lists `absent_layers` without rejecting anything.

Built (`frankie_box_experiment.py`): `all99_crosswalk(code_root)` (the pinned list with its integrity: verified / differs /
unreadable / unpinned, a SEPARATE visible state, never missing coverage), `all99_admission(code_root, day, calc_dir, calc,
plan_policy, policy_mismatch, ingest, brain)` (`FRANKIE_ALL99_ADMISSION_V1`), `all99_summary`, `Run.all99` (never raises out
of the ROOT step: a list that cannot be built is itself recorded). Wired into `Run.root` on every outcome: done, reused and
the policy refusal; the full list is the ROOT receipt's `all99` and its projection is `inspection.outputs.all99` (counts,
absent/disabled/integrity entries, carriers, the crosswalk pin). Per entry: `entry, group, role, policy, producer{file,
symbol, kind}, historical_status, produced, carrier, disposition, reason` with dispositions `admitted` (produced AND the ROOT
is under the plan's shared policy AND the carrying timeline layer is present), `produced`-but-`absent` (a legacy ROOT, a
refused policy, an absent carrier: the reason names it; the picture is thinner, the day stays), `absent` (not_derived with
the ROOT's own reason: bedrock off; could_not; no record), `knowledge` (the 23 control/knowledge/arm entries carried by the
brain, their consumption each reader's own receipt), `retired` (Memory A / A-clean overlays, by Greg), `sealed` (the 9
answer boundaries, preserved), `disabled` (the 2 shadows, listed, never activated), `output` (the 10 append-only outputs,
filed by later stages), `integrity` (`selected_files` raised: altered/incomplete native evidence, visible). Carriers: the
legacy five map to `root.prices`/`root.frames`/`root.structures` and the two post-stream aggregates to the timeline's
`completed_sources`; the 44 native calculation/clock layers to `native.member`+`native.lifecycle`; the raw six to the
sealed journal (the timeline's input). No timeline reader is instantiated and no spool is read: derive.json, the receipt's
spool pins and `selected_files` only (hot path unchanged). The missing-coverage rule holds throughout: nothing in the list
refuses a timeline or a day; `requests` lists the producer files of entries absent-and-not-produced so a request can name
file and entry.

What this does NOT claim: that any producer in Codex-owned code now derives a layer it did not before. Under a bedrock-off
ROOT the 44 native layers are `absent: not_derived (bedrock off)`; under `--bedrock on` (the policy route) they are
`admitted` only when `selected_files` finds the completed ledgers. Requests, by file and entry (producers in Codex-owned
code): `deploy/aws/box/frankie_box_boss_session.py` `Session.derive`/`_derive_bedrock` (the per-layer `layers[<id>]`
records for the `order_lifecycle`, `full_book_fifo_queue`, `microstructure_mechanics`, `derived_geometry`,
`prebirth_opportunity`, `causal_clocks` groups must be written with status derived and a producer when the native pass
runs; today only the pin's `registry_layers` get a record); `deploy/aws/box/frankie_box_market_timeline.py`
`SharedMarketTimeline.__init__` (expose, beside `coverage.layers`, which crosswalk layer ids each carrying layer delivers, so
the caller's carrier map stops being a static table); `deploy/aws/box/frankie_box_workflow_inspection.py` `FIELDS['root']`
(project `all99`: counts, absent, disabled, integrity, carriers; the work-branch copy).

### 9.2 Day-quantity agnostic

Searched every owned file for a count gate (`len(days)`, `== 1/2/3/30`, "one day", "three", `days[0]`, `[-1]`):
`frankie_box_experiment.py` (`load_plan`, `pair_units`, `start`, `scope_text`, `teacher` batching `BATCH = 5` = "1 day in
5", a batching rule for any N), `frankie_box_frankie_queue.py` (`parse_scope`, admission, `_needs_finish`),
`frankie_box_experiment.sh`/`frankie_box_frankie_queue.sh` (`DAYS` comma lists), `frankie_box_cpu_controller.sh` and
`pod_root/controller.py` (`--days` a distinct comma list, default the saved plan), `frankie_box_run.yml` (runner ingest
`DAYS`: non-empty distinct list; the controller `DAYS` regex). Nothing keys on the count: a plan of 1, 2, 3 or N days is
admitted, batched, scoped and finished identically. Removed: nothing (there was nothing to remove); the docstrings' "ONE-
day"/"THREE-day" words name Greg's rollout steps, not a gate. The two main lanes + one Linux lane stay the capacity, not a
day count.

### 9.3 One pinned model runtime for the meeting AND Jev (Greg, 2026-10-07)

`Run.shared_runtime()` (once per Run, cached, seconds recorded): the staged `knowledge/GRANITE_MEETING_RUNTIME_V1.json`
(`frankie_box_granite_meeting.load_config`), exactly one `FRANKIE_GRANITE_RUNTIME_PROVENANCE_V1` under
`/opt/frankie-box/granite/*/provenance.json` (the setup script writes it after every pin check), its release/asset/
server_sha256/model_sha256 compared with the staged pins, then the meeting's own gate (`GM.gate(config, binary, model)`: the
binary and every extracted file against `llama_cpp_files`, the model against `model_sha256`). `refused` names every reason
visibly until the pinned install exists. `Run.voice` (local route) passes `LLAMA_SERVER`/`GGUF_MODEL` to the wrapper only
when ready, else inputs-only with the reasons on the receipt (`inspection.inputs.shared_runtime`); `standing_voice`'s
inputs-only check reads the same result instead of the process environment. `Run.jev` no longer takes a separate runtime:
the plan's `jev_runtime`/`<run>/jev-runtime.json` is recorded as `superseded_jev_runtime` and not used; the request's
`runtime` is the Granite config's pin and `request.shared_runtime` = {provenance pin, binary, model}; the child gets the
same `LLAMA_SERVER`/`GGUF_MODEL`; a not-ready runtime is `waiting` with the reasons (never skipped, never borrowed).
`frankie_box_experiment.sh` refuses `JEV_RUNTIME`. Request: `deploy/aws/box/frankie_box_jev_cpu.py` `execute` accepts
`request.shared_runtime` (binary/model/provenance) in place of `JEV_CPU_RUNTIME_V1`'s binary/model (remaining_consumers is
making it reference the shared definition); the worker-CPU subset, budgets and completion policy stay Greg's.

### 9.4 The cross-owner requests of this pass, implemented in owned files

- correction_consumer (stage 12): `Run.reports` sets `SCHOOL` (the school receipt's `file` when done/reused) else
  `SCHOOL_LISTED` ("the day's school stage is <status>: <reason>"); `Run.reports_receipt(log, day, run)` reads the step's
  own receipt at `<reports-dir>/receipts/<run>/<day>.json` first (fields `school, school_sha256, school_status,
  school_listed`), the log's last line otherwise; `Run.reports_school_stale` compares the school stage's row sha256 with
  that receipt's `school_sha256` (a revision under the same N when they differ, or when the reports were rendered with no
  school while one stands now), falling back to the run's recorded `school.sha256`; the `waiting_school` drain branch
  (`frankie_box_successor_dispatch.py`), once the recovery is complete, runs `Run.reports` on the held lane when
  `reports_stale` says so (the nested drain skipped for exactly that call: the drain holds the inbox flock) and records the
  revision's status on the operation's recovery state.
- workflow_reports (stages 4/6/7): `Run.teacher` reads `experiment-teacher-rows/<day>/receipt.json`; `equation_not_run` is a
  listed day without rows (`rows_listed`, the batch not failed; exit 4/5 are the wrapper's listed outcomes, 3 the failed
  day); `Run.data` passes `DATA_WORKERS = DAY_RUN_CPUS - 1` (15); `Run.search` records `not_run` with the reason when the
  ROOT published no `work/derived/.rows/frames.jsonl` (no causal axis) and the day goes on: `not_run` joined `FINISHED`
  (`done_status`), `lessons`/`frankie_lessons` never pass a not_run day as a search path (listed), Jev waits on it by name.

### 9.5 Stages 0-3 and the lane rule, verified in source (no change needed)

Preflight/resume: `controller.preflight` names each prerequisite (saved plan, claim store, staged checkout, box script,
credentials, both buckets, the worker over SSM, no live lease) and refuses activation; `check_resume`/`reconcile_resume`
keep an uncertain resume unknown and reconcile it through the worker status, never redispatching. Lease: established at
claim, submit-after-export, renewal, coordination, save relay, resume and release (`lease_established` at each; the loop
ends `lease_lost`/`lease_unestablished`); `UNSUCCESSFUL` outcomes exit 1, distinct from budget/stop/no_remaining_work.
Ingest: never re-ingested when sealed (Monday refused by name). Day file: `external_ready` waits, never refuses. ROOT: the
owner binding's exact attempt, the policy mismatch refusal preserved, the brain commit before the receipt (`brain_stage`),
`DATA_WORKERS=15` inside the booked 16 (`cores run`). Lanes: `PARALLEL_DAYS=2` main + `SLOTS=1`/`LINUX_LANE` fixed; a day's
later steps run `--inside` its held booking. Jev blind: the request carries the classroom PRODUCER's receipt and the search
manifest only. No Pods (refused inputs in both routes).

### 9.6 AWS efficiency and data processing (Greg's token-stack rule applied to AWS), applies or not

| mechanism | applies | now / effect |
|---|---|---|
| S3 copies instead of box exports for the Linux lane's inputs | yes, existing | `controller.s3_source` HeadObject on the runner ingest and day-file keys; a hit skips a multi-GB export (hours on a big day); kept |
| multipart / parallel part transfer | yes, existing | `pod_transfer.plan_parts` + the worker's part downloads; the controller re-signs per part; kept |
| conditional reads/writes (ETag) | yes, existing | the lease (`IfNoneMatch`/`IfMatch`), `job.json` create-only; kept |
| S3 byte-range reads of the tape | no | the sealed journal is verified whole against its pin (bytes, sha256, chained head hash); a range read cannot verify the identity; invariant |
| S3 Select / Athena over the tape | no | the journal is a compact chained container, not row-addressable without the reader; a query engine cannot reproduce the decoded entries, counts and head hashes; invariant |
| S3 Metadata / Storage Lens / Athena instead of list/head | no at this scale | the controller lists one prefix per run with `MaxKeys=1` and heads a handful of keys; the system tables cost a table bucket + Athena per query for no saving; revisit only if the `pod-root/` prefix grows to many thousands of objects |
| instance type / placement | correct as is | main r7i.8xlarge (32 vCPU = two 16-CPU lanes), worker r7i.4xlarge (16 vCPU = one lane), both us-east-1d, same subnet (`subnet-0910ec79d4e5d6017`): no cross-AZ transfer; memory-optimized matches the journal readers; no change |
| SSM for every box step | yes, existing | the controller drives the worker over Run Command; the main-box actions run locally under the same preamble |
| cost side | measured read-only | both boxes STOPPED: only EBS bills (main gp3 2048 GiB 16000 IOPS 1000 MiB/s; worker gp3 120 GiB); the transfer bucket holds retained `pod-root/days-20260930-1/...` parts (not deleted here) |
| one-day canary | later | the measurement is a 1-2 minute slice on the real E2E, extrapolated; none run |

### 9.7 Read-only account inspection (the Aws connector; every call named)

`sts GetCallerIdentity` (account `...4170`, root). `ec2 DescribeInstances` us-east-1: main `i-035994afa8bdf66a5`
`frankie-ingest32-20260917` r7i.8xlarge (16 cores x 2) STOPPED, profile `arn:aws:iam::568968024170:instance-profile/Ssm`,
us-east-1d, `KeepRunning=true`, IMDSv2 required, AMI `ami-025d99823a4caad37`; worker `i-0d17573dbce871520`
`frankie-linux-r7i4xl` r7i.4xlarge (8 x 2) STOPPED, profile `Ssm`, us-east-1d, same subnet, IMDSv2 required, same AMI;
us-east-2: `i-08cee7171c0a76a04` `markets-year-pull-v2` r6i.2xlarge STOPPED (profile `Ssm`, IMDSv2 optional; not this
experiment's). `ssm DescribeInstanceInformation` us-east-1 and us-east-2: EMPTY (no managed node is Online; both boxes are
stopped, so SSM status cannot be read until a start Greg authorizes). `iam GetInstanceProfile Ssm`: role `Ssm`, trust
`ec2.amazonaws.com`, no permissions boundary; `ListAttachedRolePolicies`: `AmazonSSMManagedInstanceCore` only;
`ListRolePolicies`: none; `GetPolicy`/`GetPolicyVersion`: the managed policy grants ssm:*InstanceInformation/Document/
Parameter, ssmmessages and ec2messages, NO S3 and NO ssm:SendCommand. `s3 ListBuckets`: `bento-568968024170-us-east-2-an`
(ingest), `frankie-granite42-568968024170-us-east-1` (transfer; `GetBucketLocation` us-east-1). `ec2 DescribeVolumes`,
`s3 ListObjectsV2` (two prefixes, 5 keys): above. So: the 8A instance-profile dependency is NOT met for the main-box
controller route (it needs S3 on both buckets and SSM SendCommand to the worker); the worker box needs nothing beyond
`AmazonSSMManagedInstanceCore` (it reads/writes through presigned URLs).

### 9.8 Prepared account steps (TEXT ONLY; Greg decides; nothing executed here)

1. Least-privilege inline policy on role `Ssm` (`iam put-role-policy --role-name Ssm --policy-name FrankieBoxController`),
   built from what the box modules actually call (`controller.py`, `pod_transfer.py`, the presigned map of
   `frankie_box_run.yml`); no CloudWatch Logs (none is called):
```json
{"Version": "2012-10-17", "Statement": [
 {"Sid": "TransferObjects", "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
  "Resource": ["arn:aws:s3:::frankie-granite42-568968024170-us-east-1/pod-root/*",
               "arn:aws:s3:::frankie-granite42-568968024170-us-east-1/box-runs/*"]},
 {"Sid": "TransferList", "Effect": "Allow", "Action": "s3:ListBucket",
  "Resource": "arn:aws:s3:::frankie-granite42-568968024170-us-east-1",
  "Condition": {"StringLike": {"s3:prefix": ["pod-root/*", "box-runs/*"]}}},
 {"Sid": "IngestRead", "Effect": "Allow", "Action": "s3:GetObject",
  "Resource": ["arn:aws:s3:::bento-568968024170-us-east-2-an/frankie/ingest/*",
               "arn:aws:s3:::bento-568968024170-us-east-2-an/frankie/day_external/*"]},
 {"Sid": "IngestList", "Effect": "Allow", "Action": "s3:ListBucket",
  "Resource": "arn:aws:s3:::bento-568968024170-us-east-2-an",
  "Condition": {"StringLike": {"s3:prefix": ["frankie/ingest/*", "frankie/day_external/*"]}}},
 {"Sid": "WorkerRunCommand", "Effect": "Allow", "Action": "ssm:SendCommand",
  "Resource": ["arn:aws:ec2:us-east-1:568968024170:instance/i-0d17573dbce871520",
               "arn:aws:ssm:us-east-1::document/AWS-RunShellScript"]},
 {"Sid": "WorkerCommandRead", "Effect": "Allow",
  "Action": ["ssm:GetCommandInvocation", "ssm:ListCommandInvocations", "ssm:DescribeInstanceInformation"], "Resource": "*"}
]}
```
   Not included on purpose: `ssm:GetParameter` on `/markets/frankie/github-token` (the runner-only git push; the box must not
   hold it), any `s3:*` on `nymex/*` (the day-file build reads it through the dispatch's presigned map), any write to the
   ingest bucket. Verify after: `iam list-role-policies Ssm`; from the box, `cpu_controller.sh ACTION=preflight` (read-only).
2. Worker box setup over SSM (after `ec2 start-instances i-0d17573dbce871520`, on Greg's go): `ssm send-command
   --instance-ids i-0d17573dbce871520 --document-name AWS-RunShellScript` with the committed
   `deploy/aws/box/frankie_box_worker_setup.sh` preamble `MARKETS_SHA=<the dispatched commit>` (exactly as `frankie_box_run.yml`
   sends box scripts: `ssm_run_sh.preamble` + the script bytes); then `ACTION=jobs` through the controller route
   (`frankie_box_pod_root_loop.sh ACTION=status`) to read the worker's job list; `ssm describe-instance-information` must
   show the worker Online first.
3. Main-box systemd-run/venv check (read-only; the box started on Greg's go): `frankie_box_cpu_controller.sh
   ACTION=preflight RUN=<run> CODE_ROOT=<staged> MARKETS_SHA=<commit>` (it checks `systemd-run`, `/opt/frankie-box/venv/bin/python
   -c 'import boto3, botocore'`, the saved plan, the claim store, the staged checkout, the credential route to both buckets
   and to the worker over SSM, no live lease; exit 2 names the missing one; nothing installed).
4. The ONE pinned runtime install (serves the meeting AND Jev; one install, one pin set): on the main box over SSM,
   `CODE_ROOT=<staged checkout> GRANITE_DIR=/opt/frankie-box/granite sh deploy/aws/box/frankie_box_granite_meeting_setup.sh`.
   It fetches `https://github.com/ggml-org/llama.cpp/releases/download/b11440/llama-b11440-bin-ubuntu-x64.tar.gz`
   (sha256 `5e6dcc9178743c49de36e5e1b77f38453e820647782a738856b1e3fd73b1fb2b`, 17,693,628 bytes), extracts into its one top
   directory, verifies every extracted file against `pins.llama_cpp_files` and `llama-server` against
   `b30ec35b37e15c7365e61c6d269c5a184448f8ad342ed577999964a037abc3db`; fetches
   `https://huggingface.co/ibm-granite/granite-4.2-3b-GGUF/resolve/main/granite-4.2-3b-Q4_K_M.gguf` (sha256
   `e0406663965846ae22a403456eb826ccce5f450840491f71952f18a7cb78e7d5`, 2,244,011,552 bytes, the official ibm-granite
   repository, lfs.oid cross-checked by CCode 2026-10-06); writes `<GRANITE_DIR>/<top>/provenance.json`
   (`FRANKIE_GRANITE_RUNTIME_PROVENANCE_V1`: release, asset, archive_sha256, server, server_sha256, model, model_sha256) and
   prints `LLAMA_SERVER=...`/`GGUF_MODEL=...`. The box needs HTTPS egress to github.com and huggingface.co (not verified
   while stopped); a retained file that differs from its pin is refused and left in place. `Run.shared_runtime` then finds
   that provenance and gates it again; `Run.voice` and `Run.jev` bind to it. Disk: 2.3 GB on the main volume (2048 GiB).
   Expected sha256 sources: `knowledge/GRANITE_MEETING_RUNTIME_V1.json` (`pins`); the asset hash was measured on the fetched
   bytes, the model hash is the repository's LFS oid at commit `c40945d71cd90f249a56985e8155551a9188dc30`.

### 9.9 Checks, skills, calls

AST (`python3 -I -c "import ast,..."`) on `frankie_box_experiment.py`, `frankie_box_frankie_queue.py`,
`frankie_box_successor_dispatch.py`, `pod_root/controller.py`, `frankie_box_cores.py`: OK; `bash -n` and `sh -n` on
`frankie_box_experiment.sh`: OK; `git diff --check`: clean. Skills: `api-and-interface-design` (Skill tool, first), then the
AWS registry through `mcp__Aws__aws___search_documentation(topics=["agent_skills"])` and `retrieve_skill`: `aws-compute`
(+ `references/systems-manager.md`, `references/instance-selection.md`), `setting-up-ec2-instance-profiles`
(+ `references/ec2-instance-profile-setup.md`), `aws-storage` (`references/s3-general-purpose-knowledge.md`),
`querying-aws-s3`, `aws-iam`, `aws-billing-and-cost-management`. Account calls (all read-only, named in 9.7). No test, no
E2E, no dispatch, no model/data run, no install, no account write, no start.

### 9.10 Open after this pass

The all-99 producer requests (9.1); Jev's helper binding to the shared runtime (9.3); the reporter projection of `all99`
(work branch); `pod_agent.run_full_day` reading `facts['finish']=='waiting'` and `frankie_box_jev_cpu.execute` accepting
the REBOOK successor chain (standing requests, Codex-owned); `frankie_box_lane_state.py:619` kick scope; the inline policy,
worker setup, preflight and the one runtime install (9.8, Greg's decisions; a separate agent holds the account writes); the
remote voice acknowledgment interface stays listed as the unused fallback (`voice_route=local` is the plan). A fresh
independent review of these files is required before integration; nothing here is runtime evidence.

### 9.11 KeepRunning = "keep running only when in use" (Greg, 2026-10-07; source only)

Facts relayed: the main box was left running on its `KeepRunning=true` tag (about $51/day) after the 8A account pass;
Greg stopped it; the parent set `KeepRunning=false` on both boxes plus a `KeepRunningPolicy` tag. No idle guard was on
this branch. Built:
- `deploy/aws/idle_instance_guard.py` (NEW) and `.github/workflows/frankie_box_idle_guard.yml` (NEW, cron `17 */6 * * *`
  plus `workflow_dispatch` with `dry_run`; the runner's AWS secrets as `frankie_box_run.yml`): every Frankie box (the two
  instances by id, any `Name` starting `frankie-`) that is running with `KeepRunning` not `'true'` AND no fresh lane lease
  (`pod-root/<run>/controller/lease.json`, not released, heartbeat younger than 600 s; a fresh lease protects the worker
  lane always and the main box when its host is `main`; an unreadable lease protects) is stopped (`ec2 StopInstances`);
  everything else is left running; every instance, action and reason is in the JSON report (artifact). Nothing
  terminated, no tag changed.
- `pod_root/controller.py`: `keep_running(instance, region, value, reason, by)` (ec2 CreateTags `KeepRunning` +
  `KeepRunningReason`, failure named, never raised); `start_day` tags the worker `true` when the day's job started
  (event `keep_running`); `finish()` clears it to `false` on EVERY exit path (finished, failed, refused, lease lost /
  unestablished, budget, stop, signal) unless the worker's last-seen status shows a live job of the run (then left `true`
  with the reason, recorded on the outcome and the event journal); `preflight` adds the read-only `worker KeepRunning tag`
  check naming `ec2:CreateTags`.
- `frankie_box_experiment.py`: `this_instance()` (IMDSv2), `box_in_use(run)` (orchestrator starts alive, a line worker
  holding its lock, a CPU controller holding its lock: read-only), `keep_running(run, value, reason, by)` (tags this box;
  a clear is skipped and recorded as `kept` while `box_in_use` names something; every call appended to
  `<run>/keep-running.json`, `FRANKIE_KEEP_RUNNING_V1`, and printed). `main()` ACTION=start sets `true` before `Run.start`
  and asks for the clear in a `finally` (kept while the detached line workers run).
- `frankie_box_frankie_queue.py`: the `worker` action's `finally` asks for the clear at the line worker's end (the run's
  last work on the box); kept and named while anything else is in use.
Limits, named: a worker killed outright (SIGKILL, host reboot) leaves the tag `true` until the next worker end or a
by-hand clear; the guard then reports "KeepRunning=true: left running" so it is visible, never silent. The main box
needs `ec2:CreateTags` (own instance) in the inline policy of 9.8; the guard's runner keys need `ec2:DescribeInstances`,
`ec2:StopInstances` on the two instances and `s3:ListBucket`/`GetObject` on `pod-root/*`. Requests: the reporter's
`FIELDS` to project `<run>/keep-running.json` on the one-day inspection (work-branch `frankie_box_workflow_inspection.py`);
`pod_agent.py` (Codex) to clear the worker's tag itself at `day_complete` when no controller is attached.
Checks: AST on `idle_instance_guard.py`, `controller.py`, `frankie_box_experiment.py`, `frankie_box_frankie_queue.py`;
`yaml.safe_load` on the new workflow; `git diff --check`. Not run; no tag was changed by this pass.

## 10. The restart pass of 2026-10-07 late evening ("respawn and finish"; SOURCE-BUILT / RUNTIME-UNVERIFIED / UNREVIEWED)

Work branch `ccr-d2f8f826-iefeah-frankie` working tree over `05e97286` (the Step 8 branch merged; nothing committed by this
role). Skills: `api-and-interface-design` (Skill tool, first). No account call in this pass (the earlier survey stands). No
test, run, install, dispatch or account write. Checks: `python3 -I` AST parse of the 12 changed Python files, `bash -n` and
`sh -n` on the 5 changed shells, `json.load` on the runtime JSON, `yaml.safe_load` on `frankie_box_run.yml`,
`git diff --check` on every changed file: all clean. A fresh independent review is required before integration.

### 10.1 Greg's decisions applied

- **Jev uses ALL of Granite's settings** (`frankie_box_jev_cpu.py`): `bind_runtime` (replaces `runtime_check`; the
  `JEV_CPU_RUNTIME_V1` schema, `PROPOSED_JEV_CPU_RUNTIME_V1`, `approval_sha256`, `--propose`/`approved_example` are
  removed: review B1/B2). Every row is read at call time from `GRANITE_MEETING_RUNTIME_V1.json` through
  `frankie_box_granite_meeting.local_runtime`: weights, build, runtime path, temperature, top_p (injected on every chat
  body), context_size, max_output_tokens_per_turn, input_token_cap_per_call, the per-call ceiling (CALL_CEILING_SECONDS
  unless the definition sets one), max_meeting_seconds (per-process), completion (nothing over the cap is sent, nothing
  truncated, unparsed answers listed). Derived in code, one line each: min_output_tokens = max_output_tokens_per_turn;
  token_margin = context_size - cap - max_output (so the client refuses any prompt over Granite's cap and halves it);
  piece_chars = cap x 2. The only refusal: the shared runtime absent or its pins/files differing. The transport gets
  Granite's parameter rows verbatim (`server_params`).
- **Granite and Jev share ONE worker CPU of the day's lane** (`frankie_box_cores.py`: `STAGE_SLOTS`, `SLOT_CPUS`,
  `STAGE_CPUS`, `claim_step`, `attach_step`, `cmd_run_step`, `cmd_run_inside`, `cmd_run`): the 'adviser' slot = the
  highest worker CPU of the held booking (never the parent/coordinator), claimed under the ledger lock when voice or jev
  runs, released when it ends; the other stage WAITS in place while it is busy; the CPU_BOOKING line names the holder and
  the seconds waited (on the step receipt: `Run.jev` `adviser_slot`, `Run.voice` `inspection.inputs.adviser_slot`). Such a
  stage never books on its own (refused without `--inside`). threads = 1: Jev `JEV_THREADS`; the meeting through
  `MEETING_THREADS=1` (`Run.voice`) -> `frankie_box_granite_meeting.sh --threads` -> `frankie_box_granite_meeting._meeting(threads=)`
  (narrow edit, bound into the meeting binding). The helper checks its affinity is exactly its claim (`execute`).
  `Run.voice` without a held day slot records waiting, non-blocking, named. `'survivors'` joined `DAY_RUN_STAGES`.
- **No days on the small box**: the worker-box lane is a LISTED, UNUSED FALLBACK (`pod_root/controller.py` main:
  loop/resume refuse without `--fallback-route worker_box`; `frankie_box_cpu_controller.sh` start/resume require
  `FALLBACK=worker_box`; `frankie_box_run.yml` loop/resume require `FALLBACK=worker_box`; `frankie_box_pod_root_loop.sh`
  header). The default lane set is the main box's two lanes (`PARALLEL_DAYS=2`, unchanged). Nothing starts the worker.
- **The native pass ON for every NEW request** (Greg reversed the 2026-09-29 no-bedrock decision): `main()` defaults
  `--shared-market-policy` to `FRANKIE_SHARED_MARKET_TIMELINE_V1` when the run has no saved plan; a run with a saved plan
  keeps exactly its saved value (never mutated). Under the policy the ROOT wrapper passes `--bedrock on`
  (`frankie_box_experiment_root.sh`, confirmed). `frankie_box_experiment_root.py`: `--bedrock` default `on`, function
  defaults `bedrock=True`, docstring; the resume branch calls `Session.native_layer_records()`; the legacy pin rule text is
  kept byte-identical (an older saved plan's pinned bytes). `frankie_box_monday_calculations.py` docstrings corrected.
  `Run.root` records `seconds` and `native_pass` (`native_pass_facts`: requested, derivation bedrock record, timings,
  ledgers, ROOT child wall seconds; the ADDED time is unmeasured until a bedrock-off ROOT of the same day exists).

### 10.2 Review findings fixed (REVIEW_20261007_EVENING_SLICES_AND_READINESS.md)

B1/B2 above. B3a: `frankie_box_frankie_queue.kick` writes `<line>-kick.json` and waits up to `KICK_LOCK_WAIT_SECONDS`
for the worker's lock; `frankie_box_experiment.box_in_use` counts a kick younger than `KICK_GRACE_SECONDS` (not the kick that
started the ending worker: `PROCESS_STARTED`), running/unknown entries of any run, queued entries with a live or just-kicked
worker, and an unreadable queue (SystemExit included) as in use. B3b: `idle_instance_guard.protects` (any fresh or
unreadable lease protects BOTH experiment boxes) and `still_idle` (re-describe right before StopInstances). B3c:
`controller.finish` keeps the worker tag on when the job state is UNKNOWN (a submit/resume with no reachable worker status
newer than it: `last_submit_at`, `at_epoch`; an unresolved resume). B5: a `not_run` search makes `Run.jev`,
`Run.accumulated_lessons` and `Run.exchange` record `not_run` (listed); `Run.voice` passes it on; `Run.school` accepts it.
N2: stage 10 wired (10.3). N3: per-entry carriers from the one registry; A-clean `not_applicable`. N5: Jev's exchange-context
path `out.parents[3]`. N6: `GRANITE_MEETING_RUNTIME_V1.json` `settled.hosts_in_order` (local child first) and
`hosts_superseded`.

### 10.3 Cross-owner requests implemented here

- `Run.lessons`: each teacher call carries `receipt` (its printed last JSON line, `last_json_line`); after the batch record,
  `Run.survivors` (stage 10, `frankie_box_survivor_update.sh`: RUN, BOUNDARY_DAY = the batch's last day, BATCH_DAYS,
  BRAIN, SEARCHES of finished searches) on the held lane, recorded as stage `survivors` under the batch key (receipt path
  in `batches/`), bound to the printed `FRANKIE_SURVIVOR_UPDATE_RECEIPT_V1` (schema, run, boundary day). A batch of one day
  is a boundary. Also run for a batch whose lessons finished earlier (start loop; queue `_finish_steps`).
- `Run.school`: `missing_listed`, `withheld_listed`, `workflow_report` copied onto the step record.
- `Run.reports`: `RUN_DIR`, `CANDIDATES_RECEIPT` (the batch's survivors receipt), `CARRIED_CLAIMS_RECEIPT` (accumulated
  lessons), `JEV_RECEIPT`, each only when its stage finished with it.
- all-99: `all99_crosswalk`/`all99_admission` import the ONE registry (`frankie_box_all99_coverage.registry`,
  `MARKET_CARRIERS`, `NATIVE_ENTRIES`, `FIXED_WORDS`, `NOT_MARKET_CARRIED`, `CARRIER_ELEMENTS`); `ALL99_GROUPS`,
  `LEGACY_CARRIER` and the local `CROSSWALK` are gone; `work/native-layer-records.json` is read when bound to derive.json;
  the 18 native-only entries are listed with what was admitted (`native_only`); the shared field `FRANKIE_ALL99_COVERAGE_V1`
  (`A99.field('root', ...)`, validated) is on the ROOT receipt as `all99.coverage`, its counts/validation in
  `all99_summary`.
- `Run.jev`: the request may carry `shared_market_context` (the exchange's retained read, when it exists at request time).
- `frankie_box_jev_cpu.py` REBOOK chain: `request_chain`, `bind_owner`, `_comparable`; `Run.jev_rebooked` mints a successor
  that RESUMES retained progress on the same output under the original owner identity (recorded in `rebook-<n>.json`);
  `Run.jev` binds every link's pin; `main()` writes status for a chain link.
- `frankie_box_lane_state.learner_knowledge`: a per-document `current_document` ValueError is listed
  (`withheld_not_current`), the selection goes on; source integrity still raises. The kick at the `class_done` branch
  already carries the run's plan scope (verified).
- `frankie_box_teacher_knowledge.teach_accumulated`: `ST.test(report=)` into the result's `evidence_read` (excluded from
  the reuse header comparison).
- `pod_agent.run_full_day`: `facts['finish'] == 'waiting'` is state `finish_waiting` (exit 3), not a failure;
  `release_keep_running` at day_complete clears the worker tag only when no controller renewed the job within 1200 s
  (`controller-renewed.json`, written by `renew_job`) and no other live job runs.
- `frankie_box_granite_meeting.sh`: unset LLAMA_SERVER/GGUF_MODEL -> `--route local` (the gate refuses visibly);
  `INPUTS_ONLY=1` stays the only inputs-only switch. `Run.standing_voice` keeps such a refused record standing while the
  shared runtime is refused.

### 10.4 Requests to other owners

- workflow_reports, `frankie_box_all99_coverage.py`: a vocabulary word for an evidence integrity failure (the ROOT passes
  piece word `integrity` with canonical `unknown` meanwhile); the stale "bedrock off" wording at lines ~20 and ~244.
- workflow_reports, `frankie_box_workflow_inspection.py` FIELDS: project `root.native_pass`, `root.seconds`,
  `root.all99.coverage`/`native_only`, `jev.adviser_slot`, `voice.inspection.inputs.adviser_slot`, the `survivors` step
  (batches/<key>/survivors.json), `lessons.calls[].receipt`, `school.missing_listed/withheld_listed/workflow_report`,
  `<run>/keep-running.json`.
- workflow_reports, `frankie_box_experiment_search.py` lines 3 and 65 and `frankie_box_market_timeline.py` lines ~293, ~353,
  ~360: replace "bedrock off" as the experiment's expected state with "the native pass is ON for every NEW run (Greg
  reversed the 2026-09-29 no-bedrock decision); absent only when the pass did not complete or an older saved legacy plan
  ran it off".
- Codex / Session owner, `frankie_box_experiment_root.py` + `frankie_box_boss_session.Session.derive`: a native traversal
  that raises still fails the whole ROOT; under the missing-coverage rule it should be recorded in derive.json (bedrock
  status failed, reason) while the legacy pass completes, so the day stays with a thinner picture.
- Codex, `frankie_box_granite_meeting.resolve_threads`: `threads: null` resolves to `os.cpu_count()` (the HOST, 32 on the
  main box), not the affinity; any caller that does not pass `--threads` refuses at start inside a 16-CPU lane.
- Account (parent): the worker role lacks `ec2:CreateTags` (pod_agent's clear is recorded as `not_cleared` until it has it).

### 10.5 Bedrock hits (deploy/aws/box, .github/workflows, pod_root)

Changed: `frankie_box_experiment.py` (docstring, absent reasons, legacy plan wording, `--shared-market-policy` default and
help), `frankie_box_experiment_root.sh` (header, the legacy-only comment), `frankie_box_experiment_root.py` (docstring,
defaults, argparse), `frankie_box_monday_calculations.py` (two docstrings, `--bedrock` help). Left, with why: the legacy
pin rule text and phase label in `frankie_box_experiment_root.py` (an older saved plan's pinned bytes/label);
`BEDROCK="${BEDROCK:-off}"` for an empty policy (older saved legacy plans only); `bedrock=False` in
`write_retained_digest`/`render_digest`/`digest_bedrock=False` (the giant rendered tables, not the native pass); the
digest/projection/side-builder/cleanup modules and `boss_bedrock_integration.yml` (the bedrock table machinery, not a
default); `frankie_box_boss_session.py` (already corrected by its owner in `05e97286`); the workflow_reports files listed
in 10.4; `frankie_box_run.yml` hits are lock/script names.

### 10.6 Open (not runtime evidence)

Everything above is source-built only. Jev's and the meeting's 400-output-token, 8192-input-cap budgets are Granite's and
untested for Jev's claims answers (halving, more calls); the native pass's added time per day is unmeasured; the shared
adviser slot's wait has never been observed; the worker-tag clear needs CreateTags; the 8A dependencies and the remote
voice acknowledgment stay as named in sections 5 and 9. A fresh independent review is required before integration.

### 10.7 The model-evaluation clock from Jev's real calls (Greg approved; late addendum)

`frankie_box_jev_cpu.py`: `model_clock` (one `FRANKIE_MODEL_EVALUATION_CLOCK_V1` record per real call, through
remaining_consumers' `frankie_box_model_clock.record_call(run_dir, day, record)` into `<run-dir>/days/<day>/model-clock.jsonl`;
the module was NOT on disk at this pass, so the call is coded against that name and the parent reconciles the exact
signature; until then, or on any helper failure, the same record lands in `<out>/model-clock-unrecorded.jsonl` with the
reason, never silent). Recorded in `_run`: every chat (`chat`: answered with the reply sha256, or failed with the reason
and whether it was sent), every token count over Granite's input cap (`counted`: refused_over_cap with the count; the
client then halves the input), a failed count/server start (failed), and a refused shared runtime (not_called). Each
record: piece jev, call id (sha256 of the request body or messages), model/runtime pins (release, pins sha256, model
identity, quantization, config pin, threads, CPU), the exact market cutoff of the material (the classroom teacher
binding: source_hash, as_of, through_cursor; listed when absent), wall start/end, outcome, run/day/lane. A replayed
recorded reply is not a call and is not recorded. AST and diff-check clean.

## 11. Second-review fixes, partial pass (`08e2553`, 2026-10-07; recorded here because that pass ended before its record)

Review: `REVIEW_20261007_EVENING_SECOND_PASS.md` (F1-F11). Done in `08e2553` (SOURCE-BUILT / RUNTIME-UNVERIFIED):
- F1 (a) `Run.jev_done_receipt`: a done Jev receipt whose request is the day's retained request (or a `.rebookN`
  successor) with matching bytes and a done `JEV_CPU_RECEIPT_V1` is returned unchanged; `_finish_steps` reads a finished
  Jev back instead of rebuilding it on a later booking. (b) the queue's `_rebook_owner`: a WAITING finish keeps its owner
  binding (attempt, marker, source) with a recorded queue rebook decision and `held_bookings`; `Run.jev_rebooked` accepts a
  booking this same owner held.
- F3 inspection on every outcome: `_finish_day` runs the day inspection when a step raises (then re-raises) and on any
  SystemExit; `Run.start` inspects the days a disk-floor stop left, the trigger naming the stop.
- F8 `shared_teacher_compatible`: an unreadable day file waits; a malformed one is an integrity refusal.
- F10 the reporter is pinned by `taskset -c` in its command (no `preexec_fn` in the threaded process); unpinned when
  taskset is absent, named on the receipt.

## 12. Second-review fixes, completing pass (2026-10-07 night, session 2; Greg restarted Step 8, relayed by the parent)

Base: work branch `ccr-d2f8f826-iefeah-frankie` at `64e6335` (over `08e2553` and correction_consumer's `cceb191`); this
pass is uncommitted in the working tree and is committed by the parent by path. Source only: nothing ran, no account call.

### 12.1 Fixes, each in the file the finding names

- **F2** `pod_root/controller.py` `start_day`, IfNoneMatch 412 path: after re-signing the retained job's input GETs and
  mailbox, the job is written back to the same `job.json` key (no IfNoneMatch, SSE AES256), as `renew()` does, because the
  worker reads the job body from `_job_url`, not the submitted dict. The identity check above it is unchanged; the lease
  was established for `submit` just before.
- **F11** `pod_root/controller.py` `handle`: a `LeaseNotEstablished` deferral is not a try. It is recorded `deferred`
  (once per streak, `self.deferred`), never `failed`, and does not count toward the two-try give-up; every other outcome
  counts as before (`finally`). A lease re-established later in the same process still releases and cleans the failed job.
- **F6** `frankie_box_successor_dispatch.drain`, waiting_school branch: after a complete recovery the reports disposition
  is one of `not_applicable` (day not in the plan), `not_rendered` ("no reports rendered yet; the reports stage renders on
  the current school"), `exchange_not_done`, a reports revision (`Run.reports_stale` then `guarded('reports')`), or
  `current`. `current` is recorded only when done reports exist on a done exchange and are not stale.
- **F7** same branch: at most one `complete` owner school recovery per operation per drain call (`school_completed`). A
  second `waiting_school` in the same call records `waiting` with "the school stage ended done but the chain still
  requires a successor (one complete recovery per operation per drain call)", the previous recovery attached, sleeps the
  ordinary 5 s and breaks; the next drain call tries once more. No second school child dispatch inside one call.
- Comment drift (second review FYI): the waiting_school comments, `close_day`'s docstring, `Run._school_recovery`,
  `Run.successors` and `Run.recover_school` now say drain.lock (not "the inbox lock") and "close_day's one drain" (not its
  loop).
- **F4 consumer** `frankie_box_experiment.all99_admission`: it already read `work/native-layer-records.json` when bound to
  derive.json's sha256 (`725dffd`). Added: every calculation/clock row names its `basis` (`derive_layer_record`,
  `native_layer_record`, `group_proxy` or `no_record`); the group-proxy fallback's reason starts "GROUP PROXY (no per-layer
  record used: <why>)" and `native_only.records.group_proxy` lists those entries. Every row carries `canonical` (the shared
  vocabulary word) and `class` from `frankie_box_all99_coverage` only (FIXED_WORDS first, then LEGACY_WORDS), and the list
  carries `counts_canonical` (also in `all99_summary`). The ROOT word stays in `disposition` because the day reports read
  it (`admitted` refines to `picture`, never `computation`); it is the shared field's `piece_disposition`. An integrity row
  is now `integrity_failure` in the shared field (it was `canonical='unknown'`, which relabelled an integrity failure).
  `a_clean_promoted_positive_capsule` is `not_applicable` (FIXED_WORDS; NOT_APPLICABLE in the crosswalk, not Memory A).
  `frankie_box_workflow_inspection.artifact_paths`: the root piece also follows `work/native-layer-records.json`.
- **Gap from 08e2553** `frankie_box_frankie_queue.root_worker`, ROOT-and-finish-in-one-slot route: a `failed` finish now
  releases its owner binding (`_release_owner`), exactly as the finish-only route does. Kept, the owner pinned the retry
  to the exact CPUs of a booking the thread's end had released (`_book_slot` books `owner['cpus']`), so the retry waited
  on whichever day took them. The retry binds afresh: `root_of` names the same completed ROOT attempt, any free 16 CPUs.
  This is the review's F1(b) rule (keep the binding on `waiting`, release it on `failed`). Consequence, named: a done Jev
  is read back (`jev_done_receipt`); a failed or still-pending Jev request bound to the released booking is refused on the
  new booking (no REBOOK decision; `ACTION=resume REBOOK=on` covers saved/unknown days only). A failure is not a wait.
- **jev_cpu SI.LOCAL** `frankie_box_jev_cpu._run`: `SI.LOCAL['model_clock']` is supplied (`client_clock`), so sit_in's
  no-room refusal (decided in the client after the exact count, never sent) is a `FRANKIE_MODEL_EVALUATION_CLOCK_V1` record
  with the same runtime pins, cutoff and lane as the real calls, `decided_by` named.
- **GRANITE_MEETING_RUNTIME_V1.json** (documentation fields only, schema unchanged): `threads_rule` states the code's rule
  (null = the claimed adviser slot, one lane worker CPU shared with Jev, threads=1; never the host count; an integer
  clamped to the owning affinity), the 2026-10-06 wording named as superseded. N6: `settled.hosts_in_order[0]` already
  named the local route first; it now also says main box only (`i-035994afa8bdf66a5`). The file's sha256 changes; no run
  has pinned it.
- **N1** `frankie_box_experiment_classroom_v2.py`: the journal witness handed to `SharedMarketTimeline` carries `path` and
  the measured file's `dev`/`ino`. The reader's `_caller_witness` already requires the path to be the pin's path (or the
  same file), the size to equal the pin and dev/ino when given. Before, the path was stripped, so the classroom's
  measurement was never accepted and the reader re-hashed the journal (safe, slow).
- `frankie_box_granite_meeting.py` voice path: the meeting record carries `knowledge_listed` (`selected['listed']`: what
  the knowledge selection left out and why). Not part of the meeting input; its identity is unchanged.
- **correction_consumer's request** `frankie_box_experiment_root._calculate_day`: passes `bedrock_off_cause` to
  `Session.derive` (cceb191). With bedrock off and no stated cause: `legacy_plan` without the shared market policy,
  `caller_override` with it. This route has no native-failed fallback, so it never states `native_pass_failed`. New CLI
  flag `--bedrock-off-cause {caller_override,legacy_plan}`. Bedrock on: no cause, derive.json unchanged. The `.sh` carries
  no such flag and is unchanged.

### 12.2 Not done this pass

- `Run.reports_stale` is not wired to `late_pieces_changed` (the parent's instruction: correction_consumer is building it in
  `frankie_box_experiment_day_reports.py`; the contract comes through the parent).
- First review B5 (a `not_run` search leaves Jev waiting): fixed in `725dffd` per its record; not re-checked here.

### 12.3 Checks

AST parse without project imports clean on the nine changed `.py` files; the JSON parses; `git diff --check` clean on all
changed files. SOURCE-BUILT / RUNTIME-UNVERIFIED / UNREVIEWED. A fresh independent review is required before integration;
this self-review does not replace it.

## 13. Late pieces wired, meeting refresh invocation, day_coverage counts (2026-10-07 night, session 2; after `c2d4f4d`)

Base: `c2d4f4d` (my `9fbdc4d` and correction_consumer's `c2d4f4d`, which defines `late_pieces_changed`). Uncommitted;
source only; nothing ran; no account call.

- `frankie_box_experiment.py`:
  - `Run.reports_invocation(day, c=None, cls=None)` is now the one builder of the day reports' environment. `Run.reports`
    renders with it and `Run.reports_stale` checks with it, so the check never compares against an invocation the render
    would not use. Behaviour of `Run.reports` is unchanged (`DAY_CLASS` falls back to the plan entry's class).
  - `Run.reports_stale`: the early `return False` on a not-done exchange is gone. The exchange-returned, school and
    meeting checks still apply when the exchange is done; then, whatever the exchange's state,
    `Run.reports_late_pieces` calls `late_pieces_changed(reports_receipt_path(REPORTS, run, day), current)`, with
    `current` carrying every INVOCATION_KEYS key (None included, so nothing falls back to the recorded value).
    `changed` returns True (a revision under the same number); `unknown` returns False and logs its reason; a failure of
    the check itself is an unknown.
  - The result summary (outcome, reason, differences, reasons_only count, invocation source, recorded/current join
    sha256, checked_at) is written onto the reports step receipt as `late_pieces` and inside its `inspection` (which the
    reporter projects whole), only when it differs from the recorded one. It is a direct durable rewrite of the same
    receipt, not `record()`: no new attempt, no knowledge boundary.
- `frankie_box_lane_state.py` meeting refresh (`import_meeting_record`): `R.run` now gets `school` / `school_listed` (from
  the school step receipt, the same rule as `reports_invocation`), `run_dir` (the owner run directory) and
  `piece_receipts` (the last build's recorded `all99_invocation`), so a refresh keeps the candidates / carried-claims /
  Jev lists in the join. When no invocation is recorded, none is passed and the reason is kept on the reports step as
  `meeting_refresh_invocation.listed`.
- `frankie_box_all99_coverage.day_coverage`: `counts` keeps every DISPOSITIONS key and now also counts every other word
  present (the clock override words), so the counts sum to the entries listed. Additive.

Checks: AST parse clean on the three files; `git diff --check` clean. SOURCE-BUILT / RUNTIME-UNVERIFIED / UNREVIEWED. A
fresh independent review is required before integration.

## 14. The fresh review's required items R-A, R-C, R-D and nits N-1, N-3 (2026-10-07 night, session 2; review `fb97f35`)

Base: `fb97f35` on `ccr-d2f8f826-iefeah-frankie` (the integration push is held for Greg). Uncommitted; source only;
nothing ran; no account call. R-B belongs to the day-file agent and is not touched here.

- **R-A** (late pieces never revised the reports):
  - `frankie_box_frankie_queue._finish_steps`: after Jev ends in `X.FINISHED` and before `_close`, `run.reports_stale(e)`
    then `run.guarded('reports', e)`, in the same slot, no model call. The outcome is in the finish facts as
    `reports_revision`. A check that raises (a corrupt school chain) is listed `not_checked` and never stops the close.
  - `Run.survivors`: after a done boundary, every classroom-arm day of the batch whose reports step is done gets
    `reports_stale` then `guarded('reports')`. A revision's failure is that day's reports receipt; it is logged and never
    changes the boundary's outcome.
- **N-1** `Run.reports_late_pieces`: re-reads the reports step immediately before writing and writes only when its `at`
  is the one read. A render recorded meanwhile is never written over; the next check records the result.
- **N-3** `frankie_box_successor_dispatch` waiting_school branch: the `exchange_not_done` disposition now also runs
  `reports_stale` (the late-pieces check). A changed join gets its revision there, the exchange's state named.
- **R-C** (a failed finish released its owner, so a failed Jev was refused forever):
  - `_release_owner(..., failed_finish=True)` on both the finish-only route and the one-slot route keeps the released
    owner's bookings as `failed_finish_bookings`.
  - `_bind_owner` (the retry, new owner) consumes them once. When `_jev_progress` finds the day's retained Jev request
    with no progress (the step receipt names a request, Jev is not finished, its helper receipt is absent or `failed`),
    the new owner carries a `rebooked` decision `by='queue-after-failed'` with those `held_bookings`. `Run.jev_rebooked`
    then mints the create-only `.rebookN` successor; the original request is never changed.
  - Otherwise the decision is recorded under `owner_rebooks` with `not_applied` and its reason: no request, Jev
    finished, unreadable helper receipt, or a helper receipt in another state (the owner decides).
- **R-D** `frankie_box_experiment_search._discovery_compute` (assigned to me for this pass; normally Codex's file): when
  the problem's result file already exists, it is read back and its pin returned (`read_back` named), never recomputed.
  It stands only when it is this exact problem: schema, id, cell, cell value, target, features, seeds and regressor
  settings. Anything else is retained and refused, as before. I chose this over dropping `seconds` because a fitted
  problem is not reproducible across processes either.

Checks: AST parse and `git diff --check` clean on the four changed files.

SOURCE-BUILT / RUNTIME-UNVERIFIED / UNREVIEWED. A fresh independent review of these fixes is required before
integration.
