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

Follow-up (same day, second session): the coordinator no longer keeps its own copy of the vLLM argv. One builder,
`granite_startup.vllm_argv(directory, max_model_len, served_model)`, produces both the Pod's startup receipt and the
coordinator's expectation, so the two cannot drift again. `test_granite_coordinator.py` + `test_granite_startup.py`: 47
passed. No hash of `granite_startup.py` is pinned in the repo (the bundle digest is computed at stage time).

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

## Audit findings 2-8, second session 2026-09-17 (Greg: bare-minimum tests; item 1 row count untouched)

No Frankie, Granite, Pod, EC2, S3 or workflow action. Each slice was verified by ONE run of its own test file only;
no family run this session (usage budget). Item 1 (`T_CTX` row count) is untouched by Greg's call: if the minimal
tests surface a problem with it, then dig into the number.

| finding | status | what landed |
|---|---|---|
| 6 authority map, second slice | CLOSED | `AUTHORITY_MAP.json` `collision_check` now declares every direct store user (5 journal constructors, 26 physical connects) and a new `direct_store_users` section giving each symbol its role (reader / writer / creator / reader+creator), store and evidence (the `?mode=ro` URI or the `create=True` form). No blanket entry. `test_authority_map.py` 5/5 (the last red test is green honestly) |
| 3 compact-source dispatch selects the base host | CLOSED | `operations/run_actual_sunday_compact_source.py`: `host_class(actual, tools_root, base=)` composes the compact-source host over `run_actual_sunday_classroom.ActualHost`; `main()` runs `classroom.main(host_class=...)` (explicit class, no module rebinding) and REFUSES (`SystemExit`) when the classroom runner/adapter is absent from the lawful checkout or not bound to it. `--verify-source-only` is unchanged and still proves nothing about dispatch. 4/4 |
| 4 sealed/output admission on the BOSS boundary | CLOSED on the boundary; receiver-side proof producer still absent | `frankie_principal_adapter.py`: constructor keyword `admission` = `{output_bundle: {principal_artifact, outputs_dir} | 'NOT_PRESENTED', sealed_proof: <FRANKIE_SEALED_ABSENCE_PROOF_V1 path> | 'UNPROVEN'}`. The historical literals are admissible ONLY with a retained prompt (a new render is never exempt). `prepare` passes `--principal-artifact/--outputs-dir` or the bare `--without-output-bundle` flag to the receiver; `_check_preparation` requires the receipt's `output_bundle_gate` to match the declared policy and, when VALIDATED, all 32 current ledgers (`CURRENT_RECEIVER_REQUIRED_LEDGERS`); the sealed proof is verified (`schema`, `all_absent`, `tokens_checked`, `receipt_sha256`) and witnessed; the attachment, the request and the recovered record all carry `admission` so a downstream carry can refuse NOT_PRESENTED/UNPROVEN. `None` = UNDECLARED: constructible (retained configurations), refused at prepare/request/recover naming the missing `principal_admission`. Threaded through `make_principal_adapter(admission=)`, both runners (`c.get('principal_admission')`) and `record_actual_frankie_response`. Receiver side: `native_sealed_absence.prove_sealed_absent` exists but NOTHING in the receiver produces the proof file yet (no CLI, no caller outside tests) - producing it is the next receiver slice. 16/16 adapter tests, classroom 5/5 + 8/8, sunday_execution green |
| 5 independent Memory A proof | BOSS witness built; receiver binding pending | `FrankiePrincipalAdapter._memory_witness()` writes `memory-a-witness.json` (`FRANKIE_BOSS_MEMORY_A_WITNESS_V1`): BOSS's own receipt over the served frozen Memory A files plus the knowledge receipt/bundle hashes, a file identity distinct from the seed's self-hashes; its sha travels in the attachment and is re-verified at request. `native_layer_crosswalk` clears `DEGENERATE_PROOF_SAME_AS_SUBJECT` only when the knowledge receipt's `a_memory_prior_package_proof` layer binds a receipt whose (path, sha256, bytes) differ from the subject package - binding this witness there is the receiver-side step, not done |
| 2 stale launch pins + 7 science-byte exceptions | validator built; fresh configuration not authored | `launch_pins.py`: `NEXT_RUN` pins receiver `2ebb8ce8...` (full sha), `stacked_v1`, 8 threads, 131072, 32 ledgers, and the two science blobs by full blob sha (finding 7); `validate(configuration, boss_commit=)` names EVERY violation (stale BOSS/receiver, the retired completion ref, undeclared or historical `principal_admission`, a desktop path per D34). The 2026-09-15 configuration is refused with all five reasons (`test_launch_pins.py` 1/1) and stays untouched as historical evidence. The fresh configuration itself needs the reviewed BOSS tip and a new completion ref: Greg's call |
| 8 remote receiver checkout without parent repository | BOSS refuses cleanly; host verification HOLD | `_code()` now refuses with `frozen receiver checkout is not a git repository at <root>; restore the receiver parent repository at the pinned commit` instead of a raw subprocess error. Verifying the actual checkout on the stopped host is a host action under HOLD |

Not run this session: the family suite. Next chat opens with ONE family run before anything else.

## Later the same day (2026-09-17, second session, Fable): the chain, the CPUs, the resize

- **The started workflow became the beginning-to-end chain.** `.github/workflows/frankie_journal_stack.yml` (the one that
  ran the gold-standard journal stack, run 34962256086) now carries: job `sources` (stage sources + host start), the
  ORIGINAL `journal` job unchanged (its verification receipt recorded as ingest, receipt 02), job `host` (prefixes,
  cycles under `go`, package, snapshot over SSM; host stop always; receipts committed, rendered as the job summary).
  Dispatch inputs: day, go, until, ingest_on (runner|host), runner (label). No cron. The push trigger on the codex branch
  still runs the journal job alone (a skipped `sources` is not a failure). Codex reviewed the CPU code read-only against
  the receipt commit `549efa73` and the pin `9a8f3f46`: dedication byte-identical; one progress-only hunk.
- **Orchestrator** `operations/day_pipeline.py` + `operations/day_pipeline.configuration.json` (no credential, no
  desktop path): seven idempotent stages, one git receipt each under `runs/<DAY>/`, gate = previous receipt's fields,
  resume from the first missing receipt, HOLD before cycles without `--go <source manifest hash>`, `--record ingest
  --from verification-receipt.json`, `--host-stop`. **CPU dedication is a measured gate**: worker CPU seconds per wall
  second (busy CPUs) must be at least half the dedicated worker CPUs (first run 2.9 on 3 = 0.97); a collapsed pool is
  refused with the numbers. `test_day_pipeline.py` 4/4.
- **The numbers, settled**: 32 = the Pod (Granite's CPUs; no worker pool, nothing declares threads there); 48 =
  `data_workers`, the compact reader's worker CAP (host CPUs minus the reserved consumer CPU decide the count), not a
  machine; 8 = the native step's declared thread identity; the old t3.xlarge data box is not in the pipeline.
- **Native host RESIZED** `i-0e90ee6110ef609aa` r7i.4xlarge -> r7i.8xlarge (32 vCPU / 256 GiB) while stopped, from this
  session with `ec2_host.py resize --type` (new action, stopped-only, readback-verified). The reader cap now resolves
  to 31 workers. Cost default in `ec2_host.py` is 3.60/h. Greg's decision; ingest stays on the runner by default.
- **Memory A is VALID (Greg)**: no validation day or separate source day exists in code; the crosswalk's
  DEGENERATE_PROOF_SAME_AS_SUBJECT is an ACCOUNTED status that gates nothing. Attestation in code
  (`frankie_principal_adapter.MEMORY_A_ATTESTATION`, written into every `memory-a-witness.json`).
- **Keys**: the AWS pair was installed in this container only (`~/.config/markets/env`, `~/.aws/credentials`, 600) for
  the resize; it does not survive the container. Rotation stays deferred until after the walk (standing decision).
- **Not done**: the host scripts `deploy/aws/host/day_schedule_prefixes.ps1` and `day_cycles.ps1` (each ends with one
  `PIPELINE_RECEIPT {json}` line carrying its gate fields); the Pod credential via SSM parameter; the receiver-side
  sealed-absence proof producer; the receiver binding of the BOSS Memory A witness; the fresh configuration (reviewed
  BOSS tip + new completion ref, Greg); `T_CTX` untouched by Greg's call; NO family run this session.

## 2026-09-17, third session (Opus, using-agent-skills then shipping-and-launch): the family run, and the two host scripts

No Frankie, Granite, Pod, EC2, S3 or workflow action; no dispatch; nothing result-bearing. Git-only work plus the
container package installs the previous session listed. Launch stays HOLD.

**The family run, first business, on the tip `d0966ee`**: `1018 passed, 1 skipped, 0 failed, 0 errors, nothing
deselected` in 99.7 s - the 09-18 baseline reproduced exactly. **Item 1 (`T_CTX`) did not surface**, so per Greg's
call the row count is untouched again.

**The gap the scripts could not be written around.** `day_pipeline._ssm()` built `ssm_run_ps1.py --instance ...
--script <path> --timeout N` and passed **no day**, while `ssm_run_ps1.py` sends the script file verbatim with no
substitution and the day / `run_directory` / `run_id` live inside the host-side run configuration. So a host script
had zero per-run information. Greg's call: pass it over SSM.

- `ssm_run_ps1.py` gains `--set NAME=VALUE` (repeatable), prepended as a PowerShell **single-quoted** assignment,
  which is literal - no interpolation, no subexpression. A name that is not a bare identifier, or a value carrying a
  quote or a newline, is **refused rather than escaped**, so there is still no quoting logic in that file.
- `day_pipeline._ssm()` passes `--set Day=<day>` plus every entry of a new `host_variables` map. The host's roots
  therefore live in the pipeline configuration (which `main()` already credential-scans and D34 audits), never as a
  literal inside a script that is sent to a live host.
- `_ssm()` returns `None` when no script is declared for a stage and `run_stage` refuses by name, so a null entry is
  a clean refusal instead of a missing-file error.

**The scripts** `deploy/aws/host/day_schedule_prefixes.ps1` (stage 4) and `day_cycles.ps1` (stage 5). Each refuses any
of `$Day/$ToolsRoot/$Python/$RunRoot` the sender did not supply or that still reads `HOST_*`; runs its tool through
`cmd.exe` so the redirection is owned there (the retained-script trap: under `Stop`, a native command's first stderr
line becomes a terminating error, which cost two earlier runs their tracebacks); tails its log; and ends with ONE
`PIPELINE_RECEIPT {json}` line. **Neither script rebuilds anything and neither invents a number**: the prefix receipt
is read back from the builder's own `full19-prefix-witnesses.json` (and refuses if `witnesses` disagrees with
`prefixes`), and the cycles receipt comes from the runner's own `all_nineteen_cycles_complete` line - an incomplete
run throws with the runner's own status and resumes next dispatch from the same run directory, rather than the script
counting directories and guessing.

**`host_scripts.ingest` is null on purpose (Greg, this session)**: *"Don't use bento. I get charges for that. Why
don't you use the workflow that is already there on git?"* Ingestion stays the journal-stack job already on git,
recorded with `--record ingest`. There is no second ingestion path to build or pay for, and the reason is now carried
in the configuration and asserted by a test, so a later session cannot quietly add one. **Measured while checking it:
nothing in this chain bills Databento** - `stage_block_sources.count_records` calls `db.DBNStore.from_bytes(raw)`, a
local decode of bytes already fetched from S3, and there is no `Historical`/`Live` client or `DATABENTO_API_KEY` read
anywhere under `frankie_boss/`. The only paid resources in the chain are S3 and the EC2 host.

**What is proven and what is not.** `test_day_pipeline.py` 6/6 and a new `test_host_day_scripts.py` 8/8. **There is no
PowerShell in this container and the host is under HOLD, so neither script has ever been executed.** What the new file
checks is the contract the orchestrator depends on: the four variables are named and an unfilled `HOST_*` placeholder
is refused; exactly one `PIPELINE_RECEIPT` line and it is last; its fields cover that stage's `day_pipeline.GATES`;
and no drive-letter path or credential word travels in a verbatim script. **Every one of those assertions was
negative-tested by mutating the real file until it fired** (NC-3's lesson: a guard whose firing branch never executed
is not tested) - drive literal, credential word, a second receipt line, a receipt that is not last, a renamed gate
field, a weakened placeholder check, and all four `--set` refusals.

**Open, and each one is Greg's.**
1. `host_variables` carries `HOST_TOOLS_ROOT` / `HOST_PYTHON` / `HOST_RUN_ROOT` placeholders. They are filled when the
   fresh run configuration is authored; until then both scripts refuse. The retained scripts used `C:\tools\Markets`
   for the tools checkout.
2. The scripts expect the day's run configuration at `<RunRoot>\<Day>\actual-host-configuration.json`. Nothing places
   it yet - that is the fresh-configuration step, and its `host_runtime.prefixes_directory` is what both scripts read.
3. `frankie_journal_stack.yml`'s `ingest_on` input still offers `host`, which now lands on the clean refusal above.
   **The workflow was NOT edited** - that needs Greg's go - so the stale description is recorded here instead.
4. Spec prerequisite 6 is still the real blocker on stage 5: the Pod credential reaches the runner on **stdin**, and a
   script sent over SSM has no stdin. Declared in `day_cycles.ps1`'s header rather than papered over. Until it is an
   SSM parameter read once, a cycle needing the Granite critic cannot complete from the chain.
