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

## Box-operator: stop, grow, restart (16:4xZ)
Role: box-operator (fable), session 9, under the parent. AWS via the Aws connector only (SSM SendCommand / GetCommandInvocation).
- 16:34:13Z PROBE (SSM 553b8a3a, rc 0): receipt ABSENT; marker Q/save/e2e-20231018-a2-20231018.save-request.json 497 B 15:27
  standing (six .resumed-* markers beside it, history); child 1834 Rl 01:29:38 10.5% CPU on the exact cmdline (d67b9c63
  experiment_root --day 20231018 --resume --data-workers 31 --digest off --bedrock on); fd 3 = R/work/derived/
  legacy_book_imbalance.json pos 446,542,381,056 of 472,040,420,230; root.json seq 2 e2e-20231018-a2/20231018 state
  `running`, owner booking day-run-20231018-day_slot_root-1791402822-3111, save_request standing (by "dispatch save",
  requested 15:27:22Z, sha 9f6b4e5b..., cpus 0-31). Units: frankie-queue-root-1791471869 (worker, d67b9c63) and
  frankie-cpu-watch (d67b9c63 --loop --interval 120) active. The whole-read pass had not reached the frames spool: nothing on
  disk is lost by the stop (that pass writes only the receipt at its end).
- 16:34:31Z STOP (SSM bfb66780, rc 0): `kill -KILL 1834` (the child only); gone at 16:34:34Z. root.json: 16:34:38Z `running`
  -> 16:34:42Z `saved` (the worker's check_save). Worker log: "ROOT seq 2 20231018 (e2e-20231018-a2): saved: saved on its
  day-bound marker ... (attempt e2e-20231018-a2-20231018-a1, CPUs [0..31] retained)" and "day saved on its assigned lane;
  resume the retained attempt". Unit frankie-queue-root-1791471869 still active at 16:34:42Z (expected: it ends `saved`,
  exit 5, on its next poll).
- 16:35:16Z PROBE after the save (SSM 473bc88f, rc 0): unit frankie-queue-root-1791471869 GONE (0 root-worker units; the
  worker's last record 16:34:40Z state waiting_owner, pid 1758, worker_lock_held false). root.json seq 2 e2e-20231018-a2/
  20231018 state `saved`, owner booking day-run-20231018-day_slot_root-1791402822-3111, attempt e2e-20231018-a2-20231018-a1,
  save_request standing. Marker Q/save/e2e-20231018-a2-20231018.save-request.json 497 B 15:27 standing. Ledger
  /opt/frankie-box/cpu-bookings/day-run-20231018-day_slot_root-1791402822-3111.json: cpus 0-31, size 32, commit d67b9c63,
  `retained` {at 2026-10-08T16:34:31Z, attempt e2e-20231018-a2-20231018-a1, by_pid 1758, pids_at_retain [1758 booking holder,
  1834 step root], reason "the day is saved on its owner; its CPUs stay its own until ACTION=resume"}; owner {at 15:04:30Z}.
  Receipt R/calculations-receipt.json ABSENT (confirmed at 16:34:13Z, nothing wrote it since: the child died in the whole-read).
- 16:35:32Z CLEAN (SSM 4a56dbaa, rc 0): `systemctl stop frankie-cpu-watch.service` rc 0 -> inactive; its last loop line
  20261008T163431Z bookings 1 findings 1 (unbooked 1) repins 0 resize 0. No frankie-* unit active. nproc 64, online 0-63.
- 16:36Z HOLD (parent, Greg's new instruction): the grow, the resume and the kick were NOT run; the step-4 script was never
  sent. Greg wants the spool whole-count fixed in the source and the tip restaged before the restart (a new staged checkout,
  not 46cfe907). STATE AT HOLD: entry `saved`; booking day-run-20231018-day_slot_root-1791402822-3111 retained 0-31 (size 32,
  not grown); marker standing; receipt absent; no root worker, no watchdog, no ROOT child; the old checkout d67b9c63 and the
  staged 46cfe907 both present on disk, untouched. Box RUNNING, nothing killed beyond child 1834.

## Parent: the spool fix and the restage (16:3xZ-16:4xZ)
- Greg (16:3xZ, verbatim pieces): "save all data generated so we can start at exactly the same spot when you restart it
  after fixes"; "it's just our code that isn't allowing it so override blocker"; "if there are issues, save data first and
  then restart at same place when you restart"; "a go for any changes you might do getting to the workflow launch and then a
  go for workflow launch when it's ready. And fix spool before it starts"; "when workflow launches, switch down to opus";
  "if restage is long process use the 64 cpus" (it is ~6 min, single-process copy; the 64 go to the restart); "for the
  remaining root processes use 64 cpus".
- 16:35:34Z parent probe (SSM 8e042a91): the operator's hold landed; child gone, entry SAVED on the marker, booking 0-31
  retained (not grown), receipt absent, no frankie unit. Nothing grown/resumed/kicked.
- The spool issue (source read, tip 734ba7d..f20801a): the resume route in frankie_box_experiment_root.py called
  load_retained_layers without spools=, so RowSpool.reopen counted every line of the 496.7 GB frames spool (~63 min at
  131 MB/s) on every resume; write_claims_from_derivation added nothing to an existing claims file (a2's 57 V1 rows carry
  no spool rows). SOURCE-FIX role (fable): commit 2aed2f0e (frankie_box_experiment_root.py +80/-9; E2E doc section
  "Session 9: spool whole-count on the resume route"): rows ADDED for artifacts without one (the five legacy spools with
  sealed bytes/sha256, stat + tail, count + count_basis), existing rows untouched; the resume reopens each spool from its
  count via _legacy_spool_artifact + _reopen_counted_spool and hands spools= to load_retained_layers; receipt key
  spool_reopen names each spool's basis; a spool without a count or a holding claim is read whole ONCE, named. Parent
  review: the existing-row check and _load_file_claims use the same absolute-path key; _write_claims_atomic(target, bytes)
  matches; the claims are loaded after the note adds the rows; py_compile ok. RUNTIME-UNVERIFIED until the receipt.
- 16:43:35Z RESTAGE dispatched (github actions_run_trigger frankie_box_run.yml, script frankie_box_stage_code.sh,
  variables ACTION=stage, instance i-035994afa8bdf66a5, us-east-1): run 37811038079 (run_number 846) bound to head
  27109f4de339c4947e0149c8450c08df92f0ade2 = 2aed2f0e + session 8's closing record (.md only; verified: no non-.md diff
  between 2aed2f0e and 27109f4d; 2aed2f0e is its ancestor). NEW CODE_ROOT for the restart:
  /opt/frankie-box/code/27109f4de339c4947e0149c8450c08df92f0ade2-37811038079-1/markets, MARKETS_SHA 27109f4d....
- Restart operator spawned on model opus (Greg's rule from the launch on): wait for the stage receipt, verify the fix is in
  the checkout, then ONE script: grow the booking to 64, ACTION=resume, ACTION=kick FRANKIE_ROOT_DIGEST=on
  FRANKIE_CLASSROOM_CPUS=all (DAY_CPUS not given), then watch sparsely: receipt (claim decisions, spool_reopen), digest start.

## Box-operator (opus): the restart on 64 (16:5xZ)
- 16:45Z start: record read; run 37811038079 in_progress (head 27109f4d). Waiting for the stage before any box touch.
- 16:46:24Z run 37811038079 completed, conclusion success.
- 16:47:56Z PROBE (SSM 5bead97e, rc 0, read-only): staging-receipt status `staged`, commit 27109f4d..., files 4133,
  active_checkout_changed false; `git rev-parse HEAD` = 27109f4de339c4947e0149c8450c08df92f0ade2; `grep -c spool_reopen`
  frankie_box_experiment_root.py = 2 (the fix is in). State unchanged: root.json seq 2 e2e-20231018-a2/20231018 `saved`,
  owner booking day-run-20231018-day_slot_root-1791402822-3111 (attempt -a1, cpus 0-31); ledger cpus 0-31 size 32 commit
  d67b9c63 `retained`; receipt ABSENT; no frankie-* unit; no experiment_root process; nproc 64.
- 16:48:21Z GROW+RESUME+KICK script (SSM f324eef2, Failed rc 10): HEAD 27109f4d; `frankie_box_cores.py grow --booking
  day-run-20231018-day_slot_root-1791402822-3111 --size 64` exit 1 with a Traceback in the PRINT, after the grow was applied:
  `cmd_grow -> emit_outcome(a, outcome)` line 1066 `tag = dict(booked='CPU_BOOKING', waiting='CPU_BOOKING_WAITING',
  refused='CPU_BOOKING_REFUSED')[outcome['status']]` -> `KeyError: 'grown'`. The script's gate printed "GROW NOT DONE (exit 1
  ...); stopping here" and exited 10: show, resume, kick and status were NOT run.
- 16:48:35Z READ-ONLY CHECK (SSM 31a96e46, rc 0): the grow DID land. Ledger mtime 16:48:22, cpus 0-63 n 64 size 64 (commit
  still d67b9c63, the booking's own), `grown` [{from_size 32, to_size 64, added 32-63, at 16:48:22Z, by_pid 4745, reason
  "Greg 16:2xZ CPU add: a2 restart on all 64"}], `retained` unchanged (16:34:31Z, attempt -a1). Cause: cmd_grow's outcome
  status `grown` is missing from emit_outcome's tag map (a cosmetic print defect; exit 1 instead of 0). Entry still `saved`,
  marker standing, no unit, no child. STOPPED here per the instruction (no retry); reported to the parent. Remaining step is
  the resume + kick + status (the grow need not be re-run: the booking already holds 0-63).
- 16:49:32Z PARENT GO (16:49Z): run the rest of step 2 without the grow. SSM b7415ad3 (Failed rc 2): `show` read the
  booking on CPUs 0-27 in its first 30 lines (live idle; the head cut the rest; the ledger had 0-63). RESUME RAN: note "the next
  ROOT-line admission books exactly the retained CPUs and resumes attempt e2e-20231018-a2-20231018-a1; kick the root worker
  with this run/day in scope"; archived Q/save/e2e-20231018-a2-20231018.save-request.json.resumed-1791478174; owner
  booking day-run-...-3111, attempt -a1. Then MY OWN script defect: `${PIPESTATUS[0]}` is a bash-ism and AWS-RunShellScript
  runs sh -> "Bad substitution", the script aborted after the resume; the kick did NOT run (nothing else touched).
- 16:49:55Z KICK (SSM 4bf8d77c, rc 0): before it root.json seq 2 state `queued`, owner booking -3111 (owner record lists 32
  cpus). kick exit 0: frankie-cpu-watch.service started (27109f4d, correct=on resize=on, every 120 s for 43200 s); root
  worker unit frankie-queue-root-1791478195 (systemd-run), log Q/logs/root-worker.log, worker lock held; run_settings
  {FRANKIE_CLASSROOM_CPUS: all, FRANKIE_ROOT_DIGEST: on}; scope e2e-20231018-a2:20231018. STATUS: booking cpus 0-63,
  retained (16:34:31Z), alive false (pre-admission); marker standing false; owner code_root/commit now 27109f4d (owner.cpus
  still lists 0-31: the admission is to book the retained ledger, which holds 0-63; checked at the first probe).
- 16:52:54Z PROBE 1 (SSM 84d48966): units frankie-cpu-watch + frankie-queue-root-1791478195 active; NO experiment_root
  child; receipt absent; ROOT log tail unchanged since 15:05:48Z; cpu-watch 16:51:55Z bookings 1 findings 2 (unbooked 2 =
  the worker 4813 and the watch 4820 themselves, listed only).
- 16:53:06-16:53:40Z (SSM 7016e9e2, 8c6f5c09, 674d442f, read-only): worker pid 4813 sleeping (hrtimer_nanosleep, 1 thread),
  root-worker.json state running, pending 1, running [], 16:53:00Z; root.json seq 2 `queued` (reason "resumed by dispatch
  resume ... CPUs [0..31]"); root-events.jsonl: the last event is the 16:49:56Z kick, NO `take` (at 15:04 the take came
  within a minute of the resume).
- ROOT CAUSE (source read, 27109f4d): the worker can never admit the day. frankie_box_frankie_queue._book_slot books with
  cpus = owner.cpus (root.json owner binding: 0-31, 32 CPUs; the resume kept the binding as it was) and calls
  frankie_box_cores.book; book() (cores.py ~784-796) takes a retained booking back in place ONLY when
  `sorted(b['cpus']) == sorted(requested)`; the grown booking holds 0-63, so no match ->
  `dict(status='waiting', reason='the retained lane CPU set is still occupied')` -> the worker breaks and re-polls every
  60 s, forever. The grow (ledger 0-63, `grown` record) is not reflected in the queue's owner binding (owner.cpus,
  held_bookings, the last attempt's cpus: all 0-31). Harmless while it waits: the worker holds no booking and starts
  nothing. A fix is either source (the take-over matching a retained booking that was GROWN from the requested set, i.e.
  requested is a subset and `grown` records the added CPUs; or _book_slot reading the retained ledger set for an owned
  day) or a state edit of root.json owner.cpus. Both are outside this role; NOT done. Reported to the parent at 16:5xZ.

## Parent: the grown-booking take-over blocker (16:5xZ-17:0xZ)
- 16:49:34Z resume + 16:49:55Z kick ran on 27109f4d (operator record above); worker frankie-queue-root-1791478195 polls
  with pending 1, running []: `_book_slot` requests the owner binding's cpus 0-31 and `book_locked`'s retained take-over
  accepts only an EXACT set match, while the booking was grown to 0-63 at 16:48:22Z. Waiting forever, harmless (nothing
  runs, no booking held by the worker). The grow was built for the classroom boundary (the running day grows its own
  held booking); a grow of a RETAINED booking before its resume was never taken over. Greg: "it's just our code that
  isn't allowing it so override blocker".
- Source role (opus, Greg's usage rule) assigned: book_locked accepts a retained booking GROWN from the requested set
  (subset + the grown records' added CPUs), returns the full set; the queue records the grown set on the owner binding.
  Then: restage, then ACTION=handover LINE=root on the new checkout with FRANKIE_ROOT_DIGEST=on FRANKIE_CLASSROOM_CPUS=all
  (handover signals the idle old worker to end and starts the new worker at the new commit with the run settings:
  frankie_box_frankie_queue.handover carries _run_settings_env()), then watch.
- The grow printout defect (emit_outcome KeyError 'grown' after the ledger write) fixed on the tip: 1b4c909.
- 16:5xZ source role returned 0e2a568 (cores book_locked: a retained booking GROWN from the requested set is taken over
  on its full set, exact match preferred, orphan check over the full set, `resumed[-1]` carries requested/grown_to; queue
  _bind_owner keeps the old set as owner.cpus_before_grow; E2E doc section). Parent review: ok; py_compile ok. Confirmed by
  the role: day_cpus() reads the held booking (64); the ROOT child runs under `taskset -c <booking cpu_list>` from
  cmd_run_inside (frankie_box_cores.py ~1182-1201), so 0-63 with --data-workers 63.
- 16:57:32Z RESTAGE dispatched: run 37812835190 (run_number 847) bound to 0e2a568548cccac2e8e9bb500f0f07753819255b.
  CODE_ROOT for the handover: /opt/frankie-box/code/0e2a568548cccac2e8e9bb500f0f07753819255b-37812835190-1/markets.
- Operator (opus) continued: after the stage, ACTION=handover LINE=root SCOPE=e2e-20231018-a2:20231018 with
  FRANKIE_ROOT_DIGEST=on FRANKIE_CLASSROOM_CPUS=all on that checkout (the idle old worker 4813 ends on SIGTERM; the new
  --wait-lock worker takes the lock and admits the day on 0-63), then the receipt and the digest start.
- 16:58Z PARENT NEXT: take-over fix 0e2a568 in source; restage run 37812835190 (dispatched 16:57:32Z) staging
  0e2a568548cccac2e8e9bb500f0f07753819255b into CR2=/opt/frankie-box/code/0e2a568...-37812835190-1/markets. Plan: verify the
  stage, then ACTION=handover LINE=root on CR2 (old worker 4813 signalled; new --wait-lock worker), then watch.
- 17:01:01Z run 37812835190 completed, success.
- 17:01:59Z VERIFY + HANDOVER (SSM b6ef35f1, rc 0): staging-receipt `staged`, commit 0e2a568, files 4133; HEAD 0e2a568548cc...;
  `grep -c grown_to` cores.py 3, `grep -c cpus_before_grow` queue.py 1. State before: entry seq 2 `queued` (owner.cpus 32),
  ledger n 64 retained, worker 4813 running (17:01:08Z), receipt absent. HANDOVER exit 0: {"old_worker": 4813, "signalled":
  4813, "superseded_waiting": [], "new_unit": "frankie-queue-root-handover-1791478919", "systemd_run_exit": 0, "log":
  Q/logs/root-worker.log, "note": "the old worker finishes the days in its slots and ends; the new one waits on the lock,
  then runs"}. Status after: booking 0-63 retained (alive false), marker not standing, owner commit still 27109f4d (pre-take).
- 17:04:21Z / 17:04:42Z PROBES (SSM 8cdd9284, 4593435e, read-only) -- THE RESUME FAILED AND THE WORKER STARTED A FRESH ATTEMPT:
  - The new worker (unit frankie-queue-root-handover-1791478919, pid 5059, Environment FRANKIE_CLASSROOM_CPUS=all
    FRANKIE_ROOT_DIGEST=on MARKETS_SHA=0e2a568...) took seq 2 at 17:02:09Z on the retained booking -3111, now on 0-63 (the
    take-over fix worked: log "CPU_BOOKING inside the day's held slot day-run-...-3111: CPUs 0,...,63").
  - The ROOT at 17:02:13Z died at once: frankie_box_experiment_root.py line 428 `_calculate_day` ->
    `binding = save_or_match(output / 'source-binding.json', binding)` -> line 394 `raise ValueError('retained ROOT
    source/pin differs: %s' % path)` -> `ValueError: retained ROOT source/pin differs:
    /opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1/source-binding.json` (the -a1 source-binding pins
    calculation-pins.json sha 45e35f68... written under the earlier commit; the 0e2a568 binding differs).
  - 17:04:09Z slot_end "failed: no calculations-receipt.json (the attempt is kept) ...". The worker released the owner
    and booking -3111 (its ledger file is gone from cpu-bookings/) and, retrying once per worker start, at 17:04:10Z MINTED
    attempt e2e-20231018-a2-20231018-a2 on a NEW booking day-run-20231018-day_slot_root-1791479050-5059, CPUs 0-15,32-47
    (32, the plan's day_cpus), owner commit 0e2a568.
  - Child pid 5221 RUNNING: `frankie_box_experiment_root.py --commit 0e2a568... --day 20231018 --day-role discovery
    --output-root /opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a2 --data-workers 31 --digest on
    --shared-market-policy FRANKIE_SHARED_MARKET_TIMELINE_V1 --bedrock on` (NO --resume), affinity 0-15,32-47. A FRESH
    ROOT in a new directory, on 32 CPUs: not "the same spot", not 64. The -a1 directory is still on disk, untouched.
  - Not killed (role limit). Reported to the parent at once.

## Parent: the binding refusal and the from-scratch -a2 (17:0xZ)
- 17:01:59Z handover on 0e2a568 ran; 17:02:09Z the new worker took seq 2 on the grown booking 0-63 (the take-over fix
  worked); 17:02:13Z the ROOT child died: source-binding.json 'retained ROOT source/pin differs' (operator record above,
  traceback verbatim). CAUSE (parent, source): the binding dict carries data_workers; the saved -a1 binding says 31, the
  64-CPU child came with 63; content_rebinds treats any non-path difference as an identity refusal. The worker count is a
  run-size parameter, not calculation identity. The worker's retry-once rule then minted attempt -a2 FROM SCRATCH on 32
  CPUs (no --resume): the opposite of the directive.
- 17:06:07Z PARENT KILL (SSM 2d4e9386): child 5221 (-a2) SIGKILLed after ~2 min; R2 dir 28 MB, kept as an interrupted
  attempt (never deleted). R1 (-a1) untouched: derive.json and legacy-stage.json present.
- Source role (opus) assigned: (1) a changed data_workers is a recorded run-size rebind, never a refusal; the Session
  sizes helpers from this run's count (63 on 64); (2) a committed repair tool frankie_box_queue_repoint.py: re-point the
  entry to attempt -a1 on a retained booking rebooked for the owner and grown to 64, owner binding as _bind_owner mints
  it, state unknown; then ACTION=resume + kick/handover on the restaged tip.
- 17:08:52Z parent probe (SSM 14294853): entry failed, ownerless; worker 5059 ended stopped_at_failed 17:06:10Z, lock free;
  both bookings released; only frankie-cpu-watch (27109f4d) runs; -a1 intact, -a2 28 MB kept.
- 17:1xZ source role returned 1c59623: save_or_match(run_size=('data_workers',)) for the source binding only (a
  difference recorded as a run-size rebind in checkout-rebinds and the receipt; the saved binding stays the identity);
  Session._data_workers() takes requested_data_workers (none of the three sites run on the resume route; the resume
  digest sizes from the lane: 62 table helpers + main/side on the coordinator core of a 64 lane, 63 parts); the repair
  tool frankie_box_queue_repoint.{py,sh} (rebook_for_owner at the plan's 32, grow to 64, owner binding as _bind_owner
  mints it, state unknown; refuses on a live owner/booking or a wrong state). Parent review: ok.
- 17:13:12Z RESTAGE dispatched: run 37814850954 (run_number 848) bound to 1c59623c81287c43b0ff45b95c50d0f6b79947bc.
  CODE_ROOT: /opt/frankie-box/code/1c59623c81287c43b0ff45b95c50d0f6b79947bc-37814850954-1/markets.
- Operator (opus) continued: stage -> repoint -a1 SIZE=64 -> ACTION=resume -> ACTION=kick (digest on, classroom all) ->
  watch the child's first minute, the receipt (claim decisions), the digest start, then the teacher.
- 17:1xZ PARENT NEXT: -a2 child killed by the parent 17:06:07Z (entry seq 2 `failed`, ownerless; bookings -3111 and -5059
  released; R1 -a1 intact). Fix 1c59623 (data_workers difference = recorded run-size rebind; repair tool
  frankie_box_queue_repoint.sh); restage run 37814850954 (17:13:12Z) -> CR3=/opt/frankie-box/code/1c59623...-37814850954-1/
  markets. Plan: verify, then repoint -a1 on 64 + resume + kick, then watch the first minute closely.

## Parent: Greg's one-pass question and the boundary validator (17:2xZ)
- Greg: "I thought the validation was the source binding? Isn't this a double pass with just a different name?" Answer
  from source: the source-binding check (save_or_match) is a document compare, no data read. The ROOT stage-boundary
  validate (frankie_box_root_validate via frankie_box_stage_handoff.run_validate, session 6, Greg's order then) re-reads
  EVERY pinned artifact whole (~1.2 TB on a2: frames spool, inline layer, native ledgers) and takes no file claim: a
  second full pass under another name (~20 min on 64 after the volume raise; ~2.5 h at the baseline rate).
- Source role (opus) assigned: the validator takes the FRANKIE_FILE_CLAIM_V2 rows (bytes/sha256 equal to the pin, stat +
  64 KiB tail hold -> verified by claim; spools need the row's count), FRANKIE_ROOT_VALIDATE_CHECK=full restores the
  whole reads; recorded per file in validate.json. To apply it to this day: a save marker after the ROOT's receipt +
  digest (calculate_day's post-return check), then resume + kick on the restaged tip, so the boundary runs the
  claim-taking validator. Decision on applying it to this day: pending the digest's progress and Greg's word.
- 17:15:53Z run 37814850954 completed, success.
- 17:18:10Z VERIFY + REPOINT + RESUME + KICK (SSM 104d85f5, rc 0): staged, commit 1c59623; HEAD 1c59623c8128...; repoint.sh
  present; `grep -c run_size` experiment_root.py 7; only frankie-cpu-watch unit; 0 experiment_root processes; entry seq 2
  `failed`, no owner. REPOINT exit 0: {"status": "repointed", "attempt": "e2e-20231018-a2-20231018-a1", "booking":
  "day-run-20231018-day_slot_repoint-1791479892-5613", "cpus": 0-63, "size": 64, "state": "unknown", "route":
  "rebook_for_owner at the plan size 32 (...-5613), grown to 64 (16-31,48-63)"}. RESUME exit 0: note "the next ROOT-line
  admission books exactly the retained CPUs and resumes attempt e2e-20231018-a2-20231018-a1"; archived []; owner attempt
  -a1, booking -5613, bound 17:18:13Z, code_root/commit 1c59623. KICK exit 0: "frankie-cpu-watch already runs; nothing
  started" (that watch is still the 27109f4d one); root worker unit frankie-queue-root-1791479893, worker lock held.
  STATUS: booking -5613 alive true, cpus 0-63, retained null; marker not standing; owner -a1, cpus 0-63, commit 1c59623.
