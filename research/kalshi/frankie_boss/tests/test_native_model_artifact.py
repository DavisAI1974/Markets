"""Synthetic artifact roundtrips; no fitted model or production acceptance."""
from dataclasses import replace
import pytest
import torch
from b1_reasoner import B1Reasoner, B1Config
from c15_journal import pack, unpack, canonical_bytes
from context_session import tensor_identity, ContextSessionRunner
from native_mbo_encoder import NativeTrunk, NativeRegistry
from native_model_artifact import NativeModelSnapshot
from test_c15_full_evidence import build, submit, row


ALL_FIXTURE_ROWS = 1 << 20   # a declared window larger than any fixture: the row window has no default (Greg, 2026-09-22)

def model(b1=True, qsv=False):
    native = NativeTrunk(NativeRegistry(), d_model=16, n_heads=2, n_layers=1,
                         use_qsv=qsv).double().eval()
    if qsv:
        native.encoder.ablate_qsv()
    return B1Reasoner(native, B1Config(k_max=1, k_fixed=1)).double().eval() if b1 else native


@pytest.mark.parametrize('b1', [False, True])
@pytest.mark.parametrize('qsv', [False, True])
def test_exact_roundtrip_outputs_and_rng(tmp_path, b1, qsv):
    original = model(b1, qsv)
    snapshot = NativeModelSnapshot.capture(original)
    rng = torch.get_rng_state().clone()
    restored = snapshot.restore()
    assert torch.equal(rng, torch.get_rng_state())
    assert tensor_identity(original.state_dict()) == tensor_identity(restored.state_dict())
    assert NativeModelSnapshot.capture(restored) == snapshot
    assert all(not p.requires_grad for p in restored.parameters())
    builder = build(tmp_path); submit(builder, row(0))
    first = ContextSessionRunner(original, builder, entity=(1, 1),t_ctx=ALL_FIXTURE_ROWS).run(as_of=2)
    second = ContextSessionRunner(restored, builder, entity=(1, 1),t_ctx=ALL_FIXTURE_ROWS).run(as_of=2)
    assert first.receipt == second.receipt
    assert all(torch.equal(first.heads[k], second.heads[k]) for k in first.heads)


@pytest.mark.parametrize('change', ['extra', 'missing', 'dtype', 'shape', 'bytes', 'nonfinite'])
def test_corrupt_tensor_fails_without_conversion(change):
    snapshot = NativeModelSnapshot.capture(model())
    weights = unpack(__import__('json').loads(snapshot.weights))
    name = next(iter(weights))
    if change == 'extra': weights['unknown'] = weights[name]
    if change == 'missing': del weights[name]
    if change == 'dtype': weights[name]['dtype'] = 'torch.float32'
    if change == 'shape': weights[name]['shape'] = (1,)
    if change == 'bytes': weights[name]['bytes'] += b'x'
    if change == 'nonfinite': weights[name]['bytes'] = __import__('struct').pack('=d', float('nan')) + weights[name]['bytes'][8:]
    with pytest.raises(ValueError):
        replace(snapshot, weights=canonical_bytes(pack(weights))).restore()


def test_config_runtime_and_effective_settings_are_bound():
    snapshot = NativeModelSnapshot.capture(model())
    with pytest.raises(ValueError, match='runtime'):
        replace(snapshot, runtime='0'*64).restore()
    config = unpack(__import__('json').loads(snapshot.configuration))
    del config['trunk']['window']
    with pytest.raises(ValueError, match='configuration'):
        replace(snapshot, configuration=canonical_bytes(pack(config))).restore()
    original = model()
    original.trunk.ff[0][0].forward = lambda x: x
    with pytest.raises(ValueError): NativeModelSnapshot.capture(original)


def test_no_default_registry_fields():
    snapshot = NativeModelSnapshot.capture(model())
    config = unpack(__import__('json').loads(snapshot.configuration))
    config['registry'] = {}
    with pytest.raises(ValueError, match='registry configuration'):
        replace(snapshot, configuration=canonical_bytes(pack(config))).restore()


@pytest.mark.parametrize('change', ['training', 'float32', 'nonfinite', 'setting'])
def test_noncanonical_model_refused(change):
    original = model()
    if change == 'training': original.train()
    if change == 'float32': original.float()
    if change == 'nonfinite':
        with torch.no_grad(): next(original.parameters()).fill_(float('inf'))
    if change == 'setting': original.trunk.attn[0].scale = 99.
    with pytest.raises(ValueError): NativeModelSnapshot.capture(original)
