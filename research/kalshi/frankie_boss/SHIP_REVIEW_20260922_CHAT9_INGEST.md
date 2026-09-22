# /ship on the ingest-speed commits b606dcdc..39628236, 2026-09-22 chat 9 (Greg: "we just want time")

The code-reviewer persona ran to completion; Greg stopped the security-auditor and the test-engineer while the Monday
ingest was being dispatched ("we can worry tests later"), so this decision merges ONE specialist report with the main
session's own verification (the box canary, the full-path differential test the reviewer proposed and which passed as
written, the launch-pin and identity checks). Nothing here touches the box: the Monday ingest (run 35694087514) runs on
2ae4da20; every commit after it is a correction to the record, the receipt, the cadence and the tests, byte-identical on
the journal.

## Ship Decision: GO (the Monday ingest is running on Greg's word; the corrections below ride the next dispatch)

### Blockers
- None. The code-reviewer found no Critical issue; the box canary over the change (run 35693868307) ran 20,000 records at
  1.77 ms each with the builder's own differential check refusing nothing; the reviewer's scratch differential over EVERY
  adapter mutation path found the raw and compact journals row-for-row byte-identical, and that stream is now the test
  `test_every_adapter_path_composes_byte_identically_at_the_default_cadence_and_on_every_record` (passed as written).

### Required (all fixed, 39628236)
- [code-reviewer] `launch_pins.NEXT_RUN['science_byte_exceptions']` pinned c15_journal.py at the PRE-range blob a2dd5e9b;
  the blob that runs is dd323e2a (PrePacked, SerializedObservation, OBSERVATION_SENTINEL). Fixed: the pin names the
  running blob, with the note that `c15_registry.implementation_identity()` now hashes three changed files
  (c15_builder, c15_observer, c15_journal), so the builder's state_hash, completion digest and checkpoints differ from
  the pre-range code's and the prefix-batch re-pin (step 1b of the full rerun) covers it. "Byte-identical" in the
  commit messages is true of the JOURNAL BYTES; the builder identity is re-minted. Greg's call under audit finding 7
  stands recorded here, not assumed.
- [code-reviewer] the completion receipt enumerated its keys and `packing` was not among them (the canary receipt had
  it; the test asserted the return value, not the written file). Fixed: the receipt carries `packing` and the measured
  `boxes`; `test_main_writes_packing_into_both_receipts` drives main() and reads both files. The Monday ingest now
  running writes the OLD receipt (no packing key); its box count comes from the wrapper's `status` readout (e63d68bd).
- [code-reviewer] the differential-check cadence counted per builder while composers are per instrument. Fixed: each
  composer counts its own observations; `OBSERVATION_CHECK_EVERY = 64` named with its exposure window stated (up to 63
  unchecked observations between checks; the codec re-parses every spliced body at flush and refuses a non-canonical
  one; completion is impossible after a refusal). Test: `test_the_differential_check_counts_per_instrument_composer`.
- [code-reviewer] no test exercised the composer's deletion branch, the level pop, priority-lost and side-change
  modifies, the missing modify, the duplicate add or the F_TOB clear. Fixed: the full-path differential test above.

### Acknowledged risks (shipping anyway)
- The canary's rate is the first 20,000 records of the day, when the book is thinnest; the body per group grows with the
  book, so the hour is a projection from the open, not a measurement of the day. The ingest receipt is the measurement.
- The completion receipt of the ingest now running lacks `packing` (fixed after dispatch); the box count is read by
  `status` from the container itself.
- Up to 63 observations can be written between differential checks; the full-path test and the codec's canonical
  re-parse are the two guards; a persisting drift is refused with those bodies in an unsealed, uncompletable container.
- `compact_build_journal.close()` never flushes pending rows, so a refusal's FAILED entry and the partial block are
  discarded (pre-existing; the container stays unsealed and uncompletable; the wrapper keeps the directory). Changing
  that is Greg's call.
- The two stopped personas: no security or coverage report on this range beyond the code-reviewer's security and test
  axes and the main session's checks (the profile writes only profile.txt in the run directory; no key or URL in any
  output; the subprocess test runs --help only).

### Rollback plan
- Trigger: the Monday ingest's receipt not reconciling (the pinned conformance stack refuses), a refusal by the
  differential check, or a head hash that a `--writer both` run disagrees with.
- Procedure: `git revert` 022053eb (the incremental observation) and 39628236 with it; the writer falls back to the tree
  path (b884fc7f), still faster than the pre-range code; the box checks out whatever commit is dispatched; nothing on the
  box is deleted or overwritten by any path.
- Recovery time objective: one commit and one dispatch.

### Evidence at 39628236 (this container)
- test_compact_build_journal, test_ingest_block_sources, test_launch_pins, test_c15_full_evidence, test_c15_integration,
  test_mbo_resume_state: 50 passed. The reviewer's wider run: 123 passed, 4 failed, all four failing identically on a
  pristine b606dcdc export (authority_map x3 on a commit absent from this clone and a records/ protected-write finding;
  source_recovery's pre-existing StopIteration).
- The box: run 35693868307, 20,000 records, 35.4 s, 564.97 records/s, 1.77 ms/record, 1.0 hour projected.

### Specialist report (summary)
- code-reviewer: REQUEST CHANGES, nothing Critical, four Required (above), Optional: aligned fragment lists so the
  observation's joins run in C (the remaining O(book) Python per observation), skip the level refresh on T/F/N
  messages, `rebuild()` emitting an empty level that `note()` would pop (unreachable through the adapter), `close()`
  discarding a refusal's FAILED entry, the receipt recording bounds not the outcome (fixed: `boxes`), the compact
  branch inlined in apply() with state born through `__dict__`; done well: the sentinel is a full tagged node refused
  unless exactly once, the codec re-parses spliced bodies, `_prepacked` keys on the copied field tuple, the sealed
  observation refuses mapping reads, the box-import fix pinned by a test that runs the tool as the box does.
