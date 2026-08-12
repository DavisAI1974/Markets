# C2C-015 — S120 structural contract + full-brain canary

Status: OPEN
Owner: Claude terminal operator / next repo-capable operator
Branch: `chatgpt/agent-frankie-s117`
PR: #8
Starting head: `fecc5004808f1ba8b52d1162b1ceda60de894fdd`

## Purpose

Repair the S120 Frankie structural-output blocker before any scoring, and remove the S118 canary-only brain truncation so the next GPT-5.6 Sol canary receives the canonical full specialist brain view.

This is a narrow contract/serving repair. Do not redesign Frankie.

## Newly verified repo fact

The canonical BLD-1 template in `research/kalshi/store/sop_templates.json` explicitly says:

- `NOTHING WAS TAKEN AWAY FROM THE PLAYS. All 90 are served in full.`
- the specialist reads `play_index`, then CONSULTS selected plays BY NAME from the full `plays` map.

But `research/kalshi/frankie_group_forecast_s118.py::_compact_brain()` currently replaces `plays` with only rows whose index text contains ARMED / PARTIALLY_EVALUABLE / EVALUABLE. The first Sol canary therefore had 90 canonical plays but only 33 full play bodies served. That serving behavior is not the canonical S115 contract and must not be used for the next canary.

Do not alter the canonical brain or `brain_view.py` architecture to fix this. Fix the S118 canary packet serving seam so the canonical full view is available while retaining the index for selective consultation.

## Required work

1. Verify HEAD/branch and protected `research/kalshi/spawn.py` blob `2eb3ab8570be66bd9568bcd3ca2e6b9f19d6b33e` before edits.
2. Locate the A-86 decorative straight-line validator and its tests.
3. Locate the authoritative canonical day-level output schema/adapter and its tests. Do not invent field names from handoffs; use repo authority.
4. Implement explicit abstention semantics:
   - explicit disposition `ABSTAIN`;
   - `guessed_net_usd == 0`;
   - low confidence;
   - canonical all-zero session curve;
   => valid structural state.
5. Preserve hard A-86 rejection for non-zero forecasts whose path is flat/straight/decorative. Do not disable or globally weaken A-86.
6. Separately enforce all 14 authoritative canonical day-level required fields. Missing fields must fail with a clear structural-contract error. Keep this validation separate from the abstention exception.
7. Repair `frankie_group_forecast_s118.py` packet serving so the next canary receives the complete canonical specialist brain view, including all canonical play bodies, with `play_index` retained for selective consultation. Remove the 33-play canary truncation; do not change canonical brain content.
8. Add regression tests at minimum for:
   - complete explicit zero-net/low-confidence ABSTAIN + zero curve => PASS;
   - nonzero flat/straight decorative curve => FAIL A-86;
   - missing any canonical day-level required field => FAIL clearly;
   - complete canonical abstention output => PASS;
   - S118 canary packet serves the full canonical plays map (for current G18 proof this should be 90, not 33), while preserving play_index.
9. Run the relevant unit tests and the Frankie CI gate. Verify `spawn.py` blob unchanged after tests.
10. Do NOT open/score any realized outcome while doing steps 1-9.
11. Only after code/tests/CI are green, register the fresh canary execution as the next C2C task/result block and run exactly ONE fresh GPT-5.6 Sol `g18 / 20260427 / specialist B` invocation through the same causal packet, now with the full canonical brain and corrected structural contract.
12. The fresh canary must still satisfy A-82/no-outcome leak wall before invocation. Do not retry, use an alternate model, or score/open actual/RT outcomes afterward in this task.

## Tunnel work remains separate

Do not mix tunnel changes into this patch. Existing `C2C_005_SUSTAIN_MARKETS_MCP.md` / A-88 owns persistence: supervised always-on service, automatic restart after process death, health/readiness and real-client proof. Greg stated there is no new tunnel key, so do not rotate credentials merely because the S120 handoff mentioned an older env value. Diagnose persistence/restart behavior under C2C-005.

## Do not redo

- M-16 recovery/inventory
- Bedrock setup/agreement work
- Frankie architecture
- canonical brain/schema architecture
- `research/kalshi/spawn.py`
- realized-outcome scoring
- A-67/A-69/A-85

## Stop conditions

Stop and report rather than guess if:

- the authoritative 14-field schema cannot be located or conflicts with another claimed authority;
- passing the abstention case would require weakening nonzero A-86 protection;
- full-brain serving would violate the causal/redaction wall;
- the preflight detects any actual/RT/outcome content in the packet;
- the OpenAI invocation would not be exactly one `gpt-5.6-sol` call.

## Return

Append the matching `CLAUDE -> CHATGPT | ID: C2C-015 | STATUS: COMPLETE|STOPPED` block to `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` and commit it with the implementation/test changes.

Return exact:

- starting and ending commit SHA;
- authoritative 14 field names and source path;
- A-86 source/test paths;
- files changed;
- regression test results;
- CI result;
- protected spawn blob before/after;
- full canonical play count and served full-play count after repair;
- fresh canary model/cell/invocation count/token counts and structural verdict if run;
- explicit statement that no actual/RT outcome was opened or scored;
- exact blocker if stopped.
