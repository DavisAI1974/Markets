"""Controller acceptance with synthetic evidence and zero provider clients."""
from dataclasses import replace
import pytest

from test_execution_adapters import (venue_fixture, receipt, kalshi_create_body, tasty_submit_body,
    kalshi_order_body, tasty_order, RECEIVED)
from test_execution_policy import H
from research.kalshi.frankie_boss.execution_ledger import ExecutionLedger
from research.kalshi.frankie_boss.execution_controller import (
    AccountEvidence, ExecutionAuthority, ExecutionInputs, ReceiptStore, ExecutionController, ReflectionEvidence,
)
from research.kalshi.frankie_boss.execution_adapters import parse_order_response
import json


def setup_controller(tmp_path, venue='kalshi', environment='replay'):
    args, instrument, pin = venue_fixture(venue)
    key = replace(args['intent'].account, environment=environment)
    pin = replace(pin, account=key)
    args['policy'] = replace(args['policy'], allowed_accounts=(key,), trusted_adapters=(pin.digest,))
    args['intent'] = replace(args['intent'], account=key, policy_hash=args['policy'].digest, adapter_hash=pin.digest)
    args['account'] = replace(args['account'], account=key)
    authority = ExecutionAuthority(args['intent'].account, args['policy'].digest,
        args['registry'].digest, pin.digest, args['source'].digest, args['valuation'].digest,
        H, H, H)
    account = AccountEvidence(args['account'], H, H, (b'synthetic complete account witness',))
    inputs = ExecutionInputs(args['intent'], args['policy'], args['registry'], args['source'],
        args['valuation'], args['market'], args['loss_day'])
    ledger = ExecutionLedger(tmp_path/'orders.sqlite', create=True)
    store = ReceiptStore(tmp_path/'receipts')
    controller = ExecutionController(ledger=ledger, store=store, authority=authority,
        expected_authority_hash=authority.digest, pin=pin)
    return controller, ledger, inputs, account, pin


def test_account_witness_and_external_pin_required(tmp_path):
    c, ledger, inputs, account, pin = setup_controller(tmp_path)
    try:
        with pytest.raises(ValueError, match='pin'):
            c.prepare(inputs, account, expected_account_evidence_hash='b'*64)
        changed = replace(account, witnesses=(b'other bytes',))
        with pytest.raises(ValueError, match='pin'):
            c.prepare(inputs, changed, expected_account_evidence_hash=account.digest)
        with pytest.raises(ValueError):
            replace(account, witnesses=())
        prepared = c.prepare(inputs, account, expected_account_evidence_hash=account.digest)
        assert prepared.wire.adapter_hash == pin.digest
        assert ledger.checkpoint()['count'] == 0
    finally:
        ledger.close()


def test_complete_receipt_bytes_survive_store_reopen_and_tamper_refuses(tmp_path):
    store = ReceiptStore(tmp_path/'receipts')
    payload = dict(raw=b'\x00bad JSON', source='synthetic', status=503)
    key = store.put(payload)
    assert ReceiptStore(tmp_path/'receipts').get(key) == payload
    assert store.put(payload) == key
    (tmp_path/'receipts'/key).write_bytes(b'changed')
    with pytest.raises(ValueError):
        store.get(key)
    with pytest.raises(ValueError):
        store.put(payload)


def test_policy_denial_has_no_callback_and_preserves_evidence(tmp_path):
    c, ledger, inputs, account, pin = setup_controller(tmp_path)
    try:
        prepared = c.prepare(inputs, account, expected_account_evidence_hash=account.digest)
        with pytest.raises(ValueError):
            c.dispatch_once(prepared, expected_prepared_hash=prepared.digest,
                transport=lambda _: pytest.fail('must not send'), transport_hash=H, now=lambda: 20)
        assert ledger.state(inputs.intent.intent_id)['wire'] is None
    finally:
        ledger.close()


def prepared_for(c, inputs, account):
    return c.prepare(inputs, account, expected_account_evidence_hash=account.digest)


def send_kalshi(c, prepared, transport=None):
    response = receipt(prepared.wire, prepared.inputs.intent.account, 'kalshi.create_order',
        kalshi_create_body(prepared.wire))
    return c.dispatch_once(prepared, expected_prepared_hash=prepared.digest,
        transport=transport or (lambda _: response), transport_hash=H, now=lambda: 10)


def terminal_evidence(c, prepared, account, status='executed', fill='2.00'):
    response = receipt(prepared.wire, prepared.inputs.intent.account, 'kalshi.get_order',
        kalshi_order_body(prepared.wire, status=status, fill=fill, remaining='0.00'))
    fact = parse_order_response(response, intent=prepared.inputs.intent, wire=prepared.wire,
        pin=c.pin, expected_source=response.source)
    snapshot = replace(account.snapshot, observed_ns=RECEIVED, pnl_observed_ns=RECEIVED,
        reflected_intents=(prepared.inputs.intent.intent_id,),
        exposures=tuple(replace(e, gross=4, net_min=4, net_max=4) for e in account.snapshot.exposures))
    account = replace(account, snapshot=snapshot)
    reflection = ReflectionEvidence(fact.digest, account.digest, H, H, True, (b'independent synthetic reflection',))
    return response, account, reflection


def ingest(c, prepared, response, account, reflection):
    return c.ingest_order_observation(prepared, expected_prepared_hash=prepared.digest,
        receipt=response, expected_receipt_hash=response.digest, expected_source=response.source,
        account_evidence=account, expected_account_evidence_hash=account.digest,
        reflection=reflection, expected_reflection_hash=reflection.digest)


def test_actual_policy_outbox_and_terminal_evidence_release_across_restore(tmp_path):
    c, ledger, inputs, account, pin = setup_controller(tmp_path)
    prepared = prepared_for(c, inputs, account)
    calls = []
    def transport(wire):
        assert ledger.state(inputs.intent.intent_id)['status'] == 'SENT_UNKNOWN'
        calls.append(wire)
        return receipt(wire, inputs.intent.account, 'kalshi.create_order', kalshi_create_body(wire))
    sent = send_kalshi(c, prepared, transport)
    retained = c.store.get(sent.receipt_locator)['value']
    assert retained['http_status'] == 201 and retained['source'] == 'kalshi.create_order'
    assert ledger.state(inputs.intent.intent_id)['status'] == 'SENT_UNKNOWN'
    response, reflected, proof = terminal_evidence(c, prepared, account)
    result = ingest(c, prepared, response, reflected, proof)
    assert result.accepted and result.status == 'FILLED'
    assert ledger.reservations() == ()
    checkpoint = ledger.checkpoint()
    assert ingest(c, prepared, response, reflected, proof).accepted
    assert ledger.checkpoint() == checkpoint
    ledger.close()
    restored = ExecutionLedger(tmp_path/'orders.sqlite', checkpoint=checkpoint)
    c2 = ExecutionController(ledger=restored, store=c.store, authority=c.authority,
        expected_authority_hash=c.authority.digest, pin=pin)
    try:
        with pytest.raises(ValueError):
            send_kalshi(c2, prepared, lambda _: pytest.fail('resend'))
        assert restored.reservations() == () and len(calls) == 1
    finally:
        restored.close()


@pytest.mark.parametrize('mutation', ['snapshot', 'fact', 'issuer', 'convention', 'positions', 'witness'])
def test_no_inferred_account_reflection_and_no_release_on_bad_proof(tmp_path, mutation):
    c, ledger, inputs, account, pin = setup_controller(tmp_path)
    try:
        prepared = prepared_for(c, inputs, account)
        send_kalshi(c, prepared)
        response, reflected, proof = terminal_evidence(c, prepared, account)
        changes = {'snapshot': dict(account_evidence_hash='b'*64), 'fact': dict(fact_hash='b'*64),
            'issuer': dict(issuer_hash='b'*64), 'convention': dict(convention_hash='b'*64),
            'positions': dict(positions_match=False), 'witness': dict(witnesses=(b'changed',))}
        changed = replace(proof, **changes[mutation])
        with pytest.raises(ValueError):
            c.ingest_order_observation(prepared, expected_prepared_hash=prepared.digest,
                receipt=response, expected_receipt_hash=response.digest, expected_source=response.source,
                account_evidence=reflected, expected_account_evidence_hash=reflected.digest,
                reflection=changed, expected_reflection_hash=proof.digest if mutation=='witness' else changed.digest)
        assert ledger.reservations() and ledger.killed
    finally:
        ledger.close()


def test_timeout_remains_unknown_and_no_recovery_resend(tmp_path):
    c, ledger, inputs, account, pin = setup_controller(tmp_path)
    prepared = prepared_for(c, inputs, account)
    def timeout(_):
        raise TimeoutError('synthetic')
    with pytest.raises(TimeoutError):
        send_kalshi(c, prepared, timeout)
    checkpoint = ledger.checkpoint()
    ledger.close()
    restored = ExecutionLedger(tmp_path/'orders.sqlite', checkpoint=checkpoint)
    c = ExecutionController(ledger=restored, store=c.store, authority=c.authority,
        expected_authority_hash=c.authority.digest, pin=pin)
    try:
        assert restored.killed and restored.reservations()
        with pytest.raises(ValueError):
            send_kalshi(c, prepared, lambda _: pytest.fail('resend'))
        response, reflected, proof = terminal_evidence(c, prepared, account)
        assert ingest(c, prepared, response, reflected, proof).accepted
        assert restored.killed  # reconciliation does not clear the independent kill latch
    finally:
        restored.close()


@pytest.mark.parametrize('venue', ['kalshi', 'tastytrade'])
def test_both_venue_returns_are_evidence_not_implicit_reconciliation(tmp_path, venue):
    c, ledger, inputs, account, pin = setup_controller(tmp_path, venue)
    try:
        prepared = prepared_for(c, inputs, account)
        kwargs = {}
        if venue == 'tastytrade':
            preflight = receipt(prepared.wire, inputs.intent.account, 'tastytrade.dry_run',
                json.dumps(dict(data=dict(order=tasty_order(prepared.wire), warnings=[], errors=[]))).encode(),
                received_ns=9)
            kwargs = dict(preflight_receipt=preflight, expected_preflight_hash=preflight.digest)
        source = 'kalshi.create_order' if venue == 'kalshi' else 'tastytrade.submit_order'
        body = kalshi_create_body(prepared.wire) if venue == 'kalshi' else tasty_submit_body(prepared.wire)
        result = c.dispatch_once(prepared, expected_prepared_hash=prepared.digest,
            transport=lambda wire: receipt(wire, inputs.intent.account, source, body),
            transport_hash=H, now=lambda: 10, **kwargs)
        assert c.store.get(result.receipt_locator)['value']['body'] == body
        assert ledger.state(inputs.intent.intent_id)['status'] == 'SENT_UNKNOWN'
        assert len(ledger.reservations()) == 1
    finally:
        ledger.close()


@pytest.mark.parametrize('mode', ['missing', 'wrong_pin', 'warnings', 'expired_after_preflight'])
def test_tastytrade_preflight_cannot_bypass_final_policy(tmp_path, mode):
    c, ledger, inputs, account, pin = setup_controller(tmp_path, 'tastytrade')
    try:
        prepared = prepared_for(c, inputs, account)
        preflight = receipt(prepared.wire, inputs.intent.account, 'tastytrade.dry_run',
            json.dumps(dict(data=dict(order=tasty_order(prepared.wire), warnings=['w'] if mode=='warnings' else [],
                errors=[]))).encode(), received_ns=9)
        kwargs = {} if mode=='missing' else dict(preflight_receipt=preflight,
            expected_preflight_hash='b'*64 if mode=='wrong_pin' else preflight.digest)
        with pytest.raises(ValueError):
            c.dispatch_once(prepared, expected_prepared_hash=prepared.digest,
                transport=lambda _: pytest.fail('preflight or policy must deny'), transport_hash=H,
                now=lambda: 20 if mode=='expired_after_preflight' else 10, **kwargs)
        assert not ledger.reservations()
    finally:
        ledger.close()


@pytest.mark.parametrize('mutation', ['json', 'source', 'account', 'clock', 'http'])
def test_malformed_post_send_envelope_retained_and_kills(tmp_path, mutation):
    c, ledger, inputs, account, pin = setup_controller(tmp_path)
    try:
        prepared = prepared_for(c, inputs, account)
        response = receipt(prepared.wire, inputs.intent.account, 'kalshi.create_order', kalshi_create_body(prepared.wire))
        change = {'json': dict(body=b'<html>failure</html>'), 'source': dict(source='kalshi.get_order'),
            'account': dict(account=replace(inputs.intent.account, account_id='other')),
            'clock': dict(received_ns=1), 'http': dict(http_status=503)}
        response = replace(response, **change[mutation])
        with pytest.raises(ValueError):
            send_kalshi(c, prepared, lambda _: response)
        assert ledger.killed and ledger.reservations()
        envelopes = [c.store.get(p.name) for p in c.store.path.iterdir()]
        assert any(e.get('kind')=='transport' and e['value']['body']==response.body for e in envelopes)
    finally:
        ledger.close()


@pytest.mark.parametrize('when', ['prepared', 'transport', 'dispatch_result'])
def test_receipt_persistence_failure_preserves_send_boundary(tmp_path, when, monkeypatch):
    c, ledger, inputs, account, pin = setup_controller(tmp_path)
    calls = []
    real_put = c.store.put
    def fail(payload):
        if payload['kind'] == when:
            raise OSError('synthetic disk full')
        return real_put(payload)
    try:
        prepared = prepared_for(c, inputs, account)
        monkeypatch.setattr(c.store, 'put', fail)
        def transport(wire):
            calls.append(wire)
            return receipt(wire, inputs.intent.account, 'kalshi.create_order', kalshi_create_body(wire))
        with pytest.raises(OSError):
            send_kalshi(c, prepared, transport)
        assert len(calls) == (0 if when=='prepared' else 1)
        if calls:
            assert ledger.killed and ledger.reservations()
            assert ledger.state(inputs.intent.intent_id)['status'] == 'SENT_UNKNOWN'
    finally:
        ledger.close()


def test_account_frontier_requires_all_reflected_intents_and_causal_clock(tmp_path):
    c, ledger, inputs, account, pin = setup_controller(tmp_path)
    try:
        prepared = prepared_for(c, inputs, account)
        send_kalshi(c, prepared)
        response, reflected, proof = terminal_evidence(c, prepared, account)
        ingest(c, prepared, response, reflected, proof)
        checkpoint = ledger.checkpoint()
        for changed in (replace(reflected.snapshot, reflected_intents=()),
                replace(reflected.snapshot, pnl_observed_ns=1)):
            wrong = replace(reflected, snapshot=changed)
            with pytest.raises(ValueError):
                c.admit_account_successor(wrong, expected_account_evidence_hash=wrong.digest)
            assert ledger.checkpoint() == checkpoint
        successor = replace(reflected, snapshot=replace(reflected.snapshot,
            observed_ns=RECEIVED+1, pnl_observed_ns=RECEIVED+1))
        assert c.admit_account_successor(successor, expected_account_evidence_hash=successor.digest)['count'] > checkpoint['count']
    finally:
        ledger.close()


@pytest.mark.parametrize('environment', ['replay', 'shadow', 'sandbox', 'paper', 'live'])
def test_explicitly_pinned_environment_uses_fake_transport_without_promotion(tmp_path, environment):
    c, ledger, inputs, account, pin = setup_controller(tmp_path, environment=environment)
    try:
        prepared = prepared_for(c, inputs, account)
        assert send_kalshi(c, prepared).prepared_hash == prepared.digest
        assert ledger.state(inputs.intent.intent_id)['status'] == 'SENT_UNKNOWN'
        wrong = replace(account, snapshot=replace(account.snapshot,
            account=replace(account.snapshot.account, environment='other')))
        with pytest.raises(ValueError, match='authority'):
            c.prepare(inputs, wrong, expected_account_evidence_hash=wrong.digest)
    finally:
        ledger.close()


def test_process_control_exception_propagates_with_uncertainty_retained(tmp_path):
    c, ledger, inputs, account, pin = setup_controller(tmp_path)
    try:
        prepared = prepared_for(c, inputs, account)
        def interrupted(_):
            raise KeyboardInterrupt()
        with pytest.raises(KeyboardInterrupt):
            send_kalshi(c, prepared, interrupted)
        assert ledger.killed and ledger.reservations()
    finally:
        ledger.close()


def test_uncertain_ledger_return_write_still_latches_and_preserves_original_error(tmp_path, monkeypatch):
    c, ledger, inputs, account, pin = setup_controller(tmp_path)
    prepared = prepared_for(c, inputs, account)
    real_append = ledger.journal.append
    def fail_return(kind, payload):
        if payload['step'] == 'RETURN':
            raise OSError('synthetic uncertain journal write')
        return real_append(kind, payload)
    monkeypatch.setattr(ledger.journal, 'append', fail_return)
    try:
        with pytest.raises(OSError, match='uncertain journal'):
            send_kalshi(c, prepared)
        assert (tmp_path/'orders.sqlite.kill').is_file()
    finally:
        ledger.close()
