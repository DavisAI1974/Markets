# Frankie/BOSS key registry (names, locations, readers; NEVER values)

Greg, 2026-09-21 (chat 6): "You guys need to put the keys in a doc or file." This is that file. It records, for every
key the Frankie/BOSS run uses, its NAME, WHERE it lives, WHO reads it and HOW to use each route, so a fresh chat never
has to ask again. It holds NO values: the repository is PUBLIC, so a value written here would be published and revoked
within minutes. Greg's word (2026-09-21): the RunPod key may be used for anything; it has all permissions.

Every line below is a measurement with its run id or handoff timestamp; update it when a location changes.

## The one-time step that puts the keys in EVERY chat container

The Claude Code ENVIRONMENT CONFIGURATION (the claude.ai environment settings page, Greg's to edit) is the only
persistent store a chat container reads at start. Set these variables once and every future session has them, with
nothing passing through chat:

| Variable | Read by | Status (chat 6, 15:5xZ 09-21) |
|---|---|---|
| `RUNPOD_API_KEY` | `deploy/runpod/mcp_connect.sh` (MCP registration + runpodctl), the RunPod skills, `serverless_reading_endpoint.py` | NOT SET (mcp_connect.sh: "absent ... nothing done") |
| `MARKETS_AWS_ACCESS_KEY_ID` + `MARKETS_AWS_SECRET_ACCESS_KEY` | `scripts/session_start.sh` lines 68-88 (installs them at the D48 locations, gives the container an AWS identity: SSM reads, S3, EC2 describe) | NOT SET (container AWS vars are the proxy placeholders; STS InvalidClientTokenId, chat 5) |

Until those are set, the chat container has NO key of its own and reaches everything through the routes below.

## RunPod API key (`rpa_`, length 50)

| Location | Region / scope | Readers | Measured |
|---|---|---|---|
| Repository secret `RUNPOD_API_KEY` | DavisAI1974/Markets | Trunk-registered workflows on the runner: `frankie_pod_control.yml` (inspect / start / terminate-EXITED-replacement-only), `frankie_pod_prepare.yml`, `frankie_refresh_bootstrap_urls.yml`, `frankie_retained_granite.yml`, `frankie_runpod_key_to_ssm.yml`; `frankie_serverless_reading.yml` once registered on the trunk | set = true, runs 35621233900 (15:47Z) and 35621992986 (15:53Z), names-only report |
| SSM SecureString `/markets/frankie/runpod-serverless` | us-east-2 | The box i-035994afa8bdf66a5 (instance profile `Ssm`): `frankie_box_boss_session.py` serverless lane, `frankie_box_serverless_config.sh ACTION=key` | version 1, length 50, prefix rpa_, run 35617264569 (15:4xZ 09-21) |
| SSM SecureString `/markets/frankie/granite-service` | us-east-2 | The native host (`pod_credential_ssm`) and the box preflight (the Pod record; jobs_v1 to the retained Pod) | read "not printed" by every preflight (restart 4, run 35617931290) |
| Claude Code environment configuration `RUNPOD_API_KEY` | chat containers | `mcp_connect.sh`, RunPod skills, runpodctl | NOT SET |
| Session-only file `~/.config/markets/runpod.env` (chmod 600) | one chat container | chat 5 only (Greg pasted the key at 15:0xZ 09-21) | GONE with that container |

How to use it from a chat without the value: dispatch a trunk-registered workflow above with `ref` = the working
branch (the workflow FILE resolves on the default branch `claude/kalshi-s79-kickoff-ij8t9o`; the checkout inside it
takes the dispatched ref). Box-side RunPod actions run through `frankie_box_run.yml` + a committed
`deploy/aws/box/*.sh` script; the box reads the SSM parameter itself and prints only health, never the key.

## GitHub token (the box's push identity)

| Location | Region / scope | Readers | Measured |
|---|---|---|---|
| SSM SecureString `/markets/frankie/github-token` | us-east-2 | The box: `frankie_box_heartbeat.py` (pushes `root/cycle-NN-progress`), `frankie_box_push_response.sh` (pushes `root/cycle-NN-response`), `frankie_box_session.sh ACTION=verify` ("readable (not printed)") | version 2 = FINE-GRAINED PAT, Markets only, Contents read/write, length 93, prefix github_pat_ (16:2xZ 09-21); version 1 = the classic PAT (superseded, still valid on GitHub, referenced nowhere) |
| Repository secret `FRANKIE_GITHUB_TOKEN` | DavisAI1974/Markets | `frankie_box_run.yml` input `github_token_to_ssm=true` (copies the secret into the SSM parameter above; the phone route for a future value) | NOT SET (runs 35621233900, 35621992986) |
| Session-only file `~/.config/markets/github.env` | one chat container | chat 5 only | GONE |

Proof the chain works: heartbeat pushes `root/cycle-00-progress` since 15:35:54Z (4a204478; tip 6e7f2a12 at 15:51Z).
Expiry: the key question as a whole is Greg's (deferred at 16:3xZ 09-21); GitHub's expiration header reading is
recorded in `CLAUDE_HANDOFF_20260920.md` 16:2xZ as an observation only.

## AWS access-key pair (IAM user `Claude`, account ...4170, key id AKIAYI6JDCBVLKYQGLMH)

| Location | Readers | Measured |
|---|---|---|
| Repository secrets `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY` (`AWS_SESSION_TOKEN` empty) | Every `frankie_*` workflow on the runner (SSM send-command to the box, S3 presigning, SSM put-parameter) | AWS pair set = true (runs 35621233900, 35621992986) |
| Claude Code environment configuration `MARKETS_AWS_ACCESS_KEY_ID` / `MARKETS_AWS_SECRET_ACCESS_KEY` | `scripts/session_start.sh` -> `~/.config/markets/env` + `~/.aws/credentials` (the D48 locations) | NOT SET |
| Session-only files at the D48 locations | chat 5 only (Greg pasted the pair as a photo, 16:0xZ 09-21) | GONE |
| Box role (instance profile `Ssm` on i-035994afa8bdf66a5) | Not this pair: the box's own role reads the SSM parameters; it reads nothing in S3 (`frankie_box_run.yml` presigns for it) | SSM Online, every box run |

Rights: the `Claude` user carries S3 + EC2 + SSM-full + Bedrock-full + inline PassRole, no permissions boundary
(S93). The key id is recorded on purpose (S100 note); the secret never is.

## Other keys named by the workflows

| Name | Location | Status |
|---|---|---|
| `DATABENTO_API_KEY` | repository secret | NOT SET at repository level (runs 35621233900, 35621992986); the historical pull workflow holds it elsewhere or not at all, not Frankie's question |
| HF token | none: the pinned Granite checkpoint is public and host-cached by model reference; `serverless_reading_endpoint.py --hf-token-env` exists but the workflow never passes it | unused |

## Rules that govern this file

- Names, locations, versions, lengths, prefixes and run ids only. Never a value, never a full key id for a secret
  key, never a presigned URL.
- A key pasted into chat is a session-only convenience: written to a chmod-600 file outside the repo, never echoed,
  gone with the container. Record the paste here as a location with "GONE" once the chat closes.
- Rotation and expiry are Greg's calls; record his word with its timestamp, never act on an inference.
