# NG FORECASTER AGENTS — canonical drop-in files (S103, Greg-ordered)

**The point (Greg, S103): these agent files are STATIC. You drop the SAME files into every group and
run immediately. The ONLY things that change group-to-group are (1) the BRAIN (`knowledge/ng_brain.json`,
which updates via the refine step: s102.2 -> s102.3 -> ...) and (2) the GROUP DATA (the decision-state
file + anchor + basis). No re-authoring prompts per group. No per-group selftests. No re-pulling the
shared stores. Stop re-doing setup.**

## The files (do NOT rewrite per group)
- `blind_shared.md` — shared blind directive (group-agnostic; reads dates/calendar from the state).
- `blind_angle_storage.md` (agent A), `blind_angle_positioning.md` (B), `blind_angle_weather.md` (C)
  — the three diverse-angle blinds (the panel; Greg's weekend-uncertainty idea).
- `refine.md` — the unblinded refine directive.
- `mbo_refine_shared.md` + `mbo_specialist_{A,B,C,D,E}.md` — the MBO 5-specialist causal-refinement
  LAYER (S104; A weekend / B Monday / C core / D Thu-EIA / E Fri-expiry). Runs AFTER a block is
  scored, on the replayed MBO evidence; the coordinator SELECTS the owner per day (guarded — it can
  never emit a number no specialist owns). Round 2 injects the HE24->HE1 boundary handoff chain.

## SHARED SUBSTRATE — done ONCE per session (see GROUP_PRECHECK_S103.md)
Creds (env -u AWS_ACCESS_KEY_ID -u AWS_SECRET_ACCESS_KEY for platform_sync/boto3) + full-history
stores pulled once + the roll map. Covers every group. Do not repeat.

## PER-GROUP LOOP (the only repeated work — turnkey)
1. **State**: `forecast_harness.py decision-state --days <sessions> --mask-after <anchorDate> --out
   renders/ng_refine_s95/grp<N>_state.json`  (sessions = the dates with tape; anchor = prior Fri).
2. **Tape**: pull that group's nymex_cont day-files (front leg; + the roll-contract store for the
   pre-roll leg on a seam block). Anchor = prior Fri actual close + last-hour dir.
3. **Blind panel**: spawn 3 agents (model opus, background), each prompt = "read agents/blind_shared.md
   + agents/blind_angle_<X>.md; GROUP=<N>; STATE_FILE=grp<N>_state.json; ANCHOR=<close,dir>;
   BASIS=<contract + any seam>." -> writes forecasts/grp<N>_agent{A,B,C}.json.
4. **Synthesize (per-event)**: the orchestrator merges the 3 forecasts into ONE `forecasts/grp<N>.json`
   by taking, for each day, the call the brain's rules best support across the three (a REASONED pick,
   NOT a vote tally — pooling as a conclusion is banned). Where the three diverge (esp. weekend
   gaps), record it as a weekend-uncertainty / size-down flag. This ONE file is what gets scored.
5. **Score + render**: `continuous_score.py --guess forecasts/grp<N>.json --actual g<N>_rt.json
   --tag g<N>` + the group's rt/render (continuous_rt.py generically for clean blocks; a hand-basis
   builder like run_g15_rt_s102.py only for a Kalshi-underlying two-leg seam block). PRINT the render.
6. **HARD PAUSE** -> Greg reviews the blind score.
7. **Refine**: spawn 1 agent (model opus) = "read agents/refine.md; GROUP=<N>." -> refined_view +
   ng_brain_<nextver>_proposal.json + summary. Adjudicate (verify incumbents byte-identical, score
   the refined curves), render, PRINT, HARD PAUSE, then MERGE the proposal into ng_brain.json (the
   brain's ONLY update). Commit + push.

## WHY (the record)
S103: G15 refine ran as one refine agent; G16 blind ran as the 3-agent panel. Those prompts are now
these canonical files. From here we spin these up unchanged; only the brain + group data move.
