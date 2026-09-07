# Parallel R3 — Claude review corrections

Owner: Greg Davis. Date: 2026-09-07.
Repository: DavisAI1974/Markets.
Branch: `codex/boss-h2-p7-rulings-20260907`.
Reviewed starting tip: `c0716cc7bbc21a071be400f0ca43b9d7df715668`.

Read the supplied full review memo in `parallel_r3_contracts/` with this note.
This supersedes the old "full review not supplied" status in the H2/P7 handoff.
The architecture and H2/P7 rulings remain unchanged.

## Required corrections completed

R1: added a deterministic synthetic H2c fixture that first records eight
batch-one ratios at conv_tau=0, then chooses an interior descending pair and
uses its geometric mean as the threshold. Every preceding ratio must stay
above the threshold by more than 1%, and the selected crossing stays below it
by more than 1%. The fixture fails if no such pair exists. It asserts an
intermediate CONVERGED depth, then checks batch 32 with the unchanged
assert_h2_agreement helper. Removed the two obsolete h0 diagnostic assignments.

R2: the prompt wall now tokenizes lowercase identifiers using [a-z0-9_]+.
BLD-1 names without underscores require exact identifier equality; names with
underscores retain substring matching, including prefixed/suffixed variants.
Both rendered prompt text and decoded source strings are checked. The existing
36 name/location fixtures and exact-state test remain unchanged. New checks
prove book_update_count and consolidated_feed are accepted, date is rejected,
and the six underscore names remain rejected inside longer identifiers.

Since B1 was touched, the nonblocking eval-mode suggestion is also complete:
forward_decision rejects training mode, with a regression test. No schema,
parser, evaluator, normalizer, D-state, or existing Frankie code was changed.

## Verification

The new tests first reproduced both innocent-name rejections and the missing
eval-mode guard. After the fixes, only the two requested focused files ran:
49 B1 checks plus 55 prompt checks, **104 passed, exit 0**. The prior parser/
evaluator result of 126 passed is historical evidence, not a new rerun.
No tests were skipped, xfailed, or weakened. The fixed/zero-depth B0 path,
protected repository reference files, and all existing Frankie behavior remain
unchanged. No provider, market-data, training, AWS, or broad test run occurred.

The old linked worktree metadata had disappeared between turns. Its original
base was fetched by exact SHA, then the saved Git bundle restored the accepted
commits. Working files were preserved; status showed only the intended edits.

## Deferred items recorded in the workbook

- C15: implement PROBE_ONLY receipt consumption for Oct 1 when L-INT opens;
  current ReceiptDChain only accepts RESULT_BEARING. Do not present synthetic
  mechanics calls as receipt-bound production evidence.
- C06: define padding semantics; valid_mask currently affects halting norms,
  not trunk or recurrent attention.
- C23 schema: normalize the snapshot-hash regex to lowercase on its next touch.
- C23 evaluator: rename redundant schema_valid_count to
  content_denominator_count, or remove it while retaining visible L4/total.
- C23 / GRPO runner: build a per-prompt SnapshotIndex before optimizing repeated
  canonical validation and field lookup; preserve the reward ladder.
- C15 normalizer: measure median/MAD transform cost on the first mechanics pass
  before changing the bounded-window implementation.
- C15 D-state: the impossible zero m_prev branch is harmless; revisit on its
  next edit. Prefix hex normalization is accepted, with no correction required.

Claude clears this batch for push after R1/R2 and the focused checks. Those
conditions are satisfied. Publishing this branch does not authorize production
integration or any model/data run. OSS remains parked.
