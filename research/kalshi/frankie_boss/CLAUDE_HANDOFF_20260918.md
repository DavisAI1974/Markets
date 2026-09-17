# Claude handoff - Frankie/BOSS, 2026-09-18 (session: pre-existing test errors root-caused; audit finding 6 first slice)

Continues `CLAUDE_HANDOFF_20260917.md`. Branch `claude/first-run-using-agent-skills-bd52fj` (also pushed to the harness
branch `claude/first-run-using-agent-skills-maubxe`). Launch is HOLD. Nothing here ran Frankie, Granite, the Pod, EC2, S3
or any result-bearing cycle; no workflow was touched. Git-only work plus container package installs.

## Family run: 1018 passed, 1 skipped, 0 failed, 0 errors, NOTHING deselected

Command (repo root, `PYTHONPATH=.:research/kalshi/frankie_boss:research/kalshi/frankie_boss/tests`):
`python -m pytest -q research/kalshi/frankie_boss/tests/test_granite*.py .../test_sunday*.py .../test_run_actual*.py
.../test_frankie_controller.py .../test_actual_host*.py` -> 1018 passed, 1 skipped in 95 s. Baseline reproduced first on
the untouched tree: 8 failed, 981 passed, 28 errors, 1 deselected (matches the 09-17 handoff exactly).

## Root causes (all pre-existing; none was a skip, deselect or loosened assertion)

| item | root cause | fix (commit) |
|---|---|---|
| 28 `test_granite_coordinator.py` setup errors | fixture used the stale third context `max_model_len=3000`; under it, the `verify_directory` stub predated the `progress` keyword; under both, `validate_startup` itself pinned the argv WITHOUT the chunked-prefill flags `granite_startup` adds for the 131072 context, so every genuine receipt was refused | fixture uses `s.MAX_MODEL_LEN`, stub accepts kwargs, coordinator pins the prefill argv (`32ec520`) |
| `test_granite_bootstrap_stage` 9 != 8 puts | roster grew to 8 files + bundle when `granite_runpod_progress.py` was added (b1d4eba); literal never updated | count derives from `package.FILES` (`7b973a5`) |
| `test_granite_retained_start_guards` KeyError 'status' | Pod GET stub had no status; the ported migration rebind (ded118d) reads it before the start action | stub answers as a stopped Pod (`7b973a5`) |
| `test_granite_sagemaker[length]` | since 553f447 finish_reason `length` is the incomplete-output alert (`IncompleteModelOutput`, re-raised by `serve_shadow`), not a transport error | own test asserting the alert, its `.details` and the closed stream (`b351d89`) |
| `test_granite_retained_host` STALL + `cleanup` failure | both tests predated durable run ownership (18df7e9). The completion test's journal stub had no `client`, so `ActiveRunStore(journal.client, ...)` raised inside the watchdog's catch-all and the loop spun forever under a frozen clock | both tests claim ownership through the shared S3/Journal stubs and assert stop, memo and closed record; a `sleep` in the completion test is now an assertion failure, so a regression fails instead of hanging (`fd9ec3b`) |
| 3 `test_granite_context_stacked` + `test_granite_request_stage` | ENVIRONMENT: `databento_dbn` absent (codec pins SDK 0.62.0 exactly) and `cryptography` broken without `cffi` | `pip install cffi "databento-dbn==0.62.0"` (no commit) |
| `test_granite_sagemaker::test_native_boundary...` order-dependent | pytest imports `frankie_boss/__init__.py` as package at first setup and prepends `research/kalshi` to `sys.path`; a bare `forecast_contract` imported lazily then resolves to `research/kalshi/forecast_contract.py` (no `sha256_digest`). Only name the two directories share | `tests/conftest.py` caches the intended module at collection (`a34b67c`) |

Real code weakness surfaced, not changed: `granite_retained_lifecycle.start_once` reads `info['intent']['name']` for a
RUNNING Pod; an intent without a name is a KeyError, not a clean refusal.

## Container environment (this session)

Installed: CPU torch 2.14, zstandard, boto3, pytest-timeout, cffi, `databento-dbn==0.62.0`. `transformers`/`databento`
absent. Fetched commit `996d121c` (agent-lineage seed writer) which `test_authority_map.py` reads with `git show`; a
clone without it fails two of that file's tests for no code reason.

## Audit finding 6 (authority map): first slice done, second slice is a decision

Done (`bd28fdf5`): stores `principal_session_artifacts` and `classroom_audit_evidence` declared (writer, readers,
identity, protection, attribution); correction recorded that the classroom answer key and full grade live outside the
model-facing principal directory; the five `frankie_principal_adapter.py` symbols the file-local checker tainted through
the frozen-knowledge names are declared under `collision_check.declared_principal_directory_writers` with the reason, and
the test admits protected writes only for declared pairs and refuses stale declarations; `sunday_20260915_package`
(the retained first-run copy) excluded from the scan.

STILL RED (pre-existing, now visible): `test_authority_map.py::test_actual_boss_direct_journal_users_match_declared_semantic_owners`.
The collision check predates the compact-source/reducer/prefix stack. Undeclared direct store users on the live tree:
- `journal_constructors`: `frankie_source_mapping.bind_prefix`, `online_source_prefix.snapshot_closed_prefix`,
  `source_recovery.rehydrate_source`, `sunday_execution.JournalWitness.checkpoint`,
  `journal_prefix_snapshot.snapshot_journal_prefix`.
- `physical_connects` (26): `compact_source`, `feedback_cycle`, `closed_source_lineage`, `online_source_prefix`,
  `source_lineage_resume`, `compact_journal` (writer+reader), `granite_runpod_probe`, `boss_training_checkpoint`,
  `journal_stack_execution`, `source_recovery` (2), `compact_journal_snapshot`, `verified_journal_reader` (2),
  `prepared_context_cache._stored_tail`, `granite_runpod_jobs.JobStore._db`, `frankie_journal_reader`,
  `compact_conformance_reader`, `operations/ingest_block_sources`, `operations/benchmark_reduction_stack`,
  `operations/benchmark_native_learner_direct`, `operations/run_actual_sunday.ActualHost` (3).
Each needs its semantic-owner decision (reader vs writer, which store) declared in `collision_check`; several are the
gold-standard stack (declare, never rebuild). A blanket declaration would defeat the check, so it was not made.

## Audit finding 7 (science-byte exceptions): runtime identity recorded

On this tree vs lawful ancestor `050c5056` the two exceptions are: `c15_journal.py` blob `a2dd5e9b` (ancestor
`06893a1c`, 35 lines: typed pack fast path) and `prepared_context_cache.py` blob `8062f602` (ancestor `479f8e75`, 29
lines: reader-owned `stored_tail`). All other listed science files are blob-identical. Any launch configuration must pin
these two blobs, not claim byte-identity with `050c5056`.

## Item 1 (Greg's native row count) - inventory, still pending his number

Code: `native_mbo_encoder.py:24` `T_CTX = 4096` (provisional), `sunday_native_runtime.py:37` `DEVELOPMENT['context_rows']`,
`sunday_schedule.py:73` `model_context_rows`, `operations/build_remaining_sunday_prefixes.py:336` (reads DEVELOPMENT).
Docs: `SPEC-native-mbo-encoder.md`, `NATIVE_MAPPING_BUILD_HANDOFF_20260907.md`, `CLAUDE_TO_CODEX_FULL_EVIDENCE_RULING_20260907.md`.
Changing it changes the schedule hash and run identity (fine for a new run). Not touched.

## Not done (in priority order for the next chat)

1. Finding 6 second slice: the ownership declarations above (turns the last red test green honestly).
2. Finding 3: `operations/run_actual_sunday_compact_source.py` main() substitutes its host into the LAWFUL checkout's
   `actual.main()` (base route, base adapter); the classroom composition lives in `run_actual_sunday_classroom.py`.
   Result-bearing compact-source dispatch must compose through the classroom runner or refuse when the classroom
   package/adapter is absent. Design decision; not started.
3. Findings 2, 4, 5, 8: launch pins (receiver `2ebb8ce8`, fresh reviewed config), sealed/output admission on the BOSS
   boundary (`frankie_principal_adapter._request`/`recover`), independent Memory A proof, remote receiver checkout.
4. Token shrinks 3.1-3.4 (need a served-Granite check: HOLD), CPU items (8 threads declared in the fresh configuration,
   `--workers` default, the review's free CPU wins).

## Do not

Run Frankie, Granite, the Pod, EC2 or any result-bearing cycle without Greg's go. Rebuild the prefix/reducer machinery.
Reintroduce the retired Granite smoke context anywhere. Quote token projections at 4,096 rows. Average anything. Push a
workflow. Skip or deselect a test to get green.
