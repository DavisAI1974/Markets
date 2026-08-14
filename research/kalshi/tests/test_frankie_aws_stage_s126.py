from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_aws_stage_s126 as aws_stage  # noqa: E402
import group_config as gc  # noqa: E402


def _forcing(day: str, *, wind=0.25, solar=400.0):
    d = dt.date(int(day[:4]), int(day[4:6]), int(day[6:]))
    prior = d - dt.timedelta(days=1)
    stamp = prior.isoformat()
    return {
        "day": day,
        "cycle_utc": f"{stamp}T12:00:00Z",
        "knowable_from": f"{stamp}T13:00:00-04:00",
        "members_used": 31,
        "wind_cf_proxy": wind,
        "solar_irradiance_proxy": solar,
        "served_separately": True,
        "is_forecast_not_realized": True,
    }


def _write_fixture(tmp_path: Path, gid: str = "g24"):
    days = list(gc.GROUPS[gid]["days"])
    state = {day: {"weather_forcing_forecast": _forcing(day)} for day in days}
    (tmp_path / f"grp{gid[1:]}_state.json").write_text(json.dumps(state), encoding="utf-8")
    slices = tmp_path / f"{gid}_causal_slices"
    slices.mkdir()
    for day in days:
        sl = {d: state[d] for d in days if d <= day}
        (slices / f"state_{day}.json").write_text(json.dumps(sl), encoding="utf-8")
    return days, state, slices


def test_validate_served_forcing_accepts_complete_causal_state_and_slices(tmp_path):
    days, _, _ = _write_fixture(tmp_path)
    result = aws_stage.validate_served_forcing("g24", tmp_path)
    assert result["days"] == len(days)
    assert result["weather_forcing_forecast"] == "PASS"
    assert result["wind_solar_separate"] is True
    assert result["causal_slices"] == "PASS"


def test_validate_served_forcing_fails_on_missing_weather_block(tmp_path):
    days, state, _ = _write_fixture(tmp_path)
    state[days[0]].pop("weather_forcing_forecast")
    (tmp_path / "grp24_state.json").write_text(json.dumps(state), encoding="utf-8")
    with pytest.raises(aws_stage.StageInvariantError, match="has no weather_forcing_forecast"):
        aws_stage.validate_served_forcing("g24", tmp_path)


def test_validate_served_forcing_fails_on_stale_slice(tmp_path):
    days, state, slices = _write_fixture(tmp_path)
    day = days[0]
    sl_path = slices / f"state_{day}.json"
    sl = json.loads(sl_path.read_text(encoding="utf-8"))
    sl[day]["weather_forcing_forecast"] = _forcing(day, wind=0.99)
    sl_path.write_text(json.dumps(sl), encoding="utf-8")
    with pytest.raises(aws_stage.StageInvariantError, match="STale_slice|STALE_SLICE"):
        aws_stage.validate_served_forcing("g24", tmp_path)


def test_validate_served_forcing_fails_on_future_day_block(tmp_path):
    days, state, slices = _write_fixture(tmp_path)
    day = days[0]
    future = days[-1]
    sl_path = slices / f"state_{day}.json"
    sl = json.loads(sl_path.read_text(encoding="utf-8"))
    sl[future] = state[future]
    sl_path.write_text(json.dumps(sl), encoding="utf-8")
    with pytest.raises(aws_stage.StageInvariantError, match="CAUSAL_WALL"):
        aws_stage.validate_served_forcing("g24", tmp_path)
