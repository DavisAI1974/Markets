# Expanded candidate: scientific readout of committed results

This is an interim analysis of saved outputs, not final suite completion. The
readout contains 708 completed main-model/history metrics across all 63 cohorts
and 1,386 completed source-block ablation metrics: 2,094 of 2,097 mandatory keys.
Three depth-5 signed-price fits (60, 600 and 3,600 seconds, fold4) were still running
at collection. All 189 scheduled neural configurations were present. C/D fitting
and verified backups were complete; their callbacks remained available for reuse.
No new numerical fit, PCA or original final postprocessor was launched for this
readout. A's sole finalization and full final verified backup remain mandatory.

The main finding is a distinction between predicting activity/movement size and
predicting signed price change. The former show useful research leads; consistent
signed-price forecasting gains have not emerged. All evidence remains one retained
October17-18,2023 market day with selected overlapping contexts. Full semantic
coverage remains NOT_PASSED. V3 remains frozen.

## Collection and calculation

SSM main metric command ced71523-289e-42a6-a87b-b48b185e2dc3; source-block read
bd930785-858d-4209-a349-b6ad9a6cdb68; median benchmark read
8509fb8b-0b1d-42da-906f-ac5a0f2e881d. All four main and ablation invocations
succeeded. Initial diagnostic-only main read ad711376 failed on an omitted helper
import path; no numerical work was altered. The corrected read succeeded.

Only coordinator-committed task keys and their small metric CSVs were read; active
fits, raw matrix and databases were untouched. Source artifacts and failed/repeated
attempts retain their existing authority. No benchmark was substituted for a fit.
Saved labels/sample metadata were used to calculate training-only medians with the
original integer-time quarter boundaries, family purge, horizon purge and600-second
embargo. Train/test counts and original frequency/mean/zero benchmark MAE reproduced
within1e-12 across63cohorts. Scores below weight folds by held-out row count.
No significance test or independent-trial interpretation is made.

All columns, source bundles, benchmark values and the reproducible local calculation
are in tasks/family-research-20261022/candidate-*-20261023.* and
summarize_candidate_readout.py. The same shallow tree is used throughout the main
tables; this is not a selection of a different winning model at every horizon.
Quantile-tail models are excluded from point-forecast rankings.

## Predicting the size of the net midquote move

Outcome is the absolute endpoint-to-endpoint midquote change, not path range or
realized volatility. Percentages below are MAE reductions against a training-median
forecast. Positive means lower error. Folds are three chronological test segments
within one day, not three independent days.

| Horizon | Shallow-tree MAE reduction | Folds with lower MAE | Held-out rows |
|---|---:|---:|---:|
| 1second | -0.81% | 1/3 | 1,825 |
| 5seconds | 3.07% | 2/3 | 1,790 |
| 20seconds | 6.23% | 2/3 | 1,762 |
| 1minute | 1.65% | 1/3 | 1,745 |
| 2minutes | 2.45% | 2/3 | 1,749 |
| 5minutes | 6.00% | 2/3 | 1,712 |
| 10minutes | 11.45% | 1/3 | 1,759 |
| 30minutes | 17.11% | 2/3 | 1,714 |
| 1hour | 10.56% | 3/3 | 1,696 |

The ten-minute aggregate gain is concentrated in one fold; the one-hour gain is
more consistent across the three within-day folds. Broader day trends and overlapping
horizons remain plausible contributors. These are candidate associations, not proof
that families cause the later move or that magnitude forecasts can be monetized.

## Predicting a first-observed family within a horizon

| Horizon | Frequency Brier | Shallow-tree Brier | Relative Brier reduction | Folds improved |
|---|---:|---:|---:|---:|
| 2minutes | 0.156431 | 0.146995 | 6.03% | 3/3 |
| 5minutes | 0.070316 | 0.066727 | 5.10% | 3/3 |
| 10minutes | 0.011771 | 0.012519 | -6.36% | 0/3 |

Brier is mean squared probability error, not accuracy. These selected contexts
cannot be interpreted as population occurrence hazard or all-market probabilities.
At ten minutes TabM improves Brier4.49% pooled, but only1/3folds. No universal winner.

## Signed direction remains weak

The shallow tree loses to zero-change MAE on8/9horizons. Its only pooled gain versus
zero is0.21% at one hour, improving just1/3folds. At two minutes it is3.56% worse;
at ten minutes11.29% worse. NeuralTree is often closer to the zero benchmark, but
does not establish consistent directional superiority. Direction accuracy also
includes flat outcomes and cannot be treated as profitable long/short hit rate.

## Layer combinations are conditional and contradictory

Drop-group results refit the shallow tree after removing a complete correlated
source block. They describe incremental usefulness in that model/context, not
causal physical influence or independent feature attribution.

- Removing native timing worsens five-minute occurrence Brier9.37%, all3folds;
  removing it improves one-second signed-price MAE3.80%, all3folds.
- Removing full native book/depth/queue worsens20-second movement-size MAE1.29%,
  all3folds, but improves five-minute signed-price MAE4.44%, all3folds. It also
  improves five-minute occurrence Brier4.36%, all3folds.
- Removing external curve worsens30-minute magnitude MAE15.47%, all3folds and
  two-minute occurrence Brier6.07%, all3folds, yet improves ten-minute occurrence
  Brier5.84%, all3folds. Removing external weather worsens five-minute occurrence
  Brier8.85%, all3folds. One-day slow external series can proxy the day's evolution;
  their physical and cross-day effects are not established.
- History helps pooled ten-minute magnitude: MAE0.004869 with history versus
  0.005556 without. At two-minute magnitude removing history improves pooled MAE.
  This does not establish a universally useful lookback window.

## Neural and historical counterevidence

Added complexity does not consistently improve these fixed25-epoch configurations.
At two-minute occurrence, NeuralTree Brier0.186774, residualMLP0.289799 and
TabM0.197323 all lose to frequency0.156431. Several TabM signed-price and magnitude
errors are substantially worse than simple benchmarks. Some neural magnitude
configurations do better, so this is not a claim that all neural models fail.

The prior repeated residualMLP120-second/fold4 occurrence run remains an unresolved
reproducibility failure: maximum prediction difference0.431341; original logloss
1.568419 versus repeat2.915890. Original completed outputs remain canonical and
both attempts are preserved. Favorable residualMLP results need this qualification.

Earlier descriptive evidence remains informative: matched one-second reversals
were70-75%smaller using midquotes than transaction prices. That is consistent with
transaction-price bounce contributing, not proof of its entire cause.688/749family
starts overlap another within+/-120seconds, and740within+/-600seconds. Apparent
family effects therefore cannot be treated as independent observations.

Practical research interpretation: activity and movement-size/context conditioning
deserve more independent-day testing. A reliable directional trading rule, causal
layer synergy and executable profit after costs have not been established. The
final PCA/interaction/price-path summaries may refine the description; they do not
create an independent test day or resolve missing semantic certification.
