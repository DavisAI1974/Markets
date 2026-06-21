# KICKOFF — DATA-FIX sub-session (written 2026-06-21, S31) — finish the corrected hindsight audit

**Open this session at `E:\Markets`** (main checkout; repo = DavisAI1974/Markets). `E:\refrag` is mounted (discovery
engine + `markets_bar_loader`). Fragile 4-CPU box — if any discovery rerun is ever needed, `--workers 3`, batch-100, resume.
Sibling session to return to when done: worktree `E:\Markets\.claude\worktrees\suspicious-payne-518711`, branch
`claude/suspicious-payne-518711`. Memories auto-load (see esp. [[historic-trade-data-corruption-inert-for-signals]],
[[markets-oracle-audit-snapshot-clamp]], [[markets-win-lose-pool-provenance-confound]]).

## STATE COMING IN (S31 already did)
The historic-trade-data fix is essentially done; only the audit CSV's `oracle_exit_ts_utc` + the unmatched rows remain.
1. **Platform bins (#1): DONE** — `realbins/*kraken*` spike-flagged + grid-normalized (`bins_integrity.py --normalize`,
   only kraken; coinbase/bybit MUST NOT be normalized — `load_bins` always-zeroes `_suspect`, would destroy their real bursts).
2. **Kraken discovery re-run (#2): VERIFIED NO-OP — DO NOT RUN.** Discovery coeffs are built from **price log-returns**
   (`markets_refrag_adapter` feeds the orchestrator `{source_id: log_returns}` via `load_closes`, mid only). The kraken bug
   duplicates **volume (`n_trades`)**, which never enters the coeffs. The S29 kraken `cs2000_clean` coeffs are already correct.
   (Don't burn the box on the CLEANUP_RUNBOOK "re-run kraken discovery" item — it predates this verification.)
3. **Corrected audit CSV (#3): PARTIAL.** S30's `_relabel_true_horizon.py` recomputed best-exit-within-true-horizon
   net+label per physical trade from the history archive. S31's `_materialize_corrected_audit.py` re-formatted that into the
   audit schema → `research/strategy_evolution/live_mock_replay/live_hindsight_missed_winner_audit_rows.relabel_corrected.csv`
   (original preserved untouched). 11,844 rows corrected (1,568 distinct win trades; winners 11,521→9,891), `+oracle_relabel_status` col.

## WHAT THIS SESSION OWES (the full generator)
Two gaps, both because relabel stored the best NET but not the best-exit BAR, and only covered its clean pool:
- **(A) `oracle_exit_ts_utc` is blank on all 11,844 corrected rows.** The exit *price* is already exact (derived:
  `exit = entry*(1 + sign*(net_bps+fee)/1e4)`, fee=10, buy sign +1 / sell −1, $1000 notional → `pnl_usd = net_bps*0.1`).
  Only the exit *timestamp* needs the argmax bar.
- **(B) 9,340 audit rows (44%) were not in relabel's clean pool** → kept original (clamped) oracle values, flagged
  `unmatched_kept_original`. They need their own entry anchor + best-exit search.

### Cheapest correct path
1. **Modify `_relabel_true_horizon.py`** to also record, per trade, the **argmax exit bar** (`best_exit_ts`, `best_exit_price`)
   from the same forward scan it already does over `[entry_ts, entry_ts + horizon_minutes*60]` via
   `markets_bar_loader.load_closes(asset, venue, t_min, t_max)`. (It already finds the best net; just capture which bar.)
2. **Extend coverage to the 9,340 unmatched `unique_key`s.** They aren't in the clean deduped pools (win 1568 + lose 14181 =
   15749). Anchor their entry on the audit row's real `ts_utc` (NOT the corrupt `oracle_entry_ts_utc`, which is the 05-28
   snapshot clamp — that's the whole bug, see [[markets-oracle-audit-snapshot-clamp]]) and run the same best-exit search.
3. **Re-run `_materialize_corrected_audit.py`** (update it to read `best_exit_ts`/`best_exit_price` from the relabel output
   instead of blanking exit_ts / deriving exit_price). Result: every row corrected, no blanks, no `unmatched_kept_original`.

### Critical guardrail (this is the root cause — don't reintroduce it)
The original audit collapsed because it read exits from `E:\Markets\live_data` (the **~6h LRU snapshot**), so every exit
clamped to the audit-RUN window. The generator MUST take exits from the **history archive** via `load_closes` over each
trade's true `[entry_ts, entry_ts+horizon]`. Note `load_closes` unions the 6h `live_data` snapshot on top of the archive
(`use_live_snapshot=True`); for historic trades (05-04/11/23/24) the archive dominates, but pass an explicit `t_max` so a
stale snapshot can't leak a far-future "exit." Verify a couple of trades' real hold = 3.4–5 days (not 1–6h) as S30 found.

## OUT OF SCOPE (separate, deeper issue — don't conflate)
The win/lose **provenance confound** (win pool = 05-23/24 missed-winner opportunities; lose pool = 05-04/11 backtest slices —
disjoint in time+pipeline) is NOT fixed by this generator. Proper fix = both classes from the same 05-23/24 universe +
discover same-period losers. [[markets-win-lose-pool-provenance-confound]]. Leave it unless explicitly told.

## WHEN DONE
KB propagation (CLEANUP_RUNBOOK policy): copy the finished corrected CSV + the integrity outputs to all 3 KBs
(`E:\refrag\discoveries`, `E:\refrag\docs`, `F:\Factory\knowledge`) and supersede the tainted snapshot. Then the sibling
session (`suspicious-payne-518711`) can pick up the clean data by absolute path — no branch merge needed.
