# NG trade prebirth, dipoles, and exhaustion research log

**2026-11-08.** First quantitative discovery pass using the existing
October 18, 2023 NGX3 tape and lifecycle artifacts. October 2, 3, 17 and 18
remain equal discovery dates, with October 2 and 17 explicitly partial.
This entry reports descriptive counts and timing checks. Independent
forecast validation, full discovery scoring and simulator rules remain
separate.

## Define the event whose prebirth we are studying

- **Execution.** Anchor at the original T print. The prebirth ends at a
  completed group strictly earlier in tape order. Use event and receive
  clocks plus source cursor. Multiple prints can share a group. For a
  prediction, sample eligible decision groups before looking forward and
  keep groups followed by no print as controls.
- **Resting order lifecycle.** A passive fill can link to an observed add,
  modification, partial fill, refill or removal by order ID and price.
  Record the first observed order state and its coverage. A snapshot can
  establish that an order exists while leaving its actual birth unresolved.
  The aggressor's private decision remains outside the public tape.
- **Quote or dipole lifecycle.** A quote episode has its own onset and
  first observable recovery, retreat or improvement. A dipole candidate,
  its later phase changes and its final serialized path have separate
  availability times. Preserve the earliest valid evidence for each.
- **Structural family.** The earlier project scoped a separate 120-second
  inspection window for each of 749 referenced family IDs. That is a
  historical family-start investigation. This pass uses original prints
  and quote events as its anchors. [Prior family prebirth scope](../../artifacts/sqlite-triage/20261022/families/family-prebirth-scope.txt)
  · [Trade chronology and retained source links](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/chronological-lifecycle-v1/README.md)

## What was observable before the next group

We compared 583,593 adjacent, usable October 18 group pairs. The first
completed group supplies the observable state. The next completed group
supplies the print and midpoint outcomes. Pairs crossing the active
session boundary, a reset, a snapshot, or an invalid quote or clock are
excluded. The falling-touch flag uses the already logged candidate at the
first close. The next-group target has variable elapsed time.

| Did the decision group contain a print? | Falling-touch candidate at that close | Next group had a print |
| --- | --- | ---: |
| No | No | 22,312 / 498,417 (4.48%) |
| No | Yes | 2,408 / 55,379 (4.35%) |
| Yes | No | 3,505 / 21,902 (16.00%) |
| Yes | Yes | 1,572 / 7,895 (19.91%) |

Recent printing is a clear baseline for this day's next-group trade
arrival. The apparent falling-touch increment differs by activity
state. Among 63,274 falling-touch groups with a same-hour,
same-print-status, same-spread comparison, 3,980 had a next-group print
(6.29%). Applying the rates from the comparable groups without falling
touch gives a descriptive reference of 4,576.95 (7.23%). This weighted
reference is a comparison of rates within the same date and leaves other
confounders open.

The first future print in each of 29,797 eligible target groups had a
median lead of **0.366 ms** from the previous completed close. Sixty-three
had a zero receive-time lead with tape order still separating the events.
An event can be ordered first while offering very little decision time.

| Observable direction at the first close | Next midpoint agrees | Opposes | Flat | No unique call |
| --- | ---: | ---: | ---: | ---: |
| Side of the falling-touch call | 2,173 | 1,557 | 58,739 | 521,124 |
| Sign of displayed bid size minus ask size | 25,384 | 7,710 | 502,947 | 47,552 |

Displayed queue imbalance is worth testing as a baseline. Among its
directional calls where the next midpoint moved, 76.7% agreed. Over
93% of its directional calls were flat on the next group. The two rows
above have different coverage. They do not rank the rules on common
support or establish a tradeable outcome. A later test should retain
flat states, compare the same eligible observations at fixed elapsed
horizons and assess the probability estimates prospectively.
[October 18 signal definitions](october-discovery-log.md#october-18-full-session-touch-and-print-decisions)
· [Numerical output](october18-prebirth-research.json)

## Where the retained dipoles fall in the trade lifecycle

The saved inventory has 862 dipole paths, all with a terminal reversal
label. The inventory links 14,699 of 30,739 original prints to at least
one path by temporal overlap. There are 17,845 path–print links because
some prints overlap more than one path.

| Timing check on the linked records | Links |
| --- | ---: |
| Birth label precedes print receive time | 17,845 |
| Recorded candidate-availability clock precedes print receive time | 6,639 |
| Complete path was available before the print by clock and source cursor | 0 |
| Complete path was available by the previous eligible group close | 0 |

The 6,639 links span 5,426 distinct prints. They identify a scope for
reconstructing candidate-stage inputs from original data. They do not
establish that the full path or its reversal was known at entry. The
overlap definition itself selects prints within a path's lifetime.
An earlier completed path could be context for a later trade, but that
requires a separate as-of join across the full decision population.
[Retained path table](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/supporting-dipole-paths.csv.gz)
· [Original overlap links](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/trade-to-supporting-path-links.csv.gz)

The project's phase reconstruction uses a reversal after the third
consecutive opposed completed second. This rule describes a recognized
phase when the required evidence arrives. A separately retained lifecycle
case, trade 143, had its first stored opposition more than 13 seconds
after the bid retreat, with no fresh prints in the three opposed
rolling-flow seconds. That path illustrates how a terminal phase can
describe later context while leaving the early mechanism to the tape
and book. Preserve fresh flow and rolling flow independently.
[Dipole phase audit](../../artifacts/sqlite-triage/20261022/families/dipole-event-phase-audit-v1/event_phase_receipt.json)
· [Trade 143 lifecycle and timing](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/historical-paper-replay-v1/README.md)

## Exhaustion as a lifecycle question

Keep these mechanisms separate. Aggressive execution can slow while
resting liquidity stays thin. An opposing side can begin executing
while earlier pressure continues. The touch can replenish faster than
it is consumed, or price displacement per linked execution can decline.
Each can change the lifecycle. A valid test needs both the observed
change and its timing relative to the first response.

For a first descriptive check, take the last three completed print-group
closes strictly before each of the 1,012 saved size-one onsets. Compare
the most recent completed interarrival gap with the one before it.
Run the comparison for all prints and separately for known-side prints
pressing the episode's touch at the same absolute price. For the bid,
these are seller-aggressed prints. For the ask, they are buyer-aggressed
prints. Unknown-side prints remain in the all-print view. The onset
group's own prints and later groups are excluded from the feature. The
outcome is the first observed end. The JSON also keeps whether the
elapsed wait since the last print already exceeded its preceding gap.

| Strict-prior tape | Side | Retreats when gaps widened | Retreats when gaps narrowed |
| --- | --- | ---: | ---: |
| All print groups | Ask | 106 / 259 (40.9%) | 133 / 242 (55.0%) |
| All print groups | Bid | 124 / 271 (45.8%) | 98 / 240 (40.8%) |
| Known side pressing the touch, at its price | Ask | 120 / 257 (46.7%) | 115 / 236 (48.7%) |
| Known side pressing the touch, at its price | Bid | 110 / 253 (43.5%) | 111 / 255 (43.5%) |

Eleven episodes lack the required same-price, known-side history. Keep
them explicit. The all-print pattern changes direction by side. The
same-price attacking-side comparison provides little separation here.
The earlier order-level audit found that most recoveries were new orders
joining and that retreat often followed a fill-linked final removal.
A useful follow-on is to measure whether fresh attacking quantity,
same-order refresh, incoming depth and quote response diverge before
the onset or before an observable transition. This first check
measures arrival cadence. It does not identify a parent's execution
program or latent demand. [Order-level mechanism audit](why-october18-touch-behaved-differently.md)

## What the quantitative research is trying to estimate

| Method | Question it answers here | Starting comparison for NG |
| --- | --- | --- |
| Event study and trade–quote dynamics | How does the quote respond to a trade or unexpected flow, over which horizons, and how much persists? | Align signed midpoint and depth paths around actual prints, keep pre-event trajectories, and compare against similarly active decision groups without the event. Hasbrouck's equity model separates innovations in trades from expected activity and measures subsequent quote response. |
| Event-arrival or point-process model | Given only prior events, how does the likelihood of another print or quote move change with elapsed time and event history? | Start with empirical arrival rates from time, spread and recent prints. Then add depth, fixed-price order changes and candidate-stage states one at a time. Bacry and Muzy model self-excitation of arrivals and feedback between trades and prices. |
| Competing outcomes over time | Given a still-open quote episode, which of recovery, retreat or improvement arrives first, and how much time remains? | Compare probability of each first outcome by fixed elapsed horizons, with still-open and censored cases explicit. Start with empirical time-to-event curves by side and observable conditions. |
| Order-book forecasting | Does the book trajectory improve a forecast over a simpler baseline on later data? | Compare base rates, signed queue imbalance, and recent print activity on the same eligible groups. Add replenishment or dipole state only with known-by clocks. Sirignano and Cont's equity study tests out-of-sample prediction from order-book history. Ntakaris et al. supply a day-ordered benchmark protocol. |
| Market impact and exhaustion | Is the move holding, fading or reversing as observed pressure and liquidity change? | Compare fresh signed quantity, recovery of displayed depth, and price response in order. Bacry et al. studied impact decay with identified European metaorders. The NG tape supplies observable orders and prints, with private parent order intent unresolved. |

[Hasbrouck](https://doi.org/10.1111/j.1540-6261.1991.tb03749.x)
· [Bacry and Muzy](https://arxiv.org/abs/1301.1135)
· [Sirignano and Cont](https://arxiv.org/abs/1803.06917)
· [Ntakaris et al.](https://arxiv.org/abs/1705.03233)
· [Bacry et al. on order lifecycles and impact](https://arxiv.org/abs/1412.0217)

For later prediction work, freeze the target and minimum feasible
decision lead. Use all four dates to examine recurrence, missing coverage
and counterexamples, then assess frozen candidates on genuinely later
data. Track calibration and compare probability forecasts with a
proper score such as Brier loss. Keep timestamp buckets as context,
control dependence from overlapping groups, and preserve every tested
variant. Treat the next-group results above as diagnostics for choosing
what to study. [Gneiting and Raftery](https://doi.org/10.1198/016214506000001437)
· [Project chart and signal research guide](reading-trade-charts-and-signals.md)

## Next research entries

1. Reconstruct the strict-prior tape, full depth and order lifecycles
   behind the candidate-availability links. Preserve the first observable
   onset, persistence and opposition states. Compare against no-candidate
   groups and separate fresh prints from rolling summaries.
2. Compare competing quote endings at fixed elapsed horizons, with the
   surviving order, same-price replenishment and nearby depth identified
   by the decision. Separate flow slowing, opposing flow and declining
   price response per executed quantity.
3. Check which observations recur across the four dates with the same
   definitions. Attach the relevant planes and 13 external data points
   using verified clocks and distinguish shared source inputs from
   independent evidence. Keep the earlier admission and simulator gates.

[Reproducible analysis](research_october18_trade_prebirth.py)
· [Machine-readable counts](october18-prebirth-research.json)
