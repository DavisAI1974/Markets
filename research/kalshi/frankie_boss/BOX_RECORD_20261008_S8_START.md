# Box record: session 8 START of the main box + resume of a2/20231018 (2026-10-08, BOX-OPERATOR role)

Greg's go: "Go" (start the main box i-035994afa8bdf66a5 and resume the saved day e2e-20231018-a2/20231018).
Limits: only i-035994afa8bdf66a5 (us-east-1d, r7i.16xlarge). No other instance, no clone volume, no snapshot, no IAM,
no quota, no launch template, no fleet, no digest render, no classroom, no stop. AWS via the Aws connector only;
GitHub dispatch via the github MCP tools. Every action below carries its UTC timestamp and result; written as it happens.

## Orientation (read-only)
- Container branch ccr-d2f8f826-iefeah-frankie, local tip 85ce2827 (session-8 AWS account upgrades commit).
- Read: DROP_IN_CLAUDE_20261008_SESSION8.md, DROP_IN_CLAUDE_20261008_SESSION7.md, E2E_ONE_DAY_20231018.md "Session 8"
  sections (CPU plan + Greg's five decisions), frankie_box_stage_code.sh, frankie_box_run.yml,
  frankie_box_frankie_queue.sh header, BOX_RECORD_20261008_S6_RELAUNCH.md (the session-6 resume/kick precedent).
- a2 kick values (E2E "Session 8, later"): ACTION=resume RUN=e2e-20231018-a2 DAY=20231018; ACTION=kick LINE=root
  SCOPE=e2e-20231018-a2:20231018 with FRANKIE_ROOT_DIGEST=off FRANKIE_CLASSROOM_CPUS=all; DAY_CPUS not given (retained
  booking 0-31 governs); FRANKIE_CLEAN_ON_SAVE at its default (on); the class line's kick carries the same
  FRANKIE_CLASSROOM_CPUS. The kick starts the CPU watchdog loop (decision 4).

## Timeline
- 14:26:19Z `git fetch origin ccr-d2f8f826-iefeah-frankie`: origin tip 85ce2827c82f4a9c4894f15e9a7a25537afdf4e1 (= local tip;
  the session-8 AWS upgrades commit; parents 5d0fccf4 drop-in, e5342ef0 E2E record, 04a3d506 watchdog, a1779f2c jev).
  Not a WIP snapshot. This is the tip to stage.
- 14:27:04Z STEP 1 read-only (Aws connector, ec2 us-east-1): i-035994afa8bdf66a5 state STOPPED, r7i.16xlarge, us-east-1d,
  KeepRunning=false (reason: relaunch-2 role 03:16Z shutdown), block devices /dev/sda1=vol-0d36715924f03b86c,
  /dev/sdf=vol-004b68c077be09cc9. DescribeVolumesModifications: BOTH volumes still ModificationState=optimizing from the
  12:07:59Z/12:08:00Z baseline change (root 16,000/1,250 -> 3,000/125 progress 21%; archive 10,000/1,000 -> 3,000/125
  progress 93%). DescribeVolumes: both gp3 2048 GiB in-use at 3,000 IOPS / 125 MiB/s.
- 14:27:36Z STEP 1b ModifyVolume, ONE attempt each: vol-0d36715924f03b86c -> 16,000/1,250 REFUSED (IncorrectModificationState:
  "cannot be modified in modification state OPTIMIZING"); vol-004b68c077be09cc9 -> 10,000/1,000 REFUSED (same). Continuing at
  BASELINE 3,000 IOPS / 125 MiB/s (the resume reads only heads + 64 KiB tails; the parent raises them after the cooldown ~18:1xZ).
- 14:27:38Z STEP 2 StartInstances i-035994afa8bdf66a5: stopped -> pending. 14:27:39Z CreateTags KeepRunning=true
  (+KeepRunningReason "box-operator role session 8 ... Greg: Go; box started to resume a2 ... on the staged tip 85ce2827");
  DescribeTags read back KeepRunning=true.
- 14:28:02Z box RUNNING (LaunchTime 14:27:38Z), SSM PingStatus Online (last ping 14:27:58Z), public DNS
  ec2-54-227-194-12.compute-1.amazonaws.com. KeepRunning=true.
- 14:28:39Z STEP 4 STAGE dispatched (github actions_run_trigger, frankie_box_run.yml, ref ccr-d2f8f826-iefeah-frankie,
  script=deploy/aws/box/frankie_box_stage_code.sh, variables=ACTION=stage, instance=i-035994afa8bdf66a5, region=us-east-1):
  run 37792772826 (run_number 844). SURPRISE: the run's head_sha is d67b9c63 ("Box record session 8: main box start + a2
  resume (in-progress snapshot) [skip ci]"), i.e. the parent pushed this record file on top of 85ce2827 between my fetch
  (14:26Z) and the dispatch; the ref resolved to that newer tip. Checked below whether d67b9c63 is code-identical to 85ce2827.
- 14:29:16Z STEP 2/3 PROBE + SAVED-STATE readings (SSM command 2e861e37-3622-464e-acb6-13387e83144b, read-only, rc Success):
  up 1 min, load 0.02; nproc 64, Xeon 8488C, 2 threads/core, 32 cores; sibling map cpu0=0,32 cpu1=1,33 cpu31=31,63 (N/N+32
  as the CPU plan predicted: the retained 0-31 are 32 distinct physical cores). df: / avail 791,797,620,736 B; archive
  /opt/frankie-box/archive (nvme1n1) avail 1,714,966,781,952 B; both mounted. Checkouts present incl. 6076950, e0d7ae0,
  b474c51, c9bf631 (unchanged from session 7).
  R=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1: calculations-receipt.json ABSENT; handoff/ ABSENT;
  work/file-claims.jsonl 41,542 B 03:02Z; work/legacy-stage.json 59,810 B 01:17Z; derive.json ABSENT (NOTE: the session-7
  drop-in said "derive.json still the 01:33:06Z one"; it is not there now); R/progress.json deriving/running pid 88265 (dead;
  probe says process_alive false, age 41,226 s).
  Q=/opt/frankie-box/work/frankie-queue: save marker save/e2e-20231018-a2-20231018.save-request.json STANDING, 497 B, 03:09:51Z,
  sha256 5738b2458a0978ec94f4f5227333268800700641996dee8fd858d61ad94b39f0, FRANKIE_QUEUE_SAVE_REQUEST_V1, attempt a1, booking
  day-run-20231018-day_slot_root-1791402822-3111, cpus 0-31, by "dispatch save" (+5 .resumed-* archives). root.json seq 2:
  state SAVED, where box-slot, reason "saved on its day-bound marker ...", retained_booking ...-3111, save_request = the marker
  identity (sha 5738b245...), retain_error null, finish null. class.json ABSENT (no class entry yet).
  Booking ledger: ONE booking day-run-20231018-day_slot_root-1791402822-3111, kind day-run, cpus 0-31, size 32, pids [] (holder
  None), retained at 03:14:11Z by pid 88228 (reason "the day is saved on its owner; its CPUs stay its own until ACTION=resume").
  cores show (6076950): CPUs 0-31 booked by ...-3111, live idle; 32-63 free idle. frankie units: 0. frankie procs: 0; procs
  with files under R: 0. Stage heartbeat (RUN_DIR probe): root 20231018 final: exited (exit_code 137, elapsed 731.6 s,
  cpus 0-31); root line worker waiting (root:waiting_owner, kick 03:01:55Z, run_settings CLEAN_ON_SAVE=off ROOT_DIGEST=off);
  class line worker absent. Matches the session-7 "Run state" exactly except derive.json (absent).
- 14:31Z tip check: origin now c75054d1 (record snapshot) > d67b9c63 (record) > eb1bafe3 (fleet source (a): NEW files
  deploy/aws/box/frankie_box_fleet.py + tests/test_frankie_box_fleet.py, additive) > 85ce2827. `git diff --stat 85ce2827
  d67b9c63` = the two new fleet files + this record only; NO existing script or module changed, so the staged d67b9c63 runs
  exactly 85ce2827's box code. Not a "WIP snapshot" commit. ACCEPTED as the staged tip (>= 85ce2827).
  ROUTE DECISION for resume/kick: frankie_box_run.yml sets MARKETS_SHA=$GITHUB_SHA = the ref tip AT DISPATCH, and
  frankie_box_frankie_queue.sh refuses when `git rev-parse HEAD` of CODE_ROOT differs from MARKETS_SHA; the parent is pushing
  record snapshots to the branch every few minutes, so a workflow dispatch would bind to a tip newer than the staged checkout
  and be refused (the "push after staging" trap, runbook section 8). The resume and kick therefore go over SSM through the Aws
  connector with CODE_ROOT and MARKETS_SHA=d67b9c63 given explicitly (the session-6 live precedent, BOX_RECORD_20261008_S6_RELAUNCH
  sections C1/C2; scripts sent as `bash -s <<'EOF'`), on the same frankie_box_frankie_queue.sh the workflow would run.
- 14:33Z CORRECTION to the 14:29Z reading: derive.json lives at R/work/derive.json (`session.work`, E2E record line 1172
  "resumed from work/derive.json"); the probe listed R/derive.json, the wrong path. Re-read at the next SSM probe.
- 14:31:27Z read-only SSM 7787506f-025e-49ea-a032-2ddda7a35e7d: R/work/derive.json PRESENT, 80,813 B, 01:33:06Z, sha256
  948074df0394e33adbc82035a236949f6f78ee80523aa5b70e2ec5f1179e8eec, root_processes {bedrock_projection run, bedrock_traversal
  run, digest run, legacy run}, failure_count 0, 50 layers, bedrock not skipped (the 14:29Z "absent" was the wrong path; the
  tip's resume takes the claims route `if resume and work/derive.json.is_file()`, experiment_root.py 416-418, so the resume
  WOULD have been lawful). R/work also holds file-claims.jsonl (03:02Z), legacy-stage.json, native-layer-records.json, native-
  stage.json, derived/, bedrock/. STAGED CHECKOUT LANDED: /opt/frankie-box/code/d67b9c63ba18c35e9f7cad49802735f1d455fb35-37792772826-1/markets,
  `git rev-parse HEAD` = d67b9c63ba18c35e9f7cad49802735f1d455fb35 (the stage python process 1751 still finishing sync/receipt).

## HALT (Greg, 14:3xZ via the parent, verbatim: "Keep box off until absolutely ready")
- Received 14:3xZ BEFORE any ACTION=resume or ACTION=kick was sent. NOTHING ran on R; no ROOT child, no worker, no unit was
  started by this role. Steps 5-6 NOT performed. The staged checkout stays in place (reusable: stage it again only if the tip
  moves). Actions now: KeepRunning=false (reason "Greg 14:3xZ keep box off until ready"), wait for the stage run to finish its
  receipt so the checkout is complete, then StopInstances and wait for stopped.
- 14:31:42Z stage run 37792772826 COMPLETED success (stage-code / inactive-code job; the staged checkout above).
- 14:31:50Z CreateTags KeepRunning=false (+reason "Greg 14:3xZ keep box off until ready ..."); read back false.
- 14:32:19Z pre-stop read (SSM 60562be5-c010-4e66-8f72-9974ee5991aa): staging-receipt.json PRESENT in
  /opt/frankie-box/code/d67b9c63ba18c35e9f7cad49802735f1d455fb35-37792772826-1/ (FRANKIE_INACTIVE_CODE_STAGING_RECEIPT_V1,
  status staged, commit d67b9c63, files 4120, pack_sha256 aa898f730b370b40f9a9641a44a264764493522447de925c0eaccd705fa1ff27,
  active_checkout_changed false, model_calls 0, source_replays 0); HEAD d67b9c63. frankie units 0, frankie procs 0.
  a2 entry seq 2 state SAVED, retained_booking day-run-20231018-day_slot_root-1791402822-3111; save marker standing (497 B,
  03:09Z); calculations-receipt.json ABSENT. `sync` run.
- 14:32:25Z StopInstances i-035994afa8bdf66a5: running -> stopping. 14:33:13Z state STOPPED (r7i.16xlarge, KeepRunning=false).

## End state (14:33Z)
- Box i-035994afa8bdf66a5 STOPPED, r7i.16xlarge, KeepRunning=false, both volumes attached at baseline 3,000/125 (modifications
  still optimizing; raise refused until they finish and the 6 h cooldown clears ~18:1xZ).
- Day e2e-20231018-a2/20231018 UNCHANGED: SAVED on its marker (sha 5738b245...), booking 0-31 retained, owner commit 6076950,
  NO receipt, no teacher; derive.json intact at R/work/derive.json. Nothing ran on R this session.
- Staged and receipted for the next go: /opt/frankie-box/code/d67b9c63ba18c35e9f7cad49802735f1d455fb35-37792772826-1/markets
  (= 85ce2827's box code + the additive fleet module). Next session: StartInstances, SSM Online, KeepRunning=true, then
  ACTION=resume RUN=e2e-20231018-a2 DAY=20231018 and ACTION=kick LINE=root SCOPE=e2e-20231018-a2:20231018
  FRANKIE_ROOT_DIGEST=off FRANKIE_CLASSROOM_CPUS=all with CODE_ROOT=<that checkout> MARKETS_SHA=d67b9c63... (SSM route with the
  explicit sha, or restage if the branch tip must be the one dispatched), unless the tip has moved in CODE (then restage).
- Not touched: i-0d17573dbce871520, i-08cee7171c0a76a04, the clone volumes, snapshots, IAM, quotas, launch templates.

## 15:0xZ restart on Greg's go (BOX-OPERATOR role, second pass)
Greg's go via the parent (15:0xZ, verbatim): "If there's a better faster way, do that" after "I just didn't want it sitting idle
while we made a bunch of changes"; the parent decided: START the main box now and resume a2 so the teacher (the long pole) runs
while the fleet work finishes. Limits unchanged (only i-035994afa8bdf66a5; no second box, clone volumes, snapshots, IAM, quotas,
launch templates, fleet; no digest render, no hand classroom, no stop, no ModifyVolume: cooldown until ~18:20Z, the parent does it).
Route: the staged checkout CODE_ROOT=/opt/frankie-box/code/d67b9c63ba18c35e9f7cad49802735f1d455fb35-37792772826-1/markets with
MARKETS_SHA=d67b9c63ba18c35e9f7cad49802735f1d455fb35 explicit over SSM (Aws connector, SendCommand AWS-RunShellScript, scripts as
`bash -s <<'EOF'`), NOT a workflow dispatch (the ref tip has moved on: 1e07412f locally at 15:00Z; a dispatch would bind
MARKETS_SHA to that tip and the queue would refuse the d67b9c63 checkout). No restage: d67b9c63 carries the CPU plan + the resume
fixes; the later commits are fleet/docs, inert for a2.
Class-line kick decision (source, d67b9c63 frankie_box_frankie_queue.py): `class_worker` on an EMPTY class line ends idle at once
(front None -> state idle, lock released, exit 0), and the ROOT chain kicks the class line itself after the teacher
(`_after_root` -> `kick('class', ...)`), whose `_run_settings_env()` reads the ROOT worker's own environment = the root kick's
FRANKIE_* settings carried by systemd-run -E (S6 C2 precedent: the unit's Environment held FRANKIE_ROOT_DIGEST/CLEAN_ON_SAVE).
Decision 1 also made `all` the classroom default when unset. So NO manual class kick now: it would end idle immediately and carry
nothing; the chain's own class kick inherits FRANKIE_CLASSROOM_CPUS=all from the root kick below.

### Timeline (second pass)
- 15:01:45Z STEP 1 read-only DescribeInstances: i-035994afa8bdf66a5 STOPPED, r7i.16xlarge, us-east-1d, KeepRunning=false
  (reason: the 14:3xZ HALT), /dev/sda1=vol-0d36715924f03b86c, /dev/sdf=vol-004b68c077be09cc9 (unchanged from 14:33Z).
- 15:02:1xZ STEP 1 StartInstances i-035994afa8bdf66a5: stopped -> pending (first CreateTags refused: my KeepRunningReason exceeded
  the 256-char tag limit; nothing else affected). 15:02:35Z CreateTags KeepRunning=true + KeepRunningReason "box-operator s8
  15:0xZ: Greg go via parent ('if there is a better faster way, do that'); box started to resume a2 day 20231018 (resume+kick)
  on staged d67b9c63 so the teacher runs while fleet work finishes"; read back true. 15:02:36Z state RUNNING (LaunchTime
  15:02:19Z, public DNS ec2-54-227-168-200.compute-1.amazonaws.com); 15:02:42Z SSM PingStatus Online (last ping 15:02:38Z).
- 15:03:11Z STEP 2 PROBE (read-only, SSM 484b60ca-21da-40f7-b6eb-cce25a595e2a, rc 0): up 0 min, load 0.19, nproc 64. Staged
  checkout d67b9c63...-37792772826-1/markets present (14:31Z), `git rev-parse HEAD` = d67b9c63ba18c35e9f7cad49802735f1d455fb35,
  staging-receipt status staged, commit d67b9c63, files 4120. R: calculations-receipt.json ABSENT, handoff/ ABSENT,
  work/derive.json 80,813 B 01:33Z sha256 948074df... (unchanged). Q root.json: seq 2 run e2e-20231018-a2 day 20231018 state
  SAVED, retained_booking day-run-20231018-day_slot_root-1791402822-3111, save_request true, owner commit 6076950. class.json
  ABSENT. save/: the standing marker e2e-20231018-a2-20231018.save-request.json 497 B 03:09Z + 5 .resumed-* archives (+ a1's).
  cores show (d67b9c63 ledger): core map 32 cores x 2 threads, siblings N,N+32; CPUs 0-8 shown booked by ...-3111 live idle
  (output cut at 12 lines; the 14:29Z full read had 0-31 booked, 32-63 free). frankie units 0, frankie procs 0, no
  /opt/frankie-box/work/cpu-watch yet. Matches the 14:33Z end state. GO for the resume.
- 15:03:41Z STEP 3a RESUME (state-changing; SSM 266466c3-3cf4-43e3-a84a-e5e5a9133be7, rc 0). Script sent (bash -s <<'EOF'):
  `export CODE_ROOT=/opt/frankie-box/code/d67b9c63ba18c35e9f7cad49802735f1d455fb35-37792772826-1/markets;
  export MARKETS_SHA=d67b9c63ba18c35e9f7cad49802735f1d455fb35; ACTION=resume RUN=e2e-20231018-a2 DAY=20231018 bash
  $CODE_ROOT/deploy/aws/box/frankie_box_frankie_queue.sh` (the script also carried one mistyped MARKETS_SHA export line
  immediately overridden by the correct one; HEAD d67b9c63 verified in the same script and the queue's HEAD==MARKETS_SHA check
  passed). Output: resumed phase root, run e2e-20231018-a2 day 20231018; marker ARCHIVED to
  save/e2e-20231018-a2-20231018.save-request.json.resumed-1791471821 (6 .resumed-* now, no standing marker); owner attempt
  e2e-20231018-a2-20231018-a1, booking day-run-20231018-day_slot_root-1791402822-3111 (bound 2026-10-07T19:53:42Z by pid 3111),
  cpus 0-31, held_bookings x5 (19:53:42, 21:47:27, 22:43:49, 02:24:06, 03:01:56), holder_pid 88228 (03:01:56Z), owner commit
  6076950 (code_root the 6076950 checkout) until the next admission; source_history 98579cea -> 275367fe -> c9bf631 -> e0d7ae0.
  Note: "the next ROOT-line admission books exactly the retained CPUs and resumes attempt ...-a1; kick the root worker with this
  run/day in scope". After: entry seq 2 state QUEUED ("resumed by dispatch resume: back in line at its own place with its owner
  binding"), save_request false, retained_booking ...-3111.
- 15:04:29Z STEP 3b KICK (state-changing; SSM 4f3b5707-182c-486c-8d22-1b2b8438345d, rc 0; a first SendCommand of the SAME script
  was refused by the SSM API on its 100-char Comment limit and never reached the box). Script sent (bash -s <<'EOF'): the two
  exports above, then `FRANKIE_ROOT_DIGEST=off FRANKIE_CLASSROOM_CPUS=all ACTION=kick LINE=root SCOPE=e2e-20231018-a2:20231018
  bash $CODE_ROOT/deploy/aws/box/frankie_box_frankie_queue.sh` (DAY_CPUS not given; FRANKIE_CLEAN_ON_SAVE at its default).
  Output: "cpu watch loop: exit 0 ... correct=on resize=on; Running as unit: frankie-cpu-watch.service (invocation
  241fc82fadae4f688e71165f01fd12c4); frankie-cpu-watch started (every 120 s for 43200 s)"; "root worker started for
  e2e-20231018-a2:20231018 (systemd-run, unit frankie-queue-root-1791471869, exit_code 0); worker lock held". Kick json
  (Q/root-kick.json 986 B): started true, how {systemd-run, unit frankie-queue-root-1791471869}, run_settings
  {FRANKIE_CLASSROOM_CPUS: all, FRANKIE_ROOT_DIGEST: off}, scope e2e-20231018-a2:20231018, by dispatch, at 1791471869.47,
  cpu_watch {started true, exit_code 0, script <d67b9c63>/deploy/aws/box/frankie_box_cpu_watch.sh}.
  At 15:04:38Z: unit frankie-queue-root-1791471869 active/running MainPID 1758, Environment CODE_ROOT=<d67b9c63 checkout>
  FRANKIE_CLASSROOM_CPUS=all FRANKIE_ROOT_DIGEST=off MARKETS_SHA=d67b9c63...; unit frankie-cpu-watch.service active/running
  (python -I -S -B frankie_box_cpu_watch.py --loop --interval 120 --max-seconds 43200 --work-dir /opt/frankie-box/work/cpu-watch
  --window 1, pid 1765). Procs: 1758 root worker; 1765 watchdog; 1832 cores run --kind day-run --day 20231018 --run
  e2e-20231018-a2; 1834 experiment_root --commit d67b9c63 (the ROOT child). /opt/frankie-box/work/cpu-watch/: first record
  20261008T150429Z.json (3,662 B) + loop.log + watch.log. Entry seq 2 state RUNNING where box-slot, retained_booking
  ...-3111, owner commit d67b9c63 (rebound at admission). Class line NOT kicked by hand (see the decision above).
- 15:05:11Z WATCH 1 (read-only, SSM 473a6689-e0d3-4938-96b9-7b20f7d95fad): ROOT child 1834 Dl elapsed 0:36, 24.5% CPU, RSS
  276,832 KB, psr 31, affinity 0-31 (inside the retained booking); read_bytes 4,537,004,032, write 0; fd 3 = /opt/frankie-box/
  work/ingest-20231018-gh-36571235912-1/journal.compact.sqlite pos 4,311,744,512 (the sealed-day read); fds 1,2 = /opt/frankie-box/
  work/experiment/e2e-20231018-a2/logs/20231018-root.log (pos 8,164). receipt ABSENT; progress.json still the 03:02Z one (pid
  88265); derive.json 01:33Z; file-claims.jsonl 57 rows (03:02Z). Watchdog record 20261008T150429Z.json: FRANKIE_CPU_WATCH_V1,
  settings correct=on resize=on, bookings 1, findings 3 all kind "unbooked" (kick-time Frankie processes at affinity 0-63, e.g.
  pid 1751; "listed only"), repins 0, resize 0 (watch.log line "bookings 1 findings 3 (unbooked 3) repins 0 resize 0").
  root-worker.log tail still the 03:14:56Z waiting_owner block (the new worker's lines come later). load 0.51.
- 15:06:29Z WATCH 2 (read-only, SSM c95604d1-8438-4278-9a6c-e586d08d2048): ROOT log (/opt/frankie-box/work/experiment/
  e2e-20231018-a2/logs/20231018-root.log, 94 lines): "### root 20231018 frankie_box_experiment_root.sh at 2026-10-08T15:04:35Z";
  "15:05:48Z experiment ROOT: sealed day, legacy and native calculations; no giant bedrock digest" (digest off honoured).
  1834 Dl elapsed 1:54, 17.2% CPU, RSS 442,628 KB, 32 threads, 0 children; read_bytes 14,452,219,904, write 24,576; fd 3 =
  R/work/bedrock/recovery-6f84a8a86f454010b61346b401e3eb5f/ledgers/exact_lifecycle_rows.jsonl pos 5,167,382,528 (the evidence
  pass over the native ledgers). receipt ABSENT; file-claims.jsonl still 03:02Z (41,542 B); derive.json 01:33Z. R/work holds
  bedrock, boss-jobs, derived, input-state.pkl, legacy-cpu-split.json (+2 retained), legacy-stage.json, legacy-state.pkl,
  native-layer-records.json, native-overlap.json (+6 retained), native-stage.json, native-stage.lock. load 0.91.
- 15:07:51Z WATCH 3 (read-only, SSM 7c82d222-21b2-4717-b2f5-c0d7877c6da4): 1834 Dl elapsed 3:16, 14.3% CPU, 32 threads, psr 0;
  read_bytes 25,305,116,672 (+10.85 GB in 82 s = ~132 MB/s = the volume's BASELINE 125 MiB/s); fd 3 = R/work/bedrock/
  recovery-6f84.../ledgers/exact_member_rows.jsonl pos 8,472,494,080 of 193,743,650,444 (a WHOLE READ; exact_lifecycle_rows.jsonl
  was read whole before it). ROOT log 94 lines: header 15:04:35Z, "CPU_BOOKING inside the day's held slot ...-3111: CPUs 0-31",
  "inside the held day slot ... (stage root)", 15:05:48Z sealed day line; nothing after. progress.json rewritten 15:05:48Z
  (363 B). receipt ABSENT; file-claims.jsonl UNCHANGED (03:02:14Z; the tip did not rewrite it). FLAG: the native ledgers are
  not taken by their claims; at 132 MB/s the 193.7 GB ledger alone is ~24 min, and the receipt is NOT "within minutes" if the
  472 GB layer or the 496.7 GB frames spool are read whole too (the volumes sit at baseline until the parent's ~18:20Z raise).
  Watchdog pass 2 at 15:06:29Z: "bookings 1 findings 68 (outside_booking 67, unbooked 1) repins 67 resize 0" -> the watchdog
  RE-PINNED 67 threads (correct=on); record 20261008T150629Z.json read next. Not intervening.
