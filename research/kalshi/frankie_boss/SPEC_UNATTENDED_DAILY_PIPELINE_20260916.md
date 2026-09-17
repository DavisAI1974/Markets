# Spec: the unattended day pipeline (beginning to end, nobody babysitting)

Status: ORCHESTRATOR BUILT 2026-09-17 (`operations/day_pipeline.py`, `.github/workflows/frankie_day_pipeline.yml`, dispatch only, no cron); the three host scripts under `deploy/aws/host/` are the remaining piece (prerequisites 1-6 below still hold). Design 2026-09-16, sequenced after the Sunday run. Greg: "we need a workflow that gets
this thing going from beginning to end without us." Built with the ci-cd-and-automation skill's
shape: one orchestrating GitHub Actions workflow, every stage idempotent, every stage gated by a
receipt the next stage verifies, credentials never in files, cost bounded by starting and stopping
the compute it uses.

## Where each stage runs, and why

| stage | runs on | why there |
|---|---|---|
| orchestration, gates, receipts to git | GitHub-hosted runner | free, durable log, git is the record |
| stage sources (day files pinned into the day's S3 prefix, manifest) | GitHub runner | S3-to-S3 copy plus an in-memory decode; 110 MB per day; `operations/stage_block_sources.py` already does it |
| ingestion (DBN to compact journal), schedule, prefixes, seeds | the native host over SSM | CPU-bound hours, needs the 16 vCPU and the E: volume; GitHub runners are 4 vCPU and ephemeral |
| the native learner step per cycle | the native host over SSM | needs 32-40 GB (measured 32 GB at 3,262 rows); no GitHub runner class we pay for has it |
| the Granite critic per cycle | the Pod, dispatched from the host | as today (`granite_durable_job_client`), credential via stdin from a GitHub secret passed through SSM parameter, never a file |
| the principal (Frankie) | as today's recorded-principal handoff | out of scope for automation until the principal is a service |
| package, upload, snapshot, stop | GitHub runner (S3 API, EC2 API) | `upload_sunday_restore_set.py`, `ec2_host.py snapshot`, `ec2_host.py stop` |

## The chain

```
schedule: cron after the daily halt (18:30 ET) or workflow_dispatch(day)
  1. stage-sources     -> blocks/<DAY>_SOURCE_MANIFEST.json committed         gate: manifest_hash, counts
  2. host-start        -> ec2_host.py start (waits for SSM Online)             gate: state=running, SSM Online
  3. ingest            -> ssm_run: DBN -> compact (single pass) + completion   gate: seal (count, head) == completion; compact sha256 pinned
  4. schedule+prefixes -> ssm_run: cutoffs, receipts, seeds (single pass)      gate: 19..N receipts, every prefix sha pinned, referenced-files audit passes
  5. cycles            -> ssm_run: run_actual_sunday_compact_source (host class)  gate: completion.c15.json per cycle; resumable by design (same run directory)
  6. package+upload    -> restore set for the day to S3, manifest in git       gate: UPLOAD_MANIFEST sha-pinned; readback of receipts
  7. snapshot+stop     -> ec2_host.py snapshot --label <DAY>; ec2_host.py stop gate: snapshot completed; state=stopped
```

Every stage writes one receipt file under `runs/<DAY>/` in git (small JSON, no data), and the
workflow's job summary is those receipts. A failed stage stops the chain, stops the host (always,
in `if: always()`), and leaves the receipts of the stages that passed; the next dispatch resumes
from the first stage whose receipt is missing, because every stage is idempotent (today's restore
skips present bulk by hash, the proof rebuilds nothing, the host's cycle loop resumes from
retained completion files).

## What has to exist before this can be wired (all listed elsewhere, none new)

1. DBN-to-compact single-pass ingestion with the builder's per-record cost measured (ingestion
   review finding; the block's 6.47 M records make it mandatory).
2. Single-pass cutoff compiler emitting receipts and seeds (Part 2 item 2).
3. Every Sunday literal (57027, 19, 20211003) turned into a manifest field (session record §5).
4. The prepared-source-once path (spec) so a cycle is seconds of preparation, not minutes.
5. A Linux host image (Greg: no Windows after the Sunday run): the same tools, `ec2_host.py`,
   `ssm_run` with a bash document instead of PowerShell; everything else is OS-neutral.
6. GitHub secrets: the AWS pair with S3 + EC2 + SSM rights only; the Pod credential; both reach
   the host as SSM parameters read once on stdin, as the host already requires.

## What today already provides

`ec2_host.py` (start/stop/snapshot with waits), `ssm_run_ps1.py` (send, wait, exit code),
`presign_restore_set.py` and `restore_sunday_set_on_host.py` (idempotent restore with receipt),
`run_actual_sunday_compact_source.py --verify-source-only` (a gate that runs in 11 s),
`audit_sunday_referenced_files.py` (a gate that the day's set is complete),
`stage_block_sources.py` (stage 1), `.github/workflows/boss_frankie_tests.yml` (the test gate on
every push). The orchestrator is the missing piece and it is the smallest one.

## Not automated on purpose

Greg's go for a result-bearing run. The orchestrator takes a `go` input naming the day and the
manifest hash it may run; without it, stages 1-4 run (data plane only) and the chain stops before
stage 5 with a receipt saying so. That keeps "nothing that runs it" enforceable by the workflow,
not by memory.
