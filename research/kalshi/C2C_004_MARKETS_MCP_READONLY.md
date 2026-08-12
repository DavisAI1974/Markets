# C2C-004 — Markets MCP read-only proof

Owner authorization: Greg approved this parallel setup task.

Purpose: prepare a read-only proof-of-concept MCP connection named `Markets Terminal` using OpenAI's Secure MCP Tunnel, without changing Frankie or the Markets repository.

Claude should work outside the Frankie redo worktree and outside the Markets repository. Use only the official OpenAI tunnel flow associated with Greg's authenticated ChatGPT/OpenAI account.

For the first proof, expose only two read-only MCP capabilities:

1. `markets_repo_status` — report the Markets repository path, current branch/HEAD, and worktree status.
2. `markets_read_file` — read UTF-8 text only from paths that resolve inside the Markets repository. Reject path traversal, binary files, and credential/secret-bearing paths.

Do not expose command execution, file writes, Git writes, AWS mutation, IAM, billing, secret retrieval, unrestricted filesystem access, or a public listener.

Do not modify Frankie code, `spawn.py`, the brain/schema, the redo worktree, or any Markets repository file. Do not invoke models or forecasts.

Perform a harmless local MCP smoke test for tool discovery, repo status, and one safe text-file read. Then follow the official OpenAI Secure MCP Tunnel setup flow. If Greg must complete browser/device authorization, stop there and report the exact owner-authentication step required. Do not bypass it.

Return by appending a short `CLAUDE -> CHATGPT | ID: C2C-004` status block to `FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` that references this task file and states: implementation/runtime used, local directory, tool names, smoke-test result, tunnel mechanism/name/status, any action Greg must take, restart instructions, and confirmation that no credentials were exposed and no Markets/Frankie files were modified.
