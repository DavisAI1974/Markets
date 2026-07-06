┌─ DROP-IN — DavisAI Markets S67 ─────────────────────────────────────────────────────┐
│ Branch: reconcile to canonical FIRST (designated branch keeps getting cut from the    │
│   wrong parent — `git reset --hard` if so). Canonical S66 tip = 86b0ea1 on            │
│   claude/davisai-s66-kickoff-4kjp87. "5c5vg9" was a session LABEL, not a git SHA.      │
│ WE ARE ON KRAKEN (Greg). Coinbase parked. Bybit banned, MEXC dead. Fee = kr_mk0 (0bp).│
│                                                                                       │
│ ⭐ READ FIRST: STRATEGY_INVENTORY.md (S66 block) → SESSION_HANDOFF_2026-07-06_S66.md   │
│   → S66_CAPACITY_FINDINGS.md. Agent reads: ARCHITECT_READ_S66.md + DIPOLE_EXPERT_READ. │
│ RULES: SIM = LIVE CODE (never reimplement odcore/ in a script — run through            │
│   run_kraken_cell/run_stream); NO aggregate-as-sum ($5k = ONE shared POOL); per-coin   │
│   law; kraken in filenames; update inventory AS YOU GO. Don't re-chase the fill-quality│
│   rabbit hole (see the saga in the handoff — static cap too pessimistic, pivot patch   │
│   was LEAKAGE, dynamic-follow is the honest middle). Capacity = a VARIABLE SIZE cap.    │
│                                                                                       │
│ ⭐ THE LANDING (Greg, S66): keep last-night's per-coin EDGE; make capacity a VARIABLE   │
│   size cap (not $5k every trade); PIVOT to the CAPITAL MODEL (now the priority).        │
│  • Rank coins by RETURN-ON-CAPACITY (edge per $), NOT raw $/hr@$5k. XRP earns most per  │
│    $ but thin book (~$2.3k cap); BTC lower per-$ but deepest book (~$3.9k). Fill best   │
│    edge-per-$ to ITS capacity, then next, spread for Sharpe → your "$2k/$2k/$1k".       │
│  • Per-LEG: can't size by WHICH-WINS (direction dead, winners invisible). CAN size by   │
│    MOVE-MAGNITUDE — conviction sizing (S47 size_legs, dive_depth/climax) is already in. │
│  • Variable capacity REORDERS last night (conservative tape read; pin on book):        │
│    BTC ~+5.2 · XRP ~+7.4 · SOL ~+2.8 · ETH ~+1.8 · DOGE ~+0.4 $/hr.                    │
│  • odcore/capacity.py BUILT (canary PASS); dynamic follow-maker fills 100% (ETH +0.45/  │
│    BTC +1.35, honest). E300 on Kraken AUC 0.64–0.72 all 5 (but on the DEAD 3-piece).    │
│                                                                                       │
│ JOBS (S67):                                                                           │
│  1. Restart eligible-alt collection: `bash scripts/_s66_overnight_collect.sh &`        │
│     (resumes from 42 committed on data/kraken-smallcap-tape; ⚠ in-container bg dies on  │
│     session idle — only advances while active). 352 eligible, fat-first, 120d.          │
│  2. ⭐ BUILD THE CAPITAL MODEL — variable per-coin capacity + shared-POOL allocator on   │
│     the LIVE path. Architect spec: odcore/allocator.py + platform.run_portfolio +       │
│     capacity caps + cluster/correlation caps + pool cap; anti-resting. SETTLE FIRST     │
│     (Greg): capacity granularity (per-LEG vs per-COIN position) + total POOL size.      │
│  3. Kraken agent for OVERLOOKED MAJORS (Greg): LINK/ADA/AVAX/LTC etc. — liquid majors   │
│     beyond our 5 that deserve a cell. (S66's agent did thin eligibles, NOT majors.)     │
│  4. Re-grade eligibles + BTC/ETH with the DYNAMIC fill (static-model kill superseded);  │
│     pin capacity on the ~30h Kraken BOOK.                                               │
└───────────────────────────────────────────────────────────────────────────────────────┘
