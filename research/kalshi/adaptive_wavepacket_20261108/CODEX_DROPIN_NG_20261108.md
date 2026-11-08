# CODEX DROP-IN - HENRY HUB NG: ADAPTIVE LOCALITY ENGINE, PRE PAPER-TRADING REVIEW

**Current NG discovery handoff.** Use the [standalone discovery plan](markets_bridge/tasks/plan.md) on `codex/ng-shadow-discovery-20261108`. Git is the durable source of truth. Use a repository-backed workspace without a dependency on C:, E:, or desktop copies. October 3 and October 18 are both discovery evidence. Complete the October 3 comparison before paper orders. The migration-era instructions below are retained as historical provenance.

Repository: DavisAI1974/Markets
Branch: research/markets-adaptive-wavepacket-migration-20261108
Read first, in order:
1. research/kalshi/adaptive_wavepacket_20261108/CODEX_HANDOFF_NG_20261108.md  (what is built, what is not, how to run and read it, carry-forward criteria)
2. research/kalshi/adaptive_wavepacket_20261108/CCODE_INDEPENDENT_REVIEW_20261108.md  (findings, math derivations, fix status)
3. research/kalshi/adaptive_wavepacket_20261108/working_tree/FIX_LOG_20261108.md  (one line per fix with its proving test)
4. CLAUDE.md trading rules (top of the section): trade cost is not a market condition.

Your assignment
- Run the NG days you have been using through the engine, one day at a time, never pooled:
    PYTHONPATH=.:research/kalshi:research/kalshi/adaptive_wavepacket_20261108/working_tree \
      python3 -m research.kalshi.adaptive_wavepacket_20261108.markets_bridge.ng_runner \
      --calibrate-from-day <prior day> --day <d1> --day <d2> --day <d3> --source local --out <dir outside git> --mark-utc 14:30
  Days must be cached under data/nymex_cont/ as NG_YYYYMMDD.jsonl.gz (the repo's own loader format).
- Read <dir>/<day>/summary.json per day and <dir>/replication.json across days. Tell Greg whether running the
  historical data through this strengthens or finds trade signals worth testing in the paper environment, using
  the six carry-forward criteria in handoff section 5. A candidate is an entropy-change association that may
  sharpen the WHEN and the hold length on top of the S92 direction nowcast; it is not a direction call.
- Report what did NOT survive with the same care as what did; every abstention is in the SQLite registries with
  its reason (ResearchHoldRegistry.get(case_id)).

Rules that bind
- Zero synthetic trading data. Leakage gate before any backtest (passed for these fitters; re-run if you change
  them). Settle window excluded (21:00 UTC, 1800 s guard, default in the runner). Each day and event
  individually, never averaged. Distributions and per-trade fingerprints, never means.
- NO TRADE COST IN ANY CALCULATION: no fee, slippage, maker/taker offset or execution assumption anywhere in
  research, forecasts or outputs. Nothing from the crypto-era trade strategies; only the dipole toolkit carries over.
- Provisional until live. Launch is HOLD. Nothing scientific is dropped.
- Do not edit research/kalshi/adaptive_wavepacket_20261108/buildmap_source_snapshot/ (frozen provenance). Work in
  working_tree/ and markets_bridge/. Do not merge, deploy, or touch AWS, Frankie or Search.

State you inherit
- Status note: the NG workflow (ng_runner.py) is complete in code and under a final double-check; everything
  else here is done except the items noted (no real NG day run yet, Kalshi channel untested on data, Frankie
  adapter later, no AWS work). Git-workflow checks passed at 0456eca. PR open:
  https://github.com/DavisAI1974/Markets/pull/12 (fast-forward onto the trunk).
- 133/133 BuildMap files migrated byte-exact; all review findings fixed with tests; engine 87+31+engineering
  Python tests, Node 183, bridge 10 green; lag_join.py and coach_replay.py selftests pass; the real-day NG test
  skips until a day is cached. No real NG data has been through the engine yet: that first run is yours.
