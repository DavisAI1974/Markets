# Complementary indicator stack — November 8, 2026

User-authorized research extension. Codex owns this plan and its findings; merge
reviewers at the end. Existing NG applicability is settled. No producer reruns.

1. [x] Build a causal recognition-state table for all 863 saved candidates.
   Preserve original source clocks, empty flow and unavailable observations.
   Separate price context, dipole, fresh trades, displayed book, and same-price
   displayed changes. Verify changing best prices do not count as replenishment.
2. [x] Compare fixed ridge arms on identical eligible rows: baseline, each added
   layer, dipole+book, full stack, and each full-stack leave-one-layer-out arm.
   Use training-only scaling/imputation, alpha 10, chronological 40/60/80% splits,
   outcome purge plus 600-second embargo. Retain per-case predictions and fold
   results. Targets: midpoint change/magnitude at 5/20/60 seconds and change in
   absolute rolling-flow strength at 20 seconds where both ratios exist.
3. [ ] Preserve interpretable state combinations, missing cases, sample counts,
   source examples, and overlapping outcome clusters. Produce a graph and append
   positives, inverse findings and limitations to Codex's own findings file.
   Run focused tests, inspect graph, commit and push without overwriting peers.

Prices and clock positions are not identity features. Times/cursors establish
availability, chronology and provenance only. Fixed cutoffs are zero/balance or
the declared lookback, not searched trading thresholds. All four dates remain
discovery; this increment uses October 18's currently saved comparable evidence.
Same-price display additions are an aggregate proxy, not proof of same-order
refresh, iceberg reserve, executed absorption or participant intent. Retain
unknown trade volume. Observe survival/undefined-flow separately from price side.
Do not identify the best-looking October arm as a validated general-market rule.
