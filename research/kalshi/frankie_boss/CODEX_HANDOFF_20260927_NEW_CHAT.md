# Frankie/BOSS Monday — New Chat Drop-In

## Current truth

Read this handoff, then `research/kalshi/frankie_boss/CODEX_HANDOFF_20260927_PROJECTION_RUNTIME.md`, the referenced audits, and `CLAUDE.md`. Newer receipts supersede older prose.

- Repository: `DavisAI1974/Markets`
- Branch: `claude/agent-skills-execution-tzh7sw`
- Calculation resume: workflow `36339291716`, runtime commit `2d3e6bbf61f8f7be0568107abb618ba2d8c62b6a`
- Calculation root: `/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48`
- Corrected `CODE_ROOT`: `/opt/frankie-box/code/2d3e6bbf61f8f7be0568107abb618ba2d8c62b6a-36323776583-1/markets`
- ROOT PID: `60813`; token observed by startup probe: `099d4eb6-a46d-4b94-a888-f15e55c1ee7e:55572278`
- Startup probe run `36339391967` succeeded: process alive, phase `deriving`, stage `root-legacy-reuse`, finalized scientific state reused.
- ROOT is still `in_progress`. A live process is not completion. Do not start another ROOT run.

## Projection probe receipts

Read-only projection probes `36339506633` and `36339711464` succeeded. They report:

- Plan SHA256: `3ef241ac435253142680040976ab6f548b3119b1d73f26e6ca95bb9f78cb73b2`
- Member: `8,005` completed ranges, `145,401,924,464` archive bytes
- Lifecycle: `215` completed ranges, `1,460,318,809` archive bytes
- Combined compressed archive bytes: `146,862,243,273`
- Free bytes: `944,253,386,752`
- Range receipts observed `readback_verified=true`
- Latest projection SSM command: `2b28fa3c-3f6e-4b52-8ec9-2f118bcc8503`

These are projection evidence only. They do not prove that ROOT has produced `calculations-receipt.json`.

## Cleanup already complete

Retirement workflow `36338877506`, SSM `4ad6118d-f846-4283-b4da-87678b15a200`, removed exactly the five approved superseded member-ledger files. Actual freed bytes: `945,839,427,584`; free after: `945,841,012,736`. Receipt:
`/opt/frankie-box/work/retention/superseded-members-dbcbaaf8689f4648822b59748d3d895c/receipt.json`

Never rerun or broaden that deletion. Retained generation `recovery-9defa3169f7d46679491da2b1bfbbce2` and checkpoint SHA256 `2d61559ca9f5c650cdb22fa9aff29b8f0a366a648983493d435c26a3387943e6` remain protected.

## Immediate next action

Take one read-only receipt read when ROOT reaches a terminal state. Require:

- `calculations-receipt.json` exists with `status: calculations_retained`;
- actual receipt bytes and SHA256;
- process inactive and no competing calculation;
- `model_calls=0`, `source_replays=0`, `source_writes=0`;
- digest and digest-proof byte counts from the receipt.

Do not dispatch another observer, validator, calculation, staging run, or new route while ROOT is live.

## Next slice decision

Use receipt-level evidence for the available checks and explicitly report uncovered hash checks as unverified. Do not add a new observer or validator unless the user later authorizes that scope. After this bounded receipt read, stop for review before downstream staging.

The downstream order remains: staging, principal, classroom, grading, correction, retention, then Tuesday and learning outcomes. Preserve both members, 23 hours, all 18 historical sections/hashes, required slots, all three producer groups, exact reducers, all checkpoints, ledgers, archives, and partial publication evidence. No reconstruction, source replay, duplicate calculation, extra tests/canaries, infrastructure changes, or broad deletion.