┌─ DROP-IN — DavisAI Markets S65 ────────────────────────────────────────────────────┐
│ Branch: dev/push on the designated claude/* branch.                                  │
│   ⚠ Canonical = 5c5vg9. Reconcile FIRST (designated branch keeps getting cut from     │
│   the wrong parent — reset --hard if so). Sync canonical after pushes; paper cron     │
│   pushes to canonical — rebase, don't clobber.                                        │
│                                                                                       │
│ ⭐ READ FIRST: STRATEGY_INVENTORY.md — the canonical list of ALL our live strategies/  │
│   tools/cells + the TRIED-&-DEAD ledger. THEN SESSION_HANDOFF_2026-07-05_S64.md.       │
│   ANTI-CIRCLING RULES (Greg, S64): update the inventory AS YOU GO (not at end);        │
│   venue (kraken) in filenames for deployables; PER-COIN LAW (ditch per coin, keep      │
│   where it works — never global-kill).                                                │
│                                                                                       │
│ ⛔ BYBIT banned (US-ineligible); MEXC dead. Fee frame = KRAKEN kr_mk0 (0bp maker,      │
│   = the $10M/30d tier; aggregate across ALL pairs so majors count toward it).          │
│   Rebate −2bp = LOW-LIQ alts ONLY (majors excluded); US-legal rebate = Kraken only.    │
│                                                                                       │
│ ⭐ STATE (S64 close):                                                                  │
│  • Edge is real but bare lean is marginal-by-construction (0.5-1bp gross < ~0.8bp      │
│    adverse-sel fill cost). The lever = maker REBATES (Kraken alts) + DIVERSIFICATION.  │
│  • Majors DEPLOYED STACK = lean + early-arm(the lift) + deep-bail + cover-grace.       │
│    Under honest fills majors sit ~57% IDLE → fill it with a maker BASKET (edges        │
│    ~0-correlated → √N Sharpe), NOT taker-entry (dead: fee > captured edge).            │
│  • E300 death-selector = family B; PER-COIN on the lean ride (KEEP BTC +0.20, DROP     │
│    ETH); also runs as its own uncorrelated sleeve.                                     │
│  • ELIGIBLE SWEEP: 720 eligible → per-coin TUNED gate (window is the lever) → ~6       │
│    confirmed per-week-stable: APE/RE (fwd), XDC/SHX/AIOZ/ARPA (rev). SHX/AIOZ need      │
│    W2400. HYPE ($9.3M, most liquid)=null (efficiency gradient: liquid=weak,thin=strong)│
│                                                                                       │
│ JOBS (S65):                                                                            │
│  1. ⭐ BUILD the multi-sleeve BASKET SIMULATOR (name it *_kraken_*) through the REAL    │
│     executor (early-arm+deep-bail+cover-grace, tier/rebate/honest-fill wired): put an  │
│     honest $/hr + Sharpe on majors-sleeve + eligible-basket + E300-sleeve (~0-corr).   │
│  2. Longer pulls on SYN/GWEI/NIGHT/HYPE (7-day → per-week); finish SOL/XRP/DOGE tape;   │
│     formal per-week+reversed re-gate on the shortlist.                                 │
│  3. E300 as its own sleeve — measure its correlation vs the lean sleeve.               │
│  4. (Greg) Tardis paid month → normal-edge multi-day Kraken book → grade Job-1 fill.   │
│  5. When basket edge proven → Kraken live adapter (WS v2 add/amend/cancel post_only;    │
│     no spot testnet → tiny real size first).                                           │
└───────────────────────────────────────────────────────────────────────────────────────┘
