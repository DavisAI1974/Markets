# Event-Weight Study — how much recurring scheduled releases move the market

**Generated:** 2026-07-12 · **Project:** DavisAI Markets (Kalshi) · Analyst: research agent
**Scripts:** `research/kalshi/hist/{event_study,intraday_study,macro_study}.py` · **Data (local):** `data/kalshi_hist/`
**Machine-readable:** `research/kalshi/event_weight_study.json`, `research/kalshi/source_map.json`

---

## TL;DR — ranked event-weight table

> **Read this table as the VOLATILITY / repricing lens only** (how much the market moves on the event). It does **not** tell you *which way* — for the tradeable **directional** edge see the **PER-BUCKET (conditional) analysis** immediately below, which supersedes any directional reading of these pooled numbers. Key correction: natgas is #3 by volatility here but its directional seasonal-surprise edge is a **coin flip**, while crude (#4) carries a **real ~60% day-direction edge**.

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

## ⚑ PER-BUCKET (conditional) analysis — the directional edge (methodology correction, 2026-07-12)

**Hard rule (founder / project standing rule):** *never pool `|move|`.* The pooled ratio above (natgas 1.57×, etc.) measures **volatility / how much the market re-prices** — useful for volatility-style positioning — but it **averages bullish-surprise→up, bearish-surprise→down, and sell-the-news reversals into one number, destroying the directional structure that is the tradeable content.** Every release is bucketed by **signed SURPRISE × signed REACTION**, and we report **signed** per-bucket stats + a directional hit-rate.

**Surprise proxy (honest):** ENERGY uses `surprise = actual weekly EIA change − 5-year average change for the same ISO calendar week` — a **PROXY** for street consensus that captures the *seasonal* surprise, **not** the exact desk number. The real consensus-conditioned version comes **forward** via ForexFactory polling. Convention: a storage **build bigger than seasonal = more supply = bearish = expect price DOWN**. "Directional hit-rate" = P(reaction sign matches the fundamentally-implied direction) on **meaningful** surprises (excludes the smallest-|surprise| tercile). **Placebo for direction = the 50% binomial null** (z shown). Reaction = signed NG=F/CL=F move, two lenses: **release-hour** (Yahoo 60m, ~730d, clean window) and **release-day** close-to-close (Yahoo 1d, ~10y, deeper N). EIA actuals via API DEMO_KEY: natgas storage 2010–2026 (521 matched releases), crude stocks 1982–2026 (521 matched to the 2016+ futures window).

### 🔑 Headline: the directional edge is INVERTED from the volatility ranking
- **Natgas = the biggest mover but the seasonal-surprise sign is a COIN FLIP.** High `|move|`, **no directional edge.**
- **Crude = a modest mover but carries a REAL ~60% directional edge on the release DAY.**

### Energy per-bucket table (meaningful surprises; hit-rate vs 50% placebo)

| Cell | Lens | N (meaningful) | Directional hit-rate (z) | Confirm : Counter | Sell-the-news bucket | Dose-response (small→large \|surprise\|) | Verdict |
|---|---|---|---|---|---|---|---|
| **Crude / KXWTI** | **release-DAY** | 347 | **0.599 (z=3.70)** | **208 : 139** | minority (bull→UP 120 > bull→DOWN 74) | **0.584 → 0.615 (monotone)** | **REAL directional edge** |
| Crude / KXWTI | release-hour (10:30) | 83 | 0.446 (z=−0.99) | 37 : 46 | — | 0.415 → 0.476 | NONE in the 10:30 hour |
| **Natgas / KXNATGASD** | release-DAY | 347 | 0.516 (z=0.59) | 179 : 168 | **LARGE: bull→DOWN 91 ≥ bull→UP 86** | 0.474 → 0.557 | **NULL (coin flip)** |
| Natgas / KXNATGASD | release-hour (10:30) | 83 | 0.518 (z=0.33) | 43 : 40 | large (23 vs 19) | 0.537 → 0.500 | NULL (coin flip) |

### What the buckets say
- **Crude (KXWTI) — a real, tradeable directional signal on the day.** When the crude build/draw beats its 5-yr seasonal norm, CL=F closes in the fundamentally-implied direction **59.9% of the time** (z=3.70 over 347 meaningful releases, 2016–2026), and the hit-rate **rises with surprise size** (58.4% → 61.5% small→large tercile — a dose-response, i.e. the surprise really drives it, not an artifact). Confirmation buckets outweigh counter-moves **208:139**; the **sell-the-news bucket is the minority** (bullish→DOWN 74 vs bullish→UP 120). **BUT the edge is NOT in the 10:30 release hour** (hit-rate 0.446, coin-flip): it develops over the full session, consistent with the **API report (Tue eve) pre-empting** the instantaneous spike while the EIA confirmation plays out intraday. → Trade the *day-settled* KXWTI direction off the seasonal surprise, not a tight release-window straddle.
- **Natgas (KXNATGASD) — high volatility, NO directional edge from the seasonal proxy (an important NULL).** Hit-rate **0.516 / 0.518** (coin flip) on both lenses; confirmation vs counter is **179:168** (≈50/50). Crucially, the **sell-the-news bucket (bullish-surprise→price DOWN, N=91) is as large as the confirmation bucket (bullish→UP, N=86)** — exactly the killer bucket a naive directional trader misses. The pooled **1.57× `|move|` was pure repricing volatility, not direction.** Regime split reveals *why*: **injection season corr(bull,reaction)=+0.34 vs withdrawal season −0.23** (opposite signs that cancel in the pool) — the seasonal 5-yr-average is a poor expectation in **weather-driven winter draws**, so the proxy mismeasures the surprise exactly when it matters. → Natgas *needs the real street storage consensus* (ForexFactory forward) before any directional claim; on the seasonal proxy it is untradeable directionally.

### Natgas regime split — 4 DATA-DISCOVERED regimes (double-humped demand)
Founder correction: **do not impose calendar months.** Modern gas demand is **double-humped in temperature** — cold→heating draws *and* hot→power-burn draws — with mild spring/fall shoulders between. Regimes are discovered per-release from the **actual weekly degree-days** (thresholds from the observed humps, so warm/cold years reassign weeks automatically): `winter-withdrawal` = weekly gas-wtd HDD > 120; `summer-withdrawal` = pop-wtd CDD > 40; else `spring`/`fall` injection by ISO-week. **Discovery evidence** (national median weekly change): deep draws wk 46–13 (HDD 124–217), then a **build-MINIMUM at wk 28–31 (+26…+35 Bcf) coincident with the CDD peak (80–88)** = the summer power-burn hump, then builds recover. Regime counts: winter 186, summer 152, spring 105, fall 78.

> **Honest data note:** on the **national aggregate**, the summer CDD hump is a **build-MINIMUM, not a net draw** (median +52 Bcf) — peak-heat weeks approach zero build but don't flip the aggregate negative. The double-hump is unmistakable in *degree-days* and in the *build-minimum*; "summer withdrawal" is true at the demand-driver level and in extreme weeks, not on the national median.

| Regime | N | median Δ (Bcf) | mean\|reaction\| DAY | Directional hit-rate DAY (z) | Directional hit-rate HOUR (z, small-N) | Sell-news:confirm (bull, day) |
|---|---|---|---|---|---|---|
| **winter-withdrawal (HDD)** | 186 | **−91** | **3.44%** (biggest) | 0.528 (0.63) | **0.40 (−1.0) INVERTED** | 37:28 (sell-news wins) |
| summer-withdrawal (CDD) | 152 | +52 | 2.52% | 0.545 (0.90) | 0.71 (1.96) | 32:37 |
| spring-injection | 105 | +79 | 2.67% | 0.507 (0.12) | 0.78 (2.71) | 10:10 |
| fall-injection | 78 | +74 | 3.35% | 0.549 (0.70) | 0.27 (−1.5, N=11) | 9:12 |

**Refines the founder's hypothesis (honestly):** the two **withdrawal humps are the biggest MOVERS** (winter mean|move| 3.44% is the largest of any regime — confirming winter is the sharp weather-demand driver for *volatility*), **but the seasonal-surprise proxy is directionally BLINDEST exactly there** — winter's release-hour reaction *inverts* (hit 0.40, sell-the-news 9:4) and the day-lens is a coin flip (0.528). The seasonal proxy predicts *direction* better in the **build/injection regimes** (spring 0.78, summer 0.71 intraday). Reason, established in the next sub-section: **in winter the weather owns the storage number**, so the 5-yr-average is a poor consensus stand-in — the surprise is mismeasured precisely when moves are largest. (Intraday N is small — 11–25 meaningful per regime; lead with the day lens, treat the hour lens as suggestive.)

### Natgas WEATHER-DRIVER CHAIN — the strategic bridge (weather → storage → price)
Established empirically in two links, per regime, using **NOAA CPC gas-weighted HDD (`UtilityGas.Heating`) + pop-weighted CDD (`Population.Cooling`), 2010–2026** (national = equal-weight of the 9 census divisions; a proxy, flagged). Weather anomaly = weekly gas-wtd HDD (winter) / pop-wtd CDD (summer) minus the 5-yr same-ISO-week normal.

| Regime | **LINK A: weather anomaly → storage surprise** | | | **LINK B: → price at release** |
|---|---|---|---|---|
| | corr(w_anom, surprise) | R² | surprise-sign hit | corr / dir-hit (day) |
| **winter-withdrawal** | **−0.924** | **0.854** | **0.908** | −0.03 / 0.52 |
| spring-injection | −0.799 | 0.638 | 0.724 | −0.02 / 0.51 |
| summer-withdrawal | −0.543 | 0.295 | 0.631 | +0.11 / 0.48 |
| fall-injection | −0.529 | 0.279 | 0.564 | +0.11 / 0.51 |
| **ALL** | **−0.855** | **0.731** | **0.740** | −0.01 / 0.50 |

- **LINK A is STRONG — weather predicts the storage number.** In winter the weekly weather anomaly explains **85% of the variance of the storage surprise (R²=0.854)** and calls its **sign 91%** of the time; pooled R²=0.73. The chain *weather → heating/cooling demand → storage draw/build* is real and large (strongest in the HDD-driven winter hump; weaker in the CDD/power-burn summer hump, R²=0.30, because power burn also depends on renewables/nuclear/outages).
- **LINK B is ~ZERO — the storage number's release-window price impact is already arbitraged.** Neither the weather anomaly nor the storage surprise predicts the release-window price move (corr ≈ 0, directional hit ≈ 0.50 everywhere). The market prices weather **continuously**, so by release time the weather-implied storage level is baked in; the release move reflects only the (small) print-vs-*street-consensus* residual, which the seasonal/weather anomaly is not.

**The bridge, stated honestly (this is the strategic payoff):** a degree-day **forecast is genuinely upstream of the natgas storage NUMBER** (R²=0.85 winter) — so the OD-weather forecaster **is a storage-print forecaster**, and for any contract that settles on the **storage number itself** that is a clean **edge on the outcome that does not get arbed** (the founder's Kalshi thesis). But it is **NOT** automatically a *price*-reaction edge at the storage release: converting weather skill into a **price** edge requires (a) beating the **street consensus** on weather (an edge over what's already priced), and (b) trading the **price path** as forecasts evolve, **not** the storage-release-window reaction (which LINK B shows is efficient). Desk lore ("weather drives natgas") is **confirmed for the storage number, weaker than implied for the release-window price.**

**Scripts:** `hist/natgas_season_study.py` (regime discovery + split), `hist/natgas_weather_chain.py` (two-link chain). **Weather data (local):** `data/kalshi_hist/cpc_HDD.json`, `cpc_CDD.json`. **JSON:** `event_weight_study.json → conditional_per_bucket.natgas_regime_split` and `.natgas_weather_chain`.

### Macro (phase-2, WEAK proxy — do not size off this)
NFP bucketed with `surprise = payrolls − trailing-12-month trend` (a **trend** stand-in, **not** consensus) vs ES=F/ZN=F 8:30-hour reaction: **hit-rate 0.526 (z=0.23, n=19)** — **inconclusive**, as expected. The trailing trend is a weak consensus proxy and intraday N is tiny (~2.4 yr). This is a placeholder; the legitimate macro-surprise buckets require **ForexFactory forward polling** of the CPI/NFP/FOMC forecast. (FOMC/NFP still carry the largest *unconditional* per-event weight — see the volatility table — but their *directional* buckets are phase-2.)

### Honesty on the proxy
The 5-yr-seasonal-average surprise is a **PROXY for consensus**: it captures the *seasonal* component of the surprise, not the exact street number the market actually prices against. This is legitimate for **crude** (stocks are seasonally driven and less weather-dependent, and the dose-response + z=3.7 hold up) and demonstrably **weak for natgas in withdrawal season** (weather-driven). The real consensus-conditioned version is unlocked **forward** by polling the ForexFactory JSON (`nfs.faireconomy.media`, verified to carry EIA crude/natgas forecasts) week by week. Placebo discipline kept throughout (directional hit-rate vs the 50% binomial null). Nulls and coin-flip buckets are reported as findings, not hidden.

**Scripts:** `hist/eia_bucket_study.py` (energy, deep history), `hist/macro_bucket_study.py` (NFP phase-2). **Data:** `data/kalshi_hist/eia_ng_storage.json`, `eia_crude_stocks.json` (EIA API, local). **Per-bucket JSON:** `event_weight_study.json → conditional_per_bucket`.

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

### ⚙ FREE forward-consensus fetch recipe (for the recurring poller — energy + macro surprise axis)
**Best free source: the ForexFactory weekly calendar JSON.** Verified live, no key, no auth.
- **URL:** `https://nfs.faireconomy.media/ff_calendar_thisweek.json` (host `nfs.faireconomy.media`; send a browser `User-Agent`).
- **Shape:** a flat JSON array of event objects. **Exact fields per object:** `title` (e.g. `"Natural Gas Storage"`, `"Crude Oil Inventories"`, `"CPI m/m"`, `"Non-Farm Employment Change"`, `"Federal Funds Rate"`), `country` (filter `== "USD"`), `date` (ISO-8601 **with ET offset**, e.g. `"2026-07-09T10:30:00-04:00"`), `impact` (`"Low"|"Medium"|"High"`), `forecast` (the **consensus** string, e.g. `"60B"`, `"-1.9M"`, `"0.3%"`; may be `""`), `previous` (prior print).
- **`actual`:** the current-week file is **forward-looking** (only `forecast`+`previous` before release); the **`actual` value populates in-place after the release time.** So the poller must **snapshot twice**: (1) before the release → capture `forecast`+`previous`; (2) after → capture `actual`. **Surprise = parse_num(actual) − parse_num(forecast)** (strip suffixes `B`/`M`/`K`/`%`, keep sign).
- **Coverage limitation (honest):** only the **current week** is served — `ff_calendar_lastweek/nextweek/thismonth/nextmonth` all **404**. So there is **no deep history** here; you **accrue** the consensus series by polling every week going forward. Recommended poller: hit the URL ~hourly, upsert events keyed by `(title, date)`, and record `forecast` on first sight + `actual` once non-empty.
- **Event → contract mapping for the surprise axis:** `Natural Gas Storage`→KXNATGASD, `Crude Oil Inventories`→KXWTI, `CPI m/m`+`CPI y/y`→KXCPIYOY, `Non-Farm Employment Change`→KXUSNFP, `Federal Funds Rate`+`FOMC Statement`→KXFEDHIKE.
- **Backups:** `tradingeconomics.com/calendar` (200, freemium — `actual`/`forecast`/`previous` columns, richer but history/rate gated); CNBC RSS (200, headline narration). **Paid** if a deep *historical* consensus archive is needed: Trading Economics API, Econoday, or MarketWatch/Estimize — none free for history. For energy *actuals* (deep history, free) the **EIA API with a free key** already supplies the printed numbers; only the **consensus** must be accrued forward via ForexFactory.

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
