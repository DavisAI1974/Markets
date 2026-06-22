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

## Exit management — ditch the horizon, ride until price reverses, flip-or-flatten (Greg, S36)
`_info_dipole_trailing_backtest.py` → `_info_dipole_trailing_backtest_results.json`. Greg's directive:
no clock; a trade ends ONLY on an adverse price move; then the dipole says go-long / go-short / flatten.
Built two horizon-free exit engines (both look-ahead free): **PRICE-stop** (trailing backslide off the
peak favorable excursion — "+50 peak, 10% → exit +45") and **DIPOLE-exit** (exit when order-flow imbalance
flips against the position). At each exit the dipole flips (if it confirms the reversal) or flattens.

Result on this data — **both underperform the fixed-horizon hold**, pooled net bps/trade @ 10 bps/leg:

| | pooled net | note |
|---|---|---|
| fixed-horizon FLOW (hold) | −5.97 | baseline |
| PRICE-stop + flip (horizon-free) | −11.40 | |
| DIPOLE-exit + flip (horizon-free) | −22.29 | more legs → more cost |

**Why (the decisive diagnosis):** on **1-min bars** a reactive stop is whipsawed — average hold collapses
to ~19–50 min and the stop fires on ordinary intra-trend pullbacks before the move develops, paying 10 bps
per leg each time. The clearest case is exactly the cell Greg flagged: **eth_bybit_buy's early +79.7
(fixed-horizon) is DESTROYED by trailing** (early +2.3 price-stop / +16.9 dipole-exit) — the trailing stop
exits the big winning ride early. The fixed-horizon only "won" there by blindly holding through one big
~4h trend leg that happened in this 2-day window (a single-regime artifact). A 10–30 bps trailing stop
cannot tell a healthy 1-min pullback from a reversal.

**This is a data-resolution problem, not a logic problem.** Greg's ride-and-trail-and-flip idea is sound
but is **untestable and untunable on 1-min / 2-day / single-regime data** — it needs the local **1-sec
multi-regime onset history** (KICKOFF #2) where (a) a trailing stop isn't tripped by single-bar 1-min
noise, (b) there are many trend legs so we aren't fitting one, (c) far more independent events. The exit
engine (price-stop and dipole-exit, with flip/flatten) is built and ready to point at that data; **do not
tune its parameters on the 2-day window** (overfitting). Getting the 1-sec history is now the gating step
for the whole exit-management question.

## Swing model — buy valleys / short peaks, flip at each turn (Greg, S36)
`_info_dipole_swing_backtest.py` → `_info_dipole_swing_backtest_results.json`. Greg's model: markets
oscillate; go long at the valley as it turns up, short the peak as it rolls over, flip at each turn, no
clock. Enter AT the turn, never the backside. Min tradeable swing = the one that beats the round-trip fee
(10 bps), so I sweep swing size (ZigZag threshold θ) rather than guessing it. Three layers per venue series:
ORACLE (perfect pivots = ceiling), DIPOLE (real-time turn detector = the edge), PRICE-CONFIRM (backside baseline).

**1. The opportunity is REAL and large — oracle confirms Greg's thesis.** Perfect swing-trading nets, over
the ~2-day window, thousands of bps per venue, and the swings beat the 10 bps fee by a wide margin:

| θ (reversal) | mean swing | net per swing (after 10bps) | oracle net total (eth_kraken) |
|---|---|---|---|
| 10 bps | 27.9 bps | +17.9 | +6,478 over 356 swings |
| 20 bps | 49.8 bps | +39.8 | +5,715 over 158 swings |
| 50 bps | 140.6 bps | +130.6 | +3,163 over 27 swings |

If you catch the turns, the swings pay 3–13× the fee. The opportunity is exactly as Greg drew it.

**2. The whole game is entry accuracy at the turn — and every real-time detector enters on the BACKSIDE.**
At θ=20 bps (mean swing ~50 bps), every detector loses, because each enters ~15–27 bps off the true turn:

| venue | oracle net | dipole CROSS (entry off) | dipole EXHAUST (entry off) | price-confirm |
|---|---|---|---|---|
| btc_bybit | +1,932 | −470 (~22 bps) | −820 (~18 bps) | −324 |
| eth_coinbase | +3,798 | −280 (~25 bps) | −152 (~18 bps) | −1,379 |
| eth_kraken | +5,715 | −1,623 (~21 bps) | −1,645 (~17 bps) | −2,122 |

Capture% is **negative** everywhere. You give up ~15–20 bps entering late + ~15–20 exiting late + 10 fee,
which swamps a ~50 bps swing.

**3. It's DETECTOR LAG, not bar granularity.** 1-min bars move only **~2–4 bps each** (p90 ~6–8 bps), so
the turn *is* catchable within a few bps — but the order-flow dipole, in every form tried (imbalance
sign-cross AND S36 exhaustion/collapse, full window/threshold grids), confirms the turn only ~15–20 bps
*after* price already turned. A trailing flow signal on 1-min buckets is structurally late; a shorter
window just whipsaws (more flips, more fees) without getting closer. Exhaustion (the S36 "dipole → 0.5")
helps a little (entry off 27→18 bps on some cells) but not enough to clear cost.

**4. What this says we need.** The swing edge is real (oracle) and the dipole is the right *kind* of turn
detector, but on 1-min data it fires ~15–20 bps late. The flow's roll-over at a turn is smeared across
1-min buckets; at **1-sec resolution** the exhaustion at a turn resolves within seconds, so the dipole can
fire *at* the turn instead of 15 bars later. To clear cost we need entry-lag below ~(swing/2 − fee); on a
50 bps swing that's <~15 bps, which 1-min data cannot deliver and 1-sec plausibly can. **This makes the
local 1-sec multi-regime onset history (KICKOFF #2) the gating resource for the entire swing strategy** —
the oracle proves the money is there; closing the entry lag is the build, and it needs 1-sec bars.

## Bottom line
The 64% reversal rate is real but does NOT, by itself, clear 10-bps round-trip cost pooled — the moves
are too small. The flow gate genuinely improves on blind trend-following (+3 bps/trade), and the edge
DOES clear net-of-cost, robustly across both walk-forward halves, on **btc_bybit_sell** (both policies)
and **btc_bybit_buy** (fade gate). Deploy per cell on those, gate live use on the 1-sec multi-regime
confirmation, and let maker-rebate execution lower the cost floor.
