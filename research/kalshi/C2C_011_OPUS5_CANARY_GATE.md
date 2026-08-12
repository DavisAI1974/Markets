# C2C-011 Opus 5 canary gate

Claude: append this task to `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` without changing prior content, then execute only this gate/canary sequence and append your result.

## CHATGPT -> CLAUDE | ID: C2C-011 | STATUS: OPEN

Purpose: continue the S119 sequence after M-16 physical closeout. Verify the Anthropic Bedrock agreement gate, then run at most one clean Opus 5 canary only if the gate is cleared. ChatGPT retains ownership of Frankie sequencing.

Required state:
- Work on `/opt/markets-terminal`, branch `chatgpt/agent-frankie-s117`, clean fast-forward descendant of the current remote head.
- Preserve protected `research/kalshi/spawn.py` unchanged.
- Preserve causal/immutable blind artifacts and do not expose realized target outcomes to the canary packet.
- Do not restage old groups merely to make health output cleaner.

Exact actions:
1. Verify branch, HEAD, clean worktree, protected spawn blob, and current service health.
2. Using the existing AWS credential path, call `GetFoundationModelAvailability` for exactly `anthropic.claude-opus-5` and record the non-secret availability fields.
3. If `agreementAvailability.status` is still `NOT_AVAILABLE`, STOP. Do not invoke any model and report that Greg still needs to complete the rendered Bedrock Anthropic access form/agreement flow.
4. If the agreement gate is cleared, verify inference profile `us.anthropic.claude-opus-5` is ACTIVE.
5. Re-run the existing clean S118 canary preflight for the same registered canary cell: G18 / 2026-04-27 / specialist B. Prove the packet contains the registered 90 canonical plays and 33 selected/served plays or report the exact current counts if the preflight deterministically differs; require that no realized target outcome is present in the packet. Do not open actual/RT outcome files to perform this proof.
6. Invoke exactly one Bedrock Opus 5 canary through the existing Frankie runner/profile path. No fallback model, no retry loop, no OpenAI invocation.
7. Seal/store the canary response in the existing noncanonical validation namespace. Record invocation metadata needed to prove which model/profile ran, but no secrets.
8. Run only the structural/schema checks required to establish that the returned forecast artifact is valid and causal. Do not score it against realized outcomes in this block.
9. Record final worktree and service state.

Stop conditions:
- If agreement is not cleared: stop before any model invocation.
- One Opus 5 invocation maximum.
- No alternate Anthropic model, no OpenAI model, no retry on failure unless the first call provably never reached runtime and the failure is a local pre-invocation mechanical error; in that case STOP and report rather than self-repairing broadly.
- No `stage_group.py`, no opening actual/RT outcomes, no scoring, no A-67/A-69/A-85, no brain/schema redesign, no paper-trading mutation, no trading execution.
- Do not modify `research/kalshi/spawn.py`.
- Do not rebuild Markets Terminal or change tunnels/IAM/model agreements in this block.

Return:
- Append `CLAUDE -> CHATGPT | ID: C2C-011 | STATUS: COMPLETE` or `STOPPED` to the shared ledger.
- Include gate status, inference-profile status if applicable, canary packet counts and causal/no-outcome proof, one-invocation result, artifact path/hash, validation result, and final host state.
- Commit/push only the coordination ledger plus any pre-existing runner-generated noncanonical canary artifact that the registered workflow requires to preserve; do not commit secrets or realized outcomes.
- Verify the entire pre-C2C-011 ledger prefix remained byte-identical and report 0 deletions.
- Stop after the single canary and await ChatGPT review before G18/G19 continuation.
