# Native forecast and category-free Frankie review handoff

Repository: DavisAI1974/Markets. Remote branch: codex/boss-full-evidence-20260907.
Local branch: codex/boss-forecast-build-20260914. Checkout:
C:/Users/A/Documents/Codex/2026-09-14/b1-s-required-checks-passed-on/work/Markets-forecast-verify.
Start of this continuation: 9582660584c026394ec42175487aa08922a828a8.
Verify the current remote tip before continuing; never force-push.

## Authority and boundaries

The owner requires category-free publication: sole valid candidate or highest-ranked
comparable candidate, with no absolute score cutoff. Every registered horizon keeps
its original absolute target and append-only revisions. Ordinary new-data updates
are distinct from separately versioned model changes. The owner subsequently approved
a separate opt-in twelve-field Frankie interface with confidence null; ADR-0002
records that decision. Protected original BLD-1 still requires its enum.

Training, providers/market-data, held-out/OSS evaluation and live execution remain
parked. Synthetic software tests are permitted. No fitted checkpoint, empirical
calibration/accuracy/coverage, production throughput or B2_GATED completion is claimed.

## Previous stage: completed native forecast software

Implementation commits:

- ba3e8141: native gap, time-query path and autoregressive time/STOP heads.
- 7a285b35: explicit known-session conditioning.
- ce3b6a64: causal session manifests and immutable queryable artifacts.
- f6227b60: same-forward native B1 producer into the rolling ledger.
- eec0ded1: category-free draft and explicit legacy-interface compatibility guard.
- fbeea79bab89b93daa524daaf81adcb14ca4b7c6: previous verification/handoff.

The preexisting mapping, QSV attachment, internal diagnostics and comparable-candidate
rolling layer were retained, not rebuilt.

### Decoder and causal session semantics

forecast_heads.py consumes B1's final decision representation. Generic direction,
size or volatility heads are not relabeled as native forecasts. Gap and time-query
path heads produce ordered P10/P50/P90 values; the initial path is exactly zero.
Net is gap plus terminal, computed once. The preopen central estimate is not a
claim that marginal medians generally add to the marginal median of a sum.

The time decoder chooses successive times and STOP. STOP includes the true close.
Invalid, duplicate/unrepresentable or nonfinite emissions and exhausted budgets
reject. There is no sorting, truncation or endpoint interpolation to repair them.
Session conditioning uses time until open, duration, USD conversion and tick size.

freeze_medians() freezes median, timing and session-projection parameters and clears
stale gradients. A bounded synthetic optimizer test protects against weight-decay
drift while updating auxiliary tails. External trunk freezing is the caller's task.

forecast_session.py binds instrument/session, UTC nanosecond times, causal event and
receive cutoffs, price units, calendar/convention/source identities and known marks.
Postopen requires causal prior-close/open/current-anchor observations. Known values
remain tagged as observations. A past query without a certified mark fails; future
queries use the frozen residual path anchored at the current observed movement.
Manifest validation is not production approval of market calendars or conventions.

### Frozen artifacts and rolling generation

forecast_artifact.py retains exact CPU float64 native state, decoder tensors, source
and session provenance, model/input/arm identities and optional context/recurrence
receipts. Restore checks expected digest and exact canonical bytes and regenerates
the emitted forecast. Subsequent time queries do not forward B1 or consume its RNG.
Architecture, code, weights and runtime/arithmetic settings are bound. Incompatible
runtime restore is deliberately rejected rather than silently changing old answers.

NativeForecastRefresh.update in native_forecast_refresh.py uses one B1 forward per
generated target and takes its final representation and receipt from that same call.
Before generation the durable refresh intent binds actual source/input, native and
decoder identity, effective module settings and active session manifests.

The permanent target registry includes expired targets; only active targets require
current manifests. Current targets denote separately declared session closes, not
an invented cumulative multi-session net. A new-data update appends revisions at
unchanged targets and keeps model identity unless the model/decoder/settings change.
The producer emits one native candidate with no invented score/calibrated probability.
The existing comparable-candidate selector and no-floor publication policy remain.
The ledger is single-writer with trusted checkpoints and explicit uncertain-state
recovery. No external delivery or live schedule is introduced.

Previous acceptance: broad suite 914 passed, one CUDA-only skip; isolated checkpoint
suite 11 passed. Combined 925 passed, one skip. The 54 new focused checks overlap
these totals and must not be added again.

## Current stage: approved nullable interface and verified consumer

Committed interface implementation:
bdd76636806d602ef206c9cebc51f28b66369010.
Ledger-consumer implementation: 230c6480. This handoff is a descendant
documentation commit; resolve and verify the final tip from branch history.
Both implementation stages are complete for independent review. The chat's
temporary instruction to wait for the consumer completion no longer applies.

### Explicit compatibility decision

frankie_category_free.py introduces BOSS_FRANKIE_CATEGORY_FREE_V1 and
BOSS_FRANKIE_CATEGORY_FREE_ADAPTER_V1. Its payload retains exactly:

specialist, group, date, guessed_net_usd, overnight_gap_usd, path_p50_curve,
reasoning, plays_fired, plays_stood_down, confidence,
state_defects_and_gaps_reported, disposition.

Confidence is strictly JSON null. Enum strings, numbers, booleans and string null
reject. Contract/adapter/artifact/optional publication identities live in the
transport stamp, not a thirteenth payload field. Original BLD-1 is unchanged and
intentionally rejects the new record. Direct construction of a CategoryFreeRecord
validates a value; it is not proof that the verified projection route was called.

forecast_bridge.py defaults to the exact legacy callback before native imports.
Enabled routing restores the trusted artifact and regenerates its projection before
accepting prepared values. Schema/accounting checks alone were insufficient: changing
gap and net together could otherwise borrow an existing artifact digest.

The bridge uses supplied Frankie metadata and does not invent reasoning, plays,
disposition or execution authority. Ordinary ABSTAIN may retain a valid forecast.
S121 date/clock/accounting checks remain, including compact/ISO date preservation,
the terminal 24:00 sentinel and rejection of incompatible offset/multi-day clocks.

### Consumer flow and trust boundary

frankie_forecast_consumer.consume_forecast is separately opt-in. Disabled calls
return the exact legacy callback result without reading the book or validating
enabled-only metadata. Enabled calls require all eight existing metadata fields.
Invalid caller metadata raises; specialist/date context is not invented.

Enabled flow:

1. Obtain the requested historical receipt through RollingForecastBook.publication.
   This verifies the retained single-writer journal against its trusted head/count.
2. Restore the selected native artifact using the candidate identity.
3. Require complete canonical context and recurrence receipt structures and supported
   schemas. Reconstruct the existing order-sensitive context packet and check its
   recurrence packet hash, accepting the plain and QSV-bound packet conventions.
4. Check target instrument/time, source event/receive cutoffs/hash and experiment arm.
   Check native/execution/decoder identity against the publication's model hash.
5. Regenerate the approved projection and return the immutable stamped record with
   the exact publication receipt identity.

No model forward, provider access, delivery, execution, scheduling or Memory A write
occurs. Historical receipt reads remain stable after later revisions and verified
restart. Hashes establish consistency relative to trusted ledger/artifact roots;
they do not independently prove real-world provenance or authenticate a malicious
replacement of the entire trusted root.

Known fatal metadata defects, absent publications/providers, malformed artifacts,
receipt mismatch, altered journal state, timeout and caught storage/runtime failures
produce a complete safety abstention: zero amounts, the existing zero curve, no plays,
confidence null and explicit defect reasons. Missing calibrated probability or a low
comparative score alone does not cause safety abstention.

### Review and regression steps

Each slice received focused synthetic tests and independent review before commit.
Earlier review fixed optimizer median drift, snapshot activation/runtime gaps,
expired-target blockage, effective native setting drift, compact dates and
coarse-quantum DST acceptance. Interface review fixed coherent numeric payload forgery.

Consumer review reproduced an inconsistent recurrence packet accepted under a newly
hashed artifact, plus uncaught absent-provider/malformed-deserialization failures.
Failing regressions were added first, then packet linkage and narrow parsing-error
normalization fixed them. Actual QSV-attached native generation also has a positive
consumer regression, rather than merely testing a fabricated receipt.

Final verification at implementation commit 230c6480: broad suite **951 passed,
one CUDA-only skip** in 154.84 seconds. Separate checkpoint suite **11 passed**.
Combined: **962 passed, one skipped** across the two processes.
The current stage adds 19 interface and 18 consumer tests (37 total) over the
previous 925-pass checkpoint; focused tests overlap the suite totals.
Independent review closed both consumer findings and independently reran all
18 consumer tests. No required findings remain for the implemented slices.
Python compilation and Git whitespace checks passed; the control fixture remains LF.

## Verification commands

From the repository root, in the LF checkout:

```powershell
$env:PYTHONPATH='.;research/kalshi/frankie_boss;research/kalshi/frankie_boss/tests'
python -m pytest research/kalshi/frankie_boss/tests --ignore=research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py -q --tb=short
python -m pytest research/kalshi/frankie_boss/tests/test_benchmark_checkpoint.py -q --tb=short
git diff --check
```

The checkpoint tests require their own process because they check dependency
isolation. Focused counts overlap the broad suite. CUDA coverage is not claimed.

## Preserved files and remaining work

Original Frankie/S121/spawn.py, B0/B1 controls, context runner, C15/QSV, raw evidence,
replay and Memory A source files remain unchanged by these native/interface stages.
The existing closeout workbook remains byte-identical with SHA-256:
8862589effeee8ccb745dba6fe97a270921571c5524bd8d1b98df04f03817b23.

Production controller/service wiring and deployment acceptance remain open: the
enabled consumer is callable software, not a deployed production controller.
Other remaining work includes source conformance/wiring, QSV producer wiring and
throughput, six teacher columns, frozen Granite shadow serving, paired experiment
orchestration/single reveal and execution controls/ledger/reconciliation/adapters.
Production manifests, fitted models, empirical calibration and timestamp-noise
evidence remain unaccepted. G15 stays Partial/OPEN; production B2_GATED is incomplete.

Runtime pinning and full-journal verification favor strict software reproducibility.
Repeated artifact reconstruction and linear historical lookup have unmeasured cost.
Any future optimization must preserve trusted-head checks and old artifact semantics.
Rollback keeps the opt-in paths disconnected and retains all evidence and forecasts.

## Suggested independent review

Please inspect causal clocks/units, observed-versus-forecast handling, quantile/net
semantics, endogenous timing, snapshot/runtime coverage, retry identity, retained
revisions, null-contract separation, calibration-versus-integrity failures and
trusted-root assumptions. Distinguish required correctness fixes from optional
improvements, with file/function references and concrete reproductions. Do not run
parked training, providers, held-out evaluations or execution.
