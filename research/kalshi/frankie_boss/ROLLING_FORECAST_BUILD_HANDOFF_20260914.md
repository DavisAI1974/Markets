# BOSS rolling forecast software handoff — 2026-09-14

## Completed increment

The new additive software layer implements the owner's clarified publication rule:
use the sole valid candidate, or select the highest score among comparable
candidates. No low/medium/high categories and no absolute publication threshold
are introduced. Highest-ranked is relative, not a claim of high absolute accuracy.

Every registered horizon supports revisions. Each target retains its original
absolute time, while each revision records a new as-of/source cutoff and immutable
model, ranking and policy identities. Earlier forecasts and all alternatives remain
in a separate append-only, hash-verified forecast ledger. C15 input evidence is unchanged.

Explicit cadence bands can refresh nearer targets more frequently. Material updates
can refresh all unexpired targets, including intermediate horizons. No production
cadence values or live timer are configured.

A full refresh intent is persisted before generation: complete target registry,
material flag, source, arm, cadence and generation hashes. An identical partial
retry returns already committed revisions and generates only the unfinished due
targets. Changed intent rejects, including when the first generation failed and the
ledger has subsequently been restored from its exact trusted checkpoint.

Internal reliability primitives validate calibration identity/support/validity and
evaluate the declared joint gap/net/path event. Missing realized observations leave
that event unknown with explicit counts; they are not zero outcomes or fabricated
successes/failures. Missing calibration leaves the internal probability absent and
does not itself suppress a valid forecast.

## Verification

- 82 new synthetic checks: confidence 39, candidate/ledger 28, refresh 15.
- Combined focused regression: 244 passed, including existing seam/B1/context/QSV.
- Broader BOSS suite: 860 passed and 1 CUDA-only test skipped (no CUDA device).
  The dependency-isolation checkpoint suite passed separately: 11 tests. Total:
  871 passed, 1 skipped across these two processes; do not add overlapping focused
  counts to this total. The checkpoint suite intentionally requires no imported torch.
- Python compilation and git whitespace validation passed.
- Independent review approved all three slices; final review had no Critical or
  Required findings. Tests reproduced the retry gaps before the fixes.

These are software checks, not market experiments, learned accuracy or calibration evidence.

Reproduce from repository root in PowerShell:

```powershell
$env:PYTHONPATH='.;research/kalshi/frankie_boss;research/kalshi/frankie_boss/tests'
python -m pytest research/kalshi/frankie_boss/tests --ignore=research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py -q --tb=short
python -m pytest research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py -q --tb=short
```

Use the LF checkout for byte-pinned preservation fixtures. Do not rewrite expected
hashes to accommodate CRLF conversion.

## Implementation boundaries

The injected producer supplies already-validated immutable forecast bytes. The new
layer does not generate native forecast curves, fit a model, prove scorer quality,
or validate the semantic contents of those opaque bytes. Multiple candidates must
share source state, target, as-of, experiment arm and frozen ranking policy/scorer.
No cross-arm winner selection is allowed.

Generation hashes must be computed by the eventual producer from actual weights,
ranker and generation settings. This generic layer checks digest form and stable
binding; it cannot prove that the producer hashed all relevant content.

The ledger is single-writer and returns publications only after durable append.
Publication here means ledger commit plus returned object, not external delivery.
Delivery acknowledgements, process scheduling and live feed integration are absent.
Restart requires an exact trusted count/head checkpoint. An unknown newer database
terminal after a crash requires recovery coordination, not automatic trust adoption.

Direct manual ledger publication is also supported without a refresh policy.
Callers using refresh metadata must use ForecastRefreshLoop; the lower-level book
does not independently enforce membership in a matching refresh intent.

## Still pending

- Native gap/path/endogenous-time decoders and same-forward representation binding.
- Protected Frankie integration and its new disabled-path identity proof.
- Legacy BLD-1 requires a confidence enum; compatibility with the owner's category-free
  design remains unresolved. The projector is unchanged; winners are not labeled high.
- Actual calibration/selection evidence, timestamp resolvability, production cadence,
  instrument/calendar conventions and error tolerances.
- Production feed conformance/throughput/context validation, QSV producer wiring,
  remaining teacher columns, Granite serving and experiment orchestration.
- Execution controls and governed venue adapters.

Training, provider/market-data runs, held-out/OSS evaluation and live execution
remain parked. No workbook production gate is promoted by this increment. The
earlier workbook copy was unchanged at implementation checkpoint ccc7159d. The
subsequent closeout workbook now records this software slice while retaining open
production gates. See NEXT_CHAT_HANDOFF_20260914.md and CLOSEOUT_VERIFICATION_20260914.md.

## Review and rollback

The using-agent-skills workflow led to separate test-first implementation slices
and independent code review. The spec and ADR now remove the rejected categorical
policy and explain the remaining protected-boundary decision.

This increment is additive and not activated in the native runner or Frankie.
Rollback is to keep the producer/refresh integration unconnected; do not delete
evidence ledgers or rewrite protected controls. No production deployment occurred.
