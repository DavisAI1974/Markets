# Kalshi primary balance and resting-order collection

## Contract and scope

This additive slice reads primary-account balance and every page of the explicitly
requested resting-order inventory. It never produces risk valuation, P&L, positions,
fill reflection, account ownership or an atomic-snapshot attestation. `WireRequest`
and the order/controller path remain unchanged.

`KalshiObservationCapability` pins exact AccountKey, CredentialReference, official
environment origin, HTTP implementation identity, User-Agent, per-request timeout,
collection lifetime, order page size/page budget and total response-byte budget.
`ObservationRequest` is a separate frozen GET-only contract: account, capability
hash, source operation, path and canonical query. Primary scope is always explicit
`subaccount=0`. Order queries always include `status=resting` and a fixed `limit`;
only the cursor changes between pages. No ticker, date or exchange filter is used.

The collector validates independent capability/HTTP pins before resolving secrets.
It loads an existing Kalshi key once and signs each GET with its actual request
clock using existing RSA-PSS authentication. It uses the existing HTTPSExchange
interface with no retries or redirects and budgets each request from the remaining
collection lifetime. Credentials/signatures stay transient. Known credential echoes
are refused before receipt retention; exception text is replaced by fixed outcomes.

Every attempted HTTP request yields frozen request/time/status/raw-body evidence,
including ordinary HTTP failures. Failed/unsafe exchanges retain a fixed failure
code instead of secret-bearing bytes. Collection output owns a tuple of attempts;
mutable parsed JSON is never the source of its identity. A required receipt callback
persists each attempt before collection can advance. Persistence failure aborts.
The callback is a trusted durability boundary; the collector cannot prove that a
caller-provided callback actually writes durable storage. HTTP cancellation retains
a sanitized attempted-request receipt before propagating the cancellation. Capability
or secret/key preparation failure aborts before HTTP; pre-request clock/signing/budget
failure has no HTTP attempt to retain. Already persisted attempts remain available.

`last_clock_ns` is the last valid injected clock observation, normally immediately
after receiving an HTTP response. For a clock failure it remains the prior valid
observation, with an explicit failure outcome. It is not the function return time
or the completion time of the retention callback. The clock is checked again before
any subsequent request; final callback time does not change the observed-response
interval or make the REST reads an atomic snapshot. Oversize responses are explicitly
marked `byte_budget` with an empty retained body, never presented as complete bytes.

An explicit incomplete outcome follows malformed JSON, missing/invalid cursor,
duplicate order IDs, returned non-resting/wrong-account/subaccount order rows,
non-success HTTP status, transport failure, page budget or time budget exhaustion.
The collector never treats a short page as terminal. A terminal empty cursor is
required, and all preceding cursors must form one acyclic chain. The balance JSON
must contain exact integer cents and update time plus the documented dollar string;
no rounding or conversion into risk/P&L is performed. Raw additional fields survive.

Completeness means this declared REST page chain ended. Concurrent account changes
can still move rows between pages; this is not an atomic broker snapshot. Resting
orders remain on the live endpoint, so this scope needs no historical cutoff merge.
Canceled/executed history, positions, fills and tastytrade collection remain future
work. Real credentials and account acceptance require a separate authorized run.

## Acceptance before implementation

- Generated-key signature verification proves GET/path signing, query exclusion,
  exact primary scope, stable page limit and escaped cursor round-trip.
- Wrong independent pins fail before secret/network access; POST and changed paths,
  account/subaccount/filter/method/query mutations are refused.
- Success retains the exact balance and every order-page byte in order, including
  the final empty page; later mutation of fake payloads cannot change result digest.
- Missing/cyclic cursors, duplicate IDs, wrong row scope/status and malformed JSON
  retain evidence and remain incomplete. Empty first page with terminal cursor works.
- HTTP 401/429/500 and timeout produce one attempt with no retries. Secret echoes
  never reach the receipt callback, result body or public exception text.
- Page, total-byte and elapsed-time bounds fail closed. Receipt persistence failure
  prevents later pages; signing/clock failures cannot transmit another request.
- Existing execution regression tests remain green; only fake/local traffic is used.

## Official sources checked September 15, 2026

[Balance](https://docs.kalshi.com/api-reference/portfolio/get-balance) defines primary
subaccount zero and integer-cent balance/portfolio values. Its current response schema
explicitly marks `balance_dollars` as a required fixed-point dollar string alongside
required `balance`, `portfolio_value` and `updated_ts`. No synthetic fallback is used.
[Orders](https://docs.kalshi.com/api-reference/orders/get-orders) documents explicit
subaccount selection (omission means all subaccounts), cursor pagination with limit
1–1000, and live availability of resting orders.
[Authentication](https://docs.kalshi.com/getting_started/api_keys) defines timestamp,
method and query-free full-path RSA-PSS signing. Existing auth implementation is reused.
