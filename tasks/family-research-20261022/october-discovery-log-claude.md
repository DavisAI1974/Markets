# October NG discovery: Claude pass (interim, Oct 18 only)

Own file, to be merged with the Codex and Claude Code logs later. Not part of the shared
october-discovery-log.md. Branch: codex/ng-shadow-discovery-20261108, started from 5724f40.
Code and tables: tasks/family-research-20261022/claude-pass/ (scripts c01-c18, tables/*.csv).

## Status

| Item | State |
| --- | --- |
| Oct 18 (NGX3, instrument 150611), one UTC member | analysed: Tier 1 (749 families), Tier 2 (dense grid, 28,380 rows) |
| Oct 2, 3, 17 | not run. Scripts still read Oct 18 paths (see Handoff) |
| Dipole cohort (863 candidates), 99-plane / 13-input crosswalk, hypothesis layer, ROOT/Native/standalone output index | not started |
| Disagreements with Codex | none recorded yet; Codex conclusions not yet compared line by line |

## Conventions that hold for every number below

- Only market conditions enter the math. Trade ids, cursors, timestamps, day of week and clock
  buckets are provenance only. c14 asserts that no identity or clock column is in the input set.
- Activity quintile (trailing trade count, quote changes) replaces clock-bucket normalisation.
  Stability is read from 24 contiguous chronological chunks (count of chunks with the same sign).
- Groups close at an F_LAST record and are known at that record's ts_recv. Pre-event windows end
  at start_recv_ns - 1. Outcomes are last-group-known midpoint changes at +h, in ticks (0.001).
- Trade side is wire-only (A = seller hit bids, B = buyer lifted asks). Side-N lots are kept apart.
- No trade cost anywhere. Nothing pooled across spread regimes in new work from here on.
- Neighbouring windows overlap heavily; naive p-values are not used. One date, so day-level drift
  is mixed into everything.
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

## D. Spread regime split (primer check, computed in-session from t2_grid.parquet)

Spread 1 tick 13,616 rows, 2 ticks 13,061, 3+ ticks 1,703 (sum 28,380). Spearman of percentile
ranks within activity quintile.

| Spread | condition | rho 5 s | rho 20 s |
| --- | --- | --- | --- |
| 1 tick | touch order-count imbalance | +0.121 | +0.093 |
| 2 ticks | touch order-count imbalance | +0.088 | +0.126 |
| 3+ ticks | touch order-count imbalance | +0.061 | +0.175 |

Chunks positive at 5 s: 1 tick 23 of 24, 2 ticks 21 of 24. The coupling shifts horizon with spread.
The primer expects collapse in multi-tick books; that is not what this day shows.
(This split was run inline and is not yet a script; add as c19 in the next pass.)

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

## Layers kept apart

| Layer | Content |
| --- | --- |
| Observed mechanics | A (touch lean sign and next-second sign), reconciliation of order-level lots to retained ROOT operands for 654 of 656 comparable families, 100% touch match at 569,063 group closes |
| Associations | B, C, D, G, H |
| Hypotheses (speculative) | (1) Inventory-constrained liquidity providers re-centering quotes after a move would give reversal when the touch leans against it; (2) continuation when the touch leans with the move is the queue-depletion race in the primer. Distinguishing evidence: whether cancelled ids re-appear at new prices (re-centering), and whether the same-lean effect scales with queue size at the touch (depletion race). Neither tested |
| Unknowns | Whether any of this repeats on other days; owner of orders; spread-regime effect on A; the 694-subset null question in F |

## Handoff for the next session

1. Date-parameterise: c03 (reconstruction), c12 (grid), c14, c15, c16, c17, c18. Hard-coded: recon
   parquet name (recon_20231018.parquet), groups.npz (build the group arrays from F_LAST records of
   the recon instead; equivalent on Oct 18), output table names.
2. Tapes: gh api -H "Accept: application/vnd.github.raw"
   "repos/DavisAI1974/Markets/contents/data/nymex_mbo/ng_v0_oct2023/NG_v0_mbo_<date>.dbn.zst?ref=1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202";
   verify sha256 against MANIFEST.json; decode with databento.
3. Run the same conditions-only scan per date, split by spread regime, and tabulate which couplings
   repeat in sign and size across the four days (the day is the unit of independence).
4. Add from the primer (commit 1ce1fd8): exclude exchange reserved states (velocity / stop logic)
   like the settle window; record snapshot age on every pre-event feature; count trials.
5. Then: dipole cohort (863 candidates, examples DIP-1697581215, DIP-1697583021, DIP-1697625921,
   DIP-1697607905, G230690, G232857), 99-plane / 13-input crosswalk, ROOT/Native/standalone output
   index for Oct 2/3/17, charts with plotted counts reconciled to table rows (none built yet).
6. Large derived parquet files (t2_grid, t2_seconds, t2_seconds_states) are not committed; c12 and
   c16 regenerate them from the tape.
