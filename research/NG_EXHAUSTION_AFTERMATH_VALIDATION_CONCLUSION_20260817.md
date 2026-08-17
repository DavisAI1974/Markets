# NG Exhaustion Aftermath Validation Conclusion — 2026-08-17

Status: **VALIDATION COMPLETE / CHAIN DISCOVERY GATE OPEN**

Scope remains scratch aftermath/transition research only. The completed runway clock, its frozen classifiers/contracts, and permanent Frankie are unchanged.

## Provenance

- Dynamic-end V2 validation artifact: `ng-exhaustion-aftermath-validation-v2-20260817`, artifact `9278686522`, digest `sha256:0357826f86ce9971688a467c41ea4c64c23eaaf2d22dc1f37fc39ce62c4f168a`.
- Formal Target 1 transition artifact: `ng-exhaustion-target1-transition-validation-20260817`, artifact `9278840442`, digest `sha256:d62f81b51159bf38148e0b782b7b412d767cb1142336d603c5807cd825ac27c4`.
- Endpoint-relative Target 2 transition artifact: `ng-exhaustion-aftermath-transition-checkpoint-20260817`, artifact `9278930487`, digest `sha256:231f23c6c5d74958e7f1a0d5c03bfd33eac56f64294999bc6a04f304c877133c`.

All three study weeks were loaded continuously Sunday reopen through Friday. Calendar midnight, HE24→HE1, and daily file boundaries were not treated as market resets.

## Endpoint semantics validated

The exhaustion endpoint is not a hardcoded clock time. The structural termination run is the first three consecutive causal seconds with oriented trailing-20-second aggressor-volume imbalance `<= 0`; the **causal confirmation second** is the third confirming second and is the primary aftermath anchor.

Across all 3,429 events:

- all 2,343 bounded artifact `zero_s` labels matched reconstructed structural onset exactly;
- 41 additional cases began the qualifying run near +60 but only became causally confirmed after +60, proving why onset and confirmation must remain separate;
- no event required a manufactured endpoint within the available continuous study-week stream.

## Target 1 — next exhaustion polarity

The old within-half exploratory percentages reproduce exactly when the old ordering is intentionally repeated, but that ordering can skip intervening events from the other half. The causal validation instead uses the literal next detected event in the full target-date stream and scores a +60 rule only when that event is still in the future at +60.

Pooled same-next rates under that stricter rule:

- persistent/alive through +60: reveal `224/389 = 57.58%`; holdout `214/368 = 58.15%`;
- collapsed by +60: reveal `359/669 = 53.66%`; holdout `366/672 = 54.46%`.

The strongest clean surviving structure is a **smooth collapsed-event late-flow gradient**, not the old extreme cells. Reveal-derived pressure quintiles produce same-next rates:

- reveal: `44.44%, 45.74%, 58.00%, 63.21%, 64.00%`;
- holdout using the unchanged reveal cutpoints: `46.46%, 50.49%, 57.50%, 58.33%, 62.96%`.

This is evidence of real serial memory. It is not a chain category and the quintile cells are diagnostics only.

The dramatic exploratory ~80–90% cells are not promoted: most of their literal next exhaustions had already begun inside the +60 feature window, so those cells were substantially describing a transition already underway rather than predicting a still-future event.

## Target 2 — tape after actual exhaustion end

Unconditionally, the tape immediately after confirmed exhaustion end is mostly chop:

- at +20s: about 90% chop in both reveal and holdout;
- at +60s: about 79% reveal / 78% holdout chop;
- at +300s: about 51% chop, with continuation and reversal roughly balanced.

A second causal lane observed one complete native roll20 window **after** the confirmed endpoint (endpoint+20) and then predicted only tape after that checkpoint. The simple sign of post-end aggressor pressure did **not** produce a stable directional rule across reveal and holdout. Some subgroup differences appear, but their sign/magnitude do not replicate cleanly enough for promotion.

Conclusion: “exhaustion ended” by itself is not a directional trade rule, and the simple endpoint+20 flow-sign update is not promoted.

## Chain gate

The validation gate is satisfied. Chain research may now begin under `NG_EXHAUSTION_CHAIN_DISCOVERY_FREEZE_20260817.json`.

Load-bearing chain rules:

1. Reconstruct the complete exhaustion sequence from the first actual trade after Sunday reopen through the true weekly close.
2. Find chain instances and boundaries **before** categorizing them.
3. Do not use duration, number of links, polarity pattern, flow/book shape, price path, family, or time-of-day to pre-label or manufacture chain membership.
4. Freeze chain membership first; only then calculate characteristics and let the frozen chains reveal any natural categories.
5. Time-of-day/session position is posthoc context only.
6. Chain continuation is evidence that inherited ancestor state still adds predictive information beyond the immediately current event; loss of inherited incremental information is candidate reset evidence.
7. No permanent Frankie merge until chain findings have survived their own validation and a deliberate brain-merge decision.
