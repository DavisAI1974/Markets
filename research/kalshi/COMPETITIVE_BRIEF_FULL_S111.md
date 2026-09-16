# COMPETITIVE POSITIONING BRIEF - S111 (2026-08-05)

Source: five-lens scout (`who-we-are-up-against`, run wf_c8ed76ee-055), commissioned by Greg:
"trading is a little different now than it was when i was trading... i don't know what reasoning
and processes they use to trade off of. that would be good to research so we know what we're up
against." Six agents, 1.16M subagent tokens, 365 tool calls.

RESEARCH, NOT ADJUDICATED DOCTRINE. Nothing merged, nothing decided.

Lenses: participant map; systematic strategy taxonomy; how modern desks reason; where machines are
structurally weak; the prediction-market / Kalshi field.

---

# COMPETITIVE POSITIONING BRIEF
## Henry Hub natural gas: who we are trading against, and what business we are actually in

**Unit convention used throughout.** One NG contract = 10,000 MMBtu, so **$100 of day-move = 1.0 cent of gas ($0.01/MMBtu)**. Our internal forecast errors convert directly: a "sum|err| of 5,920 over ten days" is a **mean absolute error of 5.9 cents of gas per day**. Keep that conversion in mind; it is what makes the rest of this brief decidable.

---

## 1. WHO IS ON THE OTHER SIDE

**The NYMEX participant map is a ~330-firm club, and it is not the club people assume.** CFTC disaggregated COT for report date 2026-07-28: total open interest 1,672,441 contracts, **327 reportable traders**. Shares of OI:

| Category | Long | Short | Spreading |
|---|---|---|---|
| Producer/Merchant/Processor/User | 13.3% | 14.3% | — |
| Swap Dealers | 12.9% | 1.1% | 6.7% |
| **Managed Money** | 14.3% | 20.6% | **33.4%** |
| Other Reportables | 3.2% | 8.2% | 13.0% |
| Non-reportable (retail) | 3.3% | 2.6% | — |

Concentration: top 4 traders hold 18.1% of gross long / 25.3% of gross short OI.

**The single largest identifiable bloc in the contract is managed-money CALENDAR SPREAD positioning.** It went 3.3% of OI (2010) → 15.4% (2015) → 20.3% (2020) → 34.8% (2025) → 33.4% (now). Over the same period swap-dealer longs collapsed 28.8% → 12.9% and retail went 10.2% → 3.3%. Open interest more than doubled while the reportable trader count went 278 → 327. **Same number of firms, twice the risk each, and the risk has migrated from flat price to term structure.**

**The hedgers are not on our screen.** ICE cleared Henry Hub LD1 open interest is 8,028,413 contracts at 2,500 MMBtu = **2,007,103 NYMEX-equivalents, 20% larger than NYMEX NG itself**, and it is 57.7% producer/merchant long and 38.7% swap-dealer short — the mirror image of NYMEX. The commercial hedge flow that sets the seasonal balance is transacted as cleared swaps and EFS, not as visible NYMEX aggressor flow.

**Compounding that: outright-vs-outright is only ~27.7% of Henry Hub volume.** Roughly 72% of matched volume involves a calendar-spread leg, and CME settles non-active months off calendar-spread VWAP. Between the ICE migration and the spread dominance, **the front-month outright tape we read is a minority of the information-bearing flow, and it is disproportionately speculative.**

**Who we are actually trading against at our horizon (hours to days):**

- **Not primarily the HFT market makers.** HFT market share in NG went 12.9% (2012) → 31.7% (2020), full-sample average 24.5%, versus WTI's 52.1% average. NG is the least HFT-penetrated liquid energy contract. CFTC researchers also name natural gas as an **exception** to their own headline result — HFT participation does not measurably improve NG spreads or Amihud price impact the way it does elsewhere.
- **Managed-money spreaders and the merchant complex.** Citadel (commodities: 260+ investment professionals, ~100 engineers, ~24 meteorologists, roughly $4bn/yr of profit largely from gas, now owning Haynesville production via Paloma/Apex, and moving volume equivalent to ~11% of US consumption), Statar Capital (Ron Ozer, gas-majority book, outright plus cross-commodity RV, stated edge is "deep insight into market participant hedging and allocation psychology"), Millennium, Macquarie, and the physical merchants monetizing storage and transport optionality (Vitol, Trafigura, Mercuria, Freepoint, Hartree, Castleton).
- **A large residual of humans.** ~19% of Henry Hub volume has a human on **both** sides (vs 4.4% in Euro FX, 13.8% in the E-mini). Large *manual* traders are 17.5% of NG volume vs 5.8% in the E-mini. In 2016 NG had 374 principal-trading-firm accounts against 2,553 individual accounts.
- **On Kalshi's gas ladder: essentially one programmatic quoter and a handful of discretionary participants.** Direct measurement (below) shows eleven trades in 6.5 overnight hours on the at-the-money strike.

**Lens conflict resolved.** One lens reported Henry Hub as 42.5% ATS-ATS / 41.6% ATS-manual / 12.3% manual-manual; three reported 30.7 / 45.8 / 19.1. Both are CFTC figures from **different samples** — the 30.7/45.8/19.1 set is the primary Nov 2012–Oct 2014 white paper, the higher set is the Nov 2014–Oct 2016 update. The trend is unambiguously up. **There is no published NG-specific automation figure after 2020.** Treat 31.7% HFT and ~50% ATS-ATS as a floor, not a current number, and do not build a plan whose validity depends on gas staying this manual.

---

## 2. WHAT WE MUST NOT COMPETE ON

Blunt list. Each of these loses money slowly and invisibly.

1. **The first seconds after any scheduled number.** CFTC's own intraday charting shows automated aggressive share spiking precisely at the 10:30 ET inventory release and at settlement, and says outright that this is where the benefit of speed is greatest. Documented instance in our own market: 16 July 2026, EIA printed 41 Bcf against a 43 Bcf consensus and front-month fell **39 ticks in 11 seconds**. Machine-readable DOE/EIA feeds redistribute the number ahead of the web release. We cannot be first and must never hold a position *into* the print expecting to react to it.
2. **Passive spread capture at the top of book.** CME NG is strict FIFO and market-by-order data exposes OrderID/PriorityID, so queue rank is public to competitors. Latency races resolve in 5–10 microseconds and the top six firms take over 80% of race wins. Non-colocated means not competing.
3. **The order-flow dipole at its native horizon.** The published decay profile for order-flow imbalance is strong over roughly the next two mid-price changes, informative to a few minutes via cross-impact, then near zero — and regime-dependent. That band is exactly where market makers already condition their quotes. As a standalone entry trigger the dipole is a colocated product.
4. **Cross-venue arbitrage on any well-trafficked event series.** Crypto is fully commoditized (8–14 second BRTI settlement lags, 2–7 second Kalshi/Polymarket windows, ~25 ms WebSocket detection, open-source bots on GitHub). Fourteen of the twenty most profitable Polymarket wallets are automated.
5. **Fundamental data acquisition.** Wood Mackenzie/Genscape combine the largest North American pipeline-nomination dataset with infrared plant surveillance and AIS vessel tracking, explicitly marketed as detecting outages *before* pipelines post nomination drops. We will never see the raw fact first.
6. **Raw weather forecast quality.** GFS 00/06/12/18Z and ECMWF 00/12Z are free and simultaneous. ECMWF's AIFS is operational; GraphCast beats HRES on 90% of verification targets at a few dollars of GPU per run. Citadel employs ~24 meteorologists and pays $750k–$1m at the top. There is no forecast-possession edge for anyone, including us.
7. **Breadth.** A systematic CTA runs 100+ markets. Grinold's law: a 30-name manager needs a 59% per-bet hit rate to match a 200-name manager running 53%. A one-market, one-call-per-day desk is structurally disadvantaged and must have a genuinely high per-call hit rate to be economically meaningful.
8. **Execution and slippage measurement.** Implementation-shortfall futures algorithms have existed since 2011; institutional TCA is mature. Unmeasured discretionary slippage is a permanent, silent tax.
9. **Believing that being human is itself an edge.** Harvey/Rattray/Sinclair/van Hemert found systematic and discretionary hedge fund performance statistically similar after adjusting for volatility and factor exposures. Systematic CTAs have higher median survival (12 vs 8 years) and lower true failure rates. There is no published evidence that judgment per se wins.

Also dead, so stop looking: **the index roll trade** (post-2012 spread impact under 10bp, fully reversing, often insignificant; annual investor roll cost fell from $2.9bn to $474m) and **ETF flow** (UNG under 1% of OI; BOIL+KOLD daily rebalance ~2,000 contracts on a 5% move, against a market that traded a record 2,576,346 contracts on 20 January 2026).

---

## 3. WHERE THE GAPS ARE — RANKED AND EVIDENCED

### Gap 1 (highest value): the EIA storage complex, as a forecasting and decomposition problem rather than a reaction problem

Three published, still-live, our-horizon anomalies:

- **The announcement-day puzzle** (Prokopczuk, Wese Simen & Wichmann, *Energy Journal* 2021): **more than 50% of the annual return in NG futures is earned on EIA announcement days**, unexplained by the surprise itself or standard controls; roughly half is pre-announcement and the pre-announcement half is generated entirely on days storage prints **above** expectations. The authors state the strategy survives transaction and funding costs.
- **One-week partial reversal** (Ederington, Lin, Linn & Yang, *Energy Journal* 2019): storage flows that beat or miss analyst expectations are partially reversed the following week, and analyst dispersion widens after large errors. The price reaction is conditional on the level of disagreement.
- **The Friday attention effect** (Gu, Kurov & Stan, *Journal of Futures Markets*, July 2026): NG responds **74% weaker** to EIA prints released on Fridays than Thursdays. That a simple calendar effect of that size was publishable this year is direct evidence the automated field is not closing it.

And the structural reason a gap exists at all: **the EIA headline is a noisy observation of a latent balance nobody sees.** Analysts model production, pipeline flows and weather to predict a number they cannot observe. Resolving a print requires salt vs non-salt decomposition, regional detail, and weather normalisation — a print can be bullish on the headline and bearish on the weather-adjusted balance. Machines take the headline in milliseconds; **the decomposition has an hours-to-days half-life.**

**Fit with our method.** This is where we should be concentrating and it is where we are currently worst: EIA Thursdays were **3,530 of G20's 7,880 total error**. Analog retrieval fits well *if* the retrieval key includes surprise sign, dispersion, and the weather-adjusted balance rather than price shape. The Kalshi lag is irrelevant here. The dipole is irrelevant here and worse than irrelevant — VPIN work on crude and gas shows resting depth is deliberately thinnest exactly around inventory announcements, so a flow read taken in that window is reading liquidity withdrawal, not opinion.

### Gap 2: the weather-to-burn conversion stack (not the meteorology)

The gas call is a stack: weather-driven load, minus wind and solar, minus what coal and nuclear absorb, plus LNG feedgas, against storage slack. The raw meteorology is commoditized; the conversion is not, and it is where everyone makes mistakes. **Our own G23 instance is the cleanest evidence available: gw_cdd ran 10.0 → 14.8 exactly as forecast and gas burn FELL 4.2 Bcf/d because wind rose 62% — with `wind_mwh` served in every slice and read by nobody.** The published ceiling on price-only daily Henry Hub prediction is instructive: the best of five architectures over a 10.5-year daily dataset achieved 53.75% directional accuracy and R² of 0.057, and the authors concluded real-time weather is the missing input.

The scale of what a physical revision can do: **2 February 2026, front month settled -25.7%, the largest single-day percentage loss since 1995 excluding rolls**, caused entirely by weather models shifting milder. Nothing in any price tape, order book, or price-shape library contained that.

**Fit.** Strong for a conditions-keyed analog library and for continuous monitoring. **Weak-to-void for shape-keyed retrieval** — a price-shape match carries no information about whether wind is about to absorb the load. This argues for weighting the condition stack at least as heavily as the shape at selection time, which is a change to how the library is queried, not a new build.

### Gap 3: roll windows and the calendar-spread book

CFTC finding, from their own data: **spread trading is relatively more manual, and manual share visibly spikes during each roll period** (a few days, monthly in NG). NYMEX separately runs a contractual program paying **up to ten designated market makers** to quote continuous two-sided Henry Hub futures out the curve, 08:00–14:00 CST. An exchange only subsidizes liquidity where nobody provides it for free.

**Fit.** This is a scheduled, recurring window of reduced machine density in the exact instrument we trade, and our per-leg roll handling means we can identify those days precisely. It is also where our record is worst — seam and roll days. That is not bad luck; it is the day class where market composition changes and flat-price machinery does not apply. **Either build a genuine roll/seam model or stand down on those days.** The dipole extends here usefully: we currently read under a third of information-bearing flow by ignoring the spread book. **Extending the flow read to spreads is the single highest-value upgrade available to the existing signal stack.**

### Gap 4: capacity — our size is an asset, not a limitation

Federal spot-month position limit on Henry Hub is **2,000 contracts (~$70m notional at $3.50)**, plus 2,000 across economically equivalent swaps. NG turnover is roughly 4% of the E-mini S&P's. The best-documented systematic commodity ML strategy (41 contracts, 126 features, 30 years, Sharpe 2.4 on an eight-horizon ensemble) caps out in **the low hundreds of millions**, and its highest-Sharpe variants are the least scalable. Commodity hedge fund managers self-cap deliberately. Published cross-sectional evidence says surviving predictability concentrates in low-liquidity, high-idiosyncratic-risk corners.

**Fit.** Excellent, with one hard rule: **never design a play that only pays at size we will never reach.**

### Gap 5: the Kalshi commodity and weather ladders

The first systematic academic study of Kalshi pricing (Burgi, Deng & Whelan; 46,282 contracts, 12,403 events, 2021–Apr 2025) finds unbiasedness **rejected for Financials (ψ = 0.032***, n=27,123) and Climate & Weather (ψ = 0.031***, n=29,924), but NOT rejected for Politics (0.022, ns) or Entertainment (0.020, ns)**. The crowd has cleaned up the famous markets and left the commodity and weather ladders alone. Direction of the bias: contracts under 10c lose over 60% of stake; contracts above 50c earn a small significant positive return. **Longshots are overpriced.** Makers out-earn takers. Bias is weakening year over year (2025 ψ = 0.021, marginal) — this window is closing, slowly.

Second, the **Liquidity Incentive Program** (15 Sep 2025 – 1 Sep 2026, CFTC-filed): $10–$1,000/day per market, pro-rata on a once-per-second score of resting order size × proximity to touch — and it **excludes MM-agreement holders, IBs, FCMs and their customers.** In a book this thin the subsidy can plausibly rival the trading edge.

**Fit.** Good for maker-first resting and for a calibrated-distribution product. **Bad for the dipole** — there is no tape to read (eleven trades in 6.5 hours). Capacity is the binding constraint; see Section 6.

### Gap 6: novel physical events and regime breaks

Freeport LNG (2.0 Bcf/d removed in an afternoon on 8 June 2022; three-week guidance that became seven months), negative WTI (systems that could not represent the state; ~$1.3bn of retail losses on one product), LME nickel (+250% in 24 hours, eight hours of trades cancelled), Uri, Fern. History-trained models have no basis vector for a state that has never occurred.

**Fit — and the honest caveat.** *Our analog library is also a history-trained object.* The post-shale disappearance of Henry Hub seasonality and its decoupling from WTI mean a library spanning that boundary contains two different markets under one ticker. An analog drawn from a foreign regime re-anchors confidently and is wrong on both level and slope. Continuous shape monitoring is a **reactive** mitigation. **Add a regime gate at retrieval time** — refuse or heavily discount analogs from a different supply/LNG/seasonality regime — rather than only discarding after divergence appears. This is the same principle as our own D23 finding: a condition that cannot change state carries no information.

---

## 4. IS OUR LAG EDGE CROWDED?

**No. And that is bad news, because of the reason.**

Direct measurement of KXNATGASD-26AUG0517, overnight session, 34 strikes at 0.5-cent gas spacing:

- Whole-ladder cumulative volume ~3,600 contracts — **roughly $3,600 of notional across the entire ladder**.
- At-the-money T2.700 quoted 0.52 / 0.55 — a **3-cent spread**.
- Top of book 500 × 299 contracts; next levels 100 × 100; then a 2,250/2,268-lot block sitting 12–13 cents away at **identical size on the adjacent strike** — one participant's programmatic backstop, not tradeable liquidity.
- The ATM strike printed **eleven trades in 6.5 hours**: sizes 1, 1, 2, 3, 7, 10, 10, 40, 92, 208.

The structural tell is stronger than the tape. **Kalshi lists hourly and 15-minute contracts on WTI, gold, silver, platinum and palladium. Natural gas has only daily, weekly and monthly.** The short-horizon formats that latency capital feeds on have not been extended to gas. Weather (KXHIGHNY) quotes **one-cent** spreads with per-strike volume 1,783–7,877 and OI 1,407–6,167 — roughly 10× the gas activity at one third the spread. Crypto hourly clears over $1bn a month.

**The lag is open because it is not worth a prop firm's minute.** SIG (Kalshi's first institutional market maker, since April 2024), Jump, Jane Street, DRW, Citadel Securities and Flow Traders are all on the venue — in sports (~80% of volume), crypto, and the flagship financial series. Institutional volume is up ~800% in six months and Kalshi open interest crossed $1.16bn. None of that has arrived at KXNATGASD.

**Three honest qualifications:**

1. **The economics cap it.** Taker fee is ceil(0.07 × P × (1-P) × 100)/100, ~1.75c per side at the money, so a taker round trip is ~3.5c of fees plus the 3c spread = **~6.5 probability cents**. The observed ladder gradient is ~6.5 probability cents per 1 cent of gas. **A taker round trip therefore requires a full 1-cent gas move that does not reverse.** Maker-only cuts fees to ~0.9c round trip and makes the same trade viable on a 3–4 cent move. Even perfect capture of the entire ladder at a 5-cent edge is ~$180/day.
2. **We may be measuring the wrong lag.** KXNATGASD settles on a **Pyth composite** (120+ publishers), not the NYMEX print. Some of what we measure as "Kalshi repricing latency" may be Pyth aggregation latency — a different and more fragile object, and one that can be closed by Pyth without anyone deciding to compete with us. This is unmodelled and should be measured before sizing.
3. **The venue is not inviolable.** In July 2026 Kalshi self-certified an emergency rule to force-liquidate a class of users' positions and the CFTC had to **stay** it and compel honoring the trades under CEA 8a(9). Rothera (Robinhood/Susquehanna) took ~7% share in its first month and Robinhood is routing its own flow there.

**What would tell us it is closing — in leading-indicator order:**
- Kalshi lists an **hourly or 15-minute natural gas series**. This is the earliest and clearest signal; product listing precedes the bots.
- ATM spread compresses from 3c toward 1c (the weather-ladder level).
- Top-of-book depth rises above ~1,000 contracts, or trade count per session goes from ~10 to ~100.
- A designated market-maker agreement is signed on a commodity series, or the Liquidity Incentive Program ends (currently 1 Sep 2026).
- Our own telemetry shows the measured lag shortening. **Treat a shortening lag as a signal to retire the play, not to re-tune it.**

---

## 5. WHAT WOULD PICK US OFF

**A. Being the resting bid when a model run lands.** This is the sharpest internal contradiction in our plan. Maker-first is correct for cost (round trip ~$25–30 on NYMEX against a typical $300–500 daily range; ~0.9c vs 6.5c on Kalshi) and it is exactly the posture that gets run over by scheduled non-price information. GFS at 00/06/12/18Z, ECMWF at 00/12Z, EIA Thursday 10:30 ET, and the 14:28–14:30 settlement window are all knowable. **A resting order alive through any of them is a free option we are writing.** Cancel-on-schedule must be mechanical, not discretionary.

**B. Our Kalshi flow is fully legible.** At eleven trades per session, **our trades are the tape.** A single quoter reconciling fills against the subsequent Pyth move will see: same side, same ATM strike, consistently minutes before the composite moves, consistently one participant. That is about as identifiable a signature as exists in any market. Their response is not exotic — widen from 3c to 6c, or pull. Our edge evaporates without anyone having to out-compute us. **Corollary: we must vary strike, side and timing, and we must accept that the venue can price us out unilaterally.**

**C. The settlement minute.** 17:00 ET is simultaneously the Kalshi gas settlement window and the CME gas daily halt — the thinnest reference minute of the day, resolved on a 1-minute composite. The published measurement of exactly this structure (Polymarket 5-minute BTC): ~$3.2m transferred over two months, retail on the losing side of 64–66% of manipulated cycles bearing 62–74% of losses, **93% of the loss landing on retail and essentially none on market makers, who quote passively and end each cycle flat.** Be flat or resting well away from the touch into the print. Never be the marginal taker in the final 60 seconds.

**D. Resting stops.** CFTC: ATS orders are almost exclusively limit orders; manual orders are stop-loss 4% and market 11% of the time. Machines synthesize stops from speed. **A resting stop in the gas book is one of the few visible human artifacts left in it.** Never leave one.

**E. Trading against the informed side without knowing it.** Where a trade's thesis rests on flow information rather than our own causal reasoning, assume we are the uninformed side. The counterparties with nomination feeds, infrared plant surveillance, AIS tracking and their own production books see the fact before it is a price.

**F. Our own research process, which is the largest exposure of all.** Lopez de Prado: roughly **20 iterations on the same data manufacture a false discovery at the 5% significance level**, and **"it is as easy to overfit a walk-forward backtest as to overfit a walk-backward backtest"** — a single historical path. We are at G23 with dozens of proposed and refuted plays. Separately, McLean & Pontiff measured published predictors as returning **26% less out-of-sample and 58% less post-publication**.

**G. The one number that decides everything, and we have not computed it.** Our blind direction across the last five groups is 4/10, 6/10, 5/10, 4/10, 5/10 = **24 of 50, or 48%** — statistically indistinguishable from a coin (expected 25, sd 3.5). Blind mean absolute error is **roughly 6–9 cents of gas per day**. The refine numbers (10/10, "every day under 100" = under 1 cent) are produced *with the realized price curve visible* and are an explanation, not a forecast.

**So compute this before anything else ships: for each blind block, sum the ABSOLUTE ACTUAL day moves and compare to sum|err|.** If sum|err| ≥ sum|actual move|, the blind forecaster is not beating a **zero-change forecast**, and every downstream conclusion about edge is void. From the partial day-nets on record (moves clustering in the 20–800 range against blind errors averaging ~590), this test is genuinely at risk of failing. It is a two-hour calculation on data we already hold and it is the highest-value work available.

---

## 6. THE POSITIONING

**What this desk is not.** It is not a latency business — we are not colocated, and the microsecond and sub-second layers in gas belong to firms whose entire capital structure is built for them. It is not a data business — pipeline nominations, plant surveillance and multi-model degree days are purchasable and the raw weather is free to everyone. It is not a breadth business — one market, one call a day, against CTAs running 100+ markets and a documented ensemble that beat everything on eight horizons at once. And on the Kalshi leg it is not, at present, a business at all: a whole-ladder notional of ~$3,600/day means even flawless execution of the lag edge is worth low hundreds of dollars a day, less than the Liquidity Incentive Program pays for simply resting orders in the same book. **The most valuable thing in this brief is the arithmetic that says our clearest claimed edge is uncontested precisely because it is too small to contest, and our second claimed edge — the dipole — has no tape to read on the venue where we intend to use it and lives at a decay horizon we cannot reach on the venue where it does.**

**What this desk realistically is.** It is a small, capacity-advantaged, non-price-driven research operation in the least machine-penetrated liquid energy contract in the world — 24.5% average HFT share against WTI's 52.1%, 19% of volume with a human on both sides, 85% of passive fills resting longer than a second, a $70m regulatory ceiling that keeps large systematic capital in a different weight class, and one of only two contracts where the CFTC's own market-quality result fails. The defensible product is a **calibrated distribution of the next session's move, conditioned on the burn stack and the day class** — not a direction call, because the ladder pays for distribution and our measured direction is a coin flip, and because the venue's documented bias (longshots overpriced, ψ significant in Financials and Climate & Weather but not in Politics) pays a desk that can say "today's wings are too wide" for a physical reason. The three places to spend the next six months, in order: **(1)** the EIA complex, where three published anomalies sit on our worst-scored day class and where the decomposition has an hours-to-days half-life that no machine contests; **(2)** the burn stack as an explicit, scored feature set, because our own retired burn gate proves it is the hard part and therefore the right part; **(3)** roll and spread days, where CFTC data says manual share spikes and where we currently ignore ~72% of the information-bearing flow. Everything else — the lag, the dipole as a trigger, any attempt to be early on the tape — should be demoted to defensive instrumentation. And nothing should be sized at all until the zero-forecast benchmark test in Section 5(G) comes back positive, a trials counter is running against every play ever proposed, and every reported hit rate is deflated by the number of trials that produced it.

---

# APPENDIX - THE FIVE LENSES, VERBATIM


## LENS

```json
{
 "lens": "What systematic strategies actually run in energy futures at intraday-to-multi-day horizon, with Henry Hub natural gas as the focus - who consumes which signal, over what holding period, and therefore who is competing for the same moves we are.",
 "findings": [
  {
   "topic": "Baseline: how automated Henry Hub NG actually is",
   "what_is_actually_done": "By the last period CFTC published contract-level, 42.5% of Henry Hub NG futures volume was ATS-to-ATS, 41.6% ATS-to-manual, and only 12.3% manual-to-manual. So ~88% of volume has a machine on at least one side, but a machine is only on BOTH sides of ~42%. Trend was strongly rising (30.7/45.8/19.1 in 2012-14). Interpretation: NG is fully electronified but not yet a machine-vs-machine market the way FX or E-mini is (British pound ATS-ATS 74%, Yen 78%).",
   "evidence": "Haynes & Roberts, 'Automated Trading in Futures Markets' (CFTC OCE white paper, sample Nov 2012-Oct 2014) and its 2019 Update (adds Nov 2014-Oct 2016), Table 5 contract-level. Energy category overall rose from ~47% to ~57% automated between the two samples.",
   "timescale": "structural / all horizons"
  },
  {
   "topic": "HFT market share in NG vs other contracts - NG is the least penetrated liquid energy market",
   "what_is_actually_done": "Account-level regulatory data: HFT market share in natural gas futures went 12.9% (2012) to 31.7% (2020), sample average 24.5%. WTI crude over the same window: 29.1% to 53.9%, average 52.1%. Gold 20.6 to 48.1. E-mini S&P 31.8 to 49.7. NG is the lowest-HFT-share of the majors after agriculture.",
   "evidence": "Coughlan & Orlov, 'High-Frequency Trading and Market Quality: Evidence from Account-Level Futures Data', CFTC Office of the Chief Economist, July 2022 draft, Table 1. Sample Jan 2012 - Aug 2021, nine contracts including natural gas and WTI.",
   "timescale": "structural / all horizons"
  },
  {
   "topic": "The NG order book is measurably SLOWER than financial futures",
   "what_is_actually_done": "85% of passive executed natural gas futures orders rested in the book longer than one second (corn >90%). Compare ~40% of Euro and Yen passive fills executing WITHIN one second and ~20% for Treasuries and E-mini. The sub-second layer exists in NG but it is not where most of the volume clears.",
   "evidence": "Haynes & Roberts (CFTC), resting-time analysis, Nov 2012-Oct 2014 sample; the 2019 update shows the same table shifting faster but the ranking unchanged.",
   "timescale": "sub-second to seconds"
  },
  {
   "topic": "Natural gas is the exception in the HFT market-quality result",
   "what_is_actually_done": "Coughlan & Orlov find HFT participation significantly improves market quality across almost every contract - but they explicitly name natural gas as a non-result in BOTH the Amihud price-impact regressions and the bid-ask spread regressions (with wheat and gold). Practical read: HFT is not the established marginal liquidity provider in NG the way it is in WTI or ES; the resident liquidity is still substantially commercial/discretionary.",
   "evidence": "Coughlan & Orlov (CFTC, 2022), footnote 16 to the individual-market results: 'The only exceptions are natural gas and wheat in the Amihud regressions and gold ... and natural gas in the bid-ask spread regressions.'",
   "timescale": "structural"
  },
  {
   "topic": "Electronic market making in NG front month - how it earns",
   "what_is_actually_done": "Standard FIFO queue business: quote both sides, earn the spread, manage adverse selection. CME Globex NG and Micro NG are strict FIFO (no pro-rata, no size priority), so the earnings driver is queue position, which is won by speed and by never being the last to cancel when flow turns toxic. Market-by-order data gives exchange-assigned OrderID and PriorityID, so competitors can see exactly where in line each order sits and can identify iceberg refills by OrderID reuse.",
   "evidence": "CME Group Micro Henry Hub FAQ (FIFO matching, identical to standard size); CME Market-by-Order documentation on OrderID/PriorityID and iceberg refresh behavior.",
   "timescale": "microsecond to seconds"
  },
  {
   "topic": "Exchange-subsidised liquidity provision on the deferred NG curve",
   "what_is_actually_done": "NYMEX runs a 'Deferred Natural Gas Market Maker Program': up to TEN designated participants, competitively selected, contractually obliged to quote continuous two-sided markets at designated bid/ask widths and minimum sizes in Henry Hub NG futures on Globex, 08:00-14:00 CST, in exchange for predetermined incentives. Stated purpose is to 'build deeper liquidity out the curve'. Read this as an admission: passive liquidity provision beyond the prompt months is not spontaneously profitable, so the exchange pays for it.",
   "evidence": "NYMEX Submission 16-181R to CFTC, 'Modifications to the NYMEX Deferred Natural Gas Market Maker Program', Exhibit 1, filed May 16 2016 (program term extended to Feb 28 2017; the program family has been renewed since).",
   "timescale": "structural / continuous quoting"
  },
  {
   "topic": "Execution algorithms are the dominant algo class in gas, not signal algos",
   "what_is_actually_done": "Fourier analysis of NG futures tick data shows a strong periodic concentration of trading in the FIRST SECOND OF EVERY MINUTE - the signature of TWAP schedulers slicing parent orders. Legal/regulatory survey of power and gas algo usage finds that in NATURAL GAS markets execution algorithms predominate, while power markets see execution, signal-generation and full trading algos in comparable use. Gas is behind power in autonomous algo decision-making.",
   "evidence": "Song, Lopez de Prado, Simon & Wu, 'Intraday Patterns in Natural Gas Futures: Extracting Signals from High-Frequency Trading Data' (SSRN 2657224, 2015). Reed Smith, 'Algorithmic trading in power and gas markets: Uses, trends and regulatory considerations in EU, UK and United States', citing the ACM study.",
   "timescale": "seconds (the TWAP grid) / minutes-to-hours (the parent order)"
  },
  {
   "topic": "Order-flow imbalance and queue-dynamics alpha - the decay horizon",
   "what_is_actually_done": "Cont/Kukanov/Stoikov-family OFI: cumulative signed queue-size change at best bid/ask, near-linear in short-horizon return with slope inversely proportional to depth. Empirically the link is strong within tens of seconds and cross-impact terms carry information out to 'several minutes' before decaying. This is exactly the band our dipole/exhaustion read occupies.",
   "evidence": "Cont, Kukanov & Stoikov, 'The price impact of order book events' (arXiv 1011.6402); subsequent cross-impact literature (Quantitative Finance, 2023) on decay to a few minutes.",
   "timescale": "seconds to a few minutes"
  },
  {
   "topic": "Iceberg / hidden-liquidity detection",
   "what_is_actually_done": "Detect native icebergs from discrepancies between resting displayed volume and trade-summary size plus post-trade order modifications; detect synthetic icebergs from limit orders arriving within a short window after a trade; then predict total hidden size with a Kaplan-Meier survival model. Authors state plainly that most tranches arrive LESS THAN ONE SECOND after the previous tranche, so the output 'is more suitable as an input to other trading algorithms, rather than a signal to a day trader, who would not be able to react sufficiently fast.'",
   "evidence": "Zotikov & Antonov (Devexperts/dxFeed), 'CME Iceberg Order Detection and Prediction', preprint 2019, arXiv 1909.09495. Studied on ESU19 full-order-depth data.",
   "timescale": "sub-second to seconds"
  },
  {
   "topic": "EIA weekly storage print - the speed trade is settled and we lose it",
   "what_is_actually_done": "Low-latency machine-readable vendors (e.g. Haawks G4A) redistribute the DOE/EIA number faster than the standard 10:30 ET web release; algos fire on the surprise-vs-consensus delta. Documented instance: 16 July 2026, EIA printed a 41 Bcf injection vs Reuters consensus 43 Bcf (5-yr avg 45), and NG futures fell 39 ticks within the first 11 seconds.",
   "evidence": "Haawks blog, 'Natural Gas Futures Drop 39 Ticks in 11 Seconds After EIA Storage Report', 16 July 2026; EIA Information Releases site (ir.eia.gov) release mechanics.",
   "timescale": "milliseconds to ~15 seconds"
  },
  {
   "topic": "EIA storage - the announcement-day anomaly that has NOT been arbitraged away",
   "what_is_actually_done": "More than 50% of the ANNUAL return in NG futures is earned on EIA storage announcement days. The announcement-day/non-announcement-day return difference cannot be explained by the surprise itself or standard controls. Intraday it splits roughly half pre-announcement and half post-announcement, and the pre-announcement half is generated entirely on days when storage comes in ABOVE analyst expectations - which the authors say argues against an informed-trading explanation. A simple strategy survives transaction and funding costs.",
   "evidence": "Prokopczuk, Wese Simen & Wichmann, 'The Natural Gas Announcement Day Puzzle', The Energy Journal 42(2), 2021 (SSRN 3575861).",
   "timescale": "intraday session / day-class conditioning, held across the print day"
  },
  {
   "topic": "EIA storage - documented multi-day mean reversion in the surprise",
   "what_is_actually_done": "Analyst storage forecasts add information beyond seasonality and past flows, and the market incorporates the consensus into prices BEFORE the print. Critically: storage flows that come in higher or lower than analysts expected in one week tend to be PARTIALLY REVERSED the following week, and analyst dispersion widens after large forecast errors. The price reaction to the print is conditional on the level of analyst disagreement.",
   "evidence": "Ederington, Lin, Linn & Yang, 'EIA Storage Announcements, Analyst Storage Forecasts, and Energy Prices', The Energy Journal 40(5), 2019, pp.121-142. See also Fernandez-Perez, Garel & Indriawan, 'Natural Gas Storage Forecasts: Is the Crowd Wiser?', Energy Journal 41(5), 2020.",
   "timescale": "one week (print to print)"
  },
  {
   "topic": "An attention effect in NG still alive in 2026 peer-reviewed work",
   "what_is_actually_done": "The natural gas futures market responds 74% WEAKER to EIA inventory announcements released on FRIDAYS than to those released on Thursdays, robust to controlling for withdrawal vs injection season. Authors attribute it to lower trader attention. That a pure attention/calendar effect of this size is publishable in 2026 means the automated participants are not fully closing it.",
   "evidence": "Gu, Kurov & Stan, 'Trader Attention and Market Reaction to Fundamental News: Evidence From Natural Gas Futures', Journal of Futures Markets 46(7), July 2026, pp.1171-1181.",
   "timescale": "the print day and the following session"
  },
  {
   "topic": "Calendar-spread statistical arbitrage in energy",
   "what_is_actually_done": "Mean-reverting calendar-spread portfolios with dynamic (rolling regression) hedge ratios, Bollinger-band entry/exit on the spread. Best risk-adjusted results in the whole energy complex were WTI and NATURAL GAS, Sharpe above 2 for most front-month/second-month combinations, net of transaction costs, over 1992-2013. Practitioner-level algo descriptions use e.g. a 40-day EMA of the spread with entry at 150% of historical max deviation.",
   "evidence": "Lubnau & Todorova, 'Trading on mean-reversion in energy futures markets', Energy Economics 51 (2015), 312-319.",
   "timescale": "multi-day to multi-week holds"
  },
  {
   "topic": "Spread and roll trading is where MANUAL participation concentrates",
   "what_is_actually_done": "CFTC finds physical commodities carry a much higher frequency of spread trading than financials, and that 'spread trading is, on a relative basis, a more manual activity.' Their time series shows manual share SPIKING during each primary roll period, which lasts a few days. NG rolls monthly. This is a recurring, calendar-known window in which the machine share of the tape falls.",
   "evidence": "Haynes & Roberts (CFTC), Tables 4 and 5 and Figure 1 discussion; Eurodollar's low automation rate is explained entirely by its spread-trading intensity.",
   "timescale": "the 3-5 day roll window, monthly"
  },
  {
   "topic": "Storage / seasonal spread strategies as run by the exchange's own clients",
   "what_is_actually_done": "ICE documents four alpha families: (1) fully hedged seasonal - long the Apr-Oct strip, short the Nov-Mar strip, to monetise storage economics; (2) partially hedged seasonal - buy cash Apr-Oct, sell the Nov-Mar futures strip; (3) 'distressed gas' - buy when storage ratchets force sellers ('garage full'; cash hit $1.82/MMBtu in April 2012); (4) cash-futures spread trades where cash delinks from futures by up to 10%. Signals: storage level vs ratchet thresholds, Oct/Nov and Oct/Jan spreads, Mar/Apr spread. ICE is explicit that physical storage operators hold advantages financial traders do not (flat-fee economics, intramonth cash access, injection/withdrawal timing).",
   "evidence": "ICE white paper, 'Time Traveling the Natural Gas Market: storage dynamics and alpha generation'.",
   "timescale": "weeks to seasons; the distressed-cash leg is days"
  },
  {
   "topic": "Trend following / time-series momentum in natural gas specifically",
   "what_is_actually_done": "The published NG-specific result is a LONG-lookback result: Rate-of-Change with a 10-month (and in an alternative specification 14-month) lookback beats buy-and-hold on Sharpe and Sortino using monthly Henry Hub futures 2004-2024; adding an MA price-crossover overlay did NOT improve it. Broader TSMOM literature finds no capacity constraint in futures but weaker performance when speculator positioning is aligned with the momentum signal.",
   "evidence": "'The Performance of Momentum Trading Strategies in the U.S. Natural Gas Futures', Springer 2025. Uhl, 'Speculators and time series momentum in commodity futures markets', Review of Financial Economics, 2025. Baltas & Kosowski on CTA-TSMOM loading.",
   "timescale": "10-14 MONTH signal, monthly rebalance - not our horizon"
  },
  {
   "topic": "Carry / roll yield in a seasonal market",
   "what_is_actually_done": "Commodity carry is the interest-adjusted slope of the curve; in backwardation, index returns 7.7% vs 2.1% in contango, driven by carry (12.2% vs -3.6%). For NG the raw slope is dominated by the seasonal shape, so systematic carry books apply a SEASONAL ADJUSTMENT to the basis before ranking, to isolate structurally steep curves from calendar artefacts. Seasonally- and volatility-adjusted carry shows significant return predictability.",
   "evidence": "Levine, Ooi, Richardson & Sasseville, 'Commodities for the Long Run' (NBER WP 22793 / FAJ); Macrosynergy, 'Commodity carry as a trading signal'.",
   "timescale": "monthly rebalance, multi-month holds"
  },
  {
   "topic": "Cross-commodity: spark spread and gas-to-power",
   "what_is_actually_done": "Spark spread = power price ($/MWh) minus gas price ($/MMBtu) x heat rate (MMBtu/MWh). Traded outright, as heat-rate-linked transactions, and via tolling structures, which lets a financial participant arbitrage gas/power dislocations without owning generation. Algorithmic desks run this cross-product because power intraday markets are continuous and gas is the marginal fuel; algos monitor day-ahead vs intraday power, cross-border flows and weather in the same loop.",
   "evidence": "EIA spark spread methodology; CME Spark Conversion Calculator; Montel and Trayport practitioner material on cross-commodity algo trading; Reed Smith survey noting all three algo types in comparable use in power.",
   "timescale": "intraday (power) to multi-day (gas leg)"
  },
  {
   "topic": "Location basis",
   "what_is_actually_done": "Systematic and discretionary desks trade Henry Hub vs regional hubs (Waha, Algonquin Citygate, etc.) as pipeline-capacity-constrained spreads. The signal is physical: takeaway capacity vs production growth, maintenance, and new pipeline in-service dates. Waha traded at deep discounts (at times negative) on Permian associated-gas oversupply; Matterhorn Express and Hugh Brinson are expected to normalise the spread through late 2026.",
   "evidence": "EIA Today in Energy on hub differentials and Permian takeaway; NGI/AEGIS Waha basis coverage; PGJ, May 2026.",
   "timescale": "weeks to quarters, with event-driven days around maintenance and in-service"
  },
  {
   "topic": "Order-flow toxicity as a liquidity-withdrawal predictor around gas prints",
   "what_is_actually_done": "VPIN (volume-synchronised probability of informed trading) is used by liquidity providers to detect adverse selection and pull quotes. Measured on crude oil and natural gas futures Jan 2009-May 2015, VPIN rose significantly around inventory announcements accompanied by price jumps AND around unscheduled jumps. Practical meaning: the resting depth we would trade against is deliberately thinnest exactly when information arrives.",
   "evidence": "Easley, Lopez de Prado & O'Hara VPIN literature; published application to crude and natural gas futures around inventory announcements and jumps (2009-2015 sample).",
   "timescale": "minutes around the event"
  },
  {
   "topic": "Systematic-fundamental weather desks - the most heavily staffed lane in gas",
   "what_is_actually_done": "Multi-strategy funds run in-house meteorology as a centralised research resource feeding commodity pods: Citadel ~24 weather specialists (hires include Nicholas Klingaman, sub-seasonal forecasting; Nick Weber, PhD atmospheric sciences, ex-NCAR); Millennium 5-10; Squarepoint 6+ including climate-focused ML; DV Trading hired from NOAA; Balyasny and Jane Street also hiring. Top packages $750k-$1m, 18% YoY pay increase, 23% more hires in 2024. Citadel's commodities business has produced roughly $4bn annually for three straight years, largely from natural gas; the team lineage traces to Enron traders and meteorologists recruited from 2002 and the 2018 Cumulus acquisition (~20 people).",
   "evidence": "Hedgeweek, 'Hedge funds hiring meteorologists to weather market volatility'; Bloomberg / Financial Advisor coverage of weather-modelling pay; Proco Group hiring data.",
   "timescale": "days to weeks (forecast-driven positioning), sub-seasonal out to months"
  },
  {
   "topic": "The named NG specialist fund and what its process looks like",
   "what_is_actually_done": "Statar Capital (Ron Ozer, ex-Citadel head of NG, ex-DE Shaw, founded 2018): macro strategy running directional AND cross-commodity relative value with gas as the majority of the book, explicitly combining fundamental and technical models with rigorous drawdown analysis in construction. Ozer's Citadel team was 8 analysts, traders and meteorologists. Stated cross-commodity RV edge is 'deep insight into market participant hedging and allocation psychology' - i.e. modelling who has to trade and when, not predicting weather better. Sharpe >2 since Sept 2018 at ~16% target vol; +50%+ in 2020 and 2021, +30% 2022, -0.6% 2023, +23% through mid-Dec 2024, with a -13% Q2 2024 drawdown.",
   "evidence": "The Hedge Fund Journal profile of Statar Capital; Hedgeweek and Bloomberg coverage of the European gas options trade and the 2024 drawdown/recovery.",
   "timescale": "days to months; the RV book is multi-day"
  },
  {
   "topic": "Weather model runs as scheduled, PUBLIC catalysts",
   "what_is_actually_done": "Desks trade the delta between successive runs of public NWP: GFS at 00/06/12/18Z, ECMWF high-res at 00/12Z (ensembles 06/18Z), converted to gas-weighted degree days. Vendor forecast products update 4x daily around 05z/09z/13z/21z. A single run shift is quoted in weighted-degree-day terms (e.g. GFS +21.8 weighted CDDs vs prior cycle with ECMWF unchanged) and moves the strip. The RAW INPUT IS FREE AND SIMULTANEOUS - the differentiation is downscaling, point forecasting, and the conversion into burn.",
   "evidence": "GasAlpha and Enverus practitioner material on gas-weighted degree days and point forecasting vs raw GFS; jua.ai GFS vs ECMWF run schedule comparison.",
   "timescale": "the run-to-run gap: 6-12 hours, traded within minutes of arrival"
  },
  {
   "topic": "Who makes markets in the Kalshi leg",
   "what_is_actually_done": "Susquehanna (via Susquehanna Government Products) became Kalshi's DESIGNATED market maker in April 2024, standing up a dedicated department to quote two-way continuously; six-figure size is now available in major markets. Jump Trading took stakes in both Kalshi and Polymarket by Feb 2026. Sector notional was $113.8bn in Q2 2026, Kalshi 58.9% share. Practitioner consensus is that Kalshi ENERGY contracts settle on published prices rather than a live feed, so the edge there is forecasting rather than latency, while cross-venue dislocation windows are typically under 60 seconds and belong to automated systems.",
   "evidence": "SIG/Kalshi designated market maker announcements; Blockhead on Jump Trading's Kalshi and Polymarket stakes (Feb 2026); Kalshi Q2 2026 volume reporting.",
   "timescale": "continuous quoting; arb windows under 60 seconds"
  },
  {
   "topic": "The market we are trading into is growing and getting more contested",
   "what_is_actually_done": "CME natural gas complex set a single-day record of 2,576,346 contracts on 20 January 2026, +15% over the Nov 2018 record; Henry Hub OPTIONS traded a record 811,662 contracts, +28%. Structural demand drivers (LNG buildout, data-centre power burn, projected ~6.1 Bcf/d of data-centre gas demand by 2030) are pulling more capital in, and 2025 saw all-time-high gas trading volumes and hub liquidity across key markets.",
   "evidence": "CME Group press release, 21 Jan 2026; RBC Capital Markets, 'Natural gas powers the data center boom' (May 2026); IEA Gas Market Report Q1-2026.",
   "timescale": "structural"
  }
 ],
 "where_machines_dominate": [
  "The scheduled numeric release. EIA at 10:30 ET Thursday: 39 ticks in 11 seconds on a 2 Bcf miss, with commercial low-latency machine-readable DOE feeds (Haawks G4A class) redistributing the number ahead of the web release. There is no version of this trade we win. Do not build toward it, and do not let an intraday model take a position INTO the print expecting to react to it.",
  "Queue position and passive spread capture at the top of book. CME NG is strict FIFO, and MBO data exposes OrderID/PriorityID so competitors can see queue rank exactly. Spread capture is a speed-and-cancellation business we are not equipped for and are not colocated for.",
  "Order-flow imbalance and queue-dynamics signals at the seconds-to-few-minutes horizon. The academic decay profile (strong within tens of seconds, cross-impact informative to a few minutes) is precisely the band where HFT market makers already condition their quotes. Our dipole exhaustion read sits in this band as a standalone timing signal.",
  "Hidden-liquidity/iceberg inference. Tranche refills arrive under one second apart; the authors of the leading detection paper say outright it is unusable as a human day-trader signal and only works as an input to another algorithm.",
  "Cross-venue arbitrage inside the futures-to-Kalshi repricing window. Susquehanna is Kalshi's designated market maker with a dedicated department; Jump Trading has taken a stake. Dislocation windows are described as under 60 seconds and closing. Our (a) edge is real today but it is a depreciating asset on someone else's clock.",
  "Instant re-pricing of the whole strip and the options surface off a front-month move. Any relative-value dislocation that is purely a function of already-public prices is gone before a human reads it.",
  "Execution. TWAP/VWAP slicing is the dominant algo class in gas and it leaves a visible print at the first second of every minute. We will not out-execute it; we can only avoid being run over by it."
 ],
 "where_machines_are_weak": [
  "The deferred curve. NYMEX has to run a contractual program paying up to ten designated market makers to quote continuous two-sided Henry Hub futures out the curve, 08:00-14:00 CST. An exchange only subsidises liquidity where nobody provides it for free. Machine liquidity provision in NG is concentrated in the prompt months.",
  "Spread and roll trading. CFTC's own finding: spread trading is relatively MORE manual, and manual share visibly spikes during each monthly roll window (a few days). This is a calendar-known, recurring period when the machine share of the NG tape falls.",
  "Attention and calendar effects. A 74% weaker NG response to EIA prints released on Fridays versus Thursdays was still publishable in the Journal of Futures Markets in July 2026. That is a large, simple, day-of-week effect that automated participants are demonstrably not closing.",
  "Multi-day mechanism chains. Storage surprises partially REVERSE the following week and analyst dispersion widens after large errors (Ederington et al.). The announcement-day return concentration (>50% of annual return on EIA days, half of it PRE-announcement, unexplained by the surprise) survives transaction and funding costs. These are week-scale structures, not speed trades.",
  "The conversion problem: weather -> load -> burn -> price. This is a causal STACK (weather-driven load, minus renewables, minus what coal and nuclear absorb, plus LNG feedgas, against storage slack). A machine reading a single degree-day series gets the sign wrong when wind swings. Our own G23 evidence is an instance: gw_cdd arrived exactly as forecast and gas burn FELL 4.2 Bcf/d because wind rose 62%. Nobody has automated this reliably, which is why the funds hire humans for it.",
  "Short-horizon trend following is NOT a competitor in NG. The published NG-specific momentum result requires a 10-14 MONTH lookback on monthly data. Nobody is systematically taking our intraday-to-multi-day trend trades with a trend model.",
  "NG is the least HFT-penetrated liquid energy contract: 31.7% HFT share in 2020 vs 53.9% for WTI, with 85% of passive fills historically resting longer than a second, and it is one of only two contracts where CFTC researchers found HFT participation does NOT measurably improve spreads or price impact. There is more room here than in crude, ES or FX.",
  "Regime transitions and the once-a-year setups (Mar/Apr widowmaker, end-of-injection storage ratchets, 'distressed gas' when the garage is full, holiday and reopen seams). Thin-history, high-consequence, mechanism-dependent states are where fitted models are least reliable and where a described-conditions analog library has an actual structural advantage."
 ],
 "implications_for_us": [
  "Be honest about edge (a): the futures-to-Kalshi lag is a latency race with a fixed expiry date. SIG is the designated market maker and Jump is now an investor in Kalshi. Harvest it while it exists but do not build the desk's thesis on it, and do not spend capital on infrastructure to defend it. Practitioner reporting already notes Kalshi ENERGY contracts settle on published prices, not a live feed - so the durable Kalshi edge is FORECASTING, which is the lane we are actually building.",
  "Re-position edge (b), the dipole, from timing signal to FILTER. As a standalone entry trigger it lives in the exact seconds-to-minutes band where OFI decays and where HFT market makers already condition. As a confirmation/veto on a thesis held for hours to days it is defensible, because nobody is holding an OFI-derived position that long. This matches what our own S36 work already concluded (divergence is the filter, fine-resolution reversal is the timing) and it argues for keeping DEPLOY_VALIDATED=False on the directional map.",
  "Edge (c), the analog library, is the genuinely differentiated asset - but only if the retrieval key is the CONDITION STACK, not the price shape. The literature says the announcement-day premium and the storage-surprise reversal are unexplained by the surprise itself; that residual is exactly what a conditions-to-outcome library can carry and a factor model cannot. Our current method already re-anchors by shape; the finding argues for weighting the stack (weather anomaly, wind, storage slack, positioning, dispersion) at least as heavily as the shape when selecting the analog.",
  "Three documented, still-live, our-horizon anomalies to test directly against our corpus: (1) the Friday EIA attention effect - 74% weaker response, and note our Kalshi NG dailies skip Fridays, so this is a futures-leg trade, not a Kalshi one; (2) the one-week partial reversal of storage surprises, conditioned on analyst dispersion; (3) the pre-announcement half of the announcement-day return appearing only on days storage comes in ABOVE consensus. Each is a falsifiable claim we can score with the machinery we already have.",
  "Trade the roll. CFTC data says manual participation spikes for a few days each monthly roll and that spread trading is structurally more manual. That is a recurring, scheduled window of reduced machine density in exactly the instrument we trade. Our existing per-leg roll handling means we can identify these days precisely.",
  "Time-of-day hygiene: avoid initiating into 10:30 ET Thursday, avoid the 14:28-14:30 ET settlement window, and be aware that the first second of each minute carries TWAP prints that are execution flow, not information. If our flow reader is scoring signed flow in those slices it is scoring somebody's schedule, not somebody's opinion.",
  "Do not try to beat Citadel's weather forecast. They have ~24 meteorologists, pay $750k-$1m for the best, and the commodities book makes roughly $4bn a year largely on gas. The raw NWP input (GFS 00/06/12/18Z, ECMWF 00/12Z) is free and simultaneous for everyone. Our target must be the CONVERSION - the burn stack - not the meteorology. This is also, per our own retired burn_conversion_gate, the part we have empirically found hardest, which is a sign it is the right part to work on.",
  "Expect the water to get deeper. CME set an all-time NG single-day record of 2.58m contracts in January 2026, options records alongside it, and structural LNG plus data-centre demand is pulling in more capital. Rising volume is good for our fills and bad for our edge decay rate; assume any anomaly we find has a shorter half-life than the published sample suggests.",
  "The single most useful competitive fact in this whole survey: natural gas is where the machines are LEAST established among liquid energy contracts (31.7% HFT share vs 53.9% in WTI, and NG is a named non-result in the CFTC market-quality regressions). If the desk ever considers widening to a second instrument, that ranking should push us toward NG-adjacent physical markets and AWAY from crude, ES or FX."
 ],
 "sources": [
  "https://www.cftc.gov/sites/default/files/idc/groups/public/@economicanalysis/documents/file/oce_automatedtrading.pdf",
  "https://www.cftc.gov/sites/default/files/2019-04/oce_automatedtrading_update.pdf",
  "https://www.cftc.gov/sites/default/files/2022-07/HFT_and_market_quality_07.07.2022_ada.pdf",
  "https://www.cftc.gov/sites/default/files/filings/orgrules/16/05/rule052716nymexdcm007.pdf",
  "https://www.cftc.gov/media/1691/Impact%20of%20Automated%20Orders%20in%20Futures%20Markets/download",
  "http://www.haawks.com/blog/2026/7/16/natural-gas-futures-drop-39-ticks-in-11-seconds-after-eia-storage-report",
  "https://doi.org/10.5547/01956574.42.2.mpro",
  "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3575861",
  "https://experts.umn.edu/en/publications/trader-attention-and-market-reaction-to-fundamental-news-evidence/",
  "https://onlinelibrary.wiley.com/doi/10.1002/fut.70104",
  "https://ideas.repec.org/a/aen/journl/ej40-5-ederington.html",
  "https://doi.org/10.5547/01956574.41.5.afer",
  "https://www.sciencedirect.com/science/article/abs/pii/S014098831500208X",
  "https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2742734_code434076.pdf?abstractid=2657224",
  "https://arxiv.org/pdf/1909.09495",
  "https://arxiv.org/pdf/1011.6402",
  "https://www.tandfonline.com/doi/full/10.1080/14697688.2023.2236159",
  "https://www.ice.com/white-paper/natural-gas-market-storage-dynamics-and-alpha-generation",
  "https://www.reedsmith.com/articles/algorithmic-trading-power-gas-markets-uses-trends-eu-uk-united-states/",
  "https://www.hedgeweek.com/hedge-funds-hiring-meteorologists-to-weather-market-volatility/",
  "https://thehedgefundjournal.com/statar-capital/",
  "https://www.hedgeweek.com/statar-capital-makes-strong-comeback-amid-volatile-energy-market/",
  "https://link.springer.com/chapter/10.1007/978-981-96-6998-1_8",
  "https://onlinelibrary.wiley.com/doi/full/10.1002/rfe.1228",
  "https://www.nber.org/system/files/working_papers/w22793/w22793.pdf",
  "https://macrosynergy.com/research/commodity-carry-as-a-trading-signal-part-1/",
  "https://www.cmegroup.com/articles/faqs/micro-henry-hub-natural-gas-futures-and-options-frequently-asked-questions.html",
  "https://www.cmegroup.com/articles/faqs/market-by-order-mbo.html",
  "https://www.cmegroup.com/media-room/press-releases/2026/1/21/cme_group_sets_newrecordinnaturalgasfuturesandoptions.html",
  "https://www.eia.gov/todayinenergy/includes/sparkspread_explain.php",
  "https://www.eia.gov/todayinenergy/detail.php?id=45037",
  "https://ir.eia.gov/ngs/ngs.html",
  "https://www.blockhead.co/2026/02/10/jump-trading-stakes-bets-on-prediction-market-boom-with-kalshi-polymarket-deals/",
  "https://www.rbccm.com/en/insights/2026/05/natural-gas-powers-the-data-center-boom",
  "https://www.iea.org/reports/gas-market-report-q1-2026/executive-summary",
  "https://www.stern.nyu.edu/sites/default/files/assets/documents/con_035928.pdf",
  "https://www.enverus.com/blog/every-degree-moves-the-market-why-point-forecasting-beats-gfs-for-natural-gas-traders/",
  "https://montel.energy/resources/blog/the-rise-of-quant-power-trading-data-algorithms-and-speed"
 ]
}
```

## LENS

```json
{
 "lens": "WHO IS ACTUALLY IN HENRY HUB NATURAL GAS, AND IN WHAT SIZE. Built from CFTC disaggregated Commitments of Traders raw files (parsed directly, futures-only and futures+options, report date 2026-07-28, plus 2010/2015/2020/2025 year-end archives for the trend), CFTC Office of the Chief Economist research (Haynes and Roberts account-level CME transaction study; the CFTC HFT/market-quality study using regulatory account data), CFTC DMO's 2019 automated-orders report, the Irwin-Sanders-Yan index-roll event study, CME volume records, fund prospectus roll mechanics, and trade/practitioner reporting on prop firms, banks, merchants and producers. HEADLINE: NYMEX Henry Hub is NOT a fast market by futures standards. It is the least-automated major energy contract, its liquidity providers rest orders for seconds not microseconds, and its center of gravity has shifted from flat-price hedging to managed-money CALENDAR SPREAD positioning - a third of open interest. Meanwhile the real commercial hedging has largely migrated OFF the NYMEX screen into cleared ICE Henry Hub swaps, which are now LARGER than NYMEX NG in Btu terms. The price-insensitive flows people usually name (ETFs, index rolls) are numerically trivial, and the index-roll edge has been arbitraged away since 2012.",
 "findings": [
  {
   "topic": "CFTC disaggregated COT, NYMEX Henry Hub NG (10,000 MMBtu) - the participant map with real numbers",
   "what_is_actually_done": "Report date 2026-07-28, futures-only. Total open interest 1,672,441 contracts (16.7 Tcf notional, roughly 5.7 months of US consumption). Shares of OI: Producer/Merchant/Processor/User 13.3% long / 14.3% short; Swap Dealers 12.9% long / 1.1% short / 6.7% spreading; Managed Money 14.3% long / 20.6% short / 33.4% SPREADING; Other Reportables 3.2% / 8.2% / 13.0% spreading; Non-reportable (retail/small) 3.3% long / 2.6% short. Futures+options combined is near-identical (OI 1,683,026). Trader counts: 327 total reportable; Managed Money 65 long / 67 short / 82 spreading; Producer/Merchant 46 long / 41 short; Swap Dealers 27 long / only 9 short. Concentration: top 4 traders gross 18.1% of long OI / 25.3% of short OI; top 8 gross 27.8% / 36.5%. Net basis top 4: 9.4% long / 11.1% short. READ: this is a ~330-firm club, not a crowd. The single largest identifiable bloc is managed-money SPREAD positioning, not flat-price anything. Producers are NOT the dominant short they are assumed to be - they are 14.3%.",
   "evidence": "CFTC weekly disaggregated COT raw files f_disagg.txt and c_disagg.txt, contract code 023651, parsed field-by-field (fields 8-22 positions, 119-132 trader counts, 161-168 concentration ratios). Cross-checked against the CFTC legacy NYMEX report (deanymesf.htm), which shows the same 1,672,441 OI and 327 traders.",
   "timescale": "weekly reporting; positions held weeks to months"
  },
  {
   "topic": "THE 16-YEAR STRUCTURAL SHIFT - the single most useful table in this research",
   "what_is_actually_done": "Same contract, year-end snapshots, share of OI. 2010-12-28 (OI 760,034): Prod/Merc 7.2L/9.9S; Swap 28.8L/5.0S/7.6Sp; Managed Money 13.9L/31.6S/3.3Sp; Non-reportable 10.2L/5.0S; 278 traders. 2015-12-29 (OI 982,886): Prod/Merc 15.7/16.7; Swap 21.6L/1.8S/7.4Sp; MM 18.5L/35.4S/15.4Sp; Non-rept 6.3/4.0; 292 traders. 2020-12-29 (OI 1,162,374): Prod/Merc 17.7/23.8; Swap 15.9L/12.2S/7.1Sp; MM 19.4L/16.9S/20.3Sp; Non-rept 5.2/3.6; 303 traders. 2025-12-30 (OI 1,533,985): Prod/Merc 14.7/15.0; Swap 12.1L/2.3S/9.7Sp; MM 11.2L/16.6S/34.8Sp; Non-rept 3.5/2.9; 298 traders. 2026-07-28: MM spreading 33.4%. FOUR TRENDS: (1) Managed-money SPREADING went 3.3% -> 15.4% -> 20.3% -> 34.8% of OI. The systematic money moved from flat price to term structure. (2) Swap-dealer long collapsed 28.8% -> 12.9% - the index/passive-long era is over. (3) Retail/non-reportable collapsed 10.2% -> 3.3% long. Retail is a rounding error on NYMEX. (4) Open interest more than DOUBLED while the reportable trader count went 278 -> 327, essentially flat. Same number of firms, twice the risk each.",
   "evidence": "CFTC historical disaggregated archives fut_disagg_txt_2010/2015/2020/2025.zip parsed directly; market name changes from 'NATURAL GAS - NEW YORK MERCANTILE EXCHANGE' to 'NAT GAS NYME' but contract code 023651 is continuous.",
   "timescale": "multi-year structural"
  },
  {
   "topic": "THE HEDGERS ARE NOT ON THE NYMEX SCREEN - ICE cleared Henry Hub is bigger",
   "what_is_actually_done": "Same COT date. NAT GAS ICE LD1 (ICE Futures Energy Div, 2,500 MMBtu units): open interest 8,028,413 contracts = 2,007,103 NYMEX-equivalents, i.e. 20% LARGER than NYMEX NG itself. Its composition is the mirror image of NYMEX: Producer/Merchant 57.7% long / 30.0% short; Swap Dealers 10.1% long / 38.7% SHORT; Managed Money only 7.8L/5.5S/11.0Sp; non-reportable 0.6/0.3. Only 281 traders. NAT GAS ICE PEN adds another 761,304 (2,500 MMBtu). NYMEX Henry Hub Penultimate Financial adds 256,044 (10,000 MMBtu) and is 34.1% swap-dealer long. IMPLICATION FOR A SCREEN-WATCHING DESK: the commercial hedge flow that actually sets the seasonal balance is overwhelmingly transacted as cleared swaps/EFS into ICE LD1, not as visible NYMEX aggressor flow. What you see on the NYMEX tape is disproportionately speculative and spread-driven. Do not build a model that assumes the tape shows you the hedgers - it largely does not.",
   "evidence": "CFTC f_disagg.txt, contract codes 023391 (ICE LD1), 023392 (ICE PEN), 03565C (NYMEX HH Penultimate), 023651 (NYMEX NG); unit sizes read from the file's own contract-units field; NYMEX-equivalent conversion is my arithmetic (2,500 / 10,000 MMBtu).",
   "timescale": "weekly reporting; structural"
  },
  {
   "topic": "HFT market share in natural gas futures - the hard regulatory number",
   "what_is_actually_done": "CFTC economists using account-level regulatory trade-capture data (Part 16.02 TCR), classifying accounts as HFT by behavior (>0.25% of annual volume, end-of-day inventory <20% of volume, never >30% of daily volume held intraday). HFT market share: NATURAL GAS 12.9% (2012) -> 31.7% (2020), +145.8%, full-sample average 24.5%. Compare WTI CRUDE 29.1% -> 53.9%, average 52.1%; Gold 20.6% -> 48.1%; E-mini S&P 31.8% -> 49.7%; Euro FX 57.0% -> 46.2% (falling). NATURAL GAS IS THE LEAST HFT-PENETRATED CONTRACT IN THEIR ENERGY/METALS/FINANCIALS SET - roughly HALF of crude's HFT share. The paper's substantive finding: HFT participation improves traded bid-ask spreads and Amihud price impact through market making, but when HFTs trade AGGRESSIVELY to reduce their own inventory, market quality degrades - the damage comes in the moments they are unwinding, not the moments they are quoting.",
   "evidence": "CFTC Office of the Chief Economist, 'High-Frequency Trading and Market Quality: Evidence from Futures Markets', Table 1 (HFT Market Share Summary) and abstract; SSRN 4069573.",
   "timescale": "annual shares; intraday behavior"
  },
  {
   "topic": "Automated vs manual share of natural gas volume, and manual-on-both-sides",
   "what_is_actually_done": "CFTC study of ALL CME transactions Nov 2012 - Oct 2014 using the FIX Tag 1028 manual/automated order flag. Energy product group overall: 16.8% non-electronic, 46.9% ATS, 36.4% manual. ENERGY - NATURAL GAS subgroup (40 products): 21.2% non-electronic, 54.3% ATS, 40.2% manual. For the Henry Hub contract specifically (153mm contracts of volume in the sample): ATS-ATS 30.7%, ATS-MANUAL 45.8%, MANUAL-MANUAL 19.1%. Compare E-mini S&P MAN-MAN 13.8%, Euro FX 4.4%, Japanese Yen 3.5%. Nearly ONE IN FIVE Henry Hub trades had a human on BOTH sides. Trend context: CFTC DMO's follow-up (2013-2018) found the ATS order share rose ~19% on average for Energy/Metals/Grains/Oilseeds/Livestock versus ~7% for Currencies/Equities/Financials, and attributed persistently lower automation in physical commodities to higher basis risk against the cash market and delivery-spec complexity. HONEST GAP: I could not find a published NG-specific automation share after 2020. Treat 31.7% HFT (2020) and rising as the best available anchor, not a current number.",
   "evidence": "Haynes and Roberts, 'Automated Trading in Futures Markets', CFTC OCE, Tables 2, 3, 4, 5 (extracted from the source PDF). CFTC DMO, 'Impact of Automated Orders in Futures Markets', March 2019, Exhibit 2 narrative.",
   "timescale": "per-trade classification; multi-year trend"
  },
  {
   "topic": "SPEED: how long a resting order actually sits in natural gas",
   "what_is_actually_done": "Measuring time between passive order entry/modification and execution: about 40% of executed passive orders fill within ONE SECOND in Euro and Yen futures, about 20% in Treasury and S&P futures. In physical commodities it is far slower - 'over 90 percent of passive executed corn orders remained in the book longer than one second, as are 85 percent of natural gas futures.' Also: in the E-mini, automated orders outnumber manual by ~11:1 among fills inside 100ms but under 2:1 among fills in the 10s-1min bucket; in gold the ratio is only 2.3:1 at <100ms and 1.9:1 at 1-10s - in physical commodities there is 'a greater balance in the liquidity provision by manual and automated traders'. In the E-mini, automated traders supply 3x the liquidity of manual up to 10 seconds; in gold barely 2x. Separately, CFTC DMO found ATS orders are 'almost exclusively limit orders', while manual orders are stop 4% / market 11% of the time - automated traders SYNTHESIZE stops and market orders by watching prices and firing limits, which is why price cascades cannot be explained by resting stop orders alone.",
   "evidence": "Haynes and Roberts, CFTC OCE, section on liquidity provision speed (Figures 1-3, Tables 6-7). CFTC DMO 2019, Exhibit 5 and accompanying market-participant interviews.",
   "timescale": "microsecond to tens of seconds"
  },
  {
   "topic": "Where machine speed genuinely concentrates intraday",
   "what_is_actually_done": "Charting aggressive volume by 5-minute bucket, the CFTC found pronounced spikes in ATS aggressive share in CRUDE OIL at (a) the daily settlement window and (b) the 10:30 AM release of weekly inventory data - 'It is during these periods when the benefits of speed is often greatest.' Explicitly: 'Similar trends in the other commodities are more muted, outside of an increase in automated participation at the electronic market open for the E-mini contract.' The natural-gas analogue is the Thursday 10:30 ET EIA weekly storage print. There is documented sub-second/pre-release activity around EIA gas releases (the January 31, 2013 episode where trading in NG futures and ETFs exploded roughly 400ms before the official release). The academic verdict on pre-announcement drift in NG is important and encouraging for a research desk: Gu (Journal of Futures Markets, 2018) finds the difference between the median forecast of HIGH-ACCURACY analysts and the consensus forecast PREDICTS inventory surprises and explains part of the pre-announcement drift - concluding the informed trading is driven by SUPERIOR FORECASTING rather than leakage. Gay et al. (2009) similarly find analysts facilitate price discovery ahead of the storage print.",
   "evidence": "Haynes and Roberts, CFTC OCE, Figure 4 discussion. Gu, 'What drives informed trading before public releases? Evidence from natural gas inventory announcements', Journal of Futures Markets 2018. Gay et al., 'Analyst forecasts and price discovery in futures markets: the case of natural gas storage', Journal of Futures Markets 2009.",
   "timescale": "milliseconds at the print; hours to days for the forecast edge"
  },
  {
   "topic": "INDEX ROLL FLOW - the classic 'price-insensitive flow' trade is DEAD",
   "what_is_actually_done": "S&P GSCI rolls on business days 5-9 of each month (80/20, 60/40, 40/60, 20/80, 0/100), monthly for energy. Irwin, Sanders and Yan ran a 40-year event study (1980-2019) across 19 GSCI markets. Findings: the nearby/deferred spread compresses a maximum of only 30-40 bp during the roll window and FULLY REVERSES afterward - the impact is temporary. Total order-flow cost paid by index investors 1991-2019 was $29bn, but $23bn of that ($2.9bn/yr) was concentrated in 2004-2011; average annual cost fell to $474 MILLION in 2012-2019, an over-80% decline, attributed to a sunshine-trading effect plus electronic trading raising liquidity supply. Post-2012 the annualized roll cost is 0.64% in the roll window (vs 4.36% in 2004-2011), and per-roll spread impacts in the post-financialization period are 'generally small in magnitude (below 10 basis points)' and often statistically insignificant. TRANSLATION: everyone knows the schedule, so the flow is pre-supplied. Do not build a Goldman-roll front-run. BCOM's 2026 natural gas target weight is 7.20%, down from 7.78%.",
   "evidence": "Irwin, Sanders and Yan, 'The Order Flow Cost of Index Rolling in Commodity Futures Markets', Applied Economic Perspectives and Policy (working paper PDF, Tables 3-5, Figure 5). S&P GSCI methodology document; Bloomberg BCOM 2026 target weights announcement.",
   "timescale": "5-day monthly window; effect fully reverses"
  },
  {
   "topic": "ETF flows - genuinely price-insensitive, genuinely scheduled, and genuinely SMALL",
   "what_is_actually_done": "UNG's roll rule is published and mechanical: the benchmark shifts from near month to next month over FOUR days beginning at the end of the day TWO WEEKS prior to near-month expiration, weighted 75/25, 50/50, 25/75, then 0/100; USCF rolls the actual position across those four days. AUM roughly $420-476M. At ~$32,000 per NG contract that is ~13,000-15,000 contract-equivalents = under 1% of NYMEX NG open interest (my calculation). BOIL (2x, ~$334-398M) and KOLD (-2x, ~$97M) must rebalance DAILY into settlement, and the arithmetic is fixed: rebalance notional = AUM x return x L x (L-1), which is 2x AUM x r for BOIL and 6x AUM x r for KOLD, and BOTH BUY on an up day. On a 5% NG move that is roughly $64M, about 2,000 contracts, all one direction, concentrated near settlement (my calculation; treat the AUM inputs as approximate). VERDICT: direction and timing are knowable, but the size is small versus a market that traded a record 2,576,346 contracts in a single day. This is a settlement-window texture effect, not a driver.",
   "evidence": "UNG prospectus/424B3 benchmark and roll language (SEC EDGAR CIK 1376227); ProShares BOIL/KOLD fund pages and AUM aggregators; CME single-day natural gas complex record 2,576,346 contracts on 2026-01-20, up 15% on the prior record 2,239,081 (2018-11-14). Rebalance formula and contract-count conversions are my own arithmetic.",
   "timescale": "daily rebalance at settlement; 4-day scheduled roll"
  },
  {
   "topic": "Physical hedgers - producers, and why their flow is lumpy and calendar-linked but NOT reliably anticipatable",
   "what_is_actually_done": "Producer hedging is discretionary and has been SHRINKING. FIA MarketVoice, analyzing independent producers representing ~38% of US gas production: gas hedge coverage fell to 46% of current-year production from 58% year-on-year, with 35% of the following year and 15% of the year after covered - 'the lowest level in at least five years'. Producers also shifted structurally from options to swaps (adding ~589 MMcf/d of swaps while cutting ~219 MMcf/d of options). Current examples: Antero has 61% of remaining 2026 gas hedged (43% swaps at a $3.91 floor, 18% collars $3.25 x $5.66); EQT - the largest US gas producer - plans to keep the MAJORITY of 2026 and beyond UNHEDGED. EQT has explicitly tilted hedges to specific halves of a year to preserve upside elsewhere. HONEST READ: producer hedging is not a metronome. It clusters after earnings, after price rallies through internal trigger levels, and around budget/borrowing-base seasons, and it now increasingly lands as cleared ICE swaps rather than NYMEX screen flow. There is a real behavioral pattern (hedge into strength) but it is not a schedule you can set a clock to.",
   "evidence": "FIA MarketVoice, 'US energy producers reduce hedging to capture upside from higher prices' and 'US oil and gas producers shift to rainy day hedging strategies as prices rise'; Antero Resources Q1/Q2 2026 results and presentations; EQT 10-Q FY2026 commodity risk management disclosure.",
   "timescale": "quarterly decisions; multi-month positions"
  },
  {
   "topic": "Physical hedgers - utilities and LNG exporters, the genuinely price-insensitive cohort",
   "what_is_actually_done": "Regulated LDC/utility hedging is the one cohort that is price-insensitive BY DESIGN AND BY REGULATION. Programmatic protocols involve 'systematic, periodic purchases of futures or options for a given future month, with a portion of a future requirement accomplished on a schedule REGARDLESS OF THE PRICE', typically layered monthly over a preceding period; discretionary market-timing protocols are explicitly SUBORDINATE to the programmatic and defensive protocols. Regulators generally leave strategy to the utility with incentive mechanisms attached (e.g. CPUC allowing 75% of each hedging purchase outside the incentive mechanism, winter months only). LNG exporters hedge Henry Hub exposure on feedgas: Cheniere and Venture Global use NYMEX futures and OTC swaps, typically covering roughly 30-70% of anticipated annual volumes; Cheniere's SPAs are priced at ~115% of Henry Hub plus a $2.25-3.50/MMBtu fee, and newer IPM deals push the firm toward JKM/TTF spread capture. Venture Global Phase 1 alone is up to 2.0 Bcf/d of feedgas - one of the largest single demand points in the US. TAKEAWAY: the utility layer is the most anticipatable flow in the whole complex (calendar-driven, price-blind, winter-weighted), but it is dispersed across hundreds of small entities, executed OTC or via brokers, and reported nowhere in time to trade on.",
   "evidence": "Fortnightly, 'Natural Gas Hedging: A Primer for Utilities and Regulators'; Gettings, 'Regulation of Utility Hedging Practices' (SURFA); CPUC hedging incentive-allocation decision; NJ BPU gas purchasing and hedging report. Cheniere/Venture Global structure per CME Henry Hub benchmark whitepaper and LNG trade coverage.",
   "timescale": "monthly programmatic layering; seasonal"
  },
  {
   "topic": "The prop firms and market makers actually on the other side",
   "what_is_actually_done": "FIA Principal Traders Group membership (automated liquidity providers registered as principals) includes Allston Trading, ARB Trading Group, Citadel Securities, Cognitive Capital, DRW Holdings, Eagle Seven, Flow Traders US, Geneva Trading USA, Hard Eight Futures, Hehmeyer, Hudson River Trading, IMC Financial Markets, Jump Trading, Liger, Marquette Partners, Optiver US, Quantlab, WH Trading, XR Trading. These are the firms most likely quoting NG outrights and spreads. NOTE the distinction that matters: none of these is the biggest NG risk-taker. THE BIGGEST COMBINED DISCRETIONARY-AND-SYSTEMATIC GAS BOOK IS CITADEL - its commodities group has 260+ investment professionals and ~100 engineers across 12 locations and made about $4bn of profit in a year 'driven by natural gas trading'; it bought Paloma Natural Gas (Haynesville) for roughly $1-1.2bn, bought German power trader FlexPower, and is hiring power and refined-products PMs from Shell and Goldman. Macquarie became the world's largest commodity bank and one of the biggest US natural gas traders, though it has been cutting energy risk and losing traders through 2025. Goldman and Morgan Stanley remain but are smaller in gas than Macquarie. Physical merchants with asset-backed optionality - Vitol, Trafigura, Mercuria, Gunvor, Freepoint, Hartree, Castleton (CCI), Glencore - trade the storage and pipeline-transport option, i.e. they monetize LOCATION and TIME spreads, which is precisely why managed-money and merchant spreading dominates open interest.",
   "evidence": "FIA Principal Traders Group membership listing; Hedgeweek, 'Citadel builds commodities empire beyond hedge fund roots'; Businesswire/Bloomberg on Citadel-FlexPower and Citadel Australia power hires; Bloomberg, 'Australian Bank Macquarie Loses Oil Traders as It Cuts Back on Risk'; Castleton Commodities merchant natural gas business description.",
   "timescale": "microsecond (PTG quoting) to multi-month (Citadel and merchant positions)"
  },
  {
   "topic": "Systematic CTAs and trend followers in natural gas",
   "what_is_actually_done": "Trend-following capital reaches NG mainly through diversified managed-futures programs benchmarked to the SG CTA Index (20 managers) and SG Trend Index (10 largest trend CTAs). NG is one line in a 50-200 market portfolio, typically risk-weighted down because its volatility is the highest of any major futures contract. 2025 was a poor year for commodity trend: after a weak H1, indices recovered on equities and softs while 'reversals in energy' were an explicit drag. PRACTICAL CONSEQUENCE: CTA flow in NG is a MEDIUM-TERM, VOLATILITY-SCALED, SIGNAL-TRIGGERED flow. It is momentum-confirming, it delevers when realized vol spikes (which in NG is exactly when the move is happening), and it is broadly forecastable in DIRECTION from published trend-signal proxies but not in timing. The COT reading is consistent: managed-money FLAT positions are only 14.3% long / 20.6% short - much smaller than the 33.4% spreading. Trend followers are not the dominant managed-money activity in NG; relative value is.",
   "evidence": "Societe Generale SG CTA and SG Trend index construction; Alternatives Watch, 'CTAs and trend-following hedge funds fight back after H1 rout' (September 2025); Top Traders Unplugged trend performance reports; CFTC COT managed-money breakdown above.",
   "timescale": "weeks to months"
  },
  {
   "topic": "Options, and why the options book increasingly drives the futures tape",
   "what_is_actually_done": "Henry Hub options set a record 811,662 contracts in a single session (up 28% on the prior record) during the January 2026 cold. CME reports 99% of WTI and Henry Hub RFQs get a response in under one second, and the share of its benchmark crude options traded ON SCREEN went from 20% to 70% in three years - energy options have electronified fast. ICE's global gas futures and options open interest hit 40.2m contracts (+29% y/y) with North American Henry Hub OI +33%. The mechanism that matters to a futures-tape reader: producer collars and three-way collars leave dealers with structural options positions, and dealer delta/gamma hedging converts option open interest into MECHANICAL, PRICE-CONTINGENT futures flow - long-gamma dealers sell rallies and buy dips (volatility-dampening), short-gamma dealers do the reverse (volatility-amplifying). This is a real, non-discretionary flow whose sign flips at strike concentrations and around monthly option expiry (NG options expire one business day before the futures last trade day).",
   "evidence": "CME Group January 2026 natural gas records press release (mirrored via PR Newswire and Barchart); CME, 'CME Direct RFQ: The Best Source of Liquidity for Energy Options Strategies' (2025); ICE record open interest release (April 2024); FIA MarketVoice on producer collar and three-way structures.",
   "timescale": "continuous delta hedging; sign flips at expiry"
  },
  {
   "topic": "Retail, and the Kalshi venue",
   "what_is_actually_done": "On NYMEX NG, retail is functionally absent: non-reportable positions are 3.3% of OI long and 2.6% short, down from 10.2%/5.0% in 2010. The ETF complex (UNG+BOIL+KOLD) is roughly 1.7% of NG open interest in aggregate (my calculation). Retail concentration has migrated to venues like Kalshi, which did $21.1bn of notional in June 2026 versus Polymarket's $9.7bn and claims 90%+ of US prediction-market activity with institutional volume up 800% in six months - but volume is overwhelmingly SPORTS ($5.1bn in the first week of the FIFA World Cup alone). Kalshi lists natural gas markets, but I found NO published data on natural-gas-specific liquidity, market-maker identity, or institutional participation there. HONEST STATEMENT: I could not verify who makes the Kalshi NG daily market. Given the size disparity (a Kalshi NG daily is a rounding error against 2.5m NYMEX contracts), the plausible read is that the flow is thin, retail-dominated, and quoted by a small number of automated participants arbitraging the futures - which is exactly consistent with a persistent futures-to-Kalshi repricing lag existing at all.",
   "evidence": "CFTC disaggregated COT non-reportable series 2010-2026; ETF AUM figures and my contract-equivalent arithmetic; Kalshi volume reporting via Investing.com analysis of prediction-market volumes, June 2026.",
   "timescale": "seconds (Kalshi repricing) to daily"
  }
 ],
 "where_machines_dominate": [
  "THE FIRST 1-3 SECONDS AFTER A SCHEDULED NUMBER. The CFTC's own intraday chart shows aggressive ATS share spiking at the 10:30 ET inventory release and at settlement, and states plainly that this is where 'the benefits of speed is often greatest'. The Thursday 10:30 EIA gas storage print is the NG analogue, and there is documented sub-second activity around EIA gas releases. Do not attempt to trade the print itself on either NYMEX or Kalshi. Trade the FORECAST of the print, which is a different game entirely.",
  "TOP-OF-BOOK MARKET MAKING IN THE FRONT MONTH. FIA PTG firms (DRW, Optiver, IMC, Jump, Citadel Securities, HRT, Flow Traders, Geneva, XR, WH) exist to capture the spread and manage adverse selection in microseconds. HFT share of NG volume was 31.7% in 2020 and rising. You cannot be the passive quote at the inside and expect to survive adverse selection without colocation.",
  "INTRA-COMMODITY AND INTER-COMMODITY SPREAD ARBITRAGE AT THE MILLISECOND LAYER. CME implied-spread functionality is active in physical commodities, meaning outright and spread books are machine-linked. Any mispricing between NG outright legs and the calendar spread is closed automatically.",
  "CROSS-VENUE ARBITRAGE NYMEX <-> ICE LD1 <-> penultimate <-> basis. Four correlated Henry Hub instruments with roughly 3.7m NYMEX-equivalent contracts of combined open interest and only ~330 firms; the pricing relationships between them are machine-maintained.",
  "THE SETTLEMENT WINDOW. ATS aggressive share spikes there; leveraged-ETF rebalance, index roll and marking flow all concentrate there, and the machines know every schedule exactly.",
  "RAW OPTION-SURFACE MARKET MAKING. 99% of Henry Hub RFQs answered in under one second, and screen share of energy options went 20% -> 70% in three years. Quoting a vol surface against Optiver, IMC and Citadel Securities is not a contest."
 ],
 "where_machines_are_weak": [
  "NATURAL GAS IS THE LEAST AUTOMATED MAJOR ENERGY CONTRACT, MEASURED. HFT share 31.7% (2020) versus WTI 53.9%; full-sample average 24.5% versus crude's 52.1%. In the CME-wide flag study, 19.1% of Henry Hub volume had a HUMAN ON BOTH SIDES - versus 4.4% in Euro FX and 13.8% in the E-mini. The CFTC's own explanation is structural and durable: physical commodities carry high basis risk against a complicated cash market with delivery specifications, which is exactly the reasoning a machine handles badly and a knowledgeable human handles well.",
  "RESTING ORDERS IN NG ARE NOT IN A MICROSECOND RACE. 85% of executed PASSIVE natural gas orders sat in the book longer than one second, against roughly 40% of Euro/Yen passive fills clearing INSIDE one second. In physical commodities the automated-to-manual liquidity-provision ratio at sub-100ms is only about 2:1, against roughly 11:1 in the E-mini. A maker-first, non-colocated desk resting orders on a seconds-to-minutes horizon is operating in a time domain where the machines do not have an overwhelming edge.",
  "THE FORECAST, NOT THE REACTION. Gu (2018) finds pre-announcement drift ahead of EIA gas storage is explained by SUPERIOR FORECASTING - high-accuracy analysts' median versus consensus predicts the surprise - rather than leakage. That is a research edge with a multi-day half-life, sitting upstream of the millisecond game, and it is exactly the ground a desk with a deep conditioned-analog library should be fighting on.",
  "THE WEATHER-TO-BALANCE-TO-PRICE STACK. The mapping from a model run to gas-weighted degree days to power burn to the storage balance is a multi-step causal chain with renewables, coal and nuclear displacement, and freeze-off nonlinearity in the middle. Model runs land on a fixed cadence (GFS four times daily, ECMWF twice daily, plus ensembles), and the disagreement between models by demand region is where the real disagreement lives. Machines can read the number; converting it into a burn forecast is where the mistakes get made - and the whole market makes them, not just you.",
  "EVENTS THAT ARE NOVEL RATHER THAN RECURRING. The CFTC HFT study finds the damage HFTs cause is concentrated when they trade AGGRESSIVELY to reduce inventory. That is the regime where machine liquidity is a taker, not a maker - the moments when the book empties and a participant who knows what the move MEANS can transact against forced flow.",
  "THE INDEX-ROLL TRADE IS ALREADY DEAD, AND THAT IS USEFUL INFORMATION. Roll spread impact fell from 30-40bp to under 10bp and is often statistically insignificant post-2012; annual roll cost fell from $2.9bn to $474m. This tells you where NOT to look, and by implication that the surviving edges in NG are informational, not mechanical."
 ],
 "implications_for_us": [
  "THE MARKET YOU ARE FORECASTING IS NOT THE MARKET YOU THINK. A third of NYMEX NG open interest is MANAGED-MONEY CALENDAR SPREAD (33.4%, up from 3.3% in 2010). Managed-money FLAT positions are only 14.3% long / 20.6% short. If your daily-move model is implicitly a flat-price supply/demand model, you are modelling a minority of the positioning. The marginal risk-taker in NG is expressing a TERM STRUCTURE view, which means front-month day-moves are frequently a byproduct of spread rebalancing rather than a fresh directional opinion. This is a first-order candidate explanation for residual magnitude error and for days where a correct fundamental read produces the wrong day-net.",
  "THE HEDGERS ARE OFF-SCREEN. ICE cleared Henry Hub LD1 alone is 2.0m NYMEX-equivalent contracts - larger than NYMEX NG's 1.67m - and is 57.7% producer/merchant long and 38.7% swap-dealer short. Your NYMEX tape does not show you the commercial hedge flow. Any order-flow signal, including the dipole, is reading a tape that is disproportionately speculative and spread-driven. That does not invalidate the dipole; it means the dipole is measuring speculative leadership changeovers, and its claims should be scoped to that, not to 'the market'.",
  "YOUR NON-COLOCATION IS LESS DISQUALIFYING IN NG THAN IN ANY OTHER LIQUID ENERGY CONTRACT. 85% of NG passive fills rest longer than a second; the automated-to-manual liquidity-provision ratio at sub-100ms is roughly 2:1 not 11:1; 19.1% of volume is human-on-both-sides. The maker-first conclusion from your own S100 lag-map work (taker does not clear the regime) is independently corroborated by CFTC data on the resting-time distribution. Rest orders on a seconds-to-minutes horizon and you are in the part of the distribution where NG actually trades.",
  "STOP TREATING THE 10:30 THURSDAY PRINT AS A TRADEABLE MOMENT AND START TREATING IT AS A FORECASTABLE OBJECT. The published finding is that pre-announcement drift is driven by superior forecasting, and that high-accuracy analysts' deviation from consensus predicts the surprise. That is a directly testable, non-latency edge your existing analyst-consensus data plane can address. It also sharpens a known weakness: your own record shows EIA Thursdays were 3,530 of G20's 7,880 error. The day class you are worst on is the day class where the literature says a forecasting edge exists.",
  "THE 'ANTICIPATABLE FLOW' LIST IS SHORTER AND SMALLER THAN THE FOLKLORE SUGGESTS. Index roll: dead (impact under 10bp post-2012, fully reversing, often insignificant). ETFs: UNG is under 1% of open interest; BOIL+KOLD daily rebalance is roughly 2,000 contracts on a 5% move. Retail: 3.3% of open interest. The genuinely price-insensitive, calendar-locked flow that remains is UTILITY PROGRAMMATIC HEDGING (systematic monthly layering 'regardless of the price', winter-weighted, regulator-blessed) and LNG FEEDGAS hedging (30-70% coverage against fixed export commitments). Neither prints on a screen you can watch, but both are seasonal and both belong as structural priors in the weather-to-balance stack rather than as tradeable events.",
  "DEALER GAMMA IS A MISSING BLOCK IN YOUR STATE. Henry Hub options set a record 811,662-contract session; producer collars and three-ways leave dealers with structural gamma; delta hedging turns that into mechanical, price-contingent futures flow whose SIGN flips at strike concentrations and around option expiry (one business day before futures last trade day). You already have an options_surface store and a known strike-ladder gap. Given the size of the options complex now, an option-open-interest-by-strike block is a higher-value input than another flow refinement - it explains WHY a level holds or gives way, which no order-flow read can.",
  "THE COUNTERPARTY YOU SHOULD ACTUALLY WORRY ABOUT IS NOT AN HFT. It is Citadel - 260+ investment professionals, ~100 engineers, roughly $4bn of profit driven by natural gas, now owning Haynesville production (Paloma) and physical optionality - alongside the merchants (Vitol, Trafigura, Mercuria, Freepoint, Hartree, CCI) with storage and transport books, and Macquarie. These desks hold the same weather models you do PLUS proprietary nomination, pipeline-flow and storage-position data you do not. On FUNDAMENTAL LEVEL, in the front of the curve, on a multi-day horizon, you are outgunned and should say so plainly. Your defensible ground is (a) the venue-lag microstructure they do not bother with, (b) the conditioned-analog library, and (c) day-class specialization - not competing on the gas balance itself.",
  "A HONEST GAP TO CLOSE: I could not find any published NG automation share after 2020, nor any data at all on who market-makes Kalshi's natural gas contracts. Treat 31.7% HFT (2020) as a floor, not a current figure, and treat the Kalshi counterparty as UNKNOWN until measured directly from your own tape. Given that a Kalshi NG daily is a rounding error against 2.5 million NYMEX contracts, the persistence of your futures-to-Kalshi lag is itself the strongest available evidence that few automated participants are bothering to close it - which also means that edge is a function of Kalshi staying small, and will decay as institutional participation there grows (already up 800% in six months)."
 ],
 "sources": [
  "https://www.cftc.gov/dea/newcot/f_disagg.txt (CFTC weekly Disaggregated COT, futures only, report date 2026-07-28; contract code 023651 NAT GAS NYME parsed directly)",
  "https://www.cftc.gov/dea/newcot/c_disagg.txt (CFTC Disaggregated COT, futures and options combined)",
  "https://www.cftc.gov/dea/futures/deanymesf.htm (CFTC Legacy COT, NYMEX; cross-check of open interest and trader count)",
  "https://www.cftc.gov/files/dea/history/fut_disagg_txt_2010.zip (also _2015, _2020, _2025 - CFTC historical disaggregated archives used to build the 2010-2026 structural trend)",
  "https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm (CFTC COT report index and category definitions)",
  "https://www.cftc.gov/sites/default/files/idc/groups/public/@economicanalysis/documents/file/oce_automatedtrading.pdf (Haynes and Roberts, 'Automated Trading in Futures Markets', CFTC OCE - Tables 2-5, liquidity-provision speed, spread-vs-outright breakdown)",
  "https://www.cftc.gov/sites/default/files/2019-03/automatedordersreport032719.pdf (CFTC Division of Market Oversight, 'Impact of Automated Orders in Futures Markets', March 2019)",
  "https://www.cftc.gov/sites/default/files/2022-08/HFT_and_market_quality_ada.pdf (CFTC OCE, 'High-Frequency Trading and Market Quality: Evidence from Futures Markets' - Table 1 HFT market share by contract; SSRN 4069573)",
  "https://scotthirwin.com/wp-content/uploads/2022/02/Irwin_Sanders_Yan_AEPP_All.pdf (Irwin, Sanders and Yan, 'The Order Flow Cost of Index Rolling in Commodity Futures Markets')",
  "https://www.spglobal.com/spdji/en/documents/methodologies/methodology-sp-gsci.pdf (S&P GSCI methodology - business day 5-9 roll schedule)",
  "https://www.bloomberg.com/company/press/bloomberg-commodity-index-2026-target-weights-announced/ (BCOM 2026 target weights; natural gas 7.78% to 7.20%)",
  "https://onlinelibrary.wiley.com/doi/10.1002/fut.21926 (Gu, 'What drives informed trading before public releases? Evidence from natural gas inventory announcements', Journal of Futures Markets 2018)",
  "https://onlinelibrary.wiley.com/doi/10.1002/fut.20368 (Gay et al., 'Analyst forecasts and price discovery in futures markets: the case of natural gas storage', Journal of Futures Markets 2009)",
  "https://www.cmegroup.com/media-room/press-releases/2026/1/21/cme_group_sets_newrecordinnaturalgasfuturesandoptions.html (CME January 2026 natural gas records; mirrored at https://www.prnewswire.com/news-releases/cme-group-sets-new-record-in-natural-gas-futures-and-options-302667199.html)",
  "https://www.cmegroup.com/articles/2025/cme-direct-rfq-the-best-source-of-liquidity-for-energy-options-strategies.html (CME on energy options RFQ response times and screen-traded share)",
  "https://businesswire.com/news/home/20240411360080/en/ICE-Reports-Record-Open-Interest-Across-its-Global-Natural-Gas-Markets-with-Record-Trading-Activity-in-Natural-Gas-Options (ICE record gas futures and options open interest)",
  "https://www.fia.org/marketvoice/articles/us-energy-producers-reduce-hedging-capture-upside-higher-prices (FIA MarketVoice on producer hedge ratios and the shift from options to swaps)",
  "https://www.fia.org/marketvoice/articles/us-oil-and-gas-producers-shift-rainy-day-hedging-strategies-prices-rise (FIA MarketVoice on collar and three-way collar structures)",
  "https://www.fia.org/fia/articles/about-fia-principal-traders-group (FIA Principal Traders Group; membership listing)",
  "https://www.anteroresources.com/investors/press-releases/detail/259/antero-resources-announces-second-quarter-2026-financial (Antero 2026 hedge book: 61% hedged, 43% swaps at $3.91, 18% collars $3.25 x $5.66)",
  "https://www.sec.gov/Archives/edgar/data/0000033213/000003321326000043/eqt-20260630.htm (EQT 10-Q FY2026 commodity risk management)",
  "https://www.sec.gov/Archives/edgar/data/0001376227/000207187626000124/i26207_ung-424b3.htm (UNG prospectus - benchmark contract definition and the four-day 75/50/25/0 roll rule)",
  "https://www.proshares.com/our-etfs/leveraged-and-inverse/boil (and /kold - BOIL and KOLD daily-reset leveraged structure and AUM)",
  "https://www.hedgeweek.com/citadel-builds-commodities-empire-beyond-hedge-fund-roots/ (Citadel commodities scale, roughly $4bn profit driven by natural gas, Paloma acquisition)",
  "https://www.businesswire.com/news/home/20251006772807/en/Citadel-to-Acquire-Leading-German-Power-Trader-FlexPower (Citadel-FlexPower)",
  "https://www.bloomberg.com/news/features/2025-11-03/australian-bank-macquarie-loses-oil-traders-as-it-cuts-back-on-risk (Macquarie as largest commodity bank and major US gas trader; 2025 pullback)",
  "https://www.cci.com/our-business/merchant/natural-gas/ (Castleton Commodities - physical gas merchant storage and transport optionality)",
  "https://www.fortnightly.com/fortnightly/2001/10/natural-gas-hedging-primer-utilities-and-regulators (utility programmatic hedging protocols)",
  "https://surfa.memberclicks.net/assets/ARTICLESFROMCONFERENCE/Regulation_of_Utility_Hedging_Practices-Gettings_04-2017.pdf (Gettings, 'Regulation of Utility Hedging Practices')",
  "https://www.nj.gov/bpu/pdf/energy/hedgingreport.pdf (NJ BPU analysis of gas purchasing practices and hedging)",
  "https://www.alternativeswatch.com/2025/09/02/ctas-trend-following-hedge-funds-rebound-h1-rout-societe-generale-indices/ (SG CTA / SG Trend indices and the 2025 energy drag)",
  "https://www.enverus.com/blog/every-degree-moves-the-market-why-point-forecasting-beats-gfs-for-natural-gas-traders/ (GFS/ECMWF run cadence and gas-weighted degree day practice)",
  "https://www.worldclimateservice.com/2026/03/25/henry-hub-and-weather-forecasts-spot-price-relationship/ (Henry Hub and medium-range weather forecast relationship)",
  "https://www.investing.com/analysis/kalshis-40-billion-target-prices-prediction-markets-as-exchange-infrastructure-200682789 (Kalshi June 2026 volume, sports concentration, institutional growth)"
 ]
}
```

## LENS

```json
{
 "lens": "How modern systematic desks actually reason and decide - process, not marketing - benchmarked against a non-colocated human-plus-model natural gas desk running analog retrieval, an order-flow exhaustion read, and a futures-to-Kalshi lag claim.",
 "findings": [
  {
   "topic": "Natural gas is the least-automated major CME complex, and the gap is structural not incidental",
   "what_is_actually_done": "CFTC regulatory tape (1.5bn trades, 805 products, 362k accounts) shows physical commodities have the lowest automated participation of any class. Energy group: 46.9% ATS / 36.4% manual / 16.8% non-electronic. Natural Gas subgroup (40 products): 44.2% ATS / 34.6% manual / 21.2% non-electronic. Henry Hub NG specifically: only 30.7% of volume is ATS-vs-ATS, 45.8% is ATS-vs-MANUAL, 19.1% is MANUAL-vs-MANUAL. Compare British Pound (71.7% ATS-ATS, 4.1% MAN-MAN) or E-mini S&P (43.4 / 13.8). CFTC staff attribute the persistent gap to higher basis risk between futures and delivery-spec cash markets, confirmed via participant interviews.",
   "evidence": "Haynes & Roberts, 'Automated Trading in Futures Markets', CFTC Office of the Chief Economist, March 2015, Tables 2, 3, 4 (CME transaction data Nov 12 2012 - Oct 31 2014); CFTC DMO Market Intelligence Branch, 'Impact of Automated Orders in Futures Markets', March 2019 (30 contracts, Jan 2013 - Dec 2018)",
   "timescale": "structural / multi-year"
  },
  {
   "topic": "The 'automated' share massively overstates machine DECISION-making",
   "what_is_actually_done": "CME FIX Tag 1028 defines an automated order as one 'generated and/or routed without human intervention'. The CFTC is explicit that this 'is not restricted to those that are directly generated by algorithms, or those associated with HFT firms' - it includes orders 'generated manually but make use of automated spreading functionality, or even those where manual traders use the order submission management of third-party trading systems', and the 2019 report adds 'orders that are routed using functionality that manages order submission through automated means (i.e. an execution algorithm)'. So a large slice of the ~44% NG ATS figure is a human decision wearing an algorithm's coat. There is no public dataset that separates algorithmic DECISIONS from algorithmic EXECUTION of a human decision.",
   "evidence": "Haynes & Roberts 2015 (data section, FIX Tag 1028); CFTC DMO 2019, 'Automated and Manual Order Entry' section",
   "timescale": "structural"
  },
  {
   "topic": "Most Henry Hub volume is calendar spread, not outright - the flat-price tape is a minority of the market",
   "what_is_actually_done": "Breaking NG electronic volume by how orders match: spread-to-spread 55.9% (14.7 ATS-ATS + 27.9 ATS-MAN + 13.3 MAN-MAN), outright-to-spread 12.0%, outright-to-outright only 27.7%. E-mini S&P by contrast is ~93% outright-to-outright. The paper states plainly that 'spread trading is, on a relative basis, a more manual activity', that automated participation DROPS during roll periods, and that manual participation in spread trading peaks at 86% (silver). Structure, roll and curve trading is the manual/human stronghold inside an otherwise electronified market.",
   "evidence": "Haynes & Roberts 2015, Table 5 and Figure 1 discussion",
   "timescale": "structural, concentrated in roll windows"
  },
  {
   "topic": "Large MANUAL traders are a bigger share of gas than of any financial contract",
   "what_is_actually_done": "Among accounts contributing >=0.5% of a day's volume, NG splits 38.5% ATS / 17.5% MANUAL - the second-highest large-manual share of the 13 products studied (silver 25.4%, corn 20.2%), against E-mini 45.5/5.8 and Euro 64.1/3.7. By firm type (June 2016), NG had only 374 principal-trading-firm accounts versus 2,553 individual, 1,117 non-bank FCM, 396 bank/dealer and 100 asset-manager accounts. Market-wide, PTFs were 51-52% of all CME futures volume and the largest 27 firms accounted for 50% of volume - but that concentration is much weaker in gas.",
   "evidence": "Haynes & Roberts 2015 Table 6; Fett & Haynes, 'The Futures Trading Landscape', CFTC, March 2017, Table 3 and Table 4 (2010 - Q2 2016)",
   "timescale": "structural"
  },
  {
   "topic": "The NG book is slow by machine standards - there is no microsecond race to lose",
   "what_is_actually_done": "Only 3.2% (ATS) plus 1.2% (manual) of NG passive volume executes within 100ms of order entry or modification; 85% of natural gas passive orders rest longer than one second, and 26.3% of NG electronic volume rests beyond one minute. Compare ~40% executing within one second in Euro/Yen and ~20% in Treasury and S&P. In crude oil it takes more than 15 seconds for half of automated passive volume to execute, versus 4 seconds in the Euro contract.",
   "evidence": "Haynes & Roberts 2015, Table 7 and Figure 3",
   "timescale": "seconds to minutes"
  },
  {
   "topic": "Machines in gas hold risk longer than machines in financials - less pure market-making",
   "what_is_actually_done": "Non-directional (i.e. round-turned) share of large-trader volume: NG full-day 59.8% ATS vs 19.0% manual; at a 1-minute horizon NG ATS is only 28.1%, against 57.7% for E-mini S&P, 59.9% for E-mini NASDAQ and 49.1% for Euro. Automated gas participants are materially less scalp-like than automated equity-index participants. Interestingly the shortest MANUAL turnover rates in the whole study are seen in commodities.",
   "evidence": "Haynes & Roberts 2015, Table 8",
   "timescale": "intraday"
  },
  {
   "topic": "Machines synthesise stop-losses rather than resting them - so visible stop clusters are human",
   "what_is_actually_done": "'ATS orders were almost exclusively limit orders. Manual orders were stop-loss orders 4% and market orders 11% of the time.' CFTC interviews with participants found automated traders 'replicate the functionality of stop-loss and market orders by relying on their speed in reading prices and placing limit orders instead'. The regulatory consequence stated in the report is that price events cannot be explained by looking at resting stop orders, which is why CME velocity halt logic covers limit orders too.",
   "evidence": "CFTC DMO 2019, Exhibit 5 and 'Types of Orders' section",
   "timescale": "microsecond to intraday"
  },
  {
   "topic": "Automated aggression concentrates at scheduled prints and settlement, not evenly through the day",
   "what_is_actually_done": "Charting aggressive volume by 5-minute bucket, the CFTC found spikes in ATS activity in crude oil 'during the settlement windows at the end of the day and during the 10:30 AM time period when weekly crude oil inventory news is publicly disseminated... It is during these periods when the benefits of speed is often greatest.' The direct analogue for a gas desk is the 10:30 ET Thursday EIA storage print. Outside those windows, automated aggression in physical commodities is comparatively muted.",
   "evidence": "Haynes & Roberts 2015, Figure 4",
   "timescale": "microsecond to minutes, clustered at 10:30 ET and settlement"
  },
  {
   "topic": "How signals are really combined: theory-grounded features, cross-sectional RANKING, and horizon ensembles - not one clever model",
   "what_is_actually_done": "The most serious public commodity ML study we found: 41 continuous futures contracts (23 ag, 8 energy, 10 metals), Bloomberg, June 1994 - June 2024, gradient-boosted trees trained on 126 features built from nine theory-grounded families (momentum, time-series momentum, carry/basis, basis momentum, skewness, idiosyncratic vol, open interest, RSI, MA crossover) x 14 lookbacks (10-756 days), ~40m data points, expanding window, retrained annually, 20 random seeds averaged. Model outputs are used as RANKING signals, not point forecasts; long above cross-sectional median, short below. Ensembling eight horizons (5-200d): Sharpe 2.4, annual return 27%, vol 10.9%, max DD -22%, turnover 17%, net of 5bp per unit turnover. Best single model (5d) had Sharpe 3.6 but 38% daily turnover; 200d had Sharpe 1.7. The ensemble wins because the 200d model correlates only 0.41 with the 5d model while mid-horizons correlate above 0.80. Critically, classical technical indicators (RSI, moving averages) 'rank lower in importance across all horizons' against theory-grounded signals.",
   "evidence": "Tony Guida, 'Cross-Sectional Return Predictability in Commodity Futures: A Gradient Boosting Approach', Commodity Insights Digest (Bayes Business School / Premia Research), Summer 2026; full version in Guida (2025), CFA Institute Research Foundation, 'AI in Asset Management', Ch.8",
   "timescale": "multi-day to weeks"
  },
  {
   "topic": "The published capacity number - why gaps persist for smaller players",
   "what_is_actually_done": "The same author states the capacity of these strategies is 'in the low hundreds of millions of dollars, particularly given the turnover requirements for some tiny markets', and that the highest-Sharpe short-horizon models are the least scalable. Independently, the CTA industry as a whole is estimated at roughly 0.9% of daily futures volume. The economics are consistent: the best risk-adjusted systematic commodity signals do not scale, so large pools cannot fully occupy them, and the residue is available to small desks.",
   "evidence": "Guida, CID Summer 2026, Conclusion; participation-rate estimate from 'Is Trend Still Your Friend? A Microstructural Account of the Demise of Short-Term Trend-Following', arXiv:2607.01550 (2026)",
   "timescale": "multi-year"
  },
  {
   "topic": "The practitioner canon on why ML in finance fails - and it indicts walk-forward refinement specifically",
   "what_is_actually_done": "Lopez de Prado's ten pitfalls. #2 Research through backtesting: 'It typically takes about 20 such iterations to discover a (false) investment strategy subject to the standard significance level (false positive rate) of 5%' and 'feature importance is a research tool, and backtesting is not'. #8 Cross-validation leakage: serially correlated features plus overlapping labels leak information; fix is purging plus embargo. #9 Walk-forward backtesting is itself a pitfall - 'a single scenario is tested (the historical path), which can be easily overfit'; 'it is as easy to overfit a walk-forward backtest as to overfit a walk-backward backtest'; fix is combinatorial purged cross-validation generating thousands of train/test splits. #1 The Sisyphus paradigm: one quant per strategy fails; 'every successful quantitative firm I am aware of applies the meta-strategy paradigm' - an assembly line where quality is independently measured per subtask. Companion tool: the Deflated Sharpe Ratio, which corrects a reported Sharpe for the number of trials and for non-normality.",
   "evidence": "Marcos Lopez de Prado, 'The 10 Reasons Most Machine Learning Funds Fail', Journal of Portfolio Management 44(6), 2018 (GARP whitepaper full text); Bailey & Lopez de Prado, 'The Deflated Sharpe Ratio', 2014",
   "timescale": "applies to every research cycle"
  },
  {
   "topic": "The HFT insider view on ML metrics: benchmarks do not track profit, and self-deception is the main risk",
   "what_is_actually_done": "Hudson River Trading publicly states they operate in a 'low signal-to-noise domain' where 'it is easy to lie to ourselves while resolving small differences'. They do not port academic results directly ('it is rare for us to read a paper and immediately apply it to our problems'), they judge external research on 'simplicity, reproducibility, and generality', and they evaluate everything through standardised internal backtest procedures rather than accuracy-style metrics. A 0.1% accuracy improvement on an ML benchmark does not map to trading value.",
   "evidence": "Hudson River Trading, 'In Trading, Machine Learning Benchmarks Don't Track What You Care About', hudsonrivertrading.com/hrtbeat",
   "timescale": "applies to every research cycle"
  },
  {
   "topic": "Systematic vs discretionary: a tie on return, systematic wins on risk-adjusted return through breadth",
   "what_is_actually_done": "Harvey, Rattray, Sinclair and Van Hemert (1996-2014 hedge funds) find systematic and discretionary performance similar after adjusting for volatility and factor exposures, with systematic MACRO managers outperforming discretionary macro peers; more of discretionary funds' return and volatility is explained by known risk factors. AQR's own eVestment analysis (Apr 2007 - Mar 2017, 140/511 US managers etc.) finds excess returns near-tied, systematic tracking error lower (3.5% vs 4.5% US large cap), hence higher information ratio. Pairwise correlations among systematic managers averaged 0.13 versus 0.12 among discretionary - the 'all quants trade the same signals' claim is empirically false. The mechanism is Grinold's Fundamental Law: a manager holding 30 names needs a 59% per-name hit rate to match a 200-name manager running 53%, and 63% to match a 500-name manager.",
   "evidence": "Harvey, Rattray, Sinclair & Van Hemert, 'Man vs. Machine', Journal of Portfolio Management, Summer 2017; AQR Alternative Thinking 3Q17, 'Systematic versus Discretionary', Exhibits 3 and 4",
   "timescale": "multi-year"
  },
  {
   "topic": "The honest definition of 'quantamental' - and it excludes case-by-case overrides",
   "what_is_actually_done": "AQR's operative distinction is not inputs but where judgment is spent: in systematic investing 'that judgment is mainly used for designing investment strategies and risk control rules, not for second-guessing and overruling them on a case-by-case basis'. Both camps can be fundamentally oriented and use very similar inputs. What discretionary managers call a thematic approach, a systematic process calls factor-based. The genuinely hybrid pattern that survives is systematic-fundamental (fundamental inputs, rules-based combination), not rules-plus-veto.",
   "evidence": "AQR Alternative Thinking 3Q17, Introduction footnote 1, Exhibits 1-2",
   "timescale": "structural"
  },
  {
   "topic": "Short-horizon trend-following is structurally dead in small-tick books - but commodities are the documented exception",
   "what_is_actually_done": "Roughly 100 liquid futures, 1995-2025, four sectors including commodities. A structural break at 2008-09: fast EWM-5-20 Sharpe fell from 0.84 to 0.12 (~86% collapse), slow EWM-50-200 from 0.70 to 0.40. The discriminant is volatility-normalised tick size, not asset class, liquidity, or electronification date; large-tick contracts retained Sharpe 1.0-1.2. Mechanism: trend is a self-fulfilling loop where signal-driven aggressive flow creates the impact that confirms the signal; post-2008 HFT market makers withdraw depth ahead of predictable directional flow, and in sparse (small-tick) books there is no residual depth left, so the loop severs and the SIGNAL degrades, not just its harvest. Passive execution does not rescue it - passive bids get filled preferentially in adverse states, and passive trades do not generate the aggressive buyer-initiated volume the loop requires. Capacity, electronification and order-flow-interaction explanations are all rejected (CTA AUM peaked in 2022, years after the break; zero-cost execution still shows flat post-2008 returns). Notably: 'Commodities showed correlation shifts yet no PnL degradation whatsoever.'",
   "evidence": "'Is Trend Still Your Friend? A Microstructural Account of the Demise of Short-Term Trend-Following', arXiv:2607.01550v1, 2026",
   "timescale": "break dated 2008-09; horizons from 5-day to 200-day"
  },
  {
   "topic": "Order-flow imbalance alpha decays in seconds - the exhaustion read is a colocated product at its native horizon",
   "what_is_actually_done": "The published microstructure result is that order-flow imbalance has strong predictive power over roughly the next two mid-price changes and then decays to near zero for later changes; the strength is regime-dependent, with near-random behaviour in some environments. Practitioner and academic work estimates these models at one-second frequency and separately by 15-minute intraday interval because the relationship is not stationary through the session.",
   "evidence": "Survey of OFI literature incl. 'Returns and Order Flow Imbalances: Intraday Dynamics and Macroeconomic News Effects', arXiv:2508.06788; OFI prediction/decay summaries in market-microstructure literature",
   "timescale": "microsecond to seconds"
  },
  {
   "topic": "Who is actually on the other side in gas - named",
   "what_is_actually_done": "Citadel: Citadel Energy Marketing traded natural gas volumes equivalent to roughly 11% of total US natural gas consumption in 2025; bought Paloma Natural Gas in 2025 (renamed Apex Natural Gas), becoming one of the largest Haynesville operators; commodities platform staffed with 260+ investment professionals and ~100 engineers; explicitly invests in 'quantitative models, weather forecasting, satellite data and engineering resources'. Statar Capital (Ron Ozer, ex-DE Shaw fundamental gas unit, then Citadel gas, founded 2018): trades outright price, spreads and volatility, no physical and no OTC; combines fundamental AND technical models; 'rigorous drawdown analysis... integral to the construction process'; +23% through mid-December 2024 after double-digit losses, and profited from an outsize European gas options position in early 2024. Millennium's commodities branch is run by ex-Goldman Anthony Dewell. The dominant gas counterparty is a large, well-capitalised, fundamentally-driven human-plus-machine desk with physical assets - not a microsecond bot.",
   "evidence": "Hedgeweek, 'Citadel builds commodities empire beyond hedge fund roots'; The Hedge Fund Journal profile of Statar Capital; Bloomberg reporting on Statar 2024 performance and European gas options trade",
   "timescale": "multi-day to weeks"
  },
  {
   "topic": "The gas fundamental data stack is a purchasable commodity, not a moat",
   "what_is_actually_done": "Wood Mackenzie delivers pipeline nominations 'within minutes of being posted', with 25+ attributes across 25,000+ pipeline locations in the US and Canada, plus monitored power plant generation to gauge demand. NatGasHub (now under ICE) aggregates and standardises live data from 150+ interstate and intrastate pipelines. Degree-day vendors stream bias-corrected gas-weighted HDD/CDD across the nine EIA census divisions, built from GFS, ECMWF IFS, GEFS and AIFS, updated four times daily, with model blend weights set by longer-term forecast skill and recent model consistency, and delivered by API straight into quant models. Everyone with a budget has the same raw inputs. Edge therefore cannot come from possessing the data.",
   "evidence": "Wood Mackenzie natural gas real-time product pages; ICE Developer Portal / NatGasHub catalogue; World Climate Service and comparable degree-day forecast vendor methodology pages",
   "timescale": "intraday to multi-day"
  },
  {
   "topic": "Where quantitative methods historically DID and DID NOT work in energy - a 30-year practitioner record",
   "what_is_actually_done": "Financial models imported wholesale into energy failed: Black-Scholes broke because energy prices jump and mean-revert, and by 1993-94 the imported complex models collapsed, forcing bespoke development (Gibson-Schwartz stochastic convenience yield 1990; Asian, spread and swing options; the 1992-96 'heyday of innovation'). Where quant methods genuinely added value was valuing PHYSICAL optionality - gas storage, power plant flexibility, pipeline constraints, tolling agreements. The documented failure mode is complexity: 'the most complex models are not necessarily the best', producing instruments 'no-one understands' and 'no-one can calibrate'; the 1998 Midwest power spike from $25 to $7,500/MWh exposed the fragility. Post-Enron and post-2008 many firms moved back toward qualitative and fundamentals-driven measures.",
   "evidence": "Energy Risk, 'How quants shaped the modern energy markets' (interviews incl. Vincent Kaminski, Carlos Blanco, Chris Strickland, Les Clewlow, Krzysztof Wolyniec)",
   "timescale": "multi-year; storage/optionality valuation horizons of months"
  },
  {
   "topic": "The market's own structural logic in gas is calendar, storage and constraint - published by the exchange",
   "what_is_actually_done": "ICE characterises North American gas as 'one of the most volatile publicly traded commodities' with routine 4% intraday and 15% monthly moves, driven by inelastic demand against short-run fixed supply. Storage is framed as time arbitrage - 'buy today to sell a certain number of months from now'. Consistent curve patterns: April-October strip below November-March; January-February at yearly highs, April-May at yearly lows. Two physical bottlenecks generate tradeable signal: spring 'ratchets' (facilities must reach levels by March-April, excess gas dumps to spot - cash fell to $1.82/MMBtu in April 2012 before rebounding to $3.50 by November) and fall 'garage full' (injection rate restrictions force producer cash liquidation). October/November and October/January spreads widen when storage is ample and narrow when constrained. The paper offers no backtests, Sharpes or systematic signal metrics - it is structure, not alpha.",
   "evidence": "ICE white paper, 'Time Traveling the Natural Gas Market: storage dynamics and alpha generation'",
   "timescale": "weeks to months"
  },
  {
   "topic": "Risk control is enforced at the exchange as well as the firm, and it is fast and unconditional",
   "what_is_actually_done": "CME Globex Kill Switch shuts down all activity at SenderComp level in under one second, blocking order entry and cancelling working orders. Velocity Logic triggers a five-second halt when price moves exceed a parameter in a millisecond window (crude oil example: $0.50 in 1ms). Rule 575 governs disruptive practices and requires proper order processing at the entry point. Since July 2020 the Market Segment Gateway inserts a >=3 microsecond delay on partial order messages to reduce latency exploitation of split messages. On the fund side, systematic CTAs typically volatility-target the portfolio (12%, 15% and 18% annualised are common), size positions by risk rather than notional, and run automated drawdown gates - none of which requires a human vote at the moment of stress.",
   "evidence": "CME Group Rule 575 Market Regulation Advisory Notice; CME Globex Credit Controls / Kill Switch documentation; CME Globex Reference Guide (velocity logic); CFTC GMAC/FIA 'Best Practices for Exchange Volatility Control Mechanisms', Nov 2023; CTA risk-management practitioner surveys",
   "timescale": "microsecond (exchange controls) to daily (fund-level gates)"
  },
  {
   "topic": "Prediction-market venues are now institutionally market-made, which changes who you are trading against on Kalshi",
   "what_is_actually_done": "Susquehanna International Group became the first institutional market maker to commit to Kalshi, standing up a dedicated prediction-markets trading division; Jump and other principal firms are described as replicating their equities/options playbook in event contracts - capturing spread while staying directionally neutral. Kalshi runs a formal designated market maker programme with defined quoting and volume requirements, offering reduced fees and adjusted position limits in exchange. Citadel Securities' CEO participated in Kalshi's funding round; Galaxy Digital has publicly tested market-making there.",
   "evidence": "Kalshi announcements and Tarek Mansour public statements on SIG onboarding; Kalshi Help Center - Liquidity Provider Program, Market Maker requirements, Liquidity Incentive Program; trade coverage of prediction-market participants",
   "timescale": "seconds to intraday"
  }
 ],
 "where_machines_dominate": [
  "Sub-second reaction to scheduled information and settlement windows. CFTC charting shows automated aggressive share spiking precisely at the 10:30 ET inventory release and in settlement windows, and states plainly that this is where the benefit of speed is greatest. The Thursday EIA gas storage print is the same event class. Do not attempt to be first through that print.",
  "Continuous two-sided quoting and inventory-neutral market making. ATS orders are almost exclusively limit orders, and automated participants account for the overwhelming majority of non-directional turnover (NG large-trader full-day non-directional: 59.8% ATS vs 19.0% manual). Spread capture is their business model, not yours.",
  "Breadth. A systematic commodity book evaluates 41+ contracts x 126 features x 8 horizons every day. Grinold's law makes this decisive: a 30-name manager needs a 59% hit rate to match a 200-name manager running 53%, and 63% to match 500 names. A one-market, one-decision-per-day desk is at a severe breadth disadvantage by construction.",
  "Cross-venue and cross-instrument arbitrage. This is exactly the SIG/Jump playbook now running on Kalshi with designated-market-maker fee and position-limit advantages. The futures-to-Kalshi repricing lag is the single most mechanizable thing on your claimed edge list, and it is being mechanized by firms with colocation you do not have.",
  "Execution over minutes to hours. VWAP, TWAP, implementation shortfall, POV and liquidity-seeking algos are where most of the 'algorithmic' share of energy futures volume actually lives, and where vendors like Quantitative Brokers now cover NYMEX energy including options. Machines will beat you on slippage on any order large enough to matter.",
  "Unconditional risk execution. CME's kill switch cancels working orders in under a second; velocity logic halts on a $0.50 move in 1ms. Fund-level vol targeting and drawdown gates fire without hesitation, argument, or a story about why this time is different.",
  "Repeating an identical decision thousands of times without fatigue, drift, or narrative contamination.",
  "Capital-plus-physical integration. Citadel moved gas equivalent to ~11% of US consumption in 2025 with 260 investment professionals, ~100 engineers, and Haynesville production assets. On any question answerable by physical position and flow visibility, you are outgunned and should assume you are the uninformed side."
 ],
 "where_machines_are_weak": [
  "Basis and delivery-laden reasoning. The CFTC's own explanation for why physical commodities stay less automated, drawn from participant interviews, is 'the usually higher basis risk associated with delivery specifications in the cash markets'. Ratchets, injection constraints, pipeline capacity and hub-specific delivery do not reduce cleanly to a tape.",
  "Spread and roll structure. ~56% of electronic Henry Hub volume is spread-matched-to-spread and only ~28% is outright-to-outright; spread trading is explicitly the more manual activity and automated participation drops during roll windows. This is the largest structurally under-automated pocket in the contract you already trade.",
  "Slow decisions in a slow book. 85% of NG passive orders rest longer than one second and 26.3% rest beyond one minute. On a decision horizon measured in hours there is no latency race to lose - the speed disadvantage is real but irrelevant at your horizon.",
  "Novel causal stacks and regime breaks. A model trained on degree-days-to-price keeps missing days where the temperature forecast verified but the gas call failed because wind absorbed the load. The gas call is a stack (weather load minus renewables minus what coal and nuclear absorb); the machines that get this right are the ones with domain features, and the CFA/Bayes result confirms theory-grounded features beat technical indicators at every horizon.",
  "Non-varying conditions dressed as signals. A limb that never changes state carries no information regardless of how it is written. Systematic shops catch this through feature-importance analysis; the reason Lopez de Prado insists 'feature importance is a research tool, and backtesting is not' is that a backtest cannot distinguish a constant from a gate.",
  "Their own fast trend is broken. Short-horizon trend Sharpe collapsed ~86% post-2008 in small-tick books because HFT market makers withdraw depth ahead of predictable directional flow and the impact-mediated confirmation loop severs. The published exception is commodities, which showed no PnL degradation. The machines vacated a horizon in most markets and it did not close in yours.",
  "Capacity. The best-documented systematic commodity ML strategy caps out in the low hundreds of millions, and the highest-Sharpe variants are the least scalable. The CTA industry aggregate is ~0.9% of daily futures volume. Small size is a genuine structural advantage, not a consolation.",
  "Overfitting under repeated testing - which is simultaneously their weakness and your largest exposure. ~20 iterations on the same data produce a false discovery at the 5% level; walk-forward is a single historical path and is as overfittable as walk-backward. Anyone running a block-by-block refinement loop, machine or human, is in this failure mode unless trials are counted.",
  "Resting stop-loss orders. Machines do not leave them - they synthesise stops from speed and place limit orders. A resting stop in gas is one of the few visible, harvestable human artifacts left in the book."
 ],
 "implications_for_us": [
  "Demote the futures-to-Kalshi lag from an edge to a defence. Seconds-to-a-minute repricing on an institutionally market-made venue is exactly what SIG and Jump-class firms do for a living, with colocation and DMM fee/position-limit advantages you will not get. Keep measuring the lag - but use it as a negative control so you are never the stale quote, not as an alpha source. This is the axis on which we are plainly outgunned.",
  "Scope the dipole/exhaustion read down to what the literature supports. Published order-flow-imbalance evidence says predictive power spans roughly the next two mid-price changes and then decays to near zero, and is regime-dependent. Treat it as timing and regime conditioning inside a fundamentally-derived directional call, never as the call. Concretely: measure and record the horizon at which it dies, per cell, and stop claiming it at horizons where it does not.",
  "The analog library is the most defensible of the three claimed edges - and it is squarely in Lopez de Prado's crosshairs. A shape-matched retrieval refined block by block with a human in the loop IS walk-forward research through backtesting: one historical path, repeatedly tested. He is explicit that ~20 iterations manufacture a 5% false positive and that walk-forward is as overfittable as walk-backward. We are on G23. Before any further merge: (a) start a trials counter, where every proposed and every refuted play counts as a trial; (b) adopt purge-and-embargo around every scored block; (c) move toward combinatorial purged cross-validation over the block set rather than a single chronological walk; (d) deflate every reported hit rate by the trials count. This is the single highest-value process change available to us.",
  "Move the book toward spreads and structure, where automation is structurally thin. ~56% of electronic Henry Hub volume is spread-to-spread, spread trading is the manual stronghold, and automation drops during rolls. Our own worst-scored days have been seam and roll days - that is not bad luck, it is the day-class where market composition changes and our flat-price machinery is least applicable. Either build a genuine roll/seam model or stand down on those days.",
  "Copy the machines' process, not their speed. What is cheap and directly transferable: theory-grounded features over technical ones (RSI/MA ranked lowest in the one serious commodity ML study); ensembling across HORIZONS rather than committing to one; ranking rather than point-forecasting; feature-importance analysis as the research tool instead of the backtest. We already do written falsifiers and per-play scoping. The two gaps are trials accounting and horizon ensembling - the ensemble's 200d model correlated only 0.41 with the 5d model, and that decorrelation is where the risk-adjusted gain came from.",
  "Confront the breadth deficit numerically. Grinold says a 30-name manager needs 59% to match a 200-name manager at 53%. A one-market desk making one call a day needs a genuinely high per-day hit rate to be economically meaningful. Two honest responses: raise breadth inside gas (multiple expiries, spreads, vol, and Kalshi strikes as separate decisions), or accept that the product is a small number of high-conviction days and size accordingly. Continuing to score every day equally at low breadth is the worst of both.",
  "Weather is where a human-plus-model desk is genuinely competitive - but not on the forecast. Bias-corrected multi-model gas-weighted degree days from GFS/ECMWF/GEFS/AIFS are streamed by API four times a day to anyone with a budget, and Citadel funds weather forecasting, satellite data and engineers directly. The remaining edge is causal, not informational: the asymmetric slope (mild kills demand hard; heat and cold lift only sometimes) and the burn STACK (load minus wind and solar minus what coal and nuclear absorb). Build the stack as an explicit feature set. A price-trained model without it will keep making the error we already documented.",
  "Assume the counterparty in gas is a large, slow, better-informed human-plus-machine desk. ATS-vs-ATS is only 30.7% of Henry Hub volume; large MANUAL traders are 17.5%; there are only ~374 PTF accounts in NG against 2,553 individual accounts. We will rarely be picked off by pure speed. We will regularly be on the wrong side of someone reading pipeline nominations within minutes of posting, plant outages, and their own production book. Where a trade's thesis rests on flow information rather than on our analog reasoning, assume we are the uninformed side and pass.",
  "Harden two operational controls to exchange standard. First, a kill switch with the CME's property - cancels working orders and blocks entry in under a second, no human vote. Second, volatility-targeted position sizing plus a hard drawdown gate, since NG routinely moves 4% intraday and 15% monthly. Our paper ledger's four risk caps are a start; risk-scaled size and an automatic drawdown gate are the missing pieces, and they are the two things every systematic shop has that a discretionary desk usually lacks when it matters.",
  "Never rest a stop in the gas book. Machines are almost exclusively limit orders and synthesise stops from speed; the CFTC found manual orders carry stop-losses 4% of the time and market orders 11%. Our resting stop is a visible human artifact in a book where almost nothing else is.",
  "Be honest about what the analog method is competitively: a legitimate, well-known technique (retrieval-augmented forecasting and nearest-neighbour path matching are active research areas), not a unique capability. Its defensibility rests entirely on the quality and honesty of the CONDITION descriptions attached to each stored session - the thing we actually own that a vendor cannot sell. Invest there, and treat the retrieval mechanics as commodity."
 ],
 "sources": [
  "Haynes, R. & Roberts, J., 'Automated Trading in Futures Markets', CFTC Office of the Chief Economist, March 13 2015 - https://www.cftc.gov/sites/default/files/idc/groups/public/@economicanalysis/documents/file/oce_automatedtrading.pdf (CME transaction data Nov 12 2012 - Oct 31 2014; Tables 2-8, Figures 1-4)",
  "Fett, N. & Haynes, R., 'The Futures Trading Landscape', CFTC, March 10 2017 - https://www.cftc.gov/sites/default/files/idc/groups/public/@economicanalysis/documents/file/oce_futureslandscape.pdf (2010 - Q2 2016; firm-type classification, Tables 1-4)",
  "CFTC Division of Market Oversight, Market Intelligence Branch, 'Impact of Automated Orders in Futures Markets', March 2019 - https://www.cftc.gov/media/1691/Impact%20of%20Automated%20Orders%20in%20Futures%20Markets/download (30 contracts, Jan 2013 - Dec 2018)",
  "Lopez de Prado, M., 'The 10 Reasons Most Machine Learning Funds Fail', Journal of Portfolio Management 44(6), 2018 - https://www.garp.org/hubfs/Whitepapers/a1Z1W0000054x6lUAA.pdf",
  "Bailey, D. H. & Lopez de Prado, M., 'The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting and Non-Normality', 2014 - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2460551",
  "Guida, T., 'Cross-Sectional Return Predictability in Commodity Futures: A Gradient Boosting Approach', Commodity Insights Digest, Bayes Business School / Premia Research, Summer 2026 - https://www.bayes-cid.com/pdf/issues/2026-summer/publications/CID-Summer-2026-Guida.pdf (full version: CFA Institute Research Foundation, 'AI in Asset Management', Ch. 8, 2025)",
  "'Is Trend Still Your Friend? A Microstructural Account of the Demise of Short-Term Trend-Following', arXiv:2607.01550v1, 2026 - https://arxiv.org/html/2607.01550v1",
  "AQR Capital Management, 'Alternative Thinking 3Q17: Systematic versus Discretionary' - https://www.aqr.com/-/media/AQR/Documents/Insights/Alternative-Thinking/AQR-Alternative-Thinking--3Q17.pdf",
  "Harvey, C., Rattray, S., Sinclair, A. & Van Hemert, O., 'Man vs. Machine: Comparing Discretionary and Systematic Hedge Fund Performance', Journal of Portfolio Management, Summer 2017 - https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2880641",
  "Hudson River Trading, 'In Trading, Machine Learning Benchmarks Don't Track What You Care About' - https://www.hudsonrivertrading.com/hrtbeat/trading-machine-learning/",
  "Energy Risk, 'How quants shaped the modern energy markets' - https://www.energyrisk.com/risk-management/7956965/how-quants-shaped-the-modern-energy-markets",
  "ICE, 'Time Traveling the Natural Gas Market: storage dynamics and alpha generation' - https://www.ice.com/white-paper/natural-gas-market-storage-dynamics-and-alpha-generation",
  "Hedgeweek, 'Citadel builds commodities empire beyond hedge fund roots' - https://www.hedgeweek.com/citadel-builds-commodities-empire-beyond-hedge-fund-roots/",
  "The Hedge Fund Journal, Statar Capital profile - https://thehedgefundjournal.com/statar-capital/ ; Bloomberg, 'Ron Ozer's Statar Capital Rebounds With 23% Gain Through Mid-December' (Dec 16 2024) and 'Statar Profits After Doubling Bet on European Gas Options' (Feb 29 2024)",
  "CME Group Rule 575 Market Regulation Advisory Notice - https://www.cmegroup.com/rulebook/files/cme-group-Rule-575.pdf ; CME Globex Credit Controls / Kill Switch - https://www.cmegroup.com/tools-information/webhelp/globex-credit-controls/Content/Kill-Switch.html ; CFTC GMAC/FIA, 'Best Practices for Exchange Volatility Control Mechanisms', Nov 2023 - https://www.cftc.gov/media/9581/gmac_FIA110623/download",
  "Wood Mackenzie natural gas real-time / nominations product - https://www.woodmac.com/industry/commodity-trading-analytics/natural-gas-real-time/ ; ICE Developer Portal, Natural Gas Hub (NatGasHub) - https://developer.ice.com/fixed-income-data-services/catalog/natural-gas-hub ; World Climate Service US degree-day forecasts - https://www.worldclimateservice.com/us-trading-markets/",
  "Kalshi Help Center, Liquidity Provider Program / How to Become a Market Maker / Liquidity Incentive Program - https://help.kalshi.com/en/articles/15410219-liquidity-provider-program ; Kalshi announcement of Susquehanna (SIG) as first institutional market maker",
  "'Returns and Order Flow Imbalances: Intraday Dynamics and Macroeconomic News Effects', arXiv:2508.06788 (OFI decay and intraday non-stationarity)",
  "Quantitative Brokers, algorithm suite and NYMEX energy / CBOT commodity options coverage - https://www.quantitativebrokers.com/algorithms and https://www.quantitativebrokers.com/product-universe",
  "FIA - Crisil Coalition Greenwich, Derivatives Industry Survey 2025 - https://www.fia.org/sites/default/files/2025-03/FIA%20Coalition%20Greenwich%20Derivatives%20Market%20Survey_1.pdf (consulted; image-based PDF, no extractable execution-algo percentages)"
 ]
}
```

## LENS

```json
{
 "lens": "Where automated trading is structurally weak — regime change, novel events, ambiguous fundamentals, thin markets, physical/meteorological drivers, and limits to arbitrage — with the honest reverse: where a human-plus-model desk is outgunned. Focus: NYMEX Henry Hub natural gas and adjacent futures.",
 "findings": [
  {
   "topic": "Natural gas is measurably the LEAST machine-penetrated major non-agricultural futures market — and by a wide margin versus crude on the same exchange",
   "what_is_actually_done": "CFTC economists classified every account behaviourally (not by self-declaration) using regulatory trade-capture data on nine CME contracts. HFT market share of volume: Natural Gas 12.9% (2012) -> 31.7% (2020), full-sample average 24.5%. WTI crude 29.1% -> 53.9%, average 52.1%. E-mini S&P 500 average 45.0%. 10-Yr Note 43.5%. Euro FX 49.6%. Gold 42.1%. Corn 19.4%, Wheat 20.6%, Soybeans 24.8%. The four physically/weather-driven contracts (corn, wheat, natgas, soybeans) cluster at the BOTTOM; the financialised ones cluster at the top. Gas has less than HALF the HFT penetration of crude oil despite same exchange, same sector, same clearing. Separately, the paper's headline result — that higher HFT share is associated with better market quality — FAILS for natural gas: NG is named as an exception in BOTH the Amihud price-impact and the bid-ask-spread regressions (also gold marginally, and wheat in Amihud). Honest reading: machine presence in gas has not tightened the market the way it demonstrably has elsewhere.",
   "evidence": "John Coughlan and Alexei G. Orlov, 'High-Frequency Trading and Market Quality: Evidence from Account-Level Futures Data', U.S. CFTC Office of the Chief Economist, draft 7 July 2022, Table 1 and Section 4.3. Regulatory 17 CFR 16.02 trade-capture data, Jan 2012 - Aug 2021, ~21,591 contract-days. HFT classification per Brogaard et al. (2019): >0.25% of annual volume, end-of-day inventory <20% of volume, never >30% intraday.",
   "timescale": "structural / decade-scale participation share, measured daily"
  },
  {
   "topic": "Roughly two-thirds of natural gas futures volume still has a human on at least one side, and the big humans are still there at size",
   "what_is_actually_done": "CFTC analysis of CME's mandatory manual/automated tag (FIX Tag 1028). Henry Hub NG: ATS-ATS 30.7%, ATS-MAN 45.8%, MAN-MAN 19.1% of volume — so 64.9% of NG volume has a manual order on at least one side. Compare Euro FX (33.3%), Japanese Yen (28.5%), E-mini S&P (56.4%). Among LARGE volume traders (accounts >=0.5% of a day's volume), NG has 649 such accounts of which MANUAL activity is 17.5% of volume — versus 5.8% in E-mini S&P, 3.7% in Euro, 5.1% in 10-Yr. Large manual participation in gas is ~3x the S&P and ~5x Euro FX. Speed: 85% of passive executed NG orders rest in the book longer than one second, and 26.3% of NG electronic volume rests longer than one minute (E-mini S&P: 12.7%). CFTC staff, after interviewing participants, attribute lower automation in physical commodities specifically to higher BASIS RISK against the cash market and delivery-specification differences — a causal mechanism, not a coincidence.",
   "evidence": "Richard Haynes and John S. Roberts, 'Automated Trading in Futures Markets', CFTC Office of the Chief Economist, Tables 4, 6 and 7, CME transaction data 12 Nov 2012 - 31 Oct 2014. Corroborated directionally by CFTC DMO, 'Impact of Automated Orders in Futures Markets', March 2019 (30 contracts, 2013-2018): automation rose 19 percentage points on average in Energy/Metals/Grains/Oilseeds/Livestock vs 7 points in Currencies/Equities/Financials, and stayed structurally lower in physical commodities throughout.",
   "timescale": "microsecond-to-minute (resting times); structural for participation shares"
  },
  {
   "topic": "The natural gas order book you are watching is a minority of the real flow — the machines' primary game in gas is the CURVE, not the outright",
   "what_is_actually_done": "Breaking NG volume by outright (RO) vs spread (SP) legs: outright-against-outright is only 12.3% (ATS-ATS) + 12.0% (ATS-MAN) + 3.4% (MAN-MAN) = 27.7% of Henry Hub volume. Everything else involves a calendar-spread leg — roughly 72%. For the E-mini S&P the same figure is 93.2% pure outright. NG's single largest volume bucket is ATS-MAN spread-against-spread at 27.9%. Consistent with this, large automated accounts in NG are far LESS market-making-like than elsewhere: non-directional share of large-trader volume is 59.8% full-day / 28.1% at 1-minute in NG versus 86.7% / 57.7% in E-mini S&P. Implication: the automated participant in gas is more often a position-taking competitor expressing a curve view than an inventory-flat spread scalper, and a front-month outright tape read (which is what an order-flow/dipole signal consumes) is reading well under a third of the information-bearing flow.",
   "evidence": "Haynes and Roberts, CFTC OCE, Tables 5 and 8 (CME transaction data, Nov 2012 - Oct 2014). Corroborated by CME's own settlement convention: non-active NG months settle off the VWAP of accumulated calendar-spread transactions, i.e. the curve is where price discovery formally happens.",
   "timescale": "intraday to multi-day"
  },
  {
   "topic": "Short-horizon trend/momentum broke structurally around 2008-09 in small-tick markets — but COMMODITIES were spared, and the mechanism explains why",
   "what_is_actually_done": "~100 of the most liquid global futures, 1995-2025. Fast (5-day) trend Sharpe fell from 0.84 pre-2009 to 0.12 after; slow (50-day) from 0.70 to 0.40. The discriminant is NOT asset class but volatility-normalised tick size (mean of tick/daily-vol, ranked and split at the median): small-tick equal-risk portfolios went from Sharpe ~0.8 to ~0; large-tick went from ~1.4 to ~1.0-1.2 and are essentially intact. Government bonds and COMMODITIES 'show no appreciable degradation'; equity indices and currencies were gutted. Mechanism: trend profit depends on a self-fulfilling loop where signal-driven aggression has price impact that reinforces the signal. Post-2008 HFT market makers systematically withdraw depth ahead of predictable directional flow; on sparse small-tick books that withdrawal removed enough depth that trend followers retreated and the loop — and hence the SIGNAL ITSELF — died. Crucially, when the authors recomputed returns eliminating a full day of execution cost, small-tick performance stayed flat: this is signal death, not an execution-cost story. Dense large-tick books retained residual depth, so the loop survived. Book-imbalance correlation with CTA trades on large-tick contracts flipped from about -3% to +4% annualised around 2010 — liquidity rotated against trend followers but did not vanish.",
   "evidence": "Jutta G. Kurth (Institut Louis Bachelier / LadHyX Ecole polytechnique), Zoltan Eisler (Imperial College London), Adam Rej and Jean-Philippe Bouchaud (Capital Fund Management), 'Is Trend Still Your Friend? A Microstructural Account of the Demise of Short-Term Trend-Following', arXiv:2607.01550.",
   "timescale": "days-to-weeks signal horizon; the break itself is a one-time structural event dated 2008-09"
  },
  {
   "topic": "The published state of the art on daily Henry Hub returns is ~54% directional and R-squared under 0.06 — and the authors say you need real-time weather to do better",
   "what_is_actually_done": "Columbia Data Science group built a 10.5-year daily dataset (Jan 2015 - Aug 2025, 2,615 observations) of Henry Hub spot plus financial, energy and operational variables, and ran five architectures against a 30-day rolling multivariate linear regression baseline, with stratified expanding-window evaluation (160 evaluation points, retrained from scratch each time) and moving-block bootstrap. Results: rolling linear baseline achieved directional accuracy 43.30% (worse than a coin), Pearson r -0.041, R-squared -91.03. LSTM: DA 55.00%, R-squared -0.013. Best model (Hybrid CfC): DA 53.75%, R-squared 0.057, Pearson r 0.301, RMSE 7.84. Only LTC and Hybrid CfC had bootstrap confidence intervals for r and R-squared strictly above zero. The authors' own conclusion: 'even adaptive architectures cannot anticipate exogenous shocks outside the historical data distribution, suggesting that incorporating real-time external signals such as weather forecasts may be required to better capture tail-risk events.' Corroborating older econometric work on NG futures returns finds adjusted R-squared of just 0.005-0.026 for daily returns from temperature shock and inventory surprise, with a near-month temperature-shock coefficient of 0.1038 and a far-month storage-surprise coefficient of -0.0104.",
   "evidence": "Yiqian Liu, Jiayi Niu, Adam Kelleher, Subhabrata Das (Columbia University), 'Liquid Neural Network Models for Natural Gas Spot Price Time-Series Forecasting', arXiv:2604.24788v1, 24 April 2026, Table II. Plus Hu, Hu and Lin (2014), 'Effect of Temperature Shock and Inventory Surprises on Natural Gas and Heating Oil Futures Returns', 988 NG observations 2003-2006, PMC4122141.",
   "timescale": "one-day-ahead"
  },
  {
   "topic": "The single most important recent proof that the gas driver is a physical process, not a price process: a weather model revision produced the largest front-month daily loss in 30 years",
   "what_is_actually_done": "January 2026, Winter Storm Fern: Henry Hub spot hit an all-time high of $30.72/MMBtu on 23 January; 79 all-time-high average spot price records were set nationally, surpassing Winter Storm Uri's 77; the highest seven-day rolling total US gas demand on record, 165.6 Bcf/d, ran 24-30 January; freeze-offs cut production by as much as 17 Bcf/d at peak (January production averaged 104.4 Bcf/d, with a 3.3 Bcf/d average storm reduction); a record 360 Bcf net storage withdrawal for the week ending 30 January. Then on 2 February 2026 the March contract settled DOWN 25.7% at $3.237 — the largest single-day percentage loss for the front-month contract since 1995 excluding roll days — caused entirely by weather models shifting to milder, near-normal temperatures through mid-February. By 18 February the March contract settled $3.01, down 59.7% from the 28 January peak of $7.46. CFTC data for the week to 3 February showed money managers cutting long-only positions by 48,752 lots to 466,418, a 13-month low. Nothing in the price tape, order book, or historical price-path library contained that -25.7% day; the information was a numerical weather prediction update arriving on a fixed 00z/06z/12z/18z schedule. This is the clean case: a scheduled, non-price, physically-generated information event dominating everything a price-process model can see.",
   "evidence": "Bloomberg, 'US Natural Gas Plunges by Most in About 30 Years on Warm Weather', 2 Feb 2026; American Gas Association, Natural Gas Market Indicators, 5 Feb and 19 Feb 2026; Natural Gas Intelligence, 'January 2026 Arctic Blast Broke Natural Gas Price Records From Gulf Coast to Northeast' and 'Henry Hub Prices Smash All-Time Records as Winter Storm Fern, LNG Tag-Team to Tighten Balances'; Bloomberg, 'Hedge Funds Slash Bullish Natural Gas Bets to 13-Month Low', 6 Feb 2026.",
   "timescale": "intraday (the model run) to multi-day (the repricing)"
  },
  {
   "topic": "Novel, no-precedent events: the documented record shows rule-based and history-fitted strategies fail hardest exactly where the state has never occurred",
   "what_is_actually_done": "Four documented cases. (1) FREEPORT LNG, 8 June 2022: a fire removed 2.0 Bcf/d of US export capacity instantly; Henry Hub spot fell $1.27 to $8.16 the next day and to $6.54 by end-June; June LNG exports fell 1.5 Bcf/d to 10.1 Bcf/d; EIA cut its 2H22 export forecast by 1.8 Bcf/d. Initial company guidance was three weeks; the plant did not fully return until 2023 — a series of successive repricings driven by engineering and regulatory disclosures, not price action. (2) NEGATIVE WTI, 20 April 2020: May WTI settled at -$37.63 because Cushing storage was effectively full. Rule-based rollers and retail structured products were destroyed — Bank of China's 'Crude Oil Treasure' investors lost about $1.3bn, Interactive Brokers took a ~$104m loss (later fined $1.75m by the CFTC for supervision failures, including that its systems could not display or accept negative prices). Systems literally could not represent the state. Physical players with tank capacity profited. (3) LME NICKEL, 8 March 2022: price roughly quadrupled in three trading days, +250% in 24 hours; the LME cancelled eight hours of trades; LME Clear saw ~105 new account breaches out of ~430 accounts in the quarter; Elliott and Jane Street sued for up to $500m. In a physical squeeze the exchange rulebook itself becomes a risk factor no price model contains. (4) WINTER STORM URI, Feb 2021: Henry Hub spot $3.76 (10 Feb) to $23.86 (17 Feb), Texas production down ~45%, regional cash prints into four figures.",
   "evidence": "EIA, 'U.S. natural gas supply and demand balance shifts amid outage at Freeport LNG', Today in Energy #53079; CFTC Release 8432-21 (Interactive Brokers) and company statements; Office of Financial Research working paper 24-09 and Brief 25-01, 'Central Clearing and Trade Cancellation: The Case of LME Nickel Contracts on March 8, 2022'; EIA Today in Energy on Uri; Texas Comptroller Fiscal Notes, Oct 2021.",
   "timescale": "instantaneous shock, then weeks-to-months of repricing as the physical picture resolves"
  },
  {
   "topic": "Regime change in gas is not hypothetical — the shale revolution deleted the seasonal pattern a history library would have learned",
   "what_is_actually_done": "Markov regime-switching and structural-break studies of Henry Hub find that clear seasonal price fluctuations at Henry Hub DISAPPEARED after the shale gas revolution, and that the typical movement regime changed from slightly upward to sharply downward. Henry Hub also decoupled from WTI, while European NBP and Brent retained a long-run equilibrium relationship — so the gas complex became a domestic, basis-driven, physically-constrained market rather than a global macro asset. This is the mechanism behind the CFTC finding above: WTI, with continuous arbitrageable links to Brent, refined products and macro, drew HFT to 52.1%; Henry Hub, regionally isolated and delivery-constrained, sat at 24.5%. It is also a warning that spans the divide: any library of historical sessions crossing that boundary contains at least two different markets wearing the same ticker.",
   "evidence": "Regime-switching literature on the North American shale gas revolution and regional gas markets (Energy Policy, ScienceDirect S0301421516302774); structural-break analyses of shale gas production and natural gas prices (Science of the Total Environment, S0048969720300553); BBVA Research, 'U.S. natural gas prices after the shale boom', March 2018.",
   "timescale": "multi-year structural break"
  },
  {
   "topic": "Capacity and position limits keep large systematic capital structurally OUT of natural gas",
   "what_is_actually_done": "The CFTC's 2020 final position-limits rule extended federal spot-month limits to Henry Hub NG as a Referenced Contract: 2,000 contracts spot month per exchange for cash-settled Referenced Contracts, plus an additional 2,000 across economically equivalent OTC swaps, with spot-month levels generally set at 25% of estimated deliverable supply. At roughly $3.50/MMBtu and 10,000 MMBtu per contract that is about $70m of notional — a hard ceiling on how much any single book can express in the front month. Market size compounds it: Henry Hub futures hit record open interest of 1.73m contracts in Oct 2024 with ADV around 500,000 contracts, roughly $17bn/day of notional, versus E-mini S&P at ~1.5m contracts and roughly $450bn/day. Natural gas is on the order of 4% of the S&P contract's turnover. Practitioner confirmation: commodity hedge fund managers are described as at or near self-imposed capacity limits — almost all 15 managers in one commodity hedge fund index — because they protect edge rather than gather assets. The published cross-sectional evidence points the same way: surviving return predictability concentrates in high-idiosyncratic-risk, LOW-LIQUIDITY corners.",
   "evidence": "CFTC Position Limits for Derivatives final rule, 15 Oct 2020, and CFTC/FIA implementation materials; CME Group volume and open interest pages for Henry Hub Natural Gas and E-mini S&P 500; Bridge Alternatives commentary on the BACHFI commodity hedge fund index; R. David McLean and Jeffrey Pontiff, 'Does Academic Research Destroy Stock Return Predictability?', Journal of Finance 2016.",
   "timescale": "structural / persistent"
  },
  {
   "topic": "Why obvious edges persist: limits to arbitrage is a real, cited, mechanism — and published edges decay 58%",
   "what_is_actually_done": "Shleifer and Vishny (1997): textbook arbitrage assumes no capital and no risk, but real arbitrage is conducted by a small number of specialised investors using other people's money, facing margin, interim losses and liquidation risk. Performance-based capital withdraws exactly when mispricing is widest, so arbitrage becomes LEAST effective at extremes. Idiosyncratic volatility matters more than systematic to these players because they are undiversified and cannot hedge it. In commodities specifically, the hedging-pressure literature (Hirshleifer 1990 generalising Keynes and Working; Bessembinder 1992; Basu and Miffre 2013; Fan and Fernandez-Perez 2018) documents risk premia arising from hedgers' need to transfer risk in both backwardated and contangoed states, persisting because speculator capital is constrained — with documented withdrawal of arbitrage capital from commodity futures during crises. On the other side of the ledger: McLean and Pontiff studied 97 published cross-sectional predictors and found returns 26% lower out-of-sample and 58% lower post-publication, with the largest decay in predictors that had the highest in-sample returns. That is the honest tax on any edge that becomes known.",
   "evidence": "Andrei Shleifer and Robert W. Vishny, 'The Limits of Arbitrage', Journal of Finance 52(1), March 1997; Hirshleifer (1990), Bessembinder (1992), Basu and Miffre, 'Capturing the risk premium of commodity futures: the role of hedging pressure', JBF 2013; Fan and Fernandez-Perez, 'Hedging Pressure and Returns in Futures: Evidence Across Asset Classes' (2018); McLean and Pontiff, Journal of Finance 2016.",
   "timescale": "weeks-to-years; publication decay measured over multi-year post-publication windows"
  },
  {
   "topic": "The ambiguous-print problem is real and structural: the EIA storage number is a noisy observation of a latent balance that nobody sees directly",
   "what_is_actually_done": "The EIA Weekly Natural Gas Storage Report lands Thursday 10:30 ET. Analysts do NOT see the field-level data EIA sees; they model visible data — production, pipeline flows, weather — to predict the number they cannot observe, using historical correlations. So the headline surprise is a measurement error on a latent quantity, not the quantity. The reasoning that resolves it is decomposition: salt vs non-salt (salt cavities cycle fast and mean-revert; non-salt is the structural balance), regional detail, and weather normalisation — high summer injections normalised for weather signal robust supply or lagging demand and are bearish, high winter withdrawals adjusted for weather are bullish. A print can therefore be bullish on the headline and bearish on the weather-adjusted balance, or vice versa. Academic microstructure work confirms the print day is a distinct volatility regime: the storage-announcement dummy enters the variance equation for near-month NG futures at 2.1381. Machines take the headline surprise in milliseconds via machine-readable feeds; they do not resolve the decomposition. The half-life of that resolution is hours to days, which is the window a human-plus-model desk can actually operate in.",
   "evidence": "EIA Weekly Natural Gas Storage Report (ir.eia.gov/ngs); RBN Energy on predicting the EIA storage number and on weather-normalised injections/withdrawals; Hu, Hu and Lin (2014) variance-equation announcement dummy, PMC4122141; AlphaFlash and comparable machine-readable EIA/DOE energy release feeds.",
   "timescale": "milliseconds (headline) vs hours-to-days (decomposition)"
  },
  {
   "topic": "HONEST REVERSE 1 — the microsecond layer is not contestable, and the machines' data acquisition in gas fundamentals is now faster than any human process",
   "what_is_actually_done": "Latency races are frequent (about one per minute per symbol in FTSE 100 equities), extremely fast (modal race 5-10 MICROseconds), account for roughly 20% of trading volume, and are dominated by a handful of firms — the top 6 take over 80% of all race wins and losses. The estimated latency-arbitrage tax runs to roughly $5bn/year in global equities. Separately, the FUNDAMENTAL data layer in gas is itself machine-speed: Wood Mackenzie (which acquired Genscape in 2019) combines the largest North American pipeline nomination dataset with infrared surveillance of plants and terminals and satellite/terrestrial AIS vessel tracking, explicitly marketed as alerting traders to outages BEFORE interstate pipelines post drops in delivery nominations; Criterion Research and others compete on the same ground. And weather forecasting itself has been commoditised: ECMWF's AIFS went operational in 2024, GraphCast beats ECMWF HRES on 90% of 1,380 verification targets, and running these models costs a few dollars of cloud GPU per hour. Nobody has a weather-data edge any more, including us. Plainly: we cannot win the race to the print, we cannot win the race to the pipeline nomination, and we cannot win on raw forecast quality.",
   "evidence": "Matteo Aquilina, Eric Budish and Peter O'Neill, 'Quantifying the High-Frequency Trading Arms Race', Quarterly Journal of Economics 2022 (FCA message-level data); Wood Mackenzie / Genscape natural gas real-time product documentation; ECMWF AIFS operational status 2024 and DeepMind GraphCast verification results.",
   "timescale": "microseconds to minutes"
  },
  {
   "topic": "HONEST REVERSE 2 — there is no evidence that human judgement per se beats systematic, and systematic funds survive longer",
   "what_is_actually_done": "Harvey, Rattray, Sinclair and van Hemert compared discretionary and systematic hedge funds 1996-2014 and found that, after adjusting for volatility and factor exposures, systematic and discretionary manager performance is SIMILAR on appraisal ratio, in both macro and equity categories — directly contradicting the industry prior that systematic underperforms. In global macro specifically, systematic funds generated more alpha in aggregate in several analyses. On survival: systematic CTAs have higher median survival than discretionary, 12 years versus 8, with true failure rates of 7.8%/4.1% for systematic versus 10.8%/5.9% for discretionary (real failure rate 11.1% against a raw attrition rate of 17.3%). Add breadth: a systematic CTA runs 100+ markets and harvests a low information coefficient across many independent bets, while a single-complex desk must have a much higher IC per bet to reach the same information ratio. Add execution: implementation-shortfall algorithms have existed for futures since 2011 and institutional TCA against arrival price, VWAP and IS benchmarks is a mature, measured discipline. A discretionary desk that does not measure its own slippage is losing money it cannot see.",
   "evidence": "Campbell R. Harvey, Sandy Rattray, Andrew Sinclair and Otto van Hemert, 'Man vs. Machine: Comparing Discretionary and Systematic Hedge Fund Performance', Journal of Portfolio Management (SSRN 2880641); Julia Arnold and Paolo Zaffaroni, 'Survival of Commodity Trading Advisors: Systematic vs. Discretionary CTAs' (SSRN 2081903, distributed by CME Group), 1994-2009; Quantitative Brokers on the first futures implementation-shortfall algorithm (2011).",
   "timescale": "multi-year fund-level performance and survival"
  },
  {
   "topic": "HONEST REVERSE 3 — the futures-to-Kalshi lag is a decaying asset, and Kalshi is now institutionally market-made",
   "what_is_actually_done": "Susquehanna International Group onboarded as the first major institutional market maker on Kalshi, standing up a dedicated prediction-markets trading division. Kalshi runs a formal Designated Market Maker programme with rebates, tightened quoting obligations and adjusted position limits, plus a Liquidity Provider Programme with incentive-period rewards on designated series. Practitioner accounts describe cross-venue dislocations of 2-5 cents closing in under a second, and give a concrete example of a Fed-decision market moving 72c to 91c in 400 milliseconds with a bot 340ms behind already missing it — sub-10ms colocated latency being the working requirement. Kalshi's volume is heavily concentrated: sports is reported at more than 80% of total volume, which cuts both ways — the energy series are far less contested, but they are also thin, so our own size is capped there, and the resting liquidity we would trade against is a small number of quoting firms who will widen the moment they detect systematic adverse selection.",
   "evidence": "Kalshi Help Center, 'How to Become a Market Maker on Kalshi' and 'Liquidity Provider Program'; Kalshi announcement of Susquehanna International Group as first major institutional market maker; Kalshi trade-data and volume-composition reporting; practitioner prediction-market market-making and arbitrage guides (2026), treated as weak/indicative evidence only.",
   "timescale": "milliseconds to seconds (the lag itself); months-to-years for its decay"
  }
 ],
 "where_machines_dominate": [
  "Price formation at the print. Latency races resolve in 5-10 microseconds, run about once per minute per symbol, and account for ~20% of volume with the top 6 firms taking >80% of race wins. Not colocated means not competing, full stop. Do not build any strategy whose P&L depends on being first to a public number.",
  "Continuous two-sided market making and spread capture. In NG, large automated accounts still run 59.8% non-directional volume full-day; on Kalshi, SIG and the DMM programme now own that lane with rebates and tighter obligations than we can earn.",
  "Fundamental DATA acquisition. Pipeline nomination scrapes, infrared plant surveillance, AIS vessel tracking (Wood Mackenzie/Genscape, Criterion) explicitly detect outages before pipelines post nomination drops. Machine-readable EIA/DOE feeds deliver the storage headline in milliseconds. We will never see the raw fact first.",
  "Weather model access and processing. AIFS operational since 2024, GraphCast beating HRES on 90% of verification targets, a few dollars of GPU per run. The forecast input is commoditised; nobody has an edge in HAVING it.",
  "Calendar-spread and curve trading, which is roughly 72% of Henry Hub volume and where the largest automated books express their views, with CME settling non-active months off calendar-spread VWAP.",
  "Breadth. A systematic CTA runs 100+ markets and needs only a tiny information coefficient per bet; a single-complex desk needs a far higher IC to reach the same information ratio.",
  "Execution discipline and transaction-cost measurement. Implementation-shortfall futures algorithms since 2011, mature TCA against arrival/VWAP/IS benchmarks. Unmeasured discretionary slippage is a silent, persistent loss.",
  "Consistency and survival. Systematic CTAs have higher median survival (12 vs 8 years) and lower true failure rates than discretionary, and risk-adjusted performance between the two styles is statistically similar. Being human is not itself an edge.",
  "Any well-trafficked, high-attention event series (Fed, crypto, major sports) where cross-venue gaps close in under a second."
 ],
 "where_machines_are_weak": [
  "Non-price information arriving on a fixed schedule from a physical process. The 2 Feb 2026 front-month -25.7% (largest daily percentage loss since 1995 ex-roll) was produced entirely by a weather model revision. No order-book, price-path, or microstructure signal contains that information before the run posts. The 00z/06z/12z/18z cadence is knowable, exploitable structure that has nothing to do with speed.",
  "Regime change and structural breaks. Fast trend Sharpe collapsed 0.84 -> 0.12 post-2009. Henry Hub's seasonal price pattern DISAPPEARED after the shale revolution and the contract decoupled from WTI. Trend-following CTAs are in one of their deepest and longest drawdowns despite improved liquidity and reduced CTA participation. Every fitted model carries a stale prior across these boundaries.",
  "Genuinely novel states. Negative WTI (systems could not display or accept a negative price; ~$1.3bn retail losses on one structured product, ~$104m at one broker), LME nickel (+250% in 24 hours, eight hours of trades cancelled, ~105 of ~430 accounts in breach), Freeport LNG (2.0 Bcf/d gone in an afternoon, three-week guidance that became seven months). History-trained models have no basis vector for a state that has never occurred; the required reasoning is causal and physical.",
  "Ambiguous fundamental information. The EIA storage headline is a noisy observation of a latent balance nobody sees. Resolving it requires salt vs non-salt decomposition, regional detail, and weather normalisation — a bullish headline can be a bearish weather-adjusted balance. Machines take the surprise in milliseconds; the decomposition has an hours-to-days half-life and is where the real repricing happens.",
  "Natural gas specifically as a market. HFT share 24.5% average (12.9% -> 31.7%) vs WTI 52.1%, ES 45.0%, Euro FX 49.6%. 64.9% of NG volume has a manual order on at least one side. Large MANUAL traders are 17.5% of NG volume vs 5.8% in the S&P. 85% of passive NG fills rest longer than one second. And the CFTC's own headline result that HFT improves market quality FAILS for natural gas in both liquidity regressions.",
  "Capacity-constrained corners. Federal spot-month limit of 2,000 contracts per exchange (~$70m notional) on Henry Hub; NG turnover is roughly 4% of the E-mini S&P's; commodity hedge fund managers deliberately sit at self-imposed capacity limits. Large systematic capital is structurally excluded from the size we can trade at. Published cross-sectional evidence says surviving predictability concentrates in exactly these low-liquidity corners.",
  "Limits to arbitrage. Arbitrage is done by a small number of specialised, undiversified, capital-constrained players whose money withdraws precisely when dislocation is widest, and commodity hedging-pressure premia persist for that reason. Obvious does not mean arbitraged.",
  "Cross-domain reconciliation of several simultaneous physical processes. The gas call is a stack: weather-driven load, minus renewables, minus what coal and nuclear absorb, plus LNG feedgas, against storage. A correct degree-day forecast can still produce the wrong burn because wind rose. That multi-source causal reconciliation is a reasoning task, not a fitting task, and it is where fitted models systematically mis-attribute.",
  "Long-tail and low-attention venues. Kalshi's volume is >80% sports; the energy series are comparatively uncontested — but that is a two-sided fact (see implications)."
 ],
 "implications_for_us": [
  "Our analog-retrieval method IS a history-trained model and carries the same structural-break exposure as any ML system. The post-shale death of Henry Hub seasonality and the 2 Feb 2026 -25.7% day are direct threats: an analog drawn from a different regime will re-anchor confidently and be wrong on both level and slope. The live-divergence monitor is the right mitigation but it is REACTIVE. Add a REGIME GATE at retrieval time — refuse or heavily discount analogs from a different supply/LNG/seasonality regime — rather than only discarding after the slope diverges. This maps directly onto the desk's existing D23 'a condition that cannot change state carries no information' finding.",
  "Do not lead the forecast with the price path. The published ceiling on price-only daily Henry Hub prediction is roughly 54% directional and R-squared under 0.06, and the authors of that work say explicitly that real-time weather is the missing input. The edge must come from the non-price stack — weather to load, minus renewables, minus coal/nuclear absorption, plus LNG feedgas, against storage. This is precisely the S109 failure mode already recorded on the desk (gw_cdd arrived as forecast, burn fell 4.2 Bcf/d because wind rose 62%, and wind_mwh was served in every slice and read by nobody). 'Served but unread' is not a data hygiene problem, it is the whole edge being left on the table.",
  "Structure the day around the two scheduled non-price information events, not around the tape. Weather model runs (00z/06z/12z/18z, ECMWF full resolution at 00z/12z) and the EIA print (Thursday 10:30 ET). Machines take the first tick on both; the correct LEVEL takes hours. Our target should be the repricing that resolves over the following session, not the tick at the release.",
  "On the EIA print, build the decomposition, not the surprise. Salt vs non-salt, regional, and weather-normalised implied balance. The headline surprise is a measurement error on a latent quantity that even the analysts modelling it cannot observe. A play that trades the headline surprise is competing with machine-readable feeds; a play that trades the reconciliation of headline against weather-adjusted balance is not.",
  "Claimed edge (b), the order-flow dipole, is book-depth-dependent — which is good news in gas and bad news in the instrument we watch. CFM's mechanism says the trend/flow loop survives where residual depth exists, and NG qualifies (85% of passive fills rest >1s). BUT outright-against-outright is only ~27.7% of Henry Hub volume; roughly 72% involves a calendar-spread leg, and CME settles non-active months off calendar-spread VWAP. We are reading under a third of the information-bearing flow. Extending the flow read to the spread book is the single highest-value structural upgrade available to the existing signal stack.",
  "Claimed edge (a), the futures-to-Kalshi lag, is real but is a depreciating asset and should be sized accordingly. It is being competed away on any well-trafficked series; SIG and the DMM programme are now in the venue. Play it only where machines do not care, keep the live telemetry the desk already runs, and treat any month where the measured lag shortens as a signal to retire the play rather than to re-tune it. Do not build the business on it.",
  "Be maker-first, which the desk has already concluded independently (S100 feed M). The latency-race literature says the taker in a contested market is paying a structural tax to lose a race we cannot enter. This is not a preference, it is arithmetic.",
  "Our size is an ASSET here, not a limitation. The 2,000-contract federal spot-month limit (~$70m notional) and NG turnover at roughly 4% of the E-mini S&P's mean large systematic books are structurally excluded from where we can operate, and commodity funds self-cap deliberately because edge dies with size. Deliberately fish in the capacity-constrained corner. Corollary: never design a play that only pays at size we will never reach.",
  "Accept plainly that we are outgunned on speed, on fundamental data acquisition, on raw weather forecast quality, on breadth, and on execution measurement — and that there is no published evidence that discretionary judgement beats systematic on risk-adjusted returns (appraisal ratios are similar; systematic CTAs survive longer). The ONLY defensible edge is specific causal reasoning about a specific physical stack in a specific capacity-constrained market on days when a non-price information event dominates. Every hour spent anywhere else is spent losing.",
  "Two disciplines the systematic world has that we currently do not, and should steal: (i) measure our own implementation shortfall against arrival price on every fill — unmeasured slippage is a silent tax; (ii) the published post-publication decay of 58% on known predictors is the honest prior for every play merged into the brain. Plays should carry a decay expectation and a scheduled re-test, not just a falsifier.",
  "One uncomfortable consequence of the tick-size finding worth testing directly: CFM's discriminant is volatility-normalised tick size, and it is recomputed MONTHLY, not fixed. Henry Hub's $0.001 tick against a $3 price with high realised vol puts it in the large-tick, signal-survives half in calm regimes but potentially into the small-tick, signal-dead half during a Fern-type volatility explosion. That predicts our flow/dipole edge should DEGRADE exactly in the high-volatility windows we most want to trade. That is a falsifiable, measurable claim against our own tape and should be tested before the next high-vol season."
 ],
 "sources": [
  "https://www.cftc.gov/sites/default/files/2022-07/HFT_and_market_quality_07.07.2022_ada.pdf",
  "https://www.cftc.gov/sites/default/files/2019-04/ATS_White_Paper_2015_ada.pdf",
  "https://www.cftc.gov/sites/default/files/idc/groups/public/@economicanalysis/documents/file/oce_automatedtrading.pdf",
  "https://www.cftc.gov/sites/default/files/2019-03/automatedordersreport032719.pdf",
  "https://arxiv.org/html/2607.01550v1",
  "https://arxiv.org/abs/2607.01550",
  "https://arxiv.org/pdf/2604.24788",
  "https://pmc.ncbi.nlm.nih.gov/articles/PMC4122141/",
  "https://www.eia.gov/todayinenergy/detail.php?id=53079",
  "https://ir.eia.gov/ngs/ngs.html",
  "https://www.aga.org/research-policy/resource-library/natural-gas-market-indicators-february-19-2026/",
  "https://www.bloomberg.com/news/articles/2026-02-02/us-natural-gas-prices-plummet-as-forecasts-show-warmer-weather",
  "https://www.bloomberg.com/news/articles/2026-02-06/hedge-funds-slash-bullish-natural-gas-bets-to-13-month-low",
  "https://naturalgasintel.com/news/january-2026-arctic-blast-broke-natural-gas-price-records-from-gulf-coast-to-northeast/",
  "https://naturalgasintel.com/news/henry-hub-prices-smash-all-time-records-as-winter-storm-fern-lng-tag-team-to-tighten-balances/",
  "https://www.financialresearch.gov/working-papers/files/OFRwp-24-09_central-clearing-and-trade-cancellation.pdf",
  "https://www.financialresearch.gov/briefs/files/OFRBrief-25-01-lessons-from-trade-cancellation-at-the-lme-in-march-2022.pdf",
  "https://www.cftc.gov/PressRoom/PressReleases/8432-21",
  "https://web.stanford.edu/~piazzesi/Reading/ShleiferVishny1997.pdf",
  "https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365",
  "https://ericbudish.org/wp-content/uploads/2022/02/Quantifying-the-High-Frequency-Trading-Arms-Race.pdf",
  "https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2880641",
  "https://papers.ssrn.com/sol3/Delivery.cfm/SSRN_ID2411784_code1853882.pdf?abstractid=2081903",
  "https://www.cftc.gov/IndustryOversight/MarketSurveillance/SpeculativeLimits/index.htm",
  "https://www.cftc.gov/sites/default/files/idc/groups/public/@newsroom/documents/file/pl_factsheet_final.pdf",
  "https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.volume.html",
  "https://www.cmegroup.com/markets/equities/sp/e-mini-sandp500.volume.html",
  "https://rbnenergy.com/those-were-the-days-natural-gas-sell-off-triggered-by-a-storage-leak",
  "https://rbnenergy.com/under-the-weather%E2%80%93cooling-degree-days-natural-gas-storage-and-price",
  "https://www.woodmac.com/industry/commodity-trading-analytics/natural-gas-real-time/",
  "https://genscape.com/expertise/natural-gas",
  "https://www.ecmwf.int/en/forecasts/quality-our-forecasts",
  "https://journals.ametsoc.org/view/journals/atsc/76/4/jas-d-18-0269.1.xml",
  "https://www.sciencedirect.com/science/article/abs/pii/S0301421516302774",
  "https://www.sciencedirect.com/science/article/abs/pii/S0378426613001283",
  "https://help.kalshi.com/en/articles/13823819-how-to-become-a-market-maker-on-kalshi",
  "https://help.kalshi.com/en/articles/15410219-liquidity-provider-program",
  "https://news.kalshi.com/p/liquid-prediction-markets-are-finally-here",
  "https://www.bridgealternatives.com/insights/the-compelling-case-for-commodity-hedge-funds",
  "https://harbourfrontquant.substack.com/p/explaining-the-decline-of-trend-following",
  "https://www.withintelligence.com/insights/cta-hedge-fund-report/",
  "https://timera-energy.com/blog/to-what-extent-are-hedge-funds-driving-gas-prices/",
  "https://moneyweek.com/469046/the-worlds-greatest-investors-john-arnold",
  "https://en.wikipedia.org/wiki/Amaranth_Advisors"
 ]
}
```

## LENS

```json
{
 "lens": "The prediction-market and event-contract competitive field, Kalshi-centric, judged against a NYMEX natural gas desk running a shape-analog forecaster plus a claimed futures-to-Kalshi repricing lag. Headline result: the professional automated field on Kalshi is real, well-funded and growing fast, but it is concentrated in sports, crypto and short-horizon metals/oil formats. The natural gas daily ladder (KXNATGASD) is, on direct measurement, effectively uncontested - and also effectively uninvestable at size. The lag is an OPEN trade, not a crowded one, for the unflattering reason that it is too small to be worth a prop firm's attention.",
 "findings": [
  {
   "topic": "Who actually makes markets on Kalshi - named institutional participants",
   "what_is_actually_done": "Susquehanna (SIG) built the first dedicated prediction-markets desk at a quant firm in 2023 and became Kalshi's first onboarded institutional market maker (announced April 2024), taking reduced fees and higher position limits in exchange for two-sided quoting. The field has since broadened to Jump Trading (also co-developing contracts with Kalshi), Jane Street, DRW/Cumberland, Citadel Securities, Flow Traders, Wintermute, FalconX and Galaxy Digital (which launched an event-market OTC desk and printed a $10m block in June 2026). DRW advertises prediction-markets trader roles at $200k+ base. Kalshi's institutional trading volume rose ~800% in the six months to May 2026; Tradeweb took a minority stake (Feb 2026) to push Kalshi data to 3,000+ institutional clients; CryptoStruct built ultra-low-latency normalized access in July 2026.",
   "evidence": "Businesswire (Kalshi/Susquehanna MM announcement, Apr 2024); Markets Media 'Kalshi Targets Institutions'; Finance Magnates 'Wall Street Quants Move Into Prediction Markets to Hunt for Arbitrage, Not to Bet'; cryptobriefing on Jump/Kalshi contract development",
   "timescale": "multi-year build-out; quoting itself is sub-second"
  },
  {
   "topic": "Kalshi's institutional plumbing is now genuinely professional",
   "what_is_actually_done": "FIX 4.4 alongside REST/WebSocket; tiered API rate limits (Basic/Advanced/Premier) with separate read/write token buckets queryable at GET /account/limits; NFA approval as an FCM through affiliate Kinetic Markets (24 March 2026); Clear Street prime brokerage for hedge-fund clearing; the first CFTC-regulated US perpetual futures (29 May 2026); Kalshi Pro terminal live 13 July 2026. Margin/non-fully-collateralised trading is explicitly institutions-first and still needs CFTC rulebook sign-off.",
   "evidence": "Kalshi API docs and multiple developer guides; Coindesk 28 Mar 2026 on NFA licence; cryptobriefing on Kalshi Pro terminal and perpetuals; The Paypers on margin licence",
   "timescale": "microsecond-to-millisecond order handling; multi-quarter build"
  },
  {
   "topic": "Kalshi's own market-maker and liquidity subsidy programmes",
   "what_is_actually_done": "Two distinct tiers. (1) Designated Liquidity Provider status requires an executed Market Maker Agreement and is negotiated per incentivized series. (2) An open Liquidity Incentive Program (15 Sep 2025 - 1 Sep 2026, filed with CFTC 11 Feb 2026) that scores RESTING orders on a once-per-second snapshot: score = order size x distance multiplier (1.0x at best price, decayed by a Discount Factor), summed over the period, paid pro-rata from a pool of $10-$1,000 per day per market, with Target Size 100-20,000 contracts. Firms with MM Agreements, IBs, FCMs and their customers, and non-US members are all EXCLUDED from the open programme - it exists specifically to pull non-professional resting liquidity into thin books.",
   "evidence": "Kalshi Help Center 'Liquidity Incentive Program' and 'Liquidity Provider Program'; CFTC rule filing rules02112639183.pdf (11 Feb 2026)",
   "timescale": "1-second scoring snapshots; monthly (<=31 day) payout periods"
  },
  {
   "topic": "MEASURED: actual depth and spread on the natural gas daily ladder",
   "what_is_actually_done": "Direct pull of Kalshi's public API for KXNATGASD-26AUG0517 ('Natural gas price on August 05, 2026 at 5:00 PM EDT'), overnight session. 34 listed strikes at 0.5-cent gas spacing around $2.70. Whole-ladder cumulative volume ~3,600 contracts, i.e. roughly $3,600 of notional across the entire ladder. At-the-money T2.700 quoted 0.52 bid / 0.55 ask - a 3-cent spread. Top-of-book size 500 contracts on the yes bid and 299 on the offer; the next levels are 100 and 100; then a 2,250/2,268-lot block sitting 12-13 cents away that appears at IDENTICAL size on the adjacent T2.690 strike - one participant's programmatic backstop, not tradeable liquidity. Tail strikes quote 3-5 cents wide.",
   "evidence": "api.elections.kalshi.com /trade-api/v2/markets?series_ticker=KXNATGASD and /markets/{ticker}/orderbook, pulled 5 Aug 2026",
   "timescale": "live snapshot; ladder lists ~24h before settlement"
  },
  {
   "topic": "MEASURED: the NG trade tape shows no automated contest at all",
   "what_is_actually_done": "The ATM strike (T2.700) printed ELEVEN trades in ~6.5 hours of overnight session, sizes 1, 1, 2, 3, 7, 10, 10, 40, 92, 208 contracts, prices walking 0.41 -> 0.52. This is not the signature of competing latency systems; it is the signature of a handful of discretionary participants and one resting quoter. For contrast, Kalshi's crypto hourly series clear over $1bn a month.",
   "evidence": "api.elections.kalshi.com /trade-api/v2/markets/trades?ticker=KXNATGASD-26AUG0517-T2.700, pulled 5 Aug 2026; CF Benchmarks 'Kalshi Leads Surging Crypto Event Contract Market' (Mar 2026, cited in Dai/Jia/Yu)",
   "timescale": "intraday / overnight"
  },
  {
   "topic": "STRUCTURAL TELL: gas has no bot-format products",
   "what_is_actually_done": "Enumerating Kalshi's entire Commodities series list: WTI has hourly (KXWTIH) and 15-minute (KXWTI15M); gold has hourly, 15-minute and daily; silver has hourly, 15-minute, daily, weekly, monthly; platinum and palladium have hourly. Natural gas has ONLY daily (KXNATGASD), weekly (KXNATGASW) and monthly (KXNATGASMON) on Pyth, plus legacy EIA-settled range series (KXNGAS/KXNGASW/KXNGASMAX/KXNGASMIN). The short-horizon formats that latency firms feed on have deliberately not been extended to gas - the exchange has not seen the demand, and the arb crowd has not arrived.",
   "evidence": "api.elections.kalshi.com /trade-api/v2/series/?category=Commodities, pulled 5 Aug 2026",
   "timescale": "product-listing decision; persists over quarters"
  },
  {
   "topic": "Weather event contracts are an order of magnitude more liquid than gas",
   "what_is_actually_done": "KXHIGHNY (NYC daily high temperature, 5 Aug 2026) quotes ONE-CENT spreads across the ladder with per-strike volume 1,783-7,877 and open interest 1,407-6,167. That is roughly 10x the natural gas daily on activity and one third the spread. Practitioner accounts converge on the same description of the edge there: not out-forecasting NWS, but being faster than the crowd at converting an NWS/ensemble update into a probability and trading the gap - i.e. it is a data-processing and forecast-bias-tracking game, and professionals are already in it.",
   "evidence": "api.elections.kalshi.com KXHIGHNY market pull, 5 Aug 2026; Kalshi Help Center 'Weather Markets'; PillarLab AI and multiple practitioner write-ups on weather-model-vs-market edge",
   "timescale": "intraday, keyed to forecast issuance cycles"
  },
  {
   "topic": "ACADEMIC: Kalshi pricing is biased, and the bias is significant in exactly Greg's categories",
   "what_is_actually_done": "Burgi, Deng and Whelan (GWU CER WP 2026-001 / UCD WP2025_19), the first systematic study of Kalshi pricing: 46,282 contracts, 12,403 events, 313,972 Yes/No prices, 2021 to April 2025, filtered to >=$1,000 closing volume and final bid-ask <=20c. Prices are informative and sharpen into the close, but carry a clear favorite-longshot bias: contracts under 10c lose over 60% of stake; contracts above 50c earn a small statistically significant positive return; average pre-fee return on a Kalshi contract is MINUS 20%. Crucially, the by-category regressions (Table 8) reject unbiasedness with psi = 0.032*** for Financials (n=27,123), 0.031*** for Climate & Weather (n=29,924) and 0.058*** for Crypto (n=8,150) - but psi = 0.022 for Politics and 0.020 for Entertainment, NEITHER significant. The mispricing lives in the financial/commodity/weather contracts, not the headline political ones. Bias is weakening over time (2025 psi = 0.021*, marginal). Makers out-earn Takers. Kalshi began charging maker fees after April 2025.",
   "evidence": "https://www2.gwu.edu/~forcpgm/2026-001.pdf (also ucd.ie/economics WP2025_19 and karlwhelan.com/Papers/Kalshi.pdf); CEPR VoxEU column",
   "timescale": "multi-day to contract life; four-year sample"
  },
  {
   "topic": "The futures-to-event-contract lag IS being systematically arbitraged - in crypto",
   "what_is_actually_done": "Documented crypto latency arb: an 8-14 second lag between Kalshi's CF Benchmarks BRTI settlement source (a 60-second TWAP into the top of the hour) and Coinbase spot during volatile prints; cross-venue Kalshi/Polymarket windows of 2-7 seconds carrying 1.5-4.5% pre-cost spreads, detected over WebSocket in ~25ms. Open-source arb bots for the BTC 1-hour market are on GitHub. Academic measurement of pure cross-venue arb (Saguillo, Ghafouri, Kiffer, Suarez-Tangil 2025) finds risk-free returns of 2-60% per dollar on detected opportunities and ~$40m extracted from Polymarket over the measurement window. 14 of the 20 most profitable Polymarket wallets are automated; only 7-8% of wallets are consistently profitable.",
   "evidence": "PredictionMarketsPicks on BRTI settlement and hourly Bitcoin edges; CarlosIbCu/polymarket-kalshi-btc-arbitrage-bot (GitHub); 'Unravelling the Probabilistic Forest: Arbitrage in Prediction Markets' (2025); Finance Magnates 'Prediction Markets Are Turning Into a Bot Playground' (16 Mar 2026)",
   "timescale": "milliseconds to ~10 seconds"
  },
  {
   "topic": "Settlement-window manipulation is now a documented, quantified strategy",
   "what_is_actually_done": "Dai, Jia and Yu (Stanford MS&E / SMU, arXiv 2606.31675, July 2026) model and measure cash-settlement manipulation (Kumar-Seppi) inside retail prediction markets. After Polymarket launched its five-minute Bitcoin contract, Binance spot order flow in the final seconds of each cycle spiked ~50% above pre-launch levels, followed by sharp post-settlement price reversals. A small manipulator cohort netted roughly +$4m while retail was the near-exact mirror (-$3.3m), ~$3.2m transferred over two months; retail sat on the losing side of 64-66% of manipulated cycles and bore 62-74% of the loss pool; 93% of the loss landed on retail, essentially none on market makers, who quote passively and end each cycle flat. The signature vanishes at the fifteen-minute horizon - horizon length is the remedy.",
   "evidence": "https://arxiv.org/pdf/2606.31675 (Settlement Manipulation in Prediction Markets, 1 July 2026)",
   "timescale": "final seconds of a settlement window"
  },
  {
   "topic": "Kalshi natural gas settles on a Pyth composite, NOT the NYMEX print",
   "what_is_actually_done": "Since the April 2026 Commodities Hub launch, Kalshi's natural gas, Brent, gold, silver, copper, corn, soybean and wheat contracts resolve on Pyth Network feeds (Pyth NATGAS tracks 1 MMBtu of Henry Hub, aggregated from 120+ publishing institutions and market makers). Pyth Pro also supplies direct market data to Kalshi's market makers. Commodity contracts trade 24/7 including weekends when the underlying futures market is shut - Kalshi explicitly markets after-hours pricing as a feature. Legacy Kalshi NG range series still settle on EIA data; WTI daily/weekly settle on ICE. So the settlement reference differs by series and is often not the exchange print a futures desk watches.",
   "evidence": "api.elections.kalshi.com series metadata (settlement_sources), 5 Aug 2026; cryptobriefing 'Pyth expands Kalshi partnership'; Kalshi news 'Kalshi Doubles Down on Commodities' (15 Apr 2026)",
   "timescale": "continuous; settlement instant"
  },
  {
   "topic": "Fee mechanics and the true round-trip cost",
   "what_is_actually_done": "Taker fee = ceil(0.07 x P x (1-P) x 100)/100 per contract, capped at $0.035. At P=0.50 that is $0.0175 per contract per side. Maker fee is 25% of taker, ~$0.0044 at 0.50. No settlement fee either side; ACH free; 2% on debit-card deposits. Round trip at the money: TAKER ~3.5 cents on a $1 face = 3.5% of notional; MAKER ~0.88%. Combined with the measured 3-cent ATM spread on KXNATGASD, a taker round trip in gas costs roughly 6.5 cents of probability before any edge.",
   "evidence": "kalshi.com/docs/kalshi-fee-schedule.pdf (July 2026 update, 7.7.26); marketmath.io/platforms/kalshi; multiple corroborating fee guides",
   "timescale": "per trade"
  },
  {
   "topic": "Regulatory position as of mid-2026",
   "what_is_actually_done": "CFTC issued a Notice of Proposed Rulemaking on 10 June 2026 amending Rule 40.11, with a three-step test (excluded commodity? involves an enumerated activity - gaming, war, terrorism, assassination, unlawful conduct? contrary to public interest?) and a formalized self-certification review process; comments closed 27 July 2026. The proposal targets sports/gaming, and carves out contracts on interest rates, FX, securities, security indices and macroeconomic measures - commodity PRICE event contracts are not the target. The Third Circuit held 6 April 2026 (divided panel) that CFTC jurisdiction over sports event contracts is likely exclusive. Separately, on 14 July 2026 the CFTC took the unprecedented step of STAYING a Kalshi emergency rule (which would have force-liquidated Michigan users' positions) and directing Kalshi under CEA 8a(9) to honor the trades - explicitly reasoning that unwinding executed trades would shatter confidence. Protective for traders, but proof that venue and legal risk is live.",
   "evidence": "CFTC Press Release 9249-26; WilmerHale, Mayer Brown, Akin, Greenberg Traurig and Ropes & Gray client alerts (June 2026); Paul Weiss on the Third Circuit; governmentenforcementreport.com (July 2026) on the CFTC stay",
   "timescale": "multi-quarter; the stay episode resolved in 2 days"
  },
  {
   "topic": "The competitive venue map has fragmented sharply in 2026",
   "what_is_actually_done": "Q2 2026 prediction-market notional hit $113.8bn (+48.7% QoQ); June alone $50.7bn. Kalshi holds ~58.9% share (~$33bn in June) and its open interest crossed $1bn for the first time, reaching $1.16bn (+350% YTD). ROTHERA - a Robinhood/Susquehanna JV built from the January 2026 acquisition of MIAXdx (ex-LedgerX), CFTC-licensed DCM and DCO - launched June 2026, did ~$2bn in its first month (~7% share) and $3bn+ cumulative, and Robinhood is routing its own flow there, ending the Kalshi revenue share; Robinhood's prediction-market revenue ($156m in Q2) overtook crypto. ForecastEx (IBKR) runs ~$6.2m/day with macro 61% of volume and a flat $0.01/contract fee - thinner than Kalshi retail-side but deeper on macro/central-bank. Polymarket bought QCEX for $112m, holds an Amended Order of Designation (Nov 2025), applied 28 April 2026 to bring its main platform onshore, and is reported near a ~$2bn ICE investment. Nasdaq and Cboe filed in March 2026 to list binary index options. Sports is ~80% of Kalshi's fee-generating volume and 81% of Polymarket's June volume - commodities and weather are a rounding error on every venue.",
   "evidence": "thecurrencyanalytics Q2 2026 share data; DeFi Rate and cryptobriefing on Rothera; techtimes on Robinhood Q2 2026; tech-insider/marketmath on ForecastEx; PRNewswire on Polymarket/QCEX; Sportico and Pew Research on category mix",
   "timescale": "weeks to quarters"
  },
  {
   "topic": "For calibration: the underlying NYMEX gas futures market is machine-dominated",
   "what_is_actually_done": "CFTC's own Office of the Chief Economist study (Haynes and Roberts) found automated trading systems present on at least one side of 47% of metals and energy futures volume over Oct 2012 - Oct 2014, and the share has only risen. The first price reaction to the EIA storage print is algorithmic, not human. CME's gas complex set a single-day record of 2,576,346 contracts on 20 January 2026 (+15% on the 2018 record), with 811,662 Henry Hub options contracts (+28%). Any strategy whose entry depends on being early on the futures tape is competing there, not on Kalshi.",
   "evidence": "CFTC OCE 'Automated Trading in Futures Markets' (Haynes & Roberts); CME Group press release on the Jan 2026 NG record",
   "timescale": "microsecond"
  }
 ],
 "where_machines_dominate": [
  "Short-horizon asset-price event contracts - crypto hourly/15-minute, and now WTI, gold, silver, platinum and palladium hourly/15-minute on Kalshi. Documented 8-14 second settlement-source lags, 2-7 second cross-venue windows, ~25ms detection over WebSocket. Do not enter this format on any underlying.",
  "The final seconds of any settlement window on a pushable reference price. The Stanford/SMU paper quantifies it: ~$3.2m transferred in two months on Polymarket's 5-minute BTC contract, 93% of the loss on retail, market makers untouched. Kalshi NG settles on a 1-minute Pyth window at 17:00 ET - structurally the same shape, and 17:00 ET is exactly when the CME gas session goes into its daily halt, i.e. the thinnest minute of the day.",
  "Cross-venue arbitrage between Kalshi, Polymarket, Rothera and the crypto spot venues. Fourteen of the twenty most profitable Polymarket wallets are automated; ~$40m extracted historically on documented pure arb.",
  "The NYMEX gas futures tape itself. ATS on at least one side of 47%+ of energy futures volume per the CFTC's own study; the first reaction to the EIA storage print is machine. A non-colocated desk will never be early there.",
  "Two-sided quoting in the high-volume Kalshi verticals - sports (~80% of Kalshi volume), crypto, and the flagship financial series. Susquehanna, Jump, Jane Street, DRW, Citadel Securities and Flow Traders are all there with MM agreements, fee reductions and raised position limits.",
  "Any strategy whose P&L is a spread capture measured in single cents at high frequency. Kalshi's taker round trip is 3.5% of notional at the money; the firms who can live inside that are the ones quoting as makers with fee agreements you do not have."
 ],
 "where_machines_are_weak": [
  "The natural gas daily ladder is genuinely uncontested. Measured directly: 11 trades in 6.5 overnight hours on the at-the-money strike, ~$3,600 of notional across the entire 34-strike ladder, a 3-cent ATM spread, $300-500 of size at the touch, and a single participant's 2,250-lot backstop parked 12 cents away. No latency firm is fighting you for this.",
  "Kalshi has NOT listed hourly or 15-minute natural gas contracts, while it has for WTI, gold, silver, platinum and palladium. The product formats that attract latency capital have not been extended to gas. That is the clearest available evidence that the professional bots are absent from this underlying.",
  "Pricing bias is statistically significant in exactly the categories a gas desk trades and NOT in the headline political markets. Burgi/Deng/Whelan: Financials psi=0.032***, Climate & Weather psi=0.031***, both at n~28,000; Politics psi=0.022 and Entertainment psi=0.020, neither significant. The crowd has cleaned up the famous markets and left the commodity and weather ladders alone.",
  "Multi-day conditional reasoning about physical gas - the weather-to-burn-to-balance stack, storage trajectory, LNG feedgas, renewables displacement. No published prediction-market strategy family does this. The automated participants in event contracts are arbitrageurs and market makers, not fundamental forecasters; they set a fair two-sided price around a reference feed and take no view.",
  "Resting liquidity in thin ladders is actively SUBSIDISED and the professionals are excluded from the subsidy. Kalshi's Liquidity Incentive Program pays $10-$1,000/day per market pro-rata on a once-per-second score of order size x proximity to touch - and explicitly bars MM-agreement holders, IBs, FCMs and their customers.",
  "The weather ladders (1-cent spreads, 10x the gas volume, thousands of contracts of OI per strike) are contested but by a describable competitor: participants racing NWS forecast updates. That is a forecast-quality and bias-tracking game, not a latency game, and it is adjacent to work already done here."
 ],
 "implications_for_us": [
  "The futures-to-Kalshi lag is an OPEN trade, and that is not good news. It is open because KXNATGASD trades ~$3,600 of notional a day across the whole ladder with $300-500 at the touch. Even a perfect capture of every lag event cannot pay for a desk. Treat the lag as a fill-improvement technique on trades you were doing anyway, never as the strategy.",
  "Do the round-trip arithmetic before anything else. At the money the observed spread is 3 cents and the taker fee is 1.75 cents per side, so a taker round trip costs ~6.5 cents of probability. From the measured ladder the gradient is about 6.5 probability-cents per 1 cent of gas (0.81 at $2.65 falling to 0.155 at $2.75). So a taker round trip requires roughly a full 1-cent NG move that does not reverse. Maker-only cuts fees to ~0.9 cents round trip and makes the same trade viable on a 3-4 cent move - which is what the S100 feed-M 'maker-first' finding already said, now confirmed by the published fee schedule and by the academic result that Makers out-earn Takers.",
  "The comparative advantage is MAGNITUDE, not LATENCY, and the ladder is built to pay for it. Strike spacing is 0.5 cents of gas. A correct day-ahead view worth 3-4 cents of gas is worth 20-25 probability cents at the at-the-money strike - three to four times the entire taker round-trip cost. The analog-shape forecaster monetizes far better as a next-day ladder position than as a seconds-scale echo trade. Stop optimising the lag; optimise the level call.",
  "Settlement is on PYTH, not the NYMEX print. Pyth NATGAS is a 120+ publisher composite of Henry Hub, and Kalshi's gas contracts trade 24/7 including weekends when the futures are shut. The current futures-to-Kalshi model has no Pyth-vs-NYMEX basis leg. Measure that basis before sizing anything - it is an unmodelled risk that sits between the signal and the payoff, and the S99 finding that Kalshi's expiration_value is exchange-faithful was established against a different settlement source.",
  "Avoid the last minute. 17:00 ET is both the Kalshi gas settlement window and the CME gas daily halt - the thinnest minute available on a reference price. The Stanford/SMU paper shows exactly what a professional does with that combination and who funds it. Be flat or resting well away from the touch into the settlement print, and never be the marginal taker in the last 60 seconds.",
  "Enrol in the Liquidity Incentive Program and treat it as a real P&L line. It runs to 1 September 2026, pays $10-$1,000/day per market pro-rata on resting size weighted by proximity to touch, sampled every second, and excludes exactly the firms who would otherwise win it. In a book this thin the subsidy can plausibly rival the trading edge, and it rewards precisely the maker-first posture the fee schedule already forces.",
  "The weather ladders deserve a serious look as the better-liquidity sibling. KXHIGHNY quotes 1 cent wide with 10x the gas volume, the published edge description is 'be faster than the crowd at converting an NWS update into a probability', and the S109 weather rebuild (asymmetric slope, seasonal degree-day weights, the wind/renewables displacement term, the missing Ohio station) is directly transferable. It also hedges the gas view rather than duplicating it.",
  "Do not assume the political-market efficiency story applies. The published evidence is the opposite: the bias is significant in Financials and Climate & Weather and NOT significant in Politics. The categories nobody writes about are the ones still mispriced, and the bias is weakening year over year - so this window is closing, slowly. Size the programme against a 2-4 year horizon, not a permanent edge.",
  "Venue and counterparty risk is now a first-class item, not boilerplate. In July 2026 Kalshi self-certified an emergency rule to force-liquidate a class of users' positions and the CFTC had to stay it and compel honouring the trades under CEA 8a(9). Meanwhile the field is fragmenting - Rothera took ~7% share in its first month and Robinhood is pulling its own flow off Kalshi. Do not build infrastructure that assumes Kalshi is the only venue or that executed trades are inviolable.",
  "Be honest about the dipole. The exhaustion read is a genuine microstructure tool, but on Kalshi's gas ladder there is no order flow to read - eleven trades in six hours. The dipole's home is the NYMEX tape, where it informs the level call, not the Kalshi book. Do not port it to a venue with no tape and then attribute the result to it."
 ],
 "sources": [
  "https://www2.gwu.edu/~forcpgm/2026-001.pdf - Burgi, Deng & Whelan, 'Makers and Takers: The Economics of the Kalshi Prediction Market', GWU CER Working Paper 2026-001 (Feb 2026); also ucd.ie/economics/t4media/WP2025_19.pdf and karlwhelan.com/Papers/Kalshi.pdf",
  "https://arxiv.org/pdf/2606.31675 - Dai, Jia & Yu, 'Settlement Manipulation in Prediction Markets', Stanford MS&E / SMU, 1 July 2026",
  "https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXNATGASD - primary: KXNATGASD-26AUG0517 full ladder, quotes, volume and open interest, pulled 5 Aug 2026",
  "https://api.elections.kalshi.com/trade-api/v2/markets/KXNATGASD-26AUG0517-T2.700/orderbook - primary: at-the-money order book depth, pulled 5 Aug 2026",
  "https://api.elections.kalshi.com/trade-api/v2/markets/trades?ticker=KXNATGASD-26AUG0517-T2.700 - primary: trade tape, pulled 5 Aug 2026",
  "https://api.elections.kalshi.com/trade-api/v2/series/?category=Commodities - primary: full commodity series list with frequencies and settlement sources, pulled 5 Aug 2026",
  "https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXHIGHNY - primary: weather ladder comparison, pulled 5 Aug 2026",
  "https://kalshi.com/docs/kalshi-fee-schedule.pdf - Kalshi Fee Schedule, July 2026 update",
  "https://help.kalshi.com/en/articles/13823851-liquidity-incentive-program - Kalshi Liquidity Incentive Program mechanics",
  "https://www.cftc.gov/sites/default/files/filings/orgrules/26/02/rules02112639183.pdf - Kalshi Liquidity Incentive Program, CFTC rule filing, 11 Feb 2026",
  "https://kalshi.com/regulatory/liquidity-provider-program - Designated Liquidity Provider / Market Maker Agreement programme",
  "https://www.businesswire.com/news/home/20240403664852/en/Kalshi-Onboards-Its-First-Dedicated-Institutional-Market-Maker - Susquehanna as first institutional MM",
  "https://www.financemagnates.com/fintech/wall-street-quants-move-into-prediction-markets-to-hunt-for-arbitrage-not-to-bet/ - named firms, strategies, volume growth",
  "https://www.financemagnates.com/trending/prediction-markets-are-turning-into-a-bot-playground/ - bot share of profitable wallets, latency arb, 16 Mar 2026",
  "https://www.marketsmedia.com/kalshi-targets-institutions/ - institutional onboarding, Tradeweb, Galaxy, CryptoStruct, +800% institutional volume",
  "https://news.kalshi.com/p/kalshi-launches-commodities-hub-new-markets - Kalshi Commodities Hub launch, 15 Apr 2026",
  "https://cryptobriefing.com/kalshi-pyth-network-commodities/ - Pyth as settlement source for Kalshi natural gas and other commodities",
  "https://www.cftc.gov/PressRoom/PressReleases/9249-26 - CFTC NPRM on event contracts, 10 June 2026",
  "https://www.wilmerhale.com/en/insights/client-alerts/20260618-10-takeaways-from-the-cftc-event-contracts-proposed-rulemaking - analysis of the June 2026 proposed rule",
  "https://www.paulweiss.com/insights/client-memos/a-divided-third-circuit-holds-that-the-cftc-has-exclusive-jurisdiction-over-sports-related-event-contracts - Third Circuit, 6 Apr 2026",
  "https://www.governmentenforcementreport.com/2026/07/cftc-stays-kalshi-emergency-rule-directs-exchange-to-honor-trades-in-unprecedented-exercise-of-federal-authority/ - CFTC stay of Kalshi emergency rule, July 2026",
  "https://www.cftc.gov/sites/default/files/idc/groups/public/@economicanalysis/documents/file/oce_automatedtrading.pdf - Haynes & Roberts, 'Automated Trading in Futures Markets', CFTC Office of the Chief Economist",
  "https://www.prnewswire.com/news-releases/cme-group-sets-new-record-in-natural-gas-futures-and-options-302667199.html - CME natural gas volume record, 20 Jan 2026",
  "https://thecurrencyanalytics.com/stockmarket/prediction-markets-hit-113-8-billion-in-q2-as-kalshi-grabs-58-9-share-276747 - Q2 2026 venue share and open interest",
  "https://defirate.com/news/robinhood-prediction-market-revenue-surpasses-crypto-as-rothera-expansion-accelerates/ - Rothera (Robinhood/Susquehanna JV) launch and share",
  "https://www.prnewswire.com/news-releases/polymarket-acquires-cftc-licensed-exchange-and-clearinghouse-qcex-for-112-million-302509626.html - Polymarket QCEX acquisition and US regulated path",
  "https://marketmath.io/platforms/forecastex - ForecastEx (IBKR) volume, fees and category mix",
  "https://www.pewresearch.org/short-reads/2026/05/27/trading-volume-on-prediction-markets-has-soared-in-recent-months/ - Pew Research on prediction-market volume growth and category mix",
  "https://predictionmarketspicks.com/articles/how-kalshi-settles-bitcoin - BRTI 60-second settlement mechanics and the documented spot-vs-settlement lag",
  "https://github.com/CarlosIbCu/polymarket-kalshi-btc-arbitrage-bot - open-source cross-venue arb bot, evidence the crypto lag is commoditised",
  "https://www.coindesk.com/markets/2026/03/28/kalshi-secures-license-to-offer-margin-trading-to-institutional-investors - NFA/Kinetic Markets FCM approval, 24 Mar 2026",
  "https://www.businesswire.com/news/home/20260610193791/en/Pyth-Network-Launches-Proprietary-247-Index-Products-Across-Metals-Oil-and-U.S.-Equities-Partners-With-Marketvector-on-Equity-Index-Futures - Pyth 24/7 commodity index construction"
 ]
}
```
