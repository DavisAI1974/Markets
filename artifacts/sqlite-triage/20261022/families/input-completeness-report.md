# Input completion before a revised Julia analysis

The revised statistical rerun is paused at the user's request. An initial descriptive pass ran, but its feature selection omitted available prior-group and other context measurements. Subsequent exploratory outputs are preliminary, and the expanded rerun was cancelled before this input inventory. No model, selected predictive target, or backtest has run.

## Completed additions

- All 749 first-observed structural families remain in the master. All 583,688 retained groups remain linked in their original sequence; the verified source database is unchanged.
- 10,486 selected same-instrument completed-group contexts were read at the previously validated ROOT/native offsets. They produced 5,803,712 measurement rows. These include the nearby comparison periods, 120/300/600-second lookbacks, action/side counts, book measurements, per-level measurements, and native observed durations. No recovery-directory enumeration or source-file rescan occurred.
- 71,155 separately named completed-group second-set measurements were added for the five snapshots per family, with 128,079 additional lookback measurements. The latest input-event dispositions remain separate. A NOT_F_LAST event does not erase an earlier measured group observation.
- All 13 conceptual historical points remain linked through 62 source series in the initial external alignment. Model, horizon, target-day, station, instrument and curve-pair distinctions are preserved. Full row JSON and publication provenance remain available.
- All 99 plane identities and dispositions remain saved. Identity, control and not-read roles are retained as such; they are not manufactured numerical predictors.
- All 30,739 timestamped trades remain available, including exact clocks, instrument, price_raw, size and provenance.

## Temperature

The latest station report often contains `M` for temperature even though an earlier report from that same station has an actual temperature. The new `external_last_observed_measurements` table separately retains the latest *numerical observation already published* for each station and measurement, including its original publication time, event time, source ordinal and both ages. The latest-report M value remains unchanged.

All **18 stations have an eligible temperature observation at every one of the 749 strictly pre-start cutoffs**: 13,482 available station/family pairs and zero missing pairs. The same extraction includes 21 weather measurements per station and 1,415,610 rows over the five snapshots. This is historical observed weather with explicit age, not interpolation or a claim of contemporaneous temperature at every market event.

## Family and pullback context

`family_context_linkage` has 10,486 rows covering all 749 target families. It distinguishes the target family from the actually observed family at the selected source group. Original group clocks/cursors, source offsets, instrument, external context keys and all 99 registry dispositions remain linked.

The original completed-step pullback requires a completed extension following an armed pullback. The source geometry arms at one tick, breaks the chain at three ticks, resets on direction/scope changes, and freezes on undefined direction. It requires one completed step for the last pullback and two for the previous pullback/step ratio. These source definitions were not changed.

The stored causal D-state also contains **ongoing pullback depth**, which the first pass did not extract. This is now a separate field with exact rational numerator/denominator, source offset, known-by time, age, and frozen/broken/armed dispositions. It does not replace or relabel a completed-step field. Where raw completed-step fields are present, 728 extracted contextual values agreed with the source's log1p conversion.

Immediately before the 749 family starts:

| Measurement | Available | Still undefined |
|---|---:|---:|
| Ongoing pullback depth at the last eligible group | 617 | 132 |
| Last completed-step pullback | 48 | 701 |
| Previous completed-step pullback | 6 | 743 |

For last completed pullback, the 701 unavailable observations comprise 559 NO_COMPLETED_STEP, 132 SIDE_UNDEFINED and 10 CHAIN_BROKEN. For previous pullback and step ratio, the 743 comprise 601 NO_COMPLETED_STEP, 132 SIDE_UNDEFINED and 10 CHAIN_BROKEN. The 132 undefined flow directions include 97 NO_FLOW and 35 near-balanced-flow observations in the side-selection fields. These are unavailable measurements, not absent source rows. Ongoing geometry is not used when the source geometry is frozen/undefined.

NO_FLOW means the sum of buy- and sell-side traded sizes is zero in the preceding 64 same-instrument event groups. These are groups, not seconds. Orders and cancellations can still occur. The source needs that flow to select a far-side direction.

## Queue-age coverage

For the cited second-set far-front queue-age field, all 771,787 source rows remain present. Of the 276,054 unavailable numerical cells, 188,099 are NOT_F_LAST input events, 51,976 are NO_FLOW, and 35,979 are SIDE_UNDEFINED. Among the 583,688 completed groups, 495,733 are numerically available (about 85%). The other completed-group observations do not define the flow-selected far side.

The underlying bid and ask information is available independently of that selection. In the expanded native inputs, **each of the following is available at all 749 strictly pre-start cutoffs**, with no explicit null or unmaterialized key: `native.book.bid_levels.rank1.front_order_age_s`, `native.book.ask_levels.rank1.front_order_age_s`, `native.book.bid_levels.rank1.queue_age_p90_s`, and `native.book.ask_levels.rank1.queue_age_p90_s`. Their median observation age is 0.024690523 seconds; individual ages, seeded/observed priority provenance and source limitations remain attached. These are observed priority ages, not proof of original order birth. Both sides are kept separately; neither is relabelled as a far side when direction is undefined.

## Remaining source limitations

- Some native elapsed durations have no valid historical anchor; some measurement dictionaries do not materialize every key. Explicit nulls and unmaterialized keys remain distinguishable. They are not silently filled with zero.
- Some external series have no publication before the requested cutoff. For example, the saved calendar-count series is not yet available for 659 of the 749 pre-start cutoffs under its recorded clock, and three particular model/horizon/target-day forecast series are unavailable for the earliest 99 starts. Other available horizons remain present. No future publication is used to fill those slots.
- The original latest station reports retain their M values. Historical temperature observations are separately available with age. Other weather fields can still have no numerical observation in the saved source.
- At T−120, 26 families have no earlier retained same-instrument trade; strictly before start, 8 have no earlier retained trade. All are retained. Older observed prices keep their ages. Later price windows are censored outside the retained instrument price interval; no flat post-session return is invented.
- Slow historical series may be constant. Missing, stale, constant and contradictory evidence must be reported in the revised analysis.

Full inventories are in the `descriptive-v1/input_*.csv` files and receipts. Original full payloads remain in the pinned database and indexed files; this inventory does not claim every byte or every field of those payloads has been statistically analyzed.

## Next run, after the gap disclosure

The saved source scripts include a strict pre-start price-direction correction: the onset cohort's historical price window ends at T0−1 ns with cursor < start cursor. First-pass direction summaries used an onset-ended historical window and must not be presented as final strictly pre-start findings.

Run the revised `run_descriptive.jl`, followed by `summarize_descriptive.jl`, `compare_context_changes.jl`, and `report_descriptive.jl`, using the already completed input caches and the existing Julia environment. The revised complete analysis has **not** been run. Updated analysis code beyond the input builders remains pending end-to-end validation. Existing math boundary tests passed 9/9; input extraction assertions and source unit checks passed. The prior draft Python test remains a draft with no implementation.

Runtime: `/opt/frankie-box/work/family-research-20261022/julia-runtime/julia-1.13.2/bin/julia`, project `julia-env`, depot `julia-depot`, `--startup-file=no`. Do not download or restore anything again. No subagents, monitors, other chats or messages were used.
