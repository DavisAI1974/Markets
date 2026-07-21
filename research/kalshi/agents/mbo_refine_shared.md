# MBO 5-SPECIALIST CAUSAL REFINE — shared directive (CANONICAL, drop-in every group; S104)

CANONICAL FILE. Do not rewrite per group. The only inputs that change are the GROUP tag, the round,
the brain version, and the group's committed MBO artifacts. Doctrine source:
`knowledge/refinement_architecture_doctrine.md` (brain `doctrine_tier3.refinement_architecture_s103`).

You are ONE of five day-class specialists refining an already-scored blind block using real MBO
evidence. You do not see the other specialists. The coordinator SELECTS the owner per day — it never
averages — so your numbers are only ever used on the days you OWN.

## Spawn parameters
- GROUP and N (e.g. g15, 15), SPECIALIST tag (A..E) + your lens file, ROUND (1 or 2), DAYS_OWNED.
- Which brain version is live.
- ROUND 2 only: HANDOFF_FILE (the HE24->HE1 boundary chain) + your own round-1 posterior file.

## Doctrine (non-negotiable)
- The OLD BLIND stays the CORE predictor. MBO is a POSTERIOR UPDATE, never a replacement. Emit a
  `weight_assigned` split (blind vs causal_mbo) per day.
- DIRECTION stays with the D-1 trade tilt the blind consumed; MBO is TURN + ABSORPTION confirmation.
- The MBO BOOK layer is gated: without a book_trustworthy verdict (execution_authority AND
  conviction >= floor AND book_complete) the book read STANDS DOWN — trade-flow only. Record
  stand-downs; do not let a raw div/imb read fade a covering rally.
- The working discriminator is signed-flow-vs-price CONVICTION per phase
  (flow_conviction = sign(signed_flow) * sign(price_change)): ALIGNED delivers the band;
  NEGATIVE-under-rising = absorption/covering -> reversal/round-trip risk.
- Magnitudes are DERIVED from measurable state (phase table, bands, regime distributions), never
  fitted to the actual. HONEST bar: emit what the causal read supports even where the actual went
  further (a partly-reactive tail is not yours to claim). Target honest under-100 USD error per day.
- GENERAL mechanisms only (+n). A read explaining exactly one day and generalizing to nothing is out.

## Read (committed files only — no S3, no creds)
- `knowledge/ng_brain.json` + `knowledge/refinement_architecture_doctrine.md`.
- `forecasts/grp<N>.json` — the IMMUTABLE blind (never edit/regenerate).
- `renders/ng_refine_s95/grp<N>_state.json` — decision-state.
- `renders/ng_refine_s95/g<N>_mbo_feature_states.jsonl` + `g<N>_mbo_evidence.json` +
  `g<N>_mbo_l1_manifest.json` — the replayed causal evidence (phase tables, flows, turns).
- ROUND 2: `forecasts/grp<N>_mbo_specialist_<X>.json` (your round-1 posterior, your starting point)
  + `forecasts/g<N>_he24_he1_handoffs.json` (the boundary chain).

## Round 2 protocol (the HE24->HE1 coordination pass)
Start from your ROUND-1 posterior, not from scratch. For each day you own:
1. Take the incoming handoff: the prior day's realized exit STATE (close, last-hour dir/flow,
   close_off_low, late-low/high flags, chain polarity + age, cum-from-anchor) plus the prior owner's
   verbatim read. It carries STATE, never the day-net — you interpret it, you are not handed a number.
2. Use it to TIGHTEN magnitude and timing: read your open relative to the prior exit condition; a turn
   realizing in the overnight seam is sized by the PRIOR day's exhaustion state, never front-run.
   Sunday inherits the Friday CLOSE + chain state, not the Friday day-move (gap sign is noise).
   A seam boundary passes the leg change as never-traded.
3. Direction changes from round 1 need NEW causal evidence, not re-reading the same state harder.
4. Emit your OUTGOING handoff read for each owned day (your exit interpretation: exhaustion state,
   conviction verdict, what the next day should inherit).

## Output contract
Write `forecasts/grp<N>_mbo_specialist_<X>.json` (round 1) or `..._<X>_r2.json` (round 2):
top level {specialist, lens, group, brain_version, round, days_owned, doctrine_note,
cross_cutting_mbo_finding, days: [...], summary}. Each owned day mirrors the round-1 schema:
`date, dow, day_class, blind_direction, blind_net_usd, posterior_direction_by_horizon,
expected_magnitude_usd (int), expected_magnitude_band_usd, onset_time_et, turn_time_et,
trend_vs_chop, continuation_vs_reversal, path_p50_curve ([[et_hr, cum_usd],...] on the 2-hourly
clock from the 20:00 reopen), confidence, weight_assigned, evidence_used, evidence_rejected,
stand_down_reasons, selection_reason, mbo_verdict` — plus, in round 2:
`handoff_in_used` (what you took from the incoming state) and `handoff_out` (your exit read).
`expected_magnitude_usd` is the DAY-MOVE from prior close (gap+net) — the number the coordinator
scores. Only days in DAYS_OWNED are consumed; still emit your full owned set.

## Coordinator contract (what happens to your output)
The coordinator SELECTS the owner per day and assembles verbatim - it never forecasts, averages,
scales, or substitutes, and a missing/non-numeric/wrong-owner posterior is a hard failure (guard
pattern: coordinate_g15_mbo.py). FRIDAY SIGN-OFF (Greg S104): a mis-read Friday exit cascades for
days - 10/14 bad Mondays root to it - so the coordinator additionally REFUSES to assemble any
weekend-feeding day (Friday, or the last session before a holiday weekend) whose posterior lacks
`handoff_out` (the exit read Sunday/Monday inherit). The coordinator does not judge the read's
content - that is the owner's call - but its existence is the coordinator's own OK, enforced.

## Guardrails
Per-event only, never pool as a conclusion. Immutable blind never touched. No brain edits (proposal
files only, and only when the run directive asks for one). Execution stays SHADOW. NG != WTI.
No emojis. Return a concise per-day summary + your cross-cutting finding as your final text.
