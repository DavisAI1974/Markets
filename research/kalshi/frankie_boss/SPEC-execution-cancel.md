# Kalshi cancellation control through the existing execution ledger

The cancellation slice adds `CancellationController`, separate immutable control
contracts, and three execution-journal events. The POST order WireRequest and its
transport remain unchanged. Cancellation uses an explicit empty-body DELETE wire,
not an exposure-increasing order or a new order-state machine.

## Official mapping and trust

The exact official [Cancel Order V2 reference](https://docs.kalshi.com/api-reference/orders/cancel-order-v2)
was retained in `provenance/kalshi-cancel-order-v2-20260915.md` with retrieval metadata
in the neighboring JSON file. Its 7,350 bytes have SHA256
`f98d25bff30f0aafc93dafc2b7f373d21378225955e57755a17cd84950899b55`.
The controller verifies these bytes and requires the independently approved
CancelAuthorization.schema_hash to match. The route is
`DELETE /trade-api/v2/portfolio/events/orders/{order_id}` with explicit subaccount,
`exchange_index=-1`, and the original pinned market ticker for auto-routing.
Provider IDs are conservatively limited to letters, digits, underscores and hyphens;
unsupported identifiers refuse rather than entering a different path. The query
is canonical and ticker bytes are escaped. A 200 response is only a cancellation
acknowledgement; optional client ID must match when present. Reduced quantity and
provider/receive clocks are checked against the actual previously observed order.

The coordinator independently supplies and pins CancelAuthorization (account,
original ExecutionAuthority, adapter, cancel transport, issuer, official schema,
validity interval, maximum target age) and CancelIntent (unique control ID,
original submitted intent/wire, provider/client IDs, target receipt, authorization
and bounded validity). Neither object grants capital promotion or authenticates an
issuer by itself. Matching pins certify identity under the host's trust setup.

## Prepare and dispatch

1. Construct `CancellationController(existing_controller, authorization,
   expected_authorization_hash=...)`. It reuses the original authority and account.
2. `prepare(control, expected_control_hash=..., original=PreparedExecution,
   expected_original_hash=..., target_receipt=..., expected_target_receipt_hash=...)`
   revalidates the original prepared bytes, retains the target envelope, and parses
   it with the existing order parser against the original submitted wire. It requires
   a working remaining quantity and the exact provider/client/account/ticker chain.
   The ledger must actually contain that unresolved submitted intent/wire; an
   arbitrary parsed OrderFact is insufficient. The prepared cancellation is retained.
3. Use its distinct CancelWire to prepare a separately authorized single-use DELETE
   transport. Secret resolution/key loading precedes the final controller clock.
   The wire's exclusive expiry is the minimum of control expiry and target receipt
   time plus maximum age plus one nanosecond, preserving the inclusive integer-age
   limit. The transport must cap actual send/connect budget to this expiry.
4. `dispatch_once(prepared, expected_prepared_hash=..., transport=...,
   transport_hash=..., now=...)` revalidates every binding and samples the trusted
   host clock. The existing ledger verifies validity/freshness and the submitted
   identity under its process lease and operation lock, then commits CANCEL_ATTEMPT
   with exact control, authorization, DELETE wire and send/target clocks before I/O.
5. Retain the exact typed response envelope before interpretation. The parser emits
   an acknowledgement, not an OrderFact or reconciliation. CANCEL_RETURN/ERROR
   records the attempt outcome; the resulting receipt links preparation, response
   and trusted execution checkpoint. The response may arrive after request expiry;
   expiry bounds transmission, not the existence of later evidence.

A kill latch permits an explicitly authorized cancellation but still prevents new
exposure. Cancellation never changes the original order status, filled quantity,
reservation, account frontier or kill state. A reported reduction can race fills;
only existing independent order/account/reflection admission may release risk.

## Uncertainty, replay and errors

The execution ledger owns one cancellation-attempt map alongside its original
orders. Replay validates target/authorization/wire/timing and rejects a duplicate
control ID, another control ID for the original order, or another original intent
claiming the same account/provider target. Its mutation is included in journal
rollback snapshots. No separate process lock, reservation book or order lifecycle
is introduced. Old software that does not recognize these events must refuse
replay; recovery uses the frozen compatible execution build and trusted checkpoint.

A journal commit with lost acknowledgement calls no transport and poisons the
instance. Timeout, 404, malformed acknowledgement, interruption and uncertain
response/result storage stop new exposure through the independent durable latch.
Standalone prepare storage failures also latch. Raw responses are retained before
parsing when storage works; unavailable storage never becomes a successful result.
Original exceptions propagate, with latch durability failures chained. This is a
private host error boundary, not a general secret sanitizer; the concrete DELETE
transport separately protects credentials and sanitizes transport failures.

Preserve the database, kill marker, receipt directory and externally retained
checkpoint. Reopen the same ledger; attempted cancellation targets remain consumed
regardless of response loss, restart or a changed control ID. Recovery does not
resend, infer cancellation from not-found, or release risk. A subsequent independent
order/account observation can reconcile the original order through its existing
path. No automatic retry, cancel-replace, bulk cancel, flatten, marker clearing or
operator-resolution mechanism is provided here.

## Validation and remaining inputs

Tests use actual controller/ledger/receipt code with synthetic original submissions
and fake cancel callbacks. They cover kill-before-cancel, acknowledgement without
release, restart/changed-ID refusal, malformed envelopes/quantities/clocks,
authority/target/source pins, expiry, interrupted callbacks and journal/store faults.
The separate transport tests compose generated keys and fake HTTP. No real venue,
account, credentials, principal session, GPU, Sunday, training or new source-market
data operation occurs. Actual approved authority, fresh provider observations,
venue sandbox/recovery acceptance and operator procedure remain operational inputs.
