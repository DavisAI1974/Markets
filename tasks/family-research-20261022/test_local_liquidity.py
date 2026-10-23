import unittest

from analyze_local_liquidity import side_transition, exact_consensus, size_path_effect, rank_window_effect


def level(price, size):
    return dict(price_raw=str(price), size=str(size), order_count='1')


class LocalLiquidityTests(unittest.TestCase):
    def test_old_thin_touch_removed_exposes_existing_second_level(self):
        r = side_transition('B', [level(100, 1), level(99, 20)], [level(99, 20)])
        self.assertEqual(r['old_touch_size_after'], 0)
        self.assertEqual(r['quote_step_raw'], -1)
        self.assertTrue(r['new_best_equals_previous_second_level'])
        self.assertEqual(r['full_size_before'], 21)
        self.assertIsNone(r['unchanged_touch_size_change'])

    def test_same_quote_size_decline_does_not_infer_a_fill(self):
        r = side_transition('A', [level(101, 8), level(102, 20)], [level(101, 3), level(102, 25)])
        self.assertEqual(r['quote_step_raw'], 0)
        self.assertEqual(r['unchanged_touch_size_change'], -5)
        self.assertEqual(r['full_size_after'], 28)
        self.assertNotIn('fill_quantity', r)
        self.assertNotIn('cancel_quantity', r)

    def test_better_price_can_appear_while_old_level_remains(self):
        r = side_transition('B', [level(99, 10)], [level(100, 1), level(99, 10)])
        self.assertEqual(r['new_touch_size_before'], 0)
        self.assertEqual(r['old_touch_size_after'], 10)
        self.assertEqual(r['quote_step_raw'], 1)

    def test_scalar_conflicts_and_nonintegral_sizes_remain_unresolved(self):
        self.assertEqual(exact_consensus(['994.0', '994'], integral=True), 994)
        self.assertIsNone(exact_consensus(['994', '995'], integral=True))
        self.assertIsNone(exact_consensus(['1.5'], integral=True))
        self.assertIsNone(exact_consensus([''], integral=True))

    def test_equal_endpoint_sizes_do_not_erase_intermediate_changes(self):
        r = size_path_effect([1, 4, 1])
        self.assertEqual(r['endpoint_size_change'], 0)
        self.assertTrue(r['both_size_increases_and_decreases'])
        self.assertTrue(r['equal_endpoints_with_intermediate_changes'])
        self.assertEqual(r['positive_step_changes'], [3])
        self.assertEqual(r['negative_step_changes'], [-3])

    def test_near_depth_can_rise_when_a_thin_best_level_disappears(self):
        before = [level(p, 1) for p in range(100, 90, -1)]
        after = [level(p, 1) for p in range(99, 90, -1)] + [level(90, 5)]
        r = rank_window_effect(before, after)
        self.assertEqual(r['first_ten_size_change'], 4)
        self.assertEqual(r['shared_price_size_change'], 0)
        self.assertEqual(r['entering_rank_window_size'], 5)
        self.assertEqual(r['leaving_rank_window_size'], 1)


if __name__ == '__main__':
    unittest.main()
