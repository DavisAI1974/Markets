# SESSION HANDOFF — S29 (2026-06-11) — trade-pool bugs fixed + clean discovery rerun + dipole headline CORRECTED

Live read order for a fresh chat: this file + `KICKOFF_2026-06-12_S30.md` + `CLEANUP_RUNBOOK.md`. Memories auto-load
(`markets-trade-pool-bug-rootcause`, `dipole-real-on-128dim-per-pair` (CORRECTED), `s26-async-state`). KEEP PAIRS
SEPARATE; never pool; zero synthetic data; each bucket evaluated separately.

## ENVIRONMENT NOTE (changed from prior assumption)
`E:\refrag` IS mounted/readable in this session — code (`refrag_discovery/`, `adapters/`) + data
(`operator_discoveries/`, evidence graphs). The discovery pipeline (`od_spectral_retrieval_pipeline`) is
**PySR/Julia-free**. So discovery can be rebuilt in-session. BUT the **4-CPU box cannot sustain heavy runs** —
the discovery reruns repeatedly crashed/were killed. Keep runs to the batch-100 + clear-every-graph + parallel
driver, and expect to resume across interruptions.

## WHAT S29 DID
1. **Root-caused both trade-pool bugs at the CODE level** (builder recovered from git history; see memory
   `markets-trade-pool-bug-rootcause`):
   - **Bug 1 (win entry_ts collapse) = a REGRESSION** at `scripts/build_oracle_winner_trade_list.py` L254
     (`entry_ts = oracle_entry_ts_utc or ts_utc` — flipped from the correct `ts_utc`-first; comment deleted).
     FIXED in repo (restored builder + `oracle_winner_trade_memory.py`, ts_utc-first + regression guard).
   - **Bug 2 (strategy duplication, lose ~4.5x) = `oracle_winner_canonical_trade_key` LEADS with strategy_id**,
     so the same physical trade found by the 6 strategy passes never merges. Right dedup key = physical trade
     (`asset|venue|side|entry_ts`).
2. **Built clean deduped pools** — `scripts/dedup_pools.py` → `E:\Markets\research\strategy_evolution\per_bucket_clean\`
   `markets_*_{win,lose}.clean.json` (and driver-ready copies in `per_bucket_clean\`). Win 3104→**1568** distinct,
   lose 53913→**14181** distinct, win/lose overlap 0 all pairs. Win pools sourced from `*_win.fixed_ts.json`.
3. **CORRECTED THE DIPOLE HEADLINE — the z=+9.6 was a DEGENERATE ARTIFACT.** Every non-v2 win discovery bucket
   (cs100/preentry/cs1075) had collapsed to ONE identical coefficient vector — because discovery windows each trade
   by entry_ts, and Bug 1 made every win read the SAME bar window. The permutation null treated 100 identical
   vectors as 100 independent samples → inflated z. (Only `cs100_v2` win had distinct vectors.)
4. **Clean rerun** — non-destructive driver `E:\Markets\_run_clean_rerun.py` (= `_run_top20_bottom20_pairs.py`
   with `PER_BUCKET→per_bucket_clean` + `domain_suffix +"_clean"`). Canary (cs5) confirmed win coeffs come out
   DISTINCT. Full uncapped run (`--cross-section --target-size 2000 --pre-entry --batch-size 100`) →
   `markets_*_{win,lose}_preentry_cs2000_clean`. **23/24 buckets complete** (~14,900 trades); `cb eth sell lose`
   skipped per Greg (1138/1404; machine couldn't sustain). **All 12 win buckets now DISTINCT** (collapse gone).
5. **Honest per-bucket re-validation** (clean same-pipeline, distinct win vs distinct lose, perm-null z, grouped
   no-leak split; EACH BUCKET SEPARATELY): acc **0.62–0.76**, **6/12 buckets z>3** (btc_kraken_sell +7.0,
   btc_coinbase_buy +5.7, btc_kraken_buy +4.5, eth_bybit_buy +3.6, eth_coinbase_buy +3.4, eth_kraken_sell +3.4),
   3 marginal, 3 weak; **algebraic c_quad ≈ 0 (convex dipole surface GONE — only weak LINEAR separation)**.
   Verdict: the dipole is a WEAK, MIXED, per-bucket signal — real in ~half, not the artifact +9.6. Consistent with
   the project's standing net-of-cost nulls.
6. **NEW DATA FINDING — win-side oracle data is collapsed at the SOURCE (deeper than Bug 1).** In the audit CSV,
   for win trades BOTH `oracle_entry_ts_utc` (1779947400) and `oracle_exit_ts_utc` (1779950160) AND the
   `oracle_entry_price`/`oracle_exit_price` are collapsed to a single snapshot window, disconnected from the real
   entry (`ts_utc`, a different/earlier time and price). So:
   - `horizon_minutes` on the win side is stale/uniform (25) and **NOT recoverable from the CSV**.
   - The win **net_bps magnitude / oracle label semantics** may reflect the snapshot-window trade, not the
     real-entry trade — NEEDS upstream investigation before win-side labels are fully trusted. (The win/lose SIGN
     split is still directionally real; the magnitude/window is the question.)
   - A bar-reconstruction (time from real entry to the short's favorable extreme within the scan window) gives
     varying horizons (3–21 min) but does NOT match the oracle's recorded window → the fix is upstream (refrag
     audit), not a field patch. Lose-side horizons are real (varied).

## COEFF LOCATIONS
- **Clean (use these):** `E:\refrag\discoveries\operator_discoveries\markets_*_{win,lose}_preentry_cs2000_clean\` (23/24 buckets; `cb_eth_sell_lose` partial 1138).
- Old/tainted (collapsed-win artifact): `..._preentry_cs100`, `..._preentry_cs1075`, `..._preentry`, base. The validated z=+9.6 was on `preentry_cs100` — do NOT reuse.
- `cs100_v2` win is the only OLD distinct-win set (win-only).
- **NOT yet copied into the Markets git repo** (deferred — see kickoff).

## FILES THIS SESSION (repo worktree unless noted)
- `scripts/build_oracle_winner_trade_list.py` + `oracle_winner_trade_memory.py` — restored, Bug 1 fixed.
- `scripts/dedup_pools.py` — physical-trade pool dedup (writes per_bucket_clean).
- `scripts/dedup_discovery_pools.py` — discovery-JSON schema inspector / dedup tool.
- `E:\Markets\_run_clean_rerun.py` — clean-rerun driver (non-destructive copy; reads per_bucket_clean, writes `_clean` suffix).
- `E:\Markets\research\strategy_evolution\per_bucket_clean\` — clean deduped pools (NOT in git).
- scratch: `_builder_recovered.py`, `_owtm_recovered.py`, `integrity_S29.json`, `_traj_data.json`, `_traj_widget.html`.

## STATUS LINE
Trade data: FIXED for the dipole (clean distinct win+lose coeffs in cs2000_clean). Dipole: weak/mixed (not +9.6).
Open: win horizon + oracle-window collapse (upstream), coeff-copy to repo, cb_eth_sell_lose bucket, temporal split
+ net-of-cost PnL, KB supersede of tainted buckets.
