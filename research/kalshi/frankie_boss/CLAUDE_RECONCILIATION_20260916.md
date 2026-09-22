# Claude reconciliation record - integrated recovery + classroom tree (2026-09-16)

Step 1 of the Codex pre-launch audit handoff (`outputs/frankie-boss/20260916/prelaunch-audit/CLAUDE_HANDOFF.md`
on `codex/frankie-prelaunch-audit-handoff-20260916`): reconcile the audited recovery, classroom and receiver
trees in isolation. Git-only work. No Frankie, Granite, Pod, EC2, S3, market-data or result-bearing action was
taken. Launch remains closed. Nothing here authorises a run.

## What the integrated tree is

Branch `claude/first-run-using-agent-skills-bd52fj`. Integrated code tree = commit `dd5d4447`.

| input | SHA | relation to the integrated tree |
|---|---|---|
| classroom composition `chatgpt/frankie-feed-output-memory-wiring-20260916` | `d152dd82` | base of the integrated tree (checked out as-is) |
| recovery `ccode/frankie-lawful-recovery-review-20260915` | `34301ac0` | merged at `02aa62db`; the only recovery commit absent from `d152dd82` is `34301ac0` itself, which touches two documents (`DROP_IN_NEXT_CHAT_20260917.md`, `audits/FRANKIE_FEED_AUDIT_SUNDAY_CYCLE0_20260916.md`) and no code |
| classroom integration review `ccode/frankie-dipole-classroom-integration-review-20260916` | `61c73a2d` | merged at `dd5d4447`; its one commit (review document + two test additions) was absent from `d152dd82` |
| receiver `ccode/frankie-receiver-feed-20260916` | `2ebb8ce8` | NOT merged. It is a separate lineage (`research/kalshi/frankie_raw_mbo_benchmark`, common ancestor `a7dd99e7`, 2026-08-24) and is a pinned sibling checkout, not a merge target. The pin the drop-in requires (`receiver_commit 2ebb8ce8`) is a configuration change and is deliberately not made here (audit finding 2) |
| lawful ancestor | `050c5056` | science-byte comparison baseline (below) |

Ancestry facts checked: `d152dd82` contains `cf9e2c87`, `02306339`, `5d5c2138`; the marker/placeholder commits
between `5d5c2138` and `d152dd82` net to one added work-in-progress note. All three audited remote tips were
unchanged from the audit's SHAs at the time of this work. No `codex/*` or `chatgpt/*` branch contains all three
inputs; this is the first tree that does.

## The one merge conflict and how it was resolved

`tests/test_dipole_classroom_review_fixes.py`, test `test_final_adapter_keeps_answer_key_material_out_of_the_principal_directory`.
The classroom side parametrised it over `(adapter_class, builder)` with the integrated adapter on
`prepare_integrated_cycle`; the review commit parametrised it over `adapter_class` only, driving the integrated
adapter on a `prepare_final_cycle` package. These are different cases, so neither was chosen over the other: the
classroom form is kept and the review's case is added as a third parameter with its comment. All three pass.

## Evidence (this container: Linux, Python 3.11.15, torch 2.x CPU, numpy 2.4.6; `PYTHONPATH=.:research/kalshi/frankie_boss:research/kalshi/frankie_boss/tests`)

| run | tree | result |
|---|---|---|
| audit's `audit-tests.xml` set (10 files) | `d152dd82` untouched | 99 passed (matches the audit) |
| audit's `recovery-tests.xml` set (4 files) | `d152dd82` untouched | 21 passed (matches the audit, run on `34301ac0`) |
| audit set | `dd5d4447` | 100 passed (the +1 is the review commit's added seam test in `test_dipole_classroom_integration.py`) |
| recovery set | `dd5d4447` | 21 passed |
| `test_dipole_classroom_review_fixes.py` + `test_dipole_classroom_integration.py` | `dd5d4447` | 13 passed |
| classroom family (`test_dipole_classroom*.py`, `test_sunday_execution.py`, `test_classroom_recovery_reconciliation.py`) | `dd5d4447` | 48 passed |

Science files vs `050c5056` on `dd5d4447` (the list from the three classroom reviews: `dipole_target.py`,
`c15_teacher.py`, `c15_teacher_r3.py`, `teacher.py`, `c15_normalizer.py`, `c15_normalizer_r3.py`, `c15_dstate.py`,
`context_session.py`, `prepared_context_cache.py`, `b1_reasoner.py`, `boss_training_checkpoint.py`,
`feedback_cycle.py`, `frankie_principal_adapter.py`, `operations/run_actual_sunday.py`, `native_mbo_encoder.py`,
`trunk.py`, `c15_journal.py`, `causal_packet.py`, `research/refrag`): blob-identical except `c15_journal.py`
(35 lines) and `prepared_context_cache.py` (29 lines), exactly the two exceptions the audit's finding 7 states.
The receiver's 246-test suite was not run here; the receiver tree is untouched at `2ebb8ce8`.

## What this does NOT close

Audit findings 2 through 8 are untouched: stale launch pins, compact-source host selection, sealed/output
admission on the BOSS boundary, independent Memory A proof, authority map entries, the science-byte exceptions'
runtime identity, and the remote receiver checkout without a parent repository. The classroom tip's own
`WORK_IN_PROGRESS_FEED_OUTPUT_MEMORY_WIRING_20260916.md` lists the same seven targets as planned, not done.
The full frankie_boss suite (180 test files) was not run here.

## Environment facts for the next session

This work ran in a remote Linux container, not the Windows workstation. No Runpod credential or SSH key is
present; AWS credential environment variables are present but were not used; `boto3`, `zstandard` and CPU torch
were installed for the suites. `.github/workflows/boss_frankie_tests.yml` does not exist on any of the three
inputs or on this branch. Nothing was started, stopped, dispatched or uploaded.

## Standing rule recorded 2026-09-16 (Greg): remove the Granite 4,096-token context from all Granite code

The 4,096 Granite service context is retired. The only Granite context is 131,072, output budget = remaining context,
with the incomplete-output alert. Nothing below has been changed yet; this is the inventory for the removal slice.

Non-test code (23 lines, 13 files), all blob-identical to the lawful ancestor `050c5056`:

| file | lines | what |
|---|---|---|
| `granite_runpod_admission.py` | 16 | `CONTEXT=4096` |
| `granite_runpod_service.py` | 31, 44-45, 169 | default context 4096; `(4096, 131072)` allowlist; 1,200 output ceiling when not 131072 |
| `granite_runpod_tokenizer.py` | 30, 104 | allowlist message; 1,200 ceiling when not 131072 |
| `granite_runpod_proxy.py` | 46-47, 270, 280, 302 | `_chat` default and allowlist; `main` default; `GRANITE_MAX_MODEL_LEN` fallback '4096' |
| `granite_runpod_cloud.py` | 335-336 | `admitted.get('context', 4096)` and allowlist |
| `granite_startup.py` | 32-33 | `max_model_len` allowlist |
| `granite_startup_pins.py` | 17 | `service_context` allowlist |
| `granite_retained_host.py` | 94 | `tokenizer(..., context=4096)` default |
| `granite_retained_lifecycle.py` | 195, 199, 222 | `resume_once` hard-pins context 4096 and input+output <= 4096 (no non-test caller); `verified_service_inputs` defaults `compact_v1` / 4096 |
| `granite_full_capacity.py` | 30 | `fits_accepted_service = total <= 4096` |
| `granite_runpod_probe.py` | 42 | `len(body) > 4096` (byte bound, review whether it is a context echo) |
| `sunday_native_runtime.py` | 142, 148 | `service_context=4096` default and allowlist |

Tests: 16 files under `tests/` reference the Granite 4096 (fixtures, allowlist tests, `GRANITE_MAX_MODEL_LEN: '4096'`).
Specs: 5 documents state the 4,096 Granite context as current.

The live route already passes 131,072 and `stacked_v1` explicitly from host configuration, so today the 4096 survives as
defaults, allowlist members and one dead gate; removal makes 131,072 the only admissible value and turns any 4096 into a
refusal. Separate from this: the native row context `T_CTX = 4096` (encoder, runtime, schedule hash, prefix-builder
guard) is a modelling parameter whose replacement value Greg has not yet given.

Number provenance settled the same day: the "114k" / "117k" Codex quoted is the journal entry count 114,054
(2 x 57,027 records, INPUT + APPLIED), which the token review also uses as "the 114k-row drain"; it is not a token figure.
The token projection at 4,096 rows (~114k-116k) is a coincidence of magnitude and is retired with the row context above.

## Removal executed 2026-09-17 (Greg: "take the 4096 out of the code")

Test-first (RED 13 failed / GREEN 273 passed on the 17 affected test files; the one failure left in that set,
`test_granite_retained_start_guards.py::test_start_claim_precedes_action_and_failure_never_authorizes_repeat`, fails
identically on the untouched tree with `KeyError: 'status'` in `start_once` and pre-dates this work).

Done, 12 files. The one constant `granite_runpod_admission.CONTEXT` is now 131072 and the only admissible Granite
context everywhere it is checked; the standalone Pod modules carry their own local constant because they ship
without the package (`granite_runpod_proxy.SERVICE_CONTEXT`, `granite_startup.MAX_MODEL_LEN`).

| file | change |
|---|---|
| `granite_runpod_admission.py` | `CONTEXT = 131072` |
| `granite_runpod_tokenizer.py` | only `CONTEXT` admissible; the "1,200 unless 131072" output ceiling is now the context itself |
| `granite_runpod_proxy.py` | `SERVICE_CONTEXT`; `_chat`/`make_server` accept only it; ceiling = context; `main` reads `GRANITE_MAX_MODEL_LEN` through `environment_service_context`, which refuses an absent, malformed or non-pinned value instead of defaulting |
| `granite_runpod_cloud.py` | `validate_runtime` requires `admitted['context'] == CONTEXT`; no default |
| `granite_startup.py` | `MAX_MODEL_LEN = 131072`; `launch_environment` accepts only it |
| `granite_startup_pins.py` | `service_context` must equal `CONTEXT` |
| `granite_retained_host.py` | `tokenizer(..., context)` is now required (its one caller passes the pinned value) |
| `granite_retained_lifecycle.py` | `resume_once` gates on `CONTEXT`; `verified_service_inputs` default is `CONTEXT` |
| `granite_full_capacity.py` | `fits_accepted_service` measured against `CONTEXT` |
| `sunday_native_runtime.py` | `prepare_critic_request` default and gate are the service context; output bounded by the context alone |
| `granite_runpod_probe.py` | the 4096 here was HTTP body BYTES, now `MAX_PROBE_BODY_BYTES` (unchanged value, labelled) |
| `granite_active_run.py` | the 4096 here was an S3 record size in BYTES, now `MAX_RECORD_BYTES` (unchanged value, labelled) |

Behaviour changes to know: a Granite config, pin, startup, proxy or admission carrying 4096 is now a refusal, not a
default; the proxy's `main` no longer starts without the pinned `GRANITE_MAX_MODEL_LEN`; output requests are bounded by
the 131,072 context alone (the smoke-era 1,200 ceiling is gone). No Granite prompt bytes, encoders or science files
changed.

NOT done, pending Greg (one file, `granite_runpod_service.py`, `RunpodConfig`): its context default/allowlist still
carries 4096 because the existing rule "a 131072 context requires open-ended transport" would, once 4096 is gone, refuse
every finite-timeout Runpod config. That retires the direct smoke transport: ~18 test cases in
`test_granite_runpod_service.py`, `test_granite_open_ended_service.py` and `test_granite_durable_job_client.py` construct
finite configs, and ~160 lines of the finite `RunpodShadowService` path become unreachable. Options: (a) retire the
finite transport (delete the path and rewrite/remove those tests), or (b) relax that one guard so finite configs remain
constructible at 131072. (a) is the fail-closed reading; (b) weakens a guard whose reason (a 92k-token generation cannot
finish inside an 80 s request timeout) still holds. The live route is jobs_v1 open-ended either way.

Tests: 3 new refusal tests (tokenizer, proxy, startup pins) and refusal cases added to startup, retained lifecycle and
start guards; tests that encoded the 1,200 ceiling now assert the 131,072 bound; a synthetic positional-limit fixture in
the live-controller test moved from 4096 to 2048 so the number cannot be mistaken for the service context. The
retained-host test `test_open_run_explicit_completion_still_stops_retained_pod` stalls indefinitely here exactly as it
does on the untouched tree and on the workstation (drop-in item 7); it was deselected from the family run, not changed.
Five specification documents carry a dated correction note at the top.

Smoke-launch consequence found by the family run: `runpod_cloud_admission.json` is the REAL local-tokenizer admission
receipt of the 2026-09-14 bounded cloud smoke (commit 53b4e09e), pinned by `granite_runpod_cloud.ADMISSION_SHA`, and it
records `context: 4096`. It is evidence and was not rewritten. It is consumed only by the legacy smoke launch controller
(`granite_runpod_cloud.controller`, workflow `granite_runpod_cloud_smoke.yml`, push/dispatch only) and `probe.run_probe`;
the live retained path reads neither. Under the rule, `validate_receipt` now refuses that receipt before any intent or
provider call, so the smoke launch cannot run at the retired context (pinned by a new test). A fresh real 131,072
receipt generated on the Pod, plus a new `ADMISSION_SHA`, would re-enable it if ever wanted. The two controller lifecycle
tests stub the receipt gate (as the probe tests already did) so the stop/retain lifecycle stays covered.

Family run (`test_granite*`, `test_sunday*`, `test_run_actual*`, `test_frankie_controller`, `test_actual_host*`, one
pre-existing stall deselected): untouched tree 988 passed / 10 failed / 28 errors; this tree 994 passed / 10 failed /
28 errors with the IDENTICAL failure and error set (the 28 errors are all `test_granite_coordinator.py` setup errors).

## Completion 2026-09-17 (Greg: no relitigation; no 4096 artifacts left lying around)

- `granite_runpod_service.py`: `RunpodConfig.context` defaults to and admits only `CONTEXT`; a finite `request_timeout`
  is refused (the existing "long context requires open-ended transport" rule, now unconditional). The finite direct_v1
  critic body in `RunpodShadowService._critique` (one bounded HTTPS exchange under a request timeout: the smoke
  transport) is replaced by an explicit refusal; the open-ended and durable-jobs subclasses carry the live paths. Six
  imports only that body used are removed. The base class stays because `OpenEndedRunpodService` subclasses it and
  because the disabled service is built from it.
- `granite_runpod_controller.build_runpod_controller` gains a `spool_directory` passthrough so it can assemble the
  open-ended critic (it could only ever build the finite one before; no non-test caller).
- `runpod_cloud_admission.json` (the real 4096-context smoke admission receipt) is DELETED and `ADMISSION_SHA` removed;
  `granite_runpod_cloud.controller` (the bounded smoke launch) refuses at entry before reading any intent or touching the
  provider. The workflow `.github/workflows/granite_runpod_cloud_smoke.yml` still exists (push/dispatch only) and would
  now fail closed at that refusal; deleting it is Greg's call (standing rule: no workflow changes without him).
- Tests: `test_granite_runpod_service.py` rewritten around the surviving surface (config refusals, base-critic
  refusal, runtime binding, config hash without credentials, the config-free HTTPS bounds test); its 15 finite-critic
  cases are gone because the transport they drove is gone, and their behaviours on the live paths are covered by
  `test_granite_open_ended_service.py` and `test_granite_durable_job_client.py`. Finite-hash pin tests in the
  open-ended, durable and long-context files now assert the open-ended hash and the refusals. The controller tests run
  on the open-ended critic and assert its two observed phases (`request_sent`, `response_persisted`).
- Family run (same command as above): 981 passed / 8 failed / 28 errors; nothing introduced against the untouched
  baseline; the only two baseline failures no longer present are the two retired finite-transport tests.

Prefix / reducer-stack verification (Greg: "find the prefixes for the first run; the gold standard"): the 19 prefixes
live at `sunday_20260915_package/FB/actual-prefixes/` (00 witness; 01-18 packet-seed + receipt + witness;
`full19-witnesses.json`). Each seed selects `TOP_T_CTX_BY_RECEIVE_TIME_AND_CURSOR` with 4,096 context cursors,
`derivable: true`, bound to the compact parent (569,667,584 bytes). The compact journal of the first run: 57,027 records
= 114,054 INPUT/APPLIED entries -> 7,129 gzip blocks of at most 16 entries, codec 20.9x, verified in 715.2 s wall
(50.4 s parent CPU + 2,079 s worker CPU on CPUs 1-3) in GitHub run 34962256086 (receipt in
`outputs/frankie-boss/20260915/reduction-stack/runs/34962256086/`). The number Greg recalled as "about 1,200 boxes"
does not appear in any receipt; 7,129 blocks is the recorded figure. On this tree, `build_remaining_sunday_prefixes.py`,
`compact_journal_snapshot.py`, `compact_conformance_reader.py`, `frankie_journal_reader.py`, `journal_stack_execution.py`,
`context_session.py`, `operations/run_actual_sunday.py` and `operations/run_journal_stack.py` are blob-identical to the
first run's runtime pin `9a8f3f46`. Only `compact_journal.py` (+46/-4), `prepared_context_cache.py` (+22/-7) and
`c15_journal.py` (+24/-11) differ, all from the later reduction-stack work and all pinned byte-identical in output by
`tests/test_reduction_stack_equivalence.py`. Nothing in the prefix machinery was changed or needs reverting.

## Final sweep 2026-09-17 (Greg: "take the 4096 out", no literal left)

No Granite module or Granite/Sunday test carries the literal any more. The two byte bounds are re-sized to 2048 bytes
(`MAX_PROBE_BODY_BYTES`, `MAX_RECORD_BYTES`; the probe body and the active-run record are a few hundred bytes), the
retirement messages say "smoke context", and every refusal test uses another wrong value (8192 / 65536 / a string) so
the guarantee "only 131072 is admissible" is kept without naming the retired number. The only 4096 left in
`frankie_boss` code is the NATIVE row context in `sunday_native_runtime.py` (`context_rows`, `n_norm`, `t_ctx`) plus
its mirrors in `native_mbo_encoder.T_CTX`, `sunday_schedule.model_context_rows` and the prefix-builder guard: a
modelling parameter pending Greg's row count, not Granite. Family run: 979 passed / 8 failed / 28 errors, nothing
introduced against the untouched baseline.

Answers recorded for the log. (1) The finite smoke transport is not needed: the live route is jobs_v1 open-ended on
the retained Pod; RunpodConfig is fixed to admit only 131072 and open-ended transport, so nothing can build the smoke
transport again. (2) The journal reducer was not changed and nothing was dropped: the first run's reducer stack
(compact 16-entry gzip blocks, single-pass conformance, parent + affinity-bound workers) is on this tree and its
equivalence tests pass (`test_reduction_stack_equivalence.py` 4/4, `test_prepared_context_cache.py` 8/8,
`test_run_actual_sunday_compact_source.py` 4/4, `test_compact_source.py`, `test_compact_journal.py`); the prefix
machinery is byte-identical to runtime pin `9a8f3f46`.


## Correction 2026-09-17: the "about 1,200 boxes" was right, and this file's answer was wrong

Above, this file recorded that *"the number Greg recalled as 'about 1,200 boxes' does not appear in any receipt;
7,129 blocks is the recorded figure."* That treated his number as a faulty memory when it was a TARGET, and it sent
the question away instead of asking what set 7,129.

What sets it: `journal_stack_execution.MigratingConformanceReader.entries()` partitioned the journal with a
hardcoded literal - `range(0, count, 16)` and `min(16, ...)` - and every partition becomes exactly one block. So
114,054 / 16 = 7,129, which is the whole derivation. `CompactWriter`'s `block_bytes` (4 MiB) and `MAX_ROWS` (256)
never applied on this path at all: the loop INSERTs each partition's block directly and bypasses
`CompactWriter.add`. Nobody had chosen 16 as a size; it was never revisited.

`PARTITION_ENTRIES = 96` (Greg's call, 2026-09-17) gives 114,054 / 96 = **1,189 boxes**. It also cuts per-partition
overhead six-fold: each partition opens the source read-only and runs three queries, so 7,129 opens become 1,189.
The journal is invariant - same entries, same bytes, same order, same completion and seal, proved on a real run of
the reader at 96 and at 16 over the same fixture (`tests/test_partition_packing.py`). The compact container's bytes
and sha256 change by design.

## Standing rule, said again 2026-09-22 (Greg): the row window leaves the code; a guard keeps it out

Greg, 2026-09-22 (verbatim): "This needs to be the last time I have to repeat myself about the context output limits. We
must have taken that 4096 number out 10 different times. Take it out and look for the rule we made about this stuff and
see if limits were reimposed other places."

The sweep (every .py/.sh/.yml/.json under research/kalshi/frankie_boss, deploy, .github, the pinned package and records
excluded from the code count), classified by ROLE, not by digit string:

| Role | Where | Action |
|---|---|---|
| the native ROW WINDOW as a code literal or default | `native_mbo_encoder.py` T_CTX (+ the encoder payload), `context_session.py` default, `sunday_native_runtime.py` DEVELOPMENT.context_rows + `t_ctx=4096`, `sunday_schedule.py` model_context_rows=4096, `build_remaining_sunday_prefixes.py` gate `!= 4096` | REMOVED: declared once in the verified schedule (`model_context_rows`), read by the host runner (which now keeps `self.schedule`) and the prefix builder; `initialize` and `ContextSessionRunner` require it; encoder payload V2 without it |
| a REIMPOSED gate on the number | `build_remaining_sunday_prefixes.py:340` refused any window but 4096 | REMOVED (refuses a schedule without a positive declared window instead) |
| Granite context in a test | `tests/test_lawful_recovery_migration.py` context=4096, service_context 4096 | 131072 |
| the row window as a test fixture value or default | `test_production_bindings.py`, `test_native_runtime_diagnostics.py`, `test_retained_preparation_recovery.py`, `test_context_session.py` and six helpers that relied on the default | declared values (64, 3262, 8, ALL_FIXTURE_ROWS) |
| Granite context REIMPOSED in a pinned environment | `runpod_cloud_environment.json` GRANITE_MAX_MODEL_LEN "4096" (read by `granite_runpod_cloud.py`, the retired cloud controller) | FLAGGED, not changed: it is the pinned Pod bootstrap bundle's environment ("untouched"); Greg's word |
| an OUTPUT CAP on an LLM call | `research/kalshi/frankie_backends.py:71` Bedrock `maxTokens: 4096` (the S93 coach agent's Bedrock lane, not the BOSS) | FLAGGED, not changed: a different program; removing the cap is Greg's word (the BOSS itself has none: `max_tokens` = the remaining context, `output_budget=remaining_context` enforced) |
| byte sizes and windows that are not a context | `DEDUP_BYTES`, head-render section bytes, cursor length bounds, `read(4096)`, `block_bytes=4096`, `recv(4096)`; the C15 normalizer's `n_norm=4096` (its running-statistics window, a modelling registry value beside d_model, not the context) | unchanged; the guard's patterns are role-specific so these never trip it |
| the selection policy's NAME | `TOP_T_CTX_BY_RECEIVE_TIME_AND_CURSOR` (a pinned data string in every seed) | unchanged; the guard matches `T_CTX` only as a whole word |

Why it kept coming back: every file that carried the literal is in the first run's byte-pinned identity
(`WORKING_TREE_IDENTITY_BYTES_20260915.json`, 161 files) and the prefix binding and the 19 seed receipts pin the sha256
of `context_session.py` and `sunday_native_runtime.py`; `run_actual_sunday` refuses cycle 0 when those bytes move. So
the number could be retired in prose and never in code without breaking the gold standard's own gates. The way out is
the host's own precedent (`frankie_host_rebuild_prefix_batch.ps1`, 2026-09-20): re-mint the code pins in the binding and
the seeds with the snapshots untouched. That is a host step of the full rerun, on Greg's go.

The first run's DATA still declares 4096 (schedule `model_context_rows`, binding `context_selection.t_ctx`, every seed):
it is the measured identity of that run and is not rewritten. The rerun's row count is Greg's modelling call, set in
the schedule the rerun verifies; the code carries no number.
