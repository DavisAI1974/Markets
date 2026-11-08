# October NG discovery and paper-test log

October 2, 3, 17, and 18, 2023 are four equal discovery dates for NGX3
(instrument 150611). October 2 and 17 use the available spans starting at
the UTC midnight snapshots. October 3 and 18 have full-session tape coverage.
Each date gets its own observed signals, including opposing calls, flats,
misses and unavailable inputs. Keep original group and cursor coordinates.

## October 18 observations

The full-session standalone input export covers 583,688 completed groups and
30,739 prints. The candidate counts below come from the previously studied
22,194 consecutive book closes, groups 229201–251394. These counts describe
the window that produced the hypotheses. Full-session decision evaluation and
the separate coverage and formula admission are pending.

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
