# SPEC: prepared context cache (prepare once, reuse exactly, in process)

Date: 2026-09-15. Claude slice on `codex/full-frankie-boss-connection-20260915` @ e9d1945b.
Module: `research/kalshi/frankie_boss/prepared_context_cache.py`. Tests: `tests/test_prepared_context_cache.py`.
Host integration is in the current task's `work/run_actual_sunday.py`; it primes before readiness and restores the original preparation method before learning or a cycle change.

## Problem

`ContextSessionRunner._prepare(as_of, through_cursor)` scans and verifies the journal prefix, encodes the
native context, checks the inverse reconstruction and attaches the teacher. The actual first-cutoff
preparation took about 990 s. The native forecast path (`native_forecast_refresh`, `native_forecast_learning`),
the critic path (`sunday_native_runtime.prepare_critic_request`) and the controllers each call `_prepare`
again for the same cutoff, so the Pod window pays that cost repeatedly.

## API

```
prepare_context_cache(context, *, as_of, through_cursor,
                      expected_source_checkpoint,   # {'count': int, 'head_hash': sha256}
                      expected_model_hash,          # context._model_hash() the host trusts
                      expected_teacher_binding,     # context.teacher.binding, or None without a teacher
                      checkpoint_hash,              # BossTrainingCheckpoint.checkpoint_hash at preparation
                      current_checkpoint_hash)      # callable returning the live checkpoint hash
    -> PreparedContextCache

cache.prepare(as_of, through_cursor) -> (tokens, info, input_hash, teacher, rows)   # independent copies
cache.receipt                        -> dict (independent copy)
cache.close()                        -> invalidates further access; idempotent; also a context manager
```

`PreparedContextCache` is the class behind the factory. `own(value)` (detached tensor clones, fresh
containers, `copy.deepcopy` for other objects such as `DipoleTarget`) and `same_preparation(a, b)` (exact
structural equality including tensor bits) are exported for hosts and tests.

## Creation

1. Argument validation (integer cutoff, sha256 digests, callable checkpoint hash).
2. Cheap identity checks BEFORE the expensive preparation: bindings snapshot, builder not failed, cursor
   inside the applied journal, stored journal tail equals the trusted checkpoint, handle tail equals it,
   `context._model_hash() == expected_model_hash`, teacher presence and `teacher.binding` equal
   `expected_teacher_binding`, QSV digest equals its trusted identity, `current_checkpoint_hash() ==
   checkpoint_hash`. A wrong expectation costs no preparation.
3. `context._prepare(as_of, through_cursor)` exactly once. Any exception propagates; nothing is cached.
4. Shape checks on the tuple; `info['as_of']`, `info['t_ctx']` and `info['teacher_binding']` must agree with
   the bound cutoff, context length and teacher.
5. The full tuple is retained through `own()`: every token tensor is a detached clone, `info`, `rows` and the
   teacher attachment (including `DipoleTarget` tensors) are independent copies. The tuple `_prepare` returned
   is not the cache's storage; mutating it afterwards changes nothing served.
6. The identity checks run again after the preparation, because the preparation itself may have taken long.

## Bindings (all must hold on every `prepare` call)

`as_of`, `through_cursor`, resolved journal path, trusted source checkpoint `{count, head_hash}`, scope kind,
scope genesis hash, `scope_id`, `builder.chain.next_cursor`, entity, `t_ctx`, model hash (weights, config,
registry, QSV ablation flag, recurrence config and the pinned code files, via `context._model_hash()`), teacher
class and `teacher.binding` (which hashes the candidate, the initial normalizer export and the teacher code),
QSV expected hash, and the training checkpoint hash. The receipt carries these under `bindings` and their
evidence hash under `bindings_hash`.

## Reuse

`prepare(as_of, through_cursor)` refuses a different cutoff, then re-runs every check above, then returns
`own()` copies. Source change detection uses the STORED tail (one `SELECT ... ORDER BY ordinal DESC LIMIT 1`
through a fresh read-only SQLite connection opened from `journal.path` and closed immediately) plus the handle's cached tail; no decoded journal scan and no `entries()` call. This supports VerifiedJournalReader without exposing its private connection.
A second handle appending to the same file is detected even though the builder handle's cached `count` does
not move. Nothing is ever recomputed: a changed identity is a `ValueError`, and the caller must build a new
cache after re-establishing the identities it wants.

## What this does not do

No model forward, inference, training, service or Pod call. No persistence: nothing is written and nothing is
loaded from `BOSS_ACTUAL_CRITIC_INPUT_V1` or any serialized request (that request does not contain the complete
native preparation). It does not replace downstream source verification: the run, refresh, learning and export
paths still call `journal.verify` / `journal_prefix` on their own, and those calls are unchanged.

## Test results (this slice only, run once)

`PYTHONPATH=".;research/kalshi/frankie_boss;research/kalshi/frankie_boss/tests"`
`python -m pytest research/kalshi/frankie_boss/tests/test_prepared_context_cache.py -q` -> **8 passed** (7.15 s).
No existing suite was rerun; no smoke runs, retained database reads, source replays, cloud/Pod actions.

Seams: one preparation across three reuses with every returned tuple equal to a direct `_prepare` result
(tensors by bits, `pack` equality for info and rows, teacher attachment hash); mutation of returned tensors,
dicts, lists and teacher targets, and of the tuple `_prepare` itself returned, does not reach later reuse;
cutoff, training checkpoint, model weight, teacher, `t_ctx` and entity changes refused with `_prepare` still
called once; a second-handle append detected from the stored tail with `entries()` patched to fail; a valid
later suffix through the builder refused; wrong expectations refused before any preparation; a teacherless
context served with `teacher=None`; a failing preparation (future receive time, synthetic exception) caches
nothing and a later creation prepares again; use after close refused, close idempotent.

## Integration notes (for Codex; nothing below is done)

- Build the cache once before the Pod starts, right after the training checkpoint is opened or restored:
  `checkpoint_hash=checkpoint.checkpoint_hash`, `current_checkpoint_hash=lambda: checkpoint.checkpoint_hash`,
  `expected_source_checkpoint=dict(count=builder.journal.count, head_hash=builder.journal.head_hash)` from the
  trusted source receipt, `expected_model_hash=identity['native_hash']`,
  `expected_teacher_binding=identity['teacher_binding']`.
- Consumers that call `context._prepare(as_of, cursor)` (`prepare_critic_request`, `NativeForecastRefresh`,
  `NativeForecastLearner.step`, the controllers) can take `cache.prepare(as_of, cursor)` instead for the bound
  cutoff. Their own `journal_prefix` / `journal.verify` calls stay as they are (requirement 6).
- After `apply_completed` advances the checkpoint the cache refuses by design (`training checkpoint advanced`);
  build a new one for the next request. The same holds after any weight change.
- Memory: the cache holds one full preparation (tokens on the model device, teacher targets, context rows).
  For `t_ctx=4096` with the Sunday registry this is bounded by the same tuple `_prepare` already returns.
- Thread-safe for concurrent `prepare` calls (one lock); each caller receives its own copies.

## Unresolved limitations

- Identity checks cost a `context._model_hash()` per reuse (hashes every weight tensor and reads six code
  files). `run()` already does this twice per call; if it matters at Sunday scale, the host can pass a cheaper
  callable in a later revision, but this slice keeps the existing definition of model identity.
- `teacher.binding` re-exports the normalizer on every check; for `NormalizerR3` with `n_norm=4096` that is a
  small export, not a scan.
- Stored-tail detection cannot see a writer that rewrote earlier rows in place while keeping the tail; the
  downstream `journal.verify` in the consumer paths remains the full-integrity check (requirement 6).
- Parameter and buffer device identities are pinned. Moving the model after preparation is rejected before reading weights or returning cached tensors; rebuild the cache for a new device.

## Original Claude slice blob hashes (before integration repairs)

- prepared_context_cache.py db9e78b32f8863d8d5df1fca69eb40ccef981dc9
- tests/test_prepared_context_cache.py d8aa65c368eddbffb2f863575b606e8e396c5490

## Integration repair validation

Three new targeted tests use a real VerifiedJournalReader, reject CPU-to-meta model movement before model hashing, and distinguish signed zero and NaN payload bits through raw contiguous uint8 tensor bytes. The original eight tests were not repeated. A separate new host seam proves the original `_prepare` is restored before learning and accepts a later cutoff after the checkpoint changes. Cache close also runs on cycle release, source-view change, and host exit.
