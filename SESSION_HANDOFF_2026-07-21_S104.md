# SESSION HANDOFF - S104 (work date 2026-07-21) - G15 MBO round 2 (12/12, err 66), coordinator GUARD + actual-curves-only render, the FRIDAY->MONDAY CASCADE cleanup (3 solo specialists), brain s102.4 -> s102.5 (46 plays)

Branch: `claude/kalshi-agents-coordinator-guard-1175nr` (based on `chatgpt/ng-forecaster-s103-audit`'s
tip; all S104 work committed+pushed here). git = CODE, S3 = DATA.

## SESSION TOTAL (chronological)

1. **ENV**: tx-pair creds (Greg pasted; STS PASS ...4170). NG MBO YEAR PULL IS DONE on S3
   (`nymex/ng_mbo/_DONE`, 312 files, Jul 2025 - Jul 2026 = G16/G17/G18 all covered). TRAP CONFIRMED:
   the year-pull files are NG.n.0 continuation = the WRONG leg for pre-roll days of a Kalshi-roll-
   straddling group (G15's 0313-0319 need `nymex/ng_mbo_ngj26/`). Mixing per-contract pre-roll +
   year-pull post-roll reproduced the committed round-1 score byte-identical.

2. **COORDINATOR GUARD (the branch's namesake, Greg's ask)**: `coordinate_g15_mbo.py` now enforces
   SELECT/ASSEMBLE-only - every emitted day-move must be verbatim the owner specialist's own number;
   missing/non-numeric/wrong-owner posteriors are hard failures, never a silent fallback to the blind
   (the old code fell back silently). All three violation paths negative-tested.

3. **RENDER RULE (Greg's ask)**: actual two-leg curve + the forecast's OWN p50 path ONLY. Dropped the
   re-anchored dashed lines AND the net-target scaling; closed-market gaps get NaN breaks (no synthetic
   bridges). Round-1 score stayed byte-identical through both changes.

4. **CANONICAL MBO SPECIALIST FILES**: `agents/mbo_refine_shared.md` + `agents/mbo_specialist_{A..E}.md`
   (A weekend / B Monday / C core / D Thu-EIA / E Fri-expiry) - static drop-ins like the blind panel,
   including the round-2 HE24->HE1 handoff protocol + output contract. Registered in agents/README.md.

5. **G15 MBO ROUND 2 (handoff-injected)**: 5 Opus specialists re-ran from round-1 posteriors with
   `g15_he24_he1_handoffs.json` injected; coordinator `--r2` (guard active). **12/12 dir, mean abs err
   66** (round 1: 72; blind: 526). 10/12 days under-100; 0318 held +1500 (the confirmed base - the
   +1900 tail is reactive, not claimable); 0327 at the 100 bar. C moved 0317 +50->+30 and 0325
   +560->+600 via the prior-exit last_hour_dir magnitude gate. Renders PRINTED to Greg (new style).
   Forward-testable seam tells: D's prior-close flow-vs-direction disagreement (flagged 0327's covering
   rally a session early); B's seam chain-age read (young chain -> late buys accommodated/shallow;
   mature -> absorbed/deep).

6. **THE FRIDAY->MONDAY CASCADE (Greg: "we missed Monday so bad because we missed Friday so bad")**:
   three solo block-spanning cleanups, sequenced upstream-first per Greg ("I can't blame mon guy"):
   - **E (Friday)**: 11/22 scored Fridays wrong-signed blind (worst day-class); **10/14 bad Mondays
     root to a mis-read Friday exit**. 3 plays: friday_exit_decomposition (hand off exit TYPE
     CREST_TRIM_FADEABLE/POSITIONING_SPENT_FADE/FUNDAMENTAL_CARRY_CONTINUE/MOMENTUM_CARRY, never the
     day-net), weekend.carry_realization_flip (driver realizing over the weekend flips Monday to
     sell-the-news), friday_exhausted_extreme_giveback. + the 9-field weekend handoff_out spec.
   - **C (mid-week)**: 44-day sweep. M4 stretched extreme close (coff>=0.95 after >=$1200 run) gives
     back next day 6/6 = the midweek->Thursday failure link; M2 prior-exit last-hour magnitude gate;
     M1 giveback-exhaustion reversal recognition (n>=7); M3 young-chain full-band (n=3). + the
     corrected exit-read protocol (STRETCHED / MATURE-SHELF+TELL / YOUNG-CHAIN verdicts).
   - **B (Monday, run LAST with clean inheritance)**: 11/22 Mondays wrong-signed blind; **10 of 11
     flip right-signed on corrected Friday exit_type/monday_bias inheritance alone**. Sum |err|
     35,030 -> 10,880 (inheritance) -> 8,000 (native rules); excluding 3 declared-irreducible days
     (1027 fresh-shot gap, 0202/0309 crash tails) the other 18 Mondays sum 1,930 (mean ~107). 3 plays
     consuming E's fields: seam_chainage_accommodation_gate (MBO-proven G15), overnight_headfake_into_
     catchup, catchup_window_tilt_gate.

7. **MERGE (Greg-ordered): brain s102.4 -> s102.5, 36 -> 46 plays.** All +10 cleanup plays PROVISIONAL
   / forward_evidence NONE; doctrine_tier3.friday_monday_cascade_s104 records findings + protocols +
   the S104 run protocol. 36/36 incumbents verified byte-identical; backup ng_brain_s102.4_backup.json.
   Cleanup tables preserved committed: CASCADE_S104_{friday_cleanup,monday_fix}_summary.md.

## GREG'S STANDING ORDERS SET THIS SESSION (now in the brain doctrine)
- **FOCUS = FRIDAY AND MONDAY.** Friday is the cascade root; a wrong first Monday moves the whole week.
- **Group windows: Sunday reopen -> the SECOND Friday, always.** Orphan extra days fold in; the
  boundary never moves.
- **FIVE specialists for BOTH blind and refine, every run.** Coordinator selects under the guard.
- **Renders: actual curves + own p50 path only.** Target honest under-100 every day.

## OPEN AT CLOSE
- **E's Friday SELF-ANALYSIS: DONE** (`CASCADE_S104_friday_self_analysis.md`). VERDICT: ONE dominant
  flaw - PRIOR-OVER-STATE on Friday direction (13/18 misses, 72%); zero wrong signs from absent data
  (the cascade is free to fix); 1.25x cascade ratio (23,130 downstream vs 18,530 direct, 8 of the 10
  root-caused bad Mondays). Self-prescription #1 = a Friday turn/exhaustion GATE on direction (free
  rule) - turn into a proposal play before G17.
- **SUNDAY CONVENTION: DECIDED - FOLD (Greg, S104.1)**: the ~2h Sunday reopen folds into Monday (CME
  trade-date convention; Greg: an unanchored orphan window "has potential to really throw things off").
  Monday = Fri close -> Mon close; one Friday->Monday seam; A narrows to holiday reopens. Effective
  G17 onward; historical blocks keep their standalone-Sunday scores (footnote comparisons).
- **G17 (Sun 04-12 -> Fri 04-24) parked** - Greg: cascade cleanup first. Runs next session via the
  canonical loop with 5-specialist blind (files to write: blind day-class lenses; blind_shared.md wall
  applies) + two-leg May/NGK26 -> June/NGM26 basis, seam 04-21.
- Engine change requests (book_trustworthy bit, phase-first, print-anchored EIA windows,
  leg_map/seam_event, absorption_flag) still queued; then G16/G17 MBO forward tests.
- G17 substrate NOT built (stores not pulled this session beyond list; tape not pulled).

## RULES (unchanged) - see DROP_IN_S105.md guards block.
