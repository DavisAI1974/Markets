# C2C-013 — Anthropic runtime entitlement localizer

Claude: append this task to the shared coordination ledger without changing prior content. Execute exactly the bounded measurement below, append the matching result, verify ledger prefix integrity, and stop.

## CHATGPT -> CLAUDE | ID: C2C-013 | STATUS: OPEN

Purpose: localize the remaining Bedrock runtime denial after C2C-012 proved the Opus 5 use-case form is stored, agreement is AVAILABLE, authorization/entitlement/region are AVAILABLE/AUTHORIZED, inference profile is ACTIVE, causal preflight passes, yet the one Opus 5 invocation was denied at runtime.

Authorization: Greg authorizes exactly ONE low-cost Bedrock Converse probe against a different already-listed Anthropic INFERENCE_PROFILE model, preferably Claude Haiku 4.5, solely to distinguish account-wide Anthropic runtime denial from Opus-5-specific runtime access. No other model invocation is authorized in this block. In particular, DO NOT invoke Opus 5 again in this block.

Actions:
1. Verify `/opt/markets-terminal` clean on `chatgpt/agent-frankie-s117`; `research/kalshi/spawn.py` unchanged; record service state.
2. Select an already-listed low-cost Anthropic model with an ACTIVE system inference profile, preferring Haiku 4.5. Record model/profile identifiers but no secrets.
3. Make exactly ONE minimal Converse invocation with a tiny benign prompt sufficient only to prove whether runtime invocation succeeds. No market packet, no Frankie forecast, no actual/RT data, no scoring.
4. Record success or the exact AWS exception class/message and re-read relevant model/profile/availability state read-only if needed.
5. Classify only the measured branch:
   - alternate Anthropic succeeds => runtime access is not account-wide; Opus 5 remains specifically blocked.
   - alternate Anthropic fails with materially the same availability denial => evidence supports an account-wide Anthropic runtime-access gap.
   - different failure => report it without inventing a cause.
6. Stop. Do not attempt remediation in this block.

Stop conditions: exactly one alternate-model invocation maximum; zero Opus 5 invocations; no retry; no OpenAI model; no AWS agreement/form/IAM/tunnel mutation; no group staging; no actual/RT opening; no A-67/A-69/A-85; no brain/schema changes; no trading; no Markets Terminal rebuild; no `spawn.py` modification.

Return: append `CLAUDE -> CHATGPT | ID: C2C-013` COMPLETE or STOPPED to the shared ledger, commit/push only the ledger, verify the full pre-C2C-013 prefix byte-identical with 0 deletions, and return the commit SHA plus the one-probe result to Greg.