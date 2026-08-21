#!/usr/bin/env python3
from __future__ import annotations

import unittest

from ng_exhaustion_mbo_v4_state_adapter_20260820 import (
    F_LAST,
    F_SNAPSHOT,
    PRICE_SCALE,
    InstrumentBook,
    V4MboAdapter,
)


def rec(
    *,
    action: str,
    side: str = "N",
    order_id: int = 0,
    price: float | None = None,
    size: int = 0,
    flags: int = F_LAST,
    sequence: int = 1,
    ts_recv_ns: int = 1_000_000_000,
    ts_event_ns: int | None = None,
    instrument_id: int = 101,
) -> dict:
    return {
        "instrument_id": instrument_id,
        "publisher_id": 1,
        "channel_id": 7,
        "order_id": order_id,
        "action": action,
        "side": side,
        "price": 9_000_000_000_000_000_000 if price is None else int(round(price * PRICE_SCALE)),
        "size": size,
        "flags": flags,
        "sequence": sequence,
        "ts_event": ts_recv_ns - 1000 if ts_event_ns is None else ts_event_ns,
        "ts_recv": ts_recv_ns,
        "ts_in_delta": 500,
    }


class TestV4MboAdapter(unittest.TestCase):
    def test_fifo_queue_and_volume_ahead(self) -> None:
        a = V4MboAdapter()
        a.apply(rec(action="A", side="B", order_id=1, price=3.000, size=4, sequence=1, ts_recv_ns=1_000_000_000))
        frame, _ = a.apply(rec(action="A", side="B", order_id=2, price=3.000, size=6, sequence=2, ts_recv_ns=2_000_000_000))
        self.assertIsNotNone(frame)
        book = a.books[101]
        state = book.checkpoint_state(3_000_000_000, include_full_depth=True, include_order_ids=True)
        q = state["book"]["bid_levels_full"][0]["fifo_queue"]
        self.assertEqual([x["order_id"] for x in q], [1, 2])
        self.assertEqual([x["volume_ahead"] for x in q], [0, 4])
        self.assertEqual(state["book"]["best_bid"], 3.0)
        self.assertEqual(state["book"]["bid_depth_full"], 10)

    def test_modify_size_increase_loses_priority(self) -> None:
        a = V4MboAdapter()
        a.apply(rec(action="A", side="B", order_id=1, price=3.0, size=4, sequence=1, ts_recv_ns=1_000_000_000))
        a.apply(rec(action="A", side="B", order_id=2, price=3.0, size=6, sequence=2, ts_recv_ns=2_000_000_000))
        a.apply(rec(action="M", side="B", order_id=1, price=3.0, size=8, sequence=3, ts_recv_ns=3_000_000_000))
        state = a.books[101].checkpoint_state(4_000_000_000, include_order_ids=True)
        q = state["book"]["bid_levels_full"][0]["fifo_queue"]
        self.assertEqual([x["order_id"] for x in q], [2, 1])
        self.assertEqual(q[1]["priority_sequence"], 3)

    def test_modify_size_decrease_retains_priority(self) -> None:
        a = V4MboAdapter()
        a.apply(rec(action="A", side="A", order_id=11, price=3.1, size=8, sequence=1, ts_recv_ns=1_000_000_000))
        a.apply(rec(action="A", side="A", order_id=12, price=3.1, size=5, sequence=2, ts_recv_ns=2_000_000_000))
        a.apply(rec(action="M", side="A", order_id=11, price=3.1, size=4, sequence=3, ts_recv_ns=3_000_000_000))
        state = a.books[101].checkpoint_state(4_000_000_000, include_order_ids=True)
        q = state["book"]["ask_levels_full"][0]["fifo_queue"]
        self.assertEqual([x["order_id"] for x in q], [11, 12])
        self.assertEqual(q[0]["priority_sequence"], 1)
        self.assertEqual(q[0]["size"], 4)

    def test_cancel_reduces_then_removes(self) -> None:
        a = V4MboAdapter()
        a.apply(rec(action="A", side="B", order_id=1, price=3.0, size=10, sequence=1))
        a.apply(rec(action="C", side="B", order_id=1, price=3.0, size=3, sequence=2, ts_recv_ns=2_000_000_000))
        self.assertEqual(a.books[101].orders[1].size, 7)
        a.apply(rec(action="C", side="B", order_id=1, price=3.0, size=7, sequence=3, ts_recv_ns=3_000_000_000))
        self.assertNotIn(1, a.books[101].orders)
        self.assertEqual(a.books[101].book_snapshot(3_000_000_000)["bid_depth_full"], 0)

    def test_trade_and_fill_do_not_directly_mutate_resting_book(self) -> None:
        a = V4MboAdapter()
        a.apply(rec(action="A", side="A", order_id=2, price=3.1, size=10, sequence=1))
        a.apply(rec(action="T", side="B", price=3.1, size=4, sequence=2, ts_recv_ns=2_000_000_000))
        a.apply(rec(action="F", side="A", order_id=2, price=3.1, size=4, sequence=2, ts_recv_ns=2_000_000_000))
        self.assertEqual(a.books[101].orders[2].size, 10)
        a.apply(rec(action="C", side="A", order_id=2, price=3.1, size=4, sequence=2, ts_recv_ns=2_000_000_000))
        self.assertEqual(a.books[101].orders[2].size, 6)

    def test_snapshot_initializes_state_but_not_activity(self) -> None:
        a = V4MboAdapter()
        a.apply(rec(action="R", flags=F_SNAPSHOT, sequence=0, ts_recv_ns=1_000_000_000))
        frame, _ = a.apply(rec(action="A", side="B", order_id=1, price=3.0, size=5, flags=F_SNAPSHOT | F_LAST, sequence=1, ts_recv_ns=1_000_000_000))
        self.assertTrue(frame["snapshot_bootstrap_only"])
        for window in frame["activity"].values():
            self.assertEqual(window["event_count"], 0)
        self.assertEqual(frame["book"]["bid_depth_full"], 5)

    def test_event_group_emits_only_at_f_last(self) -> None:
        a = V4MboAdapter()
        frame, legacy = a.apply(rec(action="A", side="B", order_id=1, price=3.0, size=5, flags=0, sequence=10))
        self.assertIsNone(frame)
        self.assertEqual(legacy, [])
        frame, legacy = a.apply(rec(action="A", side="A", order_id=2, price=3.1, size=7, flags=F_LAST, sequence=10, ts_recv_ns=1_000_001_000))
        self.assertIsNotNone(frame)
        self.assertTrue(frame["event_group_complete_f_last"])
        self.assertEqual(len(frame["raw_actions"]), 2)
        self.assertEqual(frame["book"]["best_bid"], 3.0)
        self.assertEqual(frame["book"]["best_ask"], 3.1)
        self.assertEqual(len(legacy), 2)

    def test_missing_modify_is_preserved_as_integrity_anomaly(self) -> None:
        a = V4MboAdapter()
        a.apply(rec(action="M", side="B", order_id=99, price=3.0, size=5, sequence=1))
        self.assertIn(99, a.books[101].orders)
        self.assertEqual(a.books[101].integrity["modify_missing_treated_as_add"], 1)

    def test_legacy_projection_has_top10_but_v4_keeps_raw_semantics(self) -> None:
        a = V4MboAdapter()
        a.apply(rec(action="A", side="B", order_id=1, price=3.0, size=5, sequence=1))
        a.apply(rec(action="A", side="A", order_id=2, price=3.1, size=7, sequence=2, ts_recv_ns=2_000_000_000))
        frame, legacy = a.apply(rec(action="T", side="B", price=3.1, size=2, sequence=3, ts_recv_ns=3_000_000_000))
        self.assertEqual(frame["raw_actions"][0]["action"], "T")
        self.assertEqual(frame["activity"]["20"]["trade_buy_aggressor_qty"], 2)
        self.assertEqual(legacy[0]["action"], "T")
        self.assertEqual(legacy[0]["bid_px_00"], 3.0)
        self.assertEqual(legacy[0]["ask_px_00"], 3.1)
        self.assertIn("bid_px_09", legacy[0])

    def test_receive_clock_regression_is_flagged_not_backfilled(self) -> None:
        a = V4MboAdapter()
        a.apply(rec(action="A", side="B", order_id=1, price=3.0, size=5, sequence=2, ts_recv_ns=2_000_000_000))
        a.apply(rec(action="A", side="B", order_id=2, price=2.9, size=5, sequence=3, ts_recv_ns=1_500_000_000))
        self.assertEqual(a.books[101].integrity["receive_time_regression"], 1)
        self.assertEqual(a.books[101].last_recv_ns, 2_000_000_000)

    def test_full_depth_checkpoint_exposes_order_identity(self) -> None:
        a = V4MboAdapter()
        a.apply(rec(action="A", side="B", order_id=123, price=3.0, size=5, sequence=1))
        state = a.books[101].checkpoint_state(2_000_000_000, include_full_depth=True, include_order_ids=True)
        q = state["book"]["bid_levels_full"][0]["fifo_queue"]
        self.assertEqual(q[0]["order_id"], 123)
        self.assertIn("volume_ahead", q[0])
        self.assertNotIn("priority_id", q[0])


if __name__ == "__main__":
    unittest.main()
