# Reading trade charts and testing market behavior

Research note for the Markets NG discovery project, November 8, 2026. Use it
when reviewing charts, defining signals, evaluating four-date recurrence,
or preparing simulator tests. The [October discovery log](october-discovery-log.md)
holds the observed cases and current rule status.

## Start with the event sequence

Describe the prior conditions, what changed, what was observable at the
decision, and what happened afterward. A price is a measurement. The
reusable pattern is a relationship or sequence, such as a touch holding
while displayed size falls, prints meeting a replenishing queue, or a best
quote disappearing next to sparse depth. A ratio can summarize the
behavior. Keep its operands and the events that produced them.

| Record | What belongs there |
| --- | --- |
| Prior conditions | Instrument, contract, best quotes, spread, nearby depth, recent flow, session phase, and external events already available |
| Observable behavior | Ordered prints and book changes, fixed-price size paths, and the first completed group at which the rule could fire |
| Subsequent movement | Direction, raw and percentage change, ticks, elapsed time, and the first retreat, recovery, or other declared outcome |
| Execution | Observable entry and exit quotes, order side, latency, fill status, and simulator action |

## Read the chart and its underlying data

| View | What it shows | What to inspect in the source |
| --- | --- | --- |
| Trade line or OHLC candles | Open and close form the candle body. High and low mark the range. A wick records an excursion within the interval. | The sequence of the high, low, quotes and prints. Two candles with identical OHLC and volume can reach their high and low in opposite order. |
| Best bid, ask, midpoint and spread | Bid and ask show the prices currently quoted. Their average is the midpoint. Their difference is the spread. | Compare quote changes and actual prints. Alternating executions at a fixed bid and ask can create apparent reversals in the last-trade line. |
| Time and sales, footprint or volume profile | Time and sales preserves individual prints. Footprints and profiles aggregate executions by price over a window. | Check the quote available before each print, the source of any side classification, and the window definition. Executed volume, displayed resting size, and options open interest are separate series. |
| Depth ladder, chart or heatmap | The ladder shows displayed levels at a moment. A depth chart commonly cumulates quantity away from the touch. A heatmap can show persistence or disappearance across time. | Track the same price and order through time. Separate a removal at a fixed price from a level changing rank when the touch moves. |
| Derived indicators | Moving averages summarize price history. Range and momentum measures summarize movement. VWAP weights trade prices by volume over a defined interval. | Record the price source, lookback, weighting, anchor, and availability. Indicators built from the same price series can agree because they reuse the same observations. |

The paths 100 → 101 → 99 → 100 and 100 → 99 → 101 → 100 have the same
OHLC. A replay that cares which threshold was reached first needs the
ordered trades. Bid–ask bounce similarly affects interpretation of small
last-trade reversals. [CME chart types](https://www.cmegroup.com/education/courses/technical-analysis/chart-types-candlestick-line-bar) · [Roll, 1984](https://authors.library.caltech.edu/records/afwsc-6bb61)

Check the exact contract, price series and aggregation rule. A trade
close, midpoint close and exchange settlement serve different purposes.
Separate continuous-series rolls and back adjustments from movements in a
single tradable contract. Fixed-time, event-count and volume bars cover
different amounts of activity and elapsed time. Databento's OHLCV labels
the start of each interval and omits intervals with zero trades. A completed
close only becomes observable after its contributing trades. Distinguish no
trades, a coverage gap and a charting choice before carrying a value forward.
[Databento OHLCV specification](https://databento.com/docs/schemas/ohlcv) · [CME market data field descriptions](https://www.cmegroup.com/trading/about-quotes.html)

## Read the tape and book together

On GLBX.MDP3, retain event time, capture receive time, source order and
the known-by time of the completed group. Apply every market-by-order
message in sequence. Databento's F_LAST marks the final record for an
instrument in a publisher event. Trade summaries, passive fills and
updates to displayed state carry different information. Follow the
dataset's state mutation rules and link fills to the relevant order and
price where the evidence allows. Preserve order and trade IDs for
linkage. Reset or warm up at feed boundaries and retain explicit missing
prehistory for partial days. [Databento order tracking](https://databento.com/docs/examples/order-book/order-tracking) · [GLBX.MDP3 normalization and timestamps](https://databento.com/docs/datasets/glbx-mdp3)

- **Queue imbalance** describes displayed state. A top-of-book example
  divides bid size minus ask size by their sum for a ready two-sided book
  with a positive denominator. Gould and Bonart found a relationship with
  the next midpoint move in ten Nasdaq stocks, stronger in their
  large-tick group. This motivates a conditional NG comparison by spread
  and depth. A fixed-second outcome has a different target and requires
  its own comparison. [Gould and Bonart](https://arxiv.org/abs/1512.03492)
- **Order-flow imbalance** describes changes at the best quotes across
  events, including adds, removals and changes in best price. At an
  unchanged ask, size removal and size addition contribute differently.
  When the best price moves, use the price-change terms of the declared
  formula. Cont, Kukanov and Stoikov related contemporaneous price changes
  to this measure and found the relationship varied with depth in their
  equity sample. A predictive NG comparison must end the flow window
  before the outcome starts. [Cont, Kukanov and Stoikov](https://arxiv.org/abs/1011.6402)
- **Trade imbalance** describes executions. Keep known-side buy and sell
  quantities and unknown quantity separately. A known-side ratio uses
  only known-side quantity in its denominator. A print relative to the
  prior quote supplies a price relationship. Treat any inferred aggressor
  side as an estimate and retain the actual feed side independently.
  Lee and Ready documented ordering and inside-spread ambiguities in
  equity trade classification. [Lee and Ready](https://doi.org/10.1111/j.1540-6261.1991.tb02683.x)

At a thinning touch, check whether the price still holds, how much display
remains there, where the next level sits, and which orders were removed or
replenished. A large move can follow a best quote disappearing next to a
gap in displayed depth. CME documents that a native iceberg refresh
retains the OrderID. Repeated display after fills supports an observation
of replenishment. The total reserve and participant intent remain unknown
from that sequence. [Farmer et al.](https://arxiv.org/abs/cond-mat/0312703) · [CME Market by Order FAQ](https://www.cmegroup.com/articles/faqs/market-by-order-mbo.html)

## Turn a chart shape into an event test

Translate a chart description into an ordered predicate with an earliest
decision coordinate, an invalidation condition and a separate outcome.
Lo, Mamaysky and Wang defined chart shapes algorithmically and compared
conditional return distributions with an unconditional distribution in
historical US equities. For NG, start with the market events behind the
shape and compare the actual occurrences. [Lo, Mamaysky and Wang](https://www.mit.edu/~alo/Papers/techanal.html)

| Chart description | Candidate sequence to record | Alternative to retain |
| --- | --- | --- |
| Breakout or failed breakout | Define the boundary from earlier visible observations. Record the first break, whether prints follow through, and whether quotes persist beyond it. | An isolated print, an immediate return, or a jump across sparse depth. A later return belongs in the outcome unless the rule waits for it. |
| Rejection, long wick or reversal | Record the approach, excursion, prints relative to the earlier touch, and first observable return or opposing quote change. | Bid–ask bounce, a single print or a withdrawal with little execution. |
| Trend or pullback | Track successive highs, lows or midpoint changes and the intervening prints, replenishment and retreats. Establish swing confirmation at the time it becomes observable. | A range with similar end-to-end displacement, or a swing visible only after later confirmation. |
| Compression or entropy change | Preserve the size observations in both completed blocks, their bin definitions, and changes in bin occupancy. Compare spread, depth and activity separately. | Sparse activity or the same entropy with a different size path. The entropy of bin counts summarizes a distribution and leaves event order unresolved. |
| Absorption or exhaustion | For absorption, link executed size to updates for the same order and price. For exhaustion, define which flow slowed and how the book responded. | Cancellation-led thinning, replenishment by new orders, or little observable aggression. Positive linked fills with zero displayed reduction leave the ratio undefined. |

October 18 illustrates why the path matters. Two standing bids reached
one contract at 3.154 with the same best bid and ask. One recovered at
the same price. The other retreated to 3.153. Compare the prior size
paths, print timing, update lineage, and distance to the next level.
Measure which differences were observable by the assumed entry. The
absorption calculation likewise retains the actual fills, displayed
reductions and observation span. Its long variant uses the observed
active span through the current close. [October 18 cases](october-discovery-log.md#october-18-observations) · [Project absorption definition](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-input-admission.md#second-set-encoding-and-absorption-definition)

## Measure movement and group comparable events

Choose the price series before comparing outcomes. For a positive
reference, signed percentage change is 100 × (later price − reference
price) / reference price. Keep the raw change, ticks when the tick size is
known, elapsed time and endpoint coordinates. For a zero, negative or
very small reference, keep raw and tick differences and declare any
additional normalization separately. Decision-to-later midpoint movement
describes the market response. Entry-to-exit quote movement is a separate
execution estimate tied to side and latency. Simulator fills have their
own records.

Group behavior by observable conditions such as pre-event depth, spread,
recent volatility, activity, session phase and trading weekday. Compare
moves over fixed elapsed horizons and, when useful, fixed event counts.
Retain flat, opposing, missing and censored cases. The timestamp places
the event and establishes what was knowable. Recurrence in a weekday or
clock bucket is an association. For a release hypothesis, use the actual
published event and its availability, compare the same clock bucket on
non-release dates, and retain the pre-release expectation if documented.
Linn and Zhu found higher volatility around gas storage announcements in
an older NYMEX sample. Direction and current NG behavior require their
own tests. [Linn and Zhu](https://onlinelibrary.wiley.com/doi/abs/10.1002/fut.10115) · [EIA release schedule and exceptions](https://ir.eia.gov/ngs/schedule.html)

### When a specific price level matters

An option ties the underlying price to a contractual reference. Map the
underlying month or settlement reference, call or put, strike, expiry
and settlement terms. Record signed distance to strike, time to expiry
and the separately observed option premium and spread. The same
percentage move can take one option through its strike while leaving
another far away. Use the series-specific terms applicable on the
historical date. [CME Henry Hub options specifications](https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.contractSpecs.options.html)

Strike concentration is a separate hypothesis. Open interest measures
outstanding contracts and volume measures contracts traded during an interval.
Use observations available at the decision time, including when open
interest was published. Separate calls and puts, strikes, expiries and
underlying months. Aggregate counts leave participant positioning and
dealer hedge direction unresolved. Compare approach, dwell time, crossing
and movement away at concentrated strikes against similar distances to
less concentrated strikes and ordinary round levels. Match time to
expiry and liquidity. [CME volume and open interest definitions](https://www.cmegroup.com/market-data/volume-open-interest/about.html)

Ni, Pearson and Poteshman documented expiration-day clustering in US
equities. Golez and Jackwerth reported attraction or repulsion in S&P 500
futures under different option expiry arrangements. This evidence
motivates distinct NG hypotheses about clustering, crossing and moving
away. The NGX3 touch and print ledger leaves strike concentration
unmeasured. [Ni, Pearson and Poteshman](https://experts.illinois.edu/en/publications/stock-price-clustering-on-option-expiration-dates/) · [Golez and Jackwerth](https://www.sciencedirect.com/science/article/pii/S0304405X12001365)

## Evaluate candidates before paper testing

1. **Write down the version.** Name the source fields, units, instrument,
   prerequisites, exact trigger, decision clock, lookback, reset and
   invalidation conditions. Label numerical cutoffs with the version
   that introduced them.
2. **Compare eligible opportunities.** Keep each rule decision, ambiguity
   or missing-input reason, and the denominator. Compare against similarly
   situated eligible groups without the trigger. For a stack, show both
   its full scope and a matched subset where all compared arms have
   usable inputs. Keep opposing calls on the same group.
3. **Preserve dependence and chronology.** Nearby groups and overlapping
   outcome windows share information. Count unique groups and episodes as
   well as raw calls. Fit thresholds or bins on earlier data and keep
   overlapping outcome windows out of the training and evaluation
   boundary. With enough coverage, use contiguous episodes or blocks for
   uncertainty estimates. Record all attempted variants to account for
   selection among many rules. [Sullivan, Timmermann and White](https://www.fmg.ac.uk/publications/discussion-papers/data-snooping-technical-trading-rule-performance-and-bootstrap) · [Politis and Romano](https://doi.org/10.1080/01621459.1994.10476870)
4. **Report distributions.** Show case and episode counts, positive,
   flat and opposing fractions, magnitude quantiles and censoring by
   date, side, horizon and context. Compare the time to retreat, recovery
   or replenishment with time to a feasible entry. Four discovery
   sessions provide few independent date clusters for inference.
5. **Separate discovery from execution.** October 2, 3, 17 and 18 are
   equal discovery dates, with October 2 and 17 explicitly partial.
   Apply coverage and formula admission before scoring. Freeze the
   version, trigger, side, order type, size, exit and simulator environment
   before a prospective paper test. Link market outcomes, simulator
   actions, and fills or misses as separate observations.
   [Discovery log and paper-test queue](october-discovery-log.md#paper-test-queue)
