# NG Exhaustion D1-D5 Predictability Timing Grid — 2026-08-19

Status: **AUTHORITATIVE TIMING CONTRACT FOR THE ENTRY-TIMING REVIVAL. PRIOR CHAIN-BIRTH PREDICTION FIRST; FALLBACK CLOCK ONLY AFTER PRIOR FAILURE. PRESERVE ALL D1-D5. PHASE 2 REMAINS FROZEN.**

## Primary purpose

For every D1-D5 stage, determine the **earliest causal PRIOR point at which we can predict that the next chain stage is going to begin before its frozen target `t0`**.

This timing work exists to support executable trade strategies. Once a PRIOR birth signal validates, later behavior/direction and raw-price economics are measured from that exact causal signal timestamp.

The future full behavior vector remains a secondary question: **what happens after the next stage begins?** It is not the primary timing target.

## Search hierarchy

For every D1-D5 stage/rule/subfamily:

1. **Exhaust the PRIOR search first.**
2. If a PRIOR point validates, preserve the earliest validated causal point. Do not delay it to a cleaner later observation.
3. **Only if PRIOR fails**, enter the detector-relative fallback ladder.
4. If no fallback point validates with usable remaining opportunity, preserve the evidence and do not force a trade.

Therefore PRIOR is not part of a delay clock. It is the preferred outcome.

The fallback ladder is:

`+0 detector confirmation -> +1 -> +2 -> +3 -> +4 -> +5 -> +10 -> +15 -> +20 -> +25 -> +30 -> ... every 5 seconds through +3600`

`+0` and later are **recognition/fallback** results, not successful pre-birth prediction.

## Active H grid

Use:

`H = 1,2,3,4,5,10,15,20,25,30,35,...,3600 seconds`

Equivalently:

`H_GRID = [1,2,3,4,5,10,15] + range(20,3601,5)`

The same H grid applies to D1, D2, D3, D4, and D5.

In the PRIOR search, H means **seconds of causal predecessor information after predecessor detector confirmation**. It is not a synthetic number of seconds before target onset.

The older coarse values `5,10,20,30,60,120,300` are historical audit/reference points only, not the active timing grid.

## Frozen chain populations

Exact frozen depths remain preserved:

| Exact depth | Population |
|---|---:|
| D1 | 18,837 |
| D2 | 1,592 |
| D3 | 124 |
| D4 | 8 |
| D5 | 1 |

For the chain-birth classification question, condition on having reached the prior stage:

| Stage being predicted | Positive birth cohort | Frozen stop/control cohort |
|---|---:|---:|
| D1 | depth >= 1: 20,562 | exact D0: 135,860; 37 known week-end controls are target-censored |
| D2 | depth >= 2: 1,725 | exact D1: 18,837 |
| D3 | depth >= 3: 133 | exact D2: 1,592 |
| D4 | depth >= 4: 9 | exact D3: 124 |
| D5 | depth >= 5: 1 | exact D4: 8 |

The positive birth cohort includes deeper chains because every deeper chain necessarily experienced the earlier-stage births.

The first 18 base weeks remain outside forward-OOT validation credit unless a separately validated reverse backcast succeeds.

## Frozen clocks

### Target onset: `TARGET_T0`

The canonical target `t0_idx` is the frozen retrospective onset of the stage being predicted. It is never moved or redetected.

### PRIOR predecessor information

For predecessor `j` at active H:

`PREDECESSOR_READY(j,H) = predecessor_j.causal_confirmation_idx + H`

For a D-stage rule:

`RULE_READY(D,H) = max(PREDECESSOR_READY(j,H) for all required predecessors)`

PRIOR eligibility requires:

`RULE_READY(D,H) <= TARGET_T0`

Record the real lead:

`PRIOR_LEAD_SECONDS = TARGET_T0 - RULE_READY(D,H)`

Test H in ascending order. Availability alone is not predictive skill; each eligible H must validate chronologically/OOT.

### Fallback detector clock

Only if the PRIOR search fails:

`+0 = target dynamic_endpoint.causal_confirmation_idx`

Then test:

`+1,+2,+3,+4,+5,+10,+15,+20,+25,+30,...,+3600`

At each fallback checkpoint use only information causal by that checkpoint plus the fact of survival to that checkpoint.

## Causal input wall for PRIOR prediction

PRIOR features may use causal predecessor information that actually exists by predecessor confirmation+H, including predecessor polarity and partial raw-price displacement/MFE/MAE/range through H.

Do not use as PRIOR features:

- target identity, target polarity, target family/state, or target future path;
- predecessor `next_same_polarity` or any field that reveals the not-yet-born target;
- realized final D depth;
- realized final duration;
- family, frozen post-state, flow, book, time of day, session position, pre-exhaustion shape;
- confirmation lag/timing as a model characteristic. Timing gates availability only.

This preserves the settled Phase-1 causal characteristics wall.

## D-specific application

- **D1 birth:** given the origin exhaustion, can we predict before the next frozen event `t0` that a D1 chain link will form? Positive = depth >=1; control = exact D0.
- **D2 birth:** given the chain has reached D1, can we predict before the next frozen event `t0` that it will extend to D2? Positive = depth >=2; control = exact D1.
- **D3 birth:** positive = depth >=3; control = exact D2.
- **D4 birth:** positive = depth >=4; control = exact D3. Low support must be preserved and labeled.
- **D5 birth:** positive = depth >=5; control = exact D4. The single positive is a case study, not a universal law.

For D1-D3 report both **absolute birth-prediction skill** against the frozen base-rate/null and **incremental D-versus-D−1 history gain** on the same eligible rows. A birth can be predictable even if the extra depth adds little incremental information, so these are separate questions.

## Trade-strategy handoff

For every validated PRIOR birth signal, strategy work starts at the exact PRIOR `RULE_READY` timestamp and measures:

- actual entry price available then;
- predicted direction/behavior after birth;
- remaining causal runway;
- MFE/MAE and endpoint displacement;
- path efficiency versus chop/rotation;
- cost stress;
- candidate exit/management rules;
- chronological/OOT stability and held behavior.

If PRIOR fails, the earliest validated `+0/+H` fallback recognition point may support a rescue strategy, but it must be labeled fallback and must never replace an earlier valid PRIOR entry.

## Required outputs

For every D/rule/subfamily report:

- support and weeks;
- all PRIOR H values tested;
- earliest validated PRIOR H if any;
- actual PRIOR lead seconds to target `t0`;
- absolute birth-prediction metrics and D-versus-D−1 incremental gain;
- all failed earlier PRIOR points and why they failed;
- if PRIOR fails, earliest fallback recognition point from `+0/+H`;
- remaining runway/opportunity at the usable timing point;
- true/false/context decomposition under `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`;
- explicit leakage audit;
- strategy handoff from the exact causal signal time.

## Protected boundaries

Do not modify or retune the frozen exhaustion detector, canonical base/held rows, frozen Phase-1 lineage/scores, finalized Phase-2 findings/freeze, frozen exhaustion runway clock, permanent Frankie, Frankie 1, `research/kalshi/spawn.py`, or the frozen SSOS play.

Do not use later signed-direction Lane 3/4 drift to redefine this program.

No permanent brain merge and no play freeze are authorized from this historical timing study.
