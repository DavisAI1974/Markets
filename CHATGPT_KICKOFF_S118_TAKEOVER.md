# ChatGPT Kickoff — S118 Markets / Frankie Takeover

**Repository:** `DavisAI1974/Markets`  
**Working branch:** `chatgpt/agent-frankie-s117`  
**Primary PR:** #8 — AWS-ready hybrid Agent Frankie  
**Ownership:** Claude -> ChatGPT  
**Purpose:** Start a fresh ChatGPT session from the current registered truth without re-litigating completed work.

## Required reading order

Read these before changing code:

1. `CHATGPT_KICKOFF_S118_TAKEOVER.md` — this file.
2. `research/kalshi/FRANKIE_BUILD_BRIEF_S115.md` — Claude's controlling Frankie design brief.
3. `research/kalshi/FRANKIE_S115_IMPLEMENTATION.md` — implementation status against S115.
4. `CHATGPT_HANDOFF_S117_AGENT_FRANKIE.md` — engineering/AWS handoff.
5. `OPEN_ITEMS.md` — canonical outstanding-work registry.
6. `research/kalshi/FRANKIE_ARCHITECTURE_S117.md` and `research/kalshi/FRANKIE_RESEARCH_INTEGRATION_S117.md` for architecture/research detail when needed.
7. Older Claude/session handoffs only for provenance or subsystem-specific history. Do not let an older handoff override newer registered truth.

## Current Frankie entry point

`research/kalshi/agent_frankie.py`

The original specialist spawner is:

`research/kalshi/spawn.py`

**Do not modify or replace `spawn.py`.** Frankie verifies its pinned Git-blob identity and may delegate legacy specialist work to it.

## Current architectural truth

Frankie is a hybrid, AWS-ready research/opportunity agent built around the existing Markets system rather than a replacement for it.

Implemented foundations include:

- deterministic point-in-time/event qualification;
- contract identity, causal clock, freshness, cost, provenance and balance-mode gates;
- independent causal-scientist and trading-mechanics reasoning lanes;
- no voting/averaging of lane disagreement;
- WATCH_ONLY / SHADOW / REJECT / HUMAN_REVIEW states;
- permanent `execution_enabled=false` in Frankie;
- SQS worker, redrive/DLQ posture, event-hash idempotency and immutable evidence;
- optional Bedrock + independent OpenAI slow-path reasoning;
- immutable resolved-outcome sidecars;
- bounded self-improvement proposals with independent criticism and no automatic code application;
- canary-first AWS/systemd deployment package;
- S115 ownership, retention, track-record, compaction, experiment and grading contracts.

## S115 controlling sequence

Follow Claude's S115 brief, not an inferred generic-agent roadmap.

Registered order:

1. **M-16 / A-61 / A-50** — data-path truth, pinned verification snapshot, leak-channel protection.
2. **A-66** — ownership table/part-level composition contract.
3. **A-59 + A-68 + A-62** — NOOA render/typed contract, causal append-only lens book, specialist track records.
4. **A-65** — validated compaction / same-cell posterior-diff test.
5. **A-67 arm 1 + A-69** — blind-vs-Frankie architecture A/B plus walked-corpus self-training.
6. **A-67 arm 2 + A-42/FJ-1** — sequential retention test plus first production grading pass.
7. **A-5 / A-63 / A-60 later** — similarity/retrieval kernel and empirical band work stay out of the first Frankie A/B until their prerequisite library exists.

Do not pull A-63/A-60 forward merely because they are attractive research work.

## Important S115 meanings

### A-68 retention

A-68 is the lens's causal book, not generic memory and not doctrine. It is append-only, written at the lens's own decision point, and visible only to strictly later causal slices. A future entry must be literally absent from an earlier slice. General lessons still require the normal brain proposal/adjudication/merge path.

### A-69 self-training

Training is on already-walked blocks while preserving the blind wall. Outcomes appear only after the blind decision for grading. The held-out head remains the true test. Do not fit thresholds/weights after seeing the held-out result.

### FJ-1 grading

Use the frozen failure taxonomy from `failure_localization.py`. Grade the **earliest unrecovered failure**, not the loudest terminal error. Do not substitute free-form model introspection for the grader.

### A-67 A/B

Existing blind harness and Frankie/Frankenstein run blind on the same staged head, in separate namespaces, with metrics fixed before either arm runs. Do not publish one arm's result into narrative/handoff/CLAUDE.md before the other arm completes; that contaminates the comparison.

A failure to improve forecast metrics does not automatically invalidate the architecture. It may still be useful for maintainability/contract integrity, but that must be reported honestly rather than described as a performance win.

## Research incorporated into Frankie

The paper manifest/research integration includes the confirmed agent/context/harness/self-improvement work discussed by Greg and Claude, including NOOA, ACM, Kernel Forge and the later approved self-improvement/harness papers. Use the reviewed manifest/integration files rather than inventing paper claims.

Research principles already adopted include:

- deterministic methods defend model-completed methods;
- declared context offload and named retrieval;
- preserve whole retrievable memory rather than lossy silent forgetting;
- classify mechanisms by the part/organ they own;
- sharing a broad layer is acceptable; owning the same part requires resolution;
- increase ownership resolution before inventing synchronization/protocols;
- preserve baseline and branch candidate harnesses rather than serially mutating one production harness;
- held-out/regression-aware promotion;
- source-level trial work remains isolated and cannot self-promote.

## AWS posture

Frankie is intended to live on AWS. First deployment remains canary-first and non-executing.

Relevant files include:

- `deploy/aws/markets-frankie.service`
- `deploy/aws/markets-frankie-reflect.service`
- `deploy/aws/markets-frankie-reflect.timer`
- `deploy/aws/install_frankie.sh`
- `deploy/aws/frankie.env.example`
- `deploy/aws/frankie_iam_policy.example.json`
- `deploy/aws/FRANKIE_AWS_SETUP_S117.md`

Do not grant Frankie venue order credentials, repository-write authority, IAM mutation, or automatic production-promotion authority.

## What is complete versus what still needs evidence

Do not confuse implemented contracts/tests with completed market experiments.

The Frankie/S115 code and safety scaffolding have been built and validated in CI. The next phase is **evidence production** on the real/staged corpus.

The registered next work is:

1. establish/verify the M-16 head/L1 data in the canonical data plane and prove where decoded rows land;
2. verify/rebuild the required actual corpus on each historical block's original contract basis, including older g6-g16 blocks if still absent;
3. stage and run A-67 arm 1 under the frozen blind A/B contract;
4. run A-69 on the walked corpus without exposing the held-out head;
5. run A-67 arm 2 for retention across sequential blocks;
6. run the first production A-42/FJ-1 grading pass;
7. only then move into the deferred A-5/A-63/A-60 similarity/band cycle.

Before executing those steps, re-read `OPEN_ITEMS.md` and `research/kalshi/FRANKIE_S115_IMPLEMENTATION.md` to see whether Claude or another session has already advanced any of them. Continue from the newest registered state; do not redo completed work.

## Standing invariants

- Preserve blind artifacts and held-out boundaries.
- Per-event rows, not pooled means as headline evidence.
- Missing means missing; do not interpolate or hallucinate unavailable inputs.
- Contract identity/source/month/clock must be explicit.
- Structural seams are not automatically realized arbitrage.
- Predictive candidates are not proven edges without untouched-forward evidence.
- No fitted thresholds, weights or coefficients unless a later registered experiment explicitly authorizes them.
- Frankie remains non-executing until a separate future authority/risk process is deliberately designed and approved.
- Keep NYMEX, Kalshi and any future venue ledgers separate.
- Do not modify the protected original `spawn.py` as part of Frankie work.

## New-session instruction

After reading the required files, identify the newest registered state of M-16/A-61/A-50 and the S115 experiment prerequisites. Continue from the first genuinely incomplete registered action. Do not redesign Frankie, re-research already incorporated papers, or re-litigate completed architecture unless a test/evidence result falsifies it.
