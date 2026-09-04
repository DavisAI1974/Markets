# Source register

Date compiled: 2026-09-04

Purpose: Identify the repository evidence and official external material used in the Frankie BOSS final-candidate decision. External pages can change. Recheck effective prices, terms, model revisions, and API behavior immediately before purchase, deployment, or live-money promotion.

## Evidence standard

- Repository sources establish what this codebase specifies or implements.
- Official vendor and exchange sources establish published product, protocol, license, and pricing statements.
- Vendor benchmarks do not establish Frankie market performance.
- Public documentation does not replace a contract-specific written classification.
- User-supplied facts are recorded as decisions or assertions, not independently verified facts.

## Repository evidence

### Current Frankie branch

Repository: `DavisAI1974/Markets`

Branch: `chatgpt/frankie-raw-mbo-benchmark-20260828`

Inspected head before this documentation commit: `bc8c4fd728036cdc7cedf8d1b9427f58853f2e6c`

| Repository path | Claim supported |
|---|---|
| `DROP_IN_S128.md` | Active branch constraints, frozen Sunday evidence, no-rerun boundary, S128 defect context |
| `SESSION_HANDOFF_2026-09-04_S127.md` | Sunday completion, active Frankie state, provenance and current defects |
| `research/kalshi/frankie_full_stack_runtime_contracts_20260824.py` | Active provider contract pins `gpt-5.6-sol`, not Opus |
| `research/kalshi/agent_frankie.py` | Current Frankie behavior inspected for executable model selection and BOSS seam |
| `research/kalshi/spawn.py` | Current spawn path inspected for executable provider selection |

### Recovered BOSS source branch

Branch: `codex/frankie-boss-raw-mbo-benchmark-20260828`

Inspected tip: `38b37c4323a027b21b5ca65627daf294a1481541`

| Repository path | Claim supported |
|---|---|
| `research/kalshi/frankie_boss/FRANKIE_RAW_MBO_BENCHMARK_NEXT_CHAT_HANDOFF_20260828.md` | Accepted A/B0/B1/B2 matrix, B2 intended full arm, four-date partition, clean/memory variants |
| `research/kalshi/frankie_boss/BOSS_BROWNFIELD_ARCHITECTURE_INVENTORY_20260828.md` | Brownfield component inventory, B1 recurrence gap, component authority |
| `research/kalshi/frankie_boss/GRANITE_4_2_CANDIDATE_ASSESSMENT_20260828.md` | Earlier Granite candidate reasoning and gating direction |
| `research/kalshi/frankie_boss/README.md` | BOSS package status and operating boundaries |
| `research/kalshi/frankie_boss/trunk.py` | Fixed-depth B0 trunk, one temporal-graph branch, gated delta cell, QSV seam |
| `research/kalshi/frankie_boss/teacher.py` | Dipole arm definitions and current `plain_aux` implementation defect |
| `research/kalshi/frankie_boss/state_serialization.py` | Deterministic typed-state serialization boundary for a reasoning assistant |
| `research/kalshi/frankie_boss/causal_packet.py` | Causal packet, source hashes, provenance, and defect boundary |
| `research/kalshi/frankie_boss/frankie_contract.py` | Narrow BLD-1 projection into Frankie |
| `research/kalshi/frankie_boss/benchmark_checkpoint.py` | Benchmark checkpoint/restart surface |
| `research/kalshi/frankie_boss/mbo_resume_state.py` | Raw-MBO resume-state contract |
| `research/refrag/README.md` | ReFRAG operator/QSV ownership and dormant-default governance |
| `research/refrag/qsv_registry.py` | Named QSV registry and ordering surface |
| BOSS and ReFRAG test files adjacent to the modules above | Mechanical behavior checked in the source lineage; not evidence of production MBO performance |

## IBM Granite sources

### Granite 4.2 8B model card

URL: https://huggingface.co/ibm-granite/granite-4.2-8b

Publisher: IBM

Claims used:

- 8B dense decoder-only model;
- bfloat16 weights;
- native 128K context with documented extension support up to 512K;
- thinking and non-thinking behavior plus low-effort reasoning controls;
- supervised and reinforcement-learning/post-training description;
- Apache 2.0 license;
- official inference configuration guidance.

Limit: This is a vendor model card. Its benchmark results do not prove raw-MBO value, calibration, repeatability, latency, or safe trading behavior.

### Granite 4.2 language-model repository

URL: https://github.com/ibm-granite/granite-4.2-language-models

Publisher: IBM

Claims used:

- official release family and usage material;
- model variants and reasoning/agentic positioning;
- Apache-licensed checkpoint availability.

### IBM Research announcement

URL: https://research.ibm.com/blog/introducing-granite-4-2

Publisher: IBM Research

Claims used:

- Granite 4.2 release positioning;
- reasoning, tool-use, and agentic-training description;
- 8B and 30B models receive specialized agentic reinforcement-learning treatment.

Limit: This is vendor-authored product research. It supports design intent, not independent market-domain performance.

## DTN IQFeed sources

### Developer information

URL: https://www.iqfeed.net/dev/

Publisher: DTN IQFeed

Claims used:

- IQConnect is a locally running Windows client;
- developer applications use documented COM/TCP interfaces;
- direct connection to DTN servers and embedding IQConnect are not supported;
- developer program availability and annual subscription context.

### IQFeed 6.2 release notes

URL: https://iqhelp.dtn.com/iqfeed-v6-2-2021-09-17/

Publisher: DTN IQFeed

Claims used:

- CME and ICE MBO support was added;
- unlimited MBP levels were added.

Limit: The release page does not prove the field-level semantic contract required by BOSS.

### IQFeed fees

URL: https://www.iqfeed.net/index.cfm?displayaction=data&section=fees

Publisher: DTN IQFeed

Claims used:

- public core-service, real-time US futures, depth, exchange, and startup prices used in the planning calculation;
- public pricing is composed of multiple line items.

### Developer registration

URL: https://www.iqfeed.net/dev/index.cfm?section=register

Publisher: DTN IQFeed

Claims used:

- developer subscription price and program registration context.

### Globex data packages

URL: https://iqhelp.dtn.com/globex_data_packages/

Publisher: DTN IQFeed

Claims used:

- conditional USD 1 per-exchange nonprofessional package;
- qualifying broker, funded-account, nonprofessional, and executable third-party-application conditions.

Limit: Current tastytrade/custom-app/AWS eligibility is not established by the public page.

## CME Group sources

### June 2026 market-data fee list

URL: https://www.cmegroup.com/market-data/files/june-2026-market-data-fee-list.pdf

Publisher: CME Group

Claims used:

- 2026 feed-license, non-display, user, managed-user, and Category C planning figures;
- fees are categorized and per-exchange or use-dependent as specified by the schedule.

### January 2027 market-data fee list

URL: https://www.cmegroup.com/market-data/files/january-2027-market-data-fee-list.pdf

Publisher: CME Group

Claims used:

- announced 2027 versions of the selected fee lines;
- costs are temporally unstable and must be rechecked.

### Data licensing policy guidelines and non-display FAQ

URL: https://www.cmegroup.com/market-data/distributor/files/cme-group-data-licensing-policy-guidelines-and-non-display-licensing-faq.pdf

Publisher: CME Group

Claims used:

- non-display use is classified by purpose;
- A1, A3, and C use categories and cumulative-use concern;
- provider, user, and managed-service distinctions;
- need for contract-specific classification.

### Market by Order FAQ

URL: https://www.cmegroup.com/articles/faqs/market-by-order-mbo.html

Publisher: CME Group

Claims used:

- MBO distributes individual orders and order-level book detail;
- MBO is distinct from aggregated MBP depth.

### Cloud MDP

URL: https://www.cmegroup.com/market-data/connect-data/cloud-mdp.html

Publisher: CME Group

Claims used:

- SBE and JSON cloud access are distinct;
- SBE provides the fuller direct market-data path and requires onboarding/certification;
- JSON depth is limited and does not replace order-level SBE MBO.

### CME Smart Stream

URL: https://dataservices.cmegroup.com/Featured-Data/CME-Smart-Stream

Publisher: CME Group

Claims used:

- managed cloud delivery exists as a separately contracted alternative.

### Google Cloud Pub/Sub onboarding

URL: https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/457416412/Onboarding%2Bto%2BCME%2BGroup%2Bon%2BPubSub

Publisher: CME Group client documentation

Claims used:

- cloud onboarding includes entitlement/agreement and technical steps;
- direct cloud consumption is not an anonymous retail WebSocket.

### Low-cost real-time futures and options API

URL: https://www.cmegroup.com/market-data/real-time-futures-and-options-data-api.html

Publisher: CME Group

Claims used:

- WebSocket-oriented lower-cost data product;
- top-of-book/trade and conflation limitations make it unsuitable for full-order BOSS input.

## AWS sources

### Update AWS account name

URL: https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-update-acct-name.html

Publisher: Amazon Web Services

Claims used:

- the account display name can be updated;
- a display name is a manageable account attribute.

### Update primary contact

URL: https://docs.aws.amazon.com/accounts/latest/reference/manage-acct-update-contact-primary.html

Publisher: Amazon Web Services

Claims used:

- primary contact information is managed separately from account name.

### Manage payments and tax information

URL: https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/manage-account-payment.html

Publisher: Amazon Web Services

Claims used:

- billing/payment and tax settings are separately managed account records.

## Tastytrade sources

### API quickstart

URL: https://developer.tastytrade.com/docs/get-started/

Publisher: Tastytrade

Claims used:

- official API access and authentication/onboarding surface;
- production API workflow.

### Market-data streaming guide

URL: https://developer.tastytrade.com/docs/guides/stream-market-data/

Publisher: Tastytrade

Claims used:

- broker API market-data integration exists;
- broker market data is a separate integration from DTN/CME native MBO.

### Sandbox

URL: https://developer.tastytrade.com/docs/sandbox/

Publisher: Tastytrade

Claims used:

- nonproduction environment exists for mechanical order/API testing.

### Official MCP server documentation

URL: https://developer.tastytrade.com/docs/sdks-and-tools/mcp-server/

Publisher: Tastytrade

Claims used:

- official MCP tooling supports trading interactions;
- its confirmation behavior is not a substitute for a purpose-built unattended execution adapter.

### Pricing

URL: https://tastytrade.com/pricing/

Publisher: Tastytrade

Claims used:

- published futures and futures-option commissions;
- pass-through exchange, clearing, NFA, and other charges can apply;
- no separate recurring API fee was identified on the official public pages inspected.

## Kalshi sources

### API documentation

URL: https://docs.kalshi.com/welcome

Publisher: Kalshi

Claims used:

- REST, WebSocket, and FIX API surfaces exist for market access and trading.

### Authenticated request quickstart

URL: https://docs.kalshi.com/getting_started/quick_start_authenticated_requests

Publisher: Kalshi

Claims used:

- signed/authenticated production request model and API-key workflow.

### Demo environment

URL: https://docs.kalshi.com/getting_started/demo_env

Publisher: Kalshi

Claims used:

- demo environment exists for nonproduction testing.

### Regulatory fee schedule

URL: https://kalshi.com/regulatory/fee-schedule

Publisher: Kalshi

Claims used:

- transaction fees may apply to executed contracts under the effective schedule;
- fee treatment must be calculated from the current regulatory document.

## User decisions captured

The following are inputs from the user, not external-source claims:

- preserve the currently proven Frankie and Memory A;
- begin with the same four raw-MBO dates;
- exclude the separate Nucleus architecture;
- seriously evaluate Granite rather than accepting vendor claims;
- run the system at minimal non-AWS cost where possible;
- require automated execution;
- use tastytrade for futures/options and Kalshi for event contracts;
- operate as the sole user with personal capital;
- consider DTN as the likely live-MBO supplier;
- allow this documentation commit and push after the other working sessions completed.

## Revalidation triggers

Recheck the relevant source and obtain written confirmation when any of these changes:

- Granite checkpoint, license, runtime, quantization, or inference configuration;
- DTN product/version, exchange package, price, session count, client topology, or retention terms;
- CME fee year, use category, venue destination, distributor, or subscriber identity;
- AWS subscriber, organization, region, additional human access, or data consumer;
- tastytrade or Kalshi API, fee schedule, account type, automation policy, or order semantics;
- the user's capital ownership, entity, venue set, or decision to distribute data or software.

## Citation conclusion

The official sources support Granite's availability and general reasoning design, DTN's claimed MBO product, CME's direct order-level alternatives and licensing structure, AWS account-record separation, and the two execution APIs. They do not establish that B2 is profitable, that the dipole hypothesis works, that DTN passes Frankie's exact MBO schema, or that any particular licensing category has been approved. Those remain test and written-confirmation gates.
