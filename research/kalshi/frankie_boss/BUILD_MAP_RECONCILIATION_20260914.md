# Historical workbook reconciliation — 2026-09-14

Later implementation status is recorded in SESSION_CLOSEOUT_20260914.md. This
historical row audit is preserved; its then-pending compact route, attachment
software, contract and staging have advanced as documented in that closeout.

Read-only reconciliation. No workbook, repository source, model, provider, or test run changed. Spreadsheet skill applied; bundled Python ZIP/XML extraction used to inspect exact worksheet cells. This file is a build inventory, not new authorization for training, acquisition, held-out reveal, or orders.

## Evidence and precedence

- Workbook: `work/Markets-initial-build/research/kalshi/frankie_boss/artifacts/Frankie_BOSS_Build_Plan_R3_20260914_Closeout.xlsx`. SHA-256 `8862589effeee8ccb745dba6fe97a270921571c5524bd8d1b98df04f03817b23`, matching `CLOSEOUT_VERIFICATION_20260914.md`. Eight sheets inspected. It deliberately records the older `ccc7159d` software checkpoint, not current completion.
- BOSS code/tasks inspected at `f0127bc46231958828b442e93e7c0a44ef39c04c` in `Markets-initial-build`. Principal status sources: `tasks/boss-production-todo.md`, `SPEC-frankie-controller.md`, `SPEC-qsv-producer.md`, `SPEC-c15-teacher-r3.md`, `SPEC-execution-controls.md`, `SPEC-experiment-runner.md`, `SPEC-granite-context-compact.md`, `EVIDENCE_AUDIT_CLOSEOUT_20260914.md`.
- Agent lineage independently advanced to `996d121cb4b8f723c28c5eb61772fed6719c9c14`, verified from `Markets-agent-audit`. Its latest `research/kalshi/frankie_raw_mbo_benchmark/EVIDENCE_AUDIT_CLOSEOUT_20260914.md` supersedes the prior baseline-failure narrative: 2,082 tests passed across two disjoint batches, no failures/errors/skips. This is reported committed evidence, not a new run here and not merged BOSS acceptance.
- The refreshed agent seed preserves 44 prior VERIFIED findings and adds 18 Sunday findings as NEW, following the owner's explicit removal of the earlier-roster prerequisite. October 1 remains MISSING. Current seed SHA `b814bb58f03d506f1643a162ff0ca1e94e17a7f8e90d533d844e86b1995b4f07` is **not** the frozen historical Sunday prior SHA `4a47b09d5b19a9165c570f9432d2f3190a657843009536d5dad9a6bd99d83f4a`. Do not substitute the refreshed carry into the historical comparison.
- Earlier review closure: `CLAUDE_REVIEW_FIXES_HANDOFF_20260914.md`; deferred consumer changes: `ADDENDUM_WORK_TRANSFER_20260914.md`. New source: `C:/Users/A/Downloads/CLAUDE_REVIEW_ADDENDUM_230c648_2b44b4e_20260914.md`, also inside `teacherfiles.zip/claude_session_20260914_outputs.zip`, together with the original forecast review and the returned architecture ruling.
- New architecture ruling is `CLAUDE_ARCH_RULING_NOOA_CONTEXT_RETRIEVAL_20260914.md` in that nested archive. It is distinct from the repository's earlier architecture **request**. Root owns its application. The byte-distillation note explicitly presents placement/opinion and proposed rows, not completed implementation.

Statuses below mean **software built**, **integration pending**, or **empirical/external pending**. A software completion never passes a production gate by itself. Preserve historical scores; do not recalculate readiness percentages from test counts.

## Exact component rows

Cells `G` hold status, `D/F` current capability, and `H` next work. The following are proposed corrections in a successor inventory; the historical workbook itself remains untouched.

| ID / worksheet row | Correct current status | Correction and remaining dependency |
|---|---|---|
| C01 / Components 6 | Preserved; additive software built, actual agent integration pending | `frankie_controller.py` and `controller_journal.py` connect native refresh, critic, and category-free consumer in synthetic integration. They do not replace the committed-file agent fetch/emit/spawn path. Preserve exact disabled callback behavior. |
| C02 / 7 | Protected historical Memory A preserved | Use the correct hash-bound prior for each experiment. Agent seed chronology and Windows checks are now repaired on the agent branch; refreshed carry is a separate artifact, not a historical rewrite. |
| C03 / 8 | Software built; real-source acceptance pending | `source_conformance.py`, `mbo_source.py`, and `mbo_resume_state.py` implement pinned actual DBN SDK record ingestion, exact wire/field/source binding and verified restart. Replace “vendor candidates only.” Actual source rights, production scope and feed conformance remain external/operational. |
| C04 / 9 | Software built and audited; cross-lineage integration pending | Native source/context path and agent causal stream exist. Agent stream now rejects duplicate/skipped groups and uses disk-indexed lawful sidecars with exact physical witnesses. Do not conflate the two separate lineages with an integrated deployment. |
| C05 / 10 | Built | Exact causal packet remains authoritative; newer physical-evidence rechecks close mutation during forward/publication. Preserve all versions, types and defects. |
| C06 / 11 | Software built; actual configuration/capacity pending | Actual SDK-to-context path and original-encoder QSV producer now exist. Real source/mask/mapping choices, production throughput and provisional context acceptance remain. |
| C07 / 12 | Built; preserve | No new numeric-projector implementation needed. Exact raw bytes remain alongside semantic views; do not equate missing with zero. |
| C08 / 13 | Built; preserve | Stable categorical/identity encoding and explicit unknowns already exist. |
| C09 / 14 | Built; preserve | Existing graph branch and scoped causal links remain. No new retrieval/graph architecture is required by the returned ruling. |
| C10 / 15 | Built; preserve | Delta memory remains within-sequence memory, distinct from B1 reasoning depth. Window selection remains explicit model computation, not evidence deletion. |
| C11 / 16 | Built software control | Preserve V1/V2 controls and native opt-in trunk. Production combined-agent acceptance is still separate. |
| C12 / 17 | Producer and attachment software built | `qsv_producer.py` invokes the unchanged complete 64-feature encoder and journals observations/output. Replace “producer-side wiring unbuilt” with actual source/mask/mapping configuration and acceptance still required. No invented MBO-to-bar transformation. |
| C13 / 18 | Mask/ablation software built | Preserve explicit zero/missing/ablated state through configured production source and later training. |
| C14 / 19 | R3 six-column candidate built; R2 preserved | `SPEC-c15-teacher-r3.md` and R3 implementation supply all six B2/C1 slots under a new identity; they are no longer simply unimplemented. R2 control keeps its declared ablations. Paired trained results remain absent. |
| C15 / 20 | Full evidence plus R2/R3 attachment software built | Replace six-column pending claim. Raw retention, teacher transforms, and normalizer identity remain distinct; R3 full-prefix reconstruction throughput is unmeasured. |
| C16 / 21 | TeacherHead/control harness built | Reuse `teacher.py` and governed targets. Forecast-scoring and paired-training execution remain necessary; do not invent another teacher mechanism. |
| C17 / 22 | plain_aux control built; paired experiment machinery built | Production fitting/result evidence remains pending. Input-only random projection must remain distinct from aligned labels. |
| C18 / 23 | Shuffled/random controls built | Paired orchestration is now built. Actual device-specific training proof and empirical verdict remain pending; historical CUDA skip is not CUDA acceptance. |
| C19 / 24 | Native recurrent core and additive controller built | `NativeForecastRefresh` consumes same-forward representations. Existing agent-path integration remains unfinished; B1 forecast authority is independent of Granite. |
| C20 / 25 | Built | Bounded, receipted halting remains an explicit frozen compute policy; no outcome-tuned halting. |
| C21 / 26 | Native source-bound critic mapping built; compact service integration pending | `granite_context.py`, native prompt/parser, `serve_native_shadow`, and controller bind exact input/packet/receipt identity. Compact codec exists separately and is not yet the live service path. |
| C22 / 27 | Pinned SDK transport software built; deployment/inference pending | `granite_sagemaker.py` and pinned HF/runtime specification exist, as does an optional Bedrock transport. Self-hosted AWS is the recorded route; Bedrock is not an extra mandatory component. Actual artifact staging, deployment verification, calls, and capacity acceptance remain. |
| C23 / 28 | Parser/prompt/timeout/native-binding software built | Replace “complete serving and timeout handling” as missing software. Actual inference validation and prompt/schema ownership packaging remain. Preserve exact raw context, closed output and separate prompt/parser identities. |
| C24 / 29 | Shadow disagreement and failure-isolation software built | Controller journals independent native and critic results; critic never edits forecasts. Invalid/timeout critic yields incomplete integrated result without removing native publication. Decision-affecting fusion is still absent and unearned. |
| C25 / 30 | Native heads, category-free adapter and consumer built | `forecast_heads.py`, frozen artifacts, `native_forecast_refresh.py`, bridge and consumer implement gap/path/endogenous timing and nullable confidence. Do not rebuild them or label winners “high.” Actual committed-file agent linkage, authentic metadata-origin binding, and deferred C3/C4 remain. |
| C26 / 31 | Layered checkpoint/recovery software built | Source/context, forecast, controller, experiment and outbox journals have explicit trusted checkpoints. Actual coordinator checkpoint storage and operational recovery across services remain integration obligations. |
| C27 / 32 | Locks, single reveal, paired runner/scorer software built | `experiment_locks.py`, `experiment_reveal.py`, `experiment_runner.py` replace “specified, unbuilt.” Actual complete matrix artifacts, declared scorer/metric registry and empirical execution/reveal are pending. |
| C28 / 33 | Pure deterministic risk policy built | `execution_contracts.py`/`execution_policy.py` use exact explicit units, signed exposure intervals, allowlists and caller pins. Authenticated account/source/valuation authority and operational controller are not built. |
| C29 / 34 | Durable synthetic outbox/reconcile built | `execution_ledger.py` has exclusive writer ownership, intent/approval/reservations, SENT_UNKNOWN before I/O, no autoretry, reflected-account causal frontier and durable kill latch. Real provider observation ingestion/venue reconciliation remain. |
| C30 / 35 | External/API and implementation pending | Typed Tastytrade translation, authenticated broker facts, lifecycle/failure validation, account permissions and operational wiring still needed. Spec is not an adapter. |
| C31 / 36 | External/API and implementation pending | Same distinction for Kalshi. No order submission or authenticated venue behavior established. |

## Roadmap cells and gates

| Roadmap row / sequence / status cell | Corrected interpretation |
|---|---|
| 6 / 0 / G6 | Historical preserve completion remains. Current carry and historical prior must now be named separately. |
| 7 / 1 / G7 | Historical S128/current-line blocker is stale as a global current-build claim. Current agent closeout is green; use its exact ancestry/verification rather than reopening baseline fixture failures. Root/shadow still verify the combined merge base. |
| 8 / 2 / G8 | Isolated BOSS and repaired-agent branches exist. A final combined integration checkout/import is still pending, so do not mark combined stage complete merely because clones exist. |
| 9 / 3 / G9 | BOSS foundations already imported/built on BOSS lineage. Selected integration into actual agent tree remains. |
| 10 / 4 / G10 | Partial remains; software ingestion/QSV producer no longer missing. Actual source mapping and capacity are the remaining items. |
| 11 / 5 / G11 | Change Not started to Partial: disabled adapter/controller and B0 software exist; actual agent disabled identity still required. |
| 12 / 6 / G12 | Partial remains; native heads, nullable consumer and producer software now built. Actual agent route/configuration/throughput remain. |
| 13 / 7 / G13 | Partial remains; six target columns and paired machinery built; fitted D0-D5 comparisons absent. |
| 14 / 8 / G14 | Partial remains; SDK serving/controller software built; actual exact Granite hosting and inference acceptance absent. |
| 15 / 9 / G15 | No empirical warmup/fitting acceptance claimed. Do not reinstate an earlier-roster prerequisite for memory admission; experimental data splits are a separate policy. |
| 16 / 10 / G16 | Runner/locks/reveal software built; empirical blind run/reveal not started. |
| 17 / 11 / G17 | Forward shadow results still absent. |
| 18 / 12 / G18 | Change Not started to Partial software: policy/outbox built; adapters/authenticated observations/operational execution pending. |

The gate `Work status` is column F, `Gate state` column H. Do not change OPEN to COMPLETE when the passing evidence requires production or empirical facts.

| Gate / sheet row | Status correction or residual proof |
|---|---|
| G01 / 6 | Preserve COMPLETE for frozen evidence; name exact historical prior, not current carry. |
| G02 / 7 | Historical health blocker superseded by current green agent closeout; rebind to its commit/evidence in successor tracking. |
| G03 / 8 | Branches exist; OPEN until final combined parent/ancestry is recorded and integration accepted. |
| G04 / 9 | Standalone disabled identity built; OPEN until actual agent path identity is proved. |
| G05 / 10 | SDK/software conformance built; external real feed/source acceptance still BLOCKED/OPEN as applicable. |
| G06 / 11 | Synthetic causal/restart and physical mutation safeguards built; measured timing-label resolvability and operational evidence remain OPEN. |
| G07 / 12 | Full-evidence/FIFO/type/field preservation software and audit built; real source acceptance remains OPEN. |
| G08 / 13 | B0 preservation software built; final combined integration acceptance remains OPEN. |
| G09 / 14 | B1 same-forward native production software built; empirical/operational acceptance remains OPEN. |
| G10 / 15 | Halting contract tested; retain OPEN only for integrated acceptance, not missing arithmetic. |
| G11 / 16 | R3 all-column candidate plus R2 control built; empirical teacher run remains OPEN. |
| G12 / 17 | Correct control and paired runner built; fitted production comparison pending. |
| G13 / 18 | QSV producer/attachment/masks built; actual source mask policy, training and capacity pending. |
| G14 / 19 | Correct controls built; actual device and paired training evidence pending. |
| G15 / 20 | Partial/OPEN: complete metric definitions, fitted calibration/reliability/coverage and comparisons still not accepted. |
| G16 / 21 | Change Not started to Partial: exact software/HF/SDK identities specified; deployed weights/tokenizer/runtime verification pending. |
| G17 / 22 | Source-bound exact native serializer/codec software built; deployed interface/capacity and answer-wall verification pending. |
| G18 / 23 | Replicated actual inference/variance evidence remains Not started/OPEN. |
| G19 / 24 | Change Not started to Partial: synthetic timeout/malformed/hash/disagreement failures tested; real inference drills pending. |
| G20 / 25 | Change Not started to Partial: immutable paired-arm machinery built; actual complete eight-arm locks/results not frozen. |
| G21 / 26 | Change Not started to Partial: runner/control identities exist; concrete D0-D5 optimizer/batch/data/model/scorer artifacts and results pending. |
| G22 / 27 | Change Not started to Partial: single-reveal software built; real frozen outputs/scoring/exclusions and authorized reveal absent. |
| G23 / 28 | Time-disjoint forward evidence remains Not started/OPEN. |
| G24 / 29 | Keep external licensing gate. A synthetic Databento SDK adapter does not prove DTN/CME rights or replace written topology/non-display acceptance. |
| G25 / 30 | Change Not started to Partial: exact pure policy tests built; authoritative account/valuation/controller integration pending. |
| G26 / 31 | Change Not started to Partial: durable synthetic outbox/fault handling built; real sandbox/provider observation proof pending. |

## Other worksheet corrections

- `Read Me!A4`, `A21`, `A33`: native heads and additive controller now exist; 871 is the historical checkpoint count, not current aggregate. Preserve `A29` and scores in `B24:C27` as historical estimates.
- `Build Plans!K7:L9,O7:O9`: retain Partial for B0/B1/B2 as complete systems. Remove missing-heads/six-column/serving-software claims and substitute agent-path integration, configured inputs, actual Granite and empirical acceptance. Do not change `M7:N9` historical design/readiness numbers.
- `Experiment Arms!K6:K13`: system machinery exists, but no new eight-arm result is established. Memory factor belongs to the protected controller surface; do not insert Memory A into the native B1 tensor input.
- `Experiment Arms!K14:K19`: D0-D5 controls and orchestration software exist; D5 R3 candidate now has all six formerly ablated slots. Actual trained comparisons remain pending.
- `Preservation Audit!A2:A3` and `E18`: historical checkpoint assertions need a successor annotation, not retroactive rewriting. `D14` should distinguish built QSV producer from actual source conformance. `D15` has newer physical checkpoint safeguards. `D21` must distinguish authorized actual Granite inference testing from still-unperformed/still-separately-authorized training, acquisition, reveal and orders.
- `Sources!A5:E35`: add successor implementation/acceptance references only if a new workbook update is requested. Existing entries prove their historical checkpoint. Do not treat all source-register vendor references as completed rights or operational evidence.

## Claude review/addendum overlap and pending work

| Finding | Current reconciliation | Dependency/action |
|---|---|---|
| R1 / C1 | Closed software: structural historical read is separate from locked-runtime reproduction/query. | Preserve archive bytes and publisher-attestation semantics; no duplicate implementation. |
| R2 | Closed independent publication/artifact trust roots plus defensive metadata snapshot. | Preserve sanctioned consumer route. |
| C2 | Honest interim implemented: `caller_supplied_unverified` metadata stamp and metadata hash. | Real authenticated Frankie population-record origin remains an integration gap for C01/C25, not falsely “fully verified metadata.” |
| R3 | Closed: last certified observation anchors path, global cutoff controls future emissions, anchor age conditions model. | Preserve five-coordinate generation identity and old V1 archive reads. |
| R4 | Closed for new generation: certified prior-close reference required. | No backfill/rewrite of archived forecasts. |
| R5 / C5 | Closed authorized interface convention: fatal-only defect list, nonfatal gaps in reasoning. | Callers must not downgrade missing required evidence or causal corruption. |
| C3 | Pending on current BOSS tree: consumer exception tuple lacks ArithmeticError; session has no proposed datetime bounds. | Preserved predecessor edits/test file described in transfer require deliberate adoption/review. Do not count its 35 focused checks as accepted branch software. |
| C4 | Pending on current BOSS tree: no `expect_latest` policy in consumer. | Reconcile proposed latest-by-target-and-arm default with explicit audit historical mode after initial-sheet work; preserve historical reads. |
| O1 | Bounded synthetic journal/refresh timing completed. | Actual scale/latency acceptance remains open; no need rerun old tiny timing for this audit. |
| O2–O6 | Completed fixes or explicit protected constraints in review handoff. | Sessions crossing S121 boundary still need a declared convention; do not silently alter S121. |
| O7 | Publication-depth benchmark was transferred unaccepted; no accepted timing output. | Complete/review only in deferred addendum phase, retaining full journal verification. |
| O8 | Existing exception normalization acknowledged; C3 is the remaining numeric class gap. | Preserve process-control exception propagation. |
| O9 | Realistic 2026 session regression appears only in transferred proposed addendum tests. | Adopt/verify with C3/C4; current branch acceptance not established. |

The returned architecture ruling adds narrow contract packaging and static ownership work, not a replacement BOSS architecture. A-59 packages prompt/schema/hash for Granite and the legacy/category-free seam with initial byte-identity proof; A-66 records static ownership. A-62 specialist-prior component and standalone A-64 branching engine are rejected; native retrieval is not to be added. Non-recency selection and multiple-critic comparisons are deferred hypotheses. Root owns these items now.

The byte-distillation note's “six columns unbuilt” and “serving unwired” statements reflect its older inspected build map and must not reopen completed software. Its proposed **C32**, **D6**, **D7** do not have workbook rows today. They are later training experiments requiring real serving/export and D5 results; hidden-state export is a separate pinned mode, not chat transport. EOT byte-text student is explicitly rejected, byte-input boundary semantics and native STOP already exist. Teacher agent owns detailed disposition. The unrelated `operator_runs.xlsx` research results are synthetic research evidence, not Frankie forecast acceptance.

## Dependency-ordered remaining implementation

1. **Combined tree and protected agent seam** — root/shadow: record exact `f0127bc4` and `996d121c` ancestry, import selected additive modules and connect committed-file fetch/emit/spawn to native publication/critic receipts. Preserve disabled path, legacy prompt/contract and correct historical memory prior. Prove actual agent read-back, run/arm/source identity and complete byte witnesses. C01/C04/C19/C25/C26; G03/G04/G08/G09.
2. **Contract ownership packaging** — root: accepted A-59/A-66 boundary objects/registry with byte-identical initial prompt render and static field-order proof. Keep transports and native deterministic machinery outside the packaging. This can proceed alongside source/hosting configuration, but must settle identities before deployment pins.
3. **Concrete source and QSV configuration** — configure actual source manifest, masks, mapping and chunk/bar semantics using existing producer; no invented reduction/default fill. Supply trusted prefix and checkpoints through the combined controller. C03/C06/C12/C13; G05/G06/G07/G13/G24. Written rights/real-data runs are external prerequisites, not code defaults.
4. **Compact critic route** — integrate exact codec/prompt/parser through real service/controller with explicit schema/code identities and expansion admission. Demonstrate exact inverse and complete logical reference mapping, then tokenizer capacity on representative distinct data and required context length. No silent truncation. C21–C24; G16/G17/G19.
5. **Actual exact Granite hosting and integrated inference** — stage/hash pinned model/tokenizer shards, verify deployed runtime/endpoint identity, run existing controller with real weights under bounded operator configuration, inspect receipts, repeat inference/failure drills, and clean up resources. C22–C24; G16/G18/G19. `SPEC-granite-live-run.md` is a proposal, not an implemented launcher. Quota/cost/prerequisite state must be refreshed by owning agent; old access-denied and zero-quota observations are not current facts by assumption.
6. **Operational checkpoint and load acceptance** — implement concrete trusted checkpoint coordination across source/context/forecast/controller and failure recovery; measure full retained-journal, R3 reconstruction, QSV, compact context, model and publication costs at declared load. C06/C15/C26. No dropping evidence or suppressing integrity checks to meet throughput.
7. **Training/evaluation bindings and results** — prepare exact fitted-model/decoder/calibration artifacts, metric schema, paired factors, optimizer/batches/seeds, exclusions and scoring quantities using existing D0-D5/eight-arm/reveal machinery. Then perform only separately authorized fitting/evaluation/reveal. C14–C20/C27; G11–G15/G20–G23. Results are not obtainable by implementation alone. Sunday agent comparison must use the frozen prior and independent findings before comparison, not current refreshed carry.
8. **Execution integrations** — implement authenticated provider observation ingestion, typed Tastytrade/Kalshi adapters, explicit valuation/source authority and operational policy/outbox controller. Preserve unknown-outcome/no-retry and reflected-account risk frontier. C28–C31; G25/G26. Sandbox/rights/live-capital actions remain separate from this software inventory.
9. **Deferred consumer addendum closeout** — only after required initial-sheet work reaches its agreed completion boundary: reconcile preserved C3/C4/O7–O9 edits, perform focused/full checks and independent review, update docs. C1/C2-interim/C5 already overlap completed work. No addendum implementation was performed in this reconciliation.
10. **Later optional empirical forks** — D6/D7 representation teacher export after D5 and actual Granite serving; fusion versus distillation decided by evidence. Do not add EOT text decoder, native memory retrieval, or a branching framework as hidden dependencies of finishing the initial build.

Important boundary for root: “finish the initial sheet” includes external/empirical gates that software alone cannot mark complete. Preserve the user's addendum sequencing; explicitly track those gated residuals rather than silently treating all unchecked rows as coding tasks or fabricating completion.
