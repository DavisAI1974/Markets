"""Host-invoked heartbeat and signed-clock supervision using the existing kill latch.

Pins and producer/convention identities are independently trusted by the host.
A healthy sample is telemetry, never dispatch permission or account truth.
"""
from dataclasses import asdict, dataclass

from .execution_contracts import Contract, _unique
from .execution_controller import ExecutionController, _pin

SCHEMA = 'BOSS_EXECUTION_SUPERVISION_V1'


@dataclass(frozen=True)
class SessionWatch(Contract):
    session_id: str
    kind: str
    producer_hash: str
    clock_convention_hash: str
    max_heartbeat_age_ns: int
    max_clock_offset_ns: int

    def __post_init__(self):
        super().__post_init__()
        if self.kind not in ('market_data', 'execution'):
            raise ValueError('declared market_data or execution session required')
        if self.max_heartbeat_age_ns <= 0:
            raise ValueError('positive operator heartbeat age required')


@dataclass(frozen=True)
class SupervisionPolicy(Contract):
    authority_hash: str
    host_clock_hash: str
    sessions: tuple[SessionWatch, ...]

    def __post_init__(self):
        super().__post_init__()
        if not self.sessions:
            raise ValueError('complete nonempty watched session roster required')
        _unique(tuple(s.session_id for s in self.sessions), 'watched session')


@dataclass(frozen=True)
class HeartbeatEvidence(Contract):
    session_id: str
    producer_hash: str
    clock_convention_hash: str
    observed_ns: int
    clock_offset: int  # signed nanoseconds under the pinned convention
    witnesses: tuple[bytes, ...]

    def __post_init__(self):
        super().__post_init__()
        if not self.witnesses or any(not w for w in self.witnesses):
            raise ValueError('retained heartbeat witness bytes required')


class ExecutionSupervisor:
    """No background thread, journal ownership, order transition or kill clearing.

    The host must call check at its approved cadence and before dispatch, provide
    a clock bound to policy.host_clock_hash, and retain returned receipt locators.
    The independent latch can operate while a provider send holds the ledger lock.
    """
    def __init__(self, controller, policy, *, expected_policy_hash):
        if type(controller) is not ExecutionController:
            raise ValueError('existing execution controller required')
        self.controller = controller
        self.policy, self.expected_policy_hash = policy, expected_policy_hash
        try:
            self._validate_policy()
        except BaseException as original:
            self._stop(original)
            raise

    def _validate_policy(self):
        if type(self.policy) is not SupervisionPolicy:
            raise ValueError('typed supervision policy required')
        _pin(self.policy, self.expected_policy_hash)
        _pin(self.controller.authority, self.controller.expected_authority_hash)
        if self.policy.authority_hash != self.controller.authority.digest:
            raise ValueError('supervision execution authority differs')

    def _stop(self, original):
        try:
            self.controller.ledger.latch_kill('execution supervision failed')
        except BaseException as latch_error:
            raise original from latch_error

    def check(self, samples, *, expected_sample_hashes, now):
        """Revalidate exact evidence; stop on faults or unavailable supervision.

        Missing sessions produce an alarm receipt. Invalid identity/pins, clock
        or storage errors latch kill and propagate, never return a healthy result.
        No ledger checkpoint is read: it may be busy or poisoned during dispatch.
        """
        try:
            self._validate_policy()
            if type(samples) is not tuple or type(expected_sample_hashes) is not tuple:
                raise ValueError('immutable samples and independent pin tuples required')
            if len(samples) != len(expected_sample_hashes):
                raise ValueError('one independent pin per supplied sample required')
            watches = {w.session_id: w for w in self.policy.sessions}
            seen = {}
            for sample, expected in zip(samples, expected_sample_hashes):
                if type(sample) is not HeartbeatEvidence:
                    raise ValueError('typed heartbeat evidence required')
                _pin(sample, expected)
                if sample.session_id not in watches or sample.session_id in seen:
                    raise ValueError('unexpected or duplicate heartbeat session')
                watch = watches[sample.session_id]
                if (sample.producer_hash != watch.producer_hash or
                        sample.clock_convention_hash != watch.clock_convention_hash):
                    raise ValueError('heartbeat producer or clock convention differs')
                seen[sample.session_id] = sample
            observed_now = now()
            if type(observed_now) is not int or observed_now < 0:
                raise ValueError('nonnegative integer host clock required')
            reasons = []
            for watch in self.policy.sessions:
                sample = seen.get(watch.session_id)
                if sample is None:
                    reasons.append('heartbeat_missing:' + watch.session_id)
                    continue
                age = observed_now - sample.observed_ns
                if age < 0:
                    reasons.append('heartbeat_future:' + watch.session_id)
                elif age > watch.max_heartbeat_age_ns:
                    reasons.append('heartbeat_stale:' + watch.session_id)
                if abs(sample.clock_offset) > watch.max_clock_offset_ns:
                    reasons.append('clock_drift:' + watch.session_id)
            latch = None
            if reasons:
                # Latch before store I/O, independent of the order/journal lock.
                latch = self.controller.ledger.latch_kill('execution supervision alarm')
            receipt = dict(schema=SCHEMA, policy_hash=self.policy.digest,
                authority_hash=self.policy.authority_hash, host_clock_hash=self.policy.host_clock_hash,
                observed_ns=observed_now, policy=asdict(self.policy),
                samples=tuple(asdict(s) for s in samples), sample_hashes=expected_sample_hashes,
                reasons=tuple(reasons), signals_healthy=not reasons,
                kill_latched=self.controller.ledger.killed, latch=latch)
            locator = self.controller.store.put(receipt)
            return dict(signals_healthy=receipt['signals_healthy'],
                        kill_latched=receipt['kill_latched'], receipt_locator=locator)
        except BaseException as original:
            self._stop(original)
            raise
