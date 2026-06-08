## Note (Session 24 update — 2026-06-08) — MARKETS: dipole gate FAILS at full scale; root cause = off-BUILD_PLAN basis; reoriented

S24 ran the S24-kickoff #1 (the 15-source chem-dipole validation) to completion, read the numbers, and
reoriented the whole thread back onto `BUILD_PLAN.md` (the WRITTEN-IN-STONE OD / PySR-Julia rebuild plan,
commit `da9dc63` on this branch). Follow it to a T; any deviation cleared with Greg first.

**Result (full scale):** POOLED 16,003 trades (13.1% win). The in-sample control + embargoed walk-forward
gate FAIL in all three modes — `none`/`pool` degenerate to the `H_a==-H_b` tautology (r2=1, c=0), `scale`
is linear (c=-0.0006, r2_lin=0.998); WF net -15 to -26, hit <=40%, z<=0.5. The reference convex
c=1.309/R^2=0.943 reproduced in NO mode. No net-of-cost edge; the gate correctly rejects.

**Root cause (diagnosed, sources kept SEPARATE per Greg):** the collapse is a property of the 15-dim
hand-built c_i, not of the validation. It is collinear (participation-ratio eff-rank 7.82/15) and
non-discriminative (best feature Cohen d=0.19; multivariate AUC 0.574 random / 0.513 time-ordered = no OOS
signal). Per source, NO source reproduces convex c>0.

**The reorientation:** against `BUILD_PLAN.md` the S22-S24 dipole port deviated three ways — (1) WRONG
BASIS: a 15-dim hand-built coupling vector instead of the plan's ORIGINAL 128-dim `operator_coefficients`;
(2) HARDCODED a fixed quadratic instead of PySR-DISCOVERING the form; (3) POOLED all sources instead of
per-pair. The S20 blocker is now partly resolved — the originals (`_markets_algebraic_dipole.py` etc.) are
ON DISK at `E:\Markets`; reading the core confirms H_a/H_b are centroid projections of RAW 128-dim
`operator_coefficients` per pair (read from `E:\refrag\discoveries\operator_discoveries\`). The richer
labeled set `_full_pipeline_winners_preentry_cs100_v2\summary.json` (1,054 x ~128-dim) is the "where it
worked" reproduction target. Tier-3 originals (s12/s13/od_per_domain) still missing.

**Toolchain:** PySR 1.5.10 installed but NOT loading (import hangs on Julia precompile; `julia` not on
PATH). S25's FIRST action is to make the SessionStart PySR/Julia bootstrap actually load before any
discovery.

**Plan hygiene:** `MARKETS_OFFENSIVE_LAYER_PLAN.md` is a SEPARATE older defensive plan, NOT this; identify
the plan by the PySR/Julia/5-step test. Memory: [[markets-canonical-plan]], [[follow-canonical-plan-rule]].
Full detail `SESSION_HANDOFF_2026-06-08_S24.md`; next steps `KICKOFF_2026-06-09_S25.md`.
