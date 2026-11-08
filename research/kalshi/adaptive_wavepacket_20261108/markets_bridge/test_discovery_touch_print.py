from collections import Counter
import unittest

from .discovery_touch_print import decisions


def group(ordinal, ask, *, price=None, boundary=False, trades=()):
    price = 102 if price is None else price
    return dict(group_ordinal=ordinal, first_cursor=ordinal, close_cursor=ordinal,
                event_ns=ordinal, receive_ns=ordinal,
                ask=[price, ask, 1], bid=[100, 7, 1],
                snapshot_member=boundary, reset_member=boundary, bad_receive_clock_member=False,
                prints=[dict(source_ordinal=i, trade_input_cursor=ordinal, price_raw=value)
                        for i, value in enumerate(trades)])


class TouchPrintTests(unittest.TestCase):
    def test_falling_path_latches_and_print_uses_prior_touch(self):
        groups = [group(0, 8), group(1, 8), group(2, 6, trades=(102,)),
                  group(3, 5), group(4, 8, price=103, trades=(102,)), group(5, 7, price=103),
                  group(6, 6, price=103)]
        actual = list(decisions(groups, 0, 10, Counter()))
        self.assertEqual([(r["group"], r["rule"], r["side"]) for r in actual],
                         [(2, "falling-touch.v1", "ask"), (2, "falling-touch+print.v1", "ask"),
                          (2, "prior-touch-print.v1", "ask"), (4, "prior-touch-print.v1", "ask"),
                          (6, "falling-touch.v1", "ask")])

    def test_reset_or_gap_breaks_history_and_print_ties_remain_ambiguous(self):
        groups = [group(0, 7), group(1, 6, boundary=True), group(2, 5, trades=(102,)),
                  group(4, 4, trades=(102,)), group(5, 4, trades=(100, 102))]
        actual = list(decisions(groups, 0, 10, Counter()))
        self.assertEqual([(r["group"], r["disposition"]) for r in actual],
                         [(2, "PRIOR_TOUCH_UNAVAILABLE"), (4, "PRIOR_TOUCH_UNAVAILABLE"),
                          (5, "AMBIGUOUS_VS_PRIOR_TOUCH")])
        self.assertEqual([p["source_ordinal"] for p in actual[-1]["prints"]], [0, 1])

    def test_halt_rows_cannot_seed_the_open(self):
        groups = [group(0, 8), group(1, 6), group(2, 5, trades=(102,)), group(3, 4)]
        actual = list(decisions(groups, 2, 4, Counter()))
        self.assertEqual([(r["group"], r["disposition"]) for r in actual],
                         [(2, "PRIOR_TOUCH_UNAVAILABLE")])


if __name__ == "__main__":
    unittest.main()
