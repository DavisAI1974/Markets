# Stacks pass, session 5: school / scientific-teacher stages (8, 9, 10, 14 successor side)

Owner: school / scientific-teacher stage agent. Greg's go, 2026-10-07 night session 5. Base 2f39ddc on
`ccr-d2f8f826-iefeah-frankie`. SOURCE-BUILT / RUNTIME-UNVERIFIED (toy self-tests only; no box, no AWS, no run).
The parent snapshotted these edits into WIP commits (92a0889 .. c7a8228) while the work ran; the record below is the
diff from 2f39ddc. a2 gets none of this unless the work-branch TIP is restaged before a2's lessons / survivors /
school stages start (never an intermediate WIP snapshot).

## 0. State of the owned files at the start
All 13 owned files compiled at 2f39ddc (py_compile / bash -n). The scientific teacher at the tip (928df52 on top of
the WIP snapshots 5128a73 / 306a14b) was whole: the half-edit the drop-in names in 5128a73 was finished by 306a14b and
928df52 (shared_scan, completed_native_evidence_many, _segments block scan all present and consistent). No repair
was needed; every later change is below.

## 1. Template map (Greg: the Sept-29 templates and the shared pin helper)
| Template item | Where it lands now |
| --- | --- |
| Speed 1: pieces side by side | `pre_read` (scientific_teacher.py:891): every day's completed native evidence reads and the claim-document part scan on ONE pinned pool; `main` (2049) reads the claim documents first so both start together |
| Speed 2: segment replay by pinned workers, ordered join | `_part_tasks` / `_part_ranges` / `_merge_part` (513 / 485 / 535): a part above 64 MB is cut at line starts into ordered ranges scanned by pinned workers, joined in file order with ordinals moved past earlier ranges |
| Speed 2: exact saves, resume where it left off | the document boundary: a result file already written is reused, never re-tested (`main`, `to_test`; receipt `shared_read.documents_resumed`); native evidence written once per day, reused only on equal bytes (`_native_document`, 1150); survivor update frozen `inputs.json` (survivor_update.py `update`, 588); school file reuse (`retained_school`) |
| Speed 3: deferred verify | NOT applied: every part is still hashed against its pin before its rows are used (Greg's open call (c) covers skipping a re-hash; not taken) |
| Speed 5: batch decode, every per-record check kept | `_segments` (444) 16 MB block reads, C-level needle search, only lines holding a claimed series parsed (928df52), now with byte ranges |
| decoded_spool (experiment_search.py:554) | copied shape: `_part_ranges` = `_spool_ranges`, the whole-file hash as its own task in file order (`_hash_part`, 503), ranges through `frankie_box_lane_pin.ordered_map` |
| lane_pin.lane_cpus / core_order | `_lane_order` (573) |
| lane_pin.ordered_map (ordered, bounded window, dead worker redone with one fewer, never hangs) | `_pinned_map` (616): window 2 x workers, `report=` deaths/redone onto POOL_NOTES |
| lane_pin.record | `_pinned_map` note `cpu_map`; school prefetch `PREFETCH.cpu_map` (school_knowledge.py:91-133) |
| lane_pin.executor('thread') | school pointer-file hash prefetch (school_knowledge.py `prefetch_pointer_digests`) |

## 2. Audit table (A-F), before -> after
| Item | Before (2f39ddc) | After |
| --- | --- | --- |
| A1 pools sized from the booked lane | DONE: `_lane_order` read FRANKIE_LANE_CPUS / BOOKED via boss_session; workers = lane - 1 | DONE via lane_pin.lane_cpus/core_order (573, 616) |
| A2 workers pinned, physical cores first | DONE (own initializer) | DONE via lane_pin placement (coordinator's sibling last) |
| A3 serial consumer on a whole core | N/A: the coordinator only joins results (light); not pinned, recorded in cpu_map | unchanged; named in section 6 |
| A4 ordered hand-off / in-order join with overlap | PARTIAL: pool.map (ordered, unbounded submit) | DONE: ordered_map, bounded window 2 x workers |
| A5 dead-worker redo, same args, same slot, one fewer | PARTIAL: BrokenProcessPool -> every item rerun serially in-process | DONE: lane_pin.ordered_map; toy kill test below |
| A6 one shared scan for every claim document | PARTIAL: shared_scan only for >= 2 documents; one-document children (the experiment's path) scanned alone, after the native reads | DONE in-process: pre_read for >= 1 document side by side with native reads. Cross-child: see F1 |
| A7 sub-steps side by side | MISSING: native evidence reads, then the scan, in series | DONE: pre_read (one pool) |
| A8 every stop bounded | PARTIAL: `with ProcessPoolExecutor` (bounded for dead workers) | DONE for our tasks: `_default_sigterm` resets SIGTERM to SIG_DFL in the worker before each task (the a2 hang shape). Residual: lane_pin.ordered_map's `finally: pool.terminate(); pool.join()` is unbounded if a worker that never ran a task inherited a SIGTERM handler (cross-owner request R1) |
| A9 OPENBLAS / thread env | MISSING | DONE: the three wrappers export OPENBLAS/OMP/MKL=1; pool tasks set them too |
| A10 byte-identical to serial, toy self-test | DONE for 928df52 | DONE: selftest below (whole and ranged parts, 1 and 3 documents, test() end to end, kill, raise) |
| B1 sizes from plan/booking | DONE | DONE |
| B2 FRANKIE_WORK_PROBE / heartbeat units, stall flag | MISSING in teacher and survivor (school had one final phase) | DONE: `_report_units` per pool item (report_phase every 15 s; the heartbeat derives units/min and the 600 s stall flag); survivor `_phase` 4 phases (578) |
| B3 run settings exported to children (FA-6) | N/A: Run.child passes os.environ whole | N/A |
| B4 DETACH exit semantics (FA-2) | N/A: these wrappers run as Run.child children, never DETACH units | N/A |
| C1 S3 > 64 MB ranged GETs / CRT | N/A: the only S3 traffic is presigned urllib GET of Jev's claims.json and PUT of a lessons file (small JSON), scientific_teacher.py `main` / `upload_jev_lessons`; every large read is local disk | N/A (named) |
| C2 large sequential reads in big chunks | DONE: 16 MB blocks (`SCAN_BLOCK`), school 64 MB | DONE |
| C3 skip re-hash on unchanged stat (Greg's call (c)) | not done | not done; sites: every part hash (`_scan_part_shared`, `_hash_part`), native ledgers (`_finalize_rows`), school pointer files (`_hash_file`), survivor brain reads (`select`) |
| D1 every fallback / cap / retry on the receipt | PARTIAL: placement and broken-pool fallback on stderr only | DONE: receipt `pools` (every pool: cpu_map, mode or in-process reason, worker_deaths, redone, seconds) on FRANKIE_SCIENTIFIC_TEACHER_RECEIPT_V1, FRANKIE_ACCUMULATED_LESSONS_V1 and both workflow_report.use; `shared_read.pre_read` (used, side_by_side, ranged_parts, scan_listed when a part scan raised); school receipt `prefetch`; survivor `phase_timings.frozen_documents_reread/_shared_with_select` |
| D2 missing-coverage rule, scope-ineligible never confirms | DONE (unchanged) | unchanged |
| E science unchanged | - | claims, rows, ordinals, raw-line hashes, counts, pins, lessons files, survivors.json, school file bytes unchanged; receipt fields additive only |
| F1 compute dedupe: parts read once per stage | PARTIAL | in-process DONE (pre_read / shared_scan). Remaining repeats named: (a) Run.lessons starts one teacher child PER claims name (experiment.py:4466-4482): each child re-hashes every part and every native ledger; (b) teach_accumulated calls ST.test once per document (teacher_knowledge.py:453) after its own completed_native_evidence (338); (c) jev_cpu.py:700-701 native then test in series. All cross-owner (R2-R4) |
| F2 pass dedupe | DONE: one pass per part serves every needle and document (928df52) | DONE; ranged parts read the file twice (hash task + ranges; page cache usually serves one) |
| F3 content dedupe (stacked_text / DIGEST_V10) | not applied | NOT applied: the lessons, survivors and school files are pinned evidence other owners hash and compare byte-for-byte (teacher_knowledge header compare, brain manifests, school index). A keys-once / DIGEST_V10 rendering is a new file format for those readers; it needs Greg's call and the readers' owners. Where it would apply: lessons `results[].tests[]` (repeated counts/chance_check keys per row), survivors `candidates[].tests[]`, school `sections[].items[]` (repeated author/path keys) |
| F4 survivor resume double read | MISSING: a frozen restart re-read every document by pin right after select() read and verified the same bytes | DONE: same path/bytes/sha256 (no correction) take select()'s verified parse (deep copy); others re-read by pin |

## 3. Changes, by function
scientific_teacher.py (diff from 2f39ddc: +483/-121 lines)
- `_lane_pin` (563), `_lane_order` (573): the shared helper's lane_cpus/core_order.
- `POOL_NOTES`, `_report_units`, `_default_sigterm`, `_pinned_map` (586-680): ordered_map with window, deaths, redo,
  cpu_map, heartbeat units; in-process path names its reason. Own pool code removed.
- `_segments` (444): optional start/end byte range, optional hash.
- `SCAN_RANGE_MIN_BYTES`, `_part_ranges`, `_hash_part`, `_part_tasks`, `_merge_part` (481-560): large parts as ordered ranges.
- `_scan_part_shared` (735): range form (no hash), whole form unchanged.
- `_shared_plan`, `_shared_specs`, `_shared_prepared`, `shared_scan` (807-877): split so pre_read can share them; a part
  scan error returns all None (each test() reads and raises at its own point, as before).
- `_pre_read_task`, `pre_read` (879-937): one pool for native reads + scan tasks.
- `completed_native_evidence_many` / `_native_tasks` (1118 / 1135): task building split out, behaviour unchanged.
- `main` (2049): claim documents read first (pure reads), errors deferred and re-raised after the native evidence
  lines exactly as before; pre_read; receipts gain `pools`, `shared_read.pre_read`, `documents_resumed`.
- `_write_teacher_receipt` (2299): `pools` added.
survivor_update.py: `_phase` (578); `update` frozen-path dedupe (about 610-626) and four heartbeat phases; `import copy`.
school_knowledge.py: `prefetch_pointer_digests` (91) through lane_pin.executor('thread') with the old pinned threads as
fallback; `PREFETCH` (133); receipt `prefetch` (606).
Wrappers (.sh x3): OPENBLAS/OMP/MKL_NUM_THREADS=1 exported.

## 4. Why bytes are unchanged
- Every row comes from the same bytes and the same line splitting (b'\n'); a range starts and ends at a line start,
  so its lines are the file's lines; ordinals = range-local + lines of earlier ranges; raw-line sha256 of the same bytes.
- The part digest is still sha256 of every byte in file order, checked against the pin in test() before any row is used.
- Results are collected in task order (ordered_map), so selection order is (day, part, line) as before.
- A task exception propagates at its own place in order; a broken shared read falls back to each document's own scan.
- Native documents are assembled in this process in the serial order from the same reads (`_native_document` unchanged).
- Receipt changes are added keys only; lessons / survivors / school files are untouched.

## 5. Tests run (toy, this container, FRANKIE_LANE_CPUS=0-7 on a 4-CPU container)
scratchpad/school/selftest_scan.py:
```
whole parts: shared_scan 3 docs identical=[True, True, True]; pre_read 1 doc identical=True; ranged_parts=0; pools=[('ordered_map', 4), ('ordered_map', 4)]
ranged large part: shared_scan 3 docs identical=[True, True, True]; pre_read 1 doc identical=True; ranged_parts=2; pools=[('ordered_map', 706), ('ordered_map', 706)]
test() results identical with the shared read: True sha 0e54d3cfdb88
dead worker: identical=True mode=ordered_map deaths=1 redone=1
raise test: KeyError propagated as serial: 'five'
ALL OK
```
Reference = the serial `_scan_part` per document (own read); parts of 5, 3000, 40000 and 1 rows (the last without a
final newline). Also: py_compile and ast.parse of the three edited .py, bash -n of the three wrappers, git diff --check.
NOT run: survivor_update and school_knowledge changes (frankie_box_brain / experiment_review stack not exercised);
pre_read with real native evidence files (the native branch was exercised only with no retained files).

## 6. Additional CPU spots (walked end to end; ranked by expected gain; shares are estimates, unmeasured)
1. Cross-child repeat of the whole scan (experiment.py:4466-4482 Run.lessons: one teacher child per claims name;
   each re-hashes every part and native ledger). Est. (N-1)/N of the lessons stage for N claim sources. Science allows
   one child with every document (the CLI already takes Jev + Frankie + historical + findings together; one Frankie
   ledger per call). Blocked: cross-owner (experiment.py), plus a repeatable --frankie-ledgers in my CLI. R2.
2. Accumulated teaching (teacher_knowledge.py:338, 453): native evidence then one ST.test per document, each a full
   part read. Est. most of the non-classroom lessons stage. Fix: build the measured docs, call ST.pre_read(days, docs,
   out_dir), pass scanned=. Built on my side (pre_read); blocked: cross-owner. R3.
3. Jev CPU teacher (jev_cpu.py:700-701): same pattern, R4.
4. test() result assembly after the scan (scientific_teacher.py test, the per-claim loop): serial Python per claim;
   est. 5-20% when claims select many rows. Science allows per-claim workers (independent per claim), but rows would be
   pickled to workers; unmeasured, not built.
5. all99_for_operation + write() per document (main loop): serial; est. small; independent of the next document's
   test, so a pipeline (write doc k while testing doc k+1) is possible; brain publication order must stay; not built.
6. Survivor select() (survivor_update.py:128): every brain document read + sha256 + json.loads serially; est. most of
   stage 10 on a long run (one-day run: tiny). Thread prefetch of reads/hashes in manifest order is safe; not built
   (REVIEW.current_document order and listing must stay; unmeasured).
7. Survivor coverage() per day (ST.load_searches + A99.day_coverage, survivor_update.py ~555): independent per day;
   pool-able; A99.retain writes files (order of writes only); not built.
8. REVIEW.corrections(roots) re-read per reused document inside the teacher loop (scientific_teacher.py main, reused
   branch) and in every stage: small directory; caching across a loop would change currentness semantics; left.
9. Successor drain (successor_dispatch.py:636 drain): serial over request files; requests are tiny and order-bound
   (checked successor chain); no gain expected.
10. Historical reproduction (historical_reproduction.py): never invoked (teacher's authorized execution only); N/A.
11. Idle sibling: the coordinator of every pool keeps lane CPU 0 and its sibling (16) gets the last worker; the
   coordinator only collects results, so its own core is mostly idle; school_knowledge's main thread builds while
   prefetch threads hash: build on the coordinator CPU, siblings used by the hashers.

## 7. Cross-owner requests
- R1 frankie_box_lane_pin.py: `_pool_initializer` / `_tracked_initializer` should reset SIGTERM to SIG_DFL (and
  ordered_map's `finally: pool.terminate(); pool.join()` bounded, e.g. kill + join(timeout)); same shape as the a2
  shard exit hang. My tasks reset it at task start, which does not cover a worker that never ran a task.
- R2 frankie_box_experiment.py Run.lessons (4466-4482): one teacher child per batch carrying every claims source
  (needs a repeatable --frankie-ledgers/--frankie-day pair in my CLI, which I can add on request), so the parts and
  native ledgers are hashed once per batch.
- R3 frankie_box_teacher_knowledge.py teach_accumulated (338, 453): call ST.pre_read(days, measured_docs, out_dir) and
  pass scanned= to each ST.test.
- R4 frankie_box_jev_cpu.py (700-701): same as R3.
- R5 Greg: content dedupe (F3) of lessons / survivors / school files needs a format decision and the readers' owners.

## 8. RUNTIME-UNVERIFIED
Everything above on the box: the lane_pin pool under the real booking, ranged scans on real parts, the survivor
frozen-path dedupe, the school prefetch through lane_pin.executor, heartbeat units. a2 sees it only after a restage
of the work-branch tip before its lessons / survivors / school stages.
