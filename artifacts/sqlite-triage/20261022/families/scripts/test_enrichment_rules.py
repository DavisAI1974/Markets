"""Boundary checks for the enriched descriptive inputs; not the old draft test."""
import unittest
from enrichment_rules import eligible, measurement, flatten


class EnrichmentRules(unittest.TestCase):
    def test_future_or_other_instrument_rejected(self):
        self.assertTrue(eligible(100, 9, 1, 100, 9, 1))
        self.assertFalse(eligible(101, 9, 1, 100, 9, 1))
        self.assertFalse(eligible(99, 10, 1, 100, 9, 1))
        self.assertFalse(eligible(99, 9, 2, 100, 9, 1))

    def test_identity_clock_and_terminal_labels_are_not_measurements(self):
        for key in ['instrument_id', 'birth_group_index', 'terminal_recv_ns',
                    'terminal_status', 'family_id', 'censored', 'resolved']:
            self.assertIsNone(measurement(key, 12))
        self.assertEqual(measurement('lifetime_ns', 2_000_000_000), ('lifetime_s', 2.0))
        self.assertEqual(measurement('price_at_open_raw', 3_061_000_000), ('price_at_open', 3.061))
        self.assertIsNone(measurement('best_price_after', 3))  # unverified ladder units

    def test_missing_not_zero_and_list_scope_preserved(self):
        self.assertIsNone(measurement('quantity', None))
        self.assertIsNone(measurement('quantity', float('nan')))
        out = list(flatten({'episodes': [{'fills_ahead': 2}, {'fills_ahead': 4}]}))
        self.assertEqual(out, [('episodes[].fills_ahead', 2.0), ('episodes[].fills_ahead', 4.0)])
        self.assertEqual(list(flatten({'episodes': []})), [])


if __name__ == '__main__':
    unittest.main()
