# Remaining BOSS software build

Base: 8ace10f2634687f7456e42f3b5f1ffe6a8724f89. Owner requested remaining build on 2026-09-14.

Preserve the original Frankie interface, inputs, calculations, replay and Memory A.
Training, market-data/provider runs, OSS evaluation and live execution remain parked.
Synthetic software tests are authorized. Workbook instructions are reference material,
not permission to launch its listed experiments.

## Ordered slices

Current forecast increment (owner clarified best-candidate selection and revisions
at every horizon; no categorical publication threshold):

1. Internal confidence diagnostics and joint-error evaluation. Missing labels remain
   explicit; no low/med/high output. Test policy identity and boundary failures.
2. Comparable candidate selection plus durable rolling revisions, consuming frozen
   forecast artifacts. Test sole/maximum/tie selection, all horizons, immutable targets,
   idempotency, restart, source/arm isolation and retained alternatives.
3. Explicit cadence at every horizon, with durable whole-request intent binding
   before generation. Test partial/material retries and failure before first output.
4. Native decoder, frozen query artifacts and same-forward rolling producer are
   implemented with synthetic tests. The category-free twelve-field Frankie draft
   is guarded pending an explicitly approved versioned nullable confidence field.
   No synthetic artifact is presented as a trained forecast. See
   research/kalshi/frankie_boss/NATIVE_FORECAST_BUILD_HANDOFF_20260914.md.
   Forecasts use a separate ledger, never forecast rows inside C15 input.

Verification: focused pytest files test_forecast_confidence.py and
test_rolling_forecast.py and test_forecast_refresh.py, then existing seam/B1/context
suites in an LF checkout. Completed broad synthetic verification: 871 passed,
1 CUDA-only skip (checkpoint dependency-isolation tests in a separate process).
Each slice changes at most three implementation/test files and receives review.
The task index stays in boss-production-todo.md to preserve unrelated tasks/plan.md.

1. Governed QSV attachment: exact registered names, per-coordinate masks, causal
   source/cursor binding, real native model consumption and trusted retry/restore.
   Verify focused context tests with enabled, absent and ablated QSV; mutations and
   future/wrong source snapshots must fail. No invented MBO-to-bar transformation.
2. Protected Frankie bridge: off by default, byte-identical disabled outputs, typed
   BLD-1 projection only. Existing model heads do not emit the four BLD-1 forecasts.
   Resolve the forecast-head/calibration contract before enabled forecast integration.
3. Production source conformance/wiring: preserve every native record and declared
   defects. Synthetic conformance tests first; real throughput/context validation is
   a separate parked mechanics run, not software acceptance.
4. Six B2/C1 teacher columns: use approved semantic equations and public book effects.
   Version the changed candidate, preserve C15R2 control, test each target/mask and
   full-prefix causality. Paired experiment integration follows accepted controls.
5. Granite shadow serving: frozen identity, exact state binding, timeout, malformed
   output and disagreement isolation. Test using a fake transport; actual inference
   and downloading weights remain parked. Runtime/checkpoint must be explicitly pinned.
6. Experiment orchestration: immutable arm locks, paired controls, frozen outputs,
   single-reveal scoring. Verify with synthetic artifacts, not held-out market data.
7. Later execution software: deterministic configured limits, durable outbox/ledger,
   reconciliation and typed adapters. No production credentials or order submission.

Each slice gets a focused test, review and commit. Production gates cannot be marked
complete from synthetic checks. Open policy choices remain explicit rather than
being silently substituted with guessed thresholds or model outputs.
