# Adaptive Locality — standalone engineering and scientific acceptance ledger

> **Current source-of-truth acceptance amendment:** [ADAPTIVE_LOCALITY_INDEPENDENT_DIAGNOSTICS_20261108.md](ADAPTIVE_LOCALITY_INDEPENDENT_DIAGNOSTICS_20261108.md). This supersedes historical test counts and the older coupling handoff for the new work. At code checkpoint `398e62f0a8b594757fd2e743e3381a98c24a4fa8`, isolated GitHub Actions [42459918493](https://github.com/DavisAI1974/BuildMap/actions/runs/42459918493) passed **87 tests across Python 3.11/3.12/3.13**. The optional BuildMap scratch scanner [42459917897](https://github.com/DavisAI1974/BuildMap/actions/runs/42459917897) passed **1 test** (7 observed static source connections, 8 retained/unverified gates, zero altered source files or suppressed calculations). Documentation updates have advanced HEAD; recheck newer CI. **No merge/deployment/live integration authorized.**

Updated: November 8, 2026. Branch `feat/adaptive-locality-engine-20261108`.
**All components remain research-only and isolated. No Frankie, AWS, Search or BuildMap runtime wiring.**

## November 8 continuation — acceptance distinctions

- **Archive-first standalone review now available.** Save full original RawFrames and derived InfoFrames **before** running static or predictive geometry; every blocked, short, out-of-range, conflicting, rank-deficient, near-singular, unverified or unsupported case becomes a research hold. The source-bound registry checks case/history consistency and enforces SQLite foreign keys; it is **not independently signed**, and pre-RawFrame invalid bytes still need separate importer archival.
- **Scientific models remain exploratory.** Equal-entropy null `-(Ha-Hb)^2` is a universal identity. Constant-donor static quadratic is an algebraic reparameterization, not predictive geometry. Explicit nested linear-interaction vs quadratic predictive gains are checked on future target derivatives; seeded synthetic controls do not constitute independent real-world science.
- **All eight unresolved acceptance gates are retained.** An `UNVERIFIED`, `CONFLICTING` or `UNDER_REVIEW` case is not removed, substituted, averaged, smoothed or automatically marked as accepted. Research review never authorizes scientific calculation elimination.
- **BuildMap experiment decision:** keep only an optional read-only, disposable-checkout inspection aid because the native scanner exposed additional source links and missing-gate navigation. No live BuildMap changes or mathematical improvement is claimed. Source-interaction/acceptance behavior remains unverified in production.
- **Release gates:** scientific equivalence, physical normals/PDE, independent data/causal replication, real Fisher information and actual external research inputs remain **NOT VERIFIED**; PR #4 remains draft.

## Non-negotiable preservation rules

1. Every admitted observation retains its exact original event ID, order ID, member ID, provenance, event/causal clock, direction, behavioral family and all input feature values. No averaging, smoothing, flattening, or representative substitution.
2. Outliers are **not discarded**. They can be set aside only from an experimental grouping proposal, with an explicit review reason and full original data durably retained. Review statuses: `AWAITING_REVIEW`, `UNDER_REVIEW`, `RETAIN_SEPARATE`, `RELEASE_SHADOW_GROUPING`. A review action does **not** delete evidence, or authorize job suppression or implicit scientific equivalence.
3. An outlier is a potential scientific finding, not statistical noise by default. Preserve exact values and clocks even if the observation is a short-lived or isolated excursion; compare its causal neighbors and direction rather than treating distance as a sufficient explanation.
4. No scientific calculation is eliminated by proximity, aliasing, cache identity, or review status. Job-elimination claims remain exactly zero in all shadow exports. Real science must continue on the preserved event stream after separately authorized integration.
5. Never silently cross family or AB/BA direction. The experimental grouping module defaults to strict family, direction, historical-clock compatibility; unresolved causal relationships require independent domain validation.

## Components added in isolated commits

| Module | Behavior | Limits |
| --- | --- | --- |
| `contracts.py` | Source/schema/version/frozen-unit calibration, historical cutoff, missing-feature abstention | Training and actual 99-plane mapping not implemented |
| `index.py` | Deterministic grid candidate pruning and exact metric recheck, high-dimensional scan fallback, center retirement/reversal | Memory-held centers; adversarial dense cells may still produce large scans |
| `disk_index.py` | SQLite streaming exact-verification query, bounded result count, persistent stable center identity, retire/restore, source contract | Disk may grow with all distinct centers; adversarial dense cells may still be slow |
| `durable_queue.py` | SQLite WAL transactional shadow lease, expiry/retry, idempotent submit, completion identity, multi-process SQLite locking | No distributed side-effect fencing; not a production scheduler or multi-host service |
| `result_cache.py` | Complete source/input/metric/policy/code/family/direction/type keyed no-clobber exact artifact store | Cache hits do not prove science equivalence; no scientific jobs suppressed |
| `boundary_validation.py` | Monotone explicit graph stability precondition, discrete mass balance and graph-energy diagnostics | No continuum Neumann geometry/normal or model validation |
| `grouping.py` | Reversible shadow labels and aliases with immutable per-event lineage and ledger; no grouping for set-aside outliers | State held in process memory; not a production calculation planner |
| `outliers.py` | Source-bound SQLite full-original event retention, reasoned review states, audit history, integrity verification | Not a replacement for a complete raw event archive; only explicitly flagged events are recorded |
| `benchmark.py` | Reproducible CPU synthetic differential benchmark against exact baseline | Numbers are host-specific; no market-scale performance conclusions |

## Verified and not verified

The first implementation commit `01d3256e550f` passed isolated GitHub Actions across Python 3.11/3.12/3.13. The later implementation commit `0eff85e37ccc` also passed isolated CI on all three versions. Additional commits require their own CI receipts.

The tests use synthetic, bounded examples only. Their success establishes local API behavior, not mathematical convergence over infinite sequences, real Neumann boundary applicability, exact equivalence of scientific jobs, 99-plane completeness, distributed execution, or real-market performance.

## Standalone acceptance gates

| Gate | Condition for acceptance | Current conclusion |
| --- | --- | --- |
| Source isolation | No Frankie/AWS/Search/BuildMap live changes | PASS, based on changed isolated paths |
| No silent evidence loss | Outlier original data, direction and IDs recoverable | PASS for tested local registry, not verified on actual science inputs |
| Numeric stability | Extreme values fail closed and finite metric distance is checked | Limited synthetic tests |
| Candidate completeness | Accelerated queries equal exact brute-force results | Limited synthetic differential tests |
| Recovery | Local SQLite queue lease expiry, retries and reopen | Limited synthetic tests |
| Scientific equivalence | Independently proved exact outcomes and no side effects | NOT VERIFIED; never eliminate jobs |
| PDE validity | Physical geometry, normals, consistency and boundary model | NOT VERIFIED; continuum Neumann disabled |
| Multi-host recovery | Distributed fencing/side-effect safety | NOT IMPLEMENTED |
| Real science | Native market data, 99-plane lineage, 30-day replay | NOT VERIFIED |
| Release | External scientific review and authorization | NOT AUTHORIZED |

## Usage

```sh
python -m unittest discover -s tests -p 'test_adaptive_locality*.py' -v
python -m compileall -q adaptive_locality
python -m adaptive_locality.benchmark
```

The offline benchmark is synthetic and deliberately bounded; outputs cannot be used to claim real search runtime gains. No new network services are required.

## Integration decision

Keep the branch in draft. Do not merge or deploy. Do not change BuildMap's native UI or Frankie source. An optional read-only BuildMap import and any integration require a separate explicit authorization after independent scientific review.

## November 8 — five-step coupling, Level 2 and algebraic geometry extension

- Verified source: `DavisAI1974/Basic_equations/level2_four_sciences.py`, `static_dipole_test.py` and `three_discoveries.py`. The original six-node chain and `B_net` averaging are hardcoded artifacts **not** used to derive network edges here.
- `information.py`: frozen-bin H/MI, labeled Fisher-like *proxy*, complete source identity and missing/out-of-range review. Actual parameter Fisher information is unsupported.
- `coupling.py`: directional five-step operator-dynamics experiment; independent full vs self-only vs **past-only lagged** donor null; rank/denominator abstentions retained, not filtered away.
- `level2_coupling.py`: data-derived directional pair-balance candidates; every window including missing/rank-deficient results kept for research, no pair mean. `research_holds.py`: persistent SQLite immutable archive with hash-linked cases and reload tests.
- `geometry_probe.py`: isolated algebraic operator-space curve `Ha^2=a+b*HaHb+c*(HaHb)^2`, plus `-(Ha-Hb)^2=-Ha^2-Hb^2+2HaHb` identity. The algebraic identity is not evidence of coupling. Detect novel train-support outliers even when curve residual is zero; preserve every point and label research-only.
- All current modules are **experimental**, do not eliminate scientific jobs or modify raw market evidence, and have no Frankie, AWS, live BuildMap or external service integration.
- At code commit `ec0e8561d1a4a57e782b8c54e02add1bd28c84d4`, CI `42457310741` passed 61 synthetic/offline tests on Python 3.11, 3.12, 3.13. This is NOT independent scientific acceptance.
- **Still unverified:** scientific causality, real scientific job equivalence, signed source data, 99 planes, full raw-archive handoff for InfoFrames, topology discovery under confounders, real Fisher information, physical geometry/normal vectors, continuum Neumann PDE, and real-data scaling. Continue diagnostic work in the new chat, not integration.

Next critical acceptance tests: independent equal-entropy noise vs true coupling; nonstationary regime shifts; conditioning/rank; raw RawFrame-to-InfoFrame-to-research-hold retention; multiple-hypothesis control; causal lag without lookahead; source identity and estimator variations.
