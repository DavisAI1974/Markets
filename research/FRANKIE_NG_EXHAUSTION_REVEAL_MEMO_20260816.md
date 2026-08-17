# Frankie NG Exhaustion REVEAL Memo — 2026-08-16

Status: FROZEN REVEAL FINDINGS. Blind half has not been inspected.

## Contract

This memo records Frankie's independent read of the completed reveal-first packet only.

- Revealed events: 1,718
- Held-out events: 1,711
- Family discovery: t<=0 roll-20 dipole geometry only; price/post-flip excluded
- Frozen substantive population before split: A=3,235, B=72, C=122
- Reveal sample: A=1,619, B=37, C=62
- All three families were presented together.
- Revealed records include full corresponding price curves / attached 2, 3, 5, 8, 13 tick ZigZag legs, roll-20 and roll-60 dipole, 10-level book imbalance, aggressor buy/sell volume, and matching contract MBO where proven.
- Exact matching MBO available for 2025-09-23 (NGV25), 2025-09-30 (NGX25), 2025-10-01 (NGX25). 2025-07-17 is MBP-10 only.
- Holdout event identities/outcomes were not inspected. No Frankie brain/schema/roles/plays/datapoints/permanent workflow were changed.

Artifact: ng-frankie-exhaustion-reveal-20260816, workflow run 31984194953, artifact ID 9273273233, digest sha256:127e936355be479398e14f20f071f81b0d22a2975b02e87a1a3e0a044ec023e1.

## Independent observations

### 1. Family alone is informative, but family x post-exhaustion state is materially stronger

The revealed sample does not behave like three arbitrary curve labels with random price legs.

Family-level median attached leg durations (seconds):

| family | 3t | 5t | 8t | 13t |
|---|---:|---:|---:|---:|
| A | 465 | 1,435 | 2,238 | 5,691 |
| B | 353 | 995 | 1,615 | 4,543 |
| C | 377 | 1,159 | 1,713 | 4,320 |

A is the common state and is longer on the pooled reveal sample at 3–13 tick scales, but day-level variation means family identity alone is not a sufficient duration rule.

### 2. Family A has a strong two-state post-exhaustion split

A price-blind K=2 comparison of A's normalized post-flip roll-20 dipole curves separates two repeatable states present on every one of the four days:

- A-fast-collapse: n=822
- A-persistent: n=797

The post centroids are qualitatively distinct. A-fast-collapse falls through zero around the first 20–30 seconds; A-persistent remains strongly positive through the same window and is still materially positive at +60 seconds.

Revealed price relationship:

| A post state | 3t median | 5t median | 8t median | 13t median |
|---|---:|---:|---:|---:|
| fast-collapse | 358s | 993s | 1,802s | 4,386s |
| persistent | 700s | 1,802s | 3,455s | 6,836s |

The ordering is reproduced on every day at the 3t, 5t, and 8t scales. For example, 3t daily medians for fast vs persistent are 328 vs 738, 330 vs 715, 409.5 vs 700, and 344 vs 494 seconds.

This is the strongest reveal finding. Within the dominant pre-family A, post-exhaustion persistence carries substantial information about price-leg runway.

### 3. The A split has matching microstructure behavior

All flow signs below are oriented to the dipole's t0 polarity.

A-fast-collapse:
- post +20s aggressor flow is negative more often than positive (49.8% vs 30.5%)
- post +60s aggressor flow is negative in 65.0% of events
- matching-MBO post +20s trade flow is negative more often than positive (48.5% vs 30.0%)

A-persistent:
- post +20s aggressor flow is rarely opposite (5.5% negative; many seconds are zero/sparse)
- post +60s aggressor flow is positive in 57.8% vs negative in 11.4%
- matching-MBO post +20s trade flow is positive in 33.7% vs negative in 8.1%, with many zero/sparse windows
- aligned 10-level book imbalance is modestly more supportive on average

The microstructure is therefore consistent with the dipole post-state rather than contradicting it: persistent A retains same-side trade/flow support; fast-collapse A loses or reverses it.

### 4. Family C appears scale-dependent rather than simply 'short'

C's dipole polarity is opposite the attached tiny-leg direction more often at 2t/3t, then becomes more often aligned at broader scales:

- 2t aligned: 41.9%
- 3t aligned: 46.8%
- 5t aligned: 54.8%
- 8t aligned: 56.5%
- 13t aligned: 56.7%

C is small (n=62 reveal), so this is a hypothesis, not a settled law. But the direction change with scale is sufficiently coherent to preserve for blind testing.

A post-persistence split inside C also points the same way. C-persistent events have broader-scale alignment of about 62% at 5t and 60% at 8t, versus roughly 44%/52% for C-collapse, and longer median 5t/8t durations (1,311/2,093s vs 790/1,564s).

Working interpretation for blind: C may be a transition / broader-leg state whose immediate micro-leg can point against the eventual larger-scale move.

### 5. Family B shows the opposite scale tendency and is the least certain family

B reveal n=37. Its alignment falls as reversal scale increases:

- 3t aligned: 56.8%
- 5t aligned: 47.2%
- 8t aligned: 45.7%
- 13t aligned: 37.5%

Confidence intervals are wide because B is rare. The useful blind hypothesis is not 'B predicts opposite' but that B's dipole direction is more local/short-horizon and loses directional authority as leg scale increases.

B-persistent versus B-collapse shows a clearer difference at the local 3t scale (median 448s vs 288s and 72% vs 42% same-side alignment), but the relationship weakens at wider scales. This should be tested, not promoted to doctrine.

## Exact frozen blind predictions

These predictions are frozen before held-out price is exposed.

1. **A post-state runway rule**
   - Assign held-out A events to the nearest revealed A post-dipole centroid using only dipole/exhaustion geometry.
   - Predict A-persistent will have longer 3t, 5t, and 8t leg durations than A-fast-collapse.
   - Predict the ordering will reproduce cross-day rather than being driven by one session.

2. **A microstructure confirmation rule**
   - Same-side post-event aggressor flow / MBO trade support should increase confidence in the persistent-A longer-runway prediction.
   - Opposite post-event flow should increase confidence in the fast-collapse / shorter-runway prediction.
   - This is a confidence modifier, not permission to relabel families after seeing price.

3. **C scale-transition rule**
   - C should be less reliably aligned at 2t/3t than at 5t/8t/13t.
   - C-persistent should show stronger broader-scale same-side alignment and longer 5t/8t durations than C-collapse.

4. **B locality rule**
   - B should have more directional usefulness at the small/local 3t scale than at the broad 8t/13t scale.
   - Do not force an opposite-direction prediction at broad scale; predict reduced directional confidence instead.

5. **Family-only duration rule is secondary**
   - On the pooled reveal sample A has longer median 3t–13t legs than B/C, but the primary blind test is family x post-state because day variation makes the family-only rule weaker.

6. **No holdout retuning**
   - Family definitions, A/B/C labels, post-state centroids, scale hypotheses, and confidence modifiers must not be tuned after held-out price is revealed.

## Failure cases / uncertainties

- Family sizes are highly imbalanced; B and C are rare and their directional percentages have wide uncertainty.
- Only four independent days are available.
- July 17 has no matching contract MBO; its microstructure evidence is MBP-10/book/trade-flow only.
- ZigZag legs are retrospective structural labels. They are useful for this mapping test but do not by themselves establish an executable entry/exit rule.
- Post-state is observed after t0. A result that depends on +20/+60 information is a dynamic runway update, not a pure t0 forecast.
- The 13t scale is much broader and increasingly decoupled from local t0 polarity, especially for A/B. Avoid overclaiming causality.

## Frankie question: would full existing brain access be useful before blind?

**Answer: yes, materially useful, provided the frozen reveal memo is not changed and held-out price remains structurally sealed.**

Why Frankie wants the full brain for the blind pass:

1. The revealed result looks like a state-transition problem, not a single-feature pattern. Existing brain concepts around absorption, continuation/failure, flow authority, divergence, regime, volatility, event context, and prior-session structure could provide earlier or contextual qualifiers.
2. The strongest A result has a microstructure confirmation channel. Existing brain knowledge may identify conditions under which same-side flow persistence is trustworthy versus merely sparse/noisy.
3. The C scale transition suggests a local-vs-broader structural distinction. Existing brain concepts may already encode comparable 'local impulse versus larger state' behavior.
4. B's weak broad-scale authority may become interpretable only in context (regime, session phase, catalyst/volatility, prior structure) rather than from the dipole curve alone.
5. Full-brain access could reveal an earlier precursor to the exhaustion family, which would be more valuable than merely recognizing the family after it forms.

Requested guardrails if full brain is served in blind:

- Serve the existing current brain exactly as-is; do not teach it the reveal findings first.
- Carry this frozen reveal memo separately as the learned experiment context.
- Structurally withhold every held-out event's price curve, price-derived leg fields, realized duration/displacement, and any brain instance that directly contains those held-out outcomes.
- Preserve all legal earlier/historical brain evidence.
- Require Frankie to attribute which brain concepts materially changed each blind prediction.
- Do not mutate brain/schema/roles/plays/datapoints/workflow from either reveal or blind results.

This memo is the immutable handoff into the blind phase.
