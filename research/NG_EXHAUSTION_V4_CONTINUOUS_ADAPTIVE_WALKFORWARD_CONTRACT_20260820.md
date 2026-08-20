# NG Exhaustion V4 Continuous Per-Instance Timing + Adaptive Walk-Forward Contract — 2026-08-20

Status: **RESEARCH CONTRACT; NO PERMANENT FRANKIE MUTATION OR PLAY PROMOTION.**

## Purpose

Replace predeclared PRIOR/H timing buckets with a causal trajectory experiment that discovers timing from each completed instance itself, then compare a frozen discovery model against an adaptive model that learns only from previously completed instances.

Primary questions remain independent:

1. chain / continuation;
2. eventual final depth;
3. P/O/S/X structural family/state.

Target polarity is not a primary target. SAME/FLIP remains secondary annotation/context only.

## Timing is an output

The primary model is never told:

- frozen target `t0`;
- seconds until target birth;
- PRIOR/H identity;
- target polarity;
- target P/O/S/X state;
- a countdown to the stage censor boundary.

It sees only causally available predecessor/root memory plus the continuously observed price/flow/dipole/book market movie and causal age since the latest represented predecessor became available.

Each OOT instance is scored at every causal second in its natural stage opportunity window. Once the model fires a frozen lock rule, that absolute decision timestamp is recorded. Only after the prediction path is frozen is the timestamp aligned to the frozen target birth:

- negative offset -> `N seconds PRIOR`;
- zero -> `T0`;
- positive offset on a true continuation -> `H+N`;
- stopped-chain controls use control-candidate-relative wording and never receive a synthetic H label.

D0 has no true descendant H clock and remains candidate-relative where necessary.

## Lock rule: learned on discovery, frozen before OOT

A historical instance must never be declared to have "locked" merely because the retrospective answer happened to be correct at that second.

The model produces a probability vector every second. Discovery selects a lock rule using only discovery data. A rule consists of:

- minimum winning-class probability;
- minimum winning-class margin over the runner-up;
- number of consecutive seconds for which the same winning class must satisfy both conditions.

The operational decision time is the current second when persistence has actually been observed. It is never backdated to the start of the persistence run.

Lock-rule selection must not optimize against target-relative PRIOR/H timing. It uses truth only on discovery to choose a trustworthy selective-prediction rule, balancing predictive log-score improvement versus a frozen discovery null, coverage, and causal latency from predecessor availability. `t0` is not part of that objective.

Validation, untouched confirmation and held instances use the frozen discovery rule. Correctness is scored only after the rule has fired.

## Frozen benchmark lane

The frozen benchmark:

1. learns from discovery data only;
2. freezes model state and lock rule before OOT;
3. scores every OOT instance causally;
4. never updates from validation, confirmation or held outcomes.

This lane answers whether the discovered relation generalizes without adaptation.

## Adaptive walk-forward lane

The adaptive lane starts as an exact twin of the frozen discovery model and uses the same frozen lock rule.

For each later instance:

1. create the model snapshot using only completed earlier instances whose outcome reveal time precedes the new instance start;
2. score the new instance causally and freeze its prediction/decision-time ledger;
3. do not revise any prior prediction;
4. when the completed instance becomes causally revealable, add timing-agnostic samples from that completed trajectory to the adaptive learner;
5. use the improved model only on later instance snapshots.

Overlapping cases are handled conservatively: an active instance keeps the model snapshot it had when it started. If another case resolves while it is active, that new information is not injected mid-instance in V4. This intentionally understates adaptation rather than introducing ambiguous overlap hindsight. A later research version may allow timestamp-level interleaving after this conservative baseline is proven.

## Outcome reveal timing

Adaptive training may occur only after the target truth is causally revealable.

Conservative reveal rules:

- continuation / D0 terminality: after the comparison target has accumulated its causally required structural state window;
- P/O/S/X family: no earlier than target `t0 + 60s`;
- eventual final depth: only after the frozen final chain member and the first subsequent non-chain comparison event have accumulated the required causal structural window; if no subsequent event exists, censor reveal at authoritative week tape end.

Where a later causal endpoint confirmation is required by a represented fact, use the later time. Never use the frozen label itself as if it were available earlier.

## What adaptation learns

A completed instance may update the adaptive predictive relationships using samples from the actual causal trajectory it produced. Sampling count is a compute budget only; sample timestamps are selected without reference to `t0`, PRIOR or H.

V4 freezes the lock rule while allowing model parameters to adapt. This cleanly isolates whether learning from completed experience improves the underlying predictive model. Adaptive calibration / lock-rule retuning can be tested later as a separate ablation rather than mixing both effects in the first adaptive result.

## Model policy

No cross-model vote or probability averaging.

The scalable continuous baseline may use an online probabilistic model as an explicitly separate model identity. Frozen and adaptive twins of the same online model provide the cleanest estimate of adaptation value because they share discovery initialization and differ only by causal post-discovery learning.

Other frozen independent models may be added as separate lanes. KNN may remain a sampled diagnostic if full second-by-second corpus scoring is computationally pathological; it must never be silently treated as equivalent to a full-trajectory lane.

## OOT chronology

The adaptive replay follows actual chronological case-start order across validation, confirmation and held weeks rather than pretending the held insert occurred after all validation data. A traditional untouched-held score remains available only from the frozen lane. Adaptive held performance is an operational causal walk-forward result, not a conventional untouched holdout.

## Required durable outputs

For every stage / target / model lane preserve:

- frozen discovery model identity and lock rule;
- per-instance frozen prediction, confidence, decision timestamp, truth and posthoc PRIOR/T0/H coordinate;
- per-instance adaptive prediction, confidence, decision timestamp, truth and posthoc coordinate;
- no-lock / censored cases;
- adaptive training-update count available before each instance;
- target-specific conservative truth reveal timestamp;
- validation / confirmation / held summaries;
- paired frozen-versus-adaptive timing and correctness deltas;
- all wrong locks, late locks, no-locks and low-support cases.

## Protected boundaries

Do not modify:

- frozen detector;
- canonical rows/evidence;
- frozen Phase-1 lineage/scores;
- finalized Phase-2 findings;
- frozen runway clock;
- permanent Frankie;
- Frankie 1;
- `research/kalshi/spawn.py`;
- frozen SSOS play.

The standing policy remains:

`FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`

Any future Frankie enhancement mentioned during this research is intentionally deferred and is not part of V4.
