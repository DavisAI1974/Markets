# NG Exhaustion Full-Causal Information Correction — 2026-08-19

Status: **AUTHORIZED CORRECTION FOR THE CHAIN BIRTH / DEPTH / TYPE RECOVERY PASS. FROZEN PHASE-1/PHASE-2 RESULTS ARE NOT REOPENED OR RETUNED.**

## Governing principle

The recovery experiment must not artificially deprive the model of information that would genuinely be known at the tested causal checkpoint.

The rule is:

> **Use every represented fact once its own causal availability time has passed. Block only hindsight/future information.**

This correction changes the predictive-information wall for the new recovery experiment only. It does not rewrite historical Phase-1 or Phase-2 findings and does not modify any frozen detector, canonical row, lineage score, runway clock, Frankie artifact, `spawn.py`, or SSOS play.

## Clock separation

Two clocks are kept distinct.

- `PRIOR` is strictly before the candidate target birth `t0`.
- `PRIOR_AGE` is only the age of the global causal checkpoint after the latest required predecessor confirmation. It is not H.
- `H+1 ... H+5` begins only after frozen target birth `t0`, and is evaluated only for model/target questions that did not resolve in PRIOR.

At a PRIOR checkpoint, all predecessor/root information already available by that absolute checkpoint may be used. Older predecessors are not truncated to the same age as the newest predecessor.

## Price

Price is available on both sides of birth.

Before target birth:

- every predecessor/root occurrence keeps its own ordered price history;
- price known before and after predecessor confirmation may contribute once the checkpoint has passed it;
- no price after the active checkpoint may enter;
- price availability/missingness remains infrastructure and fails closed rather than becoming a classifier feature.

After target birth:

- all earlier predecessor/root price information remains available;
- the newly born target's own causal birth-anchored price path is added at H+1, then extended at H+2, H+3, H+4 and H+5;
- if another canonical event is actually born inside that elapsed window, its then-causal raw/static information may also enter. Its future lineage membership is never supplied.

## Structural information

Previously frozen characteristics are no longer globally excluded merely because an older experiment used a narrower wall.

Examples of information that may enter `FULL_CAUSAL` once actually known include:

- polarity;
- frozen A/B/C pre-family assignment and its pre-t0 distances;
- peak/prominence and other birth-static fields;
- clock/session context that is already observable;
- endpoint/onset/confirmation information after it occurs;
- P/O/S/X seed state only once its required +60 information has actually elapsed;
- A persistent/fast-collapse post-state only once its +60 input is actually available;
- threshold/zero milestones only after each milestone occurs, or after the +60 horizon establishes that it did not occur;
- then-causal price path summaries and exact early one-second price path.

No target P/O/S/X state is known in advance. No future target polarity, future lineage membership, final depth, final chain type, future price, or later event is leaked backward.

## Information views

The primary research view is:

`FULL_CAUSAL`

Two ablations are preserved at the same rows/checkpoints:

- `NO_PRICE_CAUSAL` — same causal structural information with price removed;
- `PRICE_POLARITY_ONLY` — causal price plus polarity without the richer structural fields.

These are diagnostic ablations only. They may not replace a valid `FULL_CAUSAL` finding merely because they are simpler.

## Targets

Each predeclared model independently tests three targets at D1-D3:

1. `CONTINUATION` — whether the candidate target is a continuation of the current chain. At D1 this is the primary chain-versus-D0 existence boundary.
2. `EVENTUAL_DEPTH` — frozen final D0-D5 depth as a future label only.
3. `CHAIN_TYPE_FAMILY` — the already-frozen next-link grammar label `P/O/S/X` plus `SAME/FLIP`. Ordered stage labels form the chain grammar used by the existing pairing/grouping maps; no new taxonomy is invented.

D4/D5 remain preserved case studies.

## Model doctrine

Logistic, ExtraTrees and KNN are evaluated independently. No cross-model consensus vote is allowed. A causal OOT result from one predeclared model is preserved even when the others fail. Disagreement is evidence.

Resolved means compute-resolved for that exact model/target only. It never deletes cases, failures, other models, later research eligibility, or historical evidence.

Standing policy: `FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`.
