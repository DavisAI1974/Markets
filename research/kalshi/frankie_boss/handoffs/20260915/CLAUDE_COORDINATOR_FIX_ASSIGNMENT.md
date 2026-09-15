# Claude: coordinator recovery and training checkpoint fixes

Start with `using-agent-skills`. Codex has read your review. Please implement this bounded slice now while Codex continues actual Sunday source recovery, full delivery, runtime admission, and Frankie adapter work.

## Workspace and base

Repository: DavisAI1974/Markets. Fetch branch `codex/full-frankie-boss-connection-20260915` at published commit `ae0102d8c28ed0589c86bb6f733e13b3914dea01`. The previously untracked coordinator, adapter, tests and source recovery are now committed there.

Use your own worktree and new Claude branch from that exact commit. Do not edit the active Codex checkout. Commit locally and return the exact branch, commit, worktree, changed files, new test evidence, and unresolved limitations. Codex can import the local commit; pushing is unnecessary.

## Exclusive ownership

Under `research/kalshi/frankie_boss/`, own only:

- `feedback_cycle.py`
- `boss_training_checkpoint.py`
- A new `tests/test_claude_cycle_review_fixes.py`
- A new `tests/test_claude_checkpoint_identity.py` if needed
- A new `CLAUDE_COORDINATOR_REVIEW_FIXES.md`

Do not edit the adapter, runtime, lifecycle, source recovery, or their tests. Codex workers own those concurrently. Preserve the existing chronology guard and completed replay before factories.

## Findings to fix

1. **H1: coordinator recovery gap.** Coordinate against this adapter API, being implemented independently by Codex: `PrincipalNotDispatched` means no durable session-request exists; `PrincipalPending` means a durable request exists but no response. On recovery, execute only for explicit `PrincipalNotDispatched`; propagate `PrincipalPending` without resubmission. Preserve ambiguous-call handling for an unknown result after actual dispatch. Never infer safety from a generic exception or missing response. You may access these exception classes lazily on the recovery branch until Codex merges the adapter changes. Do not implement adapter changes in your branch.
2. **M5: feedback roster.** Before saving accepted feedback or entering the training update, validate the feedback session IDs exactly match the requested session IDs in order. Rejection must leave the checkpoint usable and weights untouched.
3. **L1: export identity.** Reject a conflicting caller-supplied export request ID instead of overwriting it. Equal IDs are acceptable.
4. **L3: checkpoint identities.** Keep the admitted identity mapping immutable to callers and detached from the supplied mutable dictionary. Preserve the canonical serialization/binding APIs; a MappingProxyType exposed directly may break exact-type serialization, so choose a compatible defensive-copy/property approach or equivalent.

## New regression evidence only

Add focused tests for the newly fixed seams: pre-request recovery, pending outbox without redispatch, roster mismatch before training, export ID conflict, and identity mutation isolation. Do not rerun old passing tests or suites; no smoke runs. For H1, use a narrow local test double for the agreed exception contract if the adapter update is not yet merged, and clearly report that limit. Codex will verify the actual integrated seam once the two changes meet.

## Standing constraints

One supplied Sunday dataset is its own source. No source-day prerequisite, warmup, or added date. Reuse completed evidence. No cloud calls, Pod operations, model inference, principal invocation, source replay, broker actions, or Memory A changes in this assignment. Retained Pod `jvs75m56w8f73q` remains Codex-owned. Do not apply your old delivered branches again.

## Return

Finish the fixes, commit locally, and provide a short integration report with exact commit and new test results. If a concrete API conflict blocks this bounded slice, report the specific dependency instead of expanding ownership.
