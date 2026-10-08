# Drop-in: Frankie, 2026-10-08 early, session 6 (handoff from session 5)

## Drop-in box (paste into the new session)

```
NEW SESSION -- Frankie (Greg). THE AGENTS ARE THE ONLY WAY WORK RUNS.
1. git fetch origin ccr-d2f8f826-iefeah-frankie && git checkout -B ccr-d2f8f826-iefeah-frankie origin/ccr-d2f8f826-iefeah-frankie
   Confirm the tip is the commit named at the bottom of this file, or newer.
2. Read THIS file first, then the "Session 5" sections at the end of E2E_ONE_DAY_20231018.md and the ten
   STACKS_PASS_20261007_*.md records (same directory; each has an audit table, changes with file:line, tests, open items).
3. Session = parent only; spawn agents with model "fable"; api-and-interface-design first; AWS via the Aws connector.
   Permission mode: Greg switched the session OUT of Auto so removals on the box can be relayed; check the mode first.
4. FIRST: probe the main box: the a2 hold (did the queue save land after ROOT's digest?), the disk (archive volume, what
   was moved/removed), KeepRunning=true. Then restage the work-branch tip and resume a2 at the teacher stage.
```

## Run state at handoff (~00:12Z 2026-10-08; update at the end of session 5 if later)
- Main box i-035994afa8bdf66a5 (us-east-1, r7i.8xlarge, 32 vCPU) RUNNING, KeepRunning=true.
- Run e2e-20231018-a2, attempt e2e-20231018-a2-20231018-a1, booking day-run-20231018-day_slot_root-1791402822-3111
  (CPUs 0-31), ROOT pid 14860 on c9bf631, native child 14929, queue worker 14824, unit frankie-queue-root-1791413028.
  R=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1.
- Legacy pass FINISHED 23:34:53Z WITHOUT the shard exit hang (269,571 frame rows from the replica shards, 0 in the
  replay; shards exited through close()). Native ~00:05Z. Then ROOT's layer write (legacy_book_imbalance.json re-encodes
  the WHOLE 497 GB frames spool, ~8 GB/min, ends ~00:44Z), legacy-stage.json, native join/reuse, projection, digest,
  receipt. The digest's cost on this day is unmeasured.
- THE HOLD (Greg: pause ROOT when done so the teacher does not start on c9bf631): the queue's own ACTION=save marker is
  honoured at the ROOT->teacher boundary (frankie_box_frankie_queue.py:1335-1346 check_save before run.teacher). The
  hold agent arms an on-box watcher that fires `ACTION=save RUN=e2e-20231018-a2 DAY=20231018` once R/progress.json
  stage is root-projection or later (after boss_session.py:3026's last mid-run save check), so ROOT completes and exits 75
  on "ROOT completion published"; the entry becomes saved, booking retained, no teacher. Resume = ACTION=resume then
  ACTION=kick on the restaged tip; Run.root reuses the completed receipt and goes to the teacher. After the hold the
  worker clears KeepRunning: re-set it to true (ec2 CreateTags) before the idle guard (cron 17 */6: 06:17Z next).
- DISK: the layer write would have filled the 2 TB root volume (~0 GB free at ~00:37-00:44Z). Root volume growth is
  blocked by the 6 h EBS rule until ~04:12Z. Fix in flight: archive volume vol-004b68c077be09cc9 (gp3 2048 GiB, 1000
  MiB/s, 10000 IOPS, encrypted with the root's KMS key, ~$234/month, DELETE or downsize after the data is archived to S3
  per Greg's call (f)) attached at /dev/sdf, ext4 label frankie-archive, mounted /opt/frankie-box/archive (fstab nofail;
  backup /root/fstab.before-archive-20261008T000343Z). Plan: copy (tar.zst or rsync, verified) then remove the
  Monday root monday-calculations/full-20211004-20260927-r1-48 (427 GB, no open fd, no a2 reference), other-day
  ingest-* (~122 GB), days-2026092x/0930 roots (~84 GB), teacher rows (25 GB), non-referenced code checkouts,
  transfer tarballs, caches. NOT removed: day-external (a2's external.json references it), checkouts 98579cea/
  275367fe/18cbc5a4/c9bf631 and the running worker's, the 66 GB pre-save ledger copy bedrock/ledgers/
  exact_member_rows.jsonl (checkpoint 000005 names it), everything under a2's attempt and ingest-20231018.
  Record: the hold agent's scratchpad record (session 5) and the E2E record's Session 5 sections. CHECK what landed.
- Integration branch ccr-5fce7de3-xa4hfg = c9bf631. Work branch tip is far ahead (everything below). NOT restaged yet.

## What landed in session 5 (ALL SOURCE-BUILT / RUNTIME-UNVERIFIED; toy self-tests only; all in the pushed tip)
- ROOT: shard exit hang fixed (SIG_DFL in shards, bounded stop with kills recorded); spool save/resume without re-hash
  (resumable SHA-256 state via OpenSSL, stat+last-line fast path, one-pass fallback, INPUT row cursor seek, seal checks,
  INPUT-spool claim check); _PinnedPool bounded; native auxiliary worker stop bounded. Reviewed twice: APPROVED
  (REVIEW_20261007_ROOT_SHARD_SPOOL.md). Native checkpoint accepts the function-level finalization identity (a2's
  checkpoints restore on the new tip).
- Shared pin helper frankie_box_lane_pin.py: SIGTERM reset in every worker, bounded end_pool/end_executor, RedoPool,
  exclude_sibling option, record() keys. Every piece now uses it.
- Every piece (teacher, classroom, data/search, school, exchange/Jev/meeting, reports/inspection/finalization, ingest,
  Run controller) audited and fixed against: Sept-29 template (HANDOFF_20260929_EXPERIMENT_BUILD.md "Speed items 1-5 +
  resume"), optimizer stacks, CPU/worker plumbing, AWS transport (shared frankie_box_s3_transport.py: ranged 16 MiB GETs,
  CRT-first, receipt transport), day-1 visibility, dedupe (compute/pass/content), "Additional CPU spots" ranked, and
  ROOT's save/restore contract (save route exit 75, periodic exact saves, positions without re-read, content_rebinds,
  function-level identities, old saves load, seal). Defects found: Jev refused any lane not exactly 16 CPUs (fixed);
  ingest pass-1 saves were never written until pass 1 ended (fixed); broken encoder pool crashed the ingest (fixed);
  several inherited-SIGTERM pool hangs (fixed). Run controller: exit 75 = saved for every child step, probe dirs per
  stage, ingest booking retained on save, KillMode=mixed on stage units.
- Search memory: frames are typed on-disk columns by default (option B) with a DIGEST_V10 option A; chunk boundaries are
  save points; canary script deploy/aws/box/frankie_box_search_columns_canary.py (needs Greg's go to run on the box).
  Cell/job count is a receipt number before jobs are generated.
- Greg's decisions this session: Jev re-do rule APPLIES (interrupted Jev call re-sent byte-identical; "never retried"
  superseded); search memory redesign GO; new agents on model fable; every piece follows its faster sibling's Sept-29
  template; dedupe in every step; save/restore matches ROOT's; stream data to the next step instead of dumping it.
- In flight at handoff: ROOT owner converting the whole-spool layer hand-off to a streamed REFERENCE layer with one
  shared loader (for day 2; a2's layer is the old form). Check its record section in E2E_ONE_DAY_20231018.md.

## Open, in order
1. Confirm the hold landed and the disk was freed; re-set KeepRunning=true; archive-volume policy (keep until S3).
2. RESTAGE: fast-forward ccr-5fce7de3-xa4hfg to the work-branch tip (compiles; every WIP snapshot was syntax-checked but
   the pass has NOT run anywhere), stage, ACTION=resume + ACTION=kick a2; watch the teacher stage with probes. Expect
   runtime defects: everything is runtime-unverified. The market timeline file frankie_box_market_timeline.py is
   unchanged (frozen for a2); its queued requests (start-at-cursor, dead decode worker hang, double spool read, consumer
   sibling) open after a2.
3. Box canaries on Greg's go (CPUs free): ingest canary (STACKS_PASS_20261007_INGEST.md section 8), search columns canary.
4. Greg's calls still open: (a) Jev/voice threads 32 vs 16, flash attention; (b) ID context fields as search cells (count
   now visible); (c) skip re-hash on unchanged stat; (d) two-day hyperthread split; (e) classroom native cutoff rule;
   (f) spool archive policy/region (archive volume exists now); content dedupe of pinned evidence files (lessons,
   survivors, school, reports, coupling parts: a new rendering changes bytes other stages compare); the seal check on the
   BEDROCK=off route (parent's call, one full read, reversible); digest every day vs classroom days.
5. Greg (2026-10-08 00:2xZ, to discuss later, not decided): for the 30-day run with ONE BOX PER DAY, a day may have to keep
   its good data with it on its box. Sizing fact from a2: one day's ROOT wrote ~497 GB frames spool + ~497 GB whole-spool
   layer copy (old form) + ~290 GB native ledgers + digest (unmeasured) on a 2 TB root volume and ran out; the streamed
   reference layer (in flight) removes the copy. Decide the per-box disk and the archive policy (f) together.
   Greg's option (2026-10-08 00:2xZ): for pieces with big outputs, RUN -> PAUSE (the queue save marker: exit 75 at the piece's
   next boundary, every piece now carries ROOT's save/restore contract) -> CLEAN (MOVE finished data to the archive volume,
   zip it, symlink/reference at the old path so pins and receipts still resolve; never delete pinned inputs) -> RESTART on
   the same day's data; possibly twice per piece. Not the routine once the streamed reference layer lands; the fallback
   for inherently large outputs (frames spool, native ledgers, search columns).
6. Cross-owner requests recorded in each STACKS_PASS file (school R2 one teacher child per batch needs a repeatable
   ledger CLI; exchange X6 Jev request binds the commit; teacher anchor-pictures hand-off; reports 99-layer join pool).

## State at the session-5 close (~00:48Z 2026-10-08; the box work below was IN FLIGHT when the session closed: VERIFY FIRST)
- Greg at close: "just save data and do handoff and drop in. We'll clean in next session."
- ROOT a2: native stage complete 00:15Z; the layer write (legacy_book_imbalance.json, old inline form, ~497 GB) was at ~333 GB
  at 00:28Z, 8.1 GB/min, ending ~00:48Z; then legacy-stage.json, native join/reuse, projection, digest, receipt. The HOLD
  watcher (queue ACTION=save on stage root-projection or later) was armed in 265 s rounds; if the session ended between rounds
  the box is UNARMED: re-arm it (script text in the hold agent's record, copied below in spirit) or, if ROOT already completed,
  check root.json: did the teacher start on c9bf631? If it did, decide with Greg (the teacher on old code; a restage mid-stage).
- DISK: free space was 67 GB at 00:40Z falling 8.1 GB/min. A detached disk guard (/opt/frankie-box/archive/.logs/disk-guard.sh,
  log .logs/disk-guard.log, pid list .logs/disk-guard.frozen-pids) SIGSTOPs ROOT 14860's whole tree below 15 GB free and
  exits. FIRST CHECK: `ps -o pid,stat,wchan,args -p 14860` and its children: state T means FROZEN. If frozen: free space must
  be above 100 GB (see the removals below), then `kill -CONT 14860` first, then its children (deepest last), and confirm the
  layer file grows again. Frozen is safe; nothing is lost.
- ARCHIVE: vol-004b68c077be09cc9 (gp3 2048 GiB, 1000 MiB/s, 10000 IOPS, ~$234/month) mounted /opt/frankie-box/archive.
  The Monday root monday-calculations/full-20211004-20260927-r1-48 (427.3 GB) was archived as ONE tar.zst (297,465,977,258 B,
  tar totals 427,265,044,480 B, zstd rc 0, sha256 recorded in <archive>.sha256). Greg stopped its second verification pass
  (the decompress-list) and ordered the source removed on the completed checks; the agent was executing that at close: CHECK
  whether the source directory is gone (symlink + README at the old path) and df -B1 /. A parallel batch (3 pinned idle CPU
  pairs, one tar.zst per directory, verified, then removed) was running over 50 jobs: other-day ingest-* dirs, teacher rows,
  days-2026092x/0930 roots, the retired a1 attempt, 7 non-referenced checkouts, transfer tarballs; log archive/.logs/batch.log.
  NOT removed, must stay: day-external, checkouts c9bf631/98579cea/275367fe/18cbc5a4 and their transfer-*, the 66 GB
  pre-save ledger copy (checkpoint 000005 names it), everything under a2's attempt and ingest-20231018.
- KeepRunning=true was set at close; after the hold lands the worker clears it: re-set before the idle guard (06:17Z).
- Archive-policy lesson (Greg): per-subdirectory archives so compression/verification use many CPUs; sha256 on the write
  stream and the listing from tar -v at creation; exactly ONE read-back pass, never two; zstd -T0 on an idle lane; pin to
  measured-idle sibling pairs; ionice is a no-op under the NVMe none scheduler, manage contention by concurrency; keep a disk
  guard armed whenever a stage writes a file comparable to the free space.
- Session 5 also landed (source): spool layers streamed by reference (frankie_box_layer_spool.py, FRANKIE_LAYER_SPOOL_REF_V1,
  one shared loader, old layers load; ROOT preflight projects finalize bytes). It reaches a run only by the restage; it removes
  the 497 GB layer copy that caused tonight's disk problem.
- Session-5 scratchpad records (hold agent, probe, tests) live only in session 5's container; everything durable is in the
  E2E record's Session 5 sections, the STACKS_PASS files, the review file and this drop-in.

## Tip at handoff
(appended by the parent at the end of session 5; see the last commit on the branch)
- Work branch tip at handoff: a26a176 (this line is in the next commit, which is the tip to confirm or newer).
