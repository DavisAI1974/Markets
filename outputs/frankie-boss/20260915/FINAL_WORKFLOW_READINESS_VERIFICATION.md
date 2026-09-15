# Read-only GitHub workflow readiness verification

Observed through 2026-09-15 09:09:45 UTC using existing `gh` access. No dispatch, marker write, cancellation, artifact download, cloud/Pod action, account action, test, inference, or source database read occurred.

## Remote code identity: verified

Repository: `DavisAI1974/Markets`.
Branch: `codex/full-frankie-boss-connection-20260915`.
Frozen code: `35982ac7d42b546446038866299c23ca4fc50edc`.
Remote HEAD at initial and final checks: `b258b2163c22b59561272fece93255a43eb1b7c9`.

GitHub compare API reports ahead_by=2, behind_by=0. Children:

- `e513e497ae7de251e545ded30a566c467c2ec663`: docs: retain Sunday probe and source handoff audits.
- `b258b2163c22b59561272fece93255a43eb1b7c9`: docs: retain audited Sunday launch continuation.

Only changed files are `outputs/frankie-boss/20260915/FINAL_SOURCE_HANDOFF_CODE_AUDIT.md`, `HOST_PROBE_TEST_RECEIPT.md`, `PROBE_ANALYSIS_DELTA_AUDIT.md`, and `SUNDAY_LAUNCH_CONTINUATION.md`. No workflow or runtime code changes. Frozen local Git objects were used to inspect workflow/module contents; remote descendant comparison establishes current-branch code equivalence.

## Registration and triggers

| Actual workflow | API registration now | Actual trigger |
|---|---|---|
| frankie_bootstrap_stage.yml | Not registered/listed; direct API HTTP404 | Push to branch above changing `.github/frankie-bootstrap-stage-request.json` |
| frankie_request_stage.yml | Not registered/listed; direct API HTTP404 | Push changing `.github/frankie-request-stage-request.json`; workflow_dispatch also declared |
| frankie_retained_granite.yml | Not registered/listed; direct API HTTP404 | Push changing `.github/frankie-retained-lease-request.json`; workflow_dispatch also declared |
| frankie_retained_completion.yml | Active, workflow ID358548335 | workflow_dispatch; own-YAML push registration skips publication |

Paginated workflow inventory and direct per-filename lookups agree. Historical `boss_granite_bootstrap_stage.yml` and `boss_granite_artifact_stage.yml` are active but target the older branch; they are not the intended actual staging path.

The current remote recursive tree was not truncated and contains none of the three actual marker paths. Creating the actual independently bound bootstrap, request, and lease marker payloads will therefore change their exact configured push paths. Do not claim dispatch-by-name availability for unregistered workflows or register them with dummy/smoke markers. After each real operational marker push, verify that the expected workflow/run exists at the exact resulting marker commit and that its workflow/runtime bytes remain the reviewed bytes. A successful push alone is not workflow execution evidence.

Completion registration run34947435070 at commit553f447d9d04804442399ecf3049a1d0cba37c8c is completed/skipped, as its job requires workflow_dispatch. This is registration evidence only; no completed live publication has been demonstrated.

## Checkout, runtime pins and host alignment

Bootstrap staging checks out the exact push commit with full Git history, then reads package files from marker `source_commit` and checks the independently supplied bundle SHA before staging. Its actual marker must name the frozen code35982ac7d42b546446038866299c23ca4fc50edc and the final exact bundle digest.

Request staging checks out the push commit, accepts the exact request digest/byte count and recipient public key, and issues a conditional checksum-bound capability or verifies an existing exact object. Its encrypted capability artifact expires after one day. No plaintext capability was accessed here.

Observer checks out its exact push/event commit and receives immutable runtime configuration through the real lease marker or dispatch input. The configuration binds source commit, file roster/bundle SHA, supervisor command SHA, context encoding, service context, transport protocol and bootstrap directory. Replacement observers cannot change an existing configuration. Runtime jobs_v1 selection must be carried in the actual marker; code supports it but this audit did not manufacture or launch a marker.

Completion dispatch uses the operational branch as workflow ref but checks out `inputs.code_commit`; the standalone writer verifies actual checkout HEAD. Current authoritative host configuration aligns: boss_commit35982ac7d42b546446038866299c23ca4fc50edc, completion_workflow_ref equal to the branch above, transport_protocol jobs_v1, service_context131072, output_budget remaining_context. Later report/marker commits must not rewrite the frozen code pin.

## Existing runs and artifact access

Repository-wide in_progress query returned two unrelated scheduled collectors (Pyth34927164505 and Kalshi34922152919). Queued and waiting inventories were empty. No active retained observer, staging, or completion run was observed. Recent branch runs include unrelated failing `ng_exhaustion_step1_receipt_count_20260823.yml` push entries; these are not evidence of failure or execution of the intended retained workflows.

Authenticated artifact metadata access works: repository artifact listing returned1773 artifacts and an unexpired existing artifact. The completion registration run has zero artifacts, as expected for a skipped job. No actual new readiness artifact exists yet and no download/extraction was attempted.

The observer's prepare role uploads `retained-granite-ready-<run_id>` from `work/retained-granite/` before entering its hold step. This permits the actual operator to download that exact run's artifact while observation continues, using existing `gh run download <run_id> --repo DavisAI1974/Markets --name retained-granite-ready-<run_id> --dir <fresh E directory>`. Independently verify service-pins and admitted request/runtime identities before supplying the host stdin trigger. Bootstrap/request artifacts use `granite-bootstrap-stage-sensitive-<run_id>` and `granite-request-stage-sensitive-<run_id>` respectively and contain encrypted envelopes requiring the actual matching local recipient key. Artifact metadata accessibility does not prove future artifact creation or decryption succeeds.

## Outcome

Branch/code identity and the intended marker-trigger paths are aligned. Completion is registered and active. Bootstrap/request/observer registration is a required observation after their first actual operational marker pushes, not yet a verified state. No dummy trigger is needed or authorized by this check. Final source pinning, actual artifact/readiness verification, model execution, completion publication and confirmed run-bound cleanup remain live operator gates. This report does not claim they have worked.
