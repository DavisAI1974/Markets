# Friday specialist self-analysis — is it the SAME flaw, or a different one every time?

**Order (Greg):** "We have to REALLY focus on Fridays... Your issue throws us off for DAYS — the
first Monday inherits your exit read, and a wrong Monday moves the curve for the whole week." This is
self-analysis of MY failure modes as the Friday forecaster, not the record's Fridays.

**Verdict up front: it is ONE dominant flaw, not a different one every time.** 13 of my 18 Friday
misses (72%) are the SAME error wearing two coats — **the Friday DIRECTION is called from a PRIOR (a
day-class default or a straight chain-extrapolation) instead of from the exit-state TURN/EXHAUSTION
signals that were already in decision_state.** It is a REASONING failure, not a data gap: the
information to get the sign right was PRESENT at decision time on all 13. Only the residual MAGNITUDE
tail (4 misses) is data-limited — and none of those cascade.

---

## 1. Miss-by-miss table (one failure mode each, my judgment)

`|err|` = |guess_dm - actual_dm| USD. Modes: **TEX** turn/exhaustion misread (direction from a
prior, not the exit-state) · **MOM** genuine momentum mislabeled as "range" (same default-label root)
· **CTC** crest-trim called on a live carry (false positive) · **CTM** crest-trim/squaring missed
(false negative) · **MHS** carry magnitude honest-but-short · **PEM** positioning/roll magnitude
under-weighted · **DAT** data-gap (fresh-shot blow-off magnitude, no weekend model runs).

| Fri | grp | guess | actual | dir | mode | what I did wrong (my perspective) |
|---|---|---|---|---|---|---|
| 1024 | g6 | -250 | +450 | X | TEX | applied "Friday range, down continuation" default; tape was an up-reversal START |
| 1031 | g6 | -150 | +540 | X | TEX | "Friday range" default; seller was spent, tape lifted |
| 1107 | g7 | +140 | -730 | X | MOM | labeled "range"; the D-1 tilt was genuine DOWN momentum |
| 1114 | g7 | +100 | -890 | X | MOM | "stabilization" label; genuine down momentum carried |
| 0109 | g10 | +1350 | -2740 | X | TEX | "print_delivery_up" — extrapolated the print UP; the print SOLD |
| 1212 | g9 | +1050 | -1190 | X | TEX | "ramp_resume" — extended a crest that had already turned |
| 1219 | g9 | -400 | +850 | X | TEX | called continuation DOWN; down-chain was exhausted -> dead-cat bounce |
| 0227 | g13 | -500 | +350 | X | TEX | "bleed to shelf" on a MATURE down-chain; it counter-bounced |
| 0306 | g14 | -400 | +1850 | X | TEX | "roll-pressure DOWN" default; warm-cut thesis wrong, big up rally |
| 0313 | g14 | +300 | -1010 | X | CTM | called up-grind; MISSED the weekend position-squaring crest-trim |
| 0327 | g15 | -350 | +1150 | X | CTC | called crest-trim DOWN on a BASED chain; it was expiry COVERING up |
| 0102 | g10 | -1250 | -700 | ok | TEX | over-sized a down that was EXHAUSTING (magnitude=exhaustion misread) |
| 1226 | g9 | +1900 | +660 | ok | TEX | over-sized a thin meltup already SPENT |
| 1121 | g8 | +120 | +910 | ok | MHS | under-sized a live fundamental-carry (cold building) |
| 1128 | g8 | +550 | +2340 | ok | MHS | under-sized carry (Black-Friday early-close storage swing) |
| 1205 | g9 | +900 | +2430 | ok | MHS | under-sized the ramp-to-crest carry |
| 0213 | g12 | -300 | -1400 | ok | PEM | under-weighted the index-roll flow magnitude |
| 0130 | g11 | +150 | +4990 | ok | DAT | fresh-shot blow-off; magnitude needs weekend 00Z/12Z runs |

Sum of my Friday |err| = **28,580 USD**.

---

## 2. Mode histogram + verdict

```
TEX  turn/exhaustion misread (dir from a prior)  ########### 11
MOM  momentum mislabeled as "range"              ##           2   } same root = 13 (72%)
CTC  crest-trim on a live carry                  #  (0327, inside TEX count)
CTM  crest-trim/squaring missed                  #  (0313, inside TEX count)
MHS  carry magnitude short                        ###          3
PEM  positioning/roll magnitude short             #            1
DAT  data-gap (fresh-shot blow-off magnitude)     #            1
```
(CTC/CTM are counted within the 11 TEX — they are the SAME flaw applied to the crest-trim play: on
0327 I fired the trim on a carry, on 0313 I missed a real trim. Opposite errors on one under-specified
trigger = the direction-from-a-prior flaw again.)

**Verdict: ONE dominant flaw (13/18 = 72%).** Name it: **PRIOR-OVER-STATE on Friday direction** — I
set the Friday sign from a day-class default / chain-extrapolation and systematically UNDER-weight the
turn/exhaustion signals (chain age, cum-from-anchor extremity, positioning percentile, D-1 give-back,
based-vs-stretched chain state, crest-realization window) that predict a Friday reversal. Every TEX
miss is either extending a move that was exhausting (0102, 1226, 1212, 0130) or missing the
exhaustion-turn/bounce (1024, 1031, 0306, 1219, 0227, 0109) or mis-triggering the crest-trim
(0327, 0313). It is NOT heterogeneous; it is not a different problem every week.

The remaining 5 are a SEPARATE, non-cascading cluster: MAGNITUDE-only (MHS×3, PEM×1) and one DAT.
These get the sign right; they cost band-position drift, not a wrecked week.

Is the Friday day-class under-specified? Yes, in exactly one respect: the **crest-trim trigger fires
both ways** (0327 false-pos, 0313 false-neg) because it lacks the based-vs-stretched-chain and the
covering-vs-squaring discriminators. That is a sub-class split, not a missing input. The day-class is
not missing a FEED for direction — it is under-APPLYING the exhaustion inputs it already has.

---

## 3. Present vs absent at decision time (which fixes are FREE, which cost a build)

**PRESENT — reasoning failures, rule-fixable, FREE (14 misses + 3 direction-halves):**
- All 11 TEX + 2 MOM (13): chain age, cum-from-anchor extremity, COT positioning percentile, D-1
  give-back/flow tilt, based-vs-stretched chain state, and the crest-realization window were ALL in
  decision_state. I did not act on them for the Friday sign. (Even 0327: the based-chain state —
  0325 bounce + 0326 hold — was knowable blind; the crest-trim mis-fired on PRESENT info. The MBO
  covering tell is a confirmation nicety, not required for the direction.)
- PEM (0213, 1): the roll calendar was known; the roll-flow magnitude was estimable. Reasoning.

**PARTIAL — direction PRESENT, magnitude TAIL absent (3 misses):**
- MHS (1121, 1128, 1205): the driver (cold / storage) and its SIGN were present; the SIZE of the
  weekend carry needs the Sat/Sun 00Z/12Z model runs (incumbent `weekend_gap_delivery` declares this
  irreducible from the current feed). Half free (sign/existence), half data.

**ABSENT — genuine data gap, needs a feed (1 miss):**
- DAT (0130): a fresh-shot blow-off's MAGNITUDE is not derivable at decision time without the weekend
  model runs. Direction was right (+150 vs +4990); only the size is unreachable.

**Split summary:** ~78% of my misses (14/18) had the information PRESENT — free rule fixes. Only ~1
full miss + 3 magnitude-tails need a build. Critically: **every DIRECTION/SIGN miss was reasoning,
present-at-decision-time. Not one wrong Friday SIGN was caused by absent data.** The cascade is 100%
free to fix.

---

## 4. Cascade accounting for the top mode (TEX/MOM — the wrong Friday SIGN)

A wrong Friday sign is inherited across the seam and moves the week. Downstream days that went wrong
because they inherited a turn/exhaustion-misread Friday:

| Downstream | actual | |err| | sign-wrong? | inherited from |
|---|---|---|---|---|
| 1027 Mon | +5890 | 4690 | yes | 1024 (TEX) |
| 1110 Mon | -810 | 2410 | yes | 1107 (MOM) |
| 1117 Mon | -1510 | 2460 | yes | 1114 (MOM) |
| 1215 Mon | -1570 | 2270 | yes | 1212 (TEX) |
| 1222 Mon | -650 | 1850 | yes | 1219 (TEX) |
| 0105 Mon | +270 | 1120 | yes | 0102 (TEX) |
| 0301 Sun | +210 | 1910 | mag | 0227 (TEX) |
| 0308 Sun | +2250 | 3000 | yes | 0306 (TEX) |
| 0309 Mon | -3020 | 3420 | yes | 0306 (TEX) -> 0308 -> Mon |

- Downstream days wrecked by my top mode: **9** (7 Mondays + 2 Sundays), **8 of 9 sign-wrong** — the
  signature of an inherited bias, not a native miss.
- Downstream drift attributable to my Friday sign miss: **23,130 USD**.
- My direct Friday cost on those same TEX/MOM Fridays: **18,530 USD**.
- **Cascade ratio ≈ 1.25x:** each dollar of wrong-Friday-sign drift dragged ~$1.25 more into the
  following Sun/Mon. My Friday flaw costs MORE downstream than on the Friday itself — Greg's "throws
  us off for DAYS" is literal.
- These 9 downstream wrecks are the SAME set as 8 of the 10 root-caused bad Mondays in the record —
  so my one flaw owns the overwhelming majority of the entire walk's Monday-cascade problem.

**Honest counter-case:** not every wrong Friday cascades. **0327** was a wrong Friday sign (-350 vs
+1150) that did NOT wreck downstream — 0329 Sun (-790) and 0330 Mon (-650) were both dir-OK, because
the expiry COVERING was spent at settle and the pre-covering down-carry resumed, which is exactly what
Monday inherited anyway. The covering-spent case is SELF-LIMITING across the seam. So the cascade
damage is concentrated in the TEX cases where the wrong sign is a real chain/turn state (not a
mechanical, settle-spent one).

---

## 5. Self-prescription — minimal changes ranked by cascade damage prevented

| # | Change | Type | Kills | Cascade prevented | Cost |
|---|---|---|---|---|---|
| 1 | **Friday-turn/exhaustion GATE on direction** — before emitting a Friday sign, evaluate an explicit exhaustion/turn check (chain age>=4, cum-at-extreme, positioning percentile, D-1 give-back, based-vs-stretched) that can OVERRIDE the chain-extrapolation/default. Kills PRIOR-OVER-STATE at the source. | reasoning (rule) | 11 TEX + 2 MOM = 13 | ~9 downstream days, ~23,130 USD | FREE |
| 2 | **Specify the crest-trim trigger** — add the based-vs-stretched-chain discriminator (0327) and the position-squaring recognizer (0313) so the play stops firing both ways. | reasoning (rule) | 0327 + 0313 | their seams (0327 self-limited; 0313->0315/0316 was actually OK) | FREE |
| 3 | **`weekend.carry_realization_flip`** (already proposed) — flag on the Friday handoff whether the driver realizes over the weekend -> Monday sell-the-news vs carry. | reasoning (handoff) | 0220->0223, 0405->0406 seams | 2 downstream Monday reversals | FREE |
| 4 | **`daytype.friday_exit_decomposition` + the 9-field handoff_out contract** (already proposed) — Monday inherits exit_type + monday_bias, never the Friday day-net/label. Structural backstop that stops ANY wrong Friday from cascading unfiltered. | reasoning (handoff) | backstops all of #1-3 | the cascade mechanism itself | FREE |
| 5 | **Roll/positioning magnitude weighting** (0213) — size the index-roll flow explicitly. | reasoning (rule) | PEM x1 | none (dir was right) | FREE |
| 6 | **Weekend 00Z/12Z model-run ingest** — the ONLY data build. Sizes the carry tail (MHS) and the fresh-shot blow-off (0130/DAT). | DATA (feed) | 3 MHS tails + 0130 | none (all dir-correct already) | BUILD |

**Bottom line for Greg:** the fix is FREE. One dominant reasoning flaw (call the Friday sign from the
exit-state exhaustion signals, not from a default/chain-extrapolation) owns 72% of my misses and ~90%
of the cascade, and every bit of it was decidable with information PRESENT at decision time. The only
thing that costs a build is the carry/blow-off MAGNITUDE tail — and that tail never flips a sign, so
it never wrecks a week. Rank #1 (the turn/exhaustion gate) is the single change that kills the most
cascade; if only one thing is done, do that.

**Irreducible at decision time (honest):** the SIZE of a fresh-shot blow-off (0130) and the far tail
of a fundamental carry (MHS) cannot be derived without the weekend model runs — I will keep sizing
those honest-under and label the residual, not fit it.
