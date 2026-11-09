# Native dipole research findings

## Data first

GitHub is the durable working source: code and findings in DavisAI1974/Markets; data, tables, renders, workbooks and provenance in DavisAI1974/markets-data. The user removed the local-only rule on 2026-11-08. See PUBLICATION.md for verified artifact destinations. No AWS/S3. Markdown measurement tables are self-contained for phone review.

Review workbook: `research-tables.xlsx` (the older GitHub copy predates final results). The workbook contains complete review tables; long per-second and pair-distance observations remain compressed CSV. Every path remains individually observable, with no smoothing, amplitude normalization or across-path average.

Per date, use `tables/<date>-paths.csv.gz`, `-path-members.csv`, `-candidate-operands.csv`, `-cases.csv`, `-case-raw-records.csv.gz`, `-detector-all-comparisons.csv`, `-birth-differences-<variant>.csv`, `-lag-measurements.csv`, `-all-hierarchy-merges.csv`, `-pair-distances-<representation>.csv.gz`, `-grouping-members.csv`, `-operator-residuals.csv`, `-life-measurements.csv`, and `-life-paths.csv.gz`. All named missed/added and undefined rows are retained.

Every figure has a panel-level CSV reconciliation: `-figure-reconciliation.csv`, `-detector-figure-reconciliation.csv`, `-part2-figure-reconciliation.csv`, `-part3-figure-reconciliation.csv`, plus `crossday-figure-reconciliation.csv` and `crossday-moonshot-figure-reconciliation.csv`. Heat-strip reconciliation separates integer-second cells, fractional endpoints in companion plots, and undefined values. The original 852-candidate October 18 subset is used for its primary heat strips and hierarchy; the all-live cross-day plots and mechanism tables explicitly include the 11 seam supplements.

![SAME day-by-day distributions](https://raw.githubusercontent.com/DavisAI1974/markets-data/0487d83b1ddb1abe5e4cfae12e8b88797801f428/tasks/family-research-20261022/native-dipole/20261108-33693e180/agent-pass/figures/crossday-SAME.png)

![FLIP day-by-day distributions](https://raw.githubusercontent.com/DavisAI1974/markets-data/0487d83b1ddb1abe5e4cfae12e8b88797801f428/tasks/family-research-20261022/native-dipole/20261108-33693e180/agent-pass/figures/crossday-FLIP.png)

![All October 18 lag observations](https://raw.githubusercontent.com/DavisAI1974/markets-data/0487d83b1ddb1abe5e4cfae12e8b88797801f428/tasks/family-research-20261022/native-dipole/20261108-33693e180/agent-pass/figures/20231018-lag-distributions.png)

Each date has 36 birth-path figures, split candidate/control1/control2 and SAME/FLIP/NO_PREDECESSOR. Quotes, touch sizes, adds/cancels/fills/modify sizes by wire side, wire aggressor lots, signed ratio and exact recognition endpoints have separate panels. Structure figures show all pair distances, all merges and all retained path coordinates. Operator figures show every residual, never a mean line. Figures allocate at least one native image pixel per heat-strip row; image viewer rescaling is separate from the source PNG.

M1/M2 local tables: `-detector-free-events.csv.gz`, `-detector-free-nearest.csv`, `-detector-free-cases.csv`, `-detector-free-case-records.csv.gz`, `-lag-footprints.csv`, `-first-footprint-events.csv`, and `-cross-side-ordering.csv`. `-all-footprints-<orientation>.png` includes all 14 event/side types; `-moonshots-<orientation>.png` compares structural-event clocks and selected within-lag footprints.

![October 18 SAME moonshot observations](https://raw.githubusercontent.com/DavisAI1974/markets-data/0487d83b1ddb1abe5e4cfae12e8b88797801f428/tasks/family-research-20261022/native-dipole/20261108-33693e180/agent-pass/figures/20231018-moonshots-SAME.png)

## Confirmed measurements

### Population and birth-aligned paths

| day        | scope            | candidates   | live   | finalization_only   | path_rows   | controls   | groups   | native_matches   | completed_group_missed   | completed_group_added   |
|:-----------|:-----------------|:-------------|:-------|:--------------------|:------------|:-----------|:---------|:-----------------|:-------------------------|:------------------------|
| 2023-10-02 | partial_archived | 741          | 741    | 0                   | 254025      | 1482       | 600291   | 741              | 5                        | 5                       |
| 2023-10-03 | full_archived    | 833          | 832    | 1                   | 283542      | 1664       | 653912   | 833              | 5                        | 5                       |
| 2023-10-17 | partial_archived | 741          | 740    | 1                   | 253764      | 1480       | 635170   | 741              | 11                       | 10                      |
| 2023-10-18 | full_archived    | 863          | 863    | 0                   | 288144      | 1726       | 583688   | 863              | 21                       | 24                      |

The populations are the archived Native candidates, not the separate 839/857/830/890 full-session research detections. October 2 and 17 remain partial. October 3 and 17 each retain one finalization-only birth with no live recognition. Exactly 3,176 live candidate paths and 6,352 paired controls generate 1,079,475 path observations. The archived group source allows the 11 original October 18 seam exclusions to be retained as a separately labeled supplement; the original 59+793+11 coverage partition is unchanged.

At each anchor, the path starts at minus 60 seconds and ends at the exact candidate recognition delay. Quote state is the last completed group by the cutoff. At offsets through zero the cutoff is one nanosecond before the boundary; later offsets use the exact boundary. Action lots are summed over successive cutoff intervals and attributed to the containing completed group. The first interval uses an extra second of prehistory. The signed-ratio panel uses fully closed second bins. Fills and their linked cancels remain separate message categories; they must not be added as independent execution volume. Modify columns are message sizes, not inferred net depth changes.

Two deterministic control draws (seed 1401) match the archived session, positive spread bucket (1, 2, 3+ ticks) and trailing-60-second trade-count quintile within spread. Integer-second anchors inside any candidate study interval are excluded from the control pool. Controls retain the case duration and case SAME/FLIP label for paired comparison. Thirteen October 18 control anchors lie in the archived book prefix before the Native flow series starts; their book paths remain valid, while flow and life measurements are explicitly unavailable. A negative-index alias in the first operator calculation was corrected; all 289 superseded transitions, including 26 apparent recurrence discrepancies, remain in a labeled diagnostic table. They can be reused and their wider intervals can overlap; these observations are not independent trials. Matching-audit tables independently recover each anchor's actual regime/activity bucket. These activity bins organize controls; they do not normalize dipole paths or admit/remove research families.

There are 21 traced candidate/control members per date: an earliest candidate in each observed orientation/quote-direction alternative, with both controls. Raw-record totals are 6,161/1,483/5,345/3,122. Traces preserve tape day, source record index, cursor, receive nanoseconds, action, side, price, size and order ID. The case is an example of its cell, not a replacement for the cell distribution.

### Detector recovery and clocks

| day        | variant         | recorded   | recovered   | matched   | missed   | added   | nominal_exact   |
|:-----------|:----------------|:-----------|:------------|:----------|:---------|:--------|:----------------|
| 2023-10-02 | completed_group | 741        | 741         | 736       | 5        | 5       | 735             |
| 2023-10-02 | native_action   | 741        | 741         | 741       | 0        | 0       | 741             |
| 2023-10-03 | completed_group | 833        | 833         | 828       | 5        | 5       | 827             |
| 2023-10-03 | native_action   | 833        | 833         | 833       | 0        | 0       | 833             |
| 2023-10-17 | completed_group | 741        | 740         | 730       | 11       | 10      | 728             |
| 2023-10-17 | native_action   | 741        | 741         | 741       | 0        | 0       | 741             |
| 2023-10-18 | completed_group | 863        | 866         | 842       | 21       | 24      | 840             |
| 2023-10-18 | native_action   | 863        | 863         | 863       | 0        | 0       | 863             |

The recovered rule is a trailing finite-observation 85th percentile after the source's 900-second and 600-observation warmup, a plus/minus-five-second local maximum of absolute flow, and prominence against the original baseline median at birth minus 30 through minus 10. Qualifying peaks compete in a 45-second window. Highest prominence wins, magnitude breaks ties, and earliest observation resolves a complete tie. Nominal availability is window-open plus 50 seconds; the selected winner enforces a 45-second refractory. These are recovered detector parameters, not new research acceptance thresholds. The original baseline is reproduced only to audit the detector; it does not smooth the research paths.

Native action-time quote classification reproduces every archived birth and nominal availability on all four dates, including finalization-only nominal times. All six recorded operand columns agree at 1e-12 absolute floating tolerance; all live recognition clocks agree as exact integers. The supplied completed-group series uses another quote-classification reference and therefore has the explicitly listed missed/added births. Its mismatch is not evidence that the recorded Native detector is unrecoverable.

For every one of the 3,178 births, nominal lag = 50 - (winning birth second - window-open second). Thus it is a fixed selection-window close with a variable winner position. Actual live recognition is the first group close in a second later than nominal availability. On October 18, nominal lag ranges 6 to 50 seconds (median 50), dispatch wait 1.000046 to 87.367894 seconds (median 2.406826), and birth-to-recognition 7.059875 to 137.367894 seconds (median 51.673379). All individual observations and the other days' distributions precede this description.

### Structure without a preset cluster count

| day        | representation   | candidates   | complete   | undefined_rows   | groups_at_largest_gap   |
|:-----------|:-----------------|:-------------|:-----------|:-----------------|:------------------------|
| 2023-10-02 | signed_ratio     | 741          | 177        | 564              | 177                     |
| 2023-10-02 | touch_lots       | 741          | 741        | 0                | 2                       |
| 2023-10-02 | quote_levels     | 741          | 741        | 0                | 2                       |
| 2023-10-02 | wire_trade_lots  | 741          | 741        | 0                | 2                       |
| 2023-10-03 | signed_ratio     | 832          | 209        | 623              | 2                       |
| 2023-10-03 | touch_lots       | 832          | 832        | 0                | 2                       |
| 2023-10-03 | quote_levels     | 832          | 832        | 0                | 2                       |
| 2023-10-03 | wire_trade_lots  | 832          | 832        | 0                | 3                       |
| 2023-10-17 | signed_ratio     | 740          | 159        | 581              | 159                     |
| 2023-10-17 | touch_lots       | 740          | 740        | 0                | 2                       |
| 2023-10-17 | quote_levels     | 740          | 740        | 0                | 3                       |
| 2023-10-17 | wire_trade_lots  | 740          | 740        | 0                | 5                       |
| 2023-10-18 | signed_ratio     | 852          | 185        | 667              | 185                     |
| 2023-10-18 | touch_lots       | 852          | 852        | 0                | 4                       |
| 2023-10-18 | quote_levels     | 852          | 852        | 0                | 2                       |
| 2023-10-18 | wire_trade_lots  | 852          | 852        | 0                | 4                       |

The representation preserves every integer-time coordinate from minus 60 through plus 5 seconds. Signed ratio, touch lots, quote levels and wire-trade lots are analyzed separately because their units differ. Cityblock distance is a sum of coordinate differences, with no standardization, phase warping or averaging of paths. Every pair distance and every single-linkage merge is retained. The displayed partition uses the largest gap between adjacent merge heights (including zero before the first merge); all other cuts remain in the merge table. Undefined ratio paths are retained as explicit availability patterns and are not imputed.

The 177/185/159 singleton partitions in three signed-ratio runs occur when the largest gap precedes the first merge. They are not 177/185/159 established natural types. Touch-size partitions put 740/831/739/849 members in the largest group on October 2/3/17/18 respectively, with the remaining 1/1/1/3 in singleton groups. That large group contains both SAME and FLIP. Different representations and cuts produce different partitions; this pass establishes no unique number of natural groupings.

### Governing-form attempts and retained counterexamples

All forms were recorded before their execution. Exact recurrence is distinguished from explanatory hypotheses. The complete candidate and both control residuals are in the operator tables. The table below reports counterexample counts / defined candidate rows, keeping SAME and FLIP separate. Flat quote outcomes count as a distinct observed sign; undefined inputs do not become zero residuals.

| day        | orientation   | fixed_50s_nominal_lag   | flow_sign_determines_quote   | depth_sign_determines_quote   | monotone_magnitude_decay   | constant_signed_numerator   |
|:-----------|:--------------|:------------------------|:-----------------------------|:------------------------------|:---------------------------|:----------------------------|
| 2023-10-02 | FLIP          | 103/353                 | 201/353                      | 223/353                       | 200/353                    | 353/353                     |
| 2023-10-02 | SAME          | 112/387                 | 215/387                      | 235/387                       | 219/387                    | 387/387                     |
| 2023-10-03 | FLIP          | 122/383                 | 213/383                      | 225/383                       | 208/383                    | 383/383                     |
| 2023-10-03 | SAME          | 126/448                 | 288/448                      | 295/448                       | 229/448                    | 448/448                     |
| 2023-10-17 | FLIP          | 94/353                  | 193/353                      | 230/353                       | 189/353                    | 353/353                     |
| 2023-10-17 | SAME          | 100/386                 | 219/386                      | 255/386                       | 214/386                    | 386/386                     |
| 2023-10-18 | FLIP          | 131/390                 | 223/390                      | 209/390                       | 217/390                    | 390/390                     |
| 2023-10-18 | SAME          | 132/472                 | 257/472                      | 265/472                       | 246/472                    | 472/472                     |

The signed-net rolling relation N(s)=N(s-1)+buy(s)-sell(s)-buy(s-20)+sell(s-20) has zero residual on every retained life transition, including both matched-control draws. This is an arithmetic identity of the 20-second construction, not an independently discovered market law. Fresh and expired buy/sell operands are retained separately.

The fixed-50-second lag assertion has the listed exceptions and is replaced, for description, by the exact window-position identity above. Flow-sign and depth-sign determine-one-quote-direction assertions have contrary and flat cases on every date, as do the controls. Monotone magnitude decay has individual rebounds; no single monotone life curve represents those paths. Constant numerator has counterexamples throughout; because the operational ending changes sign, this test is partly conditioned to contradict a constant numerator. No form or input is removed from future study.

### Verification

| day        | candidates   | exact_live_recognition_clocks   | finalization_only   | path_rows   | matched_path_anchors_checked   | figure_panels   | life_transition_rows   |
|:-----------|:-------------|:--------------------------------|:--------------------|:------------|:-------------------------------|:----------------|:-----------------------|
| 2023-10-02 | 741          | 741                             | 0                   | 254025      | 2223                           | 504             | 90556                  |
| 2023-10-03 | 833          | 832                             | 1                   | 283542      | 2496                           | 504             | 103968                 |
| 2023-10-17 | 741          | 740                             | 1                   | 253764      | 2220                           | 504             | 86559                  |
| 2023-10-18 | 863          | 863                             | 0                   | 288144      | 2589                           | 504             | 107181                 |

The original detector was independently checked on plateau, quiet and variable synthetic streams: 27/24/35 outputs agree in every operand and clock. All 2,473,061 saved groups reconcile to raw cursor/receive/F_LAST coordinates. Usable two-sided action-time books agree at 2,473,057 closes; four initial incomplete books remain outside that two-sided check. Figure reconciliation, unique coordinates, matching strata, undefined residuals, and life-transition partitions are asserted in `verify_all.py`. A read-only parent review independently confirmed operands, live clocks, nominal-lag identity, path row totals and case counts.

## SPECULATIVE moonshots: measured results under declared definitions

M1 definitions are discrete quote-price relocation, touch-size change, and a new wire-aggressor-side run. All are derived from raw messages/completed groups without consulting detector birth labels. They are three structural definitions, not an exhaustive or uniquely natural event taxonomy. Unknown-side trades break run continuity. Event time is the containing completed group; raw trade receive time is also retained.

| day        | definition               | events   | unique_event_seconds   | births   | birth_seconds_with_event   | birth_seconds_without_event   | events_in_birth_seconds   | events_outside_birth_seconds   |
|:-----------|:-------------------------|:---------|:-----------------------|:---------|:---------------------------|:------------------------------|:--------------------------|:-------------------------------|
| 2023-10-02 | quote_relocation         | 33021    | 8622                   | 741      | 214                        | 527                           | 532                       | 32489                          |
| 2023-10-02 | touch_size_change        | 266441   | 22595                  | 741      | 376                        | 365                           | 2471                      | 263970                         |
| 2023-10-02 | wire_aggressor_run_start | 12360    | 6629                   | 741      | 140                        | 601                           | 143                       | 12217                          |
| 2023-10-03 | quote_relocation         | 36098    | 9298                   | 833      | 185                        | 648                           | 441                       | 35657                          |
| 2023-10-03 | touch_size_change        | 279342   | 24774                  | 833      | 430                        | 403                           | 2558                      | 276784                         |
| 2023-10-03 | wire_aggressor_run_start | 13506    | 7308                   | 833      | 135                        | 698                           | 137                       | 13369                          |
| 2023-10-17 | quote_relocation         | 36916    | 9421                   | 741      | 198                        | 543                           | 495                       | 36421                          |
| 2023-10-17 | touch_size_change        | 261554   | 21437                  | 741      | 353                        | 388                           | 2074                      | 259480                         |
| 2023-10-17 | wire_aggressor_run_start | 11346    | 6313                   | 741      | 128                        | 613                           | 129                       | 11217                          |
| 2023-10-18 | quote_relocation         | 35636    | 9490                   | 863      | 251                        | 612                           | 746                       | 34890                          |
| 2023-10-18 | touch_size_change        | 244757   | 28111                  | 863      | 437                        | 426                           | 3071                      | 241686                         |
| 2023-10-18 | wire_aggressor_run_start | 10482    | 6041                   | 863      | 141                        | 722                           | 142                       | 10340                          |

Comparison is exact containing-second intersection, not a fitted proximity tolerance. Every detector birth has nearest-before/nearest-after coordinates for each event definition, with missing boundaries retained. The detector-free event list contains many events outside birth seconds, and the detector has births without a same-second event under each selected definition. Earliest matched/unmatched raw cases are saved for every definition.

A structural event can be observed at its first completed group, so that definition does not require the Native selection-window wait. This changes event identity: it does not reproduce the 3,178 selected Native births with an earlier lawful clock. The full positive/negative recognition-advantage distribution, including structural events after recognition, remains visible.

M2 uses the strict interval [birth, recognition), excluding the recognition group itself. Endpoints use exact integer nanoseconds from candidate recognition; controls inherit that exact integer duration. M2 records the first within-lag group and total quantities for all 14 action/side and quote/size types, for every candidate and both controls. Absent events are explicit, not time zero. Cross-side tables preserve left-first, right-first, simultaneous-group-time, and one/both-absent orderings. These are retrospectively aligned footprints already occurring between birth and recognition, not a forecast or an identifiable incoming-birth precursor. Raw action-to-group attribution limits sub-group timing claims; no owner or intent attribution is made.

The inclusive first calculation is preserved in `inclusive-legacy-<date>-*.csv`. Exact inclusive/strict quantities and endpoint-only dispositions are retained in `<date>-footprint-endpoint-audit.csv`. The primary tables, charts and cross-side orderings now consistently exclude recognition itself. The following rows count event types, not unique births:

| day        | kind      | event_type_rows   | first_event_only_at_recognition   | event_types_with_endpoint_activity   | paths_with_endpoint_only_event   |
|:-----------|:----------|:------------------|:----------------------------------|:-------------------------------------|:---------------------------------|
| 2023-10-02 | candidate | 10374             | 133                               | 1463                                 | 84                               |
| 2023-10-02 | control1  | 10374             | 0                                 | 0                                    | 0                                |
| 2023-10-02 | control2  | 10374             | 0                                 | 0                                    | 0                                |
| 2023-10-03 | candidate | 11648             | 157                               | 1590                                 | 94                               |
| 2023-10-03 | control1  | 11648             | 0                                 | 0                                    | 0                                |
| 2023-10-03 | control2  | 11648             | 0                                 | 0                                    | 0                                |
| 2023-10-17 | candidate | 10360             | 148                               | 1438                                 | 75                               |
| 2023-10-17 | control1  | 10360             | 0                                 | 0                                    | 0                                |
| 2023-10-17 | control2  | 10360             | 0                                 | 0                                    | 0                                |
| 2023-10-18 | candidate | 12082             | 105                               | 1635                                 | 63                               |
| 2023-10-18 | control1  | 12082             | 0                                 | 0                                    | 0                                |
| 2023-10-18 | control2  | 12082             | 0                                 | 0                                    | 0                                |

Across all 14 measured event types, the candidate path counts are:

| day        | live_paths   | with_any_strict_event   | without_any_strict_event   |
|:-----------|:-------------|:------------------------|:---------------------------|
| 2023-10-02 | 741          | 739                     | 2                          |
| 2023-10-03 | 832          | 824                     | 8                          |
| 2023-10-17 | 740          | 731                     | 9                          |
| 2023-10-18 | 863          | 859                     | 4                          |

Within-lag absence counts below follow the full distributions. SAME/FLIP are shown separately; NO_PREDECESSOR remains in all underlying tables and figures. A path without quote relocation can still contain size changes or order actions. A path without wire-side buy/sell prints is not evidence of no order-book activity.

| day        | orientation   | kind      | paths   | no_quote_relocation   | no_buy_print   | no_sell_print   | no_wire_print   | neither_quote_nor_wire_print   |
|:-----------|:--------------|:----------|:--------|:----------------------|:---------------|:----------------|:----------------|:-------------------------------|
| 2023-10-02 | FLIP          | candidate | 353     | 41                    | 75             | 75              | 33              | 25                             |
| 2023-10-02 | FLIP          | control1  | 353     | 84                    | 115            | 127             | 106             | 80                             |
| 2023-10-02 | FLIP          | control2  | 353     | 108                   | 135            | 145             | 124             | 97                             |
| 2023-10-02 | SAME          | candidate | 387     | 50                    | 79             | 114             | 43              | 26                             |
| 2023-10-02 | SAME          | control1  | 387     | 116                   | 142            | 156             | 129             | 99                             |
| 2023-10-02 | SAME          | control2  | 387     | 95                    | 136            | 156             | 126             | 83                             |
| 2023-10-03 | FLIP          | candidate | 383     | 75                    | 92             | 84              | 35              | 29                             |
| 2023-10-03 | FLIP          | control1  | 383     | 130                   | 148            | 150             | 141             | 116                            |
| 2023-10-03 | FLIP          | control2  | 383     | 115                   | 148            | 151             | 139             | 109                            |
| 2023-10-03 | SAME          | candidate | 448     | 96                    | 110            | 103             | 45              | 36                             |
| 2023-10-03 | SAME          | control1  | 448     | 146                   | 179            | 190             | 168             | 136                            |
| 2023-10-03 | SAME          | control2  | 448     | 152                   | 179            | 188             | 172             | 138                            |
| 2023-10-17 | FLIP          | candidate | 353     | 41                    | 87             | 91              | 41              | 25                             |
| 2023-10-17 | FLIP          | control1  | 353     | 103                   | 149            | 151             | 122             | 87                             |
| 2023-10-17 | FLIP          | control2  | 353     | 102                   | 154            | 142             | 124             | 90                             |
| 2023-10-17 | SAME          | candidate | 386     | 48                    | 97             | 89              | 49              | 34                             |
| 2023-10-17 | SAME          | control1  | 386     | 98                    | 147            | 134             | 121             | 84                             |
| 2023-10-17 | SAME          | control2  | 386     | 101                   | 157            | 131             | 117             | 81                             |
| 2023-10-18 | FLIP          | candidate | 390     | 42                    | 94             | 91              | 35              | 25                             |
| 2023-10-18 | FLIP          | control1  | 390     | 135                   | 160            | 169             | 150             | 119                            |
| 2023-10-18 | FLIP          | control2  | 390     | 129                   | 157            | 154             | 141             | 111                            |
| 2023-10-18 | SAME          | candidate | 472     | 47                    | 102            | 107             | 47              | 31                             |
| 2023-10-18 | SAME          | control1  | 472     | 152                   | 182            | 197             | 169             | 130                            |
| 2023-10-18 | SAME          | control2  | 472     | 163                   | 200            | 202             | 185             | 142                            |

The exact first-event order, timestamps, quantities and all contrary/absent combinations are in the per-path tables. The data supports these observable intervals and orderings; it does not identify an incoming birth in advance or isolate a cause from the retrospective alignment.

Cross-day moonshot figures `crossday-M1-<orientation>.png` and `crossday-M2-<orientation>-1/2.png` use identical y scales within each event row. Their additional 540 panels reconcile in `crossday-moonshot-figure-reconciliation.csv`.

### Separating the clocks behind the similar shapes

Local `clock-decomposition-<definition>-<orientation>.png` and `clock-decomposition-recognition_delay-<orientation>.png` show every event-wait and recognition-delay value separately for all four dates, with no rescaling or smoothing. The 12 figures have 48 reconciled series; the full observation table retains 9,534 rows (3,178 births times three definitions), including six unavailable live-clock pairs.

For all 9,528 available pairs, exact integer nanoseconds verify: recognition minus event = (recognition minus birth) - (event minus birth). Thus each original M1 row includes the same candidate recognition-delay term. SAME recognition-delay curves have a central region around 50 seconds; the separate touch-size event-wait curves contain many events within the birth second and retain their longer waits in the tails. The table below follows these full distributions. Pearson values pair original recognition-minus-event with recognition-minus-birth by candidate, never by sorted chart rank.

| day        | orientation   | births   | live_clock_pairs   | touch_event_in_birth_second   | quote_Pearson   | touch_Pearson   | run_Pearson   |
|:-----------|:--------------|:---------|:-------------------|:------------------------------|:----------------|:----------------|:--------------|
| 2023-10-02 | FLIP          | 353      | 353                | 182                           | 0.205598        | 0.72511         | 0.180679      |
| 2023-10-02 | SAME          | 387      | 387                | 194                           | 0.272866        | 0.818346        | -0.00989      |
| 2023-10-03 | FLIP          | 383      | 383                | 187                           | 0.14527         | 0.804678        | 0.243986      |
| 2023-10-03 | SAME          | 449      | 448                | 242                           | 0.010776        | 0.785578        | -0.070335     |
| 2023-10-17 | FLIP          | 353      | 353                | 170                           | 0.390079        | 0.779298        | 0.101422      |
| 2023-10-17 | SAME          | 387      | 386                | 183                           | 0.271708        | 0.675844        | -0.115766     |
| 2023-10-18 | FLIP          | 390      | 390                | 194                           | 0.472602        | 0.794728        | 0.176907      |
| 2023-10-18 | SAME          | 472      | 472                | 242                           | 0.256409        | 0.714509        | 0.068723      |

Birth-second event counts include finalization-only candidates when an event clock exists; Pearson uses only available live-clock pairs. All before/at/after-recognition counts, contrary timing combinations, and NO_PREDECESSOR rows remain in `clock-decomposition-summary.csv` and `clock-decomposition-observations.csv`.

## Interpretation (separate from measurements)

SPECULATIVE: Similar central shapes partly reflect a shared recognition clock in the plotted difference. Different event waits contribute different tails. This descriptive decomposition and its Pearson pairings do not establish an independent common mechanism, causality or transferability.

SPECULATIVE: A fixed selection window plus variable group arrivals explains the measured clock accounting. It does not establish that price or book state causes a dipole. The recovered Native source and completed-group source are alternative flow measurements and remain separate.

SPECULATIVE: The operational lifetime is the first third consecutive second with flow opposite the anchor sign, or observation through tape end if right-censored. Undefined anchor direction has no lifetime. This analyst-defined convention makes one reproducible life/decay comparison; it is not a recovered natural lifetime and does not identify participant intent. Alternative persistence lengths and other endpoints remain open, with no current rule promoted.

SPECULATIVE: The hierarchy currently describes representation-dependent similarities and sparse extremes, not a stable taxonomy. Control reuse, overlapping paths, incomplete ratio histories, and four discovery dates limit claims of independent replication. Recurrence arithmetic cannot establish predictive or causal information by itself.

## Handoff

- Do the small isolated touch-size groups reflect single unusually displayed queues, replenishment, or another book episode? Trace their exact order histories before naming a mechanism.
- How do event identities change when action-time classification and prior-completed-quote classification disagree, especially around within-group quote changes? The full missed/added lists isolate the cases.
- How much of recognition delay is ordinary quiet-group waiting versus the selection competition, and which raw event definitions preserve a comparable identity?
- Which within-lag orderings repeat within each spread/activity stratum after accounting for reused controls and overlapping windows?
- How do life descriptions change under explicitly different endpoint conventions without imposing one as a natural boundary?
- Can partial October 2/17 populations be extended with comparable archived Native definitions, while retaining the current partial populations as their own results?
- Optional M3 crypto comparison was not run; no crypto transfer result is claimed.

All candidate forms, inverse paths, flat outcomes, undefined cases and recorded inputs remain available. Publish data, tables, renders and workbooks to markets-data under immutable versions with SHA256. PR #15 remains draft and unmerged.

## Requested shape overlays

Three local renders overlay the four SAME day curves for quote relocation, touch-size change and aggressor-run starts: `shape-overlay-<definition>-SAME.png`. Each has four colored curves at the original values and ordered-observation ranks, with no normalization or smoothing. Each figure reconciles 1,695 input rows to 1,693 plotted points and two unavailable live clocks. The parent delivered these renders in chat. `shape-overlay-points.csv`, `shape-overlay-figure-reconciliation.csv` and source SHA256 provenance retain the exact plotted values. Sorted visual resemblance alone does not establish an independent common mechanism; the subsequent exact clock decomposition is reported separately above.

## Input routing and local publication inventory

Input repository: [DavisAI1974/markets-data at 968fa113](https://github.com/DavisAI1974/markets-data/tree/968fa11324f66b70cd318140c51bf19e23f9ee4e). `MARKETS_DATA_DIR=E:/markets-data` is the configured local input root. The read-only audit verifies 25 declared SHA256 hashes; one null-hash entry remains unverified and three external archive references are not locally included. Nine inputs also match the exact pinned research cache bytes. Only byte-identical verified inputs are accepted; absent/unverified entries retain the pinned revision/cache fallback. No populations were exchanged or calculations restarted for routing.

See [pending publication inventory](PENDING_PUBLICATION.md) for the local artifact inventory hash and handoff limits. The user explicitly designated markets-data for outputs as well as inputs.

<!-- shape_forms:start -->

## Additive shape forms and environment follow-up

This follow-up preserves the completed research and the original SAME populations on October 2, 3, 17 and 18. October 18 is the pink curve throughout. CSV and figure publication destinations are recorded in PUBLICATION.md; this section contains the current numerical findings for phone review. The separate parent tail audit retains its own provenance and identity comparisons.

### Full observations before fitted descriptions

Three compact `shape_forms-negative-focus-<definition>.png` renders isolate the circled negative portions. `shape_forms-sections-<definition>.png` shows the complete curve and its negative, exact-zero and positive sections without resetting ranks. `shape_forms-gaps-<definition>.png` shows every adjacent gap and change in that gap. `shape_forms-markers-<definition>.png` marks every local gap extremum and exact sign boundary while retaining every original point. Negative recognition-minus-event means the first event occurred AFTER recognition; sorted rank is not chronological order.

| day        | definition               | rows   | negative   | zero   | positive   | unavailable   | largest_gap_s   | largest_gap_rank   |
|:-----------|:-------------------------|:-------|:-----------|:-------|:-----------|:--------------|:----------------|:-------------------|
| 2023-10-02 | quote_relocation         | 387    | 44         | 6      | 337        | 0             | 296.998         | 1                  |
| 2023-10-02 | touch_size_change        | 387    | 6          | 4      | 377        | 0             | 16.3253         | 1                  |
| 2023-10-02 | wire_aggressor_run_start | 387    | 107        | 9      | 271        | 0             | 77.5742         | 3                  |
| 2023-10-03 | quote_relocation         | 449    | 88         | 8      | 352        | 1             | 190.535         | 1                  |
| 2023-10-03 | touch_size_change        | 449    | 7          | 5      | 436        | 1             | 72.0231         | 1                  |
| 2023-10-03 | wire_aggressor_run_start | 449    | 123        | 7      | 318        | 1             | 85.7316         | 5                  |
| 2023-10-17 | quote_relocation         | 387    | 39         | 9      | 338        | 1             | 93.484          | 1                  |
| 2023-10-17 | touch_size_change        | 387    | 7          | 6      | 373        | 1             | 32.7644         | 2                  |
| 2023-10-17 | wire_aggressor_run_start | 387    | 102        | 7      | 277        | 1             | 80.7252         | 3                  |
| 2023-10-18 | quote_relocation         | 472    | 43         | 4      | 425        | 0             | 136.356         | 1                  |
| 2023-10-18 | touch_size_change        | 472    | 9          | 3      | 460        | 0             | 18.1874         | 5                  |
| 2023-10-18 | wire_aggressor_run_start | 472    | 112        | 5      | 355        | 0             | 100.602         | 1                  |

The observation table contains 5,085 birth-definition rows and 5,079 available values. The marker table retains all rows: 1,663 local gap maxima, 1,679 local gap minima and 42 section-boundary rows. Boundary rows include curve starts and transitions into unavailable-clock rows. Local extrema use the two immediate neighboring gaps and at least one strict inequality; no jump-size cutoff is applied. These numerous mathematical markers do not establish a unique set of natural market boundaries.

### Fitting conventions and every residual

Soft predictions and the candidate forms were recorded in PROGRESS.md before fitting. The forms are line a+b*r, logarithm a+b*log(r+c), shifted reciprocal a+b/(r+c), and vertically shifted exponential a+b*exp(-r/tau). r is the original zero-based observation rank. Each c/tau uses the declared rank-unit grid [0.25, 0.5, 1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024]. For each grid point, a and b minimize the sum of absolute residuals; the smallest total within that form chooses its grid point, with grid order resolving ties. No form is selected as a winner.

The finite grid is a fitting convention, not a discovered scale. A numerically constant basis (range below 1e-12) is recorded as unavailable for that grid point; it is not a market exclusion. All 1,920 grid attempts remain in `shape_forms-fit-grid.csv`. There are 192 source fits across four dates, three event definitions, four sections and four forms. Constant-zero sections do not identify a meaningful shift parameter; boundary grid choices and constant-response flags are explicit.

`shape_forms-models.csv` retains every parameter. `shape_forms-fits-<definition>-<section>.png` shows each original observation, all four fitted descriptions, and every same-day residual. Cross-day residual matrices freeze each source fit and apply it at every target original rank; common axis scales are used within comparable figure rows/matrices. The original observations are never replaced by fitted values.

Negative-section parameters follow. The shift column means c for log/reciprocal and tau for exponential; it is unused for a line. Display rounding is only in this Markdown table; full values remain in CSV.

| source_day   | definition               | form                | a        | b        | shift       | grid_boundary   |
|:-------------|:-------------------------|:--------------------|:---------|:---------|:------------|:----------------|
| 2023-10-02   | quote_relocation         | line                | -55.3891 | 1.67329  | unavailable | False           |
| 2023-10-02   | quote_relocation         | logarithm           | -121.147 | 34.5033  | 0.25        | True            |
| 2023-10-02   | quote_relocation         | shifted_reciprocal  | 16.0593  | -610.588 | 1           | False           |
| 2023-10-02   | quote_relocation         | shifted_exponential | -6.84351 | -587.685 | 2           | False           |
| 2023-10-02   | touch_size_change        | line                | -8.74795 | 2.18535  | unavailable | False           |
| 2023-10-02   | touch_size_change        | logarithm           | -10.5537 | 8.89725  | 0.25        | True            |
| 2023-10-02   | touch_size_change        | shifted_reciprocal  | 2.85364  | -12.8708 | 0.5         | False           |
| 2023-10-02   | touch_size_change        | shifted_exponential | 1.08437  | -23.9723 | 1           | False           |
| 2023-10-02   | wire_aggressor_run_start | line                | -116.137 | 1.31043  | unavailable | False           |
| 2023-10-02   | wire_aggressor_run_start | logarithm           | -302.062 | 67.1997  | 0.25        | True            |
| 2023-10-02   | wire_aggressor_run_start | shifted_reciprocal  | 28.7213  | -3522.07 | 8           | False           |
| 2023-10-02   | wire_aggressor_run_start | shifted_exponential | -13.1211 | -318.563 | 16          | False           |
| 2023-10-03   | quote_relocation         | line                | -175.992 | 2.50043  | unavailable | False           |
| 2023-10-03   | quote_relocation         | logarithm           | -456.227 | 106.384  | 0.25        | True            |
| 2023-10-03   | quote_relocation         | shifted_reciprocal  | 83.9893  | -7943.59 | 16          | False           |
| 2023-10-03   | quote_relocation         | shifted_exponential | -10.9933 | -406.592 | 16          | False           |
| 2023-10-03   | touch_size_change        | line                | -48.1687 | 8.03937  | unavailable | False           |
| 2023-10-03   | touch_size_change        | logarithm           | -63.0915 | 35.3899  | 0.25        | True            |
| 2023-10-03   | touch_size_change        | shifted_reciprocal  | 2.56756  | -57.36   | 0.5         | False           |
| 2023-10-03   | touch_size_change        | shifted_exponential | -6.01188 | -106.14  | 1           | False           |
| 2023-10-03   | wire_aggressor_run_start | line                | -204.382 | 2.00696  | unavailable | False           |
| 2023-10-03   | wire_aggressor_run_start | logarithm           | -592.357 | 127.651  | 0.5         | False           |
| 2023-10-03   | wire_aggressor_run_start | shifted_reciprocal  | 48.0887  | -6880.48 | 8           | False           |
| 2023-10-03   | wire_aggressor_run_start | shifted_exponential | -29.0153 | -629.143 | 16          | False           |
| 2023-10-17   | quote_relocation         | line                | -89.0755 | 2.83781  | unavailable | False           |
| 2023-10-17   | quote_relocation         | logarithm           | -163.174 | 46.3407  | 0.25        | True            |
| 2023-10-17   | quote_relocation         | shifted_reciprocal  | 38.7937  | -1690.54 | 8           | False           |
| 2023-10-17   | quote_relocation         | shifted_exponential | 16.8503  | -141.092 | 16          | False           |
| 2023-10-17   | touch_size_change        | line                | -75.5131 | 13.4158  | unavailable | False           |
| 2023-10-17   | touch_size_change        | logarithm           | -75.5131 | 38.613   | 1           | False           |
| 2023-10-17   | touch_size_change        | shifted_reciprocal  | 49.716   | -500.917 | 4           | False           |
| 2023-10-17   | touch_size_change        | shifted_exponential | 21.2051  | -96.7183 | 4           | False           |
| 2023-10-17   | wire_aggressor_run_start | line                | -125.529 | 1.53046  | unavailable | False           |
| 2023-10-17   | wire_aggressor_run_start | logarithm           | -358.434 | 80.6184  | 0.5         | False           |
| 2023-10-17   | wire_aggressor_run_start | shifted_reciprocal  | 54.756   | -6126.07 | 16          | False           |
| 2023-10-17   | wire_aggressor_run_start | shifted_exponential | 12.7875  | -251.042 | 32          | False           |
| 2023-10-18   | quote_relocation         | line                | -78.0807 | 2.37884  | unavailable | False           |
| 2023-10-18   | quote_relocation         | logarithm           | -176.133 | 50.2724  | 0.25        | True            |
| 2023-10-18   | quote_relocation         | shifted_reciprocal  | 19.2108  | -825.768 | 2           | False           |
| 2023-10-18   | quote_relocation         | shifted_exponential | 1.18988  | -227.127 | 8           | False           |
| 2023-10-18   | touch_size_change        | line                | -50.0507 | 7.47872  | unavailable | False           |
| 2023-10-18   | touch_size_change        | logarithm           | -224.253 | 82.7935  | 8           | False           |
| 2023-10-18   | touch_size_change        | shifted_reciprocal  | 234.668  | -9153.8  | 32          | False           |
| 2023-10-18   | touch_size_change        | shifted_exponential | 93.5064  | -144.894 | 16          | False           |
| 2023-10-18   | wire_aggressor_run_start | line                | -174.309 | 1.95506  | unavailable | False           |
| 2023-10-18   | wire_aggressor_run_start | logarithm           | -444.951 | 98.1145  | 1           | False           |
| 2023-10-18   | wire_aggressor_run_start | shifted_reciprocal  | 62.3213  | -7500.73 | 16          | False           |
| 2023-10-18   | wire_aggressor_run_start | shifted_exponential | 12.7138  | -319.987 | 32          | False           |

The residual table contains 271,040 model/target rows, including same-day fits, frozen across-day applications, and all quote-to-run and quote-to-touch applications. There are 160 unavailable rows and 22,664 predictions outside the source section's observed rank interval. Outside-domain predictions remain in the table and are separately colored; they are extrapolations. Every residual is shown in the corresponding local fit or transfer matrix. Residual sign is predicted minus observed seconds.

### Displaced quote curve compared with aggressor-run shapes

All four quote source days are applied to all four aggressor-run target days at their original ranks. The October 3 quote negative section has 88 observations, while the aggressor-run negative sections have 107/123/102/112. This necessarily creates ranks outside the October 3 quote section; they are retained. The full `shape_forms-quote-to-run-*` matrices include every source, target, form and signed section. The following slice shows all four forms of that October 3 quote description, with the contrary residuals and domain limits intact:

| target_day   | form                | rows   | within_source_domain   | outside_source_domain   | residual_min_s   | residual_max_s   |
|:-------------|:--------------------|:-------|:-----------------------|:------------------------|:-----------------|:-----------------|
| 2023-10-02   | line                | 107    | 88                     | 19                      | -32.5743         | 221.496          |
| 2023-10-02   | logarithm           | 107    | 88                     | 19                      | -206.219         | 40.1405          |
| 2023-10-02   | shifted_exponential | 107    | 88                     | 19                      | -91.1915         | 6.53387          |
| 2023-10-02   | shifted_reciprocal  | 107    | 88                     | 19                      | -77.8352         | 18.8786          |
| 2023-10-03   | line                | 123    | 88                     | 35                      | 21.2224          | 482.91           |
| 2023-10-03   | logarithm           | 123    | 88                     | 35                      | 31.4729          | 242.406          |
| 2023-10-03   | shifted_exponential | 123    | 88                     | 35                      | -11.2438         | 263.451          |
| 2023-10-03   | shifted_reciprocal  | 123    | 88                     | 35                      | 23.4623          | 273.121          |
| 2023-10-17   | line                | 102    | 88                     | 14                      | -28.515          | 238.322          |
| 2023-10-17   | logarithm           | 102    | 88                     | 14                      | -189.393         | 35.0124          |
| 2023-10-17   | shifted_exponential | 102    | 88                     | 14                      | -98.6619         | 14.3877          |
| 2023-10-17   | shifted_reciprocal  | 102    | 88                     | 14                      | -84.205          | 16.0959          |
| 2023-10-18   | line                | 112    | 88                     | 24                      | -1.76803         | 268.959          |
| 2023-10-18   | logarithm           | 112    | 88                     | 24                      | -158.756         | 45.0323          |
| 2023-10-18   | shifted_exponential | 112    | 88                     | 24                      | -55.9745         | 39.2487          |
| 2023-10-18   | shifted_reciprocal  | 112    | 88                     | 24                      | -43.4866         | 32.466           |

No translation, rank normalization, time warping or re-fit to the target aggressor curve is applied. A similar part of a sorted curve is not a match of event identities or chronology. The separate raw tail audit addresses those identities.

### Existing environment and paired controls

`shape_forms-environment-pairs.csv` retains 15,255 candidate-definition-kind rows, including both controls and unavailable finalization-only anchors. Exact candidate/control endpoints are computed from integer clocks, and the first subsequent structural event is looked up in the existing raw-derived event list. Source-environment fields retain the independently audited spread/activity buckets, trailing activity, quote change, and strict M2 action groups/quantities/orderings. `shape_forms-environment-contrasts.csv` contains all 10,170 paired control-minus-candidate timing contrasts. No new raw-event extraction or external 13-point join is introduced.

The environment charts show each individual timing/quote observation colored by spread and each paired timing contrast colored by activity. The following counts keep the candidate negative-section targets fixed and carry their two matched controls with them. A control is counted as negative only if its own first event is after its paired endpoint. C/C1/C2 denotes candidate/control1/control2; quote-flat and wire-print counts use the same retained pairs. Wire prints here mean recorded buy/sell-side T messages; their absence is not a claim of no book activity.

| day        | definition               | candidate_negative_targets   | control1_negative   | control2_negative   | flat_quote_C_C1_C2   | wire_prints_C_C1_C2   |
|:-----------|:-------------------------|:-----------------------------|:--------------------|:--------------------|:---------------------|:----------------------|
| 2023-10-02 | quote_relocation         | 44                           | 15                  | 16                  | 44/21/22             | 24/30/27              |
| 2023-10-02 | touch_size_change        | 6                            | 1                   | 1                   | 5/2/4                | 0/4/4                 |
| 2023-10-02 | wire_aggressor_run_start | 107                          | 59                  | 61                  | 52/53/44             | 68/53/58              |
| 2023-10-03 | quote_relocation         | 88                           | 41                  | 42                  | 88/47/51             | 58/45/45              |
| 2023-10-03 | touch_size_change        | 7                            | 1                   | 0                   | 7/3/2                | 0/3/4                 |
| 2023-10-03 | wire_aggressor_run_start | 123                          | 74                  | 64                  | 83/64/63             | 82/56/60              |
| 2023-10-17 | quote_relocation         | 39                           | 16                  | 17                  | 39/19/19             | 12/24/17              |
| 2023-10-17 | touch_size_change        | 7                            | 0                   | 0                   | 7/4/5                | 0/4/2                 |
| 2023-10-17 | wire_aggressor_run_start | 102                          | 49                  | 60                  | 53/48/52             | 59/57/51              |
| 2023-10-18 | quote_relocation         | 43                           | 14                  | 19                  | 43/17/26             | 16/24/21              |
| 2023-10-18 | touch_size_change        | 9                            | 2                   | 1                   | 9/4/5                | 0/5/4                 |
| 2023-10-18 | wire_aggressor_run_start | 112                          | 69                  | 74                  | 55/68/69             | 68/48/41              |

The complete section-by-kind-by-day counts, including positive, zero and unavailable targets, remain in `shape_forms-environment-section-counts.csv`. A negative quote-relocation lead constrains the quote path by definition; flat quotes in those rows are not an independently discovered mechanism. Other definitions and paired controls retain their contrary combinations. Matching strata do not make overlapping paths or reused controls independent observations.

### SPECULATIVE interpretation and open targets

SPECULATIVE: These shapes can serve as empirical targets for subsequent explanations of observable event timing and book behavior. The present algebra describes sorted distributions. It does not recover participant intent, a physical law, a unique mechanism, or the whole market environment. A proposed behavioral explanation still needs to reproduce the original event and quote paths across dates and both controls, including points its fitted curve does not describe.

SPECULATIVE: A gap extremum or sign boundary could help select raw cases for tracing, but its rank position is not a time transition in one dipole. The full provenance, sign sections, parameter-grid boundary choices and out-of-source-domain residuals identify questions to investigate; they are not acceptance rules.

The 13-external-point file remains a separate inventory with a different 749-family-start population. No relevance judgment, exclusion, or silent substitution into these 3,178 archived dipoles is made.

This follow-up currently has 110 local figures with 1,904 panel/series reconciliation rows. Every row records input, plotted and unavailable/not-marked counts. Generated artifacts belong in markets-data under the current user instruction; PR15 remains draft/unmerged.

<!-- shape_forms:end -->


## Evidence reconciliation — GitHub continuation, 2026-11-08

This section distinguishes independently inspected source definitions, saved measurements, the user's historical observations, and unresolved comparisons. No new market calculation was run on the desktop. Published artifact locations and verification are in [PUBLICATION.md](PUBLICATION.md).

The user clarified that the historical crypto figure averaged roughly 2,000 events to display a shape they had found recurring with only modest variation. Preserve this as user-reported historical evidence. It is not dismissed as an averaging artifact. The original individual curves, event selection and generator have not yet been recovered, so the extent of individual variation has not been independently remeasured here.

### Source ledger

| Comparison | Agreement | Difference | Unresolved / next evidence |
|---|---|---|---|
| Historical 2,000-winner crypto plot versus Desktop's new NG lean | Both show organized flow change around the event; Desktop's four dated panels visibly repeat a prebirth ramp, event plateau and subsequent decline. The user's historical record reports recurring individual shapes before averaging. | Crypto screenshot is an averaged winner-conditioned, turn-aligned curve labelled flow lean and price upside in bps. Desktop is all-covered birth-polarity-oriented trailing-20-second flow, summarized by p25/p50/p75; midpoint is in ticks. Crypto has a sharp trough; sign-reversed NG has a flat extremum. Orientation alone does not make their full shapes identical. | Exact crypto event table, denominator, sign convention, window, turn rule and generator. No numerical cross-market equivalence or causal mechanism established. |
| Desktop new NG lean versus our Native detector recovery | Event-centered one-sided flow and a 20-second-window structure are consistent with the recovered 20-second Native substrate. Native-action reconstruction recovers the saved births and recognition clocks. | Desktop uses completed-group reconstructed trade lots with wire-side/midpoint fallback; our exact detector recovery uses native action-time inputs. Summary quantiles are Desktop's existing artifacts, not replacements for our individual paths. | Match candidate IDs, clocks, trade-side attribution and window endpoints before testing equality. |
| Recognition-minus-first-event overlays | Both passes find an Oct 3 quote-relocation difference and substantial recognition-delay structure. | Desktop all-covered counts 741/824/740/852 differ from our live 741/832/740/863 and SAME-only overlays 387/448/386/472. Desktop's aggressor event is first birth-direction lots, timestamped by the left endpoint of a one-second interval. Quote/size events are first integer boundaries different from the anchor's state; intrasecond changes that reverse can be missed. Our events retain structural-event clocks and wire-side run changes. | Exact key-by-key join remains outstanding. Desktop's KS distances and our original-rank comparisons answer different questions. |
| Candidate coverage | Both retain archived denominators 741/833/741/863. | Desktop documents 8 additional Oct 3 seam/warm-up omissions, 11 Oct 18 seam/warm-up omissions, and the two finalization-only records. Our current pass retains those live seam candidates. | The omission categories are now documented in Desktop's source; exact omitted IDs/clock/book coverage still require a join. |
| Old directional-shape code versus the five-coin screenshots | `shape_s71/fit_shapes.py` explicitly preserves four long/short and winner/loser cells and fits pre-fire and tail separately. | It fits mean arcs on normalized time; its listed coins are SOL/BTC/ETH/XRP. `arc_gate.py` uses averaged aligned arcs and its own smoothing/window choices. These sources are related historical work, not an exact match to the five-coin July 7 screenshots. | Exact screenshot generators and the common +20-second feature remain unresolved. Do not import those processing choices into the current raw-scale NG pass. |
| Dipole-dive equation | `ng_dipole_runway_audit.py` directly defines directional onset minus directional current authority. | That source uses trailing 60-second flow and retrospective ZigZag leg labels, unlike the current 20-second birth detector. | It is a located equation, not proof that it generated the 2,000-winner screenshot. |

### Desktop lean overlay: inspected commit and denominator corrections

Source: [9622d038f, x09](https://github.com/DavisAI1974/Markets/blob/9622d038f/tasks/family-research-20261022/claude-pass-3day/x09_lean_around_birth.py), [x10 rendering](https://github.com/DavisAI1974/Markets/blob/9622d038f/tasks/family-research-20261022/claude-pass-3day/x10_lean_charts.py), and [the figure](https://github.com/DavisAI1974/Markets/blob/9622d038f/tasks/family-research-20261022/claude-pass-3day/crossday/es-lean-and-price-around-birth.png). Inspected the image, source, and saved CSV rows. This is a chronological birth-axis comparison, unlike our sorted-rank event-delay overlays. Lean uses 200 matched-control draws; the midpoint panels reuse 500 draws.

- Definition: lean = (birth-direction lots minus opposite lots) / total lots in the trailing 20 seconds. No-lot windows are undefined. Quantiles and exact-one shares use defined windows only; share_defined is separately retained.
- At boundary k=1, plus-one shares among defined windows are 0.997264 / 0.996287 / 0.983193 / 0.985419 for Oct 2/3/17/18. Defined shares of the complete covered cohorts are 0.986505 / 0.980583 / 0.964865 / 0.965962. Thus “98–99.7% of candidates” needs the nonempty-window qualifier. On Oct 18 the saved proportions correspond to 811 plus-one windows among 823 defined, out of 852 covered candidates.
- The common cliff is between boundary k=20 and k=21 in these saved tables. On Oct 18 the median changes from 0.52 to 0.04, and the defined-window share from 0.815728 to 0.653756. This is aligned with birth-second lots leaving the trailing window. The changing defined population is part of the observation, not evidence that every individual's lean falls by the median difference.
- Midpoint is polarity times (current midpoint minus that candidate's own anchor midpoint). Every valid path is zero at k=0 by construction. The plotted median remains zero while upper/lower percentile paths spread in both directions. Preserve the observed control differences away from the anchor; the V-shaped fan itself is not a median price reversal or proof of the same winner-conditioned crypto price-upside curve.
- The prebirth ramp lies outside the displayed activity/spread-matched control bands. Those controls do not condition on passing the same one-sided-flow birth selection. Therefore the residual ramp after controlling for detector selection is unresolved; it is too strong to assert that the ramp cannot arise from that conditioning. The measured separation remains evidence to explain.
- The old screenshot's late upturn near +60 seconds is absent from this NG median. Its cause remains unresolved until the original source/window/derivative endpoints are recovered. Do not label it an edge artifact without those checks.

### Paper-trading readiness checkpoint

[Existing paper handoff at 407a23379](https://github.com/DavisAI1974/Markets/blob/407a23379/tasks/family-research-20261022/codex-flow-book-discovery-20261108.md) retains 146 registry entries and 730 date-queue rows, with no performance-based exclusions. Its prospective trigger, side, order type, size, exit and simulator environment are explicitly unconfigured. Preserve those hypotheses and their contrary cases.

Readiness is not established. No running remote feed, simulator instance, fresh clock or end-to-end paper ticket/log was verified in this continuation. The existing `research/kalshi/ng_paper_loop.py` is a separate daily Kalshi forecast-to-ledger skeleton; its existence does not show that the Native dipole hypotheses are wired into a paper runner. `frankie_paper_manifest.json` describes research papers, so its READY label is not trading readiness. No paper order or live-money action was submitted.

The next operational check must identify the actual remote NG simulator route, verify live/replay input availability and clocks, bind the retained hypotheses without outcome-based filtering, and produce a receipted paper-only decision/fill/miss log. Do not substitute the early birth-aligned movement for a signal known at recognition; any earlier trigger needs its own known-by evidence.


## Four-date replication completion — 2026-11-08 Eastern

Latest user priority: finish October 2, 3 and 17 to the October 18 NG dipole analysis scope first. Assemble timestamped layers afterward, then add other researchers' work. Do not restart crypto-source exploration or paper infrastructure before finishing this replication.

The previously missing continuous precursor scan and primer diagnostics are now published in [markets-data](https://github.com/DavisAI1974/markets-data/tree/71240aa56a8b27f7d7f68acd154784579094e5c1/tasks/family-research-20261022/four-day-extensions/run-42563528655-1). [Hosted run 42563528655](https://github.com/DavisAI1974/markets-data/actions/runs/42563528655) succeeded. Source code: Markets `c4ca63f2816a50e051f70f6219f2378bd9530777`. Publication: markets-data `71240aa56a8b27f7d7f68acd154784579094e5c1`. There are 64 output files (34,935,051 measured bytes) plus the manifest.

Six unit tests passed. Before the other dates ran, October 18 reproduced all eight saved continuous-scan tables and all three primer tables, with numerical comparison tolerance rtol 1e-11 / atol 1e-12. Per-date checks passed for strict availability, all births, onset/operator reconciliation, contiguous observation clocks, outcome denominator conservation, and the two finalization-only births. The published summary/verification files were read back and the chart visually inspected.

| Analysis | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
|---|---|---|---|---|
| Native A–E, M1/M2 and shape forms | Existing complete | Existing complete | Existing complete | Existing complete |
| Original dipole application, 11-arm stack | Existing complete | Existing complete | Existing complete | Existing complete |
| Dipole prebirth controls, aggression-to-rest, delayed observations | Existing complete | Existing complete | Existing complete | Existing complete |
| Continuous completed-second precursor scan, all 10 predicates | Newly complete | Newly complete | Newly complete | Reproduced |
| Primer next-price-change and 1ms–20s response grid on aggression-to-rest cases | Newly complete | Newly complete | Newly complete | Reproduced |
| Primer dipole prebirth quote-age/control-reuse sensitivity | Newly complete | Newly complete | Newly complete | Reproduced |
| Separate 749-family-start study and family primer subset | Missing comparable population | Missing comparable population | Missing comparable population | Existing reference |

| Date | Retained births | Observed seconds | Input-available seconds | Unique onset seconds |
|---|---:|---:|---:|---:|
| Oct 2 | 741 | 75,600 | 75,579 | 10,932 |
| Oct 3 | 833 | 82,800 | 82,758 | 11,928 |
| Oct 17 | 741 | 75,600 | 75,579 | 10,602 |
| Oct 18 | 863 | 82,800 | 82,758 | 10,383 |

October 2 and 17 retain the original partial spans. No prefix was substituted. The finalization-only birth on October 3 and on October 17 remains in retrospective links without an invented recognition.

Evidence status, before assembling other layers:

- **Agrees:** the same precursor categories occur on every date. Among births with a prior onset, median last lead is 12–13 seconds for step weakening, 19 seconds for fresh opposed weakening on all four dates, and 19–20 seconds for half-window weakening. These are descriptive onset-to-birth intervals, not simulated trade lead times or measurements of whole-path similarity.
- **Differs:** onset counts, unlinked onset counts, and control sensitivities differ. For example, October 2's one-second prebirth displayed-lot contrast is negative across all matched pairs but positive when both quotes are at most one second old. October 17's 20-second contrast changes from positive to negative under that same fixed diagnostic. The original summary statistics are reproduced as diagnostics; individual input values and time paths are not rescaled.
- **Unresolved:** the separate 749-family population, older targeted family/lifecycle overlaps, and original Family A runway identities are not supplied by these sealed dipole inputs. This run does not certify those broader studies as replicated. Exact duration/exhaustion strategy and paper execution remain unconfigured. The optional parent tail audit was a proposed additional study, not a completed October 18 module to copy.

No desktop computation, producer rerun, timestamp-layer assembly, external researcher merge, simulator execution or live order occurred in this replication. All ten precursor hypotheses and all existing 11 stack arms remain retained.


## Remaining family replication completed — November 9

The remaining three-date family study is complete and published. User steering was to finish this before timestamp assembly or paper setup; neither was started during this work.

- [Published evidence](https://github.com/DavisAI1974/markets-data/tree/7b50d634f94ea4777d1e772ac2b916b001019582/tasks/family-research-20261022/family-replication/run-42566535537-1), markets-data commit `7b50d634f94ea4777d1e772ac2b916b001019582`.
- [Successful hosted run 42566535537](https://github.com/DavisAI1974/markets-data/actions/runs/42566535537).
- [Analysis source](https://github.com/DavisAI1974/Markets/blob/59195f9339c48cfcbd4a6bf9916a935a4da4fb1d/agent-pass/replication/finish_family_replication.py).
- 96 manifested output files, 12,575,413 measured bytes, plus four manifests and RUN_STATUS.json. Per-date receipts, manifests, reference comparisons and workflow conclusion were read back from the publication.

## Completed scope

The original family four-arm comparison (baseline, flow, book, both), family prebirth controls at 1/5/20/60 seconds, primer next-price-change and 1/5/25/100/250/500 ms and 1/5/20 s responses, plus quote-age/control-reuse sensitivities now cover October 2, 3 and 17. October 18's original 749-family reference reproduces eight four-arm tables; the missing-value fix also reproduces all three previously saved reference primer tables.

The four-arm method is unchanged: ridge alpha 10, train-only scaling, expanding 40/60/80% chronological splits, horizon purge and 600-second embargo, five response horizons (1/5/20/60/300 seconds), signed and absolute targets. All arms use identical eligible rows within each fit. These are the archived explanatory models, not new shape fitting or trading admission rules. No original input values or time paths were adjusted.

| Date | Retained families | Four-arm eligible | Fits | Prebirth case rows | No eligible primer prequote |
|---|---:|---:|---:|---:|---:|
| Oct 2 | 796 | 510 | 120 | 3,184 | 2 |
| Oct 3 | 849 | 535 | 120 | 3,396 | 4 |
| Oct 17 | 824 | 517 | 120 | 3,296 | 2 |
| Oct 18 original reference | 749 | 437 | 120 | 2,996 | 0 |

All families remain in opportunities and prebirth cases. Model eligibility and response availability are reported separately. In the receipt, `primer_missing_prior` and the primer-disposition label `no_strict_pre_group` mean the original method did not supply an **eligible** prequote; this includes invalid quotes, not only an absent earlier source group. Each new date has exactly one family with no earlier source group. No replacement quote or invented clock was supplied.

## Population and source verification

The exact original structural-descriptor function was recovered at producer commit `2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134`; its SHA256 and dependent source pins are retained. Applying it to saved raw action groups reproduced all 749 original October 18 family IDs, first receive clocks, source ordinals, close cursors and occurrence counts. The full observed October 18 universe has 764 IDs, including 15 outside the old catalog. That full inventory is preserved in the [preflight publication](https://github.com/DavisAI1974/markets-data/tree/54e1b1be98ae6defff25ccfe7e1c3498e8f569f9/tasks/family-research-20261022/family-replication/run-42564821790-1/family-preflight).

The other dates follow the existing direct-ROOT first-observation convention: all structural IDs observed on that date. They are not forced into October 18's selected 749-ID catalog. A first observed structural family is not asserted to be a natural market-event birth.

| Date | Completed ROOT rows | Verified compressed parts | Verified decompressed bytes | Extracted strict-pre snapshots |
|---|---:|---:|---:|---:|
| Oct 2 | 600,291 | 211 | 520,064,232,895 | 795 |
| Oct 3 | 653,912 | 236 | 572,726,375,854 | 848 |
| Oct 17 | 635,170 | 243 | 581,067,333,483 | 823 |

Every archive part and the full decompressed SHA256, byte count and row count passed. Selected frames matched original receive clocks and cursors; first-family descriptors and strict-pre full-book depth sums/best quotes reconciled. Saved coordinates include byte offsets and row hashes. Subsequent checks passed for strict information availability, family conservation, equal model denominators and embargo separation.

The initial extraction run preserved these successful source checks but failed during primer application: absent/invalid prequotes were CSV blanks while that module expected NaN. The correction only converts this missing-value representation, records the disposition, and resumes from the immutable verified extraction. The initial failure remains recorded; it is not relabeled a successful run. The successful follow-up rechecked source receipts and unchanged October 18 results.

## Agreement, differences and unresolved comparisons

- **Agrees:** the same structural definition and the same analysis pipeline apply to all three new dates. For matched family cases, the archived one-second classified-activity contrast (`total1`) at 1/5/20-second leads is positive on October 2, 17 and the October 18 reference. This is a recorded diagnostic, not proof of a whole-path shape or a trading edge.
- **Differs:** October 3's all-pair `total1` contrasts are negative at those leads. At the one-second lead, its mean difference is -0.523 lots, but becomes +0.281 when reused controls receive equal weight. October 18's one-second fresh-quote subset changes from +0.226 to -0.178 under equal-control weighting. Both versions and every case remain saved. Population sizes, available history and model errors also differ; no result was filtered to force agreement.
- **Current status:** our source-clock event joins are now assembled in the combined studies below; existing renders and Desktop's layer still require attachment. The selected October 18 family catalog and the other dates' full observed populations differ, so pooled differences cannot be assigned solely to the trading date. The older 99-field/13-external-point study, targeted family/lifecycle overlaps and original Family A runway identities are separate scopes, not certified by this completion. Event duration, exhaustion and execution timing still require the planned joined evidence and paper setup.

The recovered family input gap is closed for this four-arm/prebirth/primer scope. Existing dipole A–E/M1/M2/shape work and continuous extensions remain complete as recorded in FOUR_DAY_REPLICATION.md. No desktop calculation, market producer rerun, external-researcher merge, simulator order or live-money action occurred. PR15 remains draft and unmerged.


# 2026-11-09 — combined timing/event studies completed

## Reproducible inputs and execution

- Exact action clocks and book reconstruction: markets-data commit 2fd55ea1276d00530f8cdbd1caf5918910494f19, combined-events/run-42569937357-1. Original DBN action timestamps were recovered; every retained action reconciled to the compact cache and every completed group's best prices, sizes and order counts to the saved export.
- Full studies: run 42570958744, code 782e1e11ffb4c3eb0fbfe6fd84fc75a3a3fdc516.
- Independent read-back, clock/reference verification and joint links: run 42571551209, code 43e4d2bdfa5a10f4df9ab1b12da1dd713615bbd4.
- Authoritative data publication: 87dc338f2e74646eb731b3cd6f8968a5a0a653e2, tasks/family-research-20261022/combined-events/run-42571551209-1.
- October 2 and 17 have partial retained session coverage. Counts refer to each saved span, not equal full-session coverage.

## Completed scope

1. Chronology, duration and overlap: all retained prints, equal-price stretches, directional print legs, first family observations and all occurrences, neighboring starts, shifted family windows, prior price changes and actual archived dipole recognition links.
2. Pressure and response: size-one onsets, early falling-size signals and retreat-to-previous-second signals; strict-prior print cadence, fresh/rolling wire flow, quote-ending mechanisms, next-group print arrival and delayed hypothetical quote observations.
3. Large moves and recovery: midpoint jumps of at least two ticks, prior signals, 1/5/20-second response, first half/full return after the first-five-second displacement, selected original actions/book states, and fixed-price versus moving-rank depth changes.
4. Explicit cross-study joins: cross-study-event-links.parquet retains one row per pressure signal with its structural family, already-recognized dipole, previous trade and observable flow/book/cadence context. cross-study-condition-outcomes.parquet describes joint conditions without collapsing source events. Retrospective leg IDs are navigation only, not signal inputs.

| Date | Trades | Price stretches | Print legs | First families | Pressure signals | Large moves | Joint outcome rows |
|---|---:|---:|---:|---:|---:|---:|---:|
| Oct 2 | 37,670 | 9,569 | 5,996 | 796 | 109,307 | 46 | 327,921 |
| Oct 3 | 41,410 | 10,573 | 6,907 | 849 | 116,187 | 58 | 348,561 |
| Oct 17 | 33,451 | 9,762 | 5,592 | 824 | 114,994 | 57 | 344,982 |
| Oct 18 | 30,739 | 9,109 | 5,120 | 764 | 109,754 | 64 | 329,262 |

The original October 18 selected 749-family study remains correctly reproduced in FAMILY_REPLICATION.md. This expanded chronology includes all 764 observed structural families. The 15 additional families are a scope difference.

## Verification and comparison

**Agrees:** original October 18 chronology counts, bounded signal counts (1,012 size-one, 2,850 early-falling, 698 retreat), next-group arrival cells, 64 large moves, all twelve original rule/side-by-horizon outcome cells and thin-quote ending/by-entry counts reproduce. Every date passes individual signal clocks, strictly prior print order, episode endings, delayed quote clocks and integer-nanosecond schema checks. Joint outcome denominators conserve every signal and its three horizons.

**Differs:** date populations and observed outcomes vary. Under the defined 600-second recovery observation, full returns occur in 35/46, 48/58, 42/57 and 49/64 large moves respectively. A failure to observe return is not proof of permanent movement. Structural starts, Native births and CCode's independent candidates are distinct populations; a family first observation is not automatically a market birth.

**Unresolved:** CCode's independently generated 839/857/830/890 candidates still require explicit identity/scope matching to Native 741/833/741/863; our study uses actual archived recognition, not t0+50. See CCODE_FAMILY_AND_RECOGNITION_INPUTS.md. Desktop's shape layers and the old 2,000-winner curves are not yet reconciled by these joins. Recognizable shape, remaining duration and useful decision timing still need interpretation against these individual records.

## Clocks, limits and next use

Event, receive, completed-group known-by and actual recognition clocks remain separate integer nanoseconds with source cursors/groups. No smoothing, normalization, value adjustment or forced equal populations. Finalization-only candidates retain missing live recognition; nominal lifetime endpoints do not establish full-path availability.

The historical 1ms entry and 1/5/30-second exits are hypothetical quote observations with observed spread, not actual fills. First recovery is not event death. Overlapping cases and joint counts are descriptive, not independent trials. This completes the specified combined studies, not every historical 99-field lifecycle or hand-curated case audit.

Next use these tables to pin the existing individual renders and other researchers' records to raw source clocks. The 99 layers and 13 external points stay deferred. Paper configuration/readiness still needs checking; no paper orders have been started by this work.

Known mistakes are corrected in the active results and summaries. The corrected version is authoritative; erroneous substitutes are not competing findings. Original observations, including unfavorable cases and genuine missing data, remain intact.



# 2026-11-09 — whole-lifecycle audit and complete render publication

All four source audits and final render jobs passed. See [DIPOLE_RENDERS.md](DIPOLE_RENDERS.md) for immutable publications, full counts, scope and visual review. 3,178 candidates and 6,352 original matched controls retain separate parent identities. 397,815 original-scale lifecycle points remain in complete ordered sequences, including undefined seconds. Original path windows retain their own sampling cut clocks, cursor selectors and explicit parent links. Whole print-leg and quote-episode spans remain separate from their timed observations.

Corrections: restored anchor points omitted from the old lifecycle point tables; reconstructed two finalization-only lifecycles from original flow without invented recognition. Thirteen controls outside native-flow coverage remain explicit unavailable cases. All 166 per-date tables and 37 cross-date tables passed candidate-reference checks. Per-date checks also reconciled trade/leg and pressure-event child identities and source clocks.

**Agrees:** original operational lifecycle endpoints and every existing post-anchor path value reproduce. Source clocks/cursors and IDs agree across the joined individual records. **Differs:** whole lifecycles can outlast or end before recognition; birth-to-recognition windows are context components rather than lifecycle boundaries. Native action-midpoint flow and completed-group/wire measurements remain explicitly different definitions. **Unresolved:** the third-opposite-second convention is not a proven natural event death. CCode's independent population still requires actual identity/scope reconciliation, and paper readiness is not established by these renders.

The complete collection includes 337 original figures, 9,530 whole-instance pages and four individual-duration figures with source-row indices. The 24-page starter packet chooses first chronological cases by orientation and their original control1, not winning outcomes. The known plotting mistakes were corrected; the latest verified render publication is authoritative. No desktop research computation or external message was used.
