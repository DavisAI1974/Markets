┌─ DROP-IN — DavisAI Markets S64 ────────────────────────────────────────────────────┐
│ Branch: dev/push on the designated claude/* branch.                                 │
│   ⚠ Canonical = 5c5vg9. Reconcile FIRST (designated branch keeps getting cut from    │
│   the wrong parent — reset --hard if so). Sync 5c5vg9 after EVERY push. A PARALLEL   │
│   paper_trade cron pushes to canonical — rebase, don't clobber.                      │
│                                                                                      │
│ ⛔ BYBIT permanently banned; MEXC dead. FEE FRAME = KRAKEN kr_mk0 = 0bp maker         │
│   (Greg pivoted S63; Coinbase parked). Kraken tape re-pull = backfill_kraken_trades  │
│   (rate-limited ~1req/s); book = data/<coin>-kraken-book (gunzip to materialize).    │
│                                                                                      │
│ READ: SESSION_HANDOFF_2026-07-07_S63.md + S63_TREND_FLIP_FINDINGS.md (§1–20) +        │
│   KRAKEN_DEPLOY_MAP_S63.md.  All S63 tools = scripts/_s63_kraken_*.py (20).           │
│                                                                                      │
│ ⭐ STATE (S63) — the Kraken strategy is FULLY MAPPED:                                 │
│   • EDGE = ride the per-cell early-arm FLOW-LEAN ZIGZAG (odcore/flip_detector.py,     │
│     WFLIP=600 REV=0.1). ETH/BTC forward, SOL REVERSED. Passes the S54 gate on ETH     │
│     (z=4.0) + BTC (z=3.0). Early-arm (retime_flips) ~doubles it: ETH +9.50/BTC +8.64  │
│     $/hr @ $5k (paper, 0bp). The edge is MEAN-REVERSION.                              │
│   • LOSERS: deep bail (BTC −80 / ETH −100) = FREE tail-cap (at big depth WIN%~0, a    │
│     dead loss). NO flip/re-short (slide spent, confirmed-short wins only ~19%).       │
│     Shallow bail (−15) BLED.                                                          │
│   • WINNERS: already 68–83% of peak; NO take-profit trail helps; NOT exiting early    │
│     (price reverts after exit). Only booster = early-arm entry.                       │
│   • DIRECTION IS DEAD: unpredictable at entry AND mid-leg (t=0..600 all ~0.50; dipole │
│     agent ~chance). E300 depth predicts DEATH (magnitude) not DIRECTION. Closed 4     │
│     ways. Don't re-chase entry/direction signals.                                     │
│                                                                                      │
│ ⭐⭐ THE GATE = THE MAKER FILL (real Kraken L2 book): raw fill only ~40%, 55–67% forced │
│   to TAKER, win% 47→29, 64–77% of losses are forced-taker = the LEAK IS THE FILL.     │
│   SQUEEZES: cover_grace (rest cover past turn) → ETH fill-viable ~0.9/hr cost;        │
│   swing floor (coarser REV) → fill% 31→60% (fill-vs-edge knob). BTC/SOL fills lossy.  │
│                                                                                      │
│ ⚠ WHY THE NUMBERS LOOK MEDIOCRE: the ~1-day BOOK window is LOW-EDGE (ideal-fill net   │
│   already −2/−1), NOT the +8–9/hr tape regime → honest $/hr negative on it. CANNOT    │
│   grade viability on this window. On a normal-edge window ETH ≈ +8 − ~1 fill ≈ +7/hr. │
│   BLOCKER IS DATA (multi-day book on a normal-edge window), NOT method.               │
│                                                                                      │
│ JOBS (Greg, S64):                                                                    │
│  1. RE-GRADE the fill (cover_grace≈300 + swing floor REV≈0.2) on a NORMAL-EDGE        │
│     multi-day Kraken book — the decisive ETH viability test. Everything gated on this.│
│  2. EVALUATE the OPEN-SOURCE platform hftbacktest (Lean Lab README 2nd gate; +Tardis) │
│     — does its fill model IMPROVE ours or is it the BETTER option to build on? Drop   │
│     our ETH legs into hbt_lean_stub.py; report keep/adopt/hybrid.                     │
│  3. BENCHMARK our results vs other crypto MM/HFT platforms (Greg: "we aren't getting  │
│     great results for some reason") — is +8/hr@$5k good or bad? Diagnose why (fee tier/│
│     rebate? venue? edge genuinely thin? measurement?).                                │
└──────────────────────────────────────────────────────────────────────────────────────┘
