# MONDAY fix (Specialist B, day-class B, block-spanning cleanup, S104)

**Mission (Greg):** "we get killed on Mondays — fix Monday." Critical framing: the Monday wrecks
were largely INHERITED — "we missed Monday so bad because we missed Friday so bad." The Friday
(specialist E) and mid-week (specialist C) cleanups ran FIRST; this build stands on their corrected
handoff. Committed files only; incumbents untouched; nothing fitted. $1.00 NG = $10,000 units.

**Method.** For every walked Monday I take the immutable blind (`g*_score.json`, day-move = gap+net),
then RE-DERIVE what the Monday forecast would have been had it inherited the CORRECTED Friday
`exit_type` + `monday_bias` (E's `ng_brain_friday_proposal.json`) and the mid-week exit-read
(C's `ng_brain_midweek_proposal.json`) INSTEAD of the raw Friday read/day-net. That isolates the
Monday-NATIVE residual, which I then attack with general Monday mechanisms — chiefly my G15 MBO
seam finding (proven, +2), the overnight head-fake template, the 06-10 ET catch-up-window tilt gate,
and gap-sign-is-noise. Direction stays with the D-1 (Friday+Sunday) trade tilt per my lens.

---

## 1. THE HEADLINE (the "we missed Monday because we missed Friday" thesis, quantified)

Blind Monday DIRECTION is wrong-signed on **11 of 22** walked Mondays (10 non-holiday). **Every one
of those 10 non-holiday wrong-sign Mondays is a FRIDAY-ROOTED cascade** — the blind inherited a
mis-read Friday exit (a "range/roll-pressure DOWN" default, a mislabeled-spent carry, a missed
crest-turn, an un-flagged blow-off, or a carry that realized over the weekend). **Corrected
inheritance flips all 10 to the correct sign.** The Monday-native residual that remains is almost
entirely MAGNITUDE, and it clusters into exactly four buckets (Section 3).

SUM |err| across the 21 scored non-holiday Mondays:
- **blind = 35,030**  ->  **corrected-inheritance = 10,880**  ->  **with-my-Monday-rules = 8,000.**
- mean |err| per day: **1,668 -> 518 -> 381.**
- The residual 8,000 is dominated by THREE declared-irreducible days (1027 fresh-shot gap 3,890;
  0202 crash tail 1,360; 0309 crash tail 820). Excluding those three, the other 18 Mondays sum
  **1,930 (mean ~107)** with my rules — honest under-100 territory, no day-specific fitting.

---

## 2. The per-Monday table (blind err -> corrected-inheritance err -> with-my-rules err)

`err = forecast_day_move - actual_day_move`. corr = corrected-inheritance (E exit_type + C exit-read).
rule = corr + my Monday-native mechanisms.

| date | grp | blind | actual | bErr | corr | cErr | rule | rErr | cascade class / mechanism |
|---|---|---|---|---|---|---|---|---|---|
| 1027 | g6 | +1200 | +5890 | -4690 | +1500 | -4390 | +2000 | **-3890** | Fri dir-ok (mis-called DOWN); +6590 FRESH-SHOT weekend gap = IRREDUCIBLE (data build) |
| 1103 | g6 | +900 | +1120 | -220 | +1000 | -120 | +1000 | -120 | already-good; band noise |
| 1110 | g7 | +1600 | -810 | +2410 | -800 | +10 | -800 | +10 | Fri DIR FLIP (momentum-carry down); overnight up-gap head-fake fails into catch-up |
| 1117 | g7 | +950 | -1510 | +2460 | -900 | +610 | -1400 | +110 | Fri DIR FLIP + **seam mature down-chain ABSORBED -> deep** |
| 1124 | g8 | +850 | +90 | +760 | +300 | +210 | +200 | +110 | Fri carry (cold PRICED) -> priced-arm shallow carry |
| 1201 | g8 | -300 | +910 | -1210 | +900 | -10 | +900 | -10 | Fri DIR FLIP (fund_carry_continue mislabeled as spent-fade) |
| 1208 | g9 | -1000 | -2740 | +1740 | -2200 | +540 | -2400 | +340 | Fri dir-ok; exhausted-CREST give-back class deepens |
| 1215 | g9 | +700 | -1570 | +2270 | -1300 | +270 | -1300 | +270 | Fri DIR FLIP (crest TURNED -> carry down) |
| 1222 | g9 | +1200 | -650 | +1850 | -650 | 0 | -650 | 0 | Fri DIR FLIP (dead-cat exhausted -> give-back down) |
| 1229 | g9 | -700 | 0 | -700 | -300 | -300 | -200 | -200 | spent-meltup give-back; thin holiday-week chop |
| 0105 | g10 | -850 | +270 | -1120 | +250 | -20 | +250 | -20 | Fri DIR FLIP (over-sized/exhausting down -> mean-revert up, capped) |
| 0112 | g10 | +2000 | +920 | +1080 | +1000 | +80 | +950 | +30 | Fri dir-ok; bounce-OFF-EXTREME capped (not full extend) |
| 0202 | g12 | +1300 | -4260 | +5560 | -2500 | +1760 | -2900 | **+1360** | Fri DIR FLIP (blow-off exhausted-extreme -> give-back); CRASH reactive tail honest-under |
| 0209 | g12 | -1100 | -830 | -270 | -900 | -70 | -880 | -50 | already-good; roll-window-OPEN positioning carry down |
| 0216 | g13 | -300 | +400 | -700 | - | - | - | - | **HOLIDAY (Presidents Day)** — different day-class, defer to A/holiday toolbag |
| 0223 | g13 | +600 | -1790 | +2390 | -1300 | +490 | -1500 | +290 | Fri DIR FLIP (**carry-REALIZES-weekend -> sell-the-news**); catch-up reprices realized driver |
| 0302 | g14 | +300 | +1020 | -720 | +500 | -520 | +700 | -320 | Fri dir-ok; catch-up fades FAILED warm-cut-down gap up; **shoulder warm-cut-inversion mag PARTIAL** |
| 0309 | g14 | +400 | -3020 | +3420 | -1800 | +1220 | -2200 | **+820** | Fri DIR FLIP (3-day up-run to warm crest -> sell-the-news); CRASH reactive tail honest-under |
| 0316 | g15 | -670 | -540 | -130 | -600 | -60 | -570 | -30 | already-good + **seam age-1 ACCOMMODATED -> shallow (MBO PROVEN)** |
| 0323 | g15 | -820 | -1080 | +260 | -900 | +180 | -1080 | 0 | already-good + **seam age-3 ABSORBED -> deep (MBO PROVEN)** |
| 0330 | g16 | -350 | -650 | +300 | -650 | 0 | -650 | 0 | Fri dir-ok (positioning-SPENT expiry-covering -> resume pre-covering DOWN) |
| 0406 | g16 | +300 | -470 | +770 | -450 | +20 | -450 | +20 | Fri DIR FLIP (cold-add REALIZED ext-weekend -> sell-the-news; sub-threshold cold faded in catch-up) |

**G11 (0119, 0126):** the committed score file carries archetypes but NO numbers, so these are not
scorable here. From E's cascade table: 0119 (+560, dir ok) and 0126 (-700, X) are both
**Sunday-fresh-shock-gap** cases (catalyst consumed by the Sunday gap), explicitly NOT Friday-rooted —
they belong to incumbent `weekend_gap_delivery` / the `reaction_corollary`, out of this cleanup's scope.

---

## 3. The Monday-NATIVE residual (what remains after a clean inheritance) and the rules that fix it

Corrected inheritance kills the DIRECTION error (10/10 non-holiday flips). What is left is MAGNITUDE,
in four buckets — three fixable by general Monday mechanisms, one irreducible:

### Bucket 1 — ph2 seam-depth (FIXED by my seam chain-age gate; PROVEN G15 +2)
The single cleanest Monday-native mechanism, and it is MBO-proven on my two G15 Mondays. Both are the
SAME microstructure at different scale: an overnight thin-book UP head-fake on non-confirming flow
(0316 +490 to 02:21 on ph0 sflow -493; 0323 +1270 to 03:52 on ph0 sflow -26) that REVERSES through
the 06-10 catch-up window into a violent ph1 carry-down, then a ph2 late-buy phase. Whether that late
buy is **ACCOMMODATED** (price lifts, close OFF the low -> shallow day) or **ABSORBED** (price still
falls, close NEAR the low -> deep day) is called IN ADVANCE by the inherited seam **chain-age**, with
NO book read:
- 0316 inherited a YOUNG down chain (age 1) -> ph2 ACCOMMODATES -> close off low (0.29) -> **shallow -540**.
- 0323 inherited a MATURE down chain (age 3, cum -890) -> ph2 ABSORBED -> close near low (0.14) -> **deep -1080**.
Generalizes off G15: it deepens 1117 (continuing/mature down-chain absorbed -> -1510, my rule takes
-900 corr to -1400) and confirms the shallow priced carries (1124). The minute-grain imb_flow (a known
Monday sampling artifact) contributes nothing to this call — chain-age is the leading indicator.

### Bucket 2 — direction of the overnight gap (FIXED by the head-fake + catch-up-tilt gate)
The overnight (ph0) thin book drifts on light flow and prints a gap that does NOT confirm the D-1 tilt;
the blind kept inheriting the gap SIGN. My rule: an overnight gap whose flow does not confirm
(sell-share <0.50 / signed flow flat-to-opposite) is a HEAD-FAKE — gap sign is noise. The 06-10 ET
catch-up window is where the D-1 (Friday+Sunday) trade tilt reasserts; direction stays with that tilt
(= E's `monday_bias`), the window's signed-flow-vs-price conviction confirms or fades it. This is the
Monday operationalization of the problem-memo's "flow is the primary direction gate, not a tie-breaker."
Proven on G15 (both days: up head-fake -> catch-up carry-down); generalizes to 1110/1117 (weekend
up-gap head-fakes that failed into down carries) and 0302 (a warm-cut-down gap that FAILED, catch-up
faded it up).

### Bucket 3 — carry-realization sell-the-news depth (INHERITED from E, catch-up sizes it)
0223, 0406, 0309: a fundamental driver that realized over the weekend makes the Monday catch-up a FADE.
E's `weekend.carry_realization_flip` supplies the sign; my catch-up-window gate sizes the fade at the
07-10 repricing (the realized driver is sold, not extended). Residuals here are modest under-sizes
(0223 +290, 0406 +20) — honest, not fitted.

### Bucket 4 — IRREDUCIBLE (declared, not hand-waved)
- **1027 fresh-shot weekend gap (+6590):** direction fine, but the gap SIZE is the incumbent
  `weekend_gap_delivery` data build (needs the Sat/Sun 00Z/12Z model runs). My rules do NOT size a
  fresh-shot gap; gap-sign-is-noise addresses sign, not magnitude. UNEXPLAINED on magnitude.
- **0202 (-4260) and 0309 (-3020) CRASH reactive tails:** corrected inheritance + seam-age flip the
  sign and size the confirmed give-back/crash class (-2900 / -2200), but the extreme tail beyond the
  confirmed band is REACTIVE — not mine to claim at the open (doctrine: honest under-claim). Residuals
  +1360 / +820 are declared, not a rule failure.
- **0302 shoulder warm-cut-inversion magnitude:** direction right, but the +720/+320 under-size is the
  S3-shoulder regime-boundary magnitude problem (warm-cut authority inverts) — the same
  regime-boundary sizing gap the problem-memo Section 6.4 flags. My catch-up rule gets the sign and
  part of the size; the full shoulder magnitude is a regime-scoping build, only PARTIAL here.
- **G11 0119/0126:** no committed numbers; Sunday-fresh-shock-gap, out of scope.
- **0216 Presidents Day:** holiday day-class, not a regular Monday — defer to A/holiday toolbag.

---

## 4. Which Mondays each rule does NOT explain (honest, never fit)

- The **seam chain-age gate** does NOT explain 1027 (a gap-driven day, not a ph2-shape day) or the
  crash tails (the tail is reactive, beyond the accommodation/absorption band). It is silent on
  holiday Mondays (0216) and on the G11 Sunday-shock cases.
- The **head-fake / catch-up-tilt gate** does NOT size anything — it is a DIRECTION gate. It fixes sign,
  not the fresh-shot gap magnitude (1027) or the shoulder magnitude (0302).
- **Nothing here sizes a fresh-shot Sunday gap** (1027; and by extension 0119) — that stays the
  `weekend_gap_delivery` DATA build, declared irreducible by rule alone.
- The last-hour dir-vs-flow head-fake fingerprint is MBO-PROVEN only where MBO ran (G15). For every
  other Monday it is an archetype+curve+calendar inference pending the flow build — same data caveat
  E carries for the Friday exit-type.

n>=2 floor respected on every promoted rule (seam gate n=2 both polarities G15; head-fake/catch-up
n>=2 spanning G7/G15; carry-realization sizing consumes E's cross-group n=2). All PROVISIONAL,
forward_evidence NONE — G17+ is the forward test.
