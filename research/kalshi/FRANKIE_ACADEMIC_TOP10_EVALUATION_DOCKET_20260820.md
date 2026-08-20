# Frankie independent academic top-10 evaluation docket — 2026-08-20

Status: **CANDIDATE EVALUATION ONLY.** This is Track B: an independent search
across primary university, conference, and journal sources. It is separate from
the 340-reference Geometric Deep Learning bibliography audit in
`FRANKIE_GDL_REFERENCE_EVALUATION_DOCKET_20260820.md`.

All ten papers are peer-reviewed. Ranking reflects likely value to Frankie's
current strictly causal NG/V4 research problem. It does not authorize
implementation, permanent Frankie mutation, a canonical paper-manifest addition,
trading, or play promotion.

## Ranked candidates

### 1. When to Classify Events in Open Times Series?

Achenchabe et al., [ACML
2023](https://proceedings.mlr.press/v189/achenchabe23a.html).

Why evaluate: ECOTS addresses early classification of recurring events in an
open, unbounded stream—the closest problem statement to predicting an instance
before its formal birth without assuming a prealigned curve.

First gate: on chronological event matching with false alarms counted on
non-event intervals, require positive median prebirth lead, at least five points
of event-macro-F1 gain over a fixed-horizon alarm, and no increase in false
alarms per session.

Boundary: target onset is evaluation-only. Never crop, align, or start model
input using the eventual birth time. The paper's stationary experiments require
a separate shift evaluation.

### 2. Early Time Classification with Accumulated Accuracy Gap Control

Ringel et al., [ICML 2024](https://proceedings.mlr.press/v235/ringel24a.html).

Why evaluate: the closest fit to an auditable first-lock wrapper. It calibrates
when a prefix classifier may stop while controlling its accuracy gap relative
to the full-stream classifier.

First gate: use purged chronological calibration. Require the one-sided 95%
upper bound on early-versus-full error gap to be at most one percentage point
while median lock occurs at least 20% before target birth or natural endpoint.

Boundary: the guarantee is relative to the full classifier, not truth. Neither
full-curve statistics nor post-lock observations enter prefix features.

### 3. Dynamic-DeepHit

Lee, Yoon, and van der Schaar, [*IEEE Transactions on Biomedical Engineering*
2020](https://doi.org/10.1109/TBME.2019.2909027).

Why evaluate: dynamically estimates competing event type and time-to-event from
accumulating longitudinal measurements. It is the strongest omitted analogue
for prebirth class and timing, although its evidence is medical rather than
market-based.

First gate: compare a strictly causal Dynamic-DeepHit-style lane with the
current separate target heads using time-dependent Brier score, event-type log
loss, calibration, median correct prebirth lead, and wrong-lock rate. Require at
least 2% relative integrated-Brier improvement without reducing prebirth
coverage at the fixed wrong-lock cap.

Boundary: birth, future covariates, future missingness, and eventual event time
are labels only. Censoring and competing outcomes are defined before test; no
clinical result is presumed portable to markets.

### 4. The Price Impact of Order Book Events

Cont, Kukanov, and Stoikov, [*Journal of Financial Econometrics*
2014](https://doi.org/10.1093/jjfinec/nbt003).

Why evaluate: supplies an interpretable OFI baseline combining limit orders,
market orders, cancellations, and depth—a stronger causal baseline than volume,
CVD, or one static queue ratio.

First gate: require the held-out coefficient to retain the expected sign on at
least 80% of instrument-days and improve Brier score by at least 2% over
trade-volume and price-only features.

Boundary: use contemporaneously visible best-quote events only. Flag stale or
crossed books, auctions, and feed gaps; never repair them with later state.
Equity results do not establish NG-futures transfer.

### 5. Deep Order Flow Imbalance

Kolm, Turiel, and Westray, [*Mathematical Finance*
2023](https://doi.org/10.1111/mafi.12413).

Why evaluate: stationary multi-level order-flow features are a direct academic
analogue for signed bid/ask dipole and exhaustion-pressure channels, and a
clearer challenger than raw book tensors alone.

First gate: against price-only and raw-book baselines, require at least 2%
relative OOT log-loss reduction on held-out instruments/days and nonnegative
cost-adjusted utility in every liquidity tercile.

Boundary: build flow only from messages available by decision time; fit scaling
on training history; prohibit revised books, future trade-sign inference,
overlapping random splits, and test-P&L horizon selection.

### 6. The Neural Hawkes Process

Mei and Eisner, [NeurIPS
2017](https://proceedings.neurips.cc/paper_files/paper/2017/hash/6463c88460bd63bbe256e495c63aa40b-Abstract.html).

Why evaluate: trades, adds, cancels, depletion, and target precursors become
typed events whose intensities evolve continuously between messages; learned
inhibition is especially relevant to exhaustion.

First gate: against event-count GRU and clock-time TCN baselines, require at
least 3% next-event NLL improvement and 2% target AUCPR improvement without
worsening event-time calibration.

Boundary: hidden state consumes only events available by the cutoff. No
bidirectionality, smoothing, later corrections, or future-derived same-timestamp
ordering. Continuous book/price values require an explicitly tested marked-event
extension.

### 7. Measuring the Resiliency of an Electronic Limit Order Book

Jeremy Large, [*Journal of Financial Markets*
2007](https://doi.org/10.1016/j.finmar.2006.09.001).

Why evaluate: turns exhaustion into measurable liquidity depletion followed by
refill probability and recovery half-life instead of a subjective chart label.

First gate: add causal depletion, refill-intensity, and estimated-half-life
features. Require at least 2% relative Brier gain for reversal/continuation and
consistent direction in four of five chronological folds.

Boundary: shock onset must be knowable at depletion time; later refill behavior
is a label. Venue, tick-size, and modern market differences require re-estimation.

### 8. Time-Uniform, Nonparametric, Nonasymptotic Confidence Sequences

Howard et al., [*Annals of Statistics*
2021](https://doi.org/10.1214/20-AOS1991).

Why evaluate: Frankie inspects every causal second, so pointwise confidence can
silently inflate error under optional stopping. Confidence sequences provide an
anytime-valid audit layer for repeated monitoring.

First gate: on planted-null simulations and chronological replay, require the
declared time-uniform error rate to hold across all inspected seconds while
producing narrower useful bounds than a Bonferroni pointwise baseline at matched
familywise error.

Boundary: this audits sequential evidence; it does not make the predictor
correct or select market features. Assumptions and the monitored statistic are
fixed before observing the path.

### 9. Adaptive Conformal Inference Under Distribution Shift

Gibbs and Candès, [NeurIPS
2021](https://proceedings.neurips.cc/paper/2021/hash/0d441de75945e5acbc865406fc9a2559-Abstract.html).

Why evaluate: an online recalibration layer can adapt sets or abstention only
after each target becomes causally known, without immediately retraining the
underlying model.

First gate: at a 90% target, require overall and regime coverage within two
percentage points, rolling-500 undercoverage no worse than five points, and
smaller mean set size than static conformal.

Boundary: update only after the label's reveal time. Long-run coverage can hide
local failures and is not an instance-conditional lock guarantee.

### 10. Model Assessment and Selection under Temporal Distribution Shift

Han, Huang, and Wang, [ICML
2024](https://proceedings.mlr.press/v235/han24b.html).

Why evaluate: provides an auditable adaptive-window alternative for comparing a
frozen pool of Frankie variants after labels causally mature.

First gate: in prequential replay, require no worse cumulative loss than the best
fixed candidate, at least 5% lower worst-regime log loss, and switching below a
predeclared operational limit.

Boundary: freeze candidates, losses, and switching before test. Only matured
labels update estimates; unresolved outcomes never participate.

## Shared Frankie boundary

All tests preserve the fixed 3,429 POX working population where applicable, the
raw/V3 richness available at each causal timestamp, prebirth-first timing, the
one immutable first lock, exclusion of PRIOR-resolved cases from H fallback,
and the protected detector/brain/Frankie surfaces. A paper supplies a testable
idea, never market validation.

Conformal Risk Control and SelectiveNet remain useful watchlist papers. They were
moved out of the top ten because their generic risk/reject mechanisms are less
direct than competing-event timing and anytime-valid monitoring for the current
Frankie contract.
