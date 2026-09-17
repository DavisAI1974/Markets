# Claude handoff - Frankie/BOSS, 2026-09-17 (session: Granite 4096 retirement + reconciliation)

Branch `claude/first-run-using-agent-skills-bd52fj`, tip `935f8c63` (this file's commit sits on top).
Launch is HOLD. Nothing here ran Frankie, Granite, the Pod, EC2, S3 or any result-bearing cycle.

## What this branch IS

The first tree that contains all three audited inputs (recovery `34301ac0`, classroom composition `d152dd82`, classroom
review `61c73a2d`) plus this session's work. The receiver `2ebb8ce8` is a pinned sibling checkout, not merged. Full
record with SHAs, conflict resolution and test evidence: `CLAUDE_RECONCILIATION_20260916.md`.

## Done this session (all pushed)

1. Reconciliation of the three audited trees (audit step 1). Conflict-free except one test file, resolved by carrying
   both parametrisations. Audit suites reproduce (99 + 21), integrated tree 100 + 21, classroom family 48.
2. Standing rules recorded in `CLAUDE.md` (top block) and here: Granite 4,096 context RETIRED; native `T_CTX = 4096`
   is provisional and pending Greg's row count; 114,054 is the journal ENTRY count (2 x 57,027), never a token figure;
   8 threads fixed; first-run prefixes/reducer stack are the gold standard.
3. Granite 4,096-token context removed from ALL Granite code (13 files). One constant `granite_runpod_admission.CONTEXT
   = 131072` is the only admissible context; output is bounded by the context alone (the 1,200 ceiling is gone); the
   proxy refuses to start without the pinned `GRANITE_MAX_MODEL_LEN`. Retired with it, per Greg: the finite-timeout
   direct Runpod critic (RunpodConfig admits only open-ended transport), the bounded cloud smoke launch controller, and
   the pinned 4096 smoke admission receipt `runpod_cloud_admission.json` (deleted). Remaining 4096 literals in Granite
   code: two BYTE bounds named as bytes (`MAX_PROBE_BODY_BYTES`, `MAX_RECORD_BYTES`) and the two retirement messages.
4. Prefix / reducer-stack verification: the prefix builder, snapshot, conformance reader, journal reader, stack
   execution and both Sunday operations scripts are blob-identical to the first run's runtime pin `9a8f3f46`. Nothing to
   revert. The 19 prefixes: `sunday_20260915_package/FB/actual-prefixes/`. First-run journal: 57,027 records = 114,054
   entries -> 7,129 gzip blocks of 16 (20.9x), verified in 715 s wall on GitHub run 34962256086 (parent + 3 workers).
   Greg's recollection of "about 1,200 boxes" is not in any receipt; 7,129 is.
5. Number provenance: the "114k/117k" Codex quoted is the journal entry count; the ~114k-116k TOKEN projection at
   4,096 rows in the token review and consolidated note is retired with the row context. Proven packet: 92,427 input
   tokens at 3,262 rows, 38,645 output tokens left. Further shrinks (token review 3.1-3.4, 24.1 -> ~19.4 tokens/row)
   are NOT implemented.

## Errors to correct next chat (pre-existing; identical on the untouched tree; NOT introduced here)

Family command (from repo root, `PYTHONPATH=.:research/kalshi/frankie_boss:research/kalshi/frankie_boss/tests`):
`python -m pytest -q research/kalshi/frankie_boss/tests/test_granite*.py tests/test_sunday*.py tests/test_run_actual*.py
tests/test_frankie_controller.py tests/test_actual_host*.py --deselect
"…/test_granite_retained_host.py::test_open_run_explicit_completion_still_stops_retained_pod"` -> 981 passed, 8 failed,
28 errors, 1 skipped.

- 8 FAILED:
  - `test_granite_bootstrap_stage.py::test_conditional_writes_readback_and_existing_reuse`
  - `test_granite_context_stacked.py::test_stacked_full_genesis_and_explicit_later_seed_reproduce_all_hashes`
  - `test_granite_context_stacked.py::test_stacked_missing_seed_gap_or_wrong_commitment_keeps_literal_hashes`
  - `test_granite_context_stacked.py::test_stacked_wire_and_adapter_exceptions_remain_literal_and_exact`
  - `test_granite_request_stage.py::test_public_artifact_hides_capability_and_binds_local_recipient_and_request`
  - `test_granite_retained_host.py::test_cleanup_uses_cached_ownership_without_storage`
  - `test_granite_retained_start_guards.py::test_start_claim_precedes_action_and_failure_never_authorizes_repeat`
  - `test_granite_sagemaker.py::test_unsupported_outputs_reject_and_close_stream[length]`
- 28 ERRORs, all `test_granite_coordinator.py` at setup: its fixture calls `make_plan(max_model_len=3000, ...)`
  (a stale third context value, refused since the allowlist existed); with 3000 -> 131072 the fixture still errors on a
  second, unrelated setup problem (not diagnosed; probe reverted). The whole file has been dormant.
- STALL: `test_granite_retained_host.py::test_open_run_explicit_completion_still_stops_retained_pod` hangs indefinitely
  here, on the untouched tree, and on the workstation (drop-in 2026-09-17 item 7). Not changed; deselected in runs.
- Also pre-existing in that file: `test_cleanup_uses_cached_ownership_without_storage` fails.
- Environment notes: this container needed CPU torch, zstandard and boto3 installed; `transformers`/`databento` are
  absent (some tests in the wider suite need them). Windows PYTHONPATH uses `;`.

## Open, in priority order

1. Greg's row count for the native context `T_CTX` / `context_rows` / `model_context_rows` / the prefix-builder guard
   (4 code sites, 3 docs). A window-size parameter; changing it changes the schedule hash and run identity (fine for a
   new run). Pending his number.
2. Audit findings 2-8 (`outputs/frankie-boss/20260916/prelaunch-audit/AUDIT.md` on
   `codex/frankie-prelaunch-audit-handoff-20260916`): stale launch pins (receiver must pin `2ebb8ce8`), compact-source
   host selection, sealed/output admission on the BOSS boundary, independent Memory A proof, `AUTHORITY_MAP.json`
   entries for classroom audit + principal artifacts, science-byte exceptions' runtime identity, remote receiver
   checkout without parent repo. The classroom tip's `WORK_IN_PROGRESS_FEED_OUTPUT_MEMORY_WIRING_20260916.md` lists the
   same targets as planned.
3. Token shrinks 3.1-3.4 (graph recipe, tick-integer prices, drop static nodes, one-letter codes). Model-facing: prompt
   bytes change -> codec hash rebind + one served-Granite check. Shrinking is a top priority job.
4. CPU: declare 8 threads in the fresh final configuration (nothing committed carries it yet); block ingestion
   `--workers` defaults to inline, pass cores-minus-one on Linux; the review's free CPU wins (fresh 15-process pool per
   drain importing torch, double row verification, two fsyncs per record, double pack) are unapplied.
5. `.github/workflows/granite_runpod_cloud_smoke.yml` still exists and would fail closed at the retired controller;
   deleting it is Greg's call.
6. `codex/journal-reduction-stack-20260915` carries one code file not on this tree:
   `operations/archive_completed_sunday_prefixes.py` (191 lines); the other 30 commits are outputs/documents.
7. The repo is PUBLIC (GitHub API: visibility public, forking allowed); handoffs carry the SSH proxy user, instance id
   and bucket name with the account number.
8. Carry the CLAUDE.md Frankie block to the trunk `claude/kalshi-s79-kickoff-ij8t9o` (needs Greg's permission to push
   there).

## Do not

Run Frankie, Granite, the Pod, EC2 or any result-bearing cycle without Greg's go. Rebuild the prefix/reducer machinery
(change dates only). Reintroduce 4096 anywhere in Granite code or as a context in tests/fixtures/docs. Quote token
projections at 4,096 rows. Average anything. Push a workflow.
