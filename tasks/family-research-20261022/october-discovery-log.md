# October NG discovery and paper-test log

October 2, 3, 17, and 18, 2023 are four equal discovery dates for NGX3
(instrument 150611). October 2 and 17 use the available spans starting at
the UTC midnight snapshots. October 3 and 18 have full-session tape coverage.
Each date gets its own observed signals, including opposing calls, flats,
misses and unavailable inputs. Keep original group and cursor coordinates.

Use the [trade chart and signal research guide](reading-trade-charts-and-signals.md) to interpret event sequences, measure the moves that follow, and define replay and paper-test comparisons.

## What to watch across all four dates

Describe the ordered behavior at the touch and link the observations that
show it. Record the prior state, the sequence of changes, what was visible
at the decision close, and what happened afterward. Keep exact prices,
sizes, and ratios with their source coordinates. Use them to reconstruct
the sequence. Any numerical condition in a candidate belongs to that
versioned rule and needs its own evidence before reuse across setups.

- For a thinning touch, track whether the price held as displayed size fell,
  then record recovery at that price, replenishment, or retreat separately.
- For prints, record where they occurred relative to the immediately prior
  quote and how the book changed around them. Attribute depletion to a fill
  or cancel only where the original actions support that link.
- For absorption and entropy, keep the underlying updates and their order.
  Trace fill and display changes by order and price for absorption. For
  entropy, inspect the touch-size observations in both blocks that produced
  the change. Keep similar sequences with different outcomes side by side.

Keep three parts of each observation linked:

- **Behavior.** Record the ordered book updates and prints. Ratios can
  characterize that behavior, such as order-linked fills relative to
  displayed reductions. Keep the numerator, denominator, and observation
  span so the ratio remains interpretable.
- **Measured move.** Keep exact prices and timestamps at the relevant
  starting, decision, and later observations. Report signed percentage
  change from a defined nonzero starting price, with raw changes and ticks
  where available. Retain elapsed time and the quote side or midpoint used
  for the measurement. Compare the distribution of moves at consistent
  horizons across recurring market events and conditions, including flat
  and opposing moves. Use the event and its context to define the pattern.
- **Option contract context.** When evaluating a particular option, map the
  move to that contract's specified underlying reference, strike, call or
  put, expiry, and settlement terms. Keep the underlying's distance to
  strike and time to expiry at the observation. Record the option premium
  separately when it is observed. The same underlying move can have
  different implications for two contracts.

Use timestamps to locate events, establish their order and availability,
and measure elapsed time. Time of day, session phase, and trading weekday
can group comparable observations and show when behavior tends to recur.
Treat recurrence within a time bucket as an association. If the pattern
clusters around a session transition or scheduled release, record the
observable event and compare it with similar cases. Keep the time label
as context for that comparison.

Treat a specific price level as a separate strike-concentration hypothesis
when contemporaneously available options data show a concentration there.
Bind the observation to the matching underlying and expiry, record how the
concentration was measured, and compare behavior near that strike with
comparable levels without that concentration. Keep open interest and traded
volume separate if both are available.

## October 18 observations

The full-session standalone input export covers 583,688 completed groups and
30,739 prints. The candidate counts below come from the previously studied
22,194 consecutive book closes, groups 229201–251394. These counts describe
the window that produced the hypotheses. The full-session touch and print decision pass is below. The remaining
variants and separate scoring admission are pending.

| Candidate family | Ask / long | Bid / short |
| --- | ---: | ---: |
| Falling touch | 1,412 | 1,438 |
| Touch-size entropy decline | 132 | 125 |
| Directional prior-touch print | 615 | 544 |
| Falling touch with entropy decline | 520 | 453 |
| Falling touch with same-group print | 171 | 155 |
| Falling touch with both | 59 | 50 |

Use the frozen candidate definitions and the original per-call ledgers for
rule versions, clocks, dispositions and matched outcomes.
[Candidate register](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/plan.md#candidate-register)
· [Standalone pilot and per-call ledger](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/october18_book_entropy_pilot/october18_solo.md)
· [Stack pilot and per-call ledger](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/october18_book_entropy_pilot/october18_stack.md)

| Observation ID | What was visible | Research disposition |
| --- | --- | --- |
| NGX3-20231018-G241500 | Bid/short agreement across falling touch, entropy decline, and prior-touch print. Cursor 314654, book line 12300, original print 11556. | One shared observation. Retain the three rule decisions and all stack-arm decisions. |
| NGX3-20231018-G229205 | Directional disagreement at cursor 297873. | Retain the independent side calls and the group context. |
| NGX3-20231018-G229253 | Ambiguous prior-touch print at cursor 297953, including original print 10862. | Retain the prints and an ambiguous disposition. |
| NGX3-20231018-G230690 | The standing bid at 3.154 shrank from two units to one. The displayed bid recovered at that price after the eligible entry. | Counterexample to treating size-one onset as a guaranteed retreat. Original trade 10924. |
| NGX3-20231018-G232857 | The standing bid at 3.154 shrank from four units to one. It retreated to 3.153 after the eligible entry. | Compare with G230690. Both onset groups closed at 3.154/3.155. Original trade 11048. |

The full stack's ask calls had 27 agreements, 11 oppositions and 21 flats at
one second, then 24 agreements and 25 oppositions at five seconds. In the
separate historical spread-crossing diagnostic, 846 of 1,012 size-one onset
scenarios were negative at one second before fees. Keep the research status
of these candidates at `NOT_ENOUGH_INFO`.
[Historical diagnostics and source cases](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/historical-paper-replay-v1/README.md)

## October 18 full-session touch and print decisions

The decision pass read all 583,688 group rows and 30,739 prints from the
existing export. It evaluated 583,595 eligible group closes. It excluded
92 halt groups from signal state and reset state at the one snapshot/reset
boundary. The three-close falling-touch definition uses the three actual
observations. The print rule uses the immediately preceding eligible quote.
The stack uses any print in the same group and takes direction from the
falling-touch rule.

| Versioned candidate | Ask / long | Bid / short |
| --- | ---: | ---: |
| `falling-touch.v1` | 31,399 | 32,680 |
| `prior-touch-print.v1` | 14,001 | 13,828 |
| `falling-touch+print.v1` | 4,175 | 3,947 |

The ledger has 101,998 rows, including 1,968 ambiguous prior-touch print
decisions. Across all three rules, 83,286 distinct groups had at least one
candidate. Both directions fired in 1,189 of those groups. At G229205,
the falling-touch rule fired on both sides and the prior-touch print called
ask/long. Keep both observations. These are rule calls and ambiguity
dispositions. Returns, entropy-dependent variants, and simulator fills are
separate work.

The saved-window comparison reproduced 2,850 falling-touch calls and all
1,240 print decisions, with exact group, cursor, known-by time and direction.
The print comparison also matched original print ordinals and ambiguity.
Those counts come from the comparison input. The full run reads to the end
of its available session.

[Full-session decision ledger](october18-touch-print-decisions.jsonl.gz)
· [Decision runner](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/discovery_touch_print.py)
· [Standalone inputs](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-bounded-replay/retained/october18-standalone-inputs/groups.jsonl.gz)

## Paper-test queue

The logged signals are historical discovery candidates. The Git evidence
shows no platform entry or approved simulator ticket for these candidates.
`direction.book_contrarian` is a separate provisional hypothesis. It uses
resting-book imbalance when flow is flat or ambiguous. The needed inputs were
unavailable for its original trigger in this replay, so it remains unscored.
[Original hypothesis and contrary audit](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/local-liquidity-v1/README.md)

After the four dates run through the standalone component, record a candidate
as a paper rule when its version, exact trigger, side, order type, size,
exit and simulator environment are agreed. Log any later platform entry
and simulator observation separately from the historical discovery row.
