# SPEC: Native BOSS forecast and confidence contract

Status: implementation in progress; not fitted, calibrated, or production-approved.
Date: 2026-09-14. Capability id: `native-forecast-confidence`.
Code baseline: `25db5c8b6c5e9da2872f1870c77fca82dee1731f`.
Authority: the owner's request to design the missing forecast and confidence.
The prior build workbook and historical handoffs are reference material, not permission to run experiments.

## Owner revision: rolling best-supported forecasts (2026-09-14)

The owner's subsequent instructions supersede the categorical confidence policy
below: do not use low/med/high categories or an absolute confidence cutoff to
decide publication. Publish the sole valid candidate, or the highest-ranked of
multiple comparable candidates, with scores retained internally. An unavailable
calibrated probability is not a reason to withhold a valid ranked forecast.
Raw scores from unrelated scorers are not comparable: alternatives use one frozen
ranking policy/scorer for the same target, as-of source state and experiment arm.
Deterministic ties use candidate id order. No selection across blinded experiment arms.

Every registered horizon is revisable, including all intermediate horizons.
Targets are stable absolute times; remaining horizon decreases with each new as-of.
New forecasts append revisions and never replace earlier predictions or move the
target. A revision records source, model, ranking-policy and predecessor identities.
Ordinary new-data revisions are distinct from separately versioned model changes.
Near-term targets can update more often under a declared cadence policy; there is
no hardcoded two-horizon special case and no invented live schedule in this build.

The rolling lifecycle accepts immutable, already-validated native forecast artifact
bytes. It does not manufacture forecasts or extend single-session BLD-1 to multi-day
semantics. The existing protected projector remains untouched; any required legacy
confidence-field compatibility is separate from ranking and must not label every
winner 'high'. Empirical calibration must evaluate the selected-forecast pipeline,
including candidate count/generation/ranking policy, not only individual candidates.

## 1. Objective and assumptions

Supply the four missing `InternalBLD1Heads` quantities from the native BOSS
representation, without changing the protected twelve-field Frankie BLD-1 interface.
Forecast confidence describes forecast reliability, not trading permission or profit.

Assumptions proposed for review:

- S120/S121 remains authoritative: endogenous output timestamps, full-session path,
  path first value zero, terminal equal to net less gap, and forecast-backed ABSTAIN.
- B0/B1 control weights, existing typed heads, recurrence/halting, raw input handling,
  Frankie calculations, replay, and Memory A remain unchanged.
- Forecast heads are an additive, opt-in candidate. Granite never supplies or replaces them.
- An approved instrument/session/label manifest supplies units, calendar and anchor
  conventions. We do not guess a futures multiplier, exchange close or price source.
- Numerical confidence bands below are proposed policy, not measured performance.
  Training, market-data runs, held-out scoring and execution remain parked.

Forecast generation and its reliability label form one consumer-facing capability;
calibration has a one-way dependency on a frozen forecast, never the reverse.

## 2. Public semantics and accounting

Let `Cprev`, `O`, `C` be the certified prior close, session open and session close.
Let `u` be the manifest's exact conversion from native price units to Frankie's
existing USD convention. This is forecast price movement, not position-sized P&L.

Offline targets:

- Gap: `G = u * (O - Cprev)`.
- Cumulative path: `P(t) = u * (mark(t) - O)`.
- Full-day net: `N = u * (C - Cprev) = G + P(close)`.

`mark(t)`, auction/settlement selection, revisions, missing observations and stale
marks must use the existing approved label convention. Mixing a settlement close
with a last-trade path endpoint is forbidden. Anchor inconsistency invalidates the
label; it is not repaired by shifting or rescaling the path.

| Internal output | BLD-1 output | Definition |
|---|---|---|
| `overnight_gap_usd` | same | Conditional P50 gap before open; certified observed gap once causally available |
| `session_path_p50_curve` | `path_p50_curve` | Native, endogenous-time conditional P50 cumulative-from-open values |
| `session_net_usd` | `guessed_net_usd` | Gap output plus native path terminal, calculated once |
| `confidence_label` | `confidence` | Governed `low/med/high` forecast-reliability label |

**Median limitation:** before the open, the sum of marginal medians need not be the
median of the sum. Therefore the public net is a coherent central full-day forecast,
not a separately claimed marginal P50 net. The BLD-1 net field does not require that
claim. Do not train three independently constrained medians or overwrite the path
to reconcile them. Once the gap is observed, adding that known constant to the
conditional terminal P50 does preserve its median interpretation.

A path of pointwise conditional medians is not a statement that the whole realized
trajectory has 50% simultaneous coverage. Joint confidence is estimated separately.

## 3. Native decoder architecture

Use an additive `NativeForecastHeads` bundle with:

1. A scalar gap decoder.
2. A time-query path decoder `q50(z, t, session)`.
3. An autoregressive knot-time/STOP decoder choosing how many points and when.
4. Internal non-crossing gap/path quantiles for uncertainty auditing.
5. A separate downstream reliability scorer and calibrator.

The path decoder predicts each queried value directly from the causal representation
and known session coordinate. It does not interpolate between an already chosen
daily net and zero, average raw records, or generate a fixed clock-grid output.
Amounts are unconstrained finite real USD values, not `tanh(size)` proxies.
The existing `p_up`, `size`, `sigma` and evidence scores are not relabelled as forecasts.

Use the final `z_K` from the **same B1 forward** that produced its receipt. B1 already
exposes `B1Output.representation`; the context runner needs a candidate-only path to
consume that representation before constructing its external result. Do not execute
a second forward, reconstruct `z_K` from generic heads, or use future journal rows.
The gap/path/time bundle reads the final valid decision representation, consistent
with the existing last-state head boundary.

Freeze the control trunk/reasoner while fitting the initial additive decoder.
A later unfrozen candidate needs its own version and paired comparison; it cannot
replace or relabel the preserved B0/B1 controls.

### Endogenous times

Before locking temporal label resolution, produce a timestamp-quality report from
an authorized training/mechanics C15 journal partition. Separate event interarrival
deltas, receive deltas, event-to-receive latency, duplicates, reordering, timestamp
quantization and available clock-synchronization/uncertainty evidence, by source
and session. Interarrival gaps measure market activity, not clock jitter; latency
is not automatically timestamp error. Infer a jitter bound only with an identified
measurement model or suitable synchronization/reference evidence. If unavailable,
record "noise floor unidentified" and block a precision claim.

Lock timestamp quantum and event-matching tolerance no finer than demonstrated
resolvability (using a predeclared uncertainty bound/quantile and its tail-exceedance
rate), without rewriting raw journal times. Same-resolution label events form an
explicit tie group with preserved constituent counts. Do not charge sub-resolution
ordering to model error. This is a prerequisite for timing training, not permission
to run market-data analysis now.

The time decoder emits strictly positive next-time increments and STOP, conditioned
only on causal state, session metadata and its own preceding emissions. Mandatory
start and close are session anchors, not a canonical interior cadence. Optional
interior knot count and times are model outputs. Discretize once to the locked
timestamp precision; reject duplicates or unrepresentable times instead of sorting,
nudging or silently deleting them. An early STOP still emits the true close, never
a shortened session.

Proposed timing-training target: an unsmoothed directional-change event sequence
from the approved offline mark stream. Starting at the open, wait for a move of
`turn_delta_ticks`; then track the running extreme in that direction and mark
the first reversal of that size as the next confirmation event. Repeat, with
deterministic same-time tie handling. The research candidate uses one native tick;
a changed threshold is a new timing-policy hash, not an invisible runtime knob.
These are labels only, never an input-record filter or a substitute for retained evidence.

Fit next-event presence with binary log loss and next-event delay with median
pinball loss on positive-event examples, using chronological teacher forcing.
Freeze the timing decoder before fitting the path-value decoder. At inference,
times are generated free-running; never use realized future turning points.
This staged design keeps value labels evaluated at causally predicted query times,
rather than claiming that the median value at a realized future extremum is a
fixed-time P50. Timing accuracy and free-running knot coverage remain empirical
acceptance gates, not consequences of the architecture.

Every emitted knot value comes from the native value decoder at that timestamp.
Keep a frozen queryable forecast artifact for independent audit queries; no input
refresh or representation recomputation is permitted during later scoring.
Two endpoints alone do not establish full-path adequacy. If resource limits prevent
completion, issue a defect and safety fallback; do not truncate then append a close.
Do not add artificial wiggles to evade the existing A-86 linearity validator.

### As-of and time semantics

- Bind each call to one session, instrument, event cutoff, receive cutoff and source prefix.
- Before open, forecast both gap and path.
- After open, use the gap only if both anchors were available by the receive cutoff.
  Certified known path points are observations, identified internally as such; do
  not score them as successful forecasts. At as-of, anchor the future decoder to
  the certified current mark, with an explicitly versioned residual parameterization.
- Missing necessary anchors, unsupported session mappings or a completed-session
  request with no forecast horizon are unavailable-forecast states, not high confidence.
- Use timezone-aware absolute times internally. Serialize ET only at the protected
  boundary. Preserve S121's 20:00 wrap and terminal next-day 20:00/24:00 sentinel.
  Here `24:00` is the S121 close sentinel, not ordinary midnight.
- Verify each authoritative session against that representable clock. DST/holiday
  or early-close ambiguity must fail explicitly, not be mapped onto an invented schedule.

## 4. Training labels, losses and causal isolation

Price labels are distinct from C15R2 auxiliary teacher targets. The six unimplemented
B2/C1 columns remain ablated; this design neither fills them nor reads future
outcomes into the teacher, native input, QSV or Granite.

Fit gap and path values with `rho_0.5(y - prediction) = 0.5 * abs(y - prediction)`.
Pinball loss is a quantile-estimation objective; it is not proof of achieved
calibration or forecasting skill [1]. Enforce initial path zero by construction,
derive net from the terminal, and grade net error separately. Do not add an
independent net-median objective that silently changes the promised path estimand.

Train path values at model-generated knots and independently selected audit times.
The latter use a locked, seeded, outcome-independent sampling scheme across the
session, plus the terminal; they are **not** the emitted output grid.
Do not select only easy knots or evaluate only daily net. Record the query set,
mark convention, missing-label mask and source identifiers. Do not interpolate raw
prices to manufacture targets. Any price-at-time carry convention must already be
part of the approved label definition, with its permitted staleness.

Use session-level weighting before combining examples, so a session with many
updates does not silently count as many independent sessions. Loss weights, timing
precision, query count and optimizer settings are required versioned training
configuration. No run may use a hidden default. Missing labels are masked with
receipts; they are neither zero targets nor successful confidence outcomes.

Chronological sequence for the initial frozen candidate:

1. Timing-decoder training partition.
2. Path/gap training partition with frozen timing policy.
3. Auxiliary quantile fitting with frozen median, then reliability-scorer training
   on a later disjoint partition, using fully frozen forecast predictions.
4. Independent probability-calibration partition with frozen scorer.
5. Independent validation partition used only to accept/reject the complete lock.
6. Separately locked single-reveal evaluation.

Group by whole session and purge overlapping target horizons at every boundary.
All training labels must be available before the following partition's forecast
cutoff. No random row split, same-session leakage, calibration on fitted predictions,
or refit after looking at held-out outcomes. Rolling-origin alternatives require
a separately locked protocol, not an ad hoc mixture of different forecasters.
The currently reserved held-out dates cannot double as training/calibration data.

## 5. What confidence means

Define one immutable `ForecastErrorPolicy` with finite positive USD tolerances
`tau_gap`, `tau_net`, `tau_path`, label-convention hash and audit-query protocol.

For each frozen prediction, the binary success event is:

`E = abs(Nhat - N) <= tau_net
     AND (gap already observed OR abs(Ghat - G) <= tau_gap)
     AND max_future_query abs(q50(t) - P(t)) <= tau_path`.

Queries include all emitted future knots, the terminal and the independent
outcome-independent audit set. Thus omitting a difficult output knot cannot alone
improve the confidence label. This event covers those declared queries, not every
instant between them. No tolerance is inferred from the projector's $1 accounting
tolerance, from a desired success rate, or from future session volatility.

If a required label is missing, `E` is unavailable rather than false or true.
Report missingness by session and regime; excessive missingness blocks promotion.
Uncertainty is about the remaining unknown horizon: previously observed prices do
not pad the success count. Confidence is neither `P(up)`, `1-sigma`, model
self-description, recurrence depth, nor `P(profitable trade)`.

Fit a compact reliability scorer on detached causal native features, the frozen
forecast outputs, horizon/session phase and causal quality masks, targeting `E`
with binary log loss. It cannot alter forecasts, knot selection or B1 halting.
Pass its scalar logit through a separately fitted sigmoid calibrator [2].

Proposed policy `forecast-confidence-v1`:

| Eligible calibrated probability p(E) | Public label |
|---|---|
| `p < 0.60` | `low` |
| `0.60 <= p < 0.80` | `med` |
| `p >= 0.80` | `high` |

These are proposed reporting bands, not trading thresholds or empirical claims.
The calibrated probability stays internal; the projector receives only the resolved
enum and remains unchanged.

### Eligibility and failure states

A probability is eligible only when the exact forecaster/scorer/calibrator/policy
hashes match, the calibration artifact has passed its independent acceptance report,
and the current instrument, phase, horizon and input-quality state fall within its
declared support. Merely having a file or a finite sigmoid output is insufficient.

The acceptance lock must specify minimum distinct-session support per reported band,
maximum reliability deviation, confidence-interval procedure accounting for
within-session and serial dependence, missing-label limits and expiry/drift criteria.
Inspect reliability diagrams plus log loss/Brier scores; those scores alone do not
isolate calibration [2]. Report coverage and errors for every supported stratum,
including abstained forecasts. Do not claim certification from two evaluation days.

Those empirical gate values and USD tolerances are deliberately **required but
unbound** until an approved label/instrument and validation protocol exist.
Implement validation rejecting an incomplete production policy; do not fabricate
numbers to turn this design into a passed production gate. Synthetic tests may
supply explicitly synthetic tolerances and acceptance artifacts.

- Missing, expired, mismatched or unsupported calibration: public `low`, internal
  `probability=null`, explicit reason such as `UNCALIBRATED` or `OUT_OF_SUPPORT`.
  This sentinel does not assert that a measured probability is below 0.60.
- Invalid/missing forecast, source mismatch or timeout: existing complete zero
  safety ABSTAIN, with defects. Never synthesize a forecast from Granite.
- Valid forecast plus ordinary trading ABSTAIN: preserve net/gap/path and the
  independently resolved confidence. Confidence alone neither CALLs nor grants execution.
- Any additional production ban on uncalibrated trading belongs to the separate
  governance gate, not an undocumented change to BLD-1.

## 6. Research-driven audit and preregistration requirements

The owner's 2026-09-14 research notes motivate these checks. Their earlier numerical
findings are not independently reproduced here and are not BOSS evidence.

### Confidence must add information, not another scale

On the locked validation set, and later the single-reveal held-out set, publish
pairwise Spearman correlations of the continuous reliability logit and calibrated
probability against signed/absolute net, signed/absolute gap, path terminal, path
maximum absolute excursion on the locked diagnostic queries, interval widths,
knot count, and each existing scalar internal head. Vector heads/path outputs use
predeclared components/query coordinates, not whichever summary looks persuasive.
Report the complete matrix as well as instrument/phase/horizon strata.

Use average ranks for ties. Report pairwise valid row counts, missing counts,
constant-input flags and dependence-aware uncertainty. A constant low fallback
has undefined correlation, not evidence of independence [3]. Correlation near
either +1 or -1 is a redundancy warning, not a proof that confidence has no useful
information; low correlation alone is not proof of added value either.

Proposed preregistered diagnostic flag: absolute Spearman >= 0.95. This is a review
threshold, not a trading/calibration threshold. No run can quietly remove a flagged
comparison. Log all underlying coordinates and their shared transformations.

Primary added-information comparison:
- Candidate: the native-feature/quality-aware reliability scorer.
- Control: a separately fitted forecast-only scorer using exactly the frozen
  public forecasts, internal scalar heads, declared query values/interval widths,
  knot count and the same horizon/phase metadata, but no extra native representation
  or input-quality features.
- Both predict the identical joint event E, use the same scorer/calibration training
  partitions and fixed fitting budget, and are evaluated on identical eligible rows.
- Statistic: session-mean binary log loss(candidate) minus log loss(control), then
  equal-weight mean across the locked sessions. Lower is better; do not replace
  the difference with a ratio after seeing results. Handle probability endpoints
  with a predeclared numerical clipping rule applied equally to both.
- Claim of added predictive information requires the upper end of a predeclared
  dependence-aware 95% interval for that difference to be below zero, alongside
  calibration/support gates. Otherwise report "added information not established."
  No extra independent-measurement claim is inferred from architecture alone.

### Quantile coverage is a family of curves

Add internal gap/path quantiles at the explicit levels
`[0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 0.95, 0.99]`.
This is a designed quantile grid, not discovered evidence or a claim about every
possible quantile. Retain exactly P50 at the public seam.

After fitting and freezing the median decoder, fit an auxiliary ordered quantile
bundle around it using nonnegative adjacent gaps and quantile-specific pinball
loss `rho_a(e) = e * (a - 1[e < 0])`. Freeze the median and its shared features
during this fit; tail losses must not redefine the public P50.
Never sort crossing outputs after prediction to conceal an invalid model.
Known observations can collapse quantiles, but are excluded from forecast coverage.

Report per quantile and horizon: empirical below-quantile coverage, pinball loss,
sample/session count and uncertainty. Because USD marks can be discrete, show both
`P(Y < q_a)` and `P(Y <= q_a)`; the target quantile level can lie between them.
Report interval coverage and width at nominal 20/40/60/80/90/98% using the matching
symmetric quantile pairs [4]. Tail support failures remain visible. Pointwise
intervals do not imply simultaneous full-path coverage.

Gap/path quantile sums are not a preopen net-quantile distribution. Do not display
a net coverage curve from summed marginal quantiles. A future directly trained
internal net-distribution head would be a separately specified addition; current
net is graded by error and the joint event E.

Separately show binary E reliability over probability bins
`[0,.1), [.1,.2), ...,[.9,1]`, explicitly including empty bins and a missing/
uncalibrated bucket. These curves do not become a single "calibrated" flag in the
research report even though runtime needs an eligibility decision.

For every view, reconcile:
`eligible universe = valid scored rows + excluded rows by mutually exclusive reason`
and `valid scored rows = sum(disjoint bin counts)`.
Multi-label defect tags are additional, not summed as if exclusive.
Quantile curves reuse rows across levels: reconcile each level, never sum all levels
as independent observations. Record planned/emitted/missing query counts separately.
Keep empty bins, undefined metrics and zero support in the exported table. This
implements the Audit-sheet accounting principle without claiming to have inspected
the user's research workbook or reproduced its results.

### Declare grids, groups and pairing before outcomes

The acceptance manifest contains exact session ids, assets, as-of/horizon schedule,
audit/diagnostic query sampling law and seed, all quantile/probability bin edges,
regime definitions from causal information, metric formulas, exclusions, uncertainty
method and block lengths, comparison pairs and acceptance thresholds.
It must be complete and hashed before validation outcomes are examined.

There is no fixed emitted path grid. Evaluation schedules are separately declared
experimental choices. If geometric horizons are used, store every value, ratio,
index, units and log base and label plots accordingly. A log-horizon versus index
line is mechanical; a horizon-dependent performance trend is not automatically
affine merely because the horizon grid is geometric. Compare against the specified
design-only null/benchmark before calling a pattern a finding.

Same replay session/as-of under two model arms is paired. Horizons from the same
replay are correlated repeated measures, not extra independent sessions. Resample
whole session blocks, preserving arm/horizon/query pairing. Different assets are
between-problem comparisons unless an explicit matching design exists; preserve
shared-date dependence when aggregating across assets. Declare whether draws are
shared deliberately; derive seeds from immutable experiment/replicate/pair ids.
Never reseed inside a regime loop without recording the induced coupling.

Multiple secondary tests/strata need a predeclared multiplicity treatment. Exploratory
charts stay exploratory and cannot alter the primary acceptance statistic. A failed
lock gets a new candidate and a fresh permitted validation partition, not repeated
tuning on the same reveal.

### Support dynamics and suspicious shared failures

Distinguish append-only journal retention from active finite-context inclusion,
QSV coordinate masks, enabled/ablated features, and accepted/rejected shadow output.
Journal evidence can remain retained while model-context or gate membership exits.
Do not assert that all these supports are monotone because C15 retains evidence.

Log per stable member id and support kind: observation clock/cursor, first entry,
each exit/re-entry, current membership, cumulative active observation count,
elapsed active duration, last transition and reason. State the observation clock
and denominator. Count-based and elapsed-time persistence are different measures.
Under proven monotone inclusion, derive any redundancy between entry position and
duration rather than promoting it as two independent diagnostics; with exits,
retain both histories.

If several diagnostics fail together, inspect shared upstream causes: row masks,
source/time joins, unit conversion, reused normalizers, clipping, regime selection,
seed coupling and denominator/support changes. Independent marginal correlation
does not rule out a shared upstream failure. Synthetic tests must inject one such
shared fault and show the lineage/audit ledger identifies the common cause.

## 7. Interface, provenance and retry contract

Proposed internal objects are immutable, validated and schema-versioned:

- `ForecastSessionManifest`: instrument/contract, price scale, USD convention,
  tick size, anchor/mark source, calendar, UTC boundaries, ET mapping and as-of cutoffs.
- `ForecastBundle`: gap/path/time/auxiliary-quantile weights and architecture, complete
  native model identity, training-label/split hashes, timing/noise-floor policy and
  runtime precision.
- `ForecastArtifact`: native query state, emitted points, known/forecast flags,
  source/input hashes, all model/policy identities and deterministic payload digest.
- `ConfidenceArtifact`: frozen forecast/scorer identity, calibrator parameters,
  error policy, preregistered comparison/grid/seed manifest, support/acceptance
  report, validity interval and provenance.

Illustrative boundary usage, not code implemented by this spec:

```python
heads = InternalBLD1Heads(
    session_net_usd=gap_usd + path_points[-1][1],
    overnight_gap_usd=gap_usd,
    session_path_p50_curve=tuple(path_points),
    confidence_label=confidence.label,
    internal_only={
        "forecast_probability": confidence.probability,
        "confidence_status": confidence.status,
        "forecast_artifact_hash": artifact_hash,
    },
)
```

Keep existing `FrankieProjector.project_internal` validation. Other BLD fields
retain their protected population path; no invented reasoning or play activations.
All twelve fields must still be present. Operational diagnostics must also appear
through the existing defects channel without introducing a thirteenth public field.

Extend enabled retry identity to include decoder weights, inference/runtime settings,
session/anchor convention, knot policy, error policy, scorer/calibrator and trusted
artifact digest, in addition to existing native/QSV/context hashes. Model mutations
must be detected from actual content, not an unchanged version string. Bind this
identity **before** a forward attempt; changing anything after failure rejects retry.
Restore requires the same trusted artifacts. Persist audit-query state before
outcome reveal; querying a frozen artifact later is scoring, not refreshed inference.

Disabled mode must bypass decoder/calibrator loading and validation entirely.
No extra RNG use, model calls, state writes or changes to legacy payload bytes,
receipts, clocks, calculations or Memory A. Existing B0/B1 state dictionaries and
control hashes must not acquire additive parameters.

## 8. Files, commands and verification

Proposed additions under `research/kalshi/frankie_boss/`:

- `forecast_heads.py`: additive native gap/path/time decoders.
- `forecast_contract.py`: immutable manifests/artifacts, unit/time validation.
- `forecast_confidence.py`: policy, scorer/calibrator attachment and eligibility.
- `tests/test_forecast_heads.py`, `tests/test_forecast_confidence.py`,
  `tests/test_forecast_bridge.py`: synthetic contract and preservation tests.

A later opt-in context/Frankie bridge consumes these providers. Do not edit
`spawn.py`, S121, historical artifacts or unrelated task files to fit the new design.
Use Python dataclasses, explicit exceptions, existing PyTorch and float64 native
precision. Fit tooling can be specified later; no new dependency is needed for
sigmoid inference. Freeze Python/PyTorch/device/determinism settings per artifact.

Existing baseline verification, from repository root in PowerShell:

```powershell
$env:PYTHONPATH='.;research/kalshi/frankie_boss;research/kalshi/frankie_boss/tests'
python -m pytest research/kalshi/frankie_boss/tests/test_seam.py research/kalshi/frankie_boss/tests/test_b1_reasoner.py research/kalshi/frankie_boss/tests/test_context_session.py research/kalshi/frankie_boss/tests/test_context_qsv.py -q
git diff --check
```

Future focused command, only after these tests exist:

```powershell
python -m pytest research/kalshi/frankie_boss/tests/test_forecast_heads.py research/kalshi/frankie_boss/tests/test_forecast_confidence.py research/kalshi/frankie_boss/tests/test_forecast_bridge.py -q
```

Byte-pinned fixtures require an LF checkout. On Windows, verify with
`git ls-files --eol tests/fixtures/boss_control_beb548b8/trunk_v1.py`.
A CRLF conversion changes the audited byte hash; do not change the expected hash
to make that checkout pass. Use a separate LF checkout for these checks.

No build command, training run or new runtime test is claimed by this design-only change.

Required implementation acceptance cases:

1. Native representation reaches gap, time and path computation in the same forward;
   bounded synthetic perturbations and gradients demonstrate each connection.
2. Exact initial zero and net = gap + terminal; positive/negative gap, round-trip
   path, fractional times, midnight wrap and S121 terminal sentinel all validate.
3. Times vary with native state; free-running STOP/count works; duplicate, unordered,
   excessive-budget and non-finite outputs fail; no fixed-grid or net-only shortcut.
4. Preopen versus known-open behavior and causal mark attachment are correct.
   Later arrival/revision never changes an already bound earlier forecast.
5. Future-label perturbations cannot change inputs, model forecasts or teacher
   attachment. Train/calibrate/validation session/horizon overlap is rejected.
6. Boundary labels at 0.60 and 0.80 are exact; malformed policies reject; absent,
   stale, mismatched and unsupported calibration gives low/null plus a reason.
7. Joint-event tests catch gap-only, net-only and path-only failure, missing labels,
   and sparse-output attempts to evade independent audit queries.
8. Valid ABSTAIN preserves forecasts; invalid forecast uses the complete established
   fallback. No probability/diagnostic field leaks across the twelve-field seam.
9. Failed-forward retry and restart reject every changed forecast/calibration/session
   identity. Late-bound policy changes cannot reuse an earlier attempt's receipt.
10. Disabled path remains byte-identical and RNG/state-write identical on both
    preserved trunk lineages; the B0/B1 preservation suites continue to pass.
11. Model-clock solver/time serialization and label-unit parity agree with Frankie.
    Synthetic accounting examples are not evidence of market forecasting accuracy.
12. Timestamp noise and market interarrival diagnostics stay distinct; unresolved
    precision blocks timing labels and all tie-group counts reconcile.
13. Redundant, anticorrelated and constant synthetic confidence cases are detected;
    the declared paired log-loss comparison is invariant to input row ordering.
14. All quantile levels/bins, empty bins, missing labels and support strata reconcile;
    quantiles are ordered and tail fitting leaves P50 unchanged.
15. Repeated horizons preserve pairing; deliberate seed sharing is visible; support
    exit/re-entry and a shared upstream fault are exposed by the audit ledger.

**Software gate:** these cases pass under synthetic fixtures and independent review.
**Empirical gate:** trained checkpoint, label/units parity, free-running timing/path
accuracy, eligible calibration, production throughput/context acceptance and governed
paired evaluation. Passing the software gate does not pass the empirical gate.

## 9. Boundaries and unresolved production bindings

Always preserve native evidence, distinguish known values from forecasts, version
all policies, record exclusions, and fail explicitly on incomplete provenance.
Ask before changing protected interfaces/labels, unfreezing controls, selecting
production USD error tolerances, or launching any parked operational run.
Never train on held-out reveal data, fabricate confidence support, use Granite as
native authority, enable execution, smooth raw inputs, or quietly truncate context.

Required later bindings: approved instrument/anchor/mark manifest; actual decoder
weights and training protocol; empirical error/support/drift limits; authorized data
partitions; throughput/context result. These are explicit production prerequisites,
not unspecified meanings of the four designed outputs.

Decision rationale is recorded in `docs/decisions/0001-native-forecast-confidence.md`.
This specification is the design deliverable; implementation acceptance is still open.

## References

[1] Steinwart and Christmann, *Estimating conditional quantiles with the help of the
pinball loss*: https://arxiv.org/abs/1102.2101

[2] scikit-learn, *Probability calibration* (independent calibration data, sigmoid
calibration, and limitations of aggregate probability scores):
https://scikit-learn.org/stable/modules/calibration.html

[3] SciPy, *spearmanr* (monotonic association, ties/constant inputs):
https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html

[4] scikit-learn, *Prediction Intervals for Gradient Boosting Regression*
(quantile-specific loss and empirical interval coverage):
https://scikit-learn.org/stable/auto_examples/ensemble/plot_gradient_boosting_quantile.html

Repository authorities:
`research/kalshi/frankie_boss/frankie_contract.py`,
`research/kalshi/frankie_s121_curve_restore.py`,
`research/kalshi/frankie_boss/b1_reasoner.py`,
`research/kalshi/frankie_boss/context_session.py`.
