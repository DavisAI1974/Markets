import unittest
import numpy as np
import pandas as pd
from research_atlas_stack import same_price_changes, ridge_predict, LAYERS, ARMS
from research_atlas import OUT


class StackMechanics(unittest.TestCase):
    def test_new_best_price_is_not_replenishment(self):
        a=np.array([[0,0,201,100,101,2,3,1,0],
                    [1,1,201,100,101,5,1,1,0],
                    [2,2,203,101,102,20,30,1,0],
                    [3,3,203,101,102,21,29,1,1]])
        x=same_price_changes(a)
        np.testing.assert_array_equal(x[1],[3,0,0,2,0])
        np.testing.assert_array_equal(x[2],[0,0,0,0,2])
        np.testing.assert_array_equal(x[3],[0,0,0,0,0])

    def test_test_rows_do_not_change_training_imputation(self):
        train=np.array([[0.,np.nan],[1.,3.],[2.,4.]])
        y=np.array([0.,1.,2.])
        first=ridge_predict(train,y,np.array([[1.,np.nan]]))[0]
        other=ridge_predict(train,y,np.array([[1.,np.nan],[100000.,-90000.]]))[0]
        self.assertAlmostEqual(first,other)


class RetainedStackEvidence(unittest.TestCase):
    def test_input_clocks_and_future_separation(self):
        f=pd.read_csv(OUT/'stack-features.csv.gz',dtype={'decision_ns':str,'quote_known_by_ns':str,'flow_closed_by_ns':str})
        self.assertEqual(len(f),863)
        self.assertTrue(f.candidate_id.is_unique)
        self.assertTrue(all(int(r.quote_known_by_ns)<=int(r.decision_ns) and int(r.flow_closed_by_ns)<=int(r.decision_ns) for r in f.itertuples()))
        cols=[c for layer in LAYERS.values() for c in layer]
        self.assertFalse(any(any(s in c for s in ('future','birth','cursor','decision','candidate')) for c in cols))
        self.assertFalse(any(c.startswith('future') for c in f.columns))

    def test_all_arms_compare_identical_rows(self):
        p=pd.read_csv(OUT/'stack-predictions.csv.gz')
        for _,g in p.groupby(['target','horizon_s','fold']):
            sets={arm:set(v.candidate_id) for arm,v in g.groupby('arm')}
            self.assertEqual(set(sets),set(ARMS))
            self.assertTrue(all(v==sets['baseline'] for v in sets.values()))
        splits=pd.read_csv(OUT/'stack-splits.csv',dtype=str)
        self.assertTrue(all(int(r.last_train_target_ns)+int(r.embargo_s)*10**9<int(r.test_start_ns) for r in splits.itertuples()))

    def test_state_tables_preserve_each_case_and_flat_outcomes(self):
        s=pd.read_csv(OUT/'stack-conditional-states.csv')
        self.assertEqual(s.groupby('horizon_s').n.sum().to_dict(),{5:863,20:863,60:863})
        self.assertTrue((s.up+s.down+s.flat==s.available).all())


if __name__=='__main__':unittest.main()
