# /ship on the post-review commits 024ff09f..a58a688a and the full-rerun runbook, 2026-09-22 chat 8

Three specialists ran in parallel (code-reviewer, security-auditor, test-engineer) on the two chat-7 fix commits
(bcffe024, 5ff3ab1c), the chat-7 close docs (a58a688a) and the runbook. Merged here. Every Critical, High, Important and
Medium finding is FIXED on `claude/cycle-0-frankie-box-rerun-od5sxk` with the test that would have caught it
(077fcb5a, 903b36f2), each test shown failing before the fix. Nothing has run on the host, box, Pod or endpoint.

## Ship Decision: GO (for checkpoint E and the full rerun from the beginning, each step on Greg's go; nothing runs by itself)

### Blockers (all fixed)
- [code-reviewer Important, security-auditor Medium, test-engineer G4] `frankie_box_teach._HEX` matched any 16+ digit run,
  so every nanosecond clock and gap (19 digits) in the facts and the answer was exempt from the number gate the chat-7
  review shipped: an invented timestamp passed as "checked by code". Fixed: the strip requires a hex letter, floor 8
  (a short cited prefix like 1b777cf2 licenses nothing either). Tests: `test_a_16_plus_digit_decimal_is_a_number_not_a_digest`,
  `test_a_short_hex_prefix_never_licenses_its_digit_runs`; the two chat-7 number tests still pass.
- [code-reviewer Important, security-auditor Medium, test-engineer G3] `frankie_box_restore_data_plane.sh` overwrote a
  present file whose digest differed from the (updated) pin, silently, against its own header and the runbook. Fixed:
  refused with "not overwritten (move it aside with a receipt first)" (the fetch_correction precedent) and the refusal
  receipted with both digests; a rejected download is stamped, never overwriting an earlier one. Test (source contract,
  the script's ROOT is hard-coded): `test_the_restore_script_refuses_to_overwrite_a_different_file_at_a_pinned_destination`.
- [code-reviewer Minor, promoted: it is the runbook's rollback trigger] `_NUMBER` read a range or date hyphen as a
  minus ("groups 0-2" harvested -2), so a correct answer would be refused, twice = rollback. Fixed: a minus only when
  not preceded by a digit or a dot. Test: `test_a_range_or_date_hyphen_is_not_a_minus_sign`.
- [security-auditor Medium, test-engineer G1] `derive()` moved `work/derived` aside but overwrote `derive.json`, the
  digest and the measurement in place; a traversal that died mid-derive left a current-looking gate over a moved
  directory. Fixed: `_move_aside(siblings=...)` moves those three files INTO the superseded directory under one stamp
  and receipt (`moved_files`), picks a stamp where neither the directory nor the receipt exists, and the receipt says
  what moved (schema FRANKIE_BOX_DERIVED_SUPERSEDE_RECEIPT_V1). Tests: the second-derive test extended,
  `test_move_aside_moves_named_sibling_files_even_without_a_directory_and_never_collides_on_the_receipt`,
  `test_a_derive_that_fails_after_the_move_aside_never_leaves_a_current_derivation`.
- [test-engineer G2, High, pre-existing] the correction stage's guard waited on `frankie-session-<cycle>`, a unit no
  script starts (the unit is `frankie-cycle-<cycle>`), so the guard against moving the checkout under a running cycle
  unit was dead, and its test pinned the wrong literal. Fixed: the guard names `$UNIT`; the test parses both.

### Recommended fixes (done)
- [security-auditor Low] `git fetch ... -- "$MARKETS_REF"` on the three remaining fetch lines (preflight, verify, start).

### Acknowledged risks (shipping anyway; on the after-run list)
- The restore script's ROOT and pin table are inline, so its refusal is pinned by source text, not executed (G3/G6/G11);
  making ROOT injectable is a later task. The derive_only unit guard is TOCTOU against a concurrent start; dispatches are
  serialised per instance by the workflow's concurrency group.
- `REASON` is spliced into the restart receipt unescaped (a double quote malforms the receipt); MARKETS_REF and CYCLE
  have no shape check beyond ssm_run_sh's literal-assignment filter; the producer sha256 pins are enforced at checkout,
  not at load, and the two legacy-five modules are not in `loaded_modules`.
- `_leaf_count` counts nulls inside a list but not a bare null; `_FILES` cache keyed by mtime; frozen-name flattening can
  collide on `a/b` vs `a__b`; `bedrock.run` takes the first layer's verdict; `lineage_vocabulary` re-implements a weaker
  `load_producers`; `frankie_box_docs` hashes each ledger whole (about 1 GiB each on a day).
- The chat-7 review's torch-hidden anomaly on `test_frankie_box_boss_session_rerun` (0, 2 or 3 failures depending on
  import order) is environment-dependent; this container shows 0 in every run; the box has torch.
- The render fixture still emits a lineage status (CLOSED) outside the pinned vocabulary (G8); the digest tests build on it.
- Runbook step 0 (the trunk registration of `frankie_host_supersede_principal_response.yml`) is a git push on Greg's word;
  the whole-cycle supersede refuses without it.

### Rollback plan
- Trigger: derive or teach refuses on the box for a reason that is a code defect (not a pin refusal, not a heartbeat
  wait); the V6 digest measures beyond what the reading lane should carry (Greg's call 2); the full rerun's host chain
  refuses at a stage the 09-20 chain did not.
- Procedure: box side `restart_session REASON=<why>` on a commit before c7d10fd5 (the pre-bedrock session; the request's
  pin must then be the old one, which the full rerun re-mints on the host); host side the 09-20 remedies (supersede the
  code-bound state, re-dispatch); durable jobs are keyed by prompt so no paid work is lost; every move on the box is
  receipted and nothing is deleted.
- Recovery time: one box dispatch (about a minute) plus one host re-render if the pin moves back.

### Evidence at 903b36f2
- Codecs CI list: 189 green torch present (2.14.0+cpu), 189 green torch hidden (the notorch stub); adapter suites 44.
- GitHub codecs CI: green on 5ff3ab1c (the commit that dropped checkout credentials; the audit's open item) and on 077fcb5a.

### Specialist reports (summaries)
- code-reviewer: REQUEST CHANGES, 0 Critical, 2 Important (the hex strip, the restore overwrite), 9 Minor; every chat-7
  fix verified present with its test; nothing Python 3.12 rejects.
- security-auditor: 0 Critical/High, 3 Medium (the hex strip, the restore overwrite, derive.json overwritten), 4 Low,
  6 Info; no key or token value anywhere in the range; pin/hash gates: no bypass found; containment holds.
- test-engineer: no chat-7 fix unpinned; High G1-G3 (fixed), Medium G4-G11 (G4 fixed; the rest on the list), Low G12-G19.
