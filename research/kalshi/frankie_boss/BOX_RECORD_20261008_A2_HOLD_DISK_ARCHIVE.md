# Hold a2 before the teacher stage (box-operator role), 2026-10-07 session 5

Run e2e-20231018-a2, attempt e2e-20231018-a2-20231018-a1, box i-035994afa8bdf66a5 (us-east-1).
R=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1. ROOT 14860, native 14929, worker 14824, code c9bf631.
Greg's go (relayed by the parent): pause ROOT when it is done so it does not progress to the teacher stage, whose code is still landing.
All box times UTC. Read-only SSM unless stated. Branch ccr-d2f8f826-iefeah-frankie (tip ae219a8 WIP snapshot); no repo edit, no commit.

## Code analysis (work branch, file:line)

The ROOT-line worker runs a day's whole day in one thread of one slot: `_root_job` (frankie_box_frankie_queue.py:1647-1673)
calls `run.root(e)` and then, when the ROOT is done/reused, `_finish_day` -> `_finish_steps` (1335-1346), whose first act
after `run.successors` is `run.check_save()` (1346), BEFORE the BOSS teacher (`run.day_rows` 1349, `run.teacher` 1355/1385).
`Run.check_save` (frankie_box_experiment.py:1135-1138) raises SystemExit(75) when `Run.save_requested()` (1118-1120) sees
the owner's marker file standing: `self.stop_marker` = the queue owner's marker (bind_owner 1112-1116) =
save/<run>-<day>.save-request.json (marker_of, queue 1176-1177). So the save marker IS honoured at the ROOT -> teacher
boundary (mechanism A exists).

But the SAME marker reaches the ROOT child as FRANKIE_LANE_STOP_FILE (Run.child, experiment.py:1299-1301) and
frankie_box_experiment_root.calculate_day (experiment_root.py:123-127) turns it into `save_requested()`, honoured mid-run by
the session: legacy loop boss_session.py:2605 (save after the record, TeacherSaved), `_await_native_overlap` 2198-2202
(SIGTERM to the native child, which saves a checkpoint; TeacherSaved), `_derive_bedrock` 3026-3028 (after the native stage
is joined/reused, BEFORE the projection: TeacherSaved 'native calculation completion retained; projection remains to be
resumed'), and finally calculate_day 131-133: after `_calculate_day` RETURNS (receipt published), `if save_requested():
raise TeacherSaved('ROOT completion published; resume uses the completed receipt')`. No save check exists inside
`_native_projection` (3087), `write_retained_digest` (monday_calculations) or the receipt writing (experiment_root.py
355-375): a marker placed after the 3026 check is first seen at 131, AFTER the whole ROOT (projection, digest, layers,
calculations-receipt.json) is complete.

TeacherSaved is a SystemExit (parallel_teacher.py:757) -> the ROOT child exits 75; Run.child maps a child exit 75 under a
standing marker to SystemExit(75) in the worker thread (experiment.py ~1340-1360, see below); `_root_job` catches it via
`_thread_end` -> `_save_result` (queue 1570-1591): holder['root'] is None (run.root raised), so the entry becomes state
'saved' (OWNER_STATES) with its attempt and marker; `_end_slot` (1628-1644) RETAINS the booking (C.retain) instead of
releasing. The worker loop (1898-1912) records the entry saved with retained_booking. Nothing else runs: no teacher.

Resume path: ACTION=resume (resume_owner 2236-2290) archives the marker, puts the entry back to queued with the SAME owner
(attempt, CPUs, booking); then ACTION=kick on the restaged code; the new worker's `Run.root` (experiment.py:1483-1560)
finds the completed ROOT via `root_of` (calculations-receipt.json present) -> 'reused' (policy-checked), brain_stage, then
`_finish_day` -> teacher. Exactly "ROOT completion published; resume uses the completed receipt".

Decision: mechanism (A)+(B): the queue's own ACTION=save (request_save 2136-2165, create-only marker, never kills), placed
in the window AFTER boss_session.py:3026 has evaluated False (native stage joined and reused: log note 'bedrock: completed
native results reused in place; no traversal or finalization replay', 3077; then the projection runs) and BEFORE the ROOT
child exits. ROOT then completes everything and exits 75 at experiment_root.py:131; the worker ends the day 'saved', booking
retained, teacher never started. Placing it earlier (native still running) would SIGTERM the native child (2198) = a mid-run
save (10-15 min, the drop-in says avoid); placing it between the join and 3026 would leave the projection/digest for the
resume (lawful but not "ROOT done"). Race margin: 3077 -> 3026 is microseconds; a marker landing in it yields the lawful
projection-pending save, never an interrupted pass.

Not used: ACTION=handover (finishes the running day through the teacher), ACTION=retire (removes the entries; not a hold),
any kill or instance stop.

## Readings
Confirmed: Run.child (experiment.py:1340-1342) calls `self.check_save()` right after the child exits ("Never kill their
workers or start a following stage after a save request"), so a ROOT child exit 75 under the standing marker raises
SystemExit(75) in the worker thread before Run.root's `code != 0` check (1577). TeacherSaved.__init__ -> SystemExit(75)
(parallel_teacher.py:757-762). Probe stages after the last mid-run check: 'root-projection' (boss_session.py:3090, start of
_native_projection), 'root-projection-publication', 'root-digest' (monday_calculations.py:89), 'root-derived' complete (2940).
Trigger used for the save: R/progress.json stage in root-projection* / root-digest, or work/derive.json present.

### Probe 1, box 23:37:45Z (SSM acad4519-663d-4b08-a24c-f26a3cf2eed0, read-only)
- LEGACY FINISHED 23:34:53Z without the shard exit hang: log "legacy pass: 269571 frame rows from replica shards, 0 built in
  the replay; the replay waited 2156.2 s on shards"; legacy progress 360,328/360,328 complete, failed 0. The 14 shard pids are
  gone (shards.close() path, boss_session.py:2612); ROOT 14860 R 33% CPU, only child = native 14929 (R 83.7%). No SIGKILL
  needed; nothing done.
- Native 621,017/771,787 (80.46%) at 23:37:38, running, failed 0 -> ~150k left at ~110/s -> ETA ~00:00Z.
- ROOT now in its layer writes (write_layer_json, 2690-2700) before legacy-stage.json and the native join. No
  native-stage.json / legacy-stage.json / derive.json / calculations-receipt.json yet.
- Queue root.json seq 2: running, where box-slot, finish null, save_request null, owner attempt e2e-20231018-a2-20231018-a1,
  booking day-run-20231018-day_slot_root-1791402822-3111 CPUs 0-31, holder 14824. root-worker.json running, scope
  e2e-20231018-a2:20231018, running [2], pending 1. save/ holds only the three archived (.resumed-*) markers; no standing marker.
### Probe 2, box 23:4xZ (SSM ed4f7793-28de-406a-b115-ddcb4c67f1df, read-only): git HEAD of the staged checkout = c9bf631e88...
(the wrapper's MARKETS_SHA check will pass); the wrapper file present. The 250 s loop itself failed (dash has no $SECONDS); no
samples. Log unchanged since 23:34:53Z.

### KeepRunning / idle guard (code reading, for the parent)
The root worker's end (queue main, frankie_box_frankie_queue.py:2347-2355) calls `X.keep_running(run, False, ...)`
(experiment.py:736-760): KeepRunning is tagged 'false' unless box_in_use lists another worker/orchestrator/controller.
After the hold the worker ends with no running day, so the tag WILL be cleared (session 4 saw exactly this at 20:05Z).
The idle guard (.github/workflows/frankie_box_idle_guard.yml cron '17 */6 * * *' -> 00:17Z, 06:17Z, 12:17Z, 18:17Z;
deploy/aws/idle_instance_guard.py) STOPS a box whose tag is not 'true' and that holds no fresh pod-root controller lease
(LEASE_FRESH_SECONDS 600); a2 is a queue run over SSM with no controller lease. So: once the hold lands, KeepRunning=true must
be re-set (ec2 CreateTags, as the parent did at 22:44Z) before the next guard run, or the box is stopped (state on disk is
durable; the resume would then need a start). Not done by this role (the only write authorized is the queue save).

### hold-watch 3 (SSM 77f11096-4998-44e3-93c0-b84c69dedcd9, sent 23:41:07Z, 250 s, trigger armed)
Loop: every 2 s read R/progress.json stage; on root-projection*/root-digest*/root-derived* or work/derive.json present, run
`CODE_ROOT=<c9bf631 checkout> MARKETS_SHA=c9bf631e88... ACTION=save RUN=e2e-20231018-a2 DAY=20231018
bash deploy/aws/box/frankie_box_frankie_queue.sh` (the wrapper, as session 4) and stop; every 30 s a sample line.
Result (ended 23:45:19Z, no trigger, nothing written): 23:41:08 stage root-legacy-records complete; 23:42:09 onward stage
root-legacy-finalize (ROOT Sl futex_do_wait 37.6%, 15 encoder children 17668-17682 + native 14929): the layer writes
(write_layer_json) in progress: derived/legacy_native_signed_flow.json, legacy_per_second_roll20.json, legacy_price.json written
23:41:47; legacy_book_imbalance.json.pending-aa70a418... 21.4 GB and growing at 23:45:19. Native 638,328 (23:41:08) ->
664,309 (23:45:11): ~107 rec/s, 107,478 left -> ETA ~00:02Z. No native-stage/legacy-stage/derive.json yet.

### hold-watch 4 (SSM 5d17ee9d-9133-4cb3-bdc4-d3e34c73e920, sent 23:46:01Z, 265 s, trigger armed, same script as round 3)
Output readable by GetCommandInvocation after ~23:50:30Z. No disk fields in its samples (sent before the coordinator's note).

### DISK, report-at-once condition (read-only probes 7f9ed6e8-44d6-4fd2-b98b-397e6e8d1e46 at 23:46:23Z and
18d8e66a-6c6e-4983-b317-1b1d3daf2047 at 23:46:57/23:47:12/23:47:27Z)
- df /: 526.5 GB free at 23:46:23Z; 519.9 GB at 23:46:57; 517.0 GB at 23:47:12; 514.1 GB at 23:47:27 -> 5.78 GB per 30 s =
  11.6 GB/min (193 MB/s) consumption.
- Growing files: derived/legacy_book_imbalance.json.pending-aa70a418... 29.9 GB (23:46:22) -> 34.53 (23:46:57) -> 38.61 GB
  (23:47:27): +4.09 GB per 30 s = 8.2 GB/min (136 MB/s); bedrock/recovery-6f84.../ledgers/exact_member_rows.jsonl.assembling
  169.0 -> 169.8 GB and exact_member_rows.append.jsonl 102.8 -> 103.7 GB: +0.83 GB each per 30 s = 3.3 GB/min together
  (native). frames.jsonl ended at 496,743,568,399 B (23:34:53). bedrock/ledgers/exact_member_rows.jsonl 66.1 GB (22:32, the
  pre-save copy).
- WHY the layer is this big: write_layer_json (boss_session.py:762-790) encodes "every top-level RowSpool value of the layer
  (legacy_book_imbalance.frames ...)" into the JSON layer file: legacy_book_imbalance.json carries the WHOLE frames spool
  re-encoded (2774: "the layer files carrying a whole spool"). Expected final size ~ the spool, ~497 GB; 38.6 GB written at
  23:47:27 -> ~458 GB to go at 8.2 GB/min = ~56 min -> the layer ends ~00:43Z.
- Straight line: native finishes ~00:02Z (15 min more at 11.6 GB/min total = -174 GB -> ~340 GB free); then the layer alone
  ~41 min x 8.2 = ~335 GB -> ~5 GB free at the layer's end (~00:43Z), BEFORE legacy-stage.json, the native join/reuse, the
  projection, the digest (its legacy book table reads the frames spool; output size unmeasured) and the receipt. Any extra
  copy the native finalization makes (the 170 GB .assembling into exact_member_rows.jsonl, if copied rather than renamed)
  crosses zero before that. The free-space slope crosses zero (or ends within a few GB of it) before the digest's end.
- Nothing deleted, nothing stopped (read-only). The hold plan is unchanged and the trigger stage (root-projection) cannot be
  reached before the layer write ends (~00:43Z at the earliest), so no save fires before then.

## Coordinator's disk tasking (23:50Z): inventory, EBS, devices; hold watch kept armed; authorized write #2 = KeepRunning=true after the hold
### hold-watch 5: SSM 6ea43356-0999-439c-9567-a670513e9d38 sent 23:51:02Z (265 s; df and the three growing files in every sample).
### EBS (ec2 DescribeVolumes / DescribeVolumesModifications / DescribeInstances, us-east-1, read-only, 23:51Z)
- vol-0d36715924f03b86c gp3 2048 GiB, IOPS 16000, throughput 1250, in-use, /dev/sda1 on i-035994afa8bdf66a5 (us-east-1d), the
  ONLY block device; DeleteOnTermination true.
- Modification 20:45:57Z (throughput 1000 -> 1250) state completed, Progress 100, EndTime 2026-10-07T22:12:21Z.
- AWS rule: at least six hours after the previous modification of the same volume before another one. A size increase is NOT
  permitted now; earliest 04:12:21Z 2026-10-08 (counted from completion; 02:45:57Z if AWS counts from the start; a try before
  returns VolumeModificationRateExceeded and changes nothing).
- Root fs: ext4 on /dev/nvme0n1p1 = the full 2 TiB disk (2,197,948,448,256 B part of 2,199,023,255,552); growpart and
  resize2fs present. deploy/aws/box/frankie_box_grow_disk.sh: requires DISK_GIB=2048 exactly, checks the root device is
  /dev/nvme0n1p1 ext4 and the disk is >= 2 TiB, TMPDIR=/run, growpart /dev/nvme0n1 1 then resize2fs online; no stop, no deletion.
  It is written for the 2048 GiB expansion only (a larger size needs its constants changed; source edit, not now).
- Instance tags now: KeepRunning=true (reason "ccode_step8: a2 resumed on c9bf631 22:43:48Z ... re-set after the saved worker end
  cleared it"), KeepRunningPolicy present.
- A second volume: no cooldown applies to CreateVolume/AttachVolume; free device names: everything but /dev/sda1 (e.g. /dev/sdf,
  shows as /dev/nvme1n1). Moving a2's files is only possible for CLOSED files (see inventory 3).
### Inventory 1 (SSM 9b4308aa-53d2-4aef-8f42-eb3a5a9016e1, 23:51:07Z, read-only)
- df /: 2,129,040,207,872 total, 1,653,118,533,632 used, 475,904,897,024 free (78%). No swap. /opt/frankie-box/work 1,604.6 GB.
- a2 attempt experiment-roots/e2e-20231018-a2-20231018-a1: 925.6 GB (running).
- monday-calculations/full-20211004-20260927-r1-48: 427.3 GB (the September Monday cycle-0 ROOT, an earlier run; not a2).
- experiment-roots other than a2: e2e-20231018-a1-20231018-a1 3.6 GB (the retired a1 attempt); days-2026092x-* roots 0.7-12 GB
  each (~84 GB total for the 30-day plan runs); experiment-teacher-rows 25.1 GB (20211005 24.3 GB); day-external 10.2 GB.
- ingest-* dirs: 20231018 8.9 GB (a2's input); other days 20211004 23.7 GB, 20221011/12/18/19 and 20231003/04/10/11/17 9-15 GB
  each (~120 GB total). runs 0.76 GB.
- /opt/frankie-box/code 21.6 GB (checkouts); venv 3.0; ingest-code 3.3; session 2.7; granite 2.3; /var 2.9; /root 0.5.
### Inventory 2 (SSM e36826e3-75a0-41ea-b698-72279d234a59, 23:51:49Z, read-only: files > 1 GB, open fds)
- Layer write progress: legacy_book_imbalance.json.pending 74.47 GB at 23:51:49 (38.6 GB at 23:47:27: 8.2 GB/min, steady).
  OPEN by ROOT 14860 (writer); frames.jsonl (496.7 GB, final 23:34) OPEN for reading by the 14 encoders 17668-17682.
- Native (OPEN, live writers 14929/14974/14977): recovery-6f84.../ledgers/exact_member_rows.jsonl.assembling 174.8 GB,
  exact_member_rows.append.jsonl 108.7 GB, exact_lifecycle_rows.jsonl.assembling 4.26 GB, exact_lifecycle_rows.append.jsonl 2.57 GB.
- a2 pre-save copy work/bedrock/ledgers/exact_member_rows.jsonl 66.1 GB (mtime 22:32, the native ledger of the attempt before
  the 22:32 save): NOT OPEN by any pid. Whether the resumed native (checkpoint 000005 -> recovery-6f84...) still references it
  is checked in inventory 3 (bedrock/ listing); until then classify as a2-owned, closed, reference unresolved.
- monday-calculations/full-20211004-20260927-r1-48 (427.3 GB, the 2026-09-27 Monday cycle-0 ROOT, an earlier run): biggest
  files .projection-v2/published-e6ff.../full_bid_ask_depth.json.gz 89.5 GB (09-27 18:22), .digest-109f.../calculation-layers/
  sources.sqlite 81.8 GB (09-27 23:54), prepare-000009/rows.sqlite 42.9 GB, .rows/full_bid_ask_depth-members.jsonl 32.0 GB,
  derived_v4_mechanics_fifo_features.json.gz 30.4 GB, 14 merge-*.sqlite ~4.5 GB each (63 GB), queue_age_and_survival/fifo_queues
  gz 11.4+11.4 GB, superseded/digest-render-20260928T115002Z/derivation-digest-full.md 3.8 GB, ... Newest mtime 2026-09-28
  07:56. NO open fd by any process. Reference by a2: checked in inventory 3.
- e2e-20231018-a1-20231018-a1 (retired a1 attempt, 3.6 GB; frames.jsonl 3.07 GB, 18:59): not open.
- ingest-* journals (other days): 20211004 23.7 GB, 20231011 14.7, 20231004/20231010 11.7, 20221018 11.3, 20231003/20231017 10.2,
  20221011 10.2, 20221012 9.2, 20221019 9.1 GB; a2's own ingest-20231018 8.8 GB. None open. (The other days are the 30-day plan's
  sealed ingests: re-fetchable from S3 at a Databento-free cost of time only, but Greg's data, not this role's call.)
- days-2026092x-* experiment roots: ~84 GB total (largest files 1.7-2.8 GB), 09-29/30, not open.
- code checkouts: 11 x ~1.4 GB = 21.6 GB; a2 runs c9bf631...-37695921903-1; 275367fe..., 98579cea..., 1727bb4f... are a2's
  earlier/rebind checkouts (content_rebinds records); the rest are older sessions' checkouts.
- No swapfile.
### Inventory 3 (SSM 98d8496e-a2d4-4db3-a39e-7dd7f3e6ab59, 23:53:21Z, read-only)
- a2's attempt JSON (source-binding, calculation-pins, work/*.json, derived/*.json) references NO monday-calculations path.
  Paths it names: ingest-20231018-gh-36571235912-1 (7x, its input), code/98579cea...-37677357943-1 (2x: the first-dispatch
  checkout recorded in the binding; content_rebinds moved it to later checkouts), experiment-roots (1x).
- monday-calculations/full-20211004-20260927-r1-48: newest file mtime 2026-09-28 13:22 (calculations-receipt.json, phase, note);
  no open fd by any process; classification = an earlier run (Monday cycle 0, 2026-09-27), NOT OPEN, NOT referenced by a2:
  deletion/move candidate for Greg (427.3 GB). Its calculations-receipt is the September record (keep that 4 KB file).
- Live frankie pids' open files outside a2's attempt dir: only experiment/e2e-20231018-a2/logs/20231018-root.log, the queue's
  root-worker.log and root-worker.lock. Nothing else is open.
- a2 pre-save copy bedrock/ledgers/: exact_member_rows.jsonl 66.1 GB, exact_lifecycle_rows.jsonl 1.69 GB,
  legacy_observable_rows.jsonl 0.26 GB (all 22:32:39, the ledgers the native wrote before the 22:32 save); the resumed native
  writes under bedrock/recovery-6f84.../ledgers (296.5 GB, growing) from checkpoint 000005. Not open. Whether the recovery
  finalization re-reads the pre-save ledgers is a code question (frankie_box_bedrock recovery); unresolved here: treat as
  a2-owned until that is read. bedrock/checkpoints 0.34 GB, recovery checkpoints 1.18 GB.
- a2 attempt breakdown: work/derived/.rows 498.4 GB (frames 496.7 + prices/structures/failures/INPUT), derived (layers) 585.4 GB
  total incl. the growing legacy_book_imbalance; work/bedrock 366.1 GB; attempt 951.6 GB at 23:53Z.
- e2e-20231018-a1 attempt: 3.6 GB, closed, retired run (ACTION=retire 19:51Z): candidate.
- Code checkouts: 11; a2 runs c9bf631...; the worker's code_root is the same; 98579cea (named in a2's binding), 275367fe and
  1727bb4f (a2's rebind history) should be kept with a2; the other 7 (94f0d073, 18cbc5a4, ad46ca06, 910ef886, 9e7a7d90,
  901bc0d2, 0c478e07) ~1.4 GB each are older sessions' checkouts.

### hold-watch 5 result (SSM 6ea43356, 23:51:02-23:55:28Z, no trigger, nothing written)
free 476.78 GB (23:51:02) -> 430.56 GB (23:55:06): -46.2 GB / 244 s = 11.4 GB/min. layer 68.05 -> 101.16 GB (8.16 GB/min;
104.1 GB at 23:55:28). asm 173.5 -> 179.9 GB, app 107.4 -> 113.7 GB (3.1 GB/min together). Native 692,088 -> 714,941
(94 rec/s, slowing): 56,846 left -> ~00:05Z. ROOT Sl/Rl 38%, 16 children, stage root-legacy-finalize.
Projection at 23:55: layer needs ~497 GB -> ~396 GB more at 8.16 GB/min = ~48 min -> ends ~00:44Z. Free at the native end
(00:05Z) ~316 GB; the layer alone then needs ~318 GB -> free ~0 at the layer's end. 150 GB free is reached ~00:20Z.
### hold-watch 6: SSM 8adc039b-0258-4169-acae-8f517f0aa58f sent 23:55:38Z (265 s, armed).
### archive prep (read-only): SSM bf1187e5-fe24-4450-9391-7165bfd08852 sent 23:55:56Z (fd scan, references, du + file counts).

## MOVE plan (coordinator's request; NOTHING executed; waits for Greg's go relayed by the parent)
Targets (in order): 1 monday-calculations/full-20211004-20260927-r1-48 (427.3 GB); 2 ingest-* dirs other than 20231018
(~120 GB); 3 experiment-roots/days-2026092x-* (~84 GB); 4 experiment-teacher-rows (25 GB); 5 day-external (10 GB);
6 /opt/frankie-box/code/* other than c9bf631...-37695921903-1 (the worker's and a2's code_root) (~14 GB for 10 checkouts;
keep 98579cea/275367fe/1727bb4f with a2 unless Greg says otherwise: they are named in a2's binding/rebind records).
Precondition for each: the prep scan shows NO open fd into it and NO reference from a2's attempt/queue/run JSON (see the
prep result); a2's own files (frames.jsonl is being READ by 14 encoders; the native ledgers are OPEN) are NOT moved.

AWS (us-east-1, account of i-035994afa8bdf66a5, AZ us-east-1d):
 1. ec2 CreateVolume: AvailabilityZone=us-east-1d, VolumeType=gp3, Size=2048, Iops=10000, Throughput=1000, Encrypted (match
    the root volume's setting), TagSpecifications=[{ResourceType: volume, Tags: [{Name: frankie-archive-20261007},
    {Purpose: a2 disk relief, moved runs}]}]. Wait DescribeVolumes State=available (~10 s).
 2. ec2 AttachVolume: VolumeId=<new>, InstanceId=i-035994afa8bdf66a5, Device=/dev/sdf. Wait Attachments State=attached.
    (No cooldown applies to a new volume; the root volume's own 6 h cooldown is untouched. Cost: gp3 2048 GiB ~$164/month +
    IOPS above 3000 (7000 x $0.005 = $35) + throughput above 125 (875 x $0.04 = $35) -> ~$234/month; 3000/125 would be ~$164.)
On the box (SSM, one command per step, each verified):
 3. for i in $(seq 60); do [ -b /dev/nvme1n1 ] && break; sleep 2; done; lsblk -b -o NAME,SIZE,TYPE,MOUNTPOINT /dev/nvme1n1
    (must show the 2048 GiB disk with NO partitions and NO filesystem: blkid /dev/nvme1n1 prints nothing).
 4. mkfs.ext4 -L frankie-archive -m 0 -E lazy_itable_init=0,lazy_journal_init=0 /dev/nvme1n1
 5. mkdir -p /opt/frankie-box/archive && mount -o noatime /dev/nvme1n1 /opt/frankie-box/archive && df -B1 /opt/frankie-box/archive
 6. cp -a /etc/fstab /root/fstab.before-archive-$(date -u +%Y%m%dT%H%M%SZ); echo "LABEL=frankie-archive /opt/frankie-box/archive
    ext4 defaults,noatime,nofail 0 2" >> /etc/fstab; findmnt --verify
 7. Per directory D (source), A=/opt/frankie-box/archive/<same relative path under work or code>:
    a. before: SRC_DU=$(du -x -B1 -s D | cut -f1); SRC_N=$(find D -xdev -type f | wc -l); sha256sum of the 3 largest files
       (find D -type f -printf '%s %p\n' | sort -rn | head -3) -> recorded.
    b. re-check no open fd: ls -l /proc/[0-9]*/fd 2>/dev/null | grep -F "D/" | head -1 (must be empty).
    c. mkdir -p A && ionice -c3 nice -n 10 rsync -aHAX --info=progress2 D/ A/   (one rsync per directory; across devices, so
       no reflink; --info=progress2 to the SSM output or a log under /opt/frankie-box/archive/.logs/).
    d. verify: du -x -B1 -s A == SRC_DU (ext4 to ext4, same block size: equal or within the sparse-file tolerance), find A -type f
       | wc -l == SRC_N, sha256sum of the same 3 largest files equal; rsync -aHAXn --itemize-changes D/ A/ prints nothing.
    e. rm -rf D   (only after d passes) ; ln -s A D ; ls -la D ; readlink -f D
    f. df -B1 / after each directory, recorded.
    Order: 1 the Monday root (427 GB: at 600-800 MB/s ~9-12 min copy + ~10 min for the sha256 of the 3 largest files
    89.5/81.8/42.9 GB, hashed before and after = ~430 GB read twice; use the sampled set only), then the ingests (120 GB,
    ~3 min), the days roots (84 GB, ~2 min), teacher rows, day-external, code checkouts (many small files: slower, ~5 min).
    Total ~25-40 min of copy; the first 427 GB back on / within ~25 min of the go (rsync + verify + rm).
    NOTE on contention: the layer write reads frames.jsonl at ~136 MB/s and writes 136 MB/s; the native writes ~52 MB/s; the
    volume's cap is 1250 MiB/s; rsync at 600-800 MB/s read from / fits but is the same volume: expect the layer write to slow
    somewhat (it is CPU-bound on 14 encoders today; the disk is not its limit). ionice -c3 keeps rsync behind the ROOT.
 8. Reversal: rm the symlink D, rsync A/ back to D/, verify, rm -rf A; or mount the archive and point consumers at it.
 Alternative if the go is for a DELETE of the Monday root instead of a move: rm -rf after copying its small receipt files
 (calculations-receipt.json, calculation-pins.json, note, phase, progress.json, checkpoints.json, pause-*.json: < 1 MB) to
 /opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48.receipts/ (Greg's call; not this role's).

### Archive prep result (SSM bf1187e5-fe24-4450-9391-7165bfd08852, 23:55:56Z, read-only)
(a) Open fds: a scan of every /proc/*/fd (72 distinct open paths) finds NONE inside any candidate (Monday root, teacher rows,
    day-external, the other-day ingest-* dirs, days-20260929-3-* roots, the non-c9bf631 code checkouts); no live frankie pid
    has cwd/exe inside one. (The glob covered days-20260929-3-*; the days-20260930-1-* roots (~30 GB) were not in this scan's
    du; their fd check is implied by the full-fd scan only if listed: re-run with that glob before a go.)
(a) References from a2's attempt + run + queue JSON:
    - day-external: REFERENCED by experiment/e2e-20231018-a2/days/20231018/external.json (the day file's provenance) -> NOT
      a candidate as a whole; at most its non-a2 subdirs (days-2026092x-*-ext-*), ~9 GB. Leave day-external alone.
    - code/98579cea...: referenced by a2's calculation-pins.json and source-binding.json (3x) and root.json -> KEEP.
    - code/275367fe... and code/18cbc5a4...: referenced by frankie-queue/root.json (attempt history) -> keep (history
      pointers; moving them breaks nothing live but Greg's call).
    - Monday root, teacher rows, other-day ingests, days-2026092x roots: NO reference from a2.
    - a2 names only: ingest-20231018-gh-36571235912-1 (26x), /opt/frankie-box/brain/20231018-day-file (+superseded copy),
      brain/20231018-ingest, experiment-roots, frankie-queue, day-external (the one above).
(b) du -B1 -s and file counts (candidates, descending): Monday root 427,266,150,400 B / 500 files; experiment-teacher-rows
    25,141,534,720 / 6,048; ingest-20211004-ingest-1790057801 23,687,516,160 / 2; ingest-20231011 14.78 GB / 9;
    days-20260929-3-20211006-a1 12.04 GB / 88; ingest-20231010 11.73 / 9; ingest-20231004 11.73 / 9; ingest-20221018 11.35 / 9;
    days-20260929-3-20211005-a2 11.09 / 88; ingest-20231003 10.27 / 9; ingest-20231017 10.26 / 9; ingest-20221011 10.21 / 9;
    day-external 10.16 GB / 3,330 (referenced: excluded); ingest-20221012 9.21 / 9; ingest-20221019 9.12 / 9;
    days-20260929-3-20221004-a1 8.91 / 88; -20211012-a1 7.90 / 88; -20211013-a1 7.22 / 88; -20221005-a1 7.18 / 88;
    code checkouts 10 x ~1.42 GB / ~4,080 files each + transfer-* tarballs 9 x 0.6 GB / 2 files; small ingest canaries < 0.2 GB.
    Movable without any a2 reference and no open fd: Monday root 427.3 + other-day ingests ~122 + days-20260929-3 roots ~54
    (+ days-20260930-1 roots ~30, to re-scan) + teacher rows 25.1 + 7 non-a2 code checkouts ~10 + transfer tarballs ~5
    = ~640-670 GB.
Devices: only /dev/nvme0n1 (root) exists; /dev/sdf -> /dev/nvme1n1 is free. fstab: LABEL=cloudimg-rootfs / ext4
    discard,commit=30,errors=remount-ro,lazytime; /boot; /boot/efi.

### hold-watch 6 result (SSM 8adc039b, 23:55:38-00:00:04Z, no trigger, nothing written)
free 424.69 GB (23:55:38) -> 380.49 GB (23:59:42): -44.2 GB / 244 s = 10.9 GB/min. layer 105.39 -> 137.77 GB (8.0 GB/min;
140.75 GB at 00:00:04). asm 180.66 -> 186.42, app 114.54 -> 120.30 (2.8 GB/min together, slowing with native). Native
717,158 -> 740,356 (95 rec/s): 31,431 left -> ~00:05:30Z. ROOT 38.4%, 16 children, stage root-legacy-finalize. Log unchanged.
### hold-watch 7: SSM 75d9082a-f7c4-4eb0-8e7a-8d73901f03c9 sent 00:00:06Z (265 s, armed; samples add the final ledger size).
### Native ledger finalization (code, frankie_box_segmented_ledger.py): no extra copy at the end
- restore_prefixes/_resume_sink (380-420): on the resume the sink writes new rows to <ledger>.append.jsonl and a pinned
  materializer (_Materializer, 250-300) streams the frozen prefix PARTS (the pre-save ledgers: bedrock/ledgers/
  exact_member_rows.jsonl 66.1 GB is such a part) and then the append segment, in byte order, into <ledger>.assembling
  (_assemble 133-190); so .assembling (186 GB) = prefix copy (66) + append (120) and grows with the append. At the end
  os.replace(.assembling -> exact_member_rows.jsonl) (line ~183): a rename, no further copy; the append segment is not
  unlinked there. So the native finish adds ~nothing beyond the current slope; the 120 GB append stays unless another step
  removes it.
- The pre-save copy bedrock/ledgers/*.jsonl IS READ by the materializer (prefix parts, open only while a chunk is read):
  referenced by a2's native resume -> NOT a candidate while the native runs; after the native stage completes, a2's
  checkpoint 000005 still names it (a future resume from that checkpoint would need it); Greg's call after completion.

## GREG'S GO (relayed 00:0xZ 2026-10-08): additive archive volume + copies; nothing removed in this phase
### Step 1, AWS (us-east-1), all in one run_script at 00:02:5xZ
- ec2 DescribeVolumes vol-0d36715924f03b86c: Encrypted=true, KMS arn:aws:kms:us-east-1:568968024170:key/77551067-fa8c-412c-87a5-490d85ae2e79
  (the new volume matches it).
- ec2 CreateVolume: vol-004b68c077be09cc9, gp3, 2048 GiB, IOPS 10000, throughput 1000, us-east-1d, encrypted with the same key,
  tags Name=frankie-archive-20261007 Purpose=frankie-archive, ClientToken frankie-archive-20261007-a2-disk-relief,
  CreateTime 2026-10-08T00:02:53Z -> available.
- ec2 AttachVolume vol-004b68c077be09cc9 -> i-035994afa8bdf66a5 /dev/sdf, AttachTime 00:02:58Z -> attached.
### hold-watch 8: SSM 7072bd34-2734-4399-a299-986dad0f7a6d sent 00:02:27Z (265 s, armed; overlaps round 7's tail).
### Step 1, box (SSM a68e1776-0ab3-4f1e-a84e-8aa0b64b9bc9, 00:03:42Z, WRITES as authorized)
- /dev/nvme1n1 present (serial vol004b68c077be09cc9), 2,199,023,255,552 B, blkid empty (rc 2) before.
- mkfs.ext4 -q -L frankie-archive -m 0 /dev/nvme1n1: ok; blkid after: LABEL=frankie-archive UUID=6c02aaf8-620a-4b3c-bc41-f9aafaf14f3b ext4.
- mount -o noatime /dev/nvme1n1 /opt/frankie-box/archive: ok. fstab backup /root/fstab.before-archive-20261008T000343Z (155 B);
  appended "LABEL=frankie-archive /opt/frankie-box/archive ext4 defaults,noatime,nofail 0 2"; findmnt --verify: 0 errors,
  1 warning (systemd daemon-reload not run; not needed for the live mount; harmless).
- df: / 340,181,147,648 B free (85% used) at 00:03:42Z; archive 2,163,333,812,224 B free. zstd 1.5.5, tar, rsync, ionice present.
- Slope check: 380.49 GB (23:59:42) -> 340.18 GB (00:03:42) = -40.3 GB / 4 min = 10.1 GB/min; zero at ~00:37Z on this slope
  (the layer write ends ~00:44Z): the Monday root's removal (a later instruction) is what buys the margin.
### Step 1, box (SSM a68e1776-0ab3-4f1e-a84e-8aa0b64b9bc9, 00:03:42Z, WRITES as authorized)
- /dev/nvme1n1 present (serial vol004b68c077be09cc9, 2,199,023,255,552 B); blkid empty (rc 2) before.
- mkfs.ext4 -q -L frankie-archive -m 0 /dev/nvme1n1: ok; blkid after: LABEL=frankie-archive UUID=6c02aaf8-620a-4b3c-bc41-f9aafaf14f3b ext4.
- mount -o noatime /dev/nvme1n1 /opt/frankie-box/archive: ok. fstab backed up to /root/fstab.before-archive-20261008T000343Z;
  line appended: "LABEL=frankie-archive /opt/frankie-box/archive ext4 defaults,noatime,nofail 0 2"; findmnt --verify: 0 errors,
  1 warning (systemd daemon-reload pending; harmless, mount is live). Dirs made: archive/.logs, archive/monday-calculations.
- df at 00:03:42Z: / free 340,181,147,648 B (85% used); archive free 2,163,333,812,224 B. zstd 1.5.5, tar, rsync, ionice present.
- Removal mechanics changed (coordinator 00:0xZ): Greg runs removals himself; this role appends a "FOR GREG TO RUN" block per
  verified item. No removal by this role.
### Step 2 canary: SSM 89e8f4ce-3e8a-47d8-8aad-b0f68d26fd00 sent 00:04:29Z (60 s tar|zstd of the Monday root, output deleted after).
### hold-watch 7 result (SSM 75d9082a, 00:00:07-00:04:33Z, no trigger, nothing written)
free 375.96 GB (00:00:07) -> 335.34 GB (00:04:10): -40.6 GB / 243 s = 10.0 GB/min. layer 141.07 -> 173.70 GB (8.1 GB/min).
Native 743,116 -> 758,601 (stalled 00:00:37-00:01:38 at 745,913 with progress age 66 s, then resumed; ~13k left -> ~00:07Z).
asm 187.0 -> 190.8 GB; final ledger files still 0 B placeholders (exact_member_rows.jsonl 0 B at 22:44:08).
### Step 2 canary result (SSM 89e8f4ce, 00:04:30-00:05:36Z): 29,853,317,120 B of source in 60 s = 498 MB/s; archive bytes
24,174,865,634 (ratio 0.81); canary output deleted. Projection 427.3 GB / 498 MB/s = 858 s = 14.3 min < 20 min -> ONE tar.zst.
/ free 331.90 GB (00:04:30) -> 320.95 GB (00:05:36).
### Step 2, Monday root copy STARTED (SSM ece66ae3-f722-4580-abbf-7e3a2167acc3, WRITE to the archive only)
- 00:06:45Z: `cd /opt/frankie-box/work/monday-calculations && nice -n 19 ionice -c3 tar --totals -cf - full-20211004-20260927-r1-48
  | zstd -T2 -3 -q -o /opt/frankie-box/archive/monday-calculations/full-20211004-20260927-r1-48.tar.zst` (setsid, detached;
  pids bash 27008 / tar 27010; log /opt/frankie-box/archive/.logs/monday-root-tar.log). / free at start 309,094,195,200 B.
  Expected end ~00:21Z (14.3 min at the canary's 498 MB/s). Source untouched.
### hold-watch 9: SSM e8458b8e-af46-421a-98da-f76bdd303051 sent 00:07:04Z (armed; samples add the archive tar size).
### prep 2 (read-only): SSM 0ca3e6f1-6fc8-45a7-bd5f-bf28d830c7ee sent 00:07:17Z (Monday root counts/3 largest, days-20260930-1 fds,
re-creatable sizes, a1 receipts).
### hold-watch 8 result (SSM 7072bd34, 00:02:27-00:06:51Z, no trigger, nothing written)
free 354.13 GB (00:02:27) -> 311.54 GB (00:06:31): -42.6 GB / 244 s = 10.5 GB/min. layer 160.0 -> 192.1 GB (7.9 GB/min).
Native 747,998 -> 769,040 (86 rec/s; 2,747 left at 00:06:31 -> ends ~00:07:10Z). asm 188.3 -> 193.7 GB; final ledgers still 0 B.
### prep 2 result (SSM 0ca3e6f1, 00:07:17Z, read-only)
- Monday root full-20211004-20260927-r1-48: 604 entries (500 files, 104 dirs, 0 symlinks). Three largest: 89,515,551,980
  work/derived/.projection-v2/published-e6ff40904d5a437ea30a6f365e8f21f7/full_bid_ask_depth.json.gz; 81,806,479,360
  work/derived/.digest-109f959829b14b169fd6b98d69fc3125/calculation-layers/sources.sqlite; 42,872,123,392
  work/derived/.digest-109f.../calculation-layers/prepare-000009/rows.sqlite.
- days-20260930-1 roots (open fds 0 each): 20211020-a1 0.72 GB/6 files; 20221011-a1 0.71/6; 20221011-a2 5.35/64; 20221012-a1 0.66/6;
  20221018-a1 0.77/6; 20221018-a2 5.75/64; 20221019-a1 6.38/88; 20231003-a1 4.63/88; 20231004-a1 0.53/6; 20231004-a2 0.49/6
  (total ~26.0 GB).
- open fds 0: experiment-teacher-rows, e2e-20231018-a1 attempt, every code/transfer-* tarball.
- Re-creatable (no copy needed): __pycache__ under /opt/frankie-box 331,337,728 B in 1,838 dirs; /var/log/journal 1,707,810,816 B;
  /var/cache/apt 254,812,160 B; /root/.cache/pip 6,295,552 B; /tmp files older than 1 day: 0. (/opt/frankie-box/tmp 1.33 GB holds
  session files from 09-21 and an archive_day script: NOT re-creatable by definition; left out.) Total re-creatable ~2.3 GB only.
- a1 attempt (retired) receipts: all files < 2 MB except work/derived/.rows/frames.jsonl 3.07 GB (+ small spools); receipts =
  calculation-pins.json 33,283, external-computation.json 42,301, source-binding.json 7,631, note, phase, progress.json,
  native-overlap/*.json, work/native-overlap.json, work/input-state.pkl 7,607, work/legacy-state.pkl 314,196, bedrock/checkpoints/*.

## FOR GREG TO RUN: re-creatable items (no copy needed; nothing of the run's data; ~2.3 GB)
    # 1. python bytecode caches under /opt/frankie-box (rebuilt on import; PYTHONDONTWRITEBYTECODE=1 is set for the queue anyway)
    find /opt/frankie-box -xdev -type d -name __pycache__ -prune -exec rm -rf {} +      # 331 MB, 1838 dirs
    # 2. journald (keeps the last 200 MB)
    journalctl --vacuum-size=200M                                                        # ~1.5 GB
    # 3. apt and pip caches
    apt-get clean; rm -rf /root/.cache/pip                                               # 255 MB + 6 MB
    df -B1 /

## Greg: "Do your plan" (relayed ~00:11Z): removals of verified, unreferenced, unopened sources are now authorized (plan step 7e),
## plus the re-creatable clears. Excluded, untouched: day-external, checkouts 98579cea/275367fe/18cbc5a4/c9bf631 (and the
## worker's), the 66 GB pre-save ledger copy, everything under a2's attempt, ingest-20231018.
### hold-watch 9 result (SSM e8458b8e, 00:07:04-00:11:30Z, no trigger, nothing written)
- NATIVE FINISHED its row pass: 770,700 at 00:07:04 (progress age rising), then the materializer completed: at 00:08:36 the
  .assembling is gone and recovery-6f84.../ledgers/exact_member_rows.jsonl = 193,743,650,444 B (final). The native child then
  entered a byte-counting pass (native progress 8.4 MB -> 22.8 GB -> 48.2 GB between 00:10:07 and 00:11:08 = ~800 MB/s: the
  receipt/witness hashing of the finished ledgers, a READ). Child count still 16 (native 14929 alive).
- CONTENTION: from 00:10:07 ROOT 14860 sits in D balance_dirty_pages; the layer file grew 212.4 (00:09:06) -> 216.3 (00:09:36) ->
  220.1 (00:10:07) -> 221.5 (00:10:37) -> 221.7 GB (00:11:08): 8 GB/min down to ~0.5 GB/min. The volume (1250 MiB/s total) is
  saturated by the native's hash read (~800 MB/s) + the archive tar's read (~500 MB/s; ionice idle has no effect under the
  'none' NVMe scheduler) + the layer's own read/write. The free-space slope flattened the same way (278.3 -> 278.0 GB).
  Expected to ease when the native hash pass ends (~194 GB at 800 MB/s = ~4 min, ~00:13-00:14Z) and when the tar ends (~00:21Z).
  No action taken (the tar is the path to the 427 GB relief; the ROOT is slowed, not harmed).
- Archive tar: 5.9 GB (00:07:04) -> 112.7 GB (00:11:08) = 27 GB/min of archive = ~33 GB/min of source (~550 MB/s); 427 GB source
  -> ends ~00:20-00:21Z.
- free 306.40 GB (00:07:04) -> 278.04 GB (00:11:08).
### hold-watch 10: SSM 5cdf7a9c-db0a-444f-be6e-4394f9764d1a sent 00:09:52Z (armed).
### re-creatable clears: SSM df47c1f2-c015-4587-bee1-3b88446fc284 (pycache rm, journalctl --vacuum-size=200M, apt-get clean, pip cache).
### Re-creatable clears DONE (SSM df47c1f2-c015-4587-bee1-3b88446fc284, 00:11:39-00:11:47Z): 1,838 __pycache__ dirs removed
(0 remain), journald vacuum freed 1.3 GB, apt-get clean, /root/.cache/pip removed, no /tmp files older than 1 day.
/ free 277,767,213,056 -> 279,797,137,408 B (+2.03 GB).
### hold-watch 10 result (SSM 5cdf7a9c, 00:09:53-00:14:19Z, no trigger, nothing written)
- ROOT 14860 D balance_dirty_pages throughout 00:10:23-00:13:56; layer 218.5 (00:09:53) -> 223.2 GB (00:13:56): 1.2 GB/min (was 8).
- Native hash pass (stage bytes): 10.4 GB (00:10:23) -> 188.9 GB (00:13:56) = ~850 MB/s read; ends ~00:14:10Z (194 GB ledger),
  then the two small ledgers. nkids 16 (native 14929 alive).
- free 281.40 (00:09:53) -> 278.65 GB (00:13:56) (+2.0 GB from the clears at 00:11:47 inside that).
- Archive tar 96.4 (00:09:53) -> 140.1 GB (00:13:56): slowed to ~10 GB/min of archive under the native's read; ~173 GB of the 427 GB
  source consumed; ends ~00:23Z at the canary rate once the native read ends.
### hold-watch 11: SSM 94d912fb-1f50-4755-b660-81c6449d3cff sent 00:14:19Z (armed).
### hold-watch 11 result (SSM 94d912fb, 00:14:19-00:18:45Z, no trigger, nothing written)
- NATIVE STAGE COMPLETE: work/native-stage.json present from 00:15:20Z (native progress last stage root-ledger-verify-lifecycle,
  then stale). Native child still counted among the 16 children (join pending while the ROOT's legacy finalize runs).
- ROOT un-throttled from 00:14:19 (S futex_do_wait again): layer 224.86 (00:14:19) -> 256.97 GB (00:18:23): 7.9 GB/min.
  free 277.00 -> 244.61 GB (8.0 GB/min). Layer still needs ~240 GB -> ends ~00:48Z; free reaches zero ~00:49Z on this slope:
  the Monday root's removal (~427 GB) before ~00:45Z is required for the ROOT to finish.
- Archive tar 144.97 (00:14:19) -> 220.40 GB (00:18:23) = 18.5 GB/min of archive (~23 GB/min source); ~155 GB of source left
  -> ends ~00:25Z.
### hold-watch 12: SSM ee436927-8076-4974-87b9-babe34e4a820 sent 00:16:00Z (armed, overlaps 11).
### hold-watch 12 result (SSM ee436927, 00:16:00-00:20:25Z, no trigger, nothing written)
free 263.47 (00:16:00) -> 231.43 GB (00:20:03): 7.9 GB/min. layer 238.11 -> 270.15 GB (7.9 GB/min). Archive tar 159.27 -> 256.79 GB
(24 GB/min archive; ~110 GB of source left at 00:20 -> ends ~00:24Z). ROOT S/R 37.7%, 16 children; native-stage.json present.
### hold-watch 13: SSM 48c979e6-29ed-4127-9190-389e83e0410b sent 00:20:40Z (armed).
### Monday root tar.zst COMPLETE (log .logs/monday-root-tar.log; SSM 75d2faf1-8a43-4abb-b9e2-1866a2db4957 read it at 00:21:55Z)
- tar --totals: "Total bytes written: 427265044480 (398GiB, 450MiB/s)"; zstd_pipeline_rc=0; end 00:21:53Z (15 min 8 s).
- Archive: /opt/frankie-box/archive/monday-calculations/full-20211004-20260927-r1-48.tar.zst = 297,465,977,258 B (ratio 0.696 of
  the tar stream). / free 216,766,578,688 B (90% used) at 00:21:55; archive used 297.5 GB of 2.16 TB.
- Verification launched detached 00:21:55Z (log .logs/monday-root-verify.log): sha256sum -> <archive>.sha256 (pid 30603);
  zstd -dc | tar -tvf - -> <archive>.listing.txt (pids 30601/30599). Expected ~8 min.
### hold-watch 13 result (SSM 48c979e6, 00:20:41-00:25:05Z, no trigger, nothing written)
free 226.56 (00:20:41) -> 193.92 GB (00:24:44): 8.0 GB/min. layer 275.03 -> 307.67 GB (8.0 GB/min; ~190 GB to go -> ends ~00:48Z;
free zero ~00:48Z on this slope). tar ended between 00:21:41 and 00:22:12 (archive final 297,465,977,258 B). ROOT 38%, 16 children.
### hold-watch 14: SSM 8cda8532-3ecc-488e-9c64-d8e8e5baad7b sent 00:23:46Z (armed; samples carry the verify log tail).
### hold-watch 14 result (SSM 8cda8532, 00:23:46-00:28:10Z, no trigger, nothing written)
free 201.80 (00:23:46) -> 169.08 GB (00:27:49): 8.1 GB/min (zero ~00:48:40Z). layer 299.79 -> 332.51 GB (8.1 GB/min; ~165 GB to go
-> ends ~00:48Z). Verification still running at 00:28 (sha256 and the zstd -dc listing of the 297 GB archive; listing 73 lines
flushed so far). ROOT 38%, 16 children.
### hold-watch 15: SSM 0bcaa47d-3605-478f-91cf-027fee33d26b sent 00:27:26Z (armed).
### hold-watch 15 result (SSM 0bcaa47d, 00:27:26-00:31:50Z, no trigger, nothing written)
free 172.28 (00:27:26) -> 139.60 GB (00:31:29): 8.1 GB/min. layer 329.30 -> 362.00 GB (8.1 GB/min; ~135 GB to go -> ends ~00:48Z).
Verification still running (listing 73 lines flushed; sha256 not finished at 00:31). ROOT 38%, 16 children.
### Verify status 2 (SSM 82aceae0, 00:32:07Z): sha and listing still running (listing 85 lines), free 134.52 GB.

### GREG'S GUARD (verbatim: "If it gets within 10, you need to stop it and save data before it kills box") DEPLOYED
- SSM 123c46ce-4b89-4684-a614-779f339f701b, 00:33:26Z: /opt/frankie-box/archive/.logs/disk-guard.sh running detached (pid 32657),
  log .logs/disk-guard.log. Every 2 s: df -B1 / free; below 15,000,000,000 B -> kill -STOP every descendant of ROOT 14860
  (BFS list, deepest first: the native child's workers, the native child, the 15 layer encoders), then kill -STOP 14860; records
  time, pids, free before/after in the log and the pid list in .logs/disk-guard.frozen-pids; then exits. Ends by itself if ROOT
  exits. Nothing killed, nothing removed. free at start 123.57 GB (00:33:28Z) -> the guard would fire ~00:46:50Z on the 8.1 GB/min
  slope unless the Monday root is removed first. The CONT (ROOT first, then children) is this role's step after the removal
  when free > 100 GB.
### hold-watch 16: SSM fb1266b9-7a6f-452f-bb6e-945d26c91738 sent 00:34:03Z (armed; a first send failed on the SSM 100-char comment
limit, nothing ran).
### hold-watch 16 result (SSM fb1266b9, 00:34:03-00:38:30Z, no trigger, nothing written)
free 118.86 (00:34:03) -> 86.03 GB (00:38:07): 8.1 GB/min. layer 382.72 -> 415.55 GB (8.1 GB/min; ~80 GB to go -> ends ~00:48Z).
Guard alive (1), not fired; guard log: 83.55 GB at 00:38:25. Verification: listing 282 lines from 00:36:05 (inside big files),
sha256 not finished at 00:38 (one stream each on the archive volume, ~16 min so far).
### hold-watch 17: SSM bc43ec7c-ec84-4c6f-bea6-2bc3e25f3dcd sent 00:37:24Z (armed).
### Gated Monday removal waiter: SSM bc571e9f-a2b5-4c90-97db-14dd6dba75ee sent 00:35:53Z (waits <= 250 s for sha_rc/list_rc, then
the full checks: sha_rc=0, list_rc=0/0, entries 604, files 500, byte sum, names diff 0, 3 largest present, open fds 0 -> then
receipts copy, rm -rf, symlink, README, df, and CONT of a frozen tree when free > 100 GB; refuses on any mismatch).
### Greg (relayed 00:3xZ): "We need to put CPUs on that part too." -> the remaining items are archived as one tar.zst per directory
in parallel on idle native-half CPU pairs (measured < 10% busy, never CPUs 0/1/17), each verified independently (sha256,
zstd -dc | tar -tvf listing, entries/files/bytes/names vs the source, open fds 0) and removed per the rule as each verifies
(symlink + README at the old path). Lesson recorded below for the archive policy.
### Parallel archive batch STARTED (SSM a4d084d2-8dde-40b9-9cd8-8cf062dcd574, 00:40:2xZ)
- CPU busy% (2 s /proc/stat): 0 48.7 (ROOT), 1 43.4, 2 10.0, 3 0.5, 4 0, 5 0, 6 6.6, 7 9.0, 8 58.2, 9-15 93-100 (encoders),
  16 3.0, 17 5.6, 18 19.2, 19 8.0, 20 0, 21 5.6, 22 94.9, 23 26.1, 24-31 94-100 (encoders). Idle pairs with both siblings idle:
  3/19, 4/20, 5/21 -> 3 workers (taskset -c pair, nice 19, ionice idle, zstd -T2 -3), a shared job list under flock.
- 50 jobs (one tar.zst per directory; biggest first inside each class): 17 ingest-* dirs other than 20231018 (incl. the small
  canaries and ingest-stack-measure), experiment-teacher-rows, 17 days-2026092x/0930 roots, the retired a1 attempt, 7 non-referenced
  code checkouts and 7 transfer-* tarball dirs (c9bf631, 98579cea, 275367fe, 18cbc5a4 and their transfer-* excluded).
- Per job: tar | zstd -> <archive>/<class>/<name>.tar.zst; sha256sum -> .sha256; zstd -dc | tar -tvf -> .listing.txt; checks:
  listrc 0/0, entries, files, byte sum, sorted names identical, open fds 0; pass -> rm -rf source, symlink to the archive at the
  old path, <name>.ARCHIVED.README.txt beside it; fail -> source kept, logged. Log: archive/.logs/batch.log (one line per item).
- First three done by 00:40:27 (canary 1790056161 151 MB, ingest-20211005 empty, ingest-20211006 35 MB): all VERIFIED+REMOVED.
- / free 67.39 GB at 00:40:27Z (guard fires at 15 GB, ~00:47Z).
### hold-watch 17 result (SSM bc43ec7c, 00:37:25-00:41:50Z, no trigger, nothing written)
free 91.61 (00:37:25) -> 59.30 GB (00:41:28): 8.1 GB/min (the batch's first removals are small). layer 409.97 -> 442.77 GB
(8.1 GB/min; ~55 GB to go if the layer equals the spool -> ~00:48Z). Guard alive, not fired (59.69 GB at 00:41:25). Verification
still running at 00:41 (listing 343 lines at 00:40:03). ROOT 38.8%, 16 children.
### Monday waiter 1 (SSM bc571e9f) ended 00:40:03Z: verification still running; nothing changed. Waiter 2: SSM
46c1aa09-053d-4e7c-a268-b5ee23578cad sent 00:41:44Z (same gated script).
### hold-watch 18: SSM 7af2485d-2dbd-4871-bb3d-aeebb708fa92 sent 00:42:37Z (armed; samples carry batch_done count).
### Batch progress (archive/.logs/batch.log, read 00:45:49Z) and the ONE-PASS switch (Greg: "Is it doing more than one pass?")
- VERIFIED+REMOVED so far (18): the 4 ingest-20211004 canaries, ingest-20211005, -20211006, ingest-stack-measure, ingest-20211004-
  ingest-1790057801 (23.69 GB -> 18.39 GB), ingest-20221011 (10.21 -> 8.07), -20221012 (9.21 -> 7.37), -20221018 (11.35 -> 8.95),
  -20221019 (9.12 -> 7.22), -20231003 (10.27 -> 7.83), -20231004 (11.73 -> 9.13), -20231010 (11.73 -> 8.95), -20231011 (14.78 -> 11.42),
  -20231017 (10.26 -> 7.91), days-20260929-3-20211005-a1 (0.14 GB). Each: entries/files/bytes equal, names identical, listrc 0/0,
  open 0, sha256 recorded, symlink + README at the old path.
- / free 59.3 GB (00:41:28) -> 152.21 GB (00:45:49): the ingest removals (~122 GB) outran the layer write; the 15 GB guard will
  not fire on the current slope (the layer needs ~50 GB more).
- SSM 39c5bf88-dca6-4314-886d-eb5d50f14427 00:45:47Z: the 29 remaining jobs moved (under the list lock) to batch-jobs2.txt; the old
  workers end after their in-flight job; three one-pass workers (batch-worker2.sh, pairs 3/19 4/20 5/21) started: per directory
  `tar -cvvf - <dir> 2> <name>.listing.src.txt | zstd -T2 -3 | tee >(sha256sum > <name>.sha256) > <name>.tar.zst` (sha256 on the
  compressed write stream, listing from tar's own -vv), then exactly ONE read-back `zstd -dc | tar -tvf - > .listing.txt`, compared
  with the write-time listing and the source metadata (entries, files, byte sum, size+name pairs); no separate sha256 read.
  In-flight old-style jobs (two reads) finish as started. The Monday verification is not restarted (its sha256 pass has run; the
  decompress-list pass is the one still running).

## ARCHIVE-POLICY LESSON (for the record and the runbook)
1. Archive big roots as per-subdirectory archives (e.g. one per top-level subdir of a ROOT like the Monday root's work/derived/
   .projection-v2, .digest-*, .rows, ...), so compression AND verification run on many CPUs at once; a single 427 GB stream took
   15 min to write and > 25 min to verify on one core each, while 3 pinned workers moved ~120 GB of ingests in 5 min.
2. Compute the sha256 on the WRITE stream (tee on the compressed stream) and capture the listing from tar's own -vv while creating;
   then exactly ONE read-back pass per archive (zstd -dc | tar -tvf, compared with the write-time listing); never a second read,
   never a separate sha256 pass.
3. Use zstd -T0 (all idle threads) when the lane is idle; -T2 per worker when sharing a lane with a running stage.
4. Pin archive work to measured-idle CPU pairs (siblings N/N+16), never the running stage's cores; nice 19. ionice has no effect
   under the NVMe 'none' scheduler, so disk contention must be managed by concurrency, not priority: a heavy concurrent reader
   (the native hash pass at ~800 MB/s) throttled the ROOT's layer write into balance_dirty_pages for ~4 min.
5. Keep a disk guard (SIGSTOP of the writer's tree at a floor) armed whenever a stage writes a file comparable to the free space.

## MONDAY ROOT REMOVED (Greg's decision "Let's just stop it now and empty it"; SSM e6344593-0955-421e-8c49-474f39b5c748, 00:47:31-00:48:3xZ)
- Decompress-and-list pass stopped (TERM to zstd -dc 30601, tar -tvf 30602, wrapper 30599) after 422 of 604 listing entries
  (every frame it read decoded clean); partial listing kept beside the archive as .listing.PARTIAL-stopped-by-greg-0047xx.txt.
  The sha256sum pass (one read, pid 30603) was still running and is left to finish; it writes <archive>.sha256 by itself.
- Accepted checks (written to <archive>.VERIFICATION-NOTE.txt): tar --totals 427,265,044,480 B written (source: 500 files / 604
  entries / 427,264,335,065 file bytes + tar headers/padding); zstd pipeline rc 0 (XXH64 frame checksums); open fds 0; archive
  297,465,977,258 B. NOT completed: the full entry-by-entry listing comparison (Greg's decision).
- Receipts (< 2 MB each): 354 files, 5,001,216 B copied to monday-calculations/full-20211004-20260927-r1-48.receipts/.
- rm -rf /opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48 at 00:48:05Z: 427,266,150,400 B freed; symlink
  full-20211004-20260927-r1-48 -> the archive tar.zst; full-20211004-20260927-r1-48.ARCHIVED.README.txt beside it.
- df after: / 579,471,753,216 B free (73% used); archive 1,747,240,435,712 B free (20% used, 416 GB).
- Guard: not fired (free never went below 59 GB; min seen 59.30 GB at 00:41:28), still running (pid 32657). ROOT 14860 alive,
  layer 472.04 GB at 00:48:3x and growing; nothing of a2 touched.
### One-pass worker defect (mine) and fix
- batch-worker2.sh's `exit ${PIPESTATUS[0]}${PIPESTATUS[1]}` made rc "0" (exit 00 = 0) and the check compared with "00": every
  one-pass job logged "TAR/ZSTD FAILED rc=0" and was skipped after its archive was written (sources kept, archives unverified; 4
  such by 00:47:52: days-20260930-1-20231004-a2, -20231003-a1, -20221019-a1, e2e-20231018-a1 attempt). Fixed in batch-worker3.sh
  (pipestatus to a side file, [ "$rc" = 0 ]); the affected archives deleted and their jobs re-queued with the rest (batch-jobs3.txt).
### hold-watch 18 result (SSM 7af2485d, 00:42:37-00:47:05Z, no trigger, nothing written)
- THE LAYER FILE IS WRITTEN: legacy_book_imbalance.json.pending grew 452.00 (00:42:37) -> 472,040,420,230 B at 00:45:10 and stayed
  there (472.04 GB final = the JSON form of the 496.7 GB frames spool); ROOT then in D rq_qos_wait / folio_wait_bit_common (the
  fsync of 472 GB), R again at 00:46:41. Next in ROOT: the remaining layer(s), legacy-stage.json, the native join/reuse, then
  root-projection (the save trigger).
- free 69.42 (00:42:37) -> 152.21 GB (00:45:40) as the batch removed the ingests; guard never fired.
- batch_done 8 -> 18 in the window; the one-pass rc bug then skipped 6 days roots (re-queued, see above).
### hold-watch 19: SSM 3224aab2-3292-4b44-963f-fa966e277de7 sent 00:50:01Z (armed; the layer stat now matches .json or .pending).
### Fixed batch (worker3, SSM 8c38301d-32b9-49e9-866a-c44e020446c6, 00:48:59Z): 32 jobs; code checkouts 901bc0d2, 0c478e07,
910ef886, 94f0d073, 9e7a7d90 VERIFIED+REMOVED by 00:49:09 (entries/files/bytes w=r=src, size+name diff 0, listrc 0/0). / free
587.93 GB at 00:49:19Z. NOTE: 1727bb4f (a2's rebind-history checkout, not referenced by a2's JSON) is in the list per the
coordinator's exclusion set (c9bf631, 98579cea, 275367fe, 18cbc5a4 only); its archive is restorable.
### Report to the coordinator at 00:50Z was refused by the harness ("Only the auto-mode classifier can allow SubagentHandback");
the content is in this record (MONDAY ROOT REMOVED section) and is retried.
### hold-watch 19 result (SSM 3224aab2, 00:50:02-00:54:30Z, no trigger, nothing written)
- free 590.02 (00:50:02) -> 611.57 GB (00:52:03) and flat after (batch finished its removals). batch_done 27 -> 41.
- ROOT 14860 R ~39% since 00:46:41 with the layer file still the .pending name at 472,040,420,230 B (mtime 00:45:07): the parent is
  hashing the written layer (boss_session.py:2697 `**witness(path)` after write_layer_json: sha256 of 472 GB on one core, ~16 min,
  -> ~01:01Z), then the structures layer, then legacy-stage.json (_check_spool_claims + witness of every spool incl. the 497 GB
  frames spool: another ~16 min), then the native join/reuse and root-projection. Trigger expected ~01:20-01:35Z.
### hold-watch 20: SSM b5695161-cb91-4724-affe-c43c2a41cde2 sent 00:52:14Z (armed).

### Batch COMPLETE (archive/.logs/batch.log read 00:55:51Z, SSM 1f9f4965-7931-4d13-a09e-e1e72151a516); Monday sha256 landed
- Monday archive sha256 (sha_rc=0 at 00:48:26Z, one read): 6eae842c61cf6e0cc8dee0bb7484ec5388ff57c11d4b7b58625f4a1d90f1f662
  /opt/frankie-box/archive/monday-calculations/full-20211004-20260927-r1-48.tar.zst (297,465,977,258 B). The stopped list pass
  logged "tar: Unexpected EOF in archive" (expected: it was killed) in the verify log.
- Workers 0 alive, jobs 0. / free 636,707,545,088 B (71% used) at 00:55:51Z; archive used 438.3 GB (monday 297.5, work 128.9,
  code 12.0).
- VERIFIED+REMOVED (41): 17 ingest-* (incl. canaries, stack-measure), experiment-teacher-rows (25.14 GB -> 24.86 GB, 6,066 entries),
  days-20260929-3-20211005-a1, days-20260930-1-{20211020-a1, 20221011-a1, 20221011-a2, 20221012-a1, 20221018-a1, 20221018-a2,
  20231004-a1, 20231004-a2}, e2e-20231018-a1-20231018-a1 (3.62 GB -> 118 MB), code checkouts 0c478e07, 1727bb4f, 901bc0d2, 910ef886,
  94f0d073, 9e7a7d90, ad46ca06 (~1.42 GB -> ~1.19 GB each), transfer-* for those 7.
- VERIFY FAILED, SOURCE KEPT (8 days roots): days-20260929-3-{20211005-a2, 20211006-a1, 20211012-a1, 20211013-a1, 20221004-a1,
  20221005-a1}, days-20260930-1-{20221019-a1, 20231003-a1}: write and read listings agree (w=r), but the source has 88 files where
  the listings show 87 regular entries and the byte sums differ by 60-100 MB: the signature of ONE HARD LINK per root (tar stores
  the second name as type 'h' with size 0; my filter counted '^-' only). Re-check from the EXISTING listings (no new read):
  names incl. 'h' entries vs find -type f, bytes over unique inodes, hard-link counts equal -> remove if it passes (SSM below).
- experiment-teacher-rows first attempt at 00:50:13 failed with listrc 1/2 and an empty archive name: that was the killed in-flight
  job of the stopped worker2 (its partial archive was deleted and the job re-queued); the re-run verified and removed it at 00:55:21.
### hold-watch 20 result (SSM b5695161, 00:52:15-00:56:40Z, no trigger, nothing written)
- ROOT 14860 alternating R / D folio_wait_bit_common at 39-40% (hashing the 472 GB layer); the layer was PUBLISHED as
  work/derived/legacy_book_imbalance.json (472,040,420,230 B) at ~00:56:32Z (directory mtime; the .pending name gone). Next in
  ROOT: legacy_structure_observables (structures spool), legacy-stage.json (spool witnesses), native join/reuse, root-projection.
- free 611.57 -> 636.71 GB (00:55:47, teacher rows removed). batch_done 42.
### hold-watch 21: SSM 24daf193-7d85-41fd-be62-1aef5b09d6ef sent 00:56:48Z (armed; samples show ROOT's open data fd).
### Days-roots recheck (SSM fb61a9a6-db81-4ac3-a4a9-1dbe68145659, 00:57:11Z, read-only on the existing listings, no new read):
all 8 show exactly ONE hard-link entry in the tar listing (work/derived/.digest-*/digest.pending "link to" work/derivation-
digest-full.md, 0 B as tar stores a second name), names 88 (write) = 88 (read) = 88 (source find -type f), bytes write = read =
source over unique inodes (e.g. 11,089,687,134 for 20211005-a2), listrc 0/0, open fds 0. They were KEPT only because my condition
compared the 1 'h' entry with find's 2 linked names; corrected to (linked names - linked inodes) = 1 and re-run (SSM below).
### Days roots REMOVED after the corrected recheck (SSM 570d9269-f725-4c4f-83ed-2e1c7b048c6b, 00:58:07-00:58:08Z)
All 8 passed (names w88/r88/src88 diff 0/0; bytes write = read = source over unique inodes; 1 hard-link entry = 2 linked names -
1 inode; listrc 0/0; open 0): days-20260929-3-20211005-a2 (du 11,090,046,976 -> 1,307,401,025), -20211006-a1 (12,038,934,528 ->
1,421,127,703), -20211012-a1 (7,895,777,280 -> 923,751,670), -20211013-a1 (7,216,570,368 -> 842,784,439), -20221004-a1
(8,913,649,664 -> 1,052,181,552), -20221005-a1 (7,182,528,512 -> 847,865,728), days-20260930-1-20221019-a1 (6,384,652,288 ->
751,637,074), -20231003-a1 (4,631,429,120 -> 546,808,676). Symlink + README at each old path.
/ free 702,060,810,240 B (702.1 GB) at 00:58:08Z. experiment-roots now holds only a2's attempt (plus 20 symlinks).

## FINAL TABLE FOR GREG: everything moved off / (archive volume vol-004b68c077be09cc9 at /opt/frankie-box/archive, 2 TiB gp3)
Format: old path -> archive file | source bytes (du) -> archive bytes | verification | at (UTC, 2026-10-08)
Verification keys: T = two-pass (sha256 of the archive read + zstd -dc|tar -tvf listing; entries/files/bytes/names equal; open 0);
O = one-pass (sha256 on the write stream, tar -vv write listing, ONE read-back zstd -dc|tar -tvf; entries/files/bytes/size+name
pairs equal between write, read and source; open 0); OH = O with the hard-link aware recheck from the same listings.
Every old path is now a symlink to its archive plus <name>.ARCHIVED.README.txt beside it; every archive has .sha256 (+ .listing*).

monday-calculations/full-20211004-20260927-r1-48 -> archive/monday-calculations/full-20211004-20260927-r1-48.tar.zst
  | 427,266,150,400 -> 297,465,977,258 | tar --totals 427,265,044,480 B, zstd rc 0 (XXH64 frames), sha256 6eae842c61cf6e0cc8dee0bb74
  84ec5388ff57c11d4b7b58625f4a1d90f1f662 (one read, done 00:48:26), list pass stopped by Greg at 422/604 entries (all clean), open 0;
  354 receipt files kept in full-20211004-20260927-r1-48.receipts/ | removed 00:48:05
work/ingest-20211004-ingest-1790057801 -> archive/work/... | 23,687,516,160 -> 18,386,938,852 | T | 00:43:34
work/ingest-20231011-gh-36571235912-1 | 14,776,078,336 -> 11,424,784,044 | T | 00:45:36
work/ingest-20231010-gh-36571235912-1 | 11,729,088,512 -> 8,952,453,656 | T | 00:44:54
work/ingest-20231004-gh-36571235912-1 | 11,726,622,720 -> 9,126,568,396 | T | 00:44:18
work/ingest-20221018-gh-36571235912-1 | 11,346,653,184 -> 8,948,658,246 | T | 00:43:00
work/ingest-20231003-gh-36571235912-1 | 10,265,812,992 -> 7,831,366,294 | T | 00:43:57
work/ingest-20231017-gh-36571235912-1 | 10,259,763,200 -> 7,910,688,913 | T | 00:45:26
work/ingest-20221011-gh-36571235912-1 | 10,212,098,048 -> 8,069,804,030 | T | 00:41:43
work/ingest-20221012-gh-36571235912-1 | 9,211,707,392 -> 7,366,061,070 | T | 00:41:37
work/ingest-20221019-gh-36571235912-1 | 9,121,996,800 -> 7,222,287,697 | T | 00:42:48
work/ingest-20211004-canary-1790045552 | 151,224,320 -> 121,288,624 | T | 00:40:27
work/ingest-20211004-canary-1790056161 | 151,216,128 -> 120,347,536 | T | 00:40:27
work/ingest-20211004-canary-1790057625 | 143,011,840 -> 112,103,378 | T | 00:40:27
work/ingest-20211006-ingest-1790680900 | 35,344,384 -> 27,653,515 | T | 00:40:27
work/ingest-stack-measure | 102,400 -> 5,965 | T | 00:44:54
work/ingest-20211005-ingest-1790672828 (empty) | 4,096 -> 101 | T | 00:40:27
work/ingest-20211004-canary-1790045368 (empty) | 4,096 -> 106 | T | 00:40:25
work/experiment-teacher-rows | 25,141,534,720 -> 24,863,644,343 (6,066 entries) | O | 00:55:21
work/experiment-roots/days-20260929-3-20211005-a1 | 136,249,344 -> 7,257,845 | T | 00:45:26
work/experiment-roots/days-20260929-3-20211005-a2 | 11,090,046,976 -> 1,307,401,025 | OH | 00:58:07
work/experiment-roots/days-20260929-3-20211006-a1 | 12,038,934,528 -> 1,421,127,703 | OH | 00:58:07
work/experiment-roots/days-20260929-3-20211012-a1 | 7,895,777,280 -> 923,751,670 | OH | 00:58:08
work/experiment-roots/days-20260929-3-20211013-a1 | 7,216,570,368 -> 842,784,439 | OH | 00:58:08
work/experiment-roots/days-20260929-3-20221004-a1 | 8,913,649,664 -> 1,052,181,552 | OH | 00:58:08
work/experiment-roots/days-20260929-3-20221005-a1 | 7,182,528,512 -> 847,865,728 | OH | 00:58:08
work/experiment-roots/days-20260930-1-20221019-a1 | 6,384,652,288 -> 751,637,074 | OH | 00:58:08
work/experiment-roots/days-20260930-1-20231003-a1 | 4,631,429,120 -> 546,808,676 | OH | 00:58:08
work/experiment-roots/days-20260930-1-20221018-a2 | 5,748,908,032 -> 196,944,310 | O | 00:50:25
work/experiment-roots/days-20260930-1-20221011-a2 | 5,352,325,120 -> 183,566,028 | O | 00:50:12
work/experiment-roots/days-20260930-1-20221018-a1 | 772,042,752 -> 40,729,262 | O | 00:50:03
work/experiment-roots/days-20260930-1-20211020-a1 | 715,980,800 -> 37,621,063 | O | 00:49:48
work/experiment-roots/days-20260930-1-20221011-a1 | 710,053,888 -> 37,860,470 | O | 00:49:51
work/experiment-roots/days-20260930-1-20221012-a1 | 664,838,144 -> 35,208,317 | O | 00:49:59
work/experiment-roots/days-20260930-1-20231004-a1 | 532,979,712 -> 26,742,305 | O | 00:50:27
work/experiment-roots/days-20260930-1-20231004-a2 | 486,518,784 -> 24,291,964 | O | 00:50:29
work/experiment-roots/e2e-20231018-a1-20231018-a1 (retired a1 attempt) | 3,620,134,912 -> 117,974,819 | O | 00:50:38
code/0c478e07...-37689106651-1 | 1,422,811,136 -> 1,193,774,351 | O | 00:49:04
code/1727bb4f...-37686893730-1 | 1,422,708,736 -> 1,193,797,547 | O | 00:49:02   (a2 rebind-history checkout; unreferenced by a2's JSON)
code/901bc0d2...-37686420496-1 | 1,422,577,664 -> 1,193,667,942 | O | 00:49:02
code/910ef886...-37673131619-1 | 1,422,327,808 -> 1,193,431,551 | O | 00:49:06
code/94f0d073...-36674311691-1 | 1,349,509,120 -> 1,179,541,449 | O | 00:49:06
code/9e7a7d90...-37672447342-1 | 1,422,331,904 -> 1,193,528,460 | O | 00:49:09
code/ad46ca06...-37671852196-1 | 1,422,319,616 -> 1,193,449,009 | O | 00:51:48
code/transfer-{0c478e07, 1727bb4f, 901bc0d2, 910ef886, 9e7a7d90, ad46ca06} | ~601 MB each -> ~600.5 MB each | O | 00:51:24-00:51:36
code/transfer-94f0d073 | 12,288 -> 448 | O | 00:51:31
Re-creatable cleared (no copy): 1,838 __pycache__ dirs (331 MB), journald vacuum (1.3 GB), apt/pip caches (261 MB) | 00:11:47.
Kept on /, untouched: day-external (10.2 GB, referenced by a2's external.json); code c9bf631 (a2/worker), 98579cea (a2 binding),
275367fe and 18cbc5a4 (queue history) + their transfer-*; a2's attempt (incl. the 66 GB pre-save ledger copy); ingest-20231018.
Totals: ~700 GB moved off / (427.3 Monday + ~122 ingests + ~84 days roots + 25.1 teacher rows + 3.6 a1 + ~14.4 code),
archive volume used ~438 GB. / free 702.06 GB at 00:58:08Z (was 59.3 GB at its minimum, 00:41:28Z).
### hold-watch 21 result (SSM 24daf193, 00:56:48-01:01:15Z, no trigger, nothing written)
ROOT 14860 R 40.5-42.2%, 16 children, its one data fd = work/derived/legacy_book_imbalance.json (published 472,040,420,230 B):
the post-write witness (sha256 of 472 GB on the ROOT core, boss_session.py:2697), expected to end ~01:12Z; then the structures
layer, legacy-stage.json (every spool witnessed again, frames 497 GB ~16 min), native join/reuse, root-projection = the trigger,
now expected ~01:30-01:45Z. free 636.71 -> 702.06 GB (00:58:19, the 8 days roots) and flat. No native-stage changes; ls=n dj=n.
### hold-watch 22: SSM 023ce481-5216-45fa-b3c3-8265ff7e995c sent 01:00:29Z (armed).
### hold-watch 22 result (SSM 023ce481, 01:00:30-01:05:00Z, no trigger, nothing written)
- ROOT log 01:02:49Z: "layer legacy_book_imbalance.json written in 4861.4 s (spools encoded on pinned lane CPUs 9-15,24-31)":
  the write_layer_json call returned (23:41:47 -> 01:02:49, 81 min for 472 GB). The 15 encoders exited (nkids 16 -> 1 at 01:03:02;
  the one child = native 14929, joined later). ROOT R 43% with its data fd still on legacy_book_imbalance.json = the witness hash
  (boss_session.py:2697) from 01:02:49, ~16 min -> ~01:19Z; then legacy_structure_observables (structures spool), legacy-stage.json
  (spool witnesses incl. frames 497 GB), native join/reuse, root-projection -> trigger ~01:40-01:50Z.
- free 702.06 GB flat. Guard still running (not fired).
### hold-watch 23: SSM c0f1cd8c-19d3-4a80-8f07-6eaf0c0b26e0 sent 01:03:05Z (armed).
### hold-watch 23 result (SSM c0f1cd8c, 01:03:05-01:07:30Z, no trigger, nothing written)
ROOT R 43-44%, 1 child (native 14929), data fd legacy_book_imbalance.json (witness hash in progress). free 702.06 GB flat. ls=n dj=n.
### hold-watch 24: SSM 0d142fb5-7e8c-4453-a0ae-4493cd12e0f8 sent 01:06:34Z (armed).
### hold-watch 24 result (SSM 0d142fb5, 01:06:35-01:11:00Z, no trigger, nothing written)
- The 472 GB layer witness ended ~01:10 (7 min: page cache helped). 01:10:07 ROOT Sl with 14 encoders again (nkids 15) writing
  legacy_structure_observables.json.pending; log 01:10:14Z "layer legacy_structure_observables.json written in 9.4 s"; the other
  layer files (121 B placeholders: not derived in this ROOT configuration) written 01:10:14. 01:10:38: nkids 0 (the native child
  14929 has exited; the join is immediate), ROOT R reading frames.jsonl = the legacy-stage.json spool witnesses (frames 497 GB:
  ~8-16 min -> ~01:20-01:27Z), then native-stage.json reuse (artifact witnesses, the 194 GB ledger: ~3-5 min), the 3026 check,
  root-projection = TRIGGER, now expected ~01:25-01:40Z. free 701.12 GB (01:10:38).
### hold-watch 25: SSM 99df2460-bb9f-4d35-b9cd-e7b0fd5a4fda sent 01:09:15Z (armed).
### hold-watch 25 result (SSM 99df2460, 01:09:15-01:13:40Z, no trigger, nothing written)
ROOT R 45-46%, 0 children (native child exited), data fd frames.jsonl from 01:10:16 (legacy-stage.json spool witnesses; frames
496.7 GB at the volume's read rate ~1 GB/s -> ~01:19-01:27Z). free 701.12 GB flat. ls=n dj=n.
### hold-watch 26: SSM 6ca5083f-d04d-473d-9369-e8064134cc41 sent 01:12:48Z (armed; the sending call hit the tool's 60 s wall after
the SendCommand succeeded, confirmed by ListCommands).
### hold-watch 26 result (SSM 6ca5083f, 01:12:48-01:17:15Z, no trigger, nothing written)
ROOT R 46-47%, 0 children, data fd frames.jsonl throughout (spool witness for legacy-stage.json, started 01:10:16). free 701.12 GB.
### hold-watch 27: SSM 7e7f04ae-3ad0-4746-ae46-9fdbc4251f83 sent 01:15:19Z (armed).

## Session 5b (after the container restart)
Box-operator agent re-spawned 01:19Z (the previous one was lost in a container restart ~01:18Z). Same run, same ids, same rules
(read-only SSM except the queue save and the KeepRunning tag). Branch untouched, no repo edit.

### hold-watch 27 result (SSM 7e7f04ae, 01:15:19-01:19:4xZ, read back 01:27Z: NO trigger, nothing written by it)
Samples 01:15:19-01:19:22: stage root-legacy-finalize, ROOT R 46.9-48.0%, 0 children, data fd frames.jsonl until 01:17:21, then
native-stage.lock (ls=Y from 01:17:51: legacy-stage.json published 01:17; the native-stage reuse/witness step followed). free
701.12 GB flat. Log 01:17:50Z "bedrock: the pinned traversal (2ebb8ce8) on 771787 INPUT records for 44 layers".

### UNARMED GAP 01:19:4xZ-01:25:54Z, and the save marker LANDED inside it from another actor
- ROOT log 01:20:52Z: "bedrock: completed native results reused in place; no traversal or finalization replay" (boss_session.py:3077
  note; the 3026 save check evaluated False right after it: ROOT continued into the projection).
- save/e2e-20231018-a2-20231018.save-request.json EXISTS: mtime 01:20:55.888Z, 498 B, "by": "dispatch save", requested_utc
  2026-10-08T01:20:55Z, schema FRANKIE_QUEUE_SAVE_REQUEST_V1, attempt e2e-20231018-a2-20231018-a1, booking
  day-run-20231018-day_slot_root-1791402822-3111, cpus 0-31. root.json's a2 entry (state running, where box-slot) carries the same
  save_request with identity sha256 e5c639e0...2b5b. NOT placed by hold-watch 27 (its output shows no TRIGGER) nor by this role
  (first send 01:25:54Z): the queue's ACTION=save was run by someone else (the parent session, presumably) 3 s after the reuse
  note, i.e. exactly in the planned window (after 3026 evaluated False, before the ROOT exit). Mechanism per the code analysis
  above: ROOT finishes projection/digest/receipt, then experiment_root.py:131 raises TeacherSaved -> exit 75 -> the worker records
  the entry 'saved' with the booking retained; no teacher.
- Stage at 01:26:20Z: root-projection-member (progress.json); ROOT 14860 S, 15 children (projection workers), worker 14824 S; no
  teacher/classroom process; native-stage.json (00:15) and legacy-stage.json (01:17, 59,810 B) present; derive.json absent; no
  calculations-receipt.json yet. free 678.05 GB (69% used) at 01:26:20 (686.66 at 01:24:30, 681.90 at 01:25:30 per the guard log:
  the projection writes ~4.8 GB/min).
### hold-watch 28 (SSM 6edac15e-a490-481c-bda6-c9de2eeb2191, sent 01:25:54Z, this role): fired at once on stage
root-projection-member; the wrapper (env HOME=/root CODE_ROOT=<c9bf631 checkout> MARKETS_SHA=c9bf631e88... ACTION=save
RUN=e2e-20231018-a2 DAY=20231018 bash deploy/aws/box/frankie_box_frankie_queue.sh) returned rc=1 with "a save request stands
already: .../save/e2e-20231018-a2-20231018.save-request.json" (create-only; nothing changed). Confirms the marker is the queue's own.
### Read-only probes 5b-1 (SSM b99599bf, 01:26:20Z) and 5b-2 (SSM b67fa633, 01:27:04Z)
- Monday root removal CONFIRMED: /opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48 is a symlink (00:48) ->
  /opt/frankie-box/archive/monday-calculations/full-20211004-20260927-r1-48.tar.zst (297,465,977,258 B, 00:21); beside it
  full-20211004-20260927-r1-48.ARCHIVED.README.txt (887 B) and full-20211004-20260927-r1-48.receipts/ (00:47). In the archive dir:
  the tar.zst, .sha256 (148 B, 00:48), .VERIFICATION-NOTE.txt (1,213 B), .listing.PARTIAL-stopped-by-greg-004733.txt (67,327 B).
- Archive batch: COMPLETE. batch.log's last four lines are the 00:58:08 [recheck] VERIFIED+REMOVED entries (days-20260929-3-
  20221004-a1, -20221005-a1, days-20260930-1-20221019-a1, -20231003-a1; free_now 702,060,810,240 at the last). batch-worker
  processes alive: 0. No zstd/tar/rsync/sha256sum process running.
- Disk guard: still running (pid 32657, /bin/sh /opt/frankie-box/archive/.logs/disk-guard.sh), not fired; log 01:24:30
  free=686,661,926,912; 01:25:30 free=681,898,921,984. It exits by itself when ROOT 14860 exits.
- Instance tags at 01:28Z: KeepRunning=true (reason "ccode_step8: a2 resumed on c9bf631 22:43:48Z ... re-set after the saved
  worker end cleared it"), KeepRunningPolicy, Name frankie-ingest32-20260917. The worker's end after the save WILL clear it
  (X.keep_running(run, False)); re-set is this role's authorized write once the entry reads 'saved'. Next idle-guard cron 06:17Z.
- Nothing else in flight on the box.
### monitor 29 (SSM f0e9b2a1-ed2e-48b9-9262-606506502e1d, 01:28:55-01:33:20Z, read-only; CONT rule armed, not needed)
The role of the rounds changed: the save marker stands, so each round now watches for the ROOT exit and the entry's 'saved' state.
- stage root-projection-member 01:28:55-01:31:25; root-projection-lifecycle 01:31:56; root-projection-publication from 01:32:26.
  ROOT 14860 S with 15 projection children throughout; worker 14824 S; no teacher/classroom process; derive.json absent; no
  calculations-receipt.json; save/ holds the one standing marker; root.json a2 entry: state running, save_request recorded.
- free 666.00 GB (01:28:55) -> 652.37 (01:31:56) at ~4.6 GB/min, then the publication: 617.02 (01:32:26) -> 603.35 GB (01:32:56):
  ~27 GB/min. Guard alive (free 611.68 GB at 01:32:31), not fired.
- ROOT log 01:33:06Z: "bedrock: 43/44 layers derived by the pinned traversal on 583688 groups (86399.5 s of rows; the candidate
  lane needs 900 s); sections 4.2 derived (28 rows), 4.4 derived (1167376 rows)". Next: root-digest, root-derived, the receipt,
  then experiment_root.py:131 -> exit 75 under the standing marker.
- Processes on c9bf631: 14824 (queue worker), 14858 (frankie_box_cores), 14860 (ROOT). Nothing else frankie.
### monitor 30 (SSM 3d0cc3a1-f8b7-4e55-b9ee-33e4ec84b822, 01:34:30-01:38:55Z, read-only; CONT rule armed, not needed)
- stage root-digest from the first sample (01:34:30) through 01:38:31; ROOT 14860 S with 31 children (the digest's pinned lane
  workers), its data fd work/derived/.digest-bb89b168639a4b768e3a21df0f79ab04/families.sqlite; work/derive.json PRESENT (the
  projection publication is done); no calculations-receipt.json yet; worker 14824 S; no teacher/classroom process.
- free flat at 603.21 GB throughout (the digest's early phase reads; the big digest writes (sources.sqlite, prepare/merge sqlite
  on the Monday root were 82 + 43 + 63 GB) are still ahead). Guard alive, not fired. Marker standing; a2 entry running + save_request.
- The digest's duration on this day is unmeasured (the drop-in says so); the Monday root's digest ran for hours on a 2.0M-record
  day; a2 is 771,787 records. The ROOT exit (-> 'saved') may land after this role's 02:30Z report deadline.
### monitor 31 (SSM 9360f63b-5707-4824-8633-bbd2a41e4cda, 01:43:39-01:48:04Z, read-only; CONT rule armed, not needed)
- stage root-digest throughout; progress.json: phase "deriving", completed 0, total null, percent null (the stage-local counter is
  not a completion measure, as the 09-27 audit noted), at 01:33:06. ROOT S, 31 children, fd families.sqlite (12,288 B, 01:33).
- Digest dir work/derived/.digest-bb89b168639a4b768e3a21df0f79ab04/: families.sqlite, table-0000 (+ .save.json, .txt 1.9 MB),
  table-0001 (+ .save.json, .txt 659 KB), table-0002/ and table-0002.parallel/ (32 subdirs), all 01:33. du of the digest dir
  54,177,792 B FLAT from 01:43:39 to 01:47:40 (no growth in 15 min since 01:33); free flat 603.21 GB. Whether the 31 children are
  computing (table 2 in parallel, in memory) or idle is checked in monitor 32 (per-child CPU, wchan, newest files).
- Worker 14824 S; no teacher process; marker standing; a2 entry running + save_request. Guard alive, not fired.
### monitor 32 (SSM 03a2f225-c740-4e70-8993-cf7260c42f66, 01:48:56-01:52:57Z, read-only; CONT rule armed, not needed)
- NOT a hang: the digest's table 2 is CPU-bound in 30 parallel parts. ROOT 14860's children: 30 workers 59921-59957 (one per
  CPU 1-31 except 16, 99.4% CPU each, ~245 MB RSS each, started 01:33:07) plus 56407 (anon_pipe_read, started ~01:21, the
  projection/digest pipe helper). Sum of child CPU ~2,985%. ROOT itself 7 threads in futex_do_wait (waiting on the parts).
- table-0002.parallel/ has 32 part-NNNN dirs (empty so far); table-0002/table.sqlite 8,192 B; the newest file under the digest dir
  is still table-0001.save.json (01:33:29). table-0001.save.json: context 32,972,800 B, digest 659,276 B, key.code = document.
  per_second_rows + frankie_box_digest_render.py + frankie_box_digest_stream.py, inputs = the layer sha256s (legacy_book_imbalance
  88b6a181..., ...): the digest tables are hash-keyed save points (the c65688d5 save-points design).
- free 603.21 (01:48:56) -> 599.15 GB (01:52:27): ~1 GB/min of other writes. Guard alive (599.15 GB at 01:52:33). Worker 14824 S;
  no teacher process; marker standing; a2 entry running + save_request.
- Expectation: the digest has many tables ahead (the Monday root's digest ran for hours, its sources.sqlite alone was 82 GB), so the
  ROOT exit (exit 75 under the marker -> 'saved') is likely AFTER this role's 02:30Z report deadline. The hold itself is in place:
  the marker is the queue's own, recorded in root.json, and is honoured at experiment_root.py:131 and at the queue's check_save.
### monitor 33 (SSM f43bb33e-cd55-430b-8fd3-863e2f6ffe52, 01:54:18-02:03:20Z, 9 min round, read-only; CONT rule armed, not needed)
- Unchanged: stage root-digest, ROOT S, 31 children (30 helpers at ~99% CPU each = 2,986-2,989% summed), the digest's table 2
  still in its first pass (write_table_parallel in frankie_box_digest_parallel.py:661: passes snapshot -> plan -> merge -> final ->
  copy, each a save point in scratch/passes.pkl; the snapshot pass is in-memory per part, so nothing is written until it ends).
  digest dir 54,177,792 B flat; newest file table-0001.save.json (01:33:29); no calculations-receipt.json.
- free 599.15 (01:54:18) -> 597.13 GB (02:01:19), flat after. Guard alive (597.13 GB at 02:02:34), not fired.
- Worker 14824 S; no teacher process; the one standing marker; a2 entry running + save_request.
### monitor 34 (SSM 4d71fe42-0d10-469b-9c32-90ba882bb70b, 02:04:50-02:08:37Z): ROOT 14860 EXITED 02:08:17Z, MID-DIGEST
- 02:04:50-02:07:51: unchanged (root-digest, 30 helpers at 99% each, digest dir 54 MB, table-0002.parallel parts empty).
- 02:08:17: ROOT 14860 GONE, 0 children. Guard log: "2026-10-08T02:08:17Z ROOT gone; guard ends free=597127733248" (the guard
  exited by itself; it never fired). Memory at the exit: avail 239 GB (no OOM in dmesg).
- ROOT log after 01:33:06Z: only multiprocessing resource_tracker output: "process died unexpectedly, relaunching", seven
  "KeyError: '/mp-...'" tracebacks from resource_tracker.py:457 (cache[rtype].remove(name)) and "8 leaked semaphore objects to
  clean up at shutdown". NO main-process traceback, no "saved" line, no receipt: the digest's table 2 (parallel, pass
  'snapshot') did not finish; the newest digest file is still table-0001.save.json (01:33:29); no calculations-receipt.json;
  progress.json still says stage root-digest, state running, pid 14860 (stale). Cause of the exit NOT established from the box
  (see 5b-6 below); the exit was clean enough that the queue classed it under the standing marker.
### THE HOLD LANDED IN THE QUEUE (probes 5b-3 a183d612 02:09:55Z, 5b-4 fc6aecf5 02:10:53Z, 5b-5 fc64d9f2 02:11:38Z)
- root.json a2 entry: state "saved", finish null, where box-slot, child null, retained_booking day-run-20231018-day_slot_root-
  1791402822-3111, reason "saved on its day-bound marker .../save/e2e-20231018-a2-20231018.save-request.json"; attempts[2]
  (c9bf631, pid 14824, started 22:43:49Z) ended 02:08:54Z result "saved"; owner holder_pid 14824, marker = the standing marker;
  the marker file itself still stands (01:20:55, 498 B) for ACTION=resume to archive. root-worker.json: state waiting_owner,
  reason saved on its day-bound marker, pending 1, utc 02:08:54Z.
- Worker 14824 ENDED (systemd: frankie-queue-root-1791413028.service main process exited 02:08:55Z status 5; "Consumed 2d 51min
  CPU time, 244.7G memory peak"); 14858 (cores helper) gone. NO teacher or classroom process ever started (checked at 02:08:37,
  02:09:55, 02:10:53, 02:11:38). The teacher did NOT run on c9bf631.
- KeepRunning was cleared by the worker's end (DescribeTags 02:10Z: KeepRunning=false, reason "frankie_box_frankie_queue.py worker:
  root line worker ended (scope e2e-20231018-a2:20231018)").
### AUTHORIZED WRITE: KeepRunning=true RE-SET (ec2 CreateTags, 02:11:5xZ) after verifying STATE=saved, booking retained, worker
gone, no teacher. DescribeTags after: KeepRunning=true, KeepRunningReason "session5b hold agent: a2 ROOT entry saved on its marker
02:08:54Z (ROOT exited mid-digest, no receipt); box held for the restage + resume at the teacher; re-set after the worker end
cleared it". Next idle-guard cron 06:17Z: the box is safe from it.
### CONSEQUENCE FOR THE RESUME (for the parent): the ROOT is NOT complete. ACTION=resume + ACTION=kick on the restaged tip will
make the new worker's Run.root find NO calculations-receipt.json, so the ROOT RUNS AGAIN (not 'reused'): legacy-stage.json
(01:17) and native-stage.json (00:15) and the published layers are on disk for reuse; the digest restarts at its save points
(tables 0 and 1 have .save.json; table 2's parallel scratch has no saved pass, so it starts over). Then the digest, receipt, and
only then the teacher. The 472 GB inline layer and the 497 GB frames spool are still read by that digest.
### OTHER ACTORS ON THE BOX (not this role): /opt/frankie-box/archive/.logs/hold-a2.sh (01:16, 3,716 B) + hold-a2.log (30,311 B,
last write 01:51) = a second on-box hold watcher deployed by the parent (or its agent) during the unarmed gap; it is the actor that
ran the queue's ACTION=save at 01:20:55Z ("dispatch save"). clean-a2.sh (01:45, 26,661 B, the clean role's one-pass clean-and-zip
of the finished ROOT output; dry-run mode writes nothing) was RUNNING as `timeout 100 bash clean-a2.sh dry-run` (pids 75219/
75220/75405) at 02:10:53Z. Other SSM commands on the box not sent by this role: f2a9d527, 13dec374, 5333b0c3.
### Cause-of-exit reading (probes 5b-6 ce8ac4a9 02:12:18Z, 5b-7 8d17ace7 02:13:20Z; code read on the work branch)
- No digest-level save check exists: grep of frankie_box_monday_calculations.py, frankie_box_digest_parallel.py,
  frankie_box_digest_stream.py, frankie_box_lane_pin.py, frankie_box_progress.py for save_requested/TeacherSaved/STOP_FILE/
  SystemExit finds nothing; boss_session.py:2941-2947 runs _write_digest then probe.update('root-derived', complete). So the
  02:08:17Z exit was NOT a lawful digest save point: the ROOT ended during table 2's snapshot pass with no main-process traceback
  in its log, no OOM, no kernel message (journal 02:07-02:10 holds only the unit's exit lines; kernel log ends 00:03:43).
- WHY THE QUEUE CALLED IT 'saved' ANYWAY: Run.child (frankie_box_experiment.py:1437-1450) waits for the child, then calls
  self.check_save() BEFORE looking at the exit code ("Never kill their workers or start a following stage after a save request"),
  so under the standing marker ANY child exit, crash included, raises SystemExit(75) in the worker thread and the entry is
  recorded 'saved' with the booking retained. The ROOT's real exit code is therefore not in root.json (heartbeat.stop('exited',
  code) at 1447 may hold it: probe 5b-8).
- The parent's hold-a2.sh (01:16): poll 5 s; on stage root-projection/root-projection-publication/root-digest/root-derived or the
  receipt, ACTION=save once (refuses if a teacher runs or a marker stands), then ACTION=status every 60 s for 30 min; its log
  shows the marker standing and "save pending acknowledgment" from 01:21 to 01:50:00 (stage root-digest, ROOT Sl, teacher none);
  "watcher end" 01:51:00Z. It wrote the 01:20:55Z marker. clean-a2.sh's dry-run had ended by 02:12:18 (no process).
- Disk at 02:13:20Z: / free 597,127,131,136 B (72% used); archive free 1,725,022,760,960 B (21% used). No frankie, tar, zstd,
  clean-a2 or hold-a2 process on the box. Nothing in flight.
### RESOLVED: the ROOT was SIGKILLED by another actor's SSM command (probes 5b-8 73619305, 5b-9 61d51b37, 5b-10 0aae00ac,
### 5b-11 2f268e67, 02:14-02:16Z, read-only)
- The stage heartbeat (experiment/e2e-20231018-a2/days/20231018/progress/root.jsonl, line 540, 02:08:16Z): outcome "exited",
  exit_code 137 (SIGKILL), final true, phase = the last log line "KeyError: '/mp-itduzqby'"; the samples before it (02:07:28,
  02:07:58) read phase root-digest, 33 processes, rss 8.4 GB, stalled true (units_unchanged_s 2072: the digest publishes no
  units, so "stalled" is the probe's reading of an unmeasured stage, not a hang). Earlier finals in the same file: exit_code 75 at
  the 20:05 and 22:40 saves (pids 3146, 6737).
- SSM ab5649ac-f760-4804-a2aa-6393c5d4bd47, started 02:08:14.7Z, comment "B: SIGKILL ROOT 14860 tree (marker standing) then
  verify; never the worker 14824", NOT this role's: `pkill -KILL -P 14860` then `kill -KILL 14860` (both rc 0), 35 s, then a
  verify block (entry, booking, events, worker status, units, journal, marker, df). Its own verify at 02:08:50 saw 14860 GONE,
  14858 gone, "digest workers left: 29" (orphaned spawn_main helpers, children of the killed ROOT; by 02:10:53 no python process
  other than the system's remained: they ended with their parent's pipes), worker 14824 still up (it ended 02:08:54 'saved').
  The commands before it from the same actor were read-only ("relaunch probe 1" 01:55, "relaunch wait-probe 2" 01:56,
  "relaunch digest probe" 01:57, "relaunch poll 3" 02:00, "relaunch poll 4" 02:04): a relaunch role decided to stop the digest
  under the standing marker rather than wait for it. Other actors' commands in the window were pod-root import/queue/claim
  (02:01), report parts 1-3, queue show 2, teacher receipt 0929-3, side-builder progress logs, "Inactive reviewed source stage"
  (02:00, 02:06, 02:09) and the clean role's clean-a2.sh rows-dir (02:10:11) and dry-run (02:10:46). None by this role.
- So: the ROOT did NOT complete (no receipt; the digest's table 2 was ~35 min into its snapshot pass); the queue recorded the day
  'saved' because the marker stood when the killed child's exit reached Run.child's check_save (experiment.py:1450). No teacher
  started. The resume on the restaged tip re-runs the ROOT (stage files and digest tables 0-1 reusable; table 2 restarts).
- Box at 02:16Z: no frankie/python/tar/zstd/clean/hold process; load 29.6 falling; / free 597.13 GB (72%); archive 1,725.0 GB free
  (21%); KeepRunning=true (this role, 02:11:5xZ). Marker standing for ACTION=resume. Nothing else in flight.
### Session 5b writes, complete list: (1) SSM hold-watch 28 ran the queue's ACTION=save wrapper once (refused: marker stood; no
change); (2) ec2 CreateTags KeepRunning=true + KeepRunningReason on i-035994afa8bdf66a5 at 02:11:5xZ. No kill, no CONT (never
needed), no removal, no instance control. Everything else read-only SSM (commands 6edac15e, b99599bf, b67fa633, f0e9b2a1,
3d0cc3a1, 9360f63b, 03a2f225, f43bb33e, 4d71fe42, a183d612, fc6aecf5, fc64d9f2, ce8ac4a9, 8d17ace7, 73619305, 61d51b37,
0aae00ac, 2f268e67).
