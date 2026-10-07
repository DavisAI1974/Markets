# CCode Step 8A return: the CPU controller's lifetime and launch routing, 2026-10-07

Assignment: `CCODE_NEXT_SOURCE_TASKS_20261006.md`, "ACTIVE CCODE ASSIGNMENT, Step 8A CPU controller lifetime and launch
routing" (Greg, 2026-10-06 23:30-23:33 ET). Assigned in Codex's `3a1416b7` (which integrated the sixth return `31832bf2`); the codebase-memory index was rebuilt on
that tree before any code change; returned rebased onto Codex's CURRENT tip `439cb0bf` (its three step-5 successor commits
touch none of the 8A files; its docs say the 8A assignment remains active and disjoint). Commits, one per
group, then the two review passes: `bc178ff3` the controller's lifetime, prerequisites and controls (controller.py + the
launcher) | `bd28796e` the reachable Pod routes closed (frankie_box_run.yml + the marker) | `bdf7122b` review pass 1 (17
findings) | `cdeb61ce` review pass 2 (10 findings) | the documentation commit (this file; the handoffs and drop-ins).

SOURCE-BUILT / RUNTIME-UNVERIFIED, every line of it: `ast.parse` and `compile` without project imports, a static check that
every dotted module used is imported and every bare call is defined, `sh -n` / `dash -n` / `bash -n` on both shell files,
`yaml.safe_load` on the workflow, `git diff --check`; the code-review skill run over `origin/ccr-5fce7de3-xa4hfg..HEAD` at
high effort before the push, twice. Nothing ran: no test, synthetic stream, install, project/model/data run, historical
reproduction, AWS inspection or action, start, dispatch, canary or E2E. Both boxes untouched. No credential workaround. No
new AWS service, booking, host, lane or Pod. Pins and threads null unchanged. Steps 2-7 are not closed by this; this slice
does not close all of Step 8 and authorizes nothing of Steps 9/10.

## 1. The action-to-entrypoint / owner / receipt map (the trace, item 1)

Two hosts run ONE controller, `research/kalshi/frankie_boss/pod_root/controller.py` (CCode's). The box side it drives is
`deploy/aws/box/frankie_box_pod_root.sh` -> `frankie_box_pod_root.py` on the main box (claims, queue, export, prepare,
coordinate, release, status; reads the main orchestrator's saved plan and Frankie's ROOT line) and `pod_agent.py` on the
Linux worker (work, jobs, renew, resume, stop, clean). Neither of those is CCode's; both were used as they are.

### 1a. The runner route (bounded): `frankie_box_run.yml` script=`deploy/aws/box/frankie_box_pod_root_loop.sh`

The marker runs nothing on the box; the step "AWS CPU Linux lane controller" runs the controller on the GitHub runner with
the runner's AWS keys, `--commit $GITHUB_SHA`, `--budget-minutes 330`. Inputs: `ACTION RUN CODE_ROOT BOXES SLOTS
[DATA_WORKERS] [BUDGET_MINUTES] [JOB]`; everything else refuses (retired Pod inputs, `RUNPOD_API_KEY`, and the main-box-only
`HOST` / `STATE_DIR`, even when empty).

| ACTION | what the controller does | entry points reached (owner) | receipt / record |
|---|---|---|---|
| plan | read-only | main `queue` (plan.json of the main orchestrator, Codex's; claims, frankie_box_root_claims; ROOT line, frankie_queue, Codex's); the S3 lease read | the job log and box-run artifact only |
| status | read-only | main `status` (claims listing, import receipts); worker `jobs` (`/opt/frankie-box/pod-agent/jobs/<attempt>/state.json`); the lease | log only |
| loop | the lease taken (create-only in S3); main `enable`; every poll: worker `jobs`; per live held job every 15 min `renew` (mailbox re-signed, inputs re-signed, S3 `pod-root/<run>/<attempt>/job.json` rewritten); `coordinate` on the main box when a job waits on it (frankie_box_lane_state.coordinate, Codex's); retained jobs held; a free slot: main `claim` (create-only `root-claims/<run>/<day>.json`) -> main `export`, one file per call -> S3 `job.json` (create-only) -> worker `work` | the claim file; `job.json`; the worker's `state.json`; the controller journal `pod-root/<run>/controller/<GITHUB_RUN_ID>.json` and the `pod-root-controller-<run_id>.json` artifact; the lease released with the outcome `budget_expired` (never completion) |
| resume JOB | the lease; the day must still be claimed by this worker; `renew(resume)`: the stored `job.json` (or main `prepare` + the retained export when it is missing) -> worker `resume` (pod_agent `renew_job(resume=True)` -> `launch`); then the loop serves that job only | outcome `resumed_job_complete` / `resumed_job_retained` / `budget_expired` |
| stop JOB | worker `stop` (pod_agent `stop_job` -> `save-request.json`; the job saves and exits 75); the claim untouched | the worker's `state.json` (read through status); no completion is written |

A runner `loop` or `resume` is refused while a main-box service holds the run's lease (section 3).

### 1b. The main-box route (the lifetime): `frankie_box_run.yml` script=`deploy/aws/box/frankie_box_cpu_controller.sh`

Dispatched like any committed box script (over SSM to the main box, `MARKETS_SHA` set by the workflow); the launcher is
the experiment launcher's DETACH pattern (`frankie_box_experiment.sh`): the dispatch returns once the unit is up. Inputs:
`ACTION RUN CODE_ROOT [SAVE] [JOB] [GO] [DATA_WORKERS] [POLL_SECONDS] [STOP_WAIT_MINUTES]`; `BOXES`/`SLOTS` fixed to the one
Linux lane; retired Pod inputs refused even when empty. State: `/opt/frankie-box/work/cpu-controller/<RUN>/`.

| ACTION | what happens | record |
|---|---|---|
| preflight | `controller.py --action preflight --host main`: each prerequisite beyond source checked read-only and named (section 4); exit 2 refuses activation | printed JSON |
| start (GO=GREG_AWS_GO) | refused while a controller of RUN holds `controller.lock`, while an unacknowledged stop or an unanswered resume request stands, or when preflight refuses; else `systemd-run --unit frankie-cpu-controller-<RUN>-<epoch>` running `controller.py --action loop --host main --budget-minutes 0 --commit MARKETS_SHA`; 10 s later: active, or ended on its own (its outcome printed; only `no_remaining_work` is a clean end, anything else exits 3) | `controller.json` (identity, write-once per start, the previous kept as `controller-<epoch>.json`), the lease, the log `/opt/frankie-box/logs/cpu-controller-<RUN>.log` |
| status | no AWS call: the controller process (identity, lock held, holder pid, last `status.json`, stop request/ack, resume request/acks, outcomes) and the worker's LAST-SEEN job, reported distinctly, plus the run's claim files | printed JSON (`--action retained`) |
| stop [SAVE=on|off] | `stop-request.json` written create-only (refused when none is alive, or one stands); the service relays a save to the worker's live held job (SAVE=on), waits up to its stop wait for the job to leave its active stages, then writes `stop-ack.json` naming what is still pending and what continues unattended, and ends | the request; the acknowledgment (pending until the next poll) |
| resume JOB (GO) | `resume-request.json` to the running service: it renews the ORIGINAL job, claim and inputs and resumes it on the worker, or refuses with the reason (claim not this worker's, job live or complete, a stop pending); the request is archived beside `resume-ack-<epoch>.json` | the acknowledgment |
| clear_stop | an unacknowledged stop request (its controller died first) moved aside as `stop-request-<epoch>.json`; refused under a live controller | nothing deleted |

The service's own end states (`outcome-<epoch>.json`, `complete` always false): `no_remaining_work` (no day the Linux lane
could take or is holding, no worker job of the run incomplete; the main lanes and scientific completion are NOT judged),
`blocked_by_start_failures` (the only remaining Linux-lane work is days whose start failed twice; the events say why),
`stop_acknowledged`, `resumed_job_complete`, `resumed_job_retained`, `worker_unreachable` (10 consecutive status failures),
`lease_lost`, `terminated_by_signal`, `refused`, `failed`. A finite budget (runner) ends as `budget_expired`.

### 1c. What was NOT built: a second scheduler, a main-lane stop, Jev

Day scheduling stays where it was: the main orchestrator's plan and Frankie's ROOT line decide which day is ready; the
controller takes the front ready day for the one Linux slot. No main-lane stop/resume was wired (Codex's; section 6). No
Jev route (Codex's step 7); a Linux day whose `day_complete` waits on Jev shows as a held job and the service waits.

## 2. Controller / worker recovery ownership

- The worker's job (`pod_agent.py`): its states, `save-request.json`, retained files and the 16-CPU lane are the worker's.
  The controller only submits, renews, relays a save, and accounts. A `root-to-finish` job that leaves its active stages
  without `day_complete` is held, never released or cleaned; a job whose process is alive counts as active whatever its
  last written state (a just-resumed job carries its old state until it writes its own).
- The claim (`frankie_box_root_claims.py` on the main box): created create-only by the controller's `claim`; released by
  the controller only for a LEGACY shipping job's failed state (none can be started any more); a held day's claim is never
  released or cleared by any controller action, a stop included.
- The controller's own state: the state directory and the lease. If the service dies (SIGKILL, host reboot): the claim
  stays, the job keeps running or is retained, the lease goes stale after `LEASE_FRESH_SECONDS` (600 s); the next start
  takes the stale lease over conditionally on its ETag (recorded as `taken_over` in the lease) and resumes the
  coordination of a LIVE job by itself (renewal, coordination requests); a RETAINED job needs an explicit resume request;
  nothing is restarted or re-attempted on its own. Two controllers cannot hold one run: a create-only lease, conditional
  heartbeats, and a controller that loses its lease ends without touching the worker or a claim.
- The main lanes: Codex's (the handoff's "Main save/resume remains a real ownership gap" stands); section 6.

## 3. One controller per run, across hosts

`s3://frankie-granite42-568968024170-us-east-1/pod-root/<run>/controller/lease.json`: created with `IfNoneMatch: *`; every
later write (a heartbeat every 60 s, the release at exit) carries `IfMatch` of the ETag this controller last wrote; a stale
or released lease is taken over with `IfMatch` of the ETag read, so two takers of one stale lease cannot both win. A runner
loop refuses under a live main-box lease and names the service's own stop/resume routes; a main-box start refuses under a
live runner lease. On the main host `controller.lock` (flock, held for the process lifetime) refuses a second start before
the lease is even read, and the launcher's liveness is that lock (`controller.alive_pid`), never a command-line pattern.

## 4. Dependencies still missing (named; nothing provisioned here)

1. **The main box's instance profile.** The runner's keys did what the service now needs from the box: on
   `frankie-granite42-568968024170-us-east-1`, s3:ListBucket, GetObject, PutObject, DeleteObject under `pod-root/*` and
   `box-runs/*`; on `bento-568968024170-us-east-2-an`, s3:ListBucket and HeadObject under `frankie/ingest/*` and
   `frankie/day_external/*`; ssm:DescribeInstanceInformation, SendCommand and GetCommandInvocation on
   `i-0d17573dbce871520`; sts:GetCallerIdentity. The workflow's own comments say the box role "reads nothing in S3" today.
   Preflight proves the credential chain, the two list permissions, the lease read and the worker's SSM registration
   read-only; SendCommand and PutObject are proven only by the first use (the first status poll, the lease write). This
   cannot be established from source; a missing one is named and activation refused. Whether and how the profile is
   changed is Greg's decision; the launcher installs and provisions nothing.
2. **The signing window on the main host.** URLs are signed with the instance profile's session; the controller asks
   botocore for fresh credentials before signing (it refreshes inside its advisory window) and bounds every ExpiresIn to
   what remains (at most 1 h). The worker reads its input URLs once at job start and does not refresh them mid-fetch
   (`pod_agent.fetch_inputs` -> `pod_transfer.get_to_file` breaks on 403): an expiry during a long input fetch ends the
   job `failed_inputs` with its partial bytes retained, the claim held; the resume request re-signs and continues from
   the retained bytes. Exports go one file per call with slots signed just before it. Not a silent failure; a limit.
3. **The saved main plan** `/opt/frankie-box/work/experiment/<RUN>/plan.json`: the main orchestrator (Codex's) writes it at
   its first start of the run; the service refuses to start without it, and `queue` refuses without it on the runner.
4. **The claim store** `/opt/frankie-box/work/root-claims/`: `enable` creates it (idempotent, as before); the loop
   refuses when it is not active afterwards.
5. **The worker box** set up by `frankie_box_worker_setup.sh` (venv, pins, checkout) and Online in SSM; the B1
   duckdb/pyarrow Linux dependency named in the step-1 handoff is untouched and unverified here.
6. **systemd-run and the box venv with boto3 on the main box** (the experiment launcher already requires the former; the
   latter is checked by an import, not installed).
7. **Jev's completion dependency** (Codex's step 7): a Linux day cannot reach `day_complete` while `Run.jev` waits; the
   service shows the job's state and waits; it never fabricates completion.

## 5. The reachable Pod routes (item 4)

- `frankie_box_run.yml`: a step right after the path validation refuses `frankie_box_jev_pod.sh` and
  `frankie_box_clm_sidecar_pod.sh` before any step that could reach a provider; the former launch steps are gone from the
  workflow; the `always()` cleanup branch carries no provider call and no key (nothing was created, so nothing is deleted;
  a historical `clm-sidecar-pod.txt` is reported, not acted on); the controller step refuses the retired inputs even when
  empty. The two marker scripts stay in git as evidence (a dispatch of either now ends at the refusal). The secrets report
  step still names `RUNPOD_API_KEY` as set/unset; it reads no value and calls nothing.
- `controller.py`: no provider code remains in the file (no `http.client`, no create, no Pod worker, no registry); the
  retired flags are refused before parsing and any other unknown argument is refused by name. The history keeps the source.
- Inventory of direct Pod entrypoints OUTSIDE this workflow, needing their own owner (not touched, not called):
  `.github/workflows/frankie_pod_control.yml`, `frankie_pod_prepare.yml`, `frankie_refresh_bootstrap_urls.yml`,
  `frankie_retained_granite.yml`, `frankie_runpod_key_to_ssm.yml`, `frankie_serverless_reading.yml`;
  `deploy/aws/box/frankie_box_pods_config.sh`, `frankie_box_serverless_config.sh`; `deploy/runpod/mcp_connect.sh`;
  `research/kalshi/frankie_boss/clm_sidecar/launch.py` (Codex's Jev lineage); `operations/pod_control.py`,
  `pod_prepare.py`, `refresh_bootstrap_urls.py`, `serverless_reading_endpoint.py`; the `granite_runpod*.py` family and
  their tests; `pod_root/pod_bootstrap.sh` (the ROOT Pod's boot, unreachable now that nothing creates a Pod);
  `frankie_box_boss_session.py` / `frankie_box_staged_session.py` / `frankie_box_receipts.py` (the session's engine
  reach to Pods; Greg's Granite discussion); `frankie_box_venv_pins.sh`; `scripts/session_start.sh`.

## 6. Narrow requests to Codex-owned functions (not made here)

1. **Main day-bound save/resume and class-child acknowledgment** (`frankie_box_experiment.py`, Codex's): the Linux lane's
   stop is a request/acknowledgment pair in a state directory; a main-lane stop needs the same shape, day-bound (the
   handoff's gap: `Run.save_requested` is process-global, `_root_job`/`_finish_job` release on exit 75, the class worker
   does not acknowledge). Request: a day-bound `save-request.json` + acknowledgment under the run's day directory that
   retains owner, CPU set and attempt and that a later main stop route can write and read. No patch here.
2. **Coordination during a controller gap** (`frankie_box_lane_state.coordinate`, reached through `frankie_box_pod_root.py
   coordinate`; the worker's `rpc-pending.json`): the service answers requests only while alive; after a takeover the
   next poll answers. Request: confirm the worker's rpc wait tolerates a gap of `LEASE_FRESH_SECONDS` + a poll (about
   11 min) without failing the day.
3. **The worker agent's input fetch** (`pod_agent.fetch_inputs`, not CCode's): re-reading the renewed `job.json` on a 403
   would remove the signing-window limit of section 4.2 (the renewal already rewrites it with fresh URLs and the same
   identity). Request only; the retained-bytes resume covers it meanwhile.
4. **The queue's day states** (`frankie_box_pod_root.py day_state`, not CCode's): the service's `no_remaining_work` reads
   `ready`, `waiting_ingest`, `waiting_day_file`, `behind_in_root_line`, `not_in_root_line` and this worker's held claims
   as remaining; a new state word would need adding there. Request: tell CCode when one is added.

## 7. The two review passes (what was fixed, what was kept)

Pass 1 (`bdf7122b`, 17 findings), the gravest: the launcher's liveness pattern never matched the unit's argv, so stop,
resume and clear_stop misjudged a live controller; an orphan acknowledgment silenced every later stop; a plain
read-then-put lease let two controllers win; the heartbeat could overwrite the release; a day that failed to start twice
kept an open-ended service polling forever. Pass 2 (`cdeb61ce`, 10): a start that ended refused reported success; a
failure between the lock and the service left no outcome; a save relay was refused for a newer dispatch ref; a
just-resumed job read as retained. Kept as they are: the controller's own `write_json`/`read_json` (the controller must
not import the worker's module; the identity rule it would share lives in a closure there); the `always()` refusal branch
(the assignment asks for the cleanup branch's refusal explicitly) and the two retired scripts' routing entries (a
historical dispatch routes exactly as before, up to the refusal); the preflight's checkout check (the direct CLI route has
no shell in front of it). `KALSHI_TRADING.md` carries the new launcher (the documentation commit).

## 8. What remains of Step 8 (not this slice)

The main lanes' day-bound save/resume and class-child acknowledgments (Codex); the exact operating sequence for a real
launch (main's first start saving the plan, then `enable`, then the service) written into the runbook once a real E2E
has been authorized and observed; the instance-profile decision (section 4.1); the B1 Linux dependency; Jev's route.
Nothing here is runtime evidence; the first real dispatch of any of it needs Greg's explicit AWS go.
