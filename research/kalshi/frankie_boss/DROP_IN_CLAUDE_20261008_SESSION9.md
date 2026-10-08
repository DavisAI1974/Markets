# Drop-in: Frankie, 2026-10-08, session 9 (handoff from session 8; a2 RESUMING on the claim fix; fleet source built, review items open)

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie (Greg). THE AGENTS ARE THE ONLY WAY WORK RUNS. Greg's rules: best for SCIENCE and SPEED; STOP
building more tests and validators - if something does not work in the run, fix it then.
GREG'S DIRECTIVE FOR THIS SESSION (16:2xZ 2026-10-08, verbatim): "Definitely do the cpu add now, retain all info to this
point. Fix problem and restart from exactly the same spot." Then: "Will fix in new session."
1. git fetch origin ccr-d2f8f826-iefeah-frankie && git checkout -B ccr-d2f8f826-iefeah-frankie origin/ccr-d2f8f826-iefeah-frankie
   Confirm the tip is the commit named at the bottom of this file, or newer. SHALLOW clone: `git fetch --deepen=400` first.
2. Read THIS file, then DROP_IN_CLAUDE_20261008_SESSION8.md (newest blocks at the top of its body), then
   BOX_RECORD_20261008_S8_START.md (the live box timeline, newest section last), FLEET_SOURCE_STATUS_SESSION8.md and the two
   REVIEW_20261008_FLEET_SOURCE*.md files.
3. Session = parent only; agents model "fable"; api-and-interface-design first; AWS via the Aws connector (one read-only
   STS call first). Every role writes its record incrementally; long source work in a CLOUD SESSION; a self check-in
   (send_later) re-reads the records and continues from them.
4. SESSION 8 IS PASSIVE ON THE RUN: its box-operator stops at SAVED (no resume, no kick); its a2 check-in is DELETED; the one
   timer left in session 8 is the 18:20Z ModifyVolume raise of the two main-box volumes (harmless to the run; it appends a
   note to this file). THIS session owns the restart. FIRST ACTION, the directive applied in order, on the box:
   (a) confirm a2 reads SAVED (box record; one read-only probe), the claim-fix checkout
       /opt/frankie-box/code/46cfe907...-37800918122-1/markets (= 5bf723f4's box code) staged with its receipt, booking
       day-run-20231018-day_slot_root-1791402822-3111 retained on 0-31, receipt ABSENT;
   (b) THE CPU ADD: grow that booking from 0-31 to ALL 64 (frankie_box_cores `grow --booking <id> --size 64 --reason
       "Greg 16:2xZ CPU add"`; same booking id; it must not WAIT since nothing holds 32-63; if it refuses, STOP and report);
       verify `cores show` reads 0-63;
   (c) RESTART FROM EXACTLY THE SAME SPOT, RETAINING EVERYTHING: ACTION=resume RUN=e2e-20231018-a2 DAY=20231018 over SSM
       on that checkout (CODE_ROOT + MARKETS_SHA explicit; the workflow route is refused when the branch moves), then
       ACTION=kick LINE=root SCOPE=e2e-20231018-a2:20231018 with FRANKIE_ROOT_DIGEST=on (the ROOT renders its own FULL-DEPTH
       digest on the 64 lane right after the receipt; no separate sibling-lane render) and FRANKIE_CLASSROOM_CPUS=all;
       DAY_CPUS not given (the plan reads the HELD booking = 64). The resume accepts a2's 57 V1 claims on their tails and
       rewrites them V2: nothing recomputed; the receipt in minutes; record the claim decisions from the receipt.
   (d) then watch: receipt -> digest (disk-bound at the baseline 132 MB/s until 18:20Z) -> validate -> teacher -> classroom
       -> data/search -> scientific teacher -> meeting -> Jev -> end, all on 0-63. Fix what breaks, restage, resume at the
       save boundary. No new validators.
5. No fleet launch without Greg's explicit "launch the first box" (fleet pass-2 NEW-1/NEW-2 being fixed minimally in the
   cloud session; the rest deferred "fix when it bites"). No second-box or clone-volume action. Nothing is dropped from
   any run; FULL DEPTH digests.
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
0. The directive in the box above (CPU add, restart from the same spot) is the first action.
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
