# Adaptive locality implementation status — isolated branch

> **Current continuation handoff:** [ADAPTIVE_LOCALITY_COUPLING_GEOMETRY_HANDOFF_20261108.md](ADAPTIVE_LOCALITY_COUPLING_GEOMETRY_HANDOFF_20261108.md). It supersedes older coupling-status text below. Code HEAD validated at `ec0e8561d1a4a57e782b8c54e02add1bd28c84d4`; isolated GitHub Actions `42457310741` passed **61 tests on Python 3.11, 3.12 and 3.13**. No merge/deployment/production integration authorized.

Branch: `feat/adaptive-locality-engine-20261108`.
Intent: build in isolation; **do not connect to Frankie, AWS, BuildMap runtime, or production**. No merge or deployment authorized.

## Implemented in branch
- Typed event, feature and metric contracts; explicit exclusion of identifier-like metric columns; exact weighted Euclidean distance.
- Real Gaussian localization kernel; stable normalized soft weights; conservative family filtering.
- Finite Cauchy window and cross-window drift diagnostics (no infinite convergence claim).
- Historical-only bounded k-neighbor adaptive bandwidth and hysteresis; low-support abstention.
- Stable exclusion-radius center packing, proposal, retirement and constrained restoration; no scientific job suppression.
- Hash-linked in-memory decision ledger; exact-identity comparison eligibility checks and AB/BA distinction.
- Graph weighted flux residual and optional graph finite-volume explicit stepping with cell volumes and conservation checks; not proof of continuum Neumann correctness.
- No-clobber atomic local checkpoint publication and source/contract-bound verification.
- In-memory backpressured shadow ready-group queue, identity-aware idempotency and snapshot recovery.
- Comparable-scope workload counter structure and always-manual promotion verdict.
- Offline shadow-only JSON CLI and unsigned BuildMap-oriented export; explicit zero eliminated jobs.
- Opt-in standalone HTML scientific viewer and replay probes (`visualization.py`, `review_cli.py`) based on Slayer architectural patterns, no Slayer source code and no native BuildMap integration.
- Four standard-library test files and isolated GitHub Actions workflow for Python 3.11–3.13.

## Standalone extensions (November 8, 2026)
- `contracts.py`: explicit source/schema/version/unit calibration, historical-only reference and missingness refusal.
- `index.py`: deterministic grid with exact metric recheck and high-dimension fallback. `disk_index.py`: source-bound persistent streaming grid candidate lookup with exact verification and reversible retire/restore.
- `durable_queue.py`: local SQLite transactional shadow scheduler with capacity/backpressure, expiring and fenced lease tokens, retry and idempotent completion. No external execution or distributed effect safety.
- `result_cache.py`: immutable fully keyed offline research artifacts with torn/stale rejection; no automatic reuse to suppress science.
- `boundary_validation.py`: graph-domain stability bound, energy and conservation tests, not continuum Neumann applicability.
- `grouping.py`: chronological same-family, same-direction reversible display-only grouping and alias ledger. Does not average, flatten or remove observations.
- `outliers.py`: transactional full-original event and lineage retention, investigation statuses, hash-linked audit history. Outliers may be set aside **only from grouping**, never removed from scientific evidence or work. They are research subjects, not noise by default.
- `benchmark.py`: bounded reproducible synthetic-only exact-differential and CPU comparison harness, not real market evidence.
- New independent index/queue/recovery/numeric/outlier/benchmark tests in `tests/test_adaptive_locality_independent.py`, `tests/test_adaptive_locality_numeric_disk.py` and `tests/test_adaptive_locality_review_policy.py`.
- CI success at `d23b6bd8715982257369f4d9f2ef45e4702b8472`, Python 3.11, 3.12 and 3.13, following corrected display-alias-chain test. No production validation.
- Expanded truthful gate report: `docs/ADAPTIVE_LOCALITY_STANDALONE_ACCEPTANCE_20261108.md`.

## Not complete; keep isolated
- Production feature extraction from Frankie's actual 99-plane schema, immutable order/event lineage and frozen normalization.
- High-scale ANN, incremental center evolution and real center split/merge with scientific preservation.
- Full mathematical convergence guarantees: impossible to infer from finite samples without assumptions.
- Real geometric boundary normals, validated flux PDE model, discretization consistency and robust time-step stability.
- Real calculation exactness proof, side-effect checks, cache/FFT equivalence and permitted approximation policies.
- Local transactional SQLite shadow queue now exists; distributed side-effect fencing, multi-host recovery and cloud deployment do not.
- Optional native BuildMap import remains unimplemented. Existing offline viewer is a BuildMap-adjacent prototype, not wired to the app. Signed source-bound collector and production evidence review also remain pending.
- Real-day benchmark, performance/accuracy results, cost gates, randomized multi-day validation and rollout.
- Broader independent bounded differential and fault/reopen tests exist; exhaustive adversarial load, actual-market benchmark, signed evidence, external review and release acceptance remain unsupported.

## Next independent engineering steps
1. Expand deterministic property tests (metric/packing, chunk/replay, NaN/missing, long drift and adversarial identities).
2. Implement source-agnostic domain contracts, calibration and versioned evidence manifests; abstain on missing data.
3. Add safe deterministic incremental index and immutable group lineage/split/merge proposals.
4. Add durable on-disk queue with transactional leases, expiry/retry and fault-injection tests, still disconnected.
5. Add PDE benchmark harness, stability checks and error bounds.
6. Build mock adapter protocol and contract tests with no real imports or live service calls.
7. Add performance harness and reporting with synthetic *tests only*, never as market validation.
8. Verify all CI/test receipts and audit unsupported areas before any request for integration.

No change to Frankie, Search, AWS, production calculations, 30-day ingestion or BuildMap runtime. This document is a truthful status ledger, not a completion receipt.

## Cross-repository research pending
The user recalled a novel five-step coupling technique in `DavisAI1974/Basic_equations`. This is a research lead, not yet confirmed as a particular five-step contract. Review and independent comparison are required before borrowing a coupling method; do not import scientific findings or assume they prove Adaptive Locality equivalence.

## November 8 — five-step coupling, Level 2 and algebraic geometry extension

- Verified source: `DavisAI1974/Basic_equations/level2_four_sciences.py`, `static_dipole_test.py` and `three_discoveries.py`. The original six-node chain and `B_net` averaging are hardcoded artifacts **not** used to derive network edges here.
- `information.py`: frozen-bin H/MI, labeled Fisher-like *proxy*, complete source identity and missing/out-of-range review. Actual parameter Fisher information is unsupported.
- `coupling.py`: directional five-step operator-dynamics experiment; independent full vs self-only vs **past-only lagged** donor null; rank/denominator abstentions retained, not filtered away.
- `level2_coupling.py`: data-derived directional pair-balance candidates; every window including missing/rank-deficient results kept for research, no pair mean. `research_holds.py`: persistent SQLite immutable archive with hash-linked cases and reload tests.
- `geometry_probe.py`: isolated algebraic operator-space curve `Ha^2=a+b*HaHb+c*(HaHb)^2`, plus `-(Ha-Hb)^2=-Ha^2-Hb^2+2HaHb` identity. The algebraic identity is not evidence of coupling. Detect novel train-support outliers even when curve residual is zero; preserve every point and label research-only.
- All current modules are **experimental**, do not eliminate scientific jobs or modify raw market evidence, and have no Frankie, AWS, live BuildMap or external service integration.
- At code commit `ec0e8561d1a4a57e782b8c54e02add1bd28c84d4`, CI `42457310741` passed 61 synthetic/offline tests on Python 3.11, 3.12, 3.13. This is NOT independent scientific acceptance.
- **Still unverified:** scientific causality, real scientific job equivalence, signed source data, 99 planes, full raw-archive handoff for InfoFrames, topology discovery under confounders, real Fisher information, physical geometry/normal vectors, continuum Neumann PDE, and real-data scaling. Continue diagnostic work in the new chat, not integration.
