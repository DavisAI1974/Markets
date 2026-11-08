import unittest
import json
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

from research_atlas import OUT, RestingOrder, rolling_flow, mechanism_inventory


class ResearchMechanics(unittest.TestCase):
    def test_passive_fill_and_cancel_are_one_depletion(self):
        order = RestingOrder('A', 100, 150)
        order.update('F', 'A', 100, 106)
        order.update('M', 'A', 100, 44)
        order.update('F', 'A', 100, 44)
        self.assertEqual(order.update('C', 'A', 100, 44), 'fill_linked_clear')
        self.assertEqual(order.fills, 150)
        self.assertEqual(order.unlinked_reductions, 0)

    def test_refresh_and_unmatched_removal_stay_separate(self):
        order = RestingOrder('B', 100, 1)
        order.update('F', 'B', 100, 1)
        order.update('M', 'B', 100, 1)
        self.assertEqual(order.implied_additions, 1)
        self.assertEqual(order.update('C', 'B', 100, 1), 'unmatched_clear')
        self.assertEqual(order.fills, 1)
        self.assertEqual(order.unlinked_reductions, 1)

    def test_reprice_is_not_a_fill(self):
        order = RestingOrder('B', 100, 3)
        self.assertEqual(order.update('M', 'B', 99, 3), 'reprice')
        self.assertEqual(order.fills, 0)

    def test_aging_alone_can_reverse_rolling_flow(self):
        buy = np.zeros(24); sell = np.zeros(24)
        buy[0] = 3; sell[1] = 2
        f = rolling_flow(buy, sell)
        self.assertEqual(f['state'][19], 1)
        self.assertEqual(f['state'][20], -1)
        self.assertTrue(f['age_only_change'][20])
        self.assertFalse(f['age_only_change'][19])

    def test_final_group_add_is_visible_before_session_censor(self):
        tape = [(i, SimpleNamespace(order_id=7, action=action, side='B',
                                    price=100, size=2, ts_recv=1000+i), 'test', i)
                for i, action in enumerate(('T', 'A'))]
        groups = np.array([[1001, 1, 201, 100, 101, 2, 2, 1, 0]], dtype=np.int64)
        with patch('research_atlas.raw_records', return_value=iter(tape)), \
             patch('research_atlas.save'), patch('research_atlas.dump'):
            events, _ = mechanism_inventory([], groups)
        self.assertEqual(events.iloc[0].size_at_start_close, 2)
        self.assertEqual(events.iloc[0].end_kind, 'session_end_censored')


class RetainedEvidence(unittest.TestCase):
    def test_event_identity_and_known_case_accounting(self):
        events = pd.read_csv(OUT/'aggression-to-rest-events.csv')
        self.assertEqual(len(events), 980)
        self.assertTrue(events.event_id.is_unique)
        case = events[events.order_id.eq(788701345922)].iloc[0]
        self.assertEqual(case.total_passive_fill_lots, 150)
        self.assertEqual(case.unlinked_display_reductions, 0)
        self.assertEqual(case.duration_from_start_close_ns, 204026301)
        self.assertTrue((events.first_trade_cursor < events.add_cursor).all())
        self.assertTrue((events.add_cursor <= events.start_close_cursor).all())

    def test_observation_features_are_available_by_decision(self):
        decisions = pd.read_csv(OUT/'resting-observation-decisions.csv.gz')
        self.assertTrue((decisions.last_action_known_by_ns <= decisions.decision_cutoff_ns).all())
        self.assertTrue((decisions.quote_receive_ns <= decisions.decision_cutoff_ns).all())
        self.assertNotIn('end_kind', decisions.columns)
        self.assertEqual(decisions.groupby('delay_ms').eligible.sum().to_dict(),
                         {0: 980, 5: 585, 25: 395, 100: 349})
        outcomes = pd.read_csv(OUT/'resting-observation-outcomes.csv.gz')
        self.assertTrue((outcomes.target_ns > outcomes.decision_cutoff_ns).all())
        self.assertTrue((outcomes.endpoint_receive_ns <= outcomes.target_ns).all())
        self.assertTrue(outcomes.eligible.all())

    def test_all_chart_states_preserve_populations(self):
        configs = json.loads((OUT/'interactive-configs.json').read_text())
        self.assertEqual(len(configs), 20)
        for horizon in (1, 5, 20, 60, 300):
            for view, population in [('dipole', 863), ('resting', 980)]:
                config = configs[f'{view}-{horizon}-all']
                self.assertEqual(sum(r['count'] for r in config['rows']), population)
            for scope, population in [('all', 437), ('original', 50)]:
                config = configs[f'family-{horizon}-{scope}']
                self.assertEqual(len(config['rows']), population)
                self.assertTrue(all(np.isfinite(r['flow']) and np.isfinite(r['touch']) for r in config['rows']))


if __name__ == '__main__':
    unittest.main()
