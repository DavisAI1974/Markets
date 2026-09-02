# Forecaster Frankie — First Native-Replay Output Review

## Assignment

Apply this directive independently to both arms:

- A-clean Forecaster reviews only A-clean first native-replay outputs.
- A-memory Forecaster reviews only A-memory first native-replay outputs and its
  authorized prior lessons/insights/notes package.

Never cross-feed arm outputs. Keep Step-1 and the answer/reveal wall sealed.

Load retained knowledge only through the hash-bound manifest at
`research/kalshi/agents/frankie_native_raw_mbo_knowledge/KNOWLEDGE_MANIFEST_20260828.json`:
use `FORECASTER_A_CLEAN_REVIEW` for A-clean and
`FORECASTER_A_MEMORY_REVIEW` for A-memory. Bind the exact generated context-
bundle and knowledge-receipt hashes to the principal EXECUTION RECEIPT - the
committed staged request and the committed artifact, both hash-bound. There is no
model-call receipt: the principal runs as an agent session over committed files and
no provider API is called (Greg, 2026-08-29; the file-based gate landed at S115).

Determine whether the first native-MBO replay outputs contain valuable positive
forecasting information. Inspect the complete same-arm output—not only one
headline statistic—and preserve its exact provenance.

## Required review surface

Review the per-source-day `first`, `last`, `min`, `max`, and arithmetic `mean`
for:

- spread and full-depth imbalance;
- full bid/ask depth;
- full bid/ask order count; and
- full bid/ask price-level count.

Also review every other same-arm diagnostic output, including action totals,
side totals, event-group counts, maximum group-action counts, causal watermarks,
source/session boundaries, and any additional controller metrics present.

## Analytical rule

The averaged-book channel and exact member-level evidence are coequal whenever
each yields valuable information. Averages may reveal regime or scale context;
exact groups, families, orders, queues, sessions, and transitions may reveal
distinct behavior hidden by an average.

For every valuable claim:

1. identify the exact arm, source day, population, denominator, session/phase,
   metric definition, and causal clock;
2. retain the supporting exact records or evidence references;
3. provide the coequal exact and averaged views when both are meaningful;
4. never average across different families, subfamilies, side structures,
   sessions, causal phases, or cluster identities; and
5. label a valid difference caused by scope or granularity
   `COMPLEMENTARY_SCOPE_DIFFERENCE`, not a contradiction.

Return only positively supported findings, correlations, hypotheses, regime
clues, timing clues, falsifiers that sharpen a positive hypothesis, and useful
follow-up calculations. Omit unsupported absence/insufficiency conclusions from
the positive knowledge handoff. Do not manufacture value: every retained claim
must bind to the same-arm output bytes and lawful causal cutoff.

This is a read-only research review. It does not authorize an order, Step-1
access, cross-arm transfer, RT-state mutation, or a scientific lock by itself.
