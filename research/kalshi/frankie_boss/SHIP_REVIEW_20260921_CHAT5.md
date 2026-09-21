# /ship review of chat 5's render stacks (2026-09-21, 13:5xZ)

Scope: `git diff 6bacc7ae..2bc0ff03` as reviewed (9 commits, 11 files), then the fixes below on top (through the commit
carrying this file). Three personas ran in parallel (code-reviewer, security-auditor, test-engineer) against the files
extracted at 2bc0ff03; the merge and the decision are the main session's. Files reviewed: `deploy/aws/box/
frankie_box_digest_render.py` (DIGEST_V4), `frankie_box_reading_render.py` (L8/L9/L10), `frankie_box_stacked_text.py`
(STACKED_TEXT_V1), `frankie_box_head_render.py` (HEAD_TEXT_V1), the profile and measure scripts, the session wiring,
`tests/test_frankie_box_*.py`.

## Ship Decision: GO, after the fixes below (all applied and pinned by tests before the restart)

No persona found a path where a transform changes a value AND passes its own proof on the committed range; every
cell-spelling ambiguity probed resolved exactly. What failed was the failure contract (three transforms raised out of
the session instead of leaving the value verbatim), one proof weaker than claimed, one crash on a degenerate table,
and one silent fold the proof could not see. Verdict before fixes: REQUEST CHANGES (code-reviewer), no Critical/High
(security-auditor), two Critical test findings (test-engineer). All of them are fixed in this range:

### Blockers found and fixed
- test-engineer CRITICAL, code-reviewer REQUIRED: a table whose every column is constant or derived parsed back to 0
  rows (`parse_table` stripped the empty row lines), so `render_layers` raised and `derive` would abort on a cycle with
  one structure family. FIXED: only the block's final newline is stripped; test `..._every_column_is_constant_round_trips`.
- test-engineer CRITICAL: `-0.0` folded into `0.0` through `_same`'s `==` (as a `^` repeat, a constant, or a derived
  `=` cell) and the proof passed. FIXED: `_same` compares the sign of zero; `_equal_typed` goes through `_same`; the
  digest schema is DIGEST_V5 so every box regenerates; test `..._negative_zero_is_never_folded...`.
- code-reviewer REQUIRED, security-auditor MEDIUM: a refused L9 (a spoofed or foreign envelope, a float leaf, a
  3,000-deep string) raised out of `render()` and killed the corpus. FIXED: both L9 sites fall back to the value as it
  was and write the reason to `RenderReport.block_notes` (receipted); `_is_envelope` requires the pinned codec's
  grammar hash; `_spell` has the depth guard `_parse` had; test `..._spoofed_or_foreign_envelope_leaves_the_value...`.
- code-reviewer REQUIRED, security-auditor MEDIUM, test-engineer HIGH: a head table cell that becomes `^` after prefix
  stripping, or a literal HEAD_TEXT_V1 marker line (a prior lesson could carry one), failed the whole head render.
  FIXED: no prefix on such a column; a head that already carries the grammar's markers is read verbatim; the proof is
  per section (an unprovable section stays verbatim); `parse` raises ValueError, never IndexError, on a missing
  marker or a bad `<<@n>>`; the wrapper is counted before a transform is kept; the session falls back to the verbatim
  head on any exception. Tests `..._caret_suffix_cell...`, `..._missing_its_markers...`, `..._wrapped_section_is_smaller`.
- code-reviewer REQUIRED: the corpus cache was not versioned (a restart would have read the stale corpus). FIXED
  before the first restart (5ff0472e): the receipt carries an identity; a differing corpus is moved aside and rebuilt.
- code-reviewer REQUIRED: `_same` treated a tuple and a list alike, so the L10 proof relied on a pre-filter. FIXED
  (6fd64a67): type-strict sequences, `U` tuple cells, the constants line carries the mark.
- code-reviewer REQUIRED: the legend did not describe `*k`, `#w` and `X .`. FIXED.
- test-engineer HIGH: `parse_table` accepted a truncated or ragged block silently. FIXED: row and cell counts are
  checked against the header; test `..._refuses_a_truncated_or_tampered_block`.
- security-auditor MEDIUM: the O(n^2) `ids.index` loop was reachable from untrusted lists through L10. FIXED: one
  position map per row (O(n)); L10 attempts only lists under `TABLE_MAX_BYTES` (16 MB).
- security-auditor LOW: `known_files_index` followed symlinks. FIXED: regular files only, anchored under the checkout,
  sorted walk (deterministic paths), `packed-refs` fallback for the commit.
- code-reviewer nit / test-engineer LOW: non-ASCII digits accepted by the stacked reader; column names that read as
  marks. FIXED: ASCII digit classes; unspellable column names refuse with a ValueError.
- code-reviewer REQUIRED (session): an unexpected exception in a stage is now a `refuse` with a receipt and a note,
  never a silently stuck phase.

### Recommended fixes carried (not blockers)
- security-auditor LOW: the profile printed head lines and digest rows into a public workflow log. Gated behind
  `SAMPLES=1`; the runs already made (35603160044) printed three head lines per section and two digest rows.
- security-auditor LOW: `pip install tokenizers` into the live venv is unpinned (pre-existing in the measure script);
  the session refuses a tokenizer whose sha256 differs, the measure does not check it. Queued: pin + verify.
- code-reviewer optional: a section with a table never gets the line dictionary (its own markers trip the guard); the
  findings prose does not repeat by line, so the gain is nil today. Queued.
- test-engineer 27: no CI ran these tests. `.github/workflows/frankie_box_codecs_ci.yml` added on this branch (runs
  the four files on push to the codec paths); trunk registration is Greg's word.

### Acknowledged risks (shipping anyway)
- The stacked block is 75.9k tokens of the record table's digits (order_id / timestamps / ts_in_delta / sequence
  deltas, price indexes): the data itself; no exact fold remains. The BOSS reads it in ~1 part.
- The head's A_MEMORY findings (31.5k tokens) are prose and stay as written.
- Each restart re-derives (seconds) and rebuilds the corpus; a part already queued on the Pod runs out there (jobs_v1
  has no cancel).

### Rollback plan
- Trigger: the session refuses at the corpus (a `boss-session-refusal-*.json` receipt naming the render), the
  reading receipt's proof is not all_exact, or a part's notes show the BOSS misreading a block grammar.
- Procedure: `frankie_box_run.yml` script `frankie_box_session.sh` variables `ACTION=restart_session
  REASON=<why> MARKETS_REF=<previous commit or 6bacc7ae>`; the corpus identity differs, so the old corpus is rebuilt
  from that code; the superseded corpora stay under `work/superseded-corpus-*` and their notes under `notes-<sha>-*`.
  Nothing is deleted; no Pod, box or host action.
- Recovery time objective: one box run (~1 min) plus derive (seconds) plus one reading part (~36 min on the Pod).

## Specialist reports (verbatim summaries)
- code-reviewer: REQUEST CHANGES; 0 Critical; 6 Required (L9 raise, head `^` after prefix, legend, `_same` tuple/list,
  empty-row tables, corpus cache gate); optional: `$table` columns union (fixed), deterministic index walk (fixed),
  packed-refs (fixed), dictionary beside tables (queued), L10 fallback notes (fixed), whitespace-collapse invariant
  comment (added), pin the profile's clone ref (queued).
- security-auditor: 0 Critical, 0 High, 3 Medium (L9 fail-closed not fail-safe: fixed; quadratic loop through L10:
  fixed; head marker collision: fixed), 3 Low (public-log samples: gated; symlinks: fixed; unpinned tokenizers:
  queued), 2 Info. No finding: `$file` path traversal, SSM keys reaching the corpus or logs, regex DoS, stacked parser
  recursion, new write/execute paths.
- test-engineer: 21 tests at the tip, none in CI; 2 Critical (fixed), 5 High (fixed), property probes: 2,000 random
  trees 0 mismatches, 3,000 random row sets 621 mismatches all from the empty-row bug (fixed; a 400-set version of the
  probe and a 600-tree version are now tests).
