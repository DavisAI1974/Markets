"""
Falsification suite for the causal packet builder.

Each test is written to FAIL if the leakage protection is removed. A
test that passes against a broken implementation is worthless, so
test_naive_event_time_filter_would_leak explicitly demonstrates the bug
the design exists to prevent -- if that test ever stops showing a
divergence, the fixture has gone stale and the rest of the suite is no
longer proving anything.
"""

import math
import random

import pytest

from causal_packet import (
    CausalPacket,
    CausalWindow,
    FeatureSpec,
    IncompletenessPolicy,
    LeakageError,
    PacketBuilder,
    Record,
    canonical_bytes,
)

NS = 1_000_000_000
T0 = 1_700_000_000 * NS


class ListSource:
    """Deliberately naive adapter: returns EVERYTHING, no filtering.

    This is the adversarial case. If the builder relies on adapters to
    filter, this source breaks it. The builder must filter itself.
    """

    def __init__(self, name, records, watermark_value=None):
        self.name = name
        self._records = list(records)
        self._wm = watermark_value

    def fetch(self, entity, as_of):
        return list(self._records)

    def watermark(self, entity, as_of):
        return self._wm if self._wm is not None else as_of


def mean_spec():
    def fn(w: CausalWindow):
        vals = w.values("book", "mid")
        return {
            "n": len(vals),
            "mean": sum(vals) / len(vals) if vals else float("nan"),
            "last": vals[-1] if vals else float("nan"),
        }

    return FeatureSpec("book_stats", "v1", fn, required_sources=("book",))


def base_records():
    return [
        Record("q1", T0 + 1 * NS, T0 + 1 * NS, {"mid": 100.0}),
        Record("q2", T0 + 2 * NS, T0 + 2 * NS, {"mid": 101.0}),
        Record("q3", T0 + 3 * NS, T0 + 3 * NS, {"mid": 102.0}),
    ]


def build(records, as_of, model="m1", calib="c1", policy=None, wm=None):
    b = PacketBuilder(
        sources=[ListSource("book", records, watermark_value=wm)],
        specs=[mean_spec()],
        policy=policy,
        code_version="test",
    )
    return b.build("BTC-USD", as_of, model, calib)


# ---------------------------------------------------------------- replay


def test_replay_is_byte_identical():
    recs = base_records()
    as_of = T0 + 10 * NS
    a = build(recs, as_of)
    b = build(list(reversed(recs)), as_of)  # source ordering must not matter
    assert a.hash == b.hash
    assert canonical_bytes(a.as_dict()) == canonical_bytes(b.as_dict())


def test_float_reduction_order_does_not_change_hash():
    """Different summation orders must not produce different packets."""
    vals = [random.uniform(-1e3, 1e3) for _ in range(200)]
    recs_a = [
        Record(f"q{i}", T0 + i * NS, T0 + i * NS, {"mid": v})
        for i, v in enumerate(vals)
    ]
    shuffled = list(range(200))
    random.shuffle(shuffled)
    recs_b = [
        Record(f"q{i}", T0 + i * NS, T0 + i * NS, {"mid": vals[i]}) for i in shuffled
    ]
    as_of = T0 + 500 * NS
    assert build(recs_a, as_of).hash == build(recs_b, as_of).hash


# --------------------------------------------------------------- leakage


def test_future_ingest_is_invisible():
    recs = base_records()
    as_of = T0 + 5 * NS
    clean = build(recs, as_of)

    # A restatement of q2. It HAPPENED before as_of but was only known
    # afterwards. It must not touch the packet.
    late = Record("q2", T0 + 2 * NS, T0 + 9 * NS, {"mid": 999.0}, version=1)
    with_late = build(recs + [late], as_of)

    assert with_late.hash == clean.hash
    assert with_late.features["book_stats.n"] == 3
    assert with_late.features["book_stats.mean"] == pytest.approx(101.0)


def test_restatement_known_in_time_is_used():
    recs = base_records()
    as_of = T0 + 5 * NS
    revised = Record("q2", T0 + 2 * NS, T0 + 4 * NS, {"mid": 200.0}, version=1)
    p = build(recs + [revised], as_of)
    assert p.features["book_stats.n"] == 3  # replaced, not appended
    assert p.features["book_stats.mean"] == pytest.approx((100.0 + 200.0 + 102.0) / 3)


def test_naive_event_time_filter_would_leak():
    """Proof the suite has teeth.

    Reproduces what an event_time filter would have admitted, and
    asserts it differs from the correct answer. If these ever agree,
    the fixture no longer exercises the bug.
    """
    recs = base_records()
    late = Record("q2", T0 + 2 * NS, T0 + 9 * NS, {"mid": 999.0}, version=1)
    as_of = T0 + 5 * NS
    correct = build(recs + [late], as_of).features["book_stats.mean"]

    # What a naive implementation does: filter on event_time.
    naive_rows = {}
    for r in recs + [late]:
        if r.event_time <= as_of:
            prev = naive_rows.get(r.key)
            if prev is None or r.version > prev.version:
                naive_rows[r.key] = r
    naive = sum(r.payload["mid"] for r in naive_rows.values()) / len(naive_rows)

    assert naive != pytest.approx(correct), "fixture stale: bug no longer reproduced"
    assert naive == pytest.approx((100.0 + 999.0 + 102.0) / 3)


def test_records_after_as_of_excluded():
    recs = base_records() + [
        Record("q4", T0 + 20 * NS, T0 + 20 * NS, {"mid": 500.0})
    ]
    p = build(recs, T0 + 5 * NS)
    assert p.features["book_stats.n"] == 3
    assert p.features["book_stats.last"] == pytest.approx(102.0)


def test_unsound_clock_rejected():
    with pytest.raises(LeakageError):
        Record("bad", T0 + 10 * NS, T0 + 1 * NS, {"mid": 1.0})


def test_window_cannot_reach_unknown_source():
    def fn(w: CausalWindow):
        return {"x": len(w.records("qsv"))}

    b = PacketBuilder(
        [ListSource("book", base_records())],
        [FeatureSpec("bad", "v1", fn)],
        code_version="test",
    )
    with pytest.raises(KeyError):
        b.build("BTC-USD", T0 + 5 * NS, "m1", "c1")


# ------------------------------------------------------- stamp and audit


def test_calibrator_version_changes_the_hash():
    """The gap this closes: adaptive calibration outside the registry."""
    recs = base_records()
    as_of = T0 + 5 * NS
    a = build(recs, as_of, calib="c1")
    b = build(recs, as_of, calib="c2")
    assert a.features == b.features
    assert a.hash != b.hash, "calibrator drift would be unattributable"


def test_model_version_changes_the_hash():
    recs = base_records()
    as_of = T0 + 5 * NS
    assert build(recs, as_of, model="m1").hash != build(recs, as_of, model="m2").hash


def test_provenance_records_only_touched_sources():
    p = build(base_records(), T0 + 5 * NS)
    assert p.provenance["book_stats"] == ("book",)


# -------------------------------------------------------- incompleteness


def test_watermark_lag_is_recorded_not_filled():
    as_of = T0 + 10 * NS
    policy = IncompletenessPolicy({"book": 1 * NS})
    p = build(base_records(), as_of, policy=policy, wm=T0 + 3 * NS)
    assert p.degraded, "trailing watermark must be surfaced"
    assert "book" in p.degraded[0]
    # and it must change the hash, so a degraded decision is auditable
    clean = build(base_records(), as_of, policy=policy, wm=as_of)
    assert p.hash != clean.hash


def test_hard_fail_policy_raises():
    policy = IncompletenessPolicy({"book": 1 * NS}, hard_fail=True)
    with pytest.raises(LeakageError):
        build(base_records(), T0 + 10 * NS, policy=policy, wm=T0 + 3 * NS)


# ------------------------------------------------------- canonical bytes


def test_zero_signs_collapse():
    assert canonical_bytes({"a": 0.0}) == canonical_bytes({"a": -0.0})


def test_nan_is_stable():
    assert canonical_bytes({"a": float("nan")}) == canonical_bytes({"a": float("nan")})


def test_last_bit_drift_absorbed():
    x = 0.1 + 0.2  # 0.30000000000000004
    assert canonical_bytes({"a": x}) == canonical_bytes({"a": 0.3})


def test_genuine_difference_survives_quantization():
    assert canonical_bytes({"a": 1.0}) != canonical_bytes({"a": 1.0000001})
