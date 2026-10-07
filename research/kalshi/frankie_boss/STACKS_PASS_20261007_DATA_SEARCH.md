# Stacks pass 2026-10-07 night (session 5): data export (stage 6) and causal series/search (stage 7)

Greg's go (session 5): every workflow step gets the optimizer stacks, CPU and workers for multiple steps in each piece,
and the AWS tool upgrades ROOT got. Owner: the data/search stage agent. Branch ccr-d2f8f826-iefeah-frankie (base
2f39ddc; the parent's WIP snapshots 92a0889..ecbc7ed already carry part of these edits; the diff below is against
2f39ddc). SOURCE-BUILT / RUNTIME-UNVERIFIED: py_compile, ast.parse, bash -n, git diff --check and a toy self-test
(16/16) only; nothing ran on the box, no AWS call, no install.

**a2 gets this only by a restage of the work-branch tip before its data export starts** (after ROOT, teacher and
classroom). Never stage an intermediate WIP snapshot.

## 0. Two findings to read first (not fixed here; they decide whether stage 7 can finish on 20231018)

1. **The search holds the whole frames spool in memory (likely out of memory on 20231018).**
   `build_series` (search.py:835) calls `spool_columns`, which materializes every scalar leaf of
   root/work/derived/.rows/frames.jsonl as Python lists (`columns()`, search.py:285). a2's frames spool was
   256.6 GB at 314,117 rows (about 817 KB of JSON per F_LAST row: full-depth books, FIFO observations and every group
   INPUT record), about 430 GB projected for the day. As Python objects that is several times the box's ~240 GB RAM.
   The decode is now bounded and parallel, but the result does not fit. A fix is a design change (out-of-core
   columns, e.g. one memmap/array file per channel written by the range workers, or a streaming per-channel pass):
   values and order can stay identical, but it is beyond a stacks pass and touches what the series are built from.
   Owner decision; it should be made before a2's search starts.
2. **Greg's open call (b), ID context fields as search cells: they ARE cells today.** `non_market_reason`
   (search.py:150-178) returns 'context_only' for SEARCH_CONTEXT_IDENTITIES (search.py:143: order_id, order_ids,
   fill/unresolved/matched_order_ids, instrument_id, publisher_id, channel_id, member_id, session_id, source_day,
   source_role, raw_symbol, symbol, contract, trading_weekday) and calendar names; build_series moves them from series
   into text cells (search.py:1286-1310), and search() makes one cell per distinct value (cell_index,
   search.py:2430-2442) and one coupling job per (cell, transform, series) (jobs, search.py:2445). Feasibility cost:
   jobs = sum over cells x |transforms| x |series|; an ID-valued column has about one label per group, so on a full day
   (~10^5-10^6 groups) one such column alone gives ~10^5-10^6 cells x 5 transforms x every series, each job writing a
   recovery state pickle (`_cell_job`, search.py:1877) even when it has fewer than 2 steps (the `short` record). That
   is billions of jobs and files: infeasible on one day. Not decided here (Greg's call); behavior unchanged.

## 1. Audit table (A-F), before -> after

| Item | Before (2f39ddc) | After (this pass) |
|---|---|---|
| A1 pools sized from the booking | DONE in code (lane_pin.lane_cpus/placement; orchestrator passes WORKERS/DATA_WORKERS = day_cpus-1, experiment.py:4285/4330); wrappers defaulted to literals 1 (data.sh) and 8 (search.sh) | DONE: both wrappers size the default from FRANKIE_LANE_CPUS / FRANKIE_BOOKED_CPUS (else nproc) minus 1 (data.sh, search.sh `lane_size`) |
| A2 workers pinned, serial consumer on a whole core | PARTIAL: every pool pinned (ordered_map); search coordinator pinned only after build_series (search.py:1523 pin_coordinator) and its sibling is a worker CPU (lane_pin.placement puts the coordinator's sibling LAST, not out); during build_series the coordinator floats on the lane | PARTIAL, unchanged: listed as spot S5 (taking the sibling out costs one worker; same trade as ROOT's) |
| A3 ordered hand-off / in-order join with overlap | DONE (ordered_map yields in job order; spool parts joined in file order) | DONE; spool_columns now has a bounded in-flight window (2 per worker) instead of every range at once |
| A4 dead worker redone, one fewer | DONE (lane_pin.ordered_map in every pool: spool ranges, INPUT ranges, gates, transforms, cells, nominations, discovery; data hashing) | DONE, unchanged |
| A5 every spool/part read and hashed once | PARTIAL: spool decode + an unthrottled hasher thread = two disk passes on a spool bigger than the page cache; coupling parts read 3 times (written+hashed by the job, read by discovery, re-read+hashed at publish) | DONE inside the stage: FrontierHasher (one disk pass shared via the page cache) for frames/structures/prices, INPUT and native ledgers; parts pinned from the job's write-time digest, discovery's read hashes the same bytes and must agree. Across stages export->search the spools are hashed again (the search verifies the export pin): kept, see C/(c) |
| A6 sub-steps pipelined / side by side | PARTIAL: hashing threads beside decode; gates side by side; sources in build_series run one after another | PARTIAL: see "Additional CPU spots" S1/S2 (not built, ranked) |
| A7 every stop bounded | PARTIAL: hasher in spool_columns had no stop (an error waited for the rest of the file, up to ~430 GB); decoded_spool/native had a stop event but an unbounded join; lane_pin.ordered_map's finally does terminate()+unbounded join (the a2 shard hang shape if a worker ever catches SIGTERM) | DONE in my files: FrontierHasher.stop() wakes and joins with a timeout; SIGTERM disposition inherited by workers recorded on the MANIFEST (cpu_placement.sigterm_inherited_by_workers; default today: no handler is installed in data/search/native/journal or their imports, grepped). ordered_map's join is the lane_pin owner's (request R1) |
| A8 OPENBLAS/thread env fixed | DONE for search (pin_coordinator -> dipole_classroom_external.blas_reduction, N=32 decision; discovery PYTHON_JULIACALL_THREADS=1); data export does no BLAS | DONE, unchanged (documented in search.sh) |
| A9 byte-identical to serial, toy self-test | PARTIAL (session-4 claims) | DONE for every changed path: 16/16 (section 4) |
| B1 sizes from plan/booking | see A1 | DONE |
| B2 FRANKIE_WORK_PROBE_V1 / phase heartbeat with units | PARTIAL: search reported phases, coupling cells and discovery problems; the long decode reported nothing; data export reported nothing; probe failures swallowed (`except: pass`) | DONE: units for every spool/INPUT range decode (byte ranges, bytes_done/bytes_total, rows), transform steps, coupling cells, discovery, and the export's hashing (files, bytes); a failed probe write is counted (PROBE_FAILURES on MANIFEST cpu_placement / hashing). units/min, per-probe rates and the 600 s stall flag are the reader's (frankie_box_stage_progress.Heartbeat, STALL_SECONDS 600) |
| B3 run settings exported to children (FA-6) | DONE by inheritance: Run.child passes os.environ + env to the wrapper, the wrapper execs python, pools fork | DONE, unchanged |
| B4 DETACH exit semantics (FA-2) | N/A: these wrappers are Run.child stages under frankie_box_cores.py, never a DETACH unit | N/A |
| C1 S3 ranged/CRT reads, CRT uploads | N/A: neither piece reads or writes S3 (export = hard links on the work volume, search = local reads); the shared helper is frankie_box_s3_transport.py (another owner, 92a0889) for any later upload of exports | N/A (no S3 I/O in these files) |
| C2 large sequential reads in big chunks | DONE (64 MB hashing reads, 16 MB hasher blocks, unbuffered) | DONE (FrontierHasher reads 16 MB blocks with buffering=0) |
| C3 skip re-hash by stat (Greg's call (c)) | not done | NOT applied: the export's new save point records every pin; reuse is wired behind FRANKIE_EXPORT_REUSE_PINS=on (default off). Sites where (c) would apply: data `_pin_all` (export of the 430 GB frames + 24 GB journal), the search's re-verify of export pins (spool_columns/decoded_spool/native/journal witness) |
| D day-1 visibility | PARTIAL | DONE for the changes: serial-mode reasons (one worker / below threshold), hasher aborted/ended flags, throttle waits, re-hashed parts listed, discovery-read cross-check counted, native import fallback reason, save-point reuse list and switch state, probe failure count, SIGTERM disposition. Leakage gates unchanged and hard |
| E science unchanged | - | Columns, series, cells, couplings rows, part bytes and pins, provenance, leakage gates and receipt meaning unchanged; only additive diagnostic fields (parse.hashing, parse.window, cpu_placement.sigterm_inherited_by_workers, cpu_placement.probe_failures, hashing.save_point, hashing.mode_reason, hashing.probe_failures, source_passes kind text) |
| F1 compute dedupe | see A5 | see section 3 |
| F2 pass dedupe | see section 3 | see section 3 |
| F3 content dedupe | see section 3 | listed, not built (section 3) |

## 2. Changes (function names and line ranges after the edit)

search.py
- `FrontierHasher` (new, search.py:385-460): sha256 of a file in file order on a daemon thread, throttled to at most
  `lead` bytes past the decode frontier (`advance(offset)` after each range consumed), so the hash reads the pages the
  range workers read; `stop(timeout=60)` bounded; `finish()` reads to the end and returns (bytes, hexdigest);
  `report()` for the receipt. Shared by search and native (no duplicate helper).
- `spool_columns` (search.py:467-528): ranges = max(workers x 4, size // SPOOL_COLUMN_RANGE_BYTES + 1) with
  SPOOL_COLUMN_RANGE_BYTES = 256 MB, in-flight window 2 per worker (SPOOL_WINDOW_PER_WORKER), FrontierHasher, a
  progress unit per range, a bounded abort; serial branch records its reason. Merge rules unchanged.
- `decoded_spool` (search.py:554-600): FrontierHasher instead of the free-running hasher; bounded abort; progress per
  range. Every per-record check stays on the coordinator in spool order (build_series:995-1060 unchanged).
- `_progress` + `PROBE_FAILURES` (search.py:602-614): one heartbeat helper; the three old silent `report_phase`
  blocks (phases, coupling cells, discovery problems) now call it; transform steps report units.
- `PART_DIGESTS`, `PART_READS`, `_part_digest` (search.py:1552-1566): the coupling part pin is the digest its job
  recorded in its saved state (the fsynced bytes it renamed, or the file it re-hashed and compared on a resume).
- `_part_nominations` (search.py:1969-1990): reads the part as bytes and hashes every line as read; returns
  (rows, nominations, (bytes, sha256)); `discovery_nominations` stores the read in PART_READS.
- `search()` publish (search.py:2493-2512): pins from PART_DIGESTS; a part without a recorded digest is hashed on
  pinned threads (listed in source_passes.rehashed); a discovery read that disagrees with the job's digest is a hard
  error naming both. `cpu_placement.sigterm_inherited_by_workers` and `cpu_placement.probe_failures` added.

native.py
- `_decoded_lines.parallel` (native.py:270-312): FrontierHasher (window 2 per worker), bounded abort recorded as
  pool_recovery.hasher_ended_after_stop, `hashing` on the parse report.

data.py
- `_progress`, `PROBE_FAILURES`, `REUSE_PINS_ENV`, `_stat_key`, `_pins_progress` (data.py:134-176): heartbeat and the
  export's save point: every pin appended to `<day>/cycle-NN.pins-progress.jsonl` (beside the target) as it lands;
  reuse only with FRANKIE_EXPORT_REUSE_PINS=on and an identical (device, inode, size, mtime_ns) (ctime excluded: the
  export's own hard link changes it).
- `_pin_all` (data.py:179-247): hashes only what is not reused, largest first, ordered_map as before; heartbeat per
  file; hashing record gains mode_reason, save_point, probe_failures.
- `export` (data.py:387-): passes the save-point path; the native-selection fallback now carries its reason.

wrappers
- data.sh, search.sh: `lane_size` from FRANKIE_LANE_CPUS / FRANKIE_BOOKED_CPUS / nproc; default WORKERS = lane - 1
  (at least 1); search.sh validates WORKERS.

Not changed (as instructed): frankie_box_market_timeline.py, frankie_box_boss_session.py, frankie_box_lane_pin.py.
journal.py, dipole.py, transforms.py, surface.py: audited, no edit (reasons in section 5).

## Why bytes are unchanged
- Range cut count and in-flight window never change the joined columns: the parts are joined in file order with
  columns()'s rules (first appearance order, None for absent rows); proven for 8, 42, 229 and 6000 ranges.
- FrontierHasher hashes every byte in file order; only read timing changes. Proven equal to hashlib.sha256.
- A part's pin was sha256_file(part) at publication; now it is sha256 of the same fsynced bytes taken by the job
  before the rename (or the job's own re-hash on resume). Nothing writes a part between job end and publication; the
  discovery read cross-checks it. Same values in MANIFEST couplings.parts.
- Binary-mode `_part_nominations`: json.dumps lines have no carriage return, so the text read's newline translation
  never applied; json.loads(bytes) decodes UTF-8 the same. Proven equal to the old reader verbatim.
- The export's pins are measured exactly as before unless the reuse switch is on (default off).

## 3. Dedupe (F), per sub-step

| Sub-step | Read/computed/rendered more than once today | Done |
|---|---|---|
| export hashing (data `_pin_all`) | each file hashed once per export; whole export re-hashed on any rerun (staging rmtree'd, data.py:395) | save point records pins; reuse is Greg's call (c), switch default off |
| export -> search | every selected spool/ledger/JSON hashed by the export, then again by the search as it decodes (verifies the export pin) | kept (it is the integrity check across stages; skipping it is call (c)) |
| frames/structures/prices decode (spool_columns) | decode read + independent hasher read: 2 disk passes on spools larger than the page cache | one disk pass (FrontierHasher + bounded window) |
| INPUT spool (decoded_spool) | same | one disk pass |
| native ledgers (_decoded_lines) | same | one disk pass |
| sealed journal (journal.py:44-88 witness + FrankieCompactReader) | witness thread reads ~24 GB beside the SQLite reader | kept: 24 GB fits in page cache; the reader is SQLite pages, not a byte stream to throttle against |
| dipole source (dipole.py:37-38) | read whole once, hashed once | nothing to dedupe |
| export MANIFEST | read by search several times: build_series:788 (bytes+sha), native.read_columns:322, dipole.read_columns:31, sha256_file at identity (search.py:~2360), again at prepare end and before publication (integrity checks) | kept: small file; the repeated sha256 checks are deliberate change detection |
| coupling parts | written+hashed by job, read by discovery, re-read+hashed at publish | publish re-read removed (one write-hash, one discovery read that cross-checks) |
| partner FFTs | per cell cached per worker (existing _FFT_CACHE) | unchanged |
| pass dedupe: columns() | already one pass with per-channel accumulators (search.py:285) | unchanged |
| pass dedupe: cell index | already one pass per text column (search.py:~2430) | unchanged |
| pass dedupe: asof alignment | one alignment shared by a source's numeric and text fields (search.py:~971-975) | unchanged |
| pass dedupe: INPUT loop | one pass per record; but `for field in event_fields: append None` per record (search.py:1035-1040) is O(fields) per record | listed (S6): byte-identical rewrite to positional accumulators possible, not built (measure first) |
| content dedupe: coupling part rows | every row repeats day, cycle, day_role (header), and `transform` == `x_transform` | NOT built: the part bytes are read by the scientific teacher, review and survivor update (other owners) and pinned; a keys-once / `=k` stacked rendering (frankie_box_stacked_text.py / DIGEST_V10 grammar) would have to be an ADDITIONAL rendering with parse-back proof, or a coordinated format change. Request R4 |
| content dedupe: MANIFEST / workflow-report.json | MANIFEST repeats per-source key lists (numeric/text/placed_series); workflow_report copies leakage, dispositions, not_searched from the MANIFEST | workflow-report.json already names long lists by count and MANIFEST location (compact_report); a stacked rendering of the MANIFEST for model readers is not built (no model reads it today; the scientific teacher reads JSON) |
| content dedupe: export MANIFEST | `what` strings repeated per file of the same pattern | same as above: a pattern table referenced by index would change the MANIFEST bytes read by search/teacher; listed |

## 4. Tests run (output)

`python3 -I .../scratchpad/search/selftest_stacks.py` (package stubs for research.* because the package __init__
imports torch, absent here; c15_journal and parallel_teacher import cleanly):

```
spool_columns == serial columns() (workers 2, range bytes 1073741824, 8 ranges) PASS
spool_columns == serial columns() (workers 4, range bytes 50000, 42 ranges) PASS
spool_columns == serial columns() (workers 7, range bytes 9000, 229 ranges) PASS
spool_columns == serial columns() (workers 3, range bytes 1, 6000 ranges) PASS
spool_columns refuses a changed spool                                    PASS
decoded_spool == unpack_spool (5 workers, 6000 records)                  PASS
decoded_spool early close returns promptly (bounded stop)                PASS 0.04 s
FrontierHasher digest == hashlib.sha256 of the file                      PASS
FrontierHasher holds at frontier + lead until advanced                   PASS
FrontierHasher.stop() bounded                                            PASS
native _decoded_lines parallel == serial (rows, bytes, sha256)           PASS
_part_nominations == the old text read; its digest == sha256 of the part PASS
data _pin_all pool == serial (bytes, sha256 per file)                    PASS
data save point lists every pin as it landed                             PASS
data rerun with the reuse switch off re-hashes every file                PASS
data rerun with the switch on reuses identical-stat pins, same pins      PASS
16/16 passed
```
Toy rows carry nested books, sparse and late channels, bytes leaves, mixed None/int/float/2**70 values and a backwards
receive clock. Wrapper `lane_size`: 0-31 -> 32, 0-7,16-23 -> 16, booked 5 -> 1, none -> nproc. Also py_compile and
ast.parse of all seven .py files, bash -n of both wrappers, git diff --check.
Not tested here: a killed worker inside these new paths (ordered_map's redo was toy-tested in session 4 and is
unchanged); the full search() / export() end to end (needs numpy/pyarrow/duckdb and real exports); the box.

## 5. Template mapping (Sept-29 "Speed items 1-5 + resume" and frankie_box_lane_pin)

| Template item | Where in these pieces |
|---|---|
| 1 pieces side by side | export: files hashed side by side (data `_pin_all`, ordered_map); search: leakage gates side by side (`leakage_gate_batch`), transform steps, coupling cells, discovery problems, nominations (all `_run_pending`/ordered_map). NOT yet: the independent sources inside build_series (spot S1) |
| 2 pass 2 segment replay by pinned workers | `spool_columns`/`_spool_range_columns`, `decoded_spool`/`_spool_range_rows`, native `_decoded_lines`/`_decode_range`: ordered line ranges on pinned workers, joined in order |
| 2 exact saves at group-closed points, resume | search: identity.pkl, prepared.pkl after build_series, step-*.pkl per transform, per-cell `.state.pkl` with the exact next partner cursor, discovery-*.pkl (existing). Each frames/INPUT line is one F_LAST group, so every range cut is a group-closed boundary; a save INSIDE build_series (per source, or per range at a cursor) is not built (spot S3: needs the start-at-cursor read, which for a spool here means re-hashing the prefix because a sha256 midstate cannot be saved; deferred verify below). Export: the new pins-progress save point (reuse = call (c)) |
| 3 deferred verify | the spool pin check is already after the last range (decode runs ahead of the comparison); the hash runs concurrently, not deferred to a later job |
| 4 observation none | N/A here (ingest/teacher) |
| 5 batch decode, every per-record check kept | `decoded_spool` -> the INPUT loop in build_series keeps every instrument/closing/F_LAST check on the coordinator in order |
| lane_pin.lane_cpus / core_order / placement / record | search `lane_cpus`, `worker_cpus`, `pin_coordinator`; data `LP.record` |
| lane_pin.ordered_map | every pool in data/search/native (no own pool written) |
| lane_pin.executor('thread') | native selection witnesses, the publish re-hash fallback for parts |
| wait_result / iterate_ordered / pinned_pool | not used (ordered_map supersedes them in these pieces) |

journal.py reads through FrankieCompactReader (its own pinned workers, owned by the timeline/ROOT side) and its
witness thread; dipole.py reads one JSON whole; transforms.py are pure functions run on ordered_map workers by the
search; surface.py `journal_axis` is unwired (NOT_SEARCHED) and `external_fields` runs on the day file's as-of reader.
None of them reads a spool through its own path, so "read through the same path" holds for every spool these pieces
read; the journal goes through the shared extractor (frankie_box_market_timeline.frame_index / FrankieCompactReader),
which is frozen for a2.

## 6. Additional CPU spots (walk of both stages; ranked by expected gain)

Shares are estimates from code structure, unmeasured (no stage-6/7 run on a full day exists).

| # | Spot (file:line) | What runs serially / idle | Est. share of stage wall | Byte-identical on workers? | How | Status |
|---|---|---|---|---|---|---|
| S0 | search.py:835 spool_columns of frames | fits only if the frames spool fits RAM | blocks the stage on 20231018 | yes (out-of-core per-channel arrays written by the range workers) | redesign | blocked: owner decision (finding 0.1) |
| S1 | search.py:835-1150 build_series sources | native, journal, structures, prices, INPUT, dipole, external read one after another after the frames decode; each has its own pool but they never overlap | 30-60% of preparation | yes if each source's (series, cells, sources, notes, gates) is appended in today's order | side by side: split the lane between two or three source readers (thread per source, each ordered_map on its share) and merge outputs in the fixed order | not built: restructures the asof()/notes closure; needs a canary to size; next pass |
| S2 | search.py:995-1060 INPUT per-record checks | one coordinator core consumes every INPUT record (the single-core consumer limit queued on market_timeline) | 10-30% of preparation | yes: per-range group counts/field accumulators can be computed in the range workers and merged in order, with the instrument/closing checks done per range against event_frames | pipeline: workers return per-range partial counts | not built: event_frames/owners must be shared to workers (fork after _frame_index works); measure first |
| S3 | build_series save points | a stop or crash in preparation redoes the whole preparation (decode of every spool) | all of preparation on a resume | yes | per-source saved results (prepared parts) bound to identity + pins | not built (memory/size of the pickles is the same problem as S0) |
| S4 | search.py:2430-2442 cell index; 2445 jobs list | coordinator only; one pass per text column | small unless ID cells (call (b)) | yes: columns independent | ordered_map over columns, merged in sorted order | not built (gain depends on (b)) |
| S5 | search.py:1523 pin_coordinator; lane_pin.placement | the coordinator's hyperthread sibling (N+16) is the LAST worker CPU, so a worker shares the coordinator's core; during build_series the coordinator is unpinned | a few % on merge-heavy phases | placement only | take the sibling out of the worker set (31 -> 30), as ROOT did | not built: lane_pin owner (request R2); throughput trade |
| S6 | search.py:1035 per-record `for field in event_fields: append None` | O(fields) per record on the coordinator | small-moderate | yes (positional accumulators, materialize at end like columns()) | pass collapse | not built: measure on a canary first |
| S7 | search.py:1286-1300 context merge, non_market_reason over every channel | coordinator | small | yes | ordered_map over channels | not built (small) |
| S8 | search.py:2463-2490 couplings | already on ordered_map; per-job state pickle per cell even for short jobs | dominant at search time | n/a | fewer files for short jobs would change recovery layout | listed (depends on (b)) |
| S9 | discovery (search.py:2151) | PySR fits per problem on workers (serial Julia per worker by design) | unknown | n/a | already parallel | none |
| S10 | data.py:387-404 export links | os.link per file, coordinator | negligible | yes | - | none needed |
| S11 | data.py `_pin_all` | the largest file (frames, ~430 GB) is one sha256 on one worker: the export wall is that one file (~6 min at the 1250 MB/s volume cap; sha256 itself ~1.5-2 GB/s per core) | ~all of the export | the digest cannot be split (sha256 is sequential); a tree hash would be a new identity | none without changing the pin | listed: bounded by disk, not CPU |
| S12 | journal.py:91-104 witness + reader | already side by side | - | - | - | none |
| S13 | transforms.py | pure, run per (series, transform) on workers | - | - | - | none |

## 7. Cross-owner requests

- R1 (frankie_box_lane_pin.py owner): `ordered_map`'s `finally: pool.terminate(); pool.join()` (lane_pin.py:435-437)
  joins without a bound. If a forked worker ever inherits a SIGTERM handler that does not exit (the a2 shard-exit
  hang), join() waits forever. Ask: set SIGTERM to SIG_DFL in `_tracked_initializer`, and after terminate() join each
  worker with a timeout, then SIGKILL the survivors and record it in `report`. Today these pieces install no handler
  (recorded on the MANIFEST as cpu_placement.sigterm_inherited_by_workers).
- R2 (lane_pin owner): an option in `placement`/`ordered_map` to leave the coordinator's sibling out of the worker set
  (whole-core serial consumer), for S5.
- R3 (frankie_box_market_timeline.py, QUEUED after a2): start-at-cursor and segmented reads would let the journal
  bridge resume mid-journal (S3); the single-core consumer limit is S2's twin; the "double read of spools" item is
  handled inside these files (FrontierHasher) for every spool they read; the journal (SQLite) is read by the
  witness and the reader (kept, fits page cache).
- R4 (scientific teacher / review / survivor update owners): a keys-once stacked rendering of coupling parts (header
  and transform stated once) would need their readers to parse it; propose an additional rendering with parse-back
  proof, not a replacement, if they want it.
- R5 (owner of the frames-spool decision, finding 0.1): out-of-core columns for stage 7 before a2's search.

## 8. RUNTIME-UNVERIFIED

Everything above. Unmeasured: the FrontierHasher's single-pass effect (needs a spool larger than the page cache),
the window's memory, heartbeat rates, the lane-sized wrapper defaults on the box (the orchestrator passes its own
WORKERS, so the default changes only manual runs). The frames-memory finding is from a2's measured spool size and the
code, not from a run.
