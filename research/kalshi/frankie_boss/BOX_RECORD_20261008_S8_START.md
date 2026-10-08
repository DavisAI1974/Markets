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
