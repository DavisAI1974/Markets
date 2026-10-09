# DROP-IN, session 13 (from session 12, 2026-10-09 16:3xZ), for Claude or Codex

Greg's usage is nearly out: this box is written so a fresh session (Claude or Codex) can take over without the chat.

## THE BOX (state at 16:30Z, 2026-10-09)

- Branch `ccr-d2f8f826-iefeah-frankie` (SHALLOW: `git fetch --deepen=400` first). Tip = this commit. Every commit of
  session 12 is on GitHub and ON THE BOX (code `3071eac8` current; this handoff commit is docs only).
- Box `i-035994afa8bdf66a5` (r7i.16xlarge, 64 CPU, 495 GB, us-east-1) RUNNING. Day `e2e-20231018-a2/20231018`
  (attempt `-a1`, 64-CPU booking) in its finish: the TEACHER is sealing blocks, the CLASSROOM runs one lesson at a time.
- Teacher: pid on code `3071eac8`? NO: the teacher runs on `b8ec5d3d`-era code? NO: the teacher process was started
  at 15:22:11Z on `bd8c1a57` and never restarted since (its code root is fixed for its life; the sealing code is in
  it). At 16:27Z: 28 blocks sealed, next_cursor 168,212 of 771,787, manifest status `sealing`. It seals a block
  about every 50 s and will run for hours (the merge is ~130 rows/s plus the seals).
- Classroom: class worker unit `frankie-queue-class-*` on code `3071eac8` (pid 32938 at 16:23Z), ONE worker process,
  blocks in seal order. Sessions complete: blocks 1-20 (1-4 sequential on the first code; 5-18 under the 64-worker
  build before Greg's one-lesson rule, same computation; 19-20 sequential). Each block 160-300 s.
- Outputs: teacher blocks `/opt/frankie-box/work/experiment-teacher-rows/20231018/{teacher-blocks.json,blocks/<n>.json,
  host-dipole-classroom-source.c15.rows.jsonl}`; classroom `/opt/frankie-box/work/experiment-roots/
  e2e-20231018-a2-20231018-a1/work/classroom/blocks/<n>/` (lesson.json, second_set.json/.jsonl, store.jsonl +
  store.index.jsonl (answers written once, other files are `$ref`s), session.json (status, seconds, steps, external),
  TEACHER_REPORT.md, brain-update.json).
- The block-1 TEACHER REPORT as written on the box: `research/kalshi/frankie_boss/TEACHER_REPORT_20231018_BLOCK1.md`.
- Gauge: `/opt/frankie-box/work/gauge-block1/gauge.jsonl` (block 1 re-run per code version); profile:
  `/opt/frankie-box/work/profile-block1/run-162428.log` (the external section of block 1 under cProfile).
- Swap: 400 GB swapfile `/opt/frankie-box/archive/swapfile` (priority -1, unused): REMOVE when the day is done.
  Archive volume raised in session 8: revert to baseline when the day is done. Disk 52% at 15:49Z.
- Check-in routine armed: `trig_01J5eZ85p9CxSLL8gyvGUzfv` fires 16:49Z into session 12 (delete it from the new
  session with `delete_trigger`, or let it fire into the old session harmlessly).
- Helper agent of session 12 (a8a9c17f72e7928d6, worktree `worktree-agent-a8a9c17f72e7928d6`) was asked for an
  ANALYSIS of the evidence-hash cost (below); it may still be writing. Its worktree has no uncommitted work.

## GREG'S RULES OF SESSION 12 (binding)

1. THE SCIENCE IS NEVER WEAKENED FOR SPEED. Nothing computed, answered, graded, carried or written as evidence is
   reduced, sampled, truncated or approximated. Speed comes only from doing the same work once, in the right order,
   or at once where nothing depends on anything.
2. ONE LESSON AT A TIME: block sessions run one after another in seal order (`BLOCK_LESSONS_AT_ONCE = 1` in
   frankie_box_experiment.py). Inside a lesson, pieces that need nothing from each other run at once.
3. Everything runs at once EXCEPT what needs another piece's output first; the run order is prerequisites only.
4. THE FIRST 5 MINUTES ARE THE GAUGE: block 1 (22:00-22:05Z of the trade day, 1,588 rows) is re-run through the
   whole classroom session on every code version (`deploy/aws/box/frankie_box_block_gauge.py`); every speed claim is
   that number. Block 1 first code 163.3 s; current code 159.0 s.
5. DISCUSSION FIRST on the external section: Greg asked for options, not code. Do NOT change the external section or
   the hashing until Greg picks (the options and the finding are below).
6. From sessions 10-11, still binding: keep the workflow running; our own gates never block fine data; no coded
   waits; fixes go on the box the moment they are pushed (the push route below); code version recorded never
   compared; no lists, no records of code changes beyond commits; push every fix; no infrastructure change calls at
   a session's end; "only one canary" (block 1 is it); forward reads are not a concern (only the forecaster is blind).

## WHAT SESSION 12 BUILT (all live on the box, all on the branch)

- Streaming block publication by the teacher: `frankie_box_teacher_blocks.py` (schedule 5,30 minutes on the receive
  clock from the trading-day open 2023-10-17T22:00:00Z; cutter; atomic sealer; manifest FRANKIE_TEACHER_BLOCKS_V1),
  wired into `frankie_box_experiment_teacher.py` (`_BlockFeed`: seals in the walk and in the prefix merge; at the
  final publication every block is rebuilt from the whole-day result and compared; a difference never refuses the
  publication, the whole-day sidecar is written and the blocks listed failed). Reader `frankie_box_teacher_rows.py`
  (`blocks`, `block_record`, `iter_block` (sha-checked, streamed), `BlockSidecarStream`, `follow_blocks`).
- Classroom per block: the class door opens on the digest AND one sealed block (`Run.classroom_ready`,
  `early_class_door` in the finish while the teacher runs); `Run.class_blocks` runs `K.block_work` per block (lesson
  then the WHOLE session: key from the block's rows, Frankie's 19 answers, grade, cross-check, novel findings,
  correction, acknowledgement, completion, external section at the block's cutoff, brain-update.json,
  TEACHER_REPORT.md, session.json last with per-step seconds). Still day-end only (listed in each session.json):
  SOCRATIC/VERIFY, market context, exhaustion/D, the teacher account, the brain entry <day>-cycle-00, Jev, exchange,
  meeting, school, day reports.
- Write-once block store (`_BlockStore`, `block_load`, `block_render`): block 3: 4,229 MB -> 1,482 MB written, time
  unchanged (the writing was never the cost).
- Fixes on the box today: resume reconciles a dead finish holder itself (3c068058); teacher prefix merge by reference
  (efc27574, 4 CPUs -> full speed); `_block_dump` uses the lesson's JSON form (default=str), json_form refused a bytes
  value and failed the class line for 8 min (af184570); external section in a forked child of the block worker
  (3071eac8).
- Hub (built, unwired, proven by drivers only): frankie_box_hub.py, frankie_box_hub_spokes.py,
  frankie_box_hub_compare.py, frankie_box_hub_doctor.py; HUB_CALC_ORDER_MAP_20261009.md. Both teachers read the whole
  second set. ROOT_REPORT_1_PREVIEW_20231018.md.

## THE FINDING GREG IS DECIDING ON (16:29Z)

Profiler (`deploy/aws/box/frankie_box_block_profile.py`, block 1, fresh process, under cProfile): external.section
55.9 s, external.pre_binding 139.7 s, external.answers 0.161 s, external.grade_correction 57.5 s. ALL the time is
`research/kalshi/frankie_boss/c15_journal.py:129 evidence_hash` -> `causal_packet.py:315 canonical_bytes` ->
`causal_packet.py:295 _canon` (pure-Python canonicalizer: 40M recursive calls, 226M isinstance calls in pre_binding
alone) hashing ~56 MB objects (the external key 55,942,338 bytes and pre-message 56,047,568 bytes) 4 times in
pre_binding and 9 times in grade_correction. The external SCIENCE (answers) is 0.16 s. The main chain's
key_pre_message_binding (8-58 s) and store_writes (17-46 s) very likely hash the same way.
The fix that keeps every number identical: hash each object once per block and reuse; make the canonicalizer fast
with BYTE-IDENTICAL output proven by hashing the same objects both ways. Applies to every piece using evidence hashes.
Options Greg was given before the profile (now secondary): (1) external part once per day as the old flow; (2) build
the section once per day file, slice per cutoff (verify: block 1 section sha
052d6fe90ba24d753b3029388105d812ea6644e307e755e0959913f310caecc7 must reproduce); (3) one external section in the
hub for all spokes; (4) incremental per block ("latest replaces in place").
Greg's open questions at close: "the piece that speeds it up 250 M per sec" (unidentified: ask him which); "the
other 8 on 8 consecutive days" (unclarified: which eight; nothing scheduled).

## COMMANDS

Push code to the box (no staging; the moment it is pushed):
```
python3 deploy/aws/box/frankie_box_push_bundle.py build --commit <sha> --base <box current sha> --output <pack>
# presigned PUT/GET on s3://frankie-granite42-568968024170-us-east-1/readiness/20260923/code-push/<sha8>/<packsha>.pack
curl -X PUT --upload-file <pack> "<PUT url>"
# SSM (AWS-RunShellScript, keep every command under ~55 s; the MCP run_script tool times out at 60 s):
export BASE_SHA=.. BUNDLE_BYTES=.. BUNDLE_KIND=delta BUNDLE_SHA256=.. MARKETS_SHA=.. BUNDLE_URL='<GET url>'
sh "$(readlink -f /opt/frankie-box/code/current)/deploy/aws/box/frankie_box_push_code.sh"
```
Restart the class worker on the new code (the teacher is NOT restarted for classroom changes):
```
CR=$(readlink -f /opt/frankie-box/code/current); cd $CR
U=$(systemctl list-units --type=service --no-legend 'frankie-queue-class*' | awk '{print $1}' | head -1); systemctl stop $U
# wait until `pgrep -f 'line class'` is empty (a stop waits for the running block session, up to 90 s)
CODE_ROOT=$CR MARKETS_SHA=<sha> FRANKIE_ROOT_DIGEST=off FRANKIE_CLASSROOM_CPUS=all ACTION=kick LINE=class \
  SCOPE=e2e-20231018-a2:20231018 RUN=e2e-20231018-a2 DAY=20231018 sh deploy/aws/box/frankie_box_frankie_queue.sh
# verify: the new worker's cmdline names the new code root; another kick can race in (it did once): check, re-kick.
```
Teacher save/stop/resume (only for teacher-code changes): ACTION=save RUN=.. DAY=.., stop the `frankie-queue-root-*`
unit, wait for the teacher pid to go, then ACTION=resume with the same env (resume reconciles the dead holder).
Gauge (block 1 on the current code; run it under systemd-run, an SSM shell's children die with the command):
```
systemd-run --unit=frankie-gauge-$(date +%s) --collect -p WorkingDirectory=$CR sh -c "/opt/frankie-box/venv/bin/python -B \
  deploy/aws/box/frankie_box_block_gauge.py --rows-dir /opt/frankie-box/work/experiment-teacher-rows/20231018 \
  --ingest-dir /opt/frankie-box/work/ingest-20231018-gh-36571235912-1 --day 20231018 --out /opt/frankie-box/work/gauge-block1 > /opt/frankie-box/work/gauge-block1/run-\$(date +%H%M%S).log 2>&1"
```
Probes: teacher manifest `teacher-blocks.json` (blocks, next_cursor, status); classroom `blocks/<n>/session.json`
(status, seconds, steps, external.seconds); class events `/opt/frankie-box/work/frankie-queue/class-events.jsonl`;
root events `root-events.jsonl`; class worker log `/opt/frankie-box/work/frankie-queue/logs/class-worker.log`.

## NEXT (in order)

1. Greg's decision on the evidence-hash fix (hash once + byte-identical fast canonicalizer); then build it, prove it on
   the gauge (block 1 session seconds and the SAME hashes as before), push to the box, restart the class worker.
2. Keep the day running to its end: the teacher's final publication (blocks verified against the whole day), the
   whole-day classroom, Jev, exchange, school, the day reports; then Greg reads the TEACHER REPORT whole.
3. After the day: remove the swapfile; revert the archive volume; hub wiring per piece after by-value comparison
   (`frankie_box_hub_compare.py`), the one-pass build, the ROOT fix; then the 30-day.
