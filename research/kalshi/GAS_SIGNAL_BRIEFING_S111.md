# GAS SIGNAL BRIEFING - S111 (2026-08-05)

Source: a six-lens parallel research sweep (`gas-forecast-signal-research`, run wf_10f725ef-68a),
commissioned by Greg: "do some research on what the best quants and mid term forecasters use to
build gas forecasts." Seven agents, 1.18M subagent tokens, 395 tool calls.

THIS IS RESEARCH, NOT ADJUDICATED DOCTRINE. Nothing here is merged, nothing is a decision. Claims
carry their sources; where a lens is uncorroborated the synthesis says so. Treat every number as a
lead to verify, per the program's own falsification-first rule.

The six domain lenses (full structured findings appended below the synthesis): weather at 6-15 and
15-30 days; supply-demand balance and storage analytics; power burn and the generation stack;
positioning, flow and market structure; analog and quantitative forecasting METHOD; volatility and
options.

---

# NATURAL GAS SIGNAL BRIEFING — SYNTHESIS OF SIX DOMAIN SWEEPS
Prepared for the desk owner. Ranked, not surveyed. All numbers carry their source lens.

---

## 1. THE HORIZON ANSWER

**Short version: forecasting past one day is viable, but not the thing you are currently forecasting. The LEVEL dies at 5-7 days. The DISTRIBUTION and the CALENDAR survive to 14 days and beyond. The product does not shrink to next-day; it changes shape.**

### 1.1 The four measured numbers, from four independent directions

| What is being measured | Where skill ends | Source |
|---|---|---|
| Gas-weighted HDD anomaly to Henry Hub spot, **measured on price** | significant at **2-4 days**, "progressively weaker beyond roughly five to seven days," consistent across GFS, GEFS and ECMWF | World Climate Service, Henry Hub verification |
| Raw meteorological skill, midlatitude 2m temperature | forecast skill **equals climatology at ~day 12**; coupled GEFS ensemble mean useful to "**nearly 10 days**" at the 60% ACC threshold; Zhang et al. 2019 puts the skilful lead at **~10 days**, theoretical ceiling ~2 weeks | WCS; NOAA coupled-GEFS study; J. Atmos. Sci. 76:1077 |
| Positioning (COT change, Q = delta-net / OI) | days 1-4 t=3.04, days 5-10 t=3.62, **days 11-20 t=1.23 INSIGNIFICANT** | Kang, Rouwenhorst & Tang, J. Finance 75(1) 2020 |
| Fundamental price predictability at sub-monthly horizon | **no published evidence exists at all.** The entire NG price literature is monthly. At h=1 month the last daily close beats every fundamentals model (33% MSPE reduction); the BVAR beats the random walk at every horizon EXCEPT h=1 | Baumeister & Kilian, NBER w33156 / JAE 2026 |

**The most important line in this whole briefing is row 1 versus row 2.** Meteorological skill runs to day 10-12. The *price relationship* to weather dies at day 5-7. The gap is not a contradiction — it is the market having already priced the forecastable part. Any horizon claim built on the day-10 number is wrong by a factor of two for trading purposes. Use 5-7 days as the directional boundary; better supported because it is measured on Henry Hub itself, not on 500hPa fields.

### 1.2 What degrades first, in strict order

1. **Forecast wind (day 3-5).** ERCOT day-ahead wind is ~11.5% MAPE and is effectively climatology by day 5. This is the fastest-dying input **and it is the one that flips the SIGN, not the magnitude.** Your own 0629 instance is the canonical case: gw_cdd rose exactly as forecast, gas burn FELL 4.2 Bcf/d because wind rose 62%. Independent out-of-sample confirmation exists (Texas June heat waves, gas generation -6% y/y while wind rose 90 GWh/d).
2. **The price-relevant part of the degree-day signal (day 5-7).**
3. **Daily temperature skill (day 10-12).**
4. **Positioning drift (day 10-11).**
5. Everything level-related. Beyond ~15 days only weather-REGIME probabilities survive, and only outside winter (persistence stays competitive through week 2 in DJF; models beat persistence at weeks 3-8 in spring/summer/fall).

### 1.3 What survives past day 7, and why the product does not shrink

**(a) DISPERSION, out to 14 days and further.** This is the finding that answers your binding question in the affirmative. Most of the gas volatility curve is *deterministic, not forecast*: the Samuelson decay (mechanical in time-to-expiry), the calendar-month seasonal, and the scheduled-event calendar. Variance is additive, volatility is not — so a 14-day fan can be built by summing per-day variance contributions (ambient x n_days + event variance on EIA Thursdays + weekend day-weighting) **even where the 14-day centre is unforecastable.** You can put a defensible number on the width of a session two-to-four weeks out with no weather opinion whatsoever. And Kalshi daily contracts are dispersion instruments more than level instruments — they pay on where a settle lands in a band.

**(b) CALENDAR / STRUCTURAL, weeks to months.** Pipeline maintenance notices, planned service outages, LNG train commissioning, futures/option expiry, the UNG roll, index reweights. These are dated FORWARD by construction. They are not forecasts and they have no horizon limit. This is the class of information you have the least of, and it is the class that answers "how far out" with "as far as the posting says."

**(c) REGIME PROBABILITIES, weeks 3-8** (outside winter), and **conditional windows** in winter: an already-occurred SSW opens a 30-60 day higher-skill window with measurably reduced ensemble spread; an active MJO with RMM amplitude > 1 in phases 4/5/6 or 8/1/2 (phases 3 and 7 carry no US temperature signal).

**(d) The one measured skill-extension rule.** Confidence-gated subseasonal: forecasts issued at tercile probability >50% verified correct **51-69%** at lead week 3 AND at lead week 6, versus 33.3% base rate. Forecasts at merely >33.3% verified **39-49%** — near noise. Skill at long lead lives almost entirely in the confident sub-sample, and the ranges are the same at week 3 and week 6, which means **the confidence gate matters more than the lead.**

### 1.4 The consequence you will not like

Three lenses converge independently: **your edge cannot be level drift from fundamentals.** There is no published evidence base for it at your horizon, and at one month the last close wins. What IS measured inside your window:

- COT *change* drift, days 1-10 (real, small, cross-sectional).
- The **EIA announcement-day premium**: more than 50% of the annual NG futures return is earned on storage announcement days, and it is **NOT explained by the surprise** (Prokopczuk, Wese Simen & Wichmann, Energy Journal 42(2) 2021). Naive position-before-print-close-30-min-after returned ~12%/yr, Sharpe 1.76 net of costs.
- The forecast *revision* process, which is what actually moves price at day 6-15.

So: forecast the **revision**, not the level. Price the **width**, not just the centre. Trade the **calendar**, which is not a forecast at all.

### 1.5 One scoreboard warning

Your scoreboard is forward-curve error. At h=1 month nothing beats the last price, so a forward-curve-error metric is dominated by the random-walk component and will flatter or punish you for reasons unrelated to skill. The Benyo et al. (Economic Inquiry 2026) reappraisal is the proof: re-score Baumeister-Kilian against END-OF-MONTH rather than monthly-AVERAGE no-change and none of the improvements survive as both significant and consistent. **Name the benchmark before the result.** Add end-of-session no-change and a seasonal-naive, and test with Diebold-Mariano.

---

## 2. TOP SIGNALS WE DO NOT HAVE — RANKED BY EXPECTED VALUE

### TIER 1 — build these next

**1. ISO day-ahead and 7-day WIND, SOLAR and LOAD forecasts, combined into NET LOAD**
- Source (all free): ERCOT Public API NP4-742-CD (wind actual+forecast by region), NP4-745-CD (solar), NP3-561/565-CD (7-day load by weather zone); SPP marketplace.spp.org Mid-Term Resource Forecast +7d and MTLF +7d; CAISO OASIS `SLD_REN_FCST`; PJM Data Miner 2 `load_frcstd_7_day` + wind/solar feeds (solar includes behind-the-meter); MISO 168-hour; ISO-NE seven-day wind and solar. Python: `gridstatus`.
- Horizon: 0-7d, strong 0-3d, wind degrades to climatology by ~day 5.
- **What it lets you see that you cannot now:** the sign of the burn response. You currently hold *realized* wind from EIA-930 — which cannot fix a forward call, because on a forecast day the realized value does not exist. Net load (load minus forecast wind minus forecast solar) is the actual causal driver of thermal dispatch. Named as the top gap by two independent lenses and it is the exact shape of your worst documented miss.

**2. Raw ECMWF ENS + GEFS ensemble MEMBERS, pushed through your own gas-weighted degree-day weighting to produce a DENSITY**
- Source: ECMWF open data (data.ecmwf.int) — **the full real-time catalogue went open under CC-BY-4.0 with data charges removed on 1 Oct 2025**, 0.25 deg, ENS to day 15; mirrored on AWS Open Data. NOAA GEFS 31 members via NOMADS / `noaa-gefs-pds` on AWS, plus the +35 day extended leg. Free.
- Horizon: 0-15d; usable 0-10d, degraded 11-15d.
- **What it lets you see:** a degree-day *distribution* instead of a point. You have MOS deterministic station guidance, which structurally cannot produce a spread. This single feed fills the ensemble gap, the spread gap, the probabilistic-path gap and the option-dispersion gap simultaneously, at zero cost. It is also the prerequisite for the confidence gate and therefore for a defensible NO CALL.

**3. Forecast PROGRESSION deltas on gas-weighted degree days, by block (1-5, 6-10, 11-15)**
- Source: free, derived from an archive of (2). Sold as a view by WCS, GasAlpha (4-model GFS/IFS/GEFS/AIFS consensus, 4x daily at 05z/09z/13z/21z, with published inter-model spread), NatGasWeather.
- Horizon: the delta on days 6-10 and 11-15 moves the front of the curve; days 1-5 moves cash and prompt.
- **What it lets you see:** the quantity that actually trades. The level is priced; the revision is not. This is also the direct instrument for the Friday-to-Monday cascade you have documented — futures gap at the Monday open on weekend model shifts. Carry it as a NEWS process, not a forecast: it has no intrinsic skill and day 11-15 deltas frequently reverse on the next run. That is the point — you are modelling repricing, not weather.

**4. LNG feedgas nominations, daily by terminal**
- Source: free, targeted scrape of ~10 pipeline EBBs (FERC Order 587 / NAESB WGQ informational postings): Creole Trail / Transco 4A / NGPL (Sabine Pass), Corpus Christi Pipeline, Cameron Interstate, Gator Express (Plaquemines), TransCameron (Calcasieu Pass), Golden Pass, Dominion Cove Point, Elba Express. Paid packaged: Wood Mackenzie, S&P Global, Criterion, East Daley.
- Horizon: 0-2d hard, 1-4wk overlaid with the terminal maintenance/commissioning calendar.
- **What it lets you see:** the fastest-growing demand line, knowable BEFORE the gas day. Feedgas moved ~13 to ~15 Bcf/d on the Plaquemines ramp alone — a 14 Bcf/week storage swing sitting in a public posting. Your `lng_feedgas_bcfd` is null and 278 days stale while the vessel line runs live with zero consumers. Highest value per unit of build effort in the whole supply domain because it needs ~10 EBBs, not 150.

**5. Pipeline critical notices and the planned-maintenance calendar**
- Source: free at source on every interstate EBB (notices section; monthly "Planned Service Outage"). Paid aggregators: Enercast, PipeRiv (~200 operators, has an API), Criterion.
- Horizon: **1-6 weeks, dated forward by construction.**
- **What it lets you see:** almost the only supply-demand information that is genuinely KNOWN weeks ahead rather than nowcast or lagged. If the binding question is how far out a useful forecast is possible, this is the answer for the structural half of the balance. Known failure mode, flag it up front: unstructured prose, no severity field, no Bcf/d impact stated, pipelines post and cancel, and NAESB's own working group abandoned website scraping as unreliable. Most notices have zero price impact.

### TIER 2 — high value, second wave

**6. Degree-day-adjusted balance residual (weather-normalised tightness, Bcf/d).** Free; you already hold every input (EIA implied flow + your own gas-weighted HDD/CDD). Regress weekly implied flow on GWHDD and GWCDD, read the residual as Bcf/d of structural tightness. **This is the measure that carries information PAST the weather horizon**, because it describes the non-weather part of the balance. It is also the natural home for your rebuilt asymmetric-slope weather model — it is the residual after the slope, so it isolates the renewables/coal/nuclear stack.

**7. COT reconstructed as a CHANGE, not a level.** Free, data already in hand. Q = (net_long_t - net_long_t-1) / OI_t-1, computed separately for Managed Money and Producer/Merchant, applied as **three distinct windows** (days 1-4, days 5-10, days 11-20-and-dead). The level construction is the one three independent studies reject; the change is the one with a Journal of Finance horizon-resolved result landing inside your window. Caveat to carry honestly: the published 67bp/20d result is **cross-sectional across 26 commodities**, not single-commodity timing — forward-test it, do not inherit it.

**8. Rebuild the degree-day weights, seasonally switched.** Free — same thermometers, different weights. Winter: the published DTN/Frontier construction, state weight = (households x fraction heating primarily with NG) / total US NG-heating households, ~230 stations, counties assigned to stations. Summer: power-weighted CDD from the EIA-930 BA-level gas generation you already ingest (South Atlantic 24.0%, West South Central 17.7%; East North Central falls from ~20% under GWDD to ~11%). Evidence this is worth real money: in a published futures event study the near-month temperature coefficient nearly **doubled** (0.062 to 0.1038) purely from single-station to multi-station weighting. Your own note that **Ohio has no station at all** — 6th largest state at 0.0525 national NG-heating weight, inside the largest gas-burning BA — is the same defect from the other end.

**9. NG WEEKLY options settle IVs, plus EIA-print event variance extraction.** Free from CME daily settlements. CME lists Monday through Friday weekly expiries on Henry Hub. **This is the listed price of a one-to-five-day Henry Hub distribution — the direct comparable to your Kalshi daily book.** Extract event variance by additivity: `IV_span^2 * DTE_total = IV_noevent^2 * DTE_ambient + IV_event^2 * 1`. **Critical rule (Zhong 2026):** fit the no-event surface ONLY on non-spanning expiries, or the surface silently absorbs the event premium and the jump becomes unidentified while still looking like a good fit. Independently corroborated by the documented NGVX Wed-to-Thu decline. Your EIA Thursdays are your worst day-class (G20: two EIA Thursdays were 3,530 of 7,880 total error). *Unverified: the sweep could not load CME's weekly-options FAQ — confirm Globex product codes before wiring.*

**10. EIA implied flow vs net change, the reclassification flag, and the published sampling standard error.** Free, one field each, and together they prevent an entire class of false lesson. Consensus forecasts the FLOW; the tape prints the NET CHANGE; on reclassification weeks (4 Bcf or more) they diverge by more than the whole survey range and the "surprise" is pure accounting. And EIA publishes its own noise floor weekly in the "Estimated measures of sampling variability" table: worked example SE 2.2 Bcf on L48 net change, ~4 Bcf 90% margin of error. **A print that beats consensus by 3-4 Bcf is inside the measurement error of the print itself.** For a system whose structural finding this session was that a forced number is indistinguishable from a confident one, this is a published, numeric, auditable basis for NO CALL.

**11. The coal limb of the stack.** You have nuclear and wind; you have no coal, which is the third absorber in your own stated model. Free: EIA Coal Markets weekly basin spot prices (Central App / Northern App / Illinois Basin / PRB) plus EIA-923 heat rates and coal stocks / days-of-burn. Published bands: gas competitive with PRB below ~$3.00/MMBtu, PRB parity floor ~$2.42, Illinois Basin ~$2.40, gas-to-coal not expected until above ~$3. **Urgency flag: EIA states the historical coal price series is vendor-proprietary and cannot be released — accrual must START NOW and cannot be backfilled.**

**12. Wellhead freeze-off risk index.** Free, built on infrastructure you already have, but keyed to basin-level forecast MINIMUM temperature (Permian, Haynesville, Appalachia, Anadarko, Bakken, Rockies) — not any weighted average. January 2026: ~2 Bcf/d initial loss, then an abrupt ~12 Bcf/d, total 16-17 Bcf/d. Appalachia is comparatively resilient (~600 MMcf/d off a 32.8 Bcf/d base in one episode). It is the largest single-day supply shock in the market and **the one case where cold is bullish on both sides of the balance at once** — a model that maps cold only to demand will structurally under-forecast extreme cold days. No published transfer function exists; the relationship drifts year over year with winterisation.

### TIER 3 — cheap to carry, lower priority

- **Forecasted thermal outages beyond nuclear**: ERCOT NP3-233-CD (168h hourly), PJM `frcstd_gen_outages` (90 days) and `gen_outages_by_type`. Free, forward-looking, ~10x the nuclear capacity you already track.
- **Leveraged ETF close rebalance (BOIL/KOLD)**: free, same-direction, forced, lands at the close where Kalshi settles. **No NG-specific published measurement exists** — genuinely unexplored ground, testable entirely on tape you already own.
- **UNG four-day roll**: pre-announced 75/25 to 50/50 to 25/75 to 100/0 ramp beginning exactly two weeks before front expiry — inside your window. Per Bessembinder et al., expect a DEEPER, more mean-reverting tape, not a trending one. That is a magnitude-damping condition, and magnitude is your stated dominant residual.
- **Mexico exports and Canadian net imports, daily**: ~13-15 Bcf/d invisible in every domestic series and decorrelated from your US degree-day view.
- **Weather regimes (4 North American), MJO RMM, stratospheric polar vortex, CPC 6-10/8-14/week3-4 + verification archive**: all free (ERA5/Copernicus, BoM, CPC, Simon Lee's operational regime charts). Carry as gates, not predictors.
- **GEFSv12 reforecast (2000-2019, free on AWS `noaa-gefs-retrospective`)**: frozen-model, daily 5-member to +16d, weekly 11-member to +35d. Required if you build analog ensembles properly (see section 4).
- **EIA-930 day-ahead demand forecast field for the non-ISO Southeast** (SOCO, TVA, DUK, FPL, SCEG) — the only free forward load number in the largest summer-burn region. Requires a per-BA coverage assertion: the field is not universally reported.
- **Days of cover; storage vs demonstrated peak capacity; EIA-860M additions/retirements; Cboe VXUNG; CME CVOL NGVL.** All free or near-free, all slow.

---

## 3. WHAT YOU ALREADY HAVE AND ARE UNDER-USING

**Ranked by wasted value.**

1. **The full NYMEX tick/MBO tape.** Four separate uses you almost certainly are not extracting: (a) **separate TAS (NGT) instruments out of the pool** — a parsing change, zero data cost, and it isolates benchmark/index flow from opinionated flow, which is precisely the distinction the positioning result turns on; (b) **jump-robust realized variance** — you are probably computing close-to-close, which throws away most of what you paid for, and the literature is explicit that the jump component is not optional at daily/weekly tenor; (c) the **Baltussen et al. rest-of-day to last-30-minute momentum** measure, which needs no options data and speaks directly to close-settled contracts (scope it strictly intraday — the paper says it REVERTS over subsequent days); (d) the BOIL/KOLD close-imbalance test.

2. **The options settle-IV surface and OI strike ladder.** You hold it as a level. It becomes a signal only after you **de-Samuelsonize and de-seasonalize** — fit sigma(t,T) = theta(t) * exp(-beta*(T-t)) with **beta estimated separately for winter and injection season** (Gregoire & Boucher: the gas maturity effect is present ONLY in winter; a year-round decay will over-forecast injection-season front-month vol). The residual is the view. Also compute VRP with the **correct denominator** — implied for calendar period X against realized for the SAME calendar period historically, never against trailing realized.

3. **EIA-930.** Three under-uses: it is your free source of PWCDD weights (BA-level summer gas generation); it now breaks out **battery storage** as its own category (Q1 2025 onward), which is the reason a hot evening no longer produces the peaker burn the temperature implies; and it needs a declared basis field because of documented, invisible defects — anomalous values replaced by **IMPUTED** values, energy sources not summing to net generation, subregion demand not summing to total, UTC-only timestamps with DST gaps, and **behind-the-meter solar excluded entirely** (a one-directional and growing bias in exactly the daylight hours that matter for cooling).

4. **The weekly supply-demand balance — CHECK THIS FIRST, IT IS A LIVE RISK.** If it is sourced from the EIA Natural Gas Weekly Update, that publication's **final edition was the week ending 21 January 2026**; it was replaced on 29 January 2026 by the Weekly Natural Gas Storage Report Supplement. A pipeline pointed at the old vehicle goes stale silently — present, numeric, in range, right owner. That is your documented hole signature, eleven times over. Cheapest possible check on this entire list.

5. **COT.** Level to change (item 7 above). Plus two free splits you are not making: **futures-only vs combined (delta-adjusted) divergence** — tells you whether a positioning move was expressed in options (structured, hedged, slow to unwind) or outrights (fast, squeezable); and **52-week smoothed HP vs the raw residual** — the smoothed component is a quarters-to-a-year premium, the residual is last week's liquidity demand, and conflating them means reading a one-week absorption as a change in producer hedging intent.

6. **Storage consensus.** Check whether you carry the **RANGE**, not just the median. Magnitude of the print reaction scales with how genuinely unresolved the number was. But carry the contamination with it: Ederington/Linn/Zhang find analysts anti-herd, accuracy decreases with anti-herding intensity and with earlier release, and those two variables alone explain over 50% of cross-firm accuracy variation. **The median of a survey is not an equal-quality aggregate — later forecasts are systematically better.** And crowd-sourced forecasts are measurably less accurate than professional ones and add nothing beyond them.

7. **Term structure / calendar spreads.** Use as a **regime label**, not a level: spot and futures are MORE correlated in contango than in backwardation, and Samuelson strength itself varies with the degree of backwardation. Also, the **carryout projection** (level + cumulative forward balance) is the natural target variable for a curve-error-scored desk — and its error compounds at roughly (balance error Bcf/d) x days, so 0.5 Bcf/d over 90 days is 45 Bcf of carryout error, wider than the range analysts argue about.

8. **Your model-disagreement measure vs ensemble spread.** These are **two different variables** and you have one. Between-model disagreement (GFS vs ECMWF) is not within-ensemble spread. Carry both.

9. **Nuclear outages.** Extend to the whole thermal fleet — the fossil fleet is roughly ten times the capacity.

10. **The tropical feed.** Its sign has **inverted post-shale.** Offshore Gulf production is now a small share of supply while LNG export capacity is concentrated on the Gulf Coast; a single landfall at Sabine Pass could affect roughly half of US LNG capacity, about 12% of total US consumption. A storm now more often destroys DEMAND than supply, and trade press documents gas WEAKENING on tropical risk. Direction depends on track relative to export terminals versus production and cannot be assumed.

11. **GSCI/BCOM roll calendars.** Keep them, but demote from alpha to liquidity-regime flag — see folklore below.

12. **STEO vintages.** Correctly a slow structural prior. Explicitly NOT a short-horizon input: EIA experts win at h=9-12 months, lose badly to no-change at h=1 and h=3.

13. **Realized-vol regime.** The gas-specific literature favours the discrete Markov-switching version. One leak vector to check: the published/smoothed state probability is computed with hindsight; the real-time **filtered** state is materially noisier and is what a live system would have had.

---

## 4. METHOD GUIDANCE — ANALOG RETRIEVAL

This section is the most directly load-bearing on your stated method, and it contains the single hardest constraint in the entire sweep.

### 4.1 The dimension budget — this is the finding

Two literatures that never cite each other produce the identical exponent. Dynamical-systems analog theory: `<r_k> ~ (k/L)^(1/d)` (Platzer/Yiou 2021). Machine-learning nearest-neighbour theory: `l ~ (k/n)^(1/d)` (Bellman/standard). Inverted: **`L = k / r^d`.**

For a decent normalized analog distance (r ~ 0.1) with a single match:
- d = 3 needs L ~ 1,000 sessions (about 4 years)
- d = 4 needs ~10,000 (40 years)
- d = 10 needs 10^10 sessions

**Your library is a few hundred to a couple thousand sessions. Therefore the matching dimension must be about 3, at most 4.** Any retrieval conditioning on ten or more simultaneous conditions returns a day provably no closer than a random day — **and it will still return one, confidently, with a magnitude attached.** With 82 plays, 24 of which carried absolute bars, this is the most likely single explanation for blind-versus-refine gaps that no amount of play refinement will close.

Two corollaries: (a) more analogs COSTS dimension — `d_max,K = d_max,1 * (1 - log K / log L)`, so at L=10^4 going K=1 to K=25 forces d from 10 down to 6; (b) **depth does not rescue you** — quality improves only as L^(-1/d), and operational AnEn accuracy SATURATES near four years of archive and then DEGRADES because the underlying model changes underneath the library.

**Action: compute the effective d of your current match, publish it beside every retrieval, and hard-fail above budget.**

### 4.2 The distance metric you do not have

Adopt the Delle Monache form (Mon. Wea. Rev. 141:3498; free reference implementation PAnEn/RAnEn). Three load-bearing pieces you lack: **(a)** each predictor divided by its OWN historical standard deviation, so units cancel and no high-variance field silently dominates; **(b)** an explicit per-predictor weight w_i; **(c)** the match computed over a **TIME WINDOW around the lead time, not at a single instant** — trajectory shape, not a point. Without an explicit d(target, candidate), "find a past day whose shape matches" is unauditable and the scaling law cannot even be applied to it.

Set the weights by CRPS minimisation (Junk et al. 2015, measured ~20% gain). This makes "which conditions matter" a fitted, falsifiable object — and it enforces the predictor budget honestly, since a predictor that does not pay for itself in CRPS is diluting the match. That is the quantitative form of your own finding that a condition which cannot change state carries no information.

### 4.3 Retrieve an ENSEMBLE, not one day

Every operational analog system retrieves **K ~ 20 (about 3-4% of the archive)** and reports the DISTRIBUTION; the spread is the uncertainty estimate and CRPS is what gets verified. You retrieve one day and re-anchor its level. Moving to K analogs gives you a magnitude distribution, a native confidence measure, and would have made several of your large single-day errors visibly wide-band *before* the fact.

### 4.4 Use a regime label as the key

Four North American winter regimes (Pacific Trough, Pacific Ridge, Alaskan Ridge, Greenland High, plus a "No Regime" class) from k-means on detrended standardized 500hPa PCs. Free from ERA5 via Copernicus; free operational monitoring from Simon Lee's ECMWF and GEFS regime charts. **This collapses the match to d ~ 1-2 — the only dimension your library size permits.** Skill horizon 7-46 days, which brackets your entire window.

### 4.5 Consider Constructed Analog instead of single-day re-anchoring

Solve for a weighted linear combination of past states that reproduces the current state, then carry the same weights forward (Van den Dool, operational at NOAA CPC). It sidesteps the catalog-size problem entirely — you never need one day that matches, you need a basis that spans the state — produces a magnitude natively without a re-anchor step, and the weights are auditable. Honest caveat: its measured advantage over natural analogs is largest in specification/nowcast mode, not pure forecast.

### 4.6 Build a computable NO CALL

Two free, independent routes: **matrix-profile DISCORD** (the subsequence whose nearest neighbour anywhere in the corpus is farthest — i.e. today has no analog) and **time-lagged recurrence / local dimension** as a per-day predictability estimate. Both produce a numeric, auditable score. This bears directly on your recorded structural finding that C-0715 wrote correct handling was NO CALL and could not emit it because the coordinator hard-fails on non-numeric output. **A discord score is a number.** It does not require changing the contract to accept prose. Pair it with the EIA sampling-SE noise floor and the ensemble confidence gate and you have three independent, numeric NO CALL triggers.

### 4.7 Failure modes to design against

- **Detrend, and use a full-period climatology.** Documented consequence of getting this wrong: comparing older analog years against a recent 20-year climatology in a warming trend produced anomaly errors of several degrees and **REVERSED THE SIGN** of the El Nino signal in a worked example. Same signature as your wrong-encoding and off-instrument holes — every individual anomaly still reads numerically reasonable.
- **Purged and embargoed cross-validation (CPCV).** Any retrieval whose matched window overlaps the evaluated outcome leaks by construction. You have caught several leak classes by hand; this is the structural remedy rather than a per-incident patch. Note the split: CPCV measures overfit better, walk-forward measures tradeability better — you need both.
- **Multiple-testing correction on the play library.** 82 plays selected and merged on the same walk that measures them IS a trial count. Deflated Sharpe / Probability of Backtest Overfitting / Minimum Backtest Length. The clustering step matters (count effective independent trials, since your plays are correlated by construction). This will not tell you which play is wrong; it will tell you how much of the aggregate improvement is selection.
- **Point-in-time forecast history, never revised.** Backtesting on revised forecasts produces look-ahead bias and false confidence. Same mechanism as your hole #11 and your partial-fetch tail. Free partial substitutes: GEFSv12 reforecast, IEM MOS archive.
- **If timing alignment ever enters** (re-anchor level becomes re-align timing): DTW accuracy PEAKS at very small warping windows and degrades toward full DTW; unconstrained DTW is typically worse than plain Euclidean. The window must be learned. Flagged pre-emptively.

---

## 5. FOLKLORE TO IGNORE

Ordered by how likely you are to be carrying it.

1. **COT position LEVELS predict returns.** Three independent rejections: raw hedging pressure Fama-MacBeth slope t = -0.43; Granger tests find very little evidence positions forecast returns; Gorton/Hayashi/Rouwenhorst explicitly REJECT the hedging-pressure hypothesis, finding positions correlate with prices — i.e. positions FOLLOW. The "managed money z-score above +2 is bearish" rule has **no published NG statistics at all** — only vendor charts and post-hoc commentary. Measure it yourself or drop it.
2. **The raw 5-year-average storage comparison.** Measurably biased bullish-complacent: storage capacity is up ~7% since 2012 while total demand including exports is up more than 50%, so a given Bcf surplus is materially less cushion than the same number a decade ago. EIA also changed the 5-year-average methodology in November 2018 and revised the 2018 statistics — the series has a definitional break in it.
3. **Storage surprise drives the announcement-day move.** Directly contradicted: the announcement-day premium is significant and **not explained by the surprise or by controls**, and the pre-announcement half appears only when storage exceeds expectations. Any play mapping surprise sign to direction is fitting the smaller and less reliable of two effects.
4. **Hot weather is bullish gas.** Not unconditionally, and the failure is systematic. The correct variable is residual load. A hot day with strong wind burns LESS gas than a mild day without.
5. **The Goldman roll trade.** Measured dead. Impact 30-40bp in 1991-2011 with full V-shaped reversal; **impacts DISAPPEAR 2012-2019**; aggregate order-flow cost fell from $2.9bn/yr to $474mm/yr, an >80% decline. Mou (2011)'s Sharpe-4.39 result is a pre-2011 artifact.
6. **Predatory front-running of ETF/index rolls.** Evidence runs the OTHER WAY: on roll dates, narrower spreads, greater book depth, more distinct liquidity providers, improved resiliency. Sunshine trading. Expect roll days to be MORE mean-reverting, not trendier.
7. **"Salt leads."** True in the weak form, folklore in the strong form. Salt is a Gulf Coast / LNG / power-burn signal, a small share of L48 working gas, and increasingly a merchant trading asset so moves reflect spread positions rather than physical scarcity. And since withdrawal rate varies DIRECTLY with fullness, a slowing salt draw may be a deliverability constraint — the same observation supports opposite readings.
8. **The Monday effect and the storage-day effect as calendar rules.** Mu (2007) finds both are DRIVEN BY WEATHER. They are weather-arrival effects that cluster on those days. A calendar dummy will fit in-sample and fail whenever weather arrival decouples from the calendar.
9. **Unconditional volatility percentiles and ranks.** Any percentile not conditioned on season is a calendar signal wearing a statistics costume — it will call every November high and every May low.
10. **The IV/RV ratio across a season boundary.** Comparing forward-looking implied to backward-looking trailing realized. Nobody expects last month's volatility to repeat across a season change. Compare implied for period X to realized for the SAME calendar period in prior years.
11. **Deferred-month IV is lower so far-dated gas vol is cheap.** Pure Samuelson artifact. The correct read inverts: if the 1-year trades at the SAME implied vol as the 1-month despite moving less, the market is implying MORE variance in the coming months.
12. **Gas call skew is bullish.** It is hedging FLOW — utilities and producers buy OTM winter calls because spike cost exceeds premium, and that standing bid keeps call IV above put IV. Only deviations from the seasonal norm are candidate information. (Aegis markets it as "bullish bias"; two of our lenses say flow. Flow is better supported.)
13. **Sell gas variance, the VRP is the biggest in commodities.** Both halves true, conclusion wrong. NG 60-day VRP -10.2% (t=-9.24), three times crude's — but std dev 15% (an order of magnitude above other commodities), skew -1.61, **minimum -166% of notional**, Sharpe 0.35 versus crude 0.59 and S&P 1.02. The variance-swap return profile "resembles that of a call option": you are structurally short a call.
14. **Coal-to-gas switching sets a floor.** Asymmetric now. Cheap gas can still take coal's share; expensive gas can no longer reliably hand it back. 2022 is the counterexample of record: Henry Hub hit $6.60 and gas burn still ROSE >7% y/y because coal stockpiles were ~65-76 days and rail could not replenish. Also: there is no single switching threshold — EIA disclaims its own $/MWh conversion as illustrative only.
15. **Rig count as a near-term production predictor.** Broken by associated gas, rising wells-per-rig, and a 3-7 month DUC backlog. At 0-14 days it carries nothing.
16. **Hurricane season is bullish.** Inverted post-shale — see section 3, item 10.
17. **Ensemble spread as a per-day error forecast.** Published spread-skill correlations "rarely exceed 0.5," explaining 25% or less of accuracy variation. **However** — this is a lens disagreement worth resolving: spread as a POINT-ERROR predictor is weak (weather lens correct); spread as a DISTRIBUTION for pricing dispersion is valid (vol lens correct). Different jobs. You are not predicting today's error, you are pricing the width.
18. **ENSO composites as a forecast.** NWS states explicitly they "are not intended to be a forecast." The strongest verified US El Nino signal is Gulf Coast PRECIPITATION (>80% of events over 100 years), not temperature — and temperature is what gas trades.
19. **An SSW means cold is coming.** January 2021 is a published counterexample with limited surface impact. It opens a higher-skill window; it does not deliver the outcome.
20. **Dealer gamma in natural gas.** There is no public dealer/customer classification in NYMEX options and no gas-specific published gamma work at all. The "dealers are short gamma" sign convention is imported from equities where customers buy calls — in gas, producers systematically SELL calls. Anyone quoting a gas dealer-gamma level is modelling and presenting it as observation. Separately, the best pre-registered GEX replication (SPY, 1,972 days) shows rho -0.36 raw collapsing to **-0.03 (p=0.18) after VIX + ATM IV controls** — it is largely a repackaging of implied vol.
21. **"The European model is always right."** ECMWF leads on headline scores, but the multi-model blend beats any single model. Single-model devotion is a measurable cost.
22. **More analogs is better; a larger DTW window is better; a deeper library keeps helping.** All three refuted — see section 4.
23. **Clustering price shapes finds profitable patterns.** J.P. Morgan's own study (50,000 chunks, ~30 years S&P 500, four clustering methods): no clusters emerged as profitable or unprofitable, and cluster centres were nearly identical between profitable and unprofitable sets despite large return differences.
24. **Announced data-centre load is load.** Interconnection queues are inflated by speculative requests; EIA cut its own 2026 generation forecast by more than a percentage point. Use realized BA-level demand level shifts.
25. **The day 11-15 forecast moves the market so it must have skill.** The price reaction is real; the skill is not. Two different quantities, do not model them with one coefficient.

---

## 6. THE CHEAPEST NEXT MOVES

Ordered by (cost to land) x (value), cheapest-and-highest first.

| # | Move | Effort | Why now |
|---|---|---|---|
| 1 | **Check whether the weekly supply-demand balance is reading a dead page.** EIA Natural Gas Weekly Update's final edition was week ending 21 Jan 2026; replaced 29 Jan 2026 by the WNGSR Supplement. | minutes | A live staleness risk with your exact hole signature. Highest embarrassment-if-skipped ratio on this list. |
| 2 | **Add EIA implied flow, the reclassification flag, and the published sampling SE** beside every print. | ~1 hour | Free noise floor (~4 Bcf 90% MoE). Immediately gives you a defensible numeric NO CALL trigger. |
| 3 | **Compute the effective matching dimension d of your current analog retrieval and publish it beside every call.** | ~half day | You may find the single explanation for the entire blind-refine gap. Nothing to build, only to measure. |
| 4 | **Recompute COT as Q = delta-net / OI, split MM vs Producer, in three decay windows.** | ~half day | Data already in hand. Converts your weakest positioning input into your only one with a published in-window result. |
| 5 | **Rebuild degree-day weights on the published heating-fuel method and add a seasonal switch to power-weighted CDD** (EIA-930 BA gas generation, already ingested). | ~1-2 days | Same thermometers. Published evidence of roughly a doubling of measured coefficient from better spatial weighting. Fixes Ohio. |
| 6 | **Wire ISO day-ahead / 7-day wind, solar and load, and derive NET LOAD.** Start with ERCOT + SPP + PJM (largest burn + largest wind). | ~2-4 days | The sign-flipper. Fixes 0629 directly. `gridstatus` wraps most of it. |
| 7 | **Pull ECMWF ENS + GEFS members and push them through your GWDD weighting to produce a density.** Start archiving the runs today — the archive is the asset. | ~3-5 days | Free since 1 Oct 2025. Fills the spread gap, the distribution gap and the option-dispersion gap in one feed. |
| 8 | **Derive the forecast-progression delta by block from that archive.** | trivial once (7) exists | This is the quantity that trades. Also the pre-open Friday-to-Monday instrument. |
| 9 | **Separate TAS (NGT) out of the existing tape, and add jump-robust realized variance.** | ~1-2 days | Parsing changes on data you already own. Every VRP and event-vol number depends on the RV denominator. |
| 10 | **Scrape the ~10 LNG feedgas EBBs.** | ~3-5 days | Smallest scrape with the largest demand-line payoff; kills the null `lng_feedgas_bcfd`. |
| 11 | **Compute the degree-day-adjusted balance residual** from EIA implied flow + your own GWHDD/GWCDD. | ~1 day | Every input already held. The only measure that carries past the weather horizon. |
| 12 | **Start accruing EIA weekly coal basin spot prices.** | ~1 hour | Zero value today, but the history is vendor-proprietary and **cannot be backfilled**. Every week you wait is permanently lost. |
| 13 | **Add the UNG roll calendar and the NG futures/options expiry calendar as day-class tags.** | ~1 day | Pure calendar, free, dated forward, lands inside your window. Note the clock trap: NYMEX settles on a 14:28-14:30 ET VWAP, Kalshi at 17:00 ET — a signal calibrated on one will mis-time the other. |
| 14 | **Pull NG weekly option settlements and extract EIA-print event variance** (non-spanning expiries only). | ~3-5 days | The listed comparable to your Kalshi daily book, and it attacks your worst day-class. |

**If you do only three things:** items 1, 3 and 6. Item 1 protects you from a live silent failure, item 3 may explain your largest standing error at zero build cost, and item 6 fixes the documented miss that no amount of weather refinement can reach.

---

## CLOSING NOTE ON THE BINDING QUESTION

You asked whether forecasting past one day is viable. The measured answer is that **directional level forecasting past 5-7 days is not, and never was** — the market has already priced the forecastable part of the weather, and no published work supports fundamentals-to-price predictability at your horizon in either direction.

But that is not what kills the product. Three things survive well past one day and all three are things you can build with free data: the **distribution width** (mechanically knowable to 14 days and beyond, because variance is additive and most of the vol curve is deterministic), the **forward calendar** (maintenance, LNG in-service, expiry, rolls — not forecasts at all, so no horizon limit), and the **revision process** (which is what actually moves price at day 6-15).

The change required is not more inputs. It is a change of output object: from a point path to a fan with day-class labels and an explicit, numerically-triggered NO CALL where the fan is too wide to trade. Your own machinery already found the missing piece — C-0715 wrote that the correct handling was NO CALL and could not emit it. The weather, storage and analog literatures independently say the 8-15 day window is precisely where that option is required. Build the NO CALL first; it is the cheapest item on the list and it is the prerequisite for honestly using anything past day 7.

---

# APPENDIX - THE SIX DOMAIN LENSES, VERBATIM STRUCTURED OUTPUT


## LENS: Weather at the 6-15 and 15-30 day range for mid-term natural gas forecasting: ensemble systems, degree-day weighting, ensemble spread, teleconnections, commercial weather vendors, and measured forecas

```json
{
 "domain": "Weather at the 6-15 and 15-30 day range for mid-term natural gas forecasting: ensemble systems, degree-day weighting, ensemble spread, teleconnections, commercial weather vendors, and measured forecast skill limits by lead time.",
 "signals": [
  {
   "name": "ECMWF ENS (IFS ensemble) raw gridded members - 50/51 members, 0.25 deg",
   "what_it_measures": "Full probabilistic 2m temperature field to day 15. Lets you build your own gas-weighted degree-day DISTRIBUTION (p10/p50/p90) rather than consuming a single vendor number. This is the primary instrument every gas desk actually watches.",
   "source": "ECMWF open data, data.ecmwf.int (GRIB2, 0.25 deg). Since 1 Oct 2025 the FULL real-time catalogue is open under CC-BY-4.0 with data charges removed. Mirrored on AWS Open Data (registry.opendata.aws) and dynamical.org Icechunk Zarr. Streams: oper (HRES) and enfo (ENS).",
   "cost": "free",
   "horizon": "ENS at 00/12z: 0-144h by 3h then 150-360h by 6h (day 15). At 06/18z: 0-144h only. Post-IFS-Cycle-50r1 the enfo stream carries 50 perturbed members (control moved to oper); pre-50r1 archives on AWS carry 51.",
   "skill_limit": "World Climate Service measures that at roughly day 12 forecast skill equals climatology skill - beyond that the raw forecast adds nothing over climatology. ECMWF headline score is the lead time where 12-month-mean 500hPa NH extratropical ACC falls below 80%; ACC above 0.6 is the conventional 'still skillful' floor. Cycle 49r1 (12 Nov 2024) cut day-5 northern-extratropics 2m temperature error ~10%, the largest single-upgrade ENS gain since 2011.",
   "why_practitioners_use_it": "It is the model the market prices off. Desks run the members through their own degree-day weighting so they see the distribution and the run-to-run delta before a vendor's summary number is published. Free access since Oct 2025 removed the historical cost moat.",
   "we_already_have_it": "no"
  },
  {
   "name": "GEFS (GEFSv12/v13) 31-member ensemble, incl. the +35 day extended leg",
   "what_it_measures": "US-run ensemble temperature; the second leg of the standard desk 'multi-model consensus' and the only free ensemble that reaches into the 15-30 day window.",
   "source": "NOAA NOMADS and AWS Open Data (noaa-gefs-pds, 2017-present; noaa-gefs-retrospective for the GEFSv12 reforecast; noaa-ufs-gefsv13replay-pds for v13). 0.25 deg.",
   "cost": "free",
   "horizon": "31 members; full-cadence output through ~day 16, extended leg to +35 days.",
   "skill_limit": "GEFS/GFS 500hPa ACC drops below the 0.6 skill floor sooner than ECMWF. Beyond ~2 weeks, forecast errors exceed climatology errors for daily grid-point fields; skill at weeks 3-4 survives only at coarser space/time averaging (the day-16 to day-35 leg is a pattern tool, not a degree-day tool).",
   "why_practitioners_use_it": "Free, and the multi-model blend measurably beats any single model (WCS states its CFSv2+ECMWF multi-model 'is always better than any single model'). The GEFS reforecast archive is the correct free calibration set for bias-correcting your own forecasts.",
   "we_already_have_it": "no"
  },
  {
   "name": "Gas-weighted degree days built on Census household-heating-fuel weights (the DTN/Frontier method)",
   "what_it_measures": "National/regional HDD weighted by where gas-heated households actually are, rather than by population. The published construction: state weight = (households x fraction heating primarily with NG) / total US households heating with NG.",
   "source": "Frontier Weather (now DTN) published methodology guide; weights derived from US Census Bureau county population + ACS primary-heating-fuel share. Station layer = ~230 observation sites, each US county assigned to one site, counties then aggregated to state/EIA/Census/NERC regions. Speedwell+CWG joint product uses 198 US locations across 344 climate divisions. All input data is free; the packaged index is paid.",
   "cost": "mixed",
   "horizon": "Same as the underlying temperature forecast (1-15 day operational; DTN downscales monthly outlooks to daily out to 9 months explicitly NOT as daily weather prediction but for weekly/monthly totals).",
   "skill_limit": "Published state weights (2013 vintage): CA 0.1330, NY 0.0664, IL 0.0624, TX 0.0586, MI 0.0552, OH 0.0525, PA 0.0427, NJ 0.0379 - top 8 states = 50% of national weight, bottom 20 states = 10%. DTN's own stated failure: their earlier blended series that folded electric-heat-from-gas-generation into the NG weight 'quickly became less accurate with time since they are all based on a set of fixed weights derived from older generation data.' Weights are HEATING-derived and are simply wrong in summer.",
   "why_practitioners_use_it": "It is the industry-standard denominator. A GWDD number quoted on a desk is this construction, so mismatched weights mean you are trading a different index than the market is.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Seasonal weight switch: population-weighted CDD, gas-weighted HDD",
   "what_it_measures": "The practitioner convention that summer and winter gas demand have different geographies, so the degree-day weighting must switch by season rather than being one fixed vector.",
   "source": "Speedwell Weather / Commodity Weather Group joint 'Population and Natural Gas Weighted Degree Days' product, which publishes exactly two national series: Population CDD and Nat Gas HDD, both built state -> region -> national.",
   "cost": "free",
   "horizon": "n/a - it is a weighting convention, applied at every horizon.",
   "skill_limit": "It is a coarse two-regime approximation. It does not handle shoulder months, where neither weighting dominates and degree-day sensitivity is at its lowest and noisiest.",
   "why_practitioners_use_it": "Winter gas demand follows gas-heated households; summer gas demand is dominated by power burn, which follows AC load and therefore population/generation, not heating fuel. Using heating weights on a CDD is a known category error.",
   "we_already_have_it": "no"
  },
  {
   "name": "Power-weighted CDD (PWCDD) - degree days weighted by where gas-fired generation runs",
   "what_it_measures": "Summer cooling degree days weighted to proxy power-burn demand specifically, rather than population or heating.",
   "source": "GasAlpha publishes PWCDD: weights derived from 3 years of summer natural gas generation across 47 balancing authorities mapped to the 9 EIA census divisions (South Atlantic 24.0%, West South Central 17.7%, largest two). Constructible free from EIA-930 BA-level gas generation, which this desk already ingests.",
   "cost": "mixed",
   "horizon": "Same as the underlying temperature forecast; the weighting itself is a slowly-drifting structural quantity.",
   "skill_limit": "Static 3-year weights go stale as the generation fleet turns over (the same failure DTN documented for its blended series). Critically, PWCDD says nothing about the renewables offset - it measures where gas COULD burn, not what actually clears after wind and solar.",
   "why_practitioners_use_it": "Summer gas demand is roughly half power burn, and the marginal Bcf is set by which BA is short, not by national population. Weighting to generation is the closest free proxy to marginal burn.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Forecast PROGRESSION - the run-to-run change in forecast gas-weighted degree days",
   "what_it_measures": "The DELTA in forecast GWDD between successive model runs (and between models), by forecast block (1-5, 6-10, 11-15). This is the quantity that actually trades; the level is largely already in the price.",
   "source": "Computable free from archived ECMWF open data + GEFS runs. Sold as a view by World Climate Service ('forecast progression tracking to monitor model changes over time'), GasAlpha (4-model GFS/IFS/GEFS/AIFS consensus updated 4x daily), NatGasWeather (updates 5z/9z/13z/21z UTC). CWG's published desk note format quotes the change from previous forecast in parentheses per EIA week.",
   "cost": "mixed",
   "horizon": "The delta on the 6-10 and 11-15 day blocks is what moves the front of the curve; the 1-5 day delta moves cash and prompt.",
   "skill_limit": "This is a NEWS process, not a forecast - it has no intrinsic skill, it measures repricing. And the underlying information content is thin where the deltas are largest: the measured HDD-anomaly-to-Henry-Hub relationship is significant only at roughly 2-4 days lead and weakens materially beyond 5-7 days across GFS, GEFS and ECMWF alike. So a day 11-15 delta is a sentiment move that frequently reverses on the next run.",
   "why_practitioners_use_it": "Because the market trades the revision. Trade press documents the mechanism repeatedly: futures gap at the Monday open on weekend model shifts, and paid services update overnight so professionals trade the change before the wider market sees it. Typical quoted magnitudes are small - models 'adding 3 HDD' or differing by 7 HDD is enough to move the tape.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Ensemble spread / forecast-risk index (AG2 FRisk-style)",
   "what_it_measures": "Within-ensemble dispersion relative to the CLIMATOLOGICAL spread for that location, calendar day and season - i.e. is the atmosphere unusually uncertain right now, normalized.",
   "source": "Computable free from ECMWF ENS + GEFS members. Atmospheric G2 sells FRisk: 100 bias-corrected equally-likely members distilled to a single 0-100 index, high = spread wider than climatological norm. Marketing claims ~3.5% profitability increase per trade; no independent validation published.",
   "cost": "mixed",
   "horizon": "All leads; most informative at day 5-12 where spread grows fastest.",
   "skill_limit": "THE key honest number: published spread-skill correlations 'generally have been found to be fairly modest and rarely exceed 0.5', which corresponds to explaining 25% or less of the variation in forecast accuracy. Spread is therefore a weak day-by-day predictor of forecast error and should condition MAGNITUDE/volatility regime, not be read as a point error forecast. Assessment is also statistically awkward (heteroscedastic; log-transform both spread and error).",
   "why_practitioners_use_it": "It is the only forward-looking read on how much the forecast can still move, which is what sizes a weather position. Desks use it to anticipate overnight forecast shifts and to set position size, not to pick direction.",
   "we_already_have_it": "partial"
  },
  {
   "name": "CPC 6-10 day and 8-14 day probabilistic outlooks (+ their verification archive)",
   "what_it_measures": "Probability that period-mean temperature falls in the upper/middle/lower tercile of the 1991-2020 climatological distribution, on a US grid.",
   "source": "NOAA Climate Prediction Center, free; prognostic discussions published as text (fxus06). Verification via the CPC Verification Web Tool and the short-range skill pages.",
   "cost": "free",
   "horizon": "Days 6-10 and 8-14 - exactly the block this desk's 2-week horizon lives in.",
   "skill_limit": "Scored by Heidke Skill Score (0 = no better than chance, 100 = perfect, -50 = worst possible). CPC does not headline a long-run average for 6-10/8-14; for calibration, the adjacent Week 3-4 product averages HSS 22 for temperature and 12 for precipitation. The product is human-adjusted, so it LAGS the raw model runs the market is already trading, and it gives terciles only - no magnitude, which is precisely what a degree-day model needs.",
   "why_practitioners_use_it": "Free, standardized, and it is the reference the trade press and the physical market quote. Its verification archive is a free ground-truth set for calibrating your own extended-range confidence.",
   "we_already_have_it": "no"
  },
  {
   "name": "CPC Week 3-4 temperature outlook",
   "what_it_measures": "Tercile probabilities for the days 15-28 mean - the 15-30 day window, bridging the gap between the 8-14 day and monthly outlooks.",
   "source": "NOAA CPC, free.",
   "cost": "free",
   "horizon": "Days 15-28.",
   "skill_limit": "Published average Heidke Skill Score of 22 for temperature (12 for precipitation) over a recent year. That is real skill but modest - roughly twice the precipitation product and far below anything usable as a point degree-day forecast. Stated skill sources: ENSO, MJO, long-term trend, sudden stratospheric warmings, soil moisture.",
   "why_practitioners_use_it": "It is the only free, verified, operational product in the 15-30 day window, and its stated skill sources tell you which teleconnections are worth tracking at that range.",
   "we_already_have_it": "no"
  },
  {
   "name": "MJO - RMM index (Wheeler-Hendon) phase and amplitude, plus model MJO forecasts",
   "what_it_measures": "Tropical convection propagation state in 8 phases; the single largest named source of predictability in the 3-4 week window.",
   "source": "Bureau of Meteorology RMM daily values from Jan 1979 (free); NOAA CPC daily MJO indices and statistical MJO forecasts (free); ECMWF ENS MJO plumes; NOAA PSL MJO research page. World Climate Service sells a 28-day MJO forecast and MJO-phase-filtered analog compositing.",
   "cost": "free",
   "horizon": "Dynamical models predict the MJO itself to roughly 3 weeks. ECMWF measured at ~31 days MJO skill; ensemble-mean bivariate RMM correlation reaches the 0.6 threshold at 21 days uncoupled vs 26 days coupled. Theoretical predictability is ~7 weeks, unreached.",
   "skill_limit": "Multiple hard limits. (1) US temperature response: DJF phases 4/5/6 give positive anomalies over the eastern US and Canada, phases 8/1/2 negative over the northeastern US - but phases 3 and 7 carry essentially NO significant surface-temperature signal, so the tool is dark on a quarter of the cycle. (2) Zhou et al. (2012) computed Heidke scores for MJO-composite US temperature forecasts assuming the future MJO phase is PERFECTLY KNOWN, and only over grid points passing 95% significance - a fraction of total area. All such forecasts were positive-HSS but that is an upper bound, not an operational number. (3) MJO extinction probability rises sharply after ~27 days. (4) Composites are contemporaneous with phase, so the tropics-to-extratropics lag is folded in implicitly rather than measured.",
   "why_practitioners_use_it": "It is the named mechanism behind the 15-30 day window and the one teleconnection whose forecast is genuinely skillful past two weeks. Desks gate on amplitude (typically require RMM amplitude > 1) and use phase to bias the week 3-4 lean.",
   "we_already_have_it": "no"
  },
  {
   "name": "AO / NAO / PNA daily teleconnection indices",
   "what_it_measures": "Hemispheric circulation regimes controlling cold-air delivery to the eastern US (the highest gas-weighted region block).",
   "source": "NOAA CPC free daily indices (rolling 120-day plus historical archive, ftp and web); teleconnection index calculation documentation published.",
   "cost": "free",
   "horizon": "Skillful in the medium range (1-2 weeks) and again at seasonal range with lead times up to ~2 months for the winter-mean AO/NAO in the best seasonal systems.",
   "skill_limit": "There is a published SUBSEASONAL SKILL GAP: NAO forecasts at 20-30 day lead are not statistically significant, sitting in a trough between skillful medium-range and skillful seasonal. Intraseasonal NAO and PNA retain 'lingering' skill above the hemispheric flow as a whole but it is 'quite low'. Do not build a week 3-4 gas call on the NAO. Week 3-4 predictability IS conditionally higher during extreme phases of ENSO, PNA/TNH and AO/NAO - so the usable form is a regime gate, not a continuous predictor.",
   "why_practitioners_use_it": "Free, daily, long history, and they are the vocabulary the desk research notes and the trade press use. Best used as a conditioning variable that flags when extended-range skill is above or below normal.",
   "we_already_have_it": "no"
  },
  {
   "name": "Stratospheric polar vortex: 10 hPa 60N zonal-mean zonal wind and SSW detection",
   "what_it_measures": "Polar vortex strength/displacement; an SSW is the classic precursor to sustained eastern-US cold and the biggest winter gas demand events.",
   "source": "NOAA CPC stratosphere monitoring, FU Berlin, ERA5 - all free. World Climate Service sells SPV-state-filtered analog compositing.",
   "cost": "free",
   "horizon": "Two distinct windows. Predicting whether/when an SSW occurs is roughly a 7-10 day problem (maximum measured lead for the 2021 event was 17 days). AFTER an SSW occurs, surface impacts persist 30-60 days via stratosphere-troposphere coupling, and ensembles that predict an SSW show REDUCED spread and reduced forecast error in vortex strength for several weeks after - most pronounced for strong SSWs.",
   "skill_limit": "An SSW is not a guaranteed cold signal: the January 2021 SSW is a published case of LIMITED surface impacts. Timing and evolution detail is 'about as successful as a 7-10 day weather forecast'. So the trade is not 'SSW therefore cold' - it is 'SSW occurred, therefore the next 4-6 weeks are a conditionally higher-skill window'.",
   "why_practitioners_use_it": "It is the only mechanism that legitimately buys a multi-week skill extension in winter, and it is the mechanism behind the price spikes that define the winter gas distribution's right tail.",
   "we_already_have_it": "no"
  },
  {
   "name": "ENSO / ONI",
   "what_it_measures": "Tropical Pacific SST state; a seasonal-scale conditioner of North American winter.",
   "source": "NOAA CPC ONI, IRI ENSO forecast plume - free.",
   "cost": "free",
   "horizon": "Seasonal to multi-season; effectively no resolution inside a 2-week window.",
   "skill_limit": "The NWS explicitly warns that ENSO composites 'are not intended to be a forecast of expected conditions' - they only highlight where ENSO CAN impact conditions. Confidence scales with event amplitude, so weak events carry little. The most reliable US signal is Gulf Coast precipitation (present in >80% of El Nino events over 100 years), NOT temperature - and temperature is what gas cares about.",
   "why_practitioners_use_it": "Sets the seasonal prior and the analog pool. Almost useless for a 6-30 day call and routinely over-read by non-specialists.",
   "we_already_have_it": "no"
  },
  {
   "name": "Confidence-gated subseasonal forecasting (act only on high-probability ensemble calls)",
   "what_it_measures": "Not a data feed - a selection rule. Restrict extended-range action to the sub-sample where the ensemble's own tercile probability is high.",
   "source": "World Climate Service published verification of its own subseasonal forecasts.",
   "cost": "free",
   "horizon": "Lead weeks 3 through 6.",
   "skill_limit": "Measured: at lead week 3 AND at lead week 6, forecasts issued with tercile probability >50% verified correct 51-69% of the time, against a 33.3% climatological base rate. Forecasts issued with tercile probability only >33.3% verified correct just 39-49%. So subseasonal skill is real but exists almost entirely inside the confident sub-sample; the low-confidence majority is close to noise. Also note skill does NOT decay smoothly from week 3 to week 6 in that sample - the same ranges are reported at both, which argues the gate matters more than the lead.",
   "why_practitioners_use_it": "It converts a weak average signal into a usable conditional one, and it is directly implementable as a NO-CALL rule: when the ensemble is not confident, do not take a weather-driven position at that horizon.",
   "we_already_have_it": "no"
  },
  {
   "name": "Forecast wind generation (day-ahead to day-7), not realized wind",
   "what_it_measures": "Expected renewable supply that will be subtracted from load BEFORE gas sets the residual - the term that breaks the degree-day-to-burn link.",
   "source": "ERCOT net load forecast (current day + next 6 days, free, load minus forecast wind and solar); ERCOT/MISO/SPP/PJM wind forecasts free; or convert ECMWF/GEFS 100m wind to generation yourself. Atmospheric G2 and others sell wind/solar generation forecasts commercially.",
   "cost": "free",
   "horizon": "Day-ahead is strong; useful to roughly day 5-7; near-useless in week 2.",
   "skill_limit": "Wind forecast skill degrades much faster than temperature skill, so the residual-load correction is only available over part of the window where degree days are still forecastable. Measured instance of why it matters: strong June wind muted historic Texas heat waves, with daily average gas generation 6% LOWER year-on-year while wind generation rose 90 GWh/d - a case where CDD rose and gas burn fell.",
   "why_practitioners_use_it": "Because the gas call is a stack: weather-driven load minus renewables minus what coal and nuclear absorb. A degree-day forecast without a wind forecast produces confidently wrong burn.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Own-forecast verification archive and model bias correction",
   "what_it_measures": "Systematic, lead-time-dependent and season-dependent bias in each model's degree-day output, measured against your own realized series.",
   "source": "Build free: archive ECMWF open data + GEFS runs, verify against realized NWS/ASOS-derived degree days. The GEFSv12 reforecast on AWS is a purpose-built free calibration set. COMET/UCAR publishes the standard bias-correction methodology.",
   "cost": "free",
   "horizon": "All leads; the bias signature is itself lead-dependent and is largest in the cold season.",
   "skill_limit": "Bias correction removes a very large part of annual MEAN forecast error and some variable error, especially in the cold season - but it cannot remove flow-dependent error, which is what produces busts. Documented direction of the standard biases varies by region and study: GFS carries a cold bias in several evaluations (ML correction recovering up to 0.88 C); ECMWF carries a warm bias over some regions and a cold bias over others (evaluations citing ~2.3 C average underestimate over North America in some cells). Because sign flips by region and season, a global bias constant is worthless - it must be per-cell.",
   "why_practitioners_use_it": "Vendors' central claim is that they sell bias-corrected guidance so 'the desk acts on what the models tend to get right'. That correction is reproducible free if you keep the archive - and without it you cannot distinguish a real forecast change from a model's habitual drift.",
   "we_already_have_it": "no"
  },
  {
   "name": "00z/12z versus 06z/18z run weighting",
   "what_it_measures": "Which model cycles the market actually respects, and why.",
   "source": "Free; mechanism is radiosonde launch timing. Practitioner statements from natural-gas weather services.",
   "cost": "free",
   "horizon": "Intraday to the full 15-day block.",
   "skill_limit": "Real mechanism, commonly overstated. The majority of global weather balloons launch near 00z and 12z, so those initializations use a denser observation network and the gas market puts much more weight on them. But the 06z and 18z runs are explicitly described by the same practitioners as 'very valuable for showing trends between model runs' - so discounting them entirely discards genuine trend information. This is as much a rule about market ATTENTION as about accuracy.",
   "why_practitioners_use_it": "It tells you when a forecast-driven price move is likely to be large (00z/12z) versus when a real forecast change may be sitting unpriced (06z/18z).",
   "we_already_have_it": "unclear"
  },
  {
   "name": "Degree-day/temperature shock as a priced futures factor (published event-study coefficients)",
   "what_it_measures": "The measured elasticity of natural gas futures returns to expected temperature shock and to inventory surprise, separately by contract maturity.",
   "source": "Peer-reviewed event study of temperature shock and inventory surprise on natural gas and heating oil futures returns. Shock defined as the sum of forward-forecast CDD and HDD at day t+k minus the 30-year average, on a 7-day forward forecast basis.",
   "cost": "free",
   "horizon": "Defined on a 7-day forward forecast; effects measured on both near-month and far-month contracts.",
   "skill_limit": "Coefficients are small and the specification depends heavily on station aggregation: near-month natural gas temperature coefficient 0.062 (p<0.01) with a single weather station versus 0.1038 (p<0.01) with multiple stations - i.e. the measured elasticity nearly doubles purely from better spatial weighting. Far-month 0.0488 / 0.0983. Inventory surprise: near-month -0.0095 (p<0.10), far-month -0.0141 (p<0.05), with far-month MORE sensitive to inventory than near-month.",
   "why_practitioners_use_it": "It is one of the few published, sign-and-magnitude-specific links from a degree-day construct to futures returns, and the single-versus-multiple-station result is direct evidence that degree-day weighting quality is worth roughly a doubling of measured signal.",
   "we_already_have_it": "unclear"
  }
 ],
 "skill_horizon_notes": "The binding question - how far out a useful forecast is possible - has a reasonably consistent published answer, and it is shorter than the desk's 2-week target in its strong form.\n\nTHE CONVERGENT NUMBERS, from four independent directions:\n1. Vendor verification (World Climate Service): \"at around 12 days ahead, the skill of the forecast matches the skill of climatology.\" Beyond ~day 12 the raw forecast adds nothing over a climatological prior.\n2. Price-relationship verification (also WCS, on Henry Hub): the relationship between CONUS gas-consumption-weighted HDD anomalies and normalized Henry Hub spot is significant at roughly 2-4 days lead and \"progressively weaker beyond roughly five to seven days,\" consistent across GFS, GEFS and ECMWF. Note this is much shorter than the meteorological limit - the market has already priced the forecastable part. Full-sample R-squared is described as modest even in the strongest lead window.\n3. ECMWF's own extended-range verification: week 2 tercile 2m temperature skill exceeds persistence by ~10% and climatology by ~40%; weeks 3-4 combined drops to ~5% over persistence and ~20% over climatology (extratropics). The 2025 evaluation reports week 2 on a \"continuing trend of increasing skill\" but weeks 3-4 only a \"marginally significant trend\" - i.e. two decades of model improvement have barely moved the 15-30 day window.\n4. CPC operational: Week 3-4 temperature outlook averages Heidke Skill Score 22 (precipitation 12). Real, but far below point-forecast usability.\n\nTHE STRUCTURAL SHAPE. There are effectively three regimes, and they should be modeled separately rather than as one decaying curve:\n- Days 1-5: deterministic, the degree-day number is close to knowable, and it is largely already in the price.\n- Days 6-12: the tradeable zone. Ensemble mean carries genuine information, the run-to-run DELTA is the market-moving quantity, and this is where a distribution (not a point) is the correct output. Skill dies at the top of this range.\n- Days 12-30: no unconditional skill. Skill exists only CONDITIONALLY, and only in named windows.\n\nTHE CONDITIONAL WINDOWS ARE THE ONLY HONEST WAY PAST DAY 12. Three are documented:\n(a) Ensemble self-confidence. Measured: forecasts issued at tercile probability >50% verified 51-69% correct at BOTH lead week 3 and lead week 6, against a 33.3% base rate; low-confidence forecasts (>33.3% only) verified 39-49%. Skill lives almost entirely in the confident sub-sample. Notably the ranges are the same at week 3 and week 6, which suggests the confidence gate matters more than the lead.\n(b) An active MJO. Models predict the MJO itself to ~3 weeks (ECMWF ~31 days; bivariate RMM correlation crossing 0.6 at 21 days uncoupled / 26 days coupled), and phases 4/5/6 versus 8/1/2 carry opposite-signed eastern-US temperature anomalies in DJF. But phases 3 and 7 carry no significant surface-temperature signal, and MJO extinction probability rises sharply after ~27 days.\n(c) A sudden stratospheric warming that has ALREADY OCCURRED. The event itself is only a 7-10 day forecast problem (17 days maximum measured lead for the 2021 case), but once it happens, surface impacts persist 30-60 days AND ensemble spread in vortex strength measurably contracts for several weeks. This is the single largest legitimate skill extension available in winter - and it is not a guarantee, since the January 2021 SSW is a published case of limited surface impact.\n\nWHAT DOES NOT BUY EXTENSION: the NAO at subseasonal range. There is a documented, statistically-insignificant \"skill gap\" at 20-30 day lead sitting between skillful medium-range NAO and skillful seasonal NAO. Also worth noting: week 3-4 skill survives only at coarser spatial and temporal averaging - the forecast-skill horizon for large-scale Z500 rises from ~2-3 weeks for daily grid-point fields to ~3-4 weeks only when you average over up to 16 days and coarse space. That averaging destroys exactly the daily resolution a degree-day model needs.\n\nIMPLICATION FOR THIS DESK'S METHOD. Because the desk projects conditions forward then matches an analog day and re-anchors the level, the correct reading is: the CONDITIONS projection is trustworthy to about day 10-12 and should carry an explicit distribution, not a point. Past that, the honest output is a regime/pattern label with a confidence gate and, when the gate fails, an explicit no-call rather than a forced number. That maps directly onto the structural finding already recorded in this repo that the system cannot currently emit a NO CALL - the weather literature says the 15-30 day window is precisely where that option is needed most.",
 "debunked_or_folklore": [
  "ENSO composites read as a forecast. The National Weather Service states explicitly that ENSO composites 'are not intended to be a forecast of expected conditions' - they only show where ENSO CAN have an impact. Individual events differ, and extreme single events can dominate a composite. Confidence scales with event amplitude, so weak-ENSO winters carry almost nothing. The strongest verified US El Nino signal is Gulf Coast PRECIPITATION (>80% of events over 100 years), not temperature - and temperature is what gas trades.",
  "'The day 11-15 forecast moves the market, so it must have skill.' The price reaction is real and documented; the skill is not. Forecast skill equals climatology skill at roughly day 12, and the measured HDD-anomaly-to-Henry-Hub relationship is only significant at 2-4 days lead. A day 11-15 degree-day delta is a repricing event, not information - which is why so many of them reverse on the next run. These are two different quantities and should not be modeled with one coefficient.",
  "'The European model is always right.' Measured: ECMWF leads on headline scores and has better week 3-4 temperature and precipitation skill than CFSv2, but the multi-model blend beats any single model - WCS states its CFSv2+ECMWF combination 'is always better than any single model.' Single-model devotion is a measurable cost.",
  "'A sudden stratospheric warming means cold is coming.' The January 2021 SSW is a published counterexample with limited surface impacts, despite occurring. An SSW raises the probability and opens a higher-skill window; it does not deliver the outcome. Treating SSW as a directional trigger rather than a regime gate is a real trap.",
  "Ensemble spread read as a per-day error forecast. Published spread-skill correlations 'rarely exceed 0.5', explaining 25% or less of the variation in forecast accuracy. Wide spread does not reliably mean today's forecast is wrong. Spread is a volatility/magnitude conditioner, not a point-error predictor - and spread-skill correlation itself has been criticized as a misleading verification metric.",
  "'Hurricane season is bullish natural gas.' This has inverted post-shale. Offshore Gulf production is now a small share of US supply, while LNG export capacity is concentrated on the Gulf Coast - a single major hurricane landfall at Sabine Pass could affect roughly half of US LNG capacity, about 12% of total US gas consumption. A storm now more often destroys DEMAND (feedgas shut-in) than supply, and trade press documents gas prices WEAKENING on tropical storm risk. Direction depends on the storm's track relative to export terminals versus production, and cannot be assumed.",
  "'Ignore the 06z and 18z GFS runs.' Half true, and the mechanism is real - most global radiosondes launch near 00z and 12z, so those initializations use a denser observing network and the gas market weights them far more heavily. But the same practitioners state the 06z/18z runs are 'very valuable for showing trends between model runs.' Discarding them entirely throws away trend continuity; the correct handling is to downweight their market impact, not their information.",
  "Blended 'natural gas weighted' degree days that fold electric-heat-from-gas-generation into one fixed weight vector. DTN/Frontier abandoned exactly this construction and said so in print: those datasets 'quickly became less accurate with time since they are all based on a set of fixed weights derived from older generation data.' A blended weight built on a generation mix that is actively changing decays without announcing it.",
  "Using one fixed degree-day weight vector year-round. The industry convention publishes POPULATION-weighted CDD and GAS-weighted HDD as two separate series precisely because summer and winter gas demand have different geographies. Applying heating-household weights to a CDD is a category error, not a refinement.",
  "Vendor performance claims. Atmospheric G2 advertises a '3.5% Increase in Profitability Per Trade' and an '80% reduction in time spent interpreting weather data'; Enverus advertises a 7-day timing edge on Winter Storm Elliott. None of these are accompanied by published MAE, RMSE, skill scores or independent validation. Treat as marketing until independently measured against your own archive."
 ],
 "gaps_vs_our_stack": [
  "RAW ECMWF ENS MEMBERS - highest expected value, and it is now FREE. Since 1 Oct 2025 ECMWF opened the full real-time catalogue under CC-BY-4.0 with data charges removed; ENS is available at 0.25 deg to day 15 (0-144h/3h then 150-360h/6h at 00/12z), mirrored on AWS Open Data. The desk currently has MOS-based forecast temperatures, which is deterministic station guidance - it cannot produce a degree-day DISTRIBUTION, cannot produce spread, and is not the instrument the market prices off. This one feed simultaneously fills the ensemble gap, the spread gap and the probabilistic-path gap, at zero cost. It should be first.",
  "FORECAST-PROGRESSION DELTAS ON GAS-WEIGHTED DEGREE DAYS - the run-to-run and model-to-model CHANGE by forecast block (1-5, 6-10, 11-15), not the level. This is the quantity that actually trades; the level is already in the price. The desk has MOS cycle timing, which is the timing half, but not the multi-model degree-day delta itself. This is also the direct instrument for the Friday-to-Monday cascade the desk has documented: futures gap at the Monday open on weekend model shifts, and paid services update overnight so professionals trade the change first. Build it as a pre-open quantity.",
  "REBUILD THE GWDD WEIGHTS ON THE PUBLISHED HOUSEHOLD-HEATING-FUEL METHOD, SEASONALLY SWITCHED. The desk's own notes record that the weights are hand-set, unvalidated, and that OHIO HAS NO STATION - Ohio is the 6th largest state in the published national NG-heating weight at 0.0525, and sits inside PJM, the largest gas-burning BA. The DTN/Frontier construction is fully published and reproducible from free Census ACS heating-fuel data: state weight = (households x fraction heating primarily with NG) / total US NG-heating households, with counties assigned to ~230 stations. Then switch seasonally to a power-weighted CDD for summer, buildable free from the EIA-930 BA-level gas generation the desk already ingests. Independent evidence this is worth real money: the published futures event study found the temperature coefficient on near-month gas nearly DOUBLED (0.062 to 0.1038) purely by moving from a single weather station to multiple stations.",
  "ENSEMBLE SPREAD AS A MAGNITUDE CONDITIONER. The desk's stated dominant residual is MAGNITUDE, and spread normalized against climatological spread (the FRisk construct) is the standard forward-looking read on how much a forecast can still move. It is free once the ENS members are in hand. Import it with the published limit attached: spread-skill correlation rarely exceeds 0.5, so it conditions size and volatility, it does not predict per-day error. Note this is a DIFFERENT quantity from the desk's existing model-disagreement measure - between-model disagreement and within-ensemble spread are not the same thing and should be carried as two variables.",
  "A FORECAST VERIFICATION ARCHIVE AND PER-CELL BIAS MODEL. The desk has no archive of its own past forecasts versus realized degree days, so it cannot distinguish a genuine forecast change from a model's habitual drift. This is exactly the 'bias-corrected guidance' that vendors charge for, and it is reproducible free - the GEFSv12 reforecast on AWS is a purpose-built calibration set. Critical design constraint from the literature: bias sign FLIPS by region and season (GFS cold-biased in several evaluations, ECMWF warm over some regions and cold over others), so a global constant is worthless; it must be per-cell, matching this desk's existing per-cell doctrine.",
  "FORECAST WIND GENERATION, DAYS AHEAD - not realized wind. This is the desk's documented 0629 failure mode: gw_cdd rose exactly as forecast and gas burn FELL 4.2 Bcf/d because wind rose 62%, with realized wind_mwh served in every slice and read by nobody. Realized wind cannot fix a forward call - the forecast is what is needed. Free sources: ERCOT publishes a net load forecast (load minus forecast wind and solar) for the current day plus 6; MISO/SPP/PJM publish wind forecasts. Confirming out-of-sample instance: strong June wind muted historic Texas heat waves with gas generation 6% lower year-on-year while wind rose 90 GWh/d. Honest limit: wind forecast skill fades by roughly day 5-7, so this correction is only available over part of the window.",
  "A CONFIDENCE GATE WITH AN EXPLICIT NO-CALL AT 12+ DAYS. The measured subseasonal result is that skill lives almost entirely in the confident sub-sample: tercile probability >50% verifies 51-69% correct at lead weeks 3 AND 6, versus 39-49% for merely >33.3%, against a 33.3% base rate. This is a selection rule, costs nothing, and maps directly onto the structural finding already recorded in this repo - that a specialist wrote correct handling was NO CALL and could not emit it because the contract requires a numeric magnitude. The weather literature says the 15-30 day window is precisely where that option is required. Fixing the contract is a prerequisite for using anything past day 12 honestly.",
  "MJO RMM PHASE AND AMPLITUDE, GATED. Free from BoM (daily from 1979) and CPC (daily indices plus statistical forecasts). Import with three gates attached, all published: require amplitude > 1; treat phases 3 and 7 as NO SIGNAL for US surface temperature; and remember the composite skill numbers assume the future phase is perfectly known over only the significant-area fraction, so they are an upper bound. This is the single named mechanism that legitimately reaches into the desk's 15-30 day window.",
  "STRATOSPHERIC POLAR VORTEX STATE (10 hPa, 60N zonal-mean zonal wind). Free from CPC/FU Berlin/ERA5. Value is asymmetric and conditional: predicting an SSW is a 7-10 day problem, but once one occurs it opens a 30-60 day window of elevated surface predictability with measurably reduced ensemble spread. This is the highest-value winter regime flag the desk does not have - carried as a gate, never as a directional trigger.",
  "CPC 6-10 DAY, 8-14 DAY AND WEEK 3-4 OUTLOOKS PLUS THEIR VERIFICATION ARCHIVE. Free, and the 6-10/8-14 blocks are exactly the desk's window. Lower priority than raw ensembles because they are human-adjusted (so they LAG the model runs the market already traded) and give terciles without magnitude. But the verification archive is independently valuable as free ground truth for calibrating extended-range confidence, and the Week 3-4 HSS of 22 is the right sanity benchmark for anything the desk builds at that range.",
  "AO / NAO / PNA DAILY INDICES. Free from CPC. Lowest priority of the teleconnections because of the published subseasonal skill gap - NAO forecasts at 20-30 day lead are not statistically significant. Worth carrying not as predictors but as REGIME GATES, since week 3-4 predictability is measurably higher during extreme phases of ENSO, PNA/TNH and AO/NAO. That is a conditioner on when to trust the extended range at all."
 ],
 "sources": [
  "https://www.worldclimateservice.com/2026/03/25/henry-hub-and-weather-forecasts-spot-price-relationship/",
  "https://www.worldclimateservice.com/2021/09/10/subseasonal-forecasting-skill/",
  "https://www.worldclimateservice.com/subseasonal/",
  "https://www.worldclimateservice.com/natural-gas-trading/",
  "https://www.worldclimateservice.com/trading-markets-application/",
  "https://frontierweather.dtn.com/GuidetoFWPopulationandGasWeightedData.pdf",
  "https://portal.speedwellclimate.com/PDF/ForecastHome/WDD%20(SWD%20marketing).pdf",
  "https://gasalpha.com/pwcdd",
  "https://gasalpha.com/",
  "https://www.ecmwf.int/en/newsletter/175/news/forecast-performance-2022",
  "https://www.ecmwf.int/en/newsletter/187/news/forecast-performance-2025",
  "https://www.ecmwf.int/en/forecasts/about-our-forecasts/sub-seasonal-range-forecasts",
  "https://www.ecmwf.int/en/about/media-centre/focus/2025/fact-sheet-sub-seasonal-and-seasonal-predictions",
  "https://confluence.ecmwf.int/display/FUG/Section+6.2.1+ECMWF+headline+scores",
  "https://confluence.ecmwf.int/spaces/DAC/pages/272310539/ECMWF+open+data+real-time+forecasts+from+IFS+and+AIFS",
  "https://www.ecmwf.int/en/about/media-centre/news/2025/ecmwf-makes-its-entire-real-time-catalogue-open-all",
  "https://www.ecmwf.int/sites/default/files/elibrary/2007/15443-verifying-relationship-between-ensemble-forecast-spread-and-skill.pdf",
  "https://www.climate.gov/news-features/blogs/enso/cpc%E2%80%99s-new-week-3-4-temperature-and-precipitation-outlook-success-story",
  "https://www.cpc.ncep.noaa.gov/products/predictions/short_range/verifications/html/srskill_exp.html",
  "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/teleconnections.shtml",
  "https://www.cpc.ncep.noaa.gov/products/precip/CWlink/MJO/mjo.shtml",
  "https://www.cpc.ncep.noaa.gov/data/teledoc/teleindcalc.shtml",
  "https://www.atmos.albany.edu/daes/atmclasses/atm421/Reference_Material_files/Zhouetal_2012.pdf",
  "https://link.springer.com/article/10.1007/s00382-011-1001-9",
  "https://journals.ametsoc.org/view/journals/clim/31/10/jcli-d-17-0545.1.xml",
  "https://arxiv.org/pdf/2304.12863",
  "https://link.springer.com/article/10.1007/s00382-018-4484-9",
  "https://journals.ametsoc.org/doi/abs/10.1175/JCLI4072.1",
  "https://rmets.onlinelibrary.wiley.com/doi/10.1002/asl.1146",
  "https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2023GL104057",
  "https://www.nature.com/articles/s41467-022-28836-1",
  "https://pmc.ncbi.nlm.nih.gov/articles/PMC7492229/",
  "https://www.climate.gov/news-features/blogs/polar-vortex/predicting-chances-polar-vortex-disruption-winter",
  "https://pmc.ncbi.nlm.nih.gov/articles/PMC4122141/",
  "https://onlinelibrary.wiley.com/doi/full/10.1002/fut.22402",
  "https://atmosphericg2.com/products/frisk/",
  "https://atmosphericg2.com/ag2trader/",
  "https://www.commoditywx.com/",
  "https://www.enverus.com/blog/every-degree-moves-the-market-why-point-forecasting-beats-gfs-for-natural-gas-traders/",
  "https://natgasweather.com/",
  "https://registry.opendata.aws/noaa-gefs/",
  "https://registry.opendata.aws/noaa-gefs-reforecast/",
  "https://registry.opendata.aws/noaa-ufs-gefsv13replay-pds/",
  "https://noaa-gefs-retrospective.s3.amazonaws.com/Description_of_reforecast_data.pdf",
  "https://www.ncei.noaa.gov/products/weather-climate-models/global-ensemble-forecast",
  "https://www.meted.ucar.edu/nwp/bias_correction/print.htm",
  "https://www.weather.gov/twc/enso",
  "https://bakerobrien.com/article/after-the-storm-how-hurricanes-influence-lng-facilities-and-natural-gas-hub-pricing",
  "https://www.naturalgasintel.com/news/will-lng-exporters-dodge-hurricane-season-again-this-year/",
  "https://naturalgasintel.com/news/forecast-swings-trigger-hectic-natural-gas-trading-ahead-of-weekend/",
  "https://www.spglobal.com/energy/en/news-research/latest-news/natural-gas/070722-ercot-peakload-records-texas-wind-output-may-fall-july-8-12-gas-burn-may-fill-in",
  "https://www.gridstatus.io/datasets/ercot_net_load_forecast",
  "https://www.ercot.com/gridinfo/load/forecast",
  "https://rbnenergy.com/under-the-weather%E2%80%93cooling-degree-days-natural-gas-storage-and-price",
  "https://www.eia.gov/outlooks/steo/documentation/nat_gas_cons_prices.pdf"
 ]
}
```

## LENS: US natural gas supply-demand balance and storage analytics (Henry Hub)

```json
{
 "domain": "US natural gas supply-demand balance and storage analytics (Henry Hub)",
 "signals": [
  {
   "name": "Daily L48 dry-gas production nowcast (pipeline receipt scrape)",
   "what_it_measures": "Bcf/d of dry gas entering the pipeline grid, nowcast by summing scheduled quantities at production receipt points across interstate pipeline EBBs and scaling to a full-L48 estimate. This is the single largest line in the daily balance and the only major one with no free public daily series.",
   "source": "PAID: Wood Mackenzie (ex-Genscape) near-real-time flows for 190+ North American pipelines / ~900 operational updates / ~20,000 locations, delivered by 07:00 ET each weekday across 16 US/Canada regions; S&P Global Commodity Insights (ex-Platts Bentek / PointLogic), explicitly 'pipeline receipt nominations plus certain state production data'; Criterion Research (also distributed via ICE Developer Portal); East Daley Analytics; NatGasHub (150+ inter- and intrastate pipes, SaaS 'call for price'). FREE: direct scrape of the pipelines' own FERC Order 587 / NAESB WGQ informational postings - 'Operationally Available Capacity' and 'Total Scheduled Quantity' by cycle and point, legally required to be posted daily on a publicly accessible site in downloadable format. Concrete example with no login: northernnaturalgas.com Operationally Available Capacity posting, 7 nomination cycles, point-level, queryable by gas day.",
   "cost": "mixed",
   "horizon": "0-3d as a nowcast; the level is highly persistent so it conditions the 1-2wk balance",
   "skill_limit": "It is a sample-and-scale ESTIMATE, not a measurement, and vendors revise it. Wood Mackenzie cut its L48 estimate outright after double-counting Williams' Louisiana Energy Gateway when that system started up in late July - a several-hundred-MMcf/d error that traded. Intrastate systems (very large in Texas and Louisiana) are not on interstate EBBs at all, so the scrape structurally under-covers Permian/Haynesville/Gulf. Same-day totals move across Timely -> Evening -> ID1/2/3. Truth series is EIA-914 monthly at roughly a 2-month lag (May 2026 preliminary dry production 110.3 Bcf/d published in the June/July Natural Gas Monthly).",
   "why_practitioners_use_it": "Supply is half the balance and the half that moves for non-weather reasons - freeze-offs, maintenance, new pipe in service. Every sell-side gas desk and gas hedge fund runs one of these; NGI, RBN and East Daley quote the daily number in every note. A 1 Bcf/d production shift is ~7 Bcf/week of storage, i.e. larger than the entire EIA print consensus range on a typical week.",
   "we_already_have_it": "no"
  },
  {
   "name": "LNG feedgas nominations, daily by terminal",
   "what_it_measures": "Bcf/d nominated into liquefaction terminals, read off scheduled quantities at the ~10 pipelines that serve them: Creole Trail / Transco Zone 4A / NGPL into Sabine Pass; Corpus Christi Pipeline; Cameron Interstate; Gator Express (sourcing from TGP, Texas Eastern and Columbia Gulf) into Plaquemines; TransCameron into Calcasieu Pass; Golden Pass Pipeline; Dominion Cove Point; Elba Express.",
   "source": "FREE by targeted EBB scrape of those ~10 pipelines (a far smaller job than a full production scrape). PAID packaged by Wood Mackenzie, S&P Global, Criterion, East Daley, and as a standalone product by natgasweather ('LNG Daily Feedgas Estimate'). Trade press quotes it daily for free but lagged: NGI reported noms 'estimated to reach 19.3 Bcf/d Wednesday and average 18.7 Bcf/d in the coming seven days'; East Daley tracked Plaquemines passing 4 Bcf/d.",
   "cost": "mixed",
   "horizon": "0-2d hard; 1-4wk when overlaid with the terminal maintenance and commissioning calendar",
   "skill_limit": "Nominations are not liquefaction. Commissioning cargoes, cooldown gas and terminal upsets decouple noms from actual exports for weeks at a time - the entire Plaquemines and Corpus Christi Stage 3 ramps were periods where noms overstated steady-state demand. Noms also revise across cycles. Aggregate ~15 Bcf/d is dominated by a handful of sites, so a single-terminal trip is idiosyncratic, not a market signal, unless it is one of the big three.",
   "why_practitioners_use_it": "It is the fastest-growing demand line and the one that is knowable BEFORE the gas day rather than inferred after it. Feedgas moved from ~13 Bcf/d to ~15 Bcf/d in a single quarter on the Plaquemines ramp; that is a 14 Bcf/week storage swing available from a public posting.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Pipeline exports to Mexico, daily by border point",
   "what_it_measures": "Bcf/d crossing at the South Texas (NET Mexico/Ramones), Waha (Comanche Trail, Roadrunner, Trans-Pecos) and offshore (Sur de Texas-Tuxpan via Valley Crossing) points. Highly seasonal and increasingly weather-sensitive as Mexican power burn grows.",
   "source": "FREE: US-side border-point scheduled quantities on the same interstate EBBs; CENAGAS/SISTRANGAS public postings for the Mexican side (10 reception points, 4 of them US import points - Ramones, El Sauz, Gaza, El Castillo). PAID/packaged: Wood Mackenzie explicitly runs 'proprietary monitors at exporting pipelines at the Mexican border'; S&P Global, Criterion. Monthly truth series free from EIA (6.63 Bcf/d in 2025; 7.85 Bcf/d in May 2026).",
   "cost": "mixed",
   "horizon": "0-3d nowcast, 2-4wk seasonally",
   "skill_limit": "Mexican-side demand is opaque and gas-quality-driven rerouting ('non-compliant molecules') creates step changes with no US-visible cause. Monthly EIA truth arrives ~2 months later. Border noms can be scheduled and not taken.",
   "why_practitioners_use_it": "It is ~7-8 Bcf/d of demand that is invisible in every domestic consumption series, and it swings on Mexican summer heat rather than US heat - so it decorrelates from the desk's own HDD/CDD view exactly when that matters.",
   "we_already_have_it": "no"
  },
  {
   "name": "Canadian net imports, daily by border point",
   "what_it_measures": "Bcf/d entering at Huntingdon, Kingsgate, Eastport (Westcoast/NGTL), the Alliance border point, and Great Lakes/Iroquois/Chippawa/Niagara in the east - plus the reverse-flow re-export.",
   "source": "FREE and official but LAGGED: Canada Energy Regulator throughput-and-capacity dataset on the Open Government portal (DOI 10.35002/h579-7v23), daily granularity, no cost - but Group 1 companies file within 45 days of quarter end, so it is a calibration/backfill series, not a nowcast. FREE nowcast path: US-side border receipt points on TC Energy / Alliance / Great Lakes EBBs. PAID: Wood Mackenzie covers Canada in its 16-region daily.",
   "cost": "free",
   "horizon": "0-3d via EBB scrape; the CER series is 6-8wk lagged",
   "skill_limit": "The CER file is useless for trading at its native latency - it settles disputes, it does not call days. WCSB supply responds to AECO-Henry Hub spread and to its own freeze-offs, which are not in any US weather series.",
   "why_practitioners_use_it": "Net imports are a 5-9 Bcf/d swing line that goes hard negative on Canadian cold snaps at precisely the moment US demand peaks - a same-direction shock the domestic balance misses.",
   "we_already_have_it": "no"
  },
  {
   "name": "Pipeline critical notices and the planned-maintenance calendar",
   "what_it_measures": "Force majeure, compressor outages, capacity restrictions, operational flow orders and scheduled maintenance, posted by every interstate pipeline on its EBB under NAESB critical/non-critical flags, with effective dates that are usually days-to-weeks in the FUTURE.",
   "source": "FREE at source: each pipeline's EBB notices section; monthly maintenance reports are separately posted as 'Planned Service Outage'. PAID aggregators: Enercast (AI-scored critical notices with re-route and basis-impact analysis), PipeRiv (~200 operators, paid, has an API), Criterion, Wood Mackenzie. NAESB's own NGINSIGHT documentation notes that scraping is fragile and that the industry moved to EDI feeds.",
   "cost": "mixed",
   "horizon": "1-6wk - this is the rare balance signal whose information is dated FORWARD by construction",
   "skill_limit": "Notices are unstructured prose with no standard severity field; the same event is posted differently by each operator, and pipelines routinely post and then cancel. Impact is not stated in Bcf/d - converting a notice to a flow effect requires knowing the point's baseline utilisation. NAESB's own working group concluded website scraping is unreliable because of ownership changes and format drift. Most notices have zero price impact; the base rate of tradeable ones is low.",
   "why_practitioners_use_it": "Almost every other input in this domain is a nowcast or a lagged truth. Maintenance calendars and in-service dates are the main class of supply-demand information that is genuinely KNOWN weeks ahead, which is exactly the horizon this desk forecasts. Seasonal maintenance clusters (spring and fall shoulder) are the reason shoulder-season production dips are predictable rather than surprising.",
   "we_already_have_it": "no"
  },
  {
   "name": "EIA WNGSR 'implied flow' versus 'net change', with the reclassification flag",
   "what_it_measures": "Net change reflects everything that hit working gas, including base-to-working-gas reclassifications. Implied flow strips out reportable reclassifications (those totalling 4 Bcf or more) and is the physical-flow number. The difference is an accounting artifact, not a balance signal.",
   "source": "FREE. Published in the Weekly Natural Gas Storage Report and defined in ir.eia.gov/ngs/notes.html and /methodology.html. Available as .txt, .csv and .json, plus the EIA API v2.",
   "cost": "free",
   "horizon": "0-1d event; feeds the weekly balance",
   "skill_limit": "The published implied flow still contains unpublished net revisions of LESS than 4 Bcf, so it is not a clean physical number - it is 'net change minus the big accounting items'. Reclassifications below 4 Bcf are invisible entirely. NGI documented a reclassification adjustment producing 'a huge headline miss that drove some traders to the sidelines' - i.e. the headline surprise was pure artifact and the price move was real anyway.",
   "why_practitioners_use_it": "Because consensus surveys forecast the FLOW and the tape prints the NET CHANGE. On reclassification weeks the two diverge by more than the entire survey range, and a desk that scores its own forecast against net change books a mechanical error and, worse, learns a false lesson from it.",
   "we_already_have_it": "unclear"
  },
  {
   "name": "EIA WNGSR published sampling standard error and coefficient of variation",
   "what_it_measures": "EIA publishes, weekly, the estimated standard error of the net-change estimate and the coefficient of variation of the level, for the L48 and for each region, in the 'Estimated measures of sampling variability' table.",
   "source": "FREE, on ir.eia.gov/ngs/ngs.html alongside the print. Methodology: stratified PPS sample (six strata: East, Midwest, Mountain, Pacific, South Central Salt, South Central Nonsalt), ~80-85 respondents on EIA-912 covering at least 90% of volumes per stratum, target relative standard error <=5% of the working gas estimate per stratum, standard errors computed by bootstrap with 1,000 replicates and a finite-population correction. Pacific has been a full census since 2018.",
   "cost": "free",
   "horizon": "0-1d event",
   "skill_limit": "This is the hard number for how much of a 'surprise' is real. EIA's own worked example: an L48 net change of -50 Bcf with a published SE of 2.2 Bcf gives a 90% margin of error of about 4 Bcf. So a print that beats consensus by 3-4 Bcf is inside the measurement error of the print itself. Sampling error is only one of six error classes EIA lists (sampling, coverage, nonresponse, adjustment, measurement, processing) and it does not quantify the other five. Non-sampled operators are imputed from a 12-month moving average scaled by a stratum seasonality coefficient, which will systematically miss a genuinely unusual week.",
   "why_practitioners_use_it": "It bounds the tradeable surprise. Almost nobody uses it, and it is free and weekly. For a desk whose recurring failure mode is treating a small well-formed number as information, this is a published noise floor.",
   "we_already_have_it": "no"
  },
  {
   "name": "Storage survey consensus DISPERSION (range and standard deviation), not just the median",
   "what_it_measures": "The spread of analyst estimates for the weekly print. A Reuters poll of 13 analysts showing 17 to 67 Bcf around a 60 Bcf median is a different market state from one showing 33 to 38 Bcf around 35.",
   "source": "FREE from the published survey headlines - Reuters poll, Bloomberg, Dow Jones/WSJ survey, NGI's own model and survey, the Enelyst trader community. Energy Edge and NGI publish the range each week.",
   "cost": "free",
   "horizon": "0-1d event, plus a 2-5d after-effect while positioning resolves",
   "skill_limit": "Ederington, Linn and Zhang (SSRN 4645640, two ~8-year samples 2003-2012 and 2013-2021) find analysts ANTI-herd or neither herd nor anti-herd; accuracy DECREASES as anti-herding intensity rises, and accuracy also decreases the earlier a forecast is released. Those two variables alone explain over 50% of the cross-firm variation in accuracy. So dispersion is partly genuine uncertainty and partly analysts differentiating themselves for career reasons - it is a contaminated measure. Post-2012 overall accuracy improved, which shrinks the tradeable surprise. Note also that the median of a survey is not an equal-quality aggregate: late-released forecasts are systematically better.",
   "why_practitioners_use_it": "Magnitude of the print reaction scales with how genuinely unresolved the number was, not with the raw Bcf deviation. Fernandez-Perez, Garel and Indriawan (Energy Journal 41(5), 2020) additionally show that crowd-sourced storage forecasts are LESS accurate than professional forecasts and add nothing to the market's expectation beyond the professional consensus - so a wide crowd range is noise, a wide professional range is information.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Degree-day-adjusted balance residual (weather-normalised tightness, Bcf/d)",
   "what_it_measures": "Regress weekly implied storage flow on gas-weighted HDD and CDD (and a seasonal/trend term), then read the RESIDUAL as Bcf/d of structural tightness or looseness versus the same weather a year ago. The desk-floor phrasing is 'the market is X Bcf/d tighter than last year on a weather-adjusted basis.'",
   "source": "FREE and fully derivable from series this desk already holds: EIA implied flow plus its own NWS-derived gas-weighted HDD/CDD. The regression form is documented by EIA itself in the STEO natural gas consumption module (HDD deviation from normal weighted by number of residential gas customers; a composite that adds gas-weighted HDD to roughly 0.72x population-weighted CDD appears in EIA's consumption documentation). Commercial versions: Bespoke Weather Services' storage/market-balance analysis, Celsius Energy, EBW, Criterion.",
   "cost": "free",
   "horizon": "1-4wk - this is the measure that carries information PAST the weather-forecast horizon, because it describes the non-weather part of the balance",
   "skill_limit": "Degree-day weights are seasonal and NOT stable: summer gas demand is roughly half power burn, so a winter-calibrated gas-weighted HDD map is the wrong weighting for a July balance. The correct summer weighting is by where gas-fired generation runs, not where people live - GasAlpha's PWCDD reweights East North Central from ~20% under GWDD to ~11%, with South Atlantic at 24.0% and West South Central at 17.7%. The residual also absorbs every structural break (an LNG train starting, a pipeline in service) as if it were tightness, so it must be re-based whenever a known step change lands. It is a two-sided estimate: a wrong weather input contaminates it in the same direction as a wrong balance.",
   "why_practitioners_use_it": "It is the cleanest single number a fundamentals desk carries, and it is the only one that separates 'the market is tight' from 'it was cold'. Directly relevant to this desk's rebuilt weather model: it is the residual AFTER the asymmetric weather slope, so it isolates the stack (renewables, coal, nuclear) that the 0629 miss was about.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Days of cover / storage normalised to demand rather than to the 5-year average",
   "what_it_measures": "Working gas in storage divided by expected consumption plus exports - how many days of demand the inventory covers. Corrects the fact that inventory levels are not comparable across years when demand has grown.",
   "source": "FREE. API publishes the chart and series (api.org energy-insights 'nat-gas-days-covered'); trivially reconstructed from EIA storage plus EIA consumption/exports.",
   "cost": "free",
   "horizon": "2-4wk to seasonal",
   "skill_limit": "API states the limitation explicitly: the metric compares storage to expected consumption and exports and 'does not account for daily production' - so it overstates fragility in a high-production year. It is a slow-moving structural measure with essentially no day-to-day content.",
   "why_practitioners_use_it": "This is the measured answer to the '5-year average is broken' complaint. Indexed to 2012, working storage capacity has risen about 7% through late 2025 while total US gas demand including exports averages more than 50% higher. So a given Bcf surplus to the 5-year average is materially less cushion today than the same number was a decade ago, and the raw surplus/deficit headline systematically misleads in the bullish direction.",
   "we_already_have_it": "no"
  },
  {
   "name": "Storage as a percent of DEMONSTRATED PEAK working capacity (the containment metric)",
   "what_it_measures": "Utilisation against the capacity that has actually been achieved in operation, not against engineering design capacity. The denominator for every containment argument.",
   "source": "FREE. EIA 'Underground Natural Gas Working Storage Capacity' report, annual, data as of November each year, published the following May (November 2025 data released 21 May 2026; next update May 2027). Publishes both working gas design capacity and demonstrated peak capacity, by region and state. Design capacity of the 384 active L48 fields was 4.666 Tcf in November 2023. In 2025 demonstrated peak rose 0.1% (6 Bcf) and design capacity rose 0.6% (26 Bcf).",
   "cost": "free",
   "horizon": "seasonal (August-November for the injection-season version)",
   "skill_limit": "Annual publication with a ~6-month lag, so it is a slow denominator against a weekly numerator. Design capacity is the wrong denominator - fields do not reach it - and using it makes containment look impossible. Demonstrated peak is itself path-dependent: it records what happened, so in a loose year it understates what could be held. Containment binds regionally (South Central and Midwest) long before it binds nationally, so the L48 ratio is the least useful cut. Genuinely binding containment is rare - a handful of shoulder seasons in twenty years.",
   "why_practitioners_use_it": "When it binds it is the dominant price driver in the shoulder and it is one of the very few fundamentals that produces a hard, non-linear price floor breach. NGI has documented forward curves dragged down by containment risk with the October/January spread carrying the concern. Deliverability physics reinforces it: EIA notes injection capacity varies INVERSELY with fullness, so the last 10% of the injection season is mechanically slower - the constraint tightens faster than the linear projection implies.",
   "we_already_have_it": "no"
  },
  {
   "name": "End-of-season carryout projection, and the calendar spread as the market's own carryout signal",
   "what_it_measures": "Projected 31 October (or 31 March) inventory from the current level plus the forward balance. The market's own version is the October/November spread (containment risk into the injection-season end) and the March/April 'widow maker' (winter carryout risk).",
   "source": "FREE for the market-implied version - this desk already has the full NYMEX term structure. Analyst carryout consensus is published free by Reuters and quoted in trade press (3.899 Tcf projected for 31 Oct 2024, a four-year high; 3.797 Tcf for 31 Oct 2025, a three-year low).",
   "cost": "free",
   "horizon": "1-4 months; the spread reacts within days",
   "skill_limit": "The projection is mechanical - level plus cumulative balance - so its error compounds at roughly the balance error per day times days remaining. A 0.5 Bcf/d balance error over 90 days is 45 Bcf of carryout error, which is inside the range analysts argue about. The market-implied version is contaminated by positioning: the March/April spread carries a persistent winter risk premium that is an option value, not a forecast, and it collapses on warm resets regardless of the underlying balance. Trade press documents both directions - the spread narrowing on healthy injections, and funds caught short when it flipped.",
   "why_practitioners_use_it": "It is the mechanism by which a weeks-ahead balance view becomes a curve-shape view rather than a flat-price view. For a desk scored on forward-curve error rather than daily hit rate, the carryout projection is the natural target variable.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Salt versus non-salt divergence in the South Central region",
   "what_it_measures": "Salt caverns cycle inventory several times a year; depleted reservoirs and aquifers cycle roughly once, seasonally, and aquifers need much more cushion gas. So the salt line responds to spot economics within days while the non-salt line follows the calendar.",
   "source": "FREE. EIA WNGSR breaks South Central into salt and non-salt weekly. Basics documented at eia.gov/naturalgas/storage/basics.",
   "cost": "free",
   "horizon": "0-2wk",
   "skill_limit": "Salt is a Gulf Coast / LNG / power-burn signal, NOT a national tightness proxy - the strong form of 'salt leads' is folklore. Salt working gas is a small fraction of L48 inventory, so a 9-16 Bcf salt move is inside weekly noise at the national level. Deliverability physics cuts both ways: EIA notes withdrawal rate varies DIRECTLY with fullness, so a nearly-empty salt field cannot deliver its headline rate, and a salt draw slowing may be a constraint rather than a demand signal. Salt is also increasingly a merchant trading asset (Williams took 92 Bcf of Louisiana/Mississippi salt; prices for salt storage have jumped), so salt moves increasingly reflect a trader's spread position rather than physical scarcity.",
   "why_practitioners_use_it": "It is the fastest-responding piece of the weekly print and the piece most exposed to LNG feedgas and Gulf Coast power burn - the two demand lines growing fastest. Traders on Enelyst dissect the salt/non-salt split within minutes of the print.",
   "we_already_have_it": "yes"
  },
  {
   "name": "Wellhead freeze-off risk index (basin minimum temperature versus threshold)",
   "what_it_measures": "Expected Bcf/d of production lost when field temperatures fall low enough that produced water and liquids freeze at the wellhead or in gathering.",
   "source": "FREE to build: this desk already has NWS station infrastructure and MOS forecast temps - the input is basin-level forecast MINIMUM temperature for the Permian, Haynesville, Appalachia, Anadarko/Mid-Con, Bakken and Rockies, not a population- or gas-weighted average. PAID reference: Wood Mackenzie publishes freeze-off loss estimates as a press item; S&P Global publishes Appalachia-specific freeze-off analyses; East Daley and RBN both cover it.",
   "cost": "free",
   "horizon": "1-10d (inherits weather-model skill)",
   "skill_limit": "Magnitudes are extreme and non-linear, which makes the index dangerous rather than merely imprecise: the January 2026 event produced an initial ~2 Bcf/d loss in the Bakken/Rockies/Mid-Con followed by an abrupt ~12 Bcf/d drop driven by the Permian and Gulf Coast, with total losses reported at 16-17 Bcf/d. Appalachia is comparatively resilient - a documented episode was only about 600 MMcf/d (~2%) off a 32.8 Bcf/d Marcellus/Utica base with temperatures in the mid-20s F. There is no published transfer function; the same basin at the same temperature loses different volumes depending on wind, duration, and how much winterisation has been retrofitted since the last event, so the relationship drifts year over year. Recovery is also asymmetric and slower than onset.",
   "why_practitioners_use_it": "It is the largest single-day supply shock in the market and it is the one case where a cold forecast is bullish on BOTH sides of the balance simultaneously. It is also the correction to a naive weather-to-demand model: a desk that maps cold only to demand will systematically under-forecast the magnitude of extreme cold days.",
   "we_already_have_it": "no"
  },
  {
   "name": "Coal-to-gas switching threshold / dispatch-cost stack",
   "what_it_measures": "The Henry Hub price at which gas displaces coal (or coal displaces gas) on dispatch cost, given delivered coal price and the two units' heat rates. Defines a soft price floor and a demand-elastic band.",
   "source": "FREE inputs: EIA-923 plant-level heat rates, EIA weekly/quarterly coal reports for delivered coal prices, EIA-930 for realised generation mix. Published practitioner numbers: gas becomes competitive with Powder River Basin coal below about $3.00/MMBtu, with roughly $2.50/MMBtu the level at which PRB plants across ERCOT and the Midwest flip on dispatch cost, and a parity calculation for PRB coal yielding a gas floor around $2.42/MMBtu. Illinois Basin coal at ~$56.75/ton is ~$2.40/MMBtu. Gas-to-coal switching the other way is generally not expected until Henry Hub is above ~$3/MMBtu.",
   "cost": "free",
   "horizon": "2-4wk to seasonal",
   "skill_limit": "The switching range has compressed badly as coal capacity retired - there is far less swing coal left to switch than the rule of thumb assumes, so the elasticity is smaller each year even though the threshold price is unchanged. Thresholds are regional (ERCOT, MISO, SERC differ) and the national number is close to meaningless. Coal stockpile levels and rail constraints override economics for weeks at a time. The published $2.40-3.00 band also assumes a coal price that itself moves with global gas via export arbitrage.",
   "why_practitioners_use_it": "It is the 'what coal can absorb' limb of the gas stack that this desk has already identified as missing - weather-driven load minus renewables minus what coal and nuclear can take. Without it, a correct load forecast still produces a wrong burn forecast, which is exactly the 0629 failure shape (CDD arrived as forecast, burn fell because wind rose).",
   "we_already_have_it": "no"
  },
  {
   "name": "Power burn cross-check: implied burn versus EIA-930 estimated burn",
   "what_it_measures": "Reconciliation of gas burn derived from pipeline power-plant delivery points against gas burn implied by EIA-930 generation times heat rate. The two disagree, and the disagreement is diagnostic.",
   "source": "FREE for one side (EIA-930, which this desk has, plus EIA-923 heat rates for the conversion); PAID for the other (Wood Mackenzie states it runs 'proprietary monitors at natural gas generation units', S&P Global and Criterion equivalent).",
   "cost": "mixed",
   "horizon": "0-3d",
   "skill_limit": "EIA-930 is itself estimated and is revised; its own gas-burn estimate is a modelled quantity, not a meter reading. Heat rates vary with load, ambient temperature and unit vintage, so a fixed heat rate introduces several percent of error at exactly the temperature extremes that matter. Behind-the-meter and industrial cogeneration is invisible to both.",
   "why_practitioners_use_it": "Power burn is roughly half of summer demand, and it is the demand line with the largest day-to-day variance. Two independent estimates of the same quantity is the only way to catch a wrong-but-well-formed input, which this desk has already learned is the failure mode a field-level check cannot catch.",
   "we_already_have_it": "partial"
  },
  {
   "name": "EIA-914 monthly dry production as the revision anchor for the daily nowcast",
   "what_it_measures": "The authoritative monthly production series against which every vendor's daily pipeline-scrape estimate is eventually benchmarked and revised.",
   "source": "FREE. EIA Natural Gas Monthly / Form EIA-914. Preliminary May 2026 dry production 110.3 Bcf/d, 3.5% above May 2025's 106.5 Bcf/d.",
   "cost": "free",
   "horizon": "backward-looking; ~2-month lag",
   "skill_limit": "Useless as a forecast input on its own - by the time it prints, the market has traded two months of the daily estimate. Its value is entirely as a bias-correction series: it tells you the sign and size of the nowcast's standing error. EIA-914 itself is revised.",
   "why_practitioners_use_it": "Because the daily production nowcast is a sample and every sample has a bias. Desks that do not run this correction inherit the vendor's revisions as unexplained balance misses.",
   "we_already_have_it": "no"
  },
  {
   "name": "Nomination-cycle revision delta (Timely -> Evening -> ID1/ID2/ID3)",
   "what_it_measures": "How much a given gas day's scheduled quantity changes as the day progresses through the five NAESB cycles. The DELTA is a same-day nowcast of demand surprise or supply disruption relative to what was planned the prior afternoon.",
   "source": "FREE at source on each pipeline's EBB (Northern Natural Gas exposes 7 cycles including Non-Grid A.M. and Final A.M.; PG&E documents the standard five: Timely, Evening, ID1, ID2, ID3). Timely deadline 13:00 CCT; ID1 is the first chance to change scheduled quantity after flow has begun; ID3 deadline 20:00 for gas flowing at 23:00.",
   "cost": "free",
   "horizon": "0-1d (intraday)",
   "skill_limit": "Purely same-day - it has no content beyond the gas day. It is also asymmetric: the lesser-of rule at interconnects means a cut can reflect the counterparty rather than the market. Coverage is only as good as the set of pipelines scraped, and a large intraday revision at one point can be a re-route rather than a net change. Most cycle-to-cycle deltas are administrative noise.",
   "why_practitioners_use_it": "It is the only genuinely intraday fundamental signal in this domain and it lands on a schedule that maps onto the trading day - which matters for a desk trading daily settlement contracts. Note the timing collision: the EIA storage print lands 10:30 ET Thursday, well after Timely and before ID1.",
   "we_already_have_it": "no"
  },
  {
   "name": "EIA WNGSR sample reselection and methodology-break flags",
   "what_it_measures": "Discontinuities introduced by EIA changing its own survey sample or its summary-statistic methodology - these produce level shifts that look like balance information and are not.",
   "source": "FREE. EIA posts sample-change notices (ir.eia.gov/ngs/samplechanges2024.html) and methodology-change notices. Documented example: the method for computing the five-year average and min/max range was modified in November 2018 and the 2018 historical summary statistics on weekly net changes were revised.",
   "cost": "free",
   "horizon": "event-driven; effects persist for a full 5-year-average cycle",
   "skill_limit": "Notices are sparse and unstructured; EIA does not publish a machine-readable break list. The Pacific region moved to full census in 2018, which changed its error properties without changing its label. EIA also proposed lowering the published revision threshold from 7 Bcf to 4 Bcf - so the same underlying revision behaviour produces a different published series before and after.",
   "why_practitioners_use_it": "Any model fitted across a sample-reselection or a five-year-average methodology change is fitting a definitional break. For a desk that keeps a versioned brain of learned plays, an unflagged break is a permanent false lesson.",
   "we_already_have_it": "no"
  },
  {
   "name": "The free weekly supply-demand balance table - and its January 2026 discontinuation",
   "what_it_measures": "Weekly-average dry production, LNG exports, Mexico exports, Canadian imports, power burn and res/comm consumption - the free, coarse version of the vendor daily balance.",
   "source": "FREE. Historically the EIA Natural Gas Weekly Update, sourced from LSEG Data (consumption), Bloomberg (shipping), Baker Hughes (rigs) and Form EIA-912 (storage). IMPORTANT: the Natural Gas Weekly Update's FINAL publication was for the week ending 21 January 2026; it was replaced on 29 January 2026 by the Weekly Natural Gas Storage Report Supplement, published Thursday afternoons.",
   "cost": "free",
   "horizon": "1-2wk",
   "skill_limit": "Weekly averages only, published Thursday afternoon - it is a confirmation series, not a decision series. The vendor attribution means it inherits LSEG's and Bloomberg's estimates rather than being an independent measurement. And it has just changed publication vehicle, so any pipeline pointed at the old NGWU URLs is now reading a dead or frozen page.",
   "why_practitioners_use_it": "It is the only free published balance and it anchors the free-tier view of the market. Flagging it here because this desk lists 'a weekly supply-demand balance' in its stack - if that was sourced from the NGWU it went stale after 21 January 2026 and would fail silently, present and numeric and in range, which is precisely the failure class this desk has catalogued eleven times.",
   "we_already_have_it": "yes"
  },
  {
   "name": "Storage deliverability ratchet (rate-versus-fullness constraint)",
   "what_it_measures": "Maximum daily withdrawal falls as inventory falls, and maximum daily injection falls as inventory rises. Both are physics, both are published qualitatively by EIA, and both bound what the balance can physically do.",
   "source": "FREE. EIA 'Basics of Underground Natural Gas Storage': deliverability 'varies directly with the total amount of natural gas in the reservoir - it is at its highest when the reservoir is most full and declines as working gas is withdrawn'; injection capacity 'varies inversely with the total amount of gas in storage'. Field-level design capacity and demonstrated peak from the annual capacity report.",
   "cost": "free",
   "horizon": "2-4wk to seasonal",
   "skill_limit": "EIA publishes the direction but not the curve - there is no public field-level deliverability-versus-inventory function, so the ratchet cannot be quantified from free data. Salt caverns have a much flatter curve than depleted reservoirs and aquifers (lower base gas, several cycles a year), so a national ratchet is wrong for the region that matters most. It only binds in the tails - at very low late-winter inventory or very high late-October inventory - and does nothing in between.",
   "why_practitioners_use_it": "It is the mechanism behind both the late-winter deliverability scare and the late-shoulder containment squeeze, and it explains why the last few weeks of a season behave non-linearly relative to a straight-line carryout projection.",
   "we_already_have_it": "no"
  }
 ],
 "skill_horizon_notes": "The honest structure of this domain is that the balance splits into two parts with completely different skill horizons, and conflating them is the main way desks fool themselves.\n\nWEATHER-DRIVEN PART (res/comm plus power burn; roughly half of summer demand is power burn). Its skill horizon is the weather forecast's, nothing more. Practitioner emphasis is uniformly 1-15 days, with the stated caveat that model divergence grows sharply in the day 6-15 window and the pattern is 'not yet settled' in the 8-15 range. Bespoke Weather Services, natgasweather and World Climate Service all package 15-day GWDD as the product boundary. Beyond ~15 days the degree-day input is not skillful and therefore neither is the weather half of the balance - anything a desk claims past that horizon is climatology plus positioning, not forecast.\n\nSTRUCTURAL PART (production trend, LNG train ramps, pipeline in-service dates, announced maintenance, Mexico/Canada seasonal shape). This is far more persistent and IS informative at 2-8 weeks - but mostly because it is a CALENDAR, not a forecast. Maintenance notices, planned service outages and commissioning schedules are known in advance by construction. This is the class of signal that actually carries information at the horizon this desk forecasts, and it is the class this desk has the least of.\n\nNOWCAST PART (pipeline nominations). 0-2 days, revises across five NAESB cycles within the gas day, and revises again over the following week as vendors true up. Real information, very short shelf life.\n\nSTORAGE LEVEL is mechanical: level equals prior level plus cumulative balance. So its skill horizon is exactly the balance's, and its error compounds roughly as (balance error in Bcf/d) x (days). A 0.5 Bcf/d standing balance error is 45 Bcf of end-of-season carryout error over 90 days - which is wider than the range analysts actually argue about, and is why carryout consensus is revised so heavily through a season.\n\nTHE EIA PRINT AS AN EVENT is much less informative than its reputation. EIA's own published sampling standard error is around 2.2 Bcf on the L48 net change (worked example gives a ~4 Bcf 90% margin of error), so a print that 'beats consensus' by 3-4 Bcf is inside the measurement noise of the print itself. Ederington/Linn/Zhang show professional accuracy improved materially after 2012, further shrinking the surprise. Prokopczuk, Wese Simen and Wichmann (Energy Journal 42(2), 2021) find more than 50% of the annual natural gas futures return is earned on storage announcement days, and that the announcement-day premium is NOT explained by the surprise or by controls - the intraday return splits roughly half pre-announcement and half post-announcement, and the pre-announcement half appears only on days when storage exceeds expectations. Their naive strategy (position before the print, close 30 minutes after) returned ~12% annually at a Sharpe of 1.76 after transaction and funding costs. Read plainly: the print DAY carries a return premium; the print SURPRISE does not explain it. Any play that maps surprise sign to direction is fitting the smaller and less reliable of the two effects.\n\nON PRICE PREDICTABILITY FROM FUNDAMENTALS. Baumeister, Huber, Lee and Ravazzolo (NBER w33156, Journal of Applied Econometrics 2026) find real-time MSPE reductions versus a random walk out to two years for Henry Hub, with a six-variable BVAR of supply-demand fundamentals among the best models and real-time model-selection pooling best overall; the random walk wins only very near term, EIA experts win at medium horizons, futures win at the longest. CRITICAL CAVEAT FOR THIS DESK: those results are for MONTHLY AVERAGE price levels. Monthly-horizon predictability of the level says almost nothing about the daily path over the next ten sessions. The operational translation is that the balance LEVEL sets a conditional drift over weeks, while what actually moves price day to day is the REVISION to the expected balance - principally the weather-model revision and the production/LNG nomination delta. Forecast the revision, not the level.",
 "debunked_or_folklore": [
  "THE RAW 5-YEAR-AVERAGE STORAGE COMPARISON. Measurably misleading, not merely crude. Indexed to 2012, working storage capacity has risen ~7% through late 2025 while total US gas demand including exports averages more than 50% higher - so days of cover has fallen steadily and a given Bcf surplus to the 5-year average is materially less cushion than the same number was a decade ago. The headline surplus/deficit is biased bullish-complacent by construction. Days of cover, or storage as a percent of demonstrated peak capacity, is the measured fix. EIA also changed the 5-year-average methodology in November 2018 and revised the 2018 statistics, so the series has a definitional break in it.",
  "'STORAGE SURPRISE DRIVES THE ANNOUNCEMENT-DAY MOVE.' Directly contradicted. Prokopczuk, Wese Simen and Wichmann (Energy Journal 42(2), 2021) find a significant announcement-day return premium that CANNOT be explained by the announcement surprise or by control variables, and that the pre-announcement half of the return appears only when storage exceeds expectations - which they note casts doubt on informed-trading explanations. The day matters; the surprise sign explains much less than practitioners assume.",
  "CROWD-SOURCED STORAGE FORECASTS ADDING INFORMATION. Measured and refuted. Fernandez-Perez, Garel and Indriawan (Energy Journal 41(5), 2020): crowdsourced forecasts are LESS accurate than professional forecasts on average, show greater divergence of opinion and lower incorporation of public information, and the crowd consensus does not influence the market's expectation beyond what is already in the professional consensus. Incremental usefulness described as 'very limited'.",
  "RIG COUNT AS A NEAR-TERM PRODUCTION PREDICTOR. Broken, with named mechanisms: much gas is associated production from oil-targeted rigs, drilling efficiency (wells per rig per month) has risen continuously, and the drilled-but-uncompleted backlog runs three to seven months at major plays and buffers rig-count changes entirely. Gas production rose for years while gas-directed rigs fell sharply. Even EIA's own Drilling Productivity Report only applies rigs with a two-month lag and then nets against legacy decline. At a 0-14 day horizon rig count carries nothing.",
  "'SALT LEADS THE MARKET.' True in the weak form, folklore in the strong form. Salt caverns genuinely cycle several times a year against roughly once for depleted reservoirs and aquifers, so salt responds to spot economics within days - but salt is a small share of L48 working gas and it is a Gulf Coast / LNG / power-burn signal, not a national tightness proxy. Salt is also now a merchant trading asset (rising storage rates, Williams' 92 Bcf Louisiana/Mississippi acquisition), so an increasing share of salt movement reflects a trader's spread position rather than physical scarcity. And because withdrawal rate varies directly with fullness, a slowing salt draw may be a deliverability constraint rather than a demand signal - the same observation supports opposite readings.",
  "STEO AS A SHORT-HORIZON PRICE SIGNAL. EIA expert forecasts have a measured edge at MEDIUM horizons (roughly 9-15 months in the Baumeister et al comparison), with futures better at the longest horizons and the random walk adequate very near term. STEO's forecast horizon is 12-23 months. It carries no usable information about the next one to ten trading sessions, and STEO vintages are best used as a slow structural prior, never as a directional input to a daily path.",
  "'INJECTION SEASON ENDS 31 OCTOBER.' A reporting convention, not physics. Storage regularly builds into November and draws in October. Any rule keyed to the calendar date rather than to realised weather and the deliverability ratchet is fitting an artifact.",
  "CONTAINMENT AS A RECURRING SEASONAL TRADE. Real but rare, and routinely over-claimed. It binds regionally (South Central and Midwest) well before nationally, it must be measured against demonstrated peak rather than design capacity or it looks impossible, and genuinely binding episodes number a handful in twenty years. The October/November and March/April spreads price the RISK continuously, so the spread being elevated is not evidence that containment will occur.",
  "THE 'HEADLINE MISS' ON RECLASSIFICATION WEEKS. Not a signal at all. Net change includes base-to-working-gas reclassifications; consensus forecasts the flow. On weeks with a reportable reclassification (4 Bcf or more) the two diverge by more than the entire survey range and the resulting 'surprise' is pure accounting. NGI documented exactly this producing a large headline miss. Use implied flow, and treat the reclassification flag as a scoring exclusion, not as evidence."
 ],
 "gaps_vs_our_stack": [
  "1. DAILY DRY-GAS PRODUCTION NOWCAST. The single biggest hole. Your stack has no daily supply series at all - every input listed is demand-side, positioning, price or weather. Production is roughly half the balance and it is the half that moves for non-weather reasons. Without it, a correct weather call still produces a wrong balance, and the error will look like an unexplained magnitude miss rather than a missing input. Free path exists (FERC Order 587 / NAESB WGQ informational postings, scraped directly; Northern Natural Gas is a working no-login example) but it is a real build: ~40-150 pipelines, each with its own format, and NAESB's own working group concluded scraping is fragile. Paid path is Wood Mackenzie / S&P Global Commodity Insights / Criterion / East Daley. Recommended sequencing: build the small targeted version first (see item 2), prove the plumbing, then widen.",
  "2. LNG FEEDGAS NOMINATIONS, DAILY BY TERMINAL. Highest value per unit of build effort, because it needs only ~10 pipeline EBBs rather than the full L48 set, and because you already have the downstream consumer half-built - `lng_feedgas_bcfd` is null and 278 days stale while the vessel line is live with zero readers. Feedgas moved from ~13 to ~15 Bcf/d on the Plaquemines ramp alone, a ~14 Bcf/week storage swing that is public and dated forward. The pipelines to scrape: Creole Trail / Transco 4A / NGPL (Sabine Pass), Corpus Christi Pipeline, Cameron Interstate, Gator Express (Plaquemines), TransCameron (Calcasieu Pass), Golden Pass, Dominion Cove Point, Elba Express.",
  "3. PIPELINE CRITICAL NOTICES AND THE PLANNED-MAINTENANCE CALENDAR. The highest-value item for your specific horizon question, because it is almost the only class of supply-demand information dated FORWARD by construction rather than nowcast or lagged. Effective dates run days to weeks ahead. Free at source on every EBB; paid aggregators are Enercast, PipeRiv (~200 operators, has an API) and Criterion. If the binding open question is how far out a useful forecast is possible, this is the answer for the structural half of the balance: as far out as the calendar says, because it is not a forecast.",
  "4. THE DEGREE-DAY-ADJUSTED BALANCE RESIDUAL. Costs nothing - you already hold every input (EIA implied flow plus your own NWS gas-weighted HDD/CDD). Regress weekly implied flow on GWHDD and GWCDD, read the residual as Bcf/d of structural tightness. This is the measure that carries information PAST the weather horizon because it describes the non-weather part. It is also the natural home for your rebuilt weather model's insight: it is the residual AFTER the asymmetric slope, so it isolates the stack (renewables, coal, nuclear) that the 0629 miss was about. One caveat that bears directly on your existing weights: summer demand is roughly half power burn, so the degree-day weighting must be SEASONAL and, for summer, weighted by where gas generation runs rather than where people live - GasAlpha's PWCDD reweights East North Central from ~20% to ~11% versus GWDD, with South Atlantic 24.0% and West South Central 17.7%. Your note that Ohio has no station at all, against PJM being the largest gas-burning BA, is the same defect from the other end.",
  "5. THE COAL LIMB OF THE GAS STACK. You have nuclear outages and EIA-930 wind, but nothing for coal - which is the third absorber in your own stated stack (weather load minus renewables minus what coal and nuclear can take). Free to build from EIA-923 heat rates plus EIA coal price series. Published thresholds: gas competitive with PRB coal below ~$3.00/MMBtu, PRB parity floor ~$2.42/MMBtu, Illinois Basin ~$2.40/MMBtu, meaningful gas-to-coal switching not expected until above ~$3/MMBtu. Honest caveat: the switchable coal fleet shrinks every year, so the elasticity is falling even though the threshold is stable.",
  "6. EIA IMPLIED FLOW VERSUS NET CHANGE, PLUS THE RECLASSIFICATION FLAG. Free, one field, and it prevents a whole class of false lesson. Consensus forecasts the flow; the tape prints the net change; on reclassification weeks (4 Bcf or more) they diverge by more than the entire survey range. Given your documented history of silently wrong inputs that are present, numeric, in range and self-consistent, this is a cheap reconciliation of exactly the kind that has worked for you before.",
  "7. THE EIA'S OWN PUBLISHED SAMPLING STANDARD ERROR. Free, weekly, in the 'Estimated measures of sampling variability' table beside the print, and essentially unused by anyone. It is a published noise floor: EIA's worked example is an SE of 2.2 Bcf on the L48 net change giving a ~4 Bcf 90% margin of error. Directly relevant to a system whose structural finding this session was that a forced number is indistinguishable from a confident one - here is a number that tells you when the surprise is inside the measurement error and the honest read is NO CALL.",
  "8. WELLHEAD FREEZE-OFF RISK INDEX. Free to build on infrastructure you already have (NWS stations plus MOS forecast temps), but keyed to basin-level forecast MINIMUM temperature rather than any weighted average. It is the largest single-day supply shock in the market - the January 2026 event ran ~2 Bcf/d initially then abruptly ~12 Bcf/d, total 16-17 Bcf/d - and it is the one case where a cold forecast is bullish on both sides of the balance at once. A weather model that maps cold only to demand will structurally under-forecast extreme cold days.",
  "9. WEEKLY BALANCE SOURCE STALENESS - CHECK THIS FIRST, IT IS A LIVE RISK NOT A BUILD. Your stack lists 'a weekly supply-demand balance'. If it is sourced from the EIA Natural Gas Weekly Update, that publication's FINAL edition was the week ending 21 January 2026; it was replaced 29 January 2026 by the Weekly Natural Gas Storage Report Supplement. A pipeline pointed at the old vehicle would go stale silently - present, numeric, in range, right owner - which is your documented hole signature. Cheapest possible check, highest possible embarrassment if skipped.",
  "10. MEXICO EXPORTS AND CANADIAN NET IMPORTS, DAILY. Together ~13-15 Bcf/d of swing that is invisible in every domestic consumption series and that decorrelates from your US degree-day view (Mexican summer heat, Canadian winter freeze-offs). Free but split: CER publishes daily Canadian throughput at no cost on the Open Government portal (DOI 10.35002/h579-7v23) with ~45-60 day filing latency - a calibration series, not a nowcast; the nowcast needs border-point scrapes. Lower priority than items 1-5 but genuinely missing.",
  "11. DAYS OF COVER AND STORAGE VERSUS DEMONSTRATED PEAK CAPACITY. Both free, both slow, both cheap. Days of cover from API or reconstructed; demonstrated peak from the annual EIA storage capacity report (November 2025 data released May 2026). These are the measured corrections to the 5-year-average comparison and the denominators for any containment argument. Low urgency, near-zero cost.",
  "12. CONSENSUS DISPERSION RATHER THAN JUST THE MEDIAN. You have 'storage consensus' - check whether you carry the RANGE. Ederington/Linn/Zhang find anti-herding intensity and forecast timing explain over 50% of cross-firm accuracy variation, so dispersion is partly genuine uncertainty and partly career-driven differentiation, and later-released forecasts are systematically better. That means the median of a survey is not an equal-quality aggregate, and the range is a better proxy for how unresolved the number actually was."
 ],
 "sources": [
  "https://www.woodmac.com/industry/commodity-trading-analytics/natural-gas-supply-demand/",
  "https://www.woodmac.com/industry/commodity-trading-analytics/natural-gas-real-time/",
  "https://www.woodmac.com/press-releases/historic-natural-gas-freeze-offs-as-arctic-weather-drives-production-losses-to-near-record-levels/",
  "https://eastdaley.com/commodities/natural-gas",
  "https://eastdaley.com/commodities/natural-gas/macro-supply-demand",
  "https://eastdaley.com/the-burner-tip/plaquemines-demand-passes-4-bcf-d-as-lng-project-ramp-continues",
  "https://www.criterionrsch.com/data/general-information",
  "https://developer.ice.com/fixed-income-data-services/catalog/criterion-research",
  "https://natgashub.com/pipes/",
  "https://natgashub.com/pricing/",
  "https://www.piperiv.com/ip/natural-gas",
  "https://www.enercast.com/pipeline/all/",
  "https://press.spglobal.com/2016-02-17-U-S-Natural-Gas-Production-Rose-Slightly-in-January-Platts-Bentek",
  "https://www.spglobal.com/energy/en/news-research/latest-news/natural-gas/020521-potential-wellhead-freeze-offs-could-further-reduce-appalachia-production",
  "https://naturalgasintel.com/news/revised-us-output-estimates-hurricane-erin-outlook-spur-natural-gas-futures-rebound/",
  "https://www.naturalgasintel.com/news/pipeline-data-signals-sharp-rebound-in-lng-feed-gas-demand/",
  "https://naturalgasintel.com/news/containment-risk-drags-down-natural-gas-forward-curves/",
  "https://naturalgasintel.com/news/october-natural-gas-futures-directionless-as-widow-maker-spread-sheds-winter-worries/",
  "https://naturalgasintel.com/news/eia-natural-gas-storage-print-comes-in-tight-amid-steep-draw-on-salts/",
  "https://naturalgasintel.com/news/us-natural-gas-salt-storage-projects-stage-comeback-as-lng-renewables-drive-demand/",
  "https://rbnenergy.com/daily-posts/analyst-insight/us-lng-feedgas-demand-riding-high-thanks-plaquemines-lng",
  "https://ir.eia.gov/ngs/methodology.html",
  "https://ir.eia.gov/ngs/notes.html",
  "https://ir.eia.gov/ngs/ngs.html",
  "https://ir.eia.gov/ngs/possiblesurveyerrors.html",
  "https://ir.eia.gov/ngs/samplechanges2024.html",
  "https://www.eia.gov/naturalgas/storage/basics/",
  "https://www.eia.gov/naturalgas/storagecapacity/",
  "https://www.eia.gov/naturalgas/storage/dashboard-content/notes_sources.php",
  "https://www.eia.gov/naturalgas/weekly/",
  "https://www.eia.gov/naturalgas/monthly/",
  "https://www.eia.gov/todayinenergy/detail.php?id=13551",
  "https://www.eia.gov/analysis/handbook/pdf/STEO_natural_gas_module.pdf",
  "https://www.api.org/energy-insights/charts-analysis/nat-gas-days-covered",
  "https://journals.sagepub.com/doi/10.5547/01956574.42.2.mpro",
  "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3575861",
  "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4645640",
  "https://journals.sagepub.com/doi/10.5547/01956574.41.5.afer",
  "https://www.nber.org/papers/w33156",
  "https://onlinelibrary.wiley.com/doi/10.1002/jae.70018",
  "https://www.sciencedirect.com/science/article/abs/pii/S0261560613001113",
  "https://www.ferc.gov/sites/default/files/2020-06/OrderNo.587-W.pdf",
  "https://www.naesb.org/pdf4/geh062923w2.pdf",
  "https://www.northernnaturalgas.com/infopostings/Capacity/Pages/OperationallyAvailable.aspx",
  "https://www.pge.com/pipeline/en/reference-library/facts-and-faqs/facts/nom-cycle.html",
  "https://www.cer-rec.gc.ca/en/data-analysis/facilities-we-regulate/look-pipeline-flow-capacity/natural-pipeline-flow-capacity.html",
  "https://open.canada.ca/data/en/dataset/dc343c43-a592-4a27-8ee7-c77df56afb34",
  "https://gasalpha.com/pwcdd",
  "https://www.bespokeweather.com/",
  "https://www.worldclimateservice.com/natural-gas-trading/",
  "https://natgasweather.com/clientservices-lng-daily-feedgas-estimate/",
  "https://www.powermag.com/coal-to-gas-switching-its-all-in-the-price/",
  "https://www.trioadvisory.com/resources/its-complicated-rig-count-impact-future-natural-gas-production",
  "https://www.rystadenergy.com/insights/us-lower-48-oil-and-gas-output-faces-major-disruption-due-to-freeze"
 ]
}
```

## LENS: Positioning, flow and market structure — Henry Hub natural gas (CFTC COT, dealer gamma, open interest, index/ETF roll flows, calendar spreads, term-structure regime, expiry mechanics)

```json
{
 "domain": "Positioning, flow and market structure — Henry Hub natural gas (CFTC COT, dealer gamma, open interest, index/ETF roll flows, calendar spreads, term-structure regime, expiry mechanics)",
 "signals": [
  {
   "name": "Weekly COT position CHANGE normalized by open interest (Q = Δnet-long / OI), split hedger vs managed money",
   "what_it_measures": "Who consumed and who provided liquidity in the week ending Tuesday. Speculators are momentum/impatient liquidity CONSUMERS; commercials are contrarian liquidity PROVIDERS who get paid a price concession.",
   "source": "CFTC Disaggregated COT (free, cftc.gov). Construct Q_t = (net_long_t - net_long_t-1) / OI_t-1 per Kang, Rouwenhorst & Tang, Journal of Finance 75(1) 2020, 377-417.",
   "cost": "free",
   "horizon": "1-20 business days after the Friday release; strongest days 1-10",
   "skill_limit": "Published decay is explicit and it dies inside the desk's own window: post-formation excess-return spread is 0.21% over days 1-4 (t=3.04), 0.30% over days 5-10 (t=3.62), and 0.15% over days 11-20 (t=1.23, INSIGNIFICANT). Cumulative 67bp over 20 days ~= 9%/yr. Critically this is a CROSS-SECTIONAL result across 26 commodities (NG is in-sample: mean excess return -11.3%/yr, vol 46.9%), NOT single-commodity market timing — the paper never claims a per-commodity timing result. Average |Q| is only ~3% of OI, so most weeks the signal is small.",
   "why_practitioners_use_it": "It is the only positioning construction with a published, horizon-resolved, sign-specific return result, and its horizon (1-2 weeks) is exactly a swing window. It reframes COT from 'sentiment extreme' to 'who paid whom for immediacy last week'.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Managed-money / non-commercial NET LENGTH LEVEL (and z-score of it)",
   "what_it_measures": "Stock of speculative positioning, usually rendered as a percentile or z-score and read as a contrarian extreme.",
   "source": "CFTC Disaggregated COT NG (free); vendor renderings at MacroMicro, YCharts, Barchart.",
   "cost": "free",
   "horizon": "claimed weeks-to-months; measured: essentially none at short horizon",
   "skill_limit": "This is the weakest item in the domain and the desk should demote it. Kang/Rouwenhorst/Tang: raw hedging pressure LEVEL has no short-horizon predictability, Fama-MacBeth slope t = -0.43. Sanders, Irwin & Merrin: bivariate Granger tests find very little evidence positions forecast returns. Gorton, Hayashi & Rouwenhorst (Review of Finance 2013) explicitly REJECT the Keynesian hedging-pressure hypothesis that positions are an important determinant of risk premiums. Only the 52-week SMOOTHED hedging pressure carries a significant slope, and that is a months-to-a-year premium, not a 2-week signal.",
   "why_practitioners_use_it": "Universally quoted in trade press and in risk meetings as a crowding/fuel gauge. Its honest use is as a conditioning variable for the SIZE of a squeeze if a catalyst arrives, not as a directional forecast.",
   "we_already_have_it": "yes"
  },
  {
   "name": "52-week smoothed hedging pressure (HP-bar = trailing MA of [hedger short - hedger long] / OI)",
   "what_it_measures": "The slow-moving component of commercial hedging demand, separated from the high-frequency liquidity-demand noise that dominates raw weekly HP.",
   "source": "CFTC COT, computed. Kang/Rouwenhorst/Tang Section 4; robust to HP-filter choice and MA window length.",
   "cost": "free",
   "horizon": "quarters to a year",
   "skill_limit": "By construction it has zero content at the desk's 0-14 day horizon — the smoothing is precisely what removes the short-term variation. Raw (unsmoothed) HP is insignificant (t = -0.43). Useful only as a slow regime prior sitting behind the fast signal.",
   "why_practitioners_use_it": "It is the surviving piece of the theory of normal backwardation after the short-horizon result is stripped out, and it disambiguates 'commercials are short because they are hedging output' from 'commercials are short because they absorbed a spec buying wave last Tuesday'.",
   "we_already_have_it": "partial"
  },
  {
   "name": "CFTC futures-and-options COMBINED (delta-adjusted futures-equivalent) vs FUTURES-ONLY divergence",
   "what_it_measures": "Options open interest converted to futures equivalents using exchange-supplied delta factors (long call/short put -> long equivalent; short call/long put -> short equivalent). The gap between the two series is options-expressed positioning.",
   "source": "CFTC COT Explanatory Notes (free). Both series published weekly for NG.",
   "cost": "free",
   "horizon": "same 1-2 week decay as the futures series",
   "skill_limit": "Delta factors are exchange-supplied and applied as of the report date only, so the series carries DELTA and nothing else — gamma, vega and skew positioning are invisible in it. A large producer collar program and a large outright short look identical in the combined number. Also a single entity cannot be both commercial and non-commercial in the same commodity, so a merchant with a spec book is forced entirely into one bucket.",
   "why_practitioners_use_it": "The futures-only/combined divergence is the cheapest read on whether a positioning move was expressed in options (structured, likely hedged, slow to unwind) or in outrights (fast, squeezable).",
   "we_already_have_it": "yes"
  },
  {
   "name": "Working's T speculative index (speculation in excess of what hedging requires)",
   "what_it_measures": "Whether speculative capital is adequate to absorb hedging demand. Values above 1 mean speculators hold more than needed to balance hedgers.",
   "source": "Computed from CFTC COT long/short by category (free). Sanders & Irwin methodology, applied to energy in the Speculation by Commodity Index Funds volume.",
   "cost": "free",
   "horizon": "regime-level, months",
   "skill_limit": "Explicitly NOT a return predictor and never claimed as one. Sanders/Irwin found no evidence excess speculation contributed to the 2007-08 energy spike or the 2014-16 decline; long-only index funds were found to IMPROVE adequacy by reducing short hedging pressure. Also documented: NG carries LESS speculative activity than other energy markets despite higher volatility — so absorption capacity is structurally thinner in gas than the WTI intuition suggests.",
   "why_practitioners_use_it": "It answers 'how much risk can this market absorb right now', which conditions expected magnitude of a shock — directly relevant to the desk's stated dominant residual (magnitude, not direction).",
   "we_already_have_it": "no"
  },
  {
   "name": "Open interest GROWTH as a return predictor (Hong & Yogo)",
   "what_it_measures": "Month-over-month change in total futures open interest; argued to be more informative than price when hedging demand meets limited risk-absorption capacity.",
   "source": "Hong & Yogo, Journal of Financial Economics 105(3) 2012, 473-490 (NBER w16712). OI free daily from CME.",
   "cost": "free",
   "horizon": "leads returns by a few months (roughly 1-6 months)",
   "skill_limit": "Monthly frequency and macro/pro-cyclical in nature — the mechanism is business-cycle risk absorption, not gas fundamentals. It survives controls for other known predictors but says nothing at a daily or weekly horizon. Do not resample it to days.",
   "why_practitioners_use_it": "It is one of very few positioning-family signals with a top-journal out-of-sample result across 30 commodity futures, and OI is free, daily and unrevised — unlike COT it has no reporting lag at all.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Front-to-second calendar spread / futures basis as an inventory-scarcity read",
   "what_it_measures": "Convenience yield net of carry. Theory of storage: convenience yield is a decreasing, NON-LINEAR function of inventory, so the basis is a compressed read of how tight storage actually is relative to demand.",
   "source": "Gorton, Hayashi & Rouwenhorst, Review of Finance 17(1) 2013, 35-105 (NBER w13249), 31 commodities + physical inventories 1969-2006. Spread data free from CME settlements.",
   "cost": "free",
   "horizon": "1 month and longer for the risk-premium result",
   "skill_limit": "Non-linearity is the trap: the spread is nearly flat in inventory when storage is comfortable and explodes only when it is tight, so a linear spread-to-storage regression will be well behaved for years and then fail exactly when it matters. Published gas-specific assessments conclude the theory of storage is strongly supported but 'cannot completely explain futures pricing for natural gas'. Joint spot/futures dynamics are regime-dependent: prices are MORE correlated in contango than in backwardation.",
   "why_practitioners_use_it": "Basis/carry is the most robust single predictor in the commodity cross-section and it is a real-time, revision-free proxy for the inventory state that EIA only publishes weekly with a lag.",
   "we_already_have_it": "yes"
  },
  {
   "name": "March/April 'widow maker' spread (NGH-NGJ)",
   "what_it_measures": "Market-priced probability of an end-of-winter storage squeeze — the last withdrawal month against the first injection month.",
   "source": "CME settlements (free); commentary from NGI, Reuters, Stanwich Energy, Trio Advisory.",
   "cost": "free",
   "horizon": "seasonal — informative Oct through Feb about late-Feb/March risk",
   "skill_limit": "BE BLUNT: no published threshold, no published backtest, no published failure mode. I read the practitioner pieces directly and they supply zero cents-per-MMBtu levels for 'wide' vs 'narrow', zero dated case studies with subsequent outcomes, and zero invalidating scenarios. It is presented as a 'confidence gauge'. It is also a bet on a SEASONAL STATE, not a next-2-week direction — using it as a daily directional input is a category error. Amaranth (2006) is the standing reminder that the spread's tail is fat in both directions.",
   "why_practitioners_use_it": "It is genuinely the market's own priced opinion on end-of-winter scarcity and it is the cleanest single number for that, which is why it is quoted constantly. Its value to this desk is as a slow conditioning variable on how violently a late-winter weather surprise will be paid.",
   "we_already_have_it": "partial"
  },
  {
   "name": "GSCI/BCOM monthly index roll (the 'Goldman roll', 5th-9th business day)",
   "what_it_measures": "Predictable, uninformed one-directional order flow: sell nearby, buy first deferred. Energy rolls EVERY month (most non-energy rolls every other month).",
   "source": "Irwin, Sanders & Yan, 'The Order Flow Cost of Index Rolling in Commodity Futures Markets' (2022), event study 1980-2019; S&P GSCI methodology (free).",
   "cost": "free",
   "horizon": "calendar-deterministic, known months ahead; impact window ~day -10 to +10",
   "skill_limit": "MEASURED DEAD. Spread impact was 30-40bp maximum in 1991-2011 with a full V-shaped reversal (1991-2003: -16.5bp pre-GR, -22.1bp GR, +46.3bp post-GR, net +7.6bp insignificant; 2004-2011: -32.1bp pre-GR, -5.6bp GR, +36.6bp post, net -1.1bp). Spread impacts DISAPPEAR in 2012-2019. Aggregate order-flow cost fell from $2.9bn/yr (2004-11) to $474mm/yr (2012-19), an >80% decline, attributed to sunshine trading plus electronic liquidity. Pre-financialization (1980-90) control period is flat, confirming the design. Only ~40-55% of index roll volume actually lands inside the GR window.",
   "why_practitioners_use_it": "It is still worth carrying as a LIQUIDITY-STATE flag (spread markets get deeper and more competitive on these days), but as a directional or spread alpha it is a signal the literature has already killed. Any desk still trading it is trading a 2004-2011 artifact.",
   "we_already_have_it": "yes"
  },
  {
   "name": "GSCI/BCOM ANNUAL reweighting (January, 5th-9th business day)",
   "what_it_measures": "One-off notional reallocation into/out of NG from target-weight changes, on top of the normal monthly roll.",
   "source": "S&P DJI 2026 CPW announcement (Nov 2025) and Bloomberg BCOM target weights (free PDFs). 2026 window Jan 8-15; BCOM natural gas weight 7.78% -> 7.20% for 2026. >$200bn combined AUM across the two indices.",
   "cost": "free",
   "horizon": "known ~2 months ahead (weights announced Oct/Nov), executes over 5 business days in January",
   "skill_limit": "No published measured price impact exists for the annual reweight specifically, and the same sunshine-trading logic that killed the monthly roll applies with even more force because the weights are announced two months early. Practitioners are openly split — the counter-argument is that it only matters where trade-at-settlement liquidity is thin. Treat the flow estimate (AUM x Δweight) as an order-of-magnitude prior, not a forecast.",
   "why_practitioners_use_it": "The direction and approximate size are knowable in November for a January event, which is rare. For a desk that runs January groups it is a cheap calendar overlay.",
   "we_already_have_it": "partial"
  },
  {
   "name": "UNG four-day roll (pre-announced calendar)",
   "what_it_measures": "Retail-vehicle roll flow out of the front and into the second month, at a fully published weight schedule.",
   "source": "USCF prospectus / 10-K (free, SEC EDGAR); roll dates posted in advance on uscfinvestments.com. Benchmark changes starting two weeks before near-month expiry; day 1 = 75/25 near/next, day 2 = 50/50, day 3 = 25/75, day 4 = 100% next.",
   "cost": "free",
   "horizon": "0-14 days ahead — the roll begins exactly two weeks before front expiry, which sits inside the desk's window",
   "skill_limit": "Bessembinder et al. (2016) studied the analogous USO crude roll and found the OPPOSITE of predatory front-running: narrower bid-ask spreads, greater limit-order-book depth, more distinct accounts providing liquidity, and improved resiliency on roll dates. So this is a LIQUIDITY-REGIME variable, not an alpha — expect the tape to be deeper and more mean-reverting on these days, not to be trending. UNG's share of NG open interest is small in normal conditions; it matters only when AUM has spiked.",
   "why_practitioners_use_it": "It is a pre-announced, dated, free flow calendar landing precisely in a days-to-two-weeks window. Even used only as a day-class tag ('UNG roll day'), it partitions the tape into a known microstructure regime.",
   "we_already_have_it": "no"
  },
  {
   "name": "Leveraged/inverse ETF close rebalance (BOIL 2x, KOLD -2x on Bloomberg Natural Gas Subindex)",
   "what_it_measures": "Mechanically forced, same-direction-as-the-day's-move futures trading concentrated at/near the settlement, sized by AUM and the size of the day's return.",
   "source": "ProShares daily AUM/NAV and shares outstanding (free); Cheng & Madhavan, 'The Dynamics of Leveraged and Inverse Exchange-Traded Funds', Journal of Investment Management (2009) for the rebalance identity.",
   "cost": "free",
   "horizon": "same-day close (0-1 day); the imbalance is knowable intraday once the day's return is known",
   "skill_limit": "Cheng & Madhavan establish that daily re-leveraging is same-direction as the underlying return and exacerbates volatility toward the close, but I found NO natural-gas-specific published measurement of the effect size. The flow is quadratic-ish in the day's move and linear in AUM, so it is negligible on quiet days and only becomes material after large moves or after an AUM spike. Must be measured on the desk's own tape before it is trusted.",
   "why_practitioners_use_it": "It is a same-direction, deterministic close-of-day imbalance in a market where the desk's Kalshi daily contracts settle off a specific closing print. That combination — forced flow, known sign, known timing, settlement-relevant — is rare and it is the single most testable item here on data the desk already owns.",
   "we_already_have_it": "no"
  },
  {
   "name": "Trade-at-Settlement (TAS) volume in NG, product NGT",
   "what_it_measures": "Volume executed as a spread to the daily settlement price. TAS is the instrument index replicators and settlement-benchmarked accounts use, so TAS volume is a direct observable of passive/benchmark flow rather than opinionated flow.",
   "source": "CME Globex; NG TAS spreads (NGT) available in any spread combination for the first 12 consecutive monthly contracts. Already inside the desk's NYMEX tick/MBO tape if the NGT instruments are separated.",
   "cost": "free",
   "horizon": "same-day; and it flags the days when settlement-seeking size is present",
   "skill_limit": "No published study evaluates TAS volume as a return or volatility predictor — this is an inference from the instrument's purpose, not a measured result. It identifies WHO is trading, never direction. Also NG settlement is a VWAP of Globex outrights 14:28:00-14:30:00 ET, so TAS participants are betting on a 2-minute window, and the desk's Kalshi settlement clock (17:00 ET) is a different clock entirely.",
   "why_practitioners_use_it": "It separates informed from benchmark flow inside a tape that otherwise pools them, which is exactly the distinction the Kang/Rouwenhorst/Tang liquidity-provision result turns on — and the desk can build it from data it has already paid for.",
   "we_already_have_it": "unclear"
  },
  {
   "name": "Dealer gamma exposure (GEX) built from the NG options OI strike ladder",
   "what_it_measures": "Estimated dollar delta that option market makers must trade per 1% move, computed as gamma x modeled dealer position x contract multiplier x F^2 x 0.01, summed over strikes and expiries; Black-76 for futures options.",
   "source": "Buildable from the desk's existing NG options settle-IV surface + OI strike ladder. Vendor analogues (SpotGamma, GEXStream, MenthorQ) are equity-index only.",
   "cost": "free",
   "horizon": "0-2 days at most",
   "skill_limit": "This is the item to be most sceptical of. There is NO published gas-specific gamma-exposure work at all — every methodology source I found is SPX/SPY/NQ. The one honest pre-registered replication (1,972 SPY days, 2018-2026) reports raw GEX to next-day realized vol Spearman rho = -0.36 (p = 4.6e-60) and a top-minus-bottom quintile gap of 10.63 vol points (t = -13.00), but after a VIX control rho falls to -0.14 and after VIX + ATM IV controls to -0.03 (p = 0.18) with the quintile gap at 0.99 points (p = 0.25). The author's conclusion: 'GEX is not fake. The raw effect is real. The incremental information after VIX and ATM IV is the part that fails' — a regime descriptor, not a standalone forecast. Additionally the dealer-sign assumption (customers buy calls, dealers are short) is an equity-market convention that is probably WRONG in gas, where producers are systematic call sellers / put buyers and utilities are call buyers, so the sign of dealer gamma is genuinely unknown without EFP/OTC visibility.",
   "why_practitioners_use_it": "Widely quoted; useful strictly as a redundancy check on the desk's existing vol-regime module. If GEX is collinear with the desk's own realized-vol regime measure the way it is with VIX in SPY, it adds nothing and should not be built.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Gamma-hedging-driven intraday momentum (rest-of-day return -> last-30-minute return)",
   "what_it_measures": "Short-gamma hedgers must trade in the direction of the move, producing predictable close-window continuation.",
   "source": "Baltussen, Da, Lammers & Martens, 'Hedging demand and market intraday momentum', Journal of Financial Economics (2021). 60+ futures 1974-2020, including 21 commodity futures, 17 equity index, 16 bond, 8 FX.",
   "cost": "free",
   "horizon": "intraday only — the final 30 minutes, predicted by the open-to-T-30 return",
   "skill_limit": "Two hard limits. First it is purely intraday: the paper finds the effect REVERTS over the next days, so it is not a next-session directional input and stacking it into a multi-day path would double-count then invert. Second, the headline is 'strong everywhere' across the pooled 60+ futures; the commodity-specific and gas-specific decomposition is not something I could verify, so treat the NG magnitude as unmeasured until the desk runs it on its own tape.",
   "why_practitioners_use_it": "It is the best-evidenced gamma-related effect in the literature and it is measurable directly from tape the desk already owns, with no options data needed. For a desk whose Kalshi contracts settle on a closing print, a published close-window continuation effect is directly on-target.",
   "we_already_have_it": "partial"
  },
  {
   "name": "NG futures/options expiry and settlement calendar as a forced-flow day-class",
   "what_it_measures": "Which specific sessions carry mechanically forced, non-discretionary trading.",
   "source": "CME rulebook Ch.220 and contract specs (free). Futures terminate 3 business days before the first calendar day of the delivery month. Daily settlement = VWAP of outright Globex trades 14:28:00-14:30:00 ET. Options: LN American-style, LNE European-style, both expiring ONE business day before the futures termination; in-the-money European options auto-exercise. Weekly NG options also listed.",
   "cost": "free",
   "horizon": "calendar — known a year ahead",
   "skill_limit": "It is a calendar, not a forecast: it tells you which days carry forced flow, never the direction of that flow. Two specific traps for this desk. (a) The NYMEX Last Day Settlement print is the index price for a large volume of physical contracts, so participants are price-INSENSITIVE that day — an expiry-day move is not information about the next day. (b) The desk's Kalshi settlement clock (17:00 ET per-contract close) is NOT the NYMEX 14:28-14:30 VWAP clock; a signal calibrated on one will mis-time the other. NOTE: I could not load the CME weekly-options FAQ (repeated timeouts), so the weekly product codes and listing count are UNVERIFIED and should be confirmed from CME before use.",
   "why_practitioners_use_it": "Expiry-week behaviour is the most reliably distinct day-class in gas, and the options-expire-one-day-before-futures rule creates a specific two-day sequence (option pin pressure, then futures LDS) that recurs every month.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Contango/backwardation regime as a conditioning state",
   "what_it_measures": "Whether the curve is in carry or scarcity mode, used to switch the behavioural model rather than to predict level.",
   "source": "CME settlements (free); European NG theory-of-storage assessments in Journal of Commodity Markets / Energy Economics.",
   "cost": "free",
   "horizon": "regime persistence, weeks to months",
   "skill_limit": "Descriptive, not predictive. The measurable content is that joint spot/futures dynamics are regime-dependent — spot and futures are MORE correlated in contango than in backwardation. That is a correlation-structure statement useful for path construction and for deciding whether the front leg can be used as a proxy for the deferred, not a directional signal.",
   "why_practitioners_use_it": "Regime-switching the model beats fitting one model across both regimes, and this is the cheapest regime label available.",
   "we_already_have_it": "yes"
  }
 ],
 "skill_horizon_notes": "The binding answer is uncomfortable and it comes from the best real-time study of gas price forecastability: Baumeister & Kilian, \"Forecasting Natural Gas Prices in Real Time\" (NBER w33156, Journal of Applied Econometrics 2026), a fully real-time-vintage horserace on Henry Hub, evaluation from Feb 1997, horizons h = 1, 3, 6, 9, 12, 15, 18, 21, 24 MONTHS.\n\nAt h = 1 month the winner is simply the most recent daily closing price (33% MSPE reduction vs a monthly-average no-change benchmark). Every fundamentals model loses there: the unrestricted VAR(12) has MSPE ratios above 1 at ALL horizons, and the Bayesian VAR beats the random walk at all horizons EXCEPT h = 1. EIA expert forecasts LOSE badly to no-change at h = 1 and h = 3 and only start winning at h = 9 (35% gain) and h = 12 (38%). Futures-based forecasts only overtake at h = 3-6. The end-of-month price's informational advantage \"quickly dissipates\" — only 2% at h = 3 and gone by h = 6.\n\nTwo consequences for this desk. (1) One month is the SHORTEST horizon anyone has published on, and at that horizon nothing beats today's price. There is no published evidence that any fundamental or positioning variable carries information about the LEVEL of gas at 0-14 days. The desk's edge therefore cannot be level drift; it has to be conditional path shape, day-class and distribution width — which is in fact what the desk's method already does. This is worth saying out loud because it means a forecast that is \"right on level\" at 3 days is not evidence of skill, and a forward-curve drift metric will be dominated by the random-walk component.\n\n(2) The one positioning result that genuinely lives inside the desk's window is the post-COT-release drift, and its published decay brackets the desk's far edge almost exactly: significant at days 1-4 (t=3.04) and days 5-10 (t=3.62), INSIGNIFICANT by days 11-20 (t=1.23). So positioning-derived information decays to noise at roughly two weeks — the outer limit of the desk's stated range is also the outer limit of the measured signal.\n\nFlow/calendar signals (index rolls, UNG roll, annual reweight, expiry) are different in kind: they are deterministic, so their \"horizon\" is arbitrarily long, but the price impact literature says the exploitable part is gone (Irwin/Sanders/Yan for the monthly roll post-2012; Bessembinder et al. for ETF rolls). Their surviving value is as day-class labels and liquidity-regime flags, not as alpha. Gamma-related signals are 0-1 day and explicitly REVERT afterwards.",
 "debunked_or_folklore": [
  "THE GOLDMAN ROLL TRADE IS MEASURED DEAD. Irwin, Sanders & Yan (2022) event study, 1980-2019: spread impact peaked at 30-40bp in 1991-2011 with full V-shaped reversal, and impacts DISAPPEAR in 2012-2019. Aggregate order-flow cost fell from $2.9bn/yr (2004-11) to $474mm/yr (2012-19), >80% decline, attributed to sunshine trading plus electronic liquidity. Mou (2011)'s Sharpe-4.39 front-running result is a 2000-2010 artifact and its sample ends before the effect died. Anyone quoting Mou today is quoting a dead regime.",
  "PREDATORY FRONT-RUNNING OF ETF/INDEX ROLLS — the evidence runs the OTHER WAY. Bessembinder et al. (2016) on USO crude rolls found narrower bid-ask spreads, greater limit-order-book depth, more distinct accounts providing liquidity, and improved resiliency ON roll dates. Sunshine trading, not predation. Expect roll days to be MORE liquid and more mean-reverting, not trendier.",
  "COT POSITION LEVELS AS A RETURN FORECASTER. Three independent rejections: Kang/Rouwenhorst/Tang find raw hedging pressure has a Fama-MacBeth slope of t = -0.43 (nil); Sanders, Irwin & Merrin's Granger causality tests find very little evidence positions forecast returns; and Gorton, Hayashi & Rouwenhorst (Review of Finance 2013) explicitly REJECT the hedging-pressure hypothesis that positions are an important determinant of risk premiums, finding instead that positions are correlated with prices and inventory signals — i.e. positions follow, they do not lead.",
  "THE 'MANAGED MONEY Z-SCORE ABOVE +2 IS BEARISH / BELOW -2 IS BULLISH' RULE IN NATURAL GAS. I searched specifically for measured frequency-and-magnitude statistics on NG managed-money extremes and found NONE — only vendor charts, economic-calendar pages and post-hoc commentary. The rule circulates entirely on trade-press repetition. If the desk wants it, it has to measure it itself on its own COT history; there is no published number to inherit.",
  "THE PRICE / VOLUME / OPEN-INTEREST TABLE ('rising OI with rising price = new longs = bullish continuation; falling OI with rising price = short covering = weak rally'). This is the oldest piece of futures folklore and it does not survive testing: the research finds little evidence that trading activity leads commodity prices, and strong evidence that PRICES LEAD hedging and speculation activity. Trader-wise decompositions into expected and unexpected components are inconclusive. Hong & Yogo's OI result is real but it is a MONTHLY, macro/pro-cyclical effect — it is not a licence for the daily version of the table.",
  "DEALER GAMMA (GEX) AS A STANDALONE FORECAST. The most honest available replication (1,972 SPY days 2018-2026, pre-registered) shows raw GEX to next-day realized vol at rho = -0.36 (p = 4.6e-60), but -0.14 after a VIX control and -0.03 (p = 0.18) after VIX + ATM IV — statistically indistinguishable from noise. Quintile spread collapses from 10.63 vol points to 0.99 (p = 0.25). GEX is largely a repackaging of implied vol. Worse for gas: there is NO published gas-specific gamma work at all, and the standard 'dealers are short gamma' sign convention is imported from equities, where customers buy calls — in gas, producers systematically SELL calls and buy puts, so the dealer sign is genuinely unknown without OTC visibility. Building NG GEX without first testing it against the desk's existing vol-regime module risks manufacturing a mechanism, which is a failure mode this desk has already recorded.",
  "THE WIDOW-MAKER AS A FORECAST. The spread is a real, economically meaningful state variable, but the practitioner literature supplies zero numeric thresholds for wide vs narrow, zero dated case studies with subsequent outcomes, and — the tell — zero discussion of failure modes or regimes where it stops working. It is written up as a 'confidence gauge' with no invalidating scenario, which is the signature of an unmeasured belief. It is also a bet on END-OF-WINTER state, so using it as a next-2-week directional input is a category error.",
  "'EXCESS SPECULATION DRIVES GAS PRICE SPIKES.' Tested with Working's T on CFTC data and rejected for both the 2007-08 energy spike and the 2014-16 decline. Long-only index funds were found to IMPROVE the adequacy of speculation by reducing short hedging pressure. Separately, futures returns correlate with open interest but NOT with net financial flows.",
  "'FUTURES PRICES FORECAST SPOT.' At the horizons this desk cares about, no. Baumeister & Kilian: futures-based forecasts LOSE to the last daily price at h = 1 month and only start winning at h = 3-6. Almost all models built on futures prices or the spot-futures spread fail to beat a random walk at short horizons."
 ],
 "gaps_vs_our_stack": [
  "1. RECONSTRUCT COT AS A CHANGE, NOT A LEVEL — highest expected value by a distance. Build Q = Δnet-long / prior-week OI separately for Managed Money and for Producer/Merchant, and apply the published decay structure as three distinct windows (days 1-4, days 5-10, days 11-20-and-dead) rather than one undifferentiated 'positioning' input. The desk currently ingests COT levels and options-implied positioning; the level is the construction that three independent studies reject, and the change is the one with a Journal of Finance horizon-resolved result landing squarely in the desk's window. Cost: zero, the data is already in hand. Caveat to carry: the published result is cross-sectional across 26 commodities, so the desk must forward-test the single-commodity version rather than inherit the 67bp.",
  "2. LEVERAGED-ETF CLOSE REBALANCE (BOIL/KOLD) — the most testable gap on data already owned. The rebalance is same-direction as the day's move, forced, and lands at the close; the desk's Kalshi daily contracts settle on a closing print. Compute the implied close imbalance daily from published shares outstanding and NAV, then measure it against the desk's own MBO tape in the final 30 minutes. No NG-specific published measurement exists, so this is genuine unexplored ground rather than a re-implementation — and the desk's per-cell discipline is exactly the right tool because the flow is negligible on quiet days and only material after large moves.",
  "3. SEPARATE TAS (NGT) VOLUME OUT OF THE EXISTING TAPE. The desk already owns the full NYMEX tick/MBO tape but almost certainly pools TAS instruments with outrights. TAS is where index replicators and settlement-benchmarked accounts trade, so isolating NGT gives a direct observable of passive vs opinionated flow — the exact distinction the liquidity-provision result turns on. Zero new data cost; it is a parsing change. Note the clock mismatch: NG settles on a 14:28-14:30 ET VWAP while the desk's Kalshi contracts settle at 17:00 ET.",
  "4. UNG'S PRE-ANNOUNCED FOUR-DAY ROLL AS A DAY-CLASS TAG. The roll begins exactly two weeks before front expiry with a published 75/50/25 weight ramp and dates posted in advance. It is free, dated, and lands inside the desk's 0-14 day window. Per Bessembinder, expect it to mark a DEEPER, more resilient, more mean-reverting tape rather than a trending one — which is a magnitude-damping condition, and magnitude is the desk's stated dominant residual. Cheap to add as a calendar flag.",
  "5. NEAR-DATED / WEEKLY NG OPTIONS GAMMA CONCENTRATION. The desk has the settle-IV surface and OI strike ladder but the monthly-expiry framing misses the weekly series, where gamma is concentrated at Friday expiries — i.e. at the exact frequency of the desk's forecasts. Worth building only as a strike-magnet and pin-risk overlay near expiry, NOT as a directional GEX number, given the replication evidence. FLAG: I could not load the CME weekly-options FAQ (repeated timeouts/connection resets), so product codes and listing counts are unverified — confirm from CME before building.",
  "6. SPLIT HEDGING PRESSURE INTO FAST AND SLOW COMPONENTS. Compute the 52-week smoothed HP as a separate slow regime prior and use the residual (raw minus smoothed) as the fast liquidity-demand term. This is the paper's own decomposition and it prevents the desk from reading a one-week liquidity absorption as a change in producer hedging intent. Zero data cost.",
  "7. REST-OF-DAY -> LAST-30-MINUTE MOMENTUM MEASURE ON THE OWN TAPE. Baltussen et al. is the best-evidenced gamma-adjacent effect in the literature, needs no options data, and speaks directly to close-settled contracts. Must be scoped as intraday-only: the paper is explicit that it REVERTS over subsequent days, so it must never be allowed to feed a multi-day path.",
  "8. WORKING'S T SPECULATIVE INDEX as an absorption-capacity conditioner. Free from data already held. Not a return predictor and must not be used as one, but it answers 'how much can this market absorb right now', and the finding that NG carries LESS speculative activity than other energy markets despite higher volatility is a structural fact the desk's magnitude model should know.",
  "9. HONG-YOGO OPEN-INTEREST GROWTH as a monthly slow prior. Free, daily, unrevised, and with no reporting lag at all — a genuine advantage over COT. Low priority because the horizon (leads by a few months) sits outside the desk's window, but it is nearly free to carry.",
  "10. GSCI/BCOM ANNUAL REWEIGHT as a January calendar overlay. Weights are announced in Oct/Nov for a Jan 8-15 execution, so direction and rough size are knowable two months ahead (BCOM NG 7.78% -> 7.20% for 2026). Lowest expected value on this list: no measured impact exists, and the two-month announcement lead is precisely the condition under which the monthly roll's impact was arbitraged to zero."
 ],
 "sources": [
  "Irwin, Sanders & Yan (2022), 'The Order Flow Cost of Index Rolling in Commodity Futures Markets' — https://scotthirwin.com/wp-content/uploads/2022/02/Irwin_Sanders_Yan_AEPP_All.pdf (full text extracted; roll impact 30-40bp 1991-2011, disappears 2012-2019, $2.9bn/yr -> $474mm/yr)",
  "Kang, Rouwenhorst & Tang (2020), 'A Tale of Two Premiums: The Role of Hedgers and Speculators in Commodity Futures Markets', Journal of Finance 75(1) 377-417 — https://www7.uc.cl/economia/finance_uc/docs/conferences/11th/Rouwenhorst-Tale%20of%20two%20premiums.pdf (full text extracted; day 1-4 / 5-10 / 11-20 decay, raw HP t=-0.43, NG in sample at -11.3%/yr and 46.9% vol)",
  "Baumeister & Kilian, 'Forecasting Natural Gas Prices in Real Time', NBER Working Paper 33156 / Journal of Applied Econometrics 2026 — https://www.nber.org/system/files/working_papers/w33156/w33156.pdf (full text extracted; h=1 month MSPE results, VAR/BVAR/futures/EIA-expert horserace)",
  "Mou (2011), 'Limits to Arbitrage and Commodity Index Investment: Front-Running the Goldman Roll', SSRN 1716841 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1716841 (superseded by Irwin/Sanders/Yan; sample ends 2010)",
  "Bessembinder et al. (2016), 'Predatory or Sunshine Trading? Evidence from Crude Oil ETF Rolls' — https://www.cftc.gov/sites/default/files/idc/groups/public/@economicanalysis/documents/file/oce_predatorysunshine0314.pdf",
  "Gorton, Hayashi & Rouwenhorst (2013), 'The Fundamentals of Commodity Futures Returns', Review of Finance 17(1) / NBER w13249 — https://www.nber.org/system/files/working_papers/w13249/w13249.pdf",
  "Hong & Yogo (2012), 'What Does Futures Market Interest Tell Us about the Macroeconomy and Asset Prices?', JFE 105(3) 473-490 / NBER w16712 — https://www.nber.org/papers/w16712",
  "Baltussen, Da, Lammers & Martens (2021), 'Hedging demand and market intraday momentum', Journal of Financial Economics — https://www3.nd.edu/~zda/intramom.pdf",
  "Cheng & Madhavan (2009), 'The Dynamics of Leveraged and Inverse Exchange-Traded Funds', SSRN 1539120 — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1539120",
  "CFTC Commitments of Traders Explanatory Notes (delta-adjusted futures-equivalent methodology, classification rules) — https://www.cftc.gov/MarketReports/CommitmentsofTraders/ExplanatoryNotes/index.htm",
  "CFTC Commitments of Traders, Natural Gas Disaggregated/Legacy reports — https://www.cftc.gov/dea/futures/nat_gas_lf.htm",
  "FlashAlpha, 'GEX Backtest: 8 Years of SPY Show Gamma Exposure Mostly Tracks VIX' — https://flashalpha.com/articles/gex-dex-vex-chex-8-year-backtest-spy-vix-control (1,972 days; rho -0.36 raw, -0.03 after VIX+ATM IV)",
  "SpotGamma, Gamma Exposure (GEX) methodology — https://spotgamma.com/gamma-exposure-gex/",
  "United States Natural Gas Fund LP prospectus / 10-K, four-day roll methodology — https://www.sec.gov/Archives/edgar/data/0001376227/000207187626000124/i26207_ung-424b3.htm",
  "CME Group, NYMEX Rulebook Chapter 220 Henry Hub Natural Gas Futures — https://www.cmegroup.com/rulebook/NYMEX/2/220.pdf",
  "CME Group, Natural Gas daily settlement procedure (14:28-14:30 ET VWAP) — https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457415061/Natural+Gas",
  "CME Group, Henry Hub Natural Gas Options contract specs (LN American / LNE European, expire one business day before futures termination) — https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.contractSpecs.options.html",
  "CME Group, Trading at Settlement (TAS) — https://www.cmegroup.com/trading/trading-at-settlement.html",
  "S&P Dow Jones Indices, S&P GSCI Methodology and 2026 CPW announcement — https://www.spglobal.com/spdji/en/documents/indexnews/announcements/20251106-1480756/1480756_spgsci2026cpwindexannouncement.pdf",
  "Bloomberg Commodity Index 2026 Target Weights (NG 7.78% -> 7.20%) — https://www.prnewswire.com/news-releases/bloomberg-commodity-index-2026-target-weights-announced-302600263.html",
  "Peak Trading Research, 'Commodity Index Rebalance Explained' (Jan 5th-9th business day window, >$200bn AUM) — https://david-whitcomb-ls5p.squarespace.com/trader-education-blog/commodity-index-rebalance",
  "Stanwich Energy, 'What the Widowmaker Spread Tells Us About Late Winter Risk' — https://stanwichenergy.com/insights/what-the-widowmaker-spread-tells-us-about-late-winter-risk (read in full; contains no thresholds, no case studies, no failure modes)",
  "Trio Advisory, 'Natural gas NYMEX last day settlement' — https://www.trioadvisory.com/resources/natural-gas-nymex-last-day-settlement-always-much-ado-about-something",
  "Natural Gas Intelligence, widow-maker spread coverage — https://naturalgasintel.com/news/natural-gas-widow-maker-spread-flashes-calm-as-winter-supply-worries-ease/",
  "Irwin (ed.), 'Speculation by Commodity Index Funds' (Working's T, adequacy of speculation, 2007-08 and 2014-16 rejections) — https://www.cabidigitallibrary.org/doi/10.1079/9781800622104.0011",
  "Journal of Commodity Markets, theory-of-storage assessment of natural gas — https://www.sciencedirect.com/science/article/pii/S2405851322000678"
 ]
}
```

## LENS: Power burn, fuel switching and the generation stack (US natural gas, summer-weighted)

```json
{
 "domain": "Power burn, fuel switching and the generation stack (US natural gas, summer-weighted)",
 "signals": [
  {
   "name": "ISO day-ahead / 7-day LOAD forecasts (MTLF)",
   "what_it_measures": "The system operator's own hourly load forecast for the next 1-7 days - the forward-looking demand side that EIA-930 only reports after the fact. SPP publishes system-wide MTLF vs actual +7 days hourly; ERCOT publishes Seven-Day Load Forecast by Weather Zone (NP3-561-CD) and by Model and Weather Zone (NP3-565-CD, current day + 7); PJM Seven-Day Load Forecast updated twice per hour; MISO load forecast updated every 15 min, hourly granularity out to 168 hours; ISO-NE next 2 days; CAISO Sufficiency Evaluation Demand Forecast 7-day.",
   "source": "SPP: https://marketplace.spp.org/file-api/download/mtlf-vs-actual?path=/YYYY/MM/DD/OP-MTLF-YYYYMMDDHHMM.csv (mirror portal.spp.org/file-browser-api/download/mtlf-vs-actual). ERCOT Public API developer.ercot.com, products NP3-561-CD / NP3-565-CD / NP3-566-CD. PJM Data Miner 2 feed load_frcstd_7_day (free account required for API). MISO api.misoenergy.org / MISO Data Exchange API. ISO-NE ISO Express. Python wrappers: gridstatus, isodata.",
   "cost": "free",
   "horizon": "0-7d hourly; the useful part is 0-3d",
   "skill_limit": "These are NWP-driven, so beyond ~day 3 the load forecast inherits raw temperature-forecast error and the ISO's own posted accuracy metrics degrade sharply. MISO posts monthly accuracy metrics; day-ahead load MAPE for large BAs is typically low single digits, but the 5-7 day tail is effectively a temperature forecast wearing a load costume. Also: the forecast is of METERED load, so it silently nets out behind-the-meter solar and any load that self-curtails.",
   "why_practitioners_use_it": "It is the only free, operator-produced, forward-looking demand number, and it is published before the gas day it applies to. Gas desks use DA load minus DA wind minus DA solar as the residual thermal requirement, then convert to burn. It is also the cleanest way to get a next-day view in a region without buying a vendor load forecast.",
   "we_already_have_it": "no"
  },
  {
   "name": "ISO day-ahead / 7-day WIND and SOLAR generation forecasts",
   "what_it_measures": "Forecast renewable output by hour, the direct burn-suppressor. ERCOT NP4-742-CD Wind Power Production hourly averaged actual AND forecast by geographic region (endpoint /np4-742-cd/wpp_hrly_actual_fcast_geo) and NP4-745-CD for solar; SPP Mid-Term Resource Forecast +7 days system-wide wind and solar; CAISO SLD_REN_FCST (DA and HASP, by NP15/ZP26/SP15); PJM Data Miner wind forecast and solar forecast (solar hourly, next 48h, updated hourly, includes behind-the-meter); MISO day-ahead wind and solar forecast looking two days ahead; ISO-NE Seven-Day Wind Power Forecast and Seven-Day Solar Power Forecast, updated daily by ~10:00 ET.",
   "source": "ERCOT Public API (NP4-742-CD, NP4-745-CD); SPP https://marketplace.spp.org/file-api/download/midterm-resource-forecast?path=/YYYY/MM/DD/OP-MTRF-*.csv; CAISO https://oasis.caiso.com/oasisapi/SingleZip?resultformat=6&queryname=SLD_REN_FCST&version=1; PJM Data Miner 2; MISO api.misoenergy.org; ISO-NE isoexpress seven-day-wind-power-forecast / seven-day-solar-power-forecast.",
   "cost": "free",
   "horizon": "0-7d, but wind skill collapses fastest of any input here",
   "skill_limit": "ERCOT day-ahead wind is roughly 11.5% MAPE (one published benchmark: 11.55% for D1 with 30-day input history vs 13.39% with one day). Wind forecast skill decays faster than temperature skill: beyond about day 3-5 a point wind forecast is close to climatology, which means for week-2 work wind must be carried as a DISTRIBUTION, not a number. Solar day-ahead is much more skillful than wind (clear-sky physics dominates) except under convective cloud regimes. ISO forecasts also cover only metered utility-scale plants except where explicitly stated.",
   "why_practitioners_use_it": "This is the mechanism behind 'hot day with wind burns less gas than a mild day without.' Desks do not forecast burn from temperature; they forecast RESIDUAL load. S&P Global documented the effect directly: record Midcontinent wind pushed gas-fired burn down at key supply hubs with wind at ~60% of SPP generation and ~20% of MISO, and separately reported burn recovering as wind faded.",
   "we_already_have_it": "no"
  },
  {
   "name": "Net load / residual thermal load (constructed, not published)",
   "what_it_measures": "DA load forecast minus DA wind forecast minus DA solar forecast, per BA/ISO, hourly - the quantity the thermal stack actually has to serve. Then subtract must-run nuclear, hydro and net imports, and subtract battery discharge in the ramp hours, to get the gas-and-coal call.",
   "source": "Constructed from the two rows above plus EIA-930 nuclear/hydro/storage series and NRC Power Reactor Status Report. No vendor needed.",
   "cost": "free",
   "horizon": "0-7d, matching its weakest input (wind)",
   "skill_limit": "Errors compound: load error and wind error are partly independent, so residual-load error is larger in absolute MW than either. It also breaks where interchange is large (CAISO imports, SPP-MISO seams) - a BA can serve residual load with purchases rather than local gas. Non-ISO Southeast has no published renewable forecast at all, so residual load there can only be built from the EIA-930 day-ahead demand forecast field minus a wind/solar persistence assumption.",
   "why_practitioners_use_it": "It is the correct causal variable. The desk's own S109/S110 finding - gw_cdd rose exactly as forecast on 06-29 and gas burn FELL 4.2 Bcf/d because wind rose 62% - is precisely a net-load event misread as a degree-day event. Degree days move load; net load moves burn.",
   "we_already_have_it": "no"
  },
  {
   "name": "Power-weighted cooling degree days (PWCDD)",
   "what_it_measures": "Degree days weighted by WHERE gas is burned to make electricity, rather than by population or by total gas consumption. One published construction weights 9 EIA census divisions from 3 years of summer gas generation across 47 balancing authorities: South Atlantic 24.0%, West South Central 17.7%, Middle Atlantic 13.5%, East North Central falls to ~11% (versus ~20% in a gas-weighted HDD construction), New England 3.5%.",
   "source": "GasAlpha publishes PWCDD (https://gasalpha.com/pwcdd) on GFS, IFS, GEFS and AIFS out 10 days. The weighting scheme is reproducible in-house from EIA-930 summer gas net generation by BA - which this desk already ingests - applied to its existing NWS/MOS station temperatures.",
   "cost": "free",
   "horizon": "0-10d (limited by the underlying NWP)",
   "skill_limit": "It is still a temperature aggregate: it cannot see wind, solar, outages or hydro. It fixes the WEIGHTING error, not the omitted-variable error. And the weights themselves drift as the fleet changes, so they need annual re-estimation. No public validation metrics against realized power burn were found on the vendor page - treat the weights as a hypothesis to be measured on our own corpus.",
   "why_practitioners_use_it": "Summer gas demand is roughly half power burn, and gas-weighted degree days are built for a heating-season, Midwest/Mid-Atlantic-heavy consumption footprint. Using them in summer aims the lens at the wrong states. This is the single cheapest upgrade available to this desk: same raw temperatures, different weights.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Humidity-adjusted cooling metrics (dew point, wet-bulb, enthalpy-based CDD, heat index)",
   "what_it_measures": "The latent (dehumidification) component of cooling load, which dry-bulb CDD ignores entirely.",
   "source": "NWS/METAR dew point is already in the same observation stream this desk pulls for temperature; MOS output carries dew point. Method references: Maia-Silva, Kumar and Nateghi, Nature Communications 2020, 'The critical role of humidity in modeling summer electricity demand across the United States'; building-science literature on enthalpy-based CDD and wet-bulb CDD.",
   "cost": "free",
   "horizon": "same as the temperature forecast it rides on (0-10d)",
   "skill_limit": "Published finding: in high-consumption states such as California and Texas, projections based on air temperature ALONE underestimate cooling demand by as much as 10-15%. The correction is regional - it is large in humid Southeast/Gulf load centers and small in the arid West, so a single national humidity adjustment will help in some cells and hurt in others. Dew-point forecast skill is also worse than temperature forecast skill, so the adjustment adds its own error at longer leads.",
   "why_practitioners_use_it": "Heat-index-based degree days have been measured to predict cooling energy roughly 20% more accurately than conventional temperature degree days in building-level work. For a desk whose largest summer driver is air conditioning in the South Atlantic and West South Central, dry-bulb-only is a known, quantified, one-directional bias.",
   "we_already_have_it": "no"
  },
  {
   "name": "Coal-to-gas switching band (delivered coal cost by basin vs gas dispatch cost)",
   "what_it_measures": "The gas price range over which coal and gas swap places in the dispatch order. Practitioner numbers currently in circulation: a national inflection around $3.25-$3.50/MMBtu; below roughly $3.00 serious switching begins; below ~$2.80 gas competes with Illinois Basin coal; around $2.50 gas competes with Powder River Basin coal in the western half of the country including ERCOT and the Midwest; above roughly $11/MMBtu there is zero incremental gas-fired generation left to displace coal. Standard convention: dark spread at 10,500 Btu/kWh coal heat rate, spark spread at 7,000 Btu/kWh gas.",
   "source": "EIA Coal Markets weekly spot prices for Central Appalachia, Northern Appalachia, Illinois Basin, Powder River Basin (free, updated Tuesdays - but EIA states the HISTORICAL series is vendor-proprietary and cannot be released, so history must be accrued forward from today). EIA Electricity Monthly Update 'resource use' page publishes the coal-vs-gas comparison on both $/MMBtu and $/MWh bases. RBN Energy 'Talkin bout My Generation - Coal to Gas Switching' Parts I and II. MNI Markets summer-2025 coal-to-gas switching note.",
   "cost": "mixed",
   "horizon": "weeks to months - it moves the LEVEL of burn, not the day",
   "skill_limit": "Three hard limits. (1) EIA itself disclaims the simple conversion: 'The conversion shown in this chart is done for illustrative purposes only... It involves delivered prices and emission costs, the terms of fuel supply contracts, and the workings of fuel markets.' (2) The band is not a constant - it moves with delivered coal (rail, basis), with which coal units still exist, and by region. (3) The response is capped by physical coal availability, not by price: in 2022 Henry Hub reached $6.60 and gas burn still rose ~7% y/y because bituminous stockpiles were ~65 days of burn, subbituminous ~76, and rail performance blocked replenishment. Price told you to switch; the coal was not there.",
   "why_practitioners_use_it": "It is the only mechanism that makes power burn respond to PRICE rather than weather, and it is the source of whatever price floor exists. It also sets the asymmetry: with ~80 GW of coal retired since 2018 against ~42 GW of gas added, the downside switch (cheap gas takes coal's share) still has room, while the upside switch (expensive gas hands share back to coal) is largely exhausted.",
   "we_already_have_it": "no"
  },
  {
   "name": "Coal stockpiles and days of burn",
   "what_it_measures": "Coal inventory at generators, in tons and in days of burn, by rank (bituminous vs subbituminous) - the physical ceiling on how much the switching band can actually deliver.",
   "source": "EIA Electricity Monthly Update coal stocks page (https://www.eia.gov/electricity/monthly/update/coal-stocks.php) and Form EIA-923 monthly receipts/stocks. Free.",
   "cost": "free",
   "horizon": "1-3 months (it is a slow state variable)",
   "skill_limit": "Monthly, with roughly a two-month lag, so it can never inform a next-day call - it conditions a REGIME, telling you whether the switching band is live or dead. It is also aggregated: a national days-of-burn number hides the plant-level and rail-corridor constraints that actually bind.",
   "why_practitioners_use_it": "It is the falsifier for the switching signal. When stockpiles are thin, a gas rally does NOT buy back coal generation, and any model that assumes it does will systematically under-forecast burn on high-price days. 2021-2022 is the worked example.",
   "we_already_have_it": "no"
  },
  {
   "name": "Forecasted thermal generation outages (non-nuclear)",
   "what_it_measures": "Scheduled and active outaged capacity of the fossil fleet going forward. ERCOT NP3-233-CD Hourly Resource Outage Capacity: aggregated ACTIVE outaged capacity by Load Zone from the Outage Scheduler for the next 168 hours, published every hour. PJM Data Miner feeds frcstd_gen_outages (MW totals of forecasted generation outages for the next 90 days by sub-region) and gen_outages_by_type (7 days by type). MISO publishes outage data.",
   "source": "ERCOT Public API NP3-233-CD; PJM Data Miner 2 (frcstd_gen_outages, gen_outages_by_type); MISO market reports.",
   "cost": "free",
   "horizon": "0-7d hourly (ERCOT), out to 90d in aggregate (PJM)",
   "skill_limit": "It is a plan, not an outcome - forced outages are by construction absent from a forward outage schedule, and forced outages are exactly what matters on the extreme days. ERCOT's product explicitly excludes certain outage categories and new-equipment outages. Aggregation by load zone or sub-region loses the unit-level heat rate, so you know MW out but not which rung of the stack was removed.",
   "why_practitioners_use_it": "An outage on a coal or nuclear unit is a direct, dated, forward-looking add to gas burn in that BA; an outage on an efficient CCGT raises the marginal heat rate and adds burn per MWh served. This desk already carries nuclear outages and stops there - the rest of the thermal fleet is roughly ten times the capacity.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Battery storage discharge and charge (burn suppressor and shape distorter)",
   "what_it_measures": "Grid-scale storage output, now large enough to displace the evening-ramp peaker dispatch that used to be the highest-heat-rate gas burn of the day. CAISO batteries delivered over 12 GW at the evening peak on 29 March 2026; on 7 October 2024 they discharged 8,354 MW, over 21% of system demand, in the hours that previously required gas peakers.",
   "source": "EIA-930 now breaks out battery storage as its own energy-source category (granular categories as of Q1 2025 include battery storage, wind with/without integrated storage, solar with/without integrated storage). CAISO and ERCOT publish real-time storage dispatch. Free.",
   "cost": "free",
   "horizon": "0-2d for dispatch behaviour; months for the capacity trend",
   "skill_limit": "Battery dispatch is an economic decision, not a weather outcome, so it is far less predictable than wind or solar - it responds to price spreads and to ancillary-service opportunity cost. It is also a shape signal, not a volume signal: batteries move gas burn between hours more than they remove it, since the charging energy has to come from somewhere. Behaviour changes discontinuously as new capacity and new bidding strategies arrive, so a fitted relationship ages in months.",
   "why_practitioners_use_it": "It is now the dominant reason a hot evening does not produce the peaker burn the temperature implies, in CAISO and increasingly ERCOT. It also broke the older 4CP heuristic outright.",
   "we_already_have_it": "partial"
  },
  {
   "name": "EIA-930 day-ahead demand forecast field (DF), especially non-ISO Southeast BAs",
   "what_it_measures": "Each balancing authority's own next-day hourly demand forecast, submitted on Form EIA-930. This is the ONLY free forward-looking load number for the Southeast, where no ISO exists: SOCO, TVA, DUK, FPL, SCEG and neighbours cover the largest concentration of summer gas burn in the country.",
   "source": "EIA Hourly Electric Grid Monitor / Form EIA-930 (https://www.eia.gov/electricity/gridmonitor/). Free. Also mirrored with cleaning by PUDL (Catalyst Cooperative) as Parquet.",
   "cost": "free",
   "horizon": "1d",
   "skill_limit": "Reporting is conditional: 'If a balancing authority does not produce a day-ahead demand forecast in the normal course of business, it is not required to produce one for EIA-930 purposes' - so coverage is uneven by BA and must be checked per BA before use. EIA-930 also carries documented data-quality issues: anomalous and missing values are replaced by IMPUTED values, sums of energy sources do not always equal reported net generation, subregion demand does not sum exactly to total demand, and only UTC timestamps are retained so localized times have DST gaps and duplicate hours. Crucially, only metered generation visible to the BA is included, so distributed/behind-the-meter solar is excluded and shows up as suppressed load.",
   "why_practitioners_use_it": "It is the free substitute for an ISO forecast in the third of the country that has no ISO. Given this desk's history of holes that are 'present, numeric, in range, right owner, self-consistent', the imputation flag and the per-BA DF coverage check are exactly the kind of thing that needs a hard assertion at stage time rather than a presence check.",
   "we_already_have_it": "partial"
  },
  {
   "name": "EPA CAMD / CAMPD hourly unit-level heat input (CEMS)",
   "what_it_measures": "Actual measured hourly heat input in MMBtu, plus gross load in MW, for essentially every fossil unit above 25 MW in the Lower 48. Dividing gives a MEASURED hourly heat rate per unit at every load level.",
   "source": "EPA Clean Air Markets Program Data, https://campd.epa.gov/ with a documented REST API at https://www.epa.gov/power-sector/cam-api-portal (emissions API returns hourly values, control technologies, unit type and unit fuel types). Also packaged by PUDL as EPA CEMS. Free.",
   "cost": "free",
   "horizon": "backward-looking only - it is a calibration source",
   "skill_limit": "Two limits, both hard. (1) Release cadence: EPA releases hourly CEMS quarterly with a 2-3 month lag, so it can never be a nowcast. (2) Fuel ambiguity: EPA states that information about which fuel was burned in each hour is NOT reported - a dual-fuel unit does not say what it ran on, and only the hourly F-factor gives an indication. So co-firing and dual-fuel units need inference.",
   "why_practitioners_use_it": "It is the ground truth for the MWh-to-Bcf conversion. A constant fleet heat rate is the single largest silent error in any EIA-930-derived burn estimate: CCGTs installed since 2015 average ~6,654 Btu/kWh, the 2020 combined-cycle fleet average is ~7,146, older pre-2000 units ~8,840, and simple-cycle combustion turbines are 9,000-11,500. When solar pushes dispatch into the evening ramp, the marginal unit shifts from CC to CT and the gas per MWh rises by 40% or more even though MWh served fell. CEMS lets that curve be estimated rather than assumed.",
   "we_already_have_it": "no"
  },
  {
   "name": "Pipeline EBB scheduled volumes at power-plant meters",
   "what_it_measures": "Same-day and next-day nominated/scheduled gas deliveries to individual power plants. FERC requires interstate pipelines to post daily scheduled volumes at every meter - receipt, delivery, storage and compressor - on their Electronic Bulletin Boards, publicly.",
   "source": "Individual pipeline EBBs (free, but scraping is the work); NAESB Gas-Electric Harmonization materials describe a project collecting from 21 interstate pipelines five times daily in MISO territory. Commercial equivalents: Wood Mackenzie/Genscape natural gas real-time (190+ pipelines, plus proprietary monitoring of 63 gas-fired plants NOT captured in public nomination data), Criterion Research meter-level nominations (also distributed via the ICE Developer Portal), S&P Global Platts Natural Gas Flow.",
   "cost": "mixed",
   "horizon": "intraday to 1d - the highest-frequency true burn signal that exists",
   "skill_limit": "Three known failure modes. (1) Coverage: intrastate systems - notably in Texas and Oklahoma - are not FERC-jurisdictional and do not post, and Genscape's own pitch is that 63 gas-fired plants are invisible in public nomination data. (2) Nominations are not burn: a plant nominates what it expects to need and can cut or add at the intraday cycles. (3) Scraping fragility - the NAESB project abandoned website scraping as unreliable because pipeline ownership and site structures change, moving to EDI feeds instead.",
   "why_practitioners_use_it": "It is the only pre-settlement, physical read on power burn, and its timing is tradeable: the gas day runs 09:00-09:00 Central with five NAESB cycles (Timely, Evening, Intraday 1, 2, 3). The Intraday 2 deadline at 15:30 Eastern is for gas that begins flowing at 19:00, and Intraday 3 at 20:00 Eastern for gas flowing at 23:00 - a generator that has not nominated by ID2 cannot start until 23:00. Those are hard, calendar-known information-arrival times inside our trading session.",
   "we_already_have_it": "no"
  },
  {
   "name": "Market-implied heat rate (day-ahead power price / gas price)",
   "what_it_measures": "The ratio of the power price at a hub to the gas price at the relevant gas hub for the same delivery period. It reveals whether gas is the marginal fuel and how deep into the gas stack the market expects to dispatch.",
   "source": "Day-ahead LMPs are free from every ISO (PJM Data Miner, ERCOT public API, MISO, SPP Marketplace, CAISO OASIS, NYISO, ISO-NE). Gas leg: Henry Hub is free from CME/NYMEX; regional basis is the paid leg - ICE publishes an end-of-day natural gas settlement report (ice.com/report/254) viewable free, with the CSV package sold by subscription. Method references: multi-fuel structural bid-stack models (arXiv:1205.2299) and clean spread option valuation (arXiv:1205.2302).",
   "cost": "mixed",
   "horizon": "0-2d spot; out the forward curve for the strip",
   "skill_limit": "The identity is contaminated as a burn signal: it tells you what the market believes, so it embeds the same information you are trying to forecast. It also uses HUB prices while actual dispatch uses the plant's nodal LMP and its delivered gas cost including transport and basis, which can differ materially. In the region where coal and gas jointly set price the relationship is non-linear in both fuels, so a single implied heat rate is not a sufficient statistic there.",
   "why_practitioners_use_it": "It is the cleanest available read on which rung of the stack is marginal, which is what determines whether an incremental MWh costs 6.6 or 11 MMBtu of gas. For a desk forecasting Henry Hub rather than power, its main use is as a CONDITION - implied heat rate near the CC heat rate means gas is marginal and load moves gas; far above it means peakers are marginal and burn is convex in load.",
   "we_already_have_it": "no"
  },
  {
   "name": "EIA-860M monthly generator inventory (planned additions and retirements)",
   "what_it_measures": "Unit-level planned capacity additions and retirements with expected month, prime mover, fuel and location - the forward drift of the dispatch stack itself.",
   "source": "EIA Form 860M (monthly), free. Corroborating aggregates: EIA reports ~6.4 GW of coal retirements planned for 2026 (~4% of the coal fleet), 508 GW of gas-fired capacity expected by end-2027 (+3% vs 2025), 26.8 GW of utility solar added in 2025, ~80 GW of coal retired since 2018 against 42+ GW of gas added.",
   "cost": "free",
   "horizon": "months to years - the only genuinely long-horizon signal in this domain",
   "skill_limit": "Announced dates slip routinely, especially retirements (reliability-must-run designations reverse them outright) and interconnection-queued additions. It also gives nameplate MW, not the capacity factor or heat rate that determines burn - 1 GW of new CT is worth far less burn than 1 GW of new CC. Rule of thumb for conversion: at ~45% efficiency, 1 Bcf/d sustains roughly 6,000 MW of continuous generation, so 1 GW running flat out is roughly 0.17 Bcf/d.",
   "why_practitioners_use_it": "It separates the two halves of power burn that must not be pooled. The published decomposition for summer 2026 is 40.3 Bcf/d total, 11 Bcf/d above the 2015 baseline, of which 7.9 Bcf/d is STRUCTURAL (retirements plus data-centre load) and 3.1 Bcf/d is ECONOMIC DISPATCH (price-driven switching, up from 1.2 Bcf/d in summer 2025). Structural growth is nearly weather-inelastic and nearly price-inelastic; economic dispatch is the only part that responds to the gas price.",
   "we_already_have_it": "no"
  },
  {
   "name": "Data-centre load as a weather-inelastic base layer",
   "what_it_measures": "Large flat load additions that raise the burn floor without raising weather sensitivity. US data-centre capacity ~44 GW in 2025, ~55 GW projected 2026 (a 25% single-year increase), ~74 GW by 2027; ~125 GW of added US load 2026-2030 in one bank forecast; concentrated in Virginia (PJM/DOM) and Texas (ERCOT).",
   "source": "EIA AEO2026 and STEO; EPRI 'Powering Intelligence'; utility IRPs and interconnection queues; realized signal is visible as a level shift in EIA-930 BA demand.",
   "cost": "free",
   "horizon": "quarters to years",
   "skill_limit": "Announced load is heavily over-forecast: speculative interconnection requests clog queues and distort utility forecasts, and multiple 2025-2026 reports document inflated Southeast projections and low regional transparency. EIA itself cut its 2026 generation forecast by more than a percentage point. Treat announced GW as an upper bound and prefer the realized BA-level demand level shift.",
   "why_practitioners_use_it": "It changes the SHAPE of the weather response, which matters more to a path forecaster than the level. A larger flat base means the same degree-day swing is a smaller percentage swing in load, and it pushes the stack further up the merit order so the marginal unit on an average day is less efficient. Both effects change the burn-per-CDD coefficient - a coefficient fitted from history will be stale in the direction of under-forecasting the base and over-forecasting the weather beta.",
   "we_already_have_it": "no"
  },
  {
   "name": "ERCOT 4CP demand-response window (June-September)",
   "what_it_measures": "A calendar-known, recurring, non-weather distortion: large industrial and crypto loads in ERCOT curtail during the interval they believe will be the monthly system peak, because transmission cost allocation uses the four monthly coincident peaks, June-September.",
   "source": "ERCOT 4CP Monitor dashboard, ERCOT 60-Day DAM Generation, ERCOT 4-second ESR charging and system demand feeds. Free.",
   "cost": "free",
   "horizon": "same-day, seasonal recurrence (Jun-Sep only)",
   "skill_limit": "It has become self-defeating and battery-corrupted. GridStatus documents the mechanism as an 'ouroboros' - as loads avoid the peak they prevent the peak from occurring. Battery charging has swamped the signal: in the first two weeks of June 2024, 90% of storage charging intervals were at or below 600 MW; over the same period in 2025 that threshold was 1,600 MW. The June 2024 official 4CP interval ranked 33rd in real-time operational load. So the observed ERCOT peak is now a poor read on underlying demand.",
   "why_practitioners_use_it": "For a desk that classifies by day type, this is a named, dated, seasonal day-class that makes ERCOT load - and therefore ERCOT burn - misleading on exactly the hottest afternoons. It is the kind of thing that produces a confident wrong-signed forecast on a day that looks maximally bullish.",
   "we_already_have_it": "no"
  },
  {
   "name": "Behind-the-meter (distributed) solar",
   "what_it_measures": "Rooftop and other distribution-level solar that never appears in ISO or EIA-930 metered generation and instead shows up as reduced load.",
   "source": "EIA Form 861M small-scale solar estimates (monthly, lagged); ISO-NE publishes a Distributed Generation Forecast; PJM's solar feed explicitly includes behind-the-meter solar; CAISO estimates BTM separately.",
   "cost": "free",
   "horizon": "structural, with a daily shape",
   "skill_limit": "PUDL's EIA-930 documentation states plainly that only metered generating units visible to the BA are included and that distributed solar and distribution-level generators are typically excluded. The bias is one-directional and growing, and it is worst in exactly the daylight hours when cooling load peaks. EIA-861M is monthly and lagged by months - there is no free daily BTM series.",
   "why_practitioners_use_it": "Because it makes any historically fitted load-vs-temperature relationship drift downward year over year in a way that looks like weather-model error. Practitioners either use a BTM-inclusive load definition (PJM's solar feed, ISO-NE's DG forecast) or re-fit the temperature coefficient annually.",
   "we_already_have_it": "no"
  },
  {
   "name": "Fleet heat-rate curve by hour and load level (constructed)",
   "what_it_measures": "MMBtu of gas per MWh of gas-fired generation as a function of how hard the gas fleet is being run - the conversion factor between EIA-930 gas generation and Bcf/d of burn.",
   "source": "Built from EPA CAMD hourly heat input plus EIA-930 hourly gas net generation; anchored on published fleet numbers (CC fleet ~7,146 Btu/kWh in 2020, post-2015 CC ~6,654, pre-2000 units ~8,840, simple-cycle CTs 9,000-11,500, coal steam ~10,000-10,500) and validated against EIA-923 monthly consumption.",
   "cost": "free",
   "horizon": "applies at every horizon - it is a transform, not a forecast",
   "skill_limit": "CEMS lags by 2-3 months so the curve is always fitted on stale fleet composition, and it drifts as new CCs enter and old units retire. Dual-fuel and co-firing units cannot be cleanly attributed because EPA does not collect hourly fuel type. The curve is also regionally different - a national curve applied to ERCOT or CAISO will be wrong in the ramp hours.",
   "why_practitioners_use_it": "Because a constant conversion factor manufactures a false signal. Solar does not simply remove gas MWh; it removes the EFFICIENT midday CC MWh and concentrates what remains into the evening ramp where CTs set the margin. Total gas generation can fall while gas BURN is flat. Any pipeline that multiplies EIA-930 gas MWh by a fixed heat rate will read that as bearish when it is not.",
   "we_already_have_it": "unclear"
  },
  {
   "name": "ISO real-time fuel mix (faster than EIA-930)",
   "what_it_measures": "Current generation by fuel, published by each ISO in near real time - hours to a day ahead of the EIA-930 consolidated view.",
   "source": "ERCOT Fuel Mix / Combined Wind and Solar dashboards, CAISO, MISO real-time displays (api.misoenergy.org/MISORTWDDataBroker), SPP, PJM, NYISO, ISO-NE. Wrapped by gridstatus / isodata. Free.",
   "cost": "free",
   "horizon": "0-1d",
   "skill_limit": "Definitions differ from EIA-930 (ISO footprints are not BA footprints, and ISOs vary on whether BTM and small units are netted), so ISO real-time and EIA-930 do NOT reconcile exactly and should never be spliced into one series without an explicit basis field. ISOs also revise their own real-time postings.",
   "why_practitioners_use_it": "Latency. EIA-930's value is coverage; the ISOs' value is speed. For a next-session forecast made before EIA-930 publishes, the ISO feed is the only realized read available.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Commercial load and renewable forecast vendors",
   "what_it_measures": "Bought load, wind, solar and price forecasts, generally ML-based and continuously re-fit, benchmarked against ISO forecasts.",
   "source": "Amperon (AI/ML demand forecasts, distributed on the Yes Energy platform), Enverus Short-Term Power and Renewables (markets CAISO and ERCOT wind and load forecasts specifically), Yes Energy, Wood Mackenzie North America Power, S&P Global Commodity Insights.",
   "cost": "paid",
   "horizon": "0-14d depending on product",
   "skill_limit": "Vendor accuracy claims are self-published and generally reported as beating the ISO forecast on selected intervals, not as an independently audited MAPE by horizon. The measurable gap versus free ISO forecasts is largest at day 0-2 and shrinks toward zero by day 5+, because at longer leads everyone is running the same NWP. Given this desk's free-first policy, the honest test is whether a vendor beats ISO MTLF plus ISO renewable forecast on OUR scoring metric - which is unknown until measured.",
   "why_practitioners_use_it": "Desks that trade power intraday buy them; gas desks forecasting a daily settle mostly do not need to, because the free ISO forecasts capture most of the forward information at the horizons that matter for a daily gas contract.",
   "we_already_have_it": "no"
  }
 ],
 "skill_horizon_notes": "The domain splits cleanly into a LEVEL channel and a VARIATION channel, and they have completely different horizons. Conflating them is the main way desks fool themselves here.\n\nVARIATION (what makes tomorrow different from today) is net load, and net load is weather. Its horizon is therefore bounded by NWP skill, and each input decays at a different rate:\n- Day 0 (intraday): pipeline nomination cycles are the true observable. Gas day 09:00-09:00 Central; five NAESB cycles; ID2 deadline 15:30 ET for 19:00 flow, ID3 20:00 ET for 23:00 flow. A generator that misses ID2 cannot start before 23:00. This is near-deterministic information arriving at fixed clock times.\n- Day 1-2: ISO day-ahead load and renewable forecasts. This is where the free data is genuinely strong - operator-produced, published before the gas day.\n- Day 3-5: still real skill, degrading. Wind degrades fastest. ERCOT day-ahead wind is ~11.5% MAPE and worsens materially each day out; by roughly day 3-5 a point wind forecast is close to climatology. Solar holds skill longer than wind. Load holds longer than either because temperature holds longer than wind.\n- Day 5-10: temperature only. Standard NWP verification puts useful 2m-temperature skill scores above 0.5 out to roughly 7-10 days in midlatitudes, and the conventional 0.6 anomaly-correlation threshold for 500 hPa is crossed somewhere around day 6-10 depending on model and season (ECMWF holds it longer than GFS). Ensembles extend the usable range beyond deterministic 10-day limits but only probabilistically.\n- Day 10-15: no daily skill. CPC 6-10 and 8-14 day outlooks are probabilistic tercile products scored by Heidke skill score, useful as a REGIME PRIOR (is the pattern likely hot or mild) and nothing finer. Subseasonal skill is documented as intermittent - 'windows of opportunity' tied to particular initial states - not a standing capability.\n- Beyond 15 days: for gas specifically, the published result is seasonal-mean and count-based, not daily - e.g. skilful forecasts of the NUMBER of high-demand days in a winter from forecast winter-mean circulation. Nothing there supports a daily path.\n\nThe practical consequence for a two-week path forecast: days 0-2 should be built mechanistically from net load and nominations; days 3-7 are weather-model-limited and should carry wind as a distribution rather than a number; days 8-14 should be a regime prior with a wide band, and any narrow directional conviction out there is almost certainly overfitting.\n\nLEVEL (what makes this summer different from last summer) has a much longer horizon and is where the durable information sits: coal retirements, gas capacity additions, solar and battery additions, data-centre load. The published decomposition for summer 2026 - 40.3 Bcf/d of power burn, 11 Bcf/d above the 2015 baseline, of which 7.9 Bcf/d is structural and only 3.1 Bcf/d is price-driven economic dispatch - says the majority of the year-over-year change is NOT weather and NOT price. That component is knowable months ahead from EIA-860M and interconnection queues and is nearly inelastic to both temperature and gas price.\n\nOne asymmetry worth naming: the switching channel is now one-directional in practice. Cheap gas can still take share from coal (the band runs roughly $3.50 down through $2.50 depending on basin and region). Expensive gas can no longer reliably hand share back, because the coal fleet is smaller, already running at high capacity factors, and inventory- and rail-constrained - which is why $6.60 gas in 2022 did not produce the switch the price implied. A model that treats switching as symmetric will be wrong specifically on high-price days.",
 "debunked_or_folklore": [
  "'Coal-to-gas switching sets a floor under gas prices.' Materially weaker than it was, and asymmetric. With ~80 GW of coal retired since 2018 and the surviving fleet consolidated into fewer, better plants running at high capacity factors, the upside direction (expensive gas buys back coal generation) is largely exhausted. 2022 is the counterexample of record: Henry Hub hit $6.60/MMBtu, the highest in nearly 14 years, and gas-fired burn still ROSE more than 7% y/y, because bituminous stockpiles were ~65 days of burn, subbituminous ~76, and rail could not replenish. Price said switch; physics said no.",
  "A fixed switching threshold ('$2.50 gas means switching'). There is no single number. The published figures are basin- and region-specific and they move: ~$3.25-3.50/MMBtu as a national inflection, sub-$3.00 for serious switching, ~$2.80 versus Illinois Basin, ~$2.50 versus PRB in the West/ERCOT/Midwest, and above ~$11 there is nothing left to switch. EIA itself disclaims the simple $/MWh conversion as 'for illustrative purposes only,' naming delivered prices, emission costs and contract terms as the missing pieces. Any hard-coded threshold in a play is exactly the kind of absolute bar this desk has already found decays into a condition that cannot change state.",
  "'Gas-weighted or population-weighted degree days are the summer power-burn driver.' Wrong weighting, measurably. Gas-weighted degree days are built for a heating-season consumption footprint (Midwest and Mid-Atlantic heavy). Power-weighted weights derived from actual summer gas generation across 47 BAs put South Atlantic at 24.0% and West South Central at 17.7% while East North Central falls from ~20% to ~11%. Same thermometers, different answer.",
  "'Dry-bulb CDD captures cooling demand.' It does not capture the latent load. Published finding: in high-consumption states such as California and Texas, temperature-alone projections underestimate cooling demand by 10-15%. Heat-index-based degree days have been measured to predict cooling energy ~20% better than conventional degree days in building-level work.",
  "'Hot weather is bullish gas.' Not unconditionally - and the failure is systematic, not random. Record heat in 2026 failed to rally Henry Hub because renewables and supply absorbed it. The correct variable is residual load, not temperature. The clean statement of the mechanism: a hot day with strong wind can burn LESS gas than a mild day with no wind, and this desk has already produced its own instance (gw_cdd rose exactly as forecast on 06-29 while gas burn fell 4.2 Bcf/d because wind rose 62%).",
  "'A national wind number tells you about gas burn.' It mostly does not. Wind only displaces gas where wind and gas sit on the same dispatch stack - SPP (wind has reached ~47-60% of generation), ERCOT, and MISO (~20%). PJM and the Southeast have little wind, and those are the largest gas-burning regions. A CONUS wind aggregate averages a strong regional signal against noise and produces a weak one. Per-BA or per-ISO, never pooled.",
  "'Solar is killing summer gas burn.' Half true and misleading in the operative half. Solar removes midday MWh from the most EFFICIENT units (CC at ~6,650-7,150 Btu/kWh) and concentrates the residual into the evening ramp where simple-cycle CTs at 9,000-11,500 Btu/kWh set the margin. Gas generation in MWh can fall while gas BURN in Bcf/d is flat or up. Any pipeline that multiplies EIA-930 gas MWh by a constant heat rate will read this as bearish when it is not.",
  "'EPA CEMS tells you which fuel each unit burned each hour.' It does not. EPA states explicitly that hourly fuel-burned information is not reported; a dual-fuel unit does not identify its fuel, and only the hourly F-factor gives an indication. CEMS is superb for heat input and heat rate, unreliable for fuel attribution on dual-fuel units.",
  "'EIA-930 is a clean measurement.' It is a good dataset with documented, named defects that are invisible to a presence check: anomalous and missing values are replaced by IMPUTED values, energy-source components do not always sum to reported net generation, subregion demand does not sum exactly to total demand, only UTC timestamps survive so localized times carry DST gaps and duplicate hours, and behind-the-meter solar and distribution-level generators are excluded entirely. The BTM exclusion is a one-directional and growing bias in the daylight hours that matter most for summer cooling.",
  "'ERCOT's afternoon peak load tells you how hot it really was.' Not in June-September. 4CP curtailment by industrial and crypto load, plus battery charging behaviour, have decoupled observed peak from underlying demand: storage charging thresholds roughly tripled between June 2024 and June 2025 (600 MW to 1,600 MW at the 90th percentile of intervals), and the official June 2024 4CP interval ranked 33rd in real-time operational load. GridStatus describes it as self-defeating - loads avoiding the peak prevent the peak.",
  "'Subseasonal (week 3-4) forecasts give a tradeable gas view.' The literature does not support a daily path at that range. Subseasonal skill is documented as intermittent and state-dependent - 'windows of opportunity' - and the genuinely skilful gas-relevant results are seasonal and count-based (e.g. above-median counts of high-demand days per winter from forecast winter-mean circulation), not daily magnitudes.",
  "'Announced data-centre load is load.' Interconnection queues are inflated by speculative requests, multiple 2025-2026 reports document over-forecasting in the Southeast specifically, and EIA cut its own 2026 generation forecast by more than a percentage point. Use realized BA-level demand level shifts in EIA-930; treat announced GW as an upper bound."
 ],
 "gaps_vs_our_stack": [
  "1. ISO day-ahead and 7-day WIND and SOLAR forecasts (free, all five named ISOs plus ISO-NE). Single highest-value gap. The desk currently has realized wind from EIA-930 and no forward wind at all - the same shape as the 06-29 miss where wind_mwh was served and read by nobody, except worse, because on a forecast day the realized value does not exist yet. Endpoints: ERCOT NP4-742-CD (/np4-742-cd/wpp_hrly_actual_fcast_geo) and NP4-745-CD; SPP marketplace.spp.org/file-api/download/midterm-resource-forecast; CAISO oasis.caiso.com SLD_REN_FCST; PJM Data Miner wind/solar forecast feeds; MISO api.misoenergy.org; ISO-NE seven-day wind and solar.",
  "2. ISO day-ahead and 7-day LOAD forecasts (free). The forward demand side. SPP MTLF +7d, ERCOT NP3-561/565/566-CD, PJM load_frcstd_7_day, MISO 168-hour, ISO-NE, CAISO. Pairs with (1) to build net load.",
  "3. NET LOAD as a derived, first-class field (load forecast minus wind forecast minus solar forecast, per BA, hourly). Costs nothing beyond (1) and (2) and is the actual causal driver of thermal dispatch. This is the structural fix for the class of error where a correctly forecast degree-day add produces the wrong sign on burn.",
  "4. Power-weighted degree days. Cheapest fix on this list: same NWS/MOS temperatures already ingested, reweighted by summer gas generation share per BA (which EIA-930 already provides). Directly addresses the recorded finding that the desk's degree-day weights are hand-set, unvalidated, and that Ohio has no station at all against PJM being the largest gas-burning BA.",
  "5. Humidity in the cooling metric - dew point, wet-bulb or enthalpy-based CDD. Dew point is in the same NWS/MOS stream already pulled. Published 10-15% one-directional bias in California and Texas from temperature-only.",
  "6. Forecasted THERMAL generation outages beyond nuclear: ERCOT NP3-233-CD (168h, hourly refresh), PJM frcstd_gen_outages (90 days) and gen_outages_by_type (7 days), MISO. Free, forward-looking, and the fossil fleet is roughly ten times the nuclear capacity the desk already tracks.",
  "7. A fitted fleet HEAT-RATE CURVE to replace whatever constant converts EIA-930 gas MWh to Bcf/d. Built from EPA CAMD hourly heat input (free, campd.epa.gov, REST API at epa.gov/power-sector/cam-api-portal) against EIA-930 gas generation. Backward-looking calibration only - 2-3 month lag, quarterly release - but it removes a systematic, shape-dependent bias that grows every year solar and batteries add capacity.",
  "8. Coal-side inputs for the switching band: EIA Coal Markets weekly basin spot prices (free, Tuesdays - but history is vendor-proprietary, so accrual must START NOW and cannot be backfilled) plus EIA coal stocks / days-of-burn. Without the coal leg the desk has no price-responsive demand channel at all, only weather.",
  "9. EIA-930's own day-ahead demand forecast (DF) field, specifically for the non-ISO Southeast BAs (SOCO, TVA, DUK, FPL, SCEG). The only free forward load number in the largest summer-burn region in the country. Requires a per-BA coverage assertion because the field is not universally reported.",
  "10. Battery storage series from EIA-930 (broken out as its own category since Q1 2025), plus CAISO/ERCOT storage dispatch. The evening-ramp burn that batteries displace is the highest-heat-rate burn of the day, so its suppression is worth more Bcf/d than the MWh suggest.",
  "11. EIA-860M planned additions and retirements. The structural half of power burn - published as 7.9 of the 11 Bcf/d above baseline for summer 2026 - and the only signal in this domain with a months-to-years horizon.",
  "12. Pipeline EBB scheduled volumes at power-plant meters. Highest-frequency true burn signal that exists, free in principle (FERC-mandated posting), expensive in engineering. Known failure modes: Texas/Oklahoma intrastates do not post, ~63 gas-fired plants are invisible in public nominations, and scraping is documented as fragile. Worth scoping only after 1-6.",
  "13. Day-ahead LMPs and market-implied heat rate at ISO hubs (free from every ISO). Best used as a REGIME CONDITION - is the marginal unit a CC or a CT - rather than as a direct burn predictor, since it embeds the same information being forecast.",
  "14. ERCOT 4CP as a named seasonal day-class (June-September). Cheap to add as a calendar flag and it marks the days when ERCOT observed load is least trustworthy - which are the hottest afternoons, i.e. the days a naive model is most confident.",
  "15. ISO real-time fuel mix for latency (hours-to-a-day ahead of EIA-930 consolidated). Needs its own basis field: ISO footprints are not BA footprints and the two series must never be spliced without declaring which produced each reading."
 ],
 "sources": [
  "https://rbnenergy.com/talkin-bout-my-generation-coal-to-gas-switching-part-I",
  "https://rbnenergy.com/talkin-bout-my-generation-coal-to-gas-switching-part-II",
  "https://www.mnimarkets.com/articles/summer-2025-ngas-power-demand-us-coal-to-gas-switching-1742397027874",
  "https://www.eia.gov/electricity/monthly/update/resource-use.php",
  "https://www.eia.gov/electricity/monthly/update/coal-stocks.php",
  "https://www.eia.gov/tools/faqs/faq.php?id=18&t=5",
  "https://www.eia.gov/coal/markets/",
  "https://www.eia.gov/electricity/gridmonitor/about",
  "https://docs.catalyst.coop/pudl/en/stable/data_sources/eia930.html",
  "https://catalystcoop-pudl.readthedocs.io/en/latest/data_sources/epacems.html",
  "https://campd.epa.gov/",
  "https://www.epa.gov/power-sector/cam-api-portal",
  "https://www.epa.gov/system/files/documents/2022-07/CAMD's%20Power%20Sector%20Emissions%20Data%20Guide%20-%2007182022.pdf",
  "https://www.ercot.com/mp/data-products/data-product-details?id=NP4-742-CD",
  "https://www.ercot.com/mp/data-products/data-product-details?id=NP3-565-CD",
  "https://www.ercot.com/mp/data-products/data-product-details?id=np3-561-cd",
  "https://www.ercot.com/mp/data-products/data-product-details?id=NP3-233-CD",
  "https://developer.ercot.com/applications/pubapi/relnotes/",
  "https://dataminer2.pjm.com/feed/load_frcstd_7_day/definition",
  "https://dataminer2.pjm.com/feed/frcstd_gen_outages/definition",
  "https://dataminer2.pjm.com/feed/gen_outages_by_type/definition",
  "https://www.pjm.com/-/media/DotCom/etools/data-miner-2/data-miner-2-api-guide.ashx",
  "https://marketplace.spp.org/pages/midterm-resource-forecast",
  "https://marketplace.spp.org/groups/operational_data",
  "https://www.spp.org/documents/37657/spp%20markets%20public%20data%20guide--v13.pdf",
  "https://www.caiso.com/documents/oasis-frequently-asked-questions.pdf",
  "https://www.caiso.com/Documents/OASIS-InterfaceSpecification_v5_1_2Clean_Fall2017Release.pdf",
  "https://api.misoenergy.org/MISORTWDDataBroker/",
  "https://www.pcienergysolutions.com/2025/05/01/how-miso-forecasts-load-wind-solar-output/",
  "https://www.iso-ne.com/isoexpress/web/reports/operations/-/tree/seven-day-wind-power-forecast",
  "https://www.iso-ne.com/isoexpress/web/reports/operations/-/tree/seven-day-solar-power-forecast",
  "https://www.iso-ne.com/system-planning/system-forecasting/distributed-generation-forecast",
  "https://opensource.gridstatus.io/en/latest/autoapi/gridstatus/index.html",
  "https://blog.gridstatus.io/ercot-4cp-2025-june/",
  "https://blog.gridstatus.io/predicting-ercot-4cp/",
  "https://gasalpha.com/pwcdd",
  "https://thundersaidenergy.com/downloads/air-conditioning-energy-demand-sensitivity/",
  "https://www.nature.com/articles/s41467-020-15393-8",
  "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7125155/",
  "https://www.eia.gov/todayinenergy/detail.php?id=32572",
  "https://www.eia.gov/todayinenergy/detail.php?id=61444",
  "https://www.eia.gov/todayinenergy/detail.php?id=44636",
  "https://www.eia.gov/todayinenergy/detail.php?id=48436",
  "https://www.eia.gov/todayinenergy/detail.php?id=65787",
  "https://www.eia.gov/todayinenergy/detail.php?id=66464",
  "https://www.eia.gov/todayinenergy/detail.php?id=67427",
  "https://www.eia.gov/todayinenergy/detail.php?id=60942",
  "https://www.nrc.gov/reading-rm/doc-collections/event-status/reactor-status/index",
  "https://www.powermag.com/record-power-burn-expected-this-summer-as-coal-retirements-and-data-centers-drive-gas-demand/",
  "https://spglobal.com/platts/en/market-insights/latest-news/natural-gas/031621-gas-to-coal-switching-in-miso-spp-risks-midwest-summer-power-burn-demand",
  "https://www.spglobal.com/energy/en/news-research/latest-news/natural-gas/040821-midcontinent-power-burns-gas-prices-face-downside-risk-as-wind-generation-picks-up",
  "https://www.spglobal.com/commodity-insights/en/news-research/latest-news/natural-gas/061121-hot-weather-lower-wind-output-lift-gas-generation-prices-remain-a-risk",
  "https://www.spglobal.com/commodity-insights/en/news-research/latest-news/coal/072721-gas-fired-power-burn-intensity-surges-as-fuel-switching-capacity-wanes",
  "https://insight.factset.com/the-limits-of-coal-to-gas-switching",
  "https://www.naturalgasintel.com/news/renewables-batteries-complicating-natural-gas-power-burn-forecasts/",
  "https://naturalgasintel.com/news/record-heat-fails-to-spark-henry-hub-rally-as-renewables-hefty-supply-crimp-upside/",
  "https://www.woodmac.com/industry/commodity-trading-analytics/natural-gas-supply-demand/",
  "https://developer.ice.com/fixed-income-data-services/catalog/criterion-research",
  "https://www.ice.com/report/254",
  "https://www.naesb.org/pdf4/geh062923w2.pdf",
  "https://www.monitoringanalytics.com/reports/Presentations/2023/IMM_EGCSTF_Gas_Nomination_Cycles_and_Units_Operating_Parameters_20230718.pdf",
  "https://www.pcienergysolutions.com/2023/10/03/the-complete-guide-to-streamlining-natural-gas-scheduling/",
  "https://www.cpc.ncep.noaa.gov/products/predictions/610day/",
  "https://www.cpc.ncep.noaa.gov/products/predictions/short_range/verifications/html/srskill_exp.html",
  "https://www.ecmwf.int/en/forecasts/quality-our-forecasts",
  "https://www.ecmwf.int/en/elibrary/73843-forecast-skill-horizon",
  "https://iopscience.iop.org/article/10.1088/1748-9326/aaf338",
  "https://arxiv.org/pdf/1205.2299",
  "https://arxiv.org/pdf/1205.2302",
  "https://www.sciencedirect.com/science/article/abs/pii/S0306261920315014",
  "https://www.enverus.com/blog/precision-power-forecasting-leading-wind-and-load-forecasts-in-caiso-and-ercot/",
  "https://www.amperon.co/products/load-forecasting",
  "https://www.caiso.com/documents/2024-special-report-on-battery-storage-may-29-2025.pdf",
  "https://powering-intelligence.epri.com/load-growth.html",
  "https://www.utilitydive.com/news/energy-short-term-outlook-2026-load-demand-data-centers/807530/"
 ]
}
```

## LENS: Analog and quantitative forecasting method - analog retrieval, distance metrics, library depth, regime classification, and the overfitting/validation discipline around them

```json
{
 "domain": "Analog and quantitative forecasting method - analog retrieval, distance metrics, library depth, regime classification, and the overfitting/validation discipline around them",
 "signals": [
  {
   "name": "Delle Monache analog similarity metric (weighted, sigma-normalized, time-windowed)",
   "what_it_measures": "Distance between a target forecast state and a past forecast state. Sum over predictors i of (w_i / sigma_fi) * sqrt( sum over j=-t~..+t~ of (F_i,t+j - A_i,t'+j)^2 ). Three load-bearing pieces our method lacks: (a) each predictor is divided by ITS OWN historical standard deviation so units cancel, (b) w_i is an explicit per-predictor weight, (c) the match is computed over a short TIME WINDOW around the lead time (t~ = half-width), not at a single instant - so it matches trajectory shape, not a point.",
   "source": "Delle Monache, Eckel, Rife, Nagarajan, Searight (2013) Mon. Wea. Rev. 141:3498. Reference implementation is open source: PAnEn (C++) / RAnEn (R), Weiming Hu / Penn State, github + weiming-hu.github.io/AnalogsEnsemble.",
   "cost": "free",
   "horizon": "Inherits the horizon of whatever it post-processes. AnEn is a post-processing/calibration method - it does NOT manufacture skill beyond the driver forecast. Applied to NWP it is used at 0-72h routinely, out to the driver's useful range.",
   "skill_limit": "Published limits: (1) standard AnEn is run with about 5 predictors despite NWP carrying hundreds, because optimal weight search 'scales exponentially with the number of variables'; (2) it shows 'systematic bias when applied to extreme events'; (3) it adds little where the deterministic driver is already accurate; (4) archive length saturates near 4 years, after which accuracy DEGRADES with longer archives because the underlying model changes underneath the library (Hu et al., arXiv:2103.04530).",
   "why_practitioners_use_it": "It is the metric that beat Euclidean and Mahalanobis distance in head-to-head tests and became the operational standard at NCAR/RAL for wind, solar, temperature and air-quality post-processing. The sigma normalization is what stops a high-variance predictor from silently dominating the match - which is the exact failure mode of an unnormalized multi-field comparison.",
   "we_already_have_it": "no"
  },
  {
   "name": "Analog-to-target distance scaling law: <r_k> ~ (k/L)^(1/d)",
   "what_it_measures": "How good the k-th best analog is, as a function of library size L and the LOCAL DIMENSION d of the state you are matching on. This is the single most important quantitative result for our method. It says analog quality improves only as L^(-1/d) - i.e. adding history buys you almost nothing once d is large - and that the k-th analog degrades as k^(1/d).",
   "source": "Platzer, Yiou, Naveau, Tandeo, et al. (2021), 'Probability Distributions for Analog-to-Target Distances', J. Atmos. Sci. 78:3317, arXiv:2101.10640. Builds on Van den Dool (1994) and Nicolis (1998).",
   "cost": "free",
   "horizon": "Not a horizon signal - a design constraint that binds at every horizon.",
   "skill_limit": "Invert it and it is brutal for us. L = k / r^d. To get a normalized analog distance r = 0.1 with a single analog: d=3 needs L ~ 1,000 sessions (about 4 years); d=4 needs ~10,000 (40 years); d=10 needs 10^10 sessions. With our library at roughly a few hundred to a couple thousand sessions, the matching dimension must be about 3, at most 4, or the retrieved 'analog' is at a distance indistinguishable from a random day. The paper also gives the trade: d_max,K = d_max,1 * (1 - log K / log L), so with L=10^4 raising K from 1 to 25 forces d down from 10 to 6.",
   "why_practitioners_use_it": "It is the formal statement of why Lorenz's original analog program died and why every serious analog system aggressively reduces dimension (PCA, regime labels, learned embeddings) before searching. It also explains the counterintuitive result that for LOW-dimension systems using many analogs hurts badly (the 30th analog is vastly worse than the 1st), while for high-dimension systems K barely matters because they are all equally bad.",
   "we_already_have_it": "no"
  },
  {
   "name": "k-NN edge-length law: l ~ (k/n)^(1/d) - the same law, arrived at independently in ML",
   "what_it_measures": "The side length of the smallest hypercube containing the k nearest neighbours in d dimensions with n samples. Worked numbers for k=10, n=1000: d=2 -> 0.1; d=10 -> 0.63; d=100 -> 0.955; d=1000 -> 0.9954. Above d~10 you need essentially the entire space to find 10 neighbours, so 'nearest' neighbours are no more similar than random points.",
   "source": "Cornell CS4780 lecture notes (Weinberger), cs.cornell.edu/courses/cs4780 lecturenote02_kNN; standard result, Bellman (1961).",
   "cost": "free",
   "horizon": "n/a - structural.",
   "skill_limit": "Stated limit: to hold l=0.1 you need n = k * 10^d, which for d>100 exceeds the number of electrons in the universe. The escape hatch is explicit and is the one we should take: k-NN works when the data has LOW INTRINSIC dimensionality even if the ambient dimension is high - i.e. when the predictors lie on a low-dimensional manifold. That justifies compressing many fundamentals into a handful of factors before matching, and does NOT justify matching on many conditions at once.",
   "why_practitioners_use_it": "Two literatures that never cite each other - dynamical-systems analog theory and machine-learning nearest-neighbour theory - produce the identical exponent. That convergence is the strongest evidence available that the constraint is real and not an artifact of either field's assumptions.",
   "we_already_have_it": "no"
  },
  {
   "name": "Van den Dool catalog-size result (the founding negative result)",
   "what_it_measures": "The mean recurrence time of a good analog grows exponentially with dimension. For a hemispheric 500mb field, a useful natural analog requires a library on the order of 10^30 years.",
   "source": "Van den Dool (1994), 'Searching for analogues, how long must we wait?', Tellus 46A:314. Restated in Van den Dool, 'Empirical Methods in Short-Term Climate Prediction' (OUP 2007).",
   "cost": "free",
   "horizon": "n/a",
   "skill_limit": "This IS the limit. Lorenz's 5 years of twice-daily hemispheric data was hopeless. Nicolis (1998) sharpened it: mean recurrence time is not enough because the relative standard deviation of that recurrence time is very large - so even the average is optimistic, and analog availability is itself highly variable day to day.",
   "why_practitioners_use_it": "Everybody in operational analog forecasting cites it as the reason nobody does raw full-field analog matching. The successors all do one of two things instead: reduce d hard (indices, regimes, PCs), or CONSTRUCT an analog from a linear combination rather than picking one.",
   "we_already_have_it": "no"
  },
  {
   "name": "Constructed Analog (CA) - linear combination of past states instead of picking one day",
   "what_it_measures": "Rather than retrieving the single closest historical day and re-anchoring it, CA solves for a weighted linear combination of past observed anomaly patterns whose sum reproduces the current initial state to within tolerance, then propagates that same weight vector forward on the historical outcomes.",
   "source": "Van den Dool, NOAA CPC. Operational for CPC monthly/seasonal outlooks; documented in van den Dool, Huang & Fan (2003) JGR 108:8617 (US soil moisture 1981-2001) and van den Dool & Barnston (1995) for SST.",
   "cost": "free",
   "horizon": "Monthly to seasonal in its operational use; the method itself is horizon-agnostic.",
   "skill_limit": "Published statement: constructed analogues outperform NATURAL analogues, and the margin is largest in 'specification' mode (predicting one variable from another contemporaneously) rather than in true forward prediction. That is the honest caveat - CA's biggest measured win is in the nowcast/mapping role, not the forecast role.",
   "why_practitioners_use_it": "It sidesteps Van den Dool's own catalog problem: you never need one day that matches, you need a basis that spans the current state. It also naturally produces a magnitude rather than requiring a re-anchor step, and the weights are auditable.",
   "we_already_have_it": "no"
  },
  {
   "name": "Analog ensemble member count K ~ 20-21 (about 3-4 percent of the archive)",
   "what_it_measures": "How many retrieved analogs to keep. Measured optimum, not a convention.",
   "source": "Alessandrini, Delle Monache, Sperati, Cervone (2015) Applied Energy (solar) and (2015) Renewable Energy (wind): best CRPS at M=20 members. Djalalova/Delle Monache air-quality AnEn: 'best 20 analogs... 3-4% of the total cases in the archive'. Hu et al. deep-analog work: 21 members.",
   "cost": "free",
   "horizon": "n/a",
   "skill_limit": "Stated as an explicit trade-off, not a free parameter: enough analogs to sample the observed distribution of the predictand, but not so many that the marginal analogs are no longer similar to the target. The 3-4%-of-archive framing is the more transferable form - it scales K with L rather than fixing it. Note the Platzer result cuts against large K in low-dimensional settings.",
   "why_practitioners_use_it": "It is what turns an analog into a DISTRIBUTION. The single biggest structural difference between the operational analog literature and our method: they never retrieve one day. The ensemble spread is the uncertainty estimate, and it is the thing that is verified (CRPS, reliability), not the central member.",
   "we_already_have_it": "no"
  },
  {
   "name": "Predictor-weight optimization by brute-force CRPS minimization, and PCA-based weighting",
   "what_it_measures": "How to set the w_i in the analog metric. Two published strategies: exhaustive/brute-force search over weight combinations minimizing CRPS on a training set (static), a dynamic variant that re-weights by recent performance, and a PCA of the predictor set to decorrelate before weighting.",
   "source": "Junk, Delle Monache, Alessandrini, von Bremen, Cervone (2015), Meteorologische Zeitschrift 24:361-379, 'Predictor-weighting strategies for probabilistic wind power forecasting with an analog ensemble'.",
   "cost": "free",
   "horizon": "n/a",
   "skill_limit": "Measured gain about 20% over the unweighted/original prediction for both onshore and offshore sites. The cost is the limit: brute-force weight search scales exponentially in the number of predictors, which is precisely WHY operational AnEn is stuck near 5 predictors. If you cannot afford the search, you cannot afford the predictors.",
   "why_practitioners_use_it": "It converts 'which conditions matter' from an argued judgement into a fitted, falsifiable object with a scoring rule attached. It is also the honest accounting of the predictor budget: every predictor you add has to pay for itself in CRPS or it is diluting the match.",
   "we_already_have_it": "no"
  },
  {
   "name": "Learned analog metric (Deep Analog / ConvLSTM latent embedding)",
   "what_it_measures": "Replaces the hand-weighted Euclidean metric with a learned embedding - forecast fields are mapped into a ~120-dimensional latent space by a convolutional LSTM, and analog distance is computed there. Solves three named defects of the classical metric at once: no grid search for weights, no hard cap on predictor count, and spatial coherence is respected instead of matching each grid point independently.",
   "source": "Hu, Cervone, Young, Delle Monache (2021-2022), 'Weather Analogs with a Machine Learning Similarity Metric for Renewable Resource Forecasting' (arXiv:2103.04530) and Boundary-Layer Meteorology 'Machine Learning Weather Analogs for Near-Surface Variables'; EarthCube 2021 notebook 'Spatio-Temporal Deep Analogs'.",
   "cost": "free",
   "horizon": "Same as the driver forecast.",
   "skill_limit": "Measured: 17.54% improvement for solar irradiance and 15.74% for surface wind speed versus the NAM baseline, beating equal-weight AnEn. Limits carried over from classical AnEn: bias on extreme events, and the archive saturation near 4 years driven by operational model updates. Trained 2011-2018, tested 2019 (and a separate 2015-2017 train / 2018-2019 test), so the demonstrated generalization gap is short.",
   "why_practitioners_use_it": "This is the current research frontier of the exact method we run. The stated motivation - 'the hand-tuned metric cannot adapt when operational models are updated' - is our problem too: our brain version changes and any hand-set match weights silently go stale.",
   "we_already_have_it": "no"
  },
  {
   "name": "DTW warping-window constraint (small windows, learned, not maximal)",
   "what_it_measures": "How much temporal elasticity to allow when matching two sequences. The measured result is counter-intuitive and directly contradicts the naive use of DTW: classification accuracy PEAKS at very small warping windows and degrades as the window widens toward full DTW.",
   "source": "Ratanamahatana & Keogh (2005), 'Three Myths about Dynamic Time Warping Data Mining', SIAM SDM (myth: 'a larger warping window gives better accuracy' - refuted). Dau, Silva, Petitjean, Keogh et al. (2018), 'Optimizing dynamic time warping's window width', Data Mining and Knowledge Discovery 33:1074.",
   "cost": "free",
   "horizon": "n/a",
   "skill_limit": "The window width must be LEARNED from training data and is small (single-digit percent of series length in many datasets); an unconstrained DTW is typically worse than plain Euclidean. This is the cleanest published case of shape-matching flexibility being an overfitting mechanism rather than a modelling gain.",
   "why_practitioners_use_it": "If we ever allow time-shifting when matching a session's shape - and 're-anchor its level' is one step from 're-align its timing' - this is the guardrail. The honest reading for us: DTW is a legitimate tool with a hard-learned parameter, and using it without learning the window is worse than not using it.",
   "we_already_have_it": "no"
  },
  {
   "name": "Matrix Profile (motif and discord discovery)",
   "what_it_measures": "All-pairs nearest-neighbour distance for every subsequence of a series. Returns, for each window, the distance to its closest match anywhere in the corpus. Motifs = smallest values (repeated shapes). DISCORDS = largest values (the subsequence with no analog at all).",
   "source": "Keogh group, UCR (cs.ucr.edu/~eamonn/MatrixProfile.html); open-source implementations (STUMPY, matrixprofile-ts). Financial application: 'Financial Time Series: Market Analysis Techniques Based on Matrix Profiles', MDPI Engineering Proceedings 5(1):45.",
   "cost": "free",
   "horizon": "n/a - a retrieval and detection primitive.",
   "skill_limit": "It is exact and has only one parameter (subsequence length m), which is its selling point, but m is a real choice and results are m-dependent. It tells you a shape recurs; it says nothing about whether recurrence carries forward information - the published financial applications are descriptive/interpretive, not demonstrated alpha.",
   "why_practitioners_use_it": "The DISCORD half is what we do not have and structurally need. It gives a principled, computable answer to 'is there an analog for today at all' - and a discord is exactly the day on which a forced analog retrieval will produce a confident wrong number. This maps directly onto our own finding that the machinery cannot emit NO CALL.",
   "we_already_have_it": "no"
  },
  {
   "name": "Weather regimes as a categorical analog key (4 North American regimes)",
   "what_it_measures": "Daily 500mb geopotential height anomalies, detrended and standardized, reduced by PCA, then k-means clustered into 4 recurring flow patterns: Pacific Trough, Pacific Ridge, Alaskan Ridge, Greenland High (some implementations add a 5th 'No Regime' class for days closer to the origin than to any centroid). Forecast fields are projected onto the centroids to give regime probabilities.",
   "source": "ERA5 reanalysis 1980-2024 (free, Copernicus CDS) for the centroids; free operational regime charts from Simon Lee (simonleewx.com/ecmwf_north_america_regimes, /gefs_north_america_regimes); commercial version from World Climate Service. Load linkage: npj Clim Atmos Sci (2024) 7, 'The impact of North American winter weather regimes on electricity load in the central United States'.",
   "cost": "mixed",
   "horizon": "Stated strong for medium-range 7-15 days and subseasonal 15-46 days. Measured (arXiv:2409.08174): in winter, persistence remains competitive through week 2; in spring/summer/fall, model predictability exceeds persistence at weeks 3-8. Pacific Trough and Pacific Ridge are the most predictable regimes; predictability source shifts from atmosphere (weeks 1-2) to ocean (after week 2) to land (weeks 3-6).",
   "skill_limit": "Explicitly stated by the vendor: regime analysis 'reduces detail; cannot represent localized or rare patterns not captured in the regime set'. It will not give you a cold snap in Ohio; it gives you the probability of the flow pattern that produces one. Also: the 'No Regime' class is common and is not a failure of the method, it is a real state.",
   "why_practitioners_use_it": "This is the practitioner answer to Van den Dool. Instead of matching a high-dimensional state (impossible), you match a LABEL from a 4-way partition (d effectively ~1-2), which is exactly the dimension reduction the scaling law demands. It is also the honest description of what is forecastable at 2-6 weeks: the regime, not the day.",
   "we_already_have_it": "no"
  },
  {
   "name": "Teleconnection index conditioning for analog selection (ENSO, MJO phase/amplitude, NAO, PNA, PDO, stratospheric polar vortex)",
   "what_it_measures": "Low-dimensional indices that summarise the large-scale state. Used as the analog KEY at subseasonal-to-seasonal range: find past dates with similar MJO phase/amplitude + ENSO state + SPV strength, then composite what followed.",
   "source": "NOAA CPC free daily/weekly index files (cpc.ncep.noaa.gov: ONI, MJO RMM via BoM, AO/NAO/PNA daily indices, 10hPa zonal wind for SPV). World Climate Service packages a subseasonal analog tool on exactly this menu of indices for power and gas desks.",
   "cost": "free",
   "horizon": "Weeks to months. This is the horizon band where dynamical daily forecasts are dead and index-conditioned analogs are the only game.",
   "skill_limit": "The vendor's own stated discipline is the limit and it is worth quoting in substance: treat individual analog years with caution regardless of how impressive the similarity looks; the combined consensus of a large array of dynamical AND statistical predictors is a more reliable guide than any single analog. Also, beyond week 2 the daily anomaly correlation over CONUS is essentially zero - only the intraseasonal-oscillation MODE retains correlation around 0.3.",
   "why_practitioners_use_it": "It is the standard operating method on gas and power desks for the 3-week-and-out view, and it is the lowest-dimensionality analog key available - which is precisely why it survives the catalog-size problem.",
   "we_already_have_it": "no"
  },
  {
   "name": "Detrended climatology baseline for any degree-day or temperature analog",
   "what_it_measures": "Whether the anomaly you are matching on is measured against the right zero. Guidance is explicit: use a climatology spanning the FULL range of years in the sample, and detrend strongly-trending variables (temperature, SST) before computing anomalies.",
   "source": "World Climate Service, 'Analog Forecasting and Climatology Period Selection' (2023-10-04).",
   "cost": "free",
   "horizon": "n/a - a preprocessing requirement.",
   "skill_limit": "Measured consequence of getting it wrong: comparing older analog years against a recent 20-year (2004-2023) climatology produced temperature anomaly errors of several degrees and, in the worked Nebraska example (+0.9F/decade trend since 1950), REVERSED THE SIGN of the El Nino signal - the raw comparison said El Nino winters trend cold, the detrended one said the opposite.",
   "why_practitioners_use_it": "It is the cheapest possible way to destroy an analog library, and it is invisible because every individual anomaly still looks numerically reasonable. This is structurally the same class of defect as our own wrong-encoding and off-instrument holes: present, numeric, in range, and wrong.",
   "we_already_have_it": "unclear"
  },
  {
   "name": "GEFSv12 Reforecast archive (2000-2019) as a point-in-time analog library",
   "what_it_measures": "A 20-year retrospective forecast archive from a FROZEN model version: daily 00Z, 5 members, plus a weekly 11-member run extending to +35 days. It gives you, for any past date, what a consistent model would have forecast - so you can build forecast-to-forecast analogs rather than forecast-to-observation.",
   "source": "NOAA GEFS Reforecast v12, free on AWS Open Data: registry.opendata.aws/noaa-gefs-reforecast, bucket noaa-gefs-retrospective.s3.amazonaws.com. Description PDF at the same bucket.",
   "cost": "free",
   "horizon": "Reforecasts run to +16 days daily and +35 days weekly - which covers the desk's entire stated 'next day to roughly two weeks' window and beyond.",
   "skill_limit": "Frozen model version is both the feature and the limit: it removes the model-change contamination that causes AnEn archive saturation at ~4 years, but it also means the reforecast climatology differs from today's operational GEFS, so bias correction between the two is required. 5 members/day is thin for tail work.",
   "why_practitioners_use_it": "The entire AnEn method requires PAIRS of (past forecast, verifying observation) - not past observations alone. A minimum of about 6 months of paired forecast+observation is required to run AnEn at all, and 12-15 months is the stated typical training length. Our stack has realized HDD/CDD and MOS forecast temps with cycle timing, but a frozen-model 20-year reforecast is a different and much deeper object.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Point-in-time forecast history (as-issued, not revised)",
   "what_it_measures": "What the forecast actually said on the day, versus what a reanalysis says the forecast should have said. Vendors sell 9+ years of it specifically for backtesting energy weather signals.",
   "source": "World Climate Service point-in-time forecast history (commercial); free partial substitutes are GEFSv12 reforecast (above) and IEM MOS archive.",
   "cost": "paid",
   "horizon": "n/a - a backtest-integrity requirement.",
   "skill_limit": "The vendor states the failure directly: backtesting a signal on REVISED forecasts produces look-ahead bias and false confidence. There is no published number attached, but the mechanism is the same one that produced our own hole #11 (reading past the decision point) and hole #7 (the partial-fetch tail reporting coverage 1.0 while being 68% wrong).",
   "why_practitioners_use_it": "It is the single point on which a weather-driven analog backtest is most likely to be silently wrong, and the one that flatters results most. Our MOS-with-cycle-timing work is the right instinct; this is the industrialized version of it.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Purged + embargoed cross-validation, and Combinatorial Purged CV (CPCV)",
   "what_it_measures": "A validation scheme for overlapping-window financial data. Purging removes training samples whose event windows intersect the test fold; embargoing adds a buffer after each test fold so feature computation cannot draw on post-test data. CPCV generates many train/test path combinations so every part of the series is tested multiple times.",
   "source": "Lopez de Prado (2018), 'Advances in Financial Machine Learning', ch. 7 and 12. Wikipedia 'Purged cross-validation' carries a clean statement of the mechanics.",
   "cost": "free",
   "horizon": "n/a",
   "skill_limit": "Recent comparative work finds CPCV superior for mitigating overfitting risk, but walk-forward remains the industry standard for a REALISTIC trading simulation - i.e. CPCV measures overfit better while walk-forward measures tradeability better, and you need both. CPCV also cannot fix a leaked feature; it only fixes the split.",
   "why_practitioners_use_it": "Any analog retrieval where the matched window overlaps the evaluated outcome window leaks by construction. This is the standard remedy and it is directly applicable to how we score a re-anchored analog day.",
   "we_already_have_it": "no"
  },
  {
   "name": "Deflated Sharpe Ratio, Probability of Backtest Overfitting, Minimum Backtest Length",
   "what_it_measures": "How much of a measured edge is explainable by the number of trials that produced it. DSR corrects a Sharpe ratio for selection bias under multiple testing, non-normality, and sample length. PBO estimates the probability that the selected configuration underperforms out-of-sample. Minimum Backtest Length gives the years of data needed before a selected Sharpe is credible given N trials.",
   "source": "Bailey & Lopez de Prado (2014), 'The Deflated Sharpe Ratio', Journal of Portfolio Management 40(5); Bailey, Borwein, Lopez de Prado, Zhu (2014), 'The Probability of Backtest Overfitting'; davidhbailey.com/dhbpapers/deflated-sharpe.pdf; SSRN 2460551 and 2326253.",
   "cost": "free",
   "horizon": "n/a",
   "skill_limit": "The correction needs the EFFECTIVE number of independent trials N, and trials are usually not independent - Lopez de Prado's own remedy is to cluster similar strategies (ONC / hierarchical / spectral) and count clusters, which is itself a modelling choice. So the deflation is an estimate, not a certificate.",
   "why_practitioners_use_it": "It is the discipline that a growing play library demands. We are at 82 plays with a merge process that adds several per group - that is a trial count, and the selection is happening on the same walk that measures it. The minimum-backtest-length framing is the one that bites: N trials require materially more history before a selected result means anything.",
   "we_already_have_it": "no"
  },
  {
   "name": "Diebold-Mariano / Giacomini-White significance testing against a named naive benchmark",
   "what_it_measures": "Whether a forecast improvement is statistically distinguishable from the benchmark rather than a sample artifact.",
   "source": "Lago, Marcjasz, De Schutter, Weron (2021), 'Forecasting day-ahead electricity prices: a review of state-of-the-art algorithms, best practices and an open-access benchmark', Applied Energy 293:116983 (arXiv:2008.08004), with the epftoolbox Python package and open datasets.",
   "cost": "free",
   "horizon": "n/a",
   "skill_limit": "The review's own diagnosis of the field is the useful part: new methods are compared on unique, non-public datasets, over test samples that are too short and limited to one market; they are rarely benchmarked against well-established simple models; and significance testing is seldom conducted. Their prescription is multiple years AND multiple markets.",
   "why_practitioners_use_it": "This is the closest published analogue to our own walk: an energy price forecasting field that had to build a public benchmark because internally-validated improvements kept not replicating. The 'multiple years and multiple markets' rule is a direct challenge to a 10-day-block-at-a-time evaluation.",
   "we_already_have_it": "partial"
  },
  {
   "name": "The correct price benchmark set for Henry Hub: end-of-month random walk, futures curve, EIA STEO",
   "what_it_measures": "What any forecast of the NG price must beat, and at which horizon each one is the thing to beat.",
   "source": "Baumeister, Kilian, and co-authors, 'Forecasting Natural Gas Prices in Real Time', NBER WP 33156, published in Journal of Applied Econometrics (2026), doi 10.1002/jae.70018. Related: Baumeister & Kilian real-time oil forecasting series; Benyo et al. (2026) Economic Inquiry reappraisal.",
   "cost": "free",
   "horizon": "Monthly, evaluated out to 24 months.",
   "skill_limit": "The measured division of labour: the simple end-of-month random walk is useful only at VERY near-term horizons; EIA experts have a clear advantage at medium horizons; the futures market leads at the longest horizons (about +4% at h=21, +10% at h=24 relative to the longer evaluation sample) but LOSES its edge at intermediate horizons (about -5% on average). Best overall is a real-time combination of models selected on recent performance, and the single best individual model is a six-variable BVAR on supply and demand fundamentals. Crucially: the whole literature is MONTHLY. There is no published evidence base of fundamental price predictability at the daily-to-two-week horizon this desk operates on. And the reappraisal result matters: when Baumeister-Kilian's oil forecasts are compared to END-OF-MONTH rather than monthly-AVERAGE no-change forecasts, none show improvements that are significant and consistent on both MSPE and directional accuracy. Benchmark choice decides the answer.",
   "why_practitioners_use_it": "It sets the honest prior for our own scoreboard. It also implies where our edge can and cannot be: not in analog matching of price history (no published support at our horizon), but in the weather-to-demand transfer function and the flow/microstructure layer, which this literature does not touch.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Markov-switching / MS-GARCH regime classification for gas price volatility",
   "what_it_measures": "A discrete latent state (typically 2: high-vol and low-vol) with a transition matrix, allowing parameters to jump rather than drift. Used to condition MAGNITUDE rather than direction.",
   "source": "Standard literature: MS-VAR for US gas (Energy Economics 2018, 'Understanding the US natural gas market: A Markov switching VAR approach'); cointegrated regime-switching with jumps on NG futures (Risks 5(3):48, MDPI); MS-GARCH volatility forecasting studies reporting superior predictive ability for gas volatility.",
   "cost": "free",
   "horizon": "Days to months for the volatility state; the state is persistent by construction.",
   "skill_limit": "The methodological caution is the useful one: regime-switching allows parameters to change DRASTICALLY versus time-varying-parameter models where they change gradually, and which is right is an empirical question the model cannot answer about itself. State counts above 2-3 are generally not identifiable on commodity data, and the filtered state probability is a smoothed, revised object - the real-time (filtered) state is materially noisier than the published (smoothed) one, which is where backtests of regime models most often leak.",
   "why_practitioners_use_it": "It is the standard formal answer to 'what regime are we in' for magnitude scaling. Our vol_regime module occupies this slot; the literature says the discrete-state version is the one with measured forecasting support for gas specifically.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Time-lagged recurrence / local dimension as a per-day predictability diagnostic",
   "what_it_measures": "Estimates the LOCAL predictability of the current state directly from the data, via recurrence (how often and how closely the system has revisited this neighbourhood), without needing the forward operator. Local dimension d is the same d that appears in the analog scaling law - so estimating it tells you both how good your best analog is likely to be and how far ahead it will carry.",
   "source": "'Time-Lagged Recurrence: a data-driven method to estimate the predictability of dynamical systems', arXiv:2409.14865; theoretical basis in Faranda/Messori local-dimension work and Platzer et al. (2021); Tandeo et al., 'Using Local Dynamics to Explain Analog Forecasting of Chaotic Systems' (J. Atmos. Sci.).",
   "cost": "free",
   "horizon": "Produces a per-state horizon estimate rather than assuming a fixed one.",
   "skill_limit": "Explicitly scale-dependent - predictability differs across temporal and spatial scales, so a single scalar horizon is a simplification. Estimating local dimension from short records is noisy and biased; these are attractor-geometry methods designed for long records.",
   "why_practitioners_use_it": "It is the formal version of 'today has no analog'. Paired with a matrix-profile discord, it gives two independent routes to a defensible NO CALL, and it makes the horizon a MEASURED per-day quantity rather than a fixed doctrine.",
   "we_already_have_it": "no"
  },
  {
   "name": "Gas-weighted degree days from a multi-model consensus, with model-spread as the uncertainty measure",
   "what_it_measures": "The practitioner-standard demand proxy: temperature weighted by regional gas consumption across census divisions/EIA regions, computed from a blend of GFS, ECMWF IFS, GEFS, CMC and now AIFS, with the GFS-vs-ECMWF spread and the 4-model consensus tracked as separate quantities for the day 11-15 window.",
   "source": "NatGasWeather.com (live HDD/CDD, updates at 5z/9z/13z/21z), GasAlpha (GWDD by census division), Celsius Energy, Commodity Weather Group, DTN, Atmospheric G2. EBW AnalyticsGroup publishes its blending approach: ECMWF/GFS/CMC with bias-correction and blending weighted by forecast skill.",
   "cost": "mixed",
   "horizon": "0-15 days operationally. The 12z run (roughly 11am-1pm ET for operational models, closer to 1pm for ensembles) is the one that moves the market; 0z and 12z carry more weight than 6z/18z because of denser initialization data.",
   "skill_limit": "Days 11-15 GWDD carries very little meteorological skill - practical midlatitude predictability is about 10 days - yet it demonstrably moves price. That gap is the point: at days 11-15 what is forecastable is the MARKET'S REACTION to the model runs, not the weather. Treating a day-13 GWDD as a demand forecast is a category error; treating it as a positioning/flow input is not.",
   "why_practitioners_use_it": "It is what the desk on the other side of our trades is actually watching, on a published schedule. The bias-correct-then-blend-by-skill construction (EBW) is also the correct way to combine models and is not the same as averaging them.",
   "we_already_have_it": "partial"
  }
 ],
 "skill_horizon_notes": "The binding question - how far out is a useful forecast possible - has a reasonably firm answer, and it is a LAYERED one. Different things are forecastable at different ranges and they should not be scored on the same clock.\n\nDAYS 0-10 (weather-driven, genuinely forecastable). Zhang, Sun, Magnusson et al. (2019, J. Atmos. Sci. 76:1077, 'What Is the Predictability Limit of Midlatitude Weather?') put the SKILLFUL forecast lead time for midlatitude instantaneous weather at about 10 days, with a theoretical ceiling near 2 weeks and roughly 5 days of headroom still theoretically available to better models and initialization. This is the band where a weather-conditioned analog can carry real information, because the driver carries real information.\n\nDAYS 10-15 (the market's weather, not the weather). Beyond ~10 days the deterministic daily signal is gone, but the gas market trades the 11-15 day GWDD consensus anyway, on a published model-run schedule. So in this band the forecastable object is the market's REACTION function to model runs, not demand. Any analog built here must be keyed on forecast-state (what the models said) rather than on outcome-state, or it is fitting noise.\n\nWEEKS 3-8 (regime probabilities only). Over CONUS at weeks 3-4 the anomaly correlation based on DAILY anomaly is almost zero; only the intraseasonal-oscillation MODE retains correlation slightly above 0.3 (Week 3-4 predictability studies, Clim Dyn 52:5861). Most week 3-4 hindcast cases show no significant skill by MSE even where 'predictability' exists. What DOES carry: weather-regime occupancy. Measured (arXiv:2409.08174), persistence stays competitive through week 2 in winter, but in spring/summer/fall model predictability of North American regimes exceeds persistence at weeks 3-8, with Pacific Trough and Pacific Ridge the most predictable, and the source of skill migrating atmosphere (wk 1-2) -> ocean (wk 2+) -> land (wk 3-6). Practically: at 3+ weeks forecast the REGIME and its load/burn signature, never the day.\n\nPRICE, separately. The published NG price forecasting literature is entirely monthly. Baumeister/Kilian et al. (NBER 33156 / JAE 2026) find the end-of-month random walk is only useful at very near-term horizons, EIA experts win the medium horizons, futures win at 21-24 months, and a real-time performance-weighted combination beats all of them - but nothing in that literature speaks to the daily-to-two-week horizon we operate on. There is no published evidence base of fundamental price predictability at our horizon. The deflationary reading, which we should hold: our edge is unlikely to live in price-history analog retrieval and more likely lives in the weather-to-demand transfer function (where the driver has real 0-10 day skill) plus flow/microstructure.\n\nTHE HARD CONSTRAINT ON OUR SPECIFIC METHOD. Two independent literatures give the same scaling law for how good a retrieved analog is: <r_k> ~ (k/L)^(1/d) (Platzer/Yiou 2021 in dynamical systems) and l ~ (k/n)^(1/d) (nearest-neighbour theory in ML). Inverted: L = k / r^d. For a decent normalized analog distance (r ~ 0.1) with a single match, d=3 needs ~1,000 sessions (4 years), d=4 needs ~10,000 (40 years), d=10 needs 10^10 sessions. Our library is a few hundred to a couple thousand sessions. Therefore THE MATCHING DIMENSION MUST BE ABOUT 3, AT MOST 4. Any analog retrieval that conditions on ten or more simultaneous conditions is, by this law, returning a day no closer than a random day - and it will still return one, confidently. Two further consequences worth flagging: (a) using MORE analogs costs dimension - d_max,K = d_max,1 * (1 - log K / log L), so with L=10^4 going from K=1 to K=25 forces d from 10 down to 6; (b) archive depth does not rescue you, because quality only improves as L^(-1/d), which is why the AnEn literature finds accuracy SATURATES near 4 years of archive and then degrades as the underlying model drifts.\n\nTHE OPERATIONAL SUMMARY. A useful forecast is possible out to about 10 days for weather-driven state, to weeks 3-8 for regime probabilities (mostly outside winter), and at no published horizon for price from price history. Our stated 'next day out to roughly two weeks' is the right window and sits exactly at the edge of the weather predictability limit - which means the back half of it (days 10-14) should be explicitly reclassified as a market-reaction problem, not a fundamentals problem.",
 "debunked_or_folklore": [
  "'More analogs is better.' Refuted with a formula: r_k ~ k^(1/d). For LOW local dimension (Lorenz-63, D1 ~ 2.06) the 30th analog is vastly worse than the 1st and K=40 is far too many; only for HIGH dimension does K stop mattering - and it stops mattering because they are all equally bad. The measured operational optimum for AnEn is about 20 (roughly 3-4% of the archive), not 'as many as you can find'.",
  "'A larger DTW warping window gives a better match.' Explicitly named and refuted as Myth #1 in Ratanamahatana & Keogh (2005). Classification accuracy peaks at very SMALL warping windows; unconstrained DTW is frequently worse than plain Euclidean distance. The window must be learned, and it is typically single-digit percent of series length (Dau et al. 2018).",
  "'A deeper analog library keeps helping.' Measured false in the AnEn literature: standard AnEn hits a saturation point around FOUR years of history and accuracy then degrades with longer archives, because operational model updates make the old archive a different system. The theory agrees - quality only improves as L^(-1/d), so at even moderate d the returns to depth are negligible before the non-stationarity cost arrives.",
  "'Global/full-field analog forecasting is achievable with enough data.' Dead since Van den Dool (1994): the required catalog is on the order of 10^30 years for a hemispheric field. Every surviving analog method works by aggressive dimension reduction (indices, regimes, PCs, learned embeddings) or by CONSTRUCTING an analog from a linear combination rather than retrieving one. Nicolis (1998) made it worse - the variance of the recurrence time is large, so even the mean is optimistic.",
  "'Clustering price shapes finds profitable patterns.' J.P. Morgan's own published study (50,000 chunks of 50 trading days, ~30 years of S&P 500, K-Means / DBSCAN / hierarchical / autoencoders) reports: no clusters emerged as particularly profitable or unprofitable, and cluster CENTERS were almost identical between the profitable, unprofitable and unfiltered sets despite large return differences. The shapes are real (oscillatory, cosine-like harmonics); the edge is not in them. Caveat they state: 5-week study, single 50-day window length.",
  "'Technical chart patterns predict returns.' Lo, Mamaysky & Wang (2000) found incremental INFORMATION in some indicators over 1962-1996, but the finding does not survive as tradeable: Sullivan/Timmermann/White-style Reality Check corrections show apparent profitability across large rule universes is largely data snooping, most rules do not beat buy-and-hold net of costs, and a 2014 study of 93 technical indicators found little evidence any predict real market returns even allowing effectiveness to vary by business cycle or sentiment regime.",
  "'k-NN / nonlinear nearest-neighbour prediction beats linear models on financial series.' Not substantiated out-of-sample. The exchange-rate literature (Fernandez-Rodriguez, Sosvilla-Rivero and successors) repeatedly finds nearest-neighbour forecasts FAIL to beat a simple AR model, that in-sample nonlinearity does not imply out-of-sample gain, and that any apparent gains are sensitive to both the forecast horizon and the accuracy metric chosen.",
  "'A single striking analog year is informative.' The weather shops that sell analog products say the opposite in their own marketing: treat individual analog years with caution regardless of how impressive the similarity appears; the consensus of a large array of dynamical AND statistical predictors is more reliable. Their own 'remarkable analog' write-ups carry this caveat.",
  "'Any recent climatology is fine as the anomaly baseline.' Measured false and it can FLIP THE SIGN of a conclusion. Scoring older analog years against a recent 20-year climatology in a warming trend produced anomaly errors of several degrees and reversed the apparent El Nino winter temperature signal in the worked example. Full-period climatology plus detrending is the stated fix.",
  "'Regime-switching models give you the current regime in real time.' The published, smoothed state probabilities are computed with hindsight over the whole sample; the real-time FILTERED state is materially noisier and is what a live system would actually have had. A regime backtest run on smoothed probabilities is a look-ahead, and it is a common one.",
  "'Beating the random walk proves a price forecast works.' Benchmark choice decides the answer. When Baumeister-Kilian's oil forecasts are re-scored against END-OF-MONTH no-change rather than monthly-AVERAGE no-change, none show improvements that are both significant and consistent across MSPE and directional accuracy. Name the benchmark before the result, not after.",
  "'Consistency of a data block confirms it.' Not folklore from the literature but the exact failure our own hole #8 produced, and the analog literature has the same trap in a different dress: an analog retrieved on a wrong-but-well-formed key returns a coherent, self-consistent past day. Only reconciliation against an independent source settles it - internal consistency is never the test."
 ],
 "gaps_vs_our_stack": [
  "A FORMAL ANALOG DISTANCE METRIC. Highest expected value by a wide margin. We have no explicit d(target, candidate). The operational standard is the Delle Monache metric: per-predictor sigma normalization (so no high-variance field silently dominates), explicit weights w_i, and matching over a TIME WINDOW around the lead rather than at a point. Reference implementation is free and open (PAnEn/RAnEn). Without this, 'find a past day whose shape matches' is unauditable, and there is no object to which the library-depth scaling law can even be applied.",
  "A DECLARED DIMENSION BUDGET, AND ENFORCEMENT OF IT. The scaling law L = k / r^d says our library size supports a matching dimension of about 3, at most 4. We currently carry 82 plays, 24 of which had absolute bars. If retrieval conditions on many of them simultaneously, the retrieved analog is provably no closer than a random session - and the machinery will still return it with a magnitude attached. Concretely: compute the effective d of the current match, publish it beside every retrieval, and hard-fail above the budget. This is the single most likely explanation for blind-vs-refine gaps that no amount of play refinement will close.",
  "ANALOG ENSEMBLES INSTEAD OF ONE RE-ANCHORED DAY. Every operational analog system retrieves K ~ 20 (about 3-4% of the archive) and reports the DISTRIBUTION; the spread is the uncertainty estimate and CRPS is what gets verified. We retrieve one day and re-anchor its level. Moving to K analogs gives us a magnitude distribution rather than a point, gives a native confidence measure, and would have made several of our large single-day errors visibly wide-band before the fact rather than after.",
  "A COMPUTABLE 'NO ANALOG EXISTS' TEST. Two free, independent routes: matrix-profile DISCORD (the subsequence whose nearest neighbour anywhere in the corpus is farthest - i.e. today has no match) and the time-lagged-recurrence local-predictability estimator. This bears directly on our own structural finding that the coordinator hard-fails on non-numeric output and therefore forces a call every day, making a forced number indistinguishable from a confident one. A discord score is a defensible, numeric, auditable basis for NO CALL that does not require changing the contract to accept prose.",
  "WEATHER REGIMES AS THE ANALOG KEY (4 North American regimes, k-means on detrended standardized 500mb PCs, plus a 'No Regime' class). This is the practitioner answer to exactly our problem: it collapses the match to d ~ 1-2, which is the only dimension the scaling law permits at our library size. Free to build (ERA5 via Copernicus CDS) and free to monitor operationally (Simon Lee's ECMWF and GEFS regime charts). Skill horizon 7-46 days, which brackets our entire window.",
  "GEFSv12 REFORECAST (2000-2019, free, AWS Open Data). AnEn requires PAIRS of past forecast and verifying observation - a minimum of ~6 months, typically 12-15 months. We have realized degree days and MOS forecast temps, but a frozen-model 20-year reforecast archive (daily 5-member to +16d, weekly 11-member to +35d) is a categorically deeper library and removes the model-drift contamination that causes the 4-year saturation. Direct answer to our 'served but unread' problem in the other direction: this is a large, free, unserved input.",
  "LEARNED PREDICTOR WEIGHTS WITH A SCORING RULE (brute-force CRPS minimization or PCA weighting, Junk et al. 2015, measured +20%). This converts 'which conditions matter' from an argued judgement into a fitted object that can be refuted. It also enforces the predictor budget honestly - a predictor that does not pay for itself in CRPS is diluting the match, which is the quantitative form of our own finding that a condition which cannot change state carries no information.",
  "PURGED + EMBARGOED CROSS-VALIDATION (and CPCV) FOR ANALOG SCORING. Any retrieval whose matched window overlaps the evaluated outcome leaks by construction. We have caught several leak classes by hand (the future-in-the-state hole, the blind/refine filename collision, the price leak in the handoff chain); purging and embargoing is the standard structural remedy rather than a per-incident patch.",
  "MULTIPLE-TESTING CORRECTION ON THE PLAY LIBRARY (Deflated Sharpe / PBO / Minimum Backtest Length). 82 plays selected and merged on the same walk that measures them is a trial count. The clustering step (count effective independent trials, not raw trials) matters because our plays are correlated by construction. This will not tell us which play is wrong; it will tell us how much of the aggregate improvement is selection.",
  "DETRENDED, FULL-PERIOD CLIMATOLOGY FOR EVERY DEGREE-DAY ANOMALY. Cheap, and the documented failure mode is sign reversal, not degradation. Worth an explicit check on our gas-weighted HDD/CDD baseline - the failure is invisible because every individual anomaly still reads numerically reasonable, which is the same signature as our wrong-encoding and off-instrument holes.",
  "CONSTRUCTED ANALOG AS AN ALTERNATIVE TO SINGLE-DAY RE-ANCHORING. Solve for a weighted linear combination of past states that reproduces the current state, then carry the same weights forward. It sidesteps the catalog-size problem entirely (you never need one day that matches), produces a magnitude natively without a re-anchor step, and the weights are auditable. Operational at NOAA CPC. Honest caveat: its measured advantage over natural analogs is largest in specification/nowcast mode.",
  "AN EXPLICIT BENCHMARK SUITE WITH SIGNIFICANCE TESTING. Name the benchmark before the result: end-of-month no-change, the futures curve, and a persistence/seasonal-naive, scored with Diebold-Mariano or Giacomini-White. The Lago/Weron review's diagnosis of energy price forecasting - unique non-public datasets, short single-market test samples, no comparison to simple models, no significance testing - describes a field that had to build a public benchmark because internal improvements kept not replicating. Our 10-day-block evaluation is exposed on the 'too short, one market' axis specifically.",
  "A LEARNED SIMILARITY METRIC (Deep Analog: ConvLSTM to a ~120-dim latent space, distance computed there). Lower priority than the above because it needs the classical metric in place first, but it is where this method's research frontier is, it removes the exponential weight-search cost, it lifts the ~5 predictor ceiling, and its stated motivation - hand-tuned metrics go stale when the underlying model is updated - is precisely our brain-version problem.",
  "DTW WITH A LEARNED, SMALL WARPING WINDOW - only if we ever allow time-alignment in matching. Flagged as a gap mainly to pre-empt a mistake: if 're-anchor its level' ever becomes 're-align its timing', an unconstrained DTW is worse than no DTW."
 ],
 "sources": [
  "https://journals.ametsoc.org/view/journals/mwre/141/10/mwr-d-12-00281.1.xml",
  "https://weiming-hu.github.io/AnalogsEnsemble/doc",
  "https://ar5iv.labs.arxiv.org/abs/2103.04530",
  "https://ar5iv.labs.arxiv.org/abs/2101.10640",
  "https://journals.ametsoc.org/view/journals/atsc/78/10/JAS-D-20-0382.1.pdf",
  "https://www.schweizerbart.de//papers/metz/detail/24/84737/Predictor_weighting_strategies_for_probabilistic_w",
  "https://earthcube2021.github.io/ec21_book/notebooks/ec21_hu_etal/WH_01_Spatio-Temporal_Deep_Analogs_2021.html",
  "https://link.springer.com/article/10.1007/s10546-022-00779-6",
  "https://ral.ucar.edu/solutions/products/analog-ensemble-anen",
  "http://geoinf.psu.edu/publications/2015_AppliedEnergy_AnEn-solar_Alessandrini.pdf",
  "https://www.mdpi.com/1996-1073/16/22/7630",
  "https://www.cpc.ncep.noaa.gov/products/outreach/proceedings/cdw27_proceedings/hvandendool_2002.pdf",
  "https://agupubs.onlinelibrary.wiley.com/doi/10.1029/2002jd003114",
  "https://journals.ametsoc.org/view/journals/atsc/76/4/jas-d-18-0269.1.xml",
  "https://link.springer.com/article/10.1007/s00382-018-4484-9",
  "https://journals.ametsoc.org/jcli/article/30/10/3499/106918/Predictability-of-Week-3-4-Average-Temperature-and",
  "https://arxiv.org/abs/2409.08174",
  "https://ar5iv.labs.arxiv.org/abs/2409.08174",
  "https://www.nature.com/articles/s41612-024-00803-1",
  "https://www.worldclimateservice.com/2021/09/02/what-is-analog-forecasting/",
  "https://www.worldclimateservice.com/2023/10/04/climatology-period-and-analog-forecasting/",
  "https://www.worldclimateservice.com/2025/10/27/weather-regime-forecasts/",
  "https://www.worldclimateservice.com/quantitative-trading/",
  "https://simonleewx.com/ecmwf_north_america_regimes/",
  "https://simonleewx.com/gefs_north_america_regimes/",
  "http://alumni.cs.ucr.edu/~ratana/RatanamC.pdf",
  "https://link.springer.com/article/10.1007/s10618-018-0565-y",
  "https://www.francois-petitjean.com/Research/Dau2017.pdf",
  "https://www.cs.ucr.edu/~eamonn/MatrixProfile.html",
  "https://www.mdpi.com/2673-4591/5/1/45",
  "https://www.cs.cornell.edu/courses/cs4780/2018fa/lectures/lecturenote02_kNN.html",
  "https://arxiv.org/abs/2409.14865",
  "https://tandeo.wordpress.com/wp-content/uploads/2021/06/15200469-journal-of-the-atmospheric-sciences-using-local-dynamics-to-explain-analog-forecasting-of-chaotic-systems.pdf",
  "https://journals.ametsoc.org/view/journals/mwre/145/4/mwr-d-16-0123.1.xml",
  "https://www.jpmorgan.com/technology/technology-blog/searching-for-patterns",
  "https://www.nber.org/system/files/working_papers/w7613/w7613.pdf",
  "https://homepage.ntu.edu.tw/~ckuan/pdf/snoop01.pdf",
  "https://www.sciencedirect.com/science/article/abs/pii/S0169207099000035",
  "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551",
  "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2326253",
  "https://en.wikipedia.org/wiki/Purged_cross-validation",
  "https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf",
  "https://arxiv.org/pdf/2008.08004",
  "https://www.sciencedirect.com/science/article/pii/S0306261921004529",
  "https://www.nber.org/papers/w33156",
  "https://onlinelibrary.wiley.com/doi/10.1002/jae.70018",
  "https://onlinelibrary.wiley.com/doi/full/10.1111/ecin.70009",
  "https://www.sciencedirect.com/science/article/abs/pii/S0140988318302913",
  "https://www.mdpi.com/2227-9091/5/3/48",
  "https://registry.opendata.aws/noaa-gefs-reforecast/",
  "https://noaa-gefs-retrospective.s3.amazonaws.com/Description_of_reforecast_data.pdf",
  "https://ebwanalytics.com/methodology",
  "https://natgasweather.com/",
  "https://gasalpha.com/",
  "https://www.celsiusenergy.net/p/weather-data.html",
  "https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10168449"
 ]
}
```

## LENS: Volatility and options for Henry Hub natural gas — IV term structure and seasonality, the Samuelson effect, EIA-print event volatility, realized-vs-implied and the variance risk premium, skew and its 

```json
{
 "domain": "Volatility and options for Henry Hub natural gas — IV term structure and seasonality, the Samuelson effect, EIA-print event volatility, realized-vs-implied and the variance risk premium, skew and its seasonal sign, and distribution/dispersion forecasting (ensembles, fan charts) as it maps to option-tradeable dispersion.",
 "signals": [
  {
   "name": "Seasonally-decomposed IV term structure (Samuelson decay x seasonal factor x event calendar)",
   "what_it_measures": "Splits the NG implied-vol curve into the three parts that are mechanically knowable (time-to-expiry decay, calendar-month seasonal, scheduled-event bumps) and the residual, which is the only part carrying a view. The structural form is sigma(t,T) = theta(t) * exp(-beta*(T-t)) with theta seasonal: Schneider & Tavin (2015) give conditions under which the seasonal CIR/Heston vol factor is well-defined and show the model reproduces a smile AND a Samuelson term structure with a seasonal component simultaneously.",
   "source": "Build from the desk's own NG option settlements (CME publishes daily option settlement prices free). Model form: Schneider & Tavin arXiv:1506.05911; Back, Prokopczuk & Rudolf (2013) JBF 37(2):273-290 'Seasonality and the valuation of commodity options' (finds deterministic seasonal vol materially improves valuation in corn, soybean, heating oil and natural gas).",
   "cost": "free",
   "horizon": "The SHAPE is knowable months to a year out (it is deterministic); the LEVEL is a 1-2wk object.",
   "skill_limit": "Two published limits. (1) Schneider & Tavin is a theoretical/illustrative calibration - it supplies no fitted gas parameter values, so beta and theta must be estimated in-house. (2) The decomposition is not point-identified: the event-vol extraction requires a prior guess of the event move size and is iterative, not deterministic (Moontower shows 5%/6.5%/8% assumed moves produce materially different 'cleaned' curves).",
   "why_practitioners_use_it": "Because the raw term structure is mostly artifact. Moontower's statement of the trade: 'If your 1 year future trades at the same implied vol as your 1 month future despite the fact that the 1 year future is moving less, [that] means that the market is implying more variance in the coming months.' Only the residual after de-Samuelsonizing and de-seasonalizing is a signal.",
   "we_already_have_it": "partial"
  },
  {
   "name": "CME CVOL for Henry Hub (NGVL) plus UpVar / DnVar / Skew / ATM / Convexity",
   "what_it_measures": "30-day implied volatility from the full OTM strip on HH options, computed on SIMPLE (normal) variance rather than log variance. UpVar uses OTM calls only, DnVar OTM puts only; Skew is published both as a difference (UpVar - DnVar, negative = puts richer) and a ratio (UpVar/DnVar, <1.0 = puts richer). Convexity is the separate wing-richness measure.",
   "source": "CME Group Benchmark Administration. Symbols CVOL:NGVL, UPVAR:NGVL, DNVAR:NGVL, SKEW:NGVL, ATMVOL:NGVL, CONVEX:NGVL. Live streaming via CME Direct and ISVs; end-of-day published daily via CME DataMine.",
   "cost": "mixed",
   "horizon": "30-day constant maturity; a level/state variable, not a forecast.",
   "skill_limit": "Normal-variance construction means CVOL is NOT numerically comparable to VIX-style log-variance indices or to your own Black-76 surface - do not mix them in one series. History is distributed through CME DataMine (licensed); the free web dashboard is current-value only, so a backtestable history is a paid gap. It is a measured level, so it carries no independent forecast skill beyond what your own surface already contains.",
   "why_practitioners_use_it": "It is the exchange's own benchmark on its own book, so it is the reference every counterparty quotes against; and the UpVar/DnVar split is a ready-made, consistently-computed seasonal skew series that removes the need to fit your own wings.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Cboe US Natural Gas ETF Volatility Index (VXUNG)",
   "what_it_measures": "30-day VIX-methodology implied volatility on UNG options - a free, long-history, publicly-quoted NG vol level.",
   "source": "Cboe Global Indices (VXUNG). Cboe publishes volatility-index history free.",
   "cost": "free",
   "horizon": "30d.",
   "skill_limit": "It is on an ETF, not on Henry Hub futures. UNG carries roll drag, so VXUNG is distorted in steep contango and around each monthly roll; its level is systematically offset from HH front-month IV and the offset is regime-dependent. Use it as a backfill/cross-check for regime dating, never as the pricing input. Cboe has a history of decommissioning and relaunching its commodity-ETF vol indices (VXGDX was decommissioned Feb 2022, relaunched Nov 2025), so continuity is not guaranteed.",
   "why_practitioners_use_it": "Free, long, no licence - the cheapest way to date vol regimes and sanity-check an in-house surface without paying for CVOL history.",
   "we_already_have_it": "no"
  },
  {
   "name": "EIA Thursday-print event variance (the Wed-to-Thu vol crush)",
   "what_it_measures": "The discrete variance the option market attributes to the 10:30 ET Thursday storage release, isolated from ambient diffusive variance. Extract by variance additivity: (IV_span)^2 * DTE_total = (IV_noevent)^2 * DTE_ambient + (IV_event)^2 * 1, then convert to an expected move (daily vol = annualized/16; straddle ~ 0.8 * daily vol).",
   "source": "Own NG option settlements across expiries that do and do not span the print. Published corroboration: 'A state-preference volatility index for the natural gas market', Energy Economics 104 (2021) - NGVX 'decreases significantly from Wednesday to Thursday, when the weekly storage report is released'. Mu (2007) Energy Economics, 'Weather, storage, and natural gas price dynamics': conditional volatility is materially higher on the storage-report day.",
   "cost": "free",
   "horizon": "0-3d.",
   "skill_limit": "Zhong (2026, arXiv:2606.12872) is the sharp methodological warning: a flexible no-event surface fitted on event-SPANNING quotes will absorb the event premium and the scheduled jump becomes unidentified. The no-event surface must be fitted only on non-spanning expiries. Second limit from the same paper: what the event bump identifies is scheduled-event VARIANCE and CONVEXITY - not directional event skew. Third: Mu (2007) finds the storage-announcement effect is itself DRIVEN BY WEATHER, so the event premium is not a fixed constant to be learned once; it is conditional on the weather state.",
   "why_practitioners_use_it": "It is the single largest scheduled dispersion event in the gas week and it is on a known clock, so it can be priced rather than forecast. For a desk pricing Kalshi daily contracts this is the highest-value derived object in the whole domain: it tells you how much of Thursday's expected range is event and how much is ambient.",
   "we_already_have_it": "no"
  },
  {
   "name": "NG Weekly options (Monday/Tuesday/Wednesday/Thursday/Friday expiries) settle IVs",
   "what_it_measures": "The listed market's own price of a ONE-TO-FIVE-DAY price distribution on Henry Hub - i.e. exactly the object a Kalshi daily contract settles on. The Wednesday and Thursday weeklies bracket the EIA print directly.",
   "source": "CME Henry Hub Natural Gas Weekly options. CME states these expire Monday, Tuesday, Wednesday and Thursday with the same specs and exercise procedures as the existing Friday weeklies. Daily settlement prices free from CME.",
   "cost": "free",
   "horizon": "0-5d.",
   "skill_limit": "Could not verify the individual Globex product codes (CME pages timed out repeatedly) - confirm before wiring. The real limit is liquidity: OI concentrates near ATM and the wings are thin, so an extracted short-dated smile is unreliable away from the money. Related published limit: stochastic-volatility models without jumps FLATTEN the smile as maturity goes to zero, whereas actual short-dated data steepens - so a pure-SV fit will systematically misprice the weekly wings.",
   "why_practitioners_use_it": "CME markets them explicitly to 'precisely manage volatility surrounding events like EIA reports'; desks use them to isolate the print without carrying month-long vega. For this desk they are the direct listed comparable to the Kalshi daily book - the arbitrage/reference leg.",
   "we_already_have_it": "no"
  },
  {
   "name": "Variance risk premium in natural gas, seasonally conditioned",
   "what_it_measures": "Realized variance minus the model-free implied variance (synthetic variance swap rate). In gas it is the LARGEST in the commodity complex and also the most dangerous.",
   "source": "Prokopczuk & Wese Simen (2014), 'Variance Risk Premia in Commodity Markets', 21 commodities 1989-2011 (NG: Oct 1992 - Sep 2011, 4,394 obs). Trolle & Schwartz (2010), 'Variance Risk Premia in Energy Commodities', Journal of Derivatives 17(3):15. Build in-house from own surface + own tape.",
   "cost": "free",
   "horizon": "Measured at 60-day and 90-day horizons. It is a horizon-scale object, not a daily one.",
   "skill_limit": "This is the most important debunk-adjacent number in the domain. NG 60-day VRP mean is -10.2% (t = -9.24), median -7.3% - three times crude's -3.4% and the largest of 21 commodities. But: NG VRP std dev is 15%, an order of magnitude above the <7% typical of other commodities; skewness -1.61; MINIMUM -166% (one observation lost 1.66x notional). Log-VRP Sharpe 47% at 60d falls to 34.9% at 90d. Trolle & Schwartz put the annualized Sharpe from shorting NG variance at 0.35 vs 0.59 crude vs 1.02 S&P 500 - the WORST risk-adjusted in energy - and note the NG variance-swap return profile 'resembles that of a call option' (i.e. short gas variance is structurally short a call: it bleeds and then detonates). Both papers state the level and variation are hard to explain with systematic or commodity-specific factors.",
   "why_practitioners_use_it": "It sizes how much you are being paid to supply dispersion, and the seasonality tells you when. Prokopczuk cites Suenaga, Smith & Williams (2008) JFM 28(5):438-463 for realized-variance seasonality in gas; NG variance and its premium both peak in the cold months.",
   "we_already_have_it": "no"
  },
  {
   "name": "25-delta risk reversal / skew with its SEASONAL SIGN FLIP",
   "what_it_measures": "25d call IV minus 25d put IV by seasonal strip. The sign flips with the storage cycle: winter strips (Nov-Mar) sit in CALL skew; the summer strip (Apr-Oct) routinely moves into PUT skew.",
   "source": "Aegis Hedging market insights (measures 25d call vs 25d put by strip; example marks Summer-1 Apr26-Oct26 swap $3.829 vs Winter-1 Nov26-Mar27 $4.415). Free alternative series: CME SKEW:NGVL (UpVar-DnVar and UpVar/DnVar). Own strike ladder.",
   "cost": "mixed",
   "horizon": "Seasonal / 2-4wk for changes in level.",
   "skill_limit": "The published sources do NOT quantify the skew in vol points - Aegis gives sign and direction only. More important: the structural cause is HEDGING FLOW, not forecast - utilities and producers buy OTM winter calls because the cost of a spike exceeds the premium, and that persistent bid keeps call IV structurally above put IV. So a positive skew reading is not evidence of an expected up-move; it is evidence of who is hedging. CME itself frames directional predictiveness as an open question ('CVOL Skew Ratio: CAN options offer useful insights on market direction?'), not an established result. Treat level as flow, only CHANGES vs the seasonal norm as information.",
   "why_practitioners_use_it": "It prices the asymmetry, which is what makes a forward path tradeable in options at all: a right path with wrong dispersion shape still loses. The seasonal sign flip is the cleanest structural regularity in the gas surface.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Weather ENSEMBLE MEMBER spread mapped to a GWDD density (not two-model disagreement)",
   "what_it_measures": "The full member-level distribution of gas-weighted degree days, built by pushing every ensemble member through the GWDD weighting and reading off the resulting demand density. Ensemble members are used to produce demand scenarios which then ARE the uncertainty estimate - this is the direct, physical source of price dispersion.",
   "source": "NOAA GEFS - free, global, 4x daily, out to 16 days, 6-hour temporal resolution (NCEI / NOMADS). ECMWF ENS (51 members) - increasingly available under ECMWF open data, full res paid. Canonical method: Taylor & Buizza, density forecasting for weather-derivative pricing (Oxford), the standard ensemble-to-degree-day-density construction.",
   "cost": "free",
   "horizon": "0-15d, with the usable band 0-10d and a degraded 11-15d.",
   "skill_limit": "THE binding number for this desk. Coupled GEFS ensemble mean gives a useful skilful forecast of NEARLY 10 DAYS at the 60% anomaly-correlation threshold (NOAA repository, coupled-GEFS uncertainty study) - coupling buys only 6-12 additional HOURS. Climate Impact Company's 30-day rolling US 2m-temperature skill scoring finds ECM ENS and AIFS ENS best in both the 6-10 day and 11-15 day windows with GFS lagging badly; beyond ~15 days only weather-REGIME probabilities survive, not degree-day levels. So: a dispersion forecast has physical support to ~10 days, is weak to 15, and past that you are pricing climatology.",
   "why_practitioners_use_it": "It is the only forward-looking dispersion input that is causal rather than inferred from prices. A single deterministic MOS run gives you a path; the member spread gives you the fan, and the fan is what maps to option dispersion.",
   "we_already_have_it": "partial"
  },
  {
   "name": "4-model consensus GWDD with published model spread",
   "what_it_measures": "GWDD consensus across GFS, ECMWF IFS, GEFS and AIFS, plus the explicit inter-model spread (e.g. 'GFS vs IFS Spread: 2.6 GWDDs') and run-to-run model trend.",
   "source": "GasAlpha (gasalpha.com) - four models, updated 4x daily at 05z/09z/13z/21z, 10-day and 14-day windows, plus historical ranking vs prior years. World Climate Service Trading Markets application (paid) for gas-weighted and population-weighted DD forecasts.",
   "cost": "mixed",
   "horizon": "10-14d.",
   "skill_limit": "Publishes no quantitative GWDD-to-price or GWDD-to-Bcf conversion - the multiplier is left to the user, and it is regime-dependent (that is exactly the failure mode this desk already logged where a correct CDD add was offset by a 62% wind rise). Free-tier continuity is not contractual. Model spread between two deterministic runs is a WEAKER uncertainty measure than true ensemble member spread - use it as a cross-check, not as the density.",
   "why_practitioners_use_it": "It is the same 4-model consensus professional gas forecasters use, free, with the disagreement metric already computed and the historical ranking that tells you whether today's GWDD is extreme in context.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Samuelson maturity effect as a mechanical, weather-free vol forecast",
   "what_it_measures": "The deterministic rise in futures-price volatility as expiry approaches. Gives a 1-4 week forecast of the front contract's vol with NO market view required.",
   "source": "Samuelson (1965); 'In Pursuit of Samuelson for Commodity Futures: How to Parameterize and Calibrate the Term Structure of Volatilities' (MDPI Commodities 4(3):13, 2025); Gregoire & Boucher (2008) using an extreme-value (high-low) volatility estimator on NG.",
   "cost": "free",
   "horizon": "1-4wk, deterministic.",
   "skill_limit": "Two published constraints. (1) Gregoire & Boucher find the maturity effect in gas is SEASONALLY ASYMMETRIC and PRESENT ONLY DURING WINTER - applying a single Samuelson decay year-round will over-forecast injection-season front-month vol. (2) The effect is 'especially pronounced for energy contracts, with a particularly steep increase in the last months of the life of the contract' - it is non-linear, so a linear-in-DTE parameterization fails exactly where it matters. Moontower adds that Samuelson strength varies with the degree of backwardation or contango, so the decay parameter is itself regime-conditional.",
   "why_practitioners_use_it": "It is free forecast skill that requires no fundamental view, and it is the reason deferred-month IV is NOT a statement about deferred-month expectations.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Weather-shock and storage-surprise conditioned conditional variance (GARCH-X)",
   "what_it_measures": "Volatility conditioned on measured fundamentals rather than on its own lags. Mu (2007) uses deviation of temperature from normal (the weather surprise) plus the storage surprise as conditional-variance regressors.",
   "source": "Mu (2007), 'Weather, storage, and natural gas price dynamics: Fundamentals and volatility', Energy Economics; daily NG futures Jan 1997 - Dec 2000. All inputs are already on this desk.",
   "cost": "free",
   "horizon": "0-1wk.",
   "skill_limit": "Measured effect sizes are real but modest: a one-standard-deviation increase in the weather-shock variable raises average daily variance by only 4-5%. The economically bigger result is that adding weather shock + storage surprise cuts volatility PERSISTENCE by roughly 40% - i.e. most of what a plain GARCH calls persistence is unmodelled fundamentals. Critical caveat for calendar signals: Mu finds the elevated 'Monday effect' and 'storage announcement effect' are BOTH DRIVEN BY WEATHER, so neither survives as a standalone day-of-week rule. Sample is 1997-2000 - pre-shale, pre-LNG-export; the coefficients should be re-estimated, not imported.",
   "why_practitioners_use_it": "It converts a weather view directly into a dispersion view without going through price, which is the only way to have an options-tradeable opinion that is not just a repackaged directional bet.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Two-factor variance term structure (the hump)",
   "what_it_measures": "The shape of the variance curve across maturities. One variance factor cannot reproduce the humps that gas variance curves actually show; two can.",
   "source": "Shao, Colwell, Sheng & Wei, 'Variance dynamics and term structure of the natural gas market', Energy Economics, July 2024. Built on variance swap rates synthesized from NG option prices over 20+ years; model carries two variance factors, the Samuelson effect and seasonality with a linearly analytic pricing formula.",
   "cost": "free",
   "horizon": "Weeks to months (a term-structure object).",
   "skill_limit": "The demonstrated gain is in FITTING and in HEDGING natural gas straddles - not in forecasting the vol level. It tells you the right shape to interpolate and hedge along; it does not tell you where vol is going. Two factors are specifically needed for the humps, so a single-factor or flat-seasonal fit will misprice the mid-curve where the hump sits.",
   "why_practitioners_use_it": "If you are going to trade a forward PATH in options you need the whole variance curve, not a point; and the hump is where a one-factor fit leaks the most money.",
   "we_already_have_it": "no"
  },
  {
   "name": "Unspanned stochastic volatility (a structural constraint, not a tradeable signal)",
   "what_it_measures": "The degree to which gas volatility risk CANNOT be hedged or inferred from futures positions alone.",
   "source": "Trolle & Schwartz (2009), 'Unspanned Stochastic Volatility and the Pricing of Commodity Derivatives', Review of Financial Studies 22(11):4423 / NBER w12744 - estimated on 45,517 futures prices and 233,104 option prices over 4,082 business days, finding strong evidence for two predominantly unspanned volatility factors. Corroborated in commodities generally by Prokopczuk & Wese Simen: 'commodity variance risk premia are distinct from price risk premia, indicating that variance risk is unspanned by commodity futures.'",
   "cost": "free",
   "horizon": "Structural - always on.",
   "skill_limit": "The Trolle-Schwartz estimation is on CRUDE, not gas; the gas claim rests on the commodity-wide Prokopczuk result. The practical limit it imposes: no amount of term-structure, calendar-spread or tape work will give you the vol state - you must buy or build the options surface. It also means your existing futures-derived signals cannot be back-tested as vol forecasts.",
   "why_practitioners_use_it": "It is the reason an options desk exists separately from a futures desk. For this desk it is the argument that the vol lane genuinely needs its own data, not a derivative of the price lane.",
   "we_already_have_it": "unclear"
  },
  {
   "name": "Calendar spread option (CSO) implied distribution — the March/April 'widowmaker'",
   "what_it_measures": "The market-implied probability distribution of the H/J (March/April) spread, i.e. the price of the withdrawal-to-injection season transition. CSOs exercise into a long near-month / short deferred-month futures pair.",
   "source": "CME NG Calendar Spread Options; daily settlements free. Practitioner read-through: Moontower, 'What The Widowmaker Can Teach Us About Trade Prospecting And Fool's Gold'.",
   "cost": "free",
   "horizon": "Seasonal (months), with the informative window late winter.",
   "skill_limit": "This is the cleanest documented case of a distribution that LOOKS mispriced and is not. Moontower's worked example: with the spread trading $1.44, CSO pricing implied roughly a 3% chance of settling near $2, 2% near $3, and ZERO above that - while historically 'the spread almost always settles at zero' because when H expires it is basically at the same price as J. Conclusion: fat call premiums are 'a sucker bet' and 'upside butterflies are zeros'. The market 'appreciates path while never giving you great odds on making money on the terminal value of the options'. Also: H implied vol can run so far above J vol that it swamps the one-month time difference, so standard vol-vs-time intuition breaks entirely here.",
   "why_practitioners_use_it": "It is the market's own explicit statement of a bounded, one-sided distribution - and the single best available calibration check on whether your own path-distribution machinery is producing sane tails.",
   "we_already_have_it": "no"
  },
  {
   "name": "Jump-robust realized variance from the in-house MBO tape (jump vs diffusive split)",
   "what_it_measures": "Decomposes realized variance into a continuous component and a jump component, so implied variance can be compared to the right thing. Extreme-value (high-low) estimators are the published gas-specific choice.",
   "source": "The desk's own full NYMEX NG tick/MBO tape. Method precedent: Gregoire & Boucher (2008) measured daily NG volatility from daily low and high prices and found the maturity effect significant even after controlling for storage surprises; the 2024 Energy Economics variance-term-structure work synthesizes variance swap rates from options and compares against realized.",
   "cost": "free",
   "horizon": "0-2wk (an input, not a forecast).",
   "skill_limit": "Realized-variance estimators are sensitive to the sampling clock and to microstructure noise; on a tape with the roll and off-instrument problems this desk has already documented, a wrong-leg RV will look perfectly well-formed. Also, the published literature notes commodity SV models WITHOUT jumps fail out-of-sample and that the short-maturity smile steepens in data while SV models flatten it - so the jump component is not optional at the daily/weekly horizon this desk trades.",
   "why_practitioners_use_it": "Because the entire VRP and event-vol program is only as good as its realized-variance denominator, and close-to-close RV throws away most of the information a full tape already contains.",
   "we_already_have_it": "partial"
  },
  {
   "name": "NG option volume and open interest flow by strike (positioning, not price)",
   "what_it_measures": "Where premium is being bought and sold - the flow that actually creates the seasonal call skew.",
   "source": "CME daily volume and open interest reports, free. Historical option volume is also published in CME's monthly volume reports (Prokopczuk uses exactly this to rank commodity option liquidity: NG averaged ~26.0m contracts/yr in 2010-2011, second only to crude at ~35.9m, and NG carried the deepest OTM strike coverage in the sample at 51 calls / 27 puts per day).",
   "cost": "free",
   "horizon": "0-2wk.",
   "skill_limit": "This is where it stops working: there is NO public dealer/customer classification in NYMEX options. You can see volume and OI, you cannot see the SIGN of dealer inventory, so 'dealer gamma' constructions in gas are inference, not measurement - unlike SPX where OCC/exchange data supports it. Anyone quoting a gas dealer-gamma level is modelling, not observing.",
   "why_practitioners_use_it": "Skew and wing richness in gas are flow phenomena (pre-winter utility/producer call buying); the flow is the mechanism, so watching OI build at specific winter strikes explains the surface better than any model of it.",
   "we_already_have_it": "partial"
  },
  {
   "name": "NGVX — state-preference implied volatility index",
   "what_it_measures": "An ex-ante, forward-looking risk-neutral one-month volatility estimate for NG built by identifying hidden state prices and payoffs from NYMEX NG futures options — a computationally simpler alternative to VIX-style replication.",
   "source": "'A state-preference volatility index for the natural gas market', Energy Economics 104 (2021), Macquarie. Buildable in-house from the desk's own strike ladder.",
   "cost": "free",
   "horizon": "1 month ahead.",
   "skill_limit": "Published claim is that NGVX beats conventional volatility estimators in and out of sample and is an unbiased consensus estimate of future uncertainty — but the comparison set is conventional statistical estimators, not a well-specified two-factor seasonal model, so the margin over a properly seasonalized in-house surface is unestablished. It is also a one-month object and says nothing about the 0-5 day distribution this desk actually trades on Kalshi.",
   "why_practitioners_use_it": "Less data-hungry and less sensitive to strike truncation than VIX-style replication, which matters in gas where far wings are thin. Its documented Wed-to-Thu decline is also a clean, independent confirmation of the EIA event-vol crush.",
   "we_already_have_it": "no"
  },
  {
   "name": "EIA published Henry Hub historical volatility series and methodology",
   "what_it_measures": "Annualized realized vol of the HH front-month, computed as the standard deviation of the previous quarter's daily changes x sqrt(252) x 100.",
   "source": "EIA Today in Energy (id=65784) and the STEO natural gas section.",
   "cost": "free",
   "horizon": "Backward-looking (quarterly window).",
   "skill_limit": "EIA publishes the CHART and the methodology but the underlying series is Bloomberg-sourced — there is no free downloadable EIA volatility series, so this is a reference point and a methodology, not a feed. The quarterly window is far too slow for a 1-2 week trading horizon and will lag every regime change. Levels for context: Q4 2024 81%, falling to 69% by mid-2025; 30-day vol peaked at 102% on 3 Feb 2025.",
   "why_practitioners_use_it": "It is the publicly-agreed definition of 'gas vol', so it anchors what a counterparty or a research note means by a number. Useful for regime dating and for arguing about levels, not for pricing.",
   "we_already_have_it": "partial"
  },
  {
   "name": "Seasonal vol REGIME classification (withdrawal vs injection) as a conditioning variable on every percentile",
   "what_it_measures": "Which of the two structural vol regimes you are in: withdrawal season Nov-Mar (the X-H strip, traded as a block, peak depletion risk in March) versus injection season Apr-Oct (the J-V strip, peak supply risk in October).",
   "source": "Practitioner framing from Moontower's seasonal volatility piece; corroborated by CME education material and by the NGVX paper ('NGVX increases as demand for heating (cooling) rises in winter (summer)').",
   "cost": "free",
   "horizon": "Seasonal; the regime boundary itself is the tradeable date.",
   "skill_limit": "Winter realized vol averages in the low 50s (%) with occasional far-higher spikes (2014 polar vortex), and forward winter contracts have printed in the upper 50s. But the practitioner warning attached is explicit: percentile and rank metrics MUST be conditioned on season or they are meaningless — an unconditional vol percentile will call every November 'high' and every May 'low' and produce a pure calendar signal dressed as an edge. Also note gas is now bimodal, not unimodal: summer is the second most volatile season because of power burn, and practitioners expect HH volatility to RISE in 2026 with LNG feedgas demand — an unmeasured forward claim, not an established fact.",
   "why_practitioners_use_it": "Every other measure in this domain — skew sign, VRP magnitude, Samuelson strength, event premium — is conditional on this variable. It is the top-level split before any of the rest is computed.",
   "we_already_have_it": "partial"
  }
 ],
 "skill_horizon_notes": "The single most useful finding for your binding open question is an ASYMMETRY: in gas, DISPERSION is forecastable materially further out than DIRECTION, and for a different reason.\n\n1. The physical/weather ceiling on DIRECTION is roughly 10 days. The coupled-GEFS study puts useful ensemble-mean skill at \"nearly 10 days\" against a 60% anomaly-correlation threshold, and coupling buys only 6-12 additional hours. Climate Impact Company's rolling 30-day scoring finds ECM ENS and AIFS ENS still adding value in both the 6-10 and 11-15 day windows (GFS lagging badly), but past ~15 days only weather-REGIME probabilities survive, not degree-day levels. So your two-week outer bound is at the edge of physical support, and the 11-15 day leg of it is a probability statement, not a level statement.\n\n2. DISPERSION carries much further because most of the gas vol curve is DETERMINISTIC, not forecast. Three components are knowable in advance with no market view at all: the Samuelson decay (mechanical in time-to-expiry), the calendar-month seasonal (winter high, injection low, with a second summer power-burn hump), and the scheduled-event calendar (the Thursday EIA print, expiry, opex). Schneider & Tavin show a model can produce a smile and a seasonal Samuelson term structure simultaneously; Shao et al. (2024) show you need TWO variance factors to reproduce the humps in the real variance curve. That means you can put a defensible number on the vol of a session two-to-four weeks out without any weather opinion — which is exactly what you cannot do for the level.\n\n3. The horizons at which each thing has been MEASURED are specific and should bound your claims. VRP: measured at 60 and 90 days (Prokopczuk & Wese Simen; Trolle & Schwartz) — it is a horizon-scale object, and daily VRP is not what those papers established. Event variance: a 0-3 day object (the Wed-to-Thu NGVX crush). Weather-shock conditional variance: Mu's effects are same-week. Samuelson: 1-4 weeks, but seasonally asymmetric (Gregoire & Boucher find the maturity effect in gas present ONLY in winter). Skew sign: seasonal/structural.\n\n4. The identification trap that bounds ALL of this. Zhong (2026) proves the point formally on SPX and it transfers: if you fit your ambient/no-event volatility surface using quotes from expiries that SPAN the event, the surface silently absorbs the event premium and the event jump becomes unidentified — and it will look like a good fit while doing so. Your no-event surface must be estimated only on non-spanning expiries. The same paper's second result matters for how you use the output: scheduled-event pricing identifies event VARIANCE and CONVEXITY, not directional event skew. So the EIA print can tell you how wide Thursday will be; it cannot tell you which way.\n\n5. Variance is additive, volatility is not. That is the operational bridge from your path forecast to a tradeable distribution: build the two-week fan by summing per-day variance contributions (ambient x n_days + event variance on print days + weekend/holiday day-weighting), not by scaling a single annualized vol. The corollary is that a two-week distribution can be built even where the two-week DIRECTION is unforecastable — the fan is legitimate at 14 days even when the centre is not.\n\n6. Volatility is UNSPANNED. Trolle & Schwartz (RFS 2009) find two predominantly unspanned vol factors in energy; Prokopczuk finds commodity variance risk premia are statistically distinct from price risk premia. Nothing in your futures curve, calendar spreads, COT or tape recovers the vol state. If you want to trade dispersion you must carry an options surface — it is not derivable from what you already have.",
 "debunked_or_folklore": [
  "THE IV/RV RATIO ACROSS A SEASON BOUNDARY IS MEANINGLESS — and this is the most common gas vol error. Moontower's worked case: one-month implied 49% against one-month trailing realized 86% looks like implied is absurdly cheap. It is not. 'You are comparing a forward-looking numerator to a backwards-looking denominator. As we change seasons, nobody expects the recent bout of volatility to repeat in the next month.' Any IV/RV screen in gas must compare implied for period X to realized for the SAME CALENDAR PERIOD in prior years, never to trailing realized.",
  "'DEFERRED-MONTH IV IS LOWER, SO FAR-DATED GAS VOL IS CHEAP.' This is a pure Samuelson artifact. Deferred contracts move less because they are deferred; low deferred IV is the mechanically correct price, not an opportunity. The correct read is the inverse and non-obvious one: if the 1-year future trades at the SAME implied vol as the 1-month despite moving less, the market is implying MORE variance in the coming months.",
  "'GAS CALL SKEW IS A BULLISH DIRECTIONAL SIGNAL.' The persistent winter call skew has a documented structural cause that has nothing to do with forecasts: utilities and producers buy OTM winter calls because the cost of exposure to a spike far exceeds the premium, and that standing bid keeps call IV structurally above put IV. It is hedging FLOW. CME's own research frames directional predictiveness as a question ('CAN options offer useful insights on market direction?'), not a finding. Only DEVIATIONS from the seasonal skew norm are candidate information; the level is not.",
  "'SELL GAS VARIANCE — THE VRP IS THE BIGGEST IN COMMODITIES.' Both halves of this are true and the conclusion is still wrong. NG 60-day VRP is -10.2% (t=-9.24), three times crude's -3.4% and the largest of 21 commodities. But its standard deviation is 15% — an order of magnitude above the sub-7% typical elsewhere — skewness is -1.61, and the MINIMUM observation is -166% of notional. Trolle & Schwartz put the annualized Sharpe from shorting NG variance at 0.35 versus 0.59 for crude and 1.02 for the S&P — the worst risk-adjusted short-vol trade in energy — and observe the NG variance-swap return profile 'resembles that of a call option', i.e. you are structurally short a call. Big premium, terrible payoff shape.",
  "THE 'WIDOWMAKER' UPSIDE CALL / BUTTERFLY AS A CHEAP LOTTERY. Documented as a sucker bet. With the H/J spread at $1.44, calendar-spread-option pricing implied ~3% of settling near $2, ~2% near $3, and ZERO above — while historically the spread almost always settles at zero, because when March expires it is basically at April's price. Moontower: 'upside butterflies are zeros'; the market 'appreciates path while never giving you great odds on making money on the terminal value'. A distribution that is fat in PATH and thin in TERMINAL VALUE is the general trap here, and it applies to any spike-hunting structure in gas.",
  "THE 'MONDAY EFFECT' AND THE 'STORAGE-DAY EFFECT' AS STANDALONE CALENDAR RULES. Mu (2007) does find conditional volatility considerably higher on Mondays and on storage-report day — but explicitly finds both are DRIVEN BY WEATHER. They are not day-of-week effects; they are weather-arrival effects that happen to cluster on those days. A calendar dummy will fit in-sample and fail whenever weather arrival decouples from the calendar.",
  "UNCONDITIONAL VOL PERCENTILES AND RANKS. Any percentile screen not conditioned on season is a calendar signal wearing a statistics costume: it will call every November high and every May low. Moontower is explicit that percentile metrics must be conditioned on season, and additionally that Samuelson strength itself varies with the degree of backwardation or contango — so even the maturity adjustment is regime-conditional.",
  "APPLYING ONE SAMUELSON DECAY YEAR-ROUND. Gregoire & Boucher (2008), using an extreme-value estimator and controlling for storage surprises, find the gas maturity effect is seasonally ASYMMETRIC and present ONLY during winter. A single year-round decay parameter will systematically over-forecast injection-season front-month vol.",
  "PURE STOCHASTIC-VOLATILITY MODELS FOR SHORT-DATED GAS OPTIONS. A known and published deficiency: as maturity goes to zero, SV models FLATTEN the implied smile, whereas actual data becomes MORE pronounced. Since the daily/weekly tenor is precisely where this desk operates (Kalshi dailies, NG weeklies), an SV fit without jumps will be wrong exactly where you need it. Jump-augmented models (e.g. the MRSVJS specification) are documented to significantly improve out-of-sample option pricing in Henry Hub.",
  "'DEALER GAMMA' IN NATURAL GAS. There is no public dealer/customer classification in NYMEX options — CME publishes volume and OI but not the sign of dealer inventory. Any gas dealer-gamma level being quoted is a model output presented as an observation. The equity-index analogy does not carry over.",
  "MIXING CVOL WITH A BLACK-76 SURFACE. CVOL is built on SIMPLE (normal) variance while VIX-style indices and most in-house surfaces use log variance. The two are not numerically comparable and blending them into one history produces a series with an artificial structural break.",
  "VXUNG AS A HENRY HUB VOL SERIES. It is computed on UNG, an ETF with roll drag; its offset from HH front-month IV is regime-dependent and worst in steep contango and around each roll. Fine for regime dating, wrong as a pricing input."
 ],
 "gaps_vs_our_stack": [
  "1. WEATHER ENSEMBLE MEMBER SPREAD AS A GWDD DENSITY (highest EV). You have MOS deterministic forecast temps and a model-disagreement measure — you do NOT appear to have the member-level distribution. This is the only causal, forward-looking dispersion input available and it is FREE (NOAA GEFS, 4x daily, 16 days, 6-hour, via NOMADS/NCEI). Push every member through your existing GWDD weighting and read off the density; the width of that density IS your option dispersion input. Method precedent: Taylor & Buizza density forecasting for weather derivatives. It also directly addresses your recorded 0629 failure — a fan would have shown the CDD add was inside the noise while the wind-driven burn miss was not.",
  "2. NG WEEKLY OPTIONS (Mon/Tue/Wed/Thu expiries) SETTLE IVs. Your surface is presumably monthlies. The weeklies are the LISTED price of a one-to-five-day Henry Hub distribution — which is exactly the object your Kalshi daily contracts settle on. This is the direct comparable and reference leg for the entire Kalshi lane, and it is free from CME settlements. Verify the Globex codes before wiring (CME pages were unreachable during this research).",
  "3. EIA-PRINT EVENT VARIANCE, EXTRACTED UNDER THE NON-SPANNING RULE. Decompose Thursday's variance into event and ambient via variance additivity across spanning and non-spanning expiries, with the no-event surface fitted ONLY on non-spanning expiries (Zhong 2026 — otherwise the surface absorbs the premium and the jump is unidentified). Corroborated independently by the NGVX Wed-to-Thu decline. This gives you a per-Thursday expected-move number that is a market price, not a forecast — and your desk already has a documented weakness on EIA Thursdays (G20's two EIA Thursdays were 3,530 of 7,880 total error).",
  "4. SEASONALLY-CONDITIONED VRP WITH THE CORRECT DENOMINATOR. You already own both inputs (settle-IV surface + realized-vol regime). What is missing is the derived measure computed correctly: implied for calendar period X against realized for the SAME calendar period historically, never against trailing realized. Size it with the published numbers (NG 60d -10.2%, std 15%, skew -1.61, min -166%, Sharpe 0.35) so the tail is respected before any short-vol exposure is taken.",
  "5. DE-SAMUELSONIZED, DE-SEASONALIZED VOL TERM STRUCTURE. Fit sigma(t,T) = theta(t)*exp(-beta*(T-t)) with beta estimated SEPARATELY for winter and injection season (Gregoire & Boucher: the effect is winter-only), then trade the residual. This turns your existing surface from a level into a signal, at zero data cost.",
  "6. CME CVOL NGVL SERIES (CVOL / UpVar / DnVar / Skew / ATM / Convexity). Ready-made, consistently-computed seasonal skew and wing series on the exchange's own book. Free at current value on the CME dashboard; a backtestable HISTORY requires CME DataMine — this is a genuine measured paid gap and probably the first thing worth paying for in this domain. Keep it in a separate series from your Black-76 surface (normal vs log variance).",
  "7. JUMP-ROBUST REALIZED VARIANCE OFF YOUR OWN MBO TAPE. You have the full tape and are almost certainly computing close-to-close RV. Split continuous from jump variance (and consider the extreme-value high-low estimator, which is what the gas-specific maturity-effect literature used). Every VRP and event-vol number you compute is only as good as this denominator, and the short-dated smile literature says the jump component is not optional at your tenor.",
  "8. CALENDAR SPREAD OPTION IMPLIED DISTRIBUTION (H/J and the seasonal strip boundaries). Free from CME settlements. Its unique value is as a CALIBRATION CHECK: it is a published, one-sided, bounded distribution with known historical settlement behaviour, so it will tell you immediately whether your path-distribution machinery produces sane tails or the fat-path/thin-terminal illusion.",
  "9. TWO-FACTOR VARIANCE TERM STRUCTURE FIT. Shao et al. (2024) show one factor cannot reproduce the humps in the real gas variance curve and that two factors measurably improve straddle hedging. If you intend to trade the forward PATH in options rather than a single tenor, a one-factor or flat-seasonal interpolation will leak most in the mid-curve.",
  "10. CBOE VXUNG for free long-history regime dating and backfill. Lowest effort item on this list. Use only for regime dating and cross-checking, never as a pricing input (UNG roll drag).",
  "11. NG OPTION VOLUME AND OI BY STRIKE. Free from CME daily reports. Explains the seasonal skew mechanically (pre-winter utility/producer call buying builds at identifiable strikes). Note the hard limit before investing: there is no dealer/customer classification in NYMEX options, so this supports flow observation but NOT dealer-gamma inference.",
  "12. WORLD CLIMATE SERVICE (paid) or equivalent for gas- and population-weighted DD ensembles with regime probabilities, if and only if the free GEFS/GasAlpha path proves insufficient. Worth measuring the free path first — GasAlpha already publishes a free 4-model consensus GWDD with an explicit inter-model spread, 4x daily, 10 and 14 day."
 ],
 "sources": [
  "https://www.cmegroup.com/market-data/cme-group-benchmark-administration/cme-group-volatility-indexes.html",
  "https://www.cmegroup.com/market-data/cme-group-benchmark-administration/files/cvol-methodology.pdf",
  "https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457326006/CVOL+End+of+Day+Index",
  "https://www.cmegroup.com/education/courses/introduction-to-cvol/introduction-to-cvol-skew",
  "https://www.cmegroup.com/insights/economic-research/2025/cvol-skew-ratio-can-options-offer-useful-insights-on-market-direction.html",
  "https://www.cmegroup.com/articles/2024/navigating-volatility-in-natural-gas-with-weekly-options.html",
  "https://www.cmegroup.com/articles/faqs/faq-natural-gas-weekly-options.html",
  "https://www.cmegroup.com/markets/energy/weekly-energy-options.html",
  "https://www.cmegroup.com/markets/energy/natural-gas/henry-hub-natural-gas-weekly.html",
  "https://www.cmegroup.com/education/courses/introduction-to-energy/introduction-to-natural-gas/natural-gas-calendar-spread-options",
  "https://moontowermeta.com/seasonal-volatility/",
  "https://moontowermeta.com/what-the-widowmaker-can-teach-us-about-trade-prospecting-and-fools-gold/",
  "https://blog.moontower.ai/how-an-option-trader-extracts-earnings-from-a-vol-term-structure/",
  "https://optionsoffice.ru/wp-content/uploads/2017/11/Marcel-Prokopczuk_Variance-Risk-Premia-in-Commodity-Markets.pdf",
  "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1160195",
  "https://infoscience.epfl.ch/record/148475/files/TrolleSchwartz_Energy_Variance_Risk_Premia.pdf",
  "https://jod.pm-research.com/content/17/3/15",
  "https://www.nber.org/papers/w12744",
  "https://academic.oup.com/rfs/article-abstract/22/11/4423/1568437",
  "https://www.sciencedirect.com/science/article/abs/pii/S0140988321004862",
  "https://www.sciencedirect.com/science/article/abs/pii/S0140988324004882",
  "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4575374",
  "https://www.sciencedirect.com/science/article/abs/pii/S0140988306000417",
  "https://iaee.org/en/students/best_papers/Xiaoyi_Mu2.pdf",
  "https://arxiv.org/pdf/1506.05911",
  "https://arxiv.org/pdf/1401.7913",
  "https://www.mdpi.com/2813-2432/4/3/13",
  "https://www.preprints.org/manuscript/202505.2487",
  "https://arxiv.org/pdf/2606.12872",
  "https://academic.oup.com/rof/article/29/4/963/8079062",
  "https://link.springer.com/article/10.1007/s10479-022-05128-x",
  "https://link.springer.com/article/10.1007/s11156-016-0569-x",
  "https://www.sciencedirect.com/science/article/abs/pii/S037842661600039X",
  "https://www.sciencedirect.com/science/article/abs/pii/S0140988314002254",
  "https://www.sciencedirect.com/science/article/abs/pii/S014098831630038X",
  "https://www.sciencedirect.com/science/article/abs/pii/S1042443122000543",
  "https://arxiv.org/pdf/1711.02925",
  "https://www.eia.gov/todayinenergy/detail.php?id=65784",
  "https://www.eia.gov/outlooks/steo/report/natgas.php",
  "https://www.eia.gov/naturalgas/storage/",
  "https://aegis-hedging.com/insights/natural-gas-option-skew-signals-bullish-bias",
  "https://naturalgasintel.com/news/henry-hub-price-volatility-in-2026-seen-rising-with-lng-feed-gas-demand-the-offtake/",
  "https://naturalgasintel.com/news/natural-gas-widow-maker-spread-flashes-calm-as-winter-supply-worries-ease/",
  "https://www.tradingview.com/symbols/CBOE-VXUNG/",
  "https://www.cboe.com/us/indices/indicesproducts/",
  "https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Selected_Broad_Based_Index_Equity_and_ETF_Volatility_Indices.pdf",
  "https://www.ncei.noaa.gov/products/weather-climate-models/global-ensemble-forecast",
  "https://repository.library.noaa.gov/view/noaa/55248/noaa_55248_DS1.pdf",
  "https://www.ecmwf.int/en/forecasts/quality-our-forecasts",
  "https://climateimpactcompany.com/u-s-medium-range-forecast-preferred-ecm-ens-is-hotter-than-aifs-ens-in-the-medium-range-2-2/",
  "https://gasalpha.com/",
  "https://www.worldclimateservice.com/trading-markets-application/",
  "https://www.worldclimateservice.com/2025/10/27/weather-regime-forecasts/",
  "https://users.ox.ac.uk/~mast0315/WeatherDerivative.pdf",
  "https://onlinelibrary.wiley.com/doi/full/10.1002/fut.22402",
  "https://gasfoundation.org/wp-content/uploads/2019/11/volstudych3.pdf"
 ]
}
```
