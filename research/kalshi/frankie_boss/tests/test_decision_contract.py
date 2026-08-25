"""
Falsification suite for the decision contract.

Emphasis on the properties that are load-bearing for audit:
  - decode is a pure projection (determinism)
  - no head output can raise into the caller
  - repair runs at most once and only when declared
  - abstentions carry the same stamp as decisions
  - evidence pointers must resolve into the originating packet
"""

import json

import pytest

from decision_contract import (
    AbstainReason,
    Abstention,
    Decision,
    DecisionEngine,
    DecisionSchema,
    FieldKind,
    FieldSpec,
    HeadOutput,
    IdentityCalibrator,
    shadow_compare,
)

PKT = "a" * 64
KEYS = ("q1", "q2", "q3")


def schema():
    return DecisionSchema(
        version="frankie/1",
        fields=(
            FieldSpec("p_up", FieldKind.PROBABILITY),
            FieldSpec("size", FieldKind.MAGNITUDE, lo=-1.0, hi=1.0),
            FieldSpec("regime", FieldKind.REGIME, choices=("trend", "chop", "shock")),
            FieldSpec("contradiction", FieldKind.CONTRADICTION),
            FieldSpec("evidence", FieldKind.EVIDENCE),
            FieldSpec("sigma", FieldKind.UNCERTAINTY),
        ),
    )


def engine(**kw):
    return DecisionEngine(schema(), IdentityCalibrator(**kw))


def good_head(**over):
    vals = {
        "p_up": 0.90,
        "size": 0.4,
        "regime": "trend",
        "contradiction": 0.1,
        "evidence": ["q1", "q2"],
        "sigma": 0.2,
    }
    vals.update(over)
    return HeadOutput(vals, PKT, "boss/2026.08.01")


def decide(e=None, head=None, keys=KEYS, degraded=()):
    return (e or engine()).decide(head or good_head(), keys, degraded)


# ------------------------------------------------------------ happy path


def test_emits_decision():
    d = decide()
    assert isinstance(d, Decision)
    assert not d.abstained
    assert d.payload["regime"] == "trend"
    assert d.repaired_fields == ()


def test_output_is_strict_json():
    d = decide()
    parsed = json.loads(d.to_json())
    assert parsed["abstained"] is False
    assert parsed["stamp"]["calibrator_version"] == "identity/1"
    assert parsed["stamp"]["packet_hash"] == PKT


def test_decode_is_deterministic():
    e = engine()
    a = e.decide(good_head(), KEYS)
    b = e.decide(good_head(), KEYS)
    assert a.to_json() == b.to_json()


# ------------------------------------------------- nothing escapes as raise


@pytest.mark.parametrize(
    "bad",
    [
        {"p_up": float("nan")},
        {"p_up": float("inf")},
        {"p_up": 1.5},
        {"p_up": -0.1},
        {"p_up": "high"},
        {"p_up": True},
        {"size": 99.0},
        {"regime": "melt-up"},
        {"regime": 3},
        {"sigma": -1.0},
        {"evidence": "q1"},
        {"evidence": [1, 2]},
    ],
)
def test_malformed_head_abstains_never_raises(bad):
    out = decide(head=good_head(**bad))
    assert isinstance(out, Abstention)
    assert out.reason is AbstainReason.CONTRACT_VIOLATION


def test_missing_required_field_abstains():
    vals = dict(good_head().values)
    del vals["regime"]
    out = decide(head=HeadOutput(vals, PKT, "boss/1"))
    assert isinstance(out, Abstention)
    assert "regime" in out.detail


def test_extra_field_abstains():
    out = decide(head=good_head(secret_alpha=1.0))
    assert isinstance(out, Abstention)
    assert "secret_alpha" in out.detail


# ------------------------------------------------------------------ repair


def test_declared_repair_runs_once_and_is_recorded():
    sch = DecisionSchema(
        version="v1",
        fields=(
            FieldSpec("p_up", FieldKind.PROBABILITY),
            FieldSpec(
                "size",
                FieldKind.MAGNITUDE,
                lo=-1.0,
                hi=1.0,
                repair=lambda v: max(-1.0, min(1.0, float(v))),
            ),
        ),
    )
    e = DecisionEngine(sch, IdentityCalibrator())
    out = e.decide(HeadOutput({"p_up": 0.9, "size": 5.0}, PKT, "m1"))
    assert isinstance(out, Decision)
    assert out.payload["size"] == 1.0
    assert out.repaired_fields == ("size",)


def test_undeclared_repair_does_not_happen():
    out = decide(head=good_head(size=5.0))
    assert isinstance(out, Abstention), "clamping without a declared repair is silent corruption"


def test_non_total_repair_abstains_rather_than_propagating():
    sch = DecisionSchema(
        version="v1",
        fields=(
            FieldSpec("p_up", FieldKind.PROBABILITY),
            FieldSpec(
                "size",
                FieldKind.MAGNITUDE,
                lo=-1.0,
                hi=1.0,
                repair=lambda v: 1 / 0,
            ),
        ),
    )
    e = DecisionEngine(sch, IdentityCalibrator())
    out = e.decide(HeadOutput({"p_up": 0.9, "size": 5.0}, PKT, "m1"))
    assert isinstance(out, Abstention)
    assert "ZeroDivisionError" in out.detail


def test_repair_that_still_violates_abstains():
    sch = DecisionSchema(
        version="v1",
        fields=(
            FieldSpec("p_up", FieldKind.PROBABILITY),
            FieldSpec("size", FieldKind.MAGNITUDE, lo=-1.0, hi=1.0, repair=lambda v: 42.0),
        ),
    )
    e = DecisionEngine(sch, IdentityCalibrator())
    out = e.decide(HeadOutput({"p_up": 0.9, "size": 5.0}, PKT, "m1"))
    assert isinstance(out, Abstention)
    assert "repair failed" in out.detail


# -------------------------------------------------------------- abstention


def test_low_confidence_abstains():
    out = decide(head=good_head(p_up=0.52))
    assert isinstance(out, Abstention)
    assert out.reason is AbstainReason.LOW_CONFIDENCE


def test_high_contradiction_abstains():
    out = decide(head=good_head(contradiction=0.9))
    assert isinstance(out, Abstention)
    assert out.reason is AbstainReason.HIGH_CONTRADICTION


def test_degraded_packet_abstains_before_anything_else():
    out = decide(degraded=("book: watermark lag 5s",))
    assert isinstance(out, Abstention)
    assert out.reason is AbstainReason.DEGRADED_PACKET


def test_malformed_field_beats_confidence_gate():
    """A broken field must not slip through by being confident."""
    out = decide(head=good_head(p_up=0.99, regime="nonsense"))
    assert out.reason is AbstainReason.CONTRACT_VIOLATION


def test_abstention_carries_full_stamp():
    out = decide(head=good_head(p_up=0.51))
    parsed = json.loads(out.to_json())
    assert parsed["abstained"] is True
    assert parsed["stamp"]["packet_hash"] == PKT
    assert parsed["stamp"]["model_version"] == "boss/2026.08.01"
    assert parsed["stamp"]["calibrator_version"] == "identity/1"
    assert parsed["stamp"]["schema_version"] == "frankie/1"


# ---------------------------------------------------------------- evidence


def test_dangling_evidence_pointer_abstains():
    out = decide(head=good_head(evidence=["q1", "ghost"]))
    assert isinstance(out, Abstention)
    assert out.reason is AbstainReason.UNRESOLVED_EVIDENCE
    assert "ghost" in out.detail


def test_evidence_resolving_into_packet_passes():
    out = decide(head=good_head(evidence=["q3"]))
    assert isinstance(out, Decision)


# ------------------------------------------------------------- calibration


def test_calibrator_version_travels_with_every_emission():
    e = DecisionEngine(schema(), IdentityCalibrator(version="platt/2026.08"))
    d = e.decide(good_head(), KEYS)
    assert d.calibrator_version == "platt/2026.08"


def test_calibrator_can_flip_the_outcome_and_it_is_attributable():
    strict = engine(confidence_floor=0.95)
    loose = engine(confidence_floor=0.10)
    head = good_head(p_up=0.80)
    assert isinstance(strict.decide(head, KEYS), Abstention)
    assert isinstance(loose.decide(head, KEYS), Decision)


# ------------------------------------------------------------------ shadow


def test_shadow_agreement():
    d = decide()
    frankie = dict(d.payload)
    diff = shadow_compare(d, frankie, schema())
    assert diff.agreed
    assert not diff.mismatched


def test_shadow_detects_drift():
    d = decide()
    frankie = dict(d.payload)
    frankie["size"] = frankie["size"] + 0.01
    diff = shadow_compare(d, frankie, schema())
    assert not diff.agreed
    assert "size" in diff.mismatched
    assert diff.field_deltas["size"] == pytest.approx(0.01)


def test_shadow_reports_abstention_asymmetry_directionally():
    a = shadow_compare(decide(head=good_head(p_up=0.51)), {"p_up": 0.51}, schema())
    assert a.new_abstained and not a.frankie_abstained
    assert not a.agreed

    b = shadow_compare(decide(), None, schema())
    assert b.frankie_abstained and not b.new_abstained
    assert not b.agreed


def test_both_abstaining_counts_as_agreement():
    diff = shadow_compare(decide(head=good_head(p_up=0.51)), None, schema())
    assert diff.agreed
