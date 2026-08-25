"""
Falsification suite for the corrected seam.

Three properties carry the most weight:
  - ts_recv_ns is the visibility gate and ts_event_ns can never become one
  - an ABSTAIN record is complete, not truncated
  - reasoning cannot move the determinism digest
"""

import json

import pytest
import torch

from causal_packet import IncompletenessPolicy, PacketBuilder, FeatureSpec, CausalWindow
from databento_adapter import (
    CAUSAL_AVAILABILITY_CLOCK,
    DatabentoMBOSource,
    MBORow,
    SkewPolicy,
)
from frankie_contract import (
    BLD1_FIELD_NAMES,
    CallerError,
    ContractError,
    Disposition,
    FrankieProjector,
    validate_bld1,
)
from trunk import Trunk, TrunkConfig
from research.refrag.qsv_registry import QSV_FEATURE_REGISTRY

NS = 1_000_000_000
T0 = 1_700_000_000 * NS
PKT = "b" * 64


# ------------------------------------------------------- causal clock


def test_clock_declaration_matches_markets_replay():
    assert CAUSAL_AVAILABILITY_CLOCK == "ts_recv_ns"


def rows():
    return [
        MBORow("m1", T0 + 1 * NS, T0 + 1 * NS, 500, {"px": 100.0}),
        MBORow("m2", T0 + 3 * NS, T0 + 2 * NS, 900, {"px": 101.0}),  # 1s recv lag
        MBORow("m3", T0 + 9 * NS, T0 + 4 * NS, 700, {"px": 102.0}),  # late arrival
    ]


def src(rs=None, policy=None):
    data = rs if rs is not None else rows()
    return DatabentoMBOSource("mbo", lambda e: data, policy=policy)


def test_visibility_gate_is_ts_recv_not_ts_event():
    """m3 happened at +4s but only arrived at +9s. At as_of=+5s it is
    invisible, even though its event time is in the past."""
    got = src().fetch("ES", T0 + 5 * NS)
    assert {r.key for r in got} == {"m1", "m2"}


def test_ts_event_filter_would_have_admitted_the_late_row():
    """Teeth check: confirm the two clocks actually disagree here."""
    naive = [r for r in rows() if r.ts_event_ns <= T0 + 5 * NS]
    assert "m3" in {r.key for r in naive}
    correct = {r.key for r in src().fetch("ES", T0 + 5 * NS)}
    assert "m3" not in correct


def test_ingest_time_is_recv_and_event_time_is_event():
    rec = {r.key: r for r in src().fetch("ES", T0 + 20 * NS)}["m3"]
    assert rec.ingest_time == T0 + 9 * NS
    assert rec.event_time == T0 + 4 * NS


def test_in_delta_is_provenance_only():
    rec = {r.key: r for r in src().fetch("ES", T0 + 20 * NS)}["m1"]
    assert rec.payload["ts_in_delta_ns"] == 500
    assert rec.ingest_time == T0 + 1 * NS  # unaffected by in_delta


# ------------------------------------------------------------- skew


def skewed():
    return [
        MBORow("ok", T0 + 2 * NS, T0 + 1 * NS, 100, {"px": 1.0}),
        MBORow("bad", T0 + 2 * NS, T0 + 6 * NS, 100, {"px": 2.0}),  # recv < event
    ]


def test_skewed_row_is_quarantined_not_admitted():
    s = src(skewed())
    got = s.fetch("ES", T0 + 10 * NS)
    assert {r.key for r in got} == {"ok"}, "a row visible before it happened is lookahead"
    assert s.stats.quarantined_skew == 1


def test_quarantine_is_reported_not_silent():
    s = src(skewed())
    s.fetch("ES", T0 + 10 * NS)
    defects = s.defects()
    assert defects and "quarantined" in defects[0]


def test_high_skew_rate_flags_the_feed():
    s = src(skewed(), policy=SkewPolicy(max_quarantine_rate=0.0001))
    s.fetch("ES", T0 + 10 * NS)
    assert any("clock discipline is unsound" in d for d in s.defects())


def test_tolerance_admits_small_inversions():
    s = src(skewed(), policy=SkewPolicy(tolerance_ns=5 * NS))
    got = s.fetch("ES", T0 + 10 * NS)
    assert {r.key for r in got} == {"ok"}, "still excluded: Record itself rejects it"
    assert s.stats.quarantined_skew == 1


def test_adapter_plugs_into_the_packet_builder():
    def fn(w: CausalWindow):
        v = w.values("mbo", "px")
        return {"n": len(v), "last": v[-1] if v else float("nan")}

    b = PacketBuilder(
        [src()], [FeatureSpec("mbo_stats", "v1", fn, ("mbo",))], code_version="t"
    )
    p = b.build("ES", T0 + 5 * NS, "boss/1", "cal/1")
    assert p.features["mbo_stats.n"] == 2
    assert p.features["mbo_stats.last"] == pytest.approx(101.0)


# ------------------------------------------------------------ BLD-1


def proj(**kw):
    return FrankieProjector("spec-a", "grp-1", **kw)


def good_heads(**over):
    h = {
        "guessed_net_usd": 12500.0,
        "overnight_gap_usd": -300.0,
        "path_p50_curve": [
            [20.0, 0.0],
            [22.0, 120.0],
            [0.0, 340.0],
            [17.0, 12800.0],
        ],
        "confidence": "med",
    }
    h.update(over)
    return h


def test_call_record_has_all_twelve_fields():
    r = proj().project(
        "2026-08-24", good_heads(), PKT, "boss/1", reasoning="projection"
    )
    assert not r.abstained
    assert set(r.payload) == set(BLD1_FIELD_NAMES)
    assert len(BLD1_FIELD_NAMES) == 12


def test_abstain_record_is_complete_not_truncated():
    r = proj().abstain("2026-08-24", ["feed down"], PKT, "boss/1")
    assert set(r.payload) == set(BLD1_FIELD_NAMES)
    assert r.payload["disposition"] == Disposition.ABSTAIN.value
    assert r.payload["guessed_net_usd"] == 0.0
    assert r.payload["overnight_gap_usd"] == 0.0
    assert r.payload["plays_fired"] == []
    assert r.payload["confidence"] == "low"
    assert r.payload["state_defects_and_gaps_reported"] == ["feed down"]
    assert None not in r.payload.values(), "zeroed, never null"


def test_packet_defects_land_in_the_defect_field():
    r = proj().project(
        "2026-08-24", good_heads(), PKT, "boss/1",
        packet_defects=["mbo: watermark lag 4s"],
    )
    assert r.abstained
    assert r.payload["state_defects_and_gaps_reported"] == ["mbo: watermark lag 4s"]


def test_low_confidence_is_independent_of_trade_disposition():
    r = proj().project(
        "2026-08-24", good_heads(confidence="low"), PKT, "boss/1",
        reasoning="low-confidence forecast",
        plays_fired=["p1", "p2"], plays_stood_down=["p3"],
    )
    assert not r.abstained
    assert r.payload["plays_fired"] == ["p1", "p2"]
    assert r.payload["plays_stood_down"] == ["p3"]


def test_numeric_confidence_thresholds_are_not_invented_by_the_adapter():
    with pytest.raises(ValueError, match=r"low\|med\|high"):
        proj(confidence_floor=0.9)


@pytest.mark.parametrize(
    "bad",
    [
        {"guessed_net_usd": float("nan")},
        {"guessed_net_usd": "lots"},
        {"overnight_gap_usd": float("inf")},
        {"path_p50_curve": []},
        {"path_p50_curve": [[20.0, 0.0], [17.0, float("nan")]]},
        {"path_p50_curve": [[20.0, 0.0], [float("inf"), 12500.0]]},
        {"path_p50_curve": [[20.0, 0.0, 1.0], [17.0, 12500.0]]},
        {"path_p50_curve": 12500.0},
        {"confidence": 1.4},
        {"confidence": "certain"},
    ],
)
def test_malformed_head_abstains_never_raises(bad):
    r = proj().project(
        "2026-08-24", good_heads(**bad), PKT, "boss/1", reasoning="projection"
    )
    assert r.abstained
    assert r.payload["state_defects_and_gaps_reported"]


def test_missing_head_field_abstains():
    h = good_heads()
    del h["path_p50_curve"]
    r = proj().project("2026-08-24", h, PKT, "boss/1", reasoning="projection")
    assert r.abstained
    assert "head_output_malformed" in r.payload["state_defects_and_gaps_reported"][0]


def test_extra_field_is_rejected_at_the_seam():
    payload = {n: v for n, v in proj().abstain("2026-08-24", [], PKT, "m").payload.items()}
    payload["secret_alpha"] = 1.0
    with pytest.raises(ContractError, match="outside BLD-1"):
        validate_bld1(payload)


def test_bad_date_is_a_caller_error_not_an_abstention():
    """A malformed date has no valid ABSTAIN record either -- date is
    required. Abstaining would have hidden a caller bug, and the first
    version of this code did exactly that: project() caught the error,
    called abstain(), and abstain() raised the same error again."""
    with pytest.raises(CallerError):
        proj().project(
            "24-08-2026", good_heads(), PKT, "boss/1", reasoning="projection"
        )
    with pytest.raises(CallerError):
        proj().abstain("24-08-2026", ["x"], PKT, "boss/1")


def test_disposition_must_be_call_or_abstain():
    payload = dict(
        proj().project(
            "2026-08-24", good_heads(), PKT, "b", reasoning="projection"
        ).payload
    )
    payload["disposition"] = "MAYBE"
    with pytest.raises(ContractError):
        validate_bld1(payload)


# -------------------------------------------------------- determinism


def test_reasoning_does_not_move_the_determinism_digest():
    a = proj().project("2026-08-24", good_heads(), PKT, "b", reasoning="short")
    b = proj().project(
        "2026-08-24", good_heads(), PKT, "b", reasoning="a much longer rewrite"
    )
    assert a.determinism_digest() == b.determinism_digest()
    assert a.reasoning_digest() != b.reasoning_digest()


def test_a_real_change_does_move_the_digest():
    a = proj().project(
        "2026-08-24", good_heads(), PKT, "b", reasoning="projection"
    )
    b = proj().project(
        "2026-08-24",
        good_heads(
            guessed_net_usd=12501.0,
            path_p50_curve=[
                [20.0, 0.0],
                [22.0, 120.0],
                [0.0, 340.0],
                [17.0, 12801.0],
            ],
        ),
        PKT,
        "b",
        reasoning="projection",
    )
    assert a.determinism_digest() != b.determinism_digest()


def test_calibrator_version_moves_the_digest():
    a = proj(calibrator_version="c1").project(
        "2026-08-24", good_heads(), PKT, "b", reasoning="projection"
    )
    b = proj(calibrator_version="c2").project(
        "2026-08-24", good_heads(), PKT, "b", reasoning="projection"
    )
    assert a.determinism_digest() != b.determinism_digest()


def test_emission_is_valid_json_with_both_digests():
    r = proj().project("2026-08-24", good_heads(), PKT, "b", reasoning="x")
    parsed = json.loads(r.to_json())
    assert parsed["stamp"]["contract_id"] == "BLD-1"
    assert parsed["stamp"]["adapter_id"] == "S120/S121"
    assert len(parsed["stamp"]["reasoning_digest"]) == 16
    assert set(parsed["payload"]) == set(BLD1_FIELD_NAMES)


# ---------------------------------------------------------------- QSV


def tcfg(**kw):
    base = dict(
        d_model=16, n_heads=2, n_layers=1, window=8, n_numeric=4,
        categorical_cardinalities=(3,), n_venues=2, n_instruments=3,
    )
    base.update(kw)
    return TrunkConfig(**base)


def tbatch(c, b=2, t=6):
    g = torch.Generator().manual_seed(0)
    return dict(
        numeric=torch.randn(b, t, c.n_numeric, generator=g),
        categorical=torch.randint(0, 3, (b, t, 1), generator=g),
        venue_id=torch.randint(0, c.n_venues, (b, t), generator=g),
        instrument_id=torch.randint(0, c.n_instruments, (b, t), generator=g),
        parent=torch.full((b, t), -1),
        qsv=torch.randn(b, t, c.qsv_dim, generator=g) if c.qsv_dim else None,
    )


def test_default_qsv_dim_is_the_named_registry_and_branch_is_dormant():
    c = TrunkConfig()
    assert c.qsv_dim == len(QSV_FEATURE_REGISTRY)
    assert c.use_qsv is False


def test_wrong_qsv_width_is_caught_with_a_registry_hint():
    c = tcfg(use_qsv=True)
    m = Trunk(c).eval()
    b = tbatch(c)
    with pytest.raises(ValueError, match="QSV_FEATURE_REGISTRY"):
        m.represent(
            b["numeric"], b["categorical"], b["venue_id"],
            b["instrument_id"], b["parent"],
            torch.randn(2, 6, c.qsv_dim - 1),
        )


def test_qsv_mask_gates_the_stream():
    c = tcfg(use_qsv=True)
    m = Trunk(c).eval()
    b = tbatch(c)
    args = (b["numeric"], b["categorical"], b["venue_id"], b["instrument_id"], b["parent"])
    with torch.no_grad():
        on = m.represent(*args, b["qsv"], torch.ones(2, 6))
        off = m.represent(*args, b["qsv"], torch.zeros(2, 6))
        off_other = m.represent(
            *args, torch.randn(2, 6, c.qsv_dim), torch.zeros(2, 6)
        )
    assert not torch.allclose(on, off)
    # The property that matters: masked off, QSV values cannot reach the
    # representation at all. Note this is stricter than passing zeros --
    # a zero input still lets the projection bias through, which is why
    # masking and zero-filling are not interchangeable.
    assert torch.equal(off, off_other)


@pytest.mark.parametrize("unavailable", [float("nan"), float("inf")])
def test_masked_nonfinite_qsv_is_exactly_absent(unavailable):
    c = tcfg(use_qsv=True)
    m = Trunk(c).eval()
    b = tbatch(c)
    args = (b["numeric"], b["categorical"], b["venue_id"], b["instrument_id"], b["parent"])
    poisoned = torch.full((2, 6, c.qsv_dim), unavailable)
    finite = torch.randn(2, 6, c.qsv_dim)
    mask = torch.zeros(2, 6)
    with torch.no_grad():
        absent_poisoned = m.represent(*args, poisoned, mask)
        absent_finite = m.represent(*args, finite, mask)
    assert torch.isfinite(absent_poisoned).all()
    assert torch.equal(absent_poisoned, absent_finite)


def test_present_nonfinite_qsv_fails_closed():
    c = tcfg(use_qsv=True)
    m = Trunk(c).eval()
    b = tbatch(c)
    args = (b["numeric"], b["categorical"], b["venue_id"], b["instrument_id"], b["parent"])
    poisoned = torch.full((2, 6, c.qsv_dim), float("nan"))
    with pytest.raises(ValueError, match="present qsv values must be finite"):
        m.represent(*args, poisoned, torch.ones(2, 6))


def test_ablation_is_exact():
    c = tcfg(use_qsv=True)
    m = Trunk(c).eval()
    b = tbatch(c)
    args = (b["numeric"], b["categorical"], b["venue_id"], b["instrument_id"], b["parent"])
    with torch.no_grad():
        before = m.represent(*args, b["qsv"])
        m.encoder.ablate_qsv()
        after = m.represent(*args, b["qsv"])
        other = m.represent(*args, torch.randn(2, 6, c.qsv_dim))
    assert not torch.allclose(before, after)
    assert torch.equal(after, other), "ablated stream must be exactly inert"


@pytest.mark.parametrize("unavailable", [float("nan"), float("inf")])
def test_ablated_nonfinite_qsv_is_exactly_absent(unavailable):
    c = tcfg(use_qsv=True)
    m = Trunk(c).eval()
    b = tbatch(c)
    args = (b["numeric"], b["categorical"], b["venue_id"], b["instrument_id"], b["parent"])
    poisoned = torch.full((2, 6, c.qsv_dim), unavailable)
    finite = torch.randn(2, 6, c.qsv_dim)
    m.encoder.ablate_qsv()
    with torch.no_grad():
        absent_poisoned = m.represent(*args, poisoned)
        absent_finite = m.represent(*args, finite)
    assert torch.isfinite(absent_poisoned).all()
    assert torch.equal(absent_poisoned, absent_finite)


def test_ablated_qsv_stream_requires_no_payload():
    c = tcfg(use_qsv=True)
    m = Trunk(c).eval()
    b = tbatch(c)
    args = (b["numeric"], b["categorical"], b["venue_id"], b["instrument_id"], b["parent"])
    m.encoder.ablate_qsv()
    with torch.no_grad():
        absent = m.represent(*args, None)
    assert torch.isfinite(absent).all()
