# FEED M DELIVERABLE - THE LAG EXECUTION MAP + FILL/FEE ECONOMICS (S100, 2026-07-20)

Successor to the gate's `KALSHI_ECHO_REPLAY_S98.md` deliverable on the RESCOPED substrate (feed L
proved the walked-winter echo replay structurally impossible - no market existed; the walk-call
echo replay itself happens chronologically at G14+). This is the execution-economics half feed M
owed: the lag's NG-specific execution shape on the KXNATGASD life + the fill/fee model.
Modules: `lag_execution_map.py`, `kalshi_fill_model.py`. Store: S3 `kalshi_echo/lag_map.jsonl`
(76,594 event x bracket rows, 61 event-days, Mar 30 - Jul 17 2026).

## SCOPE GUARD (unchanged)

The lag's EXISTENCE is established (gate 0c) and is not retested here. Everything below is
execution economics on THIS product in THIS regime. Delay-to-first-trade is a LIQUIDITY-DEPENDENT
proxy: on a thin bracket it measures "when did anyone trade" as much as "when did price update";
candle-mid pass-through partially covers quote repricing. 1-sec-or-finer NYMEX readouts remain
lower bounds.

## THE REGIME (load-bearing context for every number)

The life is the SPRING LOW-VOL regime: the most active day shows max 60s travel 1.8c / max 300s
travel 3.0c (the winter-scale 2c/60s event definition fires ZERO events across the whole life).
Event definition used: >=1.5c within 300s, classes 1.5-2.5c / 2.5-4c / >=4c, non-overlapping,
NYMEX settle window excluded, bracket-settle-adjacent (>=16:30 ET) flagged out of the summaries.
Winter execution numbers will differ; the map must be RE-MEASURED when vol returns (the live
collector makes this continuous at go-live).

## THE MAP (per-cell descriptors; per-event rows are the store)

Response = first trade in the bracket within 10 min of the event.

- RESPONSE RATES: ATM 4,856/11,610 (~42%) | NEAR 5,137/17,129 (~30%) | FAR 3,596/47,855 (~7.5%).
  MOST BRACKET-EVENTS SEE NO TRADE AT ALL - fill reality is the binding constraint, exactly as
  S81/S82 found at size.
- DELAYS (responded cells): medians run ~110-215 SECONDS; larger moves respond faster
  (ATM >=4c med ~105-115s vs 1.5-2.5c ~180s am); pm faster than am at ATM (112s vs 179s);
  min delays of 0.0s exist (trades landing inside the move - the fast tail is real and reaches
  the established seconds-scale at the liquid margin).
- PASS-THROUGH: dmid_1m/dmid_5m signed by NYMEX direction ride per-row in the store; on the
  liquid ATM band a mid response of ~3.5-5c per 1.5-2.5c NYMEX move is typical where two-sided
  quotes exist (per-event, from the canary day's joined rows; the store carries every instance).

## THE FILL/FEE WALL (kalshi_fill_model.py, verified 0.07*P*(1-P))

- Taker fee ~1.75c/contract at midprob, BOTH sides => ~3.4c fees round trip.
- MEASURED ATM SPREADS (1m two-sided closes): Apr 22 med 15c (p90 38c); Jun 4 med 11c (p90 30c);
  Jul 7 med 4c (p90 4c). The book TIGHTENED over the life but April-June spreads DWARF the fee.
- CONSERVATIVE TAKER ROUND TRIP (cross both ways): fees + full spread = ~7.4c (July-era 4c
  spread) to ~18c (April-era 15c spread) per contract.
- VERDICT (this regime, taker): the median echo event (1.5-2.5c NYMEX move, ~3.5-5c bracket
  pass-through) DOES NOT CLEAR the taker wall on most of the life; the >=4c class on July-era
  spreads is the first cell where taker economics approach viability. THE SAME SIZE-VS-FEE
  CONCLUSION AS S81/S82, now measured on the actual product.
- MAKER: fee 0, spread EARNED not paid - the real angle given minutes of runway (median delays
  100-200s = enormous time to rest orders at the lag). BOUND ONLY: resting-fill probability is
  unclaimable from candles (no historical book depth exists); the live collector's books
  (2026-07-12+) are the evidence source. This is the Kalshi coach's live paper-trade question,
  not a historical claim.

## CONSEQUENCES CARRIED FORWARD

1. TWO_COACH_SPEC: the Kalshi coach's entry design must be maker-first (rest at the lag, let the
   echo come to us) with taker reserved for the >=4c fast tail; per-cell expected-window numbers
   come from THIS map, not from the winter 7-20s constant.
2. The seconds-scale lag lives at the liquid margin (min delays ~0s); the minutes-scale medians
   are THIN-BRACKET fill reality. Both true; never conflate.
3. Named gaps: 2026-06-30/07-05/07-12 partial-session days not in the map (store convention);
   winter-regime map = re-measure at first cold (live).
4. July 3 half-day tape vs flow_calendar full-holiday flag - discrepancy queued for verify
   before feed M's calendar is trusted on holidays.
