"""Synthetic heartbeat/clock supervision; no provider or session is opened."""
from dataclasses import replace
import threading
import pytest
from test_execution_controller import setup_controller, prepared_for, send_kalshi
from test_execution_policy import H
from research.kalshi.frankie_boss.execution_controller import ExecutionController
from research.kalshi.frankie_boss.execution_ledger import ExecutionLedger
from research.kalshi.frankie_boss.execution_supervision import SessionWatch, HeartbeatEvidence, SupervisionPolicy, ExecutionSupervisor


def fixture(tmp_path):
    c, ledger, inputs, account, pin = setup_controller(tmp_path)
    watches = (SessionWatch('feed', 'market_data', H, H, 5, 2),
               SessionWatch('orders', 'execution', H, H, 5, 2))
    policy = SupervisionPolicy(c.authority.digest, H, watches)
    monitor = ExecutionSupervisor(c, policy, expected_policy_hash=policy.digest)
    samples = tuple(HeartbeatEvidence(w.session_id, w.producer_hash, w.clock_convention_hash,
                                     9, 0, (b'synthetic heartbeat witness',)) for w in watches)
    return c, ledger, inputs, account, policy, monitor, samples


def check(monitor, samples, now=10):
    return monitor.check(samples, expected_sample_hashes=tuple(s.digest for s in samples), now=lambda: now)


def test_healthy_check_retains_exact_samples_and_existing_dispatch_is_authoritative(tmp_path):
    c, ledger, inputs, account, policy, monitor, samples = fixture(tmp_path)
    try:
        result = check(monitor, samples)
        assert result['signals_healthy'] and not result['kill_latched']
        receipt = c.store.get(result['receipt_locator'])
        assert receipt['policy_hash'] == policy.digest
        assert receipt['sample_hashes'] == tuple(s.digest for s in samples)
        assert receipt['samples'][0]['witnesses'] == samples[0].witnesses
        prepared = prepared_for(c, inputs, account)
        send_kalshi(c, prepared)
        assert ledger.state(inputs.intent.intent_id)['status'] == 'SENT_UNKNOWN'
        assert len(ledger.reservations()) == 1
    finally: ledger.close()


@pytest.mark.parametrize('fault,reason', [('missing','heartbeat_missing:orders'),
    ('stale','heartbeat_stale:feed'), ('future','heartbeat_future:feed'),
    ('positive','clock_drift:feed'), ('negative','clock_drift:feed')])
def test_fault_latches_before_dispatch_and_survives_restart(tmp_path, fault, reason):
    c, ledger, inputs, account, policy, monitor, samples = fixture(tmp_path)
    prepared = prepared_for(c, inputs, account)
    if fault == 'missing': samples = samples[:1]
    elif fault == 'stale': samples = (replace(samples[0], observed_ns=4), samples[1])
    elif fault == 'future': samples = (replace(samples[0], observed_ns=11), samples[1])
    else: samples = (replace(samples[0], clock_offset=3 if fault=='positive' else -3), samples[1])
    result = check(monitor, samples)
    assert reason in c.store.get(result['receipt_locator'])['reasons']
    assert result['kill_latched'] and not result['signals_healthy']
    with pytest.raises(ValueError): send_kalshi(c, prepared, lambda _: pytest.fail('sent despite kill'))
    checkpoint = ledger.checkpoint(); ledger.close()
    restored = ExecutionLedger(tmp_path/'orders.sqlite', checkpoint=checkpoint)
    try:
        assert restored.killed
        c2 = ExecutionController(ledger=restored, store=c.store, authority=c.authority,
            expected_authority_hash=c.authority.digest, pin=c.pin)
        m2 = ExecutionSupervisor(c2, policy, expected_policy_hash=policy.digest)
        healthy = tuple(HeartbeatEvidence(w.session_id,H,H,10,0,(b'synthetic recovered heartbeat',)) for w in policy.sessions)
        result = check(m2, healthy)
        assert result['signals_healthy'] and result['kill_latched']
        with pytest.raises(ValueError): send_kalshi(c2, prepared, lambda _: pytest.fail('recovery unlocked'))
    finally: restored.close()


@pytest.mark.parametrize('fault', ['pin', 'producer', 'convention', 'extra', 'duplicate', 'invalid_clock'])
def test_invalid_supervision_evidence_also_fails_closed(tmp_path, fault):
    c, ledger, inputs, account, policy, monitor, samples = fixture(tmp_path)
    try:
        if fault == 'producer': samples = (replace(samples[0],producer_hash='b'*64),samples[1])
        elif fault == 'convention': samples = (replace(samples[0],clock_convention_hash='b'*64),samples[1])
        elif fault == 'extra': samples += (replace(samples[0],session_id='undeclared'),)
        elif fault == 'duplicate': samples += samples[:1]
        kwargs = dict(expected_sample_hashes=tuple(s.digest for s in samples),now=lambda:10)
        if fault == 'pin': kwargs['expected_sample_hashes']=('b'*64,)*len(samples)
        if fault == 'invalid_clock': kwargs['now']=lambda:True
        with pytest.raises(ValueError): monitor.check(samples, **kwargs)
        assert ledger.killed
    finally: ledger.close()


def test_threshold_edges_and_negative_clock_offset_are_supported(tmp_path):
    c, ledger, inputs, account, policy, monitor, samples = fixture(tmp_path)
    try:
        samples = (replace(samples[0], observed_ns=5, clock_offset=-2),replace(samples[1], clock_offset=2))
        assert check(monitor, samples)['signals_healthy']
    finally: ledger.close()


def test_receipt_failure_cannot_delay_kill_or_claim_success(tmp_path, monkeypatch):
    c, ledger, inputs, account, policy, monitor, samples = fixture(tmp_path)
    def fail(_):
        assert ledger.killed
        raise OSError('synthetic storage failure')
    monkeypatch.setattr(c.store,'put',fail)
    try:
        with pytest.raises(OSError): check(monitor, samples[:1])
        assert ledger.killed
    finally: ledger.close()


def test_kill_during_blocked_send_retains_reservation_and_never_resends(tmp_path):
    c, ledger, inputs, account, policy, monitor, samples = fixture(tmp_path)
    prepared = prepared_for(c,inputs,account)
    completed = threading.Event(); errors=[]; calls=[]
    def stop():
        try:
            result = check(monitor, samples[:1])
            assert result['kill_latched']
        except BaseException as exc: errors.append(exc)
        finally: completed.set()
    def transport(wire):
        calls.append(wire)
        thread=threading.Thread(target=stop);thread.start()
        assert completed.wait(5), 'supervision waited for blocked provider operation'
        thread.join(5)
        assert not errors
        raise TimeoutError('synthetic provider outcome unknown')
    with pytest.raises(TimeoutError): send_kalshi(c,prepared,transport)
    assert len(calls)==1 and len(ledger.reservations())==1
    checkpoint=ledger.checkpoint();ledger.close()
    restored=ExecutionLedger(tmp_path/'orders.sqlite',checkpoint=checkpoint)
    try:
        c2=ExecutionController(ledger=restored,store=c.store,authority=c.authority,
            expected_authority_hash=c.authority.digest,pin=c.pin)
        assert restored.killed and len(restored.reservations())==1
        with pytest.raises(ValueError):send_kalshi(c2,prepared,lambda _:pytest.fail('resend'))
        assert len(restored.reservations())==1
    finally:restored.close()


@pytest.mark.parametrize('fault', ['policy_pin', 'authority', 'clock_raises', 'healthy_store_failure', 'missing_pins'])
def test_unavailable_supervision_never_returns_healthy(tmp_path, monkeypatch, fault):
    c, ledger, inputs, account, policy, monitor, samples = fixture(tmp_path)
    try:
        if fault == 'policy_pin':
            with pytest.raises(ValueError): ExecutionSupervisor(c,policy,expected_policy_hash='b'*64)
        elif fault == 'authority':
            wrong=replace(policy,authority_hash='b'*64)
            with pytest.raises(ValueError): ExecutionSupervisor(c,wrong,expected_policy_hash=wrong.digest)
        elif fault == 'clock_raises':
            def unavailable():raise OSError('synthetic clock unavailable')
            with pytest.raises(OSError): monitor.check(samples,expected_sample_hashes=tuple(s.digest for s in samples),now=unavailable)
        elif fault == 'healthy_store_failure':
            def unavailable(_):raise OSError('synthetic receipt storage unavailable')
            monkeypatch.setattr(c.store,'put',unavailable)
            with pytest.raises(OSError):check(monitor,samples)
        else:
            with pytest.raises(ValueError):monitor.check(samples,expected_sample_hashes=(),now=lambda:10)
        assert ledger.killed
    finally:ledger.close()


def test_negative_clock_offset_limit_is_rejected():
    with pytest.raises(ValueError, match='negative'):
        SessionWatch('feed','market_data',H,H,5,-1)
