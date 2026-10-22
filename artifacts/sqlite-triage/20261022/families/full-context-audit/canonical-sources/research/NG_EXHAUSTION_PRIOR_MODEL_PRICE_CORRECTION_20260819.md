# NG Exhaustion PRIOR Recovery — Independent Models + Price Information Correction — 2026-08-19

Status: **AUTHORITATIVE CORRECTION FOR THE RECOVERY PASS.**

## 1. No 2-of-3 model consensus gate

The recovery pass must not require two of three models to agree before preserving a valid causal prediction.

For D0-D3:

- logistic, ExtraTrees, and distance-weighted KNN are evaluated independently;
- each model receives its own chronology, discovery-only tuning, validation, untouched confirmation, and held non-contradiction checks;
- each model receives its own earliest causal PRIOR H result;
- disagreement between models is evidence and must be preserved;
- a valid pre-birth result from one predeclared model may not be discarded solely because the other two models fail or disagree;
- there is no model-vote promotion rule in this recovery pass.

A target is considered resolved for the purpose of avoiding unnecessary later-H computation once at least one predeclared model has independently validated an earlier PRIOR H. All other model results through that resolved H remain preserved. This is a compute rule only; it does not erase model disagreement and does not promote a live play.

D4 and D5 remain sparse preserved case studies rather than forced statistical universals.

## 2. PRIOR means before the target is born

The primary search remains PRIOR-first.

For target stage D, only information from already-causal predecessor occurrences may be used before target `t0`.

The target detector-relative clock remains fallback only and may not begin for a target until the full PRIOR search required for that unresolved target has failed.

## 3. Pre-birth price is predictive information, not merely post-birth execution data

Every predecessor occurrence carries its own distinct causal one-second price path through H exactly as required by the existing price-structure addendum.

For each model and each PRIOR H, report two matched causal views on the same eligible rows:

1. `POLARITY_ONLY`: ordered predecessor polarity only;
2. `POLARITY_PLUS_PRICE_PATH`: ordered predecessor polarity plus each predecessor occurrence's full causal one-second price prefix through H.

The price-path view is the primary full-information model. The polarity-only view is an ablation baseline used to measure whether pre-birth price adds predictive value.

For validation, untouched confirmation, and held where applicable, report incremental price value on matched rows using at minimum:

- log-loss improvement of price-path model versus polarity-only model;
- Brier improvement of price-path model versus polarity-only model;
- AUC difference when both blocks contain both classes;
- support and chronology block identity.

Price availability/missingness remains infrastructure only and may not become a feature.

## 4. Price after birth remains active too

When a target D actually begins, its own causal price path becomes available only from that birth onward.

Post-birth work must therefore keep two separate clocks/information sets:

- **before birth:** predecessor histories + predecessor causal price paths only;
- **after birth:** predecessor histories remain available, and the newly born target's own causal price path may be added for recognition, trade management, next-stage prediction, continuation/reset/reverse decisions, and downstream chain research.

No target price after `t0` may leak backward into a pre-birth PRIOR prediction.

## 5. Trade handoff

If a PRIOR signal validates before birth, execution economics begin at the exact causal PRIOR signal timestamp. The already-known market price at that timestamp is part of execution, and the predecessor price path that generated the signal remains available.

After target birth, the target's own causal price evolution may update management or downstream-state decisions, but it may not retroactively redefine the original pre-birth signal.

## 6. Preserve everything

No D, H point, model disagreement, negative result, low-support case, censored row, or failed hypothesis is deleted.

`resolved` means only: the earliest required answer for that target has been found, so later H values cannot produce an earlier answer and need not consume compute for that target.

Unresolved targets continue through the full authorized PRIOR H grid. Only after PRIOR fails may they enter the detector-relative fallback ladder.

## Protected boundaries

This correction does not modify or retune the frozen detector, frozen canonical evidence, Phase-1 lineage/scores, finalized Phase-2 findings, frozen runway clock, permanent Frankie, Frankie 1, `research/kalshi/spawn.py`, or the frozen SSOS play. No permanent brain merge or live-play promotion is authorized.
