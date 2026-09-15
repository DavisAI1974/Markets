# Real-time performance requirements — current implementation status

## Standing instruction for additional days

**Reuse this pipeline. For additional days, change the dates and run. Rebuild only when functionality is explicitly added or changed.** Date-specific inputs, state and receipts belong in configuration/manifests; unchanged reducers, readers, CPU controls, checkpoints, probes and publishing must be reused. The current Sunday-specific counts/cutoffs still need one-time configuration parameterization before arbitrary dates are accepted.

## Authority and preservation

Read [NEW_CHAT_HANDOFF.md](NEW_CHAT_HANDOFF.md) first. Repository: DavisAI1974/Markets. Publication branch: codex/journal-reduction-stack-20260915. Runtime checkout remains frozen at 9a8f3f46abaa3d840b07b685010108e0c551b174; the publisher advances the remote branch independently. Do not pull/reset the runtime during execution. Original documents and frozen evidence on E/C are retained as history; this Git continuation supersedes their old live-status claims.

## Required outcome

Ingestion, calculations, context preparation, evidence persistence and audit work must sustain the actual input load with bounded backlog and visible event-to-result lag. Preserve exact numbers, source records, causal order, integrity checks and recovery evidence. Do not hide latency by dropping records or reducing audit coverage. No arbitrary elapsed cutoff while meaningful progress continues.

## Implemented components

- Exact order sharing and gzip block storage, with complete journal conformance evidence.
- Faster exact canonical decoding.
- Bounded ordered CPU workers and explicit allocation-aware budgets.
- Full-envelope compact reader in Frankie's Sunday host; no removal of its observation fields.
- Compressed prefix block reuse, exact physical cutoffs and original source anchors.
- Percentage probes, queue/rate/worker counters and preserved operation journals.
- Existing completed-cycle and model/optimizer save points; durable same-job recovery.
- Authenticated Git preservation of completed prefixes using exact references to the existing base journal.

## Acceptance still required during actual operation

1. Declare actual input rate and burst shape from workload evidence.
2. Observe sustained throughput, oldest queued event age, event-to-result lag and backlog recovery under that load.
3. Record CPU allocation, memory/disk headroom, transfer cost and slow phases, including ordered calculations and persistence.
4. Retain per-stage correctness/recovery evidence and honest incomplete/failure state.
5. Distinguish a model-input token reduction, a storage ratio and a worker-reader result from an end-to-end gain.

Do not invent new source days, rerun passing tests or schedule extra smoke inference for these measurements. Use the authorized actual workload. Completed source conversion and currently advancing Sunday prefixes do not by themselves establish real-time readiness.

## CPU facts and portable reuse

Local host4logicalCPUs ->3ingestion workers with consumer capacity reserved. Retained Pod32includedvCPUs; no48CPU purchase or resize performed. The worker ceiling can use a larger verified allocation when available, without rebuilding the reducer. CPU decoding and ordered model/learning cycles are different phases.

Historical requirement text and original measurements are preserved at E:/Codex/Frankie-BOSS-20260915/github-parallel/REALTIME_PERFORMANCE_REQUIREMENTS.md.
