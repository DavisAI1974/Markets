# Drop-in: Frankie, 2026-10-08, session 9 (handoff from session 8; a2 RESUMING on the claim fix; fleet source built, review items open)

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie (Greg). THE AGENTS ARE THE ONLY WAY WORK RUNS. Greg's rules this session: do what is best for
SCIENCE and SPEED; STOP building more tests and validators - if something does not work in the run, fix it then.
1. git fetch origin ccr-d2f8f826-iefeah-frankie && git checkout -B ccr-d2f8f826-iefeah-frankie origin/ccr-d2f8f826-iefeah-frankie
   Confirm the tip is the commit named at the bottom of this file, or newer. SHALLOW clone: `git fetch --deepen=400` first.
2. Read THIS file, then DROP_IN_CLAUDE_20261008_SESSION8.md (every decision and state block of session 8, newest at the top
   of its body), then BOX_RECORD_20261008_S8_START.md (the live box timeline), FLEET_SOURCE_STATUS_SESSION8.md and the two
   REVIEW_20261008_FLEET_SOURCE*.md files. The session-8 drop-in's "Run state (UNCHANGED since the session-7 drop-in)" block
   and everything below it is HISTORY; the box state now is in THIS file.
3. Session = parent only; spawn agents with model "fable"; api-and-interface-design first; AWS via the Aws connector (test
   with one read-only STS call; the IAM user Claude's key pair is NOT in a new container: Greg pastes it if the connector is
   down). Greg is in and out: background agents die with a container resume, so (a) every role writes its record file
   incrementally, (b) long source work runs in a CLOUD SESSION (create_session, pushes to the branch), (c) a self check-in
   (send_later) re-reads the records and continues from them.
4. SESSION 8's TIMERS ARE STILL ARMED IN SESSION 8 (they wake that session even when Greg is elsewhere): the a2 check-in
   every 30 min (next 16:36Z) and the 18:20Z step (ModifyVolume raise of the two main-box volumes, then the full-depth
   digest render on the sibling lane beside the teacher). Do NOT duplicate them unless session 8 is confirmed dead; if you
   take them over, delete session 8's triggers first (list_triggers: "a2 restart check-in (3)", "Volume raise + digest
   render (a2)") so two sessions never drive the box at once.
5. No fleet launch without Greg's explicit "launch the first box". No second-box or clone-volume action. Nothing is dropped
   from any run; FULL DEPTH digests.
```

## The box NOW (16:1xZ 2026-10-08)
- Main box i-035994afa8bdf66a5, us-east-1d, RESIZED to r7i.16xlarge (64 vCPU) this session, RUNNING, SSM Online,
  KeepRunning=true. Volumes vol-0d36715924f03b86c (root) and vol-004b68c077be09cc9 (archive) at BASELINE 3,000 IOPS /
  125 MiB/s since 12:08Z (idle-cost cut); the 18:20Z timer raises them to 16,000/1,250 and 10,000/1,000 (6 h cooldown).
- Day e2e-20231018-a2/20231018 (R=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1): resumed 15:04Z on the
  staged checkout d67b9c63 over SSM (the workflow route is refused when the branch moves: MARKETS_SHA binds at dispatch),
  ROOT child on the retained booking 0-31 hashing artifacts WHOLE at the baseline rate because every FRANKIE_FILE_CLAIM_V1
  row stored st_dev and the reboot renumbered the NVMe devices. FIX on the tip (5bf723f4 code + 38cfb10b toys): V2 claims
  (ino+size+mtime_ns+tail+fs UUID), V1 rows accepted on a tail match and rewritten. The save marker was written 15:27Z and
  stands; the child reaches its save point after the 472 GB inline layer (~16:37Z); the claim-fix tip is STAGED on the box
  (run 37800918122, checkout /opt/frankie-box/code/46cfe907...-37800918122-1/markets = 5bf723f4's box code). A box-operator
  in session 8 then does ACTION=resume + ACTION=kick over SSM (CODE_ROOT/MARKETS_SHA explicit; FRANKIE_ROOT_DIGEST=off
  FRANKIE_CLASSROOM_CPUS=all; DAY_CPUS not given) and the receipt lands in minutes. Then the chain self-drives: validate ->
  teacher (0-31) -> classroom on ALL 64 (grows; waits while the render holds 32-63) -> data/search -> scientific teacher ->
  meeting -> Jev -> end. The CPU watchdog (re-pin + resize on, wall-clock rule) runs with every kick.
- Second box i-0d17573dbce871520 (r7i.16xlarge) STOPPED; year-pull box i-08cee7171c0a76a04 (us-east-2) STOPPED. Clone volumes
  vol-0c53052c4a6b38bfe (root) / vol-0025eb0f8dc9d97b9 (archive) exist UNATTACHED (the durable copy of a2 + a spare); the two
  snapshots behind them are kept.

## Built this session (all SOURCE-BUILT / RUNTIME-UNVERIFIED unless the box record says it ran)
- CPU plan for 64 vCPU: one resolver (frankie_box_cores.lane_for), live sibling map, whole-cores-first slots, grow at the
  classroom, Jev threads = lane, watchdog frankie_box_cpu_watch (re-pin + lawful save/resume resize, wall-clock only).
- Fleet source (cloud session session_017Gvs4EeRCAaoZmnqZXBf7Y, pushes to the branch): S3 day list + per-day claims +
  ONE classroom lease + waiting queue (frankie_box_fleet.py), handoff gate, launch-template / fleet-launch / golden-ami /
  day-box-role steps in frankie_aws_stack.py, .github/workflows/frankie_fleet.yml (plan/launch/status/stop-all) +
  frankie_fleet_status.py, the reboot-resume driver frankie_fleet_day.sh, the queue's release-on-fleet-gate-save + rebook.
  Review pass 1 (7 blocking) FIXED; pass 2 found NEW-1 (free-lease deadlock) and NEW-2 (KeepRunning cleared on waiting
  boxes): the cloud session was told to fix ONLY those two, minimally, no new tests, then stop; NEW-3..10 deferred "fix when
  it bites". Verdict: one proof box with ONE day and the day list ON is sound once NEW-1/NEW-2 land.
- Account: quota L-1216C47A still 256 (640 DENIED; Greg's 512 appeal posted on case 179140016900825 12:39Z; poll, never
  file); Spot quota 256 separate (8 boxes today: 4 OD + 4 Spot for ROOT); Compute Optimizer + Cost Optimization Hub active;
  budget $3,000/mo; cost anomaly $20 -> SNS frankie-alarms (no email subscriber yet); CW agent association on
  Project=frankie; system-recover alarm (notify-only; add the recover action once running); archive bucket
  frankie-archive-568968024170-us-east-1 + Glacier lifecycle (also on bento); IAM role + instance profile frankie-day-box
  with policy FrankieDayBox-20261008 (13 statements, verified); Project=frankie tags + resource groups in both regions;
  idle storage cut (old AMI, 4 snapshots, unattached volume removed; two before-termination snapshots kept).
- DEFERRED by design: cost-allocation tag activation (billing must see the tag first); disk/mem alarms (need the agent's
  live dimensions after first boot); the recover action on the alarm; the role tag typo "Project = frankie".

## Next, in order
1. Confirm a2's receipt and the claim decisions (v1-compat rows rewritten V2) from the box record; then watch the chain:
   validate, teacher, the 18:20Z render on 32-63, the classroom on 64.
2. If anything in the run breaks: fix THAT (Greg), restage, resume at the save boundary. No new validators.
3. Fleet: when NEW-1/NEW-2 are pushed, ONE proof box with ONE fresh day, day list ON, only on Greg's "launch the first
   box" (frankie_fleet.yml ACTION=plan first, then launch with confirm GREG_GO_AWS_STACK; golden-ami from a CLEAN staged
   box, never the main box).
4. Session-9 drop-in to update as state moves; CLAUDE.md pointer already set.

## Tip at handoff
- The commit carrying this file (parent fa733f39/cb156bca record snapshots; 5bf723f4 claim fix; 36c082ec queue half;
  b79a7a27 fleet status). Stage the tip or newer; never a WIP snapshot.
