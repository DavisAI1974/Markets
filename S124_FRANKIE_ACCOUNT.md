# S124 - FRANKIE'S OWN ACCOUNT OF THE FOUR BLIND DAYS

Branch `claude/frankie-temp-s124`. Namespace `claude_s124_g17g18_01`. Blind artifacts were frozen
and committed at `7422bcd` BEFORE any actual was opened; the outcome lines below were added after.

**This is the forecaster's own text, quoted verbatim from the frozen artifacts.** Nothing here is a
refine - RFN-1 never ran (blocker at the end). Nothing here is averaged, pooled or summarised
across days: **each day is its own instance** (D4/D37). There is deliberately no hit-rate, no mean
error and no aggregate score in this document.

Reading order that matters: the CALL, then why, then what it fired, then what it refused and why,
then what it says it did not have. The last section is the one that turns into work.

---

## 20260427 - Mon, specialist B

| | |
|---|---|
| called | **-730 USD** (net -550 / gap -180) |
| actual | **+370 USD** (net +420 / gap -50) |
| absolute error | **1100** |
| size called | **197%** of the realized move |
| direction | **WRONG SIGN** |
| disposition / confidence | CALL / low |
| path emitted | 12 self-chosen points |
| artifact | `research/kalshi/forecasts/claude_s124_g17g18_01/grp18_B_20260427.json` |

### Why it called that - verbatim

> No inbound bridge from A this run (A did not spawn), so I own the Monday number unaided from the D-1 (Friday 20260424) tape and open-conditions state alone. FUNDAMENTAL BACKDROP: near-window forecast HDD is very low (D0 5.885 gw, D0..D+3 max 9.191 gw), well under both selector.divergence_resolution's 16.4 gate and magnitude.shoulder_weather_band_void's 13.5 void threshold -> the weather-cold-add UP angle cannot win; default to the S3-bearish DOWN angle, weather delivery band VOID, fall through to the residual/fundamental co-condition. storage_regional shows a materially building surplus (L48 vs_5yr +111.8 Bcf, weekly_chg +103), consistent with early-injection-season bearish trajectory. WEATHER REVISION READ: the weekend cycle CUT HDD across nearly every horizon vs the prior evening run (D0 -0.334 to D+4 -0.941, one small D+5 add +0.433), and the Monday weekday_open cycle cut D0 further (-0.862) -- persistent warm-cut revisions, not a first-appearance shock (all deltas well under the ~3-4 gw shock-scale bar in timing.catalyst_continuity_frontrun / magnitude.unpriced_shot_extension), so I read this as a MODERATE/PRICED revision, not a fresh-shot event. POSITIONING: managed-money net is at the 8.49th 1y percentile (crowded short) but chg_wow is +13,521, i.e. IMPROVING/covering, not worsening -- boundary.seam_gap_up_prior_on_worsening_cot's arming gate (WoW<0) is NOT satisfied, so I did not license an up-gap prior off the crowded-short read; treated as a spent/already-covering signature rather than a live squeeze trigger. squeeze_watch.active is false and unwind_watch is false despite the front (NGK26) expiring in 1 session and today being opex -- no squeeze regime is live, so squeeze doctrine does not override the fundamental lean. TAPE: Friday's (D-1) session showed net BUY flow (session_signed_flow +3,189, phase-3 flow +3,171, big_print_b_share 0.593 on a guard-clean 91-print sample) despite a sub-0.50 raw session_b_share (0.453). Per tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell, the D-1 form of this instrument is explicitly refuted as a next-day signal (measured coin-flip, 4/9) -- I deliberately did NOT read Friday's buy flow as bullish confirmation for Monday. The raw sub-0.50 session_b_share is read with the known S108 basis caveat (no two-sided series served this slice) but was still used, per magnitude.s1void_injection_chain_bleed, to arm a chain-sided-down TREND read (Monday carry, non-coil) rather than damping to a stub. SIZING: given only a moderate (not shock-scale) weather revision, a spent rather than fresh positioning trigger, and no squeeze/flip confirmation available, I sized toward the lower-middle of the S1-void trend band (-450..-780) rather than its top, landing total day-move -550 (gap -180 in the priced/moderate weekend_gap_delivery class, session -370). PATH: overnight/Asia-Europe drift is thin and mildly bearish (Friday's late buy flow fading rather than continuing, consistent with the D-1 tape being a null next-day signal); the bulk of the move is delivered in the 06-10 ET Monday catch-up window as the further Monday-morning weather cut and the building-surplus backdrop get priced by returning desks (per my own Monday-specialist lens: the catch-up window is where Monday decides, not the overnight drift); the afternoon flattens into the 14:00-14:30 settle window and holds into the 17:00 close.

### Plays it FIRED (7)

- `magnitude.s1void_injection_chain_bleed`
- `weather.shoulder_weather_band_void / magnitude.shoulder_weather_band_void`
- `selector.divergence_resolution`
- `monday.overnight_headfake_into_catchup`
- `tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell`
- `boundary.seam_gap_up_prior_on_worsening_cot`
- `magnitude.weekend_gap_delivery`

### Plays it STOOD DOWN (7) - with its stated reason

- timing.catalyst_continuity_frontrun (EIA print 3 sessions out; weather is being cut, not building -- no live ramp to front-run)
- structure.squeeze_unwind / squeeze-regime plays (squeeze_watch.active false, unwind_watch false despite front expiring T+1 and today being opex)
- positioning.covering_self_limiting_cot_wow_gate (WoW improving but not extreme enough either way to force a directional covering-spent claim; carried as context only)
- magnitude.block_gap_ownership (cum_from_anchor / chain age are price-derived and masked; structural/weather/chain-drift ownership rungs unevaluable this slice)
- structure.chain_polarity_flip (no realized D-1 price tape or handoff available to evaluate C1 band-break / C2 continuation-collapse)
- monday.window_deep_book_shakeout (needs a live 06:00 ET L1-10 book snapshot; not served)
- weather.freeze_conjunction_class2 / weather.hydro_winter_buffer (April shoulder session, zero freeze-risk readings in any basin)

### What it says it did NOT have (6)

- storage (national weekly) block is null this slice; only storage_regional (as of 2026-04-17) and storage_consensus (survey) were available and used as the surplus proxy instead.
- vol_regime is fully masked/null this slice (masked_one_shot=true, value null) -- no sigma reference available for magnitude sizing; sized off condition-class bands instead of a measured vol scale.
- weather (realized) block is null; only weather_forecast / weather_forecast_cycle (MOS forecast) fields were available and used in its place.
- No specialist-A bridge read was produced for this Monday (A did not run) -- owned the Monday number unaided per the run directive.
- model_disagreement horizons 2-7 show zero coverage (spread null, not zero -- beyond both models' reach); only h0/h1 were usable for the disagreement read.
- tape_conditions.session_b_share is served only on the known S108-biased single-sided basis (no two-sided series in this slice); read with that caveat rather than treated as a clean 50/50 bar.

---

## 20260428 - Tue, specialist C

| | |
|---|---|
| called | **-350 USD** (net -300 / gap -50) |
| actual | **-440 USD** (net -440 / gap +0) |
| absolute error | **90** |
| size called | **80%** of the realized move |
| direction | **HIT** |
| disposition / confidence | CALL / low |
| path emitted | 12 self-chosen points |
| artifact | `research/kalshi/forecasts/claude_s124_g17g18_01/grp18_C_20260428.json` |

### Why it called that - verbatim

> Core Tue day, S1-void shoulder regime (D0 forecast_gw_hdd 6.739, forecast_vs_normal +0.68, mod_cool; near-window HDD far below the ~16-20gw band-authority thresholds), so weather cannot own the day and the default falls to the S3 storage-trajectory lean (selector.divergence_resolution gate (a) unreachable at this HDD level; treated as weak/structural context per weather.absolute_hdd_bar_unevaluable_in_cdd_regime doctrine, not a hard bearish trigger on its own). D-1 (Mon 4/27) tape_conditions is the strongest legitimate never-masked signal available: session_signed_flow -3950 (net sell), session_b_share 0.419, and phase_b_share declining through the session (0.478->0.422->0.405) with the heaviest selling in the middle/late phases (phase_signed_flow 254/-3299/-905) - a chain-sided sell tape, not a coil/near-neutral D-1. Under magnitude.s1void_injection_chain_bleed this argues for a TREND-class session (not the shallower coil band), so I size toward the lower-middle of the -450..-780 trend band rather than damping to a stub, while discounting because multi-day chain age/polarity cannot be confirmed blind (cum_from_anchor is masked) - treated as a soft lean, not a hard commitment. COT: managed_money_net_pctile_1y 8.49 (crowded short) but chg_wow +13521 (IMPROVING, i.e. covering already happened last week) - positioning.covering_self_limiting_cot_wow_gate limb (b) is satisfied (flat/improving), and D-1's aligned-selling-under-declining-price shape plausibly satisfies limb (a) too, so I read the crowded short as SPENT/self-limiting rather than live fuel for a squeeze bounce - this damps any covering-driven upside expectation and reinforces a modest-not-extreme bearish lean rather than a violent one. structure.accumulation_arm_turn does NOT fire: D-1 big_print_b_share 0.42 is well below the 0.55 recurrence bar, and the COT WoW is improving not worsening, so no buy-absorption turn signature - default S3-down stays uncontested by that arm. magnitude.positioning_saturation_turn's percentile limbs are both technically satisfied (NYMEX 8.49<=12, ICE LD1 0.94<=3) but its trigger requires a weekend/block-opening gap, which does not exist on a plain Tuesday - stood down on scope. Today is NGK26 (May, calendar-front) expiry (flow_calendar.is_expiry_day=true, days_to_futures_expiry=0), but the scored/traded leg is the deferred volume/OI front (NGN26, July) - the same configuration as the G22 0626 NGN26-expiry-on-deferred-NGQ26 precedent. squeeze_watch is frozen at the 4/24 anchor vintage (masked_one_shot) and shows active=false, unwind_watch=false, no widening front-next spread - no stranded premium evident, so I do not expect a dead-sponsor unwind or a covering-into-settle rally to drive the scored leg; expiry mechanics treated as Descriptor-grade context only. No storage catalyst today (print is 2 sessions out, Thu 4/30); no freeze risk anywhere (all basin thresholds 0 days-below); grid_stack day-over-day shows wind up (+65k MWh) and solar down (-52k MWh) with gas down (-127k MWh) - a mild renewables-displacing-gas signal, but too small relative to the already-low HDD to be decisive, so treated as context not a fired play. All price-derived chain/R1/R4/R5/flip machinery is unevaluable blind (cum_from_anchor, last_hour_dir/flow, close-off-extreme all masked). Net read: a quiet, catalyst-light S1-void Tuesday inheriting continued D-1 sell-tape momentum into the reopen and main session, damped by a self-limiting (not live) COT-covering read and by weak confirmation of chain age - small overnight continuation, session weight concentrated in the 08:00-14:00 ET window, modest total move, low confidence given how many plays stood down for lack of price/chain confirmation.

### Plays it FIRED (3)

- `magnitude.s1void_injection_chain_bleed`
- `positioning.covering_self_limiting_cot_wow_gate`
- `selector.divergence_resolution`

### Plays it STOOD DOWN (11) - with its stated reason

- structure.accumulation_arm_turn
- magnitude.positioning_saturation_turn
- tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell
- timing.catalyst_continuity_frontrun
- structure.covering_absorption_directional_tell
- boundary.prior_close_flow_direction_disagreement
- weather.renewables_masking_flip
- structure.mature_swing_alternation
- structure.squeeze_unwind
- daytype.storage_thursday_magnitude
- daytype.weekday_archetype

### What it says it did NOT have (5)

- contract_structure/options_surface/vol_regime/cash_basis/squeeze_watch are all frozen at the 2026-04-24 anchor vintage (masked_one_shot) while flow_calendar (live/deterministic) shows today IS the calendar-front (NGK26) futures expiry day - the frozen structural fields cannot confirm live spread/stranded-premium state on the actual expiry session itself, a real gap for evaluating structure.squeeze_unwind / block_gap_ownership's dead-sponsor arm today.
- vol_regime.value is null - no sigma/range benchmark available for magnitude calibration on this day.
- top-level `storage` and `weather` blocks are null; only storage_consensus, storage_regional (stale, period ending 2026-04-17), and weather_forecast (D-1-evening MOS) are populated - consistent with the mask design but named for completeness.
- ngwu_balance level fields (dry_production, LNG feedgas, industrial, power, rescomm, etc.) are null/stale since week_ending 2025-09-24 (216+ days) - LNG/production context is limited to the vessel-departure proxy (35 vessels, 134 Bcf capacity, unchanged vs D-1).
- model_disagreement and weather_forecast_cycle.stability horizons beyond h0/h1 are all zero-coverage (null), consistent with the known MAV(~72h)/MET(~84h)/NAM/GFS reach limits - only the near-term two days are usable.

---

## 20260429 - Wed, specialist C

| | |
|---|---|
| called | **-400 USD** (net -350 / gap -50) |
| actual | **-440 USD** (net -440 / gap +0) |
| absolute error | **40** |
| size called | **91%** of the realized move |
| direction | **HIT** |
| disposition / confidence | CALL / low |
| path emitted | 14 self-chosen points |
| artifact | `research/kalshi/forecasts/claude_s124_g17g18_01/grp18_C_20260429.json` |

### Why it called that - verbatim

> Day class: Wednesday core session (specialist C territory), no weekend/holiday seam, no EIA print today (print is tomorrow 2026-04-30, days_to_next_eia_release=1, inside the 1-3 session catalyst-front-run window but with NO live continuous weather ramp - forecast_run_delta on the HDD axis oscillates sign across horizons rather than trending monotonically, so timing.catalyst_continuity_frontrun's ramp-live arm does not arm; per that play the resume/turn WAITS for the discrete catalyst rather than front-running it, so today's move is read as tape/positioning-driven, not print-anticipation-driven. Regime: near-window max forecast_gw_hdd (fwd7 span [5.185, 11.463]) never clears the 16.4 gw-HDD authority bar, so selector.divergence_resolution's weather-up gate is unreachable and the play defaults to the S3-bearish storage-trajectory angle - consistent with the storage backdrop: storage_regional (as-of 2026-04-23) shows L48 vs_5yr +111.8 Bcf (wide, building surplus), weekly_chg +103, and tomorrow's consensus is another +80 Bcf build (house_disagreement only 3 Bcf, low dispersion) after last week's print already surprised bearish (+103 actual vs +94 consensus, +9 surprise). This is a confirmed S1-void injection-season backdrop (near-window HDD well under 20 gw): weather-trajectory authority is void for gaps/day-sides, ownership passes to storage-trajectory + positioning. Tape: flow.price_free_absorption_proxy's precondition is satisfied on D-1 (2026-04-28) - aggregate session_signed_flow +342 (positive, barely) on a guard-clean sample (big_prints_n=85, well above the ~20 thin-tape floor) - and the big_print_b_share on that session reads 0.318, inside the play's tail-sell class (<=0.47): 'big prints still selling = absorber present, take the turn small.' This is corroborated by the phase-level flow shape the same day: phase_signed_flow [71, 1055, -784] - a flat morning, a midday buy push (+1055), then a sell-driven fade into the close (-784), netting only +342. That is a faded-rally / distribution shape at the session-flow grain (the only grain available blind - direction.absorption_is_reversal and structure.covering_absorption_directional_tell both need realized phase flow-vs-price conviction, which requires price and is masked, so both are stood down rather than proxied). COT: managed_money_net pctile_1y 8.49 / pctile_3y 13.69 is a genuinely crowded short, but chg_wow is +13,521 (IMPROVING/covering), not worsening - so structure.accumulation_arm_turn's COT limb (extreme AND worsening) fails, and its buy-absorption limb also fails (only 1 of the last 3 sessions, 2026-04-24 at 0.593, clears the >=0.55 bar; the play needs >=2 of the last ~5 non-consecutive). selector.midblock_right_the_ship inherits the same failure - no turn stack is building, so the block default (S3-down) is not unlocked. magnitude.s1void_injection_chain_bleed's sell-tape limb is satisfied (D-1 session_b_share 0.471 < 0.50) but I cannot confirm the chain-sided-down precondition blind (chain age/polarity requires day-N-1 realized cum, which is masked), so I decline to claim its trend band (-450..-780) outright and instead size below it, consistent with the honest-under-claim discipline - if a mature down-chain IS running my -300 session estimate is conservative relative to that band, not contradicting it. magnitude.catalyst_condition_sort classifies today as non-catalyst core chop (no weekend gap, no storage Thursday, no swing-reversal seam), which caps magnitude at the small end rather than the up-sized catalyst classes. No armed parabolic swing or confirm signature is visible (structure.chain_polarity_flip, structure.failed_rally_tell, structure.mature_swing_alternation all stand down for want of realized chain state/day-N-1 tape). tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell is a same-day-only instrument and cannot be evaluated pre-open. Net read: modest bearish-to-flat grind, tape-driven (unabsorbed large-size selling into the prior close) inside a bearish storage-trajectory backdrop, with COT covering acting as a mild brake against sizing this larger (per doctrine, positioning is a convexity conditioner, never a timing/direction driver, and no squeeze regime is active - squeeze_watch.active=false). No weekend/holiday seam exists (ordinary Tue->Wed transition), so the overnight gap is sized small and same-signed as the session read rather than treated as a separate information event. Path drawn as a continuous grind-down (a hill slopes, it does not gap): flat overnight, building through the US morning as the unabsorbed sell pressure reasserts, flattening into the settle window rather than a violent one-shot move, consistent with a session-flow-shape read rather than a catalyst-driven spike.

### Plays it FIRED (4)

- `flow.price_free_absorption_proxy`
- `selector.divergence_resolution`
- `magnitude.catalyst_condition_sort`
- `timing.catalyst_continuity_frontrun`

### Plays it STOOD DOWN (12) - with its stated reason

- structure.accumulation_arm_turn
- selector.midblock_right_the_ship
- tape.heavy_buy_aggression_is_the_asymmetric_bearish_tell
- direction.absorption_is_reversal
- structure.covering_absorption_directional_tell
- structure.chain_polarity_flip
- magnitude.block_gap_ownership
- magnitude.s1void_injection_chain_bleed
- daytype.storage_thursday_magnitude
- daytype.eia_preprint_overextension_gate
- structure.mature_swing_alternation
- structure.failed_rally_tell

### What it says it did NOT have (5)

- vol_regime is masked_one_shot with value null on all three days in my slice (2026-04-27/28/29) - no sigma/range basis is available to calibrate magnitude against, so the -350 estimate is derived from tape/fundamental reads alone, not cross-checked against a vol band.
- The top-level `storage` block is null on every day; only storage_consensus, storage_regional (as-of 2026-04-23) and storage_vintage (55 days stale, as-of 2026-03-05) are served. storage_vintage's staleness means the as-printed/current-vintage reconciliation this desk normally relies on is unavailable for the live period - I fell back to storage_regional + storage_consensus.
- stor_surprise and stor_surprise_sign are null on all three days; the seasonal-proxy surprise metric is unpopulated. I substituted storage_consensus.last_print.surprise_vs_consensus_bcf (+9.0) as the decision-legit equivalent.
- No session_b_share_two_sided field is served anywhere in tape_conditions on any of my three days - per the b_share_basis_rule doctrine, the ~0.47/0.50 bars in flow.price_free_absorption_proxy and magnitude.s1void_injection_chain_bleed were read on the raw (single-sided) series, which is known to run biased low versus a hypothetical two-sided series; I flag this rather than silently trusting the raw read.
- model_disagreement horizons 2-7 are null (no MAV/MET overlap beyond D+1) on all three days - expected per the model-reach doctrine, but it means the weather-authority channel is effectively unusable past tomorrow, reinforcing why I did not lean on any forward weather read.

---

## 20260430 - Thu, specialist D

| | |
|---|---|
| called | **+450 USD** (net +400 / gap +50) |
| actual | **+1230 USD** (net +1230 / gap +0) |
| absolute error | **780** |
| size called | **37%** of the realized move |
| direction | **HIT** |
| disposition / confidence | CALL / low |
| path emitted | 18 self-chosen points |
| artifact | `research/kalshi/forecasts/claude_s124_g17g18_01/grp18_D_20260430.json` |

### Why it called that - verbatim

> Thursday EIA storage-print day (print 10:30 ET, for week ending 2026-04-24, consensus +80 Bcf build, house_disagreement only 3 Bcf, days_to_print=0). Per lens doctrine (D), SIDE on a storage Thursday comes from the running chain/swing state, never from the unknown print surprise sign; the print delivers magnitude, chain delivers direction. (1) PRE-PRINT OVER-EXTENSION GATE (daytype.eia_preprint_overextension_gate): checked all three tells against the never-masked tape_conditions across the block's four served days. (a) Over-extended same-side chain into the print (>=~$900 cum run): flow direction alternates day to day (Fri 04/24 buy +3189 -> Mon 04/27 sell -3950 -> Tue 04/28 mixed/incoherent +342 with big_print_b_share only 0.318 -> Wed 04/29 strong coherent buy +7783) -- no sustained same-side run, tell NOT met. (b) Incoherent D-1 (Wed 04/29) flow: session_b_share 0.520 and big_print_b_share 0.621 both point the same (buy) way, and phase_signed_flow [53, 3644, 4086] accelerates into the close -- coherent, tell NOT met. (c) Surprise already priced >=1 week: unassessable blind for the NEXT print's own surprise (it hasn't printed yet) -- not counted as firing. 0 of 3 tells clear the >=2 bar, so the gate does NOT force a two-sided/damped call; per the lens file's own '0423 hit' precedent, coherent D-1 flow earns the FULL BAND chain-sided call. (2) CHAIN SIDE = UP, taken from Wednesday's flow (coherent, accelerating buy into the close) rather than from any print-sign guess. (3) flow.price_free_absorption_proxy: precondition met (D-1 aggregate session flow positive +7783, guard-clean sample big_prints_n=116>=20 so flow.big_print_bshare_thin_tape_guard's standard 0.55 bar applies, not the raised thin-tape bar). big_print_b_share 0.621 clears the play's own decisive-buy threshold (>=0.58) -> reads 'absorber gone / accumulation confirmed', a second independent confirmation of the UP lean (play status PROPOSED, so weighted moderately, not decisively). (4) magnitude.shoulder_weather_band_void: near-window (D0..D+3) max forecast_gw_hdd = 10.253 (D+2), well under the 13.5 gw threshold -> the weather band is VOID for day-lean/magnitude authority despite the above-normal cold read (forecast_vs_normal +2.954 at D0). Weather is carried as CONTEXT ONLY, not as a magnitude driver, consistent with April shoulder-season doctrine. (5) selector.divergence_resolution's mechanical form defaults to S3-bearish-DOWN when its HDD>=16.4 up-gate is unreached; per the brain's own DEGENERATE finding on this play (the gate is essentially unreachable in shoulder blocks), this un-fired default is explicitly NOT read as evidence for DOWN and is stood down rather than banked. (6) Fundamental/burn context: US48 est_gas_burn_bcfd rose 29.6->31.3 Bcf/d day-over-day while wind_mwh fell ~17% (1,747,896->1,449,408) and solar also declined -- renewables falling onto a regulating-gas stack is a mild bullish confirmation, consistent with the flow read, though it is a lagged (period+2) EIA-930 read and not fresh for today specifically. Nuclear outages ~19.5-20 GW (~20% of fleet) offline, spring refuel season, essentially flat day-over-day -- background bullish tilt, no fresh delta. (7) Positioning: COT (report 2026-04-21, published Fri 2026-04-24, unchanged/stale across the whole block by construction) shows a crowded short at the 8.5th 1y-percentile with a positive (improving/covering) WoW delta of +13,521 contracts. This is weekly-cadence context supporting some short-covering tailwind but is not a fresh same-day signal and cannot be scored as a fired directional play (positioning.covering_self_limiting_cot_wow_gate's 'spent' criteria are unverifiable blind); carried as a mild tailwind only. (8) squeeze_watch inactive (active=false, unwind_watch=false, sessions_since_prompt_expiry=19, well past the ~3-session dead-sponsor window) -- no structural/squeeze overlay. No expiry/opex/roll flow live today (days_to_futures_expiry=18, in_gsci_roll/in_bcom_roll both false). Given the modest, non-extreme conjunction of signals (coherent-but-not-extended flow, a mild positive accumulation tell, voided weather, background positioning tailwind, tight print consensus with small house disagreement limiting surprise-driven volatility), I size the day honestly under the emission ceiling rather than fitting to any single instrument: a small continuation-style overnight gap (no fresh overnight weather shock, weekday_open HDD delta only +0.053), a mild pre-print drift up, a moderate chain-sided delivery leg at the 10:30 print, and modest digestion into the close. Curve is continuous from the 20:00 reopen (cum=0) through the 17:00 close (cum=350=day-move 400 minus gap 50), with the discontinuity confined to the gap and the print window carrying the largest single repricing consistent with 'a hill slopes, it does not gap' outside the print itself.

### Plays it FIRED (5)

- `daytype.eia_preprint_overextension_gate`
- `daytype.storage_thursday_magnitude`
- `magnitude.shoulder_weather_band_void`
- `flow.price_free_absorption_proxy`
- `flow.big_print_bshare_thin_tape_guard`

### Plays it STOOD DOWN (9) - with its stated reason

- selector.divergence_resolution (HDD>=16.4 up-gate unreached; its mechanical default-DOWN explicitly NOT read as evidence, per its own DEGENERATE finding)
- weather.absolute_hdd_bar_unevaluable_in_cdd_regime (N/A -- HDD-dominant regime today, not CDD)
- structure.chain_polarity_flip (no parabolic arm / no confirm signature present)
- structure.squeeze_unwind / squeeze_watch overlay (inactive; 19 sessions since last prompt expiry, well past the ~3-session window)
- structure.covering_absorption_directional_tell (out of scope -- Friday/weekend-seam play, not applicable to a Thursday)
- weather.winter_heating_size_term (out of scope -- Nov-Mar only)
- daytype.friday_*/monday.*/weekend.* toolbag plays (out of scope -- not a Friday/Monday/weekend day)
- positioning.covering_self_limiting_cot_wow_gate ('spent' criteria unverifiable blind; COT is weekly-stale context, not fired as a decisive play)
- all needs_intraday_reveal plays (direction.flow_nowcast, shape.grind_vs_spike, ride.magnitude_staircase, magnitude.crash_regime_bands, exit.recruitment_reversal, direction.book_contrarian, timing.subsecond_reversal_exhaustion) -- unevaluable under the price mask

### What it says it did NOT have (4)

- vol_regime is masked_one_shot/null for every day in this packet -- expected under the blind protocol, but it removes any sigma-based reference for sizing the day's magnitude band, which materially widens the honest uncertainty on the emitted number.
- grid_stack (EIA-930 generation/burn stack) is served at period+2 lag with no forward wind/solar expectation anywhere in the packet -- the renewables-falling/burn-rising read used above is a backward-looking (2-day-lagged) fact, not a forecast for Thursday itself, and cannot be extrapolated with confidence.
- the daily 'weather' (realized) and 'storage' (daily print) fields are null on every served day -- consistent with expected blind masking / the print not yet having occurred (days_to_print=0 today), not flagged as anomalous, but noted for completeness.
- model_disagreement.disagreement rows for horizon>=2 all carry coverage=0.0 (no MAV/MET overlap beyond ~D+1), limiting the weather stability read past tomorrow -- not decision-critical here since the weather band is already void, but named as a standing coverage gap.

---

## The refine that did not run, and why

RFN-1 was attempted on exactly these four frozen days and **failed before any model call**, so
nothing was spent and no posterior exists:

```
STOP - ForecastStop: spawn RFN-1 g18 20260427 failed:
STOP - template RFN-1 needs slots that did not resolve: DIRECTIVE
```

`spawn.py:583-584` is explicit that this is not a lookup failure to be patched around:
*"DIRECTIVE is an INPUT, not a lookup - the SOP requires the run directive"*. A refine directive is
written by the coordinator for the run; inventing one here would repeat NC-1 (S110), where a
directive carried a false calendar premise into a refine and a specialist had to catch it.

So the refine is **blocked on a human/coordinator input, not on a defect**. The operator has
stopped this run to make changes; the four blind artifacts above are frozen and remain valid
evidence whenever RFN-1 is run against them.

## One contamination note the next operator needs

The actuals in this document were opened to score these four days. **That contaminates this
reasoner for the six remaining g18 blind days** (20260501, 20260504, 20260505, 20260506, 20260507,
20260508). Those must be run from a fresh context, not from this session.
