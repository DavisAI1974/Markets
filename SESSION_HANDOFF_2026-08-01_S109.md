# SESSION HANDOFF - 2026-08-01, S109 (G22 blind; holes #9-#11; the AUDITOR role; the weather model rebuilt)

Branch: `claude/kalshi-agents-coordinator-guard-1175nr`. Brain **s103.6 -> s103.7, 68 plays**.

This session ran the G22 blind twice - the first run was VOID - built a sixth agent role, found three more
data holes, and rebuilt the weather model from the ground up on Greg's desk knowledge. Four of the
sharpest corrections came from Greg, not from the machinery, and each changed a conclusion rather than
decorating one.

## THE HEADLINE

- **G22 BLIND COMPLETE: 4/10 direction, sum|err| 5,965, drift -1,815, survives 30%.** Second-best blind
  of the walk on sum|err| (G17 4,510 - **G22 5,965** - G21 6,320 - G20 7,880 - G19 9,390); worst on
  direction.
- **THE DRIFT IS THE MISSED HILL.** Realized gw_cdd ran 9.0 -> 17.5 across the block; actual cum **+470**;
  blind cum **-1,345**; miss **-1,815** = the drift, exactly.
- **THREE NEW HOLES: #9 (`session_b_share` wrong ENCODING), #10 (`squeeze_watch` FROZEN-BUT-LIVE),
  #11 (the state let every specialist READ PAST ITS OWN DECISION POINT).** All three fixed.
- **THE STATE AUDITOR is a new canonical role** (`agents/state_auditor.md`), trialled blind on G21 where
  it independently found the hardest of the eight prior holes.
- **Brain s103.7**: +`supply.lng_export_throughput_vessel_line`, WIRED_UNPROVEN, on Greg's instruction.

## HOLE #9 - session_b_share served a hard 0.0 (WRONG ENCODING)

Found auditing G22's staged state before spawning. `session_b_share` read **exactly 0.0 on all 8
scored-leg days of G22 and G23** plus both `prior_full_session` limbs - 20 readings, every one present,
numeric, in range and self-consistent.

The two readers that fill `_tape_day_stats` spell a side differently: the continuous reader appends the
raw tape string `"B"`, the S108 leg reader appends flow_read's signed int `1`, and its docstring claimed
they were mapped identically. The shared math tests `s == "B"`, so nothing matched. Only this field
showed it because `_tape_enrich` copies every OTHER b_share through from flow_read and `session_b_share`
was the one field missing from that list.

Three defences, different in kind: source normalization; the copy-through; and a **RECONCILIATION** guard
(`session_b_share == session_b_share_two_sided * (1 - unsided_volume_frac)` is an algebraic identity),
HARD at >0.002. Negative-tested 20 hard pre-repair, 0 after, zero false positives across 17 groups.
`bshare_restage_repair.py` recovers the value without a data plane and declares each repair.

## HOLE #10 - squeeze_watch's "_live" limbs were the FROZEN value under a live name

S108 set out to derive the calendar limb live and shipped fields that copy the anchor vintage:
`days_to_calendar_front_expiry_live` a constant 5 and `calendar_front_symbol_live` a constant NGN26 on all
ten days, while `flow_calendar` correctly walks 4,3,2,1,0 then 21,20,19,18 and rolls to NGQ26. The block
asserted the opposite **in prose**. `calendar_limb_satisfied_live` read TRUE on five sessions whose live
dte is 18-21 against a <=7 window - **S108 fixed a false negative here and shipped its mirror image.**

Also frozen: the dead-sponsor arm, stuck on the MAY prompt (`sessions_since_prompt_expiry` 16) though
NGN26 expired 06-26 inside the block. Re-derived: 1 on 0629, and `unwind_watch` flips TRUE on 0629-0701 -
the `block_gap_ownership` ANCHOR_STRUCTURAL trigger a false flag was routing past.

The boolean is NOT repaired to true: the gate needs a masked spread limb, so it is **null with the reason
stated**. A derived boolean whose input is unavailable must not be emitted as false.

## HOLE #11 - THE STATE LET EVERY SPECIALIST READ PAST ITS OWN DECISION POINT

**The defect is the file layout, not the agents.** A block serves, under each day's key, the PRIOR
session's tape - correct per day. But all ten days live in ONE file, so day X's own realized outcome sits
one block later:

```
[20260623].tape_conditions                    = session 20260622 realized
[20260629].tape_conditions.prior_full_session = session 20260626 realized
[20260703].stor_surprise                      = 39.2, the 07-02 print's OWN surprise
```

**On the first G22 blind ALL THREE specialists reached forward and ALL THREE DECLARED IT.** D forecast
an EIA print day already knowing the print. E built its entire phase read, path shape and all nine
handoff fields on its own day's realized close phase. Those posteriors are retained as the record in
`forecasts/g22_wave1_void/` and are NOT blind-legitimate.

**A rule in the prompt is not the fix** - all three were already under a hard read-only rule and reached
forward anyway, because the data sat in the file they were told to read and reaching for it is
indistinguishable from diligence. `build_causal_slices.py` cuts one slice per day and makes the future
ABSENT. It self-audits, and `forward_stamps()` additionally reports capture stamps past the decision
point (found by C: a `consensus_pre_print_snapshot_utc` dated 2026-07-02 under the 0629, 0630 and 0701
blocks).

## THE STATE AUDITOR - a sixth role, and it works

Greg's call: *"create a separate agent to do the two roles... test it on a group that's already run."*

The tension it resolves: cross-day reading is how eleven holes were found, but a forecaster reading
across days acquires information past its own decision point. Split the roles and both survive - the
auditor cross-compares freely because it has nothing to contaminate; the specialists run on causal slices.

**TRIAL (G21, blind to all of it), graded against a pre-committed table:**
- Found the **off-instrument tape defect S108 called the hardest of the eight** - and found it WITHOUT
  the scored-leg reconciliation S108 used, building an internal proof from three ratios crossing a
  trade-tape statistic against a non-trade-tape statistic, all separating with **zero overlap**.
- Independently rediscovered two more documented defects, with **no hints**.
- **Corrected a ground-truth claim of mine** that was wrong.
- Zero filler; two thirds of its effort produced specific clean negatives.
- Missed one: verified `session_signed_flow == sum(phase_signed_flow)` and walked past a **-1 net on a
  22,490-trade session**. That miss is now a standing instruction in the role file: check LEVELS for
  plausibility, not only identities.

**FIRST LIVE RUN (G22): 15 findings**, including the two severe ones fixed above and a confirmed
**LOOK-AHEAD**: `storage_consensus` serves a consensus captured AFTER the print it precedes (on 0622,
`days_to_print: 3`, the served 74.0 is snapshotted 06-25/06-26). On the 06-25 print it destroys ~78% of
the decision-time surprise. **Unfixed - needs the source feed.**

## THE G22 BLIND, RE-RUN CLEAN

Per-day causal isolation, 10 agent runs (C x4, D x2, E x1, A x1 + bridge, B x2), sequenced C/D/E -> A -> B.

```
0622 B  -420 vs  +650   0629 B  +325 vs -1110      4/10 dir
0623 C  -430 vs  -730   0630 C  -420 vs  +780      sum|err| 5,965
0624 C  -200 vs  +800   0701 C  -380 vs  -500      drift   -1,815
0625 D  -110 vs   -60   0702 D  +200 vs     0      survives   30%
0626 E  +250 vs  +230   0703 A  -160 vs  +410
```

**What went right:** both EIA Thursdays inside 200, each with a FALSIFIABLE timing claim attached (D put
~11% of magnitude pre-print and stated the falsifier). E's 0626 off by 20. D used the **pre-print 67.0**
rather than the leaked 74.0, so the "already priced" limb correctly did not fire.

**The roll confound - three specialists, independently, no contact.** E's own flip-limb keys on 0626's
big prints hitting 0.783 on 210 prints with a +2,737 final phase. It fires on the letter and is **roll
mechanics**: NGN26 expired that day and the scored leg is the deferred NGQ26. Settled by an independent
quantity - `session_b_share_two_sided` did **not move** (0.509 -> 0.504) on the day big prints supposedly
hit 78.5% buy, so the rest of the tape must have been selling into it. Control: 0625 was also a
scheduled-flow day and shows none of the fingerprints.

**A caught a defect in MY architecture.** A is spawned on the last day, so its slice contained the Monday
it was bridging. It declared and firewalled rather than hiding, and recommended "fix architecturally."
The bridge was re-run on a 0629-cut slice. **Per-day slices are right for a specialist's own day and
wrong for a second job with an earlier decision point.**

## THE WEATHER MODEL, REBUILT (Greg - the session's most valuable thread)

**1. Weather is a MULTIPLIER, not only a driver.** *"Where they play a big one is unexpected swings that
no one forecasts for, or long durations of the extremes... what they can really be is a big multiplier."*
The Chicago case: transport capped for maintenance + mild expected temps + a cold snap that **sits for
days** = huge factor.

**2. Then Greg corrected my over-reading, and the correction is the more important half.** *"Mild weather
kills demand: big driver down. High heat/cold: driver up (some). The weather is the low grade hill...
It is THE driver but it's gentle changes over time."* I had written "close to inert absent an anomaly."
**Wrong, and it would have shipped.**

**THE CORRECTED STRUCTURE - TWO REGIMES:**
- **THE HILL (always on).** Weather IS the driver, continuously, as a SLOPE. **ASYMMETRIC**: mild kills
  demand and is a **big** driver down; heat/cold is up but **only some**.
- **THE SPIKE (conditional).** `anomaly x duration x constraint` multiplies on top.
- **A hill slopes, it does not gap.** That sentence resolves 0629: the error was not expecting weather to
  matter, it was expecting the hill to GAP (+480 forecast against +50 actual).

**3. The gas call is a STACK, and weather is only its top term:**
```
gas call = weather-driven load - renewables (solar+wind) - what coal/nuclear can absorb
```
**0629 explained mechanically:** gw_cdd 10.0 -> 14.8 exactly as forecast, and **gas burn FELL 4.2 Bcf/d**
(38.6 -> 34.4) because **wind rose 62%** (+660,219 MWh) and total demand declined. **The channel was
served.** A and B both adjusted for nuclear (~19,200 MWh) and **neither looked at wind, which moved 34x
more, against their thesis.** C found it independently on 0630; per-day isolation meant it never reached
the bridge - **a real cost of causal isolation, recorded.**

**4. Summer gas demand is ~50% power burn (Greg, from EIA docs)** - so the degree-day weights must be
**SEASONAL**. Winter = heating-weighted; summer = **gas-fired generation** weighted, a completely
different distribution (CISO is 4.8% of electric demand but **0.4%** of gas generation). Our table is
static. My hedge that PJM's nuclear/coal suppress its gas share was wrong both ways: **PJM's gas share
is 0.4286 - higher than MISO or ERCOT - and PJM is the largest gas-burning BA at 23.2% of national
power-sector gas burn.**

**5. The station weights are hand-set, unvalidated, and OHIO HAS NO STATION AT ALL** (Greg: *"Philly is a
huge PJM load, as is Columbus where I live"*). Also absent: Baltimore, Pittsburgh, Cleveland, Cincinnati,
Richmond. PJM is 18.3% of US48 demand; its footprint in our index is PHL+DCA = 11.2%.

**6. Chicago IS tracked on demand** - `ORD` at **11.24%**, second only to NYC - so I overstated "we could
not have seen the Chicago case." We would see the cold; we cannot see the **cap**. `nws_temp_feed`'s own
header names the gap: *"per-hub local weather (Chicago Citygate etc.) is the DEFERRED per-location basis
stack."*

**7. Coal headroom is the supply-side twin of the multiplier.** Coal is still 16.1% of US48 GENERATION
and not fading in-block - but that measures the wrong thing. The trade-relevant quantity is **marginal
switching headroom**, and we have fuel generation with **no fuel availability**. EIA-860M (S98's "slow
layer") and ISO outage aggregates (arm 4, Greg's own spec) were scoped and never built.

## gas_call_residual - BUILT, AND UNTESTED IN ITS CLAIMED REGIME

`gas_call_residual.py` computes `demand - solar - wind - nuclear` (coal deliberately NOT subtracted -
that would reproduce `gas_mwh` by construction). Two alignments, mechanism and decision-time.

**Greg: *"Residual is only going to drive it in cold or getting cold times."*** And **every block with
`grid_stack` is WARM** - mean gw_hdd 0.12 to 0.72 across G20-G23. So the verdict is **not "inconclusive"
but UNTESTED IN ITS CLAIMED REGIME**. A null measured entirely outside a play's scope is not a null.

It also corrected me: I described the negative degree-day correlation (-0.412, -0.293, -0.223, -0.243) as
holding "across winter, spring and two summers." **There was no winter block.** Scoped to WARM, that
result *supports* the hill/spike model - the level change is already priced, so trading it fades an
anticipated move.

**Cheapest decisive test:** backfill `grid_stack` (EIA-930 - **free, historical**) across G7-G13, the
walked winter. The gap is chronological: feed Q was built in S99, after those blocks were staged.

## BRAIN s103.6 -> s103.7

**+`supply.lng_export_throughput_vessel_line`** (Greg: *"are we still tracking lng tankers?"*). The audit
found the vessel line **live and moving** (departures 36->35->36, capacity 133.0->135.0->136.0, Vortexa
via EIA WNGSR) with **zero consumers** - while `lng_feedgas_bcfd` is null and its only figure is 278 days
stale. Wired **WIRED_UNPROVEN**, confidence none-yet, forward_evidence NONE - merged to make a live
channel readable, explicitly **not** as a signal.

**WHY IT IS ABOUT TO MATTER MORE, NOT LESS (Greg):** two live forward drivers. **(1) GULF HURRICANE
SEASON** - the US liquefaction fleet is Gulf Coast (Sabine Pass, Corpus Christi, Freeport, Cameron), so a
storm hits export capacity AND Gulf production together and the two pull price in **opposite**
directions; departures are the observable that separates them. Season is **Aug-Oct and live NOW**.
**(2) A MIDDLE EAST SUPPLY HOLE** pulling more US cargoes - export throughput rises, bullish US gas. Both
are STEP events, which is what this line reads.
**The weakness is the hurricane case**: departures LAG, so a terminal that shuts today shows here days
later while price reacts to the track immediately. Confirmation, never early warning. **NAMED GAP: we
carry NO tropical/hurricane feed at all** - `freeze_risk` is the winter analogue and has no summer
counterpart. All 67 incumbents byte-identical; backup at
`knowledge/ng_brain_s103.6_backup.json`.

## OPEN, highest value first

1. **G22 REFINE** - not run. Two specific targets, not an aggregate: the missed hill, and 0629's
   slope-treated-as-spike.
2. **Backfill `grid_stack` G7-G13** (free) - makes the residual testable in cold, and puts a cold arm
   under the degree-day correlation.
3. **Seasonal station weights + Ohio/Baltimore**, reconciled against EIA state-level gas consumption BY
   SECTOR. Summer table is buildable from `grid_stack.bas[*].gas_mwh` already on disk.
4. **`storage_consensus` look-ahead** (auditor f2) - needs the source feed.
5. **CDD vs NORMAL** - the anomaly instrument; separates hill from spike.
6. Re-stage G18/G19 weather (S107 path hole) for the shoulder arm.
7. Coal headroom: EIA-860M + ISO outage aggregates.
8. **A TROPICAL / HURRICANE FEED** - Aug-Oct is live now and the Gulf carries both the liquefaction
   fleet and Gulf production. No summer counterpart to `freeze_risk` exists.
9. Citygate basis (the Chicago constraint tell) and **ECMWF** - the only two plausibly PAID items.
   **Greg: a weather sub "at some point but not tonight."** Sequencing: the free items land FIRST,
   because they change what the slope channel measures.
10. G21 round 2; the live orchestrator; `options_surface` 10x strike scale.

**KEYS DO NOT ROTATE DURING THE WALK.**

## THE THING TO CARRY FORWARD

Four of tonight's sharpest corrections came from Greg, not the machinery: weather-as-multiplier, the
two-regime correction, Chicago/PJM coverage, and the residual's cold-only scope. **A panel can be
internally rigorous and collectively wrong when the instrument encodes the wrong model**, and no amount
of cross-checking inside the panel surfaces that.

And the recurring enemy now has a name and a shape: **served but unread**. The renewable subtractor was
served and unread. `session_b_share` was served and broken. The CDD ladder was computed and dropped. The
vessel line is live with zero consumers. Every one of them is present, well-formed, in range - and wrong
or invisible. **Field checks cannot catch it; only reconciliation against an independent source can.**
