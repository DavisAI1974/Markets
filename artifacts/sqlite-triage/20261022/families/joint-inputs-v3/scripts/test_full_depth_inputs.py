import unittest
from augment_full_depth_inputs import measurements


class FullDepthTests(unittest.TestCase):
    def source(self):
        level = dict(price=3.001, price_raw=3001000000, size=5, order_count=2,
                     front_order_size=2, front_order_age_s=7,
                     fifo_queue=[dict(size=2, priority_age_s=7, volume_ahead=0, order_id=999),
                                 dict(size=3, priority_age_s=1, volume_ahead=2, order_id=888)])
        return dict(book={'bid_levels': [level], 'ask_levels': []},
                    book_full={'bid_levels_full': [level, dict(level, price=3.000, price_raw=3000000000)],
                               'ask_levels_full': []}, within_group_receive_gaps_ns=[], ts_in_delta_ns=123)

    def test_deeper_levels_retained_and_top_levels_not_duplicated(self):
        j = self.source()
        j['book']['bid_levels'] = [{k:v for k,v in j['book']['bid_levels'][0].items() if k!='fifo_queue'}]
        out = measurements(j)
        self.assertEqual(out['native.book.bid_levels.rank2.price'], 3.0)
        self.assertNotIn('native.book.bid_levels.rank1.price', out)

    def test_fifo_summary_uses_sizes_and_ages_without_order_identifiers(self):
        out = measurements(self.source())
        self.assertAlmostEqual(out['native.book.bid_levels.rank2.fifo_size_hhi'], .52)
        self.assertAlmostEqual(out['native.book.bid_levels.rank2.fifo_size_weighted_age_s'], 3.4)
        self.assertFalse(any('order_id' in k or 'priority_recv' in k for k in out))

    def test_empty_side_does_not_manufacture_a_rank_or_zero_age(self):
        out = measurements(self.source())
        self.assertFalse(any('ask_levels.rank' in k for k in out))
        self.assertIsNone(out['native.receive_gaps.mean_ns'])

    def test_bad_units_and_incomplete_queue_are_rejected(self):
        j = self.source(); j['book_full']['bid_levels_full'][1]['price_raw'] = 1
        with self.assertRaises(AssertionError): measurements(j)
        j = self.source(); j['book_full']['bid_levels_full'][1]['size'] = 6
        with self.assertRaises(AssertionError): measurements(j)


if __name__ == '__main__':
    unittest.main()
