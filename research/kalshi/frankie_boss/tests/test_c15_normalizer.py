"""Contract tests for the isolated C15 normalizer, with no Torch import."""

import math
from dataclasses import replace
import hashlib
import struct
from statistics import median

import pytest

from c15_normalizer import (
    ABLATED_COLUMNS, COLUMNS, SCHEMA, Normalizer, NormalizerConfig, State,
)
from causal_packet import canonical_bytes

A1 = "far_front_age_log"
A3 = "far_size_hhi"


def new():
    return Normalizer(NormalizerConfig(instrument_ids=(10, 20)))


def emit(norm, value, column=A1, instrument=10, state=State.PRESENT):
    return norm.observe(instrument, column, value, state)


def f32(v):
    return struct.unpack("<f", struct.pack("<f", v))[0]


def reference(v, values, floor=0.05):
    loc = median(values)
    scale = max(1.4826 * median([abs(x - loc) for x in values]), floor)
    return f32(max(-8.0, min(8.0, (v - loc) / scale)))


def test_n1_exclusive_window_at_257th_present():
    norm = new()
    history = [float(i) for i in range(256)]
    for v in history:
        emit(norm, v)
    expected = reference(300.0, history)
    inclusive = reference(300.0, history + [300.0])
    assert expected != inclusive
    assert emit(norm, 300.0).value == expected


def test_n2_warmup_boundary_and_missing_invalid_not_counted():
    norm = new()
    for i in range(256):
        result = emit(norm, float(i))
        assert (result.state, result.reason, result.value) == (State.MISSING, "NORM_WARMUP", 0.0)
        emit(norm, 0.0, state=State.MISSING)
        emit(norm, 0.0, state=State.INVALID)
    assert emit(norm, 256.0).state == State.PRESENT


def test_n3_constant_floor_reports_zero():
    norm = new()
    for _ in range(300):
        result = emit(norm, 12.0)
    assert result.state == State.PRESENT
    assert result.value == 0.0
    assert result.floor_bound is True


def test_warmup_is_per_instrument_and_column():
    norm = new()
    for _ in range(256):
        emit(norm, 1.0)
    assert emit(norm, 1.0).state == State.PRESENT
    assert emit(norm, 1.0, instrument=20).reason == "NORM_WARMUP"
    assert emit(norm, 1.0, column=A3).reason == "NORM_WARMUP"


def test_nonpresent_never_emits_nonzero_or_fits():
    norm = new()
    before = norm.state_hash
    for state in (State.MISSING, State.INVALID, State.ABLATED):
        result = emit(norm, 0.0, state=state)
        assert result.state == state
        assert result.value == 0.0
    assert norm.state_hash == before


def test_n8_blocked_slots_have_no_state_or_present():
    norm = new()
    assert len(COLUMNS) == 19
    assert len(ABLATED_COLUMNS) == 6
    for col in ABLATED_COLUMNS:
        assert emit(norm, 0.0, column=col, state=State.ABLATED).state == State.ABLATED
        with pytest.raises(ValueError):
            emit(norm, 1.0, column=col)
    assert len(norm.export()["windows"]) == 2 * 13


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -float("inf"), True, "1", None])
def test_bad_present_values_rejected_without_state_change(bad):
    norm = new()
    before = norm.state_hash
    with pytest.raises(ValueError):
        emit(norm, bad)
    assert norm.state_hash == before


def test_unknown_instrument_column_or_state_rejected():
    norm = new()
    for args in [(30, A1, 1.0, State.PRESENT), (True, A1, 1.0, State.PRESENT),
                 (10, "invented", 1.0, State.PRESENT), (10, A1, 1.0, 99),
                 (10, A1, 1.0, True), (10, A1, 1.0, State.MISSING)]:
        with pytest.raises(ValueError):
            norm.observe(*args)


def digest(payload):
    return hashlib.sha256(SCHEMA.encode() + b"\x00" + canonical_bytes(payload)).hexdigest()


def test_n4_explicit_freeze_and_strict_frozen_restore():
    norm = new()
    history = list(map(float, range(256)))
    for v in history:
        emit(norm, v)
    payload, old_hash = norm.export(), norm.state_hash
    with pytest.raises(ValueError, match="config"):
        Normalizer.restore(replace(norm.config, mode="FROZEN"), payload, old_hash)
    restored = Normalizer.restore(norm.config, payload, old_hash)
    restored.freeze()
    frozen_hash = restored.state_hash
    assert frozen_hash != old_hash
    assert restored.export()["windows"][0]["values"] == payload["windows"][0]["values"]
    restored = Normalizer.restore(restored.config, restored.export(), frozen_hash)
    for v in range(1000):
        assert emit(restored, float(v)).value == reference(float(v), history)
    assert restored.state_hash == frozen_hash
    assert restored.normalizer_id == f"{SCHEMA}:FROZEN:{frozen_hash}"
    assert norm.normalizer_id == f"{SCHEMA}:UPDATING"


def test_warmup_stays_missing_after_freeze():
    norm = new()
    for _ in range(255):
        emit(norm, 0.0)
    norm.freeze()
    before = norm.state_hash
    for _ in range(300):
        assert emit(norm, 0.0).reason == "NORM_WARMUP"
    assert norm.state_hash == before


def test_n5_prefix_extension_and_equal_timestamp_suffix_do_not_change_output():
    prefix = [(i, float(i % 7)) for i in range(300)]
    suffix = [(299, 2.0), (299, 2.0), (300, -1000.0), (301, 1e8)]
    def run(rows):
        norm = new()
        # Availability order belongs to builder; timestamps are not fit values.
        return [emit(norm, value) for _, value in rows]
    assert run(prefix) == run(prefix + suffix)[:len(prefix)]


def test_n6_export_restore_every_cutoff_equals_continuous_and_split_steps():
    continuous, resumed = new(), new()
    for i in range(300):
        value = math.sin(i)
        expected = emit(continuous, value)
        actual = resumed.transform(10, A1, value)
        # A checkpoint between transform and update must preserve the exact window.
        resumed = Normalizer.restore(resumed.config, resumed.export(), resumed.state_hash)
        resumed.update(10, A1, value)
        resumed = Normalizer.restore(resumed.config, resumed.export(), resumed.state_hash)
        assert actual == expected
    assert resumed.state_hash == continuous.state_hash


def test_n7_window_bounded_with_exact_fifo_eviction():
    norm = new()
    for i in range(4100):
        norm.update(10, A1, float(i))
    slot = norm.export()["windows"][0]
    assert slot["values"] == list(map(float, range(4, 4100)))
    assert slot["n_present"] == 4100
    assert norm.transform(10, A1, 4100.0).value == reference(4100.0, slot["values"])


def test_export_and_restore_are_not_aliased_to_callers():
    norm = new()
    emit(norm, 1.0)
    payload, expected_hash = norm.export(), norm.state_hash
    restored = Normalizer.restore(norm.config, payload, expected_hash)
    payload["windows"][0]["values"][0] = 99.0
    payload["config"]["floors"][0] = 99.0
    assert restored.state_hash == norm.state_hash == expected_hash
    emit(restored, 2.0)
    assert restored.state_hash != norm.state_hash


@pytest.mark.parametrize("field,value", [("mode", "FROZEN"), ("n_norm", 8192),
    ("n_warm", 128), ("clip", 7.0), ("floors", (0.2,) * 19),
    ("instrument_ids", (10,))])
def test_restore_refuses_config_mismatch(field, value):
    norm = new()
    with pytest.raises(ValueError, match="config"):
        Normalizer.restore(replace(norm.config, **{field: value}), norm.export(), norm.state_hash)


@pytest.mark.parametrize("mutation", [
    lambda p: p.update(extra=1),
    lambda p: p.update(schema="wrong"),
    lambda p: p.update(candidate="wrong"),
    lambda p: p["windows"].pop(),
    lambda p: p["windows"].append(p["windows"][0]),
    lambda p: p["windows"][0].update(column="far_absorption_share_64"),
    lambda p: p["windows"][0].update(instrument_id=True),
    lambda p: p["windows"][0].update(n_present=-1),
    lambda p: p["windows"][0].update(n_present=True),
    lambda p: p["windows"][0].update(n_present=2),
    lambda p: p["windows"][0].update(values=[1.0]),
    lambda p: p["windows"][0].update(mode="FROZEN"),
    lambda p: p["windows"][0].update(extra=1),
    lambda p: p["config"].update(n_norm=True),
])
def test_restore_refuses_malformed_even_with_recomputed_hash(mutation):
    norm = new()
    payload = norm.export()
    mutation(payload)
    with pytest.raises(ValueError):
        Normalizer.restore(norm.config, payload, digest(payload))


def test_restore_checks_digest_and_finite_values():
    norm = new()
    emit(norm, 1.0)
    for bad in ("a" * 64, None, ""):
        with pytest.raises(ValueError):
            Normalizer.restore(norm.config, norm.export(), bad)
    for bad in (float("nan"), float("inf"), True, "1"):
        payload = norm.export()
        payload["windows"][0]["values"][0] = bad
        with pytest.raises(ValueError):
            Normalizer.restore(norm.config, payload, norm.state_hash)


def test_receipt_binds_code_config_and_state():
    norm = new()
    receipt = norm.receipt()
    assert receipt["config_hash"] == norm.config.config_hash
    assert receipt["state_hash"] == norm.state_hash
    import c15_normalizer
    from pathlib import Path
    content = Path(c15_normalizer.__file__).read_bytes()
    expected = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
    assert receipt["normalizer_code_sha"] == expected


def test_identity_has_no_statistics_warmup_and_preserves_blocked_slots():
    from c15_normalizer import IdentityNormalizer
    norm = IdentityNormalizer((10, 20))
    assert norm.normalizer_id == "C15_NORM_IDENTITY"
    result = emit(norm, 12.3)
    assert result.state == State.PRESENT
    assert result.value == f32(12.3)
    assert emit(norm, 0.0, state=State.MISSING).state == State.MISSING
    assert all(emit(norm, 0.0, column=c, state=State.ABLATED).state == State.ABLATED
               for c in ABLATED_COLUMNS)
    assert not norm.export()["windows"]


@pytest.mark.parametrize("kw", [
    {"instrument_ids": [10]}, {"instrument_ids": (10, 10)},
    {"instrument_ids": (True,)}, {"instrument_ids": ()},
    {"mode": "VALIDATION"}, {"n_norm": True}, {"n_warm": 4097},
    {"floors": (0.0,) * 19}, {"floors": (True,) * 19},
    {"clip": float("nan")}, {"clip": 1e100},
])
def test_invalid_config_rejected(kw):
    with pytest.raises(ValueError):
        NormalizerConfig(**{"instrument_ids": (10, 20), **kw})


def test_float32_emission_and_clipping_are_finite():
    norm = new()
    for _ in range(256):
        emit(norm, 0.0)
    assert norm.transform(10, A1, 1e308).value == 8.0
    assert norm.transform(10, A1, -1e308).value == -8.0
    assert norm.transform(10, A1, 0.0123).value == f32(0.0123 / 0.05)


def test_overflowing_statistics_rejected_before_observe_updates():
    norm = new()
    for _ in range(256):
        norm.update(10, A1, 1e308)
    before = norm.state_hash
    with pytest.raises(ValueError, match="statistics"):
        emit(norm, 1e308)
    assert norm.state_hash == before


def test_normalizer_config_cannot_be_reassigned():
    norm = new()
    with pytest.raises(AttributeError):
        norm.config = replace(norm.config, mode="FROZEN")


def test_config_hash_has_domain_separator():
    config = new().config
    expected = hashlib.sha256(b"C15_NORM_CONFIG_V1\x00" + canonical_bytes(config.payload())).hexdigest()
    assert config.config_hash == expected


def test_distinct_float64_windows_cannot_share_identity_and_differ_in_outputs():
    left, right = new(), new()
    for _ in range(256):
        left.update(10, A1, 1.0)
        right.update(10, A1, 1.0 + 1e-13)
    assert left.transform(10, A1, 1.0).value != right.transform(10, A1, 1.0).value
    assert left.state_hash != right.state_hash
    payload = left.export()
    payload["windows"][0]["values"][0] += 1e-13
    with pytest.raises(ValueError, match="float64"):
        Normalizer.restore(left.config, payload, left.state_hash)


def test_config_hash_binds_float64_floors_and_clip_exactly():
    config = new().config
    assert config.config_hash != replace(config, clip=config.clip + 1e-13).config_hash
    floors = list(config.floors)
    floors[0] += 1e-15
    assert config.config_hash != replace(config, floors=tuple(floors)).config_hash


def test_overflowing_numerator_does_not_silently_clip_finite_in_range_z():
    norm = new()
    for v in [-1.2e308] * 128 + [-8e307] * 129 + [-4e307] * 129:
        norm.update(10, A1, v)
    assert norm.transform(10, A1, 1.2e308).value == f32(5.0 / 1.4826)
