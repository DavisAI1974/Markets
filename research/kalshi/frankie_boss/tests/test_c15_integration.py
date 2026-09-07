"""Synthetic integration checks against the unchanged V4 book implementation."""
import copy
import math

import pytest

from causal_prefix import ScopeKind
from causal_prefix_records import RecordPrefixChain
from c15_dstate import ReceiptDChain
from test_causal_prefix_records import record, scope, member, SHA_A


def test_probe_d_consumer_binds_real_probe_chain_and_rejects_result_path():
    chain = RecordPrefixChain(scope(kind=ScopeKind.PROBE_ONLY))
    receipt = chain.advance(record(0, instrument=1, sequence=1, last=True))
    consumer = ReceiptDChain(chain, instrument_id=1, publisher_id=1,
                             tick_raw=1, builder_code_sha="a" * 40)
    args = dict(session_id="s", anchor_dir=1, far_best_price_raw=10,
                book_integrity=True)
    with pytest.raises(ValueError):
        consumer.advance(receipt, **args)
    out = consumer.advance_probe(receipt, **args)
    assert out.receipt_hash == receipt.receipt_hash
    assert out.output.columns[0].value == 0
    foreign = RecordPrefixChain(scope(kind=ScopeKind.PROBE_ONLY))
    forged = foreign.advance(record(0, instrument=1, sequence=2, last=True))
    with pytest.raises(ValueError):
        chain.validate_probe(forged)


def test_d_receipt_checkpoint_preserves_fractional_geometry_and_binding():
    chain = RecordPrefixChain(scope(kind=ScopeKind.PROBE_ONLY))
    args = dict(instrument_id=1, publisher_id=1, tick_raw=2,
                builder_code_sha="a" * 40)
    machine = ReceiptDChain(chain, **args)
    for i, price in enumerate((20, 18, 23)):
        receipt = chain.advance(record(i, instrument=1, sequence=i, last=True))
        machine.advance_probe(receipt, session_id="s", anchor_dir=1,
                              far_best_price_raw=price, book_integrity=True)
    state = machine.export_state()
    restored = ReceiptDChain.restore(chain, state, **args)
    receipt = chain.advance(record(3, instrument=1, sequence=3, last=True))
    obs = dict(session_id="s", anchor_dir=1, far_best_price_raw=21,
               book_integrity=True)
    assert machine.advance_probe(receipt, **obs) == restored.advance_probe(receipt, **obs)
    damaged = copy.deepcopy(state)
    damaged["machine"]["ordinal"] += 1
    with pytest.raises(ValueError):
        ReceiptDChain.restore(chain, damaged, **args)
