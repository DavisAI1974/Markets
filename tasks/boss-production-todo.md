# BOSS remaining build

- [x] Governed QSV artifact-to-native/B1 attachment and retry/restore tests (11 new focused checks)
- [x] Governed original-encoder QSV producer with complete source receipts (e0da21db)
- [ ] Actual QSV source/mask/mapping configuration and production throughput validation
- [x] Native forecast and category-free confidence/selection design documented (SPEC-native-forecast-confidence.md)
- [x] Pinned native/B1, decoder, source/session/QSV/calibration configuration loader and runtime assembly (5f18fa32; 131 selected checks)
- [ ] Actual fitted artifacts, production configuration and empirical calibration acceptance
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
- [x] Existing controller/service joined by verified hosted coordinator and bounded CI cleanup (29f505b2)
- [ ] Actual hosted runtime/controller acceptance and real-environment operation
- [x] Source conformance and pinned DBN SDK ingestion through native context (e834167e, da0443f8)
- [x] Six B2/C1 teacher columns with preserved C15R2 control (7c46a31b)
- [x] Granite frozen serving, exact native state, failure isolation, real AWS SDK transports (aa1c0cf4, ec64284b, d30110a7, e807488c)
- [ ] Actual pinned Granite deployment/inference and full-context capacity acceptance
- [x] Paired experiment runner/scorer software (7ef81398); empirical run and single reveal remain open
- [x] Deterministic execution policy and durable synthetic outbox/reconciliation (73 focused tests)
- [x] Typed Kalshi/tastytrade adapters with documented provider parsing and fake-transport reconciliation (f1fffd23; 172 passes)
- [x] Operational execution controller with pinned account/reflection evidence and durable receipts (bc18611d; 215 selected execution checks)
- [ ] Authenticated transport/provider/account facts, heartbeat/recovery and cancel/flatten operation
- [x] Lossless compact-context codec and explicit expansion admission bounds
- [x] Compact-context service/controller routing software; actual model acceptance tracked separately
- [x] Committed-file BOSS exporter and separate receiver protocol (receiver 2b4bae18; recorded 2,127 passes)
- [ ] Actual source mapping and configured agent operation with attributed BOSS/Granite input
- [x] Claude Granite contract imported and corrected; original 44df4aa7 retained as provenance
- [x] Preserve distinct legacy 11-field and additive BOSS 12-field seams with unchanged protected prompts
- [x] A66 static authority map and writer-collision checks; no runtime arbitration
- [x] Reconcile historical workbook rows and new teacher/Claude material in separate reports (original workbook unchanged)
- [x] Combined derivative workbook through 5f18fa32 with original historical sheets preserved and Claude/ChatGPT crosswalk
- [x] Rolling increment reviewed; workbook and next-chat handoff completed (remaining production build still open)

## Current integration status - September 14 continuation

Granite model/bootstrap staging completed successfully (34901570054/34902805329).
Coordinator software 29f505b2 joins exact tokenizer admission, startup/resource
verification, real controller invocation and finally/CI cleanup. First real hosted
attempt 34905678210 failed at tokenizer return-shape admission before resource
creation. Fix 3e0a01ed was independently reviewed and verified with the actual
pinned tokenizer: 2,284 complete input IDs. Corrected run 34906771361 is in progress;
no successful inference is claimed yet.
Execution adapters are integrated at f1fffd23 after independent review and 172
passing tests. Reviewed production artifact/configuration bindings are integrated
at 5f18fa32 (131 selected checks). Execution controller bc18611d passed 215 selected
checks, including failure retention and independent kill on inaccessible state.
Authentication/transport implementation is in progress; no provider orders were sent.

The user selected `attributed_input`: Frankie sees clearly attributed BOSS/Granite
input while working. Finish the build before launching Sunday. Source recovery is
preparation only; no rerun is scheduled. The old task completed its derivative
workbook through 993298d5/receiver2b4bae18. The current task's combined workbook
preserves its eight historical sheets, tables, chart and scores and adds current
status through 5f18fa32 plus the source crosswalk. Later code/results require a
subsequent snapshot update. The original workbook remains unchanged.

## Historical baseline below (superseded where current evidence above differs)

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

Current closeout: research/kalshi/frankie_boss/CONTINUATION_HANDOFF_20260914.md.
Agent branch 996d121c records 2,082 passing tests and preserves distinct current
carry versus frozen Sunday prior. BOSS de27bb26's negative-reference repair has
83 focused passing tests. These are separate lineages, not a fully integrated
Frankie result. C32/D6/D7 distillation rows are conditional proposals, not newly
accepted production components. Earlier Claude C3/C4 work remains deferred until
the initial-sheet work is complete.
