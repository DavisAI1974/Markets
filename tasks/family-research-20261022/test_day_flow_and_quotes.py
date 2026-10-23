import unittest

from analyze_day_flow_and_quotes import flow_flags, publication_range, quote_consensus, second_bounds


class DayMechanismTests(unittest.TestCase):
    def test_nanosecond_second_boundaries(self):
        second = 1697581526
        self.assertEqual(second_bounds(second, 20),
                         (1697581507000000000, 1697581527000000000))
        self.assertEqual(second_bounds(second, 1)[1] - second_bounds(second, 1)[0], 1000000000)

    def test_publication_ranges_are_left_open_right_closed(self):
        clock = 1697581526067136130
        self.assertEqual(publication_range([clock - 1, clock, clock + 1], clock - 1, clock), [2, 2])
        self.assertIsNone(publication_range([clock], clock, clock))
        self.assertIsNone(publication_range([clock], None, clock))

    def test_rolling_persistence_is_not_fresh_flow(self):
        r = dict(trades=0, window_signed_flow=-7, net_volume=0)
        self.assertEqual(flow_flags(r, 0), ['NONZERO_ROLL_WITHOUT_NEW_TAPE'])
        self.assertIn('FRESH_NET_OPPOSES_ROLL', flow_flags(dict(trades=1, window_signed_flow=-7, net_volume=1), 1))
        self.assertIn('FRESH_TAPE_WITH_ZERO_ROLL', flow_flags(dict(trades=1, window_signed_flow=0, net_volume=-1), 1))
        self.assertIn('SOURCE_FRESH_COUNT_MISMATCH', flow_flags(r, 1))

    def test_contradictory_quotes_cannot_be_selected_or_averaged(self):
        views = [dict(bid_raw=3061000000, ask_raw=3062000000, clock_match=True),
                 dict(bid_raw=3061000000, ask_raw=3063000000, clock_match=True)]
        result = quote_consensus(views)
        self.assertEqual(result['status'], 'CONFLICTING_SAVED_QUOTES')
        self.assertIsNone(result['bid_raw'])
        self.assertIsNone(result['ask_raw'])

    def test_invalid_clocks_and_unresolved_views_are_not_filled(self):
        good = dict(bid_raw=3061000000, ask_raw=3062000000, clock_match=True)
        invalid = dict(bid_raw=None, ask_raw=3062000000, clock_match=True)
        self.assertEqual(quote_consensus([good, good])['bid_raw'], 3061000000)
        self.assertEqual(quote_consensus([good, invalid])['status'], 'UNRESOLVED_SAVED_VIEW_RETAINED')
        self.assertEqual(quote_consensus([dict(good, clock_match=False)])['status'], 'UNRESOLVED_SAVED_VIEW_RETAINED')
        self.assertEqual(quote_consensus([])['status'], 'NOT_MATERIALIZED')


if __name__ == '__main__':
    unittest.main()
