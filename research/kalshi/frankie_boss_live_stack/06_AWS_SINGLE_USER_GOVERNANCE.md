# AWS single-user governance

Date: 2026-09-04

Decision status: An AWS account display name such as `DavisAI` is not by itself a blocker. The account still needs a documented personal single-user control package before market-data or production broker credentials are installed.

## Facts and limits

`USER DECISION`: The user believes the AWS account may be named `DavisAI`, is the only person using the intended live project, and has no other active workload on the account. A HomeLift-related item may exist but is not currently running.

`OFFICIAL EXTERNAL FACT`: AWS allows an account name to be edited. AWS separately maintains primary contact, alternate contacts, billing, payment, and tax information. The visible account name therefore is a label, not complete proof of the legal subscriber, taxpayer, or market-data end user.

`INFERENCE`: A `DavisAI` account name can be compatible with a personal single-user deployment if the underlying billing/contact/tax identity is accurate and vendor declarations describe the actual person, use, devices, and automation. Market-data vendors may still classify a branded name, business activity, software development, non-display use, or alternative-venue use differently. Obtain their answer in writing.

This document is an engineering governance record, not tax or legal advice.

## Identity evidence package

Before signing a DTN, CME, tastytrade, or Kalshi production agreement, capture a dated internal record of:

| Evidence | Required statement |
|---|---|
| AWS account ID | Exact 12-digit account identifier, never a guessed display name |
| AWS account name | Current display label and whether it is changed |
| Primary contact | Natural person or entity actually controlling the account |
| Billing/payment identity | Name and address tied to payment method |
| Tax profile | Actual tax identity selected in AWS billing |
| Organization membership | Whether the account is standalone or belongs to AWS Organizations |
| Root access custody | User-controlled, MFA-protected, no shared root credentials |
| IAM identities | Complete list of human users, roles, access keys, and federated principals |
| Active workloads | Services, regions, resources, and cost centers currently active |
| Dormant workloads | HomeLift or other resources that exist but are stopped or unused |
| Vendor subscriber | Exact natural person/entity named in each data and brokerage agreement |
| Intended use | Personal capital, non-display model use, AWS runtime, tastytrade and Kalshi execution |

Do not put the 12-digit account ID, contact data, tax identifiers, secret ARNs, account numbers, or credentials in Git. The repository should contain only the dated conclusion and evidence hashes or redacted references.

## Single-user baseline

The user reports there are no other users or active consumers. Verify rather than assume this before vendor onboarding:

- enumerate IAM users, roles, identity-center assignments, access keys, and recent authentication events;
- enumerate linked accounts and AWS Organizations membership;
- enumerate EC2, ECS, EKS, Lambda, RDS, S3, Secrets Manager, CloudWatch, and networking resources in every enabled region;
- locate any HomeLift resources and tag them as dormant, archive, or separate project;
- verify no credentials are shared with Claude, Frankie, Fable, another agent, contractor, or application outside the governed runtime;
- verify no data stream is redistributed to another person, account, public endpoint, or unrelated project.

An agent may operate through a least-privilege runtime role. That is not a second human user. A second natural person receiving or using the feed can materially change vendor terms and must be reported.

## Recommended account structure

For the first proof of capability, using the existing account can be acceptable if the audit is clean. Avoid a rushed account migration solely because the display name is `DavisAI`.

Create a hard project boundary inside the account:

| Control | Required implementation |
|---|---|
| Project tag | Apply a stable `Project=FrankieLive` tag to every supported resource |
| Environment tag | Separate `replay`, `shadow`, `sandbox`, and `production` |
| Cost allocation | Activate project/environment tags and a dedicated budget |
| Network | Dedicated VPC/subnets/security groups; no public inbound administration |
| Compute | Dedicated host or instance for the licensed feed session as required |
| Storage | Separate encrypted raw journal, canonical data, results, and audit prefixes |
| Secrets | Separate DTN, tastytrade, and Kalshi secrets with distinct runtime permissions |
| Logging | Central append-only operational and security logs with retention policy |
| IAM | One deployment role, one runtime role per function, and explicit deny boundaries |
| Kill control | Human-controlled mechanism that removes order permission without deleting evidence |

If HomeLift becomes active, another human joins, an entity becomes the subscriber, or data is consumed by another application, re-run the licensing classification before sharing infrastructure or streams.

## Root and IAM controls

- protect root with phishing-resistant MFA where available;
- do not create or retain root access keys;
- use a separate administrative identity for routine work;
- require MFA for privileged changes;
- prohibit long-lived developer access keys when workload roles can be used;
- constrain production runtime roles to the exact secret, queue, storage prefix, and network actions needed;
- separate market-data intake permission from broker-order permission;
- make the Granite inference role unable to read broker secrets;
- make the execution adapter unable to rewrite raw market journals or model artifacts;
- review CloudTrail and credential reports before every promotion stage.

## Data controls

Market-data contract terms must become technical controls:

- encrypt in transit and at rest;
- keep original vendor records in an append-only licensed-retention prefix;
- keep deterministic normalized records separately;
- prevent public access at the account and bucket level;
- limit replay access to the licensed single-user runtime;
- log reads and exports of raw feed data;
- apply retention and deletion only after the vendor terms are recorded;
- do not copy raw MBO into prompts or an external hosted model without explicit rights;
- do not place raw feed data in GitHub, ChatGPT attachments, general-purpose agent memory, or public artifacts.

Granite self-hosting is the preferred initial posture partly because the serialized state can stay inside the governed AWS boundary. The serializer should still minimize content and exclude credentials, account identifiers, future labels, and unrelated memory.

## Cost controls

Excluding AWS from the user's vendor-cost comparison does not remove the need to control AWS spend. Before live intake:

- set a monthly AWS Budget with email/SNS alerts at multiple thresholds;
- alarm on unexpected EC2, storage, egress, NAT Gateway, and GPU spend;
- use a separate cost-allocation tag for Granite inference;
- measure whether Granite needs an always-on GPU or can run in bounded batches/shadow windows;
- lifecycle only data the contract permits to cheaper storage;
- avoid building cross-region replication until recovery and licensing require it;
- stop development instances automatically, but never auto-stop the licensed live collector without a safe feed/recovery procedure.

Self-hosted Granite has no per-token model-license charge under its Apache 2.0 terms. Its compute is not free; if that compute runs in AWS, it appears in the AWS bill the user chose to exclude from the model/vendor subtotal.

## Evidence and change control

Create a private, non-repository launch packet containing:

1. AWS account and identity screenshots or exports with sensitive values protected.
2. IAM/access inventory and date of review.
3. Resource inventory by region and project tag.
4. Data-flow diagram from vendor socket to retained journal to BOSS to execution adapters.
5. DTN/CME written use and AWS-hosting confirmation.
6. tastytrade and Kalshi account/API approvals.
7. Secrets and key-rotation procedure.
8. Incident, kill, recovery, and reconciliation runbooks.
9. Budget thresholds and named alert recipient.
10. Hashes of deployed code, model, configuration, and policy artifacts.

Any change to subscriber identity, human access, data consumers, venue use, account organization, or redistribution requires an explicit review of that packet.

## Go/no-go checklist

The AWS account is acceptable for the Frankie proof of capability when all answers are yes:

- Is the actual account ID known and the `DavisAI` label no longer being used as identity proof?
- Are primary contact, billing, payment, and tax details correct for the actual subscriber?
- Is the user the only natural person with access to or use of licensed market data?
- Are all IAM identities and active resources inventoried?
- Is HomeLift confirmed dormant or cleanly separated?
- Are root MFA, CloudTrail, budget alarms, encryption, and least privilege active?
- Are market-data and broker secrets separated from Granite and general agents?
- Has the data supplier approved the AWS topology, retention, and automated use in writing?
- Can order permission be revoked immediately without destroying the data/audit plane?
- Can the runtime be reconstructed from hash-bound artifacts without exposing secrets?

## Lock

Do not rename or replace the AWS account merely to make it look personal. First establish the true billing/contact/tax identity and the actual single-user topology. Keep `DavisAI` if it is an accurate, convenient display label and vendors accept the disclosed use. Use a separate account or entity only if the audit reveals conflicting ownership, shared consumers, material HomeLift coupling, or a vendor requires it.
