# STEO VINTAGE FEED - BUILDER NOTES (feed T, S99, built 2026-07-20)

Module: `research/kalshi/steo_vintage.py`. Store: `data/steo_vintage/` (raw workbooks +
`steo_vintage.json.gz`), S3 prefix `steo_vintage/` (push via platform_sync). Wired into
`forecast_harness.py::decision_state` as block `steo_vintage`; audit-joins class `steo_release`.
Module selftest 22/22 PASS; harness selftest PASS; audit-joins 0 violations / 101 days with the
feed present on all 101.

## WHAT IT IS

The seven walked-winter STEO archive workbooks (sep25..mar26), Table 5a = the complete NG balance
as-of each monthly release, ALL 37 series rows kept per vintage (raw-ingestion discipline).
`steo_vintage_asof(iso)` exposes the latest knowable vintage: curated field set (production,
consumption by sector, LNG/pipeline trade, net withdrawals, working gas), prev/cur/next month
values, age_days, and REVISION DELTAS vs the prior vintage (the first-appearance-vs-revision
signal). Full store via `load_store()`.

## THE TRAPS (named in the S98 sweep, handled in this build)

1. **Last-Modified is NOT availability.** The archive files' HTTP Last-Modified equals the
   forecast-COMPLETION date, 3-6 days BEFORE public release, on four of seven vintages. Joins key
   ONLY on the measured official release dates (Wayback-captured, hardcoded with provenance in the
   module). knowable_from = release + 1 (releases ~noon ET).
2. **The column origin changes between vintages** (202101 for sep25-dec25, 202201 for jan26+).
   The parser detects the monthly header per workbook (datetime-row strategy A / month-name+year
   row strategy B); selftest asserts both origins were detected, never assumed.
3. **EIA v2 API is current-vintage-only** - the archives are the ONLY as-of source. The API is
   useless for this feed's purpose (measured in the sweep).
4. **Scope guard: apr26+ vintages are NOT loaded.** Their release dates are unmeasured; joining
   them on guessed dates would be a manufactured blind wall. Extending = measure release dates
   first (Wayback or live capture), then add rows to VINTAGES.
5. Values at/after the NGM anchor are STIFS MODEL ESTIMATES, as-printed (label rides on every
   read). The per-cell history/estimate break (gray shading) is not parsed - a build detail if
   ever wanted. The `Dates` sheet's "Last Historical Month" is the model boundary, NOT the NGM
   anchor - stored raw, unused for joins.

## VERIFIED ANCHORS (selftest-pinned, from the sweep's measured tables)

- jan26 NGPRPUS 2026-01 = 109.22 Bcf/d; feb26 same month re-marked 106.68.
- The freeze re-mark pair: NGTCPUS 2026-01 jan26 115.95 -> feb26 121.90 (+5.95); NGWGPUS end-Jan
  2609 -> 2472 (-137). Visible to the agent from 2026-02-11 as revisions_vs_prev_vintage.
- G11 open (Jan 18): jan26 at age 5d. G12 open (Feb 1): jan26 at age 19d, pre-freeze consensus.
  G13 open (Feb 15): feb26 at age 5d, post-freeze re-mark in hand.
- Blind wall: 2026-01-13 (release day) sees dec25; 2026-01-14 sees jan26. Walk Nov 3 - Feb 27:
  0 violations.

## INDUSTRIAL-ID NOTE

The workbook's industrial-consumption row resolves under the CURATED candidates list
(NGINPUS/NGINCON - whichever the workbook carries is recorded per read as `series_id`); the
curated exposure never guesses an ID, it resolves against what is actually in the store.
