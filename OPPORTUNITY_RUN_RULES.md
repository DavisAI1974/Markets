# Opportunity Evidence Run Rules

These rules are locked for the opportunity evidence study. Do not change them for new runs unless the user explicitly approves the change first.

## Canonical 6-Hour Block

Every 6-hour block uses the same structure as the first two blocks:

- Loose evidence sweep: 15 minute stride.
- Dense evidence sweep: 5 minute stride.
- Duration: exactly 6 replay hours per block.
- Families launched in the same sweep:
  - `MEAN_REVERSION_CHOP`
  - `NEWS_BREAKOUT`
  - `LIQUIDITY_SQUEEZE`
  - `VOL_BREAKOUT`
  - `BASIS_DISLOCATION`
  - `RELATIVE_STRENGTH`
- Evidence probes use the loose gates already used for the first two 6-hour blocks:
  - `--all-families-until-hit`
  - `--passes-per-family 1`
  - `--min-context-family-samples 1`
  - `--winner-pnl-r-floor 0`
  - `--winner-min-trades 1`
  - `--no-enforce-bucket-health`
  - `--no-enforce-daily-limits`
- Later 6-hour blocks may re-sample a context that already has a promoted winner because the new timestamp is a new opportunity. Do not rerun an already-completed output root unless explicitly forced.

## Resolver Source

`EXACT_CONTEXT_RESOLVER` is not a replay family. It is a supplemental positive-entry resolver source loaded from `research/strategy_evolution/_routing.json`.

The opportunity list must include resolver positives beside replay positives. Current list policy:

- Replay positive evidence rows become `tradable_opportunities`.
- Exact-context resolver positives become `tradable_opportunities` with source `exact_context_resolver`.
- Nonpositive replay evidence becomes negative rule/mutation memory, not an opportunity list.
- `unresolved_opportunities` must remain zero after mutation resolution.

## Artifact Contract

The first two 6-hour blocks are the baseline artifact shape:

- `strategy_evolution_workflow_runs_loose_h0`
- `strategy_evolution_workflow_runs_loose_h6`
- `strategy_evolution_workflow_runs_loose5_h0`
- `strategy_evolution_workflow_runs_loose5_h6`

Their ledger/list structure is the template for every later 6-hour block.

Do not substitute routed replay counts for evidence-sweep counts. Routed replay can be useful later, but it is not comparable to this opportunity evidence ledger unless the user explicitly changes the study rules.
