# NG Exhaustion Aftermath / Transition Discovery Snapshot — 2026-08-17

Status: **EXPLORATORY DISCOVERY ONLY — SEPARATE FROM THE COMPLETED RUNWAY CLOCK.**

Clock source-of-truth freeze:
- branch: `chatgpt/ng-exhaustion-runway-clock-20260817`
- completed clock head: `637778d6f460940379ac0feaf8223be47971c11f`
- completion handoff: `CHATGPT_HANDOFF_NG_EXHAUSTION_CLOCK_COMPLETE_20260817.md`

Aftermath research branch:
`chatgpt/ng-exhaustion-aftermath-20260817`

This file preserves what was discovered while finishing the clock so a new chat can investigate it without changing or retuning the completed runway clock.

## The separate question

The completed runway clock asks:

> How much runway is likely left in the **current corresponding price leg**?

This new lane asks a different question:

> What does an exhaustion episode itself tell us about the **market state after that exhaustion episode**, including the next exhaustion episode and the subsequent tape?

These are deliberately independent targets.

## Baseline serial-memory finding

Order detected exhaustion events chronologically within each day and compare each event with the next detected exhaustion event on that same day.

Using whether the current oriented exhaustion has crossed through zero inside the post-t0 +60 second window:

- if exhaustion is still alive through +60s, the next exhaustion episode has the **same polarity roughly 60–62%** of the time;
- if exhaustion has collapsed through zero by +60s, next-event polarity is roughly **50/50**.

The two-half reconstruction observed approximately:

- reveal alive-at-60: `n=546`, same-next-polarity `62.27%`;
- reveal collapsed-by-60: `n=1168`, same-next-polarity `50.60%`;
- held-out alive-at-60: `n=533`, same-next-polarity `60.23%`;
- held-out collapsed-by-60: `n=1174`, same-next-polarity `50.34%`.

Interpretation: persistent exhaustion has serial directional memory. The apparently coin-flip collapsed population is likely a mixture of different transition states rather than one random population.

## Strong candidate inside persistent / alive-at-60 exhaustion

A much more concentrated same-direction candidate appeared when persistent exhaustion also retained extreme same-side late aggressor flow.

Exploratory condition, stated in the form used during screening:

- current exhaustion remains alive through +60s;
- roughly `95%+` of aggressor volume over seconds `+41..+60` remains aligned with the current exhaustion polarity;
- broader aligned flow strengthens materially from t0 to +60 (screen used about `>0.40` improvement);
- final-20-second oriented roll-20 flow is extremely one-sided (screen used about `>0.933`).

Observed next-exhaustion same-polarity rates:

- reveal: `40/47 = 85.1%`;
- held-out: `37/42 = 88.1%`.

Combined descriptive total: `77/89 = 86.5%`.

This is the strongest currently preserved candidate with a nontrivial sample. It is **not frozen doctrine** because several candidate combinations were screened while exploring the split.

## Tighter opposing-book candidate

A narrower cell also appeared when the late same-side aggressor flow was extreme while the resting 10-level book leaned against that flow.

Observed same-next-polarity rates:

- reveal: `19/21 = 90.5%`;
- held-out: `16/18 = 88.9%`.

Combined descriptive total: `35/39 = 89.7%`.

This is especially interesting mechanistically — aggressors may be repeatedly driving through opposing resting liquidity — but the total sample is only 39 and multiple conditions were screened. Treat it as a **high-priority candidate**, not a rule.

## The collapsed ~50/50 group splits into two regimes

The key discovery is that collapse timing alone does not explain the next event. The tape state **after/through the collapse** appears to separate continuation from reversal.

### A. Collapse + original-side flow reasserts

If exhaustion collapses but late aggressor/roll-20 flow reasserts the original polarity, the next exhaustion tends to repeat the original polarity.

Observed same-next-polarity rate:

- reveal: about `75.5%`;
- held-out: about `72.6%`.

The exact threshold/cell definition used during exploratory screening must be reconstructed and audited before this percentage is treated as a formal result. Do not infer missing counts from these rounded rates.

### B. Collapse + genuine late flow reversal

A cleaner opposite regime appeared when, after collapse:

- final-20-second oriented roll-20 flow is strongly opposite the original polarity (screen used approximately `<= -0.778`);
- essentially all late aggressor volume is on the opposite side.

Then the **next exhaustion episode flips polarity**:

- reveal: `53/70 = 75.7%` flips;
- held-out: `58/72 = 80.6%` flips.

Combined descriptive total: `111/142 = 78.2%` flips.

This is currently the cleanest candidate inside the former coin-flip population.

## Important negative finding

**How quickly exhaustion died by itself did not consistently separate the next-state outcome.**

Simple collapse-time buckets such as 0–10s, 10–20s, 20–30s, etc. did not reproduce cleanly across halves. The useful discriminator appears to be the **state of order flow at/after the collapse**, not merely the number of seconds until zero.

Therefore do not reduce this lane to another duration model.

## Plain-language working model

The emerging state machine is:

1. **Persistent exhaustion + strengthening same-side flow**
   - directional regime likely still active;
   - next exhaustion often repeats the same polarity (~86–88% in the screened candidate).

2. **Exhaustion collapses + same-side flow reloads/reasserts**
   - current exhaustion died, but the market appears to reload in the same direction;
   - next exhaustion often repeats (~73–76% in the exploratory split).

3. **Exhaustion collapses + flow genuinely switches sides**
   - transition/reversal state;
   - next exhaustion often flips (~76–81%).

4. **Exhaustion collapses without a decisive late-flow state**
   - remains much closer to genuinely uncertain.

Potential future vocabulary, not yet frozen:
- `continuation_exhaustion`
- `reload_transition`
- `reversal_exhaustion`
- `indeterminate_collapse`

Do not add these names to permanent Frankie until they survive formal blind validation.

## Second independent target: post-exhaustion price/tape aftermath

The serial next-exhaustion result is only one target. The new lane must separately study what the actual **trade tape does after exhaustion ends**, without using the corresponding ZigZag leg as the target.

For each exhaustion episode, anchor on an exhaustion endpoint such as `zero_s` or another explicitly frozen endpoint definition, then measure the raw trade-price/tape aftermath at fixed horizons such as:

`+5, +10, +20, +30, +60, +120, +300 seconds after exhaustion endpoint`

Candidate descriptive outcomes:
- same-direction continuation from exhaustion polarity;
- reversal against exhaustion polarity;
- chop/no meaningful displacement;
- favorable/adverse ticks;
- max favorable/adverse excursion;
- time to first 3t / 5t displacement after exhaustion endpoint;
- next exhaustion polarity and time-to-next-exhaustion;
- aggressor-flow and book transition state.

This target must remain independent of the runway clock's corresponding-price-leg duration label.

## Data sources already available

Reveal-first artifact:
- workflow run `31984194953`
- artifact ID `9273273233`
- digest `sha256:127e936355be479398e14f20f071f81b0d22a2975b02e87a1a3e0a044ec023e1`
- reveal events: 1,718

Held-out blind input artifact:
- artifact ID `9274443976`
- SHA-256 `224be8b033c1a03d638d7b84aef849363067e1961e9945e72bc86b52c3d01c39`
- held-out events: 1,711

Held-out actual reveal/score artifact:
- workflow run `31989542165`
- artifact ID `9274882157`
- digest `sha256:9c29dd6add1940172f11ac9e72d5f3396262829eeb46487eb89d88b161a9dece`

Authoritative raw continuous NG MBP-10 days remain on S3. The existing reveal/score code shows the exact four held-out days and rebuild path.

## Required validation discipline for the next chat

1. Reconstruct the serial-memory table from source artifacts before trusting this snapshot.
2. Reconstruct every exploratory threshold from code/data; do not treat rounded thresholds above as sacred.
3. Use the 1,718-event reveal half for discovery only.
4. Freeze the candidate rule(s) before inspecting the 1,711-event held-out outcome for that target.
5. Report day-level results, not only pooled percentages.
6. Prefer simple monotone/quantile-derived thresholds over hand tuning.
7. Correct for the fact that multiple candidate combinations were screened during exploration.
8. Keep the serial-next-exhaustion target separate from the post-exhaustion-price/tape target.
9. Keep both separate from the already-completed runway clock.
10. No permanent Frankie brain/schema/roles/plays/datapoints/workflow mutation during discovery.

## Do not contaminate the completed clock

The completed runway clock is frozen on:
`chatgpt/ng-exhaustion-runway-clock-20260817` @ `637778d6f460940379ac0feaf8223be47971c11f`

Do not:
- change its pre-family classifier;
- change the frozen A +60 classifier;
- change reveal runway baselines;
- feed these aftermath thresholds into runway seconds;
- use post-exhaustion future price inside the clock;
- reinterpret this research as evidence to retune the clock.

This aftermath lane is deliberately a second independent research piece.
