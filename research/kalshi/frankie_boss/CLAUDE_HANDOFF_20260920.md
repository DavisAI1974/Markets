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

Verified source facts are unchanged: 57,027 source records, 114,054 input plus applied entries, 1,189
target boxes, and the first two prefixes verified. All 19 prefixes are not built.
