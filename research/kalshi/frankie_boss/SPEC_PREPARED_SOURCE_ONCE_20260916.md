# Spec: prepare the source once per cycle (the per-cycle time fix)

Status: design, 2026-09-16. Not built. Companion to `compact_source.py` (built, tested, proven on
the real data with the raw journal hidden), which is the foundation this reuses.

## The measurement that motivates it

Run 2 of the direct harness on the Sunday tree (sheet 1.6): identity stack 35 s, `_prepare` 531 s,
causal scan 162 s, all single-threaded Python, before any tensor work. Reading the code shows what
those seconds are: full drains of the cycle's prefix journal, each drain decoding and verifying
every row (JSON parse, tagged decode, canonical re-encode, SHA-256, pair repack):

| where | drain | why |
|---|---|---|
| `ContextSessionRunner._prepare` | 1 | context selection: heap of the last `t_ctx` entity rows by receive time |
| `ContextSessionRunner._prepare` | 2 | `teacher.attach(journal_prefix(...))` streams every row again |
| `sunday_native_runtime.prepare_critic_request` | 3 | `ts_event_ns > source_as_of` scan over the prefix |
| `NativeForecastLearner.step` | 4 | `ts_event_ns > event_cutoff_ns` scan over the prefix |
| `ContextSessionRunner.export` | 5 | re-drain only to assert the journal is unchanged |

The cache (`prepared_context_cache.py`) removes the second `_prepare` inside a process but is bound
to `checkpoint_hash`, and drains 3, 4 and 5 sit outside it. So one cycle drains its prefix about
five times, and the prefix grows from 6.5k rows (cycle 0) to 114k rows (cycle 18). The drain
profile on the host (`operations/profile_journal_drain.py`, results in the session handoff) gives
the per-row cost on the r7i.4xlarge; the arithmetic below uses it.

## What a drain actually produces, and where else it already exists

| product | derivable without a drain from |
|---|---|
| chain integrity of the prefix (every row hashed, every `previous_hash` checked) | the sealed prefix container: per-block sha256 + block chain + seal `(count, head)` equal to the receipt; `CompactSource` verifies the block table at open in milliseconds and decodes only blocks it reads |
| the `t_ctx` context cursors | `prefix-NN-packet-seed.json` (`context_cursors`, `derivable: true`, sealed for cycles 1-18) |
| the context rows themselves | `CompactSource.rows(first, last)` over the ordinals of those cursors: the last 4,096 entity rows live in the tail blocks, roughly 256 blocks of 7,095 for cycle 18 |
| `prefix_rows`, `entity_rows`, `other_entity_rows` | one counted pass, sealed into the prefix receipt at prefix-build time (the builder already drains once to verify) |
| `journal_prefix_hash`, `journal_entries` | the receipt's `journal_head_hash`, `journal_count` |
| `max ts_recv_ns`, `max ts_event_ns` over the prefix (drains 3 and 4) | already computed by the prefix builder (`_verify_pairs` returns `as_of`, `source_as_of`); the scans become two integer comparisons against the receipt |
| teacher attachment (drain 2) | `iter_raw` is stateful over ALL rows (group deques, origins, machines), so it cannot be fed context rows only; it must run once, and its output (`attachment_hash`, rows) sealed per cycle |
| export's re-drain (drain 5) | the stored tail check `_stored_tail`, as the cache already does |

## Design

1. **Prefix receipt v2** (built once, at prefix-build time, by the pass that already drains): adds
   `prefix_rows`, `entity_rows` per entity, `max_receive_ns`, `max_event_ns`, and the sealed
   teacher attachment `{attachment_hash, rows, processed_records}` for the bound teacher identity.
   Everything in it is a function of (prefix bytes, entity, t_ctx, teacher binding), none of it of
   model weights. `build_remaining_sunday_prefixes.py` emits it in its single pass (Q4 of the
   sheet: one pass, 18 receipts).
2. **`PreparedSource`** (new module): opens the prefix as a `CompactSource`-style verified block
   table, takes the seed's cursors, reads the covering tail blocks, reconstructs exactly the
   `(tokens, info, input_hash, teacher, context)` tuple `_prepare` returns. `info` fields come from
   the receipt where the table above says so.
3. **Equivalence is the test, not the argument.** On synthetic journals (fixture + `CompactWriter`
   + `snapshot_compact_prefix`), run the lawful `_prepare` and `PreparedSource` and assert
   `prepared_context_cache.same_preparation(...)` on the full tuple, including `input_hash`. Also
   on the real cycle-1 prefix on the host, once, read-only: same `input_hash` as the retained
   `host-context-cache.c15.json` for that cycle if one exists, else as a fresh lawful `_prepare`.
4. **Cache key without weights** (item G of the sheet): `PreparedContextCache` gains a mode whose
   identity excludes `checkpoint_hash` and `model_hash`; the model identity is recorded in a
   separate model receipt at the moment of use. `NativeForecastLearner.step` and
   `prepare_critic_request` then consume the same prepared tuple, and the two causal scans read
   the receipt maxima.
5. **Identity declaration.** `context_session.py` is inside `_model_hash()`'s code set and the
   teacher binding hashes `c15_teacher*.py`; any change there is a new native identity. This is
   for a NEW run and must be declared as such (sheet 1.6, consequence (c)). The retained cycle-0
   feedback stays bound to the lawful tree; the benchmark on it keeps using the lawful path.

## Expected effect (to be re-measured, not promised)

Per cycle: five drains of N rows become one verified-table open plus about 256 decoded blocks,
independent of N. With the host's measured per-row and per-block costs the 19-cycle preparation
total falls from hours to minutes; the exact figure goes in the handoff after the profile.

## Sequence, smallest reviewable step first

1. Receipt v2 fields emitted by the prefix builder, with the drain that already exists (no
   consumer yet). 2. `PreparedSource` + equivalence tests on synthetic journals. 3. The two causal
   scans read receipt maxima (a one-line consumer each). 4. Cache key without weights. 5. Wire the
   learner and the critic preparation to the prepared tuple. Each step keeps the lawful path
   available under a flag until the equivalence test has run on the real prefixes.
