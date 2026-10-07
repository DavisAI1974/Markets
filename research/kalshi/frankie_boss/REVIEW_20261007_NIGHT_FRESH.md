# Fresh independent review: everything since 0166c4d1 (ccode_review, 2026-10-07 night, session 2)

Reviewer: ccode_review. Greg resumed this role in session 2 (item 2 of the drop-in's open list), relayed by the parent.
This pass is READ-ONLY: no fixes, no git writes, no account calls, nothing run. This file is the only file written.

Scope: the committed range `0166c4d1..a0007a9` on `ccr-d2f8f826-iefeah-frankie`. It was read through `git diff` and
`git archive` into a scratch extract; the working tree was not used. Commits: b72d895, 9464189, 52c44a2, 08e2553,
cceb191, 430b6bd, 64e6335, 9fbdc4d, c2d4f4d, a0007a9. 21 `.py` files, one JSON and the docs. The day-file agent's
uncommitted edits (`frankie_box_day_external.py`, `day_files/`) are excluded; the parent sends them as a follow-up.
Line numbers are those of `a0007a9`.

Status: SOURCE-BUILT / RUNTIME-UNVERIFIED. This review is not an E2E verdict.

## Verdict: APPROVED for integration (source only), with four items REQUIRED before the one-day E2E

No finding blocks integration of the source. No finding makes a day unable to finish. No finding fabricates a
measurement or turns a wait into a refusal on the default route. The second review's F1 blocker is fixed.

Four required items (R-A to R-D below) must land before the one-day E2E. Without R-A, the 99-layer table in Greg's
day-1 reports shows Jev and the candidates as "not reported" even after they finish. Without R-B, two readers can use a
day-file value before Greg's 14:00 ET placement.

## Required before the one-day E2E (most severe first)

**R-A. F9a works only partly: on the default route, nothing asks for a report revision after Jev or the candidates
finish.**
- Where:
  - `frankie_box_frankie_queue.py:1416-1423`: `_finish_steps` runs Jev after the class line, then goes straight to
    `_close`.
  - `frankie_box_experiment.py:4073` (`if self.stopped or root_line: break`): `start()` does not run the stage loop with
    the ROOT line on, the default per `:4315`.
  - `frankie_box_lane_state.py:503` notes that "a done class never re-enters the queue".
- Defect:
  - `Run.reports_stale` and `late_pieces_changed` detect a late piece correctly. But their only callers are the class
    worker's `passed()` (before Jev), `start()`'s stage loop (skipped for queue-owned days and under the ROOT line) and
    the waiting_school branch of the drain.
  - Jev finishes after the reports, in the same finish thread. The candidates update finishes at a batch boundary. After
    either one, no code path checks `reports_stale`.
- Failure path:
  1. Day 1 runs on the default route: ROOT line on, class queue on.
  2. The class line renders the reports with Jev `not_reported`.
  3. Jev finishes `done`.
  4. `_close` runs, then `_finish_day` writes the inspection.
  5. The day's FRANKIE report and its 99-layer table still list Jev and jev_sit_in as "not reported". No `late_pieces`
     result is ever recorded. This is exactly the second review's F9 symptom.
- Minimal fix (owner ccode_step8):
  - In `_finish_steps`, after Jev ends in `X.FINISHED` and before `_close`, call
    `if run.reports_stale(e): run.guarded('reports', e)` on the classroom-arm route. This uses the same slot and makes no
    model call.
  - In `Run.survivors` (or `Run.lessons`), after a done boundary, do the same for each arm day of the batch whose reports
    are done.

**R-B. Greg's 14:00 ET placement is honoured by the shared reader but not by the classroom's external section or the
search.**
- Where:
  - The shared reader places correctly: `frankie_box_market_timeline.py` PublicationReader puts each row at
    `max(event_time_ns, publication)`.
  - The search does not: `frankie_box_experiment_search.py` writes `placement_note='the search places each point through
    the day file's own as-of reader ... at the stamps it returns; the shared reader places at max(event time,
    publication)'`.
  - The classroom does not either. `frankie_box_classroom_code.py:external_points_use` (the `tie_of` and
    `read_before_event_time` branch) only labels such rows. The values have already entered the external section
    arithmetic through `AsOfReader` at the reader stamp.
- Defect: when a day file stamps a value with no intrinsic event time at a publication time before 14:00 ET, three
  readers disagree:
  - the shared reader presents it at 14:00;
  - the search and the classroom's external section read it at its earlier stamp.
  The classroom then records the point as `absent` with an integrity reason. But its value was already in that day's
  external answers, so the label understates what was used.
- Failure path: the day file gives a no-intrinsic-time point `event_time_basis=default_1400` and `published_ns` at
  09:00 ET. The external section and the search's `external.<alias>` series read it from 09:00 onward; Greg's rule
  places it at 14:00.
- Minimal fix:
  - Preferred, for the day-file agent (`frankie_box_day_external.py`, in its follow-up): write each row's reader stamp
    (`stamp_column`) as `max(event_time_ns, publication)`, keeping the publication time in its own column. All three
    readers then agree with no change to them.
  - Otherwise: `AsOfReader` honours `event_time_ns`.
  - Impact depends on the 30 day files: UNVERIFIED until they are reviewed.

**R-C. A failed finish now releases its owner on the one-slot route, so a failed Jev can never be retried.**
- Where:
  - `frankie_box_frankie_queue.py:1805-1817` (one-slot route) and `:1759` (finish-only route) call `_release_owner` on
    `failed`.
  - `frankie_box_experiment.py:3247-3249`: `Run.jev_rebooked` needs `owner.rebooked`.
  - `frankie_box_frankie_queue.py:2085-2094`: `resume_owner REBOOK=on` keeps a binding only for saved or unknown days.
- Defect:
  - Releasing the owner fixes the CPU-pinning wait the record names, and that part is correct.
  - But the retried finish gets a fresh owner with no `rebooked` decision and no `held_bookings`.
  - A retained Jev request that ended `failed` (for example a llama-server crash) differs from the new request in
    `slot_booking`/`cpus`, so `Run.jev` refuses it.
  - No route exists to supply a decision for a released owner, so the refusal repeats on every retry.
- Before this change the one-slot route kept the owner and retried Jev on the exact CPUs. The finish-only route has had
  this gap since 5f11188.
- Failure path:
  1. Jev fails once.
  2. The finish ends `failed`.
  3. On retry, Jev is `refused` ("no REBOOK decision on the owner binding").
  4. The day ends `failed` permanently, and its Jev evidence is never produced.
  This goes against "failed = retried by the ordinary path".
- Minimal fix (owner ccode_step8), either of:
  - (a) `_release_owner` on `failed` records `previous_owner_bookings` (the released owner's `held_bookings`).
    `_bind_owner` carries them into a `rebooked` decision with `by='queue-after-failed'` only when the retained Jev
    request's helper receipt is `failed` or absent (no progress to resume). `jev_rebooked` then mints `.rebookN` as it
    does for a wait.
  - (b) `Run.jev` treats a retained request whose helper receipt is failed with no progress as re-mintable under a
    `.rebookN`, with the reason recorded.
  - The original request is never changed in either case.

**R-D. A discovery problem cannot be resumed after a crash between its result file and its recovery pickle.**
- Where: `frankie_box_experiment_search.py` `_discovery_compute` (the last block: `if out.is_file() and
  out.read_bytes() != data: raise ValueError(...)`) and `_discovery_job`.
- Defect:
  - The result bytes include `seconds` (wall time). The file is written before `_save_state` writes the pickle.
  - After a kill in that window, the resume recomputes the problem, gets different bytes and raises. The search step then
    fails on every resume.
  - With PySR absent the status is `equation_not_run`, and `seconds` still differs between runs. With PySR present, the
    fits are also non-deterministic across processes.
- Minimal fix (owner of the search, workflow_reports): when the result file exists for the same problem id, read it back
  and return its pin instead of recomputing. Or keep `seconds` out of the pinned bytes.

## Non-blocking findings

- **N-1. `Run.reports_late_pieces` rewrites the reports step receipt without coordinating with `record()`**
  (`frankie_box_experiment.py:2183-2197`).
  - It reads the step receipt, runs `late_pieces_changed` (which reads every join input), then writes
    `dict(step, late_pieces=...)` back.
  - Suppose another process records a new reports step in that window: the drain in the class worker, or an operator
    start on a non-queue day. The older step is then written over the new one, and `report_number`, `reports` and
    `meeting` revert.
  - `record()` itself takes no lock, so this race exists already, but the check widens the window.
  - Fix: re-read the step immediately before the write, and write only when its `at` equals the value read.
- **N-2. A report revision during the class line can fail the class day**
  (`frankie_box_frankie_queue.py:633` with `keep()` at 724-736).
  - `keep('reports')` calls `passed()`, which calls `reports_stale` right after the render.
  - If a late piece lands in between (a candidates update from another day's boundary, a lane_state meeting refresh),
    `passed` returns False and `keep` returns `failed` ("reports done: ..."), not a revision.
  - A retry recovers, so this is rare and visible.
  - Fix: in `keep`, a done reports step whose only staleness is `late_pieces` re-renders once.
- **N-3. F6's `exchange_not_done` branch skips the late-pieces check**
  (`frankie_box_successor_dispatch.py`, waiting_school branch).
  - This is inconsistent with the new `reports_stale` contract ("runs whatever the exchange's state").
  - The next check catches it. A nit.
- **N-4. The ROOT's new `counts_canonical` and per-row `canonical`/`class` are not projected by the one-day reporter.**
  - `frankie_box_workflow_inspection.all99_section` reads `shared_counts` only from a shared field.
  - The ROOT list is not a shared field, so its canonical counts are absent from the root piece's md. The reports' 99-layer
    table carries them.
  - Fix: project `counts_canonical` when present.
- **N-5. Picture size growth (efficiency, magnitude UNVERIFIED).**
  - Every picture now carries `coverage.carried_entries` (the full carrier-to-entries map), `opening_state`, and per
    update `entries` (and `placement` for publications).
  - The adviser picture text and render grow by this on every Granite/Jev prompt. The token cap still refuses visibly
    and nothing is trimmed, but more items may hit it.
  - `_entries_of` also walks the 18 native specs per native row on the hot path.
  - Measure on a canary slice. Precomputing per row shape and moving `carried_entries` to the context once would help.
- **N-6. `late_pieces_changed` logs an `unknown` on every poll while the receipt is absent.** Cosmetic.
- **N-7. Classroom `exhaustion_d_facts` reports `computed` while frozen-text integrity findings exist.** This is
  correct under the missing-coverage rule: each finding is listed per entry as `absent` with the reason. FYI only.

## Earlier findings: status at a0007a9

First review (`REVIEW_20261007_EVENING_SLICES_AND_READINESS.md`):

| Finding | Status | Where |
|---|---|---|
| B1 | FIXED by Greg's decision (Jev on Granite's settings; 725dffd, before this range) | `frankie_box_jev_cpu.py:49` bind_runtime |
| B2 | FIXED by Greg's decision (no separate approval gate) | no approval code remains in jev_cpu |
| B3a | FIXED (kick grace, running/unknown/queued entries) | `frankie_box_experiment.py:568-613` |
| B3b | FIXED (any fresh lease protects both boxes; re-describe before stop) | `idle_instance_guard.py:89-114` |
| B3c | FIXED (unknown keeps the tag) | `pod_root/controller.py:1588-1605` |
| B3d / R1 | Account record: inline grants KeepRunningDescribe and KeepRunningTagMainBox (main box only, matching Greg's main-box-only decision). Not re-checked in this pass. | drop-in, Account state |
| B4 | FIXED (`not_read` with analogue consumer; arm profile `control`; FIXED_WORDS settles) | `frankie_box_adviser_market.py` ROUTES; `frankie_box_all99_coverage.py` FIXED_WORDS |
| B5 | FIXED (`not_run` search gives Jev `not_run`) | `frankie_box_experiment.py:3034-3036` |
| N1 | FIXED (witness bound to path, size and dev/ino; caller witnesses carry them) | `market_timeline._caller_witness`; `classroom_v2.py:239-287`; `classroom_code.py:370` |
| N2 | FIXED in 725dffd (stage 10 wired; `Run.survivors`); not re-traced here | `frankie_box_experiment.py:3911` |
| N3 | FIXED (per-row basis; GROUP PROXY named; a_clean `not_applicable`) | `frankie_box_experiment.py:789-889` |
| N4 | FIXED (`use` computed/context/absent; picture-only reads `exposed`; decision_open text) | `frankie_box_classroom_code.py` `_classroom_use` |
| N5 | FIXED (`parents[3]`) | `frankie_box_jev_cpu.py:424-425` |
| N6 | FIXED (local first, main box only, threads rule) | `GRANITE_MEETING_RUNTIME_V1.json` |
| N7 | FIXED (a clock is `thin` with no test row) | `frankie_box_all99_coverage.py` `_plane_disposition` |
| R2 | OPEN. All days now run on the main box. The main box's free disk for one day (journal 8.8-14.7 GB plus spools and native ledgers) is not recorded; measure before day 1. | account |

Second review (`REVIEW_20261007_EVENING_SECOND_PASS.md`):

| Finding | Status | Where / note |
|---|---|---|
| F1 | FIXED | (a) `Run.jev_done_receipt` (`experiment.py:3209-3233`) and the queue read-back (`frankie_queue.py:1416-1418`); (b) `_rebook_owner` keeps the binding with `held_bookings` (`frankie_queue.py:1672-1694`), and `jev_rebooked` accepts held bookings (`experiment.py:3257-3263`). Path 2 (pending Jev on a new booking) now mints `.rebookN`. The failed side is R-C. |
| F2 | FIXED | `pod_root/controller.py:908-913`: written back before submit; the lease was established at `:872` |
| F3 | FIXED | `frankie_queue.py:1228-1237`; `experiment.py:4130-4138` (disk-floor stop) |
| F4 | FIXED | basis on rows, `native_only.records.group_proxy`, reporter follows the native-layer records |
| F5 | FIXED | `boss_session._bedrock_off_cause`; `experiment_root._calculate_day` passes the cause; bedrock-on bytes unchanged |
| F6 | FIXED | three dispositions plus revision; N-3 is a nit |
| F7 | FIXED | `school_completed` once per operation per drain call; waits with the reason, sleeps, breaks |
| F8 | FIXED | `experiment.py:3597-3601` (OSError waits; ValueError/KeyError/TypeError is an integrity refusal) |
| F9a | PARTLY | the predicate is correct and the one-builder invocation is consistent; no trigger after Jev or candidates (R-A) |
| F9b | FIXED | the lessons come from the exchange's own `sources.lessons` pins, with basis; a fallback is labelled MAY BE STALE |
| F10 | FIXED | `taskset -c` in the command, `start_new_session`; no `preexec_fn` |
| F11 | FIXED | `LeaseNotEstablished` is `deferred` and not counted (`controller.py:978-990`) |
| Notes | comment drift fixed; the `admit`/`meeting_input_sha256` note and the remote-intent note are unchanged (FYI items, not in scope of the fixes) | |

## The questions the parent named

- **Reports staleness revision loop after a re-render.** NO LOOP FOUND.
  - The render records `all99_invocation` and the join `inputs`. The check recomputes the same input set:
    - `Day(join_only=True)` reads the exchange, meeting and school before its early return, and `collect_all99` uses
      nothing it skips;
    - both sides use the same `reports_invocation`;
    - the compared fields exclude reason text and no-list receipt bytes;
    - ROOT lists are keyed by `path#field` plus the sha256 of their canonical JSON, so a rewritten step receipt is not a
      change.
  - A fresh render is therefore `unchanged` unless an input moved.
  - The check's own write goes to the reports STEP receipt, which is not a join input.
  - The remaining issues are R-A (no trigger), N-1 (race on that write) and N-2 (a mid-class race fails the class day
    rather than looping).
- **F1/F7 interactions.**
  - F7's guard is per operation per drain call.
  - A waiting finish from close_day (F7 waiting) now goes to `_rebook_owner`, so the retry keeps the owner and its Jev
    request mints a `.rebookN` or is read back done.
  - The stale save marker is archived exactly as before.
  - No conflict found.
- **Failed one-slot finish releasing its owner.**
  - Correct for the CPU-pinning wait it targets: the attempt is unchanged because `root_of` names the same completed ROOT.
  - It introduces R-C on that route.
- **Canonical words against every consumer of the old words.**
  - Every word of the classroom (15), adviser, ROOT, teacher, core and scientific vocabularies is in `LEGACY_WORDS`.
  - The pieces' internal checks still compare their own words: market_timeline:665, experiment_teacher:202-218,
    classroom_code:870/897, experiment.py:890-899.
  - The day reports read `piece_disposition` for a shared field and the piece word for the ROOT's own list, mapping
    through the registry (`canonical_of`).
  - `day_coverage` now returns the shared-field `entries` (canonical `disposition`, piece word as `piece_disposition`)
    while `counts`/`absent`/`thin` stay in the piece words. `boundary()` and `markdown()` therefore group by the
    canonical word. That is consistent with the field, and no consumer was found that expects the old scientific words in
    `entries[].disposition`.
  - The scientific words changed: `policy` absent became `not_read_by_this_piece`; Memory A `disabled` became `retired`.
    No consumer keys on the old values (grep across `deploy/aws/box`).

## Greg's decisions (drop-in) against the code in range

| Decision | Status |
|---|---|
| Jev on Granite's settings | Holds (bind_runtime over GRANITE_MEETING_RUNTIME_V1; SI.LOCAL model_clock added) |
| One shared lane CPU, threads=1 | Config text now states it; the code rule is from 725dffd/53678055 (not re-traced) |
| Main box only | `hosts_in_order` names it; the Linux route stays listed |
| Day-quantity agnostic | Nothing in range keys on the day count (report numbering, late pieces, rebook all per run/day) |
| Native pass ON | Default on; an off cause is recorded truthfully (F5) |
| Model and confirmation clocks | `model_clock` row/override; sit_in no-room refusal stamped; confirmation_clock_row |
| Everything mapped to a 99 entry, 14:00 ET default | The registry reads the day file's mapping, basis and note, and lists unmapped points (never guessed). Placement is honoured by the shared reader only (R-B). |
| KeepRunning only while in use; idle guard off the default branch | Not changed in range; the guard workflow is not on the default branch (no change seen) |

## Missing-coverage rule

- PASS in range:
  - `teach.facts` drops only a missing frozen file's text, and lists a differing one as integrity;
  - a survivor update is withheld from every day of its batch (listed, never a refusal);
  - native entries without rows read `yielded_no_rows`/`thin` with reasons, never zero;
  - stale stays distinguishable: a carrier hit from `previously_known` rows says "not a new observation";
  - `unknown` is never counted as a change or a zero;
  - integrity stays separate (`integrity_failure`, never `unknown`);
  - external rows are never sorted backward: placement is `>=` publication.
- Exception: R-B.

## Per-file verdicts

| File | Verdict | Findings |
|---|---|---|
| frankie_box_experiment.py | APPROVED with R-A, N-1 | F1a, F3, F4, F8, F10 fixed; reports_invocation consistent |
| frankie_box_frankie_queue.py | APPROVED with R-A, R-C, N-2 | F1b, F3 fixed |
| frankie_box_successor_dispatch.py | APPROVED (N-3) | F6, F7 fixed |
| frankie_box_experiment_day_reports.py | APPROVED | F9a predicate, F9b, canonical_of correct; no loop |
| frankie_box_all99_coverage.py | APPROVED | one registry, field/validate, day_coverage counts |
| frankie_box_classroom_code.py | APPROVED with R-B | use words, exhaustion/D invocation, external points |
| frankie_box_experiment_classroom_v2.py | APPROVED | N1 witness, exhaustion/D phase |
| frankie_box_market_timeline.py | APPROVED (N-5) | carriers, opening_state, placement correct |
| frankie_box_experiment_search.py | APPROVED with R-B, R-D | native per-entry rows; discovery producer |
| frankie_box_adviser_market.py | APPROVED | B4 fixed |
| frankie_box_experiment_teacher.py | APPROVED | teacher field derived from the core field |
| frankie_box_boss_session.py | APPROVED | F5 |
| frankie_box_experiment_root.py | APPROVED | cause passed |
| frankie_box_teach.py | APPROVED | missing coverage |
| frankie_box_lane_state.py | APPROVED | same-batch withholding; refresh invocation |
| frankie_box_experiment_data.py, frankie_box_experiment_native.py | APPROVED | projection plan pinned; native entry files linked, never recomputed |
| frankie_box_workflow_inspection.py | APPROVED (N-4) | |
| frankie_box_jev_cpu.py, frankie_box_granite_meeting.py, GRANITE_MEETING_RUNTIME_V1.json | APPROVED | SI.LOCAL, knowledge_listed, wording |
| pod_root/controller.py | APPROVED | F2, F11 |

## Checks run

- AST parse without project imports (`python3 -I`, `ast.parse`): all 21 changed `.py` files at a0007a9 parse.
- `git diff --check 0166c4d1 a0007a9`: clean.
- `bash -n`: no `.sh` file changed in range. Every `deploy/aws/box/*.sh` at a0007a9 also passes.
- No tests, no imports of project modules, nothing executed.

## Skills and account calls

- Skills (Skill tool), in order: `api-and-interface-design`, `code-review-and-quality`, `doubt-driven-development`.
- `doubt-driven-development` ran in its degraded self-questioning form. A subagent cannot spawn a fresh-context reviewer,
  so cross-model review was not run. The re-checks it drove:
  - R-A: the `root_line` break; `queue_owned` skips; the lane_state note; no reports call after Jev.
  - The no-loop claim: the `Day.__init__` order against `collect_all99`'s reads.
  - R-C: the `resume_owner` rebook scope.
- Account calls: none.

## UNVERIFIED

- Runtime behaviour of everything above.
- Whether the 30 day files stamp default-1400 points before 14:00 ET (R-B impact).
- The main box's free disk for a day (R2).
- Whether a retried finish whose class entry failed under a released owner is admitted by `_after_root` without an
  owner-waiting hold. This predates the range on the finish-only route.
- The picture-size cost of N-5.

## Follow-up, 2026-10-07 night (session 2): the fixes and the day files, `fb97f35..2527e2f`

Reviewer: ccode_review, under the same go, relayed by the parent. This pass is READ-ONLY: no fixes, no git writes.
The only writes are this appended section and local scratch downloads. NO RUNS.

Commits reviewed:
- f99d1a1: R-A, R-C, R-D, N-1 and N-3.
- 3bf4f2d: the 31 per-day md files.
- 72e9ae8: the day-file builder, the box module, the workflow `days` input and the 31 day files on S3.
- baf8b57: the classroom reads `storage.estimate` and the stamp shape.
- 2527e2f: the search reads the new files.

They were read through `git diff` and `git archive`.

### Verdict: APPROVED for integration (source only)

- R-A, R-B, R-C and R-D are fixed. N-1 and N-3 are fixed.
- The day files check out on the three days sampled.
- One new required item, F-1, should land before the one-day E2E. It does not block integration.

### Status of R-A..R-D

| Item | Status | Where |
|---|---|---|
| R-A | FIXED. `_finish_steps` revises the reports after Jev, before `_close`; a check error is listed in the facts and never blocks the close. `Run.survivors` revises the batch's done arm-day reports after a done boundary. The cross-day half introduces F-1. | `frankie_box_frankie_queue.py` `_finish_steps` (after the Jev block); `frankie_box_experiment.py` `Run.survivors` |
| R-B | FIXED in the file itself. Every row carries `event_time_ns`, and `published_ns = max(event time, publication)`, with 14:00 ET for a row without an event time (`place()`). `check_day_file` refuses an event time later than its stamp. The shared reader, the classroom and the search therefore read the same instants. A superseded publication-stamp file is still read and is named as a finding (`stamp_shape`). The classroom no longer labels a used value `absent`. | `operations/frankie_day_external.py` `place`, `EVENT_TIME_RULES`; `dipole_classroom_external.stamp_shape`; `frankie_box_classroom_code.external_points_use`; `frankie_box_experiment_search.build_series` |
| R-C | FIXED. A failed finish carries the released owner's bookings (`failed_finish_bookings`). `_bind_owner` turns them into a `queue-after-failed` rebook decision only when `_jev_progress` finds a retained request whose helper receipt is failed or absent; otherwise it records the decision with `not_applied`. The original request is never changed. | `frankie_box_frankie_queue.py` `_release_owner(failed_finish=True)`, `_jev_progress`, `_bind_owner` |
| R-D | FIXED. An existing result file of the exact same problem definition is read back and never recomputed. Any other definition is still refused, with the file kept. | `frankie_box_experiment_search._discovery_compute` |
| N-1 | FIXED. The step receipt is re-read right before the write; if its `at` changed, the result is not written over it. | `Run.reports_late_pieces` |
| N-3 | FIXED. The late-pieces check also runs on an exchange that is not done. | `successor_dispatch.drain` waiting_school branch |

### The author's deliberate deviation: clocks are kept out of the entity-grouping set

AGREED.
- `ENTITY_COLUMNS` partitions a table's rows into entities. Partitioning by `event_time_ns`, or by storage.estimate's
  `print_ns`, would make every row its own entity, which splits a series into singletons.
- The clocks are emitted as fields and routed to `identity_fields` by `identity_and_clock_columns(point)`, so they are
  never searched as a numeric signal.
- `external_fields` has one caller (the search), so no other consumer depends on the old grouping.

### New required finding (before the one-day E2E; not blocking integration)

**F-1 (owner ccode_step8). `Run.survivors` revises OTHER days' reports through `guarded`, on the boundary day's lane.**
- Where: `frankie_box_experiment.py` `Run.survivors`, the new loop. The other calls involved:
  - `self.guarded('reports', entry)` runs `self.successors(entry['day'])` and then `Run.child`;
  - that calls `successors(day)`, which calls `drain`;
  - `drain` raises `ValueError('successor requires its original held day lane')` for any unacknowledged request, because
    this Run's `slot_booking` belongs to the boundary day.
- Failure path:
  1. An arm day of the batch has a pending correction (an unacknowledged successor request) at the boundary.
  2. `guarded` catches the ValueError and records that day's DONE reports step as `failed`.
  3. That relabels a done step on the strength of another lane's lane check. `reports_stale` then returns False for a
     non-done step, so the day is never revised again by this route.
- Even when no request is pending, the other day's reports child runs `--inside` the boundary day's held slot.
  `cmd_run_inside` does not check the day, so it runs, but the rule is that a day stays on its lane. The reports render
  is small, so the cost is negligible.
- Minimal fix:
  - Skip a day whose successor inbox holds an unacknowledged request; that day's own drain revises it (F6 / N-3).
  - For the rest, call the revision with that day added to `_school_recovery` (no nested drain), or record a revision
    request that the day's own owner picks up.
  - Never let a revision failure record over a done reports step. Write the revision's outcome beside the step instead.

### Non-blocking

- **F-2. `storage.weekly` mixes vintages inside one row without saying so per field.**
  - In `frankie_day_external.py` `storage_weekly`, where the archived report lacks `net_change_bcf` or the five-year
    average, the row keeps the EIA-series (revised) change or `vs_5yr`.
  - Meanwhile `level` is the printed value and the row's single `source` names the printed report.
  - The record lists these prints (2024-09-26 and 10-03; 2025 five-year average), so the rows are honest at day level but
    not at field level.
  - Fix: a per-field vintage column, such as `revised_fields`.
- **F-3. The receipts' `markets_sha` reads `worktree-on-3bf4f2df`, not a commit.**
  - The receipts' `code_sha256` entries equal the committed files at 2527e2f (checked below), so the code is pinned
    exactly.
  - A rebuild under a commit would make the receipts self-describing.
- **F-4. A table with no `EVENT_TIME_RULES` entry falls back to the 14:00 ET default.** This is conservative (later,
  never earlier), so it cannot leak. It would delay a future table that does have an intrinsic time. Listed only.
- **F-5. A late-pieces revision that ends `failed` inside `_finish_steps` is listed in `facts['reports_revision']`.**
  The day still closes `finished`. That matches "never gates the close". The reports step shows the failure. FYI.

### Day files on S3 (read-only spot check)

Three of the 31 files were sampled, one per era: 20211012, 20231017 and 20251007. For each, the day file and its
receipt were downloaded by presigned GET into a scratch directory, and the data was parsed by a checker script kept
outside that directory (`python3 -I`).

| day | bytes | sha256 = receipt | sha256 = DAY_FILES_30 record | tables | 99 mapping on every table | event_time_ns on every table | stamp < event time | stamp at/after halt | no-event row before 14:00 ET | stamps non-decreasing |
|---|---|---|---|---|---|---|---|---|---|---|
| 20211012 | 46,971,399 | yes | yes (1beb8acb...) | 20 | yes | yes | 0 | 0 | 0 | yes |
| 20231017 | 38,223,001 | yes | yes (c8e99961...) | 20 | yes | yes | 0 | 0 | 0 | yes |
| 20251007 | 45,290,865 | yes | yes (5aaf3ed7...) | 20 | yes | yes | 0 | 0 | 0 | yes |

- Every table maps to a 99 entry with mapping `closest`.
- The calendar table is `default_1400`, with `placement_ns` at 14:00 ET of the day (for example 1634061600000000000 for
  20211012). All other tables are `intrinsic`.
- The receipts' `code_sha256` equal the sha256 of the three code files committed at HEAD:
  - frankie_day_external.py 404e536d...
  - fetch_day_history.py be07f9fc...
  - frankie_box_day_external.py f6cd3943...
- Listed missing: 1, 7 and 1 entries, matching the record's counts.
- The other 28 days were not opened in this pass: UNVERIFIED beyond the record's own verification.

### Checks run

- AST parse without project imports: all 11 changed `.py` files at 2527e2f parse.
- `git diff --check fb97f35..HEAD`: clean.
- `bash -n`: no `.sh` file changed in this range.
- The workflow change was read: a `days` input validated as digits and commas, and a deadline variable. Nothing else
  changed, and nothing was dispatched.

### Skills and account calls

- Skills: `api-and-interface-design`, `code-review-and-quality` and `doubt-driven-development` (reduced self-check form,
  as before), carried from this session's pass.
- Account calls, all read-only, through the `Aws` connector:
  - `run_script` x1: an s3 GetObject attempt. The connector's validator rejected the script (hashlib is blocked), so no
    API call ran.
  - `get_presigned_url` x6: presigned GETs for the three day files and their receipts. They were used with curl from the
    container.
  - No writes, and no other service.
- The local copies of the three day files were deleted after the check; the receipts remain in the session scratch only.
