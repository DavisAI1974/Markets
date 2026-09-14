# SPEC: execution adapters (`execution_adapters.py`)

Status: implemented on `claude/execution-adapters-20260914` from integration tip
`4f35963b`. Pure translation and parsing only, exercised with retained synthetic
fixtures and fake transports through the existing `ExecutionLedger`. No live or
sandbox call, credential, order, cancel, flatten or account change. Nothing here
proves authenticated venue behaviour; every provider shape below is taken from the
official documentation read on 2026-09-14 and exercised on synthetic bytes.

Governing spec: `SPEC-execution-controls.md` (adapter-first order: contracts,
policy, ledger, then pure adapter fixtures, then controller with fake transports).
Contracts and ledger are reused unchanged; their acceptance behaviour is untouched.

## Supported subset (exact), everything else refused

| venue | instrument product | order | sides | effect | TIF | price | quantity |
|---|---|---|---|---|---|---|---|
| kalshi | `event` | single-leg `limit` | buy/sell of the pinned YES or NO contract | `open` only | `good_till_canceled`, `fill_or_kill`, `immediate_or_cancel` | fixed-point dollars, 2 to 4 decimals, strictly inside (0,1) | fixed-point contracts, exactly 2 decimals |
| tastytrade | `future` (`Future`) or `future_option` (`Future Option`) | single-leg `Limit` | buy/sell | open/close (option actions carry it; futures use Buy/Sell) | `day`->`Day`, `good_till_canceled`->`GTC`, `immediate_or_cancel`->`IOC` | nonnegative decimal string, up to 8 decimals | decimal string, up to 8 decimals |

Refused with no bytes produced: Kalshi `tif='day'` (not in the v2 enum), Kalshi
`effect='close'` (no reduce_only claim), tastytrade `fill_or_kill` (no FOK enum),
negative tastytrade price (sign lives in the pinned price-effect, never inferred),
any non-`limit` order type, any intent off the instrument grid (no rounding to
valid), a value whose exact decimal needs more places than the venue accepts (no
rounding), a pin whose account key differs from the intent's venue/environment/
account, an `adapter_hash` that is not the pin digest, unsupported enum values in a
pin, and any pin/instrument/intent naming different instruments.

## Caller-pinned mappings (never inferred)

`KalshiPin(account, instrument_id, ticker, outcome, self_trade_prevention_type,
subaccount, price_units_per_dollar, quantity_units_per_contract)` and
`TastytradePin(account, instrument_id, symbol, instrument_type, price_effect_buy,
price_effect_sell, automated_source, source, price_units_per_currency,
quantity_units_per_contract)`. The pin digest is the intent's `adapter_hash` and
must be in `Policy.trusted_adapters` (the existing `adapter_pin` check still
gates it). Unit scales convert the intent's integer units by exact `Fraction`
arithmetic; a result that is not a terminating decimal within the venue's places
refuses. No float enters the path.

Kalshi NO economics use only the explicit complement documented by the YES-book
semantics ("`bid` buys YES, `ask` sells YES"): with `outcome='no'`, buy at p sends
`ask` at `1-p`, sell at p sends `bid` at `1-p`. Legacy `yes_price`/`no_price`/
`action` fields are never emitted.

## Exact wire routes and bodies

Kalshi create-order v2 — POST `/trade-api/v2/portfolio/events/orders`
(`https://docs.kalshi.com/api-reference/orders/create-order-v2`; demo base
`https://external-api.demo.kalshi.co/trade-api/v2` per
`https://docs.kalshi.com/getting_started/quick_start_create_order`). Body keys
sent, canonical JSON (sorted keys, no whitespace, ASCII): `ticker`, `side`
(`bid`|`ask`), `count` (fixed-point string, 2 decimals), `price` (fixed-point
dollars, 2-4 decimals), `time_in_force`, `self_trade_prevention_type`
(`taker_at_cross`|`maker`, required by the schema), `client_order_id`
(= intent id), `subaccount` (explicit, 0 = primary). Not sent: `expiration_time`,
`post_only`, `cancel_order_on_pause`, `reduce_only`, `order_group_id`,
`exchange_index`. Documentation states no idempotency behaviour for
`client_order_id`; none is assumed.

tastytrade submit — POST `/accounts/{account-number}/orders`
(`https://developer.tastytrade.com/reference/orders/postAccountsAccountNumberOrders/`).
Body keys: `order-type` `"Limit"`, `time-in-force`, `price` (decimal string),
`price-effect` (pinned per side), `legs` = one `{instrument-type, symbol, action,
quantity}`, `external-identifier` (= intent id), `automated-source` (pinned
bool), `source` (pinned). Dry-run — POST `/accounts/{account-number}/orders/dry-run`
(`.../postAccountsAccountNumberOrdersDryRun/`) takes the identical body; it is
produced as a distinct `PreflightRequest` type that also binds the account/environment, so it cannot be passed to
`ExecutionLedger.dispatch_once`, and `parse_tastytrade_preflight` refuses any
error or warning. Per the official guide
(`https://developer.tastytrade.com/docs/guides/idempotency-and-retries/`)
"Order placement is not idempotent" and `external-identifier` is correlation only.

Account/environment travel with the wire by `intent_hash` (the intent carries the
`AccountKey`) and by the pin (which binds the same key); the transport host for an
environment is outside this module.

## Provider bytes -> facts -> observation

`TransportReceipt(wire_hash, account, source, http_status, body, received_ns)` is
the caller's trusted transport provenance. `parse_order_response(receipt, intent=,
wire=, pin=, expected_source=)` returns an `OrderFact` binding request hash,
response hash, provider id, echoed client id, verbatim provider status, ledger
status, quantities in intent units, the provider's self-asserted event clock and
the caller's receive clock. A provider clock later than the receive clock refuses.
Identifiers inside JSON are cross-checked against the wire and pin, never trusted
alone; unknown extra JSON fields are retained in the raw bytes and never promoted.

Sources and shapes read:

| source | HTTP | body read | provider status -> ledger |
|---|---|---|---|
| `kalshi.create_order` | 201 | top-level `order_id`, `client_order_id`, `fill_count`, `remaining_count`, `ts_ms` (ms) | `created`: ACKNOWLEDGED if fill 0, PARTIAL if 0<fill<size, refuse if fill==size (conflicting) |
| `kalshi.get_order`, `kalshi.historical_order` | 200 | `order` object: `order_id`, `client_order_id`, `ticker`, `book_side`, `status`, `yes_price_dollars`, `fill_count_fp`, `remaining_count_fp`, `initial_count_fp`, `last_update_time` (`https://docs.kalshi.com/api-reference/orders/get-order`) | `resting` -> ACKNOWLEDGED/PARTIAL by counts; `executed` -> FILLED (counts must agree); `canceled` -> CANCELED |
| `tastytrade.submit_order` | 201 | `data.order` (+ `data.errors` must be empty) | see below |
| `tastytrade.get_order` | 200 | `data` order object (`.../getAccountsAccountNumberOrdersId/`) | `Received`/`Routed`/`Live`/`Cancel Requested` -> ACKNOWLEDGED/PARTIAL by enumerated fills; `Filled` -> FILLED; `Cancelled` -> CANCELED; `Rejected` -> REJECTED; `Expired` refused (gap 1); anything else refused |

tastytrade filled quantity is the sum of the single leg's enumerated `fills[]`
`quantity` values deduplicated by `fill-id`; it must reconcile with `size` minus the single leg's
`remaining-quantity` for nonterminal statuses. The documented field is on the
leg, not the order. If an extra order-level copy is present, it must agree. Acknowledgement size is never
counted as a fill. `remaining_quantity` in the fact and observation means quantity
still working: it is the provider's remaining count while nonterminal and 0 once
terminal (a canceled remainder is not working).

Any status other than the documented success code (timeout, 429, 5xx, 409,
malformed body) is refused as "no provider fact": it is never rejected-and-safe,
never a fill, and the ledger's SENT_UNKNOWN stays until reconciliation.

`observation(fact, intent=, wire=, receipt=, observation_id=,
account_snapshot_hash=, positions_match=)` binds the fact to the ledger
`Observation`. The account snapshot hash and the positions attestation are the
CALLER's independent evidence; an order response never certifies that a fill is
reflected in an account snapshot. The ledger separately requires the typed
reflected snapshot before any terminal reservation release (unchanged rule).

## Pagination and completeness

`parse_kalshi_fills(pages, ...)` takes `((request_cursor, response_bytes), ...)`
in fetch order (`https://docs.kalshi.com/api-reference/portfolio/get-fills`:
`cursor` string, "leave empty for the first page", absent/empty cursor signals the
last page). The chain must start at `''`, each response `cursor` must be the next
request cursor, and the last must be empty; otherwise there is no completeness
claim and the call refuses. Fills are deduplicated by `fill_id`, must belong to
the given `order_id`, ticker and book side, and must not exceed the intent
quantity. Zero pages is refused: absence of evidence is not an empty fill set.
Historical routing (`https://docs.kalshi.com/getting_started/historical_data`):
orders canceled or fully executed before the cutoff are only in
`/historical/orders`; the `kalshi.historical_order` source exists so the caller's
receipt can say which resource answered. A resting-only list cannot establish
absence; the adapter offers no "not found" fact at all.

## Preserved invariants (tested through `ExecutionLedger`)

- exactly one send of exactly the translated bytes; a second dispatch refuses;
- a transport timeout leaves `SENT_UNKNOWN` with the reservation held; restart
  from the trusted checkpoint does not resend;
- a wire under a foreign adapter hash or intent hash refuses before transport;
- an acknowledgement then a terminal order response WITHOUT a reflected account
  snapshot freezes and latches; with the independently pinned snapshot and
  positions attestation the reservation releases once;
- out-of-order (regressing) observations freeze, exact duplicates are idempotent,
  same-id-different-content latches (existing ledger rules);
- kill latch and full journal verification (foreign suffix) unchanged.

## Contract gaps (reported, not patched)

1. tastytrade documents `Expired` as an order status. `Observation.status` /
   the ledger's terminal set (`FILLED`, `CANCELED`, `REJECTED`) have no vocabulary
   for it, so the adapter refuses rather than relabel it as `CANCELED`. Failing
   example: `test_tastytrade_conflicting_or_unknown_statuses_refuse` with
   `status='Expired'` (message "no ledger vocabulary").
   Smallest extension: add `EXPIRED` to the ledger terminal set with the
   `CANCELED` residual rule (`remaining_quantity == 0`).
2. Kalshi counts are fixed-point with 0.01 granularity. This is representable
   today by declaring the quantity unit as 0.01 contract
   (`quantity_units_per_contract=100`); with a 1-contract unit a fractional fill
   refuses ("finer than the declared quantity unit") rather than rounding. Not a
   contract change; a caller unit choice.
3. Cancellation, replacement, multi-leg, market/stop orders, Kalshi
   `reduce_only`/`expiration_time`/`post_only`, tastytrade `GTD`/`gtc-date`,
   account snapshot parsing (positions/balances) and valuation authority are
   outside this slice; the bridge and ledger keep their explicit caller inputs.

## Verification

PYTHONPATH = repository root, `research/kalshi/frankie_boss`, its `tests` dir
(`;` separator on Windows). `python -m pytest research/kalshi/frankie_boss/tests/
test_execution_policy.py test_execution_ledger.py test_execution_adapters.py -q`.


## Codex integration review � 2026-09-14

Imported Claude commit `5e09b38c24722b96ec98f146f902d1feac19448b` onto the
current BOSS integration history, without reapplying the Granite contract.
The original 146 policy/ledger/adapter tests passed before changes. Sixteen
new regression cases first failed against that import; all 162 now pass.

Review corrections:

- Read tastytrade remaining quantity from its single leg as documented by the
  [Get Order schema](https://developer.tastytrade.com/reference/orders/getAccountsAccountNumberOrdersId/).
  Compare decimal prices by exact rational value, accepting equivalent trailing
  zeros while preserving the original response bytes.
- Reject duplicate JSON keys and nonfinite JSON constants, including nested
  unknown fields, rather than silently choosing one interpretation.
- Reject a Kalshi page after a terminal cursor and repeated request cursors.
- Restrict account identifiers interpolated into URL paths to a single safe
  segment. JSON-only identifiers retain their separate rules.
- Bind dry-run requests and receipts to an exact account/environment. Require a
  returned order with matching account, client id, price, TIF and single-leg
  economics; empty warnings/errors alone do not validate an unrelated order.
- Recheck receipt account and fact venue when creating an Observation.
- Reject impossible Kalshi canceled quantities and tastytrade Filled responses
  that still report working quantity before converting terminal working size to 0.

No existing policy, ledger, or contract acceptance rule changed. All tests use
synthetic responses and fake transports; authenticated account/position snapshots,
real provider calls, Expired ledger vocabulary and operational controller wiring
remain outside this slice. This is software integration, not trading readiness.
