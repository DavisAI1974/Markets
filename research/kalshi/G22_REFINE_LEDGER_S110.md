# G22 REFINE REASONING LEDGER — S110

**Why this file exists (Greg, S110):** *"are we logging the context of the refine's decisions? those are
probably the most useful."* Audit answer: the structured reasoning IS committed (390 KB across the ten
r1 posteriors and five r2 files — `evidence_used`, `evidence_rejected`, `stand_down_reasons`,
`magnitude_derivation`, `mbo_verdict`, `proposal_contribution`). What was NOT captured is the
specialists' PROSE SUMMARIES — the sharpest framing of the run — and the distilled cross-day
narrative. S109 built a ledger for the G22 BLIND because Greg asked in-session; nobody made it
standing procedure, so the refine had none. Now required by SOP v1.4.

Scope: the G22 refine, brain s103.7, per-day causal isolation.
Score: blind 4/10 · sum|err| 5,965 · drift −1,815 → **r1 10/10 · 500 · −80** → **r2 10/10 · 330 · +50**.

---

## PART 1 — DECISIONS THAT WERE RIGHT, AND THE REASONING THAT PRODUCED THEM

### 1.1 C separated a ROLL-DOWN from a REVISION (0624, blind −200 → +600, actual +800)
The blind read `run_delta_cdd −0.011` as "nothing new, therefore priced, therefore inert." C found
the +2.2 gw-CDD step was **not a forecast revision at all**: 0623's h1 view of 06-24 was 10.034 and
0624's D0 view is 10.022 — the mass **rolled down** into the near window while the skeptic model
capitulated upward (MET 8.402 → 9.115, spread 1.632 → 0.907). The blind applied the revision arm to
a roll-down event. **The brain already held the right instrument** — the s101.6 pricing-time rule
(moderate adds price at near-window ENTRY, D0..D+2), which supersedes the revision read by its own
text. Replicable rule: *before reading a delta as "priced," check whether the level moved by
revision or by the window advancing.*

### 1.2 C proved the flip was NOT tape-callable, and said so (0624)
C checked `giveback_exhaustion` limb by limb **with price visible** and it fails all three (chain age
2, cum −80, no D-1 absorption tell); the accumulation arm's silence was *correct*. Conclusion stated
plainly: **no tape instrument could have called this flip — the instrument was the weather slope.**
Why it matters: a refine that manufactures a tape story for a fundamentals day teaches the blind to
hallucinate one. The honest negative is the lesson.

### 1.3 D re-verified its own consensus reconstruction against the price curve (0625, err −10)
Blind used 67.0 (strictly pre-print) over the served 74.0 (post-print capture). The refine confirmed
it from the other side: **a −770 flush in 18 minutes pinned to 10:30** is the signature of a genuine
unpriced surprise, not an in-line print inside a 7 Bcf dispersion. Decision-time surprise **+9
bearish**, not the served +2. Adjacent trap found: top-level `stor_surprise` −5.0 on a print-day
slice is the *prior* print's seasonal surprise — mislabel-shaped, flagged.

### 1.4 E re-derived the roll confound independently and AGREED with the settlement (0626, err 0)
Seven measured quantities, including the control: 0625 was also a scheduled-flow day (opex + EIA) and
shows **none** of the fingerprints. Big-print cohort 210 @ 0.783 contributing ≥ ~+4,800 net buy while
session flow was only +871 → the organic residual **sold** ~3,900–8,600 lots; breadth unmoved
(0.509 → 0.504). Fires on the letter, void on the mechanism.

### 1.5 E's corrected flip test survived its own re-execution (0626 → 0629)
E re-classified its exit **MOMENTUM_CARRY → POSITIONING_SPENT_FADE** and re-specified the flip as
two limbs: flip UP only if (1) weekend cycles add gw_cdd **AND** (2) the burn confirms. Executed on
the realized weekend: limb 1 passes (+4.8 CDD), **limb 2 fails decisively** (burn 38.6 → 34.4, wind
+62%) → HOLD DOWN. **E's original blind sign survives its own corrected test** — the S109 ledger's
"perfect process, wrong outcome" resolved by adding the missing limb, not by reversing the process.

### 1.6 B answered the P3 question as a CONFIRMED NEGATIVE plus a positive (0622)
Gap **not ownable as a number** from any decision-legit channel — walked channel by channel (Friday
exit pointed down; CDD ladder had no forward levels; calendar mild; positioning could not sign it,
the same 2.83-pctile book sat under G21's 0614 seam that gapped −750). **But ownable in SIGN**:
`model_disagreement.stability` served +0.58/+0.42/+0.47/+1.01/+0.52 across h1–h5 — every reachable
horizon hotter, sum +3.0 — while every purpose-built weekend feed was HDD-only and read ~zero on the
wrong axis. 3/3 seams called (0614 −750, 0621 +1,210, 0628 +50); positioning 1/3. **The channel's own
label ("uncertainty conditioner") steered readers away** → the new audit kind, *served-but-mislabeled*.

### 1.7 B derived the 0629 sign at the reopen, BEFORE any session tape (err 110)
Re-executed E's two-limb test from its own slice, got HOLD DOWN pre-tape, then derived
DOWN-how-much from exactly three terms: fade-class crest remainder (−230), the block's own bleed
scale (−560/−730 realized), constraint floor (−150..−200). Stack ≈ −1,050 session / −1,000 day
against actual −1,110. The 14:52 capitulation tranche **explicitly not claimed**.

### 1.8 A stood on a repair clause it had authored and refuted itself (0703)
`thin_session_range_invariance` — sqrt(participation) survives its **second consecutive forward
pass** (net 410 vs 453 predicted). New nuance: thinness scaled magnitude, not direction; the
holiday-eve session carries a **risk-bound** participant (weekend squaring) that tilts sign without
preserving range — distinct from the volume-bound class.

---

## PART 2 — SELF-CATCHES AND CORRECTIONS

### 2.1 D audited its own timing claim and called it WRONG (0702)
Blind put ~12–13% of path mass pre-10:30 (positive); realized pre-print share was ~38% of leg travel,
all down. **The falsifier window was drawn too narrow** — it named 08:00–10:30, which netted just −50
and "never fired" while the decomposition failed anyway. Corrected rule: pre-print window =
**reopen → 10:30**. A right net (0) with a wrong window is a different lesson than a wrong net, and
only the decomposition separates them.

### 2.2 D re-derived its own point and named its r1 slack (0702, r2)
r2 kept the point at 0 but re-derived it as *reclaim-to-boundary*, and named two timing slacks
against the authoritative curve: the r1 seam front-ran the onset, and the r1 afternoon clock ran ~1h
early. Same number, better mechanism, stated as a correction rather than a confirmation.

### 2.3 C recorded the honest in-block NEGATIVE on its own new channel (0701)
Wind read this time — but recorded plainly: **wind does not sort day sign** (0630 printed +780 under
a rising-wind slice). It is a **damper, never a sorter**. That caveat went into the merged play text.

### 2.4 A found the two-sided derivation the r1 could only bound one way (0703, r2)
D's phase grammar (reclaim paid, extension denied) transferred one altitude up and became A's close
cap: two independent derivations — sqrt-participation (440–453) and the reclaim-cap ceiling (~500) —
triangulating the same center. **The handoff's value is that it hands the next owner the
interpretation, not the number.**

### 2.5 C found the HE24 boundary is a fourth phase sample (r2)
dir-vs-flow at the exit sorted the next session's class **5/5 in G22**: failing dip-buys →
continuation down; absorption → reversal up; still-delivering stall → give-back; unpaid late
extension → round-trip. Honest n stated by C itself: 5 boundaries in ONE block, two arms with
cross-group siblings. Owned-set error r1 340 → r2 170 (blind 2,620).

### 2.6 B found the seam TURN CLOCK, both edges (r2)
On a weekend seam the turn lands at a **model-posting-window edge**, and covering-license × burn-
constraint selects WHICH edge: licensed+confirmed → the LAST window (0622 high 04:07–04:09, verified);
unlicensed+vetoed → the FIRST window with the second hot cycle **ignored** (0629 died 22:55/23:32,
then straight down through the posting window). By ~04:30 ET the seam has classified the Monday.

---

## PART 3 — THE CROSS-CUTTING FINDING THREE SPECIALISTS CONVERGED ON

**"READ-AT-THE-WRONG-LEVEL" — gross where the tradeable object is the RESIDUAL.** Named by E,
co-signed by B and A, three instances in one block:

| instance | gross (what was read) | residual (what traded) |
|---|---|---|
| expiry Friday 0626 | aggressor flow +871 | ex-program residual: net SELLING |
| Monday 0629 | CDD add +4.8 realized | burn residual −4.2 Bcf/d (wind +62%) |
| Monday 0629 gate | D-1 tilt aggregate | program-decontaminated tilt |

Every one passes every reconciliation, because the value **is** correct — as the wrong object. Merged
into `agents/state_auditor.md` as known-kind #6, beside #7 *served-but-mislabeled* (§1.6).

---

## PART 4 — WHAT THE LEDGER ITSELF TEACHES

Three of the ten best reads came from **standing down** a play whose reading agreed with the
specialist's own number (C's accumulation arm on trajectory; E's refute-limb on the roll; D's
surviving selection limb). Two came from **refusing to force** a branch (B's gap ownership; D's
"already priced" limb). One came from **auditing its own falsifier** and reporting the failure
(D-0702). None came from finding a new signal.

The generalizable claim: **at this stage the refine's value is disciplined subtraction — removing
instruments that fire on the letter and void on the mechanism.** The blind's remaining error is not
mostly a missing signal; it is a handful of instruments reading the wrong object at the wrong level
in the wrong window.
---

## PART 5 — THE PER-DAY RECORD: ACTION AND REASONING, AS THE SPECIALISTS STATED IT

Captured from the specialists' own run summaries (S110). These die with the session unless written
down; every number below is bound by the DECISION CLAIMS table at the end of this file. Format:
**ACTION** = what it decided. **REASONING** = why, in its terms. **DECLARED** = what it refused to
work around.

### 0622 · B · blind −420 → r1 +650 (actual +650, err 0) · r2 held +650
**ACTION.** +650, band [450,900] → r2 [450,800]; gap and session emitted and scored separately.
**REASONING.** The P3 question answered mechanically: the +1,210 gap was NOT ownable as a NUMBER
from any decision-legit channel — the Friday exit pointed down; the CDD ladder had no forward levels
(h1 *below* h0); the calendar was mild mechanics; positioning could not sign it, since the same
2.83-pctile worsening book sat under G21's 0614 seam that gapped **−750**. **But ownable in SIGN**:
`model_disagreement.stability` (Sun 12Z vs Sat 12Z, pre-reopen legit) served d_gw_cdd
+0.58/+0.42/+0.47/+1.01/+0.52 at h1–h5, sum +3.0 — every reachable horizon revised hotter — while
every purpose-built weekend feed is HDD-only and read ~zero on the wrong axis. So seam SIGN = the
revision ladder (3/3: 0614 −750, 0621 +1,210, 0628 +50; positioning 1/3), and seam GAIN =
positioning extremeness (|gap|/σ 1.2 and 2.0 at the crowded-worsening book vs 0.08 at the normalized
one). Add-size → gap-size is INVERTED across instances, and reopen participation is refuted in both
directions (252 lots → +1,210; a 194-trade stub → +50). r2 hardened the timing into a rule:
licensed + confirmed seams buy BOTH in-gap hot cycles and turn at the LAST posting window's edge
(GFS 00Z 03:30–04:30; tape high 04:07–04:09), then the 06–10 catch-up window round-trips (−710).
The session engine survives untouched: −440 against −560, err 120.
**DECLARED.** The stability channel's own label ("uncertainty conditioner") steers readers away —
served-but-MISLABELED; sunday_reopen HDD-only, its cost now priced at −1,070 of day error; n0
era-degraded; Monday grid_stack serves Saturday (burn confirms at D+2).

### 0623 · C · blind −430 → r1 −700 (actual −730, err 30) · r2 held −700, band tightened
**ACTION.** −700, band [−880,−520] → r2 [−820,−580]; direction confirmed and repositioned INSIDE
the blind's own fired play band (s1void trend −450..−780) rather than below it.
**REASONING.** The blind trimmed under its band's low end for two reasons the causal evidence
dissolves: Monday's −3,942 sell flow DELIVERED −560 with zero absorption (resolving the blind's own
declared-unresolvable branch), and the session printed the cleanest C-lens tape of the block — an
unpaid overnight lift (+470 crest at 01:02 on net-SELL flow: negative conviction under rising price)
that round-tripped at the 01:02 turn, then both body phases aligned-sell (−1,281/−430; −593/−460),
ph_absorb false throughout, low −910 at 12:42, close_off_low 0.13. Aligned delivers the band. Spent
covering (MM +37.7k WoW, pctile 2.83 → 25.5, published Monday 15:30) floors the flush AND caps the
extension — hence −700, not the −890 tail. On the hill: 0623 is the local TROUGH on the
decision-time track (fCDD 9.06 → 7.82 → 10.02) with every slope input mild-side (run_delta_cdd
−0.486, NAM −1.463, MET 0.74 under MAV), so under the asymmetric doctrine this is the down-slope
step. The renewable subtractor was served AND CONFIRMING here — wind +21% d/d, burn 33.0 (−1.3 d/d),
gas_chg_7d −664k MWh — the mirror of 0629, making it n=2 in-block with OPPOSITE interaction signs.
**DECLARED.** No decision-legit consensus existed for the 06-25 print on this day (both estimates[]
captures post-date it; even the "pre-print" 67.0 is stamped 06-25T06:25Z); the CDD ladder ends
06-24; 0622's lo_et sits ~2 min past its session boundary; book layer stood down (no
book_trustworthy verdict served).

### 0624 · C · blind −200 → r1 +600 (actual +800, err 200) · r2 raised to +700 (err 100)
**ACTION.** Flip to UP; r2 raised the point using the handoff's cum −80 to define repriceable width.
**REASONING.** See §1.1 (roll-down vs revision) and §1.2 (not tape-callable). The mechanics behind
them: the burn channel was OPEN and unread in the blind — demand +8.3% d/d, wind −22%,
est_gas_burn 33.0 → 39.3 Bcf/d (+6.3), the exact mirror of 0629. The tape confirms the driver was
EXOGENOUS: price +790 on net aggressor flow of just +311 over ~70k lots — passive markup, ph1/ph2
aligned, ph3 flowless (+410 px on −69 flow, explicitly NOT called absorption because ph_absorb is
false and the flow is noise-level). Timing cycle-clocked (04:00 = 00z; the 06–08 main leg = 06z plus
morning burn data; 10:00 pre-opex retrace; late high 19:17). Magnitude derived from the measured
moderate-entry class (G13 0220's +590 floor; 0222's +1,310 EXCLUDED as a delivery-pull on a deferred
leg) with the S109 asymmetry damp; the last ~200 of extension on negative flow left unclaimed. r2:
cum_from_anchor −80 means Sunday's heat premium was fully given back, which defines the repriceable
width to the 3.263 pre-giveback shelf (+730), triangulating with the r1 floor-class derivation.
**DECLARED.** The CDD forecast ladder ends at D+1 (HDD-only horizons) — the hill's steep 0629+
segment was structurally invisible in the slice; the "hard_cool" regime label is an HDD-derived
artifact inside a CDD block.

### 0625 · D · blind −110 → r1 −70 (actual −60, err 10) · r2 held −70, band tightened
**ACTION.** −70, band [−250,+150] → r2 [−180,+80]; weights blind 0.55 / causal 0.45.
**REASONING.** See §1.3 — the consensus reconstruction corroborated from the other side by an
18-minute −770 flush pinned to 10:30 (10:29 +340 → 10:48 −490), which is the signature of a genuine
unpriced surprise, not an in-line print inside a 7 Bcf dispersion. The realized day was three round
trips: an overnight slope ramp (+766 flow / +620 px, aligned), a net-zero two-sided auction across
top → print-flush → full reclaim (−12 flow on 70,526 lots under a $1,280 range — degenerate
conviction, declared as such), and a ph3 BUY-ABSORPTION close (+1,202 flow / −290 px, absorb=true)
that denied the 14:00 opex push and decided the close. What the blind structurally could not see:
0624 was a +790 break closing 0.97 off-low — flow-only cannot separate a coil from an absorbed
break. r2's incoming exit was a CROSSED pair (last_hour_dir +1 on signed_flow −1): the break entered
the seam pre-absorbed, which sizes the seam as carry-then-ceiling — exactly what the tape did (+190
by 22:00, stall, 03:14 onset to +600, spike top +850 at 09:01 fading pre-print).
**DECLARED.** Top-level `stor_surprise` −5.0 on a print-day slice is the PRIOR print's seasonal
surprise — mislabel-shaped; no phase clock boundaries (reconstructed ~04:00/~12:00); options_surface
on the block's one opex day, where the 14:00–15:00 window visibly swung $560.

### 0626 · E · blind +250 → r1 +230 (actual +230, err 0) · r2 held 230
**ACTION.** 230, band [130,330] → r2 [160,300]; exit re-classified MOMENTUM_CARRY →
POSITIONING_SPENT_FADE; corrected two-limb flip condition emitted.
**REASONING.** See §1.4 and §1.5. Path corrected: delivery was OVERNIGHT (onset 01:43, +700 by
02:00, crest +1,110 at 08:40) and the entire RTH was a roll-execution giveback to a close at 0.23 of
range — the blind had drawn an RTH climb. r2 pinned the gap (0625's close 3.264 equals the open
exactly, so day-move = session net), explained the seam residue (the 20:01 low is 0625's aligned
last-hour selling dying one minute into the reopen), and gave the 01:43 onset its D-1 antecedent:
0625's two-sided compression — defended floor, absorbed top — releasing a capped buy overhang into a
5,653-lot book, plus the pre-LTD roll bid. Second consecutive morning-crest-then-RTH-fade, which is
D's reclaim-and-stall read realized at day scale. The handoff strengthened to a TWO-SESSION
absorption basis with a new `delivery_decay_sequence` field (+790 → −60 → +230-with-79%-giveback).
**DECLARED.** The forward CDD ladder is still HDD-only in the refine slices; no book_trustworthy
fields exist in the MBO evidence, so the book layer stood down throughout.

### 0629 · B · blind +325 → r1 −1,000 (actual −1,110, err 110) · r2 held −1,000, band tightened
**ACTION.** Override to DOWN, derived at the Sunday reopen BEFORE any session tape; band
[−650,−1,250] → r2 [−890,−1,110]; weights blind 0.35 / causal 0.65.
**REASONING.** See §1.7. B was explicit that the sign correction is the blind's OWN D-1-tilt rule
fed a decontaminated input, not a doctrine override. Component scoring on DISJOINT instruments: the
GAP failed on branch adjudication — it took the fresh arm on step size (+4.7) when the real test is
LADDER VISIBILITY, and growth of a hill already in the ladder is the PRICED branch — aggravated by a
3-for-3 under-forecast prior drawn entirely from not-in-ladder winter shots, and by an era-degraded
sigma conditioner. The SESSION failed on four separate instruments: the tilt gate fed the
roll-contaminated aggregate (+871) instead of the sell residual B had itself derived and then
weighted 0.10; `carry_realization_flip` was applied at the GROSS level (peak-ahead true of CDD,
false of burn); `divergence_resolution`'s session leg was sized gap-relative instead of at the
bleed's served scale; and grid_stack sat served-in-every-slice, unread. MBO confirms the chain
end-to-end: 23:32 Sunday rejection, flow-free overnight markdown (+53 flow / −440 px), ALIGNED
catch-up delivery (−3,770 / −650, zero absorb flags), close 0.09 off low. The 14:52 capitulation
tranche explicitly not claimed. r2 added the seam turn clock's second edge: an unlicensed book plus
a burn veto caps the pop at +150..+350 and kills it at the FIRST window's edge (22:55/23:32), after
which the second hot cycle prints into a falling tape and is IGNORED (−440 by 06:00, tape-verified).
**DECLARED.** The seam_delta_warning and the sunday_reopen CDD ladder are NOT in the committed state
(0 grep hits) — the S109 P4 nonconformance, found mid-refine; the level rule was executed by hand
instead, and it yields the sign at decision time.

### 0630 · C · blind −420 → r1 +700 (actual +780, err 80) · r2 raised to +750 (err 30)
**ACTION.** Flip to UP; weights blind 0.15 / causal 0.85 — the largest causal weight of the block.
**REASONING.** The blind's sign rested on one assumption it had itself declared untestable: that
0629's clean sell tape (−4,547, big prints 0.322 on 267) was UNABSORBED. The tape refutes it at
three grains — the 0629 exit already showed price ticking UP under sell flow off a low set 2h+
before the close; the overnight chain-extension probe died at −130/−160 by 23:54 and turned up
~02:30 ET; then mid-session −4,266 of sell flow was ABSORBED under a +880 price rise (ph_absorb
true, absorb_session true), and the block's largest aggressive sell session closed +790. Per
`absorption_is_reversal` the absorbed side loses: sized as a 50–75% retrace of the one-session
−1,160 crash, capped under the 0626 origin shelf because storage (+112 vs 5yr, 81 loose) and neutral
COT (29.25 pctile — no squeeze fuel) still own the backdrop; the +1,530 high is reactive tail, not
claimed; the round-trip risk printed as the aligned-sell ph3 give-back into the close. r2 raised it
because the incoming 0629 boundary showed absorption ALREADY BEGUN (dir +1 under flow −1, low 2h+
old, close 0.09 off low) — the strongest form of the setup, which moves it to the upper half of the
crash-retrace class.
**DECLARED.** The wave-1 VOID file's 0630 wind read cited period 06-29 grid fields the legitimate
slice does not serve (the mechanism survives on the 06-28 slice at +91%); grid_stack weekday
confound at 2-day staleness; one play conflict logged —
`boundary.prior_close_flow_direction_disagreement`'s distribution arm resolved the WRONG way at the
0629 exit (n=1, observation only).

### 0701 · C · blind −380 → r1 −470 (actual −500, err 30) · r2 −490 (err 10)
**ACTION.** Confirm DOWN and resize; weights 0.55 / 0.45.
**REASONING.** The curve re-grounds WHY the blind was right: the −5,573 sell tape it leaned on never
delivered on 0630 — price reveals it was absorbed into a +790 conviction-negative covering pop
(ph2: −4,266 flow vs +880 price). That is the g19 distribution-flip pre-warning configuration
exactly, and it kills the covering-UP prior for the NEXT session; 0701 is that session. The day was
a give-back that ground −500 on flow-flat tape (−73 total; failing dip-buys under falling price),
with the one retest of the pop dying at a 09:02 LOWER HIGH (3.270 vs 0630's 3.328) inside ten
minutes. The blind's "flatten from 14 ET" shape leg was wrong — a give-back day's late longs
squaring into the print are supply, not lift. Magnitude derived at ~60% of the pop, floored by the
live CDD slope, that floor muted by the constraint term. The accumulation-arm stand-down upgraded
from two inferred legs to THREE MEASURED ones: tape (buy-absorption ≥0.55 on only 1 of 5 sessions),
COT (29.25 pctile, improving +2,187 WoW), and now price (no turn ever delivered; the sole post-pop
up-excursion was +160 and rejected).
**DECLARED.** Wind at block-max (2.137M MWh, third straight climb) plus nuclear returning mutes the
heat floor — but the honest in-block NEGATIVE is recorded: WIND DOES NOT SORT DAY SIGN (0630 printed
+780 under a rising-wind slice). It is a damper, never a sorter.

### 0702 · D · blind +200 → r1 0 (actual 0, err 0) · r2 held 0, re-derived
**ACTION.** 0, band [−150,+150] → r2 [−120,+100]; weights 0.40 / 0.60.
**REASONING.** PRINT = EXHAUSTION, NOT IGNITION. The chain's residual delivered OVERNIGHT (onset
03:03, aligned ph1 −126 flow / −280 px, −480 by 08:59). The 10:30:00 release flushed −230 in ten
seconds to a marginal new low (−530, only −50 under the overnight low) — a stop-run into the
absorber, on a print that was actually −1.4 BELOW consensus, so surprise sign sorted neither the
impulse nor the day. The flush absorbed (ph2: −1,612 sold for +20 of price), the 10:39 retest held,
turn_up 530 from the print tick. The whole recovery ran on negative conviction (ph3: −1,123 sold
under +250, absorb-flagged): covering reclaims the excursion but earns no new ground — the +160 high
at 15:53 faded to a dead-flat close. Magnitude derived, not fitted: absorption_is_reversal gets the
reclaim at FULL size (+530, never damped — D's own g20_0528 lesson honored), while extension beyond
the reclaim required an aligned phase that never printed. r2 re-derived the same 0 as
reclaim-to-boundary and named two r1 timing slacks against the authoritative curve.
**DECLARED.** See §2.1 — the window audit called its own blind claim WRONG. Also: the downsampled
render clips the print low (−490 shown vs −530 authoritative); and the phase-straddle cost is now
demonstrated (ph2 nets +20 while containing both the −250 pre-print slide and the +270 post-print
recovery — turn_et is what saved the read).

### 0703 · A · blind −160 → r1 +450 (actual +410, err 40) · r2 held +450, band tightened
**ACTION.** UP +450, band [300,560] → r2 [340,510]; the G23 anchor handoff emitted.
**REASONING.** The day never traded below its 20:00 reopen print, climbed +540 overnight, crested
+680 at 10:07, closed +410 at 0.59 of range — and did all of it against NEGATIVE aggressor flow in
every phase (total −1,005, absorb_session TRUE). That is the G18 covering/procurement signature, and
it was seeded the day before: 0702's coherent sell tape (−2,861, the blind's whole down case) was
ABSORBED under a flat-then-rising price, ph_absorb [F,T,T] strengthening into a 0.77-off-low close,
turn_up 10:30, net 0 — the tilt measured the losers. The sign flip was licensed on two independent
channels: the D-1 absorption exit state, and the burn-confirmed hill up-arm (burn 44.8 Bcf/d = block
max, wind fading, both models agreeing at the 18.8-CDD crest) — which is E's two-limb test PASSING
from the side opposite 0629. The crest was vs-normal ~0.0, so the rally was burn-led (constraint
releasing), not anomaly-led. r2 added the second derivation (see §2.4).
**DECLARED.** Session close time is still not served on shortened sessions: the tape shows
20:00:00 → 12:59:58 ET (1,020 min), matching the blind's assumed 13:00 by CONVENTION-LUCK rather
than by data, while the state still carries `cme_early_close: false` on a `partial_session`.

---

## DECISION CLAIMS (machine-checked - do not hand-edit; regenerate with `python decision_trace.py claims <gid>`)

| date | owner | phase | number | decision_id |
|---|---|---|---|---|
| 20260622 | B | blind | -420 | `072d52a6f475` |
| 20260622 | B | refine_r1 | +650 | `af2a319ca0ed` |
| 20260622 | B | refine_r2 | +650 | `af2a319ca0ed` |
| 20260623 | C | blind | -430 | `9ba7dca4d555` |
| 20260623 | C | refine_r1 | -700 | `65147514c786` |
| 20260623 | C | refine_r2 | -700 | `65147514c786` |
| 20260624 | C | blind | -200 | `9d813b96b772` |
| 20260624 | C | refine_r1 | +600 | `8f037a42fe8d` |
| 20260624 | C | refine_r2 | +700 | `14cd8a972924` |
| 20260625 | D | blind | -110 | `d080ba58adf5` |
| 20260625 | D | refine_r1 | -70 | `6d64d73ec460` |
| 20260625 | D | refine_r2 | -70 | `6d64d73ec460` |
| 20260626 | E | blind | +250 | `dd476bf17075` |
| 20260626 | E | refine_r1 | +230 | `3eca232aaeb6` |
| 20260626 | E | refine_r2 | +230 | `3eca232aaeb6` |
| 20260629 | B | blind | +325 | `1af30be59d28` |
| 20260629 | B | refine_r1 | -1000 | `34a4f46fe057` |
| 20260629 | B | refine_r2 | -1000 | `34a4f46fe057` |
| 20260630 | C | blind | -420 | `7d54b97e89fb` |
| 20260630 | C | refine_r1 | +700 | `66e9c72e2d63` |
| 20260630 | C | refine_r2 | +750 | `27bd098eddb5` |
| 20260701 | C | blind | -380 | `848991d524fc` |
| 20260701 | C | refine_r1 | -470 | `b9985f6ed78e` |
| 20260701 | C | refine_r2 | -490 | `53ebac970ca4` |
| 20260702 | D | blind | +200 | `d4f8fd78755d` |
| 20260702 | D | refine_r1 | +0 | `a11d6e131e5d` |
| 20260702 | D | refine_r2 | +0 | `a11d6e131e5d` |
| 20260703 | A | blind | -160 | `db7ddf0b69e6` |
| 20260703 | A | refine_r1 | +450 | `b144708a9d82` |
| 20260703 | A | refine_r2 | +450 | `b144708a9d82` |

