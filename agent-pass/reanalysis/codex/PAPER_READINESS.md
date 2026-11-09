# Paper readiness — Codex independent analysis

No NG paper runner or order has been started by this analysis. The four written configurations are not deployed. Every hypothesis remains eligible for research observation; lack of demonstrated performance is not an exclusion rule.

| Candidate | Current status | Concrete next action |
| --- | --- | --- |
| P01: touch order-count imbalance | Observation-only; not ready for an execution claim | Verify NG contract/feed/simulator, fees and order lifecycle; then perform a paper-only execution check |
| P02: hit-side replenishment | Observation-only; not ready for an execution claim | Verify exact add/fill side definitions and clock windows, then the same execution checks |
| O03: price-response sequences | Observation-only recorder specification | Verify NG recording source and fixed-price/order links; record complete responses and explicit missing intervals |
| O04: duration/state context | Automated use blocked by unverified live classifier input/calibration contract | Pin original classifier, factors and causal sample availability; record forecasts without directional orders |

## Existing project capability
The inspected [paper adapter](https://github.com/DavisAI 1974/Markets/blob/43 aa 3 ec 3 a 925 d 27 d 805 eb 69320 c 8 fdd 68 fe 0 e 6 d 0/executor/exchanges/paper.py) asks cryptocurrency venues for minute closes, creates a synthetic one-basis-point spread, and uses a default 25-bps fee. This does not establish an NG futures simulator, MBO latency or credible queue fills. Its in-memory position state also does not establish durable restart reconciliation. The separate historical Kalshi forecast ledger is not proof that these NG rules are connected.

## Required launch checks
1. Pin the exact contract/security ID, session boundaries, tick size and quantity unit from the chosen NG source. Verify integer event/receive/group-known-by clocks, source sequencing, reset and snapshot behavior. Do not infer the active futures contract from the old 2023 data.
2. Pin the paper simulator route and explicit fees. Keep live-money routing disabled. Measure actual submit/ack/fill times; the configuration's 100-ms delay is only a provisional experiment.
3. Validate each trigger and suppression against saved input-to-action traces, including conflicting sides, zero denominators, stale groups, invalid quotes and duplicate messages.
4. Verify marketable-limit IOC handling, partial/unfilled orders, cancel acknowledgment, exit delay, stop slippage, loss/exposure limits, disconnect and restart reconciliation. A quoted price is not a fill.
5. Produce an immutable receipt with config hash, code/source versions and a paper-only decision/order/fill-or-miss/exit log. Only then label a candidate ready for a paper execution check or a verified running paper trial.
6. Freeze before a new session. Preserve every opportunity, including suppressed signals, misses, flats and unavailable outcomes. Compare net results only after all fill/cost fields are resolved.

## Configuration and evaluation
[PAPER_STRATEGIES.json](PAPER_STRATEGIES.json) is the matching structured specification. P01/P02 use separate virtual ledgers, one-contract maximum per ledger, no adds,4-tick stop/target,60-second cooldown,20 entries/session and 20 tick-contract daily loss limit. These are provisional risk settings, not empirical optima. P01's hold is 5 seconds; P02's is 1 second. A missing fee value or unverified route blocks orders. O03/O04 have zero positions.

Report per-day and per-condition support, adverse/favorable excursion, missed moves, suppressed cases, available and unavailable endpoints, latency, spread, fees, slippage and net results. Retain all 11 stack arms,10 precursor predicates, the original/inverse screens, SSOS and the historical hypothesis register. Candidates with incomplete operational definitions remain named research items until specified; do not fabricate a running trial.

The independent report's evidence is retrospective. No threshold, risk setting or written rule is represented as measured profitable. The reports remain separate; there is no reconciliation stage.
