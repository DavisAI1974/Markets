# FLOW_CALENDAR_NOTES_S98 - feed F (family CAL) build notes

Built 2026-07-20. Module: `research/kalshi/flow_calendar.py` (standalone, additive; nothing
existing edited). Store: `data/flow_calendar/flow_calendar.json` (365 rows, 2025-09-01 ..
2026-08-31, one row per calendar date; 52 EIA releases). `flow_calendar_asof(date)` returns the
row, or None outside the span. Deterministic, zero market data. `--selftest` PASS (all
assertions; full output includes the per-instance cross-check tables below). NOT committed
(builder discipline).

## 1. Sources fetched (URLs) and what each verified

| source | URL | verified |
|---|---|---|
| EIA WNGSR release schedule | https://ir.eia.gov/ngs/schedule.html (fetched twice, second pass verbatim) | Thursday 10:30 ET standard + the full 2025-2026 holiday-exception table (9 rows, 4 in-span) |
| NYMEX NG contract text mirror | https://www.tkfutures.com/natural_gas.htm | futures: "Trading terminates three business days prior to the first calendar day of the delivery month"; options: "Trading terminates at the close of business on the business day immediately preceding the expiration of the underlying natural gas futures contract" |
| EIA NYMEX table definitions | https://www.eia.gov/dnav/ng/TblDefs/ng_pri_fut_tbldef2.asp | independent corroboration: "Natural gas contracts expire three business days prior to the first calendar day of the delivery month" |
| S&P GSCI methodology (Jun-2021 edition, mirror) | https://etn.daishin.com/e5_data/mboard/etn_product/2022/09/40_00_5100201%20%EC%A7%80%EC%88%98%EC%82%B0%EC%B6%9C.pdf | roll period text verbatim: first day = 5th S&P GSCI business day, fractions 80/20, 60/40, 40/60, 20/80, 0/100 through the 9th; NG contract-expiration months = ALL TWELVE (G H J K M N Q U V X Z F); NG RPDW 3.24 percent (2021); "S&P GSCI Business Day. A day on which the indices are calculated, as determined by the NYSE Euronext Holiday & Hours schedule" |
| BCOM methodology PDF | https://assets.bbhub.io/professional/sites/10/BCOM-Methodology.pdf | glossary verbatim: "'Roll Period' means ... the sixth Business Day through and including the tenth Business Day of each month"; RW array {1,1,1,1,1,.80,.60,.40,.20,0} (20 percent/day BD6-10); "'Hedge Roll Period' means ... the fifth Business Day through and including the ninth Business Day"; "'Business Day' means any day on which the sum of the CIPs for those Index Commodities that are open for trading is greater than 50%"; Table 2: NG is a component (NYMEX Henry Hub); Table 9 NG lead months Mar/Mar/May/May/Jul/Jul/Sep/Sep/Nov/Nov/Jan/Jan; NG target weight ~7.94 percent (2025) |
| AMP Futures repost of CME Christmas 2025 schedule | https://www.ampfutures.com/news/christmas-holiday-trading-schedule | Dec 24 early close; Dec 25 day session closed, night session reopens 17:00 CT; Dec 26 regular |
| Broker/search mirrors of CME 2026 MLK/Presidents advisories | (CME advisory PDFs are on the blocked host; mirrored content via search) | Monday-holiday pattern: partial Globex session, early halt, "prices carried forward from the prior day", i.e. no settlement cycle - not a business day |
| Repo: Databento definition expirations | `data/contract_structure/NG_instrument_map.json.gz` (read-only) | authoritative CME-origin expiration dates for 157 NG outrights (NGZ25..2038) |
| Repo: per-date structure store | `data/contract_structure/NG_structure.json` (read-only) | per-date calendar_front symbol/expiry for 101 sessions 2025-11-03..2026-02-27 |
| Repo: tape-derived sessions | `data/contract_structure/NG_sessions.json` (read-only) | empirical session classes: Thanksgiving 2025 traded 14.4k front-contract trades (partial session); Christmas 174 / New Year's 411 (evening-reopen only, i.e. full closure); day-after-Thanksgiving 33.6k (business day) |

Unreachable from this environment (all named, none silently substituted):
- `cmegroup.com` - ECONNRESET on every path tried (contract specs page, rulebook chapter
  220/370 PDFs, holiday calendar). The futures/options termination rules therefore rest on the
  NYMEX text mirror + EIA definitions page + the Databento definition reproduction (below),
  which is CME-origin data already in the repo.
- `web.archive.org` - blocked by the fetch tool.
- `spglobal.com` methodology and 2026-weights PDFs - HTTP 403. Current-edition GSCI text
  could not be fetched; the Jun-2021 edition mirror was used and the roll rule additionally
  corroborated by search snippets of the April-2026 edition. The GSCI roll window has not
  changed between those editions.
- `sec.gov` (iShares GSG prospectus, for current weights) - HTTP 403.

## 2. Every rule: verified vs assumed

| rule as given in the spec | status |
|---|---|
| NG futures expiry = 3rd-last business day of month prior | VERIFIED (two independent text sources) and VALIDATED against Databento definitions: the derivation reproduces 145/157 listed expiries, including ALL 12 whose expiry falls inside the engine's holiday-table coverage (through Oct 2026); the 12 beyond-coverage disagreements are each the finite-holiday-table boundary (section 3a) |
| NG options expire the business day BEFORE futures expiry | VERIFIED from the NYMEX text mirror ("business day immediately preceding the expiration of the underlying"). NOT cross-checkable in-repo: the S97 definitions pull was futures-parent only (zero LN/ON instruments in the map). Flagged for feed I (options surface) to confirm empirically from GLBX option definitions. Derived anchors: opex(NGG26) = 2026-01-27, opex(NGH26) = 2026-02-24 |
| bidweek = final 5 business days of the month | AS SPECCED (a convention, not an exchange rule). Computed on the CME energy calendar; cash bidweek follows the NAESB/NGI convention, identical over this span (caveat 4c) |
| GSCI roll = business days 5-9, 20 percent/day | VERIFIED verbatim from the methodology. NG present with all 12 contract months (rolls every month). NOTE: an intermediate web-search summary claimed NG "rolls only to the January contract annually" - REFUTED by the methodology's own contract-expiration table; recorded here as a caught misstatement |
| BCOM roll = business days 6-10, 20 percent/day | VERIFIED verbatim (Roll Period BD6-10). ADDITION from the same document: the "Hedge Roll Period" - where the hedge FLOW executes - is BD5-9, overlapping the GSCI window; exposed as `in_bcom_hedge_roll`. NG held months Jan/Mar/May/Jul/Sep/Nov, so NG roll FLOW months are Feb/Apr/Jun/Aug/Oct/Dec (`bcom_ng_roll_this_month`), plus the January rebalance (`bcom_january_rebalance`) |
| EIA release = published schedule incl. holiday shifts | VERIFIED from the published page; the four in-span exceptions are encoded as data (section 4). Two of them break the naive rules: Veterans Day (a TUESDAY holiday) slips the release to FRIDAY, and Christmas slips it LATE to Monday Dec 29, not early to Dec 24 |
| CME holiday / early-close flags | VERIFIED by triangulation (repo tape + definition reproduction + schedule mirrors); cmegroup.com itself unreachable, named. Three-class model: full_closure (Christmas, New Year's Day, Good Friday), partial_session (Labor/Thanksgiving/MLK/Presidents/Memorial/Juneteenth/Jul-3-observed; Globex trades short, NO settlements, NOT business days), early_close (day after Thanksgiving, Christmas Eve; full business days) |

The Thanksgiving-class business-day exclusion is not an assumption: reproducing NGZ25 =
2025-11-25 (and NGZ26 = 2026-11-25, NGZ27 = 2027-11-26 from the definitions map) REQUIRES
excluding Thanksgiving from the count in three separate years; including it derives the wrong
date in all three.

## 3. Disagreements found (per instance, none silently resolved)

### 3a. Derived rule vs Databento definition expirations (157 contracts compared)

- In-coverage (expiry through 2026-10-31, i.e. every contract the span can touch plus two
  beyond): 12 contracts, ZERO disagreements (NGZ25 2025-11-25, NGF26 2025-12-29, NGG26
  2026-01-28, NGH26 2026-02-25, NGJ26 2026-03-27, NGK26 2026-04-28, NGM26 2026-05-27, NGN26
  2026-06-26, NGQ26 2026-07-29, NGU26 2026-08-27, NGV26 2026-09-28, NGX26 2026-10-28).
- Beyond coverage: 12 disagreements, ALL explained by the engine's holiday table ending
  2026-09 (missing future Thanksgiving/Memorial-Day/Good-Friday instances), and all carrying
  the mechanical missing-holiday signature (definition EARLIER than derived - a missing
  holiday can only push the derived date later): NGZ26 (Thanksgiving 2026-11-26), NGM27
  (Memorial 2027-05-31), NGM28 (Memorial 2028-05-29), NGJ29 (Good Friday 2029-03-30), NGZ30
  (Thanksgiving 2030-11-28), NGZ31 (Thanksgiving 2031-11-27), NGM32/33/34/38 (Memorial),
  NGZ36/37 (Thanksgiving). The definitions are authoritative for those dates; this feed never
  serves them (outside span).
- NAMED GAP: NGV25 (derived 2025-09-26) and NGX25 (derived 2025-10-29) - the front contracts
  for Sep/Oct 2025, the first two span months - are derivation-only; the instrument map starts
  at NGZ25 so no definition cross-check exists for them. The rule they rest on is the one
  validated 12/12 in-coverage.

### 3b. This feed vs data/contract_structure/NG_structure.json (101 session rows)

97/101 dates agree on the calendar-front symbol; expiry VALUES agree on every date where the
symbols agree; the late-Feb rows carry NGH26 expiry 2026-02-25 exactly as derived (the S97
handoff's "Feb 25 2026 expiry" is CONFIRMED - no disagreement to report on the anchor).

Four per-instance front-symbol offsets, all the same convention difference, none an expiry
disagreement: 2025-11-26 (feed NGF26 vs store NGZ25), 2025-12-30 (NGG26 vs NGF26), 2026-01-29
(NGH26 vs NGG26), 2026-02-26 (NGJ26 vs NGH26). The structure store keys state as-of the PRIOR
close, so it shows the old front for one session after expiry (its own days_to reads -1 on
those rows). This feed is a pure calendar: the front rolls the calendar day after expiry.
Wiring note: both conventions are internally consistent; the offset matters only if someone
joins the two front symbols on those four dates.

### 3c. This feed vs forecast_harness._HOLIDAYS (read-only reference; parsed textually, not imported)

The dict's tags describe session LIQUIDITY; this feed's classes describe business-day /
settlement status. Two lenses on the same days - reported, dict untouched:

- CONSISTENT on all 14 in-span dict entries under that reading (selftest prints the full
  table). The substantive differences a naive reader should know:
  - 2026-05-25 Memorial Day and 2026-06-19 Juneteenth: dict says "closed"; CME Globex energy
    actually trades a partial no-settlement session on these (the S96 Thanksgiving correction
    - "it is NOT closed" - generalizes to every Monday-class federal holiday). For
    business-day counting both readings exclude the day, so no downstream number changes.
  - 2026-07-03 Independence Day observed: dict says "early_close"; CME treats it as a HOLIDAY
    (partial session, no settlements, NOT a business day). This one DOES change counting:
    this feed excludes it from business days (so the Jul-2026 GSCI window is Jul 8-14, not
    Jul 7-13). `contract_structure.py`'s own CME_HOLIDAYS set (read-only, checked) agrees
    with this feed, not with the dict's tag.
  - 2025-10-13 Columbus Day, 2025-11-11 Veterans Day, 2025-12-31 NYE: dict "thin" = liquidity
    observations; all three are NORMAL CME business days (feed agrees; Veterans Day 2025
    empirically traded and sits in the structure store).
  - Coverage note, not a disagreement: the dict starts 2025-10-13; this feed's span starts
    2025-09-01 and carries Labor Day 2025 (2025-09-01, partial_session), which the dict does
    not cover.

## 4. EIA release table findings (the blind-wall-relevant part)

Standard rule (from the page): Thursday 10:30 a.m. ET. In-span exceptions, all from the
published schedule, never assumed:

| release | time ET | displaced from | reason |
|---|---|---|---|
| Fri 2025-11-14 | 10:30 | Thu 2025-11-13 | Veterans Day (a TUESDAY holiday still slips the release) |
| Wed 2025-11-26 | 12:00 | Thu 2025-11-27 | Thanksgiving (selftest anchor - asserted) |
| Mon 2025-12-29 | 12:00 | Thu 2025-12-25 | Christmas (slips LATE across the weekend) |
| Wed 2025-12-31 | 12:00 | Thu 2026-01-01 | New Year's Day (pulled a day early) |

Consequences encoded per-date: the Mon-Sun week of 2025-12-22 has NO release; the week of
2025-12-29 has TWO (Mon covers week ending 2025-12-19, Wed covers week ending 2025-12-26 -
week attribution follows the NOMINAL Thursday, which the ordered sequence confirms). Monday
federal holidays do NOT move the release (no exceptions listed for Labor/Columbus/MLK/
Presidents/Memorial weeks; 2025's Juneteenth shifted because it fell on a Thursday, 2026's
falls on a Friday so Thu 2026-06-18 stands). Out-of-span exceptions on the same page (Jan 3 /
Jan 8 / Jun 18 2025; Nov 13 / Nov 25 2026) were checked for pattern consistency and left out
of the store.

Time stamps carry explicit ET offsets (-04:00/-05:00 by the span's DST dates). The 12:00-noon
time on Wednesday/Monday shifts is from the schedule page itself, as is the 10:30 on the
Friday shift.

## 5. Field notes (what the agent sees)

Per date: `front_symbol_calendar`, `futures_expiry_date`, `days_to_futures_expiry` (business
days, date-exclusive/target-inclusive - the `contract_structure.business_days_between`
convention; 0 on expiry day), `is_expiry_day`; `options_expiry_date`, `days_to_opex` (-1 on
the futures expiry day - opex has passed), `is_opex_day`; `in_bidweek` + `bidweek_day_n` (1-5)
+ `bidweek_delivery_month`; `business_day_of_month`; `in_gsci_roll` + `gsci_roll_day_n` (1-5,
day n = 20n percent rolled) + `gsci_ng_roll_this_month` (constant True - NG rolls every
month); `in_bcom_roll` + `bcom_roll_day_n` + `in_bcom_hedge_roll` (BD5-9) +
`bcom_ng_roll_this_month` (Feb/Apr/Jun/Aug/Oct/Dec) + `bcom_january_rebalance`;
`eia_storage_release_datetime_et` + `eia_releases_this_week` (list; empty for the no-release
week, two entries for the double week) + `is_eia_print_day` + `next_eia_release_datetime_et` +
`days_to_next_eia_release`; `is_cme_business_day`, `cme_holiday`, `cme_holiday_name`,
`cme_session_class` (full_closure | partial_session | early_close | None), `cme_early_close`.
Not-applicable is None throughout; outside-span asof is None.

G13 sanity picture (the reason this feed exists): the Feb-2026 block carries GSCI roll Feb
6-12, BCOM roll Feb 9-13 (an NG roll-flow month, Mar->May), bidweek Feb 23-27, opex Feb 24,
futures expiry Feb 25, and normal Thursday prints Feb 19/26 - all visible per-date.

## 6. Honest caveat list

a. CME primary documents unreachable (ECONNRESET); the termination rules rest on two
   independent text mirrors plus the definitions reproduction. Strong, but the current CME
   rulebook text itself was never read in this build.
b. The OPTIONS rule has no in-repo empirical validation yet (no LN/ON definitions in the
   map). Feed I's GLBX options pull should assert `option_expiry == prev_business_day
   (futures_expiry)` per month and report any instance where CME's actual listing disagrees.
c. Bidweek is computed on the CME calendar; the cash market's NAESB business-day calendar is
   the true convention. Over this span the two are identical (the NAESB holiday set for
   these dates matches the CME closed+partial set on month-end windows - checked by
   inspection of the affected month-ends: Nov 2025 is the only month whose bidweek window
   contains a holiday). A span crossing a divergent holiday would need the distinction.
d. GSCI business days follow the NYSE calendar ("NYSE Euronext Holiday & Hours schedule");
   BCOM's is the >50 percent-of-CIP-open rule; this feed uses the CME-energy calendar for
   both. All three calendars coincide on every in-span date (the ten closed/partial dates are
   NYSE holidays too, and Columbus/Veterans days are open on all three), so the windows are
   exact for this span; the equivalence is span-local, not general.
e. Index weights are context, not fields: GSCI NG RPDW 3.24 percent is the 2021 edition
   (current 2026 announcement PDF 403s - the number in force today was NOT retrieved);
   BCOM NG ~7.94 percent is the 2025 target from the methodology PDF. Window mechanics, which
   ARE the fields, do not depend on the weights.
f. Exact early-close minute times are not encoded (flags + classes only); the partial-session
   halt times (roughly 13:00-13:30 ET, product-dependent) were seen only via mirrors and are
   not load-bearing for any field.
g. The engine's holiday table extends only to 2026-09-07 (deliberately: one verified entry
   past the span so late-August days_to counts to NGV26's Sep-28 expiry are correct). Expiry
   derivations beyond that boundary are wrong-by-construction where a future holiday
   intervenes (section 3a) and are never served by the feed.
h. The EIA schedule page could in principle be revised by EIA mid-year (it carries a
   subject-to-change note); the store snapshots it as fetched 2026-07-20. A re-run of
   `--build` after any EIA schedule revision is the refresh path, and the four encoded
   exceptions are already-past events unlikely to change.
i. `datetime_et` strings use fixed numeric offsets from a span-local DST table (correct for
   2025-09..2026-08); reusing the module outside the span would need the table extended.
