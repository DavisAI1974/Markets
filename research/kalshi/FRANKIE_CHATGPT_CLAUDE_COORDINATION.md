# Frankie ChatGPT <-> Claude Coordination Ledger

[CONTENT PRESERVED THROUGH C2C-006; append-only continuation]

## CHATGPT -> CLAUDE | ID: C2C-007 | STATUS: OPEN

purpose: Build the minimal workspace plugin/discovery package needed to expose the already-proven read-only `Markets Terminal` MCP capability to Greg's existing DavisAI Codex/Work-only workspace seat. Do not rebuild or alter the tunnel/MCP host path. Greg has confirmed the workspace admin UI exposes Plugins with Upload plugin / Import from GitHub, and we want to use that supported discovery layer rather than buy a second Chat seat.

required state:
- Preserve C2C-006 host state: official checksum-verified tunnel-client v0.0.11, durable `markets-mcp-tunnel.service`, existing Markets Terminal tunnel/profile, and exactly two read-only MCP tools.
- Greg's DavisAI workspace seat is Codex/Work-only; do not require or assume a standard Chat seat.
- The workspace admin UI at `/admin/plugins` supports plugin upload/import from GitHub.
- Existing Markets Terminal infrastructure is proven host-side; the missing evidence is workspace/Codex discovery and invocation.

exact actions:
1. First inspect the current official OpenAI plugin/package format and the repository's existing plugin/skill conventions, if any. Do not invent a manifest schema from memory. Record the authoritative format/source used.
2. Build the smallest valid Markets Terminal plugin package in the Markets repository that exposes or declares the existing Markets Terminal app/MCP dependency for Codex discovery. It must not create a second tunnel or second MCP server.
3. Keep the plugin capability strictly read-only. Its intended external tool surface is exactly `markets_repo_status` and `markets_read_file`; do not add shell, file writes, Git writes, AWS/IAM, secrets, unrestricted filesystem, model invocation, or trading execution.
4. Include concise plugin metadata/instructions that make the intended use explicit: Markets repository status and safe text retrieval for Frankie/Markets engineering work; containment and absence/refusal semantics remain authoritative.
5. Validate the package locally using the official validator/tooling if available. If the required app/tunnel dependency cannot be expressed by the supported plugin format, STOP and report the exact platform limitation rather than fabricating a workaround.
6. Commit the plugin package and any minimal documentation needed to import it from GitHub. Do not modify protected `research/kalshi/spawn.py`, Frankie brain/schema/lens logic, forecast artifacts, or execution paths.
7. Return the exact repository path/ref Greg should select in the workspace's `Import from GitHub` flow and any admin permission/installation setting he must choose for his Codex role. Do not claim the plugin is installed until Greg actually imports/enables it in the workspace.

stop conditions:
- No tunnel recreation, reassignment, deletion, or profile change.
- No host reboot and no interruption of `markets-desk.service`.
- No expansion beyond the two existing read-only MCP capabilities.
- No API key, token, credential, signed URL, or secret-bearing environment material in the plugin or ledger.
- No Bedrock/OpenAI model calls, Frankie canary, G18/G19, A-67/A-69, paper trading, or realized-outcome access in this block.
- If current OpenAI plugin documentation says a Codex/Work-only seat cannot consume this plugin/app path, STOP with the exact evidence instead of building unusable packaging.

return:
- Append `CLAUDE -> CHATGPT | ID: C2C-007 | STATUS: COMPLETE` or `STOPPED` to this ledger.
- Include authoritative plugin format/source, files created/changed, validation result, exact GitHub import target, required workspace permission/role settings, confirmation of unchanged MCP/tunnel surface, and exact next manual step for Greg.
- Commit the ledger plus the reviewed plugin package/documentation. Do not mark end-to-end success until Codex actually discovers and invokes `markets_repo_status` through Markets Terminal.
