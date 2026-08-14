from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_s118_redo as s120  # noqa: E402
import frankie_s121_curve_restore as s121  # noqa: E402
import frankie_specialist_parity_s126 as parity  # noqa: E402


def _payload() -> dict:
    causal = {
        "20260427": {
            "storage": {"level": 2063, "weekly_chg": 103},
            "weather_forcing_forecast": {
                "wind": {"proxy": 0.5},
                "solar": {"proxy": 0.3},
            },
            "grid_stack": {"wind_mwh": 123, "solar_mwh": 45},
        }
    }
    plays = {"p1": {"body": "one"}, "p2": {"body": "two"}}
    return {
        "group": "g18",
        "day": "20260427",
        "realized_outcome_in_packet": False,
        "causal_slice": causal,
        "brain_view_served": {
            "plays": plays,
            "_frankie_serving": {
                "canonical_plays_total": 2,
                "full_plays_served": 2,
            },
        },
    }


def test_all_five_specialists_get_identical_complete_served_universe() -> None:
    source = _payload()
    causal = source["causal_slice"]
    brain = source["brain_view_served"]
    for spec in parity.SPECIALISTS:
        out = parity.attach_specialist_access(source, specialist=spec)
        assert out["causal_slice"] is causal
        assert out["brain_view_served"] is brain
        contract = out["specialist_access_contract"]
        assert contract["coordinator"] == "Frankie"
        assert contract["active_specialist"] == spec
        assert contract["specialists"] == list("ABCDE")
        assert contract["role_text_rewritten"] is False
        assert contract["frankie_settings_changed"] is False
        assert contract["frankie_schema_changed"] is False
        assert contract["frankie_inputs_changed"] is False
        assert contract["canonical_plays"] == contract["full_plays_served"] == 2
        assert "weather_forcing_forecast" in out["causal_slice"]["20260427"]


def test_blind_wall_stays_fail_closed() -> None:
    bad = _payload()
    bad["realized_outcome_in_packet"] = True
    with pytest.raises(s120.ForecastStop, match="realized outcome"):
        parity.attach_specialist_access(bad, specialist="A", phase="BLIND")


def test_reduced_brain_is_refused() -> None:
    bad = _payload()
    bad["brain_view_served"]["_frankie_serving"]["full_plays_served"] = 1
    with pytest.raises(s120.ForecastStop, match="reduced brain"):
        parity.attach_specialist_access(bad, specialist="E")


def test_s121_current_install_uses_parity_packet_and_keeps_curve_validator() -> None:
    s121.install()
    assert s120.base._packet is parity.packet
    assert s120.base._validate_day is s121.validate_day
