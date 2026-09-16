# The b_share re-point was INCOMPLETE - two sign plays were missed (S108, found by C on the G21 blind)

Recorded during the G21 blind run. **Nothing is edited.** The brain stays at s103.4 for the duration of
this blind, because C, D and E ran on it and A was running on it when this was found - re-pointing
mid-run would hand B a different rule set from the rest of the block, which is the silent turning-on the
standing order forbids. This is input to the G21 merge.

## What s103.4 did, and what it missed

s103.4 re-pointed the two plays whose ABSOLUTE 0.50 bar I found by regexing numeric bars near
`b_share`: `selector.divergence_resolution` arm (b) and `magnitude.s1void_injection_chain_bleed`.

That method was wrong in a specific way. A play can carry BOTH an empirically-fitted numeric bar AND a
separate theoretical 0.50 semantic expressed in PROSE. `structure.accumulation_arm_turn` reads:

> "recurring big-print BUY-absorption (big_print_b_share >= 0.55 on >= 2 of the last ~5 sessions,
> NON-CONSECUTIVE) **under a sub-0.50 sell tape**, against an extreme-AND-worsening COT short, is
> ACCUMULATION"

The `0.55` is a fitted big-print bar and correctly stays on the original series. The **sub-0.50 session
tape** is a theoretical balance claim and belongs on the two-sided series. I saw the 0.55 and classified
the play as fitted. C caught it.

## The audit, done properly

Swept every play for `sub-0.50` / `sell tape` / absolute-0.50 phrasing rather than numeric bars alone:

| play | semantic | re-pointed in s103.4 | verdict |
|---|---|---|---|
| `selector.divergence_resolution` | sub-0.50, >=0.50 | YES | done |
| `magnitude.s1void_injection_chain_bleed` | sub-0.50 | YES | done |
| `structure.accumulation_arm_turn` | sub-0.50 + sell tape | **NO** | **MISSED - and it is a SIGN play** |
| `selector.midblock_right_the_ship` | sell tape (by reference) | **NO** | **MISSED - inherits the arm's condition** |
| `midweek.giveback_exhaustion_reversal_recognition` | none | n/a | C over-reached; no absolute bar |

C claimed three. Two hold, one does not. `giveback_exhaustion_reversal_recognition` mentions an "extreme
sell-climax big_print_b_share at the low", which is a shape read, not a 0.50 bar.

## It is not hypothetical - it already changed a forecast in this block

`accumulation_arm_turn` requires big prints >=0.55 on **>=2 of the last ~5 sessions under a sub-0.50
session tape**. D used exactly two sessions on 20260618:

| session | big_print_b_share | session tape SERVED | session tape TWO-SIDED |
|---|---|---|---|
| 06-11 | 0.572 (clears) | 0.445 sub-0.50 YES | 0.481 sub-0.50 **YES** |
| 06-12 | 0.597 (clears) | 0.479 sub-0.50 YES | 0.52 sub-0.50 **NO** |

On the corrected basis only ONE of the two qualifies, so the >=2 bar is not met and **the arm does not
fire**. D reported 0618 as having a "second independent channel agreeing"; on the corrected series it
rests on ONE channel - the pre-print generator. D's NUMBER may still be right, and the generator fired on
its own stated preconditions (MM net -122,617, 2.83 pctile, WoW -7,763 still ADDING). What changes is the
confidence basis, and the merge must not bank the arm as forward evidence on this day.

## Block-wide scale

The sub-0.50 semantic flips on **5 of 10 days** of G21 between bases:

```
day        prior session   served   two-sided   sub-0.50 served / two-sided
20260608   20260607         0.460     0.511       TRUE  / FALSE   <- flips
20260609   20260608         0.480     0.518       TRUE  / FALSE   <- flips
20260610   20260609         0.454     0.490       TRUE  / TRUE
20260611   20260610         0.449     0.490       TRUE  / TRUE
20260612   20260611         0.445     0.481       TRUE  / TRUE
20260615   20260614         0.325     0.449       TRUE  / TRUE
20260616   20260615         0.406     0.520       TRUE  / FALSE   <- flips
20260617   20260616         0.366     0.468       TRUE  / TRUE
20260618   20260617         0.401     0.520       TRUE  / FALSE   <- flips
20260619   20260618         0.400     0.500       TRUE  / FALSE   <- flips (exactly balanced)
```

On the served series the block is an unbroken sell tape, 10/10. On the corrected series it is genuinely
two-sided. That is the whole defect in one table.

## C handled its own exposure correctly - record this as the model

On 20260616 C found the arm's "sub-0.50 sell tape" holds on the original series (0.406) and FAILS on the
corrected one (0.520), noted that with the crowd at 0.520 and big prints at 0.841 both were buying so
there is no divergence and the accumulation mechanism is absent, kept its sign, and credited it to
`flow.price_free_absorption_proxy` **explicitly not** to the arm - so a merge cannot bank the denominator
fix as forward evidence for the arm. That is the attribution discipline working inside a blind run,
unprompted.

## Proposed for the G21 merge (NOT applied)

1. Re-point `structure.accumulation_arm_turn`'s sub-0.50 SESSION-tape condition to
   `session_b_share_two_sided`. Its `big_print_b_share >= 0.55` arm STAYS on the original series - it is
   fitted there, and the thin-tape quartile bars are calibrated on that basis.
2. Re-point `selector.midblock_right_the_ship`'s inherited "under a sell tape" the same way, or state
   explicitly that it defers to the arm's definition so there is one definition rather than two.
3. Record `midweek.giveback_exhaustion_reversal_recognition` as CHECKED AND CLEAR, so the claim is not
   re-raised next group.
4. Record the method failure itself: **a semantic can live in prose as well as in a numeric bar, and a
   regex over bars will miss it.** The sweep above is the reproducible check.
