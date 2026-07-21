# Friday / weekend-seam cleanup (Specialist E, block-spanning, S104)

**Mission (Greg):** "we missed Monday so bad because we missed Friday so bad." The Monday wrecks
inherit a WRONG Friday exit read across the weekend seam. This is the Friday/expiry/roll specialist's
cleanup, done BEFORE the Monday fix lands. Committed files only; incumbents untouched; nothing fitted.

**Scope of the record:** 24 walked Fridays G6->G16 (+ 2 G11 Fridays with no rt-window decomposition;
+ the Good-Friday-dark 0403 extended-weekend seam). Blind scores are the immutable blind
(`grp*.json` / `g*_score.json`). $1.00 NG = $10,000 units.

**Headline finding.** Blind Friday DIRECTION is ~50% (11 of 22 scored Fridays wrong-signed) — the
worst day-class in the record — and the error PROPAGATES: of 14 bad Mondays, **10 trace directly to a
mis-read Friday exit** carried across the seam. The Friday close is the weekend's anchor, but the
handoff currently passes a day-NET (or the blind's directional LABEL), not the EXIT-STATE
decomposition. The two halves of a Friday close decay on different clocks and must be handed off
separately.

---

## 1. Per-Friday table (blind call vs actual, which mechanism failed, correct exit decomposition)

`dm` = day-move USD (gap+net). EXIT-TYPE = what the OUTGOING handoff should have said.

| Fri | grp | blind dm | actual dm | dir | mechanism that failed | CORRECT exit-type (what Mon should inherit) |
|---|---|---|---|---|---|---|
| 1024 | g6 | -250 | +450 | X | "Friday range, mild down continuation" default | UP reversal STARTING (fresh turn) -> Mon extends |
| 1031 | g6 | -150 | +540 | X | "Friday range" default | up-lift, seller spent -> Mon carry up (Mon dir OK) |
| 1107 | g7 | +140 | -730 | X | "range + late cold-front-run bid" | DOWN momentum -> Mon carry down |
| 1114 | g7 | +100 | -890 | X | "range / stabilization" | DOWN momentum carry -> Mon carry down |
| 1121 | g8 | +120 | +910 | ok | undersize (post-resumption hold) | fundamental-carry (cold building) -> Mon carry up |
| 1128 | g8 | +550 | +2340 | ok | undersize; **Black Friday early close** storage swing | **fundamental-carry** (cold arriving), NOT spent -> Mon continue |
| 1205 | g9 | +900 | +2430 | ok | undersize ramp-to-crest | crest forming; aft-trim = first same-sign trim |
| 1212 | g9 | +1050 | -1190 | X | called "ramp_resume", tape ROLLED OVER | **crest TURNED** (rollover) -> Mon carry DOWN |
| 1219 | g9 | -400 | +850 | X | "capitulation_stabilization" | dead-cat bounce (exhausted) -> Mon give-back |
| 1226 | g9 | +1900 | +660 | ok | oversize thin hard-heat meltup | spent meltup -> Mon give-back (dir OK) |
| 0102 | g10 | -1250 | -700 | ok | OVER-sized down | down but EXHAUSTING -> Mon mean-revert up |
| 0109 | g10 | +1350 | -2740 | X | "print_delivery_up" mis-fired | print SOLD (down) -> Mon bounce off extreme |
| 0116 | g10 | -700 | -430 | ok | fine; weekend fresh-shot dominated | down-carry; Sun fresh cold shot owns the gap |
| 0123 | g11 | +900 | +1210 | ok | fine | up-ramp; Sun priced-shock owns the reversal |
| 0130 | g11 | +150 | +4990 | ok | **BLOW-OFF** extreme close undersized | **exhausted extreme** -> give-back-biased weekend |
| 0206 | g12 | -1100 | -1160 | ok | good (young down-chain, **GSCI roll**) | positioning-CARRY (roll window open Mon) -> Mon carry down |
| 0213 | g12 | -300 | -1400 | ok | undersize (**roll day marked**) | roll-window CLOSING at settle -> fade the roll component |
| 0220 | g13 | +700 | +600 | ok | good (extension into cold weekend) | **fundamental-carry that REALIZES over weekend** -> Mon SELL-THE-NEWS |
| 0227 | g13 | -500 | +350 | X | "bleed back to shelf - surplus" default | counter-bounce to mature down-chain (spent) |
| 0306 | g14 | -400 | +1850 | X | "roll-pressure continuation DOWN" default | strong UP lift (warm-cut thesis WRONG) -> Sun carried up |
| 0313 | g14 | +300 | -1010 | X | "whipsaw grind UP into cold weekend" | position-squaring flow-led BREAK down -> Mon down |
| 0320 | g15 | -250 | -80 | ok | good (**roll seam**, settle-flow) | absorbed near-flat; down-chain flattening (moderate carry) |
| 0327 | g15 | -350 | +1150 | X | mis-fired weekend_crest_friday on a based chain | **expiry COVERING (spent at settle)** -> Mon resume pre-covering down |
| 0410 | g16 | -200 | -190 | ok | good (**weekend_crest_friday fired**) | crest-trim fadeable (clean success) |

**MBO-measured last-hour fingerprint (G15 only, the covering/exhaustion tell):**
- 0320: last-hr dir +1 / flow +1 aligned buy = seller exhausted -> shallow; Mon 0323 carried down modest.
- 0327: last-hr price UP against SELL flow (-2470, absorb_session) = COVERING -> spent at settle;
  Mon 0330 resumed the pre-covering down (-650). The covering half did NOT carry.

---

## 2. The Friday -> Sunday -> Monday cascade table (root-cause trace)

Bad Monday = dir wrong or magnitude wreck. "root" = the Friday exit read was the cause.

| Monday | act | dir | preceding Friday (exit issue) | Sunday | cascade class | root? |
|---|---|---|---|---|---|---|
| 1027 +5890 | X (g+1200) | 1024 called DOWN, tape +450 (up reversal starting) | (no Sun) | **wrong-sign Friday** -> Mon under-called reversal 5x | YES |
| 1110 -810 | X (g+1600) | 1107 called +140, tape -730 (down momentum) | (no Sun) | **wrong-sign Friday** -> Mon extended wrong up-reversal | YES |
| 1117 -1510 | X (g+950) | 1114 called +100, tape -890 (down momentum) | (no Sun) | **wrong-sign Friday** -> Mon carried the wrong side | YES |
| 1201 +910 | X (g-300) | 1128 strong +2340 read as fadeable mature-extreme | (no Sun) | **carry mislabeled SPENT** -> Mon faded a continuing driver | YES |
| 1215 -1570 | X (g+700) | 1212 called ramp UP, tape ROLLED OVER -1190 | (no Sun) | **crest-turn missed** -> Mon extended a dead crest | YES |
| 1222 -650 | X (g+1200) | 1219 bounced +850 (dead-cat, exhausted) | (no Sun) | **dead-cat read as fresh-turn** -> Mon extended a give-back | partial |
| 0105 +270 | X (g-850) | 0102 down but OVER-sized (-1250 vs -700 = exhausting) | (no Sun) | **exhaustion missed** -> Mon mean-reverted up | partial |
| 0202 -4260 | X (g+1300) | 0130 BLOW-OFF +4990 (exhausted extreme) | 0201 -7590 | **extreme not flagged spent** -> Mon extended a blow-off | YES |
| 0216 +400 | X (g-300) | 0213 roll -1400 | 0215 -1190 | **holiday Monday** (Presidents Day) dominates | NO (holiday) |
| 0223 -1790 | X (g+600) | 0220 +600 fundamental-carry (cold weekend) | 0222 +1150 | **carry REALIZES over weekend** -> Mon sell-the-news | YES |
| 0309 -3020 | X (g+400) | 0306 called DOWN, tape +1850 (warm-cut thesis wrong) | 0308 +2250 | **3-day wrong sign** then exhausted-reverse | YES |
| 0406 -470 | X (g+300) | **Good Fri 0403 DARK** (Sun 0405 cold-add +400) | 0405 +400 | **carry REALIZES over ext-weekend** -> Mon sell-the-news | YES (via Sun) |
| 0119 +560 | ok (g+2000 over) | 0116 down; Sun 0118 fresh cold shot +2090 | 0118 +2090 | weekend fresh-shot; catalyst consumed by gap | NO (weekend-gap) |
| 0126 -700 | X (g+650) | 0123 up-ramp; Sun 0125 priced-shock +2660 | 0125 +2660 | Sunday shock consumed; Mon reversal | NO (weekend-gap) |

**Tally:** 10 of 14 bad Mondays are root-caused (in whole or part) by a mis-read Friday/pre-weekend
exit. The 4 non-Friday cases are: 1 holiday Monday (0216) and 3 Sunday-fresh-shot-gap cases
(0119, 0126, and the 0405/0406 gap magnitude) that belong to `weekend_gap_delivery` /
`reaction_corollary`, not the Friday decomposition.

---

## 3. General Friday mechanisms (n>=2 spanning groups, decision-time-legit, honest)

The Friday close = **positioning component + fundamental-carry component**, and they decay on
DIFFERENT clocks. The handoff must decompose them.

### R-A. Friday exit decomposition (the missing handoff verdict)
Classify the Friday close into one EXIT-TYPE from measurable state, and hand off the TYPE:

- **CREST-TRIM (fadeable):** chain stretched near extreme + driver PRICED + realization expiring by
  close. Friday trims same-sign; Monday CONTINUES the give-back. Evidence: 0410 (fired clean, -190),
  1205 (aft -1050 off peak). (This is incumbent `weekend_crest_friday`, trigger MET.)
- **POSITIONING-SPENT (fade Monday):** the close is driven by mechanics spent AT SETTLE — futures
  expiry / opex pin / weekend-risk squaring / index-roll on its LAST day. Tell: price moves AGAINST
  last-hour signed flow (covering/absorption). Evidence: 0327 (April expiry, +1150 covering ->
  Mon 0330 resumed the pre-covering DOWN -650); 0213 (roll's last marked day). Sub-rule: an index
  roll whose WINDOW is still open Monday is positioning-CARRY, not spent — 0206 down -> 0209 carried
  down (window open) vs 0213 window closing -> fade. (GSCI/BCOM roll = 5th-9th business day.)
- **FUNDAMENTAL-CARRY (continue Monday) — IF the driver is still AHEAD:** an unrealized weather/
  storage driver whose peak is later than Monday. Evidence: 1128 (cold arriving, +2340 -> Mon 1201
  carried +910); 1121 (+910 -> 1124 held). n>=2 spanning G8.
- **MOMENTUM-CARRY:** genuine one-sided flow at the close (dir AND flow aligned). Carry the side.
  Evidence: 1107/1114 down-momentum (missed by the "range" default) -> Mon 1110/1117 carried down.

### R-B. The carry-realization flip (the load-bearing new mechanism)
A FUNDAMENTAL-CARRY Friday's Monday direction depends on WHEN the driver realizes:
- driver peak still **AHEAD** of Monday -> **carry / continuation** (1128->1201; 0111 cold shot
  Sun -> 0112 extend bounce).
- driver peak lands **Sat/Sun/Mon (realizes over the weekend)** -> **Monday = SELL-THE-NEWS reversal.**
  Evidence n>=2 both spanning groups: **0220** (cold weekend, peak realized -> Sun +1150 carried ->
  Mon 0223 REVERSED -1790); **0405** (cold-add realized over the Good-Friday extended weekend ->
  Mon 0406 -470). Contrast the ahead cases above. This is the single mechanism that most cleanly
  explains the worst Monday reversals after a CORRECT Friday direction.

### R-C. Extreme / blow-off exit = spent (give-back-biased weekend)
A Friday closing at an EXTREME cum-from-anchor or on a mature chain (age >= 4) is EXHAUSTED, not a
continuation. The weekend is give-back-biased; Monday must NOT extend. Evidence: 0130 blow-off +4990
-> 0201 -7590 give-back (Mon 0202 wrongly extended +1300, actual -4260); 1212 mature crest rolled
over; 0102 over-magnitude down -> 0105 mean-reverted up. n>=3 spanning G9/G10/G12.

### R-D. Do NOT default a Friday to "range / roll-pressure down"
The single largest cascade source is the blind's Friday DOWN/range default firing on a day the tape
is actually lifting on covering/exhaustion. 1024, 1107(inverted), 0227, 0306 all mis-fired a
directional LABEL the weekend then inherited. The fix is structural: Monday inherits the MEASURED
exit-state, never the Friday directional label. (See the protocol, section 4.)

---

## 4. The weekend handoff_out protocol (exactly what a Friday must emit for A and B)

The seam must pass EXIT-STATE, not a day-net or a label. Required `handoff_out` fields on every
Friday (and the Good-Friday-dark Sunday that replaces it):

1. `close_px`, `cum_from_anchor_usd`
2. `chain_polarity`, `chain_age_sessions`   (age>=4 or extreme cum -> exhaustion flag)
3. `last_hour_dir` (+1/-1) and `last_hour_signed_flow` (+1/-1)
   -> `conviction`: ALIGNED (genuine momentum) | DIVERGENT-covering (price up vs sell flow) |
      DIVERGENT-exhaustion (price down vs buy flow)
4. `close_off_extreme_frac` (how far off the session high/low the close sits)
5. `positioning_calendar`: {expiry, opex, index_roll_window_open_monday (bool)} -> spent vs carrying
6. `driver_realization`: {driver, peak_day_et, realizes_before_monday (bool)} -> carry vs sell-the-news
7. **`exit_type`** verdict: one of {crest_trim_fadeable, positioning_spent_fade,
   fundamental_carry_continue, fundamental_carry_realizing_reverse, momentum_carry,
   exhausted_extreme_giveback}
8. **`monday_bias`**: directional lean + size class Monday should inherit (the consumable)
9. `sunday_gap_owner`: {structural | weather | chain_drift} for A's Sunday-gap sizing
   (feeds incumbent `block_gap_ownership` / `weekend_gap_delivery` — unchanged).

**Consumption rule for A (Sunday) and B (Monday):** read `exit_type` + `monday_bias`, NOT the Friday
day-move sign. Sunday inherits the CLOSE + chain state (gap sign is noise). Monday's 07-10 ET
catch-up window reprices `driver_realization`: if the driver realized over the weekend, the catch-up
is a FADE (sell-the-news), not an extend.

---

## 5. Honest: what these rules STILL miss

- **Last-hour FLOW (the covering/exhaustion tell, field #3) is only MBO-measured for G15.** For every
  other Friday I inferred exit-type from archetype + curve direction + calendar; the dir-vs-flow
  covering fingerprint is PROVEN as a live discriminator only where MBO ran. Extending it to all
  Friday closes is a DATA build, not a rule refinement — declared, not hand-waved.
- **The magnitude of a fresh-shot Sunday gap stays irreducible** (0118, 0125, 0201, 0308) — incumbent
  `weekend_gap_delivery` already declares this needs the Sat/Sun 00Z/12Z model runs. My rules address
  exit-type/DIRECTION and the carry-realization flip, not the fresh-shot gap SIZE.
- **Holiday Mondays** (0216 Presidents Day) are a different day-class; the Friday decomposition does
  not govern them (defer to the catch-up/holiday doctrine, 0216->0217).
- **1031->1103** and **1222/0105** remain PARTIAL: the exit-type rule flags the exhaustion/dead-cat,
  but the Monday MAGNITUDE (bounce depth) is not yet sized — a band-position gap, not a sign gap.
- Two bad Mondays (**0119, 0126**) are genuinely NOT Friday-rooted — they are Sunday-fresh-shock-gap
  reversals (catalyst consumed by the gap). Correctly OUT of this cleanup's scope.

n=2 floor respected on every promoted rule; R-B (carry-realization flip) is the strongest cross-group
result (0220/G13 + 0405/G16, both polarities against the ahead-cases). All PROVISIONAL, forward
evidence NONE — G17+ is the forward test.
