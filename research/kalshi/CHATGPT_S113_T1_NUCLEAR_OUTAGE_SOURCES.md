# S113 TASK 1 REPORT

# Forward Nuclear Planned-Outage Schedule Sources

Date: 2026-08-05
Registry item: A-17
Scope: Source and endpoint research only. No thresholds, weights, or fitted coefficients.

## Executive determination

FOUND: There is no single free, public, nationwide, unit-level forward nuclear refueling-outage calendar that can be ingested as a production feed.

The free public source stack is instead:

1. NRC daily unit power status for realized outages and coastdowns.
2. ISO and RTO forward outage totals for aggregate capacity pressure.
3. Licensee and commission documents as irregular manual evidence.
4. EIA-860M as a monthly generator-level calendar for coal retirements and additions.

The main operational consequence is that the public ISO products cannot identify the nuclear unit that is scheduled out. ERCOT, PJM, MISO, and SPP publish aggregate capacity. CAISO publishes a current-trade-date unit snapshot, not a multi-day forward schedule. The non-ISO Southeast has no standardized public equivalent located in this search.

The correct build is therefore two separate fields:

- `forward_outage_capacity`: public, aggregate, ingestible.
- `forward_nuclear_unit_schedule`: unresolved public-data gap, with irregular documents kept in a shadow evidence lane.

Do not infer a unit-level refueling calendar from aggregate outage totals.

## Evidence labels

- FOUND: verified at a followable source.
- SEARCHED AND FOUND NOTHING: official sources were checked and no matching public product was located.
- NOT VERIFIED: a plausible route exists, but the exact claim could not be verified from an official source.

## 1. NRC daily power reactor status

### 1.1 Exact public endpoints

| Purpose | Exact endpoint | Format | Authentication | Cost |
|---|---|---|---|---|
| Product index and archive years | https://www.nrc.gov/reading-rm/doc-collections/event-status/reactor-status/index | HTML | None | Free |
| Rolling last 365 days | https://www.nrc.gov/reading-rm/doc-collections/event-status/reactor-status/PowerReactorStatusForLast365Days.txt | Pipe-delimited text | None | Free |
| Current 2026 year file | https://www.nrc.gov/reading-rm/doc-collections/event-status/reactor-status/2026/2026PowerStatus.txt | Pipe-delimited text | None | Free |
| 1999 archive index | https://www.nrc.gov/reading-rm/doc-collections/event-status/reactor-status/1999/index | HTML | None | Free |
| Example daily detailed report | https://www.nrc.gov/reading-rm/doc-collections/event-status/reactor-status/2026/20260414ps | HTML table | None | Free |
| ADAMS public document search | https://adams-search.nrc.gov/ | Search application | None for public search | Free |

The rolling text file header is exactly:

```text
ReportDt|Unit|Power
```

The file contains one row per reporting date and reactor unit. `Power` is the reported integer unit power level. It is not MW. The NRC archive index links annual pages from 1999 through the current year.

The annual text path is verified for 2026. The apparent reusable pattern is:

```text
https://www.nrc.gov/reading-rm/doc-collections/event-status/reactor-status/YYYY/YYYYPowerStatus.txt
```

Only the 2026 instance was directly verified in this research. An implementation should discover annual links from the NRC index rather than assume every historical year follows the same filename.

### 1.2 History and fields

FOUND:

- Public daily status pages are available back to 1999 from the NRC archive.
- The raw rolling file supplies `ReportDt`, `Unit`, and `Power`.
- The daily HTML page can additionally carry `Down`, `Reason or Comment`, change status, and scram count.
- Daily pages identify realized refueling outages and sometimes a coastdown immediately before an outage.

Example: the NRC report for April 14, 2026 listed several units in a refueling outage and showed Catawba 1 in coastdown to a refueling outage:
https://www.nrc.gov/reading-rm/doc-collections/event-status/reactor-status/2026/20260414ps

### 1.3 What this source cannot do

The NRC daily status product is realized or near-real-time operating status. It does not provide a planned start date and planned end date months ahead.

A coastdown comment may provide a short lead immediately before the shutdown. It is not a substitute for a 12-month planned calendar.

### 1.4 Recommended ingest contract

```text
source: NRC_POWER_REACTOR_STATUS
report_date
unit_name_raw
unit_name_normalized
reported_power_pct
down_date
reason_comment
is_refueling_outage
is_coastdown_to_refueling
publication_url
retrieved_at_utc
```

`down_date`, `reason_comment`, and the derived flags require the detailed daily HTML page. They are not in the three-column raw text file.

## 2. Licensee refueling schedules

## 2.1 What is verified

FOUND: licensees plan refueling outages well in advance.

Duke Energy states that outage preparation begins about three years ahead and that the actual outage schedule is created around 12 months before the outage:
https://nuclear.duke-energy.com/2022/03/09/five-things-you-didnt-know-about-the-refueling-outage-scheduling-group

This verifies internal planning lead time. It does not provide public unit dates.

FOUND: NRC ADAMS is a public searchable repository for official agency records:
https://adams-search.nrc.gov/

NRC documents can contain references to upcoming outages, inspection planning, or outage work. No structured ADAMS dataset or mandatory public field containing every unit's planned refueling start and end dates was found.

FOUND: some utilities announce scheduled outages when they begin and when they finish. TVA's 2026 press-release archive includes start and completion notices for scheduled refueling outages:
https://www.tva.com/news-media/releases/press-release-archive

Those notices are useful for realized-event validation. They do not solve the long-lead forward requirement.

FOUND: state commission records can contain outage-related filings, but access and content are inconsistent.

Georgia's official filing schedule requires investor-owned utilities to file monthly generating-plant outage reports in a public-disclosure copy and a trade-secret copy:
https://psc.state.ga.us/exsec/OfficialFilingSchedule.htm

The filing schedule does not promise a machine-readable forward unit calendar, and it explicitly contemplates confidential material.

The South Carolina Public Service Commission has docketed individual nuclear outage matters, including a V.C. Summer refueling-outage accrual proceeding:
https://dms.psc.sc.gov/Web/Dockets/Detail/117509

That is an episodic regulatory filing, not a standardized recurring calendar feed.

## 2.2 Honest finding

SEARCHED AND FOUND NOTHING:

No official nationwide rule or public endpoint was located that requires every commercial reactor licensee to publish exact planned refueling start and end dates 12 to 18 months ahead.

The statement "licensees file refueling schedules" must therefore be qualified:

- Licensees plan the outages internally.
- They submit outage information to grid operators and regulators.
- Public disclosure varies by operator, ISO, commission, and document.
- Exact unit dates may be delayed, redacted, aggregate, or absent.
- No production-grade public national feed was found.

## 2.3 Recommended treatment

Do not make irregular utility announcements or commission filings the authoritative production calendar.

Use them as a shadow evidence lane:

```text
source_document_type
utility
plant
unit
claimed_start_date
claimed_end_date
publication_date
date_precision
source_url
public_or_confidential
machine_readable
verification_status
```

A unit date should not become production-authoritative unless it is supported by a dated public document and reconciles with the relevant ISO aggregate.

## 3. ISO and RTO forward outage products

## 3.1 ERCOT

### Exact endpoints

Product page:
https://www.ercot.com/mp/data-products/data-product-details?id=NP3-233-CD

Current API endpoint:
https://api.ercot.com/api/public-reports/np3-233-cd/hourly_res_outage_cap

Product metadata:
https://api.ercot.com/api/public-reports/np3-233-cd

Archive endpoint:
https://api.ercot.com/api/public-reports/archive/np3-233-cd

Developer documentation:
https://developer.ercot.com/applications/pubapi/user-guide/using-api/

Registration:
https://developer.ercot.com/applications/pubapi/user-guide/registration-and-authentication/

Known limits:
https://developer.ercot.com/applications/pubapi/known-limits/

### Coverage

FOUND:

- Product: NP3-233-CD, Hourly Resource Outage Capacity.
- Horizon: next 168 hours.
- Granularity: hourly.
- Update frequency: hourly.
- Content: approved and accepted planned, forced, and maintenance outages, including full outages and derates.
- Geography: aggregated by ERCOT load zone.
- Public file types: ZIP, CSV, and XML.
- Public API activation included NP3-233-CD.
- API access requires an ERCOT registration, a subscription key, and a bearer token.
- API limit: 30 requests per minute.
- Historic file downloads are limited to 1,000 files at once.
- Pre-API history is available as historic files and retained for at least seven years.

### Nuclear usefulness

The product is not unit-level and does not identify fuel type. It cannot state that a particular nuclear unit is scheduled out.

Verdict: useful as an aggregate Texas capacity calendar, not as a nuclear schedule.

## 3.2 PJM

### Exact endpoints

Feed definition:
https://dataminer2.pjm.com/feed/frcstd_gen_outages/definition

REST route:
https://api.pjm.com/api/v1/frcstd_gen_outages

Data Miner information and terms:
https://www.pjm.com/markets-and-operations/etools/data-miner-2.aspx

Official Data Directory description:
https://www.pjm.com/markets-and-operations/data-dictionary.aspx

Official confidentiality statement:
https://www.pjm.com/markets-and-operations/etools/data-miner-2/data-availability.aspx

### Coverage

FOUND:

- Product: PJM Forecasted Generation Outages.
- Horizon: next three months, commonly described as 90 days.
- Granularity: one expected MW total per day.
- Geography: PJM RTO and subregional totals.
- Update: daily.
- Automation: PJM account required for API use.
- Non-member API rate: six data connections per minute.
- PJM states that Data Miner data is for internal use and redistribution is prohibited without the required PJM membership or redistribution license.
- PJM explicitly states that individual generator outages are generally confidential and only aggregate outage information is released.

The maintained `gridstatus` implementation cross-checks these feed fields:

```text
forecast_execution_date_ept
forecast_date
forecast_gen_outage_mw_rto
forecast_gen_outage_mw_west
forecast_gen_outage_mw_other
```

Implementation cross-check:
https://opensource.gridstatus.io/en/latest/_modules/gridstatus/pjm.html

The field list above was not independently rendered from PJM's JavaScript feed-definition page during this research. Treat it as implementation-verified rather than primary-page-verified.

### Nuclear usefulness

PJM's public product is aggregate and cannot identify the nuclear unit. PJM's own data-availability policy confirms that unit outage information is confidential.

Verdict: valuable 90-day aggregate capacity pressure, unusable as a public unit calendar.

## 3.3 MISO

### Exact endpoints

Official public API index:
https://public-api-ci.misoenergy.org/

Generation outage endpoint:
https://public-api-ci.misoenergy.org/api/GenerationOutages/GetGenerationOutagesPlusMinusFiveDays

### Coverage

FOUND from the endpoint response:

- Window: five days before through five days after the reference date.
- Granularity: daily.
- Fields: `OutageDate`, `OutageMonthDay`, `Unplanned`, `Planned`, `Forced`, and `Derated`.
- Geography: MISO-wide aggregate.
- Format: JSON.
- Authentication: none observed for the public endpoint.
- Cost: no fee observed.
- License or reuse terms: not verified in this research.

### Nuclear usefulness

The endpoint has no plant, unit, fuel, or region field. It is aggregate.

Verdict: useful for MISO aggregate outage pressure across a short forward window, not a nuclear schedule.

## 3.4 SPP

### Official publication

Portal page:
https://portal.spp.org/pages/capacity-of-generation-on-outage

Official SPP description:
https://portal.spp.org/groups/operations

SPP describes the product as a seven-day outlook of MW of generation on outage by fuel type, including submitted CROW outages and resources offered with commit status `OUTAGE`.

### Raw download pattern

The official portal is JavaScript-driven and did not expose the raw URL pattern in its page text. The maintained `gridstatus` adapter documents the public file-browser route as:

```text
https://portal.spp.org/file-browser-api/download/capacity-of-generation-on-outage?path=/YYYY/MM/Capacity-Gen-Outage-YYYYMMDD.csv
```

Annual archive pattern:

```text
https://portal.spp.org/file-browser-api/download/capacity-of-generation-on-outage?path=/YYYY/YYYY.zip
```

Implementation source:
https://opensource.gridstatus.io/en/stable/_modules/gridstatus/spp.html

### Coverage

FOUND:

- Horizon: next seven days.
- Granularity: hourly.
- Breakdown: fuel type.
- Publication: daily, described by the maintained adapter as 8:00 a.m. Central.
- Format: CSV, with annual ZIP archives.
- Authentication: none indicated for the public file browser.
- Cost: free public portal access.
- License or reuse terms: not verified in this research.

### Nuclear usefulness

SPP is more useful than the other aggregate products because it separates outage capacity by fuel type. It still does not identify a plant or unit.

Verdict: should be ingested as a nuclear-fuel aggregate where the file's fuel label confirms that category, but it cannot become a unit schedule.

## 3.5 CAISO

### Exact public page

https://www.caiso.com/market-operations/outages/curtailed-and-non-operational-generators

### Coverage

FOUND:

- CAISO publishes a daily list of visible California power plants that are not operational because of planned or unplanned outages.
- The main report is a snapshot for the current trade date, anticipated around 8:30 a.m. Pacific.
- It includes units visible to CAISO across CAISO, BANC, TIDC, LADWP, and IID.
- The page warns that the list is incomplete where CAISO lacks visibility and that conditions can change.
- This is a web-published report, not a verified public API.
- No public multi-day forward generation-outage calendar equivalent to the ERCOT, PJM, MISO, or SPP products was found.

Verdict: unit-level current status, not a forward schedule.

## 3.6 Non-ISO Southeast

Units and regions of interest include TVA, Southern Company, Duke Energy Carolinas, Duke Energy Progress, Dominion Energy South Carolina, and Florida utilities.

SEARCHED AND FOUND NOTHING:

No centralized free public product was located that provides standardized forward generating-unit outage dates across the non-ISO Southeast.

What exists is fragmented:

- TVA announces scheduled nuclear outages through press releases, often at commencement and completion:
  https://www.tva.com/news-media/releases/press-release-archive
- Georgia requires monthly plant outage reports, but the filing process includes a trade-secret copy and does not provide a standardized API:
  https://psc.state.ga.us/exsec/OfficialFilingSchedule.htm
- South Carolina dockets can contain outage-specific proceedings, but they are episodic:
  https://dms.psc.sc.gov/Web/Dockets/Detail/117509

This is the largest unresolved geographic gap for a unit-level forward nuclear calendar.

## 4. Coal retirements and additions

## 4.1 EIA-860M

### Exact endpoints

Product page:
https://www.eia.gov/electricity/data/eia860m/index.php

Latest file verified for June 2026:
https://www.eia.gov/electricity/data/eia860m/xls/june_generator2026.xlsx

EIA explanation of workbook content:
https://www.eia.gov/pressroom/releases/press572.php

Survey description:
https://www.eia.gov/Survey/

### Coverage

FOUND:

- Frequency: monthly.
- Format: XLSX workbook.
- Authentication: none.
- Cost: free.
- Population: generators at plants with at least 1 MW of combined nameplate capacity.
- Status: preliminary; EIA may revise later inventories without a separate correction notice.
- `Operating` tab: operating generators and a planned retirement date where applicable.
- `Planned` tab: proposed generators, technology, energy source, capacity, planned operation timeframe, and project status.
- `Retired` tab: comprehensive retirements since 2002 in monthly files from March 2017 onward.
- EIA states these are estimates and are not capacity commitments by the facilities.
- EIA-860M is published as a workbook. A machine-readable EIA API route for the complete 860M workbook was not verified.

### Recommended coal calendar extraction

Filter the current workbook to coal units by the workbook's energy-source and technology fields, then emit:

```text
plant_code
generator_id
plant_name
state
county
technology
energy_source_code
nameplate_mw
summer_capacity_mw
operating_status
planned_retirement_date
planned_operation_date
report_month
source_workbook
retrieved_at_utc
```

Do not assume that a reported planned date is firm. Preserve report month and compare revisions from one monthly workbook to the next.

## 5. Source comparison

| Source | Forward horizon | Granularity | Unit-level | Nuclear-specific | Machine-readable | Auth | Build value |
|---|---:|---|---|---|---|---|---|
| NRC raw status | None | Daily | Yes | Yes | Text | None | Realized truth and coastdown detection |
| NRC daily HTML | None | Daily | Yes | Yes | HTML scrape | None | Reason and down-date validation |
| ERCOT NP3-233-CD | 168 hours | Hourly | No | No | API, CSV, XML, ZIP | Registration and tokens | Aggregate Texas outage pressure |
| PJM forecast outages | 90 days | Daily | No | No | API and UI export | PJM account for API | Longest public aggregate horizon |
| MISO plus/minus five days | 5 forward days | Daily | No | No | JSON | None observed | Short aggregate calendar |
| SPP capacity on outage | 7 days | Hourly | No | Fuel-type aggregate | CSV and ZIP | None indicated | Aggregate nuclear-fuel outage capacity |
| CAISO C&NOG | Current trade date | Snapshot | Yes where visible | Fuel must be joined | Web report | None | Current unit status only |
| Southeast utility and PSC documents | Irregular | Document event | Sometimes | Sometimes | Mostly HTML or PDF | Usually none | Shadow evidence only |
| EIA-860M | Monthly near-term calendar | Monthly | Yes | All fuels | XLSX | None | Coal additions and retirements |

## 6. Recommended implementation order

### P0

1. Ingest NRC rolling raw text daily.
2. Crawl the detailed NRC daily page for `Down` and `Reason or Comment`.
3. Ingest ERCOT NP3-233-CD.
4. Ingest PJM `frcstd_gen_outages`.
5. Ingest the MISO public JSON endpoint.
6. Ingest SPP's seven-day fuel-type outage CSV.
7. Ingest EIA-860M monthly and maintain a revision history.

### P1

1. Add the CAISO current-day unit snapshot as realized validation.
2. Create a document-watch lane for TVA, Georgia PSC, South Carolina PSC, Florida PSC, Duke, Southern Nuclear, and Dominion.
3. Link each aggregate outage curve to realized NRC unit outages after the fact to measure how much of each aggregate change was nuclear.

### Do not build as production authority

- A calendar inferred solely from typical 18- or 24-month refueling cycles.
- Unit dates inferred from aggregate ISO MW totals.
- Exact dates extracted from undated commentary or vendor calendars without a primary public document.
- A nationwide licensee schedule represented as public and complete.

## 7. Acceptance tests

1. NRC parser reads the literal header `ReportDt|Unit|Power`.
2. Annual discovery starts from NRC archive links rather than hardcoding all year filenames.
3. Every record preserves publication and retrieval timestamps.
4. ERCOT adapter fails closed when token or subscription-key authentication is absent.
5. PJM adapter preserves internal-use and redistribution restrictions in source metadata.
6. MISO adapter records that the product is MISO-wide aggregate and daily.
7. SPP adapter records fuel type and never maps aggregate nuclear MW to a specific unit.
8. CAISO adapter labels the data current-trade-date only.
9. EIA-860M adapter stores every monthly vintage and does not overwrite prior planned dates.
10. `forward_nuclear_unit_schedule` remains explicitly unavailable unless a public unit-date document exists.

## 8. Final build decision

A-17 should not be closed as "forward nuclear unit schedule solved."

It can be split into:

- A-17A: Public aggregate forward outage calendar. Buildable now from ERCOT, PJM, MISO, and SPP.
- A-17B: Public unit-level nuclear refueling calendar. Still an open measured data gap.
- A-17C: Realized nuclear outage truth. Buildable now from NRC.
- A-17D: Coal additions and retirements calendar. Buildable now from EIA-860M.

The forward calendar class is real and valuable. The public data resolution is lower than the original task assumed.
