# Historical data for Frankie's 13 points on the 30 experiment days (2026-09-29)

Greg, 2026-09-29: "find the historical data that Frankie wants for the days it just picked. Some of this is hourly
data, some isn't." "We'll give him storage for 11 points." "it's 12 now." "We'll do est vs actual storage numbers."
"everyone who sees his ingest should see these data points too." "He'll get the futures curve shape too." "We're trying
to make correlations and the best trade signals we can. I'm not concerned about him having trade curves."

The days: the 30 of `DAY_SELECTION_20260929.md` (2021-10-05 .. 2025-10-21, Tue/Wed, late September and October). Each is
a trading day: it opens 18:00 ET the prior calendar day (22:00Z) and halts 17:00 ET (21:00Z).

Status: PLAN plus fetch code; nothing fetched, nothing dispatched, no S3 write, nothing from Databento.
Built in this change: `operations/fetch_day_history.py` (plan / canary / fetch), its offline output
`blocks/DAY_HISTORY_AVAILABILITY_20260929.json` (when each value became public, per day), the workflow
`.github/workflows/frankie_day_history.yml` (canary and fetch on a GitHub runner, upload under a NEW S3 prefix), and a
one-line span fix in `research/kalshi/cot_feed.py` (the pull starts in 2018; section 1).

## 0. The short answer

- **In hand now (committed or computed from the calendar):** point 6, `squeeze_watch.sessions_since_prompt_expiry`,
  for all 30 days (a calendar count, in section 2). The publication time of every weekly value per day (COT report
  and its release, the storage print before the open and the next one, the MOS cycles public at the open and those
  arriving during the day): `blocks/DAY_HISTORY_AVAILABILITY_20260929.json`.
- **On S3 already (by the committed records; not listed from here, the container has no AWS access):**
  the EIA weekly storage actuals (object `eia/eia_surprise.json`, built from the EIA API's full weekly history);
  the storage ESTIMATE for the five 2025 prints the 2025 days touch (store `consensus/`, TradingEconomics + investing
  captures, Aug 2025 - Mar 2026); the DAILY EIA-930 store (`grid_stack/`, 2019 onward; daily, not hourly); the daily
  gas-weighted degree-day store for the 2025 days (`weather/nws_temp/`, from about 2025-06-25); the COT stores
  (`cot/`, built from 2019, see point 4 for why that is short for 2021).
- **Free to fetch (public, no charge):** COT from CFTC (points 1, 3, 4, 8), MOS every cycle from the IEM archive
  (points 2, 9), EIA-930 HOURLY from the EIA API (points 5, 7; key = the repository secret `EIA_API_KEY`, else
  EIA's public `DEMO_KEY`, rate-limited), hourly station observations from IEM (point 10), EIA weekly storage and its
  as-printed page (point 11), and Wayback captures that MAY hold the street estimate for the 16 prints of 2021-2024
  (point 12; whether a capture exists for each print is only known after the canary).
- **Costs money:** only point 13, the futures curve: the back months are not in our pull (the 5-year MBO pull is
  `NG.v.0`, one instrument per partition). Databento, estimated (not quoted) in section 1, point 13.
- **Does not exist for these days:** the street ESTIMATE is not free anywhere except archived web captures; weeks
  with no capture have none (listed per print after the canary). No as-first-published vintage exists for EIA-930 hourly
  (the API serves today's revision). The COT reports of 2025-09-30, 10-07 and 10-14 did not exist on the 2025 days (the
  shutdown; published 2025-11-19 to 12-02), so those days see the 2025-09-23 report, 3 to 24 days old: a real stale
  reading, listed, not a gap. The analyst count and survey range of the estimate are not archived anywhere free.
- **Not reachable from this container:** every public host (IEM, CFTC, EIA, NOAA, Wayback, ForexFactory, investing)
  is refused by the session's egress proxy (organization policy, HTTP 403 on CONNECT). So the 1-2 minute probes are
  written, not run: `frankie_day_history.yml action=canary` runs them on a GitHub runner (the runners reach these hosts;
  `free_ng_collectors.yml` and `frankie_g3_s130_hydrate.yml` already do).

Codes in the tables: H in hand; S on S3 already (by committed record); F free to fetch; W free IF a Wayback capture
exists (unknown until the canary); P paid (Databento); M missing.

## 1. The 13, in Greg's order

Each value carries the time it became public. A trading day sees a value from that time on: at its open if it was
public before 22:00Z the prior day, or at the moment it arrived during the day. Nothing is rolled up; nothing averaged.

### 1. `cot.managed_money_net_pctile_1y`  |  3. `cot.managed_money_net_chg_wow`  |  4. `cot.managed_money_net_pctile_3y`  |  8. `cot.ice.ld1.managed_money_net_pctile_1y`
- Source: CFTC Disaggregated COT, futures-only, annual archives `https://www.cftc.gov/files/dea/history/fut_disagg_txt_<YEAR>.zip`
  (free; Cloudflare 403s a Python user agent, `cot_feed.py` sends a browser one). Contract codes: `023651` NYMEX NG;
  `023391` ICE LD1 (point 8); the feed also builds `023392`, `0233AG`, `0233AH`.
- Native resolution: weekly (positions as of Tuesday). The percentiles and week-over-week change are the feed's own
  per-report derivations on the report's trailing window (a per-report reading, not an average across days).
- Published: the Friday after, 15:30 ET, delayed a business day per federal holiday; the 2025 shutdown table
  (`cot_feed.PUBLICATION_OVERRIDES`, the CFTC's catch-up schedule) replaces the rule for 2025-09-30 .. 12-23 reports.
  Per day: section 2. No COT report is published inside a Tue/Wed trading day.
- Feed: `research/kalshi/cot_feed.py --build` (builds all five served codes). It was built for the 2025-26 walk, and
  its span was the one problem: BUILD_YEARS started in 2019, and MIN_OBS_3Y = 140 of about 156 weeks would have served
  a 3-year percentile for the 2021 days off about 143 weeks (a window starting in 2019, not 2018) as if it were whole.
  FIXED here: the pull starts in 2018; no later value changes. The 1y window needs 52 weeks before the report (fine).
  ICE LD1 history before 2021 in the disaggregated file: to confirm in the canary (a code with too little history gets
  None, never a truncated percentile).
- S3: `cot/` (built from 2019; replace it only on Greg's word, the fetch writes to the new prefix).
- Cost: free. Fetch: `fetch_day_history.py fetch --family cot` (calls `cot_feed.build(years=2018..2025)` per code).

### 2. `weather_forecast.forecast_gw_hdd`  |  9. `model_disagreement.summary.max_abs_spread_gw_hdd`
- Source: NWS MOS point forecasts, IEM archive `https://mesonet.agron.iastate.edu/cgi-bin/request/mos.py`
  (`station=K<metro>&model=GFS|NAM|MEX&sts=&ets=&format=csv`), back to about 2000, free. The 16 gas-weighted metros of
  `nws_temp_feed.STATION_WEIGHTS_RAW`.
- Native resolution: per model CYCLE (00/06/12/18Z runtime), each with its forecast temperatures (3-hourly GFS/NAM,
  12-hourly MEX). The raw rows (runtime, valid time, temperature) are kept whole; `forecast_gw_hdd` per cycle and
  the GFS-vs-NAM spread per matched horizon are computed by the existing code, never averaged across cycles.
- Published: runtime + about 3.2-4.0 h; the feeds use runtime + 4.5 h (`mos_cycle_feed.DISSEM_LAG_H`, conservative; IEM
  does not keep dissemination stamps). So at a day's open (22:00Z) the latest cycle is the prior day's 12Z; the 18Z,
  00Z, 06Z and 12Z cycles arrive DURING the day (section 2 lists them per day). Note: `nws_temp_feed`'s own as-of wall
  (runtime <= D-1 23:59Z) is a different, looser convention; the day file stamps each cycle with runtime + 4.5 h.
- Feeds: `nws_temp_feed.fetch_mos` (raw), `nws_temp_feed.build_mos_asof` / `mos_cycle_feed.py` (per cycle) and
  `model_disagreement.py` (the spread; reads the raw cache, no network). Span problems: `mos_cycle_feed` loads normals
  for 2025-09-01..2026-09-01 only (its `vs_normal` would be None on 2021-2024 days; the gw_hdd itself is unaffected);
  `build_mos_asof` OVERWRITES its index (the documented builder trap), so the fetch saves the raw files only, under the
  same file names `load_mos_cached` uses, and the per-cycle values are computed from them once, into the day file.
- S3: the raw MOS cache on S3 covers 2025-10-29 .. 2026-03-09 (`mos_cycle_feed` docstring): none of the 30 days.
- Cost: free (48 requests per year window). Fetch: `--family mos`.

### 5. `grid_stack.bas.US48.wind_mwh`  |  7. `grid_stack.bas.US48.est_gas_burn_bcfd`
- Source: EIA-930 via EIA API v2, `https://api.eia.gov/v2/electricity/rto/fuel-type-data` (net generation by fuel)
  and `.../region-data` (demand, day-ahead demand forecast, net generation, interchange), `frequency=hourly` (UTC), for
  US48 and the six BAs `grid_stack` carries (ERCO, CISO, MISO, PJM, SWPP, SOCO). Needs a key: the repository secret
  `EIA_API_KEY` (used by `free_ng_collectors.yml`); `DEMO_KEY` works rate-limited. No key is in this container.
- Native resolution: hourly. `est_gas_burn_bcfd` is an ESTIMATE per hour: gas MWh in that hour x 24 x 7,900 Btu/kWh
  / 1.035e9 (grid_stack's stated method, heat rate from the STEO pair), labelled as such.
- Published: an hour appears about an hour after it ends (nominal; EIA does not stamp first publication in the API).
  The API serves the CURRENT revision: the value first published is not recoverable anywhere (named, not solved).
  The feed's daily wall (period + 2 days) is for the daily routes.
- Feed: `grid_stack.py` pulls the DAILY routes only (2019 onward; on S3 as `grid_stack/`). No hourly path exists, so
  `fetch_day_history.py --family eia930` adds one (same respondents, same API, hourly), for the 8 days before each
  trading day through its halt (the 7-day change some plays name).
- Cost: free. Fetch: `--family eia930` (420 requests; with DEMO_KEY expect throttling, so use the secret).

### 6. `squeeze_watch.sessions_since_prompt_expiry`
- Pure calendar: business days since the most recent NG last trade date before the day (`forecast_harness`'s rule,
  `flow_calendar.ng_expiry` / `bd_between`). Values in section 2 (2 to 17). In hand. `flow_calendar`'s CME holiday table
  covers 2025-2027 only; no CME holiday falls between a late-September expiry and these days in 2021-2024 (Columbus
  Day trades), so the count holds. Not price-derived. The OTHER squeeze_watch fields (`active`,
  `calendar_front_next_spread`) are price-derived: they need the front and next settlements (point 13's data).

### 10. `weather.gw_hdd` (observed)
- Source: NWS ASOS hourly observations, IEM `https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py`, free, the 16
  weighted metros plus the extra stations `nws_temp_feed.RAW_STATIONS` carries.
- Native resolution: every observation (hourly routine plus specials), all fields verbatim
  (`nws_temp_feed.fetch_asos_raw`). The daily gas-weighted `gw_hdd` is the feed's daily index (gas day = America/Chicago
  calendar day); the hourly rows stay in the file beside it.
- Published: an observation is public minutes after its time (routine METARs at about :51-:56). The daily gw_hdd of a
  gas day exists when that day ends: at a trading day's open (22:00Z = 17:00 CT) the last complete gas day is D-2; D-1's
  completes at 05:00Z during the day.
- S3: `weather/nws_temp/` daily store starts about 2025-06-25 (so the 2025 days' daily index is there);
  `weather/nws_hourly/` coverage is not in any committed record. 2021-2024: fetch.
- Cost: free. Fetch: `--family weather_obs` (Sep and Oct of each year, per station per month).

### 11. EIA weekly storage: level, weekly change, vs 5-year
- Source: EIA API v2 `natural-gas/stor/wkly`, series `NW2_EPG0_SWO_R48_BCF` (Lower 48, Bcf), free (key as above); the
  as-printed report page `ir.eia.gov/ngs/ngs.html` via Wayback (the market saw the as-printed number; the API carries
  revisions, `storage_vintage.py` explains the 1-3 Bcf differences).
- Native resolution: weekly (week ending Friday). Weekly change = level minus prior level; vs 5-year = level minus the
  same ISO week's level in the prior five years, as `forecast_harness._storage_series` computes (EIA prints its own
  5-year figure in the report; the as-printed capture carries it).
- Published: Thursday 10:30 ET; no Tue/Wed trading day contains a print. Per day, the print before the open and the
  next print: section 2. No holiday moved an October 2021-2025 print (Columbus Day Monday does not).
- S3: `eia/eia_surprise.json` (the national actuals, current vintage). Fetch: `--family storage` (current vintage) and
  `--family consensus` (which also takes the Wayback captures of the EIA page: the as-printed values).

### 12. Storage estimate vs actual
- Prints the 30 days touch (the print before each open and the next one): 21 Thursdays - 2021: 09-30, 10-07, 10-14,
  10-21; 2022: 09-29, 10-06, 10-13, 10-20; 2023: 09-28, 10-05, 10-12, 10-19; 2024: 09-26, 10-03, 10-10, 10-17; 2025:
  09-25, 10-02, 10-09, 10-16, 10-23.
- 2025 (5 prints): IN HAND on S3 (`consensus/`, `storage_consensus.py`; `STORAGE_CONSENSUS_NOTES_S98.md` table):
  09-25 +75 (TE, investing; pre-print +76), 10-02 +67 (pre +66), 10-09 +76 (pre +76), 10-16 +81 (pre +76; investing
  kept 76), 10-23 +83 (pre +78). Each with capture time; as-printed actuals beside them.
- 2021-2024 (16 prints): no store. The same method that built 2025 is the free route: Wayback captures of
  TradingEconomics `united-states/natural-gas-stocks-change` and investing.com event 386 (www, es, mx) in the week
  around each print. `--family consensus` lists every capture per print (CDX) and saves the raw pages; extraction of the
  numbers from those pages is the next build, once the real HTML is seen (the 2025 extraction was done by hand; no
  committed parser exists). A print with no capture is MISSING (listed by print).
- Published: the estimate is public before the print (surveys and calendars post Mon-Wed; captures carry their own
  time); the actual at 10:30 ET Thursday. A Tue/Wed day can see the estimate of its NEXT print forming during the day.
- Not free: the Reuters poll and WSJ survey (paywalled, unarchived), The Desk LDC survey, TradingEconomics' API
  history (a paid tier; no price in any repo record). The analyst count and range: none free.
- Cost: free (Wayback). Fetch: `--family consensus`.

### 13. The futures curve shape (`curve_regime`, `curve_slope_1`, `curve_slope_back`, `curve_curvature`, front-next spread incl. the calendar-front pair)
- What exists: `contract_structure.py` (fields as named; reads `data/contract_structure/NG_statistics_raw.json.gz`
  settlements + OI and `NG_instrument_map.json.gz` definitions) and `forward_curve.py` (Databento `NG.c.0..c.11`
  ohlcv-1d). On S3: `nymex/contract_structure/` and `nymex/nymex_curve/`, built for the 2025-26 walk (the S101 pull
  runs from about July 2025): they MAY cover the 2025 days as DAILY settles; nothing for 2021-2024. Our MBO pull is
  `NG.v.0` only, so no back month is in hand for any day.
- A leak found on the way: `forward_curve.py` treats the ohlcv-1d close as the settle. A Databento daily bar is a UTC
  day, so its close is at 00:00Z = 20:00 ET, two hours INTO the next trading day. Under the time-only guard such a
  value has no honest single stamp; use the statistics settlements (stamped by their receive time) instead.
- What Greg allows (2026-09-29): the curve is treated like the front month's MBO: every value up to each decision's
  cutoff, including the back months trading during the day. That needs intraday back-month data: Databento only.
- Options, all GLBX.MDP3, symbols `NG.FUT` (stype_in `parent`: every listed month and the calendar spreads), per
  trading day its two partitions (the 46 UTC days of `DAY_SELECTION_20260929.md`), NOT pulled, prices ESTIMATED from
  our own committed quotes (not a Databento quote; `metadata.get_cost` needs the key, which is not here):
  | schema | what it gives | estimate for the 46 partitions | basis |
  |---|---|---|---|
  | `statistics` + `definition` | settlements (with receive time), open interest, the instrument map | under $1 | S101: a year of NG+CL statistics and definitions incl. options, with n0/n1 trades, cost $1.10 in total |
  | `ohlcv-1m` (or `ohlcv-1s`) | an intraday curve per minute (second) per month | under $1 (1m); low single dollars (1s) | bars are a small fraction of the trades |
  | `trades` / `tbbo` | every trade per month (tbbo adds the top of book at each trade) | about $1-7 | front-month trades are a few percent of its MBO records; all months a few times that |
  | `mbp-1` | every top-of-book change per month | about $8-30 | a large fraction of MBO messages |
  | `mbo` | full depth, all months, the same as Frankie's ingest | about $16-55 | our 5-year `NG.v.0` quote: $145.74 for 26.58 GB = about $5.48 per stored GB; these 46 partitions are 0.99 GB = about $5.43 for the FRONT month; all months and spreads taken as 3-10x the front (a guess, not measured) |
  The statistics+definition pull alone gives the settled curve (daily, stamped) and feeds squeeze_watch's price
  pieces; any one intraday schema adds the back months during the day. Greg decides; the quote comes from
  `metadata.get_cost` with a hard ceiling before any pull, as the 5-year workflow did.
- Guard (time only, spec 2d7313bd): every curve value carries its own timestamp (the statistics message's receive
  time; for intraday schemas the record's receive time); the one as-of reader refuses anything past the cutoff; staging
  names any value without a stamp; the search's leakage gate covers the curve fields.

## 2. Per day

### When each value became public (computed offline; `blocks/DAY_HISTORY_AVAILABILITY_20260929.json`)

| Day | COT report visible at open (published ET, age d) | Storage print before open / next print | sessions_since_prompt_expiry (H) | MOS cycles public at open / arriving in the day |
|---|---|---|---|---|
| 2021-10-05 | 2021-09-28 (2021-10-01 15:30, 3.1) | 2021-09-30 / 2021-10-07 | 5 (since NGV21 2021-09-28) | 10-03 18Z,10-04 00Z,10-04 06Z,10-04 12Z / 10-04 18Z,10-05 00Z,10-05 06Z,10-05 12Z |
| 2021-10-06 | 2021-09-28 (2021-10-01 15:30, 4.1) | 2021-09-30 / 2021-10-07 | 6 (since NGV21 2021-09-28) | 10-04 18Z,10-05 00Z,10-05 06Z,10-05 12Z / 10-05 18Z,10-06 00Z,10-06 06Z,10-06 12Z |
| 2021-10-12 | 2021-10-05 (2021-10-08 15:30, 3.1) | 2021-10-07 / 2021-10-14 | 10 (since NGV21 2021-09-28) | 10-10 18Z,10-11 00Z,10-11 06Z,10-11 12Z / 10-11 18Z,10-12 00Z,10-12 06Z,10-12 12Z |
| 2021-10-13 | 2021-10-05 (2021-10-08 15:30, 4.1) | 2021-10-07 / 2021-10-14 | 11 (since NGV21 2021-09-28) | 10-11 18Z,10-12 00Z,10-12 06Z,10-12 12Z / 10-12 18Z,10-13 00Z,10-13 06Z,10-13 12Z |
| 2021-10-19 | 2021-10-12 (2021-10-15 15:30, 3.1) | 2021-10-14 / 2021-10-21 | 15 (since NGV21 2021-09-28) | 10-17 18Z,10-18 00Z,10-18 06Z,10-18 12Z / 10-18 18Z,10-19 00Z,10-19 06Z,10-19 12Z |
| 2022-10-04 | 2022-09-27 (2022-09-30 15:30, 3.1) | 2022-09-29 / 2022-10-06 | 4 (since NGV22 2022-09-28) | 10-02 18Z,10-03 00Z,10-03 06Z,10-03 12Z / 10-03 18Z,10-04 00Z,10-04 06Z,10-04 12Z |
| 2022-10-05 | 2022-09-27 (2022-09-30 15:30, 4.1) | 2022-09-29 / 2022-10-06 | 5 (since NGV22 2022-09-28) | 10-03 18Z,10-04 00Z,10-04 06Z,10-04 12Z / 10-04 18Z,10-05 00Z,10-05 06Z,10-05 12Z |
| 2022-10-11 | 2022-10-04 (2022-10-07 15:30, 3.1) | 2022-10-06 / 2022-10-13 | 9 (since NGV22 2022-09-28) | 10-09 18Z,10-10 00Z,10-10 06Z,10-10 12Z / 10-10 18Z,10-11 00Z,10-11 06Z,10-11 12Z |
| 2022-10-12 | 2022-10-04 (2022-10-07 15:30, 4.1) | 2022-10-06 / 2022-10-13 | 10 (since NGV22 2022-09-28) | 10-10 18Z,10-11 00Z,10-11 06Z,10-11 12Z / 10-11 18Z,10-12 00Z,10-12 06Z,10-12 12Z |
| 2022-10-18 | 2022-10-11 (2022-10-14 15:30, 3.1) | 2022-10-13 / 2022-10-20 | 14 (since NGV22 2022-09-28) | 10-16 18Z,10-17 00Z,10-17 06Z,10-17 12Z / 10-17 18Z,10-18 00Z,10-18 06Z,10-18 12Z |
| 2022-10-19 | 2022-10-11 (2022-10-14 15:30, 4.1) | 2022-10-13 / 2022-10-20 | 15 (since NGV22 2022-09-28) | 10-17 18Z,10-18 00Z,10-18 06Z,10-18 12Z / 10-18 18Z,10-19 00Z,10-19 06Z,10-19 12Z |
| 2023-10-03 | 2023-09-26 (2023-09-29 15:30, 3.1) | 2023-09-28 / 2023-10-05 | 4 (since NGV23 2023-09-27) | 10-01 18Z,10-02 00Z,10-02 06Z,10-02 12Z / 10-02 18Z,10-03 00Z,10-03 06Z,10-03 12Z |
| 2023-10-04 | 2023-09-26 (2023-09-29 15:30, 4.1) | 2023-09-28 / 2023-10-05 | 5 (since NGV23 2023-09-27) | 10-02 18Z,10-03 00Z,10-03 06Z,10-03 12Z / 10-03 18Z,10-04 00Z,10-04 06Z,10-04 12Z |
| 2023-10-10 | 2023-10-03 (2023-10-06 15:30, 3.1) | 2023-10-05 / 2023-10-12 | 9 (since NGV23 2023-09-27) | 10-08 18Z,10-09 00Z,10-09 06Z,10-09 12Z / 10-09 18Z,10-10 00Z,10-10 06Z,10-10 12Z |
| 2023-10-11 | 2023-10-03 (2023-10-06 15:30, 4.1) | 2023-10-05 / 2023-10-12 | 10 (since NGV23 2023-09-27) | 10-09 18Z,10-10 00Z,10-10 06Z,10-10 12Z / 10-10 18Z,10-11 00Z,10-11 06Z,10-11 12Z |
| 2023-10-17 | 2023-10-10 (2023-10-13 15:30, 3.1) | 2023-10-12 / 2023-10-19 | 14 (since NGV23 2023-09-27) | 10-15 18Z,10-16 00Z,10-16 06Z,10-16 12Z / 10-16 18Z,10-17 00Z,10-17 06Z,10-17 12Z |
| 2023-10-18 | 2023-10-10 (2023-10-13 15:30, 4.1) | 2023-10-12 / 2023-10-19 | 15 (since NGV23 2023-09-27) | 10-16 18Z,10-17 00Z,10-17 06Z,10-17 12Z / 10-17 18Z,10-18 00Z,10-18 06Z,10-18 12Z |
| 2024-10-01 | 2024-09-24 (2024-09-27 15:30, 3.1) | 2024-09-26 / 2024-10-03 | 3 (since NGV24 2024-09-26) | 09-29 18Z,09-30 00Z,09-30 06Z,09-30 12Z / 09-30 18Z,10-01 00Z,10-01 06Z,10-01 12Z |
| 2024-10-02 | 2024-09-24 (2024-09-27 15:30, 4.1) | 2024-09-26 / 2024-10-03 | 4 (since NGV24 2024-09-26) | 09-30 18Z,10-01 00Z,10-01 06Z,10-01 12Z / 10-01 18Z,10-02 00Z,10-02 06Z,10-02 12Z |
| 2024-10-08 | 2024-10-01 (2024-10-04 15:30, 3.1) | 2024-10-03 / 2024-10-10 | 8 (since NGV24 2024-09-26) | 10-06 18Z,10-07 00Z,10-07 06Z,10-07 12Z / 10-07 18Z,10-08 00Z,10-08 06Z,10-08 12Z |
| 2024-10-09 | 2024-10-01 (2024-10-04 15:30, 4.1) | 2024-10-03 / 2024-10-10 | 9 (since NGV24 2024-09-26) | 10-07 18Z,10-08 00Z,10-08 06Z,10-08 12Z / 10-08 18Z,10-09 00Z,10-09 06Z,10-09 12Z |
| 2024-10-15 | 2024-10-08 (2024-10-11 15:30, 3.1) | 2024-10-10 / 2024-10-17 | 13 (since NGV24 2024-09-26) | 10-13 18Z,10-14 00Z,10-14 06Z,10-14 12Z / 10-14 18Z,10-15 00Z,10-15 06Z,10-15 12Z |
| 2024-10-16 | 2024-10-08 (2024-10-11 15:30, 4.1) | 2024-10-10 / 2024-10-17 | 14 (since NGV24 2024-09-26) | 10-14 18Z,10-15 00Z,10-15 06Z,10-15 12Z / 10-15 18Z,10-16 00Z,10-16 06Z,10-16 12Z |
| 2025-09-30 | 2025-09-23 (2025-09-26 15:30, 3.1) | 2025-09-25 / 2025-10-02 | 2 (since NGV25 2025-09-26) | 09-28 18Z,09-29 00Z,09-29 06Z,09-29 12Z / 09-29 18Z,09-30 00Z,09-30 06Z,09-30 12Z |
| 2025-10-01 | 2025-09-23 (2025-09-26 15:30, 4.1) | 2025-09-25 / 2025-10-02 | 3 (since NGV25 2025-09-26) | 09-29 18Z,09-30 00Z,09-30 06Z,09-30 12Z / 09-30 18Z,10-01 00Z,10-01 06Z,10-01 12Z |
| 2025-10-07 | 2025-09-23 (2025-09-26 15:30, 10.1) | 2025-10-02 / 2025-10-09 | 7 (since NGV25 2025-09-26) | 10-05 18Z,10-06 00Z,10-06 06Z,10-06 12Z / 10-06 18Z,10-07 00Z,10-07 06Z,10-07 12Z |
| 2025-10-08 | 2025-09-23 (2025-09-26 15:30, 11.1) | 2025-10-02 / 2025-10-09 | 8 (since NGV25 2025-09-26) | 10-06 18Z,10-07 00Z,10-07 06Z,10-07 12Z / 10-07 18Z,10-08 00Z,10-08 06Z,10-08 12Z |
| 2025-10-14 | 2025-09-23 (2025-09-26 15:30, 17.1) | 2025-10-09 / 2025-10-16 | 12 (since NGV25 2025-09-26) | 10-12 18Z,10-13 00Z,10-13 06Z,10-13 12Z / 10-13 18Z,10-14 00Z,10-14 06Z,10-14 12Z |
| 2025-10-15 | 2025-09-23 (2025-09-26 15:30, 18.1) | 2025-10-09 / 2025-10-16 | 13 (since NGV25 2025-09-26) | 10-13 18Z,10-14 00Z,10-14 06Z,10-14 12Z / 10-14 18Z,10-15 00Z,10-15 06Z,10-15 12Z |
| 2025-10-21 | 2025-09-23 (2025-09-26 15:30, 24.1) | 2025-10-16 / 2025-10-23 | 17 (since NGV25 2025-09-26) | 10-19 18Z,10-20 00Z,10-20 06Z,10-20 12Z / 10-20 18Z,10-21 00Z,10-21 06Z,10-21 12Z |

Every day also sees, from its open: the hourly observations and EIA-930 hours as they arrive (22:00Z D-1 to 21:00Z D),
the storage estimate of its next print as it forms, and (point 13, if bought) the curve up to each cutoff.

### Coverage per day and point

| Day | 1 cot 1y | 2 MOS fHDD | 3 cot wow | 4 cot 3y | 5 930 wind | 6 since expiry | 7 930 burn | 8 ICE LD1 1y | 9 MOS spread | 10 obs gw_hdd | 11 storage actual | 12 est vs actual | 13 curve |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2021-10-05 | F | F | F | F | F; daily S | H = 5 | F; daily S | F | F | F | S + F | W | P |
| 2021-10-06 | F | F | F | F | F; daily S | H = 6 | F; daily S | F | F | F | S + F | W | P |
| 2021-10-12 | F | F | F | F | F; daily S | H = 10 | F; daily S | F | F | F | S + F | W | P |
| 2021-10-13 | F | F | F | F | F; daily S | H = 11 | F; daily S | F | F | F | S + F | W | P |
| 2021-10-19 | F | F | F | F | F; daily S | H = 15 | F; daily S | F | F | F | S + F | W | P |
| 2022-10-04 | F | F | F | F | F; daily S | H = 4 | F; daily S | F | F | F | S + F | W | P |
| 2022-10-05 | F | F | F | F | F; daily S | H = 5 | F; daily S | F | F | F | S + F | W | P |
| 2022-10-11 | F | F | F | F | F; daily S | H = 9 | F; daily S | F | F | F | S + F | W | P |
| 2022-10-12 | F | F | F | F | F; daily S | H = 10 | F; daily S | F | F | F | S + F | W | P |
| 2022-10-18 | F | F | F | F | F; daily S | H = 14 | F; daily S | F | F | F | S + F | W | P |
| 2022-10-19 | F | F | F | F | F; daily S | H = 15 | F; daily S | F | F | F | S + F | W | P |
| 2023-10-03 | F | F | F | F | F; daily S | H = 4 | F; daily S | F | F | F | S + F | W | P |
| 2023-10-04 | F | F | F | F | F; daily S | H = 5 | F; daily S | F | F | F | S + F | W | P |
| 2023-10-10 | F | F | F | F | F; daily S | H = 9 | F; daily S | F | F | F | S + F | W | P |
| 2023-10-11 | F | F | F | F | F; daily S | H = 10 | F; daily S | F | F | F | S + F | W | P |
| 2023-10-17 | F | F | F | F | F; daily S | H = 14 | F; daily S | F | F | F | S + F | W | P |
| 2023-10-18 | F | F | F | F | F; daily S | H = 15 | F; daily S | F | F | F | S + F | W | P |
| 2024-10-01 | F | F | F | F | F; daily S | H = 3 | F; daily S | F | F | F | S + F | W | P |
| 2024-10-02 | F | F | F | F | F; daily S | H = 4 | F; daily S | F | F | F | S + F | W | P |
| 2024-10-08 | F | F | F | F | F; daily S | H = 8 | F; daily S | F | F | F | S + F | W | P |
| 2024-10-09 | F | F | F | F | F; daily S | H = 9 | F; daily S | F | F | F | S + F | W | P |
| 2024-10-15 | F | F | F | F | F; daily S | H = 13 | F; daily S | F | F | F | S + F | W | P |
| 2024-10-16 | F | F | F | F | F; daily S | H = 14 | F; daily S | F | F | F | S + F | W | P |
| 2025-09-30 | F | F | F | F | F; daily S | H = 2 | F; daily S | F | F | F; daily S | S + F | S | S daily settles (to confirm) + P intraday |
| 2025-10-01 | F | F | F | F | F; daily S | H = 3 | F; daily S | F | F | F; daily S | S + F | S | S daily settles (to confirm) + P intraday |
| 2025-10-07 | F, stale 10.1 d | F | F, stale | F, stale | F; daily S | H = 7 | F; daily S | F, stale | F | F; daily S | S + F | S | S daily settles (to confirm) + P intraday |
| 2025-10-08 | F, stale 11.1 d | F | F, stale | F, stale | F; daily S | H = 8 | F; daily S | F, stale | F | F; daily S | S + F | S | S daily settles (to confirm) + P intraday |
| 2025-10-14 | F, stale 17.1 d | F | F, stale | F, stale | F; daily S | H = 12 | F; daily S | F, stale | F | F; daily S | S + F | S | S daily settles (to confirm) + P intraday |
| 2025-10-15 | F, stale 18.1 d | F | F, stale | F, stale | F; daily S | H = 13 | F; daily S | F, stale | F | F; daily S | S + F | S | S daily settles (to confirm) + P intraday |
| 2025-10-21 | F, stale 24.1 d | F | F, stale | F, stale | F; daily S | H = 17 | F; daily S | F, stale | F | F; daily S | S + F | S | S daily settles (to confirm) + P intraday |

"Stale" is the shutdown: the newest report public at those opens is 2025-09-23 (published 09-26); it is served with its
age, never hidden and never replaced. W becomes S or M per print once the canary and the fetch list the captures.

## 3. Lower priority (the families the 13 do not already cover; listed, not dropped)

| family | source | native resolution | 2021-2025 route | feed and span |
|---|---|---|---|---|
| weather regime / gw_cdd | same ASOS obs as point 10 | hourly obs, daily index | free, same fetch | `nws_temp_feed.realized_index` |
| solar | computed sun geometry + EIA-930 solar gen | per day (geometry), hourly (gen) | geometry: compute; gen: point 5's fetch | `solar_calendar.py` SPAN is 2025-09-01..2026-12-31 (pure calculation; widen the span) |
| freeze_risk | IEM MOS for four basin stations (MAF, OKC, PIT, SHV) | per cycle | free, IEM | `freeze_risk_feed.py` (reuses `mos_cycle_feed`; October lows are rarely near its 20F bar, still carried) |
| storage_regional | EIA regional + salt/non-salt | weekly | free (EIA xls/API) | `storage_regional.py --build --source xls` (full history) |
| cot combined (futures+options) | CFTC `com_disagg_txt_<YEAR>.zip` | weekly | free | `cot_combined_feed.py` (uses `cot_feed.BUILD_YEARS`, so 2018 now) |
| weather_forecast_cycle | MOS per cycle | per cycle | from point 2's raw | `mos_cycle_feed.py` (normals span, see point 2) |
| steo_vintage, ngwu_balance, options_surface, nuclear_outages, cash_basis | EIA / NRC / Databento | monthly / weekly / daily | per their feeds | not in the 13; not planned here |

## 4. One file per trading day: `FRANKIE_DAY_EXTERNAL_V1` (proposal; readers not wired)

Where: beside the day's sealed ingest, `/opt/frankie-box/work/ingest-<day>-.../day-external.json` (or a sibling
directory the ingest receipt names), its sha256 in `day-external-receipt.json`; built once, read by everyone.

```
{ "schema": "FRANKIE_DAY_EXTERNAL_V1",
  "trading_day": "20211005", "open_utc": "2021-10-04T22:00:00Z", "halt_utc": "2021-10-05T21:00:00Z",
  "sources": { "<source id>": {"url": ..., "retrieved_utc": ..., "vintage": "current|as_printed|archived_capture",
                               "s3_key": ..., "sha256": ...} },
  "points": {                                   # Greg's order; each a list of stamped values, native resolution
    "cot.managed_money_net_pctile_1y": [ {"value": 83.4, "as_of": "2021-09-28", "published_utc": "2021-10-01T19:30:00Z",
                                          "source": "cftc_fut_disagg_2021", "n_obs": 52, "age_days_at_open": 3.1} , ...],
    "weather_forecast.forecast_gw_hdd": [ {"value": 4.2, "runtime_utc": ..., "valid_for": "2021-10-05",
                                          "published_utc": runtime + 4.5 h, "model": "GFS", "metros_present": 16}, ...],
    "grid_stack.bas.US48.wind_mwh": [ {"value": ..., "period_utc": "2021-10-05T13", "published_utc": period end + 1 h,
                                       "vintage": "current"}, ...],
    "weather.gw_hdd": [ ... per gas day ...],  "weather.obs_hourly": [ ... every station observation ... ],
    "storage.actual": [ {"week_ending": ..., "level_bcf": ..., "weekly_chg_bcf": ..., "vs_5yr_bcf": ...,
                         "published_utc": Thu 14:30Z, "vintage": "as_printed|current"} ],
    "storage.estimate": [ {"print": ..., "value_bcf": ..., "house": "tradingeconomics", "captured_utc": ...,
                           "published_utc": captured_utc} ],
    "curve.*": [ ... each with its receive time ... ] },
  "missing": [ {"point": ..., "day": ..., "reason": ...} ] }
```

Rules the file carries (spec 2d7313bd, time-only guard): every value has a `published_utc` (or receive time); the day
file keeps values published before the halt, including the ones that arrive during the day, so each reader cuts at its
own decision time. One as-of reader takes (file, cutoff) and REFUSES (hard error naming the point, the value's time
and the cutoff) any value past the cutoff; staging refuses a value with no stamp and names it; the search's leakage
gate (`odcore/leakage.py`) covers every point, the curve included. A missing value is listed with its day and reason.

Readers (the next build, not done here): (1) the ROOT/derive stage of `frankie_box_experiment_root.py` (the day file
beside the ingest, pinned in the source binding by sha256); (2) the teacher-only step (`frankie_box_experiment_teacher`,
not built) and the BOSS teacher's classroom material; (3) the search's series list (`frankie_box_experiment_search.py`:
each point a series on the day's causal axis, a value existing from its `published_utc`); (4) Jev's material on
classroom-arm days; (5) the orchestrator's `data` stage exports it with the day.

## 5. Order of work (each dispatch on Greg's go)

1. `frankie_day_history.yml action=canary` (a GitHub runner; about 1-2 minutes; prints what each source returns for
   October 2021; writes nothing).
2. `frankie_day_history.yml action=fetch families=calendar,cot,storage,weather_obs,mos,eia930` (free sources; uploads
   to `s3://bento-568968024170-us-east-2-an/frankie/day_history/<run id>/` with a manifest; touches no existing store).
3. `frankie_day_history.yml action=fetch families=consensus` (Wayback; slow on purpose, 1 s between captures). Then
   the extraction of the 2021-2024 estimates from the saved pages (next build), per print, missing ones listed.
4. The day-file builder (`FRANKIE_DAY_EXTERNAL_V1`) and its staging beside each sealed ingest (next build), then the
   reader wiring (section 4).
5. Point 13: Greg picks the schema; a cost quote with a hard ceiling, then the pull.

Local equivalents: `python3.12 research/kalshi/frankie_boss/operations/fetch_day_history.py plan|canary|fetch
--family <list> --out <dir>` (network needed for canary and fetch; `requests` for the families that reuse
`nws_temp_feed`).

## 6. Questions for Greg

1. Point 13: which schema(s) - statistics+definition only (daily settled curve and OI, under $1), an intraday curve
   (ohlcv-1m/1s or trades/tbbo, low dollars), mbp-1, or full MBO for all months (tens of dollars, estimated)?
2. Point 12, 2021-2024: accept the Wayback route (free, coverage unknown per print, missing prints listed), or name a
   paid source?
3. COT: replace the served `cot/` store with the 2018-start build (only 2021-early 2022 percentiles change), or keep the
   new build beside it under `frankie/day_history/`?
4. EIA-930 and storage: the current vintage is all the API gives; the as-printed storage number comes from Wayback. Is
   the current vintage acceptable for EIA-930 hourly (no first-published record exists)?
