#!/usr/bin/env bash
# Connect this Claude Code session to the hosted RunPod MCP with the API key as a Bearer header, and install runpodctl
# with the same key (the RunPod router skill's rule: one key unlocks the MCP and the CLI; OAuth is the last resort and
# the web/mobile Claude Code UI has no /mcp sign-in menu). Greg's permission 2026-09-21 12:4xZ. The key comes ONLY from
# the environment (Claude Code environment configuration -> RUNPOD_API_KEY); it is never printed, never written to the
# repo. The MCP connection lands in the container's user-scope config (outside the repo); the tools load on the next
# session start (or after a reconnect). Prints pass/fail and the key's length only.
set -u
if [ -z "${RUNPOD_API_KEY:-}" ]; then
  echo "RUNPOD_API_KEY absent: add it to the Claude Code environment configuration (never paste it into chat); nothing done"; exit 2
fi
case "$RUNPOD_API_KEY" in proxy-injected*|*placeholder*) echo "RUNPOD_API_KEY is a container placeholder, not a key; nothing done"; exit 2;; esac
echo "RUNPOD_API_KEY present (length ${#RUNPOD_API_KEY})"
# 1. the hosted MCP, Bearer auth, user scope (replaces a stale entry of the same name)
claude mcp remove runpod -s user >/dev/null 2>&1 || true
claude mcp add --transport http runpod -s user https://mcp.getrunpod.io/ --header "Authorization: Bearer $RUNPOD_API_KEY" >/dev/null \
  && echo "mcp: runpod registered (user scope, Bearer)" || { echo "mcp: claude mcp add failed"; exit 3; }
claude mcp list 2>&1 | grep -i '^runpod\|plugin:runpod' | sed 's/Bearer [A-Za-z0-9_-]*/Bearer ***/'
# 2. the server's version from the initialize handshake (proves the key is accepted; prints no key)
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"markets-probe","version":"0"}}}' \
 | curl -sS -m 30 -X POST https://mcp.getrunpod.io/ -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" \
     -H "Authorization: Bearer $RUNPOD_API_KEY" -d @- | tr -d '\r' | grep -o '"serverInfo":{[^}]*}' | head -1 || echo "handshake: no serverInfo (key rejected or network)"
# 3. runpodctl with the same key (the installer may be blocked by the proxy; then the skills' flags still apply)
if ! command -v runpodctl >/dev/null 2>&1; then curl -sSL -m 120 https://cli.runpod.net | bash >/tmp/runpodctl-install.log 2>&1 || echo "runpodctl install failed (see /tmp/runpodctl-install.log)"; fi
command -v runpodctl >/dev/null 2>&1 && { runpodctl version 2>/dev/null | head -1; runpodctl user >/dev/null 2>&1 && echo "runpodctl: key accepted" || echo "runpodctl: user lookup failed"; }
echo "next: the runpod MCP tools appear after the session reconnects; verify with list-endpoints"
