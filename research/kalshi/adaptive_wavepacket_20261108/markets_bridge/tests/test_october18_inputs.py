import unittest

from research.kalshi.adaptive_wavepacket_20261108.markets_bridge.october18_inputs import group_row


def action(code, flags=0):
    return dict(action=code, flags=flags, order_id=19, side="A", sequence=90,
                ts_event_ns=100, ts_recv_ns=110, price_raw=3051000000, size=2)


class October18InputsTests(unittest.TestCase):
    def test_keeps_each_print_at_its_own_cursor_and_group_close(self):
        row, trades = group_row(40, 7, dict(
            instrument_id=150611, ts_event_ns=99, ts_recv_ns=115,
            raw_actions=[action("T"), action("T"), action("C", 128)],
            book={"bid_levels": [], "ask_levels": [
                dict(price_raw=3051000000, size=3, order_count=2)]},
        ))
        self.assertEqual([t["trade_input_cursor"] for t in trades], [38, 39])
        self.assertEqual([t["available_ns"] for t in trades], [115, 115])
        self.assertEqual([t["group_ordinal"] for t in trades], [7, 7])
        self.assertIsNone(row["bid"])
        self.assertEqual(row["ask"], [3051000000, 3, 2])
        self.assertEqual(row["print_count"], 2)

    def test_keeps_empty_print_groups_and_surfaces_snapshot_and_reset(self):
        row, trades = group_row(1, 0, dict(
            instrument_id=150611, ts_event_ns=99, ts_recv_ns=115,
            raw_actions=[action("R", 32), action("A", 128)],
            book={"bid_levels": [], "ask_levels": []},
        ))
        self.assertTrue(row["snapshot_member"])
        self.assertTrue(row["reset_member"])
        self.assertEqual(row["print_count"], 0)
        self.assertEqual(trades, [])
