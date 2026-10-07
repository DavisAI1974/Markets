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
