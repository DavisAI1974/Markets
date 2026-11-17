import tempfile
import unittest
from pathlib import Path
from adaptive_locality.core import Observation,MetricContract,LocalityError
from adaptive_locality.advanced import (AdaptivePolicy,adaptive_neighborhood,PackingIndex,
                                        window_drift,localized_weights)
from adaptive_locality.checkpoints import seal_snapshot,load_snapshot
from adaptive_locality.experiments import Workload,compare_workloads

def obs(i,x,f="P"):
    return Observation(str(i),f,{"spread":float(x)},i,"fixture")

class AdvancedTests(unittest.TestCase):
    def setUp(self):
        self.metric=MetricContract(("spread",),(1.0,),(1.0,),"v1")
    def test_adaptive_historical_and_hysteresis(self):
        n=adaptive_neighborhood(obs(5,1),[obs(1,0.8),obs(2,0.9),obs(6,1)],self.metric,
                                AdaptivePolicy(k=3,min_support=2),previous_bandwidth=0.2)
        self.assertEqual(n.status,"READY")
        self.assertEqual(len(n.neighbors),2)
        self.assertAlmostEqual(n.bandwidth,0.2)
        empty=adaptive_neighborhood(obs(1,0),[],self.metric,AdaptivePolicy())
        self.assertEqual(empty.status,"ABSTAIN_LOW_SUPPORT")
    def test_packing_and_reversibility(self):
        p=PackingIndex(self.metric,0.5)
        a,b,c=obs(1,0),obs(2,0.1),obs(3,1)
        p.admit_center(a,p.propose(a))
        self.assertEqual(p.propose(b).action,"ASSIGN_CANDIDATE")
        p.admit_center(c,p.propose(c))
        p.retire("3","test")
        self.assertIn("3",p.retired)
        p.restore(c)
        self.assertIn("3",p.centers)
    def test_weights_and_drift(self):
        weights=localized_weights(obs(9,0.2),[obs(1,0),obs(2,1)],self.metric,0.5)
        self.assertAlmostEqual(sum(weights["weights"].values()),1)
        self.assertFalse(window_drift([obs(i,float(i)) for i in range(4)],self.metric,2,0.1)["stable_across_windows"])
    def test_checkpoint_rejects_conflicts(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"state.json"
            seal_snapshot(p,{"groups":[1,2]},source_identity="source",contract_identity="v1")
            self.assertEqual(load_snapshot(p,source_identity="source",contract_identity="v1"),{"groups":[1,2]})
            with self.assertRaises(LocalityError): seal_snapshot(p,{},source_identity="source",contract_identity="v1")
            with self.assertRaises(LocalityError): load_snapshot(p,source_identity="other",contract_identity="v1")
            p.write_text('{"broken":true}')
            with self.assertRaises(LocalityError): load_snapshot(p,source_identity="source",contract_identity="v1")
    def test_comparison_cannot_auto_promote(self):
        a=Workload("src","data","env",100,100,90,10,5,1000,"output")
        b=Workload("src2","data","env",90,90,90,8,4,900,"output")
        result=compare_workloads(a,b)
        self.assertTrue(result["comparable"])
        self.assertTrue(result["exact_output_identity"])
        self.assertFalse(result["safe_to_promote"])
if __name__=="__main__":unittest.main()
