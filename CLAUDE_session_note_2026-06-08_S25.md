## Note (Session 25 update — 2026-06-08) — MARKETS: PySR/Julia toolchain FIXED; dipole VALIDATED real on the 128-dim per-pair basis

S25 cleared the S24 toolchain blocker and executed kickoff §0–§2 of `BUILD_PLAN.md` on the RIGHT basis. The
markets algebraic dipole is REAL per pair on the original 128-dim `operator_coefficients` — categorically unlike
the S24 collapse (an artifact of the off-plan 15-dim POOLED basis). Full detail
`SESSION_HANDOFF_2026-06-08_S25.md`; next `KICKOFF_2026-06-09_S26.md`. Folded into `CLAUDE (5).md` (header → S25).

**Toolchain FIXED (durable).** The S24 "PySR hangs" was juliacall/juliapkg's first-run Julia download stalling
on the flaky `julialang-s3` mirror (it resets connections — curl itself died at 22 MB; = SETUP_julia_pysr.md
failure-mode #4). Fix on this LOCAL Windows box: pre-downloaded Julia 1.11.9 via a `curl -C -` resume loop →
`C:\Users\A\.julia\juliabin\julia-1.11.9\`, set user env `PYTHON_JULIAPKG_EXE` so juliapkg skips the broken
download; SymbolicRegression.jl + 95 deps precompiled/cached. VERIFIED: `import pysr` 1.5.10 + Julia 1.11.9, tiny
fit recovers `2x0²+0.5x1` (loss 1e-14), cached import ~12s. [[pysr-julia-local-toolchain]]

**STEP 1 — algebraic dipole reproduces per pair (real 128-dim).** Verbatim `_markets_algebraic_dipole.py` on
`E:\refrag\discoveries\operator_discoveries\<pair>_<win|lose>\*.json`: per-pair R²_quad up to 0.975 (convex +γ),
6/11 ≥ 0.91; POOLED 0.493. Pooling collapses it — per-pair is right.

**HONEST validation (the key result).** `_preentry_cs100` (100 win/100 lose per pair, no look-ahead):
nearest-centroid `Ha−Hb>0` classifier acc 0.947, AUC ~1.0; a 200× label-permutation null collapses to
0.50±0.045 → real-vs-null **z = +6..+11.6 on all 12/12 pairs (mean +9.6, p=0.000)**. The pre-entry separation is
genuine predictive signal, not a D≫N geometric artifact. (Random k-fold pooled = 0.976 = the old ~0.993, which
overstates — BUILD_PLAN signal I; the permutation null is what makes it trustworthy.)
[[dipole-real-on-128dim-per-pair]]

**Why S24 collapsed (Greg, confirmed):** the earlier run mashed all sources together instead of analyzing them
separately — pooling forces the degenerate Hb=−Ha tautology. KEEP PAIRS SEPARATE.

**PySR discovery (kickoff §2).** ops {+,−,*,/,square,cube,exp,log,sqrt}, 3 seeds, target Ha² on x0=Ha·Hb: PySR
reproducibly discovers a convex surface per pair (5/12 identical across 3 seeds) and the crypto data prefers a
CUBIC over the hardcoded quadratic. Promotion gate readout needs fixing (it keyed on the x0² term, mislabeling
cubic pairs "fail").

**Correct construction already in repo:** `odcore/dipole_predictor.py` carries the verbatim 128-dim primitives;
S24's error was `odcore/dipole_trade.py` feeding a 15-dim standardized c_i. Fix = data-path (raw 128-dim per pair).

**Still owed → S26:** walk-forward/non-random split (JSONs lack trade timestamps), net-of-cost PnL, and the
LARGER trade-set run — the 15-source 16–30 day (~16k-trade) set attached from an E-drive folder.
