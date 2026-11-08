import unittest
import pandas as pd
from research_atlas_dipole import flow_change_reason, half_activity
from research_atlas import OUT


class DipoleAccounting(unittest.TestCase):
    def test_expiry_is_not_new_opposition(self):
        self.assertEqual(flow_change_reason(0, 0, 3, 0), 'expiry_only')
        self.assertEqual(flow_change_reason(0, 2, 0, 0), 'fresh_only')
        self.assertEqual(flow_change_reason(0, 2, 3, 0), 'fresh_and_expiry')

    def test_empty_half_stays_distinct_from_balanced_trading(self):
        self.assertEqual(half_activity([1, 0, 0, 0], [0, 0, 0, 0]), 'late_empty')
        self.assertEqual(half_activity([1, 0, 1, 0], [0, 1, 0, 1]), 'both_active')

    def test_all_candidates_retained_and_inputs_available(self):
        f=pd.read_csv(OUT/'dipole-operator-observations.csv.gz',dtype={'decision_ns':str,'source_bin_closed_by_ns':str})
        self.assertEqual(len(f),863*5)
        self.assertEqual(f.groupby('stage').candidate_id.nunique().to_dict(),
                         {s:863 for s in ['prebirth_1s','prebirth_5s','prebirth_20s','prebirth_60s','recognition']})
        self.assertTrue(all(int(r.source_bin_closed_by_ns)<=int(r.decision_ns) for r in f.itertuples()))
        self.assertNotIn('birth_polarity',f.columns)
        self.assertTrue(f.loc[f.half_activity.eq('both_empty'),'operator_defined'].eq(False).all())

    def test_path_accounting_never_calls_expiry_new_volume(self):
        p=pd.read_csv(OUT/'dipole-weakening-path.csv.gz')
        expiry=p[p.reason.eq('expiry_only')]
        self.assertTrue((expiry.buy_lots+expiry.sell_lots).eq(0).all())
        self.assertTrue((expiry.expired_buy_lots+expiry.expired_sell_lots).gt(0).all())
        self.assertTrue((p.bin_closed_by_ns<=p.recognition_ns).all())


if __name__ == '__main__':
    unittest.main()
