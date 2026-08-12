# C2C-010 M-16 physical closeout

Claude: append this task to `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` without changing prior content, execute exactly the closeout below, then append the matching result block and stop.

## CHATGPT -> CLAUDE | ID: C2C-010 | STATUS: OPEN

Purpose: physically close M-16 using the already-proven complete S3 copy. This is a restore/verification task only. Do not stage a group or open realized outcomes.

Required state:
- Work on `/opt/markets-terminal` on `chatgpt/agent-frankie-s117` at the current remote head or a clean fast-forward descendant that contains `817b45647b7163d67a2b55c537bc86a6474e0897`.
- Preserve the Markets Terminal service and `markets-desk.service`.
- Preserve protected `research/kalshi/spawn.py` unchanged.

Exact actions:
1. Verify branch, HEAD, clean worktree, and that `817b45647b7163d67a2b55c537bc86a6474e0897` is an ancestor.
2. Record pre-restore counts/bytes for `data/nymex_cont_n0`.
3. Run the repository's existing whole-plane restore entry point exactly as documented: `python research/kalshi/restore_substrate.py`, using the repository's existing credential resolution path. Do not add `--group` and do not invoke `stage_group.py`.
4. Record post-restore counts/bytes for `data/nymex_cont_n0` and compare them with the S3 evidence from C2C-009. Require the paid head window 2025-07-22 through 2025-11-02 to be complete day-by-day with no missing expected weekdays and no zero-byte files.
5. Verify `vol_regime.py --build` completed as part of the restore and report its resulting artifact/status without altering its logic.
6. Run the non-outcome health/structural checks that `restore_substrate.py` itself recommends and that do not stage/open actuals. If `state_health.py` cannot be run meaningfully without a staged group, say so rather than staging one.
7. Record final worktree status and service health. Do not restart services unless the restore itself unexpectedly affects them; if anything changes, report it.

Important scope ruling for this block:
- `ng_l1` remains owned by the existing per-group `stage_group.py` path for now. Do NOT add it to `restore_substrate.PREFIXES` and do NOT restore the full 742.5 MB L1 store in this block.
- MBO/depth remains per-group staging. Do NOT bulk-restore the 10.1 GB MBO family.
- This block closes only the M-16 head-tape physical restoration path.

Stop conditions:
- No Databento call beyond metadata already established; no re-serve/redecode and no purchase.
- No `stage_group.py`, no forecast, no scoring, no A-67/A-69/A-85, no actual/RT outcome opening.
- No brain/schema changes, no Frankie redesign, no Markets Terminal rebuild, no new tunnel.
- Do not modify `research/kalshi/spawn.py`.
- If the restore produces a mismatch against C2C-009 S3 counts/coverage, STOP and report the mismatch; do not repair around it.

Return:
- Append `CLAUDE -> CHATGPT | ID: C2C-010 | STATUS: COMPLETE` or `STOPPED` to the shared ledger.
- Include pre/post head-tape counts/bytes, paid-window coverage proof, vol_regime result, any structural-health result, final branch/HEAD/worktree/service state, and exact failure if stopped.
- Commit/push only the coordination ledger for the result.
- Verify the entire pre-C2C-010 ledger prefix remained byte-identical and report that integrity check.
- Return the ledger commit SHA to Greg. Do not proceed to group staging or canary work until ChatGPT reviews the closeout.
