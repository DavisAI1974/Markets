# ChatGPT Handoff — NG Exhaustion Clock V0 COMPLETE — 2026-08-17

Status: **CLOCK V0 COMPLETE AS AN ISOLATED DOWNSTREAM RUNWAY COMPONENT.** Permanent Frankie remains untouched. Production activation is a separate operation.

Repository: `DavisAI1974/Markets`
Branch: `chatgpt/ng-exhaustion-runway-clock-20260817`
Takeover base: `4954e9f178569f53623e9326be5dc3ac91caaca1`
Supersedes for current status:
- `CHATGPT_HANDOFF_NG_EXHAUSTION_RUNWAY_CLOCK_V0_20260817.md`
- `CHATGPT_HANDOFF_NG_EXHAUSTION_S3_NOVA_20260817.md`

## Exact scope boundary

The completed V0 begins **after an upstream causal exhaustion-event detector marks t0**. Event detection itself is not part of this clock and was not reinvented here.

From that t0 onward the V0 clock owns the complete deterministic runway path:

`upstream causal t0 -> exact live roll20 input -> dipole polarity -> frozen pre-family A/B/C -> A pending until +60 -> frozen A fast/persistent state -> deterministic runway countdown -> optional NOVA model-facing packet`

No future price, realized endpoint, ZigZag outcome, or LLM call is used by the clock.

## Frozen pre-family classifier

Artifact:
`research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json`

SHA-256:
`583f6a121788b3d962f2ec849a270f96b1786d714ac930d2b0069c6261eda6f7`

Input is only the oriented 61-sample roll-20 geometry from t=-60..0. The recovered operational adapter reproduces the already-frozen original A/B/C family assignment on all 3,429 substantive reveal+blind events with zero mismatches. No price/post-t0/outcome field was used to recover it.

## Exact live roll-20 input

Implemented in:
- `research/ng_exhaustion_live_clock.py`
- `research/kalshi/ng_live_exhaustion_collector.py`

The historical/live-identical input is:

- use only Databento MBP-10 records (`rtype=10`);
- accept only trade action `T`;
- classify aggressor side from trade price vs the concurrent top-of-book midpoint;
- price > midpoint = buy, price < midpoint = sell, midpoint = skipped;
- compute `(buy_volume - sell_volume) / (buy_volume + sell_volume)` over the trailing 20 seconds inclusive;
- orient by the t0 roll-20 polarity;
- preserve the historical bounded forward-fill/back-fill behavior inside the requested causal window.

The explicit `rtype=10` gate prevents TBBO (`rtype=1`) from double-counting the same trade in the existing multi-schema live session.

## Frozen A post-state / runway

The original frozen A state classifier remains byte-locked:

`research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json`

SHA-256:
`698b956f2a9aad4b99ccb9afab916e7219123d10c82408b8d9340137c266ecb9`

A stays pending before +60. At +60 it classifies the exact oriented t0..+60 61-sample roll-20 window. Frozen runway seconds remain unchanged:

- A-fast-collapse: 3t=358, 5t=993, 8t=1802, 13t=4386
- A-persistent: 3t=700, 5t=1802, 8t=3455, 13t=6836
- B unresolved fallback: 353 / 995 / 1615 / 4543
- C provisional fallback: 377 / 1159 / 1713 / 4320

`remaining_s = max(0, baseline_total_s - elapsed_since_t0_s)`

Microstructure remains confidence-only and can never change state identity or runway seconds.

## Final equivalence proof

Committed proof:
`research/NG_EXHAUSTION_LIVE_CLOCK_V0_FINAL_PROOF_20260817.json`

GitHub Actions final run:
- run ID: `31998769659`
- conclusion: `success`
- artifact ID: `9277695889`
- artifact digest: `sha256:bbd0dc31caa46824bc833efe72c56c098202fb8c83e37eaba3b83bfcb9f1a072`

Exact frozen blind batch results:

- records checked: 1,711
- pre-family assignment mismatches: **0**
- live roll-20 samples checked: **104,371**
- live roll-20 bad records: **0**
- maximum roll-20 absolute error: **0.0**
- Family A records checked at +60: 1,616
- A post-state mismatches: **0**
- future price accessed by clock: **false**
- permanent Frankie mutated: **false**

Callback tests additionally prove MBP-10 rtype 10 is consumed and TBBO rtype 1 is rejected.

## Existing S3 / cache / NOVA proof remains valid

Bulk exhaustion data is canonical on S3 under:

`s3://bento-568968024170-us-east-2-an/nymex/ng_exhaustion/v0/`

The exact frozen source ZIP and deterministic day partitions were published and SHA-read-back verified. The S3 cold/warm overlay proof reproduced the frozen clock across all four held-out days. The NOVA model-facing packet remains a disposable derived view and reduced the clock payload by roughly 93%; it never replaces the canonical S3 object.

One deterministic worker remains the V0 architecture. Large-batch timing showed the clock math is not the bottleneck.

## Production deployment witness

The old live collector code advertises:

`s3://bento-568968024170-us-east-2-an/nymex/live/ng/health.json`

The final proof attempted a read-only witness and received HeadObject 404. Therefore **this handoff does not claim that the old live collector is currently deployed/publishing at that path**.

That is deliberately separated from clock correctness:

- clock component: COMPLETE;
- drop-in exact live input tap: BUILT + TESTED;
- production activation/deployment of that tap: NOT PART OF THIS V0 completion proof;
- permanent Frankie integration: NOT DONE.

Do not open a second Databento live session merely to prove the clock. If production activation is later desired, deploy the drop-in tap through the existing single live-collector session and verify its health/output there.

## Do not change after this freeze

- Do not retune A/B/C family geometry from price outcomes.
- Do not retune the frozen A post-state classifier.
- Do not replace reveal runway baselines with held-out medians.
- Do not use the scratch blind price-curve generator as doctrine.
- Do not let NOVA packets become canonical data.
- Do not add extra clock workers unless live instrumentation proves a real backlog.
- Do not merge the separate exhaustion-aftermath discovery into this clock.
- Do not mutate permanent Frankie from this branch without a separate explicit approval step.

## Next research thread is separate

A second, independent discovery was made while closing the clock: exhaustion episodes appear to have useful **aftermath / transition-state** information about what the tape and the next exhaustion episode do after a collapse or persistent run. That work must live on a separate branch/handoff so none of its exploratory thresholds contaminate this frozen clock.

This clock branch is the completed V0 source of truth for the runway component.
