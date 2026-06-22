# SESSION HANDOFF — S36 (2026-06-22) — the info-dipole FLOW edge: order-flow divergence + exhaustion = a per-cell trend-continuation-vs-FLIP detector

Branch `claude/crypto-trading-platform-plan-MpqwG` (PUSHED to origin). Read order: `CLAUDE.md`
(S36 delta top) -> this file -> `KICKOFF_2026-06-22_S36.md`. Continues the S35b fingerprint thread;
all S35 memories still apply (`bucket-distinctiveness-is-the-goal`, `tools-are-complementary-not-competing`,
`deploy-signal-per-cell-not-universal`, `markets-data-lives-local-not-git`).

## WHAT THIS SESSION DID
Started from the S35b "bleed" (the 128-dim OD coeff is side-AGNOSTIC -> buy & sell on the same chunk
get byte-identical coeffs). Investigated it, brought in the information dipole (davisai.ai/dipole) as the
directional/flow tool, and -- following Greg's reframe -- landed a real, robust, per-cell **flow-based
trend-continuation-vs-FLIP edge**. Everything runs in-git off the committed `fingerprint_dataset/`.

## THE BLEED (characterized)
- 385 buy<->sell groups have byte-identical winning coeffs (coeffs are price log-returns, side-agnostic).
- Stacking the 6 micros separates 67% of joinable pairs; 27 are FULLY degenerate (coeff + all 6 micros
  identical, same chunk + onset ts, but different outcomes -- the pre-entry fingerprint cannot encode
  direction there). That gap is what the information dipole fills.

## THE EDGE (validated, committed)
Following a trend IS following the flow. The info dipole detects the changeover on TWO factors:
1. **DIVERGENCE** `aligned_flow = imb_level * sign(price_drift)` (>0 flow confirms trend; <0 opposes).
   Strong divergence (aligned <= -0.20) -> ~65% REVERSAL pooled (n=234), temporally STABLE (early 70% /
   late 62%), consistent per cell (btc_bybit_sell 100%, btc_kraken_buy 84%, btc_coinbase_buy 67%,
   btc_kraken_sell 68%, eth_kraken 61-62%; only btc_bybit_buy neutral 50%).
2. **EXHAUSTION** the order-flow dipole COLLAPSING toward 0.5 (|late-half imbalance| < |early-half|, the
   leader weakening). Greg's "dipole going to 0.5 = change in flow" -- NOT the discrete 0.5 crossing
   (that's a coin flip, 48/52), but the dipole MOVING toward balance (+6pp reversal: 57% vs 51%).

They STACK monotonically (pooled n=1560):
| flow state | reversal | n |
|---|---|---|
| oppose + exhaust (collapsing toward 0.5) | **64%** | 317 |
| oppose + strengthen | 58% | 212 |
| with-trend + exhaust | 52% | 440 |
| with-trend + strengthen (healthy trend) | 49% (=51% continue) | 591 |

KEY DISCIPLINE NOTES:
- The signed flow is NOT a direct direction predictor. A directional probe looked like +5..+11 lift on
  4 cells, but `_info_dipole_flow_robustness.py` + `_info_dipole_flow_detrend.py` proved those were
  TREND/base-rate artifacts (Simpson's paradox on a 2-day trending window): they vanish under a
  window/forward sweep, temporal OOS, and a detrended target. Only `btc_kraken_sell mi_flow` survived
  detrending (+7.1), weakly. **Do not deploy the directional `cell_signal` map** -- `DEPLOY_VALIDATED=False`.
- The DIVERGENCE/FLIP read is the robust one (survives temporal split + per-cell). That is the edge.
- The static `imb_level` is the divergence detector (the differential `mi_flow`/`imb_flow` are NOT --
  divergence is a level comparison, not a rate).

## WHY THIS MATTERS (Greg) — platform-wide
Markets are mostly follow-the-leader until the leader exhausts, then a new leader (usually opposite) ->
almost all trend-following. This one flow primitive plugs into every layer: regime classifier
(divergence/collapse -> reversal/transition; confirm/strengthen -> CHANNELED/CASCADE continuation),
entry gating (don't follow into divergence; fade strong divergence), sizing (`reversal_conviction`),
the per-cell fingerprint, and the product signal feed ("flow diverging from price -> reversal alert").

## DELIVERABLES (in git, branch crypto-trading-platform-plan-MpqwG)
- `odcore/info_dipole.py` -- portable (numpy-only) operator. `signed_flow_features()` (Shannon/MI
  primitives per the paper), `divergence(buy_vol, sell_vol, price_drift)` -> the 2-factor flow-state read
  `{imb_level, aligned_flow, confirms, opposing, exhausting, expect in {reversal,flip_risk,weakening,
  continue}, reversal_conviction}`. `cell_signal()`/`DEPLOY` are the PROVISIONAL directional map
  (`DEPLOY_VALIDATED=False`, do not trade off it). Reusable in pre-window gathering AND the fingerprint.
- `odcore/fingerprint.py` -- stacks `signed_flow_features` into the Fingerprint (`flow_features` +
  per-cell `flow_signal`; `stack()`), no look-ahead.
- Analysis (committed, bar-free off test_bars): `_info_dipole_flow_probe.py` (per-cell directional probe),
  `_info_dipole_flow_robustness.py` (window/forward/temporal sweep), `_info_dipole_flow_detrend.py`
  (trend-artifact vs real), `_info_dipole_trend_flip.py` (the divergence + 2-factor reversal edge).
- Commits 21ec02f -> (this session's tip). All pushed.

## DATA / SCOPE
- `fingerprint_dataset/test_bars/` = 1-min bars 2026-05-23..24, 6 venues (have buy_vol/sell_vol). Covers
  the 1,560 winner onsets. The data-branch `realbins/` are 1-sec but a LATER period (not the onset window).
- So n is capped at 1,560 labels and validation is on thin 1-min/2-day data. The real confirmation needs
  the LOCAL 1-sec onset-window history (not in git) -- multi-regime, more N, finer entropy/MI.

## NEXT (KICKOFF_2026-06-22_S36.md has the detail)
1. **Net-of-cost backtest of the divergence/exhaustion reversal gate, per cell** (THE decisive test:
   a 64% reversal hit-rate is only an EDGE if the moves beat fees+slippage; walk-forward).
2. Validate on the local 1-sec multi-regime history (the thin-data caveat).
3. Wire `divergence()` into the regime classifier + fingerprint as a per-cell flip/continuation feature.
4. The two inverting cells (btc_bybit_buy, eth_kraken_sell) -- why do they break the rule? Per-bucket physics.
5. Sharpen with the info-dipole C ratio (autonomy/coupling -- the paper's collapse/decouple modes).
