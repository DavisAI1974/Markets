# Execution heartbeat and clock supervision

`execution_supervision.py` implements the heartbeat and signed-clock-drift portion
of the operational controls in live-stack document 05. It reuses the existing
controller, receipt store and independent durable kill latch. It creates no order
state, reservation authority, provider client, scheduler or background thread.

## Operator contract

Construct `ExecutionSupervisor(controller, policy, expected_policy_hash=...)`.
The independently trusted `SupervisionPolicy` binds the controller's exact
ExecutionAuthority, host-clock identity, and the complete nonempty session roster.
Each SessionWatch binds a unique actual session-instance ID, kind (`market_data`
or `execution`), producer identity, clock-convention identity, positive maximum
heartbeat age, and nonnegative maximum absolute clock offset. All durations and
clock offsets use integer nanoseconds; no thresholds are selected by software.
The caller attests roster completeness. A new session/clock epoch requires an
appropriate new independently approved policy, never a fabricated matching ID.

Invoke `check(samples, expected_sample_hashes=..., now=...)` with exact immutable
HeartbeatEvidence objects and one independently trusted digest per supplied sample.
Each sample retains producer/convention identity, heartbeat observation time in
the declared host clock domain, signed clock offset under that convention, and
nonempty original witness bytes. `now()` must be the host's trusted clock bound
to policy.host_clock_hash, in the same domain/epoch as sample observation times.
The callable and evidence issuer are host-attested capabilities; matching hashes
do not authenticate a clock, heartbeat producer, signature or provider service.
Checks evaluate only the supplied snapshot. There is no persisted observation
frontier or independent clock-attestation service: a rolled-back host clock paired
with older still-pinned samples can pass. The host must establish clock integrity,
monotonicity where required and replay/epoch handling; a hash does not prove these.
Only put non-secret operational evidence in these local retained witnesses.

At the approved cadence, and before calling the existing controller dispatch:

1. Revalidate policy, authority and all supplied independent sample pins.
2. Detect missing, stale or future heartbeat observations and absolute clock-offset
   violations. Exactly equal age/offset thresholds pass; signed offsets are valid.
3. On any alarm, latch the existing kill marker before receipt storage. No journal
   checkpoint/state call is made while the provider may hold the execution lock.
4. Retain full typed telemetry, pins, policy, reasons and latch result through
   ReceiptStore, returning its locator plus signals_healthy/kill_latched flags.
5. Invalid pins/identity/types, clock errors or storage errors also latch kill and
   propagate the original error; latch durability errors remain chained. Invalid
   evidence does not yield a successful receipt. A write failure leaves no claimed
   successful supervision result; the marker remains independent of the store.

A healthy sample does not clear any kill marker or authorize dispatch. Dispatch
still checks policy, account/evidence freshness and the existing kill latch at its
own boundary. The monitor's telemetry flags are snapshots, not reusable permits.
Healthy telemetry can coexist with kill_latched=true after a prior alarm.

## Alarm handling and local recovery drill

The operational questions answered are: Which declared session is missing/stale?
Did a pinned signed clock offset exceed the operator limit? Was the kill durable?
Where are the exact policy and witness bytes for the decision?

For heartbeat_missing/stale/future or clock_drift, stop new exposure, retain the
receipt locator, inspect the relevant session/clock producer and its original
witnesses, and investigate the configured convention and thresholds. If check
raises, investigate the independent pins, host clock, receipt storage and durable
kill marker; unavailable monitoring is not a healthy session.

After any in-flight sender exits, the ledger owner can capture its authoritative
checkpoint. Preserve that checkpoint, database, receipt directory and kill marker
and reopen with the independently retained checkpoint. Existing SENT_UNKNOWN
intent/reservation state remains unresolved. Obtain real independently admitted
account/order/reflection evidence through the existing reconciliation path. Never
resend the old wire, release reservations from a heartbeat, delete the marker or
clear kill automatically. These tests exercise that local sequence with fake I/O.
They do not establish venue sandbox acceptance or an operational recovery approval.

## Remaining host and operational work

The host must schedule and supervise this check at an approved cadence, supply
actual session/clock witnesses and independent authority, and route its results to
operators. If the host stops invoking check, this module cannot detect elapsed time
on its own. External watchdog deployment/cadence and genuine clock measurement
remain operational inputs. No position/P&L drift formula, feed-gap convention,
reject-burst/risk-proximity thresholds, cancel-all, flatten, environment promotion,
credential refresh, provider polling or actual session operation is invented here.
No Sunday, market-data acquisition, model training or venue order is launched.
