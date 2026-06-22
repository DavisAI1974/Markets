# SESSION HANDOFF — S41 (2026-06-22) — book-layer (liquidity+flow+price) lead/lag + 5-step coupler runs

Branch `claude/crypto-backfill-validation-31tubb` (all pushed). Data + methods only.

## Data
- `realbins/` (6 cells, gitignored): btc/eth × {bybit_perp, coinbase, kraken}, 1-sec. btc_bybit_perp 536,391s (149h); eth_bybit_perp 925,284s (257h).
- Book file `data/btc-book` branch -> `btc_coinbase_book.jsonl.gz`: 209,998 records, median 100ms, 5.83h, 0 gaps >1s. Per record: `ts, mid, spread, bids[[offset,size]×10], asks[[offset,size]×10], buy, sell, n_trades`. Carries liquidity (bid/ask depth), executed taker flow (buy/sell), price (mid) on one grid. Copied to `research/od_book/chat_runs/OD_book_run_1.docx` is Chat's external run (below).

## Docs
- `BUILD_PLAN.md`: S37–S40 folded in (S40 architecture block + PART 5). Commit 0c2f511.

## Tools built + results
### `_birth_probe.py` — lead/lag of book liquidity / flow / price (5.83h book, 100ms)
Method: grid to 100ms (book fields last-in-cell ffill; flow summed). LIQ_K=(Σbid−Σask)/(Σbid+Σask), top-K∈{1,3,5,10}; FLOW=trailing-W(buy−sell)/(buy+sell); PXV=Δlog(mid). Normalized cross-correlation over ±5s; event-aligned (sign-aligned) at top-0.1% |PXV| onsets (168 onsets, ±5s).
- LIQ→FLOW peak r≈+0.14 at +0.7..0.9s (K=1..10). LIQ→PXV peak r≈+0.12 at +0.1s. FLOW→PXV peak r=+0.106 at 0.0s. dLIQ→PXV peak +0.06..0.07 at +0.1s, r@0 negative.
- Event-aligned means: LIQ(K5) pre-onset +0.170 / post +0.029; FLOW pre +0.072 / post +0.246; price ~0 pre.

### `_od_book_run.py` — OD engine on 4 channel pairs (windowed_operator_matrix + analyze_coupling + PySR)
window=40 (4s) stride=10, 20,996 rows. analyze_coupling per pair (structured flag, mi_frac, eq_entropy_frac, chem_residual_frac, mi_slope_r2, singular_gap). PySR via symbolic.discover (niter 40) for MI and H_a^2.
- buy/sell: structured=False, eq_entropy_frac 0.660, mi_frac 0.012, mi_slope_r2 0.109.
- bid_dep/ask_dep: structured=False, mi_frac 0.9997, mi_slope_r2 0.011, eq_entropy 0.0001.
- bid_dep/buy: structured=False, mi_frac 0.999, mi_slope_r2 0.0375, mi_mean 0.022.
- buy/abs_return: structured=False, eq_entropy 0.812, mi_frac 0.0003.
- PySR: H_a^2 → square(H_a) (loss ~1e-11; feature set included H_a → degenerate). MI: buy/sell `cube(H_a·H_b·0.036²)` loss 0.795 vs const 1.023; bid/ask `≈0.548` (const) loss 0.066 vs 0.069; bid/buy `H_a²·0.00036` loss 0.0077; buy/absret `≈0` loss 0.973.

### `_rolling_coupler.py` — full 5-step coupler (trade_coupling_vector, all 5 steps), rolling
Window 3000 cells (5min), step 300 (30s), 690 windows. a=signed depth-imbalance(K5), b=price return. Per-window also: quiet_frac (fraction n_trades=0), realized vol (std ret), relax_r2 (in-sample AR(1) fit of imbalance).
- leadlag (step 4) sign: >0 (a leads b) 75.5%, <0 2.8%, =0 21.7%. mean +0.69 cells (+0.07s), median +1.0.
- corr(leadlag, quiet_frac)=+0.058; corr(leadlag, vol)=−0.043; corr(leadlag, relax_r2)=+0.002. mean quiet_frac @lead 0.828 / @lag 0.875; relax_r2 @lead 0.873 / @lag 0.920.

### `_dipole_trend_follow.py` — hysteresis trend-follow on the dipole lean
position = +1 if lean≥thr, −1 if lean≤−thr, else carry; lean=trailing-W(buy−sell)/(buy+sell), W=300s; fee 10bps/flip; pnl = Σ pos·Δlog(mid)·1e4 − flips·fee. realbins btc/eth bybit_perp, thr∈{0.05,0.10,0.15,0.20,0.30,0.40}.
- btc_bybit_perp: buy-hold +148 bps. gross −398..−1479 (negative all thr); net −4,189..−16,922; flips 381..1576; in_mkt 1.00.
- eth_bybit_perp: buy-hold +111 bps. gross −610..−1929; net −6,469..−24,629; flips 576..2270.

### `_coupling_scan.py` — agnostic 5-step scan over book channels (no imposed direction) [running at handoff]
Channels: bid_depth, ask_depth, taker_buy, taker_sell, abs_return, volume (K=5). score_pair (5 steps + circular-shift tautology null, n_null=20; leadlag n_null=100) over 15 pairs, window=40 stride=20; rank by rank_score. Output `_coupling_scan_results.json` + `_coupling_scan.png`.

### `_diag_flip_states.py` (reproduced)
buy/sell leave-one-out mirror accuracy 63.5% (n=1400, 14-cell coeff basis). corr(margin, |mean_dipole|)=+0.019, |imb_level|=−0.006, |trade_from_onset|=−0.043, net_bps=+0.059. correct vs wrong-class |feature| means near-identical.

### `_trend_gate.py` — price-primary turn trigger + dipole filter (built, not validated)
price ZigZag pivots (primary); dipole filter via midline cross / pivot trend-line break / fast+deep override. WIP commit 9627af2; superseded direction by the agnostic-scan approach.

## Chat external run — `research/od_book/chat_runs/OD_book_run_1.docx`
Method: linear first-order operator X[t+1]=φ·X[t]+c, OLS, 60/40 train/OOS, rolling 3000/300.
- ret(t+1) ~ {imb,top_imb,ofi,ret}: OOS R² 0.0445.
- imb(t+1) ~ imb: OOS R² 0.865, φ=0.936, half-life 10.53 steps (1.05s).
- Decimation: φ 0.936→0.166, OOS R² 0.865→0.023 over step 0.1s→10s.
- Quiet (n_trades=0, n=169,532): φ 0.947, R² 0.904. Trade (n=40,465): φ 0.883, R² 0.726.
- imb→fwd price: R² 0.024..0.035, dir acc 0.126..0.421 (horizon 0.1..3.0s).
- Loudness (1−R²) vs realized vol cross-corr: 0.51..0.83, peak at lag −2.0min.
- Operator stress → fwd vol | current vol removed: corr −0.002.
- Local lead/lag (loudness vs vol, 20-min): operator leads 18.9%, lags 58.9%, lag std 4.94 windows; mean |fwd move| leading 7.98e-4 / lagging 9.93e-4.

## Commits
0c2f511 (BUILD_PLAN), 9627af2 (_trend_gate WIP), fa1e7ad (_birth_probe), 45c1209/8136111/d7ea08c (_od_book_run + PySR), 6fdd2c4/7a439ea (_rolling_coupler), bc95* (_dipole_trend_follow), 60b986b (_coupling_scan). PNGs gitignored.
