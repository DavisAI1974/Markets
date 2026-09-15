# Single-use authenticated Kalshi cancellation transport

This additive transport accepts only the cancellation controller's immutable
`CancelWire`. It never expands the existing POST wire/ready-transport interface.
`CancelTransportCapability` is a distinct exact type and digest, with operation
`kalshi.cancel_order`. It retains the established explicit account/environment,
credential reference/version, original adapter digest, official HTTPS origin,
HTTP implementation identity, User-Agent and bounded timing configuration.

`prepare_cancel_transport` validates independently pinned capability and HTTP
identity plus wire/account/adapter/ticker/subaccount bindings before resolving
credentials. It loads the existing Kalshi private key once, before the cancellation
controller samples its final policy clock. The ready lease expires at the earlier
of its configured ready lifetime and `CancelWire.expires_ns`. The controller is
responsible for deriving that exact wire from its independently pinned intent and
operator authorization, including their expiry bounds.

The lease permits one call with that exact wire. It marks itself consumed before
signing or I/O, signs the actual timestamp + DELETE + full path excluding query,
checks the clock again, and passes no more than whole milliseconds remaining to
the existing HTTPSExchange. This preserves exact query bytes while ensuring a
slow connect cannot extend the cancellation authorization window. Less than one
millisecond remaining refuses. Existing HTTPS DNS-return limitations still apply.

HTTP is invoked once with empty body, redirects disabled and retries zero. Every
non-secret response, including 401/404/429/500, returns a `TransportReceipt` bound
to the cancel wire digest/account and source `kalshi.cancel_order`. The controller
retains/interprets it. Known credential echoes and backend exceptions are redacted;
uncertainty never permits reuse, refresh, resend, reservation release or flattening.
Only the controller's durable journal establishes no-resend across restarts.

## Acceptance

- Exact type, independent pin, account, adapter, ticker, subaccount and canonical
  path mutations fail before resolving secrets or HTTP.
- Generated RSA key verifies actual-time DELETE/path signing with query excluded.
- Status/error bytes survive as typed receipts; URL mismatch and known secret
  echoes cannot enter generic receipt storage.
- Ordinary timeout, cancellation, expiry during preparation/signing/connect, and
  concurrent use make at most one HTTP attempt and never renew a consumed lease.
- Wire expiry clamps the request timeout independently of a longer ready lifetime.
- Old POST preparation refuses the cancel capability and CancelWire.
- Fake/local-only tests cover composition with concrete HTTPS; no venue call,
  credentials, cancellation or order occurs during build acceptance.

## Source

The official [Cancel Order V2](https://docs.kalshi.com/api-reference/orders/cancel-order-v2)
documents DELETE `/trade-api/v2/portfolio/events/orders/{order_id}` and auto-routing
with `market_ticker` plus `exchange_index=-1` (or omitted). The shared CancelWire
contract owns canonical subaccount/routing query construction. Authentication uses
the existing [RSA-PSS signing contract](https://docs.kalshi.com/getting_started/api_keys).
