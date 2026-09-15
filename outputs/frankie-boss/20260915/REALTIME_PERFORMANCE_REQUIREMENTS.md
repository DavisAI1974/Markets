# Real-time processing must keep up — owner requirement

Recorded2026-09-15 from the owner's instruction: "make a note about these because we will have to change things so the rt numbers don't bog us down when it's running."

## Required outcome

Before claiming real-time readiness, source ingestion, numerical calculations, journal persistence, context preparation and audit work must sustain the actual declared input load without an ever-growing backlog. A model-input token reduction alone does not satisfy this requirement. The nineteen-cycle Sunday run remains authorized; this document records additional engineering and acceptance work for real-time operation.

Preserve every required record, exact numerical values, causality, recovery evidence and integrity check. Do not make the system appear fast by dropping records, hiding lag, truncating evidence, skipping checks or inventing missing observations. No elapsed cutoff should kill a run while meaningful progress continues.

## Observed bottleneck and available evidence

- Current Sunday input57,027 records becomes114,054 journal entries and an approximately11.7GB journal.
- The final source worker runs two complete legacy verification passes for completion and checkpoint.
- Model-input encoding already reduced929,730→92,427 tokens; that is separate from journal/CPU cost.
- Existing faster verified-reader benchmark:3.37x on a prior synthetic fixture, not Sunday throughput.
- New bounded closed-copy sample:128rows10,748,549bytes; gzip1 gives1,180,249bytes (9.11x), gzip6 gives929,197bytes (11.57x). Observation material contributes approximately91% of sampled bodybytes.
- Exact dictionary representation of repeated orders plus gzip6: three adjacent completed observations777,745→36,200bytes (21.48x combined); direct gzip6 for the same observations59,942bytes. Exact canonical observations reconstructed. This is a small prototype, not a production journal format or a whole-journal ratio.
- Decoder timing on a small sample is too coarse/contended to support a further CPU speedup claim.

## Stack the engineering changes

The owner's explicit direction is to **stack as much as we can**. Treat the list below as composable layers, not competing alternatives or a3.37x stopping point. Keep every compatible layer that proves useful and preserves correctness; measure the combined result.

Correct earlier resource accounting that considered only10x model-input reduction. Include the existing3.37x verified-reader result and measured21.48x storage prototype in the implementation plan and full-system evaluation. They operate at different stages and remain useful together; their ratios are not automatically multiplicative end-to-end. Current parallel runner has not yet integrated those two changes.

1. **Avoid duplicate work:** retain one verified result for an explicitly immutable, physically pinned snapshot and return completion plus checkpoint from that same verified state. Every semantic check still runs. Count/head alone is not a sufficient cache key.
2. **Faster exact decoding:** extend the existing validated reader into missing final-conformance paths while preserving INPUT/APPLIED, scope, prefix, group and checkpoint checks.
3. **Use CPU capacity:** distribute independent envelope checks; retain ordered causal calculations. Give ingestion, calculations and verification explicit worker budgets. Bound queues and memory, account for process-transfer overhead, and reserve capacity for the real-time producer.
4. **Shrink persisted evidence losslessly:** evaluate compressed canonical blocks and exact dictionaries/deltas for repeated full order-book state. Retain exact reconstruction, semantic hashes and legacy-reader compatibility. New physical formats require explicit identities and migration/recovery handling.
5. **Make backpressure visible:** report incoming/processed record rates, queue depth, oldest unprocessed event age, calculation lag, write/flush latency, CPU use per worker, memory and disk headroom. Alerts identify the phase falling behind; do not silently discard work.
6. **Move audits out of the hot path where correctness permits:** use durable incremental commitments/checkpoints and independently audited snapshots; do not rescan all historical evidence for every new real-time number. Crash recovery still validates the exact state being resumed.

## Acceptance before real-time readiness

- Declare the intended input rate and burst shape from actual workload evidence; do not invent a throughput target.
- Measure every relevant phase and end-to-end event-to-result lag, including worst/burst periods and individual slow phases, not only averages.
- Show bounded/recoverable backlog at sustained and burst load, with stated CPU/memory/disk allocation and visible lag alerts.
- Compare each added optimization and the combined stack on identical bounded evidence; prove exact reconstructed bytes/state/hashes and causal outputs. Do not multiply isolated ratios into an unmeasured total claim.
- Exercise meaningful new corruption/recovery/partial-write cases for changed storage or verification boundaries. Do not rerun already-passing suites without a new change or unresolved failure.
- Keep current frozen Sunday code and live processes unchanged until each applicable change is reviewed. Do not add another source day or a smoke inference to obtain performance evidence.

## Status

The isolated GitHub verification job combines compressed private transfer and parallel exact verification. Production compressed/delta journal storage, single-pass final-conformance reuse, and a sustained real-time load acceptance are **not implemented/established** by that job. Track these through implementation, combined measurement, recovery validation and documentation; do not close the work at the first3.37x result.
