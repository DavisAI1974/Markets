# NG BEHAVIOR — living knowledge base (grows every pass)

**Purpose (Greg S92):** the accumulating, self-growing understanding of WHY natural gas behaves the way it
does — general causal mechanisms + discovered empirical patterns. Every discovery pass APPENDS and REFINES
here; nothing is a one-shot. Each entry is tagged with its status and evidence base so knowledge compounds
honestly as data grows (12 warm-season days -> full clean year -> forward-live). **Never average away the
per-event fingerprint** — extreme rates are LEADS, individual events pinpoint the WHEN.

Status tags: **[STABLE]** held across many events/regimes · **[PROVISIONAL]** real but thin/one-regime ·
**[HYPOTHESIS]** a lead, n small, not sized · **[OPEN]** known unknown, unsolved · **[MECHANISM]** causal
structure (why), not yet an empirical measure.

---

## A. GENERAL CAUSAL STRUCTURE (why NG moves — the market's clock and drivers)
- **[MECHANISM] Weekly EIA storage print, Thursday 10:30 ET** is the one scheduled catalyst — the biggest
  recurring decision point of the NG week. Empirically the busiest hour on Thursdays.
- **[MECHANISM] US-session liquidity concentration (~08–16 ET).** The day's real range is decided in the US
  session; overnight (Globex) is thin drift. [STABLE across the 12 days: every big leg landed 12–16 UTC.]
- **[MECHANISM] Weekend information gap -> Monday is distinct.** News/weather/supply accumulate over the
  closed weekend and reprice at the Sunday-evening reopen -> Monday shape differs from mid-week. [OPEN — all
  Mondays in the corpus were corrupt stubs; re-downloading; Monday shape UNCHARACTERIZED yet.]
- **[MECHANISM] Seasonal demand regime.** Summer = cooling/power-burn demand (weather-led); winter =
  heating (bigger swings, withdrawal season). The learn window is warm-season only -> winter behavior
  unknown. [OPEN until the full-year tape.]
- **[MECHANISM] Storage cycle** (injection spring–fall vs withdrawal winter) sets the backdrop the weekly
  surprise is measured against.
- **[MECHANISM] Supply side** (LNG export feedgas, production, pipeline constraints/outages) — real drivers,
  currently UNMEASURED (no feed). [OPEN — data-gap.]

## B. DISCOVERED EMPIRICAL PATTERNS (from the tape)
- **[STABLE] Magnitude law: a leg that gets BIG holds.** Legs >$350 peak sustained 35/38; small legs
  round-trip. Extreme rate (pooled 94%) that averaging could not flatten -> real. The threshold-CROSSING is
  usable as a real-time continuation event ("it's big now -> ride it"). Pinpoint the WHEN per-event.
- **[STABLE] Grind-vs-spike: how a leg is built predicts its length.** Slow grind holds; a front-loaded
  spike (high fast_capture / peaked_fast) round-trips. Of legs that held, ~1/111 spiked fast.
- **[PROVISIONAL] Storage-surprise |MAGNITUDE| -> trend-vs-range DAY.** |surprise|>=~20 Bcf weeks were the
  trend days; near-consensus weeks were range. Blind test confirmed on 08-12/13, 08-07, 08-21. SIGN did NOT
  sort direction. (~6 distinct prints, season-confounded — provisional.)
- **[PROVISIONAL] Weekday archetypes** (never pool across DOW): Wed = US-session up-lean; Thu = storage
  catalyst at the print; Fri = range, overrides surprise; Tue = strongest-trend weekday. Mon = [OPEN].
- **[HYPOTHESIS] Turning-point / "fuel spent":** the only 3 big legs that flattened had extreme far-side
  liquidity consumed (far_thinning) at the top. Candidate top-marker; n=3; test on the year via turn_* fields.
- **[PROVISIONAL] DIRECTION is callable from pre-entry order-flow imbalance (dip_imb_level).** Terciles:
  LOW dir-up 0.073 vs HIGH dir-up 0.927 (n=123 each) — a 7%/93% extreme. MONOTONE in strength: sign agrees
  the leg's direction 0.68 (|dip|<0.05) -> 0.84 (0.05-0.15) -> 0.94 (0.15-0.30) -> 0.93 (>0.30). Stable
  per-day: strong-flow agreement 0.94-1.00 on 9/12 days, worst 0.79 (07-03). Exemplars: 07-24 idx=5126
  dip=+0.59->up $270; 07-24 idx=7216 dip=-0.49->down $110; 08-01 12/12, 07-24 14/14, 08-06 9/9 agreed.
  [MECHANISM caveat: the 300s flow window overlaps the nascent trigger push -> this is a leakage-safe
  direction NOWCAST ("flow as the leg is born tells its sign"), not a from-flat forecast; ideal for the
  Kalshi-lag read (know NG's way before Kalshi reprices). Direction ONLY — correctly-signed legs still
  round-trip (07-01 idx=52270 dip=+0.48 up, peak $10, ret -11). This is the FIRST crack in the direction
  problem — 12 warm-season days, size on the year.]
- **[PROVISIONAL] imb_R = CONTRARIAN direction tilt (fade the resting wall).** Ask-heavy book (imb_R<-.05)
  -> up 0.61 (n=158); bid-heavy -> up 0.42 (n=121). Price runs THROUGH the heavy resting side (wall = fuel,
  not floor). Independent of flow but WEAKER — when flow and book disagree, flow wins direction 262/293=0.89.
  Use imb_R only as a tie-breaker when dip_imb_level is flat.
- **[STABLE] Magnitude law as a full continuation STAIRCASE.** cont vs peak-already-reached: $50->0.43(259),
  $100->0.49(192), $150->0.57(136), $190->0.70(101), $250->0.75(71), $350->0.92(38), $500->1.00(n=11);
  retention med +0.31->+0.81 along it. The ~$350 crossing is a 92% continuation event; $500 was 11/11.
  Reproduces + sharpens "big legs hold" with exact real-time thresholds. Exemplars: 07-03 idx=17768 $1060
  ret .83; 08-06 idx=9611 $840 ret .98; 07-16 idx=28757 $560 ret .91.
- **[MECHANISM+PROVISIONAL] Sustain = far-side liquidity RECRUITMENT, not absence of consumption.** The n=3
  "fuel spent" top-marker upgrades to n=101 big legs AND flips sign-meaning: HELD big legs have the far
  ladder GROWING by the top (turn_far_thinning med -0.156 = new resting liquidity stepping in AHEAD of the
  move); REVERSED tops have it static/eaten (med +0.000). Pooled tercile agrees (turn_far_thin HIGH->cont
  0.285 vs LOW 0.416). A healthy NG leg RECRUITS liquidity ahead of it; a dying one eats through static
  depth and stalls. Held exemplars (far side grows): 08-06 idx=9611 up$840 tft=-0.55; 08-06 idx=10046
  up$700 -0.33; 07-16 idx=28757 up$560 -0.40. Reversed tops (eaten): 07-03 idx=22125 dn$390 ret.13 tft=+0.55;
  09-03 idx=18622 up$310 ret-.13 +0.53; 07-01 idx=14585 dn$330 ret.18 +0.26. Measured entry->peak (diagnostic
  of the realized top); n=15 reversed, 2 were negative too -> median separation not a clean gate.
- **[PROVISIONAL] A SECOND, orthogonal hold marker: book support at the top (turn_aligned_push).** All legs:
  turn_apush>+.05 -> cont 0.39/ret +0.10 (n=117); <-.05 -> cont 0.24/ret -0.09 (n=146). Independent of
  far_thinning -> the two STACK. Works on the FULL population; muddies on the big-leg subset (where
  far_thinning is the marker). The genuine reversal top fires BOTH factors: far_thinning high AND
  turn_exhaustion deep (reversed med -0.107 vs held -0.018) — e.g. 07-03 idx=22125, 09-03 idx=18622.

## C. WHAT IS *NOT* A SIGNAL (tested, ruled out — but only for the target tested)
- **[PROVISIONAL] Book-imbalance, dipole (flow divergence), exhaustion, spread, pre-vol, weather, curve** —
  all NOISE for leg SHAPE at entry-snapshot resolution (they were magnitude confounds that vanish under
  size-conditioning). NOTE: ruled out for SHAPE only — being retested against DIRECTION, the TURNING POINT,
  and DAY-TYPE (a tool useless for one target may explain another). Curve was contango-flat all 12 days = no
  contrast; retest with a backwardation/winter stretch.
  UPDATE (multi-target pass, 372 legs): retest DONE for warm-season. Order-flow (dip_imb_level) is NOT
  noise -> it CALLS DIRECTION; resting book (imb_R) is NOT noise -> contrarian DIRECTION tilt (both Sec B).
  Still-noise for ALL FOUR targets (direction/sustain/turn/peak, every tercile at base rate): aligned_imb,
  aligned_imb_R, exhaustion, spread_ratio, pre_vol (incl. coiled quiet/active 0.30 vs 0.28), dip_aligned_flow,
  dip_mi_flow, bid/ask_dep_entry.
- **[PROVISIONAL, WEAKENED] Storage-surprise |magnitude| -> trend-vs-range DAY did NOT reproduce** on the
  372-leg continuation read: high-|surprise| days (>=20 Bcf) ran cont 0.26-0.38, low-surprise 0.21-0.44 (no
  separation); 09-12 (surp +5.6) had the HIGHEST cont 0.44. One hint survives: 08-06 (surp +25.6) was the
  only strong up-trend day (up 0.67) -> surprise may sort DIRECTION not hold-rate (n=1 day). Downgrade the
  Section-B claim; re-test on the year with winter/backwardation contrast.

## D. OPEN PROBLEMS (the frontier — where discovery goes next)
- **[PARTIAL] DIRECTION (up vs down)** — FIRST crack: dip_imb_level (pre-entry order-flow) calls direction
  monotonically (0.94 at |dip|>=0.15), imb_R adds a contrarian book tilt (Section B). Both are warm-season
  NOWCASTS partly contemporaneous with the leg birth — the OPEN part is a true from-flat FORECAST (which way
  BEFORE the move triggers) and winter validation. Data plan in `NG_FORECAST_LOG_S92.md` (news, real
  consensus, day-ahead/spot pipeline noms, overnight-lean, winter tape).
- **[OPEN] Monday shape** — re-downloading; then learn Monday as its own event.
- **[OPEN] Live turning-point / exit-timing** — the entry-snapshot failed, but the entry->peak turn_* DOES
  separate held vs reversed tops (far-side replenishment + book-support-at-top, Section B). Next: convert
  those to a REAL-TIME RUNNING TRACK (does turn_far_thinning cross from negative/replenish to positive/eaten
  as the run matures = the live exit trigger?) rather than the realized-peak diagnostic.
- **[OPEN] Winter / backwardation regime** — everything above is warm-season; re-verify on the full year.

## GROWTH LOG (append each pass)
- **S92 seed** — established from: the 12-day learn pass (PASS 1+2, full toolbox), the blind-forecast test,
  and the forecast-reasoning log. Signal-hunt (multi-target, per-event) IN PROGRESS — its results append here.
- **S92 multi-target signal hunt** (fresh unbiased analyst, 372 legs, 12 warm-season days). Full report:
  `NG_SIGNAL_HUNT.md`. Deltas landed above: (1) DIRECTION is callable — dip_imb_level monotone 0.68->0.94
  by flow strength (Sec B, moved D-direction OPEN->PARTIAL); (2) imb_R contrarian book direction tilt;
  (3) magnitude law given as an exact continuation staircase ($350=0.92, $500=11/11); (4) turning-point
  upgraded n=3->n=101 AND reframed as far-side liquidity RECRUITMENT (held legs grow the far ladder), plus
  a 2nd orthogonal marker (book support at top) and a 2-factor reversal top; (5) storage-surprise->day-type
  WEAKENED (did not reproduce); (6) confirmed 8 signals still-noise across all four targets (Sec C).
  Method note for the next pass: dip_imb_level and the turn_* markers are entry->peak / overlapping-window
  NOWCASTS — the highest-value next build is the from-flat FORECAST + a real-time running turn track; and
  everything is warm-season contango, so the winter/backwardation tape is the decisive out-of-regime test.
- **S94 knowledge add — the coin (BTC) sub-second look-ahead, tested on NG (S90).** [HYPOTHESIS, execution-layer]
  The crypto edge (S36/S37: fine-resolution price-reversal timing ~5-6bps off the turn at 1-sec vs ~9-11 at
  1-min + dipole EXHAUSTION filter) tested on NG NYMEX futures directly: static divergence did NOT transfer,
  but the EXHAUSTION factor showed a faint RIGHT-SIGNED pulse (oppose+exhaust 0.410 vs trend+strengthen 0.382
  = +2.7pp, BTC-direction; n=1 trend day, 1-sec binned). LOAD-BEARING (Greg S90): the 1-sec canary is FAR too
  coarse - the edge lives at NATIVE TICK / ms-us (MBP-10 is nanosecond); real test pending at native tick,
  per-cell, event-time. Brain play `timing.subsecond_reversal_exhaustion` (target=turn, conf 0.25). This is a
  TURN-TIMING / EXECUTION edge (like the futures->Kalshi lag) - carried in the brain, NEVER a blind open-time
  curve input. Distinct from the dipole DIRECTION nowcast (dip_imb_level, Sec B) and from the futures->Kalshi lag.
- **S92.3 — GROUP-2 coach merge (2026-07-14).** Unseen warm-season NG days (Jul-Sep 2025) blind-forecast then
  scored vs the actual tape (`scratchpad/grp2_score.json`). MERGE not rewrite — all 8 prior plays + 5 mechanisms
  preserved; 3 plays added, confidences refined. **Every lesson is stated PER EVENT, day by day — NO average, NO
  median, NO ratio, NO X-of-N count (Greg, load-bearing: any aggregate blurs away the per-event fingerprint and
  tells us nothing). Each named day is a LEAD that pinpoints the WHEN, not a memorized rule.**
  - **[PROVISIONAL] MONDAY = a big mover via the weekend-gap reprice, NOT range.** The three Group-2 Mondays,
    named individually: 0707 actual dominant +$1530 (guessed range +$180); 0728 −$1240 (guessed +$170); 0818
    −$710 (guessed −$650, close only because surprise_magnitude separately flagged it a trend day). Side differed
    each Monday — 0707 up, 0728 down, 0818 down — so bigness is the lesson, not side. Promotes `clock.weekend_gap`
    from [OPEN] toward a provisional pattern; new play `daytype.monday_weekend_gap` (n=3). Mechanism: weekend info
    accumulates over the closed market → Sun-eve reopen reprices → a big Monday leg. Per-regime until it recurs.
  - **[PROVISIONAL] STORAGE THURSDAY big, named individually.** 0710 actual dominant +$1860 (guessed −$330);
    0828 +$1310 (guessed +$420). New play `daytype.storage_thursday_magnitude` (n=2). Complements the
    `clock.storage_thursday` catalyst mechanism with a magnitude prior; side stays a coin flip at the open (print
    unknown). Two named events, not "Thursdays average big."
  - **[HYPOTHESIS / CANDIDATE] MAGNITUDE — the guesses were dwarfed on specific days, named per event.** 0707
    +$1530 vs guess +$180; 0710 +$1860 vs −$330; 0728 −$1240 vs +$170; 0730 −$1460 vs +$400; 0828 +$1310 vs
    +$420 (also 0702 +$1040 vs +$470; 0715 +$820 vs +$200; 0725 +$460 vs +$210; 0829 −$620 vs +$380). It is NOT
    uniform: on the three surprise-magnitude 'trend-day' bets the guess OVERSHOT — 0818 −$710 vs guess −$650,
    0820 −$370 vs +$880, 0826 −$560 vs +$850. Recorded as a CANDIDATE only (`magnitude.warm_season_scale_candidate`),
    prior nudged up modestly/provisionally. **Two live, unresolved readings (Greg, load-bearing): (A) the brain's
    warm-season magnitude scale is simply too small, OR (B) summer-2025 Group-2 was a higher-vol REGIME than the
    S92 learn set.** Do NOT globally rescale off one group; each day stands on its own.
  - **[unchanged] DIRECTION stays weak — from-flat direction remains OPEN.** The days that MISSED were 0710,
    0728, 0730, 0820, 0826, 0829. The two big-surprise 'trend' bets went the OPPOSITE way — 0820 guessed UP $880
    → actual DOWN $370; 0826 guessed UP $850 → actual DOWN $560 — reinforcing per event that surprise MAGNITUDE
    does not sort DIRECTION. No claim that direction improved; `direction.flow_nowcast` and the from-flat-direction
    frontier are untouched. Added as evidence to `daytype.surprise_magnitude`.
  - **GUARD:** every pattern above is a per-regime observation (one warm-season group) stated as mechanism + the
    named events + n, never averaged and never a memorized day. Winter/backwardation and a 2nd independent group
    are the decisive next tests.
- **S92.6 — CONSECUTIVE-BLOCK coach merge G3 -> G4 -> G5 (2026-07-15).** Three CONSECUTIVE chronological blocks
  (Sep 8 -> Oct 21 2025) that had been forecast + scored but never folded in; brought the brain current by merging
  each block's BLINDED guess-vs-actual lessons in order (scorecards only — `scratchpad/grp{3,4,5}_score.json` +
  `_forecasts.json`; the rich-tape / characterize_day unblinded mechanism dig is a SEPARATE later step). MERGE not
  rewrite — all 11 prior plays preserved, confidences refined, ONE play added (12 total). **Every lesson PER EVENT,
  day by day — NO average, NO median, NO ratio, NO X-of-N count (Greg, load-bearing). Each named day is a LEAD that
  pinpoints the WHEN.**
  - **[HYPOTHESIS] THE BIGGEST LEAD — CROSS-BLOCK REVERSION (new play `direction.cross_block_reversion`, n=3).**
    Each ~2-week block tended to REVERSE / give back the prior block's net move, so the agent's block-OPEN
    directional lean kept landing CONTRA the market. Per-event chronology: **G3** (Sep8-24) block fell 3.07 -> 2.86
    (down — correctly called by the +150 Bcf storage surplus backdrop). **G4** (Sep24-Oct7) REVERSED UP 2.86 -> 3.51
    — the agent EXTENDED G3's downtrend and was wrong week 1: 0925 actual +$1160 (guessed DOWN -$330), 0929 Mon
    +$1240 (guessed DOWN -$640); caught the up-move only week 2 (1001/1002/1006/1007 dir_ok). **G5** (Oct8-21) a V
    that gave back G4's up then re-rallied 3.51 -> 2.92 -> 3.52 — the agent leaned UP and was wrong week 1: 1008
    actual -$1980 (guessed UP +$320); then caught the 1016 turn-DOWN and the 1020 Monday reversal UP. Pattern
    G3 down -> G4 up -> G5 down-then-up: block-open trend-CONTINUATION is dangerous; lean AGAINST the prior block.
    Mechanism unproven (genuine ~2-week reversion vs the agent's trend-extending bias) — a lean to weight, not
    a hard fade; confirm with intraday flow.
  - **[PROVISIONAL] Weekend-gap MONDAY = huge and badly UNDER-SIZED, often a REVERSAL** (refines
    `daytype.monday_weekend_gap`, conf 0.4 -> 0.5). Named per event: 1020 Mon actual +$2770 (guessed +$580 = ~5x
    under, the block-V bottom reversal UP); 0929 Mon +$1240 (guessed -$640, wrong side AND ~2x under, the G3->G4
    up-reversal); 1006 Mon +$1150 (guessed +$600); and the G3 Mondays all big — 0908 +$1260 (guessed -$450), 0915
    -$1150 (guessed +$450), 0922 -$1410 (guessed -$500). Exception: 1013 Columbus Day (thin holiday) was the lone
    quiet Monday, handled right. Size Mondays up hard and lean toward a reversal of the block's recent direction.
  - **[PROVISIONAL] Storage THURSDAYS all large and under-forecast** (refines `daytype.storage_thursday_magnitude`,
    conf 0.35 -> 0.45). Every one across G3/4/5 a large dominant leg: 0911 -$1180 (guessed -$540); 0918 -$1560
    (guessed -$650); 0925 +$1160 (guessed -$330, wrong side); 1002 +$1360 (guessed +$760); 1009 -$1010 (guessed
    +$450, wrong side); 1016 -$1190 (guessed -$300, caught the block-V turn down). Magnitude prior up; SIDE mixed
    per event (right on 0911/0918/1002/1016, wrong on 0925/1009) — the print is unknown at the open.
  - **[HYPOTHESIS] MAGNITUDE under-forecast RECURS across three consecutive blocks** (refines
    `magnitude.warm_season_scale_candidate`, conf 0.2 -> 0.3). Across G3/G4/G5 the actual dominant move dwarfed the
    guessed peak on nearly every big day (1020 +$2770 vs +$580 the extreme; 1008 -$1980 vs +$320; 0918 -$1560 vs
    -$650; 1007 +$1620 vs +$460; 1001 +$1590 vs +$360). This strengthens reading (A) the warm-season magnitude
    scale is simply too small — but reading (B) autumn-2025 was a genuinely higher-vol / block-reversal regime is
    still live and UNRESOLVED. Do NOT globally rescale off these blocks; each day is its own LEAD.
  - **[level] FUNDAMENTALS are a slow BACKDROP, not a short-term direction/timing signal** (caveat added to
    `daytype.surprise_magnitude` + `daytype.storage_thursday_magnitude`). The +150 Bcf storage surplus correctly
    called G3's BLOCK trajectory DOWN (a real block-direction backdrop), but did NOT sort intraday side (G3 per-day
    dir_ok was a coin-flip) and did NOT anticipate the G3->G4 or G4->G5 REVERSALS. Read surplus/HDD as block-level
    backdrop, never a day-level or pre-print side/timing call.
  - **GUARD:** three consecutive blocks, still ONE regime (autumn-2025 warm-season, contango). Refine off the
    consecutive G3/4/5 only — Group-2's scattered plays were left as prior knowledge, untouched. Every pattern is
    mechanism + named events + n, never averaged, never a memorized day. Winter/backwardation and a 4th independent
    block are the decisive next tests.
