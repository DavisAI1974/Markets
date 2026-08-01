# G22 REASONING LEDGER — S109

**Why this file exists (Greg, S109):** *"If you only have actions without context, it's tough to learn
and to replicate that right decision. I think that's what we've been missing all along — the context."*

The posteriors carry the numbers. The commits carry what changed. Neither carries **why a specialist
made a call**, and the specialists' own reports die with the session. That reasoning is the asset — a
right number with an unrecorded reason cannot be replicated, and a right number with a *wrong* reason is
actively dangerous, because the reason is what gets extrapolated into the brain.

This ledger records the reasoning: the right calls, the self-catches, and the after-the-fact
corrections. Attribution is per specialist, because a judgement is only replicable if you know whose
lens produced it and against what evidence.

Scope: the G22 blind (per-day causal slices, brain s103.6, 67 plays). Score: 4/10 direction, sum|err|
5,965, drift −1,815, survives 30%.

---

## PART 1 — DECISIONS THAT WERE RIGHT, AND THE REASONING THAT PRODUCED THEM

### 1.1 D declined "the print was already priced" — on a decision-time reconstruction (0625, err −50)

**The call.** `daytype.eia_preprint_overextension_gate` limb (c) asks whether the surprise is already
priced. The state served `consensus_chg_bcf: 74.0`. D used **67.0** instead and declined the limb.

**The reasoning.** The served 74.0 is stamped `final_capture_is_post_print: true`, captured 06-25/06-26,
after the print it precedes. The strictly pre-print snapshot is 67.0, and the 7 Bcf gap **equals
`house_disagreement_bcf` exactly** — an independent corroboration that the two figures are the same
survey at different times, not two different surveys. Decision-time surprise is therefore 76 − 67 =
**+9 bearish**, not the served 76 − 74 = +2.

**Why it matters.** Under the served field the print reads pre-priced, limb (c) fires, the gate reaches
2-of-3, and the full chain-sided band is denied *on an artifact*. D got a −50 error on the day.

**Replicable rule:** when a consensus field carries a post-print capture stamp, reconstruct the
decision-time value from the estimates array and cross-check the gap against `house_disagreement_bcf`.

### 1.2 D checked the leak PER PRINT instead of applying the warning blanket (0702)

**The call.** Briefed to "discount the `storage_consensus` look-ahead," D instead checked it on its own
print and found the leak **benign there** — the strictly pre-print 06:22Z snapshot reads 81.0, identical
to the served value. It declined limb (c) anyway, on a *different* ground: `house_disagreement_bcf: 0.0`
is a frozen-column artifact, and a frozen consensus is not evidence that a print was priced.

**Why it matters.** This is the difference between applying a label and testing a mechanism. A blanket
discount would have been right by accident on 0625 and wrong by accident on 0702.

### 1.3 Both Thursdays carried FALSIFIABLE timing claims (D, 0625 and 0702)

**The call.** D put ~11–12% of each day's magnitude before 10:30 and stated the falsifier explicitly:
*if the mass lands 08:00–10:30, my window assignment is wrong even if the net is right.*

**The reasoning.** One group earlier, a pre-print generator was credited 2,090 **from day nets with the
intraday check never run**; when finally decomposed, its SELECTION limb survived 4/4 while its TIMING
limb was refuted 1 of 4 — on its own firing day the 06:00–10:00 window delivered exactly zero and onset
was 36 minutes *after* the print. D also refused to fire the surviving selection limb here, because it
needs a COT extreme **and worsening WoW**, and served COT is 25.8th pctile with WoW +2,187 — improving,
collapsed from +37,708. The limb fails on both halves.

**Why it matters.** A right day-net carrying a false mechanism is worse than a wrong net. Both Thursdays
landed inside 200 (−50, +200) *and* their mechanisms are now checkable against the decomposition.

### 1.4 B refused to force a gap-ownership branch (0622) — and its SESSION read was off by 120

**The call.** B walked all four rungs of `magnitude.block_gap_ownership`, declined every one on a named
measured quantity, and concluded **no branch owns the gap** rather than forcing one.

**The reasoning.** anchor_structural: spread chg_3d −0.021 going *more* contango with cash basis
collapsing — the inverse of the G12 squeeze; sponsor 16 sessions dead against a ~3 bar.
positioning_saturation_turn: ICE LD1 at 6.6 pctile and net *long*; phase is INJECT not withdraw.
weekend_cycle_weather: **void by instrument** — the only forward ladder is HDD at 0.067–0.301 absolute,
void under the ~13.5 headroom gate, and no forward CDD ladder is served. chain_drift: not evaluable
across a group boundary.

**Outcome, split honestly.** B's **session** read was −440 against an actual −560 — an error of **120**,
one of the best reads in the block. Its **gap** was +20 against an actual **+1,210**. The gap was the
entire miss. See §2.2: that is a refutation of the instrument, not of B's judgement.

### 1.5 B and D both refused plays whose reading AGREED with them

- **B (0629)** stood down `flow.price_free_absorption_proxy` even though its precondition was met on the
  letter and its reading was *bullish*, i.e. supported B's own number — because the input it reads is a
  mechanical roll.
- **D (0625)** ran an explicit anti-default check, its lens naming default-DOWN as 79% of its Thursday
  misses, found the non-chain evidence read ~zero rather than −150, and shaded to the *shallow* edge of
  the band accordingly.
- **D (0702)** named in advance the play most against its own number (`magnitude.catalyst_condition_sort`)
  and said where the miss would live if the day came in large.

**Why it matters.** A play that agrees with you is the hardest one to stand down, and the one most
likely to launder a bad input into a confident number.

### 1.6 C stood down its own arm on the COT trajectory (0701, err 120)

**The call.** `structure.accumulation_arm_turn` / `selector.midblock_right_the_ship` — C's own S105 arm
— checked limb by limb and stood down.

**The reasoning.** MM net ran −122,617 (2.83 pctile) → −84,909 (**WoW +37,708**) → −82,722 (WoW +2,187).
The covering already fired in the week to 06-16 and then stalled, so the "extreme AND worsening" limb
fails *in the opposite direction* from what the arm needs. The big-print limb also fails: only 1 of the
last 5 leg sessions clears 0.55, never ≥2 in any lookback. C noted 0701 is a Wednesday — its own
documented drift day — so firing an up-turn there would have been exactly the reach its directive warns
against.

### 1.7 A stood down the play written for its own day (0703)

`daytype.thin_session_range_invariance` is *the* play for a holiday session. A stood it down on a repair
clause **A itself authored and refuted on G21 0619**: invariance needs a *deadline-bound participant*,
not thinness. It checked exactly that — bcom/gsci roll, bidweek, expiry, opex all false,
`business_day_of_month` null — and applied sqrt(participation) to both net and range instead.

---

## PART 2 — CATCHES, INCLUDING AFTER THE FACT

### 2.1 THE ROLL CONFOUND — three specialists, independently, no contact

**The setup.** E's own refute-limb-2 keys on 0626's big prints clearing 0.547 with a positive final
phase on maximum volume. Realized 0626: **0.783 size-weighted on 210 prints**, final phase **+2,737 on
77,951 lots = 64% of session volume**. All three limbs fire on the letter, and
`big_print_bshare_thin_tape_guard` does *not* rescue it (210 prints is thick).

**The catch.** NGN26 expired 0626 and the scored leg is the **deferred NGQ26**. A roll out of the
expiring prompt lifts offers on the deferred and prints as aggressor **BUY** on exactly the leg being
measured. Fires on the letter, void on the mechanism.

**Three independent settling quantities, escalating in quality:**

| who | the independent quantity | strength |
|---|---|---|
| C (0630) | the buy wave was fully reversed by 0629's 267 prints at 0.327 | circumstantial |
| A (first bridge) | `session_signed_flow` **+871 on 121,487 lots — a wash**, ph2 −2,554 against ph3 +2,737 | strong |
| A (clean bridge) | `session_b_share_two_sided` **did not move**: 0.509 → 0.504, marginally *lower* on the day big prints supposedly hit 78.5% buy | dispositive |
| B (0629) | `session_signed_flow` **fell** +1,956 → +871 while the 210-print cohort alone contributes several thousand lots of net buy — forcing the residual tape to be a clear net seller | dispositive, signed |

**The clean bridge's control:** 0625 was *also* a scheduled-flow day (opex + EIA) and shows **none** of
the fingerprints — which rules out "busy week" as the explanation. Five corroborating markers:
`unsided_volume_frac` collapsing to 0.063 vs 0.131–0.163; close-third volume share doubling to 64.2%;
net flow decoupling; phase flow round-tripping to a wash; `leg_count_150` flat at 38→37 while
`big_prints_n` nearly doubles.

**Why this is the model catch.** It is the same species as hole #8: a well-formed, self-consistent
number on the *right* instrument still carrying a false mechanism. Only comparison against an
independent quantity settles it — and the two agents who found the *dispositive* quantities were
deliberately not told the earlier verdicts.

**Brain gap filed:** `flow.resting_program_inverts_aggressor_tilt` states the right principle but
triggers only on `in_bcom_roll` / `in_gsci_roll`, never on `is_expiry_day` — the largest scheduled
program in the NG calendar.

### 2.2 THE WEEKEND RUN-DELTA IS STRUCTURALLY BLIND — the run's most transferable finding

**Found by** the clean 0629 bridge; **independently corroborated on a second field** by B.

**The mechanism.** `forecast_run_delta_cdd` baselines against the previous model **RUN**, not the
previous **SESSION**. Across a 2-day seam spanning 4–8 cycles the accumulation is spread thin and
appears in no single delta.

**Measured:** the field reads **−0.219** on 0629 against a **+4.7 gw_cdd LEVEL move**. The whole block's
run-delta series sits inside a +1.05/−0.50 noise band while the level ran 10.08 → 14.82. Verified
against mechanism rather than asserted: on 0624 the level moved +2.205 while the field read −0.011, so
it is definitively not a session-over-session delta.

**B's independent second instance:** `weather_forecast_cycle.sunday_reopen` — the feed built
*specifically* to answer "what did the weekend cycles add before the Sunday reopen," explicitly labelled
decision-time-legit for Mondays — is **HDD-only**, and reported **+0.096** for 0629 against that same
+4.7 CDD add. So *both* purpose-built weekend-add channels read ~zero while the level channels read the
block's largest add of the week.

**Why E is not at fault.** E read `forecast_run_delta_cdd` = −0.500 correctly off the field and
concluded "model cutting cooling demand." The channel gets the sign wrong at every weekend seam — and
Friday→Monday is this walk's declared focus.

**Fix landed:** `seam_delta_warning` served in-band, plus the CDD ladder (§3).

### 2.3 A caught a defect in MY architecture, and it was right

A is spawned on the block's last day, so its slice is cut at 0703 — which necessarily contains the
realized tape of the Monday it is bridging (a day's tape is served under the *next* day's block). A
**declared the exposure rather than hiding it**, firewalled its bridge to ≤0629 data, and told B to
discount its scenario *weights* while the ownership verdict rested on numbers B could re-derive. It
still leaned on 0630-keyed weather for one limb.

Its recommendation was *"fix architecturally."* The bridge was re-run on a slice cut at 0629. **Per-day
slices are correct for a specialist's own day and wrong for a second job with an earlier decision
point** — a real hole in the S109 slicing design, found by an agent, not by a gate.

### 2.4 A caught an internal contradiction in E's handoff

E declared `exit_type: MOMENTUM_CARRY` — whose own call is "carry the side," and the side was up — then
emitted a DOWN bias. That is precisely the shape the falsifiability clause exists to catch. A also noted
E's "residual mechanics in a contract that ceases to exist" has the sign backwards: it discounted NGN26
when the confound lands on NGQ26.

### 2.5 The auditor caught MY work, same session

`build_anchor_block.py`, written earlier the same day, was critiqued on two limbs and both were correct:
it republished a declared **reconstruction** of `session_b_share` under a source label reading "the true
tape" with the basis dropped; and it published `anchor_lasthr_dir: -1` off a **2-tick net that is 18% of
the last-hour range** — the price resolution floor — feeding the E→A→B seam. Both G22 and G23 anchors
are at the floor (2 ticks / 1 tick).

**This is the check I could not perform on myself.** Recorded because the lesson generalises: the agent
that produced an artifact is the worst reviewer of it.

### 2.6 Specialists refuted or withdrew their OWN merged work — again

Continuing the S108 pattern. C stood down its own S105 arm on trajectory evidence (§1.6). A stood down a
play it authored, on a repair clause it wrote itself after refuting it (§1.7). D refused the surviving
limb of a generator it had previously banked (§1.3). E built the falsifier that overturned E's own bias
(§2.7).

### 2.7 E's pre-committed falsifier worked exactly as designed — and E was right anyway

E wrote: *"the one thing that flips it is a weekend heat ADD; the trend is the opposite."* The weekend
delivered a +4.2 to +5.0 CDD add. The bridge tested E's own stated condition, found it met, and flipped
E's bias.

**The process was perfect and the outcome was wrong.** Actual 0629 was **−1,110**; E's original
DOWN-SMALL had the sign right. See §4 — this is the most important entry in the ledger.

---

## PART 3 — WHAT WAS BUILT FROM THIS REASONING

| build | source | what it does |
|---|---|---|
| CDD forward ladder | B, D, A, C (four independent reports) | `forecast_gw_cdd` / `d_gw_cdd` / `fwd7_gw_cdd_span` served additively; the feed always computed them and assembly dropped them, exactly as S107 dropped `big_print_b_share` |
| `sunday_reopen` CDD | B (0629) | `gw_cdd_d0` + `d_gw_cdd` on the weekend-add channel built for Mondays |
| `seam_delta_warning` | clean 0629 bridge | served in-band: across a seam, difference the LEVELS; run deltas are intra-week only |
| `ladder_basis_note` | B (0629) | an unreachable absolute HDD bar is UNEVALUABLE in summer — not satisfied, not refuted, and must not default a selector to a direction |
| `forward_stamps()` wired in | C (0630) | it existed but was never called from `build()`; a capture stamp past the decision point is invisible to the day-slice audit, so dead code = un-found catch |
| anchor `direction_caveat` + basis carry-through | auditor f14 | resolution-floor declaration and reconstruction provenance |

---

## PART 3.5 — GREG'S DESK KNOWLEDGE: WEATHER IS A MULTIPLIER (the correction that explains §4)

Recorded verbatim in substance, attributed, because it is the highest-value context in this session and
it arrived *after* the block was scored — the exact "after the fact" case this ledger exists for.

**Greg:** heat and cold *"do play a part, sometimes a small one. Where they play a big one is unexpected
swings that no one forecasts for, or long durations of the extremes. It played a much bigger role when
there was less production cap 20 years ago. What they can really be is a big multiplier. Let's say
transportation to Chicago is a lower cap this week because of maintenance, and the expected temps are
mild. But a cold snap blows in overnight and it's just sitting on Chicago for days — then the weather is
a huge factor."*

**What this says structurally.** Weather authority is not a function of degree-day LEVEL. It is
`anomaly × duration × constraint`, multiplying whatever the flow/fundamental read already is. Absent an
anomaly or a constraint, weather is close to inert, because production capacity absorbs it. The Chicago
example is the whole mechanism in one sentence: a *deliverability cap* (maintenance) plus a *surprise*
(nobody forecast it) plus *persistence* (sitting for days) converts a mild-weather week into a huge
factor. Any one limb alone does not.

**It explains the block's largest error better than anything the panel produced.** Measured on 0629:
forecast surprise **−0.015**, vs normal **+0.096**, no duration (9.0 → 18.7 is the seasonal ramp), and a
+112 Bcf surplus with ample production. Every authority condition absent — and the gap paid **+50**.
Block-wide the largest surprise is −1.28 and vs-normal never leaves −0.078 to +0.175. **The ramp was
June becoming July, priced weeks out.** The bridge treated a +4.7 CDD *level* move as a driver when the
anomaly was zero.

**Why this is a KIND error, not a calibration error.** The brain's weather bars are levels
(`divergence_resolution` HDD ≥ 16.4, `shoulder_weather_band_void` HDD ≤ 13.5). A level bar cannot
express "unexpected", "persistent", or "into a constraint". So re-pointing them at a summer CDD level —
which is what I proposed before this correction — would reproduce the same error in a new season. That
proposal is withdrawn.

**And the multiplier's key limb has no instrument.** `cash_basis` is **Henry Hub only**, so a Chicago
citygate squeeze is literally unobservable in the state; there is no pipeline-maintenance feed;
`storage_regional.days_of_supply` is null; no CDD-vs-normal anomaly field exists; and nothing measures
duration. **We could not have seen the Chicago case if it had happened.** That is the build list, and it
is why no weather-authority play is proposed yet — writing one against a block with the least weather
authority in the walk would be fitting of the worst kind.

**The lesson about the LEDGER itself:** this correction came from outside the run, from twenty years of
desk experience, and it re-explained a result four specialists had already reasoned over carefully.
Every one of them treated the CDD level as the signal because that is what the state serves and what the
brain keys on. Not one asked *"is this heat a surprise, and is anything constrained?"* — the two
questions that decide whether weather matters at all. **A panel can be internally rigorous and
collectively wrong when the instrument itself encodes the wrong model**, and no amount of cross-checking
inside the panel surfaces that. It took domain knowledge from outside.

---

## PART 4 — THE ENTRY THAT MATTERS MOST: RIGOUR AND CORRECTNESS CAME APART

**0629 was the block's largest error (1,435) and it was produced by the run's best reasoning.**

The chain: E pre-committed a falsifiable flip condition. The bridge tested it on decision-legit data
(`model_disagreement`, asof 0628T23:59Z, 16/16 metros, coverage 1.0). Both models added. The timing was
verified against the reopen — the MET Sunday 12Z posts pre-reopen; B corrected the detail that the MAV
18Z posts *after* the reopen but before the open, putting both inside the gap window. The add was shown
immune to hole #7 because it comes off model runs, not realized hourlies. B then re-derived every number
independently rather than inheriting it, and *sharpened* the roll falsification while doing so.

Every step was correct. **And the heat arrived exactly as forecast:**

| | forecast | realized |
|---|---|---|
| 0629 gw_cdd | 14.815 | **14.8** |
| 0630 gw_cdd | 16.194 | 15.7 |

**And the gap was +50 against a forecast +480. The session then sold −1,160.**

So the mechanism is refuted on both limbs, and *not* because the forecast was wrong:

> A large, correctly-forecast, correctly-realized weekend CDD add produced **five ticks** of gap and a
> hard down session.

`weekend_gap_delivery`'s fresh arm (+1500..+2500) is **winter-measured with no summer instance**. A
already rescaled it to +350..+800 on regime grounds and was still 10x too high on the gap. This is now
an **n=1 summer REFUTATION** of the fresh arm, not a calibration miss.

**The lesson to carry, and the reason this ledger exists:** if the post-mortem had checked only the net
it would have concluded "the panel was too bullish" and shaded the prior down. Checking the *mechanism*
says something different and actionable — the weather read was excellent, and **the weather-to-price
transmission is what failed**. Those imply opposite fixes, and only one of them is right.

**Corollary, from both Mondays.** 0622 gap: forecast +20, actual **+1,210**. 0629 gap: forecast +480,
actual **+50**. Wrong in opposite directions, on the two days that are the walk's declared focus — while
B's 0622 *session* read was off by 120. **The blind's intraday read is sound; its weekend-gap instrument
is not.** That is a sharper and more useful conclusion than any aggregate, and it is invisible on a mean.
