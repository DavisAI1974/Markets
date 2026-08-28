# Spec: BOSS state serialization

Status: **ACCEPTED FOR PLAN/TDD**

Date: 2026-08-28

Module id: `boss-state-serialization`

Repository: `DavisAI1974/Markets`

Branch: `codex/frankie-boss-sol-replacement-20260824`

Governing lifecycle: `addyosmani/agent-skills` release `0.6.7`, `spec-driven-development` after brownfield context characterization.

## Accepted human decisions

Accepted on 2026-08-28 under the user's explicit `Proceed` instruction:

1. Canonical JSON is the sole authoritative first representation. No second prose rendering in this tranche.
2. The typed snapshot requires an existing `CausalPacket` identity plus separately supplied typed sequence/graph/QSV state. `CausalPacket` alone is not represented as the full trunk state.
3. No real Step-1 sample is selected yet. Mechanical serializer tests use synthetic/fixture state; the smallest frozen representative Step-1 sample is selected only in a later semantic-validation tranche.

## Assumptions being surfaced

1. This tranche tests the interface representation only. It does not invoke Granite or any provider model.
2. The serializer is additive and lives outside the existing `Trunk`, `CausalPacket`, BLD-1, Frankie core/provider seam, and ReFRAG governance.
3. The first serializer is deterministic schema-native text, not a learned projection into an LLM embedding space.
4. Mechanical tests may use synthetic/fixture typed state and do not require a new Step-1 run.
5. Real Step-1-derived examples enter only in a later semantic-validation tranche after this contract is proven mechanically.
6. The serializer must bind to existing causal/provenance identities but must not claim that `CausalPacket` alone is the entire tensor state consumed by BOSS.
7. The current executable graph behavior is one `TemporalGraphBranch` module applied once before the fixed-depth layer loop. This tranche records graph structure; it does not change graph execution.
8. No outcome label, future information, Frankie result, or post-`as_of` evidence may appear in serialized input.

## Objective

Create a deterministic, versioned, testable textual representation of a declared BOSS reasoning-state snapshot so that a future text reasoner can receive market state without ad-hoc prose.

The output is an **experimental interface artifact**, not a public Frankie contract and not a substitute for BOSS tensors.

Success means we can prove what information the serializer preserves, what it intentionally excludes, and when a serializer failure must be distinguished from a downstream reasoning-model failure.

## Non-objectives

This tranche does not:

- download or invoke Granite,
- implement recurrent-depth BOSS reasoning,
- implement adaptive halting,
- train or distill BOSS,
- alter Step-1 or V4,
- alter causal packet construction,
- create the missing production packet-to-tensor/data seam,
- alter BOSS trunk weights or architecture,
- alter QSV registry/governance,
- alter the one graph branch,
- alter BLD-1,
- expose additional internal heads to Frankie,
- launch Frankie/provider/production,
- claim market-semantic usefulness.

## Tech stack

- Python 3.11-compatible source
- Python standard library preferred for serialization/parsing/hashing
- Existing BOSS types and ReFRAG QSV registry are read-only authorities
- `pytest` for focused tests, following existing `research/kalshi/frankie_boss/tests/` conventions
- No new runtime dependency in this tranche

## Proposed files

New only:

- `research/kalshi/frankie_boss/state_serialization.py`
- `research/kalshi/frankie_boss/tests/test_state_serialization.py`

Documentation/lifecycle updates after behavior is proven:

- this spec,
- `tasks/plan.md`,
- `tasks/todo.md`,
- relevant dated provenance/handoff record.

Existing executable files are not modified merely to support the serializer.

## Commands

Focused RED/GREEN command in an environment with the existing BOSS test dependencies:

```bash
python -m pytest research/kalshi/frankie_boss/tests/test_state_serialization.py -q
```

Focused preservation checks after the new tests pass:

```bash
python -m pytest \
  research/kalshi/frankie_boss/tests/test_causal_packet.py \
  research/kalshi/frankie_boss/tests/test_trunk.py \
  research/kalshi/frankie_boss/tests/test_seam.py \
  research/kalshi/frankie_boss/tests/test_state_serialization.py -q
```

Exact broader preservation commands must follow the governing handoff/environment available at implementation time. Historical `101`, `74`, or `160 passed` receipts are not represented as rerun until actually executed again.

## Typed input boundary

The serializer must consume one explicit immutable snapshot type owned by the new module. It must not accept an untyped arbitrary `dict` as the public entry point.

The snapshot must have explicit sections for at least:

### Identity/provenance

- serializer schema/version,
- source packet hash or causal-state identity,
- entity,
- `as_of`,
- relevant code/feature/model/calibrator version identities when supplied by the source boundary,
- degraded/defect state.

### Sequence fields

The declared time-ordered rows needed for the reasoning experiment, with:

- stable row index,
- explicit time/causal availability fields supplied to the snapshot,
- named numeric fields + units,
- named categorical fields + decoded labels or declared ids plus registry identity,
- venue identity,
- instrument identity,
- masks/presence.

The serializer must not invent semantic names for anonymous tensor columns. If the upstream experiment cannot provide an authoritative registry for a column, that column cannot silently receive a guessed name.

### Graph structure

- row/node index,
- parent index or explicit root marker,
- enough information to reconstruct the same declared parent relation from the serialized artifact.

The serializer records graph structure; it does not execute graph message passing.

### QSV/OD state

When QSV is present:

- registry identity,
- exact ordered `QSV_FEATURE_REGISTRY` names,
- values,
- availability mask.

When QSV is absent or masked, absence must be explicit. Missing must not be rendered as numeric zero unless zero is the actual present value.

## Output format

The initial output is deterministic machine-parseable canonical JSON rather than prose.

Rationale:

- Granite/text models can consume JSON text,
- round-trip/mechanical preservation can be tested exactly,
- stable ordering can be enforced,
- field ablation can preserve schema shape,
- provenance/hash binding can be explicit,
- a null result is less confounded by hidden natural-language summarization choices.

Human-friendly prompt prose, if later useful, belongs in a separate formatting layer and cannot replace the canonical artifact in provenance.

## Determinism contract

For the same immutable snapshot and serializer version:

- output bytes must be identical,
- output SHA-256 must be identical,
- mapping input insertion order must not change output,
- equivalent float representation must follow one declared canonical policy,
- no randomization or sampling is permitted.

The serializer's canonicalization policy must either reuse an existing authoritative BOSS canonical primitive where semantically correct or define its own explicitly versioned policy. It may not silently depend on incidental `repr()`/dictionary order behavior.

## Round-trip / preservation contract

The canonical serialized artifact must be parseable back into an equivalent declared snapshot representation for every field the serializer claims to preserve.

Round-trip equality is semantic/typed equality under the serializer's declared canonical float policy, not a claim that PyTorch tensor storage bytes or hidden states are recreated.

Required preserved relationships include:

- row ordering,
- parent/root graph relation,
- named numeric values and units,
- categorical/venue/instrument identity representation,
- QSV name/value order,
- QSV presence mask,
- `as_of`/causal identity,
- defects/degraded state,
- provenance/hash identities included in the snapshot.

## Explicit leakage boundary

Tests must prove that the serializer cannot include fields outside the declared snapshot schema.

No serializer API may accept an unrestricted `extra` payload that can smuggle:

- future rows,
- outcome labels,
- realized post-`as_of` returns,
- Frankie decisions,
- holdout results,
- hidden answer keys.

Unknown fields must fail closed or be excluded by construction through typed input. Silent passthrough is forbidden.

## Market-field ablation contract

The serializer must support creation of a controlled **market-ablated view** without changing schema shape/ordering.

The ablation policy must be explicit and versioned. It must distinguish:

- `present real value`,
- `intentionally ablated`,
- `source missing/masked`.

The initial implementation need only provide the mechanism and test semantics. The exact field set to ablate for Granite experiments is a later experiment definition, not hardcoded into this generic serializer.

## Mechanical probe readiness

This tranche does not call Granite, but the output must make later objective probes possible, such as:

- recover a parent relationship,
- identify which QSV feature occupies a named position,
- distinguish present-zero from missing/ablated,
- compare two explicitly named numeric fields,
- identify a declared defect,
- identify which rows were available by the snapshot's `as_of` identity.

Passing serializer tests is necessary but not sufficient evidence that Granite can reason over the representation.

## Testing strategy

Follow TDD. The first implementation tranche begins with RED tests.

Minimum test categories:

1. **Determinism**
   - same snapshot -> byte-identical output,
   - insertion order does not change output,
   - serializer version participates in identity.

2. **Round-trip**
   - canonical text parses to equivalent declared snapshot,
   - graph roots/parents preserved,
   - QSV names/order/mask preserved,
   - present zero differs from absent/ablated.

3. **Fail closed**
   - unknown/untyped fields cannot pass through,
   - non-finite present numeric values handled by explicit policy rather than accidental JSON behavior,
   - malformed parent references rejected,
   - mismatched QSV registry width/order rejected.

4. **Ablation**
   - market-ablated output retains identical schema/ordering,
   - ablated values are marked as ablated, not missing and not zero,
   - non-ablated fields remain identical.

5. **Provenance binding**
   - source causal identity/hash is preserved,
   - a real source-state change moves serialized identity,
   - formatting-only mapping order does not.

6. **Preservation**
   - existing BOSS causal/trunk/seam tests remain unchanged and pass.

## Code style

Prefer small immutable dataclasses/typed enums and pure functions.

Illustrative style only:

```python
@dataclass(frozen=True, slots=True)
class SerializedState:
    schema_version: str
    source_state_hash: str
    body: str

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.body.encode("utf-8")).hexdigest()
```

Do not introduce a generic framework, prompt-template engine, plugin abstraction, model client, or provider dependency in this tranche.

## Boundaries

### Always

- preserve exact causal chronology,
- use named registries where authority exists,
- fail closed on malformed structure,
- keep serialization deterministic and versioned,
- keep source/provenance identity visible,
- test before implementation,
- preserve existing BOSS tests and frozen seams.

### Ask first / separate spec required

- choosing the actual Granite prompt wrapper,
- downloading/model-serving Granite,
- adding a learned embedding adapter,
- changing BOSS typed inputs,
- changing the temporal graph frequency or semantics,
- introducing recurrent-depth reasoning,
- adding adaptive halting,
- choosing market fields for Granite-specific ablation,
- using real Step-1-derived result-bearing data,
- adding dependencies.

### Never in this tranche

- modify `spawn.py`, Frankie core/provider files, or the 1,940/46 capability surface,
- modify Step-1/V4 science,
- alter ReFRAG QSV governance,
- alter the BLD-1 mapping,
- expose internal BOSS heads publicly,
- serialize future/outcome/answer data,
- call a provider/model,
- launch Frankie or production.

## Success criteria

This capability is complete only when:

1. The serializer has a single explicit typed input snapshot contract.
2. Canonical text is deterministic and versioned.
3. Claimed state fields round-trip exactly under the declared canonical policy.
4. Graph parent/root structure round-trips.
5. QSV registry names/order/masks round-trip when enabled.
6. Present zero, missing, and intentional ablation are mechanically distinguishable.
7. Unknown/untyped fields cannot silently pass through.
8. Source causal/provenance identity is bound into the artifact.
9. Market-field ablation preserves schema shape/order and changes only declared value-state markers.
10. Focused serializer tests pass.
11. Existing causal/trunk/seam preservation tests pass unchanged.
12. No Granite/provider/Step-1/Frankie call occurs.
13. Provenance records RED/GREEN receipts, exact code SHA, and any KILL/null finding.

## Deferred question

For later real-data semantic validation, select the smallest frozen Step-1-derived sample that is representative enough to test serializer/teacher semantics. This is deliberately deferred and is not required for mechanical serializer tests.
