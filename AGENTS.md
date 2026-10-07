# Codex entry point — DavisAI Markets

## Start here

- Apply using-agent-skills, then context-engineering when available. Locate missing named skills before proceeding.
- Read research/kalshi/frankie_boss/CODEX_HANDOFF_20261007_WORKFLOW_CONTINUATION.md first. It records the remaining agent work across the entire workflow and the agreed E2E, one-day inspection, then three-day sequence. CODEX_HANDOFF_20261006_NIGHT.md and earlier handoffs remain background.
- Consult CLAUDE.md for shared project context; its older session notes and startup hooks do not supersede the current handoff or Greg's current instructions.
- Verify the actual branch tip and preserve newer work. Current integration branch: ccr-5fce7de3-xa4hfg. CCode returns on ccode/teacher-tasks-20261006b. Do not reset to the handoff checkpoint.
- Inspect existing implementations, inventories and contracts before building. Coordinate disjoint ownership with other agents; CCode owns the Step #4 scientific/candidate files and separate smaller-model facilitator work.

## Current execution boundaries

- AWS CPU only; no Pods. Exactly three held 16-CPU lanes: two main and one Linux, each with 15 workers plus coordinator. Keep giant evidence on its owning lane.
- No starts, AWS installations, compute dispatch, training, data/scientific runs or model calls without Greg's explicit authorization.
- No extra tests or validator framework. One real E2E only after wiring/discussions and explicit AWS go; thirty days require separate authorization.
- Greg settled workflow #5 on 2026-10-06 at 21:53 ET: market-only checking/correction through affected calculations, findings and lessons, with checked corrections reaching Frankie before dependent work. Read the opening section of SPEC-experiment-orchestrator.md. Never keep known errors active merely because records were frozen; no trading-cost/profit criterion or knowledge freeze. Implementation remains incomplete; other mathematical decisions remain open. Its old draft stays unapplied; never apply 9c19cc2. Jev CPU remains discussion pending. Do not activate disabled producers silently.
- Push with [skip ci]. Distinguish source-built from runtime-verified; Steps #2/#3 remain open and no real E2E is established by this setup.

## Evidence and successor work

- Greg's latest market-research rule (2026-10-06): market signals come from underlying market conditions. IDs, dates and days of week can be search conditions/cells that group those signals for forecasting; they are not numerical signals or targets themselves. Keep dates/weekdays associated with the original data. Predictions must be attributed to the underlying conditions, not to their date/day/ID labels. Exclude trade costs, commissions, fee/slippage assumptions, P&L objectives and non-market bookkeeping from signal calculations. Preserve actual market prices/spreads, flow, depth, FIFO rank/age, elapsed market durations and geometry. Keep identity/missingness bindings without treating their codes as measurements. Historical cost-tuned results must be identified and reworked, not merely stripped of final fee columns or silently admitted as cost-free evidence.
- Preserve Frankie's applicable inputs, calculations, planes, adapters and replay, plus the BOSS's original targets, masks, controls, representation and training role. Greg retired Memory A; H06–H08 remain historical/not_bound as the current handoff specifies.
- Every applicable retained record/field and knowledge source must reach actual computation. Receipts, lists and storage alone are insufficient. Exclude private trade-decision logic from teacher evidence.
- No silent dropping, arbitrary truncation, output pooling or averaging across runs. Preserve raw causal availability and answer walls; do not impose a market-date gate on completed knowledge.
- Reuse existing owner-local shared calculations and the normal checkpoint updater.
- Locate retained state before proposing replacement. Preserve immutable forecast/request/input/source/session identities and pending evidence. Do not invent outcome labels, initialize replacement weights, bypass pending feedback, or equate classroom code with native training.

## Memory MCP

.codex/config.toml registers the same local codebase-memory-mcp executable as Claude's .mcp.json. See .codex/README.md for client requirements and the observed host blocker.

Use a successful MCP call to establish availability; configuration or --version alone is not proof. Check index freshness against the actual checkout. If unavailable, report the failure and use direct source inspection. Never bypass executable/process identity checks.
