# NEXT CHAT HANDOFF — Adaptive Locality mathematical engine and optional offline reviewer

> **Current continuation handoff:** [ADAPTIVE_LOCALITY_COUPLING_GEOMETRY_HANDOFF_20261108.md](ADAPTIVE_LOCALITY_COUPLING_GEOMETRY_HANDOFF_20261108.md). It supersedes older coupling-status text below. Code HEAD validated at `ec0e8561d1a4a57e782b8c54e02add1bd28c84d4`; isolated GitHub Actions `42457310741` passed **61 tests on Python 3.11, 3.12 and 3.13**. No merge/deployment/production integration authorized.

Date: Sunday, November 8, 2026 (US Eastern)
Repository: `DavisAI1974/BuildMap` (this is the accessible GitHub storage repository, not a runtime dependency)
**Working branch**: `feat/adaptive-locality-engine-20261108`
**Draft PR**: https://github.com/DavisAI1974/BuildMap/pull/4
**Planning-only PR**: https://github.com/DavisAI1974/BuildMap/pull/3
**Architecture**: `docs/ADAPTIVE_LOCALITY_ARCHITECTURE_BUILD_PLAN_20261108.md`
**Status ledger**: `docs/ADAPTIVE_LOCALITY_IMPLEMENTATION_STATUS_20261108.md`
**Slayer review**: `docs/SLAYER_RENDERING_REVIEW_20261108.md`

## User intent, priority and constraints

User: **finish the entire standalone implementation before connecting anything**. User asked about optional BuildMap visualization, agreed to try it, supplied the public rendering project https://github.com/janearc/slayer, and then requested a committed/pushed handoff and new chat because the prior chat had slowed.

Stay on the existing **separate** branch, preserving all newer changes. Do NOT merge PR #4, merge main, modify Frankie/AWS/Search/30-day ingestion, run production scientific jobs, delete checkpoints/data, connect the new library into BuildMap runtime, or deploy. Do not present successful unit tests as proof of scientific correctness. No scientific calculation may be eliminated solely because of proximity or similar visual grouping. CPU first; no GPU addition merely because Slayer has a Metal path. Keep scientific event identities, original orders, member links, causal/directional clocks, family types, and original evidence intact. Budget and no-silent-drop principles remain.

The standalone mathematical package intentionally lives in BuildMap's repository only because that is the available GitHub repo. **It does not depend on BuildMap or Frankie at runtime.**

## What is implemented and committed

Python standard-library package `adaptive_locality/`:
- `core.py`: immutable typed observations, frozen weighted metric contract, finite Cauchy diagnostic, real Gaussian localization, family-aware candidates, conservative admission, graph flux residual.
- `advanced.py`: historical-only adaptive neighborhood, k-neighbor bandwidth with hysteresis and low-support abstention, stable packing centers with retirement/restoration, window drift, normalized kernel weights.
- `ledger.py`: hash-linked decisions, fail-closed scientific receipt comparison; AB/BA orientation preserved.
- `checkpoints.py`: local no-clobber atomic checkpoint publish, source/contract identity and checksum validation.
- `graph_boundary.py`: optional graph finite-volume flux-step research component, not a physically validated continuum Neumann BC.
- `queue.py`: bounded identity-aware **in-memory** shadow queue with backpressure and snapshot recovery; NOT transactional production scheduling.
- `experiments.py`: comparable workload counters and conservative no-auto-promotion verdict.
- `adapters.py`: strict shadow-only decision/evidence exports with **zero eliminated jobs** and no production side effects.
- `cli.py`: offline shadow JSON command.
- `visualization.py`: source-bound scientific raw frame, deterministic display-only sampling, finite family diagnostic, independent offline HTML plot, deterministic replay probes. Does not edit or drop science.
- `review_cli.py`: explicit opt-in command that produces local HTML and optional probe JSON from local input. No service calls, no overwrite.
- `__init__.py` and `README.md`.
- Tests: `tests/test_adaptive_locality.py`, `tests/test_adaptive_locality_advanced.py`, `tests/test_adaptive_locality_graph_queue.py`, `tests/test_adaptive_locality_visualization.py`.
- CI: `.github/workflows/adaptive-locality.yml` runs unit tests across Python 3.11, 3.12 and 3.13.

## Slayer review and decision

Public repository inspected via connected GitHub: https://github.com/janearc/slayer.
Read `README.md`, `OPERATION.md`, `PACKAGES.md`, `doc/fast.md`, `burning-trousers/README.md`, `LICENSE.txt`, selected `render/smokecache` and `render/frame` code. Slayer is a pre-release Go ray tracer/photographic toolkit with optional macOS Metal path; Apache License 2.0.

**Borrow architecture, not the renderer**:
- Separate raw scientific state from display styling, analogous to raw linear-light frame versus color development.
- Reproducible display probes and full source/metric identity (inspired by its Fermat pixel replay).
- Source/input-aware exact cache keys and atomic complete artifacts; a full cached scientific execution path is NOT implemented here.
- Independent mathematical tests and regression comparisons, rather than validating algorithm by its own output.
- Task-grouping wavefront concepts may inspire a future batch scheduler, but must not replace market-event causality.

No Slayer source code was copied or vendored. We intentionally did not import the Go ray tracer or Metal code. The BuildMap-adjacent viewer is **a separate offline prototype**, not part of `public/app.js` or BuildMap's live Guide.

## How to run safe local checks

From a checkout of the branch (not Frankie source):
```bash
python -m unittest discover -s tests -p 'test_adaptive_locality*.py' -v
python -m compileall -q adaptive_locality
python -m adaptive_locality.review_cli my-shadow-input.json \
  --x spread --y pressure \
  --output locality-review.html \
  --probes locality-probes.json
```
Example JSON layout is in `adaptive_locality/README.md`. `spread` and `pressure` must both be actual metric feature names in the input; choose different names to match a given input. The reports are intentionally unsigned and not production evidence.

## Verification state

At visualization test commit `65e67d9267cb63cabd29eea299b307d6bff7ea1f`, GitHub Actions workflow run `42454412744` reported **success** on Python 3.11, 3.12, 3.13 for isolated syntax/unit tests. Later documentation-only commits updated the source review/status/handoff; recheck current HEAD and newest CI before any completion claim. CI has **not** validated real Frankie data, a native BuildMap browser integration or full science equivalence.

No scientific production job ran; no AWS boxes were started; no data was changed, no PR merged or service connected.

## November 8 continuation and preservation directive

Current verified working commit for this handoff: `d23b6bd8715982257369f4d9f2ef45e4702b8472` (recheck before further edits). Three incremental engineering commits introduced `index.py`, `contracts.py`, `boundary_validation.py`, `durable_queue.py`, `result_cache.py`, `disk_index.py`, `grouping.py`, `outliers.py` and `benchmark.py`; three new test modules and the accurate `docs/ADAPTIVE_LOCALITY_STANDALONE_ACCEPTANCE_20261108.md` ledger. CI for this HEAD passed on all three Python versions.

CRITICAL USER CHANGE: do not discard outlying data points. Investigate them, and optionally set them aside only from a *shadow grouping decision*, not from original evidence, work, or calculations. Retain exact observations and all metadata, causal clocks, order/member IDs, direction and provenance. Never average, smooth, flatten or use a center as a substitute for individual events. The SQLite outlier registry retains original events and an investigation audit trail, with recoverable state.

User also asked about a novel 'five-step coupling technique' from `DavisAI1974/Basic_equations`. Its source should be examined **after** current standalone work; it is NOT automatically relevant or proved, and no coupling adapter is authorized. The source repo was located; its notes discuss coupling, KBK / AI Poincare / SINDy / PySR layering and important negative/corrected results, but the specific five-step procedure is not yet identified.

## Open work: finish independently BEFORE discussing integration

1. Full metric calibration contract (source/data/version identities, units, missing features/abstention, no lookahead, dimensionality/validity checks), correct handling for near-zero distances, precision and stability.
2. Scalable dynamic metric index/packing with bounded-memory online insertion, deterministic partitioning, center version evolution, safe split/merge ledger and explicit causality/family policies. The current O(number_of_centers) scan is a research baseline, not large-scale execution.
3. Durable transactional queue with atomic leases/retries/crash recovery, read-after-write validation, multiple workers and bounded memory; keep **local/offline** and use fake workers first.
4. Distinguish identity hashes from proof of exact scientific equivalence, validate no side effects and scientific admissibility, preserve AB/BA and important directionality, and require explicit approximation policy.
5. Formal graph PDE geometry/flux/boundary condition applicability, stability and conservation/consistency convergence tests. If the PDE/flux model is unjustified, leave Neumann disabled rather than using an inaccurate label.
6. Fully source/contract-keyed raw-frame/result caches with explicit refusals on incompatible source or inputs. Preserve independent tests and correct no-clobber/torn-state behavior.
7. Broader property-based/differential/fault-injection/performance tests, deterministic replay across chunks, randomized event order subject to causal rules, stress bounds. No dishonest scientific receipts.
8. Optional **read-only** BuildMap import design after standalone engine is complete; DO NOT wire it yet. A real native UI integration would require source-bound/staleness validation and scope-controlled release acceptance.
9. Final standalone package docs, release guide, architecture decision records, build/test instructions, precise acceptance ledger, summary of unsupported behavior.
10. Real Frankie integration requires separate authorization and private source access. Previous GitHub access exposed BuildMap, not Frankie's private implementation. Do not invent integration signatures or imply it is done.

## First actions in new chat

1. `@GitHub`: Recheck PR #4 HEAD, latest CI and current files. Preserve newer changes rather than resetting.
2. Continue **standalone** P0–P9 work as feasible; do not ask for approval at every step or repeat already verified tests unnecessarily.
3. Add/fix mathematical, durable scheduler, index and test modules in small source-bound commits; leave production connections untouched.
4. Keep draft PR open and branch isolated. Update this handoff + status doc after each substantial increment.
5. When actually finished, report a complete measured acceptance matrix and remaining limits. Never claim infinite Cauchy convergence from finite data.

**No new AWS work, no change to Frankie or Search, and no production merge.**

## Updated follow-up

The five-step source has **now been found and inspected**; standalone coupling, Level 2, durable research holds and algebraic geometry diagnostics have been implemented and CI-tested. The authoritative, detailed continuation is [ADAPTIVE_LOCALITY_COUPLING_GEOMETRY_HANDOFF_20261108.md](ADAPTIVE_LOCALITY_COUPLING_GEOMETRY_HANDOFF_20261108.md). Earlier statement that the five-step procedure was unidentified is superseded. Finish the geometry diagnostics in the next chat, preserve research holds and all originals, and do not connect or merge.
