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
