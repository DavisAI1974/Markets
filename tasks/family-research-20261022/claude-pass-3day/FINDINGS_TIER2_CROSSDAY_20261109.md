# The Oct 18 Tier 2 suite on Oct 2, Oct 3 and Oct 17, side by side with Oct 18

Written 2026-11-09. Branch `claude/three-day-dipole-20261108`, folder `claude-pass-3day/`. This completes the part of the Oct 18 suite that was run on
all four days but never compared (handoff section 3B): the condition/outcome couplings (c14), pair couplings (c15), one-second lead-lag (c16), one-second
state cells (c17) and the forward-selection stack (c18). Every row below is one pair, one cell, one series pair or one selection step with the four days'
values beside each other. Nothing is averaged across days; counts of days are counts. Days are column labels only. No trade cost anywhere.

Tables: `crossday/t2x_*.csv` (written by `x14_tier2_crossday.py`). Figures: `crossday/t2x-*.png` (written by `x15_tier2_crossday_charts.py`; every plotted
count is asserted equal to its table rows, `crossday/t2x_chart_reconciliation.csv`, 28 of 28 match). Reference draws: `x16_tier2_shift_draws.py`. Full
pair family: `x17_pair_couplings_full.py` -> `crossday/pairs_full/`.

## 1. Inputs and the replication check

| Input | Oct 2 | Oct 3 | Oct 17 | Oct 18 | Source |
| --- | --- | --- | --- | --- | --- |
| grid rows after closed-market rows out | 26,980 | 26,980 | 26,979 | 26,980 | c12 grid, UTC member, one decision every 3 s |
| condition/outcome pairs (157 x 17) | 2,669 | 2,669 | 2,669 | 2,669 | `tables/<day>/t2_coupling_conditions.csv` |
| per-day shifted-Y 95% line, |rho| | 0.1094 | 0.0921 | 0.1445 | 0.1134 | c14 (300 shifts, family-wise) |
| pairs beyond the day's own line | 285 | 346 | 103 | 199 | same |
| lead-lag series pairs (7 x 7) | 49 | 49 | 49 | 49 | `t2_leadlag_matrix.csv` |
| state cells x horizons | 42 | 42 | 42 | 42 | `t2_state_cells.csv` |
| pair-coupling rows (x17, full family) | 5,406 | 5,418 | 5,166 | 5,166 | `crossday/pairs_full/` |
| forward-stack steps, 7 outcomes | 30 | 38 | 27 | 31 | `t2_forward_stack.csv` |

Replication: the four UTC tapes (sha256 equal to the markets-data `MANIFEST.json`) were decoded and the grids rebuilt in this session (c00 -> c03 -> c01b
-> c12, unchanged code). Re-running c14, c16, c17 and c18 from the rebuilt grids reproduces the committed tables: lead-lag, state cells and forward
stack byte-identical; coupling rho equal to 1.1e-16 with identical n, chunk counts and line flags on every row of every day. x17 reproduces every c15
top-400 row (max difference 9.7e-17).

Why the Oct 18 tables here (2,669 pairs, 42 cells) differ in row count from the original Oct 18 run in `claude-pass/tables/` (2,635 pairs, 44 cells;
identical to `claude-pass/tables/20231018_legacy/`): the original ran in the scripts' legacy mode, which builds the grid from the retained export's groups,
flags no closed-market rows (28,380 grid rows against 26,980 after the 1,400 closed-market rows are left out) and keeps the snapshot-age conditions
`age_s` and `qage_s` out of X (155 conditions against 157; 155 x 17 = 2,635, 157 x 17 = 2,669). In the one-second tables the closed-market seconds are
likewise left out of the dense run, which takes the `down|ask-heavy|none` cell below the 100-second floor at both horizons (44 cells against 42). On
the 2,635 shared pairs the two Oct 18 runs agree in sign on 96 percent, largest |rho| difference 0.067. The four-day comparison uses the dense run on
every day, so the days are like for like.

## 2. Condition/outcome couplings (c14), 2,669 pairs on all four days

Counts of pairs by how many days share the majority sign, observed against the same pairs with Y cyclically shifted on each day (20 draws, draw s combining
the s-th shifted matrix of each day; `t2x_coupling_shifted_reference.csv`):

| | 2 of 4 days | 3 of 4 | 4 of 4 | 4 of 4 with |rho| beyond every day's line |
| --- | --- | --- | --- | --- |
| observed | 485 | 854 | 1,330 | 99 |
| Y shifted, mean (min to max of 20 draws) | 904 (793 to 1,037) | 1,274 (1,149 to 1,385) | 491 (372 to 633) | 0 (0 to 0) |

Smallest |rho| across the four days among the 4-of-4 pairs: median 0.022, 90th percentile 0.120, largest 0.333 (observed); 0.003, 0.014, 0.040 under
the shifted draws (means over draws). Days on which a pair is beyond its own line: 0 days 2,311 pairs, 1 day 78, 2 days 84, 3 days 97, 4 days 99
(shifted: 0 days 2,664 to 2,669, 1 day 0 to 5, never 2 or more).

By outcome family (counts of pairs):

| family | pairs | same sign 4 of 4 | 3 of 4 | 2 of 4 | beyond line on 4 days | on 0 days |
| --- | --- | --- | --- | --- | --- | --- |
| book response (F_sup, F_cx, F_add, 5 s) | 942 | 675 | 201 | 66 | 93 | 619 |
| magnitude (am_5, am_20) | 314 | 219 | 45 | 50 | 1 | 305 |
| quote response (dbid_5, dask_5, dspr_5) | 471 | 190 | 181 | 100 | 5 | 455 |
| flow persistence (F_net_5, F_net_20) | 314 | 89 | 128 | 97 | 0 | 314 |
| signed move (dm_1, dm_5, dm_20, dm_60) | 628 | 157 | 299 | 172 | 0 | 618 |

The 99 pairs beyond every day's line are 93 book-response, 5 quote-response (spr -> dspr_5, spr -> dask_5, spr -> dbid_5, an -> dspr_5, bn -> dspr_5)
and 1 magnitude (qchg_300 -> am_20). No signed-move or flow-persistence pair is beyond the line on more than 1 day (signed move: 4 pairs on 1 day, 1 on 2,
5 on 3; flow persistence: none).

Pairs with the same sign on all four days, per family, ranked by the smallest |rho| (figure `t2x-coupling-top-by-family.png`; top rows):

| family | pair | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
| --- | --- | --- | --- | --- | --- |
| signed move | tchn_imb -> dm_5 | +0.13 | +0.14 | +0.12 | +0.13 |
| signed move | tch_imb -> dm_5 | +0.12 | +0.12 | +0.11 | +0.12 |
| signed move | an -> dm_5 | -0.08 | -0.10 | -0.08 | -0.10 |
| magnitude | qchg_300 -> am_20 | +0.13 | +0.19 | +0.16 | +0.19 |
| magnitude | qage_s -> am_5 | -0.08 | -0.08 | -0.08 | -0.08 |
| quote response | spr -> dspr_5 | -0.34 | -0.33 | -0.35 | -0.37 |
| quote response | an -> dspr_5 | -0.16 | -0.18 | -0.19 | -0.20 |
| quote response | spr -> dbid_5 | +0.14 | +0.13 | +0.13 | +0.15 |
| flow persistence | tchn_imb -> F_net_5 | +0.04 | +0.06 | +0.03 | +0.06 |
| flow persistence | prior_300 -> F_net_20 | -0.02 | -0.02 | -0.05 | -0.08 |
| book response | addT_a_60 -> F_add_a_5 | +0.24 | +0.21 | +0.22 | +0.23 |
| book response | addT_b_60 -> F_cx_b_5 | +0.23 | +0.21 | +0.32 | +0.20 |

Where Oct 18 stands apart or another day does:
- Beyond the line on Oct 18 only (3 pairs, all magnitude, same sign on all four days): cxN_a_60 -> am_20 (+0.09, +0.08, +0.08, +0.12), addT_b_60 -> am_20
  (+0.06, +0.08, +0.11, +0.12), cxT_b_60 -> am_20 (+0.06, +0.09, +0.10, +0.13).
- Beyond the line on the other three days but not Oct 18 (3 pairs, book response, same sign on all four): addN_b_1 -> F_add_b_5, addT_b_1 -> F_add_b_5,
  cxN_b_5 -> F_add_a_5 (Oct 18 values +0.11, the line that day 0.113).
- The widest four-day ranges among 4-of-4 pairs are bid-side book pairs on Oct 17: age_s -> F_cx_b_5 (-0.15, -0.18, -0.30, -0.13), addT_b_20 -> F_cx_b_5
  (+0.20, +0.19, +0.31, +0.16), cxT_b_60 -> F_cx_b_5 (+0.21, +0.19, +0.31, +0.18); and na10 -> F_add_b_5 (+0.18, +0.14, +0.00, +0.14), where Oct 17 is
  the day at zero.
- The largest single-day |rho| among 2-of-4 pairs is 0.11 (near10_imb -> F_add_b_5 on Oct 17: -0.02, +0.02, -0.11, +0.04); none of the 2-of-4 pairs is
  beyond any day's line.
- Each other day shares Oct 18's sign on 1,330 pairs (all three days), 604 pairs (two of the three), 485 (one), 250 (none); shifted reference 491, 951,
  904, 324 (means).

## 3. Pair couplings (c15), interaction partial corr(y, z1*z2 | z1, z2)

Committed per-day tables hold each day's top 400 by |interaction|. The union over the four days is 1,102 triplets; 78 are in all four top-400 lists
(dspr_5 61, am_20 15, dm_5 2), 47 in three, 170 in two, 807 in one. In all four top-60 lists: 24 (dspr_5 23, am_20 1).

The full family (x17, every triplet, same code): 5,166 triplets on all four days (5,418 on Oct 2 and 3; 42 pairs with fewer than 3,000 usable rows are
skipped on Oct 17 and 18, as c15 skips them). Days sharing the majority sign: 2 of 4 1,416, 3 of 4 2,324, 4 of 4 1,426. Beyond the day's line (0.058,
0.067, 0.063, 0.065; 17, 14, 25, 10 rows per day): 4 days 9 rows, 3 days 2, 2 days 6, 1 day 8, 0 days 5,141. All 25 rows beyond a line on any day have
y = dspr_5; the 9 beyond every line are tch_imb x tchn_imb (+0.140, +0.145, +0.130, +0.126), tchn_imb x an, tch_imb x an, tch_imb x asz, spr x qchg_5,
bn x qchg_5, an x qchg_5, bsz x qchg_5, asz x qchg_5 (all negative on all four days, smallest |value| 0.063 to 0.082). By outcome, 4-of-4 counts of 861
rows each: dspr_5 356, am_20 308, dm_5 209, F_supdiff_5 200, F_net_5 185, dm_20 168. Figure `t2x-pair-couplings-top-by-outcome.png`; table
`t2x_pair_couplings_full_crossday.csv` (top-400 membership view: `t2x_pair_couplings_crossday.csv`).

## 4. One-second lead-lag (c16), 21 distinct series pairs

Lag-0 sign shared by all four days: 14 of 21 pairs; 3 of 4: 3; 2 of 4: 4. Peak |rho| at lag 0 on all four days: 12 of 21. Beyond the 99.9% shifted band
on all four days: 12 pairs; on one day: 6; on two: 3. The twelve pairs beyond the band on all four days with their lag-0 values (Oct 2, 3, 17, 18):

| pair | Oct 2 | Oct 3 | Oct 17 | Oct 18 | peak lag, all days |
| --- | --- | --- | --- | --- | --- |
| dmid, supA | -0.56 | -0.54 | -0.58 | -0.57 | 0 |
| dmid, supB | +0.54 | +0.53 | +0.53 | +0.58 | 0 |
| dmid, flow | +0.50 | +0.48 | +0.51 | +0.51 | 0 |
| supA, supB | -0.45 | -0.43 | -0.44 | -0.46 | 0 |
| flow, supA | -0.40 | -0.39 | -0.40 | -0.39 | 0 |
| flow, supB | +0.39 | +0.37 | +0.35 | +0.38 | 0 |
| dmid, timb | -0.13 | -0.15 | -0.13 | -0.11 | 0 |
| dspr, supA | -0.08 | -0.06 | -0.06 | -0.06 | 0 |
| dspr, supB | -0.05 | -0.06 | -0.04 | -0.05 | 0 |
| churn, supA | +0.06 | +0.03 | +0.08 | +0.05 | 0 |
| flow, timb | +0.03 | +0.04 | +0.02 | +0.03 | timb leads flow by 1 s on all four days |
| churn, supB | +0.04 | +0.07 | +0.00 | +0.03 | 0, 0, -14 (Oct 17), 0 |

The remaining nine pairs have lag-0 |rho| at or below 0.05 on every day and peak lags that differ by day (table `t2x_leadlag_crossday.csv`, figure
`t2x-leadlag.png`). dmid, dspr has lag-0 values +0.01, +0.04, -0.03, -0.02.

## 5. One-second state cells (c17), 21 cells x 2 horizons

All 42 rows are present on all four days. Sign of the net share shared by all four days: 16 of 21 cells at next 1 s and 16 of 21 at next 5 s; the cells not
agreeing are the mid-imbalance cells (next 1 s: flat|mid|buy 2 of 4; down|mid|sell, flat|mid|none, flat|mid|sell, up|mid|none 3 of 4; next 5 s:
down|mid|sell, flat|mid|none, up|mid|none 2 of 4; flat|mid|buy, flat|mid|sell 3 of 4). Every bid-heavy cell is positive and every ask-heavy cell negative
on all four days at both horizons. Cells with |net| at or above 0.10 on Oct 18, with the other days (next 1 s / next 5 s; support on Oct 18):

| cell | Oct 2 | Oct 3 | Oct 17 | Oct 18 | support Oct 18 |
| --- | --- | --- | --- | --- | --- |
| up ask-heavy sell, 1 s | -0.155 | -0.156 | -0.220 | -0.131 | 168 |
| up ask-heavy buy, 1 s | -0.138 | -0.118 | -0.155 | -0.117 | 852 |
| down bid-heavy sell, 1 s | +0.133 | +0.149 | +0.110 | +0.104 | 985 |
| down bid-heavy buy, 1 s | +0.140 | +0.098 | +0.143 | +0.113 | 194 |
| up bid-heavy buy, 1 s | +0.082 | +0.090 | +0.071 | +0.109 | 649 |
| down bid-heavy buy, 5 s | +0.178 | +0.155 | +0.219 | +0.175 | 194 |
| up ask-heavy none, 5 s | -0.150 | -0.122 | -0.167 | -0.175 | 704 |
| up ask-heavy buy, 5 s | -0.174 | -0.114 | -0.197 | -0.177 | 852 |
| up ask-heavy sell, 5 s | -0.110 | -0.213 | -0.168 | -0.173 | 168 |
| down bid-heavy none, 5 s | +0.137 | +0.164 | +0.110 | +0.127 | 653 |
| flat ask-heavy sell, 5 s | -0.092 | -0.099 | -0.121 | -0.144 | 757 |
| down bid-heavy sell, 5 s | +0.153 | +0.188 | +0.087 | +0.131 | 985 |
| flat bid-heavy sell, 5 s | +0.067 | +0.086 | +0.058 | +0.102 | 381 |

Supports, up/flat/down counts, z against the shifted outcome, chunk agreement and median ticks per day are in `t2x_state_cells_crossday.csv`; figure
`t2x-state-cells.png`.

## 6. Forward-selection stack (c18), 7 outcomes

| outcome | first condition chosen (Oct 2 / 3 / 17 / 18) | out-of-fold corr after step 1 | final out-of-fold corr (steps) | conditions chosen on all four days |
| --- | --- | --- | --- | --- |
| dspr_5 | spr / spr / spr / spr | 0.390 / 0.354 / 0.293 / 0.371 | 0.412 (3) / 0.412 (6) / 0.331 (3) / 0.404 (3) | spr |
| am_20 | qchg_300 x 4 | 0.012 / 0.070 / 0.041 / 0.075 | 0.034 (6) / 0.098 (6) / 0.073 (6) / 0.107 (5) | qchg_300 |
| dm_5 | tchn_imb x 4 | 0.078 / 0.097 / 0.079 / 0.087 | 0.086 (4) / 0.106 (4) / 0.079 (1) / 0.098 (4) | tchn_imb |
| dm_20 | tchn_imb / tchn_imb / tch_imb / tchn_imb | 0.061 / 0.063 / 0.060 / 0.067 | 0.070 (4) / 0.083 (5) / 0.070 (4) / 0.094 (5) | none (tchn_imb on three) |
| dm_60 | net_60 / an / tch_imb / modT_b_60 | 0.034 / 0.030 / 0.042 / 0.061 | 0.062 (5) / 0.069 (6) / 0.058 (4) / 0.098 (6) | none |
| F_net_5 | asz / bsz_per_ord / tch_imb / bsz_per_ord | 0.033 / 0.024 / 0.030 / 0.030 | 0.051 (5) / 0.047 (5) / 0.045 (5) / 0.044 (3) | none |
| F_supdiff_5 | tch_imb / near5_imb / buy_2 / prior_5 | 0.028 / 0.021 / 0.026 / 0.022 | 0.036 (3) / 0.052 (6) / 0.042 (4) / 0.040 (5) | none |

Full paths (condition added, out-of-fold correlation and gain at every step, every day) are in `t2x_forward_stack_paths.csv`; per-condition selection steps
in `t2x_forward_stack_features.csv`; figure `t2x-forward-stack.png`. Oct 18's dm_60 first step (modT_b_60, 0.061) is not chosen on any other day; on those
days modT_b_60 -> dm_60 has rho -0.013, +0.008, +0.009 against -0.076 on Oct 18 (section 2 table, 2-of-4 rows).

## 7. Interpretation (labelled; not measurements)

- The couplings that repeat on all four days beyond every day's line are, with six exceptions, book-response pairs: activity at the touch over the past
  5 to 60 s and activity at the touch over the next 5 s. This reads as persistence of book activity, the same reading the regime comparison gave.
- The six exceptions are the spread and the touch order counts against the next spread change (sign and size the same on all four days), and the
  300 s quote-change count against the next 20 s absolute move.
- Signed-move pairs repeat in sign (157 of 628 on all four days, chiefly the touch imbalances tch_imb and tchn_imb with dm_1 to dm_20 at +0.11 to +0.14)
  but no signed-move pair is beyond the line on more than one day, and the forward stack's out-of-fold correlation for dm_5 is 0.08 to 0.11 on every day
  with the same first condition. Speculation: the one-second state cells carry the same content at cell level (bid-heavy touch after a down move
  reads positive on all four days; ask-heavy after an up move negative).
- Oct 17 differs from the other three days on bid-side book pairs (values 0.29 to 0.32 against 0.15 to 0.23) and on na10 -> F_add_b_5 (0.00 against
  0.14 to 0.18); Oct 17 is also the day with the highest line (0.1445) and the fewest pairs beyond it (103). The tape-level reason is not examined here.
- Each day is one session of one instrument; the shifted-Y reference is per day and combined day by day, with no pooling of rows.

## 8. What remains of section 3B

- Tier 1 was run later the same day on the actual first-observed family starts of all four sessions (`FINDINGS_TIER1_CROSSDAY_20261109.md`); the
  family-run inputs exist in markets-data 7b50d634, as section 22 of the discovery document records. The 99-plane and 13-input crosswalk remains Oct 18 only.
- The regime comparison (c19 to c23, `claude-pass/tables/crossday/t4_*`) already covers all four days and is unchanged.
