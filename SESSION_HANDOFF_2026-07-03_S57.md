# SESSION HANDOFF — S57 (2026-07-03) — the ELIGIBILITY RESET: Bybit STRUCK (permanent ban) +
# MEXC killed; mk0 exposed as an unreached tier -> REAL fee models adopted; the fine band
# measured DEAD at every reachable tier; staged-commit sizing (Greg's design) VALIDATED on two
# venues' tape; the MID BAND declared the only way (Greg) -> first probe run, bleed diagnosed
# as theta-giveback at entry -> the S55 R5/R8 lag cuts (dipole dive) = the fix -> S58 = the
# 3-PIECE PLAN, one piece at a time.

## ⛔ STANDING BAN (Greg): BYBIT — NEVER USE FOR ANYTHING
US-ineligible (Bybit's restricted-jurisdictions policy names the United States; UBO-level for
entities per their Business-KYC FAQ; no US-facing intermediary offers its books post-Falcon-Labs
CFTC enforcement). ALL bybit code/data/cells struck this session: platform SANDBOX emptied,
collector workflow deleted from the default branch, probes/ledgers git-rm'd, local tapes
deleted. Never collect its data, run its tape, cite its cells or fee tiers, or propose it.
Greg UI-deletes the two leftover branches data/{sol,eth}-bybit-book (git proxy refuses ref
deletions). ZEC-as-cell died with it (its thesis was the Bybit G4 rebate).
Same class: MEXC = DEAD VENUE (API maker +6bp overrides the marketing 0%; ToS bans HFT/API
algo; unlicensed everywhere incl. home Seychelles; verified freeze-profitable-traders pattern;
volume substantially non-organic). Full citable record: `S57_VENUE_FINDINGS.md`.
NEW STANDING RULE: VERIFY VENUE ELIGIBILITY (jurisdiction + fee reality, primary sources)
BEFORE any venue work — the S57 lesson.

## 1. FEE REALITY (the session's pivot fact)
mk0/tk5 — the basis of every Coinbase paper number since S47 — is an UNREACHED tier. Verified
Coinbase Exchange schedule: 40/60bp under $10k; 10/20 at $100k-1M; 8/18 at $1-15M; 6/16 at
$15-75M; 3/10 at $75-250M; 0.00 maker only at $250M+/30d. The $500k/mo fee-upgrade program is
REAL but matches proportionally (~3-8bp maker for 60 days, once/year) — cannot deliver mk0.
No rebate exists anywhere lawful (Coinbase INTX rebates exclude US; onshore CFTC perps
(Coinbase CFM ~2bp/side + $0.15/contract floor; Kraken/Bitnomial flat $0.15/contract) pay no
maker rebate). STANDING FEE MODELS (print on every test): cb_entry 40/60 | cb_early 10/20 |
cb_real 8/18 | cb_scale 3/10 | cb_top 0/6 (labeled ceiling, NOT held).

## 2. THE BLEED MAP (measured, Coinbase books: sol 99.3h / eth 64.3h)
- FINE BAND = FEE TOLL: gross edge real (+1.9bp/leg, 63.6% win) but 61 legs/hr x ~16bp rt at
  cb_real = -$429/hr (sol) / -$806/hr (eth) at $5k all-in. Negative at EVERY reachable tier
  (-$124..-$4,143/hr); positive only at the 0/6 ceiling. The fine band is structurally dead
  on lawful venues — not a selection/win-rate problem, a toll:edge = 8:1 problem.
- MID BAND (as naively built) = THETA-GIVEBACK AT ENTRY: coarse theta zigzag (60-100bp) with
  entry at the first fine flip AFTER the coarse confirm: SOL -31bp/leg GROSS (fees only 16 of
  the 47 net loss), REVERSED control POSITIVE — the S54 bigline signature; entries land theta
  late, on SOL's window right where the retrace starts. ETH theta80: +21bp/leg gross, +$1.77/hr
  at cb_real, REVERSED negative (right shape) — but n=22, ONE window, PROVISIONAL.
- NOT bleeding: execution (taker 0-1% w/ grace), fine direction (gate-passed), the confirm-add
  mechanism (positive after-signal P&L everywhere measured).

## 3. STAGED-COMMIT SIZING (Greg's design) — VALIDATED, spec frozen this session
Starter in EVERY leg; ALL-IN on confirmation; **$5k IS the all-in (no $10k)**; adds MAKER-
POSTED (taker adds fatal at tight confirms); entry = the zigzag's own barely-late fine-flip.
Evidence: confirmation adds beat random-add by 10-14 sigma on BOTH venues' tape tested; the
add tranche earns +1.4-2.0bp net AFTER the signal (causally clean); loser:winner capital
0.33-0.6; on thin-cushion cells staged BEAT flat outright. Confirm timing: 16% of sol legs
confirm <1s, 27% <5s; SPEED does not grade quality — THAT it confirms does (win 69%->91-95%).
ACROSS trades there is NO signal: P(win|prev win) == P(win|prev loss) +-1-2pp on all 5 cells,
corr(net_i,net_i+1) ~ 0 — probe-then-commit lives INSIDE the trade, never across trades
(re-confirms the anti-martingale kill honestly in this regime). AT COARSE SCALE the +2bp
trigger fires on ~90-100% of legs = no filter — THE CONFIRM THRESHOLD MUST SCALE WITH THE BAND.

## 4. THE LOOKBACK (Greg: "we had the lag time lowered — dipole dive?") — CONFIRMED, S55 R5/R8
- R5 ENTRY: theta-confirm enters 151bp/54min from the true pivot; fine 25bp reversal confirm
  enters 26bp/~1min (saves 125bp/side). Fine confirm is fakeout-blind alone; the DIPOLE DIVE
  read at that moment lifts P(real) 0.36->0.48; R4 dipole class (`continue`/rc~0) = the veto
  for false fires.
- R8 EXIT: with-ride lean CLIMAXES at the top then collapses through zero within 60s at only
  ~28bp giveback (vs 151bp theta-exit) — saves ~123bp/side. `lean_exit` is ALREADY WIRED in
  the executor (S55 R10), never aimed. TOTAL prize ~250bp/leg = the S54 giveback ledger;
  S55 prize table at these costs: theta100 +106..122bp/leg, 5-coin ~+$2,900-3,700/day.
- HONEST REOPENING: S56's ARM-family kill was graded under the Bybit rebate regime (ARM0's
  free volume paycheck made every filter look bad). That regime is BANNED/GONE. At real fees
  the question is 26bp confirm vs 60-100bp theta-giveback — a different question. Re-test at
  MID-BAND ARM levels with the R4 veto; this is not relitigating S56.

## 5. ALSO THIS SESSION (stands)
- Freight-train veto: anatomy REAL (signed fade-velocity corr -0.31; unsigned first pass was
  a tool error), gate UNPROFITABLE (no subgroup sums negative) -> content already inside the
  deployed size axis. Baseline ledger healthy: 26,784 trades, all 5 cells positive (at the
  mk0 record basis — see §1 for what that basis means).
- Eligibility research record (3 agents + subthreads): Bybit/MEXC verdicts, ECP/prime-broker
  law (Falcon Labs precedent; ECP = $10M entity assets), onshore CFTC perp framework (May
  2026), Coinbase fee-upgrade terms — all in `S57_VENUE_FINDINGS.md`. Two parent syntheses
  may still land in-session-log; fold silently if they add anything.
- OPEN VERIFICATION: Kraken Pro US spot maker tiers (possible mk0 ~$10M/30d organic — 25x
  lower bar than Coinbase; verify + bleed-cost math for the tier climb).

## NEXT: S58 = THE 3-PIECE PLAN (one piece at a time — Greg). Read `KICKOFF_2026-07-04_S58.md`.
