# Event-Weight Study — how much recurring scheduled releases move the market

**Generated:** 2026-07-12 · **Project:** DavisAI Markets (Kalshi) · Analyst: research agent
**Scripts:** `research/kalshi/hist/{event_study,intraday_study,macro_study}.py` · **Data (local):** `data/kalshi_hist/`
**Machine-readable:** `research/kalshi/event_weight_study.json`, `research/kalshi/source_map.json`

---

## TL;DR — ranked event-weight table

"Weight" = how much bigger the **absolute move** in the relevant underlying is on the release day/hour vs a **matched placebo** (same ET hour on non-event weekdays for intraday; other weekdays for daily). `ratio` >1 and a `welch_z` on |move| clearly above ~2 means the event carries real weight. Ranked by best-isolated (intraday release-hour) effect; cadence matters for how often that weight is paid.

| # | Event (ET time) | Kalshi | Underlying | Release-hour ratio (z) | Daily ratio (z) | Cadence | Verdict |
|---|---|---|---|---|---|---|---|
| 1 | **FOMC statement** (2:00pm) | KXFEDHIKE | ZN=F / ES=F | **5.06** (3.85) ZN · 3.03 (3.39) ES | 2yr +1.48 (2.45) | 8/yr | Heaviest macro. Bonds move ~5×, stocks ~3× in the 2pm hour. |
| 2 | **Nonfarm Payrolls** (8:30am, 1st Fri) | KXUSNFP | ZN=F / ES=F | **3.00** (3.77) ZN · 1.86 (2.37) ES | SP500 +1.25 (2.17) | 12/yr | Strong, rate-heavy. Dates first-Friday-derived (~90% accurate). |
| 3 | **EIA Natural Gas Storage** (10:30am Thu) | KXNATGASD | NG=F | **1.57** (5.21) | spot NULL (0.87) | 52/yr | **Heaviest recurring ENERGY event; highest significance of all (z=5.2).** |
| 4 | **EIA Petroleum Status — crude** (10:30am Wed) | KXWTI | CL=F | 1.12 (1.07); h11 1.18 | Wed +1.06 (2.15), N=2094 | 52/yr | Real but modest/diffuse — pre-empted by API report (Tue eve). |
| 5 | EIA Petroleum → **Brent** | KXBRENTD | Brent | — | 0.99 (−0.35) | 52/yr | **NULL** — European benchmark, not keyed to US EIA weekly. |
| — | **CPI** (8:30am mid-month) | KXCPIYOY | ZN=F / ES=F | *not measured* | — | 12/yr | **GAP** — no historical date list this session (see gaps). Method ready. |

**Single most important energy finding:** the **EIA Weekly Natural Gas Storage report is the dominant recurring energy catalyst.** At the 10:30 ET Thursday release, NG=F front-month futures move **1.57× a matched placebo** (mean |hourly move| 1.28% vs 0.82%, z=5.21, Cohen's d=0.63), with the effect spilling into the 11am hour (1.32×). Crucially, **Henry Hub SPOT (FRED DHHNGSP) shows NO Thursday effect (ratio 0.87)** — spot is a physical cash price that does not react to storage surprises the way futures do. Any study or signal keyed to natgas storage **must use NG=F futures, not spot.** The Kalshi KXNATGASD contract settles on the futures, so the futures reaction is the right proxy.

---

## Method (and its honest limits)

We do **NOT** have historical Kalshi *contract* price bins (that history is not collected yet), so we study the **reaction of the underlying market** to each historical release — the robust, immediately-available signal and a strong proxy, since Kalshi energy/macro contracts settle on these underlyings.

Two lenses, because granularity drives everything:
- **Intraday (best):** Yahoo Finance 60-minute futures bars, ~730 days. We measure the log-return of the bar that **contains the release** (10:30/8:30 fall in the 10:00/08:00 ET bar; 14:00 in the 14:00 bar) on release days, vs the **same ET hour on non-event weekdays** = a clean placebo that nets out time-of-day volatility. This isolates the release from the other 23 hours of noise.
- **Daily (deep history):** FRED close-to-close (WTI to 1986, natgas to 1997, yields to 1976). Deep N, but a release-day move is diluted into a full trading day of other news, and **Monday close-to-close spans the weekend (mechanically inflated)** — the placebo mitigates but does not remove this.

**Placebo is load-bearing.** No weight claim is made without it. For each event we report N, mean signed & |move|, the placebo mean |move|, the ratio, a Welch z on |move|, and Cohen's d.

**Release-date sourcing.** Weekly energy reports have a fixed weekday (EIA petroleum = Wed, natgas storage = Thu), so the *release day-of-week itself* is the event flag (robust; rare holiday shifts add conservative noise). FOMC uses the **exact statement dates** fetched from the Fed calendar (2021–2026, 44 meetings). NFP uses the **first-Friday rule** (≈90% accurate; occasional 2nd-Friday shifts noted). CPI/PCE dates were not cleanly obtainable this session.

**Caveats (do not over-claim):** (a) underlying reaction is a *proxy* for the contract move, not the contract itself; (b) a big release-day move can coincide with other news — N + placebo handle this *statistically*, not *causally*; (c) intraday N is modest (~19 FOMC, ~27 NFP, ~121 weekly-energy) due to the 730-day hourly window — effect sizes are large and significant regardless; (d) no historical **consensus/surprise** merged yet, so these are **unconditional** event-window weights (magnitude of reaction, not reaction-per-unit-surprise).

---

## ENERGY (most depth)

### #3 (energy #1) — EIA Weekly Natural Gas Storage → NG=F · KXNATGASD
- **Intraday:** release-hour (10:00–11:00 ET Thu) mean |move| **1.28%** vs placebo **0.82%** → **ratio 1.57, z=5.21, d=0.63** (n=121 release hours). By-hour scan confirms the signature: h10 1.57×, h11 1.32× (the surprise detonates at 10:30 and bleeds into the next hour), all other hours ≈1.0×.
- **Spot is blind:** DHHNGSP (Henry Hub spot) Thursday ratio **0.87** — no effect. Mon/Fri highest (weekend + physical-market artifacts). Confirms futures-only.
- **Why heaviest:** natgas has no high-weight private pre-release number (unlike crude's API report), so the EIA storage print is *the* weekly information event.

### #4 (energy #2) — EIA Weekly Petroleum Status (crude) → CL=F/WTI · KXWTI
- **Intraday:** release-hour ratio **1.12 (z=1.07)**, h11 **1.18** — real but modest and **diffuse** across 10–11am, plus mild elevation pre-open (h06–08). n=122.
- **Daily (deep):** Wednesday |move| in WTI 1.87% vs 1.76% placebo → **ratio 1.06, z=2.15** over **N=2094 Wednesdays back to 1986** — a small but statistically robust excess.
- **Interpretation:** the crude reaction is **pre-empted by the API Weekly Statistical Bulletin (~Tue 4:30pm ET)**, which puts a private inventory estimate into the market a day early; the EIA print often confirms rather than surprises. This is *the* reason crude's EIA weight is far below natgas storage's.

### #5 (energy #3, NULL) — EIA Petroleum → Brent · KXBRENTD
- Daily Wednesday ratio **0.99, z=−0.35** — **no measurable EIA weight.** Brent is a European/global benchmark keyed to ICE and global balances, not the US EIA weekly. A genuine non-mover — trade KXBRENTD off global/OPEC/geopolitical flow, not the Wednesday EIA print.

### Energy breadth
- **Propane weekly** (inside the petroleum report): Wed daily ratio 1.07, z=2.10 — same modest signature as crude.
- **RBOB gasoline (RB=F)** and the AAA retail-gas contract (KXAAAGASD): RB=F reacts to the same Wed EIA gasoline-stocks line; retail AAA gas is a slow weekly average that lags futures by 1–2 weeks (weight is in the *futures* move, not the retail print). Not separately quantified this session.

---

## MACRO

### #1 — FOMC statement → ZN=F / ES=F / 2yr · KXFEDHIKE
- **Intraday (2pm hour):** ZN=F (10yr note) **ratio 5.06, z=3.85, d=3.11**; ES=F (S&P) **ratio 3.03, z=3.39, d=1.65** (n=19 meetings in the 730d window). The single largest per-event reaction measured.
- **Daily:** 2yr yield |change| 7.07bps vs 4.78bps placebo → **1.48, z=2.45**; S&P500 1.33, z=1.85. (n=44 meetings 2021–2026.)

### #2 — Nonfarm Payrolls → ZN=F / ES=F · KXUSNFP
- **Intraday (8:30 hour):** ZN=F **ratio 3.00, z=3.77, d=1.31**; ES=F **1.86, z=2.37, d=0.69** (n=27). Rate-heavy, as expected.
- **Daily:** SP500 1.25 (z=2.17); 2yr 1.16 (z=1.37, diluted by the full day).
- Caveat: first-Friday-derived dates; a handful of 2nd-Friday shifts add conservative noise.

### CPI / PCE — GAP (see below).

---

## Data we COULD and COULD NOT reach

**Reached (used):**
- **FRED CSV (no key):** WTI (DCOILWTICO, 1986+), Brent (DCOILBRENTEU, 1987+), Henry Hub spot (DHHNGSP, 1997+), propane (DPROPANEMBTX), DGS10/DGS2 (yields), SP500, DTWEXBGS. Deep, clean, no missing markers.
- **Yahoo Finance chart API (no key):** CL=F, NG=F, RB=F, BZ=F, ES=F, ZN=F, ^TNX — **daily 10y + 60-minute ~730d.** The 60m data is what enabled the tight release-window isolation. (DX=F 404 — used DTWEXBGS for the dollar.)
- **Fed FOMC calendar** (federalreserve.gov, 200) — exact statement dates 2021–2026.
- **Kalshi public API (no auth)** — see below.

**Could NOT reach (noted, not fabricated):**
- **stooq.com** — behind a JS proof-of-work anti-bot challenge; unusable via curl. (Yahoo substituted for all futures.)
- **EIA API v2** — needs a key; **DEMO_KEY works** (rate-limited) and returns actual historical inventory values (6896 rows) — usable for *actuals*, register a free key for production.
- **FRED releases API / EIA release dates** — need a key.
- **BLS.gov** (CPI + NFP schedule/release pages) — **403 bot-blocked** through the proxy → no historical CPI/PCE release-date list this session.
- **investing.com, forexfactory.com HTML, ir.eia.gov/wpsr** — 403 bot-blocked.

**Kalshi candlesticks — ARE they public? YES (mostly).**
- `GET /trade-api/v2/markets/trades?ticker=...` returns **real historical trades (price + timestamp + size) with NO auth** on settled markets — verified on `KXWTI-26JUL1014-T80.99`. This unlocks **contract-level reaction studies** later.
- `GET /trade-api/v2/series/{s}/markets/{m}/candlesticks` is **also public (no auth — returns validation errors, not 401)** but returned **empty** for my test market/range (likely sparse hourly activity or an exact-param requirement). Trades are the reliable path today; candlesticks are reachable but need a param sweep on an active market to confirm OHLC output.
- **Implication:** once we pick a recurring event + a liquid settled contract, we can pull its trade tape around the release and confirm the underlying study transfers to the contract itself. (Not done this session — no contract-price history is stored yet, and the task scoped it as a bonus probe.)

---

## SOURCE MAP (added task) — per-family, 3 tiers, ranked, with reachability

Full machine-readable version: `research/kalshi/source_map.json`. Tiers: **RELEASE** (the number/statement that *is* the event) · **CONSENSUS** (what the surprise is measured against — the priority, because markets move on surprise) · **LEADING** (what counterparties trade *ahead* on). Reachability tested through the session proxy. "Most-used by Kalshi counterparties" is partly unknowable (small venue, no trader survey) — ranked by canonical underlying-market importance + our empirical which-releases-move-the-market evidence.

### ENERGY (KXWTI, KXBRENTD, KXNATGASD, KXAAAGASD)
**RELEASE** — 1) **EIA Natural Gas Storage** `ir.eia.gov/ngs/ngs.html` (302) / API `api.eia.gov/v2/natural-gas/stor/wkly` (DEMO_KEY 200) — Thu 10:30 ET, **highest load** (NG=F 1.57× placebo, z=5.2). 2) **EIA Weekly Petroleum Status** `eia.gov/petroleum/supply/weekly` (200) — Wed 10:30 ET, modest crude weight. 3) EIA STEO (monthly). **In news_ingest:** EIA press/Today-in-Energy yes; the *dedicated weekly-report data feeds are MISSING.*
**CONSENSUS** — 1) **ForexFactory JSON** `nfs.faireconomy.media/ff_calendar_thisweek.json` (200) — **FREE, VERIFIED** carries "Crude Oil Inventories" forecast (−1.9M) and "Natural Gas Storage" forecast (60B). **← the free energy-surprise unlock** (current-week only; poll to accrue). 2) **API crude bulletin** (Tue eve, paid; hits news wires) — doubles as consensus + leading; explains crude's diffuse EIA reaction. 3) TradingEconomics calendar (200). 4) Reuters polls (news-text only).
**LEADING** — 1) **API crude inventory** (Tue night, news-wire) — strongest crude front-run. 2) **NOAA GFS/NBM** `nomads.ncep.noaa.gov` (200) — natgas demand. 3) Kpler/Vortexa/Genscape flows (paid — deprioritized).

### MACRO (KXCPIYOY, KXUSNFP, KXFEDHIKE)
**RELEASE** — 1) **FOMC statement** `federalreserve.gov` (200) — heaviest macro (ZN=F 5.1×). *In news_ingest: yes (Fed Press).* 2) **BLS NFP** `bls.gov/news.release/empsit` (**403 blocked**) — ZN=F 3.0×. **MISSING from news_ingest.** 3) **BLS CPI** (**403 blocked**) — marquee, MISSING. 4) BEA PCE — MISSING.
**CONSENSUS** — 1) **ForexFactory JSON** (200) — **FREE, VERIFIED** CPI/NFP/FOMC forecast+previous+exact ET timestamp. **← the free macro-surprise unlock.** 2) TradingEconomics `tradingeconomics.com/calendar` (200). 3) CNBC RSS (200). 4) investing.com / FF-HTML (403 — use the JSON).
**LEADING** — 1) **CME Fed Funds futures ZQ=F** (Yahoo 200) — market-implied policy path. 2) Fed speaker calendar (in FF JSON). 3) ADP + weekly jobless claims (FF JSON / FRED ICSA).

### WEATHER (daily-high temp, hurricane)
**RELEASE** — 1) **NWS/ASOS station ob** `api.weather.gov/stations/{ID}/observations/latest` (200) + METAR `aviationweather.gov/api/data/metar` (200) — **the ASOS daily max IS the settlement value.** MISSING from news_ingest (station-specific). 2) **NHC advisories** `nhc.noaa.gov/index-at.xml` (200) — *in news_ingest.*
**CONSENSUS** — NWS NDFD/NBM forecast `api.weather.gov/gridpoints/.../forecast` (200) — the official expected high.
**LEADING** — GFS/NBM runs (NOMADS 200, 4×/day); ECMWF Open Data (highest skill, free subset).

### ELECTRICITY (ISO price/load, if listed)
**RELEASE/LEADING** — ERCOT `ercot.com/api/1/services/read/dashboards/fuel-mix.json` (200), PJM DataMiner2 `dataminer2.pjm.com` (200), MISO RT broker (200) — all **free, reachable**; RT load/price + weather drive spike probability. **CONSENSUS** — ISO day-ahead forecast load & DA LMP (same hosts).

### Source-map bottom line
- **Top MISSING release feeds to add to news_ingest:** (1) **EIA weekly report data feeds** — natgas storage (`ir.eia.gov/ngs` / EIA API `natural-gas/stor/wkly`) and petroleum status (EIA API `petroleum/stoc/wstk`), our **highest-and-4th-highest energy catalysts**; (2) **BLS NFP + CPI** (currently 403-blocked — need a UA/mirror workaround or a keyed calendar); (3) **NWS/ASOS station obs** for temperature-contract settlement; (4) **BEA PCE**.
- **Free consensus exists for BOTH energy and macro:** the **ForexFactory calendar JSON** (`nfs.faireconomy.media/ff_calendar_thisweek.json`) carries forecast+previous for EIA crude/natgas AND CPI/NFP/FOMC — verified live. It is **current-week only** (no deep history), so the **surprise-conditioned coupling test** is unlocked *going forward by polling weekly to accrue a surprise series*; a historical surprise backtest still needs a consensus archive (EIA DEMO_KEY already supplies deep *actuals*).

---

## Recommended next steps
1. **Turn on the surprise test:** start weekly polling of the ForexFactory JSON to build (actual − forecast) for EIA crude/natgas + CPI/NFP/FOMC; regress underlying release-window move on surprise (does bigger surprise → bigger move, and with what slope per cell). Pair with EIA DEMO_KEY actuals for deep history.
2. **Register a free EIA API key** and add the two weekly-report feeds to news_ingest (highest-value energy gap).
3. **On-target confirmation:** pull the Kalshi *trades* tape around one natgas-storage Thursday for a liquid KXNATGASD contract; show the contract-price reaction matches the NG=F 1.57× signature.
4. **Close the CPI gap:** obtain a historical CPI/PCE release-date list (keyed FRED releases API, or accrue via FF/TE) and run the identical intraday study — expected to rank with or above NFP on rates.
5. Fix daily's Monday-weekend artifact in any daily-only extension by restricting placebo to single-calendar-day midweek returns.
