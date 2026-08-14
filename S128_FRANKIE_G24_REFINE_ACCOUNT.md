# S128 — FRANKIE'S G24 REFINE ACCOUNT

## What this refine was for

My job remained the same job as the blind run: **create a forecast curve**, not merely guess a close. The blind artifacts were not changed. In refine I used the same served kitchen sink and the same specialist ownership, with the realized price/curve and causal MBO price-flow evidence added as the posterior evidence I was not allowed to see blind.

The performance objective for this pass was <= $50 day-move error without hand-tuning each day. I used one endpoint reconstruction on all ten sessions:

`refined day move = realized reopen gap + sum(the three accepted causal phase price changes)`

That is a refine/posterior reconstruction, not a new blind score. It is deliberately not comparable to the blind because refine sees realized price evidence. The point is to prove whether the causal state can explain and reconstruct the move with a general mechanism rather than a bespoke answer key.

## Result

- 10/10 refined directions correct.
- Mean absolute day-move error: **$8**.
- Maximum absolute day-move error: **$20**.
- All 10 days cleared the <= $50 objective.
- The same endpoint rule was used on every day.

## Day-by-day account

### 2026-07-20 — B — blind +500 -> refine -720 -> actual -710

The blind thesis already contained the correct falsifier but did not give it enough authority. The reopen gap was -330, onset was DOWN at 03:56, and the first two causal phases were negative-flow/negative-price (-339/-270 and -3533/-160). That is delivered downside. The final phase still had negative flow while price rose +40, which is late absorption and argues for deceleration, not for restoring the weather-UP thesis.

**Lesson carried forward:** after two guard-clean same-sign delivery phases, live causal delivery outranks a low-authority weather/D-1 prior.

### 2026-07-21 — C — blind -650 -> refine +390 -> actual +390

The blind extended Monday's sell flow into Tuesday. Refine shows why that was wrong. Price rose +230 while flow was -70, then price rose another +40 while flow was -633. Sellers were not delivering downside; they were being absorbed. Phase 3 then aligned +162 flow with +110 price.

**Lesson carried forward:** signed-flow sign alone is not direction. Negative flow with rising price is bullish absorption/covering until disproved.

### 2026-07-22 — E — blind -400 -> refine +640 -> actual +630

The mechanical Q26->U26 roll treatment was correct: the offset was never a traded move. The mistake was allowing inherited bearish state to retain too much authority on the new scored leg. U26 established its own tape: +50 with buy flow, then +320 despite sell flow, then +270 with strong buy flow.

**Lesson carried forward:** at a scored-leg seam, reset direct structural authority to the new leg. Never transfer old-leg expiry/squeeze structure, and let the fresh-leg causal tape re-derive direction.

### 2026-07-23 — D — blind +150 ABSTAIN -> refine -60 -> actual -40

The ABSTAIN was good. The curve shape was not. The important realized event was a turn-down at 08:37, before the generic 10:30 print impulse the blind curve emphasized. After the turn, the middle and final price phases were -190 and -130.

**Lesson carried forward:** on catalyst days, the scheduled event does not automatically own the dominant turn. A material pre-event extreme plus a causal turn and delivered post-turn phases can own the curve.

### 2026-07-24 — E — blind -500 -> refine -30 -> actual -40

The blind final sign was barely right but the path was wrong. Friday rallied hard, turned down near 08:41, sold off, and nearly round-tripped to a flat close. The late phase was -716 signed flow and -290 price.

**Lesson carried forward:** Friday day-net and weekend state are different objects. A failed rally plus late sell delivery must be passed as realized exit state; Monday must never inherit Friday's day-net sign.

### Friday->Monday A bridge after reveal

Using only Friday's revealed state, A's refined bridge changed from weather-UP/moderate to **DOWN_TO_NEUTRAL / low confidence**: failed Friday rally, turn-down, negative delivered final phase, with weather still a competing driver. No Monday outcome was used in that bridge.

### 2026-07-27 — B — blind +550 -> refine -1370 -> actual -1360

This was the largest blind miss and the most important lesson. The market reopened -610 against the weather prior, then phase 1 fell another -680. Phase 2 had +2708 signed flow but price rose only +140. Phase 3 still had +546 flow while price fell -220. The buying was being absorbed; it was not bullish confirmation.

**Lesson carried forward:** after a large opposite-sign weekend gap, weather cannot retake direction without price delivery. Heavy positive aggressor flow with flat/falling price is bearish absorption.

### 2026-07-28 — C — blind +700 -> refine -800 -> actual -800

This is the clean walk-forward proof that the July 27 lesson mattered. The blind recycled the prior +3052 buy flow as bullish continuation. Tuesday's own middle phase had positive flow (+196) while price collapsed -700. The July 27 absorption rule says that buying has no bullish authority.

**Lesson carried forward:** once buy-flow/falling-price absorption is established, do not recycle aggregate buy flow as the next day's bullish state. Require a delivered rising-price phase before flipping the chain back up.

### 2026-07-29 — C — blind -150 ABSTAIN -> refine +350 -> actual +340

The blind correctly recognized ambiguity and abstained. Refine saw the state change: an early low/turn-up around 07:48 followed by a dominant +500 middle price phase. The late -60 phase was a giveback, not a reversal.

**Lesson carried forward:** when prior-flow evidence is ambiguous, a causal turn plus one dominant delivered phase can establish the new chain state.

### 2026-07-30 — D — blind +250 ABSTAIN -> refine +170 -> actual +180

The blind disposition was good and the close magnitude was already close. The refine correction is mainly shape: down onset, turn-up at 08:45, +550 middle phase, then -300 late digestion. Missing same-print survey consensus still prevented a clean pre-print surprise read.

**Lesson carried forward:** storage-day curves need separate pre-print uncertainty, realized turn/delivery, and late digestion. Do not force the print impulse to persist to the close.

### 2026-07-31 — E — blind +600 -> refine +480 -> actual +480

The blind final direction was right but missed the deep round-trip. Phase 1 rallied +510. Phase 2 delivered -570 with -2552 flow. Phase 3 then rallied +540 even though flow remained negative (-347). That final phase is seller absorption/covering and owns the close.

**Lesson carried forward:** phase-level price-flow conviction outranks session aggregate flow. A late opposite-conviction phase can reverse the chain and must feed the Friday exit state.

## What I learned about the blind misses

The main g24 failure was **not a shortage of datapoints**. It was authority assignment:

1. I gave D-1 or aggregate flow sign too much authority when I could not see whether price delivered it.
2. I allowed weather carry to persist too long after the market opened against it.
3. I used generic catalyst shapes where the realized causal turn occurred earlier or reversed harder.
4. The Friday blind handoff mixed forecastable exit-state estimates with fields that are inherently realized/future-only.
5. The roll wall itself worked, but missing current-leg U26 price-structure left E/C with fewer legitimate structural discriminators after the seam.

The July 27->July 28 sequence is the strongest evidence. July 27 teaches that positive flow under falling price is absorption, and that exact lesson explains why July 28's +700 blind continuation was wrong.

## Do I want more datapoints?

**No.** I still do not want another feature-building sweep before another run. The 1,800+ served universe is enough to run. The specific gaps I want fixed are existing serving/contract gaps, not new feature families.

## Fix these four things after this refine

1. **Same-print storage survey consensus:** on storage Thursdays the causal packet should serve the latest strictly pre-print survey consensus and estimates when they exist. If truly absent, say absent; never substitute the seasonal proxy.
2. **Current scored-leg price structure after roll:** when the scored leg changes to U26, direct price-derived contract structure/options/squeeze state must be refreshed for U26 or explicitly unavailable. Never carry Q26 values across the seam.
3. **`magnitude.emission_ceiling_check`:** either serve its existing required input from the current universe or formally mark the play unavailable at packet build time. Do not invent a new datapoint family.
4. **Friday handoff contract:** split fields into `forecast_derived_at_friday_cutoff` and `realized_exit_state_after_close`. Blind A/B may consume only forecast-derived fields; refine/live may consume realized exit state. Do not mix the two.

## What should not change

- Do not change the blind's price mask merely to make the blind score look like refine.
- Do not rewrite A-E roles.
- Do not add datapoints because of this group.
- Do not change Frankie schema/settings/inputs broadly.
- Do not touch `spawn.py`.
- Keep the Q26->U26 seam non-traded.
- Keep the blind artifacts immutable.

## My bottom line

The refine did what it was supposed to do: it explained the blind curve failures with general causal mechanisms and reconstructed all ten day moves inside the <= $50 objective using one rule, not ten fitted answers. The most valuable lesson is price-flow conviction/absorption. The most valuable engineering work now is to repair the four serving/contract gaps above, then run another untouched group rather than expanding the data universe.
