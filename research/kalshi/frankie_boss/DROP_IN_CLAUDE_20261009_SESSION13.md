# DROP-IN, session 13 (from session 12, 2026-10-09 16:4xZ), for Claude or Codex

## SESSION 13 RAN (Claude, 2026-10-09 23:5xZ -> 2026-10-10 06:5xZ): the day is RUNNING again on the tip; the box's own package upgrades killed it once

- AWS came back (Greg: "Aws should be good"). Box STARTED 23:58Z, tag KeepRunning=true; the tip 4e5ca5d pushed by the
  push route (delta pack, 20.7 s) = `/opt/frankie-box/code/current`; ACTION=resume at 00:01Z reconciled the dead finish
  holder itself; root, class and teacher lines came up on the tip.
- The teacher walk ENDED 04:04:35Z: 47 blocks sealed (block 47 `final: true`), cursor 771,787 = the whole day; the
  prefix merge after a resume re-feeds the sealed rows as carry (~112 rows/s) and walks the rest at ~44 rows/s on one
  core. Then the teacher went into its whole-day second set (`_second_set` -> `teacher_book_read.assemble` ->
  `state_split`, one thread, 305 GB RSS, ~54% of the rows after 80 min; it writes nothing until it is done, so the
  manifest stays `sealing`; `py-spy dump --pid <teacher> --locals` shows the `cursor` local in the assemble frame).
  The classroom ran blocks 23-42 (240-984 s each, the time scales with the block's rows; no new errors).
- THE KILL (06:09:53Z): Ubuntu's `apt-daily-upgrade` timer ran unattended-upgrades (libssl3, libxml2, a kernel, ...),
  which re-executed systemd and restarted every service holding the old libraries, the two frankie transient units
  among them: SIGTERM at 06:09:53Z, "stop-sigterm timed out", SIGKILL of root/class/teacher at 06:11:23Z. Not OOM
  (dmesg clean; 495 GB box, root unit peak 461 GB). The teacher lost its second set 2.5 h in; the classroom its block 43.
  The re-started workers parked ("every pending day is held by its owner ... only ACTION=resume moves it").
- THE FIX ON THE BOX (06:4xZ, applied and verified): apt-daily.timer + apt-daily-upgrade.timer disabled, their services
  masked, unattended-upgrades disabled, `/etc/apt/apt.conf.d/99frankie-no-auto-upgrade` (periodic 0),
  `/etc/needrestart/conf.d/99-frankie-no-restart.conf` (`$nrconf{restart} = 'l'`). The same block is now in
  `deploy/aws/box/frankie_box_worker_setup.sh` for every future box. (A newer kernel is installed but not running; a
  reboot would boot it. Nothing else changed.)
- RESUMED 06:45:51Z (ACTION=resume, same env as THE BOX step 2): teacher restarted at next_block 48 / cursor 771,787
  (its log `/opt/frankie-box/work/experiment-teacher-rows/logs/20231018-1791614754.log`): it re-feeds all 47 sealed
  blocks as carry (~2 h), assembles the second set (~2.5 h), then publishes; the class worker resumes blocks 43-47,
  then the whole-day classroom, Jev, exchange, school, day reports.
- The evidence-hash fix: NOT touched (rule 5). Verified locally: on `pack` output `_canon` is the identity, so
  `canonical_bytes(pack(x)) == json.dumps(pack(x), sort_keys=True, separators=(',',':'), ensure_ascii=True).encode()`
  byte for byte (every edge type and a 30 MB row-shaped object: same hash; 3.5x faster here). Recommendation stands:
  (b) inside evidence_hash in shadow mode on the box, then (a), then the store. Greg has not picked.
- Check-ins: this session armed its own (send_later) and re-arms them; probes are in COMMANDS.

Greg's usage is nearly out: this box is written so a fresh session (Claude or Codex) can take over without the chat.

## THE BOX: STOPPED 16:37Z (Greg: "Kill box for right now taking a break")

- Branch `ccr-d2f8f826-iefeah-frankie` (SHALLOW: `git fetch --deepen=400` first). Tip = this commit. Every commit of
  session 12 is on GitHub and ON THE BOX (code `3071eac8` = `/opt/frankie-box/code/current`; later commits are docs).
- Box `i-035994afa8bdf66a5` (r7i.16xlarge, 64 CPU, 495 GB, us-east-1) STOPPED at 16:37Z, tag KeepRunning=false.
  Stopped cleanly: ACTION=save written, every frankie unit stopped, no frankie process left, disks synced.
- Day `e2e-20231018-a2/20231018` (attempt `-a1`, 64-CPU booking retained) as left: root entry `done` with its finish
  reading `running` on a dead holder (ACTION=resume reconciles that itself); class entry `saved`. TEACHER manifest:
  29 blocks sealed, next_cursor 190,923 of 771,787, status `sealing` (the resumed teacher continues the manifest from
  the next block; its walk save is the raw-state save, the prefix merge restarts from row 0 and re-feeds the sealed
  rows as carry only). CLASSROOM: block sessions 1-22 complete; a resumed class worker keeps every block with a
  session.json and runs the rest one lesson at a time.
- RESTART (in order; each SSM command under ~55 s, the MCP run_script tool times out at 60 s):
  1. `StartInstances` + tag KeepRunning=true; wait for SSM Online. Then PUSH THE TIP to the box (COMMANDS below; the
     box's current is 3071eac8 and the tip carries the seal-gate removal Greg asked for at close: the publication
     pins the sealed sidecar by one read instead of rebuilding and comparing every block, and the block reader no
     longer re-reads a block for its sha256 before yielding its rows).
  2. `CR=$(readlink -f /opt/frankie-box/code/current); cd $CR; CODE_ROOT=$CR MARKETS_SHA=$(basename $(dirname $CR) | cut -d- -f1)
     FRANKIE_ROOT_DIGEST=off FRANKIE_CLASSROOM_CPUS=all ACTION=resume SCOPE=e2e-20231018-a2:20231018 RUN=e2e-20231018-a2 DAY=20231018
     sh deploy/aws/box/frankie_box_frankie_queue.sh` (resume reconciles the dead finish holder, re-points the slot, kicks the
     root worker; the finish restarts the teacher child on `current` and the early class door re-enqueues the class with the slot
     and kicks the class worker). If the class line does not start within a minute: the class kick from COMMANDS below.
  3. Probe the teacher manifest and `blocks/<n>/session.json` (COMMANDS, Probes).
- Teacher code note: the teacher child runs whatever `current` is when the finish starts it (after a resume: 3071eac8
  or newer); a teacher-code change while it runs needs the save/stop/resume below.
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
- No check-in routine is armed. A new session arms its own if it wants one.
- Greg at close (2026-10-09 16:36Z): "running this on future days as the data is loading instead of waiting for the
  full day to fill in will save us a lot of wait time" = the streaming design is the standard for every later day:
  the teacher seals blocks as the data arrives and the classroom lessons start on block 1; no day waits for its full
  fill. (On this day the sealing started after the walk; the 30-day wiring makes the seal follow the ingest.)

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
WHAT THE EXTERNAL PART REUSES TODAY (read from the code at close, Greg's question): within a block the section is
built once and the answers computed once, then the same key and pre-message are hashed 13 times (bookkeeping, not
science). Across blocks only the parsed, checked day file is reused inside the worker process (commit 7); each block
rebuilds its own section at its own cutoff, its own answers and grade; the prior-external-grade/history chain runs
day to day (`previous`, external-history.json), never block to block. Across pieces nothing is shared: the day-end
classroom builds its own section in its own directory (reused only if one already stands there, which the blocks
never write); the school reads the day-end one; Jev and the exchange read none. Options 3 and 4 above are what
would close that.
THE HELPER'S ANALYSIS (a8a9c17f72e7928d6, 16:36Z, no files changed; the decision is Greg's):
- `evidence_hash(x) = sha256(SCHEMA + NUL + canonical_bytes(pack(x)))`; `pack` and `_canon` are recursive pure Python.
  `pack` emits only lists, exact str/int/bool and tag strings (floats as IEEE hex strings, bytes as hex, None as
  ["null"], dicts as tagged lists), so on pack output `_canon` is the IDENTITY and
  `canonical_bytes(pack(x)) == json.dumps(pack(x), sort_keys=True, separators=(',',':'), ensure_ascii=True).encode()`
  BYTE FOR BYTE (tested on a 7.9 MB key-shaped object and on every edge type: same bytes, same hash). The fast path
  is 4.4-10x faster and must apply ONLY inside evidence_hash / the journal's canonical_bytes(pack(...)) uses, never
  to canonical_bytes on raw values (there _canon quantizes floats, sorts Mapping keys, converts numpy). Prove it on
  the box in SHADOW mode (every evidence_hash computes both and asserts equal) on block 1 and one large block.
- Per block the external key's content enters 5 large hashes (E1 key, E2 verify, E3 pre-message, E5 model-visible,
  E6 verify again); only E1 and E3 are new content. The Dipole main chain repeats similarly (snapshot verified twice,
  pre-message hashed then discarded and re-hashed, post-grade hashed 3x, correction 2x). store_writes (22.9 s) is the
  block store re-serializing the same objects per file and per subtree. The day-end classroom calls the same
  functions on ~770k rows: far larger there, same fixes.
- Estimates for block 1 / a 9,000-row block: now 159 / ~300 s; forked child only ~122 / ~270; (a) hash once ~82 /
  ~205; (b) fast canonicalizer ~50 / ~110; (a)+(b) ~42 / ~85 (then bound by the main chain and the section build's
  non-hash work ~30 s); store write-once serialization 22.9 -> ~7 s.
- Recommendation: (b) first (one change inside evidence_hash, byte identity by construction, shadow-checked on the
  box), then (a) as explicit carry-the-hash / skip-the-discarded-intermediate parameters at the named sites, then the
  store. Side finding: cyclic GC doubles a large hash's cost (3.44 s -> 1.54 s with gc.freeze()).
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

1. Start the box and resume the day (THE BOX above). Greg's decision on the evidence-hash fix ((b) then (a) above);
   then build it, prove it in shadow mode and on the gauge (block 1 seconds and the SAME hashes), push, restart the
   class worker.
2. Keep the day running to its end: the teacher's final publication (blocks verified against the whole day), the
   whole-day classroom, Jev, exchange, school, the day reports; then Greg reads the TEACHER REPORT whole.
3. After the day: remove the swapfile; revert the archive volume; hub wiring per piece after by-value comparison
   (`frankie_box_hub_compare.py`), the one-pass build, the ROOT fix; then the 30-day.
