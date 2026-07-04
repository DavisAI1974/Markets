# SESSION HANDOFF — S61 (2026-07-04/05) — THE COINBASE EXIT BUILD + THE BIG-LOSER FLIP ARC

**PRIMARY ARTIFACT: `S61_BUILD_NOTES.md`** (round-by-round R1–R13f). This is the headline.
Branch: designated `claude/davisai-markets-s61-2svo2y`, reset to canonical `5c5vg9`
(`636fa31`) at open, +this session's commits. NOTE: designated branch was cut from the wrong
default/crons parent AGAIN (4th session) — reset --hard to canonical at open per drop-in.

## 1. THE COINBASE EXIT BUILD (rounds 1–4) — SHIPPED, canary-clean
- **The 2 S60-casualty agents delivered their numbers.** SOL = PROTECT (zigzag stands; every
  exit candidate negative on the registry cell; power bar: <150 books legs auto-rejects any
  SOL exit pitch; honest fill leaves the +6.11 record intact ∈[+0.94,+6.95]). BTC = plain40
  rider (X=40 primary per Amendment 2; armed-before demoted to SOL-only; ops bar BLOCKING:
  needs exchange-side stop + staleness kill-switch — a tape-graded stop gives ZERO gap
  protection). Both reports IN-REPO (`sol_exit_report_s61.md`, `btc_armedbefore_report_s61.md`).
- **BUILD (a) honest fill model WIRED** (`fill_model="queue"` = maker_book queue-ahead rule via
  cumsum searchsorted; `swing_maker._queue_fill_index`; threaded run_stream + run_midband_cell;
  default `"front"` = bit-identical). MEASUREMENT: queue clears median 8.6s at mid-band, maker_close
  stays 100%, net unchanged — binding constraint is PRICE ELIGIBILITY, not queue depth.
- **The 2 coin exit variants CODED** (`exit_spec` socket in swing_maker: price_stop/armed_dive/
  casc_flip, flat/flip, taker-accounted; `lean_w` wall-clock fix). `COINBASE_MIDBAND_VARIANTS` =
  `doge_coinbase_mb100_cascflip` (S60 spec) + `btc_coinbase_mb80_plainstop` (X=40). paper_trade
  accrues them in SANDBOX. Canary: base cells bit-identical mod the new `stop_exit` key. PASS.
- **CONVERGENCE:** honest fill = build #1 (both agents); FEE TIER outranks all exit code (Greg's
  2 clicks); cover-grace demoted to shadow; fee-aware unload NOT for SOL; cascflip DOGE-only.
- **$/HR STANDING RULE restated (Greg):** profit-per-hour is the scoreboard; per-leg = diagnostics.

## 2. DIPOLE LANE (rounds 3, 9) — 2 agents, all research, nothing wired
- Every rank-A cross-venue/cross-coin TIMING use collapses to lag-0 synchrony at 1s (one finding).
- Coupling decider: DIRECTIONAL not vol-state, but fully LINEAR -> regime-conditioner descriptor
  = rolling cross-coin signed CORRELATION vs BTC (~400s), 1/1000 compute vs KSG.
- Fill-toxicity: no overlay earned; `bn_nf_pre` = free descriptor column on sol/doge only.
- Job C (big losses vs whole dipole family): NOTHING NEW — cross-venue flow separates
  troubled-from-WINNER (z+5-6.8) but CANNOT tell death-from-recovery. Reports in-repo
  (`dipole_lane_report_s61.md`, `dipole_followups_s61.md`).

## 3. THE BIG-LOSER FLIP ARC (rounds 5–13f) — the session's deep thread (Greg-driven)
- **The prize is REAL:** flip-only-the-big-losers (SOL bins, fee=0) = -14.00 -> +6.79 $/hr
  (~$21/hr swing @$5k); the full 3-part oracle (hold winner / flatten chop-loser / flip
  trend-loser) = **+26/hr (15x baseline), 508/508 winners kept.** Structure is perfect.
- **No mid-leg CAUSAL signal reaches it.** Naked stop/flip (both depths, shallow AND deep) =
  killed; flow classifier (agent's z+5-6.8) at the decision moment = z=0.0 vs shuffle, p=0.87 on
  huge-loss-vs-dipping-winner (TWINS at -20 in price/flow/efficiency); efficiency classifier =
  SOL-only + week-fragile. WHY: a big-loser-starting and a winner-dipping are identical at the
  moment you'd act; the only separator is the future (oracle) = winners-invisible law, fundamental.
- **The pre-entry signed return (pre600; -10.3 mean = the SAME quantity throughout):** strongest
  single trait (big losers FADE a running move) but AUC 0.40-0.60. NO pure zone (winners fade
  DEEPER, min -429 vs loser -217; outnumber losers ~2.5:1 at every negative threshold). By
  DOLLARS the deep tail (pre600<-80) tips loser-heavy.
- **⭐ BEST SINGLE-FEATURE LEVER (Greg's flip thesis, R13e): FLIP the deep-fade zone.** Flip
  pre600<-80 = +2.38 $/hr (+0.61 over baseline), beats skip (+0.24), uses ONLY the pre number,
  no classifier — "big losers flip to big winners" carries it. WEEK-FRAGILE (wk1 +2.31 / wk2
  -0.33 / wk3 +2.30 / wk4 -1.66; 2/4 strongly positive, wk4 kills it — the recurring regime).
- **⭐ NEXT-BUILD SPEC (Greg R13f — the wk4 mitigation): FLIP-THEN-MANAGE.** After the flip,
  manage the reversed leg: adverse -> FLATTEN small; favorable -> RIDE. Caps the mis-flip
  downside (the +291bp deep-fade winners we wrongly flip get cut small instead of riding to
  loss). Self-contained price-managed stop; testable WITHOUT the coeff tier.
- **⭐⭐ THE HEAVY TIER (carry-forward, needs Greg's E: drive):** the robust separation of
  big-loser-vs-winner needs the MULTIVARIATE 128-dim OD coefficient signatures + centroid
  dual-print + onset re-anchor (`markets_<cell>_win_cand_sp`, `_win_onset/`, hist AUC 0.72-0.84)
  — archived on GREG'S LOCAL E: DRIVE, not this container. Cheap-feature stack floor = AUC 0.606.
  GET THE COEFFICIENTS -> build the heavy entry fingerprint -> capture the +6.79/+26 prize.

## 4. INFRA / STANDING
- 20 commits this session, all on the designated branch. Reports + build notes + renders in-repo
  (`docs/renders/s61/legs_*.png`). Kraken PARKED throughout (Greg). Fee frame = COINBASE always
  (the "kr_mk0" label was dropped mid-session as confusing — Greg handles the fee tier).
- Standing owed: push clear + the 2 fee-tier clicks + the Kraken Run-workflow click (books still 0).
- Record change owed (BTC Amendment 1): demote armed-before robustness entry to SOL-only in S60.

## 5. NEXT (S62) — see KICKOFF_2026-07-06_S62.md
1. **FLIP-THEN-MANAGE** (R13f): flip pre600<-80 + price-managed stop on the reversed leg;
   per-week (rescue wk4?) + shuffle floor + fee-accounted. The session's live lead.
2. **REGIME GATE** on the flip (stand aside in the wk4-type regime) via the dipole regime
   conditioner (cross-coin corr state) — the alternative robustifier.
3. **GET THE E: COEFFICIENTS** -> heavy entry fingerprint (the real prize path; onset canary +
   per-mid-band revalidation preconditions).
4. Coinbase exit: fee-tier clicks; un-park Kraken exits once Coinbase deploys; Kraken books.
