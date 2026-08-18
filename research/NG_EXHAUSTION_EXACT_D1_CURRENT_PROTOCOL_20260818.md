# NG Exhaustion Exact-D1 Current Protocol — 2026-08-18

Status: **AUTHORITATIVE CURRENT TRUTH FOR THE EXACT-D1 / SINGLE-LINK CAMPAIGN.**

This file reconciles the original D1 contract with the later user-authorized corrections and additions. Read these together, in this order:

1. `research/NG_EXHAUSTION_EXACT_D1_AGENT_CONTRACT_20260818.md` — original scope and protected boundaries.
2. `research/NG_EXHAUSTION_EXACT_D1_PROTOCOL_CORRECTION_20260818.md` — authoritative D1 chronology correction.
3. `research/NG_EXHAUSTION_EXACT_D1_PRESERVE_ALL_ADDENDUM_20260818.md` — authoritative preserve-all/profitability interpretation.
4. This file — current reconciled operating rule, including reverse-backcast and late-entry survivorship.

## Current D1 population rule

A valid forward exact D1 is an instance with `all_model_consecutive_positive_depth == 1` in the frozen Phase-1 lineage. **Every such instance is retained.**

No D1 is discarded because it is short, long, extreme-tail, directional, choppy, lower-return, negative under one reference horizon, rare, low-support, or a true/false investigator case. Profitability is a ranking/annotation dimension only.

The campaign's purpose is to learn **how profitable each D1 type is and how that profitability varies with time length, causal runway, grammar, ancestry, path shape, regime, and entry age**, not to define D1 membership by profit.

## Correct forward D1 chronology

- Base weeks 0–17: `PRELINEAGE_UNLABELED` under the original forward Phase-1 lineage because those weeks train the first fold.
- Base weeks 18–35: D1 discovery/fitting block; first 18 genuinely forward-OOT lineage-labeled weeks.
- Base weeks 36–47: D1 validation.
- Base weeks 48–53: untouched historical D1 confirmation.
- Held `20260329`: insert-only held validation.

Machine outputs may use internal `train` for base weeks 18–35 solely for compatibility with the existing lane code. In D1 research, that means **D1_DISCOVERY_OOT**, not Phase-1 training.

## Reverse-backcast recovery of base weeks 0–17

The first 18 weeks are not discarded. They receive a separate reverse-time study.

A reverse/backcast D1 labeler must be developed only from later weeks that already have frozen forward-OOT D1 labels. The labeler is fit on the earlier portion of the labeled later cohort, validated on still-later labeled weeks, confirmed on the untouched final six base weeks and held insert where applicable, and only then frozen and applied backward to base weeks 0–17.

Backcast rows must carry a permanent provenance tag such as `REVERSE_BACKCAST_NOT_FORWARD_OOT`. They may join the descriptive/profitability ledger as a separate cohort after the backcast rule validates, but they may never be counted as forward-OOT confirmation evidence and may never rewrite the frozen Phase-1 lineage.

The preferred backcast target is exact-D1 membership itself, not realized profitability. Profitability and duration are analyzed only after the backcast membership rule is frozen.

## Preserve-all ledger requirement

The master ledger is mandatory and must contain every valid forward exact D1 and, when validated, every reverse-backcast D1 as a separately tagged cohort, with where available:

- immutable origin/descendant IDs and sequence indices;
- exact elapsed origin-to-descendant seconds;
- duration-family annotation;
- causal remaining runway from each permitted entry clock;
- local pair/state/polarity grammar;
- older causal ancestry;
- origin family/A-poststate;
- common reference returns and cost stresses in both orientations;
- MFE/MAE;
- descendant re-origin information where comparable;
- raw-path `DIRECTIONAL` / `CHOP_ROTATION` annotation and raw path statistics once reconstructed.

Grouped support thresholds grade confidence only. `LOW_SUPPORT` and `VERY_LOW_SUPPORT_PRESERVED` groups remain in the ledger.

## Late-entry / survivorship protocol

Do **not** require a D1 to be predicted as long at birth. A D1 may become a valid opportunity after it has already survived for some time, provided enough expected remaining runway and edge remain to enter.

Two clocks must be kept separate:

1. `DETECTOR_KNOWN` clock — starts when the frozen detector has causally confirmed the origin event. This permits the earliest possible D1-survival research using only information available by that moment.
2. `FULL_STATE_KNOWN` clock — starts when the origin's required h=60 information wall is available. This permits state/grammar-conditioned research that requires the frozen post-event state.

The first survivorship checkpoint is **+5 seconds** after the applicable causal clock. Required checkpoints are at least:

`+5, +10, +15, +20, +30, +45, +60, +90, +120, +180, +300, +600, +900, +1800, +3600 seconds`, with additional longer landmarks where support exists.

At every checkpoint, retain all D1s and report:

- count and fraction still alive;
- empirical remaining-time distribution;
- probability of surviving another 5/10/30/60/120/300/600 seconds where support permits;
- expected/median remaining runway;
- duration-family and origin-context mix as annotations;
- raw path available from checkpoint onward;
- directional vs chop/rotation behavior from checkpoint onward;
- MFE/MAE and realized gross/net opportunity from entering at that checkpoint;
- whether an origin-known/checkpoint-known model can predict which surviving D1s have enough runway/edge left.

A D1 that is unpredictable at origin but becomes predictable at +5s, +10s, +30s, +2m, +5m, or later remains a valid candidate. **Late entry is explicitly allowed.** The only execution requirement is that the signal at that checkpoint be causal and that sufficient expected remaining runway/edge remain after costs.

Realized survival age, realized duration family, and realized path shape may not leak future information into an earlier checkpoint. At checkpoint `t`, the model may use only information available by `t` plus the causal fact that no descendant has arrived yet.

## Profitability rule

All D1s remain eligible research evidence. Rankings may identify more-profitable and less-profitable D1 subfamilies and entry ages, but ranking never deletes or suppresses the lower-ranked population.

The common endpoint+5 to endpoint+60 descendant reference trade is only one profitability annotation. It does **not** measure the entire origin-to-descendant D1 leg. Full-leg, late-entry, and chop/rotation profitability require raw-tape paths and causal checkpoint-specific entry logic.

The objective is therefore not `find profitable D1s vs unprofitable D1s`; it is **rank all D1s and all causally valid entry ages by repeatable net opportunity while preserving the entire population.**

## Protected boundaries

Do not modify the frozen detector, canonical base/held rows, Phase-1/Phase-2 scores/findings, frozen runway clock, permanent Frankie, Frankie 1, `research/kalshi/spawn.py`, or the frozen SSOS paper play. No permanent brain merge and no new play freeze without explicit authorization and a fresh prospective/OOT promotion contract.

Current corrected runner: `research/ng_exhaustion_exact_d1_agents_v2_20260818.py`.
Current preserve-all ledger builder: `research/ng_exhaustion_exact_d1_master_ledger_20260818.py`.
Current ten-lane workflow: `.github/workflows/ng_exhaustion_exact_d1_parallel_v2_20260818.yml`.
