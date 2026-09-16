# Claude Code takeover — Frankie audit and box navigation, 2026-09-16

Greg's latest instruction: **do the audit, write a handoff, and Claude takes over the box; include how to navigate the Pod box.** Codex completed audit/report work only. Read `AUDIT.md` and its receipts first. **HOLD: not launch-ready.** No new result-bearing launch authorization is implied by this handoff.

## Start on the workstation

Use the installed `using-agent-skills` and relevant Runpod/review/debugging skills. Existing checkouts:

```powershell
Set-Location E:\Markets
git rev-parse HEAD
git status --short
# Expected audited recovery tip: 34301ac081016a1e750bd99303267e27941aeb9e

git -C E:\Markets-receiver rev-parse HEAD
# Expected receiver tip: 2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134

git -C E:\Markets-classroom rev-parse HEAD
```

`E:\Markets` has an untracked `.github/workflows/boss_frankie_tests.yml`: preserve it; do not push or execute it. The receiver is a worktree with per-worktree `core.autocrlf=false`; do not change the shared `E:\Markets\.git\config`. Byte identity is part of runtime/parser/knowledge admission. Inspect any dirty state and preserve unrelated work. Use an isolated integration branch/worktree for changes.

Freeze the three audit SHAs in `AUDIT.md` before merging. Fetch newer tips only to inspect changes; if tips advanced, audit the difference rather than silently treating this report as covering them. The classroom integration/review branches and handoffs are named in the recovery branch's `DROP_IN_NEXT_CHAT_20260917.md`. That document contains older tips; the audit's checked SHAs take priority as observed facts.

## Runpod: connect to the existing Granite Pod

Runpod hosts **Granite/service inference**. Native/stateful BOSS runs on the Windows EC2 host below. Their CPUs are separate authority domains, not one optimizer pool.

1. Open `https://console.runpod.io`, select **Pods** in the left sidebar. Select `granite-smoke-4e2ecee03d7b2bb77da16180aba4f98d-migration`, id **`ycf4v6lmave6xw`**. This is the retained RUNNING Pod. The similarly named old id `jvs75m56w8f73q` is EXITED.
2. Inspect its details and **Connect** panel. Use its offered web terminal or SSH connection. Prefer the live Connect command if the proxy suffix changed.
3. The exact SSH proxy command returned by the audit's live Runpod read is:

```powershell
ssh ycf4v6lmave6xw-6441231d@ssh.runpod.io
```

Runpod proxy host is `ssh.runpod.io`, port 22. This requires the already configured public/private SSH key pair. If SSH refuses a key, use the existing console terminal or resolve existing SSH-key registration; do not paste private keys or service tokens into chat/Git. The Runpod MCP tools list/get Pods and logs; they do not give an SSH shell or perform file transfer.

### Read-only navigation inside the Linux Pod

```bash
pwd
ls -lah /opt/ml
ls -lah /opt/ml/model
ls -lah /opt/ml/additional-model-data-sources
ls -lah /opt/ml/additional-model-data-sources/bootstrap-jobs-v1
ls -lah /opt/ml/granite-jobs-v1
ps -eo pid,ppid,etime,args | grep -E 'granite|vllm|supervisor' | grep -v grep
ss -lntp | grep -E ':8080|:8081'
```

Paths come from the current code/live Pod bootstrap configuration:

| Path/port | Purpose |
|---|---|
| `/opt/ml` | persistent 50-GB mount; preserve it |
| `/opt/ml/model` | exact staged model artifacts |
| `/opt/ml/additional-model-data-sources/bootstrap-jobs-v1` | retained migrated bootstrap modules/manifest |
| `/opt/ml/granite-jobs-v1` | durable job spool, result and dispatch evidence |
| `127.0.0.1:8080` | vLLM backend |
| `8081/http` | authenticated bounded proxy, published by Runpod |

List directories before reading contents; job IDs/results and startup identity are evidence. Do not dump `env`, secrets or presigned bootstrap URLs. Find the actual spool filenames by `ls`; do not assume a SQLite name or edit/delete its files. Inspect status/logs from the Pod details panel or available Runpod log tools. Backend readiness can be inspected with a local read-only `/health` GET; the published proxy `/health` requires the existing service credential. RUNNING is infrastructure status, not proof of model readiness.

The durable proxy protocol is `jobs_v1`: an existing `/v1/jobs/<64-hex-id>` GET reads status and `/result` reads its retained result. A POST submits a job; do not issue one during takeover inspection. Before any restart or repair, identify pending/completed/ambiguous intents in both host critic spool and Pod spool. Never create another job ID, resend inference, or restart the Pod to resolve an ambiguous dispatch. Preserve exact response bytes and use the existing status/recovery paths.

Live tool cost field is **1.09** for the retained L40S Pod; the screenshot shows a separate UI hourly figure. Read current price/status before any billable action. No duplicate deployment is necessary.

## Native Windows EC2: navigation and takeover

Audited live instance: **`i-0e90ee6110ef609aa`**, `r7i.4xlarge`, Windows Server 2022 as recorded in the restoration handoff, region `us-east-2`, STOPPED, profile `Ssm`, `KeepRunning=false`.

Read status from the workstation using the existing helper and existing private AWS environment file:

```powershell
Set-Location E:\Markets
python deploy/aws/ec2_host.py --instance i-0e90ee6110ef609aa --region us-east-2 --env-file scratchpad/aws.env status
```

When takeover work requires a running host, use the existing start helper within Greg's authorization. It waits for SSM Online. The recorded Windows hourly planning rate is about $1.80; verify current rate before starting. Starting it is distinct from launching a Frankie run.

Use **AWS Systems Manager → Session Manager** for this instance, or send a saved PowerShell script through the existing runner:

```powershell
python deploy/aws/ssm_run_ps1.py --instance i-0e90ee6110ef609aa --region us-east-2 --script <saved-inspection.ps1> --env-file scratchpad/aws.env --timeout 1800
```

That sends the actual script bytes as `AWS-RunPowerShellScript`. Keep tokens/presigned URLs out of scripts that enter SSM history. Do not print AWS credentials. Inside the Windows host, inspect:

```powershell
Get-PSDrive -Name C,E
Get-Item C:\Python313\python.exe
git -C C:\tools\Markets rev-parse HEAD
Get-Content E:\Codex\RESTORE_RECEIPT_20260916.json
Get-ChildItem E:\bench -File
Get-CimInstance Win32_Process | Where-Object Name -Match 'python' | Select-Object ProcessId,CommandLine
```

Recorded paths: `C:\tools\Markets` tools checkout, `C:\Python313` Python 3.13.7, `E:\Codex\Frankie-BOSS-20260915` path-preserving restoration, `E:\bench` disposable benchmark outputs. Actual evidence receipts contain both C: and E: absolute paths; recreate them rather than rewriting receipts. Existing restore/inspection/benchmark scripts are under `deploy/aws/`. Existing object set is `s3://bento-568968024170-us-east-2-an/frankie/sunday_20260915_restore/`. The host has been restored/benchmarked in later sessions; the older AccessDenied/"not run" handoff is superseded. Verify current receipt/files before attempting restoration again.

The later host session also reports the receiver was restored as a worktree without its parent Git repository (`RECEIVER_HEAD` empty). The benchmark bypassed that dependency; principal preparation cannot. Verify `git rev-parse HEAD` at the configuration's exact `receiver_root`, reconstruct the intended receiver checkout/parent when necessary, and verify `2ebb8ce8` plus byte hashes. Do not confuse a working tools checkout at `C:\tools\Markets` with a valid receiver at the pinned historical C: path.

Do not rerun the completed 8-versus-16 benchmark merely because an older handoff says it is pending. `CCODE_SESSION_20260916_RESTORE_BENCHMARK_COMPACT_SOURCE.md` records both completed: 525 versus 494 seconds, peak private about 24 GB and pagefile about 32 GB. Result hashes differ with thread count. Greg selected **8 threads**, fixed throughout the new result-bearing identity. Preserve the original failed cycle-00 directory.

## Claude's next work, in order

1. Reconcile current recovery `34301ac`, classroom composition `d152dd8` and receiver `2ebb8ce8` in isolation. Preserve all compatible reducers, migrated Pod semantics and classroom coverage/causality.
2. Close the audit findings: exact host/adapter composition including compact source; sealed proof before the final model-facing request; current output receipt/32 required ledgers after response; independent prior-memory witness; authority map writers; receiver preparation arguments and declared historical policy.
3. Produce a fresh final run configuration. Replace stale old receiver/completion pins only after code/config/package agreement is proved. Keep old config/evidence intact. Re-render all 99 layers per actual cycle/attachment; historical cycle-0 counts alone are insufficient.
4. Verify remote restoration and code/toolchain/line-ending hashes without duplicating restoration or benchmarks. Audit the final integrated SHA and config on the actual host. The full-journal receipt in this handoff covers the retained workstation compact file, not every remote object.
5. Require Frankie to author both documents himself, covering FINDINGS, BUILD, DATA and SUGGESTION, plus the complete governed output bundle. Supply finalize's `--what-he-learned` and `--in-his-own-words`. Carry the committed completed run with `carry_run_into_memory --write --run-id <id>` and verify it with `--check`; do not replace frozen Sunday comparison memory with the refreshed carry.
6. Return concrete readiness evidence to Greg. Sunday alone is first; the October 4–6 block follows his sequence. No new workflow or result-bearing launch until his explicit go.

Never change MBO/FIFO/full-book, Dipole mathematics, refrag, calculations/planes/adapters/replay, causal clocks, loss/optimizer, or retained weighting to make a gate pass. Never filter, truncate, smooth or sample required evidence. Preserve ambiguous service/principal intents and exact retained outputs. Host teardown/power decisions must respect active work and Greg's retained-Pod instructions; do not terminate the Pod, instance or volumes.
