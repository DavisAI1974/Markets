"""Focused guards for exact chronology and sequence interpretation."""
import unittest
import json

from continue_trade_chronology import PARENT, price_stretches, sequence_diagnostics, print_legs


class ChronologyTests(unittest.TestCase):
    def test_print_legs_overlap_at_turning_stretch_without_losing_trades(self):
        stretches, _ = price_stretches([100, 100, 102, 102, 101, 100, 100, 103])
        legs, membership = print_legs(stretches)
        self.assertEqual([(v['first_stretch_ordinal'], v['last_stretch_ordinal'], v['step_sign'])
                          for v in legs], [(0, 1, 1), (1, 3, -1), (3, 4, 1)])
        self.assertEqual(membership, [[0], [0, 1], [1], [1, 2], [2]])

    def test_flat_day_has_no_directional_leg(self):
        stretches, _ = price_stretches([100, 100])
        self.assertEqual(print_legs(stretches), ([], [[]]))

    def test_equal_price_trades_remain_individual_at_turn(self):
        stretches, membership = price_stretches([100, 100, 102, 102, 101, 100, 100])
        self.assertEqual([(s['first_trade_ordinal'], s['last_trade_ordinal'])
                          for s in stretches], [(0, 1), (2, 3), (4, 4), (5, 6)])
        self.assertEqual(membership, [0, 0, 1, 1, 2, 3, 3])
        self.assertEqual(stretches[1]['incoming_step_raw'], 2)
        self.assertEqual(stretches[1]['outgoing_step_raw'], -1)
        self.assertTrue(stretches[1]['print_direction_turn'])
        self.assertFalse(stretches[2]['print_direction_turn'])

    def test_entirely_flat_and_single_print_are_boundary_censored(self):
        for prices in [[100], [100, 100, 100]]:
            stretches, membership = price_stretches(prices)
            self.assertEqual(len(stretches), 1)
            self.assertEqual(membership, [0] * len(prices))
            self.assertIsNone(stretches[0]['incoming_step_raw'])
            self.assertIsNone(stretches[0]['outgoing_step_raw'])
            self.assertIsNone(stretches[0]['print_direction_turn'])

    def test_duplicate_sequences_are_not_missing_sequence_numbers(self):
        d = sequence_diagnostics([12, 12, 12, 13, 13])
        self.assertFalse(d['literal_one_sequence_per_action'])
        self.assertEqual(d['forward_jump_pairs'], [])
        self.assertEqual(d['regression_pairs'], [])
        self.assertEqual(d['duplicate_adjacent_pairs'], [[0, 1], [1, 2], [3, 4]])

    def test_forward_jump_and_regression_remain_separate(self):
        d = sequence_diagnostics([12, 15, 14])
        self.assertEqual(d['forward_jump_pairs'], [[0, 1, 2]])
        self.assertEqual(d['regression_pairs'], [[1, 2]])

    def test_saved_role_results_preserve_source_and_resolve_only_resting_side(self):
        gap = PARENT / 'quote-order-gapfill-v1'
        original = json.loads((gap / 'each-trade-exact-quote-order-analysis.json').read_text())
        result = json.loads((gap / 'role-reconciliation-v1/all-32-trade-role-reconciliation.json').read_text())
        self.assertEqual([r['trade_ordinal'] for r in result], list(range(118, 150)))
        for before, after in zip(original, result):
            self.assertEqual(before['original_trade'], after['original_trade'])
            self.assertEqual(before['original_same_price_fill_actions'],
                             [f['original_fill_action'] for f in after['fill_order_reconciliation']])
        lookup = {r['trade_ordinal']: r for r in result}
        for n in [126, 133]:
            self.assertEqual(lookup[n]['source_reported_aggressor_side'], 'N')
            self.assertEqual(lookup[n]['fill_order_reconciliation'][0]['pre_group_resting_order']['resting_side'], 'A')
        for n, price in [(123, 2990000000), (128, 3063000000)]:
            fill = next(f for f in lookup[n]['fill_order_reconciliation'] if f['same_id_as_T'])
            self.assertEqual(fill['pre_group_resting_order']['resting_price_raw'], price)
            self.assertFalse(fill['resting_price_matches_execution_price'])
        self.assertEqual(lookup[119]['fill_order_reconciliation'], [])
        self.assertEqual(sum(f['original_fill_action']['size']
                             for f in lookup[134]['fill_order_reconciliation']), 2)


if __name__ == '__main__':
    unittest.main()
