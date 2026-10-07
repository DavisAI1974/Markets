# Independent review, second pass: the parts the first review left UNVERIFIED (school_recovery, 2026-10-07)

Reviewer: school_recovery, acting as an independent reviewer. Greg asked for this role to be resumed, and the parent
relayed the request (Phase C: cross-review of work this role did not author). This review is read-only. It fixes
nothing; the owners carry the fixes. No git write commands and no account calls were made. This file is the only
file written.

What was reviewed: the committed state of `ccr-d2f8f826-iefeah-frankie` at `05e97286`, read through `git show` and
`git archive` into a scratch extract. The working tree was not used; three agents are editing it in parallel.

Scope: the items the first review (`REVIEW_20261007_EVENING_SLICES_AND_READINESS.md`) marked UNVERIFIED.
1. `frankie_box_workflow_inspection.py` as committed (the eff34d5 union and the c8c8fb0 merge).
2. `frankie_box_successor_dispatch.py` on the Step 8 branch, including the waiting_school drain branch from 9d4291e.
3. The Step 8 restart pass 5f11188 and the corrections in 9cd1e2a: finish states, day inspection, close_day draining,
   voice reuse, remote admission on both sides, the REBOOK chain, the Jev status collision, lease release ownership,
   retained jobs with expired URLs, save acknowledgment binding, and the day-file witness refusal.
4. The newest commit 05e97286: the day reports' 99-layer join and the native-layer records in boss_session.

Line numbers below are those of `05e97286`.

Independence caveat:
- 9cd1e2a states that it carries "frankie-school-recovery's in-progress edits (Run.school region, successor_dispatch
  waiting_school, reporter FOLLOW/pins)". These were written by an earlier instance of this role.
- For those hunks this is a self-review, not an independent one. They are: the `time.sleep(5)` and its comment in the
  waiting_school branch (`frankie_box_successor_dispatch.py:757-764`), and the school `inspection=` fields in
  `Run.school`.
- A reviewer other than school_recovery should re-read those hunks. Everything else in scope was authored by other
  roles.

Checks run:
- AST parse without project imports passed on all 8 in-scope `.py` files.
- `bash -n` passed on `frankie_box_experiment.sh` and `frankie_box_experiment_day_reports.sh`.
- `git diff --check` is clean on 9cd1e2a, 5f11188, 9d4291e and 05e97286.
- Nothing was executed. Status: SOURCE-BUILT / RUNTIME-UNVERIFIED. A fresh independent review of the fixes is required
  before integration.

## Verdict: BLOCKED

One blocking defect (F1), spanning the queue's new waiting finish and Run.jev. Everything else in scope is approved,
or approved with the required or non-blocking findings listed below.

## Blocking finding

**F1. A day whose finish ends "waiting" can never finish later: on the retry, Jev is refused, even when it is already
done.**
- Where:
  - `frankie_box_frankie_queue.py:1695`: a `waiting` finish now releases the owner binding (5f11188, item 3).
  - `frankie_box_frankie_queue.py:1785`: a waiting finish is retried on the next worker start, on whatever slot is
    free.
  - `frankie_box_frankie_queue.py:1378`: `_finish_steps` calls `run.guarded('jev', e)` unconditionally on every finish.
  - `frankie_box_experiment.py:2805-2819` and `2912-2916`: Run.jev has no early return for a done receipt. It rebuilds
    the request and compares it with the retained `jev-request-<stamp>.json`. That comparison binds `slot_booking` and
    `cpus`. A new booking therefore goes to `jev_rebooked`, which needs `owner.rebooked`. Only `ACTION=resume REBOOK=on`
    records that decision, and the queue's own retry never does, so the result is `record('jev', day, 'refused', ...)`.
- Failure paths:
  1. Jev finishes `done`. `close_day` then returns `waiting` because a successor request is still unacknowledged
     (5f11188's new non-looping close). The finish ends `waiting`, and `_release_owner` drops the binding. On the next
     worker start, `_book_slot` books a new slot with a new booking id. `_finish_steps` reaches Jev again: the request
     differs in `slot_booking`/`cpus`, and there is no REBOOK decision. The done Jev receipt is overwritten with
     `refused` (the earlier `done` survives only in `previous_attempts`). The finish becomes `failed`, and every later
     retry repeats the refusal.
  2. Jev returns `waiting` because its receipt awaits the owner's disposition or lists unresolved calls. This is the
     helper's normal outcome when a comparison is pending, so it is likely on day 1. The finish ends `waiting`. On
     retry, the wait is relabelled as `refused`.
  3. Before 5f11188, path 1 could not happen: close_day looped and held the slot. Path 2 existed only on the `failed`
     route.
- Why it matters:
  - A wait becomes a refusal, and completed evidence is relabelled.
  - The day can never finish: it is held forever by a booking id that no longer exists.
  - This goes against the missing-coverage rule (waits stay waits, and never block the day) and against "unknown
    effects preserved".
- Minimal fix:
  - (a) Run.jev returns the day's existing jev receipt unchanged when `done_status()` holds and that receipt's
    `request` is the retained request path (or its rebook successor). `_finish_steps` can equally skip Jev when
    `run.finished('jev', day)`.
  - (b) A `waiting` finish keeps its owner binding (release it only on `failed`), so the retry gets the retained booking
    and CPUs back, as a saved day does. Alternatively, the queue writes an explicit `rebooked` decision on the new owner
    binding naming the replaced booking/CPUs, so that `jev_rebooked` mints the `.rebookN` successor through the existing
    rule.
  - Without (b), path 2 remains: a pending Jev disposition, retried on a new booking, is still refused.

## Required, non-blocking findings (most severe first)

**F2. The "retained job with expired URLs" correction (9cd1e2a, item 3) does not take effect.**
- Where: `research/kalshi/frankie_boss/pod_root/controller.py:894-900`.
- Defect: on the IfNoneMatch 412 path, `start_day` re-signs `existing['inputs']` and `existing['mailbox']` in memory
  only. But `submit` (line 419) gives the worker only `_job_url`, a presigned GET of the S3 `job.json`, and the worker
  reads the job body from that URL (`pod_agent.py:931`). The worker therefore still receives the stale first-export
  GETs.
- Contrast: `renew()` handles this correctly. It writes the re-signed `saved` back with `put_object` (lines 1023-1029)
  before resubmitting.
- Failure path: a controller restart races an existing `job.json` (the 412 path). The worker's input GETs have
  expired, the job ends `failed_inputs`, and the next attempt re-exports from the box. The failure is visible and the
  day recovers, but the claimed correction is not in effect.
- Fix: after re-signing, `put_object` the updated `existing` to the same key, without IfNoneMatch, as renew does (the
  identity check above already proved it is the same job).

**F3. The inspection is not written when a finish raises.**
- Where: `frankie_box_frankie_queue.py:1190-1210` (`_finish_day`), and `frankie_box_experiment.py:3724` (the
  non-queue start path).
- Defect: `_finish_day` catches only `SystemExit`. A step that raises means no `_inspect` and no inspection receipt.
  Examples: `close_day` raising "successor requires its original held day lane", or `run.teacher` raising.
- In `Run.start`, the inspection is skipped when `self.stopped` (the disk floor) is set, and no receipt says why.
- This goes against 5f11188's "after the day's last step WHATEVER the outcome", on exactly the days an operator most
  needs to see.
- Fix:
  - wrap `_finish_steps` in `try/except Exception`: run `_inspect(run, day, 'failed', log)` and re-raise;
  - in `start`, record an inspection receipt with the stop reason when `self.stopped`.

**F4. The native-layer records (05e97286) have no consumer, and the one-day report does not show them.**
- Where: `frankie_box_boss_session.py:1123-1236`.
- `work/native-layer-records.json` is written, but nothing reads it:
  - `all99_admission` (`frankie_box_experiment.py:687`) still admits the 40 native-carried entries by the group-level
    proxy (first review, N3).
  - No caller invokes `Session.native_layer_records()` for retained ROOTs.
  - `frankie_box_workflow_inspection.artifact_paths` (lines 400-403) does not follow it.
  - It is not among the ROOT brain-stage sources.
- So the per-native-layer status, which the commit says exists "so the ROOT's all-99 admission list names each native
  entry", does not reach the admission list or the root piece's inspection md.
- Fix:
  - `all99_admission` reads the sidecar when it is bound to `derive.json`'s sha256, and falls back to the proxy, naming
    the fallback;
  - add `root / 'work/native-layer-records.json'` to the root artifact list.

**F5. boss_session records a false provenance in the skip reason.**
- Where: `frankie_box_boss_session.py:1052-1056` and `1097-1101`.
- Defect: every bedrock-off derivation now records "explicitly overridden off by the caller" with `override=True`
  hard-coded. But at this commit, `frankie_box_experiment_root.py:62,81,302` and `frankie_box_experiment_root.sh:23` still
  default to bedrock off for a plan without the shared policy. That off is the committed default of the experiment
  caller, not an explicit override.
- The docstring at line 769, "ON for the experiment", is likewise false for legacy plans at this commit. (An uncommitted
  working-tree edit flips that default; it is not reviewed here.)
- Fix: set `override` from whether the caller passed `bedrock=False` explicitly (an argument the caller sets), and say
  "the caller ran with bedrock=False" otherwise. Or land the caller's default change in the same commit.

**F6. In the waiting_school branch, "current" is recorded when no reports exist yet.**
- Where: `frankie_box_successor_dispatch.py:750-753`.
- Defect: `reports_stale(entry)` is False when there is no done reports receipt, or when the exchange is not done. The
  branch then records `reports: {status: 'current', reason: 'the reports already carry this school'}`, which is untrue
  in those cases.
- Fix: distinguish three cases:
  - "no reports rendered yet (the reports stage renders on the current school)";
  - "the exchange is not done";
  - "current".

**F7. The waiting_school branch has no guard against repeated child dispatch when a "complete" recovery does not
complete the chain.**
- Where: `frankie_box_successor_dispatch.py:740-765`, with `Run.recover_school` (`frankie_box_experiment.py:2697-2713`).
- Defect: after `recovered.status == 'complete'`, the loop `continue`s straight into `rebuild_dependents`, with no
  sleep. If that again returns `waiting_school`, `recover_school` runs `school(e)` again. While the chain still requires
  a successor, that dispatches the school child again. This can happen when the school child wrote a receipt but
  `retained_school` still reads `requires_successor`, for example because another correction landed meanwhile.
- The loop is bounded only by the child's behaviour. The fifth pass closed the per-call unbounded model-child dispatch;
  this case is its mirror.
- Fix: allow at most one `complete` recovery per operation per drain call. On a second `waiting_school` in the same
  call, record the state `waiting` with "the school stage ended done but the chain still requires a successor",
  sleep, and break.

**F8. A day-file content failure is relabelled as a wait.**
- Where: `frankie_box_experiment.py:3258-3261` (`shared_teacher_compatible`).
- Defect: `attached_day_file` raises `ValueError` from `check_day_file` or `json.loads` on a malformed day file. That
  is an integrity failure of the file's content, and it is recorded as `waiting: the day file ... could not be read`.
- 9cd1e2a's own rule keeps a MISSING witness waiting (correct) and a DIFFERS witness refused (correct). A malformed file
  belongs with the latter.
- Fix: `OSError` -> waiting; `ValueError` -> refused, with the error named as an integrity failure.
- FYI, a sibling case: with `EXTERNAL_WAIT=off`, a teacher result built when the day file was absent
  (`external_section.status == 'absent'`, bound None) is refused as "differs" once the file appears (line 3269). That
  is late knowledge, not a mismatch. External wait is on by default (`external_ready`), so this is not reachable on the
  default route.

**F9. The 99-layer join can stay stale without anyone noticing.**
- Where: `frankie_box_experiment_day_reports.py:1200-1430` and 1915-1921, with `Run.reports_stale`
  (`frankie_box_experiment.py:1941-1956`).
- The join's sha256 is part of the reports' reuse key. But the reports step reruns only on an exchange, meeting or
  school change. Jev and the cross-day candidates update normally finish after the reports, so their columns stay "not
  reported" forever, and no revision is ever triggered.
- After an exchange is rebuilt by a successor, or on a `reused` exchange receipt (lines 2068-2069, 356-358 of
  successor_dispatch), the step receipt carries no `lessons` list. The join then falls back to the original Frankie
  lessons path (lines 1256-1260), reads that list as `read`, and reports the historical and Jev lists as not reported.
  The stale list is not distinguished from a current one.
- Fix:
  - `reports_stale` also compares the reports receipt's `all99_sha256` with a cheap recompute of the join's input set
    (piece, file, sha256);
  - the exchange records its `lessons` on reuse and on successor rebuilds, or the join reads the lesson inputs pinned in
    the exchange's own receipt.json.
- Inherited from the first review's B4: the adviser's `arrived_at_consumer` overclaims flow through REACH_REFINE into a
  `consumer` final for the brain/knowledge entries in Frankie's 99-layer table. The join shows faithfully what the
  pieces recorded; the fix stays B4's.

**F10. The inspection reporter is started with `preexec_fn` in a threaded process.**
- Where: `frankie_box_experiment.py:1915-1924`.
- Defect: the two main lanes are threads of one process. Python documents `preexec_fn` as unsafe in the presence of
  threads, because the child can deadlock before exec.
- The damage is bounded: the 900 s timeout kills the child and the failure is recorded. But it can cost the day's
  inspection.
- Fix: pin with `taskset -c <cpus>` in the command, or with `frankie_box_cores.py run --inside <booking>`, as the
  stage children do.

**F11. A deferred failed-job release can be abandoned until the controller restarts.**
- Where: `research/kalshi/frankie_boss/pod_root/controller.py:946-950` with 937-940.
- Defect: `LeaseNotEstablished`, raised at the release boundary (correct, 9cd1e2a item 2), is caught by the generic
  `except` as `result='failed'`, and it counts toward the two-try give-up.
- If the lease is re-established in the same process after two deferrals, this controller never releases or cleans the
  failed job. The claim stays held until a new controller process starts.
- Fix: do not count a `LeaseNotEstablished` deferral in `self.tries`, and record it as `deferred`, not `failed`.

## Non-blocking notes (FYI)

- Comment drift:
  - `frankie_box_successor_dispatch.py:760-762` still says "close_day loops on drain until every request is
    acknowledged". Since 5f11188, close_day drains once.
  - `frankie_box_successor_dispatch.py:745` and `frankie_box_experiment.py:2656` say "holds the inbox lock". The drain
    holds `drain.lock`; close_day takes `inbox.lock` afterwards.
  - `frankie_box_experiment.py:2670-2675` names "close_day's loop".
- close_day's `waiting` return covers only the waiting_school break. The drain's own in-request waits still poll inside
  `drain` and hold the finish thread: a failed child awaiting its named retry, a candidate awaiting the scientific-owner
  decision, a save. That is the existing "save/decision waits keep that booking" contract (docstring line 636), named
  in close_day's docstring. It is correct as documented, but it means close_day can still hold a slot indefinitely on a
  human decision.
- An existing 91f3766/05077ed0 contract, carried here: under a checked source correction, a school successor waits for
  a complete corrected meeting (`Run.school`, `needs_meeting`, lines 2583-2589). A non-blocking refused or inputs_only
  meeting is never re-dispatched. So a correction on a day whose meeting is refused (for example, the runtime gate not
  ready) keeps the successor, and therefore close_day, waiting until the owner decides. Under the 2026-10-07
  missing-coverage rule, the owner of `frankie_box_school_knowledge._successor_projection` (Codex) should decide whether
  a non-blocking meeting refusal can enter the successor as a listed thinner discussion, the way the original school
  does. This predates the change under review and is not counted against it.
- `frankie_box_granite_runner.admit` (5f11188) checks run/day, exchange sha256, commit, run id/attempt and the
  predecessor. It does not check `meeting_input_sha256`, which the owner's admission carries. The commit and the
  exchange bytes bind it deterministically, so this is defence in depth only. Consider adding it.
- The remote voice intent binds `source.commit` and the runtime config witness, and is create-only (lines 2323-2331). A
  restart under a new commit, or an edited `GRANITE_MEETING_RUNTIME_V1.json`, refuses the remote meeting for that
  exchange permanently. No owner-decision route is implemented to replace the intent. This affects
  `voice_route=github` only; Greg's 10-07 decision makes local the default.
- `inspect_day` moves the previous inspection directory aside with a timestamp at one-second resolution. Two
  inspections in the same second would collide on the rename; the failure is named on the receipt.
- The first review's B5 (a `not_run` search makes Jev wait permanently, `frankie_box_experiment.py:2750-2753`) is
  still present at 05e97286.

## What was found clean

**1. `frankie_box_workflow_inspection.py` (eff34d5 union, kept by c8c8fb0): no Step 8 behaviour lost.**
- An AST comparison of the 9d4291e Step 8 version against HEAD found:
  - FIELDS: HEAD is a strict superset (+86 names, none dropped);
  - FOLLOW: identical (meeting, school, corrections), as is FOLLOW_DEPTH;
  - `artifact_paths`: a strict superset (adds the school index and reports receipt, phase-progress, teacher-knowledge
    and the external-section receipt, the search findings and discovery index, the brain MANIFESTs, and Jev's
    receipt/owner/client receipt; keeps Jev's `request` and `status_file`);
  - `lane_records`, `pins`, the bounded successor-chain walk, the foreign-owner rule and the plan-identity rule are
    unchanged, apart from print -> emit.
- `--write` is kept: one file per piece plus `index.md`, written atomically through a `.pending` rename.
- Changes in shape:
  - the plan pin and the excluded-records block now head every piece file instead of `index.md`;
  - the final stdout line changed text. Run.inspect_day does not parse it: it checks the exit code and `index.md`.
- Nothing is silently dropped:
  - unprojected receipt fields are named under `other_fields_retained_at_source`;
  - unreadable or excluded records are listed;
  - the only in-scope receipt no piece selects is the reporter's own `inspection` stage receipt.
- New receipt fields that reach the md:
  - `inspection` (in FIELDS) on root, teacher, school, reports and jev;
  - the remote voice `intent`/`admission`/`returned` (through FOLLOW['meeting']);
  - the finish facts (`rows_missing`, `rows_refused`, `rows_waiting`, `not_queued`, `finish`), including on the queue
    entry projected by `lane_records`;
  - the day reports' `workflow_report.use.all99`, as a summary through the reports receipt.
- Fields named but not projected by value (listed at source, not dropped):
  - the ROOT's per-entry `all99` (its counts reach the md through `inspection.outputs.all99`);
  - Jev's waiting `shared_runtime`/`superseded_jev_runtime`;
  - `frames_spool` on a `not_run` search.
  - Projecting `all99` whole on the root piece would put the per-entry list in front of Greg's day-1 read. This is
    optional; the reports' 99-layer table carries it.

**2. `frankie_box_successor_dispatch.py`: the Step 8 non-reentrance holds.**
- Every path from `recover_school`, and from the waiting_school reports call, back to `drain` goes through
  `Run.successors()` (directly, through `Run.child()`, or through `guarded()`). That function returns `[]` for a day in
  `_school_recovery`, and the set is held across both calls (try/finally).
- A second Run instance on the same day blocks on `drain.lock`. That is serialization, not deadlock: the holder waits
  on nothing the second one holds.
- Inside the branch, a save (`SystemExit(75)` from `check_save`) reaches drain's existing `saved` handling.
- close_day:
  - computes `pending` from `ack.json` under `inbox.lock`;
  - returns a named `waiting` dict instead of spinning;
  - writes `closed.json` only when every request is acknowledged;
  - `_close` maps the result to the finish state.

**3. 5f11188 and 9cd1e2a, item by item.**
- Finish states:
  - a policy refusal stays `failed`;
  - missing teacher rows continue under the missing-coverage rule, with `rows_missing` named;
  - the class door's `waiting` and `refused` are kept distinct;
  - the entry records `finished`/`waiting`/`failed`;
  - the defect is F1, in the interaction of a waiting finish with Jev, not in the state mapping.
- Day inspection: bounded at 900 s, never a gate, the previous output moved aside, its own receipt. Gaps: F3 and F10.
- Voice reuse: one meeting child per decision. A receipt the drain wrote during the call is returned, never
  re-dispatched. A standing non-blocking refusal is reused only while the refusing decision stands: the config gate
  for `refused`, the shared runtime for `inputs_only`.
- Remote admission, both sides:
  - the owner side is create-only: intent before any dispatch, then per-attempt dispatched/admission/returned;
  - an admitted attempt without a return blocks a new attempt;
  - a continuation binds the predecessor archive;
  - the runner's `admit` verifies before setup;
  - the workflow fetches the admission only over HTTPS, and sets up only on admission success;
  - the meeting runs the model only with the admission copy plus both runtime variables, otherwise replay;
  - a restored predecessor `admission.json` cannot trigger model work without a fresh admission, because setup is
    skipped.
- REBOOK chain:
  - the original request is never changed;
  - successors `.rebookN` are create-only, and only with the owner decision naming the newest booking;
  - retained progress is refused by name.
  - Correct as specified. F1 is that the queue's own retry never supplies the decision.
- Jev status collision: `status_file` replaces the duplicate keyword at both sites, and `request_pins` is recorded.
- Lease release ownership: the release, clean and delete are made only after `lease_established('release')`. F11 is
  the accounting around the deferral.
- Save acknowledgment binding: the ack carries `cpus` and `source_owner`; the verdict requires marker, attempt,
  booking, CPUs, source and the standing save generation; a saved entry without an ack is `unknown`, not acknowledged.
- Day-file witness: a missing witness waits; DIFFERS or a real sha mismatch is refused. The read is cached once per
  Run, and Runs are per queue job. Gap: F8.

**4. 05e97286.**
- The 99-layer join:
  - reads each piece's list once;
  - checks a pinned list against its pin;
  - keeps an absent file (`not_reported`, a thinner picture) separate from a pin mismatch or unreadable JSON
    (integrity);
  - takes classes from the one shared registry module, never a copy;
  - names unregistered and duplicate ids as integrity, never drops them;
  - lets neither Jev nor the ROOT decide a final;
  - reads a piece without a list as unknown, never zero;
  - prints the integrity section separately ("not a missing-data disposition");
  - is day-count agnostic.
- The `.sh` path guards are exact-prefix and refuse `..`.
- The native-layer records:
  - are additive: written after `derive.json`, never read by the derivation, moved aside with it;
  - copy statuses from derive.json;
  - list `absent` with a reason, never fabricate;
  - state the limits of the two native-only clocks instead of filling them in;
  - activate no disabled producer.
  - All 18 NATIVE_ONLY_ENTRIES are members of the 44 native registry layers (checked against
    `REGISTRY_CALCULATION_SET`). The gap is F4 (no consumer).

## UNVERIFIED

- Runtime behaviour of everything above: nothing was run.
- Whether `frankie_box_school_knowledge` (Codex) can ever return `done` from the school child while `retained_school`
  still reads `requires_successor` (F7's trigger). This was not read in depth.
- Whether any resume or reuse check compares a retained `derive.json`'s `not_derived` reason text with a fresh one.
  F5's text change would make such a comparison differ. A grep found no consumer of the old text except one classroom
  note.
- The Linux lane (`pod_root` worker) finish path: whether it runs `_finish_day` and therefore the inspection. Not
  traced.
- The worker-side `work` action beyond `pod_agent.py:931`, for F2: whether any later step re-reads inputs from the
  submitted body. None was found.
- The uncommitted working-tree edits, including `frankie_box_experiment_root.py`'s bedrock default: excluded by
  instruction.

## Per-file verdicts

| File (commits) | Verdict | Findings |
|---|---|---|
| deploy/aws/box/frankie_box_workflow_inspection.py (eff34d5, c8c8fb0, 9cd1e2a, 5f11188) | APPROVED | no Step 8 loss; F4 (native records not followed) |
| deploy/aws/box/frankie_box_successor_dispatch.py (9d4291e, 5f11188, 9cd1e2a) | APPROVED with required F6, F7 | comment drift; 9cd1e2a hunk is a self-review (caveat above) |
| deploy/aws/box/frankie_box_frankie_queue.py (5f11188, 9cd1e2a) | BLOCKED | F1 (lines 1378, 1695, 1785); F3 |
| deploy/aws/box/frankie_box_experiment.py (5f11188, 9cd1e2a, 9d4291e) | BLOCKED | F1 (lines 2805-2819, 2912-2916); F3, F8, F10; first review's B1, B3a and B5 still stand |
| deploy/aws/box/frankie_box_granite_runner.py, .github/workflows/frankie_granite_meeting.yml (5f11188) | APPROVED | admit could also check meeting_input_sha256 |
| research/kalshi/frankie_boss/pod_root/controller.py (9cd1e2a corrections) | APPROVED with required F2, F11 | first review's B3c still blocks the file as a whole |
| deploy/aws/box/frankie_box_experiment_day_reports.py/.sh (05e97286) | APPROVED with required F9 | B4 overclaims propagate into the table |
| deploy/aws/box/frankie_box_boss_session.py (05e97286) | APPROVED with required F4, F5 | derive.json, layers and spools untouched |

## Skills and account calls

- Skills (Skill tool): `api-and-interface-design`, then `code-review-and-quality`.
- Account calls: none.
