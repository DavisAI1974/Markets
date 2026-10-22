import unittest
from external_classroom_reconstruction import value_state, select_known, align_known, claim_relation


class ExternalClassroomTests(unittest.TestCase):
    def test_null_bool_and_non_numeric_states_remain_distinct(self):
        self.assertEqual(value_state(None)[:2], (1, None))
        for value in [True, 'M', 'nan', float('inf')]:
            self.assertEqual(value_state(value)[0], 2)
        self.assertEqual(value_state('0')[:2], (0, 0.0))

    def test_exact_ns_stable_same_stamp_scope_and_no_future(self):
        stamp = 1697662799696377528
        rows = [dict(published_ns=stamp, station='A', tmpf=2),
                dict(published_ns=stamp-1, station='B', tmpf=99),
                dict(published_ns=stamp, station='A', tmpf=None),
                dict(published_ns=stamp+1, station='A', tmpf=4)]
        known = select_known(rows, 'tmpf', {'station': 'A'}, stamp)
        self.assertEqual(len(known), 2)
        self.assertEqual(align_known(known, stamp-1), (-1, 1, None))
        self.assertEqual(align_known(known, stamp), (1, 1, None))
        self.assertEqual(align_known(known, stamp+1), (1, 1, None))

    def test_mos_horizons_remain_scoped_to_source_file_for_reproduction(self):
        rows = [dict(published_ns=10, model='GFS', horizon_days=0, gw_hdd=5),
                dict(published_ns=11, model='GFS', horizon_days=1, gw_hdd=99)]
        known = select_known(rows, 'gw_hdd', {'model':'GFS', 'horizon_days':0}, 11)
        self.assertEqual(align_known(known, 11), (0, 0, 5.0))

    def test_claim_premise_relation_is_required(self):
        self.assertEqual(claim_relation('end this window SAME_DIRECTION first-to-last'), 'SAME_DIRECTION')
        with self.assertRaises(ValueError):
            claim_relation('no stated endpoint relation')


if __name__ == '__main__': unittest.main()
