# Stacks pass, 2026-10-07 night (session 5): the Run controller (`deploy/aws/box/frankie_box_experiment.py`)

Owner of this pass: the Run controller agent (narrow integration of the stage owners' cross-owner requests). Branch
`ccr-d2f8f826-iefeah-frankie`; SOURCE-ONLY, nothing ran on AWS or the box. Every edit is additive and minimal; Run.jev's
booking/lane/queue rules, the booking sizes, the queue protocol, the Jev runtime pins and Pod refusal are unchanged.
The parent's WIP snapshot commits swept the working-tree edits into `1896354` and `6830dce` while this pass ran (the
diff below the "Checks" section was taken against the tree at the time of writing; nothing here is staged for a run).

Everything in this record is SOURCE-BUILT / RUNTIME-UNVERIFIED: py_compile, ast.parse, `git diff --check`, `bash -n`
on the two shell files, and toy tests of the three pure functions (section 8). No stage child, ledger or systemd unit
ran.

## 1. Exit 75 = saved, one helper for every stage child (school R6, reports X5, ingest S1 on the Run side)

What the day thread already did: a stage child that exits 75 on this owner's STANDING save marker never reaches a step:
`Run.child` calls `check_save()` right after the child (now :1426) and raises `SystemExit(75)`; the queue's day thread
(`frankie_box_frankie_queue._thread_end`, 1571-1580) classifies the DAY saved with its slot retained (`_end_slot`). A 75
WITHOUT the standing marker (the child's own save route: a SIGTERM to the child, mark only, run to the next save point,
exact durable state; every stage now exits 75 that way) was recorded `failed` by every step, and counted as a failed
teacher call by `Run.lessons`.

Built:
- `SAVED_EXIT = 75` (:146) and `Run.child_saved(stage, key, code, log=None, **fields)` (:1190-1217): None unless the
  code is 75 and the ledger did not print a "waiting for a CPU booking" line for this call (that 75 is "not started":
  the caller's own waiting record, as before); else the step's `saved` receipt (status `saved`, exit_code 75, the
  reason, the caller's fields). `done_status` is False for `saved`, so the next start re-runs the step, which reuses its
  saved pre-read and written work; the day's later steps read `saved` as not finished and wait, exactly as for
  `waiting`. Nothing is booked or released by it (a step inside the held slot never touches the booking).
- Call sites, each `saved = self.child_saved(...)` / `if saved: return saved` placed before the step's failure
  classification: ingest :1533 (after the ledger's waiting check :1527; records the directories made, the ledger line,
  the RESUME_DIR candidate), root :1669 (the claim is NOT ended on a save: `claim_root` retakes this box's own claim
  when no ROOT of the day runs, :1740-1744 unchanged; recorded on the receipt as `claim`), external :1921, classroom
  :2301, reports :2515 (X5), exchange :2972, school :3527, teacher :4109 (a batch receipt), data :4448, search :4495,
  accumulated_lessons :4569, survivors :4693.
- `Run.lessons` (:4643-4657): a teacher call that exits 75 (ledger line not waiting) stops the loop (no following call
  is started after a save; the calls not started are listed on `calls` with `not_started`), and the batch is recorded
  `saved` through `classify_child_calls(results)` (:656, pure: saved = exit 75, bad = every other nonzero); `survivors`
  is not run after a saved batch. The next start re-runs the batch: the finished calls' written lessons are reused
  (`lessons_written`, unchanged), the saved call resumes its own saved pre-read.
- Not changed: `Run.jev` (exit 75 without a receipt/status is `waiting`, the exchange owner's rule, :3864-3871);
  `Run.voice` (the meeting has no save route in this pass; a nonzero exit stays its own classification);
  `jev_context_read` (returns a status dict, not a step receipt; a 75 there reads `retained_nonzero_exit` or
  `failed` with the exit named); `fetch` (no save route). `record()`'s own "waiting on the ledger line" rule is
  untouched.

## 2. Reports X4: no read-back

`Run.reports` :2476-2481: the loop that read both report files back into the Run's log is replaced by one log line per
report from the step's own receipt (kind, number, revision, file, sha256, existing). The child's log already holds the
reports in full. The receipt (`reports_receipt`) is read once, as before.

## 3. Probe directories (teacher 4, ingest X4, reports X6)

The reader (`frankie_box_stage_progress.Heartbeat`, the reports owner's extension) finds a FRANKIE_WORK_PROBE_V1
progress.json in the caller's `probe_dirs` first, then in every absolute directory under `/opt/frankie-box/work/` that
a process of the tree names in its environment, command line or working directory (comma-separated values split), then
beside open files. Chosen form: BOTH, since the reader understands both and they cost one small read each.
- `probe_directories(stage, env, code_root, work_root=None, box_root=None)` (:665-699, pure, toy-tested): every
  absolute work path an env value names (a directory, or a file's own directory; lists split on commas), then per
  stage: teacher `experiment-teacher-rows/<day>` for each day of DAYS; ingest/fetch the block data directory
  `/opt/frankie-box/data/block_<block>` (from the committed manifest's `block`; OUTSIDE the work root, so the generic
  reader never finds it on its own) and RESUME_DIR; reports `REPORTS_DIR/receipts/<run>`. Deduplicated, the work root
  itself never named.
- `Run.child` :1376-1383: the list is exported to the child as `FRANKIE_PROBE_DIRS` (`PROBE_DIRS_ENV`, :148), so the
  forked/spawned pool workers inherit it and the reader finds the directories from any process of the tree; :1401-1403
  the same list is passed to the Heartbeat as `probe_dirs` after the existing OUTPUT_ROOT (checked first).
- `frankie_box_frankie_queue.RUN_SETTING_IDENTITY` :501-503: `FRANKIE_PROBE_DIRS` added, so a kicking process never
  carries a child's probe directories to the line workers as a run setting (it never has it in its own environment
  either; the entry makes the rule explicit).
- The ingest's fresh output directory (`ingest-<block>-ingest-<ts>`, created by the wrapper at run time) is not known
  before the child starts; the reader finds it from the tool's `--output-dir` argument (under the work root).

## 4. School R2: one scientific-teacher child per batch

NOT done, recorded for the school owner. `frankie_box_scientific_teacher.py` :2368-2369 take ONE `--frankie-ledgers`
with ONE `--frankie-day` (`frankie_box_scientific_teacher.sh` forwards `FRANKIE_LEDGERS`/`FRANKIE_DAY` once); there is
no repeatable pair. Per the pass's rule, no argument was invented. Request to the school owner: a repeatable
`--frankie-ledgers PATH --frankie-day YYYYMMDD` pair (and a wrapper form, e.g. `FRANKIE_LEDGERS=day=path,day=path`),
one `--jev-stamp` per day likewise; `Run.lessons`' per-call `lessons_written` reuse (:4614-4620) would then be checked
per claims source before the one batch call, and the batch receipt would carry one call. Until then `Run.lessons`
starts one child per claims source (unchanged), each hashing the parts and native ledgers again.

## 5. Ingest S1 (cores and queue side) and S2 (KillMode)

- `frankie_box_cores.py`: `SAVED_EXIT` (:120), `SAVE_RETAINED_KINDS = ('ingest', 'canary')` and `RETAINABLE_KINDS`
  (:124-128). `cmd_run` :888-903: a job of a SAVE_RETAINED kind that RAN and exited 75 (the ingest's INGEST_SAVED with
  ingest-saved-<ts>.json, as the wrapper distinguishes at `frankie_box_ingest_block.sh` 326-333) keeps its booking:
  `retain(booking, run, day)` with the reason, exactly as a saved day's slot; the ledger's own "waiting" 75 never
  reaches this code (cmd_run returns before the job). A retain error falls back to the release as before.
  `retain()` :632-633 accepts RETAINABLE_KINDS (was day-run only). `book_locked` :515-543: without `--cpus`, the owner
  of a booking retained on a save (same kind, run, day; the ingest's `--run` is its RESUME_DIR's basename, `--day` the
  block) takes it back IN PLACE on the retained CPUs (the size asked is recorded as `size_asked`, never applied: a
  saved job resumes on its own CPUs), after the same orphan check as the `--cpus` take-over; without this the retained
  set would wait on itself for ever. Day-run slots are excluded from both (the queue's own retain/`--cpus` resume
  protocol is unchanged). `reap_locked` is unchanged (a retained booking is never reaped).
  Caveats, runtime-unverified: `frankie_box_ingest_block.sh` 328 still says "the booking was released by
  frankie_box_cores.py run" (the ingest owner's file; now retained); a resumed ingest whose DAY_CPUS=auto sizing differs
  from the retained set runs on the retained set with WORKERS computed from the new size (the ingest pins to
  FRANKIE_BOOKED_CPUS and its output never depends on the count, per its own contract).
- `frankie_box_frankie_queue.py` ~175 (`save`) runs no ingest child; the queue runs the ingest only through
  `Run.ingest`, which now records exit 75 past the ledger line as `saved` (section 1). Nothing else to pass through.
- S2 `KillMode=mixed` with the reason in a comment: `frankie_box_frankie_queue.py` :406-408 (kick: the line workers,
  which run every stage child incl. the ingest when the queue is on) and :487 (handover); `frankie_box_experiment.sh`
  :155-159 (the detached orchestrator unit: the ingest under a plain start runs here); `frankie_box_cpu_controller.sh`
  :147-150 (the Linux lane controller). A stop now signals the main process only; the remainder is SIGKILLed at
  TimeoutStopSec (default 90 s) -- a `systemctl stop` is still not the save route (ACTION=save, the marker, is); the
  session/heartbeat/correction units of `frankie_box_session.sh` are not stage units and are unchanged.

## 6. Jev X6 (retained request identity by content)

DEFERRED with the restage case measured and named. `Run.jev` :3757-3777 and `Run.jev_source_rebind` (:3939-3961): when the
retained request differs from the one this checkout builds and no REBOOK successor stands, the refusal now carries
`source_rebind` = {saved_source, current_source, bound_moves (content_rebinds over the bound keys less `source`),
pins_equal (classroom receipt, search manifest, runtime config sha256), content_equal}; `content_equal` True means a
restage with equal bound content (source alone differs), and the reason names it. It is still refused because the
helper binds `source.commit` itself: `frankie_box_jev_cpu.py` 398 (the held booking's commit must equal the request's),
408-410 (MARKETS_SHA and CODE_ROOT must equal the request's source) and `bind_owner` 208-215 (the whole retained owner
identity through content_rebinds, where a changed commit is a plain value difference, not a checkout move). Accepting at
the Run alone would move the refusal into the helper on every start. Accepting form (joint, listed for the exchange
owner + Run): the Run mints a `.source<n>` successor request (the `jev_rebooked` chain shape) with the new `source` and
a link `source_rebind.of = file_pin(previous)`; the helper's `request_chain` follows that link, `bind_owner` excludes
`source` from the content identity, and 398/408 accept the successor's source. Old requests load unchanged.

## 7. Other requests addressed to the Run controller: verdicts

- Teacher 4 (probe_dir for `experiment-teacher-rows/<day>`): DONE (section 3).
- Ingest X4 (ingest output and block data directories as probe_dirs): DONE for the block data directory and
  RESUME_DIR; the fresh output directory is found by the reader from the tool's command line (section 3).
- Reports X4, X5: DONE (sections 2, 1). Reports X6 (stage owners name their probe directory): the Run side names what it
  knows and exports FRANKIE_PROBE_DIRS; each owner's own writing location is theirs.
- School R6: DONE (section 1), generalized to every child step listed there.
- School R2: deferred, request recorded (section 4).
- Exchange X2 (keep `request['cpus']` = the held booking's CPUs): unchanged, confirmed (:3731).
- Exchange X3 (re-dispatch of interrupted Jev calls): the exchange owner's own edit (:3806-3812), not touched.
- Exchange X6: deferred with the measured report (section 6).
- Ingest S1, S2: DONE (section 5).
- Reports F3 / School R5 (content dedupe): Greg's call, not the Run's; nothing done.
- Every lane_pin / market_timeline / teacher_knowledge / jev_cpu request in those records is another owner's.

## 8. Checks

- `python3 -m py_compile` and `ast.parse` on frankie_box_experiment.py, frankie_box_cores.py,
  frankie_box_frankie_queue.py: OK. `bash -n` on frankie_box_experiment.sh and frankie_box_cpu_controller.sh: OK.
  `git diff --check`: clean.
- Toy tests (`/tmp/claude-0/-home-user-Markets/2248cf40-1f2f-560c-b5b2-bc0289b3f56b/scratchpad/run_controller/toy_tests.py`,
  all passed): `classify_child_calls` (saved/bad split, empty, all-zero); `probe_directories` (root OUTPUT_ROOT only;
  teacher rows per DAYS plus comma-split receipts' directories; ingest RESUME_DIR + block data directory from the
  manifest, absent manifest -> no block dir; reports receipts dir; a file's parent, the work root itself never named;
  non-work paths such as BRAIN excluded); `Run.jev_source_rebind` (source-only difference with equal pins ->
  content_equal; a pin differing -> False; another bound key differing -> bound_moves None).
- Runtime-unverified: every stage child's actual 75 path, the `saved` receipt through the start loop and
  `finished()`, the ledger retain/take-over on a real box, the systemd KillMode behaviour, the heartbeat finding the
  named directories.
