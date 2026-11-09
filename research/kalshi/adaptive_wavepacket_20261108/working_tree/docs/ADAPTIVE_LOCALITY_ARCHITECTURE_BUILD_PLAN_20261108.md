# Adaptive Locality and Soft-Boundary Grouping — architecture and complete build plan

Status: design specification only; no Frankie production changes authorized. Prepared 2026-11-08.
Owner architecture: independent deterministic scientific module; Frankie is the data/calculation consumer; BuildMap is observer, inspector, comparison, and acceptance surface.

## 0. Verified baseline and limits
BuildMap PR #2 (head codex/buildmap-completion-20261031, SHA 079c5e4c4a2f87681d2e5933ce60dddc70c74ccc) documents explicit signed Python runtime observations and source-bound finite-case comparisons; it is open and unmerged. PR #1 is open. The checklist says domain workload, equivalence, checkpoint, realistic-scale, and release integration are still pending. The Frankie private source is *not* available through this GitHub connection. Before implementation, inspect live Frankie HEAD, saved handoffs, current day/run, 99-plane catalog and evidence schema using the authorized access path. Do not assume earlier group counts are current.

## 1. Goal and non-goals
Deliver a reversible, evidence-preserving alternative to ID-driven combinatorial grouping based on meaningful market-state neighborhoods, mathematically explicit local kernels, strict convergence diagnostics, probabilistic/geometric packing experiments, and optional flux-aware boundary treatment. Stream accepted groups into the existing assembly-line calculator; measure changes in distinct scientific calculations and real runtime. Never modify original events or discard order IDs, member IDs, causal/directional data, family labels, timestamp clocks, saved results, checkpoints or 30-day ingestion. Do not turn analogies to quantum mechanics into a physical claim. No production algorithm switch without controlled equivalence and scientific-signoff.

The target is not to collapse meaningful market states. Reducing group cardinality is a testable outcome, not a license to drop scientifically meaningful comparisons or market microstructure information.

## 2. Math contracts (distinct mechanisms, no conflation)
Let observation x_i=(m_i,e_i,f_i,p_i) where m is typed market-state feature vector with units, missingness and schema; e is event/order evidence lineage; f is behavioral family; p is provenance. Identifiers remain in e/p for downstream membership/order analysis, never in the distance metric merely because they are identifiers.

Metric d: explicit unit-aware weighted standardized distance or masked Mahalanobis distance using training-frozen calibration, positive-semidefinite regularization, missing-data abstention and temporal admissibility; do not imply a metric when missing-value handling violates triangle inequality. Validate symmetry, nonnegativity, triangle inequality where required, and identity/missing policies. Keep event order and direction separate from symmetric similarity.

Locality: K_h(x,c)=exp(-d(x,c)^2/(2h^2)) for h>0 as a *real, positive localization kernel* (not a Schrödinger state or physical quantum wavefunction). Neighbor candidates selected with approximate index but exact metric verification before merge. Adaptive bandwidth h(x) from bounded local k-neighbor density with hysteresis, min/max radius and low-support abstention. Avoid look-ahead: fit/normalize on past admitted data only; version boundaries and preserve prior states.

Cauchy: for a state sequence (s_n), finite diagnostics C(N,epsilon,W)=max_{i,j in [N-W+1,N]} d(s_i,s_j) <= epsilon on windows; explicitly a finite approximation, not a proof of full Cauchy property. To assess asymptotic behavior use increasing windows/tolerances, drift tests and stable feature identity. Define metric-space completeness assumptions and counterexamples (slow drift, oscillation, discontinuities, finite deceptive stabilization). No future leakage.

Merge: proposed A,B merge iff (1) same compatible behavioral family or explicitly approved cross-family relation; (2) necessary temporal/causal invariants hold; (3) verified exact distance / overlap and frozen confidence limits; (4) no scientifically meaningful directional/order-book behavior lost; (5) no rejected conflicting saved results. Record proposed/accepted/rejected decision, evidence and reversible lineage. Distinguish assignment, probabilistic overlap, representative substitution, and actual calculation elimination: the last requires separate exact-equivalence or approved bounded-error contract.

Packing: centers with exclusion radius r under chosen metric, with explicit minimum separation and coverage target; packing/covering dual objectives can conflict. Dynamic insertion, split, retire and re-center with stable identity aliases. Approximate ANN candidates plus exact verification; version center movement to avoid invalidating stored keys. Sphere-packing is a geometric heuristic, not guaranteed optimal in arbitrary high-dimensional spaces.

Boundaries: optional graph-domain finite volume/difference operator on a justified physical/abstract conserved quantity u; flux boundary n·(D∇u)=g (zero g for reflecting Neumann) constructed using neighbor geometry, normals and stencil weights, not solely differences in pairwise distances. Define conservation/stability consistency and flux residual. If no valid PDE, geometry, and flux interpretation exists, use simpler boundary-aware kernel/graph cut penalty, never claim a Neumann BC.

Soft transition: retain fractional memberships w_ik=K(x_i,c_k)/sum_j K(x_i,c_j) only when denominator valid; preserve original discrete event identities and measure mass/conservation. Never average raw causal events, event clocks, resting order, queue position or meaningful family modes. Add uncertainty/abstain route and conservative hard-route baseline.

## 3. Architecture

```
immutable native events + 99-plane schema + existing saved tables
   -> validated feature contracts (versioned, no IDs as calculation drivers)
   -> snapshot + provenance registry -> metric/calibration service
   -> nearest-neighbor candidate retrieval -> exact distance verifier
   -> locality kernels + adaptive bandwidth -> family-aware packing/index
   -> soft membership + finite Cauchy diagnostics + boundary policy
   -> decision ledger (propose/accept/reject, split/merge, immutable lineage)
   -> comparison eligibility gate (scientific exactness / bounded error)
   -> job dedupe/plan (AB-BA directionality, FFT cache, Y-partner reuse)
   -> ready-group queue -> existing streaming calculator/teachers
   -> output receipts, provenance, checkpoint, workload and accuracy metrics
   -> BuildMap evidence adapter -> inspect/compare/approve/roll back
```

Isolation: keep a standalone library/package with deterministic APIs and fixtures; Frankie adapter translates source contracts and emits ready groups; BuildMap adapter reads signed evidence, workload counts and decision graphs, not live scientific control. No new global whole-day gate. CPU-first, bounded per-worker memory, concurrent group admission with back-pressure, checkpoint-safe recovery.

Suggested implementation directory in Frankie *after inspecting repository*:
- adaptive_locality/contracts.py — schema, identities, rejected/unsupported states.
- features.py — market feature extractor, family tags, missingness.
- metric.py — frozen calibration, exact distance and invariants.
- locality.py — kernels, neighborhood and bandwidth.
- convergence.py — finite Cauchy diagnostics with drift guards.
- packing.py — stable centers, split/merge, coverage.
- boundaries.py — optional graph/FVM flux module and fallback edge-aware kernel.
- decisions.py — audited reversible action ledger.
- scientific_gate.py — equivalence/approximation policies, causal/directional checks.
- scheduler_adapter.py — streaming ready groups and backpressure.
- receipts.py — identities/checkpoints/workload counters.
- experiments.py — baseline/shadow/canary comparisons.
- buildmap_adapter.py — source-bound read-only evidence manifest.

API sketches:
observe(event, contract_version)->typed feature/evidence reference
propose(event, neighborhood_snapshot)->{memberships, centers, reasons, unknowns}
evaluate_merge(A,B, scientific_contract)->ACCEPT|REJECT|ABSTAIN + evidence
release_ready(group, checkpoint)->immutable downstream job descriptor
compare_exact(baseline, candidate, identity_scope)->eligibility verdict and metrics
recover(receipt, source, contracts)->verified replay or explicit refusal.

State models:
- FeatureContract(version, types, units, axes, missing policy, provenance).
- MetricVersion(normalizer, covariance, weights, calibration window, source hash).
- GroupState(stable ID, family, center version, members, neighborhood, epoch).
- GroupDecision(source IDs, target, action, explanation, hashes, exactness class).
- JobReceipt(run/day, origin events, feature/metric versions, directional keys, checkpoint pointer, output identity).
- ScientificComparison(baseline, candidate, scopes, exact/approx classification, unsupported/unknown counts, savings).

## 4. Delivery phases, dependencies, and acceptance

P0 — Audit/current-state lock: inspect Frankie source, run status, original grouping and all table/receipt contracts; capture grouping provenance and five representative exact groups; classify IDs vs state features vs event-sequence/family inputs. Confirm deployment owner and non-interference boundaries. Deliver frozen inventory, baseline manifests and test fixtures. Exit: reproducible source-bound and run-bound reference metrics, no changes to Search.

P1 — Formal model and schemas: market-condition taxonomy, candidate feature units, causal time direction, compatible families, valid comparison contracts, missingness and precision, stable IDs and input snapshots. Write equations and failure modes. Exit: signed off mathematical contracts and testable type schemas; explicit unknown/non-applicable Neumann status.

P2 — Deterministic standalone core: exact distance, normalization, neighborhood retrieval and verification, kernel, adaptive h, finite Cauchy diagnostic, family-aware center packing, conservative memberships, soft boundaries, deterministic ledger. Exit: property, fuzz, adversarial and benchmark tests; zero data omission or silent mixing; reproducible chunked outcomes.

P3 — Scientific preservation gates: order/member ID kept as attributes; keep real orders, FIFO/age, queue state, causality, 99 planes, raw family modes and directionality. AB/BA, FFT/equivalent transforms/Y reuse only where proven; all conflicting saved results investigated not deleted. Exit: every eliminated calculation has a source-bound proof of exact equivalence or explicit approved approximation; unknown routes untouched.

P4 — Streaming integration and persistence: shadow-read existing tables and immutable ingestion; microbatch group admission, ready-group work queue, separate calculation host eligibility, CPU/memory budgets, atomic partial group receipts, deduped side-effect-safe retries and crash resumes. Exit: interrupted/resumed equals continuous on approved exact paths; no whole-day stage gate; Search untouched; all other 30-day data retained.

P5 — Optional graph/Neumann research submodule: implement only when a scientifically defined domain, u, flux and normal exist. Compare edge-kernel fallback and no-boundary baselines; conservation/stability tests on synthetic PDEs and real-data applicability check. Exit: no false Neumann labeling; robust residual checks or disabled module.

P6 — BuildMap integration: map source producers/consumers, feature transformations, proposed/accepted merges, finite convergence displays, coverage/packing, masked missing cases, detailed workload original/eligible/completed/remaining, cache hits, I/O byte counters, source-bound signed receipts, checkpoint and rollout comparisons. Preserve current free mapping/Guide behavior and avoid extra billing; BuildMap PR #2 pending merge conflicts and acceptance scope must be reconciled. Exit: current source-bound real-project walkthrough and checks, no stale receipt used as acceptance.

P7 — Experiment and performance: compare A current exact workflow, B shadow grouping with no calculation suppression, C safe exact-reuse algorithm, D explicitly opt-in approximate grouping. Same input/day/hardware/thread budgets, warmed cache policy, evidence hashes. Report accuracy/coverage drift, family purity, direction/causal preservation, work eliminated, wall-clock, CPU-hours, RSS, bytes, disk, network, restart costs and budget. Use one-day 20231018 as first representative if retained, then 3 staggered days and 30-day randomized order only with scientifically acceptable results and cost limits. Exit: no unexplained divergence; no scientifically meaningful calculation omitted; measured gains vs cost and regression thresholds.

P8 — Controlled rollout: dark-launch/off by default, opt-in per run/day and family, conservative conservative no-merge fallback, versioned migration/rollback and audit; protect concurrent Search work and all data volumes. Exit: reviewed real-world run, reproducible counters, zero production data loss, stable restart and reversibility. No irreversible deployment/production automation by design document.

P9 — Operational completeness: documentation, architecture decision records, property and integration suite, threat model, deterministic replay, CLI/config docs, deployment/back-out runbook, release notes, explicit owners, budget/scale gates. Verify BuildMap integration separately; Stripe remains out-of-scope and last in its existing roadmap. Exit: every acceptance receipt current, no unsupported claim of physical quantum or infinite convergence.

## 5. Tests and invariants
- Geometry: d(x,x)=0; symmetry and triangle when declared; center spacing and coverage; determinism across chunk sizes and ordering; no unsafe source-ID mixing; low-data abstention.
- Mathematical: distinguish finite Cauchy evidence from true Cauchy theorem; slow drift/oscillation/jumps; adaptive h bounded; conservation and boundary residual if PDE enabled.
- Scientific: preserve event/order IDs, exact raw events, causal clocks, queue/FIFO, member links, family distinctions, directional AB/BA when warranted, zero missing/NaN imputation unless approved. Exact-equivalence comparison via digests and values under declared tolerances/precision.
- Engineering: recover torn checkpoint and conflicting saved products without deletion; idempotent replays; mixed-version refusal; large-scale memory and CPU caps; reproducible indexes; source/data/schema hashes; cancellation and partial completion.
- BuildMap: signed/current observations not treated as proof of scientific correctness; plain-language owner journey, unsupported paths, stale refusal; old app feature regressions; no payments.

## 6. Delivery artifacts & task decomposition
ADR-001 scope and deployment boundaries; ADR-002 features and metrics; ADR-003 soft assignment and packing; ADR-004 finite convergence vs proof; ADR-005 boundary eligibility; ADR-006 equivalence and directionality; ADR-007 checkpoints/work queue; ADR-008 BuildMap evidence; ADR-009 experiments/rollback.
Implementation PRs: contracts/fixtures; core metrics/kernels; convergence/packing; scientific gates; queues/checkpoints; optional graph boundary; BuildMap viewer; experiments; release hardening. Small PRs with input identities, exact acceptance criteria, reversible flags and no broad fixture residue. Do not create synthetic acceptance receipts and pass them off as market evidence.

## 7. Go/no-go decision record
Required before switching: baseline group count source verified, effective unique calculations and pair counts measured; output identity/approx tolerance specified; preserved evidence paths and no missing family/causal/order impacts; CPU/disk/memory budget known; rollout/rollback rehearsed; scientific owner approves results. Neumann component off by default unless PDE justification is documented. A conservative experiment that increases cost or changes distinct market behavior is rejected.

## 8. Next implementation action
Do not assume the Frankie repository is here; first attach or grant an accessible repository/workspace for Frankie. Then run P0 inspection and revise exact filenames and code touchpoints against observed HEAD. This document authorizes planning only, not AWS starts, deletions, changes to Search or production deployment.
