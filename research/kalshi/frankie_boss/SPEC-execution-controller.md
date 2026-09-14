# Execution controller: pinned evidence and durable outbox composition

## Scope

`execution_controller.py` joins existing deterministic execution policy, ledger
and typed Kalshi/tastytrade adapters. It implements the controller seam described
by `SPEC-execution-controls.md` and the ChatGPT live-stack document
`05_PERSONAL_AUTOMATED_EXECUTION_AND_LICENSING.md` (Execution architecture lock,
Before any outbound request, Retry and idempotency, Operational controls).

No network client, account parser, credential/signing/refresh mechanism, strategy,
new risk formula, cancellation or environment-promotion operation is added.
Tests inject fake transports only. The controller supports the environments
already defined by policy (`replay`, `shadow`, `sandbox`, `paper`, `live`) when
the independently configured authority, policy, account and adapter agree.
Selecting an environment string does not itself authorize account access/orders.

## Trust boundary

All expected hashes are **independently caller-trusted**, not derived from an
untrusted incoming object inside the controller. The caller must obtain them
from the actual approved configuration/evidence authority. Fixture tests pin
synthetic objects directly; those fixtures are not production trust setup.

`ExecutionAuthority` pins exact account/environment, policy, registry, adapter,
source, valuation, account issuer/convention and transport capability identities.
It consumes upstream authority; it is not another production artifact registry.
The injected callable's `transport_hash` is a caller-attested capability identity,
not a cryptographic verification of Python code or provider authentication.
Binding the actual configured transport to that capability is the host's job.

`AccountEvidence` binds the existing complete AccountSnapshot to an issuer,
position/P&L/reflection convention and nonempty retained witness bytes. Checking
these hashes proves byte identity and consistent claimed authority, not actual
provider completeness, position truth or validity of the valuation convention.
No missing exposure, P&L, fill or page is replaced by zero.

`ReflectionEvidence` independently binds one exact parsed OrderFact to one exact
AccountEvidence, issuer/convention and positions_match assertion with witness
bytes. The caller supplies its separately expected digest. The controller never
sets positions_match from an order response, equal IDs or matching clocks.
False/mismatched reflection refuses and keeps exposure unresolved.

## Public operations

Construct `ExecutionController(ledger=..., store=..., authority=...,
expected_authority_hash=..., pin=...)` around the existing single-writer
ExecutionLedger and an immutable ReceiptStore. Adapter pin must be exact
KalshiPin/TastytradePin and match authority/account.

1. `prepare(inputs, account_evidence, *, expected_account_evidence_hash)` checks
   full typed inputs and authority, selects one registered instrument, reuses
   `translate`, persists the exact prepared envelope and returns PreparedExecution.
   It performs no ledger state transition or send. ExecutionInputs contains the
   existing intent/policy/registry/source/valuation/market and explicit loss_day.
2. `dispatch_once(prepared, *, expected_prepared_hash, transport, transport_hash,
   now, preflight_receipt=None, expected_preflight_hash=None)` re-admits exact
   prepared identity and bytes. Tastytrade requires a separately pinned successful
   existing dry-run receipt for the same wire/account; Kalshi refuses extra
   preflight inputs. Sample `now()` **after** preflight validation/retention and
   check that preflight receipt falls inside intent creation/send clocks.
   Create the intent idempotently, then delegate approval/send to the existing
   ledger's dispatch_once. The ledger owns reservations and kill state and runs
   policy again at the send boundary. No earlier decision authorizes send.
3. The injected transport receives exact WireRequest and returns TransportReceipt.
   The controller retains the complete envelope before parsing, including HTTP
   status, source, account, wire identity, receive clock and original body. It
   returns raw body to the ledger and uses existing parse_order_response.
   DispatchResult binds prepared/receipt/fact hashes and the receipt locator.
   **Even a valid acknowledgement leaves the ledger SENT_UNKNOWN** until separately
   admitted account/reflection evidence is supplied. No implicit position match.
4. `ingest_order_observation(prepared, *, expected_prepared_hash, receipt,
   expected_receipt_hash, expected_source, account_evidence,
   expected_account_evidence_hash, reflection, expected_reflection_hash)` requires
   the exact durably attempted ledger intent/wire, retains full reconciliation
   evidence, reuses the existing parser/observation builder, verifies reflection
   pins and account scope/unit/causal-clock coverage, then calls ledger.reconcile.
   Terminal release uses the typed account snapshot whose digest is bound by the
   independently admitted AccountEvidence. Deterministic observation ID is the
   complete reflection digest. The result reports current status and trusted
   checkpoint, separately from the reconcile boolean. A repeated older observation
   may no longer validate against current state; it is not a new historical claim.
5. `admit_account_successor(account_evidence, *, expected_account_evidence_hash)`
   retains and validates evidence, then delegates to ledger.reflect_account;
   existing causal frontier and reflected-intent preservation stay authoritative.

## Receipt storage, uncertainty and recovery

ReceiptStore writes exact tagged `pack` JSON bytes under SHA256 content filenames
using exclusive creation, file flush/fsync and exact readback. POSIX also fsyncs
the directory; Windows file metadata durability remains subject to the platform.
Any partial/conflicting file fails closed. Store reads require a trusted digest;
symlink entries are refused. Preserve this evidence directory and caller-held
locators together with the ledger and independent checkpoints.

The evidence store and ledger are **not** one transaction. No second order state
machine or reservation authority exists. Before outbound I/O the ledger has
already durably recorded SENT_UNKNOWN. A timeout, malformed reply, post-send
receipt-storage failure or uncertain journal write retains uncertainty/reservation
and invokes the independent persistent kill latch. An unavailable/poisoned journal
is not evidence that no send happened. Original exceptions, including process
control, propagate; latch durability errors are chained rather than reported as
provider outcomes. A kill cannot recall already transmitted bytes.

If persistence fails before send, no transport callback runs. A success receipt
is not returned until its complete envelope, parsed identity and checkpoint-bound
result have been retained. On recovery, reopen the ledger using independently
trusted checkpoint and retained kill marker. Supply independently pinned later
order/account observations if needed; never resend an intent with an existing
wire, clear kill automatically, infer HTTP errors mean REJECTED, or release risk
from absent account evidence. Missing receipt bytes remain missing evidence.

The host must preserve returned result/checkpoint identities externally. This
slice provides no automatic polling, lookup, background recovery or trusted-root
distribution service. A returned account hash alone is never authentication.

## Verification and remaining work

Focused command (Windows PYTHONPATH is repository root, this package and tests):

`python -m pytest -q research/kalshi/frankie_boss/tests/test_execution_policy.py
research/kalshi/frankie_boss/tests/test_execution_ledger.py
research/kalshi/frankie_boss/tests/test_execution_adapters.py
research/kalshi/frankie_boss/tests/test_execution_controller.py`

Tests cover both venues, explicit supported environments, independent account and
reflection pins, exact transport-envelope retention, no implicit reconciliation,
terminal release/replay, causal account successors, post-preflight policy refusal,
timeouts/no resend, malformed HTTP/body/source/account clocks, evidence corruption,
disk failures before/after send, poisoned RETURN journal writes, process-control
exceptions and independent kill while transport remains in flight. Every transport
is synthetic. Actual provider behavior/authentication remains unproved.

Combined execution verification: **211 passed in 25.86 seconds** (39 new
controller cases plus the existing 172 policy/ledger/adapter cases), no failures
or skips. The first account/dispatch and reflection test batches failed against
the absent interfaces before implementation; separate red/green regressions
covered supported environments and the poisoned-journal error/kill path.

The next operational increments must bind an actual approved transport and source
of complete account/position/P&L/valuation/reflection evidence, secrets/signing and
refresh, query pagination, monitoring and clock drift, cancel/flatten contracts,
provider sandbox/recovery drills and explicit production promotion. Unsupported
Expired/cancel-replace/multi-leg/reduce-only semantics still refuse under the
existing adapter/ledger contracts; this controller does not silently translate them.
