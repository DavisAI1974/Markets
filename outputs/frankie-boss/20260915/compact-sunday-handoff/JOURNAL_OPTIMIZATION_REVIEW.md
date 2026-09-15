# Reduction stack review — deployed preparation path

## Standing instruction for additional days

**Reuse this pipeline. For additional days, change the dates and run. Rebuild only when functionality is explicitly added or changed.** Date-specific inputs, state and receipts belong in configuration/manifests; unchanged reducers, readers, CPU controls, checkpoints, probes and publishing must be reused. The current Sunday-specific counts/cutoffs still need one-time configuration parameterization before arbitrary dates are accepted.

## Authority and preservation

Read [NEW_CHAT_HANDOFF.md](NEW_CHAT_HANDOFF.md) first. Repository: DavisAI1974/Markets. Publication branch: codex/journal-reduction-stack-20260915. Runtime checkout remains frozen at 9a8f3f46abaa3d840b07b685010108e0c551b174; the publisher advances the remote branch independently. Do not pull/reset the runtime during execution. Original documents and frozen evidence on E/C are retained as history; this Git continuation supersedes their old live-status claims.

## Layers and actual status

| Layer | Evidence / status |
| --- | --- |
| Model input | Existing stacked_v1 first request929730→92427tokens.38645output tokens remain in131072context. |
| Faster verified reader | Prior3.37x synthetic observation remains historical, not an end-to-end Sunday timing claim. Its exact canonical validator is reused in the new full-envelope compact reader. |
| Exact storage | Prior21.48x sample prototype became a complete compact journal:11700711424→569667584bytes, about20.54x. Every logical record remains. |
| CPU ingestion | Ordered bounded workers decode/check complete envelopes. CPU assignment is capped to actual allocation; local4CPUs yields3workers. Retained Pod has32vCPUs.48is a requested ceiling only. |
| Prefix preparation | Reuses already compressed blocks and re-encodes only the cutoff-crossing block; validates original cutoff digest and complete pairs. Running on actual Sunday evidence. |
| Git retention | Exact page references reuse the archived base journal. First six prefix archives are59970–130275bytes for runtime files50–191MB; they depend on the already stored569.7MBbase and are not standalone compression ratios. |

The reductions apply to separate costs. Do not multiply independent ratios into an unmeasured runtime prediction. CPU count alone does not predict nineteen-cycle latency.

## Correctness and recovery

Five new integration checks passed once in6.399seconds: exact original fields and types, cutoff inside a block, unchanged complete blocks, rejected worker seam corruption, rejected physical-pin mismatch, and CPU/progress behavior. These used fabricated records without model calls or a source replay. Do not repeat passing suites.

Full original envelopes, including order-book observations, reach Frankie. Projection of selected fields is restricted to the separate conformance checker and does not delete stored data. Existing completed-cycle reuse, prepared request recovery, native model/optimizer checkpoints and same-job recovery are unchanged.

The actual prefix publisher verifies each patch by reconstructing its exact target SHA, checks encryption roundtrip, checks Git blob identity and confirms commit publication before reporting success.

## Boundaries

Sustained real-time throughput/backlog acceptance and actual nineteen-cycle model timing are still unproven. The model-input V2 drafts in drafts/ are inactive and unvalidated; no additional V2 token gain is claimed. Do not replace admitted V1 request bytes silently.

Original detailed sample report is preserved at E:/Codex/Frankie-BOSS-20260915/github-parallel/JOURNAL_OPTIMIZATION_REVIEW.md. Original benchmarks and evidence remain intact. Further profiling-only rounds are not authorized; collect operational measurements during the real run.
