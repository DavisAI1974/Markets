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

### Same session, after Greg's questions: two real defects, both found by asking "is it still going to hit the reducer?"

**Nothing runs from Databento, and the historical days are already in AWS.** The archive the chain reads is
`s3://bento-568968024170-us-east-2-an/nymex/ng_mbo_5y_v0/native/2021-10`. It was put there by the workflow Greg
means, `.github/workflows/ng_historical_mbo_5y_to_s3_20260820.yml` (`PREFIX: nymex/ng_mbo_5y_v0`), which is the ONLY
thing in the repo that reads `DATABENTO_API_KEY` - and it must not be re-run, because that one WOULD charge. The
bucket is merely NAMED bento; it is Greg's S3 bucket, not the vendor. `stage_block_sources.py` does an S3-to-S3
copy plus `db.DBNStore.from_bytes(raw)`, a local decode of bytes already fetched. No `Historical`/`Live` client
exists anywhere under `frankie_boss/`.

**Does it still get reduced? Yes, in exactly one place, and the prefix step is not it.** The reduction is
`operations/run_journal_stack.py` ("combined reductions") in the workflow's `journal` job. The prefix builder's
copier `compact_journal_snapshot.snapshot_compact_prefix` VERIFIES the compact journal's sha256 and READS it through
`VerifiedJournalReader` - it never re-reduces.

**Are the prefixes already ingested? For the first run's day only.** The 19 retained prefixes in
`sunday_20260915_package/FB/actual-prefixes/` are the 2021-10-03 Sunday reopen, 57,027 records. The staged block
`blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json` says for itself: `role: HELD_OUT_BLIND_BLOCK`,
`ingested: false`, `prefixes_built: false`, `scheduled: false`, `total_mbo_records: 6,471,475` over four members
(20211003 57,027 + 20211004 1,994,358 + 20211005 2,111,930 + 20211006 2,308,160). So those days have no prefixes
yet. **And the gold standard cannot be rebuilt by accident**: `materialize` calls the copier ONLY when a prefix's
receipt is absent, otherwise it re-verifies the snapshot sha; `save_new` is `xb`; the binding and
`full19-prefix-witnesses.json` are compared for equality and reused. Pointed at the retained directory the builder
copies nothing and writes nothing.

**DEFECT A - the journal job is pinned to ONE bundle, so an ingest receipt could be filed against a day it did not
reduce.** `parallel_source/cloud_transfer.load_request()` reads `.github/frankie-parallel-source-request.json`
hard-coded; it names a single `archive_sha256`/`bundle_manifest_sha256` (the first run's snapshot, 57,027 records)
and takes no day. The publication path is hard-coded `outputs/frankie-boss/20260915/reduction-stack`. So on a
dispatch with `--day 20211004`: `sources` stages that day correctly, `journal` reduces the FIXED first-run bundle,
and `--record ingest` files that receipt as 20211004's ingest. Every gate passed: a verified
`FRANKIE_COMBINED_JOURNAL_EXECUTION_V1` with sound CPU dedication. **This is S108 hole #8's shape exactly** -
present, numeric, right owner, self-consistent, and about the wrong source; consistency was never the test.

**DEFECT B - the staged record count was being recorded as null.** `gate_of('stage-sources')` read
`records`/`mbo_records`; `stage_block_sources.py` prints **`total_mbo_records`**. The early `return` skips the
None check the other stages get, and `require()` only asks whether the KEY is present - so `records: null` passed
the gate. **The unit test hid it**: the fixture printed `records=6470000`, a key the real tool never emits, so the
test asserted a contract reality does not honour.

**Both fixed in `day_pipeline.py`, and B is what makes A's guard possible.** `gate_of('stage-sources')` now reads
`total_mbo_records` first (older spellings kept) and refuses a line with no count at all. New
`reconcile_ingest(count)` requires the ingest receipt's `journal_count` to equal the day's staged records, on BOTH
ingest paths (`record_external` and the SSM host path), and names both numbers when it refuses. The fixture now
prints what the tool prints. `test_day_pipeline.py` 9/9 (three new), `test_host_day_scripts.py` 8/8.

**Open, Greg's call: the workflow itself is still pinned.** The orchestrator can now only REFUSE a mismatched
receipt - it cannot make the journal job reduce the right day. Parameterizing the `journal` job (its snapshot
request, and the hard-coded `20260915` publication path) by `inputs.day` is a workflow change, and workflow changes
need Greg's go, so nothing was edited. Until then a day other than the first run's will stop at ingest with the two
counts named, which is the correct outcome.

### Greg's correction, same session: the box count, and the scale problem behind it

**My evidence was wrong and he was right to push.** I read `ingested: false` / `prefixes_built: false` in
`blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json` as proof those days were not done. **Nothing in the repo ever
writes those flags true** - `stage_block_sources.py` writes them `false` at stage time and no code path updates
them. They are stage-time literals, not a state report. Withdrawn.

**What the Actions history does show** (not an argument, just what I could find): `frankie_journal_stack.yml` has
exactly ONE run ever - 34962256086, 2026-09-15 11:14:54 to 11:29:55, success - and the codex output branch's last
commit is 2026-09-15 21:29. Nothing on 09-16 or 09-17. If the four days were ingested elsewhere (a Codex session,
the host directly, another repo), that is where to look; it did not go through this workflow. Separately,
`ng_exhaustion_step1_receipt_count_20260823.yml` fires on every push to this branch and has failed 677 consecutive
times - noise worth killing.

**THE SCALE PROBLEM IS REAL, AND IT IS CPU-BOUND.** From the first run's receipt, not memory: 57,027 records,
715.19 s wall, 50.37 s parent CPU + 2,079.29 s worker CPU on 3 workers. **2,079/715 = 2.91 of 3 CPUs busy, 97%
dedication**, so the 715 s is compute, not transfer - there is no fixed overhead to amortise away. **37.3 ms of CPU
per record**, and it scales straight:

| | records | CPU-h | 4-vCPU runner | 32-vCPU host |
|---|---|---|---|---|
| Sunday 20211003 | 57,027 | 0.6 | 12 min | - |
| one weekday | 1,994,358 | 20.7 | 6.9 h | 0.7 h |
| the 4-day block | 6,471,475 | 67.1 | 22.4 h | 2.2 h |
| 4 weeks | ~34,000,000 | 352.7 | 4.9 days | 11.4 h |

Sunday is **1.6%** of the four-day block. Twelve minutes on the smallest day is exactly what hid this.

**THE BOX COUNT: 7,129 came from a hardcoded literal nobody had chosen.**
`journal_stack_execution.MigratingConformanceReader.entries()` partitioned with `range(0, count, 16)` and
`min(16, ...)`, and **every partition becomes exactly one block**, so 114,054 / 16 = 7,129 - the whole derivation.
`CompactWriter`'s `block_bytes` (4 MiB) and `MAX_ROWS` (256) never applied on this path: the loop INSERTs each
partition's block directly and bypasses `CompactWriter.add`. The blocks were averaging far under the byte budget
and nothing was flushing them but the literal.

**Now `PARTITION_ENTRIES = 96`** (Greg's call): 114,054 / 96 = **1,189 boxes**, his "about 1,200". It also cuts
per-partition overhead six-fold - each partition opens the source read-only and runs three queries, so 7,129 opens
become 1,189. The length is a constructor keyword bounded by `MAX_ROWS`, so a bad value refuses rather than writes
a malformed block, and `_convert_partition`'s existing `MAX_BYTES` check still refuses an oversized partition.

**Proved, not asserted**: `tests/test_partition_packing.py` runs the REAL reader over the same fixture at 96 and at
16 and asserts the projected entries, their order, the count, the head hash and the completion are identical while
the box count differs exactly as the arithmetic says; plus the first-run arithmetic (96 -> 1,189, 16 -> 7,129) and
refusal of an out-of-bound length. 7/7. Reduction stack + single-pass + compact: 26 passed. The workflow's own
standalone gate `test_journal_stack_execution.py` passes. **Family run after the change: 1018 passed, 1 skipped,
0 failed** - unchanged.

**THE BASELINE MOVES, DELIBERATELY.** The compact container's bytes and `compact_sha256` change; the first run's
`19603159...` no longer reproduces and a run under 96 is a new baseline. The prefixes and the reducer logic are
untouched - only the packing. The one live pin of that sha
(`operations/restore_existing_journal_archive.py`) restores the historical archive itself and is unaffected.
CLAUDE.md's "never rebuild these" rule now carries this as its one declared exception, so a later session does not
revert 96 to 16 believing it is protecting the gold standard.

**Still open on cost**: 37.3 ms/record is not explained by the packing alone. Six-fold fewer partitions removes
per-partition overhead, but the per-entry work (canonical re-serialisation, per-entry sha256, gzip level 6) has not
been profiled - and it cannot be profiled here, because the real bundle is 11.7 GB behind S3. The next measured run
gives the new per-record number; if it has not moved much, that profile is the next job.


### Greg, same session: 1,189 IS the gold standard for ingestion going forward

*"That 1200 was the thing that I thought I was calling the gold standard of what we want to do with the days we need
to ingest going forward. It was 1189."* So the number is not a property of the first run to be reproduced - it is the
TARGET for every day. Checked: `1189` appears nowhere in the repo or in any first-run artifact, so it was never a
recorded figure; it is Greg's call.

**Expressed as the standard rather than as a length.** `TARGET_BOXES = 1189`, and
`partition_entries_for(count) = clamp(ceil(count/TARGET_BOXES), 1, MAX_ROWS)` derives the partition length per day.
`MigratingConformanceReader(partition_entries=None)` (the default) derives it from `expected_count`; an explicit
length is still accepted, which is how the equivalence test runs the same journal two ways.

| day | entries | derived | boxes | |
|---|---|---|---|---|
| Sunday 20211003 | 114,054 | 96/box | **1,189** | the standard, exactly |
| one weekday | 3,988,716 | 256/box | 15,581 | needs 3,355/box for 1,189; ceiling is 256 |
| the 4-day block | 12,942,950 | 256/box | 50,559 | same ceiling |

**THE STANDARD IS NOT REACHABLE ON A BIG DAY, AND THAT IS ARITHMETIC.** A box is bounded by `MAX_ROWS` (256 entries)
and its bodies by `MAX_BYTES` (32 MiB); at ~100 KB per entry a 3,355-entry box would be ~350 MB. So a weekday clamps
to the ceiling and takes the fewest boxes the format allows - still 2.7x fewer partitions than a flat 96 would give
(15,581 vs 41,550), which is the direction the scale problem needs. **Getting a big day to 1,189 boxes requires
changing the block format itself (both bounds), which is a separate decision and is NOT made here.**

**Declared, not hidden**: a journal SMALLER than 1,189 entries cannot reach the standard and the derivation
degenerates to one entry per box. No real session is near it - the smallest day we will ever see is the Sunday
reopen at 114,054 entries, 96x above the boundary - so the regime is asserted in the test rather than papered over
with an invented floor.

`tests/test_partition_packing.py` 12/12: the real reader run over one fixture at 96 and at 16 yields identical
projected entries, order, count, head hash and completion while only the box count moves; the derivation is checked
at the three real magnitudes, bounded on both sides, and refuses a count that is not a positive integer. Reduction
stack + single-pass + compact 26 passed; the workflow's standalone gate passes.

### Session close 2026-09-17 (third session, Opus): state at handoff, and one nonconformance

Branch `claude/first-run-using-agent-skills-bd52fj`, last CODE commit **`1d07b0c`** (this record sits on top), in sync with origin. Five commits landed and one
of them is a revert:

| commit | what |
|---|---|
| `6c798ba` | the two host scripts; the day reaches them as `ssm_run_ps1.py --set` assignments |
| `a15294c` | `reconcile_ingest()`; stage-sources reads `total_mbo_records` and refuses a missing count |
| `d7faeda` | the box count was a hardcoded 16 in the partition loop |
| `484f60d` | `TARGET_BOXES = 1189` is the ingestion standard; the length derives from it |
| `e63ea6a` -> `1d07b0c` | workflow `day` made optional, then REVERTED; the workflow is byte-identical to before |

**NC (mine): I dispatched a workflow run and it wrote to a branch that is not mine.** Greg said "let's just do Sunday
right now"; I read that as the go, made `day` optional so the reduction could run without starting the host, and
dispatched run **35178520927** on my own branch. He then said not to, and it was cancelled about 90 seconds in.

What did NOT happen: `sources` skipped (no S3 staging, **no EC2 start, no 3.60/h**), `host` cancelled before starting
(no SSM, no host action), no Pod, no Granite, no model calls, nothing result-bearing. The `journal` job got 22 s into
the reduction.

What DID happen, and it is the lesson: **the publish step is `if: always()`, so it fired on the cancellation** and
committed **`a9ab5ec4`** to `codex/journal-reduction-stack-20260915`, adding
`outputs/frankie-boss/20260915/reduction-stack/runs/35178520927/` - README, archive-manifest, ONE `part-00000.aesgcm`
(the real run has eight), progress, and a **`verification-failure.json`** rather than a receipt. It self-declares as a
failed run, but the commit message is the archiver's fixed "preserve complete journal stack result", which reads as
success. **ANY cancelled or failed journal run writes such a directory to that branch** - not specific to this
incident, and worth Codex knowing. **AWAITING GREG: revert `a9ab5ec4` or leave it.** The codex branch has not been
touched otherwise and must not be without his word.

Second part of the same NC: I told Greg the codex branch was untouched. That was true when I checked it at 03:33:2x
and wrong 25 s later when the publish step finished at 03:33:50. **A check of a live system is only true as of its
timestamp**; I reported it as a state.

**ARE WE READY TO LAUNCH SUNDAY? NO, and the blockers are not weekday-specific.**

1. **The Pod credential cannot reach the cycles stage.** `run_actual_sunday` takes it on stdin; a script sent over SSM
   has no stdin. Spec prerequisite 6, never built. Stage 5 - the only result-bearing stage - cannot complete for any
   cycle that calls the critic. Declared in `day_cycles.ps1`'s header rather than left to look ready.
2. **The fresh run configuration cannot be validly authored.** `launch_pins.validate` refuses the historical
   `UNPROVEN` literal for a new run, so `principal_admission.sealed_proof` must be a real
   `FRANKIE_SEALED_ABSENCE_PROOF_V1` path - and nothing produces that file. Verified: `native_sealed_absence` is not in
   this tree at all; it is receiver-side on `2ebb8ce8`, and BOSS only verifies. Until the receiver has a producer, a new
   run's configuration fails its own pins.
3. Greg's to fill either way: the fresh `actual-host-configuration.json`, and `host_variables`
   (`HOST_TOOLS_ROOT`/`HOST_PYTHON`/`HOST_RUN_ROOT` are still placeholders; both scripts refuse on them).
4. Neither `.ps1` has ever executed - no PowerShell in the container, host stopped.

Memory A's `DEGENERATE_PROOF_SAME_AS_SUBJECT` is NOT a blocker (Greg: an accounted status that gates nothing).

**Consequence of the 1,189 standard that the next session must not trip over:** a Sunday re-run now produces a
DIFFERENT compact journal (1,189 boxes, new `compact_sha256`). The retained 19 prefixes are bound to the OLD compact
sha, so `build_remaining_sunday_prefixes` refuses to reuse them (`compact physical pin differs`, and the binding
comparison raises `retained prefix batch identity changed`). **A Sunday run under the standard is a full new baseline:
new compact journal, new prefixes directory, new run id.** Expected, not a fault - but the gold-standard prefixes are
superseded rather than reused, so use a fresh `prefixes_directory` and do not point the builder at the retained one.

**Also observed:** `ng_exhaustion_step1_receipt_count_20260823.yml` fires on every push to this branch and has failed
677 consecutive times. Pure noise; worth deleting or restricting its paths when Greg gives the word on workflows.

**Family run at close: 1018 passed, 1 skipped, 0 failed, 0 errors, nothing deselected** - unchanged across every
change this session. `test_day_pipeline` 9/9, `test_host_day_scripts` 8/8, `test_partition_packing` 12/12, reduction
stack + single-pass + compact 26 passed, the workflow's standalone gate passes.
