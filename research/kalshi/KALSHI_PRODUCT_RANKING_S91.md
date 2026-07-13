# KALSHI PRODUCT RANKING — per-day FIT to our two live edges (S91, 2026-07-13)

Ranked, per-cell analysis of Kalshi's currently-tradeable catalog against our two live Kalshi edges.
No pooled scores — every product is scored per-cell on the five axes and net-of-fee at **both** maker
and taker. All series/volume/depth/rules numbers below were pulled LIVE from the Kalshi public API
(`api.elections.kalshi.com/trade-api/v2`) on 2026-07-13; external structure/liquidity claims are cited.

## Our two edges (restated from the repo, so the fit test is explicit)
1. **Futures→Kalshi LAG** (`LAG_EXPLOIT_FINDINGS_S81.md`, `NYMEX_CANARY_NOTES_S84.md`): NYMEX/ICE moves
   first, Kalshi reprices seconds-to-a-minute later (futures lead, Kalshi never leads — S80 19/19).
   Direction is easy and **sharpens with move size** (0.55 at $0.05–0.10 → 0.77 at $0.40+). Binding
   constraint = **move-size vs fee**, not direction; net-positive proven when gated to *lagging contract
   × big futures move* (+91¢/26 trades over 5 WTI days). Sub-minute (our Pyth / raw MBP-10 tick tape)
   turns it from rare into frequent. Needs: a liquid futures underlying we can tape + a deep intraday
   Kalshi book.
2. **Weather-distribution** (`WEATHER_BASELINE_S82.md`, `WEATHER_REGIME_FINDINGS_S84.md`, S90 handoff):
   `KXHIGH*`/`KXLOW*` daily-temp ladders (6 mutually-exclusive ~2°F buckets, re-centered daily). Greg's
   OD temp forecaster hands a full residual distribution; we buy the 1–3 buckets the market centered
   away from. S90 update: the OD edge is **BROAD** (everyday few-degree miss — winter DJF +21%, mid-error
   2–5°F days the largest cell +21%, all leads f048–f120 +7–9%), not just frontal-transition days.
   Binding constraint = **thin book depth**, not fee.

## Fee reference (net-of-fee at maker AND taker) — Kalshi fee schedule, July 2026
Taker fee per contract = `ceil(0.07 × P × (1−P) × 100)/100`; **maker fee = 25% of taker**
([Kalshi fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf),
[pm.wiki](https://pm.wiki/learn/kalshi-fees-explained)). So per side:
- Near mid (P=0.50): taker **1.75¢**, maker **~0.44¢**. Round-trip taker ~3.5¢, maker ~0.9¢.
- Tail bucket (P=0.10): taker **0.63¢**, maker **~0.16¢**. This is why the weather tail-bucket trade is
  fee-cheap and the near-money lag trade is fee-bound — and why our fee-floor rule (rest a **maker**
  limit at the predicted turn) is load-bearing: it cuts the cost 4× on both edges.

---

## LIVE catalog scan — what actually exists and trades (API, 2026-07-13)

**Energy / commodity daily (LAG surface):**
| series | title | settle source | open mkts | vol_24h | OI | ATM book depth (yes/no contracts) | edge |
|--------|-------|---------------|-----------|---------|-----|-----------------------------------|------|
| **KXWTI** | WTI daily | ICE WTI Aug-26 **daily settle** 14:30 ET | 75 | **111k** | **291k** | **14.8k / 12.1k** | LAG |
| **KXBRENTD** | Brent daily | **Pyth** BRENTU6 1-min candle @5PM EDT | 50 | **150k** | 85k | 13.1k / 0.7k (one-sided) | LAG |
| **KXNATGASD** | Henry Hub NG daily | **Pyth** NGDQ6 1-min candle @5PM EDT | 120 | 53k | 29k | 6.3k / 7.1k | LAG (+ settle-oracle) |
| KXAAAGASD | US retail gasoline daily | **AAA survey** (no futures) | 17 | 33k | 27k | 1.9k / 3.7k | NEITHER (no tape) |
| KXGOLDH | Gold hourly | COMEX GC | 80 | **0.58k** | 0.5k | 35 / 1 (dead) | LAG but no capacity |
| KXNASDAQ100 | Nasdaq-100 range | NQ future | 60 | 17.7k | 11.5k | 102k / 106k (very deep) | LAG (efficient) |
| KXBTCD / KXETHD | BTC / ETH daily+hourly | crypto spot/CME | 300 / 165 | **3.16M** / 104k | 1.78M / 74k | very deep | LAG (efficient) + OD toolkit |

**Weather daily-high / low (WEATHER-DISTRIBUTION surface):**
| series | city | settle station | open mkts | vol_24h | OI | edge-cell character |
|--------|------|----------------|-----------|---------|-----|---------------------|
| **KXHIGHNY** | NYC | Central Park (NWS Daily Climat. Report) | 12 | **116k** | 78k | transition-rich = **most room**; broad daily |
| KXHIGHLAX | LA | LAX | 12 | **313k** (highest) | 214k | marine-clamped = **least room** (efficient) |
| KXHIGHCHI | Chicago | (verify MDW vs ORD) | 12 | 92k | 62k | frontal / transition-rich |
| KXHIGHTHOU | Houston | | 12 | 39k | 27k | summer-ridge / heat-dome cell |
| KXHIGHTPHX | Phoenix | | 12 | 26k | 20k | heat-dome cell |
| KXHIGHDEN | Denver | | 12 | 18k | 15k | transition-rich but **thin** |
| KXLOWTNYC | NYC low | Central Park | 12 | 19k | 19k | second surface, same forecaster |

**Confirmed NOT a fit / delisted-or-dormant right now:** `KXAAAGASD` (AAA retail survey — no futures tape,
LAG cannot apply), `KXGOLDH` (great GC tape but vol_24h≈0 → no capacity), `KXNGASW`/`KXWTIMONTHLY`/
`KXUSDJPYH`/`KXGBP`/`KXUSNFP`/`JOBLESS` (no open markets at scan time — weekly/monthly release cadence,
between cycles). Macro release series (`KXCPIYOY` vol_24h 154k, OI 1.13M) are large but are **news-release
events**, not a lag or weather-distribution surface — neither of our two edges maps; they belong to the
separate release/consensus thread.

---

## RANKING — per-cell, on the five axes

Axes: (a) which edge, (b) opportunities/day, (c) book depth & achievable size, (d) directness of the
leading signal we already collect, (e) fee vs typical edge. Reported per-cell; never a pooled score.

### #1 — KXWTI (WTI crude daily) · EDGE: futures→Kalshi LAG
- **(a) Edge:** LAG. The purest instance of our proven S81 result — the +91¢/26 backtest WAS on KXWTI.
- **(d) Leading signal (direct):** ICE/NYMEX WTI front-month. We **already collect both** feeds: Databento
  CL true-tick MBP-10 (raw year on S3) and the live Pyth WTI SSE stream (`pyth_collector.py`). Zero new
  ingest. Underlying is the Aug-26 contract; settles on the **ICE daily settle @14:30 ET** (rules_primary
  verified live).
- **(b) Opportunities/day:** ~30 near-money strikes on the daily ladder reprice continuously; the S81
  gate fires on big futures moves — ~5 qualifying big-move events/WTI-day at 1-min, and **sub-minute (our
  tick tape) multiplies both count and captured reprice** (catches the full move before the ~1¢-residual
  decay). Highest genuine intraday opportunity count of the energy set.
- **(c) Capacity:** Deepest energy book — **14.8k yes / 12.1k no** resting on the ATM strike, OI 291k,
  vol_24h 111k. You can size the lag trade here without moving the book. Best capacity of any LAG cell.
- **(e) Fee vs edge:** Near-money strikes sit at P≈0.5 → taker 1.75¢/side (3.5¢ RT), maker ~0.44¢/side.
  Gated to ≥$0.40 futures moves the reprice is ~4.5¢ → clears taker; **work it maker** to clear
  comfortably and lift the small-move sub-gate.
- **Caveat:** [botforkalshi/kalshiview](https://www.botforkalshi.com/blog/how-to-trade-oil-on-kalshi)
  note "no microsecond race to the *settlement* print" — true, and irrelevant: our edge is the **intraday
  repricing lag** (measured, seconds-to-a-minute), not the settlement race.
- **Next build step:** point the S87 `lag_join.py` at the live Pyth WTI stream + the KXWTI intraday book
  bins (`kalshi_collector.py` already watches KXWTI); run the rolling per-contract lag classifier live,
  fire maker limits gated to big moves. Everything exists — this is a wiring + live-canary step.

### #2 — KXHIGHNY (NYC daily high temp) · EDGE: weather-distribution
- **(a) Edge:** Weather-distribution — the flagship cell. NY is the **transition-rich** book: biggest
  naive-baseline failure = biggest room (`WEATHER_REGIME_FINDINGS_S84.md`), and the S90 OD update makes
  the edge **broad/everyday**, not just frontal days.
- **(d) Leading signal (direct):** Greg's OD temp forecaster (residual distribution per
  `WEATHER_FORECAST_INTERFACE_S90.md`) + NWS/ASOS raw hourly feed (`nws_temp_feed.py --ingest-hourly`,
  already ingesting to S3). Settles on the **NWS Daily Climatological Report for Central Park** (verified).
- **(b) Opportunities/day:** One 6-bucket ladder per day, and the edge shows in the **aggregate of ~8–20
  lines/day across cities** — NY is the anchor line. Daily cadence, every day.
- **(c) Capacity (BINDING):** Good top-line liquidity (vol_24h 116k, OI 78k) but **per-strike book is
  thin** (sampled ATM strike 616 yes / 2330 no). Depth — not fee — caps size; keep lines small, spread
  across buckets/cities. This matches the S90 read exactly.
- **(e) Fee vs edge:** The buckets we buy are the **cheap under-weighted tails** (P≈0.10–0.25) → taker
  0.6–1.6¢, maker ~0.15–0.4¢. Fee is negligible; a called few-degree miss pays 4–8× the fee
  (`KXHIGHNY-26JUN29` worked example: +$87 on a 12¢ entry). Best fee-vs-edge of any cell.
- **Next build step:** wire the `(value,sigma)→bucket-prob` bridge to score tomorrow's NY ladder per-cell
  vs the live market (`weather_regime_score.py` drop-in), net-of-fee, on the WHIFF/mid-error cells only;
  needs a sample of the forecaster's per-day emit. Confirm the exact settlement station per city first.

### #3 — KXNATGASD (Henry Hub natural gas daily) · EDGE: LAG + settlement-oracle (uniquely ours)
- **(a) Edge:** LAG **plus a second edge nobody else is positioned for** — KXNATGASD settles on **Pyth's
  NGDQ6 1-min candle @5PM EDT**, NOT CME. Tracking CME/Databento vs Pyth in the 5PM settle window gives a
  **settlement-oracle divergence** trade (if CME moves but Pyth's candle reads otherwise, we already know
  where Kalshi lands — `NYMEX_CANARY_NOTES_S84.md` S87 section).
- **(d) Leading signal (direct, and this is our data moat):** we **own the full-raw MBP-10 NG tick year on
  S3** (every message, 10-level book, nanosecond) — the richest NG microstructure dataset on the desk. The
  Thu EIA Weekly NG Storage print is the biggest intraday catalyst (`event_move_baseline` shows NG is
  front-loaded: 60s captures 66% of the move).
- **(b) Opportunities/day:** Daily settle + a large Thursday catalyst; ladder reprices intraday like WTI.
  Fewer clean big-move lag events than WTI (thinner tape/book) but the weekly catalyst is a reliable,
  high-conviction window.
- **(c) Capacity:** Moderate — 6.3k/7.1k ATM depth, vol_24h 53k, OI 29k. Two-sided (unlike Brent). Sizeable
  but below WTI.
- **(e) Fee vs edge:** Same near-money fee as WTI; the settlement-oracle edge, when it fires, is large
  (Kalshi pays off the Pyth number regardless of CME) and effectively fee-insensitive.
- **Caveat / next build step:** the Pyth NGDQ6 **live** feed is still the known-bogus id
  (`pyth_collector.py` FEEDS) — **fix it** (a valid Pyth NG feed exists since Kalshi settles off it). Then
  run the CME−Pyth 5PM-window divergence monitor + the standard lag join. This is the highest-leverage
  build because the data + a *second* edge are already ours.

### #4 — KXBRENTD (Brent crude daily) · EDGE: futures→Kalshi LAG
- **(a) Edge:** LAG, same mechanics as WTI; settles on **Pyth BRENTU6 1-min candle @5PM EDT** (verified)
  → same settlement-oracle angle as NG.
- **(d) Leading signal:** ICE Brent front-month. Live Pyth BRENTU6 feed is valid; **historical Brent tick
  is the gap** (Pyth-historical 404s; needs Databento ICE dataset or Yahoo `BZ=F`) — the one data caveat.
- **(b) Opportunities/day:** Highest energy vol_24h (150k) → active intraday repricing, comparable
  opportunity count to WTI on the settle-window and catalyst days.
- **(c) Capacity:** vol_24h 150k, OI 85k, but the sampled ATM book was **one-sided** (13.1k yes / 0.7k no)
  — achievable size is direction-dependent; check both sides before sizing.
- **(e) Fee vs edge:** Identical near-money fee profile; work maker.
- **Next build step:** close the Brent historical-tick gap (Databento ICE or `BZ=F`), then reuse the WTI
  lag-join wiring verbatim (Brent is a drop-in second energy cell). Lower priority than NG because NG
  brings a data moat + a second edge; Brent is "more of the WTI edge."

### #5 — KXHIGHCHI + the weather breadth portfolio (CHI / DEN / PHX / HOU) · EDGE: weather-distribution
- **(a) Edge:** Weather-distribution breadth. The edge lives in the **aggregate of ~50–100 lines/week
  across cities** (S90) — no single city is the trade, so #5 is the *second weather book*, anchored on
  **KXHIGHCHI** (frontal/transition-rich, vol_24h 92k, OI 62k) and rounded out per-cell:
  - **KXHIGHCHI** — transition-rich, good volume → real room + capacity. Primary #5.
  - **KXHIGHDEN** — highest edge-density (transition-rich) but **thinnest** (vol_24h 18k) → small size only.
  - **KXHIGHTPHX / KXHIGHTHOU** — **heat-dome overshoot** cell (a *distinct* mode from the frontal whiff —
    sustained record highs stacking above the ladder); watch these when the OD forecaster lights up in a
    summer ridge, per the S84 caveat.
  - **KXHIGHLAX** — **capacity outlier / low edge:** highest weather volume on Kalshi (vol_24h 313k) but
    marine-clamped and efficient → the crowd is already sharp. Deprioritize for the distribution edge;
    only worth a line on a rare marine-layer-break day, where its depth would actually let us size.
- **(d) Leading signal:** same OD forecaster + NWS raw hourly feed as #2 — one forecaster fans out across
  all cities at zero marginal ingest cost.
- **(b) Opportunities/day:** ~6-bucket ladder × ~5–8 cities daily; the breadth IS the capacity answer to
  the thin-per-book constraint.
- **(c) Capacity (BINDING):** thin per-strike everywhere except LAX; breadth-across-cities is how we get
  size without moving any one book.
- **(e) Fee vs edge:** tail-bucket cheap (maker ~0.15–0.4¢), same as #2.
- **Next build step:** run the per-cell weather scorer across all cities in one daily pass; deploy only on
  the non-route-away cells (skip easy ≤2°F days → raw, <32°F & 50–70°F → climo, per the S90 routing);
  report the edge **distribution across lines**, never a pooled Brier. Add `KXLOWT*` as a parallel surface.

---

## Honorable mentions / future lanes (not top-5, logged per-cell)
- **KXBTCD / KXETHD (crypto daily+hourly):** by far the deepest books on Kalshi (BTC vol_24h **3.16M**,
  OI 1.78M; ETH 104k). Two things make them a *future* lane rather than top-5: (1) crypto price markets
  are hyper-efficient and 24/7 → the lag is thinner and the competition fiercer than energy; (2) they map
  natively to our **OD crypto toolkit** (`odcore/info_dipole.py` divergence/exhaustion, the gated-swing
  stack) — the right way in is the OD filter/timing split, not the raw energy-lag join. High capacity if
  we can find a per-cell lag that clears fee. Worth a dedicated probe after the energy lag is live.
- **KXNASDAQ100 (index range):** NQ-future underlying, **very deep book** (102k/106k), but index markets
  are efficient → small lag. A capacity-rich, low-edge cell; revisit only if the sub-minute tick edge
  proves out on a faster underlying.
- **KXGOLDH (gold hourly):** perfect *cadence* for the lag (hourly) and a great GC tape, but **vol_24h≈577
  = no capacity**. If Kalshi gold volume ever wakes up, it becomes a strong lag cell overnight; monitor.

## Discipline notes (carried from the skills / repo rules)
- Every cell above is a hypothesis until it clears the `kalshi-backtest` gate: **leakage gate first**,
  settle-window excluded, per-cell never pooled, distributions/fingerprints not means, net-of-fee at
  **maker AND taker**. The rankings are *fit*, not validated edge.
- LAG cells (WTI/NG/Brent) share one binding constraint (**size vs fee** → work maker, gate on move size);
  weather cells share the other (**thin depth** → small lines, breadth across cities). The two edges are
  capacity-complementary — energy gives depth, weather gives breadth.
- Settlement-source split matters for endgame execution: WTI = ICE official settle @14:30 ET; NG + Brent =
  **Pyth** 1-min candle @5PM EDT (the settlement-oracle second edge lives on the Pyth-settled pair).

Sources: live Kalshi API `api.elections.kalshi.com/trade-api/v2` (series/markets/orderbook, 2026-07-13);
[Kalshi fee schedule PDF](https://kalshi.com/docs/kalshi-fee-schedule.pdf);
[pm.wiki Kalshi fees](https://pm.wiki/learn/kalshi-fees-explained);
[how to trade oil on Kalshi](https://www.botforkalshi.com/blog/how-to-trade-oil-on-kalshi);
[Kalshi weather markets help](https://help.kalshi.com/en/articles/13823837-weather-markets);
[Kalshi daily temperature category](https://kalshi.com/category/climate/daily-temperature);
repo: `LAG_EXPLOIT_FINDINGS_S81.md`, `LEVEL_HIT_FINDINGS_S82.md`, `WEATHER_BASELINE_S82.md`,
`WEATHER_REGIME_FINDINGS_S84.md`, `NYMEX_CANARY_NOTES_S84.md`, `SESSION_HANDOFF_2026-07-13_S90.md`.
