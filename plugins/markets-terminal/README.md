# Markets Terminal

Markets Terminal is the read-only MCP access path for the DavisAI Markets development environment.

## Proven ChatGPT Business path (2026-08-12)

The working ChatGPT path is a **custom App backed by the existing OpenAI Secure MCP Tunnel**. The repo-local Codex plugin is a separate local-stdio path; it is not what gives ChatGPT cloud access to the Markets host.

Working topology:

```text
ChatGPT Business
  -> Markets Terminal custom App
  -> OpenAI Secure MCP Tunnel
  -> /opt/markets-terminal on the Markets host
  -> mcp_server/markets_mcp_readonly.py
```

The live proof returned `/opt/markets-terminal`, branch `chatgpt/agent-frankie-s117`, the deployed HEAD, a clean worktree, and read-only access through `markets_repo_status`.

## ChatGPT setup sequence

1. In the Business workspace, enable Developer mode under Admin -> Apps.
2. Create a custom App.
3. Name/describe it as the Markets read-only integration.
4. Choose **Tunnel**, not Server URL.
5. Select the existing Markets Terminal Secure MCP Tunnel. Do not create a replacement tunnel merely to publish the App.
6. Use **No Auth** for this tunnel-backed private MCP server.
7. Review the custom-MCP risk notices and the actual action parameters before publishing.
8. Before publication, inspect **Actions** and require exactly two actions:
   - `markets_repo_status`
   - `markets_read_file`
9. Both actions must be classified **READ**. If ChatGPT shows WRITE, DESTRUCTIVE, or OPEN WORLD, do not publish that action snapshot. The MCP server must advertise `ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)`, the host service must be restarted, and on ChatGPT Business the App may need to be recreated so discovery occurs against the corrected live metadata.
10. Publish/enable the App, then connect it from the user-facing Plugins/App directory before expecting tools in chat.
11. Use **Try in chat** and call `markets_repo_status` as the positive proof.

Observed negative-path behavior: a `../outside.txt` traversal request was blocked by OpenAI safety checks before the MCP server received it. This is an additional upstream safety layer; server-side containment remains implemented and tested independently.

## Read-only surface

Exactly two MCP tools are intended:

- `markets_repo_status`
- `markets_read_file`

No shell, file writes, Git writes, AWS/IAM, secret retrieval, unrestricted filesystem, model invocation, or trading execution is exposed.

`markets_read_file` resolves symlinks/`..` before component-wise repo containment, rejects credential/secret-bearing paths, refuses binary/non-UTF-8 content, and caps reads at 256 KiB.

## Host/runtime

The durable host checkout used by the tunnel is `/opt/markets-terminal`. The tunnel service is `markets-mcp-tunnel.service`. Updating MCP tool metadata requires the host checkout to receive the new server commit and the service to restart before ChatGPT can rediscover the new action definitions.

Do not delete/recreate the working Secure MCP Tunnel during ordinary plugin/App maintenance.

## Codex-local package

The repository also retains a Codex-local discovery wrapper:

- `.codex-plugin/plugin.json` - plugin metadata
- `.mcp.json` - local stdio MCP launch config
- `../../mcp_server/markets_mcp_readonly.py` - shared read-only server implementation
- `../../.agents/plugins/marketplace.json` - repo/team marketplace registration

Codex-local launch is intentionally repo-scoped:

```text
python mcp_server/markets_mcp_readonly.py
```

The Python environment must have a compatible MCP Python package (`mcp` 2.x; the proven runtime used 2.0.0).

## Validation contract

A valid deployment must preserve all of the following:

- exactly two tools;
- both tools classified READ by ChatGPT;
- successful live `markets_repo_status` through the tunnel-backed App;
- no write, shell, Git mutation, AWS/IAM, secret, model, or trading authority;
- server-side path containment and secret denial remain intact;
- `research/kalshi/spawn.py` and Frankie forecast architecture are unrelated to this transport and must not be modified merely to maintain Markets Terminal.
