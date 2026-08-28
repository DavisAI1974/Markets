# Frankie BOSS Granite 4.2 research candidate

Date: 2026-08-28

Status: **UNADOPTED RESEARCH CANDIDATE**

Repository: `DavisAI1974/Markets`

Branch: `codex/frankie-boss-sol-replacement-20260824`

This record preserves a possible BOSS enhancement for later falsifiable testing. It is not an implementation directive and does not authorize model download, Granite invocation, BOSS modification, Step-1 compute, Frankie/provider calls, training, promotion, or production use.

## Motivation

Full-MBO Step-1 reconstruction is expensive enough that a five-year census is operationally impractical. The research question is therefore not whether Granite can replace missing MBO evidence; it cannot. The question is whether a pretrained reasoning model can improve BOSS **sample efficiency**, allowing BOSS to extract more useful reasoning behavior from a substantially smaller high-fidelity MBO corpus.

The scarce resource is expensive full-MBO-derived training data. The target outcome is a reduction in the amount of that data needed to reach a predeclared held-out performance level.

## External source facts verified 2026-08-28

Primary/near-primary sources:

- IBM Granite docs: `https://www.ibm.com/granite/docs/models/granite4-2`
- IBM Granite 4.2 8B model card: `https://huggingface.co/ibm-granite/granite-4.2-8b`
- IBM Granite technical walkthrough on Hugging Face: `https://huggingface.co/blog/ibm-granite/granite-4-2`
- IBM Research introduction: `https://research.ibm.com/blog/introducing-granite-4-2`

Facts relevant to this candidate:

- Granite 4.2 is a dense decoder-only reasoning-model family in 3B, 8B, and 30B sizes.
- The family was pretrained from scratch on roughly 15T tokens, then SFT'd on reasoning/chain-of-thought and agentic-trajectory data, then post-trained through a multi-stage RL pipeline.
- RL stages are separate warm-started runs using GRPO-style training.
- The 8B and 30B models, but not the 3B, receive the additional agentic RL block covering software engineering, terminal use, and search in real environments.
- Thinking, non-thinking, and low-effort thinking modes are supported.
- The models are Apache 2.0 licensed.
- 8B is the smallest size receiving the agentic RL stages and is therefore the initial teacher candidate if the experiment reaches model invocation.

External model facts are not BOSS architecture authority and must be reverified against exact model-card/version identities before any result-bearing experiment.

## Candidate role

Granite is **not** proposed to replace:

- Step-1 MBO/V4 reconstruction,
- the BOSS typed encoder,
- the one shared temporal graph branch,
- gated-delta temporal memory,
- QSV/ReFRAG governance,
- BLD-1,
- Frankie's core/provider seam,
- or the existing dipole teacher experiment.

Possible later role:

- frozen shadow reasoning control,
- frozen structured reasoning teacher/critic,
- research input for adaptive-compute/effort experiments.

The intended leverage is to transfer generic reasoning behavior while reserving expensive MBO data for market-specific structure that only the market data can supply.

## Arch-master objections promoted to required gates

The following objections are mandatory experiment-design gates, not optional suggestions.

### Gate 1: serialization is its own experiment

Granite consumes text tokens. BOSS authority is typed numeric/categorical state, ancestry graph structure, QSV/OD geometry, masks, chronology, and provenance.

A BOSS-to-Granite representation must therefore be separately specified and validated before Granite reasoning quality is interpreted.

A null Granite result must distinguish:

- `reasoning prior did not transfer`

from

- `serializer discarded or obscured the information needed to reason`.

Initial preference is a deterministic schema-native textual rendering rather than a learned projection into Granite embedding space, because a learned projection adds another trainable system and another data requirement. This is a preference to test, not an approved interface.

Required serializer properties before teacher evaluation:

- stable deterministic ordering,
- explicit field names and units,
- explicit causal timing,
- explicit masks/presence,
- explicit ancestry/graph relationships,
- named QSV features rather than anonymous width-only vectors,
- provenance/hash binding,
- no outcome-label leakage,
- mechanical round-trip or equivalence checks for the information claimed to be preserved,
- verifiable probe tasks proving Granite can recover mechanically encoded relationships before subjective reasoning labels are trusted.

### Gate 2: validate teacher labels before distillation

Do not spend BOSS training compute merely to discover that Granite process labels are uninformative.

Before distillation, test Granite's proposed process targets directly against held-out market reality where an objective relationship is available.

For abstention/uncertainty in particular, examine selective-prediction behavior rather than accepting prose confidence:

- does higher Granite uncertainty/abstention score associate with larger held-out realized error?
- as low-confidence cases are removed, does risk decrease as coverage decreases?
- is the signal stable across time-disjoint periods/regimes?

A failed teacher-validity pre-check is a clean negative and stops that target from entering distillation.

### Gate 3: order targets by plausible transferability

Granite's strongest agentic RL environments have externally checkable success conditions. NG microstructure contains irreducible aleatoric uncertainty where `reason longer` does not imply `become certain`.

Initial target order should therefore prioritize:

1. contradiction detection,
2. evidence conflict/consistency,
3. structured evidence selection,
4. competing-hypothesis comparison,
5. missing-evidence identification,

before attempting:

- compute halting,
- market abstention,
- uncertainty calibration.

Halting/abstention transfer is specifically considered higher-risk until empirically validated.

### Gate 4: native adaptive-depth control is mandatory

Any future Granite-assisted recurrence experiment must include an equivalent native BOSS adaptive-depth arm trained without Granite.

The recurrence architecture and halting mechanism should be held constant between native and Granite-supervised arms wherever possible. The experimental variable should be supervision, not a simultaneously changed mechanism.

Minimum conceptual arms once recurrence exists:

- fixed-depth BOSS baseline,
- native recurrent/adaptive-depth BOSS,
- same recurrent BOSS with Granite supervision,
- same with shuffled Granite labels,
- same with Granite labels generated from market-specific-field-ablated state.

If native adaptive depth matches Granite-assisted adaptive depth, the finding is that the mechanism helped and Granite transfer did not add measurable value.

### Gate 5: shuffled Granite control

Teacher labels must be shuffled across examples while preserving their marginal distribution. If shuffled supervision performs similarly to aligned Granite supervision, the apparent benefit is not evidence that Granite understood the BOSS state.

### Gate 6: market-specific-field-ablation control

Regenerate Granite teacher labels from a serializer input with market-specific information removed while preserving prompt/schema shape and formatting as closely as possible.

This control is distinct from shuffling. It tests whether Granite is using the market state versus providing generic auxiliary regularization or generic reasoning scaffolding.

Proxy leakage must be checked: removing a named market field while leaving a derived field that encodes the same quantity does not constitute a valid ablation.

### Gate 7: measure sample-efficiency shift directly

The primary result is not merely `best score with Granite`.

Pre-register a held-out performance target and estimate the amount of expensive MBO-derived training data each arm requires to reach it.

Training rungs should be nested. Validation/test data must remain time-disjoint and untouched by all training rungs. Training rungs should be constructed from predeclared calendar blocks so a small rung is not accidentally equivalent to one particular regime.

Use multiple seeds and estimate uncertainty on the horizontal learning-curve shift.

A useful result would look like:

`Granite-assisted BOSS reaches target performance with materially less high-fidelity MBO data than native BOSS, with confidence intervals excluding no meaningful shift.`

A maximum-score improvement without a runway reduction is secondary for the present operational problem.

## Relationship to the existing dipole teacher experiment

Do not fold Granite into `teacher.py`'s existing OD/dipole experiment merely as another arm.

That harness asks a different question: whether market-operator/dipole geometry contributes useful intermediate supervision beyond multiple generic controls.

Granite reasoning transfer is a separate hypothesis and requires a separate experiment family. Preserve the existing `none`, `plain_aux`, `shuffled`, `random`, `dipole` controls and their KILL semantics unchanged.

## Relationship to BOSS reasoning-depth work

The current BOSS trunk is a fixed-depth baseline. `GatedDeltaCell` recurrence is temporal memory across sequence time, not whole-representation reasoning-depth recurrence.

A future recurrent-depth mechanism must first prove itself against the untouched fixed-depth baseline. Granite cannot be used to smuggle recurrent/adaptive behavior into the baseline.

Granite's thinking/non-thinking/low-effort modes are useful conceptual research evidence for variable compute allocation, but they do not define BOSS's recurrence or halting mechanism.

## Step-1 dependency

No new Step-1 run is required for:

- BOSS brownfield architecture characterization,
- serializer mechanical tests using synthetic/fixture states,
- deterministic ordering/round-trip/hash tests,
- market-field-ablation mechanics.

A small frozen representative Step-1-derived sample becomes necessary later for market-semantic serializer probes and Granite teacher-validity tests.

Do not authorize another broad Step-1 census simply to investigate Granite.

## Stop/KILL rules

Preserve all positive, negative, null, contradictory, and KILL outcomes.

Stop a proposed Granite target or branch when its prerequisite fails. Examples:

- serializer cannot demonstrably preserve/recover required state -> stop Granite reasoning claim; fix or reject serializer first,
- Granite fails mechanical state probes -> do not distill higher-level labels,
- proposed teacher label has no held-out validity -> KILL that teacher target,
- shuffled or market-ablated controls match aligned Granite -> no Granite-specific transfer claim,
- native adaptive-depth control matches Granite-assisted arm -> retain adaptive mechanism finding, reject Granite-specific credit,
- sample-efficiency confidence interval does not show a meaningful horizontal shift -> no training-runway reduction claim.

A KILL is a scientific result, not a failure to be removed from provenance.

## Next allowed action

Finish the BOSS brownfield context/architecture inventory and adversarial review. Only after the existing architecture is characterized should a small feature specification be written for the first testable interface/experiment tranche.
