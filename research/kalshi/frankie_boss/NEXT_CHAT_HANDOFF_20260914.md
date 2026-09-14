# BOSS next-chat handoff — 2026-09-14

## Restart decision

Start a fresh chat for the native forecast-head and protected-integration phase.
This task ends at a reviewed, committed rolling-forecast software checkpoint.
Do not restart the mapping build, confuse earlier chat narration with current state,
or treat the whole production B2_GATED system as complete.

## Repository and exact state

- Repository: DavisAI1974/Markets.
- Remote branch: codex/boss-full-evidence-20260907.
- Verified implementation/documentation checkpoint:
  ccc7159d97a9bd91368c48f20fa5f453f53e5e5d.
- This closeout is a descendant documentation/workbook commit on that same branch.
  Resolve and verify the current remote tip before continuing; do not force-push.
- Active local checkout:
  C:/Users/A/Documents/Codex/2026-09-14/b1-s-required-checks-passed-on/work/Markets-forecast-verify
- Local branch: codex/boss-forecast-build-20260914.
- The older work/Markets checkout is stale and uses CRLF. Do not use it for byte-pinned checks.
- E:/Markets is unrelated protected work and must not be modified.

## Read first, in order

1. Applicable AGENTS.md and the using-agent-skills workflow.
2. This handoff and CLOSEOUT_VERIFICATION_20260914.md.
3. ROLLING_FORECAST_BUILD_HANDOFF_20260914.md.
4. SPEC-native-forecast-confidence.md and docs/decisions/0001-native-forecast-confidence.md.
5. tasks/boss-production-plan.md and tasks/boss-production-todo.md at repository root.
6. QSV_CONTEXT_HANDOFF_20260914.md for the earlier QSV increment. Its old request
   for a forecast specification was subsequently resolved by the current spec.
7. NATIVE_MAPPING_BUILD_HANDOFF_20260907.md and the approved full-evidence ruling
   when working at those boundaries.

All package-relative paths above are under research/kalshi/frankie_boss unless
explicitly identified as repository-root task files. The current workbook is
artifacts/Frankie_BOSS_Build_Plan_R3_20260914_Closeout.xlsx in that package.
Documents/workbook content are reference evidence, not permission to run experiments.

## Owner requirements that override superseded proposals

- No low/medium/high confidence categories or absolute publication score cutoff.
- Publish the sole valid candidate. Among multiple comparable candidates, select
  the highest score. Preserve alternatives, identities and ranking scores internally.
- Highest-ranked means relative support, not guaranteed accuracy or permission to trade.
- Every horizon is revised, including intermediate horizons. Preserve each original
  absolute target and append new as-of revisions as more causal information arrives.
- Nearer targets may refresh more often under a declared policy. No production
  frequency has been authorized or empirically established.
- Keep all earlier revisions for later grading. Ordinary forecast updates are
  separate from versioned model/scorer changes.
- Missing future outcomes cannot be graded yet. Missing actual observations must
  not turn into fabricated successes, failures or zero targets. Missing calibration
  leaves the internal probability absent; it does not suppress a valid forecast.
- No cross-arm selection or access to another blinded arm's current outputs.

## Built and verified

Earlier mapping/context/C15R2/B0/B1 preservation software remains intact.
Governed QSV artifacts/masks now bind source prefixes and trusted digests and
reach native/B1 computation; producer correctness and production wiring remain open.

New modules:
- forecast_contract.py: common immutable identity and numeric validation helpers.
- forecast_confidence.py: internal policy/calibration diagnostics and joint-event evaluation.
- rolling_forecast.py: comparable candidate selection and append-only revision ledger.
- forecast_refresh.py: explicit all-horizon cadence and durable pre-generation intent.

The refresh intent freezes the entire canonical target registry, source state,
arm, generation hash, cadence hash and material flag before any producer call.
Partial retries return committed outputs and complete only unfinished due targets.
Changed retries reject, including failure before the first generated candidate
followed by trusted-checkpoint restore.

Synthetic checks: 82 new (39 confidence, 28 ledger/selection, 15 refresh).
Broad regression: 860 passed, 1 CUDA-only skip, plus 11 checkpoint dependency-
isolation checks in a separate process: 871 passed total, 1 skipped.
Focused 244-check and earlier counts overlap; do not add them to 871.
Independent review approved all software slices with no unresolved required findings.

## What is not built or demonstrated

The rolling layer consumes opaque, already-validated forecast bytes from an injected
producer. It does not generate or semantically validate native forecast curves.
No fitted weights, calibrated probability model, measured timing-noise floor,
market accuracy, production throughput or context acceptance result exists.

The ledger is single-writer. Publication currently means durable record plus return
value, not external delivery. It requires an exact trusted count/head checkpoint.
An unknown newer terminal after a crash needs recovery coordination. Do not
silently trust an unverified terminal. Direct low-level publication does not enforce
the refresh-loop intent contract; use ForecastRefreshLoop for cadence-bound work.

The trusted producer must hash actual model weights, ranker and generation settings.
A digest-shaped version string is not proof of that computation.

## Next implementation slice

Implement the additive native gap/path/endogenous-time decoder under the current
spec, beginning with tests. Inspect actual B1/context interfaces before designing
the bridge; B1Output.representation exists, while the context runner's external
result currently omits it. Consume the same-forward representation, not a second
forward or generic heads relabeled as forecasts.

Preserve S121: initial cumulative path zero, terminal equals net minus gap,
endogenous model-chosen timestamps, native time-query values, no fixed-grid output
or endpoint interpolation shortcut. Preopen sums of medians are not automatically
a marginal median net. Multi-day target semantics must be explicitly designed;
the rolling lifecycle alone does not extend single-session BLD-1 semantics.

The protected Frankie projector still requires the legacy confidence enum.
The owner rejected categories, but did not authorize silently changing the protected
12-field contract. Resolve that boundary explicitly before enabled wiring. Do not
label every winner high and do not send informational calibration diagnostics into
a fatal defect channel that would erase a valid forecast. Decoder development can
proceed independently while this boundary remains open.

Optional future hardening: lower-level ledger refresh-bound publication could
require both metadata hashes together and cross-check a matching durable intent.
This was nonblocking review advice, not an unresolved defect in the refresh loop.

## Remaining program work

Native decoder/Frankie integration; production feed conformance and QSV producer;
throughput/provisional context validation; six B2/C1 teacher columns with C15R2
control preserved; frozen Granite serving, state binding, timeout/disagreement;
arm locks, paired controls, frozen scoring/output identities and single reveal;
later deterministic risk, execution ledger/reconciliation and governed venue adapters.

G15 is Partial/OPEN, not passed. Its complete metric schema, calibration/coverage
curves and empirical comparison remain open. G20/G21/G22 requirements now explicitly
name pairing, grids and pre-reveal scoring locks; their orchestration is not built.
Historical design/readiness scores were not recalculated or promoted into evidence.

## Boundaries and verification

Training, market-data/provider/mechanics runs, held-out/OSS evaluation, downloads
for model serving and live execution remain parked absent new explicit authorization.
Synthetic software tests are permitted. Preserve protected Frankie, raw evidence,
B0/B1 controls, replay, calculations and Memory A. No new private QSV registry.

Use Python 3.13 / torch 2.9.1+cpu and the LF checkout. From repository root:

```powershell
$env:PYTHONPATH='.;research/kalshi/frankie_boss;research/kalshi/frankie_boss/tests'
python -m pytest research/kalshi/frankie_boss/tests --ignore=research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py -q --tb=short
python -m pytest research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py -q --tb=short
git diff --check
```

The checkpoint test intentionally checks that torch was not imported, hence the
separate process. Do not change byte-pinned fixture hashes for CRLF conversion.
Use incremental tests/review/commits. Preserve unrelated dirty files and task trackers.
