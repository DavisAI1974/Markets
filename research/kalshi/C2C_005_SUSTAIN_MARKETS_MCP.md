# C2C-005 - Sustain Markets MCP

Status: OPEN
Owner: Claude terminal operator
Registered item: A-88
Parallel-safe: YES. This task may proceed while ChatGPT tests the current read-only Markets Terminal connection.

## Purpose

Finish A-88 so Markets Terminal survives the end of the current session/container and returns automatically without rebuilding or manually relaunching the MCP stack.

## Required state

- Preserve the existing read-only MCP security boundary and tool behavior.
- Preserve the chosen Markets Terminal identity/logo decision.
- Do not modify Frankie forecast logic, brain, schema, spawn.py, G18/G19 validation artifacts, or Bedrock model-access work as part of this task.
- The durable MCP source is the in-repository `mcp_server/` implementation; do not make `/opt/markets-mcp` the source of truth.

## Work

1. Identify the durable host/runtime that will remain available after the current interactive session/container ends. Do not claim persistence until that runtime is proven durable.
2. Run Markets Terminal from the in-repository `mcp_server/` source on that durable runtime.
3. Configure an always-on service supervisor appropriate to that host so the MCP/tunnel stack starts automatically, restarts after an unexpected process exit, and does not depend on an interactive Claude session.
4. Preserve health/readiness checks for the tunnel/MCP stack. A healthy supervisor process alone is not sufficient; the MCP child and tunnel path must be usable.
5. Keep secrets outside Git. Do not copy AWS/OpenAI credential values into repository files, service definitions, logs, or the coordination ledger.
6. Prove persistence with controlled tests:
   - stop/kill the supervised MCP/tunnel process and verify automatic recovery;
   - restart the service supervisor and verify recovery;
   - if the durable host permits a safe reboot without disrupting unrelated production workloads, reboot and verify automatic startup. If a host reboot is not safe, explicitly record it as NOT TESTED rather than simulating success.
7. After recovery, use a real MCP client to verify tool discovery, repo status, one allowed safe read, and the existing containment/refusal behavior.
8. Verify no tracked Markets files changed except files intentionally required to make the MCP runtime durable. Do not commit generated runtime state, credentials, tunnel bearer material, logs, caches, or machine-specific secret configuration.

## Acceptance gate

A-88 may be called complete only when:

- the authoritative MCP code is durable/in Git;
- the active service runs from that authoritative code or a reproducible deployment of it;
- it starts without an interactive Claude session;
- it automatically recovers from process death;
- health/readiness and a real MCP client both succeed after recovery;
- the read-only containment tests still pass;
- no secret value is committed or printed into the shared coordination record.

A tunnel that works only while the current session/container is alive does NOT pass.

## Stop conditions

Stop and report rather than infer if persistence requires any of the following:

- new broad IAM/admin privileges;
- exposing an unrestricted shell or arbitrary command tool;
- weakening the existing path/credential/size/binary containment rules;
- moving secrets into Git;
- changing the ChatGPT plugin's permission scope beyond the current read-only proof;
- modifying Frankie or trading behavior;
- rebooting a host when safety/ownership of unrelated workloads is uncertain.

## Return

When finished, append a short `CLAUDE -> CHATGPT | ID: C2C-005 | STATUS: COMPLETE|STOPPED` result to `research/kalshi/FRANKIE_CHATGPT_CLAUDE_COORDINATION.md` and commit it.

Include:

- durable host/runtime chosen (non-secret identifier only);
- service/supervisor mechanism;
- source path used by the service;
- process-death recovery result;
- supervisor-restart result;
- host-reboot result: PASS or NOT TESTED with reason;
- post-recovery MCP discovery/read/containment results;
- health/readiness result;
- final tracked-file changes;
- exact blocker if stopped.

Do not include tunnel bearer tokens, API keys, AWS keys, session tokens, signed URLs, or other credential-bearing values.
