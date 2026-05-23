# Refrag Evolution Handoff - Continue From Hour 48

Date: 2026-05-17

## Next Step

Continue Refrag strategy evolution from historical hour `48`.

Recommended command:

```powershell
python run_strategy_evolution_workflow.py --start-hour 48 --hours 6 --iterations 1 --all-families-until-hit --passes-per-family 1 --min-context-family-samples 3 --winner-pnl-r-floor 0 --winner-min-trades 1
```

## Current Rules

- Use usage-triggered evolution only, not timed workflow evolution.
- Run one full active-family sweep per 6-hour historical slice.
- Do not restart historical data unless fixing a current-slice behavior bug.
- Reporting or booking label fixes do not trigger reruns.
- Every possible learning/probe trade is logged as full-bank hypothetical evidence using the `$10,000` starting bank.
- Capital/exposure must not suppress evidence logging.
- Actual/booked PnL only includes positive exact-context winner routes and real broker/exchange/platform fees if charged.
- Research evidence outcomes can be negative and are learning input only.
- Zero-trade windows are valid evidence and must produce JSON attempts/candidates.
- Every 6-hour slice must produce an analysis paper.
- `PRESSURE_CONTINUATION` remains disabled and out of active candidates.

## Evidence Vs Execution Fields

- `notional` / `hypothetical_notional`: simulated full-bank evidence size.
- `actual_execution`: whether anything was really bought or sold.
- `actual_notional`: real executed notional, `0.0` for paper/evidence.
- `actual_side`: side that would be or was executed.
- `learning_capital_model`: evidence sizing model used to interpret the record.

## Last Completed Slice

Hours `42-48`.

- Summary: `E:\Markets\strategy_evolution_workflow_runs\workflow_summary_20260517_020316.json`
- Analysis paper: `E:\Markets\strategy_evolution_workflow_runs\analysis_paper_20260517_020316.md`
- Winner route: none
- Actual executable PnL: `$0.00 / +0.00R`
- Research evidence outcome, not booked PnL: `-$135.43 / -12.74R`
- Evidence trades simulated: `12`
- `NEWS_BREAKOUT`: `9` evidence trades, `-$170.76 / -17.16R`
- `BASIS_DISLOCATION`: `2` evidence trades, `+$63.98 / +8.00R`
- `RELATIVE_STRENGTH`: `1` evidence trade, `-$28.66 / -3.58R`

## Post-Handoff Patch Already Applied

- `run_strategy_evolution_workflow.py` now labels probe losses as research evidence, not booked PnL.
- Existing 36-42 analysis paper was rewritten with corrected labels.
- Existing 36-42 summary metadata was updated with `analysis_paper`.
- No rerun was done for that reporting fix.
- `run_strategy_evolution_workflow.py` now records compact `mock_trades` rows in workflow summaries and renders a "Mock Trades Opened" table in analysis papers.
- Existing 42-48 summary and analysis paper were backfilled from existing slice outputs only; no rerun was done for that reporting fix.

## Verification Already Run

```powershell
python -m py_compile run_strategy_evolution_workflow.py backend\api_server.py mock_trade_replay.py
```
