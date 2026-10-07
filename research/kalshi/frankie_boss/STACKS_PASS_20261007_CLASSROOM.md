# Stacks pass, classroom stage (2026-10-07 night, session 5)

Greg's go (session 5): "make sure every workflow step has been updated with the optimizer stacks, cpu and workers for
multiple steps in each piece and the aws tool upgrades that root got from the deep dive". Owner: the classroom stage
agent. Branch `ccr-d2f8f826-iefeah-frankie`, base `2f39ddc`. The parent's WIP snapshots (`92a0889` .. `c7a8228`) already
carry these edits; diff them against `2f39ddc`. SOURCE-BUILT / RUNTIME-UNVERIFIED. No AWS call, no run, no install.

Files changed: `deploy/aws/box/frankie_box_experiment_classroom_v2.py` and `deploy/aws/box/frankie_box_classroom_code.py`.
No other owned file needed a change (reasons in the table). No WIP half-edit was found: every owned file compiled and
`bash -n` passed at the start.

**a2 gets this only through a restage of the work-branch tip before its classroom stage starts.** a2's ROOT runs on
c9bf631, and the classroom stage reads the checkout staged for it. Stage the TIP, never one of the WIP snapshots.

## 1. Audit (before -> after), file:line on the current tree

| Item | Before | After |
|---|---|---|
| A1 pools sized from the booking | PARTIAL. `K.lane_cpus` (classroom_code.py:37) read only FRANKIE_LANE_CPUS, then the affinity. Native series, picture texts, 171 pairs and side tasks all size from it. The learner walk sizes `len(booked)-1` (classroom_reader.py:85). | DONE. FRANKIE_BOOKED_CPUS added as the fallback, in the same order lane_pin reads them (classroom_code.py:37-57). Not intersected with the affinity, because the learner walk compares the two and refuses on a difference (classroom_reader.py:68). |
| A2 workers pinned, serial consumer on a whole core | DONE. The pass consumer is pinned to lane[0] plus its siblings once the reader streams start, and its mask is restored afterwards (classroom_code.py:365-428). Every pool is pinned through lane_pin placement. Gap: lane[0]'s sibling stays in the timeline's decode list, which is cross-owner (see 6). | DONE (unchanged). Side-task pins are now recorded: `_side_main` writes a pin note that the parent reads (v2.py:239-260, 299-305). |
| A3 ordered hand-off / in-order join | DONE: ordered_map in native series (classroom_code.py:1502), picture texts (2754), and pairs by index (2839). | DONE (unchanged). |
| A4 dead worker redone with one fewer | DONE: ordered_map. The 171 pairs re-run the lost pairs on a new pool with live-1 workers (2839-2900). A dead side task is redone in order (v2.py `_SideTask.result`). | DONE (toy-tested, section 4). |
| A5 each input read/hashed once | PARTIAL. The journal witness is measured once and handed to the core, so the learner walk and the full reader hit the same cache (v2.py:395-440). teacher-attachment.pkl was streamed for its sha256 and then read whole again. | DONE for the attachment: one read, hashed in memory, unpickled from the same bytes (v2.py:443-452, 531-534). Remaining small re-reads are listed under F. |
| A6 pictures made once | DONE: anchor pictures are encoded once and spliced into each answer (classroom_code.py:2690-2790). | unchanged |
| A7 sub-steps side by side | PARTIAL. Only exhaustion/D ran beside the market read. | DONE+. Exhaustion/D, stage-knowledge reproduction and school reproduction all run as forked side tasks beside the full ordered read (v2.py:745-770, 799-810). More spots are in section 3. |
| A8 every stop bounded | MISSING. The classroom installs a SIGTERM handler that only marks a save (v2.py `run`). Every process forked from it inherited that handler: pool workers from `lane_pin.ordered_map` (`pool.terminate(); pool.join()`, lane_pin.py:435-437) and the 171-pair ProcessPoolExecutor (terminate on broken, then join). On terminate they kept running, and join() waited forever. This is the exact a2 shard-exit-hang shape. | DONE. `_owner_sigterm` (v2.py:338-353) is installed in `run` (v2.py:355-358). In the owner it marks the save as before. In any forked child it restores SIG_DFL and re-raises, so the child exits. Reproduced and fixed in the toy (section 4, test 1). `_SideTask.cancel` was already bounded (terminate, join 5, kill, join 5). `_SideTask.result` joins a live computation on purpose and returns at once on a dead one. |
| A9 BLAS/thread env fixed | DONE: v2.sh exports OPENBLAS/OMP/MKL=32, and `EXT.blas_reduction` settles the count after load (classroom_code.py:1360-1365). | unchanged |
| A10 byte-identical toy | n/a before | DONE (section 4). |
| B1 sizes from plan/booking | see A1 | DONE |
| B2 FRANKIE_WORK_PROBE / stage heartbeat with units and stall | PARTIAL. The only units were "saved operations" per phase (v2.py phase()) plus native "pictures" during the pass. The full ordered read without native entries, the native series phase (units stuck at the picture count, so a 10-minute series phase read as STALLED), the picture-text pool and the 171 pairs published no moving units. Forked series workers also wrote their own lines, which alternated with the coordinator's. | DONE. `K.heartbeat` (classroom_code.py:84-100) feeds report_phase. Moving units now come from: the market read (`classroom: shared market read`, pictures, every 4096, :396) when the native entries do not report; native series (`classroom native entries: series`, done/total, :1137 and :1520-1547) from the coordinator only; picture texts (:2775); 171 pairs (:2877). The stall flag (600 s, frankie_box_stage_progress.py:351) can now see a hung sub-step. |
| B3 run settings exported to children (FA-6) | N/A here. The queue/Run wrappers export them, and v2.sh only execs python, so the environment passes through unchanged. | unchanged |
| B4 DETACH exit semantics (FA-2) | N/A. That lives in the queue wrappers. v2.sh exit codes (0/3/75/other) are documented in its header. | unchanged |
| C S3 ranged GETs / CRT | N/A. The classroom reads no S3 object. Every input is a local file the ROOT/teacher/ingest wrote on the box. Large local sequential reads use 16 MB blocks (frankie_box_filehash.py:36). Box read-ahead (4 MB) applies. | unchanged. Where (c) "skip re-hash on unchanged stat" would apply: `_pin_outputs` (v2.py:177) re-hashes files this process just wrote. Not applied (Greg's open call). |
| D day-1 visibility | PARTIAL. The phase heartbeat swallowed its own exceptions (v2.py phase()). The side-task pin outcome was not recorded. | DONE. Probe import errors are counted in `K.PROBE_ERRORS` and land on `received.probe_errors` (refusal :860 and complete :1032). Side pin outcome is in `received.side_by_side.<op>.pin`. Output-pin placement and time are in `received.output_pins`. Identity acceptance is in `received.identity_acceptance`. SOCRATIC/VERIFY still refuse visibly without the learner reader (v2.py ModeNotAnswerable branch). Nothing was forced to TEACH. |
| E science unchanged | - | Answers, carries, series, categories, queues, pins and receipt meaning are unchanged. Every field added to the receipt is additive (`identity_acceptance`, `probe_errors`, `output_pins`, `stop_polling.forked_children`, `teacher_attachment.read`, `side_by_side.<op>.pin`). `received.exhaustion_d_code` / `native_entry_code` keep their whole-file sha256 meaning. Old saves still load (item 5). |
| F1 compute dedupe | Journal: once (DONE). Pictures: once (DONE). Attachment: twice (fixed). Small files read more than once, by size: calculations-receipt.json (v2.py:401, the identity sha, exhaustion_d_facts classroom_code.py:2266, reader classroom_reader.py:48); source-binding.json (v2.py:410 + sha + reader :52); the day file (v2 sha, package, `external_points_use` classroom_code.py:2531, KX independent read). | Attachment fixed. The others are KB-sized JSON. Merging them would mean passing parsed objects across owner boundaries (EXT, KR), so they are listed and left. derive.json is read whole and hashed by exhaustion_d_facts (classroom_code.py:2268) and then read again by `frankie_box_teach.facts` `_load` (cross-owner, 6). |
| F2 pass dedupe | Native entries already take one pass with changes-only ledgers, materialized per series (classroom_code.py:900-1000). The biggest duplicated pass: the classroom's full ordered read of the shared market repeats the teacher stage's read of the same source, and on SOCRATIC/VERIFY days the learner walk adds a third. | Unchanged in this pass. It cannot be collapsed inside the classroom files (6.1, 6.2). |
| F3 content dedupe (model-read content) | No model reads the classroom's answers (Frankie is code; MODEL_IDENTITY v2.py:54). The one model-read product is Jev's material `jev-material/classroom-request.json` (v2.py:690-697), whose bytes are pinned on the receipt and checked on resume. The Jev relay re-packages it (frankie_box_jev_relay.sh ACTION=material). | Not changed here. Stacking belongs in the relay's render, using `frankie_box_reading_render` / `frankie_box_stacked_text` with parse-back proof (6.5). Changing the classroom's JSON bytes would refuse every retained material. |
| Item 5 exhaustion_d_code function-level | MISSING. Whole-file sha256 of frankie_box_teach.py and frankie_box_bedrock.py. | DONE (2). |
| Greg's call (e), native cutoff | `_NativeEntryArithmetic._check` returns True as soon as `self.cutoff` is set (classroom_code.py:1113-1118). Defaults are 3600 s / 48 GB / check every 10,000 pictures (:809), env FRANKIE_NATIVE_CUTOFF_* (:810). Documented only; not decided here. | unchanged |
| staged / workers / cache / external_code / reader / classroom.py / V1 arm | staged.py:59 `ThreadPoolExecutor(max_workers=8)` is HTTP fetch threads on the old principal-session route (frankie_box_boss_session), not the experiment classroom. workers/cache are the same route. external_code has no pool (numpy on the parent). The V1 arm installs no SIGTERM handler, so its children keep the default. | N/A, unchanged |

## 2. Changes (function names, line ranges on the current tree)

v2.py = `deploy/aws/box/frankie_box_experiment_classroom_v2.py`, K = `deploy/aws/box/frankie_box_classroom_code.py`.

1. **Bounded stops.** v2.py `_owner_sigterm` (338-353) is installed by `run` (355-358). `received.stop_polling.forked_children` records it. Bytes are unchanged because the handler only changes how a forked child reacts to SIGTERM. In the owner it does the same thing as before.
2. **Function-level exhaustion/D identity (drop-in open item 5).** v2.py adds `EXHAUSTION_D_CODE`, `NATIVE_ENTRY_CODE` (90-105), `_code_identities`, `_whole_file_identities` and `identity_acceptance` (108-134). It uses `frankie_box_bedrock.code_identity`, the same as the native identities in eac32a0.
   - The declared names are the transitive closure, computed by AST inside each file, of what the classroom calls. teach: `facts` and its 16 helpers and constants. bedrock: `producers_commit`, `load_producers`, `crosswalk_records` and their 6 helpers and constants. joined_teacher: `_flatten`, `CATEGORY_LIMIT`.
   - The identity binds the function-level form (v2.py identity dict, ~549-556).
   - `_run` accepts a saved identity that is equal (`code`). It also accepts one that equals the current identity with those two fields in the earlier whole-file form, while the files are byte-identical (`whole_file_unchanged`). In that case it keeps the saved identity, so the saved phase files load (v2.py 604-613). The result is recorded as `received.identity_acceptance`.
   - `received.exhaustion_d_code` / `native_entry_code` still carry the whole-file sha256 values (meaning unchanged).
   - Not covered (as before): `frankie_box_digest_sources._JSON`, which teach imports.
3. **Attachment read once.** v2.py `_run` (443-452, 531-534): read, hashed in memory, checked, unpickled from the same bytes. `received.teacher_attachment.read` names it. The object is the same because the bytes are the same.
4. **Side by side.** v2.py `_run` (745-770): `exhaustion_d_facts`, `knowledge_reproduction` and `school_reproduction` start as `_SideTask`s off the consumer core, before the full ordered read. Each phase takes `.result` (799-810).
   - Why bytes are unchanged: each value comes back through pickle, the same way its saved phase does. A resume already hands every later consumer that unpickled value.
   - The two reproductions read only `visible` and the retained learner_inputs. `_evidence(visible)` is cheap in every mode at that point: TEACH transcribes; GUIDED is cached by the guided_evidence phase; SOCRATIC/VERIFY return the learner evidence. So no 171-pair pool is started inside a side process.
5. **Side pin visible.** v2.py `_side_main` (239-260) writes `<value>.pin`. `_SideTask.result` reads it into the record (299-305). Stale notes are removed at start (279).
6. **Output pins on pinned threads.** v2.py `_pin_outputs` (174-208) hashes on `frankie_box_lane_pin.executor('thread', ...)` and places pins in `names` order. It uses the same `frankie_box_filehash.witness`. It falls back to one thread with the reason recorded. `received.output_pins` records it (1033).
7. **Heartbeats.** K `PROBE_ERRORS` and `heartbeat` (84-100). Where they fire:
   - market read (396)
   - `_check`: coordinator only, units by phase (1121-1141)
   - `_native_series_parallel`: thread path `counted` (1513-1527); fork path series_done after each in-order chunk (1535-1547)
   - `picture_texts` (2775), `_pair_measures` (2877)
   - v2 phase() uses `K.heartbeat` (645). `received.probe_errors` (860, 1032).
8. **Booking fallback.** K `lane_cpus` (37-57).

## 3. Additional CPU spots (classroom stage end to end, ranked by expected gain)

Shares are estimates. The classroom has never run on a full day; `phase_timings` on the receipt measures them on day 1.

| Rank | Stretch (file:line) | What | Est. share | Science allows? | How | Status |
|---|---|---|---|---|---|---|
| 1 | v2.py:767 `market_context` (K:304-470) | One full ordered read of the shared market. Serial consumer on lane[0]; decode on lane[1:] inside the timeline. | 50-80% (dominant) | Yes, by segment, once the core can start at a cursor: pictures are built new per INPUT and anchors are known up front. | Segmented replay by pinned workers, from the saved group-closed states (template item 2), merged in order. | BLOCKED: cross-owner market_timeline start-at-cursor. That file is hashed into a2's binding, so after a2 (drop-in open 3). |
| 2 | v2.py:716 `KR.read_day` -> `experiment_teacher._teach` (SOCRATIC/VERIFY only) | The learner's own full walk, then the market read (1), serially. | Equal to 1 on those days | The learner walk must stay independent. The classroom read depends on its evidence (anchors), but could be fused into the same walk's shared read. | Fuse: the walk's shared read retains the anchor pictures, arrivals and native operands. | BLOCKED: cross-owner experiment_teacher. TEACH/GUIDED days skip it. |
| 3 | K:900-1100 `native.note` on the consumer thread | The native operands per picture, on the serial consumer. | Unmeasured (`native_entries.hot_path_seconds`) | Yes. | A pipelined second process fed by the timeline. Pickling pictures likely costs more than it saves, so it needs a measurement first. | Unmeasured |
| 4 | v2.py:834 the 19 `component_answer` calls, serial | Each splices pictures and computes texts. | Unmeasured; could be minutes | Not as written. `ClassroomMarketContext` records per-component use (stateful), so children would lose it. Safe only if each child returns its use record and the parent merges them in name order. | ordered_map over names plus merged use records. | Listed (needs a ClassroomMarketContext change and a proof that the use records merge identically). |
| 5 | v2.py:841 `KX.answers` beside rank 4 | The external section: numpy Pearson, independent of the 19 answers. | Small to medium | Yes, but a fork after OpenBLAS threads exist, under the blas_reduction contract, needs its own proof. | Parent thread or side task. | Listed (BLAS fork proof) |
| 6 | v2.py:911-935 V1 grade chain and v2.py:927-935 external grade chain | Two independent host chains, run serially. | Small | Yes; independent inputs. | Two side tasks. | Listed (small; ordering of the saved phases must stay) |
| 7 | v2.py:885-947 large `_dump` writes | json.dumps then write, serial. | Small to medium (code-answers.json carries the picture texts) | Yes. | A writer thread overlapping the grade chain. | Listed |
| 8 | v2.py:1022 `_pin_outputs` | About 25 sha256s, serial. | Small to medium | Yes. | Threads. | BUILT (change 6) |
| 9 | Exhaustion/D and the two reproductions | Ran after the read. | Small to medium | Yes. | Side by side. | BUILT (change 4) |
| 10 | Idle hyperthread: lane[0]'s sibling | The consumer is pinned to its whole core, but the sibling is still in the timeline's decode list, so it is not idle and not whole. | - | - | Drop the sibling from the decode worker list. | BLOCKED: cross-owner market_timeline / journal reader |
| 11 | `teach._streams` (frankie_box_teach.py:174) | Six spawn processes, unpinned, inside the side process. | Small | Yes. | Pin them through lane_pin. | Cross-owner (teach is pinned by the identity) |
| 12 | brain publication fsync loop v2.py:949-998 | Serial fsync. | Tiny | - | - | Leave |

## 4. Tests run (scratchpad `classroom/selftest.py`; Python 3 here, box deps absent where noted)

Command: `timeout 300 python3 selftest.py`. Output, verbatim keys:
```
1_pool_terminate_join_old_handler HUNG (timeout 20 s)
1_pool_terminate_join_new_handler joined True
2_identity_files {'frankie_box_teach.py': '1babdb754abd', 'frankie_box_bedrock.py': 'ccb8aa83fb7e'}
2_acceptance ['code', 'whole_file_unchanged', None, None]
2_comment_edit_same_change_differs [True, True]
3_pins_equal_serial [True, [{'name': 'missing.json', 'reason': 'not on disk after the classroom wrote its files'}], 4]
4_side_value_equal [True, 'side_process', 'pinned']
4_dead_side_redone [True, 'redone_in_order', 'side process exit 9']
5_lane_booked_fallback [0, 1]
5_native_series_equal_serial [True, True, 300, 'classroom native entries: series', 300, 300, 30]
5_thread_path_equal_serial [True, True, 300]
5_probe_errors {}
```

What each test does:
1. A forked Pool whose 4 workers are busy computing 32 MB results is terminated and then joined. Under the old save-mark handler it hangs; under `_owner_sigterm` it joins. In both cases a SIGTERM to the owner still only sets the save flag.
2. The identities compute. A comment-only edit keeps the code identity and a signature change alters it. The whole-file form is accepted only while the bytes match; a changed file or field refuses.
3. Threaded pins equal serial sha256 values, in the same order.
4. A side value equals the direct call. A side process killed with exit 9 is redone in order and recorded.
5. Run on the real `_native_series_parallel` through `lane_pin.ordered_map` (fork, 300 jobs, 30 chunks) and its thread path. Both equal serial (== and JSON bytes). The phase file shows units 300/300.

Also run: py_compile and ast.parse on both changed files and every owned .py; `bash -n` on both .sh; `git diff --check` clean.

Not run: any box module path that needs the ROOT, the market timeline, research packages beyond import, or the real classroom.

## 5. RUNTIME-UNVERIFIED
Everything on the box:
- the side tasks beside a real market read (memory: three COW forks of the classroom process)
- the heartbeat lines under Run.child
- `_owner_sigterm` under a systemd group stop: forked workers now exit on a group SIGTERM, and their tasks are redone by ordered_map, where before they ran on
- output pins on real files
- identity acceptance on a real saved classroom (a2 has none yet)

## 6. Cross-owner requests (named precisely)
1. `frankie_box_market_timeline.py` (after a2; hashed into a2's binding): start-at-cursor and segmented replay from group-closed saved states, so the classroom read gets a save/resume point inside the read. Today a stop mid-read resumes from the read's start; every other operation resumes at its saved phase. Also drop lane[0]'s sibling from the decode worker list, so the consumer's core is whole.
2. `frankie_box_experiment_teacher.py`:
   - (a) `teach()` installs the same save-mark SIGTERM handler (frankie_box_experiment_teacher.py:436) before forked pools. Use a pid-guarded handler like `_owner_sigterm`, or SIG_DFL in pool initializers.
   - (b) A shared-read handoff: the teacher stage's (or learner walk's) full read retains the classroom's anchor pictures, arrivals and native operands, so the classroom read (rank 1/2) is not a second pass.
3. `frankie_box_lane_pin.py` (shared helper): `_pool_initializer` / `_tracked_initializer` should set `signal.signal(SIGTERM, SIG_DFL)`. That makes every ordered_map/pinned_pool/executor worker safe whatever handler its parent holds (the root cause of the a2 shard hang family). `ordered_map`'s final `pool.join()` should also be bounded (join with timeout, then kill).
4. `frankie_box_teach.py`: `facts()` could accept the derive.json already read and pinned by the classroom (one read instead of two), and pin `_streams` through lane_pin. Any change there moves the function-level identity on purpose.
5. Jev relay (`frankie_box_jev_relay.sh` ACTION=material, Jev render): stack Jev's material with the existing lossless stacks (`frankie_box_reading_render` / `frankie_box_stacked_text`, parse-back proven) before Jev reads it. The classroom's `classroom-request.json` bytes stay as they are (pinned on the receipt, checked on resume).
6. `frankie_box_classroom_code.ClassroomMarketContext` (mine, not built): per-component use records mergeable from workers, to enable rank 4.

## 7. Template mapping (the Sept-29 templates -> classroom functions)
| Template item | Classroom function |
|---|---|
| 1 pieces side by side | v2.py `_SideTask` + `_run` 745-770: exhaustion/D, knowledge and school reproduction beside the read |
| 2 pass 1 state / pass 2 segment replay by pinned workers / pass 3 patch; exact saves at group-closed points | Per-operation exact saves: v2.py `phase()` and saved-phases/*.pkl, the identity-checked resume. The native series are a pinned ordered_map replay over the one pass's changes-only state (K `_native_series_parallel`). A save inside the read needs 6.1. |
| 3 deferred verify | Not used. Every check stays inline (journal witness against its pin, attachment, day file). The witness is overlapped on a thread (v2.py:395-440). |
| 4 no full copy at a group close | Anchor pictures retained by reference, not deep-copied (K market_context:417). |
| 5 batch decode with every per-record check | Inside the market timeline (cross-owner); the classroom reads no spool, so `decoded_spool` (experiment_search.py:473) has no classroom caller. |
| lane_pin lane_cpus/core_order/placement | K `lane_cpus` (same env order), `LP.consumer_core`/`pin_core` (K market_context) |
| lane_pin ordered_map | K `_native_series_parallel`, K `picture_texts` |
| lane_pin executor | K `_pair_measures` (process), K `_native_series_parallel` thread fallback, v2 `_pin_outputs` (thread) |
| lane_pin record | `received.cpu_pinning.*`, `received.output_pins` |
| classroom commit 5de6392 sub-steps | v2 series/categories/queues (ordered_map), pictures (ordered_map), exhaustion/D (side task), pairs (executor with redo). The reader (learner walk) reuses the teacher's pinned walk sized from the booking. Code answers, external code and staged have no pool (see rank 4/5; staged is not on the experiment path). |

## 8. Save/restore vs ROOT (follow-up, Greg: "every workflow piece needs their restore save code updated to match ROOT's")

v2 = `deploy/aws/box/frankie_box_experiment_classroom_v2.py`, K = `deploy/aws/box/frankie_box_classroom_code.py`. Lines
are from the current working tree. SOURCE-BUILT / RUNTIME-UNVERIFIED.

| ROOT item | Classroom before | Classroom now |
|---|---|---|
| 1 save route, exit 75, children not mark-only | PARTIAL. SIGTERM / the lane stop file marked a save. `phase()` stopped between operations (v2 `stop()` :738-742) and exited 75 (`TeacherSaved`, a SystemExit(75); `run` records `last_event` saved, :450). Forked children inherited the mark-only handler. Inside the long sub-steps a request was honoured only at the end of the operation. | DONE. `_owner_sigterm` (v2:412): forked children get the default action. The three long sub-steps check the request at every closed boundary, save, and raise `TeacherSaved` (K `_Segments.offer`, :160-185). Queued pairs/series are cancelled, so exit waits only for work already running (K :1620-1628, :3010-3022). Saved, failed and refused stay distinct on receipt.json (v2 `_failure_receipt`; exit 3/75/1). The queue side (frankie_box_frankie_queue.py:175) is unchanged and not mine. |
| 2 periodic exact saves at closed boundaries | PARTIAL. One exact save per completed operation (saved-phases/*.pkl, sha256-prefixed pickle). Nothing inside the native series, 171 pairs or picture texts. | DONE. K `_Segments` (:111-200) runs every `FRANKIE_CLASSROOM_SAVE_EVERY_SECONDS` (default 120 s, v2:714). It also saves on a request. Boundaries: each in-order native series chunk (K `_native_series_parallel` :1603, fork and thread paths), each pair in pair order (K `_pair_measures` :2993 pool, :3050 serial), each anchor picture text in cursor order (K `picture_texts` :2885). Each save is one more segment file holding only the new values (`parallel_teacher._save_raw_state`: pickle, key order kept, sha256 prefix, fsync, rename). The key binds the classroom identity digest, the operation and its whole job list (functions by qualified name, never by address, K `_job_key` :120). Segments are removed once the sub-step returns; its phase then saves it. A cutoff marker is never saved; saving stops at the first one. |
| 3 file positions without re-read | N/A for spools: the classroom appends to no spool or part file and reads no spool itself. The journal is read by the market timeline (cross-owner). Two large inputs: the journal witness was fully re-hashed on every resume; teacher-attachment.pkl is read whole every attempt because it must be unpickled. | DONE (mirrored, the classroom has no RowSpool). The journal claim is saved in `<classroom>/journal-witness.json` with the additive resume block, by `_journal_witness_record` (v2:211, written at :612): device, inode, mtime_ns, size and the last MiB's offset/sha256. This is the line-free form of `_saved_spool_position` / `_line_ending_at`. A resume on the same unchanged file takes the claim without a full read; anything else is one full pass, with the reason on `received.journal_witness.resume.how` (`_saved_journal_witness` v2:220; the rule of `_resume_row_spool`). The recorded sha256 is the same value. The attachment stays one combined pass (read, hash in memory, unpickle the same bytes). No stat-only skip anywhere. |
| 4 identity is content, not location | MISSING. Any path difference refused, e.g. `rules.path` names the checkout's CLASSROOM_RULES_V3.json. | DONE. `checkout_rebinds` (v2:134) applies `frankie_box_experiment_root.content_rebinds` to the saved identity versus the one this checkout builds, in its code form and its whole-file form. Only checkout-prefix moves of equal bytes/sha256 are accepted. They are recorded under `<classroom>/checkout-rebinds/` (`_record_rebinds` v2:148) and on `received.identity_acceptance.checkout_rebinds`. The saved identity stays the identity (v2 ~700-712), and nothing saved is rewritten. |
| 5 function-level code identities | DONE in the first pass for exhaustion/D and native entry code (v2 `EXHAUSTION_D_CODE` / `identity_acceptance` :99-131). PARTIAL for the classroom's own code: `runner_sha256` and `producers` still bind the classroom's own modules by whole bytes, so any edit to classroom code refuses a saved classroom. | unchanged. Listed: a2 has no classroom save yet, and its classroom stage starts from the restaged tip. Moving the classroom's own producers to declared functions is a separate, larger step. |
| 6 additive, old saves load, probe continues | PARTIAL | DONE. New files/fields only: `journal-witness.json`, `segment-saves/`, `checkout-rebinds/`, and `received.segment_saves` / `journal_seal_check` / `identity_acceptance`. A c9bf631 classroom identity has the same field set (checked against `git show c9bf631`) and loads through `whole_file_unchanged` while those files' bytes and the runner/producer bytes match. A save without journal-witness.json takes one full pass, noted. Without `SEGMENT_SAVES` (an older runner) nothing is saved inside sub-steps and the values are unchanged (test 4). The heartbeat continues from the resumed count (series_done = start; pairs and pictures count the resumed values). |
| 7 seal check against the saved claim | MISSING | DONE. When an attempt took the journal claim without a full read, the full read runs as a side process beside the stage (v2 :864). It is compared at the seal before the receipt (v2 ~1150-1160, ROOT's `_check_spool_claims`). A difference raises, so the failure receipt names it. Every saved phase file is checked by its own sha256 prefix on load (`_load_raw_state`). |

**The one listed exception:** the full ordered market read (`shared_market_context`, K `market_context`) cannot save mid-read. A stop there raises `TeacherSaved` with no partial reading claimed, and a resume reads again from the start. Saved native-series segments are reused after it, because the read is deterministic and the segments are keyed by identity and job list. Lifting this needs `frankie_box_market_timeline.py` start-at-cursor and segmented replay from group-closed states, which is cross-owner and after a2 (that file is hashed into a2's binding).

Also listed:
- The native-entry cutoff clock (Greg's open call (e)) counts the current attempt's native work only. A resumed series phase can therefore compute series an uninterrupted run would have cut off. Recorded here, not decided.
- Pickle bytes of the pair values differ between the pool path and the serial loop even without any save (memo sharing), while the values are equal and their JSON bytes are identical (test 2b). The products are the JSON files.

### Toy proof (scratchpad `classroom/selftest2.py`; research package `__init__` skipped because torch is absent here)

Each case: save (a requested save after 3 arrivals: exit 75, one segment file) -> resume -> compare with from scratch.
```
1  native series, fork pool:   exit 75, 1 segment, resumed 40 of 300 series, equal (== and JSON bytes), segments removed
1b native series, thread path: exit 75, 1 segment, resumed 4, equal, removed
2  171 pairs, fork executor:   exit 75, 1 segment, resumed 4, equal (== True, JSON True; pickle bytes differ, see above)
2b pool path without any save: == True, pickle bytes differ (pre-existing; values equal)
3  anchor picture texts:       exit 75, 1 segment, resumed 4, texts equal
4  old shape (no SEGMENT_SAVES): values equal, saving disabled
5a another identity's segments: not read (0 resumed), values equal
5b a tampered segment:         refused ("saved teacher state hash differs; retained, not discarded")
6  journal witness:            same file -> claim without a full read; appended file -> "the file is not the one saved
                               (size, device, inode or mtime differ)"; no journal-witness.json -> "the save recorded no
                               journal witness (a first attempt or an older save)"
7  identity from another checkout (rules path under /opt/frankie-box/code/c9bf631-x/markets/):
                               direct equality None; content_rebinds accepts ('code', the rules file relative path); a
                               changed sha256 -> None; an old whole-file save from another checkout -> 'whole_file_unchanged'
8  TeacherSaved exit code 75
```
Also run: py_compile on both files, `git diff --check` clean.

### Cross-owner (save/restore)
- `frankie_box_market_timeline.py`: start-at-cursor / segmented replay (the listed exception), after a2.
- `frankie_box_lane_pin.py:135-145, 306-310`: SIG_DFL in the pool initializers (the classroom now covers this for its own forks).
- `frankie_box_experiment_teacher.py:436`: the learner walk runs `_teach` inside the classroom. Its own saves inside the walk are the teacher's contract; the classroom phase `learner_reading` resumes it through `KR.read_day`'s retained receipt.
