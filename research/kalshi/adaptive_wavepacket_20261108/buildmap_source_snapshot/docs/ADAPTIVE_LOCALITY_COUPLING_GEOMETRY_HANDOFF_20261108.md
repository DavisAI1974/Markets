# ADAPTIVE LOCALITY — FINAL NEW-CHAT HANDOFF: COUPLING & GEOMETRY DIAGNOSTICS

Date: 2026-11-08 (US Eastern)
Repository: `DavisAI1974/BuildMap` — storage-only for standalone Python package
Working branch: `feat/adaptive-locality-engine-20261108`
Draft PR: https://github.com/DavisAI1974/BuildMap/pull/4
Code checkpoint at handoff preparation: `ec0e8561d1a4a57e782b8c54e02add1bd28c84d4`
Latest successful code CI: GitHub Actions `42457310741`, isolated suite **61 tests**, Python 3.11/3.12/3.13 all green.
**Re-read actual HEAD, PR, CI and newer commits in new chat.** This handoff document will add a documentation-only commit, so HEAD will advance again.

## User intent

Continue the standalone Adaptive Locality mathematical engine until independently ready. Keep ALL work on the separate branch. Do not connect to Frankie, AWS, Search, 30-day ingestion, or live BuildMap; do not merge, deploy, start machines, alter production, or eliminate scientific calculations. Continue without asking permission for every step, but respect explicit integration authorization.

**Critical preservation rule:** Outliers and any rank-deficient, unexpected, conflicting, low-support, non-finite, underidentified, or otherwise unsupported scientific cases are set aside **FOR RESEARCH ONLY**, never silently discarded. Preserve original values, event/order/member IDs, family, direction (AB/BA), clocks, causality, complete source evidence and interpretation, even if short-lived. NEVER average/flatten original events, smooth them to explain away anomalies, replace them with a cluster representative, or use grouping to suppress scientific calculations. Keep a recoverable audit record of every abstention and original source.

Latest user request: finish the current coding, **commit/push everything to GitHub**, print the new-chat drop-in. Because this chat is slow, do remaining geometry diagnostics in the new chat.

## Baseline modules and standalone work previously completed

Earlier branch state: `adaptive_locality/core.py`, `advanced.py`, `ledger.py`, `queue.py`, `checkpoints.py`, `graph_boundary.py`, `experiments.py`, shadow `adapters.py`, `visualization.py`, `cli.py`, `review_cli.py`, tests, and dedicated `.github/workflows/adaptive-locality.yml`.

Earlier standalone increments added:
- `contracts.py`: source/schema/version/unit-frozen metric and cutoff checks.
- `index.py`: accelerated grid candidates with exact distance verification and honest high-dimensional fallback.
- `disk_index.py`: SQLite exact-verified disk-based center index.
- `durable_queue.py`: local SQLite shadow leases, retries, capacity and idempotency; no external execution.
- `result_cache.py`: no-clobber fully keyed offline cache, never permission to eliminate science.
- `boundary_validation.py`: discrete graph mass/energy and stability diagnostics, **not** continuum Neumann proof.
- `grouping.py`: chronological, family- and direction-specific shadow assignments and reversible display aliases.
- `outliers.py`: original event archive, explicit investigation status, audit history, no smoothing or dropping.
- `benchmark.py`: synthetic CPU-only reference comparison.
- Independent tests for these modules and the standalone acceptance ledger.

## Newly implemented in THIS continuation

### Basic Equations five-step reconstruction (SOURCE INSPECTED)
Read `DavisAI1974/Basic_equations/level2_four_sciences.py` and `per_domain_kbk.py`, as well as context in `CLAUDE.md`, `static_dipole_test.py`, `three_discoveries.py`.
The original five steps: (1) H/MI/FI-like observables, (2) operator library with `Ha, Hb, MI, Ha^2, Hb^2, Ha*Hb`, (3) least-squares `dH/dt = library @ coefficients`, (4) per-science independent analysis, (5) compare surviving operator relationships. Level 2 builds the sliding-window ratio `B_ij=|c_(Hi^2)|/|c_(Hi*Hj)|` and analyzes links among balance series.

Original `level2_four_sciences.py` hardcodes six nearest-neighbor subsystems per science and computes all predefined pairs. Its `B_net` is the mean of other pair balances. Those are **not data-discovered topology** and can hide distinct patterns. Its tiny-denominator ratio is ill-conditioned; use a research hold instead of an arbitrary epsilon pretending a real ratio.

### Isolated modules and tests built and pushed

- `adaptive_locality/information.py`: exact original RawMember/RawFrame identities, frozen-bin H and MI, explicitly labeled **Fisher-like roughness proxy** (NOT actual parameter Fisher information), strict aligned members and out-of-range review, no clipping or imputation. `tests/test_adaptive_locality_coupling.py`.
- `adaptive_locality/coupling.py`: source-bound chronological Level 1 *directional* five-step operator test with independent full vs self-only baseline vs past-lagged donor null. Reorthogonalized QR rank screening, downstream exact operator coefficients, pairwise holdout, no fixed adjacency, zero suppressed jobs, ratio abstention. **Important bug fixed:** original prototype's shifted donor used a circular future wrap; now donor null uses PAST-only lookback, matched train/test indices. Four-science comparison explicitly REFUSES non-independent duplicated source evidence.
- `adaptive_locality/level2_coupling.py`: retains **all original Level 1 balance windows**, each pair separately, all candidate directed links, rank and outlier review holds; no `B_net` average, no hardcoded chain. `tests/test_adaptive_locality_level2_coupling.py`.
- `adaptive_locality/research_holds.py`: source-bound SQLite original-evidence archival with transaction, digest checks, immutable cases, repeatable reload, hash-linked review history, `preserve_level2_holds` and `preserve_five_step_holds`. Research states do not erase evidence. Tests: `tests/test_adaptive_locality_research_holds.py`. **Caveat:** archived Level 1 `InfoFrame` contains original raw identities, not the full upstream RawFrame measurements; complete raw archives must be provided separately before any real science.
- `adaptive_locality/geometry_probe.py`: purely **operator-space geometric diagnostics** inspired by Basic Equations' `static_dipole_test.py` and `three_discoveries.py`. It analyzes `Ha^2 = a + b*(HaHb)+c*(HaHb)^2` with training/holdout, returns every unchanged source-frame identity and per-point diagnostic. It also exposes the algebraic identity `-Ha^2-Hb^2+2HaHb=-(Ha-Hb)^2`. **This identity is NOT a discovered coupling law**: it holds algebraically, including for unconnected equal-entropy noise. No continuum Neumann boundary or other physical geometry is established. Its novel-outlier check flags extrapolation far beyond frozen train support even when quadratic residual is zero. Nothing is removed from the fit, result or source. Tests: `tests/test_adaptive_locality_geometry.py`.
- New tests cover synthetic known-coupling vs independent cases, rank defects, source identity, chronological donor lookahead, corrupted original archives, disk persistence, missing windows, novel geometric outliers, and model-exact outliers.

### CI and specific correction sequence

At `9a8a907616c54e8d40d24260aa2633273529e139`, the new geometry test exposed an **actual diagnostic gap**: a large outlier can lie exactly on the fitted static quadratic, so residual-only screening misses it. Repaired in `3900a5b3cba3dbe94531787731080972471d1e2f` using frozen train-support novelty alongside residual. That commit exposed Python variable shadowing (`reason` overwritten inside per-point loop) in the equal-entropy test, repaired in `ec0e8561d1a4a57e782b8c54e02add1bd28c84d4`. Its isolated CI run `42457310741` completed successfully on all 3 Python versions (61 tests). Preserve those receipts; do not rerun broad suites without source changes.

## Key mathematical cautions before next diagnostics

1. `(-1,-1,+2)/sqrt(6)` in the `(Ha^2,Hb^2,HaHb)` plane represents `-(Ha-Hb)^2`, often an equal-entropy / rank-basis artifact, not a sufficient coupling condition. Previous Basic Equations' interpretation was explicitly corrected in later research.
2. The static polynomial relation is an observable-data *fit*, not a physical spatial geometry, not a Neumann boundary, and not proof that two event groups can merge. Its coefficients can be estimator-, window-, regime- and source-dependent.
3. Rank-deficient and zero-denominator cases are **research findings**, not records to drop. Include them in denominators/counters, audit and revisit with independent features or better-conditioned estimation.
4. Keep distinct links, direction, family, causal clocks, and original rows; NO `B_net` mean, silent flattening, surrogate averaging, shared-family conflation, data loss or calculation elimination.
5. A held-out predictive gain and past-lag null suggest a **candidate association** only, not causation or scientific equivalence. Check common drivers, multiplicity, stationarity, negative controls, reparameterization and independent source/calibration.
6. Real Fisher Information needs a defined parameter, likelihood and estimator; `information.py` deliberately implements only a binned discrete density-roughness proxy, not claiming FI.
7. A finite-window Cauchy diagnostic cannot prove infinite convergence. Dynamic geometry is not a validated continuum PDE domain.
8. No real market or Frankie private-source integration has been tested, and no legitimate scientific calculations have been eliminated. CI success is bounded synthetic unit validation.

## Next chat: priorities (do NOT merge or connect)

1. Recheck current branch HEAD, PR #4 and latest CI. Preserve all newer work, inspect the above five modules and tests and this handoff.
2. **Continue geometric dipole diagnostics first:** compare equal-entropy/noise null vs genuine predictive interaction; quantify model residual vs frozen training-support novelty separately, inspect rank/conditioning and origin of geometric artifacts; add negative controls, seed/change-point/causal-lag robustness. No need to repeat passed CI for unchanged code.
3. Wire **offline diagnostic-to-ResearchHoldRegistry archival only** for `geometry_probe.py` (no production wiring). Make all rejected/abstaining geometry inputs including original upstream RawFrame payloads recoverable; verify re-open and checksum, avoid ambiguous identity of supplied synthetic InfoFrames.
4. Harden Level 1/Level 2 no-lookahead and independent domain claims; compare against original Basic Equations as a baseline but do not copy hardcoded topology or average pair network.
5. Decide whether any geometry-aware index metric is warranted only after independent tests; no causal merge, scientific dedupe, job suppression or physical Neumann claims.
6. Update docs/acceptance matrix honestly; keep all work in draft PR #4 on isolated branch. Never merge/deploy/connect until a separate explicit authorization.

Standalone commands:
```sh
python -m compileall -q adaptive_locality
python -m unittest discover -s tests -p 'test_adaptive_locality*.py' -v
python -m adaptive_locality.benchmark
```

Acceptance: **61 isolated tests green at code commit**, not scientific production acceptance. Standalone engine remains in development. Continue diagnostics and finish independent verification in a fresh chat.
