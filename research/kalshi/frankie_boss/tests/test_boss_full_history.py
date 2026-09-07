"""Regression proofs for the owner-directed removal of evidence reductions."""
import math

import pytest
import torch

from causal_packet import CausalWindow, PacketBuilder, Record, FeatureSpec
from databento_adapter import DatabentoMBOSource, MBORow
from trunk import FieldEncoder, Trunk, TrunkConfig


class Source:
    name = 'mbo'

    def __init__(self, rows):
        self.rows = rows

    def fetch(self, entity, as_of):
        return self.rows

    def watermark(self, entity, as_of):
        return as_of


def packet(rows, specs=()):
    return PacketBuilder([Source(rows)], specs).build('ES', 10, 'm', 'c')


def test_all_versions_and_partial_rows_reach_feature_and_packet():
    rows = [Record('order', 1, 1, {'order_id': 2**60 + 1, 'size': 3}),
            Record('order', 1, 2, {'order_id': 2**60 + 1}, version=1)]
    p = packet(rows, [FeatureSpec('raw', '2', lambda w: {
        'size': w.values('mbo', 'size'), 'id': w.values('mbo', 'order_id')})])
    assert p.features == {'raw.size': (3, None), 'raw.id': (2**60 + 1, 2**60 + 1)}
    assert p.source_records['mbo'] == tuple(rows)
    assert p.record_counts == {'mbo': 2}
    assert p.resolved_record_counts == {'mbo': 1}
    assert CausalWindow(10, {'mbo': rows}).latest_records('mbo') == (rows[-1],)


def test_raw_last_bit_and_signed_zero_change_packet_identity():
    def one(value):
        return packet([Record('a', 1, 1, {'px': value})])
    assert one(1.0).hash != one(math.nextafter(1.0, 2.0)).hash
    assert one(0.0).hash != one(-0.0).hash
    assert one(1).hash != one(1.0).hash


def test_received_skewed_rows_count_and_defects_reach_packet_without_future_leak():
    rows = [MBORow('a', 2, 5, 7, {'order_id': 2**60 + 1})]
    src = DatabentoMBOSource('mbo', lambda _: rows)
    build = lambda: PacketBuilder([src], []).build('ES', 3, 'm', 'c')
    p = build()
    assert p.record_counts == {'mbo': 1}
    assert p.source_records['mbo'][0].event_time == 5
    assert p.source_records['mbo'][0].ingest_time == 2
    assert p.degraded and 'retained' in p.degraded[0]
    rows.append(MBORow('future', 20, 21, 0, {'secret': 1}))
    assert build().hash == p.hash


def config(**kwargs):
    return TrunkConfig(d_model=8, n_heads=2, n_layers=1, n_numeric=2,
                       categorical_cardinalities=(3,), use_delta_memory=False, **dict(dict(use_qsv=True), **kwargs))


def test_explicit_complete_attention_uses_rows_beyond_128_and_remains_causal():
    torch.manual_seed(47)
    c = config(window=None)
    assert c.window is None and c.use_qsv
    model = Trunk(c).eval()
    t = 140
    numeric = torch.randn(1, t, 2, requires_grad=True)
    inputs = dict(numeric=numeric, categorical=torch.zeros(1, t, 1, dtype=torch.long),
                  venue_id=torch.zeros(1, t, dtype=torch.long),
                  instrument_id=torch.zeros(1, t, dtype=torch.long),
                  parent=torch.full((1, t), -1, dtype=torch.long),
                  qsv=torch.zeros(1, t, c.qsv_dim))
    out = model.represent(**inputs)
    gradient = torch.autograd.grad(out[0, -1, 0], numeric)[0]
    assert gradient[0, 0].abs().sum() > 0
    earlier = out[:, :-1].detach()
    inputs['numeric'] = numeric.detach().clone()
    inputs['numeric'][:, -1, 0] += 100
    assert torch.equal(model.represent(**inputs)[:, :-1], earlier)


def test_partial_qsv_keeps_available_fields_and_marks_missing_separately():
    torch.manual_seed(12)
    c = config()
    enc = FieldEncoder(c).eval()
    qsv = torch.zeros(1, 1, c.qsv_dim, requires_grad=True)
    mask = torch.ones_like(qsv, dtype=torch.bool)
    mask[..., 1] = False
    numeric = torch.randn(1, 1, 2)
    categorical = torch.zeros(1, 1, 1, dtype=torch.long)
    out = enc(numeric, categorical, qsv, mask)
    gradient = torch.autograd.grad(out[0, 0, 0], qsv)[0]
    assert gradient[..., 0].abs().sum() > 0
    assert gradient[..., 1].abs().sum() == 0
    poisoned = qsv.detach().clone()
    poisoned[..., 1] = float('nan')
    assert torch.equal(enc(numeric, categorical, poisoned, mask), out)
    assert not torch.equal(enc(numeric, categorical, qsv.detach(), torch.ones_like(mask)), out)


def test_partial_numeric_and_categorical_rows_survive_and_extra_columns_raise():
    torch.manual_seed(12)
    c = config()
    enc = FieldEncoder(c).eval()
    numeric = torch.tensor([[[2., float('nan')]]], requires_grad=True)
    cats = torch.tensor([[[-1]]])
    qsv = torch.zeros(1, 1, c.qsv_dim)
    out = enc(numeric, cats, qsv, numeric_mask=torch.tensor([[[1, 0]]]),
              categorical_mask=torch.zeros_like(cats))
    grad = torch.autograd.grad(out[0, 0, 0], numeric)[0]
    assert grad[0, 0, 0] != 0 and grad[0, 0, 1] == 0
    with pytest.raises(ValueError, match='exactly every'):
        enc(torch.zeros(1, 1, 2), torch.zeros(1, 1, 2, dtype=torch.long), qsv)






def test_graph_rejects_future_or_invalid_ancestry():
    from trunk import TemporalGraphBranch
    c = config()
    branch = TemporalGraphBranch(c)
    for parent in (torch.tensor([[1, -1]]), torch.tensor([[-2, -1]])):
        with pytest.raises(ValueError, match='future ancestry'):
            branch(torch.randn(1, 2, c.d_model), torch.zeros(1, 2, dtype=torch.long),
                   torch.zeros(1, 2, dtype=torch.long), parent)


def test_packet_owns_immutable_raw_and_feature_values():
    raw = {'nested': [1, {'x': 2}]}
    feature = {'nested': [4]}
    row = Record('a', 1, 1, raw)
    p = packet([row], [FeatureSpec('f', '1', lambda w: feature)])
    before = p.hash
    raw['nested'][1]['x'] = 999
    feature['nested'].append(6)
    assert p.hash == before
    assert p.source_records['mbo'][0].payload['nested'][1]['x'] == 2
    assert tuple(p.features['f.nested']) == (4,)
    with pytest.raises(TypeError):
        p.source_records['mbo'][0].payload['nested'][1]['x'] = 3
    with pytest.raises(TypeError):
        p.features['f.nested'] = ()


def test_field_entries_distinguish_absent_null_and_zero():
    rows = [Record('a', 1, 1, {}), Record('b', 2, 2, {'size': None}),
            Record('c', 3, 3, {'size': 0})]
    entries = CausalWindow(10, {'mbo': rows}).field_entries('mbo', 'size')
    assert [(present, value) for _, present, value in entries] == [(False, None), (True, None), (True, 0)]




def test_operator_fetch_history_retains_counts_without_packet_leakage():
    rows = [MBORow('a', 1, 2, 0, {}), MBORow('later', 10, 10, 0, {})]
    source = DatabentoMBOSource('mbo', lambda _: rows)
    source.fetch('ES', 3)
    source.fetch('ES', 20)
    history = source.fetch_history()
    assert len(history) == 2
    assert history[0][2].inspected == 2
    assert history[0][2].received_asof == 1
    assert history[0][2].excluded_future == 1
    assert history[1][2].received_asof == 2


def test_generic_source_cannot_self_authorize_an_independent_clock():
    from causal_packet import CaptureClockContract, LeakageError
    with pytest.raises(ValueError, match='clock contract'):
        Record('a', 3, 2, {}, independent_clocks=True)
    row = Record('a', 3, 2, {}, independent_clocks=True, clock_contract=CaptureClockContract('mbo'))
    with pytest.raises(LeakageError, match='declared source'):
        packet([row])


def test_missing_authoritative_watermark_is_explicit_and_does_not_rescan():
    calls = []
    def rows(entity):
        calls.append(entity)
        assert len(calls) == 1
        yield MBORow('a', 2, 3, 0, {})
    source = DatabentoMBOSource('mbo', rows)
    p = PacketBuilder([source], []).build('ES', 5, 'm', 'c')
    assert p.watermarks[0].value is None
    assert p.watermarks[0].lag_ns is None
    assert any('completeness watermark unavailable' in d for d in p.degraded)
    assert len(p.source_records['mbo']) == 1
