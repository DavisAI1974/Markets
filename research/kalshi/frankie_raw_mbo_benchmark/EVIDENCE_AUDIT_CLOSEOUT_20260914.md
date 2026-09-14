# Agent evidence audit closeout, 2026-09-14

Branch: `codex/frankie-agent-evidence-fixes-20260914`, based on 9006b633.
This is the existing committed-file agent path. The BOSS build remains on
`codex/boss-full-evidence-20260907`; the trees are not yet integrated.

## Fix follow-up, 2026-09-14

The owner explicitly removed the requirement to run/promote every earlier roster
day before admitting later findings. October 1 remains MISSING; no run or evidence
was invented. Attribution, source-day validation, content identity and veto checks
remain. The current seed retains all 44 previous VERIFIED findings exactly and
adds 18 Sunday findings as NEW. All historical file-seed entries are unchanged.

Current seed: 244,923 bytes, SHA-256
`b814bb58f03d506f1643a162ff0ca1e94e17a7f8e90d533d844e86b1995b4f07`.
Mission and knowledge-manifest pins were regenerated. The frozen prior used by
Sunday run 33746436209 remains 166,700 bytes, SHA-256
`4a47b09d5b19a9165c570f9432d2f3190a657843009536d5dad9a6bd99d83f4a`.
Archived principal-run files were not changed. The refreshed carry is not the
frozen prior for a historical Sunday comparison.

Windows fixes use Git Bash and stdin for workflow tests, explicit native Python
for the fake AWS command, and LF fixture bytes. Workflow bodies and production
rescue behavior are unchanged. Seed writing now preserves the hashed LF bytes;
checking compares actual bytes and rejects text-equivalent CRLF drift.

Final verification: **2,082 passed, zero failures/errors/skips**, across two
disjoint batches covering the complete legacy-agent test directory: 53 Windows
workflow/knowledge/helper tests (236.44 seconds) and all other 2,029 tests
(135.95 seconds). The seed/findings 36-test and delivery 29-test focused runs
overlap these totals and are not added. All four seed/knowledge regeneration
checks, Python compilation and Git whitespace checks passed. This verifies the
Windows host; it is not a separate Linux CI or BOSS integration result.

This follow-up is fixes only. No replay, Granite run, integration build or build-doc
organization was performed. The earlier baseline failures below are historical;
the owner's explicit policy change supersedes their chronology instruction.

## Reviewed fixes

- d9e7f809 preserves original source fields, rtype, missing/null distinctions and
  SDK wire bytes beside normalized fields. Unsupported JSON types reject before
  book mutation. Ledger creation refuses existing files; reconciliation verifies
  actual count/size/hash and close flushes/fsyncs. Original V4 is unchanged.
- fdabc363 refuses duplicate/skipped groups and delivers lawful sidecar rows
  through an indexed disk queue even when an earlier emitted row has a future
  clock. Source bytes remain unchanged; ordering within a delivery uses source
  ordinal. Exact integer nanoseconds and existing legacy float-clock semantics
  are preserved. Physical byte/hash and full row accounting survive partial and
  error paths; handles close without claiming unread data was consumed.
- 81d8a24a verifies manifest self-hash/roster before fetch, suppresses presigned URL
  contents in download errors, rehashes actual ledger/result bytes at emission,
  and validates knowledge bytes against the pinned corpus. Completion requires
  actual delivery/stream receipts, exact three-file witnesses, matching run/arm,
  all READ statuses and terminal withheld-row consumption.
- 28237baa migrates spawn-gate fixtures to actual pinned knowledge bytes. Tests
  exercise the stronger gate without mocking it away.

Every slice received independent review. Source ledgers, scientific calculations,
original S121 and Memory A were not rewritten. No replay or model run occurred.

## Verification and remaining baseline failures

Final broad suite: **2,053 passed, 15 failed, 11 errors**, 171.18 seconds.
The repaired emitter/staging modules pass all 79 tests. Focused source/sink suite:
64 passed; stream/crosswalk/emitter: 218 passed including an unchanged real
NativeReplayDriver fixture. Counts overlap and must not be summed.

The remaining failures are outside the changed behavior:

1. A-memory chronology: three failed tests and eleven setup errors reproduce at
   clean 9006b633. October 3 findings exist without the prior October 1 promotion
   required by build_a_memory_seed. Resolve the real frozen memory provenance
   before Sunday comparison; never fabricate a promotion, remove findings or
   weaken the chronology rule merely to obtain a green test.
2. Windows workflow/fixture execution: twelve failures in the final broad run.
   The same four modules at clean 9006b633 reproduce nine failures/41 passes;
   cleanup failure counts vary. The WSL bash shim misreads Windows paths, shell
   quoting and temporary-directory cleanup fail, and a fixture writes CRLF while
   expecting LF. This does not establish Linux CI success; the whole legacy suite
   is explicitly not green.

## Required agent procedure

Use fetch_frankie_ledgers fetch with the delivery manifest, then emit_frankie_spawn
with --result, --delivery-receipt and --ledger-dir. Omitting --knowledge-receipt
builds the knowledge bundle, receipt and pre-call receipt beside the prompt.
Spawn Frankie against the emitted prompt and three ledgers. He computes from
the lawful observations: calculation_result.json and lifecycle per-section rows
are runner output, not his independently established evidence or findings.

Exhaust the stream, then call drain_withheld and retain terminal accounting. Never
backfill terminal-only evidence into an earlier decision. native_staging read-back
now requires --stream-receipt alongside actual delivery/knowledge/bundle/prompt
and output files. Byte/accounting verification is not proof of comprehension.

Commit/push agent outputs as they land. Do not seed conclusions from an earlier
run. Attribute coordinator inquiry pointers in confidence_basis. The next requested
comparison is Sunday 2021-10-03, with prior A-memory run 33746436209 and earlier
A-clean run 33630348943 available for comparison after independent output filing.

The next task must finish BOSS-to-agent integration and the rest of the initial
build, including actual Granite model integration, before the deferred Claude
addendum. See the BOSS branch's EVIDENCE_AUDIT_CLOSEOUT_20260914.md and current
task maps. Do not replace this agent path with another API/calculation runner.
