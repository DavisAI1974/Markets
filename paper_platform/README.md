# Purchased MBO paper platform

The registered market is NYMEX Henry Hub natural gas futures. Its input is the already-purchased daily DBN archive in `DavisAI1974/markets-data`. There is no feed purchase or broker connection. The 30 versioned rules are in `rules/`. CL decisions use the exchange event boundary specified by the rule. CX print-pair decisions use the next print in tape order. A management action names its originating trade and rule. Each manager has its own record of what it would do at that entry.

## Market configuration and display

`markets/nymex-ng.json` selects the archive, instrument, adapter, price units and rules. The HTML template in `monitor.html` is shared. Another market needs its instrument definition and applicable feed, book, calendar and strategy logic. Options also need expiry, strike, call or put, underlying and multiplier. Add the profile when those inputs have been verified.

The Render service serves the HTML and read API. Server-sent events update an open page. The browser reads the initial view and rule definitions with JavaScript disabled. The API exposes `/api/markets`, `/api/rules`, `/api/session` and `/api/events`. Events support market, run, rule and sequence filters. Use `follow=true` for the live NDJSON stream. Nanosecond values outside JavaScript's safe integer range use decimal strings. A local controller can use `api.application(session)` to step a separately authorized session with its expected cursor.

## Replay and evidence

ROOT's archive reader checks file hashes and record counts. A fresh session rebuilds the book from Sunday, checks each later opening restatement and retains the raw record's file hash and zero-based index. The original compressed bytes stay in the purchased input archive. The receive-time sidecar holds one little-endian unsigned 64-bit replay-host nanosecond timestamp per delivered record in that same order. Signals use historical receive time. The replay host's clock controls pacing and run duration.

Only a named trade day's records reach the strategy adapter. The existing research ROOT gate remains intact. Each trade record retains both quotes when available. The ledger records unpriced paper orders. Greg's fill policy is open. Each forced closing order carries its stop reason and `trade_data=false`. There is no research P&L.

## Operation

The supplied Actions workflow accepts Greg's manual approval, market, named trade day, message budget and event budget. An atomic signal/order batch that would exceed the event budget ends the run before that batch is published. Administrative close and receipt records are always written. The clock limit is 5.75 hours. Each run writes a new directory on its own `paper-runs/<run>` branch in markets-data. Git publishes on paper orders, each minute and at shutdown. The Actions data repository is public at the time of this build. A password on the viewer only protects the viewer.

The proposed host is Render using `paper_platform/render.yaml`. The proposed phone service is Pushover. Both require setup before an operational run. The runner expects `PAPER_RELAY_URL`, `PAPER_RELAY_TOKEN`, `PUSHOVER_APP_TOKEN`, `PUSHOVER_USER_KEY` and a `MARKETS_DATA_TOKEN` scoped to writing the data repository. The viewer also needs `PAPER_VIEW_PASSWORD`. Set values in the service secret stores. Render's SQLite cache is ephemeral. The events in markets-data are the permanent record. Hard termination of the runner can prevent application finalizers and phone delivery.

## Local verification

Set `MARKETS_DATA` to a checkout containing `data/nymex_mbo/ng_v0_oct2023/MANIFEST.json` and its purchased files. Run `python -B -m pytest -p no:cacheprovider paper_platform`. The tests check field preservation, the Sunday-to-Monday boundary, the signed-trade flow calculations, the physically truncated tape prefix and the HTML/event API using a real decision. These tests do not authorize a platform run.
