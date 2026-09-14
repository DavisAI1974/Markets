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
independently pinned implementation identity, not proof about a Python callable. There is
no built-in network client or environment/file secret discovery in this slice. No token cache
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
must remain green. Concrete TLS client, account discovery and complete account collection
are explicit next seams and are not claimed complete here.
