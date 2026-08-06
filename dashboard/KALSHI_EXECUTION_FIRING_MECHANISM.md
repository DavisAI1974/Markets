# Kalshi Execution Firing Mechanism

Date: 2026-08-05
Status: DESIGN ONLY - NOT WIRED
Environment for first implementation: Kalshi Demo

## Purpose

This document defines how a future DavisAI signal can become a Kalshi order without allowing
the browser, dashboard, forecaster, or signal registry to place trades directly.

The current dashboard remains a read plane. It displays:

- signals consumed by the brain;
- the selected as-of decision state;
- a versioned demonstration opportunity feed;
- Kalshi market data when present locally;
- no execution authority.

The firing mechanism should be a separate server-side service added only after the policy for
when a signal may fire has been agreed and tested in the Kalshi Demo environment.

## Official Kalshi sources

API environments:
https://docs.kalshi.com/getting_started/api_environments

Demo environment:
https://docs.kalshi.com/getting_started/demo_env

API keys and RSA-PSS signing:
https://docs.kalshi.com/getting_started/api_keys
https://docs.kalshi.com/getting_started/quick_start_authenticated_requests

Current V2 event-order create and cancel:
https://docs.kalshi.com/api-reference/orders/create-order-v2
https://docs.kalshi.com/api-reference/orders/cancel-order-v2

Order groups:
https://docs.kalshi.com/api-reference/order-groups/create-order-group

Orders and fills:
https://docs.kalshi.com/api-reference/orders/get-orders
https://docs.kalshi.com/api-reference/orders/get-order
https://docs.kalshi.com/api-reference/portfolio/get-fills

WebSocket connection and user-order stream:
https://docs.kalshi.com/getting_started/quick_start_websockets
https://docs.kalshi.com/websockets/user-orders

Account limits and endpoint costs:
https://docs.kalshi.com/api-reference/account/get-account-api-limits
https://docs.kalshi.com/api-reference/account/list-non-default-endpoint-costs
https://docs.kalshi.com/getting_started/rate_limits

Official Kalshi GitHub organization and starter code:
https://github.com/Kalshi
https://github.com/Kalshi/kalshi-starter-code-python

## Environment boundaries

Kalshi Demo and production use different credentials and endpoints.

Recommended Demo endpoints:

```text
REST: https://external-api.demo.kalshi.co/trade-api/v2
WS:   wss://external-api-ws.demo.kalshi.co/trade-api/ws/v2
```

Recommended production endpoints:

```text
REST: https://external-api.kalshi.com/trade-api/v2
WS:   wss://external-api-ws.kalshi.com/trade-api/ws/v2
```

Use separate environment variables and separate key files:

```text
KALSHI_ENV=demo
KALSHI_DEMO_API_KEY_ID=...
KALSHI_DEMO_PRIVATE_KEY_PATH=/run/secrets/kalshi-demo-private-key.pem
KALSHI_EXECUTION_ENABLED=false
```

Do not put either key in the repository, frontend bundle, HTML snapshot, browser local storage,
log output, test fixture, or exception message.

## Required service separation

### 1. Signal emitter

The signal core produces one canonical output per target. It does not know Kalshi credentials and
does not call Kalshi.

Output:

```json
{
  "schema": "davisai.signal_emit.v1",
  "signal_id": "stable-id",
  "decision_id": "causal-decision-id",
  "as_of_utc": "2026-08-05T22:00:00Z",
  "target": "KXNATGASD",
  "direction": "up",
  "status": "eligible",
  "provenance": "blind",
  "policy_version": "pending",
  "evidence": ["signal paths"],
  "expires_at_utc": "2026-08-05T22:02:00Z"
}
```

The emitter must not invent a market ticker, order size, price, or execution mode.

### 2. Market mapper

The mapper resolves a signal target to an exact open Kalshi market and validates:

- event ticker and market ticker;
- settlement rule and source;
- close time;
- strike or bracket semantics;
- side conversion;
- market status;
- orderbook availability;
- whether the mapping is exact or related.

Only an exact mapping may proceed to an executable intent. Related markets remain signal-only.

### 3. Firing-policy service

This is the unresolved mechanism Greg referred to. It decides whether an eligible signal becomes:

```text
NO_CALL
SHADOW
SIGNAL
APPROVAL_REQUIRED
AUTO_ELIGIBLE
```

The policy must be versioned. It should use named gates rather than one score. No gate, threshold,
weight, or coefficient should be entered until it is measured against the desk's own evidence.

Minimum gate families:

```text
causal wall passed
signal not stale
market mapping exact
market open and tradable
quote fresh
definition snapshot unchanged
brain provenance allowed for requested mode
position and loss limits available
order-group capacity available
no duplicate intent or live order
no operator pause
no venue or data health fault
```

### 4. Risk coordinator

The risk coordinator converts an approved signal into an immutable order intent. The browser can
request or display an intent, but cannot create or mutate it.

Suggested contract:

```json
{
  "schema": "davisai.kalshi_order_intent.v1",
  "intent_id": "stable-id",
  "signal_id": "stable-id",
  "decision_id": "causal-decision-id",
  "environment": "demo",
  "market_ticker": "resolved-open-market",
  "book_side": "bid",
  "count_fp": "10.00",
  "price_dollars": "0.5600",
  "time_in_force": "fill_or_kill",
  "post_only": false,
  "cancel_order_on_pause": true,
  "reduce_only": false,
  "order_group_id": "group-id-or-null",
  "created_at_utc": "2026-08-05T22:00:00Z",
  "expires_at_utc": "2026-08-05T22:00:20Z",
  "policy_version": "kalshi-fire.v1",
  "approval": {
    "required": true,
    "approved_by": null,
    "approved_at_utc": null
  }
}
```

Use fixed-point strings or Decimal objects for contracts and prices. Do not use binary floats in
the executor.

### 5. Kalshi executor

The executor is the only process allowed to read the private key. It accepts immutable approved
intents and performs only these actions:

```text
validate intent
create deterministic client_order_id
check local dedupe ledger
check current Kalshi orders and positions
check intent expiration
submit one order
record request hash before network send
record response and order_id
track order through WebSocket user_orders and fills
cancel, decrease, or amend only from a new versioned intent
reconcile with REST after reconnect or sequence uncertainty
```

Do not automatically retry an order POST or cancellation DELETE after an ambiguous network
failure. Reconcile by client_order_id, order_id, orders, and fills before deciding what happened.

### 6. Reconciler

The reconciler owns the order truth ledger:

```text
INTENT_CREATED
RISK_APPROVED
SUBMITTING
ACKNOWLEDGED
RESTING
PARTIAL
FILLED
CANCEL_REQUESTED
CANCELED
REJECTED
EXPIRED
UNKNOWN_RECONCILE_REQUIRED
```

Every transition records:

```text
timestamp_utc
intent_id
client_order_id
order_id
market_ticker
previous_state
new_state
source: rest | websocket | operator
raw_response_hash
reason
```

## Request signing

Authenticated requests require three headers:

```text
KALSHI-ACCESS-KEY
KALSHI-ACCESS-TIMESTAMP
KALSHI-ACCESS-SIGNATURE
```

The signature message is:

```text
timestamp_milliseconds + HTTP_METHOD + full_request_path_without_query
```

The full request path includes `/trade-api/v2`. Sign with RSA-PSS and SHA-256, then base64 encode
the signature.

Reference implementation adapted from Kalshi's official authentication documentation:

```python
from __future__ import annotations

import base64
import time
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


def load_private_key(path: str) -> rsa.RSAPrivateKey:
    raw = Path(path).read_bytes()
    key = serialization.load_pem_private_key(raw, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise TypeError("Kalshi key must be an RSA private key")
    return key


def signed_headers(
    key_id: str,
    private_key: rsa.RSAPrivateKey,
    method: str,
    request_path: str,
) -> dict[str, str]:
    timestamp = str(int(time.time() * 1000))
    path_without_query = request_path.split("?", 1)[0]
    message = f"{timestamp}{method.upper()}{path_without_query}".encode("utf-8")
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {
        "Content-Type": "application/json",
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("ascii"),
    }
```

## Safe Demo client skeleton

This code is a design example. It must not be imported by the dashboard server until the firing
policy is approved.

```python
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from decimal import Decimal

import requests

DEMO_HOST = "https://external-api.demo.kalshi.co"
API_ROOT = "/trade-api/v2"


@dataclass(frozen=True)
class OrderIntent:
    intent_id: str
    ticker: str
    book_side: str
    count: Decimal
    price: Decimal
    time_in_force: str
    order_group_id: str | None = None


class KalshiDemoExecutor:
    def __init__(self) -> None:
        if os.environ.get("KALSHI_ENV") != "demo":
            raise RuntimeError("This client is demo-only")
        self.key_id = os.environ["KALSHI_DEMO_API_KEY_ID"]
        self.private_key = load_private_key(os.environ["KALSHI_DEMO_PRIVATE_KEY_PATH"])
        self.execution_enabled = os.environ.get("KALSHI_EXECUTION_ENABLED") == "true"

    def _request(self, method: str, path: str, *, json_body=None):
        headers = signed_headers(self.key_id, self.private_key, method, path)
        response = requests.request(
            method,
            DEMO_HOST + path,
            headers=headers,
            json=json_body,
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def list_orders(self):
        return self._request("GET", f"{API_ROOT}/portfolio/orders")

    def list_fills(self):
        return self._request("GET", f"{API_ROOT}/portfolio/fills")

    def create_order(self, intent: OrderIntent):
        if not self.execution_enabled:
            raise RuntimeError("Demo execution is disabled")
        client_order_id = str(uuid.uuid5(uuid.NAMESPACE_URL, intent.intent_id))
        path = f"{API_ROOT}/portfolio/events/orders"
        body = {
            "ticker": intent.ticker,
            "client_order_id": client_order_id,
            "side": intent.book_side,
            "count": format(intent.count, "f"),
            "price": format(intent.price, "f"),
            "time_in_force": intent.time_in_force,
            "self_trade_prevention_type": "taker_at_cross",
            "cancel_order_on_pause": True,
            "order_group_id": intent.order_group_id,
        }
        return self._request("POST", path, json_body=body)

    def cancel_order(self, order_id: str):
        if not self.execution_enabled:
            raise RuntimeError("Demo execution is disabled")
        path = f"{API_ROOT}/portfolio/events/orders/{order_id}"
        return self._request("DELETE", path)
```

Before using this skeleton, confirm every current request and response field against Kalshi's live
OpenAPI documentation. The API evolves, and field drift must fail closed.

## Order groups

An order group can cap matched contracts over Kalshi's rolling 15-second group window. The firing
service should create or select the group before submitting an order and store the group ID in the
intent.

Order groups supplement DavisAI risk controls. They do not replace:

```text
per-market position limit
per-thesis limit
per-day loss limit
stale-signal expiration
quote-age guard
duplicate-order guard
operator pause
reconciliation after uncertainty
```

## Demo rollout sequence

### Stage 0 - current branch

```text
SIGNALS_IN_USE registry displayed
real as-of signal values displayed when available
demo opportunities displayed
credentials reported only as present or absent
no authenticated Kalshi call
no order endpoint in dashboard
```

### Stage 1 - authenticated reads

```text
load demo credentials server-side
GET account limits
GET balance
GET open orders
GET fills
subscribe to user_orders and fills
write append-only read/reconciliation logs
no order submission
```

### Stage 2 - shadow intents

```text
market mapper resolves exact demo ticker
firing policy emits immutable intents
executor validates and logs would-submit payload
payload hash and expected order-group usage recorded
no POST or DELETE
```

### Stage 3 - one-contract Demo approval mode

```text
operator approval required
demo environment hard-coded
one active intent at a time
order group present
create one order
observe acknowledgment, fill, rest, and cancel states
reconcile REST versus WebSocket
```

The one-contract condition is an operational rollout constraint, not a fitted trading threshold.

### Stage 4 - Demo automatic mode

Enable only after the firing policy, duplicate protection, reconnect reconciliation, and kill-path
tests all pass in Demo.

### Stage 5 - production review

Production requires a separate key, separate deployment configuration, explicit authorization, and
an independent readiness review. Do not promote a Demo key or environment file.

## Acceptance tests before any firing

```text
1. Browser source and network responses contain no private key or API key ID.
2. Dashboard process cannot import the executor package.
3. Demo and production hosts cannot be selected by the same unvalidated string.
4. An expired signal cannot create an intent.
5. A related market mapping cannot become executable.
6. Replaying the same intent produces the same client_order_id and no duplicate order.
7. Ambiguous POST timeout enters UNKNOWN_RECONCILE_REQUIRED, never blind retry.
8. WebSocket disconnect triggers REST reconciliation before further writes.
9. Operator pause prevents new orders and requests cancellation only through policy.
10. Order-group limits and account API budgets are checked before submission.
11. Every Decimal survives serialization without binary-float conversion.
12. Every request, response, transition, and operator approval is append-only logged.
13. Demo mode refuses a production hostname and production credentials.
14. Production mode remains absent until separately approved.
```

## Build decision

Wire the demo feed now. Add authenticated Demo reads next when the key is found. Do not connect the
order POST until the canonical signal emitter and firing-policy state machine exist.
