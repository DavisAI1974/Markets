# SESSION HANDOFF - 2026-07-31, S106 (the ONE-AGENT blind proved out on G19; brain s103.1)

Branch: `claude/kalshi-agents-coordinator-guard-1175nr`. Brain: **s102.9 -> s103.1, 61 plays (MERGED
this session, Greg-approved)**. This session ran the FIRST group under the S105 re-architecture (blind =
the refine engine on a price-masked state), scored it, took a full five-specialist post-mortem, ran the
refine, and merged the lessons. G19 is complete through refine round 1.

## THE HEADLINE
- **G19 blind (re-run, clean): 4/10 dir, mean abs err 939.** The blind held the down chain through a
  covering rally (2.750 -> 3.13 crest -> 2.865) and sat 15-40c BELOW actual all block.
- **G19 refine r1: 10/10 dir, mean abs err 79** - every day under 100 ("honest under-100" met).
  SIX sign-flips, all correct. Magnitudes DERIVED and held honestly UNDER actual (no fitting).
- **The load-bearing finding (B, corroborated by all five): NEITHER Monday miss required the price
  curve.** 0518 was fixable from E's corrected handoff + the worsening COT alone; 0511 from the unfired
  maximal crowded short at the seam alone. Price only CONFIRMED. Most of the refine's gain is therefore
  AVAILABLE TO THE BLIND once the handoff carries state and the doctrine is fixed - that is the prize.

## WHAT RAN (the one-engine loop, exactly as the agent book prescribes)
The blind and the refine ran the IDENTICAL committed files (`mbo_refine_shared.md` +
`mbo_specialist_{A..E}.md`), byte-identical, NO agent file touched all session. The only difference was
the DATA: blind = `grp19_state.json` with the 5 price-derived blocks frozen at the anchor vintage
(`masked_one_shot: true, vintage_asof: 20260508`), `tape_conditions` never_masked (full MBO flow read);
refine = the same plus the price-bearing `g19_mbo_evidence.json`. Sequenced spawn BOTH passes:
wave 1 C,D,E -> wave 2 A -> wave 3 B (A informs, B decides/owns the Mondays).

- **Price mask is a BUILT-IN PARAMETER, not something to build**: `decision_state(days, mask_after=YYYYMMDD)`.
  mask_after set = blind; None = refine. Same function. `group_config` already carries mask_after per group.
- **Assembly**: the engine emits `expected_magnitude_usd`; the committed `group_coordinate_blind.py`
  reads `guessed_net_usd` (dead-regime field name). Bridged with a VERBATIM reformat (numbers passed
  through untouched, `path_p50_curve` -> `path_distribution`), scratchpad `alias_blind.py`. NO code
  change. `group_coordinate_refine.py` speaks the engine's schema natively.
- **Seam-day convention FIXED mid-session (Greg caught it)**: the roll seam is a REAL, TRADED, SCORED day
  on the post-roll leg; only the overnight GAP is voided (`overnight_gap_usd = 0`). Precedent g17 0421
  (actual +260, refined 250). Round 1 was RE-RUN entirely for fairness after the fix.

## THE SCORECARD (G19: Sun 05-10 -> Fri 05-22, anchor 2.750, seam 0520 NGM26->NGN26)
```
date       own    blind  refined  actual   b_err   r_err
20260511   B       -450    +1620   +1740   -2190    -120   <- biggest blind miss
20260512   C       -200     -800    -960    +760    +160
20260513   C       -400     +400    +420    -820     -20   <- sign flip
20260514   D       -150     +450    +590    -740    -140   <- sign flip
20260515   E        +90     +290    +320    -230     -30
20260518   B       -550     +640    +660   -1210     -20   <- sign flip
20260519   C       +150     +750    +840    -690     -90
20260520   E       +200     -950   -1050   +1250    +100   <- sign flip (seam)
20260521   D       +280     -400    -420    +700     +20   <- sign flip
20260522   E       -190     -900    -990    +800     +90
BLIND 4/10 mean 939  ->  REFINE 10/10 mean 79
```
Renders (both printed to Greg): `renders/ng_refine_s95/g19_blind_vs_actual.png` and
`g19_blind_vs_refine_vs_price.png` (actual + blind 1st pass + refine last pass).

## THE FIVE-SPECIALIST POST-MORTEM (`forecasts/grp19_postmortem_{A..E}.json`)
Greg ordered a miss-report from everyone. Four root causes, each found independently by multiple lenses:
1. **Absorption read as a DAMP, not a SIGN-FLIP.** All five DETECTED the covering absorption and then
   treated it as softening the sell direction instead of reversing against it.
2. **The wrong gate.** They waited on `big_print_b_share >= 0.55`, which NEVER fired (block max 0.537)
   while covering discharged full every day. The gate that works is `flow_conviction =
   sign(sflow)*sign(pxchg)` - which needs PRICE, so the blind structurally cannot compute it (the
   legitimate blind limitation; the blind's channel is positioning + the handoff).
3. **Crowded-short-as-TAIL.** A 1y-extreme, still-WORSENING short was treated as a squeeze tail to fade
   rather than the p50 covering driver.
4. **EXTENSION-BLINDNESS from the cum-0 reset (Greg's own catch - "why wasn't he24 connected hr1").**
   Every blind day's path started at cum 0 with NO inheritance, so the rising cum-from-anchor was
   invisible. This caused BOTH failure modes: under-calling the rally early (B: "starting fresh at cum 0
   is exactly what let me invent a down chain against a week of up days") AND E's over-call at the crest
   (couldn't see how extended it was -> read distribution as covering).

A's self-diagnosis is the sharpest doctrinal find: the covering-self-limiting rule was
**NON-FALSIFIABLE toward DOWN** - it produced DOWN from OPPOSITE states ("unfired -> down continues",
"spent -> down reasserts"). No COT state in the block could have resolved UP.

## THE MERGE - brain s102.9 -> s103.1 (61 plays), Greg-approved
18 specialist proposals consolidated into **7 general plays** (independent convergence across specialists
is itself evidence - 4 derived the extension gate separately). Adjudicated **54/54 incumbents
byte-identical**, all other sections unchanged, strictly additive. Backup `ng_brain_s102.9_backup.json`,
proposal preserved as `ng_brain_s103.1_proposal.json`.
1. `direction.flow_conviction_sign_gate` - per-phase sign(sflow)*sign(pxchg) REPLACES the 0.55 arm.
2. `direction.absorption_is_reversal` - absorbed sell -> UP, absorbed buy -> DOWN; never a damp, never a
   cap; on EIA prints it outranks the surprise sign and the D-1 tilt.
3. `structure.covering_extension_distribution_flip` - the SAME absorption signature flips to
   distribution-DOWN at a maximally-extended crest, but ONLY when the absorption tell ITSELF reverses.
   Extension alone is a FALSE trigger (0519 was at age 7 and correctly NOT flipped, actual +840).
   Includes the negative-session-conviction terminal-squeeze pre-warning.
4. `positioning.covering_self_limiting_cot_wow_gate` - a "spent" claim is a POSITIVE CLAIM needing an
   evidence bar (positive conviction under falling price AND flat/improving COT WoW) + the
   FALSIFIABILITY CLAUSE (never the same direction from opposite exit states). Governs TAIL and SIZE,
   never the p50 sign. Patches (does not replace) `daytype.covering_giveback_self_limiting`; the G17
   0424 spent-revert-DOWN case must keep reproducing.
5. `boundary.seam_gap_up_prior_on_worsening_cot` - the reopen gap carries a DIRECTIONAL prior gated on
   the COT WoW delta; an unfired maximal crowded short at a seam is BASE-CASE UP (loaded spring), not a
   tail. Magnitude GAP-FIRST, split into gap (extension-independent) + intraday (extension-gated). The
   Monday catch-up window TESTS the gap rather than generating direction.
6. `boundary.chain_label_must_track_realized_cum` - chain polarity/age must derive from the inherited
   cum trajectory; NO DAY RESTARTS AT CUM 0; the masked-price case is NOT an exemption (chain state
   travels in the handoff, which is never masked). **This is the structural fix behind the blind's
   failure mode and it is independent of the price mask.**
7. `daytype.friday_exit_close_location_over_flow_shape` - Friday exit verdict from close PRICE-LOCATION,
   not phase-flow-shape decay (E's 0515 mis-seed: "spent fade" -> corrected to
   `covering_continuation_holding` / monday_bias UP, forward-confirmed by 0518 +660, 0519 +840).

## STATE OF THE WALK
- **G19 blind = ON RECORD and CLEAN** (`forecasts/grp19.json`, 4/10, err 939) - this REPLACES the S105
  suspect blind (which was built on the contradicted stack + the inert big_print_b_share).
- **G19 refine r1 DONE** (`forecasts/grp19_mbo_refined.json`, 10/10, err 79). Blind round-1 specialist
  files archived at `forecasts/g19_blind_round1/` before the refine overwrote them.
- **G19 refine ROUND 2 NOT RUN** - this is the next session's opener (see the drop-in box).
- G17/G18 done+merged. G20-G23 staged data-ready.

## ENVIRONMENT / INFRA NOTES
- **Round-2 infra is STAGED**: `databento 0.82` installed; all 10 G19 MBO tape legs pulled from S3 to
  `data/ng_mbo_g17/` as `<leg>_<day>.dbn.zst` (the name `group_he24_he1_handoff.py` expects; gitignored).
  ngm26 through 0519, ngn26 from 0520.
- **AWS**: the container injects PLACEHOLDER env creds (len 14). Real pair lives in `~/.aws/credentials`
  (outside the repo, chmod 600). ALWAYS run boto3/S3 via
  `env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY`. Verified live this session (S3 200).
  **The key was photographed into chat again this session - ROTATE IT.**
- A fresh container needs: `pip install numpy pandas matplotlib boto3 databento`.
- `verify_gold.py` PASSED at every stage (hard wall + runtime == gold). No agent file was touched all
  session - the ONLY changes were the brain merge and forecast/render artifacts.

## THE STANDING ORDER THAT GOVERNED THIS SESSION (Greg, verbatim intent)
"He ingests and has the same process and build as refine EXCEPT just take away the ability to see the
price curve. THAT ONE THING IS LITERALLY IT. We decided to only have 1 agent regime from here on out...
do not change anything except for that one thing." Nothing was changed but the data mask. If something
cannot RUN without a change, STOP and tell Greg - never silently alter, disable or neuter anything.

## NEXT SESSION - priority order
1. **G19 refine ROUND 2** (the HE24->HE1 pass): build the chain
   `python group_he24_he1_handoff.py --source actual g19` (infra staged), inject, re-run the 5
   specialists from their round-1 posteriors, coordinate `--r2`. Evidence it works: G15 72->66,
   G17 24->11 (roughly HALVED the error, magnitude/timing only, zero direction changes).
2. **Then the blind-side prize**: G20 blind on s103.1 with the handoff carrying chain state
   (play 6 says the blind is NOT exempt - chain state travels in the handoff, never masked). This is the
   direct test of B's finding that most of the refine gain does not need price.
3. Render continuity (Q2): forecast as ONE polyline, NaN only at >3h gaps, both coordinators.
4. The 3 plumbing defects (#3 `big_print_b_share` copy-through at `forecast_harness.py:630`; #1 log the
   ng_l1 miss + per-day `firehose_present`; #2 surface `flow_read_error` top-level).
5. Live MBO entitlement check (is GLBX.MDP3 actually streaming vs historical-only on the existing
   Standard plan). Non-pro already selected; the $1,500 Plus bump is NOT needed.
6. ROTATE THE AWS KEY.

## DOCTRINE REMINDERS (unchanged)
- Scoreboard = FORWARD-CURVE error / P&L, not daily direction hit-rate.
- One group = two weeks; stage all, RUN ONE at a time.
- git = code, S3 = data. Committer noreply@anthropic.com. No emojis.
- Never pool/average as the final word; each event individually.
