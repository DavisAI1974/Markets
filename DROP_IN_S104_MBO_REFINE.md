# DROP-IN - next session (the MBO causal-refinement track, off S103)

Branch: `chatgpt/ng-forecaster-s103-audit` (where the whole G15 MBO refine lives). First commands:
`git fetch origin chatgpt/ng-forecaster-s103-audit && git checkout -B chatgpt/ng-forecaster-s103-audit
origin/chatgpt/ng-forecaster-s103-audit`, then `git log --oneline -3` and confirm the tip is the G15 MBO
refine + brain s102.4 doctrine merge.

## THE CANONICAL FILES - USE THESE, DO NOT RE-AUTHOR PER GROUP

- BLIND panel (3 agents): `research/kalshi/agents/blind_shared.md` + `blind_angle_{storage,positioning,
  weather}.md`. Spin the SAME files every group; only the brain + group data + anchor/basis change.
- REFINE: `research/kalshi/agents/refine.md`. The MBO 5-specialist refine adds the causal layer on top -
  see the doctrine below and the driver files.
- RENDERS: `research/kalshi/continuous_rt.py` (generic, non-roll groups) - change the dates. For a group
  that STRADDLES a Kalshi roll, use the two-leg hand-roll (`coordinate_g15_mbo.py` is the worked
  example); `continuous_rt.py` reads NG.n.0 and will draw the wrong leg pre-roll.
- MBO refine driver: `research/kalshi/coordinate_g15_mbo.py` (coordinator: SELECT owner per day, two-leg
  actual curve, scores blind vs refined, renders) + `replay_g15_mbo.py` (feeds MBO through
  NGLiveOperator + build_feature_state). Immutable blind: `forecasts/grp15.json` (NEVER edit).
- Integration gotchas already solved: `research/kalshi/G15_MBO_FIXES_FOR_CHATGPT.md`.

## WHERE THE MBO TRACK STANDS

G15 MBO 5-specialist refine DONE: blind 9/12 (err 526) -> refined 12/12 (err 72). Full writeup +
honest helped/hurt verdict + the 5 specialists' change requests + the HE24->HE1 spec + next-iteration
plan: `research/kalshi/G15_MBO_REFINE_HANDOFF_S103.md`. Read that first.

Brain merged to **s102.4** (36 plays preserved, no play changes):
`doctrine_tier3.refinement_architecture_s103` (the causal-refinement-LAYER doctrine: the old blind stays
the CORE predictor, MBO is a POSTERIOR UPDATE, never a replacement) +
`doctrine_tier3.mbo_refinement_g15_findings` (the result + lesson proposals, forward-test G16/G17 MBO).

Honest one-liner: the MBO TRADE-FLOW layer helps; the MBO BOOK layer hurts if trusted raw and must stay
gated behind a book_trustworthy floor (it was stood down on all 12 G15 days). The working discriminator
is signed-flow-vs-price CONVICTION per phase; DIRECTION stays with the D-1 trade tilt.

## DEFERRED TO NEXT SESSION (Greg, end of S103 - stopped the round-2 run to pick up fresh)

The HE24->HE1 handoff BUILDER is committed and validated (`he24_he1_handoff.py` ->
`forecasts/g15_he24_he1_handoffs.json`, the full G15 boundary chain). The round-2 specialist re-run WITH
the handoff injected was launched but STOPPED before writing (working tree clean, committed round-1
12/12 state intact). Next session:
1. Re-run the 5 specialists round 2 with the handoff injected (A/B/C/D/E) - each starts from its round-1
   posterior, uses the incoming boundary STATE to tighten magnitude/timing, emits an outgoing handoff,
   targets honest under-100 every day. Then re-coordinate + re-score + re-render.
2. WATCH THE COORDINATOR - make sure it ONLY coordinates. Today `coordinate_g15_mbo.py` selects the
   owner per day (the OWNER map) and assembles; it has no forecast/average logic. Add an explicit GUARD
   that asserts the coordinator never emits a day-move no specialist owns (enforce, do not assume).
3. RENDER: print only the ACTUAL curve + the specialists' ACTUAL p50 path - drop the "angular things"
   (the re-anchored-to-actual dashed lines and any straight/scaled angular reconstruction). Plot the
   real forecast path, nothing synthesized.

## NEXT-ITERATION WORK (Greg's asks, in order)

1. Wire the HE24->HE1 handoff object (carry STATE not the day-net number) so the 5 specialists coordinate
   at the day boundary. Spec in the handoff doc.
2. Implement the engine change requests: one session-level book_trustworthy verdict (not 150+ stand-down
   rows), phase-first emission, print-anchored EIA windows, leg_map/seam_event, a named absorption_flag.
3. Re-run G15 MBO with those changes; hold 12/12 with honest under-100 magnitude every day; THEN carry
   the layer forward to G16/G17 MBO as the forward test. "Refine the refinement" until the numbers are
   better before trusting the layer on unseen blocks.

## DATA

NG MBO year pull was running on box `i-08cee7171c0a76a04` (us-east-2), RANGES prioritizing 2026-03..07
first (the groups we still walk) then backfill; raw .dbn.zst to S3 `nymex/ng_mbo/`. NG is already on the
10 (mbp-10), so this is NG-only MBO (CL deferred, live Plus/MBO tier NOT bought). Verify what months
landed at session start (`research/kalshi/pull_ng_mbo_year.py`, marker-resume). git = CODE, S3 = DATA.
AWS: the tx-pair key must be in the process env for any box-side pull (the box Ssm role cannot write S3).

## GUARDRAILS (unchanged)

Immutable blind never edited/regenerated. Don't edit ng_brain.json by hand during a refine - use proposal
files. Execution stays SHADOW (no order routing). Coexist with ChatGPT on the box. No emojis in repo
artifacts. Per-event, never average - the coordinator SELECTS the owner per day.
