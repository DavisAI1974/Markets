# Frankie BOSS — Granite structured-output architecture plan

Identifier: `BOSS_GRANITE_STRUCTURED_OUTPUT_PLAN_V1`
Date: 2026-09-07
Base: `beb548b86b777dc69bf834950b30cc28000e16ef`
Reference recipe: Hugging Face blog "Fine-tuning a 350M Model for Better Structured Outputs in 100 GRPO Steps" (LFM2.5-350M, TRL GRPO, IFStruct, 2026-09-03). Adapted here to Granite 4.2 8B with LoRA.

## 0. Boundary

Additive only. Frankie inputs, calculations, planes, Memory A, adapters, and replay are untouched. Granite is shadow-only: nothing here can change a Frankie output. The only Frankie-adjacent artifact this plan produces is a pinned Granite checkpoint identity for the B2 shadow lane.

Standing assumption per owner: Granite is promoted to the B2 shadow lane. A fine-tuned Granite is a new pinned identity (G16), not a violation of "frozen." A second open-weight model may be added alongside Granite later; sections 1 and 2 are model-agnostic so it plugs into the same schema and reward with no schema change.

## 1. C23 output schema: `BOSS_GRANITE_OUTPUT_SCHEMA_V1`

This is built first because the parser is the GRPO reward. Fields, all required, no additional keys allowed:

```
{
  "schema_version": "BOSS_GRANITE_OUTPUT_SCHEMA_V1",
  "snapshot_hash": "<64-hex, must equal SerializedState.hash of the prompt>",
  "evidence_refs": [ {"row": <int>, "field": "<name>"} , ... ],      # 0..16 entries; row/field must exist in the snapshot
  "contradictions": [ {"a": <ref>, "b": <ref>, "note": "<<=200 chars>"} ],   # 0..8
  "missing_evidence": [ "<<=120 chars>" ],                            # 0..8
  "hypotheses": [ {"label": "<<=40 chars>", "support": [<ref>...], "against": [<ref>...]} ],  # 1..4
  "disposition": "CONSISTENT" | "CONFLICTED" | "INSUFFICIENT"        # bounded, no side/size/price
}
```

Rules:
- `snapshot_hash` echo is the answer-wall check: an output that names a different snapshot is rejected regardless of content.
- Every `ref` must resolve to a row index and field name present in the serialized state. Unresolvable refs reject the output.
- `disposition` is a three-value enum describing evidence quality only. It is never a trade direction and never maps to BLD-1 `disposition`; the name collision is intentional to force the parser to keep them apart (C23 never emits a BLD-1 field).
- No free text outside `note`, `missing_evidence` strings, and `label`, all length-capped.
- Thinking mode: Granite thinking tokens, if enabled, are stripped before parsing; only the final JSON block is scored. Whether thinking is on is part of the pinned identity (G16), not a per-call choice.

Target order follows the Granite candidate doc: contradiction detection, evidence consistency, structured evidence selection, hypothesis comparison, missing evidence. Halting, abstention, and calibration are not in the schema.

## 2. Parser as reward: `granite_parser.py`

One module, used unchanged at training time (reward) and at runtime (acceptance). Any drift between them is a defect by definition.

`score(output_text, snapshot) -> (reward: float, verdict: Verdict)` with a fixed ladder:

| Level | Condition | Reward |
|---|---|---|
| L0 | not JSON, or JSON not an object | 0.00 |
| L1 | JSON object but wrong key set (missing or extra keys) | 0.20 |
| L2 | correct keys, wrong types/lengths/enums | 0.40 |
| L3 | schema-valid but `snapshot_hash` mismatch or any unresolvable ref | 0.60 |
| L4 | fully valid | 1.00 |

Runtime acceptance is L4 only. Levels below L4 exist for GRPO shaping so the policy gets gradient before it ever reaches full validity, exactly as the reference recipe partial-credits format compliance. Rewards are deterministic; no LLM judge.

Non-goals in the reward: content quality is NOT rewarded. Rewarding it would need a judge and would drift the model toward pleasing the judge. Content is checked in section 5 as a guard, not trained.

## 3. Training data: prompts from real serialized states

- Source: `state_serialization.serialize_state()` over snapshots built from the Oct 1 mechanics scope (PROBE_ONLY). About 500 prompts, matching the reference recipe. No held-out day enters.
- Prompt = fixed system instruction (schema text, rules from section 1) + serialized state JSON. The system instruction is versioned and its hash is part of the pinned identity.
- Half the prompts additionally use `ablate_market_fields()` renderings. This keeps the policy learning the format rather than memorizing NG-specific values, and reuses the existing ablation helper.
- No targets, labels, outcomes, or Frankie outputs appear in any prompt (answer wall). A prompt-builder test asserts the prompt text contains no key from the BLD-1 field set.

## 4. GRPO run

- Model: Granite 4.2 8B, LoRA (r=16, alpha=32, attention and MLP projections), bf16, TRL `GRPOTrainer`.
- Group size 8 generations per prompt, 100 to 200 steps, batch of 4 prompts, learning rate 1e-5 on LoRA params, KL beta 0.04 to the base model (prevents collapse into template-only outputs). Sampling during training: temperature 0.8.
- Compute: one 48 GB GPU (L40S/A6000 class) for roughly one to two hours, or an AWS `g6e.xlarge`. Not free-tier; the 350M recipe scales in size but not in method.
- Reward = section 2 score only. Optional length penalty: reward minus 0.05 if output exceeds 1,200 tokens, to stop padding.
- Seeds, config, TRL and transformers versions, base checkpoint SHA, tokenizer SHA, and quantization are recorded in `GraniteTuneReceipt`.

## 5. Pass/fail (quick, no A/B)

Held-out set: 200 serialized states from Oct 1 not used in training (time-disjoint within the day).

Pass requires all of:
1. L4 acceptance rate rises from base to tuned by at least 10 points absolute, or reaches 95 percent.
2. `snapshot_hash` mismatch rate is 0 on the tuned model (answer-wall guard).
3. Content guard: tuned outputs are not boilerplate. Measured deterministically: over the held-out set, the number of distinct `contradictions` and `missing_evidence` strings is at least 60 percent of the base model's count, and `disposition` is not a single value on more than 90 percent of prompts. This catches "learned to emit an empty valid object."
4. Latency: tuned decode time does not exceed base by more than 20 percent at the same token budget.

Fail on any of the four means the tuned checkpoint is not pinned and the base identity stays. No further study.

## 6. Pinning and promotion (G16)

On pass, `GraniteIdentity` records: base checkpoint SHA, LoRA adapter SHA (or merged weights SHA), tokenizer SHA, quantization, runtime and versions, thinking mode, sampling recipe for inference (temperature 0, fixed max tokens), system prompt hash, schema version, parser code SHA, and the tune receipt hash. This identity is what G17 to G19 test against. Changing any element mints a new identity.

## 7. Build order and lanes

| Step | Deliverable | Lane | Depends on |
|---|---|---|---|
| 1 | `granite_output_schema.py` (schema constants, validators) | L-GRANITE | none |
| 2 | `granite_parser.py` with the reward ladder and tests | L-GRANITE | 1 |
| 3 | Prompt builder over `state_serialization` with answer-wall test | L-GRANITE | 1, serializer at base |
| 4 | GRPO run script and `GraniteTuneReceipt` | L-GRANITE | 2, 3, GPU |
| 5 | Pass/fail evaluator (section 5) | L-GRANITE | 2, 3 |
| 6 | `GraniteIdentity` pin and registry entry | L-GRANITE | 4, 5 |

Steps 1 to 3 and 5 are pure code with synthetic tests and can go in the current batch. Step 4 needs the GPU and Oct 1 serialized states, so it runs once the mechanics scope is authorized. Nothing waits on B1 or C15.

## 8. Acceptance criteria for the code lanes

- P1 Parser determinism: same text and snapshot always yield the same level and reward.
- P2 Ladder monotonicity: fixture outputs at L0 to L4 score strictly increasing rewards.
- P3 Runtime equals training: the runtime acceptance function is literally `score(...)[1] is L4`; a test imports both call sites and asserts the same function object.
- P4 Answer wall: an otherwise perfect output with a foreign `snapshot_hash` scores L3 and is rejected at runtime.
- P5 Ref resolution: a ref to a nonexistent row or field scores L3.
- P6 No BLD-1 leakage: parser output type has no field named in `BLD1_FIELD_NAMES`; a test asserts the intersection is empty.
- P7 Prompt builder: prompt text contains the exact serialized state text (byte match) and no BLD-1 field name.
- P8 Model-agnostic: parser and prompt builder take no model-specific arguments; a second model can be evaluated with the same code and its own identity.

## 9. Deferred

- Rewarding content quality, judges, or preference data.
- Distilling Granite behaviour into BOSS (separate experiment family with its own controls, per the candidate doc).
- Any Granite influence on halting or abstention.
- The second open-weight model: same schema, parser, and evaluator; its own tune receipt and identity; decision on how it sits beside Granite pending owner input.
