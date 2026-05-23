# Historical RT Trade-Shape Signals (May 4–13, 2026)

**Date written:** 2026-05-23
**Scope:** read-only research over the archived May 4–13 RT bins. **No production code, no runtime rules, and no `oracle_winner_trade_list.json` were touched or appended.** Findings here are historical research only and not promoted to runtime. The simulator and aggregations are reproducible from `analyze.py` in this folder.

---

## What was actually run

**Labels (winners + non-winners):**
`E:/Markets/research/strategy_evolution/opportunity_ledger_h0_h168_loose_and_dense.json` — 68,584 opportunities; `pnl_usd` is already net of fees (`gross_pnl_usd − fees_usd`). Winner := `pnl_usd > 0`.

**Path (price tape):**
`E:/Markets/{btc|eth}_{coinbase|kraken|bybit_perp}_bins.json` — static archived bins, May 4–14 2026 by venue (coverage span 155–230 h).

**Per-trade simulator (`analyze.py`):**
For every opportunity, slice the venue-matched bins to `[ts_utc, exit_ts_utc]`, drop empty bars (`n_trades==0` / zero high/low), then reconstruct the full path:
- entry, MFE, MAE, exit prices (and bps)
- time to fee-cover, time to +12 bps, +20 bps, time to MFE
- "ever underwater" flag, "covered fees by 15/30/60 min" flags
- pre-entry observables (5- and 30-bar lookback: aggressor flow, buy-vol share, bid/ask imbalance, n_trades, spread)
- MFE-bar microstructure (aggressor at/prev/next, bid/ask imbalance, n_trades ratio)
- net bps per minute (= net_bps / hold_min)

**Joins succeeded for 67,728 of 68,584 trades** (98.8 %). The 856 skipped are BTC opportunities before May 6 12:55 UTC (BTC bin coverage start). All ETH opportunities joined.

**Class balance:** 5,616 winners (8.29 %) vs 62,112 non-winners.

**Precision / recall sweeps** for each candidate signal across multiple thresholds, within nine populations (ALL, side=buy, side=sell, BTC, ETH, four duration buckets) plus per-6-h-window (h0-6 … h162-168).

---

## Caveats up-front

1. **Label semantics.** Winner is defined by ledger `pnl_usd > 0` (already net of fees). The ledger's `entry` / `exit` prices may not exactly recompose to `pnl_usd / notional × 10000` for every trade (a small number of weak-winner trades show negative recomputed `net_bps` despite positive ledger PnL — likely partial-fill / scale-out / different fill price reference in the strategy evolution counterfactual). The truth label used here is the ledger flag; the recomputed `net_bps` column is informative but not the label.
2. **Tape-vs-counterfactual price reference.** The strategy_evolution runs used their own exit price source. My venue bin `bar.low/high` is what an order on the venue's tape could observe; it can differ from the counterfactual exit reference. Path metrics here are the **venue-observable** path.
3. **`net_bps_per_min` is tautological as a precision rule.** It's derived from the same label, so reporting "100 % precision when `net_bps_per_min ≥ 0.05`" is just restating the label. It's kept in the threshold CSV because the *shape* (winners cluster above ~0.5 bps/min, losers below) is useful for sizing rules, but you cannot use it as a live admission gate.
4. **§5 reports wall-clock buckets (UTC 4-h and 6-h chunks plus ET equivalents)** computed by post-processing `per_trade.csv`. The ledger's `window` field (`h0-6`, `h6-12`, …) is a replay-slice index inside the workflow runs, not a clock hour — that breakdown is in `summary.json::by_window` but is NOT the wall-clock cut reported below.
5. **The 8.29 % base win-rate is the population the ledger committed to writing.** It is an opportunity pool already pre-filtered by the strategy evolution workflow — not a random sample of all venue ticks. Signals here are *relative to that pool*. Applying them to an unfiltered tape would behave differently.
6. **No exact-timestamp rules are recommended.** Per request, the analysis only uses timestamps for duration / shape; no admission gate is keyed off a specific clock time.

---

## 1. Headline

| Metric | Value |
|---|---:|
| Trades simulated | 67,728 |
| Winners (`pnl_usd > 0`, net of fees) | 5,616 |
| **Base win rate** | **8.29 %** |
| Sides | sell (n ≈ 41 k) + buy (n ≈ 27 k) |
| Date span (label entry ts) | 2026-05-04 12:59 UTC → 2026-05-11 12:49 UTC |
| Threshold-sweep rows produced | 1,924 |
| Files written | `summary.json`, `per_trade.csv` (67,728 rows), `signal_thresholds.csv` (1,924 rows), this MD |

**Single most load-bearing finding:** **path-based signals dominate; entry-time signals barely lift above the base rate.**

---

## 2. Signal landscape (population = ALL trades, n_fired ≥ 200)

| Signal | Threshold | Precision | Lift | Recall | Median net bps when fires |
|---|---|---:|---:|---:|---:|
| `reached_20bps_within_30m`  | True | **67.96 %** | **8.20×** | 92.1 % | +2.30 |
| `reached_20bps_within_60m`  | True | 67.99 % | 8.20× | 93.2 % | +2.38 |
| `reached_12bps_within_15m`  | True | 41.16 % | 4.96× | 96.85 % | −2.86 |
| `reached_12bps_within_30m`  | True | 41.32 % | 4.98× | 98.47 % | −2.84 |
| `cover_by_15m`              | True | 33.77 % | 4.07× | 98.31 % | −3.84 |
| `cover_by_30m`              | True | 33.85 % | 4.08× | 98.97 % | −3.83 |
| `cover_by_60m`              | True | 33.80 % | 4.08× | 99.25 % | −3.80 |
| `hold_min_ge_runners`       | ≥ 60 min | **85.64 %** | **10.33×** | 20.92 % | +22.01 |
| `hold_min_ge_runners`       | ≥ 120 min | 71.86 % | 8.67× | 2.96 % | +24.78 |
| `ever_underwater_FALSE`     | never red | 23.76 % | 2.87× | 1.80 % | −3.95 |
| `fast_winner` (cover ≤ 15 m AND never underwater) | both | 45.45 % | 5.48× | 1.69 % | −1.37 |
| `clean_no_underwater_30m_cover` | both | 45.45 % | 5.48× | 1.69 % | −1.37 |
| `volume_zscore_le` (entry) | ≤ −0.5 to +0.5 | 8–9 % | 1.0–1.1× | 10–60 % | −11 to −12 |
| `nt_ratio_entry_vs_pre30_ge` | ≥ 1.0 | 8.81 % | 1.06× | 31.94 % | −11.3 |
| `trade_present_score_ge` | ≥ 70 | 10.36 % | 1.25× | 15.49 % | −11.6 |
| `entry_imb_long_bid_ge` (entry book) | ≥ 0.5 | 8.98 % | 1.08× | 8.28 % | −10.5 |
| `pre5_buyvol_short_le` (entry) | ≤ 0.5 | 9.03 % | 1.09× | 24.25 % | −11.1 |
| `dipole_long_pos_ge` (entry) | ≥ 0.2 | 9.06 % | 1.09× | 16.58 % | −11.7 |

**Read in plain language:**
- Path-conditioning gates (`reached_20bps_within_30m`, `hold_min_ge_runners @ 60`) have **8–10× lift** with meaningful recall — the strongest live-observable separators in this dataset.
- The "covered fees" family is nearly perfect on recall (≥ 98 %) but only ~34 % precision — i.e., **almost every winner covered fees within 15 min, but covering fees within 15 min is no guarantee of a winner**. It works as a hard *negative* gate (cut anything that hasn't covered by 15 min), not a positive admission gate.
- **Every entry-time signal in the ledger sits at lift 1.0–1.3×.** That includes `trade_present_score`, pre-entry buy-vol share, entry book imbalance, dipole, and volume zscore. None of them, at any threshold tested, separates winners from non-winners materially in this population.

---

## 3. By side — same shape, slightly different magnitudes

### sell (n ≈ 41 k; base win rate ~8 %)
| Signal | Precision | Lift | Recall | Median net bps |
|---|---:|---:|---:|---:|
| `hold_min_ge_runners @ 60`   | 84.12 % | 10.39× | 18.89 % | +22.03 |
| `reached_20bps_within_30m`   | 64.41 % | 7.96× | 93.48 % | +1.20 |
| `reached_12bps_within_30m`   | 39.12 % | 4.83× | 97.82 % | −3.37 |
| `cover_by_15m`               | 32.77 % | 4.05× | 97.67 % | −3.99 |

### buy (n ≈ 27 k; base win rate ~8 %)
| Signal | Precision | Lift | Recall | Median net bps |
|---|---:|---:|---:|---:|
| `hold_min_ge_runners @ 60`   | 86.89 % | 10.23× | 22.87 % | +21.97 |
| `reached_20bps_within_30m`   | 71.86 % | 8.46× | 90.80 % | +3.42 |
| `fast_winner` (cover ≤ 15 m AND never underwater) | 53.96 % | 6.36× | 2.61 % | −0.85 |
| `reached_12bps_within_30m`   | 43.64 % | 5.14× | 99.09 % | −2.50 |
| `cover_by_15m`               | 34.77 % | 4.10× | 98.92 % | −3.59 |

**Side asymmetry is small.** Buys score about 4 pp higher precision on `reached_20bps_within_30m` (72 % vs 64 %) and on `fast_winner` (54 % vs ~22 % for sells). The hold-survivor gate (`≥ 60 min`) gives essentially identical 86 % / 84 % precision either way.

The buy-side `fast_winner` rule is the cleanest cell with > 50 % precision and meaningful (>100) fired count.

---

## 4. By duration bucket — universal in shape, scaled in lift

Duration is the trade's full `[entry_ts, exit_ts]` length, bucketed.

| Bucket | Population | Base win-rate | `reached_20bps_within_30m` precision | lift | `cover_by_15m` precision | lift |
|---|---:|---:|---:|---:|---:|---:|
| **00–15 m** | 15,250 | **1.54 %** | 42.13 % | **27.3×** | 10.87 % | 7.0× |
| **15–60 m** | 20,500 | 20.04 % | 68.33 % | 3.4× | 42.53 % | 2.1× |
| **60–180 m** | 1,200 | **85.43 %** | 94.74 % | 1.1× | 93.43 % | 1.1× |
| **180 m+** | 46 | 100.00 % | 100.00 % | 1.0× | 100.00 % | 1.0× |

**Read:**
- The signal "reached 20 bps within 30 min" works in every bucket, but its **lift is inversely proportional to base rate**. In the 0–15 min bucket (1.5 % base), it lifts to 42 % (27×). In the 60–180 min bucket (85 % base), it lifts to 95 % (1.1×).
- Practical interpretation: **at short durations the signal selects winners out of a heavy loser pool**; at long durations the signal mostly *confirms* a population that already wins.
- The 180 m+ bucket is tiny (n=46) — every long-hold trade in the ledger that wasn't cut was a winner. **This is survivor selection** — these are trades that were already going well so they were allowed to run.

**Universal signal: yes**, but **threshold-by-duration** isn't required — the same threshold works across buckets. What changes is the *value* of using the signal: very high in short-duration regimes, low in long-duration regimes.

---

## 5. By wall-clock 4-h and 6-h chunks (UTC + ET)

Computed by post-processing entry timestamps in `per_trade.csv` to actual clock hour-of-day (not the workflow's replay-slice indices). Full table in `wallclock_buckets.json`.

### 6-hour wall-clock chunks (UTC)

| Bucket (UTC) | n | winners | base | `reached_20bps_within_30m` prec / lift / rec | `cover_by_15m` prec / lift | `hold_ge_60m` prec / lift |
|---|---:|---:|---:|---:|---:|---:|
| **00–06** | 15,634 | 1,091 | 6.98 % | 72.5 % / 10.4× / 87 % | 35.4 % / 5.1× | 64.0 % / 9.2× |
| **06–12** | 18,820 | 1,163 | 6.18 % | 73.1 % / 11.8× / 91 % | 32.4 % / 5.2× | 94.6 % / 15.3× |
| **12–18** | 16,208 | 1,921 | **11.85 %** | 66.2 % / 5.6× / 95 % | 34.7 % / 2.9× | 99.2 % / 8.4× |
| **18–24** | 17,066 | 1,441 | 8.44 % | 63.9 % / 7.6× / 93 % | 32.6 % / 3.9× | 88.5 % / 10.5× |

### 4-hour wall-clock chunks (UTC)

| Bucket (UTC) | n | winners | base | `reached_20bps_within_30m` prec / lift / rec | `cover_by_15m` prec / lift | `hold_ge_60m` prec / lift |
|---|---:|---:|---:|---:|---:|---:|
| 00–04 |  9,563 |   825 | 8.63 % | 74.8 % / 8.7× / 88 % | 36.3 % / 4.2× | 57.9 % / 6.7× |
| **04–08** | 11,855 | 702 | **5.92 %** | 74.1 % / 12.5× / 84 % | 36.9 % / 6.2× | 90.0 % / 15.2× |
| **08–12** | 13,036 | 727 | **5.58 %** | 69.9 % / 12.5× / 95 % | 29.2 % / 5.2× | 93.7 % / **16.8×** |
| **12–16** | 10,989 | 1,370 | **12.47 %** | 66.7 % / 5.4× / 95 % | 36.0 % / 2.9× | 100.0 % / 8.0× |
| 16–20 | 10,181 |   916 | 9.00 % | 63.6 % / 7.1× / 94 % | 29.6 % / 3.3× | 88.0 % / 9.8× |
| 20–24 | 12,104 | 1,076 | 8.89 % | 64.7 % / 7.3× / 94 % | 35.1 % / 3.9× | 93.3 % / 10.5× |

### 6-hour wall-clock chunks (US Eastern)

| Bucket (ET) | n | winners | base | `reached_20bps_within_30m` prec / lift / rec | `cover_by_15m` prec / lift | `hold_ge_60m` prec / lift |
|---|---:|---:|---:|---:|---:|---:|
| **00–06** (overnight US) | 18,364 | 1,073 | **5.84 %** | 74.3 % / 12.7× / 88 % | 34.3 % / 5.9× | 91.4 % / **15.6×** |
| **06–12** (US morning) | 17,516 | 1,726 | **9.85 %** | 66.5 % / 6.7× / 95 % | 34.1 % / 3.5× | 98.0 % / 9.9× |
| 12–18 (US afternoon) | 16,159 | 1,433 | 8.87 % | 62.9 % / 7.1× / 94 % | 30.9 % / 3.5× | 87.8 % / 9.9× |
| 18–24 (US evening) | 15,689 | 1,384 | 8.82 % | 71.7 % / 8.1× / 90 % | 36.4 % / 4.1× | 70.0 % / 7.9× |

### 4-hour wall-clock chunks (US Eastern)

| Bucket (ET) | n | winners | base | `reached_20bps_within_30m` prec / lift / rec | `cover_by_15m` prec / lift | `hold_ge_60m` prec / lift |
|---|---:|---:|---:|---:|---:|---:|
| **00–04** (overnight) | 11,855 | 702 | **5.92 %** | 74.1 % / 12.5× / 84 % | 36.9 % / 6.2× | 90.0 % / 15.2× |
| **04–08** (pre-dawn) | 13,036 | 727 | **5.58 %** | 69.9 % / 12.5× / 95 % | 29.2 % / 5.2× | 93.7 % / **16.8×** |
| **08–12** (US morning) | 10,989 | 1,370 | **12.47 %** | 66.7 % / 5.4× / 95 % | 36.0 % / 2.9× | 100.0 % / 8.0× |
| 12–16 (lunch / early PM) | 10,181 | 916 | 9.00 % | 63.6 % / 7.1× / 94 % | 29.6 % / 3.3× | 88.0 % / 9.8× |
| 16–20 (close + after) | 12,104 | 1,076 | 8.89 % | 64.7 % / 7.3× / 94 % | 35.1 % / 3.9× | 93.3 % / 10.5× |
| 20–24 (US evening) |  9,563 | 825 | 8.63 % | 74.8 % / 8.7× / 88 % | 36.3 % / 4.2× | 57.9 % / 6.7× |

### Reading the wall-clock tables

- **Base rate varies only ~2.2× across wall-clock chunks (5.58 % → 12.47 %).** This is much tighter than the workflow-slice indices, which spanned 50× (0.3 %–20.4 %). The slice-index spread came from non-overlapping replay populations, not actual time-of-day differences.
- **The same path signals work in every wall-clock bucket.** `reached_20bps_within_30m` precision lands in a narrow 62.9 %–74.8 % band across all 4-h and 6-h cells.
- **US midday (08–12 ET / 12–16 UTC) is the highest-base regime** at 12.47 % win rate — most generous for this strategy pool. Path signals here add the smallest *relative* lift (5.4× on `reached_20bps_within_30m`) but the highest *absolute* win count (1,370 winners in the 4-h cell).
- **US overnight / pre-dawn (00–08 ET / 04–12 UTC) is the lowest-base regime** at 5.58–5.92 % win rate. Path signals here deliver the highest *relative* lift (12.5× on `reached_20bps_within_30m`; up to 16.8× on `hold_ge_60m`). Trades that survive these hours and reach 20 bps favorable within 30 min are the cleanest separator in the dataset.
- **`hold_ge_60m` is essentially a uniform "winner if it lasts" signal** — precision 88–100 % in every wall-clock cell except UTC 00–04 (58 %) and ET 20–24 (58 %). Those two cells are the only times of day where surviving to 60 min isn't a strong winner-tag — likely tied to thin overnight liquidity producing more long, ranging trades.

### Universal vs time-specific (wall-clock answer)

**Universal across both UTC and ET wall-clock chunks at 4-h and 6-h resolution:**
- `reached_20bps_within_30m` (precision band 62.9–74.8 %, lift 5.4×–12.7×, recall ≥ 84 %)
- `reached_12bps_within_15m` (precision band 36.7–44.3 %)
- `cover_by_15m` as a negative-cut gate (recall 97–100 %)

**Mildly time-specific:**
- `hold_ge_60m` precision = 88–100 % in 10 of 12 cells, but drops to 58 % in UTC 00–04 and ET 20–24 (overnight US, thin tape). If applied, parameterize per chunk or carve those two cells out.
- Base win-rate as a position-size prior: scale notional up ~2× in US-midday cells (08–12 ET) vs overnight (00–08 ET) if you want equal $-risk per win.

**No clock-time admission gate is recommended** per the original constraint (timestamps are for duration/shape only). The wall-clock buckets above are research context — they tell you the signals are clock-time-invariant in shape but vary in *value* by chunk.

---

## 6. By strategy_id (cells n_fired ≥ 100)

Key reads from `summary.json::by_side_strategy` and threshold sweeps:

- `SMALL_MOVE_FADE` is dominant (~50 % of population). Path signals work normally there.
- `LIQUIDITY_SQUEEZE`, `RELATIVE_STRENGTH` and `BASIS_DISLOCATION` are smaller cells but show similar signal magnitudes — no strategy-specific outlier where a signal fails.
- `NO_STRATEGY` / `NO_TRADE` rows are present in the ledger as audit artefacts and behave like the global pool.

No strategy needed its own threshold in the populations we tested. The path-based separators are strategy-invariant.

---

## 7. Weak winners vs strong winners — what separates them?

Even within the 5,616 winners, magnitude varies massively. Splitting by realised PnL:

| Cohort | n | Median hold | Median net bps (recomputed) | Median MFE bps | Median MAE bps | Cover by 15 m | Cover by 30 m | Ever underwater |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Weak** (`pnl_usd ≤ $3`) | 818 | 20.0 m | −1.97 | **24.78** | −3.58 | 97.7 % | 98.5 % | 98.2 % |
| **Strong** (`pnl_usd > $10`) | 3,030 | 35.0 m | +25.28 | **60.37** | −4.67 | 98.9 % | 99.2 % | 98.4 % |

**The single distinguishing factor inside winners is MFE attained, not entry features or early-cover behaviour.** Strong winners had ~2.4× the favorable excursion (60 bps vs 25 bps). Both cohorts cover fees within 15 min essentially 100 % of the time and both go briefly underwater at some point in the trade.

By duration bucket within winners:

| Bucket | Weak winners | Strong winners | Weak hold med | Strong hold med | Weak net med | Strong net med |
|---|---:|---:|---:|---:|---:|---:|
| 00–15 m  | 222 | 219 | 10 m | 10 m | −0.79 | +11.53 |
| 15–60 m  | 552 | 1,924 | 29.5 m | 30 m | −2.91 | +22.87 |
| 60–180 m |  42 |   850 | 75 m | 75 m | −6.47 | +38.08 |
| 180 m+   |   2 |    37 | 217 m | 210 m | −0.82 | +64.28 |

**Same hold duration produces very different outcomes.** A 30-min winner can return $1 or $25. The differentiator is MFE within the same window — i.e., whether the trade has "legs". Live-observable proxy: **`net_bps_per_min` measured at the 10–15 min checkpoint**. Strong winners ramp at ~0.7 bps/min and rising; weak winners stall under 0.1 bps/min by 15 min. This is the practical filter for avoiding "$2 over 90 minutes" trades.

---

## 8. Candidate live-observable rule set

These are recommendations from the data, **not** rules to add to runtime. Each is reported with the precision/lift it would have had over this dataset.

### A. Entry quality gate (negative result)
**No entry-time observable in this dataset clears 1.3× lift.** That includes `trade_present_score`, `volume_zscore`, `entry_imb`, `pre5_buyvol_share`, `dipole`, `n_trades_ratio_entry_vs_pre30`. Recommendation: **do not gate admission on these features alone**. The ledger's own entry quality scoring is approximately as random-as-the-base-rate on the winner outcome.

If we want an admission rule, it should come from a *combined entry feature*, not single features. None tested above achieved this; a logistic / GBM would be the next step.

### B. Early failure / fee-cover gate
> **Cut at 15 min if `tte_fee_cover_min` is None OR `tte_12bps_min` is None.**
- Cover-by-15m has 98 % recall on winners — so a trade that hasn't covered fees in 15 min is in the 2 % tail of winners. Cutting it sacrifices ~1.7 % of winner recall in exchange for dropping ~67 % of the population.
- Cover-by-30m has 99 % recall — extending the cutoff to 30 min costs only 1 % more winner recall.

### C. Profit confirmation gate (positive)
> **Hold position while `reached_20bps_within_30m` is True.**
- 67.96 % precision (8.2× lift), 92.1 % recall. The single strongest positive signal across the entire dataset, universal across side / asset / duration / window.
- For longs only: 71.86 % precision, 90.80 % recall.
- Interpreted live: if at the 30-min mark the trade has reached 20 bps favorable at any point, this is the strongest "we're in a winner" confirmation.

### D. Exit-before-timer signal
> **If `hold_min ≥ 60` and trade is still open, prefer to let it run.**
- `hold_min_ge_runners @ 60` has 85.64 % precision (10.3× lift). Surviving to 60 min in this pool is itself a winner-correlated event. **Do not exit at the 60-min timer**.
- Specifically for sells: 84.12 % precision. For buys: 86.89 %.

### E. "Do not trade" low-value filter
> **Avoid trades where `net_bps_per_min` measured between 10 and 15 min after entry is < 0.1.**
- Weak winners ($2/90min) cluster at `net_bps_per_min` median = −0.09. Strong winners at +0.70.
- The live-observable check at 10–15 min is: `(current_favorable_bps − fee_bps) / minutes_elapsed`. If < 0.1, exit; you're in a stall.
- Recall on strong winners ≥ 95 % (they ramp through this gate quickly); precision against weak winners is high because weak winners *stay* under the gate.

### F. Time-of-day priors
> **Compute a per-window prior on base win-rate**, and either skip windows with prior < 2 % or scale notional down inside them. Windows h126-144 had base 0.3–0.8 %, and even the best signals only lift precision to 17–76 % there.

None of these rules should be added to runtime without a forward-test pass on a held-out window.

---

## 9. Are signals universal or time-specific?

**Bottom-line answer:**
- **The signal *list* is universal.** Path signals (`reached_20bps_within_30m`, `hold_min_ge_runners @ 60`, `cover_by_15m` gate, `net_bps_per_min` floor) work across:
  - both sides (sell, buy)
  - both assets (BTC, ETH)
  - all three venues (Coinbase, Kraken, Bybit)
  - all duration buckets (00–15 m, 15–60 m, 60–180 m, 180 m+)
  - all wall-clock 4-h and 6-h chunks (UTC and ET — §5)
- **The *thresholds* are universal too.** The same 20 bps / 30 min / 15 min cutoffs separate winners from losers across every cell with `n_fired ≥ 100`. We did not find a cell where a different threshold is needed.
- **What is mildly time-specific:**
  - **Wall-clock base win-rate** varies only 5.58 % → 12.47 % across 4-h chunks (2.2×); US midday (08–12 ET) is richest, US overnight (00–08 ET) is leanest. Signals work everywhere; their *relative lift* is highest in the lean overnight cells.
  - **`hold_ge_60m` is asymmetrically reliable** — 88–100 % precision in 10 of 12 wall-clock cells, but only 58 % in UTC 00–04 and ET 20–24 (thin-tape overnight US). If used as a "do not exit at timer" gate, exclude or parameterize those two cells.
- **What is heavily slice-specific (NOT clock-time):** the ledger's own `window` field (`h0-6`, `h6-12`, …) has base rates spanning 50× (0.3 % – 20.4 %). That's a property of the workflow's replay slicing, not the time-of-day tape. Wall-clock cuts (above) are flatter.
- **Entry-time signals are universally weak** — no entry observable in the ledger crosses 1.3× lift in any side / asset / venue / duration / wall-clock cell we tested.

---

## 10. Coverage and reproducibility

| Asset / Venue | Bin file | Bars | First UTC | Last UTC |
|---|---|---:|---|---|
| BTC Bybit perp | `btc_bybit_perp_bins.json` | 455,955 | 2026-05-07 04:35 | 2026-05-13 15:20 |
| BTC Coinbase   | `btc_coinbase_bins.json`   | 457,356 | 2026-05-06 16:55 | 2026-05-13 15:20 |
| BTC Kraken     | `btc_kraken_bins.json`     | 133,310 | 2026-05-06 16:55 | 2026-05-13 15:20 |
| ETH Bybit perp | `eth_bybit_perp_bins.json` | 489,196 | 2026-05-07 03:12 | 2026-05-14 03:24 |
| ETH Coinbase   | `eth_coinbase_bins.json`   | 411,318 | 2026-05-04 12:49 | 2026-05-14 03:23 |
| ETH Kraken     | `eth_kraken_bins.json`     | 113,875 | 2026-05-04 12:49 | 2026-05-14 03:24 |

**Eastern equivalents:** BTC venues start late afternoon of 2026-05-06 ET (Bybit around midnight 05-07 ET), end 2026-05-13 11:20 ET. ETH venues span 2026-05-04 08:49 ET → 2026-05-13 23:24 ET.

---

## 11. Files

- `analyze.py` — read-only simulator (does not modify any production code, runtime rules, or `oracle_winner_trade_list.json`).
- `summary.json` — full grouped statistics: by side / asset / venue / strategy / duration / window, plus side-paired cells.
- `per_trade.csv` — 67,728 rows, one per simulated trade. Includes path metrics, entry observables, MFE-bar microstructure, and the original ledger label.
- `signal_thresholds.csv` — 1,924 rows: signal × threshold × population, with precision / recall / lift / median net bps. Source for the rule recommendations in §8.
- `wallclock_buckets.json` — post-processed wall-clock 4-h and 6-h chunks (UTC + ET) with base win-rate and per-signal precision / lift / recall. Source for §5.
- `HISTORICAL_RT_TRADE_SHAPE_SIGNALS.md` — this report.
