# Frankie/BOSS Monday: remaining workflow connection plan

**For Claude evaluation — planning only.** Prepared 2026-09-27 UTC (2026-09-26 evening in America/New_York). Repository: DavisAI1974/Markets. Runtime branch: `claude/agent-skills-execution-tzh7sw`. Inspected runtime commit: `cdeb202645e522d7da7903bcd0b4dd587cf2aa42`.

This document records a read-only review and proposes the smallest remaining connections. No runtime code, deployment, workflow dispatch, infrastructure change, or test was performed for this planning task. The document is published separately from the runtime branch. It is a review proposal, not evidence that the proposed connections already work.

## 1. Are we just waiting?

**Yes, for the current ROOT calculation job.** GitHub reported [run 36284909445](https://github.com/DavisAI1974/Markets/actions/runs/36284909445) as `in_progress` at approximately 01:25 UTC. It started at 01:14:06 UTC. This is an Actions status observation, not a new process-level progress measurement. A completed `calculations-receipt.json` has not been observed.

ROOT completion does **not** automatically launch the remaining Monday pipeline. The real remaining work is to connect its retained outputs to the actual principal, Linux native host, Granite request/response, classroom correction loop, and retained knowledge. Existing implementations cover much of the science and classroom behavior; several wrappers still address the previous Windows host or historical Memory A session.

Do not stop or restart ROOT to implement this plan. Do not dispatch a second calculation run. No defensible completion ETA is available from the status alone.

## 2. Essential checklist

Cross off a step only when its actual output exists. The downstream items are pending, not executed.

- [x] Bind the complete Monday source across both members; retain the completed authorship receipt.
- [x] Stage runtime code through `cdeb2026` on the ROOT box.
- [x] Prepare the whole-day schedule from the completed binding, with **zero source-journal traversals**.
- [ ] **Running:** finish the existing full ROOT/native producer calculation run and retain its calculation receipt.
- [ ] Connect those results, existing source provenance, actual brain knowledge, and delivery evidence to fresh Monday principal inputs.
- [ ] Connect a fresh Linux host/session configuration to those inputs and the existing mandatory classroom host.
- [ ] Complete the actual native forecast/Granite critic handoff using all applicable reducers.
- [ ] Complete principal full reading, comparison, teaching/teach-back, and the initial response.
- [ ] Record the initial response; complete host grading, correction, correction recording, and final classroom evidence.
- [ ] Retain Monday knowledge and the Tuesday-target forecast with **`pending_target_outcomes`**.

Tuesday outcomes and subsequent native learning are a separate unresolved dependency. They cannot be crossed off using Monday evidence.

## 3. Scope that must survive every connection

Monday is the entire **23-hour trading day 20211004**, from **2021-10-03 22:00 UTC through 2021-10-04 21:00 UTC**, across both UTC source members: **2,032,203 records; 4,064,406 journal entries; 1,535,939 F_LAST groups**.

Preserve every required calculation, the complete registry, all three repository producer groups (`derived_geometry`, `prebirth_opportunity`, `causal_clocks`), full Granite critic input and full reading, all classroom teaching/grading/correction, and retained knowledge. Repository “bedrock” group names do not authorize Amazon Bedrock.

Operational rules:

- Execute existing stages manually and sequentially where they already exist. Do not introduce an orchestration layer as a prerequisite.
- No extra tests, canaries, comparison runs, validators, source-proof audits, or parallel agent work. The explicitly requested data-reader CPU parallelism remains allowed.
- No ingestion restart/replay, infrastructure stop, pinned-bootstrap changes, evidence deletion, Amazon Bedrock, or BOSS output caps.
- Preserve completed binding and calculation work; no duplicate full-source pass merely to reconnect a consumer.
- Any later implementation must go through GitHub in atomic commits. No C:/E: artifacts, force pushes, or deletion of prior run evidence.
- Preserve the pinned receiver and its real scientific/admission requirements. Do not replace missing evidence with invented receipts or exceptions.
- Normal checks intrinsic to an existing consuming stage remain part of that stage. Do not create a separate checking project.

## 4. Current artifacts to reuse

| Artifact or execution | Actual location/status |
|---|---|
| Completed source binding | `/opt/frankie-box/work/monday-launch/full-20211004-20260923-r4` |
| Binding completion | 2026-09-24T02:00:15.741Z; complete count; zero failures; retained/read-verified receipt |
| Prepared schedule | `/opt/frankie-box/work/trading-day-preparation/full-20211004-20260927-r6-48` |
| Preparation execution | [36284801549](https://github.com/DavisAI1974/Markets/actions/runs/36284801549), successful; one whole-day prefix; `source_journal_traversals: 0` |
| Staged runtime | `/opt/frankie-box/code/cdeb202645e522d7da7903bcd0b4dd587cf2aa42-36284629312-1/markets` |
| Current calculation output root | `/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48` |
| Calculation completion | Pending; expected `calculations-receipt.json` under that output root |
| Actual knowledge source | `/opt/frankie-box/brain`; use an immutable session baseline derived from its real contents |

The earlier binding Actions run was cancelled after its workflow time window, but its remote job subsequently completed. Its completed receipt is authoritative; do not repeat authorship because the Actions label was cancelled.

The current calculation entry uses existing `Session.derive(source=recovered)` before a principal request exists. Its completion receipt is designed to carry source binding, calculation pins, derivation, result, ledgers, full digest and digest proof, with `status=calculations_retained` and `principal_binding=pending`. It declares no model calls or ingestion replay. These are expected receipt fields, not a claim that the running calculation has finished.

### CPU configuration: avoid an unsupported speed claim

The retained ROOT task identifies the existing Linux ROOT box as `i-035994afa8bdf66a5`, us-east-1, r7i.8xlarge, 32 vCPU and about 248 GiB RAM. Recent inventory agrees.

The current run requests **48 data workers**. Existing reader budgeting reserves one CPU and caps the pool to available affinity: with all 32 CPUs available, the effective reader budget is **31**, not 48 physical CPUs. The actual active pool has not been observed for this run.

Reader parallelism is distinct from parallel ROOT science. The inspected legacy producer path contains a stateful serial record loop; the native replay path preserves causal order. No separate 48-way ROOT calculation pool was established by this review. Reuse the old ROOT box and existing producer facilities, but do not claim all calculations now use 48 workers or extrapolate runtime from that number. If Claude knows an existing multicore facility from the six-hour run, identify its exact entry/configuration before proposing new machinery.

## 5. Sequential connection plan

```text
Completed full binding + prepared schedule
                   |
Current ROOT calculation -> retained result / ledgers / digest / pins
                   |
Fresh actual-brain principal inputs + receiver-compatible provenance/delivery
                   |
Fresh Linux native/classroom host -> actual request or retained WAIT
                   |
Native forecast + complete Granite critic request/outcome
                   |
Principal: reuse ROOT -> compare -> full reading -> classroom/teach-back
                   |
Record initial -> host grade -> correction -> record correction -> final grade
                   |
Retain knowledge + Tuesday-target forecast + pending_target_outcomes
```

This is a dependency order. The existing host owns its internal native/critic/request ordering; manual dispatch follows its actual retained WAIT/request, rather than fabricating one to force the diagram.

### A. Finish the already-running calculation

**Existing entry:** `deploy/aws/box/frankie_box_monday_calculations.sh` through `frankie_box_run.yml`.

**Input:** completed r4 authorship, sealed recovered source, complete whole-day calculation definitions. **Output:** the actual calculation receipt and all artifacts it references.

**Necessary action:** wait for this job. At its normal completion boundary, read its existing progress/checkpoint and completion receipts. Use real counters, saved/read-verified checkpoints, and failures; do not perform a second source traversal as an audit.

**Done evidence:** a retained calculation receipt identifying complete, failure-free derivation and the actual result/ledgers/digest. A green Actions badge alone is insufficient. If Actions ends before remote work, use retained process/checkpoint evidence before deciding what happened.

**Failure rule:** preserve partial evidence and identify the failed producer. Current adapter checkpoints are not proof that every scientific accumulator can resume after a crash. Do not promise arbitrary mid-calculation resume or automatically restart the full day.

### B. Connect retained calculations to genuine principal inputs

**Reuse:** current ROOT result, ledgers, digest/proof, `source-binding.json`, `calculation-pins.json`, completed schedule/contract, and real brain helpers.

**Missing connection 1 — actual brain:** current `frankie_box_principal_inputs.py`, `source_contract_runtime.make_principal_adapter`, and principal adapter construction still expect historical Memory A inputs: retained Sunday prompt, knowledge bundle/receipt, protected frozen Memory A, and section witnesses. There is no committed turnkey route from today's actual brain to this complete Monday principal contract.

The intended connection must capture the real brain as one immutable baseline shared by host and principal, preserving earlier cycle-0 knowledge before Monday writes. Reuse existing brain capture/pin/write helpers. Supply genuine knowledge evidence and required contract sections. Do not rename stale Memory A data as Monday knowledge, import an old global historical prompt accidentally, or treat unpublished draft code as implemented.

**Missing connection 2 — mapping schema:** the completed authorship `mapping.jsonl` is a cursor/group schedule index. The principal receiver path expects its source-member mapping/bound mapping with exact-wire provenance. These are different contracts. First reuse any retained compatible mapping and completed binding. If an adapter is needed, translate already-proved facts without repeating full-source binding. If an exact required fact is genuinely absent, name that fact and its producer for Claude; do not invent equivalence or launch the legacy mapping workflow.

**Missing connection 3 — delivery/admission:** bind the real calculation result and actual delivered ledger bundle to the principal receiver. Prefer a valid existing local delivery route; do not invent an S3 bucket, presigned URL, receipt, principal artifact, or “historical” status. Current fresh admission expects an actual principal/output bundle with its required ledger count and sealed evidence. Reclassifying this as a historical retained-prompt session to bypass fresh admission is unacceptable.

**Dependency to resolve explicitly:** establish which real artifact satisfies fresh principal admission and at what point it exists. If current APIs require a principal artifact before the principal can run, this is a contract-ordering gap to resolve, not evidence to fabricate.

**Done evidence:** principal input references point to the actual full Monday calculation and real shared brain baseline, with accepted provenance/delivery/admission and all mandatory sections. No source rebinding or repeated ROOT calculation was needed.

### C. Connect the fresh Linux host and principal session

**Reuse:** `frankie_box_cycle0.sh` has actual actions **`config` and `launch`**. Its launch action already runs:

```text
run_actual_sunday_ec2.py --configuration <actual-config>
  --compact-source-tools <staged-code> --cycles 1 --pending-return
```

For the same retained host run, the existing wrapper supports `RESUME=1` and `WAIT_SHA256`, adding `--ec2-resume` and `--resume-wait-sha256`. These are future execution references, not commands executed by this document.

**Missing connection:** the current config builder inherits legacy principal fields. Session request/prompt reads use global `/opt/frankie-box/request`; response/attestation records include old C: paths; publishing assumes an old global session and response location. Scope request, work, output, configuration, and records to this fresh Monday run while deliberately reusing the current calculation artifacts.

Keep the host's `IntegratedDipoleClassroomPrincipalAdapter` path. Do not substitute a simpler principal adapter that omits classroom behavior. Preserve the pinned receiver/bootstrap and actual native runtime policy.

**Done evidence:** a fresh Linux host configuration uses the r6 whole-day schedule, genuine inputs from B, a unique host run, and actual Monday paths. It produces its real request/WAIT. Its principal session recognizes the retained complete calculation, so `_derive_needed` does not trigger a second Monday derivation.

### D. Connect the actual Granite critic request and outcome

**Reuse:** native host/controller forecast and critic logic, exact tokenizer/context accounting, applicable stacked lossless reducers, retained Granite service and durable job journal, existing request staging/completion capabilities.

The host must produce the actual complete critic request. Apply `stacked_v2` and every applicable reducer under the existing scientific contracts. Check fit at the real request boundary against the actual 131,072-token context contract. No full-day fit has been established yet. Full reading cannot stand in for omitted critic evidence. Do not shorten Monday, cap BOSS output, truncate the request, or use a small comparison run.

Windows wrappers for critic archive/readiness delivery cannot simply be pointed at Linux. Prefer existing platform-neutral delivery primitives and manual retained WAIT/resume. Use conditional request staging and retained completion workflows only if the actual controller route needs them. Preserve request/job identity for reuse; do not issue duplicate inference.

The retained service's present health was not independently established in this planning task. If its existing authority/readiness or full request fit fails, report the precise blocker. Do not stop/recreate infrastructure or change the pinned bootstrap as an implicit remedy.

**Done evidence:** actual forecast/native artifacts, the complete critic request, actual reducer/context evidence, the real retained job and complete outcome, and the host's accepted delivery receipt.

### E. Run full principal reading, comparison, and teaching

**Reuse:** the existing normal `Session._run` sequence: verify/pin/brain, labels, engine reach, derive only if needed, comparison, full reading when not already current, classroom, teaching as needed, receipts, writing, publication.

The intended session uses ROOT from A, the shared immutable knowledge baseline from B, and the real host request. Keep every required corpus item and reading/critic obligation. Reuse a completed reading artifact only when the existing session's own corpus/request binding says it is current.

Keep the full classroom and exhaustion/teach-back behavior, required analysis and accounting, and real principal output. Do not add an extra preflight/canary run merely because a preflight action exists.

**Done evidence:** the actual principal initial response and receipts for comparison, full reading, classroom work, and teaching, attributable to this Monday request and the retained calculation.

### F. Record, grade, correct, and close the classroom loop

**Reuse:** platform-neutral `record_actual_frankie_response.py`, existing host grading/correction, and the session correction path.

The recorder already accepts configuration/hash, response/hash, host-attestation/hash, cycle index, and initial/correction turn. Once B/C are connected, use that existing recorder with the real Linux files, avoiding a Windows/S3/Git round trip unless the host contract actually requires one.

Sequence:

1. Record the initial principal response against its existing request.
2. Resume the same host at its real WAIT; obtain actual grading and correction request.
3. Have the same principal session complete the correction turn.
4. Record the actual correction; resume host grading.
5. Retain final grading, crosschecks, novelty/investigation evidence, and teaching/correction transcripts.

The recorder reconstructs the adapter, so the principal/brain connection must work there too. It must not recreate the source binding or launch a second session. Do not mark completion after the first response.

**Done evidence:** accepted initial and correction records, actual grading/correction transcripts, and host-confirmed classroom completion.

### G. Retain knowledge and explicitly preserve pending Tuesday outcomes

**Reuse:** brain entry/history helpers, classroom lessons and pending-feedback/checkpoint support in the existing feedback cycle.

Retain all required digest, derivation, comparison, reading/teaching, classroom, analysis, accounting, and correction/final-grade knowledge. Confirm that the final corrected knowledge is included, rather than retaining only the pre-correction answer. Preserve earlier entries.

The intended terminal Monday status is:

```text
status: pending_target_outcomes
classroom_complete: true
native_learning_performed: false
cycle_complete: false
forecast target: Tuesday 20211005
```

Existing classroom host code represents this pending result with exit 3. A pending exit is not permission to invent labels or relaunch the forecast. Preserve the already-issued forecast and pending state.

**Done evidence:** actual retained knowledge entry/history, full classroom receipts, and forecast/pending-feedback checkpoint. Verified Tuesday outcomes remain explicitly missing. The later outcome-to-learning transition is not established as a ready workflow by this review and is a separate future dependency.

## 6. Existing workflow disposition

All paths below are under `.github/workflows/`. “Reuse” means at the appropriate actual stage with its real inputs, not dispatch now.

| Workflow | Disposition and connection |
|---|---|
| `frankie_box_run.yml` / `frankie_stage_code.yml` | Reuse existing committed-script Linux execution and staging. No replacement orchestrator. The documentation commit must not become the runtime staging target by accident. |
| `frankie_host_advance.yml` | Old Windows host/run paths. Do not dispatch unchanged. Reuse Linux cycle-0 launch/resume instead. |
| `frankie_host_export_principal_request.yml` | Windows export, including historical prompt semantics. Reuse request/turn concept; connect actual Linux request locally or adapt only necessary transport. |
| `frankie_box_fetch_response.yml` | Old request key, global session, and response-path assumptions. Use actual scoped Monday outputs; direct local recording may avoid this transport entirely. |
| `frankie_host_record_principal_response.yml` | Windows PowerShell delivery wrapper. Prefer its underlying platform-neutral Python recorder once B/C are ready. |
| `frankie_host_stage_critic_request.yml` | Hardcoded Windows instance/run-root restrictions. Existing Linux host must supply its real request; connect only the required archival handoff. |
| `frankie_request_stage.yml` | Platform-neutral conditional capability staging. Reusable if required by the actual request transport; not an extra prerequisite by default. |
| `frankie_retained_granite.yml` | Retained readiness/observer workflow, not the critic inference itself. Includes parallel roles and hold/cleanup behavior; do not blindly dispatch under current restrictions. Reuse existing retained authority/readiness first. |
| `frankie_deliver_readiness.yml` | Windows-targeted wrapper. Reuse platform-neutral delivery primitives for Linux if needed. |
| `frankie_retained_completion.yml` | Can publish a real retained completion without new inference. Requires actual request/startup/outcome hashes, job, journal generation, and code identity. |
| `frankie_workflow_continuation.yml` | Existing optional automatic continuation calls Windows routes. Manual retained WAIT/resume is sufficient; rewiring this entire layer is not a prerequisite. |
| `frankie_boss_ledger_mapping.yml` | **Do not use:** old Sunday/fixed-source route invokes ingestion. It would violate the no-replay instruction and does not solve Monday mapping reuse. |
| `frankie_serverless_reading.yml` | Do not create endpoints or run its verification inference. Reuse already configured reading capability if applicable; preserve full reading and sequential stage execution. |

Other ingestion, recovery, audit, test, and comparison workflows are not missing Monday stages and are excluded.

## 7. Minimum future implementation surface

Only implement a connection if Claude cannot identify an existing valid manual route.

| Necessary capability | Likely existing files to adapt narrowly |
|---|---|
| Actual brain principal inputs, genuine admission, compatible retained mapping/delivery | `frankie_box_principal_inputs.py`; `source_contract_runtime.py`; `frankie_principal_adapter.py`; use existing brain/mapping/delivery helpers |
| Fresh Monday Linux config and shared knowledge baseline | `frankie_box_host_config.py`; source configuration consumers in actual host/classroom |
| Scoped request/work/response/attestation and reuse of current ROOT results | `frankie_box_boss_session.py`; existing session/response wrappers only where needed |
| Linux request/readiness/response handoffs | Existing cycle-0 wrapper, recorder and delivery primitives; adapt Windows wrappers only if manual local paths cannot satisfy the real contract |
| Final corrected retained knowledge | Existing brain/session/classroom write path, only if final grade/correction is not already retained |

Do not rewrite scientific calculations, reducers, native forecast logic, classroom grading, or durable job semantics to solve path/configuration transport. No new orchestrator, validator framework, test suite, or blanket refactor is proposed.

## 8. Claude evaluation request

Please evaluate this plan without executing workflows or changing code during the evaluation:

1. Identify an already-implemented manual route for any gap before endorsing new implementation.
2. Resolve the fresh-admission ordering and actual-brain contract precisely. Preserve all required evidence; reject a historical-mode waiver or synthetic principal bundle.
3. Identify the retained receiver-compatible mapping/provenance to reuse. Distinguish it from the schedule cursor/group index; avoid repeating completed binding.
4. Confirm that the fresh Linux host and principal can consume the running calculation's artifacts without deriving Monday again.
5. Confirm every required native/producer, Granite critic/reading, classroom grading/correction, and retained-knowledge stage remains represented.
6. Check that initial response, correction, and final retained knowledge share the correct actual request, brain baseline, and run.
7. Identify any existing six-hour-run multicore ROOT facility that should be reused. Do not equate reader worker count with producer parallelism.
8. Return only concrete plan corrections, essential missing connections, and real blockers. Preserve manual sequential execution and explicitly pending Tuesday outcomes.

## 9. Protected evidence and reference pins

Never delete or modify the original sealed journal:

`/opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite`

Bytes: `23687368704`  
SHA-256: `947949d84732b0d7fa22b2e853ee89fdcfaf995955d9de652b36b344333b9888`

Preserve `/opt/frankie-box/work/sealed-recovery-35796793428` and all prior run receipts.

Already-recorded connection pins, supplied to avoid repeating discovery:

| File | SHA-256 |
|---|---|
| r4 `authorship-receipt.json` | `ade460dede20a4557b6369ca45f653fdae24a958fd52d1f1e449da53fe8e2ec6` |
| r4 cursor/group `mapping.jsonl` | `df4df1871f5019dffff1d847fcb59a5f1429d968bc66b33d7c810f0e4d918dee` |
| r6 `prepared-configuration.json` | `d90601c01def652b44466c69dcfab4f4769c27dd5a9cc86a71b097b4501ceb23` |
| r6 `preparation-receipt.json` | `062c6f7b947f526dc70a94171a903fa8b05aeef3a0d199269adfae119f5b1d73` |

These are recorded references, not a request for another source-proof audit. Preserve exact nanosecond integers when passing existing JSON between components.

## 10. Primary code and handoff references

The links are pinned to the inspected runtime commit. Older handoff progress statements are superseded by the current artifacts/status above; their remaining requirements and protected evidence still apply.

- [research/kalshi/frankie_boss/CODEX_HANDOFF_20260923_MONDAY_WIRING.md](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/research/kalshi/frankie_boss/CODEX_HANDOFF_20260923_MONDAY_WIRING.md)
- [research/kalshi/frankie_boss/operations/ROOT_CYCLE_00_TASK_20260920.md](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/research/kalshi/frankie_boss/operations/ROOT_CYCLE_00_TASK_20260920.md)
- [CLAUDE.md](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/CLAUDE.md)
- [deploy/aws/box/frankie_box_monday_calculations.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/deploy/aws/box/frankie_box_monday_calculations.py)
- [deploy/aws/box/frankie_box_boss_session.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/deploy/aws/box/frankie_box_boss_session.py)
- [deploy/aws/box/frankie_box_brain.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/deploy/aws/box/frankie_box_brain.py)
- [deploy/aws/box/frankie_box_principal_inputs.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/deploy/aws/box/frankie_box_principal_inputs.py)
- [deploy/aws/box/frankie_box_host_config.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/deploy/aws/box/frankie_box_host_config.py)
- [deploy/aws/box/frankie_box_cycle0.sh](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/deploy/aws/box/frankie_box_cycle0.sh)
- [research/kalshi/frankie_boss/source_contract_runtime.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/research/kalshi/frankie_boss/source_contract_runtime.py)
- [research/kalshi/frankie_boss/frankie_principal_adapter.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/research/kalshi/frankie_boss/frankie_principal_adapter.py)
- [research/kalshi/frankie_boss/frankie_source_mapping.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/research/kalshi/frankie_boss/frankie_source_mapping.py)
- [research/kalshi/frankie_boss/operations/run_actual_sunday_ec2.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/research/kalshi/frankie_boss/operations/run_actual_sunday_ec2.py)
- [research/kalshi/frankie_boss/operations/run_actual_sunday_classroom.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/research/kalshi/frankie_boss/operations/run_actual_sunday_classroom.py)
- [research/kalshi/frankie_boss/operations/record_actual_frankie_response.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/research/kalshi/frankie_boss/operations/record_actual_frankie_response.py)
- [research/kalshi/frankie_boss/operations/workflow_delivery.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/research/kalshi/frankie_boss/operations/workflow_delivery.py)
- [research/kalshi/frankie_boss/feedback_cycle.py](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/research/kalshi/frankie_boss/feedback_cycle.py)
- [Workflow directory](https://github.com/DavisAI1974/Markets/blob/cdeb202645e522d7da7903bcd0b4dd587cf2aa42/.github/workflows)

This document completes the requested read-only planning deliverable. All operational actions above are proposed future steps; the only running work identified here is the ROOT job already dispatched before the planning request.
