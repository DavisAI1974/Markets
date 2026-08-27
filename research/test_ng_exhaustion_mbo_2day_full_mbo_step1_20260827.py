from __future__ import annotations

from types import SimpleNamespace

import pytest

import ng_exhaustion_mbo_2day_full_mbo_step1_20260825 as full_mbo


def _state(*, bid_ids=(), ask_ids=(), bid_depth=0, ask_depth=0):
    return {
        "bid_depth": bid_depth,
        "ask_depth": ask_depth,
        "bid_orders": len(bid_ids),
        "ask_orders": len(ask_ids),
        "bid_levels": int(bool(bid_ids)),
        "ask_levels": int(bool(ask_ids)),
        "bid": {"ids": tuple(bid_ids)},
        "ask": {"ids": tuple(ask_ids)},
    }


def _message(*, recv_ns: int, is_last: bool, action: str, side: str, size: int):
    return SimpleNamespace(
        instrument_id=7,
        ts_recv_ns=recv_ns,
        ts_event_ns=recv_ns - 1,
        is_last=is_last,
        action=action,
        side=side,
        size=size,
        source_dbn_object="/raw/oct4.dbn.zst",
        source_dbn_sha256="a" * 64,
    )


def test_surface_collector_buffers_group_that_crosses_receive_second(monkeypatch):
    collector = full_mbo.MboSurfaceCollector(
        {"/raw/oct4.dbn.zst": {"key": "canonical/oct4.dbn.zst"}}
    )
    book = SimpleNamespace(state=_state())
    monkeypatch.setattr(
        full_mbo.CausalMboCollector,
        "_state_book",
        staticmethod(lambda current_book, _now_ns: current_book.state),
    )

    book.state = _state(bid_ids=(101,), bid_depth=10)
    collector.consume_effect(
        _message(recv_ns=999_900_000, is_last=False, action="A", side="B", size=10),
        SimpleNamespace(side="B", size_delta=10),
        book,
        None,
    )

    book.state = _state(bid_ids=(101,), ask_ids=(202,), bid_depth=10, ask_depth=5)
    collector.consume_effect(
        _message(recv_ns=1_000_100_000, is_last=True, action="A", side="A", size=5),
        SimpleNamespace(side="A", size_delta=5),
        book,
        {"group": "complete"},
    )
    collector.finish()

    assert len(collector.surface_rows) == 1
    row = collector.surface_rows[0]
    assert row["recv_second"] == 1
    assert row["cutoff_ts_recv_ns"] == 1_000_100_000
    assert row["f_last_group_completion_ts_recv_ns"] == 1_000_100_000
    assert row["surface_inputs"]["add_bid"] == 10
    assert row["surface_inputs"]["add_ask"] == 5


def test_resume_seconds_are_hash_and_window_bound(tmp_path):
    source = tmp_path / "seconds.jsonl.gz"
    rows = [
        {"epoch_second": full_mbo.WINDOW_START, "value": 1},
        {"epoch_second": full_mbo.WINDOW_END - 1, "value": 2},
    ]
    output = full_mbo.base.deterministic_gzip_jsonl(source, rows)

    loaded, summary = full_mbo._load_resume_native_seconds(
        source,
        output["gzip_sha256"],
        expected_rows=2,
        expected_first=full_mbo.WINDOW_START,
        expected_last=full_mbo.WINDOW_END - 1,
    )

    assert loaded == rows
    assert summary["status"] == "PRESERVED_NATIVE_SECONDS_REUSED"
    assert summary["rows"] == 2
    with pytest.raises(full_mbo.base.CensusError, match="identity drift"):
        full_mbo._load_resume_native_seconds(
            source,
            "0" * 64,
            expected_rows=2,
            expected_first=full_mbo.WINDOW_START,
            expected_last=full_mbo.WINDOW_END - 1,
        )
