"""Exact native fields reach tensors and learned computation; synthetic only."""
import copy
import struct
import pytest
import torch
from c15_journal import pack
from causal_packet import canonical_bytes
from test_c15_full_evidence import row
from native_mbo_encoder import NativeRegistry, ADAPTER_FIELDS, encode, reconstruct, reconstruct_payloads, NativeTrunk


def test_exact_inverse_including_identity_unknowns_and_extensions():
    rows = [row(0, oid=2**64-1), row(1, oid=7)]
    rows[0].update(rtype=160, extra={'huge': 10**100, 'null': None,
        'zero': -0.0, 'bits': b'\x00\xff', 'nan': struct.unpack('>d', bytes.fromhex('7ff8000000000001'))[0]})
    rows[1].update(action='UNKNOWN-A', extra=('x', 0))
    registry = NativeRegistry(extra_fields=('extra',))
    tokens = encode(rows, as_of=102, registry=registry)
    assert canonical_bytes(pack(reconstruct(tokens, registry))) == canonical_bytes(pack(rows))
    assert tokens['numeric'].dtype == torch.float64
    assert tokens['parent'].tolist() == [[-1, -1]]
    assert tokens['byte_values'].numel() > 0


def test_coverage_rejects_undeclared_adapter_fields():
    with pytest.raises(ValueError, match='unmapped.*new_field'):
        encode([{**row(0), 'new_field': 1}], as_of=2, registry=NativeRegistry())


def test_missing_null_and_zero_are_different_and_owned():
    rows = [row(0), row(1), row(2)]
    del rows[0]['size']
    rows[1]['size'] = None
    rows[2]['size'] = 0
    registry = NativeRegistry()
    tokens = encode(rows, as_of=202, registry=registry)
    saved = reconstruct(tokens, registry)
    rows[2]['size'] = 9
    assert 'size' not in saved[0] and saved[1]['size'] is None and saved[2]['size'] == 0
    assert tokens['numeric_mask'][0, :, 9:12].tolist() == [[False]*3, [False]*3, [True]*3]


def test_graph_links_and_context_age_are_causal_and_scoped():
    rows = [row(0, oid=9), row(1, oid=7), row(2, oid=9), row(3, oid=9)]
    tokens = encode(rows[1:], as_of=302, registry=NativeRegistry())
    assert tokens['parent'].tolist() == [[-1, -1, 1]]
    assert tokens['numeric'][0, :, -1].tolist() == [0, 0, 100]


@pytest.mark.parametrize('field', tuple(row(0)) + ('rtype',))
def test_each_native_field_changes_hidden_state(field):
    torch.manual_seed(71)
    registry = NativeRegistry()
    model = NativeTrunk(registry, d_model=16, n_heads=2, n_layers=1).double().eval()
    a = [row(0), row(1)]
    a[0]['rtype'] = 160
    b = copy.deepcopy(a)
    if field == 'action': b[0][field] = 'M'
    elif field == 'side': b[0][field] = 'B'
    else: b[0][field] += 1
    with torch.no_grad():
        before = model.represent(tokens=encode(a, as_of=102, registry=registry))
        after = model.represent(tokens=encode(b, as_of=102, registry=registry))
    assert not torch.equal(before, after), field


def test_unknown_categories_and_first_order_ids_do_not_collapse():
    torch.manual_seed(72)
    registry = NativeRegistry(extra_fields=('extra',))
    model = NativeTrunk(registry, d_model=16, n_heads=2, n_layers=1).double().eval()
    a = [{**row(0, oid=7), 'action': 'unknown-A', 'extra': b'A' * 3000}]
    with torch.no_grad():
        baseline = model.represent(tokens=encode(a, as_of=2, registry=registry))
        for field, val in [('order_id', 9), ('action', 'unknown-B'), ('extra', b'B'+b'A'*2999)]:
            changed = [{**a[0], field: val}]
            assert not torch.equal(baseline, model.represent(tokens=encode(changed, as_of=2, registry=registry)))


def test_each_semantic_column_and_graph_link_has_computation_path():
    torch.manual_seed(99)
    registry = NativeRegistry()
    model = NativeTrunk(registry, d_model=16, n_heads=2, n_layers=1).double().eval()
    tokens = encode([row(0), row(1)], as_of=102, registry=registry)
    tokens['categorical_mask'].fill_(True)
    with torch.no_grad():
        base = model.represent(tokens=tokens)
        for i in range(tokens['numeric'].shape[-1]):
            changed = {k: v.clone() for k,v in tokens.items()}
            changed['numeric'][0,1,i] += 1
            assert not torch.equal(base, model.represent(tokens=changed)), ('numeric',i)
        for i, cardinality in enumerate(model.cfg.categorical_cardinalities):
            changed = {k: v.clone() for k,v in tokens.items()}
            changed['categorical'][0,1,i] = (changed['categorical'][0,1,i]+1) % cardinality
            assert not torch.equal(base, model.represent(tokens=changed)), ('categorical',i)
        changed = {k: v.clone() for k,v in tokens.items()}
        changed['parent'].fill_(-1)
        assert not torch.equal(base, model.represent(tokens=changed))


def test_future_suffix_does_not_change_previous_hidden_states():
    torch.manual_seed(13)
    registry = NativeRegistry()
    model = NativeTrunk(registry, d_model=16, n_heads=2, n_layers=1).double().eval()
    rows = [row(0), row(1)]
    tokens = encode(rows, as_of=102, registry=registry)
    with torch.no_grad():
        base = model.represent(tokens=tokens)
        changed = encode([rows[0], {**rows[1], 'size': 77}], as_of=102, registry=registry)
        assert torch.equal(base[:,:1], model.represent(tokens=changed)[:,:1])


@pytest.mark.parametrize('provided', [None,1.9,'1'])
def test_invalid_clock_semantic_type_is_masked_but_exact_bytes_survive(provided):
    r={**row(0),'independent_clocks':provided}
    tokens=encode([r],as_of=2,registry=NativeRegistry())
    assert not tokens['categorical_mask'][0,0,-1]
    assert reconstruct(tokens,NativeRegistry())==[r]


def test_absent_clock_flag_is_missing_not_a_fabricated_present_value():
    tokens=encode([row(0)],as_of=2,registry=NativeRegistry())
    assert not tokens['categorical_mask'][0,0,-1]


def test_every_adapter_field_and_metadata_value_reaches_computation():
    torch.manual_seed(73)
    registry=NativeRegistry()
    model=NativeTrunk(registry,d_model=16,n_heads=2,n_layers=1).double().eval()
    rows=[row(0)]
    meta=dict(adapter={},source_context={'cursor':0},defects={'count':0})
    with torch.no_grad():
        base=model.represent(tokens=encode(rows,as_of=2,registry=registry,metadata=[meta]))
        for field in ADAPTER_FIELDS:
            changed=[{**rows[0],field:True if field.startswith('is_') or field=='independent_clocks' else 1}]
            tokens=encode(changed,as_of=2,registry=registry,metadata=[meta])
            assert reconstruct(tokens,registry)==changed
            assert not torch.equal(base,model.represent(tokens=tokens)),field
        for section,field in [('adapter','raw_symbol'),('source_context','cursor'),('defects','count')]:
            changed=copy.deepcopy(meta); changed[section][field]=1
            tokens=encode(rows,as_of=2,registry=registry,metadata=[changed])
            assert reconstruct_payloads(tokens,registry)[0]['metadata']==changed
            assert not torch.equal(base,model.represent(tokens=tokens)),(section,field)
