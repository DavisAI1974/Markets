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

To trade real money, **you must write your own `Exchange` adapter** for
your specific exchange. See `exchanges/base.py` for the interface. We do not
ship live-trading adapters because:
1. Your exchange API keys must never touch our infrastructure.
2. The signal hasn't validated yet (multi-day data still accumulating).
3. Different friends use different exchanges; one-size-fits-all doesn't work.

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

## Writing a real-exchange adapter

Implement the `Exchange` protocol in `exchanges/base.py`:

```python
from executor.exchanges.base import Exchange, OrderResult, PriceQuote

class MyCoinbaseAdapter:
    name = "coinbase_advanced"

    def __init__(self, api_key, api_secret, ...):
        # set up your exchange client (e.g., coinbase-advanced-py)
        ...

    def get_quote(self, asset: str) -> PriceQuote:
        # call your exchange's ticker endpoint
        ...

    def market_buy(self, asset: str, notional_usd: float) -> OrderResult:
        # call market-order endpoint with quote_size=notional_usd
        ...

    # ...etc
```

Then in `executor.py`, swap `PaperExchange(...)` for your adapter.

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
