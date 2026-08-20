from __future__ import annotations

import pytest

from research.kalshi.ng_exhaustion_v4_causal_clock import (
    CausalClockError,
    first_receive_ordered_mark,
    make_receipt,
    validate_availability_chain,
)

SHA_A = "a" * 64
SHA_B = "b" * 64


def receipt(**overrides):
    args = dict(
        event_id="e1",
        session_id="s1",
        detector_revision="causal-replay-v1",
        detector_source_sha256=SHA_A,
        source_manifest_sha256=SHA_B,
        source_object_id="s3://bucket/raw.dbn.zst",
        source_range_id="r1",
        source_ts_event=100.0,
        source_ts_recv=101.0,
        detector_marked_at=105.0,
        event_known_by=105.0,
        canonical_t0=90.0,
        mark_mode="CAUSAL_REPLAY",
    )
    args.update(overrides)
    return make_receipt(**args)


def test_canonical_t0_may_be_earlier_but_never_backdates_known_by():
    r = receipt(canonical_t0=80.0, detector_marked_at=110.0, event_known_by=110.0)
    assert r.canonical_t0 == 80.0
    assert r.event_known_by == 110.0


def test_detector_mark_cannot_precede_receive_time():
    with pytest.raises(CausalClockError):
        receipt(detector_marked_at=100.5, event_known_by=100.5)


def test_availability_chain_is_fail_closed():
    r = receipt()
    assert validate_availability_chain(
        r, feature_available_at=106.0, model_evaluated_at=107.0, decision_available_at=108.0
    )["decision_available_at"] == 108.0
    with pytest.raises(CausalClockError):
        validate_availability_chain(
            r, feature_available_at=104.0, model_evaluated_at=107.0, decision_available_at=108.0
        )


def test_receive_order_not_event_order_governs_first_mark():
    rows = [
        {"ts_event": 90.0, "ts_recv": 120.0, "qualifies": True},
        {"ts_event": 100.0, "ts_recv": 110.0, "qualifies": True},
    ]
    mark = first_receive_ordered_mark(rows)
    assert mark["row_index"] == 1
    assert mark["event_known_by"] == 110.0


def test_future_rows_do_not_change_already_lawful_first_mark():
    prefix = [
        {"ts_event": 100.0, "ts_recv": 101.0, "qualifies": False},
        {"ts_event": 101.0, "ts_recv": 102.0, "qualifies": True},
    ]
    mark1 = first_receive_ordered_mark(prefix)
    mark2 = first_receive_ordered_mark(prefix + [{"ts_event": 102.0, "ts_recv": 103.0, "qualifies": True}])
    assert mark1 == mark2


def test_receipt_hash_is_deterministic():
    assert receipt().receipt_hash == receipt().receipt_hash
