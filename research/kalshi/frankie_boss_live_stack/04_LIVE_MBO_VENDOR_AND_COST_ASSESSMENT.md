# Live MBO vendor and cost assessment

Date: 2026-09-04

Decision status: DTN IQFeed is the preferred proof-of-capability candidate. It is not yet approved as the production source. Direct CME remains the control and escalation path, not a presumed USD 600 complete solution.

## Decision in plain language

Frankie needs original order-level events, not merely a deep price ladder. DTN publicly states that IQFeed supports CME and ICE Market by Order data and unlimited Market by Price depth. That makes it a credible supplier to investigate first. The public material does not prove that IQFeed exposes every field and recovery behavior required by the repository's native-MBO scientific contract.

No purchase should be made until DTN provides a sample or trial that passes the field-level proof described below and confirms that a single natural person may run the client on the intended AWS topology.

Direct CME is technically stronger because its MDP feeds are the source protocol and the direct SBE service includes order-level data. It also brings certification, agreements, cloud/network engineering, and non-display licensing that are not represented by the roughly USD 600 monthly feed-license number alone.

## What Frankie actually requires

The accepted BOSS experiment is not satisfied by top of book, MBP-10, or a reconstructed approximation labeled MBO. The acquisition path must preserve enough source truth to deterministically build the repository's canonical event and causal packet.

Required capabilities:

| Requirement | Why it matters | Passing evidence |
|---|---|---|
| Original order identity | Add, modify, and delete events must refer to the same resting order | Stable source order identifier demonstrated across a captured lifecycle |
| Side, price, and quantity | Required for queue reconstruction and typed book state | Raw messages and decoded records agree |
| Action and event type | Distinguishes adds, trades, modifications, cancellations, and resets | Complete field dictionary plus captured examples |
| Source sequence | Detects loss, duplication, and reordering | Monotonic or documented channel sequence with recovery procedure |
| Source and receive time | Preserves causal ordering and latency evidence | Nanosecond or documented precision; source meaning is explicit |
| Event-group boundary | Prevents partial application of an atomic exchange update | Transaction/event boundary or a documented safe substitute |
| Instrument and venue identity | Prevents contract or venue mixing | Stable product, maturity, channel, and venue mapping |
| Recovery and reset behavior | A book that silently crosses a gap is scientifically invalid | Snapshot/recovery/reset procedure tested by forced disconnect |
| Replay and retention rights | The four-date test and audit trail require retained data | Contract explicitly permits the intended storage and internal research use |
| Headless or AWS operation | Live intake is planned on AWS | Written permission and supported topology, not an assumption |

The repository remains authoritative about the canonical schema and `ts_recv_ns` causal clock. A vendor adapter may translate the feed. It may not weaken the schema silently.

## DTN IQFeed assessment

### What the official material establishes

`OFFICIAL EXTERNAL FACT`: IQFeed Developer documentation describes a Windows IQConnect client that exposes COM and TCP socket interfaces to a locally running application. It says direct connection to DTN servers and embedding the IQConnect client are not supported.

`OFFICIAL EXTERNAL FACT`: IQFeed release documentation states that version 6.2 added CME and ICE MBO support and unlimited MBP levels.

`OFFICIAL EXTERNAL FACT`: DTN publishes separate IQFeed service, exchange, depth, and developer-program charges. Public prices can change and must be re-quoted before purchase.

### What remains unproved

The public pages inspected do not settle these BOSS-critical points:

- whether the exposed MBO record contains the original exchange OrderID without lossy remapping;
- the complete action-code and implied-order treatment;
- source message sequence and channel-gap detection;
- packet or event-group boundaries;
- timestamp origin, precision, normalization, and clock discipline;
- recovery behavior after an IQConnect restart or network loss;
- whether historical replay contains the same fields as live MBO;
- whether internal raw-message retention and repeatable research replay are licensed;
- whether an unattended Windows client on the user's AWS account is supported and permitted;
- whether a custom application qualifies for the discounted broker-linked Globex package.

These are acceptance questions, not paperwork to defer until after integration.

### Public-price planning range

The following uses the official public IQFeed price page inspected for this record. It is a planning estimate, not a quote or invoice.

| Component | Public price used | Treatment |
|---|---:|---|
| IQFeed core service | USD 108.15/month | Recurring |
| Real-time US futures | USD 24.87/month | Recurring |
| Market-depth surcharge | USD 24.15/month | Recurring |
| NYMEX Level 1 exchange fee | USD 139.57/month | Conservative public nonprofessional line item |
| Developer subscription | USD 597/year | USD 49.75/month when amortized |
| Startup fee | USD 50 | First month only |

Conservative planning total, excluding AWS, brokerage, execution, taxes, and usage fees:

- recurring equivalent: USD 346.49/month;
- first month: USD 396.49;
- subsequent cash billing may differ because the developer subscription is annual rather than monthly.

DTN also publishes a possible nonprofessional Globex package price of USD 1 per exchange when all eligibility conditions are met, including a fully funded account with a qualified broker and a third-party application that can execute through the broker. Eligibility for the user's own application and intended tastytrade path is not established.

If DTN confirms that waiver in writing, the corresponding planning total is:

- recurring equivalent: USD 207.92/month;
- first month: USD 257.92.

The waiver is a possible reduction, not the budget baseline.

### AWS topology implication

IQFeed's documented local-client design implies a supported Windows host running IQConnect with the Frankie acquisition adapter connecting over local COM/TCP. It does not establish a supported Linux container, direct cloud socket, server redistribution, or embedded library.

A technically plausible topology is one dedicated Windows EC2 instance per permitted IQFeed session, with a local adapter that writes an append-only raw journal and publishes only the governed internal event stream. That topology remains conditional on DTN approval and session/licensing terms.

## Direct CME assessment

### Technical fit

CME's direct SBE market-data path is the strongest technical match. CME's MBO documentation describes order-level market data, and CME's cloud MDP material states that the SBE feed carries full depth/order data. CME's JSON cloud service is a different product and exposes only limited book depth, so it cannot be substituted for BOSS MBO.

CME's low-cost WebSocket futures and options API is also not a substitute. It provides top-of-book/trade-oriented data with conflation, not the complete order lifecycle required for queue reconstruction.

### Cost reality

The user's recollection of approximately USD 600 per month matches the order of magnitude of one 2026 CME feed-license or basic non-display line item. It does not describe the whole direct-MBO stack.

Selected 2026 published monthly line items per exchange include:

| CME line item | 2026 published amount |
|---|---:|
| Feed license | USD 610 |
| Basic non-display Category A1 | USD 609 |
| Basic non-display Category A3 | USD 1,820 |
| Category C | USD 363 |
| User non-display Category A | USD 457 |
| Managed-user Category A | USD 208 |

The 2027 list raises the corresponding figures to USD 631, USD 630, USD 1,883, USD 375, USD 472, and USD 215.

Which lines apply depends on application, entity, provider, access method, and use categories. Categories may stack. Infrastructure, certification, cloud egress, vendor integration, and execution costs are additional. No single total is asserted until CME or an authorized distributor classifies the exact use in writing.

### Likely non-display questions

The intended use may touch more than one category:

- tastytrade execution of CME futures/options for the user's own account resembles own-account CME trading, commonly analyzed under A1;
- using NYMEX information to inform Kalshi execution can resemble use related to an alternative trading venue, commonly analyzed under A3;
- quantitative research, model development, signal generation, or risk processes may implicate Category C or additional policies.

This is an engineering reading of public policy, not legal or licensing clearance. The exact questions must be submitted to CME or the licensed distributor with the actual data flow attached.

## Decision matrix

| Candidate | Native MBO fit | Integration burden | Published cost signal | Current verdict |
|---|---|---|---|---|
| DTN IQFeed | Plausible, field semantics unproved | Moderate; Windows IQConnect constraint | About USD 208 to USD 346 recurring before AWS if eligibility assumptions hold | First proof-of-capability candidate |
| CME direct SBE/cloud MDP | Strongest source semantics | High; agreement, certification, protocol, recovery, and cloud work | Feed line starts near USD 610, but full licensing is materially higher or scope-dependent | Escalation/control path |
| CME low-cost WebSocket API | Fails full-order requirement | Low | Low-cost positioning | Rejected for BOSS MBO |
| Top-of-book or MBP-only retail feed | Fails original-order requirement | Low to moderate | Often cheaper | Rejected for the scientific input |

## DTN proof-of-capability gate

Before purchase or long implementation, request all of the following in one written exchange:

1. A complete CME/NYMEX IQFeed MBO field dictionary and at least one raw sample containing add, modify, partial fill, full fill, delete, reset, and implied activity.
2. Confirmation of original exchange order-identifier preservation.
3. Documentation for source sequence, gap detection, recovery, and book reset.
4. Timestamp definitions and precision for exchange and receive timestamps.
5. Confirmation that live and any replay/historical products expose equivalent MBO semantics.
6. Confirmation that a single natural person may run IQConnect unattended on a dedicated AWS Windows instance.
7. Confirmation of allowed internal storage duration and repeatable research replay.
8. Confirmation of whether the user's custom application plus tastytrade account qualifies for the USD 1 Globex package.
9. A trial or sample window sufficient to run the adapter conformance suite.
10. A complete quote including exchange, depth, developer, session, startup, and any cloud-related charges.

### Mechanical acceptance test

The trial passes only if the adapter can:

- journal the vendor record before transformation;
- deterministically normalize every record;
- reconstruct a book without negative quantity or orphaned order mutations;
- detect deliberately induced duplication, reordering, and a connection gap;
- resume only through the documented recovery path;
- reproduce identical canonical output and hashes from the same raw journal;
- populate every mandatory BOSS field without fabricated defaults;
- keep `ts_recv_ns` semantics explicit and monotonic under the repository rules.

## Cost conclusion

Excluding AWS does not make the whole live system free. Self-hosting an Apache-licensed Granite checkpoint can eliminate a per-token model fee, and the native Frankie/BOSS code has no vendor token charge by itself. The market-data feed, exchange entitlements, developer access, and filled trades still cost money.

The lowest defensible current data-only planning number is USD 207.92/month if DTN approves every discounted-package assumption. The safer public-price number is USD 346.49/month. Neither includes AWS, trading commissions, exchange/clearing/NFA charges, Kalshi transaction fees, taxes, or a second independent data/model provider.

## Lock

Proceed with a bounded DTN proof of capability. Do not call DTN production-ready, do not collapse the input to MBP, and do not budget direct CME as a complete USD 600/month alternative. If DTN fails source-identity, recovery, retention, or AWS-operation gates, escalate to a CME-authorized direct or managed MBO path with a written use-category quote.
