# AGENT RUNBOOK — S95 (how to re-spin the two agent steps of the NG forecaster loop)

The loop runs IN the Claude env: sub-steps are spawned via the Agent tool (subagent_type general-purpose,
run_in_background). Their prompts are captured here so the loop is re-spinnable cold without reconstructing
them. Both work off committed files only (no S3/creds needed inside the subagent — the substrate is pre-built).

Shared discipline injected into BOTH prompts (Greg, load-bearing):
- PER-EVENT only; NEVER average/pool/median/ratio/"X-of-N". Name days individually.
- DRIFT is a DESCRIPTOR (tie to conditions), not an error to minimize.
- NOT POINT-FITTING — only GENERAL condition->behavior rules (mechanism + n); a rule explaining one day is
  discarded. Curve-tracking is a byproduct of the reasoning being right.
- Only GENERAL rules enter the brain; per-day reasoning stays in the forecast record.
- Skill is judged on the NEXT blind block + live, never the refined-on days.

═══════════════════════════════════════════════════════════════════════════════════════════
## STEP A — the BLIND forecaster (the true-holdout skill test; how G6 was run)
Purpose: forecast a NEW block with NO tape, from the brain + decision-state + anchor, day-into-day continuous.

Setup before spawning (orchestrator, has creds):
1. `python forecast_harness.py decision-state --days <block days> --out renders/ng_refine_s95/grpN_state.json`
2. Anchor = the actual hr24 (last-hour price + net direction) of the day BEFORE the block. Get it from
   `fast_tape.fast_load_day("NG", <day-before>)` (last price + last-hour dir).

Prompt skeleton (fill <...>):
> You are the BLIND forecast agent for the NG intraday forecaster, forecasting Group-N (<dates>). Absolute
> BLIND WALL: never read/load/infer any actual data for the block (no S3, tape, fingerprints, *_rt.json for
> those dates). Forecast ONLY from: knowledge/ng_brain.json (read fully — reasoning_method, plays,
> fingerprints [execution-layer, not open-time inputs], mechanisms), renders/ng_refine_s95/grpN_state.json
> (the per-day blind-safe decision-state), and the ANCHOR (<day-before> closed <price>, last hour <dir>).
> Reason CONTINUOUSLY day-into-day: day-1 flows from the anchor; each later day flows from the PRIOR day's
> GUESSED close (hr24->hr1, no flat reset). Apply block_open_lean / swing_exhaustion_reversion at the open,
> the day-type priors, catalyst-condition magnitude sizing. Open-time from-flat side is a coin-flip — forecast
> the expected dominant MOVE + SHAPE + block lean, not a precise tick side. Write forecasts/grpN.json:
> {group, tag, brain_version, anchor, days:[{date,dow,group,archetype,reasoning (REQUIRED, day-into-day why),
> overnight_gap_usd, guess_curve [[et_hr,cum_from_open_usd] on grid 20,22,0,2..18,20], guessed_net_usd}]}
> MULT=10000. Return a per-day summary + the block-level lean call.

Then SCORE: `python continuous_rt.py --anchor <day-before> --start <first> --end <last> --tag grpN --guess forecasts/grpN.json`
(real-RT chart + forecast) and `python continuous_score.py --guess forecasts/grpN.json --actual renders/ng_refine_s95/grpN_rt.json --tag grpN` (skill overlay + scorecard).

═══════════════════════════════════════════════════════════════════════════════════════════
## STEP B — the UNBLINDED refine (deep dig on PAST scored consecutive blocks; how G3-5 was refined)
Purpose: learn WHY days moved from the real tape + fingerprints; correct + generalize the brain; produce the
refined guess CURVES for rendering.

Setup before spawning:
1. `continuous_rt.py` for the block window -> `<tag>_rt.json` (REAL prices + detected `rolls`).
2. `characterize_turns.py <all block days>` -> `fingerprints.json` (per-leg flow/turn/continuation).
3. `extract_guesses.py` -> `guesses.json`; `decision-state` -> `<tag>_state.json`.

Prompt skeleton:
> You are the UNBLINDED refine agent for the NG forecaster, re-doing the G3/4/5 refinement on ROLL-CLEAN data.
> CONTRACT-ROLL CORRECTION (load-bearing): the continuous series rolls ~monthly (see `rolls` in the rt.json);
> a roll is a FAKE price jump (calendar spread), not a move. Void any finding built on a cross-roll gap; the
> "0925 +$2760 overnight gap" was the Oct->Nov roll (0.276*10000). Intraday per-day nets are roll-clean.
> Inputs (read all): knowledge/ng_brain.json; renders/ng_refine_s95/{g3g4g5_rt.json (REAL + rolls),
> fingerprints.json (dip_imb_level flow; turn_far_thinning is NOISE; continuation-asymmetry + peaked_fast +
> dip_imb_level carry direction/hold/turn), guesses.json, g3g4g5_state.json}; forecasts/grp{3,4,5}.json.
> Fold in the latest blind HOLDOUT result. Tasks: (1) full refinement across all days, tie drift->conditions,
> GENERAL rules only, correct roll-contaminated claims; (2) produce a RENDERABLE refined guess CURVE per day by
> applying the refined general reasoning to each day's decision-state (day-into-day, NOT tracing the actual) ->
> write overnight_gap_usd + guess_curve + guessed_net_usd into forecasts/grp{3,4,5}.json; (3) MERGE a brain
> proposal ng_brain_s95.X_proposal.json (keep all plays, refine confidences, meta note) — do NOT overwrite
> ng_brain.json. Return a per-event summary. G3/4/5 ONLY (never the scattered Group-2).

Then RENDER: `python continuous_rt.py --anchor <anchor> --start <first> --end <last> --seams <g4,g5> --tag g3g4g5 --guess forecasts/<combined-or-per-group>.json`
and REVIEW the proposal before merging into `ng_brain.json`.
