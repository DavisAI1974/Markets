# Drop-in: Frankie, 2026-10-07 night, session 5 (handoff from session 4)

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie (Greg). THE AGENTS ARE THE ONLY WAY WORK RUNS.
1. git fetch origin ccr-d2f8f826-iefeah-frankie && git checkout -B ccr-d2f8f826-iefeah-frankie origin/ccr-d2f8f826-iefeah-frankie
   Confirm the tip is the commit named at the bottom of this file, or newer.
2. Read THIS file first, then the "Session 4" sections at the end of E2E_ONE_DAY_20231018.md (same directory).
3. Session = parent only; spawn agents with model "opus"; api-and-interface-design first; AWS via the Aws connector.
4. FIRST: probe run e2e-20231018-a2 on the main box (ROOT running on c9bf631). Watch the legacy finish (~23:35Z
   2026-10-07) for the shard exit hang (see "Watch"), then native (~00:00Z), then the digest.
```

## Run state at handoff (~23:00Z)
- Main box i-035994afa8bdf66a5 (us-east-1, r7i.8xlarge, 32 vCPU) RUNNING, KeepRunning=true (re-set 22:44Z).
- Run e2e-20231018-a2, attempt e2e-20231018-a2-20231018-a1, booking day-run-20231018-day_slot_root-1791402822-3111
  (CPUs 0-31). ROOT pid 14860 on code c9bf631 (/opt/frankie-box/code/c9bf631e884813adb79d263c80afd52a7fd9d837-37695921903-1/markets),
  native child 14929, queue unit frankie-queue-root-1791413028. R=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1.
- Progress: resumed 22:43-22:52Z from an exact save (native checkpoint 000005 at 283,338; legacy next record 411,459).
  Legacy ~140 rec/s (14 replica shards), native ~102-125 rec/s (book placement fix live; native ROOT CPU 1 is the limit).
  ETA legacy ~23:35Z, native ~00:00Z, then digest/layer writes (unmeasured on this day).
- Integration branch ccr-5fce7de3-xa4hfg = c9bf631. Work branch tip is newer (everything below).
- Disk ~859 GB free at 22:44Z (frames spool ~257 GB at 41%, ~430 GB projected). RAM fine.

## Watch
- SHARD EXIT HANG (in c9bf631): LegacyFrameShards._stop() terminate() is caught by the inherited SIGTERM handler, then
  join() waits forever (shards in anon_pipe_write, ROOT in do_wait). It hit the 22:32Z save. It may hit the legacy finish.
  Safe unblock (done 22:39Z): SIGKILL only the shard pids (children of the ROOT pid, wchan anon_pipe_write); the parent writes
  all rows, shards write nothing. Fix being built (agent "fix shard exit hang + spool resume"; see Open 1).
- A save/resume costs ~10-15 min today (frames spool re-hashed at save and twice at resume). Avoid unless needed.

## What landed in session 4 (work branch; SOURCE-BUILT, mostly RUNTIME-UNVERIFIED unless noted)
- AWS on the main box (applied, live): gp3 1250 MiB/s (vol-0d36715924f03b86c); S3 gateway endpoint vpce-0472311a451e2cedf
  (us-east-1 only; the bento bucket is us-east-2); awscrt in /opt/frankie-box/venv; read-ahead 4 MB, lazytime, dirty bytes
  2/16 GiB, THP always (reverts in E2E record). IOPS left at 16000 (Greg's call).
- ROOT (runtime-verified on a2): whole-core serial consumers; legacy frame rows on pinned replica shards (~140 rec/s vs
  ~25 in a1); save/resume across checkouts (content_rebinds; reader resumes at the saved cursor); native book placement
  fix (golden-ratio hash; aux policy V5); function-level native identities; restore materializers spread; dead workers
  redone with one fewer (Greg: never stop or hang on a dead worker); digest concurrency; probe/start-check/kick fixes.
- Newer than c9bf631 (NOT on a2's ROOT): native levers 976278a (pipelined replenishment, native_parallel V2, fast level
  copy, aux V6, faster checkpoint pickler, gc freeze; toy ~18% faster, byte-identical incl. 275367f->new resume).
- Later stages (reach a2 by a restage BEFORE each stage starts): teacher (encodings on 30 pinned workers, finish pool on
  31), classroom (native series on 32 processes, pictures encoded once), data/search (linear columns(), pinned decode and
  leakage gates), school/scientific teacher (one shared scan), exchange/Jev (cutoff read once on the lane before Jev; Jev
  and voice on the whole 32-CPU lane at 32 threads), ingest (DAY_CPUS up to 32/auto, pinned, pipelined).
- WIP SNAPSHOTS: several commits on the work branch are mid-edit snapshots (e.g. 5128a73 has a broken scientific-teacher
  half-edit). Stage only the TIP, never an intermediate snapshot.

## Open, in order
1. Agent running at handoff: shard exit hang + spool resume (no re-hash/re-count of the 257 GB frames spool). If the
   session ended, its uncommitted edits may be lost: check `git status`, re-run the task if needed.
2. Restage the work-branch tip (after 1 lands) BEFORE a2's teacher stage starts (after ROOT), so later stages get all the
   upgrades. Fast-forward ccr-5fce7de3-xa4hfg to the tip, stage, and let the queue continue.
3. The shared market timeline file (frankie_box_market_timeline.py) is hashed into a2's ROOT binding: do NOT edit it during
   a2. Requests queued for after a2: pool hang on a dead decode worker, double read of spools, single-core consumer limit,
   start-at-cursor (enables segmented replay for teacher/classroom/adviser).
4. Greg's open calls: (a) Jev/voice at 32 threads vs 16 (text changes with thread count; speed may not improve);
   flash-attention off for determinism? (b) search: should ID context fields (order_id etc.) become search cells
   (coupling jobs may be infeasible on a full day)? (c) skip re-hash on unchanged stat (export, school, adviser);
   (d) two-day hyperthread split in the CPU ledger; (e) classroom native cutoff rule (_check returns True after cutoff);
   (f) spool archive policy and region; render native tables into the digest; digest every day vs classroom days.
5. Whole-file identities still to make function-level: classroom_v2 exhaustion_d_code (bedrock), finalization.
6. Native next lever (designed, not built): snapshot replicas (~15-25%), adapter pipeline (~40%, needs checkpoint sync).

## Tip at handoff
(appended by the parent below)
- Work branch tip at handoff: a13b8b6 (this commit's parent carries all code; the fix agent's edits, if any, come after).
