# Granite 4.2 8B reasoning-layer assessment

Date: 2026-09-04

Decision: Retain Granite in the final B2 design, but make it a gated shadow teacher/critic first. Do not make it the market-authoritative live hot path.

## Why this assessment is independent of the vendor pitch

IBM's claims establish model identity, architecture, training method, license, supported inference modes, and vendor-reported benchmark results. They do not establish that Granite understands Frankie's MBO state, improves an NG forecast, calibrates uncertainty, preserves causal timing, or creates net trading value.

This assessment therefore separates:

- official model facts;
- relevance to Frankie's actual state representation;
- risks introduced by the text-serialization boundary;
- evidence the repository already has;
- evidence that still must be produced by our own controlled test.

## Official model facts verified

The IBM/Hugging Face model card dated August 25, 2026 identifies Granite 4.2 8B as:

- an 8B-parameter dense decoder-only transformer;
- natively 128K context, with a stated long-context extension to 512K;
- bfloat16 at the published checkpoint;
- Apache 2.0 licensed;
- capable of thinking, non-thinking, and low-effort thinking modes;
- post-trained from Granite 4.1 8B Base;
- supervised on instruction, chain-of-thought, reasoning, synthetic, agentic-trace, and human-authored data;
- reinforced with multi-environment GRPO followed by preference alignment;
- one of the 8B and 30B sizes receiving the specialized agentic RL phase described by IBM.

IBM reports strong general reasoning, coding, tool use, and long-context benchmark results. None of the published result tables contains native futures MBO reconstruction, order-lifecycle semantics, FIFO queue reasoning, NG forecasting, or a Frankie-compatible calibration benchmark.

The 8B checkpoint is the correct first Granite candidate because it is the smallest size IBM says received the specialized agentic RL phase. The 3B model is cheaper but lacks that stated phase. The 30B model increases infrastructure and latency before Frankie's serialization hypothesis has been proven.

## What Granite can plausibly contribute

Granite's plausible initial value is generic reasoning structure, especially:

1. identifying contradictions among explicitly named evidence;
2. comparing competing hypotheses;
3. identifying missing evidence and invalid inferences;
4. selecting relevant evidence from a bounded snapshot;
5. producing a structured critique of the native BOSS result;
6. creating candidate process labels for a later native-model distillation experiment.

Granite is less credible as the initial authority for:

- raw order-book reconstruction;
- queue position;
- exchange action semantics;
- causal availability;
- calibrated market uncertainty;
- compute halting;
- final order size;
- live-money execution.

Those functions either already have deterministic native authority or require market-specific validation that Granite's public benchmarks do not provide.

## Fit and mismatch with the BOSS

| Dimension | Granite strength | Frankie/BOSS risk | Required control |
|---|---|---|---|
| Multi-step reasoning | Native thinking mode and reasoning post-training | General reasoning may not transfer to market microstructure | Objective warmup probes before subjective labels |
| Tool use | Agentic RL and structured tool use | Live model tool use would enlarge the execution attack surface | No broker tools; read-only bounded evidence tools only |
| Long context | 128K native context | More context can increase latency and hide serialization defects | Smallest sufficient snapshot; token and latency budgets |
| Text interface | Mature serving and OpenAI-compatible endpoints | BOSS state is typed numeric, graph, mask, and provenance data, not prose | Deterministic schema-native serializer and parser |
| Flexible effort | Full, low-effort, and non-thinking modes | Different modes are different experimental conditions | Freeze mode in every receipt |
| Open license | Apache 2.0 weights | License cost is not infrastructure cost | Self-host and account for AWS compute separately |
| Published evaluations | Strong general results | Vendor-reported, no MBO task | Our time-disjoint paired benchmark |
| Stochastic generation | IBM recommends temperature 1.0, top-p 0.95, sampling enabled | Native BOSS eval is deterministic; stochastic labels can impair audit and replay | Freeze checkpoint, prompt, seed/backend; run replicated draws and preserve all outputs |

## Nucleus ambiguity resolved

The project decision against `Nucleus` refers to the separate Nucleus architecture preserved in the ReFRAG source bundle. That component is not part of the accepted executable route.

IBM's published inference recipe uses `top_p=0.95`, often called nucleus sampling. This is an inference-sampling algorithm, not the excluded Nucleus project. Removing the project component does not imply silently changing IBM's sampling recipe.

The sampling recipe is still a reproducibility issue. A Granite benchmark must either:

- follow IBM's recipe and run a predeclared number of replicated draws, freezing each output; or
- run a separately named deterministic decoding experiment and admit that it deviates from the model-card recommendation.

One sampled response is not a stable teacher label.

## Architecture scoring

These scores are an engineering decision matrix, not measured predictive performance. Each dimension is scored against Frankie's stated needs. Readiness is listed separately so a good target architecture cannot be mistaken for already working code.

Weights:

| Dimension | Weight |
|---|---:|
| Market causality and typed-state fidelity | 20 |
| Reasoning capability | 20 |
| Audit, replay, and falsifiability | 15 |
| Live latency and failure isolation | 15 |
| Operating and licensing cost | 10 |
| Experimental identifiability | 10 |
| Integration simplicity | 10 |

Results:

| Candidate | Design-fit score / 100 | Current implementation readiness / 100 | Assessment |
|---|---:|---:|---|
| B0 fixed native BOSS, no Granite | 73 | 75 | Strong causal baseline; does not satisfy the intended reasoning-depth requirement |
| B1 native recurrent BOSS, no Granite | 85 | 15 | Best self-contained long-term core; recurrence and halting are not implemented |
| B2 with Granite authoritative in the hot path | 66 | 5 | Adds reasoning but creates unproven text, stochastic, latency, and failure dependencies |
| B2 gated: B1 core plus Granite shadow/critic | 92 | 10 | Best architecture if Granite cannot override native state or block execution; still requires implementation and testing |

The conclusion is not simply `Granite good` or `Granite bad`. The best design includes Granite in an isolated role and excludes it from market authority until it earns promotion.

## With Granite versus without Granite

### Without Granite

Benefits:

- lower latency and lower infrastructure demand;
- simpler deterministic replay;
- no typed-state-to-text semantic loss;
- no sampled-output variability;
- smaller security surface;
- native reasoning can be trained directly on market objectives.

Costs:

- B1 must learn all reasoning behavior from limited market data;
- no pretrained generic reasoning critic;
- weaker early contradiction and evidence-selection prior;
- no external teacher/control for measuring sample-efficiency gain.

### With Granite in the live hot path

Potential benefits:

- more mature generic multi-step reasoning immediately;
- structured critique and competing-hypothesis generation;
- possible sample-efficiency improvement.

Costs:

- no current evidence that serialized MBO state retains the semantics Granite needs;
- IBM's public results do not validate market reasoning;
- stochastic inference conflicts with the native audit contract;
- context and thinking tokens add latency;
- model or serving failure can become a trading-system failure;
- a fluent rationale can make a wrong answer appear more credible;
- promotion would confound architecture change with teacher change unless B1 is held constant.

### With Granite as a gated shadow teacher/critic

This preserves the potential benefit while containing the risk:

- Native B1 produces the authoritative result.
- Granite receives only a hash-bound, causal, allowlisted serialized snapshot.
- Granite returns a closed structured critique, not free-form execution instructions.
- Both outputs are stored independently.
- Disagreements are preserved.
- Granite timeouts or errors do not affect B1.
- Granite cannot see broker credentials or call execution tools.
- Granite's contribution can be evaluated against B1 and against market outcomes before it affects decisions.

This is the locked initial B2 form.

## Cost and the meaning of free

Granite 4.2 weights are Apache 2.0 licensed. There is no per-token IBM license fee for downloading and running those weights yourself.

That does not make inference economically free:

- the published bfloat16 8B weights alone imply roughly 16 GB before runtime overhead, KV cache, activations, and serving headroom;
- a long 128K context can materially increase memory use;
- a quantized checkpoint reduces memory but becomes a distinct model identity that must be revalidated;
- AWS CPU/GPU, EBS, network, and operations remain costs;
- a third-party hosted Granite endpoint may impose its own fees and retention terms.

Under the user's accounting convention, self-hosted Granite can be `zero external model-API cost, excluding AWS`. It should not be documented as zero total cost.

The first test should avoid a permanently running GPU. Start with a bounded batch job or an on-demand instance, freeze the exact checkpoint, stop the instance after the run, and measure actual tokens, peak VRAM, wall time, and AWS cost.

## Required Granite interface

Input must be a closed schema containing only:

- source packet hash;
- entity and as-of receive time;
- named numeric fields and units;
- categorical fields;
- explicit value states: present, missing, or ablated;
- row order and graph ancestry;
- named QSV values and registry identity;
- defect flags and source versions;
- no answer, future row, realized outcome, another arm's result, broker state, or credentials.

Output must be a closed schema such as:

- snapshot hash echoed exactly;
- evidence references by allowed field/node identifier;
- contradiction list;
- missing-evidence list;
- ranked hypotheses;
- proposed disposition limited to `SUPPORT`, `CHALLENGE`, or `INSUFFICIENT`;
- no order side, quantity, price, or broker command;
- model, checkpoint, tokenizer, prompt, mode, sampling, seed, server version, start/end time, and output hash.

Free-form thinking text may be stored for research but cannot be the deterministic identity of the forecast.

## Promotion gates

Granite remains shadow-only until all gates pass:

1. Exact checkpoint and license identity frozen.
2. Serializer round-trip and answer-wall tests green.
3. October 1/3 objective probes show Granite actually reads ancestry, names, masks, defects, and numeric relationships.
4. Market-field ablation reduces performance on probes that require those fields.
5. Replicated inference quantifies response variance under the chosen decoding recipe.
6. B1 and B2 use identical native recurrence, data, seeds, heads, and evaluation windows.
7. October 4/5 outputs freeze before reveal.
8. Granite improves predeclared metrics over B1 and all Granite controls, with uncertainty reported.
9. Worst-case and high-percentile latency fit the decision deadline.
10. Timeout, malformed response, and disagreement drills prove B1 continues or abstains safely.
11. No broker/exchange credential or execution surface is reachable from Granite.
12. A later forward-live shadow period reproduces the benefit before live influence.

## Kill and fallback criteria

Do not promote Granite if any of these occurs:

- objective probes do not beat the market-field-ablated control;
- the serializer cannot preserve the relationships under test;
- output variance is too high for a stable teacher target;
- benefit disappears against B1 with the same recurrence;
- shuffled Granite labels perform similarly to aligned labels;
- Granite confidence does not rank realized error;
- latency breaches the decision budget;
- Granite introduces a new single point of failure;
- the result requires exposure to outcomes or another current arm;
- quantization removes the observed benefit;
- cost per decision exceeds the predeclared cap.

On a kill, keep B1 as the target reasoning layer and preserve the negative result. Do not silently swap to a larger Granite checkpoint or tune on the held-out days.

## Final decision

Keep Granite 4.2 8B in the final architecture, because it is the smallest Granite 4.2 size with IBM's stated specialized agentic RL phase and it provides a credible generic reasoning control. Do not treat it as a proven market predictor or a production dependency. B1 native recurrence remains the authoritative reasoning layer; Granite begins as a frozen, bounded, shadow teacher/critic whose value must be earned through Frankie's own tests.

## Primary sources

- IBM Granite 4.2 8B model card: https://huggingface.co/ibm-granite/granite-4.2-8b
- IBM Granite 4.2 repository: https://github.com/ibm-granite/granite-4.2-language-models
- IBM Research introduction: https://research.ibm.com/blog/introducing-granite-4-2
