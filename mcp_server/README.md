# Markets Terminal - a read-only MCP server over this repository

Built for C2C-004 so ChatGPT can read the Markets repo directly through an OpenAI Secure MCP
Tunnel instead of having files pasted at it. **Two tools, both read-only.**

| tool | what it does |
|---|---|
| `markets_repo_status` | repo path, branch, HEAD, head subject, `git status --short` |
| `markets_read_file` | UTF-8 text read of a path INSIDE this repository |

## Security posture

Deliberately absent, and this is the design rather than an oversight: **no command execution, no
writes, no git mutation, no AWS/IAM surface, no secret retrieval, no unrestricted filesystem
access, no network listener.** Transport is stdio only - the process talks to whatever launched it
and to nothing else, so running the file exposes nothing by itself.

The read tool is the risky one, so its boundary check does not trust the string it is handed:

1. `os.path.realpath` FIRST (collapses `..`, follows symlinks), and only then compare against the
   realpath of the repo root. Comparing before resolution is the classic hole - `repo/../../etc/passwd`
   starts with the repo prefix as a string.
2. Compare on path COMPONENTS via `os.path.commonpath`, not `startswith`, so a sibling directory
   named `Markets-secrets` cannot pass by sharing a prefix.
3. A deny list runs AFTER containment, on the repo-relative path, for names that carry secrets even
   when they live inside the repo (`.env`, `credentials`, `id_rsa`, `.pem`, `secret`, ...).
4. Binary is refused by decoding UTF-8 strictly and failing closed - not by guessing at extensions.
5. A 256 KB cap so one call cannot drain a large artifact.

The credential files this project actually uses (`~/.config/markets/env`, `~/.aws/credentials`)
live OUTSIDE the repo by design (D34/D48), so containment alone already excludes them; the deny
list is the second layer for anything that later lands inside.

## Smoke test - and what "passing" has to mean

```bash
python mcp_server/smoke_test.py
```

It drives the server as a real MCP client over stdio: discovery, status, one safe read, then
**nine negative cases that must each REFUSE**. A read tool returning the right file proves nothing;
what has to be shown is that it refuses the wrong ones.

**NC-3 applies here and was violated once already.** An earlier version of this test aimed the
oversize case at a 121 KB file (under the cap, correctly allowed) and the nonexistent-path case at
a path that refused for "not a regular file" - so it printed `SMOKE_PASS` with the size-cap branch
never executed. The cases below are chosen so every branch actually fires; if you change them,
re-verify that each refusal message names the rule you intended, not a different one.

Last observed run: 9/9 refused, size cap firing on `OPEN_ITEMS.md` at 421,563 bytes.

## Running it locally (behind a tunnel)

```bash
export CONTROL_PLANE_API_KEY="$(python -c "import sys;sys.path.insert(0,'research/kalshi');import creds;print(creds.get('OPENAI_API_KEY'))")"
export CONTROL_PLANE_TUNNEL_ID="tunnel_..."
export CONTROL_PLANE_ORGANIZATION_ID="org-..."

tunnel-client doctor --profile markets-local-stdio --explain
tunnel-client run   --profile markets-local-stdio
```

`tunnel-client` is OpenAI's, from `github.com/openai/tunnel-client` (build:
`go build -o /usr/local/bin/tunnel-client ./cmd/client`). Profile creation:

```bash
tunnel-client init --sample sample_mcp_stdio_local --profile markets-local-stdio \
  --tunnel-id "$CONTROL_PLANE_TUNNEL_ID" \
  --mcp-command "/usr/local/bin/python /path/to/repo/mcp_server/markets_mcp_readonly.py"
```

### Three config values, three different failure messages

Worth writing down because each one looks like a broken key and none of them is:

| symptom | cause | fix |
|---|---|---|
| `tunnel_active_organization_required` (401/403) | no org context | set `CONTROL_PLANE_ORGANIZATION_ID` |
| `tunnel_use_forbidden` (401/403) | the key's principal cannot USE this tunnel | key must be in the tunnel's PROJECT (`sk-proj-` keys are project-scoped) and hold Tunnels **Read + Use** |
| `Missing scopes: api.model.read` on `/v1/models` | expected and correct | the key is Tunnels-only; do NOT widen it to work around an org-ID or project problem |

## Deploying so it SURVIVES (Greg, S118: "we want this to sustain")

A container-hosted daemon dies with the session and the connector goes dark. The durable home is
the EC2 box `i-08cee7171c0a76a04` - already SSM-managed and already the agent host since S93, so
this is a home the architecture already has rather than a new one.

**NOT YET EXECUTED.** Per D51, the unit below is written, not proven; nothing here may be reported
as deployed until the box has actually run it and the connector has answered a call.

```ini
# /etc/systemd/system/markets-mcp-tunnel.service
[Unit]
Description=Markets read-only MCP server behind the OpenAI secure tunnel
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=markets
WorkingDirectory=/opt/Markets
EnvironmentFile=/etc/markets/tunnel.env
ExecStart=/usr/local/bin/tunnel-client run --profile markets-box-stdio
Restart=on-failure
RestartSec=15
# bound the retry storm: an unauthorized tunnel backs off forever otherwise (the A-73 hot-loop shape)
StartLimitIntervalSec=300
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
```

`/etc/markets/tunnel.env` (chmod 600, outside the repo, per D34/D48) carries
`CONTROL_PLANE_API_KEY`, `CONTROL_PLANE_TUNNEL_ID`, `CONTROL_PLANE_ORGANIZATION_ID`.

Deploy = `git pull` on the box, install the unit, `systemctl enable --now`. The server code comes
from git and the data plane from S3, so nothing about this contradicts D34.

**Before enabling it, read A-87.** An always-on connector is an always-on token faucet: a single
`markets_read_file` can return 256 KB (~64k tokens), and an agent that can read whole files freely
will pull them repeatedly. The reducer belongs at this tool boundary, and it ships through A-65's
validated-compaction gate - not around it.
