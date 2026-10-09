# AWS Agent Toolkit - setup record (2026-10-09)

Copies of AWS's own instructions, fetched from https://github.com/aws/agent-toolkit-for-aws on 2026-10-09:

- `setup.md` - the 7-step setup runbook (CLI install, `aws login`, verify, `aws configure agent-toolkit`, rules).
- `setup-troubleshooting.md` - per-step fixes for that runbook.
- `aws-agent-rules.md` - the advanced-experience rules; the same text is appended to `CLAUDE.md` between
  the `BEGIN/END AWS Agent Toolkit rules` markers.

Upstream may change; re-fetch from the repo above when re-running the setup.

## How this repo applied it (Claude cloud sessions)

- Profiles: `greg-davis-claude` = Claude, `greg-davis` = Codex (never share one). Region us-east-1. See `KEYS.md`.
- Step 2: `scripts/session_start.sh` installs AWS CLI v2 every session if absent.
- Step 3: no browser in a cloud container, so use `aws login --remote --region us-east-1 --profile greg-davis-claude`;
  Greg opens the link and pastes the code back. Only the newest link works (each run cancels the previous one).
  The environment's network policy must allow `us-east-1.signin.aws.amazon.com` (added 2026-10-09).
  Email+password sign-in gives the account ROOT user; a non-root Identity Center user is the planned fix.
- Step 5: `aws configure agent-toolkit --yes` ran non-interactively, installed the skills and wrote a user-level
  `aws-mcp` entry in `~/.claude.json` (profile added via `AWS_MCP_PROXY_PROFILES`). The repo's own `.mcp.json`
  `aws-mcp` entry was left as is: it takes precedence in this repo and works without the CLI login.
- Skills: `scripts/session_start.sh` copies `skills/core-skills` (24) from the public repo every session; no
  sign-in needed. Not vendored in git.
- Step 7: done in `CLAUDE.md`.
- The CLI login itself does not survive a container; re-run step 3 when CLI access is needed.
