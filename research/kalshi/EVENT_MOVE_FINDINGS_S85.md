# EVENT-MOVE BASELINE — first real result on the true-tick NYMEX tape (S85)

`event_move_baseline.py` on Databento `GLBX.MDP3` trades (every print, nanosecond), continuous VOLUME
front-month (`NG.v.0`/`CL.v.0`). 12 NG (Thu) + 12 CL (Wed) EIA-release windows, Apr-Jul 2026, +/-40min
around 14:30 UTC. Leakage gate PASS (pre-release anchor invariant to post-release ticks). Tick size/value
POINT-IN-TIME from the `definition` schema (all 12/12 events on `definition`, not reference): NG
$0.001x10000 = $10/tick, CL $0.01x1000 = $10/tick (both confirmed vs reference). Provisional-until-live;
these are FUTURES (canary) moves = the CEILING the Kalshi echo chases, NOT realized P&L.

## The headline: it's a HOLD-TIME map, per contract (distributions, not means)

The load-bearing cut is the **fast (sub-minute) window** — the lag-scalp opportunity (Greg, S85). The
pooled median time-to-peak (NG ~12min, CL ~22min) HIDES it; the per-event fast window exposes it.

| contract | 60s move (bps) p50 / p90 / max | 60s $ p50 / p90 / max | 60s captures of full peak (p50) | peaked <=60s | full peak (bps) p50 |
|----------|-------------------------------|----------------------|-------------------------------|-------------|--------------------|
| **NG** (KXNATGASD) | 106 / 174 / 181 | $310 / $490 / $550 | **0.66** | 2/12 | 169 |
| **CL** (KXWTI)     | 23 / 50 / 73    | $190 / $509 / $700 | 0.27 | 0/12 | 88 |

## Read (per-cell, both KEPT — "works on both, different hold windows")

- **NG is front-loaded → a ~60-SECOND hold captures ~2/3 of the whole move.** The release hits and it
  goes fast: 06-11 peaked in **1 second** (177 bps / $550), 07-02 in 9s; 5/12 peaked within 2 minutes.
  NG is the fast lag-scalp underlying. ~$310 median / up to $550 per NYMEX contract gross in the first 60s.
- **CL is slower and less front-loaded → 60s catches a real ~27%, a LONGER hold catches the rest.** This
  is NOT "CL fails" (the S85 correction — never lead with the deflationary median). CL moves are real and
  sometimes large; they just DEVELOP over ~20 min. The tell: 06-17 CL caught $290 in 60s but the full move
  was **$2,640 (341 bps)** built over 17 minutes. So CL's lag-scalp is a LONGER scalp, and its 60s window
  still throws p90 $509 / max $700 on the bigger days. Kept, on a longer hold.
- **Frequency is not the gate; EV-net-of-fee is.** A smaller/less-frequent capture is still harvested if
  it clears the Kalshi toll (0.07*C*P*(1-P) per taker leg). "I'll take 27% any day" = positive-EV is the
  filter, not how often it fires. Same size-vs-fee finding as S81/S82, now on the canary tape.
- Matches the S79 EVENT_WEIGHT_STUDY: NG=F is the heaviest, fastest energy reactor (z=5.2); crude is
  diffuse/pre-empted by the Tuesday API report -> slower intraday development. Independent confirmation.

## Honest caveats (provisional)

1. **Futures move != Kalshi P&L.** These $ are per-NYMEX-contract, the CEILING. The realized capture is
   the KALSHI echo of this move, net of fee, and only the fraction Kalshi reprices in our hold -> the
   **lag join** (next step) measures it. Futures $ != Kalshi $ (binary moves in probability space; the
   conversion depends on strike moneyness + time-to-settle; the SIZE in bps is what carries over).
2. **surprise=unknown for all events** — the historical consensus/actual join isn't wired (consensus.jsonl
   is forward-only). So this is the UNCONDITIONAL per-series move. The surprise-cell split (beat/miss x
   big/small) is where CL's "when does it fire big" almost certainly lives (the $2,640 day was surely a
   big surprise) — needs historical EIA actuals + street consensus. Next build.
3. n=12 per contract, release windows only. A first read, never sized off one window.

## Data

- Tape: `data/pyth_ticks/{NG,CL}_2026MMDD.jsonl` (src=databento_trades), defs
  `data/pyth_ticks/{NG,CL}_definitions.jsonl`, baselines `data/event_move_{NG,CL}.json`. Persisted gzipped
  on the **`data/nymex-ticks`** branch (restored by `kalshi-session-start`).
- Cost so far: ~$0.50 of the $125 credit (24 release windows + defs). Full-year plan below.

## Next (the S85 -> S86 thread)

1. **Upgrade the schema to MBP-10** (Greg's call, ~$5 over the credit for a full year of both): trades +
   top-of-book bid/offer size + 10-level resting DEPTH, ns-stamped. The depth is the run-length/exhaustion
   read (does a thinning book predict a longer run?). Needs the writer + baseline extended to consume depth.
2. **Full-year batch pull** (NG+CL MBP-10, ~$130) -> the daily tape (KXNATGASD settles on the 5PM close
   EVERY day, not just Thu) + all ~52 releases/yr per contract for real per-cell N.
3. **Historical surprise join** (EIA actuals + consensus) -> the surprise-cell split (this is where CL's
   big-day fires show up).
4. **The lag join** -> Kalshi echo net-of-fee vs the futures move: the actual capture, per hold-time, per
   contract. Turns this ceiling into realized-EV.
