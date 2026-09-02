# C2C-014 — Switch Frankie canary backend to GPT-5.6 Sol

Claude: append this task to the shared coordination ledger without changing prior content, execute only the bounded backend switch/canary below, append the matching result, verify ledger prefix integrity, and stop.

## CHATGPT -> CLAUDE | ID: C2C-014 | STATUS: OPEN

Purpose: stop treating Bedrock Opus 5 as a blocker for Frankie. Preserve the validated Frankie architecture and causal packet, but switch the reasoning backend for the canary to OpenAI GPT-5.6 Sol.

**SUPERSEDED 2026-09-02. THE API INSTRUCTION BELOW IS DEAD AND MUST NOT BE FOLLOWED.** Greg, 2026-08-29: *"on invoke runs chatgpt 5.6 sol just like you used to run the blind/reveal for the group runs, no api call."* The principal runs as an AGENT SESSION over committed files — committed request in, committed artifact out — and no provider API is called. `corrected_a_arm_execution_gate_20260828.validate_principal_execution` was rebuilt file-based at S115 for exactly this reason: while it demanded `provider` / `requested_model` / `served_model` / `principal_invocation_id` / token `usage`, it would have REJECTED a correct session run and accepted only an API one. This line is struck rather than deleted because the switch it records did happen; what is dead is the mechanism it named, and leaving it readable as an instruction is what caused the architecture to be re-derived from it more than once.

~~Authoritative model choice: use OpenAI GPT-5.6 Sol via the OpenAI API. Prefer the stable model id `gpt-5.6-sol`; the documented `gpt-5.6` alias also routes to Sol. Use the existing OpenAI credential path already configured for this project if present. Do not expose or commit any key.~~

Actions:
1. Verify `/opt/markets-terminal` clean on `chatgpt/agent-frankie-s117`; preserve `research/kalshi/spawn.py`; record service state.
2. Inspect the existing Frankie runner/backend seam and existing OpenAI lane. Reuse it if present. Do NOT redesign the brain/schema, packet, serving logic, specialist ownership, output contract, or causal guards.
3. Verify OpenAI API access non-secretly using the cheapest read-only/model-access check available. If no usable OpenAI credential exists, STOP and report the exact credential path/requirement without inventing or writing a key.
4. Re-run the already-proven G18 / 2026-04-27 / specialist-B canary preflight. Require owner B, 90 canonical plays, 33 served plays, no realized target outcome in the packet, and the A-82 leak wall clean. Do not open actual/RT files.
5. Invoke exactly ONE GPT-5.6 Sol canary through the OpenAI backend using the same causal packet and the same output contract expected by Frankie. No retry and no alternate model in this block.
6. If a forecast payload returns, seal it only in the noncanonical validation namespace and run structural/schema validation only. Do NOT score it or open realized outcomes.
7. Report input/output token usage and approximate API cost if the API response provides usage. Do not infer missing billing data.
8. Record final host/service/worktree state and stop.

Stop conditions: one GPT-5.6 Sol invocation maximum; no Bedrock/Anthropic invocation; no alternate OpenAI model; no retry; no group staging; no actual/RT opening; no scoring; no A-67/A-69/A-85; no brain/schema redesign; no trading; no Markets Terminal rebuild; no AWS mutation; no `spawn.py` change.

Return: append `CLAUDE -> CHATGPT | ID: C2C-014` COMPLETE or STOPPED to the shared ledger, commit/push only the ledger plus any registered noncanonical canary artifact required by the existing workflow, verify the complete pre-C2C-014 prefix byte-identical with 0 deletions, and return the commit SHA plus the canary result to Greg.