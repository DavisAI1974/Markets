# ChatGPT Kickoff — NG Exhaustion Chain-Birth V2 — 2026-08-19

Status: **AUTHORITATIVE NEW-CHAT CHECKPOINT. CURRENT BRANCH STATE IS TRUTH. PRIOR BIRTH PREDICTION IS PRIMARY. V2 PRICE STRUCTURE IS PER OCCURRENCE AND ONE-SECOND CAUSAL. ALL CURRENT FINDINGS AND PROPOSAL LAYERS ARE DURABLE.**

## Takeover instruction

Take over the NG exhaustion entry-timing revival on branch:

`chatgpt/ng-exhaustion-entry-timing-revival-20260818`

Use the current branch state as truth. Do not restart Phase 1, do not reopen Phase 2, do not retune the frozen detector/runway clock, and do not use the prior-chat signed-direction drift to redefine this program.

The immediate task is to finish the **D1-D5 chain-birth V2 predictability study** and then turn validated birth timing into trade-strategy research.

## Mandatory read order

Read these first, in order:

1. `CHATGPT_KICKOFF_NG_EXHAUSTION_CHAIN_BIRTH_V2_20260819.md` — this checkpoint.
2. `research/NG_EXHAUSTION_CHAIN_BIRTH_V2_ALL_FINDINGS_20260819.md` — authoritative current findings/non-findings/pending boundary. Do not invent results beyond this record unless durable V2 outputs exist.
3. `research/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_PREDICTABILITY_PROTOCOL_20260819.md` — authoritative primary target and PRIOR-first hierarchy.
4. `research/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_PRICE_STRUCTURE_ADDENDUM_20260819.md` — authoritative per-occurrence second-level price rule.
5. `research/NG_EXHAUSTION_D1_D5_PREDICTABILITY_TIMING_GRID_20260819.md` — dense H grid.
6. `research/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_PRIOR_AVAILABILITY_20260819.md` — canonical PRIOR availability only; not predictive skill.
7. `research/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_AGENTS_V2_LAUNCH_20260819.json` — active V2 launch contract.
8. `research/ng_exhaustion_d1_d5_chain_birth_agents_v2_20260819.py` — active V2 price-path wrapper.
9. `research/ng_exhaustion_d1_d5_chain_birth_agents_20260819.py` — base birth classifier and validation gates.
10. `.github/workflows/ng_exhaustion_d1_d5_chain_birth_agents_v2_20260819.yml` — active four-agent V2 workflow and reconciliation.
11. `research/kalshi/knowledge/ng_brain_exhaustion_chain_birth_v2_proposal_20260819.json` — current proposal-only Chain-Birth V2 lesson layer; do not merge into Frankie.
12. `research/NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_20260818.md` — authoritative four-layer proposal lineage and merge policy.
13. `research/NG_EXHAUSTION_CHAIN_PHASE1_CAUSAL_PROTOCOL_20260817.json` — frozen characteristics wall and paired causal discipline.
14. `research/NG_EXHAUSTION_CHAIN_PHASE2_FINAL_FREEZE_20260818.md` and `research/NG_EXHAUSTION_CHAIN_PHASE2_ALL_AGENT_FINDINGS_20260818.md` — settled Phase-2 truth; read, do not relitigate.

Use older entry-timing/D1 docs only for provenance or specific secondary lanes after the above current contract is understood.

## Primary research question

For each stage D1 through D5:

**At what earliest causal point can we predict that the next chain stage is going to begin?**

The preferred result is always **PRIOR**, before the frozen target `t0`.

The detector-relative clock is fallback only.

## Search hierarchy — do not change

For every D1-D5 stage, rule, motif, or subfamily:

1. **Exhaust PRIOR first.**
2. Test active predecessor-information H values in ascending order:

   `H = 1,2,3,4,5,10,15,20,25,30,35,...,3600 seconds`

3. A PRIOR H is eligible only when all required predecessor information is causal before target onset:

   `RULE_READY(D,H) = max(predecessor causal_confirmation_idx + H)`

   and

   `RULE_READY(D,H) <= target.t0_idx`

4. Record actual lead:

   `PRIOR_LEAD_SECONDS = target.t0_idx - RULE_READY(D,H)`

5. **Earliest validated PRIOR wins.** Do not delay it for a cleaner later signal.
6. Only when PRIOR fails for that rule/subfamily, test fallback:

   `+0 detector confirmation -> +1 -> +2 -> +3 -> +4 -> +5 -> +10 -> +15 -> +20 -> +25 -> ... every 5s through +3600`

7. `+0` and post-detection results are fallback recognition, not prediction of birth.

## Conditional chain-birth cohorts

Condition on the chain having reached D-1, then ask whether it extends to D.

Frozen forward-OOT + held populations used by the V2 run:

| Stage | Birth positive | Stop/control | Censored |
|---|---:|---:|---:|
| D1 | depth >=1: 20,562 | executable exact-D0: 135,823 | 37 week-end target-unavailable |
| D2 | depth >=2: 1,725 | exact-D1: 18,837 | 0 |
| D3 | depth >=3: 133 | exact-D2: 1,592 | 0 |
| D4 | depth >=4: 9 | exact-D3: 124 | 0 |
| D5 | depth >=5: 1 | exact-D4: 8 | 0 |

Original exact-depth populations remain preserved:

- D0 = 135,860
- D1 = 18,837
- D2 = 1,592
- D3 = 124
- D4 = 8
- D5 = 1

The first 18 base weeks remain outside forward-OOT exact-D1/birth-validation credit unless the separately predeclared reverse-backcast study validates. Do not manufacture labels for them.

## Per-occurrence price structure — V2 correction

Every predecessor exhaustion occurrence carries its **own separate causal price path**.

- D1: one predecessor price path.
- D2: two separate ordered predecessor price paths.
- D3: three.
- D4: four.
- D5: five.

Do not average or pool them into one generic chain path.

For occurrence detector confirmation `c`:

- baseline = last authoritative trade known at or before `c`;
- second `s` = last authoritative trade known at or before `c+s`;
- at H, the model sees all integer-second price values from `1..H`, aligned to occurrence polarity and expressed relative to the causal baseline;
- no future interpolation;
- if no new trade occurs during a second, carry forward the last already-known price;
- no price after `c+H` may enter the H snapshot.

Implementation stores one signed cumulative price value per second. Adjacent differences fully recover the one-second changes.

At H=15, a D3 input therefore contains three separate 15-second price paths, not one summary statistic.

## Price availability is NOT a predictive gate

The authoritative raw NG tape is infrastructure.

The V2 workflow downloads and verifies raw NG tape for every agent lane, including D4/D5.

If required raw tape or a causal baseline is missing, **fail closed as data-integrity failure**.

Once tape integrity passes:

- do not include `price_structure_available` as a model feature;
- do not let missingness distinguish births from stops;
- do not silently drop a row because price data are inconvenient;
- all model-eligible positive and control rows receive the same price-structure treatment.

## Active V2 agents

Four parallel lanes:

1. D1 birth agent
2. D2 birth agent
3. D3 birth agent
4. combined low-support D4/D5 case-study agent

Reconciliation runs only after all four complete.

Active workflow:

`.github/workflows/ng_exhaustion_d1_d5_chain_birth_agents_v2_20260819.yml`

Active launch marker:

`research/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_AGENTS_V2_LAUNCH_20260819.json`

Launch-marker commit:

`1afbb329fe4b5cf93778b9466664b8807667f6e4`

## Expected durable V2 outputs

When the V2 workflow completes, expect:

`research/generated/ng_exhaustion_entry_timing_revival_20260819/d1_d5_chain_birth_agents_v2/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_V2_ALL_AGENT_RESULTS_20260819.json`

and

`research/generated/ng_exhaustion_entry_timing_revival_20260819/d1_d5_chain_birth_agents_v2/NG_EXHAUSTION_D1_D5_CHAIN_BIRTH_V2_ALL_AGENT_FINDINGS_20260819.md`

D4/D5 also preserve compressed per-occurrence sparse price paths in companion `jsonl.gz` artifacts.

If those reconciled files are not present on takeover, do not invent results. Inspect the V2 workflow/branch state and continue from there.

## Validation gate — D1-D3

Birth prediction must survive chronological/OOT validation, not merely separate in-sample.

The active base runner uses:

- models: logistic, extra trees, distance-weighted KNN;
- discovery fit: eras 1-2;
- discovery tune: era 3;
- validation: eras 4-5;
- untouched confirmation: final block;
- held: insert-only, no retuning;
- 2-of-3 model gate for validation;
- positive log-loss gain vs discovery-frozen null;
- positive Brier gain vs null;
- ROC AUC > 0.5;
- positive-week Brier stability >= 0.5;
- support floors by D;
- held must not contradict when held support is sufficient.

Report absolute birth-prediction skill separately from incremental D-vs-D-1 history gain.

D4/D5 are low-support preserved cases only. Do not force population laws.

## Characteristics wall — frozen

PRIOR prediction may not use:

- target identity/polarity/family/state before birth;
- predecessor `next_same_polarity` or any field that reveals the not-yet-born target;
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
- confirmation lag/timing as a model characteristic.

Timing is allowed only to establish causal availability and report actual lead.

## Completed availability fact — not skill

The canonical PRIOR availability audit showed meaningful pre-birth runway. At H=1, pre-birth information is available for:

- 13,372 D1 births;
- 1,171 D2 births;
- 88 D3 births;
- 7/9 D4 births;
- 1/1 D5 birth.

These are availability counts only. They do not prove predictive skill.

A quick lower-bound polarity-only D2 H=1 probe showed a small structural clue, but **it failed the real 2-of-3 validation gate**: extra trees passed while logistic and KNN did not. Treat that as a non-finding/clue only. Do not claim D2 is predictable at H=1 unless the active V2 price-path run validates it.

## Durable findings and proposal boundary

The complete current evidence grading is in:

`research/NG_EXHAUSTION_CHAIN_BIRTH_V2_ALL_FINDINGS_20260819.md`

The new proposal-only brain layer is:

`research/kalshi/knowledge/ng_brain_exhaustion_chain_birth_v2_proposal_20260819.json`

The authoritative proposal lineage/index is:

`research/NG_EXHAUSTION_BRAIN_PROPOSAL_INDEX_20260818.md`

Important:

- the Chain-Birth V2 proposal is a **fourth layer** that extends runway, Phase-2 chain, and entry-timing proposals;
- it replaces none of them;
- the permanent brain is unchanged;
- any future permanent merge must adjudicate all four layers together;
- failed/non-validating clues must travel with positive lessons;
- V2 predictive H results remain pending until durable reconciled outputs exist.

## Trade-strategy program after birth timing

The purpose of this research is executable trading.

For every validated PRIOR birth signal:

1. use the **exact causal PRIOR signal timestamp** as the candidate entry clock;
2. attach the already-preserved direction/behavior work to determine what the predicted birth tends to do;
3. reconstruct raw price economics from that exact signal time forward;
4. measure remaining runway, entry fill, MFE, MAE, net displacement, path efficiency, chop/rotation, and costs;
5. develop candidate entry/sizing/exit/management rules;
6. validate strategies chronologically/OOT and held without retuning;
7. keep directional and chop/rotation strategies separate where appropriate.

For rules/subfamilies with no validated PRIOR birth signal, use the earliest validated fallback recognition point and label it clearly as fallback.

Do not force every chain into one strategy. Different D depths, motifs, timing families, and price structures may require different plays.

## Secondary full-behavior target

The frozen full behavior vector — next same/flip plus displacement/MFE/MAE at 5/10/20/30/60/120/300 — remains useful **after birth timing is established** to answer what happens after a stage begins.

It is secondary. It may not replace chain-birth prediction or be used to claim pre-birth timing.

The earlier 20260819 full-behavior predictability agent/workflow is superseded as the primary timing target. Preserve it only as secondary/context work.

Likewise, the first chain-birth workflow without the V2 per-second-per-occurrence price correction is superseded by V2 for primary results.

## Protected boundaries

Do not modify or retune:

- frozen exhaustion detector;
- canonical base/held rows;
- frozen Phase-1 lineage/scores;
- finalized Phase-2 findings/freeze;
- frozen exhaustion runway clock;
- permanent Frankie;
- Frankie 1;
- `research/kalshi/spawn.py`;
- frozen SSOS paper play.

Do not merge a proposal into permanent Frankie and do not freeze a historical trade play without a fresh prospective/OOT promotion contract.

## Finalization commits added at this checkpoint

- All-findings record: `66460334d5a583bcb5efa6b111ba9978ac90a684`
- Chain-Birth V2 proposal layer: `d2ff94963505cf82eeefc78f078a798a54837791`
- Four-layer proposal index update: `43f45d8830bd8556cb96c66d5ef8558d3b236c3e`

## Immediate next step in the new chat

1. Read the mandatory order above.
2. Inspect whether the V2 reconciled output files have landed.
3. If yes, audit their invariants against the all-findings record and report the earliest validated PRIOR birth H for D1-D3 plus preserved D4/D5 case timing; then update the findings/proposal layer with actual validated results and begin exact-signal-time trade economics/strategy work.
4. If no, inspect the V2 workflow status/branch state and finish the V2 run without changing the contract.
5. Preserve every failure and control case under `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.
6. Do not redo the work recorded here.
