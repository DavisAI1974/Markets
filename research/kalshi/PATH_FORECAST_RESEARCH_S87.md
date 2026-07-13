# PATH-FORECAST RESEARCH — methods survey for the NYMEX hold-length signal (S87)

Cited literature survey (S87) for building an INTRADAY NYMEX-path forecast used as a STACKED hold-length /
continuation signal (NOT standalone alpha; NOT gospel). The forecast lives entirely on the NYMEX canary
(Databento CL/NG); Kalshi is only the execution/echo side. The analog library + microstructure features
both come off the one MBP-10 feed. All of this must still pass `odcore/leakage.py`, exclude the settle
window, be scored PER CELL as distributions (never a pooled mean), and be judged net-of-fee (maker AND
taker). Full agent transcript is not stored; this is the synthesis.

## The honest verdict (the framing that makes this worth building)
Intraday price LEVEL is near-unpredictable. But path SHAPE, continuation-vs-reversal, and
conditional-on-event structure carry small-but-repeatedly-measured skill. That is exactly the regime where
a STACKED signal is right: catalyst/flow triggers the trade (already built), the path read sizes the HOLD.
The forecast predicts CONTINUATION / HOLD-LENGTH, never price.

## Where the edge actually is (measured, replicated) — and it IS our setup
- **Around scheduled releases — the strongest, most-replicated result.** Natgas "announcement-day puzzle":
  >50% of annual NG-futures return is earned on EIA storage-announcement days, not explained by the
  surprise itself (Prokopczuk/Wese Simen/Wichmann, 10.5547/01956574.42.2.mpro). Crude: on EIA-inventory
  days the 3rd half-hour predicts the last half-hour (informed traders + a liquidity dip around the print;
  Indriawan/Lien/Wen/Xu, ssrn 3822093).
- **Intraday momentum, conditionally.** First half-hour predicts last half-hour, OOS R^2 ~1.6% (2.6% w/ the
  12th half-hour), and STRONGER on high-vol / high-volume / macro-news days (Gao/Han/Li/Zhou, ssrn 2552752)
  — the predictability concentrates in the exact cells we trade (release days, Hormuz-vol days).
- **First-seconds order flow.** OFI predicts returns over seconds-to-a-minute, decays fast — a TIMING /
  continuation feature, not a multi-minute forecaster, and much is contemporaneous not predictive (arXiv
  2507.22712). Consistent with our own DEPLOY_VALIDATED=False (imbalance = detector, not direction oracle).
- **Mostly NOISE:** multi-minute LEVEL forecasting on ordinary non-event periods; any single-window result;
  directional maps from signed flow.

## The methods (ranked implementability x honesty)

1. **Conditional-mean-by-analog-BUCKET continuation table (cheapest, hardest to fool).** Per cell (release x
   surprise-sign x pre-vol/coiled regime x imbalance-sign), tabulate the historical forward path +
   continuation rate from the MBP-10 windows; the "forecast" = the bucket's realized forward distribution.
   ~Zero new machinery, plugs into our per-cell discipline. THE honest baseline every fancier method must beat.
2. **Analog / kNN-DTW path matching.** Query = realized partial path + entry-state features; match (banded
   Sakoe-Chiba DTW) against the same-cell library; read forward continuation quantiles from neighbors
   (Ohnishi et al. 10.1007/978-3-319-93794-6_7; SPINEX arXiv 2408.02159). DTW classifies SHAPE well, level
   poorly; big overfitting surface (warping flexibility) -> constrain the band, condition the pool on regime.
3. **Functional PCA / curve-shape (the principled anchor).** Register release windows to event-time (t=0 at
   the print), functional-PCA the day-curves; **rolling FPCA handles the partial/mid-session curve**
   (Jasiak, arXiv 2505.20508 / Journal of Forecasting 10.1002/for.70127). Reported to beat ARMA/ML on the
   SIGN at fixed points; functional-GARCH gives the interval band (arXiv 2311.18477). **FPC1/FPC2 ~= "how big
   the move" + "front-loaded vs slow-bleed" = literally our S85 hold-time map (NG front-loads 66% in 60s, CL
   slow-bleeds).** Adopt only if it beats the bucket baseline OOS.
4. **Gradient-boosted CONTINUATION classifier.** Target = P(move continues >= X for >= T s); features = our
   tick/book (OFI, depth run-length, exhaustion, pre-release volume) + exogenous (surprise, degree-days,
   regime). Cheap, nonlinear, gives feature importances for falsification. Predict continuation/hold-length,
   NEVER price. Walk-forward, per cell, net-of-fee.
5. **Intraday seasonal PROFILE (the anchor generator / band).** The U-shape vol/volume profile is highly
   predictable (calendar effect); the DYNAMIC deviation is the uncertainty. De-seasonalize BEFORE any
   z-score (failing to biases spot-vol). Our pre-release-volume "coiled" detector is already a
   deviation-from-seasonal read. Scales the residual-z band (arXiv 2505.08180, 1904.01412).
6. **HMM trend-vs-chop GATE (gate only).** 2-3 state HMM to suppress the continuation signal in chop states
   (credible: arXiv 2006.08307). Treat blog Sharpes (e.g. the "5.9 daily" claim) as RED FLAGS, unproven
   until they clear our own walk-forward. Validate as an EV gate, not standalone.
7. **Gaussian processes for path distributions** — elegant intervals but O(n^3) and documented to DEGRADE in
   volatile regimes (exactly when we'd need it). Downsampled event-windows only, if at all.

## Tracking-error as the hold-vs-exit rule (the application)
Given the anchor path (#1/#3/#5) and the live realized NYMEX path, quantify divergence each tick:
residual-z = (realized-expected)/sigma_expected; rolling shape-correlation of increments; or DTW distance
to the matched prototype. HOLD while residual is inside the band AND shape-corr positive (the move is
tracking = has legs -> ride the long leg / trail wide); EXIT on first band-breach or corr sign-flip
(diverging = the analog thesis is void). This is a FORECAST-CONDITIONED exit replacing/augmenting the fixed
dollar trailing stop. **Honesty: the ANCHOR carries the skill; tracking-error is a variance-reduction /
risk-control overlay — its benefit is fewer round-trips held into reversals = improved net-of-fee EV per
trade, measured as a DELTA vs a fixed-hold baseline, per cell, NOT new directional alpha.** (Priors, not
evidence: optimal trailing-stop control arXiv 1701.03960; ATR dynamic stops.)

## Traps to bake into the eval (all consistent with our standing rules)
- **Data-snooping / multiple testing:** we test many cells x features -> false positives guaranteed. Use
  PBO/CSCV + a DEFLATED Sharpe and REPORT the number of specifications tried (Bailey/Lopez de Prado; surmount).
- **Transaction costs erase thin edges:** a 1-2% R^2 path signal is often below the round-trip fee -> this
  MUST be a hold-length overlay on catalyst-justified trades, never a standalone entry (our S81/S82/S36b
  "edge is size-vs-fee" is the same result the literature keeps hitting).
- **Look-ahead in normalization/registration:** de-seasonalizing or z-scoring with full-day stats is the
  commonest silent leak; normalize on decision-time-available data only; run through `odcore/leakage.py`.
- **Regime shift:** analog pools / FPCA bases fit across regimes mix incompatible dynamics; condition on
  regime; the 2026 Hormuz-era CL window is its own cell.

## Prioritized build order (cheapest / most honest first)
1. **Bucket continuation table** (#1) — the honest baseline; extends our per-cell S85 hold-time map. Needs the
   full-year MBP-10 library (the analog database).
2. **Event-time registered expected-path anchor + residual-z / shape-corr tracking overlay** (#3+#5+tracking)
   — operationalizes the hold-time map as the hold-vs-exit rule; measured as a net-of-fee EV delta vs
   fixed-hold, per cell.
3. **GBT continuation classifier** (#4) — nonlinear stack of tick+book+exogenous; predict continuation, not price.
4. **Rolling FPCA** (#3, Jasiak) — principled probabilistic anchor; only if it beats the bucket baseline OOS.
5. **HMM chop gate** (#6) — suppress the signal in chop; EV gate only.

Cross-cutting: leakage-gated, settle-excluded, per-cell distributions, net-of-fee maker AND taker, and the
whole thing is a HOLD-LENGTH / CONTINUATION overlay on catalyst-justified trades — which is both what the
architecture calls for and what the honest skill evidence supports.
