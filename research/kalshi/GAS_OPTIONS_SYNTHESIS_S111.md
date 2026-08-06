# GAS OPTIONS BRIEFING - S111 (2026-08-05)

Source: five-lens research sweep (`gas-options-trader-knowledge`, run wf_56f46667-bc7),
commissioned by Greg: "do some research on options and how they are priced and traded... so you
know what we need." Six agents, 1.16M subagent tokens, 430 tool calls.

RESEARCH, NOT ADJUDICATED DOCTRINE. Nothing merged, nothing decided. Contract specs in particular
must be verified against our own instrument definitions before anything is wired - the sweep flags
its own unclosed caveats.

Lenses: contract mechanics and pricing model; the volatility surface; greeks and book management;
execution and structures; converting a path-and-dispersion forecast into an options position.

---

# GAS OPTIONS: THE DESK BRIEFING

**Synthesis of five lenses. Written for a futures trader who wants to be dangerous in Henry Hub options quickly.**

**Live anchor used throughout, verified this session (2026-08-05):** front month NGU26 (September delivery) **$3.41**, ATM implied vol **43.68%**, 21 calendar days to expiry, option expiry **08/26/26**. Where the lenses disagreed on the level ($3.00, $3.20, $4.16), they were all wrong or stale; every number below is recomputed at $3.41. The lenses' *formulas* were right.

That expiry date is itself a free confirmation of the most-contested convention in the set: Sep 1 2026 is a Tuesday, so the futures LTD is Aug 27 (3 business days prior) and the option dies Aug 26 (one business day before that). Barchart independently reports 08/26/26. The rule is confirmed; the retail pages saying "3 business days before the first of the month" are quoting the futures rule and are wrong for options.

---

## 1. THE TEN THINGS

Ordered by what it costs you not to know them.

**1. The spot-vol correlation runs the OTHER WAY, so puts do not pay on the way down.**
Equities: price down, vol up (leverage effect). Gas: the *inverse leverage effect* — vol responds more to an up shock than to an equal down shock. Trolle & Schwartz state it in payoff terms: a natural gas variance swap's return profile resembles a **call**; crude's resembles a put. Mechanism: the tail is a physical squeeze (freeze-offs, storage exhaustion, LNG feedgas outage) with no ceiling, while the downside is cushioned by coal-switching demand buying back power burn.

Consequence you trade on: a long **call** in gas has effective delta *above* its Black-76 delta on a rally, because vega pays alongside delta. A long **put** has effective delta magnitude *below* its Black delta on a selloff, because vol falls or barely rises. There is a documented practitioner case of a 20% selloff in which the puts barely moved and a long-futures-plus-puts book took the full drawdown with essentially no offset.

**This one is aimed straight at us.** Our weather model says mild kills demand: big down. If our directional edge concentrates in down days, long puts are the single worst available expression of it — we would be fighting the vol beta on exactly our best days. Down views belong in futures, or in put *spreads* (near vega-neutral), never in outright long puts.

Caveat, stated precisely: the effect is an asymmetry in *magnitude* of vol response, not a guarantee vol falls on every down day. In a glut collapse gas can sell off with vol rising. The asymmetry versus equities is reliable; the sign of dσ/dF on any given day is not.

**2. The blowup is on the calls, not the puts.**
Equity vol sellers die short puts (XIV 2018, March 2020). **Gas vol sellers die short calls.** OptionSellers.com, November 2018: naked short NG calls, gas +18% in a single session on 14 Nov, roughly $150m lost across ~290 accounts, clients lost 100% *and owed the FCM* for extended margin, and the clearer force-liquidated at the vol peak. Note that 14 Nov 2018 was simultaneously an all-time NG options volume record — the liquidity spike *was* the liquidation.

The mechanism is not "vol went up." On a gas rally, four things arrive together and in the same direction against a short-call book: gamma delta, vanna delta (vol rising raises your short-call delta), skew steepening (the wing vol rises faster than ATM, amplifying vanna), and liquidity evaporation in the futures you must buy back. During Winter Storm Fern (Jan 2026, HH $3.04 → $8.21 in one week) cash-hub volumes fell 66-85% while prices made their largest moves.

Worked vanna: a 25-delta call, 21 DTE, has vanna of roughly 0.57 delta points per vol point. Short 500 of them, vol rises 5 points, and you have 14 futures of new short delta out of nothing, before the underlying moved.

**3. Skew is call-skewed in winter and flips to put-skewed in summer.**
Winter strips (Nov-Mar, "X-H") sit in call skew essentially always. The summer injection strip (Apr-Oct, "J-V", spoken "ape-oct") routinely rotates into put skew, because in injection season the tail risk inverts to storage containment and mild-summer demand destruction. A single "skew" parameter fitted across the year is meaningless. Our own measured rr25 already shows this: positive on every winter session, about −0.015 in summer.

Jacobs & Li report a flat, roughly symmetric short-dated NG smile on a 1992-2016 average. That is not a contradiction — it is what pooling does to a quantity that changes sign seasonally. The pooled number is the artifact. Never pool skew.

**4. Every expiry references a different underlying. Deltas do not add.**
The September option is on NGU; the January option is on NGF. These are different assets with different weather exposure and no arbitrage link. A $1.00 move in the nearby produced only about **$0.57** in deferred months (2024 measurement). Aggregate delta only through a measured hedge ratio h, and gamma through h². Moontower's illustration: an M12 option's raw gamma exceeded M1's, but its *prompt-equivalent* gamma was 97% lower, so gamma neutrality needed 46x more contracts than the raw numbers implied.

Desk rule: hedge every option in its own contract month. Hedging a January option with the prompt future is a calendar spread you did not intend to put on.

**5. Options are named for the DELIVERY month and expire BEFORE the future, into physical.**
A "December" option dies in late November. It never observes most of the weather it is nominally about. Key every row of options data by **delivery month**, not expiry month, or you silently mis-join the entire dataset. The American root exercises into a physically-delivered NG future with one business day left to trade — assignment in gas is a pipeline nomination, not a share position. That is precisely why the European/financially-settled root won the volume.

**6. Samuelson and seasonality fight each other, so the term structure is not monotone.**
Vol rises steeply as a contract approaches its own expiry (Samuelson, empirically an exp(−λ(T−t)) damping on instantaneous vol). Delivery-month seasonality raises winter vol regardless of tenor. The two offset: a **deferred January can print lower implied vol than a nearer May**, because the deferred contract has low beta to today's balance. Never read the gas vol term structure as a forecast of realized vol — that is an equity habit and it will make you "discover" that the market underprices winter every single year.

**7. Two calendar seams, and you never interpolate across them.**
Oct/Nov and Mar/Apr separate injection from withdrawal season. Vol, skew and implied correlation all jump. H/J (March/April) is the widowmaker — Amaranth lost ~$6.6bn on it in 2006 at roughly 8:1 leverage. A spline or SSVI fit run naively across the calendar axis will smear March vol into April and manufacture fake calendar arbitrage at exactly the two seams where the money is made and lost. Fit *within* strip.

**8. The settle surface is a model, not a market — and it is our entire surface.**
CME staff establish the ATM vol, build the OTM skew from traded/quoted implieds, apply that skew to the futures settlement price to generate OTM settles, and derive ITM settles by **put-call parity**. For longer-dated options with no Globex data, *market participants supply bid/ask on seed strikes*. The futures settle itself is a 14:28:00-14:30:00 ET VWAP.

Therefore: our 294k settle IVs are smooth, arbitrage-clean and internally consistent **by construction**. Consistency is not evidence of correctness. ITM settles carry zero independent information. Wing and deferred settles are the exchange's interpolation. And our "Black-76 justified, on-LNE gap inside noise" result was measured on numbers produced by a Black-76-consistent fitting procedure — that is circular until re-tested on traded prices.

**9. Vol levels are 2-4x equity, and 40 is quiet.**
EIA measures HH front-month realized vol at 81% in Q4 2024 falling to 69% by mid-2025 — described as vol *falling*. 30-day realized hit 102% on 3 Feb 2025. Winter realized averages low-50s but is strongly right-skewed, so the median winter is calmer than the mean and short vol prints for several seasons before returning everything in one week. Working bands: shoulder/summer front 35-50, winter front 50-70, event spikes 90-100+. The current 43.68 is a quiet market.

**10. Liquidity is bimodal, the weeklies barely exist, and the root plumbing has already bitten us.**
2025 Henry Hub ADV: futures 708,000, **options 326,000**, combined 904,000 (record). Single-day options records 561,379 (21 Nov 2024) and 811,662 (20 Jan 2026). That is a genuinely deep market — but the depth is in the front one-to-three monthly expiries, on the $0.25/$0.50 handles, within ~25 delta. **Weekly options ran ADV of "nearly 4K contracts" in January 2026** — about 1% of the complex, spread across five expiry days and dozens of strikes.

Execution is a two-tier market. CME's own figure: 1,000 call spreads crossed as a single RFQ instrument costs **under 1 tick**; the same spread legged across the outrights costs **2.5-5 ticks**. Block minimums are small (10 contracts on HH weeklies). In the closest measured analogue (WTI options), blocks are >30% of volume and multi-leg strategies ~40%.

The plumbing corollary, and this one is now **resolved**: our x10 LNE strike trap is a known, vendor-confirmed Databento bug reported 12 June 2024, affecting CME roots including LNE and LN1-LN5. Root cause, verbatim: *"The option's display_factor is being used to decode the strike price, and not the future's display_factor."* Fix: decode the strike with the **underlying future's** display factor. The 0.1 multiplier circulating as a workaround is our x10.

---

## 2. THE MENTAL ARITHMETIC

All at **F = $3.41, σ = 43.68%, 10,000 MMBtu**. Fσ = 1.490 — that product is the base of everything.

**Money units.** Tick $0.001 = $10. 1 cent = $100. 10 cents = $1,000. $1.00 = $10,000. Our forecast errors are already in these units: "sum|err| 720" over ten days is $72/day is 0.72 cents/day.

**Divide the vol by 16.** 1-sigma day = F·σ/√252 = 1.490/15.87 = **9.4 cents = $939**. On a calendar-day basis (365) it is 7.8 cents = $780. Both are correct and they mean different things — see the day-count note below.

**The straddle is 0.8·F·σ·√T.** (The constant is 2/√(2π) = 0.7979.) With T in calendar years:

| T | √T | ATM straddle | vega/vol pt | 1 tick in vol pts | theta/day | gamma (Δ per $1, straddle) |
|---|---|---|---|---|---|---|
| 1 day | 0.0523 | **$622** | $7.1 | 1.40 | $311 | 10.2 |
| 3 days | 0.0907 | **$1,078** | $12.3 | 0.81 | $180 | 5.91 |
| 1 week | 0.1385 | $1,646 | $18.8 | 0.53 | $118 | 3.87 |
| 21 days | 0.2399 | **$2,852** | $32.6 | 0.31 | $68 | 2.23 |
| 90 days | 0.4966 | $5,904 | $67.5 | 0.148 | $33 | 1.08 |

Cross-checks that make the table self-verifying: straddle price ÷ vol in points = straddle vega ($2,852/43.68 = $65.3 = 2 × $32.6). Straddle theta = straddle price ÷ (2 × days). Gamma × ½ × F² × σ²/365 × 10,000 = theta exactly ($67.9 at 21 days, both ways).

**The single most useful identity on this page:** for T = 1 day, the ATM straddle price *is* the market's expected absolute one-day move. 0.798·F·σ·√(1/365) = E|ΔF| under a normal. **$622 at today's numbers.** Hold that against our blind mean absolute error and the whole options question answers itself. (Section 3.)

**Vega scales as √T; theta scales as 1/√T.** 90-day vega is 2.07x 21-day vega. Theta doubles when time quarters: the 21-day straddle bleeds $68/day at inception and $170/day with 5 days left.

**Converting a quoted spread into vol.** vol points = ticks × $10 / vega-per-point. Three ticks on a 21-day ATM is 0.9 vol and 1.1% of premium — fine. Three ticks on a **3-day** ATM is 2.4 vol; a two-cent-wide market (20 ticks) on that same option is **16 vol points**, and buying then selling the straddle at that width costs $400 round trip on $1,078 of premium — **37%**. Same product, same tick, order-of-magnitude different execution cost. *Never quote a spread in ticks or in percent of premium. Quote it in vol points and in percent of the structure's vega.*

**The futures leg is nearly free and that is the comparison that matters.** NG prompt is one tick wide; round trip = $10 of spread plus ~$3.20 of exchange/clearing fees = **~$13 all-in**, or 3.4 basis points. Against a weekly option's $60-$400 round trip. A directional view costs 5x to 30x more in an option than in the future.

**Hedge frequency, solved rather than hand-waved.** Discrete-hedging error: std of terminal P&L ≈ 0.886 × ATM premium / √n. Transaction cost (Leland): σ̂² = σ²[1 + √(2/π)·k/(σ√dt)], k = 3.4 bps round trip. Daily hedging costs 0.21 vol but leaves 19.3% of premium in hedging noise; every ~90 minutes costs 0.84 vol with 4.8% error; the crossover sits near **every 35 minutes** at ~3% each. That is far more frequent than equity-derived advice, *because the gas tick is tiny relative to gas vol*. Do not hedge on a clock through 10:30 ET Thursday or through the 14:28-14:30 settle window.

**Sizing arithmetic.** Breakeven win rate = 1/(1+R). At 1:1 you need 50%; at 2.5:1, 29%. Standard error of a sample standard deviation ≈ σ/√(2(N−1)): at **N = 20 that is 16.2%, or ±7 vol points on a 44 vol.** Reaching ±1 vol point needs ~950 analogues. Kelly is undefined for an unbounded short-option payoff — size shorts off a 15-20% up-gap stress (NG did +18% on 14 Nov 2018) and take the smaller of that and Kelly.

**The day-count, resolved.** The market prices T in calendar days / 365. That is internally consistent with your calendar-basis breakeven of 7.8 cents *per calendar day including weekends*. But you only get moves on trading days, so over a week you must deliver 7 × $68 = $475 of gamma P&L across 5 sessions, which requires **9.2 cents per trading day** — the 252-basis number. Both are right; they are different denominators, and they reconcile. On a monthly option the discrepancy is ~2% and irrelevant. **On a 3-day weekly spanning a weekend it is decisive:** calendar time says √(3/365) = 0.0907, a trading-day count says √(1/252) = 0.063, a 44% gap in vol-time. Professionals split the difference with day-weighting (business day 1.0, weekend day 0.5, overnight 0.25 → a 308-day year), which puts Friday-to-Monday at 0.0806. Pick one, write it into the SOP, use it in the vol conversion, the theta engine, the breakeven and the dispersion annualization identically.

---

## 3. WHAT OUR FORECAST ACTUALLY BUYS US

### The blunt answer: not enough to trade options today.

Here is the calculation that decides it, and we can run it this week on data we already hold.

For each walked day, the market's implied expected absolute move is **0.798 × F × σ_imp × √(1/365)** — literally the price of a one-day ATM straddle. Our blind |error| on that day is our own expected absolute miss. Define

> **skill ratio = blind |error| ÷ 0.798 · F · σ_imp · √(1/365)**

Below 1.0, we know something the market does not. At or above 1.0, we do not. Compute it **per day, never pooled** — that is our own doctrine and it is also the only honest form.

Rough numbers, from our own record and today's market: our blind mean absolute error is **$596 (G22) and $592 (G23)**, having improved from $939 (G19) → $788 (G20) → $632 (G21). A one-day ATM straddle at $3.41 and 43.68 vol costs **$622**. We are at roughly 0.95. On ten days that is inside noise. And against realized — the mean absolute day move over the G22/G23 windows looks to be in the $500-700 range from the individual days in our own records — we are at or barely better than **forecasting zero**.

Three further facts that make this worse, not better:

**Blind direction is 4-6/10 across five blocks.** A coin flip. Breakeven on a 1:1 vertical is 50% before costs. A directional options book has no path to breakeven at any reward:risk we can realistically execute.

**The MAE improvement may be shrinkage, not skill.** A forecaster that shrinks its magnitude toward zero improves MAE monotonically while adding no information. Blind MAE fell 939 → 592 while direction stayed flat at the coin flip. **Check whether the mean |blind forecast| has been falling block over block.** If it has, the improvement is compression and there is no magnitude edge at all. This is a one-line query and it should be run before anything else in this briefing.

**The refine's 10/10 and $40-80 day errors are hindsight and cannot be traded.** Any Kelly fraction, expected value or position size computed from refine statistics is computed from a number that will not exist at decision time. This must be a stated rule.

### Where the method *is* genuinely differentiated

Two things, and they are real.

**(a) We produce a DENSITY, not a moment.** The cohort is an empirical distribution. The options market prices a risk-neutral density that we can extract from the LNE ladder by Breeden-Litzenberger (q(K) = ∂²C/∂K²). That is a density-to-density comparison, which is exactly what our method outputs and exactly what options price. Crucially, *shape* disagreements (skew, kurtosis) are more robust than *level* disagreements, because the level absorbs the variance risk premium and the shape does not, to first order. Most vol desks compare a number to a number. We can compare a distribution to a distribution.

**(b) We produce PATHS at daily resolution, which separates two things options price separately.** *Terminal dispersion* (the cohort's spread at the horizon) prices strike structure — verticals, digitals, risk reversals. *Path roughness* (the sum of squared daily moves along each analog path) prices gamma and vega. A cohort with wide terminal spread but smooth paths says buy the vertical and sell gamma; tight terminal spread with violent paths says the reverse. **No listed instrument gives you that read and almost nobody has it.** It is the genuinely unusual asset in our machinery.

Neither of these is currently wired, and neither is worth anything until the skill ratio clears 1.0.

### Where it is just an expensive way to be directional

**A one-session view in a 21-day option.** Our view covers 1/21 of the option's calendar variance — about 4.8%. We pay for the other 95%. The 21-day straddle costs $2,852; one day's expected move is $622. We are paying 4.6x our view's horizon.

**Verticals off a directional call — which is what the 51-event replay did.** Three problems, all of which the replay did not measure. Skew moves against the short leg as the underlying rallies (documented case: a call spread expected to make 40 cents made 20, because call skew ripped higher with the future). It is two legs, so legging costs 2.5-5 ticks against under 1 tick as an RFQ package. And it was marked at settle, which is the price nobody trades on. **That replay's P&L is an upper bound with unknown and probably large slack, and the slack is widest exactly where the structure looks most attractive.**

### The horizon problem, stated hard

Our forecast horizon is one session. There is no liquid one-session gas option. The listed weekly chain now has Monday-through-Friday expiries — horizon-matched — and does **~4,000 contracts a day across five expiries and dozens of strikes**, i.e. tens of lots per strike. Our exit would be our own bid.

**The horizon-native instrument we already own is Kalshi KXNATGASD.** Matched clock, no vega, no theta convention, no delivery, no root plumbing, and we already have the dock, the signed auth, the paper ledger and the risk caps. For a one-day directional or distributional view, Kalshi is strictly better than any gas option. One correction to make there: a daily binary is a digital, and digital = N(d2) − Vega·(∂σ/∂K). With positive gas strike skew an upside digital is worth **less** than the naive flat-vol N(d2), by an amount we can compute from our own rr25 and fly25 features. Digital vega also *changes sign* across the strike — an OTM digital call is long vega, an ITM one is short — so a binary is only a vol bet in one direction relative to the forward.

### What would have to be added before options beat the future or Kalshi

1. **A blind skill ratio below 1.0**, measured per day, with the shrinkage check passed. Nothing else matters until this.
2. **A horizon extension to 5+ sessions**, or a re-framing that aggregates daily paths into a weekly terminal density. The front monthly is where liquidity is; our clock has to reach it.
3. **A measured k = RV/IV at our own tenor**, per season and day-class (Section 4).
4. **A quote-based surface** with bid/ask/size, not settle marks.
5. **A cohort large enough to resolve the edge.** At N = 20 we cannot distinguish 44 from 51. We need N in the hundreds, or we need to publish the standard error and refuse to trade inside it.
6. **A selection-bias correction** on the cohort dispersion.
7. **An execution model in vega units**, with an RFQ package assumption, not legged mids.

---

## 4. THE MEASUREMENT PROBLEM

### The measure error, concretely

Our cohort is a **physical (P) measure** sample. Implied vol is a **risk-neutral (Q) measure** quantity. The wedge between them is the pricing kernel, and the wedge *is* the risk premium. Risk-neutral densities are systematically fatter-tailed and more skewed than physical ones, because they embed crash-risk premia and insurance demand. Setting σ_emp against σ_imp and calling the difference "edge" is a measure error, not a signal — you have measured the variance risk premium and mislabelled it as forecast skill.

### What the gas VRP actually is

Model-free variance swap replication, NG Oct 1992 - Sep 2011, n = 4,394 (Prokopczuk, Symeonidis & Simen):

- 60-day VRP: mean **−10.2 variance points**, t = −9.24, median −7.3. Crude −3.4, heating oil −3.0. **Gas carries roughly 3x the premium of crude.**
- 60-day **log** VRP: **−43.0%**, t = −12.71, annualized Sharpe of shorting **47.0%**.
- Independently (Trolle & Schwartz): short-variance Sharpe gas **0.35**, crude 0.59, cold season 0.38 vs warm 0.35 (difference not significant).
- Gas VRP *volatility* is **15%** against a cross-commodity norm below 7%.

**The translation to carry in your head:** exp(−0.43) = 0.65 in variance, √0.65 = **0.81**. Realized vol in gas averages ~80% of implied. **IV/RV ≈ 1.24.** Mean equals median, so this is not outlier-driven.

Read that carefully: a naive σ_emp-vs-σ_imp comparison will fire "sell vol" on **nearly every single day**, because implied runs 24% above realized on average. That is not our signal. That is us rediscovering a 30-year-old published fact and mistaking it for alpha.

**Big premium, poor Sharpe.** 0.35-0.47 on a fat-tailed, seasonal, event-driven series is not a business you can lever. The premium is compensation for a genuinely one-sided tail, and it arrives on the call side.

### The maturity structure, and a conflict resolved

Jacobs & Li estimate the **one-month** NG VRP as *positive and significant*, while simultaneously finding that delta-hedged gains and ATM straddle returns at one month are *negative*. They concede the two are "difficult to reconcile."

**Resolve in favour of the direct measurement.** The delta-hedged gain is what you would actually have earned; the positive 1M VRP runs realized variance through a forecasting regression to build an ex-ante physical variance, and that estimation step is most fragile at the shortest horizon. Prokopczuk's model-free 60-day number is decisively negative. **Verdict: front-month gas vol is mildly rich; the reliable premium lives at 3-6 months** (NG 6-month VRP = −31.66% of risk-neutral variance).

**And nobody has measured 1-5 days.** All published gas VRP work is 30/60/90/180-day. Our horizon is 1/60th of the shortest measured tenor. We must generate this number ourselves.

### The comparison, done correctly

1. Compute cohort terminal log returns r_i = ln(S_T,i / S_0).
2. σ_emp = std(r_i) annualized on the **same day-count basis** as the surface. Also keep the full quantile set — the std throws away most of what the cohort knows.
3. **Do not compare σ_emp to σ_imp.** Compare σ_emp to **k · σ_imp**, where k is *our own* measured RV/IV ratio at that tenor, that season, that day-class. The literature's 0.81 is a 60-day number from a sample ending 2011; it predates Uri, Freeport, the LNG-export regime and Fern.
4. The signal is only the residual **(σ_emp − k·σ_imp)**, and only if it exceeds the estimator's standard error.
5. Better: do it density-to-density. Breeden-Litzenberger the LNE $0.25/$0.50 handles for q(S_T), k-adjust, and compare shape against the cohort's p(S_T).

### THE THREE-BIAS STACK — the thing that will actually get us

Three separate errors, all pointing the same way:

**Bias 1 — selection compresses the cohort.** We select analogs on shape match, then measure how much the selected days differ. Selection on similarity mechanically shrinks the dispersion of the selected set below the true conditional dispersion, and the shrinkage grows as the match test tightens. **σ_emp is biased low.**

**Bias 2 — the measure error inflates σ_imp.** The VRP makes implied look rich by ~24% on average, before any skill.

**Bias 3 — the settle surface is smooth by construction.** Exchange-fitted OTM skews, parity-derived ITM, participant-seeded long end. The wings we would sell are the wings the exchange interpolated.

All three say *implied is rich, sell vol*. Two independent biases stacking in one direction, plus a contaminated mark, is how a book ends up structurally short gamma without anyone deciding to be. **In gas, short gamma dies on the upside.**

And our weather model — mild kills demand, big down; heat/cold up but only some — will independently push us toward believing the upside is overpriced. That is a fourth arrow into the same trap.

### Three more measurement items that are ours alone to fix

**Estimator precision.** SE(σ̂) = σ/√(2(N−1)). At N = 20 that is ±7 vol points on a 44 vol. Publish the SE with every dispersion output and **refuse any trade whose claimed edge is smaller than one standard error.** This kills most trades. That is the point.

**The re-anchoring convention.** Gas vol is level-dependent. Our error metric is in dollars, which implies we transfer shape in absolute cents. A $9-era day carrying 40 cents of range is a 4.4% day there and a 12.5% day on $3.20 gas. Test cents versus log returns; they will disagree most on the extreme analogs that set our tails.

**The seasonal-boundary artifact.** Comparing forward-looking IV to trailing realized across a seasonal transition produces a spurious signal every spring and every autumn. Worked case: 28 January, IV 49%, RV 86% — that looks like a 37-point buy signal and is correct pricing of a seasonal roll-off the trailing window cannot see. Our architecture is set up to make exactly this error.

---

## 5. WHAT WOULD KILL US

Ranked by probability × severity **for this desk, with this method**.

**1. The three-bias stack drives us short vol, then gas squeezes.** Highest probability by a wide margin, and it is the one that ends the desk rather than costing a bad month. Selection-compressed cohort + VRP-inflated implied + smooth settle marks + a weather model that says the downside is where the moves are, all converging on "sell the upside wing." Then Fern, or 14 Nov 2018, or Uri. OptionSellers' clients did not lose 100%; they lost more than 100% and owed the clearer.

**2. Sizing off refine statistics.** The refine is 10/10 with $40-80 day errors. That number is hindsight-conditioned and will not exist when the order is entered. Any expected value, Kelly fraction or limit computed from it is fiction with a decimal point on it.

**3. Execution death in weeklies.** The horizon-matched instrument does ~4,000 lots/day across five expiries. A two-cent-wide market on a 3-day straddle is 16 vol points and 37% of premium round trip. Legging a two-leg structure costs 2.5-5 ticks versus under 1 tick as an RFQ package. And liquidity migrates off transparent venues during extreme weather — the exact days our forecast is most valuable (FERC/Rice: "information became scarce when it was most needed").

**4. Root, ladder and display-factor plumbing.** We have hit this class three times already (holes #7 encoding, #8 off-instrument after a roll, #9 wrong encoding). An options surface is the richest possible substrate for it: three or more monthly roots on the same underlying with different exercise styles and different display factors, weeklies that on a shared expiry day exercise into the **second** nearby, and contract sizes of 10,000 / 2,500 / 1,000 MMBtu across the complex. Every one of these produces values that are present, numeric, in range and self-consistent. Only reconciliation against an independent quantity catches them.

**5. Long puts on our down views.** Section 1, item 1. This is where our specific weather thesis meets the specific gas vol beta, and it is a systematic, repeatable loss.

**6. Buying the cheap upside call spread.** A cheap gas call spread is cheap because the surface assigns low probability there, and as the future rallies call skew richens against the short leg. Buying the wing is buying the market's stated improbability, in the market where skew is described as extreme because of physical delivery constraints.

**7. Delta-hedging the wrong contract month, or through the roll.** The option roll and the futures roll are different dates in gas. We already hit the data version of this defect. In an options book it means an entire session hedged against the wrong asset.

**8. The seasonal-boundary VRP artifact**, generating a confident 30-40 vol-point "signal" twice a year.

**9. Physical assignment on the American root**, into a contract with one business day of life. We cannot make or take delivery at Henry Hub.

**10. Procyclical margin.** Under SPAN/SPAN 2 (natural gas is a day-1 energy POD) short-option margin scales with vol, so the call arrives in the same week the position is losing, and exchanges raise scan ranges discretionarily during exactly those events.

**11. Over-trading because defined risk feels safe.** More trades against a 24% vol premium and a two-legged spread is a reliable way to convert a small edge into a certain loss. And the deeper version: "you only risk your premium" is true only if you do not hedge — the danger of a hedge that does not work is not the hedge, it is that believing you were protected made you size larger.

---

## 6. THE SEQUENCE

### Phase 0 — the decision calculation (days, not weeks; all on data we hold; zero trades)

**0.1 The shrinkage check.** Plot mean |blind forecast| by block, G19 → G23, against mean |actual move|. If our forecast magnitude has been shrinking toward zero, the MAE improvement is compression and the magnitude edge does not exist. **This is one query and it may end the programme. Run it first.**

**0.2 The skill ratio, per day, never pooled.** For every walked day: blind |error| ÷ (0.798 · F · σ_imp · √(1/365)), with σ_imp taken from our own settle surface for that date. Report the distribution and the per-day fingerprint. Also compute it against realized unconditional (blind |error| ÷ mean |actual move| over the window). Two tests: is there option edge, and is there any magnitude information at all.

**0.3 Wire the sigma yardstick into the harness.** Every forecast and every error gets printed in sigma units alongside dollars: σ_day = F·σ/√252. A $600 error on $3.41 gas at 44 vol is 0.64 sigma. That single conversion makes every future result legible.

**0.4 Measure k = RV/IV** at 1, 5 and 21 days, per season, per day-class, from the 294k settle surface plus our realized tape. This number does not exist in the literature at our tenor.

**0.5 The selection-bias sweep.** Re-run cohort matching at progressively looser tolerances and watch σ_emp. If it rises monotonically, the tight-match dispersion is biased low by that amount and every "implied is rich" reading is uninterpretable until corrected.

**0.6 Publish SE(σ_emp) = σ/√(2(N−1))** with every dispersion output. Add a hard gate: no trade whose edge is inside one SE.

**0.7 Decide the re-anchoring convention** (cents vs log returns) by testing both, and **decide the day-count once** and write it into RUN_SOP.md.

**Gate: if 0.1 or 0.2 fails, stop. Trade futures and Kalshi, extend the horizon, come back.**

### Phase 1 — make the surface trustworthy (only if Phase 0 clears)

**1.1 The put-call parity slope test, as a hard state_health gate.** For premium-paid-upfront options, C − P = e^{−rT}(F − K) exactly. So regressing (C − P) on K across a single (root, expiry, date) cell must give **slope = −e^{−rT} ≈ −0.997**. A slope near −0.0997 proves a x10 strike scale; a slope near −9.97 proves the reverse; a slope that is not near −1 at all proves a merged or mirrored ladder. This is an algebraic identity, exactly like the session_b_share identity that closed hole #9, and it must hard-fail the surface build. Run it across all 294k IVs and all 180 sessions before another line of options code is written.

**1.2 Fix the strike decode at source.** Databento issue, confirmed 12 Jun 2024: decode strikes with the **underlying future's** display_factor, not the option's. Then re-run 1.1 to prove it.

**1.3 Resolve the root question from our own instrument definitions, not from documentation.** The public tables contradict each other (one authority calls the American root ON with LN the look-alike; other sources call LN the American clearing code with LNE the European Globex root) and CME's pages block automated fetch. Pull the GLBX definition records, read exercise style, underlying_id, expiration, unit_of_measure_qty and display_factor, rank roots by measured volume and OI, and write the answer into KEYS.md as a **measured fact with a date**. Everyone agrees on the operative point: the liquid monthly root is the European/financially-settled one, the American is nearly dead, and they have different display factors.

**1.4 Tag every settle IV observed vs fitted.** Restrict all alpha claims to OTM, near-dated, actually-traded strikes. ITM = zero information (pure parity). Wing and deferred = exchange methodology output.

**1.5 Re-key the pin/OI map** by (root, expiry date, underlying **delivery** month). Never merge across roots. Add the explicit rule that a weekly expiring on the monthly's expiry day exercises into the **second** nearby, and assert the underlying per instrument rather than deriving it from the expiry date. Filter to the $0.25/$0.50 handles — an off-handle $0.05 strike with trivial OI is a listing artifact, not a pin.

**1.6 Ingest CVOL daily** (NGVL, NGSK, NGUP, NGDN, NGAM, NGCV). Free, independent construction, and therefore exactly the kind of external source that catches a well-formed-but-wrong internal value. Note it is simple-variance with equal strike weighting, so it is not VIX-comparable.

**1.7 Add three deterministic day-classes** to the harness, all computable years ahead: options expiry (4th business day before the 1st), futures LTD (3rd business day before), and the roll. Options expiry is repeatedly reported as a thin, jumpy session. Treat it like EIA Thursday.

### Phase 2 — measure the two parameters that decide P&L

**2.1 The vol path slope.** Regress Δ(ATM IV) on Δ(ln F), per contract month, per season, per curve regime. **Expect a positive slope in winter.** This single parameter converts a Black delta into an effective delta and therefore decides whether a correct path forecast converts into P&L. Hull & White report negative price-vol correlation for a pooled commodity sample, which conflicts — resolve it by measuring on our own data, where rr25 is already positive on every winter session. Then freeze the parameter; changing surface-dynamics models mid-book makes P&L attribution meaningless.

**2.2 The quote-based surface.** Build top-of-book bid/ask/size IVs from the GLBX MDP3 feed we already pay for, by (root × expiry bucket × delta bucket × handle-vs-off-handle × season), plus behaviour on EIA Thursdays and weather-event days. The settle surface stays as the **mark**; the quote surface becomes the **backtest input**. No public source has this and no strategy is real until we do.

**2.3 Re-mark the 51-event vertical replay** on quotes, at both RFQ economics (<1 tick) and legged economics (2.5-5 ticks), with the skew-dynamic assumption rather than a static surface. Report both. If the edge survives only at settle mids, there is no edge.

### Phase 3 — choose the instrument deliberately

Answer, in writing: one-session views go to **Kalshi** (horizon-native, already docked, with the digital-skew correction applied) or to the **future** ($13 round trip). Options require either a 5+ session horizon or a density product. If options: **LNE monthly only**, front two expiries, handles only, ±25-30 delta, and only structures that are implied-eligible UDS on Globex — **vertical, straddle, strangle, risk reversal, calendar, diagonal, guts, double**. Butterflies, condors and ratios are Generic Combos and must be legged; build the view in butterfly space (which is what a cohort naturally produces) and **execute it as verticals**. Always RFQ the package. Open a broker/ClearPort relationship *before* validation, not after — the 10-contract weekly block minimum makes off-screen size genuinely reachable at our size.

### Phase 4 — capital, and only then

Long-premium or defined-risk only. Never a naked wing. Risk report as a grid by delivery month and season bucket, with net **and gross** vega, gamma as delta-per-10-cents per month, theta with a separate weekend line, and vanna/volga/charm on the wings. Put charm on the Friday report explicitly as "delta drift to Monday open at unchanged price" — a 25-delta wing at 5 DTE sheds 2.3 delta points per calendar day, and the Friday-to-Monday seam is our documented weakest link. Stress grids must couple price and vol **positively and asymmetrically on the upside** and must include a front-to-back correlation break. Never a parallel vol shift.

---

## THE SENTENCE

**Our forecaster does not yet support an options business.** Blind direction is a coin flip, blind magnitude is at or near parity with the price of the market's own one-day straddle, the 10/10 refine is hindsight, the horizon has no liquid instrument, every mark we own is exchange-fitted, and our dispersion estimate at N=20 has a standard error five times larger than any mispricing that survives in a liquid market. Three independent biases in our method all point toward "sell vol," which in gas is the direction that ends desks.

What we do have is unusual and worth building toward: daily-resolution paths that separate terminal dispersion from path roughness, an empirical density that can be compared shape-to-shape against a Breeden-Litzenberger risk-neutral density, and — genuinely rare — an engineering culture that retires its own plays on forward tests. Point that at Phase 0. The answer arrives in days, and it is cheap.

---

**Verified this session:** [NGU26 front-month $3.41 (Google Finance)](https://www.google.com/finance/quote/NGM26:NYMEX) · [ATM IV 43.68%, 21 DTE, expiry 08/26/26 (Barchart)](https://www.barchart.com/futures/quotes/NG*0/volatility-greeks) · [CME CVOL methodology and NG index symbols](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457326006/CME+Group+Volatility+Indexes+-+CVOL) · [CME Henry Hub volume and open interest](https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.volume.html) · [Natural Gas Last-Day Financial Options contract specs](https://www.cmegroup.com/markets/energy/natural-gas/natural-gas-last-day.contractSpecs.options.html)