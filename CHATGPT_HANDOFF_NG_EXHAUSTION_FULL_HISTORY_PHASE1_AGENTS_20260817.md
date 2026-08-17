# ChatGPT Handoff — NG Exhaustion Full-History Phase 1 Agent Campaign — 2026-08-17

## Status

This handoff supersedes any earlier plan to move into Phase 2 after the three-week pilot.

**Phase 2 is LOCKED.** The next chat must finish Phase 1 across the full historical NG corpus before any chain characterization, naming, time-of-day profiling, family profiling, flow/book profiling, or permanent Frankie learning.

Current source branch at handoff construction:

- `chatgpt/ng-exhaustion-aftermath-20260817`
- coverage freeze commit: `a3d9251c08653d09cfc2feb14a9ed83c4fb18a3f`

The next working branch will be:

- `chatgpt/ng-exhaustion-chain-full-history-phase1-20260817`

## Read first, in this order

1. `CHATGPT_HANDOFF_NG_EXHAUSTION_FULL_HISTORY_PHASE1_AGENTS_20260817.md`
2. `research/NG_EXHAUSTION_FULL_HISTORY_COVERAGE_FREEZE_20260817.json`
3. `research/NG_EXHAUSTION_CHAIN_FULL_HISTORY_PHASE1_GATE_20260817.json`
4. `research/NG_EXHAUSTION_CHAIN_STUDY_CONTRACT_20260817.json`
5. `research/NG_EXHAUSTION_CHAIN_PHASE1_DISCOVERY_PROTOCOL_20260817.json`
6. `research/NG_EXHAUSTION_CHAIN_PHASE1_MECHANISM_ADDENDUM_20260817.json`
7. `research/NG_EXHAUSTION_CHAIN_PHASE1_CAUSAL_PROTOCOL_20260817.json`
8. `research/ng_exhaustion_chain_canonical_table_20260817.py`
9. `research/ng_exhaustion_chain_phase1_discovery_20260817.py`
10. `research/ng_exhaustion_chain_phase1_causal_20260817.py`
11. Only then consult older aftermath/reveal/runway files for provenance when needed.

Current repo state is truth. Do not redo the runway clock or the blind exhaustion experiment.

## Historical corpus is now complete

Authoritative raw source:

`s3://bento-568968024170-us-east-2-an/nymex/nymex_cont/NG_*`

Post-repair inventory:

- workflow run: `32005944876`
- artifact: `9280008162`
- artifact digest: `sha256:f943b59f27c2e3e2d03fcb43870a16f0248b1eeeb78899a49ae5718472cd1734`
- 329 unique NG raw UTC dates
- first raw date: `2025-06-29`
- last raw date: `2026-07-17`
- **55 trading weeks touched**
- **55/55 usable complete Sunday→Friday weeks**
- zero repair-required weeks after repair
- zero duplicate raw dates

The previously missing opening Sunday reopen was repaired:

- week: Sunday `2025-06-29`
- exact series: `NG.v.0`
- schema: `mbp-10`
- S3 key: `nymex/nymex_cont/NG_20250629_sun.jsonl.gz`
- repair workflow: `32005876639`
- repair artifact: `9279991016`
- repair artifact digest: `sha256:5c9e0145fcc1095d7a218e4cdafb4c5ecac6f0552a3b5d54c0d99d90cb0a6e9d`
- estimated Databento cost: `$0.003881208599`, below hard `$0.01` ceiling
- 22,649 MBP-10 rows, 1,618 trade rows
- gzip SHA-256: `a0056f22adbafb91c18b91535e47a6de701f08e74cfff2022a91b0d8f60b9f64`
- first Sunday trade: `2025-06-29T22:00:00Z`
- upload length verified

Do not silently exclude any of the 55 weeks.

## Weekly chain semantics — immutable

A chain observation stream starts at the **first actual NG trade after the Sunday weekly reopen** and continues to the **last actual NG trade before the genuine weekly close**.

The following are NOT resets:

- calendar midnight
- HE24→HE1
- UTC source-file boundary
- date-label boundary
- ordinary session/day boundary

Holiday/special-session handling follows actual observed trading timestamps and real closure/reopen behavior. Never invent a reset from the clock or calendar.

Time-of-day must eventually be logged for every chain/link, but it is **not a Phase-1 gate or chain-definition feature**.

## What the three-week pilot established — pilot only, not final history

The strict canonical pilot used three complete weeks:

- `2025-07-13`
- `2025-09-21`
- `2025-09-28`

Canonical pilot table:

- 12,991 exhaustion events total
- 4,313 / 4,378 / 4,300 events by week
- all 3,429 frozen reveal+holdout target events recovered
- zero family mismatches
- zero blind-A frozen post-state mismatches
- calendar-day chain reset = false
- real cross-UTC-date links were observed

The pilot event density is roughly 4,300 exhaustion events per trading week. That is event density, not a claim that there are 4,300 separate chains.

### Retrospective structural pilot

Formal Phase-1 structural run:

- workflow: `32004586223`
- artifact: `9279678072`
- artifact digest: `sha256:b5a17b8ec70117c4a6e402cc829ed9a39bd770c487246ab7bfc68bbf57d8e207`
- behavior-only full-path vector: next exhaustion same/flip + signed displacement/MFE/MAE at 5/10/20/30/60/120/300s
- characteristics were not accessed

Pilot result under the preregistered interpretation:

- D=1 prior-after\-math depth is strongly positive across all three weeks and all three model families.
- D=2 is a **mixed/conditional higher-order candidate**: ridge and extra-trees are positive on all three weeks; KNN is negative on all three weeks.
- D>=3 does not replicate in this small pilot under the full-path test.
- same-origin cross-depth enrichment is approximately neutral; no statistically convincing inherited-origin enrichment appears in the pilot.

Interpretation rule frozen **before formal results were read**:

- replicated higher-order population memory is a first-class chain mechanism even without same-origin persistence;
- lack of origin persistence means **rolling/re-origin chain behavior**, not “no chain”;
- positive same-origin enrichment would identify inherited-origin chains;
- mixed evidence stays a candidate instead of being erased.

These are pilot findings only. The 55-week Phase-1 campaign determines the historical answer.

### Causal-executable pilot

A separate preregistered run tests what higher-order depth is actually available before each descendant event at information horizons 5/10/20/30/60/120/300 seconds. It complements rather than replaces the retrospective structural chain test.

Pilot workflow: `32004985328`.

At handoff construction it was still running. If complete when the next chat starts, read its artifact and freeze it as **pilot provenance only**. Do not let the pilot causal result substitute for the required 55-week rerun.

## Critical conceptual axes — preserve all possibilities

Phase 1 must preserve at least these independent axes rather than squeezing observations into predefined chain cells:

1. **Order depth:** how many preceding aftermaths add out-of-sample predictive information beyond shorter history?
2. **Origin persistence:** does the same original event continue adding unique information, or does the chain roll/re-origin at newer events?
3. **Executability:** is the higher-order behavior known by descendant t0, or only visible retrospectively after later aftermath has completed?
4. **Instance-specific lifespan:** some individual chains may die after one link while others may persist farther. Do not force one universal length.

Therefore valid eventual Phase-1 mechanisms include:

- single-step / one-link behavior
- rolling/re-origin higher-order chains
- inherited-origin higher-order chains
- structural-but-not-yet-executable chains
- causally executable chains
- mixed/conditional deeper-order candidates

Do not predefine “long,” “short,” “reversal,” “same-side,” “alternating,” family types, time buckets, or other characteristics as the chain categories. **Find the chains/depth first; characterize them later.**

## Mandatory next-chat agent fan-out

The next chat must use parallel agents for the full-history Phase-1 campaign after it verifies the shared immutable coverage/event semantics. Agents must not each invent their own detector, endpoint, week boundary, or chain definition.

Required lanes:

### Agent 1 — Corpus/continuity auditor

- verify all 55 Sunday→Friday weeks against `NG_EXHAUSTION_FULL_HISTORY_COVERAGE_FREEZE_20260817.json`;
- verify repaired 2025-06-29 provenance;
- flag special-session/holiday weeks;
- ensure no silent date/week omission;
- independently verify cross-midnight continuity invariants.

### Agent 2 — Full-history canonical event-table builder/equivalence auditor

- extend the canonical three-week table builder to all 55 weeks using the same detector semantics;
- preserve Sunday→Friday continuous ordering;
- maintain feature/outcome namespaces;
- reproduce the frozen three-week pilot event identities/families/post-states exactly where applicable;
- freeze the all-history event-table hash/schema before downstream agents score it.

### Agent 3 — Retrospective structural-depth analyst

- rerun behavior-only D=1..higher-order analysis across the full 55-week event table;
- determine depth from data, not a predetermined long/short cutoff;
- use trading-week-blocked temporal validation and strong out-of-time checks;
- preserve mixed/conditional depth when evidence differs by model/era.

### Agent 4 — Causal-executable depth analyst

- rerun executable higher-order analysis across full history;
- enforce causal availability at descendant t0;
- preserve results separately by information latency;
- report structural depth and executable depth as two axes, not competing answers.

### Agent 5 — Origin-persistence / chain-lineage analyst

- determine whether deeper memory is carried by the same original event or rolls/re-origins through newer events;
- measure instance-specific chain survival/lifespan without imposing a cutoff;
- preserve both inherited-origin and rolling chains if both occur.

### Agent 6 — Independent falsifier

- attack leakage, sample-selection, threshold artifacts, temporal nonstationarity, single-era dependence, and model-family dependence;
- use null/permutation/placebo tests that preserve weekly/session structure where appropriate;
- specifically test whether apparent deeper-order memory is merely omitted current-state information;
- fail closed on any provenance/continuity violation.

A coordinator must reconcile the agents only after the all-history canonical event table is frozen. No agent may modify permanent Frankie, the frozen runway clock, or the completed aftermath/blind artifacts.

## Validation expectations for 55-week campaign

Three-week leave-one-week-out is no longer sufficient. The next chat should design the full-history validation so training and testing remain temporally honest.

At minimum:

- block by whole trading week;
- use multiple out-of-time eras/folds rather than random event splits;
- report per-week/per-era stability, not pooled hit rates only;
- keep tuning inside training eras;
- retain a later untouched historical/forward segment where practical for final confirmation;
- quantify uncertainty and support at each depth;
- do not promote tiny rare sequences merely because 55 weeks allow many screens.

The full-history campaign must not use Phase-2 characteristics to choose Phase-1 boundaries.

## Phase 2 hard lock

Do NOT perform chain characterization yet.

Forbidden until full-history Phase 1 is complete/frozen:

- naming discovered chains by characteristics
- defining long/short cutoffs from family/flow/book/time/polarity
- searching time-of-day enrichment as a chain gate
- clustering chains using family/A-poststate/late-flow/book/session characteristics
- promoting chain lessons into permanent Frankie

After full-history Phase 1 freezes chain depth/lineage/executability, Phase 2 may characterize the already-frozen chains using polarity, family, exhaustion geometry, flow, book, tape aftermath, duration, time-of-day/session position, and other legal context.

## Do-not-touch boundary

Completed runway clock remains frozen at:

`chatgpt/ng-exhaustion-runway-clock-20260817 @ 637778d6f460940379ac0feaf8223be47971c11f`

Do not modify:

- `research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json`
- `research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json`
- frozen runway baselines in `research/ng_exhaustion_runway_clock.py`
- completed runway proof semantics
- permanent Frankie brain/schema/roles/plays/datapoints/workflow
- frozen reveal/blind artifacts

Nothing from this full-history chain campaign belongs in permanent Frankie until the complete validation/promotion process is deliberately reviewed.

## First action in the next chat

1. Read the handoff/read-order above.
2. Inspect the current branch and confirm `NG_EXHAUSTION_FULL_HISTORY_COVERAGE_FREEZE_20260817.json` says 55/55 complete weeks.
3. Verify the new full-history branch base.
4. **Immediately spin up the parallel Phase-1 agents described above.**
5. Coordinator freezes one shared full-history canonical event table before structural/causal/lineage agents are allowed to produce final scores.
6. Do not begin Phase 2.
