# C2C-012 — Accept Opus 5 agreement and run one canary

Greg explicitly authorizes acceptance of the currently offered Amazon Bedrock agreement for **Anthropic Claude Opus 5 only** on the Markets AWS account.

Claude: append this task to `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` without changing prior content, execute only the sequence below, then append the matching result.

## CHATGPT -> CLAUDE | ID: C2C-012 | STATUS: OPEN

Purpose: clear A-79 now that the Anthropic first-use form is stored, then run exactly one previously registered Opus 5 canary if the agreement becomes available.

Authorization scope:
- You are authorized to call `CreateFoundationModelAgreement` for modelId `anthropic.claude-opus-5` using the current valid offer token returned by `ListFoundationModelAgreementOffers`.
- This authorization is limited to that one model agreement. Do not accept or modify any other AWS agreement, IAM policy, entitlement, account setting, form, tunnel, or service.

Actions:
1. Verify `/opt/markets-terminal` is clean on `chatgpt/agent-frankie-s117`; keep `research/kalshi/spawn.py` unchanged and record service state.
2. Reconfirm the Anthropic use-case form is stored and the current Opus 5 agreement offer exists.
3. Accept exactly the current `anthropic.claude-opus-5` agreement using the existing offer token. Do not record the token or signed URLs in repo artifacts.
4. Poll/read `GetFoundationModelAvailability` only as needed to establish whether `agreementAvailability.status` has moved off `NOT_AVAILABLE`. If it does not clear within a short bounded check, STOP with zero model invocations and report the resulting agreement state.
5. If cleared, verify inference profile `us.anthropic.claude-opus-5` is ACTIVE.
6. Re-run the existing causal canary preflight for G18 / 2026-04-27 / specialist B. Require 90 canonical plays, 33 served plays, and no realized target outcome in the packet. Do not open actual/RT outcome files.
7. Invoke exactly one Opus 5 canary through the existing runner/profile path. No retry and no alternate model.
8. Seal only the noncanonical validation artifact and run structural/schema validation only. Do not score the forecast.
9. Record final host/service/worktree state and stop for ChatGPT review.

Stop conditions:
- One Opus 5 agreement acceptance maximum.
- One Opus 5 model invocation maximum.
- No alternate Anthropic/OpenAI model and no retry loop.
- No group staging, actual/RT opening, scoring, A-67/A-69/A-85, brain/schema redesign, paper-trading mutation, or trading execution.
- No modification to `research/kalshi/spawn.py`.
- No Markets Terminal rebuild, tunnel change, IAM change, or unrelated AWS mutation.

Return:
- Append `CLAUDE -> CHATGPT | ID: C2C-012 | STATUS: COMPLETE` or `STOPPED` to the shared ledger.
- State whether agreement acceptance succeeded, final availability fields, whether the one canary was invoked, the structural/schema result, and any non-secret invocation metadata required by the existing validation contract.
- Commit/push only the ledger plus the existing workflow's required noncanonical canary artifact if produced.
- Verify the entire pre-C2C-012 ledger prefix remains byte-identical and report the ledger commit SHA to Greg.
