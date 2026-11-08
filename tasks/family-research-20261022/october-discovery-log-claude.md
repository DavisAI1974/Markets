# October NG discovery: Claude pass (four days, 2026-11-08)

Own file, to be merged with the Codex and Claude Code logs later. Not part of the shared
october-discovery-log.md. Branch: codex/ng-shadow-discovery-20261108, started from 5724f40.
Code and tables: tasks/family-research-20261022/claude-pass/ (scripts c00-c26; tables in tables/<date>/, tables/crossday/, tables/dipole/, tables/crosswalk/; figures/; claude-pass-tables-20261108.xlsx).
Sections A-C, E-H below are the original Oct 18 record and were computed on the pooled grid; sections I-M are the four-day regime-split work and supersede D.

## Status

| Item | State |
| --- | --- |
| Oct 18 (NGX3, instrument 150611), one UTC member | analysed: Tier 1 (749 families), Tier 2 (dense grid, 28,380 rows) |
| Oct 2, 3, 17 | run from the tapes (single UTC-day members, SHA-256 checked): regime-split conditions-only scan, state cells, lead-lag (sections I-K) |
| Dipole cohort (863 candidates) | run on Oct 17 evening and Oct 18 tapes: 852 covered, 11 in the seam (section L) |
| 99-plane / 13-input crosswalk | run (section M). Inputs are bound for Oct 18 only, so no cross-day comparison exists for them |
| ROOT/Native/standalone output index for Oct 2/3/17 | not built; not re-checked for newer publications |
| Prefix members (evening members of the Oct 2 and Oct 17 sessions) | published on the branch (data commit b9ed761, UTC days 2023-10-01 and 2023-10-16; Claude Code cited 603c4def). Not used in this pass: my four days are single UTC members (see Caveats) |
| Disagreements with Codex | recorded in L and M where compared line by line; earlier Codex conclusions outside those tables not yet compared |

## Conventions that hold for every number below

- Only market conditions enter the math. Trade ids, cursors, timestamps, day of week and clock
  buckets are provenance only. c14 asserts that no identity or clock column is in the input set.
- Activity quintile (trailing trade count, quote changes) replaces clock-bucket normalisation.
  Stability is read from 24 contiguous chronological chunks (count of chunks with the same sign).
- Groups close at an F_LAST record and are known at that record's ts_recv. Pre-event windows end
  at start_recv_ns - 1. Outcomes are last-group-known midpoint changes at +h, in ticks (0.001).
- Trade side is wire-only (A = seller hit bids, B = buyer lifted asks). Side-N lots are kept apart.
- No trade cost anywhere. Nothing pooled across spread regimes in new work from here on.
- Neighbouring windows overlap heavily; naive p-values are not used. Sections A-H are one date, so
  day-level drift is mixed into them; sections I-K use the day as the unit of independence.
- Trials examined: 2,635 condition/outcome pairs in the conditions scan (plus the pair, state and
  stack passes listed below). Of the 2,635, 259 exceed the circular-shift 95% line (exceeds_null95).

## A. One-second states: last move x touch lean x net flow (t2_state_cells.csv, 44 rows)

Outcome: net share (up - down)/support of the next 1 s, with the circular-shift null mean beside it.

| Last move | Touch lean | Support | up / flat / down | Net share | z | Chunks agreeing |
| --- | --- | --- | --- | --- | --- | --- |
| flat | bid-heavy, no flow | 20,034 | 1,038 / 18,494 / 502 | +0.027 | +16.5 | 21 of 24 |
| flat | ask-heavy, no flow | 20,504 | 542 / 18,786 / 1,176 | -0.031 | -16.1 | 23 of 23 |
| down | bid-heavy, sell flow | 960 | 173 / 717 / 70 | +0.107 | +11.5 | 14 of 19 |
| down | ask-heavy, sell flow | 567 | 58 / 401 / 108 | -0.088 | -6.5 | 12 of 15 |
| up | bid-heavy, buy flow | 621 | 121 / 447 / 53 | +0.110 | +8.9 | 15 of 17 |
| up | ask-heavy, buy flow | 860 | 64 / 634 / 162 | -0.114 | -10.6 | 14 of 18 |

Observed: in every move state the next-second sign follows the touch lean. A lean against the last
move gives a reversal, a lean with it gives continuation. Magnitude after a move is about 3-4x the
flat-state value.

## B. Conditions that couple to outcomes (t2_coupling_conditions.csv, 2,635 rows)

| Outcome | Conditions above the null line (rho) | Chunks agreeing |
| --- | --- | --- |
| midpoint change 5 s / 20 s | touch order-count imbalance +0.125 / +0.118; touch size imbalance +0.116 / +0.118 | 23 of 24 |
| midpoint change 60 s | none above the null line | n/a |
| absolute move 20 s | 300 s quote churn +0.255; 60 s cancel/add counts +0.13 to +0.15 | 22-23 of 24 |
| spread change 5 s | current spread -0.345; order counts at touch -0.19/-0.20; touch sizes -0.17/-0.18 | 23 of 24 |
| net flow 5 s; support difference 5 s | none above the null line | n/a |

Interaction (t2_pair_couplings_top60.csv): for the 5 s spread change, touch size imbalance x touch
order-count imbalance, partial rho +0.125 (23 of 24 chunks). Effect of size imbalance is -0.096
when order-count imbalance is low and +0.101 when high (sign flip).

## C. Forward-selection stack, out-of-fold correlation (t2_forward_stack.csv)

| Outcome | Step 1 | Last step | Picks in order |
| --- | --- | --- | --- |
| midpoint 5 s | 0.080 | 0.096 | tchn_imb, prior_5, supdiff_1, modT_b_60, addT_b_5, prior_1 |
| midpoint 20 s | 0.063 | 0.092 | tchn_imb, modT_b_60, cxF_a_60, spr, prior_5, addT_b_5 |
| midpoint 60 s | 0.058 | 0.097 | modT_b_60, tchn_imb, qchg_60, cxT_b_60, prior_300, modT_a_60 |
| spread change 5 s | 0.359 | 0.433 | spr, bn, an |
| net flow 5 s | 0.030 | 0.049 | bsz_per_ord, cxT_b_5, cxT_b_20, addT_a_5, prior_300 |

Each added condition adds 0.002-0.02. Column names are defined in c04_order_features.py.

## D. Spread regime split (superseded by section I; see the disclosure there)

Spread 1 tick 13,616 rows, 2 ticks 13,061, 3+ ticks 1,703 (sum 28,380). Spearman of percentile
ranks within activity quintile.

| Spread | condition | rho 5 s | rho 20 s |
| --- | --- | --- | --- |
| 1 tick | touch order-count imbalance | +0.121 | +0.093 |
| 2 ticks | touch order-count imbalance | +0.088 | +0.126 |
| 3+ ticks | touch order-count imbalance | +0.061 | +0.175 |

Chunks positive at 5 s: 1 tick 23 of 24, 2 ticks 21 of 24. The coupling shifts horizon with spread.
The primer expects collapse in multi-tick books; that is not what this day shows.
(Run inline; the numbers in this table could not be reproduced from the scripts. c19 replaced it; use section I.)

## E. Original 50-case stack and its flow-flipped version (t1_oriented_to_5s_flow.csv)

Full-depth imbalance has one sign all day on Oct 18, so the original selection came entirely from
the flow pattern. The strict inverse stack has zero support; the flow-flipped version has 45 cases.

| Flow pattern | h | n | with 5 s flow | flat | against | median ticks in flow direction |
| --- | --- | --- | --- | --- | --- | --- |
| original 60+/5-/1- | 5 s | 50 | 23 | 3 | 24 | 0.0 |
| original | 300 s | 50 | 33 | 1 | 16 | +2.5 |
| flipped 60-/5+/1+ | 5 s | 45 | 20 | 10 | 15 | 0.0 |
| flipped | 300 s | 45 | 17 | 3 | 25 | -1.0 |

## F. Four arms on the same families (t1_fourarm_summary.csv, t1_fourarm_by_block.csv)

749 families, 600 test rows at h <= 60 s (596 at 300 s), expanding chronological folds with outcome
purge. MSE relative to a zero-change guess; bracket = fraction of circular-shift null runs at or
below the observed MSE.

| h | baseline | +flow | +book | +both |
| --- | --- | --- | --- | --- |
| 1 s | 1.022 (0.43) | 0.999 (0.02) | 1.014 (0.17) | 1.010 (0.07) |
| 5 s | 1.041 (0.63) | 1.023 (0.43) | 1.006 (0.06) | 1.095 (0.80) |
| 20 s | 1.076 (0.74) | 0.997 (0.00) | 1.004 (0.08) | 0.986 (0.01) |
| 60 s | 1.033 (0.68) | 1.001 (0.13) | 1.002 (0.10) | 1.001 (0.05) |
| 300 s | 1.020 (0.29) | 1.052 (0.56) | 1.024 (0.30) | 1.031 (0.31) |

Open: on the 694 in-member subset (order-level book features available) every arm including the
baseline sits at 0.90-0.98 of the null for h = 1 to 20 s. Not resolved whether the null is
comparable there. No conclusion drawn from that subset at short horizons. At 300 s on that subset
+both is 0.988 (0.00).

## G. Bid refill before the event (t1_refill_by_fill_stratum.csv; operands kept in the table)

Refill ratio = (bid adds at/near touch) / (bid fill lots).

| Fill stratum | ratio group | n | down/flat/up at 5 s | down/flat/up at 300 s |
| --- | --- | --- | --- | --- |
| small fills | >= median | 67 | 20 / 14 / 33 | 37 / 3 / 27 |
| small fills | < median | 65 | 37 / 5 / 23 | 35 / 3 / 27 |
| large fills | >= median | 66 | 33 / 12 / 21 | 23 / 2 / 40 |
| large fills | < median | 65 | 39 / 9 / 17 | 32 / 4 / 29 |

## H. One-second lead-lag (t2_leadlag_matrix.csv)

| Pair | lag 0 rho | note |
| --- | --- | --- |
| net flow, midpoint change | +0.509 | contemporaneous |
| bid support change, midpoint change | +0.573 | contemporaneous |
| bid support change, ask support change | -0.462 | contemporaneous |
| midpoint change, touch imbalance | -0.109 | lag +1: -0.072, lag -1: +0.100 |
| quote churn, touch imbalance | -0.029 | peak at +/-9 s |

Off-zero values are 0.05 or smaller except the midpoint/touch-imbalance pair. Lag-sign convention
for that pair not yet checked; direction not interpreted.

## I. Four-day regime-split scan (c19, c20; tables/<date>/t3_regime_coupling.csv, tables/crossday/t4_crossday_*.csv)

Pipeline now takes a date label (c00 decode, c03 reconstruction, c01b groups, c12 grid, c19 scan). Legacy mode
reproduces the committed Oct 18 c14, c16 and c17 tables exactly. Grid decision every 3 s, as-of conditions, forward
outcomes. Regimes by spread at the cutoff: 1 tick, 2 ticks, 3+ ticks (almost entirely 3 ticks). Nothing is pooled across
regimes. Activity quintiles are computed inside the regime. Closed market is data-defined (a gap of at least 1,800 s between
group closes through the first trade print plus 600 s), 21:00:03-22:10:00 UTC on all four dates; locked or crossed rows are
excluded. Row reconciliation is asserted per day: regimes + closed + settle + locked/crossed = grid rows (28,380 on each day;
closed 1,400 to 1,401 rows; locked or crossed 0 after the closed rule).

| Day | rows 1 tick | rows 2 ticks | rows 3+ ticks |
| --- | ---: | ---: | ---: |
| Oct 2 | 15,276 | 10,700 | 1,004 |
| Oct 3 | 16,092 | 10,176 | 712 |
| Oct 17 | 13,374 | 13,050 | 555 |
| Oct 18 | 13,547 | 12,938 | 495 |

Trials: 2,652 condition/outcome pairs per regime-day at 1 and 2 ticks (156 conditions x 17 outcomes on Oct 18 at 1 tick; counts per regime-day are in the receipts). In the 3+ regime a condition with fewer
than 100 usable rows has no defined correlation and is left out, never reported as 0: 2,499 defined on Oct 2 and 3, 2,499 on
Oct 17, 2,397 on Oct 18 (pairs_undefined in the receipts). Reference line per regime-day: outcomes cyclically shifted inside the
regime, 300 shifts, family-wise 95% line of max |rho| (0.104 to 0.177 at 1 and 2 ticks, 0.317 to 0.506 at 3+).

**Cross-day agreement** (pairs defined on all four days; days sharing the majority sign, against 20 draws in which each day's
outcome is replaced by a shifted version):

| Regime | pairs | same sign 4 of 4 | shifted-outcome 4 of 4 (mean, min-max) | 3 of 4 | 2 of 4 |
| --- | ---: | ---: | --- | ---: | ---: |
| 1 tick | 2,652 | 1,329 | 509.6 (434-658) | 828 | 495 |
| 2 ticks | 2,652 | 1,337 | 427.2 (318-571) | 828 | 487 |
| 3+ ticks | 2,397 | 755 | 324.2 (175-453) | 1,060 | 582 |

The observed 4-of-4 counts sit above every shifted draw in all three regimes. Of the pairs agreeing on all four days, the
minimum |rho| across days has median 0.022 (1 tick), 0.037 (2 ticks), 0.028 (3+) and maximum 0.209, 0.188, 0.192; in the shifted
draws the median is 0.004, 0.003, 0.010. Pairs beyond the day's own 95% line on all four days: 137 at 1 tick, 48 at 2 ticks, 0 at 3+
(on at least three days: 184, 209, 0). The leading repeating pairs are in the book response and flow families (top-repeating
sheet, crossday-top-by-family-heatmap.png). The settle-window sensitivity run (nosettle files) is saved alongside.

Figures: crossday-rho-distributions.png, crossday-agreement-vs-shifted.png, crossday-rho-scatter.png,
crossday-top-repeating-heatmap.png, crossday-top-by-family-heatmap.png. Plotted counts reconcile to table rows
(figures/t5_chart_reconciliation.csv).

**Disclosure.** The section D table above was computed inline on the pooled grid and its numbers are not reproduced by any script;
the original c14 outputs for the four dates also included closed-market rows and about 3,380 stale Oct 18 outcomes in the old
3+ bucket. The regime-split tables replace them. The primer expectation of collapse in multi-tick books is treated as a guess:
the 3+ regime here is 495 to 1,004 rows per day and has the least support.

## J. State cells by regime and day (c22; tables/crossday/t4_state_crossday.csv)

Last move x touch lean x net flow cells (section A definition) split by regime, support at least 100, K = 12 chunks. Cells with
the same sign of net next-second direction on all four days: 16 at 1 tick, 12 at 2 ticks, 0 at 3+. Next 5 s: 16, 9 and 0.
The 3+ regime has 3 cells defined on all four days next-second and none agreeing on four. Figures: crossday-state-cells-next1s.png,
next5s.png. The Oct 18 touch-lean sign pattern of section A therefore repeats at 1 and 2 ticks on the other three days.

## K. Lead-lag by regime and day (c22; tables/crossday/t4_leadlag_crossday.csv)

Same-sign counts over four days for the lead-lag rank correlations (series pair x lag): 1 tick 45 of 99 on all four days, 2 ticks 43 of 99,
3+ ticks 23 of 99 (3 of 4 days: 35, 38, 53). Figure: crossday-leadlag-heatmap.png. No lead is interpreted here.

## L. Dipole cohort (c24a-c24d; tables/dipole/, figures dipole-cohort-*.png)

**What the candidate file is.** The 863 archived Native candidates (472 SAME, 390 FLIP, 1 without predecessor by Codex's
orientation labels; 862 with a predecessor). The S92 dip_imb_level nowcast is a different object (not used here). The candidate
birth is retrospective: median 50 s from birth second to the nominal emission second (min 6, max 50) and a further median 2.407 s
(max 87.4 s) to recognition; birth start to recognition median 51.7 s (max 137.4 s). A strict prebirth cutoff therefore precedes
the moment the candidate was visible by about a minute, and features at that cutoff stay retrospective stratifiers.
Codex's member runs 2023-10-17 22:00 UTC to 2023-10-18 21:00 UTC; my tapes are UTC days, so 59 candidates are served by the Oct 17
tape, 793 by the Oct 18 tape, and 11 fall in the 23:50 to 00:10 UTC seam where neither tape holds the whole window (863 = 59 + 793 + 11).
All 863 Codex prebirth quotes match my reconstructed books on bid and ask price and size and on receive time.

**Method.** Features at the strict prebirth cutoff (birth second start minus 1 ns) and at the recognition clock come from the
same code as the dense grid. Outcomes oriented by birth polarity (a recognition-time label), in ticks: birth-to-recognition move
(retrospective) and forward +1, 5, 20, 60 s from the recognition close. Controls: 500 draws of matched rows (same tape, spread
regime and activity quintile; 3 s grid rows for the retrospective move, random group closes for forward moves because a recognition
is itself a group close with snapshot age 0). Ids and timestamps place the cutoffs and join to Codex's tables, nothing else.

**Agreement with Codex, line by line (covered 852 of 863).** Birth-to-recognition direction label 852 of 852; prebirth displayed
depth label 852 of 852; forward direction at +1 and +5 s 852 of 852, at +20 and +60 s 851 of 851 available. The 11 uncovered
candidates account for the differences from Codex's published cell counts (for example flow-opposite 217 vs 216, same 275 vs 271,
undefined 345 vs 339). Both passes read the same tapes, so this agreement confirms the reconstruction and not an independent
finding. Flow definitions differ and are kept apart: my wire-side aggressor lots over a trailing 20 s ending at the recognition
close versus Codex's price-versus-prior-midpoint classes over completed one-second bins. Against Codex's classes the two agree on
249 same-as-birth and 196 opposite cases; 87 candidates fall off the diagonal and 320 have no classified flow under either (t6_flow_definition_crosstab.csv). In the
four narrated cases my 20 s lots at recognition match Codex's exactly in one (14 buy, 39 sell) and are one lot higher on each side in
another (5 and 26 against 4 and 25), consistent with the window ending at the recognition close.

**Cohort result (852 covered).** Midpoint moved in the birth direction / against / flat:

| Interval | in | against | flat | matched controls: in, median (2.5-97.5%) |
| --- | ---: | ---: | ---: | --- |
| birth to recognition | 378 (44.4%) | 275 (32.3%) | 199 (23.4%) | 34.9% (31.6-37.9) |
| +1 s after recognition | 96 (11.3%) | 94 (11.0%) | 662 (77.7%) | 19.2% (16.8-22.0) |
| +5 s | 148 (17.4%) | 166 (19.5%) | 538 (63.1%) | 25.7% (22.9-28.9) |
| +20 s | 257 (30.2%) | 245 (28.8%) | 350 (41.1%) | 34.7% (31.6-38.3) |
| +60 s | 335 (39.3%) | 334 (39.2%) | 183 (21.5%) | 40.6% (37.4-43.8) |

Between birth and recognition the midpoint moved in the birth direction more often than in the matched draws (cohort share above
all 500 draws), and flat less often. After recognition, in-direction and against shares are about equal at every horizon, and
both are below the matched draws at +1 and +5 s (cohort above none of the 500 draws) and the in-direction share is above 1 of 500 at +20 s; the cohort sits inside the draw range for in-direction at +60 s.
Mean oriented move after recognition: -0.011, -0.026, -0.071, -0.082 ticks at +1, 5, 20, 60 s. Regime splits (1 tick 455 and 2 ticks 381 at
prebirth; 3+ ticks 16) are in t6_cohort_controls.csv; the 3+ cell is too small to read. The nominal-clock version (from the emission
second) is in t6_cohort_cells.csv (nom columns) beside the recognition-clock version; its horizons start before the candidate was recognized.

**Cells (denominators in every share; alternatives and inverse paths kept).**
- Recent flow at recognition (Codex class) x midpoint in birth direction by recognition: same 153 of 271 (against 65, flat 53); opposite 56 of 216 (against 126, flat 34);
  balanced 12 of 26; none classified 157 of 339. This reproduces the log's 155/65/55, 56/127/34, 12/13/1, 159/73/113 up to the 11 uncovered.
- Prebirth displayed depth versus birth direction, in-direction by recognition: aligned 219 of 413 (53.0%), opposed 123 of 335 (36.7%), equal 36 of 104 (34.6%).
  After recognition the aligned/opposed difference is not visible at +5 s (82/68/263 against 50/80/205 in/against/flat) and is
  smaller at +20 s (129/115 against 96/106).
- SAME against FLIP orientation: retro in-direction 211 of 462 against 167 of 389; +20 s 135/142 against 122/103.
- Prebirth sign relative to the later birth direction (retrospective): 20 s flow toward birth 455, against 78, zero 35 of 568 defined;
  60 s flow 423/216/42 of 681; displayed touch lean 413/335/104 of 852; 20 s net book support 484/268/100; 20 s prior displacement
  323/145/384. Same-regime grid expectation under a symmetric split is shown in dipole-cohort-signed-conditions.png.
- Recognition delay thirds: retro in-direction 118, 128, 132 of 284 each; against 105, 100, 70.

**Cases with source coordinates (t6_cohort_cases.csv, t6_cohort_case_paths.csv).** Tape day label, record index range in my
reconstruction, receive times and Codex's cursors are in the table. Re-traced independently:
- Case 1 (birth 1697581215, Oct 17 tape, records 844867 to 845012): midpoint back at its start (0.0 ticks); Codex cursors 3266 to 3411.
- Case 2 (1697583021, records 849212 to 849327): ask 3.067 to 3.068 after 3 buy lots traded, bid held at 3.066 (log narrative reproduced); +0.5 tick.
- Case 3 (1697625921, Oct 18 tape, records 123391 to 123772): 14 buy and 39 sell lots in the 20 s at recognition, bid 3.085 to 3.086, midpoint +0.5 tick.
- Case 4 (1697607905, records 33504 to 33885): both sides lower at recognition (bid 3.074 to 3.069, ask 3.076 to 3.072), -4.5 ticks in birth direction; my lots 5 buy and 26 sell.
- Cases 5 to 8: typical members (lower-median oriented move, ties to earliest) of four cells: opposite recent flow with midpoint in the birth direction; same-direction flow with midpoint against; aligned depth with midpoint against; in the birth direction by recognition then against by +20 s.
The aggregate and the cases pair: the cohort shows how often each path occurs; each case shows one order-level path, not the rest.

Figures: dipole-cohort-vs-controls.png, dipole-cohort-cells.png, dipole-cohort-signed-conditions.png.

## M. 99-plane and 13-input crosswalk (c25, c25b; tables/crosswalk/)

**99 planes.** My class from the registry's own fields (group, role, class), written before comparing: 75 of 99 match Codex's relationship class
(agreed counts: market mechanism or state 23, derived transform 17, availability 7, control 24, outcome 4). The 24 differences all
have one source: I let the registry's piece disposition decide (an entry not read, sealed or withheld by this piece is control or boundary),
Codex let the entry's semantic role decide (the learned structures and raw-source entries are derived transforms or market records
even when not read). Nine learned-structure entries, five raw-tape entries and five sealed step1 entries make most of it (t7_plane_roles.csv,
t7_plane_class_crosstab.csv). Neither mapping is a numerical or semantic admission.

**13 inputs, on the 749 Oct 18 families.** 93 series; 70 are constant across the 749 families and 23 vary at all. Within the day:
- Points 1, 3, 4, 6, 8, 11, 12 are constant: no coupling, sign or lead/lag can be measured on one day.
- The weather series (points 2, 9, 10) and the settled curve shape have 2 to 5 distinct values (1 to 4 steps); series sharing step positions give identical
  correlations (0.173 four times, 0.637 twice), so they measure where a step falls in the day. Their correlation with family order
  is up to 0.84, with the traded mid up to 0.79.
- Point 13 traded-curve slope and curvature series track the traded instrument: |rho| with the traded mid 0.52 to 0.96 (shared front-contract leg).
- Wind (point 5) rank correlation with the traded mid 0.59; gas burn (point 7) -0.10; wind against gas burn -0.02 (same EIA table, no shared variation).
- Largest |rho| with a saved strict-pre outcome among the 23 varying series: 0.26 (absolute 20 s move, point 13 slope_back); the family-wise
  shifted-outcome 95% line is 0.34. Chunk stability and the full table are in t7_input_series_measurements.csv; heatmap crosswalk-input-series-heatmap.png.

**Relationship labels (my reading; proposals).** Shared input: points 1, 3, 4 (one weekly report), 9 with 2 (same model runs), 5 with 7 (same table), 11 with 12, 13 with the
traded instrument. Alternative measurement: 8 (ICE LD1 positioning against 1, 3, 4), 10 (observed against forecast weather), 13 (price level and term structure).
Plausible market transmission: 2, 7, 11. Context: 5, 6. No input is an outcome; 12 is a derived estimate-versus-actual built on 11. Against Codex's labels the shared-source flag
agrees for 11 of 13; I flag 11 and 12 as sharing a source and Codex does not. Closest registry entries are proposed analogies (price_and_book_path,
contract_session_roll_state for 13; aggressor_and_native_signed_flow for the positioning points); the tests above are what could be run on one day.

## Caveats on days

- My Oct 2, 3, 17 and 18 members are single UTC days. The branch now holds prefix members (the preceding evening, data commit b9ed761 for Oct 2 and Oct 17; Claude Code cited 603c4def) that add the
  22:00-24:00 UTC hours; this pass did not use them, and the Codex and Claude Code logs carry full-session Oct 17 results that this log does not reconcile with. Day counts from a prefix-complete run will differ from mine by those evening hours
  (65 events on Oct 17 per Claude Code). My dipole cohort already uses the Oct 17 tape for the evening births.
- Reserved exchange states (velocity or stop logic) are not observable in the mbo schema; only the closed-market and settle-window handling applies.

## Layers kept apart

| Layer | Content |
| --- | --- |
| Observed mechanics | A (touch lean sign and next-second sign), reconciliation of order-level lots to retained ROOT operands for 654 of 656 comparable families, 100% touch match at 569,063 group closes |
| Associations | B, C, G, H (Oct 18 only), I, J, K (four days), L cohort comparison, M crosswalk correlations |
| Hypotheses (speculative) | (1) Inventory-constrained liquidity providers re-centering quotes after a move would give reversal when the touch leans against it; (2) continuation when the touch leans with the move is the queue-depletion race in the primer. Distinguishing evidence: whether cancelled ids re-appear at new prices (re-centering), and whether the same-lean effect scales with queue size at the touch (depletion race). Neither tested |
| Unknowns | Owner of orders; 3+ tick regime (little support); the 694-subset null question in F; whether the dipole path differences are mechanisms or selection; external inputs on any day but Oct 18 |

## Handoff for the next session

0. Direction from Greg (2026-11-08): prebirth being retrospective is acceptable; reverse-engineer the Native dipoles from the birth point.
   (a) Birth-aligned event study of the 852 covered candidates: book and flow paths from about 60 s before the birth second through recognition
   (quote levels, touch sizes, adds/cancels/fills by side, aggressor lots), each against matched controls aligned the same way (same tape, spread regime,
   activity quintile). Descriptive of how births arise, not a forecast: birth is visible about 50 s later. Keep SAME/FLIP and the alternative paths, and pair each
   cohort result with a traced case and its source coordinates. Start from c24a-c24d (cuts, features, controls, cases) and tables/dipole/.
   (b) Recover the detector rule: use the recorded operands in october18-candidate-inputs.jsonl.gz (baseline, threshold, prominence, magnitude,
   observations_behind_threshold, searched_span_seconds, window_truncated) and research-atlas-v2/dipole-completed-group-flow.csv.gz (20 s signed ratio by second)
   to test whether one rule reproduces all 863 births and their timing, including the 6 to 50 s birth-to-emission gap; list births it misses or adds.
   Ids, cursors and timestamps stay provenance; no thresholds or verdicts unless asked.
1. Re-run with the published prefix members (Oct 2 and 17 evenings, data commit b9ed761; check Oct 3 and 18) and compare regime-row counts and cross-day agreement with the single-UTC-day numbers here; then reconcile with the full-session Oct 17 sections in the Codex and Claude Code logs.
2. ROOT/Native/standalone output index for Oct 2/3/17: re-fetch the branch and map what has published; then run the dipole cohort on those days if candidates exist.
3. Run c15 (pairs) and c18 (forward stack) per regime; they are date-parameterised but unrun on the four-day data.
4. Dipole: record-level paths for the remaining cells beyond the eight cases; test whether the below-control move rate after recognition holds at group closes matched on flow state.
5. Crosswalk: bind external inputs for Oct 2, 3 and 17 so signs can be compared across days; until then the 13 inputs are one-day, mostly constant or stepped.
6. Large derived parquet and npz files live in the work directory and are regenerated by c00, c03, c01b, c12; nothing large is committed.
7. Nothing has been committed or pushed from this pass.
