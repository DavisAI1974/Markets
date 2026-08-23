#!/usr/bin/env python3
from __future__ import annotations

import unittest

from ng_exhaustion_mbo_v4_state_adapter_20260820 import F_LAST, PRICE_SCALE, V4MboAdapter


def r(action, side="N", order_id=0, price=3.0, size=1, flags=F_LAST, sequence=1, ts=1_000_000_000):
    return {
        "instrument_id": 101,
        "publisher_id": 1,
        "channel_id": 7,
        "order_id": order_id,
        "action": action,
        "side": side,
        "price": int(price * PRICE_SCALE),
        "size": size,
        "flags": flags,
        "sequence": sequence,
        "ts_event": ts - 1000,
        "ts_recv": ts,
        "ts_in_delta": 500,
    }


class LegacyControlSemanticWall(unittest.TestCase):
    def test_mbo_only_fill_and_none_stay_out_of_legacy_control(self):
        a = V4MboAdapter()
        a.apply(r("A", "B", 1, 3.0, 10, sequence=1))
        a.apply(r("A", "A", 2, 3.1, 10, sequence=2, ts=2_000_000_000))

        # A CME execution event may normalize to Trade + Fill + Cancel in MBO.
        frame, legacy = a.apply(r("T", "B", 0, 3.1, 3, flags=0, sequence=3, ts=3_000_000_000))
        self.assertIsNone(frame)
        frame, legacy = a.apply(r("F", "A", 2, 3.1, 3, flags=0, sequence=3, ts=3_000_000_000))
        self.assertIsNone(frame)
        frame, legacy = a.apply(r("C", "A", 2, 3.1, 3, flags=F_LAST, sequence=3, ts=3_000_000_000))

        self.assertEqual([x["action"] for x in frame["raw_actions"]], ["T", "F", "C"])
        self.assertEqual([x["action"] for x in legacy], ["T", "C"])
        self.assertEqual(legacy[0]["ask_sz_00"], 10)
        self.assertEqual(legacy[1]["ask_sz_00"], 7)
        self.assertFalse(legacy[0]["projection_at_f_last"])
        self.assertTrue(legacy[1]["projection_at_f_last"])
        self.assertEqual(frame["activity"]["20"]["trade_buy_aggressor_qty"], 3)
        self.assertEqual(a.books[101].orders[2].size, 7)

    def test_below_top10_book_actions_do_not_emit_legacy_rows(self):
        a = V4MboAdapter()
        for i in range(10):
            _frame, legacy = a.apply(r(
                "A", "B", i + 1, 3.00 - i * 0.01, 10,
                sequence=i + 1, ts=(i + 1) * 1_000_000_000,
            ))
            self.assertEqual(len(legacy), 1)

        _frame, legacy = a.apply(r(
            "A", "B", 11, 2.90, 10, sequence=11, ts=11_000_000_000,
        ))
        self.assertEqual(legacy, [])
        _frame, legacy = a.apply(r(
            "C", "B", 11, 2.90, 2, sequence=12, ts=12_000_000_000,
        ))
        self.assertEqual(legacy, [])
        _frame, legacy = a.apply(r(
            "A", "B", 12, 3.01, 10, sequence=13, ts=13_000_000_000,
        ))
        self.assertEqual(len(legacy), 1)
        self.assertEqual(legacy[0]["bid_px_00"], 3.01)

    def test_reset_rebuild_collapses_to_one_final_legacy_row(self):
        a = V4MboAdapter()
        frame, legacy = a.apply(r("R", flags=0, sequence=1))
        self.assertIsNone(frame)
        self.assertEqual(legacy, [])
        for i in range(12):
            flags = F_LAST if i == 11 else 0
            frame, legacy = a.apply(r(
                "A", "B", i + 1, 3.00 - i * 0.01, 10, flags=flags,
                sequence=1, ts=1_000_000_000 + i,
            ))
        self.assertIsNotNone(frame)
        self.assertEqual(len(legacy), 1)
        self.assertEqual(legacy[0]["action"], "A")
        self.assertEqual(legacy[0]["bid_px_00"], 3.0)
        self.assertTrue(legacy[0]["projection_at_f_last"])

    def test_multiple_book_mutations_collapse_at_event_group_boundary(self):
        a = V4MboAdapter()
        a.apply(r("A", "A", 1, 3.10, 10, sequence=1))
        a.apply(r("A", "A", 2, 3.11, 10, sequence=2))

        frame, legacy = a.apply(r(
            "C", "A", 1, 3.10, 3, flags=0, sequence=3, ts=3_000_000_000,
        ))
        self.assertIsNone(frame)
        frame, legacy = a.apply(r(
            "C", "A", 1, 3.10, 2, flags=0, sequence=3, ts=3_000_000_001,
        ))
        self.assertIsNone(frame)
        frame, legacy = a.apply(r(
            "N", flags=F_LAST, sequence=3, ts=3_000_000_002,
        ))
        self.assertEqual([row["action"] for row in frame["raw_actions"]], ["C", "C", "N"])
        self.assertEqual(len(legacy), 1)
        self.assertEqual(legacy[0]["action"], "C")
        self.assertEqual(legacy[0]["ask_sz_00"], 5)
        self.assertTrue(legacy[0]["projection_at_event_group_end"])
        self.assertFalse(legacy[0]["projection_after_mbo_action"])

    def test_visible_add_is_retained_when_group_restores_same_book(self):
        a = V4MboAdapter()
        a.apply(r("A", "B", 1, 3.00, 5, sequence=1))
        frame, _legacy = a.apply(r(
            "C", "B", 1, 3.00, 5, flags=0, sequence=2, ts=2_000_000_000,
        ))
        self.assertIsNone(frame)
        frame, legacy = a.apply(r(
            "A", "B", 1, 3.00, 5, flags=F_LAST, sequence=2, ts=2_000_000_001,
        ))
        self.assertEqual(len(legacy), 1)
        self.assertEqual(legacy[0]["action"], "A")
        self.assertEqual(legacy[0]["bid_px_00"], 3.0)
        self.assertEqual(legacy[0]["bid_sz_00"], 5)


if __name__ == "__main__":
    unittest.main()
