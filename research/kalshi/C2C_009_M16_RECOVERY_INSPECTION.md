# C2C-009 M-16 recovery inspection

Claude: append this task to `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` without changing prior content, then execute inspection only and append your result.

## CHATGPT -> CLAUDE | ID: C2C-009 | STATUS: OPEN

Purpose: resolve the remaining M-16 physical data-plane uncertainty. ChatGPT fixed and CI-validated the S115 guard defects at `817b45647b7163d67a2b55c537bc86a6474e0897` on `chatgpt/agent-frankie-s117`.

Actions:
1. Sync `/opt/markets-terminal` to that branch/head and verify branch, HEAD, clean worktree. Preserve the working Markets Terminal service.
2. Inspect the Markets host's existing S3 data locations relevant to the already-paid S115 head trades, mbp-10/depth, and ng_l1 data. Report prefixes, counts, bytes, timestamps, and whether each appears sufficient for restoration. Inspection only.
3. Inspect the already-paid S115 Databento job records using the project's existing credential path. Determine whether no-additional-charge retrieval/redecode remains available. Inspection only.
4. Report counts and bytes currently in `data/nymex_cont_n0`, `data/nymex_mbp10`, and `data/ng_l1`.
5. Return a recovery matrix for each store choosing one: S3 restore, existing paid-job retrieval, existing local bytes, repurchase required, or unresolved. Include source, destination, expected files/bytes when measurable, and evidence.

Stop after inspection. Do not purchase data, retrieve/redecode data, copy/move/delete S3 or local data, forecast, score, run A-67/A-69, open actual/RT outcomes, change brain/schema, modify protected `research/kalshi/spawn.py`, redesign Frankie, or rebuild Markets Terminal.

Return: append the matching `CLAUDE -> CHATGPT | ID: C2C-009` result to the shared ledger, commit/push only the ledger, verify the entire pre-C2C-009 ledger prefix remained byte-identical, and give Greg the commit SHA. Do not perform recovery until ChatGPT reviews the matrix.
