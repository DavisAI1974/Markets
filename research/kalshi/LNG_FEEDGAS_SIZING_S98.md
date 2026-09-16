# LNG FEEDGAS SIZING SPIKE - FEED J (DATA_GATE_S98)

Date: 2026-07-20. Author: Feed J investigation agent (S98 gate).
Status: INVESTIGATION REPORT ONLY. No scraper built, no account created, no trial started, no
subscription taken. Every price below is either quoted from a published page (URL given) or stated
as "not published - quote required". Subscribing to anything is GREG'S decision, off this report.

The question (from `DATA_GATE_S98.md` feed J): what would it take - free scrape or modest paid
subscription - to put a DAILY LNG feedgas series (total and per-terminal) in front of the
forecaster, (a) historically for the walked winter Nov 2025 - Feb 2026, and (b) live-forward.

---

## 0. EXECUTIVE VERDICTS

- **Live-forward, free: YES.** The terminal-serving interstate pipes post scheduled quantities and
  operationally available capacity at their delivery meters on public, no-login EBBs (verified on
  five host platforms). A daily total + per-terminal series from the top 5-6 terminals is a
  **~5-8 build-day** scrape (top-6 lean pass; ~7-11 days for all nine terminals with validation),
  across **~8 host-platform adapters**. Timely-cycle scheduled quantities post the afternoon BEFORE
  the gas day - the feed would be genuinely LEADING, not lagging.
- **Historical Nov 2025 - Feb 2026, free: NOT VERIFIED OBTAINABLE.** This is the honest make-or-break
  finding. The federal retention floor found in this spike is 90 days (and that clause attaches to
  transactional reports; no longer retention mandate for daily capacity postings was found). The
  walked winter is already 142-261 days in the past. Whether each pipe's query interface serves gas
  days back to Nov 2025 is a per-pipe VOLUNTARY-archive question that the posting interfaces did not
  answer to a non-interactive fetch (they are JS/query UIs; the in-session browser pane timed out).
  **A 0.5-1 day hands-on browser pass across the 8 platforms resolves it definitively.** Until that
  pass is run, the walked winter must be treated as NOT free-obtainable at daily/meter resolution.
  Per the gate spec, this is a successful spike conclusion, not a failure. No proxy is proposed.
- **Historical, paid: YES, at every real vendor.** All the flow vendors (flagship and independent)
  carry multi-year daily feedgas history spanning the walked winter - their analysts publicly cite
  specific daily values from inside the window (e.g. East Daley: Gator Express deliveries above
  4.1 Bcf/d since Nov 15, 2025). Prices: only PipeRiv publishes numbers ($50/user/mo premium,
  $500/user/mo API); Criterion, NGI, East Daley, Enverus, S&P, Wood Mackenzie, Kpler, LSEG are all
  "quote required" - stated per-vendor below, nothing guessed.
- **Free coarse anchors exist for the walked winter** (real data, wrong resolution): EIA's Natural
  Gas Weekly Update (weekly average total feedgas) and the DOE/EIA monthly export series
  (per-terminal, monthly, ~2-month lag). Usable as validation spine, not as the daily driver feed.

---

## 1. THE MECHANISM (why the free arm exists at all)

- 18 CFR 284.13(d) requires every interstate pipeline to provide "on its Internet web site and in
  downloadable file formats ... equal and timely access to information relevant to the availability
  of all transportation services whenever capacity is scheduled", including capacity at delivery
  points, "the total design capacity of each point", and "the amount scheduled at each point or
  segment whenever capacity is scheduled". Source:
  https://www.law.cornell.edu/cfr/text/18/284.13
- Scheduled quantity at a terminal's delivery meter IS the feedgas nomination. Postings occur per
  NAESB nomination cycle (Timely / Evening / ID1 / ID2 / ID3); Timely-cycle scheduled quantities are
  posted late afternoon of D-1 (exact per-cycle posting timestamps to be pinned from NAESB WGQ in
  any build - not assumed here). Wood Mackenzie's product page counts "48 cycles" of postings per
  day across pipes (https://www.woodmac.com/industry/commodity-trading-analytics/natural-gas-real-time/).
- Same regulation, actuals: pipelines must post best-estimate information "at each receipt and
  delivery point before 11:30 a.m. central clock time three days after the day of gas flow" - i.e.
  ACTUAL flows become visible with at most a ~3-day lag, refining the scheduled series.
- Retention (THE catch for the historical arm): the retention language found in 284.13 is "must
  maintain access to that information for a period not less than 90 days from the date of posting",
  and it attaches to the firm/interruptible transactional reports of paragraph (b). No LONGER
  federal retention mandate for the daily capacity/scheduled postings was found in this spike.
  Anything deeper than 90 days on an EBB is the pipeline's voluntary practice, which varies by
  host platform and must be checked per pipe.
- Blind-wall note for any future feed (spec-level): join on the posting timestamp of the cycle
  actually captured. D-1 Timely nominations are legitimately pre-gas-day information (leading, not
  leakage) PROVIDED the capture timestamp is stored; D+3 actuals are a revision layer with their own
  publication clock. Vendor historical files carry the same revision-vintage question as feed K.

---

## 2. TERMINAL INVENTORY, NOV 2025 - FEB 2026 (Arm 1 step 1)

EIA counts eight operating export terminals through the window, with Golden Pass becoming the ninth
at first cargo on 2026-04-22 - i.e. AFTER the walked winter
(https://www.eia.gov/todayinenergy/detail.php?id=67564,
https://www.eia.gov/todayinenergy/detail.php?id=67224).

| terminal | status in window | feedgas pipes (delivery-meter visibility) | EBB visibility |
|---|---|---|---|
| Sabine Pass (Cheniere, LA) | operating, 6 trains | Creole Trail (Cheniere), NGPL (KM), KMLP (KM, 2.2 Bcf/d design, terminates at the terminal), Transco (Williams, Gulf Trace) | FULL - 4 interstate pipes, 3 host platforms |
| Corpus Christi (Cheniere, TX) | operating; Stage 3 midscale trains ramping through 2025 (first Stage 3 cargo Mar 2025, EIA) | Cheniere Corpus Christi Pipeline (CCPL, 2.75 Bcf/d design, 21.5 mi) | FULL - CCPL is FERC-jurisdictional with its own EBB |
| Plaquemines (Venture Global, LA) | operating + RAMPING HARD: 34/36 trains making LNG at 3Q25 earnings; deliveries on Gator Express above 4.1 Bcf/d sustained from Nov 15, 2025 | Gator Express (VG; two 42-inch laterals, ~26.8 mi) | FULL - single dedicated interstate lateral |
| Freeport (TX) | operating, 3 trains | Gulf South "Coastal Bend"/Stratton Ridge (interstate), TETCO Stratton Ridge (interstate), TETCO-leased BIG Pipeline (INTRASTATE Brazoria Interconnector) + other intrastate supply | PARTIAL - the intrastate share has NO EBB obligation; the known weakest terminal for EBB-derived flows |
| Cameron (Sempra, LA) | operating, 3 trains | Cameron Interstate Pipeline (40 mi; connects the terminal to five interstate pipelines) | FULL - single dedicated interstate |
| Calcasieu Pass (Venture Global, LA) | operating (full commercial ops since Apr 2025) | TransCameron (VG; 24 mi, 42-inch, 1.9 Bcf/d; interconnects ANR/TETCO/Sabine near Grand Chenier) | FULL - single dedicated interstate |
| Cove Point (MD) | operating | Cove Point Pipeline (BHE GT&S) | FULL |
| Elba Island (Kinder Morgan/Southern LNG, GA) | operating | Elba Express + SNG interconnects (Kinder Morgan family) | FULL - KM platform |
| Golden Pass (TX) | COMMISSIONING only in-window: its pipeline EBB posted "Mile Post 33 Ready for Operations" Nov 18, 2025 and "Mile Post 69 Ready for Operations" Nov 24, 2025; Train 1 complete Jan 2026; first LNG Mar 2026; first cargo Apr 22, 2026 | Golden Pass Pipeline | FULL going forward; in-window feedgas was commissioning-scale |

Sources: Sabine pipes - https://naturalgasintel.com/news/ngpl-creole-trail-maintenance-seen-tightening-sabine-pass-natural-gas-supply/ ,
https://www.kindermorgan.com/Operations/Natural-Gas/Index ; Plaquemines ramp -
https://eastdaley.com/the-burner-tip/plaquemines-demand-passes-4-bcf-d-as-lng-project-ramp-continues ,
https://naturalgasintel.com/news/record-plaquemines-lng-ramp-sets-up-knife-fight-in-gulf-coast-for-natural-gas-supply/ ;
CCPL - https://www.cheniere.com/about/where-we-work/corpus-christi-pipeline ; Freeport meters -
https://www.piperiv.com/lng/freeport/notes ,
https://www.naturalgasintel.com/news/freeport-lng-feed-gas-remains-depressed-as-vessels-collect-around-texas-coast/ ;
Cameron Interstate / TransCameron - https://rextag.com/pages/cameron-interstate-pipeline ,
https://ventureglobal.com/calcasieu-pass/transcameron-pipeline/ ; Golden Pass -
https://pgjonline.com/news/2026/january/golden-pass-lng-train-1-complete-first-cargoes-expected-in-march ,
https://www.goldenpasslng.com/newsroom/golden-pass-lng-marks-historic-milestone-with-first-lng-production ,
http://www.gasnom.com/ip/goldenpass/ (ready-for-operations notices seen directly on the EBB).

Market-context footnote for the walk: Plaquemines' record ramp plus Golden Pass startup anticipation
were live demand-side drivers of exactly the walked winter - this feed is not hypothetical relevance.

## 3. PER-PIPE EBB FINDINGS (Arm 1 step 2)

What was verified by direct fetch in this spike vs what needs a hands-on pass. "History depth" is
the walked-winter question; NONE of the platforms revealed archive depth to a non-interactive fetch,
so every history cell below is honest UNVERIFIED unless stated. The verification recipe per pipe is
identical and trivial by hand: open the OAC / scheduled-quantity report, set gas day = 2025-11-15,
see whether rows return.

| host platform (adapter) | pipes (terminals) | URL | login? | format seen | history depth |
|---|---|---|---|---|---|
| Cheniere "LNG Connection" | Creole Trail + CCPL (Sabine, Corpus) | https://lngconnection.cheniere.com/ (CCPL at #/ccpl) | not determinable by fetch (JS SPA - page serves a loading shell only) | SPA; underlying JSON API likely; needs browser/API sniff | UNVERIFIED |
| Kinder Morgan PortalUI/DART | NGPL, KMLP (Sabine); SLNG/Elba Express, SNG (Elba) | https://pipeportal.kindermorgan.com/PortalUI/DefaultKM.aspx?TSP=KMLP (TSP=SLNG etc.) | info postings visible without login (verified) | "Operationally Available" point/segment sections; Excel artifacts present; shell showed Current/Tomorrow gas-day options - full report UI needs interaction | UNVERIFIED |
| Williams 1Line | Transco (Sabine) | https://www.1line.williams.com/Transco/info-postings/capacity/Operationally-Available_NEW.html ; site map https://www.1line.williams.com/Transco/site-map.html | public pages (verified reachable) | JS-driven report page (fetch returned shell); site map lists Capacity / Operationally Available / Location Data Download | UNVERIFIED |
| Boardwalk "GasQuest" | Gulf South (Freeport partial; also serves Sabine-area interconnects) | https://www.gasquest.com/informational-posting (old infopost.bwpipelines.com/?tspid=1 now 302-redirects here) | not determinable by fetch (JS app) | NEW platform - Boardwalk migrated its EBB; adapter churn risk is real | UNVERIFIED |
| Enbridge LINK | TETCO (Freeport partial - Stratton Ridge + leased BIG) | via https://link.enbridge.com (not fetched this spike) | industry-standard public info postings; NOT VERIFIED here | - | UNVERIFIED |
| Quorum "myquorumcloud" IPWS | Gator Express tspno=2 (Plaquemines); TransCameron tspno=10 (Calcasieu Pass) | https://web-prd.myquorumcloud.com/VGPPB1IPWS/?tspno=2 ; OAC report https://web-prd.myquorumcloud.com/VGPPB1IPWS/OpAvailPosting?tspno=2 | NO login (verified - report page renders public) | best-verified platform: plain URL navigation; OAC report columns include Design Capacity, Operating Capacity, Operationally Available Capacity, and **Total Scheduled Quantity**, plus Effective Gas Day / Post Date/Time / Cycle Desc; Download + Retrieve buttons; LOCATIONDATA.csv served | UNVERIFIED (report is query-driven; default view showed "No items to display" until a gas-day query is made) |
| BHE GT&S infopost | Cove Point Pipeline (Cove Point) | https://infopost.bhegts.com/cpl | public menu (verified) | menu verified: "Operationally Available", "Unsubscribed", "No-Notice Transportation", "Posted Imbalances", Downloads section | UNVERIFIED |
| gasnom.com (hosted EBB) | Cameron Interstate (Cameron); Golden Pass Pipeline (Golden Pass) | http://www.gasnom.com/ip/cameron/ ; http://www.gasnom.com/ip/goldenpass/ | NO login (verified - notices render public) | primitive ColdFusion frames; notices verified rendering (Golden Pass ready-for-ops notices read directly); capacity reports behind menu frames | UNVERIFIED |

Notes:
- The Quorum platform result generalizes: one adapter covers both Venture Global pipes, and the same
  IPWS software hosts many other pipes (Ozark, PNGTS, Destin observed at the same host), so the
  adapter is reusable.
- The Total Scheduled Quantity column on the Quorum OAC report means the free feed does NOT need the
  design-minus-available derivation on that platform; scheduled quantities are posted directly.
- Freeport is the structural exception: PipeRiv's methodology page names its three visible meters
  (Gulf South Stratton Ridge, TETCO BIG, TETCO Stratton Ridge) and notes BIG is an intrastate line
  TETCO leases - the intrastate share of Freeport supply has no EBB obligation. Any free series
  carries a per-terminal completeness caveat on Freeport specifically (vendors patch this with
  proprietary monitoring - see Arm 2).
- Browser-pane note: the in-session browser (needed to drive date pickers) timed out in this
  environment, which is WHY history depth is uniformly unverified above. This is a tooling
  limitation of the spike session, not a property of the EBBs.

## 4. FREE-ARM VERDICTS (Arm 1 step 3)

Per terminal - historical (Nov 2025 - Feb 2026) / live-forward:

| terminal | historical free | live-forward free |
|---|---|---|
| Sabine Pass | UNVERIFIED - 4 pipes on 3 platforms must each serve 8-month-old gas days | YES (4 pipes, all public) |
| Corpus Christi | UNVERIFIED - hinges on the Cheniere SPA's archive | YES |
| Plaquemines | UNVERIFIED - Quorum query interface, depth unknown | YES (verified public report) |
| Freeport | UNVERIFIED and PARTIAL AT BEST (intrastate share invisible even live) | PARTIAL (interstate meters only) |
| Cameron | UNVERIFIED (gasnom archive depth unknown) | YES |
| Calcasieu Pass | UNVERIFIED (same Quorum adapter as Plaquemines) | YES |
| Cove Point | UNVERIFIED | YES |
| Elba | UNVERIFIED | YES |
| Golden Pass | n/a in-window (commissioning; EBB live and public) | YES - and it matters: T1 ramp + T2 2H2026 |

- **Effort estimate, live-forward daily series, top-6 terminals** (Sabine, Corpus, Plaquemines,
  Freeport-partial, Cameron, Calcasieu): 7 platform adapters (Cheniere SPA 1-2d the hardest; KM
  0.5-1.5d; 1Line 0.5-1d; GasQuest 0.5-1.5d; Enbridge LINK 0.5-1.5d; Quorum 0.5-1d covering two
  pipes; gasnom 0.25-0.5d) + meter identification from the pipes' own location files
  (LOCATIONDATA.csv / Location Data Download) + validation against the EIA weekly total ->
  **~5-8 build days lean, 7-11 days for all nine terminals with per-cycle capture and a selftest.**
  Ongoing maintenance is nonzero: Boardwalk's mid-window migration to GasQuest is exactly the kind
  of churn an 8-platform scraper eats.
- **The historical gate-check that must run FIRST if the free arm is picked: 0.5-1 hand-day.** Open
  each platform's OAC/scheduled report, query gas day 2025-11-15, record per pipe whether rows
  return and how far back the picker goes. Outcomes: (a) archives reach Nov 2025 on all pipes ->
  the walked winter is free after all (then the scrape backfills it in the same build); (b) some or
  all trim to ~90 days -> those pipes' winters are NOT free-obtainable, the gaps are named per pipe,
  and the historical question moves to the paid arm or stays an honest gap. No interpolation, no
  proxy, either way.
- **Free supplementary series that DO cover the walked winter** (real data, coarser resolution -
  candidate decision_state inputs regardless of the daily decision):
  - EIA Natural Gas Weekly Update - weekly average total LNG feedgas (vendor-sourced figure,
    published free): https://www.eia.gov/naturalgas/weekly/
  - EIA Natural Gas Monthly + DOE FECM LNG export details - per-terminal MONTHLY export volumes,
    ~2-month lag (regulatory filings, authoritative): https://www.eia.gov/naturalgas/monthly/ ,
    https://www.eia.gov/dnav/ng/hist/n9133us2m.htm
  - Daily TOTALS quoted in wire coverage (Reuters citing LSEG; NGI/Argus articles) exist across the
    window in news text - scrapeable in principle but fragile, total-only, and carries licensing
    questions for systematic use; recorded as an observation, NOT proposed as the feed.

## 5. PAID ARM - VENDOR SURVEY (Arm 2)

No vendor was contacted, no trial started. "Quote required" means the vendor publishes no price.
Third-party-reported price ranges: none were found in this spike's searches for these specific gas
products, so none are cited - the honest statement is that the numbers live behind sales calls.

### Modest / independent tier

| vendor / product | carries | history (covers Nov 25 - Feb 26?) | delivery | price |
|---|---|---|---|---|
| **PipeRiv** (piperiv.com) | EBB aggregation: informational postings, critical notices, dedicated LNG feedgas tools (Freeport and Plaquemines pages confirmed; full terminal roster unconfirmed), flows "across pipeline cycles" | serves historical charts per its notes pages; DEPTH UNCONFIRMED - inherits the same EBB-archive question plus whatever they have stored since ~2024 launch | web tools; API + data downloads on the $500 tier; Snowflake on enterprise | **PUBLISHED**: Basic free; Premium $50/user/mo; Individual API $500/user/mo; Custom from $5,000/mo (https://www.piperiv.com/pricing) |
| **Criterion Research** (criterionrsch.com) | categorical pipeline flows for North America incl. "deliveries to LNG terminals", production receipts, power meters; live low-latency, end-of-day summaries | multi-year vendor archive (firm founded 2015; flows product is their core) - depth to be confirmed on the sales call | API, bulk files, dashboards; also distributed via ICE Connect and ICE's API/bulk services (https://developer.ice.com/fixed-income-data-services/catalog/criterion-research) | not published - quote required (https://criterionrsch.com/data/natural-gas-flows) |
| **NGI - LNG Data Suite / U.S. LNG Export Tracker** (naturalgasintel.com) | daily U.S. LNG export flow data - deliveries to each major operating terminal BROKEN OUT BY FEEDER PIPELINE; netbacks, arb curves | **datafeed carries a ROLLING 7-DAY history only** - live-forward product; does NOT solve the walked winter by itself (tracker page is paywalled - returned 403 to fetch) | API + XLS (https://www.naturalgasintel.com/services/lng-datafeed/) | not published - sales contact |
| **East Daley Analytics - Energy Data Studio** (eastdaley.com) | asset-level gas S&D incl. LNG terminal demand (their public posts cite per-day Gator Express deliveries inside our window), pipeline flow sampling near-real-time | yes - their published winter analysis quotes daily values from Nov 2025 | platform + exportable data sets | not published - quote required |
| **Enverus - Natural Gas Transmission Analytics** (enverus.com) | ~30,000 transmission meters monitored daily, basin-to-hub corridors incl. LNG demand | multi-year vendor archive expected - confirm on call | PRISM platform / data feeds | not published - quote required |
| **FactSet (BTU Analytics lineage)** | gas markets: spot/forward prices, pipeline flow, transport, storage | confirm on call | FactSet workstation/feeds | not published - quote required |
| **RBN Energy** (rbnenergy.com) | REPORTS not raw data: LNG Voyager (weekly feedgas/exports analysis), U.S. NATGAS Billboard (daily report) | weekly analysis archive | PDF/report subscriptions | not published on product pages |

### Flagship tier

| vendor / product | carries | history | delivery | price |
|---|---|---|---|---|
| **Wood Mackenzie (Genscape lineage) - Natural Gas Real-time + North American LNG service** | flows for 190+ pipelines, 900+ updates/day, 48 cycles, 20,000 locations; LNG service explicitly tracks **100% of US export terminals** combining pipeline nominations + infrared facility monitoring + AIS vessel tracking (this is how Freeport's intrastate blind spot gets patched) | deep multi-year; "pipeline flow history" explicit on the product page | web platform + feeds | not published - quote required (https://www.woodmac.com/industry/commodity-trading-analytics/natural-gas-real-time/) |
| **S&P Global Commodity Insights (PointLogic lineage)** | NA gas pipeline flows, meter watchlists, LNG feedgas daily (EIA weekly + AGA indicators cite S&P feedgas figures); "Gaslytics - Pipeline Flows" dataset listed on S&P Marketplace as "real-time and historical" | deep multi-year | FTP, API, Energy Studio, Marketplace feeds | not published - quote required (https://www.spglobal.com/commodityinsights/en/ci/products/pointlogic-gas.html) |
| **LSEG** | daily US gas demand/flows incl. feedgas - the series Reuters wires quote daily | deep | Workspace/feeds | not published - quote required |
| **Kpler - Gas & Power** | US production, pipeline flows, LNG terminal tracking, storage; daily LNG reports | deep | platform/API | not published - quote required (https://www.kpler.com/solution/gas-power) |

Not surveyed in depth: Bloomberg terminal channels (BNEF daily feedgas exists on-terminal) - only
relevant if a terminal subscription existed for other reasons; not priced here.

## 6. COMPARISON

| option | daily per-terminal? | covers walked winter? | leads the gas day? | cost | build effort | risk |
|---|---|---|---|---|---|---|
| Free EBB scrape | yes (Freeport partial) | UNKNOWN until the 0.5-1d depth check; assume NO until proven | yes (D-1 Timely cycle) | $0 | 5-8d (top-6) / 7-11d (all 9) + maintenance | platform churn; per-pipe archive gaps; Freeport intrastate blind spot |
| EIA weekly + DOE monthly (free) | no (weekly total / monthly terminal) | YES | no | $0 | <1d | resolution far below the driver's timescale |
| PipeRiv | LNG tools confirmed for 2 terminals; roster + depth need a demo | unconfirmed | premium tier is "today's data"; API tier for pulls | $50-500/user/mo PUBLISHED | days, not weeks (API) | young platform; coverage/depth unproven - verify before relying |
| Criterion (or East Daley / Enverus) | yes | yes (vendor archive) | vendor-dependent (Criterion markets live low-latency) | quote required | ~1-3d integration | price unknown until the call - could exceed "modest" |
| NGI LNG datafeed | yes, by feeder pipeline | NO - rolling 7-day window | daily | quote required | ~1-2d | live-forward only; pairs with, not replaces, a history source |
| WoodMac / S&P / LSEG / Kpler | yes, incl. Freeport patched | yes | yes | quote required (flagship-scale) | ~1-3d | cost; overkill if only feedgas is wanted |

## 7. RECOMMENDATION (for GREG'S decision - nothing below is actioned)

Laid out as the decision structure, cheapest-information-first:

1. **Run the 0.5-1 day EBB history depth check before deciding anything** (free, hands-on browser
   session, no accounts): per pipe, query gas day 2025-11-15 on the 8 platforms in section 3 and
   record depth. It either unlocks the walked winter free, or converts the free arm to
   live-forward-only with the gaps NAMED per pipe. Every downstream choice is better-informed for
   one desk-day of work.
2. **If the walked winter must be in decision_state at daily resolution and the depth check fails:**
   the only assured route is a vendor with history. The modest-tier shortlist to price, in order of
   likely fit: **Criterion** (independent, LNG terminal deliveries explicit, API/ICE delivery),
   **East Daley** (already publishing exactly our winter's numbers), **PipeRiv demo** (the only
   published prices: $50/$500/user/mo - verify terminal roster and history depth in the demo before
   treating it as sufficient), **NGI** (clean daily by-feeder-pipeline feed but 7-day rolling - live
   leg only). Three quote requests and one demo are zero-commitment actions.
3. **The free live-forward scrape is worth building regardless of the paid decision** (5-8 days,
   top-6 terminals): it starts accruing now, it is vendor-independent, it captures the D-1 leading
   nomination signal, and G13-forward (Golden Pass T1 ramp, T2 in 2H2026) is exactly the period
   where a live feedgas eye pays. It also directly sizes the deferred "full production/flow network"
   gate item - the adapter framework is the same, just pointed at more meters.
4. **Either way, wire the free coarse anchors** (EIA weekly total feedgas, DOE monthly per-terminal)
   for the walked winter now - real data, zero cost, honest resolution labels.
5. **Do not** buy anything to close the Freeport intrastate blind spot alone - only the flagship
   tier (WoodMac's infrared/AIS layer) truly patches it, and that is a flagship-price question, not
   a feedgas-feed question.

## 8. NAMED LIMITATIONS OF THIS SPIKE

- Per-pipe EBB archive depth: UNVERIFIED (JS/query interfaces; the session's browser pane timed
  out). This is the single load-bearing unknown, and section 7 item 1 is its named resolution.
- Enbridge LINK (TETCO) postings were not directly fetched; visibility asserted from industry
  practice and the PipeRiv methodology page naming TETCO meters, not from a direct fetch.
- No vendor was contacted, so every "quote required" is exactly that - no third-party price ranges
  for these specific products surfaced in searches, and none are guessed.
- NAESB per-cycle posting timestamps are described qualitatively; the exact times must be pinned
  from the NAESB WGQ standard (or observed posting stamps) during any build - they are the blind
  wall of the live feed.
- PipeRiv's LNG coverage was confirmed for Freeport and Plaquemines only; whether all nine terminals
  are served, and with what history, needs their demo.

## 9. SOURCE INDEX (all URLs cited above, deduplicated)

Regulation and mechanism:
- https://www.law.cornell.edu/cfr/text/18/284.13
- https://www.naesb.org/members/urls_of_pipelines.htm (EBB URL directory; the printed PDF variant is image-only)

Terminals and pipes:
- https://www.eia.gov/todayinenergy/detail.php?id=67564 (Golden Pass ninth terminal, first cargo)
- https://www.eia.gov/todayinenergy/detail.php?id=67224 (ten-year retrospective, eight operating terminals)
- https://pgjonline.com/news/2026/january/golden-pass-lng-train-1-complete-first-cargoes-expected-in-march
- https://www.goldenpasslng.com/newsroom/golden-pass-lng-marks-historic-milestone-with-first-lng-production
- https://www.goldenpasslng.com/newsroom/first-lng-export-cargo-departs-golden-pass-lng
- https://eastdaley.com/the-burner-tip/plaquemines-demand-passes-4-bcf-d-as-lng-project-ramp-continues
- https://naturalgasintel.com/news/record-plaquemines-lng-ramp-sets-up-knife-fight-in-gulf-coast-for-natural-gas-supply/
- https://naturalgasintel.com/news/ngpl-creole-trail-maintenance-seen-tightening-sabine-pass-natural-gas-supply/
- https://www.kindermorgan.com/Operations/Natural-Gas/Index
- https://www.cheniere.com/about/where-we-work/corpus-christi-pipeline
- https://ventureglobal.com/calcasieu-pass/transcameron-pipeline/
- https://rextag.com/pages/cameron-interstate-pipeline
- https://www.naturalgasintel.com/news/freeport-lng-feed-gas-remains-depressed-as-vessels-collect-around-texas-coast/

EBBs (fetched directly):
- https://lngconnection.cheniere.com/
- https://pipeportal.kindermorgan.com/PortalUI/DefaultKM.aspx?TSP=KMLP
- https://www.1line.williams.com/Transco/info-postings/capacity/Operationally-Available_NEW.html
- https://www.1line.williams.com/Transco/site-map.html
- https://www.gasquest.com/informational-posting
- https://web-prd.myquorumcloud.com/VGPPB1IPWS/?tspno=2
- https://web-prd.myquorumcloud.com/VGPPB1IPWS/OpAvailPosting?tspno=2
- https://infopost.bhegts.com/cpl
- http://www.gasnom.com/ip/cameron/
- http://www.gasnom.com/ip/goldenpass/

Free anchors:
- https://www.eia.gov/naturalgas/weekly/
- https://www.eia.gov/naturalgas/monthly/
- https://www.eia.gov/dnav/ng/hist/n9133us2m.htm

Vendors:
- https://www.piperiv.com/pricing ; https://www.piperiv.com/lng/freeport/notes ; https://www.piperiv.com/natgas/links
- https://criterionrsch.com/data/natural-gas-flows ; https://developer.ice.com/fixed-income-data-services/catalog/criterion-research
- https://www.naturalgasintel.com/services/lng-datafeed/ ; https://www.naturalgasintel.com/premium/u-s-lng-export-tracker/
- https://eastdaley.com/commodities/natural-gas ; https://eastdaley.com/services/energy-data-studio
- https://www.enverus.com/products/natural-gas-transmission-analytics/
- https://www.factset.com/marketplace/catalog/product/factset-oil-and-gas-industry-natural-gas-markets
- https://rbnenergy.com/analytics/reports/natural-gas-suite
- https://www.woodmac.com/industry/commodity-trading-analytics/natural-gas-real-time/
- https://www.spglobal.com/commodityinsights/en/ci/products/pointlogic-gas.html ; https://www.marketplace.spglobal.com/en/datasets/gaslytics-pipeline-flows-(1755275929)
- https://www.kpler.com/solution/gas-power
