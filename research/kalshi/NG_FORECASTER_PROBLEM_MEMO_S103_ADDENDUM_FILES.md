# ADDENDUM to the NG Forecaster Problem Memo — the applicable files to inspect

Companion to `NG_FORECASTER_PROBLEM_MEMO_S103.md`. The memo is self-contained; this lists the ACTUAL
files behind every claim so you (or a reader with repo access) can verify the numbers, read the exact
reasoning, and audit the logic. Paths are relative to the repo root; the forecaster lives under
`research/kalshi/`. Everything is committed on branch `claude/ng-coach-agent-loop-5ha5bf`.

## THE RULEBOOK ("brain") — the logic under review
- `research/kalshi/knowledge/ng_brain.json` — the live brain, **version s102.3, 36 plays**. This is the
  whole rulebook (reasoning_method, the ~36 condition->behavior "plays", the seasonal_salience_slider
  S1/S2/S3 in doctrine_tier3.usage_doctrine, class_curve_profiles, the selector/magnitude additions
  from this session). START HERE to see how rules are structured and scoped.
- Backups showing the progression this session: `ng_brain_s102.1_backup.json` (pre-G15-refine),
  `ng_brain_s102.2_backup.json` (post-G15, pre-G16). Diff these to see exactly what each refine changed.
- The two NEW plays from the G16 refine (the selector + magnitude fixes) are inside ng_brain.json:
  search `selector.divergence_resolution` and `magnitude.s1void_injection_chain_bleed`.
- The G15 rule that was later MIS-SCOPED (the ping-pong seed): search `shoulder_counter_print_damping`
  and `shoulder_weather_band_void` — note their scope wording, then judge whether the blind could have
  known not to over-apply them.

## THE AGENT INSTRUCTIONS (how the blind and refine are told to reason)
- `research/kalshi/agents/README.md` — the turnkey loop + the design intent.
- `research/kalshi/agents/blind_shared.md` — the shared BLIND directive (the open-time reasoning rules;
  this is where "how the blind decides" lives — key to the diagnosis).
- `research/kalshi/agents/blind_angle_storage.md`, `blind_angle_positioning.md`, `blind_angle_weather.md`
  — the three panel "angles" (which driver-family each blind agent weights first).
- `research/kalshi/agents/refine.md` — the REFINE directive (the post-hoc, tape-allowed step).

## G16 — the block in the memo (the UNDER-sized bleed, Mar 29 - Apr 10 2026)
- `research/kalshi/renders/ng_refine_s95/grp16_state.json` — the DECISION-STATE the blind saw (all the
  open-time conditions per day: storage, weather forecast, positioning, curve, event calendar, and the
  never-masked `tape_conditions` incl. `session_b_share`). THIS is "what was knowable at forecast time" —
  audit whether the right call was derivable from it.
- The three blind panel forecasts: `research/kalshi/forecasts/grp16_agentA.json` (storage-first),
  `grp16_agentB.json` (positioning-first), `grp16_agentC.json` (weather-continuation-first). Each has
  per-day `reasoning` — read these to see the competing narratives on the miss days (04-01, 04-06, 04-07).
- `research/kalshi/forecasts/grp16.json` — the SYNTHESIS (our selector). Per day it carries
  `synth_reasoning`, `curve_source_agent`, and `weekend_uncertainty_flag`. The 04-07 averaging error
  (A+250/B+500/C-300 -> flat) is visible here.
- `research/kalshi/renders/ng_refine_s95/g16_score.json` — the per-day BLIND scorecard (guess vs actual,
  direction, drift). This is the 8/11, drift +2365 table.
- `research/kalshi/forecasts/grp16_refined_view.json` — the REFINE's corrected per-day forecast.
- `research/kalshi/renders/ng_refine_s95/g16_refined_score.json` — the refined scorecard (11/11, drift
  +40, every day <40).
- Renders (PNG, the visual): `research/kalshi/renders/ng_refine_s95/g16_continuous.png` (blind vs actual)
  and `g16_refined_continuous.png` (refine vs actual). Blue = real jagged tape; orange = our guess.
- `research/kalshi/renders/ng_refine_s95/g16_rt.json` — the REAL per-day tape (open/close/net + intraday
  curve). The ground truth.

## G15 — the PRIOR block (the OVER-sized give-back; the other half of the ping-pong, Mar 15 - 27)
- Blind: `forecasts/grp15.json`; scorecard `renders/ng_refine_s95/g15_score.json` (8/12, drift -3260).
- Refine: `forecasts/grp15_refined_view.json`; renders `g15_refined.png`, `g15_refined_overlay.png`.
- Actuals: `renders/ng_refine_s95/g15_rt.json`; state `renders/ng_refine_s95/grp15_state.json`.
- Compare G15 (over-sized) vs G16 (under-sized) directly to see the sign-flip of the magnitude error.

## THE REFINE WRITE-UPS (the human-readable "why each day moved")
- `research/kalshi/scratchpad/g16_refine_summary.md` — the G16 refine's per-event narrative + the
  selector-logic finding + the magnitude resolution. (Under scratchpad/, which is gitignored — if it is
  not present in a clone, ask for it; the same content is summarized in the brain's meta.s102_3 note.)
- The prior blocks' equivalents live in the session handoffs (below).

## SESSION RECORD / HISTORY (the recurring pattern across ALL blocks in the memo's Section 2 table)
- `SESSION_HANDOFF_2026-07-21_S103.md` (this session), `_S102.md`, `_S101.md`, `_S100.md`, `_S99.md`,
  `_S98.md`, `_S97.md`, `_S96.md` — each block's blind score, refine score, and lessons. The
  blind-30-70% / refine-90-100% table in the memo is reconstructed from these.
- `CLAUDE.md` — the running project state (top of file = latest; the "Recent arc" list summarizes each
  session).
- `research/kalshi/GROUP_PRECHECK_S103.md` — the group windows + roll map (context for the seasons/regimes).

## What to look at FIRST if you only read three things
1. `agents/blind_shared.md` — how the blind is told to reason (is the flaw in the instructions?).
2. `forecasts/grp16.json` + `grp16_agent{A,B,C}.json` — the actual competing calls on the miss days and
   how we combined them (the selector/averaging flaw, in the raw).
3. `renders/ng_refine_s95/grp16_state.json` — what was knowable at forecast time (was the answer derivable?).
