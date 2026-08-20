# ChatGPT Kickoff — NG Chain Birth / Depth / Type Recovery — 2026-08-19

## Status

This document is the authoritative framing for the next chat.

Stop and read this before modifying or launching the current recovery implementation. The recent recovery code was written while the experiment framing was still being corrected in conversation. Treat the words in this document as the contract and inspect/revise the code against it before running anything.

Current branch:

`chatgpt/ng-exhaustion-entry-timing-revival-20260818`

Current repo state is truth. Do not redo settled work.

## Protected boundaries

Do not modify, retune, reopen, or relitigate:

- frozen detector;
- frozen canonical evidence / canonical rows;
- frozen Phase-1 lineage and scores;
- finalized Phase-2 findings;
- frozen runway clock;
- permanent Frankie;
- Frankie 1;
- `research/kalshi/spawn.py`;
- frozen SSOS play.

No permanent brain merge or live-play promotion is authorized by this research.

Preserve every valid row, losing case, false case, censored case, low-support case, model disagreement, and failed hypothesis. The standing policy remains:

`FLAG_AND_DECOMPOSE_NOT_AUTO_KILL`

## What this experiment is actually trying to answer

The immediate research question is not trade direction and not polarity.

It is:

1. **Will this exhaustion become a chain at all?**
2. **How deep will the chain ultimately go?**
3. **What kind / structural family of chain is it becoming?**
4. **At what earliest causal point can each of those answers be predicted?**

The key timing question is specifically:

> Can we know the answer before the next D is born? If not, how many seconds into the developing chain — +1, +2, +3, +4, +5, then later if necessary — are required before chain existence, eventual depth, or chain type becomes predictable?

These are separate targets. It may be possible to know that a chain is forming before its eventual depth is knowable, and to know depth before the exact family/type is knowable. Record the earliest causal point for each target independently.

## Chain/depth definitions to preserve

Frozen exact-depth counts remain:

- D0 = 135,860
- D1 = 18,837
- D2 = 1,592
- D3 = 124
- D4 = 8
- D5 = 1

Do not renumber, collapse, or delete D groups.

D0 versus D1+ answers the first question: chain versus no chain.

For chains that continue, the next questions are eventual depth and structural sequence/family.

## Primary hierarchy: PRIOR first, clock only as fallback

The detector-relative `+0,+1,+2,...` clock is **not** the primary experiment. It is fallback.

The correct hierarchy is:

### A. PRIOR / pre-birth prediction

First ask whether chain existence, eventual depth, and/or family/type can be predicted **before the next target D is born**, using only information that is already causally available from predecessor/root occurrences.

No target information from after its birth may leak backward.

If a target is already predictably resolved before birth, preserve that earliest PRIOR result. Do not force it through the fallback clock merely for uniformity.

### B. During-chain earliest recognition

Only for questions not solved pre-birth, ask how soon after the developing chain/state begins the answer becomes knowable:

- +1 second
- +2 seconds
- +3 seconds
- +4 seconds
- +5 seconds

Most useful D behavior may resolve in this first-five-second window, so these checkpoints should be explicit and dense.

Only unresolved questions continue to later checkpoints.

### C. Later fallback

Continue later causal checkpoints only for still-unresolved questions. Do not drop unresolved cases merely because they are difficult or low support.

The existing frozen runway/detector-relative ladder remains a fallback timing tool, not the default starting point.

## What may be used as predictive information

Polarity is not the prediction target. It is one possible causal input.

Price is also a causal input and must be treated in two distinct phases.

### Before target birth

For every predecessor/root occurrence, its own causal price history may be useful before the next D is born.

Keep predecessor occurrences separate and ordered. Do not pool multiple chain occurrences into one generic price-available feature.

The existing one-second causal price-path contract remains important:

- baseline = last authoritative trade known at or before that occurrence's frozen confirmation;
- at each second, use only the last trade known by that second;
- carry forward when no new trade occurs;
- no future interpolation;
- no price after the active causal checkpoint may enter the model;
- price availability/missingness is infrastructure, never a predictor.

Pre-birth work should be able to measure whether price adds information beyond simpler structural inputs, but do not assume polarity-only is the research target.

### After target birth

Once a D is actually born, that newly born D's **own causal price path** becomes available and may help identify:

- whether this is truly developing as a chain;
- eventual depth;
- structural family/type;
- next-stage birth probability;
- later trade-management research.

The target's post-birth price path may never be leaked backward into a pre-birth call.

## Models and validation

Do **not** require a 2-of-3 model consensus gate.

If logistic, ExtraTrees, KNN, or another predeclared model independently demonstrates a causal OOT result, preserve it. Disagreement is evidence; do not erase one model's valid finding because others fail.

Each model/result should remain individually auditable across the frozen chronology:

- discovery fit;
- discovery tuning where applicable;
- validation;
- untouched confirmation;
- held non-contradiction.

Do not manufacture universality from D4/D5 support. Preserve them as case studies while still recording every causal checkpoint and available price/structure path.

## What “resolved” means

`Resolved` is a compute concept only.

If the earliest valid answer to a particular target/question is already known at an earlier causal point, later checkpoints cannot produce an earlier answer and need not be recomputed for that same model/question.

This does **not** remove any row, chain, model disagreement, failure, or historical evidence from the research record.

Different questions can resolve at different times. For example:

- chain/no-chain may resolve pre-birth;
- eventual depth may resolve at +2 seconds;
- family/type may resolve at +4 seconds.

Preserve all three timing results separately.

## Chain type / family target

The next chat must explicitly define the structural family/type labels from the already-frozen chain/pairing/grouping evidence before modeling them.

Family/type is a **future outcome label** for prediction, not a pre-birth feature.

Do not let target family identity, future target polarity/state, realized final depth, future path shape, or post-birth target data leak into a PRIOR feature set.

Use the existing Phase-2/post-Phase2 chain maps and pairing/grouping findings as the source of label definitions; do not invent a new taxonomy merely to make classification easier.

## Relationship to POX

The clean D0-D5 birth/depth/type experiment should remain separable from POX-specific identity unless and until a deliberate incremental-value cross is performed.

Do not contaminate the base causal study by baking held-out POX identity into the predictor merely because POX is interesting.

After clean birth/depth/type timing results exist, POX can be tested for **incremental** predictive value.

## Relationship to trade research

Trade direction/execution is downstream of this pass.

First establish:

- whether a chain will form;
- eventual depth;
- structural family/type;
- the earliest causal point each becomes knowable.

Then trade research can attach to the exact causal signal timestamp and use the signal plus then-known price/structure information.

Do not distort this experiment to force immediate trade rules.

## Existing recovery work that must be reviewed, not blindly trusted

Recent recovery artifacts/code were created while the framing was still changing, including:

- `research/ng_exhaustion_prior_early_model_agent_20260819.py`
- `.github/workflows/ng_exhaustion_prior_early_recovery_20260819.yml`
- `research/NG_EXHAUSTION_PRIOR_MODEL_PRICE_CORRECTION_20260819.md`

Important corrections already established in conversation include:

- no 2-of-3 model-voting requirement;
- PRIOR before birth is primary;
- the detector-relative clock is fallback;
- preserve independent model findings;
- predecessor price may add predictive information before birth;
- newly born D price becomes available only after birth;
- no rows/cases/groups are dropped;
- the actual target set is broader than the early binary D-boundary runner: **chain existence + eventual depth + chain type/family + earliest causal prediction time**.

The next chat should inspect and revise/supersede the half-built recovery implementation as needed before launch. Do not assume it already satisfies this contract.

## Recommended next-chat sequence

1. Read this file first.
2. Read the current branch state and the authoritative D1-D5 birth protocol / price-structure addendum / D0 protocol.
3. Read the Phase-2 and post-Phase2 chain pairing/grouping maps needed to define chain-type labels.
4. Audit the recent recovery runner/workflow against this framing.
5. Correct the implementation before launching anything.
6. Run a focused early causal pass first: PRIOR and +1/+2/+3/+4/+5.
7. Preserve earliest result independently for chain existence, depth, and family/type.
8. Only unresolved questions proceed later.
9. Only after PRIOR/early-chain prediction is exhausted should fallback-clock research be invoked.
10. Produce durable findings including failures and unresolved cases. Do not merge into permanent Frankie.

## Bottom line

The experiment is:

> **How early can we causally know that an exhaustion is becoming a chain, how deep that chain will ultimately go, and what structural kind of chain it is — before birth if possible, otherwise as early as +1/+2/+3/+4/+5 seconds into development, using all causally available predecessor/root information and price, with the detector-relative clock reserved only as fallback?**
