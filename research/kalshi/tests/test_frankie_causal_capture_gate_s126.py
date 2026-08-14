from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import frankie_causal_capture_gate_s126 as gate  # noqa: E402


def _install_group(monkeypatch, gid="gtest"):
    days = ["20260720", "20260721"]
    monkeypatch.setitem(gate.gc.GROUPS, gid, {"days": days})
    return gid, days


def _write(tmp_path: Path, gid: str, days: list[str], *, future_stamp=False, future_block=False):
    d = tmp_path / f"{gid}_causal_slices"
    d.mkdir()
    state = {
        days[0]: {
            "storage_consensus": {
                "next_print": {
                    "consensus_pre_print_snapshot_utc": (
                        "2026-07-23T14:06:50Z" if future_stamp else "2026-07-19T14:06:50Z"
                    )
                }
            }
        },
        days[1]: {"storage_consensus": {"next_print": {"consensus_pre_print_snapshot_utc": None}}},
    }
    first = {days[0]: state[days[0]]}
    if future_block:
        first[days[1]] = state[days[1]]
    (d / f"state_{days[0]}.json").write_text(json.dumps(first), encoding="utf-8")
    (d / f"state_{days[1]}.json").write_text(json.dumps(state), encoding="utf-8")


def test_clean_slices_pass(monkeypatch, tmp_path):
    gid, days = _install_group(monkeypatch)
    _write(tmp_path, gid, days)
    result = gate.validate(gid, tmp_path)
    assert result["future_capture_stamps"] == 0
    assert result["causal_structure"] == "PASS"


def test_future_capture_stamp_fails_closed(monkeypatch, tmp_path):
    gid, days = _install_group(monkeypatch)
    _write(tmp_path, gid, days, future_stamp=True)
    with pytest.raises(gate.CausalCaptureError, match="future value-capture"):
        gate.validate(gid, tmp_path)


def test_future_day_block_still_fails_closed(monkeypatch, tmp_path):
    gid, days = _install_group(monkeypatch)
    _write(tmp_path, gid, days, future_block=True)
    with pytest.raises(gate.CausalCaptureError, match="causal structure"):
        gate.validate(gid, tmp_path)
