"""Synthetic cancel-once controls; real ledger, fake venue callback only."""
from dataclasses import replace
import json
import pytest
from test_execution_controller import setup_controller, prepared_for, send_kalshi
from test_execution_adapters import receipt, kalshi_create_body, RECEIVED
from test_execution_policy import H
from research.kalshi.frankie_boss.execution_ledger import ExecutionLedger
from research.kalshi.frankie_boss.execution_controller import ExecutionController
from research.kalshi.frankie_boss.execution_cancel_contracts import CancelAuthorization, CancelIntent
from research.kalshi.frankie_boss.execution_cancel import CancellationController, CANCEL_SCHEMA_SHA256
S=1_000_000_000


def setup_cancel(tmp_path):
    c,ledger,inputs,account,pin=setup_controller(tmp_path)
    original=prepared_for(c,inputs,account)
    target=receipt(original.wire,inputs.intent.account,'kalshi.create_order',kalshi_create_body(original.wire))
    send_kalshi(c,original,lambda _:target)
    auth=CancelAuthorization(inputs.intent.account,c.authority.digest,pin.digest,H,H,CANCEL_SCHEMA_SHA256,12*S,20*S,5*S)
    cancel=CancellationController(c,auth,expected_authorization_hash=auth.digest)
    control=CancelIntent('cancel/1',inputs.intent.intent_id,inputs.intent.digest,original.wire.digest,
        inputs.intent.account,'ord-1',original.wire.client_id,target.digest,auth.digest,12*S,19*S)
    prepared=cancel.prepare(control,expected_control_hash=control.digest,original=original,
        expected_original_hash=original.digest,target_receipt=target,expected_target_receipt_hash=target.digest)
    return c,ledger,cancel,prepared


def response(prepared, **changes):
    body=dict(order_id='ord-1',client_order_id=prepared.wire.client_id,reduced_by='2.00',ts_ms=14000)
    body.update(changes)
    return receipt(prepared.wire,prepared.control.account,'kalshi.cancel_order',json.dumps(body).encode(),received_ns=15*S)


def send(cancel, prepared, transport=None, now=13*S):
    return cancel.dispatch_once(prepared,expected_prepared_hash=prepared.digest,
        transport=transport or (lambda _:response(prepared)),transport_hash=H,now=lambda:now)


def test_cancel_after_kill_is_once_and_ack_never_releases_reservation(tmp_path):
    c,ledger,cancel,prepared=setup_cancel(tmp_path)
    try:
        before=ledger.state(prepared.control.original_intent_id)
        ledger.latch_kill('synthetic operator kill')
        calls=[]
        def transport(wire):
            calls.append(wire)
            assert ledger.cancellation(prepared.control.control_id)['returned'] is False
            return response(prepared)
        result=send(cancel,prepared,transport)
        assert result['acknowledgement']['reduced_quantity']==2
        assert len(calls)==1 and ledger.state(prepared.control.original_intent_id)==before
        assert len(ledger.reservations())==1
        with pytest.raises(ValueError):send(cancel,prepared,lambda _:pytest.fail('duplicate cancel'))
    finally:ledger.close()


@pytest.mark.parametrize('fault',['timeout','404','wrong_order','wrong_client','bad_quantity','future_clock','duplicate_json'])
def test_ambiguous_cancel_never_releases_or_resends_on_restart(tmp_path,fault):
    c,ledger,cancel,prepared=setup_cancel(tmp_path)
    def transport(_):
        if fault=='timeout':raise TimeoutError('synthetic remote outcome unknown')
        if fault=='404':return replace(response(prepared),http_status=404)
        if fault=='wrong_order':return response(prepared,order_id='another')
        if fault=='wrong_client':return response(prepared,client_order_id='another')
        if fault=='bad_quantity':return response(prepared,reduced_by='3.00')
        if fault=='future_clock':return response(prepared,ts_ms=16000)
        return replace(response(prepared),body=b'{"order_id":"ord-1","order_id":"other"}')
    with pytest.raises((ValueError,TimeoutError)):send(cancel,prepared,transport)
    assert ledger.killed and len(ledger.reservations())==1
    checkpoint=ledger.checkpoint();ledger.close()
    restored=ExecutionLedger(tmp_path/'orders.sqlite',checkpoint=checkpoint)
    try:
        c2=ExecutionController(ledger=restored,store=c.store,authority=c.authority,expected_authority_hash=c.authority.digest,pin=c.pin)
        cancel2=CancellationController(c2,cancel.authorization,expected_authorization_hash=cancel.authorization.digest)
        changed=replace(prepared.control,control_id='cancel/bypass')
        p2=cancel2.prepare(changed,expected_control_hash=changed.digest,original=prepared.original,
            expected_original_hash=prepared.original.digest,target_receipt=prepared.target_receipt,
            expected_target_receipt_hash=prepared.target_receipt.digest)
        with pytest.raises(ValueError):send(cancel2,p2,lambda _:pytest.fail('new ID resent cancel'))
        assert restored.killed and len(restored.reservations())==1
    finally:restored.close()


@pytest.mark.parametrize('fault',['expired','future','stale_target','transport_pin','prepared_pin','target_pin','original_wire'])
def test_invalid_control_never_calls_transport(tmp_path,fault):
    c,ledger,cancel,prepared=setup_cancel(tmp_path)
    try:
        if fault in ('expired','future','stale_target'):
            clock={'expired':19*S,'future':11*S,'stale_target':18*S}[fault]
            with pytest.raises(ValueError):send(cancel,prepared,lambda _:pytest.fail('invalid timing sent'),now=clock)
        elif fault in ('transport_pin','prepared_pin'):
            with pytest.raises(ValueError):cancel.dispatch_once(prepared,expected_prepared_hash='b'*64 if fault=='prepared_pin' else prepared.digest,
                transport=lambda _:pytest.fail('invalid pin sent'),transport_hash='b'*64 if fault=='transport_pin' else H,now=lambda:13*S)
        else:
            control=prepared.control
            if fault=='original_wire':control=replace(control,submitted_wire_hash='b'*64)
            with pytest.raises(ValueError):cancel.prepare(control,expected_control_hash=control.digest,original=prepared.original,
                expected_original_hash=prepared.original.digest,target_receipt=prepared.target_receipt,
                expected_target_receipt_hash='b'*64 if fault=='target_pin' else prepared.target_receipt.digest)
        assert ledger.cancellation(prepared.control.control_id) is None
        assert len(ledger.reservations())==1
    finally:ledger.close()


def test_cancel_journal_uncertain_before_send_does_not_call_transport(tmp_path,monkeypatch):
    c,ledger,cancel,prepared=setup_cancel(tmp_path)
    original=ledger.journal.append
    def fail(kind,payload):
        if payload['step']=='CANCEL_ATTEMPT':
            original(kind,payload)
            raise OSError('synthetic commit acknowledgement lost')
        return original(kind,payload)
    monkeypatch.setattr(ledger.journal,'append',fail)
    try:
        with pytest.raises(OSError):send(cancel,prepared,lambda _:pytest.fail('uncertain journal sent'))
        assert ledger.killed
        with pytest.raises(ValueError):send(cancel,prepared,lambda _:pytest.fail('poisoned resend'))
    finally:ledger.close()


def test_cancel_receipt_storage_failure_latches_and_preserves_reservation(tmp_path,monkeypatch):
    c,ledger,cancel,prepared=setup_cancel(tmp_path)
    original=c.store.put
    def fail(payload):
        if payload.get('kind')=='cancel_response':raise OSError('synthetic full disk')
        return original(payload)
    monkeypatch.setattr(c.store,'put',fail)
    try:
        with pytest.raises(OSError):send(cancel,prepared)
        assert ledger.killed and len(ledger.reservations())==1
        with pytest.raises(ValueError):send(cancel,prepared,lambda _:pytest.fail('lost receipt resend'))
    finally:ledger.close()


def test_standalone_prepare_storage_failure_stops_new_exposure(tmp_path,monkeypatch):
    c,ledger,cancel,prepared=setup_cancel(tmp_path)
    def fail(_):raise OSError('synthetic preparation disk failure')
    monkeypatch.setattr(c.store,'put',fail)
    try:
        with pytest.raises(OSError):cancel.prepare(prepared.control,expected_control_hash=prepared.control.digest,
            original=prepared.original,expected_original_hash=prepared.original.digest,
            target_receipt=prepared.target_receipt,expected_target_receipt_hash=prepared.target_receipt.digest)
        assert ledger.killed and len(ledger.reservations())==1
        assert ledger.cancellation(prepared.control.control_id) is None
    finally:ledger.close()


def test_target_freshness_caps_actual_cancel_wire_lease(tmp_path):
    c,ledger,cancel,prepared=setup_cancel(tmp_path)
    try:
        assert prepared.wire.expires_ns==RECEIVED+cancel.authorization.max_target_age_ns+1
        assert prepared.wire.expires_ns<prepared.control.expires_ns
    finally:ledger.close()


def test_process_control_exception_consumes_cancel_target_across_restart(tmp_path):
    c,ledger,cancel,prepared=setup_cancel(tmp_path)
    def interrupt(_):raise KeyboardInterrupt('synthetic cancel interruption')
    with pytest.raises(KeyboardInterrupt):send(cancel,prepared,interrupt)
    assert ledger.killed and len(ledger.reservations())==1
    checkpoint=ledger.checkpoint();ledger.close()
    restored=ExecutionLedger(tmp_path/'orders.sqlite',checkpoint=checkpoint)
    try:
        assert restored.cancellation(prepared.control.control_id)['error_type']=='KeyboardInterrupt'
        with pytest.raises(ValueError):restored.cancel_once(control=prepared.control,authorization=cancel.authorization,
            wire=prepared.wire,target_received_ns=prepared.target_receipt.received_ns,now=13*S,
            sender=lambda _:pytest.fail('interrupted target resent'))
        assert restored.killed and len(restored.reservations())==1
    finally:restored.close()


def test_wrong_schema_authorization_is_rejected_and_stops(tmp_path):
    c,ledger,cancel,prepared=setup_cancel(tmp_path)
    try:
        wrong=replace(cancel.authorization,schema_hash='b'*64)
        with pytest.raises(ValueError):CancellationController(c,wrong,expected_authorization_hash=wrong.digest)
        assert ledger.killed
    finally:ledger.close()
