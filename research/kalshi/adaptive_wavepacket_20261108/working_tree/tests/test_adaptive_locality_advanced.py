import json
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

class ReviewFixCheckpointAndWorkloadTests(unittest.TestCase):
    """Findings E-12 and E-13."""

    def test_e13_distinct_load_failures_keep_cause(self):
        with tempfile.TemporaryDirectory() as folder:
            missing=Path(folder)/"missing.json"
            with self.assertRaises(LocalityError) as ctx:
                load_snapshot(missing,source_identity="s",contract_identity="c")
            self.assertIn("missing",str(ctx.exception))
            self.assertIsInstance(ctx.exception.__cause__,FileNotFoundError)
            torn=Path(folder)/"torn.json"
            torn.write_text('{"schema":1,"payload":',encoding="utf-8")
            with self.assertRaises(LocalityError) as ctx:
                load_snapshot(torn,source_identity="s",contract_identity="c")
            self.assertIn("torn",str(ctx.exception))
            self.assertIsInstance(ctx.exception.__cause__,ValueError)
            folder_path=Path(folder)/"dir.json"
            folder_path.mkdir()
            with self.assertRaises(LocalityError) as ctx:
                load_snapshot(folder_path,source_identity="s",contract_identity="c")
            self.assertIn("unreadable",str(ctx.exception))
            self.assertIsInstance(ctx.exception.__cause__,OSError)
            good=Path(folder)/"good.json"
            seal_snapshot(good,{"v":1},source_identity="s",contract_identity="c")
            tampered=json.loads(good.read_text(encoding="utf-8"))
            tampered["payload"]={"v":2}
            good.write_text(json.dumps(tampered),encoding="utf-8")
            with self.assertRaises(LocalityError) as ctx:
                load_snapshot(good,source_identity="s",contract_identity="c")
            self.assertIn("tampered",str(ctx.exception))

    def test_e13_nan_payload_is_a_locality_error(self):
        with tempfile.TemporaryDirectory() as folder:
            target=Path(folder)/"nan.json"
            with self.assertRaises(LocalityError) as ctx:
                seal_snapshot(target,{"v":float("nan")},source_identity="s",contract_identity="c")
            self.assertIsInstance(ctx.exception.__cause__,ValueError)
            self.assertFalse(target.exists())
            with self.assertRaises(LocalityError):
                seal_snapshot(target,{"v":float("inf")},source_identity="s",contract_identity="c")

    def test_e12_workload_rejects_nonfinite_and_bool(self):
        good=Workload("src","data","env",100,100,90,10.,5.,1000,"output")
        self.assertEqual(good.original_jobs,100)
        for field,value in (("cpu_seconds",float("nan")),("elapsed_seconds",float("inf")),
                            ("original_jobs",True),("completed_jobs",False),
                            ("distinct_pairs",True),("bytes_read",float("nan")),
                            ("cpu_seconds",True)):
            kwargs=dict(good.__dict__); kwargs[field]=value
            with self.assertRaises(LocalityError,msg=field):
                Workload(**kwargs)

    def test_e12_comparison_reports_pairs_and_bytes(self):
        a=Workload("src","data","env",100,100,90,10,5,1000,"output")
        b=Workload("src2","data","env",90,90,70,8,4,900,"output")
        result=compare_workloads(a,b)
        self.assertEqual(result["distinct_pairs"],{"baseline":90,"candidate":70})
        self.assertEqual(result["bytes_read"],{"baseline":1000,"candidate":900})
        self.assertEqual(result["distinct_pairs_delta"],-20)
        self.assertEqual(result["bytes_read_delta"],-100)
        self.assertFalse(result["safe_to_promote"])
        c=Workload("src","other-data","env",100,100,90,10,5,1000,"output")
        incomparable=compare_workloads(a,c)
        self.assertIsNone(incomparable["distinct_pairs_delta"])
        self.assertEqual(incomparable["distinct_pairs"],{"baseline":90,"candidate":90})

if __name__=="__main__":unittest.main()
