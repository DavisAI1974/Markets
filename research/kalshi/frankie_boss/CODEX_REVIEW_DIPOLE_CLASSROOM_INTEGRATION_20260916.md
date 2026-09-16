# Codex review handoff — Dipole classroom integration (2026-09-16)

Repository: `DavisAI1974/Markets`

Review branch: `chatgpt/frankie-dipole-classroom-integration-20260916`

Implementation tip immediately before this handoff file: `ab0dd3c78e5176bb8f3786e05877537fd5408f8c`

Reviewed classroom base: `ccode/frankie-dipole-classroom-review-20260916 @ 02306339ad34670de581c731b129924979ab4731`

Run `using-agent-skills` first, then the relevant context/review/debugging skills. This is a focused integration review. Do not launch Frankie, Granite, EC2, Pod, market data, or any result-bearing workflow.

## Baseline already reviewed by ccode

The `02306339` classroom base is ccode's final review of the classroom hardening. Its focused classroom suites were **59 passed** on the workstation. That base closed the answer-key filesystem leak, post-cycle-0 renderer crash, HYPOTHESIS/171-ledger inconsistency, transcript field omissions, classroom cycle-count duplication, Pearson floor consolidation at 8 overlapping PRESENT values, curriculum measurement/discovery attribution, taper regression, and the completion-audit/newline cleanup.

The reviewed base also verified the governed Dipole target/teachers/normalisers, context/cache, reasoner/checkpoint, lawful host/base principal adapter, encoder/journal/packet and refrag science files byte-identical to the lawful `050c5056` lineage.

## What this integration pass changes

This pass moves the reviewed classroom from an isolated wrapper/monkeypatch seam into explicit runtime composition. It does not change Dipole mathematics or Frankie science.

### 1. Explicit principal-adapter injection

`source_contract_runtime.make_principal_adapter(...)` now accepts `adapter_class` explicitly. It defaults to the base mandatory classroom adapter for construction compatibility, but any supplied class must be a subclass of `DipoleClassroomPrincipalAdapter`.

### 2. SundayRuntime owns the adapter dependency

`SundayRuntime` now has `principal_adapter_class: type | None = None` in addition to `classroom_package`.

Execution remains strict: `SundayExecution.run_cycle()` refuses a missing classroom package and refuses a missing/non-class adapter. `_LazyPrincipal` passes `runtime.principal_adapter_class` explicitly to `make_principal_adapter`.

The request plan now retains `principal_adapter_identity` as `module:qualname`. Resume refuses a different adapter identity alongside the existing source/admission/classroom checks. This is intentional: changing which classroom adapter interprets a retained cycle is an identity change, not a transparent restart.

### 3. Live hardening path collapsed

New module: `dipole_classroom_integration.py`.

Production now uses:

`IntegratedDipoleClassroomPrincipalAdapter -> DipoleClassroomPrincipalAdapter -> FrankiePrincipalAdapter`

The superseded `HardenedDipoleClassroomPrincipalAdapter` is not in the production MRO. The old hardening module remains in the repository for reviewed-history/test compatibility.

The two policies that remain live are owned directly by the integration module:

- mastery taper/regression: advance only after two consecutive mastered+acknowledged teacher-complete cycles at the current level; regress one level after non-mastery;
- Pearson re-pin: coefficients below the core minimum overlap of 8 remain suppressed while overlap count is retained.

`prepare_integrated_cycle()` otherwise preserves the ccode-reviewed final classroom message/binding semantics: complete coverage, direction definition, novelty invitation, `learning_measurement`, and `independent_discovery_eligible`.

The integrated adapter reuses the ccode-reviewed final `prepare`, `_request`, and `_recover_with_classroom` method implementations directly on the base mandatory classroom adapter. Review this method rebinding deliberately; it is intended to preserve reviewed behavior without carrying the superseded adapter in the MRO.

### 4. Classroom host is explicit composition, no module rebinding

`operations/run_actual_sunday_classroom.py` no longer rebinds:

- `source_contract_runtime.DipoleClassroomPrincipalAdapter`;
- `base.ActualHost`;
- `base.await_recorded_principal`;
- `driver.SundayRuntime`.

`ClassroomActualHost.prime_cache()` still reuses the **already prepared governed teacher attachment** and never re-attaches/recalculates Dipole. It builds the package from the exact prepared context rows, retains the host classroom source/key/message/binding, and retains the selected adapter module/qualname.

`ClassroomActualHost.runtime()` clears any prior-cycle in-memory package before loading the current cycle, pins the adapter identity for that cycle, calls the ordinary host runtime, then attaches the exact current `classroom_package` and `principal_adapter_class` to the returned `SundayRuntime`.

This stale-package clearing is deliberate: a partially retained later cycle must never inherit the previous cycle's classroom package even transiently. `SundayExecution` independently checks the package request id and binding hash.

`ClassroomActualHost.run()` builds the ordinary Sunday runner and uses the classroom-aware same-session waiter without mutating globals.

`main(host_class=ActualHost)` is now an explicit host-class composition seam.

### 5. EC2 wrapper no longer rebinds the host class

`operations/run_actual_sunday_ec2.py` now calls:

`actual.main(host_class=EC2ActualHost)`

instead of assigning `actual.ActualHost = EC2ActualHost`.

The recovery-only sidecar verifier and learning telemetry behavior are otherwise unchanged.

## Focused tests added/updated

- `tests/test_dipole_classroom_integration.py`
  - integrated adapter MRO excludes the superseded hardened adapter;
  - taper still requires two mastered cycles and regresses;
  - classroom runtime attaches package + adapter without host/runtime class rebinding;
  - classroom `main` exposes the explicit host-class seam and contains no old module rebinding.
- `tests/test_sunday_execution.py`
  - composition fixture supplies an explicit integrated adapter class;
  - request plan retains exact adapter identity;
  - missing adapter class is refused before coordinator work.

**Important:** these new integration tests have NOT been executed from ChatGPT's GitHub connector environment. There is no CI status on the branch. Do not report them green until you run them. The last actually executed classroom baseline is ccode's 59 green at `02306339`.

## Diff scope from ccode-reviewed base

Against `02306339`, the integration branch changes only:

1. `dipole_classroom_integration.py` (new)
2. `operations/run_actual_sunday_classroom.py`
3. `operations/run_actual_sunday_ec2.py`
4. `source_contract_runtime.py`
5. `sunday_execution.py`
6. `tests/test_dipole_classroom_integration.py` (new)
7. `tests/test_sunday_execution.py`

No governed Dipole teacher/target/normaliser, model architecture, Frankie input/calculation/plane, replay, Memory A, loss/optimizer, causal source, journal/packet, or refrag science file is changed by this integration pass.

## Review requests for Codex

1. Run the focused classroom suite that produced ccode's 59-green baseline **plus** `test_dipole_classroom_integration.py` and the updated `test_sunday_execution.py`.
2. Check the direct-method reuse in `IntegratedDipoleClassroomPrincipalAdapter` for any Python descriptor/super/MRO surprise. The reused reviewed methods intentionally call the durable/base methods explicitly rather than relying on the removed hardened MRO, but prove it with the real two-turn adapter tests.
3. Verify the runtime path end-to-end without making a model call: prepared teacher attachment -> integrated package -> `SundayRuntime.classroom_package` + adapter class -> `_LazyPrincipal` -> `make_principal_adapter` -> integrated adapter.
4. Verify restart refuses:
   - wrong request-id classroom package;
   - changed classroom binding hash;
   - missing adapter class;
   - changed adapter module/qualname;
   - stale prior-cycle package.
5. Re-check model-visible filesystem isolation. The source snapshot, teacher key, and full post-grade must remain in host-owned audit storage, not the principal directory. Do not weaken the filesystem-scope assumption silently.
6. Verify same-session correction still uses only correction-local facts, not the exhaustive answer key, and that the next cycle carries only the reviewed prior-correction summary.
7. Verify `dipole_novel_findings` remains mandatory as a response key (empty list allowed) and novelty remains non-punitive to classroom mastery.
8. Confirm no module/class monkeypatch remains on the production classroom/EC2 path.
9. Re-run the science-drift comparison against the reviewed base/lawful lineage. The integration pass is supposed to touch composition only.
10. If you find a defect, fix it on your review branch with focused tests and hand back the exact commit. Do not broaden into result-bearing execution.

## Separate recovery/benchmark branch — do not merge blindly during this review

The separate ccode recovery/reduction branch has advanced since the earlier benchmark handoff:

`ccode/frankie-lawful-recovery-review-20260915 @ 848ffe0d90114ba7ad441faecb13442f9c8188a6`

That branch now contains the measured ingestion reduction stack (14.4 ms/record with three encode workers) in addition to the recovery/direct-benchmark history. Keep that work separate while reviewing this classroom integration.

When the branches are deliberately reconciled, preserve this rule:

**Do not add a general production classroom bypass merely to make a benchmark convenient.**

The disposable/direct benchmark is non-result-bearing and historically executes against a scratch/restored checkout with no Frankie/Granite/principal path. If an exemption is needed after branch reconciliation, keep it harness-local, explicit, and fail-closed on any result-bearing/principal/Granite path. Prefer preserving the existing isolated benchmark behavior rather than weakening `SundayExecution`'s mandatory classroom gate.

## Launch gate

Closed. No Frankie, Granite, EC2, Pod, market-data, or result-bearing cycle was launched by this integration work. Review and focused tests first.
