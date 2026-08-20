# Frankie GDL bibliography evaluation docket — 2026-08-20

Status: **CANDIDATE EVALUATION ONLY.** Nothing in this docket is integrated
into permanent Frankie or added to `frankie_paper_manifest.json` merely because
it appears here.

## Scope and accounting

The complete bibliography in Bronstein et al., [*Geometric Deep Learning:
Grids, Groups, Graphs, Geodesics, and Gauges*](https://arxiv.org/abs/2104.13478)
was screened against the current Frankie and NG Exhaustion V4 contracts.

The authoritative bibliography contains **340 references**. An initial PDF-text
split produced 339 records because GDL-116 (Helvétius, 1759) was merged with the
following Hjelm et al. paper. That extraction was repaired before this docket
was written. The PlotNeuralNet Zenodo URL was also restored to its owning
citation. All GDL identifiers below use the corrected 340-entry ordering.

Disposition:

- 10 references support five near-term candidate experiments;
- 20 references remain on a background watchlist;
- 310 references are deferred for the current Frankie/V4 problem.

Deferred means no present experiment priority, not disproven or permanently
irrelevant.

## Evaluation order

### 1. Causal graph-stability audit

Sources:

- GDL-090 — Gama, Bruna, and Ribeiro, [*Stability Properties of Graph Neural
  Networks*](https://arxiv.org/abs/1905.04497), IEEE TSP 2020.
- GDL-140 — Kenlay, Thanou, and Dong, [*Interpretable Stability Bounds for
  Spectral Graph Filters*](https://arxiv.org/abs/2102.09587), 2021.
- GDL-160 — Levie, Isufi, and Kutyniok, [*On the Transferability of Spectral
  Graph Filters*](https://arxiv.org/abs/1901.10524), 2019.

Hypothesis: a useful causal representation changes smoothly under small lawful
topology, timestamp, book, and flow perturbations while remaining sensitive to
real discontinuities.

First test: replay identical OOT causal movies with discovery-frozen price
translations, delayed-only timestamp jitter, lawful book-level dropout, and
small flow/book perturbations. Report probability displacement, first-lock
flips, wrong locks, no-locks, latency shift, and calibration by stage and head.

Boundary: no perturbation may move information earlier, use future topology or
target truth, or smooth away a genuine discontinuity.

### 2. Event-time dynamic-graph lane

Sources:

- GDL-238 — Rossi et al., [*Temporal Graph Networks for Deep Learning on
  Dynamic Graphs*](https://arxiv.org/abs/2006.10637), 2020.
- GDL-322 — Xu et al., [*Inductive Representation Learning on Temporal
  Graphs*](https://arxiv.org/abs/2002.07962), 2020.

Hypothesis: timed-event memory can retain irregular price, flow, book, dipole,
and predecessor interactions better than independent snapshots, especially
before target birth.

First test: run TGN and TGAT as separate frozen/adaptive lanes with exactly the
same causally available raw/V3/V4 inputs as the existing candidate. Compare
prebirth log loss, Brier score, selective coverage at matched wrong-lock risk,
decision latency, and chronological block/week stability.

Boundary: every sampled event and edge must satisfy `event_time <= cutoff`.
There is no target node or target-derived edge before causal confirmation.
PRIOR-resolved instances never enter T0/H fallback.

### 3. Deterministic graph-signal features

Sources:

- GDL-244 — Sandryhaila and Moura, [*Discrete Signal Processing on
  Graphs*](https://arxiv.org/abs/1210.4752), IEEE TSP 2013.
- GDL-263 — Shuman et al., [*The Emerging Field of Signal Processing on
  Graphs*](https://arxiv.org/abs/1211.0053), IEEE SPM 2013.

Hypothesis: causal low/high graph-frequency energy distinguishes coherent
price/flow/book movement from divergence and adds a compact description of
dipole and exhaustion structure.

First test: use a fixed semantic adjacency, or one learned only on discovery,
and compute filter-band energies independently at each causal cutoff. Compare
raw+V3+V4 with the same lane plus graph-signal features across chronological
blocks.

Boundary: adjacency, normalization, eigenvectors, and scaling may not be fit on
a full instance or the OOT population. Future correlations cannot create an
earlier edge.

### 4. Causal invariance regularization

Source: GDL-189 — Mitrovic et al., [*Representation Learning via Invariant
Causal Mechanisms*](https://arxiv.org/abs/2010.07922), 2020.

Hypothesis: consistency under valid discovery-frozen transformations improves
robustness across price levels, event density, and small lawful timing changes.

First test: compare the existing encoder with an equal-budget
invariance-regularized candidate on OOT calibration, prebirth coverage, wrong
locks, latency, and transformation consistency.

Boundary: sign reversal is normally equivariance, not unconditional invariance.
Transformations may not depend on the realized label or future path.

### 5. Size/regime extrapolation diagnostic

Sources:

- GDL-032 — Bevilacqua, Zhou, and Ribeiro, [*Size-Invariant Graph
  Representations for Graph Classification
  Extrapolations*](https://arxiv.org/abs/2103.05045), 2021.
- GDL-325 — Xu et al., [*How Neural Networks Extrapolate: From Feedforward to
  Graph Neural Networks*](https://arxiv.org/abs/2009.11848), 2020.

Hypothesis: pooled representations degrade when causal graph size, ancestry
length, event density, or regime differs from discovery.

First test: stratify OOT results by causal node/event count, ancestry length,
session, and chronological regime; compare current pooling with size-normalized
representations. Keep any cross-stage transfer a separately named ablation.

Boundary: causal graph size may not become an indirect target-head identifier
or encode future final depth. D4/D5 remain preserved cases, not population
validation.

## Background watchlist

- Learned relation/topology: GDL-083, GDL-139, GDL-144.
- Long-range memory: GDL-004, GDL-162, GDL-246, GDL-279.
- Attention architectures: GDL-075, GDL-079, GDL-298.
- Expressivity and ordering: GDL-041, GDL-111, GDL-274.
- Spectral/self-supervised representation: GDL-089, GDL-277, GDL-339.
- Reasoning/domain lineage: GDL-025, GDL-048, GDL-315, GDL-336.

These wait until simpler geometric candidates show incremental value. Learned
topology and contrastive pairs are particularly dangerous because full-path or
label-aware construction would leak future state. GDL-315 is historically
interesting because it used a natural-gas market model, but it does not validate
modern causal order-book exhaustion prediction.

## Common promotion gate

No candidate may enter permanent Frankie or the canonical paper manifest unless
it:

1. passes forbidden-field, availability-time, and target-derived-edge audits;
2. improves prebirth performance on chronological OOT evidence;
3. preserves the one-lock rule and excludes PRIOR-resolved cases from H fallback;
4. improves a preregistered metric vector, not one favorable aggregate;
5. preserves calibration, wrong-lock risk, latency, and D0-D3 retention
   tolerances;
6. treats D4/D5 as cases rather than population proof; and
7. is independently reversible without mutating protected Frankie state.

## Why most references are deferred

The remaining papers are dominated by molecular, medical, mesh, 3D, traffic,
recommendation, and physical-system demonstrations; differential-geometry and
group-theory foundations; generic architecture/training work already represented
by current baselines; and high-capacity graph methods disproportionate to the
small D-chain graphs. Their domain analogies do not by themselves create a
falsifiable causal-market experiment.
