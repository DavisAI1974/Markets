# Native dipole research findings

## Data first

Part 1A tables: [every candidate and operand](tables/20231018-candidate-operands.csv), [every candidate/control path member](tables/20231018-path-members.csv), [all 288,144 path observations](tables/20231018-paths.csv.gz), [raw cases](tables/20231018-case-raw-records.csv.gz), and [figure reconciliation](tables/20231018-figure-reconciliation.csv). The workbook contains the complete review tables; the longer observations remain lossless compressed CSV.

![SAME candidate paths](figures/20231018-candidate-SAME-quotes.png)
![FLIP candidate paths](figures/20231018-candidate-FLIP-quotes.png)

All 36 Part 1A figures are in `figures/`: candidate, control1 and control2; SAME, FLIP and NO_PREDECESSOR; quotes, actions, signed ratio and fractional recognition endpoints. The reconciliation has 270 panel rows. Each heat strip shows actual levels or one-interval lots. Its companion endpoint plot retains the fractional final observation. White space after recognition is not a zero. Ratio undefinedness is retained explicitly.

Part 1B: [all detector comparisons](tables/20231018-detector-all-comparisons.csv), [missed and added births from completed-group flow](tables/20231018-birth-differences-completed_group.csv), [native-action differences, header only because there are zero](tables/20231018-birth-differences-native_action.csv), [all lag observations](tables/20231018-lag-measurements.csv).

![All lag observations](figures/20231018-lag-distributions.png)

## Measurements

863 archived candidates were read. Their original coverage labels reconcile as 59 served by the October 17 UTC tape, 793 by October 18, and 11 seam exclusions. The primary figures use the original 852; the archived full-session group source additionally supplies paths for all 11, retained in the tables as a supplement. 583,688 completed groups were checked against 771,787 raw records using cursor, receive clock and F_LAST. All 863 strict-prebirth quote operands and recognition quote/clock checks agree with the saved candidate file.

There are two matched controls per candidate, 1,726 total and 1,532 distinct anchors. Matching uses the same archived session, positive spread bucket (one, two, or at least three ticks), and trailing-60-second trade-count quintile. Activity quintiles are computed within each spread regime, with deterministic seed 1401. Control anchors inside any candidate's requested interval are excluded; their wider windows can still overlap other windows. Control reuse and overlapping events preclude treating rows as independent trials. Calendar times are join coordinates only.

Paths use integer-second observations from minus 60 to recognition and the exact recognition endpoint. At offsets through zero, the cutoff is one nanosecond before the boundary. Quote levels are the last completed group at the cutoff. Action quantities are summed over successive cutoff intervals using the containing group close; adds, cancels, fills, modify message sizes, and wire-side trade lots are separate columns. Fills and linked cancel messages are not additive independent executed volume. The first interval has one extra second of source prehistory. Signed ratio uses only completed full-second bins; no rescaling or smoothing is applied. Full exact raw records for an earliest case of each observed SAME/FLIP and in/against/flat alternative, plus its two controls, are retained with tape day, record index, cursor, integer receive time and order ID.

All 863 birth-to-recognition quote paths include 382 in the birth direction, 278 against, and 203 flat. These are the expanded full-session-source denominator; the original 852 remains the chart denominator. The saved member table retains each orientation and each alternative without averaging.

Part 1B recovers the source rule: a trailing finite-observation 85th percentile, 900-second and 600-finite-observation warmup, a plus/minus-five-second local maximum of absolute signed ratio, and prominence equal to magnitude minus the original baseline median over birth minus 30 through minus 10. Qualified peaks compete in a 45-second window. The highest prominence wins, with magnitude as tie-break and earliest observation retained for a complete tie. Availability is window-open plus 50 seconds. The winner enforces a 45-second refractory interval. These are recovered detector parameters, not research admission thresholds. Existing baseline/threshold calculations are reproduced solely to audit the detector; research paths are never smoothed.

Completed-group flow produces 866 births: 842 matching, 21 missed and 24 added; 840 matching births have identical nominal emission timing. The reconstructed Native action-time flow produces exactly 863 births, no misses/additions, 863 identical nominal times, and 863 identical actual recognition clocks. Baseline, threshold, prominence, magnitude, finite observation count and searched span each reconcile on all 863 (floating operands checked at absolute 1e-12 numerical tolerance). All 583,687 usable raw group books match saved quote levels and sizes; the initial incomplete book remains outside that quote check. Independent plateau, quiet and variable-stream fixtures produce the same 27/24/35 outputs as the pinned source detector, including operands and clocks.

For all 863, nominal lag equals 50 minus the winner offset from window-open. The offset ranges from 0 to 44 seconds, so nominal lag ranges from 6 to 50 seconds; median 50. Dispatch from nominal second to actual recognition ranges from 1.000046 to 87.367894 seconds, median 2.406826. Recognition from birth ranges from 7.059875 to 137.367894 seconds, median 51.673379. The recognition clock is exactly the first group close whose containing second is later than the nominal emission second. Thus the nominal lag is window-defined with a variable winning position, and the remaining lag is the observed group-arrival wait.

## Interpretation

SPECULATIVE: These descriptive paths can distinguish quote relocation, changing displayed size and incoming trades. They cannot identify participant intent. The two control selections characterize control-choice variation only. No family, input or target is removed.

## Handoff

Part 1B, Part 2 and Part 3 are still running. Questions raised so far: how much of the path contrast depends on a control anchor being a wall-clock cutoff versus a group close, and how often are recognition endpoints reached only after a trade-free interval?
