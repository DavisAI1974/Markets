# Stacks pass, TEACHER stage (2026-10-07 night, session 5)

Owner: teacher-stage agent. Branch ccr-d2f8f826-iefeah-frankie at 2f39ddc. SOURCE-ONLY: no AWS call, no run, no install.
Owned files: deploy/aws/box/frankie_box_experiment_teacher.py (ET.py), frankie_box_experiment_teacher.sh (ET.sh),
frankie_box_teacher_knowledge.py, frankie_box_joined_teacher.py/.sh, frankie_box_teach.py, frankie_box_teacher_discussion.py,
frankie_box_teacher_successor.sh. The teacher's pools themselves live in research/kalshi/frankie_boss/parallel_teacher.py
(PT.py; added to this owner's files mid-pass by the parent, 2026-10-07 ~23:40Z) and the shared reader in
frankie_box_market_timeline.py (hashed into a2's ROOT binding: untouchable during a2).

## Interim audit (state at 2f39ddc, before any edit of this pass)

Step 0: py_compile on the five .py files and bash -n on the three .sh files all pass at 2f39ddc. The WIP snapshots
f9f4460 / 6dedbba / a215495 left the teacher files COMPLETE (no half-edit): the read-ahead precompute, the failed-next
propagation, the finish placement and the spare-CPU split are whole and consistent with PT.py at 42c4e89.

Which files are on a2's teacher path: ET.sh -> ET.py (Run.child stage 'teacher', DAY_RUN_STAGES, under
frankie_box_cores.py run --size day_cpus() = 32) is THE teacher stage. teacher_knowledge.py is called in-process by
the orchestrator after the rows (brain filing, small JSON, no pool). teacher_successor.sh is an exec wrapper of the
successor dispatch (later stage 14). teach.py, joined_teacher.py/.sh and teacher_discussion.py are not on the a2 path
(Monday-era facts; joined teacher retired from host config; the discussion is a model-voiced transport reused by the
exchange): N/A for CPU stacks, audited for D only.

| Item | State | Where (file:line at 2f39ddc) | Note |
|---|---|---|---|
| A1 pools sized from booking | DONE (one gap) | ET.sh:39-48,59-61,80-81 (own affinity = booking, SPARE split, FRANKIE_LANE_CPUS, --workers = slice-1); ET.py:527-540 (lane = sched_getaffinity) | Gap: ET.py:847 `--workers` default 8 literal (only a hand start; the wrapper always passes it) -> PARTIAL |
| A2 pinned workers, serial consumer on a whole core | DONE on the shared path | ET.py:527-540 (consumer core + siblings, raw CPUs physical first), ET.py:632-640 (pin after streams start), ET.py:712-718 (finish plan); PT.py:195-205 | Legacy no-policy walk unpinned by design (not a2's path) |
| A3 ordered hand-off / in-order join with overlap | DONE | ET.py:563-590 (read-ahead in source order), PT.py:820-830 join_ready while chunks run | |
| A4 dead worker: redo same args same slot, one fewer, never stop | DONE in PT pools | PT.py:333-357 (raw), PT.py:507-533 (precompute), PT.py:835-880 (finish) | Hazard NOT fixable here: the shared reader's decode pool (market_timeline.py:212-258) is a multiprocessing.Pool with `.get()` and no timeout: a dead decode worker hangs the walk forever (queued request 3 in the session-5 drop-in). Cross-owner, after a2 |
| A5 read and hashed once | DONE | ET.py:84-99 prefetch, ET.py:438-447 witness handed to the shared reader | rows file and attachment are written then re-read for sha256 (ET.py:776-777): PARTIAL (hash as written possible for the attachment) |
| A6 encode once | DONE | ET.py:550-620 EvidencePrecompute registered into PJ._CANONICAL/_SUBSETS, guard per batch | |
| A7 sub-steps side by side | PARTIAL | journal sha256 overlapped (ET.py:84); raw pool, precompute and walk overlap; finish join overlap | Publication tail is serial: attachment write -> rows write -> two re-read hashes -> external section; the rows-file hash and the attachment hash can run beside the external section |
| A8 every stop bounded | PARTIAL | PT pools are spawn (no inherited SIGTERM handler, so the a2 shard-hang pattern of fork + inherited handler + unbounded join does not apply); pool.shutdown(wait=True) after cancel waits only for a running batch | Unbounded waits remain in market_timeline (Pool `.get()`), cross-owner |
| A9 thread env fixed | MISSING | none of the teacher files sets OMP/OPENBLAS/MKL threads; PT._chunk imports torch in 31 spawn workers | torch is only used to build tensors (no reductions), so a cap cannot change bytes |
| A10 byte-identical toy self-test | DONE for PT pools (42c4e89 era, per its commit) | | re-run here for what this pass changes |
| B1 sizes from plan/booking | DONE (see A1) | | |
| B2 FRANKIE_WORK_PROBE_V1 / units heartbeat, stall flag | PARTIAL | ET.py:358-366 phase(): report_phase at phase boundaries only, units = number of phases | The raw pass (hours on a full day) and the finish pool show NO unit movement: the heartbeat's 600 s stall flag fires on a healthy walk and cannot tell a hung decode pool from a working walk. No progress.json for `frankie_box_progress.sh DIRECTORY=experiment-teacher-rows/<day>` (ET.sh:7 promises it) |
| B3 run settings to children (FA-6) | DONE | env inherited (ET.sh:49 export, no env scrub) | |
| B4 DETACH (FA-2) | N/A | the teacher is a Run.child of the orchestrator, no wrapper of its own | |
| C1 S3 ranged/CRT reads | N/A | the teacher reads only local files (sealed journal, ROOT, day file) | |
| C2 big sequential chunks | DONE | ET.py:101-106 64 MB blocks | |
| C3 skip re-hash on unchanged stat | N/A (Greg's open call c) | would apply to the sealed journal re-hashed by every later process (classroom, export, school) | |
| D visibility on receipt + inspection markdown | PARTIAL | cpu_pinning, raw_pool, finish_pool, evidence_precompute are on the receipt (ET.py:722-735) | NOT in workflow_report (the inspection markdown projects workflow_report only): pool rebuilds, not-registered batches, pin fallback, the prefetch's swallowed error (ET.py:92-94), the defaults taken (FRANKIE_TEACHER_CHANGES setdefault ET.py:471, workers default) are invisible in the markdown; workflow_report.outputs.waits is always [] |
| E science unchanged | DONE so far | | every change of this pass is additive |
| teacher_knowledge / successor.sh | N/A for A-C; D DONE | brain filing in-process; successor exec wrapper | |
| teach.py / joined_teacher / teacher_discussion | N/A (not on a2's path) | joined_teacher.py:756 default workers from os.cpu_count() (host count, not the booking) | listed, not changed: retired path |

Missing or partial today, in fix order: A8/A4 (cross-owner only), A1 default, A9 thread caps, A7 publication tail,
A5 attachment hash as written, B2 unit probes (raw pass and finish), D (stack events into workflow_report).

## After the pass (uncommitted edits; line numbers are of the edited files)

| Item | Before | After | Where now |
|---|---|---|---|
| A1 pools sized from booking | DONE, default literal 8 | DONE | ET.py:1001-1030 main(): `--workers` default = lane_pin.lane_cpus() minus one, listed in run_defaults |
| A2 pinned workers / whole-core consumer | DONE (shared path) | DONE, every PT pool through lane_pin.executor | PT.py:205-236 `_spawn_pool` (lane_pin.executor('process', n, cpus=plan, spawn); record() placement on each pool record); used by `_RawStreams._new_pool` PT.py:~430, `EvidencePrecompute._new_pool` PT.py:~655, `finish.new_pool` PT.py:~1050 |
| A3 ordered hand-off | DONE | DONE (unchanged) | |
| A4 dead worker redo one fewer | DONE | DONE, plus a redo submit that meets a broken pool no longer escapes | PT.py:280-292 `_submit` (Future holding BrokenProcessPool), used in `_RawStreams._result` |
| A5 read/hash once | PARTIAL | DONE in owned files | ET.py:134-143 `_HashingWriter` (attachment hashed as written; no read-back) |
| A7 sub-steps side by side | PARTIAL | PARTIAL+ | ET.py:~900-960: rows-file sha256 (and a retained attachment's) on threads while the external section builds; joined at `hash_publications` phase |
| A8 every stop bounded | PARTIAL | DONE in PT | PT.py:238-278 `_bounded_shutdown` (cancel queued, poll alive 50 ms up to STOP_GRACE_SECONDS=60, then terminate, kill after 5 s, listed as `stops`); every former `pool.shutdown(wait=True, ...)` replaced (raw rebuild/exit, precompute rebuild/close, finish rebuild/finally). The shared reader's Pool remains cross-owner (below) |
| A9 thread env fixed | MISSING | DONE (CLI path) | ET.py:1016-1022: OMP/OPENBLAS/MKL/NUMEXPR_NUM_THREADS=1 when unset, before any torch/numpy import; an operator value stands; listed in run_defaults |
| A10 toy byte-identity | per 42c4e89 | re-proved for this pass | below |
| B2 unit heartbeat + stall | PARTIAL | DONE | PT.py:297-317 `PROGRESS`/`_progress` (every 15 s; raw rows every 1,024, finish per chunk); ET.py:101-124 `_work_probe` writes FRANKIE_WORK_PROBE_V1 `<out>/progress.json` (frankie_box_progress.Probe) and the stage heartbeat's phase file (report_phase units_done/units_total/unit), so units/min and the 600 s stall flag now move with real work; ET.py:632 wired, reset in the walk's finally |
| B3 FA-6 env | DONE | DONE | |
| C S3 transport | N/A | N/A | local files only |
| D visibility | PARTIAL | DONE | ET.py:222-281 `stack_events` -> workflow_report.use.stacks (FRANKIE_TEACHER_STACK_EVENTS_V1): placement outcome, pool rebuilds, bounded stops, not-registered batches, resume skips, periodic saves, resumes, probe write errors, prefetch errors, every default taken. New receipt fields (additive): `raw_saves`, `journal_prefetch`, `run_defaults`, `cpu_pinning.*.placement/stops` |
| E science | DONE | DONE | additive only; see "Why bytes are unchanged" |
| F1 compute dedupe | see table F | | |
| Save/restore | stop-save only | ROOT-shaped (section below) | |

## F: dedupe, per sub-step (Greg: "Did we dedup in every step too?")

| Sub-step | Read / computed more than once today | Done |
|---|---|---|
| ingestion receipt | hashed by ET.sh (`sha256sum`, ET.sh:61) and by ET.py `_teach` (ET.py:~465); small file | left (the wrapper's sha is the given witness the step checks; a few KB) |
| sealed journal | hashed once per process (prefetch thread -> filehash cache -> witness handed to the shared reader, ET.py:70-92, ~490-505) | DONE; across processes (classroom, export, school) it is re-hashed: that is Greg's open call (c), skip-by-stat, not applied |
| first INPUT entity | a second CompactReader opened on the journal head (ET.py:~555) | left: reads the first block only |
| shared picture | read once (iter_applied) | DONE |
| canonical bytes of each payload | once (EvidencePrecompute on workers, registered, consumer only hashes) | DONE |
| resume of the raw pass | the saved prefix is read again by the reader (no start-at-cursor) and WAS encoded again by the precompute | encoding of the skipped prefix removed (ET.py:666-690 `present_seen` vs PT.RESUME_SKIP); the re-read stays (cross-owner: start-at-cursor in market_timeline) |
| attachment | written, then read back for sha256 | hashed as written (ET.py `_HashingWriter`) |
| rows file | written (SE._save canonical bytes), then read back for sha256 | read-back moved onto a thread beside the external section; SE.\_save is not owned (it holds the bytes in memory: a returned digest would remove the read: cross-owner, sunday_execution.py:45-69) |
| F2 pass dedupe | raw pass and finish are one pass each over the rows; the 19-column observe is per chunk once | nothing to collapse |
| F3 content dedupe | the teacher makes no model call (model_calls 0); its rows file and attachment are code-read, pinned formats hashed by every consumer | N/A: changing their encoding would change science bytes; no model-read text is produced here |

## Additional CPU spots (teacher stage end to end, 32-CPU lane, one day)

Wall-time shares are estimates from the code shape (the teacher stage has never run on 20231018 under the shared
policy; a1's teacher did not run): UNMEASURED.

| Rank | Stretch (file:line) | Serial today? | Share (est.) | Byte-safe parallel/overlap? | State |
|---|---|---|---|---|---|
| 1 | Shared reader decode + timeline merge (frankie_box_market_timeline.py:203-258 and its streams) feeding the raw loop | decode on lane[1:] workers; merge serial in the consumer | large (unmeasured) | yes (placement) | cross-owner, frozen during a2; plus the dead-worker hang (below) |
| 2 | The pinned raw loop c15_teacher_r3._paired_raw (stateful group history, chains, DChain machines) in PT.row_pass | serial by construction (state carried row to row) | the long pole | only the pure window functions are offloaded (done); the stateful part is the pinned equation: segment replay would need exact group-closed state snapshots of both raw teachers (the Sept-29 pass-2 pattern) | not built: needs a design for snapshotting JournalTeacher/RawJournalTeacherR3 continuation per segment (pinned files c15_teacher*.py unchanged); listed |
| 3 | Consumer's sibling hyperthread | the consumer is pinned to its whole core (consumer + sibling, ET.py:~590); the sibling hosts the executor manager/feeder threads and the precompute/read-ahead bookkeeping on purpose | n/a | the ROOT-equivalent of 16/17/24 idle: yes, deliberate (a worker there would steal cycles from the serial loop, the stage's limit) | kept |
| 4 | Finish (normalizer observe, targets, receipts) PT.finish | chunks on 31 workers, in-order join | medium | done | DONE |
| 5 | Normalizer update() replay to build chunk-start states (PT.finish "for start in range(prepared, ...)") | serial in the parent before the pool starts | small-medium for NormalizerR3 (identity normalizer: none, the a2 case) | could pipeline: submit chunk k as soon as its start state exists instead of after all are prepared | not built (identity normalizer on a2 makes it free); listed |
| 6 | Snapshot of the attachment (DC.snapshot_teacher_attachment) + SE._save canonical encoding of the rows (pure Python, GIL) | serial | medium on a full day | an encode on workers needs a split of pack/canonical_bytes per row (exact concatenation) in dipole_classroom/sunday_execution | cross-owner (dipole_classroom.py, sunday_execution.py) |
| 7 | pickle.dump of the attachment | serial, GIL-bound | medium | a forked writer beside SE._save would overlap it byte-identically, but forking a process that holds reader threads risks a lock held at fork | not built (risk), listed |
| 8 | External section (EXT.ensure_external_section) | serial | small | overlapped with the two publication hashes now | DONE (overlap) |
| 9 | Several days at once | ET.sh splits the booking over the days (SPARE split) | n/a | done | DONE |

## Save/restore vs ROOT (Greg's directive items 1-7)

| # | ROOT contract | Teacher | Where |
|---|---|---|---|
| 1 | save route: SIGTERM marks, runs to the next save point, exit 75; workers do not inherit the mark-only handler | DONE: teach() installs the mark-only handler (ET.py:425-443), row_pass/finish save and raise TeacherSaved (exit 75, PT.py:757-762). Every teacher pool is spawn (a Python handler is not inherited across exec) and lane_pin.executor's initializer now also resets SIGTERM (lane_pin owner's reset_worker_sigterm). The classroom's request (ET.py:436 teach(): forked pools inherit the handler): there is no fork pool in the teacher; the shared reader's Pool is spawn too | |
| 2 | periodic exact saves at group-closed points | BUILT: PT.py:820-845 SAVE_EVERY_SECONDS=1800 (env FRANKIE_TEACHER_SAVE_EVERY_S, 0 = off); due -> saved at the next row that closes its group (F_LAST receipt) AND ends a raw batch exactly (PT.py:~914), raw streams drained, the same state the stop-save writes (complete False), walk continues; SAVE_RECORD on the receipt (`raw_saves`). The finish already saves each chunk as it completes | |
| 3 | spool/file positions without re-read | N/A for writes (the teacher appends no spool); PARTIAL for reads: a resume re-reads the shared picture from instant 0 (no start-at-cursor in the reader); the encoding of the skipped prefix is now skipped | cross-owner: market_timeline start-at-cursor (queued request 3) |
| 4 | identity is content: content_rebinds | BUILT: PT.py:344-373 `_identity_accepted`: equal -> resume; else frankie_box_experiment_root.content_rebinds on the saved vs built identity; checkout moves recorded in `<recovery>.checkout-rebinds/<ns>.json`; the saved identity stays the identity (row_pass and finish adopt it). ET.py's retained-receipt check (shared_market_identity equality, ET.py:~525) still compares by equality: PARTIAL | |
| 5 | function-level code identity | BUILT: PT.py:322-341 ROW_PASS_CODE / FINISH_CODE through frankie_box_bedrock.code_identity (whole-file sha256 fallback when bedrock is not importable); old whole-file saves accepted while the file is byte-identical (toy) | |
| 6 | additive; old saves load; probe continues from the cursor | DONE: the old-shape save loads while byte-identical (toy); `_progress('teacher_raw_rows', processed)` starts at the resumed cursor. Note: a save written by the c9bf631 PT (whole-file sha of the OLD bytes) refuses on the new file: that is the rule (byte-identical only); a2's teacher has written no save | |
| 7 | seal check | DONE in substance: every process (fresh or resumed) re-measures the sealed journal against the ingestion receipt (the saved claim) before the walk and refuses a difference (ET.py:~495-505) | |

## Why bytes are unchanged

- Placement (lane_pin.executor vs the private initializer) only changes WHERE a pure function runs.
- `_bounded_shutdown` runs only after every needed result is collected (or when the step is already failing/rebuilding);
  a rebuild resubmits the same blobs in order, as before.
- The periodic save drains the raw streams only at a row that ends a batch exactly, so no batch boundary moves: every
  worker result is unpickled from the same batch, so even the in-memory object sharing (which the attachment pickle
  records) is the reference run's. Toy: pickle sha256 of the rows equal with periodic saves.
- A resume (from a periodic save OR the existing stop-save) gives equal VALUES; its rows' pickle object-sharing differs
  from an uninterrupted run (the loaded prefix's strings are other objects), so teacher-attachment.pkl bytes after a
  resume can differ while every value, the rows file's canonical bytes and the attachment hash are equal. This is the
  pre-existing behaviour of the stop-save, not introduced here; listed.
- `_HashingWriter` gives pickle the same file and records the digest of exactly the bytes written (toy: bytes equal, digest
  equal to the file sha256).
- Thread caps: torch only builds tensors in PT._chunk (no reduction), so a BLAS/OpenMP thread count cannot change a value.

## Tests run (scratchpad /tmp/claude-0/-home-user-Markets/2248cf40-1f2f-560c-b5b2-bc0289b3f56b/scratchpad/teacher/)

- `toy/run_toy.py`: a verbatim copy of the edited parallel_teacher.py in a toy package with a fake stateful raw loop
  (c15_teacher_r3 stand-in: three pure window functions on spawn workers through lane_pin.executor, a continuation dict),
  3,000 rows, RAW_BATCH_CALLS 64, 4 CPUs. Output (toy_output.json):
  reference pickle sha afdeddc6...; periodic saves (2 saves, at cursors 1279 and 2239) afdeddc6... (equal);
  crash at row 1777 after the save at 1280, resume from it: values equal (value digest 615bbf23... both), pickle differs
  (see above); a raw worker killed (os._exit) mid-walk: one rebuild to 3 workers, 8 batches redone, afdeddc6... (equal);
  old-shape save (whole-file sha of the same file) loads, values equal, note listed; old-shape save of another file
  refused ("saved teacher source, code or causal bound differs"); placement record lane [0-3], workers on [1,2,3];
  progress samples 0/1024/2048/...; ALL True.
- `toy/probe_stop.py`: `_bounded_shutdown` of a healthy and of a broken pool: 0.02 s / 0.0 s, nothing terminated.
- `toy_et.py`: `_HashingWriter` bytes equal and digest == file sha256; `stack_events` on a synthetic receipt: 9 events
  (bounded_stop, default, fallback, placement, resume, retry, save, skip); empty receipt -> [] and placement None.
- py_compile + ast.parse on the five .py files and parallel_teacher.py; bash -n on the three .sh; git diff --check clean.
- NOT run: the real teacher (torch is not installed in this container; the box venv has it), the shared reader, any
  journal, ET._teach end to end, content_rebinds with a real checkout move.

## RUNTIME-UNVERIFIED

Everything above on the box: the lane_pin.executor placement on the 32-CPU lane, the bounded stops, the periodic save's
cost on a full day (each save pickles every row so far; estimated tens of seconds per save at 30 min intervals), the
resume path on a real journal, the unit probes as read by frankie_box_stage_progress, the thread caps, the publication
overlap, the identity changes (code_identity) on real saves.

## Cross-owner requests

1. frankie_box_market_timeline.py:212-258 `_rows_parallel` (frozen in a2's ROOT binding; after a2): `pool.apply_async(...).get()`
   on a multiprocessing.Pool with no timeout: a dead decode worker is replaced silently and its task never completes,
   so the teacher (and every shared-policy reader) waits forever while the heartbeat shows the stall. Use
   lane_pin.ordered_map (or wait_result) over the ranges; and add start-at-cursor so a resumed teacher does not re-read
   the saved prefix. `pool.terminate(); pool.join()` at :257-258 is the unbounded-join shape too (lane_pin.end_pool).
2. sunday_execution.py:45-69 `_save`: return the sha256 of `raw` (it holds the bytes) so the rows file is not read back.
3. dipole_classroom.snapshot_teacher_attachment + sunday_execution pack/canonical_bytes: a per-row split of the canonical
   encoding would let the snapshot encode on workers (exact concatenation) - the largest serial tail after the walk.
4. frankie_box_experiment.py:1318-1319 Run.child: name `experiment-teacher-rows/<day>` as a probe_dir for the teacher
   stage (the phase file already carries the units; this adds the work-probe lines with completed_per_min).
5. frankie_box_lane_pin.py: when `end_executor` lands, parallel_teacher._bounded_shutdown (PT.py:238) should call it
   (one shared rule); today it is a local equivalent with the same bound-then-kill shape.
6. Pending from the school owner (R3): frankie_box_teacher_knowledge.py:338 and :453 should call
   ST.pre_read(days, docs, out_dir) once and pass scanned= to each ST.test(...). NOT done in this pass (time); additive.
7. Pending from the classroom owner: hand the full read's anchor pictures to the classroom so its second pass goes away
   (needs a published picture artifact from the teacher and a reader in classroom_reader): not built, listed.

## a2

a2's teacher stage gets none of this unless the work-branch tip is restaged BEFORE the teacher stage starts (after ROOT).
The teacher-knowledge producer identity (frankie_box_experiment.py:4077-4087) and the classroom reader's producer hashes
(frankie_box_classroom_reader.py:28-37) include frankie_box_experiment_teacher.py / parallel_teacher.py, so every stage
of a2 after ROOT must run on the same restaged tip. Never stage an intermediate WIP snapshot.

## Follow-up (parent's go while a2's teacher stage is held): R3 and the retained-identity check

### R3 (school owner): one shared pre-read in teach_accumulated (frankie_box_teacher_knowledge.py)
- Before: `ST.completed_native_evidence(days[0], out_dir)` (was :338), then one `ST.test(...)` per document (was :453),
  each scanning and hashing every search part again (dedupe F1 (b) in STACKS_PASS_20261007_SCHOOL.md).
- After (teach_accumulated, ~:333-395 and ~:480-492):
  - phase 1: the claim scheduling of every document, in the same order and with the same keys; each item's reuse
    entries are kept and appended at that item's own place in the loop, so `reused` keeps its exact order;
  - `result_plan(item, claims)`: the claim_inputs / result_identity / result path block moved verbatim into one pure
    function, called once in phase 1 (to skip documents whose result file already exists) and once in the loop;
  - `measured_doc(item, claims)`: the exact dict ST.test receives (the successor's affected subset);
  - `ST.pre_read(days, [measured docs], out_dir)` once: this owner day's completed native evidence AND the part scan
    of every document still to be measured, side by side on the school owner's pinned pool; `native_ref, native_listed`
    from it; each `ST.test(..., scanned=prepared)`; test() uses a prepared scan only when its key equals its own read
    plan, and its `report` (evidence_read, written into the result file) is filled identically either way;
  - fallback: no `ST.pre_read` (an older scientific teacher) -> the old reads, listed;
  - receipt: new top-level `pre_read` (the note pre_read returns, or the fallback reason); additive.
- Bytes: the native reference, rows, ordinals, raw-line hashes, counts and the read report are pre_read's / test's own
  (the school owner's toy: pre_read 1 doc identical=True; shared_scan 3 docs identical). Toy here
  (`scratchpad/teacher/toy_tk_order.py`): the restructured scheduling vs the original single loop on 12 synthetic
  documents (already-tested claims, cross-document duplicates, two existing result files): identical `reused` order
  (13 entries), measured documents (8) and scheduled count -> True.
- One behaviour difference, error path only: a ValueError raised while building a result identity ("original
  historical collection lacks its unchanged claims binding") is now raised in phase 1, before any document of the
  call is written or published, instead of after the earlier documents. No value changes.
- RUNTIME-UNVERIFIED: teach_accumulated itself was not run (it needs a brain, a search and retained lessons).

### Retained-receipt identity through content_rebinds (frankie_box_experiment_teacher.py)
- `_identity_matches(saved, built, out, what)` (ET.py ~:126-157): equal -> accepted; otherwise
  frankie_box_experiment_root.content_rebinds; checkout-prefix moves with equal bytes and sha256 accepted and recorded in
  `<out>/checkout-rebinds/<ns>.json` and on the receipt (`identity_rebinds`, and as `rebind` / `refusal` events in
  workflow_report.use.stacks); anything else refuses as before; nothing retained is rewritten.
- Used at the retained receipt's `shared_market_identity` check (was a plain `!=`) and at the saved shared read's
  identity check after the raw pass (was `shared_read.get('identity') != market.identity`), which otherwise would have
  refused a resume from another checkout even after parallel_teacher accepted its raw state.
- Toy (`scratchpad/teacher/toy_rebind.py`, real content_rebinds): equal True; checkout move with equal bytes/sha256
  True (recorded, one file written); changed sha256 False; a path outside the checkout False.
- Save/restore table item 4 for the teacher: now DONE (raw state, attachment state, retained receipt, saved shared read).

### Still recorded as requests (not built, per the parent)
- Anchor-pictures hand-off to the classroom (classroom owner).
- sunday_execution.py:45-69 `_save` returning the digest of the bytes it holds.

### Checks
py_compile + ast.parse on every owned .py, bash -n on the owned .sh, git diff --check: clean.
