# Codex integration handoff — Dipole classroom into lawful recovery (2026-09-16)

Repository: `DavisAI1974/Markets`

Source branch: `chatgpt/frankie-dipole-classroom-integration-20260916`

Source implementation/handoff tip before this file: `d52ff73e910b3183cfb359bca2b84e221677a295`

Reviewed classroom base: `ccode/frankie-dipole-classroom-review-20260916 @ 02306339ad34670de581c731b129924979ab4731`

Current recovery/reduction integration target observed immediately before this handoff: `ccode/frankie-lawful-recovery-review-20260915 @ 030608e337a54a90c2da53da363ee3e33097c431`

Focused CI proof branch: `chatgpt/frankie-dipole-classroom-integration-ci-20260916 @ 89980adcf88467958a4dba10e0832f49d3af9225`

Focused CI run: GitHub Actions `Dipole Classroom Integration Focused`, run `35089010057`, completed successfully against the CI proof branch. The CI branch is a child of `d52ff73`; its only additional repository change is the focused workflow used to execute the reviewed classroom and integration suites. Do not treat the unrelated legacy workflow failure on that push as a failure of the focused classroom suite.

Run `using-agent-skills` first, then the relevant context/review/debugging skills.

## Read first

1. `research/kalshi/frankie_boss/CODEX_REVIEW_DIPOLE_CLASSROOM_INTEGRATION_20260916.md`
2. this file

The first file is the detailed implementation/review record. This file is the cross-branch integration drop-in.

## What is complete on the classroom source branch

The classroom integration work that belongs on this branch is complete and committed:

- explicit `adapter_class` injection in `source_contract_runtime.make_principal_adapter(...)`;
- explicit `SundayRuntime.principal_adapter_class` dependency;
- request-plan pinning of adapter identity as `module:qualname` and fail-closed resume on identity change;
- production classroom path routed through `IntegratedDipoleClassroomPrincipalAdapter`;
- superseded `HardenedDipoleClassroomPrincipalAdapter` removed from the production MRO;
- classroom host composition made explicit with no production module/class rebinding;
- EC2 host composition made explicit instead of rebinding `ActualHost`;
- stale prior-cycle classroom package cleared before current-cycle runtime construction;
- focused integration/runtime-identity tests added/updated;
- no Frankie, Granite, EC2, Pod, market-data, or result-bearing run launched.

Against reviewed base `02306339`, the source branch changes only the composition/runtime/test surface plus the two handoff documents. It does not intentionally change governed Dipole teacher/target/normaliser math, Frankie inputs/calculations/planes, replay, Memory A, model architecture, loss/optimizer semantics, causal ordering/source evidence, journal/packet science, or refrag science.

## Important benchmark disposition

Greg's requirement remains:

- classroom is mandatory for every result-bearing Sunday/Frankie path;
- any benchmark exemption must be explicitly non-result-bearing;
- no result-bearing/principal/Granite path may inherit that exemption.

Do **not** add a general production classroom bypass.

The direct/disposable benchmark implementation lives on the separate lawful recovery/reduction line, not on the classroom source branch. Therefore the exemption is intentionally a reconciliation task, not something to fake on this isolated classroom branch. During integration, preserve the existing scratch/direct benchmark isolation if it already avoids the principal path. If an explicit exemption is still necessary after reconciliation, make it harness-local, explicit, and fail-closed when any result-bearing, principal, Frankie, or Granite path is active.

## Integration target state to preserve

The recovery/reduction target had advanced to `030608e337a54a90c2da53da363ee3e33097c431` immediately before this handoff. Its preceding measured reduction stack is `848ffe0d90114ba7ad441faecb13442f9c8188a6`, including the 14.4 ms/record three-worker ingestion result and its output-equivalence work. The current target tip reverts a broad whole-package CI workflow; do not reintroduce a broad CI gate as a side effect of this classroom merge.

Do not overwrite or regress the recovery/direct-benchmark/reduction work merely to take the classroom branch. Integrate deliberately.

## Codex integration job

1. Start from the current remote tip of `ccode/frankie-lawful-recovery-review-20260915`; re-fetch it first because that branch is active.
2. Bring in the classroom composition changes from `chatgpt/frankie-dipole-classroom-integration-20260916`, preserving the recovery/reduction work.
3. Resolve overlaps by behavior, not by choosing one branch wholesale. Preserve the explicit classroom adapter/runtime seam and the lawful recovery/reduction changes together.
4. Preserve the result-bearing classroom requirement. Handle the non-result-bearing benchmark only at the benchmark harness boundary as described above.
5. Re-run the same focused classroom/integration suites proved by CI on `89980ad`, plus any focused recovery/reduction tests touched by conflict resolution.
6. Verify the end-to-end non-model path: governed teacher attachment -> classroom package -> `SundayRuntime.classroom_package` + exact adapter class -> `_LazyPrincipal` -> `make_principal_adapter` -> integrated adapter.
7. Verify restart still refuses wrong request id, changed classroom binding hash, missing adapter class, changed adapter module/qualname, and stale prior-cycle package.
8. Re-check model-visible filesystem isolation and same-session correction locality. Answer-key/source snapshot/full post-grade material must remain host-owned audit material, never principal-visible.
9. Confirm no production module/class monkeypatch has returned on classroom or EC2 paths.
10. Re-run the science-drift comparison. Integration must not alter Frankie science, governed Dipole math, causal evidence, Memory A, loss/optimizer semantics, or replay.
11. Do not launch Frankie, Granite, EC2, Pod, market data, or any result-bearing cycle. This handoff is for code integration and focused verification only.
12. Commit and push the reconciled result on Codex's review/integration branch and hand back the exact branch, commit SHA, tests run, and any remaining blocker.

## Source-branch focused CI command surface

The successful focused workflow ran these suites under Python 3.13 with `pytest`, `numpy==2.3.5`, and CPU `torch==2.9.1`:

- `tests/test_dipole_classroom.py`
- `tests/test_dipole_classroom_session.py`
- `tests/test_dipole_classroom_hardening.py`
- `tests/test_dipole_classroom_final_review.py`
- `tests/test_dipole_classroom_review_fixes.py`
- `tests/test_dipole_classroom_integration.py`
- `tests/test_sunday_execution.py`
- `tests/test_frankie_principal_adapter.py`
- `tests/test_source_contract_runtime.py`
- `tests/test_claude_cycle_review_fixes.py`
- `tests/test_integrated_principal_recovery.py`

## Stop conditions

Stop and report rather than silently weakening a gate if the reconciliation would require any of the following:

- changing Frankie inputs, calculations, planes, adapters' scientific semantics, replay, Memory A, model architecture, loss/optimizer semantics, causal order, or source evidence;
- adding a general production classroom bypass;
- dropping, truncating, averaging, smoothing, normalizing, or otherwise excluding retained evidence;
- making a result-bearing/model call merely to prove integration;
- discarding recovery/reduction work to make the merge easier.

No launch.
