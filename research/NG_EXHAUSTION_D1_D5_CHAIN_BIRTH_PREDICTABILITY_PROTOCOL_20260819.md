# NG Exhaustion D1-D5 Chain-Birth Predictability Protocol — 2026-08-19

Status: **AUTHORITATIVE TARGET CORRECTION FOR THE ENTRY-TIMING REVIVAL. PRIOR PREDICTION IS PRIMARY; THE DETECTOR-RELATIVE CLOCK IS FALLBACK ONLY.**

## Primary question

For each stage D1 through D5, determine the **earliest causal time at which we can predict that the next chain stage is going to begin**.

This supersedes any interpretation that makes the primary target the future behavior vector of a chain link already known to exist. The frozen full behavior vector remains a secondary characterization target only after chain-birth timing is established.

## Search hierarchy — PRIOR first, fallback clock only if PRIOR fails

The research order is:

1. **Exhaust the PRIOR search first for every D1-D5 stage.** Test whether already-causal predecessor information predicts that the next stage will begin before its frozen `t0`.
2. **Only if no PRIOR point validates for a chain/rule/subfamily**, move to the detector-relative fallback ladder.
3. The fallback ladder is:

`+0 detector confirmation -> +1 -> +2 -> +3 -> +4 -> +5 -> +10 -> +15 -> +20 -> +25 -> +30 -> ... every 5 seconds through +3600`

The active H values used to age causal predecessor information in the PRIOR search, and then as fallback survival checkpoints when needed, are:

`H = 1,2,3,4,5,10,15,20,25,30,35,...,3600`

**PRIOR is not closed off by the fallback clock. PRIOR is the preferred result.** If a chain stage can be predicted before birth, preserve that earliest causal prior signal even if +0 or a later checkpoint is cleaner or stronger.

For the primary question, only a validated PRIOR point counts as predicting chain birth before it begins. `+0` and later checkpoints are recognition/fallback timing for cases where pre-birth prediction cannot be validated; they must not be mislabeled as prediction of the beginning.

## Frozen conditional birth cohorts

Use the frozen Phase-1 lineage exactly as written. Do not invent negatives.

For stage D, condition on the chain having reached D-1 and ask whether it extends to D:

| Stage being predicted | Positive: next stage begins | Frozen negative/control: chain stops at prior stage |
|---|---:|---:|
| D1 | depth >= 1: 20,562 | exact D0: 135,860 |
| D2 | depth >= 2: 1,725 | exact D1: 18,837 |
| D3 | depth >= 3: 133 | exact D2: 1,592 |
| D4 | depth >= 4: 9 | exact D3: 124 |
| D5 | depth >= 5: 1 | exact D4: 8 |

These counts are the 36 forward-OOT base weeks represented in the frozen lineage plus held `20260329`. The first 18 base weeks remain outside forward-OOT birth-validation credit unless separately validated reverse-backcast work succeeds.

The original exact populations remain preserved as evidence: D1=18,837, D2=1,592, D3=124, D4=8, D5=1. The positive birth cohort for a stage includes deeper chains because a D3/D4/D5 chain necessarily experienced the earlier D1/D2 births.

## Frozen event alignment

For a lineage origin at sequence index `i`, stage D birth refers to the already-frozen canonical event at sequence index `i + D`.

- predecessors available to the D-stage rule: canonical events `i ... i + D - 1`;
- target birth onset: frozen target `t0_idx` at `i + D`;
- target detector confirmation: frozen target `dynamic_endpoint.causal_confirmation_idx`;
- no event is redetected and no target `t0` is changed.

Rows whose required canonical target is unavailable because the frozen week ends are preserved as censored/model-ineligible rather than manufactured or deleted.

## PRIOR H test — the main success condition

At active H, predecessor `j` is ready at:

`PREDECESSOR_READY(j,H) = predecessor_j.causal_confirmation_idx + H`

The full D-stage rule is prior-eligible only if:

`RULE_READY(D,H) = max(PREDECESSOR_READY(j,H)) <= target.t0_idx`

Record actual lead:

`PRIOR_LEAD_SECONDS = target.t0_idx - RULE_READY(D,H)`

H is **information age after causal predecessor detection**, not a synthetic number of seconds before target onset.

Test PRIOR H in ascending order and preserve the earliest chronologically/OOT validated prior signal. Do not abandon the PRIOR search merely because the target later becomes detectable. Do not replace an earlier valid PRIOR signal with a later cleaner fallback signal.

At PRIOR H, features may use only causal predecessor information available by each predecessor confirmation+H. The allowed fresh raw-path summary is restricted to predecessor polarity and causal partial price-path displacement/MFE/MAE/range through H.

The following are prohibited as PRIOR features:

- target identity, polarity, family, state, or future path;
- predecessor `next_same_polarity` or other fields that reveal the not-yet-born target;
- realized final chain depth;
- realized final duration;
- family, frozen post-state, flow, book, time of day, session position, pre-exhaustion shape;
- explicit timing/confirmation lag as a model characteristic (timing may gate availability only).

This preserves the settled Phase-1 causal characteristics wall.

## Fallback clock — only after PRIOR fails

If no PRIOR H validates for the relevant stage/rule/subfamily, then and only then test:

`+0, +1, +2, +3, +4, +5, +10, +15, +20, +25, +30, ... every 5 seconds through +3600`

`+0` is when the target itself is causally confirmed. Later checkpoints use only information causal by that checkpoint plus the fact of survival to that checkpoint.

These results answer **when chain membership becomes recognizable after birth**, not when birth was predicted. Report them separately as `AT_DETECTION_RECOGNITION` or `POST_DETECTION_RECOGNITION`.

Fallback recognition is useful for trade rescue/management when a chain could not be called beforehand, but it must never overwrite or delay a validated PRIOR entry.

## Chronological validation

Use the existing forward-OOT chronology:

- eras 1-2: discovery fit;
- era 3: discovery tune;
- eras 4-5: validation;
- untouched confirmation: confirmation;
- held `20260329`: insert-only held.

No tuning on validation, confirmation, or held.

For D1-D3, require out-of-sample predictive skill against a discovery-frozen base-rate/null benchmark on the same eligible rows. Report model probability loss, discrimination, positive-week stability, support, and the D-vs-D-1 history incremental comparison. A chain birth may be predictable even if the full D history adds little beyond D-1, so absolute birth-prediction skill and incremental depth gain must be reported separately.

D4 and D5 remain preserved low-support case studies; do not force a universal timing law.

## Trade-strategy handoff

The timing study exists to support executable trade strategies.

For every validated PRIOR birth signal, attach trade research to the **exact causal signal timestamp**, not to a later detector or convenient checkpoint. Measure direction/behavior, entry price, remaining runway, MFE/MAE, endpoint behavior, path efficiency/chop, cost stress, and candidate exits from that timestamp forward.

For stages/subfamilies with no validated PRIOR signal, strategy research may use the earliest validated fallback recognition point, clearly labeled as fallback rather than birth prediction.

Thus:

- PRIOR answers **can we get positioned before the next chain stage begins?**
- behavior/direction analysis answers **what should we trade once we have the signal?**
- raw-path economics answers **is the remaining opportunity large and stable enough to execute?**
- fallback clock answers **can we rescue a trade when pre-birth prediction is unavailable?**

## Secondary target only

After earliest chain-birth timing is established, the previously frozen full behavior vector — next same/flip plus displacement/MFE/MAE at 5/10/20/30/60/120/300 seconds — may be used to answer the secondary question: **what behavior follows once the next chain stage begins?**

It may not replace the birth target or be used to claim pre-birth predictability.

## Protected boundaries

Do not modify or retune the frozen detector, canonical rows, Phase-1 lineage/scores, finalized Phase-2 findings, runway clock, permanent Frankie, Frankie 1, `research/kalshi/spawn.py`, or the frozen SSOS play. No permanent brain merge and no play freeze are authorized.
