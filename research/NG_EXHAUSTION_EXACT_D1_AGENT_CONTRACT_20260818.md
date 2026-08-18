# NG Exhaustion Exact-D1 / Single-Link Agent Contract — 2026-08-18

Status: **AUTHORIZED POST-PHASE-2 CHARACTERIZATION; SINGLE-LINK POPULATION FIRST-CLASS; NO PERMANENT BRAIN MERGE; NO PLAY FREEZE.**

## Purpose

Investigate the exact-D1 / single-link exhaustion population that was preserved by the original Phase-1 contract but not separately characterized in the later D2/D3 timing work.

The central question is whether some chains that stop after one predictive link nevertheless contain **long-duration legs** that carry distinct state/polarity, price-path, re-origin, or execution information.

Exact D1 means `all_model_consecutive_positive_depth == 1` in the frozen Phase-1 lineage. It must not be described as a failed D2 chain; it is its own valid mechanism class.

## Immutable sources

Use the same frozen 55-week evidence as finalized Phase 2:

- base54 canonical artifact `9281733364`, ZIP SHA256 `f50eaf74a57654334691cbf5cce3b038443f6944a9c00eb5da6ca35b557802b1`;
- held canonical artifact `9281272840`, ZIP SHA256 `21577d01d45241264df714ab6ee5b95f6a774e1475e0d74a9454221fdfdde12e`;
- Phase-1 lineage artifact `9289929292`, ZIP SHA256 `a67caab9de6b183e8c102ebd73a7e542aa909e23f66575290563e40b056efd95`;
- final 55-week reconciliation artifact `9306082330`, ZIP SHA256 `f17c130df029429bfbc35067d1cc9d16128ca4fb227dd37f3fb4fbb8bbaf8875`.

For raw-path reconstruction only, use the already-authoritative raw NG corpus under `s3://bento-568968024170-us-east-2-an/nymex/nymex_cont/NG_*`; do not redetect events. Raw tape is used only to reconstruct price between already-frozen canonical t0 indices.

## Protected boundaries

Do not modify or retune:

- frozen exhaustion detector;
- canonical 54-week base or held rows;
- frozen Phase-1/Phase-2 lineage and scores;
- frozen runway clock;
- permanent Frankie;
- Frankie 1;
- `research/kalshi/spawn.py`;
- frozen SSOS paper play;
- finalized Phase-2 findings or proposal files.

No valid short or long exact-D1 instance may be deleted because it is inconvenient.

## Chronological protocol

Use the same block partition already used by the post-Phase-2 campaign:

- first 18 base weeks = train/discovery;
- next 18 = Eras1-3 validation;
- next 12 = Eras4-5 validation;
- final 6 base weeks = untouched historical confirmation;
- held `20260329` = insert-only held week.

Duration families must be learned from **train exact-D1 only**. Later blocks are assignment/validation only. Fitted centers or empirical quantiles are characterization labels, never live cutoffs.

## Seven independent lanes

1. **D1 lifespan agent** — characterize the complete exact-D1 elapsed-time distribution, fit train-only log-time mixture models with BIC selection, freeze the selected train model, assign later exact-D1 instances, and report short/middle/long-tail proportions, quantiles, maxima, and held replication.

2. **D1 grammar agent** — map origin state + descendant state + same/flip polarity (`PP|S`, `OS|F`, etc.) inside each train-frozen D1 duration family. Determine whether long exact-D1 legs are enriched for particular local grammar without using duration as a trade rule.

3. **D1 true/false decomposition agent** — preserve all long and short cases and test older causal ancestry, family/A-poststate/seed-state context where available, chronological regime, and duration family. Policy remains `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.

4. **D1 outcome agent** — compare origin aftermath and descendant aftermath across duration families and pair grammars. Use only canonical frozen outcomes. Do not optimize stops or select management rules.

5. **D1 causal-runway agent** — measure how much of each exact-D1 lifespan remains after the origin predecessor h=60 information wall is causally available. Distinguish retrospective long duration from a leg that still has meaningful remaining time after the origin is fully characterized. Never infer the final duration family before it is knowable.

6. **D1 termination/re-origin agent** — after the one-link chain ends at its descendant, inspect the descendant's own frozen lineage depth and later state to distinguish true termination from immediate rolling/re-origin. Do not reinterpret descendant depth as inherited same-origin depth.

7. **D1 raw-leg-path agent** — reconstruct the actual NG trade-price path from exact-D1 origin t0 to descendant t0 using the authoritative raw tape and the frozen canonical indices. For train-defined long-tail cases and matched short/middle controls, report signed displacement relative to origin polarity, MFE, MAE, endpoint displacement, path monotonicity/choppiness summaries, and duration. Do not redetect events from the raw tape.

## Required end products

- one machine-readable output per lane;
- a verification manifest with hashes and protected-boundary assertions;
- a human-readable all-agent exact-D1 findings record;
- explicit statement whether long-duration exact-D1 legs exist and replicate;
- exact pair/state/polarity grammars associated with those long D1 legs;
- causal lead/runway remaining after the origin h=60 wall;
- raw-tape evidence of what price actually does during the long single link;
- true/false and regime decompositions;
- a curated brain proposal extending (not replacing) the runway and Phase-2 proposals;
- separate historical trade-strategy proposals only where causal/execution evidence supports them;
- no permanent Frankie merge and no new play freeze without fresh prospective/OOT promotion.

## Promotion boundary

This campaign may discover that a single-link chain can be long-lived and may nominate historical strategy candidates. It may not convert realized duration into a live rule, may not promote a fitted duration center as a cutoff, and may not freeze a strategy from the already-mined 55-week history alone.
