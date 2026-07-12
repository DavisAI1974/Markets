# NYMEX is the canary — load-bearing principle + data-source reality (S84, Greg)

## Settlement-mechanics correction (S84 — verified off Kalshi rules_primary)

What the energy/electricity Kalshi markets ACTUALLY settle on — corrects earlier framing:
- **`KXNATGASD` is a DAILY NG PRICE market, not an EIA-storage event.** rules_primary: "the close price
  of the 1-minute candlestick for natural gas using the **NGDQ6 contract** at 5:00 PM EDT." So it settles
  on the **Henry Hub NG futures** price (the front NG contract), every day. The NYMEX-canary/lag model
  applies EVERY DAY (Kalshi follows NGDQ6); the Thursday EIA storage report is the biggest intraday
  CATALYST, not the settlement basis. Underlying data = NG futures (Databento `NG.c.0`; Pyth lacks NG).
- **`KXPOWERKWH` is a MONTHLY MACRO-STAT market, not a futures.** rules_primary: "the average price of
  electricity per kilowatt-hour in the U.S. city average for [month]" = the **BLS/EIA monthly retail
  electricity average** (~21c/kWh), a CPI-style print. There is NO traded electricity futures behind it,
  NO per-second tape, NO NYMEX canary — it resolves on a monthly data release. It belongs to the
  release/consensus thread (like CPI/NFP), NOT the energy-lag/Databento thread. A per-second "electric"
  backfill does not exist to buy. (A power-futures market on an ISO hub — PJM/ERCOT — would be different
  and IS on Databento, but Kalshi's KXPOWERKWH is not that.)

## Resolution + how we MEASURE moves (Greg, S84)

- **Pull TICK data (`trades` schema = every print), never daily settle / OHLC.** Kalshi trades
  continuously intraday, so the lag strategy needs the tick tape. Daily settle enters ONLY as the
  settlement REFERENCE (KXNATGASD resolves on the NGDQ6 1-min candle close at 5PM EDT) — one value read
  off the tape, not a reason to pull daily data.
- **Measure moves in TICKS and DOLLARS, not just bps** (trader-native; ties directly to P&L). A move of
  N ticks = N x tick_value $/contract. Blip vs run is defined in ticks: a blip = a few ticks that
  revert; a run = many ticks sustained.
- **Tick size + value come from Databento's `definition` schema** (`min_price_increment` x
  `unit_of_measure_qty`), pulled POINT-IN-TIME per contract (the exchange can change tick size — do NOT
  hardcode). `databento_backfill.py --schema definition` pulls it; `event_move_baseline.py` will read it
  to express every move in ticks/$/bps. Reference to VERIFY against the definition (not to hardcode):
  CL crude ~ $0.01/bbl tick, $10/tick (1,000 bbl); NG ~ $0.001/MMBtu tick, $10/tick (10,000 MMBtu).

## The principle (Greg, S84 — load-bearing)

**NYMEX/ICE is the LEADER; Kalshi is the delayed FOLLOWER. We map/gather NYMEX data as our CANARY —
the leading signal — and trade the lagged Kalshi echo.** Kalshi's energy binaries are re-quoted off the
underlying futures by a handful of market-makers; the move happens on NYMEX first and reprices onto
Kalshi seconds-to-a-minute later (the S80-S81 lead-lag thread: futures lead, Kalshi NEVER leads). It is
an odd setup — we trade Kalshi numbers, not NYMEX — but it is pure follow-the-leader, just delayed. So:
- The **signal** (what's about to happen) lives in the NYMEX tape.
- The **trade** (what we actually fill) lives on Kalshi, after the lag.
- Gather NYMEX continuously as the canary; measure the lag; fire on Kalshi.

## Resolution reality (Greg, S84 — do not pretend otherwise)

- **1-minute is USELESS.** NYMEX moves fast; a 1-min bar smears the whole release move into one candle
  and hides the blip-vs-run character and the lag entirely.
- **1-second is the practical floor we can get historically, and it STILL UNDERSAMPLES.** NYMEX prints
  faster than 1/sec around a release; 1-sec historic sampling (the Pyth timestamp endpoint) WILL miss
  ticks/trades. We accept this KNOWINGLY: we are not trading on NYMEX, so missing sub-second NYMEX
  ticks does not cost us a fill — but every readout built on 1-sec NYMEX data must be reported as a
  LOWER BOUND on move speed/count, never as the complete tape. Do not claim 1-sec captures everything.
- Going forward, the live Pyth SSE stream is finer than 1-sec (real push ticks); the 1-sec floor is a
  limitation of HISTORICAL backfill, not the live feed.

## Data-source inventory (what NYMEX data we can actually get — S84 probe)

| underlying | Kalshi series | Pyth feed | Pyth historical (per-sec) | source we use |
|-----------|---------------|-----------|---------------------------|---------------|
| **WTI crude** | KXWTI | full monthly curve (WTIF6..WTIZ6) | **WORKS** (timestamp endpoint, back to at least early July) | **Pyth 1-sec backfill** |
| **Brent** | (ICE) | full monthly curve, `BRENTU6` valid | **404s** (Hermes historical-retention gap) | TODO: Pyth Benchmarks API, else Yahoo `BZ=F` |
| **Natural gas** | KXNATGASD | **NONE — Pyth has no Henry Hub feed at all** | n/a | **Yahoo `NG=F`** (coarser: 1m/7d, 5-15m/60d) |

Consequential findings from the S84 probe:
- **Pyth carries NO natural gas.** Catalog queries for "natural gas"/"gas"/"henry" return 0 feeds. The
  collector's `NGDQ6` feed id (`3ea3adf4...`) is **BOGUS — it resolves to nothing**, so the live NG
  stream was never real (part of why the tape was empty). **Thursday's planned "NGDQ6 lag on live Pyth
  ticks" cannot run on Pyth** — NG must come from Yahoo `NG=F` or a paid tick source. FIX NEEDED: drop
  or replace the bogus NG id in `pyth_collector.py` FEEDS.
- **Brent** feed ids are valid/current but the Hermes historical timestamp endpoint 404s for them —
  live-only until we find the historical route (Benchmarks API).
- **Rate limit:** the public Hermes endpoint returns **429 after ~8 rapid calls** — any per-second
  backfill must throttle (~2-3 req/sec) with exponential backoff on 429; a naive walk gets blocked.

## Implication for the plan
- The per-second NYMEX canary + move-duration baseline is buildable NOW **on WTI** (Pyth historical).
- NG (Thursday) is data-constrained to Yahoo ~1m historically — below the useful-resolution bar; a real
  NG tick source is a standing need. Live NG going forward also needs a non-Pyth feed.

## RESOLUTION: Databento (Greg, S84) — the primary historical source that fixes both gaps

`databento.com/historical` (CME Globex dataset `GLBX.MDP3`) carries **CL crude AND NG Henry Hub natural
gas** at the **`trades` schema = every individual print, nanosecond timestamps** (MBO gives the full
book). This fixes BOTH S84 gaps at once:
- **Natural gas coverage** — the feed Pyth does not have. Thursday's NG lag becomes real.
- **True tick, not 1-sec** — no more undersampling / lower-bound caveat; this is the actual tape.
- Deep CME history + **continuous front-month symbology** (`CL.c.0`/`NG.c.0`) auto-handles the roll.

Cost: usage-based **$/GB, $125 free signup credit**; a release-window `trades` pull is **<$0.01**, and
**batch jobs** make large multi-year pulls cheap (re-downloadable free within 30d). Every pull is gated
on `metadata.get_cost` first (see `databento_backfill.py --max-cost`).

**New source hierarchy:** Databento = PRIMARY historical (true tick, incl. NG). Pyth = free LIVE feed
(WTI) going forward. `pyth_backfill.py` = free WTI-only historical fallback (1-sec, undersamples).
Brent = ICE (separate Databento dataset) or Yahoo. **Needs the `DATABENTO_API_KEY` secret to run.**
