---
name: kalshi-backtest
description: The mandatory discipline for ANY Kalshi backtest, signal evaluation, or dataset build — leakage gate first, settle-window exclusion, per-cell never pooled, distributions and per-trade fingerprints never means, net-of-fee at maker AND taker. Use before building or judging any predictive result on Kalshi data.
---

# Kalshi backtest discipline

These are Greg's load-bearing rules (S80–S82). A result that skips any step is not a result.

## Gate 0 — leakage, before anything runs

- Every context/feature closure must be strictly PRE-event and pass the leakage gate
  (`odcore/leakage.py` pattern: perturb/append FUTURE rows, assert the context is byte-invariant).
- Existing harnesses to copy from: `research/kalshi/level_hit_dataset.py` (context closure over
  the last N trades, gate PASS 0-fails) and `release_book_signal.py --selftest` (30/0).
- If the gate cannot be written for a design, the design is wrong. Do not "check later".

## Gate 1 — exclude the settle window

- Drop all events/trades inside the settlement window (the `SETTLE_UTC` guard in
  `release_signal_history.py`). Settlement-window prints are mechanical, not signal.
- Forward outcomes must be BOUNDED by the daily-settle exclusion (a trailing exit cannot run
  through settle).

## Rule 1 — per cell, never pooled

- Cells for tape/level work: moneyness × side × velocity-regime × release.
- Cells for weather: regime (calm/transition minimum) × city × synoptic season × bucket-moneyness
  × swing-dir.
- Report per-cell tables. A signal surviving on a SUBSET of cells is KEPT for those cells —
  partial coverage is not failure. Say "works on {X}, not {Y}", never "X failed".
- Pooling across cells manufactures nulls out of real structure (the S24 collapse). A pooled
  number may appear ONLY as a footnote after the per-cell table, never as the headline.

## Rule 2 — each trade individually, never average

- No pooled hit-rate, mean signed-bps, or averaged coefficient as the primary readout.
- Report the DISTRIBUTION (quantiles, pos_frac, run-length histogram) and the winner
  FINGERPRINT (feature shares among winners minus base rate), per cell.
- Any summary must preserve per-trade distinctiveness, never collapse it.

## Rule 3 — net of fees, both legs

- Kalshi fee: `round_up(0.07 * C * P * (1-P))` per contract per taker leg. Score every result
  at TAKER and at MAKER; a signal that only pays at maker carries fill-risk and must say so.
- Direction is the easy part — the recurring finding (S81, S82) is the edge is SIZE-vs-FEE.
  A hit-rate without a size-vs-toll distribution is not an edge.

## Rule 4 — honesty of the readout

- Zero synthetic data, ever. Provisional-until-live — a backtest edge is a hypothesis.
- A clean negative that sharpens the program (e.g. S82: "no cell pays at maker") is a real
  deliverable; write it up in a `*_FINDINGS_*.md` under `research/kalshi/` and index it in
  `KALSHI_TRADING.md`.
- Weather: the FORECASTER is Greg's spec — HANDS OFF. We only score, through
  `research/kalshi/kalshi_score.py`, per regime, vs the baselines in
  `research/kalshi/WEATHER_BASELINE_S82.md`.
- `--events` on `news_coupling_research.py` is a BASENAME joined onto `--data-dir`, not a path.
