# Codex entry point — DavisAI Markets

## Start here

- Apply using-agent-skills, then context-engineering when available. Locate missing named skills before proceeding.
- Read research/kalshi/frankie_boss/HANDOFF_20261006_SUCCESSOR_AND_FULL_EVIDENCE.md first, including its newest addenda, and follow its reading order. It is the current continuation pointer for this branch.
- Consult CLAUDE.md for shared project context; its older session notes and startup hooks do not supersede the current handoff or Greg's current instructions.
- Verify the actual branch tip and preserve newer work. Current work branch: chatgpt/frankie-30day-aws-workflow-20261006. Do not reset to the handoff checkpoint.
- Inspect existing implementations, inventories and contracts before building. Coordinate disjoint ownership with other agents; CCode owns the Step #4 scientific/candidate files and separate smaller-model facilitator work.

## Current execution boundaries

- AWS CPU only; no Pods. Exactly three held 16-CPU lanes: two main and one Linux, each with 15 workers plus coordinator. Keep giant evidence on its owning lane.
- No starts, AWS installations, compute dispatch, training, data/scientific runs or model calls without Greg's explicit authorization.
- No extra tests or validator framework. One real E2E only after wiring/discussions and explicit AWS go; thirty days require separate authorization.
- Workflow #5 freeze/evaluation remains discussion-gated; its draft stays unapplied. Jev CPU remains discussion pending. Do not activate disabled producers silently.
- Push with [skip ci]. Distinguish source-built from runtime-verified; Steps #2/#3 remain open and no real E2E is established by this setup.

## Evidence and successor work

- Preserve Frankie's inputs, calculations, planes, adapters, replay and Memory A, plus the BOSS's original targets, masks, controls, representation and training role.
- Every applicable retained record/field and knowledge source must reach actual computation. Receipts, lists and storage alone are insufficient. Exclude private trade-decision logic from teacher evidence.
- No silent dropping, arbitrary truncation, output pooling or averaging across runs. Preserve raw causal availability and answer walls; do not impose a market-date gate on completed knowledge.
- Reuse existing owner-local shared calculations and the normal checkpoint updater.
- Locate retained state before proposing replacement. Preserve immutable forecast/request/input/source/session identities and pending evidence. Do not invent outcome labels, initialize replacement weights, bypass pending feedback, or equate classroom code with native training.

## Memory MCP

.codex/config.toml registers the same local codebase-memory-mcp executable as Claude's .mcp.json. See .codex/README.md for client requirements and the observed host blocker.

Use a successful MCP call to establish availability; configuration or --version alone is not proof. Check index freshness against the actual checkout. If unavailable, report the failure and use direct source inspection. Never bypass executable/process identity checks.
