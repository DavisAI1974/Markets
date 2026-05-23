# Winner-Trade Extrema: Leading Signals at the Cover / Sell Point

**Date:** 2026-05-23
**Source of truth:** `research/strategy_evolution/live_mock_replay/live_hindsight_missed_winner_audit_rows.csv`, filtered to `is_oracle_winner_after_fees == True`.
**Universe ingested:** 8 024 audit rows → **5 886 oracle-after-fee winners** with valid `[oracle_entry_ts_utc, oracle_exit_ts_utc]` windows on BTC + ETH (sell or buy side).
**Extreme definition (as instructed):**
- `side == 'sell'` (short): lowest `bar.low` in `[oracle_entry_ts_utc, oracle_exit_ts_utc]`
- `side == 'buy'`  (long):  highest `bar.high` in the same window
- Empty bars (`n_trades == 0` / zero low/high) are dropped before locating the extreme.
**Method:** read-only. Price bins are the per-venue tick aggregates at `live_data/{asset}_{venue}_bins.json`. Microstructure (aggressor, bid/ask imbalance, spread, volume ratio, buy-vol share) computed at the extreme bar and its ±1-bar neighbours, with a 5-bar lookback aggregate. Six grouping dimensions: **side, asset, venue, strategy_id, pattern_family, miss_type**, plus selected pairs.
**Reproducibility:** `analyze.py` in this folder → `summary.json` + `per_trade.csv`.
**Time frame:** price bin coverage at run time was 2026-05-23 02:42 UTC → 08:42 UTC (~6 h; 22:42 EDT Thu → 04:42 EDT Fri). Oracle windows span 02:38 UTC → 08:38 UTC.

---

## Two caveats that change how you read the numbers

**1. ~51 % of oracle windows extend beyond the price-bin window** and were *clamped* to bin coverage (`bins_clamped=True`). Clamped trades are kept in `per_trade.csv` (with the flag) but **dropped from every grouped aggregate**. The headline tables below are computed on the **unclamped subset only: n = 2 909** (sell 2 678, buy 231).

**2. The oracle uses a tighter price reference than the venue bin tape.** Even on unclamped windows the bar `low/high` only beats or matches the oracle's chosen `oracle_exit_price` in **23 %** of trades. So `oracle_net_bps` is consistently larger than the `captured_bps` I compute from `bar.low/high`. Concretely, on BTC the tape gives ~46–50 % of the bps the oracle reports; on ETH ~65–70 %; on Kraken BTC the tape actually *beats* the oracle (a venue-bin-granularity quirk — Kraken bars are sparser and span wider price excursions). **The bar-low/high extreme is the right object for "what an order watching this venue's tape could realistically have observed"; the oracle reference is something finer (likely tick-level or cross-venue/bid-side).** Both numbers are reported.

Other smaller caveats: single live window, single timezone of activity (overnight US / Asia), 6-h capture span; per-(side, asset, venue, strategy) cells get thin fast; spread for ETH `n_trades == 1` bars often equals the venue tick — read `spread_bps_extreme` p25 medians, not means.

---

## 1. Headline by side (unclamped, n = 2 909)

| Side | n | $ realised (oracle) | Median oracle_net_bps | Median tape captured_bps | Median hold (min) | Median time-to-extreme (min) | Median extreme position in window |
|---|---:|---:|---:|---:|---:|---:|---:|
| **sell** (short, cover at low) | 2 678 | $144 779 | **160.4** | 134.1 | 312 | 114.8 | **0.99** |
| **buy** (long, sell at high) | 231 | $239 | **3.2** | 12.6 | 18 | 9.0 | **0.94** |

**Take-aways**
- **Long winners are micro-bps events on the oracle's reference (3 bps median) but ~13 bps on the venue tape.** They're also fast — median hold 18 min vs 312 min for shorts.
- **Short winners produce 50× the dollar PnL of long winners** in this window ($144 k vs $239) — the regime is dominated by short-side oracle wins.
- For **every group**, the extreme lands at `ext_pos_pct ≈ 0.94 – 1.00` — i.e., the oracle's exit timestamp essentially is the natural extreme of the visible-tape window, by construction. **The exit timer rides to the extreme; the missed-bps versus the oracle is a price-reference gap, not a timing gap.**

---

## 2. By side × asset

| Group | n | Median captured_bps (tape) | Median oracle_net_bps | Ratio tape/oracle | Median hold (min) | Median tte (min) |
|---|---:|---:|---:|---:|---:|---:|
| sell_BTC | 1 624 | 77.4  | 149.6 | 0.52 | — | 117.8 |
| sell_ETH | 1 054 | 168.3 | 251.1 | 0.67 | — | 108.7 |
| buy_BTC  |    38 | 11.9  |   4.3 | 2.77 | — | 22.1 |
| buy_ETH  |   193 | 12.7  |   3.2 | 3.97 | — |  7.8 |

For shorts the oracle's reference materially outperforms what's observable on the venue tape; for longs the tape *over-states* edge versus oracle (because `bar.high` can register a tick spike that the oracle would not execute against).

---

## 3. By side × asset × venue (sell-side, the venue asymmetry)

| Group | n | Median captured_bps (tape) | Median oracle_net_bps | Reading |
|---|---:|---:|---:|---|
| sell_BTC_Bybit    | 499 |  71.5 | 153.5 | Tape catches **47 %** of oracle |
| sell_BTC_Coinbase | 497 |  66.0 | 148.9 | Tape catches **44 %** of oracle |
| sell_BTC_Kraken   | 628 | 160.1 | 147.2 | **Tape beats oracle by 9 %** — sparser Kraken bars span bigger excursions |
| sell_ETH_Bybit    | 450 | 148.3 | 252.9 | Tape catches **59 %** |
| sell_ETH_Coinbase | 233 | 188.1 | 251.1 | Tape catches **75 %** |
| sell_ETH_Kraken   | 371 | 175.3 | 246.3 | Tape catches **71 %** |

For buys all venue n's are < 80 so per-venue stats are advisory only — see `summary.json::by_side_asset_venue` for raw cells.

---

## 4. By side × strategy_id (cells with n ≥ 20)

| Strategy | n | Median captured_bps (tape) | Median oracle_net_bps | Median hold |
|---|---:|---:|---:|---:|
| sell_SMALL_MOVE_FADE       | 1 140 | 137.3 | 166.9 | 115.7 m |
| sell_NO_STRATEGY           | 1 098 | 126.4 | 162.3 | 124.3 m |
| sell_LIQUIDITY_SQUEEZE     |   186 | 171.4 | 158.5 | 205.0 m |
| sell_MEAN_REVERSION_CHOP   |   182 |  58.8 | 128.0 |  36.4 m |
| sell_NEWS_BREAKOUT         |    34 | 140.2 | 244.9 |  74.1 m |
| sell_RELATIVE_STRENGTH     |    38 | 131.3 | 118.4 |  28.5 m |
| buy_VOL_BREAKOUT           |    53 |  12.7 |   2.8 |  33.9 m |
| buy_BASIS_DISLOCATION      |    44 |  11.6 |   1.8 |  41.7 m |
| buy_MEAN_REVERSION_CHOP    |    35 |  14.2 |   6.4 |   5.6 m |
| buy_NO_TRADE               |    32 |  10.8 |   1.6 |  38.5 m |
| buy_NO_STRATEGY            |    28 |  29.1 |  23.7 |   6.7 m |
| buy_RELATIVE_STRENGTH      |    27 |  14.9 |   6.4 |   2.0 m |

**Note:** `sell_LIQUIDITY_SQUEEZE` and `sell_RELATIVE_STRENGTH` are the only sell strategies where the venue tape **beats** the oracle reference, hinting their cover-side optimum is large enough that bin granularity doesn't lose it.

---

## 5. By side × pattern_family (cells with n ≥ 20)

| Family | n | Median captured_bps (tape) | Median oracle_net_bps | Median tte (min) |
|---|---:|---:|---:|---:|
| sell_SMALL_MOVE_FADE          | 2 107 | 131.2 | 164.7 | 137.7 |
| sell_SELL_DOWN_CONTINUATION   |   248 | 156.1 | 147.4 |  93.8 |
| sell_EXTENDED_UP_SELL_FADE    |   236 |  65.9 | 121.7 |  28.1 |
| buy_BUY_UP_CONTINUATION       |   148 |  13.7 |   4.5 |  32.4 |
| sell_SMALL_MOVE_FADE_NEIGHBOR |    47 | 172.6 | 161.3 | 244.0 |
| buy_BUY_FADE                  |    45 |  10.1 |   1.8 |   5.0 |
| sell_SELL_SHAPE_WATCHLIST     |    40 | 130.1 | 125.1 |  23.8 |
| buy_BUY_SHAPE_WATCHLIST       |    38 |  11.4 |   5.0 |   1.6 |

---

## 6. By side × miss_type (all four types)

| Cell | n | Median captured_bps | Median oracle_net_bps | What this cell is |
|---|---:|---:|---:|---|
| sell_missed_entry           | 1 931 | 134.7 | 162.7 | Saw the setup, didn't open. Dominant cell. |
| sell_opened_pending         |   379 |  87.6 | 159.3 | Opened, hadn't closed yet at snapshot. |
| sell_exit_missed_or_fee_leak|   254 | 146.8 | 153.9 | Opened, exited badly (left edge / paid fees). |
| sell_captured_net_win       |   114 | 160.7 | 255.1 | The actually-realised winners. |
| buy_missed_entry            |   171 |  12.1 |   3.2 | Long setups not opened. |
| buy_opened_pending          |    60 |  13.5 |   3.3 | Long opened, not yet closed. |

The `captured_net_win` row (114 trades) corresponds to the 113-trade universe used in the first version of this report — the audit-driven view shows the same cells with the same microstructure profile (next section), so the previous findings still hold; the new dataset just adds 25× more winners across longs, missed-entries, and pending positions.

---

## 7. Microstructure signals at the extreme bar

Read by side × asset (n's ≥ 38). All values are computed on the unclamped subset.

### Short cover (bar.low extreme)

| Signal | sell_BTC (n=1624) | sell_ETH (n=1054) |
|---|---:|---:|
| `last_aggressor` at extreme = `buy`            | **99.6 %** | 34.6 % |
| `last_aggressor` next bar  = `buy`             | 68.8 %   | 42.9 % |
| `last_aggressor` flip *sell → buy* next-bar    |  0.1 % * | 42.6 % |
| `(bid_qty − ask_qty)/(bid_qty + ask_qty)` med | **+0.264** | +0.489 |
| `(bid_qty − ask_qty)/(bid_qty + ask_qty)` p25 | −0.791   | −0.661 |
| `n_trades` at extreme / 5-bar prior mean       | 1.69×    | 1.53×  |
| `buy_vol_share` at extreme (median)            | 0.25     | 0.04   |
| `buy_vol_share` in 5 bars before (median)      | **0.04** | 0.23   |
| `spread_bps_extreme` median                    | 0.013    | 3.111  |

*\* on BTC the at-extreme bar is almost always already buy-aggressed, so the *sell→buy* flip rate is mechanically zero — see commentary below.*

**BTC short-cover pattern (n=1624, dominant).** The bar that prints the trough is **the bar where a buyer steps in to the low**: `last_aggressor` = `buy` on 99.6 % of trough bars, while the prior 5 bars are 96 % sell flow (`buyvol_share_lb5` = 0.04). So the structure is *persistent seller pressure → one buy print at the low → trough recorded*. Bid/ask imbalance at the trough is positive on median (+0.26, bids loaded) but the IQR runs from −0.79 to +1.00 — the trough fires in two distinct regimes: book bid-loaded (absorbed) or bid-depleted (cleared). Volume on the trough bar is 1.7× the prior 5 — modest cluster.

**ETH short-cover pattern (n=1054).** Much noisier. Aggressor at trough is 65 % `sell` / 35 % `buy`. The cleanest signal here is the *next-bar* flip: 42.6 % of ETH troughs are followed by a buy bar after a sell-aggressed trough bar (vs 0.1 % for BTC by construction). Bid-side imbalance is +0.49 median — slightly more bid-loaded than BTC. Wide-spread bars (median 3.1 bps vs 0.01 bps on BTC) dominate the extreme — ETH troughs frequently print on a spread widening, not on a tight book.

### Long sell (bar.high extreme)

| Signal | buy_BTC (n=38) | buy_ETH (n=193) |
|---|---:|---:|
| `last_aggressor` at extreme = `buy`            | 57.9 % | 69.4 % |
| `last_aggressor` next bar  = `sell`            | 36.8 % | 22.3 % |
| `last_aggressor` flip *buy → sell* next-bar    | 21.1 % | 10.4 % |
| `(bid_qty − ask_qty)/(bid_qty + ask_qty)` med | +0.393 | −0.028 |
| `n_trades` at extreme / 5-bar prior mean       | **3.39×** | **3.04×** |
| `buy_vol_share` at extreme (median)            | **0.986** | **1.000** |
| `buy_vol_share` in 5 bars before (median)      | 0.653 | 0.861 |
| `spread_bps_extreme` median                    | 0.013 | 0.049 |

**Long-sell pattern (both assets).** Peaks form on a **buy-volume burst**: the extreme bar's `buy_vol_share` is near 1.0 on the median trade, and `n_trades` is **~3× the 5-bar prior mean** — a clear volume spike at the top. The run-up is already buy-dominated (`buyvol_share_lb5` ≈ 0.65 BTC / 0.86 ETH) so the peak is a *culmination*, not a reversal punch. The `buy → sell` flip on the next bar fires only 10–21 % of the time, so the cleanest tell is **the volume spike on a near-100 % buy bar**, not an aggressor flip.

### A useful cell: `buy_opened_pending` (n=60) is explosive

These long positions are not closed yet at snapshot. Their extreme bars have **`n_trades_ratio_lb5` median = 58×** — by an order of magnitude the strongest volume-spike cell in the entire dataset. If these turn into realised winners, the long peak is going to print on a very obvious explosion of activity.

---

## 8. Microstructure by pattern_family (where signals diverge)

| Family | n | aggressor=buy at extreme | bidask_imb median | n_trades ratio | buyvol_share at extreme | buyvol_share lb5 |
|---|---:|---:|---:|---:|---:|---:|
| sell_SMALL_MOVE_FADE          | 2107 | 71.6 % | +0.264 | 1.69× | 0.09 | 0.23 |
| sell_SELL_DOWN_CONTINUATION   |  248 | 86.7 % | **−0.791** | 1.02× | 0.55 | 0.04 |
| sell_EXTENDED_UP_SELL_FADE    |  236 | 76.7 % | +0.264 | **2.21×** | 0.09 | 0.23 |
| sell_SMALL_MOVE_FADE_NEIGHBOR |   47 | 91.5 % | −0.791 | 1.02× | 0.84 | 0.04 |
| sell_SELL_SHAPE_WATCHLIST     |   40 | 85.0 % | −0.661 | 1.02× | 0.22 | 0.04 |
| buy_BUY_UP_CONTINUATION       |  148 | 61.5 % | +0.219 | **7.31×** | 1.00 | 0.65 |
| buy_BUY_FADE                  |   45 | 95.6 % | −0.141 | 1.88× | 1.00 | 1.00 |
| buy_BUY_SHAPE_WATCHLIST       |   38 | 57.9 % | −0.237 | 2.14× | 0.98 | 0.84 |

**Family-level reads worth highlighting**
- **`sell_SELL_DOWN_CONTINUATION` troughs are bid-depleted (−0.79)** — the bids get cleared as price grinds down; the trough is the moment after the bid stack is fully eaten. Volume is *not* unusual (1.02×). Contrast with `sell_SMALL_MOVE_FADE` troughs, which are bid-loaded (+0.26) with a modest volume bump.
- **`sell_EXTENDED_UP_SELL_FADE` troughs are the loudest sell cell** — 2.2× volume on the trough bar, suggesting these fade-the-rip trades hit their low on a real flush.
- **`buy_BUY_UP_CONTINUATION` peaks are the loudest cell of all** — **7.3× volume spike**, full buy share, bid-loaded book. Classic blow-off top profile.
- **`buy_BUY_FADE`** is structurally the opposite — peaks form on a bar that's 100 % buy with 100 % buy in the prior 5 — i.e., a steady lift that runs out of room (no flush, no flip). These are the cells most likely to round-trip.

---

## 9. Entry-side audit features at the time of decision

Pulled directly from the audit CSV columns (already snapshotted at `oracle_entry_ts_utc`). These describe what the system saw at entry, not at the extreme.

| Group | trade_present_score | trade_option_readiness | mean_dipole | dipole_acl1 | volume_zscore |
|---|---:|---:|---:|---:|---:|
| sell_BTC | 0 (med) | 55 | +0.071 | +0.031 | **−0.667** |
| sell_ETH | 0 | 58 | +0.055 | −0.061 | **−0.796** |
| buy_BTC  | 45 | 65 | +0.043 | +0.059 | **−0.908** |
| buy_ETH  | 48 | 55 | +0.196 | −0.024 | **−0.897** |

**One consistent entry-side fingerprint:** `volume_zscore_at_entry` is **negative across every group** (median −0.67 to −0.91). Winning trades — long and short — are entered in **below-average volume** conditions. That's worth highlighting: the oracle's after-fees wins systematically come from quiet-tape setups, not high-volume breakouts. (Counter-evidence would change the read.)

`trade_present_score = 0` median on sells means most sell winners are flagged at *no-present-signal* score (early-edge or watchlist state) by the live scoring; buy winners enter with present score ~45–48 (mid-band).

---

## 10. What's NOT in this analysis

- **Single live window (~6 h).** All findings are conditional on the price-bin coverage at run time. Need to re-run when bin coverage spans multiple days.
- **Window-clamping bias.** ~51 % of audit windows extend beyond bin coverage and were dropped from aggregates. Re-aggregation after extending bin coverage backwards/forwards will broaden the universe.
- **Oracle vs venue-tape price reference.** Tape `bar.low/high` is consistently looser than the oracle's chosen price; this is not a model error but a different price object. The MD distinguishes the two consistently; downstream code that wants to *act* on these signals needs to decide which reference to trade against.
- **Per-venue, per-strategy and especially per-(side, asset, venue) cells get thin** below n ≈ 30. The 6-way cube is in `summary.json` for users who want to slice further.
- **No funding / OI / cb-premium join in this pass.** The audit CSV already carries `mean_dipole`, `dipole_acl1`, `volume_zscore`, `trade_present_score`, `trade_option_readiness` at entry; deeper cross-venue feature joins (Bybit OI delta into the extreme, funding turn) would require a second-pass and are not included.
- **Long sample is still small relative to short sample** (231 vs 2 678). The buy-side microstructure is directionally clear (volume spike + near-100 % buy bar) but per-asset/per-strategy buy cells are too thin to publish.

---

## 11. Files

- `analyze.py` — read-only one-shot script (no production code or rules modified).
- `summary.json` — full grouped statistics across all six dimensions + side-paired cuts.
- `per_trade.csv` — one row per winner (5 886 rows) with entry/extreme/exit timestamps and prices, oracle pnl/bps, captured/actual/missed bps, all microstructure fields, all entry-side audit features, and a `bins_clamped` flag.
- `WINNER_EXTREMA_SIGNALS.md` — this report.
