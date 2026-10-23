import unittest

from analyze_saved_trade_quotes import quote_position, exact_projected_quote


class SavedQuoteTests(unittest.TestCase):
    def test_print_position_is_not_an_aggressor_classification(self):
        self.assertEqual([quote_position(p, 100, 102) for p in [99, 100, 101, 102, 103]],
                         ['BELOW_PRIOR_BID', 'AT_PRIOR_BID', 'INSIDE_PRIOR_SPREAD', 'AT_PRIOR_ASK', 'ABOVE_PRIOR_ASK'])

    def test_missing_and_crossed_quotes_do_not_invent_direction(self):
        self.assertEqual(quote_position(101, None, 102), 'MISSING_PRIOR_QUOTE')
        self.assertEqual(quote_position(101, 102, 100), 'LOCKED_OR_CROSSED_PRIOR_QUOTE')
        self.assertEqual(quote_position(101, 101, 101), 'LOCKED_OR_CROSSED_PRIOR_QUOTE')

    def test_duplicate_values_remain_usable_but_conflicts_are_not_averaged(self):
        q = exact_projected_quote(['3.061', '3.061'])
        self.assertEqual(q['raw_integer'], 3061000000)
        self.assertIsNone(exact_projected_quote(['3.061', '3.062'])['raw_integer'])

    def test_scalar_projection_is_never_silently_rounded(self):
        for values in [['3.0610000000000004'], ['nan'], ['inf'], []]:
            self.assertIsNone(exact_projected_quote(values)['raw_integer'])


if __name__ == '__main__':
    unittest.main()
