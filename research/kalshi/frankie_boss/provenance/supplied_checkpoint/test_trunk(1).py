"""
Falsification suite for the trunk and the teacher harness.

The load-bearing test is test_no_future_leakage. Everything upstream --
bitemporal filtering, watermarks, canonical hashing -- is wasted if the
model itself can attend forward. That test perturbs a single future step
and asserts every earlier output is bit-identical.
"""

import pytest
import torch

from teacher import ARMS, ExperimentReport, ArmResult, TeacherHead, run_experiment
from trunk import GatedDeltaCell, Trunk, TrunkConfig

torch.manual_seed(0)


def cfg(**kw):
    base = dict(
        d_model=32, n_heads=4, n_layers=2, window=8,
        n_numeric=5, categorical_cardinalities=(4, 6),
        qsv_dim=7, n_venues=3, n_instruments=5, n_regimes=3,
    )
    base.update(kw)
    return TrunkConfig(**base)


def batch(c: TrunkConfig, b=2, t=12, seed=0):
    g = torch.Generator().manual_seed(seed)
    return {
        "numeric": torch.randn(b, t, c.n_numeric, generator=g),
        "categorical": torch.stack(
            [
                torch.randint(0, n, (b, t), generator=g)
                for n in c.categorical_cardinalities
            ],
            dim=-1,
        ),
        "venue_id": torch.randint(0, c.n_venues, (b, t), generator=g),
        "instrument_id": torch.randint(0, c.n_instruments, (b, t), generator=g),
        "parent": torch.cat(
            [torch.full((b, 1), -1), torch.zeros(b, t - 1, dtype=torch.long)], dim=1
        ),
        "qsv": torch.randn(b, t, c.qsv_dim, generator=g),
        "label": torch.randint(0, 2, (b,), generator=g).float(),
        "dipole": torch.randn(b, t, 4, generator=g),
    }


def fwd(model, b):
    return model(
        b["numeric"], b["categorical"], b["venue_id"],
        b["instrument_id"], b["parent"], b["qsv"],
    )


# ------------------------------------------------------------------ shapes


def test_head_shapes_and_bounds():
    c = cfg()
    m = Trunk(c).eval()
    with torch.no_grad():
        out = fwd(m, batch(c))
    assert out["p_up"].shape == (2,)
    assert out["regime_logits"].shape == (2, c.n_regimes)
    assert out["evidence_scores"].shape == (2, 12)
    assert bool(((out["p_up"] >= 0) & (out["p_up"] <= 1)).all())
    assert bool(((out["size"] >= -1) & (out["size"] <= 1)).all())
    assert bool((out["sigma"] >= 0).all())
    assert bool(torch.isfinite(out["size"]).all())


def test_qsv_dim_zero_disables_branch_cleanly():
    c = cfg(qsv_dim=0)
    m = Trunk(c).eval()
    b = batch(c)
    with torch.no_grad():
        out = m(
            b["numeric"], b["categorical"], b["venue_id"],
            b["instrument_id"], b["parent"], None,
        )
    assert out["p_up"].shape == (2,)


def test_qsv_required_when_configured():
    c = cfg(qsv_dim=7)
    m = Trunk(c).eval()
    b = batch(c)
    with pytest.raises(ValueError):
        m(b["numeric"], b["categorical"], b["venue_id"],
          b["instrument_id"], b["parent"], None)


# -------------------------------------------------------------- causality


def test_no_future_leakage():
    """Perturb the last step. Every earlier hidden state must be identical."""
    c = cfg()
    m = Trunk(c).eval()
    b = batch(c)
    with torch.no_grad():
        h1 = m.represent(
            b["numeric"], b["categorical"], b["venue_id"],
            b["instrument_id"], b["parent"], b["qsv"],
        )
        n2 = b["numeric"].clone()
        n2[:, -1] += 100.0
        h2 = m.represent(
            n2, b["categorical"], b["venue_id"],
            b["instrument_id"], b["parent"], b["qsv"],
        )
    assert torch.equal(h1[:, :-1], h2[:, :-1]), "future step altered the past"
    assert not torch.equal(h1[:, -1], h2[:, -1]), "perturbation had no effect at all"


def test_sliding_window_horizon_is_respected():
    """A step outside the window must not reach the final position
    through attention.

    Both other long-range paths are removed to isolate attention: delta
    memory is disabled, and parent is set to -1 everywhere so the graph
    branch has no edges. With them present this test fails, which is
    correct -- see test_graph_branch_is_an_unbounded_path.
    """
    c = cfg(window=4, n_layers=1, use_delta_memory=False)
    m = Trunk(c).eval()
    b = batch(c, t=12)
    orphan = torch.full_like(b["parent"], -1)
    with torch.no_grad():
        base = m.represent(
            b["numeric"], b["categorical"], b["venue_id"],
            b["instrument_id"], orphan, b["qsv"],
        )[:, -1]
        n2 = b["numeric"].clone()
        n2[:, 0] += 100.0  # far outside the 4-step window
        moved = m.represent(
            n2, b["categorical"], b["venue_id"],
            b["instrument_id"], orphan, b["qsv"],
        )[:, -1]
    assert torch.allclose(base, moved, atol=1e-5)


def test_graph_branch_is_an_unbounded_path():
    """Documents a real property, not a bug.

    Order ancestry legitimately spans arbitrary time, so the graph branch
    can carry information from outside the attention window. The
    consequence is that `window` does NOT bound the model's receptive
    field -- only the attention path's. Anything reasoning about the
    effective horizon (capacity half-life, drift attribution) has to
    account for ancestry edges separately.
    """
    c = cfg(window=4, n_layers=1, use_delta_memory=False)
    m = Trunk(c).eval()
    b = batch(c, t=12)
    hub = torch.zeros_like(b["parent"])
    hub[:, 0] = -1  # every step descends from step 0
    with torch.no_grad():
        base = m.represent(
            b["numeric"], b["categorical"], b["venue_id"],
            b["instrument_id"], hub, b["qsv"],
        )[:, -1]
        n2 = b["numeric"].clone()
        n2[:, 0] += 100.0
        moved = m.represent(
            n2, b["categorical"], b["venue_id"],
            b["instrument_id"], hub, b["qsv"],
        )[:, -1]
    assert not torch.allclose(base, moved, atol=1e-5)


# ------------------------------------------------------------ determinism


def test_eval_is_deterministic():
    c = cfg()
    m = Trunk(c).eval()
    b = batch(c)
    with torch.no_grad():
        a, z = fwd(m, b), fwd(m, b)
    for k in a:
        assert torch.equal(a[k], z[k]), f"{k} not reproducible in eval"


# ---------------------------------------------------- gated delta memory


def test_delta_cell_is_causal():
    c = cfg()
    cell = GatedDeltaCell(c).eval()
    x = torch.randn(2, 10, c.d_model)
    with torch.no_grad():
        y1 = cell(x)
        x2 = x.clone()
        x2[:, -1] += 50.0
        y2 = cell(x2)
    assert torch.equal(y1[:, :-1], y2[:, :-1])


def test_delta_cell_state_actually_carries():
    """Memory must propagate: an early perturbation should reach the end."""
    c = cfg()
    cell = GatedDeltaCell(c).eval()
    x = torch.randn(2, 10, c.d_model)
    with torch.no_grad():
        y1 = cell(x)
        x2 = x.clone()
        x2[:, 0] += 50.0
        y2 = cell(x2)
    assert not torch.allclose(y1[:, -1], y2[:, -1], atol=1e-6)


def test_erase_and_write_gates_are_independent():
    """The decoupling is the whole point. Perturbing only the erase
    projection must change the output, and likewise for write."""
    c = cfg()
    cell = GatedDeltaCell(c).eval()
    x = torch.randn(2, 8, c.d_model)
    with torch.no_grad():
        base = cell(x).clone()
        cell.erase.bias += 2.0
        erased = cell(x).clone()
        cell.erase.bias -= 2.0
        cell.write.bias += 2.0
        written = cell(x).clone()
    assert not torch.allclose(base, erased, atol=1e-6)
    assert not torch.allclose(base, written, atol=1e-6)
    assert not torch.allclose(erased, written, atol=1e-6)


# ------------------------------------------------------- teacher harness


def test_harness_refuses_to_run_without_controls():
    with pytest.raises(ValueError, match="refusing to run without controls"):
        run_experiment(
            build_model=lambda: Trunk(cfg()),
            build_teacher=lambda: TeacherHead(32, 4),
            batches=[], val_batches=[], arms=("dipole",),
        )


def test_verdict_refuses_without_every_arm():
    rep = ExperimentReport([ArmResult("dipole", 0.1, 0.1, 0.1, 0)])
    with pytest.raises(RuntimeError, match="control arms never ran"):
        rep.verdict()


def test_verdict_kills_when_gain_is_inside_control_spread():
    rep = ExperimentReport(
        [
            ArmResult("none", 0, 0, 0.50, 0),
            ArmResult("plain_aux", 0, 0, 0.44, 0),
            ArmResult("shuffled", 0, 0, 0.42, 0),
            ArmResult("random", 0, 0, 0.46, 0),
            ArmResult("dipole", 0, 0, 0.41, 0),  # beats all, but barely
        ]
    )
    ok, msg = rep.verdict()
    assert not ok and "within the control spread" in msg


def test_verdict_kills_when_a_control_wins():
    rep = ExperimentReport(
        [
            ArmResult("none", 0, 0, 0.50, 0),
            ArmResult("plain_aux", 0, 0, 0.30, 0),
            ArmResult("shuffled", 0, 0, 0.45, 0),
            ArmResult("random", 0, 0, 0.47, 0),
            ArmResult("dipole", 0, 0, 0.40, 0),
        ]
    )
    ok, msg = rep.verdict()
    assert not ok and "does not beat best control" in msg


def test_verdict_passes_only_on_a_clear_margin():
    rep = ExperimentReport(
        [
            ArmResult("none", 0, 0, 0.50, 0),
            ArmResult("plain_aux", 0, 0, 0.49, 0),
            ArmResult("shuffled", 0, 0, 0.48, 0),
            ArmResult("random", 0, 0, 0.50, 0),
            ArmResult("dipole", 0, 0, 0.30, 0),
        ]
    )
    ok, msg = rep.verdict()
    assert ok and "Not proof" in msg


def test_end_to_end_smoke():
    c = cfg(d_model=16, n_heads=2, n_layers=1)
    tr = [batch(c, seed=i) for i in range(2)]
    va = [batch(c, seed=100)]
    rep = run_experiment(
        build_model=lambda: Trunk(c),
        build_teacher=lambda: TeacherHead(c.d_model, 4),
        batches=tr, val_batches=va, seeds=(0,),
    )
    assert len(rep.results) == len(ARMS)
    assert all(r.val_metric == r.val_metric for r in rep.results)  # no NaN
