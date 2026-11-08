# Why the October 18 size-one quotes recovered or retreated

This audit precedes strategy design. It uses the original NGX3 market-by-order
tape and all 1,012 size-one onset episodes in the previously saved 22,194-close
October 18, 2023 window. Each episode has a distinct onset group. This is
one historical window. October 2, 3, 17 and 18 remain equal discovery dates
and October 2 and 17 remain partial.

## What changed the quote

An independent order map replays the October 18 UTC tape from its opening
snapshot. It reconciles both best prices, displayed quantities and order
counts with the standalone export immediately before and at 5,172 distinct
targeted closes. The episode ledger preserves the onset and end actions,
same-price changes and prints between them, the surviving order's observed
refresh history since the UTC snapshot, the next displayed level, and the
outcome's timing relative to the earlier replay's assumed entry.

The audit uses original message order. It links a displayed reduction to
a preceding fill in the same completed group when the resting order and
fixed price agree, up to the displayed quantity actually removed. An
unlinked C means this audit found no matching fill. The feed leaves its
reason unresolved at that coordinate. An unchanged displayed quantity
after a same-order fill and modify is evidence of observed refresh.
Remaining reserve and trader intent are unavailable.
[Original episode definitions and ledger](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/historical-paper-replay-v1/README.md)
· [Tape member](https://github.com/DavisAI1974/Markets/blob/1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202/data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_20231018.dbn.zst)

| First end | Observed mechanism | Episodes |
| --- | --- | ---: |
| Recovered at the same price | New order joined the touch | 534 |
| Recovered at the same price | Existing order repriced into the touch | 13 |
| Recovered at the same price | Existing order increased its displayed size | 1 |
| Retreated | Last displayed quantity removed with a matching fill | 272 |
| Retreated | Last displayed quantity removed by a C with no matched fill | 187 |
| Retreated | Remaining order repriced away | 2 |
| Improved | A new order joined at a better price | 3 |

Of 461 retreats, 460 landed at the immediately preceding second level.
In ten cases a fill-linked reduction also reached the new best level in
the ending group. The next level's median displayed size at onset was
ten contracts for both recoveries and retreats. Median distance to it was
one price increment in both groups. Those medians leave individual depth
paths and tail differences open. Of the 1,012 first ends, 659 were
already visible by the earlier replay's assumed entry. That includes 298
retreats, 359 recoveries and two improvements.

The two original examples show the difference between an order holding
its displayed size and displayed depth increasing. In G230690 a surviving
bid took another fill and kept one lot displayed. A distinct order then
joined and produced the measured recovery. In G232857 the final fill
removed the last lot, exposing the next bid. Both surviving orders had
previously refreshed. [Exact paired tape paths](october-discovery-log.md#why-the-two-one-contract-bids-diverged)

## What was visible by onset

For episodes where an existing best quote shrank to one contract, the
source-linked onset reduction gives these descriptive counts.

| Side | Onset reduction at the standing best | Retreats among all onsets | Retreats among episodes still open at assumed entry |
| --- | --- | ---: | ---: |
| Ask | At least one fill-linked reduction | 54 / 68 | 8 / 15 |
| Ask | No fill-linked reduction found | 80 / 123 | 26 / 50 |
| Bid | At least one fill-linked reduction | 50 / 65 | 8 / 14 |
| Bid | No fill-linked reduction found | 82 / 153 | 29 / 65 |

Fill-linked thinning was followed by more retreats in the all-onset
counts on both sides. The after-entry comparison is much smaller. In
particular, on the ask the two fractions are close. The entry comparison
conditions on an episode remaining open at an observable quote after a
hypothetical delay. It is a timing diagnostic.

The surviving order showed an unchanged-display fill in the onset group
in six cases, with four retreats and two recoveries. Three more surviving
orders had the same observed pattern earlier since the UTC snapshot, and
all three retreated. The other 1,003 lacked that recorded history under
this definition. This is a small recorded subset. Keep missing prehistory
and the difference between surviving-order refresh and incoming orders
when comparing dates.

[Per-episode mechanism ledger](october18-size-one-mechanisms.jsonl.gz)
· [Reproducible audit](audit_october18_touch_mechanisms.py)

## Which of the 99 planes answer which question

The registry inventories source roles. Plane ordinals below are the
zero-based entries in the original 99-row register. Use the direct
carriers first. The present admission audit separates 58 canonical
context roles and 41 held roles, with zero admitted to the full
discovery input set. This bounded audit uses original tape evidence.
[Original plane registry](../../artifacts/sqlite-triage/20261022/families/descriptive-v1/plane_registry.csv)
· [Current admission audit](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-input-admission.md)

| Plane ordinals | Relationship to the behavior |
| --- | --- |
| 24, 26, 29–36, 46 | The date-specific raw source, book actions, trades, fills, order identity and actions by side and level trace what joined, left, repriced, refreshed or was executed. |
| 38–40, 43–44, 48–51 | Depth, order counts, FIFO, volume ahead, spread, depletion, recovery and price path explain the visible state changes. Keep fixed-price quantities separate from a change in relative rank. |
| 41–42, 47, 54–58, 62–67 | Queue age, concentration, flow, imbalance, dipole and path summaries can characterize the sequence. Record their operands, scopes and clocks. The historical registry marks 54–55 as completed-only because contributor availability was unresolved. Multiple summaries of the same orders or prints share evidence. |
| 25, 27–28, 37, 45, 52, 61, 65, 71–77 | Bootstrap, resets, continuity, identity, integrity, lineage and clocks define whether a case is observable and comparable. A snapshot priority clock records observation and leaves earlier order age censored. |
| 66–70, 78–79, 82–88 | Separate any proven as-of detector state from later episode labels, outcomes and sealed answers. The first end in this audit belongs with outcomes. |

Join the book and actions by trade date, instrument, continuity segment,
group ordinal and close cursor. Retain exact event, receive and known-by
clocks. Same-time ties follow source ordering. The decision includes only
completed onset members and derived inputs whose last contributor and
emission are available by that close. Use the ROOT `input_records` and
`input_record_indices` for action lineage, and
`book.{bid,ask}_levels_full[].fifo_queue[]` and `observation.orders[]`
for depth and queue state. For example, another October 18 transition
showed first-ten depth growing by 21 contracts entirely because its rank
membership changed, with no net change at prices shared across the two
views. [ROOT field inventory](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-ledger-headings.md)
· [Fixed-price versus rank example](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/local-liquidity-v1/README.md)

## Which of the 13 data points might explain context

The external crosswalk labels all 19 table mappings `closest`. For
example, weekly CFTC positioning and native signed flow share plane 47
by analogy. Physical storage and power measures share plane 48 with
order-book depletion and replenishment. Keep the external and MBO
observations, units and sources separate.
[Actual October 18 input bindings](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/all-13-input-bindings.json)
· [External provenance crosswalk](../../artifacts/sqlite-triage/20261022/families/descriptive-v1/external_point_provenance.csv)

| Data points | Relationship and what to require |
| --- | --- |
| 1, 3, 4, 8 | CFTC positioning is regime context. Points 1, 3 and 4 derive from the same NYMEX history. Point 8 is ICE LD1. Use the actual publication clock separately from the report date. |
| 2, 9 | Forecast HDD and GFS/NAM disagreement describe expected demand and uncertainty. A verified first observable forecast revision can be tested as an event. Keep model run, target, vintage and comparable station coverage. The retained runtime-plus-4.5-hour stamp is modeled. |
| 5, 7 | Wind and estimated power-sector gas burn share EIA930 inputs. They can describe demand context. The retained period-plus-two-hour stamp is nominal and current revisions leave the first vintage unresolved. |
| 6 | Sessions since prompt expiry can group contract and roll conditions. The synthetic 14:00 ET stamp is a calendar placement. |
| 10 | Observed HDD and station temperature describe realized weather context. Gas-day and observation clocks are distinct from nominal availability. |
| 11, 12 | Carry-in gas stocks are context. An actual storage release can be an event. A surprise requires a comparable estimate demonstrably available before the actual release. |
| 13 | Traded and settled curve shape can describe market context by exact delivery month. Retain per-leg source and age, separate trade and settlement clocks, and link any front-leg input shared with the NG tape. |

Across all 1,012 episodes, zero retained non-curve declared publication
clocks fell after onset and through first end. Traded-curve updates did
fall in 77 intervals, covering 59 retreats, 17 recoveries and one
improvement. That series can reuse the NG front trade and is therefore
not independent confirmation. Neither of the two paired examples
overlapped a declared update. At their onsets, 42 of 48 retained series
pointers were identical, including one unavailable at both. The six
differences came from one traded-curve row per onset, with the front
at 3.154 in both and the next contract at 3.537 versus 3.536. Those rows
carry timestamps shared with NG prints. This comparison covers the
retained declared clocks. Actual delivery, unrecorded events and prior
expectations remain separate questions.
[Original publication rows](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/day-wide-mechanisms-v1/all-declared-external-publications-during-tape.jsonl.gz)
· [Trade-linked original series](../../artifacts/sqlite-triage/20261022/families/trade-lifecycle-targeted-v1/every-trade-original-external-links.jsonl.gz)

Exact attachment inventories have 288,095 rows for October 3, 363,661
for October 17 and 329,647 for October 18. The normalized inventories
lack point 12. A distinct October 18 completed-run attachment had
11 estimate rows and no capture table. October 2 has no exact attachment.
Its separate recovery provides 146,800 candidates with specific CFTC and
as-printed storage history and 37,670 matched NGX3 prints. Weather
availability, power vintages and full curve coverage remain held. The
13 data points leave strike-level option open interest and premiums
unmeasured.
[Coverage and variant audit](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-input-admission.md)
· [October 2 recovery](../../research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/october02-external-recovery/README.md)

## Compare mechanisms before drafting rules

Compare onset pressure, the survival and refresh history of the order
left at the touch, whether depth was joining or withdrawing at nearby
fixed prices, and the time to the first end. Evaluate these as-of onset
for comparable eligible episodes on both sides of each date. Then attach
time, depth and verified external context separately. Keep no-print,
unknown linkage, recovery, retreat and contrary cases. A terminal
fill-linked removal explains that retreat after it occurs. A strategy
would need an earlier observable condition and an entry that can still
act on it.
