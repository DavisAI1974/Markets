# G23 BLIND REASONING LEDGER — S110

**Why this file exists (Greg, S110):** *"we need to go back through the agents' summaries and pick the
reasoning along with their actions and populate this file with it."* The specialists' run summaries
live only in the session transcript; this is the durable capture. Every number is bound by the
DECISION CLAIMS table at the end (regenerate at close-out once the refine completes).

**A demonstration of why co-location matters, recorded because it happened here:** B's two Monday
agents hit the session usage limit and died **while composing their summaries** — that prose is
gone. Their REASONING survived completely, because it was written INSIDE the posterior beside the
number. The artifact that co-locates answer and explanation was the one that survived; the one that
separated them was not.

Scope: the G23 blind, brain **s104.0** (the S110 merge's first forward test), per-day causal slices,
on the ladder-repaired state.
Score: **5/10 dir · sum|err| 5,920 (2nd-best of the walk) · drift +4,900 · survives 83%.**
Actual cum **−3,290** vs blind cum **+1,610**. Every prior block leaned DOWN; this one leaned UP.

---

## PART 0 — THE PRE-LINE AUDIT (state auditor, before any forecast)

**ACTION.** 5 findings, 15 clean areas, 8 uncheckables; all 5 adjudicated GO and fixed pre-blind.
**REASONING.** The severe pair was one family: the block's final day served a flow/b-share family
computed on a **~44% truncated tape** while the session counts beside it came from the leg (f1) —
and the root cause (f2) was that the S108 off-instrument fix **never reached the flow channel**:
nothing anywhere set `flow_read._ACTIVE_LEGS`, so its leg path was dead code and the cont-store
max-count fallback served every staged group, correct elsewhere only by a ranking accident. Worse,
the gate built after that hole compared a leg-sourced field against the leg — 1.00 by construction,
structurally blind. Also found: the consensus survey store died after the 07-09 print while the
state kept serving that print as `last_print` for eight days (f4); the n0 volatility basis carries
~23% of the scored tape in the leg era (f3); option strikes sit 10× off the $/MMBtu convention in
every group that carries them (f5).
**CONSEQUENCE.** Four new HARD reconciliation guards, negative-tested (25 true fires across the two
live states, zero false positives across 46 clean scopes in 17 historical groups). No completed
score was affected — the pre-blind gate did exactly its job.

---

## PART 1 — THE PER-DAY RECORD: ACTION AND REASONING

### 0706 · B · +500 (actual +100, err 400 — direction right)
**ACTION.** +500; gap +400 / session +100 emitted **split**, the gap explicitly a BAND TOKEN
(+150..+700) rather than a point claim.
**REASONING.** Seam sign UP from the stability ladder: D0 add confirmed by all three models (GFS
+0.963, NAM +0.930, MEX +0.579 gw-CDD), the MEX multi-horizon ladder 4/6 positive (adds ~2.59 vs
cuts ~0.19), merged run-deltas 5/6 positive summing +3.57 — coherent-*enough*, and B tempered
confidence precisely because it is **not** the strict all-horizons-same-way form. The burn gate says
the add CONVERTS: 42.9 Bcf/d on the freshest same-day-class row (Sat 0704) with Sat-over-Sat gas
generation +1.11M MWh — the weekday-normalized form the play requires. Gain term: NYMEX MM at 29.25
pctile improving = MID-BOOK, so the 0.5–1.0× σ band applies, **not** the extreme band; the ICE LD1
book at 2.83 pctile and worsening was recorded as covering fuel on a **separate book, never pooled**
into the gain.
**DECLARED.** The seam LEVEL difference — the named play's required input — was **not computable**
from the slice; wind trend unserved (no `wind_chg_7d`), so the burn limb was licensed at the
lower-middle of its class rather than the top; n0 σ era-degraded.

### 0707 · C · −350 (actual +160, err 510 — WRONG)
**ACTION.** −350, confidence LOW, no hard chain asserted.
**REASONING.** Direction stayed with the D-1 tilt per doctrine: Monday sold its close (final phase
−1,207 at 0.474 two-sided; session −632 on 95.6k lots), 0703 was all-sell phases closing in its
lower quarter, the S3 backdrop is bearish (+151 vs 5yr; +87 print vs +47.8 seasonal), ICE LD1 longs
liquidating at a 1-year extreme (0.94 pctile, −27.5k WoW), and the GSCI roll opens tomorrow. **The
claim was capped, not extended**, because the size cohort disagreed — 85 guard-clean big prints
leaned 0.593 BUY under the sell aggregate with a bid-leaning book — and because the burn gate
contradicted a full down band (CDD warming into Thursday, burn ramping, wind low, nuclear +1.1 GW
w/w). Hence −350, priced *above* the authority-discounted −450..−780 trend band.
**MERGE BEHAVIOR (the point of the forward test).** The HDD bars (16.4, 13.5) were marked
UNEVALUABLE by the new play — **the bearish lean stands on tape/storage/positioning evidence, not on
a silently-defaulted selector.** That is the merged play working exactly as written.
**DECLARED.** No consensus was knowable at the open (the pre-print snapshot is blank), so no play
consumed it; no D-1 last-hour price/flow decomposition served (the R1 family unevaluable blind);
big-print history too short to execute the arm's 2-of-5 count as written.

### 0708 · C · +250 (actual −520, err 770 — WRONG) — *and the alternative branch was right*
**ACTION.** +250 with a stated **35–40% alternative branch: a 0608-class program inversion netting
−300..−500.** The actual, −520, landed in that alternative.
**REASONING.** A basing-to-turn sequence: 0702's print flushed and reclaimed, 0703 thin holiday
drift, Monday's sell tape absorbed by big prints at 0.593/0.641, then Tuesday an outright organic
buy tape (+1,748, all three phases positive and *building*: +391/+604/+753 on 50k trades) — and C
verified that tilt was program-clean by checking 0707 sat outside the roll window. Confirmation:
burn 44.9 Bcf/d at/above the G22 block max with wind falling; positioning washed out and covering.
**The cap:** C's own day is GSCI roll day 1, so `resting_program_inverts_aggressor_tilt` fired as a
**governor** — the program rests offers in the scored leg all session and big-print instruments lose
authority on the day's own tape. C argued the distinction rather than pattern-matching: it damps and
caps rather than flips, because 0608's chain context was the opposite (crowd buying into a live
down-bleed vs today's based/turned tape). `price_free_absorption_proxy` came back inconclusive
(0.535 < the 0.547 bar), so the turn was taken small.
**DECLARED.** 10 defects including the post-print consensus freeze (used at reduced weight), the
missing `wind_chg_7d` (the wind limb evaluated off levels across Sat/Sun/Mon — partly mechanical,
flagged for the feed), and a truncated 3-session tape window against an arm needing 5.

### 0709 · D · −250 (actual −2,050, err 1,800 — direction right, magnitude 8×) — **the block's largest miss**
**ACTION.** −250 net, band −650..+250, travel ~1,100, confidence 0.55.
**REASONING.** The flow chain flipped hard to sell the day before the print: Mon −632 mixed, Tue
+1,748 coherent buy, Wed **−2,336 coherent sell** (big prints 0.38 on n=96) — with three named
drivers, two of which persist into the print day: the July STEO knowable 0708 (production up,
consumption/power burn revised down ~1 Bcf/d), GSCI roll day 1 on the scored leg, and a ~1.5 gw-CDD
cooling of the Jul 11–13 window. Counterweights: D0/D+1 heat added overnight, 45.3 Bcf/d burn, ICE
LD1 MM at its **0.94th** percentile. The over-extension gate ran honestly and did NOT fire (flows
alternate, so no $900 same-side run), which permits a chain-sided down sign — but the swing was one
session old in a summer tape, so the winter band was withheld and the day was scenario-weighted
(loose print −450..−700 / in-band grind ~−250 / tight-print counter-pop).
**MERGE BEHAVIOR.** D applied its own newly-merged `eia_window_reopen_to_print` and put the catalyst
up-size on **RANGE, not NET** — which is precisely why the net came out small. The refine's named
target is whether a −2,050-class day was derivable at decision time at all.
**DECLARED.** The consensus headline 49.0 is a post-print capture; the only strictly-pre-print entry
carries a **null value**. D used **no point consensus** — a reconstructed 49–60 band, mid ~54.5,
cross-checked against `house_disagreement_bcf` = 11.0 (vs 0.0 the prior week), with that elevated
dispersion load-bearing in the band width.

### 0710 · E · −150 (actual −660, err 510 — direction right, 4× light)
**ACTION.** −150, band [−450,+250], low confidence; the mandatory 9-field handoff emitted.
**REASONING.** The turn/exhaustion gate ran FIRST and returned CLEAN (aggressor flow alternated sign
all five sessions; COT 44th pctile improving; nothing stretched) — so continuation had to come from
state, not chain. The D-1 aggregate +1,551 buy is **program-suspect** (0709 was GSCI d2/BCOM d1;
`resting_program_inverts_aggressor_tilt` fired; big prints 0.454 sell; resting book ask-leaned) →
decontaminated residual flat-to-sell. The weekend bag prices a knowable **−2.6 gw-CDD LEVEL cut**
Fri→Mon by the seam level rule, and the week's five-run heat-add engine had decayed to +0.02 at E's
vintage. Roll sign authority is refuted doctrine — the roll capped, it never signed.
**THE SUPPRESSION THAT IS NOW TESTABLE.** The burn gate **suppressed E's down-lean to a −150..−200
floor class** because burn was ramping against it (+83k MWh 7d; ngwu power +6.3 WoW). Actual −660.
That is the gate capping a correct read, and it is a named refine target.
**Also:** `carry_realization_flip`'s REALIZING arm stood down per the merged scope split — the heat
is a priced ladder slope, hill grammar — **explicitly not repeating the G22 0703 miss class.**
**DECLARED.** The 0709 "+12 bearish surprise" rests on a post-print-frozen TE 49 against
investing.com's 60 (possibly +1 in-line), so E used the tape's absorbed-flat verdict instead; the
report-0707 COT publishes 15:30 ET **inside** its own session — an unseeable late catalyst, carried
as tail risk and as a seam confirm/refute limb.

### 0713 · A (bridge) → B (decision) · B +550 (actual −620, err 1,170 — WRONG)
**A's ACTION.** Exit sanity-check PASSES; gap ownership walked four rungs; the two-limb test staged
with pinned baselines. No Monday number (B owns it).
**A's REASONING.** Every load-bearing quantity E cited verified bit-for-bit against A's own 0710
slice. Three flags rather than contradictions: (1) **E's COT re-arm limb is over-armed vs the play's
own trigger** — from 44.34 pctile after two accelerating improving weeks, one print cannot
reconstitute crowding, so a re-worsening print is a +150–300 tail widener, never the G19 +580
quantum; (2) the cooling trough realizes **Sunday**, so Monday is the slope's last session with the
Tue/Wed rebuild ahead — down-Mondays close off the low and nothing past −400 is fundable without a
fresh cut; (3) E's Friday-close refutation limb leans on masked close-location, re-staged for B on
the never-masked (volume, net) pair with residual decontamination. Gap ownership: weather owns on
the **priced-slope** arm; structural, positioning and chain-drift all disarmed on named quantities.
A also caught that the Limb-B burn baseline (0704) is **July-4-soft**, so a burn FAIL would be the
loud outcome.
**B's ACTION.** +550 — an UP flip against E's DOWN-SMALL default.
**B's REASONING (verbatim in substance).** *"E handed DOWN-SMALL conditional on the two-limb flip
test; A staged the limbs with pinned baselines; my slice resolves BOTH limbs PASS — so the sign is
UP by E's own verdict table, not by my override."* Limb A was not marginal: the weekend cycles added
**+1.84/+1.97/+3.25 gw-CDD** at 0713/0714/0715 against the frozen Friday vintage (bar ~+1.0, noise
~1.7) — a coherent repricing that replaces the carried cooling-slope story outright, with the new
peak (16.312, Wednesday) sitting **ahead** of the day. Limb B confirmed transmission: Sat 0711 burn
43.5 vs the holiday-soft 42.9, wind down 11%, solar down w/w. The catch-up window ratifies rather
than fades because the driver is ahead. The served 0710 exit corroborated: a buy handover on
session-max volume (+2,019 on 66,880) with guard-clean buy-tilted big prints (0.541/0.550, n=223)
against a net-sell aggregate on a program day.
**WHY THIS ENTRY MATTERS MOST.** The chain worked exactly as designed — E specified a falsifiable
test, A staged it with pinned baselines and caught a soft baseline, B resolved both limbs honestly
and followed the verdict table rather than its own prior. **Both limbs passed and the market fell
−620.** That is the cleanest possible forward test of the S110 merge, and it is the refine's central
question.
**DECLARED.** B declared exactly what its `prior_full_session` served rather than assuming; the
cycle-store `cdd_basis` and the ladder graft honored as declared repairs.

### 0714 · C · +280 (actual +200, err 80 — right)
**ACTION.** +280, band [−350,+700]; curve: quiet reopen, +60–75 by 06:00, morning softness to +30
by 10:00 (the down-risk window), then 12:00–17:00 delivery as the roll completes post-settle.
**REASONING.** The D-1 sell tilt (−950, ph3 −1,162) is **program-contaminated**: 0713 was GSCI roll
day 4, the selling concentrated where settle-window roll executions print, big prints were balanced
(0.483) against the negative aggregate, and the week's only heavy sell-flow sessions were exactly
the roll days while pre-roll days had big prints buying (0.641/0.568) — decontaminated tilt ≈
neutral. Against that: the Monday-evening model batch, **arriving during the session window**,
extended the heat shot through 0717 (+1.2/+1.6/+1.6 gw-CDD at D1–D3, peak 17.55 tomorrow) at
horizons whose prior vintage showed cooling; burn confirms (+1.0 Bcf/d Sun-over-Sun, midweek scale
45+); Thursday's print covers the hot week; and the 0709 session absorbed a 12-Bcf bearish surprise
on the week's biggest tape closing NET BUY +1,551. The surplus/backwardation/STEO backdrop plus the
post-0717 cooling caps it at +280 rather than the G22 +410..+800 delivered band.
**DECLARED.** `residual_tilt_field` run in **declared PROXY form** — the cohort-decomposition field
the play wants does not exist yet; Friday 0710's session tape is absent from every slice.

### 0715 · C · +300 (actual −60, err 360 — WRONG)
**ACTION.** +300, band [−250,+700]; **the tape deliberately demoted** in favor of the exogenous stack.
**REASONING.** Block-max heat (CDD 18.08) with the overnight runs warming every forward horizon
(+0.5 to +1.7), and the burn residual confirming — 47.2 Bcf/d block max, Monday-over-Monday +2.3,
solar falling; wind rose but **burn rose through it** (damper, not sorter — the G22 caveat applied
correctly). Plus WNGSR balance tightening known since 0709, COT covering three straight weeks, and
the GSCI roll's mechanical front-selling ending with D-1.
**THE COLLISION C DECLARED (a gift to the scoring pass).** D-1 (0714) printed the block's most
coherent buy tape (+3,747 all-phase, big prints 0.553) — but 0714 was GSCI d5 + BCOM d4, so the
program guard **strips that tape's authority**, while `price_free_absorption_proxy`'s precondition
is *fully met* on the same tape (positive flow, 61 guard-clean big prints, 0.553 flip-buy = "absorber
gone"). Two merged plays, one tape, opposite verdicts. C let the **deterministic roll calendar**
select the guard and flagged that G23's scoring adjudicates both falsifiers on this single instance.
**DECLARED.** Friday 0710's tape absent from every slice (Monday slices carry 149/256-trade Sunday
stubs as "prior session") — the 5-session scans run 4-of-5 sighted; next-print consensus null at the
decision point; the LNG vessel line stepped −14% against the thesis and widened the down tail per
its own play text.

### 0716 · D · +300 (actual −20, err 320 — WRONG)
**ACTION.** +300 net, +80 overnight, confidence 0.45 — chain-sided through the print.
**REASONING.** A fresh up-chain born 0714: session signed flow +3,747 then +6,326 (the block's two
largest), big prints agreeing (0.559/0.560 two-sided), final phases strongest — a coherent,
accelerating buy tape into the print. The driver measurable: models added near-term heat two runs
running (Jul-16 target CDD 13.8 → 15.4 → 16.7; D0 peaked 18.1 on 0715), burn-confirmed at 48.8
Bcf/d and rising with solar falling. The physically-implied print reads TIGHT — ngwu (knowable 0710)
shows the print week's power burn +6.3 Bcf/d WoW and supply −1.1 — so a small injection well under
the 5-year class. D's over-extension gate did NOT fire (~1 of 3), so **per its own dominant-flaw
rule the chain-sided band is earned**, trimmed at the top; the loose-print branch (27% weight) was
bounded by S1-void counter-print damping.
**DECLARED.** The consensus survey store is **dead** for this print — `next_print` null on every row
since 0710, and even the 0709 print had no strictly-pre-print number. D forecast **without the
consensus channel** and refused a 0721-stamped "45B for Jul 16" capture as not decision-legit. It
also cross-checked that the TE-vs-investing gap (49 vs 60) equals `house_disagreement_bcf` = 11
exactly, so the 0709 "+12 surprise" was house-dependent and near-in-line on the other house.

### 0717 · E · +180 (actual +180, err 0 — exact)
**ACTION.** +180, band [−250,+600], trend-then-fade; onset 08:30, crest ~12:30, afternoon trim.
**REASONING.** Direction with the D-1 tilt: session 0716 (program-free, leg-true after the f1
repair) net +1,089 on 100k lots, phases [−101, −2,776, **+3,966**] — the bearish print (+41 build,
+5.4 above proxy) was sold for one phase and **bought back bigger in the final phase**, the block's
strongest ph3 on 27.6k lots: a signed high-volume handover, not a flowless close. The mandatory
Friday turn/exhaustion gate ran CLEAN (chain age 3 below the ≥4 bar; COT mid-book improving; D-1
flow aligned; no give-back). The crest-trim counter-fade STOOD DOWN because the weekend driver is
unrealized-and-building (Sat CDD revised +2.256 overnight) — the never-against-a-live-building-
catalyst condition binds. Burn gate applied **both ways**: the CDD-add and burn limbs pass (51.0
Bcf/d, Wed/Wed +5.6, wind low) so the up-lean keeps its band, **and** the far-week CDD collapse
(15.3 → 9.8 by 0723) is NOT converted into a session down-call because burn ramps against it.
`expiry_day_extension` CHECKED and correctly **not met** (GSCI d1–5 and BCOM both complete) — but
its consequence guard still flagged the week-2 buy tilts (+3,747/+6,326) as program-suspect, resting
chain authority on the program-free 0716 confirm.
**HANDOFF.** exit_type `crest_trim_fadeable`, monday_bias `down_mild`, with the two-limb flip
specified numerically (Monday CDD ≥ ~14.0 **and** burn ≥ ~49 Bcf/d Sat-over-Sat, wind not ramping).
**CROSS-CUTTING (E's own framing).** *The program-tilt-then-clean-confirm ordering* — two roll-window
buy sessions followed by a program-free session that still printed the block's strongest final-phase
buy through a bearish print — **the roll windows inflate the aggregate tilt, and the first
post-program session is the tape that actually adjudicates the chain.**
**DECLARED.** The 0716 b_share family is NULLED by the f1 repair — E reasoned only from recovered
signed flow, phase volumes and leg-true counts; GFS stability ladder null beyond h0 (null, not zero);
and session 0710's tape appears under **no day key** in the slice.

---

## PART 2 — WHAT THE BLOCK SAYS, BEFORE THE REFINE ADJUDICATES

**Four specialists independently flagged the same structural hole:** session 0710's tape is absent
from every slice (Monday keys carry Sunday stubs). Four sightings, one defect — recorded here as the
refine's docket item, not as four separate observations.

**The merged plays behaved as written, and that is what makes the result usable.** The HDD-bar play
prevented silent bearish defaults (0707, 0714, 0715). The program guard damped or stripped
contaminated tilts on four separate days and C argued the 0608 context distinction rather than
pattern-matching. The window play put catalyst size on range rather than net. The scope split kept
`carry_realization_flip` off a priced slope — explicitly not repeating G22's 0703 error. **None of
these failed as instruments. The block still fell while the panel leaned up.**

**The sharpest single fact for the refine:** on 0713 the chain executed flawlessly — E specified a
falsifiable two-limb test, A staged it with pinned baselines and caught that one baseline was
holiday-soft, B resolved both limbs honestly and deferred to the verdict table over its own prior —
**both limbs passed and the market fell −620.** Combined with 0710, where the same gate *capped a
correct down-read* to a −150 floor against a −660 actual, the burn-conversion gate now has a
two-sided forward record on its first outing, and its own falsifier is the thing to test.

---
