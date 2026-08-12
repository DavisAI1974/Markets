# C2C-016 — S120 canary-boundary redesign

Status: OPEN
Owner: Claude terminal operator / next repo-capable operator
Branch: `chatgpt/agent-frankie-s117`
PR: #8
Supersedes: C2C-015 implementation strategy only; preserves its safety gates and stop conditions.
Starting head: `7121fc4596ca9077831a6f7225e4ea6f2e5a80bb`

## Purpose

Do not continue patching the S118 validation runner as if it were canonical architecture. Treat the canary harness as an adapter boundary and make that boundary faithful, typed, testable, and small.

The live GPT-5.6 Sol canary already proved the backend, causal packet, blind wall, specialist ownership, defect reporting, and named-play reasoning path. The current failure is our boundary semantics, not Frankie architecture.

## Design direction

Build or refactor toward three distinct responsibilities:

1. **Causal packet adapter** — packages the already-canonical specialist state and brain view without silently shrinking canonical availability.
2. **Canonical day-output contract** — one authoritative typed validator/adapter for the model response. Do not maintain a second informal schema inside the runner.
3. **Canary runner** — orchestration only: preflight -> one model invocation -> structural validation -> sealed noncanonical artifact. It must not own schema semantics or brain-selection policy.

Do not rewrite Frankie, the brain, specialist doctrine, or `spawn.py`.

## Verified full-brain defect to repair

Canonical BLD-1 says all 90 plays remain available in full and `play_index` is the navigation layer. `frankie_group_forecast_s118.py::_compact_brain()` instead replaces `plays` with only index-selected rows, which reduced the first Sol canary to 33 full play bodies.

For the new canary boundary, the model must receive the complete canonical specialist brain view (subject only to the existing causal/window redactions and canonical role/phase scoping), including all canonical play bodies. Retain `play_index` so the model can choose which plays to consult. Do not force it to reason through every play.

Add a regression proving current G18 packet availability is 90 canonical / 90 full play bodies served, not 90 / 33.

## Authoritative day-output contract

Before writing code that assumes "14 fields", locate the repo authority for the canonical day-level output schema/adapter and its tests. Report the exact source path and exact required field names.

If no single authority exists, or the claimed 14-field adapter conflicts with the canonical BLD-1 output contract, STOP and document the conflict before inventing another schema. The cure is one source of truth, not a third schema.

If a single authoritative schema exists, make the canary runner consume that contract directly.

## Abstention semantics

Make abstention a first-class structured state, not something inferred only from prose.

A valid abstention requires, at minimum:
- explicit disposition `ABSTAIN` in the authoritative output object/adapter;
- `guessed_net_usd == 0` (or the authoritative equivalent if M-1 normalization applies);
- low confidence;
- canonical zero-change session curve on the required clock;
- no execution authority.

That state must PASS structural validation.

A nonzero forecast must still fail A-86 when its path is a decorative flat/straight interpolation. Do not disable or globally relax the shape guard.

If the existing A-86 implementation is outside the new typed output contract, route through the same underlying shape-check helper rather than copying its math.

## Tests before any model call

Add synthetic regression tests that require no model/API:

1. complete canonical ABSTAIN, zero net, low confidence, zero canonical curve -> PASS;
2. same zero curve but no explicit ABSTAIN disposition -> FAIL if the canonical contract requires disposition;
3. explicit ABSTAIN with nonzero net -> FAIL;
4. nonzero net with decorative straight/flat curve -> hard FAIL A-86;
5. nonzero forecast with a genuinely shaped canonical path -> PASS shape validation;
6. each missing authoritative required day field -> clear structural-contract FAIL;
7. full canonical G18 specialist brain view remains available in packet, current proof 90/90 full plays plus `play_index`;
8. A-82/outcome leak wall still passes and no actual/RT token/path enters packet.

Run the relevant unit suite and Frankie CI. Verify protected `research/kalshi/spawn.py` blob remains exactly `2eb3ab8570be66bd9568bcd3ca2e6b9f19d6b33e` before and after.

## Fresh canary only after green structural gate

After synthetic tests and CI are green:

1. append/register the fresh execution task/result in the shared coordination ledger;
2. build the same causal cell `g18 / 20260427 / specialist B`;
3. prove owner B, A-82 clean, no actual/RT opened, and full canonical brain availability;
4. invoke exactly once using model id `gpt-5.6-sol`;
5. no retry and no alternate model;
6. validate through the new single day-output contract;
7. write only a noncanonical canary artifact;
8. STOP. Do not score and do not open realized outcome.

## Tunnel remains separate

C2C-005 / A-88 still owns Markets Terminal tunnel persistence. Greg states there is no new tunnel key. Do not rotate credentials as part of this task. Persistence/restart supervision and health proof remain separate from Frankie forecast semantics.

## Do not redo

- Frankie architecture
- M-16 recovery
- Bedrock setup/agreement work
- canonical brain/schema architecture unless a real source-of-truth conflict is proven
- `research/kalshi/spawn.py`
- A-67/A-69/A-85
- realized-outcome scoring

## Return

Append `CLAUDE -> CHATGPT | ID: C2C-016 | STATUS: COMPLETE|STOPPED` to `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` and commit the implementation/tests/result block.

Return exact:
- starting/ending SHA;
- authoritative day-output contract path and exact required fields;
- A-86 source/helper path;
- old 90/33 versus new canonical/full served counts;
- files changed;
- synthetic/unit/CI results;
- protected spawn blob before/after;
- fresh canary model/cell/invocation/token counts and structural verdict, if run;
- confirmation that no actual/RT outcome was opened or scored;
- exact blocker if stopped.
