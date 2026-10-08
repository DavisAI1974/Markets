# Box probe, 2026-10-08 00:58-01:04Z (session 6, box-probe role, READ-ONLY)

Box i-035994afa8bdf66a5 (us-east-1, r7i.8xlarge), probed through SSM AWS-RunShellScript (read commands only:
ps, df, ls, stat, cat, du, tail, lsblk, findmnt, journalctl, pgrep, top, /proc reads). Nothing on the box or in AWS
was changed. Raw SSM stdout saved beside this file (raw_C1..C4.txt, raw_B.txt). Repo tip read: d07a07d.
Drop-in read: research/kalshi/frankie_boss/DROP_IN_CLAUDE_20261008_SESSION6.md (all); queue contract read:
deploy/aws/box/frankie_box_frankie_queue.py (QUEUE=/opt/frankie-box/work/frankie-queue, SAVE_DIR=QUEUE/save,
marker <run>-<day>.save-request.json, request_save writes it exclusively and records entry['save_request'];
_finish_steps calls run.check_save() before run.teacher).

## Headline

- ROOT 14860 ALIVE and RUNNING (not frozen, not completed). State R, 100% of one CPU. It finished the 472 GB layer
  write at 01:02:49Z and is now in a SECOND sequential read of that same layer file (~1.09 GB/s, ends ~01:10Z).
  progress.json is STALE: stage "root-legacy-finalize" written 23:41:47Z, never updated since.
- THE HOLD DID NOT LAND AND IS NOT ARMED: no save marker stands in frankie-queue/save/, entry save_request=null,
  no watcher process, no save_requested event after the 22:43Z kick. If ROOT completes, the worker proceeds to the
  teacher on c9bf631 (the thing Greg wanted to prevent). Projection (the watcher's trigger) has NOT been reached yet.
- TEACHER NOT STARTED: no teacher process, no teacher unit, the only unit is frankie-queue-root-1791413028 (running).
- Root volume free: 702,059,421,696 B (702.06 GB = 653.9 GiB), 68% used, at 01:03:03Z. Min free was
  59,689,934,848 B at 00:41:25Z (disk guard log); guard never fired (no frozen-pids file; limit 15 GB).
- Monday root REMOVED at 00:48:05Z (freed 427,266,150,400 B); symlink + README + receipts dir at the old path;
  archive tar.zst 297,465,977,258 B, sha256 6eae842c61cf6e0cc8dee0bb7484ec5388ff57c11d4b7b58625f4a1d90f1f662
  (sha256sum pass finished 00:48:26Z, 21 s AFTER the source was gone; the decompress-list pass was stopped at
  422/604 entries; the full entry comparison never ran).
- Archive batch: 50 jobs, all 50 VERIFIED+REMOVED (last at 00:58:08Z), 51 tar.zst on the archive volume
  (438,311,010,304 B used of 2,163,350,618,112), every .pipestatus "0 0", no batch worker running.
- KeepRunning = "true" (tag present on the instance).

## 1. EC2 / EBS

DescribeInstances i-035994afa8bdf66a5: State running (code 16), r7i.8xlarge, LaunchTime 2026-10-07T18:17:49Z.
Tags: KeepRunning="true"; KeepRunningPolicy="true only while a run holds the box; the run sets it at lane claim and
clears it at finish (Greg 2026-10-07)"; KeepRunningReason="ccode_step8: a2 resumed on c9bf631 22:43:48Z (root worker
frankie-queue-root-1791413028); re-set after the saved worker end cleared it"; Name=frankie-ingest32-20260917;
Purpose="Frankie Sunday existing journal workflow ingest runner".
Block devices: /dev/sda1 = vol-0d36715924f03b86c (attached 2026-09-17), /dev/sdf = vol-004b68c077be09cc9
(attached 2026-10-08T00:02:58Z).
- vol-0d36715924f03b86c (root): gp3 2048 GiB, 16000 IOPS, 1250 MiB/s, encrypted, in-use, DeleteOnTermination true.
- vol-004b68c077be09cc9 (archive): gp3 2048 GiB, 10000 IOPS, 1000 MiB/s, encrypted, in-use, attached /dev/sdf,
  DeleteOnTermination FALSE.
DescribeVolumesModifications: InvalidVolumeModification.NotFound for vol-004b68c077be09cc9 (no modification record
exists for it; the call errors on the pair, so the root volume's modification state could not be read in the same
call; the root is 2048 GiB as before, no resize in flight is inferred).

## 2. ROOT process tree, freeze state, disk guard

At 00:58:10Z:
```
    PID    PPID STAT WCHAN                                ELAPSED COMMAND
  14860   14858 Rl   -                                   02:14:19 .../frankie_box_experiment_root.py --commit c9bf631e884813adb79d263c80afd52a7fd9d837 ... --output-root .../e2e-20231018-a2-20231018-a1 --data-workers 31 --digest on --shared-market-policy FRANKIE_SHARED_MARKET_TIMELINE_V1 --bedrock on --resume
  14824       1 Ssl  hrtimer_nanosleep                   02:14:22 .../frankie_box_frankie_queue.py --action worker --line root --code-root /opt/frankie-box/code/c9bf631e...-37695921903-1/markets --commit c9bf631e... --max-seconds 43200 --poll-seconds 60 --scope e2e-20231018-a2:20231018
  14929   14860 Z    -                                   02:14:02 [python] <defunct>
```
pstree: 14824 (queue worker) -> 14858 (frankie_box_cores.py run --kind day-run ... --inside
day-run-20231018-day_slot_root-1791402822-3111 -- bash frankie_box_experiment_root.sh) -> 14860 (ROOT) -> 14929 (Z,
the finished native child, not reaped) + 15 worker children 17668-17682 (S, futex_do_wait / anon_pipe_read, elapsed
01:16:22, i.e. started 23:41:47Z = the layer encoders on CPUs 9-15,24-31) + 4 threads. By 01:03:02Z the 15 encoders
were gone (pgrep -c -P 14860 = 1, the zombie); 14860 single-threaded, R, top 81.8-100% CPU, TIME+ 60:02.
ALL T-STATE PROCESSES: none (header only). Nothing is frozen. 14929 is a zombie (native stage complete 00:15Z).
Disk guard: `pgrep -af disk-guard` -> `32657 /bin/sh /opt/frankie-box/archive/.logs/disk-guard.sh` STILL RUNNING,
polling every 2 s (limit 15,000,000,000 B, root pid 14860, SIGSTOPs the tree below the limit, exits when ROOT is gone).
disk-guard.frozen-pids: "No such file or directory" (never fired). disk-guard.log (complete):
```
2026-10-08T00:33:26Z guard start limit=15000000000 root=14860
00:34:24 free=115947220992 ... 00:40:25 free=67143061504
00:41:25 free=59689934848     <- minimum
00:42:25 free=71045390336   00:44:25 free=121092927488   00:47:26 free=152210694144
00:48:26 free=579471777792  (Monday root removed 00:48:05)
00:55:26 free=636707590144  (teacher rows removed 00:55:21)
00:57:27 free=636707319808 ... 01:02:27 free=702059507712
```

## 3. Disk

```
df -B1 /               2129040207872 total  1426964008960 used  702059421696 avail  68%   (01:03:03Z)
df -B1 /opt/frankie-box/archive  2163350618112 total  438311010304 used  1725022830592 avail  21%
lsblk -b: nvme0n1 2199023255552 (nvme0n1p1 2197948448256 /), nvme1n1 2199023255552 /opt/frankie-box/archive
findmnt: /opt/frankie-box/archive /dev/nvme1n1 ext4 rw,noatime
```
Root free now: 702,059,421,696 B. du -xb --max-depth=1 /opt/frankie-box/work (01:02Z): total 1,393,961,299,004 B,
of which experiment-roots 1,374,073,670,111 (ALL of it the a2 attempt: 1,374,073,657,679), day-external
10,148,699,904, ingest-20231018-gh-36571235912-1 8,861,540,520, runs 755,021,410, monday-launch 69,005,731,
performance-session 16,379,012, two sealed-recovery-code dirs ~15 MB each, monday-calculations 3,873,647 (receipts
only), everything else < 1 MB. /opt/frankie-box/code: 8,056,335,106 B total = 4 checkouts kept (18cbc5a4,
98579cea, 275367fe, c9bf631, ~1.41 GB each) + their 4 transfer-* dirs (~0.6 GB each).
a2 attempt breakdown (du -xb, 01:03Z): work/derived 970,408,090,285 (legacy_book_imbalance.json 472,040,420,230 +
.rows 498,361,324,566: frames.jsonl 496,743,568,399, structures.jsonl 1,063,001,944, input-*.jsonl 537,361,074,
prices.jsonl 17,393,149, failures.jsonl 0); work/bedrock 403,664,543,623 (recovery-6f84a8a8... 335,248,031,691 incl.
ledgers/exact_member_rows.jsonl 193,743,650,444 per native-stage.json; pre-save ledgers/ 68,074,692,642 incl.
exact_member_rows.jsonl 66,121,336,080; checkpoints 341,767,005).

## 4. Monday root removal and the archive

/opt/frankie-box/work/monday-calculations/ (ls -la):
```
lrwxrwxrwx full-20211004-20260927-r1-48 -> /opt/frankie-box/archive/monday-calculations/full-20211004-20260927-r1-48.tar.zst   (00:48:05)
-rw-r--r-- 887 full-20211004-20260927-r1-48.ARCHIVED.README.txt
drwx------ full-20211004-20260927-r1-48.receipts   (calculation-pins.json, calculations-receipt.json, checkpoints.json, note,
            phase, progress.json, source-binding.json, pause-for-*.json, reap-orphans-*.json, superseded/digest-render-*/digest-proof.json, work/)
```
The directory is GONE; a symlink to the archive stands at its path; README says: 427,266,150,400 B, 500 files / 604
entries, moved 2026-10-08T00:48:05Z; small receipts (< 2 MB) kept uncompressed; restore line given.
Archive side (/opt/frankie-box/archive/monday-calculations/):
```
297465977258  full-20211004-20260927-r1-48.tar.zst            (00:21)
        1213  ...tar.zst.VERIFICATION-NOTE.txt                 (00:47)
       67327  ...tar.zst.listing.PARTIAL-stopped-by-greg-004733.txt   (422 lines)
         148  ...tar.zst.sha256                                (00:48)
sha256: 6eae842c61cf6e0cc8dee0bb7484ec5388ff57c11d4b7b58625f4a1d90f1f662  .../full-20211004-20260927-r1-48.tar.zst
```
Logs: monday-root-tar.log "start 00:06:45 free_root 309094195200 / Total bytes written: 427265044480 (398GiB,
450MiB/s) / zstd_pipeline_rc=0 end 00:21:53". monday-root-verify.log "start 00:21:55 / tar: Unexpected EOF in archive /
tar: Error is not recoverable: exiting now / 2026-10-08T00:47:33Z decompress-list pass STOPPED by Greg's decision after
422 listing lines / sha_rc=0 00:48:26" (the EOF error is the killed pipe). monday-root-removal.log
"2026-10-08T00:47:33Z removal start (Greg's decision) free=152210620416 sha=pending / 2026-10-08T00:48:05Z removal done
free=579471753216 freed=427266150400". VERIFICATION-NOTE: checks that RAN = tar --totals (427,265,044,480 B stream for
427,264,335,065 file bytes), zstd pipeline rc 0 (XXH64 frame checksums verified on decompression), decompress-list
validated 422 of 604 entries before the stop, no open handle at removal; "sha256 of the archive: pending (the
sha256sum pass, one read, is left to finish and writes ...sha256 by itself)"; "NOT run to completion: the full
entry-by-entry listing comparison". So: the archive's sha256 is recorded, but it was computed AFTER the source was
removed and nothing compared it against a write-stream hash; 182 of 604 entries were never list-verified.

Archive volume top level (du -sb): monday-calculations 297,466,045,946; work 128,889,132,004; code 11,954,687,604;
.logs 33,413; lost+found 0. 51 tar.zst total: 1 Monday + 50 batch (7 code checkouts ~1.19 GB each + 7 transfer-*
~0.60 GB each [one 448 B] under code/; under work/: 15 ingest-* (ingest-20211004-ingest 18,386,938,852; the
2022/2023 gh-36571235912-1 ingests 7.2-11.4 GB each; 4 canaries; two 101/106 B empties), ingest-stack-measure,
experiment-teacher-rows 24,863,644,343; under work/experiment-roots/: 17 days-2026092x/0930 roots + the a1
attempt e2e-20231018-a1-20231018-a1 117,974,819). Every *.pipestatus reads "0 0" (none non-zero).

batch.log (92 lines; counts: VERIFIED+REMOVED 50, "TAR/ZSTD FAILED rc=0" 14, "VERIFY FAILED (source kept)" 11, 3
worker-start lines, "worker done" 6). Timeline: 00:40:25 start, 3 workers on CPU pairs 3,19 4,20 5,21; 00:45:47
"one-pass workers start (Greg: no second read)"; 00:48:58 "one-pass workers stopped to fix the rc check (jobs skipped as
'FAILED rc=0' were archive-written but unverified)"; 00:48:59 worker3 (fixed rc check); 00:49-00:51 VERIFY FAILED on
the days-20260929-3 / 20260930-1 roots with a hardlinked file (w87/r87/src88) and on teacher rows (listrc 1/2, a
transient missing-archive stat in batch-worker-4,20.out); 00:55:21 teacher rows VERIFIED+REMOVED (entries
w6066/r6066/src6066, bytes 25,128,540,076 all three ways, sha 5d3dd82d8f3af932); 00:58:07-00:58:08 "[recheck]
VERIFIED+REMOVED" for the 8 hardlink roots (names w88/r88/src88, bytes equal, "hardlink entries 1 (expected 1 from 2
linked names / 1 inodes)"). Final: all 50 batch sources removed and replaced by symlink + .ARCHIVED.README.txt (36
READMEs under work/, 17 under experiment-roots/, 14 under code/). Sources NOT touched, still directories: day-external,
ingest-20231018-gh-36571235912-1, the a2 attempt, checkouts 18cbc5a4/98579cea/275367fe/c9bf631 + their transfer-*,
runs/, monday-launch, etc. No batch worker, tar or zstd process is running.

## 5. a2 state

R/progress.json (mtime Oct 7 23:41, unchanged through 01:04Z):
{"at": 1791416507.21 (=23:41:47Z), "phase": "deriving", "pid": 14860, "stage": "root-legacy-finalize", "state": "running",
 completed 0, failed 0, in_flight 0, percent null, total null}
R/root.json: does NOT exist. R/phase: "deriving". R/out: empty. R/note at 01:02:49Z: "layer legacy_book_imbalance.json
written in 4861.4 s (spools encoded on pinned lane CPUs 9-15,24-31)" (before that: "legacy pass: 269571 frame rows from
replica shards, 0 built in the replay; the replay waited 2156.2 s on shards").
R top level: calculation-pins.json 33,283 (19:53), checkout-rebinds/, external-computation.json 41,956, native-overlap/
(checkpoints.json 302 B 00:14:41: counts saved 10 / read_verified 10, last checkpoint-000009.json; progress.json
00:14:04), source-binding.json 7,631, work/.
R/work: bedrock/, boss-jobs/ (empty), derived/, input-state.pkl, legacy-cpu-split.json (23:34), legacy-state.pkl
860,663 (23:41), native-overlap.json (22:44), native-stage.json 46,079 (00:15:04; lists 5 artifacts with sha256 under
bedrock/recovery-6f84a8a8.../: receipt.json, result.json 224,765,615, ledgers/exact_member_rows.jsonl
193,743,650,444, exact_lifecycle_rows.jsonl 7,560,352,552, legacy_observable_rows.jsonl 742,788,266), native-stage.lock 0.
R/work/derived: legacy_book_imbalance.json 472,040,420,230 B mtime 2026-10-08 00:45:07.893Z (stat at 00:58:10,
00:59:42, 01:00:53, 01:01:13, 01:03:03: identical size and mtime: NOT GROWING; the write ended 00:45:07);
legacy_native_signed_flow.json 5,301,145; legacy_per_second_roll20.json 1,042,750; legacy_price.json 1,594 (all
23:41:47); .rows/ (frames.jsonl 496,743,568,399 mtime 23:34:53, structures.jsonl 1,063,001,944, prices.jsonl, input).
Receipts: NONE. No legacy-stage.json, no digest*, no receipt*, no projection* under R (find maxdepth 3). Only
native-stage.json (00:15:04) and native-overlap/checkpoints.json exist.
ROOT log /opt/frankie-box/work/experiment/e2e-20231018-a2/logs/20231018-root.log (3,378 B; fds 1,2 of 14860):
```
2026-10-07T22:44:08Z native stage started beside the legacy pass (child 14929; native on CPUs 0-7,16-23, legacy on 8-15,24-31 ...)
2026-10-07T22:52:13Z legacy pass: replay on CPU 8, frame rows built on 14 pinned replica shards 9-15,25-31 ...
2026-10-07T23:34:53Z legacy pass: 269571 frame rows from replica shards, 0 built in the replay; the replay waited 2156.2 s on shards
2026-10-08T01:02:49Z layer legacy_book_imbalance.json written in 4861.4 s (spools encoded on pinned lane CPUs 9-15,24-31)
```
No "ROOT completion published". journalctl -u frankie-queue-root-1791413028: one line only (Started ... 22:43:48Z).
No *.log under R or /opt/frankie-box/work/. Queue worker log frankie-queue/logs/root-worker.log last written 22:40.

What ROOT is doing (from /proc/14860, read-only):
- 00:45:07-01:02:49Z: after the file was fully written it READ IT BACK sequentially: fd 41 O_RDONLY on
  legacy_book_imbalance.json, pos 418,897,723,392 at 01:02:06; read_bytes +90,998,419,456 in 73 s (1.25 GB/s); 100% of
  one CPU; write_bytes flat. The "written in 4861.4 s" log line (23:41:47 -> 01:02:49) covers encode+write (63 min, ends
  00:45:07) plus this read-back (17.7 min). When the 15 encoder children exited at 01:02:49 their counters folded into
  14860's /proc io (wchar +472,041,018,906 = the layer bytes they piped, read_bytes +651 GB = the frames spool they read).
- 01:02:49Z onward: a NEW fd (6) on the SAME layer file, a SECOND full sequential read: pos 14,814,281,728 at 01:03:02,
  90,194,313,216 at 01:04:12, 106,484,989,952 at 01:04:27 (1.086 GB/s). Remaining 365.6 GB at 01:04:27 -> ends ~01:10Z.
  Presumably the legacy-stage.json artifact hash (native-stage.json carries per-artifact sha256). Two consecutive full
  reads of a 472 GB file on c9bf631 = the "exactly ONE read-back pass" lesson violated by the running code; Greg's open
  call (c) "skip re-hash on unchanged stat" is exactly this.
- After it: legacy-stage.json, native join/reuse, projection, digest (cost unmeasured), receipt, "ROOT completion
  published". No ETA can be given for those from the box.

## 6. The hold

frankie-queue/save/ holds ONLY archived markers (no standing *.save-request.json):
e2e-20231018-a1-20231018.save-request.json.resumed-1791400389 (18:59:45Z), e2e-20231018-a2-20231018.save-request.json
.resumed-1791409621 (20:05:24Z), ...resumed-1791413028 (22:32:39Z). All three "by": "dispatch save".
root.json entry seq 2 (e2e-20231018-a2 / 20231018): state "running", reason "its whole day in the held box slot
day-run-20231018-day_slot_root-1791402822-3111", finish null, save_request NULL, child null, retained_booking
day-run-20231018-day_slot_root-1791402822-3111, retain_error null, classroom_arm null. owner.marker =
/opt/frankie-box/work/frankie-queue/save/e2e-20231018-a2-20231018.save-request.json (NOT present), owner.commit
c9bf631, attempt e2e-20231018-a2-20231018-a1, bound 19:53:42Z. attempts[]: 98579cea pid 3111 saved 20:05:42Z;
275367fe pid 6704 saved 22:40:28Z; c9bf631 pid 14824 started 22:43:49Z, no ended/result. retired: e2e-20231018-a1.
root-events.jsonl last events: 22:32:39 save_requested (pid 13761), 22:40:28 slot_saved + worker_end, 22:43:48 resume
(archived the marker) + take (pid 14824) + kick (unit frankie-queue-root-1791413028). NOTHING after the kick.
root-worker.json 01:00:53Z: state running, pending 1, running [2], stop null, scope e2e-20231018-a2:20231018.
Hold watcher: `pgrep -af "ACTION=save|hold|watcher"` -> nothing. No python process outside the ROOT tree except
networkd-dispatcher and unattended-upgrades. THE BOX IS UNARMED.
Teacher: `pgrep -af teacher` -> nothing; systemctl list-units 'frankie-*' --all -> exactly 1 unit,
frankie-queue-root-1791413028.service loaded active running. /opt/frankie-box/work/experiment-teacher-rows is now a
SYMLINK to the archive tar (00:55:21Z) with experiment-teacher-rows.ARCHIVED.README.txt; no teacher rows directory
exists for a teacher to write into (a teacher start would hit a symlink to a .tar.zst: RELAY THIS). days/20231018/
root.json under experiment/e2e-20231018-a2 is the 19:53 enqueue record (status queued); no teacher.json there.
run plan.json/summary.json/progress.json unchanged since 19:53; keep-running.json last entry 22:40:28 (worker ended,
asked false, tagged true) -- the tag was re-set to true afterwards (EC2 shows true).

## 7. Booking / units

systemctl list-units 'frankie-*' --all: 1 unit (above). Booking /opt/frankie-box/cpu-bookings/day-run-20231018-
day_slot_root-1791402822-3111.json exists: commit c9bf631, cpu_list 0-31, demand 32, nproc 32, owner at 22:43:49Z
attempt e2e-20231018-a2-20231018-a1, pids [14824 "booking holder", 14860 "step root (under taskset, inside the held
slot)"], resumed[] carries the 21:47:27 (275367fe, pid 6704) and the retained records from 20:05:28 (by_pid 3111).
Retained and live.

## 8. CPU load

uptime 00:58:10: load 1.12, 4.64, 11.46 (up 6:40); 00:59:42: 1.02, 3.64, 10.43.
top 00:59:43: Tasks 427, 2 running, 1 zombie; %Cpu 2.3 us 0.9 sy 96.8 id; Mem 253,663.9 MiB total, 20,628.6 free,
228,893.3 buff/cache; 14860 python 100.0% CPU RES 770,544 KB TIME+ 56:47. At 01:03:02: 14860 81.8%, TIME+ 60:02, the
only busy process. 31 CPUs idle.

## Surprises / to relay

1. The hold is NOT armed and did not land; ROOT is still well before projection (second read of the layer, then
   legacy-stage, native join, projection, digest, receipt). Re-arm before projection or the teacher starts on c9bf631.
2. progress.json has been stale at "root-legacy-finalize" since 23:41:47Z; a watcher keyed on the stage field would
   not have fired during the whole 81-minute layer step either.
3. c9bf631 reads the 472 GB layer back TWICE in a row (17.7 min + ~7 min) after writing it.
4. experiment-teacher-rows is a symlink to a tar.zst; a teacher start on this box would have no rows directory.
5. The Monday archive's sha256 was computed after the source was removed; the list pass covered 422/604 entries.
6. The archive volume is DeleteOnTermination=false (survives a stop/terminate); root free 702 GB; the disk guard
   script is still polling every 2 s and will SIGSTOP ROOT's tree below 15 GB free.
7. No DescribeVolumesModifications record for the archive volume; root volume still 2048 GiB.
