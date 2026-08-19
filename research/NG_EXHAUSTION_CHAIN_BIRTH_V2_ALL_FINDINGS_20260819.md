# NG Exhaustion Chain-Birth V2 — All Findings and Boundaries — 2026-08-19

Status: **AUTHORITATIVE DURABLE FINDINGS RECORD FOR THE CHAIN-BIRTH V2 ENTRY-TIMING REVIVAL. V2 PREDICTIVE RESULTS ARE STILL PENDING UNLESS DURABLE RECONCILED OUTPUTS ARE PRESENT.**

## Scope

This record preserves everything established during the 2026-08-19 chain-birth timing correction and V2 launch without reopening Phase 1 or Phase 2.

The primary research question is now:

> **At what earliest causal point can we predict that the next exhaustion-chain stage is going to begin?**

The purpose is executable strategy research. Timing identifies when a trade can first be positioned; the preserved behavior/direction work identifies what may be traded; raw price paths establish remaining opportunity and execution economics.

## 1. Primary target correction — settled protocol fact

The primary timing target is **chain birth / next-stage extension**, not the full future behavior vector of a link that is already known to exist.

For stage D, condition on the chain having reached D-1 and classify whether it extends to D.

The frozen full behavior vector — next same/flip plus displacement/MFE/MAE at 5/10/20/30/60/120/300 seconds — remains a secondary characterization target after birth timing is established. It may not be used to claim pre-birth predictability.

The earlier 20260819 full-behavior predictability workflow is therefore preserved as secondary/context work, not primary timing authority.

## 2. Search hierarchy — settled protocol fact

**PRIOR is primary and must be exhausted first.**

For every D1-D5 stage, rule, motif, and subfamily:

1. Test whether already-causal predecessor information predicts the next stage before frozen target `t0`.
2. Test active predecessor-information H values in ascending order:

   `H = 1,2,3,4,5,10,15,20,25,30,35,...,3600 seconds`

3. For predecessor j:

   `PREDECESSOR_READY(j,H) = predecessor_j.causal_confirmation_idx + H`

4. Full rule readiness:

   `RULE_READY(D,H) = max(PREDECESSOR_READY(j,H))`

5. PRIOR eligibility requires:

   `RULE_READY(D,H) <= target.t0_idx`

6. Record actual lead:

   `PRIOR_LEAD_SECONDS = target.t0_idx - RULE_READY(D,H)`

7. **Earliest chronologically/OOT validated PRIOR signal wins.** A later cleaner signal may be reported but may not overwrite an earlier valid one.

Only when PRIOR fails for the relevant rule/subfamily does the fallback recognition ladder begin:

`+0 detector confirmation -> +1 -> +2 -> +3 -> +4 -> +5 -> +10 -> +15 -> +20 -> +25 -> ... every 5 seconds through +3600`

`+0` and post-detection points are recognition/fallback timing, not prediction of birth.

## 3. Frozen conditional birth populations — settled data fact

Forward-OOT + held frozen lineage cohorts:

| Stage being predicted | Birth positive | Prior-stage stop/control | Censored |
|---|---:|---:|---:|
| D1 | depth >= 1: 20,562 | executable exact-D0: 135,823 | 37 week-end target unavailable |
| D2 | depth >= 2: 1,725 | exact-D1: 18,837 | 0 |
| D3 | depth >= 3: 133 | exact-D2: 1,592 | 0 |
| D4 | depth >= 4: 9 | exact-D3: 124 | 0 |
| D5 | depth >= 5: 1 | exact-D4: 8 | 0 |

Original exact-depth populations remain preserved:

- D0 = 135,860
- D1 = 18,837
- D2 = 1,592
- D3 = 124
- D4 = 8
- D5 = 1

The first 18 base weeks remain outside honest forward-OOT birth-validation credit unless the separately predeclared reverse-backcast work validates. They may not be manufactured into forward labels.

## 4. PRIOR availability findings — availability only, not skill

The frozen canonical availability audit establishes that substantial pre-birth causal runway exists.

At H=1, PRIOR information is available for:

- D1: 13,372 / 20,562 positive births, median positive lead 43s;
- D2: 1,171 / 1,725, median lead 47s;
- D3: 88 / 133, median lead 47.5s;
- D4: 7 / 9, median lead 60s;
- D5: 1 / 1, lead 64s.

At H=10, positive PRIOR eligibility remains:

- D1: 12,577 / 20,562;
- D2: 1,111 / 1,725;
- D3: 84 / 133;
- D4: 7 / 9;
- D5: the single case remains eligible.

At H=15:

- D1: 12,177 / 20,562;
- D2: 1,078 / 1,725;
- D3: 80 / 133;
- D4: 7 / 9;
- D5: the single case remains eligible.

At H=20-30, roughly half of D1-D3 positives remain causally testable before birth. D4/D5 retain individual prior windows but are too sparse for general laws.

**Interpretation:** PRIOR prediction is empirically testable and must remain the preferred lane. These counts do not establish predictive skill.

Full availability record:

`research/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_PRIOR_AVAILABILITY_20260819.md`

## 5. D2 H=1 polarity-only clue — explicit non-finding

A quick lower-bound probe using only causal predecessor polarities showed a small D2 H=1 structural separation clue.

Under the actual validation discipline, it **did not validate**:

- extra trees passed;
- logistic failed;
- distance-weighted KNN failed;
- required gate is at least 2 of 3 models.

Therefore:

**Do not claim D2 birth is predictable at H=1 from polarity alone.**

This remains a decomposition clue only. The active V2 run must determine whether adding the actual per-occurrence causal second-level price path makes H=1 or a later PRIOR H validate.

## 6. Per-occurrence one-second price structure — settled V2 protocol fact

Each exhaustion occurrence in a chain carries its **own separate causal price path**.

- D1: one predecessor path;
- D2: two separately ordered predecessor paths;
- D3: three;
- D4: four;
- D5: five.

They are never collapsed into a generic `price_structure_available` flag or one pooled chain path.

For occurrence detector confirmation c:

- causal baseline = last authoritative NG trade known at or before c;
- at integer second s, use only the last authoritative trade known at or before c+s;
- at H, the model sees the full causal second-by-second path from 1..H and nothing after H;
- if no new trade occurs in a second, carry forward the last already-known price;
- no future interpolation is allowed;
- the implementation stores one signed cumulative value per second relative to occurrence polarity and detector-time baseline; adjacent differences recover one-second changes.

At D3/H=15, the model therefore receives three distinct 15-second price paths in chain order.

### Price availability is infrastructure, not a model feature

Raw-tape completeness is a fail-closed data-integrity invariant.

Once the authoritative tape passes integrity:

- `price_structure_available` may not be used as a feature;
- missingness may not separate births from stops;
- positive and control rows receive identical price treatment;
- D4/D5 also receive their own individual price paths despite low support.

Authoritative addendum:

`research/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_PRICE_STRUCTURE_ADDENDUM_20260819.md`

## 7. Characteristics wall — settled protocol fact

A PRIOR birth model may not use:

- not-yet-born target identity, polarity, family, state, or future path;
- predecessor `next_same_polarity` or equivalent future-revealing fields;
- realized final chain depth;
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

Timing is used only for causal availability and actual lead reporting.

## 8. V2 validation discipline — settled protocol fact

For D1-D3, active models are:

- logistic regression;
- extra trees;
- distance-weighted KNN.

Chronology:

- eras 1-2: discovery fit;
- era 3: discovery tune;
- eras 4-5: validation;
- untouched confirmation: final historical confirmation block;
- held `20260329`: insert-only, no retuning.

The active gate requires at least 2 of 3 models to pass, with:

- positive log-loss gain vs discovery-frozen null;
- positive Brier gain vs null;
- ROC AUC > 0.5;
- positive-week Brier stability >= 0.5;
- stage-specific support floors;
- held must not contradict when held support is sufficient.

Absolute birth-prediction skill and incremental D-vs-D-1 history gain are reported separately.

D4/D5 remain low-support preserved case studies. No universal D4/D5 law may be inferred from current n.

## 9. Active V2 implementation and launch — settled engineering fact

Active runner:

`research/ng_exhaustion_d1_d5_chain_birth_agents_v2_20260819.py`

Base classifier:

`research/ng_exhaustion_d1_d5_chain_birth_agents_20260819.py`

Active workflow:

`.github/workflows/ng_exhaustion_d1_d5_chain_birth_agents_v2_20260819.yml`

Active V2 launch marker:

`research/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_AGENTS_V2_LAUNCH_20260819.json`

Launch-marker commit:

`1afbb329fe4b5cf93778b9466664b8807667f6e4`

The V2 workflow runs D1, D2, D3, and combined D4/D5 agents in parallel and reconciles only after all four complete.

## 10. Pending result boundary — do not invent findings

At the time this findings record was written, the expected reconciled V2 outputs had not yet been observed as durable branch files:

`research/generated/ng_exhaustion_entry_timing_revival_20260819/d1_d5_chain_birth_agents_v2/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_V2_ALL_AGENT_RESULTS_20260819.json`

`research/generated/ng_exhaustion_entry_timing_revival_20260819/d1_d5_chain_birth_agents_v2/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_V2_ALL_AGENT_FINDINGS_20260819.md`

Therefore there is currently **no authorized claim** that D1, D2, or D3 validates at any specific PRIOR H from the V2 price-path model.

The next session must inspect these outputs first. If absent, finish the V2 run without changing the contract.

## 11. Trade-strategy implications — authorized research direction, not a frozen play

For every validated PRIOR birth signal:

1. entry clock = exact causal `RULE_READY(D,H)` timestamp;
2. attach preserved direction/behavior evidence to determine what the predicted birth tends to do;
3. reconstruct raw price economics from that exact signal timestamp forward;
4. measure entry fill, actual prior lead, remaining runway, MFE, MAE, displacement, path efficiency, chop/rotation, and costs;
5. develop entry/sizing/exit/management candidates;
6. validate chronologically/OOT and held without retuning;
7. keep directional and chop/rotation strategies separate where appropriate.

If a stage/rule/subfamily does not validate PRIOR, use its earliest validated fallback recognition point and label the strategy as fallback. Do not delay a validated PRIOR trade to a later detector-relative point merely because it is cleaner.

No historical strategy is authorized for permanent play freeze from this study alone. Fresh prospective/OOT promotion remains required.

## 12. Protected boundaries

No work in this revival modifies or retunes:

- frozen exhaustion detector;
- canonical base/held rows;
- frozen Phase-1 lineage/scores;
- finalized Phase-2 findings/freeze;
- frozen exhaustion runway clock;
- permanent Frankie;
- Frankie 1;
- `research/kalshi/spawn.py`;
- frozen SSOS paper play.

Policy remains:

`FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`

Preserve true, false, low-support, censored, and non-validating cases. Do not delete evidence to rescue a timing rule.

## 13. Supersession map

For the **primary chain-birth timing question**:

- V2 chain-birth protocol + V2 runner/workflow supersede the first 20260819 chain-birth implementation without per-occurrence second-level paths.
- Both chain-birth implementations supersede the earlier full-behavior predictability workflow as primary timing authority.
- Older work is preserved for provenance, secondary behavior analysis, and comparison; it is not deleted.

## 14. Current evidence grades

### VALIDATED / SETTLED

- PRIOR-first hierarchy.
- Dense active H grid: 1/2/3/4/5/10/15 then every 5s through 3600.
- Conditional birth cohorts and exact-depth counts.
- Per-occurrence causal second-level price-path rule.
- Price availability is infrastructure, never a predictive feature.
- Characteristics wall and chronology.
- Preserve-all / FLAG_AND_DECOMPOSE discipline.

### AVAILABILITY-ONLY FINDINGS

- Large pre-birth causal windows exist for D1-D3 and several D4/D5 cases.
- H=1 availability counts and lead distributions documented above.

### FAILED / NON-FINDINGS

- D2 H=1 polarity-only clue fails the required 2-of-3 validation gate and is not a birth-prediction finding.

### PENDING

- Earliest V2 PRIOR H for D1.
- Earliest V2 PRIOR H for D2.
- Earliest V2 PRIOR H for D3.
- D4/D5 individual price-path/timing case results.
- Exact-signal-time trade economics and strategy proposals after validated timing is known.

No protected component was modified and no play was promoted.
