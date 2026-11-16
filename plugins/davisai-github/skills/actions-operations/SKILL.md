---
name: actions-operations
description: How to read, diagnose and (only on Greg's explicit go) dispatch the GitHub Actions workflows in DavisAI1974/Markets - the collector, ingest, CI, AWS guard and Frankie box/host/pod workflows. Use before listing or inspecting workflow runs, reading run logs, answering "did the collector run", "why is this run queued", or before any workflow dispatch, re-run or cancel.
---

# DavisAI GitHub Actions operations

## 0. HOLD is the default

Reading is free. Acting is not.

- **No dispatch, re-run or cancel of any `frankie_*` workflow, and nothing that starts, stops or
  changes a box, Pod, EC2 instance or Granite run, without Greg's explicit go in this
  conversation, step by step.** A go for one step is not a go for the next.
- Never redispatch a cancelled run on your own. Never stop a Pod on your own.
- Collector and CI workflows are lower stakes, but a dispatch still spends runner minutes: say
  what you are about to run and why before running it.
- Listing runs, reading jobs and reading logs need no go.

## 1. The workflow map (`.github/workflows/`)

| Group | Files | Trigger | Notes |
|---|---|---|---|
| Durable collectors | `kalshi_collectors_durable.yml`, `pyth_collector_durable.yml` | cron every 6 h, dispatch, push to the trunk on their own paths | Check out `CODE_REF` (the trunk) and push bins to a `data/*` branch |
| Weather and tape | `nws_hourly_collector_durable.yml`, `nymex_mbp10_ingest_durable.yml` | cron, dispatch | Write to S3, not git |
| Free NG collectors | `free_ng_collectors.yml` | cron, dispatch, push, pull_request | Research inputs only - no execution authority from these feeds |
| Cost guard | `aws_idle_instance_guard.yml` | cron every 6 h, dispatch | Stops EC2 idle six hours unless tagged `KeepRunning=true`. Manual dispatch is a dry run unless `stop` is true |
| CI | `ng_live_build_ci.yml`, `frankie_box_codecs_ci.yml`, `frankie_cycle_identity_ci.yml`, `frankie_host_scripts_ci.yml` | push and/or pull_request | Billed on every qualifying push - hence `[skip ci]` |
| Frankie box | `frankie_box_run.yml`, `frankie_box_control.yml`, `frankie_box_fetch_response.yml` | dispatch only | `frankie_box_run.yml` sends one committed script from `deploy/aws/box/` over SSM |
| Frankie host | `frankie_host_*.yml` | dispatch only | Cycle status, reports, probes, supersede and record steps |
| Frankie pod and retained | `frankie_pod_control.yml`, `frankie_pod_prepare.yml`, `frankie_retained_*.yml`, `frankie_serverless_reading.yml`, `frankie_runpod_key_to_ssm.yml` | dispatch (two retained ones also on push) | Pods bill by the hour |

Before any Frankie work, load the repository's `full-run-orchestrator` or
`experiment-orchestrator` skill. Its current drop-in doc holds the live run ids, paths and shas.

## 2. Reading a run

1. List runs for the workflow, newest first. Report the run id, branch, head sha, event, status
   and conclusion - not just "green".
2. Open the jobs, then the failed step's log. Quote the failing lines.
3. **A green workflow is not proof of execution.** For box and host workflows only a receipt
   proves a step ran. A wrong `script` input with a valid `ACTION` has come back green before.
4. Long output arrives paged as "report part i/n" - read every part.
5. Exit 3 or 4 from a cycle launch is a durable WAIT, not a failure.

## 3. Common diagnoses

| Symptom | Most likely cause | What to do |
|---|---|---|
| Run sits `queued` and never starts | Account-level Actions issue: billing, minutes or runner cap | Not a workflow bug. Tell Greg; do not edit the workflow |
| Cron never fires | Scheduled workflows run only from the repository's default branch | Check that the file exists on the default branch and what `CODE_REF` points at |
| Collector run green but no new data | The data branch did not accrue | Check the tip and date of `data/kalshi-bins` / `data/pyth-ticks` before trusting it |
| Unexpected CI run after a push | Push-triggered workflow and no `[skip ci]` | Add `[skip ci]` to docs, research and data commits |
| Pyth symbol flat or expired | Front-month contract rolled | Use the repository's `kalshi-roll` skill |
| Box step refuses: staged checkout differs from `MARKETS_SHA` | Something was pushed to the run branch after staging | Stage last, dispatch from that exact tip |
| AWS step fails on credentials | Session token expired or a secret is missing | Name the missing secret; never print or ask for its value in chat |

## 4. Dispatching (after Greg's go)

- State the workflow file, the ref, and every input value, then dispatch exactly that.
- `frankie_box_run.yml` inputs: `script`, `variables` (space-separated `NAME=VALUE`, no quotes,
  no spaces inside values), `timeout` (default 1800 - set it for long stages), `instance`,
  `region`, `comment`. **Check `script` before every dispatch.**
- After dispatch, report the run id and URL, then follow it with a probe - do not assume.
- If the token cannot dispatch (the "Run workflow" permission is missing), say so and give Greg
  the exact file, ref and inputs to run by hand.

## 5. Secrets referenced by the workflows

`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_SESSION_TOKEN`, `RUNPOD_API_KEY`,
`DATABENTO_API_KEY`, `EIA_API_KEY`. Names only. Values are never read, echoed, logged or passed
as a workflow input.
