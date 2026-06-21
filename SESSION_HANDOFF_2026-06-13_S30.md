# SESSION HANDOFF — S30 (2026-06-13) — win-oracle collapse root-caused + fixed; dipole = real-but-weak gate piece (no standalone net edge); BACK TO THE PLAN

Live read order for a fresh chat: this file + `KICKOFF_2026-06-13_S31.md` + `CLEANUP_RUNBOOK.md`. Memories auto-load
(`markets-oracle-audit-snapshot-clamp`, `markets-win-lose-pool-provenance-confound`, `dipole-real-on-128dim-per-pair`
(updated S30), `markets-trade-pool-bug-rootcause`). KEEP PAIRS SEPARATE; zero synthetic; each bucket separate.

## FRAMING (Greg, S30): the dipole is ONE PIECE of the architecture
The dipole is a GATE / spread-adjuster in the market-making arch (see `QUOTE_SERVICE_PLAN.md` + the S26 quote-service
note: OD coupling/lead-lag/decoupling/dipole are GATES + spread adjusters, NOT entry signals; the edge lever is the
maker-rebate spread capture). So a negative *standalone* net-of-cost result for the dipole does NOT close anything down
— it confirms the dipole isn't a standalone alpha source, which the plan already assumed. S30 finished the S29 win-oracle
investigation, fixed the data, and pinned the dipole's true (weak) strength. Next: **back to the canonical plan.**

## WHAT S30 DID (the S29 open issue → fully resolved)
1. **Root-caused the win-oracle collapse (S29 TODO#2) at the source.** The audit
   (`research/strategy_evolution/live_mock_replay/live_hindsight_missed_winner_audit_rows.csv`, 21184 rows) computed each
   trade's oracle exit by reading `E:\Markets\live_data` — the **~6h LRU snapshot** (per `markets_bar_loader.py`). The audit
   ran 05-28; every trade entered 05-23/24, so EVERY oracle exit clamped to the 05-28 snapshot edge. Proof: `oracle_entry_ts_utc`
   = 1 constant (05-28 05:50Z), `oracle_exit_price` = 1 snapshot price/venue, `horizon_minutes` = config const (buy360/sell60),
   `oracle_net_bps = sign*(exit/entry-1)*1e4 - 10bps` EXACTLY; real hold (exit_ts - ts_utc) = 3.4–5 DAYS not 1–6h.
   `oracle_entry_price` IS real (bar@ts_utc, verified). So the win **labels** are an audit-RUN-time artifact.
   Memory: [[markets-oracle-audit-snapshot-clamp]]. Generator not in repo (only `api_server.py` reads it); fix = regenerate
   via `markets_bar_loader.load_closes` (history archive).
2. **Fixed the labels** (`_relabel_true_horizon.py`): best-exit within EACH trade's OWN true horizon (`horizon_minutes`),
   from the history archive, −10bps. **17.3% of pool labels flip** (2337 lose→win, 383 win→lose); win rate 10%→22.4%.
   Greg's spec: best-exit, true per-trade horizon for win AND lose, no blanket horizon.
3. **Coefficients confirmed SOUND — no recompute.** The discovery operator window is `[entry_ts−30m, entry_ts]` (pre-entry,
   anchored on real entry); the oracle exit/label never enters it. Each discovery JSON carries its trade `source_id`
   (`result.evidence_graph_metadata.supporting_documents`), so coeffs are **re-partitioned by corrected label** — NOT recomputed.
   Built the index `_extract_coeff_index.py` → `_cs2000_coeff_index.json(.gz)` (also satisfies the dropped S29 TODO#1 compact copy).
4. **Found a SECOND, bigger confound — win/lose pool provenance/temporal mismatch.** WIN pool = 1568 `chunkhash` missed-winner
   opportunities, entry **05-23/24**. LOSE pool = 14181 `slice_..._basis_dislocation_2026-05-18` backtest slices, entry **05-04/11**.
   Disjoint in time AND pipeline → S29's "win-vs-lose" was partly a date/source detector. [[markets-win-lose-pool-provenance-confound]].
5. **CLEAN verdict (both confounds controlled — same-period, same-pipeline, corrected labels, pooled within-pair perm null):**
   a real but WEAK signal survives. 05-23/24 chunkhash AUC 0.67 z=+5.0 (782w/259l); **05-04/11 slice AUC 0.59 z=+13.6**
   (2198w/10895l, 9/12 pairs z>3, null cleanly at 0.50). Robust across two independent universes weeks apart. So the dipole is
   NEITHER the S25/26 +9.6 artifact NOR dead — a weak real edge (AUC ~0.6). [[dipole-real-on-128dim-per-pair]] updated.
6. **Net-of-cost standalone test (`_netcost_backtest.py`, slice, best-exit-trained, walk-forward online centroids, REALISTIC
   fixed-horizon exit):** NO standalone edge. Realistic fixed-horizon exit loses even at 0 cost (ALL mean −4.1bps, hit 34.9%);
   dipole gating does NOT help (edge **−0.74 bps** at every cost level). The AUC-0.6 edge is on hindsight best-exit labels, which
   is uncorrelated with realistic fixed-horizon profit. CONSISTENT with the plan (dipole = gate, not entry signal) and with the
   project's standing net-of-cost nulls. (Did NOT chase matched-objective/discovery variants — not the dipole's architectural role.)

## ARTIFACTS (E:\Markets, scratch unless noted)
- `_relabel_true_horizon.py` (+ `_relabel_true_horizon_results.json`) — corrected best-exit/true-horizon labels per trade.
- `_extract_coeff_index.py` → `_cs2000_coeff_index.json(.gz)` + `_cs2000_coeff_index/` shards — source_id→128-dim coeff (TODO#1 copy).
- `_revalidate_sameperiod.py` / `_revalidate_relabel.py` — clean per-pair + pooled re-validation.
- `_netcost_backtest.py` (+ `_netcost_backtest_results.json`) — walk-forward net-of-cost tradeability test.
- Clean discovery coeffs still at `E:\refrag\discoveries\operator_discoveries\markets_*_preentry_cs2000_clean\` (S29).

## STATUS LINE
Win-oracle collapse: ROOT-CAUSED + labels fixed (relabel). Coeffs: sound (re-partition, no rerun). Dipole: real but weak
(AUC ~0.6), NO standalone net-of-cost edge — as expected for a gate piece. Generator fix (regenerate audit via history archive)
still owed upstream if win labels are ever needed verbatim. Next: BACK TO THE PLAN (`QUOTE_SERVICE_PLAN.md` / OD layer as gates).
