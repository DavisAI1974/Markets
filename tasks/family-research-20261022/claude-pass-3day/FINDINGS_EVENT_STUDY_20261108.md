# Second-by-second birth-aligned study, four days (Oct 2, 3, 17, 18)

Claude chat, November 8, 2026. Companion to FINDINGS_THREE_DAYS_20261108.md. Same candidates (741, 824, 740, 852 covered), same reconstructed books, same matched-control method (500 draws; same tape, spread regime and activity quintile; birth-axis controls are 3 s grid anchors, recognition-axis controls are random group closes). Each day is one set of dependent observations and remains discovery. Section 6 is interpretation and is labelled.

## 1. Construction and checks

- Birth axis: boundaries b_k = pre-birth cutoff + k s, k = -60 to +160. Second k is the interval (b_k, b_k+1]; second 0 is the birth second. Recognition axis: boundaries -100 to +60 around the recognition receive time.
- State at a boundary = book after the last completed group closed by it. Per-second sums = records of the groups closed in (b_k, b_k+1], so seconds partition the records.
- Orientation by birth polarity. Target side = the side the birth direction trades against (ask for a buy birth). Own side = the other.
- Check against earlier tables: on the recognition axis the oriented midpoint at +1, +5, +20, +60 s equals the earlier cohort forward values on every covered row (741/741, 824/824, 740/740, 852/852 at each horizon), and trailing 20 s with/against lots equal the earlier cohort lots on every row.
- Plotted points equal table rows: 688 plotted series, 130,784 points (crossday/es_chart_reconciliation.csv). Heatmap rows 741, 824, 740, 852 equal table rows (es_heatmap_reconciliation.csv).
- Control pool: every covered candidate had a matched pool on both axes (741, 824, 740, 852 candidates with a pool; x03_receipt.json per day).

## 2. What the birth second and the 20 seconds before it look like (every day)

Share of candidates with any aggressor lots in the stated second (cohort; matched-control 2.5 / 50 / 97.5 percent in brackets):

| second | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
|---|---|---|---|---|
| k = -20, lots against the birth direction | 0.301 (0.041 / 0.055 / 0.072) | 0.318 (0.042 / 0.058 / 0.073) | 0.357 (0.041 / 0.054 / 0.070) | 0.339 (0.039 / 0.052 / 0.067) |
| k = -20, lots in the birth direction | 0.201 | 0.226 | 0.224 | 0.209 |
| k = -10, lots against | 0.000 | 0.000 | 0.001 | 0.001 |
| k = 0, lots in the birth direction | 0.381 (0.045 / 0.059 / 0.076) | 0.392 (0.044 / 0.061 / 0.078) | 0.346 (0.043 / 0.057 / 0.073) | 0.344 (0.043 / 0.058 / 0.073) |

Candidates with no against-direction lots at all in seconds -19 to -1: 740 of 741, 821 of 824, 730 of 740, 843 of 852. Candidates with against-direction lots in second -20: 223, 262, 264, 289. Candidates with with-direction lots in second 0: 282, 323, 256, 293. The same two-spike shape (second -20 and second 0) appears in the share of candidates with fills, adds at the touch and unlinked cancels at the touch on both sides (es-book-activity-birth-axis.png).

## 3. Midpoint paths

Share of candidates with oriented midpoint change > 0 / < 0 relative to the pre-birth boundary (k = 0), with matched-control 2.5 to 97.5 percent bands for the share > 0 (full per-second rows: x03_cohort_stats.csv.gz and x03_control_stats.csv.gz per day; selected seconds side by side: crossday/es_selected_seconds.csv):

| k | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
|---|---|---|---|---|
| -10 | 0.065 / 0.200 (0.143-0.194) | 0.052 / 0.171 (0.126-0.174) | 0.064 / 0.209 (0.145-0.194) | 0.070 / 0.266 (0.160-0.209) |
| +1 | 0.197 / 0.020 (0.019-0.044) | 0.160 / 0.019 (0.018-0.040) | 0.181 / 0.016 (0.022-0.049) | 0.208 / 0.020 (0.027-0.053) |
| +5 | 0.265 / 0.090 (0.088-0.132) | 0.212 / 0.078 (0.081-0.120) | 0.241 / 0.096 (0.093-0.135) | 0.302 / 0.102 (0.103-0.149) |
| +20 | 0.350 / 0.193 (0.209-0.268) | 0.341 / 0.176 (0.192-0.248) | 0.349 / 0.218 (0.208-0.265) | 0.400 / 0.242 (0.232-0.291) |
| +60 | 0.466 / 0.305 (0.322-0.389) | 0.411 / 0.296 (0.291-0.359) | 0.443 / 0.301 (0.314-0.380) | 0.458 / 0.354 (0.339-0.409) |
| +160 | 0.493 / 0.375 (0.385-0.450) | 0.445 / 0.380 (0.373-0.442) | 0.449 / 0.400 (0.384-0.452) | 0.489 / 0.394 (0.400-0.464) |

Before the birth, on every day the share with oriented change > 0 at k = -10 is below the control band and the share < 0 is above the control median (above the band on Oct 2, 17 and 18, at its upper edge on Oct 3): the midpoint had moved in the birth direction going into the birth boundary more often than in the controls. After the birth second the share > 0 rises steeply on every day and sits above the control band through at least +60 s; the share < 0 sits below the control median.

First second with a non-zero oriented change after the birth-second boundary (count of candidates whose first change is at boundary k = 1, i.e. inside the birth second, in the birth direction / against; control 2.5 / 50 / 97.5 for the in-direction count): Oct 2: 146 / 15 (14 / 23 / 33); Oct 3: 132 / 16 (15 / 24 / 33); Oct 17: 134 / 12 (16 / 26 / 36); Oct 18: 177 / 17 (23 / 33 / 45). Never changed within +160 s: 12, 43, 22, 12. Full first-move distribution for k = 1 to 160: x03_first_move_birth_axis.csv per day and es-first-move-timing-birth-axis.png.

Every candidate's full oriented-midpoint path (k = -60 to +160) is in x03_cohort_mid_o_birth_axis.csv.gz per day and drawn in es-heatmap-oriented-mid-paths.png sorted by recognition delay.

## 4. Where the births sit in the one-sided runs of the 20 s flow series (x05, x06)

A run = consecutive series seconds with |ratio| = 1 and the same sign.

| | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
|---|---|---|---|---|
| runs | 1,185 | 1,321 | 1,187 | 1,377 |
| births | 741 | 832 | 740 | 863 |
| births on the first second of a run | 495 | 562 | 515 | 583 |
| runs containing at least one birth | 737 | 827 | 732 | 855 |
| runs containing more than one birth | 4 | 4 | 6 | 5 |

Births not on the first second of a run sit 1 to 34 seconds into it; counts are between 8 and 33 per position at positions 1 to 9 and between 0 and 9 per position at 10 to 19 (x05_birth_position_in_run.csv). The share of runs that contain a birth rises with run length (Oct 2: 59 of 113 runs of 1 s, 116 of 239 of 6 to 10 s, 299 of 420 of 11 to 20 s, 17 of 18 over 40 s; the other days are similar). Holding one onset per h seconds does not reproduce the recorded set at any h tried (x05_onset_hold_rules.csv).

Recorded detection lag against position in the run (covered candidates, four days, 3,157 rows; x06_lag_classes.csv):

| class | rows | recognition delay (s), range across the four days |
|---|---|---|
| birth on run onset, lag = 50 | 1,841 | p50 52.4 to 53.7 |
| birth inside a run, lag = 50 | 398 | p50 52.8 to 54.0 |
| birth inside a run, lag + seconds since run onset = 50 | 394 | p50 49.0 to 50.0; p5 43.1 to 44.1 |
| birth on run onset, lag < 50 (6 to 48) | 303 | p50 20.2 to 24.1 |
| other | 221 | p50 25.0 to 27.6 |

Every birth 10 or more seconds into a run has lag 50 (171 of 172 at positions 10 to 19, 44 of 44 at 20 and above).

## 5. First-event curves (x07, x08): reproducing the sorted "recognition minus first event" form

For each covered candidate: first aggressor lots in the birth direction, first change in either touch size, first change in the best bid or best ask price, each searched from the birth-second start boundary forward to +700 s on my books; y = recognition receive time minus that first event time. These are my definitions on all covered candidates, not SAME-birth-only and not the other agent's definitions. Each day sorted separately and overlaid per event type (es-first-event-curves.png). Plotted points + no-event rows equal rows for all 12 curves (x08_reconciliation.csv); one Oct 3 row has no quote relocation within the tape.

| event, day | n | p5 | p25 | p50 | p75 | p95 | min | share y < 0 | share 45 <= y <= 55 |
|---|---|---|---|---|---|---|---|---|---|
| aggressor, Oct 2 / 3 / 17 / 18 | 741 / 824 / 740 / 852 | -47.9 / -39.4 / -61.2 / -49.5 | 19.3 / 21.2 / 18.5 / 19.1 | 46.3 / 45.5 / 45.1 / 46.1 | 53.6 / 52.9 / 52.9 / 51.7 | 75.9 / 69.9 / 73.8 / 64.8 | -368 / -275 / -376 / -489 | ~0.1 | ~0.3 |
| touch size, Oct 2 / 3 / 17 / 18 | same | 7.0 / 6.3 / 7.5 / 7.2 | 42.2 / 40.9 / 39.9 / 41.4 | 49.9 / 49.8 / 49.4 / 49.5 | 53.5 / 53.1 / 53.4 / 51.7 | 75.1 / 69.8 / 73.7 / 62.9 | -51 / -113 / -76 / -127 | ~0.0 | ~0.5 |
| quote relocation, Oct 2 / 3 / 17 / 18 | 741 / 823 / 740 / 852 | -44.2 / -112.7 / -56.6 / -33.4 | 10.5 / -0.0 / 8.2 / 17.3 | 39.0 / 35.0 / 39.6 / 41.3 | 50.1 / 48.4 / 49.8 / 50.1 | 67.3 / 62.1 / 64.2 / 60.2 | -595 / -434 / -309 / -394 | ~0.2 / 0.3 / 0.2 / 0.1 | ~0.3 / 0.2 / 0.3 / 0.3 |

Two-sample KS distances between curves (distance between empirical distributions, no threshold applied; x08_ks_between_curves.csv):
- Same event type across days (18 pairs): 0.031 to 0.122. Largest within type: quote relocation 0.122 (Oct 3 against Oct 18), aggressor start 0.089, touch-size change 0.078.
- Different event types on the same day (12 pairs): 0.165 to 0.348.
- Quote relocation of each day against the aggressor-start curve of each day: Oct 2 0.145 to 0.171; Oct 17 0.163 to 0.191; Oct 18 0.165 to 0.194; Oct 3 0.194 to 0.219. Oct 3's quote-relocation curve is the farthest of the four from the aggressor-start curves in this construction.
- Oct 3 quote relocation against the other days' quote relocation: 0.077 (Oct 2), 0.091 (Oct 17), 0.122 (Oct 18). Its left tail is the longest of the four days (share y < 0: about 0.25 of rows, p5 -113 against -33 to -57).

Share of Oct 3 candidates with quote relocation after recognition by birth tape: 0.333 of 42 (prior-evening tape), 0.248 of 782 (own-day tape). By UTC hour of the birth, Oct 3 shares are 0.40 to 0.47 in hours 0 to 2 and 0.50 in hour 20; the same hours on the other days are 0.12 to 0.39 (hours 0 to 2) and 0.17 to 0.33 (hour 20). Regenerate any hour from x07_first_events.csv.

## 6. Interpretation (labelled; not measurements)

SPECULATIVE readings to test, not adopted:
- Section 2 reads as a time structure that is the one-sided 20 s window itself: the birth sits where a window with no against-direction lots begins to be filled by with-direction lots, either because the last against-direction trades have just aged out (second -20) or because the first with-direction lots arrive (second 0). About two thirds of births sit on the first second of a one-sided run, the rest 1 to about 19 s into one. Which runs receive a birth is not recovered here (62 percent of runs on Oct 2 contain one).
- The recorded lag takes distinct values by class: exactly 50, exactly 50 minus the seconds since run onset, or 6 to 48. That agrees with the three-part shape (plateau at about 50, shoulder below it, right tail) in the first-event curves, in the delay histogram of the earlier pass and in the curves the user circled. A reading consistent with the data: the plateau is births recognised 50 s after a reference second, the ramp below it is births whose reference second is earlier or whose recognition arrived sooner, and the left tail is first events that occur after recognition. Which reference second applies to which class is open.
- The curves for the three event types differ in the sub-plateau region by more than the four days differ from each other within a type (KS 0.165 to 0.348 against 0.031 to 0.122). That repeats on my construction, which differs from the other agent's. Oct 3's quote-relocation curve is the one that separates from the other days in my version; in my version it does not move toward the aggressor-start curves.
- The distinct regimes in the user's circled areas can be tested as separate populations (section 4 classes). Cohort path shares differ by class (x06_lag_classes.csv: for example first-move-in-birth-second share 0.31 / 0.27 / 0.28 / 0.35 for births on run onset with lag 50, against 0.08 / 0.00 / 0.06 / 0.06 for births inside a run with lag 50), so the classes carry different book behaviour at the birth second.

## 7. Limits

- Control anchors on the birth axis are arbitrary grid times; controls near candidates are not excluded.
- First-event definitions in section 5 are mine. The user's renders are SAME-birth only (387 / 449 / 387 / 472 rows); SAME/FLIP orientation is not in the other days' candidate inputs here, so the exact curves cannot be reproduced.
- Trade side uses wire side where given and the midpoint rule otherwise (as in c04).
- Each day is a dependent set from one session of one instrument. No pooling across days.
