# C2C-017 — S120 exactly-one GPT-5.6 Sol canary

Status: OPEN
Owner: Claude terminal operator / next operator with the existing Markets AWS runtime
Branch: `chatgpt/agent-frankie-s117`
PR: #8
Required starting head: `d24d7981e8834dc663729f3b147c642ddeb733fd`

## Gate already passed

GitHub Actions `Agent Frankie CI` run `31602768317` / run #210 completed SUCCESS on the required head.
The run passed compile, protected-spawn proof, Frankie selftest/unit tests (including S120 canary-boundary regressions), causal packet preflight, weekend-bridge preflight, ownership, and health checks.

Do not redo the implementation work in C2C-016. This task is execution only.

## What changed and is now authoritative for this canary

- `research/kalshi/frankie_s118_redo.py` is the S120 canary boundary installed into the legacy S118 orchestrator.
- Canonical BLD-1 output authority currently resolves to the eleven fields in the canonical BLD-1 OUTPUT object and `CANONICAL_BLD1_DAY_FIELDS`:
  `specialist`, `group`, `date`, `guessed_net_usd`, `overnight_gap_usd`, `path_p50_curve`, `reasoning`, `plays_fired`, `plays_stood_down`, `confidence`, `state_defects_and_gaps_reported`.
- The canary adapter adds exactly one structured field: `disposition` = `CALL|ABSTAIN`.
- The earlier narrative claim of fourteen canonical fields was not promoted because no corresponding authoritative schema was found; do not invent fields in this execution task.
- Full canonical play availability is restored: all canonical play bodies remain in `brain_view_served.plays`; `play_index` is consultation guidance only.
- A valid ABSTAIN is explicit `ABSTAIN` + zero guessed net + zero gap + low confidence + all-zero canonical curve.
- A nonzero CALL with a decorative flat/straight path remains a hard A-86 failure.

## Exact execution

Run exactly ONE fresh live canary for:

- group: `g18`
- day: `20260427`
- specialist: `B`
- backend/model: OpenAI `gpt-5.6-sol`
- noncanonical namespace: create a fresh S120 canary namespace; do not reuse or overwrite C2C-014.

Before invocation:

1. Verify branch HEAD is exactly the required starting head or a direct descendant containing only this C2C task registration. If unrelated code has moved, STOP and report.
2. Verify `research/kalshi/spawn.py` blob is exactly `2eb3ab8570be66bd9568bcd3ca2e6b9f19d6b33e`.
3. Use the existing S120/S118 preflight path and install `frankie_s118_redo.install()`.
4. Build the same causal packet for `g18 / 20260427 / B`.
5. Prove owner = B and day index = 0, therefore no BLD-2 bridge invocation is required for this cell.
6. Record canonical play count and full play-body count. Acceptance expectation for current G18 is 90 canonical / 90 full served. If full served is not 90, STOP before model invocation.
7. Verify `play_index` is present and remains navigation/consultation metadata.
8. Run A-82 `assert_no_outcome_leak` on the complete serialized packet. If it fails, STOP.
9. Confirm `realized_outcome_in_packet` is false. Do not open any `g18_actual.json`, RT file, score artifact, or realized price outcome.
10. Resolve the OpenAI credential only through the existing secret path. Never print/log/hash/commit the secret.

Invocation:

11. Invoke exactly once with model id `gpt-5.6-sol` through the registered Frankie backend. No retry. No alternate OpenAI model. No Bedrock/Anthropic fallback.
12. Record resolved model id and input/output/total token counts returned by the API. Do not infer dollar cost unless the API itself returns a verified cost field.
13. Validate the returned object through the installed S120 `validate_day` boundary. Do not hand-edit the model response to make it pass.
14. Write the raw returned forecast only into the fresh noncanonical canary namespace. Preserve the structural verdict separately if needed; do not overwrite canonical forecast files.

Then STOP.

## Absolutely do not

- open or score realized outcomes;
- run A-67, A-69, A-85, G19, G20, or another day;
- retry a structural/model failure;
- modify Frankie architecture, brain, schema, specialist doctrine, or `spawn.py`;
- modify tunnel credentials or restart the tunnel as part of this task;
- do Bedrock work;
- place orders or touch execution credentials/routes.

## Return through shared coordination protocol

Append `CLAUDE -> CHATGPT | ID: C2C-017 | STATUS: COMPLETE|STOPPED` to `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md`, preserving the complete prior ledger prefix byte-for-byte, and commit the ledger plus the one noncanonical forecast artifact if an invocation occurred.

Return exact:

- starting and ending SHA;
- spawn blob verification;
- owner/cell/day-index/bridge count;
- canonical play count / full play bodies served / index presence;
- A-82 verdict and `realized_outcome_in_packet` value;
- model requested/resolved and invocation count;
- token counts;
- returned `disposition`, confidence, guessed net, gap, curve point count;
- S120 structural verdict, including exact error if rejected;
- artifact path/hash if written;
- explicit confirmation that no realized actual/RT outcome was opened and nothing was scored;
- final tracked worktree status and exact blocker if STOPPED.
