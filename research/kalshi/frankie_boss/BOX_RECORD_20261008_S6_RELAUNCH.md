# Relaunch role record, 2026-10-08 (session 6): run e2e-20231018-a2 day 20231018, ROOT save -> rows-dir -> resume+kick -> watch

Box i-035994afa8bdf66a5 (us-east-1), SSM AWS-RunShellScript via the Aws connector (SendCommand + GetCommandInvocation).
R=/opt/frankie-box/work/experiment-roots/e2e-20231018-a2-20231018-a1. Q=/opt/frankie-box/work/frankie-queue.
Restaged tip on the box: CODE_ROOT=/opt/frankie-box/code/b474c51ede1066e0ffc0960995a2fdb836607057-37714898818-1/markets,
MARKETS_SHA=b474c51ede1066e0ffc0960995a2fdb836607057. Old (running) checkout: c9bf631e...-37695921903-1/markets.
Local repo tip read: a435d06 (WIP snapshot; the box's b474c51 is the staged tip). Docs read: E2E_ONE_DAY_20231018.md
"Session 6: ROOT validate -> stop -> clean -> trigger"; frankie_box_frankie_queue.sh header; HOLD_20261008.md 3.x;
CLEAN_PREP_20261008.md (step 0 rows-dir); PROBE_20261008.md.

## Step 1: read-only probes (one SSM command each)

### Probe 1, command ddb1ac93-6ebf-48ba-b889-5637cf9a1cad, 01:55:22Z: NOT SAVED
- R/calculations-receipt.json: absent. derivation-digest-full.md: absent.
- progress.json: stage root-digest, state running, at 1791423186.6 (01:33:06Z), completed 0, total null. Digest elapsed 22 min 16 s.
- ROOT log last line 01:33:06Z ("43/44 layers derived ... sections 4.2 derived (28 rows), 4.4 derived (1167376 rows)").
- ps 14860: Sl, elapsed 03:11:30, 39.9% CPU, RSS 640,088 KB; 31 children (digest workers). load 30.07.
- root.json seq 2: state running, finish null, save_request = marker identity (requested 01:20:55Z, sha e5c639e0...),
  retained_booking day-run-20231018-day_slot_root-1791402822-3111, child null. owner commit c9bf631, attempt
  e2e-20231018-a2-20231018-a1, cpus 0-31.
- booking file: present (3007 B), cpu_list 0-31, retained null, release null, pids 14824 holder + 14860 step root. No released record.
- save/: marker e2e-20231018-a2-20231018.save-request.json standing (498 B, 01:20Z) + 3 archived .resumed-*.
- events tail: last = save_requested 01:20:55Z (pid 56373). worker 14824 Ssl 03:11:33, root-worker.json running, pending 1, running [2].
- teacher procs: none. units: frankie-queue-root-1791413028 only (active running).
- ACTION=status (c9bf631 checkout): verdict "save pending acknowledgment"; booking alive True retained None; marker standing True; clean None.
- checkouts: b474c51e...-37714898818-1 present (01:52Z), HEAD b474c51ede1066e0ffc0960995a2fdb836607057 (verified);
  stage_handoff.py 35,129 B, root_validate.py 40,638 B, root_move.py 23,510 B present. ebc7ef38 (01:49Z) also present.
- experiment-teacher-rows: still the symlink -> archive/work/experiment-teacher-rows.tar.zst.
- df: / avail 599,154,561,024 (used 1,529,868,869,632); archive avail 1,725,022,760,960. KeepRunning tag = true.

### Wait-probe 2 (01:55:5xZ): the run_script tool timed out at 60 s (the command ran on the box; output not collected). From
here each SSM command is sent in one call and fetched in another.

### Digest probe (Greg: "check with root to see what the delay is"), command ce4ee3ab-34ba-44cf-a3f3-6c639e631ef3, 01:57:34Z
- 14860 Sl 39.5% CPU elapsed 03:13:43 RSS 640,088 KB; fds: families.sqlite, table-0002/table.sqlite, 2 deleted, root.log x2.
- 31 children 59921-59957 (spawn_main helpers), ALL state R, 99.4-99.6% CPU each, elapsed 24:26-24:27, RSS ~243-253 MB,
  TIME+ 24:22 each; each holds ONE fd on work/derived/.rows/frames.jsonl (496,743,568,399 B). 56407 = resource_tracker (S).
- io 20 s apart (01:57:34 -> 01:57:54): 59921 read_bytes 13,398,827,008 -> 13,583,376,384 (+184,549,376 = 9.23 MB/s);
  59924 13,176,254,464 -> 13,356,609,536 (+180,355,072 = 9.02 MB/s); write_bytes 0 for both; 14860 flat
  (read 3,848,849,846,272 / write 1,146,901,606,400). Aggregate ~286 MB/s over 31 helpers: CPU-bound decode, not I/O.
- scratch .digest-bb89b168639a4b768e3a21df0f79ab04: du 54,009,340 B at both samples (flat). Files: families.sqlite 12,288
  (01:33:06), table-0002/table.sqlite 8,192 (01:33:06), table-0000/table.sqlite 18,419,712 + table-0000.txt 1,901,761 +
  table-0000.save.json (01:33:18-19), table-0001/table.sqlite 32,972,800 + table-0001.txt 659,276 + save.json (01:33:27-29).
- R/note and the log: last line 01:33:06Z (43/44 layers derived ...). progress.json root-digest, at 01:33:06Z, unchanged.
- top: 31 running, 93.6% us, 0.0 wa; mem 253,663 MiB total, 6,225 free, 240,828 buff/cache; no swap. load 30.02.
- Code (c9bf631: frankie_box_digest_document.write_digest + frankie_box_digest_parallel.write_table_parallel): legacy
  tables in order 0 legacy_price, 1 per_second_flow_and_roll20, 2 legacy_book_imbalance (= the frames spool; parallel
  writer, spool_specs cuts it into `parts` line-aligned ranges, 31 here = 16.02 GB each), 3 legacy_structure_observables
  (serial, context from table 2 via cross_context), 4 structure_families; then the bedrock tables from ordinal 5.
  Parallel passes, each a full re-decode of the part (json.loads + c15_journal.unpack per line): cross_context (the
  context job, submitted first), snapshot (nothing written), plan (freq.sqlite counts), merge (no read), final (rows.txt
  written), copy (parts appended to the table), verify (full read + decode of the written table). Only `note` callbacks
  (in-memory notes list) mark the passes: the probe stage stays 'root-digest' the whole time.
- Placement: 13.4-13.6 GB of a 16.0 GB part read after 24.5 min -> the first full pass (cross_context or snapshot) ends
  ~02:02Z. Each further pass ~29 min at 9.2 MB/s per helper. Remaining for table 2: 4 passes (~116 min) + copy; then
  tables 3, 4 and 44 bedrock tables (bedrock.members single-core). Estimate given to main: saved not before ~04:00Z,
  likely 04:00-05:00Z; the biggest consumer = five CPU-bound decodes of the 496.7 GB spool at ~9 MB/s per core.
- Reported to main 02:00Z (SendMessage).

Parent update (02:00Z): a third stage is in progress for tip 7468399; at save time resume on the newest staged checkout
whose HEAD is 7468399... if present, else b474c51 as briefed, and say which.

### Poll 3, command 3859debe-24a3-460c-bfee-3ab636139b59, 02:00:14Z: NOT SAVED
- receipt absent; progress root-digest (01:33:06Z); 14860 Sl 03:16:23 39.0%; 31 children, 30 in R.
- 59921 read_bytes 14,862,639,104; 59924 14,619,095,040 (part ~16.02 GB: first pass ends ~02:02Z).
- scratch: table-0002.parallel/ with 31 part dirs (part-0000 EMPTY: the no-write pass), table-0002/table.sqlite 8,192; du 54,009,340 (flat).
- entry running, finish None, save_request True; teacher 0; unit frankie-queue-root-1791413028 active running.
- checkouts: 74683990d5e7a0f34ee758e6077ce5c59060fe14-37715548798-1/markets dir created 02:00:10Z, `git rev-parse HEAD`
  fails (not yet populated: landing). b474c51 (01:52), ebc7ef38 (01:49), c9bf631, 275367fe, 98579cea, 18cbc5a4 present.
- df / avail 598,148,874,240; archive 1,725,022,760,960.

Note (02:04Z): 7468399 = origin/ccr-d2f8f826-iefeah-frankie tip ("Stage handoff complete: bind mount for guarded prefixes,
Glacier second copy after the trigger, redundant native segments ..."); its frankie_box_frankie_queue.sh contract is the
same (ACTION=resume RUN DAY [REBOOK]; ACTION=kick LINE SCOPE; MARKETS_SHA checked against `git rev-parse HEAD`). Its
clean_action order: note beside marker (running) -> wait_saved (bound 1800 s) -> M.clean (move / archive / bind_mount
items) -> clean/clean-receipt.json -> trigger (resume + kick on the launching checkout) -> trigger.json + marker note ->
S3 Glacier second copy AFTER the trigger (receipt beside the clean receipt; a refusal is recorded, never a failure) ->
keep_running(True). Watch order after resume: handoff/<day>/root/handoff.json (validating) -> validate.json ->
handoff.json saved + save marker -> entry saved (worker exit) -> frankie-clean-* unit -> clean-receipt.json ->
trigger.json -> new frankie-queue-root-* worker -> teacher.

### Poll 4, command 01d6a2b3-0d98-49d0-b188-50b9f19325e4, 02:04:47Z: NOT SAVED
- progress root-digest age 1901 s; 14860 Sl 03:20:56 38.1%; 31 children, 30 R; 59921 read_bytes 17,317,380,096 (> the
  16.02 GB part: pass 1 = cross_context ended ~02:02Z, pass 2 = snapshot ~1.3 GB in), write 0; part-0000 empty, no
  passes.pkl; du 54,009,340 flat. entry running / save_request True / retained booking. teacher 0; one unit.
- 7468399 checkout LANDED: /opt/frankie-box/code/74683990d5e7a0f34ee758e6077ce5c59060fe14-37715548798-1/markets, HEAD
  74683990d5e7a0f34ee758e6077ce5c59060fe14, stage_handoff.py present. -> the resume target (per the parent's 02:00Z update).
- df / avail 597,127,856,128; archive 1,725,022,760,960; load 30.01.

## Plan change (02:06Z, Greg: "That works"; "Just move it manually this time"): A-E

### A. What the worker does when the ROOT child dies with the marker standing (c9bf631 source, read-only)
Snapshots verified byte-identical to git (sha256 ex_c9bf631.py 49d142f1... = git show c9bf631:deploy/aws/box/
frankie_box_experiment.py; q_c9bf631.py 37712adc... = frankie_box_frankie_queue.py).
- frankie_box_experiment.py Run.child() 1257-1330: Popen the step (1307), `code = proc.wait()` (1311), heartbeat.stop in
  the finally (1316-1317), then line 1320 `self.check_save()` UNCONDITIONALLY, before the exit code is interpreted.
  check_save (1113-1116): `if self.save_requested(): log(...); raise SystemExit(75)`; save_requested (1096-1098) = the
  owner's marker file exists (stop_marker = owner['marker'], 1094).
- Run.root() 1542 `code, log = self.child('root', ...)`: the SystemExit(75) propagates out of root() BEFORE 1543-1551 (the
  'failed' record for a non-zero exit without calculations-receipt.json) and before claim_end (1544): nothing is recorded
  for the attempt, nothing released.
- frankie_box_frankie_queue.py _root_job 1647-1672: `r = run.root(e)` (1654) raises; `except (Exception, SystemExit)`
  (1670) -> _thread_end(error, facts, holder, entry, run, 'failed') (1570-1576): error.code == 75 and
  run_obj.save_requested() -> _save_result (1579-1591): holder['result'] = ('saved', 'saved on its day-bound marker
  <marker>', facts) (no class child -> not 'unknown').
- _end_slot (1628-1644, the finally at 1672): result in OWNER_STATES -> C.retain(slot, run, day, attempt=owner.attempt,
  reason='the day is saved on its owner; its CPUs stay its own until ACTION=resume'); holder['retained'] = the booking.
  (A 'failed' result would instead _release_slot at 1644: that path is NOT taken because child() raised first.)
- The worker's slot end (1880-1923): _end_attempt(y, 'saved', reason) (1900); root_done absent (holder['root'] never set:
  1655-1656 need a done/reused root) -> 1917-1923: y.update(state='saved', reason, retained_booking=<booking>,
  retain_error=None, child=None); event 'slot_saved'; log "ROOT seq 2 20231018 (e2e-20231018-a2): saved: ... (attempt
  e2e-20231018-a2-20231018-a1, CPUs [0..31] retained)". No new attempt, no requeue, no teacher (the teacher is in
  _finish_day, reached only from a done/reused root, 1659).
- Worker end (2088-2100): `not running and stop and not after` -> ('saved', 5): worker_end event state saved, exit 5;
  the unit frankie-queue-root-1791413028 ends (exit 5). Resume: resume_owner (2240-2290) requires state in
  OWNER_STATES ('saved') -> back to queued with the SAME owner binding (attempt a1, CPUs 0-31, booking), the marker
  archived as .resumed-<ts>; the next admission books exactly the retained CPUs.
- Side effects of a kill vs a clean exit 75: claim_end is not called either way (child() raises first; the 20:05Z and
  22:40Z saves took the same path and resumed fine); the digest scratch .digest-bb89... (54 MB) and .projection-v2
  (~98 GB) stay on disk under work/derived; the disk-guard script (pid 32657) exits when ROOT is gone.
Conclusion: SIGKILL of the tree with the marker standing = saved, booking retained (CPUs 0-31), no teacher, no new
attempt; exactly the hold's outcome, minus the receipt.

### B. Kill ROOT's tree, command ab5649ac-f760-4804-a2aa-6393c5d4bd47, 02:08:14Z (state-changing; relayed for Greg)
`pkill -KILL -P 14860` (rc 0) ; sleep 1 ; `kill -KILL 14860` (rc 0). Before: marker standing yes; 14860 Sl 03:24:23, 31
children; worker 14824 Ssl. Verify at 02:08:50Z: 14860 GONE, 14858 gone; 29 orphan spawn_main helpers still alive (29
procs with files under R); worker 14824 alive Ssl; entry still 'running' (the worker's 60 s poll pending); booking file
rewritten 02:08 (3,325 B): retained {at 2026-10-08T02:08:16Z, attempt e2e-20231018-a2-20231018-a1, by_pid 14824, reason
'the day is saved on its owner; its CPUs stay its own until ACTION=resume'}, release None, cpu_list 0-31, no released
record; worker log: "day saved on its assigned lane; resume the retained attempt"; teacher 0; unit active (MainPID
14824, Memory 229.0G peak 244.7G, CPU 2d 49min); marker standing; ROOT log tail = resource_tracker KeyError
'/mp-itduzqby' traceback (the kill's cleanup); disk guard 0 running; df / avail 597,127,729,152; archive 1,725,022,760,960.
### Post-kill check, command 5333b0c3-87cd-423e-a40d-817068ba181f, 02:09:41Z (read-only)
- entry seq 2: state 'saved', reason 'saved on its day-bound marker /opt/frankie-box/work/frankie-queue/save/
  e2e-20231018-a2-20231018.save-request.json', finish None, retained_booking day-run-20231018-day_slot_root-1791402822-3111,
  retain_error None, child None; save_request True; last attempt {commit c9bf631, pid 14824, result saved, ended_utc
  2026-10-08T02:08:54Z}. Events: slot_saved (at 1791425334.05) + worker_end (02:08:54Z).
- worker 14824 ENDED; unit frankie-queue-root-1791413028 ActiveState inactive SubState dead MainPID 0; no frankie units.
- orphan helpers: NONE left; no process holds a file under R; teacher 0. load 13.94.
- KeepRunning tag: "false" (cleared by the worker's end) -> CreateTags true (02:10Z, below).

### KeepRunning, ec2 CreateTags 02:10Z (state-changing; relayed): KeepRunning=true (+ KeepRunningReason "relaunch role
2026-10-08 02:10Z: a2 day saved on its marker (ROOT tree killed at 02:08:14Z, booking retained); manual clean + resume
follow; the worker end had cleared the tag"); DescribeTags read back: KeepRunning=true.

### C. Step 0 rows-dir, command 13dec374-c449-45ac-bcbe-f37c1a2a3211, 02:10:11Z (state-changing; relayed): DONE rc 0
Before: symlink -> /opt/frankie-box/archive/work/experiment-teacher-rows.tar.zst; teacher procs 0. clean-a2.sh rows-dir:
"STEP 0 DONE: real directory now". Verify: test -d = IS A DIRECTORY, not a symlink; contents: ARCHIVED-OTHER-DAYS.README.txt
(1,490 B, names the tar.zst 24,863,644,343 B sha256 5d3dd82d8f3af932..., the listing and the restore line); the original
experiment-teacher-rows.ARCHIVED.README.txt (578 B, 00:55) kept beside it; the archive tar untouched (24,863,644,343 B).

### D. dry-run, command f2a9d527-4148-4431-bd42-1499f35cc21b, 02:10:46-51Z (read-only): STOPPED, 1 preflight FAIL
```
STEP 0: /opt/frankie-box/work/experiment-teacher-rows is already a real directory (1 entries); nothing to do
PREFLIGHT:
  PASS R is a directory and not a symlink
  FAIL R/calculations-receipt.json exists (ROOT completion published)
  PASS queue entry e2e-20231018-a2/20231018 state is 'saved' (read: saved)
  PASS no process holds a file or cwd under R open (open: 0)
  PASS no ROOT / teacher / batch / validate process running (found: 0)
  PASS archive volume mounted; PASS archive free 1725.02 GB >= planned 670.77 GB uncompressed + 15 GB; PASS root free 597.13 GB >= 15 GB
  PASS tools tar taskset flock sha256sum tee findmnt zstd; PASS python /opt/frankie-box/venv/bin/python
  PASS measured-idle sibling CPU pairs >= 3 (idle pairs: 15: 1,17 2,18 ... 15,31)
  PASS move pin found in legacy-stage.json and its bytes equal the file (pin: 472040420230 88b6a181e5698725ba2e4951d5542ce89499099dc9097debac6b482d76e57860)
  PASS plan is not empty
PLAN: MOVE 472040420230 B work/derived/legacy_book_imbalance.json -> archive (plain copy + symlink);
      ZIP 127622314364 B work/bedrock/recovery-6f84a8a86f454010b61346b401e3eb5f/ledgers/exact_member_rows.append.jsonl;
      ZIPDIR 68074692642 B work/bedrock/ledgers/; ZIP 3035329789 B .../exact_lifecycle_rows.append.jsonl; total 670772757025 B
STAY: attempt dir, receipts, work/derived/.rows/* (frames 496743568399 B), recovery-*/{receipt,result,ledgers/*_rows.jsonl},
      .projection-v2/ (97835917374 B), checkpoints, everything < 1 GiB. ESTIMATE 10-13 min, 20 pessimistic.
DRY-RUN: 1 preflight condition(s) FAIL; 'execute' would REFUSE. Nothing written.
```
Reported to main 02:11Z with options (a) E first then clean after a re-armed save / after the teacher; (b) relax preflight 2
to the legacy-stage.json pin; (c) leave the clean to the restaged boundary. HOLDING for the parent's E message.

### D decision (02:1xZ): option (b). Read-only checks at tip e0d7ae0 before the clean (repo, git show e0d7ae0:...)
1. Legacy-stage reuse: frankie_box_boss_session._derive 2548-2582: `stage = work/legacy-stage.json` (2548); identity
   compared (2551); for each artifact: spool with count -> `witness(path)` (2561, boss_session.witness 1725 =
   frankie_box_filehash-cached, `open(path,'rb')` fh 37, os.stat fh 22: symlink-transparent); .jsonl without count ->
   _witness_counting (2566); else `witness(path)` (2569) = the inline layer legacy_book_imbalance.json. THEN
   `load_retained_layers(self, receipt=..., spools=reopened)` (2579) = frankie_box_monday_calculations.load_retained_layers
   (line 26): the inline layer is parsed with `path.open(encoding='utf-8')` (line 83, symlink-transparent) BUT its entry
   is witnessed at line 106 `**witness(path)` with `witness` imported at line 20 FROM frankie_box_prepare_trading_day:
   `witness` -> `open_regular` -> `safe_path` ("symlink path refused" when any component is a symlink) + O_NOFOLLOW.
   => a symlink at work/derived/legacy_book_imbalance.json makes the resumed ROOT REFUSE. THE MOVE LEAVES THE PLAN.
   (experiment_root._pinned 97-105 (safe_path) pins only derive.json, the digest, the small JSONs and the three shared
   spools, 377-424; frankie_box_joined_teacher reads the layer with open(); those were never the problem.)
2. Completed-native reuse: _native_stage 3435-3465: `if recovery and native_stage.is_file()` -> identity check (3443),
   then per artifact of native-stage.json (recovery-6f84.../receipt.json, result.json, ledgers/exact_member_rows.jsonl,
   exact_lifecycle_rows.jsonl, legacy_observable_rows.jsonl: all STAY) `_claim_still_holds` (1390-1403: stat identity +
   last 64 KiB) else witness whole (3459). B.run (3467-3474, where frankie_box_bedrock 544-606 resume_checkpoint ->
   read_checkpoint/restore_driver -> native_checkpoint.restore_driver 328-342 -> copy_ledger_prefixes 134) is the ELSE
   branch, skipped. boss_session names no '.append.jsonl' and no work/bedrock/ledgers/ (the pre-save copy); the
   projection reuse _reusable_projection 190-232 reads .projection-v2/plan.json, result.json and the ledgers' pins by
   path (the *_rows.jsonl, STAY). => the three zips (127.62 GB + 3.04 GB append segments, 68.07 GB pre-save ledgers dir)
   are safe; their symlinks are siblings, never a component of a reused path.
Note for E: the reuse at line 106 reads the 472 GB layer whole again (prepare_trading_day.witness, uncached): ~7 min.

### clean-a2.sh v2 (local: scratchpad/relaunch/clean-a2.v2.sh, 29,009 B, sha256 735a24b74213ab6826742883e962c8320ff2e868dd170c2e6a9efbb509d7f416; bash -n ok; 31 diff lines)
- plan(): the MOVE branch commented out (with the reason); zips only.
- preflight 2: receipt present -> PASS as before; receipt ABSENT + queue entry saved + work/legacy-stage.json a regular
  file -> PASS "work/legacy-stage.json pin accepted in its place (sha256 ...)", RECEIPT_BASIS set; else FAIL as before.
- CLEAN_RECEIPT: + receipt_basis (the basis text with legacy-stage.json bytes + sha256), + plan_note (the MOVE left out).
- Preflight 11 (move pin) is skipped by the script's own `if plan has move` guard: 18 conditions remain.

### FINDINGS FOR THE ROOT ROLE (the parent forwards them; from the e0d7ae0 source, 02:15Z)
1. frankie_box_monday_calculations.load_retained_layers (e0d7ae0 line 26; called by boss_session._derive 2579 on the
   legacy-stage reuse route) witnesses the INLINE layer (work/derived/legacy_book_imbalance.json, 472,040,420,230 B) at
   line 106 with `witness` imported at line 20 from frankie_box_prepare_trading_day: open_regular -> safe_path (any
   symlink component -> ValueError 'symlink path refused') + O_NOFOLLOW, hashlib.file_digest over the whole file,
   UNCACHED (not frankie_box_filehash): every resume re-reads the 472 GB whole (~7 min at 1.1 GB/s) after
   boss_session 2569 already witnessed the same file through the cache, and a moved layer behind a symlink refuses the
   resume. (The spool-reference branch, line 81, has the same witness; line 83 `path.open()` is symlink-transparent.)
2. The reuse path should take the layer's claim from legacy-stage.json instead (bytes + sha256 + stat identity + the
   last line / last 64 KiB, the FRANKIE_FILE_CLAIM_V1 rule the native reuse already applies via _claim_still_holds,
   boss_session 1390-1403), falling back to the whole read only when the claim no longer holds; and open the layer
   through a reader that accepts the clean's symlink (a resolved regular file), so the workflow's own clean can move
   the inline layer from day 2 without refusing the next resume.
Greg's call (parent, 02:18Z): the 472 GB layer STAYS for a2; it moves with the workflow's clean from day 2, after a
receipt exists. The manual clean = the 198.73 GB of zips only.

### D. v2 installed + dry-run, command 0f5c2e6a-d519-4b96-84f6-513cf4610257, 02:18:07-12Z
- /opt/frankie-box/archive/.logs/clean-a2.sh = v2 (29,009 B, sha256 735a24b74213ab6826742883e962c8320ff2e868dd170c2e6a9efbb509d7f416,
  mode 700); v1 kept as clean-a2.v1.sh (sha256 2831bf345d35d4e6...).
- dry-run: 18 PASS / 0 FAIL. Preflight 2: "PASS R/calculations-receipt.json ABSENT and entry saved: work/legacy-stage.json
  pin accepted in its place (sha256 a973d226bde070118948150c3480a19f20636050f2b15dce77dcf5a7a814b862)". archive free
  1725.02 GB >= 198.73 + 15; root free 595.10 GB; idle pairs 15; plan not empty. (Preflight 11 skipped: no move planned.)
- PLAN: ZIP 127,622,314,364 B recovery-6f84a8a8.../ledgers/exact_member_rows.append.jsonl; ZIPDIR 68,074,692,642 B
  work/bedrock/ledgers/; ZIP 3,035,329,789 B .../exact_lifecycle_rows.append.jsonl; total 198,732,336,795 B.
  "DRY-RUN: every preflight condition holds; 'execute' would run the plan above. Nothing written."
- e0d7ae0 checkout: /opt/frankie-box/code/e0d7ae00500bdc3d341af3abe170687ce5ab80ec-37716712485-1/markets (02:14:24Z),
  HEAD e0d7ae00500bdc3d341af3abe170687ce5ab80ec, stage_handoff.py present. Entry saved, retained; teacher 0; units 0.

### D. EXECUTE, command 3185fad2-c0c9-481c-b144-dc33bfe9d01e, 02:18:41Z (state-changing; Greg's go via the parent 02:18Z)
`systemd-run --unit=frankie-clean-a2 --collect -p KillMode=mixed bash /opt/frankie-box/archive/.logs/clean-a2.sh execute`
-> "Running as unit: frankie-clean-a2.service; invocation ID 0029d834edc74892b5b4f7e08d2b3446", rc 0; MainPID 81437,
active/running since 02:18:41Z. df before: root avail 595,100,282,880; archive avail 1,725,022,728,192.
Log: 02:18:49Z EXECUTE start jobs=3 pairs/job=5 plan_bytes=198,732,336,795 root_free=595,100,258,304 archive_free=
1,725,022,720,000; CPU sets 1,17,4,20,7,23,10,26,13,29 / 2,18,5,21,8,24,11,27,14,30 / 3,19,6,22,9,25,12,28,15,31;
02:18:49Z START x3; 02:18:55Z ZIPPED+REMOVED exact_lifecycle_rows.append.jsonl (6 s) pipestatus 0 0 0 0 entries w1/src1
files w1/src1 bytes w3035329789... -> exact_lifecycle_rows.append.jsonl.tar.zst 102,627,436 B (+ .listing.txt 83 B,
.pipestatus, .sha256). At 02:19:0xZ: exact_member_rows.append.jsonl.tar.zst.part 531,906,560 B; ledgers.tar.zst.part
432,787,456 B; two zstd -T0 -3 processes; df root avail 598,135,586,816, archive 1,723,955,216,384; load 0.87.

### E (prepared; runs after the CLEAN_RECEIPT): checkout e0d7ae0 (HEAD verified 02:18Z)
CODE_ROOT=/opt/frankie-box/code/e0d7ae00500bdc3d341af3abe170687ce5ab80ec-37716712485-1/markets
MARKETS_SHA=e0d7ae00500bdc3d341af3abe170687ce5ab80ec
1. `CODE_ROOT=$CODE_ROOT MARKETS_SHA=$MARKETS_SHA ACTION=resume RUN=e2e-20231018-a2 DAY=20231018 bash $CODE_ROOT/deploy/aws/box/frankie_box_frankie_queue.sh`
   (no REBOOK: the booking is retained; refused -> STOP and report)
2. `FRANKIE_ROOT_DIGEST=off FRANKIE_CLEAN_ON_SAVE=off CODE_ROOT=$CODE_ROOT MARKETS_SHA=$MARKETS_SHA ACTION=kick LINE=root SCOPE=e2e-20231018-a2:20231018 bash $CODE_ROOT/deploy/aws/box/frankie_box_frankie_queue.sh`
   Where the settings go (e0d7ae0): frankie_box_frankie_queue.sh exports every FRANKIE_* shell variable (FA-6 block);
   kick() (frankie_box_frankie_queue.py 363-437) passes them as `systemd-run -E NAME=VALUE` (409) and prints
   run_settings on the kick receipt (422-437); Run.child hands the worker's environment to the ROOT child;
   Run.root_digest_setting (frankie_box_experiment.py 1368-1386) reads FRANKIE_ROOT_DIGEST on|off and the root step
   passes DIGEST=<value> (1748-1753), recorded as digest_setting on the root record; frankie_box_stage_handoff.on()
   reads FRANKIE_CLEAN_ON_SAVE (off = validate -> successor directly, no save, no clean).

### Clean watch 1, command de34ea8d-7098-4b0b-9a75-f750a7f607cd, 02:21:36Z: ALL THREE JOBS DONE
- 02:18:55Z ZIPPED+REMOVED exact_lifecycle_rows.append.jsonl (6 s) pipestatus 0 0 0 0, bytes w3035329789/src3035329789 -> 102,627,436 B.
- 02:20:49Z ZIPPED+REMOVED work/bedrock/ledgers (120 s) pipestatus 0 0 0 0, entries w4/src4 files w3/src3, bytes
  w68074692642/src68074692642 -> ledgers.tar.zst 3,260,199,720 B, sha df0ec0f427fcb584fb150bd30ee8bf061bd0813f12c8efbd3184e1830a239ad.
- 02:21:35Z ZIPPED+REMOVED exact_member_rows.append.jsonl (166 s) pipestatus 0 0 0 0, bytes w127622314364/src127622314364
  -> exact_member_rows.append.jsonl.tar.zst 6,693,014,456 B.
- guard lines 02:19:47Z / 02:20:47Z paused=0. df at 02:21:36Z: root avail 793,832,644,608 (+198.7 GB), archive 1,714,966,786,048. load 3.53.
### CLASSROOM-ARM CHECK (same command): day 20231018 IS a classroom-arm day
- /opt/frankie-box/work/experiment/e2e-20231018-a2/plan.json: plan['classroom_arm'] = ['20231018']; days entry
  {"classroom_arm": true, "cls": "midweek", "day": "20231018", "manifest": "research/kalshi/frankie_boss/blocks/
  BLOCK_20231018_SOURCE_MANIFEST.json", "manifest_gap": null, "opens_after": "20231017", "role": "discovery"}.
- queue root.json entry: classroom_arm = None (no role-like keys); no class.json exists yet (the class line file is
  absent: FileNotFoundError), i.e. no class entry.
- Consequence (e0d7ae0 frankie_box_experiment.py 1368-1386 + 2331): with FRANKIE_ROOT_DIGEST=off given, the ROOT runs
  DIGEST=off (the setting wins); the classroom step later refuses "the ROOT ran without the digest; a classroom-arm day
  needs DIGEST=on" until a digest route renders it (the parent: being built). Proceed with E as briefed (digest off).

### CLEAN_RECEIPT, command cb010f05-f59c-432a-ada6-2acc8f5ef153, 02:22:09Z (read-only)
CLEAN_RECEIPT {"status": "done", "jobs_done": 3, "jobs_failed": 0, "started_utc": "2026-10-08T02:18:49Z", "ended_utc":
"2026-10-08T02:21:37Z", "seconds": 168, "root_free_before": 595100258304, "root_free_after": 793832632320, "root_freed":
198732374016, "archive_free_before": 1725022720000, "archive_free_after": 1714966786048, "archive_written": 10055933952,
"manifest": ".../e2e-20231018-a2-20231018-a1.moved-manifest.json", "receipt_basis": "calculations-receipt.json ABSENT (ROOT
killed before its receipt); entry saved; the legacy-stage.json pin accepted in its place (work/legacy-stage.json 59810 B
sha256 a973d226...)", "plan_note": "v2: the MOVE of work/derived/legacy_book_imbalance.json left out ...", "script_sha256":
"735a24b7...", "cpu_sets": "1,17,4,20,7,23,10,26,13,29 2,18,5,21,8,24,11,27,14,30 3,19,6,22,9,25,12,28,15,31"}
Manifest (3,007 B): FRANKIE_ROOT_MOVE_MANIFEST_V1, 3 moves (kind archive, op zip, status done), 0 not_moved:
  exact_lifecycle_rows.append.jsonl 3,035,329,789 -> 102,627,436 sha f0c9fb580ce6207b...;
  work/bedrock/ledgers 68,074,692,642 -> 3,260,199,720 sha df0ec0f427fcb584...;
  exact_member_rows.append.jsonl 127,622,314,364 -> 6,693,014,456 sha 83c5c37cc016bac1....
Old paths: symlink -> tar.zst + <name>.ARCHIVED.README.txt at each; recovery ledgers untouched: exact_member_rows.jsonl
193,743,650,444, exact_lifecycle_rows.jsonl 7,560,352,552, legacy_observable_rows.jsonl 742,788,266,
legacy_observable_rows.append.jsonl 478,939,352 (under the floor). Unit frankie-clean-a2 inactive/dead ExecMainStatus 0;
procs under R 0; no frankie units; df root avail 793,832,558,592, archive 1,714,966,781,952; entry saved, retained.

### E. RESUME, command d1c39270-278c-4b94-b0da-f3cad9f331a2, 02:23:29Z (state-changing; Greg's go via the parent)
(First attempt was rejected by SSM validation: Comment > 100 chars; nothing ran.) HEAD e0d7ae0... verified; pre: 0
procs under R, 0 units, 0 teacher. `ACTION=resume RUN=e2e-20231018-a2 DAY=20231018` (CODE_ROOT/MARKETS_SHA e0d7ae0)
-> rc 0: {"resumed": {"phase": "root", "archived": [".../save/e2e-20231018-a2-20231018.save-request.json.resumed-1791426209"],
"owner": {attempt e2e-20231018-a2-20231018-a1, booking day-run-20231018-day_slot_root-1791402822-3111, cpus 0-31, commit
c9bf631 (the owner's last source; the next admission rebinds to the worker's source), held_bookings x3, marker ...}},
"note": "the next ROOT-line admission books exactly the retained CPUs and resumes attempt ...; kick the root worker"}.
THEN my command script died at its line 11 ("Bad substitution": SSM runs AWS-RunShellScript under sh/dash;
`${PIPESTATUS[0]}` is bash-only), so the KICK did not run in that command. State after: entry queued (resumed), no worker.
### E. KICK, separate command (sh-safe), 02:24Z: see below.
Command a19113dd-cec7-4e24-8e8e-b1fb0510f44f, 02:24:05Z: pre entry queued, 0 units, 0 ROOT procs.
`FRANKIE_ROOT_DIGEST=off FRANKIE_CLEAN_ON_SAVE=off ACTION=kick LINE=root SCOPE=e2e-20231018-a2:20231018` (e0d7ae0) ->
rc 0: "root worker started for e2e-20231018-a2:20231018 ({'method': 'systemd-run', 'unit': 'frankie-queue-root-1791426245',
'exit_code': 0}) ... worker lock held"; receipt run_settings {"FRANKIE_CLEAN_ON_SAVE": "off", "FRANKIE_ROOT_DIGEST": "off"}.
Unit Environment: CODE_ROOT=.../e0d7ae0...-37716712485-1/markets, FRANKIE_CLEAN_ON_SAVE=off, FRANKIE_ROOT_DIGEST=off,
MARKETS_SHA=e0d7ae00500bdc3d341af3abe170687ce5ab80ec. After 20 s (02:24:26Z): entry seq 2 state running, where
box-slot, retained_booking day-run-...-3111, save_request None; owner {attempt a1, booking ...-3111, cpus 0-31, commit
e0d7ae0, code_root e0d7ae0 checkout}; last attempt {pid 87218, started 02:24:06Z}; events: resume (02:23:29Z), take
(pid 87218, 02:24:06Z), kick. ROOT procs: 87254 frankie_box_cores.py run --kind day-run ... ; 87256
frankie_box_experiment_root.py --commit e0d7ae0.... Day log 20231018-root.log: "### root 20231018 ... at 02:24:09Z",
CPU_BOOKING inside the held slot CPUs 0-31, "02:24:23Z experiment ROOT: sealed day, legacy and native calculations; no
giant bedrock digest".

### E watch 1, command 59bffcec-3836-41ab-acd0-9329b908f675, 02:27:23Z
- ROOT log since 02:24:09Z: only "02:24:23Z experiment ROOT: sealed day, legacy and native calculations; no giant bedrock
  digest" (no reuse line yet). progress.json: deriving running, age 180 s. 87256 Rl 03:14 99.0% CPU, 0 children;
  io read_bytes 235,226,914,816 (~1.3 GB/s: the legacy-stage reuse witnessing the spools/layer whole), write 16,384;
  fds: .projection-v2/published-238b8654.../full_bid_ask_depth.json.gz + root.log. receipt absent; derive.json still
  the 01:33 one (80,813 B). days/20231018/root.json = the enqueue record (status queued). handoff/ absent. Stage
  heartbeat days/20231018/progress/root.jsonl: cpus_busy 0.97, cpu_seconds 178.6, elapsed 180.1, processes 2.
  teacher 0; unit frankie-queue-root-1791426245 active; entry running box-slot; df root 793.8 GB; load 0.98.

### E status (parent request), command d9e4715b-3153-42c2-93ad-167547f57220, 02:29:24Z
87256 Rl 05:14 98.4% RSS 411,772 KB, 0 children; read_bytes 385,570,160,640 (1.25 GB/s since 02:27:23Z), write 16,384;
fd on work/derived/legacy_book_imbalance.json. Log since 02:24:09Z: 3 lines, last 02:24:23Z (no reuse line yet).
progress.json deriving/running at 02:24:23Z. New under R: checkout-rebinds/1791426263613438265-e1953057.json 2,442 B,
progress.json, phase, note (02:24:23Z). derive.json 01:33:06Z; receipt absent; file-claims.jsonl absent. Root record
queued/None. handoff 0. Entry running box-slot. teacher 0. df / 793,832,275,968. load 1.01. Reported to main.
### E watch 2, command 8b339c7d-1db5-48e7-bc9e-a2172f25ec62, 02:31:40Z: 87256 Rl 07:31 98.0%, 0 children, read_bytes
556,471,271,424 (1.26 GB/s), fd legacy_book_imbalance.json; no new log line; progress deriving age 437 s; receipt absent;
heartbeat cpu_seconds 441.2 elapsed 450.1 cpus_busy 0.98; entry running; teacher 0; df root 793.8 GB; load 1.04.
### E watch 3, command 02421419-7e67-486d-adc9-5ef5cf3280ef, 02:33:55Z: 87256 Rl 09:46 97.9%, read_bytes 724,889,354,240
(1.25 GB/s), fd legacy_book_imbalance.json; no new log line; progress age 571 s; receipt absent; entry running; teacher 0.
Note: after the witness pass, load_retained_layers parses the 472 GB inline layer with the Python _JSON streaming
parser (monday_calculations 83-95: counts the 'frames' array) whose rate is unmeasured here; it may be the long step.
### E status 2 (parent request), command 2f015f88-23a4-4bdc-9a70-05d634dc9ffa, 02:36:09Z: 87256 Rl 11:59 96.3% RSS
412,216 KB, 0 children; read_bytes 891,921,817,600 (1.25 GB/s); fd .rows/frames.jsonl (the layer pass ended ~02:35Z);
log unchanged (3 lines since the header); receipt absent; file-claims.jsonl absent; root record queued/None; handoff
none; entry running box-slot; teacher none; unit active; df / 793,832,083,456; load 1.00. Reported to main.
### E watch 4, command ebf1ee81-dca3-4742-8739-b62b828ebfdc, 02:38:59Z: 87256 Rl 14:50 95.2%, read_bytes 1,105,311,227,904;
fd 3 frames.jsonl pos 371,902,234,624 of 496,743,568,399 (75%, ends ~02:40:40Z); no new log line; receipt absent;
entry running; teacher 0; load 1.01. (Parent rule: if the receipt projects past 03:15Z, a kill + restage + resume on
the claims code; measure only.)

## Second resume (relaunch-2 role, 02:56Z onward): kill the e0d7ae0 ROOT child mid-parse, resume ONCE MORE on tip 6076950

Greg: "Do it". Box i-035994afa8bdf66a5, SSM via the Aws connector (SendCommand + GetCommandInvocation; scripts sent as
`bash -s <<'EOF'` so no sh/dash bash-ism trap). R, Q as above. New checkout: CODE_ROOT=/opt/frankie-box/code/
607695094bd33c175bd6822bb53d4616a9b98a9c-37720265393-1/markets, MARKETS_SHA=607695094bd33c175bd6822bb53d4616a9b98a9c
(stage run 843 started 02:55:47Z; dir landed 02:58:20Z; `git rev-parse HEAD` verified 02:59:15Z and 03:01:10Z).

### A. Probe, command d7d934de-baf1-4d54-9cc8-8d7f6055b689, 02:57:55Z (read-only)
- 87256 Rl elapsed 33:46 97.3% CPU RSS 452,908 KB, 0 children; fd 3 = work/derived/legacy_book_imbalance.json pos
  27,866,693,632 of 472,040,420,230 (5.9%): the Python streaming parse of the inline layer (monday_calculations
  load_retained_layers, e0d7ae0); fds 1,2 = root.log. io read_bytes 1,259,105,243,136, write 32,768.
- ROOT log since the 02:24:09Z header: 02:24:23Z "sealed day ..."; 02:40:40Z reusing retained legacy layer legacy_price;
  02:40:43Z legacy_native_signed_flow; 02:40:43Z legacy_per_second_roll20; nothing after.
- Rate: ~27.9 GB in ~17 min since 02:40:43Z = ~27 MB/s -> ~4.5 h for the 472 GB: far past the 03:15Z rule.
- progress.json deriving/running (02:24:23Z). receipt absent; derive.json 01:33:06Z (80,813 B); file-claims absent;
  handoff/ absent. root.json seq 2: running, box-slot, save_request null, retained_booking ...-3111, owner commit
  e0d7ae0, last attempt pid 87218 started 02:24:06Z. save/: NO marker (4 .resumed-* archives: 1791400389, 1791409621,
  1791413028, 1791426209). Worker 87218 Ssl; unit frankie-queue-root-1791426245 active running; teacher 0; ROOT procs
  87254 (cores) + 87256. 6076950 checkout NOT present yet. df / 793,831,948,288; archive 1,714,966,781,952. load 1.00.
- KeepRunning (DescribeTags 02:58Z): true (session5b hold agent's reason).
- e0d7ae0 trace (git show e0d7ae0:deploy/aws/box/frankie_box_experiment.py, local): child() 1430: check_save() at 1435
  before Popen; `code = proc.wait()` 1494; `self.check_save()` 1503 unconditionally after; check_save 1215-1218 raises
  SystemExit(75) when save_requested() (1198-1200: the owner marker is_file). root() 1651: child_saved 1765 (a 75
  WITHOUT a marker = the child's own save route) else 1771-1778 'failed' record + claim_end only when child() returns.
  frankie_box_frankie_queue.py e0d7ae0: OWNER_STATES 107 ('saved','unknown'); _thread_end 1618-1621 (SystemExit 75 and
  run_obj.save_requested() -> _save_result 1627); _end_slot 1676-1683 C.retain; _root_job 1695 except (Exception,
  SystemExit) 1718; resume_owner 2286. Same path as the proven 02:08Z kill.
- 6076950 (git log e0d7ae0..6076950, 18 commits; deploy/aws/box diff: monday_calculations +165, stage_handoff +116,
  experiment_root +95, classroom_v2 +195, teacher +124, render_digest, root_move, frankie_queue +11):
  load_retained_layers(session, ..., layer_witnesses=) takes the caller's verified claims; an inline layer whose claim
  holds takes the SEALED RECORD route (head keys + count from the file head, the keys after the array from the last 64
  KiB = INLINE_TAIL_BYTES; the array not parsed; count checked against the spool) and logs
  "reusing retained legacy layer <name> (sealed record)"; otherwise parse_inline_layer_counting (one hashing pass) logs
  "(parsed". count_basis is written on the entry.

### B1. Marker, command b162b898-44ed-412f-8a89-40879ce2b47b, 02:59:15Z (state-changing)
`CODE_ROOT=<e0d7ae0> MARKETS_SHA=e0d7ae0... ACTION=save RUN=e2e-20231018-a2 DAY=20231018` -> rc 0, entry_state running,
marker Q/save/e2e-20231018-a2-20231018.save-request.json written 02:59:15Z, 498 B, sha256
d3b9bff9fc8acda006d8468b6f7e774c5c4ae7dccd899481900576d4869f1e1f, FRANKIE_QUEUE_SAVE_REQUEST_V1, attempt a1, booking
...-3111, cpus 0-31, requested_at 1791428355.2277634, by "dispatch save". Pre: no marker, 87256 Rl 35:05 pos
29,916,332,032. Post: 87256 Rl, worker 87218 Ssl. 6076950 checkout present (02:58:20Z), HEAD verified.

### B2. Kill, command d3970430-4730-49d4-92b7-9fa60503ca03, 02:59:53Z (state-changing)
Pre: marker STANDING, 87256 Rl 35:43, 0 children, worker Ssl. `pkill -KILL -P 87256` rc 1 (no children); `kill -KILL
87256` rc 0 at 02:59:54Z. Verify 03:00:24Z: 87256 GONE, 87254 GONE, 0 procs with files under R, worker 87218 GONE,
unit frankie-queue-root-1791426245 inactive/dead MainPID 0 ExecMainStatus 0, marker STANDING, root.json seq 2 state
'saved' reason "saved on its day-bound marker ...", finish null, save_request = marker identity (sha256 d3b9bff9...),
retained_booking ...-3111, retain_error null, child null; last attempt pid 87218 result saved ended_utc 03:00:06Z;
root-worker.log state waiting_owner 03:00:06Z, worker_lock_held false. ROOT log: no traceback (ends at the 02:40:43Z
line). teacher 0; no frankie units; load 0.73. KeepRunning (DescribeTags 03:01Z): FALSE ("frankie_box_frankie_queue.py
worker: root line worker ended (scope e2e-20231018-a2:20231018)") -> re-set below.

### C1. Resume, command 0eb839ff-717b-453e-a15e-c8523be03a22, 03:01:10Z (state-changing; 6076950 checkout, HEAD verified)
Pre: entry saved, retained_booking ...-3111, retain_error null; 0 procs under R, 0 ROOT/worker procs, 0 units, 0
teacher; marker standing. `ACTION=resume RUN=e2e-20231018-a2 DAY=20231018` -> rc 0: resumed phase root, archived
save/...save-request.json.resumed-1791428470; owner attempt a1, booking ...-3111, bound 2026-10-07T19:53:42Z by pid
3111, cpus 0-31, held_bookings x4 (19:53:42, 21:47:27, 22:43:49, 02:24:06), holder_pid 87218, source_history
98579cea (until 21:47:26Z) -> 275367fe (until 22:43:48Z) -> c9bf631 (until 02:24:05Z); commit e0d7ae0 until the next
admission. After: entry seq 2 'queued' ("resumed by dispatch resume: back in line at its own place with its owner
binding"), save_request null, retained_booking ...-3111. save/: 5 .resumed-* archives, no marker.
### KeepRunning, CreateTags 03:01:5xZ: KeepRunning=true (+ reason "relaunch-2 role ... a2 day 20231018 saved on its
marker (ROOT child 87256 killed 02:59:54Z, booking retained), resumed on 6076950 ..."); read back true.

### C2. Kick, command e8cfeef3-a757-4a1f-b805-585d052d9088, 03:01:54Z (state-changing)
Pre: HEAD 6076950, 0 units, 0 ROOT/worker procs, entry queued. `FRANKIE_ROOT_DIGEST=off FRANKIE_CLEAN_ON_SAVE=off
ACTION=kick LINE=root SCOPE=e2e-20231018-a2:20231018` -> rc 0 at 03:01:56Z: "root worker started ... unit
frankie-queue-root-1791428515 exit_code 0 ... worker lock held"; receipt run_settings {"FRANKIE_CLEAN_ON_SAVE": "off",
"FRANKIE_ROOT_DIGEST": "off"}, started true. At 03:02:21Z: unit active/running MainPID 88228, Environment CODE_ROOT=
<6076950 checkout>, FRANKIE_CLEAN_ON_SAVE=off, FRANKIE_ROOT_DIGEST=off, MARKETS_SHA=607695094bd33c175bd6822bb53d4616a9b98a9c.
Entry seq 2 running box-slot, retained_booking ...-3111, save_request null; owner commit 6076950, code_root the 6076950
checkout; last attempt pid 88228 commit 6076950 started 03:01:56Z. ROOT procs 88263 (cores run --kind day-run --day
20231018 --run e2e-20231018-a2 --stage root) + 88265 (experiment_root --commit 6076950 ... --digest off --resume).
ROOT log: "### root 20231018 ... at 03:01:59Z", CPU_BOOKING inside the held slot CPUs 0-31, "03:02:13Z experiment ROOT:
sealed day, legacy and native calculations; no giant bedrock digest". progress.json deriving/running pid 88265
(03:02:13Z). teacher 0; load 0.45.

### D. Watch (read-only, ~2 min)
- Watch 1, command 074dc385-4c3e-41dd-815c-0454400dafd8, 03:04:02Z: 88265 Rl 02:02 91.9% RSS 408,156 KB, 0 children;
  fd 3 = work/derived/.rows/frames.jsonl pos 135,857,790,976 of 496,743,568,399 (a WHOLE READ of the frames spool,
  ~1.2 GB/s; read_bytes 145,330,122,752, write 61,440). work/file-claims.jsonl WRITTEN 03:02:14Z (41,542 B, 57 rows).
  Log since the header: only the 03:02:13Z "sealed day" line. derive.json 01:33:06Z; receipt absent; handoff absent;
  entry running box-slot; teacher 0; unit active; load 0.95. REPORTED to main at once (fd + log).
- Claims read, command c7daaeda-83c9-48da-800c-559260087d0a, 03:04:50Z: fd 3 pos 196,670,181,376; read_bytes
  206,076,227,584. file-claims.jsonl: 57 rows, keys at/bytes/claimed_by/path/rule/schema/sha256/stat/tail_bytes/
  tail_sha256; claimed_by "root reuse: receipt/derive.json sha256 (sealed on an earlier checkout) + stat + tail at
  2026-10-08T03:02:14Z"; rule "taken by a later stage only when stat and the last 64 KiB match; else that stage hashes
  in full". The 472 GB layer HAS a row (bytes 472,040,420,230, sha256 88b6a181e5698725ba2e4951d5542ce89499099dc9097deb
  ac6b482d76e57860, stat [66305, 8691433, 472040420230, 1791420307893228716], tail 65,536 B sha256 0ba9f92b8d22ff5fe3
  4137e6782bf1f0f49a6ebea0efb13f19c17a4b26cd5639). frames.jsonl has NO row. legacy-stage.json (59,810 B, 01:17:50Z,
  keys artifacts/identity/receipt/schema): frames entry {bytes 496743568399, sha256 be7655b2663841df1b3662a057f86122
  750364b1b0678fcfd46c92798b0c1495} with no count; the layer entry {bytes 472040420230, sha256 88b6a181...}.
- Watch 2, command 863cd4d7-5703-48ed-81c2-b2284060e4c7, 03:05:37Z: fd 3 pos 255,275,139,072; read_bytes
  264,683,237,376; log unchanged; claims basenames = the 44 .projection-v2 published *.json.gz + 5 legacy_*.json layers
  + .rows/input-34b2233453834fa090fe5b4c1848d4b6.jsonl + recovery-6f84.../{receipt.json, result.json, ledgers/
  exact_lifecycle_rows.jsonl, exact_member_rows.jsonl, legacy_observable_rows.jsonl}; derive.json mentions
  frames.jsonl 0 times (its only .rows path is the input spool). teacher 0; load 0.99.
- Watch 3, command 5d4f07ff-43f2-4334-938d-227d5cca9c75, 03:06:38Z: 88265 Rl 04:38 90.3%; fd 3 pos 331,069,763,584
  (1.24 GB/s over 61 s; ends ~03:08:50Z); read_bytes 340,478,504,960; log unchanged; derive.json 01:33:06Z; receipt
  absent; new under R: note, phase, checkout-rebinds/1791428533903405857-89ae808e.json, progress.json,
  work/file-claims.jsonl; teacher 0; unit running; load 1.00.
- CAUSE (6076950 source, local git show): the ROOT runs experiment_root.py's resume route (385-436: `resume and
  work/derive.json is_file`): write_claims_from_derivation (116-171: one FRANKIE_FILE_CLAIM_V1 row per derive.json
  layer / native ledger / result / receipt from the sealed sha256+bytes, a fresh stat and one 64 KiB tail; never a full
  read) -> evidence() for the native receipt/result/ledgers and every layer via boss_session._artifact_check (claim
  holds -> no read; else read whole) -> load_retained_layers(session, allow_failures=True, layer_witnesses=witnessed)
  with NO spools= (the spools are reopened inside it: the frames spool pass) -> session.note('retained evidence: %d
  artifacts, %d by their claim, %d read whole') -> (digest off: no write_retained_digest) -> receipt. derive.json never
  lists frames.jsonl and the c9bf631 seal recorded no count for it, so no claim exists for the spool: exactly one
  496.7 GB pass on this seal; the 472 GB layer is taken by its claim (sealed-record route in load_retained_layers,
  log "(sealed record)"). boss_session._derive's own legacy-stage route (2592-2640) has the same shape for a .jsonl
  artifact without a sealed count (2618-2621 _witness_counting, one hashing+counting pass, no claim lookup).
  Reported to main 03:05Z and 03:07Z with the finding for the ROOT role (the spool count is in the sealed layer head).
  Route confirmed (frankie_box_monday_calculations.py 6076950, 164-178): load_retained_layers' reopen(path) returns the
  caller's spool when given, else B.RowSpool.reopen(path) for the input, prices, frames, structures and failures spools:
  the frames pass is RowSpool.reopen counting the 496.7 GB spool's lines (the experiment_root resume route passes no
  spools=). The sealed inline layer head's `count` (trusted by the sealed-record route as len(spool)) could seed it.

## Shutdown for the night (Greg via the parent, ~03:08Z): marker now, let the receipt land (bound 03:30Z), then stop the box

### (1) Marker, command 49741c01-b407-4a92-b771-208966664110, 03:09:51Z (state-changing)
Pre: no marker; 88265 Rl 07:51; fd 3 pos 1,528,627,200 on work/derived/legacy_book_imbalance.json (the frames pass had
ended 03:08:51Z). `CODE_ROOT=<6076950> MARKETS_SHA=6076950... ACTION=save RUN=e2e-20231018-a2 DAY=20231018` -> rc 0,
entry_state running; marker Q/save/e2e-20231018-a2-20231018.save-request.json 497 B 03:09:51Z sha256
5738b2458a0978ec94f4f5227333268800700641996dee8fd858d61ad94b39f0. Post: 88265 Rl, worker 88228 alive.
ROOT log since the header: 03:02:13Z sealed day; 03:08:51Z reusing retained legacy layer legacy_price (parsed);
03:08:56Z legacy_native_signed_flow (parsed); 03:08:56Z legacy_per_second_roll20 (parsed). The 472 GB inline layer is
being PARSED WHOLE (parse_inline_layer_counting; count_basis 'parsed'), not taken by its claim: the sealed-record basis
fired for no layer. Expected end ~03:16:30Z at ~1.2 GB/s, then derive.json + receipt (digest off). Reported to main
03:10Z; per step (2) the child is left to finish.
(Watch-4 deferred probe: its CommandId was lost to a formatting error in my result line; superseded by this command.)
### (2) Poll A, command 21742a2b-95a3-415c-ae38-aefe4adf8cc2, 03:12:31Z (read-only): the parse is SLOW
88265 Rl 10:31 93.4% RSS 453,360 KB; fd 3 pos 5,834,342,400 on the 472 GB layer (from 1,528,627,200 at 03:09:51Z:
~27 MB/s = the Python _JSON streaming parse, not the 1.2 GB/s hash pass); read_bytes 513,046,228,992; write 77,824.
Projection ~4.8 h: the receipt cannot land by 03:30Z. Marker STANDING; entry running box-slot save_request true;
receipt absent; derive.json 01:33:06Z; worker 88228; unit running; teacher 0; load 1.00.
### Cause of the whole parse (read-only tail/head reads, commands 6eb57d69-0f62-424a-af43-3b0846f03fd7 03:12:22Z and
3cfcd46c-9e3f-4494-b779-889ae1f21995): the layer head is the sealed layout: {"count": 583688, "fields": [...8...],
"frame_sections": [...7...], "frame_sections_schema": "FRANKIE_ROOT_FULL_DEPTH_GROUPS_V2", "frames": [ (offset 437).
The tail (last 64 KiB; size 472,040,420,230): `],\n "producer": "V4MboAdapter F_LAST book snapshot +
a_memory_member_first_recalculation_20260828.book_values/book_transition",\n "reason": null,\n "status": "derived"\n}`.
frankie_box_monday_calculations.inline_layer_without_array (6076950): `at = tail.rfind(b'"reason"')`, then requires
`before = tail[:at].rstrip()` to end with b',' AND before[:-1].rstrip() to end with b']' -> False here (the "producer"
key sits between the array and "reason") -> returns None -> load_retained_layers 213-217 parse_inline_layer_counting
(count_basis 'parsed'). The three small layers' "(parsed)" is expected (no inline array; cheap). FINDING for the ROOT
role: anchor on the first top-level key after `],` in the tail (producer / reason / status here), not on "reason".
Reported to main 03:13Z with the recommendation to kill with the marker standing (the proven saved path); WAITING for
the parent's go; read-only polls every 2 min meanwhile.
### Kill (parent's go, Greg: shut down for tonight), command 5d109b8d-72c2-448c-8540-b4f5085c90a3, 03:14:10Z
Pre: marker STANDING; 88265 Rl 12:10, 0 children, fd 3 pos 8,464,957,440 (1.8% of the layer); worker 88228 Ssl.
`pkill -KILL -P 88265` rc 1 (no children); `kill -KILL 88265` rc 0 at 03:14:11Z. Verify 03:14:43Z: 88265 GONE, 88263
GONE, 0 open files under R, unit still active (worker's 60 s poll pending), marker STANDING, entry still 'running',
receipt absent, ROOT log ends at the 03:08:56Z "(parsed)" line (no traceback), teacher 0. df before the stop:
/ size 2,129,040,207,872 avail 791,803,990,016; /opt/frankie-box/archive size 2,163,350,618,112 avail 1,714,966,781,952.
### Verify saved, command f5284128-bc4a-4720-ae0d-bc23b4ca5024, 03:15:51Z (read-only)
worker 88228 GONE; frankie procs 0; open files under R 0; unit frankie-queue-root-1791428515 inactive/dead MainPID 0
ExecMainStatus 0; NO frankie-* unit of any kind (no clean, no upload); marker STANDING. root.json seq 2: state 'saved',
reason "saved on its day-bound marker ...", finish null, retained_booking day-run-20231018-day_slot_root-1791402822-3111,
retain_error null, child null; owner cpus 0-31, commit 6076950; last attempt pid 88228 commit 6076950 result saved
ended_utc 03:14:56Z; root-worker.log: state waiting_owner 03:14:56Z, front seq 2 "saved on its day-bound marker",
worker_lock_held false. teacher 0. No receipt for a2 (the ROOT never completed on any checkout: c9bf631 killed in
the digest 02:08Z, e0d7ae0 killed in the layer parse 02:59Z, 6076950 killed in the layer parse 03:14Z).
### (4) Stop, ec2 03:16Z (state-changing; parent's go)
CreateTags KeepRunning=false (+ reason "relaunch-2 role 2026-10-08 03:16Z: Greg: shut down for tonight; a2 day 20231018
saved on its marker (ROOT child 88265 killed 03:14:11Z, entry saved 03:14:56Z, booking retained); box stopped by
StopInstances"); DescribeTags read back KeepRunning=false. StopInstances i-035994afa8bdf66a5 (us-east-1) at 03:16:24Z:
running -> stopping. Instance r7i.8xlarge; volumes /dev/sda1 vol-0d36715924f03b86c DeleteOnTermination true, /dev/sdf
(archive) vol-004b68c077be09cc9 DeleteOnTermination false; a stop keeps both.
Other instances (DescribeInstances, read-only): us-east-1 i-0d17573dbce871520 "frankie-linux-r7i4xl" r7i.16xlarge
stopped (KeepRunning false, launched 2026-10-07T19:03:28Z); us-east-2 i-08cee7171c0a76a04 "markets-year-pull-v2"
r6i.2xlarge stopped (launched 2026-09-29T12:26:28Z). Nothing else running in either region; nothing else stopped.
### (5) Final: i-035994afa8bdf66a5 state 'stopped' at 03:17:03Z (DescribeInstances poll). KeepRunning=false. Nothing else
running in us-east-1 / us-east-2. a2 state on the stopped box: entry saved on the standing marker (03:09:51Z, sha256
5738b245...), booking ...-3111 retained (CPUs 0-31), owner commit 6076950, no teacher, no receipt. Resume tomorrow:
ACTION=resume then kick (FRANKIE_ROOT_DIGEST=off FRANKIE_CLEAN_ON_SAVE=off) on a checkout with the tail-anchor fix
(inline_layer_without_array: anchor on the first top-level key after `],`, not "reason") and a spool-count source for a
count-less seal (the sealed layer head's `count`). Reported to main 03:17Z.
