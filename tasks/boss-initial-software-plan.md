# Initial-sheet software continuation

Base implementation: 4eebf5852d039c28a016213baefc7e118c454e58.
Predecessor final handoff 79bd40abfe4ca0ea0dfb4af839d22254a4f61de2 has been
verified and merged. Its original checkout retains unfinished addendum work and
remains untouched. The historical workbook remains unchanged.

## Parallel slices and ownership

- Source conformance: source_conformance.py, its test and dedicated spec.
- Granite serving boundary: granite_shadow.py, its test and dedicated spec.
- Six causal teacher columns: c15_teacher_r3.py, separate R3 normalizer if needed,
  their tests and dedicated spec. Existing R2 source and bindings stay unchanged.
- Paired experiment locks: experiment_locks.py, its test and dedicated spec.
- Root coordinates reviews, integration, task status, commits and pushes.

Acceptance criteria and focused verification commands live in each dedicated spec.
No shared source files are assigned to multiple agents. Each completed increment
receives independent review and focused tests before commit. Run the combined BOSS
suite after integration, with checkpoint dependency tests in a separate process.

## Work checklist

- [x] Source-conformance slice verified and reviewed (e834167e).
- [x] Frozen Granite request/response boundary verified and reviewed (aa1c0cf4).
- [x] Real Bedrock SDK service and explicit real-call harness (f91b06b5).
- [ ] GitHub Actions endpoint discovery and actual model integration run.
- [x] Pinned native SDK extraction into source conformance (da0443f8).
- [x] Six-column R3 teacher slice verified and reviewed (7c46a31b).
- [x] Exact native-context Granite mapping (ec64284b) and SDK service wiring (d30110a7).
- [x] Self-hosted SageMaker/vLLM transport for exact Granite (e807488c).
- [x] Governed original-encoder QSV producer and provenance (e0da21db).
- [x] Combined native/Granite controller software and synthetic integration (84b986dd); real agent delivery integration remains open.
- [x] Immutable paired experiment/output locks verified and reviewed (55faec71).
- [x] Durable reveal intent and trusted restart (55faec71); paired runner/scorer software (7ef81398), empirical runs remain open.
- [x] Reconcile final predecessor closeout and verify combined regression (1,371 passed, one skipped; 11 checkpoint tests separately).
- [x] Pure execution policy and durable synthetic ledger, including terminal account frontier and independent kill latch (73 focused tests).
- [x] Lossless compact-context codec and explicit expansion admission bounds (43 dependent tests).
- [ ] Wire compact context through SDK/controller and accept actual model capacity.
- [ ] Join BOSS build with the existing committed-file Frankie agent delivery path.
- [ ] Complete execution adapters, provider observation ingestion and operational controller.
- [x] Commit/push reviewed increments and update successor handoff (audit closeout; full build remains open).

Full initial-sheet implementation remains the objective. These are increments,
not claims of completed service integration, B2_GATED or production gates.
Actual QSV source policies, Granite deployment/runtime/context acceptance,
controller deployment and execution software remain explicit subsequent work.
## Owner clarification during this continuation

The target is full operational Frankie, including the actual Granite/Bedrock model
in the role required for B2 and tests through the same SDK path used in operation.
The owner explicitly rejected treating Bedrock as a proof-of-concept or stopping at
fake-transport tests. Actual model calls and deployment/test prerequisite work are
now in scope. GitHub Actions holds the existing AWS secrets; use them in runner
environment without printing or transferring their values. The authorized SageMaker
target is us-east-1; the inventory workflow now uses that region explicitly.

Workbook source check: commit 9006b633's AWS governance and Granite assessment
explicitly favor self-hosted Granite inside AWS and a bounded initial GPU run.
Neither the workbook nor those source documents requires Bedrock. Nucleus is the
explicitly excluded architecture; Granite 4.2 8B remains required. User reiterated
that Granite is definitely included. SageMaker is an implementation option for
self-hosting, not an additional reasoning component.

The later AWS check at workflow 34871775747, attempt 2, supersedes the initial
AccessDenied findings: the execution role is visible in us-east-1 and the pinned
vLLM image resolves. The ml.g6e.2xlarge endpoint quota was still zero at that check;
the owner's increase request was pending. Inventory pagination and Hosting-price
selection are repaired in this continuation. No GPU resource or real inference
has been created. The artifact stager and integrated live model run remain build
work; quota is not the only unfinished item.

Actual pinned IBM tokenizer diagnostic (synthetic neutral MBO rows): native-context
V1 with QSV uses 5,744 tokens at 1 row, 122,335 at 32, 483,555 at 128 and 1,928,858
at 512, including non-thinking chat template. Without QSV, 512 rows use 783,485.
These are capacity observations, not latency/quality measurements. The 4096-row
diagnostic was stopped after smaller cases established overflow; no 4096 count is
claimed. Lossless removal of repeated schema/display material is under design;
no evidence truncation or silent context reduction is authorized by this finding.
The compact codec is now implemented; a 512-row repeated-QSV diagnostic measured
95,301 tokens. This is not proof for arbitrary QSV or 4096-row model capacity.

This overrides older handoff statements parking model inference. It does not
authorize order submission or reinterpret the held-out single-reveal restrictions.
Synthetic fault tests complement, and do not replace, actual integration runs.

## Deferred Claude addendum

Read at owner request to detect overlap before implementation. C1, C2's honest
interim, and C5 overlap newer completed corrections. C3 numeric-clock safety and
C4 current-versus-historical selection require reconciliation against final closeout;
do not implement addendum requests until initial-sheet work is completed. Preserve
historical-read API behavior while that decision is pending.

## Architecture review request and agent execution

`CLAUDE_ARCH_REVIEW_NOOA_CONTEXT_RETRIEVAL_20260914.md` at 3cfbf5c4 is the older
request. The returned ruling and Slice 1 stop handoff have now been received.
See CONTINUATION_HANDOFF_20260914.md, BUILD_MAP_RECONCILIATION_20260914.md and
CLAUDE_CODE_CONTRACT_ASSIGNMENT_20260914.md under frankie_boss. The separate
forecast addendum above remains deferred. The 11-field protected legacy prompt
and 12-field additive BOSS adapter require a caller trace and corrected contract
proof; no frozen prompt was changed to force the proposed equality assertion.

The manual Claude assignment owns narrow byte-preserving contract packaging for
all three current Granite prompt variants. No implementation has returned; the
automatic local read-only Claude attempt failed expired OAuth with no edits.
Codex's compact service/controller route is SPEC-granite-compact-service.md only.
The agent-file exporter/receiver is AGENT_FILE_INTEGRATION_PLAN_20260914.md only.
The original workbook remains unchanged; no derivative workbook was generated.

The owner clarified that Frankie runs as an agent session over committed files.
Use the existing fetch/emit/spawn/read-back path from the raw-MBO benchmark lineage;
do not build another calculation runner for him. The repaired agent path is on the
separate `codex/frankie-agent-evidence-fixes-20260914` branch. BOSS and that branch
are not yet integrated. Rerun Sunday 2021-10-03 first, using prior A-memory run
33746436209 for comparison after independent findings are filed. No rerun has
started in this audit. Preserve original findings provenance and do not seed the
new session with old conclusions.
