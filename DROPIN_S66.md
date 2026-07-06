┌─ DROP-IN — DavisAI Markets S66 ────────────────────────────────────────────────────┐
│ Branch: reconcile to canonical 5c5vg9 FIRST (reset --hard if cut from wrong parent). │
│ WE ARE ON KRAKEN (Greg). Coinbase = parked/legacy. Bybit banned, MEXC dead.          │
│                                                                                      │
│ ⭐ READ FIRST: STRATEGY_INVENTORY.md (§1 KRAKEN registry, §2.A per-coin config, the   │
│   S65 blocks, §8 PIECES) → SESSION_HANDOFF_2026-07-06_S65.md.                         │
│ RULES: SIM = LIVE CODE + NEW PIECES (never reimplement odcore/ in a script); MAKER    │
│   NUMBERS ARE FRONT-OF-LINE (fill_model="front"); NO aggregate-as-sum ($5k TOTAL);    │
│   per-coin $/hr is the EDGE (fixed) — aggregate gain = ALLOCATION; kraken in filenames;│
│   per-coin law; never tune off one window; update inventory AS YOU GO.               │
│                                                                                      │
│ STATE (S65 close) — Job 1 DONE: `scripts/basket_sim_kraken.py` decides through the    │
│   LIVE `platform.run_kraken_cell` (KRAKEN registry). All 5 cells POSITIVE front-of-   │
│   line: eth +6.77 / btc +6.66 / sol +6.01 / doge +6.59 / xrp +14.02 $/hr @ $5k;       │
│   corr ~0; portfolio Sharpe +0.810. ⚠ ONE 30h LOW-EDGE book window — provisional.     │
│  • FILL solved: front-of-line + ENTICING close (`swing_maker.close_improve_bps`, opt- │
│    in) = maker close not taker. Bleed WAS the back-of-line assumption; now forced-    │
│    taker→0. New bleed = SIGNAL-LOSS (wrong-dir swings, direction is DEAD).            │
│  • The 2.5× front-of-line legs are CHURN — money is only in the big swings (≥20bp).   │
│    REV=0.10 kept ALL coins (majors' fine churn is net-POSITIVE — "don't cut positive  │
│    churn", Greg). DOGE 0.30 / XRP 0.13 book-better but BIG change off 1 window → pend. │
│  • Direction RE-ADJUDICATED (exec agent): FWD wins all 5 on book (SOL/XRP/DOGE fwd) —  │
│    employed in KRAKEN registry FLAGGED provisional; 30d-TAPE deploy map stands live.   │
│  • XRP is a real positive cell "stand aside" missed (3 agents concur).                │
│                                                                                      │
│ JOBS (S66):                                                                          │
│  1. ⭐ CAPITAL STRATEGY: ONE $5k pool + ANTI-RESTING rotation across the 5 uncorrelated│
│     cells so it's NEVER idle (majors ~57% idle). Per-coin $/hr fixed — optimize the   │
│     ALLOCATION for the best $5k aggregate. Kill the $25k aggregate framing.           │
│  2. Confirm book-provisional bits on a 30d TAPE/Tardis: direction (SOL/XRP/DOGE fwd) + │
│     REV (DOGE 0.30, XRP 0.13). Tape NOT on-box → backfill_kraken_trades.py (~hrs).    │
│  3. Repoint the paper/live path from legacy Coinbase DEPLOYED → KRAKEN registry (needs │
│     a live Kraken book loader). Stop accruing the parked Coinbase ledger.             │
│  4. Agent-ranked probes: E300 on Kraken tape (XRP/DOGE); bigline on all 5; S42 book-  │
│     depth direction on Kraken. Small-cap eligible basket (−2bp) folds into #1.        │
└──────────────────────────────────────────────────────────────────────────────────────┘
