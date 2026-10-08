# Probe: a2 legacy finish watch (box-probe role), 2026-10-07 session 5

Run e2e-20231018-a2, attempt e2e-20231018-a2-20231018-a1, box i-035994afa8bdf66a5 (us-east-1).
R=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1. ROOT 14860, native 14929, code c9bf631.
All box times UTC. Read-only unless stated.

## Probe 1, box 23:08:01-23:08:44Z (SSM 1e32924c-b6fc-44dc-8ef2-0cebc44af941, 856c089c-d6c1-4340-a6bc-e455fb607095, 3d77538c-b19d-4ab7-9258-feb80b742f87)
- EC2: running; KeepRunning=true; SSM PingStatus Online.
- ROOT 14860: S, wchan poll_schedule_timeout, 41.0% CPU, elapsed 24:10. Native 14929: R, 83.5%, elapsed 23:53, Cpus_allowed 1.
- 14 legacy replica shards, children of 14860: pids 15281-15294, each R ~97-100% CPU, elapsed 15:47, pinned one each to
  CPUs 9,10,11,12,13,14,15,25,26,27,28,29,30,31 (Cpus_allowed_list verified).
- 14929 children: resource tracker 14973 + 16 spawn workers 14974,14977,14982,14995-15007 (book workers etc.).
- Legacy progress ($R/progress.json, root-legacy-records, running): 133,805 / 360,328 (37.13%), failed 0, at 23:08:01.
  (Total 360,328 = 771,787 - 411,459: counted from the resume cursor; start 22:52:13 -> ~139 rec/s; ETA ~23:35Z.)
- Native progress ($R/native-overlap/progress.json, root-native-records, running): 431,072 / 771,787 (55.85%), failed 0,
  at 23:07:51. (From 283,338 at 22:45:25 -> ~108 rec/s; 340,715 left -> ETA ~00:00Z.)
- phase file: deriving. note: "legacy pass: replay on CPU 8, frame rows built on 14 pinned replica shards 9-15,25-31".
- Queue: root-worker.json state running, pid 14824, commit c9bf631, scope e2e-20231018-a2:20231018, running [2], pending 1.
  root.json: third attempt (c9bf631, pid 14824, started 22:43:49Z) open; prior attempts 98579cea and 275367fe "saved".
- Unit frankie-queue-root-1791413028: active (running) since 22:43:48, Tasks 68, Memory 182.3G (peak 182.7G, page cache
  included), CPU 4h45m.
- ROOT log /opt/frankie-box/work/experiment/e2e-20231018-a2/logs/20231018-root.log, last line 22:52:13Z (legacy pass start).
- Disk /: 2.0T, used 1.2T, avail 777G (61%). frames spool work/derived/.rows/frames.jsonl = 325G (du).
- RAM: 247 G total, 11 used, 236 buff/cache, 236 available; no swap.
- CPU (mpstat 2 s): shards 9-15,25-31 at 94-100% usr; CPU 1 78.6% (native ROOT); CPUs 4,5,6 30-38%; 8 (legacy replay) 14.5%+4.5 sys;
  24 idle with 14.65% iowait; rest <10%. Load avg 16.61.

## Watch 1, box 23:09:36-23:13:36Z (SSM 0b72b708-95f7-44d8-859c-02862fcbfd6c; 9 samples at 30 s)
- Legacy 146,895 -> 181,516 / 360,328 (34,621 in 240 s = 144 rec/s; 178,812 left -> ETA ~23:34Z). failed 0.
- Native 441,327 -> 468,084 / 771,787 (26,757 in 240 s = 111 rec/s; 303,703 left -> ETA ~23:59Z). failed 0.
- ROOT wchan poll_schedule_timeout (one sample 0 = running); 14 shard children; anon_pipe_write 0 except one transient 1 at 23:11:06
  (normal pipe backpressure mid-pass, not the hang). legacy-state.pkl still the 22:36:09 save (1,405,815 B). Log last line 22:52:13Z.

## Watch 2, box 23:14:57-23:18:57Z (SSM 32a091c0-9aec-4b35-903d-fb66effc594b)
- Legacy 192,500 -> 226,212 / 360,328 (140 rec/s; 134,116 left -> ETA ~23:35Z). failed 0.
- Native 477,660 -> 498,533 / 771,787 (87 rec/s over the window; flat at 487,869 for ~30 s 23:16:27-23:16:57, progress age 32.8 s,
  then resumed ~105 rec/s). failed 0.
- ROOT poll_schedule_timeout; 14 shard kids; anon_pipe_write transient 0-4 (backpressure, progress advancing every sample).

## Watch 3, box 23:20:15-23:24:15Z (SSM 91f43f84-a989-45ed-99d9-993512300956)
- Legacy 237,004 -> 271,856 / 360,328 (145 rec/s; 88,472 left -> ETA ~23:34:30Z). failed 0.
- Native 506,929 -> 534,243 / 771,787 (114 rec/s; 237,544 left -> ETA ~23:59Z). failed 0.
- ROOT poll_schedule_timeout; 14 shard kids; anon_pipe_write transient 0-3; legacy-state.pkl unchanged (22:36:09 save).

## Watch 4, box 23:25:26-23:29:26Z (SSM ac843d6d-fc6d-4c4f-93d3-de481543bc30)
- Legacy 281,385 -> 311,532 / 360,328 (126 rec/s; slower first minute, 23:25:56 sample had anon_pipe_write 12 while advancing;
  48,796 left -> ETA ~23:35:45Z). failed 0.
- Native 541,096 -> 563,151 / 771,787 (92 rec/s; flat at 555,334 23:27:26-23:27:56, progress age 44.7 s, then resumed; 208,636 left
  -> ETA ~00:00-00:05Z). failed 0.
- ROOT poll_schedule_timeout; 14 shard kids; legacy-state.pkl unchanged.

## Watch 5, box 23:30:40-23:34:40Z (SSM 08783a3b-24b3-461c-a811-be33aa8f7beb)
- Legacy 322,393 -> 357,364 / 360,328 (146 rec/s; 2,964 left at 23:34:40 -> finish ~23:35:05Z). failed 0.
- Native 572,141 -> 599,939 / 771,787 (116 rec/s; 171,848 left -> ETA ~23:59-00:00Z). failed 0.
- ROOT poll_schedule_timeout; 14 shard kids; anon_pipe_write 0-6 transient; legacy-state.pkl unchanged.

## Watch 6 -- LEGACY FINISHED, NO HANG (SSM 0342b93e-49d6-468a-a09b-331f5f53dc80, box 23:35:52Z; loop exited LEGACY_MOVED_ON on sample 1)
- Legacy progress: root-legacy-records state COMPLETE, 360,328 / 360,328, failed 0, progress at 23:34:53Z.
- ROOT log 23:34:53Z: "legacy pass: 269571 frame rows from replica shards, 0 built in the replay; the replay waited 2156.2 s on shards".
- At 23:35:52Z: shard children of 14860 = 0 (all 14 shards 15281-15294 exited on their own), ROOT wchan 0 (running, not do_wait),
  only child 14929 (native, R, 83.7%). Hang signature ABSENT. No kill was sent. Nothing was killed or touched.
- Native at 23:35:52Z: 607,370 / 771,787, running.

## Post-finish probe, box 23:41:11Z (SSM 845d2adb-1c6a-4147-8b6e-82c9a3caa1ee)
- ROOT 14860 R, 37.2% CPU, on CPU 31, elapsed 57:20; native 14929 R 83.9% on CPU 1; 14929 is ROOT's only child.
- Native 638,328 / 771,787 (82.71%), failed 0, at 23:41:07Z (133,459 left at ~110 rec/s -> ~00:01Z).
- Files written at 23:34:53 (legacy end): work/derived/.rows/frames.jsonl 496,743,568,399 B (du 463G), structures.jsonl 1,062,994,740 B,
  prices.jsonl 17,393,149 B, work/legacy-cpu-split.json 1,496 B, note 112 B. work/legacy-state.pkl NOT rewritten (still the 22:36:09 save
  file, 1,405,815 B) -- the normal finish path does not write it (it is the save-route file).
- Native checkpoint 000005 re-written 23:39:21-22 under work/bedrock/recovery-6f84a8a86f454010b61346b401e3eb5f/checkpoints
  (driver-state 221,739,175 B gz); native-overlap/checkpoints.json 23:39:22.
- Bedrock ledgers growing (23:41:11): exact_member_rows.jsonl.assembling 159,551,869,608 B; exact_member_rows.append.jsonl
  93,432,257,457 B; exact_lifecycle_rows .assembling 3,878,460,948 / .append 2,189,020,608; legacy_observable_rows .assembling
  614,985,122 / .append 351,144,224.
- Disk /: 1.5T used, 535G avail (74%) -- down from 777G at 23:08:01 (242 GB in 33 min; frames +138 GB of it). frames spool 463G
  vs the drop-in's ~430 GB projection.
- RAM 247 G: used 12, free 56, cache 180, avail 235. CPUs 8, 9, 24 idle (legacy side free). Unit active; root-worker.json running
  23:40:50Z, running [2], pending 1.

## Disk-growth sample, box 23:41:33Z -> 23:42:18Z (SSM 0d127964-d0b3-4845-8d8c-e23ab74e1a86)
- / avail 572,583,915,520 -> 569,818,562,560 B: -2.77 GB in 45 s (~3.7 GB/min) with legacy finished (native-only writes).
- Native 640,193 -> 645,086 (4,893 in 45 s = 109 rec/s) -> ~565 KB of disk per native record.
- exact_member_rows.append.jsonl +1.344 GB and exact_member_rows.jsonl.assembling +1.343 GB in the same 45 s (the member rows go to
  both files). exact_member_rows.jsonl (final name) 0 B since 22:44.
- Linear projection: 126,701 native records left -> ~72 GB more -> ~498 GB free at native end (~00:01-00:02Z). Digest/layer writes
  after that are unmeasured on this day.

## Outcome
- Legacy pass FINISHED 23:34:53Z, 360,328/360,328 from the resume cursor (771,787 total), failed 0, 269,571 frame rows from the shards.
- SHARD EXIT HANG DID NOT OCCUR: all 14 shards (15281-15294) exited by themselves; ROOT not in do_wait. No SIGKILL sent; no process,
  unit or instance touched. Watch stopped at 23:44Z per the brief (legacy done, hang absent); native finish not awaited.
