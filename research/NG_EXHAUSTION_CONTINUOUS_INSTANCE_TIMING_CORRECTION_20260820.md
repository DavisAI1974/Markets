# NG Exhaustion Continuous Per-Instance Timing Correction — 2026-08-20

Status: **AUTHORITATIVE TIMING CORRECTION FOR THE CURRENT RECOVERY LINE.**

This supersedes any interpretation that preselects a finite set of PRIOR ages, `T0`, or H values and then asks which fixed bucket wins.

## Core rule

Timing is an **output**, not a predeclared input grid.

For each eligible historical instance, the model is allowed to observe the causal stream as it progresses. It scores the instance continuously at the frozen one-second research resolution. The research then reports the first and first-durable prediction times for that individual instance.

Only after the prediction trajectory is produced is its timestamp aligned to the frozen target birth `t0` for reporting:

- decision time `< t0` -> report `PRIOR` with exact `t0 - decision_time` seconds of lead;
- decision time `== t0` -> report `T0`;
- decision time `> t0` -> report `H+N` where `N = decision_time - t0`.

No list such as PRIOR `0..5`, H `+1..+5`, or a later hand-selected timing grid may define the answer.

## What the model may see

The primary continuous timing surface uses only information actually represented as causal at the scoring second:

- all predecessor/root information already causally known;
- continuous raw price direction/path;
- continuous signed aggressor flow;
- continuous roll-20/dipole path;
- continuous book imbalance/path;
- causal session/clock context.

Frozen future target labels are never model inputs.

Critically, the primary continuous timing model does **not** receive `t0`, seconds-to-`t0`, PRIOR/H identity, realized target polarity, realized final depth, or future chain family as features. Frozen `t0` is used only after scoring to express the discovered decision timestamp as PRIOR/T0/H.

Because the exact upstream detector event-mark timestamp is not yet durably represented, target-event-relative features that require knowing the target `t0` are not part of the primary continuous timing surface. They may remain secondary/oracle ablations until the real event-mark clock is proven.

## Natural trajectory boundaries

No arbitrary timing horizon is imposed.

A trajectory begins when all predecessor events required for that stage are causally available under the represented predecessor-confirmation contract.

A trajectory ends at the next natural canonical stage boundary (the next canonical event after the candidate target) or at the authoritative week/tape boundary when no later canonical event exists. These boundaries define what historical causal state exists; they are not predictive features.

D0 uses the same candidate-event structure for research, but any post-candidate time is reported as candidate-relative timing rather than pretending an exact-D0 terminal case had a true descendant H clock.

## Per-instance outputs

For every OOT instance preserve at minimum:

- full true label;
- first second the model argmax equals the eventual truth;
- first second from which the model remains correct through the natural trajectory boundary (`first_durable_correct`);
- exact absolute decision second;
- exact birth-relative reporting coordinate (PRIOR N / T0 / H+N, or D0 candidate-relative equivalent);
- model confidence at those times;
- prediction flips / last flip;
- unresolved/never-correct/never-durable cases.

These are research characterizations. `first_correct` and `first_durable_correct` use the revealed outcome only to score the already-produced model trajectory; the truth is never supplied as a feature or live stop condition.

## Training / validation

Models remain independent. No 2-of-3 vote is allowed.

The temporal training bank must not be built from hard-coded PRIOR/H timestamps. Training snapshots are selected inside each instance's natural causal trajectory by deterministic, timing-agnostic sampling for computational tractability. Sampling caps are compute controls, not timing hypotheses.

Hyperparameters are frozen from discovery data. OOT validation remains chronological. A model's per-instance timing characterization is authoritative only if the underlying continuous trajectory model demonstrates OOT improvement over its chronological null/baseline; majority-class correctness alone is not evidence of timing information.

Preserve class-specific timing distributions so the large D0/stop population cannot hide poor recognition of D1+ continuation cases.

## Relationship to the previous T0/fixed-grid work

The explicit T0 checkpoint remains a useful semantic correction and comparison point, but it is no longer the authoritative search architecture. The fixed-grid V1/V2/V3/T0 passes remain audit/comparison evidence only.

The authoritative hierarchy is now generated per instance by continuous causal scoring. PRIOR/T0/H are labels applied after the fact to the model's discovered timestamp, not bins chosen in advance.

## Protected boundaries

Do not modify or retune the frozen detector, canonical rows, Phase-1 lineage/scores, finalized Phase-2 findings, frozen runway clock, permanent Frankie, Frankie 1, `research/kalshi/spawn.py`, or the frozen SSOS play.

No permanent brain merge or live-play promotion is authorized.

`FLAG_AND_DECOMPOSE_NOT_AUTO_KILL` remains in force.
