# Adaptive Locality — updated research, architecture and build plan

**Research-first standalone engine | November 8, 2026**

| Item | Current state |
| --- | --- |
| GitHub repository | `DavisAI1974/BuildMap` (storage/review repository) |
| **Current working branch** | **`feat/adaptive-locality-engine-20261108`** |
| Draft PR | [#4 — standalone Adaptive Locality](https://github.com/DavisAI1974/BuildMap/pull/4) |
| Integration | **NONE** with Frankie, AWS, Search, 30-day ingestion or live BuildMap |
| BuildMap experiment | Optional **scratch-only read-only inspection**, retained because it improved source navigation; not runtime integration |
| Release | Draft, unmerged, undeployed; **not independently scientifically accepted** |
| Engineering baseline | 87 isolated Python tests passed on 3.11/3.12/3.13, [CI 42460124352](https://github.com/DavisAI1974/BuildMap/actions/runs/42460124352) at pre-documentation HEAD `228e7f1795f7fd2551e537a87d87fbaea7660357`; optional [BuildMap trial 42460124388](https://github.com/DavisAI1974/BuildMap/actions/runs/42460124388) passed |

**CORE PRINCIPLE — NOTHING SCIENTIFIC IS DROPPED.** Every original observation, mathematical idea, counterexample, conflicting finding, outlier, surprising pattern, rank-deficient result, source mismatch, low-support interval, numerical limitation and unverified hypothesis is **retained and marked for further inspection/research**, not discarded, averaged, smoothed, flattened, substituted or treated as permission to eliminate a scientific calculation. Fit abstention does not mean data deletion. Historical explanations corrected by new evidence remain in the scientific-context register together with the counterevidence. A shadow grouping is a proposal, not permission to change science.

Read this README together with [the science/context register](../docs/ADAPTIVE_LOCALITY_SCIENCE_CONTEXT_REGISTER_20261108.md) and the [independent scientific diagnostics/acceptance report](../docs/ADAPTIVE_LOCALITY_INDEPENDENT_DIAGNOSTICS_20261108.md). They are not optional context when evaluating the architecture.

## 1. Where it began: original user-shared post

The idea that launched this project, preserved from the earlier chat:

> I'm working on some functions that mimic Cauchy behavior (sequence terms that become arbitrarily close), but are bounded by computability over a dynamic domain.
>
> We can achieve this by implementing a wave packet function that localizes both a merge by distance condition and sphere packing (use difference in distance between position neighbors to enable Neumann BCs).
>
> Soft launching hard boundaries #complexity #quantumphysics #mathart #

This was a **mathematical and computational inspiration**, not a proven physical model or a ready-to-run system. Our objective is to see how much of it can be implemented as defensible, bounded, reversible mathematics while **not erasing any original observations or unresolved interpretations**.

Its five strands are kept separate: finite/dynamic-domain Cauchy behavior; kernel or “wave-packet” locality; conditional merge-by-distance; sphere packing/covering; and possible Neumann/soft-boundary geometry. “Soft launching hard boundaries” remains a testable hypothesis about progressing from reversible fuzzy localization to evidence-backed constraints — not an instruction to hard-delete dissimilar events.

## 2. What we want this to become

**Primary goal:** a source-bound, CPU-first, recoverable research engine for adaptive locality, dynamic grouping *proposals*, original-evidence archiving, operator discovery, and independent scientific validation. The engine should explain **where and why states might relate**, preserve what differs, and make unresolved evidence easy to research.

**Longer-term possible benefit:** help identify unnecessary identifier-driven combinatorial expansion and duplicate non-scientific overhead in high-volume event calculations, eventually without losing scientifically important market behaviors or directions. That is **future application research**, not currently implemented Frankie optimization.

**Separate scientific direction:** test whether entropy, mutual-information and independently meaningful Fisher information, operator balances and dipole geometries capture reproducible patterns in distinct domains. This may reveal useful relationships, but current synthetic held-out tests alone establish neither causality nor cross-science universality.

**Not a goal:** asserting that a Gaussian is a quantum wavefunction, that finite Cauchy checks prove infinite convergence, that proximity proves equivalent science, that an algebraic identity proves coupling, or that graph distance alone defines physical Neumann normals.

## 3. Mathematical architecture — research contracts

### 3.1 Source, metric and locality

Represent each observation as **immutable original evidence + typed state features + family + time/order direction + provenance + frozen source/calibration contract**. IDs are retained as identities/links; they do not automatically become quantitative distance dimensions.

A basic exact calibrated distance is

```text
d(x,y) = sqrt(sum_j w_j * ((x_j - y_j)/scale_j)^2)
K_h(x,c) = exp(-d(x,c)^2 / (2*h^2)), h > 0
```

Candidate indexes may narrow search, **but exact contract-aware distance verification is mandatory**. Adaptive bandwidth uses strictly historical observations, bounded neighborhood support and hysteresis. Unknown/missing/calibration conflicts are research holds, never silently imputed. Membership weights are hypothetical/reversible and not surrogate event records.

### 3.2 Cauchy-like sequences on a changing domain

The classical Cauchy property concerns **all sufficiently late pairs** in a fixed metric space. Current code computes finite, bounded windows and drift indicators; no finite sample proves an infinite limit. If the domain or metric changes, comparisons may require a shared embedding, defined transport map or version-compatible comparison. Do not mask unsupported cross-domain comparisons.

Keep long drift, oscillation, transient jumps, boundary changes and deceptive finite stabilization as first-class counterexamples. **Unverified dynamic-domain convergence remains on the research agenda.**

### 3.3 Reversible packing and soft-to-hard boundary studies

Separate **center spacing** from **coverage**, **same-family proposal** from **actual equivalence**, and **visual display grouping** from **scientific calculation scheduling**. Preserve each original event, causal clock, order/queue history, directional AB/BA and family distinction. No merge removes original data or scientific jobs.

Original Neumann inspiration is retained. On a justified PDE domain, a no-flux boundary might have `n·(D∇u)=0`; neighbor distance differences alone do not establish the field, physical domain, normal, operator or continuum limit. Existing graph flux and stability tests are **graph experiments only**. Physical Neumann applicability is **UNVERIFIED**. If unsupported, investigate graph cuts/edge barriers or mark “not applicable” without deleting the Neumann hypothesis.

### 3.4 Five-step information/operator coupling

The previous [Basic Equations](https://github.com/DavisAI1974/Basic_equations) scientific work informed a five-step research procedure:

1. Derive independently calibrated `H`, `MI` and a clearly defined FI-like observable from original samples. Current `information.py` implements a **Fisher-like histogram roughness proxy**, **not parameter Fisher information**.
2. Construct a candidate library: `1, H_a, H_b, H_a², H_b², H_aH_b, MI_ab` and appropriately identified FI terms.
3. Fit `dH/dt ≈ Library · coefficients`; audit rank, numerical conditioning, future leakage and source identities.
4. Study independent sources/domains, originally **physics, biology, chemistry and geology**, without pretending duplicate data under different labels are independent.
5. Compare independently supported operator relationships while keeping distinct results, conflicts and counterexamples.

The original six-node nearest-neighbor topology and averaged `B_net` from `level2_four_sciences.py` were **fixed modeling choices, not discovered laws**. Current implementation does not inherit them as assumptions. Additional research lines from those discussions, including **KBK, AI Poincaré, SINDy and PySR** comparisons, are retained as *future exploratory leads*, not completed work.

### 3.5 Dipole balance, algebraic geometry and predictive controls

Level 2 investigates separately retained, directional balance series

```text
B_ij(t) = abs(c_(Hi^2)(t)) / abs(c_(Hi*Hj)(t))   [only when identified]
```

Near-zero denominators, rank deficiencies, cross-window conflicts and unsupported links become **research holds**. Do not replace the vector of pair balances with an average or use an arbitrary epsilon to manufacture a ratio.

The operator-space identity

```text
-Ha^2 - Hb^2 + 2*Ha*Hb = -(Ha-Hb)^2
```

is algebraically true for any values. It can hold in independent equal-entropy channels with empirical MI≈0; **it does not establish coupling or physical geometry**. Likewise if `Hb=c` is constant and nonzero, `Ha²=(HaHb)²/c²` can explain a static quadratic fit exactly without interaction. Both the **original hypothesis and correction** remain preserved for scientific review.

Our geometric study distinguishes frozen-support novelty from a model residual, investigates conditioning, and tests whether including `(HaHb)²` improves **future** entropy-change prediction beyond a **nested linear interaction** and matched historical donor nulls. Some toy dynamics show additional predictive information, but **causality, independent replication, physical geometry and general scientific utility are unverified**.

## 4. Updated system architecture — current vs future

```text
[ORIGINAL SCIENCE / SOURCE DATA -- future authorized adapter ONLY]
    immutable raw events, member/order IDs, family/direction, causal clocks
    (external source, 99-plane contracts if later applicable)
                      |
             source/schema admission
    (pre-admission invalid bytes require own future raw archive)
                      |
       +--------------+----------------+
       |                               |
[ALREADY BUILT, STANDALONE]     [RESEARCH IDEAS / FUTURE]
  exact typed frames, H/MI          moving-domain transport
  fixed bins + FI-like proxy        learned metrics, packet forms
  exact metric + grid index         larger index, scale tests
  Gaussian locality, centers        physical normals/PDE geometry
  finite Cauchy + graph tests       real parameter Fisher info
  directional coupling + Level2     independent four-science study
  static geometry + future-rate     independent causal controls
  historical null/nested model      equivalence proofs
       |                               |
       +-------------------------------+
                      |
      archive original raw + derived BEFORE any fit
      preserve every fit/outlier/abstention/conflict
       +--------------+----------------+
       |                               |
       v                               v
[LOCAL RESEARCH HOLDS]       [OFFLINE INSPECTION ONLY]
 SQLite + hash-linked review   local HTML; optional BuildMap
  all data & gate records       scratch scanner (read-only)
  no scientific job skipping    source links + unknowns
       |                               |
       +--------------+----------------+
                      |
           independent scientific review
                (NOT ACCEPTED)
                      |
           [FUTURE, SEPARATELY AUTHORIZED]
        possible source adapters, real replay,
       streaming comparisons, signed receipts,
       controlled rollout & reversible rollback
```

### Module inventory and actual implementation state

| Component | Current implementation | Important limits |
| --- | --- | --- |
| Core locality / kernels | `core.py`, `advanced.py`, `contracts.py` | finite diagnostic and frozen experimental metrics, not dynamic-space theorem |
| Index / packing | `index.py`, `disk_index.py`, `grouping.py` | exact-verified candidates, reversible shadow grouping; no real production scale claim |
| Flux/boundary | `graph_boundary.py`, `boundary_validation.py` | graph-domain research, not continuum Neumann proof |
| Source and information | `information.py` | original RawFrame lineage; H/MI and Fisher-like **proxy** |
| Level 1 and Level 2 | `coupling.py`, `level2_coupling.py` | all directional windows/results; rank and causal limits explicit |
| Operator-space diagnostics | `geometry_probe.py` | identity/artifact checks, frozen-support novelty, conditioning indicator |
| Future-rate diagnostic | `geometry_validation.py` | historical donor controls, nested quadratic vs linear interaction, multiple time splits; synthetic only |
| Original preservation | `outliers.py`, `research_holds.py`, `standalone_review.py` | archive-first local SQLite; importer must still archive invalid pre-RawFrame source bytes |
| Retained unresolved gates | `research_gates.py` | 8 explicit gate categories; not exhaustive of possible science |
| Queue, checkpoints and cache | `queue.py`, `durable_queue.py`, `checkpoints.py`, `result_cache.py`, `ledger.py` | offline/local; no distributed side-effect equivalence or job suppression |
| Offline tools and experiments | `cli.py`, `review_cli.py`, `visualization.py`, `benchmark.py`, `experiments.py`, `adapters.py` | shadow-only, unsigned outputs; display-only sampling |
| Optional BuildMap review | `buildmap_trial.py` and `tests/adaptive-locality-buildmap-trial.test.js` | scratch read-only source inspection, **not live BuildMap integration** |

This package sits in `BuildMap` **for version control and review only**. The mathematical modules do not depend on BuildMap's running application, its web UI or Frankie's private pipeline. The independent architecture is deliberate.

## 5. Build plan — completed work and next gates, in safe order

The earlier [P0–P9 full architecture plan](../docs/ADAPTIVE_LOCALITY_ARCHITECTURE_BUILD_PLAN_20261108.md) remains a **historical comprehensive proposal**. Its Frankie-facing, scheduler and rollout phases are **NOT authorized current work**. This is the updated execution order:

| Stage | Status | Work / acceptance evidence |
| --- | --- | --- |
| A. Original proposal and mathematical distinctions | **DOCUMENTED** | Preserve Cauchy/dynamic domain, wave-packet, packing, soft/hard boundary and physical Neumann *hypotheses* without conflating them |
| B. Deterministic standalone locality core | **BUILT, SYNTHETIC TESTED** | typed identity contracts, frozen metrics, exact distance, locality, reversible center/soft membership proposals, finite diagnostics |
| C. Offline robustness & recovery | **BUILT, BOUNDED TESTED** | grid/disk candidate verification, local queue/checkpoints/cache, graph stability and unsigned viewer; larger scale/multihost unverified |
| D. Five-step & Level 2 science | **BUILT, SYNTHETIC TESTED** | independent derived information, full/self/past-only control, individual directional balance links, no averaged network |
| E. Operator geometry & independent checks | **BUILT, SYNTHETIC TESTED** | equal-entropy zero-MI negative control, constant-donor tautology, rank/conditioning review, nested predictive comparison, seed/regime tests |
| F. Evidence/archive-first scientific review | **BUILT, BOUNDED TESTED** | full source-bound RawFrames/InfoFrames, outliers, rejected/blocked cases, contradictory windows and linked research holds; no automatic suppression |
| G. Optional BuildMap scratch trial | **KEEP, OFFLINE ONLY** | 7 native static source connections and 8 visible unverified gates; zero source changes, false verified states and scientific jobs eliminated |
| H. Next independent scientific validation | **UNVERIFIED / RESEARCH** | independent data/seed/calibration, causal and negative controls, multiplicity, operator reparameterization, true conditioning/precision, meaningful Fisher definition, real/physical geometry |
| I. Future independent scale & source contracts | **NOT BUILT / RESEARCH** | recover invalid pre-admission bytes, lossless partition manifests, signed external evidence, independent scale/cost benchmarks and realistic source adapter design |
| J. Any Frankie, cloud, Search, live BuildMap or production execution | **NOT CONNECTED / NOT AUTHORIZED** | only consider after scientific and source-contract review and separate explicit authorization; protect active research and all data |

**Research-hold is a first-class outcome in every stage** — an unresolved result remains available for inspection, not discarded or promoted. Engineering PASS cannot satisfy scientific equivalence by itself.

### Eight explicitly retained scientific gates

`independent-replication`; `causal-controls`; `algebraic-novelty`; `rank-conditioning`; `parameter-fisher-information`; `physical-neumann-boundary`; `raw-external-validation`; `scientific-equivalence`. All are **UNVERIFIED**. Additional research ideas are also recorded in the [science-context register](../docs/ADAPTIVE_LOCALITY_SCIENCE_CONTEXT_REGISTER_20261108.md); they are not silently excluded by this eight-item classification.

## 6. Possible future scientific and product explorations (no endorsement yet)

**Mathematical:** rigorous comparison of moving metric spaces, other kernel/packet families, anisotropic supports, packing/covering tradeoffs, perturbation-stable coefficient manifolds, improved false-discovery controls, independent symbolic discovery, threshold sensitivity and adaptive boundary analogues.

**Scientific:** independent physics/biology/chemistry/geology operator experiments; distinguish equal-entropy artifacts from actual interactions; discover domain-relevant causal/structural relationships; investigate why rank deficient, short-lived or contradictory points occur instead of smoothing them out.

**Engineering/application:** high-volume event-state review without ID-driven grouping; original-order and direction-preserving candidate locality maps; CPU/memory-bounded streamed science; improved anomaly visibility; independently signed reproducible experiment receipts; richer BuildMap review walkthroughs only if future evidence warrants them.

**Visualization inspiration:** [Slayer](https://github.com/janearc/slayer) prompted raw-computation/display separation, immutable source-aware frames, replay probes, cache-key completeness, and CPU-first correctness tests. No Slayer rendering/Metal code was copied; this remains a separate implementation and an architectural inspiration.

All above possibilities are **OPEN FOR RESEARCH**, not rejected or discarded; they remain explicitly separate from existing code and validated behavior.

## 7. Why this is isolated and what must not change

**Branch currently in use: `feat/adaptive-locality-engine-20261108`**. Draft PR #4 is intentionally **unmerged**. The original architecture envisioned eventual Frankie/BuildMap consumers, but their real contracts and science equivalence are not established, and the private source was not inspected in this branch. Running this as production grouping would risk discarding exactly the distinct patterns we are trying to protect.

**Isolation guarantees / directives:**

- No connection to Frankie, AWS, Search, 30-day ingestion, active production BuildMap runtime or cloud machines.
- No merge, deploy, live ingestion, production job scheduling or automatic calculation skipping.
- No smoothing, averaging, flattening, dropping or substituted original observations or scientific results, including rank-deficient, conflicting, unverified or negative cases.
- Retain individual order/member/event links, original values and original source identities, direction, family, clocks, and full research history.
- CPU-first bounded experiments; reuse applicable CI receipts and avoid unnecessary broad test runs.
- Review must explicitly distinguish “implemented,” “synthetic test passes,” “scientific hypothesis,” “unverified,” “negative/counterexample,” and “not implemented.” All unresolved material remains marked **FURTHER INSPECTION / RESEARCH**.

## 8. Developer commands and prior CLI compatibility

From a checkout of the isolated feature branch:

```bash
python -m compileall -q adaptive_locality
python -m unittest discover -s tests -p 'test_adaptive_locality*.py' -v
python -m adaptive_locality.benchmark
```

The original shadow CLI remains available; it **does not** execute real scientific jobs:

```bash
python -m adaptive_locality.cli example.json --output proposals.json
```

Example input for the shadow CLI (unchanged in meaning):

```json
{
  "manifest":{"run_id":"test","day":"20231018","source_identity":"demo","planes":["example-plane"]},
  "metric":{"features":["imbalance","spread"],"scales":[1,1],"weights":[1,1],"version":"v1"},
  "config":{"radius":0.5,"bandwidth":0.25},
  "events":[
    {"event_id":"e1","family":"P","features":{"imbalance":0.1,"spread":1},"event_clock":1,"provenance":"demo"},
    {"event_id":"e2","family":"P","features":{"imbalance":0.2,"spread":1},"event_clock":2,"provenance":"demo"}
  ]
}
```

Offline display/replay experiment (choose TWO different features actually present in your data):

```bash
python -m adaptive_locality.review_cli example.json \
  --x imbalance --y spread \
  --output offline-locality.html --probes offline-locality-probes.json
```

Optional BuildMap read-only scratch inspection (separate Node test; requires installed locked dependencies):

```bash
npm ci --ignore-scripts --no-audit --no-fund
node --test tests/adaptive-locality-buildmap-trial.test.js
```

The newest archive-first research API is `adaptive_locality.standalone_review.archive_first_geometric_review`, which requires complete already-typed `RawFrame` originals, matching `FixedBins` and a bound `ResearchHoldRegistry`. It archives upstream raw and derived data before attempting a fit. Invalid source bytes rejected before `RawFrame` construction still require future importer-level preservation. It does not connect external systems.

## 9. Documentation for independent review / Claude Code

- [Original P0–P9 architecture proposal](../docs/ADAPTIVE_LOCALITY_ARCHITECTURE_BUILD_PLAN_20261108.md): important historical scope and possible future integrations, **not** current deployment authorization.
- [Scientific inspirations, math, hypotheses and corrected interpretations](../docs/ADAPTIVE_LOCALITY_SCIENCE_CONTEXT_REGISTER_20261108.md): context preservation; nothing unverified discarded.
- [Five-step, Level 2 and geometry technical handoff](../docs/ADAPTIVE_LOCALITY_COUPLING_GEOMETRY_HANDOFF_20261108.md): detailed prior engineering decisions.
- [Current scientific diagnostic/acceptance report](../docs/ADAPTIVE_LOCALITY_INDEPENDENT_DIAGNOSTICS_20261108.md): measured controls and explicit limits; 87 isolated Python tests in verified CI.
- [Standalone acceptance ledger](../docs/ADAPTIVE_LOCALITY_STANDALONE_ACCEPTANCE_20261108.md): incomplete gates and older historical states.
- [Slayer architectural review](../docs/SLAYER_RENDERING_REVIEW_20261108.md): visualization/validation inspiration.
- [Claude Code review handoff](../docs/ADAPTIVE_LOCALITY_CLAUDE_CODE_REVIEW_HANDOFF_20261108.md): review instructions, proposed gaps and preservation boundaries.

**Final engineering status:** standalone implementation and bounded synthetic verification have progressed substantially. **Scientific acceptance, real dataset correctness, physical Neumann applicability, production scaling, exact calculation equivalence and deployment remain UNVERIFIED / NOT AUTHORIZED, retained for further inspection.**
