# Handoff for ChatGPT: start Frankie's cycle-0 session on his box (2026-09-21)

Everything is built and verified on the box i-035994afa8bdf66a5 (us-east-1, Ubuntu, 32 vCPU). The engine is the
BOSS: the retained Granite vLLM on RunPod Pod g7y3g2w1kor4l3, reached over the durable jobs_v1 transport by
`deploy/aws/box/frankie_box_boss_session.py` (no external model, no API key). The session needs the git credential
below and the Pod RUNNING (Greg's word). Your job: get Greg through the grant below and the Pod start, then preflight,
start, watch, record. Essentials only; no tests, no gates.

Branch for every dispatch: `claude/cycle-0-frankie-box-rerun-od5sxk`. All actions are GitHub `workflow_dispatch`
on DavisAI1974/Markets (Actions tab). Never stop, resize or terminate any box or Pod. Never touch the native host
i-0e90ee6110ef609aa (its runner is holding for the response by design).

## Step 1 (Greg, AWS console or CLI, us-east-2 SSM Parameter Store): ONE SecureString

The engine is the BOSS (Greg, 2026-09-21): no API keys, no external model. The only credential the box needs is
for git. The box's instance role `Ssm` already decrypts SecureStrings in us-east-2 (verified). Create:

- `/markets/frankie/github-token` = a GitHub fine-grained personal access token, repository DavisAI1974/Markets,
  permission Contents: Read and write (nothing else). Frankie pushes `root/cycle-00-response` and
  `root/cycle-00-progress` with it.

```
aws ssm put-parameter --region us-east-2 --name /markets/frankie/github-token --type SecureString --value '<PAT>'
```

Optional, for S3 heartbeats (git heartbeats work without it): allow `s3:PutObject` on
`arn:aws:s3:::frankie-granite42-568968024170-us-east-1/host-deliveries/20211003/principal-response/cycle-00/progress/*`
for role `Ssm`.

## Step 2: preflight (proves the backend answers; starts nothing)

Workflow `Frankie box run` (frankie_box_run.yml), ref `claude/cycle-0-frankie-box-rerun-od5sxk`, inputs:
- script: `deploy/aws/box/frankie_box_session.sh`
- variables: `ACTION=preflight`
- timeout: `600`
Expected in the job summary: `verified: request 1b777cf28c34415c ...`, `labels: 29 timing labels ...`, `engine: BOSS
granite42-smoke on Pod g7y3g2w1kor4l3 healthy (jobs_v1)`, then `preflight: OK`. A `REFUSED:` line names the one thing
missing; the two that need Greg: the Pod g7y3g2w1kor4l3 must be RUNNING (it was EXITED at 09:00Z; a Pod start is
Greg's word, never the session's), and the SecureString `/markets/frankie/granite-service` (already readable by the
box role, verified). Nothing starts on preflight.

## Step 3: start the session

Same workflow, variables: `ACTION=start`, timeout `900`. The summary shows `request_sha256
1b777cf28c34415c4387119b1a42aed7dbc1f5e7b1799fdc0ed2cabd755624be`, the unit `frankie-cycle-00` active and the
heartbeat unit active. The session runs detached on the box for hours; the workflow returns in a minute.

## Step 4: watch

- Progress: `git ls-remote origin 'root/*'` shows `root/cycle-00-progress` once the first heartbeat is pushed;
  the file `research/kalshi/frankie_boss/runs/20211003/root/progress.jsonl` on that branch has one JSON line per
  heartbeat (phase, at, note). Or dispatch `Frankie host cycle status` (frankie_host_cycle_status.yml), read-only,
  which prints the last six heartbeats and flags STALE past 15 minutes.
- On the box: `Frankie box run` with script `deploy/aws/box/frankie_box_session.sh`, variables `ACTION=status`
  (phase, note, files written, log tail). Log reader: script `deploy/aws/box/frankie_box_read_log.sh`, variables
  `FILE=logs/session-00.log MODE=tail LINES=120`.
- Phases: downloaded, verified, reading, deriving, writing, pushing, done. Stale for 15 minutes with no phase
  change = look at the session log; do not restart unless Greg says so.

## Step 5: when the phase is `done`

Frankie's own pusher runs from inside the session and prints `git ls-remote origin root/cycle-00-response`. If the
branch exists, dispatch `Frankie record the principal response on the native host`
(frankie_host_record_principal_response.yml) with:
- source_ref: `root/cycle-00-response`
- response_path: `research/kalshi/frankie_boss/runs/20211003/root/response.json`
- attestation_path: `research/kalshi/frankie_boss/runs/20211003/root/host-attestation.json`
- record_path: `research/kalshi/frankie_boss/runs/20211003/root/host-session-record.json`
- cycle_index: `00`
It must end with `actual_principal_response_recorded`. Then the native host runner resumes on its own (verify,
native learning, readback, completion). Probe with `frankie_host_cycle_status.yml` only; never stop the runner.

If the pusher said the token was not readable, the four files are safe in `/opt/frankie-box/session/out/`; fix
step 1 item 1 and dispatch `Frankie box run` with script `deploy/aws/box/frankie_box_push_response.sh`.

## What the four files are (so nobody is surprised by the shapes)

The recorder workflow checks these before anything reaches the native host; the shapes are the first run's.
1. `response.json`: the response itself. `request_sha256` (digest of the request), `session_id`,
   `model_identity_as_reported_by_session`, `sections` (18 section ids to their retained sha256, copied from the
   request), `feedback` (the typed roster: request_id, input_hash, source_hash, available_ns, sessions), and
   `lessons`: a list of Markdown entries. THE LESSONS LIST IS WHERE FRANKIE'S WORK LIVES AND IT HAS NO LIMIT:
   the analysis, the per-layer calculation accounting, the ten output ledgers, and anything he finds that the
   registry does not name yet. New findings go in as more lesson entries; the shape does not change.
2. `analysis.md`: the analysis entry again as a plain file (readable without parsing JSON).
3. `host-session-record.json`: who produced the response (session id, model, host authority), the digest of the
   response, and sha256 witnesses of files 1 and 2.
4. `host-attestation.json`: the same binding fields plus a witness of file 3. This is what the host stores as the
   attestation that the record is the one the session produced.

## Where the full record is
`research/kalshi/frankie_boss/CLAUDE_HANDOFF_20260920.md` (08:00Z to 08:58Z on 09-21) and
`research/kalshi/frankie_boss/DROP_IN_CLAUDE_20260921.md` (READ FIRST). The task document Frankie reads is
`research/kalshi/frankie_boss/operations/ROOT_CYCLE_00_TASK_20260920.md`.
