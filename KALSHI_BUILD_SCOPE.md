# KALSHI BUILD SCOPE — concrete (S77 → S78 kickoff)

> Branch: `claude/book-swing-s77-kraken-meomsh`. Written 2026-07-11.
> The premise (established this session): the crypto book-swing edge is a **fee-floor microstructure signal**
> whose dollar ceiling is capital + a maker-fee regime we don't control. Kalshi is a better *fit* for the stack
> we already built because (a) **news→outcome coupling is direct and causal** on event contracts (vs weak/noisy
> on BTC), (b) it's **CFTC-regulated, all 50 US states, real REST+WS API**, (c) the book is **wide-spread and
> far less HFT-competed**, so a maker edge isn't instantly arbed, and (d) Greg's **energy/macro/weather domain
> knowledge is a genuine information edge** on the specific contracts, which it never was on BTC.
> Four pieces already exist and port over: (1) the news pipeline, (2) the order-book/microstructure signal
> (`early_signal.py`), (3) the OD regime/flow layer (`odcore/`), (4) Greg's domain edge. This scopes wiring
> them onto Kalshi.

---

## WHAT ALREADY EXISTS (reuse, do not rebuild)

**News pipeline** — on `origin/claude/run-pass-14-classifier-nTViL` (cherry-pick / merge onto the Kalshi branch):
- `news_ingest_rss.py` — RSS → `news_events.jsonl`. Classifies `directional_bias`, `impact`, `confidence`,
  `category`, `nlp_features.magnitude_bps_hint`, `source_quality`. **Currently pointed at CoinDesk/Cointelegraph/
  Eth-Foundation with BTC/ETH term regexes.** This is the file we repoint.
- `news_coupling_research.py` — the validation engine: aligns each event to a venue price series and measures
  **signed bps edge vs a placebo (random-time) baseline**, **hit-rate**, per-horizon, per-category. This is the
  exact machinery that answers "does this news actually move the outcome" — reused verbatim, just swap the price
  series for a Kalshi contract's mid-probability series.
- `build_news_policy_from_coupling.py` — turns coupling stats into a **policy**: risk multiplier, shock actions
  (`PAUSE_NEW_ENTRIES`), `requires_confirmation` gates, `shock_valid_minutes`, thresholds
  (`min_signed_bps_edge_vs_placebo=3.0`, `min_hit_rate=55`). Directly reusable.
- `build_daily_news_context.py` / `NEWS_EVENTS_SCHEMA.md` — the schema + daily rollup. Schema is domain-agnostic.

**Microstructure signal** — `research/shape_s71/early_signal.py`: `book_imbalance()`, `fit_direction_sign()`,
the ride-to-reversal `swing()`. Kalshi order books are L2 (yes/no bids+asks in cents) — the same imbalance→turn
math applies to the **probability** series instead of price.

**OD layer** — `odcore/` (coupling, lead-lag, decoupling, regime classifier). Use for cross-contract coupling
(e.g. the "Fed hikes" contract vs the "recession-by-EOY" contract lead-lag) and regime gating.

---

## THE FOUR-STEP BUILD

### STEP 1 — Kalshi API data collection (`research/kalshi/kalshi_collector.py`)
Concrete deliverable: a collector that snapshots the order book + trades for a **watchlist of contracts** into
the same JSONL bin format the crypto collectors use, so every downstream tool reads it unchanged.
- **API:** `https://api.elections.kalshi.com/trade-api/v2` (public market data needs **no auth**; placing orders
  later needs an RSA-key-signed session). Endpoints: `GET /markets` (list + filter by `series_ticker`/`status`),
  `GET /markets/{ticker}/orderbook` (yes/no depth), `GET /markets/{ticker}` (last, volume, close_ts),
  `GET /series` / `GET /events`. WebSocket `wss://.../trade-api/ws/v2` channels `orderbook_delta`, `ticker`,
  `trade` for live depth.
- **Watchlist (where Greg has edge — start narrow, ~8–15 contracts):** EIA weekly petroleum / natural-gas
  storage, monthly CPI/PCE prints, FOMC rate decisions, NFP/jobless claims, NWS temperature/hurricane
  contracts. These are the ones with a **scheduled data release** = a clean news→outcome causal event.
- **Bin schema (match the crypto collectors):** `{ts, ticker, mid, spread, yes_bid, yes_ask, bids:[[offset,size]],
  asks:[[offset,size]], last, volume}` where `mid` = mid-probability in cents (0–100). Poll book every ~1–5s
  (Kalshi books move far slower than crypto — 1s is overkill, but keep it configurable). Write to
  `data/kalshi/<ticker>_bins.jsonl`, gzip on push (S37 lesson: >100MB files break git).
- **Gate:** run it live for a few hours, confirm we get real depth + trades on the watchlist. Cheapest possible
  first check before anything else (the Hummingbot lesson — stand it up, watch it, then decide).

### STEP 2 — Repoint the news pipeline (`news_ingest_rss.py` DEFAULT_FEEDS + term regexes)
Concrete edit: swap crypto feeds/regexes for macro/energy/weather sources and per-contract keyword maps.
- **Feeds:** EIA "Today in Energy" + weekly-release RSS, BLS CPI/employment release schedule, Federal Reserve
  press releases, NWS/NHC alerts, Reuters/AP economy + energy wires. (`source_quality`: EIA/BLS/Fed =
  `PRIMARY`; Reuters/AP = `TRUSTED_MEDIA`.)
- **Classifier:** replace `BTC_TERMS`/`ETH_TERMS` with a **contract-keyword map** — each watchlist contract gets
  a regex ("crude inventory", "CPI", "rate cut", "hurricane") so an event tags the specific Kalshi ticker(s) it
  bears on. `directional_bias` stays (bullish/bearish → yes/no lean); `magnitude_bps_hint` becomes a
  **probability-move hint in cents**. The `nlp_features` + schema are unchanged.
- This is a **surgical edit of one file's constants**, not a rewrite — the ingest/classify/emit machinery is
  domain-agnostic by design.

### STEP 3 — Validate coupling + microstructure (reuse `news_coupling_research.py` + `early_signal.py`)
Two independent validations, same tools as crypto, run on the collected Kalshi bins:
- **News→contract coupling:** point `news_coupling_research.py`'s `VENUES` map at
  `data/kalshi/<ticker>_bins.jsonl` (mid-probability series). Measure signed-cents edge vs placebo + hit-rate
  per horizon per category. **Decision gate:** does a tagged EIA/CPI/FOMC event move its contract's probability
  beyond the placebo baseline (the `min_signed_bps_edge_vs_placebo` / `min_hit_rate` thresholds)? On event
  contracts this should be *far* cleaner than BTC — that's the whole thesis, and this is the test of it.
- **Book-imbalance→turn:** run `early_signal.fit_direction_sign()` + the ride-to-reversal on the probability
  series (train/test split like `realistic_fill.py`). Does the Kalshi book lean into a probability turn the way
  the crypto book leans into a price turn? Report per-contract $/settlement and hit-rate.
- Both feed a `build_news_policy_from_coupling.py` run → a **Kalshi policy.json** (which contracts to trade,
  which news categories are tradeable shocks, confirmation gates).

### STEP 4 — Paper/live decision
- If coupling clears the gate: stand up a **paper loop** (Kalshi has a **demo environment** —
  `demo-api.elections.kalshi.com` — with a funded paper account and the same API) exactly like the Hummingbot
  sanity check, and watch fills on real contracts.
- Structure the economics: Kalshi **maker fees ≈ 25% of taker** (and many contracts have promo/zero maker
  windows), settlement is binary at 0 or 100¢, so the edge is **holding a mispriced probability to resolution**,
  not scalping spread — a fundamentally different (and capital-friendlier) P&L than crypto MM.

---

## ADVANTAGES vs CRYPTO (why this fits)
- **Direct causal coupling:** an EIA storage number *is* the input to the "nat-gas price above X" contract. The
  news→outcome link we struggled to find on BTC is structural here.
- **Wide spreads, less HFT:** a maker edge survives longer; we're not racing colocated bots.
- **Domain edge is real:** Greg's energy-trading background prices EIA/weather contracts better than the crowd.
- **Regulated + all-50-states + real API:** no venue-access or fee-tier games; no $250M-AMV Coinbase dance.

## CAUTIONS (put in the plan up front)
- **Thin liquidity / capacity:** many contracts are $-thousands deep — same capital ceiling shape as thin crypto
  books, but here the answer is *breadth* (many contracts) not *depth*.
- **News-jump / gap risk:** a scheduled print gaps the probability discontinuously — resting makers get run over.
  The policy's `PAUSE_NEW_ENTRIES` shock logic exists precisely for this; wire it to the release calendar.
- **Settlement timing / holding cost:** capital is locked until resolution (hours→months). Model annualized
  return, not $/hr — the crypto $/hr frame does not transfer.
- **Provisional-until-live:** same rule as crypto — backtests only remove optimism; only the demo/paper loop on
  real books confirms fills.

---

## FIRST CONCRETE ACTIONS FOR THE NEW SESSION (in order)
1. `mkdir research/kalshi`; write `kalshi_collector.py` against the public v2 API; pick the ~8–15 contract
   watchlist (energy/macro/weather); run it live a few hours → confirm real depth. **(Step 1, the cheap gate.)**
2. Merge the news pipeline files from `origin/claude/run-pass-14-classifier-nTViL` onto this branch.
3. Repoint `news_ingest_rss.py` feeds + classifier to macro/energy + per-contract keyword map. **(Step 2.)**
4. Once a few days of bins + events accrue: run `news_coupling_research.py` and `early_signal` validation.
   **(Step 3 — the thesis test.)**
