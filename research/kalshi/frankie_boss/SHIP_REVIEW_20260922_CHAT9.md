# /ship on the chat-8 code commits 903b36f2..ba4d25ed, 2026-09-22 chat 9

Three specialists ran in parallel (code-reviewer, security-auditor, test-engineer) on the post-chat-8-review code: the row
window out of the code (ccf9bac1), the Friday anchor script (8388b441), module 1 = the partial-member take, the manifest
derivation and the Monday manifest (6261dcaf), the box ingest wrapper and its fixes (fd2922bf, 90d0bb76, f6b1cc5c,
8c089436, ba4d25ed). Merged here. Every Required, Medium and Critical-class finding is FIXED on this branch with the test
that would have caught it, each shown failing before the fix (a2f32bae, d68c0b90, 68340beb, 094e06b1, 891bd26a). The
build the review sat in front of, sections 4.2 and 4.4 as V6 tables (BR-9), is built and shipped in the same chat
(da294b91). Nothing has run on the host, Pod or endpoint; the box ran one read-only status probe at open (run 35688540984).

## Ship Decision: GO (for the Monday ingest, checkpoint E and the full rerun from the beginning, each step on Greg's go; nothing runs by itself)

### Blockers (all fixed)
- [code-reviewer Required, security-auditor Medium] `frankie_box_ingest_block.sh` checked out the markets tree at the top for
  EVERY action, before `units_idle`, on a BRANCH NAME whose default was another branch: a running cycle unit lazy-loads
  modules from that checkout, and the tool that decides what is ingested came from whatever the branch held at run time.
  Fixed (68340beb): `prepare()` = units idle, then the checkout of the DISPATCHED COMMIT (`MARKETS_SHA`, set by
  `frankie_box_run.yml` from GITHUB_SHA, set last so no variable replaces it; the wrapper refuses a HEAD that differs), then
  the manifest; `status` touches no git. Tests: `test_the_wrapper_checks_out_the_dispatched_commit_only_after_the_units_are_idle_and_status_moves_nothing`.
- [security-auditor Medium] the fetch heredoc trusted `manifest.block` and every `member_key` before any validation and ran
  as root: a crafted committed manifest could place bytes at any path on the box. Fixed (68340beb): the manifest is validated
  by the tool's own `block_source_scope` before any path is built, every destination is realpath-pinned under the data
  directory, `BLOCK` is digits and underscores, MAP_URL and every map entry must be https amazonaws (`--proto =https`,
  `--url`), WORKERS is bounded by the box's CPUs and CANARY checked on its own, receipts are written once, a file that
  appears at a destination during a download is never overwritten. Test: `test_the_wrapper_validates_the_manifest_with_the_tools_own_scope_pins_every_destination_and_bounds_its_inputs`.
- [code-reviewer Required, test-engineer Critical 1] a partition that ENDED at its take was accepted as a verified boundary
  (`following is None`), though the manifest declared take < partition count. Fixed (a2f32bae): refused with the counts.
  Test: `test_a_take_that_reaches_the_end_of_its_partition_is_refused_not_receipted_as_a_boundary`.
- [code-reviewer Required, test-engineer Critical 3] the take's `break` came before the canary stop, so a canary of exactly
  the take on the last member ran `complete()` and wrote an ingestion receipt inside a canary directory. Fixed (a2f32bae):
  the canary stop precedes the take. Test: `test_a_canary_that_ends_exactly_at_the_take_claims_nothing`.
- [test-engineer Critical 2 and High 6] a partial member that was not the last member let the next member be ingested whole
  after the take with completion claimed; two partial members were accepted. Fixed (a2f32bae): one partial member, and it
  is the last, refused at `partial_takes` before any record is decoded. Test: `test_a_partial_member_must_be_the_last_member_and_there_is_one`.
- [code-reviewer Required] `frankie_box_friday_anchor.sh` decoded with zstandard's `stream_reader` at its default, which
  stops after the FIRST zstd frame, and (security-auditor Low) decoded the checked path rather than the checked bytes.
  Fixed (094e06b1): the ingest's own multi-frame loop (`decompressobj`, `unused_data`, `eof`), the bytes hashed as they are
  decoded and the receipt refused unless they equal the pin, `zstd_frames` and `decoded_sha256` in the receipt, receipt
  written once. The committed anchor record carries a `decode_caveat` (the value itself untouched; a re-run on the box is
  Greg's word). Test: `test_the_decode_reads_across_zstd_frames_and_hashes_the_bytes_it_decodes`.
- [test-engineer Critical 4 and 5, code-reviewer Optional] `derive_trading_day_manifest` replayed in the SESSIONS list order
  (a reordered staged manifest put Monday's UTC file before Sunday's), raised KeyError on a missing halt count, and carried
  a clock in the hashed body so nobody could re-derive the committed file. Fixed (d68c0b90): the sources' member_index is
  the order, a session naming no source or missing a measured field is refused with the reason, the clock is gone; the
  committed Monday manifest re-derived byte for byte (hash 79ea97f8 -> a399377b; partitions, sha256s, counts and the take
  unchanged; the box's fetched partitions still verify). Tests: `test_contributions_replay_in_source_order_whatever_the_sessions_list_order`,
  `test_a_staged_manifest_without_measured_halt_counts_is_refused_with_the_reason`,
  `test_the_committed_monday_manifest_is_the_derivation_of_the_staged_block_byte_for_byte`.
- [test-engineer, CI] the ingest, derivation and row-window guard suites ran in no workflow. Fixed (891bd26a): they join the
  torch-equipped pytest list of `frankie_journal_stack.yml`.

### Recommended fixes (done)
- [security-auditor Info] the receipt names the partition count `declared_partition_mbo_records` (never measured; a2f32bae).
- [code-reviewer Nit] header default 32 -> 31; `MANIFEST` refuses `..` and a subdirectory (68340beb).

### Acknowledged risks (shipping anyway)
- The Friday anchor's record and trade totals are the first frame's if the object holds more than one frame; the anchor at
  20:59:56.64Z lies 3.4 s before the halt, so a truncated read is unlikely but unproven until the re-run (Greg's word).
- [security-auditor Low] the presigned map URL persists in SSM command history (about 30 days, within the account, live for
  `presign_hours`); a per-run SecureString or a cap on `presign_hours` is Greg's AWS call. Not changed.
- The cycle's own box scripts (`frankie_box_session.sh`, the restore script) still check out `MARKETS_REF` by branch name;
  the same fix applies and is ported on the next cycle-side change, on Greg's word (they are the cycle's; HOLD).
- [security-auditor Info] the box's git fetch credential path is unverified (a `git remote -v` probe, on Greg's word);
  `zstandard` is unpinned in the box venv (0.25.0 recorded).
- [test-engineer, code-reviewer Optional] the row-window guard's regex misses some spellings (`ROW_WINDOW = 4096`,
  `4_096`, a YAML value); the required-argument signature test is the real guard. Widening is a later task.
- [code-reviewer Optional] the encoder payload V2 changes the registry digest: the first run's retained preparation and
  granite-context receipts are not resumable under V2 (consistent with a full rerun from the beginning; noted for step 1b).
- BR-9 enlarges the V6 digest by the two sections' tables (on cycle 0's rows: 6 companion rows, 6 declarations, 1 pair,
  6 mirror rows, 1 rule); checkpoint E re-measures the digest (Greg's call 2, the reading cost).

### Rollback plan
- Trigger conditions: the ingest refuses the Monday manifest at the take (a count the fix now checks), a fetch refusal on a
  pinned partition, the V6 digest failing its own parse-back on the box, or Greg's word.
- Rollback procedure: `git revert` the specific commit (each is one concern: a2f32bae the take, d68c0b90 the derivation and
  the manifest, 68340beb the wrapper and the workflow, 094e06b1 the anchor, 891bd26a the CI list, da294b91 BR-9); the box
  checks out whatever commit is dispatched, so a rollback on the box = dispatch the prior commit; no data moved anywhere.
- Recovery time objective: one commit and one dispatch (minutes); nothing on the box is deleted or overwritten by any path.

### Evidence at da294b91 (this container: torch 2.14.0+cpu, zstandard 0.25.0, databento-dbn 0.62.0, boto3 1.42.23)
- The block suites (ingest, derive, block scope, stage): 22 passed (the eight new tests shown failing first).
- The two box contract suites: 5 passed on the new scripts; the same tests 3 failed on the old bytes (shown).
- The codecs CI list (21 files): 198 passed torch present; torch hidden by the notorch stub: 198 passed.
- The frankie_boss family (row window, context session, context qsv, compact journal, sunday*, run_actual*, actual_host*,
  day_pipeline, launch_pins): 101 passed, 8 failed = boto3 absent at that moment (the baseline set), 9 passed once boto3
  was installed.
- BR-9's four suites: 72 passed; the producers worktree at 2ebb8ce8 clean (`git status --porcelain` empty).

### Specialist reports (summaries)
- code-reviewer: REQUEST CHANGES; no Critical; four Required (the wrapper's checkout order, the take at EOF, the canary at
  the take, the anchor's single-frame decode); Optional: the derivation's clock in the hash, the duplicated weekend roll,
  the two counts for one file, the take vs before_halt binding, the guard regex, the V2 digest change, the branch default;
  done well: the removal complete in the live tree, the take reconciled by the untouched pinned stack, halt semantics
  consistent in three places, the wrapper never overwrites.
- security-auditor: 0 Critical, 0 High, 2 Medium (the fetch's unvalidated paths; the mutable branch checkout), 5 Low, 5 Info;
  the row-window change sound (model_context_rows reaches initialize only through the digest-checked verified schedule);
  secrets clean across the range.
- test-engineer: the nine named suites (4 could not collect here for torch/zstandard, since installed); the codecs list
  191 passed; probes: the guard catches a re-added literal and default, misses some spellings; the derivation reproduces
  the committed file with the clock frozen; partial_takes accepts two partials (now refused); 25 recommended tests, the
  five Critical ones written and green here, the rest on the after-run list.
