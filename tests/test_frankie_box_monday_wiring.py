"""Whole-day next-session scheduling contracts; synthetic source identities only."""
import copy
import importlib
from pathlib import Path
import sys
import types

import pytest


@pytest.fixture
def schedules(monkeypatch):
    # These contracts are stdlib-only; do not import the package's optional model exports.
    name = "research.kalshi.frankie_boss"
    if name not in sys.modules:
        package = types.ModuleType(name)
        package.__path__ = [str(Path(__file__).resolve().parents[1] / "research/kalshi/frankie_boss")]
        monkeypatch.setitem(sys.modules, name, package)
    return importlib.import_module(name + ".trading_day_schedule")


def whole_day_body():
    terminal = dict(groups_delivered=2, records_delivered=4, through_cursor=3,
                    as_of=1633381199999999000, source_as_of=1633381199999998000,
                    source_hash="e" * 64)
    return dict(schema="BOSS_WHOLE_DAY_NEXT_SESSION_SCHEDULE_V1",
        mapping_index_sha256="a" * 64,
        steps=[dict(terminal, group_index=1, feedback_available_through=None)],
        terminal_delivery=terminal, model_context_rows=4, source_dates_required=2,
        context_selection="all_source_records", feedback_lag="verified target-day outcomes pending",
        forecast_target=dict(trading_day="20211005", open_ns=1633384800000000000,
                             close_ns=1633467600000000000, calendar_hash="c" * 64),
        trading_day="20211004", source_manifest_hash="b" * 64,
        source_partitions=["member-0.dbn", "member-1.dbn"],
        source_record_count=4, journal_count=8, journal_hash="d" * 64,
        journal_sha256="f" * 64, step_count=1)


def test_whole_day_schedule_selects_every_record_and_keeps_future_feedback_pending(schedules):
    body = whole_day_body()
    sealed = schedules.seal(body)
    assert schedules.verify(sealed, expected_digest=sealed["schedule_sha256"]) == sealed
    from research.kalshi.frankie_boss.verified_sunday_schedule import verified_schedule
    assert verified_schedule(sealed, expected_digest=sealed["schedule_sha256"]) == sealed
    assert sealed["steps"][0]["through_cursor"] + 1 == sealed["model_context_rows"] == 4
    assert sealed["steps"][0]["feedback_available_through"] is None
    assert sealed["forecast_target"]["open_ns"] > sealed["terminal_delivery"]["as_of"]


@pytest.mark.parametrize("damage", ["window", "prefix", "invented_cutoff", "fake_feedback",
                                    "closed_target", "already_open", "same_day", "calendar",
                                    "source_count", "member_roster", "context_mode", "clock"])
def test_whole_day_schedule_refuses_cutoffs_truncation_and_lookahead(schedules, damage):
    body = copy.deepcopy(whole_day_body())
    if damage == "window":
        body["model_context_rows"] = 3
    elif damage == "prefix":
        body["steps"][0].update(through_cursor=1, records_delivered=2, groups_delivered=1, group_index=0)
    elif damage == "invented_cutoff":
        body["cutoff_rule"] = "first hour"
    elif damage == "fake_feedback":
        body["steps"][0]["feedback_available_through"] = dict(body["terminal_delivery"])
    elif damage == "closed_target":
        body["forecast_target"]["close_ns"] = body["terminal_delivery"]["as_of"]
    elif damage == "already_open":
        body["forecast_target"]["open_ns"] = body["terminal_delivery"]["as_of"]
    elif damage == "same_day":
        body["forecast_target"]["trading_day"] = body["trading_day"]
    elif damage == "calendar":
        body["forecast_target"]["calendar_hash"] = "invalid"
    elif damage == "source_count":
        body["source_record_count"] = 5
    elif damage == "member_roster":
        body["source_partitions"][1] = body["source_partitions"][0]
    elif damage == "context_mode":
        body["context_selection"] = "latest_rows"
    else:
        body["terminal_delivery"]["source_as_of"] = body["terminal_delivery"]["as_of"] + 1
    with pytest.raises(ValueError):
        schedules.seal(body)
