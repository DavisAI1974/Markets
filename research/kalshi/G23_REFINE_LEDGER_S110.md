# G23 REFINE REASONING LEDGER — S110

**Why this file exists (Greg, S110):** the specialists' run summaries die with the session; this is
the durable capture — **the reasoning beside the action**, plus, per **D24**, the **past instances**
each specialist found when it searched the corpus. D24's qualification is honored throughout: past
evidence is used WHEN AVAILABLE and a finding is never disregarded for lacking it, so each entry
records which of the three states applies — **instances FOUND**, **corpus SEARCHED, none found**, or
**NOT SEARCHED**.

Scope: the G23 refine, brain **s104.0**, per-day causal isolation, ladder-repaired state.
Blind: 5/10 · sum|err| 5,920 · drift **+4,900** · survives **83%** — the most one-directional block of
the walk, and the first to lean UP. Actual cum −3,290 vs blind +1,610.

---

## THE BLOCK-LEVEL FINDING, AND ITS CORRECTION WITHIN THE SAME RUN

**First reading (C-0707, C-0708, independently):** the GSCI/BCOM roll window owns the decline — the
window sums **−3,650**, the five non-roll days **+360**, together −3,290, the block cum exactly, and
`flow_calendar` published that window before the block opened.

**Correction (C-0714), on the same data:** the window is a **CONTAINER, NOT A CAUSE.** A tighter
partition exists — **0708 + 0709 + 0710 = −3,230 = 98% of the block in three consecutive sessions**,
while the other seven net **−60 total**. Strip the flush and the window's own residual is ~−$60. The
mechanism test: if five days of roll supply had been holding price down, its removal on the last
window day would restore the impact coefficient toward the week-1 median (0.380) — worth ~+$1,400 on
that day's flow. Realized **0.053**. **Nothing was released because nothing was held.** Settle-phase
flow even swung **+2,290 to net BUY** on that final roll day while price barely moved.

**Refinement (D-0716):** BCOM runs one day past GSCI, so the correct partition is **six
roll-overlapped sessions at −3,710 against four roll-free at +420**. D's own blind had read the roll
*ending* as support for its up-chain; the roll ending was the reason the tape stopped moving.

**Status:** held at **n=1 block, container-not-cause**, deliberately. C-0714's data request stands:
only NGQ26 is staged, and a roll is a calendar spread — roll questions can only be answered
negatively without the NGU26 leg.

---

## THE LIVE STRUCTURAL CLAIM: THE IMPACT-COEFFICIENT COLLAPSE (C-0714)

`k3` = |prior-session phase-3 price change| / |phase-3 signed flow| — the tape's marginal price
impact per unit of aggressor imbalance. After the 0709 liquidity void it collapses:

| session | k3 | what the flow bought |
|---|---|---|
| 0709 | — | price moved on **no flow** (zero depth) |
| 0710 | 0.302 | |
| 0713 | 0.026 | |
| 0714 | 0.018 | |

**Week two, in both directions:** flows of **+3,747 / +6,326 / +1,089 / +1,333** produced only
**+200 / −60 / −20 / +180**. A void is **price discovering where liquidity actually sits; once
found, flow stops moving price** — which predicts quiet in *both* directions, not just down. C's own
day was derived from this rule: carry k3 forward from 0713 (0.026) against served flow +3,747, one
declared judgement term worth $73 → **+170 against +200 actual**.

**CORPUS EVIDENCE — INSTANCES FOUND (D24 state a).** `magnitude.terminal_impact_coefficient_carry`:
the numb class (k3 ≤ 0.05 on ≥500 lots) → small next day, **n=6 spanning g20+g23, 5/6 at ≤$200
(median 115)** against a base rate of 12/40 days (30%) and a block median |net| of $535. Sign-free by
construction. **One live counterexample named and not explained away: g20 0605, −1,350.**
Companion, `structure.void_precedes_impact_collapse`: the void signature scan across four groups
returns **exactly two instances** (g23 0709, g20 0529), both followed within one session by a k3
collapse — sequence claimed, **duration explicitly not** (g20 lasted one session, g23 four).

**WHY THIS ONE MATTERS MOST: `k3_prev` is PRE-CUTOFF information — it belongs in the blind's hands.**
C's cross-cutting verdict: *"G23's second week is a magnitude problem misdiagnosed as a direction
problem. A better direction rule doesn't fix that; putting k3_prev in front of the blind does."*

---

## THE BURN-CONVERSION GATE: REFUTED BY FOUR SPECIALISTS ON ITS FIRST FORWARD TEST

Merged S110 as the centerpiece of the G22 proposal; G23 was its **named** forward test. Its own
falsifier: *"a burn-confirmed CDD add that fails to deliver, in G23+."*

| specialist | verdict | the evidence it brought |
|---|---|---|
| **C-0707** | MIS-SCOPED, not refuted | The blind confirmed the gate off a **holiday-Sunday** grid row that the gate's own weekday-normalization rule disqualifies. Read correctly it pointed UP and its day rose (+160). Falsifier **not discharged** on this day; the nearest clean candidate (0708) is roll-confounded, so C **declined to bank a refutation on it**. |
| **C-0708** | Full-band up-call limb REFUTED | Three clean up-fires in G23 — 0708 (−520), 0715 (−60), 0716 (−20) — **0 of 3 delivered**, sum −600 against a block of −3,290. 0706 excluded honestly as unevaluable (no in-block prior grid period). The **damper limb survives** (0709/0710 both wind-ramping, both fell). Structural reason: the gate converts a **D+2-stale realized** grid burn into a **forward** lean, and on 0708 a second burn instrument knowable the same morning said the opposite (July STEO: power burn −0.926, consumption −1.196, production **+0.237**). |
| **D-0709** | REFUTED AS WRITTEN — with the mechanism | **The CDD-add limb is a constant: `d_gw_cdd` at horizon 1 is positive 20/20 days across G22+G23** (min +0.129, max +2.256; h0+h1 positive 19/20). **A limb that never changes sign cannot gate** — whatever discriminating work the gate did in G22 was done by wind/burn. D then **tested and rejected the obvious repair**: the forward integral does not sort direction (~10/19; the most positive forward limb of the twenty days delivered −60). |
| **E-0710** | REFUTED on BOTH polarities — *its own play* | Up arm re-run against the realized weekend: **both limbs pass** (CDD add +1.840/+1.969/+3.245 clearing the bar; Sat-over-Sat burn 43.5 vs 42.9, wind −11.3%) → verdict "flip UP +300..+800" into a **−620** Monday. Down arm: the both-ways clause **capped a correct DOWN read** to a −150..−200 floor against a **−660** actual. E's words: *"Not softened — it is my play, and the G22 support (6 instances, one block, never spanning) should be read as having been insufficient."* |

**THE MECHANISM (E-0710), the session's best single sentence:** *the gate reads burn as a numerator
with no balance-clearing denominator; when the balance loosens at the demand peak, burn confirmation
is **bearish** information.* Burn hit 45.4 Bcf/d at the CDD ladder peak while the print came in +61
against a 5-year pace of 56 and STEO revised production **up**. Peak demand was not clearing the
surplus.

**THE MISSING TERM, SUPPLIED (D-0716).** E's balance-term successor **would have sorted D's day**,
in the specific form `storage.vs_5yr` and its WoW delta: **112 → 151 → 156 → 162** while injections
collapsed **87 → 61 → 41**. Both terms were decision-time-visible in the same served state file and
D used neither. Honest scoring attached: as a gate **revocation** it is 2/3 (right 0709, right 0716,
wrong 0618); as a **standalone direction sorter** it is 4/7, and D explicitly does not claim it as
one. C-0714 sharpened the denominator further: **+1.0 Bcf/d is 2.3% of burn against storage of
2,983** in injection season — the numerator is always positive and always small in this season,
*which is why* the CDD limb reads 20/20 and cannot gate.

**Corpus state: INSTANCES FOUND (D24 state a)** — the refutation rests on 20 days across two groups
for the constant-limb argument, 3 clean up-fires in-block, and a 2/3 revocation record spanning
G21–G23. **Attribution fence honored by every specialist**: the CDD ladder is an S110 graft, so
C-0708 verified the grafted values against realized `weather.gw_cdd` on all ten days (within 0.3–0.8,
same sign of change every day) **before** ruling, and E-0717 flagged that half of its own 0710
refutation is itself fence-exposed because limb A differences a D0 against a frozen horizon while the
graft's identity proof covers D0 only.

---

## THE 0709 PRINT — THE BLOCK'S LARGEST MISS, DECOMPOSED

Blind −250 · actual **−2,050** · 1,800 of the block's 5,920 error.

**D-0709's decomposition.** The print's own surprise was **−100 net / −190 at the spike, reclaimed in
40 seconds = ~5%** of the day. **59% (−1,210) was already done pre-print**, where the blind's path
had +10. Absent channels account for −400 to −700. **Verdict: an attribution error, not a sizing
error** — nothing was missing from the read; the blind treated position-carry drivers as
catalyst-contingent and held them until after 10:30.

**The mechanism.** The block's only `absorb_session` day: day signed flow **+1,551 net BUY while
price fell −2,050**; phase 2 delivered **−1,860 on −11 of flow across 98,400 lots** (66% volume
expansion over the block's next-largest core phase). A length liquidation with **no short base to
arrest it** — and D found the load-bearing mirror of its own blind reasoning: reading COT's mid-book
as "no squeeze risk" is right, but a mid book also **removes the floor**.

**How much was derivable (D's honest answer).** A **−1,450-class day WAS derivable** at decision time
from a prior-group absorption band (**median 1,235, max 2,090, n=6, G17–G20** — corpus evidence,
state a) placed on four-channel agreement. **The last ~600 was not**: it ran into the **3.00 put wall
(42,295 puts; low 2.993, close 3.014)** and the dealer side is unobtainable from OI. Posterior
**−1,450**, honest error 600 vs the blind's 1,800 — *and D states plainly that this is still 6× the
doctrine target.* (The put wall is only readable because the S110 audit fixed `options_surface`'s
10×-off strikes on a block that had zero consumers.)

**The distinction that came out of it (E-0710):** **a flowless reprice is NOT absorption.** Phase 2
was −1,860 on 98,400 lots at net flow −11 — the resting **bid withdrew**; nothing was transferred, so
the level was never tested and got pressed twice more. E had called the genuinely absorbing phase
(ph3: +1,390 of buying purchasing −160, `ph_absorb` true in the file it was reading) a bullish "buy
handover" — **polarity inverted on the flagged phase, label misapplied to the unflagged one, both
errors pushing less bearish.** Blind-available discriminator offered: `l1_book.quote_bid_share`,
which printed the block minimum **0.475** on 0709 — **with an honest negative attached**: that field
is **not** a day-ahead direction signal (6/10 in-block), it is a labeller for the flowless case only.

**E-0717 extended it to n=3 both-polarity within the block** — and found the proposal *as written*
would have **mislabelled its own morning phase**: separating the two objects needs **two axes**, flow
intensity *and* price efficiency. **A withdrawn book continues; an absent book round-trips.** A
correction to its own file.

---

## PER-DAY: ACTION AND REASONING

### 0707 · C · blind −350 → **+150** (actual +160, err 10) — sign FLIPPED
**REASONING.** The blind's direction rested on D-1 aggregate sell flow (0706 session −632, final
phase −1,207). That flow was **absorbed**: 0706 ph3 carries −1,207 against pxchg **+140** with
`ph_absorb` TRUE, closing 0.99 off the low with last-hour flow BUY — a configuration the shared
directive names as explicitly *not* a direction signal. The session that followed ran **+1,748**, the
opposite sign to the blind's projection. The blind had both confirming limbs (big prints 0.593 buy on
n=85 guard-clean; `quote_bid_share` 0.512 bid-leaning) and **used them as a brake rather than a sign
input** — it wrote that it "cannot compute flow_conviction" without price and therefore capped the
down band instead of dropping the tilt.
**MAGNITUDE, leave-one-out (not fitted).** Aligned overnight phases in this leg deliver +250 (0706
ph1 and 0708 ph1 both exactly +250; C's own day excluded); absorbed phases give back 20–60% of the
aligned rung (median ~40%); 250 × 0.60 = **+150**. The fitted answer (summing served phase pxchg)
would have been +170 — C published the harder number.
**CORPUS: INSTANCES FOUND, and one honestly held below the bar.** The refuted mirror arm may survive
at an extreme: the only two readings ≥0.57 in the six-point set are 0611 (0.572, G21) and 0706
(0.593, G23), **both up** — n=2 spanning groups, but **the bar is post-hoc**, so proposed *only* as a
pre-committed forward test for G24+, scope not relaxed.

### 0708 · C · blind +250 → **−520** (actual −520, err 0) — *credit declined*
**REASONING.** Two-regime day, decided at 04:29. Overnight the D-1 tilt genuinely carried — peak
**+800 at 04:28 on only 5.3k lots**. Then turn_down (mag 1,360) and **92k lots of aggressive
selling**: ph2 −1,969/−340, ph3 −808/−450, both ALIGNED, `ph_absorb` false on all three phases, close
0.11 off the low. Realized range 1,460 against the blind's 700–1,000 envelope.
**THE DECLINED CREDIT.** The blind's alternative branch (−300..−500) bracketed the actual but named
the 0608-class **program inversion** (aggressor buying absorbed by roll offers). The tape refutes it
outright: aggressors **sold** (−2,336), price moved *with* the flow, nothing was absorbed,
`resting_program_inverts_aggressor_tilt` did not fire in any form. **C explicitly declines the
credit** — right number, wrong mechanism.
**ITS OWN SECOND ADJUDICATION.** The promotion evidence was price-free and served: 0707 showed signed
flow *building* (+391/+604/+753) while `phase_b_share` **declined and sat below 0.50 in every phase**
(0.498/0.481/0.469) with `big_print_b_share` 0.535 — size-concentrated buying against a broad sell
base, which is absorption by C's own lens. Realized 0707 `ph_absorb` = [F, **T**, **T**] across 101k
of 111k lots. The blind had cited the balanced share as *support* for an organic buy tape; the
pairing is a contradiction.
**CORPUS: SEARCHED, INSUFFICIENT (D24 state b) — and reported as such.** The price-free absorption
tell was tested across **all 30 staged G21–G23 sessions**: loose form gives 2 hits, 3 flats, **2 clean
counterexamples** (0618 +520, 0626 +230); the strict conjunction isolates 0708 alone (n=1, with 0717
a consistent mirror). **Not proposed as a rule.** What C proposed instead is the corpus-wide sweep
plus re-measuring `flow.price_free_absorption_proxy`'s centroids — it read 0.535 (nearer its
absorber-*gone* centroid) against a truth of absorber *present*, and was saved only by failing its
own confirm bar.
**Also proposed (n=2):** STEO-knowable-day revision sign + burn-instrument rank (G21 0610 bullish
revision → +490; G23 0708 bearish → −520), with the ranking clause that a **forward balance revision
outranks a stale realized-grid burn when they contradict** — thin, and said to be thin.

### 0709 · D · blind −250 → **−1,450** (actual −2,050, err 600) — see the decomposition above
**D's window claim, checked and HELD harder than claimed:** it predicted a *range* share and delivered
**59% of NET**; the day's high and turn origin sit at **03:15 ET**, outside any 08:00-start window.
n goes 4 → 5. **The real lesson is a third thing:** the blind **fired the play by name and emitted a
curve contradicting it** — flagged as process discipline, and explicitly **not** named as the cause of
the miss.
**CORPUS: INSTANCES FOUND.** EIA-Thursday session flow **anti-sorts** the day — flow sign agrees with
day-net sign **4/13 on print Thursdays across G17–G23** vs **28/56** on the 56 non-Thursday controls;
this undercuts the blind's D-1-coherence proxy on exactly this day class. And the print-Thursday band
is **absorption-generated**: 5 of the 7 large absorption sessions across G17–G23 are print Thursdays
— *the blind damps when it cannot find coherence, which is backwards on this class.* Four further
items were **flagged below the bar and not proposed** (forward-strip permission, floor removal,
roll-size conversion, the put-wall gamma leg).

### 0710 · E · blind −150 → **−650** (actual −660, err 10)
**REASONING.** Direction stays the blind's; magnitude/turn/shape are causal, derived in three
measurable steps (continuation class off an expanding tape → excursion ~−1,350 → aligned reclaim of
~half), with **the excursion fraction declared as the softest link**. Weight blind 0.40 / causal 0.60
— the sub-half blind weight justified because *the blind's own magnitude instrument was declared
defective in the blind file itself*.
**THREE STACKED CAPS ON ITS OWN DOWN-READ, RANKED:** (1) the burn gate run as a suppressor, which set
−150 **before magnitude was derived**; (2) the D-1 phase misread, which let it delete the driver as
"spent on the tape"; (3) a **declared-degraded vol instrument** that picked a G22 quiet-day universe
(−60/−160/+410) while never-masked fields showed D-1 at **155,141 lots and −2,050** — that is why the
band failed too.
**THE MONDAY RE-RUN.** DOWN-SMALL was correct in sign (−620) **only because the conditional was never
executed** — run as written it flips up. The COT limb is the one piece that held (report 0707
published Fri 15:30, MM −60,295, WoW +4,513 improving, pctile 50.0 → down-small confirmed, seam prior
correctly disarmed; A's flag-1 demotion was right and moot).
**AND THE FIELD IT PROPOSED WOULD HAVE MISLED B:** `residual_tilt` reported **INVERTED** — realized
big-print 0.550 **BUY** against a −1,225 **SELL** aggregate. The very field E instructed B to
substitute would have handed B the wrong Monday sign.
**Corrected handoff** carries a re-labelled `exit_type` (flow-delivered down leg with a **weekend-
squaring reclaim** — session high at the 20:05 reopen, so the +710 afternoon reclaim is squaring, not
accumulation, and Monday handed back 51% of it at the seam) and the chain corrected to **DOWN age 3**
— the blind's "no chain" was an artifact of using signed-flow sign as a substitute, which matched
day-net on only **6/10** sessions and **inverted on the two largest**.

### 0714 · C · blind +280 → **+170** (actual +200, err 30) — the k3 day, above
**Its inheritance read:** the depth regime, and it is *the inverse of the void*. That predicts
something the void reading alone does not — **quiet in both directions** — and week 2 confirms it.
Corroborated by a non-price field (0713 `quote_bid_share` 0.493, 1-tick median spread, 254k quote
updates), and 0714 is the block's **lightest** session; thin books do not do this.
**A further corpus result (state a):** `handoff.residual_tilt_field` should discount a D-1 tilt by its
measured **impact**, not its **provenance** — provenance needs a cohort field that does not exist,
impact is already served. Generalized trigger, measured: **D-1 aggregate flow sign predicts next-day
sign 16/36 = 44% across four groups** — a coin flip everywhere, not a roll-day special case.
**DECLARED (worth carrying):** a **render-vs-leg close discrepancy** — the downsampled `continuous`
carries 2.916–2.919 through 16:51–16:58 ET against the leg's stated close 2.906 (~$100–130 at the
day's most load-bearing point). Scored against the leg; render used for path shape only.

### 0716 · D · blind +300 → **−60** (actual −20, err 40)
**REASONING.** The day was **built before the print and rejected by it.** The reopen→10:29 window
delivered **+560** and set the session HIGH at **10:29:06 — fifty-four seconds before the release**.
Then −570 in nine seconds, a 350-point reclaim in fourteen more, delivery to −770 by 11:08, three
hours of basing, and a covering rally taking back 56% of the overshoot. All three phases flow-ALIGNED
(−101/−60, −2,776/−430, +3,966/+460), `absorb_session` FALSE — **the near-zero net is cancellation of
two convicted legs, not a quiet day.** Posterior derived three independent converging ways, none
fitted: the blind's own pre-declared counter-print branch (0..−300), the 0625 round-trip structure,
and phase 3's aligned buy.
**Its own window claim, checked:** assignment **CONFIRMED** (the window owned the whole up move and
the session high); **mass REFUTED 5×** (+560 vs +110). **CORPUS (state a): the pre-print share of day
travel has median 49.5%, n=14 across 7 groups — the EIA Thursday is half built before the print.**
**Scoring artifact named honestly:** the entire 320 of blind error is magnitude; a "wrong direction"
on a 2.898-vs-2.900 close is a scoring artifact, not a directional failure.

**PROPOSAL 1 — `daytype.eia_print_impulse_arbiter` (corpus-searched, state a).** On a pre-print UP
run ≥ +300, the **60-second impulse** separates continuation from full round-trip **6/6 across five
groups**: inside ±300 → continues (0416, 0430, 0528, 0604); ≤ −300 → round-trips (0625, 0716).
**Stable at 30s / 60s / 120s and degrading at 300s — which places the arbiter inside the first two
minutes, exactly where the NYMEX-canary lag says the platform's edge lives.**

**PROPOSAL 2 — `tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell` (corpus-searched, state a).**
Across **all 70 sessions**, same-day buy flow agrees with price **41% → 29% → 25% → 20%** at the
>+1000 / +1500 / +2000 / +3000 thresholds — **monotone**, with **8 of 10 extreme days closing down** —
while the **sell side is flat at 46 / 43 / 46 / 47%**, and **the D-1 version is a coin flip (4/9)**.
**That is precisely D's own blind error, named: it cited 0715's +6,326 — the largest buy flow in seven
groups — as bullish evidence, reading a same-day bearish tell as a next-day bullish one.**

**Thursday anti-sort reproduced independently:** 4/13 vs 28/56 controls; D's own day is a member
(+1,089 buy flow, −20 close); g23 alone is Thursdays 0/2, non-Thursdays 6/8. **Honest strength
p ≈ 0.13 — a lead, not a proof.**

### 0717 · E · blind +180 → **+180 CONFIRMED** (actual +180, err 0) — the hardest refine
**THE THREE-WAY VERDICT on "right for the right reasons or right by cancellation":**
- **Right for the right reasons** — direction from the D-1 program-free tilt (realized tape confirms:
  session flow +1,333, ph3 +1,157); the crest-trim counter-fade **stand-down** (firing it would have
  inverted the sign); and the exit-location call, correct in every clause (high 13:48, close 0.88 off
  the low, off the high, last hour negative in both price and flow).
- **Right with a refuted instrument** — the burn gate's up-limb kept the band and licensed a
  "morning delivery on burn-51" story. Its +600 band top was **unreachable — there was no delivery to
  have.** By E's own successor rule the balance was **loosening** (injection +5.4 above 5-yr pace,
  third straight above-pace week, surplus 151 → 156 → 162, STEO production revised up three months):
  **no up-licence from burn at all.**
- **Right by cancellation** — the path. The blind drifted monotonically up and never went below zero;
  the session was **−540 at 08:19**. Mean node error **228 USD**, max adverse excursion **530 against
  a +180 outcome** (MAE:outcome 2.9). E's corrected path scores **175 — a 23% gain bought by refusing
  to forecast the overnight, not by knowing it.**
**ACTION: CONFIRM, not move.** Standalone causal derivation lands **+170** (void pair 0, ph3 handover
+200, settle trim −30) at ±350 resolution; +180 sits inside it, so moving it would be false
precision. It **published `derived_centre_standalone_usd: 170`** so the confirm is auditable. Weight
blind 0.70 / causal 0.30 — *the inverse of its 0710 split, because here the number survived but its
mechanism did not.*
**Realized structure worth keeping:** overnight **−490 on 3,498 lots** (5.5% of session volume,
**140.1 USD per 1,000 lots — the block's price-efficiency maximum by 3×**), low −540 at 08:19, then a
**near-flowless reclaim +560 on 31,052 lots at 0.95% flow intensity**, then the day's only conviction
phase (**+1,157 net buy lots buying 130 USD** — the day's *worst* efficiency), high +290 at 13:48,
−100 into the settle. **The up was delivered by the two low-conviction phases; the phase with real
buying was absorbed.**
**Third exit form named** (reclaim completed / extension failed — neither covering-into-settle nor the
0710 reopen-high squaring), chain corrected from "up-flow age 4" to **NO CHAIN** on a 200-USD
four-session shelf.
**Post-program vacuum:** the window arithmetic reproduces, and so does the error split — **4,330 of
5,920 on those five days, four of the five misses over 500**. But program and print are confounded in
one window, so it licenses a **magnitude class, not a direction play**. E's day is a textbook
instance: 63,165 lots, 21.4 trades/min — the block's thinnest real session.

---

## STANDING DEFECTS THE WHOLE GROUP DECLARED

- **`g23_mbo_feature_states.jsonl` and `g23_mbo_l1_manifest.json` DO NOT EXIST** (present for g15,
  absent g21/g22/g23) though the canonical shared directive lists them as required refine inputs. **No
  `book_trustworthy` verdict is derivable, so the MBO book layer stood down GROUP-WIDE.** Sharpest
  cost, named by E-0717: *the absent-book hypothesis is its own ph1 mechanism, and the missing files
  are the ones that would test it.*
- **Only NGQ26 is staged.** A roll is a calendar spread; aggressive roll execution and outright
  liquidation are **indistinguishable in a single-leg tape**, so the block's biggest attribution
  question is unanswerable as staged. Staging NGU26 (or the spread) settles it.
- **Session 0710's full-session tape is absent from every slice** (Monday keys carry 149/256-trade
  Sunday stubs as "prior session") — flagged independently by four specialists in the blind and again
  in the refine.
- `contract_structure` frozen at the 0703 vintage on all ten days (spread evolution through the roll
  window unavailable by construction); `storage_consensus` dead post-0709; `vol_regime` n0 era-degraded
  (~0.226 of leg tape); `grid_stack` serves **no `wind_chg_7d`** — a limb now load-bearing for a
  refutation; no phase timestamps (boundaries reconstructed, ~30 min slop).
- **A tooling defect found by a specialist before any gate saw it (E-0717):** two refine posteriors use
  a nested `days[]` wrapper while four use a flat day record — both legitimate readings of the shared
  contract. Fixed in `merge_perday` (the JOIN normalizes); **the posteriors were not edited**, because
  they are the record.

---
