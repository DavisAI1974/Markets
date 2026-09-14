# NGWU / WNGSR-SUPPLEMENT WEEKLY S/D BALANCE - S98 FEED N NOTES (family D/supply)

Build date 2026-07-20. Module `research/kalshi/ngwu_feed.py`; store `data/ngwu/ngwu.json` (raw
page captures under `data/ngwu/raw/`, including one Wayback capture). Additive standalone; nothing
existing edited. Feed G's store (`data/cash_basis/hh_cash.json`) is read READ-ONLY by one
selftest cross-check.

## 1. THE HEADLINE, MEASURED: THE FREE WEEKLY BALANCE OBJECT DIED BEFORE THE WALKED WINTER

The feed was commissioned to put the NGWU's weekly production / consumption / LNG-feedgas /
imports estimates in front of the agent for the walked winter. The measured reality:

- **EIA removed the S/D section on 2025-10-02.** The last NGWU issue carrying live S&P Global
  supply/demand estimates is **2025-09-25** (report week ending Sep 24). The 2025-10-02 issue and
  every later issue carry the section only as commented-out dead template. EIA's own notice,
  printed live on the 2025-10-02 and 2025-10-09 issues (then dropped without the section ever
  returning): "Certain sections of the Natural Gas Weekly Update are currently unavailable. The
  affected sections include the supply and demand section, liquified natural gas pipeline
  receipts section, and related supply and demand tables. We will provide an update when we have
  more information." The timing (first issue after the federal fiscal-year end / the Oct 1
  shutdown start) is recorded as fact; EIA did not state a cause.
- **Independently verified on the LIVE page**: Wayback snapshot 2025-11-15 of
  eia.gov/naturalgas/weekly/ (the Nov 13 issue as visitors saw it) has "Supply:" present ONLY
  inside an HTML comment - mid-winter visitors saw no balance data. (Wayback IS reachable from
  this environment by plain HTTP; feed G's recorded block was at its fetch-tool level. Capture:
  `data/ngwu/raw/wayback_live_20251115.html`.)
- **The archived issue pages are per-issue static snapshots** (their commented-out leftovers
  differ per issue - e.g. each carries the PREVIOUS issue's holiday notice), so a live section on
  publication day would have been captured. It is not there. The balance was not published,
  anywhere on the vehicle, for any week after Sep 24.
- The NGWU itself was then **discontinued with the 2026-01-22 issue** (stated on the issue) and
  replaced by the WNGSR Supplement (launched 2026-01-29), which does NOT restore the balance
  table (section 3).
- Consequence for the gate: **Oct 2025 - Feb 2026 has NO free weekly S/D balance levels.** The
  walked winter's freeze-off/feedgas story exists in this vehicle only as (a) the weekly LNG
  vessel-departure series, which survived both eras, and (b) era-2 narrative w/w deltas from LSEG
  starting 2026-01-29. This is a named honest gap, not an extraction failure: the data was never
  published. It also materially strengthens feed J's paid-arm question (the free weekly
  production/feedgas source desks could previously lean on is gone).

## 2. ERA 1 - THE NGWU (through 2026-01-22)

- Per-issue archive: `eia.gov/naturalgas/weekly/archivenew_ngwu/YYYY/MM_DD/`. Release dates
  MEASURED from EIA's archive index (identical to feed G's list): 2025 Aug 28 (w/w seed),
  Sep 4/11/18/25, Oct 2/9/16/23/30, Nov 6/13/20, Dec 4/11/18; 2026 Jan 8/15/22. Holiday skips are
  real: no issue for the report weeks ending 2025-11-26, 2025-12-24, 2025-12-31 - those weeks
  never appeared in any issue (named gap, never bridged).
- Report week = Thu -> Wed ending release-1; masthead "for week ending <Wednesday>" parsed and
  verified per issue (all Wednesdays; all = release-1).
- **What a LIVE issue carries (text, not table)**: one Supply sentence + one Demand sentence,
  "According to data from S&P Global Commodity Insights". Absolute Bcf/d LEVELS are stated only
  where the sentence says "to average X" / "averaging X": dry production (every live issue), LNG
  feedgas (every live issue, printed TWICE - demand sentence + LNG-section pipeline-receipts
  sentence), occasionally total supply / total consumption / industrial. Everything else is
  published as w/w percent + Bcf/d delta only (power, res/comm, Mexico exports, Canada net
  imports). The store carries level, stated pct, stated delta, and qualifier ("less than 0.1
  Bcf/d") per metric per issue; sector LEVELS beyond the above are not published - that is the
  publication's shape, not a parse gap.
- **Extraction route**: raw HTML captured per issue; HTML comments stripped FIRST (load-bearing:
  the dead template inside comments contains a frozen sample week that a naive text-strip
  extracts as if real - both this build's first pass and any scraper that ignores comments would
  ship one fixed week's numbers for every issue from Oct 2 on); values parsed from live text only.
- **Vessels (live in every issue incl. the dead-S/D span)**: "N LNG vessels with a combined
  LNG-carrying capacity of X Bcf departed ...", Bloomberg Finance L.P. shipping data.

## 3. ERA 2 - THE WNGSR SUPPLEMENT (2026-01-29 -> present)

- An Angular app at `eia.gov/naturalgas/weekly/supplement/`; per-issue content is plain HTML
  fragments at `supplement/archive/YYYY/MM/DD/content/bullets_*.html` (measured by reading the
  app bundle: components are prices / storage / LNG only). Release dates measured from
  `content/release_dates.json`: **every Thursday 2026-01-29 -> 2026-07-16, no skips; data week
  ends release-1 (Wednesday)**. This measures what feed G could only model: its conservative
  era-2 Thursday grid is CONFIRMED for the supplement vehicle through Jul 16 (feed G's separate
  July observation of a Wednesday DNAV stamp concerns the DNAV page, not the supplement).
- **Balance content verdict**: the supplement does NOT carry the S/D balance table. Balance
  information appears as editorial BULLETS with w/w CHANGES (Bcf/d and/or percent) for whichever
  components moved that week - total US demand, res/comm, power burn, LNG feedgas, dry
  production, net Canadian imports, total supply - attributed inline to **LSEG Data** (a
  different source than era 1's S&P Global). Absolute levels are essentially never stated (one
  exception captured: dry production 109.4 Bcf/d in the 2026-07-09 issue). Era-2 rows carry
  parsed stated deltas; the full bullet text is retained verbatim per row; unparsed content stays
  None. Per-issue field coverage therefore VARIES - that is the publication's editorial shape.
- **Vessels**: weekly count + capacity continue, source now **Vortexa Analytics** (era-1 was
  Bloomberg). Cross-era continuity observed at the boundary: the Jan 29 supplement says "down 6
  vessels / down 22 Bcf from the previous week", implying 37 / ~140 for the week ending Jan 21;
  the Jan 22 NGWU (Bloomberg) printed 37 / 139 for that week - two trackers, same week, 1 Bcf
  apart.
- **Prices source changed too**: supplement HH quotes cite Natural Gas Intelligence; the DNAV
  daily series (feed G's store) is Refinitiv-sourced. Measured spread (selftest S3d): 30/35
  matched values agree within $0.10; the named divergences are the squeeze aftermath and one July
  week - Jan 28: NGI 9.03 vs Refinitiv 9.34; Feb 4: 6.44 vs 6.88; Jul 8: 3.31 vs 3.13. Do not
  mix the two assessments into one series.

## 4. BLIND WALL

`knowable_from = release_date + 1 calendar day`, both eras (feed G's convention: releases are
afternoon, mid-session; the day-after rule is airtight). The trap: the report week ends
release-1, so "week data joins the day after the week ends" would leak a full week's balance a
day before its release even starts. Values join on ISSUE PUBLICATION only. In-code `_require`
assertions on every asof call; store-wide audit in `--selftest`: **0 violations over 422
evaluations** (daily sweep 2025-08-25 -> 2026-07-23 + per-issue release-day/knowable-day boundary
probes: the issue is invisible on its own release day, visible the day after).

## 5. PER-ISSUE COVERAGE (all 44 issues recovered; zero unrecoverable)

- Era 1: 19 issues fetched and parsed (18 in-scope Sep 2025 - Jan 22 2026 + Aug 28 seed).
  5 S/D-live (Aug 28 - Sep 25), 14 S/D-dead (Oct 2 - Jan 22, each row named
  `era1_sd_discontinued`, levels None). Vessels parsed 19/19.
- Era 2: 25 issues (Jan 29 - Jul 16 2026, incl. current). Vessels parsed 25/25.
- Named gaps: the three skipped era-1 report weeks (section 2); S/D levels for every issue after
  Sep 25 (section 1); era-2 absolute levels (section 3).

## 6. THE FACTUAL BALANCE RECORD (everything the vehicle published, walked-winter relevant)

### 6a. The five live S/D issues (S&P Global; Bcf/d; w/w as stated by the issue)

| issue | week (Thu-Wed) | total supply | dry production | total consumption | power | industrial | res/comm | Mexico exp | Canada net imp | LNG feedgas |
|---|---|---|---|---|---|---|---|---|---|---|
| 2025-08-28 | Aug 21 - Aug 27 | 112.7 (lvl) | 107.8 (+0.3) | (-4.4) | (-4.7) | (+0.3) | (+0.2 pct only) | (-0.1) | (-0.3) | 16.4 (+0.9) |
| 2025-09-04 | Aug 28 - Sep 03 | (-0.6) | 107.2 (-0.6) | (-2.4) | (-2.8) | (+0.2) | (+0.2) | (-0.2) | (less than 0.1, -1.0%) | 16.1 (-0.3) |
| 2025-09-11 | Sep 04 - Sep 10 | (-0.2) | 107.2 (-0.5) | 69.6 (lvl, "essentially unchanged") | (-1.7) | (+0.2) | (+1.4) | (-0.2) | (+0.3) | 16.0 (-0.1) |
| 2025-09-18 | Sep 11 - Sep 17 | (-0.5) | 107.0 (-0.2) | (-0.5) | (+1.3) | (-0.4) | (-1.3) | (-0.7) | (-0.3) | 16.2 (+0.1) |
| 2025-09-25 | Sep 18 - Sep 24 | (-0.1) | 106.7 (-0.3) | (+1.7) | (+1.7) | 22.1 (lvl) | (+0.1) | (+0.7) | (+0.2) | 16.3 (+0.1) |

(lvl) = absolute level published; bare parentheses = stated w/w Bcf/d delta; the store carries
stated percents too. These are the LAST free weekly balance levels before the winter:
production 106.7 Bcf/d, feedgas 16.3 Bcf/d, week ending 2025-09-24.

### 6b. The walked winter in this vehicle: the LNG vessel series (the only continuous line)

Era 1 = Bloomberg, era 2 = Vortexa; per report week ending Wednesday; capacity in Bcf.

| wk ending | vessels | cap | | wk ending | vessels | cap |
|---|---|---|---|---|---|---|
| 2025-10-01 | 32 | 122 | | 2025-12-17 | 33 | 126 |
| 2025-10-08 | 30 | 112 | | (Dec 24 / Dec 31: no issues) | | |
| 2025-10-15 | 32 | 122 | | 2026-01-07 | 38 | 143 |
| 2025-10-22 | 32 | 122 | | 2026-01-14 | 33 | 127 |
| 2025-10-29 | 34 | 129 | | 2026-01-21 | 37 | 139 |
| 2025-11-05 | 34 | 128 | | 2026-01-28 | 31 | 118 |
| 2025-11-12 | 34 | 129 | | 2026-02-04 | 35 | 134 |
| 2025-11-19 | 34 | 129 | | 2026-02-11 | 37 | 140 |
| (Nov 26: no issue) | | | | 2026-02-18 | 34 | 130 |
| 2025-12-03 | 37 | 138 | | 2026-02-25 | 35 | 135 |
| 2025-12-10 | 40 | 151 | | 2026-03-04 | 39 | 148 |

The squeeze week (ending Jan 28) is the winter's low: 31 vessels / 118 Bcf, down 6 / 22 w/w.

### 6c. Era-2 winter balance statements (LSEG, w/w only; full text retained in the store)

| issue | week ending | stated (national scope only) |
|---|---|---|
| 2026-01-29 | 2026-01-28 | LNG feedgas deliveries FELL 18 percent w/w (no Bcf/d given) - the squeeze week's physical response |
| 2026-02-05 | 2026-02-04 | res/comm demand -8.3 Bcf/d (-12.5 percent) |
| 2026-02-12 | 2026-02-11 | total US demand -19.1 Bcf/d |
| 2026-02-19 | 2026-02-18 | total US demand -15.8 Bcf/d (issue also quotes prior week -19.1) |
| 2026-02-26 | 2026-02-25 | total US demand +9.7 Bcf/d (quotes prior week -15.8) |
| 2026-03-05 | 2026-03-04 | total US demand -14.5 Bcf/d, led by res/comm -11.0 Bcf/d |

G12 (Feb 1-13) and G13 (Feb 15-27) decision days therefore have: the vessel series, these LSEG
deltas at release+1, and `latest_sd_levels` falling back to 2025-09-25 with age_days approx
130-155 - the honest picture.

## 7. ATTRIBUTION AND REDISTRIBUTION

Carried per row in the store: era-1 S/D = S&P Global Commodity Insights (formerly IHS
Markit/Platts) republished by EIA; era-1 vessels = Bloomberg Finance L.P.; era-2 balance bullets
= LSEG Data (as cited inline); era-2 vessels = Vortexa Analytics. All values were published
openly by EIA on public pages; no redistribution terms are printed on those pages. The
attribution travels with the numbers; note that after Oct 2025 EIA itself evidently lost the
ability to republish the S&P weekly estimates, which is consistent with (but not stated as) a
licensing limit on exactly this data.

## 8. CROSS-CHECKS AND VINTAGE FINDINGS (selftest, all named)

- S3a: LNG feedgas is printed twice per live issue (demand sentence + LNG section) - 5/5 agree.
- S3b: issue N-1 level + issue N's stated w/w vs issue N's level - 7/8 agree; the one miss is a
  measured SOURCE REVISION, not a parse error: the 2025-09-11 issue's own numbers are internally
  consistent with a prior week of 107.7 while the 2025-09-04 issue printed 107.2 - S&P revised
  the Sep-3 week by +0.5 Bcf/d between publications. Feed-K-class finding: the weekly S/D
  estimates REVISE, so any historical S/D series carries vintage risk.
- S3c: all 14 dead issues carry the same frozen commented sample, and it exactly matches the
  2025-09-25 issue's live values (production 106.7 / feedgas 16.3 / industrial 22.1) - two-plus
  independent archived pages corroborating the last live week, and proof the frozen text is a
  template artifact, not per-issue data.
- S3d: era-2 HH bullets vs feed G's DNAV store - 30/35 within $0.10; 5 named NGI-vs-Refinitiv
  assessor spreads (section 3). Also observed: consecutive era-2 issues quote identical values
  for the shared Wednesday (9.03 twice, 6.44 twice) - the vehicle is self-consistent.
- S3e: era-2 issues quoting last week's delta vs the prior issue's own statement - 2 agree; 1
  named revision (power +6.3 restated a week later as +5.9, same sign, 6 percent apart - LSEG
  estimates revise too).

## 9. STORE / MODULE / SELFTEST

- Store `data/ngwu/ngwu.json`: 44 issue rows {era, issue_date, knowable_from, week_span,
  week_ending, sd_live, fields (per metric: level_bcfd / wow_stated_pct / wow_stated_bcfd /
  qualifier / direction), computed_wow_bcfd (only across exactly-consecutive weeks, never
  bridged), sentences (verbatim), lng_vessels_departed, lng_vessel_capacity_bcf, attribution,
  source_url, extraction_route, notes}. Meta carries the measured release lists (both eras), the
  skips, the S/D death boundary + EIA's notice text, the Wayback live-page check, the frozen
  template samples, attribution, and named gaps.
- `ngwu_asof(date)`: latest knowable issue (blind wall asserted) + `latest_sd_levels` (the most
  recent knowable issue with live balance levels, with its own age_days) - the agent always sees
  the freshest issue AND the freshest actual balance, each with honest staleness.
- `--selftest` 2026-07-20: S1 integrity OK; S2 blind wall 0/422; S3a-S3e as in section 8 (0
  parse failures; revisions and assessor spreads named); S4 era boundaries demonstrated
  factually (S/D death Sep 25 -> Oct 2; vehicle change Jan 22 -> Jan 29 with the supplement
  invisible until Jan 30); S5 missing-is-None (year-end blackout serves the Dec 18 issue at age
  16d; skipped weeks absent from the store). PASS.
- NOT wired into decision_state (wiring is the orchestrator's serial pass). Wiring note: expose
  `latest_sd_levels.age_days` alongside any level - a 139-day-old production level is a regime
  anchor, not a fresh reading, and the age IS part of the signal's meaning. The vessel series
  and the era-2 LSEG deltas are the only winter-fresh lines.
