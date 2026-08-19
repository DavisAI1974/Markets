# NG Exhaustion D0 Predictable + Tradeable Protocol — 2026-08-19

Status: **FOCUSED D0 RESEARCH CONTRACT. TWO QUESTIONS ONLY. PRESERVE ALL ORIGINAL D0s. NO PERMANENT PROMOTION.**

## Purpose

D0 has so far served mainly as the negative/control side of D1 chain-birth prediction. This protocol promotes D0 to its own research population without reopening Phase 1/Phase 2 or changing the active D1-D5 Chain-Birth V2 contract.

The D0 program is deliberately narrow. It asks only:

1. **When can we causally predict that a root exhaustion will remain D0 rather than extend to D1, and is there an executable trade from that earliest validated clock?**
2. **Does causal information from the root/D0-stage exhaustion add incremental predictive value for later D2/D3 births (and preserved D4/D5 cases)?**

No broad D0 taxonomy, motif hunt, family study, or side research is authorized unless it directly answers one of those two questions.

## Frozen population — never renumber or drop

Original frozen exact-depth counts remain:

- D0 = 135,860
- D1 = 18,837
- D2 = 1,592
- D3 = 124
- D4 = 8
- D5 = 1

For the active forward-OOT + held D1-birth cohort, exact-D0 contributes:

- executable D0 controls = 135,823
- target-unavailable/week-end censored D0 = 37
- total preserved D0 = 135,860

The 37 censored rows are parked as preserved research evidence. They are not silently deleted or re-labeled to improve a result.

Policy: `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.

## Agent A — D0 terminality -> trade

### Primary D0 timing signal

D0 terminality is the complement of D1 birth on the same uncensored cohort.

If Chain-Birth V2 validates a D1 **PRIOR** birth signal at exact causal time:

`SIGNAL_TIME = origin causal_confirmation_idx + H`

then at that same timestamp:

`P(D0 terminal) = 1 - P(D1 birth)`

This is the primary D0 predictor. Do **not** build a separate hindsight exact-D0 classifier when the validated D1 complement already answers the same binary question.

A D1 `+0` or post-detection winner does not count as pre-birth D0 prediction. If D1 has no validated PRIOR signal, D0 terminality remains unresolved under the primary path and any future fallback must be a separately causal D0 survivorship study.

### Frozen model-to-signal rule

For D0 strategy research, use the V2 D1 winning PRIOR H exactly. Do not delay it for a cleaner later H.

For probability aggregation, use the median of all three predeclared V2 model probabilities (logistic, extra trees, distance-weighted KNN). Do not select models using realized trade returns.

Hyperparameters remain discovery-frozen under the V2 chronology.

### Trade clock and execution

Candidate entry clock is the exact D1 PRIOR signal timestamp inherited above.

Executable fill rule:

- entry = first authoritative NG trade at or after the signal timestamp;
- candidate exit horizon = first authoritative NG trade at or after the planned horizon;
- cap the research holding window at the onset of the next canonical exhaustion event so a D0 trade does not silently consume a later exhaustion regime;
- if required raw tape/fill is unavailable, fail closed or mark the row censored; never use missingness as a strategy feature.

### Tight candidate grid

Do not wander across arbitrary strategy searches.

D0 probability thresholds:

`0.75, 0.85, 0.90, 0.95, 0.975`

Candidate holding horizons from signal:

`5, 10, 20, 30, 60, 120, 300 seconds`

Two orientations only:

- `WITH_ROOT_POLARITY`
- `AGAINST_ROOT_POLARITY`

Measure for every candidate:

- signaled n;
- realized exact-D0 fraction among signaled rows;
- gross ticks;
- 0.5 / 1.0 / 2.0 tick cost stress;
- MFE;
- MAE;
- net displacement;
- range/path efficiency;
- positive-week fraction;
- chronology-block results.

Candidate ranking may be developed only on the discovery blocks. Exact threshold/orientation/horizon candidates are then frozen before validation, untouched confirmation, and held reporting.

No D0 row is removed because its realized trade is bad. Bad/false signaled cases remain in the evidence.

### D0 strategy success boundary

A historical D0 candidate may be called `HISTORICALLY_VALIDATED_CANDIDATE` only if the frozen candidate has positive 1-tick net expectancy in validation and untouched confirmation, positive-week fraction >= 0.5 in both blocks, sufficient support, and held does not contradict when held support is meaningful.

This is **not** live promotion. Fresh prospective/OOT promotion is still required.

## Agent B — root/D0-stage information value for deeper births

This agent must distinguish causal root-stage information from the hindsight label `exact D0`.

The realized final label "this remained D0" may never be used to predict a later D stage; that would leak the future.

For D2 and D3, Chain-Birth V2 already constructs the required paired ablation:

- `long` history = root predecessor + all later required predecessors;
- `short` history = identical eligible cases and timing, but with the root predecessor removed.

Therefore the focused D0/root question is:

> On the same D-eligible rows and exact H, does adding the root predecessor improve validated birth prediction relative to removing it?

Audit, model by model and block by block:

- incremental log-loss gain of long vs short;
- incremental Brier gain of long vs short;
- whether gains are positive in validation and confirmation;
- whether held contradicts when support is sufficient;
- whether the full-history signal validates while root-ablated history does not.

Evidence grading:

- `ROOT_INFORMATION_VALIDATED_INCREMENTAL` = at least 2 of 3 predeclared models have positive incremental log-loss and Brier gain in validation and confirmation, with no supported held contradiction;
- `ROOT_INFORMATION_MIXED` = signs/model conclusions differ materially by block;
- `ROOT_INFORMATION_NOT_INCREMENTAL` = root does not add stable validated skill;
- D4/D5 = preserved case-study annotations only; no universal law.

D1 is a special case: the root is the only predecessor, so D1 prediction itself is the direct test of root-stage information.

## Chronology

Keep the current V2 chronology unchanged:

- eras 1-2: discovery fit;
- era 3: discovery tune;
- eras 4-5: validation;
- untouched confirmation: final historical confirmation;
- held `20260329`: insert-only, no retuning.

The first 18 original Phase-1 training weeks are not manufactured into forward-OOT D0/D1 labels.

## Characteristics wall

The focused D0 work inherits the active Chain-Birth V2 wall.

Do not use as predictive characteristics before they are causally available:

- realized exact-D0/final-depth identity;
- target identity/polarity/family/state before birth;
- predecessor future-revealing `next_same_polarity` fields;
- realized final duration;
- future path shape;
- family;
- frozen post-state;
- flow;
- book;
- time of day;
- session position;
- pre-exhaustion shape;
- confirmation lag/timing as a characteristic.

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

No permanent brain merge and no historical play freeze are authorized.

## Dependency

Agent A and Agent B are armed to run only after the durable Chain-Birth V2 reconcile output exists. This avoids duplicating the active V2 experiment and ensures D0 timing inherits the exact validated D1 clock rather than inventing a parallel clock.
