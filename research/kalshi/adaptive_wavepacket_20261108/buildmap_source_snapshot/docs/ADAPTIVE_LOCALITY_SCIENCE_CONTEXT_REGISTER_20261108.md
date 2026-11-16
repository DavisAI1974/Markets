# Adaptive Locality — scientific context, inspiration and open-ideas register

**Created:** 2026-11-08. **Working branch:** `feat/adaptive-locality-engine-20261108` in `DavisAI1974/BuildMap`. **Draft review PR:** https://github.com/DavisAI1974/BuildMap/pull/4.

This register accompanies [the canonical engineering README](../adaptive_locality/README.md), the [original architecture plan](ADAPTIVE_LOCALITY_ARCHITECTURE_BUILD_PLAN_20261108.md), [technical coupling/geometry handoff](ADAPTIVE_LOCALITY_COUPLING_GEOMETRY_HANDOFF_20261108.md), and [independent diagnostics report](ADAPTIVE_LOCALITY_INDEPENDENT_DIAGNOSTICS_20261108.md).

**First and permanent rule: NOTHING SCIENTIFIC IS DROPPED.** Unverified, incompatible, rank-deficient, anomalous, contradictory, out-of-support, insufficiently calibrated and speculative findings are retained verbatim when available and marked for **FURTHER INSPECTION / RESEARCH**. Rejecting an inference, a fitting attempt, a grouping proposal or a production route never deletes its source data, alternate hypothesis or mathematical context. No smoothing, averaging, flattening, representative substitution or scientific job elimination. The register records scientific ideas as ideas; code and experimental evidence have separate status.

## 1. Original inspiration — the user-shared post that started the work

Preserved text from the earlier conversation:

> I'm working on some functions that mimic Cauchy behavior (sequence terms that become arbitrarily close), but are bounded by computability over a dynamic domain.
>
> We can achieve this by implementing a wave packet function that localizes both a merge by distance condition and sphere packing (use difference in distance between position neighbors to enable Neumann BCs).
>
> Soft launching hard boundaries #complexity #quantumphysics #mathart #

This is the motivating **proposal**, not a theorem, a verified simulation, an accepted merge contract or a physical quantum claim. It combines five separable research threads:

1. **Cauchy-like behavior under finite computation and changing domains** — compare successive states without confusing a bounded test with infinite mathematical convergence.
2. **Localized wave packets / kernels** — limit where potential state relationships are examined, preserving other regimes.
3. **Merge by distance** — investigate near states, but never infer causal or scientific equivalence from proximity alone.
4. **Sphere packing and covering** — organize distinct candidate centers without using a center as a replacement for its original members.
5. **Neighbor-distance differences and Neumann boundary ideas** — a promising motivation for investigating boundary-sensitive evolution, not a sufficient mathematical construction of normals or PDE boundary flux.

“**Soft launching hard boundaries**” is preserved as a design question: can reversible, fuzzy localization/uncertainty and research abstention be used to approach a sharp eligibility boundary only after independently demonstrated evidence? It does not authorize abrupt event deletion or an unjustified physical boundary claim.

## 2. Dynamic-domain Cauchy mathematical questions

- For a fixed complete metric space (X,d), a Cauchy sequence requires: for every epsilon>0 there exists N such that d(x_m,x_n)<epsilon for all m,n>=N. A finite tolerance/window diagnostic measures something weaker.
- If the domain, schema, metric, topology, calibrated scales or observable family changes with time, **how are points at different times compared**? Research possibilities include common embedding, explicitly versioned transport maps, comparable pullback metrics, path-specific distance and set-valued/graph notions of proximity. None is a proven current convergence theorem.
- Implemented experiments: fixed calibration and exact distance checks, finite-window Cauchy maxima, drift guards and provenance/metric versions; historical-only candidate neighborhood calibration.
- Retained counterexamples and caveats: deceptively stable finite tails, oscillation, long drift, jumps, missing windows, nonstationarity, dimensional mismatch, metric incompleteness, and a dynamically changing space that makes a naive Cauchy inference invalid.
- Future mathematical work: prove precisely which finite statements are valid; inspect convergence in moving spaces and under family-conditioned metrics; test adversarial slow drift, long-period oscillations, new families and calibration changes. Mark unresolved rather than claiming convergence.

## 3. Localization, packet functions and statistical-state geometry

- Built reference kernel: **real nonnegative Gaussian** `K_h(x,c)=exp(-d(x,c)^2/(2h^2))`. “Wave packet” is a useful localization analogy, **not** an asserted complex quantum amplitude or Schrödinger state.
- Built exploratory historical-only adaptive bandwidth/density and bounded exact-verified center indexing; near-neighbor candidate retrieval must always recheck the declared metric.
- Questions retained: whether packet width should vary with local density, temporal regime, operator uncertainty, anisotropy, or source support; whether hysteresis can avoid unstable center churn; whether localized spectral/oscillatory components improve over real Gaussian weights. Each would need independent controls and a defined scientific meaning.
- A soft membership `w_ik=K(x_i,c_k)/sum_j K(x_i,c_j)` can propose a **reversible** group affiliation; it must not average/order-compress original causal events or determine calculation equivalence.
- High-dimensional volume effects and distance concentration are open. Exact similarity, packing, covering and physical geometry are different contracts.

## 4. Sphere packing, family modes, event semantics and causal direction

- Packing requires separated centers under a particular metric; coverage and scientific representativeness are separate optimization questions.
- Discussed target application: reduce *unnecessary ID-driven combinatorics* in a future event/market-state pipeline while preserving actual order records. An order ID is not a physical market condition, but its **actual associated order and member** remains scientifically important.
- Keep event IDs, order IDs, member IDs, original orders, family labels (including P/O/X/F if those are actual source families), AB/BA directions, resting/queue age, FIFO, replenishment/withdrawal/absorption/modification, causal clocks, temporal sequences, provenance, original measurements and all applicable evidence planes. Do not treat names/IDs as numerical-distance drivers merely because they exist.
- Current implementation is conservative, offline, family-aware and reversible. There is **no proven production calculation reduction**, no justified elimination of any directional comparison, and no implemented 99-plane source adapter. A future application is optional and requires separate authorization.

## 5. Soft boundaries, graph flux and proposed Neumann treatment

- Original neighbor-distance-difference inspiration is **retained as a research hypothesis**, not discarded because it is presently underidentified.
- A Neumann condition has the form `n·(D∇u)=g` (reflecting/no-flux when g=0) on a specified boundary, with defined domain, field u, geometry, normal n, differential operator and discretization. Differences in neighbor distance do **not** determine all of these by themselves.
- Built: graph-domain weighted-flux residual, bounded finite-volume/difference-style experiments and synthetic mass/energy/stability diagnostics.
- Unverified: continuum-domain geometry, normals, boundary measurement, consistency, correct flux physics, continuum limit and applicability to observational market-state vectors.
- Keep alternative branches: graph cut/edge penalties, kernel reflection, graph Laplacian, graph-conservative transport, soft barrier potentials, moving interfaces and “Neumann not applicable” as an explicit legitimate finding. Never replace the physical PDE hypothesis with an unrelated graph quantity without labeling the substitution.

## 6. Five-step Basic Equations scientific discovery conversation

The earlier research came from `DavisAI1974/Basic_equations`: `level2_four_sciences.py`, `static_dipole_test.py`, `three_discoveries.py`, and context such as `per_domain_kbk.py`. The recovered five-step procedure was:

1. Compute information-theoretic observables — Shannon H, mutual information MI, and an FI-like measure — from raw calibrated measurements. Treat observables as variables in their own right, without discarding the original data.
2. Build candidate operator libraries, including `H_a`, `H_b`, `MI`, `H_a²`, `H_b²`, `H_a H_b`, cross terms and relevant FI-like variables.
3. Fit `dH/dt ≈ Library × coefficients` with explicit rank/conditioning controls; investigate self and interaction terms rather than presuming a topology.
4. Run independent analyses within *physics, biology, chemistry and geology* with distinct source lineage and calibration.
5. Compare independently supported operator relationships across sciences. Four names attached to copied evidence do **not** establish independent replication.

The original code hardcoded a six-node neighbor chain and predefined pairs; its averaged `B_net` can blur distinct pair behavior. Those implementation assumptions are **recorded as historical hypotheses**, not copied into the new engine or silently omitted from the history. Other ideas in the original context — **KBK, AI Poincaré, SINDy, PySR, sparse symbolic/operator discovery** — remain **research leads**, not completed or verified Adaptive Locality implementations.

Implementation: `information.py` (frozen-bin H/MI, explicitly *Fisher-like histogram roughness proxy*, not parameter Fisher information), `coupling.py` (source-bound directional QR fitting, self-only baseline and matched past-only shifted donor null), `level2_coupling.py` (each pair-balance window and directed interaction separately), `research_holds.py` (recoverable full-raw evidence). Independent real-domain scientific replication remains pending.

## 7. Level 2 directional dipoles and ratio conditioning

- Source concept: opposing self-quadratic and interaction coefficients, often studied through `B_ij=|c_(H_i²)|/|c_(H_i·H_j)|` as a **windowed pair-specific balance series**. Direction a←b need not equal b←a.
- Open issue: tiny/zero denominator, collinearity, duplicated windows, shifting calibration, sparse support and confounding. These are **findings for inspection**. Do not inject an epsilon and call an unidentifiable ratio reliable.
- Built: independent unsmoothed directional windows and Level 2 link tests; missing, overlapping, rank-deficient, conflicting and low-support windows preserved in full with audit cases.
- Do not replace distinct pair series with a `B_net` mean, inferred six-node chain or a cluster surrogate. The original six-node experiment itself remains a reviewable scientific precedent.

## 8. Geometry-based dipole interpretations — preserved and corrected

- The basis vector `(-1,-1,+2)/sqrt(6)` on `(H_a²,H_b²,H_aH_b)` is tied to `-H_a²-H_b²+2H_aH_b=-(H_a-H_b)²`, a universal **algebraic identity**. Exact equal-entropy signals can exhibit it with **zero empirical MI** in deliberately independent synthetic ensembles.
- The static curve `H_a² = a + b(H_aH_b) + c(H_aH_b)²` can fit perfectly for algebraic reasons. If donor `H_b=c0 !=0` is constant, `H_a²=(H_aH_b)²/c0²`; this proves no interaction. Both this historical geometric interpretation and the counterexample are kept.
- Current `geometry_probe.py` retains point-by-point residual, frozen-support novelty, identity, rank and conditioning indicators. An extreme unseen point can have zero fitted residual; novelty remains separately flagged.
- `geometry_validation.py` tests future target entropy-rate changes with historical controls and a nested linear-interaction baseline before considering whether `(H_aH_b)²` adds information. Positive toy controls establish *possibility*, not independent real-world causation.
- Remaining possibilities: different polynomial coordinate systems, reparameterization/centering effects, stable operator manifolds, geometry of coupling coefficients, phase/regime transitions, structural invariants across different sciences, and independent symbolic confirmation. These are research questions, not validated physical spaces or known merge rules.

## 9. Distinguish prediction, association, causation and scientific equivalence

Held-out predictive gain, matched past-only donor null and multiple chronological cutoffs can support only an **association candidate**; overlapping splits are not independent replications. Common causes, reverse direction, feedback, changing regimes, multiplicity, estimator choice and hidden confounders remain open.

Even a genuinely predictive relation does **not** show two market/order event calculations are equivalent. Reuse or elimination requires an independent exact scientific proof covering causal clocks, family/order semantics, side effects, input sources and precision. As of this document: **zero scientific jobs eliminated**, with no production authorization.

## 10. Inspirations beyond the equations: BuildMap, Slayer, CPU reference

- **Slayer**: user shared https://github.com/janearc/slayer. The prior review found a Go ray-tracing toolkit with optional Metal path and examined raw frame vs display development, deterministic replay probes, source-aware cache keys, atomic artifacts and independent regression tests. Adopted *architecture*, not the rendering code, physical ray formulas, GPU or dependency. `visualization.py` and `review_cli.py` keep computation and offline visualization separate.
- **BuildMap**: originally a possible future observer/inspector, not a mathematical solver. A disposable copy/source-scanner experiment showed **7 observed static source relationships and 8 planned unverified scientific gates**, zero false verified/live claims, zero original source mutations or scientific jobs suppressed. Keep only the **optional offline inspection trial**; no live BuildMap UI/Guide or signed collector connection.
- **CPU-first science**: bounded synthetic tests, exact reference comparisons, source identity/provenance, deterministic replay and no broad revalidation when applicable CI receipts are current. GPU/Metal is a possible later implementation study only if it proves reproducibility and cost benefit.

## 11. Applications — provenance and speculation clearly separated

**Explicitly discussed future application, not connected:** reduce ID-based combinatorial explosion in a streaming market/event analysis while protecting all order semantics, families, directional comparisons, current checkpoints and 30-day ingestion. Source-specific design requires inspecting the independently authorized Frankie implementation; this branch does not touch it.

**Cross-science comparison discussed:** independently seek information-operator patterns across physics, biology, chemistry, geology, without pretending labels produce replication.

**Exploratory possibilities inferred from the mathematical framework (not previously claimed as built):** research on nonstationary time-series regimes, streaming anomaly/novelty detection, graph-boundary alternatives, adaptive sampling/review priority, geometrically organized visual inspection, candidate equivalence auditing, and computationally bounded scientific experiment routing. Each is an idea to evaluate on its own data, calibration and evidence with full original retention.

## 12. Permanent unverified/research agenda and no-loss guarantee

`research_gates.py` defines eight explicit retained gates: independent replication; causal controls; algebraic novelty; numerical rank/conditioning; true parameter Fisher information; physical Neumann boundary; real raw external validation; scientific equivalence. Every one remains **UNVERIFIED** and eligible for durable source-bound research review. See `docs/ADAPTIVE_LOCALITY_INDEPENDENT_DIAGNOSTICS_20261108.md`.

There are other important open areas **in addition to these eight**: true convergence in dynamic spaces, metric/topology invariance, packet family choice, packing/coverage optimality, physical graph boundary meaning, realistic scale/accuracy, multiplicity correction, independently measured cost/performance, cryptographically signed external receipts, complete pre-admission bad-byte archival, large-archive partition manifests and multi-host recovery. The eight-gate registry is **not** permission to overlook those additional questions.

**Nothing is silently dropped, averaged, smoothed, flattened, renamed as a solved theorem or removed from the scientific calculation set.** A failed/absent implementation is recorded as `NOT IMPLEMENTED`; a challenged inference is recorded as `NOT ESTABLISHED`; a counterexample is recorded along with the historical hypothesis; any incomplete case is marked `RETAIN FOR FURTHER INSPECTION/RESEARCH`.

**Scope of historical recovery:** This document preserves the recoverable earlier user-shared post, current conversation work, GitHub handoffs, architecture plan and related source-review notes. It is not a claim to have recovered every unseen remark from every past chat. If another discussion or scientific possibility is subsequently recovered, append it here with its provenance instead of overwriting or dropping existing research.
