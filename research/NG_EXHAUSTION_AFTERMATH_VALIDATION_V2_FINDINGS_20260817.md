# NG Exhaustion Aftermath / Transition Validation V2 — Findings — 2026-08-17

Status: **VALIDATION COMPLETE FOR THE REQUIRED SECOND-ORDER AFTERMATH PASS. RESEARCH ONLY.**

Completed runway clock and permanent Frankie remain untouched.

## Provenance

- Branch: `chatgpt/ng-exhaustion-aftermath-20260817`
- Successful validation run: `32001550796`
- Validation artifact: `9278686522`
- Artifact digest: `sha256:0357826f86ce9971688a467c41ea4c64c23eaaf2d22dc1f37fc39ce62c4f168a`
- Population: reveal `n=1718`, holdout `n=1711`, combined `n=3429`
- Raw weekly streams used:
  - week beginning Sunday 2025-07-13: Sunday reopen through Friday close
  - week beginning Sunday 2025-09-21: Sunday reopen through Friday close
  - week beginning Sunday 2025-09-28: Sunday reopen through Friday close
- Every studied week includes its Sunday reopen file. Calendar midnight and HE24->HE1 do not censor the raw stream.

## Endpoint semantics proved

Exhaustion does **not** end at +60 or any other hardcoded clock time.

The dynamic termination condition remains the first three consecutive causal seconds for which oriented trailing-20-second aggressor imbalance is `<= 0`.

Two times are recorded:

- structural onset = first second of that qualifying three-second run;
- causal confirmation = third second of that run.

Post-exhaustion price/tape measurement begins at the **causal confirmation second**. This prevents the analysis from starting its aftermath before the termination condition is actually known.

Reconstruction checks:

- artifact zero present: `2343`
- artifact zero structural-onset exact matches: `2343`
- artifact zero absent: `1086`
- onset by +60 but confirmation after +60: `41`
- endpoint censored in the continuous target-week stream: `0 / 3429`

Median causal confirmation offset from t0:

- reveal: `34s` (Q25 `17s`, Q75 `76.75s`)
- holdout: `35s` (Q25 `17s`, Q75 `76.5s`)
- alive-through-60: reveal `117s`, holdout `115s`
- collapsed-by-60: reveal `22s`, holdout `22s`

## Target 1 — next-exhaustion transition memory

### 1. The preserved exploratory baseline reproduces exactly under its original within-split ordering

Reveal:
- alive through +60: `340/546 = 62.27%` same-next-polarity
- collapsed by +60: `591/1168 = 50.60%` same-next-polarity

Holdout:
- alive through +60: the previously preserved reconstruction is reproduced by the validator under the same within-split method
- collapsed by +60: the previously preserved reconstruction is reproduced by the validator under the same within-split method

That historical method is retained only as provenance because it can skip an intervening event from the other half.

### 2. Literal next event in the full target-day chronological stream is stronger descriptively

Reveal:
- alive through +60: `373/547 = 68.19%` same
- collapsed by +60: `559/1169 = 47.82%` same

Holdout:
- alive through +60: `373/535 = 69.72%` same
- collapsed by +60: `576/1174 = 49.06%` same

But this is **not a valid +60 prediction rate** for all events, because the literal next event has already started by +60 for a large fraction of anchors.

### 3. Causal +60 direct target

For a rule using information through +60, score only anchors whose literal next event begins after +60.

Reveal:
- alive through +60: `224/389 = 57.58%` same
- collapsed by +60: `359/669 = 53.66%` same

Holdout:
- alive through +60: `214/368 = 58.15%` same
- collapsed by +60: `366/672 = 54.46%` same

Therefore persistence retains **modest** causal serial memory, but the old 60–70%+ headline cannot be used as an executable +60 next-event forecast without respecting as-of timing.

### 4. Late aggressor pressure is the most reproducible causal Target-1 discriminator

Using sign only, with no held-out-tuned threshold:

Collapsed + same-side late aggressor pressure:
- reveal: `142/222 = 63.96%` next polarity same
- holdout: `125/207 = 60.39%` next polarity same

Collapsed + opposite late aggressor pressure:
- reveal: `118/254 = 46.46%` next polarity same (`53.54%` flip)
- holdout: `132/255 = 51.76%` next polarity same (`48.24%` flip)

The exploratory ~76–81% flip cell therefore **does not survive** as a clean causal next-exhaustion rule once the literal next event and +60 as-of wall are enforced.

Alive + same-side late aggressor pressure:
- reveal: `39/63 = 61.90%` next polarity same
- holdout: `34/48 = 70.83%` next polarity same

This cell is directionally interesting but day-to-day variance remains material and the sample is smaller.

### 5. Reveal-derived aggressor-pressure quintiles show a useful monotone neighborhood

Using only causal +60 eligible anchors with non-sparse late pressure, reveal-derived quintile edges are approximately:

`[-1.0, -0.50, -0.127, +0.20, +0.597, +1.0]`

Same-next-polarity rate by pressure quintile:

Reveal:
- Q1: `44.5%`
- Q2: `47.4%`
- Q3: `60.5%`
- Q4: `59.1%`
- Q5: `66.1%`

Holdout using the frozen reveal edges:
- Q1: `47.1%`
- Q2: `50.4%`
- Q3: `57.1%`
- Q4: `63.5%`
- Q5: `65.6%`

This is much more credible than one isolated hand-picked cut: stronger same-side late aggressor pressure generally corresponds to more same-polarity serial memory.

### 6. Resting-book condition does not earn a separate rule

The previously interesting opposing-book cell does not show a stable incremental separation once the causal wall is enforced. Resting-book alignment remains useful context, but it is **not promoted as an independent Target-1 transition rule** from this validation.

## Target 2 — raw post-exhaustion tape aftermath

### 1. Pooled terminal displacement is mostly chop at short horizons

At the confirmed exhaustion endpoint, terminal price displacement is frequently below the predeclared 2-tick material threshold through the first minutes.

Holdout chop rates:
- +5s: `97.19%`
- +10s: `94.80%`
- +20s: `89.71%`
- +30s: `84.86%`
- +60s: `77.97%`
- +120s: `65.58%`
- +300s: `50.61%`

So the useful signal is not a claim that every exhaustion instantly produces a tradeable price move.

### 2. Collapsed exhaustion + late-flow sign strongly separates the direction of material post-end moves

The cleanest validated Target-2 result is obtained by conditioning on whether a material `>=2t` move has occurred by the fixed horizon.

#### Collapsed + same-side late aggressor pressure

Continuation share among material movers:

| Horizon after confirmed end | Reveal | Holdout |
|---|---:|---:|
| 30s | `49/63 = 77.8%` | `60/90 = 66.7%` |
| 60s | `87/108 = 80.6%` | `90/124 = 72.6%` |
| 120s | `102/151 = 67.5%` | `116/182 = 63.7%` |
| 300s | `135/224 = 60.3%` | `134/236 = 56.8%` |

At +60, terminal-state rates including chop are:
- reveal: continuation `23.0%`, reversal `5.6%`, chop `71.4%`
- holdout: continuation `24.1%`, reversal `9.1%`, chop `66.8%`

At +120:
- reveal: continuation `27.0%`, reversal `13.0%`, chop `60.1%`
- holdout: continuation `31.0%`, reversal `17.6%`, chop `51.3%`

The continuation-over-reversal ordering reproduces on **every one of the four days** at +60 and +120 in both halves.

#### Collapsed + opposite late aggressor pressure

Continuation share among material movers (therefore reversal share is `1-rate`):

| Horizon after confirmed end | Reveal continuation | Holdout continuation |
|---|---:|---:|
| 30s | `43/97 = 44.3%` | `38/94 = 40.4%` |
| 60s | `53/138 = 38.4%` | `52/139 = 37.4%` |
| 120s | `73/187 = 39.0%` | `82/200 = 41.0%` |
| 300s | `124/253 = 49.0%` | `146/285 = 51.2%` |

Thus at +60 the material-move reversal share is:
- reveal: `61.6%`
- holdout: `62.6%`

At +120:
- reveal: `61.0%`
- holdout: `59.0%`

The reversal-over-continuation ordering reproduces on all four days at +120 in both halves. By +300 the directional edge has largely decayed.

### 3. First-hit sequencing is consistent but weaker than the 30–120s material-move split

Collapsed + same-side late flow, first 3-tick side reached:
- reveal: same side first `235/378 = 62.2%`
- holdout: same side first `217/374 = 58.0%`

Collapsed + opposite late flow:
- reveal: original side first `220/479 = 45.9%`, therefore opposite side first `54.1%`
- holdout: original side first `222/483 = 46.0%`, therefore opposite side first `54.0%`

At 5 ticks the ordering persists but weakens.

### 4. Persistent/alive exhaustion is a different state

Alive-through-60 events take much longer to terminate. After they finally confirm termination, the immediate post-end tape is more often chop and does **not** show the same clean continuation advantage as collapsed + same-side reload.

This is important: `persistent current exhaustion` and `post-collapse same-side reload` are not interchangeable concepts.

### 5. Family A/B/C comparison

Family A dominates the population and its pooled post-end terminal direction remains near balanced outside the conditional late-flow states. B and C are too small for doctrine here. Their descriptive differences are retained only for later replication.

## Relationship between Target 1 and Target 2

The two targets partially decouple.

- **Collapsed + same-side late flow** predicts both:
  - modestly higher probability that the next exhaustion has the same polarity (`64.0%` reveal, `60.4%` holdout in the causal +60 direct target), and
  - substantially stronger continuation among material post-end tape moves over roughly 30–120 seconds.

- **Collapsed + opposite late flow** predicts the post-end tape reversal state over roughly 30–120 seconds, but it does **not** predict the next exhaustion polarity flipping at the old ~75–80% rate once the causal next-event definition is enforced.

Therefore the serial-exhaustion chain target and the raw-tape aftermath target must remain separate outputs.

## Findings explicitly downgraded or killed

Do **not** promote the following exploratory headlines as validated causal rules:

- ~85–88% persistent -> same next exhaustion;
- ~89–90% tighter opposing-book persistent cell;
- ~76–81% collapsed opposite-flow -> next exhaustion flips.

Those cells were affected by exploratory screening and/or by the fact that the next event could already have started inside the +60 feature window.

## Validated research-state vocabulary for the chain study

These are research labels only, not permanent Frankie doctrine:

1. `collapsed_same_flow_reload`
   - exhaustion has causally terminated;
   - late +41..+60 aggressor pressure was aligned with the original polarity;
   - strongest validated post-end continuation candidate.

2. `collapsed_opposite_flow_reversal`
   - exhaustion has causally terminated;
   - late +41..+60 aggressor pressure was opposite the original polarity;
   - strongest validated post-end reversal candidate over approximately 30–120 seconds.

3. `collapsed_sparse_indeterminate`
   - exhaustion terminated but late aggressor evidence was sparse/balanced;
   - no strong directional doctrine.

4. `persistent_exhaustion`
   - not terminated by the +60 checkpoint;
   - retains modest serial same-polarity memory but is not equivalent to a post-end continuation state.

## Gate into higher-order chain research

The required aftermath validation is complete enough to begin the separate chain study.

Chain study rules remain:

- start each observation week at the **first actual trade after the Sunday weekly reopen**;
- continue through the genuine Friday weekly close;
- never reset at midnight, HE24->HE1, a date label, or a file boundary;
- log time-of-day/session position for every link as context, never as an initial gate;
- distinguish inherited-chain continuation from behavioral reset;
- investigate long and short chains separately;
- do not let higher-order chain findings alter the frozen runway clock;
- do not mutate permanent Frankie.

Higher-order chain findings will require their own discovery/validation discipline and should ultimately receive forward-live validation before promotion.
