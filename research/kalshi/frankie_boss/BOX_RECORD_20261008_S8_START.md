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
