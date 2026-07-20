# EIA BALANCE OPTIONS - THE FULL SWEEP (S98, 2026-07-20)

Greg's question: "is there nothing in the EIA docs that can fill our need?" Context: feed N measured
that the FREE weekly NG supply/demand balance LEVELS (the NGWU's S&P-sourced section) died
2025-10-02, leaving the walked winter (Nov 2025 - Feb 2026) with no free weekly balance levels.
This sweep covers EVERYTHING EIA publishes, at any cadence, that fills or partially fills a
walked-winter balance need. INVESTIGATION ONLY - nothing here was built or wired. This document is
an INPUT to the S99 paid-data discussion, not a recommendation to buy or skip vendor data.

Method: live EIA Open Data v2 API walk (real key, every natural-gas route to its leaves + steo +
electricity/rto + petroleum spot-checks + the v2 root), the STEO archive vintage files themselves
(seven workbooks downloaded and parsed), and Wayback captures of the live pages (release dates as
mid-winter visitors actually saw them). Working evidence in scratchpad `eia_sweep/` (session-local,
not committed): route JSONs, the seven `*_base.xlsx` vintages, `steo_vintages.json`, Wayback HTML.

ZERO SYNTHETIC doctrine applied throughout: every value below is labeled MEASUREMENT (survey data),
ESTIMATE (model/indicator-anchored, method named), or FORECAST. Nothing is interpolated.

---

## 1. THE HEADLINE FIND: STEO MONTHLY VINTAGES - A FROZEN AS-OF BALANCE READ FOR EVERY WINTER DECISION DAY

The Short-Term Energy Outlook publishes, EVERY MONTH, the complete U.S. natural gas balance -
dry production, marketed production BY BASIN (Appalachia/Permian/Haynesville/Eagle Ford/Bakken/
rest - the Drilling Productivity Report's successor series live here), consumption by sector
(residential/commercial/industrial/electric power/lease+plant/pipeline/vehicle), LNG gross
exports/imports, pipeline gross exports/imports, net storage withdrawals, and end-of-month working
inventory BY STORAGE REGION (the five WNGSR regions + AK) - monthly history plus the current month
and a ~2-year forecast. And EIA ARCHIVES EVERY MONTHLY VINTAGE as a frozen workbook.

### 1a. Routes (all verified live 2026-07-20)

- API: `https://api.eia.gov/v2/steo/data/` - **CURRENT VINTAGE ONLY** (measured: the route's only
  facet is `seriesId`; there is no vintage dimension). 1,469 series, 158 `NG*`. Useful for the
  live-forward layer, USELESS for as-of reads: every value is today's revision.
- Archives: `https://www.eia.gov/outlooks/steo/archives/{mon}{yy}_base.xlsx` (e.g.
  `jan26_base.xlsx`), ~1.06-1.09 MB each, one per monthly issue. Direct GET works with a browser
  User-Agent (the bare listing page 403s from this environment; the files themselves serve fine).
  Each workbook: a `Dates` sheet (forecast month, modeling-completion date, table beginning month)
  + per-table sheets; **Table 5a (`5atab`) = the NG balance, series IDs in column A, monthly
  columns from 2021-01 or 2022-01** (per-vintage - read the `Dates` sheet, do not assume). All
  seven walked-winter vintages downloaded and parsed end-to-end.

### 1b. Release mechanics (the blind wall), MEASURED

Official release dates read from Wayback captures of the live STEO landing page (the dates
visitors saw, not inferred):

| vintage | forecast completed | OFFICIAL release date | note |
|---|---|---|---|
| Sep 2025 | Sep 4 | Tue **Sep 9, 2025** | |
| Oct 2025 | Oct 2 | Tue **Oct 7, 2025** | published DURING the shutdown |
| Nov 2025 | Nov 6 | Wed **Nov 12, 2025** | slipped ~1 week, landed the day the shutdown ended |
| Dec 2025 | Dec 4 | Tue **Dec 9, 2025** | |
| Jan 2026 | Jan 8 | Tue **Jan 13, 2026** | |
| Feb 2026 | Feb 5 | Tue **Feb 10, 2026** | |
| Mar 2026 | Mar 9 | Tue **Mar 10, 2026** | |

**The STEO published straight through the walked winter - the shutdown did not break the series**
(contrast: COT suspended Oct 1 - Nov 12; the NGWU S/D section died outright; the NGM skipped an
issue - section 2). Blind-wall rule for any future feed: `knowable_from = official release date +
1 day` (releases are ~noon ET; the +1 convention matches feeds G/N). TRAP, named: the archive
files' HTTP Last-Modified stamps for sep25-dec25 equal the forecast-COMPLETION date, 3-6 days
BEFORE public release - Last-Modified is file-write time, NOT availability evidence. Join on the
official release dates above, never on Last-Modified.

### 1c. What a decision-time agent could have had (the vintage table, extracted from the workbooks)

U.S. dry production `NGPRPUS`, Bcf/d, rows = vintage, columns = data month:

| vintage | 2025-09 | 2025-10 | 2025-11 | 2025-12 | 2026-01 | 2026-02 | 2026-03 |
|---|---|---|---|---|---|---|---|
| sep25 | 106.68 | 106.69 | 106.28 | 106.78 | 107.05 | 105.10 | 106.18 |
| oct25 | 107.59 | 107.72 | 108.17 | 108.80 | 108.71 | 106.85 | 107.68 |
| nov25 | 108.79 | 109.17 | 109.23 | 109.08 | 109.31 | 106.46 | 107.96 |
| dec25 | 108.25 | 109.10 | 110.05 | 110.31 | 109.75 | 108.21 | 108.95 |
| jan26 | 108.27 | 107.19 | 108.28 | 109.46 | 109.22 | 108.38 | 108.75 |
| feb26 | 108.27 | 107.19 | 110.38 | 110.39 | 106.68 | 110.28 | 110.25 |
| mar26 | 108.33 | 107.39 | 110.26 | 111.57 | 108.49 | 110.09 | 109.70 |

Total consumption `NGTCPUS`, Bcf/d:

| vintage | 2025-11 | 2025-12 | 2026-01 | 2026-02 |
|---|---|---|---|---|
| nov25 | 93.09 | 108.82 | 116.72 | 109.05 |
| dec25 | 91.37 | 112.25 | 116.00 | 108.28 |
| jan26 | 91.17 | 109.02 | **115.95** | 108.09 |
| feb26 | 91.73 | 110.03 | **121.90** | 112.93 |
| mar26 | 92.60 | 112.79 | 121.88 | 110.82 |

The Jan-13 -> Feb-10 vintage pair BRACKETS the freeze/squeeze: January consumption re-marked
**+5.95 Bcf/d** (115.95 -> 121.90), residential +2.8 (28.28 -> 31.10), and end-of-January working
inventory re-marked **-137 Bcf** (NGWGPUS 2,609 -> 2,472). The January cold shock enters the STEO
exactly one vintage later - G13's decision days (Feb 15-27) had the post-freeze re-mark in hand;
G11/G12's had the pre-freeze consensus. That evolution is itself signal (the same
first-appearance-vs-revision structure the MOS feed carries), and it is exactly feed-K-class
vintage material - EXCEPT this route has ZERO vintage risk: each issue is a frozen file; the
as-printed record is preserved by construction.

Also per vintage (extracted, in `steo_vintages.json`): by-sector consumption (res/comm/ind/power),
LNG gross exports (`NGEXPUS_LNG`: the jan26 vintage carried Jan at 17.08 Bcf/d), pipeline gross
imports/exports, per-region end-of-month inventories, per-basin marketed production, and (in
table 2, not extracted here) the Henry Hub price path per vintage.

### 1d. Honest labeling

STEO values for months at/after the NGM measurement anchor are **STIFS MODEL ESTIMATES** (EIA's
Short-Term Integrated Forecasting System), anchored on indicator data (weekly storage, 930,
pipeline flows EIA uses internally) - published by EIA, as-printed, but estimates, not survey
measurements. The workbook's own note: historical anchor = "Natural Gas Monthly; and Electric
Power Monthly" databases; the history/estimate break is marked per-cell by gray shading
(machine-recoverable from cell fills if a feed is ever built - a build detail, noted). The `Dates`
sheet's "Last Historical Month" stamp is the model's current-month boundary, NOT the NGM anchor -
e.g. the jan26 vintage stamps 202512 while NGM measurements then extended only through Oct 2025.
Do not confuse the two.

### 1e. Winter coverage verdict

**FILLS the monthly as-of balance need for every walked-winter decision day.** Staleness at block
starts: G11 (Jan 18): Jan-13 vintage, 5 days old, carrying Jan+Feb estimates. G12 (Feb 1): Jan-13
vintage, 19 days old, until Feb 10 mid-block (then 1-3 days old). G13 (Feb 15): Feb-10 vintage,
5 days old, carrying the post-freeze re-mark. Compare: the free weekly balance levels the NGWU
used to carry were 123-155 days stale across the same span. Cadence is MONTHLY - it does not see
week-to-week freeze-offs (that remains feed N's vessel line + LSEG deltas + the 930 estimate
below, or vendor daily data).

---

## 2. NGM / EIA-914 - THE MEASURED MONTHLY LEVELS (candidate 1)

- Routes (all monthly + annual, verified): `natural-gas/prod/sum` (gross withdrawals, marketed,
  dry; 37 duoareas = state-level geography for freeze-off states TX/OK/NM/ND/PA...),
  `natural-gas/cons/sum` (consumption by end-use sector; 52 duoareas), `natural-gas/sum/sndm`
  (**the one-call U.S. monthly supply/disposition balance**: 9 series - dry production, marketed,
  NGPL gaseous equivalent, supplemental, net storage withdrawals, net imports, total consumption,
  balancing item; units Bcf/month), `natural-gas/sum/lsum` (summary), `natural-gas/move/*`
  (imports/exports - section 5/6).
- All end 2026-04 as of today - the API serves the CURRENT (revised) vintage only. As-printed NGM
  vintages would come from archived NGM issue files ("Previous Issues" on the NGM page), unexplored
  - a feed-K-class question if NGM history is ever walked.
- **Release chronology through the winter, MEASURED from Wayback captures of the live NGM page:**

| release | newest data month | lag |
|---|---|---|
| Sep 30, 2025 | Jul 2025 | 2 mo |
| Oct 31, 2025 | Aug 2025 | 2 mo |
| Nov 28, 2025 | Sep 2025 | 2 mo |
| Dec 31, 2025 | Oct 2025 | 2 mo |
| ~Jan 30, 2026 | **ISSUE MISSED** - the Feb 1 capture still shows the Dec 31 issue | - |
| Feb 27, 2026 | Dec 2025 (Nov+Dec landed together - the catch-up issue) | Nov data: 3 mo |
| Mar 31, 2026 | Jan 2026 | 2 mo |

- Winter coverage verdict: **the measured monthly anchor, 2-3 months stale, with a named
  mid-winter skip.** Through ALL of G11 and G12 the freshest NGM-measured month was OCTOBER 2025
  (93+ days old at G12 open); Nov/Dec measurements first became public Feb 27 - the second-to-last
  day of G13. NGM is the RECONCILIATION layer (what the STEO estimates get graded against), never
  a decision-fresh read. Data is survey MEASUREMENT (EIA-914/857 et al.), revised in later issues.

---

## 3. WEEKLY ANYTHING - THE CONFIRMED NEGATIVE (candidate 3)

Measured, by walking every route in the `natural-gas` tree to its leaves: **the ONLY weekly EIA
natural gas series is storage** (`natural-gas/stor/wkly`, the WNGSR, already carried). Prices
under `pri` are daily/monthly (DNAV - feed G carries HH daily). Everything else in the tree -
production, consumption, moves, LNG - is monthly or annual. There is no weekly production,
consumption, LNG, or imports series anywhere in EIA's official statistics.

- WPSR check (Greg asked for the honest negative): the Weekly Petroleum Status Report routes carry
  NO natural gas. Product facet of `petroleum/stoc/wstk` inspected: every "gas" match is motor
  GASOLINE or blending components. (Weekly propane/propylene stocks DO exist there - an NGL,
  heating-adjacent context at most, not the NG balance.)
- The NGWU/WNGSR-Supplement weekly narrative (vessels + LSEG w/w deltas) is feed N's territory and
  remains the only weekly-cadence balance-adjacent vehicle. Its S/D LEVELS are dead as measured
  (NGWU_NOTES_S98.md) - nothing found in this sweep resurrects them.

---

## 4. LNG (candidate 4)

- **Monthly by TERMINAL, free, in the API**: `natural-gas/move/poe2` (exports by point of exit)
  carries **581 LNG series - terminal x destination-country monthly volumes** (Sabine Pass, Corpus
  Christi, Cameron, Calcasieu Pass, Cove Point, Elba Island, Freeport, Plaquemines, Golden Pass as
  they ramp), plus vessel+truck splits. Cadence monthly at NGM lag INCLUDING the winter skip
  (section 2 chronology applies - it is NGM data). Country-level totals: `move/expc`.
- **DOE/FE "LNG Monthly": DISCONTINUED - November 2023 was the final edition** (measured from the
  energy.gov listing page, which now points to EIA). The EIA poe2 route IS the official
  terminal-level record now.
- Faster than monthly, official: **NOTHING.** The weekly vessel-departure line (feed N, both eras)
  and the era-2 LSEG feedgas w/w deltas are the only sub-monthly free reads. The STEO vintage
  carries `NGEXPUS_LNG` as a monthly nowcast at 1-34 day staleness (section 1). Daily feedgas =
  vendor territory (feed J's survey) or the terminal-lateral EBB route (feed J's free arm).
- Winter verdict: terminal-level monthly history EXISTS free for the whole winter (retro), but at
  decision time G11/G12 saw only October terminal data. The balance-slice fill is partial and
  slow; the fast layer stays vendor/EBB.

---

## 5. EIA-930-DERIVED POWER BURN - SIZING THE CONSUMPTION RECOVERY (candidate 5; feed Q's substrate, NOT duplicated here)

- Route verified: `electricity/rto/daily-fuel-type-data` (daily gen by fuel by BA, 2019-01-01 ->
  2026-07-18 = **T+2 observed availability**; hourly variant same family; facets respondent x
  fueltype x timezone). Feed Q owns the build, publication/revision mechanics included.
- **The conversion EIA itself publishes**: the STEO's own pair NGEPCON (power burn, Bcf/d) /
  NGEPGEN_US (gas net generation, billion kWh/month) implies the fleet heat rate. Measured across
  Jul 2025 - Jul 2026 (current vintage): **~7,900 Btu/kWh, stable** (monthly burn/gen ratio 0.243
  - 0.272 Bcf per GWh-day equivalent). Method: `burn_bcfd ~= MWh_per_day x 7900 / 1.035e9`.
  **This is an ESTIMATE with a stated method** (measured MWh x EIA-published implied heat rate),
  never a measurement. Retro grading: EPM/EIA-923 measured monthly power burn
  (`electricity/electric-power-operational-data`, monthly, ends 2026-04) and the STEO's own
  NGEPCON.
- Demonstration on the squeeze window (930 US48 NG, MWh -> estimated Bcf/d): Jan 10: 3.71M MWh ->
  ~28.3; Jan 20: 5.39M -> ~41.1; Jan 25: 5.60M -> ~42.8; Jan 28: 5.46M -> ~41.7. The freeze's
  power-burn ramp (+14 Bcf/d, +50% in two weeks) would have been visible DAILY at T+1-2 through
  the entire squeeze - no other free source sees any demand component at that cadence.
- **How much of the consumption picture it recovers** (shares from the STEO balance, measured):
  power burn = **28.8% of total consumption in Jan 2026, 54.8% in Jul 2025** (the gate's 29-53%
  seasonal band confirmed at 28.8-54.8%). In winter the DOMINANT slice is res/comm (Jan 2026:
  res 31.1 + comm 18.4 = 49.5 Bcf/d = 41% of total, per the feb26 vintage) - and NO free source
  measures it faster than the NGM. Weather (HDD) is its proxy and we already carry weather.
  Verdict: 930 recovers roughly A THIRD of winter demand at daily cadence, the third that swings
  with sun/wind/cold snaps; it recovers none of supply, none of res/comm, none of LNG.

---

## 6. PIPELINE IMPORTS/EXPORTS - CANADA/MEXICO (candidate 6)

- Routes: `natural-gas/move/impc` + `expc` (by country), `poe1` + `poe2` (by border point),
  `move/state`, `move/ist`. All MONTHLY at NGM lag (winter chronology in section 2, skip
  included). **Monthly is the fastest official cadence.** The STEO vintages carry monthly
  nowcasts (`NGIMPUS_PIPE` / `NGEXPUS_PIPE`) at 1-34 day staleness. Sub-monthly border flows =
  pipeline EBBs (feed J machinery) or vendor - not EIA. The NGWU's old Canada/Mexico w/w
  sentences were S&P data and died with the section.

---

## 7. EVERYTHING ELSE CHECKED (named, with disposition)

- `natural-gas/stor/sum`, `/type`, `/cap`, `/lng` (monthly storage detail incl. LNG storage
  adds/withdrawals): monthly complements to the weekly WNGSR; salt/nonsalt already carried by
  `storage_regional.py`. No new winter-fresh content.
- `natural-gas/cons/num`, `/heat`, `/acct`, `/pns`: consumer counts, heat content, delivery
  accounting - structural reference only.
- `natural-gas/enr/*`: annual reserves + drilling activity. Too slow; rejected.
- `natural-gas/prod/whv`, `/wells`, `/ss`, `/pp`, offshore/basin annuals: monthly-to-annual
  structural production detail; `prod/sum` covers the need.
- `natural-gas/pri/fut`: NYMEX futures series DEAD in the API ("Futures prices after April 5,
  2024, are not available" - printed on the route). Spot (DNAV) lives; we carry HH via feed G and
  futures via Databento. No gap for us; named so nobody chases it.
- `total-energy` (Monthly Energy Review): republishes NGM-derived NG tables at equal-or-worse
  lag. Duplicate; rejected.
- **`nuclear-outages` (v2 top-level route) - SIDE FIND FOR FEED R**: daily US/facility/generator
  nuclear capacity-out series, 2007-01-01 -> 2026-07-17, straight from the API (sample verified:
  Jan 15-20 2026 outage 1.8 -> 3.2 GW). Feed R's arm 1 need not scrape NRC pages. Passed to the
  gate, not built here.
- Natural Gas Storage Dashboard (`eia.gov/naturalgas/storage/dashboard/`): a JS app; its daily
  flow/sample panels were S&P-era; the mid-winter Wayback capture renders only the shell, and it
  exposes no retrievable historical archive. Not a data route; status of its S&P panels
  undeterminable from captures; nothing lost - its weekly substance IS the WNGSR we carry.
- RECS/CBECS/MECS + consumption reports: already dispositioned by Greg (structural survey
  reference, no event-time use) - DATA_GATE_S98.md prerequisites note 4.
- EIA release-calendar page: 403s from this environment (as several eia.gov HTML pages do; the
  API and direct file GETs work). Not blocking: every release date used above was measured from
  Wayback captures of the product pages themselves.
- Petroleum tree (WPSR): no NG (section 3). Propane weekly stocks noted as heating-adjacent only.

---

## 8. THE HONEST COMPOSITE - HOW CLOSE FREE EIA GETS TO A WALKED-WINTER BALANCE

Per slice, with cadence and staleness AT DECISION TIME (walked winter):

| balance slice | best free EIA route | cadence | staleness at a winter decision day | label |
|---|---|---|---|---|
| Dry production (US) | STEO vintage `NGPRPUS` | monthly issue | 1-34 d (issue gap, measured) | ESTIMATE (STIFS) |
| Dry production, measured | NGM `prod/sum` / `sndm` | monthly | 62-118 d (Oct data through G11/G12; skip) | MEASUREMENT (revised) |
| Production by basin/state | STEO vintage (basin) / NGM (state) | monthly | as above | ESTIMATE / MEASUREMENT |
| Power burn | 930 x STEO heat rate (feed Q) | DAILY | 1-2 d | ESTIMATE (stated method) |
| Res/comm consumption | STEO vintage `NGRCPUS`+`NGCCPUS` | monthly issue | 1-34 d | ESTIMATE (STIFS); weather = the daily proxy |
| Industrial consumption | STEO vintage `NGINX` | monthly issue | 1-34 d | ESTIMATE (STIFS) |
| Total consumption | STEO vintage `NGTCPUS` | monthly issue | 1-34 d | ESTIMATE (STIFS) |
| LNG exports (feedgas proxy) | STEO `NGEXPUS_LNG` monthly; vessels weekly (feed N); LSEG w/w deltas (era 2) | monthly / weekly | 1-34 d / <=7 d | ESTIMATE / MEASUREMENT (count) / third-party delta |
| LNG by terminal | NGM `move/poe2` | monthly | 62-118 d | MEASUREMENT (revised) |
| Pipeline imports/exports | STEO `NG*PUS_PIPE`; NGM `move/*` | monthly | 1-34 d / 62-118 d | ESTIMATE / MEASUREMENT |
| Storage | WNGSR (carried) + STEO regional month-end path | weekly / monthly | <=6 d / 1-34 d | MEASUREMENT / ESTIMATE |
| The whole balance, one object | STEO vintage Table 5a | monthly issue | 1-34 d (max gap Dec 9 -> Jan 12, measured) | ESTIMATE, as-printed, frozen per issue |

Worked example - G12 day 1 (Sun Feb 1, 2026), what a blind agent could legitimately hold:
- STEO Jan-13 vintage (age 19 d): the full January+February balance consensus - production 109.2,
  total consumption 116.0, power 34.8, res/comm 45.2, LNG exports 17.1 Bcf/d, end-Jan storage
  2,609 Bcf. (Pre-freeze consensus - the re-mark came Feb 10, mid-block.)
- 930-derived power burn (age 1-2 d): the daily freeze ramp, ~28 -> ~43 Bcf/d over the prior
  three weeks. The ONLY daily demand read in existence, free or paid, at this staleness.
- WNGSR (age 3 d): the measured weekly storage draw + salt split (carried).
- Vessel line (age 4 d): 31 vessels/118 Bcf squeeze-week low (carried, feed N).
- NGM measured anchor: October 2025 (age 93 d) - the reconciliation layer only.

**What remains UNFILLABLE without vendor data** (unchanged by this sweep, now with the full free
perimeter measured):
1. WEEKLY or DAILY balance LEVELS - measured dry production, sector consumption, feedgas - for
   Oct 2025 - Feb 2026. Never published free, by anyone, at any point. The S&P weekly estimates
   EIA used to republish are licensing-dead; LSEG era-2 gives deltas only.
2. Daily pipeline-flow-derived production/feedgas nowcasts (the vendor product feed J priced:
   PipeRiv $50-500/mo; Criterion/East Daley/NGI quote-required) - the only route to
   day-resolution supply and LNG demand, historical or live.
3. Res/comm consumption at ANY sub-monthly cadence - vendors model it from weather+flows; free
   data has weather (carried) + the STEO monthly estimate, nothing between.

**The composite's honest reach**: free EIA gives the walked winter a monthly as-of balance
consensus with 1-34 day staleness that reprices ONCE mid-winter (the Jan-13/Feb-10 vintage pair
bracketing the freeze), a daily power-burn estimate covering ~29% (Jan) to ~55% (Jul) of total
consumption, weekly storage, weekly vessel counts, and a 2-3-month-lagged measured reconciliation
layer. It does NOT give week-resolution balance levels - the specific object that died Oct 2 -
and no EIA product at any cadence substitutes for it. Whether that residual gap is worth vendor
money for pass-2's re-reads is exactly the S99 discussion; both sides of that discussion now have
the full free-side inventory.

---

## BUILD FEASIBILITY NOTE (not built - investigation only)

A `steo_vintage_feed` would be small: one XLSX GET per monthly issue (browser UA), parse `Dates` +
`5atab` (series IDs in col A; column origin from the Dates sheet - it CHANGES between vintages,
202101 for sep25-dec25 vs 202201 for jan26+, the one real parse trap, hit and solved in this
sweep's scratch code), join on the measured official release dates (section 1b), `knowable_from =
release + 1`. The as-printed record is frozen by construction - no vintage risk. History/estimate
break per cell recoverable from gray shading if wanted. Everything verified here is reproducible
from the scratchpad evidence.
