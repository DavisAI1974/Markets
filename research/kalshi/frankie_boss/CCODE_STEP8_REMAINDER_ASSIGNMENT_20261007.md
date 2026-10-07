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

### Addendum — shared market timeline and Jev CPU callers (02:35 ET)

Greg explicitly authorized building a synchronized market input on 2026-10-07. Raw and
derived calculations may execute out of order; Frankie, both teachers and other advisers
must receive applicable evidence together on its faithful causal timeline, within existing
role/private/answer boundaries. Preserve original input order, exact event/receive clocks
and the actual availability of later calculations. Do not backfill future-dependent results
into earlier live state. The existing separate processing is useful; this adds the fullest
coherent picture. A registry reference or a stored file is not proof of that presentation.

Codex's timeline agent owns `frankie_box_market_timeline.py`, the journal/native/search
readers and the narrow `frankie_box_experiment_root.py` / `.sh` policy forwarding. Its source
implementation is underway, not yet a published or verified all-99 consumer. CCode keeps
the `Run.root` / plan caller. The agreed interface is
`SHARED_MARKET_POLICY=FRANKIE_SHARED_MARKET_TIMELINE_V1`, forwarded by the ROOT wrapper as
`--shared-market-policy` and `--bedrock on`. Persist the requested policy with the original
plan/attempt and carry it through local and Linux dispatch/recovery. Fetch the completed
source contract before wiring or acknowledging completion. Check it before every retained
ROOT fast path: a legacy bedrock-off result does not satisfy a new shared-policy request.
Preserve old artifacts/attempts; use explicit compatible successor handling, never silently
change an old request or recompute completed science. An omitted legacy policy keeps its
actual legacy coverage and must not be presented as the new shared view. This narrow,
explicitly requested source wiring supersedes the prior no-producer-activation instruction
only for this named route; no runtime start or general scientific change is authorized.

Codex's Step 7 owner has also drafted `frankie_box_jev_cpu.py` / `.sh`; independent review is
underway. Read the final published `STEP7_CPU_CONTINUATION_20261007.md` and caller supplement
before integration. `Run.jev` must retain `JEV_CPU_REQUEST_V1` before calling the child with
`JEV_REQUEST`; add `jev` to `cores.DAY_RUN_STAGES` so it inherits the exact existing 16-CPU
booking. It uses a required explicit worker subset of that lane, not another host/booking.
Preserve original run/day/discovery-role/attempt/owner/source/plan/marker and exact input
pins. Do not substitute an orchestrator step receipt for the classroom producer receipt.
The child returns 0 only with its exact `JEV_CPU_RECEIPT_V1`; 5 is waiting/unknown and 75
requires a checked `JEV_CPU_STATUS_V1` save acknowledgment with current marker/child/owner
bindings. A missing runtime choice is waiting, never skipped or done. Exact runtime/model
pins and budgets are still pending setup, not values to borrow from Granite. Checked peer
Jev knowledge may enter via pinned owner-local `prior_brain` entries/lessons; do not assume
a foreign lane's absolute path is shared. Final source may refine details during review.

### Previously assigned caller integrations

The reviewed Step 7 helper and full `CCODE_STEP7_CALLER_SUPPLEMENT_20261007.md` are now
published at `523336f`. Its Jev-only peer namespace uses the existing snapshot transport;
run the normal knowledge boundary before selection and after completed local delivery,
including a delivery whose comparison disposition still leaves Jev waiting. Step 5's
standalone affected-only correction owner is published at `2c332df`; preserve its new
dispatcher branches when adding your narrow non-reentrant `waiting_school` callback.

**Granite remote admission caller:** read `STEP6_COMPLETION_20261007.md` when published.
The retained runner intake/return is being completed, but a fresh GitHub dispatch can
otherwise duplicate an unresolved meeting. Complete the existing `Run.voice` owner
boundary: persist original exchange/source/config/run/day/owner and predecessor archive
intent before dispatch, retain/reconcile the exact original GitHub run identity, and
admit that exact run before model setup/start. Unknown dispatch is reconciled, never
resent under a new identity. A predecessor's complete state and stopped process must
be established before admitting continuation. Return through the existing owner importer.
Coordinate the exact acknowledgment interface with the Granite runner owner; do not
invent a new scheduler, S3/Git lock service or different hosting policy. Until this
contract is wired, the remote workflow allows inputs-only and verified completed-record
replay, and refuses new model calls. Existing configured owner-local meeting recovery
remains available. This is an open caller dependency, not completed Step 6 or execution
authorization. Source ownership includes these narrow `Run.voice` integrations; Codex
owns the matching Granite runner helper/workflow changes and will review the interface.

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
