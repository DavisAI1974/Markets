# REFINE AGENT — directive (CANONICAL, drop-in every group; S103)

CANONICAL FILE. Do NOT rewrite per group. Only the BRAIN version and the GROUP DATA (which grp<N>
files) change. Static from S103 to session end.

You are the UNBLINDED REFINE AGENT, refining the group named in your spawn params, after its blind
panel has been scored. cd to `/home/user/Markets/research/kalshi`; committed files only (no S3/creds).

## SPAWN PARAMS
- GROUP tag (e.g. g15) and N.
- The blind result to refine (the scored grp<N>.json + grp<N>_score.json) + which brain version is live.

## BLIND WALL (refine is legit-unblinded on THIS past, already-scored block)
You MAY read the realized tape/curves for this group (it is scored). Two guardrails:
1. Extract GENERAL condition->behavior MECHANISMS (+ n), NEVER memorized day-specific outcomes. A
   rule explaining exactly one day and generalizing to nothing is DISCARDED.
2. Skill is judged on the NEXT blind block + forward-live, never the refined-on days.

## READ (all committed)
- `knowledge/ng_brain.json` — current BRAIN. Read fully; note every `g<N>_forecast`/holdout note and
  forward_evidence already recorded — BUILD ON them, do not redo.
- `forecasts/grp<N>.json` — the synthesized blind forecast WITH per-day reasoning (what you refine).
  (Panel era: also `forecasts/grp<N>_agent{A,B,C}.json` — the three angle reads, for diagnosing which
  angle owned each miss.)
- `renders/ng_refine_s95/grp<N>_state.json` — the per-day decision-state = your MEASURABLE STATE.
- `renders/ng_refine_s95/g<N>_rt.json` — REAL prices + curve_2h + any roll seam (never a move).
- `renders/ng_refine_s95/g<N>_score.json` — the per-event scorecard (drift = descriptor).
- fingerprints (leg-grain) if built for this group; if NOT (creds-gated), use tape_conditions D-1
  session flow and FLAG anything needing leg grain for a creds-gated follow-up — do NOT fabricate.

## THE JOB
1. DAY-SEQUENCING AUDIT first (real tape, incumbent rules): classify each miss as (a) one-verdict
   propagation the running logic self-corrects vs (b) a genuine rule GAP.
2. MAGNITUDE / regime investigation: test the block's framing per-event (do NOT assume the
   kickoff's characterization); resolve where the drift came from, per-event, from measurable state.
3. Explain each miss per-event as a GENERAL rule (mechanism + n); derive magnitudes from measurable
   state, never fitted; record rejected scalings + which the back-check breaks.
4. LEG-GRAIN only if a signature needs it (else flag creds-gated).
5. ITERATE TO DERIVED: rebuild the refined guess so EVERY step <= ~250 and residuals are
   band-position, EVERY residual DERIVED (Greg's "lines darn close to perfect").

## OUTPUTS (do NOT overwrite the blind record or the live brain)
- `forecasts/grp<N>_refined_view.json` — refined guess per day {date,dow,archetype,overnight_gap_usd,
  guess_curve,guessed_net_usd,day_move_usd,refine_reasoning}. Apply refined reasoning day-into-day,
  NOT tracing the actual.
- `knowledge/ng_brain_<nextver>_proposal.json` — copy the live brain, bump version, keep ALL
  incumbent plays (supersession), refine confidences on touched plays, add NEW plays (mechanism + n +
  status + forward_evidence NONE), add a meta refine note. Do NOT overwrite ng_brain.json.
- `scratchpad/g<N>_refine_summary.md` — per-event summary + the block finding + proposed rule items +
  creds-gated flags.

## GUARDRAILS
PER-EVENT only (never pool as a conclusion; drift is a descriptor). GENERAL rules only. Magnitudes
DERIVED not fitted. DAY-CLASS first then S1/S2/S3. SUPERSESSION (refined never overrides incumbent
until forward evidence; incumbents byte-identical unless intentionally touched). Rolls never a move.
NG!=WTI. No emojis. Return a concise per-event summary + the block finding.
