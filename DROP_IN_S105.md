# DROP-IN - S105 (Friday/Monday focus era; G17 5-specialist blind is the opener)

**FIRST: SWITCH TO THE BRANCH.** The harness auto-branch is NEVER the work. Run:
`git fetch origin claude/kalshi-agents-coordinator-guard-1175nr && git checkout -B claude/kalshi-agents-coordinator-guard-1175nr origin/claude/kalshi-agents-coordinator-guard-1175nr`
Tip must begin "S104". (This branch carries S103's MBO track + all of S104; it is the current trunk of
the forecaster work.)

**AWS**: tx-pair (ID `AKIAYI6JDCBVLKYQGLMH`, ...4170, secret begins `txRGHd`; Greg pastes if not on
disk). Write scratchpad/aws.env + ~/.aws/credentials; STS verify; ALWAYS
`env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY` for boto3/platform_sync (placeholder-env trap).

## READ, in order
`SESSION_HANDOFF_2026-07-21_S104.md` -> this drop-in -> `research/kalshi/agents/README.md` ->
`knowledge/ng_brain.json` (**s102.5, 46 plays** - the S104 adds: friday_exit_decomposition,
carry_realization_flip, friday_exhausted_extreme_giveback, 4x midweek.*, 3x monday.*, +
doctrine_tier3.friday_monday_cascade_s104) -> `research/kalshi/GROUP_PRECHECK_S103.md` ->
`CASCADE_S104_friday_cleanup_summary.md` + `CASCADE_S104_monday_fix_summary.md`.

## STANDING ORDERS (Greg, S104 - the operating frame)
- **FOCUS = FRIDAY AND MONDAY.** Friday misses cascade for DAYS; the first Monday being off moves the
  curve for the whole week. Friday's handoff_out (exit_type + monday_bias, 9 fields - spec in the
  brain doctrine) is the load-bearing artifact of every block.
- **Group windows: Sunday reopen -> the SECOND Friday, always.**
- **FIVE day-class specialists for BOTH blind and refine** (A weekend/B Monday/C core/D Thu-EIA/
  E Fri-expiry). Coordinator SELECTS the owner per day under the GUARD (never emits a number no
  specialist owns - guard pattern in coordinate_g15_mbo.py, port it to every coordinator) **+ the
  FRIDAY SIGN-OFF (Greg S104): the coordinator REFUSES to assemble a weekend-feeding day whose
  posterior lacks handoff_out - the Friday cascade is the coordinator's OK too, not just E's.**
- **Renders: actual curve + the forecast's OWN p50 path only** (no re-anchored/scaled lines, no
  gap bridges). Target **honest under-100 every day**.

## E'S FRIDAY SELF-ANALYSIS (DONE at S104 close - `CASCADE_S104_friday_self_analysis.md`)
VERDICT: ONE dominant flaw, same every time - **PRIOR-OVER-STATE on Friday direction** (13/18 misses,
72%): the sign came from a day-class default / chain extrapolation instead of the exhaustion/turn
state ALREADY in decision_state. NOT ONE wrong Friday sign was caused by absent data - the whole
cascade is free to fix. Cascade accounting: 9 downstream days wrecked (8/9 sign-wrong), 23,130 USD
downstream vs 18,530 direct = 1.25x ratio; these are 8 of the 10 root-caused bad Mondays. Ranked
self-prescription (#1 = a Friday turn/exhaustion GATE on direction, rule, free; only the magnitude
tail costs a data build and it never flips a sign). S105: turn prescription #1 + #2 (crest-trim
discriminators) into proposal plays before G17's blind, so E runs G17 with the gate in hand.

## JOB 1 - G17 BLIND (Sun 04-12 -> Fri 04-24), 5-specialist panel
- Substrate: shared stores via platform_sync (list in GROUP_PRECHECK_S103.md) + G17 tape +
  `forecast_harness.py decision-state --days <sessions> --mask-after 20260410 --out grp17_state.json`.
  Anchor = 04-10 close + last-hour dir. Basis: **May/NGK26(996) through 04-20, June/NGM26 from 04-21**
  (seam 04-21 never-traded). TAPE TRAP: NG.n.0 continuation is the wrong leg near the seam - use
  per-contract stores for the legs (pattern: nymex/ng_mbo_ngj26 was G15's; check for an NGK26/NGM26
  store or pull per-contract).
- BLIND = 5 day-class specialists (blind-walled per agents/blind_shared.md; write thin day-class lens
  files agents/blind_class_{A..E}.md off the mbo_specialist lenses, minus any realized/MBO content).
  Ownership: A=0412,0419 B=0413,0420 C=0414,0415,0422 D=0416,0423 E=0417,0421(seam),0424.
  E MUST emit the 9-field weekend handoff_out; B consumes exit_type+monday_bias, never the Friday net.
- Coordinate per-day by ownership (GUARDED), score, render (two-leg hand-roll like
  coordinate_g15_mbo.py's build_actual - continuous_rt.py generic reads n.0 and is WRONG for the
  pre-roll leg), PRINT, **HARD PAUSE for Greg**, then refine = the SAME 5 specialists (unblinded,
  agents/mbo_refine_shared.md pattern) -> proposal -> adjudicate -> render -> PRINT -> merge on Greg's
  go. FORWARD-TEST the s102.5 cascade plays: this is their first blind test.
- Then G18 (Sun 04-26 -> Fri 05-08, clean June). Then engine change requests + G16/G17 MBO forward test
  (see the S103 handoff's list: book_trustworthy bit, phase-first, print-anchored EIA windows,
  leg_map/seam_event, absorption_flag).

## OPEN DECISION (ask Greg before G17 if unanswered)
**Sunday convention**: keep the ~2h standalone Sunday day, or fold Sun 18:00-20:00 ET into Monday
(CME trade-date convention, one Friday->Monday seam)? RECOMMENDED: fold. Recorded in
doctrine_tier3.friday_monday_cascade_s104.open_decision_sunday_convention. Affects the G17 day list
(0412/0419 as days vs folded into 0413/0420).

## DATA
NG MBO year pull DONE (s3 nymex/ng_mbo/_DONE, 312 files, 2025-07..2026-07). NG L1 pull: check
nymex/ng_l1/_DONE (was ~105/250 at S103 open); if done queue CL L1; stop the box only when all pulls
done. ChatGPT coexists on the box - do not collide. git = CODE, S3 = DATA.

## GUARDS (unchanged, non-negotiable)
PER-EVENT never pool/average as conclusion; blind wall decision-time only + tape_conditions
never-masked; immutable blinds never edited; renders PRINTED before merges; magnitudes DERIVED never
fitted; day-class first; S1/S2/S3 every open; rolls marked never traded; flips C1+C3+C4 never
front-run; net-of-fee maker AND taker; execution SHADOW; NG != WTI; weather forecaster HANDS OFF;
keys are SECRETS, never committed; no emojis.
