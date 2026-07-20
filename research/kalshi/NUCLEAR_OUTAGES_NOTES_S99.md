# NUCLEAR OUTAGES FEED - BUILDER NOTES (feed R arm 1, S99, built 2026-07-20)

Module: `research/kalshi/nuclear_outages.py`. Store: `data/nuclear_outages/us_daily.json.gz`
(7,140 days, 2007-01-01 -> 2026-07-20), S3 prefix `nuclear_outages/`. Wired into decision_state
as block `nuclear_outages`; audit-joins class `nuclear_wall`. Module selftest 10/10 PASS; harness
selftest PASS; audit 0 violations / 101 days, present on all 101.

## WHAT IT IS

EIA Open Data v2 `nuclear-outages/us-nuclear-outages` - daily U.S. aggregate operable capacity,
capacity out (MW), percent out. The sweep's side-find; no NRC page scraping needed.
`nuclear_outages_asof(iso)` = latest day STRICTLY BEFORE iso with GW alongside raw MW, 1d/7d
changes, calendar season tag.

## MEASURED MECHANICS AND TRAPS

1. **Same-day-morning publication on weekdays** (a 2026-07-20 row existed on 2026-07-20), but
   weekend/holiday rows arrive late or NEVER: 2026-07-18 (Sat) is absent outright, and the S98
   sweep saw the series end at 07-17 hours before 07-19/07-20 rows appeared in a Monday batch.
   WALL: knowable_from = period + 1 calendar day, strictly-prior join - airtight vs everything
   observed.
2. **Real gaps stay gaps.** Missing calendar days are absent in the store; chg_1d/chg_7d across a
   gap are None, never bridged (selftest exercises the real 07-17->07-19 gap).
3. **EIA v2 serializes numerics as STRINGS in data pulls** - coerced at store time. (Generic v2
   trap; any future EIA v2 feed builder should expect it.)
4. Revision risk: NRC statuses are point-in-time; EIA-side corrections unmeasured - store is a
   retrieval-dated snapshot, named as a feed-K-class question only if it ever matters.
5. Facility/generator level exists on sibling routes (facets verified) - NOT pulled in arm 1,
   named phase-2 scope. ISO aggregate outage reports (coal/gas maintenance) = arm 4, separate.

## VERIFIED ANCHORS (selftest-pinned)

- The freeze window: 2026-01-15 outage 1,839 MW -> 2026-01-20 3,184 MW (the sweep's 1.8 -> 3.2 GW
  sample reproduced exactly) - ~1.4 GW of implied extra gas burn arriving DURING the squeeze
  build-up, now visible at D+1 staleness.
- asof 2026-01-21 -> period 2026-01-20 age 1; asof 2026-01-20 -> 2026-01-19 (own-day walled).
- Walk Nov 3 - Feb 27: 0 violations.

## PYTH LIVENESS SIDE-FINDING (recorded here so it is not lost; measured 2026-07-20)

While answering the free-live-canary question: **Pyth's Henry Hub NG feeds (Commodities.NGD*) are
catalog-listed but have NEVER PUBLISHED** - all seven contracts return price 0 at publish_time
epoch-0; TTF (TGE*) equally dead; NL* is nickel, not natgas. WTI/XAU/XAG publish live (sampled
fresh). CONSEQUENCES: (1) S84's "Pyth has no natgas" stands; S91's "NGDQ6 confirmed correct"
verified only the ID mapping, not data flow - pyth_collector.py's NGDQ6 entry collects nothing;
(2) the live-loop canary can be tested end-to-end at $0 on WTI/gold/silver only; NG live tape =
Databento Standard ($179/mo, page-verified) or a broker CME L1 sub at NG go-live; (3) NAMED
TENSION for feed M: feed L recorded KXNATGASD's settlement source as "Pyth" - with Pyth NG feeds
never-published, the actual settlement source must be verified from the contract spec (already a
gate requirement), never assumed.
