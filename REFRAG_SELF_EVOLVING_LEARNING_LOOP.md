# Refrag Self-Evolving Learning Loop

Date: 2026-05-16

## Intent

Refrag is the strategy memory and invention layer. In practice, learning, autoresearch, and live-paper modes, active families should trade when a directional side exists so the loop can collect evidence, write structured JSON, and evolve the next family or variant.

## Current Safety Default

Risky self-evolving trades are live-paper or practice only. Product/live-money exposure remains gated by daily health, bucket health, disabled-strategy checks, and normal blockers.

This policy is intentionally documented here because it may change later. If live-money learning is ever allowed, update this file and the strategy-mode gates together.

## Loop Contract

1. A family attempts a trade, including forced exploration when normal gates do not match.
2. The trade records the family, variant id, forced flag, risk tags, queue action, and handoff hint.
3. Refrag writes `strategy_attempt_v1` JSON from the observed trade and result.
4. Refrag queues the next experiment:
   - failed attempt: hand off to the next candidate family,
   - winning attempt: refine the same family,
   - incomplete/no-trade run: force an active family on the next learning pass.
5. JSON variants are created immediately. Repeated winners can later be promoted into Python strategy classes with tests.

## Execution And Migration Rule

Signal-score tiers are not the learning gate. Practice/live-paper learning uses one broad `route_evidence` scenario so every directional signal can become evidence.

The default practice replay bank starts at `$10,000`, and `route_evidence` uses `100%` bank/equity notional for each possible learning trade. At the starting bank, that is about `$10,000` hypothetical notional per signal.

Learning evidence is not exposure-throttled. Open positions do not suppress logging another possible trade, even on the same asset. The bank affects PnL sizing, not whether the evidence is recorded. Records must separate the hypothetical learning trade from real execution fields:

- `notional` and `hypothetical_notional`: full-bank learning size used for PnL evidence.
- `actual_execution`: whether anything was actually bought or sold.
- `actual_notional`: real executed notional, `0.0` for pure paper/evidence records.
- `actual_side`: the side that would be or was executed.
- `learning_capital_model`: capital policy used to interpret the record.

The promotion threshold is realized positive PnL for an exact context:

- Exact context means family + asset + venue + side + session.
- Positive-PnL exact contexts can be called again for that exact instance.
- Non-positive exact contexts become `avoid_context` once sampled, so that family is not called again there unless a mutation creates a new variant.
- If no family has produced positive PnL for an exact context, that context is not traded on after the unseen-family probes are exhausted.
- Role labels like specialist, hybrid, or generalist are only job titles for reporting; they are never callable strategy ids.
- Zero-trade slices are still evidence. If no family can execute, write `no_trade` attempt JSON and generate a candidate variant for the next time a similar context appears.

## New Live Contexts

When live-paper sees something new, use the same rule as historical learning: send the active family set at it with learning sizing, record every trade attempt or no-trade attempt, and let the JSON decide the next call. If a family-context pair is positive PnL, it can be called again for that exact context. If nothing shakes out positive, the context is not traded on, but its no-trade/failed-attempt JSON remains available so Refrag can create a better-fitting variant next time.

For historical catch-up, use one full family sweep per 6-hour slice unless a real bug is found in the current slice. Do not restart at the first slice until the full historical data has been processed.

## Shared Artifacts

- `research/strategy_evolution/_queue.json`
- `research/strategy_evolution/_candidate_experiments.json`
- `research/strategy_evolution/_attempts.jsonl`
- `research/strategy_evolution/_variants.json`
- `research/strategy_evolution/_routing.json`

## Usage-Triggered Evolution

Evolution is triggered every time the system attempts to use a strategy, not by a timer. A trade attempt immediately writes:

- an attempt row in `_attempts.jsonl`,
- an interpreted variant in `_variants.json`,
- a candidate experiment in `_candidate_experiments.json`,
- and a queue update in `_queue.json`.

Replay workflows can still be used as laboratory tools to replay a 6-hour window, but they are not the production evolution loop. The production loop is usage-triggered: observe the attempted trade, write JSON, consult JSON on the next decision, and promote only positive-PnL exact contexts.

## Non-Negotiable Guardrail

`PRESSURE_CONTINUATION` stays out of the active strategy universe. It may remain only as an internal disabled/kill-switch constant for rejecting old records.
