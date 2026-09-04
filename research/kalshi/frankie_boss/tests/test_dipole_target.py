"""
Falsification suite for DIPOLE_TEACHER_SCHEMA_V1.

Every test is a way the contract refuses a tensor. The one positive test
proves a valid target round-trips into the runner and its hash is stable.
"""

import pytest
import torch

from dipole_target import (
    SCHEMA_VERSION,
    DipoleTarget,
    DipoleTargetSpec,
    SchemaError,
    TargetState,
    masked_mse,
)

B, T = 3, 5
H = "a" * 64
H2 = "b" * 64
AS_OF = 1_700_000_000_000_000_000


def spec(**kw):
    base = dict(
        registry_id="refrag/qsv/test",
        target_names=("lean", "exhaustion", "dive", "coupling"),
        target_units=("bp", "bp", "bp", "ratio"),
        normalizer_id="zscore/oct1-train",
        builder_code_sha="c" * 40,
    )
    base.update(kw)
    return DipoleTargetSpec(**base)


def tensors(seed=0, k=4, present_frac=0.7):
    g = torch.Generator().manual_seed(seed)
    values = torch.randn(B, T, k, generator=g)
    states = torch.full((B, T, k), int(TargetState.PRESENT), dtype=torch.int8)
    miss = torch.rand(B, T, k, generator=g) > present_frac
    states[miss] = int(TargetState.MISSING)
    values[miss] = 0.0
    ts = torch.arange(1, T + 1, dtype=torch.int64).repeat(B, 1) * 1_000 + AS_OF - 10_000
    return values, states, ts


def target(**kw):
    v, s, ts = tensors()
    base = dict(
        spec=spec(), source_manifest_hash=H, source_prefix_hash=H2,
        as_of_ts_recv_ns=AS_OF, values=v, states=s, ts_recv_ns=ts,
    )
    base.update(kw)
    return DipoleTarget(**base)


# ---------------------------------------------------------------- spec


def test_spec_width_is_len_names():
    assert spec().width == 4


def test_spec_rejects_wrong_version():
    with pytest.raises(SchemaError, match="schema_version"):
        spec(schema_version="DIPOLE_TEACHER_SCHEMA_V0")
    assert spec().schema_version == SCHEMA_VERSION


def test_spec_rejects_empty_names():
    with pytest.raises(SchemaError, match="must not be empty"):
        spec(target_names=(), target_units=())


def test_spec_rejects_name_unit_length_mismatch():
    with pytest.raises(SchemaError, match="equal length"):
        spec(target_units=("bp",))


def test_spec_rejects_duplicate_names():
    with pytest.raises(SchemaError, match="unique"):
        spec(target_names=("a", "a", "b", "c"))


@pytest.mark.parametrize("field", ["registry_id", "normalizer_id", "builder_code_sha"])
def test_spec_rejects_blank_identity(field):
    with pytest.raises(SchemaError, match=field):
        spec(**{field: " "})


def test_spec_hash_is_deterministic_and_order_sensitive():
    assert spec().spec_hash == spec().spec_hash
    swapped = spec(target_names=("exhaustion", "lean", "dive", "coupling"))
    assert swapped.spec_hash != spec().spec_hash


# -------------------------------------------------------------- target


def test_valid_target_computes_hash_and_round_trips():
    t = target()
    assert len(t.target_hash) == 64
    again = target(target_hash=t.target_hash)
    assert again.target_hash == t.target_hash
    fields = t.to_batch_fields()
    assert set(fields) == {"dipole", "dipole_mask", "dipole_ts_recv_ns"}
    assert torch.equal(fields["dipole_mask"], t.mask)
    assert 0.0 < t.coverage < 1.0


def test_supplied_hash_mismatch_is_rejected():
    with pytest.raises(SchemaError, match="target_hash mismatch"):
        target(target_hash="0" * 64)


def test_hash_changes_when_any_content_changes():
    base = target().target_hash
    v, s, ts = tensors()
    v2 = v.clone()
    idx = (s == int(TargetState.PRESENT)).nonzero()[0]
    v2[tuple(idx)] += 1e-3
    assert target(values=v2).target_hash != base
    assert target(as_of_ts_recv_ns=AS_OF + 1).target_hash != base
    assert target(source_prefix_hash="d" * 64).target_hash != base


@pytest.mark.parametrize("field", ["source_manifest_hash", "source_prefix_hash"])
def test_provenance_hashes_must_be_sha256_hex(field):
    with pytest.raises(SchemaError, match=field):
        target(**{field: "not-a-hash"})
    with pytest.raises(SchemaError, match=field):
        target(**{field: "z" * 64})


def test_width_must_match_names():
    v, s, ts = tensors(k=5)
    with pytest.raises(SchemaError, match="width"):
        target(values=v, states=s)


def test_dtypes_are_enforced():
    v, s, ts = tensors()
    with pytest.raises(SchemaError, match="float32"):
        target(values=v.double())
    with pytest.raises(SchemaError, match="int8"):
        target(states=s.int())
    with pytest.raises(SchemaError, match="int64"):
        target(ts_recv_ns=ts.int())


def test_unknown_state_is_rejected():
    v, s, ts = tensors()
    s = s.clone(); s[0, 0, 0] = 7
    with pytest.raises(SchemaError, match="outside TargetState"):
        target(states=s)


def test_present_values_must_be_finite():
    v, s, ts = tensors()
    v = v.clone()
    idx = tuple((s == int(TargetState.PRESENT)).nonzero()[0])
    v[idx] = float("nan")
    with pytest.raises(SchemaError, match="finite"):
        target(values=v)


def test_non_present_values_must_be_exactly_zero():
    """The state carries the meaning. A stray number under MISSING is how
    present-zero and missing get confused downstream."""
    v, s, ts = tensors()
    v = v.clone()
    idx = tuple((s == int(TargetState.MISSING)).nonzero()[0])
    v[idx] = 0.5
    with pytest.raises(SchemaError, match="exactly 0.0"):
        target(values=v)


def test_ablated_and_invalid_are_distinct_from_missing():
    v, s, ts = tensors()
    s = s.clone()
    s[0, 0, 0] = int(TargetState.ABLATED); v[0, 0, 0] = 0.0
    s[0, 0, 1] = int(TargetState.INVALID); v[0, 0, 1] = 0.0
    t = target(values=v, states=s)
    counts = t.state_counts()
    assert counts["ABLATED"] == 1 and counts["INVALID"] == 1
    assert t.mask[0, 0, 0] == 0.0 and t.mask[0, 0, 1] == 0.0


# ------------------------------------------------------------ causality


def test_step_after_cutoff_is_an_answer_wall_violation():
    v, s, ts = tensors()
    ts = ts.clone(); ts[1, -1] = AS_OF + 1
    with pytest.raises(SchemaError, match="answer-wall"):
        target(ts_recv_ns=ts)


def test_timestamps_must_be_non_decreasing():
    v, s, ts = tensors()
    ts = ts.clone(); ts[0, 2] = ts[0, 1] - 1
    with pytest.raises(SchemaError, match="non-decreasing"):
        target(ts_recv_ns=ts)


def test_as_of_must_be_positive_int():
    with pytest.raises(SchemaError, match="positive"):
        target(as_of_ts_recv_ns=0)
    with pytest.raises(SchemaError, match="int"):
        target(as_of_ts_recv_ns=float(AS_OF))
    with pytest.raises(SchemaError, match="int"):
        target(as_of_ts_recv_ns=True)


def test_timestamp_shape_must_be_B_T():
    v, s, ts = tensors()
    with pytest.raises(SchemaError, match=r"\(B, T\)"):
        target(ts_recv_ns=ts[:, :-1])


# ------------------------------------------------------------- receipt


def test_receipt_identifies_the_target_exactly():
    t = target()
    r = t.receipt()
    assert r["schema_version"] == SCHEMA_VERSION
    assert r["target_hash"] == t.target_hash
    assert r["spec_hash"] == spec().spec_hash
    assert r["shape"] == [B, T, 4]
    assert sum(r["state_counts"].values()) == B * T * 4


# ------------------------------------------------------------------ loss


def test_masked_mse_ignores_non_present_entries():
    t = target()
    pred = t.values.clone()
    # Corrupt only masked-out entries: loss must stay zero.
    pred[t.mask == 0.0] = 99.0
    assert float(masked_mse(pred, t.values, t.mask)) == 0.0
    # Corrupt one present entry: loss must move.
    idx = tuple((t.mask == 1.0).nonzero()[0])
    pred[idx] += 1.0
    assert float(masked_mse(pred, t.values, t.mask)) > 0.0


def test_masked_mse_refuses_empty_mask():
    t = target()
    with pytest.raises(SchemaError, match="no PRESENT"):
        masked_mse(t.values, t.values, torch.zeros_like(t.mask))


def test_masked_mse_equals_plain_mse_when_all_present():
    x = torch.randn(2, 3, 4); y = torch.randn(2, 3, 4)
    assert torch.allclose(
        masked_mse(x, y, torch.ones_like(x)), torch.nn.functional.mse_loss(x, y)
    )
