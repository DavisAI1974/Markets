# SESSION HANDOFF — S96 (work date 2026-07-17) — THREE winter blocks walked (G7, G8, G9-December); protocol settled (one-shot canonical + per-group refine); brain s95.2 -> s98.2 (13 -> 20 plays)

## SESSION TOTAL (updated end-of-session — G8 and G9 ran after the G7 sections below)
- **G8 (Nov 19 - Dec 2)** blind on s96.2: direction 7/10, block lean RIGHT (+3150g/+4640a, drift -1100).
  Refine -> **s97.2** (17 plays): NEW `timing.catalyst_continuity_frontrun` (live cold-ramp -> the resume
  front-runs the print; no ramp -> waits; n=2+2 spanning groups); R2 leg-vs-net split (12/12); R1 ramp/depth
  arms; winter bands; weekend gap = NEW closure info only; thin AMPLIFIES delivery, damps holds. Refined:
  direction 10/10, drift -250. Dec->Jan roll on the 1121->1123 weekend (+0.039). Thanksgiving = a REAL thin
  session (harness map corrected closed->thin; 13.6k prints).
- **G9 (Dec 3-31, the LONG surplus-collapse block, 20 days)** blind on s97.2: **the first BLOCK-LEAN MISS** —
  direction 13/20 but +3000g vs ~-6150a roll-adjusted; the market crested Dec 5 (5.337) and SOLD THE COLD all
  month (surplus +201 -> +15; the walk's first NEGATIVE roll, Jan->Feb -0.504 at the Christmas reopen =
  winter BACKWARDATION). Refine -> **s98.2** (20 plays): NEW `structure.chain_polarity_flip` (parabolic-run
  ARM [>=1.5-2x the season's prior largest swing, >=9 sessions] + band-breaking counter-day CONFIRM with
  old-side continuation-collapse; back-checked on the 1007 top AND 1016 bottom; post-flip the R5 shelf is
  VOID), `structure.failed_rally_tell` (counter-chain spike round-trips -> next session runs hard chain-side),
  `magnitude.crash_regime_bands`; fundamental-inversion DISSOLVED into ONE rule (prints are chain-sided at
  current POLARITY, 7/7); symmetric R1 boundary read (the down-chain's bounces were all R1-readable). Refined:
  direction 18/20 (1210 pause + a -10 flat), cumulative tracks the crash (drift ±1000 until the declared 1223
  +5010 tail; final -2900 vs the blind's +10k float). Irreducibles: two-sided extreme tails, Sunday-gap size,
  third-day pause (n=1 each way), post-termination basing.
- Renders printed to Greg at every step (blind + refined, all three groups). Refine cadence = per group
  (Greg); refine bar = iterate-to-tracking via GENERAL rules only (Greg). All merged brains + proposals +
  backups + records committed. NEXT = G10 (January) — see `KICKOFF_2026-07-17_S97.md`.

---
(The sections below were written at the G7 milestone and stand as the detailed G7 record.)

Branch: `claude/ng-coach-continuous-curve-7pk2gf` (== `claude/ng-coach-agent-loop-5ha5bf` S95 tip + S96 work,
pushed). Read `KICKOFF_2026-07-17_S97.md` next session. git = CODE + committed renders/records; S3 = the tape;
`scratchpad/aws.env` = keys (gitignored; ROTATED this session — the pair pasted S94/S95 is dead).

## HEADLINE
G7 (Nov 5-18, the first winter block) ran as a ONE-SHOT blind holdout on s95.2 -> blinded merge s96.1 -> the
FIRST PER-GROUP refine (Greg's new cadence) -> s96.2. The refine hit Greg's new bar: refined curves track the
actual at direction 9/10 with final block drift +$100 (vs the blind run's 3/10 / +$390), all via GENERAL rules
(n>=2 spanning groups), one day declared irreducible. THREE new plays entered the brain.

## PROTOCOL DECISIONS (Greg, S96 — load-bearing)
1. **One-shot block-blind is CANONICAL** for the skill test (comparable G6->G7->G8...). A day-sequential
   rolling-anchor protocol was built and run for 3 days, then PAUSED (see experiment below) — revisit as the
   LIVE-coach operating mode, not the test.
2. **Refine after EVERY group** (was every 3). Renders PRINTED (sent to Greg) before each refine.
3. **Refine bar raised**: iterate until the refined curves are as close to actual as GENERAL rules carry them —
   never day-tuning. Every rule: condition->behavior + mechanism + n>=2 spanning groups, applied UNIFORMLY
   across all days (a rule that worsens another day = the point-fitting alarm). Days that cannot be brought
   close are DECLARED irreducible with the mechanism why.

## THE S96 SEQUENTIAL EXPERIMENT (paused, recorded — `forecasts/grp7_seq_experiment.json`)
Day-sequential rolling actual anchor (each day forecast blind, flowing from the prior day's ACTUAL close +
per-leg reveal fingerprint via the new `forecast_harness.py reveal` machinery). 3 days run: 1105 -350g/-520a
HIT; 1106 storage-Thu +1450g/+1350a HIT (read 1105's actual tape as give-back-exhausted and sized the Thursday
up — near-exact); 1107 +400g/-720a MISS. The 1106 call is the first direct evidence the day-boundary turn IS
callable from day-N actuals. The refine (below) independently converged on the same conclusion (R1/R4 need
day-N-1 tape).

## BLIND-WALL FIX (S96, `forecast_harness.py`)
The storage/surprise joins used `<= day`: a storage THURSDAY'S OWN 10:30 ET print was leaking into its
open-time decision-state (G3-G6 comparability caveat — they ran with the leak). Now STRICTLY before the day.

## G7 ONE-SHOT BLIND RESULT (s95.2; `renders/ng_refine_s95/g7_score.json`, `g7_continuous.png`, `g7_overlay.png`)
Direction 3/10 days BUT the BLOCK lean was RIGHT: guessed a W netting above the anchor — close-cum +880g vs
+490a, final drift +390 (price 4.405g vs 4.366a). The W landed TIME-SHIFTED: the hard-heat Monday shock was
guessed on 1110 (actual -820) while the real +1580 rally came 1111 Veterans Day — the day sized DOWN on the
thin-holiday flag; both storage Thursdays went UP against fundamental down-leans (1106 +1350a vs -700g through
a bearish +10.8-above print; 1113 +620a vs -900g). Both Mondays were big CONTINUATION days (-820, -1500), not
reversals. NEW located problem: DAY-LEVEL SEQUENCING inside a right block lean. Blinded merge -> **s96.1**.

## THE S96.2 REFINE (per-group, iterative; renders `g7_refined_continuous.png` / `g7_refined_overlay.png`)
Refined curves: direction 9/10, final drift +$100 (+590g vs +490a close-cum); only 1112 (a +/-$100 flat hold
day) missed on sign — declared irreducible rather than tuned. **The five general rules (each n>=2 across
groups; full evidence in the brain):**
- **R1 `direction.giveback_exhaustion_boundary`** (NEW play, 0.55): a give-back day closing >=~40-50% off its
  intraday extreme with a last-hours counter-tick, swing big-legs NOT collapsed -> exhausted; next session
  resumes the swing. Close AT the extreme + last hours extending -> continues. Swing legs collapsed -> stand
  down (the filter that catches 0916). n=9 across G3/G4/G7. THE sequencing answer: 1110's fade closed +690 off
  its low with a 16-18h recovery while its up-legs stayed healthy -> 1111 carried the move.
- **R2** (into `daytype.storage_thursday_magnitude`, 0.6): the print-leg side = the RUNNING swing/turn state,
  NEVER the print/surprise sign — 10/10 Thursdays G3-G7; the swing beat the surprise sign every disagreement.
- **R3** (into `daytype.monday_weekend_gap`): weekend repricing lands at the SUNDAY reopen gap; Monday's US
  session is the gap-REACTION: fade a mature-swing gap, extend a fresh-turn gap, else carry Friday's side.
  Monday-as-reversal RETIRED.
- **R4 `structure.mature_swing_alternation`** (NEW, 0.5): a mature swing (>=4 sessions) never extended a
  material fresh extreme close in the walk (G7 5/5, 1007->1008); young swings (<=3) chain extensions.
- **R5 `level.giveback_origin_shelf`** (NEW, HYPOTHESIS 0.4, n=4): terminal give-back stops at the swing's
  origin shelf; at >=~75% retrace the R1 read INVERTS (capitulation precedes the bounce: 0922->0923,
  1016->1017, 1117->1118, 1029->1030).
**Honest caveat (in the brain + forecast record): R1/R4 consume day-N-1 ACTUAL tape** — the live-coach /
sequential input the one-shot test withholds; that gap is exactly blind-3/10 vs refined-9/10. Irreducibles:
1112-type hold-day sign; extreme-day FULL magnitude (1111 +1580 direction+size-up callable, full size not —
the standing dominant residual); Sunday-gap magnitude (1109 +1560); R5's soft 75% threshold.

## WINTER FUNDAMENTALS (reconfirmed, n=2 blocks)
Rising HDD beats the widening storage surplus at the winter transition: the market rallied +1350 THROUGH the
bearish print on 1106; the surplus widened +130 -> +146 all block yet the block netted UP. Weather regime in
the state ran shoulder -> mod_heat -> hard_heat (1110-1111) -> moderation -> re-cool.

## DATA / ENV
G7 window (Nov 4-18) is ROLL-CLEAN (Dec contract throughout; next roll Dec->Jan lands ~late Nov = INSIDE G8 —
`roll_adjust` handles, but watch it). All 13 session files healthy on S3 (Sundays thin = real). G8 carries
Thanksgiving (11/27 CLOSED, 11/28 early close) in the harness holiday map. eia_surprise regenerated
(DEMO_KEY); curve_regime stayed `unknown` (Databento key not re-pasted this session — forward-curve cache is
a $0.07 re-pull when needed; brain lists curve_regime as ruled-out noise anyway). New machinery:
`forecast_harness.py reveal` (day-sequential reveal packages, kept for the live-coach mode).

## STATE
- Brain `research/kalshi/knowledge/ng_brain.json` = **s96.2, 16 plays** (13 preserved + 3 new). Backups:
  `ng_brain_s95.2_backup.json`, `ng_brain_s96.1_backup.json`; proposal kept as `ng_brain_s96.2_proposal.json`.
- Forecast records: `forecasts/grp7.json` (blind + refined fields per day), `grp7_seq_experiment.json`.
- Renders (committed): `g7_continuous.png`, `g7_overlay.png`, `g7_refined_continuous.png`,
  `g7_refined_overlay.png` + `g7_rt.json`, `g7_score.json`, `g7_refined_score.json`, `grp7_state.json`,
  `grp7_reveals.json`; `fingerprints.json` extended with Nov 4-18 (11 days).

## RULES (unchanged): PER-EVENT, never pool/average; drift is a DESCRIPTOR; general rules only, no
point-fitting; blind wall (decision-time only) + leakage gate; one-shot canonical / refine per group / renders
printed pre-refine; net-of-fee maker AND taker at the money step; provisional-until-live; git=CODE S3=DATA;
NG != WTI; weather forecaster HANDS OFF; keys are SECRETS.
