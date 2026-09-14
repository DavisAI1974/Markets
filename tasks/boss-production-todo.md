# BOSS remaining build

- [x] Governed QSV artifact-to-native/B1 attachment and retry/restore tests (11 new focused checks)
- [x] Governed original-encoder QSV producer with complete source receipts (e0da21db)
- [ ] Actual QSV source/mask/mapping configuration and production throughput validation
- [x] Native forecast and category-free confidence/selection design documented (SPEC-native-forecast-confidence.md)
- [ ] Empirical calibration bindings and acceptance completed (forecast design, heads and bridge software are built)
- [x] Internal confidence diagnostics without categorical publication labels (39 synthetic tests; G15 empirical acceptance remains open)
- [x] Best comparable candidate selection and durable revisions at every horizon (synthetic software only)
- [x] Explicit all-horizon refresh cadence and durable pre-generation retry intent
- [x] Native gap/path/endogenous-time decoder and immutable query-artifact software (synthetic only)
- [x] Same-forward native B1 producer into the rolling ledger; active-target revisions and retry identity
- [x] Category-free twelve-field draft and standalone disabled-route proof on both control lineages
- [x] Owner-approved versioned nullable confidence field and enabled standalone ledger consumer
- [x] Separate adapter disabled identity proof on both B0/B1 control lineages
- [x] Claude R1-R5 and O2-O6 corrections: historical reads, independent roots, causal anchors/reference, gap reporting and contract edge cases
- [x] Claude O1 bounded synthetic timing harness; production throughput acceptance remains open
- [ ] Production Frankie controller/service wiring and deployment acceptance
- [x] Source conformance and pinned DBN SDK ingestion through native context (e834167e, da0443f8)
- [x] Six B2/C1 teacher columns with preserved C15R2 control (7c46a31b)
- [x] Granite frozen serving, exact native state, failure isolation, real AWS SDK transports (aa1c0cf4, ec64284b, d30110a7, e807488c)
- [ ] Actual pinned Granite deployment/inference and full-context capacity acceptance
- [x] Paired experiment runner/scorer software (7ef81398); empirical run and single reveal remain open
- [x] Deterministic execution policy and durable synthetic outbox/reconciliation (73 focused tests)
- [ ] Provider reconciliation ingestion, venue adapters and operational execution controller
- [x] Lossless compact-context codec and explicit expansion admission bounds
- [ ] Compact-context integration through actual Granite service and controller
- [ ] Integrate BOSS outputs with existing committed-file agent fetch/emit/spawn path
- [x] Rolling increment reviewed; workbook and next-chat handoff completed (remaining production build still open)

Owner-authorized: actual Granite model deployment and integration testing. AWS
credentials were exercised through GitHub secrets. The later workflow 34871775747
attempt 2 found the us-east-1 execution role and resolved the pinned vLLM image;
the target endpoint quota was still zero. Initial AccessDenied observations are
superseded. No model call has run; artifact staging and integrated live testing
remain unbuilt. Workbook-linked decisions specify self-hosted Granite in AWS; Bedrock
is not required. No existing control is removed by this hosting clarification.

Still parked: training, market-data acquisition, held-out/OSS evaluation and live
order submission. Do not reinterpret model-inference authorization as those actions.
Unmeasured: production throughput and provisional context-length acceptance.
