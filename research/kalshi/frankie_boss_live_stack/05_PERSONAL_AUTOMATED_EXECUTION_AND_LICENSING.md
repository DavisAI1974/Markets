# Personal automated execution and licensing

Date: 2026-09-04

Decision status: Automated execution remains a required target. The planned venue split is accepted for engineering: tastytrade for futures/options and Kalshi for event contracts. Live-money authorization is not granted by this record.

## User-supplied operating facts

`USER DECISION`:

- one natural person operates the system;
- the system trades that person's own accounts and capital;
- automated execution is required;
- tastytrade is the intended futures/options broker;
- Kalshi is the intended event-contract venue;
- AWS is the live runtime location;
- there are currently no other users or active projects sharing the intended live access, according to the user.

Those facts reduce organizational complexity. They do not by themselves waive exchange non-display licensing, broker API rules, market-data rights, or trading fees.

## Is a separate trading-app fee required?

No separate recurring tastytrade API platform fee was found in the official public material inspected for this record. Tastytrade provides documented OAuth/API access, production and certification/sandbox environments, market-data streaming guidance, and published trading commissions.

That does not mean execution is free. Filled futures and futures-option orders incur commissions and pass-through fees. Tastytrade's public pricing lists, among other products:

| Product | Published commission signal | Additional costs |
|---|---:|---|
| Futures | USD 1.00 per contract to open and USD 1.00 to close | Exchange, clearing, NFA, and other applicable fees |
| Options on futures | USD 1.25 per contract to open and USD 1.25 to close | Exchange, clearing, NFA, and other applicable fees |

The exact schedule and account permissions must be checked again before launch.

Kalshi's public API documentation exposes REST, WebSocket, and FIX capabilities for trading. No recurring public API subscription fee was identified in the material inspected. Kalshi transaction fees can apply to executed trades under its current regulatory fee schedule. Fee formulas and product-specific treatment must be calculated at order time from the then-effective schedule.

## Market data and execution are separate contracts

Using tastytrade to place a CME order does not automatically grant Frankie the right to ingest and retain DTN or direct CME MBO on AWS. Likewise, a Kalshi account does not grant the right to use CME/NYMEX data as an automated signal without the relevant market-data classification.

The system has at least four separate commercial and policy surfaces:

| Surface | Provider or authority | What must be cleared |
|---|---|---|
| Source market data | DTN and/or CME | Display/non-display use, exchange entitlement, retention, replay, cloud topology |
| Futures/options execution | tastytrade | API access, account approval, automation policy, order types, rate limits, commissions |
| Event-contract execution | Kalshi | API credentials, account eligibility, automation/rate limits, transaction fees |
| Cloud runtime | AWS | Account identity, security, cost, region, logging, and incident control |

## Likely CME non-display classification

CME's policy focuses on how data is used, not only on whether the user is a person or company. The intended system consumes exchange data without a human display as the primary purpose and uses it in automated logic, so a non-display analysis is required.

Potential categories include:

| Planned use | Plausible policy category | Why it must be confirmed |
|---|---|---|
| Use CME/NYMEX data to automate trades in the user's own CME account through tastytrade | Category A1 or a provider's corresponding user license | Own-account trading is distinct from human display |
| Use CME/NYMEX data to inform Kalshi orders | Category A3 or alternative-venue treatment | The resulting trade is not executed on CME |
| Build, backtest, calibrate, or risk-manage Frankie/BOSS | Category C or another research/analytics treatment | Research and signal generation can be separately categorized |

CME categories can be cumulative. The cheapest interpretation must not be assumed. Send the actual data-flow diagram and these exact uses to DTN/CME and request a written classification for a single natural person using only personal capital.

## DTN discounted-package issue

DTN describes a USD 1 per-exchange nonprofessional Globex package with conditions that include:

- a fully funded account with a qualified broker;
- all nonprofessional qualification questions answered in the qualifying direction;
- IQFeed received through a third-party trading application that can execute through the linked broker.

Open questions for the current plan:

- whether tastytrade is a qualifying broker for that package;
- whether the user's custom Frankie application counts as the required third-party application;
- whether orders must be executable through the same application/feed integration rather than through a separate tastytrade API adapter;
- whether using the same data for Kalshi signals changes eligibility;
- whether an AWS-hosted unattended process remains within nonprofessional and session terms.

Budget the full public exchange fee until DTN answers all five in writing.

## Execution architecture lock

No language model, including Granite, receives broker credentials or emits a broker-ready request directly. The final pathway is deterministic and typed.

| Stage | Responsibility | Failure behavior |
|---|---|---|
| Native BOSS/Frankie | Produce a receipted market assessment and bounded proposed intent | Invalid state means abstain |
| Policy gate | Enforce allowed instrument, side, size, price, time-in-force, session, exposure, and loss limits | Any violation means reject |
| Venue router | Select only the predeclared tastytrade or Kalshi adapter | Unknown venue means reject |
| Order ledger | Assign durable intent ID and record state before transmission | Ledger unavailable means reject |
| Broker adapter | Translate the exact approved intent to the provider schema | Schema mismatch means reject |
| Reconciler | Compare acknowledgments, fills, cancels, and account state | Ambiguity freezes new exposure and alerts |

Granite may criticize an intent before promotion or supply a bounded feature after promotion. It cannot bypass the policy gate, change an approved intent after hashing, or retry an order.

## Required safety controls

### Before any outbound request

- allowlist accounts, venues, products, maturities, and order types;
- set per-order quantity and notional limits;
- set gross and net position limits by venue and underlying;
- set daily realized and mark-to-market loss limits;
- reject stale market state and crossed or inconsistent books;
- reject intents whose model, data, policy, or configuration hashes are unknown;
- require a current broker/account snapshot;
- record a durable intent before sending;
- support a global local kill switch independent of provider availability.

### Retry and idempotency

Tastytrade documentation warns that retrying order submission can create duplicate orders; the client must provide its own durable control. Use the API's dry-run validation where available, then submit once from an outbox state machine. Never infer failure merely from a timeout.

Required states are at least:

`CREATED -> VALIDATED -> APPROVED -> SENT_UNKNOWN -> ACKNOWLEDGED -> PARTIAL/FILLED/CANCELED/REJECTED`

On an ambiguous timeout, query broker/account order state and reconcile before any retry. A new submission requires a new approved intent unless the provider documents an idempotency key with the exact desired semantics.

For Kalshi, populate its client order identifier where supported and still maintain the local durable ledger. Provider-side identifiers complement local reconciliation; they do not replace it.

### Unattended authentication

- store broker and venue secrets in AWS Secrets Manager or an equivalent encrypted service;
- use separate production and sandbox credentials;
- grant the runtime only the minimum account and order permissions;
- never place credentials in prompts, model context, logs, result bundles, or Git;
- rotate credentials through a rehearsed procedure;
- stop new exposure when token refresh or signature state is ambiguous;
- keep clock synchronization and signed-request drift alarms.

### Operational controls

- heartbeat each market-data and execution session;
- alarm on feed gaps, stale state, reject bursts, reconciliation mismatches, position drift, and risk-limit proximity;
- implement cancel-all and flatten procedures appropriate to each venue;
- test disconnect, partial fill, cancel/replace, restart, and provider outage behavior;
- require a human-controlled promotion flag for every environment transition;
- preserve an append-only audit chain from source event through final fill.

## Promotion ladder

| Stage | Data | Execution | Capital | Exit gate |
|---|---|---|---|---|
| Replay | Recorded four-date input | No adapter call | None | Deterministic decisions and ledger simulation |
| Shadow live | Live data | Produce intents only | None | Stable feed, latency, and disagreement evidence |
| Provider sandbox | Live or provider test data | Sandbox APIs | None | Restart, retry, reject, and reconciliation tests pass |
| Paper/simulation | Live data | Venue-supported simulation where available | None | Multi-session operational evidence |
| Bounded live | Live data | Production APIs | Minimal declared limits | No severity-one safety defect and explicit user authorization |
| Expanded live | Live data | Production APIs | Separately approved | Evidence-based limit increase, not automatic scaling |

Kalshi offers a demo environment. Tastytrade documents a sandbox/certification environment. Provider test environments can differ from production liquidity, permissions, and order lifecycle; use them to prove mechanics, not profitability.

## Cross-model and stopgap conclusion

Current Frankie without Granite is the protected orchestration and reasoning baseline. It is not, on repository evidence, a validated standalone market predictor. B0 is a fixed-depth BOSS control, not a proven trading edge. B1 is the intended native reasoning layer but is not implemented. Granite can be self-hosted without a per-token license fee, but that does not turn an unvalidated model into an independent oracle.

For the initial four-date program:

- use Frankie/A as the unchanged baseline;
- use B0 as the built native control once the brownfield adapter exists;
- build B1 as the authoritative reasoning candidate;
- run Granite B2 in a shadow/critic lane;
- compare paired outputs, calibration, abstention, latency, and failure behavior;
- do not require a paid second LLM API merely to claim cross-model evidence.

An open-source second model can later be added as an ablation if it contributes a genuinely independent checkpoint and runtime. Calling the same local checkpoint through a different wrapper is not cross-model validation. No free external API should be assumed to have durable capacity, privacy, or terms suitable for live automation.

## Launch blockers

Live automated execution remains blocked until:

1. DTN/CME data rights and use categories are confirmed in writing.
2. tastytrade and Kalshi production API access and account permissions are verified.
3. The BOSS input, B1 reasoning, and deterministic risk/order seams are implemented and tested.
4. The dipole experiment and Granite shadow lane complete their promotion gates.
5. Replay, sandbox, and shadow-live failure tests pass.
6. Position, loss, stale-data, kill-switch, and reconciliation controls are independently exercised.
7. The user gives a separate explicit production-capital authorization with numeric limits.

## Lock

Keep automated execution in scope. Treat tastytrade and Kalshi as separate typed execution adapters behind one deterministic policy and ledger. Treat source-market-data licensing separately from broker access. Do not pay a presumed trading-app fee that the provider does not publish, but budget commissions, exchange/pass-through charges, Kalshi transaction fees, market data, AWS, and any confirmed non-display licenses.
