# Evidence audit and build continuation, 2026-09-14

The audit repairs below are separate from completing the final Frankie build.
Neither an actual Granite inference nor the Sunday comparison has run here.
The owner wants fixes closed first, then a new task to finish the full build.

## Authority and scope

Reused the September 7 FULL_EVIDENCE_HANDOFF, superseding
CLAUDE_TO_CODEX_FULL_EVIDENCE_RULING and NATIVE_MAPPING_BUILD_HANDOFF. Traced
source -> journal -> native context -> forecast and source -> three ledgers ->
fetch -> knowledge/prompt -> causal agent delivery -> completion read-back.
Declared model/teacher compute windows remain distinct from full raw retention;
no window was silently enlarged, truncated, or removed to make tests pass.

The original V4 adapter, S121, Memory A, historical workbook and existing source
evidence remain unchanged. The newer adapter preserves original values beside its
derived normalized fields. No previous ledger is overwritten or regenerated.

## Repairs

| Boundary | Defect and resulting behavior |
| --- | --- |
| Native replay | Receive-clock inversions accepted at ingestion could fail checkpoint completion. Replay preserves the actual order/defects and validates against the authoritative maximum receive watermark. |
| Context and forecast | Cached journal heads could miss physical mutation during forward. Recheck physical evidence before acceptance/publication and validate exported prefixes. |
| Controller identity | Pin the shared Granite runtime implementation as well as its caller so changed runtime bytes cannot reuse a completed generation. |
| Compact context | Repeated DAG references could expand exponentially. Admit against explicit input/depth/node/byte budgets before expansion; reject the whole oversized request. No evidence truncation. |
| Execution ledger | Terminal release now requires the exact independently pinned reflected account snapshot. Future approvals use its recorded frontier. A durable kill marker works even while an injected sender holds the dispatch lock. |
| Source capture | Preserve rtype, original fields, missing/null distinctions and SDK wire bytes. Refuse unsupported JSON types before mutating the book. Protected V4 normalization remains unchanged. |
| Ledger output | Exclusive creation refuses overwrites. Reconciliation hashes the physical bytes and checks size/count; closing flushes and fsyncs. Same-size/count tampering is refused. |
| Fetch and prompt | Verify canonical manifest identity, exact object roster and safe names before downloads. Rehash actual delivered ledger/result bytes and reconstruct the pinned knowledge bundle. Download errors do not expose presigned URLs. |
| Causal delivery | Refuse duplicate/skipped groups. Disk-indexed sidecars let lawful rows pass a future-timestamp row without editing source bytes. Preserve source ordinal within a delivery and exact integer nanoseconds/existing legacy clock semantics. |
| Completion | Close handles on errors/partial reads. Bind actual complete stream and delivery receipts, exact three-file byte/hash witnesses, run/arm identity and terminal withheld-row accounting. PARTIAL cannot be accepted as completed delivered evidence. |
| Agent attribution | Prompt explicitly distinguishes runner calculations from agent evidence and requires attribution of coordinator pointers in confidence_basis. |

The sidecar index reads operator-side bytes before causal delivery; that is not
principal visibility. Future/unknown-clock rows remain explicitly accounted for.
The final drain is terminal evidence and must never be backfilled into an earlier
decision. Receipt verification establishes byte identity/accounting, not proof
that a language model understood a document.

## Verification

- BOSS combined regression: 1,371 passed, one CUDA-only skip, 257.63 seconds.
  Checkpoint dependency tests: 11 passed separately. Two additional execution
  adversarial tests were added afterward; the resulting policy/ledger suite
  passes 73 tests, including process death after durable kill marker creation.
- Compact codec/native dependency suite: 43 passed. AWS inventory: 23 passed.
- Agent raw capture/launch/sink focused suite: 64 passed.
- Causal stream/crosswalk/emitter suite: 218 passed, including the unchanged real
  NativeReplayDriver fixture with disordered sidecar clocks.
- Delivery/knowledge/staging independent review batch: 232 passed; final strict
  staging integrity: 15 passed after the review-discovered run identity repair.
- All changed slices received independent review. Counts overlap and must not be
  added to claim a unique total.

The final stable broad legacy-agent run returned **2,053 passed, 15 failed and
11 errors**, in 171.18 seconds. All changed emitter/staging cases pass: their
stable two-module batch passes 79 tests using real pinned knowledge bytes.
The first broad run's missing-bundle fixtures and concurrent staging fixture
updates have been resolved. Its older count is not the final result.
Unchanged A-memory seed tests reproduce three failures and eleven errors at the
clean starting commit 9006b633: Sunday findings exist without the preceding
October 1 promotion required by the seed builder. Do not invent that promotion,
delete Sunday findings, or weaken Memory A to make the suite green. Resolve the
actual chronological memory source before the Sunday A-memory comparison.
The remaining twelve test failures are Windows Bash/temp-file/quoting/newline
fixture failures. The same four modules at the clean baseline return nine
failures and 41 passes; temporary-directory cleanup failures vary between runs,
so do not claim an identical failing-node count. Bash resolves to the Windows
WSL shim, which misinterprets Windows temporary paths; the knowledge fixture
writes CRLF but expects LF. The full legacy suite is not green. Retained local
logs are agent_final_regression_20260914.log and
baseline_windows_workflows_knowledge_20260914.log in the task's work directory.

## Published implementation checkpoints

BOSS remote branch `codex/boss-full-evidence-20260907`: c51a8020 (physical
evidence/replay), aa10a464 (compact codec), 61b34ee6 (execution policy/outbox),
cc5e6bf1 (AWS inventory). Agent remote branch
`codex/frankie-agent-evidence-fixes-20260914`: d9e7f809 (capture/sinks), fdabc363
(causal delivery), 81d8a24a (byte-bound delivery/completion), 28237baa (real
knowledge fixtures). These are separate published lineages, not a merged final
Frankie deployment. Later documentation commits do not change these test results.

## Build still required

1. Integrate this BOSS lineage with the existing committed-file agent path; they
   currently live on separate branches with different trees. Do not substitute
   another API/calculation runner for the agent session.
2. Wire the compact codec through SDK service/controller with explicit identity,
   inverse checks and actual model capacity acceptance. 95,301 tokens at 512
   repeated-QSV rows is a diagnostic, not arbitrary-QSV/4096-row acceptance.
3. Finish exact model artifact staging/runtime verification and a supervised
   actual Granite integration run. Reuse existing classes and workflow seams;
   the live-run spec is a proposed implementation outline, not an implemented
   launcher or authority to add unrelated infrastructure.
4. Finish actual QSV source/mask/mapping configuration, trained model/decoder and
   empirical calibration bindings, and production throughput acceptance.
5. Finish typed venue adapters, provider observation ingestion and operational
   execution integration. The tested outbox uses synthetic caller-attested data;
   it is not an authenticated broker integration.
6. Resolve the existing A-memory chronological seed discrepancy, then run Sunday
   first with independent findings and comparison afterward. Paired experiment
   orchestration software is built; empirical runs and held-out reveal are not.
7. Reconcile the deferred Claude addendum only after initial-sheet work is
   completed, as the owner instructed. Do not count overlapping fixes twice.

Granite remains required in final Frankie, with actual model calls in integrated
tests. Historical ShadowService names do not reduce that requirement. Self-hosted
AWS is the recorded route; Bedrock is not a mandatory additional component.

## AWS and review documents

Workflow 34871775747 attempt 2 supersedes earlier access-denied observations:
the us-east-1 execution role is visible and the pinned vLLM image resolves. The
target ml.g6e.2xlarge endpoint quota was zero at that check; owner requested two.
Use the private DROP_IN_CODEX.md for resource identifiers and prefix restrictions,
never keys in chat or Git. The inventory correction targets the exact quota and
Hosting price; its existing boss-name endpoint listing is not reconciliation of
future frankie-granite42 deployment resources. No GPU resource was provisioned.

The original Claude R1-R5/O1-O6 review has an implementation or documented
constraint in the predecessor closeout. The September 14 addendum was read for
overlap and remains deferred: C1, C2's interim and C5 overlap completed work; C3/C4
need reconciliation with preserved predecessor edits. The new
CLAUDE_ARCH_REVIEW_NOOA_CONTEXT_RETRIEVAL_20260914.md at 3cfbf5c4 is a review
request, not a returned disposition. Do not treat it as architecture approval.
