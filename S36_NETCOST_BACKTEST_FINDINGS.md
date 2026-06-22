# S36 net-of-cost backtest — the flow divergence/exhaustion policy (2026-06-22)

Branch `claude/divergence-exhaustion-backtest-wj65sm`. Decisive test from `KICKOFF_2026-06-22_S36.md` #1:
the 64% reversal hit-rate is only an EDGE if the moves beat fees+slippage. Tool:
`_info_dipole_netcost_backtest.py` → `_info_dipole_netcost_backtest_results.json`.

## Strategy (TREND-FOLLOWING; we KEEP the trend — no detrend)
Greg's frame: markets are mostly follow-the-leader until the leader exhausts → new leader, usually
opposite. So this is a **bidirectional flow policy**, not a pure fade. At each onset, on the strictly
pre-entry 30m order-flow window, `odcore.info_dipole.divergence()` picks direction:
- **FOLLOW** the trend (`dir = +sign(price_drift)`) when flow **CONFIRMS** (`aligned_flow > 0`);
- **FADE** (`dir = -sign(price_drift)`) when flow **OPPOSES** (`aligned_flow < 0`).
Enter at the onset close, exit at the trade's OWN horizon (buys ~4h, sells ~25m). Cost = **5 bps/side**
(round-trip 10 bps, audit convention). PnL = `dir·(P_exit/P_entry−1)·1e4 − cost`. Gate fires pre-entry;
PnL measured post-onset → no look-ahead. Evaluable onsets: 1546/1560.

## Headline verdict
**Pooled, the policy does NOT beat realistic cost — but the flow gate adds real value, and it CLEARS
robustly on the bybit-BTC cells (per-cell deployment, exactly as the platform rule expects).**

| policy (pooled, 10 bps round-trip) | net bps/trade | t | note |
|---|---|---|---|
| FOLLOW_ALL (blind trend-follow, no gate) | −9.01 | −4.8 | baseline |
| **FLOW (follow when confirms, fade when opposes)** | **−5.97** | −3.2 | gate adds **+3.0 bps/trade** over blind follow |
| FLOW_2F (follow only healthy trend) | −5.56 | −3.0 | |
| FADE_GATE (fade only `expect=='reversal'`) | −6.34 | −2.2 | the literal kickoff ask |

- **Breakeven ≈ 4 bps round-trip.** At 0 cost FLOW makes +4.0 bps/trade; the gross edge is real but
  realistic 10-bps cost eats it pooled. (Maker-rebate spread capture — the BUILD_PLAN edge lever — would
  lower effective cost toward breakeven; not assumed here.)
- The flow gate beating blind follow-all by +3 bps/trade confirms the divergence read carries genuine
  directional information; it just isn't large enough to clear 10 bps everywhere.

## Per cell — which cells clear (net > 0), and robustly
Per the platform rule (`deploy-signal-per-cell-not-universal`): keep it where it works.

**Robust survivors (clear net-of-cost AND positive in both walk-forward halves):**
- **btc_bybit_sell** — clears under BOTH policies and both time halves: FLOW +9.1 bps/trade (t=3.1; early
  +4.2 / late +14.1), FADE_GATE +18.6 (t=5.9, 91% win; early +31.5 / late +5.6). The standout.
- **btc_bybit_buy** — clears strongly on the FADE_GATE: +25.7 bps/trade (t=4.6, 75% win; early +31.2 /
  late +20.2, both halves+). Under the full FLOW policy it loses (−8.6) — for this cell the *fade-on-
  reversal* subset is the edge, not trend-following (consistent with the handoff noting btc_bybit_buy as
  the "neutral" divergence cell). Deploy the FADE_GATE here, not FLOW.

**Fragile / do NOT deploy (clear pooled but FAIL walk-forward = single-regime artifacts on thin data):**
- eth_bybit_buy FLOW +37.7 but early +79.7 / late −4.3 (concentrated in one regime half).
- eth_coinbase_buy FLOW +10.8 but t=0.9 (not significant) and early +23.1 / late −1.4.

**Does not clear:** btc_coinbase (buy/sell), btc_kraken (buy/sell), eth_bybit_sell, eth_kraken (buy/sell),
eth_coinbase_sell. Report as "does not clear on these cells", not "failed".

## Caveat (load-bearing)
`test_bars` are **thin**: 1-min bars, ~2 days (05-23/24), ONE trend regime, n≤1560. This is a FIRST CUT.
The single-regime window is exactly why the eth "clearing" cells are walk-forward fragile, and why even
the bybit survivors need confirmation on the **local 1-sec multi-regime onset history** (not in git;
KICKOFF #2). Treat the bybit-BTC clears as promising, not deployment-grade, until that confirmation.

## Bottom line
The 64% reversal rate is real but does NOT, by itself, clear 10-bps round-trip cost pooled — the moves
are too small. The flow gate genuinely improves on blind trend-following (+3 bps/trade), and the edge
DOES clear net-of-cost, robustly across both walk-forward halves, on **btc_bybit_sell** (both policies)
and **btc_bybit_buy** (fade gate). Deploy per cell on those, gate live use on the 1-sec multi-regime
confirmation, and let maker-rebate execution lower the cost floor.
