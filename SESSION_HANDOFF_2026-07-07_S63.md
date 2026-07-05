# SESSION HANDOFF — S63 (2026-07-07) — the KRAKEN pivot, fully mapped: direction is dead, the edge is the mean-reversion RIDE, the gate is the maker FILL

Branch reconciled to canonical `5c5vg9` at open (designated branch was cut from an S37-era parent AGAIN
— reset --hard; sync canonical after every push). Full detail: **`S63_TREND_FLIP_FINDINGS.md`** (§1–20)
+ **`KRAKEN_DEPLOY_MAP_S63.md`**. Fee frame = Coinbase→**KRAKEN this session** (Greg pivot): kr_mk0 =
0bp maker. Rules held: crypto only; per-cell deploy; never tune off one window; git = source of truth.

## THE ARC (what we learned, in order)
1. **Direction reframe (Binance-spot research):** the machine's losers are a DIRECTION mistake (shorts
   into 1h uptrends). The buy/sell answer = FADE the multi-hour trend (+sign momentum is backwards).
   Fade beats the machine's dir-acc by +3–5pts, clears on DOGE-8h / SOL-4h; XRP/ETH fragile. `_s63_
   trend_flip/_diag/_direction/_fade/_e300_trend.py`.
2. **KRAKEN PIVOT (Greg):** park Coinbase, go to kr_mk0 (0bp maker) where the machine's gross IS its net.
   Re-pulled the 30d Kraken tape (`backfill_kraken_trades.py`) + materialized the L2 book branches.
3. **The REAL bybit model = the flow-lean flip detector** (`odcore/flip_detector.py`, WFLIP=600/REV=0.1,
   ARM0), NOT a price zigzag — it zigzags on the taker-flow LEAN (price at a turn is ~99.6% symmetric).
   On the Kraken tape it PASSES the S54 gate on **ETH (z=4.0) + BTC (z=3.0)**, SOL anti-predictive→REVERSED,
   XRP/DOGE not sig. Early-arm entry (retime_flips) ~doubles it: **ETH +9.50, BTC +8.64 $/hr @ $5k**.
4. **Losers:** win/loss shows we're NOT hemorrhaging on loss size (avg win > avg loss). At BIG depth a
   trade is a DEAD loss (recover-to-profit ~0% by −80) → a **deep bail (BTC −80 / ETH −100)** caps the
   −150/−200 tail for FREE (WIN%~0, clips no winners). Flip/re-short at depth FAILS (slide is spent —
   even a flow-confirmed short at −80 wins only ~19%). Shallow bail (−15) BLED. `_s63_kraken_deepstop/
   bailshort/widebail/flipbail.py`.
5. **DIRECTION is unpredictable at entry AND mid-leg** (t=0/60/120/300/600 all ~0.50; the dipole/trend
   agent = ~chance, big-loser flip 41–53%). E300 depth predicts DEATH (magnitude) but NOT direction.
   Closed 4 ways (coeff/momentum/fade/dipole-agent). `_s63_kraken_dipole_agent/direction_timing.py`.
6. **Winners:** already capture 68–83% of peak; no take-profit trail helps (exits early + taker). NOT
   exiting too early — price REVERTS after the flow-turn exit (post-exit 120s favorable −0.6bp, 46% keep
   going). `_s63_kraken_winners.py`.
7. **THE MAKER-FILL GATE (the decisive one), real Kraken L2 book:** raw maker fill is only ~40%; 55–67%
   of exits forced to TAKER; win% collapses 47%→29%; 64–77% of losses are forced-taker closes → **the
   leak is the FILL, not the signal.** `_s63_kraken_makerfill/_losers.py`.
8. **The squeezes (both help the fill leak):**
   - **cover_grace** (rest the cover past the turn): ETH taker 55%→12%, fill cost only ~0.9/hr vs ideal →
     ETH fill VIABLE; BTC ~6/hr, SOL ~12/hr (still lossy). `_s63_kraken_covergrace.py`.
   - **swing floor** (coarser REV, from the small-winner churn tail — ~45% of winners are <5bp / ~10% of $
     and flip to losers under taker): raises fill% 31%→60%, lifts honest net. A **fill-vs-edge knob**.
     `_s63_kraken_smallwinners/swingfloor.py`.

## THE VERDICT (per-cell deploy map — `KRAKEN_DEPLOY_MAP_S63.md`)
- **ETH:** forward flow-lean zigzag, early-arm eps10, ride to turn, deep bail −100; fill VIABLE (~1/hr).
- **BTC:** forward, early-arm eps5, deep bail −80; fill lossy (~6/hr) — needs the swing floor + cover_grace.
- **SOL:** REVERSED, ride, no early-arm (fragile); fill worst.
- **DOGE:** fade-8h (different tool); **XRP:** stand aside.
- Levers that WORK: early-arm entry, deep bail (tail-cap), cover_grace + swing floor (fills).
- Levers that DON'T: any direction/entry signal, flip/re-short, stop-loss (shallow), take-profit trail.

## ⚠ THE HONEST BLOCKER (why the numbers look mediocre)
Every honest-fill $/hr this session is NEGATIVE — but the ~1-day BOOK window is **LOW-EDGE** (the
perfect-fill IDEAL was already −2/−1 on ETH/BTC). This is NOT the +8–9/hr regime the 30d TAPE had. So
we **cannot grade viability on this window.** On a normal-edge window, ETH honest ≈ tape-edge(+8) −
fill(~1) ≈ +7/hr. **We need multi-day Kraken book on a normal-edge window** (collectors running) to
grade for real. This is DATA-gated, not method-gated.

## FOR S64 (see `KICKOFF_2026-07-08_S64.md`)
1. Re-grade the maker-fill (cover_grace + swing floor) once multi-day Kraken book accrues on a normal-edge
   window — the decisive test for ETH.
2. **Evaluate the OPEN-SOURCE platform `hftbacktest`** (the Lean Lab README's fill-level 2nd gate; py-v2.4.x)
   — does its queue/latency/fill model improve our fill validation, or is it just the better platform to
   build on? Also Tardis.dev for deeper history.
3. **BENCHMARK our results vs other platforms/strategies** — Greg's gut: we're not getting great results.
   Are ~+8/hr@$5k (paper) / marginal-net (fill) numbers good or bad vs published crypto MM/HFT? Find out
   WHY (fee tier? venue? the mean-reversion edge is just thin? are we measuring right?).
