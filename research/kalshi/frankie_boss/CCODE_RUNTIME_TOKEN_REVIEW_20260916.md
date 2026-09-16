# Runtime and token review of Frankie / BOSS / ingestion / runners, 2026-09-16

Method: performance-optimization (measure first, attribute, then change one thing) and
code-simplification (behaviour-preserving only) over five areas, each reviewed read-only against
this session's measurements (`CCODE_SESSION_20260916_RESTORE_BENCHMARK_COMPACT_SOURCE.md`). Every
finding carries its identity class, because that decides WHEN it may land:

- **NATIVE**: hashed by `context_session._model_hash` (`trunk.py`, `b1_reasoner.py`,
  `native_mbo_encoder.py`, `context_session.py`, `c15_journal.py`, `causal_packet.py`): a new
  numeric identity, new run only.
- **TEACHER**: hashed into the teacher binding / `c15_registry.implementation_identity`
  (`c15_teacher*.py`, `c15_normalizer*.py`, `c15_builder.py`, `c15_dstate.py`, `c15_observer.py`,
  `c15_registry.py`, `causal_prefix*.py`, `mbo_resume_state.py`, the adapter): new run only.
- **SEED**: bytes pinned into the retained prefix seed sidecars (`sunday_native_runtime.py`,
  `native_forecast_refresh.py`): new seeds, new run.
- **HOST**: in `ActualHost.code` (every .py under the package): new host identity; the Sunday
  re-run is a new run, so allowed, but the lawful `run_actual_sunday.py` itself stays untouched
  until that run is done (Greg).
- **FREE**: readers, codecs, runners, tools; output bytes must stay identical.

Baseline numbers (r7i.4xlarge): raw drain 4.27 ms/row; compact single 6.46 ms/row; compact 15
workers 0.63 ms/row (the parent spends 4.4 of 7.7 s deserialising worker results); full 114k-row
drain ~72 s; cycle-0 step: prepare 311-334 s, causal scan 93-101 s, forward 15-17 s, loss 22 s,
backward 37-41 s, peak 32 GB; 8 vs 16 threads differ in result hash; journal stack 80 records/s on
3 workers (36 ms CPU/record); raw ingestion under 2 records/s; stacked packet 92,428 tokens at
3,262 rows (24.1 tokens/row), ~114k at 4,096.

## 0. Defect found and fixed this session (not a speed item)

**The first compact prefix would have failed cycle 1 of the Sunday run.** `CompactReader` /
`FrankieCompactReader` had no `verify()` although `context_session.run()` (l.229) and
`NativeForecastLearner.step` (l.297) call `journal.verify(...)`, and `prepared_context_cache._stored_tail`
queried an `entries` table a compact container does not have, so `prime_cache` would have raised at
cache creation. Cycle 0 used the raw prefix, which is why the retained run never hit it. Fixed:
`CompactReader.stored_tail()` (seal) and `CompactReader.verify()` (re-hash every block blob against
the table, re-check the chain to the seal, compare to the caller's expectation; no row decoded), and
the cache dispatches on `stored_tail`. Test `tests/test_compact_prefix_through_cache.py` pushes a
compact prefix through the cache and `verify()` with both readers and refuses a rewritten block.
Identity: FREE (HOST hash moves, as any edit does). **For the architecture reviewer: is a block-level
re-pin an acceptable replacement for the raw reader's full post-consumption re-drain?** The argument:
nothing consumed can change retroactively; what the check exists to catch (a rewritten or extended
file under a live handle) is caught by re-hashing every block and the seal.

## 1. Where the per-cycle hour goes and how it comes out (journals/readers + native)

| # | finding | effect | identity |
|---|---|---|---|
| 1.1 | Three causal-scan drains per cycle (`sunday_native_runtime.py:153`, `native_forecast_learning.py:229`, `native_forecast_refresh.py:107`) recompute `max(ts_event_ns)` over the whole prefix; the prefix receipt already carries that maximum as `source_as_of`, computed by the same verified drain at build time, pinned by sha256 and checked at `prefix()` install | minus 3 drains/cycle, about 68 of the 72 min per 19 cycles (derived) | SEED, new run. **Needs sign-off: runtime re-derivation replaced by a pinned witness.** Test: for all 18 retained prefixes assert the scan equals the receipt once; tamper a receipt copy and the host must refuse at `prefix()` |
| 1.2 | Compact path verifies each row twice: `decode_block` (dumps + sha) then `verified_partition` (loads + decode + dumps + sha). The second re-encode is a tautology on bytes the first just produced | 6.46 to ~4.3 ms/row single-thread; minus 33% worker CPU (derived from the raw floor) | FREE. Test: per-block `pack` equality old vs new; corruption tests unchanged |
| 1.3 | Parent-side deserialisation of full envelopes is the parallel reader's floor (4.4 of 7.7 s). Decoded rows in a block should SHARE their order dicts (id-keyed memo in decode) so each distinct order crosses the process boundary once | proportional to the block's order dedup ratio: ~8x at today's 16-row blocks, ~110x at 160 | FREE. Test: `pack` equality; count transferred bytes |
| 1.4 | The container is 16-row blocks (`journal_stack_execution.py:80`), not the format's 256-row / 32 MB bound; every per-block fixed cost is paid 16x more often and order dedup is ~8x instead of ~110x | fewer round trips (7,129 to ~715 blocks), smaller container (unmeasured) | physical re-pin only; for the block build |
| 1.5 | `journal.verify()` after the forward re-drains the raw prefix a sixth time (cycle 0 only) | minus 1 raw drain on cycle 0 | FREE; the compact form is item 0; the raw form needs the same sign-off as 1.1 |
| 1.6 | `_prepare` drains twice (heap, then `teacher.attach` over every row); `iter_raw` is stateful over all rows so the teacher pass cannot be fed context rows only; seal its output per cycle at prefix-build time (SPEC_PREPARED_SOURCE_ONCE) | prepare 311-334 s to seconds | NATIVE + TEACHER, new run |
| 1.7 | `FrankieCompactReader.entries()` spawns a fresh 15-process pool per drain; each worker imports the package `__init__`, which imports torch | unmeasured; up to minutes over 19 cycles | FREE; measure first |
| 1.8 | `ActualHost` primes the cache only when the controller stage is absent (`run_actual_sunday.py:729`); a RESUMED cycle pays the uncached 300 s `_prepare` inside the step | minus 5 min per resumed cycle | HOST, after Sunday |
| 1.9 | Compact readers duplicate the block-table and seam logic that `compact_source.py` already centralises; unify so every reader has O(1 block) random access (the foundation for tail-only drains) | structural | FREE |

## 2. Ingestion for the block (6.47 M records; 2 TB raw at Sunday's 205 KB/record)

| # | finding | effect | identity |
|---|---|---|---|
| 2.1 | Two fsync'd commits per record (`c15_journal.py:286-305`, DELETE journal mode, exFAT): the measured under-2 records/s is fsync-bound, not CPU-bound; the same code at one commit per 16 rows ran 80 records/s | 41 days to CPU-bound | FREE via an injected batched writer (the `__new__` pattern `source_recovery.py:99` already uses); TEACHER if done inside `EvidenceJournal` |
| 2.2 | Write compact directly from the builder: `CompactWriter.add` needs only `(ordinal, kind, body, digest)`, which the builder has before the sqlite insert; the conformance second pass over the compact container already exists (`finalize_snapshot(storage='compact')`) | the 2 TB raw journal is never written or read; minus the 22 h conversion pass | FREE glue. **Proof: convert the Sunday day both ways, compare all 114,054 rows and the seal `(114054, d8de0394…)`, `state_hash d46ec933…`** |
| 2.3 | Every envelope is packed, canonicalised and dumped TWICE (`body`, then `evidence_hash(envelope)`); `digest = sha256(prefix + body)` is byte-identical and is what every reader already verifies | about halves builder CPU per F_LAST row | TEACHER (`c15_journal.py`), new run; proven by the row-for-row Sunday comparison |
| 2.4 | Builder per record: two `public_dict()` of the same object, two `sorted(levels)` for `order_rank` on every record, `asdict` per resting order in `observe_book` (`vars().copy()` is identical and ~10x cheaper), receipt built and hashed twice | ~2-4x on the dominant F_LAST cost | TEACHER, new run |
| 2.5 | Codec re-parses each body three more times during conversion; pass trees instead | ~2x conversion CPU | FREE |
| 2.6 | Seam correctness (checked, clean for Oct 4-6): every day file ends on F_LAST and the last pre-halt record is F_LAST, so neither the member seams nor the 21:00Z halts split a group. Recorded in the block manifest (`member_seams_close_groups`, `halt_boundaries_close_groups`) | prerequisite | none |
| 2.7 | Session identity must be DECIDED before ingestion: today one `session_id` per member (UTC day file); the intended session is the trading day (22:00Z to 21:00Z). `DChain` resets on session change, so the string is in the bytes | decision | PIN (`mbo_source.py`) if derived from `ts_recv` |
| 2.8 | Scope construction is hard-bound to the Sunday manifest (`selected_source_scope.py`); the block needs `block_source_scope(manifest, expected_hash)` over `manifest['sources']` | prerequisite | FREE |
| 2.9 | Keep the INPUT/APPLIED pair: a hash-only INPUT saves 0.3% bytes and costs a schema version; the pair's real cost is the commit (2.1) | none | n/a |

## 3. Tokens per cycle (Granite packet)

Measured breakdown at 3,262 rows: records 85% (24.1 tokens/row), graph 7.4%, fixed material
~7.5% (grammar, registry, layouts, receipt). Corrections to earlier notes: consecutive Sunday
windows overlap 18-33%, and on the weekday block at hourly cadence they overlap 0%; the request is
one stateless message per cycle, so a **delta packet cannot save anything regardless of cadence**
(rows not re-sent are not in the model's context; prefix caching matches from the start and the
overlap is the tail of one prompt and the head of the next). Drop that item.

| # | finding | tokens/cycle at 4,096 rows | model-facing |
|---|---|---|---|
| 3.1 | `graph` is a pure function of `order_id` (rule at `native_mbo_encoder.py:133-139`); recomputed it reproduces the retained graph exactly. Send a `graph_recipe`, omit the literal | minus 8.6k | yes (grammar states the rule) |
| 3.2 | prices as tick integers (all non-sentinel values divisible by 1e6; 441 sentinel rows) | minus 5.7k | yes |
| 3.3 | drop the model-irrelevant static nodes (registry, layouts, receipt_layout, scope_public), referenced by hash; the critic's references never touch them | minus 2.9k | removal only |
| 3.4 | `action`/`side` as one-letter strings instead of dictionary index vectors | up to 4.1k, unmeasured with the real tokenizer | yes |
| 3.5 | output budget: `remaining_context` is right; the cycle-0 critic under-filled (119 of 38,644 tokens, empty hypotheses, rejected) rather than being cut. The binding number is admission: ~5,100 rows today, ~6,400 after 3.1+3.2 | policy | no |
| 3.6 | the 28 MB principal prompt is the attributed BOSS result block, not the knowledge bundle (249 KB, hash-pinned); the only lever is the frozen receiver emitting it by path+hash | principal only | receiver change |

Together 3.1-3.3 take 24.1 to ~19.4 tokens/row (4,096 rows ≈ 96k input, ~35k output budget), all
inside `codec_code_hash` and the existing exact-inverse gate; one model-side check on the served
Granite follows because the prompt bytes change. Rows per window and cadence remain Greg's
modelling call; the packet is linear in rows.

## 4. Host, runners, wrappers

| # | finding | effect | identity |
|---|---|---|---|
| 4.1 | Restore hashes every present archive member twice per run; batch `git show` (170 spawns) into one `cat-file --batch` | about minus 40% of the 50 s idempotent restore, minus 10 s | FREE |
| 4.2 | SSM runners: tools refetch is inconsistent across runners; `ssm_run_ps1.py` slices output to 6,000 chars (SSM returns 24k); under `$ErrorActionPreference='Stop'` a native command's first stderr line becomes a terminating error (two runs lost their tracebacks this session). One prelude: pinned tools head, `cmd.exe`-owned redirection, `$LASTEXITCODE` to `exit` | no time; stops losing evidence | FREE |
| 4.3 | `git diff --exit-code` in `ActualHost.__init__` rewrites `.git/index` in place (the restore top-up defect); `git diff-index --quiet HEAD` asks the same question without writing. Verify on the restored tree first (sparse checkout, 1,149 skip-worktree files) | correctness | HOST, after Sunday |
| 4.4 | `frankie_host_benchmark_8_16.ps1` still deletes raw-journal sidecars under the restored set; dead since the compact-source host and should not exist | hygiene | FREE |
| 4.5 | four copies of `load_env_file`, eight chunked sha256 helpers, five canonical-JSON encoders (not all byte-identical: consolidate only with recorded-hash tests), two benchmark harnesses sharing ~120 lines, `prefix()` duplicated in the compact subclass (give the lawful method an anchor hook after Sunday) | simplification | FREE / HOST |
| 4.6 | `run_actual_sunday.py`: `source()` 50 lines with seven concerns, `runtime()` 100 lines threading state through three restart branches, `encoding_options()` a 20-line `or` chain; names `outer`/`info`/`t`/`j` reused for different things | readability | HOST, one revision after Sunday |

## 5. Order of work, by measured impact and by when it may land

Before the Sunday run (FREE, output-identical, tested): 0 (done), 1.2, 4.2, 4.4, 4.1.
For the Sunday run itself: declare the thread count (8) in the EC2 wrapper's numeric policy.
After the Sunday run, new run identity, each with its equivalence test: 1.1 (sign-off), 1.6 (spec),
1.8, 4.3, 4.6, 2.3, 2.4.
For the block, before ingestion: 2.7 (decision), 2.8, 2.1, 2.2 (with the Sunday both-ways proof),
1.4, 2.5, then 3.1-3.3 with the model-side check.

## 6. Native context and learner review: the arithmetic corrected

Measured on the workstation with torch 2.9.1+cpu and reconciled against every bracket of the
host benchmark. Corrections to the numbers above:

- On the host a reader drain of the cycle-0 prefix is ~22 s; the rest of each drain is
  CONSUMER-side hashing in the calling thread, which `data_workers` cannot touch:
  `context_session.journal_prefix` (`:60`) computes `evidence_hash(entry)` for every applied row
  (~20 ms/record: ~65 s at cycle 0, ~19 min at cycle 18) and keeps only the last value, which is
  the stored digest the reader already verified. Three drains per step carry it: about 200 of the
  525 s step at cycle 0 and about an hour per step at cycle 18. Value-identical three-line change;
  NATIVE identity (`context_session.py`).
- The "loss 22 s" bracket is `journal.verify()` at `native_forecast_learning.py:297`, a full raw
  re-drain between the label loop and `backward()`; the decoder loops are sub-second.
- The 32 GB peak: `native_mbo_encoder.py:225-230` builds a per-row positional multiplier
  (4.45 MB/row) that autograd saves for backward, 14 GB at 3,262 rows; gated-delta states 5.3 GB;
  twelve full T x T float64 attention maps 4.1 GB (the window masks, it never bounds cost). One
  shared positional tensor sliced per row is bit-identical subject to a `torch.equal` test and
  takes 4,096 rows to ~22 GB. NATIVE identity.
- `evidence_hash` runs `_canon` + `sort_keys` over `pack()` output where both are the identity;
  `canonical_tagged_bytes` is byte-identical, 45 ms to 7 ms per Sunday-sized envelope, every
  digest value unchanged. NATIVE and TEACHER.
- `c15_teacher_r3.py:232` hashes the full evidence row per row and `c15_normalizer.py:150-151`
  recomputes two pure-Python medians over 4,096-deques per column per group (~390 s per attach at
  cycle 18); the teacher's state is an online function of the ordered prefix and is resumable,
  which bounds the attach to the new rows per cycle. TEACHER identity.
- The causal-scan replacement (1.1) is identity-FREE if `PrefixCursor`
  (`online_source_prefix.py:16-27`) carries `source_as_of` and the learner and the critic compare
  integers; `context_session.py` stays untouched. No receipt v2 field is needed for the maxima.
- Identity hashing per step (52 MB state to hex to JSON to sha, 1.2 s a call) is ~4-5 s per cycle.

The prepare-once spec attributes the drain cost to the reader; the dominant term is consumer-side
hashing, and `PreparedSource` leaves the teacher attach at full prefix length unless the teacher
is resumable.

## 7. Status of the cycle-1 fix, for the architecture reviewer

Landed on this branch: `CompactReader.stored_tail()` (seal, O(1)), `CompactReader.verify()`
(re-hash every block blob against the table, re-check the chain to the seal, compare to the
caller's expectation, no row decoded), `CompactReader.append()` refused,
`VerifiedJournalReader.stored_tail()` (entries tail via a fresh read-only connection), and the
cache calls `journal.stored_tail()` as a method with one named fallback for the writer class
`EvidenceJournal` (its file is native-identity; the method lands there with the next identity).
Measurements: `tests/test_compact_prefix_through_cache.py` (prepare then reuse through the cache
with both compact readers, a decode counter proving reuse decodes nothing, refusals for seal count
changed, seal head changed, one rewritten block (by `verify()` and `entries()`), seal table
dropped; the same logical prefix through the raw and both compact readers yields the same envelope
stream and tail) and `tests/test_journal_reader_contract.py` (every reader exposes entries,
verify, stored_tail, close, refuses append, same `verify` signature). 67 tests green with torch on
the workstation. NOT yet done: a dry `prime_cache` on the retained cycle-1 compact prefix on the
host, no training step; first item of the next boot.

Branch facts (measured against `87d42439`): the classroom and ChatGPT recovery branches carry no
diff on the three files; `chatgpt/frankie-lawful-dual-compute-20260915` changes
`verified_journal_reader.py` (+102/-29); `chatgpt/frankie-dual-compute-20260915` changes it too
and DELETES `compact_journal.py`. The fix must be the base the dual-compute branches rebase onto.

## 8. Revised order of work

Identity-free and output-identical, allowed before the Sunday run: 7 (landed), `PrefixCursor`
carrying `source_as_of` with integer checks in the learner and the critic (sign-off: a pinned
witness replaces a runtime re-derivation), 1.2, 4.2, 4.4, 4.1.
For the Sunday run: declare the thread count (8) in the EC2 wrapper's numeric policy.
First declared new identity after Sunday, each with `torch.equal` / `same_preparation` / digest
equality tests: `journal_prefix` hashing only the last entry; the shared positional tensor;
`evidence_hash` via `canonical_tagged_bytes`; the learner's `verify` as a stored-tail check; then
prepare-once and the resumable teacher.
For the block, before ingestion: 2.7 (decision), 2.8, 2.1, 2.2 with the Sunday both-ways proof,
1.4, 2.5; then 3.1-3.3 with the model-side check.
