# Commodity markets and price formation: a working primer

Compiled November 8, 2026 by Claude Code from six sourced research notes in
[research-notes/](research-notes/). This is background for the NG discovery program:
basic understandings to build from and argue with, not rules. Where the literature is
settled it says so; where it is contested or unknown it names the competing explanations
and the observation that would separate them. It contains none of the project's own
October findings.

Sourcing caveat: primary hosts (cmegroup.com, eia.gov, cftc.gov, arxiv.org, nber.org)
were outside this session's network allowlist, so numbers come from search summaries,
abstracts and secondary pages. Items marked (secondary) or (verify) should be confirmed
against the linked primary page before being quoted as hard facts. Each note file lists
its own gaps.

## 1. What a futures contract is and how Henry Hub natural gas trades

A futures contract is a cleared obligation, marked to market daily against the
exchange settlement price, with initial and maintenance margin posted at the clearing
house. A margin call restores equity to the initial level, not the maintenance level,
which makes forced liquidation lumpier than in securities margin accounts.
[CME margin education](https://www.cmegroup.com/education/courses/introduction-to-futures/margin-know-what-is-needed)

NYMEX Henry Hub Natural Gas (NG) specifics:

| Item | Value | Source |
| --- | --- | --- |
| Contract size | 10,000 MMBtu | [CME specs](https://cmegroup.com/trading/energy/natural-gas/natural-gas_contractSpecs_futures.html) |
| Tick | $0.001 per MMBtu, worth $10 per contract | CME specs (secondary confirmation) |
| Futures expiry | Third-last business day of the month before the contract month | CME specs |
| Standard options expiry | Fourth-last business day, one business day before the futures | [CME options guide](https://www.cmegroup.com/markets/energy/files/getting-started-with-micro-henry-hub-natural-gas-options.pdf) |
| Delivery | Physical, at Sabine Pipe Line's Henry Hub, Erath, Louisiana, ratably over the month | CME specs; NYMEX Chapter 220 (not retrieved) |
| Globex hours | About 6:00 pm to 5:00 pm ET, Sunday to Friday, 60-minute daily break (secondary) | [StoneX](https://futures.stonex.com/blog/money-never-sleeps-futures-trading-hours-run-23-5) |
| Regular trading hours | Begin 9:00 am ET | [Kurov et al. summary](https://clsbluesky.law.columbia.edu/2016/09/15/what-drives-informed-trading-before-public-releases) |
| Daily settlement | VWAP of outright trades in the 14:28 to 14:30 ET window, rounded to the tick; deferred months from spread VWAPs anchored to the front, 100-contract minimum; fallback to last trade checked against the 14:30 bid and ask | [NYMEX filing 2019](https://cftc.gov/filings/orgrules/rule091718nymexdcm005.pdf), [2015](https://www.cftc.gov/filings/orgrules/rule060815nymexdcm001.pdf) |
| Circuit breakers | Dynamic, rolling 60-minute window; the level (10 percent per the current page, 15 percent per a March 2020 notice) in force in October 2023 is unresolved (verify) | [CME](https://www.cmegroup.com/education/articles-and-reports/understanding-price-limits-and-circuit-breakers), [SER-8569](https://cmegroup.com/notices/ser/2020/03/SER-8569.pdf) |

Three things follow for intraday work. The settlement is a two-minute VWAP, so anyone
benchmarked to it must trade through the window, which concentrates volume and makes
the window's price a liquidity-weighted average rather than a marginal price; the curve
(deferred months) is fixed in the same two minutes through spread prints. Options expire
the day before the futures, so the penultimate day of the front month carries exercise
and assignment flows plus final futures positioning. The settlement window under EDT
(through November 4, 2023) is 18:28 to 18:30 UTC; after the November 5 clock change it is
19:28 to 19:30 UTC (inference; verify).

Continuous series: a single contract month needs no adjustment; splicing months requires
a declared method (difference or ratio back-adjustment), and each method breaks a
different property (point value or percentage change).
[Quantpedia](https://quantpedia.com/continuous-futures-contracts-methodology-for-backtesting/)

## 2. Who trades and why: the two theories of the curve

The CFTC classifies reporting traders by predominant business purpose into Producer,
Merchant, Processor or User; Swap Dealer; Managed Money; and Other Reportables, as of each
Tuesday's open interest. Staff classify traders, not trades.
[CFTC explanatory notes](https://www.cftc.gov/MarketReports/CommitmentsofTraders/DisaggregatedExplanatoryNotes/index.htm)

Two frameworks explain risk premia and the shape of the curve, and they are not settled
against each other:

- **Hedging pressure (Keynes, Hicks; Bessembinder 1992; de Roon, Nijman and Veld 2000).**
  Net hedger positioning earns speculators a premium; own and cross hedging pressure
  explain futures returns across 20 markets.
  [de Roon et al.](https://ideas.repec.org/a/bla/jfinan/v55y2000i3p1437-1456.html).
  Kolb (1992) found "normal backwardation is not normal" across 29 contracts (secondary).
- **Theory of storage (Kaldor, Working; Fama and French 1987; Gorton, Hayashi and
  Rouwenhorst 2013).** Basis = interest plus storage cost minus convenience yield, with
  inventories as the state variable. Convenience yield is a decreasing nonlinear function
  of inventories; low inventories go with backwardation, high with contango; GHR find no
  evidence that participants' positions predict premia.
  [NBER w13249](https://nber.org/papers/w13249)

Kang, Rouwenhorst and Tang (2020) partly reconcile them: hedging pressure mixes
speculators' short-horizon liquidity demand and hedgers' long-horizon insurance demand,
which move expected returns with opposite signs.
[JF 2020](https://econpapers.repec.org/RePEc:bla:jfinan:v:75:y:2020:i:1:p:377-417)

For natural gas the seasonal cycle is storage theory: injection season (nominally April
to October, not strictly) builds inventory; the winter strip carries a scarcity premium
whose size depends on how full storage is. The March/April spread (the "widowmaker") is
the market's price for end-of-winter risk; it reached a record $2.13 in May 2022 and a
record-low premium in 2023.
[EIA on seasons](https://www.eia.gov/todayinenergy/detail.php?id=18211),
[Oil and Gas 360](https://www.oilandgas360.com/u-s-natgas-price-collapse-cut-2023-widow-maker-premium-to-record-low/)

## 3. Natural gas fundamentals and their clocks

**The storage report.** The EIA Weekly Natural Gas Storage Report is released Thursday at
10:30 am ET (14:30 UTC), covering working gas as of 9:00 am the prior Friday, so the
number is six days stale at release. Holiday weeks move it to Wednesday noon or Friday.
It is sampled through Form EIA-912 from the EIA-191 census and is EIA's only Principal
Federal Economic Indicator. [EIA methodology](https://ir.eia.gov/ngs/methodology.html),
[schedule](https://ir.eia.gov/ngs/schedule.html)

Consensus is accurate: the median Bloomberg forecast anticipates over 99 percent of the
variation in storage changes and is impounded before release; analyst error averaged
13.2 Bcf in a 1997 to 2004 sample, larger in withdrawal season.
[Ederington et al. 2019](https://ideas.repec.org/a/sae/enejou/v40y2019i5p121-142.html),
[Gay, Simkins and Turac via NGI](https://www.naturalgasintel.com/study-finds-average-13-2-bcf-error-in-analysts-weekly-storage-predictions-2/)

What the report does to prices, from the announcement literature:

| Finding | Source |
| --- | --- |
| Volatility elevated at release and for about 30 minutes after; also heavy at open and close | [Linn and Zhu 2004](https://ideas.repec.org/a/wly/jfutmk/v24y2004i3p283-313.html) |
| Price moves inversely to the storage surprise, on release day only; futures lead spot; response roughly doubled after 2005 | [Chiou-Wei, Linn and Zhu 2014](https://econpapers.repec.org/RePEc:eee:jimfin:v:42:y:2014:i:c:p:156-173) |
| OLS understates the impact because the surprise variable is noisy; corrected estimates about four times larger for NG | [Halova, Kurov and Kucher 2014](https://ideas.repec.org/a/wly/jfutmk/v34y2014i10p911-933.html) |
| Pre-announcement drift begins about 90 minutes before, at the 9:00 am open, and is correlated with the surprise | [Kurov et al. 2018](https://ideas.repec.org:443/a/wly/jfutmk/v38y2018i9p1079-1096.html) |
| More than half of NG futures' annual return accrues on announcement days; the pre-announcement return occurs only ahead of bearish surprises, which argues against simple informed trading | [Prokopczuk, Wese Simen and Wichmann 2021](https://iaee.org/ej/ejexec/ej42-2-Wichmann-exsum.pdf) |

The coefficient in cents per Bcf was not retrievable from any of these.

**Weather.** GFS and ECMWF run at 00, 06, 12 and 18 UTC; ECMWF products arrive about
08:30 UTC (00z) and 20:30 UTC (12z), provisional. The midday (12z) run is the one traders
watch; a 2013 source puts the market-moving window at 11:00 am to 1:00 pm ET. Weather
affects about half of US gas demand; weather surprises move both the mean and the
volatility of NG returns.
[NOAA GFS](https://www.ncei.noaa.gov/metadata/geoportal/rest/metadata/item/gov.noaa.ncdc:C00634/html),
[ECMWF schedule](https://confluence.ecmwf.int/spaces/DAC/pages/272310483/Dissemination+schedule),
[Mu 2007](https://ideas.repec.org/a/eee/eneeco/v29y2007i1p46-63.html)

A lesson from orange juice: Roll (1984) found weather explained little of OJ futures
variance; Boudoukh et al. later showed the puzzle dissolves once you condition on the
nonlinear freeze threshold. The same logic applies to heating demand: condition on the
HDD regime before concluding weather does not matter.
[Boudoukh et al.](https://archive.nyu.edu/bitstream/2451/26487/2/02-43.pdf)

**Why gas is so volatile.** Both supply and demand are inelastic in the short run,
storage is finite, and the system is pipeline-bound and regional, so any fundamental
shock produces large swings. Crude volatility predicts gas volatility but not the other
way round; volatility shocks are short-lived. Front-month annualised volatility was about
81 percent in Q4 2024 and about 69 percent by mid-2025 (secondary), so thresholds in
absolute dollars are non-stationary by construction.
[EIA 2003](https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2003/10_23/Volatility%2010-22-03.htm),
[Pindyck 2003](https://ceepr.mit.edu/workingpaper/volatility-in-natural-gas-and-oil-markets-2/)

**October 2023 context.** Prompt below $2.90 early in the month, spot above $3 for the
first time since January in the week of October 5, $3.18 on October 11 and $2.90 on
October 18; storage 3,700 Bcf on October 20, 182 Bcf (5.2 percent) above the five-year
average; record production (113.1 Bcf/d marketed), record LNG feedgas, record consumption.
A comfortable-storage, record-supply regime with a compressed winter premium.
[EIA NGWU Oct 19](https://www.eia.gov/naturalgas/weekly/archivenew_ngwu/2023/10_19),
[AGA Oct 31](https://www.aga.org/research-policy/resource-library/natural-gas-market-indicators-october-31)

## 4. What a price movement is, mechanically

In a limit order book the midpoint changes in exactly two ways: the best queue on one
side reaches zero (by fills or by cancellations), or a new order is posted inside the
spread. Trade size is a weak cause; the depth sitting at the best price is the strong one.
Large price changes come from gaps in the book, not from large trades.
[Farmer et al. 2004](https://arxiv.org/abs/cond-mat/0312703)

On CME market-by-order data (GLBX.MDP3 via Databento) every add, modify, cancel, fill and
trade summary is visible with order identity and FIFO priority. The book is valid only on
records flagged `F_LAST` (end of a matching event per instrument); between those records
the displayed best may already have traded. `ts_event` is the matching engine clock,
`ts_recv` the capture clock. Databento has announced that from July 2026 the `F_LAST` flag
moves to a separate `action='N'` record. Iceberg refreshes keep the same order ID and go
to the back of the queue, so hidden liquidity on Globex is detectable after the fact as
repeated same-ID refreshes at one price.
[Databento GLBX.MDP3](https://databento.com/docs/venues-and-datasets/glbx-mdp3),
[Databento 2026 change](https://databento.com/blog/cme-normalization-changes-2026-07),
[CME matching steps](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457218521/CME+Globex+Matching+Algorithm+Steps)

A sweep is one matching event: a trade summary (T) with the aggressor side, fills (F)
against resting orders at successively worse prices, then cancels or modifies for the
orders that were exhausted. A trade moves the quote only if the aggressor's size at least
equals the displayed size of the queue it hits. On CME the aggressor side is supplied by
the exchange, so trade signing is exact; the Lee-Ready problem (75 to 85 percent accuracy
in equities) does not arise for trades, only for the question of which non-trade events
to count as flow.
[Ellis, Michaely and O'Hara](https://resolve.cambridge.org/core/journals/journal-of-financial-and-quantitative-analysis/article/abs/accuracy-of-trade-classification-rules-evidence-from-nasdaq/A2CAD2206B562784527548F5283A9ECB)

Classic theory and what it predicts about the price response to a trade:

- **Kyle (1985):** linear, permanent impact; lambda is the inverse of depth.
- **Glosten and Milgrom (1985):** the spread is the cost of adverse selection; each trade
  moves the quote permanently by the market maker's Bayesian update.
- **Inventory models (Ho and Stoll; Amihud and Mendelson):** transient pressure that
  reverts as the dealer rebalances, giving negative autocorrelation in price changes.
- **Hasbrouck (1991):** the cumulative impulse response of the quote to a trade innovation
  separates the permanent (information) plateau from the transient (inventory) overshoot.
- **Roll (1984):** bid-ask bounce alone creates negative autocorrelation in trade prices;
  it is measurement, not a return.

Empirical regularities that replicate:

| Regularity | Scope of evidence | Source |
| --- | --- | --- |
| Short-horizon midpoint change is linear in order-flow imbalance at the best quotes, slope about 1/depth; adds and cancels carry impact comparable to trades, and dominate in large-tick books | 50 NYSE stocks; US equities | [Cont, Kukanov and Stoikov](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1712822), [Eisler et al.](https://arxiv.org/abs/0904.0900) |
| Queue imbalance (bid size minus ask size over their sum) predicts the next midpoint move strongly in large-tick instruments (spread pinned at one tick) and weakly in small-tick ones | Nasdaq LOBSTER | [Gould and Bonart](https://arxiv.org/html/1512.03492v1) |
| Metaorder impact grows as about the square root of size (exponent 0.5 to 0.6), measured on futures | CFM futures metaorders 2007 to 2010, about 500,000 trades | [Toth et al. 2011](https://www.arxiv.org/abs/1105.1694v3) |
| Order flow has long memory (Hurst about 0.6 to 0.8) while prices are nearly uncorrelated; the persistence is order splitting by single institutions, not herding | LSE with member IDs | [Lillo and Farmer](http://sfi-edu.s3.amazonaws.com/sfi-edu/production/uploads/sfi-com/dev/uploads/filer/d0/d9/d0d92e50-17b7-4072-98a7-293ca01b8d89/03-12-066.pdf), [Toth et al. 2015](https://arxiv.org/pdf/1108.1632) |
| Impact of a metaorder decays after it ends, to roughly two-thirds of peak within the day (contested whether to zero) | ANcerno US equities | [Bucci et al.](https://arxiv.org/pdf/1901.05332), [Brokmann et al.](https://arxiv.org/pdf/1407.3390) |
| Event arrivals are self-exciting; the Hawkes branching ratio is near one in E-mini futures, though the "rising reflexivity" reading is kernel-dependent | E-mini S&P 1998 to 2012 | [Hardiman, Bercot and Bouchaud](https://arxiv.org/abs/1302.1405), [Filimonov and Sornette](https://arxiv.org/abs/1308.6756) |
| After an aggressive order, spreads and depth recover within about 20 best-limit updates, with partial price reversal; fast replenishment happens only in a minority of cases | Paris Bourse; LSE | [Degryse et al.](https://econpapers.repec.org/RePEc:oup:revfin:v:9:y:2005:i:2:p:201-242.), Large 2007 (not fetched) |
| Liquidity vanishes when providers with no quoting obligation cancel ahead of being hit; the 2010 flash crash was a large selling program meeting a withdrawing book; HFTs did not trigger it but exacerbated volatility | CFTC audit trail, E-mini | [Kirilenko et al.](https://www.repository.cam.ac.uk/handle/1810/304244) |

The single most important moderator is tick size. In a one-tick-spread book the only way
the midpoint moves is a queue depleting, so the ratio of queue sizes is the race, and
imbalance predictability is strong; in multi-tick books it collapses. Whether front-month
NG at $0.001 is a large-tick book in the day session is an empirical question the tape
can answer; back months and overnight will be small-tick. Results should never be pooled
across the two regimes. [Dayri and Rosenbaum](https://arxiv.org/abs/1207.6325)

Exchange mechanisms interrupt normal dynamics during fast moves: CME Velocity Logic
(reserves the market when price moves too far too fast within a one-second window) and
Stop Logic (reserved state when triggered stops would move price beyond the no-bust
range; it produced the five-second pause on May 6, 2010). Reserved states accumulate
order flow without price response and should be excluded like the settlement window.
[CME Velocity Logic](https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457218368/Velocity+Logic)

Peer-reviewed microstructure work on NYMEX natural gas books specifically is thin to
absent; depth, spread-in-ticks, resiliency and settlement-period behaviour have to be
measured from the project's own data.

## 5. Market psychology: what is established and what is not

Established at the individual level, almost entirely in equities and retail accounts at
daily to monthly horizons: the disposition effect (selling winners, holding losers),
underperformance of high-turnover retail traders (Taiwan day traders: 97 percent expected
to lose, under 1 percent persistent winners), attention-driven buying, and extrapolative
survey expectations that are negatively correlated with subsequent returns.
[Barber, Lee, Liu, Odean, Zhang](https://econpapers.repec.org/RePEc:oup:rasset:v:10:y:2020:i:1:p:61-93.),
[Greenwood and Shleifer](https://nber.org/system/files/working_papers/w18686/w18686.pdf)

Most damaged: loss aversion as a general, stake-independent law (Gal and Rucker 2018,
rebutted by Mrkva et al. 2020). Fama's 1998 objection stands: overreaction and
underreaction appear about equally often and anomalies are methodology-sensitive. Lo's
adaptive markets hypothesis reframes biases as heuristics that work in some regimes and
not others, which maps onto per-cell evaluation.
[Gal and Rucker](https://papers.ssrn.com/abstract=3049660),
[Lo 2004](https://web.mit.edu/~alo/www/Papers/JPM2004.html)

The futures evidence is thin and old but direct:

- Coval and Shumway (2005), CBOT T-bond locals, 1998 audit trail: traders with morning
  losses were about 16 percent more likely to take above-average afternoon risk; they
  bought above and sold below prevailing prices; their price impact reverted faster than
  others' and other traders faded them. A behavioral footprint exists on the tape and is
  transient. [CFA Digest](https://rpc.cfainstitute.org/research/cfa-digest/2005/11/do-behavioral-biases-affect-prices-digest-summary)
- Locke and Mann (2005), CME floor locals: losses held longer than gains, framed as
  "discipline"; exact figures not retrieved.
- Boyd et al. (2016), 30 US futures markets 2004 to 2009: managed-money herding is real,
  does not destabilize prices, and declines with electronic trading.
  [JFM 2016](https://econpapers.repec.org/RePEc:wly:jfutmk:v:36:y:2016:i:7:p:671-694)
- Osler (2003), one FX bank's orders: take-profits cluster at round numbers, stops just
  beyond them, so support and resistance bounces and post-break accelerations are
  mechanically self-fulfilling; stop cascades produce continuation, not the retail "sweep
  and reverse". No comparable study exists for CME energy.
  [NY Fed SR 125](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr125.pdf),
  [SR 150](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr150.pdf)
- Menkhoff (2010), 692 fund managers: technical analysis dominates at weekly horizons,
  and its users believe prices are psychologically driven.
  [JBF 2010](https://econpapers.repec.org/RePEc:eee:jbfina:v:34:y:2010:i:11:p:2573-2586)

The central methodological point for tape work: every behavioral footprint has an
observationally equivalent mechanical generator.

| Behavioral story | Mechanical twin | What separates them |
| --- | --- | --- |
| Herding, copying | Order splitting of one institution's parent order; common reaction to a public number | Participant IDs; timing relative to the release |
| Panic, capitulation | Stop orders converting to market orders; margin liquidation; market makers re-centering quotes | Order-type data; whether cancelled IDs re-appear at new prices |
| Loss-chasing | Inventory-constrained market makers forced to unwind | Account P&L (audit trail only) |
| Anchoring to round numbers | Option strikes and dealer gamma hedging; algorithms quoting one tick ahead of the cluster | Strike open interest; order placement relative to the cluster |
| Attention-driven buying | The news itself; hedging flows it triggers | Does the drift revert (attention) or persist (information) |

Attribution to psychology has only ever been achieved with participant-identified data.
On an anonymous tape the behavioral layer is a set of named alternatives whose
predictions about timing and reversal can be tested per cell; it is not a source of
direction on its own. Physiological studies (cortisol tracks uncertainty, testosterone
tracks P&L, 10 to 17 traders) establish a channel but no price footprint.
[Coates and Herbert](https://pmc.ncbi.nlm.nih.gov/articles/PMC2329689)

## 6. What quants look for and how they avoid fooling themselves

Quants hunt four kinds of edge: risk premia, behavioral anomalies, liquidity provision
and microstructure, and information speed. The published record says most discoveries
are inflated: anomaly returns fall about 26 percent out of sample and about 58 percent
after publication; a published strategy's Sharpe roughly halves; a new factor should
clear t greater than 3.0, not 2.0, given cumulative data mining.
[McLean and Pontiff](https://Www.Gwern.net/doc/economics/2016-mclean.pdf),
[Harvey, Liu and Zhu](https://papers.ssrn.com/abstract=2513152),
[CFM half-life study](https://arxiv.org/pdf/2105.01380)

Commodity signals that have survived decades of replication are all slow: time-series
momentum (positive in every one of 58 contracts 1985 to 2009; positive every decade since
1880 across 67 markets), carry and term structure (within-class Sharpe 0.5 to 0.9), hedging
pressure sorts (contested by GHR), basis-momentum (JF 2019). None speaks to minute-scale
behavior. The intraday evidence that exists for energy is event-time structure: the
storage release and open and close volatility.
[Moskowitz, Ooi and Pedersen](https://econpapers.repec.org/RePEc:eee:jfinec:v:104:y:2012:i:2:p:228-250),
[Koijen et al.](https://www.nber.org/papers/w19325),
[Boons and Prado](https://ideas.repec.org/a/bla/jfinan/v74y2019i1p239-279.html)

The validation protocol, and why it matters with few independent days:

- The unit of independence is the day or the event, not the tick. CFM's identity
  t = Sharpe times the square root of years says no tick-level Sharpe is significant on
  its own; about 50 storage releases per year per contract is the true sample size for
  any announcement-conditioned claim.
  [CFM Lucking Up](https://www.cfm.com/wp-content/uploads/2022/12/187-Lucking-Up.pdf)
- Purge training samples whose label window touches the test period and embargo the
  following session; bootstrap at the block or day level (stationary bootstrap, block
  length at least a session). Overlapping forward windows share increments, so the
  effective sample is about N/k and naive standard errors are overstated by about the
  square root of k.
  [Politis and Romano](https://gnosis.library.ucy.ac.cy/handle/7/57533),
  [purged CV](https://en.wikipedia.org/wiki/Purged_cross-validation)
- Track the number of trials. Every cell, threshold and variant examined is a test;
  deflate for them (deflated Sharpe ratio, probability of backtest overfitting, minimum
  backtest length about 2 ln(N) over the squared expected maximum).
  [Bailey and Lopez de Prado](https://papers.ssrn.com/abstract=2460551)
- Sullivan, Timmermann and White: the best of a large universe of technical rules shows
  no genuine outperformance once data snooping across the universe is accounted for.
  [JF 1999](https://econpapers.repec.org/RePEc:bla:jfinan:v:54:y:1999:i:5:p:1647-1691)
- Score probabilistic forecasts with a proper rule (Brier) and its reliability component,
  not hit rates; a three-way up, flat, down target keeps flats in the denominator.
- Look-ahead through the signal definition is the subtle one: a feature computed over an
  interval whose end is defined by the outcome (the leg ends when price reverses; the
  metaorder ends when the trader stops) is conditioned on the future.

Machine learning: Gu, Kelly and Xiu report monthly out-of-sample R squared of about 0.3
to 0.4 percent and a 1.35 Sharpe long-short, which a replication thesis could not
reproduce. Order-book deep learning (Sirignano and Cont; DeepLOB) reaches about 70 percent
next-move accuracy on equities, but the 2023 cross-dataset benchmark found most models
overfit the FI-2010 set and degrade sharply on unseen data. Microstructure predictability
is real at the next-event horizon and is venue-, tick- and regime-specific.
[Sirignano and Cont](https://arxiv.org/abs/1803.06917v1),
[Prata et al.](https://arxiv.org/pdf/2308.01915.pdf)

Practitioner habits that recur: Renaissance's three steps (find the anomaly, confirm it
is significant and consistent, then seek an explanation but keep it if none is found);
most academic strategies failed in-house replication; Carver's "weight, do not drop"
rule for weak signals and small simple rule pools; CFM's point that portfolio Sharpe
grows with the square root of the number of independent signals, so many weak signals
beat one strong one. Impact is the bridge from gross signal to tradeable edge: the
square-root law means edge over impact deteriorates as the square root of size, which
defines capacity. The project excludes trade cost from research, but the concept is why
a small hit-rate edge can still exist (Medallion's reported 50.75 percent, second-hand).
[Zuckerman notes](https://novelinvestor.com/notes/the-man-who-solved-the-market-by-gregory-zuckerman/),
[Carver via CXO](https://www.cxoadvisory.com/big-ideas/a-few-notes-on-systematic-trading)

## 7. What nobody has explained

Regularities everyone accepts whose causes are open:

| Puzzle | Status | Competing explanations | What would separate them |
| --- | --- | --- | --- |
| Fat tails (return tail exponent about 3) | Regularity settled, mechanism open | Large-trader size plus concave impact (Gabaix et al.) vs endogenous self-excitation and liquidity criticality; Farmer and Lillo show volume alone fails | Condition tails on volume and trade frequency across markets; test whether exponents move with institutional concentration |
| Volatility clustering and long memory | Regularity settled; "rough volatility" is contested as a fact (Cont and Das: realized volatility looks rough even when spot volatility is not) | News-arrival mixture vs interacting heterogeneous agents vs order splitting | Compare clustering persistence on release vs non-release days; apply the roughness estimator where microstructure noise is absent |
| Most large moves have no news | Replicated at every resolution (Cutler, Poterba and Summers 1989; Fair 2002; Joulin et al. 2008; Ait-Sahalia and Li 2024, who also rule out insider trading as the bulk explanation) | Flow and inelastic demand vs endogenous liquidity dynamics vs discount-rate variation | Post-jump volatility relaxes differently after news jumps and liquidity jumps; exogenous flow shocks with no information content give the multiplier |
| Long-memory order flow with martingale prices | Settled; splitting origin is near-consensus; the compensating mechanism is open | Power-law decaying impact propagator (Bouchaud et al.) vs asymmetric liquidity (Lillo and Farmer) vs multi-timescale latent book | Impact trajectories when a metaorder is interrupted or reversed |
| Square-root impact | Broadly accepted; exact exponent and universality contested | Latent liquidity vanishing at the price (Toth, Donier) vs Kyle-Obizhaeva invariance | Exponent as a function of participation rate; bet-size scaling across assets |
| Momentum and reversal coexisting | Trend profitable over a century; cause open | Underreaction then overreaction vs hedging premia vs slow institutional flows; reversal as compensation for liquidity provision (Nagel) | Trend returns should scale with asset-level flow persistence if flow-driven; momentum crashes are partly forecastable, which a pure risk story cannot absorb |
| Inelastic markets ($1 of flow moves aggregate value about $5) | Open; identification under attack | Mandate-constrained institutions vs persistence contaminating elasticity estimates (van Binsbergen, David and Opp) | Elasticity estimates should fall as the horizon passes the instrument's persistence; roll-window flows in futures |
| Commodity index "financialization" | Masters bubble hypothesis mostly rejected; changed co-movement mostly accepted | Irwin and Sanders vs Singleton (significant flow effects on imputed positions) and Tang and Xiong | The index versus non-index co-movement gap should have narrowed after index AUM fell |

Commodity-specific puzzles:

- **Natural gas announcement-day puzzle.** More than half the annual return on EIA days,
  with the pre-announcement return realized only ahead of bearish surprises; practitioners
  record identical surprise signs producing opposite moves within a week. No systematic
  test of post-announcement asymmetry was retrievable.
  [Prokopczuk et al.](https://iaee.org/ej/ejexec/ej42-2-Wichmann-exsum.pdf)
- **Futures as forecasts.** Energy futures are roughly unbiased but rarely beat a
  no-change forecast; EIA forecasts are worse than no-change; the one robust conditional is
  that futures beat the random walk when the basis exceeds about 5 percent.
  [Alquist, Kilian and Vigfusson](https://www.federalreserve.gov/econres/ifdp/forecasting-the-price-of-oil.htm),
  [FEDS Notes 2026](https://www.federalreserve.gov/econres/notes/feds-notes/revisiting-the-forecasting-potential-of-futures-prices-20260903.html)
- **Negative WTI, April 20, 2020.** The CFTC interim report named fundamentals plus
  unspecified "technical factors" and, by a commissioner's own statement, did not identify
  a root cause; academics converge on expiry and trade-at-settlement closing pressure.
  [CFTC release](https://www.cftc.gov/PressRoom/PressReleases/8315-20),
  [Ge et al. AEA 2023](https://aeaweb.org/conference/2023/program/paper/FRQksbtk)
- **Samuelson effect** (volatility rising toward expiry) is absent in most contracts and
  present in about 30 percent of energy contracts; where it holds, the Bessembinder
  covariance mechanism fits.
  [Daal, Farhat and Wei](https://econpapers.repec.org/RePEc:wly:revfec:v:15:y:2006:i:2:p:113-128)
- **Amaranth and the widowmaker.** The loss ($4.9 to $6.4 billion depending on source)
  is documented; a statistical study found no significant effect of its positions on
  prices or spreads, while contemporaries said it propped up the curve. Contested.
- **Absorption and exhaustion** as practitioners define them have no academic test; the
  nearest published relatives are iceberg detection and replenishment on CME
  (Zotikov and Antonov 2021), detected icebergs attracting market orders (Frey and
  Sandas), and a crypto preprint finding that reversal after flow-driven moves scales with
  the flow and not with any hole in the book.
  [Zotikov and Antonov](https://ideas.repec.org/a/taf/quantf/v21y2021i11p1977-1992.html),
  [arXiv 2608.21888](https://arxiv.org/pdf/2608.21888)

## 8. Unconventional framings and what they have actually earned

Ranked by evidence, from the novel-frameworks note:

**Strong evidence.** The square-root impact law on futures (Toth et al.). Intraday
momentum from option-dealer gamma hedging across more than 60 futures including
commodities, strongest when dealers are short gamma (Baltussen, Da, Lammers and Martens,
JFE 2021). Order flow explaining more than half of daily FX changes and beating a random
walk out of sample (Evans and Lyons). Broker-dealer risk capacity forecasting energy
futures returns in and out of sample (Etula 2013). Zero-intelligence order flow explaining
96 percent of cross-sectional spread variance and 76 percent of volatility variance
(Farmer, Patelli and Zovko), with the caveat that it gets direction right and magnitude
wrong. Latency-arbitrage races about once per minute per symbol (Aquilina, Budish and
O'Neill).
[Baltussen et al.](https://econpapers.repec.org/RePEc:eee:jfinec:v:142:y:2021:i:1:p:377-403),
[Evans and Lyons](https://www.nber.org/papers/w7317.pdf),
[Etula](https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr406.pdf),
[Farmer et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC548562)

**Useful frames with indirect support.** The latent order book (Donier et al.): the
visible book is mostly market makers; the real supply and demand is a hidden reservoir of
intentions, vanishingly thin near the price, which makes small orders disproportionately
impactful and predicts partial reversion when a flow stops. Market ecology (Farmer;
Scholl, Calinescu and Farmer): strategies are species competing for the same flow,
returns are density-dependent, and edges are consumed as capital crowds in; demonstrated
in a toy model, not measured on real strategy capital. Kyle-Obizhaeva invariance: bet
size, arrival rate and impact scale with dollar volume and volatility in "business time",
which gives a dimensional null for how much a book should move per contract.
[Donier et al.](https://arxiv.org/abs/1412.0141v3),
[Scholl et al.](https://arxiv.org/pdf/2009.09454v2.pdf),
[Kyle and Obizhaeva](https://pages.nes.ru/aobizhaeva/Kyle-Obizhaeva-ECTA-2016-Invariance-with-Supplement.pdf)

**Contested.** Log-periodic bubble prediction (Sornette): some ex-ante calls, documented
misses, and the functional form is "sloppy" under small sample changes. The Hawkes
branching ratio read as rising "reflexivity": kernel-choice dependent, with regime
switching producing spurious criticality. Self-organized criticality inferred from power
laws: log-normals fit as well (Clauset, Shalizi and Newman). Risk-parity feedback:
accepted sign, disputed size.

**Narrative only.** Soros's reflexivity at any intraday level; Minsky at trading
frequency; Market Profile value area and the "80 percent rule"; Wyckoff; footprint delta
divergence; "stop hunt then reverse" (the evidence points to continuation after a stop
cluster trades); "markets as measurement devices" and order-book conservation laws beyond
the reaction-diffusion annihilation picture.

Two framings worth carrying as hypotheses because they generate testable order-book
predictions: flow and inventory pricing (the sign of recent aggressive flow should explain
the next move far better than any fundamental at seconds horizons, and impact per unit
flow should rise when intermediary capital is constrained), and the latent-book
conservation picture (a move driven by a transient-inventory holder must be unwound and
so reverts; a move driven by a hedger changing open interest need not).

## 9. What an order-book researcher can and cannot see

Observable on CME MBO: every displayed order's birth, size changes, price changes, fills
and removal, with queue priority; the aggressor side of every trade; iceberg refreshes by
order ID; spread, depth at every level, and their changes event by event; the matching
engine clock and the capture clock; exchange reserved states; declared publication clocks
for scheduled releases.

Not observable: who owns an order; whether two orders belong to one participant (order
splitting versus herding); the undisplayed remainder of an iceberg before it refreshes;
stop orders before they trigger; positions, P&L, margin state and risk limits; whether a
cancellation was fear, repricing or a hedge completing; beliefs, intent and hormones.
Implied liquidity from calendar spreads appears in aggregated depth but not as individual
orders (unconfirmed for GLBX.MDP3).

Consequences: trade signing is exact but flow definition is a choice; book state is valid
only at event boundaries; a quote can be stale by seconds in a quiet book, so every
"pre-event" snapshot carries an age; every behavioral reading has a mechanical twin that
the anonymous tape cannot separate without a timing or reversal test; the day or the
release, not the tick, is the unit of independence; and fundamentals enter the intraday
tape mostly at fixed clocks (10:30 ET Thursdays, model runs at 00, 06, 12, 18 UTC, the
14:28 to 14:30 ET settlement), with the rest of the tape's movement attributable, on
present evidence, mostly to the flow and liquidity dynamics in sections 4 and 7.
