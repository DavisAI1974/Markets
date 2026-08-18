# NG Exhaustion Exact-D1 Current Protocol — 2026-08-18

Status: **AUTHORITATIVE CURRENT TRUTH FOR THE EXACT-D1 / SINGLE-LINK CAMPAIGN.**

This file reconciles the original D1 contract with the later user-authorized corrections and additions. Read these together, in this order:

1. `research/NG_EXHAUSTION_EXACT_D1_AGENT_CONTRACT_20260818.md` — original scope and protected boundaries.
2. `research/NG_EXHAUSTION_EXACT_D1_PROTOCOL_CORRECTION_20260818.md` — authoritative D1 chronology correction.
3. `research/NG_EXHAUSTION_EXACT_D1_PRESERVE_ALL_ADDENDUM_20260818.md` — authoritative preserve-all/profitability interpretation.
4. This file — current reconciled operating rule, including reverse-backcast and fallback late-entry survivorship.

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

## Entry hierarchy: early entry first, late entry only as fallback

Late-entry survivorship is **not** a universal delay rule. It applies only to D1s or D1 subfamilies that are not reliably actionable at the earliest validated causal entry.

For each D1 type, research must follow this hierarchy:

1. **Primary early-entry path.** If the D1 setup can already be identified with sufficient causal reliability and positive net expectancy at the normal earliest decision point, retain that early entry. Do not delay a profitable predictable trade merely to wait for survival confirmation.
2. **Fallback survivorship path.** If the D1 is not adequately predictable/actionable at the earliest point, test whether survival itself makes the remaining opportunity predictable at progressively later checkpoints.
3. **No forced entry.** If neither early nor later causal checkpoints establish adequate remaining edge, preserve the D1 in the ledger as research evidence without manufacturing a trade rule.

The goal of fallback survivorship is to **rescue opportunities that cannot be predicted well enough at birth**, not to reduce the profitability of D1s that are already callable early.

## Fallback late-entry / survivorship checkpoints

For D1s that require fallback entry, two clocks must be kept separate:

1. `DETECTOR_KNOWN` clock — starts when the frozen detector has causally confirmed the origin event. This permits the earliest possible D1-survival research using only information available by that moment.
2. `FULL_STATE_KNOWN` clock — starts when the origin's required h=60 information wall is available. This permits state/grammar-conditioned research that requires the frozen post-event state.

The first fallback survivorship checkpoint is **+5 seconds** after the applicable causal clock. Required checkpoints are at least:

`+5, +10, +15, +20, +30, +45, +60, +90, +120, +180, +300, +600, +900, +1800, +3600 seconds`, with additional longer landmarks where support exists.

At every fallback checkpoint, retain all surviving D1s and report:

- count and fraction still alive;
- empirical remaining-time distribution;
- probability of surviving another 5/10/30/60/120/300/600 seconds where support permits;
- expected/median remaining runway;
- duration-family and origin-context mix as annotations;
- raw path available from checkpoint onward;
- directional vs chop/rotation behavior from checkpoint onward;
- MFE/MAE and realized gross/net opportunity from entering at that checkpoint;
- whether checkpoint-known information can now predict which surviving D1s have enough runway/edge left.

A D1 that is unpredictable at origin but becomes predictable at +5s, +10s, +30s, +2m, +5m, or later remains a valid candidate. The only execution requirement for fallback entry is that the signal at that checkpoint be causal and that sufficient expected remaining runway/edge remain after costs.

Realized survival age, realized duration family, and realized path shape may not leak future information into an earlier checkpoint. At checkpoint `t`, the model may use only information available by `t` plus the causal fact that no descendant has arrived yet.

## Profitability rule

All D1s remain eligible research evidence. Rankings may identify more-profitable and less-profitable D1 subfamilies and entry ages, but ranking never deletes or suppresses the lower-ranked population.

For each D1 subfamily, profitability reporting must distinguish **earliest validated entry** from any **fallback late-entry alternatives**. The preferred strategy is the earliest causal entry that has adequate validated predictability and net expectancy; later checkpoints are alternatives only when the earlier entry is not sufficiently predictable/actionable.

The common endpoint+5 to endpoint+60 descendant reference trade is only one profitability annotation. It does **not** measure the entire origin-to-descendant D1 leg. Full-leg, fallback late-entry, and chop/rotation profitability require raw-tape paths and causal checkpoint-specific entry logic.

The objective is **rank all D1s by repeatable net opportunity while preserving the complete population, and use fallback survivorship only to recover D1s that cannot be called early enough.**

## Protected boundaries

Do not modify the frozen detector, canonical base/held rows, Phase-1/Phase-2 scores/findings, frozen runway clock, permanent Frankie, Frankie 1, `research/kalshi/spawn.py`, or the frozen SSOS paper play. No permanent brain merge and no new play freeze without explicit authorization and a fresh prospective/OOT promotion contract.

Current corrected runner: `research/ng_exhaustion_exact_d1_agents_v2_20260818.py`.
Current preserve-all ledger builder: `research/ng_exhaustion_exact_d1_master_ledger_20260818.py`.
Current ten-lane workflow: `.github/workflows/ng_exhaustion_exact_d1_parallel_v2_20260818.yml`.
