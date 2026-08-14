# S129 Frankie G3 Account — September 8–19, 2025

Status: **post-reveal analysis of the frozen S129 replay**.  This document explains what the S129 run did and what the revealed September path says about it.  It is **not** a new forecast, not a refinement, and not permission to write lessons into Frankie's brain.

## Run identity

- Window: 2025-09-08 through 2025-09-19.
- Starter anchor: 2025-09-05 close = **3.026**, cumulative $0.
- Scored leg: **NGV25 for the entire window**.  There is no contract seam inside this block; the next known seam is 2025-09-25.
- Operator: ChatGPT operating current Frankie as coordinator with the current brain/schema and S128-era safeguards.
- Frozen blind artifact: `research/kalshi/forecasts/frankie_g3_s129_chatgpt_current/g3_s129_current_frankie_blind_frozen.json`.
- Frozen forecast commit: `8c0b48ac5a44cbae7569ccd28e05c176744500f8`.
- Historical decision state exposed the current 31-channel schema, but only four channel families were materially populated in the clean historical runner: COT, flow calendar, day-of-week/calendar state, and curve regime. Missing channels remained unavailable/null and were not synthesized.
- Integrity label: **not pristine holdout blind**.  The current brain contains historical provenance from older G3-era work and setup inspection exposed old outcome artifacts.  S129 is therefore a current-Frankie learning replay, not a score that may independently validate or teach the system.

## S129 headline result

- Endpoint MAE: **$529/day**.
- Endpoint RMSE: **$578.1/day**.
- Maximum absolute endpoint error: **$950**.
- P50 direction: **5/10**.
- CALL-only direction: **2/4**.
- Day-local intraday curve MAE: **$336.8**.
- Forecast cumulative close from the Sep. 5 anchor, excluding unforecast weekend gaps: **-$2,000**.
- Actual final cumulative close from the Sep. 5 anchor: **-$1,080**.

The endpoint metrics above grade each forecast session's day move.  The cumulative path additionally contains realized reopen/weekend gaps.  S129 deliberately emitted zero-gap bridges when causal weekend evidence was unavailable rather than inventing a gap.

## What Frankie believed before reveal

S129 carried a **weak-down inherited chain** into the first week.  Frankie treated the scheduled GSCI/BCOM roll windows as timing/context rather than enough evidence for a high-confidence call, but in the absence of tape and weather delivery the weak-down chain still became the default P50 direction.

The blind operating thesis was:

1. **Sep. 8 Monday:** elevated Monday magnitude prior, but no causal weekend-gap evidence; weak-down Friday handoff only, therefore ABSTAIN with a small downside P50.
2. **Sep. 9–10:** GSCI/BCOM roll windows live.  COT covering opposed the inherited weak-down chain, so downside continuation was kept low-confidence rather than upgraded.
3. **Sep. 11 storage Thursday:** event timing licensed a much larger range, but same-print consensus and causal post-print tape were absent.  D abstained on side; P50 retained the weak-down chain with a storage-shaped downside stress curve.
4. **Sep. 12 Friday:** final GSCI roll day / BCOM still live, but no tape delivery.  E retained only a small downside residual and abstained.
5. **Sep. 15 Monday:** weak-down Friday handoff plus final BCOM roll day, but no causal weekend gap evidence.  B abstained and carried only a small downside P50.
6. **Sep. 16–17:** both scheduled roll windows had cleared and newly published COT showed further short covering.  C allowed a low-confidence upside covering drift for two sessions.
7. **Sep. 18 storage Thursday:** again, event timing implied large range but not sign.  D abstained; P50 used downside stress.
8. **Sep. 19 Friday:** roll programs were over; options/futures expiry was approaching but the scored-leg seam was not yet active.  E retained only a small downside residual and abstained.

Frankie also made both weekend bridges **zero-gap / low-confidence** because the causal weekend-cycle evidence was unavailable.  That was an intentional no-fabrication decision, not a claim that the market would actually reopen unchanged.

## Day-by-day revealed account

| Date | Owner | S129 | Actual day move | Error (forecast - actual) | Direction | Post-reveal reading |
|---|---|---:|---:|---:|---|---|
| Sep 8 | B | -250, ABSTAIN | +190 | -440 | Miss | Weak-down Friday inheritance survived into Monday even though side authority was explicitly insufficient. Separately, the unforecast positive weekend reopen gap displaced the cumulative path before the Monday session developed. |
| Sep 9 | C | -300, CALL | +120 | -420 | Miss | Roll-window timing plus inherited chain became too directional. COT covering was correctly recognized as opposition but was not strong enough in the decision logic to prevent the downside CALL. |
| Sep 10 | C | -250, CALL | -750 | +500 | Hit | The downside continuation was directionally right, but magnitude was far too small. The framework identified the chain direction yet did not license the realized scale. |
| Sep 11 | D | -550, ABSTAIN | -1,010 | +460 | Hit | Storage-day range expansion was directionally aligned and correctly treated as large-range potential, but the move was still materially under-sized. D's abstention was appropriate because sign was not causally observable at forecast time. |
| Sep 12 | E | -200, ABSTAIN | +280 | -480 | Miss | The weak-down residual persisted one session too long after the large Thursday move. Friday/roll context did not justify carrying downside without fresh delivery evidence. |
| Sep 15 | B | -250, ABSTAIN | +200 | -450 | Miss | Same failure family as Sep. 8: a weak Friday handoff became the default Monday P50 when causal weekend evidence was absent. The second weekend also reopened positively, adding cumulative displacement that the zero-gap bridge intentionally did not predict. |
| Sep 16 | C | +250, CALL | +1,200 | -950 | Hit | Clearing of the roll windows plus COT covering caught the reversal direction correctly. This was S129's strongest directional read and its largest magnitude failure: the realized upside was nearly five times the P50 move. |
| Sep 17 | C | +150, CALL | -430 | +580 | Miss | The covering thesis was extrapolated one day too long. Once the large Sep. 16 rally had occurred, continuing the same positive story without fresh price/tape delivery was not justified. |
| Sep 18 | D | -450, ABSTAIN | -1,360 | +910 | Hit | Storage-day downside stress caught direction and event scale class but still dramatically under-sized the realized move. This is another case where event-day range awareness was useful even though side remained formally unconfirmed. |
| Sep 19 | E | -150, ABSTAIN | -250 | +100 | Hit | Small downside residual was directionally right and relatively close. This was the cleanest endpoint of the block. |

CALL-only result:

- Sep. 9 DOWN: wrong.
- Sep. 10 DOWN: right.
- Sep. 16 UP: right.
- Sep. 17 UP: wrong.

Thus the **2/4 CALL score** is not a story of random sign flipping.  The failures cluster around *persistence*: downside persisted too long into Sep. 9 and upside covering persisted too long into Sep. 17.

## Frankie's S129 diagnosis

### 1. The dominant error was authority persistence, not absence of datapoints

S129's misses do not support a simple "more historical feeds would fix it" story.  The later S130 hydration diagnostic restored more existing slow-state information and did **not** improve endpoint MAE or direction.  Therefore the main S129 problem is better described as **which surviving signal was allowed to own the curve when direct causal confirmation was unavailable**.

The specific persistence failures were:

- weak Friday/down-chain state carried into Monday when weekend evidence was unavailable;
- roll-calendar context helped preserve a directional chain even though roll schedules are clocks, not signs;
- COT covering correctly identified the Sep. 16 upside transition but was then allowed to persist into Sep. 17 without a fresh delivery test.

### 2. S129 was often right about *event magnitude class* but too conservative about realized amplitude

The largest actual moves were:

- Sep. 11: -$1,010;
- Sep. 16: +$1,200;
- Sep. 18: -$1,360.

S129 got the P50 direction right on all three, but emitted only -$550, +$250, and -$450 respectively.  Sep. 10 was also directionally right at -$750 actual versus -$250 forecast.

So the block contains a different failure from G24's pure directional authority mistakes: **Frankie sometimes identified the correct regime/turn but compressed the magnitude too aggressively when fast confirmation channels were unavailable.**

That does *not* mean Frankie should invent larger numbers.  It means the next pristine runs should test whether the existing magnitude framework has enough authority to express fat-tail/event-day scale while the directional CALL remains conservative.

### 3. Roll timing was useful as a clock but dangerous as a directional substitute

S129 knew when GSCI and BCOM roll programs were active and when they cleared.  That timing helped frame Sep. 9–16.  But on Sep. 9–12, the lack of tape/weather delivery left the inherited weak-down chain as the default.  The revealed path says the schedule itself should not be allowed to keep a sign alive.

Candidate test for a future pristine group: **a roll window may increase expected path complexity/flow intensity, but absent delivered price evidence it should not strengthen inherited directional authority.**

### 4. Weekend no-data handling was honest, but the chain handoff still needs scrutiny

S129 did the correct causal thing by refusing to invent weekend gaps.  The zero-gap bridges should remain zero/unavailable when no causal weekend evidence exists.

The problem is separate: after setting the gap to unavailable/zero, Frankie still let the **Friday directional residue** become Monday's default P50.  Both Mondays then had positive session moves, and the realized reopen gaps were also positive.  The lesson candidate is not "predict positive gaps"; that would be hindsight.  The candidate is:

**When weekend evidence is unavailable, Monday should be allowed to reset directional ownership rather than automatically inheriting a weak Friday chain.**

### 5. Covering worked as a transition signal, not as a durable trend signal

COT covering plus cleared roll windows correctly flipped S129 UP on Sep. 16.  That was a meaningful success.  The failure was extending the same covering drift to Sep. 17 after the market had already delivered a very large upside session.

Candidate test for a future pristine group: **after an outsized delivery in the direction of a slow positioning signal, that signal's directional authority should decay unless a fresh causal phase confirms continuation.**

This is consistent with the broader G24 authority doctrine: context can propose a move; delivered price/flow must decide whether the story remains alive.

### 6. Storage Thursday behavior was structurally sensible

D abstained on both storage Thursdays because same-print consensus and causal post-print tape were unavailable.  That was correct behavior under the blind wall.  The downside P50 happened to match the realized sign both times, but those two outcomes do not justify teaching a bearish storage rule.

What *is* supported operationally is that the storage calendar correctly marked both sessions as capable of very large path expansion.  Any future lesson must preserve the distinction:

- event calendar can own **range/timing**;
- event calendar alone cannot own **sign**.

## What should NOT be learned from S129

Because S129 is not a pristine holdout blind, none of the following should be written directly into the brain from this document:

- "September Mondays gap up."
- "Storage Thursdays are bearish."
- "Roll windows are bearish."
- "COT covering means buy for two days."
- any fitted endpoint magnitude derived from the revealed Sep. 8–19 moves.

S129 should be used as a **diagnostic account and source of candidate hypotheses** only.  Those hypotheses must earn authority on a future clean chronological group.

## Candidate hypotheses to test on the next pristine groups

These are test proposals, not frozen lessons:

1. **Unavailable weekend evidence should neutralize weak Friday directional inheritance rather than merely setting the gap to zero.**
2. **Roll schedules are clocks/intensity context, not directional confirmation.**
3. **Slow positioning signals such as COT covering should decay after a large delivered move unless fresh causal price/flow evidence confirms continuation.**
4. **Event calendars may widen the magnitude/range prior without assigning sign.**
5. **When Frankie has the correct directional transition but repeatedly under-sizes large moves, inspect the existing magnitude-authority path before adding any datapoints.**

## Relationship to S130 hydration

S130 was run after September actuals had already been revealed and was explicitly diagnostic/non-teachable.  Restoring additional existing historical feeds produced:

- the same endpoint MAE: $529/day;
- the same P50 direction: 5/10;
- the same CALL direction: 2/4;
- slightly better day-local curve MAE ($332.4 vs $336.8);
- worse RMSE ($599.4 vs $578.1);
- worse maximum endpoint error ($1,025 vs $950).

Therefore **historical hydration is rejected as the default replay process**.  S129 remains the meaningful current-Frankie September run for discussion.  Future groups should use the historical state actually available through the normal current decision-state path, leave missing feeds unavailable, freeze the group, then reveal actuals once.

## Bottom line

S129's central result is:

> Frankie did not primarily fail because the historical runner exposed too few datapoints.  He got 5/10 directions and correctly identified four of the five most important directional transitions in the block, but his slow/contextual signals were allowed to persist without fresh delivery confirmation, and his magnitude output was much too compressed on the largest moves.

The next clean work should therefore focus on **authority decay/reset and magnitude expression inside the existing framework**, not on adding feeds and not on hydrating old groups after the fact.
