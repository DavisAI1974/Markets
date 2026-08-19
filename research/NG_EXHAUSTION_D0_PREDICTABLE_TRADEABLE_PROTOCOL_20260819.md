# NG Exhaustion D0 Predictable + Tradeable Protocol — 2026-08-19

Status: **FOCUSED STANDALONE D0 RESEARCH CONTRACT. PREDICT D0 DIRECTLY, TRADE IT DIRECTLY, AND TEST ROOT INFORMATION FOR DEEPER CHAINS. PRESERVE ALL ORIGINAL D0s. NO PERMANENT PROMOTION.**

## Purpose

D0 has so far served mainly as the negative/control side of D1 chain-birth prediction. That is not sufficient. D0 is a first-class exhaustion outcome and does **not** depend on D1 being validated to be useful.

The D0 program is deliberately narrow but complete. It asks only:

1. **When can we directly and causally predict that a root exhaustion will remain D0 rather than extend to D1?**
2. **From the earliest validated D0 signal, what executable price trade remains, in either orientation, after realistic cost stress?**
3. **Does causal root/D0-stage information improve prediction of D1, D2, D3 and preserved D4/D5 continuation?**

The wider program still aims to predict as much of the full exhaustion chain as the evidence supports. D0 is not dropped, subordinated, or treated only as a control.

No broad D0 taxonomy, motif hunt, family study, or side research is authorized unless it directly improves D0 prediction, D0 tradeability, or deeper-chain prediction.

## Frozen population — never renumber or drop

Original frozen exact-depth counts remain:

- D0 = 135,860
- D1 = 18,837
- D2 = 1,592
- D3 = 124
- D4 = 8
- D5 = 1

For the forward-OOT + held root terminality cohort:

- exact-D0 terminal positives = 135,823 executable rows;
- D1+ continuation controls = 20,562;
- target-unavailable/week-end censored exact-D0 = 37;
- total preserved original D0 = 135,860.

The 37 censored rows are parked as preserved research evidence. They are not silently deleted or re-labeled to improve a result.

Policy: `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.

## Agent A — direct D0 PRIOR-first terminality predictor

D0 is modeled directly. Do not require the D1 V2 result to exist first.

### Target

Condition on the root exhaustion being present.

- positive = the chain terminates at exact D0;
- negative/control = the chain extends to D1 or deeper;
- censored = next canonical target is unavailable at frozen week end.

The realized exact-D0 label is the **future target**, never an input feature.

### Causal clock

For root detector confirmation `c`, test active H in ascending order:

`H = 1,2,3,4,5,10,15,20,25,30,35,...,3600 seconds`

At H, the model may see only information causally available through `c+H`.

For a row to be PRIOR-eligible:

`c + H <= next canonical exhaustion t0`

Actual lead:

`D0_PRIOR_LEAD_SECONDS = next_event_t0 - (c + H)`

Earliest chronologically/OOT validated PRIOR H wins. Do not delay a valid earlier D0 signal for a cleaner later one.

If no PRIOR H validates, direct D0 fallback recognition/survivorship may be studied from the root detector clock under a separately causal ladder. No hindsight final-duration or final-D0 information may leak into an earlier checkpoint.

### Input

Use the root exhaustion's own separate causal one-second price path:

- baseline = last authoritative trade known at or before root detector confirmation;
- at integer second s, last authoritative trade known at or before `c+s`;
- carry forward last known price if no new trade occurs;
- no future interpolation;
- at H, only seconds `1..H` are visible;
- root polarity may be included because it is known at the root event.

Price availability is infrastructure, never a feature. Missing required tape fails closed.

### Models and chronology

Use the same predeclared model family and chronology as Chain-Birth V2:

- logistic regression;
- extra trees;
- distance-weighted KNN;
- eras 1-2 discovery fit;
- era 3 discovery tune;
- eras 4-5 validation;
- untouched confirmation;
- held `20260329` insert-only.

Require at least 2 of 3 models with positive log-loss and Brier gains vs frozen null, ROC AUC > 0.5, positive-week Brier stability >= 0.5, sufficient support, and no supported held contradiction.

### D1 complement cross-check

After D1 Chain-Birth V2 lands, compare the direct D0 model with `1 - P(D1 birth)` at matched H/rows. This is a **consistency and calibration cross-check only**. D0 validity does not depend on D1 validating first.

## Agent B — D0 terminality -> executable trade

Agent B begins from Agent A's earliest validated direct D0 PRIOR H. If Agent A has no validated PRIOR H, Agent B may only use an explicitly validated D0 fallback clock.

### Signal and fill

- signal time = exact causal D0 model timestamp;
- entry = first authoritative NG trade at or after signal time;
- planned exit = first authoritative trade at or after the candidate horizon;
- cap the research holding window at the onset of the next canonical exhaustion event so a D0 trade never silently consumes a later exhaustion regime.

### Tight candidate grid

D0 probability thresholds:

`0.75, 0.85, 0.90, 0.95, 0.975`

Candidate holding horizons:

`5,10,20,30,60,120,300 seconds`

Two orientations only:

- `WITH_ROOT_POLARITY`
- `AGAINST_ROOT_POLARITY`

For every candidate measure:

- signaled n;
- realized exact-D0 fraction;
- gross ticks;
- 0.5 / 1.0 / 2.0 tick cost stress;
- MFE;
- MAE;
- net displacement;
- range/path efficiency;
- positive-week fraction;
- discovery/validation/confirmation/held results.

Candidate selection occurs only on discovery information. Freeze threshold/orientation/horizon before validation, untouched confirmation, and held reporting.

A historical D0 trade candidate may be called `HISTORICALLY_VALIDATED_CANDIDATE` only when the frozen candidate has positive 1-tick net expectancy in validation and untouched confirmation, positive-week fraction >= 0.5 in both, sufficient support, and no meaningful held contradiction.

No D0 row is removed because its realized trade is bad. Losing/false signal rows remain evidence.

## Agent C — root/D0-stage information value for the rest of the chain

This agent asks whether the root-stage exhaustion carries useful information for later chain prediction.

The hindsight label `exact D0` may never be used to predict a later D stage. Only root information that was causally available by the tested signal time is allowed.

### D1

D1 birth versus D0 terminality is the direct root-stage continuation question. Agent A and the D1 Chain-Birth V2 lane provide complementary direct views of that boundary.

### D2 and D3

Chain-Birth V2 already provides the paired ablation on identical eligible rows:

- `long` history = root predecessor + all later required predecessors;
- `short` history = same cases/timing with the root predecessor removed.

Audit model by model and block by block:

- incremental log-loss gain of full/root-retained history vs root-ablated history;
- incremental Brier gain;
- whether gains are positive in validation and confirmation;
- held contradiction when support permits;
- whether full history validates when root-ablated history does not.

Evidence grades:

- `ROOT_INFORMATION_VALIDATED_INCREMENTAL` = at least 2 of 3 predeclared models show positive incremental log-loss and Brier gains in validation and confirmation with no supported held contradiction;
- `ROOT_INFORMATION_MIXED` = model/block conclusions differ materially;
- `ROOT_INFORMATION_NOT_INCREMENTAL` = no stable validated root contribution.

### D4 and D5

Preserve root-stage contribution as individual case evidence only. Current support is too small for universal law. Do not drop the cases.

## Predict-everything boundary

The research goal remains to predict every useful component that can be supported causally:

- whether the chain stops at D0 or extends;
- when D1-D5 stages are going to begin;
- what later stages are likely to do once birth timing is established;
- whether root information improves deeper-stage prediction;
- whether each validated prediction leaves enough executable price opportunity after costs.

Failure to validate a particular D0/D1/D2/D3/D4/D5 rule does not remove that group from its original population. It is parked for later decomposition/research under its original number.

## Characteristics wall

Do not use as predictive characteristics before they are causally available:

- realized exact-D0/final-depth identity;
- target identity/polarity/family/state before birth;
- future-revealing `next_same_polarity` fields;
- realized final duration;
- future path shape;
- family;
- frozen post-state;
- flow;
- book;
- time of day;
- session position;
- pre-exhaustion shape;
- confirmation lag/timing as a predictive characteristic.

Timing may establish causal availability and signal time only.

## Protected boundaries

Do not modify or retune:

- frozen exhaustion detector;
- canonical base/held rows;
- frozen Phase-1 lineage/scores;
- finalized Phase-2 findings/freeze;
- frozen runway clock;
- permanent Frankie;
- Frankie 1;
- `research/kalshi/spawn.py`;
- frozen SSOS play.

No permanent brain merge and no historical play freeze are authorized. Fresh prospective/OOT promotion remains required.

## Parallel execution rule

Agents A and B may run immediately in parallel with the active D1-D5 V2 workflow because they use immutable frozen sources and do not alter its contract.

Agent C's D2/D3 root-ablation audit waits only for the durable V2 reconciled output because that output contains the paired full-vs-root-ablated metrics. This dependency does **not** block standalone D0 prediction or trade research.
