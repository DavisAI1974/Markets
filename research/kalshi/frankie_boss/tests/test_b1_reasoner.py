"""C19/C20 acceptance tests. Real torch and the unchanged B0 trunk are required."""

from b1_reasoner import B1Config, B1Reasoner, convergence_halt

import inspect
import subprocess
from dataclasses import asdict, replace
from pathlib import Path

import pytest
import torch

from causal_packet import canonical_bytes
from trunk import Trunk, TrunkConfig


@pytest.fixture(params=('v1_control', 'v2'), autouse=True)
def trunk_lineage(request, monkeypatch):
    """Run A1-A8/H1-H7 against the pinned control and the v2 extension."""
    if request.param == 'v1_control':
        import importlib.util
        import hashlib
        import sys
        path=Path(__file__).resolve().parents[4]/'tests/fixtures/boss_control_beb548b8/trunk_v1.py'
        assert hashlib.sha256(path.read_bytes()).hexdigest() == '82d2a3ac73cc7d2f7d03d39fd0ef9c96d615f1c611084d702a4a506bbe573c33'
        name='_boss_b1_control_v1'
        spec=importlib.util.spec_from_file_location(name,path)
        control=importlib.util.module_from_spec(spec)
        sys.modules[name]=control
        spec.loader.exec_module(control)
        monkeypatch.setattr(sys.modules[__name__],'Trunk',control.Trunk)
        monkeypatch.setattr(sys.modules[__name__],'TrunkConfig',control.TrunkConfig)


def inputs(b=2, t=4, seed=11):
    g = torch.Generator().manual_seed(seed)
    return dict(numeric=torch.randn(b, t, 3, generator=g),
                categorical=torch.randint(0, 4, (b, t, 1), generator=g),
                venue_id=torch.zeros(b, t, dtype=torch.long),
                instrument_id=torch.zeros(b, t, dtype=torch.long),
                parent=torch.full((b, t), -1, dtype=torch.long))


def model(**kw):
    torch.manual_seed(31)
    trunk = Trunk(TrunkConfig(d_model=8, n_heads=2, n_layers=1, window=3,
                             n_numeric=3, categorical_cardinalities=(4,), use_qsv=False))
    return B1Reasoner(trunk, B1Config(**kw)).eval()


def forward(m, x):
    return m(**x, packet_hash="a" * 64)


def equal_heads(a, b):
    assert a.keys() == b.keys()
    for key in a:
        assert torch.equal(a[key], b[key]), key


def test_a1_zero_depth_is_exact_b0():
    m, x = model(k_fixed=0), inputs()
    equal_heads(forward(m, x), m.trunk(**x))
    assert torch.equal(m.represent(**x), m.represent_b0(**x))


def test_a2_core_count_independent_embedding_count_exact():
    counts = []
    for depth in (1, 4, 8):
        m = model(k_max=depth, k_fixed=depth)
        receipt = forward(m, inputs()).receipt
        counts.append(receipt.n_params_core)
        assert receipt.n_params_step_embedding == depth * 8
        assert receipt.n_params_core + receipt.n_params_step_embedding == sum(
            p.numel() for p in m.parameters())
    assert len(set(counts)) == 1


@pytest.mark.parametrize("policy", ["FIXED", "CONVERGENCE"])
def test_a3_h5_eval_determinism(policy):
    m, x = model(halt_policy=policy), inputs(b=1)
    a, b = forward(m, x), forward(m, x)
    equal_heads(a, b)
    assert torch.equal(a.representation, b.representation)
    assert a.receipt == b.receipt


def test_a4_full_gradient_reaches_first_step_injection_and_trunk():
    m, x = model(k_fixed=4).train(), inputs()
    out = forward(m, x)
    (out["regime_logits"].square().sum() + out["size"].sum()).backward()
    for grad in (m.e_step.grad[0], m.w_in.weight.grad,
                 m.trunk.encoder.numeric.weight.grad):
        assert grad is not None and torch.count_nonzero(grad) > 0


@pytest.mark.parametrize("depth", [0, 1, 4, 8])
def test_a5_graph_applied_once(depth):
    m = model(k_fixed=depth)
    seen = []
    hook = m.trunk.graph.register_forward_hook(lambda *args: seen.append(1))
    forward(m, inputs())
    hook.remove()
    assert seen == [1]


def test_a6_no_cross_forward_state():
    m, b = model(), inputs(seed=20)
    before = forward(m, b)
    forward(m, inputs(seed=300))
    equal_heads(before, forward(m, b))


def test_a7_each_reasoning_delta_sweep_starts_with_zero_memory(monkeypatch):
    m = model(k_fixed=4)
    original = torch.einsum
    first_reads = []
    pending = [False]
    hook = m.gdc_r.register_forward_pre_hook(lambda *args: pending.__setitem__(0, True))

    def observe(equation, *operands):
        if pending[0] and equation == "bhkd,bhk->bhd":
            first_reads.append(operands[0].clone())
            pending[0] = False
        return original(equation, *operands)

    monkeypatch.setattr(torch, "einsum", observe)
    forward(m, inputs())
    hook.remove()
    assert len(first_reads) == 4
    assert all(torch.count_nonzero(state) == 0 for state in first_reads)


def test_a8_hash_binding_is_canonical_and_actual_git_blob():
    import hashlib
    import b1_reasoner
    m = model()
    receipt = forward(m, inputs()).receipt
    expected = hashlib.sha256(b"BOSS_B1_RECURRENCE_V1\0" + canonical_bytes(asdict(m.config))).hexdigest()
    assert receipt.config_hash == expected
    blob = subprocess.check_output(["git", "hash-object", b1_reasoner.__file__], text=True).strip()
    assert receipt.b1_code_sha == blob
    assert len({B1Config().config_hash, B1Config(k_max=9).config_hash,
                B1Config(conv_tau=0.02).config_hash}) == 3


def test_h1_fixed_matches_unconditional_manual_recurrence():
    m, x = model(k_fixed=4), inputs()
    h0 = m.trunk.represent(**x)
    z = h0
    for k in range(4):
        z = m.reasoning_step(z, h0, k)
    result = forward(m, x)
    assert torch.equal(result.representation, z)
    equal_heads(result, m.trunk.heads(z))
    assert result.receipt.depth_used == (4, 4)
    assert result.receipt.stop_reason == ("FIXED_DEPTH", "FIXED_DEPTH")


@pytest.mark.parametrize("tau", [1e-3, 10.0])
@pytest.mark.parametrize("length,seed", [(4, 11), (7, 11), (7, 33)])
def test_h2b_h2c_convergence_batch_independence(length, seed, tau):
    m, x = model(halt_policy="CONVERGENCE", conv_tau=tau), inputs(b=32, t=length, seed=seed)
    batch = forward(m, x)
    alone = forward(m, {k: v[:1] for k, v in x.items()})
    assert_h2_agreement(batch, alone, m.config.conv_tau)


@pytest.mark.parametrize("width,length", [(8, 1), (16, 7), (32, 7)])
def test_h2_review_regression_unchanged_trunk_batch_numerics(width, length):
    """Retain all three review fixtures under the owner-approved H2b/H2c."""
    torch.manual_seed(31)
    m = B1Reasoner(
        Trunk(TrunkConfig(d_model=width, n_heads=2, n_layers=1, window=3,
                          n_numeric=3, categorical_cardinalities=(4,), use_qsv=False)),
        B1Config(halt_policy="CONVERGENCE", k_max=2, k_fixed=2),
    ).eval()
    x = dict(numeric=torch.randn(32, length, 3),
             categorical=torch.randint(0, 4, (32, length, 1)),
             venue_id=torch.zeros(32, length, dtype=torch.long),
             instrument_id=torch.zeros(32, length, dtype=torch.long),
             parent=torch.full((32, length), -1, dtype=torch.long))
    single = {key: value[:1] for key, value in x.items()}
    with torch.no_grad():
        batched = forward(m, x)
        alone = forward(m, single)
    assert_h2_agreement(batched, alone, m.config.conv_tau)


def test_h3_zero_threshold_forces_max_depth():
    m = model(halt_policy="CONVERGENCE", conv_tau=0, k_max=3, k_fixed=3)
    receipt = forward(m, inputs()).receipt
    assert receipt.depth_used == (3, 3)
    assert receipt.stop_reason == ("MAX_DEPTH", "MAX_DEPTH")


def test_convergence_cell_heads_and_graph_use_whole_batch():
    m, x = model(halt_policy="CONVERGENCE", k_max=2, k_fixed=2), inputs(b=3)
    shapes = {"cell": [], "heads": [], "graph": []}
    hooks = [module.register_forward_pre_hook(
        lambda module, args, name=name: shapes[name].append(args[0].shape[0]))
        for name, module in [("cell", m.ln_in), ("heads", m.trunk.heads),
                             ("graph", m.trunk.graph)]]
    result = forward(m, x)
    for hook in hooks:
        hook.remove()
    assert shapes == {"cell": [3] * max(result.receipt.depth_used),
                      "heads": [3], "graph": [3]}
    equal_heads(result, m.trunk.heads(result.representation))


def assert_h2_agreement(batch, alone, tau):
    # Both actual traces must be away from the threshold before comparing depth.
    for trace in (batch.receipt.r_trace[0], alone.receipt.r_trace[0]):
        assert min(abs(r - tau) for r in trace) > .01 * tau
    assert batch.receipt.depth_used[0] == alone.receipt.depth_used[0]
    assert batch.receipt.stop_reason[0] == alone.receipt.stop_reason[0]
    assert batch.representation.dtype == alone.representation.dtype == torch.float32
    assert (batch.representation[:1] - alone.representation).abs().max().item() <= 1e-4
    for key in alone:
        assert (batch[key][:1] - alone[key]).abs().max().item() <= 1e-4, key


@pytest.mark.parametrize("policy", ["FIXED", "CONVERGENCE"])
def test_h2a_exact_zero_cross_example_gradients(policy):
    m, x = model(halt_policy=policy, k_max=2, k_fixed=2).train(), inputs(b=4)
    x["numeric"].requires_grad_()
    out = forward(m, x)
    losses = out["regime_logits"].square().flatten(1).sum(1) + out["size"].reshape(4, -1).sum(1)
    for b in range(4):
        grad, = torch.autograd.grad(losses[b:b+1].sum(), x["numeric"], retain_graph=True)
        assert torch.count_nonzero(grad[b]) > 0
        assert torch.count_nonzero(grad[torch.arange(4) != b]) == 0


def test_audited_decision_is_one_packet_and_rejects_batch_before_trunk():
    m = model(halt_policy="CONVERGENCE")
    x = inputs(b=1)
    equal_heads(m.forward_decision(**x, packet_hash="a" * 64), forward(m, x))
    calls = []
    hook = m.trunk.graph.register_forward_pre_hook(lambda *args: calls.append(1))
    with pytest.raises(ValueError, match="exactly one packet"):
        m.forward_decision(**inputs(), packet_hash="a" * 64)
    hook.remove()
    assert calls == []


def test_h4_h7_mixed_depth_freezes_each_example(monkeypatch):
    m, x = model(halt_policy="CONVERGENCE", k_max=4, k_fixed=4), inputs()
    states = []

    def step(z, h0, k):
        states.append(z.clone())
        change = torch.zeros_like(z)
        change[1] = 1
        return z + change

    monkeypatch.setattr(m, "reasoning_step", step)
    out = forward(m, x)
    assert out.receipt.depth_used == (1, 4)
    assert out.receipt.stop_reason == ("CONVERGED", "MAX_DEPTH")
    assert all(torch.equal(state[0], states[0][0]) for state in states)
    assert torch.equal(out.representation[0], states[0][0])
    assert len(out.receipt.r_trace[0]) == 1
    assert len(out.receipt.r_trace[1]) == 4


def test_h6_halting_has_only_representation_arguments():
    assert tuple(inspect.signature(convergence_halt).parameters) == (
        "z_prev", "z_next", "valid_mask", "k", "constants")
    import decision_contract
    source = Path(decision_contract.__file__).read_text()
    assert "depth_used" not in source and "stop_reason" not in source


def test_halting_norm_ignores_invalid_tokens():
    prev = torch.ones(1, 2, 2)
    nxt = prev.clone()
    nxt[:, 1] = 1e10
    ratio, halt = convergence_halt(prev, nxt, torch.tensor([[True, False]]),
                                   1, B1Config(halt_policy="CONVERGENCE"))
    assert ratio.item() == 0 and halt.item()


@pytest.mark.parametrize("kw", [dict(k_max=0), dict(k_fixed=-1), dict(k_fixed=9),
    dict(k_max=True), dict(conv_tau=float("nan")), dict(conv_tau=-1),
    dict(halt_policy="CONFIDENCE"), dict(inject_input=1)])
def test_config_rejects_invalid_contract(kw):
    with pytest.raises(ValueError):
        B1Config(**kw)


def test_receipt_requires_packet_identity():
    m = model()
    with pytest.raises(ValueError, match="packet_hash"):
        m(**inputs(), packet_hash="")


def test_early_stop_matches_full_loop_with_all_rows_frozen(monkeypatch):
    m, x = model(halt_policy="CONVERGENCE"), inputs()
    calls = []

    def identity_step(z, h0, k):
        calls.append(k)
        return z

    monkeypatch.setattr(m, "reasoning_step", identity_step)
    out = forward(m, x)
    assert calls == [0]
    assert out.receipt.depth_used == (1, 1)
    assert out.receipt.stop_reason == ("CONVERGED", "CONVERGED")
    assert torch.equal(out.representation, m.trunk.represent(**x))


def test_convergence_training_uses_same_depth_and_reaches_encoder():
    m, x = model(halt_policy="CONVERGENCE", conv_tau=0, k_fixed=4, k_max=4), inputs()
    evaluation = forward(m, x)
    m.train()
    training = forward(m, x)
    assert training.receipt == evaluation.receipt
    training["size"].sum().backward()
    assert torch.count_nonzero(m.e_step.grad[0]) > 0
    assert torch.count_nonzero(m.trunk.encoder.numeric.weight.grad) > 0


def test_declared_ablations_remove_only_their_contributions():
    m, x = model(inject_input=False, step_embedding=False, k_fixed=2), inputs()
    before = forward(m, x)
    with torch.no_grad():
        m.e_step.fill_(1e10)
        m.w_in.weight.fill_(1e10)
    after = forward(m, x)
    equal_heads(before, after)
    assert before.receipt == after.receipt


@pytest.mark.parametrize("mask", [torch.ones(2, 4), torch.ones(2, 3, dtype=torch.bool),
                                 torch.zeros(2, 4, dtype=torch.bool)])
def test_invalid_token_masks_fail_closed(mask):
    with pytest.raises(ValueError, match="valid_mask"):
        model()(**inputs(), valid_mask=mask, packet_hash="a" * 64)


def test_qsv_mask_reaches_unchanged_trunk_and_teacher_surface():
    from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY
    trunk = Trunk(TrunkConfig(d_model=8, n_heads=2, n_layers=1, n_numeric=3,
                             categorical_cardinalities=(4,), use_qsv=True))
    m = B1Reasoner(trunk, B1Config(k_fixed=0)).eval()
    x = inputs()
    x["qsv"] = torch.full((2, 4, len(QSV_FEATURE_REGISTRY)), float("nan"))
    x["qsv_mask"] = torch.zeros(2, 4, dtype=torch.bool)
    equal_heads(forward(m, x), trunk(**x))
    state = m.represent(**x)
    assert state.shape == (2, 4, 8)
    assert torch.isfinite(state).all()


def test_audited_decision_rejects_metadata_broadcast_to_multiple_packets():
    m, x = model(halt_policy="CONVERGENCE"), inputs(b=1)
    x.update({k: v for k, v in inputs(b=3).items()
              if k in ("venue_id", "instrument_id", "parent")})
    with pytest.raises(ValueError, match="exactly one packet"):
        m.forward_decision(**x, packet_hash="a" * 64)


def test_h2c_interior_convergence_depth_is_batch_independent():
    m = model(halt_policy="CONVERGENCE", conv_tau=0, k_max=8, k_fixed=8)
    x = inputs(b=32)
    single = {key: value[:1] for key, value in x.items()}
    with torch.no_grad():
        trace = forward(m, single).receipt.r_trace[0]
        candidates = []
        for j in range(1, len(trace) - 2):
            if not trace[j] > trace[j + 1] > 0:
                continue
            tau = (trace[j] * trace[j + 1]) ** 0.5
            if (all(r - tau > .01 * tau for r in trace[:j + 1])
                    and tau - trace[j + 1] > .01 * tau):
                candidates.append((j + 2, tau))
        assert candidates, "fixture has no interior first crossing with a 1% margin"
        expected_depth, tau = candidates[0]
        m.config = replace(m.config, conv_tau=tau)
        alone = forward(m, single)
        batch = forward(m, x)
    assert 1 < expected_depth < m.config.k_max
    assert alone.receipt.depth_used == (expected_depth,)
    assert alone.receipt.stop_reason == ("CONVERGED",)
    assert_h2_agreement(batch, alone, tau)


def test_audited_decision_requires_eval_mode():
    with pytest.raises(ValueError, match="eval mode"):
        model().train().forward_decision(**inputs(b=1), packet_hash="a" * 64)
