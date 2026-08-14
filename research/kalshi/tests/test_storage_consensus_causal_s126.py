from __future__ import annotations

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import storage_consensus as sc  # noqa: E402


def _report(*, release="2026-07-23", observed="2026-07-23T14:06:50Z", value=29.0):
    return {
        "for_report_date": "2026-07-17",
        "print_date": release,
        "print_dow": "Thu",
        "print_time_et": "10:30",
        "print_datetime_utc": f"{release}T14:30:00Z",
        "print_schedule_note": "fixture",
        "nominal_release_date": release,
        "consensus_chg_bcf": value,
        "source": "fixture-source",
        "consensus_pre_print_bcf": value,
        "consensus_pre_print_snapshot_utc": observed,
        "n_estimates": 1,
        "range_low_bcf": None,
        "range_high_bcf": None,
        "house_disagreement_bcf": None,
        "actual_current_vintage_bcf": 31.0,
        "actual_as_printed_bcf": 31.0,
        "actual_as_printed_source": "fixture-actual",
        "estimates": [
            {
                "source": "fixture-source",
                "value_bcf": value,
                "pre_print": True,
                "snapshot_utc": observed,
                "actual_on_page_bcf": 31.0,
            }
        ],
    }


def _serve(day: str, report: dict):
    sc._CACHE = {"store": {"reports": [report]}, "surprise": {}}
    return sc.storage_consensus_asof(day)


def test_future_capture_cannot_travel_backward_into_earlier_decision_day():
    view = _serve("2026-07-20", _report())
    nxt = view["next_print"]
    assert nxt["print_date"] == "2026-07-23"
    assert nxt["consensus_chg_bcf"] is None
    assert nxt["consensus_pre_print_snapshot_utc"] is None
    assert nxt["estimates"] == []


def test_same_day_capture_after_0800_et_open_is_withheld():
    # 14:06:50Z = 10:06:50 ET in July, after the 08:00 ET decision cutoff.
    view = _serve("2026-07-23", _report())
    assert view["next_print"]["consensus_chg_bcf"] is None
    assert view["next_print"]["estimates"] == []


def test_same_day_capture_before_0800_et_open_is_legal():
    # 08:49:47Z = 04:49:47 ET in August, strictly before the 08:00 ET cutoff.
    report = _report(release="2026-08-13", observed="2026-08-13T08:49:47Z", value=31.0)
    view = _serve("2026-08-13", report)
    nxt = view["next_print"]
    assert nxt["consensus_chg_bcf"] == 31.0
    assert nxt["consensus_pre_print_snapshot_utc"] == "2026-08-13T08:49:47Z"
    assert len(nxt["estimates"]) == 1
    assert "actual_on_page_bcf" not in nxt["estimates"][0]


def test_prior_day_capture_is_legal_for_upcoming_print():
    report = _report(observed="2026-07-22T18:00:00Z")
    view = _serve("2026-07-23", report)
    assert view["next_print"]["consensus_chg_bcf"] == 29.0
    assert view["next_print"]["consensus_pre_print_snapshot_utc"] == "2026-07-22T18:00:00Z"


def test_completed_print_keeps_historical_consensus_and_actuals():
    report = _report()
    view = _serve("2026-07-24", report)
    assert view["next_print"] is None
    last = view["last_print"]
    assert last["print_date"] == "2026-07-23"
    assert last["consensus_chg_bcf"] == 29.0
    assert last["actual_as_printed_bcf"] == 31.0
