# S129 / S130 Consolidated Analysis Handoff

Status: **analysis/handoff only**. This document consolidates Frankie's S129 findings, ChatGPT's interpretation, the S130 hydration diagnostic, and the agreed next-run procedure. It makes **no change to Frankie's brain, schema, specialist roles, spawn path, or datapoint surface**.

## Purpose

Use this file as the first analysis document for the next chat. It exists so the next operator can recover the September findings without reconstructing the prior conversation or accidentally turning diagnostic observations into brain edits.

Primary branch: `chatgpt/burn-hh-12m-s125`

Primary S129 account: `S129_FRANKIE_G3_ACCOUNT.md`

Frozen S129 forecast artifact:
`research/kalshi/forecasts/frankie_g3_s129_chatgpt_current/g3_s129_current_frankie_blind_frozen.json`

Frozen S129 forecast commit:
`8c0b48ac5a44cbae7569ccd28e05c176744500f8`

September window: **2025-09-08 through 2025-09-19**

Starter anchor: **2025-09-05 close = 3.026**

Scored contract: **NGV25 for the full block**. No seam inside Sep. 8-19; next known seam is Sep. 25.

---

# 1. S129 run identity and integrity

S129 used current Frankie as coordinator with the current brain/schema and S128-era safeguards. The clean historical runner exposed the current 31-channel decision-state schema, but only four channel families were materially populated in that clean replay:

- COT
- flow calendar
- day-of-week/calendar state
- curve regime

All other unavailable historical fields stayed unavailable/null. They were not synthesized.

Important integrity label: **S129 is not a pristine holdout blind**. The current brain contains historical provenance from earlier G3-era work and setup inspection exposed older outcome artifacts. S129 is therefore a current-Frankie learning replay and diagnostic run. It is meaningful for discussion, but it must not be treated as independent holdout evidence that can directly teach the brain.

No new datapoints were added. Protected specialist roles, `spawn.py`, and G24 remained untouched.

---

# 2. S129 headline result

- Endpoint MAE: **$529/day**
- Endpoint RMSE: **$578.1/day**
- Maximum absolute endpoint error: **$950**
- P50 direction: **5/10**
- CALL-only direction: **2/4**
- Day-local intraday curve MAE: **$336.8**
- Forecast cumulative close from Sep. 5 anchor, excluding unforecast weekend gaps: **-$2,000**
- Actual final cumulative close from Sep. 5 anchor: **-$1,080**

S129 deliberately emitted zero-gap weekend bridges when causal weekend evidence was unavailable. That was a no-fabrication decision, not a prediction that the market would reopen unchanged.

---

# 3. What Frankie believed before reveal

Frankie carried a **weak-down inherited chain** into the first week.

Blind operating thesis:

1. **Sep. 8 Monday** — Monday magnitude prior was elevated, but causal weekend-gap evidence was unavailable. Weak-down Friday handoff only. Frankie ABSTAINed with a small downside P50.
2. **Sep. 9-10** — GSCI/BCOM roll windows were live. COT covering opposed the inherited weak-down chain. Frankie kept downside continuation low-confidence instead of upgrading it.
3. **Sep. 11 storage Thursday** — event timing licensed a much larger range, but same-print consensus and causal post-print tape were unavailable. D abstained on side; P50 retained the weak-down chain with a storage-shaped stress curve.
4. **Sep. 12 Friday** — final GSCI roll day / BCOM still active, but no tape delivery. E retained only a small downside residual and abstained.
5. **Sep. 15 Monday** — weak-down Friday handoff plus final BCOM roll day, but no causal weekend-gap evidence. B abstained and carried only a small downside P50.
6. **Sep. 16-17** — roll windows had cleared and newly published COT showed further short covering. C allowed a low-confidence upside covering drift for two sessions.
7. **Sep. 18 storage Thursday** — event timing implied large range but not sign. D abstained; P50 used downside stress.
8. **Sep. 19 Friday** — roll programs were over; options/futures expiry approached, but the scored-leg seam was not active. E retained a small downside residual and abstained.

Both weekend bridges were zero-gap / low-confidence because causal weekend-cycle evidence was unavailable.

---

# 4. Day-by-day revealed account

| Date | Owner | S129 forecast | Actual | Error | Direction | Post-reveal reading |
|---|---|---:|---:|---:|---|---|
| Sep 8 | B | -250, ABSTAIN | +190 | -440 | Miss | Weak Friday downside survived into Monday even though side authority was insufficient. Positive reopen gap also displaced cumulative path. |
| Sep 9 | C | -300, CALL | +120 | -420 | Miss | Roll-window timing plus inherited chain became too directional. COT covering was recognized but did not suppress the downside CALL. |
| Sep 10 | C | -250, CALL | -750 | +500 | Hit | Direction was right; magnitude far too small. |
| Sep 11 | D | -550, ABSTAIN | -1,010 | +460 | Hit | Storage-day large-range framing was useful, but realized amplitude was still under-sized. Abstention on sign was structurally appropriate. |
| Sep 12 | E | -200, ABSTAIN | +280 | -480 | Miss | Weak-down residual persisted one session too long after the large Thursday move. |
| Sep 15 | B | -250, ABSTAIN | +200 | -450 | Miss | Same family as Sep. 8: weak Friday state became Monday's default P50 without causal weekend evidence. |
| Sep 16 | C | +250, CALL | +1,200 | -950 | Hit | Cleared roll windows + COT covering caught reversal direction correctly. Largest magnitude failure. |
| Sep 17 | C | +150, CALL | -430 | +580 | Miss | Covering thesis persisted one day too long after the Sep. 16 rally. |
| Sep 18 | D | -450, ABSTAIN | -1,360 | +910 | Hit | Storage-day downside stress caught direction and event scale class but dramatically under-sized the move. |
| Sep 19 | E | -150, ABSTAIN | -250 | +100 | Hit | Cleanest endpoint of the block. |

CALL-only record:

- Sep. 9 DOWN — wrong
- Sep. 10 DOWN — right
- Sep. 16 UP — right
- Sep. 17 UP — wrong

The 2/4 CALL score is therefore not random sign-flipping. The two misses are clustered around **thesis persistence**: downside persisted too long into Sep. 9; upside covering persisted too long into Sep. 17.

---

# 5. Frankie's S129 findings

## 5.1 Dominant issue: authority persistence, not simply missing datapoints

The central S129 diagnostic is that the surviving contextual signals were sometimes allowed to own the curve for too long when direct causal confirmation was unavailable.

Observed persistence failures:

- weak Friday/down-chain state carried into Monday when weekend evidence was unavailable;
- roll-calendar context helped keep an inherited sign alive even though roll schedules are clocks, not signs;
- COT covering correctly identified the Sep. 16 upside transition but was then allowed to persist into Sep. 17 without a fresh delivery test.

This is consistent with the broader G24 authority doctrine: context can propose a move; delivered price/flow should decide whether the story remains alive.

## 5.2 Magnitude was too compressed on the largest correct-direction moves

Largest actual moves:

- Sep. 11: **-$1,010** vs S129 **-$550**
- Sep. 16: **+$1,200** vs S129 **+$250**
- Sep. 18: **-$1,360** vs S129 **-$450**

Sep. 10 was also **-$750** actual vs **-$250** forecast.

Frankie often identified the correct regime/transition but expressed far too little amplitude when fast confirmation channels were unavailable.

This does **not** justify simply making numbers larger. The correct next question is whether the existing magnitude-authority path can express fat-tail/event-day scale without requiring a high-confidence directional CALL.

## 5.3 Roll timing is useful as a clock, dangerous as a directional substitute

Roll windows may increase expected path complexity and flow intensity, but the revealed September block does not support using roll timing to preserve or strengthen inherited sign when delivered price evidence is absent.

## 5.4 Weekend no-data handling was honest; Monday directional inheritance is the questionable part

Zero-gap bridges were correct when the weekend gap was unknowable. The problem was separate: weak Friday directional residue still became Monday's default P50.

The candidate mechanism is not "predict positive Monday gaps." The candidate is that **Monday directional ownership should be allowed to reset when weekend evidence is unavailable rather than automatically inheriting a weak Friday chain**.

## 5.5 COT covering behaved like a transition signal, not a durable two-day trend signal

COT covering plus cleared roll windows correctly helped flip Sep. 16 UP. The mistake was extending the same slow positioning thesis into Sep. 17 after the market had already delivered a very large upside session.

Candidate mechanism: **after an outsized delivery in the direction of a slow positioning signal, that signal's directional authority should decay unless fresh causal evidence confirms continuation**.

## 5.6 Storage Thursday behavior was structurally sensible

D abstained on both storage Thursdays because same-print consensus and causal post-print tape were unavailable. That was correct under the blind wall.

The event calendar correctly identified both days as capable of large path expansion. But the two bearish outcomes do not support a bearish storage rule.

Operational distinction:

- event calendar may own **range/timing**;
- event calendar alone may not own **sign**.

---

# 6. ChatGPT interpretation / notes

These notes are analysis only and are intentionally not written into Frankie's brain.

## 6.1 S129 is more informative than S130 for discussion

S129 is the meaningful September current-Frankie replay because its forecast was frozen before the scoring pass. It is still not a pristine holdout because of historical provenance, but it is cleaner than S130.

## 6.2 The starved run equaled or beat the hydrated diagnostic

S130 historical hydration was performed only as a diagnostic after September actuals had already been revealed. It restored more existing slow-state information, but did not improve the key forecast result.

S129 starved:

- endpoint MAE **$529**
- RMSE **$578.1**
- max error **$950**
- direction **5/10**
- CALL **2/4**
- curve MAE **$336.8**

S130 hydrated diagnostic:

- endpoint MAE **$529**
- RMSE **$599.4**
- max error **$1,025**
- direction **5/10**
- CALL **2/4**
- curve MAE **$332.4**

Hydration slightly improved day-local curve MAE by about $4.4 but worsened RMSE and worst-day error while leaving endpoint MAE and direction unchanged.

Conclusion: **do not use hydration as the default historical-run process**.

## 6.3 Why hydration is rejected

The extra restored inputs were mostly slower balance/context channels. Without historical weather forecast vintages, direct causal tape/price delivery, structure/options, and some other fast confirmation channels, those extra slow signals sometimes pushed Frankie harder in the wrong direction.

Therefore the September result argues against the idea that Frankie simply needs more historical data. It points more strongly toward **authority assignment, authority decay/reset, and magnitude expression**.

## 6.4 Do not add datapoints in response to S129/S130

The agreed stopping point remains the existing ~1,800+ served fields. Frankie should see the current surface and decide whether it is sufficient over more runs. September does not justify adding feeds.

## 6.5 Do not teach from S129 or S130 yet

S129 is not a pristine holdout. S130 is explicitly post-reveal. Neither should directly alter the brain.

Use them to generate testable hypotheses for future clean chronological groups only.

---

# 7. Candidate hypotheses for future pristine groups

These are **test proposals, not lessons**:

1. **Unavailable weekend evidence should neutralize weak Friday directional inheritance rather than merely setting the gap to zero.**
2. **Roll schedules are clocks/intensity context, not directional confirmation.**
3. **Slow positioning signals such as COT covering should decay after a large delivered move unless fresh causal price/flow evidence confirms continuation.**
4. **Event calendars may widen the magnitude/range prior without assigning sign.**
5. **When Frankie gets the directional transition right but repeatedly under-sizes large moves, inspect the existing magnitude-authority path before adding any datapoints.**

These hypotheses must earn authority on future clean groups before any brain edit.

---

# 8. Explicit things NOT to learn from September

Do not write any of the following into the brain from S129/S130:

- "September Mondays gap up."
- "Storage Thursdays are bearish."
- "Roll windows are bearish."
- "COT covering means buy for two days."
- any fitted endpoint magnitude derived from Sep. 8-19 actual outcomes.
- any rule whose only support comes from S130 hydration.

---

# 9. Agreed future historical-run procedure

For future groups, do **not** hydrate historical state after the fact just to make the replay richer.

Use this procedure:

1. Run **current Frankie brain/schema/current improvements**.
2. Use only historical state available through the normal current decision-state path at that cutoff.
3. Missing feeds stay unavailable/null. Do not backfill them merely to enrich a historical replay.
4. Give Frankie the explicit real starter anchor before the first session.
5. Run the full group mechanically and quickly.
6. Freeze the entire blind forecast set before revealing actuals.
7. Reveal actuals once.
8. Score endpoint and full intraday curve.
9. Render the full comparison.
10. Only clean chronological evidence may eventually teach Frankie.

Do not re-audit the architecture before every group unless the run itself throws a contract or integrity error.

---

# 10. Standing constraints for the next chat

- **No new datapoints.** ~1,800+ remains the stopping point.
- Do not broadly change Frankie settings/schema/inputs.
- Do not rewrite A-E specialist roles.
- Do not touch `research/kalshi/spawn.py`.
- Do not rebuild S114 wind/solar.
- Do not reopen M-13.
- Preserve blind/causal walls.
- Blind artifacts remain immutable.
- Frankie remains the coordinator.
- Frankie forecasts a **full curve**, not merely a close.
- ChatGPT operates Frankie; do not drift to Claude/API.
- G24 remains frozen/untouched.
- S130 hydration artifacts are diagnostic/provenance only and are not the default historical input path.
- Do not change Frankie's brain based on this document.

---

# 11. Bottom line for the next chat

The main September finding is:

> Frankie did not primarily fail because the historical runner exposed too few datapoints. He got 5/10 directions and caught several of the largest directional moves, but slow/contextual signals were allowed to persist without fresh delivery confirmation, and magnitude was much too compressed on the largest correct-direction moves.

The strongest next research direction is therefore **authority decay/reset + magnitude expression inside the existing framework**, tested on future clean groups. Do not hydrate old groups and do not add datapoints in response to S129/S130.
