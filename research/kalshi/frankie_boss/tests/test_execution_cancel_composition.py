"""Real cancellation controller/ledger/auth composition; synthetic transport only."""
import base64
from dataclasses import asdict, replace
import json
import sqlite3
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from test_execution_controller import setup_controller, prepared_for, send_kalshi
from test_execution_adapters import receipt, kalshi_create_body
from test_execution_policy import H
from research.kalshi.frankie_boss.c15_journal import unpack
from research.kalshi.frankie_boss.execution_auth import CredentialReference, KalshiSecrets
from research.kalshi.frankie_boss.execution_cancel import CancellationController, CANCEL_SCHEMA_SHA256
from research.kalshi.frankie_boss.execution_cancel_contracts import CancelAuthorization, CancelIntent
from research.kalshi.frankie_boss.execution_cancel_transport import CancelTransportCapability, prepare_cancel_transport
from research.kalshi.frankie_boss.execution_controller import ExecutionController
from research.kalshi.frankie_boss.execution_ledger import ExecutionLedger
from research.kalshi.frankie_boss.execution_providers import HTTPSExchange
from research.kalshi.frankie_boss.execution_transport import HTTPResponse, TransportError

S = 1000000000


def composed(tmp_path):
    controller, ledger, inputs, account, pin = setup_controller(tmp_path, environment='sandbox')
    original = prepared_for(controller, inputs, account)
    target = receipt(original.wire, pin.account, 'kalshi.create_order', kalshi_create_body(original.wire))
    send_kalshi(controller, original, lambda _: target)
    ref = CredentialReference(pin.account, 'synthetic-local-reference', 'v1')
    cap = CancelTransportCapability(pin.account, pin.digest, ref,
        'https://external-api.demo.kalshi.co', H, 'frankie-test/1', 1000, 30*S, S)
    auth = CancelAuthorization(pin.account, controller.authority.digest, pin.digest, cap.digest,
        H, CANCEL_SCHEMA_SHA256, 12*S, 20*S, 5*S)
    cancel = CancellationController(controller, auth, expected_authorization_hash=auth.digest)
    control = CancelIntent('cancel-composed/1', inputs.intent.intent_id, inputs.intent.digest,
        original.wire.digest, pin.account, 'ord-1', original.wire.client_id, target.digest,
        auth.digest, 12*S, 19*S)
    prepared = cancel.prepare(control, expected_control_hash=control.digest, original=original,
        expected_original_hash=original.digest, target_receipt=target, expected_target_receipt_hash=target.digest)
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                            serialization.NoEncryption())
    return controller, ledger, cancel, prepared, cap, key, KalshiSecrets('synthetic-key', pem)


def ready_for(prepared, controller, cap, secret, http, now):
    return prepare_cancel_transport(wire=prepared.wire, pin=controller.pin, capability=cap,
        expected_capability_hash=cap.digest, expected_http_hash=cap.http_hash,
        resolve_secret=lambda _: secret, http=http, now=now)


def assert_committed_attempt(tmp_path, ledger, prepared):
    state = ledger.cancellation(prepared.control.control_id)
    assert state['returned'] is False and state['error_type'] is None
    # Separate read-only SQLite connection proves the write-ahead event is committed.
    connection = sqlite3.connect((tmp_path/'orders.sqlite').as_uri() + '?mode=ro', uri=True)
    try:
        body = connection.execute('SELECT body FROM entries ORDER BY ordinal DESC LIMIT 1').fetchone()[0]
    finally:
        connection.close()
    event = unpack(json.loads(body))['payload']
    assert event['step'] == 'CANCEL_ATTEMPT'
    assert event['payload']['wire'] == asdict(prepared.wire)


@pytest.mark.parametrize('timeout', [False, True])
def test_authenticated_controller_attempt_ack_or_timeout_then_restart_no_resend(tmp_path, timeout):
    c, ledger, cancel, prepared, cap, key, secret = composed(tmp_path)
    clock, calls = [13*S], []
    before = ledger.state(prepared.control.original_intent_id)
    def http(**kwargs):
        assert_committed_attempt(tmp_path, ledger, prepared)
        calls.append(kwargs)
        assert kwargs['method'] == 'DELETE' and kwargs['body'] == b''
        assert kwargs['url'] == cap.origin + prepared.wire.path
        assert kwargs['retries'] == 0 and kwargs['follow_redirects'] is False
        headers = kwargs['headers']
        key.public_key().verify(base64.b64decode(headers['KALSHI-ACCESS-SIGNATURE']),
            ('13000DELETE' + prepared.wire.path.split('?')[0]).encode(),
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH), hashes.SHA256())
        assert headers['KALSHI-ACCESS-TIMESTAMP'] == '13000'
        if timeout:
            raise TimeoutError('synthetic timeout')
        clock[0] = 15*S
        body = json.dumps(dict(order_id='ord-1', client_order_id=prepared.wire.client_id,
            reduced_by='2.00', ts_ms=14000)).encode()
        return HTTPResponse(200, body, kwargs['url'])
    ready = ready_for(prepared, c, cap, secret, http, lambda: clock[0])
    try:
        if timeout:
            with pytest.raises(TransportError):
                cancel.dispatch_once(prepared, expected_prepared_hash=prepared.digest,
                    transport=ready, transport_hash=ready.digest, now=lambda: clock[0])
            assert ledger.killed
        else:
            result = cancel.dispatch_once(prepared, expected_prepared_hash=prepared.digest,
                transport=ready, transport_hash=ready.digest, now=lambda: clock[0])
            assert result['acknowledgement']['reduced_quantity'] == 2
            assert result['reservation_release'] is False
        assert len(calls) == 1 and ledger.state(prepared.control.original_intent_id) == before
        assert len(ledger.reservations()) == 1
        checkpoint = ledger.checkpoint()
    finally:
        ledger.close()
    restored = ExecutionLedger(tmp_path/'orders.sqlite', checkpoint=checkpoint)
    try:
        c2 = ExecutionController(ledger=restored, store=c.store, authority=c.authority,
            expected_authority_hash=c.authority.digest, pin=c.pin)
        cancel2 = CancellationController(c2, cancel.authorization,
            expected_authorization_hash=cancel.authorization.digest)
        changed = replace(prepared.control, control_id='cancel-composed/bypass')
        p2 = cancel2.prepare(changed, expected_control_hash=changed.digest, original=prepared.original,
            expected_original_hash=prepared.original.digest, target_receipt=prepared.target_receipt,
            expected_target_receipt_hash=prepared.target_receipt.digest)
        retry_calls = []
        def retry_http(**kwargs):
            retry_calls.append(kwargs)
            return HTTPResponse(500, b'{}', kwargs['url'])
        ready2 = ready_for(p2, c2, cap, secret, retry_http, lambda: clock[0])
        with pytest.raises(ValueError):
            cancel2.dispatch_once(p2, expected_prepared_hash=p2.digest,
                transport=ready2, transport_hash=ready2.digest, now=lambda: clock[0])
        assert len(restored.reservations()) == 1 and len(calls) == 1 and retry_calls == []
    finally:
        restored.close()


def test_controller_target_age_deadline_prevents_concrete_delete_after_slow_connect(tmp_path, monkeypatch):
    c, ledger, cancel, prepared, cap, _, secret = composed(tmp_path)
    assert prepared.wire.expires_ns == prepared.target_receipt.received_ns + cancel.authorization.max_target_age_ns + 1
    assert prepared.wire.expires_ns < prepared.control.expires_ns < cancel.authorization.expires_ns
    clock, monotonic, connections, transmissions = [13*S], [0.0], [], []
    class Connection:
        def __init__(self, host, **kwargs):
            connections.append(kwargs)
            self.sock = self
        def set_debuglevel(self, level):
            assert level == 0
        def connect(self):
            assert_committed_attempt(tmp_path, ledger, prepared)
            monotonic[0] += .003
            clock[0] = prepared.wire.expires_ns + 1
        def settimeout(self, seconds):
            pass
        def shutdown(self, how):
            pass
        def request(self, *args, **kwargs):
            transmissions.append(args)
            pytest.fail('DELETE transmitted after target freshness expired')
        def close(self):
            pass
    monkeypatch.setattr('http.client.HTTPSConnection', Connection)
    monkeypatch.setattr('research.kalshi.frankie_boss.execution_providers.time.monotonic', lambda: monotonic[0])
    ready = ready_for(prepared, c, cap, secret, HTTPSExchange(origin=cap.origin), lambda: clock[0])
    clock[0] = prepared.wire.expires_ns - 2_000_000
    try:
        with pytest.raises(TransportError):
            cancel.dispatch_once(prepared, expected_prepared_hash=prepared.digest,
                transport=ready, transport_hash=ready.digest, now=lambda: clock[0])
        assert len(connections) == 1 and connections[0]['timeout'] <= .002
        assert transmissions == [] and ledger.killed and len(ledger.reservations()) == 1
        assert ledger.cancellation(prepared.control.control_id)['error_type'] == 'TransportError'
    finally:
        ledger.close()
