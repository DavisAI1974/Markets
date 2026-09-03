# Drop-in for Codex — S123 closeout continuation

Repository: `DavisAI1974/Markets`

Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`

## State

Tasks A–I, the A_MEMORY checkpoint fix, the retired four-helper cleanup, and the
seven legacy failure classes are implemented, tested, committed, and pushed.
Read `research/kalshi/CLAUDE_S123_A_I_IMPLEMENTATION_HANDOFF_20260903.md` first;
it is the authoritative map of commits, files, behavior, caveats, and tests.

The implementation tip before the documentation handoff commit was
`58e3e6c3abb2f7a5a8e4956d3b9f3b5711e2ea80`. Resume from the branch HEAD that
contains this file and verify local HEAD equals origin before changing anything.

## Hard constraints

- Dispatch no workflow, canary, benchmark, Frankie session, feed run, or other
  run. D89 still makes the run last and Greg has not authorized it.
- Preserve D61 exactly:
  `research/ng_exhaustion_mbo_v4_state_adapter_20260820.py`, SHA-256
  `4a80e3e4b83867046d318ba97d350c2d7aca22e9d182d98399d01eeacc72d3ce`.
- Do not delete or rebuild the retired four-helper system. RT and Forecaster use
  their already-selected one skill.
- Do not weaken refusal gates, fabricate receipts, rewrite frozen records, or
  treat the one-day self-proof bootstrap as independent evidence.
- Empty daily findings are legitimate and add no memory. Missing output remains
  distinguishable. Veto is persistent unserved state, never deletion.

## New Frankie spawn lookup contract

`emit()` looks up the live result and all receipt/proof objects, computes the
crosswalk, gates first, then passes the exact already-loaded gated knowledge
receipt object to `render_knowledge_block`. It must not reload the receipt or
duplicate the renderer's schema, headings, counts, or bytes. The exact rendered
block belongs in the emitted prompt. Tests assert this object binding.

## Verification already complete

The final code suite was green:
`1997 passed, 14 warnings, 6389 subtests passed in 92.35s`.
Store checks, documentation indexing, YAML parse, `py_compile`, diff checks, and
the D61 lock passed. A documentation-only handoff commit may have run the suite
again; use its recorded result. Do not rerun expensive checks unless the tree
changes or the repository rules require them.

No implementation task is intentionally left open. The next work is review and
Greg's decision about when to run, not an automatic dispatch.

## Local operational note

Plain local HTTPS Git push lacked credentials in the previous session, so the
selected GitHub connector was used to update this branch. A redundant stash named
`task-g-awaiting-task-i` may still exist locally; its content is already integrated
and pushed. Do not reapply it.
