# NG Exhaustion D1-D5 Chain-Birth PRIOR Availability — 2026-08-19

Status: **CANONICAL AVAILABILITY AUDIT ONLY — NOT PREDICTIVE SKILL.**

Purpose: establish how many frozen conditional chain-birth positives and prior-stage stops have enough causal predecessor information at each selected active H to be tested **before the next-stage target `t0`**.

The authoritative active H grid remains `1,2,3,4,5,10,15`, then every 5 seconds from `20` through `3600`. This summary prints selected landmarks; the agents test the dense grid.

Eligibility rule:

`RULE_READY(D,H) = max(predecessor causal_confirmation_idx + H)`

A row is PRIOR-eligible iff:

`RULE_READY(D,H) <= target.t0_idx`

`lead = target.t0_idx - RULE_READY(D,H)`

Availability does **not** imply predictive skill. It only proves that the information existed soon enough to attempt a causal pre-birth prediction.

## Frozen conditional birth cohorts

- D1 birth: 20,562 positives (`depth >= 1`) vs 135,860 exact-D0 controls; 37 D0 controls are frozen week-end target-censored, leaving 135,823 executable controls.
- D2 birth: 1,725 positives (`depth >= 2`) vs 18,837 exact-D1 controls.
- D3 birth: 133 positives (`depth >= 3`) vs 1,592 exact-D2 controls.
- D4 birth: 9 positives (`depth >= 4`) vs 124 exact-D3 controls.
- D5 birth: 1 positive (`depth >= 5`) vs 8 exact-D4 controls.

## D1 birth PRIOR eligibility

| H sec | Positive eligible | Positive % | Control eligible | Control % | Median positive lead sec |
|---:|---:|---:|---:|---:|---:|
| 1 | 13,372 | 65.0% | 105,873 | 77.9% | 43 |
| 5 | 13,039 | 63.4% | 103,351 | 76.1% | 40 |
| 10 | 12,577 | 61.2% | 99,987 | 73.6% | 36 |
| 15 | 12,177 | 59.2% | 97,022 | 71.4% | 33 |
| 20 | 11,029 | 53.6% | 88,848 | 65.4% | 30 |
| 25 | 10,126 | 49.2% | 82,087 | 60.4% | 28 |
| 30 | 9,233 | 44.9% | 75,459 | 55.6% | 27 |
| 60 | 4,313 | 21.0% | 36,605 | 27.0% | 28 |
| 120 | 1,321 | 6.4% | 10,976 | 8.1% | 69 |
| 300 | 361 | 1.8% | 2,832 | 2.1% | 195 |

## D2 birth PRIOR eligibility

| H sec | Positive eligible | Positive % | Control eligible | Control % | Median positive lead sec |
|---:|---:|---:|---:|---:|---:|
| 1 | 1,171 | 67.9% | 14,182 | 75.3% | 47 |
| 5 | 1,141 | 66.1% | 13,805 | 73.3% | 43 |
| 10 | 1,111 | 64.4% | 13,332 | 70.8% | 39 |
| 15 | 1,078 | 62.5% | 12,914 | 68.6% | 37 |
| 20 | 989 | 57.3% | 11,833 | 62.8% | 37 |
| 25 | 903 | 52.3% | 10,990 | 58.3% | 34 |
| 30 | 820 | 47.5% | 10,161 | 53.9% | 33 |
| 60 | 450 | 26.1% | 5,113 | 27.1% | 27.5 |
| 120 | 136 | 7.9% | 1,680 | 8.9% | 66 |
| 300 | 41 | 2.4% | 469 | 2.5% | 176 |

## D3 birth PRIOR eligibility

| H sec | Positive eligible | Positive % | Control eligible | Control % | Median positive lead sec |
|---:|---:|---:|---:|---:|---:|
| 1 | 88 | 66.2% | 1,086 | 68.2% | 47.5 |
| 5 | 87 | 65.4% | 1,057 | 66.4% | 44 |
| 10 | 84 | 63.2% | 1,009 | 63.4% | 40.5 |
| 15 | 80 | 60.2% | 986 | 61.9% | 36.5 |
| 20 | 74 | 55.6% | 872 | 54.8% | 36 |
| 25 | 67 | 50.4% | 798 | 50.1% | 33 |
| 30 | 61 | 45.9% | 738 | 46.4% | 29 |
| 60 | 29 | 21.8% | 362 | 22.7% | 32 |
| 120 | 10 | 7.5% | 109 | 6.8% | 124 |
| 300 | 4 | 3.0% | 25 | 1.6% | 202 |

## D4 birth PRIOR eligibility — low support preserved

| H sec | Positive eligible | Positive % | Control eligible | Control % | Median positive lead sec |
|---:|---:|---:|---:|---:|---:|
| 1 | 7 | 77.8% | 87 | 70.2% | 60 |
| 5 | 7 | 77.8% | 86 | 69.4% | 56 |
| 10 | 7 | 77.8% | 82 | 66.1% | 51 |
| 15 | 7 | 77.8% | 80 | 64.5% | 46 |
| 20 | 5 | 55.6% | 69 | 55.6% | 64 |
| 25 | 4 | 44.4% | 67 | 54.0% | 77 |
| 30 | 4 | 44.4% | 60 | 48.4% | 72 |
| 60 | 4 | 44.4% | 28 | 22.6% | 42 |
| 120 | 2 | 22.2% | 9 | 7.3% | 706.5 |
| 300 | 1 | 11.1% | 0 | 0.0% | 1,233 |

Do not infer a D4 population law from these counts. They only establish that several frozen D4 births were causally testable prior.

## D5 birth PRIOR eligibility — single case only

The lone D5 birth is PRIOR-eligible at every active H from `H=1` through `H=60`; its actual lead declines from 64 seconds at H=1 to 5 seconds at H=60. It is no longer prior-eligible by H=90.

Controls: 7/8 exact-D4 stops are prior-eligible at H=1 through H=15; 5/8 at H=20 and H=25; 4/8 at H=30; 2/8 at H=60; 1/8 at H=90 and H=120.

This is a case study only, not validation of a general D5 rule.

## Immediate interpretation

The PRIOR search is empirically viable and must remain primary:

- roughly two-thirds of positive D1-D3 births have at least one second of post-confirmation predecessor information available before the next-stage onset;
- about 60-65% still have 10-15 seconds of predecessor information before onset;
- roughly half remain testable around H=20-30;
- D4/D5 have meaningful individual prior windows but insufficient support for broad laws.

The next step is predictive validation on these same eligible positive/control rows. If a PRIOR H validates, trade research begins from the exact `RULE_READY(D,H)` timestamp. The `+0/+H` detector-relative clock is used only for cases/subfamilies where PRIOR prediction does not validate.

No protected component was modified and no play was promoted.
