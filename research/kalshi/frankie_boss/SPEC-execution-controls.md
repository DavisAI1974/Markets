# Deterministic execution controls, outbox and venue translation

Status: contracts, pure policy and durable synthetic outbox are implemented and
independently reviewed. Provider reconciliation ingestion, venue adapters and
operational execution controller remain future increments.
No provider request or execution authorization. Governing record:
`9006b633829cc2d7d34df269d6645d1ec4ddee54:research/kalshi/frankie_boss_live_stack/05_PERSONAL_AUTOMATED_EXECUTION_AND_LICENSING.md`.
Official API documentation checked 2026-09-14. This spec grants no live-money,
sandbox credential, source-data, or environment-promotion authorization.

### First increment implementation boundary

`execution_contracts.py`, `execution_policy.py`, and
`tests/test_execution_policy.py` implement immutable typed inputs and pure
eligibility receipts only. `evaluate` has explicit clock, loss-day, kill-switch,
independently trusted source-reference hash and valuation hash. Its caller supplies
the trusted policy/registry and complete account/reservation observations; this
module checks consistency but does not attest broker facts or verify publication
bytes by opening the forecast ledger. That integration belongs to the controller.

The implemented arithmetic accepts scaled integers with caller-declared quantity,
price, money and exposure units. Conservative per-quantity valuation/fee ratios
use reduced integer fractions, preserving exact noninteger results without float
or Decimal-context rounding. The independent valuation pin covers the convention,
source and full admissible better-fill price interval. It does not calculate
futures margin, option delta, maximum loss, or fees from market data. The valuation
authority must supply a conservative bound under a declared convention.
Gross exposure is positive, while a separate explicitly side-bound signed net
interval contains zero and fits within the gross bound. Policy never infers net
direction from buy/sell: buying a put may produce negative underlying exposure.
The receipt carries exact signed net endpoints for outward reservation rounding.

Current instrument grids are constant steps from zero; tiered grids, economic
symbol discovery, true expiry/calendar resolution, Decimal-string wire conversion,
and product-specific multi-leg valuation are unsupported future work. Registry
maturity labels and explicit trading windows are checked against caller policy.
Each policy uses one declared unit system. Account exposure must cover every policy
scope; each separately supplied reservation must cover the same scopes (explicit
zero rows allowed). Already-reflected/duplicate intent IDs reject, rather than
being silently double-counted or removed. Conservative gross/net intervals treat
all possible new fills as additional risk, including proposals labeled close;
there is no claimed reduce-only or flatten permission in this first increment.

An allowed receipt means only these pure checks passed. It creates no approval,
reservation, durable intent, dispatch, environment promotion or risk-state update.
The separate ledger increment below supplies atomic reservation and send-time
rechecking. Source/artifact verification against operational publication bytes and
provider fact collection remain controller integration work.

### Durable ledger implementation boundary

`execution_ledger.py` adds exclusive process ownership, journaled approvals and
reservations, send-time policy rechecking, exact wire-byte intent, one injectable
send attempt, uncertain-outcome retention and trusted checkpoint replay. Tests use
synthetic account observations and injected senders; no broker client is present.

Terminal reservation release requires a typed account snapshot, its independently
expected hash, matching account and observation clocks, and reflected intent IDs.
Subsequent approvals use the admitted snapshot frontier; `reflect_account` records
an explicitly verified successor. The caller remains responsible for attesting
provider facts, pagination/completeness and valuation inputs.

The kill latch uses an independent thread event and fsynced sidecar marker, so a
blocked sender cannot delay latching. Journal synchronization occurs at the next
safe boundary or restart. The receipt distinguishes latched, durable and journaled
state; a kill cannot recall an already transmitted request. Regression coverage
includes process exit after the marker is durable but before journal import.

The policy/ledger suite passes 73 tests. This does not establish authenticated
provider reconciliation, exchange-specific translation, cancellation, flattening,
or live account acceptance; those capabilities still need implementation.

## Objective and capability boundaries

Accept an explicitly proposed, receipted intent and deterministically reject or
reserve it under caller-configured limits. Durably record exact approved provider
bytes before one transmission attempt. Reconcile uncertainty without duplicate
submission. B1 retains forecast authority; neither Granite nor free-text Frankie
output chooses an account, broker operation, limit, retry, or credential.

| Module id / proposed additive file | Responsibility | Depends on |
| --- | --- | --- |
| execution-contracts / `execution_contracts.py` | Immutable intents, instrument registry, explicit limits, snapshots, receipts | existing exact evidence primitives |
| execution-policy / `execution_policy.py` | Pure validation and conservative reservation calculation | execution-contracts |
| execution-ledger / `execution_ledger.py` | Durable state, reservations, outbox, single writer and reconciliation | execution-policy |
| execution-adapters / `execution_adapters.py` | Pure typed tastytrade/Kalshi wire translation and injectable I/O boundary | execution-contracts |
| execution-controller / `execution_controller.py` | Recheck, persist, send once, reconcile | execution-ledger, execution-adapters |

Build order: contracts/policy, then ledger with simulated lifecycle, then pure
adapter fixtures, then controller using only fake transports. Each file gets a
focused matching test file. Root reviews these proposed boundaries before coding.
Actual authenticated transports and operational promotion remain later increments.

## Repository audit and reuse

- Reuse `c15_journal.EvidenceJournal`, `pack`, `unpack`, `evidence_hash` for exact
  immutable journal records and trusted count/head replay. Execution gets its own
  database/schema; never insert order events into C15 or the forecast ledger.
- Reuse `forecast_contract.sha256_digest`; use the exact evidence hash pattern
  with a new execution schema. Do not reuse float validation for money/quantities:
  accept canonical decimal strings or explicitly scaled integers and calculate
  with Decimal/integer arithmetic, never binary float rounding.
- Reuse `RollingForecastBook.publication` and existing artifact/consumer binding
  verification to establish the source publication. Preserve category-free record
  bytes/digest and null confidence. A forecast price path is not an order.
- Reuse the uncertain-write stop and trusted-replay patterns in
  `controller_journal.py` and `experiment_reveal.py`, not their domain transitions.
  Verify persisted journal contents at dispatch/reconciliation boundaries, not
  merely cached count/head. Append commit followed by acknowledgement loss is
  always an uncertain write that poisons the instance.
- Preserve `executor/risk.py`, `executor/executor.py`, and `executor/exchanges/*`.
  Their regime/confidence gates, numeric defaults, float sizing, empty allowlist
  behavior, boolean order success and in-memory open-trade state are legacy
  controls, not suitable execution authority here. No tastytrade/Kalshi transport
  was found in that adapter directory (only base and paper).
- `research/kalshi/ng_live_operator.py` tracks source MBO resting orders and states
  that it has no execution authority. Its order objects are not broker orders.
  Do not confuse them with account positions or acknowledged fills.

## Typed inputs and authority

`ProposedIntent` includes unique caller intent ID; venue/environment/account;
explicit instrument registry identity and ordered legs; side and opening/closing
effect; quantity, limit price and currency; order type/TIF/expiration; creation and
expiry times; source publication/artifact/record hashes; source cursor/cutoffs;
model, data, policy, configuration, strategy-proposal and adapter-schema hashes.
Unknown fields/enums or missing pins reject. No coercion, nearest tick rounding,
partial leg dropping, market-order fallback or inferred account/venue.

The proposal producer is a separate declared strategy seam. This increment accepts
typed synthetic proposals; it does not invent a trading rule from B1 or Granite.
Initial supported order shape is explicitly bounded single-leg limit orders.
Futures and future-option symbols must come from verified instrument metadata;
complex spreads/conditional orders are rejected until separately specified.

`ExecutionPolicy` has no operational defaults. Caller must provide explicit
account/venue/product/underlying/maturity/side/order-type/TIF allowlists; per-order
quantity and notional caps; gross/net exposure caps per venue and underlying;
realized and mark-to-market daily loss caps; quote/account/fee-state maximum age;
price/slippage bounds; trading windows; intent lifetime; fee valuation identity;
and trusted model/data/configuration/strategy/adapter pins. Empty allowlists deny.
All numeric caps are finite, nonnegative with declared units; zero means no new
exposure, never disabled enforcement. Missing risk metrics reject, not zero-fill.
Changing policy requires a new explicit generation; no online widening or sizing.

`InstrumentSpec` binds venue symbol, underlying, expiry/session, quantity increment,
price grid (including tier rules), multiplier, currency, payout/risk convention,
supported order semantics and source metadata hash. Canonical serialized decimals
are independently validated at ingestion and wire serialization. A generic
price-times-quantity formula is insufficient for futures/options risk: notional,
margin and maximum loss are distinct. Each supported product needs an explicit
deterministic valuation rule and current required reference inputs; unsupported
products or unbounded risk under the selected policy reject. No invented delta,
volatility, margin, exchange calendar or fee schedule.

`AccountSnapshot` binds account/environment, positions, working orders, balances,
realized P&L and marks/fees, provider observation times, pagination/completeness,
and reconciliation generation. Include external/manual orders and exercise,
assignment/settlement changes. `MarketSnapshot` binds exact instrument, quote and
source identity with event/receive/observation times. Reject future, stale, crossed,
inconsistent or incomplete snapshots. Day boundaries and loss-reset baseline are
explicit timezone/session configuration; restart never resets the loss budget.

## Deterministic policy and reservations

`evaluate(intent, policy, instrument, market, account, reservations, now)` is pure:
return an immutable decision with every measured check, rejection codes, all input
hashes and conservative incremental exposure. It cannot call providers or models.
Use an explicit clock argument. A valid model receipt establishes provenance only;
it never overrides a failed risk check or supplies a confidence cutoff.

Check aggregate existing positions plus all remaining working orders and local
approved/unknown reservations. Avoid double counting orders already represented
in an account snapshot using exact venue/account/client/provider identities and
snapshot watermarks. Compute adverse possible fills: opposing pending orders do
not cancel each other's risk until filled. Evaluate net exposure as a reachable
interval, gross exposure conservatively, and include worst permitted fees and
price movement under the declared valuation rule. Refuse an ambiguous mapping.

Approval and reservation commit atomically in the execution journal under one
writer/dispatch lock. Two individually legal orders may jointly exceed a limit;
the second must observe the first reservation. Recheck fresh account/market,
policy generation and local kill switch immediately before dispatch. Changed
inputs require a newly recorded approval or rejection, never hidden mutation of
approved bytes. An expired approval cannot send after restart.

Kill switch is local, latched and independent of provider availability. It blocks
new exposure immediately. Cancellation is a separately journaled control action;
flattening is an explicit approved reduce-only intent against reconciled positions,
not an unchecked emergency market order. Unknown state blocks automated flattening
that could reverse/increase exposure. Clear/reset is explicit and audited.

## Durable outbox and recovery

Required lifecycle: CREATED -> VALIDATED -> APPROVED -> SENT_UNKNOWN ->
ACKNOWLEDGED -> PARTIAL/FILLED/CANCELED/REJECTED. Local denial/expiration is
distinguished from provider rejection. Provider fill/terminal evidence may arrive
before acknowledgement; replay permits that ordering without losing evidence.

Before I/O, commit SENT_UNKNOWN containing approval hash, exact method/path/body,
environment/account, client correlation ID, adapter/schema/config hashes and
attempt ID. Credentials/signatures are injected only inside the eventual transport
and are never journaled. If commit is uncertain, do not call transport. If the
process dies after commit but before send, restart still treats outcome as unknown.
Never silently reset to APPROVED or resend an unmatched SENT_UNKNOWN.

One attempt per approved intent, including timeout, cancellation, 429, 5xx,
malformed response and authentication-refresh uncertainty. No HTTP/SDK automatic
mutation retries. A response is durably retained before exposing status; its
observation is not proof all fills have arrived. Timeout does not release exposure.
In-flight work remains owned until actual underlying I/O finishes; late responses
are evidence for that attempt only. Overlapping dispatches reject. A second process
must fail an exclusive writer lease before any side effect; single-thread locking
alone is insufficient protection across restarts/processes.

Restore only against an independently trusted count/head and replay legal
transitions, hashes, unique intent/client IDs and reservations. Verify full current
history and checkpoint prefix relationships. Never truncate an unexpected suffix.
Changed bytes under an existing ID reject. Completed replay returns its prior
receipt with zero sends. Persisted historical receipts remain immutable.

Reconciliation correlates exact account/environment/client/provider IDs, legs,
side, quantity and price. Collect all paginated orders, fills and positions across
the required time window; missing page/cursor, conflicting duplicate ID or stale
snapshot freezes new exposure and emits a local structured alert. Deduplicate
fills by provider fill identity; do not count acknowledgement quantities as new
fills. Allow partial-fill/cancel races and late fills with explicit accounting.
Unknown statuses remain unknown. A cancel acknowledgement does not undo fills;
reservation release requires reconciled residual quantity and matching account
state. Corrections/busts append compensating evidence rather than rewriting history.

Not found in one order query is never proof of non-submission. Preserve uncertainty
until authoritative complete reconciliation or an explicit audited operator
resolution. Any resubmission is a new approved intent linked to the old one, with
old possible exposure still reserved unless resolved. No generic exactly-once claim.

## Official provider mappings to pin at implementation

### tastytrade

Use POST `/accounts/{account-number}/orders/dry-run` before POST
`/accounts/{account-number}/orders`, with exact approved economic fields. The
schema uses `order-type`, `time-in-force`, decimal-string `price`, `price-effect`,
`automated-source`, `external-identifier` and ordered `legs`. Preserve explicit
`Future` versus `Future Option`; futures actions are `Buy`/`Sell`, option actions
include opening/closing intent. Do not guess symbology or debit/credit.
[Submit schema](https://developer.tastytrade.com/reference/orders/postAccountsAccountNumberOrders/),
[dry-run schema](https://developer.tastytrade.com/reference/orders/postAccountsAccountNumberOrdersDryRun/).

Treat dry-run as validation evidence, not a fill or capital authorization. Bind its
response to exact economic request bytes and reject errors/unhandled warnings.
Any provider-required preflight field gets a separate explicit final wire hash.
`external-identifier` is correlation, not server-enforced deduplication. Timeout
requires account/order-status reconciliation; never repeat placement automatically.
[Official retry guidance](https://developer.tastytrade.com/docs/guides/idempotency-and-retries/).

### Kalshi

Pin the current event V2 endpoint POST `/trade-api/v2/portfolio/events/orders`.
Its `side` is the YES book (`bid` buys YES, `ask` sells YES); `count` and `price`
are fixed-point strings. Populate durable `client_order_id`, explicit TIF,
self-trade-prevention and account/subaccount routing. Supported TIF values are
`fill_or_kill`, `good_till_canceled`, `immediate_or_cancel`. Translate NO economics
only by a tested explicit complement mapping; never send legacy yes/no fields to
this schema. Preserve `reduce_only`, expiration and other configured semantics.
Do not infer idempotency guarantees from a client ID or HTTP 409.
[Current create schema](https://docs.kalshi.com/api-reference/orders/create-order-v2).

Reconciliation must consult historical cutoffs and query both current and
historical order/fill resources where the window crosses them. Resting-only lists
cannot establish absence of a submitted order. Preserve pagination and exact
fixed-point fill counts.
[Historical routing](https://docs.kalshi.com/getting_started/historical_data),
[fill schema](https://docs.kalshi.com/api-reference/portfolio/get-fills).

### Shared adapter seam

Pure `translate(approved_intent, instrument, adapter_pin)` returns immutable wire
bytes plus all route/schema identities. An eventual injected transport exposes
submit-once, cancel-once and read/reconcile operations separately. No generic
`success: bool` result: use typed acknowledgement, provider rejection, unknown
outcome and observation records with exact sanitized raw response evidence.
Unknown response fields are retained; unknown semantics never promoted to success.
Pin retrieved official schema bytes/digest and test actual documented shapes before
transport implementation. Documentation URLs alone are not reproducible schema pins.

## Acceptance and delivery gates

1. Synthetic boundary tests cover every configured cap at equality and either side;
   missing/negative/NaN/float/unknown fields; decimal grids; sessions, maturity,
   stale/crossed/future state; unknown provenance and empty allowlists.
2. Concurrent approvals cannot oversubscribe remaining budget. Pending opposing
   orders, external orders, partial fills, fees and restarted loss state remain
   counted correctly. Unknown risk never becomes zero.
3. Kill-switch change between approval and send produces zero sends; clearing and
   environment promotion require explicit recorded configuration. Replay/shadow
   modes cannot instantiate credential discovery or mutation transports.
4. Fault injection before/after every durable transition, especially persist-then-
   throw and send-then-disconnect, proves no duplicate send and no lost reservation.
   Test two process writers, trusted restart, foreign suffix, changed intent bytes,
   stale approvals, late response and journal unavailable behavior.
5. Reconciliation tests include reordered/duplicate fills, partial-cancel races,
   unknown terminal values, incomplete pagination, historical cutoff crossing,
   mismatched accounts and positions, assignment, corrections and external orders.
6. Golden pure adapter fixtures verify futures versus options actions, opening/
   closing, debit/credit, exact decimals, Kalshi YES/NO complement, TIF and account
   routing. Unsupported/malformed orders yield zero transport calls. Synthetic
   transport integration proves approved bytes are exactly those transmitted.
7. Native forecast/Frankie/S121 outputs and category-free record bytes remain
   unchanged; no model receives secrets and no model output directly invokes I/O.

Open caller inputs: numeric limits, actual account/instrument/session/fee registries,
valuation conventions and trusted runtime/config pins. These are explicit required
configuration, not gaps to fill with arbitrary numbers. Actual sandbox mechanics,
source rights, empirical promotion evidence and separate production-capital approval
remain outside this software slice. No broad licensing research is required here.
