# Geometric Deep Learning front-to-back Frankie / NOVA adjudication — 2026-08-20

Status: **FULL MONOGRAPH AUDIT COMPLETE; RESEARCH CANDIDATES ONLY.** The complete
160-page physical PDF (arXiv:2104.13478), every chapter, figures/tables,
appendices/references, and the six influential pipelines named in the
introduction were reviewed. This document supplements the 340-reference docket;
it does not authorize a Frankie or NOVA architecture change, training, V4, or
paper-manifest promotion.

Primary source: Bronstein et al., [Geometric Deep Learning: Grids, Groups,
Graphs, Geodesics, and Gauges](https://arxiv.org/abs/2104.13478).

## Whole-book conclusion

The book is a representation-design blueprint, not a general theory of
reasoning, memory, continual learning, causal discovery, forecasting, or agent
safety. Its most useful transfer is to make Frankie's transformations, object
types, graph directions, invariances/equivariances, and multiscale views
explicit and testable. Most group-, manifold-, mesh-, gauge-, and E(3)-specific
architectures are not justified for generic language/market reasoning.

For hosted GPT-5.6 Sol, every transfer is external: typed data contracts,
deterministic graph/aggregation services, prompts, and evaluators. For trainable
NOVA, graph/set/sequence adapters are possible, but must beat simple numeric
GRU/LSTM/TCN/Transformer and Deep-Sets baselines at matched compute.

## Chapter-by-chapter audit

| Chapter | Actual subject | Frankie transfer | NOVA transfer | Disposition |
|---|---|---|---|---|
| 1. Introduction | Erlangen-style geometry as symmetry plus scale separation | Freeze transformation contracts before learning; distinguish invariance from equivariance | Candidate data/architecture inductive biases | Strong design principle, not cognition |
| 2. Learning in high dimensions | Curse of dimensionality and task-specific priors | Prefer explicit typed structure over unbounded feature search | Constrain small-model hypothesis class | Background |
| 3. Geometric priors | Domains, groups, local/global structure, invariant/equivariant maps | Test harmless transformations and harmful near-neighbors separately | Data augmentation/equivariant adapters only where the domain supports them | High-value contract discipline |
| 4. Grids and groups | CNNs, translation symmetry, group convolutions | Only for genuinely regular price/time grids; never assume arbitrary time warp or scale invariance | Optional numeric front end | Conditional |
| 5. Graphs | Message passing, permutation symmetry, graph attention, recurrent/set variants | Typed directed evidence/event graphs and immutable provenance paths | Graph/set/sequence sidecar | Strongest architectural transfer, with major limits |
| 6. Geodesics/manifolds/meshes | Intrinsic convolution, spectral/spatial operators, meshes | No natural manifold/mesh has been established for Frankie evidence | Watchlist for a proven geometric numeric domain | Defer |
| 7. Gauges and bundles | Coordinate choices, local frames, gauge equivariance | Useful analogy for representation changes only | No current justified gauge architecture | Defer |

## What should transfer

1. **Transformation contracts.** For every candidate feature, preregister which
   input changes should leave the result invariant, which should transform it
   predictably, and which must change the answer. Test all three.
2. **Typed directed dynamic graphs.** Keep event, evidence, mechanism,
   correction, outcome, and derived-memory nodes distinct; preserve edge
   direction, timestamp, provenance, and authority.
3. **Deep Sets as the edgeless control.** A graph model earns complexity only if
   it beats a permutation-invariant set baseline at equal returned tokens,
   parameters, calls, and latency.
4. **Graph stability pairs.** Couple harmless relabeling/reordering tests with
   adversarial direction, timestamp, polarity, missing-edge, and heterophily
   tests. Generic robustness is not enough.
5. **Scale separation.** Evaluate book-event, causal-second, event-instance,
   session, regime, and cross-regime summaries separately; do not blur them into
   one learned scale.
6. **Algorithmic pre/postconditions.** Learned algorithmic reasoning is a
   proposal; deterministic state, transition, termination, and postcondition
   checks remain authoritative.

## What the book does not justify

- Learned attention or a latent graph is not causal provenance.
- Message passing is bounded by graph expressivity (including 1-WL limits) and
  can over-smooth, fail under heterophily, erase direction, and dilute rare
  evidence on long branching paths.
- A graph neural network does not supply selective forgetting, descendant
  invalidation, calibration, evaluator independence, or rollback.
- LSTM/RNN state is not an auditable long-term memory. It needs reset,
  truncation, contamination, poison, interruption, and replay tests.
- A class-level claim of time-warp stability is not zero-shot invariance and not
  evidence of persistent memory.
- E(3), mesh, group, manifold, and gauge architectures should not be imported
  without a real domain action and a matched non-geometric baseline.
- Neural Relational Inference may learn association/interaction structure; it
  must not be labeled causal discovery.

## Required graph/sequence gates

Any graph candidate must test:

- isomorphic relabeling and input-order invariance;
- reversed edge, delayed timestamp, wrong polarity, dropped critical edge, and
  spurious-hub sensitivity;
- 1-WL-indistinguishable controls;
- increasing depth/branching and over-smoothing;
- homophily versus heterophily;
- active versus invalidated/descendant-withdrawn memory nodes;
- evidence-path citation accuracy and no latent-edge causal claims;
- Deep Sets, linear, GRU/LSTM, TCN, and Transformer baselines at matched compute.

The first eligible experiment is a no-authority typed-graph view plus an
edgeless control, not a learned graph policy. No candidate may rewrite raw
evidence, timestamps, outcomes, permissions, or canonical memory.

## Six introduction citations

The introduction explicitly names six influential pipelines that the book does
not review in depth. Each was independently audited rather than inherited from
the book's brief citation.

### Variational Autoencoders — Kingma and Welling (2013/2014)

VAEs optimize an evidence lower bound using reparameterized variational
inference. The strongest Frankie transfer is an external probabilistic
belief/memory sidecar with explicit uncertainty—not free-form memory. The ELBO
gap, posterior collapse, likelihood/calibration mismatch, OOD behavior, and
latent non-identifiability remain. For NOVA, a small latent adapter is a
trainable candidate only after deterministic and flow-based controls.

### Generative Adversarial Networks — Goodfellow et al. (2014)

GANs train a generator against a discriminator. Frankie should use the idea only
for adversarial case generation: hard provenance, temporal-leakage, poisoning,
and rare-tail tests. Minimax instability, mode collapse, discriminator overfit,
and lack of calibrated likelihood make GANs unsuitable as Frankie's belief or
memory system. NOVA may use adversarial examples, not an unvalidated GAN core.

### Normalizing Flows — Rezende and Mohamed (2015)

Flows provide exact change-of-variables likelihood through invertible maps.
They are the strongest of the six for a separately calibrated density/belief
sidecar, but topology restrictions, computational cost, and the known failure of
high likelihood to imply in-distribution membership require explicit OOD and
calibration gates. This is external for Sol and optional for trainable NOVA.

### Deep Q-Networks — Mnih et al. (2015)

DQN combines replay, a target network, and approximate Q-learning for Atari.
Its transfer is limited to a small external router/tool policy with a frozen
action set and offline counterfactual evaluation. It does not improve Sol's
weights, reasoning, or memory; live market exploration is forbidden. Double-DQN
and later ALE protocol work narrow the original overestimation and evaluation
claims. NOVA may test a Q-head only if a valid sequential environment exists.

### Proximal Policy Optimization — Schulman et al. (2017)

PPO uses a clipped surrogate to limit policy-update size, but the clipping term
is not a general safety or monotonic-improvement guarantee. Implementation
details and reward quality dominate results. It is irrelevant to immutable Sol
weights and conditional for NOVA post-training only after a trustworthy reward,
offline policy evaluation, and no-live-exploration contract. Direct preference
optimization is a required simpler control where applicable.

### Deep InfoMax — Hjelm et al. (2019)

Deep InfoMax uses contrastive objectives to encourage global/local
representation agreement. It is a candidate retrieval/memory representation
loss, not a guaranteed mutual-information estimator and not a causal-memory
system. Negative sampling, shortcut features, false negatives, and representation
collapse must be tested. External retrieval is the only Sol transfer; NOVA may
train an encoder challenger.

## Priority after the full audit

Keep only three near-term candidates:

1. transformation/invariance contracts;
2. typed directed graph views with Deep-Sets and simple sequence controls;
3. a separately calibrated VAE/flow belief sidecar experiment.

GANs remain test generation; DQN/PPO remain external routing/post-training
watchlist items; Deep InfoMax remains a retrieval-loss challenger. None is a
validated Frankie upgrade, and none authorizes V4.
