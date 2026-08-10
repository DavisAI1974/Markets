# Markets Terminal Codex plugin

This is the Codex-local discovery wrapper for the existing read-only Markets MCP server.

It does not replace or modify the OpenAI Secure MCP Tunnel. The tunnel remains the ChatGPT-side path. This plugin exists because Codex can launch local stdio MCP servers directly.

## Surface

Exactly two MCP tools are intended:

- `markets_repo_status`
- `markets_read_file`

No shell, file writes, Git writes, AWS/IAM, secret retrieval, unrestricted filesystem, model invocation, or trading execution is exposed.

## Files

- `.codex-plugin/plugin.json` - plugin metadata
- `.mcp.json` - stdio MCP launch config
- `../../mcp_server/markets_mcp_readonly.py` - the proven read-only server implementation
- `../../.agents/plugins/marketplace.json` - repo/team marketplace registration

## Runtime prerequisite

The Python environment used by Codex must have the MCP Python package compatible with this server (`mcp` 2.x; the proven C2C-004 runtime used 2.0.0). The plugin intentionally does not auto-install Python packages or mutate the host environment.

## Expected working directory

The MCP config launches:

```text
python mcp_server/markets_mcp_readonly.py
```

It is therefore intentionally repo-scoped: Codex should run it with the Markets checkout as the workspace/current directory. The server itself derives the repository root from its file location and also supports `MARKETS_REPO` as an explicit override.

## Validation sequence

After Codex installs/enables the repo plugin:

1. Confirm only `markets_repo_status` and `markets_read_file` are discovered.
2. Call `markets_repo_status`.
3. Read one harmless small UTF-8 file.
4. Attempt one containment-negative read such as a traversal outside the repository and require a `REFUSED:` result.
5. Do not broaden permissions merely to make discovery easier.

The Business workspace admin GitHub importer is not the validation target for this local stdio package. If/when OpenAI supports organization-managed local stdio MCP plugins through that importer, this package can be evaluated for that route separately.
