┌─ DROP-IN — DavisAI Markets S62 ────────────────────────────────────────────────────┐
│ Branch: dev/push on the designated claude/* branch.                                │
│   ⚠ Canonical = 5c5vg9. Fetch + --ff-only else reset --hard (S58–S61 were ALL cut  │
│   from the wrong default/crons parent — reconcile FIRST). Sync 5c5vg9 after EVERY   │
│   push. A PARALLEL session may push to canonical — rebase, don't clobber.           │
│                                                                                     │
│ ⛔ BYBIT permanently banned; MEXC dead. KRAKEN PARKED until Coinbase exit deploys.  │
│   FEE FRAME = COINBASE (Greg handles the fee tier; never label analysis "kr_mk0").  │
│                                                                                     │
│ READ: S61_BUILD_NOTES.md (R1–R13f round-by-round) → SESSION_HANDOFF_2026-07-05_S61  │
│   → KICKOFF_2026-07-06_S62. (S58_ENTRY_NOTES + S60_EXIT_NOTES = prior-piece record.)│
│                                                                                     │
│ ⭐ STATE (S61 close): COINBASE EXIT BUILT (canary-clean) — honest fill model wired   │
│   (fill_model="queue"; binding constraint = PRICE ELIGIBILITY not queue depth); 2   │
│   exit variants coded + accruing SANDBOX (doge_cascflip, btc_plainstop X=40) via    │
│   the new exit_spec socket. SOL=PROTECT (power bar); BTC rider ops-bar-BLOCKED.      │
│   PROFIT-PER-HOUR is the scoreboard (Greg standing rule; per-leg = diagnostics).     │
│                                                                                     │
│ ⭐ THE BIG-LOSER FLIP ARC (Greg-driven; the session's meat): the prize is REAL —     │
│   flip big losers = +6.79/hr (~$21/hr swing); 3-part oracle = +26/hr (15x), 508/508 │
│   winners kept. NO mid-leg causal signal reaches it (big-loser-start vs winner-dip = │
│   TWINS at the decision moment in price/flow/efficiency; winners-invisible). Greg's  │
│   FLIP thesis = the best single-feature lever: flip the deep-fade zone (pre600<-80)  │
│   = +2.38/hr (+0.61 over baseline), pre-number-only — WEEK-FRAGILE (wk4 -1.66).      │
│                                                                                     │
│ ⭐ DO THIS FIRST (Greg, explicit): FLIP-THEN-MANAGE (R13f — the wk4 mitigation).     │
│   Flip pre600<-80, THEN manage the reversed leg: adverse → FLATTEN small; favorable  │
│   → RIDE. Caps the mis-flip downside (the +291bp deep-fade winners we wrongly flip). │
│   GRADE: per-week (rescue wk4?), shuffle floor, $/hr, FEE-ACCOUNTED (flip = taker).  │
│   Sandbox-first + baseline canary bit-identical if it clears. Testable WITHOUT the   │
│   coeff tier. Alternative robustifier: REGIME GATE the flip (stand aside in the wk4  │
│   regime) via the S61 dipole regime descriptor (rolling cross-coin corr vs BTC).     │
│                                                                                     │
│ ⭐⭐ CARRY-FORWARD (Greg brings from E: drive): the 128-dim OD COEFFICIENT signatures │
│   (markets_<cell>_win_cand_sp) + centroid dual-print + onset re-anchor (_win_onset/) │
│   — LOCAL on E:, NOT in-container. They are the MULTIVARIATE tier (hist AUC 0.72–    │
│   0.84 vs the 0.606 cheap-feature floor) that robustly separates big-loser-from-     │
│   winner AT ENTRY = the real path to the +6.79/+26 prize. Get them → build the heavy │
│   entry fingerprint (onset-canary + per-mid-band revalidation + leakage gate first). │
│                                                                                     │
│ JOBS — ONE ROUND = ONE DEFINED TEST (update an S61_BUILD_NOTES successor each round):│
│ 1 FLIP-THEN-MANAGE build + grade (the live lead).                                   │
│ 2 REGIME GATE alternative (dipole cross-coin-corr descriptor).                      │
│ 3 GET E: COEFFICIENTS → heavy entry fingerprint (the prize path).                   │
│ 4 COINBASE EXIT finish: 2 fee-tier clicks (biggest lever); BTC ops-bar (exchange-   │
│   side stop + staleness kill-switch) before the rider touches capital.              │
│ 5 UN-PARK KRAKEN exits + books once Coinbase deploys.                               │
│                                                                                     │
│ STANDING OWED: push clear + 2 fee-tier clicks + Kraken Run-workflow click (books 0).│
│ Record change owed: demote BTC armed-before robustness entry to SOL-only.           │
│ DATA (/tmp dies): Coinbase books x5 from data/<coin>-book; Binance 30d bins via     │
│   backfill_binance_spot.py x5 (~40min); agent aligned arrays cached in scratchpad.  │
│                                                                                     │
│ ENV: crypto only; zero synthetic; per-cell deploy; never tune off one window;       │
│   graded beats gated; scale-locality; venue law; PROFIT-PER-HOUR scoreboard;        │
│   sandbox-first + baseline canary bit-identical; git = source of truth;             │
│   falsification-first; MPLBACKEND=Agg; token 403 on GHA dispatch (Greg clicks Run).  │
└─────────────────────────────────────────────────────────────────────────────────────┘
