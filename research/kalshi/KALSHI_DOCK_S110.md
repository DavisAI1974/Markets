# KALSHI DOCK — endpoint + auth reference (S110; sources: docs.kalshi.com pages Greg supplied + live probes)

**THE ROUTING DECISION (probed live, S110):** the MARGIN platform's demo carries 33 PERPETUALS —
crypto, FX, metals, WTI (`KXWTIPERP1`) — and **NO NATURAL GAS**. The CLASSIC demo carries
**KXNATGASD live** (probed: Monday 26AUG0317 brackets present). Therefore:

- **PAPER TRADING NG RUNS ON THE CLASSIC DEMO.** Margin docs are FILED for the live/latency stage.
- **WATCH-LINE (not a build):** if Kalshi ever lists `KXNATGASPERP`, a direct-delta NG vehicle
  changes the product question — surfaced to Greg the day it appears (QC sweep can grep the
  margin catalog). WTI perp exists today but WTI is parked under gas-only (D13).

## CLASSIC (the paper lane — NG lives here)

| lane | demo | production |
|---|---|---|
| REST | `https://external-api.demo.kalshi.co/trade-api/v2` | `https://api.elections.kalshi.com/trade-api/v2` |
| WebSocket | `wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2` | (prod ws host per docs) |

- Public market data needs NO auth (proven live from the session container both on prod and demo).
- Demo = mock funds; demo books/prices "may not be reflective" (docs) — see PAPER DESIGN below.
- Credentials do NOT transfer between demo and prod.

## MARGIN (the future lane — perps; filed, not wired)

| lane | demo | production |
|---|---|---|
| REST | `https://external-api.demo.kalshi.co/trade-api/v2/margin/` | `https://external-api.kalshi.com/trade-api/v2/margin/` (rolling rollout) |
| WS | `wss://external-api-margin-ws.demo.kalshi.co/trade-api/ws/v2/margin` | per docs at rollout |
| FIX order entry / drop copy | `margin-fix.demo.kalshi.co` | `margin-mm.fix.elections.kalshi.com` |
| FIX market data | `margin-marketdata.fix.demo.kalshi.co` | `margin-marketdata.fix.elections.kalshi.com` |

FIX sessions (FIXT.1.1 / FIX50SP2, TLS 1.2+, ONE connection per API key):
port 8228 `KalshiNR` (order entry, no retrans) · 8229 `KalshiDC` (drop copy, request-response,
3h window, resend by ExecID) · 8230 `KalshiRT` (order entry with retransmission) · 8233 `KalshiMD`
(market data; snapshot 35=W + incremental 35=X; no retransmission, ResetSeqNumFlag=Y).
Margin REST prices are DECIMAL DOLLARS (4dp), not classic integer cents. Listener sessions
(`ListenerSession=Y` + tag 21011, orders rejected) = live read-only exec-report shadow feed.
ORDER GROUPS (35=UOG, tags 20130-20132) = exchange-native contracts-limit + trigger kill switch —
the live-stage complement to the paper ledger's local caps. Reject taxonomy: session 35=3 /
business 35=j / order 35=8 ExecType=Rejected (codes captured in the docs; 103=3 risk breach,
373=10 clock skew >30s — NTP the box).

**FIX is raw TCP+TLS -> BOX LANE ONLY** (same S100 structural constraint as GLBX). REST/WS run
from anywhere HTTPS runs, container included.

## AUTH (one scheme, both platforms; classic REST included)

- ONE RSA key pair serves REST and FIX ("FIX API keys use the same RSA key pair as the REST API").
- Provisioning (Greg, G0): generate locally, register the PUBLIC key at kalshi.com/account/profile,
  receive the API KEY ID (UUID). Demo and prod are separate registrations.
  `openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out kalshi-demo.key`
  `openssl rsa -in kalshi-demo.key -pubout -out kalshi-demo.pub`
- REST: RSA-PSS SHA256 signature headers per the classic quick-start (timestamp + method + path).
- FIX logon (35=A): sign SOH-joined `SendingTime|MsgType|MsgSeqNum|SenderCompID|TargetCompID`
  with RSA-PSS SHA256, base64 into tag 96; 98=0; 1137=9 (FIX50SP2); SenderCompID = the key UUID;
  SendingTime within +-30s of server time.
- STORAGE (standing key discipline): `scratchpad/kalshi.env` -> `KALSHI_DEMO_KEY_ID=<uuid>` +
  `KALSHI_DEMO_KEY_PEM=<path to .key beside it>`. Never in chat, never in git. KEYS.md carries
  names only.

## MARGIN-LANE OPERATIONAL FACTS (filed for the live stage)

- **REST auth headers (BOTH platforms, classic included):** `KALSHI-ACCESS-KEY` (key UUID) +
  `KALSHI-ACCESS-SIGNATURE` (RSA-PSS SHA256 over timestamp+method+path) + `KALSHI-ACCESS-TIMESTAMP`.
- **Price banding (perps):** tick 0.0001 USD; bids >= lower of (80% of best bid, best bid - 1000
  ticks); asks <= higher of (120% of best ask, best ask + 1000 ticks); amends outside the band
  rejected; resting orders survive band shifts; empty side = no band.
- **API limits:** token buckets per read/write with usage tiers (premier/paragon/prime), queryable
  at `margin-rest/account/get-perps-account-api-limits`; grants split by exchange_instance
  (event_contract vs margined) — the classic lane has its own tiering.
- **FCM subtrader endpoints:** FCM members only — NOT part of a retail demo signup; ignore for G0.
- **Risk model (perps):** account-wide NOTIONAL risk limit (fixed-point dollars, e.g. 5000.0000
  default-class) with per-market overrides (`get-notional-risk-limit`); global
  liquidation-margin-ratio + queue-entry-margin-ratio thresholds and a per-market
  initial-margin multiplier over maintenance (`get-risk-parameters`). The live stage sizes UNDER
  the notional limit and treats the queue-entry ratio as its own hard floor — our ledger caps
  stay the inner ring, the exchange's limits the outer.

## MARGIN-LANE ORDER + RISK CONTRACTS (captured from Greg's walk; wire at live stage)

- **create-order (REST):** required ticker / client_order_id / side(bid|ask) / count / price /
  time_in_force(fok|gtc|ioc) / self_trade_prevention(taker_at_cross|maker); optional
  expiration_time(ms), post_only, cancel_order_on_pause, reduce_only, subaccount(0-63),
  order_group_id. Counts are FIXED-POINT CONTRACTS at 0.01 granularity (fractional!); prices
  fixed-point USD up to 6dp. Response echoes fills: fill_count, remaining, avg_fill_price,
  avg_fee_paid.
- **get-orders:** filters ticker/min_ts/max_ts/status/subaccount, cursor pagination (limit
  <=10000); last_update_reason vocabulary incl. MarginCancel / SelfTradeCancel /
  PostOnlyCrossCancel; order_reason incl. liquidation and take_profit_stop_loss.
- **get-risk:** account leverage (= notional / maintenance), total_position_notional,
  total_maintenance_margin; per position: signed qty, mark, notional, maintenance required,
  leverage, ESTIMATED PORTFOLIO-AWARE LIQUIDATION PRICE. Dollars to 6dp, counts to 2dp.
  (No balance / unrealized PnL here - those live on portfolio endpoints.)

## PAPER DESIGN CONSEQUENCE (G2 refinement, decided S110)

Two loops, different jobs:
1. **MECHANICS loop (demo):** order lifecycle against the CLASSIC DEMO with demo keys — tests
   auth, placement, cancels, fills plumbing on KXNATGASD demo brackets. Mock funds; prices not
   meaningful.
2. **ECONOMICS loop (prod-public + local ledger):** quotes from the PRODUCTION public API (real
   books, no keys), fills simulated locally by `kalshi_paper_ledger` on the verified fee model.
   This is the loop the day-score reads, because its prices are real.

The daily paper cadence runs BOTH: intents priced on prod-public quotes -> ledger fill (economics)
+ mirrored demo order (mechanics). Divergence between the two is itself a dock measurement.
