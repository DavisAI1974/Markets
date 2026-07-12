# SESSION HANDOFF — S78 (2026-07-12) — MARKETS PIVOT crypto→Kalshi; full pipeline built

Branch **`claude/kalshi-s78-kickoff-jb5oyx`** (based on the S77 tip `claude/book-swing-s77-kraken-meomsh`;
all S71–S77 code present). PUSHED. Read `KICKOFF_S78_KALSHI.md` + `KALSHI_BUILD_SCOPE.md` (the plan) and
`S77_REVIEW_FOR_CHATGPT.md` (why we pivoted). Standing rules: per-contract deploy; provisional-until-live;
git is source of truth; commit+push regularly; never size off one window; zero synthetic.

## The pivot (S77 → S78)
The crypto book-swing edge is REAL but a **fee-floor microstructure signal** — negative at taker, positive
only at 0% maker, and its dollar ceiling is capital + a maker-fee regime we don't control (S77 Hummingbot
live check: naive MM ≈ flat). Crypto was the **proving ground**. **Kalshi prediction markets fit the stack
better**: direct causal news→outcome coupling on event contracts, CFTC-regulated all-50-states real API,
wide-spread less-HFT books (a maker edge survives), and Greg's energy/macro/weather domain edge is genuinely
informative here (it never was on BTC). Same infrastructure, better-fit venue. **The S25–S37 crypto work is
NOT discarded** — it's the validated track record that sells the capability.

## What was built (KALSHI_BUILD_SCOPE 4 steps + infra; all pushed)

### Step 1 — `research/kalshi/kalshi_collector.py`
Public v2-API (`https://api.elections.kalshi.com/trade-api/v2`, no auth) snapshot collector. Appends one JSONL
line per (market, snapshot) to `data/kalshi/<SERIES>_bins.jsonl` (one file per SERIES so the whole strike
ladder's history lives together — what the weather-vs-implied-distribution test needs).
- **28-series watchlist**, grouped by thesis: 12 weather daily-high cities (KXHIGHNY/LAX/CHI/AUS/DEN/…) + 7
  macro prints (KXUSNFP/KXCPIYOY/KXCPICOREA/PCECORE/KXFEDHIKE/RATECUTS/KXEFFR) + 4 energy (KXWTI/KXBRENTD/
  KXNATGASD/KXAAAGASD) + 5 electricity (KXPOWERKWH live; KXUTILITYERCOT/PJMWEST/NYC/SOCAL auto-capture when
  their periodic markets open).
- **Book transform**: Kalshi binary YES/NO → unified YES book (NO bid @q = YES ask @100−q), best-first, cents.
  **Feeds `research/shape_s71/early_signal.book_imbalance()` UNCHANGED** (verified: imb/ok=True).
- **Price source = `/orderbook`** (the `/markets` ladder item's top-of-book + `liquidity_dollars` are NULL for
  weather/econ — a trap; only orderbook has live prices). Front-ladder selection by soonest close_time.
- `--discover` cheap gate confirmed **clean 2-sided implied distributions** live (NYC high: 82-83°@41%,
  84-85°@35%…; Denver 93-94°@83¢; WTI/Brent deep 10/10 ladders; natgas wide 2-sided).

### Step 2+3 — news pipeline merged + repointed (`news_ingest_rss.py`)
Merged the domain-agnostic ingest/coupling/policy machinery from `origin/claude/run-pass-14-classifier-nTViL`
(news_ingest_rss, news_coupling_research, build_news_policy_from_coupling, build_daily_news_context,
NEWS_EVENTS_SCHEMA, example jsonl). **Repointed** (surgical constants edit, machinery unchanged):
- Feeds → EIA Today-in-Energy + Press, Fed Press (all + monetary), NOAA NHC Atlantic — **all verified live
  (200)**. BLS CPI/employment included but **403s from datacenter IPs** (works box-side).
- `BTC_TERMS/ETH_TERMS` → **`CONTRACT_KEYWORDS`** map (each series a regex; `assets` now holds series tickers).
- Categories crypto→macro (ENERGY/INFLATION/JOBS/MONETARY/HURRICANE/WEATHER); bull/bear term sets swapped.
- **Verified live**: two EIA crude items tag `[KXWTI, KXBRENTD]`; a Fed release tags `KXFEDHIKE`; the NHC
  outlook tags `KXTROPSTORM` = the direct EIA-release→contract causal coupling the whole thesis rests on.
- Weather daily-high city contracts are served by the OD thread, not RSS (noted in code).

### Step 4 — coupling adapter (`research/kalshi/kalshi_coupling_adapter.py`)
Feeds Kalshi mid-probability into `news_coupling_research.py` UNCHANGED via `--source kalshi`. Maps
asset=SERIES, venue=MARKET(strike), close=mid(cents); `KBar` exposes .ts/.close/.buy_vol/.sell_vol/.n_trades.
Snapshots carry the BOOK not trades → buy/sell/n_trades=0 (flow/volume-confirmation cols N/A; the
**signed-bps-vs-placebo decision gate is fully intact** off mid). Verified: a synthetic INFLATION event tagged
to `KXCPIYOY` produced 8 observations across its strike markets. `DEFAULT_MACRO_SERIES` = macro + energy +
electricity (weather excluded — OD thread). Placebo baseline needs >10 snaps/market (real accrued data clears).

### Option A — settlement + scoring harness (`research/kalshi/kalshi_score.py`)
**The "does a forecast beat the market" engine, and the scoreboard the ⭐ weather-via-OD forecaster plugs into.**
- Fetches REALIZED settlement (ground truth) per settled market: `result`=yes/no, `floor/cap_strike`, and
  **`expiration_value`** (the exact realized number), grouped to events.
- Builds the market-implied distribution over the strike ladder; **auto-detects PARTITION ladders** (weather:
  mids ARE P(bucket)) vs **CUMULATIVE ladders** (energy: all "Above $X" → difference adjacent thresholds).
- **Proper market baseline = implied dist from accrued bins at `--lead-minutes` before close** (`--bins-dir`).
  Settled `last_price` is **post-hoc near-certain** (the market knows the answer by close) → flagged; the real
  baseline activates as bins accrue. This is load-bearing: a perfect forecast can't beat an already-certain
  post-hoc market — edge shows only against the market's UNCERTAIN forecast hours before close.
- Scores ANY forecast (explicit bucket dist, OR point `value+sigma` via Gaussian-over-buckets) vs realized AND
  vs market: Brier, log-loss, `brier_edge_vs_market`. Forecast keying tolerant of the ~1-day UTC close offset.
- **Verified on real NYC settled data**: realized values correct (JUL03=98, JUL10=85); perfect point forecast
  fc_p=0.95, wrong forecast edge=−1.997. Forecast-agnostic — OD / climatology / persistence all plug in.

### Infra — `.github/workflows/kalshi_collectors_durable.yml`
Durable GHA cron (6h, ~5h50m/run) mirroring the coin collectors. Adaptation: kalshi bins are **append-JSONL**
(vs coins' grow-a-dict), so cycle = restore prior `<SERIES>_bins.jsonl.gz` from `data/kalshi-bins` → append →
gzip+push (orphan force-push, line-count guardrail, ~6% gz ratio). Stdlib-only, no pip. **First run
auto-triggered on push (run id 29173014938).**

## The two threads (both live)
1. **News→contract COUPLING** (macro/energy) — the KALSHI_BUILD_SCOPE thesis. Complete + proven end-to-end;
   awaiting days of accrued bins spanning real EIA/CPI/NFP/FOMC releases before the coupling result is
   meaningful. Then: `python news_coupling_research.py --source kalshi --data-dir data/kalshi --events
   news_events.jsonl` → does a tagged release move its contract's probability beyond placebo?
2. **⭐ WEATHER via real OD** (Greg's own spec — he is running it separately, not this session). Turn the real
   OD engine (LIGO chirp / GPS time-dilation / QCD from raw data) on raw NOAA/NWS/GHCN/GFS to forecast the
   exact settlement variable a Kalshi weather contract keys on → **edge on the OUTCOME, not microstructure, so
   it does NOT get arbed away.** `kalshi_score.py` is its scoreboard. **CONVERGENCE: electricity prices are
   weather-driven → the OD-weather forecaster is also an electricity-price forecaster.**
   HONEST SCOPE (Result Discipline): OD's proven wins RECOVERED KNOWN laws (validation, not new physics).
   vs operational NWP (ECMWF/GFS on supercomputers) the defensible FIRST claim is **OD as a local operator /
   bias-correction on the exact station settlement variable**, tested to beat climatology + persistence + MOS —
   NOT "out-forecast ECMWF from raw obs alone." Escalate only if the modest claim clears.

## Standing Kalshi rules (new; carry forward)
- Per-CONTRACT deploy (the per-cell rule, applied to contracts). Report "works on {X}", never "failed".
- Provisional-until-live: backtests only remove optimism; only the demo/paper loop on real books confirms fills.
- **Capital is locked until resolution → model ANNUALIZED return on locked capital, NOT $/hr** (the crypto
  $/hr frame does NOT transfer). Binary settlement at 0/100¢; edge = holding a mispriced probability to
  resolution, not scalping spread.
- Maker fees ≈ 25% of taker (some promo/zero-maker windows). News-jump gap risk → wire `PAUSE_NEW_ENTRIES` to
  the release calendar. Breadth (many contracts) not depth is Kalshi's capacity answer.

## State / what's running
- **Durable Kalshi collector**: run #1 live on GitHub compute → will create `data/kalshi-bins` (~6h). Picks up
  the full 28-series watchlist on its next cron.
- **Ephemeral session collector**: was accruing to `data/kalshi/` this session (dies with the container;
  superseded by the durable run).

## NEXT (priority)
1. **Let `data/kalshi-bins` accrue** days across real EIA/CPI/NFP/FOMC releases, then run the coupling test
   (`--source kalshi`) + `kalshi_score.py` with `--lead-minutes` baselines. THIS is the thesis test.
2. **Greg: sync `kalshi_collectors_durable.yml` onto the DEFAULT branch** for recurring cron (GHA cron fires
   only from default; my token can't trigger runs — push-trigger fired run #1). Optional fast smoke-test:
   Actions → Run workflow with `duration_seconds=300` → creates `data/kalshi-bins` in ~5 min.
3. **Plug the OD-weather forecaster into `kalshi_score.py`** when Greg's spec finishes running (distribution or
   value+sigma per event → edge vs the lead-time market baseline vs realized).
4. **Kalshi microstructure thread** — `early_signal` book-imbalance→turn on the probability series (wide
   spreads = the maker edge crypto lost to the fee floor). Runs on the accruing energy/weather ladders.
5. **Paper loop** on `demo-api.elections.kalshi.com` (RSA-key auth) to watch real fills (S77 plan step 4).

## Files added this session
`research/kalshi/kalshi_collector.py`, `research/kalshi/kalshi_coupling_adapter.py`,
`research/kalshi/kalshi_score.py`, `.github/workflows/kalshi_collectors_durable.yml`; merged
`news_ingest_rss.py` (repointed) + news pipeline; edited `news_coupling_research.py` (`--source kalshi`);
`.gitignore` (kalshi bins + news outputs). Commits `a0b2862`..`c98fe1b` on `claude/kalshi-s78-kickoff-jb5oyx`.
