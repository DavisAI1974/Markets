# COACH REPLAY S97 - net-of-fee replay of the s99.2 playbook on the walked winter blocks G7-G10

Job 4 of `KICKOFF_2026-07-17_S97.md`. PROVISIONAL UNTIL LIVE: everything below is a backtest, i.e. a
hypothesis, not a fact. Nothing here has traded.

## What was replayed, exactly

The playbook is not replayed from raw plays here - it is replayed AS IT WAS ACTUALLY CALLED. The committed
per-day forecast records (`renders/ng_refine_s95/g{7,8,9,10}_score.json`) are the coach's own output: each
day carries the play/archetype it called and the dollar net it guessed. The replay takes the SIGN of that
guess as the trade side and prices it against the real tape in `g*_rt.json`. That is the honest version of
"did the playbook pay" - it grades the calls that were actually made, at the brain version they were made
on (G7 s95.2, G8 s96.2, G9 s97.2, G10 s98.2; the s99.2 brain is the product of all four refines, so
replaying s99.2 on G7-G10 would be pure in-sample fitting and is deliberately NOT done).

**Vehicle:** 1 NG futures contract ($10,000 per $1.00; tick 0.001 = $10). Canary-side only. The Kalshi echo
is a further layer and is NOT modelled here.

**Trade object (primary cell) - SESSION, settle-excluded:** enter at the session open, exit at the last
2-hour grid mark strictly before the 14:30 ET daily settle (grid index k=10, approximately 14:00 ET). The
standing settle-window exclusion is therefore satisfied structurally - no fill is taken in or after the
settle window. A session never spans a contract roll, so this cell is roll-clean BY CONSTRUCTION.

**Trade object (secondary cell) - OVERNIGHT HOLD:** enter at the prior forecast day's close, carry through
every intervening session (Sundays included), exit at the same settle-excluded mark. This cell DOES span
rolls and is where the roll landmines live.

**Fees, per contract round-trip, both reported:**
- **MAKER $5.00** - commission plus exchange/clearing/NFA only. Assumes a resting limit fills at the entry
  mark and at the exit mark. **Fill risk is real and completely unmodelled** (see Limitations).
- **TAKER $25.00** - the same $5.00 plus crossing a 1-tick ($10) bid/ask on entry AND on exit.

## Roll handling (Guard 3) - the landmines, named

The RT series are REAL prices, not back-adjusted; rolls are recorded in each file.

- **G8: roll 2025-11-23, offset +0.039.** The 1121 Fri close 4.577 -> 1123 Sun open 4.616 gap of **+$390 is
  100% the roll** - a calendar spread, not a move. The forecast record skips Sundays, so the **20251124
  Monday overnight-hold event spans it and is VOIDED**, named, and excluded from every hold figure. Its
  session trade (+$195 taker) is unaffected and stands.
- **G9: roll 2025-12-25, offset -0.504.** The 1224 close 4.249 -> 1225 open 3.745 gap of **-$5,040 is 100%
  the roll** (winter backwardation at the Christmas reopen). This is the single biggest artifact in the
  walk: taken naively, a short carried over Christmas would book a fake +$5,040. The **20251226 Friday
  overnight-hold event spans it and is VOIDED**. Its session trade (+$195 taker) stands.
- **G7 and G10: no rolls detected.** All events clean.

No session-cell P&L anywhere in G7-G10 derives from a cross-roll gap.

---

# PART 1 - BLIND (the only tradeable read)

These are one-shot block-blind calls: the coach saw nothing inside the block. This is the number that
matters.

## G7  Nov 5 - Nov 18 2025 (first winter block) - BLIND on brain s95.2

| date | dow | side | archetype (play called) | gross $ | MAKER net $ | TAKER net $ | dir | overnight-hold MAKER/TAKER $ |
|---|---|---|---|---|---|---|---|---|
| 20251105 | Wed | short | post-run consolidation / early give-back probe | +1030 | +1025 | +1005 | HIT | n/a (first day) |
| 20251106 | Thu | short | storage Thursday - dominant post-print leg, sized up, down side | -850 | -855 | -875 | MISS | -835 / -855 |
| 20251107 | Fri | long | Friday range with a late cold-front-run bid | -580 | -585 | -605 | MISS | -595 / -615 |
| 20251110 | Mon | long | weekend-gap Monday reversal UP + hard_heat shock - compound up-size | -1140 | -1145 | -1165 | MISS | +125 / +105 |
| 20251111 | Tue | long | thin-holiday drift (Veterans Day) - size DOWN | +1870 | +1865 | +1845 | HIT | +1865 / +1845 |
| 20251112 | Wed | short | cold-moderation give-back off the new cum-extreme | -20 | -25 | -45 | MISS | -15 / -35 |
| 20251113 | Thu | short | storage Thursday - dominant post-print leg down, sized up | -900 | -905 | -925 | MISS | -905 / -925 |
| 20251114 | Fri | long | Friday range / stabilization at the mid-block low | -230 | -235 | -255 | MISS | -215 / -235 |
| 20251117 | Mon | long | weekend-gap Monday reversal UP on re-cooling | -1350 | -1355 | -1375 | MISS | -1555 / -1575 |
| 20251118 | Tue | long | Tuesday trend continuation up | +510 | +505 | +485 | HIT | +505 / +485 |

Block footnote (secondary, NOT the finding): 10 events, 3 direction-right; sum maker -1710, sum taker -1910.

## G8  Nov 19 - Dec 2 2025 (Thanksgiving; Dec->Jan roll inside) - BLIND on brain s96.2

| date | dow | side | archetype (play called) | gross $ | MAKER net $ | TAKER net $ | dir | overnight-hold MAKER/TAKER $ |
|---|---|---|---|---|---|---|---|---|
| 20251119 | Wed | long | post_stabilization_hold_drift_up | +1790 | +1785 | +1765 | HIT | n/a (first day) |
| 20251120 | Thu | long | storage_thursday_turn_resume_up | -970 | -975 | -995 | MISS | -995 / -1015 |
| 20251121 | Fri | long | post_resumption_hold_range | +1080 | +1075 | +1055 | HIT | +1075 / +1055 |
| 20251124 | Mon | long | monday_weekend_gap_extend_cold_arriving | +220 | +215 | +195 | HIT | VOID (roll) |
| 20251125 | Tue | short | mature_swing_giveback | +1800 | +1795 | +1775 | HIT | +1785 / +1765 |
| 20251126 | Wed | long | giveback_exhausted_resume_pre_holiday_cold | +990 | +985 | +965 | HIT | +995 / +975 |
| 20251127 | Thu | long | thanksgiving_thin_hold_no_giveback | +220 | +215 | +195 | HIT | +225 / +205 |
| 20251128 | Fri | long | storage_print_early_close_swing_up | +2340 | +2335 | +2315 | HIT | +2335 / +2315 |
| 20251201 | Mon | short | monday_gap_fade_mature_extreme | -1090 | -1095 | -1115 | MISS | -605 / -625 |
| 20251202 | Tue | long | giveback_exhausted_resume_tuesday_trend | -430 | -435 | -455 | MISS | -445 / -465 |

Block footnote (secondary, NOT the finding): 10 events, 7 direction-right; sum maker +5900, sum taker +5700.

## G9  Dec 3 - Dec 31 2025 (surplus-collapse; Jan->Feb roll inside) - BLIND on brain s97.2

| date | dow | side | archetype (play called) | gross $ | MAKER net $ | TAKER net $ | dir | overnight-hold MAKER/TAKER $ |
|---|---|---|---|---|---|---|---|---|
| 20251203 | Wed | long | ramp_resume_frontrun | +1790 | +1785 | +1765 | HIT | n/a (first day) |
| 20251204 | Thu | short | storage_thu_postviolent_giveback | -810 | -815 | -835 | MISS | -815 / -835 |
| 20251205 | Fri | long | ramp_resume_to_crest | +2160 | +2155 | +2135 | HIT | +2145 / +2125 |
| 20251208 | Mon | short | crest_giveback_monday | +2330 | +2325 | +2305 | HIT | +4325 / +4305 |
| 20251209 | Tue | short | giveback_continue | +2640 | +2635 | +2615 | HIT | +2645 / +2625 |
| 20251210 | Wed | long | reramp_resume_frontrun | +180 | +175 | +155 | HIT | +175 / +155 |
| 20251211 | Thu | short | storage_thu_postviolent_giveback | +3820 | +3815 | +3795 | HIT | +3805 / +3785 |
| 20251212 | Fri | long | ramp_resume | -970 | -975 | -995 | MISS | -985 / -1005 |
| 20251215 | Mon | long | secondary_crest_late_rollover | -1690 | -1695 | -1715 | MISS | -765 / -785 |
| 20251216 | Tue | short | terminal_giveback_lull_deep | +1480 | +1475 | +1455 | HIT | +1465 / +1445 |
| 20251217 | Wed | short | giveback_chain_continue | -1400 | -1405 | -1425 | MISS | -1415 / -1435 |
| 20251218 | Thu | short | storage_thu_with_downchain | +2340 | +2335 | +2315 | HIT | +2355 / +2335 |
| 20251219 | Fri | short | capitulation_stabilization | -710 | -715 | -735 | MISS | -715 / -735 |
| 20251222 | Mon | long | fresh_turn_gap_extend | -830 | -835 | -855 | MISS | -455 / -475 |
| 20251223 | Tue | long | young_turn_chain_extension | +4160 | +4155 | +4135 | HIT | +4155 / +4135 |
| 20251224 | Wed | long | holiday_shifted_print_early_close | -2450 | -2455 | -2475 | MISS | -2535 / -2555 |
| 20251226 | Fri | long | thin_hardheat_delivery_meltup | +220 | +215 | +195 | HIT | VOID (roll) |
| 20251229 | Mon | short | postmeltup_giveback | +30 | +25 | +5 | HIT | -755 / -775 |
| 20251230 | Tue | long | ramp_resume | +130 | +125 | +105 | HIT | +125 / +105 |
| 20251231 | Wed | short | nye_thin_hold_drift | +2480 | +2475 | +2455 | HIT | +2475 / +2455 |

Block footnote (secondary, NOT the finding): 20 events, 13 direction-right; sum maker +14800, sum taker +14400.

## G10 Jan 2 - Jan 16 2026 (roll-clean) - BLIND on brain s98.2

| date | dow | side | archetype (play called) | gross $ | MAKER net $ | TAKER net $ | dir | overnight-hold MAKER/TAKER $ |
|---|---|---|---|---|---|---|---|---|
| 20260102 | Fri | short | chain_continue_down | +50 | +45 | +25 | HIT | n/a (first day) |
| 20260105 | Mon | short | capitulation_retest | -540 | -545 | -565 | MISS | +1235 / +1215 |
| 20260106 | Tue | long | alternation_bounce | -1310 | -1315 | -1335 | MISS | -1315 / -1335 |
| 20260107 | Wed | short | basing_giveback | -1160 | -1165 | -1185 | MISS | -1155 / -1175 |
| 20260108 | Thu | long | flip_confirm_frontrun | -1840 | -1845 | -1865 | MISS | -1855 / -1875 |
| 20260109 | Fri | long | print_delivery_up | -2530 | -2535 | -2555 | MISS | -2515 / -2535 |
| 20260112 | Mon | long | gap_extend_monday | +1300 | +1295 | +1275 | HIT | +2435 / +2415 |
| 20260113 | Tue | long | young_chain_extension | +550 | +545 | +525 | HIT | +545 / +525 |
| 20260114 | Wed | short | mature_giveback | +2880 | +2875 | +2855 | HIT | +2885 / +2865 |
| 20260115 | Thu | long | ramp_resume_delivery | +250 | +245 | +225 | HIT | +235 / +215 |
| 20260116 | Fri | short | post_extension_print_giveback | +200 | +195 | +175 | HIT | +185 / +165 |

Block footnote (secondary, NOT the finding): 11 events, 6 direction-right; sum maker -2205, sum taker -2425.

---

# PART 2 - REFINED CURVES (NOT BLIND - DO NOT READ AS EDGE)

**Loud label: the figures below are NOT a tradeable result and must never be presented as one.** The
refined curves are the post-hoc product of the per-group refine, iterated against the known actual tape
until they tracked it. They are in-sample by construction. They are reported only because the kickoff asked
for the structural upper bound, and because two of the strongest plays
(`direction.giveback_exhaustion_boundary` and `structure.mature_swing_alternation`) legitimately consume
day-N-1 ACTUAL tape - input a live coach would have and the one-shot blind test withholds. The truth for
those two plays sits somewhere between Part 1 and Part 2, and this replay cannot say where.

## G7  Nov 5 - Nov 18 2025 (first winter block) - REFINED (in-sample, not blind) on brain s95.2

| date | dow | side | archetype (play called) | gross $ | MAKER net $ | TAKER net $ | dir | overnight-hold MAKER/TAKER $ |
|---|---|---|---|---|---|---|---|---|
| 20251105 | Wed | short | mature-swing give-back probe off the 1104 extreme | +1030 | +1025 | +1005 | HIT | n/a (first day) |
| 20251106 | Thu | long | storage Thursday resume-day UP - give-back exhausted, side = running swing | +850 | +845 | +825 | HIT | +825 / +805 |
| 20251107 | Fri | short | mature-swing give-back off the fresh 1106 extreme, origin-shelf target | +580 | +575 | +555 | HIT | +585 / +565 |
| 20251110 | Mon | short | Sunday-gap delivery + Monday gap-fade at a mature-swing extreme | +1140 | +1135 | +1115 | HIT | -135 / -155 |
| 20251111 | Tue | long | resume day after exhausted gap-fade - hard_heat overrides the thin holiday | +1870 | +1865 | +1845 | HIT | +1865 / +1845 |
| 20251112 | Wed | short | post-violent-resumption hold day (give-back probes fail) | -20 | -25 | -45 | MISS | -15 / -35 |
| 20251113 | Thu | long | storage Thursday resume-day UP, late-swing sized | +900 | +895 | +875 | HIT | +895 / +875 |
| 20251114 | Fri | short | TERMINAL give-back - swing-exhaustion trigger fully armed at the 1113 extreme | +230 | +225 | +205 | HIT | +205 / +185 |
| 20251117 | Mon | short | give-back continuation Monday (not exhausted at Friday's close) | +1350 | +1345 | +1325 | HIT | +1545 / +1525 |
| 20251118 | Tue | long | origin-shelf stabilization - give-back spent-by-depth | +510 | +505 | +485 | HIT | +505 / +485 |

Block footnote (secondary, NOT the finding): 10 events, 9 direction-right; sum maker +8390, sum taker +8190.

## G8  Nov 19 - Dec 2 2025 (Thanksgiving; Dec->Jan roll inside) - REFINED (in-sample, not blind) on brain s96.2

| date | dow | side | archetype (play called) | gross $ | MAKER net $ | TAKER net $ | dir | overnight-hold MAKER/TAKER $ |
|---|---|---|---|---|---|---|---|---|
| 20251119 | Wed | long | immediate violent resume off the armed 1118 shelf turn (catalyst-continuity front-run) | +1790 | +1785 | +1765 | HIT | n/a (first day) |
| 20251120 | Thu | short | post-violent-extension give-back day - the print pops WITH the swing and round-trips (1002 form) | +970 | +965 | +945 | HIT | +985 / +965 |
| 20251121 | Fri | long | one-day give-back exhausted under a live ramp - Friday resume | +1080 | +1075 | +1055 | HIT | +1075 / +1055 |
| 20251124 | Mon | long | pre-priced-cold Monday hold at the swing extreme | +220 | +215 | +195 | HIT | VOID (roll) |
| 20251125 | Tue | short | mature-swing give-back in the weather LULL - deep band | +1800 | +1795 | +1775 | HIT | +1785 / +1765 |
| 20251126 | Wed | long | R5-depth resume into the arriving hard_heat - pre-holiday positioning | +990 | +985 | +965 | HIT | +995 / +975 |
| 20251127 | Thu | long | Thanksgiving thin hold after the violent resume | +220 | +215 | +195 | HIT | +225 / +205 |
| 20251128 | Fri | long | holiday-thin + hard_heat + print MELT-UP - thin amplifies, the early close does not cap | +2340 | +2335 | +2315 | HIT | +2335 / +2315 |
| 20251201 | Mon | long | Friday-carry resume Monday - the Sunday session already took the give-back | +1090 | +1085 | +1065 | HIT | +595 / +575 |
| 20251202 | Tue | short | mature-swing give-back at the HDD crest | +430 | +425 | +405 | HIT | +435 / +415 |

Block footnote (secondary, NOT the finding): 10 events, 10 direction-right; sum maker +10880, sum taker +10680.

## G9  Dec 3 - Dec 31 2025 (surplus-collapse; Jan->Feb roll inside) - REFINED (in-sample, not blind) on brain s97.2

| date | dow | side | archetype (play called) | gross $ | MAKER net $ | TAKER net $ | dir | overnight-hold MAKER/TAKER $ |
|---|---|---|---|---|---|---|---|---|
| 20251203 | Wed | long | ramp_resume_frontrun | +1790 | +1785 | +1765 | HIT | n/a (first day) |
| 20251204 | Thu | long | print_day_ramp_rising_through_extends | +810 | +805 | +785 | HIT | +805 / +785 |
| 20251205 | Fri | long | parabolic_blowoff_crest | +2160 | +2155 | +2135 | HIT | +2145 / +2125 |
| 20251208 | Mon | short | polarity_flip_confirm_crash | +2330 | +2325 | +2305 | HIT | +4325 / +4305 |
| 20251209 | Tue | short | flip_chain_crash_continue | +2640 | +2635 | +2615 | HIT | +2645 / +2625 |
| 20251210 | Wed | short | post_double_crash_continue_decelerating | -180 | -185 | -205 | MISS | -185 / -205 |
| 20251211 | Thu | short | print_liquidity_crash_at_flipped_extreme | +3820 | +3815 | +3795 | HIT | +3805 / +3785 |
| 20251212 | Fri | short | chain_continue_ordinary | +970 | +965 | +945 | HIT | +975 / +955 |
| 20251215 | Mon | short | cold_delivery_fails_in_flipped_chain | +1690 | +1685 | +1665 | HIT | +755 / +735 |
| 20251216 | Tue | short | chain_continue_decelerating | +1480 | +1475 | +1455 | HIT | +1465 / +1445 |
| 20251217 | Wed | long | exhausted_chain_leg_alternation_bounce | +1400 | +1395 | +1375 | HIT | +1405 / +1385 |
| 20251218 | Thu | short | print_crushes_young_bounce | +2340 | +2335 | +2315 | HIT | +2355 / +2335 |
| 20251219 | Fri | long | exhausted_leg_bounce_stabilization | +710 | +705 | +685 | HIT | +705 / +685 |
| 20251222 | Mon | short | chain_side_probe_thin | +830 | +825 | +805 | HIT | +445 / +425 |
| 20251223 | Tue | long | capitulation_recovery_thin_meltup_bounce | +4160 | +4155 | +4135 | HIT | +4155 / +4135 |
| 20251224 | Wed | short | holiday_print_crushes_young_bounce | +2450 | +2445 | +2425 | HIT | +2525 / +2505 |
| 20251226 | Fri | long | postcrash_basing_drift_up | +220 | +215 | +195 | HIT | VOID (roll) |
| 20251229 | Mon | STAND-DOWN | basing_hold | - | 0 | 0 | - | - |
| 20251230 | Tue | long | cold_peak_spike_fade | +130 | +125 | +105 | HIT | +125 / +105 |
| 20251231 | Wed | short | nye_liquidation_flush | +2480 | +2475 | +2455 | HIT | +2475 / +2455 |

Block footnote (secondary, NOT the finding): 19 events, 18 direction-right; sum maker +32135, sum taker +31755.

## G10 Jan 2 - Jan 16 2026 (roll-clean) - REFINED (in-sample, not blind) on brain s98.2

| date | dow | side | archetype (play called) | gross $ | MAKER net $ | TAKER net $ | dir | overnight-hold MAKER/TAKER $ |
|---|---|---|---|---|---|---|---|---|
| 20260102 | Fri | short | year_boundary_normalization_pause | +50 | +45 | +25 | HIT | n/a (first day) |
| 20260105 | Mon | long | weekend_gap_fade_monday | +540 | +535 | +515 | HIT | -1245 / -1265 |
| 20260106 | Tue | short | post_fade_chain_resume | +1310 | +1305 | +1285 | HIT | +1305 / +1285 |
| 20260107 | Wed | long | alternation_bounce | +1160 | +1155 | +1135 | HIT | +1145 / +1125 |
| 20260108 | Thu | short | post_bounce_chain_reassertion | +1840 | +1835 | +1815 | HIT | +1845 / +1825 |
| 20260109 | Fri | short | polarity_sided_print_crash | +2530 | +2525 | +2505 | HIT | +2505 / +2485 |
| 20260112 | Mon | long | counter_catalyst_gap_bounce | +1300 | +1295 | +1275 | HIT | +2435 / +2415 |
| 20260113 | Tue | long | bounce_day2_fade | +550 | +545 | +525 | HIT | +545 / +525 |
| 20260114 | Wed | short | bounce_death_crash | +2880 | +2875 | +2855 | HIT | +2885 / +2865 |
| 20260115 | Thu | long | bleed_post_crash_pause | +250 | +245 | +225 | HIT | +235 / +215 |
| 20260116 | Fri | short | chain_sided_print_small | +200 | +195 | +175 | HIT | +185 / +165 |

Block footnote (secondary, NOT the finding): 11 events, 11 direction-right; sum maker +12555, sum taker +12335.

---

# PART 3 - PER-CELL (Guard 2): which calls pay, on which subset

All BLIND, session cell, TAKER (the pessimistic assumption). Each cell lists its own events.

## By archetype family

| cell | n | dir-right | sum TAKER $ | events (date: taker $) |
|---|---|---|---|---|
| resume / continuation | 10 | 9 | +8560 | 20251118: +485, 20251203: +1765, 20251205: +2135, 20251210: +155, 20251212: -995, 20251223: +4135, 20251230: +105, 20260102: +25, 20260113: +525, 20260115: +225 |
| give-back | 10 | 6 | +6600 | 20251105: +1005, 20251112: -45, 20251125: +1775, 20251202: -455, 20251209: +2615, 20251216: +1455, 20251217: -1425, 20251229: +5, 20260107: -1185, 20260114: +2855 |
| thin / holiday session | 5 | 5 | +5655 | 20251111: +1845, 20251126: +965, 20251127: +195, 20251226: +195, 20251231: +2455 |
| unclassified | 6 | 2 | +660 | 20251107: -605, 20251114: -255, 20251119: +1765, 20251121: +1055, 20251219: -735, 20260105: -565 |
| print / storage day | 10 | 4 | -60 | 20251106: -875, 20251113: -925, 20251120: -995, 20251128: +2315, 20251204: -835, 20251211: +3795, 20251218: +2315, 20251224: -2475, 20260109: -2555, 20260116: +175 |
| weekend-gap Monday | 7 | 3 | -735 | 20251110: -1165, 20251117: -1375, 20251124: +195, 20251201: -1115, 20251208: +2305, 20251222: -855, 20260112: +1275 |
| turn / bounce / polarity flip | 3 | 0 | -4915 | 20251215: -1715, 20260106: -1335, 20260108: -1865 |

## By day of week

| cell | n | dir-right | sum TAKER $ | events (date: taker $) |
|---|---|---|---|---|
| Tue | 10 | 8 | +11150 | 20251111: +1845, 20251118: +485, 20251125: +1775, 20251202: -455, 20251209: +2615, 20251216: +1455, 20251223: +4135, 20251230: +105, 20260106: -1335, 20260113: +525 |
| Wed | 11 | 7 | +5835 | 20251105: +1005, 20251112: -45, 20251119: +1765, 20251126: +965, 20251203: +1765, 20251210: +155, 20251217: -1425, 20251224: -2475, 20251231: +2455, 20260107: -1185, 20260114: +2855 |
| Thu | 9 | 4 | +1035 | 20251106: -875, 20251113: -925, 20251120: -995, 20251127: +195, 20251204: -835, 20251211: +3795, 20251218: +2315, 20260108: -1865, 20260115: +225 |
| Fri | 11 | 6 | +755 | 20251107: -605, 20251114: -255, 20251121: +1055, 20251128: +2315, 20251205: +2135, 20251212: -995, 20251219: -735, 20251226: +195, 20260102: +25, 20260109: -2555, 20260116: +175 |
| Mon | 10 | 4 | -3010 | 20251110: -1165, 20251117: -1375, 20251124: +195, 20251201: -1115, 20251208: +2305, 20251215: -1715, 20251222: -855, 20251229: +5, 20260105: -565, 20260112: +1275 |

## Concentration check (Guard 1 in reverse - the aggregate is carried by named individuals)

| rank | block | date | archetype | TAKER $ |
|---|---|---|---|---|
| 1 | G9 | 20251223 | young_turn_chain_extension | +4135 |
| 2 | G9 | 20251211 | storage_thu_postviolent_giveback | +3795 |
| 3 | G10 | 20260114 | mature_giveback | +2855 |
| 4 | G9 | 20251209 | giveback_continue | +2615 |
| 5 | G10 | 20260109 | print_delivery_up | -2555 |
| 6 | G9 | 20251224 | holiday_shifted_print_early_close | -2475 |
| 7 | G9 | 20251231 | nye_thin_hold_drift | +2455 |
| 8 | G8 | 20251128 | storage_print_early_close_swing_up | +2315 |

## Fee-materiality check

Across all 51 blind session events, **zero** had a gross P&L small enough for the taker fee to flip its
sign (no event had 0 < gross < $25). The 11 events inside the fee-material band (|gross| <= $250) are
20251112 (-20), 20251114 (-230), 20251124 (+220), 20251127 (+220), 20251210 (+180), 20251226 (+220),
20251229 (+30), 20251230 (+130), 20260102 (+50), 20260115 (+250), 20260116 (+200). On this vehicle the
maker-vs-taker gap ($20/contract) is roughly 1 percent of a typical NG day range.

---

# BOTTOM LINE

**1. On the NG futures vehicle, fees are not the binding constraint - direction is.** A $5 maker or $25
taker round trip against day sessions that routinely move $500-$4,000 per contract is noise. Every
loss-making block below loses because the call was wrong, not because the cost ate it. This reframes "the
money question": the S81/S82 size-vs-fee problem is a KALSHI problem, and it does not transfer to the NYMEX
canary leg. It will return the moment the Kalshi echo (wide spreads, per-contract fees on a $1 instrument)
is the vehicle - this replay says nothing about that leg.

**2. Blind, the playbook does not pay across the walk as a whole - two of four blocks lose.** Per block,
session cell, named individually:
- **G7 blind: MAKER -$1,710, TAKER -$1,910** over 10 events, 3 direction-right. Loses.
- **G8 blind: MAKER +$5,900, TAKER +$5,700** over 10 events, 7 direction-right. Pays.
- **G9 blind: MAKER +$14,800, TAKER +$14,400** over 20 events, 13 direction-right. Pays.
- **G10 blind: MAKER -$2,205, TAKER -$2,425** over 11 events, 6 direction-right. Loses.

**3. G9's large positive is carried by six named events, not by breadth.** 20251211 (+3,795), 20251223
(+4,135), 20251209 (+2,615), 20251231 (+2,455), 20251218 (+2,315), 20251208 (+2,305). The other fourteen
G9 events sum to roughly -$3,200. The block pays because a handful of high-magnitude days were called on
the right side - which is consistent with the standing magnitude-staircase read, and is also exactly the
profile that a single mis-called crash day would invert. Do not read G9 as a stable +$14k.

**4. A right block lean and a paying day-book are different things, and they came apart here.** G9 was
recorded in the S96 handoff as the walk's FIRST BLOCK-LEAN MISS (+3,000 guessed vs about -6,150 actual) -
yet the day-by-day session book is the walk's best blind block. G10's blind block lean was also a miss and
the day book loses. The block lean and the daily call are separate products; a wrong lean did not
automatically cost money on G9 because the daily trade never carries the lean.

**5. Per-cell (Guard 2) - the subsets that clear costs, blind, at taker:**
- **WORKS: Tuesday sessions.** 8/10 direction-right, +$11,150 across G7-G10. The single strongest cell in
  the walk. Mechanism candidate: Tuesday is the post-weekend-reaction, pre-print day - the running swing
  state is cleanest and no catalyst is pending.
- **WORKS: thin / holiday sessions.** 5/5 direction-right, +$5,655 (20251111 Veterans Day, 20251126,
  20251127 Thanksgiving, 20251226, 20251231 NYE). Small n but unblemished, and consistent with the S96
  finding that thin AMPLIFIES delivery. The magnitudes are lopsided (+1,845 and +2,455 carry it).
- **WORKS: resume / continuation calls.** 9/10 direction-right, +$8,560. Calling an existing chain to
  continue is the playbook's most reliable act.
- **WORKS (marginally, high variance): give-back calls.** 6/10, +$6,600, but with -1,425 and -1,185 inside.
- **DOES NOT WORK: turn / bounce / polarity-flip calls.** 0/3, -$4,915 (20251215, 20260106, 20260108).
  Every attempt to call a turn in advance lost money. This is the same defect the S96/S97 refines already
  identified and is why the flip CONFIRM was hardened to four mandatory conditions in s99.2 - but that
  hardening is UNTESTED forward, and this replay is its indictment, not its vindication.
- **DOES NOT WORK: weekend-gap Monday.** 3/7, -$735, with -1,375, -1,165 and -1,115 inside. Monday remains
  unsolved; the S96 retirement of "Monday as reversal" is supported but nothing reliable replaced it.
- **DOES NOT WORK: print / storage Thursday.** 4/10, -$60 - a coin flip that nets to nothing. Note the
  distribution is violent, not flat: +3,795 and +2,315 against -2,555 and -2,475. The R2 rule (print leg
  sides with the running swing) scored 10/10 in the refine but its BLIND application is 4/10, which is a
  direct measure of how much of R2 lives in day-N-1 tape the blind test withholds.

**6. The refined figures are not evidence of edge and are quarantined in Part 2.** For the record they run
G7 +$8,190, G8 +$10,680, G9 +$31,755, G10 +$12,335 taker, 48/50 direction-right. That is a fitted upper
bound on what perfect access to the prior day's tape plus perfect rule selection would have produced. The
gap between Part 1 and Part 2 is the size of the prize for making the live sequential coach work; it is not
a claim that the prize has been won.

**7. The overnight-hold cell adds nothing and costs the roll risk.** Where clean, the hold numbers track the
session numbers closely (G8 +4,210 vs +5,700; G9 +14,870 vs +14,400; G10 +480 vs -2,425; G7 -1,805 vs
-1,910 taker). G10 is the only block where holding beat the session, and it did so on one event (20260112,
+2,435 hold vs +1,275 session). Given that holding is what exposes the book to the +$390 and -$5,040 roll
artifacts, the session cell is the correct default.

## Limitations - read before quoting any number

- **Maker fill risk is unmodelled and is the single largest soft assumption.** The maker column assumes a
  resting limit fills at both the entry and the exit mark. On this vehicle the maker/taker difference is
  only $20/contract, so no conclusion above depends on the maker assumption - but the moment this method is
  ported to Kalshi, where the spread IS the cost, the maker assumption becomes load-bearing and must be
  replaced with a real fill model.
- **The exit is a 2-hour-grid approximation** (grid index 10, roughly 14:00 ET), not a tick-level fill. It
  is deliberately conservative on the settle guard, and it means the exit price is not the day's close -
  several events differ materially in sign or size from the `actual_net_usd` in the score records, which
  are close-based. The session P&L here should not be reconciled against those close figures.
- **Slippage beyond one tick, partial fills, and position sizing are all absent.** 1 contract per event, no
  scaling, no stops.
- **51 blind events over four blocks is a small sample**, and the four blocks are consecutive winter, so the
  cells are not independent of regime. The Tuesday cell (n=10) and the thin-session cell (n=5) are
  suggestive, not established.
- **G3-G6 comparability caveat stands** (those groups ran before the S96 blind-wall fix); they are not
  included here.
- Canary-side only. No Kalshi echo, no lag, no NYMEX options.
