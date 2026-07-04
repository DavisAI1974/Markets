┌─ DROP-IN — DavisAI Markets S61 ────────────────────────────────────────────────────┐
│ Branch: dev/push on the designated claude/* branch.                                │
│   ⚠ Canonical = 5c5vg9. Fetch + --ff-only else reset --hard (S58/S59/S60 were ALL  │
│   cut from the wrong default/crons parent — reconcile FIRST). Sync 5c5vg9 after    │
│   EVERY push. A PARALLEL session may push to canonical — rebase, don't clobber.    │
│   Default = crons (Kraken + Coinbase book collectors + paper cron, all 6h).        │
│                                                                                     │
│ ⛔ BYBIT permanently banned; MEXC dead; ELIGIBILITY BEFORE ANY VENUE WORK.          │
│                                                                                     │
│ READ: S60_EXIT_NOTES.md (R1a-R7 round-by-round) → SESSION_HANDOFF_2026-07-04_S60   │
│   → KICKOFF_2026-07-05_S61 → S58_ENTRY_NOTES.md for the entry record.              │
│                                                                                     │
│ ⭐ STATE: ENTRY done. KRAKEN TAPE VERDICT = the gross EXISTS on Kraken's own prices │
│   (all cells kr_mk0+, sol +$3.14/hr 5/5wk, eth alive on Kraken; fills = the open   │
│   unknown, books accruing). PIECE 2 EXIT worked to per-cell verdicts: ZIGZAG HOLDS;│
│   only edge = the WRONG-SIDE CORRECTOR, DIAGONAL per cell (sol none / btc plain-   │
│   stop rider / doge cascade-flip / xrp none). Toll law 4/4 both venues; NO peak    │
│   harvester (S35 fingerprint-tier). COINBASE EXIT FIX reframed FILL/FEE-not-timing:│
│   the sandbox ledger can't see the real fill cost (128/128 closes booked maker by  │
│   construction); honest fill machinery exists UNWIRED; grace=0 at mid-band; FEE    │
│   TIER > the whole exit prize. DIPOLE PROGRAM: paper PRINTED (docs/DIPOLE_PAPER_    │
│   S60.* + dive chapter + crypto-uses notes); absorption candidate RESOLVED against │
│   (real SOL signal = maker-quoting price-discovery lead, filed to fill fingerprint).│
│                                                                                     │
│ ⭐ DO THESE TWO FIRST (Greg, explicit):                                             │
│  A. SPIN UP THE 2 AGENTS THAT DIDN'T FINISH (S60 interrupt casualties): the SOL    │
│     Coinbase-exit-fix agent + the BTC armed-before recheck. Charters are in the    │
│     S60 record; conclusion is expected (SOL protect / BTC rider) but the explicit  │
│     numbers were never delivered — GET THEM.                                        │
│  B. EXPECT REAL CODING THIS SESSION: the S60 proposals (honest fill model, cover-  │
│     grace at mid-band, fee-aware unload, doge _cascflip variant) + whatever the 2  │
│     agents propose = code to WRITE and wire (sandbox-first, canary bit-identical). │
│     This is a build session, not just analysis.                                    │
│                                                                                     │
│ JOBS — ONE ROUND = ONE DEFINED TEST (update S60_EXIT_NOTES or a S61 successor):    │
│ 1 COINBASE EXIT FIX build order (Greg sign-off): (a) HONEST FILL MODEL FIRST (port │
│   maker_book._first_fill_index into the mid-band close; measure real maker_close%  │
│   on books — makes the fill cost visible) → (b) cover-grace arm (wall-clock) → (c) │
│   swing_accum fee-aware unload → (d) doge _cascflip sandbox variant. Sandbox-first,│
│   baseline canary bit-identical every wire.                                        │
│ 2 FEE-TIER VERIFICATION (2 Greg clicks, biggest lever): Coinbase fee-upgrade prog  │
│   + CFM tier tab (12-16bp RT vs +3-5 best exit read).                              │
│ 3 UN-PARK KRAKEN EXITS once Coinbase exit lands (doge-flip shuffle-floor, btc      │
│   plain40 Kraken premium, eth_kraken).                                             │
│ 4 KRAKEN BOOKS accrual → the fill unknown (taker-share + fill-depth at kr_mk0).    │
│ 5 RESEARCH MENU (Greg's fascination, background): paper's 29 candidate uses + dive │
│   cross-domain map (seizure-onset flow collapse = novel standout); each pre-specced.│
│ DATA (/tmp dies): Coinbase books x5 from data/<coin>-book (~2min); Binance 30d via │
│   backfill_binance_spot.py x5 (~40min); Kraken 30d via backfill_kraken_trades.py   │
│   x5 SEQUENTIAL (hours, START FIRST if needed); Kraken books from data/<coin>-      │
│   kraken-book (once cron/click fires — CHECK Actions, still 0 runs at S60 close).  │
│                                                                                     │
│ ENV: crypto only; zero synthetic (tool-validation anchors OK); per-cell deploy;    │
│   never tune off one window; graded beats gated; scale-locality; venue law (no     │
│   flow read ports w/o per-venue pass); office discipline (dipole value = operator  │
│   × what it's conditioned against); sandbox-first + baseline canary bit-identical;  │
│   git = source of truth; falsification-first; MPLBACKEND=Agg; token 403 on GHA     │
│   dispatch (Greg clicks Run workflow).                                             │
└─────────────────────────────────────────────────────────────────────────────────────┘
