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