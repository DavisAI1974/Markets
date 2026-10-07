# CCode: finish the remaining Step 8 source work

Greg, 2026-10-07 01:49–01:51 ET: CCode only did Step 8A; give him the rest while
Codex works on other workflow pieces, then have an independent agent review his return.
This assignment supersedes the old Step 8A-only ownership restriction. It does not assign
the entire workflow to CCode or describe Steps 2–7 as complete.

## Branch and starting state

- Integration: `ccr-5fce7de3-xa4hfg`; starting tip `e86a6adfb6b149e47445bac4a99b1add5e643d32`.
  Fetch its ACTUAL current tip first; this assignment and concurrent Codex work advance it.
- CCode: `ccode/teacher-tasks-20261006b`; reviewed Step 8A return
  `954f3f356aff41fd0bccb483e1cfdcb539efd9ef`, based on `439cb0bf71968f30f94b696b85acfaa00dccc3c1`.
- The six Step 8A commits have NOT been merged into integration. Preserve them and newer
  work when bringing the latest integration changes into your branch. Do not reset away
  either side's commits. Resolve documentation overlap with this assignment authoritative.
- Codex's local main-recovery agent stopped BEFORE making any edits. Main recovery ownership
  is now yours. Other Codex agents continue correction/school consumers, full-workflow
  inspection reporting and bounded scientific-reader improvements on disjoint files.

Read `AGENTS.md`, `CODEX_HANDOFF_20261007_WORKFLOW_CONTINUATION.md`, your
`CCODE_STEP8_CPU_CONTROLLER_20261007.md`, `STEP1_MODULE_REVIEW_20261007.md`,
`STEP8_MODULE_REVIEW_20261007.md`, and section 0 of `SPEC-experiment-orchestrator.md`.
Apply `using-agent-skills`, context-engineering and API and Interface Design to the modules.
Use existing efficiency/recovery mechanisms and recorded AWS workflow research first.
AWS tools in Codex's current session require reauthentication; do not describe that as a
successful fresh AWS skill/tool call. If your connection works, documentation-only research
is permitted; no account operations or new services follow.

## 1. Correct the three Step 8A integration findings

Independent source review of `954f3f3` requests these changes in `pod_root/controller.py`:

1. **Lease freshness at effects.** `heartbeat()` marks loss only on HTTP 412. Other renewal
   failures can outlast the 600-second lease; another controller can take over while the old
   one continues. `_worker_loop()` checks loss only at iteration entrance, including before
   an export that may take hours. Track successful lease-renewal freshness and stop when
   current ownership cannot be established. Guard mutation boundaries, including submission
   after export, claim, renewal and coordination. Preserve unknown outstanding effects and
   the original owner/attempt; do not release or retry another controller's work.
2. **Resume uncertainty.** `check_resume()` catches errors after `renew()`/SSM and records
   `resumed=False`, refused, and inputs untouched. A timeout may follow a real launch and
   transport metadata may already be rewritten. Record unknown/pending and reconcile the
   original attempt through its worker status before acknowledging a definite outcome.
   Do not automatically redispatch an unresolved resume or erase its request evidence.
3. **Exit outcome.** `run_serving()` currently exits nonzero only for `worker_unreachable`.
   Recorded `failed`, `lease_lost`, and `blocked_by_start_failures` must not become a green
   runner exit. Keep normal budget/stop outcomes distinct from scientific day completion.

Review anchors refer to the functions, not line numbers that may shift. Existing lifetime,
conditional lease, original-claim retention and retired-Pod refusal improvements remain.

## 2. Complete the coherent main/class save-resume contract

Own the entire boundary rather than adding exit-code-only handling:

- Persist the existing queue entry's run/day/host/original attempt/source commit and code
  root/exact 16-CPU set/booking/day-specific save marker BEFORE dispatch. Each concurrent
  `Run` must have its own marker and child environment; never mutate a process-global
  environment variable across day threads.
- Supply the original main attempt to `Run.root`. Reuse the exact retained attempt on
  resume rather than selecting the latest directory or minting a replacement attempt.
- `_root_job`, `_finish_job`, the class worker and reconciliation must distinguish saved,
  failed, running, done and unknown. Exit 75 is not failure/requeue. Preserve original
  claim/source/CPU identity and exclude saved/uncertain work from ordinary admission.
- Carry the same owner binding into the independent class process. The parent must wait
  for a saved-child acknowledgment bound to the exact marker, child, booking and attempt.
  A SIGTERM exception, child disappearance or missing receipt is not an acknowledgment.
  Bind acknowledgment to the current immutable save-request identity/generation so a
  previous save's marker or acknowledgment cannot satisfy a later save.
- Integrate the CPU ledger's dead-process reaping with explicit retained ownership. Do not
  let another day claim saved CPUs, and do not silently rebook a missing live classroom
  slot. Recovery of a saved owner must reconcile the named retained CPU set and its source.
- Preserve existing continuation/checkpoint writers and completed work. No failure retry
  substitution, blanket exception suppression, duplicate dispatch, claim clearing or
  scientific rerun to repair bookkeeping. Keep the existing stop-before-kick protections.
- Expose exact owner-bound save/status/resume through existing entrypoints; report pending
  acknowledgments truthfully. Stop/save must not bypass an unfinished Jev dependency.

## 3. Scope global queues to the authorized run and days

`Run.start`/`Run.kick` currently operate global queue workers. Bind admission and dispatch
to the exact authorized run/day scope, including class work and restart/recovery paths.
Compare an already-running worker's persisted run/day/plan scope before returning
"already running"; the process-lock fast path must not bypass scope enforcement.
A one-day request must not admit unrelated pending days from this or another run. Preserve
FIFO within the eligible scope, retained owner claims and submitted randomized day order.
Do not delete unrelated queue entries or expand the authorized scope on restart. Carry the
same exact scope through the Linux controller route where applicable. No second scheduler.

## 4. Small shared-runner integrations

- `Run.previous_of`: persist non-queue predecessor selection (including explicit none) in
  the existing continuation before first child dispatch; retries must not repick a newer
  classroom and invalidate the original request. Existing queue pinning stays intact.
- `Run.teacher_knowledge`: bind new summaries to the exact relevant producer identities.
  Changed/unestablished producer identity requires explicit checked successor handling,
  preserving the old result; no automatic historical regeneration or invented provenance.
- School consumer change is being built by Codex in `frankie_box_school_knowledge.py`.
  Its proposed `retained_school(brain, day)` returns `None`, or `{row, original, content,
  corrections, status}`. `row` is the immutable original index row; `original` is the latest
  checked complete school's path/bytes/sha256 witness. `status='complete'` permits reuse
  using that checked path and witness, carrying corrections. `requires_successor` requires
  the ordinary school child (the school owner rebuilds from the original). Propagate the
  child's `successor` and `correction` fields into the run's school receipt. Do not swallow
  corrupt bindings. Fetch and read the final helper/report before implementing this call.
  Coordinate if the interface changes; do not edit the school owner implementation.
- The completed source contract is in `SCHOOL_RECOVERY_CONTINUATION_20261007.md`.
  `successor_dispatch.rebuild_dependents` returns `waiting_school` with the exact recovery
  intent. Wire existing voice then school under that owner/day/held lane without recursive
  successor draining, preserving save/currentness/source/allocation checks. Then retry
  dependent recovery and deliver the checked school correction to original-session requests.
  CCode owns the narrow `drain` waiting-school invocation branch in
  `frankie_box_successor_dispatch.py` for this integration, plus the matching `Run` methods.
  The rest of that module and the school owner/review implementation remain Codex's.
  Guard finished/report reuse against superseded school content; retain old report artifacts.
  Fetch the actual published school source and report before wiring; do not implement from
  this summary alone or describe the waiting state as completed recovery.

## Ownership

CCode retains the four Step 8A implementation boundaries and now owns:

- `deploy/aws/box/frankie_box_experiment.py`
- `deploy/aws/box/frankie_box_frankie_queue.py`
- `deploy/aws/box/frankie_box_cores.py`
- Necessary narrow launch/claim plumbing for those interfaces, after naming exact files
  and checking concurrent source. Keep unrelated functions and science unchanged.

Codex owns school knowledge, experiment review, successor dispatcher, principal adapter,
BOSS session, scientific teacher, teacher knowledge, search/native/journal consumers,
one-time inspection reporter, and Jev runtime/model decisions. Request narrow cross-owner
interfaces rather than overwriting them. Granite pins and science remain unchanged.

## Verification and return

Source/interface review, AST parsing without project imports, and `git diff --check` only.
No extra tests or validator framework, installs, model/data/scientific/historical runs,
AWS account inspection/actions, starts, dispatch, canaries or E2E. Exactly three held
16-CPU lanes (15 workers plus coordinator each), no Pods, keep giant evidence owner-local.
No new mathematical mapping, objective, lag policy, model lineage or producer activation.

Commit and push with `[skip ci]`. Return exact tip/commits, changed files, owner and save
protocol, scoped-dispatch contract, pending/unknown failure handling, source checks and
remaining concrete dependencies in `CCODE_STEP8_REMAINDER_RETURN_20261007.md`. Update the
Codex-facing handoff/drop-in. Codex will use an independent review agent on the actual
returned diff before integration; CCode self-review does not replace that review.

The rollout remains: finish wiring/discussions, authorized E2E, ONE full-day input/output
inspection, review/adjust, then THREE days. Thirty days remain a separate decision.
