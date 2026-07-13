# FORECAST-AGENT DIRECTIVE — the operational marching orders for the path-forecasting agent (S88)

STATUS: DIRECTIVE (Greg + Claude, S88). This is the OPERATIONAL brief for the agent/session that builds
the intraday NYMEX path forecaster. It OPERATIONALIZES `FORECAST_AGENT_DESIGN_S87.md` (Greg's spec) and
`PATH_FORECAST_RESEARCH_S87.md` (cited methods) into scoped, un-foolable marching orders. Where this doc
and the S87 design differ, the design is the intent and this is the how. Nothing here overrides the
`kalshi-backtest` discipline or CLAUDE.md rules — it inherits them.

---

## 1. The job (Greg's core loop — unchanged)

Turn our pieces into a forecast of the intraday NYMEX (canary) TRADE-CURVE shape, per commodity, and use
real-time-vs-forecast tracking as the HOLD-LENGTH signal (ride the long legs, cut the chop — fees force
selectivity, the forecast is the selector). The agent OWNS figuring out how the pieces combine; it is not
handed weights. The method:

1. Get a DIVERSE sample of past days (calm, trending, whipsaw, release, geopolitical, each season).
2. GRAPH it and LEARN from it — exploratory, per commodity, before modeling.
3. BUILD BLIND — for held-out days, take ALL our pieces (that day's decision-time state) and forecast,
   without looking at the outcome, what the trade curve SHOULD look like (shape, legs, hold-length).
4. COMPARE to the actual curve; score the blind forecast.
5. RESCORE and SHARPEN — update piece weights / correlations / conditioning from the errors; repeat.

Self-supervised forecast-skill learning. The blind step is the leakage guard (see 3-below for what "blind"
formally means).

---

## 2. Scope for v1 (hard-scoped — do NOT boil the ocean)

- **Commodities: CL crude + NG natgas only.** Scored and forecast SEPARATELY (same scaffold, different
  values — S86). Never pool across commodity.
- **Level only, one line per commodity: NYMEX WTI (CL) and Henry Hub front-month (NG).** PER-LOCATION /
  PER-HUB basis is DEFERRED to a later stack (Greg S88: "different hubs later"). We do not yet have hub
  tick data — the NGI/regional feeds are coarse daily and un-ingested. Do not stall trying to score
  locations we have no data for. The deferred design (level = common factor + basis = regional − Henry Hub
  on local drivers) stays as written in `FORECAST_AGENT_DESIGN_S87.md` sec 2.
- **Method #1 (bucket continuation table) FIRST.** It is the honest baseline. Everything fancier (analog
  kNN-DTW, FPCA, GBT continuation classifier, HMM chop gate) is a NAMED LATER STACK and is kept only if it
  beats the bucket table OUT-OF-SAMPLE, per cell. See sec 7.
- **Output = a HOLD-LENGTH overlay**, not standalone alpha. See sec 8.

---

## 3. The forecast TARGET, defined precisely (so "compare to actual" is scoreable)

The target is NOT price level (near-unpredictable — the honest verdict in the research). It is the
**event-time-registered CONTINUATION curve**, three components:

- **(a) Magnitude** — how far the move gets (in $/contract, never bps), per horizon.
- **(b) Shape** — front-loaded vs slow-bleed. This is literally the S85 hold-time map (NG front-loads ~66%
  of the move in 60s; CL slow-bleeds, 60s ~27%). FPC1/FPC2 in the FPCA stack == "how big" + "front-loaded
  vs slow-bleed".
- **(c) Continuation probability** — P(move continues >= X for >= T seconds) at horizons.

**Scoring** = shape-correlation of increments + residual-z calibration + continuation hit-rate, per cell,
as DISTRIBUTIONS not means. NEVER RMSE-on-level. Register every window to EVENT TIME (t=0 at the catalyst,
e.g. the storage print / the sustained-move trigger).

**"BLIND" is a chronological date-cut, not a mindset.** For forecasting day D: every analog pool, fitted
weight, correlation, and normalization uses ONLY days strictly BEFORE D. De-seasonalizing or z-scoring with
full-sample stats is the commonest silent leak (research doc) — normalize on decision-time-available data
only, and run the whole closure through `odcore/leakage.py`.

---

## 4. Conditioning cells — temperature/season constrained, NO cross-regime matching (Greg S88, load-bearing)

A 60F day cannot be the forecast for a 30F day. The analog/bucket pool is gated on regime, not just pooled.

### NG (natgas) cells
- **Demand-temp regime** — bucket on gas-weighted degree-days (HDD/CDD), the demand-relevant aggregate,
  NOT a single city (see sec 6 for the data). This is the PRIMARY constraint — temp is dominant for NG.
- **Calendar proximity: +/- 2 WEEKS** of the target day's calendar position (electricity-load / seasonal
  demand). Widen by a week or two ONLY if the agent DEMONSTRATES the wider pool improves out-of-sample
  skill; NEVER more than that (Greg: "he might prove me wrong and add a week or two but that's it").
- **Weekday-type** — `Mon | Tue-Thu (ex-storage) | Storage-day | Fri | Sat | Sun`:
  - **Storage-day** (normally Thu 10:30 ET EIA natgas storage) is its OWN cell — the announcement-day
    catalyst (>50% of annual NG return is earned on storage-announcement days; research doc).
  - **Tue-Thu grouped** EXCEPT the storage day (Greg S88).
  - **Mon, Fri, Sat, Sun each separate** — Sat and Sun may have distinct shapes (Greg S88). CAVEAT for the
    agent: NYMEX NG has little-to-no weekend trading (Sat closed; Sun electronic session opens ~18:00 ET),
    so Sat/Sun most likely function as demand/weather CONDITIONING into Monday's open rather than as their
    own intraday trade curves — the agent CONFIRMS this empirically, does not assume it.
- **Plus** the standing state axes: surprise-sign (beat/miss), pre-release/coiled volume regime,
  book-imbalance sign, geopolitical/vol regime.

### CL (crude) cells
- **Time-of-year / season** (Greg S88: "time of year definitely important in oil") — a LOOSER calendar
  window than NG; temperature is NOT a primary CL driver.
- Weekday-type: probably NOT a strong CL axis (no storage-degree-day load structure); the agent MAY test it
  but should not assume it. CL's own catalyst is the EIA crude-inventory day (normally Wed 10:30 ET) — its
  own cell, same logic as NG storage-day.
- **Plus** the standing state axes: geopolitical regime (the 2026 Hormuz-era window is ITS OWN cell —
  never pool it with calm regimes), surprise-sign, coiled volume, book-imbalance sign.

**Cell-thinning honesty:** many cells x tiny corpus = tiny-n. Enforce a minimum-n floor per cell; report n
on every cell; a signal surviving on a SUBSET of cells is KEPT for those cells (partial coverage is not
failure). Never widen a cell to grab n at the cost of mixing regimes.

---

## 5. The pieces and correlation discovery (the agent's real job)

Our pieces (event-state model + microstructure): news (3 tenses), storage level+surprise, forward-curve
shape/backwardation, weather (degree-days / adverse), geopolitical regime, season, weekday-type, book
imbalance, flow exhaustion, depth run-length, pre-release/coiled volume, herd breadth.

- **Score each piece against FOUR outcome types: {price-change, direction, momentum/continuation,
  exhaustion/reversal}.** A piece may hit MULTIPLE at once (Greg).
- **Pieces may correlate WITH EACH OTHER** — find and handle redundancy (don't double-count two pieces that
  are the same signal) and interaction (two pieces together say more than either alone).
- **Correlations DIFFER PER COMMODITY** — same piece strong on CL, weak/opposite on NG (S86: depth
  run-length NG -0.17 / CL +0.52; surprise/move opposite-signed). Discovery is per-commodity, never pooled.
- **A correlation is "found" ONLY if it survives OUT-OF-SAMPLE on held-out days.** Many pieces x cells x 4
  outcome-types => false positives guaranteed. Use PBO/CSCV + a DEFLATED Sharpe and REPORT the number of
  specifications tried (Bailey/Lopez de Prado). An in-sample correlation is a hypothesis, not a finding.

---

## 6. Temperature data — a v1 BUILD (Greg S88: "temp is extremely important in nat gas")

Build a gas-demand temperature feed as a piece AND the NG conditioning axis. Two data needs, both required:

- **(A) HISTORICAL hourly temps for EVERY corpus day (Greg S88, load-bearing) — the SCORING input.** To
  build and score the historical forecast curves, the agent needs the realized hourly temperature record
  for each past day in the corpus (the 24 weeks now, the year later). This is what characterizes each
  historical day's demand regime, assigns it to a temp cell, and populates the analog buckets the blind
  forecast scores against. Without it, NG analog matching cannot respect the temp regime (no 60F-forecasts-
  for-30F-days guard) and the curves cannot be scored.
- **(B) DECISION-TIME temp forecast — the conditioning input at forecast time.** When forecasting a
  held-out day, the temp feature must be what was knowable that morning.
- **Aggregate: population/gas-weighted HDD/CDD** across the key US consuming regions — the demand-relevant
  number, NOT a single city high. Build the weighting once (a fixed set of demand-region stations x gas-
  consumption weights); apply to both (A) and (B).
- **Source:** for (A) historical hourly, use a free HISTORICAL hourly source with full back-coverage —
  NOAA ISD / NCEI-LCD station observations, or Open-Meteo / ERA5 historical hourly reanalysis (free,
  hourly, arbitrary lat/lon, decades back) aggregated to the demand stations. For (B), NOAA/NWS forecast
  API (or archived forecast issuances where available).
- **Leakage rule (the (A)/(B) split IS the leakage boundary):**
  - **Labeling / bucketing a past day (A)** => realized historical hourly temp is fine and correct — it
    characterizes history.
  - **Conditioning a forecast at decision time (B)** => use the FORECAST available that morning (the
    expected degree-days the market is pricing — also what the Kalshi `KXHIGH*` markets price). Realized
    same-day temp as a decision-time feature is LOOK-AHEAD; forbidden. Where archived hourly forecasts are
    unavailable, the broad HDD regime is highly forecastable a day ahead — a realized-as-proxy-for-forecast
    is permissible ONLY if the small leak is flagged and the feature is coarsened to the forecastable
    regime bucket (not the exact realized value); run it through `odcore/leakage.py`.
- Build it NOW so it is ready the moment winter days enter the corpus (see sec 9 — the 24-week corpus is
  warm-season, so temp differentiation bites hardest once the year lands).

---

## 7. Method / build order (cheapest + most honest first)

1. **Bucket continuation table (#1)** — per cell (sec 4), tabulate the historical forward path + magnitude
   + shape + continuation rate; the "forecast" = the cell's realized forward distribution. THE baseline.
2. **Event-time anchor + residual-z / shape-corr tracking overlay (#3+#5+tracking)** — operationalize the
   hold-time map as the hold-vs-exit rule (HOLD while residual inside band AND shape-corr positive; EXIT on
   first band-breach or corr sign-flip). Measured as a net-of-fee EV DELTA vs fixed-hold, per cell.
3. **GBT continuation classifier (#4)** — nonlinear stack of tick+book+exogenous; target = P(continuation),
   NEVER price. Feature importances for falsification.
4. **Rolling FPCA (#3, Jasiak)** — principled probabilistic anchor; adopt ONLY if it beats the bucket
   baseline OOS.
5. **HMM trend-vs-chop gate (#6)** — suppress the continuation signal in chop; EV gate only, not standalone.

Each fancier method must beat the bucket table OOS per cell or it is not kept.

---

## 8. Output / where it plugs in

- The RT-vs-forecast tracking error becomes the HOLD-LENGTH modulator in `research/kalshi/lag_join.py`
  (the S87 trade engine). It replaces/augments the fixed dollar trailing stop.
- **Payoff is measured as a net-of-fee EV DELTA vs the fixed-hold baseline, per cell — at MAKER AND TAKER.
  NOT claimed as standalone directional alpha.** The anchor carries the skill; tracking-error is
  variance-reduction / risk-control (fewer round-trips held into reversals).

---

## 9. Sequence (Greg S88: "the 24 weeks first, then the rest")

1. **The 24 weekly MBP-10 windows first (Apr-Jul, ~12 NG + 12 CL).** Build the machinery, wire the leakage
   gate, validate the discipline. HONESTY: this is ONE warm season — it contains ZERO cold-demand winter
   analogs, so within the +/-2wk NG temp constraint a NG day has only a handful of same-regime neighbors
   (very thin), and it CANNOT forecast a January cold-snap day (no cold days to match). The 24-week NG
   result is machinery-validation + a warm-season-only read, NOT tradeable and NOT a failure. This is
   precisely why the year library is load-bearing, not nice-to-have.
2. **The continuous YEAR MBP-10 library** (`data/nymex-ticks:nymex_cont/`, the pay-once pull) — the real
   diverse cross-season analog corpus. Real forecasting skill switches on here.
3. **2-year to S3 at go-live** (AWS live env).

---

## 10. Discipline (inherited, non-negotiable — from `kalshi-backtest` + CLAUDE.md)

- Leakage-gated (`odcore/leakage.py`) before anything runs; blind = chronological date-cut (sec 3).
- Exclude the settle window; forward outcomes bounded by the daily-settle exclusion.
- Per-cell distributions + per-trade fingerprints, NEVER a pooled mean. A pooled number is a footnote only.
- Net-of-fee at MAKER AND TAKER; a maker-only edge carries fill-risk and must say so.
- Zero synthetic data. Provisional-until-live.
- FILE DISCIPLINE — extend live files (e.g. `lag_join.py`, `event_move_baseline.py`) with a flag/mode; only
  new-file if none exists. Check `KALSHI_TRADING.md` before creating any file.
- Weather FORECASTER = Greg's spec, HANDS OFF; weather enters here only as a conditioning driver.

---

## 11. Agent shape + deliverables (recommended)

- **Build via direct edits in-session with Greg in the loop + a canary** (precision live-path work; the box
  has wedged multi-agent workflows before). Use a BOUNDED analysis subagent only for the exploratory
  "graph a diverse day-sample and report the structure" step (sec 1.2) — not one long autonomous agent
  owning the whole build.
- **Artifacts to produce:** (a) the per-cell bucket continuation table; (b) a blind-vs-actual SCORECARD
  with the number of specifications tried; (c) a per-commodity piece-correlation matrix (piece x 4
  outcome-types); (d) a `FORECAST_V1_FINDINGS_S88.md` write-up; (e) the tracking overlay wired into
  `lag_join.py`; (f) `KALSHI_TRADING.md` index updated.

---

## 12. Deferred later stacks (named, so the agent doesn't stall on them)

- Per-location / per-hub BASIS (level common-factor + basis on local drivers) — needs hub data (NGI /
  regional feeds; crude grade spreads). Greg S88: "different hubs later".
- FPCA / GBT / HMM (sec 7) — only after the bucket baseline exists and only if they beat it OOS.
- The daily FORECAST WORKFLOW (5PM load / morning recalc / mid-session re-match) — noted top of
  `KALSHI_TRADING.md`.
