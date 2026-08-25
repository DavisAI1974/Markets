from __future__ import annotations

import sys
from pathlib import Path

from research.kalshi.frankie_boss.frankie_contract import (
    BLD1_FIELD_NAMES,
    INTERNAL_HEAD_TO_BLD1,
    FrankieProjector,
    InternalBLD1Heads,
)

KALSHI_ROOT = Path(__file__).resolve().parents[1]
if str(KALSHI_ROOT) not in sys.path:
    sys.path.insert(0, str(KALSHI_ROOT))
import frankie_s121_curve_restore as authoritative_bld1  # noqa: E402


PKT = "b" * 64


def _projector() -> FrankieProjector:
    return FrankieProjector("spec-a", "grp-1")


def _heads(**changes: object) -> InternalBLD1Heads:
    values: dict[str, object] = {
        "session_net_usd": 12_500.0,
        "overnight_gap_usd": -300.0,
        "session_path_p50_curve": (
            (20.0, 0.0),
            (22.0, 120.0),
            (0.0, 340.0),
            (17.0, 12_800.0),
        ),
        "confidence_label": "med",
        "internal_only": {
            "calibrated_call_probability": 0.82,
            "p_up": 0.91,
            "size": 0.4,
            "regime_logits": [0.1, 0.7, 0.2],
            "contradiction": 0.12,
            "sigma": 0.3,
            "evidence_scores": [1.0, 0.5],
        },
    }
    values.update(changes)
    return InternalBLD1Heads(**values)


def test_internal_head_mapping_is_exactly_the_four_deliberate_destinations() -> None:
    assert dict(INTERNAL_HEAD_TO_BLD1) == {
        "session_net_usd": "guessed_net_usd",
        "overnight_gap_usd": "overnight_gap_usd",
        "session_path_p50_curve": "path_p50_curve",
        "confidence_label": "confidence",
    }


def test_typed_internal_heads_project_to_the_complete_bld1_record() -> None:
    record = _projector().project_internal(
        "2026-08-24", _heads(), PKT, "boss/1", reasoning="mapped"
    )

    assert not record.abstained
    assert set(record.payload) == set(BLD1_FIELD_NAMES)
    assert record.payload["guessed_net_usd"] == 12_500.0
    assert record.payload["overnight_gap_usd"] == -300.0
    assert record.payload["path_p50_curve"] == [
        [20.0, 0.0],
        [22.0, 120.0],
        [0.0, 340.0],
        [17.0, 12_800.0],
    ]
    assert record.payload["confidence"] == "med"

    authoritative_bld1.validate_day(
        record.payload, "grp-1", "20260824", "spec-a"
    )


def test_additional_learned_quantities_stay_internal() -> None:
    record = _projector().project_internal(
        "2026-08-24", _heads(), PKT, "boss/1"
    )

    for internal_name in _heads().internal_only:
        assert internal_name not in record.payload


def test_abstain_disposition_preserves_the_mapped_market_forecast() -> None:
    record = _projector().project_internal(
        "2026-08-24",
        _heads(confidence_label="low"),
        PKT,
        "boss/1",
        reasoning="forecast retained; no trade authority",
        disposition="ABSTAIN",
    )

    assert record.abstained
    assert record.payload["guessed_net_usd"] == 12_500.0
    assert record.payload["path_p50_curve"][-1][1] == 12_800.0
    authoritative_bld1.validate_day(
        record.payload, "grp-1", "20260824", "spec-a"
    )


def test_curve_endpoint_must_equal_session_net_less_gap() -> None:
    record = _projector().project_internal(
        "2026-08-24",
        _heads(
            session_path_p50_curve=(
                (20.0, 0.0),
                (0.0, 100.0),
                (17.0, 12_500.0),
            )
        ),
        PKT,
        "boss/1",
    )

    assert record.abstained
    assert "path_p50_curve endpoint" in record.payload["state_defects_and_gaps_reported"][0]


def test_flat_scalar_path_is_not_the_bld1_time_value_curve() -> None:
    record = _projector().project_internal(
        "2026-08-24",
        _heads(session_path_p50_curve=(0.0, 120.0, 340.0, 12_800.0)),
        PKT,
        "boss/1",
    )

    assert record.abstained
    assert "path_p50_curve" in record.payload["state_defects_and_gaps_reported"][0]


def test_malformed_internal_head_output_abstains_at_the_existing_seam() -> None:
    record = _projector().project_internal(
        "2026-08-24",
        _heads(confidence_label="certain"),
        PKT,
        "boss/1",
    )

    assert record.abstained
    assert record.payload["state_defects_and_gaps_reported"]
