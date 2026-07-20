# DATA GATE S98 - THE REWRITTEN DATA PLAN (supersedes the GATE section of SESSION_HANDOFF_2026-07-19_S97.md)

Status: AUTHORITATIVE as of 2026-07-20 (Greg: "this is what we're doing before we do any more runs").
This document extends the S97 gate with the desk-review additions (S98 desk gap analysis, delivered
in-chat 2026-07-20) and reorganizes everything by regime family, tier, and critical path. The S97
handoff's gate section remains the historical record; THIS file is the build list. NO NEW GROUP RUNS
until the gate-closure condition at the bottom of this file is met.

UPDATED same day with Greg's two decisions: (1) a MODEST PAID data tier is on the table - any actual
subscription is Greg's action, the gate's job is to PRICE the options (feed J expanded); (2) the
VEHICLE decision: KALSHI IS THE INITIAL PRIMARY, NYMEX dailies follow quickly, and BOTH are built
NOW as TWO COACHES over one shared signal core (section 0c). The Kalshi leg is therefore UN-PARKED:
feeds L and M added, Tier 3 item 6 added, gate closure amended.

---

## 0. DOCTRINE (Greg, load-bearing - governs every build below, verbatim from S97)

- **We are NOT testing theses.** We put what we believe is relevant information in front of the agent
  and IT decides how to use it. Never gate an input on whether it "worked", never score keep/drop,
  never quarantine an input that looks inert. Characterize per-instance where conditions discriminate
  ("works on {X}, not on {Y}") and leave the data in place.
- **MISSING IS EXPLICIT, NEVER ZERO.** `None` = unknown. A zeroed HDD in January, a zeroed storage
  level, or a zeroed front/next spread during a squeeze are each catastrophic false signals.
- **ADDITIVE only.** Never replace, rename, or remove existing fields.
- **BLIND WALL per feed, stated with its exact publication mechanics** (each feed's trap named in its
  spec below). Assertion in code AND an audit of the built store reporting the violation count.
- **Standalone module + `*_asof(date) -> dict | None`.** Feed builders NEVER edit
  `forecast_harness.py`; decision_state is wired in ONE serial pass by the orchestrator.
- **Investigate the real endpoint/format FIRST** (WebFetch). If the archive does not cover the period
  or the format changed, SAY SO and STOP. Zero synthetic data. No interpolation.
- **Coverage reported PER DATE / PER REGION, gaps named individually, never as a percentage.**
- Every feed ships a `--selftest`. Builders do not commit. No emojis.
- **Sources: free + Databento** (Databento spend authorized, Greg S97). Any other paid source is a
  question for Greg, never an assumption.

## 0b. THE ORGANIZING PRINCIPLE (from the S98 desk review)

The market has three regime families with different physics, and the walk's misses sort cleanly by
which family the forecaster could not see:

| family | physics | the walk's evidence |
|---|---|---|
| DEMAND | weather-driven; HDD deltas reprice the strip | most of the brain's plays live here and work |
| POSITIONING | crowding sets convexity; squeezes overshoot every band | G11: MM net short at the 2.83rd 1-yr percentile on Jan 16, then a 63 percent rally |
| DELIVERY | contracts-vs-deliverable-supply near expiry; cash leads, gamma amplifies | G11 0130 +5020 (17x under band); NGG26 settled 7.460 |

Every feed below is tagged D / P / DEL (or CAL for calendar / META for integrity / KAL for the
Kalshi leg). The point of the gate is that the agent must be able to SEE all three families before
G12; G13 is the designed forward test of the DELIVERY family.

## 0c. THE TWO-COACH ARCHITECTURE (Greg, 2026-07-20 - the vehicle decision)

Two coaches, one shared signal core, built NOW in the same gate period. The NYMEX->Kalshi LAG works
BOTH ways for us: it is the standing edge on the Kalshi side (NYMEX moves first, Kalshi reprices
seconds-to-minutes later) and it means the NYMEX read is already the leading input for both games.

- **THE SHARED SIGNAL CORE** - everything this gate builds: decision_state (all feeds), the brain,
  the walk, the day-net calls. One signal engine; both coaches consume it. G12/G13 remain the signal
  engine's skill tests.
- **THE NYMEX COACH** (second vehicle chronologically, full depth) - trades NYMEX NG dailies off the
  full input stack: day-book primary (session cell, settle-excluded), magnitude bands, sizing,
  net-of-fee at futures fee scale ($5 maker / $25 taker - immaterial per COACH_REPLAY_S97; DIRECTION
  is the constraint on this leg).
- **THE KALSHI COACH** (INITIAL PRIMARY, deliberately shallow) - a DIFFERENT GAME on the SAME
  signals: it does NOT need the deep fundamental stack; it needs (a) the NYMEX coach's read, (b) the
  LAG mechanics (when NYMEX moves, how long until the Kalshi bracket reprices, and how far), (c) the
  Kalshi microstructure: strike ladder, spread, fees, fill reality - where the S81/S82 SIZE-VS-FEE
  problem returns and is load-bearing (the exact opposite of the futures leg). Its skill test is not
  the walk; it is the echo replay (feed M) and then paper-trade on Kalshi demo
  (provisional-until-live, unchanged).
- Same signals, two games, scored separately, never conflated. The walk's per-day calls are
  vehicle-agnostic SIGNAL; each coach owns its own execution translation and its own net-of-fee
  ledger.
- BUILD-ORDER RATIONALE (Greg, 2026-07-20): build for the BIGGEST thing (full NYMEX depth) and use
  LESS of it for Kalshi - never build shallow-for-Kalshi and retrofit depth later. Subsetting a deep
  stack is trivial; deepening a shallow one is a rebuild. The subset is MEASURED, not guessed: feed
  M's echo replay identifies which signals survive Kalshi's fee wall, so "use less" is an empirical
  selection.

### THE STANDING LOOK-AHEAD (Greg, 2026-07-20: ESTABLISHED - DO NOT RETEST)

The futures -> Kalshi LAG is the Kalshi coach's entry trigger and it is settled evidence, confirmed
repeatedly without ever being the target again ("we've done it 15 times, not intentionally"):
- S80: WTI Jul 6-10, 41 contracts, **15 significant at z>=3** (peak lags 0/+1m/+5m), Brent 4/10 on a
  second hub (`SESSION_HANDOFF_2026-07-12_S80.md`, `futures_kalshi_lag.py`, odcore.leadlag +
  time-slide null).
- S81: tick-level resolution - **7-20 SECONDS on the fastest/most-liquid strike, LONGER on
  less-liquid strikes**; the 1-min "full minute" was coarse-bar aliasing; net-of-fee cleared on the
  lagging x >=$0.40-move cell (+91c over fee) (`SESSION_HANDOFF_2026-07-12_S81.md`,
  `lag_exploit_backtest.py`).
- S91: gold 37/60, silver 26/54 significant, futures-lead, same one-directional structure.
- S84 standing principle: NYMEX is the CANARY, Kalshi the delayed follower; futures lead, Kalshi
  never leads.
CONSEQUENCES: (1) feed M does NOT re-measure whether the lag exists - it measures the EXECUTION
ECONOMICS of trading it on KXNATGASD (which brackets, spread/fee/fill, echo replay of the walk's
calls); (2) the live executor logs observed lag per fire as TELEMETRY (decay watch), which is
flight instrumentation, not a retest (`deploy/aws/AWS_PLATFORM_S98.md` section 4); (3) the small
edge on the NYMEX dailies and the big edge on Kalshi are the same signal at two vehicles - the
two-coach split exists precisely to harvest both without conflating their ledgers.

---

## TIER 0 - WIRE WHAT IS ALREADY LANDED (JOB 0; serial, one hand, orchestrator only)

The three S97 feeds are committed, pushed, and on local disk. None are wired. This tier is ONE
collision-free serial pass over `forecast_harness.py::decision_state`.

| feed | module | function | family |
|---|---|---|---|
| COT positioning | `cot_feed.py` | `cot_asof(date, contract_code="023651", data_dir=None)` | P |
| Regional/salt storage | `storage_regional.py` | `storage_regional_asof(date)` | D |
| Contract structure | `contract_structure.py` | `contract_structure_asof(date, root="NG")` (49 fields) | DEL |

Wiring requirements (all from S97, unchanged and non-negotiable):
1. **Expose the CALENDAR-FRONT fields, not just n0/n1** - `calendar_front_next_spread`, its 1/3/5d
   changes, `days_to_calendar_front_expiry`, `mar_apr_spread`. On 2026-01-22 `front_next_spread` reads
   0.093 while the real squeeze sat at `calendar_front_next_spread` 1.539 - wiring only the obvious
   fields ships a feed that structurally cannot see the event it exists for.
2. Respect `*_pair_changed_*d` - cross-roll spread changes are `None`, not moves.
3. Blind wall re-audited on every join: COT keys on PUBLICATION (Friday 15:30 ET for Tuesday
   positions - the naive rule leaks 3 days of future positioning into every Wed/Thu); EIA storage
   Thursday 10:30 ET strictly-prior (the S96 fix pattern); OI respects CME next-morning publication.
4. Confirm `curve_regime` stops reading `'unknown'`.
5. All additive; missing explicit; `forecast_harness.py --selftest` extended with per-feed assertions
   (present-or-None, never zeroed) and must PASS.

**NEW in the wiring pass (S98 desk review) - two derived, additive state reads:**
6. **`squeeze_watch`** (family DEL) - a convenience read derived transparently from already-wired
   structure fields: `days_to_calendar_front_expiry <= 7` AND `calendar_front_next_spread_chg_3d`
   positive-and-widening. Exposed as a named flag PLUS its components so the agent sees both the
   read and the raw. It is information, not a gate; its definition lives in the field's `note`.
7. **Clock doctrine constant** - a static `information_clock` block (not per-day data): the ET hours
   at which information arrives (model cycle post times, EIA 10:30 Thu, settle window 14:00-14:30,
   Globex reopen 18:00). Static reference so the agent can reason "this catalyst lands at 19:00 ET,
   so it prices the gap, not the session." (The S97.2 finding that 0119's catalyst was consumed by
   the gap generalizes to this.)

## TIER 1 - THE G12 BLOCKERS (critical path; orchestrator, serial)

1. **G11 fingerprints on `.n.0`** - DONE 2026-07-20 (`run_g11_fingerprints_s98.py`): all 12 G11
   sessions through `month_characterize` on the walked NG.n.0 basis, rows tagged `series_basis`,
   merged into `renders/ng_refine_s95/fingerprints.json`. Comparability PROVEN by exact reproduction
   of all five recorded pre-G11 instance counts (1208 up 3/33 big 2/6; 1008 up 0/15; 1020 dn 1/10;
   1223 dn 3/38; 0107 dn 10/36 big 6/7).
2. **The C2 ratio reformulation** - DONE 2026-07-20, and the measurement REFUTES the reformulation:
   on the comparable base 0120 (true) reads 0.714 vs 0107 (false) 0.718 - near-identical on every
   C2 arm (absolute share 28.6% vs 27.8%; big legs 3/3 vs 6/7 alive); the proxy's 0.00-0.42-vs-1.23
   separation was a non-comparable-base artifact (the derive-don't-adopt flag did its job). Also
   corrects the s100_2 mechanism: 1208 collapsed to 9.1% on an 85-leg tape, so leg-count scale is
   not the condition. C2 is KEPT and SCOPED per-instance (discriminates on its four 2025 instances,
   abstains on the 0107/0120 class); the confirm completes as C1+C3+C4 on the modern tape class,
   which RESOLVES the G12 blocker. Full record: `C2_RATIO_FINDINGS_S98.md`. Brain proposal
   `knowledge/ng_brain_s100.3_proposal.json` - awaiting Greg's review before merge (protocol).

## TIER 2 - NEW FEEDS (parallel STEP C subagent builds per AGENT_RUNBOOK_S95 STEP C; then ONE second
serial wiring pass by the orchestrator)

Each entry: WHY (concrete, names the instance that motivates it), source, fields, blind wall, size.
Feed IDs A-K for tracking.

### A. Model-cycle timing (family D) - S97 gate item 4, EXPANDED. THE HIGHEST-VALUE DATA ITEM.
- WHY: the Sunday reopen is priced by a LATER model cycle than our D-1-evening feed. The Jan-24
  +8.511 add first appears in our data about an hour AFTER the +2100 gap that priced it. Weekend-gap
  magnitude (0118 +2100, 0125 +2480, 1020 +2770) is the walk's most reproduced residual, and the
  refine proved it is a DATA limitation, not a reasoning one.
- Phase 1 (required for the gate): cycle-level as-of. CHECK THE RAW ARCHIVE FIRST - the S97 MOS build
  audited 11,648 run stamps and its ~50MB `weather/mos_asof/raw/` archive (S3) very likely already
  holds the 00z/06z/12z/18z cycles including Sat/Sun; if so this is an EXPOSURE rework of
  `nws_temp_feed.py --mos-asof` (asof at hour resolution: `mos_cycle_asof(date, asof_hour_et)`), not
  a re-pull. Re-pull from the IEM archive only what is missing. Deliver: the LATEST cycle available
  before (a) the Sunday 18:00 ET reopen and (b) each weekday open, plus run-to-run deltas between
  consecutive cycles (not just evening batches).
- COVERAGE EXTENSION (found by the S98 Tier 0 join audit, 2026-07-20): the S97 MOS store ENDS
  2026-01-31 - `weather_forecast` is None for ALL of February 2026, i.e. G12 and G13 would run with
  NO forecast-temperature input and the blind agent would not know it was missing. Phase 1 MUST
  extend the store through 2026-02-27 (fresh IEM pull for February). A hard G12 requirement,
  independent of the cycle-timing upgrade.
- Phase 2 (post-gate, recorded not required): full-field GFS/GEFS from the NOAA AWS Open Data
  archives (free; verify bucket coverage for Nov 2025+) for ensemble spread and a true gas-weighted
  national HDD. ECMWF historical is NOT freely archived - named gap, do not fake it.
- Blind wall: a cycle is usable only after its full dissemination time (MOS posts ~3-4h after
  initialization; the builder verifies IEM's actual posting stamps rather than assuming). Assert +
  audit as-of correctness across all 91 walked days.
- HANDS OFF note: this ingests existing model output as input; the weather FORECASTER remains Greg's
  spec, untouched.

### B. Vol / range regime (family: tape conditioner) - S97 gate item 5, unchanged plus one addition.
STATUS: **DONE + WIRED 2026-07-20** (`vol_regime.py`, store on S3 `vol_regime/`). n0 coverage
102/102 sessions Nov 2 - Feb 27, zero gaps; blind-wall 0 violations (6,480 field recomputes);
bases never mixed and the necessity demonstrated numerically (same window: v0 sigma_5 $4,734 vs
n0 $1,586 - v0's 0121 is the Feb contract's +11,940 squeeze day where n0 prints +3,820). KEY STATE
FACTS FOR THE WALK: G11 opened at the winter's vol MINIMUM (sigma_20 $798, the lowest in the
store); the arc peaks $1,825 on 02-09 then collapses to $680 by 02-27 with activity_trend 0.26 -
G12 and G13 open in a regime January does not resemble. NAMED STUB: v0-basis fields are None
outside 2026-01-16..01-30 (the G3-G10 v0 corpus is S3-only; local restore + rebuild deferred to
pass-2-adjacent work - not needed for G12/G13, which run on the n0 basis).
- WHY: the brain's magnitude bands keep getting overshot (1119, 1128, 1211, 1223, 0121, 0130); bands
  calibrated in one vol regime are applied in another.
- From tape already on disk (`.v.0` for G3-G10 continuity, `.n.0` where that is the walked basis).
  Fields per date, strictly from prior sessions: realized vol (session net and intraday), ATR-class
  range measures, range percentile vs trailing window, volume trend, **trades-per-session and
  legs-per-session** (the activity metric - ALSO the conditioning variable the C2 scale artifact
  named, so Tier 1 consumes it).
- Blind wall: trailing windows end at the prior session's close. No same-day tape.
- `vol_regime_asof(date) -> dict | None`. Free, local, medium build.

### C. Model disagreement (family D) - S97 gate item 7, unchanged.
- WHY: the market prices uncertainty, not just the central case. G11's 0125/0126 whipsaw happened on
  a wobbling forecast.
- GFS-MAV vs NAM-MET, both already pulled. Horizon-MATCHED disagreement only (MET is short-range; the
  overlap is the comparable set) - per-horizon spread of gas-weighted HDD, plus a same-model
  run-to-run stability read at each horizon. Report which horizons have no overlap per date.
- `model_disagreement_asof(date) -> dict | None`. Free, small build.

### D. Storage consensus series (family D) - NEW (desk review B4). UPGRADES eia_surprise.
STATUS: **DONE + WIRED 2026-07-20.** 29/29 report weeks covered Sep 2025 - Mar 5 2026 (15/29
strictly-pre-print-stamped; the 14 evidence-post-print weeks named individually); per-house rows
(TE/investing/FF/NGI/Platts-secondary), disagreement exposed never averaged (largest: Jan 22, TE
-106 vs FF -90); four holiday-shifted prints verified incl. the double-print Christmas week; module
self-audit + the harness join audit both 0 violations; store on S3 `consensus/`. THE MOTIVATING
CASE RE-MEASURED: 0129's print was only -10/-5/-4 Bcf below the surveyed consensus (per house) vs
-15.2 on the seasonal proxy - the re-characterization of print days lands in pass 2. BONUS: 17
weeks show as-printed vs current-vintage differences (usually 1-3 Bcf, Sep 4 by +10) - direct
corroborating evidence handed to feed K. NAMED FORWARD HOLE: Mar-Jul 2026 (consensus_poll.py
accrues live since 2026-07-12; the hole matters only if the walk extends there before K-era work).
`STORAGE_CONSENSUS_NOTES_S98.md` has the full source/caveat record.
- WHY: the market prices actual-minus-SURVEY-CONSENSUS, not actual-minus-5yr-proxy. A -80 draw is a
  bearish miss if consensus was -95; our proxy can mislabel it bullish. This contaminates
  per-instance characterization of every print day in the walk, INCLUDING the 14/14
  chain-sided-print streak - some "disagreeing prints the chain overrode" may not have been
  surprises at all. The FIX is a re-measurement, and the finding may survive - that is the point of
  measuring.
- Source: investigate (WebFetch first) the archived weekly analyst-survey numbers - candidate free
  routes: econ-calendar archives that carry the pre-print "forecast" figure for the EIA weekly
  change; news-archive survey mentions. Compile per report week: consensus draw/build (Bcf), source
  named per row. If a week's consensus is unobtainable, that week is `None` and NAMED - never
  interpolated, never proxied.
- Coverage target: the walked winter (Nov 2025 - Feb 2026) minimum; back to the start of the walk
  ideal.
- Blind wall: consensus is public BEFORE the print (survey publishes Tue/Wed); join as-of the print
  morning; the print's own value stays strictly-prior for the following days (existing rule).
- `storage_consensus_asof(date) -> dict | None` (fields: `consensus_chg_bcf`, `n_estimates`,
  `range_low/high` if available, `source`, `for_report_date`, plus post-join `surprise_vs_consensus`
  computed only where both sides exist). Medium build, scrape-and-verify heavy.

### E. Freeze-off risk (family D-supply) - NEW (desk review B3). The missing convexity mechanism.
- WHY: deep cold CUTS SUPPLY (wellhead/gathering freeze-offs in producing basins) at the same time it
  raises demand - extreme-cold days are convex, which is a mechanism-level explanation for the
  walk's dominant residual (extreme days overshooting bands 2-17x). The brain's weather logic is
  demand-only and cannot see this.
- Source: the same IEM MOS archive, PRODUCING-BASIN stations: Permian (MAF Midland), Anadarko (OKC),
  Appalachia (PIT), Haynesville (SHV). Builder verifies station availability in the archive and
  substitutes nearest-basin stations only with the substitution NAMED per station.
- Fields per date (forecast, as-of the same cycle discipline as feed A): per-basin forecast min temp
  by horizon, consecutive-days-below thresholds (e.g. 20F/15F/10F - thresholds exposed as data, not
  tuned), first/last sub-threshold day in the horizon. NO synthesized production impact, NO Bcf
  estimate - temperatures only; the agent decides what they mean.
- Blind wall: identical to feed A (cycle as-of).
- `freeze_risk_asof(date) -> dict | None`. Small-medium build once A's cycle plumbing exists (build
  AFTER or WITH A).

### F. Flow calendar (family CAL) - NEW (desk review). Deterministic, zero external dependencies.
STATUS: **DONE + WIRED 2026-07-20** (`flow_calendar.py`, store on S3 `flow_calendar/`, 365 rows +
52 EIA releases). Anchors verified: NGG26 expiry 2026-01-28; NGH26 expiry **2026-02-25 CONFIRMED**
(derived + Databento definition + structure store agree - the S97 handoff's date stands); opex =
business day before expiry (NGG26 Jan 27, NGH26 Feb 24); expiry rule reproduces 12/12 in-coverage
definitions. SCHEDULE SURPRISES ENCODED: Veterans week EIA slips to FRIDAY Nov 14; Christmas week
slips LATE to Mon Dec 29 (no release week of Dec 22, TWO the week of Dec 29 - independently matches
feed D). G13's gauntlet on record: GSCI roll Feb 6-12, BCOM Feb 9-13, bidweek Feb 23-27, opex Feb
24, expiry Feb 25. CORRECTION APPLIED to the harness holiday dict: 2026-07-03 is a FULL CME holiday
(was mistagged early_close); counting authority = this feed. Disagreement log in
`FLOW_CALENDAR_NOTES_S98.md` (12 beyond-span definition boundary cases, 4 structure-store
convention offsets, the refuted GSCI-annual-roll web claim - all named).
- WHY: mechanical, scheduled flows desks trade around; none are visible to the agent. G13 carries an
  expiry; bidweek and index-roll windows sit inside every block.
- Fields per date: `days_to_futures_expiry` (front), `options_expiry_date` + `days_to_opex` (NG
  options expire the business day BEFORE futures expiry - the pin/unpin boundary), `in_bidweek`
  (final 5 business days of the month) + `bidweek_day_n`, `in_gsci_roll` (business days 5-9) /
  `in_bcom_roll` (business days 6-10) - builder VERIFIES both roll windows against the current index
  methodology docs rather than trusting this line - `eia_print_date` for the week incl.
  holiday-shifted releases (from EIA's actual release schedule archive, never assumed),
  `cme_early_close` flags.
- Blind wall: none (fully deterministic/forward-known), except EIA holiday shifts which must come
  from the published schedule.
- `flow_calendar_asof(date) -> dict`. Small build (one afternoon class).

### G. Cash basis (family DEL) - NEW (desk review). The free sliver of the physical market.
STATUS: **DONE + WIRED 2026-07-20** (`cash_basis.py`, store on S3 `cash_basis/`). THE LOAD-BEARING
MEASUREMENT: EIA's "daily" HH spot publishes in WEEKLY BATCHES (NGWU era -> WNGSR-Supplement era
from Jan 2026) with holiday blackouts up to 22 days - a naive T+1 join would have leaked the whole
Jan 2026 cash blowout (Jan 23 cash $30.72, basis +25.37) a WEEK early. Wall = knowable_from
release+1; blind-wall 0/317; selftest pins BOTH sides of the wall (0123 sees -0.12, 0130 sees
+10.765 with chg_3d +7.287 - the delivery squeeze visible decision-time-legit on the walk's 17x
residual day). 212 rows Sep 2025 - Jul 2026; 14 holiday gaps named; vintage measured ($0.01-0.07);
settle caveat recorded (ohlcv close vs official settle: NGG26 7.200 vs 7.460 final day).
- WHY: cash leads futures in delivery stress; we have zero physical-market visibility. In a squeeze
  the cash-futures basis is the ground truth the paper market converges to.
- Source: EIA daily Henry Hub spot (Refinitiv-sourced, published free with a short lag). Builder
  investigates the ACTUAL publication lag and vintage mechanics first - if the series revises or the
  lag is longer than assumed, report it honestly; the feed may be D-1 or D-2. Field:
  `hh_cash_minus_front_settle` as-of the latest jointly-published day, plus its 1/3/5d trend, plus
  `age_days`.
- Blind wall: join on publication availability, not price date; audit.
- `cash_basis_asof(date) -> dict | None`. Small build.

### H. COT futures-and-options combined (family P) - NEW, small. Closes half of COT limit #9.
STATUS: **DONE + WIRED 2026-07-20** (`cot_combined_feed.py`, store on S3 `cot_combined/`; publication
machinery imported from cot_feed incl. the shutdown overrides, never re-derived). 393 reports
2019-2026, date set identical to the futures store; blind-wall 0 (exhaustive 6-decision-times/day
probe walk); OI cross-check 393/393. THE FINDING: the walked winter's two largest options-implied
MM-net divergences (+1,210 and +1,085 futures-equivalent) are the two crowded-short weeks entering
G11 - at the G11 open, futures-only MM net sat at the 2.83rd 1-yr percentile while the
OPTIONS-IMPLIED read sat at the 97.17th. The two books at opposite extremes is now a wired state
variable. ENV NOTE: cftc.gov now 403s python's default UA (this module sends a browser UA;
cot_feed's downloader will need the same if ever re-run --force). ICE HH half of limit #9 stays
open (no free source).
- WHY: the S97 COT build is futures-only; options positioning is a separate picture and expiry-week
  mechanics (G13) are exactly where it diverges.
- Source: same CFTC disaggregated publication, the futures-AND-options-combined variant. Same store
  layout, same publication-time blind wall as `cot_feed.py` (reuse its machinery; additive fields
  `*_combined`).
- Extend `cot_asof` output additively. Small build. The ICE Henry Hub gap REMAINS OPEN and stays
  named (no free source).

### I. Options surface (family DEL/P) - S97 gate item 9, NOW SCOPED. Required before G13, best-effort
  before G12.
- WHY: options expire the day before futures expiry and drive pinning/squeeze mechanics - plausibly
  part of G11's February (NGG26 settled 7.460). G13 is the squeeze test; running it without the
  options view repeats the G11 pattern of testing a family the agent cannot see.
- Source: Databento GLBX NG options (authorized spend). Phased:
  - Phase i (REQUIRED for G13): `definition` + `statistics` - per-strike OI for the front two
    months, settlement prices, opex dates. Fields: top-5 OI strikes + concentrations (the pin/wall
    map), total P/C OI, `days_to_opex`, front-month OI-weighted strike distance from settle.
  - Phase ii (post-gate ok): settle-implied ATM IV + a 25-delta risk-reversal skew proxy computed
    from settlement prices (standard Black on futures settles - computation, not synthesis; every
    input is a real settle).
- Blind wall: CME settlement/OI publication is next-morning - same rule as the futures OI join.
- `options_surface_asof(date, root="NG") -> dict | None`. The largest new build in the gate.

### J. LNG feedgas + paid-data survey - S97 gate item 8, converted to a BOUNDED SIZING SPIKE,
  EXPANDED per Greg 2026-07-20 ("modest is on the table").
- WHY: structurally the biggest modern NG demand driver (a Freeport-class outage reprices the curve
  for months). Vendor nomination data is paid; EIA monthly is too slow. BUT the terminal-serving
  interstate pipes post scheduled quantities on FERC-mandated public EBBs.
- The spike (investigation, NOT a feed build), two arms:
  - FREE arm: enumerate the EBB posting locations for the 5-6 big terminal laterals; determine
    per-source whether HISTORICAL postings are retrievable (the honest risk: EBBs often show current
    + shallow history only - useless for the walk, still valuable live-forward); report
    obtainability per terminal + effort estimate.
  - PAID arm (NEW): survey the vendor landscape for daily feedgas/production nowcasts at a MODEST
    price point - name each candidate source, what it carries (feedgas by terminal, dry-gas
    production, power burn), its history depth, delivery mechanics (API/file), and monthly cost.
    Include the cheaper aggregator tier, not just the Platts/WoodMac flagship tier. NO
    subscription is taken by the builder or the orchestrator - the deliverable is a costed
    recommendation; subscribing is GREG'S action.
- Deliverable: `LNG_FEEDGAS_SIZING_S98.md` (both arms). Explicitly authorized conclusion on the free
  arm: "not obtainable historically; live-only feed possible" - a successful spike, not a failure.
  No synthetic proxy under any circumstances.

### N. EIA weekly S/D balance - the Natural Gas Weekly Update (family D/supply) - NEW (Greg
2026-07-20: "this site has weekly production and consumption data also").
- WHY: the desk audit's #2 structural gap is the flow/balance side, and the NGWU is the FREE weekly
  version of it: dry production estimates, consumption by sector (power/industrial/rescomm), LNG
  feedgas weekly average, net imports - published every Thursday. Weekly cadence is coarser than
  vendor daily noms, but it is the same balance object desks anchor on, it is historical, and it
  costs nothing. It also absorbs feed J's "wire the EIA weekly/monthly anchors now" recommendation.
- Builder investigates first: where the NGWU's weekly supply/demand table actually lives (page
  archive vs API), its EXACT publication timing (the blind wall - NGWU posts Thursday, pin the
  hour), the week-definition (avg Wed-Wed?), and the attribution (production/consumption estimates
  in the NGWU are third-party-sourced - S&P Global Commodity Insights; carry the attribution and
  any redistribution limits honestly; if the numbers are only chart-embedded and not extractable,
  SAY SO).
- Fields per report week: dry_production_bcfd, total_consumption_bcfd + by-sector split, lng
  feedgas_bcfd, net_imports_bcfd, each with w/w change; publication_datetime; join strictly on
  publication. Coverage target: the walked winter minimum, back to Sep 2025.
- `ngwu_asof(date) -> dict | None`, store `data/ngwu/`, selftest + blind-wall audit, notes doc.
  QUEUED - launch when an agent slot frees.

### O. Structural-demand news watch (family D/structural) - NEW (Greg 2026-07-20: "keep one eye on
data centers coming online or any major manufacturing coming online... checking the news feeds").
- WHAT IT IS: a LIVE-FORWARD watch, not a walk input. Keyword families: datacenter campuses /
  hyperscaler-utility interconnections, major industrial/manufacturing plant startups, LNG train
  startups AND outages (Freeport-class events), major pipeline maintenance/outages. Sources: free
  feeds (EIA Today in Energy, company/utility releases, ISO announcements) via the existing
  news_ingest_rss.py machinery; quantified slow-layer companions: ISO interconnection queues and
  utility IRPs (datacenter load), and feed N's weekly power-burn/industrial consumption as the
  MEASURED confirmation of what the news claims qualitatively.
- HONEST SCOPING: retrofitting a news feed into the WALK is out of scope for now - historical news
  joins are hindsight-prone (publication-dated archives are patchy) and the walk's blind wall is
  the project's most protected asset. The watch enters at the LIVE coach layer: a standing item in
  the daily lifecycle (the S87 5PM/AM/intraday cycle) and a section in the two-coach spec (Tier 3
  item 6). Recorded here so it is not lost; built with M5 (the live box).

### L. Kalshi-side NG market data - inventory, restore, backfill (family KAL) - NEW (two-coach).
- WHY: the Kalshi coach's echo replay (feed M) needs the Kalshi side of the walked winter -
  KXNATGASD (daily NG settle brackets) quotes/trades/books. We currently hold NONE of it locally
  (data/ has no kalshi dirs); the durable collectors push to `data/kalshi-bins` on the trunk branch
  `claude/kalshi-s79-kickoff-ij8t9o`, and their accrual through Nov 2025 - Feb 2026 is UNVERIFIED
  (S83 recorded runs sitting queued on account-level Actions issues).
- The task: (1) inventory what actually accrued - fetch the data branch, list KXNATGASD coverage PER
  DATE across the walked winter; (2) backfill gaps from the Kalshi public history API
  (`kalshi_history.py` exists - verify it still matches the current API before leaning on it);
  (3) land the store locally + push to S3 under `kalshi/` (git = CODE, S3 = DATA); (4) report
  per-date coverage, gaps named individually. If whole blocks of the winter are unrecoverable at
  quote/book depth, say so - trades-only coverage changes what feed M can honestly claim.
- Blind wall: n/a for collection; feed M owns the join discipline.
- Deliverable: the store + `KALSHI_NG_COVERAGE_S98.md`. Medium build.

### M. The lag echo replay + Kalshi fill/fee model (family KAL) - NEW (two-coach). UN-PARKS the
  Kalshi-side fill modeling that S97 deferred.
- WHY: the Kalshi coach's game IS the lag (NYMEX leads, Kalshi follows seconds-to-minutes later) and
  its constraint IS size-vs-fee (S81/S82) - the exact inversion of the futures leg, where
  COACH_REPLAY_S97 proved fees immaterial and direction binding. Nothing about the Kalshi leg is
  provisional-until-live except via this build.
- RESCOPED 2026-07-20 BY FEED L'S HEADLINE: **Kalshi had NO daily NG market in the walked winter -
  KXNATGASD launched 2026-03-27 (first settle 03-30), and Jan 1 - Feb 27 2026 had ZERO NG-linked
  Kalshi markets of any kind** (`KALSHI_NG_COVERAGE_S98.md`; a market-existence gap, not a
  data-recovery gap - no credential or vendor can produce data that was never generated). The
  G7-G11 winter echo replay is STRUCTURALLY IMPOSSIBLE and is struck as a named honest gap. M's
  substrate is the KXNATGASD LIFE (2026-03-30 -> present): the NYMEX side for that window exists on
  S3 (the year MBP-10 pull runs through Jul 2026), and the walk itself reaches that era at G14+ -
  the echo replay of walk calls happens THERE, chronologically, when the walk arrives.
  Product-structure fact for the spec: KXNATGASD skips FRIDAYS (the weekly market owns Friday).
  Items (1)/(2) below run on the life window; item (3) is re-pointed at G14+ calls.
- SCOPE GUARD (Greg 2026-07-20): the lag's EXISTENCE is established - see THE STANDING LOOK-AHEAD
  in 0c. M never re-litigates it. What follows is execution economics only.
- The build, on feed L's store, reusing the existing lag thread (`futures_kalshi_lag.py`,
  `lag_exploit_backtest.py`, `odcore/leadlag.py`):
  - (1) CHARACTERIZE the lag's NG-specific execution shape on KXNATGASD across the walked winter:
    per-event (never pooled) NYMEX move -> Kalshi bracket reprice delay + pass-through fraction,
    per moneyness band and time-of-day - the fill-tradeoff map (deepest-lag strikes fill worst),
    not a significance test. 1-sec NYMEX readouts are LOWER BOUNDS (standing rule).
  - (2) FILL/FEE MODEL: Kalshi spread-as-cost per bracket + per-contract fee schedule + a
    conservative fill assumption (cross-the-spread taker baseline; resting-order fill claims
    require book evidence, else not claimed).
  - (3) ECHO REPLAY: re-price the walk's blind day-book calls (G7-G11) through the Kalshi leg -
    which calls survive net-of-fee at Kalshi scale, per-cell (moneyness x day-class), maker AND
    taker framing. This is the Kalshi coach's first honest scorecard, the direct sequel to the
    S81/S82 size-vs-fee finding.
- Leakage gate (`odcore/leakage.py`) mandatory before the replay; settle-window exclusion applies on
  the NYMEX side; Kalshi settle mechanics (bracket settlement time/source) verified from the
  contract spec, never assumed.
- Deliverable: `KALSHI_ECHO_REPLAY_S98.md` + the fill/fee module (`kalshi_fill_model.py`,
  `echo_replay.py`). The largest KAL build; runs parallel off the critical path until L lands.

### K. Revision-vintage assessment (family META) - S97 concern #1, promoted into the gate.
- WHY: the blind wall governs WHEN a report becomes visible, not WHICH VINTAGE - the store carries
  EIA's latest revisions, so the agent may see numbers nobody had at the time. Likely affects the
  existing national `storage` field and `eia_surprise.py` too, i.e. the whole walk carries an
  unmeasured look-ahead. "Probably small" is not measured.
- The task: pull EIA's revision/vintage archive (REAL EIA key required - see prerequisites), diff
  as-first-printed vs currently-stored for every weekly report in the walked window (national + the
  new regional store), and NAME each week where the vintage differs, with the delta in Bcf. If the
  vintage archive does not cover the window, say so and report what is checkable.
- Deliverable: `REVISION_VINTAGE_AUDIT_S98.md` + where differences exist, an as-printed override
  layer in the affected stores (additive: `*_as_printed` fields; the revised values STAY, labeled).
- This is the leakage-gate discipline applied to our own storage feeds. Medium task.

## TIER 3 - DOCTRINE AND STRUCTURAL WORK (brain + protocol; orchestrator; renders/proposals PRINTED
to Greg before any brain merge, per standing protocol)

1. **Usage-doctrine block in the brain** (from the S98 desk review Part 2): per-source-family reading
   guidance - weather deltas (first-appearance vs revision; D+4-8 battleground; clock), storage
   (weekly re-anchor; salt = front-month scarcity; composition second wave), COT (convexity
   conditioner, never timing/direction; band-overshoot flag at percentile extremes; never fade the
   squeeze side; its three limits carried), structure (level is state, widening RATE is signal;
   expiry clock switches regime), vol (band scaler, never direction), options (pin/unpin, walls,
   IV as uncertainty). Written as GUIDANCE the agent reads, never as gates - merged as a brain
   proposal for review.
2. **Driver checklist at flip evaluations** (desk review B2): at every chain_polarity_flip arm/confirm
   evaluation the agent must READ (not obey) the four families' state: forecast stream
   (first-appearance adds and their side), positioning (COT percentile + side), structure
   (spread widening + expiry clock), tape (C1/C2-ratio). Recorded in the brain as method, joining
   the existing C1-C4 which stay unchanged.
3. **Evidence-day registry** (desk review B7): a brain section mapping day -> plays citing it, so
   overlapping calibration evidence (1208, 1223, 1020, 0107 anchor multiple plays) is visible and
   per-play n counts are not silently double-counted.
4. **Two-books scoring split, effective G12** (desk review B1, resolves S97 concern #5): the DAY-BOOK
   (per-day nets, net-of-fee maker AND taker) is the PRIMARY scored product; the BLOCK LEAN is
   demoted to a REGIME-STATE call (polarity + conviction) recorded and graded as a descriptor and as
   a conditioner of day plays - not as a standalone pass/fail deliverable. Both continue to be
   recorded per-event. Rationale on record: two-week directional calls on NG are near-coin-flip at
   the best desks; the replay shows the day-book is where the edge lives (resume 9/10; fees
   immaterial; turn-calls 0/3) and G9 proved a wrong lean does not cost the day-book money. Under
   the two-coach architecture (0c) the day-book is the NYMEX coach's product; the Kalshi coach's
   product is the echo book (feed M) and is scored on its own ledger.
5. **Squeeze-regime doctrine** (desk review B5): brain guidance that inside the delivery window
   (squeeze_watch active) demand-regime bands and alternation rules are OUT OF SCOPE - bands void,
   no mean-reversion assumption, never short the squeeze leg on band logic; G11 is n=1, G13 the
   forward test. Scope-tagged like every play; the agent decides application.
6. **The two-coach spec** (Greg 2026-07-20, section 0c): a short design doc
   (`TWO_COACH_SPEC_S98.md`) fixing the boundary - what the shared signal core emits (per-day call:
   side, magnitude band, conviction, regime state, timing notes), what the NYMEX coach adds
   (sizing, session cell, futures fees), what the Kalshi coach adds (bracket selection off the
   strike ladder, lag-triggered entry, spread/fee/fill model from feed M, exit before settle), and
   the rule that the two ledgers are never pooled. Written after feed M's first numbers exist so the
   spec is grounded in measured lag/fee reality, not assumption.

## TIER 4 - PLATFORM CONSOLIDATION + AWS MIGRATION (Greg 2026-07-20; parallel, does NOT block G12)

Greg: "we don't want data spread everywhere. i want to start the migration to aws where the
platform will live. or a hybrid of that and git. i want you to look at that too for trade execution
speed." The full plan is `deploy/aws/AWS_PLATFORM_S98.md`. The decision: HYBRID FORMALIZED -
git = CODE + docs + records; S3 = ALL DATA in ONE bucket with per-prefix manifests; local = cache
rebuildable in one command; the LIVE loop in us-east-1 co-region with Kalshi. Execution-speed
verdict: the established 7-20s+ lag means the platform needs SUB-SECOND, not sub-millisecond - a
plain co-region box beats the edge's clock 100x, the LLM never sits in the hot path (playbook
pre-set, deterministic executor fires), and live lag TELEMETRY per fire watches decay without
retesting. M-steps: M1 key rotation (Greg, blocks pushes) -> M2 taxonomy + platform_sync.py ->
M3 push local-only stores -> M4 repoint collectors off the git data branches (freeze as archive) ->
M5 us-east-1 live box (post-gate, with the two-coach spec) -> M6 session ritual becomes
platform_sync pull. Runs alongside the gate; no G12 dependency.

## EXPLICITLY NOT IN THE GATE (named deferrals, unchanged reasons)

- **Cross-market (TTF/JKM, power stack, coal switch)** - S97 item 10; real drivers, slower-moving,
  lowest priority. Post-gate.
- **CTA-replication daily positioning proxy** - free to build later; COT + the combined variant
  cover the gate's positioning need.
- **Full production/flow network (all-pipeline EBB scrape)** - the desk's biggest remaining edge, out
  of scope until the J spike sizes the terminal-lateral subset.
- **ECMWF historical cycles** - not freely archived; named gap, no proxy.
- **Pass-2 series construction AND the second refinement round** - JOB 4, after the first pass
  completes. CONFIRMED by Greg 2026-07-20: a full second refinement round runs over the
  already-walked groups once pass 1 is done - so ALL retroactive old-run work lands THERE, not now:
  the series-construction re-base (`PASS2_CONTINUOUS_SERIES_NOTES.md`), re-characterizing old print
  days against feed D's true consensus, propagating feed K's as-printed vintages through old
  findings, and re-reading old extremes against the new positioning/structure/vol state. Do not
  touch the old runs before then.

## PREREQUISITES (Greg, before/while the builds run)

1. ROTATE the AWS pair + DATABENTO key (both exposed in-chat S97).
2. GET A REAL EIA KEY - DONE 2026-07-20 (key live in aws.env, verified against the weekly
   salt/nonsalt series). S97 CONCERN #2 CLOSED same day: the regional store rebuilt `--source api`
   and diffed against the xls-fallback build - ZERO value differences across all 863 periods and
   every region; blind-wall audit 0/791 days, 0 thursday-own-print; refreshed store pushed to S3.
   (Both sources carry CURRENT vintages - the as-printed vintage question remains feed K's.)
3. DECIDED 2026-07-20 (recorded, no longer open): a MODEST paid tier is on the table - feed J prices
   the options, Greg subscribes or declines; the vehicle is KALSHI FIRST then NYMEX dailies, both
   coaches built now (section 0c, feeds L/M, Tier 3 item 6).
4. EIA KEY SCOPE NOTE (Greg 2026-07-20): the ONE registered key covers ALL EIA Open Data v2 routes -
   including PETROLEUM (crude stocks/prices/refining = the WPSR data; the Wednesday 10:30 ET print
   is the CL-side analog of the NG storage Thursday). Relevant the moment a CL/WTI leg enters - and
   feed L found KXWTI existed through the walked winter with archive to 2022, so a WTI Kalshi leg
   HAS the history the NG leg lacks. Also checked (Greg's pointer): eia.gov/consumption - RECS/
   CBECS/MECS are PERIODIC MULTI-YEAR STRUCTURAL surveys, not timely feeds: no next-day event use;
   their honest use is slow-layer demand-share weights (e.g. validating the gas-weighted metro
   weighting), recorded as a reference, not a gate item. Also eia.gov/consumption/reports.php
   (Greg's second pointer): the derived analyses off those surveys - same verdict, structural
   reference (useful facts: gas share of households by region, heating's dominance of commercial
   fuel use) for the demand-weight layer, no event-time use.

## SEQUENCING AND THE CRITICAL PATH

- SERIAL (orchestrator, one hand): Tier 0 wiring -> Tier 1 (fingerprints -> C2 ratio). This is the
  G12 critical path.
- PARALLEL (STEP C subagents, run while Tier 0/1 proceeds): B, C, D, F, G, H, J, L; A phase 1;
  E with/after A; I phase i started early (largest GLBX build); M as soon as L lands data.
- SECOND SERIAL WIRING PASS (orchestrator): wire A, B, C, D, E, F, G, H (+I if landed) into
  decision_state; re-audit the blind wall across ALL joins; selftest. (L/M do not enter
  decision_state - they are the Kalshi coach's substrate, not walk inputs; the walk stays blind to
  the echo leg.)
- TIER 3 brain proposals assembled after the wiring passes; PRINTED to Greg; merged on approval.
- K runs parallel as an audit; its as-printed overlays land in the second wiring pass.

## GATE-CLOSURE CONDITION (what "done" means; no new group runs before this)

G12 (Sun Feb 1 - Fri Feb 13 2026) may run when ALL of:
1. Tier 0 wired; selftest PASS; blind-wall audits clean; curve_regime no longer 'unknown'.
2. Tier 1 complete (G11 fingerprints on .n.0 + C2 ratio reformulation derived and recorded in a
   brain proposal).
3. Tier 2 feeds A(ph1), B, C, D, E, F, G, H built AND wired; K's audit delivered (with as-printed
   overlays where differences were found); J's sizing report delivered; L's coverage report
   delivered (the store restored/backfilled to whatever honest coverage exists).
4. Tier 3 items 1-5 proposed, printed to Greg, and merged on his approval.
5. Roll check for G12 run by a SUBAGENT returning ONLY roll date + spread (the S97 protocol fix).

G13 (Sun Feb 15 - Fri Feb 27 2026, the SQUEEZE TEST) additionally requires:
6. Feed I phase i (options OI/pin map) built and wired.
7. Feed M delivered ON ITS RESCOPED SUBSTRATE (lag characterization + fill/fee model on the
   KXNATGASD life 2026-03-30 -> present; the walked-winter echo replay is STRUCK - feed L proved
   the market did not exist, a named honest gap closing that sub-item) and Tier 3 item 6 (the
   two-coach spec) written off M's measured numbers - the Kalshi coach's first scorecard exists
   before the walk resumes past G12.

Anything in this file found unobtainable is reported per-instance in the closing session handoff -
a named honest gap closes its item; a silent skip does not.
