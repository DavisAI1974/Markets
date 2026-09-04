"""
Falsification suite for the teacher control arms.

Every test here is a statement about what a control MUST NOT be able to
do. The two characterization tests at the top pin the 2026-09-04 defects
against a frozen copy of the original code so they can never quietly
return.
"""

import pytest
import torch

from teacher import (
    ARMS,
    PlainAuxProjection,
    TeacherHead,
    derangement,
    make_targets,
    run_experiment,
    verify_controls,
)
from trunk import Trunk, TrunkConfig
from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY

B, T, N_NUM, TD = 4, 6, 5, 4


def gen(seed=0):
    return torch.Generator(device="cpu").manual_seed(seed)


def batch(seed=0, b=B, t=T, with_mask=True):
    g = gen(seed)
    out = {
        "numeric": torch.randn(b, t, N_NUM, generator=g),
        "dipole": torch.randn(b, t, TD, generator=g),
    }
    return out


def proj():
    return PlainAuxProjection(N_NUM, TD, seed=0)


# ------------------------------------------------ characterization (legacy)


def _legacy_plain_aux(dipole: torch.Tensor) -> torch.Tensor:
    """Verbatim reconstruction of the original control. Do not 'fix' this;
    its job is to stay broken so the test below keeps proving the defect."""
    g = torch.Generator(device="cpu").manual_seed(0)
    w = torch.randn(dipole.shape[-1], dipole.shape[-1], generator=g)
    return dipole.detach() @ w.to(dipole.device) * 0.0 + dipole.mean(
        dim=1, keepdim=True
    ).expand_as(dipole)


def test_legacy_plain_aux_leaked_the_dipole_target():
    d1 = batch(0)["dipole"]
    d2 = batch(1)["dipole"]
    t1, t2 = _legacy_plain_aux(d1), _legacy_plain_aux(d2)
    assert not torch.equal(t1, t2), "legacy control was a function of dipole"
    # And exactly what it leaked: the per-sequence time-mean of the target.
    assert torch.allclose(t1, d1.mean(dim=1, keepdim=True).expand_as(d1))


def test_legacy_randperm_can_return_identity():
    """torch.randperm has no fixed-point guarantee. Show it on B=2 within
    a modest number of draws; the corrected arm uses derangement()."""
    hits = 0
    for s in range(200):
        p = torch.randperm(2, generator=gen(s))
        hits += int(torch.equal(p, torch.arange(2)))
    assert hits > 0


# --------------------------------------------------------- plain_aux (new)


def test_plain_aux_is_invariant_to_the_dipole_target():
    b = batch(0)
    p = proj()
    a = make_targets("plain_aux", numeric=b["numeric"], dipole=b["dipole"],
                     generator=gen(), plain_aux=p).values
    c = make_targets("plain_aux", numeric=b["numeric"],
                     dipole=torch.randn_like(b["dipole"]),
                     generator=gen(), plain_aux=p).values
    assert torch.equal(a, c)


def test_plain_aux_depends_on_inputs():
    b = batch(0)
    p = proj()
    a = make_targets("plain_aux", numeric=b["numeric"], dipole=b["dipole"],
                     generator=gen(), plain_aux=p).values
    c = make_targets("plain_aux", numeric=b["numeric"] + 1.0, dipole=b["dipole"],
                     generator=gen(), plain_aux=p).values
    assert not torch.allclose(a, c)


def test_plain_aux_projection_is_fixed_across_instances_and_calls():
    b = batch(0)
    assert torch.equal(proj()(b["numeric"]), proj()(b["numeric"]))
    assert torch.equal(
        PlainAuxProjection(N_NUM, TD, seed=0).weight,
        PlainAuxProjection(N_NUM, TD, seed=0).weight,
    )
    assert not torch.equal(
        PlainAuxProjection(N_NUM, TD, seed=0).weight,
        PlainAuxProjection(N_NUM, TD, seed=1).weight,
    )


def test_plain_aux_has_no_dipole_argument():
    """Structural guarantee: the projection's call signature cannot even
    receive the target."""
    import inspect
    params = inspect.signature(PlainAuxProjection.__call__).parameters
    assert list(params) == ["self", "numeric"]


def test_plain_aux_target_does_not_carry_gradient_to_inputs():
    b = batch(0)
    x = b["numeric"].clone().requires_grad_(True)
    t = proj()(x)
    assert not t.requires_grad


def test_plain_aux_width_mismatch_is_loud():
    b = batch(0)
    with pytest.raises(ValueError, match="teacher_dim mismatch"):
        make_targets("plain_aux", numeric=b["numeric"], dipole=b["dipole"],
                     generator=gen(), plain_aux=PlainAuxProjection(N_NUM, TD + 1))


# ---------------------------------------------------------------- shuffled


@pytest.mark.parametrize("n", [2, 3, 4, 7, 16])
def test_derangement_never_has_a_fixed_point(n):
    for s in range(300):
        p = derangement(n, gen(s))
        assert not bool((p == torch.arange(n)).any())
        assert torch.equal(torch.sort(p).values, torch.arange(n))


def test_derangement_refuses_batch_of_one():
    with pytest.raises(ValueError, match="batch size >= 2"):
        derangement(1, gen())


def test_derangement_is_deterministic_per_seed():
    assert torch.equal(derangement(8, gen(5)), derangement(8, gen(5)))
    assert not torch.equal(derangement(8, gen(5)), derangement(8, gen(6)))


def test_shuffled_moves_every_row_and_keeps_marginals():
    b = batch(0)
    s = make_targets("shuffled", numeric=b["numeric"], dipole=b["dipole"],
                     generator=gen(), plain_aux=proj()).values
    for i in range(B):
        assert not torch.equal(s[i], b["dipole"][i])
    assert torch.equal(
        torch.sort(s.flatten(1), dim=0).values,
        torch.sort(b["dipole"].flatten(1), dim=0).values,
    )


# ------------------------------------------------------------------ random


def test_random_is_invariant_to_dipole_values_but_matches_shape():
    b = batch(0)
    r1 = make_targets("random", numeric=b["numeric"], dipole=b["dipole"],
                      generator=gen(), plain_aux=proj()).values
    r2 = make_targets("random", numeric=b["numeric"],
                      dipole=torch.zeros_like(b["dipole"]),
                      generator=gen(), plain_aux=proj()).values
    assert torch.equal(r1, r2)
    assert r1.shape == b["dipole"].shape
    assert not torch.allclose(r1, b["dipole"])


# --------------------------------------------------------- RNG contract


def test_non_cpu_generator_is_rejected():
    if not torch.cuda.is_available():
        pytest.skip("no CUDA device to build a non-CPU generator")
    b = batch(0)
    g = torch.Generator(device="cuda").manual_seed(0)
    with pytest.raises(ValueError, match="CPU generator"):
        make_targets("random", numeric=b["numeric"], dipole=b["dipole"],
                     generator=g, plain_aux=proj())


def test_targets_land_on_dipole_device_and_dtype():
    b = batch(0)
    d = b["dipole"].to(torch.float64)
    for arm in ("shuffled", "random"):
        t = make_targets(arm, numeric=b["numeric"].to(torch.float64), dipole=d,
                         generator=gen(), plain_aux=proj()).values
        assert t.device == d.device and t.dtype == d.dtype


# ------------------------------------------------------ verify_controls


def test_verify_controls_passes_on_a_sane_batch():
    verify_controls(batch(0), gen(), proj())


def test_verify_controls_rejects_a_leaking_plain_aux(monkeypatch):
    """PlainAuxProjection cannot see the target, so to simulate the
    legacy leak we have to reach past it and patch make_targets itself.
    That is the point: the only way to leak is to change the seam."""
    import teacher as T
    real = T.make_targets

    def leaking(arm, *, numeric, dipole, generator, plain_aux, dipole_mask=None):
        if arm == "plain_aux":
            return T.Targets(_legacy_plain_aux(dipole), torch.ones_like(dipole))
        return real(arm, numeric=numeric, dipole=dipole, dipole_mask=dipole_mask,
                    generator=generator, plain_aux=plain_aux)

    monkeypatch.setattr(T, "make_targets", leaking)
    with pytest.raises(RuntimeError, match="leak"):
        T.verify_controls(batch(0), gen(), proj())


def test_verify_controls_rejects_non_finite_dipole():
    b = batch(0)
    b["dipole"][0, 0, 0] = float("nan")
    with pytest.raises(RuntimeError, match="non-finite"):
        verify_controls(b, gen(), proj())


def test_verify_controls_does_not_consume_training_randomness():
    g = gen(3)
    before = g.get_state()
    verify_controls(batch(0), g, proj())
    assert torch.equal(before, g.get_state())


# -------------------------------------------------------------- masks


def test_mask_defaults_to_all_present():
    b = batch(0)
    t = make_targets("dipole", numeric=b["numeric"], dipole=b["dipole"],
                     generator=gen(), plain_aux=proj())
    assert torch.equal(t.mask, torch.ones_like(b["dipole"]))


def test_plain_aux_and_random_share_the_real_mask():
    b = batch(0)
    m = (torch.rand(B, T, TD, generator=gen(7)) > 0.4).float()
    for arm in ("plain_aux", "random", "dipole"):
        t = make_targets(arm, numeric=b["numeric"], dipole=b["dipole"],
                         dipole_mask=m, generator=gen(), plain_aux=proj())
        assert torch.equal(t.mask, m)


def test_shuffled_derangs_mask_with_values():
    b = batch(0)
    m = (torch.rand(B, T, TD, generator=gen(7)) > 0.4).float()
    t = make_targets("shuffled", numeric=b["numeric"], dipole=b["dipole"],
                     dipole_mask=m, generator=gen(3), plain_aux=proj())
    perm = derangement(B, gen(3))
    assert torch.equal(t.values, b["dipole"][perm])
    assert torch.equal(t.mask, m[perm])


def test_mask_shape_mismatch_is_loud():
    b = batch(0)
    with pytest.raises(ValueError, match="dipole_mask"):
        make_targets("dipole", numeric=b["numeric"], dipole=b["dipole"],
                     dipole_mask=torch.ones(B, T), generator=gen(), plain_aux=proj())


# ----------------------------------------------------------- harness


def cfg(**kw):
    base = dict(
        d_model=16, n_heads=2, n_layers=1, window=8,
        n_numeric=N_NUM, categorical_cardinalities=(4, 6),
        qsv_dim=len(QSV_FEATURE_REGISTRY), use_qsv=True,
        n_venues=3, n_instruments=5, n_regimes=3,
    )
    base.update(kw)
    return TrunkConfig(**base)


def trunk_batch(c, seed=0, b=B, t=T, mask=True):
    g = gen(seed)
    out = {
        "numeric": torch.randn(b, t, c.n_numeric, generator=g),
        "categorical": torch.stack(
            [torch.randint(0, n, (b, t), generator=g)
             for n in c.categorical_cardinalities], dim=-1),
        "venue_id": torch.randint(0, c.n_venues, (b, t), generator=g),
        "instrument_id": torch.randint(0, c.n_instruments, (b, t), generator=g),
        "parent": torch.cat(
            [torch.full((b, 1), -1), torch.zeros(b, t - 1, dtype=torch.long)], dim=1),
        "qsv": torch.randn(b, t, c.qsv_dim, generator=g),
        "label": torch.randint(0, 2, (b,), generator=g).float(),
        "dipole": torch.randn(b, t, TD, generator=g),
    }
    if mask:
        out["qsv_mask"] = (torch.rand(b, t, generator=g) > 0.3).float()
    return out


def test_harness_refuses_qsv_without_mask_by_default():
    c = cfg()
    with pytest.raises(ValueError, match="without qsv_mask"):
        run_experiment(
            build_model=lambda: Trunk(c),
            build_teacher=lambda: TeacherHead(c.d_model, TD),
            batches=[trunk_batch(c, mask=False)],
            val_batches=[trunk_batch(c, 9, mask=False)], seeds=(0,),
        )


def test_harness_forwards_qsv_mask_to_the_trunk():
    c = cfg()
    seen = []
    orig = Trunk.represent

    def spy(self, *a, **kw):
        seen.append(kw.get("qsv_mask"))
        return orig(self, *a, **kw)

    Trunk.represent = spy
    try:
        run_experiment(
            build_model=lambda: Trunk(c),
            build_teacher=lambda: TeacherHead(c.d_model, TD),
            batches=[trunk_batch(c)], val_batches=[trunk_batch(c, 9)], seeds=(0,),
        )
    finally:
        Trunk.represent = orig
    assert seen and all(m is not None for m in seen)


def test_harness_pairs_initialization_across_arms():
    c = cfg()
    rep = run_experiment(
        build_model=lambda: Trunk(c),
        build_teacher=lambda: TeacherHead(c.d_model, TD),
        batches=[trunk_batch(c)], val_batches=[trunk_batch(c, 9)], seeds=(0, 1),
    )
    assert len(rep.results) == len(ARMS) * 2
    for seed in (0, 1):
        digests = {r.init_digest for r in rep.results if r.seed == seed}
        assert len(digests) == 1
    assert len({r.init_digest for r in rep.results}) == 2  # seeds differ


def test_harness_refuses_shuffled_with_batch_of_one():
    c = cfg()
    with pytest.raises(ValueError, match="batch size >= 2"):
        run_experiment(
            build_model=lambda: Trunk(c),
            build_teacher=lambda: TeacherHead(c.d_model, TD),
            batches=[trunk_batch(c, b=1)], val_batches=[trunk_batch(c, 9)], seeds=(0,),
        )


def test_harness_reports_coverage_and_masks_the_aux_loss():
    c = cfg()
    tb = trunk_batch(c)
    tb["dipole_mask"] = (torch.rand(B, T, TD, generator=gen(11)) > 0.5).float()
    rep = run_experiment(
        build_model=lambda: Trunk(c),
        build_teacher=lambda: TeacherHead(c.d_model, TD),
        batches=[tb], val_batches=[trunk_batch(c, 9)], seeds=(0,),
    )
    cov = {r.arm: r.aux_coverage for r in rep.results}
    expected = float(tb["dipole_mask"].mean())
    for arm in ("plain_aux", "random", "dipole", "shuffled"):
        assert abs(cov[arm] - expected) < 1e-6   # derangement keeps the total
    assert cov["none"] == 1.0
