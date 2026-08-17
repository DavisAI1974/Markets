# Frankie NG Exhaustion Blind — Post-Reveal Analysis Scaffold

Status: POSTREVEAL_COMPLETE_NO_RETUNING
Frozen prediction commit: `0f26c125548c801037bb3084d23b1b5d974ae0eb`
Predictions scored: 1711

## Core holdout checks
- A 3t: persistent median 706.0s vs fast 344.0s; persistent>fast=True; day-level passes=4/4.
- A 5t: persistent median 1898.0s vs fast 992.5s; persistent>fast=True; day-level passes=4/4.
- A 8t: persistent median 3455.0s vs fast 1576.0s; persistent>fast=True; day-level passes=4/4.
- A 13t: persistent median 7474.0s vs fast 3786.0s; persistent>fast=True; day-level passes=4/4.

## B locality / C transition
- B alignment by scale: 3t=0.514, 5t=0.486, 8t=0.514, 13t=0.545
- C alignment by scale: 3t=0.500, 5t=0.542, 8t=0.569, 13t=0.582

## Curve fit
- Overall median RMSE: 9.993 ticks.
- Overall median curve correlation: 0.003156563165320449.
- Overall mean path-sign agreement: 0.4945145369558937.

No classifier, brain, schema, family definition, or forecast was retuned after reveal.
