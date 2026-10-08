# Box record, session 9 (2026-10-08): the CPU add to all 64 and the restart of a2 from exactly the same spot

Parent session (parent only; roles do the work; model fable). Greg's directive (16:2xZ, verbatim): "Definitely do the cpu
add now, retain all info to this point. Fix problem and restart from exactly the same spot." Then (drop-in box, this session):
"For this step we are about to stop, fix and restart, use all 64 cps for it and 64 workers."
Branch ccr-d2f8f826-iefeah-frankie, tip at open 734ba7d (fleet pass-2 NEW-1/NEW-2 fix) on 6ca48398 (the session-9 drop-in).
AWS: Aws connector live (STS read-only, account ...4170, root caller) 16:24Z.

## Orientation (parent, read-only, 16:24-16:3xZ)
- 16:24:09Z box i-035994afa8bdf66a5 RUNNING r7i.16xlarge (LaunchTime 15:02:19Z), KeepRunning=true, SSM Online (ping 16:21Z).
  Volumes vol-0d36715924f03b86c (root) and vol-004b68c077be09cc9 (archive) at baseline 3,000 / 125; the root volume's 12:08Z
  modification still `optimizing`, the archive's `completed`. Session 8's 18:20Z raise timer stands (not this session's).
- 16:26:45Z probe (SSM 0674a214, rc 0): up 1:24, load 1.34. R/calculations-receipt.json ABSENT. ROOT child 1834 (d67b9c63
  experiment_root --resume --data-workers 31 --digest off) Dl 1:22:10, 10.5% CPU, RSS 446 MB, psr 10; fd 3 =
  R/work/derived/legacy_book_imbalance.json pos 387,771,793,408 of 472,040,420,230 (ends ~16:37Z at ~131 MB/s); read_bytes
  643,495,780,352. Units: frankie-queue-root-1791471869 (root worker, d67b9c63, scope e2e-20231018-a2:20231018) and
  frankie-cpu-watch (d67b9c63, every 120 s) active. Watchdog 16:26:30Z bookings 1 findings 1 (unbooked 1 = itself) repins 0
  resize 0. Staged checkout /opt/frankie-box/code/46cfe9074bec6094653cf1f6df72d6bee76f05e6-37800918122-1/markets PRESENT with
  staging-receipt.json (status staged, commit 46cfe907, files 4128, pack e34d58d6..., intent a0febdd0...). df avail: / 787.6 GB,
  archive 1,714.97 GB. Q = /opt/frankie-box/work/frankie-queue.
- Expected (box record session 8, 15:55Z source check on d67b9c63): after the 472 GB layer the small layers, then
  load_retained_layers reopens the five spools whole (frames.jsonl 496.7 GB ~63 min at 131 MB/s) -> receipt -> exit 75 ->
  SAVED ~17:4xZ. The marker (15:27:22Z, sha 9f6b4e5b...) is the lawful stop; the child is never killed.

## Source facts read before the restart (parent, tip 734ba7d)
- frankie_box_cores.grow_locked: widens a live or retained day-run booking with free CPUs (lowest first), same id, recorded
  under `grown`; the holder's affinity is NOT changed (the next step runs under taskset of the new list; a running step keeps
  its own until the watchdog re-pins or it resumes). CLI `grow --booking ID --size 64 --reason TEXT`: exit 0 grown,
  75 waiting, 2 refused. lane_for('day-slot') accepts a retained booking whose size differs from the plan's day_cpus (32)
  ONLY when the booking was grown; Run.day_cpus() reads the held booking's live size -> 64 -> every stage's worker count
  = 64 - 1 (DATA_WORKERS=63 for ROOT: the pool plus one coordinator fill the 64 CPUs; the ledger's rule counts the
  coordinator: "the largest WORKERS that fit: size - 1").
- frankie_box_cpu_watch (resize=on, running since 15:04Z on d67b9c63): a `plan_wider_than_lane` finding (the resolver's
  planned lane wider than a RUNNING step's lane) drives a lawful save -> grow -> resume -> kick at the OWNER's commit
  (d67b9c63, the old code). So the grow must NOT be done while the d67b9c63 child runs on 0-31: it is done after SAVED,
  in the same script as the resume and the kick (seconds apart), so no watchdog pass sees a grown booking under a running
  step on the old code.
- frankie_box_frankie_queue worker: when its scoped day saves and nothing else runs, the root worker ends `saved` (exit 5)
  and releases its lock; kick then starts a new worker at the new commit. If the old worker is still alive at the kick,
  kick refuses ("a root worker runs ... covers the scope") and the OLD worker (old code) would admit the resumed day: the
  operator verifies the old unit is gone first (handover if not).
- Claims (5bf723f4): frankie_box_experiment_root.write_claims_from_derivation writes V2 rows (stat identity + 64 KiB tail +
  sealed counts for the five legacy spools) and returns a note for the receipt; the resume accepts V1 rows on a tail match
  and rewrites them. The claim decisions are read from the receipt's claims note, the ROOT log and work/file-claims.jsonl.
