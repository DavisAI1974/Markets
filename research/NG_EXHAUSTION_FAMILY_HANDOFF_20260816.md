# NG Exhaustion Family Handoff — 2026-08-16

## Scope

This is scratch research only. Do **not** change Frankie, its permanent workflow, brain, schema, roles, plays, or datapoints.

Scratch branch: `chatgpt/s40-independent-recalc-20260816`

## Current question

Discover NG's own dipole exhaustion geometry first. Do **not** force crypto shapes or prior hypotheses onto NG.

The research order is:

1. Detect dipole events from dipole data only.
2. Build fixed real-time exhaustion curves around the dipole flip/spike (`t=0`).
3. Find repeatable NG pre-flip shape families and verify that similar pre-flip families reproduce similar post-flip exhaustion behavior across independent days.
4. Only **after** the exhaustion families are stable, attach price legs and test any relationship to leg duration. Positive, negative, or no relationship are all acceptable outcomes.

Hypotheses such as "hockey stick = long" are guesses only and must never dictate thresholds, family definitions, or interpretation. Follow the data.

## Historical visual semantics recovered from the crypto work

The old Kraken graphs were fixed-time windows around a flip/spike. The left side was roughly 30–60 seconds before `t=0`; the right side roughly 20–60 seconds after. `t=0` is the dipole flip/spike. The y-axis is dipole mean flow, not price. Old winner/loser labels were wrong for structural analysis and must be ignored.

Price direction does not define exhaustion geometry. Negative dipole polarities may be mirrored by dipole polarity itself so opposite-sign events can share one geometric vocabulary.

## NG-native first pass

Implemented:

- `research/ng_native_dipole_shape_audit.py`
- `.github/workflows/ng_native_shape_audit.yml`

Workflow run:

- Run ID: `31980543522`
- Artifact: `ng-native-dipole-shape-audit`
- Artifact ID: `9272282546`
- Artifact SHA256: `5d8335ded0d324cfec5d50e4290ffe1892166164f66cecafa2f80deb06d276a2`

The run uses four authoritative NG MBP-10 days:

- 2025-07-17
- 2025-09-23
- 2025-09-30
- 2025-10-01

Construction:

- `t=0` detected from dipole only, not from a price-leg start.
- Fixed real-time window: `-60s .. 0 .. +60s`.
- Negative flips mirrored by dipole polarity only.
- 20s and 60s trailing trade-flow imbalance variants were both rendered.
- Price labels exist in the scratch result for later use, but **must not be used yet** for family discovery or validation.

Renders in the artifact:

- `ng_native_shape_families_roll20.png`
- `ng_native_shape_families_roll60.png`

## Current visual finding

The first 20s-flow render shows **three visually distinctive pre-flip families**. Greg specifically noted that the pre-flip portions are much more distinctive than the tails. The tails have some differences/noise, but the family identity appears concentrated on the left side.

Do not claim the three families are final merely because three were rendered. Treat "three" as the current visible candidate family count. Test whether the data supports three or naturally splits further.

Also do not dismiss the first render merely because NG trade-flow can be sparse. Preserve it as evidence. A denser book-imbalance representation may be useful as a challenger, but it must not overwrite the trade-flow result.

## Exact next step

Stay **exhaustion-only**.

1. Quantify the three visible pre-flip families using only `t <= 0` data.
2. Measure their distinguishing geometry without outcome-fitting: baseline level, excursion to spike, build duration, early/mid/late slopes, curvature, and whole-curve similarity.
3. Validate family stability cross-day: fit/derive family prototypes on some days and assign events from held-out days using pre-flip curve only.
4. Check whether held-out members assigned to the same pre-family show tighter post-flip exhaustion curves/durations than members from different pre-families.
5. Compare candidate family counts (at least 2–8) descriptively so the data can indicate whether three is too coarse. Do not choose K using price-leg outcomes.
6. Render the families and show them in chat if they group themselves cleanly.
7. **Stop before any price-leg correlation analysis.** Only after Greg approves the exhaustion-family result should price legs be reintroduced.

## Standing interpretation rule

Hypotheses are disposable. They are useful for curiosity, not for forcing the result. No threshold, cluster count, polarity transform, smoothing choice, or family label may be selected because it improves agreement with a preconceived story.
