# Stacks pass 2026-10-07 night (session 5): end-of-day reports, inspection, finalization, progress readers

Owner: END-OF-DAY REPORTS / INSPECTION / FINALIZATION agent. Branch `ccr-d2f8f826-iefeah-frankie`, base `2f39ddc`.
Greg's go (session 5): every workflow step gets the optimizer stacks, CPU and workers for multiple steps in each piece,
and the AWS tool upgrades ROOT got. SOURCE-BUILT / RUNTIME-UNVERIFIED: py_compile, ast.parse, bash -n, git diff --check
and the toy self-tests below only. Nothing ran on the box. a2 gets none of this until a restage of the work-branch tip
(and see the finalization warning in section 5 before any restage that could resume a2's native checkpoint).

Files (owned): `deploy/aws/box/frankie_box_experiment_day_reports.py`, `frankie_box_workflow_inspection.py`,
`frankie_box_finalization.py`, `frankie_box_receipts.py`, `frankie_box_heartbeat.py`, `frankie_box_progress.py`,
`frankie_box_stage_progress.py` (edited); `frankie_box_experiment_day_reports.sh`, `frankie_box_progress.sh` (audited,
unchanged: bash -n clean). The parent's WIP snapshots e81c3a7..e40ed62 already carry these edits; the diff below is
against `2f39ddc`. The e0804ec inspection half-edit (search `workflow-report.json`) was complete and compiles; kept.

## 1. Audit table (before = 2f39ddc, after = this pass)

| Item | Before (file:line at 2f39ddc) | After |
|---|---|---|
| A1 pools sized from the booked lane | PARTIAL: receipts.py:70 fixed `min(16, jobs)`; finalization.py:45-51 fixed CPUs 0-15 whatever the booking (a lane 16-31 ROOT would pin onto lane 0); day_reports and inspection no pool | DONE: receipts `_pool` 76-90 (lane_pin.executor, lane-sized); finalization `_lane`/`placement` 61-95 (FRANKIE_LANE_CPUS / BOOKED_CPUS, physical-core order; 0-31 or 0-15 gives the old 0/1/2-15 exactly); day reports `render_side_by_side` 2363 on lane_pin.ordered_map |
| A2 pinned workers | finalization helpers pinned (fixed CPUs); others none | DONE: all pools go through lane_pin (receipts threads, report fork workers); finalization keeps its own per-thread pin with the lane CPUs |
| A3 ordered hand-off | receipts pool.map ordered | DONE: ordered_map yields in KINDS order (assert at the writer) |
| A4 dead worker redo with one fewer | N/A (no pools) | DONE for the reports: ordered_map redo, coordinator renders after 3 losses (toy kill test below). finalization: threads (no silent death; a read error raises, by design) |
| A5 inputs read and hashed once, shared | PARTIAL: Day reads once (day_reports `Day._read`); inspection read each step receipt twice (main glob + metadata) and each shared artifact once per piece | DONE in-process: inspection `read_object` 226-240 cache + ledger; heartbeat file read once for first/last line and CPU use (`_jsonl_lines`). Remaining repeats: section 4 F1 |
| A6 independent reports side by side | MISSING: classroom and Frankie reports rendered one after the other (day_reports 2391-2392 at base) | DONE: `render_side_by_side` |
| A7 every stop bounded | N/A in owned code except ordered_map's own `pool.terminate(); pool.join()` (lane_pin.py, not mine) | DONE for owned code: report workers reset SIGTERM to default and the handler `_os._exit`s any non-coordinator pid, so terminate cannot hang on the a2 pattern; cross-owner X1 for lane_pin |
| A8 byte-identical to serial, toy self-test | n/a | DONE: section 6 tests 1-3 |
| B1 FRANKIE_WORK_PROBE_V1 read for every piece | PARTIAL: stage_progress read probes only in caller-named dirs (OUTPUT_ROOT = ROOT) and beside open files; `work_probes` only when named dirs | DONE: `_process_dirs`/`_candidates` 269-314 (environment, argv, cwd of every tree process under /opt/frankie-box/work, plus subdirs); `work_probes` on every line |
| B2 units, units/min, per-probe rates, unchanged, STALLED, cpu_ranges | PARTIAL: per-probe rate only; no per-probe stall; no cpu_ranges; final line units None after exit | DONE: `probe_item` 88-105 (any writer's fields, cpu_ranges from the probe or the writer's Cpus_allowed_list), per-probe `units_unchanged_s`/`stalled` in `_named_probes` 316-346, line `cpu_ranges`, last measured units carried labelled (sample 364-483) |
| B3 probes outside stage children | MISSING: the Run's own progress.json and the queue line workers were never in the run-dir reader | DONE: `run_probes` 569-585, `_probe_file` 537-566; printed by progress.py |
| B4 heartbeat line format backward compatible | n/a | DONE: every earlier key and printed field kept; new keys and trailing ` units_from=... cpus=...` appended; old lines summarise (test 4) |
| B5 run_settings (FA-6) shown | MISSING in readers | DONE: kick receipt `run_settings` on the run-probe lines (progress.py) and in the inspection preflight piece (`lane_records`, "Line kick receipt") |
| B6 DETACH exit (FA-2) in wrappers | N/A: my wrappers are not DETACH wrappers (day_reports.sh runs as a stage child; progress.sh is read-only) | N/A |
| B7 CPU use per piece | MISSING | DONE: heartbeat `cpu_seconds`/`cpus_busy` (lower bound from /proc utime+stime); inspection `cpu_use`/`cpu_use_row` per piece (booked CPUs, CPU-equivalents busy, idle stretches by phase, every lane_pin.record / cpu_placement / pool_recovery map) |
| C1 S3 read > 64 MB ranged / CRT | N/A: no owned file reads S3 objects | N/A |
| C2 report/receipt uploads CRT-first | N/A: owned files upload nothing except heartbeat.py's ~1 KB ROOT_PROGRESS beats (put_object, IfNoneMatch) | N/A (a CRT client for 1 KB objects buys nothing) |
| C3 no stat-skip of re-hash | receipts `_witness` uses frankie_box_filehash.witness (in-process stat-keyed cache, predates call (c)) | Unchanged, noted (section 4) |
| D1 visibility fields rendered for every piece | PARTIAL: FIELDS whitelist projected top-level keys; nested skips/fallbacks/caps/retries inside other objects were named only as "other fields retained at source" | DONE: `visibility_rows`/`visibility_block` (every key, any depth, matching skip/wait/refusal/fallback/cap/retry/missing/stale/absent/swallowed/default/error/problem/listed/not_run/deferred/withheld/excluded/worker death/redo/recovery/lost/timeout/stop/limit/transport/dedupe/stall/unavailable; empties counted) on every metadata object; FIELDS + run_settings, transport*, hash_pass, stalls, bytes_to_fetch/fetched, fetch_pin, rehash_rule, report_rendering ... |
| D2 X3 ingest projections | MISSING | DONE: ingest piece reads the fetch receipts named on the fetch log's `RECEIPT` lines (`fetch_receipts` 853), the fetch probe beside the partitions (`fetch_probe_dirs` 874), the ingest `progress.json` beside the journal (artifact_paths 912) |
| E science unchanged | n/a | DONE: report text, numbering, index rows, receipt keys unchanged; additive receipt key `report_rendering`; finalization verification semantics unchanged |
| F1 compute dedupe | see A5 | DONE in-process; remaining repeats listed in section 4 |
| F2 pass dedupe | inspection: two reads per step receipt | DONE: one read; the reports already make one pass |
| F3 content dedupe | n/a | NOT APPLIED, Greg's call needed: the numbered reports' bytes are pinned by E (numbering, index sha256, Jev #N); the inspection markdowns are human-read (kept readable). Nothing here is read by a model, so no stacked_text / DIGEST_V10 grammar was applied |
| F4 dedupe row per piece | MISSING | DONE as a generic projection: any `dedupe`/`read_once`/`repeated` field a piece records is in its visibility table; index.md carries this reporter's own read ledger |

Per sub-step (end-of-day stage):

| Sub-step | Function (file:line) | Status |
|---|---|---|
| inputs read once | day_reports `Day.__init__` / `Day._read` 365-455 | DONE (unchanged, already once) |
| 99-layer join | `collect_all99` / `all99_join` | unchanged (serial; section 3 rank 3) |
| classroom report | `classroom_report` via `_render_one` 2343 | side by side + save point |
| Frankie report | `frankie_report` via `_render_one` | side by side + save point |
| index / receipt | `_run` 2486-2680 | seal check vs save claims 2618; additive `report_rendering` 2651 |
| school consolidation | frankie_box_school_knowledge.py (NOT mine) | cross-owner, section 3 |
| inspection markdowns | workflow_inspection `main` | read cache, visibility, CPU map, heartbeats, CPU use, save/restore rows |
| finalization identity | finalization 27-58 | DONE (function-level) |
| uploads | none in owned files | N/A |

## 2. Probe coverage (piece -> progress.json path -> reader finds it)

The stage heartbeat now finds a live FRANKIE_WORK_PROBE_V1 in: caller-named dirs; every directory named by the tree's
environment, command line or cwd under /opt/frankie-box/work (and their immediate subdirectories); open-file dirs.

| Piece (writer) | progress.json | Found by heartbeat | Found by progress.py --run-dir |
|---|---|---|---|
| ROOT legacy (boss_session for_session) | experiment-roots/<attempt>/progress.json | yes (OUTPUT_ROOT, also env) | yes, as a work probe |
| ROOT native (boss_session 1768) | experiment-roots/<attempt>/native-overlap/progress.json | yes (subdir) | yes |
| classroom publication (boss_session 3633) | the session dir | yes (CLASSROOM env names <root>/work/classroom; its root via ROOT dir or open files) | yes |
| ingest (ingest_block_sources `_emitter`) | beside the journal (ingest dir) | yes (open files; env/argv OUTPUT dirs) | yes; inspection reads it too |
| block fetch (ingest_block.sh T.WorkProbe) | beside the partitions | yes (open files) | yes; inspection reads it via the fetch receipt |
| Run itself (experiment.py:1109) | <run>/progress.json | not a stage child | yes, `run_probes` |
| queue line workers (frankie_queue 933/1869) | frankie-queue/<line>-worker/progress.json | not a stage child | yes, with the kick run_settings |
| joined teacher (joined_teacher 89) | its out dir | yes if the dir is named by env/argv/open files | yes |
| teacher, data, search, school, exchange, Jev, meeting, reports, lessons, survivors (other agents adding writers now) | wherever their process names a directory under /opt/frankie-box/work, or beside an open file | yes, generic (any writer; missing fields None) | yes |
| these stages' report_phase phase files | <run>/days/<day>/progress/<stage>.phase.json | yes (first source of units) | yes |

A writer whose directory is named by nothing (not env, argv, cwd, an open file, nor a caller dir) is not found: the
line then says `units_from=` the phase file or the log line. Item for owners: put the probe in the stage's output dir.

## 3. Additional CPU spots (end-of-day stage, ranked by expected gain)

Shares are estimates (nothing measured on the box; the reports step's own `timings_seconds` will show them on day 1).

| Rank | Stretch (file:line) | What | Est. share | Parallel / overlap, byte-identical? | Status |
|---|---|---|---|---|---|
| 1 | inspection `main` per-piece loop (workflow_inspection ~985-1060) | 16 pieces rendered one after another; json.dumps(indent=2) of up to 8 MB objects dominates | most of the inspection wall | Yes: pre-read every artifact once in the coordinator (thread pool, read cache), then render pieces on lane_pin.ordered_map fork workers, coordinator prints/writes in PIECES order: stdout and files identical | NOT BUILT (time); safe and local, next |
| 2 | day reports two renders | classroom and Frankie reports | ~50% of build_and_write | Yes | BUILT (`render_side_by_side`) |
| 3 | `collect_all99` (day_reports 1245-1496) reading 11 pieces' receipts and pinned lists serially | small JSON reads + sha256 | unknown, I/O small | Yes on threads (reads only, witnesses appended in fixed order); must keep `d.inputs` order | NOT BUILT: needs `d.inputs` order kept by an ordered map; safe, next |
| 4 | `Day.__init__` JSON_FILES loop (day_reports ~420-432) | ~15 small classroom JSON files | small | overlap with rank 3 (same thread pool, ordered witnesses) | NOT BUILT |
| 5 | receipt write `json.dumps(receipt, indent=1)` of the full all99 join (day_reports ~2660) | one large dump | small-medium | overlap with the index write | not built (low) |
| 6 | Run.child re-reads both reports and logs them again (experiment.py:2373-2377) | duplicate read + duplicate log content | small | drop (the child's log already holds them) | cross-owner X4 |
| 7 | school consolidation (frankie_box_school_knowledge.py) | not mine | unknown | owner | cross-owner |
| 8 | finalization `scan` | 14 helpers on 14 cores; I/O-bound at 1250 MiB/s | ROOT tail | already parallel; HELPERS could take the lane's other cores on a 32-CPU lane, gain bounded by EBS | not changed (bounded by EBS) |
| 9 | heartbeat.py S3 beat | 1 KB put per 300 s | none | n/a | n/a |

## 4. Every change (functions and line ranges, current files)

- `frankie_box_stage_progress.py`: docstring stacks-pass note 29-40; `CLOCK_TICKS`, `WORK_ROOT`, `MAX_PROBE_DIRS`,
  `QUEUE_DIR`, `cpu_list_of` 70-75, `_ranges` 78-85, `probe_item` 88-105; `Heartbeat.__init__` adds `peak_cpu`,
  `probe_moved`, `seen_processes`; new `_process_dirs` 269-300, `_candidates` 302-314; `_named_probes` 316-346 rewritten
  over `_candidates` with per-probe stall and cpu_ranges; `_units_from_probe` 348-362 over `_candidates`; `sample`
  364-483: per-process utime+stime -> `cpu_seconds`, `cpus_busy`; `work_probes` on every line; `cpu_ranges`; last
  measured units carried with a labelled source; `stages_summary` 504-534 adds `units_source`, `cpu_ranges`,
  `cpu_seconds`, `cpus_busy`, `work_probes_error`, `sample_error`, `run_probes`; new `_probe_file` 537-566,
  `run_probes` 569-585.
- `frankie_box_progress.py`: `_ranges` 20-27; `Probe.update` writes optional `cpus`/`cpu_ranges`/`workers` when a
  writer sets them (additive; no existing writer sets them); `__main__` printing appends ` units_from= cpus=` to each
  stage line, ` unchanged= STALLED cpus=` to each work-probe line, and prints one `probe` line per run probe with its
  kick receipt; the JSON summary stays the last line.
- `frankie_box_heartbeat.py`: `sub_probes` 34-44; each beat gains `work_probes` (snapshot of every immediate
  subdirectory holding a progress.json, e.g. native-overlap/). `work` and `note` unchanged.
- `frankie_box_receipts.py`: `provider_invocations` uses `_pool` 76-90 (lane-sized, pinned, unpinned fallback).
- `frankie_box_finalization.py`: `HELPERS`, `NATIVE_VALUE_CODE`, `WHOLE_FILE_PREDECESSORS` 22-37,
  `native_code_identity` 40-44, `accepts_whole_file` 47-58, `_lane` 61-76, `placement` 79-95; `scan` 110-179 takes
  its reserved/coordinator/helper CPUs from `placement()` (the 16-distinct-core refusal is removed: placement only),
  barrier/pool width = helpers, policy gains `placement_basis`. `file_identity`, `_block`, `restore_closed`,
  `reconcile_all`, `execution_receipt` are byte-unchanged (their code identity equals the 15164b45 file's).
- `frankie_box_experiment_day_reports.py`: section note + `SAVE_SCHEMA` 2328-2340, `_render_one` 2343, `_render_job`
  2351 (SIGTERM default in the worker), `render_side_by_side` 2363-2411, save route `SAVED_EXIT`/`_SAVE`/`_mark_save`/
  `save_requested`/`_code_sha256` 2414-2433, `_save_path`/`_save_identity`/`load_save`/`write_save` 2435-2466, `run`
  2469-2483 (installs the mark-only handler for the step, restores it), `_run` 2486 (the old body): resume from the
  save point, side-by-side render, save point after each report, report_phase per report, exit 75 at a report boundary
  on a requested save, seal check vs the save claims, additive receipt key `report_rendering`.
- `frankie_box_workflow_inspection.py`: docstring note; `import re`; FIELDS additions; `_READ_CACHE`/`_READ_LEDGER`,
  `VISIBILITY`, `SAVE_RESTORE`, `PLACEMENT_SCHEMA`, `CPU_KEYS` 188-208; `read_object` 226 (cached) / `_read_object_once`
  242; `metadata` adds cpu map, visibility, save/restore blocks; `_short`, `_walk`, `visibility_rows`,
  `visibility_block`, `save_restore_block` 345, `cpu_map_rows`, `cpu_map_block`, `_jsonl_ends`, `_count_cpus`,
  `_jsonl_lines`, `cpu_use`, `heartbeat_block`, `_compact_cpus`, `cpu_use_row`; `lane_records` reads both kick
  receipts; `_log_path`, `fetch_receipts` 853, `fetch_probe_dirs` 874; `artifact_paths` ingest branch 912; `main`
  resets the per-piece CPU maps, renders heartbeats + CPU use for every piece, index.md read ledger.

Why bytes are unchanged: the reports are the same pure functions of the same `Day` (built once, before the fork); the
coordinator encodes and writes them in KINDS order; resumed reports are the very bytes written before, hash-checked.
The index rows and receipt keys are those of the serial path (one key added). Finalization changes CPU placement only:
the digest is sha256 of the file bytes in order either way, and on the box's 0-31/0-15 lanes the placement is the old
one exactly. Readers only add fields and trailing print text.

Remaining repeated reads (F1, named): day_reports `late_pieces_changed` (~2700+) re-reads pieces to detect late changes
(a separate invocation, by design); `previous = sha256_file(receipt_path)` reads the previous receipt for its sha
(needed); the reuse path re-reads each existing report to check its sha (verification, needed); experiment.py:2373-2377
re-reads the written reports to log them (X4); receipts `_witness` -> frankie_box_filehash.witness skips a re-hash by
stat within one process (Greg's open call (c): left as is, noted).

## 5. Finalization function-level identity and the a2 warning

`frankie_box_native_checkpoint.runtime_identity` (NOT mine, line 40/48) still binds `finalization_sha256` = the WHOLE
file's sha256. This pass changed finalization.py's bytes, so a native checkpoint saved under c9bf631 (a2's ROOT) would
be REFUSED by `runtime_acceptance` on a resume from a checkout carrying this file, until X2 lands. a2's ROOT is
expected to finish native before the restage; if a2 must resume its native pass from a checkpoint after a restage,
either land X2 first or restage without this finalization change. The new file provides everything X2 needs:
`native_code_identity()` (sha 3ee8150e...) and `accepts_whole_file(saved_sha256)` which accepts the old whole-file sha
15164b45... ('whole_file_15164b45_code_unchanged') while NATIVE_VALUE_CODE is unchanged, and the current whole file.

## 6. Tests run (scratchpad/reports/, exact output)

1. `t_reports.py` (real `run()` on a refused toy day, the shared registry imported): serial
   (FRANKIE_REPORTS_SIDE_BY_SIDE=off) vs side by side on a 4-CPU lane: classroom 41c05cd2..., frankie 4e2c4054...
   both modes; `IDENTICAL report bytes: True`, `receipt core equal: True`; resume after deleting the second report:
   `resumed: ['classroom']`, `IDENTICAL after resume: True`.
2. `t_dead.py`: the Frankie report's worker `os._exit(9)` on its first try: same two sha256s; pool_recovery
   `worker_deaths [{pids [..], in_flight_after 1}]`, `redone [{job 'frankie', try_number 2}]`.
3. `t_save.py` (save -> resume -> compare, both render modes): stop file present -> `('exit', 75)` + `SAVED ...`
   line, one report written, index rows 0; resume -> `resumed_from_save ['classroom']`, problems [], `bytes equal
   from-scratch: True`, `index rows equal: True`; a save under another code_sha256 -> not reused, both rendered,
   bytes equal. `t_sig.py`: SIGTERM marks the coordinator (still running, save_requested True); a forked child ends
   on SIGTERM in 0.00 s with 143.
4. `t_probe.py` (real Heartbeat on a child writing two probes via frankie_box_progress.Probe in a directory named only
   by its OUT_DIR env, WORK_ROOT pointed at scratch): units 290/300 from the work probe; both probe dirs found
   (`.../20231018`, `.../native-overlap`); cpu_ranges `0-3`; per-probe rate and unchanged; line cpu_seconds 2.95,
   cpus_busy 1.0; run probes read (Run, root line worker with kick run_settings, class worker absent); a line in the
   old format (no new fields) still summarises; `progress.py --run-dir` prints the final line with
   `units=290/300 ... units_from=the last measured units (work probe ...)`.
5. `t_insp.py` (real reporter `--write` on a toy run): visibility, CPU map, stage heartbeats, CPU use with an idle
   stretch (`phase hash, cpus_busy_max 3.0` of 32 booked), fallbacks/retries/worker_deaths rendered; read ledger
   `files read 18; requests 24; served from an earlier read 6`; kick receipt section; X3: fetch receipt,
   transport_fallback, hash_pass and the fetch probe in ingest.md; save/restore row in school.md.
6. `t_final.py` (finalization imported with stubs: prepare_trading_day.safe_path, segmented_ledger._read_at by pread,
   bedrock.code_identity extracted verbatim): identity 3ee8150e...; accepts old 15164b45 ->
   `whole_file_15164b45_code_unchanged`, current -> `whole_file_unchanged`, other -> None; placement: no env -> 0/1/2-15,
   0-31 -> 0/1/2-15, 0-15 -> 0/1/2-15, 16-31 -> 16/17/18-31, 0-3 -> 0/1/2-3; `scan` of a 300,000-row file: sha256
   equal, rows 300000.
7. py_compile + ast.parse of all seven .py, bash -n of both .sh, git diff --check: clean.

RUNTIME-UNVERIFIED: everything on the box: /proc environ reads as root on real stage trees, the CPU-use numbers,
lane_pin topology order on the 8488C, the reports pool under the cores wrapper, the finalization placement inside the
native child, the inspection on real (multi-MB) receipts.

## 7. Save/restore vs ROOT (Greg's directive items 1-7, the end-of-day reports step)

| Item | Status | Where |
|---|---|---|
| 1 save request route | DONE: SIGTERM or FRANKIE_LANE_STOP_FILE marks; runs to the next report boundary (its save point already durable), exits 75; forked workers reset SIGTERM and the handler exits any non-coordinator pid. A request after the last report completes the step. The Run's handling of exit 75 is cross-owner X5 | day_reports 2414-2433, 2469-2483, 2580-2593 |
| 2 periodic exact saves | DONE: a save point after every report (the reports' boundary; the unit is one report) | `write_save` 2460, call in `_run` |
| 3 file positions without re-read | N/A: the step reads whole small JSON files once; no spool or appended file. A resumed report is re-read once and hash-checked (seal) | |
| 4 identity is content | DONE by construction: the save identity is sha256 values (classroom receipt, exchange, meeting, school, all99 join, code), numbers and revisions; no checkout path is in it, so content_rebinds has nothing to rebind (N/A) | `_save_identity` 2439 |
| 5 function-level code identities | PARTIAL by choice: the save binds the whole day_reports.py sha (`_code_sha256`); a mismatch re-renders (never a mixed-version day), costs milliseconds; finalization's identity is function-level (section 5) | 2428, finalization 27-58 |
| 6 additive; old saves load; probe continues | DONE: no earlier save shape exists (new file); receipt key additive; report_phase per report counts resumed reports as done | `_run` report_phase call |
| 7 seal check | DONE: each index row the step writes is compared with the save point's claim; a difference is a visible problem (exit 1) | `_run` 2618 |

The inspection reporter renders a per-piece save/restore row (`save_restore_block`) from every receipt: last save
point, resume source, rebinds, checkpoints, cursors, seal, exit codes, full passes forced (fields named
save/resume/rebind/checkpoint/full_pass/restore/cursor/seal). Stage heartbeat continuity after a resume: the units come
from the piece's own probe or phase file, which continue from the cursor when the piece's writer starts there
(`Probe.track(done=...)` already does); the heartbeat itself is per child attempt.

## 8. Sept-29 template map

| Template item | Function here |
|---|---|
| 1 pieces side by side | `render_side_by_side` (reports); inspection pieces side by side = section 3 rank 1 (not built) |
| 2 exact saves at boundaries, resume where it left off | `write_save` / `load_save` / exit 75 (reports) |
| 3 deferred verify | the seal check compares claims without a re-read; finalization `scan` unchanged (it IS the verify) |
| 4/5 batch decode with every per-record check | N/A (no decode in these files) |
| lane_pin lane_cpus / core_order / placement | finalization `placement`, receipts `_pool`, reports via ordered_map |
| lane_pin ordered_map / executor | reports (ordered_map), receipts (executor) |
| lane_pin record | reports `report_rendering.cpu_placement`; inspection renders every record() map (`cpu_map_block`, `cpu_use_row`) |

## 9. Cross-owner requests

- X1 `frankie_box_lane_pin.py` `ordered_map` finally (`pool.terminate(); pool.join()`): unbounded join after terminate;
  a worker that inherited a mark-only SIGTERM handler hangs it (the a2 shard pattern). Make the join bounded
  (join with a deadline, then SIGKILL the remaining worker pids) or reset SIGTERM in `_tracked_initializer`.
- X2 `frankie_box_native_checkpoint.py` 33-73: bind `finalization_code=finalization.native_code_identity()['sha256']`
  instead of `finalization_sha256` (V3 runtime), and in `runtime_acceptance` accept a saved runtime that carries
  `finalization_sha256` when `finalization.accepts_whole_file(saved['finalization_sha256'])` and every other field
  equals the current runtime (for the V2 and V1 forms). Until then any finalization.py edit refuses older checkpoints.
- X4 `frankie_box_experiment.py` 2373-2377: the Run re-reads both reports to log them; the child's log already holds
  them (drop or log the sha256 only).
- X5 `frankie_box_experiment.py` 2371-2410: treat the reports child's exit 75 as `saved` (booking retained, re-run
  resumes from the save point), not `failed`; pass FRANKIE_LANE_STOP_FILE (already passed by Run.child 1299-1301).
- X6 every stage owner whose probe sits in a directory no env/argv/cwd/open file names: write it under the stage's
  output directory (or name it in the child env) so the generic reader finds it.
- F3 content dedupe of the numbered reports (Greg): would change report bytes (E); needs his call.

## 10. Open (not done in this pass)

- Inspection pieces rendered side by side with a pre-read (section 3 rank 1); `collect_all99` / JSON_FILES reads on an
  ordered thread map (ranks 3-4).
- Greg's call (c) on stat-skip re-hash (receipts `_witness`).

## 11. Addendum: X2 landed (granted narrowly) and the inspection pieces side by side

### X2: `frankie_box_native_checkpoint.py` binds finalization by its function-level identity

Granted by the parent for this one change. Nothing else in that file was touched.
- `runtime_identity` 31-45: new saves record BOTH `finalization_sha256` (whole bytes, the earlier meaning) and
  `finalization_code` (`frankie_box_finalization.native_code_identity()`).
- New `_finalization_normalized` 47-71. A saved finalization is accepted when:
  - the save carries `finalization_code` and it equals the current code identity (the whole bytes may differ); or
  - the save carries no `finalization_code` (every save before this pass, V2 and V1 forms) and
    `finalization.accepts_whole_file(saved['finalization_sha256'])` holds (the same bytes, or 15164b45 with
    NATIVE_VALUE_CODE unchanged).
  An accepted save has its finalization fields replaced by the current ones. The EXISTING rules then compare every
  other field unchanged: code, persistent-id serializer 65006dc9, whole_file_unchanged and the named predecessors.
- `runtime_acceptance` 88-91 does this once. The label is recorded with the resume, for example
  `serializer_persistent_id_65006dc9; finalization whole_file_15164b45_code_unchanged`.
- `runtime_identity`, `runtime_acceptance` and the new helper are outside that file's NATIVE_VALUE_CODE. Its
  serializer_code is unchanged: code_identity is f445ba3f... both at 2f39ddc and now.
- V1 whole-file saves already bound native_checkpoint.py's whole bytes, so any edit there affected them. The
  current tip writes V2 only.

Toy `t_ckpt.py` ran the real module, stubbed only for imports: prepare_trading_day (witness, safe_path),
segmented_ledger (a constant code id, `__file__`), bedrock.code_identity (extracted verbatim), and an empty
periodic_checkpointer base class. Exact output:
```
new runtime keys: ['cloudpickle', 'finalization_code', 'finalization_sha256', 'ledger_storage_code', 'python', 'schema', 'serializer_code']
a2-shape (persistent id, old finalization whole sha): serializer_persistent_id_65006dc9; finalization whole_file_15164b45_code_unchanged
V2 current serializer, old finalization sha: code; finalization whole_file_15164b45_code_unchanged
new-shape save (current): code
new-shape save, other finalization whole bytes, same code: code; finalization finalization_code
new-shape save, changed finalization code: None
old-shape save, unknown finalization whole sha: None
old-shape save, changed python: None
changed finalization function, a2-shape save: None
changed finalization function, new-shape save recorded before the change: None
```
The "changed finalization function" cases point the module at a copy of frankie_box_finalization.py whose
`restore_closed` differs by one character.

Result: the restage blocker in section 5 is resolved in source. a2's native checkpoints (000005 and later,
runtime = V2 with persistent-id serializer and finalization 15164b45) restore on a tip carrying both files.
This is RUNTIME-UNVERIFIED on the box: the real bedrock/segmented_ledger imports, the real a2 descriptor.

### Inspection pieces side by side (section 3 rank 1, now BUILT)

`frankie_box_workflow_inspection.py`:
- `render_piece`: main's per-piece loop body, moved verbatim, with locals taken from ctx.
- `_PRINT`: emit prints unless held inside a worker.
- `_piece_job`: the worker; returns the piece's lines and its read-ledger delta.
- `_prefetch`: the coordinator reads every artifact the step receipts name ONCE, on a lane-sized thread pool, into
  the read cache, before the fork (it counts no ledger request).
- `render_pieces`: `lane_pin.ordered_map` over PIECES on pinned fork workers. Ordered hand-off; a dead worker's piece
  is redone. The coordinator prints and writes the pieces in PIECES order. If the pool fails, the remaining pieces
  render in-process (listed).
- `main` uses `render_pieces`. index.md gains a "Rendering" block: mode, reason, prefetched count, cpu_placement
  (lane_pin.record), pool_recovery.
- `FRANKIE_INSPECTION_SIDE_BY_SIDE=off` gives the earlier in-process path.

Toys:
- `t_insp_par.py`: off vs on gives the same stdout sha256 (cdbac44e...), all 16 piece files identical, and an
  identical read ledger (18 files, 24 requests, 6 served from an earlier read).
- `t_insp_dead.py`: the school piece's worker `os._exit(9)` on its first try. Same stdout sha256, school.md
  144a5197... equal to the serial run, and index.md lists `worker_deaths` and `redone` for the school job.
- `t_insp.py`: all earlier assertions still hold.
- py_compile and git diff --check: clean.

Still open from section 3: ranks 3-4 (`collect_all99` and JSON_FILES reads on an ordered thread map).
