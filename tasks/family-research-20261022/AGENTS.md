# NG discovery project context

Read [Reading trade charts and testing market behavior](reading-trade-charts-and-signals.md) before interpreting signals, designing replay comparisons, or drafting paper-test rules for this workstream. Use the [October discovery log](october-discovery-log.md) as the single Markdown repository for findings, counterexamples, open hypotheses, paper outcomes, and the per-date table index. Use its independent-review handoff for Codex and Claude.

- Define patterns by observable market behavior and conditions. Keep exact prices for movement measurement and contract-specific context. Preserve ratio operands and source observations.
- Use timestamps for ordering, availability, elapsed time and grouping. Keep clock buckets and weekdays separate from observed market events.
- Treat strike concentration as a separate hypothesis requiring options evidence available at the time for the matching underlying and expiry.
- Keep all four dates as discovery. Record October 2 and 17 as partial. Preserve contrary cases and distinguish historical signal decisions, scored outcomes, and prospective simulator execution.
- Investigate the order-level mechanism and what was observable before the outcome before drafting a strategy. Use the [October 18 mechanism audit](why-october18-touch-behaved-differently.md) for the first cohort and the 99-plane and 13-data-point crosswalk.
- Keep candidate availability, terminal phases, fresh flow, and rolling flow distinct. Log how and why findings arose, including alternative explanations and direct source coordinates. Use the original research notes as supporting references.
- Follow the [standing paper-phase handoff](three-date-replay-runbook.md#standing-handoff-for-the-first-paper-phase). Carry forward every hypothesis and its outcomes. The orchestrator uses the observed conditions to consider candidates. Record any evidence-based noise judgment with its scope and preserve its history.
