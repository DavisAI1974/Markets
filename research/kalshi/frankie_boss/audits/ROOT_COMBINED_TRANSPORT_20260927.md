# ROOT combined transport and frozen ledger source package — 2026-09-27

Status: implemented and statically reviewed; not yet staged or activated. Canonical ROOT remains runtime 68f2311e3071f24fd63b65134b81861b3246400f, PID 56172, workflow 36305497169.

## Actual basis

Read-only progress workflow 36308440564 observed 1,166,757 / 2,032,203 records (57.41%), failed=0, alive, at 1790500144.804435 (09:09Z). Four full checkpoints saved/read_verified; latest checkpoint-000003.json. Interval since workflow 36307444156: 109.84 records/s over 1,128.63 seconds, including checkpoint overhead. The earlier short post-fix interval was 120.265 records/s versus the earlier 64.74; these are different real intervals, not a controlled comparison.

Retained post-fix profile 36306860732 and readers 36306968197 / 36306996610 identify duplicate evidence/census freezing and output receive work. Existing worker CPU time was 75.54 CPU-seconds over 30 seconds. Profile pins and phase-one receipts remain in ROOT_WORKER_TRANSPORT_ACTIVATION_20260927.md.

## Implemented changes

1. Inside the exact pinned NativeCalculationRun.note_member_row call, census freezes the member row once and evidence consumes that same immutable protocol-5 pickle. The original method is still invoked; scoped object identity, one offer/use, nonnesting and removal of the wrapper at every full-state checkpoint are enforced. Unrelated rows are frozen independently. Census reads its input without mutating it.
2. Two existing evidence encoders run the unchanged pinned RowSink.write. Encoded bytes go to producer-owned shared-memory slots. ROOT receives offsets/accounting, commits and hashes exact views in ledger order, and only then offers the next batch. The producer owns unlink, attach uses Python 3.13 track=False, and no live view crosses slot reuse. Output is not capped.
3. Full checkpoints retain immutable ordered ledger segments with explicit byte extents, logical bytes and original SHA256. Resume reads/hashes those exact bytes with bounded parallel prefetch; it does not physically rewrite old prefixes before calculation starts. A new generation appends only new bytes to new files. Original files and post-checkpoint tails remain untouched.
4. Three independent I/O workers assemble ordinary complete ledger files while calculation continues. They verify prefix and whole-file SHA256 and counts, fsync, and atomically replace only the same fresh zero-byte placeholder. Finalization waits for these actual receipts before using unchanged pinned reconciliation. Original segments remain retained. These workers are pinned to reserved CPU0; the 15 native/evidence processes remain on CPUs1–15.

The prefix still must be read to restore ordered SHA256 state. Physical whole-file copying still occurs in the background for existing downstream readers; this package removes it from the startup critical path, not from all I/O. No claim of a combined speedup has been made.

## Review and transition

The exact candidate code in 19e2da01e6b3804d29550e0aa054a2cf66ba3a94 passed Python syntax compilation without importing or running calculators. Review follow-up fdc6328f97632a27f273ce1cd82481479697ab24 retains completed ledger-transfer receipts and completes cleanup of its own I/O children. Review covered pinned member/census/RowSink methods; checkpoint external bindings and barrier order; shared-memory ownership/reuse; ordered extent restoration; append freeze and final publication; finalizer writes; closed sinks; and the existing PID-token pause route, which discovers all owned spawn children without assuming a fixed count.

Only the exact phase-one checkpoint serializer/policies are accepted as predecessors; current Python/cloudpickle and complete producer/source identity must match. New checkpoints include the ledger-storage implementation hash. Complete driver, census and book state remain checkpointed; incomplete background assemblies contain no unique state and are not checkpoint dependencies.

- [x] Implementation source and manual static review.
- [x] Candidate syntax compilation; final changed bytes also compiled successfully at fdc6328f97632a27f273ce1cd82481479697ab24.
- [ ] Immutable inactive staging receipt.
- [ ] Fresh read-verified full checkpoint and identified old ROOT/worker exit.
- [ ] One canonical resume and restored ledger/cursor receipt.
- [ ] New runtime worker receipt, forward progress and post-activation full checkpoint.
- [ ] Actual combined throughput measurement.

No extra scientific test, canary, comparison calculation, model inference, ingestion replay, infrastructure stop, bootstrap change, agent delegation or orchestration was introduced. Granite's retained priming binding remains configured but actual package delivery and acknowledgement are pending in the real Monday sequence. All historical sections/hashes, slots and producer groups remain required.
