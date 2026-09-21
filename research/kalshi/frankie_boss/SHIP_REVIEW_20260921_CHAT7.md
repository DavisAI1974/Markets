# /ship on the bedrock build (BR-0..BR-7 of PLAN_CYCLE0_BEDROCK_20260921.md), 2026-09-21 chat 7

Three specialists ran in parallel on `082e2ec9..024ff09f` (code-reviewer, security-auditor, test-engineer); merged
here. Every Critical, High and Important finding is FIXED on `claude/cycle-0-frankie-box-rerun-od5sxk` with the test
that would have caught it (bcffe024 group 1, 5ff3ab1c group 2). Nothing has run on the host, box, Pod or endpoint.

## Ship Decision: GO (for checkpoint E and the rerun, each on Greg's go; nothing runs by itself)

### Blockers (all fixed)
- [code-reviewer, Critical] `frankie_box_teach.facts` read recurrence gaps as integers; the pinned driver emits mappings
  (gap_ns, from_node, to_node, recv_ns, continuity_segment). On the box every rerun would have died after the classroom
  with a TypeError and no response. Fixed: the producers' shape, the largest gaps named with their nodes, a facts
  failure (TypeError/KeyError too) is a receipted refusal; the teach test now derives its work directory with the REAL
  session on the fixture stream and computes every expectation from the ledger rows
  (`test_facts_are_built_from_the_sessions_own_files_in_the_producers_shapes_and_never_average`).
- [code-reviewer, Critical] lineage statuses were counted as CLOSED vs the rest; the producers' vocabulary
  (native_lineage) is TERMINATED / CENSORED_SEGMENT_END / CENSORED_STREAM_END / OPEN and CLOSED is never emitted, so
  the facts would have told the BOSS "0 closed" as exact. Fixed: the vocabulary is imported from the pinned checkout
  (refused if loaded from elsewhere), terminated/censored/open reported by those names, a status outside it refused
  (`test_a_lineage_status_outside_the_pinned_vocabulary_is_refused`).
- [code-reviewer Important, test-engineer H1] the derive gate compared derive.json with the CHECKOUT pin only: a current
  derivation could be reused under a request rendered for another pin. Fixed: `_pin_matches_request` runs first in the
  gate and right after `verify()` in the run loop, before any engine reach; cycle index and group compared too
  (`test_a_current_derivation_under_a_pin_the_request_does_not_carry_is_refused_not_reused`,
  `test_the_run_loop_checks_the_request_pin_right_after_verify_before_any_engine_reach`).
- [code-reviewer Important, test-engineer H2] the number check harvested digit runs from the sha256 strings in the facts
  (any small integer the BOSS invented was likely licensed) and compared spellings (13 vs 13.0 refused). Fixed: hex
  digests (16+ hex chars) are removed before harvesting, the sign stays with its number, values are compared
  (`test_digit_runs_inside_a_sha256_in_the_facts_never_license_a_number`, `..._as_values`).
- [code-reviewer, Important] `result.json` declared a `result_hash` that no longer recomputed once `ledger_retention`
  was added after `finalize()` (the launcher's own F-feed-6). Fixed as the launcher does: `runner_result_hash` kept,
  `result_hash` recomputed last (`test_the_result_hashes_to_itself_as_written_...`).
- [code-reviewer, Important] the traversal's own verdict and failed gates were recorded in derive.json only. Fixed: in
  every layer file (`traversal`), the V6 header, a `bedrock.run` table and the teach facts. WHETHER a REJECTED
  traversal's layers stay `derived` is Greg's call (recorded below as an acknowledged risk).
- [security-auditor, Medium] the receipt hashed the pinned driver by path while the module that ran was resolved
  markets-first. Fixed: the modules that actually loaded are witnessed by their own `__file__` and refused outside the
  pinned checkout (`loaded_modules`; `test_a_producer_module_loaded_from_another_tree_is_refused`); the receipt lists
  the launcher differences (no checkpointer, no stage_spawn, no pre-traversal gates).
- [code-reviewer Important, test-engineer M3] a nested mapping key containing a dot re-nested differently on parse-back
  and killed derive() mid-run. Fixed: `.` is unspellable, such a mapping is one JSON string cell
  (`test_v6_a_nested_key_containing_a_dot_becomes_one_json_string_cell`).
- [code-reviewer, Important] the digest's members table carried the whole FIFO queue of every level per group (the bulk
  of the member ledger; tens of millions of tokens on cycle 0). Fixed: a list-valued carrier path rides as its leaf
  count (`<path>#count`); the values stay in the layer file and the ledger. The measured size is checkpoint E's job.
- [security-auditor Low, code-reviewer Important] the docs bundle copied the ledgers but the pusher never ships them
  (a published index naming absent files; and git = code, S3 = data). Fixed: referenced by name, bytes and sha256,
  kept on the box; the V6 header says so.
- [test-engineer, H3] the legacy-five byte witness was a recorded constant. Kept, and joined by the paired-run invariant
  (`test_the_legacy_five_are_byte_identical_with_and_without_the_bedrock`).

### Recommended fixes (also done)
- [security-auditor Low] `derive_only` aborts on a failed fetch/checkout, waits for the heartbeat and correction units,
  prints the markets HEAD; frozen entry names and delivered paths are contained; model text renders as one Markdown
  line, questions capped; `work/derived` moved aside with a receipt before a re-derive; refusal receipts carry a uuid;
  `producers_checkout.sh` identifies the worktree by git's registry (tested on a real shallow clone: populate, plain
  directory refused, another commit refused); the CI checkout keeps no credentials.
- [test-engineer M2, M4-M8, L2, L3, L6] the tokenizer-present-but-failing record; project's "emitted no rows" branch;
  the candidate-lane-opened verdict; a clock layer not derived reported unknown; parse edge shapes; producers_commit
  and loaded_modules refusals; docs/brain error entries; None group index and missing group key; duplicate bedrock
  group refused.

### Acknowledged risks (shipping anyway)
- The runner's coverage gate may return REJECTED on a slice cut mid-group (cycle 0's first 3,262 records); the layers
  are still filed by their rows and the verdict is everywhere. Greg decides whether a REJECTED traversal's layers count
  as `derived` (call 5, below).
- The digest's size on the real 2,282 groups is unmeasured until checkpoint E (no model call); `project` and
  `bedrock_tables` hold the projected rows in RAM (fine for cycle 0; the whole day needs per-layer streaming, recorded
  as a later task with the full CME Monday note).
- `_pin()` imports the adapter package (torch) in the derive stage as every stage did before; the bedrock module
  itself never does; the box venv carries torch.
- The code-reviewer's torch-hidden run saw two `test_frankie_box_boss_session_rerun` failures through `compare()`'s
  adapter import that this container's torch-hidden run (the notorch stub on PYTHONPATH) does not show; the CI list
  is green torch-present on GitHub (run 35667982872). The box has torch; recorded, not chased.
- The whole ledgers (about 45 MiB on cycle 0, about 1 GiB on the day) stay on the box; routing them to S3 is Greg's call
  (licence and size).

### Rollback plan
- Trigger: derive refuses on the box for a reason that is a code defect; the V6 digest measures beyond what the
  reading lane should carry (Greg's call 2); the teach stage refuses twice on a facts defect.
- Procedure: `restart_session REASON=<why>` on a commit before c7d10fd5 restores the pre-bedrock session (the request's
  pin then must be the old one: reverting BR-1's commit re-renders the request back to the old hash on the host);
  durable jobs are keyed by prompt, so no paid work is lost; `work/bedrock` and `work/derived` are moved aside with
  receipts, never deleted.
- Recovery time: one restart_session dispatch (about a minute of box time) plus the host re-render if the pin moves back.

### Specialist reports (full)
The three hand-backs of this chat: code-reviewer (REQUEST CHANGES: 2 Critical, 7 Important, 9 Minor), security-auditor
(no Critical/High; 1 Medium, 6 Low, 5 Info; no key or secret can be printed or published), test-engineer (0 Critical,
3 High, 8 Medium, 6 Low). Their findings are itemised above with the tests that pin them.
