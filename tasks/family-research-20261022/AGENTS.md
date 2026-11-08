# NG discovery project context

Read [Reading trade charts and testing market behavior](reading-trade-charts-and-signals.md) before interpreting signals, designing replay comparisons, or drafting paper-test rules for this workstream. Use the [October discovery log](october-discovery-log.md) for actual cases and current status.

- Define patterns by observable market behavior and conditions. Keep exact prices for movement measurement and contract-specific context. Preserve ratio operands and source observations.
- Use timestamps for ordering, availability, elapsed time and grouping. Keep clock buckets and weekdays separate from observed market events.
- Treat strike concentration as a separate hypothesis requiring options evidence available at the time for the matching underlying and expiry.
- Keep all four dates as discovery. Record October 2 and 17 as partial. Preserve contrary cases and distinguish historical signal decisions, scored outcomes, and prospective simulator execution.
- Investigate the order-level mechanism and what was observable before the outcome before drafting a strategy. Use the [October 18 mechanism audit](why-october18-touch-behaved-differently.md) for the first cohort and the 99-plane and 13-data-point crosswalk.
