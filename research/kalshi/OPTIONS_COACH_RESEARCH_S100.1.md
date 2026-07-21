# OPTIONS COACH RESEARCH - THE THIRD COACH: NYMEX NG OPTIONS (S100.1, 2026-07-20)

## S100.2 REVISION - BUILD RECORD (same day; Greg green-lit E5 items 1-5, all DELIVERED)

Everything below section 0 was written as proposal; this block records what is now BUILT and
MEASURED, for review alongside the next blind runs (G12/G13, S101).

- E2 items 1-2 BUILT: `options_iv_surface.py` - 180 sessions Oct 31 - Jul 17 (81 winter +
  99 live-era bridge), 687,866 settle IVs, LNE backbone, exact per-month futures settles both
  eras, surface_asof D-1 wall, selftest 10/10. Store S3 `options_iv/`.
- MEASURED SCALE TRAP (load-bearing for anyone touching options data): LNE strike_price
  decodes at 1/10 dollars. Proven by matched-pair pricing: 4,804 LNE-ON pairs price within
  median $0.0004 at scale 10 vs $1.79 at scale 1. CONSEQUENCE: phase i's COMBINED ON+LNE
  pin view (options_surface.py `_combine`, wired into decision_state block `options_surface`)
  merges MISMATCHED ladders - combined top-OI walls are suspect until the signal core fixes
  it; PER-ASSET views are unaffected. Flagged for S101/G13 (the pin map is a G13 input).
- E3 Phase MD MEASURED (`options_md_measures.py`, per-event rows stored): Samuelson sized
  (winter med ATM 0.32 at 181d+ -> 0.75 inside 30d, 1-10d p90 1.81); rr25 POSITIVE every
  winter cell (backwardation|squeeze med 0.228 vs |normal 0.090 vs contango 0.037) but
  summer rr25 ~ -0.015 (regime split real; contango cells thin, said so); event-vol: winter
  subset day-after +0.019 vs all-span ~0 (34 events, never pooled); IV-vs-RV: 56/75 IV
  above, med +0.19, p10 -1.09 (the fat left tail = the defined-risk constraint's evidence);
  ON-LNE ATM gap med 0.0002 across 177 sessions -> Black-76-everywhere justified BY
  MEASUREMENT (C3 CLOSED).
- E4 REPLAY RUN (`options_replay.py`, G7-G11 blind calls only, v1 vertical menu, leakage
  invariant 59/59, squeeze-short declined 6x): 51 events on the OPTIONS BOOK ledger.
  Footnotes: G7 -632 / G8 +930 / G9 +3,908 / G10 -12 / G11 +8,842. THE READ: G11 (the
  futures book's blind lean MISS) was the options translation's best block - defined-risk
  verticals capped wrong-side days near the debit while squeeze days paid multiples
  (best event +5,297). G7 chop bled theta (verticals in give-back blocks = known-bad cell).
  Settle-marked, execution unmeasured, not an edge claim.
- E2 item 5 DELIVERED at $0.00 (in-subscription, get_cost-gated): bridge raws Mar-Jul 2026
  (ON/LNE defs+stats + NG.FUT stats) at S3 `options_ng_bridge/`; the options clock now
  aligns with the KXNATGASD life.
- E5 dispositions: 4 (intraday quotes) deferred until the replay names paying cells;
  6 (weeklies) open - NOT captured by the phase-i parent pull, needs a defs-only pull;
  7 (CSOs) held; 8 (three-coach spec amendment) held until Greg judges the replay earned it.
- BLIND-RUN HYGIENE (binding on S101): data/options_ng/* and S3 options_iv/ carry UNWALLED
  Feb-window realized data (IV paths, replay marks). The G12/G13 blind agent must NOT read
  them; the G12/G13 options replay runs AFTER those blinds complete (extend GROUPS in
  options_replay.py).

Foundational research for a THIRD coach over the same shared signal core: the NYMEX NG OPTIONS
coach. Greg's steer, verbatim emphasis: "this is where our forward curves really matter" - the
forward curve is the UNDERLYING of this entire lane, not context. NG options are options on
futures; Black-76 prices off the FORWARD, each option month prices off ITS OWN futures contract,
so the whole surface is indexed by (curve point, strike). Everything the curve feeds
(`forward_curve.py` 12-rank settles, `contract_structure.py` calendar-front squeeze fields,
curve_regime) is underlying-state here, not conditioning.

Every claim carries an evidence label: MEASURED-IN-REPO / PEER-REVIEWED / PRACTITIONER-STANDARD /
VENDOR-CLAIM / UNVERIFIED. Nothing below is our edge until measured on our data
(provisional-until-live, unchanged). No pooled-mean scoring anywhere; per-event, per-cell always.
This file proposes INPUTS and a coach, never plays - the brain is read-only to this lane
(S97 rule: put relevant info in front of the agent; never gate an input on whether it "worked").

---

## 0. WHAT WE ALREADY HOLD (the substrate; all MEASURED-IN-REPO)

- **Feed I phase i, BUILT + WIRED** (`options_surface.py`, `OPTIONS_SURFACE_NOTES_S99.md`):
  GLBX NG options definition + monthly statistics, BOTH roots (ON American + LNE European),
  $4.67 total. Store `data/options_ng/surface.json.gz`: **81 sessions Oct 31 2025 - Feb 27
  2026, 715,843 OI points, 1,124,806 settle points**; raw .dbn.zst on S3 `options_ng/`.
  Wired as decision_state block `options_surface`; blind wall = CME next-morning publication;
  audit 0 violations / 101 days.
- **Measured symbology traps**: CME NG options live under ON/LNE roots, NOT NG ("NG.OPT"
  resolves to nothing); statistics stat_type 3 = settlement (@1e9), 9 = OI; session date in
  ts_ref; INT64/UINT64 null sentinels; defs repeat per session (dedupe by instrument_id);
  `underlying` names the future month directly (e.g. NGQ26). Opex cross-check: defs reproduce
  the flow-calendar anchors exactly (NGG26 opex 2026-01-27; NGH26 opex 2026-02-24).
- **The vendor Black-76 pattern** (`vendor/databento_options_iv_black76_example.py`): chain via
  parent symbology filtered to the underlying -> price -> scipy root_scalar inversion. Our two
  standing adaptations: ON/LNE roots, and SETTLEMENT prices instead of intraday midprices
  (statistics already pulled; zero marginal data cost). This IS the designated feed I phase ii
  path.
- **The curve stack**: `forward_curve.py` 12-rank daily settle curve (~$0.07/yr, curve_regime
  backwardation/contango/flat, mar_apr_spread = the H/J widow-maker); `contract_structure.py`
  49 fields incl. the CALENDAR-FRONT pair. S97 lesson, load-bearing here: **the OI-continuous
  front HIDES the squeeze** (0122: `front_next_spread` 0.093 vs calendar-front 1.539). For the
  options lane this generalizes: every option month must be joined to ITS OWN futures
  contract's settle, never to a continuous series.
- **The walked-winter decision_state**: 23 blocks/day, 101 days, 0 audit violations - the
  options coach's input side already exists day-by-day for the whole options-data window.
- **NYMEX MBP-10 futures year tape** on S3 (realized-vol ground truth for any IV-vs-RV
  measurement), and `vol_regime.py` (realized session sigma/range, D-1 wall) already wired.
- **Positioning**: `cot_combined_feed.py` measured the futures book and options-implied book at
  OPPOSITE extremes entering G11 (MM futures 2.83rd pctile vs options-implied 97.17th) - a
  wired state variable that is natively an OPTIONS-lane input.

Coverage statement, explicit: options data = **Oct 31 2025 - Feb 27 2026** (raw statistics
pulled Nov 2025 - Mar 2026 in monthly chunks). The walked winter G7 (opens Nov 5) through G13
(ends Feb 27) is FULLY inside it. G3-G6 (Sep 8 - Nov 4) is NOT (G6's last 4 days only). The
KXNATGASD life (Mar 30 2026+) is NOT covered by the current pull.

---

## A. THE FORWARD CURVE AS THE OPTIONS UNDERLYING (Greg's emphasis - the organizing frame)

### A1. Black-76 mechanics: the surface is a curve object

Black-76 prices a futures option off the futures price F, not spot: the option on NGH26 knows
nothing about NGG26 except through the curve. Consequences (PRACTITIONER-STANDARD, and
mechanical from the model):

1. **The vol surface is indexed by (curve point, strike)**, not by (time, strike) alone. An
   "ATM" strike is ATM relative to THAT month's futures settle. The curve's seasonal shape
   means the ATM ladder itself is seasonal: in winter backwardation the Feb ATM sits far above
   the Apr ATM.
2. **Curve moves ARE underlying moves, per month.** A calendar-spread move (front +1.5, next
   +0.2 - our measured G11 shape) is a huge underlying move for front options and a small one
   for next-month options. The delta-one lane sees one number (the walked basis); the options
   lane sees a VECTOR of underlyings. This is why the calendar-front lesson binds: option-month
   P&L joined to a continuous front series is simply wrong.
3. **Rates are a rounding error at our horizons**: Black-76's discount factor e^(-rT) at
   r ~ 4-5% and T <= 60 days is a <1% price effect, far below settle-mark noise. Keep r fixed
   from a single public curve, disclose it, and never tune it.
4. **NG's most-watched structural point, the H/J (mar_apr) spread, is also an options object**:
   CSOs (calendar spread options) trade directly on it (CME education pages call March/April
   "the most volatile of all NG futures spreads", the widow-maker;
   https://www.cmegroup.com/education/courses/introduction-to-natural-gas/natural-gas-calendar-spread-options.html,
   VENDOR-CLAIM but uncontroversial). Our mar_apr_spread field is the underlying of that
   product family.

### A2. Samuelson effect (vol term structure rising into expiry)

- The effect (front vol > deferred vol, steepening into expiry) is documented as especially
  pronounced in energy, with the steepest rise in the final months of contract life
  (PEER-REVIEWED: "In Pursuit of Samuelson for Commodity Futures",
  https://www.mdpi.com/2813-2432/4/3/13, exponential 1- and 2-decay parameterizations;
  "Variance dynamics and term structure of the natural gas market",
  https://www.sciencedirect.com/science/article/abs/pii/S0140988324004882 - NG variance carries
  both seasonality and time-to-maturity effects; option pricing accuracy on Henry Hub improves
  when Samuelson is modeled).
- HONEST COUNTERWEIGHT (PEER-REVIEWED): in some NG specifications maturity loses to VOLUME -
  significant negative maturity coefficients fall from 28% to 6% of contracts once volume is
  included (https://ecomod.net/sites/default/files/document-conference/ecomod2007-energy/478.pdf).
  So Samuelson in NG is partially a liquidity-concentration artifact, not pure delivery physics.
  For us this is a feature, not a problem: our activity/vol feeds already carry the volume side.
- SIZE: the literature parameterizes instantaneous vol as sigma(t,T) with exponential decay in
  (T-t); NG calibrations show front-month IV routinely a large multiple of 6-month-out IV in
  winter (direction robust across the cited papers; exact multiples vary by sample -
  UNVERIFIED as a specific number, and our own settle surface can measure it directly for
  2025-26, which is the right answer).
- INTERACTION WITH THE SQUEEZE (our G13 window): Samuelson says front IV rises into expiry
  mechanically; a delivery squeeze (measured: Feb 3.0 -> 5.4 while Mar 2.7 -> 4.4) rides ON TOP
  of that. Expect the front-month IV path into Feb 24 opex to carry both a calendar component
  (predictable) and a squeeze component (the event). Separating them per-day on our own settle
  surface is a first-class measurement, and G13 (opex 02-24 / expiry 02-25 inside bidweek,
  GSCI/BCOM rolls Feb 6-13) is the designed test window.

### A3. Seasonal surface structure and skew direction

- Winter premium: NG IV is higher in winter months, and the variance seasonality itself is
  winter-loaded (PEER-REVIEWED, both ScienceDirect cites above; also Doran-Ronn below on
  winter-loaded vol premia).
- SKEW DIRECTION: the canonical NG finding is POSITIVE strike skew - IV increasing with strike
  (calls over puts), i.e. the market prices upside gaps (cold shocks, squeezes); documented in
  "Implied Volatility in Crude Oil and Natural Gas Markets"
  (https://www.researchgate.net/publication/228425050_Implied_Volatility_in_Crude_Oil_and_Natural_Gas_Markets)
  and in Trolle-Schwartz's unspanned-stochastic-volatility work on NYMEX gas options
  (PEER-REVIEWED). Energy also shows POSITIVE price-vol correlation - the opposite of equities
  (Doran-Ronn 2008, https://www.sciencedirect.com/science/article/abs/pii/S0378426608000885).
- REGIME CONDITIONING (call skew in cold-shock regimes vs put skew in glut; does backwardation
  predict skew/term shifts?): plausible, thinly published, and exactly the kind of claim we
  never adopt from literature - label UNVERIFIED. Our data can answer it: 81 sessions of settle
  surface x curve_regime x squeeze_watch is the per-cell join. Note the walked winter is almost
  all backwardation, so the contango cell will be thin - report "works on {winter
  backwardation}" honestly and leave the other cell open rather than extrapolate.
- Trolle-Schwartz "unspanned stochastic volatility" (PEER-REVIEWED, RFS 2009 and sequels):
  commodity vol risk is NOT spanned by the futures curve - options carry state the futures tape
  does not. This is the academic license for the whole third coach: the options surface is new
  information, not a transform of what the signal core already sees.

### A4. Expiry week, pinning mechanics, and the squeeze in options space

- Structure of the clock (MEASURED-IN-REPO): options expire the business day BEFORE futures
  expiry (NGH26 opex Feb 24, futures Feb 25); post-opex the front OPTION month has already
  rolled while the future is still squeezing - the unpinned expiry day is itself a read.
- What a squeeze should print in options (PRACTITIONER-STANDARD, each item measurable on our
  settles): front-month IV explosion concentrated at the front curve point (next-month IV
  comparatively quiet - the vol-surface image of the calendar-front spread blowout); call-wing
  steepening (upside gap risk); OI walls near the settle becoming pin candidates INTO opex and
  irrelevant after it.
- AMERICAN EXERCISE: ON options are American-style. Early exercise on futures options is worth
  little for ATM short-dated at low rates but becomes material deep ITM (see C3). In a
  squeeze, deep-ITM calls on the expiring month are exactly the class where American != Black-76.
  Mitigation is structural, not numerical: we hold BOTH roots, and LNE is EUROPEAN - Black-76
  is exact for it (up to settle-mark quality). Build IV off LNE; use ON for the OI/pin map;
  the measured ON-minus-LNE settle-IV gap at matched strikes IS the early-exercise premium,
  a free data-quality check and a squeeze diagnostic in one.

---

## B. PREDICTORS / FORECASTING TOOLS (what the evidence actually supports)

### B1. IV as an RV forecast, and the variance risk premium

- IV is the best single forecaster of subsequent realized vol in futures markets: 34/35
  markets, beating historical vol and GARCH (PEER-REVIEWED: Szakmary, Ors, Kim, Davidson 2003,
  J. Banking & Finance,
  https://www.sciencedirect.com/science/article/abs/pii/S0378426602003230). It is also BIASED:
  IV > RV on average.
- The bias is the variance risk premium, and in energy it is negative and NG-specific work
  finds it winter-loaded: Doran-Ronn 2008 (J. Banking & Finance,
  https://www.sciencedirect.com/science/article/abs/pii/S0378426608000885) find a significant
  negative volatility risk premium for natural gas with larger premia in winter months; the
  general VRP literature (e.g.
  https://macrosynergy.com/research/realistic-volatility-risk-premia/,
  PRACTITIONER-STANDARD) finds unconditional short-vol carry positive but fat-left-tailed.
- CONSEQUENCE FOR THE COACH: systematic short vol in NG winter is picking up a premium in
  front of exactly the convexity our walk keeps measuring (bands overshot 2-17x on extreme
  days; the squeeze). The coach's short-vol expressions must be defined-risk and
  condition-gated, never a standing carry book. The VRP is a CONTEXT number per cell, not a play.
- Event-cycle vol (EIA storage Thursdays): scheduled-event IV build/crush is
  PRACTITIONER-STANDARD (the earnings-straddle analog; average ATM straddle returns into
  events are negative in the broad literature) but NG-specific published measurement is THIN -
  say so plainly: UNVERIFIED for NG at daily granularity. Our data measures it directly: 17
  storage Thursdays inside the surface window, daily settle-IV path D-3..D+1 per report week,
  per-cell by surprise size (feed D consensus) and chain polarity. This is directly analogous
  to our information_clock and needs no new data.

### B2. OI structure: walls, pinning, max pain - be skeptical

- Pinning is REAL but modest in the best evidence: equity optionable stocks cluster at strikes
  on expiration days (Ni, Pearson, Poteshman 2005, J. Financial Economics -
  PEER-REVIEWED; delta-hedging mechanics, effect size cents-scale). Max-pain as a TRADING
  signal is retail lore with poor evidence quality (the sources that promote it are
  vendor/blog tier, e.g. https://menthorq.com/guide/max-pain-theory-explained/ - VENDOR-CLAIM;
  even promoters concede it "is not guaranteed").
- In futures options the evidence is weaker still, and NG's dominant hedgers are commercials
  whose books are not equity-market-maker books. VERDICT: OI walls enter as INPUTS (the pin
  map we already wired - distance to wall, concentration share, days_to_opex), never as a
  standalone directional predictor. The agent reads them; nothing gates on them. This is
  already the brain's doctrine_tier3.options stance; the options coach inherits it unchanged.
- Dealer-gamma / GEX-style analysis in NG: public data cannot identify who holds each side
  even in equities (estimation error 30-50% per practitioner sources,
  https://spotgamma.com/gamma-exposure-gex/ - VENDOR-CLAIM), and in NG the
  dealer-is-short-gamma assumption is unsupported. HONEST VERDICT: UNVERIFIED and probably
  not measurable from our data. The one legitimate fragment we hold: CFTC options-implied
  positioning (cot_combined), which measured the two books at opposite extremes into G11 -
  that is a real, wired, weekly-cadence positioning read; use it and do not build a fake GEX.

### B3. Skew / risk-reversal as predictor

- Commodity implied-skewness work finds predictive content but nuanced and horizon-dependent:
  implied variance/skewness risk premia predict commodity returns
  (https://www.sciencedirect.com/science/article/abs/pii/S1042443122000543, PEER-REVIEWED);
  realized-skewness sorts price commodity futures (Fernandez-Perez et al.,
  https://www.sciencedirect.com/science/article/abs/pii/S0378426617301504, PEER-REVIEWED);
  risk-neutral skewness and futures pricing
  (https://openaccess.city.ac.uk/id/eprint/27562/1/Risk_Neutral_Skewness_and_Commodity_Futures_Pricing.pdf).
  Signs differ across studies and horizons - this is a "carries information, direction not
  settled" literature. Label: PEER-REVIEWED that skew is informative; UNVERIFIED which way for
  NG daily horizons.
- COACH USE: the 25d risk-reversal is a STATE variable (crowding/insurance-demand read,
  natural join against cot_combined's opposite-extremes find), an input the agent sees at
  flip-checklist time - not a direction rule.

### B4. Term-structure signals

- Front/back IV ratio and its change: the Samuelson-adjusted front/2nd IV ratio is the vol
  image of squeeze_watch (front IV decoupling from next = delivery physics active).
  PRACTITIONER-STANDARD as a monitor; measurable daily from our settles.
- Event-day forward vol: with daily expiries absent, the clean version (extracting the
  one-day event variance from two expiries bracketing the event) is coarse in NG monthlies -
  the two nearest monthlies are ~1 month apart, so EIA-Thursday forward-vol extraction is
  noisy at best; weeklies (if liquid - see D) are the honest instrument for it. Do not
  oversell this one on monthly data.

### B5. Cross-signals from OUR stack -> options expressions (the translation table)

The signal core's emit is vehicle-agnostic (TWO_COACH_SPEC section 1); the options coach
TRANSLATES it. Sketch of the mapping (each row = translation of an existing owned call, NOT a
new play; per-cell scoring on the options ledger):

| emit element (owning play class) | options expression (typed menu) |
|---|---|
| day_side long/short + magnitude_band normal (resume/giveback/continuation class) | short-dated vertical (debit spread) in the FRONT option month, strikes off the band edges; defined risk |
| day_type = post-print chain-sided (storage Thursday, 14/14 leg-sided) | pre-print: nothing directional; the EVENT-VOL cycle trade is the measurement target (build/crush), not assumed |
| magnitude_band VOID + squeeze_watch active (squeeze doctrine: bands void, never short the squeeze leg) | LONG-vol only: front-month calls / call spreads, long front-vs-next IV (calendar), NEVER short front vol or upside |
| flip checklist armed (C1 band-break state) | risk-reversal or backspread instead of delta-one: pays if the flip is real, defined cost if the chain holds |
| weekend_gap plays (Sunday-reopen cycle delta) | Monday-expiry weekly straddle/strangle IF weeklies prove liquid (open question D3); otherwise front monthly gamma |
| COT opposite-extremes state (futures vs options-implied books) | skew expression: RR positioned against the crowded book's squeeze side - INPUT-conditioned, direction still owned by the emit |
| vol_regime floor state (e.g. G11 opened at winter sigma minimum) | long-gamma tilt when entering catalyst-dense windows from a vol floor - the S98 miss mechanism expressed as a vol trade |

The right column is deliberately a SMALL TYPED MENU (verticals, straddles/strangles, RR,
front/next calendars, backspreads). No exotic structures; every structure priced off the settle
surface at entry and exit.

---

## C. MODELING PROPERLY

### C1. Surface construction from settles (our data reality: daily statistics, no options tape)

Pipeline (feed I phase ii, all inputs already on disk):
1. Per session, per option month: join each strike's settle to ITS underlying future's settle
   (from the defs' `underlying` field -> that month's futures settle in the statistics /
   curve store; NEVER a continuous series).
2. Invert Black-76 per strike (vendor pattern, root_scalar; r fixed ~4-5%, disclosed;
   T from defs' expiration). Prefer OTM side per strike (puts below F, calls above) to
   minimize American/intrinsic contamination.
3. **LNE (European) is the IV backbone** - Black-76 exact. ON (American) IVs computed the same
   way are recorded as `iv_amer_naive` with the ON-LNE gap exposed per strike (the early
   exercise premium as a data product; see C3).
4. Reduce to per-(month, session) FEATURES: ATM IV (interpolated at F), 25d RR, 25d butterfly,
   wing slopes, front/next ATM ratio, days_to_opex. Missing strikes/months = None, never
   interpolated across months.

SMOOTHING RECOMMENDATION - the simplest thing that fits per-cell doctrine and daily-settle
granularity: **NO global surface fit initially.** Raw per-strike settle IVs + the feature set
above. Rationale: (a) our unit of decision is a per-cell feature (ATM level, RR, ratio), not a
continuous density; (b) SVI/SSVI/SABR (survey:
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6197858; Gatheral-Jacquier arbitrage-free
SVI: https://mfe.baruch.cuny.edu/wp-content/uploads/2013/01/OsakaSVI2012.pdf - both
PEER-REVIEWED/PRACTITIONER-STANDARD) earn their complexity only when you need an arbitrage-free
density or to price strikes you do not observe; (c) a parametric fit SMOOTHS AWAY exactly the
local anomalies (a kinked wing at a wall strike, a front-month blowout) that are our subject.
If a fit is later needed (pricing unlisted strikes for structure P&L), per-expiry SVI with
butterfly/calendar checks is the designated step - SSVI/SABR only if SVI per-expiry proves
insufficient. Record no-arb violations in the RAW settle surface as a data-quality flag rather
than repairing them silently.

SETTLE-MARK HONESTY (load-bearing caveat): CME settles exist for every listed strike including
untraded ones - they are marks from the settlement procedure, not fills. Far-wing and zero-OI
strike IVs are the settlement algorithm's opinion. Every feature above must carry its
supporting OI/liquidity context (we have per-strike OI), and claims must degrade honestly:
ATM +-2 strikes on the front two months = trustworthy; 10-delta wings = descriptive only.

### C2. Greeks, bucketing, margin

- Greeks at entry from the same Black-76 inversion (closed-form). Bucket VEGA BY CURVE POINT
  (option month = curve point - the Greg emphasis made operational: a vega ladder along the
  curve, exactly parallel to the futures curve object). Gamma concentrates at the front month
  and into opex (Samuelson + time decay); report gamma/theta per month, never summed across
  months (summing across curve points is pooling).
- Margin (short options): CME SPAN/SPAN2 scenario-based; short deep-OTM carries a Short
  Option Minimum floor (https://www.cmegroup.com/clearing/files/margins-on-options.pdf,
  VENDOR-CLAIM/authoritative). Magnitudes: NG futures maintenance margin has run
  order-$3-8k/contract depending on regime (UNVERIFIED as a current number - pull the live
  CME margins page / CME CORE before any sizing;
  https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.margins.html). Working
  assumption for design: a short ATM option margins at futures-scale. CONSEQUENCE: at our
  size, DEFINED-RISK structures (verticals, flies, spreads) are the default; naked short
  options need a margin model we have not measured. This is a design constraint, not a
  measured number.

### C3. American-on-futures adjustment: is it material?

- Theory/practice: early-exercise premium on futures options is small for ATM short-dated
  options at moderate rates, material deep-ITM (PRACTITIONER-STANDARD;
  https://ryanoconnellfinance.com/options-on-futures/; Kwok, American options chapter,
  https://www.math.hkust.edu.hk/~maykwok/courses/ma571/06_07/Kwok_Chap_5.pdf). Empirical EEP
  studies (equity-index American vs European pairs, e.g.
  https://onlinelibrary.wiley.com/doi/10.1002/fut.22508) find single-percent-of-premium
  magnitudes ATM.
- OUR ANSWER IS STRUCTURAL, NOT NUMERICAL: NG uniquely lists BOTH styles side by side (ON
  American, LNE European; https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.contractSpecs.options.html).
  Use LNE for IV (Black-76 exact); MEASURE the matched-strike ON-LNE settle-IV gap across the
  81 sessions. If the gap at the moneyness we trade is inside settle-mark noise, Black-76
  everywhere is justified BY MEASUREMENT; where it widens (deep ITM, squeeze week), that
  gap is itself a delivery-stress read. No binomial tree until the measurement says we need one.
- OPEN VERIFICATION ITEM: relative OI/liquidity of ON vs LNE in our own defs+stats (which root
  carries the walls? which carries the volume?) - answerable from data on hand, do it in
  phase ii before choosing default trading root.

### C4. Leakage discipline for options (binding)

- Settle-based IV is END-OF-DAY information with next-morning publication - the SAME D-1 wall
  as the futures OI join, already implemented and audited in phase i. Phase ii inherits it:
  `surface_asof(D)` serves the latest session strictly before D.
- Event-vol studies run under the walk's blind walls: the D-3..D+1 IV path around a storage
  print may only be READ at D+2; a "vol builds into the print" rule derived on the walked
  winter is refined-not-blind until it survives a forward block (same doctrine as every play).
- Realized-vol comparisons use vol_regime / the futures tape under its existing wall; the
  settle window exclusion applies to any intraday RV we compute (standing rule).
- `odcore/leakage.py` gate before any replay scoring run - mandatory, unchanged.

---

## D. EXECUTION REALITY (the options coach's feed-M analog - MEASURE before any trading claim)

What feed M did for Kalshi (response rates, delays, spread/fee wall, maker-vs-taker verdict)
does not exist for NG options and nothing below may be assumed:

- **D1. Liquidity structure - what we can measure FREE from data on hand**: per-strike, per-month
  OI and its daily change; settle coverage; ON-vs-LNE split; how far OI concentrates from ATM.
  What we CANNOT measure from statistics: bid-ask spreads, top-of-book depth, block share,
  trade counts. Options books are quote-driven and MM-dominated (the S91 survey scored options
  LAST for the tick-timing edge for exactly this reason - different edge here, same
  microstructure fact).
- **D2. The paid measurement (bounded)**: intraday options quotes from GLBX.MDP3 (MBP-1 or
  trades+tbbo) for a SMALL cell: front month, ATM +-5 strikes, both roots, a handful of
  named days (a storage Thursday, an opex day, a squeeze-week day, a quiet day). The
  options universe is thousands of instruments - never pull the chain wholesale.
  COST: UNVERIFIED until quoted; the phase i full-winter defs+stats ran $4.67, and vendor
  per-GB pricing suggests a strike-limited quote pull is single-to-low-double-digit dollars,
  but the standing rule binds: `metadata.get_cost` gate before EVERY pull, abort on surprise.
- **D3. Weeklies**: CME lists Friday weeklies plus Mon-Thu expiries
  (https://www.cmegroup.com/articles/faqs/faq-natural-gas-weekly-options.html, VENDOR-CLAIM).
  Whether they existed and carried OI in OUR window is answerable from the defs already pulled
  (scan instrument roots/expirations) - do this before any weekend-gap-via-weeklies idea
  survives design review.
- **D4. Fees**: CME energy options exchange+clearing runs the same family as futures
  (~$1.50/side non-member per the TradeStation schedule,
  https://www.tradestation.com/pricing/exchange-execution-and-clearing-fees/, VENDOR-CLAIM -
  re-verify per options product before sizing) vs our carried futures line $5 maker / $25
  taker RT all-in. Fee is NOT the wall here; the SPREAD is. A quote-driven book's bid-ask in
  IV points is the real cost line, and it is exactly what D2 measures. Prior (UNVERIFIED,
  design-only): ATM front-month NG options trade tick-tight in active hours; wings and
  deferreds do not.
- **D5. CVOL**: CME publishes a free 30-day NG implied-vol index
  (https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.contractSpecs.options.html
  references CVOL) - a zero-cost daily sanity anchor for our ATM IV series; history depth and
  license terms UNVERIFIED - investigate before wiring.

---

## E. THE COACH PROPOSAL

### E1. Boundaries (per the TWO_COACH_SPEC pattern - now three coaches, one core)

- **Consumes**: the SAME signal-core emit (one voice per target: block_regime_state, day_side,
  day_type, magnitude_band, timing_notes, watch_list - the coach translates, NEVER edits) PLUS
  options-specific state: settle surface features (per month: ATM IV, RR, fly, front/next
  ratio), OI pin map (phase i, wired), flow_calendar opex clock, cot_combined two-books state,
  contract_structure calendar-front fields, vol_regime. All existing or phase-ii derivable.
- **Translates** day_side/day_type/magnitude_band/timing into the SMALL TYPED MENU of B5
  (verticals, straddles/strangles, risk-reversals, front/next calendars, backspreads), each
  order fully specified (month, strikes, side, 1-lot) and priced off the settle surface.
- **Its own ledger**: the OPTIONS BOOK - per-event, per-cell (structure type x month x
  moneyness x day-class), net of fee estimates, NEVER pooled with the NYMEX day-book or the
  Kalshi echo book. Drift/aggregates are descriptors only.
- **Provisional-until-live**; every probability provenance-labeled; new inputs default to
  CONTEXT never voice (doctrine unchanged). The coach adds NO plays to the brain; anything it
  learns proposes INPUTS or coach-side translation rules, printed to Greg before merge.
- **Not in the hot path**: like the other coaches, playbook pre-set, deterministic pricing;
  the LLM never prices an option live.

### E2. Data/feed build list (ordered, free-first; DATA_GATE format)

| # | feed | what it feeds | source | wall / leakage rule | cost |
|---|---|---|---|---|---|
| 1 | I-ph2a: settle-IV surface (LNE backbone + ON naive + ON-LNE gap) | the coach's underlying state; every measurement in E3 | data ON HAND (statistics + defs + futures settles) | CME next-morning publication (phase i rule, audited) | $0 |
| 2 | I-ph2b: surface FEATURES store (`surface_asof`: per-month ATM IV, 25d RR, 25d fly, front/next ratio, days_to_opex) | decision_state additive fields (INPUT, not play) + the replay | derived from 1 | inherits 1 | $0 |
| 3 | roots/weeklies inventory | D3 answer; ON-vs-LNE liquidity split; trading-root default | data ON HAND (defs) | n/a | $0 |
| 4 | CVOL daily history | free external IV anchor / cross-check on our ATM series | CME (investigate license + depth FIRST) | publication-time join | $0 (verify) |
| 5 | live-era bridge: statistics Mar-Jul 2026, both roots | aligns the options clock with the KXNATGASD life + live-forward paper | Databento GLBX statistics | same as 1 | est. ~$5-class; get_cost gate |
| 6 | event-day intraday options quotes (bounded cell, D2) | the execution map: spreads/depth by moneyness/month | Databento GLBX MBP-1/tbbo, strike-limited | n/a (execution measurement, not walk input) | UNVERIFIED; quote first, expect low-double-digit |
| 7 | CSO defs+statistics (H/J and front-pair) | the squeeze lane's direct instrument; mar_apr options view | Databento GLBX (CSO roots - verify symbology, expect a distinct root) | same as 1 | small; quote first |

Free-first is satisfied: items 1-4 cost nothing and unlock the whole replay; 5-7 are gated on
measured need and get_cost quotes. No subscription anywhere; any recurring feed is Greg's call.

### E3. The measurement program BEFORE any trading claim (the feed L/M analog)

Phase MD (market discovery - free, settle/OI only):
1. Samuelson curve per month: ATM IV vs days-to-opex across 81 sessions; the winter premium
   term shape; front/next ratio baseline vs squeeze weeks (A2/A4 sized on OUR data).
2. Skew book: RR level/dynamics vs curve_regime, vs squeeze_watch, vs cot_combined extremes
   (A3/B3 answered per-cell; contango cell honestly thin).
3. Event-vol cycle: settle-IV path around all 17 in-window storage Thursdays, per surprise
   cell (B1 measured; the information_clock analog).
4. IV-vs-RV: front ATM IV vs subsequent realized (vol_regime / tape), per-event never pooled
   mean - the NG VRP on our own winter.
5. ON-LNE matched-strike gap (C3) + settle-mark trust map (which strikes' settles are live:
   OI-weighted coverage per moneyness band).
Honest scope statement: settle-only data supports EOD-granularity claims about STATE and
about settle-to-settle structure P&L. It CANNOT support: intraday entry/exit claims, spread
costs, fill probability, or the intraday shape of event vol crush. Those cells stay
UNCLAIMED until item 6 (bounded quotes) or live paper collection exists.

Phase EX (execution economics - gated on item 6 or live): spread in IV points by
moneyness/month/time-of-day; depth; the options maker-vs-taker framing. Until then every
replay P&L carries the label "settle-marked, execution unmeasured".

### E4. The blind/refine walk adaptation - the settle-IV replay of the walked winter

THE OPPORTUNITY (and why this coach can be stood up faster than the Kalshi coach could):
Kalshi's walked-winter echo replay was structurally impossible (no market existed). The
options market EXISTED all winter and we ALREADY OWN its daily record: 81 sessions Oct 31 -
Feb 27 covering G7 through G13 exactly, with the walk's decision_state present day-by-day
(101 days, audited) and the walk's blind day-book calls on record.

- **Coverage, explicit**: G7-G13 replayable (Nov 5 - Feb 27 all inside Oct 31 - Feb 27).
  G3-G6 NOT replayable (no options data before Oct 31); the KXNATGASD-life era (Mar 30+) not
  covered until build item 5. Named honestly, no extrapolation.
- **Protocol**: same as the walk's. Per group, ONE-SHOT BLIND: the coach sees decision_state
  asof D + surface_asof D (both D-1-walled) + the signal core's recorded BLIND emit for D
  (the calls as actually made at that group's brain version, COACH_REPLAY_S97's honest
  pattern - never re-run the brain in-sample), translates to the typed menu, and the
  structure is priced at D's (or exit-day's) settle surface. Then refine, renders printed to
  Greg, lessons merge as COACH-side translation rules (never brain plays). Leakage gate run
  on the replay harness before scoring; roll/expiry handling per option month (no continuous
  series anywhere).
- **Scoring product: the VOL/STRUCTURE DAY-BOOK** - the options analog of the day-book: per
  event (day x structure), entry and exit at settle marks, fees per D4, P&L decomposed
  delta/vega/theta (Black-76 attribution) so a right-vol-wrong-direction day is visible
  per-event; cells = structure type x month x moneyness x day-class x regime
  (squeeze_watch/vol-floor). Per-event rows are the store; block sums are footnotes.
- **Honest limitations, stated up front**: settle-marked fills are marks, not fills
  (execution unmeasured until E3-EX); one settle per day means intraday structure
  (enter-at-open exit-before-settle, the futures session cell) has NO options analog yet -
  the options day-book is settle-to-settle and says so; far-wing structures inherit the
  settle-mark caveat (C1). The replay is the coach's SIGNAL scorecard, exactly parallel to
  COACH_REPLAY_S97's role for futures - "did the translation pay at marks", with execution
  its own later gate.
- **The designed showcase cells**: G9's crest/crash (did long-vol translations of flip-armed
  days pay?), G11 squeeze weeks (front IV/calendar behavior vs the never-short-the-squeeze
  doctrine), G13 (opex inside bidweek - the pin map's live test), and the storage-Thursday
  event-vol cells.

### E5. Open questions for Greg (ranked, each with recommendation)

1. **Green-light feed I phase ii + the settle-IV replay as the options coach's foundation?**
   $0 data cost, all inputs on hand, G7-G13 covered. RECOMMENDATION: yes, before any paid
   options data - this is the FREE-FIRST path and it produces the coach's first honest
   scorecard (the analog of feed M's map + COACH_REPLAY in one).
2. **LNE-first IV policy** (European backbone, ON for OI/pin, ON-LNE gap as a measured
   product)? RECOMMENDATION: yes - it converts the American-adjustment question from a
   modeling task into a measurement, and phase i already showed both roots populated.
3. **Defined-risk-only constraint** until SPAN margin is measured (no naked short options in
   any replay or paper book)? RECOMMENDATION: yes - short-vol carry in NG winter is selling
   insurance against exactly the convexity our walk keeps hitting (B1/C2); verticals and
   flies express the same views with a known worst case.
4. **The bounded intraday options quote pull** (item 6, ~4 named days, strike-limited, quoted
   via get_cost first) - now, or only after the settle replay names paying cells?
   RECOMMENDATION: after the replay - the replay may kill cells cheaply and the pull is
   better targeted then; the standing procurement policy (pay only MEASURED gaps) points the
   same way.
5. **Live-era bridge pull** (statistics Mar-Jul 2026, ~$5-class): RECOMMENDATION: yes at
   next data session - it aligns the options surface with the KXNATGASD life so the three
   coaches share one clock at go-live, and it is squarely inside the authorized
   Databento-spend pattern.
6. **Weeklies lane** (weekend-gap plays via Monday-expiry weeklies): RECOMMENDATION: defer
   until the free defs inventory (item 3) shows they existed with real OI in-window; no
   design work before that fact.
7. **CSO lane** (options directly on H/J and front spreads - the purest squeeze instrument):
   RECOMMENDATION: quote the data cost, hold the build until the G13 settle replay shows
   whether the vanilla surface already carries the squeeze read; CSOs are a thin,
   specialist book and execution reality there is a bigger unknown than in vanillas.
8. **Third-coach status in the spec**: amend TWO_COACH_SPEC to a three-coach registry (same
   core, third ledger) now, or hold until the replay delivers? RECOMMENDATION: hold the spec
   edit until the replay exists (the spec was written off feed M's MEASURED numbers; the
   options coach should earn its section the same way).

---

## SOURCES (external; all accessed 2026-07-20)

- Samuelson/term structure: https://www.mdpi.com/2813-2432/4/3/13 ;
  https://www.sciencedirect.com/science/article/abs/pii/S0140988324004882 ;
  https://ecomod.net/sites/default/files/document-conference/ecomod2007-energy/478.pdf
- Seasonality/skew/VRP: https://www.sciencedirect.com/science/article/abs/pii/S0378426608000885
  (Doran-Ronn 2008) ; https://www.researchgate.net/publication/228425050_Implied_Volatility_in_Crude_Oil_and_Natural_Gas_Markets ;
  https://www.sciencedirect.com/science/article/abs/pii/S0140988321004862 ;
  https://link.springer.com/article/10.1007/s10479-022-05128-x ;
  https://macrosynergy.com/research/realistic-volatility-risk-premia/
- IV predicts RV: https://www.sciencedirect.com/science/article/abs/pii/S0378426602003230
  (Szakmary et al. 2003)
- Skewness/RR predictability: https://www.sciencedirect.com/science/article/abs/pii/S1042443122000543 ;
  https://www.sciencedirect.com/science/article/abs/pii/S0378426617301504 ;
  https://openaccess.city.ac.uk/id/eprint/27562/1/Risk_Neutral_Skewness_and_Commodity_Futures_Pricing.pdf
- Pinning/max-pain/GEX (weak-evidence tier, labeled): https://menthorq.com/guide/max-pain-theory-explained/ ;
  https://spotgamma.com/gamma-exposure-gex/ ;
  https://fabiobaruffa.com/articles/pin-risk-options-trading-python/
- Surface fitting: https://mfe.baruch.cuny.edu/wp-content/uploads/2013/01/OsakaSVI2012.pdf ;
  https://papers.ssrn.com/sol3/papers.cfm?abstract_id=6197858 ;
  https://arxiv.org/pdf/2204.00312
- American-on-futures: https://ryanoconnellfinance.com/options-on-futures/ ;
  https://www.math.hkust.edu.hk/~maykwok/courses/ma571/06_07/Kwok_Chap_5.pdf ;
  https://onlinelibrary.wiley.com/doi/10.1002/fut.22508
- Contract/venue/margin/fees: https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.contractSpecs.options.html ;
  https://www.cmegroup.com/articles/faqs/faq-natural-gas-weekly-options.html ;
  https://www.cmegroup.com/education/courses/introduction-to-natural-gas/natural-gas-calendar-spread-options.html ;
  https://www.cmegroup.com/articles/whitepapers/trading-energy-calendar-spread-options.html ;
  https://www.cmegroup.com/clearing/files/margins-on-options.pdf ;
  https://www.cmegroup.com/markets/energy/natural-gas/natural-gas.margins.html ;
  https://www.tradestation.com/pricing/exchange-execution-and-clearing-fees/ ;
  https://databento.com/datasets/GLBX.MDP3/options/LNE
