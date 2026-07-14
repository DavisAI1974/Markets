# SESSION HANDOFF — S93 (work date 2026-07-14) — the AWS COACH AGENT infrastructure built end-to-end (box driveable, Bedrock live); one Claude-Code model-preflight snag left; OpenAI written in as an agent-backend option

Branch: came up on the stale S70 tip, reset onto trunk `claude/kalshi-s79-kickoff-ij8t9o` (all work pushed there).

## HEADLINE
This session was almost entirely **standing up the coach agent IN AWS** (Greg's call: the agent must live in
his AWS, on the box, not in a Claude Routine). We cleared the entire access chain and the box is now fully
driveable, Bedrock inference works, and Claude Code is installed. **One snag remains before the agent's LLM
actually runs: Claude Code 2.1.197's model preflight rejects the Bedrock Opus IDs (boto3 invokes them fine).**
Per Greg, **OpenAI is now an accepted alternative agent backend** — the loop logic is provider-agnostic, so
next session picks a backend and runs the loop. **The brain did NOT advance this session** (`ng_brain.json`
still `s92.1`); no group was scored/merged. The win is the durable AWS agent home.

## WHAT'S BUILT + PROVEN (the AWS agent chain — so the next session NEVER re-fights this)
### AWS access — the `Claude` IAM user (acct 568968024170), all resolved
- Attached now: `AmazonS3FullAccess`, EC2 (limited/read), **`AmazonSSMFullAccess`**, **`AmazonBedrockFullAccess`**,
  + inline **`pass-ssm-role`** (`iam:PassRole` on `arn:aws:iam::568968024170:role/Ssm`). **No permissions boundary.**
- The long grind was: (a) Bedrock kept getting `AccessDenied` until plain `AmazonBedrockFullAccess` (not the
  `...AgentCore...`/`...DataZone...` service policies) was attached to the USER; (b) SSM needed both a user
  policy AND the box getting a role.
### Bedrock — LIVE, but region-specific (LOAD-BEARING)
- **Model access is enabled in `us-east-1`, NOT `us-east-2`.** (Model access is per-region; the console default
  was us-east-1.) From the box, `us-east-2` bedrock-runtime converse returns `ResourceNotFoundException`;
  **`us-east-1` works.** The S3 bucket/box/tape are us-east-2 — so the coach is **cross-region: Bedrock=us-east-1,
  S3=us-east-2** (fine, tested together).
- Invocable via boto3 (us.* inference profiles, region us-east-1): **opus-4-1, opus-4-5, opus-4-6, haiku-4-5** all OK.
  opus-4-7 / opus-4-8 = `AccessDenied` (their model access isn't enabled — flip on in the us-east-1 console to use).
### The box `i-08cee7171c0a76a04` (t3.xlarge, Ubuntu 22.04, us-east-2)
- **Instance profile `Ssm` attached** (SSM-only role) -> box is **Online in SSM** -> I drive it via SSM SendCommand.
  Helper: `scratchpad/ssm_run.py` (send + poll + print; gitignored). NOTE the box role has ONLY SSM; the coach
  uses the static `Claude` keys in its env for S3+Bedrock (an EC2 box wears ONE role; Greg also made separate
  `Bedrock`/`S3` roles that can't stack — cleaner later: put all three managed policies on ONE role).
- **Data pull still running (PID 2541)**: `pull_year_mbp10 --weekly` -> S3. Jul-Dec 2025 complete; crossing into
  2026 (~halfway of the 2025-07..2026-07 year). Monday stubs remain: **NG 13, CL 24** (final sweep still pending).
- Code at **`/opt/markets`**. Installed this session: **Node 20.20.2 + Claude Code 2.1.197**. python3.10 +
  boto3(1.43) + databento + pandas already present.
- **`/etc/markets/coach.env`** written (chmod 600): `CLAUDE_CODE_USE_BEDROCK=1`, `AWS_REGION=us-east-1`,
  `AWS_DEFAULT_REGION=us-east-2`, `ANTHROPIC_MODEL=us.anthropic.claude-opus-4-1-20250805-v1:0`,
  `ANTHROPIC_SMALL_FAST_MODEL=us.anthropic.claude-haiku-4-5-20251001-v1:0`, static `Claude` AWS keys + Databento key.

## THE ONE SNAG (next session's JOB 1)
`claude -p` headless FAILS: Claude Code 2.1.197's model preflight says *"There's an issue with the selected model
(us.anthropic.claude-opus-4-1-...). It may not exist or you may not have access to it,"* and warns *"Opus 4.6 not
available — using Opus 4.5."* This is a **Claude-Code-version mismatch**, NOT an access problem: raw **boto3
converse to those exact IDs SUCCEEDS in us-east-1**. Claude Code has an internal Opus-version mapping fighting the
explicit `ANTHROPIC_MODEL`, and its region handling reads `AWS_DEFAULT_REGION` (us-east-2) where the models aren't
enabled. Fixes to try next (any one likely unblocks): (i) enable **opus-4-6 model access in us-east-1** (Claude
Code's preferred version) so its default resolves; (ii) set BOTH `AWS_REGION` and `AWS_DEFAULT_REGION` to
us-east-1 for the `claude` process and force S3 clients to us-east-2 in code (the tape reader takes an explicit
region); (iii) pin `claude --model <exact-arn>`; (iv) upgrade/downgrade Claude Code to a build whose Bedrock
model registry matches the account.

## OPENAI / BACKEND OPTION (Greg S93 — written in)
The coach's LLM backend is **pluggable** — the loop is deterministic scaffolding (`forecast_harness.py`
decision-state -> blind forecast -> `overlay` score -> merge brain -> commit); only the *forecast* and *merge*
steps need an LLM, and they're provider-agnostic. Agent-brain options, pick next session:
1. **Claude Code + Bedrock** — 90% there; one config snag above. Most faithful port (full tool-use coding loop).
2. **Anthropic API direct** (an API key, no Bedrock) — sidesteps the Bedrock/Claude-Code region+version mismatch.
3. **OpenAI** via a small Python harness (`openai` SDK or the OpenAI Agents SDK) — a clean alternative brain if
   Bedrock stays finicky; the loop calls it for the forecast/merge reasoning, same decision-state in / forecast
   JSON out contract. Reproducible setup + all three options live in `deploy/aws/COACH_AGENT_SETUP_S93.md`.

## THE LOOP (unchanged, staged, ready to run once a backend invokes)
- Group-2 = 12 fresh, never-seen warm-season NG days (excl. the 12 learn + 12 group-1): **20250702, 20250707,
  20250710, 20250715, 20250725, 20250728, 20250730, 20250818, 20250820, 20250826, 20250828, 20250829**.
- `data/eia_surprise.json` rebuilt this session (free EIA, 703 NG surprises through 2026-07). Curve field stays
  `unknown` (constant contango-flat warm season = ruled noise; no Databento pull — Greg: box pulls on schedule).
- Recipe: `forecast_harness.py decision-state --days <grp2>` -> agent BLIND-forecasts from `knowledge/ng_brain.json`
  (NO tape peeking) -> `forecast_harness.py overlay` (score vs S3 tape) -> merge lessons into the brain -> commit.

## RULES (unchanged): each event individually, NEVER pool-as-final; per-cell; distributions not means; leakage
gate + blind wall; net-of-fee maker AND taker; exclude settle window; zero synthetic; provisional-until-live;
git = CODE, S3 = ALL DATA; NG and WTI kept SEPARATE; weather forecaster HANDS OFF; keys are SECRETS (ROTATE — now
also in `/etc/markets/coach.env` on the box + `scratchpad/aws.env` this session).

## SECRETS (session-pasted; ROTATE early next session — they're on the box + were pasted here):
`AWS_ACCESS_KEY_ID=AKIAYI6JDCBVLKYQGLMH`, `AWS_SECRET_ACCESS_KEY` (txRGHd...), `DATABENTO_API_KEY` (db-3ba8...),
Bedrock region `us-east-1`, S3 region `us-east-2`.

## OPEN / S94 PRIORITIES
1. **Make the agent's LLM invoke on the box (JOB 1)** — fix Claude Code+Bedrock (the four fixes above) OR switch
   to the Anthropic-API-direct or OpenAI backend. Then a headless one-shot must return before the loop.
2. **RUN THE LOOP on the box** — group-2 blind forecast -> overlay score vs S3 tape -> merge -> commit; walk the year.
3. **Deploy it durable** — `markets-coach.{service,timer}` (extend `deploy/aws/`) once a one-shot works; canary first.
4. Standing: box year finish -> `--reconcile-names` -> final Monday sweep (NG 13 / CL 24 stubs); consolidate the box
   onto ONE role (SSM+Bedrock+S3); ROTATE keys; enable opus-4-6/4-8 model access in us-east-1 if we want newer Opus.
Detail: this file + `deploy/aws/COACH_AGENT_SETUP_S93.md` + `research/kalshi/FORECASTER_RUNBOOK_S93.md` (loop manual).
