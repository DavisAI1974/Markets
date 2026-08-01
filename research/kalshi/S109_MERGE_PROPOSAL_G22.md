# S109 MERGE PROPOSAL — from the G22 blind

**PROPOSAL ONLY. No brain edit has been made.** Per standing doctrine: brain merges are proposal files
plus adjudication, incumbents byte-identical, never a direct edit. Nothing here is merged until Greg
says so. Evidence and reasoning: `G22_REASONING_LEDGER_S109.md`.

G22 blind: 4/10 direction, sum|err| **5,965**, drift **−1,815**, survives 30%. Second-best blind of the
walk on sum|err| (G17 4,510 · **G22 5,965** · G21 6,320 · G20 7,880 · G19 9,390) and the worst on
direction.

---

## P0 — WEATHER IS A MULTIPLIER, NOT A DRIVER (Greg, S109 — supersedes the framing of P1)

**Greg, from the desk:** heat and cold usually play a *small* part. Where they play a big one is
**unexpected swings nobody forecast for**, or **long durations of extremes**. Weather mattered far more
20 years ago when there was less production capacity. *"What they can really be is a big multiplier."*
The illustration: transportation into Chicago is capped this week for maintenance, expected temps are
mild — then a cold snap blows in overnight and **sits on Chicago for days**. Now weather is a huge
factor.

**Greg, correcting an over-reading of the above:** *"That's not totally true about being a driver in
only those 2 situations. Mild weather kills demand: big driver down. High heat/cold: driver up (some).
The weather is the low grade hill. Until something extreme or unexpected happens. It is THE driver but
it's gentle changes over time."*

**The structural claim, in its corrected form — two regimes, not one:**

1. **THE HILL (always on).** Weather **is** THE driver, continuously, as a **slope** — gentle changes
   over time. It is **not** inert absent an anomaly; that was my over-correction and it was wrong. And
   it is **ASYMMETRIC**: mild weather *kills demand* and is a **big driver down**; high heat/cold is a
   driver **up, but only some**. The down-side of the asymmetry is the stronger one.
2. **THE SPIKE (conditional).** `anomaly × duration × constraint` is a **MULTIPLIER on top of the
   hill** — the Chicago case. This is when weather stops being a slope and becomes the whole story.

The error to avoid is confusing them: **a hill slopes, it does not gap.**

**G22 measures the hill directly, and the hill is the entire drift:**

| | |
|---|---|
| realized gw_cdd across the block | **9.0 → 17.5** — a rising hill, demand building all block |
| actual block cum | **+470** — the hill, sloping up, gently |
| blind block cum | **−1,345** — called it down |
| miss | **−1,815** = the block drift, exactly |

So the drift is **not** "four bearish artifacts" as P1 framed it. The drift **is the missed hill**; the
artifacts (P1) are the *mechanism* by which the blind could not see it — every HDD-keyed instrument
being void or bearish in a CDD block left it with no slope channel at all.

**And this re-reads 0629 correctly.** The error was not expecting weather to matter — weather mattered
all block. It was expecting the **hill to gap**: a forecast gap of +480 from what was slope movement,
against an actual +50. The hill was real and it was up; it simply does not arrive as an overnight
repricing. That is a sharper and more useful lesson than "the panel was too bullish."

**G22 is a clean confirming instance, and it explains the block's largest error.** Every authority
condition was absent on 0629:

| condition | 0629 | reading |
|---|---|---|
| forecast surprise | **−0.015** (forecast 14.815, realized 14.8) | nobody was surprised |
| vs normal | **+0.096** | dead normal |
| duration of extreme | none — 9.0 → 18.7 is the seasonal ramp | June becoming July |
| supply constraint | +112 Bcf surplus, ample production | nothing to multiply |

Block-wide the largest surprise is −1.28 and vs-normal never leaves −0.078 to +0.175. **The CDD ramp
was summer arriving on schedule, priced weeks out.** The bridge read a +4.7 *level* move as a driver
when the anomaly was zero — and the gap paid +50.

**This reframes P1 from a calibration problem to a KIND problem.** `divergence_resolution` (HDD ≥ 16.4)
and `shoulder_weather_band_void` (HDD ≤ 13.5) are **level** bars. A level bar cannot express
"unexpected", "persistent", or "into a constraint" — so no re-pointing of those bars to a CDD ladder can
be right, and setting a summer CDD level bar would reproduce the same error in a new season. **My
earlier P1 proposal to re-point them to CDD levels is WITHDRAWN.**

**INSTRUMENT INVENTORY — and the multiplier's key limb does not exist.**

| limb | instrument | status |
|---|---|---|
| anomaly (CDD) | CDD **vs normal** | **MISSING.** `forecast_vs_normal` is HDD-keyed; the CDD levels landed this session, the anomaly did not |
| surprise | realized − forecast | **derivable now** (computed above; the feed carries both) |
| revision | forecast run-over-run | served, but seam-blind (P2) |
| duration | consecutive days of anomaly beyond a bar | **MISSING** — no persistence field anywhere |
| constraint — regional basis | citygate / regional cash basis | **MISSING.** `cash_basis` is **Henry Hub only**. `nws_temp_feed`'s header names it: *"per-hub local weather (Chicago Citygate etc.) is the DEFERRED per-location basis stack"* — scoped out deliberately, never built |
| constraint — maintenance | pipeline maintenance / capacity derates | **MISSING** — no feed exists |
| constraint — regional tightness | `storage_regional.days_of_supply` | present but **null** |
| supply headroom | production vs capacity | not served |
| **demand at the location** | **COVERED, and heavily** | `ORD` is **11.24%** of the gas-weighted index (2nd after NYC 13.48%); `MISO` + `PJM` in `grid_stack`; `storage_regional.midwest` |

**The split matters for scoping the build (Greg): Chicago is a huge city and is already factored into HH
usage — it is tracked.** The DEMAND half of the Chicago mechanism is instrumented at heavy weight. What
is absent is the CONSTRAINT half: the cap, the citygate blowout, the deliverability squeeze. So a cold
snap parked on Chicago **would** move our degree-day index; what we could not see is whether it was
landing into a constrained pipe — which is the difference between a slope and a spike. **Build the
basis stack, not the demand side.**

**PROPOSED AS BUILDS, NOT AS PLAYS.** The SPIKE limbs (anomaly, duration, constraint) cannot be written
or tested until they are observable, and writing one against G22 — the block with the least *spike*
authority in the walk — would be fitting of the worst kind. The HILL, by contrast, is measurable right
now and is the higher-value half, because it is always on. Priority order:

1. **THE SLOPE CHANNEL — highest value, and it is now half-built.** The CDD level ladder landed this
   session, so a summer block finally has a slope instrument at all. What is still missing is the
   **asymmetry**: mild-kills-demand is a *bigger* down driver than heat-adds is an up driver, and
   nothing in the brain encodes that. Measurable across the walked blocks — regress day-move against
   the CDD/HDD slope separately on the mild side and the extreme side. This is a MEASUREMENT, not a
   proposal; the coefficient must come from the tape, per block-class.
2. **CDD vs NORMAL** — the anomaly instrument, and the thing that separates hill from spike. The feed
   already computes normals for HDD; this is the same computation on the other side of the balance
   point. Without it, summer has no way to tell a seasonal ramp from a genuine anomaly — which is
   exactly the distinction 0629 got wrong.
3. **Forecast surprise + persistence** — realized − forecast per day, and a run-length of consecutive
   days beyond an anomaly bar (the "sitting on Chicago for days" limb). Both derivable from data on disk.
4. **Regional / citygate basis** — the constraint tell, and the one carrying the Chicago mechanism. A
   cold snap parked on a constrained citygate shows up in basis *before* it shows up in the front.
5. **Pipeline maintenance / capacity derates** — the "cap is lower this week" input. Genuinely new feed.

**Falsifier for the whole frame, stated so it can be killed:** a block where a large degree-day anomaly
with high forecast surprise, long duration and a live regional constraint produces **no** outsized move
would refute the multiplier model. G22 cannot test it — it has none of those conditions, which is
precisely why weather was inert here.

**Historical scope note (Greg):** the multiplier was larger 20 years ago at lower production capacity.
Any coefficient fitted on the modern tape must not be back-applied to older data, and vice versa.

---

## P0.5 — THE DEGREE-DAY STATION WEIGHTS ARE HAND-SET, UNVALIDATED, AND MISS OHIO ENTIRELY

**Greg, S109:** *"Philly is a huge PJM load, as is Columbus where I live. DC, Baltimore, the whole I-95
corridor actually."* Checked against `STATION_WEIGHTS_RAW` and EIA-930, and there is a real coverage
hole.

**What the index actually contains** — 16 stations, hand-set raw weights summing to 0.890:

| region | stations | normalized weight |
|---|---|---|
| I-95 corridor | NYC .1348 · BOS .0562 · PHL .0562 · DCA .0562 | **0.3034** |
| Midwest | ORD .1124 · DTW .0562 · MSP .0506 · STL .0393 | 0.2585 |
| South/Texas | IAH .0787 · DFW .0730 · ATL .0618 | 0.2135 |
| West | LAX .0618 · PHX .0506 · SEA .0393 · DEN .0393 · SFO .0337 | 0.2247 |

**Absent, and they are not small:**

| metro | utility / zone | status |
|---|---|---|
| **Columbus OH** | AEP Ohio (PJM) | **ABSENT** |
| **Cleveland** | FirstEnergy (PJM) | **ABSENT** |
| **Cincinnati** | Duke Ohio (PJM) | **ABSENT** |
| **Baltimore** | BGE (PJM) — a separate metro from DCA | **ABSENT** |
| Pittsburgh | Duquesne (PJM) | **ABSENT** |
| Richmond | Dominion (PJM) | **ABSENT** |

**Ohio has NO station in the index at all.**

**The scale check (EIA-930, 20260629):** PJM is **18.3%** of US48 demand — **the largest single BA in
the country**, ahead of MISO 15.0% and ERCOT 13.0%. PJM-footprint stations in the index are PHL + DCA =
**11.2%** of weight (NYC is NYISO; BOS is ISO-NE).

**MY CAVEAT HERE WAS WRONG, IN BOTH DIRECTIONS — Greg, S109:** *"In the summer, electricity gen is 50%
of gas demand. We found that in EIA docs."*

I had hedged that electric load share is not gas-demand share because PJM "carries substantial nuclear
and coal." Both halves of that are wrong, and our own served data says so:

| BA | `gas_mwh` | share of US gas-fired gen | `gas_share` of own stack |
|---|---|---|---|
| **PJM** | 1,045,767 | **23.2%** | **0.4286** |
| MISO | 650,342 | 14.4% | 0.346 |
| ERCO | 503,267 | 11.2% | 0.3048 |
| SOCO | 393,197 | 8.7% | 0.5116 |
| SWPP | 190,641 | 4.2% | 0.2047 |
| CISO | 17,448 | 0.4% | 0.0411 |

**PJM's gas share is HIGHER than MISO's or ERCOT's, and PJM is the single largest gas-burning BA in the
country at 23.2% of national power-sector gas burn.** And the 50% figure is corroborated independently
by our own state: `grid_stack.est_gas_burn_bcfd` reads **34.4 Bcf/d** against a summer total US
consumption on the order of 70 Bcf/d — roughly 48%.

**THE REAL CONSEQUENCE IS BIGGER THAN A REWEIGHT: THE WEIGHTS MUST BE SEASONAL.**

- **Winter** — gas demand is dominated by residential/commercial **heating**. Population/heating-weighted
  metros are the right basis. The current table is a plausible shape for this season.
- **Summer** — **~50% of gas demand is power burn**. The right basis is **gas-fired generation by
  region**, not heating population. A metro's summer weight should track the gas burn of the BA it sits
  in, which is a completely different distribution: CISO is 4.8% of electric demand but **0.4%** of gas
  generation, while SOCO burns gas for 51% of its stack.

**A single static weight table cannot be correct in both seasons, and ours is static.** That is a
misspecification of the SLOPE instrument — the channel P0 just made the top build priority — in the
exact season G22 sits in, and the season where we just measured a missed hill of **−1,815**.

It also lands squarely on existing doctrine: the brain's **SEASONAL SALIENCE SLIDER** (S101, S1/S2/S3)
already says weather salience shifts by season. The degree-day index it reads has no such shift.

**The instrument for the summer half already exists and is served daily:** `grid_stack.bas[*].gas_mwh`
and `gas_share`, per BA, plus `est_gas_burn_bcfd`. No new feed is needed to build the summer weighting —
only the reconciliation and the seasonal switch.

**The coverage gap compounds it:** Ohio sits inside PJM, the largest gas-burning BA, and has no station
at all. In a summer block that is a hole in the heaviest power-burn region in the country.

**The deeper issue: `STATION_WEIGHTS_RAW` is a hand-set table with no recorded provenance and has never
been validated against actual gas consumption.** That is the same species as every other defect this
session — a plausible, well-formed, in-range set of numbers that nobody reconciled against an
independent source. It sits directly upstream of `gw_hdd` / `gw_cdd`, which is the **slope instrument**
P0 just made the top build priority. A mis-weighted slope channel biases every weather read in every
block, one direction, invisibly.

**PROPOSED AS A BUILD (measurement first, no weights invented):**

1. **SEASONAL WEIGHTS — the headline.** Two tables, not one. Winter keyed to heating consumption; summer
   keyed to **gas-fired generation by region**, since ~50% of summer gas demand is power burn. Blend
   through the shoulders rather than switching hard, consistent with the seasonal salience slider.
2. **Reconcile both against EIA state-level natural gas consumption** — residential + commercial +
   industrial + electric power, published by state and month. That is the independent source the table
   has never been checked against, and it decomposes by sector, which is exactly what the seasonal split
   needs.
3. **Build the summer table from data already on disk** — `grid_stack.bas[*].gas_mwh` / `gas_share` is
   served daily per BA. No new feed required for the summer half.
4. **Add the missing metros** — Ohio (Columbus/Cleveland/Cincinnati) and Baltimore — weighted from that
   reconciliation, not from judgement. Ohio sits in the largest gas-burning BA and has no station.
5. **Record the provenance in the feed.** Today the weights are bare literals with no derivation.
6. **Re-run the walked blocks on the corrected index** and measure whether the slope channel moves. G22
   is the natural test: it is a summer block, its actual cum (+470) is known, and the blind missed the
   hill by −1,815. If the corrected summer weighting steepens the hill, that is a direct measurement of
   what the misspecification was costing.

**Falsifier:** if the reconciled weights land within noise of the hand-set ones — and if the summer and
winter tables turn out similar — the table was fine and only the coverage gap needs filling. Either
outcome is a real result worth having, and both are cheap to test.

*The measurement below stands and explains the down lean. What changed under P0 is the remedy: the
answer is not to re-point these bars at CDD levels, it is that a LEVEL bar is the wrong instrument.
Retained here because the one-directional degradation is real and must still be neutralised.*

**Claim.** In a summer/CDD block the HDD-keyed play family is *unevaluable*, and every member degrades
**in the same direction — bearish or void**. Four independent artifacts push down at once; none is a
signal.

**The four, measured on G22** (realized gw_cdd ran 9.0 → 18.7; `forecast_gw_hdd` sat at 0.034–0.301):

| # | play / field | HDD bar | in July | degrades to |
|---|---|---|---|---|
| 1 | `selector.divergence_resolution` catalyst override | HDD ≥ 16.4 | unreachable | never fires → selector defaults to the S3-bearish angle |
| 2 | `magnitude.shoulder_weather_band_void` | HDD ≤ ~13.5 | trivially satisfied | **voids the weather band** on every summer day |
| 3 | `forecast_run_delta_cdd` across a seam | — | structurally blind (§P2) | reads ~0 against a +4.7 add |
| 4 | `weather_forecast_cycle.sunday_reopen` | HDD-only | +0.096 for 0629 | reads ~0 against the same +4.7 add |

**Forward evidence.** Specialist B named this mechanism in its 0629 posterior **before the block was
scored**. The scoreboard then showed: four days forecast down that printed up (0622, 0624, 0630, 0703),
contributing **−3,840** of signed error against a block drift of −1,815. Blind cum −1,345 vs actual
+470; blind ends 3.063 vs 3.245.

**This is the same shape as the S108 b_share defect**: a one-directional structural lean in which every
individual field is present, numeric, in range, and self-consistent.

**Proposed (additive, no incumbent rewritten):**

- **`weather.absolute_hdd_bar_unevaluable_in_cdd_regime`** — an absolute HDD bar that is unreachable in
  the block's regime returns **UNKNOWN**, never a satisfied/refuted boolean, and must not default a
  selector or void a band. `requires`: the block's realized or forecast CDD regime. `scope`: any play
  stating an absolute HDD threshold. **Falsifier**: a winter block where the same bars evaluate normally
  and the plays behave as measured — i.e. this play must be inert outside CDD regimes.
- **Re-point 1 and 2 to the now-served CDD ladder** (`forecast_gw_cdd`, `d_gw_cdd`, `fwd7_gw_cdd_span`).
  The summer-side thresholds are **NOT proposed here** — there is no measured summer authority threshold
  anywhere in the brain (16.4 is a winter instrument), and D named that gap independently as the main
  driver of its own low sign confidence. Inventing a summer bar now would be fitting. **Proposed as a
  build item, not a play.**

**Attribution discipline:** the CDD ladder is a DATA fix (§P4). Do not bank any G23 improvement as
evidence for a play when the input changed underneath it.

---

## P2 — SEAM DELTAS ARE STRUCTURALLY BLIND (general, high confidence)

**Claim.** A model *run* delta baselines run-over-run, not session-over-session. Across a weekend or
holiday seam spanning 4–8 cycles the accumulation appears in no single delta.

**Measured.** `forecast_run_delta_cdd` = −0.219 on 0629 against a **+4.7 level move**; the block's whole
run-delta series sits in a +1.05/−0.50 noise band while the level ran 10.08 → 14.82. Mechanism verified
rather than asserted: on 0624 the level moved +2.205 while the field read −0.011. Second independent
instance on a different field: `sunday_reopen` d_gw_hdd +0.096 for the same seam.

**Consequence.** E read the field correctly and got the sign backwards. Friday→Monday is the walk's
declared focus, so this touches the highest-value day class.

**Proposed:** **`weekend.seam_delta_requires_level_difference`** — across any weekend or holiday
boundary, difference the **LEVELS**; run deltas are intra-week instruments only. `forward_evidence`:
G22 0629, two independent fields. **Falsifier**: an intra-week day where the run delta and the level
difference agree (they should — the claim is scoped to seams).

*Data side already landed: `seam_delta_warning` is served in-band.*

---

## P3 — THE WEEKEND-GAP INSTRUMENT IS REFUTED IN SUMMER (n=1, strongest single result)

**Claim.** `magnitude.weekend_gap_delivery`'s fresh arm (+1500..+2500) is **winter-measured with no
summer instance**, and G22 supplies an n=1 **refutation**, not a calibration miss.

**The test, and why it is clean.** The bridge pre-committed to a mechanism, and the driver **arrived
exactly as forecast**:

| | forecast | realized |
|---|---|---|
| 0629 gw_cdd | 14.815 | **14.8** |
| 0630 gw_cdd | 16.194 | 15.7 |

| 0629 | forecast | actual |
|---|---|---|
| gap | **+480** | **+50** |
| session | −155 | **−1,160** |
| net | +325 | **−1,110** |

A large, correctly-forecast, correctly-**realized** weekend CDD add produced **five ticks of gap** and a
hard down session. A had already rescaled the winter band to +350..+800 on regime grounds and was still
~10× high on the gap.

**Both Mondays fail the gap in opposite directions:**

| Monday | forecast gap | actual gap | forecast session | actual session |
|---|---|---|---|---|
| 0622 | +20 | **+1,210** | −440 | −560 (**err 120**) |
| 0629 | +480 | **+50** | −155 | −1,160 |

B derived 0622's gap from reopen participation — *"a weekend that traded nothing repriced nothing"* —
and the 252-lot reopen preceded a +1,210 gap. So **reopen participation does not predict gap size
either**.

**Proposed (deliberately conservative):**

- **RETRACT the summer applicability** of `weekend_gap_delivery`'s fresh arm — scope it to winter
  explicitly, where its exemplars live. Do **not** propose a summer band; n=1 refutation licenses a
  scope restriction, not a new number.
- **`boundary.weekend_gap_is_not_forecastable_from_current_instruments`** (PROPOSED, n=2) — on this
  evidence the blind's weekend-gap read is uninformative in both directions, while its **session** read
  is sound (0622 session err 120). Suggests carrying weekend gaps as an explicit **wide band** rather
  than a point estimate, and scoring gap and session separately. **Falsifier**: a block where a
  pre-committed gap call lands inside ±300 on both Mondays.

**Do NOT merge as "the panel was too bullish."** That is the net-not-mechanism error this walk has
already paid for once.

---

## P4 — DATA BUILDS LANDED THIS SESSION (not brain changes; listed for attribution hygiene)

1. **CDD forward ladder served** — `forecast_gw_cdd`, `d_gw_cdd`, `fwd7_gw_cdd_span` on `horizons` /
   `run_delta`. The feed always computed them; assembly dropped them, exactly as S107 dropped
   `big_print_b_share`. Additive: fitted HDD bars read exactly what they read before.
2. **`sunday_reopen` carries CDD** — `gw_cdd_d0` and `d_gw_cdd`.
3. **`seam_delta_warning`** and **`ladder_basis_note`** served in-band.
4. **`forward_stamps()` wired into `build_causal_slices.build()`** — it existed but was never called, so
   C's catch (a `consensus_pre_print_snapshot_utc` stamped 2026-07-02 under the 0629, 0630 and 0701
   blocks) would have stayed invisible. Reported, never fatal.
5. **Anchor block** carries `direction_caveat` / `close_in_range` / `net_ticks` and the reconstruction
   basis (auditor f14).

**Standing attribution rule:** these changed the INPUTS. Any G23 improvement must not be banked as
evidence for a play.

---

## STILL OPEN — NOT PROPOSED, NEEDS A DECISION OR A BUILD

| item | why it is not a proposal |
|---|---|
| `storage_consensus` post-print look-ahead (auditor f2) | a DATA fix needing the source feed; on 0625 it destroys ~78% of decision-time surprise. Specialists are currently working around it correctly, which is not a substitute for fixing it. |
| No measured **summer** authority threshold | genuine build gap; naming a number now would be fitting. D and B both hit it independently. |
| `flow.resting_program_inverts_aggressor_tilt` never fires on `is_expiry_day` | proposed by the clean bridge with a price-free discriminator; wants a second instance before merge. |
| `options_surface` 10× strike scale (auditor f6) | data fix; 0 of 67 plays read it, so it costs specialist budget, not signal. |
| Session **close time in ET** absent on shortened sessions | A had to assume ~13:00 on 0703. `cme_early_close: false` on a `partial_session` should be a hard `state_health` failure. |
| Phase boundaries carry no clock mapping | binds hardest on EIA days — D cannot anchor a mechanism to the 10:30 print, which is why its timing claims are testable only in post-mortem. |

---

## P0.6 — COAL HEADROOM IS THE SUPPLY-SIDE TWIN OF THE MULTIPLIER (and we measure the wrong quantity)

**Greg, S109:** *"Coal is almost all the way out of the gen cap in the US. Look back in the handoffs for
our discussions on this because we talked about a lot of stuff with this."*

**The prior thread, recovered:**
- **S97 item 10** — "Cross-market: power prices (gas sets marginal power price), **coal-switching
  economics**, TTF/JKM. Real drivers, slower-moving. **Lowest priority** of the list."
- **S98 DATA_GATE** — "Cross-market (TTF/JKM, power stack, coal switch) — S97 item 10 … **Post-gate.**"
- **S98, Greg 2026-07-20** — "COAL + GAS PLANT maintenance: per-unit schedules are mostly confidential;
  the free quantified source is the ISOs' **AGGREGATE outage reports** … **EIA-860M monthly status = the
  slow layer.** Trade relevance both ways: **coal unit down pushes burn TOWARD gas**, gas unit down
  pulls it away." Queued as arm 4 — **never built**.

**What our served data actually shows** (`grid_stack`, 20260629, and across G22):

| BA | coal share of gen | gas:coal |
|---|---|---|
| CISO | **0.000** | no coal |
| ERCO | 0.120 | 2.5× |
| PJM | 0.165 | 2.6× |
| SOCO | 0.199 | 2.6× |
| SWPP | 0.210 | 1.0× |
| MISO | **0.272** | **1.3×** |
| US48 | **0.161** | 2.3× |

US48 coal share across the block runs 0.149 → 0.170 — **not declining within the window**.

**So state it precisely, because generation is not capacity.** Coal is ~16% of US *generation* here, which
is not "almost out" — but that measures the wrong thing, and the two diverge exactly when a fleet is
retiring: capacity falls fast while the survivors run harder. **The trade-relevant quantity is neither
share nor capacity — it is MARGINAL SWITCHING HEADROOM**, i.e. whether coal can actually absorb a demand
shock. A 16% share that is baseload, must-run, or economically committed provides no buffer, and coal
units cycle slowly. **We cannot answer that question with anything we serve.** We have fuel GENERATION
and no fuel AVAILABILITY.

**WHY IT BELONGS IN P0 AND NOT IN "cross-market, lowest priority."** Coal headroom is the **supply-side
twin of the weather multiplier**. The demand side asks *how much load does the weather create*; the
supply side asks *is there anything to absorb it*. If coal cannot step in, a summer heat event passes
straight into gas burn with nothing damping it — a **steeper slope and a larger multiplier**. If MISO
genuinely retains headroom at 27% coal, the same heat is partly absorbed there. **This is regional, and
it multiplies against the seasonal power-burn weighting proposed in P0.5** — the two are the same
calculation seen from opposite sides.

The S97/S98 deprioritisation was right about the *mechanism it named* — classic gas-to-coal **price**
switching is a slow, fading arbitrage. It undervalued the *structural consequence*: the disappearance of
that buffer is precisely what makes weather translate more directly into price, which is the model Greg
has now stated.

**PROPOSED AS A BUILD (unblocks the supply side of the multiplier):**

1. **EIA-860M capacity + retirement status** — the "slow layer" named in S98 and never built. Gives
   installed coal capacity by region and the retirement schedule, so headroom is computable rather than
   inferred from generation share.
2. **ISO aggregate outage reports (arm 4)** — Greg's own 2026-07-20 spec, already scoped: planned +
   forced MW, per-fuel where offered, coverage named per ISO and never assumed uniform. This is the
   *availability* half.
3. **Derive a per-region `coal_headroom` / switching-buffer field** and serve it beside `gas_share`. The
   forecaster should be able to see, on the day, whether a heat shock has anywhere to go.
4. **Do NOT build classic coal-switch price economics.** The prior calls were right on that. What is
   wanted is the *headroom*, not the arbitrage.

**Falsifier:** if per-region coal headroom turns out to be uncorrelated with the realized weather→burn
transmission across the walked blocks, the buffer is not the mechanism and this drops back to
post-gate. Testable on data we would then have.
