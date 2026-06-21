# SESSION HANDOFF — S34 (2026-06-21) — Path C ran (dipole de-confounds to weak/null); the asset is per-cell EXACT coeffs + a strong MICRO signal + STACKING; Direction-2 meat run IN PROGRESS

Worktree `E:\Markets\.claude\worktrees\xenodochial-montalcini-f21fb6` (branch
`claude/crypto-trading-platform-plan-MpqwG`). Read order: `CLAUDE.md` (S34 delta top) → this
file → `KICKOFF_2026-06-21_S35.md` → `BUILD_PLAN.md`. Memories auto-load:
`tools-are-complementary-not-competing`, `markets-dipole-deconfound-verdict-s34`,
`deploy-signal-per-cell-not-universal`.

## SCOPE (unchanged, hard)
Crypto trading platform per `BUILD_PLAN.md` only. Quote service OUT. Zero-synthetic = no
synthetic *trading* data. Per-cell deployment. **NEW standing rule: tools are COMPLEMENTARY, not
competing — evaluate by stacking; even a 5% net edge is huge.**

## ARC OF THE SESSION
1. **Ran the S30-built-but-never-run Path-C pipeline** (de-confound): `_extract_coeff_index.py`
   (→ `_cs2000_coeff_index\`) → `_relabel_true_horizon.py` (→ `_relabel_true_horizon_results.json`;
   best-favorable-exit within each trade's own horizon from `live_data_history` via
   `markets_bar_loader`) → `_revalidate_sameperiod.py`. Construction: take ONLY the 05-23/24
   chunkhash winner coeffs (one pipeline), relabel → 383/1568 winners flip to lose → same-period,
   same-pipeline win+lose. Kills the date/provenance confound AND the oracle-label corruption.
2. **Dipole-separation result (SECONDARY question): 0/12 cells survive the within-period 500-perm
   null** (SEED=1974; verified bit-EXACT on single-cell re-run). The confounded AUC ~0.67-0.72 was
   substantially a date/source detector; `c_quad` sign-inconsistent (no consistent algebraic dipole).
   `z=+9.6` + confounded OD-AUC SUPERSEDED.
3. **Greg's two reframes (load-bearing):**
   (a) **Per-bucket EXACTNESS is what matters, not dipole strength.** Verified: per-cell 128-dim
       coeffs are bit-reproducible AND isolated (0 cross-bucket bleed, 0 foreign-pair trades, ~95%
       distinct) → a validated per-cell OD fingerprint, intact regardless of the weak dipole. Win
       data COMPLETE (100%+ vs the cross2000 discovery lists; the earlier "82%" was a denominator
       error — divided by the 1568 dedup-bucket total, not the eligible-list total).
   (b) **Tools are COMPLEMENTARY, not competing** (`tools-are-complementary-not-competing`).
4. **Stacking test (`_stack_deconfound.py` → `_stack_deconfound_results.json`):** on the
   de-confounded universe, per cell, DIPOLE vs MICRO vs STACK (5-fold OOF AUC). Findings:
   - **Micro features (`mean_dipole, dipole_acl1, volume_zscore, trade_present_score,
     trade_recent_2chunk_bps, trade_from_onset_bps`) are the strong, real signal** — AUC **0.72-0.84**
     on 5 cells (btc_bybit_sell 0.81, eth_coinbase_buy 0.844, btc_coinbase_sell 0.726,
     btc_kraken_sell 0.723), de-confounded (same period, not the date confound).
   - **Not redundant:** dipole leads on eth_bybit_buy (0.845 vs micro 0.659); micro leads elsewhere.
   - **STACK adds +0.024..+0.029 AUC on 4/10 cells** (btc_bybit_buy, btc_coinbase_buy,
     btc_kraken_sell, eth_coinbase_sell) → orthogonal info. Where it hurts = small-n overfit.
   - **The per-cell STACK is the product**, with micro as the base and the coeff dipole a contributor.
5. **Net-of-cost (`_netcost_backtest.py chunkhash`):** only btc_kraken_sell had enough same-period
   losers to pass walk-forward `MIN_TRAIN=40`; there the dipole gate was slightly negative. ⇒ the
   thin lose side blocks net-of-cost too. Motivates Direction 2.

## DIRECTION 2 — IN PROGRESS (discovery RUNNING in the S34 chat at handoff time)
**Goal:** add lose-side meat so every cell can be tested with a real null + net-of-cost. The
de-confound was lose-starved because only the missed-winner subset (1240) ever got coeffs. The
05-23/24 audit holds **3,991 more same-period trades** (no coeffs); **2,645 pass the pre-entry
`min-returns≥192` gate**; capped at **~150/cell (~1,669 trades)**.
- **Built:** `_build_sameperiod_cand.py` → per-cell candidate buckets `_sameperiod_cand\markets_<pair>_cand.json`;
  capped eligible lists `_sameperiod_cand\lists\markets_<pair>_cand.cap150.json`.
- **Running:** `_run_sameperiod_cand.py --workers 4` — PARALLEL (~45-55min). Writes to isolated
  domain `markets_<pair>_win_cand_sp\`. Batch+resume; resume fast-skips done cells. Launched DETACHED
  as Windows scheduled task **`markets_cand_disc`** (`_run_cand_detached.bat`) so it survives the chat/app
  closing (harness `run_in_background` dies on session teardown). Check: `schtasks /query /tn
  markets_cand_disc`; log `_pipeline_logs\_cand_driver.out`. Delete task when done: `schtasks /delete
  /tn markets_cand_disc /f`.
- **PARALLEL ENABLED via a SHARED-REFRAG EDIT (recorded here):** the WinError 5 race was
  `os.replace` in `E:\refrag\refrag_discovery\control_plane\storage.py::save_json` — patched to RETRY
  on the transient Windows lock (40×0.05s backoff; added `import time`). Validated: 4×80 concurrent
  replaces on one shared file → 0 PermissionErrors (`_racetest.py`). A SECOND race on
  `E:\refrag\discoveries\index.json` (`discovery_index_writer.py`) is COSMETIC and left as-is:
  last-writer-wins by design + rebuildable by directory scan; coeffs are written BEFORE the index
  update and survive it (verified on disk); ALL our analysis reads coeffs directly from the domain
  dirs, never from index.json. NOTE: storage.py is shared by 4+ sessions — the edit is purely
  additive resilience (retry-on-transient-lock), backward-compatible.
- **WHEN DONE:** `_balanced_rerun.py` — merges existing 1240 + new cand_sp coeffs, relabels
  candidates by true-horizon, pulls micro from the audit, re-runs per cell: dipole (AUC+perm null)
  + dipole/micro/STACK + lift, on the balanced pools → `_balanced_rerun_results.json`. Then
  net-of-cost on the stack for the "5% edge" bar.

## DATA / ISOLATION FACTS (verified S34)
- Same-period universe = 05-23/24 audit, 5,231 unique trades. Had coeffs: 1,240. New eligible: 2,645.
- Buckets cleanly isolated: 0 shared source_ids across buckets, 0 foreign-pair trades.
- Lose-side thinness is intrinsic (relabel ~21% on a winner-heavy missed-winner set), not coverage.
- The 05-04/11 slice lose pool is the CONFOUNDED, wrong-period set — NOT used by the de-confound.

## ENV / RULES
- Did NOT branch-switch shared `E:\Markets`. No commit/push (not requested). PySR/Julia not needed.
- Discovery can now run PARALLEL (`--workers 4`) after the storage.py retry fix. Pure-numpy analysis CAN run
  alongside discovery (no control-plane contention).
