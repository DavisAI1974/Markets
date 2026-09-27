# ROOT worker transport — 2026-09-27

## Receipts and scope
- Retained profile only: read workflow https://github.com/DavisAI1974/Markets/actions/runs/36304811923.
- Source: work/performance/profile-1790494087515792496/pid-55501.json, 88,365 bytes, SHA256 5e4f59496c3af3249bfc0c04b7d096699fda9a9ffa35f92a1e640ff9666c42cb.
- Total sampled active Python weight 17.66; cloudpickle dump leaves across all matching frames 6.08. Book contexts 2.90, evidence 1.58, census 1.54, other native transport contexts 0.06. Some nonblocking samples have incomplete/inconsistent callers; these are context attribution, not measured wall-clock savings. The earlier top-frame report's 34.31% remains historical; this pooled matching-frame reading is 34.43%.
- Progress workflow 36304704078 observed 875270/2032203, failed=0, PID55501 alive, at1790495819.4585981. No new calculation or profile was launched.

## Implemented source changes
- [x] Evidence batches: freeze each row immediately with its own protocol-5 pickle; flush at32rows or1MiB, permit a whole oversized row; two batches in flight plus one filling batch. ROOT commits each returned row in original global order, using the original RowSink.write bytes, ledger ordinal, key-sample ordinal and accounting.
- [x] Census batches: freeze observations immediately, deliver in order, check actual observed count, flush/drain before returning the original census at state boundaries.
- [x] Persistent book partitions: fixed side/price ownership; seed each book once; track old/new affected levels around the unchanged _book_effect. Replace changed level FIFO lists/orders at the next snapshot. Delete old touched levels before installing replacements so moved IDs survive correctly. Resets/TOB clears re-seed complete partitions. All workers acknowledge the same monotonically ordered snapshot generation before the next causal event.
- [x] Native ROOT books remain authoritative and complete. Worker mirrors contain no unique scientific state. Restore both original class methods during checkpoints; retain the byte-identical full-state serializer and queue/replenishment implementation.
- [x] Full-state policy migration accepts only the exact deployed V1 helper hashes and full policy dictionaries, or the current policy. Requires a parent checkpoint, closed groups and no unfinished reconstruction. Retain old/new policy and parent checkpoint in the driver and worker startup receipt.
- [x] Message/byte/timing counters retained in normal driver checkpoint state.
- [x] Static review of add, cancel, modify/move, FIFO priority loss, missing-reference paths, reset/TOB clear, empty books, changing books, immutable row capture, commit ordering, ordinals and checkpoint materialization. In-memory Python3.13 syntax compilation passed. No scientific tests, canaries, comparisons, validators or model calls.
- [x] Fresh read-verified checkpoint handoff at 917,118 records: pause workflow 36305210399; full descriptor read 36305384051. Old PID 55501 and all 14 owned workers exited; files and tails preserved.
- [x] Inactive staging workflow 36305212151 and one resume workflow 36305497169 at immutable runtime 68f2311e3071f24fd63b65134b81861b3246400f. PID 56172, token 099d4eb6-a46d-4b94-a888-f15e55c1ee7e:52022690, generation recovery-03a70711353a433c989b18074d7baacd.
- [x] Restore I/O observation 36305982145: 120,535,908,352 member-ledger bytes copied at 1790497373.0830061; checkpoint member prefix is 231,001,441,265 bytes. This is exact-byte restoration, not new calculation progress.
- [ ] New worker startup receipt and post-change full-state checkpoint.
- [ ] Actual forward throughput evidence. No speedup claimed.

## Shared-memory decision
No shared-memory transport added in this slice. The measured large book dictionaries now stay in workers; replacing their repeated serialization is the direct saving. Rows still require an immutable serialization boundary. Moving the resulting pickle bytes through shared memory would retain that serialization and add ownership/reuse/lifecycle machinery. Reconsider only if normal-run counters establish remaining byte-copy cost. Python primary references: https://docs.python.org/3.13/library/multiprocessing.html#programming-guidelines and https://docs.python.org/3.13/library/multiprocessing.shared_memory.html.

## Deployment and recovery
Transition procedure used: the existing PID/token-bound native-workers pause route and its fresh read-verified full-state checkpoint, preserve every old ledger/tail, stage an immutable checkout, then resume the same calculation root with original binding/authorship. Never run two generations concurrently. Restore/copy cost is material (roughly15minutes for the earlier190GB ledger prefix); no multiplier or net completion-time gain is promised. If continuation refuses, preserve its new generation and use a reviewed forward fix; rollback to the old runtime must use its compatible retained pre-change checkpoint, with all later evidence preserved.

Granite watcher 36304223443 succeeded; authenticated readiness and atomic binding migration are retained in GRANITE_ADOPTION_20260927.md. No new watcher, Pod or inference was started. Actual host configuration builder now includes the retained priming profile (commit f4569cb578af02a79990d660221db352f3ffd793); see GRANITE_PRIMING_BINDING_20260927.md. Actual priming delivery/acknowledgement and all downstream Monday stages remain pending. Orchestrator remains plan-only. Tuesday outcomes remain pending.
