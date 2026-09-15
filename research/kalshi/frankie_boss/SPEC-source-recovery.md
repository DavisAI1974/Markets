# Explicit interrupted C15 source recovery

`source_recovery.rehydrate_source(scope, parent_path, destination_path,
expected_parent={count, head_hash, sha256}, event=None)` returns a recovered
builder and an explicit parent-bound receipt. The failed writer must already be
stopped. The original database and its failure receipt remain unchanged.

Recovery validates the original physical hash, full journal hash chain and
alternating INPUT/APPLIED sequence. FAILED entries are refused, not removed.
It creates an exclusive SQLite backup retaining the exact existing envelopes.
The destination uses WAL with synchronous FULL; callers retain WAL sidecars
while it is live and should still avoid long reader snapshots during ingestion.

The existing adapter rebuilds in-memory source state from retained INPUTs.
Every generated INPUT and APPLIED envelope must match the retained bytes exactly.
Existing entries are never appended again. If the final original entry is a
pending INPUT, its matching APPLIED is appended once after all prior comparisons
pass. No principal calls or model forwards occur during this source-state replay.
The receipt distinguishes replayed completed records from the newly completed
pending input and records the new cursor and journal head.

The execution host independently matches retained INPUT raw mappings to the
same pinned full DBN stream before rehydration. It then continues source
ingestion from the returned cursor, retaining all remaining source records.
The normal source-conformance completion and checkpoint verification still run.

Focused new tests cover pending-input recovery, WAL commit under an existing
reader, FAILED-tail refusal, changed parent pin refusal, and rejection of
self-consistent retained evidence whose calculations do not reproduce exactly.
