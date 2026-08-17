# ChatGPT Kickoff — NG Exhaustion Aftermath / Transition Research — 2026-08-17

## Start here

Repository: `DavisAI1974/Markets`
Branch: `chatgpt/ng-exhaustion-aftermath-20260817`
Branch base / completed clock freeze: `637778d6f460940379ac0feaf8223be47971c11f`

Read in this order:

1. `research/NG_EXHAUSTION_AFTERMATH_DISCOVERY_SNAPSHOT_20260817.md`
2. `CHATGPT_HANDOFF_NG_EXHAUSTION_CLOCK_COMPLETE_20260817.md`
3. `research/FRANKIE_NG_EXHAUSTION_REVEAL_MEMO_20260816.md`
4. `research/ng_dipole_native_shape_audit.py`
5. `research/ng_exhaustion_frankie_blind_input_20260816.py`
6. `research/ng_exhaustion_frankie_blind_reveal_score_20260816.py`
7. only then inspect older S86/S90/S92 exhaustion files if needed for provenance.

Current repo state is truth. Do not redo the completed clock.

## Mission

Build and validate a **second independent exhaustion signal** that answers what the market tends to do **after an exhaustion episode**, rather than how long the corresponding current price leg lasts.

There are two distinct targets to investigate:

### Target 1 — exhaustion-to-exhaustion transition memory

Given the current exhaustion episode and the tape state through its collapse/persistence window, predict whether the **next detected exhaustion episode** on the same day:

- has the same polarity;
- flips polarity;
- how long until the next exhaustion event;
- whether the next exhaustion is itself persistent/collapsing.

Known exploratory baseline:

- persistent through +60s -> next polarity same roughly 60–62%;
- collapsed through zero by +60s -> pooled next polarity roughly 50/50.

Known exploratory conditional candidates:

- persistent + extreme same-side late flow -> next polarity same about 85–88% (`40/47` reveal, `37/42` held-out in exploratory screen);
- tighter same-side aggressor / opposing-book cell -> about 89–90% same (`19/21`, `16/18`), but n=39 and multiple-screening risk;
- collapsed + original-side late flow reassertion -> roughly 73–76% same in exploratory screen;
- collapsed + strong opposite final-20s roll20 and essentially all opposite late aggressor flow -> next polarity flips `53/70=75.7%` reveal and `58/72=80.6%` held-out.

Do not promote these numbers until independently reconstructed.

### Target 2 — post-exhaustion raw tape / price aftermath

Anchor at a strictly defined exhaustion endpoint and measure **what the actual tape does next**, independent of the corresponding ZigZag leg duration used by the runway clock.

Start with fixed post-end horizons:

`5, 10, 20, 30, 60, 120, 300 seconds`

Measure at least:

- signed price displacement in ticks from the exhaustion endpoint;
- same-polarity continuation rate;
- opposite-polarity reversal rate;
- chop / no-material-move rate using predeclared tick thresholds;
- max favorable excursion and max adverse excursion;
- time to first 3t and 5t displacement either side;
- late aggressor flow state;
- 10-level book state/change;
- next exhaustion polarity and time-to-next-exhaustion.

Do not use the existing ZigZag containing-leg direction/duration as the primary target. It can be a later descriptive cross-check only.

## Core methodological rule

This project must preserve the same blind discipline that made the runway finding trustworthy.

Use:

- reveal half (`n=1718`) for discovery;
- freeze the exact rule/thresholds;
- held-out half (`n=1711`) for validation;
- day-level replication across all four days;
- no held-out retuning.

Because the exploratory chat already screened multiple conditions, the new analysis must explicitly account for that. Preferred approach:

1. re-derive simple candidate features from mechanism-neutral quantities;
2. choose thresholds from reveal-half quantiles / monotone bins, not from held-out hits;
3. freeze a small candidate set;
4. test once on holdout;
5. report effect sizes and uncertainty, not only hit rates.

If possible, preserve a further untouched forward-live validation set for eventual promotion.

## Exact source artifacts

Reveal packet:
- run `31984194953`
- artifact `9273273233`
- digest `sha256:127e936355be479398e14f20f071f81b0d22a2975b02e87a1a3e0a044ec023e1`

Frozen held-out blind input:
- artifact `9274443976`
- SHA-256 `224be8b033c1a03d638d7b84aef849363067e1961e9945e72bc86b52c3d01c39`

Held-out reveal score:
- run `31989542165`
- artifact `9274882157`
- digest `sha256:9c29dd6add1940172f11ac9e72d5f3396262829eeb46487eb89d88b161a9dece`

Canonical bulk clock input is also on S3:
`s3://bento-568968024170-us-east-2-an/nymex/ng_exhaustion/v0/`

Authoritative continuous raw NG MBP-10 corpus remains under the existing `nymex/nymex_cont/` S3 layout.

## First implementation step

Create one deterministic research table with one row per exhaustion event, ordered by day/time, containing **no corresponding-leg outcome fields in the feature block**.

Feature block should include only information available by the selected exhaustion endpoint:

- day, t0, polarity, A/B/C family;
- A fast/persistent state when legally available;
- t50/t25/t10/zero status/time;
- oriented roll-20 values and slopes;
- late-window aggressor buy/sell fractions;
- change in aligned aggressor pressure from t0;
- aligned 10-level book imbalance and change;
- MBO features only where matching contract MBO is proven;
- session/time-of-day and other legal pre-existing context only if added in a later controlled pass.

Outcome block for Target 1:
- next-event existence;
- seconds to next event;
- next polarity same/flip;
- next family/state.

Outcome block for Target 2:
- post-end fixed-horizon trade-price/tape measurements.

Keep feature and outcome namespaces explicit so leakage scans are easy.

## Immediate analyses to run

For Target 1:

1. reproduce the alive-at-60 vs collapsed baseline;
2. quintile/decile late oriented roll-20 flow;
3. quintile/decile late same-side aggressor share;
4. 2D table: late flow strength x flow change/reassertion;
5. 2D table: late aggressor flow x resting-book alignment;
6. test whether the conditional split reproduces by day;
7. check sample-size stability and exact confidence intervals;
8. quantify whether threshold effects are monotone rather than one lucky cut.

For Target 2:

1. define exhaustion endpoint policy before looking at price aftermath;
2. plot median and quantiles of signed post-end price path for persistent vs collapsed states;
3. split collapsed events by late flow reassert/reversal state;
4. compare continuation/reversal at each fixed horizon;
5. test whether the same transition state predicts both next-exhaustion polarity and subsequent tape direction;
6. compare results by family A/B/C but do not pool rare B/C into doctrine.

## Falsifiers

Kill or downgrade a candidate if:

- pooled result disappears on multiple individual days;
- the held-out rate falls near 50% after a strong reveal result;
- the effect exists only at one hand-picked threshold with no monotone neighborhood;
- the result depends on future price in the feature block;
- it is merely restating A-persistent vs A-fast-collapse rather than adding transition information;
- it depends on unproven/mismatched MBO;
- sample size is too small to distinguish the effect from noise;
- the corresponding post-exhaustion tape outcome contradicts the proposed state interpretation.

## Relationship to Frankie

Nothing from this branch belongs in permanent Frankie yet.

If a transition classifier survives reveal -> frozen holdout -> forward-live validation, the eventual role would be a **separate state/aftermath input**, conceptually something like:

- current runway clock: `how long does the current leg likely have?`
- aftermath state: `when this exhaustion resolves, is the market reloading, reversing, or indeterminate?`

Do not let the aftermath lane alter runway seconds.

## Hard do-not-touch boundary

Completed clock source of truth:
`chatgpt/ng-exhaustion-runway-clock-20260817` @ `637778d6f460940379ac0feaf8223be47971c11f`

Do not modify from this aftermath branch:

- `research/FRANKIE_NG_PRE_FAMILY_CLASSIFIER_FROZEN_OPERATIONAL_20260817.json`
- `research/FRANKIE_NG_A_POSTSTATE_CLASSIFIER_FROZEN_PREBLIND_20260816.json`
- frozen runway baselines in `research/ng_exhaustion_runway_clock.py`
- completed clock proof semantics
- permanent Frankie brain/schema/roles/plays/datapoints/workflow

The new chat's job is **research and validation of the second piece only**.
