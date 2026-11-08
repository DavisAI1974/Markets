import unittest

import numpy as np
import pandas as pd

from flow_book_discovery import OUT, asof_index, purged_training, ratio, stack_class


class Boundaries(unittest.TestCase):
    def test_strict_clock_and_cursor(self):
        times = np.array([1697634552081390596, 1697634552081390598], dtype=np.int64)
        cursors = np.array([303654, 303655], dtype=np.int64)
        self.assertEqual(asof_index(times, cursors, 1697634552081390597, 303655), 0)
        self.assertEqual(asof_index(times, cursors, 1697634552081390598, 303654), 0)
        self.assertEqual(asof_index(times, cursors, 1697634552081390595, 303655), -1)

    def test_purge_equal_boundary_and_overlap(self):
        self.assertEqual(purged_training(np.array([100, 150, 200]), 2, 50).tolist(), [0])

    def test_missing_and_inverse_are_distinct(self):
        self.assertIsNone(ratio(0, 0))
        self.assertEqual(stack_class(-1, -1, 1, 1), 'original')
        self.assertEqual(stack_class(1, 1, -1, -1), 'inverse')
        self.assertEqual(stack_class(0, -1, 1, 1), 'other')
        self.assertEqual(stack_class(None, -1, 1, 1), 'missing')

    def test_published_probe_uses_identical_arms_and_embargo(self):
        pred = pd.read_csv(OUT / 'arm-predictions.csv.gz')
        groups = pred.groupby(['instance', 'horizon_s', 'target', 'fold'])
        self.assertTrue(groups['arm'].nunique().eq(4).all())
        self.assertTrue(groups['observed'].nunique().eq(1).all())
        splits = pd.read_csv(OUT / 'chronological-splits.csv', dtype=str)
        for r in splits.itertuples():
            self.assertLess(int(r.last_train_label_target_ns) + int(r.embargo_s) * 10**9,
                            int(r.test_start_ns))

    def test_published_clocks_and_pinned_case_outcomes(self):
        opportunities = pd.read_csv(OUT / 'opportunities.csv.gz', dtype=str)
        self.assertEqual(len(opportunities), 749)
        for r in opportunities.itertuples():
            self.assertLessEqual(int(r.pre_receive_ns), int(r.cutoff_ns))
            self.assertLessEqual(int(r.pre_cursor), int(r.cursor_cap))
        outcomes = pd.read_csv(OUT / 'outcomes.csv.gz').set_index(['instance', 'horizon_s'])
        self.assertEqual(len(outcomes), 749 * 5)
        for key, expected in { (375, 1): -.0055, (375, 300): -.0125,
                               (391, 1): -.0015, (391, 300): .007 }.items():
            self.assertAlmostEqual(outcomes.at[key, 'change'], expected, places=12)

    def test_original_order_fill_evidence(self):
        raw = pd.read_csv(OUT / 'case-original-messages.csv.gz')
        self.assertEqual(raw.groupby('instance').size().to_dict(), {375: 1612, 391: 1207})
        fills = raw[(raw.order_id == 788701345922) & raw.action.eq('F')]
        self.assertEqual(int(fills['size'].sum()), 150)


if __name__ == '__main__':
    unittest.main()
