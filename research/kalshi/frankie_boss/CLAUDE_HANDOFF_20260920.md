# Claude handoff - Frankie/BOSS, 2026-09-20 (session: final checks result recorded)

Continues `CLAUDE_HANDOFF_20260918.md` and the operator drop-in `DROP_IN_CLAUDE_20260920.md`.
Work branch `claude/frankie-launch-verification-lqmv0m`, cut from
`codex/frankie-launch-two-cycle-20260919` at `a5ad20bcfe51d4f6478dd1632ad82ca717305f29` (the pushed
tip was verified first). The local harness checkout arrived on a stale divergent tip `9c9c4c1d` that
is not an ancestor of the branch; it was discarded, not built on.

Launch stays HOLD. This session ran no Frankie, Granite, Pod, EC2, S3 or result-bearing action, read
or wrote no retained S3 prefix, and touched no workflow. `a9ab5ec4` was not reverted and
`codex/journal-reduction-stack-20260915` was not touched. Nothing was written to a PC C: or E: drive.

## Done: ordered item 1, the final checks result is now durable

`runs/20260920/checks-only-validation.md` records it, read back from the Actions API and the
downloaded run log archive rather than from the operator summary. Headline: run 35497376513 on
`a5ad20bc` completed success, `checks` success with `sources`/`journal`/`cleanup`/`host` all skipped,
the scientific family at 1101 passed, 1 skipped, 3 warnings in 79.95s, and the receiver step at 352
passed with 234 subtests passed against the frozen receiver `7b98617b`, which matches
`launch_pins.py` `receiver_commit`.

Two corrections to what can be claimed from it, both recorded in the ledger entry:

- The dispatch inputs are not exposed by the run API. `day=20211003`, `cycles=2`, `checks_only=true`,
  `keep_compute=true` stay operator-reported. The job skip pattern corroborates `checks_only=true`;
  `keep_compute` has no observable effect in a run where no compute job started, so it is neither
  confirmed nor contradicted.
- The three warnings are one environment `DeprecationWarning` from `multiprocessing/popen_fork.py:73`
  under two `test_granite_runpod_cloud_control.py` tests. Not assertion failures.

The drop-in's own item 1 named the earlier run 35497249802 at the code tip `fbbc5ce9`. That is also
completed success and its logs carry the identical counts, so that item is closed too. Since
`a5ad20bc` adds only the docs commit on top of `fbbc5ce9`, the identical counts are the expected
result and confirm the docs commit changed no check.

## Not done, and why

Ordered item 2 (an actual two-cycle execution) is unstarted. Launch is HOLD and a go to run on Sunday
is not by itself permission to change a workflow, so this needs an explicit new authorization naming
the run.

Items 3 and 4 (sealed-absence receipts for every absent downstream artifact, and a configuration
consumer that accepts only the signed proof) were read but not changed. Grounding for whoever picks
them up, from `frankie_principal_adapter.py` on this tree:

- `admission_policy` already refuses an undeclared admission (`ADMISSION_UNDECLARED`) at every use
  (prepare, request, recover), and already refuses the historical literals `NOT_PRESENTED` and
  `UNPROVEN` on a newly rendered run: they are admissible only on the retained-prompt route. A new
  two-cycle run therefore cannot silently take the unproven path today.
- `sealed_absence()` verifies schema `FRANKIE_SEALED_ABSENCE_PROOF_V1`, `all_absent is True`, a
  positive `tokens_checked` and a 64-character `receipt_sha256`, and returns `SEALED_UNPROVEN` for
  the literal.
- The one committed proof on this tree is `audits/SEALED_ABSENCE_PROOF_SUNDAY_CYCLE0_20260916.json`
  (cycle 0). There is no proof yet for the currently absent downstream artifacts.

So the open work is producing the per-artifact proofs, not loosening or re-deriving the consumer. The
remaining consumer question, which is a decision rather than a fix, is whether the retained-prompt
exemption should survive for the two-cycle run at all, given that the run is newly rendered.

The per-record ingest cost item is untouched and remains the scale blocker: 37.3 ms/record at about
97 percent dedication implies roughly 4.9 days for four weeks on the small runner. Fewer partitions
remove per-partition overhead, but no measurement yet shows per-entry work moved, so no scale claim
is available. Note that the operator note and the drop-in number this item differently (4 versus 5);
it is the per-record ingest cost item under either numbering.

## Frankie state, unchanged by this session

The classroom package and the model-visible pre-message exist. There is still no verified initial
principal response, classroom grade, correction receipt or configuration receipt. The native run last
reached `boss_reasoning` at cursor 3261 with completed 0. The retained AWS prefix proves durable
model-completion metadata exists; it does not prove the current two-cycle run produced any of the
four artifacts above, and the service-ready record was written before inference with
`inference_sent:false`.

Both EC2 hosts remain last-verified stopped: native `i-0e90ee6110ef609aa` in us-east-2, ingest
`i-035994afa8bdf66a5` in us-east-1. Neither was started, stopped or contacted here.

## Correction: the source facts are one measurement, not four (Greg, 2026-09-20)

The handoff line that carried "57,027 source records, 114,054 input plus applied entries, 1,189
target boxes, and the first two prefixes verified" as four verified source facts was wrong, and
restating it is why the same number keeps having to be re-explained. It is one measurement and two
derivations.

- **57,027 source records** is the measurement. It is the `record_count`, `member_counts` and
  `source_records` of the run 34962256086 verification receipt, and the `next_cursor` pinned in
  `operations/parallel_source/verify_snapshot.py`.
- **114,054 is not a second fact.** It is exactly 2 x 57,027, because every record emits one INPUT
  and one APPLIED entry. The relation holds exactly in all 18 committed prefix receipts under
  `sunday_20260915_package/FB/actual-prefixes/`: `journal_count == 2 * record_count` in every one,
  checked. Quoting it beside 57,027 double-counts a single measurement, which is what makes it look
  like independent corroboration when it is arithmetic. It is also not a token count.
- **1,189 is not a measurement either.** `journal_stack_execution.py:80` is
  `TARGET_BOXES = 1189`, Greg's chosen standard, and `partition_entries_for` derives the partition
  length from the target rather than the other way round. For this day it yields 96 entries per box
  and therefore 1,189 boxes; on a big day it clamps at `MAX_ROWS` and the day does not land on 1,189
  at all. Calling it a verified source fact states a configuration constant as an observation.

What is independently verified alongside the record count is the seal over that journal
(`journal_hash d8de0394...`, `state_hash d46ec933...`, `scope_hash 7460b519...`, pinned in
`verify_snapshot.py`), and the verification status of the prefixes, which is the first two. All 19
prefixes are not built.

The usable form, for anything that quotes this again: 57,027 source records, sealed by
`journal_hash d8de0394...`; the journal entry count is that doubled by construction; the box count
is a configured standard, not an observation; prefixes 1 and 2 verified, 19 not built.

Historical receipts and earlier handoffs that carry the old flat list were left untouched, per the
rule to append new evidence rather than rewrite receipts. The correction is made where it
propagates from: this handoff and the `CLAUDE.md` Frankie block.

## Locked in: the packing numbers, and the CI gap that let them keep being undone

Greg, 2026-09-20: the 7,129 stack will be rebuilt to pack other days more compactly, but the numbers
are to be locked first because they kept being undone.

They are already locked, executably, in `tests/test_partition_packing.py`, which is stronger than any
prose record:

- `assert TARGET_BOXES == 1189` (the standard going forward)
- `assert -(-sunday // 96) == 1189` and `assert partition_entries_for(sunday) == 96`
- `assert -(-sunday // 16) == 7129`, commented as what the old hardcoded literal produced, so the
  first run's box count is pinned as history rather than as a target
- `assert -(-weekday // MAX_ROWS) == 15581`, the clamp on a day the standard cannot reach
- the invariance proof: repacking yields the same entries, same bytes, same order and same seal,
  while the box count and container bytes change

Independently confirmed here by arithmetic: 114,054 / 16 = 7,129 boxes with 6 entries in the last,
which matches `ACTUAL_RUN_STATUS.md`'s "the final block contains six original entries"; 114,054 / 96
= 1,189 boxes, also with 6 in the last.

**The gap: nothing runs that test.** `grep -rn partition_packing .github/` returns nothing, and the
file matches none of the twelve globs in the checks step at `frankie_journal_stack.yml:296`. A revert
of `TARGET_BOXES` to 16 would therefore pass all 1,101 checks green and be invisible. That is the
likely mechanism behind the repeated undoing: the guard was written but never wired to CI, so nothing
could refuse the next revert. The fix is one line, adding the file to that pytest list. It is a
workflow edit and was NOT made here; it needs Greg's explicit authorization, since a go to run is not
permission to change a workflow.

The test could not be executed in this container: its import chain needs `torch`, which the checks
job installs as CPU torch 2.9.1 and which is absent here. That is an environment gap, not a failure.

**The contract for the coming rebuild**, already encoded in that test: decoded entries, their count,
their order and the head hash/seal are invariant; the container bytes and `compact_sha256` are free
to change. The first run's `compact_sha256 19603159...` no longer reproducing is the expected
consequence of the packing standard, not a regression. Neither 7,129 nor 1,189 is a source fact:
both are 114,054 divided by a packing choice, which is the derived-number rule above.
