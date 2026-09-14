# GAS SIGNAL BRIEFING (SYNTHESIS ONLY) - S111, 2026-08-05

Six-lens research sweep, synthesis section only. The full version with all six lenses' verbatim
structured output is GAS_SIGNAL_BRIEFING_S111.md (344KB).

RESEARCH, NOT ADJUDICATED DOCTRINE. Nothing merged, nothing decided. Every number is a lead to
verify.

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