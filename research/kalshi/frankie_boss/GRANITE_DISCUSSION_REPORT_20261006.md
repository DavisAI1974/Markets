# Granite Discussion Report - Frankie 30-Day AWS Experiment

Filed verbatim by CCode on 2026-10-06 from the report Greg handed over (the separate Granite discussion chat). Its branch
tip note (c6a8f6a5) predates the step 3 integration and the step 4 handoff; the role conclusions do not depend on it.
Implementation record: CCODE_GRANITE_FACILITATOR_20261006.md. Runtime config: knowledge/GRANITE_MEETING_RUNTIME_V1.json.

**Date:** October 6, 2026
**Repository reviewed:** `DavisAI1974/Markets`
**Branch reviewed:** `chatgpt/frankie-30day-aws-workflow-20261006`
**Branch tip verified during review:** `c6a8f6a54b7bade720aeb0e3da6e404bc63457b3`

## Executive conclusion

Granite should remain a **small, bounded post-class discussion coordinator**, not part of Frankie's scientific machinery.

The current plan is to start with **IBM Granite 4.2 3B GGUF, Q4_K_M**, preferably on a free standard GitHub CPU runner. If that is too slow, use the existing small AWS CPU box only while a discussion is occurring.

**Do not start with 8B.** Move to Granite 4.2 8B only if the single real end-to-end run demonstrates a concrete facilitator-quality problem with 3B.

No Pod, standing GPU, L40S service, old retained-vLLM infrastructure, critic role, self-assessment role, or separate Granite model-evaluation project should be restored for this 30-day experiment.

That is the newest position in the 30-day runbook and current checkpoint.

---

## 1. What Granite actually does

Granite operates **after the classroom**.

There are three scientific/data seats:

| Seat | Responsibility |
|---|---|
| Frankie | Learner/researcher; produces findings and hypotheses |
| BOSS teacher | Mathematics, representation, targets, masks, controls and its measured teacher evidence |
| Scientific teacher | Tests claims, counts evidence, checks cells/days/chance and proposes scientific tests |
| Granite | Coordinates the conversation between those three; it adds no scientific evidence |

Granite may:

- choose the next unresolved issue;
- ask a seat to clarify an ambiguity;
- identify scope, cell, or day mismatches;
- ask the BOSS teacher how its targets, masks, or controls bear on a disagreement;
- ask the scientific teacher which code test should resolve an open claim;
- ask Frankie what he learned, what remains a hypothesis, or what calculation he wants next;
- maintain the list of agreements, disagreements, missing evidence, and requested tests;
- continue follow-up rounds until the code/data seats either resolve the item or explicitly leave it open.

**Granite itself contributes zero evidentiary weight.**

Primary source:

`research/kalshi/frankie_boss/knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md`

Related rules:

`research/kalshi/frankie_boss/knowledge/CLASSROOM_RULES_V3.json`

---

## 2. Hard boundaries

Granite does **not**:

- calculate;
- derive counts;
- pool days;
- estimate;
- grade;
- score;
- select survivors;
- confirm hypotheses;
- alter the frozen confirmation list;
- forecast;
- trade;
- size positions;
- choose entries or exits;
- invent market facts, numbers, mechanisms, or findings.

If Granite asks for a new calculation, the appropriate code/scientific seat performs the calculation. Only the source-bound result may return to the discussion.

Granite also cannot expose Frankie's private decision process to the teachers or expose prohibited answer-key/graded material.

**Granite is a traffic controller for intelligence, not an intelligence source for the market science.**

---

## 3. Granite's outputs

The durable discussion record should distinguish four categories:

| Output | Meaning |
|---|---|
| Source-backed seat statement | Something Frankie, BOSS, or the scientific teacher actually supplied |
| Granite coordinator question | Coordination only; never evidence |
| Code-seat follow-up answer | New answer backed by that seat's code/data |
| Open item / requested test | Something that still needs scientific resolution |

Granite must not silently lose an unresolved disagreement, missing source, or requested test.

Its role is therefore closer to a disciplined research-meeting coordinator than to a fourth researcher.

---

## 4. Knowledge stacking

When a discussion or follow-up produces **new legally available knowledge**, that knowledge goes into Frankie's brain immediately.

It does **not** wait until the end-of-day school/consolidation step.

That matches the larger 30-day design: each new piece of checked knowledge becomes part of the foundation for the next work as soon as the relevant workflow boundary permits it.

Granite therefore participates in the continuous-learning loop, but only by coordinating source-backed knowledge produced elsewhere.

Relevant sources:

- `GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md`
- `Frankie_30Day_AWS_Runbook_20261006.md`
- `HANDOFF_20261006_STEP2_KNOWLEDGE.md`

---

## 5. Model choice

This is where the documentation evolved.

The **older** October 6 AWS handoff originally described:

- Granite 4.2 8B GGUF;
- Q4_K_M;
- GitHub CPU first;
- small AWS CPU second;
- paid GPU as a fallback.

That wording appears in:

`research/kalshi/frankie_boss/HANDOFF_20261006_AWS_WORKFLOW.md`

The **newer 30-day runbook/checkpoint supersedes that implementation choice**.

The current runbook says to:

**Start with Granite 3B `Q4_K_M`.**

Then:

**Use 8B only if the real end-to-end run exposes facilitator-quality problems with 3B.**

The current Codex handoff repeats the same rule, and the newer chat-reset handoff explicitly says not to introduce Pod/GPU execution under the historical fallback wording.

### Current source hierarchy

1. `research/kalshi/frankie_boss/Frankie_30Day_AWS_Runbook_20261006.md`
2. `research/kalshi/frankie_boss/CODEX_HANDOFF_FRANKIE_30DAY_AWS_20261006.md`
3. `research/kalshi/frankie_boss/HANDOFF_20261006_CHAT_RESET.md`
4. Historical implementation wording: `research/kalshi/frankie_boss/HANDOFF_20261006_AWS_WORKFLOW.md`

### Current implementation choice

| Choice | Current position |
|---|---|
| Granite 4.2 3B Q4_K_M | **Default** |
| Granite 4.2 8B Q4_K_M | Escalation only |
| GitHub standard CPU | **First hosting choice** |
| Small AWS CPU | Second choice |
| GPU/Pod | **Not part of current 30-day plan** |
| Standing Granite service | No |
| Old 131K retained principal machinery | No |

---

## 6. Why 3B makes sense for this particular job

The reduction from 8B to 3B does **not** weaken Frankie's scientific work because Granite no longer owns scientific work.

All difficult market mathematics, evidence checking, scientific judgments, survivor selection, and calculations remain in the code/BOSS/scientific-teacher paths.

Granite mainly needs to be good at:

- maintaining conversational state;
- obeying strict role boundaries;
- identifying unresolved issues;
- asking useful clarification questions;
- routing requests to the correct seat;
- distinguishing evidence from discussion;
- maintaining source attribution;
- producing a reliable structured discussion record.

For this role, spending additional compute on 8B before 3B demonstrates a deficiency would add complexity without an established need.

---

## 7. Runtime parameters still to settle

The role is already settled. What remains is the actual runtime configuration.

### Recommended starting parameters

| Parameter | Recommended starting decision |
|---|---|
| Model | Granite 4.2 3B GGUF |
| Quantization | Q4_K_M |
| Runtime | llama.cpp |
| Primary host | Free standard GitHub CPU runner |
| Fallback host | Existing small AWS CPU box |
| Upgrade model | Granite 4.2 8B Q4_K_M |
| Upgrade trigger | Demonstrated facilitator-quality failure in the real E2E |
| Context | Governed three-seat material, rules, applicable accumulated knowledge, unresolved discussion state |
| Scientific authority | None |
| Critic/self-assessment | None |
| Memory update | Immediate after legally completed discussion knowledge |
| Persistent GPU | None |
| Pod | None |

The following values were **not found locked** in the current runbook or role contract:

- temperature;
- top-p;
- maximum output tokens;
- exact input-token cap;
- maximum discussion turns;
- meeting timeout.

Those are implementation parameters still available for discussion.

---

## 8. What should count as a 3B failure

There is no need for a broad A/B model-evaluation project.

The authorized real E2E can answer whether 3B is adequate.

A move to 8B should require a material failure such as repeated inability to:

- remain inside the coordinator role;
- preserve source attribution;
- keep unresolved items intact;
- distinguish one seat's statements from another's;
- track discussion state;
- route a requested calculation to the proper code seat;
- follow the three-seat conversation as its state grows;
- produce a stable, usable structured discussion record.

"8B sounds smarter" is not sufficient reason to upgrade.

If 3B coordinates the discussion correctly, 3B is adequate for this role even if 8B could phrase the discussion more elegantly.

---

## 9. Recommendation

**Lock the initial Granite implementation to Granite 4.2 3B Q4_K_M with llama.cpp.**

Use the free GitHub CPU runner first.

If meeting latency is unacceptable, move that same 3B model to the existing small AWS CPU box rather than immediately changing the model.

Run Granite as an ephemeral meeting process: start it when a post-class discussion is ready and stop it when the discussion is complete.

Use the one real ROOT-to-finish E2E to judge facilitator adequacy.

Only move to 8B if the 3B model demonstrably cannot perform the bounded coordinator contract.

Do not restore the old Granite critic, self-assessment path, retained L40S service, 131K principal machinery, or GPU/Pod deployment.

This preserves the strongest parts of Frankie where they matter - the scientific/code seats - while keeping the conversational coordinator inexpensive and operationally simple.

---

## 10. Source-of-truth documents

1. `research/kalshi/frankie_boss/Frankie_30Day_AWS_Runbook_20261006.md`
2. `research/kalshi/frankie_boss/CODEX_HANDOFF_FRANKIE_30DAY_AWS_20261006.md`
3. `research/kalshi/frankie_boss/HANDOFF_20261006_CHAT_RESET.md`
4. `research/kalshi/frankie_boss/HANDOFF_20261006_STEP2_KNOWLEDGE.md`
5. `research/kalshi/frankie_boss/knowledge/GRANITE_DISCUSSION_COORDINATOR_ROLE_V2.md`
6. `research/kalshi/frankie_boss/knowledge/CLASSROOM_RULES_V3.json`
7. Historical/superseded implementation detail: `research/kalshi/frankie_boss/HANDOFF_20261006_AWS_WORKFLOW.md`
