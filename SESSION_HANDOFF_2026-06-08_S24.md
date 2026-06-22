# SESSION HANDOFF — 2026-06-08 — Session 24 (Markets: dipole gate FAILS at scale; root cause = off-plan basis; reoriented to BUILD_PLAN.md)

WORKING BRANCH: `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets). No PR.
**WRITTEN-IN-STONE GUIDE: `BUILD_PLAN.md`** (commit `da9dc63`, this branch) — the approved OD / PySR-Julia
rebuild plan. Follow it to a T; ANY deviation must be cleared with Greg first (memory
[[follow-canonical-plan-rule]]). All Operating Rules + Result Discipline in force. Zero synthetic data.

## Headline
Finished the S24-kickoff #1 run (the 15-source chem-dipole validation) and read the numbers: the gate
FAILS in all three standardization modes, confirming the S23 collapse at full 16,003-trade scale. The
diagnosis pins the cause to a DEVIATION FROM `BUILD_PLAN.md` — the dipole was fed a 15-dim hand-built c_i
instead of the plan's 128-dim `operator_coefficients`, the quadratic was hardcoded instead of PySR-
discovered, and all sources were pooled instead of kept per-pair. No code shipped; this was a
diagnose-and-reorient session.

## What ran + the result (full 15 sources, pooled, resumable cache)
`python scripts/od_trade_dipole_run.py --leadlag-nnull 10 --sources <all 15>` completed (resumed 5 cached
+ computed 10). POOLED 16,003 trades (win=2,104, 13.1%). In-sample control + embargoed walk-forward gate:
- `none`  : degenerate (H_a==-H_b), r2=1 tautology; WF net=-26.0, hit 32.6%, z=-1.04 -> FAIL x4
- `scale` : a=-0.87 b=+1.05 c=-0.0006, r2_lin=0.998 (linear, no curvature); WF net=-20.8, hit 36.3%, z=-0.13 -> FAIL x4
- `pool`  : degenerate tautology; WF net=-15.2, hit 39.7%, z=+0.51 -> FAIL x4
take-all net=+0.022 (~buy-hold). Reference convex c=1.309/R^2=0.943 reproduced in NO mode. The dipole
predictor LOSES net-of-cost everywhere. (Runner caveat: the Option-2 set includes the dipole generator's
own entries -> already a generous read, and it still fails.)

## Why it collapses (diagnosed; sources KEPT SEPARATE per Greg)
Diagnostics on the cached c_i:
- Centroid geometry explains each mode: `scale` cos(c_win,c_lose)=+0.9981 (centroids nearly identical ->
  H_a~=H_b -> linear); `pool` cos=-1.0000 (mean-centering forces antiparallel -> exact tautology); `none`
  scale-dominated.
- The 15-dim basis is THIN + COLLINEAR: participation-ratio effective rank 7.82/15; mi_frac~chem_residual_frac
  r=0.91, mi_slope~mi_var 0.87, dipole_a~dipole_b 0.86.
- And NON-DISCRIMINATIVE: best single feature Cohen d=0.19 (dipole_r2); multivariate balanced logistic
  AUC 0.574 random-CV but 0.513 time-ordered (= no out-of-sample win/lose signal).
- Per source (15 separate scale-mode fits): NO source reproduces convex c>0 — all c~=0.
CONCLUSION: the collapse is a property of the 15-dim hand-built c_i, NOT of `odcore/validation.py`.

## The reorientation (the real finding)
Read against `BUILD_PLAN.md`, the S22-S24 dipole work deviated three ways:
1. WRONG BASIS. BUILD_PLAN's primary signal (D) projects the ORIGINAL 128-dim `operator_coefficients`
   per trade; S22 substituted a 15-dim hand-built coupling-feature vector + a standardizer. That swap is
   the entire collapse.
2. HARDCODED, not DISCOVERED. BUILD_PLAN says PySR (Julia) DISCOVERS the dipole/coupling form from raw
   operator data (>=3 seeds, <5% coeff var), then validate; we polyfit a fixed quadratic.
3. POOLED, not PER-PAIR. The original `_markets_algebraic_dipole.py` loops per pair; the runner pools all
   sources into one C / centroids / gate.

## S20 blocker now (partly) resolved — the originals are ON DISK
The S20 BUILD_PLAN blocker ("Basic_equations unreachable") no longer fully holds locally:
- PRESENT on `E:\Markets`: `_markets_algebraic_dipole.py`, `_markets_dipole_kfold.py`,
  `_markets_dipole_separation.py`, `_markets_dipole_chunker_stack.py`.
- Read `_markets_algebraic_dipole.py`: H_a/H_b are centroid projections of RAW 128-dim
  `operator_coefficients` read per pair from `E:\refrag\discoveries\operator_discoveries\<pair>_<win|lose>/*.json`
  (12 pairs: btc/eth x bybit/coinbase/kraken x buy/sell), NO standardization, fit per-pair AND pooled.
  Imports only stdlib (argparse/json/math/pathlib) — the entropy/MI/operator work is UPSTREAM, in the
  pipeline that produced those coefficients.
- STILL MISSING (Tier 3): `s12_coupling_decomposition.py`, `s13_chemistry_residual.py`,
  `s12_consolidate_per_domain.py`, `od_per_domain_equations.json`.
- Richer labeled set on disk: `E:\Markets\_full_pipeline_winners_preentry_cs100_v2\summary.json`
  (1,054 results, each with `operator_coefficients_head`) — the ~128-dim "where it worked" reproduction
  target.

## Toolchain status — PySR/Julia NOT loading this session
The SessionStart hook (`.claude/settings.json` -> `scripts/session_start.sh`) bootstraps numpy/scipy/sklearn
+ PySR + Julia and materializes real bins. This session: PySR installed (1.5.10) but `import pysr` HANGS on
first-run Julia precompile and `julia` is not on PATH -> "PySR not importable yet". Discovery (BUILD_PLAN
Phase 1) is blocked until this loads. THIS is why S25 must start by verifying the toolchain.

## Plan clarification (avoid the wrong-plan trap)
`MARKETS_OFFENSIVE_LAYER_PLAN.md` (on branch `run-pass-14-classifier`) is a SEPARATE, OLDER defensive/PnL
plan (wilson+protective, in-flight promotion) and is NOT this work — it never mentions PySR/Julia/5-step.
`BUILD_PLAN.md` is the canonical guide. Identify the plan by Greg's PySR/Julia/5-step test, not filename.
Memory written: [[markets-canonical-plan]], [[follow-canonical-plan-rule]].

## HONEST STATUS (Result Discipline)
No net-of-cost edge. The gate (`odcore/validation.py`) is unmet and correctly rejected a losing signal.
Reproducing the algebraic R^2 is structural, not an edge — and it did not even reproduce on the wrong
basis. WIRE step stays deferred.

## What is NOT done (-> S25, see `KICKOFF_2026-06-09_S25.md`)
- Verify PySR/Julia actually loads (first action).
- Rebuild the dipole on the ORIGINAL 128-dim `operator_coefficients`, per pair (not the 15-dim c_i).
- Reproduce `_markets_algebraic_dipole.py` c~=1.309 on the real coefficients (cs100 / refrag discoveries).
- Then PySR-DISCOVER the form per pair (>=3 seeds, <5%); validate walk-forward + tautology null.
- Obtain the missing Tier-3 files.

## Pointers
- Written-in-stone plan: `BUILD_PLAN.md`
- Next kickoff: `KICKOFF_2026-06-09_S25.md`
- This session's CLAUDE note: `CLAUDE_session_note_2026-06-08_S24.md` (folded into `CLAUDE (5).md`, header -> S24)
- Prior: `SESSION_HANDOFF_2026-06-08_S23.md`, `KICKOFF_2026-06-08_S24.md`

## Branch
WORKING BRANCH: `claude/crypto-trading-platform-plan-MpqwG` (DavisAI1974/Markets)
