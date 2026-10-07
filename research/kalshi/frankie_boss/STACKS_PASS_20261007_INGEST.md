# Stacks pass, session 5: INGEST / DAY FILE / OFFLOAD (2026-10-07 night)

Owner: the ingest agent (stage 0 preflight checks outside the Run controller, stage 1 ingest, stage 2 day file, the S3
transport helpers, archive). Greg's go: "make sure every workflow step has been updated with the optimizer stacks, cpu and
workers for multiple steps in each piece and the aws tool upgrades that root got from the deep dive". Follow-ups relayed
mid-task: build on the Sept-29 templates and the shared pin helper (`frankie_box_lane_pin.py`); F DEDUPE; "Additional CPU
spots". Base: work branch `ccr-d2f8f826-iefeah-frankie` at 2f39ddc (the parent snapshotted these edits into its WIP
commits 92a0889..c7a8228 while the work ran). SOURCE-BUILT / RUNTIME-UNVERIFIED: no AWS call, no box run, no install.

## 1. Files changed (diff against 2f39ddc)

| File | Change |
|---|---|
| `deploy/aws/box/frankie_box_s3_transport.py` | NEW: the ONE shared S3 transport (section 3) |
| `deploy/aws/box/frankie_box_ingest_block.sh` | ACTION=fetch inline Python uses `fetch_url` (curl and the private `ranged()` removed); block fetch probe; receipt fields |
| `deploy/aws/box/frankie_box_offload.py` | `_upload` through `transport.upload`; `sha256_basis` on every pointer |
| `research/kalshi/frankie_boss/operations/ingest_cpus.py` | placement re-based on `frankie_box_lane_pin`; new bounded `end_pool` |
| `research/kalshi/frankie_boss/operations/parallel_ingest.py` | pass 2/3 pool stop through `ingest_cpus.end_pool` (bounded, both paths) |
| `research/kalshi/frankie_boss/operations/ingest_block_sources.py` | `--fetch` through `transport.download`; FRANKIE_WORK_PROBE_V1 probe in `_emitter`; journal sha256 hashed beside the drain |
| `research/kalshi/frankie_boss/compact_build_journal.py` | bounded encoder-pool stop; broken pool at SUBMIT time redone (a real defect found by the toy test) |

Not edited (read only): boss_session, market_timeline, experiment.py, frankie_queue, cpu_controller, lane_pin, mbo_source
(pinned extractor), frankie_journal_reader / CompactConformanceReader (gold reader), compact_journal (codec), c15_builder.

## 2. Audit table (before -> after), checklist A-F

| # | Item | Before (file:line at 2f39ddc) | After |
|---|---|---|---|
| A1 | Pools sized from the booked CPU list, DAY_CPUS 8/16/24/32/auto, W+1, no fixed WORKERS=7 | DONE: ingest_block.sh `size_day` 94-114, run_tool 328, cores.py `run --size` | DONE (unchanged) |
| A2 | Parent on the lowest booked CPU, workers one per CPU physical-core first (N/N+16 siblings last) | PARTIAL: ingest_cpus.py placement used boss_session directly, not the shared lane_pin helper | DONE: ingest_cpus `lane` 90, `core_order` 105, `placement` 131, `pin_thread` 256, `record` 294 now call `frankie_box_lane_pin` (lane_cpus / core_order / placement / pin_thread / record); the ingest's own rule (never more workers than lane-1, parent = lane[0], the reader's reserved CPU) is checked on lane_pin's answer, local fallback otherwise. Toy: 32-CPU N/N+16 map gives parent 0, workers 1-15,17-31,16; lane 8-15,24-31 gives parent 8, workers 9-15,25-31,24 |
| A3 | Pinned encoders ending at the seal | DONE: compact_build_journal `_start_pool`/`_pin_encoder`, `seal` -> `_end_pool` | DONE; the stop is now bounded (A6) |
| A4 | Dead encoder / dead worker redo with one fewer, never stop/hang/wait | PARTIAL: `_collect` redid on BrokenProcessPool, but `flush()` -> `_submit()` on an already-broken pool RAISED (the ingest would die). Found by the toy kill test | DONE: compact_build_journal `flush` (try/except around `_submit`, then `_recover`). Toy: SIGKILL of one of 4 spawn encoders mid-run, container file sha256 identical |
| A5 | Parallel pass 2/3 on one pinned pool, ordered hand-off; members side by side | DONE: parallel_ingest `ingest_parallel` (one `pinned_pool`, window workers+2, `CompactBuildJournal(executor=)`), `prepared_sources` | DONE (unchanged); pool helper is boss_session `_PinnedPool` (lane_pin has no submit/get never-stop pool: cross-owner request X1) |
| A6 | Every stop bounded (no unbounded join after terminate; the a2 shard hang shape) | MISSING: parallel_ingest 524-526 `pool.close()` / `pool.terminate()` (both join unbounded); compact_build_journal `_end_pool` `shutdown(wait=True)` unbounded; `_close_handout` `join_thread()` | DONE: `ingest_cpus.end_pool` 326 (close/terminate in a helper thread for `grace` s, then SIGKILL of live worker pids, then `grace` more; noted when it had to act), used by parallel_ingest 523/528; `_bounded_shutdown` + `END_GRACE_SECONDS` in compact_build_journal; `cancel_join_thread`. Toy: a fork pool whose busy workers IGNORE SIGTERM (a2 shape) stops in 3.0 s, 3 workers SIGKILLed |
| A7 | Fetch-ahead of the next day inside the running day's booking; rolling DAYS_AT_ONCE; staging days in parallel | DONE: ingest_block.sh `fetch_ahead` 175, `each_day` 142, `at_once` 344 (rolling) | DONE (unchanged). at_once still fetches the list's days one after another before booking (339): NIC-bound, see section 6 rank 6 |
| A8 | Every partition read and hashed once | PARTIAL: fetch wrote then re-read the whole `.part` to hash it (ingest_block.sh 286 `got = sha(part)`) | DONE for the fetch: `fetch_url` hashes in order as the bytes land (`_OrderedHash`); remaining repeats named in F1 |
| A9 | Outputs byte-identical proven by a toy | MISSING for this pass | DONE: section 5 (inline, 1, 2, 4 encoders, 4 with one killed, shared fork pool with a kill: all one container file sha256) |
| B1 | FRANKIE_WORK_PROBE_V1 progress.json heartbeat for fetch, decode, pass 2/3, seal | MISSING: ingest wrote progress.jsonl only; the fetch wrote nothing | DONE: ingest_block_sources `_emitter` 542 writes progress.json beside the journal (stages: ingest records, pass 1 records, opening book warm, pass 2 segments, pass 3 entries, seal + conformance, saved); the block fetch writes one beside the partitions (`T.WorkProbe`, bytes); the stage heartbeat (frankie_box_stage_progress) finds probes beside files the tree holds open and computes units/min and its report-only 600 s stall flag; fetch_url adds its own report-only STALLED note at 600 s on the receipt |
| B2 | Run settings exported to children (FA-6) | DONE in the Run controller wrappers (frankie_box_run / queue, session 4); the ingest wrapper's settings are SSM `--set` assignments read as shell variables and passed as flags/env to the tool | N/A here (Run controller owns the export) |
| B3 | DETACH exit semantics (FA-2) | N/A: the ingest wrapper does not DETACH (it runs to completion under SSM; 75 = booking wait, 3 = failed, 2 = refused) | N/A |
| C1 | MBO partition fetch 15 x 16 MB ranged above 64 MB, bytes/sha checks, receipt `transport` | DONE (session 4) in bash-inline Python | DONE through the shared helper; receipt adds `hash_pass`, `retries`, `stalls`, `transport_receipt`, `bytes_to_fetch`, `bytes_fetched`, `fetch_pin`, `rehash_rule` (additive) |
| C2 | CRT first (awscrt 0.31.2), 128 MB x 16, classic fallback, REASON on the receipt, download and upload | PARTIAL: offload and `--fetch` tried CRT then classic but swallowed the reason (no receipt field) | DONE: `transport.download`/`upload` record `transport` ('crt'/'classic') and `transport_fallback` (why CRT was absent or failed, each attempt's error); offload pointer carries `transport`, `transport_fallback`, `transport_attempts`; `--fetch` writes `fetch-receipts-<ts>.json` and a `fetch_member` event per member. Presigned-URL fetches (the box's role reads nothing in S3) cannot use the CRT S3 client: they use the ranged urllib path |
| C3 | ONE shared transport helper importable by other pieces | MISSING (logic duplicated in ingest_block.sh, day_external.py, pull_runner_ingest.sh, archive_day.py) | DONE: `frankie_box_s3_transport.py` (section 3). Adopted by ingest_block.sh, ingest_block_sources, offload. Not yet adopted: day_external.py 170-182 (`FETCH_STREAMS` ranged), pull_runner_ingest.sh 174-221, archive_day.py (presigned PUT pieces with If-None-Match): mine, left for a follow-up to keep this pass reviewable (section 7) |
| C4 | Large sequential reads in big buffered chunks | PARTIAL: ingest_block.sh `sha` 4 MiB ok; offload `file_digest` ok; mbo_source `_verified_copy` 64 KiB (pinned, not editable) | DONE where owned (transport 4 MiB `READ_CHUNK`); mbo_source named in F1 |
| C5 | No skip of a re-hash by stat alone (open call (c)) | offload `_sha256` HAS a cross-process stat cache (offload-cache, predates the call); frankie_box_filehash.witness is an in-process stat-keyed cache | Kept unchanged (Greg's call) but made visible: every offload pointer has `sha256_basis` ('hashed' or 'stat_cache:<tag>'); the fetch receipt states `rehash_rule`. Where a skip would apply if Greg says yes: ingest_block.sh `member_one` present path (`have = sha(dest)`), the linked-from-other-block path (`sha(other)`), ingest_block_sources `fetch_sources` present check, parallel_ingest `_done` (spool re-hash on resume) |
| D1 | Every skip/wait/refusal/fallback/cap/retry/stale input on the receipt with its reason | PARTIAL: fetch retries printed only; CRT fallback silent; pool stops silent | DONE for the touched paths: retries, stalls, kept-aside paths, transport fallback reasons, bounded-stop actions (`pool_stopped`, `encoder_pool_stop_bounded` events), placement helper used (`pin_helper`, `pool_helper` on the cpu_placement event). Inspection markdown: the ingest has no inspection writer of its own; frankie_box_workflow_inspection (not mine) should project these (X3) |
| D2 | Record count measured at ingest; a wrong day stops at ingest with both numbers named | DONE: the tool's counts are the builder's (record_count on the receipt, measured), the pinned conformance stack refuses a declared-count mismatch; `day_pipeline.reconcile_ingest` names both numbers (operations/day_pipeline.py, the 2026-09-17 fix) | DONE (unchanged) |
| E | Journal bytes, head hash, box cut, receipt field meaning identical; additive only | n/a | Held: no change to append/append_body/flush cut rule/encode_block/insert order/seal; receipt fields only added; journal_sha256 is the same whole-file sha256 (hashed on a thread, used only if size/mtime/inode unchanged, else re-hashed) |
| F1 | COMPUTE dedupe: each partition fetched, hashed, decoded once per day | fetch: write + full re-read to hash (fixed). Still repeated: (a) mbo_source `_verified_copy` (mbo_source.py:96) copies each partition to a temp file while hashing, then `_decompressed` (110) re-reads it: the TOCTOU snapshot of the pinned extractor (the bytes verified are the bytes decoded), not editable here; (b) the ingest tool re-hashes a partition the fetch already hashed (across processes; skipping is call (c)); (c) parallel resume: `pass_one(evolve=False)` (parallel_ingest 439) decodes every record again to hold them for pass 2 (by design: records are in memory, not saved); (d) resume: `_done` (345) hashes each finished spool and pass 3 `read_spool` (509) hashes it again; (e) receipt `journal_sha256` re-reads the sealed journal after the drain, and the drain reads it too | fetch: once (in-stream). (e): the hash now runs BESIDE the drain on its own thread (`_HashBeside`, `_journal_sha256`), the two reads overlap in time and page cache; the gold drain itself is a required verification pass. (a)-(d) kept: (a) pinned + security, (b) call (c), (c) design (pass 1 and pass 2 already share ONE decode on a fresh run through `_SHARED` + gc.freeze), (d) a corrupt spool must be redone, not refused |
| F2 | PASS dedupe | Passes 1/2/3 are the design; fresh run: no sub-step re-walks data another walked except the verification drain (gold) and the receipt hash (now overlapped) | No pass dropped; no per-record check relaxed |
| F3 | CONTENT dedupe (receipts/manifests only) | fetch receipt repeated `transport` per file; `transport_receipt` adds the full transport receipt per file (it repeats member_key/sha256) | Accepted repeat: the transport receipt is the shared schema other pieces read; stated once per member. Gold journal bytes untouched |

## 3. The shared transport: `deploy/aws/box/frankie_box_s3_transport.py`

Import (stdlib-only at import; boto3/awscrt imported inside the calls):
`sys.path.insert(0, <checkout>/deploy/aws/box); import frankie_box_s3_transport as T`.

- `T.fetch_url(url, dest, *, expected_bytes, expected_sha256=None, range_streams=15, ranges=None, probe_dir=None,
  say=print, on_bytes=None, attempts=6, range_bytes=16 MiB, ranged_above=64 MiB, window=None) -> receipt`
  Presigned GET. Above 64 MiB: concurrent 16 MiB ranges written by `pwrite` into `<dest>.part`; sha256 computed in order
  while ranges land (`_OrderedHash`, at most `window` = streams + 4 ranges held: about 300 MB per member); at or below:
  one stream, range-resume after a drop, hashed while written. Then bytes/sha256 compared; equal -> renamed create-only;
  different -> `.part.rejected-<ts>`; a file that appeared at dest -> `.part.late-<ts>`. `ranges` lets the caller share
  one ThreadPoolExecutor across members (the NIC budget is not multiplied; no deadlock: a range waits only for a lower
  range of its own member, which FIFO hand-out has already started).
- `T.download(bucket, key, dest, *, region, expected_bytes=None, expected_sha256=None, client=None) -> receipt`
  Signed GET via boto3: CRT (128 MiB x 16) then classic (16 MiB x 15); sha256 one 4 MiB-chunk read after
  (`hash_pass: after_download`: boto3 writes the file itself). Same create-only / keep-aside rules.
- `T.upload(path, bucket, key, *, region, sha256=None, extra_args=None, client=None) -> receipt`
  CRT (128 MiB x 16) then classic (128 MiB x 16). The caller does the head/If-None-Match decision.
- `T.WorkProbe(directory, stage, total)`: a FRANKIE_WORK_PROBE_V1 progress.json writer (frankie_box_progress.Probe when
  importable); `T.sha256_file(path)`.
- Receipt schema FRANKIE_S3_TRANSPORT_V1 (additive): op, dest/path, bucket/key or url_host, status
  (restored|uploaded|refused), reason, bytes, sha256, expected_bytes, expected_sha256, transport
  (`ranged-<N>x16MiB`|`single-stream`|`crt`|`classic`), transport_fallback, hash_pass, seconds, bytes_per_second,
  retries[], stalls[], kept_aside. Never raises for a transfer outcome; every read has a 120 s socket timeout and at most
  `attempts` tries (backoff 5..60 s), so a stalled transfer ends as `refused`, never a hang.

## 4. Template map (Sept-29 "Speed items 1-5 + resume", HANDOFF_20260929_EXPERIMENT_BUILD.md) and the session-4 stack

| Template item | Function(s) | Session-4/5 stack on it |
|---|---|---|
| 1 days side by side, worktree per dispatched commit, DAYS_AT_ONCE, own concurrency group, per-dispatch presign map | ingest_block.sh `checkout_markets` 123, `at_once` 344, `MAPF` per dispatch and day 199; concurrency group is frankie_box_run.yml (Run controller's) | rolling DAYS_AT_ONCE, `size_day` DAY_CPUS per day, fetch-ahead inside the booking, fetch through the shared transport |
| 2 parallel_ingest: pass 1 state only, saves every 20,000 at a group-closed point (adapter pickled), pass 2 replay through C15BuilderNoObservation must end on pass 1 state, pass 3 patch hash + cut boxes as append() | parallel_ingest `pass_one` 181 (`_state` at 253/276/294), `_segment` 307, `ingest_parallel` 398, `CompactBuildJournal.append_body` | `prepared_sources` members side by side on lane CPUs; pass 2+3 overlapped on ONE pinned pool (`ingest_cpus.pinned_pool`, executor=); bounded stop (`end_pool`) |
| 2 resume (`RESUME_DIR` / `--resume`) | ingest_block_sources `main` (--resume), parallel_ingest `ingest_parallel` (plan.json reuse, `_done`) | see the resume finding below |
| 3 VERIFY=deferred + ACTION=conform | ingest_block_sources `ingest` (verify == 'deferred'), `conform_directory`; ingest_block.sh `conform` 380 | conformance drains under `ingest_cpus.resilient` (one worker fewer on a broken pool) |
| 4 OBSERVATION=none (+ observation_replay.py for the teacher) | ingest_block_sources `ingest` (C15BuilderNoObservation class swap); parallel mode requires it | unchanged |
| 5 fast_mbo_decode batch decode, every per-record check kept | ingest_block_sources `ingest` (`fast_mbo_decode.records`), parallel_ingest `pass_one` | unchanged |
| shared pin helper frankie_box_lane_pin.py | ingest_cpus `lane`/`core_order`/`placement`/`pin_thread`/`record` | NOW on lane_pin (this pass); pool stays boss_session `_PinnedPool` (X1) |

RESUME FINDING (verified by reading, not run): `--resume` continues from (i) a COMPLETE pass 1 (plan.json + states +
pickles hash-checked, parallel_ingest 405-412; the records decoded again, no state recomputed) and (ii) every finished
pass-2 segment (`_done`, size + sha256), with pass 3 always rebuilt (the partial container moved aside). It does NOT
continue from the last 20,000-record point INSIDE pass 1: the states are computed every 20,000 records but held in
memory and written only when pass 1 ends (parallel_ingest 420-431); an interruption inside pass 1 restarts it at record 0.
Not changed in this pass (cannot be toy-tested here: the package import needs torch; and it touches the state that pass 2
must end on). Design for the follow-up: write each `_state` (canonical + pickle, sha256) to `segments/pass1-<n>.c15.json`
/ `.pickle` as it is made; on --resume without plan.json, restore chain (RecordPrefixChain.restore), adapter (the pickle)
and sessions from the last saved state, decode records up to its cursor with evolve=False, then continue with evolve=True;
the plan.json write stays the commit point. The sequential writer has no resume (by design: canary or full).

## 5. Tests run (this container, Python 3.13; scratchpad/ingest/)

1. `test_transport.py` (local HTTP server with Range; no network): 4 members side by side on one shared 3-stream range pool
   (window 2), two injected range failures retried: all restored, sha256 equals the file and the in-stream hash; digest
   mismatch refused and kept aside; a present destination never overwritten; an unreachable object refused after bounded
   retries. Output: `ALL TRANSPORT CHECKS PASSED`.
2. `test_journal_bytes.py` (real codec: compact_journal, c15_journal, verified_journal_reader; synthetic 3,000 records =
   6,000 entries, 37 rows per box): inline, spawn 1, 2, 4 pinned encoders, spawn 4 with one encoder SIGKILLed mid-run,
   and the shared pinned fork pool (`executor=`): `ALL 6 CASES BYTE-IDENTICAL (blocks, seal, head, box count 163, container
   file sha256 cb7d6b7b1625cdf260750a826f2789cb5d7c509229ce3bc51efc3ae1f23bdd60)`. The first run of the kill case FAILED
   (BrokenProcessPool from `flush`), which is the A4 defect fixed above.
3. `test_pools.py`: shared fork pool with a worker SIGKILLed (idle at the kill: respawned, nothing lost; bytes identical);
   `end_pool` on a pool whose busy workers ignore SIGTERM: stopped in 3.0 s, 3 workers SIGKILLed (`POOL CHECKS PASSED`).
4. `test_placement.py` / `test_placement32.py`: placement through lane_pin on this 4-CPU container and on a simulated
   32-CPU N/N+16 map (lanes 0-31, 8-15+24-31, 0-7): parent = lane[0], workers physical-core first, sibling last, never
   more than lane-1.
5. `py_compile` of every changed .py, `ast.parse` of the fetch's inline heredoc, `bash -n` of ingest_block.sh,
   `git diff --check`: clean.
Not run: the ingest tool itself (`operations/*` imports the package `__init__` which needs torch here), boto3/CRT paths
(no AWS), anything on the box.

## 6. Additional CPU spots (ingest and day-file stages end to end), ranked by expected gain

Pass 1 is the serial spine (parallel_ingest `pass_one`, one parent CPU: decode + chain + book per record). What runs or
could run beside it on the other booked CPUs is marked.

| Rank | Stretch (file:line) | Serial / idle today | Est. share of stage wall | Can run on workers / overlap with gold bytes identical? How | Status |
|---|---|---|---|---|---|
| 1 | Sequential writer parent loop (ingest_block_sources `ingest` 321 `for raw in records`): decode + builder per record on one CPU while encoders idle between blocks | serial by construction (causal chain) | most of a sequential ingest (~70-90%) | Yes, it is what MODE=parallel does (pass 2 replay on all CPUs). Gain = use MODE=parallel for experiment days (OBSERVATION=none required); classroom days needing OBSERVATION=full keep the sequential writer | built; a config call (orchestrator default is parallel) |
| 2 | Pass 1 (parallel_ingest `pass_one` 181): decode + state advance | serial spine, ~1 CPU busy, W idle | est. 30-50% of a parallel ingest (unmeasured) | (a) decode of member k+1 on a worker while pass 1 consumes member k (a decode-ahead thread/process feeding records in order: fast_mbo_decode releases little GIL, so a process + shared memory; bytes identical since pass 1 consumes the same records in order); (b) pass 2 could START on segment k as soon as pass 1 has saved state k+1 (today pass 2 waits for the whole pass 1): a pipelined pass 1 -> pass 2 hand-off; gold unchanged (same states, same spools) | NOT built: needs the incremental pass-1 save (section 4) and records shared with workers forked BEFORE pass 1 ends (today they are inherited at fork after pass 1); unmeasured; design listed |
| 3 | Conformance drain (inline) after the seal | gold reader on all booked CPUs (parallel), ordered consumer on cpus[0] | 10-25% | Already parallel (first-run reader, not edited). VERIFY=deferred moves it off the critical path to ACTION=conform later | built (config) |
| 4 | Receipt `journal_sha256` re-read after the drain (ingest_block_sources 754 at 2f39ddc) | one serial read of the sealed journal | ~1-3% (GB-scale file at ~2 GB/s) | Yes: hashed on a thread beside the drain/completion, used only if the file's size/mtime/inode are unchanged | BUILT (`_HashBeside`) |
| 5 | Member preparation (`prepared_sources` 132): `_verified_copy` copy+hash 64 KiB, then zstd decompress to a temp file, per member | members side by side (one thread each, pinned), each serial internally | ~3-8% (per member size) | Fusing copy+hash+decompress into one read would remove one read of the compressed bytes, but it re-implements the pinned extractor's functions | blocked: pinned extractor (gold/security); listed |
| 6 | at_once fetch of every day before any day books (ingest_block.sh 339) | days fetched one after another | network-bound; small CPU | Days could be fetched side by side on the one shared range pool (same bytes, same checks); gain bounded by the NIC (12.5 Gb/s already filled by 15 streams) | not built (low gain); fetch-ahead already overlaps fetch with the previous day's ingest in the list mode |
| 7 | Fetch hash (ingest_block.sh fetch) | was a full serial re-read after download | 10-20% of the fetch | in-stream ordered hash | BUILT |
| 8 | Pass 3 (parallel_ingest 506-517): parent patches previous_hash + cuts boxes per entry | serial (digest chain), encodings on the pool | est. 10-20% of a parallel ingest | The digest chain is serial by definition; box encodings already on the pool | at the limit (gold) |
| 9 | Resume: `_done` spool hash (345) then pass-3 re-hash (509) | double read per finished spool on resume only | resume only | could hash `_done` checks on the pool side by side (pure reads) | not built (resume only; listed) |
| 10 | Opening book warm (ingest 247-276 / pass_one tail): tail records applied to the book only | serial (book state) | small (<5%) | no (book is causal) | at the limit |
| 11 | Day external (frankie_box_day_external.py): days on `lane_pin.ordered_map`, fetches on a thread executor | already pinned/parallel | n/a | adopt `T.fetch_url` for in-stream hashing of its ranged objects (day_external.py 165-185) | not built (follow-up, mine) |
| 12 | Archive/offload: archive_day upload/verify pieces on PARALLEL threads; offload gzip/upload on `_each` threads | already parallel; offload sha256 serial per file (stat cache) | n/a | archive verify reads every object back by GET: by design (proof). Offload: CRT now first | partly built |

Beside pass 1 today: nothing else of the same day runs (the prep threads end before it; the pool is forked after it).
What COULD run beside it on the other booked CPUs without touching the gold bytes: (i) the next day's fetch (fetch-ahead,
built, list mode), (ii) the next day's member preparation (verify + decompress) for a list (not built), (iii) pass 2 on
already-saved segments once pass-1 states are saved incrementally (rank 2b, not built), (iv) a decode-ahead of the next
member (rank 2a, not built).

## 7. RUNTIME-UNVERIFIED and open

- Everything above on the box: the shared transport (urllib ranged path, CRT/classic paths), the new probes, the bounded
  stops, lane_pin placement on the real topology, the hash-beside thread.
- Not adopted yet (mine, follow-up): day_external.py ranged fetch, pull_runner_ingest.sh fetch, archive_day.py PUT/GET
  pieces onto `frankie_box_s3_transport` (keep their own receipts; add `transport_receipt`).
- Pass-1 incremental save + resume from the last 20,000-record point: designed (section 4), not built.
- Greg's calls touched: (c) re-hash skip (offload's existing stat cache kept but labelled `sha256_basis`); (f) the bento
  bucket region (us-east-2, cross-region, over the IGW; nothing moved).

## 8. The 1-2 minute box canary (for the parent to relay; needs Greg's go, read-only on the sealed day)

What it proves: the new code (pinned encoders on lane_pin placement, the bounded stops, the probe) writes the same boxes
as a sealed receipt's container for the first 20,000 records, and the sealed receipt still matches its file. Sequential
writer only (MODE=parallel refuses a canary; its proof is the full run's receipt compare).

Step 1, dispatch (frankie_box_run.yml, the tip commit staged; OBSERVATION must equal the sealed receipt's
`observation_mode`):
```
script=deploy/aws/box/frankie_box_ingest_block.sh
variables="ACTION=canary MANIFEST=research/kalshi/frankie_boss/blocks/BLOCK_20231018_SOURCE_MANIFEST.json CANARY=20000 DAY_CPUS=32 OBSERVATION=<sealed observation_mode> VERIFY=inline"
```
Step 2, compare (SSM, read-only, venv python, after step 1 printed its canary-receipt; CAN = the canary directory it
printed, SEALED = the 20231018 ingest directory whose ingestion-receipt.json has trading_day 20231018):
```
/opt/frankie-box/venv/bin/python -I - "$CAN" "$SEALED" <<'EOF'
import hashlib, json, sqlite3, sys
can, sealed = sys.argv[1], sys.argv[2]
cr = json.load(open(can + '/canary-receipt.json')); sr = json.load(open(sealed + '/ingestion-receipt.json'))
h = hashlib.sha256()
with open(sealed + '/' + sr['journal_file'], 'rb') as f:
    for b in iter(lambda: f.read(4 << 20), b''): h.update(b)
print('sealed file sha256 == receipt:', h.hexdigest() == sr['journal_sha256'])
print('same packing:', cr['packing']['block_rows'] == sr['packing']['block_rows'])
q = 'SELECT start,count,body,sha256,previous,head FROM blocks ORDER BY start'
c = sqlite3.connect('file:%s/journal.compact.sqlite?mode=ro' % can, uri=True)
s = sqlite3.connect('file:%s/%s?mode=ro' % (sealed, sr['journal_file']), uri=True)
cb = c.execute(q).fetchall(); sb = {r[0]: r for r in s.execute(q.replace('ORDER BY start', 'WHERE start < ? ORDER BY start'),
                                                               (cr['journal_count'],))}
same = all(sb.get(r[0]) == r for r in cb)
last = cb[-1] if cb else None
print('canary boxes', len(cb), 'all byte-identical to the sealed boxes at the same start:', same)
print('canary head at its last box == sealed head at that entry:', bool(last) and sb.get(last[0], (None,) * 6)[5] == last[5])
EOF
```
Expected: three True lines. The canary's in-memory tail rows (not yet a full box) are not in its container; the digest
head of the last flushed box is compared instead. Wall: the canary is ~20,000 records (~1-2 min at the measured rates)
plus a full read of the sealed journal for its sha256.

## 9. Cross-owner requests

- X1 (frankie_box_lane_pin.py owner): add a submit/get pool that survives a dead worker with one fewer (the
  `_PinnedPool` contract: submit(fn, arg) -> task, task.ready(), get(task), workers, close/terminate), or adopt
  `_PinnedPool` into lane_pin, so the ingest's pass 2/3 pool and `CompactBuildJournal(executor=)` go through lane_pin
  entirely. Also: `ordered_map`'s `finally: pool.terminate(); pool.join()` (lane_pin `ordered_map` end) is the a2 shard
  hang shape (unbounded join after terminate); `ingest_cpus.end_pool` is a drop-in bounded stop to copy.
- X2 (frankie_box_boss_session.py owner, after the current agent): `_PinnedPool.close()`/`terminate()`/`_recover()` join
  unbounded (boss_session 466-467, 498-506); the ingest wraps them in `end_pool`, the ROOT callers do not.
- X3 (frankie_box_workflow_inspection.py owner): project the ingest's new events (`pool_stopped`,
  `encoder_pool_stop_bounded`, `encoder_lost`, `worker_lost`, `fetch_member` transport receipts, cpu_placement
  `pin_helper`/`pool_helper`) and the fetch receipt's `retries`/`stalls`/`transport_fallback` into the ingest piece's
  inspection markdown (Day-1 visibility).
- X4 (Run controller, frankie_box_run.yml / experiment.py): when the ingest runs as an experiment stage, pass the ingest
  output directory and the block data directory as the stage heartbeat's `probe_dirs` so the new progress.json probes are
  read first (they are also found beside open files).

## 10. Save/restore vs ROOT (Greg: "every workflow piece needs their restore save code updated to match ROOT's")

Scope: the PARALLEL ingest (operations/parallel_ingest.py, MODE=parallel) is the resumable writer. The sequential
writer (ingest_block_sources.ingest) is canary-or-whole by design: it has no save point, so it keeps the default SIGTERM
(a stop ends it, the day is ingested again from its start) and says so on its `save_route` event. The ingest's files are
not RowSpools (binary spools with sealed `.done.json` markers; canonical JSON + pickle states), so ROOT's rules are
mirrored with each helper named in a comment; nothing of the journal bytes depends on any of it. Lines are the current
working tree.

| # | ROOT contract item (ROOT helper) | Before | After (file:line) |
|---|---|---|---|
| 1 | Save request route: SIGTERM / FRANKIE_LANE_STOP_FILE MARKS the save, run to the next save point, write exact state, exit 75; workers never inherit the mark-only handler (experiment_root.py:125 save_requested; boss_session `_legacy_shard_worker` SIG_DFL) | MISSING: no handler (SIGTERM killed the tool mid-pass); exit 75 meant only "CPU booking waiting" | DONE: ingest_block_sources `save_requested` 727 + mark-only SIGTERM in parallel mode, `os.register_at_fork(after_in_child=_child_default_sigterm)` 734/495 (EVERY forked child, incl. a replacement pool after a dead worker, starts with the default SIGTERM), task-level `default_sigterm` (parallel_ingest 155, compact_build_journal `_default_sigterm` 395; both skip the parent itself when a task runs inline). Save points: each pass-1 group-closed state (parallel_ingest `saved` 325 -> `IngestSaved` 335) and each pass-2/3 segment boundary (718). `IngestSaved` -> `ingest-saved-<ts>.json` (BOSS_BLOCK_INGESTION_SAVED_V1, the RESUME_DIR) + `INGEST_SAVED` line + exit 75 (ingest_block_sources 805). The wrapper tells saved from booking-wait (ingest_block.sh 326, each_day, at_once 370/373) and traps TERM with a command so it reports the tool's 75 instead of dying first (415). A request arriving during the drain after the seal completes the day (exit 0), as ROOT publishes its completion |
| 2 | Periodic exact saves at group-closed points every N units, the last save is the resume point (native checkpoints; legacy-state.pkl) | PARTIAL: states made every 20,000 records at group-closed points but written only when pass 1 ENDED (an interruption inside pass 1 restarted it at record 0) | DONE: `save_pass1_state` 191 writes every state as it is made (canonical JSON + the live adapter pickle, key order kept, done record with both sha256s LAST, create-only, fsync) under segments/pass1/; `load_pass1_states` 212 (contiguous, sha256-checked); `pass_one(resume=...)` 314 restores chain (RecordPrefixChain.restore), adapter (the pickle, checked against its canonical state) and sessions from the last save and continues; records before its cursor are decoded again (held for pass 2), no state advanced for them; plan.json stays the commit point of a complete pass 1 |
| 3 | File positions without re-read (boss_session `_saved_spool_position` 1102, `_resume_row_spool` 1129, `_records_cursor` 1192, `_spool_records_from` 894) | PARTIAL: a resume re-hashed every finished spool in `_done`, then pass 3 hashed it again | DONE (mirrored): `_segment` adds a `resume` block to each `.done.json` (device, inode, mtime_ns, size of the sealed spool, 490); `_done` 496 accepts the same unchanged file with NO read (pass 3 reads it once and compares bytes + sha256: the seal check), else ONE full pass with the reason (`resumed_how`, summed on the `parallel_pass2_reused` event 670). `_records_cursor` for the partition read: N/A, stated: the partition is a zstd DBN stream through the pinned extractor's verified snapshot (mbo_source `_verified_copy`), which has no seekable record offset; the decode is re-run by count (the records are needed in memory for pass 2 anyway) |
| 4 | Identity is content, not location (experiment_root.py:52 content_rebinds) | DONE by construction: plan.json and the pass-1 saves bind content only (manifest_hash, `implementation_identity()` = code blob hashes keyed by file NAME, segment size, sha256s); no saved path. The worktree per dispatched commit (`ingest-code/<sha>`) therefore resumes from any checkout of the same source | DONE (no path to rebind; `content_rebinds` would return [] on every saved document; nothing recorded under checkout-rebinds/ because nothing moves) |
| 5 | Function-level code identity (frankie_box_bedrock.code_identity) | MISSING: the saves bound the builder identity only, not the pass code itself | DONE: `code_identity` 170 = bedrock.code_identity(parallel_ingest.py, CODE_NAMES: pass_one, _state, _segment, SpoolJournal, read_spool, PLACEHOLDER, SEGMENT_RECORDS); bound in the pass-1 saves and plan.json (`code`, additive); a different identity refuses; the builder identity (gold) is checked as before |
| 6 | Additive; an older save still loads (with one full pass noted); the probe continues from the saved cursor | n/a | DONE: plan.json without `code` loads (`old_save_loaded` event 590); a `.done.json` without `resume` is one full pass (`resumed_how`); a pass-1 save without `code` loads; the work probe counts records decoded from 0, so it continues past the saved cursor on its own |
| 7 | Seal check: the full witness read compared with the last saved claim (boss_session `_check_spool_claims`) | DONE: pass 3 reads every spool once and compares bytes + sha256 with its `.done.json` (706-711), refusing visibly; the plan's states/pickles are sha256-checked on resume | DONE (unchanged; now the ONLY full read of a reused spool) |

Toy proof (`scratchpad/ingest/test_save_resume.py`; synthetic MBO rows, the real builder, prefix chain and V4 adapter,
torch stubbed for the package import): from scratch 403 records -> 10 states; the same run with a save requested after
the 4th save stops with IngestSaved at state 3 (cursor 150), 4 states on disk; the resumed run's 10 states are
byte-identical (canonical) to from-scratch, records and counts equal; pass 2 on both gives 9 byte-identical spools; an
unchanged spool is reused with no read, an old marker with one full pass; an old-shape pass-1 save (no code identity)
loads and a different code identity refuses; a forked child has the default SIGTERM while the parent holds the mark-only
handler. `SAVE/RESUME CHECKS PASSED`. The earlier journal-bytes, pool and transport toys re-ran clean after these edits.
Not run: a real day, the queue's ACTION=save route on the box, frankie_box_cores.py run's 75 pass-through.

Cross-owner for save/restore:
- S1 (frankie_box_cores.py `run`, frankie_box_frankie_queue.py:175 save): the ingest exits 75 on a SAVE as well as on a
  booking wait; `cores.py run` must pass the child's 75 through and RELEASE vs RETAIN the booking as the queue's saved
  rule says (ROOT retains it; the ingest today releases at the end of `run`), and the queue must record "saved" for an
  ingest that printed INGEST_SAVED (saved/failed/running/done/unknown distinct).
- S2 (the Run controller's unit for the ingest): systemd's default KillMode=control-group sends SIGTERM to every
  process of the unit, the pool workers included; with the default SIGTERM they die and the parent redoes their work
  with one fewer before it reaches its save point. KillMode=mixed (SIGTERM to the main process only) is the clean route.
- S3 (boss_session `_PinnedPool._recover` 451-467): its `terminate(); join()` is unbounded; with the at-fork rule the
  ingest's workers end on SIGTERM, so it returns, but the bound belongs there.
