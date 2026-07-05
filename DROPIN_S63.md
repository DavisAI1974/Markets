┌─ DROP-IN — DavisAI Markets S63 ────────────────────────────────────────────────────┐
│ Branch: dev/push on the designated claude/* branch.                                │
│   ⚠ Canonical = 5c5vg9. Reconcile FIRST (designated branch keeps getting cut from  │
│   the wrong parent — reset --hard if so). Sync 5c5vg9 after EVERY push. A PARALLEL  │
│   paper_trade cron pushes to canonical — rebase, don't clobber.                     │
│                                                                                     │
│ ⛔ BYBIT permanently banned; MEXC dead. KRAKEN PARKED. FEE FRAME = COINBASE (Greg   │
│   handles the fee tier; all tests fee=0, FLIP = 22bp taker cross — locked S62).     │
│                                                                                     │
│ READ: SESSION_HANDOFF_2026-07-06_S62.md + S62_RESUME.md + KICKOFF_2026-07-07_S63.md.│
│                                                                                     │
│ ⭐ STATE (S62): the 3-PIECE REBUILT (reproduces R11 exactly — SOL base +1.77, oracle │
│   +26.02, 508/508 winners kept). Entry-flip ORACLE per coin (the prize, winner-     │
│   preserving): SOL +30 / ETH +23 / DOGE +22 / XRP +22 / BTC +14 $/hr @ $5k.         │
│   Scripts: scripts/_s62_*.py. PROFIT-PER-HOUR is the scoreboard (per-leg=diagnostic).│
│                                                                                     │
│ ⭐ BREAKTHROUGH — the 3-PIECE at E300 (_s62_e300_3piece.py): decide MID-LEG, not at  │
│   entry (winners-invisible at entry). The realized DEPTH at E300 predicts DEATH at  │
│   AUC 0.69–0.77 on ALL 5 coins — first strong cross-coin classifier. BTC +1.29/hr   │
│   (crosses zero, 4/5wk), XRP +0.81. Earns via death-vs-WINNER (depth) + FLATTEN, NOT │
│   by predicting recovery. Deep-arm variant = ETH/BTC/DOGE +1.1..1.6 at arm -20/-30. │
│                                                                                     │
│ ⭐ THE REFRAME (Greg, load-bearing): the big losers are a DIRECTION problem, not     │
│   win/lose — SHORTS into clean UPTRENDS (traded the wrong side). Win-long/win-short  │
│   coeffs = PERFECT MIRROR (-1.0). But direction is ~chance at entry (coeff/momentum/ │
│   dipole) at the 600s scale — the market MEAN-REVERTS there (the machine's own edge).│
│   Death-vs-RECOVERY (which underwater leg bounces) = ~chance from EVERY signal at    │
│   every depth = the true wall. Coeff tier + 3 dipole flow agents mapped, all ~chance │
│   in-container (data_s62/). Don't re-chase those in-container.                       │
│                                                                                     │
│ ⭐⭐ DO THIS FIRST (Greg, S62 close): the 1-HOUR TREND flip. The big losers FADE a    │
│   strong 1-HOUR trend. Among big losers the 1h trend (mom 3600s) predicts the        │
│   forward direction at 0.58–0.67 (btc 0.672 / eth 0.633 / xrp 0.655) while overall   │
│   momentum is BELOW 0.5 (mean-reverting). "Know the trend — short or long" at the    │
│   RIGHT horizon (1h, not 600s). BUILD: at entry signal = -side*mom1h (machine fading │
│   a strong 1h trend) → flip the strongest. GRADE: per-week OOS $/hr vs baseline,     │
│   shuffle floor, big10-flip, fee-accounted; sweep window (1h/2h/4h) + cutoff. The    │
│   pieces converge: R13e flip pre600<-80 (+0.61, the 600s freight-train) is the       │
│   shallow version; 1h is the refinement. This catches the WHOLE move (better than    │
│   the E300 mid-leg stop, which only manages past E300).                             │
│                                                                                     │
│ ⭐ JOB 2: SPIN THE DIPOLE/TREND AGENT BACK UP — build the ACCURATE 1h trend-following │
│   read (dipole at the 1h scale + momentum + S36 divergence). Can it flag+flip the    │
│   big losers at entry better than raw -side*mom1h? (S62 agent tested death-vs-       │
│   recovery = chance; it did NOT test the 1h-trend direction — the new question.)     │
│                                                                                     │
│ Also queued: E300 mid-leg management (working earner, 2nd-window confirm + SOL       │
│   action tuning); FLIP-THEN-MANAGE (R13f). Renders: pip install matplotlib.         │
└─────────────────────────────────────────────────────────────────────────────────────┘
