# Claude: get Monday cycle 0 running — stay on this plan

## Directive from the owner

**Do not diverge from this plan.** Work serially. The objective is to get the existing Monday cycle-0 run executing, preserving its token reducers, source evidence, and actual workflow. Do not start another architecture exercise, planner, optimization project, or broad test campaign.

The owner authorized deployment and asked to fix only concrete issues preventing cycle 0 from running. Classroom is complete. Do not reopen it without a concrete cycle-0 issue. Do not delay for unrelated test failures. Never report success from a green wrapper job alone: verify the actual execution receipt.

This handoff records the state on 2026-09-23. Resolve the remote branch tip and recent workflow runs first because another operator may have progressed after this file was written.

## Remote branch and current state

- Repository: `DavisAI1974/Markets`.
- Branch: `codex/trading-day-readiness-20260922`.
- Application/code tip verified immediately before this documentation commit: `eb382e019c5fefc9ea1172403f11c50bb7d907cf`.
- This handoff adds documentation only. Use the actual dispatched full SHA when staging/preparing; do not mismatch the checkout and workflow SHA.
- No verified deployment activation or cycle-0 start exists in this continuation.
- Correct inventory completed. Staging has **not** been verified.
- Codex's authenticated GitHub browser control now works. The browser problem was missing Codex temporary directories, repaired under a narrow owner-approved exception. This was not an AWS or Markets code failure.
- The workflow form may still be open. An open form is not a dispatch. Check Actions before doing anything to avoid duplicate runs.

Read the existing context in this order, retaining restrictions except where the owner's later explicit directions supersede them:
1. `CODEX_HANDOFF_20260923_WORKFLOW_AUTOMATION.md`
2. `SHIP_REVIEW_REQUEST_ARCHIVE_AUTOMATION_20260923.md`
3. `ARCH_PLAN_R2_ASSESSMENT_20260923.md`
4. Earlier handoffs referenced by those files.

Use the remote `using-agent-skills` and `ship` skills requested by the owner, with their relevant suggestions. Do not let generic skill routines override the owner's later serial-only, essentials-only directions.

## 1. Stage the actual committed code

Use the existing GitHub Actions workflow:
https://github.com/DavisAI1974/Markets/actions/workflows/frankie_box_run.yml

Select the branch above, then set **both** fields exactly:

| Input | Value |
| --- | --- |
| Repo-relative script | `deploy/aws/box/frankie_box_stage_code.sh` |
| Optional NAME=VALUE pairs | `ACTION=stage` |
| Timeout | `1800` |
| Instance | `i-035994afa8bdf66a5` |
| Region | `us-east-1` |
| Presign paths | empty |
| Presign hours | `4` |
| Copy GitHub token to SSM | `false` |

Inspect the script field after selecting the branch; the mobile UI previously reset it to the default inventory script. Then dispatch once.

The exact script routes through `validate-staging-route` into `.github/workflows/frankie_stage_code.yml`. Successful staging creates a fresh inactive checkout under `/opt/frankie-box/code`. It does not activate code or launch cycle 0. Read the returned staging receipt and retain its exact commit and code-root path for preparation.

Two important existing runs:
- **#104 / 35827707969**: correct `frankie_box_stage_code.sh`, `ACTION=inventory`, success. https://github.com/DavisAI1974/Markets/actions/runs/35827707969
- **#105 / 35828174059**: misleading success; script was `frankie_box_inventory.sh` with `ACTION=stage`. Only inventory ran. Staging jobs were skipped. **Do not count it as staging.** https://github.com/DavisAI1974/Markets/actions/runs/35828174059

Inventory #104 verified:
- About 166 GB available.
- Existing active checkout at `/opt/frankie-box/markets` is older: `2ae4da204b0d2a12f605e765f281b505ff51491a`, with untracked files. Do not overwrite or clean it.
- The original container and recovery directory below exist.
- No model calls, source replays, or application writes occurred.

## 2. Resolve the actual launch inputs; do not pretend they are already authored

At the verified code tip, `research/kalshi/frankie_boss/blocks/MONDAY_20211004_LAUNCH.json` still has these null fields:

```text
model_context_rows
cutoff_rule
cutoffs
ingestion_receipt
mapping
source_contract
publish_route
```

These are actual execution prerequisites, not a request for a new planning layer. Bind source-related fields to the existing verified recovery artifacts. Use the existing implementations in:
- `research/kalshi/frankie_boss/trading_day_schedule.py`
- `research/kalshi/frankie_boss/operations/prepare_trading_day.py`
- `deploy/aws/box/frankie_box_prepare_trading_day.py`
- `SPEC_LINUX_TRADING_DAY_PREPARATION_20260923.md`

Derive exact boundaries from already-ingested data, remotely, without ingestion restart/replay. Keep integer timestamps exact: use Python for nanosecond-bearing JSON rather than a JavaScript parse/stringify round trip. Do not treat the declared record count as a fresh ingestion measurement.

### Context rows and token reduction: avoid repeating the mistaken assumption

The owner explicitly rejected assuming 4,096 context rows are the correct Monday setting. No proposed 4,096/18-cutoff Monday configuration was committed. That proposal was withdrawn. Do not resurrect a stale draft or uncommitted blob.

Verified historical Sunday evidence:
- `research/kalshi/frankie_boss/sunday_20260915_package/FB/actual-feedback-run/initialization.c15.json`
- The same run's `execution/cycle-00/host-context-cache.c15.json` and `host-preparation.c15.json`
- Sunday configuration: `t_ctx=4096`; consumed/entity/prefix rows: `3262`; outside-context rows: `0`.
- Format: `stacked_v1`; historical input tokens: `92428`; context: `131072`; output remaining: `38644`.
- Those are historical measurements, not an approved Monday setting or a forecast of the new run's tokens.

One context row is one market record. Reducing the window can discard model input; it is not equivalent to lossless token compression. The normalization parameter `n_norm=4096` is a separate setting. Do not confuse them. Do not choose the smallest syntactically accepted window merely to get past validation.

Use the existing authorized scientific semantics and actual retained evidence to resolve the smallest defensible context/cutoff settings. If evidence cannot determine a required scientific choice, state that single concrete choice to the owner; do not invent approval or spend hours on alternatives. Do not copy Sunday's numeric cutoff spacing across Monday; the earlier attempt produced an excessive cycle count. The requested immediate objective is cycle 0, not execution of an arbitrary full-day roster.

The token reducers are **already in the pushed code**; no restoration patch was necessary:
- `stacked_v1` native context with lossless inversion.
- `Session._reading_corpus` repeated-evidence deduplication, stacked text/table blocks, known-file references, and prior-cycle ledger.
- Current `tensor_mode='identity'` preserves exact tensor bytes with statistics under the existing authorization.
- `Session.derive` → `_write_digest` → `frankie_box_digest_document.write_digest`, using **DIGEST_V6**.
- Review `deploy/aws/box/frankie_box_boss_session.py` and `deploy/aws/box/frankie_box_digest_document.py` only as needed to verify the actual invoked path.

Keep these reducers in the runtime being launched. Do not add BOSS truncation or output caps. Do not reopen broad reducer development.

## 3. Prepare from the recovered source through the existing remote route

After launch/configuration bindings are real and code has been staged at the dispatch SHA, use `frankie_box_run.yml` with:
- Script: `deploy/aws/box/frankie_box_prepare_trading_day.sh`.
- Variables: `ACTION=prepare`, the staging receipt's `CODE_ROOT`, an existing absolute `CONFIGURATION` path and its actual `CONFIGURATION_SHA256`, and a fresh `OUTPUT_ROOT` directly under `/opt/frankie-box/work/trading-day-preparation/`.
- The workflow supplies `MARKETS_SHA`; the adapter requires an exact clean checkout match.
- The configuration must point schedule/prefix output paths inside that fresh output root.
- Do not paste symbolic placeholders as executable workflow inputs.

Preparation reuses the existing operation, makes schedule/prefix artifacts and receipts, and performs no model calls or source replays. Preserve its receipt and artifact hashes. If the selected existing execution route requires publication, the same script's `ACTION=publish` requires a real private upload map and hash; do not print signed capabilities.

**Do not blindly run the stock pipeline configuration.** `operations/day_pipeline.configuration.json` still targets a different Windows host and contains C: host paths. It is not a ready-to-run Linux Monday configuration. Do not run journal ingestion, host stop, or cleanup stages to reach cycles.

## 4. Finish the concrete runtime bindings, then launch cycle 0

Carry out these steps in order. Each is part of the launch, not a separate workstream.

1. **Select the runtime already authorized in the retained handoffs.** Inventory its existing interpreter, packages, capacity, native dependencies, storage and endpoint readiness read-only. Do not assume the Linux box's installed torch/numpy versions equal the historical Sunday's versions. Use real measurements in its numeric/toolchain policy; do not silently claim old checkpoint compatibility on a changed host.
2. **Complete original step 1b coherently.** Bind Monday source, schedule, context selection, prefix ancestry/boundaries, packet seed, mapping, source contract, runtime and provenance together. Verify against the prepared artifacts and canonical recovery. A path rewrite or old Sunday prefix-00 does not establish this binding. Preserve the existing transfer/provenance descriptor and dependency/storage closure requirements.
3. **Bind the retained knowledge and model prerequisites.** Resolve brain/history, part4 and Granite priming acknowledgement from the existing artifacts/receipts. Reuse verified prerequisites; do not recreate completed classroom work. If one is actually absent, complete only that prerequisite through its existing route. Do not forge a priming/readiness acknowledgement.
4. **Produce the actual native configuration.** Use schema `FRANKIE_BOSS_ACTUAL_HOST_CONFIGURATION_V1`, real Monday pins, the correct `host_runtime.repository` and `boss_commit`, prepared prefix manifest, and the intended completion workflow ref. On a first launch select a fresh run ID/directory and record it once. On continuation retain the already-created run ID/directory. Initial flags `model_calls_performed=false` and `training_updates_performed=false` must be truthful. Set native runtime resources/numeric identity explicitly from the authorized runtime. Keep credentials out of JSON and logs.
5. **Do not reuse the Sunday builder blindly.** `operations/build_ec2_rerun_configuration.py` is pinned to a particular failed Sunday configuration and its source hash. It is not a generic Monday launch builder. Build/bind Monday inputs through the current preparation path and existing host contract instead of weakening those checks.
6. **Connect the existing Python runner on the allowed remote runtime.** The actual audited entry point is `research/kalshi/frankie_boss/operations/run_actual_sunday_ec2.py`. Despite its historical name, it composes the existing classroom host, compact source adapter, runtime identity and receipt resume behavior. Verify Monday admission against that code. The current `day_cycles.ps1` demonstrates its invocation, but do not run that Windows script or its stock Windows pipeline configuration under the present restrictions. If no Linux launch shell exists, add the minimal committed shell adapter to the existing `frankie_box_run.yml` route; do not add another planner, ingestion path, automatic deployment trigger or alternate native implementation. Preserve exit 3/4 receipts and full logs; never attach stop/cleanup to WAIT.
7. **Perform source/configuration admission with the real bindings.** Use the existing prepare-only mode if needed for the runner's required preparation/approval artifacts. It is not successful execution. If it creates the run directory/runtime identity, subsequent invocation must use `--ec2-resume`; never delete it to make first-launch admission pass. Carry all actual readiness/release inputs through the existing gates. The owner has explicitly requested launch; do not ask a repeated general permission question. Do not turn that request into a fabricated release receipt.
8. **Invoke exactly one initial cycle.** The verified runner accepts the following command shape. These are remote shell variables that Claude must bind to real paths, not literal placeholders for the user to paste:

```sh
"$PYTHON" -B "$CODE_ROOT/research/kalshi/frankie_boss/operations/run_actual_sunday_ec2.py" \
  --configuration "$ACTUAL_CONFIGURATION" \
  --compact-source-tools "$CODE_ROOT" \
  --cycles 1 \
  --pending-return
```

   Use the existing credential mechanism without printing credentials. Use the exact staged code and admitted configuration. `--cycles 1` means the first scheduled cycle (cycle 0); it does not mean cycle index 1. If step 7 already initialized this exact run, add `--ec2-resume`. Never add that flag to adopt an unrelated historical run. Do not invoke bare `run_actual_sunday.py` as a shortcut: the EC2 wrapper preserves classroom composition and runtime identity.

9. **Handle WAIT through the already-implemented workflow.** Read the durable WAIT/ATTENTION receipt. Export/archive the exact existing request, deliver verified readiness or record the principal response through the existing workflow, and let its receipt-bound callback resume the same run. Keep exact request hash, job ID, context, configuration, code, schedule and target-cycle scope. Do not issue new inference merely because transport or acknowledgement is ambiguous.
10. **Use the exact retained WAIT hash on resume.** The native same-run command adds `--ec2-resume --resume-wait-sha256 "$WAIT_SHA256"` while retaining `--cycles 1 --pending-return`, the same configuration and the same run. The callback must pass the verified actual WAIT hash, not a newly invented receipt. The pipeline's corresponding option is `--resume-wait`; do not confuse its option with the native runner's `--resume-wait-sha256`. Do not dispatch the entire journal workflow if that would restart ingestion or invoke host-stop cleanup.
11. **Interpret the actual result.** Exit 3/4 with a durable WAIT/ATTENTION is pending, not failed work to restart and not completed cycle 0. A `stopped` record identifies a concrete blocker; use its type/code frames and fix only that blocker. Incomplete output is not completion; preserve the evidence and same job. A live model job or advancing native host-progress proves execution has started. An SSM acknowledgement, staged checkout or GitHub green check alone does not.
12. **Report launch and completion separately.** Once execution has really started, report the workflow URL, run ID, cycle 0, dispatched code SHA, configuration pin and actual model/native status. On completion require the runner's `requested_cycles_complete` (or `all_scheduled_cycles_complete` for a one-cycle schedule) with `cycles=1`, plus retained cycle outcome/response/checkpoint evidence. Do not automatically expand the initial one-cycle scope after this handoff's objective is met.

The workflow automation is already implemented and pushed:
- Receipt-bound WAIT/ATTENTION with retained execution scope.
- Verified readiness/principal response callbacks.
- Same-run resume with exact request/job/cycle identity and retained context.
- Replay-safe request archive and dispatch evidence.
- Existing day pipeline/host workflow integration.

Relevant integration files: `operations/day_pipeline.py`, `operations/workflow_wait.py`, `deploy/aws/host/day_cycles.ps1`, `.github/workflows/frankie_journal_stack.yml`, `.github/workflows/frankie_deliver_readiness.yml`, and `.github/workflows/frankie_host_record_principal_response.yml`. The Windows files describe current integration; their presence does not authorize Windows operational access.

**Known limit of this handoff:** no verified, fully bound Monday native launch command/configuration exists yet in this continuation. The command above documents the real runner CLI, not a claim that its prerequisites are filled. Resolve those concrete inputs and the minimal allowed Linux dispatch connection, then execute. Do not tell the owner to paste guesses or claim that another inventory run is launch.

## Preserved source and restrictions

Canonical original:
```text
/opt/frankie-box/work/ingest-20211004-ingest-1790057801/journal.compact.sqlite
bytes: 23687368704
sha256: 947949d84732b0d7fa22b2e853ee89fdcfaf995955d9de652b36b344333b9888
```
Recovery directory: `/opt/frankie-box/work/sealed-recovery-35796793428`.
Published evidence: `s3://frankie-granite42-568968024170-us-east-1/readiness/20260922/sealed-recovery/35797500956/`.
Recovery verifier run: `35797842849`.
Trading day: `20211004`, Sunday 18:00 through Monday 17:00 Eastern; Friday anchor: `5.544`.

Restrictions remain:
- Remote Markets operations only. No local filesystem/shell/checkout or C:/E: operational access. The one-time Codex cache repair exception does not authorize local Markets work.
- No ingestion restart/replay; no runtime/Pod/instance stop or termination.
- No pinned bootstrap changes, evidence deletion, key disclosure, Amazon Bedrock, or BOSS truncation/output caps.
- No parallel agents or parallel work.
- No additional broad tests or classroom reruns without a concrete cycle-0 blocker.
- No unrequested production push-trigger automation.
- Preserve canonical recovery evidence and exact request/job identity.
- Add `Co-Authored-By: Codex <noreply@openai.com>` to repository commits made by Codex.

Existing verification: 262 focused tests passed for the implementation candidate; final host-contract/readiness checks passed. Those results are not evidence that Monday's missing launch configuration has been supplied. Do not repeat completed verification just to delay deployment.

**Stay on this sequence: verify current remote state → stage the right script → bind the real Monday inputs → prepare existing data → launch cycle 0 → verify actual execution. Do not diverge.**
