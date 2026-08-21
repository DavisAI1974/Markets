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
        self.assertEqual(frame["activity"]["20"]["trade_buy_aggressor_qty"], 3)
        self.assertEqual(a.books[101].orders[2].size, 7)


if __name__ == "__main__":
    unittest.main()
