# CLAUDE FRANKIE TEMP TAKEOVER — S124

## Purpose

You are the TEMPORARY reasoning operator for the EXISTING Frankie framework. This is a short-term provider substitution so Frankie can run without OpenAI API/AWS inference spend. You are **not** redesigning Frankie around Claude and you are **not** creating a permanent Claude backend.

This file is the operating contract for the first Claude-driven Frankie validation.

## Git anchor and authority

Repository: `DavisAI1974/Markets`

Temporary operating branch: `claude/frankie-temp-s124`

Frankie code anchor before this takeover file was added:

`65138356bd944c0b7d85566028a9e90e79dc0801`

When you clone, use the **latest HEAD of `claude/frankie-temp-s124`**, not the anchor SHA, because this takeover file advances the branch.

Authority order:

1. Current checked-out branch code, tests, runtime invariants, and current CI state.
2. The newest S122/S123 progress-lock/current-task artifacts present in the checkout.
3. Current Frankie build/implementation docs where still consistent with code.
4. Older `OPEN_ITEMS.md`, handoffs, and kickoff docs only for provenance. They may describe work that has already been completed and MUST NOT override current code/tests.

Do not redo completed Frankie architecture.

## Data phase is CLOSED

Do not spend this run reconciling the old 1,914 count versus a lower local survey. The accepted stopping point is the existing **1,800+** causal data surface. That is enough to move forward.

Do **not** add new data fields, sources, collectors, features, or derived datapoints during this validation.

`unread` is diagnostic only. It is not a Frankie access restriction. Every currently possessed field that is causal at the decision cutoff and not future-contaminated remains eligible for Frankie access.

Do not fabricate the identities or values of unresolved fields.

## Absolute no-change contract

Claude is the reasoner, not the configurator. You MUST NOT change, prune, rank-gate, hide, truncate, summarize-away, reconfigure, rewrite, override, reinterpret, or otherwise alter what Frankie is served.

Specifically, DO NOT change:

- Frankie data surface / available fields
- Frankie brain
- Frankie schema
- full play inventory or play bodies
- masks
- future target-price mask
- A-82 isolation
- thresholds
- timing rules
- causal cutoff rules
- ownership rules
- specialist assignments
- decision settings
- output contract
- execution authority
- serving/access policy
- field inventory semantics

The complete prepared causal packet is authority. Frankie gets the whole currently allowed packet and the full brain, and Claude decides **inside its reasoning** which information is relevant. Do not reduce availability as a way of filtering.

Never weaken a fail-closed invariant to make a run pass.

## `spawn.py` is protected

`research/kalshi/spawn.py` may be READ for historical blind/refine behavioral reference only.

**DO NOT MODIFY `research/kalshi/spawn.py`.**

Do not change its pin or bypass `verify_original_spawn()`.

## Causal/blind wall

The first forecast phase is BLIND.

- No realized target outcome may enter the blind packet.
- Do not infer, reconstruct, search for, or derive the masked future target-price path from later information.
- No actual/reveal data may be read for the purpose of producing the blind forecast.
- Blind artifacts are immutable once written.
- If an invariant indicates future contamination or missing required causal access, STOP rather than weakening the invariant.

A-82 isolation remains binding throughout.

## Temporary Claude operator

Use:

`research/kalshi/frankie_claude_code_temp.py`

This file is a removable wrapper around the existing Frankie runner. It is not a permanent Frankie provider registration.

The wrapper intentionally:

- serves the full 90-play brain;
- preserves the current prepared Frankie packet;
- strips Anthropic API / Bedrock / Vertex routing variables so the inner invocation can use Claude Code subscription authentication;
- disables tools for the inner forecasting invocation;
- keeps blind forecast, score/reveal, and RFN-1 refine as separate phases;
- refuses refine until the full blind group is already frozen;
- preserves the original `spawn.py` verification.

Do not turn this temporary wrapper into permanent architecture.

## First validation scope

Run **g17 and g18 only**.

The underlying current S118 validation harness is deliberately scoped to g17/g18. Do not broaden that harness during this run.

Namespace for this run:

`claude_s124_g17g18_01`

## Authentication rule

Before inference, ensure the local Claude Code CLI is authenticated through the user's Claude app subscription.

Do not add or require an Anthropic API key, AWS Bedrock, Vertex, OpenAI API, or another paid inference route to complete this temporary validation.

If subscription authentication is unavailable, STOP and report that environment/authentication blocker. Do not redesign Frankie to work around it.

## Exact run sequence

Run from repository root.

### 1. Confirm branch and clean starting state

```bash
git status --short --branch
git rev-parse HEAD
```

Confirm you are on `claude/frankie-temp-s124` and record the HEAD.

Do not silently discard pre-existing user changes. If the checkout is fresh, it should be clean before runtime artifacts are produced.

### 2. Run the temporary adapter tests

```bash
python -m pytest -q research/kalshi/tests/test_frankie_claude_code_temp.py
```

If these fail because of a real invariant/implementation problem, diagnose the smallest temporary-seam fix possible. Do not alter Frankie inputs/settings to force green.

### 3. Preflight g17/g18

```bash
python research/kalshi/frankie_claude_code_temp.py preflight g17 g18 --namespace claude_s124_g17g18_01
```

Preflight must pass before blind forecasting.

### 4. BLIND forecast

```bash
python research/kalshi/frankie_claude_code_temp.py forecast g17 g18 --namespace claude_s124_g17g18_01
```

This is the causal blind pass. Claude receives the complete prepared packet/full brain and filters relevance in reasoning only.

### 5. Freeze/verify blind artifacts BEFORE reveal

Before running score, verify that every required g17/g18 blind artifact for the namespace exists and is complete.

Do not edit or regenerate a completed blind artifact after any actual/reveal information has been accessed.

If any blind artifact is missing, malformed, or incomplete: **STOP. Do not score.** Fix only the blind/runtime issue without reading actuals, then rerun the required blind step.

Record hashes of the completed blind artifacts if practical so immutability is auditable.

### 6. Reveal / score

Only after Step 5 succeeds:

```bash
python research/kalshi/frankie_claude_code_temp.py score g17 g18 --namespace claude_s124_g17g18_01
```

Do not use score/reveal information to modify the frozen blind artifacts.

### 7. RFN-1 refine

After score/reveal:

```bash
python research/kalshi/frankie_claude_code_temp.py refine g17 g18 --namespace claude_s124_g17g18_01
```

Refine is posterior diagnosis/learning. The frozen blind forecast is historical evidence and remains immutable.

Use the canonical RFN-1 behavior already wired by the wrapper. Do not invent a new refine protocol.

## What you may fix during the run

If something fails, first determine whether it is:

1. environment/authentication,
2. temporary Claude wrapper compatibility,
3. missing runtime dependency/path,
4. genuine Frankie invariant/data/access failure.

Make only the smallest necessary fix on `claude/frankie-temp-s124`.

Do not use a failure as permission to redesign Frankie, prune the data surface, change decision settings, weaken causal protections, alter masks, or add new data.

If a genuine Frankie invariant fails and cannot be resolved without changing protected behavior, STOP and report it.

## Git discipline

This branch is temporary Claude operating space.

- Do not modify the permanent `chatgpt/agent-frankie-s117` branch.
- Do not merge anything automatically.
- Do not rewrite Frankie architecture.
- Do not modify `research/kalshi/spawn.py`.
- Runtime artifacts/results may remain on the temporary branch/check-out for evaluation.
- If you make a code fix, keep it minimal, explain it, run the relevant tests, and commit it only to the temporary branch.

## Required completion report

At the end, report concisely:

1. branch and final HEAD;
2. Claude subscription/authentication path used;
3. temporary adapter test result;
4. g17/g18 preflight result;
5. blind artifacts produced and whether they were frozen before reveal;
6. blind forecast outputs/calls with confidence/probability information from the canonical artifacts;
7. score/reveal results;
8. RFN-1 refine outputs/lesson conclusions;
9. any invariant stops, errors, or minimal fixes;
10. whether the first Claude-operated Frankie cycle is sufficiently clean to proceed to the next forward-running Frankie stage.

Do not recommend new datapoints merely because one validation forecast misses. We are intentionally letting Frankie run with the existing 1,800+ surface first and will only revisit specific missing inputs later if repeated runs demonstrate a concrete need.

## End state

The objective is not a perfect historical score. The objective is to prove that the EXISTING Frankie system can complete a clean causal cycle with Claude temporarily acting as its reasoner:

**full existing causal surface + full brain -> blind forecast -> immutable blind artifact -> reveal/score -> RFN-1 refine**

Do that without changing what Frankie sees.