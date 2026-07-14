# COACH AGENT — AWS box setup (S93)

How the coach agent is wired to run IN AWS on the durable box `i-08cee7171c0a76a04` (us-east-2), plus the
three interchangeable LLM backends (Bedrock / Anthropic-API / OpenAI). This is the reproducible record of
what S93 built on the box; read `SESSION_HANDOFF_2026-07-14_S93.md` for the state and the open snag.

## The shape
The coach loop is deterministic scaffolding (`research/kalshi/forecast_harness.py` + `coach_replay.py` +
`month_characterize.py`); only the **blind-forecast** and **merge** steps need an LLM. That LLM is a
**pluggable backend** — everything else (S3 tape, git, python, the brain) is identical regardless of backend.

## Access prerequisites (done S93 — see handoff for the grind)
- IAM user `Claude` (acct 568968024170): `AmazonS3FullAccess`, EC2 read, `AmazonSSMFullAccess`,
  `AmazonBedrockFullAccess`, inline `pass-ssm-role` (`iam:PassRole` on role `Ssm`). No permissions boundary.
- Box has instance profile **`Ssm`** attached -> Online in SSM -> drive it via `scratchpad/ssm_run.py`.
- **Bedrock model access is enabled in `us-east-1` only** (per-region). S3/tape are `us-east-2`. Cross-region.

## Box provisioning (done S93)
```bash
# via SSM (scratchpad/ssm_run.py '<cmd>'):
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && apt-get install -y nodejs   # Node 20
npm install -g @anthropic-ai/claude-code                                                  # Claude Code 2.1.197
# /etc/markets/coach.env (chmod 600):
#   CLAUDE_CODE_USE_BEDROCK=1
#   AWS_REGION=us-east-1              # Bedrock region (models live here)
#   AWS_DEFAULT_REGION=us-east-2      # S3/tape region
#   ANTHROPIC_MODEL=us.anthropic.claude-opus-4-1-20250805-v1:0
#   ANTHROPIC_SMALL_FAST_MODEL=us.anthropic.claude-haiku-4-5-20251001-v1:0
#   AWS_ACCESS_KEY_ID=... AWS_SECRET_ACCESS_KEY=... DATABENTO_API_KEY=db-...
```
Python (3.10 + boto3 + databento + pandas) and the `/opt/markets` checkout were already on the box.

## Backend option A — Claude Code + Bedrock (started; one snag)
`set -a; . /etc/markets/coach.env; set +a; claude -p "<prompt>" --output-format text`.
**Snag (open):** Claude Code 2.1.197 preflight rejects the Bedrock Opus IDs ("issue with the selected model")
and reads `AWS_DEFAULT_REGION` (us-east-2, no models) not `AWS_REGION`. Raw boto3 converse to the same IDs
works in us-east-1. Fixes to try: enable opus-4-6 model access in us-east-1; force both region vars to
us-east-1 for the `claude` process (and pin S3 clients to us-east-2 in code); `claude --model <arn>`; or a
different Claude Code build. Verify with a one-shot: `claude -p "Reply with: COACH-ONLINE"`.

## Backend option B — Anthropic API direct
Drop `CLAUDE_CODE_USE_BEDROCK`; set `ANTHROPIC_API_KEY=...` in coach.env; Claude Code then calls the Anthropic
API directly (no Bedrock region/version mismatch). Simplest way to get Claude Code working if Bedrock stays fussy.

## Backend option C — OpenAI (Greg S93)
The forecast/merge steps can be driven by an OpenAI model via a small Python harness instead of Claude Code:
- `pip install openai`; `OPENAI_API_KEY=...` in coach.env.
- A thin `coach_backend.py` (to write) exposes `forecast(decision_state, brain) -> forecasts_json` and
  `merge(overlay_scores, brain) -> brain'`, implemented against `openai` (Responses/Chat) or the OpenAI Agents
  SDK. Same contract as the Claude path — decision-state in, forecast JSON out; NO tape peeking in forecast.
- Trade-off: loses Claude Code's built-in tool-use loop (git/bash/file-edit), so the harness wires those
  itself; gain is total independence from Bedrock. Good fallback / A-B option.

## Loop entrypoint (to deploy once a backend invokes)
`markets-coach.{service,timer}` in `deploy/aws/` (timer DISABLED until a one-shot works; canary one group first):
each fire = `git pull` trunk -> pick next un-done NG group -> decision-state -> blind forecast (chosen backend)
-> `overlay` score vs S3 tape -> merge into `knowledge/ng_brain.json` -> commit+push -> notify. Guard: commits
provisional, pings the overlay, true-holdout days reserved (see `FORECASTER_RUNBOOK_S93.md`).
