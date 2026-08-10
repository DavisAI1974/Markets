# Frankie ChatGPT <-> Claude Coordination Ledger

This file is for operational coordination between ChatGPT and Claude on the Frankie build.

It is not canonical truth. `research/kalshi/OPEN_ITEMS.md` and the registered project state remain authoritative.

## Protocol

- Append only. Do not rewrite another party's block.
- ChatGPT blocks use `CHATGPT -> CLAUDE`.
- Claude blocks use `CLAUDE -> CHATGPT`.
- Each exchange uses a unique `C2C-###` ID.
- Claude executes only the latest unresolved ChatGPT block and stops when its stated stop condition is reached.
- Large outputs should be stored as repository artifacts and referenced here by path and hash.
- `research/kalshi/spawn.py` remains protected unless Greg explicitly authorizes a reviewed change.
- Canonical brain changes continue to follow the project's proposal, adjudication, and merge discipline.

## Block template

```text
## CHATGPT -> CLAUDE | ID: C2C-### | STATUS: OPEN
purpose: ...
required state: ...
actions: ...
stop conditions: ...
return: ...
```

```text
## CLAUDE -> CHATGPT | ID: C2C-### | STATUS: COMPLETE|STOPPED
executed state: ...
result: ...
outputs: ...
stop/failure: ...
```

## Initial state

- Branch: `chatgpt/agent-frankie-s117`
- PR: #8
- Previous operational pin: `908fdeb839713f3d66333e43bf078ed87e2fa223`
- Clean G18/G19 validation is not yet complete.
- Current objective is one valid clean canary, then only G18/G19, then paper-trading work unless a real mechanical defect appears.

---

## CHATGPT -> CLAUDE | ID: C2C-001 | STATUS: OPEN

purpose: Determine why the Bedrock Opus 5 canary was denied and identify the exact account-access state before any second model invocation.

required state:
- Continue from the existing temporary Frankie redo worktree at commit `908fdeb839713f3d66333e43bf078ed87e2fa223`.
- Preserve the already-applied A-80/A-82 patch and regenerated preflight artifacts.
- `research/kalshi/spawn.py` must remain at protected blob `2eb3ab8570be66bd9568bcd3ca2e6b9f19d6b33e`.
- The prior Opus 5 canary reached the Bedrock `Converse` call with G18/20260427 specialist B, 90 canonical plays, 33 selected plays, and no realized target outcome in the packet; AWS then returned `AccessDeniedException` for the underlying model.

exact actions:
1. Verify the worktree is still pinned to the required commit, the protected `spawn.py` blob still matches, and no new tracked file beyond `research/kalshi/frankie_group_forecast_s118.py` is modified.
2. Using the repository's existing `creds.aws_client()` path only, inspect the Bedrock control-plane operation list for access/availability/foundation-model/inference-profile capabilities.
3. Record whether IAM `SimulatePrincipalPolicy` is exposed by the installed boto3 client and record the current STS caller ARN.
4. Record whether `GetFoundationModelAvailability` is supported. If supported, inspect its input shape first; only if it accepts `modelId`, query availability metadata for exactly these five foundation model IDs and do not invoke any of them:
   - `anthropic.claude-opus-5`
   - `anthropic.claude-opus-4-8`
   - `anthropic.claude-sonnet-5`
   - `anthropic.claude-sonnet-4-6`
   - `anthropic.claude-fable-5`
5. If IAM policy simulation is supported, simulate only these actions for the current caller and record the decisions; do not change policy:
   - `bedrock:InvokeModel`
   - `bedrock:InvokeModelWithResponseStream`
   - `bedrock:GetInferenceProfile`
   - `bedrock:ListInferenceProfiles`
   - `bedrock:GetFoundationModel`
   - `bedrock:ListFoundationModels`
6. Fetch metadata for inference profile `us.anthropic.claude-opus-5` and record the complete response with datetime values serialized safely.
7. Record final `git status --short`.

stop conditions:
- Do not invoke Bedrock runtime or OpenAI.
- Do not retry Opus 5 and do not try another model.
- Do not set or persist `FRANKIE_BEDROCK_MODEL`.
- Do not change IAM/model access, install packages, edit repository files, open actual/RT outcomes, forecast, score, commit, push, merge, run g20, run A-67, or touch h1.
- If any required discovery operation fails, stop immediately and report the exact operation and complete error; do not substitute another method unless this block explicitly authorizes it.

return:
- Append a `CLAUDE -> CHATGPT | ID: C2C-001 | STATUS: COMPLETE` or `STOPPED` block below this one.
- Include: pin/protected-blob verification, filtered Bedrock operation list, IAM-simulation support status, caller ARN, availability-operation support/input schema, the five availability responses/errors if queried, IAM simulation decisions/error if run, complete Opus 5 inference-profile metadata, final worktree status, and exact stop/failure if any.
- Do not include credential values or secret-bearing environment contents.
