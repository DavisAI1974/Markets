# The Oct 18 Tier 1 chain on the actual family starts of Oct 2, Oct 3 and Oct 17, side by side with Oct 18

Written 2026-11-09. Branch `claude/three-day-dipole-20261108`, folder `claude-pass-3day/`. This closes the last open piece of handoff section 3B. The Oct 18
Tier 1 chain (c02 outcomes, c06 family master with order-level windows, c07 cells and stack variants, c08 depth and corners, c10 refill at the side being hit,
c11 four arms) was run with its method unchanged on the first-observed structural family starts of the other three sessions. The inputs are the family
replication run's per-date index (markets-data commit `7b50d634`, run 42566535537), the same inputs section 22 of `claude-october-discovery-20261108.md` used
for the four-arm pass; the populations are therefore section 22's 795 / 848 / 823 / 749. Every row is one family or one cell with the four days beside each
other; shares are per day; nothing is averaged across days. No trade cost anywhere.

Scripts: `x18_tier1_days.py` (the chain, one session per run), `x19_tier1_crossday.py` (side by side). Tables: `tables/<session>/t1_*.csv` with
`t1_receipt.json`; `crossday/t1x_*.csv`. The Oct 18-only matched-50 pass (c09, which needs the saved screen status) is not run.

## 1. Inputs, exclusions and the replication check

| | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
| --- | --- | --- | --- | --- |
| families in the index | 796 | 849 | 824 | 749 |
| left out, with id recorded | 1 (snapshot-start family, no pre-event source cursor) | 1 (starts at the first session group; no earlier group) | 1 (snapshot-start) | 0 |
| families used | 795 | 848 | 823 | 749 |
| session groups (prior member from 21:00 UTC to the 21:00 UTC close) | 609,611 | 653,912 | 638,324 | 583,688 |
| families inside the date member with a full 60 s of records | 781 | 796 | 809 | 694 |
| 60 s aggressor lots equal to the retained ROOT operands, buy / sell | 744 / 752 | 749 / 742 | 770 / 774 | 654 / 656 |
| outcomes censored at 300 s / 600 s (horizon past the close) | 0 / 0 | 2 / 2 | 3 / 3 | 4 / 5 |

The per-date index has no `cutoff_ns`; the decision boundary is `start_recv_ns - 1 ns`, which is the Oct 18 ledger's own rule (749 of 749 there), and the
chronological quarter is the rank quartile within the date. Replication: run on Oct 18 from the rebuilt tape, the chain reproduces every committed Tier 1
table (`claude-pass/tables/t1_*.csv`) value for value: family master, cells, stack variants, corners, orientation, refill terciles and strata, four-arm
summary and by-block tables, including the 4 and 5 censored outcomes at 300 and 600 s. The session group count of Oct 18 (583,688) and Oct 3 (653,912)
equal the counts in the discovery document.

## 2. The displayed book at family starts (c08)

| | Oct 2 | Oct 3 | Oct 17 | Oct 18 |
| --- | --- | --- | --- | --- |
| full-depth imbalance, min / median / max | -0.087 / 0.081 / 0.254 | -0.004 / 0.172 / 0.317 | -0.085 / 0.095 / 0.316 | 0.015 / 0.193 / 0.417 |
| bid / ask full depth ratio, median | 1.18 | 1.42 | 1.21 | 1.48 |
| families with ask-heavy full depth | 76 | 1 | 69 | 0 |
| near (ten-level) imbalance: negative / positive / zero | 361 / 426 / 8 | 403 / 438 / 7 | 360 / 453 / 10 | 365 / 378 / 6 |
| correlation of full and near imbalance | 0.55 | 0.28 | 0.53 | 0.22 |

The full displayed book is bid-heavy at 718 / 847 / 754 / 749 of the family starts; the near ten levels split about evenly on every day.

## 3. Stack variants (c07), share of families whose midpoint is lower at the horizon

Support per day (Oct 2 / 3 / 17 / 18) and the down share per day:

| variant | support | 5 s | 60 s | 300 s |
| --- | --- | --- | --- | --- |
| all families | 795 / 848 / 823 / 749 | 0.43 / 0.36 / 0.36 / 0.43 | 0.47 / 0.42 / 0.42 / 0.47 | 0.47 / 0.41 / 0.50 / 0.50 |
| original: 60+ / 5- / 1-, bid-heavy full depth | 40 / 57 / 46 / 50 | 0.40 / 0.35 / 0.30 / 0.46 | 0.50 / 0.28 / 0.57 / 0.58 | 0.42 / 0.49 / 0.52 / 0.66 |
| flow of the original, any depth sign | 47 / 58 / 52 / 50 | 0.36 / 0.34 / 0.31 / 0.46 | 0.49 / 0.28 / 0.54 / 0.58 | 0.43 / 0.48 / 0.48 / 0.66 |
| flow flipped: 60- / 5+ / 1+, bid-heavy | 46 / 63 / 55 / 45 | 0.43 / 0.38 / 0.38 / 0.33 | 0.39 / 0.44 / 0.33 / 0.33 | 0.41 / 0.35 / 0.49 / 0.56 |
| inverse (all four flipped), ask-heavy | 2 / 0 / 3 / 0 | | | |

The original stack's down share at 60 s is above the day's all-family share on Oct 17 (0.57 against 0.42) and Oct 18 (0.58 against 0.47), equal to it on
Oct 2 (0.50 against 0.47) and below it on Oct 3 (0.28 against 0.42). Section 22 measured the same four numbers on the same families with its own
orientation (0.59 / 0.34 / 0.61 / 0.64 continuation). The inverse stack has 5 families across the four days.

## 4. Flow pattern by full-depth sign (c07) and near-depth corners (c08)

Cells with at least 20 families on every day, down share per day at 60 s (cell sizes Oct 2 / 3 / 17 / 18):

| pattern 60 / 5 / 1, full depth | cell sizes | 60 s down share | days with more down than up |
| --- | --- | --- | --- |
| + / + / +, bid-heavy | 148 / 152 / 164 / 134 | 0.41 / 0.42 / 0.35 / 0.42 | 0 |
| - / - / -, bid-heavy | 139 / 149 / 111 / 144 | 0.55 / 0.50 / 0.45 / 0.55 | 3 |
| - / + / +, bid-heavy | 46 / 63 / 55 / 45 | 0.39 / 0.44 / 0.33 / 0.33 | 0 |
| + / - / -, bid-heavy (the original) | 40 / 57 / 46 / 50 | 0.50 / 0.28 / 0.57 / 0.58 | 3 |
| + / + / NA, bid-heavy | 49 / 43 / 52 / 49 | 0.45 / 0.49 / 0.48 / 0.57 | 4 |
| - / + / NA, bid-heavy | 29 / 32 / 24 / 21 | 0.62 / 0.41 / 0.58 / 0.62 | 3 |
| + / NA / NA, bid-heavy | 45 / 45 / 38 / 74 | 0.47 / 0.42 / 0.34 / 0.32 | 0 |

At 5 s the all-buying cell (+ / + / +) has down share 0.32 to 0.36 and the all-selling cell (- / - / -) 0.42 to 0.56 on the four days; the full table with
quartiles and medians is `t1x_cells_flow_pattern_x_depth_crossday.csv`. Oriented to the 5 s flow (`t1x_oriented_to_5s_flow_crossday.csv`): among all
families with a signed 5 s flow (664 / 679 / 687 / 573), the share continuing in that direction is 0.43 / 0.41 / 0.43 / 0.47 at 5 s and 0.47 / 0.42 / 0.46 /
0.48 at 60 s; for the original pattern 0.36 / 0.34 / 0.31 / 0.46 at 5 s and 0.49 / 0.28 / 0.54 / 0.58 at 60 s. Near-depth corners at 60 s
(`t1x_corners_flow_x_neardepth_crossday.csv`): original pattern with near bid-heavy book, down share 0.48 / 0.32 / 0.60 / 0.62 on 29 / 28 / 25 / 21 families;
with near ask-heavy book 0.50 / 0.23 / 0.50 / 0.55 on 16 / 30 / 26 / 29.

## 5. Refill at the side being hit (c10), in-member families

Families whose last second before the start had sell-aggressor lots and bid fills: 360 / 345 / 332 / 263; buy-aggressor lots and ask fills: 325 / 334 / 339 /
279. Ratio = lots added at or within four ticks of the hit side's touch over lots of resting orders executed, both over the last 1 s. Spearman of the ratio
against the midpoint change (`t1x_refill_spearman_crossday.csv`):

| set | 1 s | 5 s | 20 s | 60 s | 300 s |
| --- | --- | --- | --- | --- | --- |
| sell-hit, bid ratio | +0.21 / +0.15 / +0.10 / +0.26 | +0.14 / +0.13 / +0.06 / +0.24 | +0.14 / +0.09 / +0.12 / +0.19 | +0.15 / +0.06 / +0.09 / +0.17 | +0.17 / -0.02 / -0.13 / +0.09 |
| buy-lift, ask ratio | -0.14 / -0.13 / -0.29 / -0.27 | -0.10 / -0.12 / -0.21 / -0.17 | -0.09 / +0.03 / -0.19 / -0.19 | -0.02 / -0.04 / -0.16 / -0.17 | -0.18 / +0.11 / -0.08 / -0.12 |

Terciles, down share at 1 s: sell-hit low ratio 0.56 / 0.52 / 0.52 / 0.61 against high ratio 0.39 / 0.32 / 0.44 / 0.36; buy-lift low ratio 0.29 / 0.28 / 0.18 /
0.19 against high ratio 0.47 / 0.35 / 0.50 / 0.42. The sign of the 1 s and 5 s relation is the same on all four days in both sets. Inside fill-size halves
(`t1x_refill_by_fill_stratum_crossday.csv`, sell-hit set): small fills, ratio at or above median, down share at 1 s 0.41 / 0.29 / 0.42 / 0.28 against below
median 0.46 / 0.49 / 0.48 / 0.52; large fills 0.52 / 0.37 / 0.38 / 0.56 against 0.51 / 0.49 / 0.52 / 0.57. At 300 s the relation has no consistent sign.

## 6. Four arms (c11): purged chronological ridge, MSE relative to predicting zero, sign share

Of the 40 (set, horizon, arm) rows, 31 are at or above the predict-zero MSE on all four days, 8 below it on one day, 1 below it on two days
(`t1x_fourarm_crossday.csv`). Selected rows, MSE ratio per day (Oct 2 / 3 / 17 / 18) and sign share:

| set, horizon | arm | MSE / zero | sign share |
| --- | --- | --- | --- |
| all families, 5 s | baseline | 1.04 / 1.04 / 1.06 / 1.04 | 0.55 / 0.45 / 0.52 / 0.52 |
| all families, 5 s | + both | 1.02 / 1.06 / 1.07 / 1.10 | 0.55 / 0.47 / 0.55 / 0.54 |
| all families, 60 s | + flow | 1.04 / 1.03 / 1.02 / 1.00 | 0.47 / 0.46 / 0.51 / 0.51 |
| all families, 300 s | baseline | 1.01 / 1.06 / 1.05 / 1.02 | 0.51 / 0.49 / 0.49 / 0.51 |
| in-member, 5 s | + both | 1.03 / 1.02 / 1.06 / 1.33 | 0.53 / 0.52 / 0.55 / 0.52 |
| in-member, 60 s | + flow | 1.03 / 1.03 / 1.01 / 1.03 | 0.49 / 0.47 / 0.52 / 0.51 |
| in-member, 300 s | + both | 1.02 / 1.04 / 1.08 / 0.99 | 0.51 / 0.52 / 0.46 / 0.52 |

Sign share above one half on all four days: one row (in-member, 5 s, + both, 0.52 to 0.55); on three days: 18 rows; on two: 14; on one: 6; on none: 1.
The shifted-outcome null columns are in the table per day.

## 7. Interpretation (labelled; not measurements)

- The family-start population looks the same on all four sessions in its book: the full displayed book is bid-heavy at 90 to 100 percent of starts
  while the near ten levels split evenly, as section 22 found. The one-second flow cells sort the next 5 s on every day (buying cells lower less often
  than selling cells), and this ordering fades by 60 s on most cells.
- The order-level refill read is the piece that was Oct 18 only and now repeats: when the bid is being hit, more adds per lot filled at or near the bid
  goes with a higher midpoint over the next 1 to 20 s, and the mirror holds when the ask is being lifted, with the same sign on all four days and inside
  fill-size halves at 1 s. It is a few ticks and is gone by 300 s. Speculation: this is replenishment read at the moment of the hit, the mechanism the
  primer calls resiliency, and it is the same kind of object as the touch-size reads in the Tier 2 state cells.
- The original stack's 60 s read is Oct 17 and Oct 18, not Oct 2, and reversed on Oct 3; section 22 said this already from the four arms.
- No ridge arm beats predicting zero on more than two days at any horizon. The features carry sign more than size.
- Each day is one session of one instrument; the reads above are per day and never pooled.

## 8. What this leaves of section 3B

Nothing. Tier 1 (this file), Tier 2 (`FINDINGS_TIER2_CROSSDAY_20261109.md`), the regime comparison (`claude-pass/tables/crossday/t4_*`) and the dipole
cohort (`FINDINGS_THREE_DAYS_20261108.md`) now exist on all four days with the same code. The 99-plane and 13-input crosswalk remains Oct 18 only and is tied
to merge time.
