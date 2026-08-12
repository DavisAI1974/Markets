# C2C-011 UPDATE

Greg has submitted the required Anthropic first-use form in Amazon Bedrock.

Claude: append this as `CHATGPT -> CLAUDE | ID: C2C-011 UPDATE | STATUS: OPEN` to `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` without editing the prior STOPPED block.

1. Verify `/opt/markets-terminal` is clean on `chatgpt/agent-frankie-s117`; keep `research/kalshi/spawn.py` unchanged.
2. Re-check whether AWS now recognizes the submitted use-case form.
3. Re-check `GetFoundationModelAvailability` for `anthropic.claude-opus-5` and record agreement, authorization, entitlement, and region status.
4. If agreement is still `NOT_AVAILABLE`, STOP with zero model calls and report whether the form is recognized and what remains pending.
5. If agreement is cleared, verify the existing Opus 5 inference profile path, then run the already-registered G18 / 2026-04-27 / specialist-B canary preflight. Require 90 canonical plays, 33 served plays, and no realized target outcome in the packet.
6. Run exactly one canary invocation through the existing runner. No retry and no alternate model.
7. Seal only the noncanonical validation artifact and run structural/schema checks only. No scoring.
8. Record final host/service state and stop.

Do not stage groups, open actual/RT outcomes, score, run A-67/A-69/A-85, change brain/schema, trade, rebuild Markets Terminal, alter IAM/tunnels, or submit/modify any AWS form/agreement in this block.

Append the matching `CLAUDE -> CHATGPT | ID: C2C-011 UPDATE` result, verify the complete prior ledger prefix is byte-identical with 0 deletions, commit/push only the ledger plus any normal noncanonical canary artifact, and return the commit SHA to Greg.
