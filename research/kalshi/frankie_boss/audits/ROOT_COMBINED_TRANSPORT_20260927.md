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

## Actual checkpoint handoff — 09:20Z

- [x] Pause workflow36308640458 saved/read-verified checkpoint000004 at1,215,705records (59.82%); identified PID56172 and all14owned native workers exited. Pause receipt1270bytes SHA256208f43b0066159483c36b1a138c58e78c8679b81085f67254e4cbf4e13058150. All files/tails preserved.
- [x] Full descriptor read36308965747:10525bytes SHA256fb78159f28f2cafcb88c94276bf0f04007900789fdb3bafda4529e6adbd32a73. Driver state293255540bytes SHA256171d6984a06f5b636a0431504c8cb99e52939a2495c8885751c319ce6c5a6967; finalized=false; Python/cloudpickle and exact predecessor serializer match.
- [x] Frozen ledger prefixes: member312183215696bytes/906982rows SHA256786f05de4b8a57375e1bfc461350ca0211562587d453464d2729f33e8ae3166e; lifecycle6071380890bytes/6568550rows SHA2569f3979ee62fa0f29c71e98681a78fc98e4cf8129b741765d0cc00d597ef3218d; legacy766552961bytes/583556rows SHA2562896256c1b69d7c3cb0d524a6840071f08f85c65a1486d7c01e10bd3d1bb4ff0.
- [x] Immutable runtime293113435a8fdf7bd5566f2652e1a1f7a1734c35 staged by36308610841; source pack589523154bytes/3676files SHA25629eab7876dbc38c6db3857a02aeabbda1e0d87f564ab48f7c5a79234cbf44a80; intent85e793aba0f28c823071c93360b0ab9deec91234c959c18249eb7ec9522f51c0. CODE_ROOT=/opt/frankie-box/code/293113435a8fdf7bd5566f2652e1a1f7a1734c35-36308610841-1/markets. Existing workflow serial lock required pause before staging; staging did not overlap the active calculation.
- [x] One resume dispatched in36309059667 on codex/frankie-shared-ledger-runtime-2931134, from recovery-03a70711353a433c989b18074d7baacd/checkpoints/checkpoint-000004.json, same root/authorship/binding/48readers. No reconstruction flag.
- [ ] Restored-state and activated worker receipts still pending; do not launch another resume. First probe36309073512 read the old exited process status during startup, not a newly activated worker receipt.
