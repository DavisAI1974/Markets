# Executor — closed-group signal trader

This is the reference implementation of the Tier 1 executor: connects to the
markets-watch backend, applies your personal risk gates, and (in paper mode)
places simulated trades on each qualifying signal.

**You run this on your own machine. Capital and keys never leave your control.**

## What it does

1. Subscribes to the backend's `/api/stream` SSE endpoint.
2. For each new signal event, runs your configured risk gates (asset
   whitelist, regime whitelist, confidence floor, daily limits, etc.).
3. If gates pass, places a paper-trade entry (long for WHALE_UP / HERD_UP,
   short for WHALE_DOWN / HERD_DOWN, fade for EQUILIBRIUM with extreme dipole).
4. Schedules an exit at one of: stop-loss, take-profit, or max-hold timeout.
5. Logs every signal seen, every gate decision, every order, and every
   close to `audit.jsonl`. Paper trades also log to `paper_trades.jsonl`.

## Important: paper-only by default

The shipped `PaperExchange` adapter does NOT place real orders. It fetches
the current price from the markets-watch API and simulates fills against it
with a configurable fee assumption (default 25 bps).

We also ship adapter scaffolds for **Coinbase Advanced Trade**, **Binance
Spot**, and **Kraken** (`executor/exchanges/{coinbase,binance,kraken}.py`).
They use signed REST against the official APIs, default to dry-run, and
read API keys from env vars on your own machine. The keys never leave
your host — the central markets-watch backend never sees them.

Switching exchanges is a config + env change:

```jsonc
// my_config.json
{
  "settings": {
    "exchange": "coinbase",         // "paper" | "coinbase" | "binance" | "kraken"
    "exchange_kwargs": {}           // optional adapter constructor overrides
  }
}
```

```bash
# Required env per exchange (set on your own machine; never commit):
export COINBASE_API_KEY=...      COINBASE_API_SECRET=...
export BINANCE_API_KEY=...       BINANCE_API_SECRET=...
export KRAKEN_API_KEY=...        KRAKEN_API_SECRET=...

# Adapters default to dry-run (no real orders); flip to live only after
# end-to-end validation:
export EXCHANGE_LIVE=1

# Binance testnet (recommended before going live):
export BINANCE_REST=https://testnet.binance.vision
```

The adapters cover MARKET and LIMIT orders + position lookup. Each has
the same `Exchange` interface (`get_quote`, `market_buy`, `market_sell`,
`limit_buy`, `limit_sell`, `get_position`) so the executor works identically
across them.

We DO ship these adapters (vs. requiring users to write their own) because:
1. Most users want one of these three exchanges and copying signed-REST
   code from scratch is error-prone — the auth schemes are subtle.
2. Default dry-run + env-only keys keeps the failure mode safe.
3. Code is short (~150 LOC each) and auditable; read `exchanges/<name>.py`
   to see exactly what the adapter does before flipping live.

## Setup

```bash
# Install deps in a Python virtualenv
pip install aiohttp requests

# Copy the example config; edit your risk parameters
cp executor/config.example.json my_config.json
# (edit my_config.json: position_size_usd, min_confidence, etc.)

# First run: dry-run mode (no orders placed, just logs decisions)
python -m executor.executor --config my_config.json --dry-run

# After verifying gates fire correctly: paper-trade mode
python -m executor.executor --config my_config.json
```

## Config reference

```json
{
  "settings": {
    "api_base": "http://localhost:8000",        // markets-watch backend URL
    "audit_path": "executor/audit.jsonl",       // every event logged here
    "paper_trade_log": "executor/paper_trades.jsonl",
    "simulated_fee_bps": 25.0
  },
  "risk": {
    "asset_whitelist": ["BTC", "ETH"],          // empty list = allow all
    "venue_whitelist": ["Coinbase", "Kraken"],
    "regime_whitelist": [
      "WHALE_UP", "WHALE_DOWN", "HERD_UP", "HERD_DOWN"
    ],
    "min_confidence": 0.6,                       // skip signals below this
    "position_size_usd": 100.0,                  // notional per trade
    "max_trades_per_day": 6,
    "max_daily_loss_usd": 50.0,                  // halt for the day if hit
    "max_position_usd": 500.0,                   // hard cap on single position
    "stop_loss_bps": 80.0,                       // exit if down 80 bps
    "take_profit_bps": 60.0,                     // exit if up 60 bps
    "max_hold_minutes": 35,                      // exit unconditionally
    "require_cross_venue_confirm": false         // require both venues to agree
  }
}
```

## Gates evaluation order

Every signal goes through these gates in order. First denial short-circuits.

1. asset whitelist
2. venue whitelist
3. regime whitelist (default excludes EQUILIBRIUM_EXTREME_DEMO so demo
   signals don't auto-trade)
4. confidence floor
5. cross-venue confirmation (if `require_cross_venue_confirm: true`)
6. daily trade count
7. daily loss limit

The audit log records the gate decision for every signal, so you can debug
"why didn't I trade this?" by reading `audit.jsonl`.

## Click-to-trade: manual orders from the PWA

The phone app's bid/ask cells emit `manual_trade_intent` events on the
SSE stream when a user taps to trade. The executor consumes those events
in addition to auto-signals:

- Side + price + qty come from the user's tap + ticket modal
- The intent BYPASSES the auto-trading risk gates (the human already
  decided), but still goes through the same exchange adapter and audit
  trail
- For "buy", the executor places a `limit_buy` at the clicked price (or
  market if the adapter doesn't support limits); same for sell
- Every intent is recorded in `audit.jsonl` with kind
  `manual_intent_received` / `manual_intent_order_placed`

If you want manual clicks to remain notification-only (no real order),
keep `--dry-run` on or use the paper exchange.

## Writing a custom-exchange adapter

If you use an exchange other than Coinbase/Binance/Kraken, implement the
`Exchange` protocol in `exchanges/base.py`:

```python
from executor.exchanges.base import Exchange, OrderResult, PriceQuote

class MyExchangeAdapter:
    name = "myexchange"
    def __init__(self, api_key, api_secret, dry_run=True):
        ...
    def get_quote(self, asset): ...
    def market_buy(self, asset, notional_usd): ...
    def market_sell(self, asset, size): ...
    def limit_buy(self, asset, price, size): ...    # optional
    def limit_sell(self, asset, price, size): ...   # optional
    def get_position(self, asset): ...
```

Register it in `executor/exchanges/__init__.py:make_exchange` so it can
be selected via `settings.exchange = "myexchange"` in your config.

**Recommended workflow before going live**:
1. Run `--dry-run` for a week. Verify gates fire as expected.
2. Run paper for two weeks. Verify entry/exit logic matches your intent.
3. Compare paper P&L to your manual judgment of whether you'd have taken
   each signal.
4. Only then connect a real exchange adapter, with the smallest position
   size your exchange allows. Increase only after multi-week stable P&L.

## Closed-group rules

- Never share your config file (it may contain your asset/venue choices).
- Never share your audit log publicly (timing reveals strategy).
- Never share signals or screenshots outside the closed Discord.
- This is research, not investment advice. Your money, your risk.
