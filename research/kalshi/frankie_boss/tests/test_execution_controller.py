"""Controller acceptance with synthetic evidence and zero provider clients."""
from dataclasses import replace
import pytest

from test_execution_adapters import venue_fixture, receipt, kalshi_create_body, tasty_submit_body
from test_execution_policy import H
from research.kalshi.frankie_boss.execution_ledger import ExecutionLedger
from research.kalshi.frankie_boss.execution_controller import (
    AccountEvidence, ExecutionAuthority, ExecutionInputs, ReceiptStore, ExecutionController,
)


def setup_controller(tmp_path, venue='kalshi'):
    args, instrument, pin = venue_fixture(venue)
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
