# Explicit authentication and ready transport

Additive ChatGPT05 software slice, September 14, 2026. All acceptance uses generated keys,
synthetic secrets and injected fake HTTP. No credentials were resolved from a real secret
store, no provider request was made and no account permission or live execution is certified.

## Composition

1. Independently approve a `TransportCapability` digest as the controller authority's
   `transport_hash`. It pins account/environment, adapter digest (including Kalshi
   subaccount), exact official origin, credential reference/version, HTTP implementation
   identity, User-Agent, timeout, short ready lifetime and expiry margin.
2. Prepare the controller's immutable wire, then call `prepare_transport` with the
   independently expected capability and HTTP identity, explicit secret provider and clock.
   This resolves secrets and loads a Kalshi key or completes one tastytrade refresh.
3. For tastytrade call the lease's `preflight()` once, retain and independently pin its
   returned `TransportReceipt`, then pass it into the existing controller. Preflight
   interpretation and retained failure evidence remain the controller's responsibility.
4. Call `controller.dispatch_once(..., transport=ready, transport_hash=ready.digest, now=...)`.
   Its final policy clock occurs after all secret resolution, key loading, OAuth and dry-run
   work. For Kalshi, the sender signs the current request timestamp with the already loaded
   key immediately before HTTP, then rechecks the lease/clock after local signing. It never
   re-resolves credentials or refreshes OAuth inside submission.
   Every order response, including 401/429/5xx/3xx, is returned as raw typed evidence.
   No response causes automatic refresh or resubmission.

The ready object binds one exact WireRequest and supports one order attempt, protected by
a lock. Only the existing durable ledger establishes no-resend across process restarts.
The lease is not an alternative order authority. Unknown responses continue to retain
reservations and latch the controller kill; account observations/reflection stay separate.

## Boundaries and sources

- Kalshi `live` and `sandbox` map exactly to `external-api.kalshi.com` and
  `external-api.demo.kalshi.co`. No silent legacy host fallback. These application environment
  names correspond to provider production/demo. [Official environments](https://docs.kalshi.com/getting_started/api_environments).
- Kalshi signatures are base64 RSA-PSS with SHA256, MGF1 SHA256 and digest-length salt.
  The signed string is millisecond timestamp + uppercase method + full path without query.
  The narrow sender allows only the adapter's exact POST route, with no query.
  [Signature contract](https://docs.kalshi.com/getting_started/api_keys),
  [Create-order V2](https://docs.kalshi.com/api-reference/orders/create-order-v2),
  [Cryptography RSA API](https://cryptography.io/en/46.0.3/hazmat/primitives/asymmetric/rsa/).
- tastytrade `live` and `sandbox` map exactly to `api.tastyworks.com` and
  `api.cert.tastyworks.com`. The OAuth JSON exchange requests `trade` scope using
  `refresh_token` and `client_secret`. Every request has product/version User-Agent.
  `/sessions` is not used. The refresh section guarantees an access token and 15-minute
  lifetime but does not explicitly require `expires_in`/`token_type`; missing fields use
  900 seconds/Bearer. Present lifetime must be a positive exact integer and is capped at
  900 seconds. Expiry starts before secret resolution/request, subtracts the configured
  margin (at least the HTTP timeout), and is also capped by the 30-second ready lifetime.
  This conservative local lifetime is not a JWT validity claim. Present scope must contain
  trade. Credentials, token scopes and account ownership still need operational validation.
  [Official OAuth contract](https://developer.tastytrade.com/docs/authentication/oauth2/).

Only live/sandbox have an actual documented HTTP origin; replay/shadow/paper remain usable
with other explicit controller capabilities, not silently routed to production by this
provider transport. This is a route mapping boundary, not a controller replay-only gate.

## Trust and secrets

The injected HTTP implementation must perform exactly one exchange, verify TLS certificates
and hostname, enforce the supplied timeout, disable redirects/retries/proxies unless separately
approved, and not log request headers/body or auth responses. Its digest is a caller's
independently pinned implementation identity, not proof about a Python callable. Concrete
opt-in providers are described below; there is no environment/file secret discovery. No token cache
or concurrent refresh coordinator is added: each explicit preparation performs one exchange;
the same prepared lease can then support the dry-run and submission without refreshing.

Secret containers and ready leases are opaque, excluded from Contract serialization and have
redacted repr. Exceptions at the injected boundary expose only fixed messages; cancellation
types remain cancellation with blank messages. Auth responses are never returned as evidence.
Known credential echoes in order bodies fail before generic receipt retention; their outcome
is uncertain and must be reconciled. This check is defense in depth, not a defense against an
actively malicious approved backend encoding secrets. Python memory/debugger access and a
backend that logs secrets remain outside this module's isolation. Do not serialize HTTP
callback arguments, traceback locals or private object slots.

Exact response URL is checked; redirects must already be disabled by the HTTP implementation.
POST bodies are passed unchanged. No global HTTP client, installation, proxy settings,
automatic retry, refresh-and-resend or account-risk conversion is introduced.

Install the optional pinned `requirements-execution-transport.txt` in the runtime selected
for this slice; training and existing deployment lockfiles are intentionally untouched.

## Acceptance

Focused tests verify generated signatures and query exclusion; official origin/account/path
and HTTP identity refusal before secret resolution; malformed/failed refresh and expiry;
single-use concurrency; raw error receipts, redirect refusal and secret-echo refusal;
sanitized timeout/cancellation; controller final policy expiry and durable SENT_UNKNOWN/kill
across reopen with no second send. Existing execution policy/ledger/adapters/controller tests
must remain green. Account discovery and complete account collection remain next seams.

## Concrete opt-in providers (continuation)

`execution_providers.HTTPSExchange(origin=..., max_response_bytes=...)` implements
the HTTP callable with Python's standard-library HTTPSConnection. The explicit origin must
be one of the existing official live/sandbox origins and must match every request exactly.
Constructing a provider does no I/O. Compose it with `prepare_transport`; retain the
independently approved implementation hash in the capability. That approval must cover
provider source, Python/TLS runtime and trust-store configuration, response limit and origin;
the hash argument by itself does not authenticate a callable or the machine running it.

The client verifies TLS certificates and hostnames using the runtime's default trust store,
explicitly disables HTTP debug output, uses direct connections (no environment proxy
discovery), and makes one request on one fresh connection. It does not follow redirects or
retry any status/exception. Bytes are passed unchanged; non-success statuses are returned
as raw evidence. Invalid framing/truncation, excessive response size and transport failure
fail closed through sanitized exceptions. The default body budget is 4 MiB, configurable up
to 16 MiB; overflow produces uncertainty, never a truncated successful receipt.

The deadline includes local TLS-context preparation and connection establishment. After
connect, a watchdog shuts down the connected socket when the remaining budget expires,
including slow response headers/body. The request is refused if connection establishment
has already exhausted that budget. OS DNS resolution cannot be interrupted by this Python
socket timeout; it may delay return, but an expired connect cannot subsequently transmit.
Hard process-return deadlines need an external runtime boundary and existing durable
SENT_UNKNOWN/reconciliation handling. This is not a certified hard-real-time client.

ReadyTransport now passes the smaller of the capability timeout and whole milliseconds
remaining on its lease to the HTTP callable. Less than one millisecond remaining refuses
before HTTP. OAuth preparation retains the original capability timeout. This prevents a
slow concrete connect from extending an almost-expired ready lease into order transmission.

`FileSecretProvider(reference=..., path=...)` implements the secret callable for one exact
public CredentialReference and absolute local file path. The private JSON envelope contains
exactly `credential_hash` (the public reference digest) and `secrets`. Kalshi secrets contain
exactly `key_id` and `private_key_pem` (PEM text); tastytrade secrets contain exactly
`refresh_token` and `client_secret`. Duplicate/unknown fields, wrong bindings, non-string
values, symlinks, non-regular files and files exceeding 64 KiB are refused. There is no
implicit file discovery, credential provisioning, rotation, or secret-content hashing.
Known errors are redacted; provider repr omits paths and references.

The operator must provision that file outside Git and apply private ACLs to it and its
parent directories. This adapter does not enforce Windows ACL policy, encrypt storage,
prevent privileged process inspection, authenticate rotation history, or claim account
ownership. The envelope binds declared public identity; file access/placement is trusted
configuration. A managed vault remains a separate optional deployment choice.

Acceptance uses synthetic file secrets, fake connections and a generated-certificate
loopback TLS server. It covers refusal before connection, actual byte preservation and
redirect retention, slow-response interruption, truncated body refusal, exact secret
binding, and ready-lease connect expiry with zero order transmissions and no reuse.
No real credentials, venue requests or operational account acceptance occurred.

Implementation sources: [Python HTTPSConnection](https://docs.python.org/3/library/http.client.html)
and [default TLS context](https://docs.python.org/3/library/ssl.html#ssl.create_default_context).
