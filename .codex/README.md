# Codex repository setup

Added at Greg's request on 2026-10-06, based on branch tip fe7744e7280ddad83485c74f4b5e0f2f86eaef9c.

## What is shared

| Claude setup | Codex setup |
| --- | --- |
| CLAUDE.md and current handoffs | AGENTS.md points to the current handoff and shared context |
| .mcp.json / enabledMcpjsonServers | .codex/config.toml registers codebase-memory-mcp |
| Local executable at $HOME/.local/bin/codebase-memory-mcp | Same executable path; no second server or graph framework |

The configuration contains no credentials, permission overrides, automatic installers or compute launch hooks. Claude's existing files are unchanged.

## Use from a supported local Codex client

Open this checkout in a supported Codex client and trust the project through the client's normal mechanism. The official codebase-memory-mcp executable must already be installed at the path above on that host. Repository configuration does not install it.

Start a new Codex session from the checkout root so project instructions and MCP configuration load. In the CLI, inspect registration with `codex mcp list` and connection status with `/mcp`. Require an actual successful MCP tool call before reporting that memory is working. An index belongs to its host/checkout; verify its project and freshness before relying on it.

## Hosted chat and current limitation

GitHub connector access is working in the current ChatGPT Work session. This is separate from having a local Git checkout or local MCP connection.

Hosted ChatGPT Work does not attach local stdio tools by reading a repository .codex/config.toml. It uses its available plugin/connector tools. This setup prepares supported local Codex clients; it does not establish a working Memory MCP connection in this hosted chat.

A fresh stdio MCP initialize attempt using the retained official v0.11.0 binary exited 1 with no protocol response:

> codebase-memory-mcp: exact executable identity could not be verified (process-fingerprint)

No codebase-memory-mcp tool is exposed in this session. Memory MCP remains blocked. The current handoff records the prior PID/proc-view investigation. Do not remove security checks, spoof process identity, downgrade, or repeatedly reinstall to disguise this failure. A compatible host and supported client are needed; no local repair is established here.

Claude's scripts/session_start.sh is not registered as a Codex hook: it installs dependencies, materializes old datasets, restores AWS substrate and installs RunPod skills. That does not match the current source-only, AWS-CPU-only continuation. Read the current handoff rather than running that legacy bootstrap.

Verification for this setup: compare the configured launcher with the existing .mcp.json, parse TOML, review the three-file change, and read back the committed files. No Frankie tests, model calls, data runs, AWS actions or E2E are part of this setup.

Official references:
- https://learn.chatgpt.com/docs/extend/mcp?surface=cli
- https://learn.chatgpt.com/docs/agent-configuration/agents-md
