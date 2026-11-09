"""Standard-library tests; no fixtures or production data required."""
import unittest
from adaptive_locality import (Observation,MetricContract,LocalityConfig,LocalityEngine,
    finite_cauchy,gaussian_kernel,graph_neumann_residual,LocalityError,
    DecisionLedger,ScientificGate,JobReceipt)
from adaptive_locality.adapters import EvidenceManifest,shadow_batch,buildmap_evidence

def event(i,x,family="A",direction="BUY"):
    return Observation(str(i),family,{"imbalance":x,"spread":1.0},i,"immutable-test",order_id="order-"+str(i),direction=direction)

class LocalityTests(unittest.TestCase):
    def setUp(self):
        self.metric=MetricContract(("imbalance","spread"),(1.0,1.0),(1.0,1.0),"v1")
        self.engine=LocalityEngine(self.metric,LocalityConfig(1.0,0.5))
    def test_metric_and_kernel(self):
        self.assertAlmostEqual(self.metric.distance(event(1,0),event(2,1)),1)
        self.assertEqual(gaussian_kernel(0,1),1)
        with self.assertRaises(LocalityError): gaussian_kernel(1,0)
        with self.assertRaises(LocalityError): MetricContract(("order_id",),(1,),(1,),"v1")
    def test_conservative_membership(self):
        a,b,c=event(1,0),event(2,0.2),event(3,0.3,"B")
        first=self.engine.propose(a)
        self.assertEqual(first.status,"NEW_CENTER")
        self.engine.admit(a,first)
        second=self.engine.propose(b)
        self.assertEqual(second.status,"PROPOSE_ONLY")
        self.assertEqual(second.proposed_center,"1")
        self.assertAlmostEqual(sum(x[2] for x in second.candidates),1)
        self.engine.admit(b,second)
        self.assertEqual(self.engine.propose(c).status,"NEW_CENTER")
        self.assertEqual(self.engine.count,2)
        self.assertEqual(self.engine.propose(a).status,"DUPLICATE")
    def test_stale_and_conflict(self):
        a=event(1,0)
        d=self.engine.propose(a)
        self.engine.admit(event(2,0.1),self.engine.propose(event(2,0.1)))
        with self.assertRaises(LocalityError): self.engine.admit(a,d)
        with self.assertRaises(LocalityError): self.engine.propose(event(2,8))
    def test_finite_not_infinite(self):
        self.assertTrue(finite_cauchy([event(1,0),event(2,0.001)],self.metric,0.01,2).finite_window)
        self.assertFalse(finite_cauchy([event(1,0),event(2,1)],self.metric,0.01,2).finite_window)
    def test_graph_residual(self):
        self.assertEqual(graph_neumann_residual({"a":1,"b":1},[("a","b",2)],["a"]),{"a":0})
    def test_scientific_gate_direction(self):
        a=JobReceipt("j1","src","input","metric","A","AB","out",True,True)
        b=JobReceipt("j2","src","input","metric","A","BA","out",True,True)
        self.assertFalse(ScientificGate.equivalent(a,b)[0])
        self.assertTrue(ScientificGate.equivalent(a,a)[0])
    def test_ledger_and_shadow(self):
        ledger=DecisionLedger()
        manifest=EvidenceManifest("r","day","source",("plane1","plane2"))
        result=shadow_batch([event(1,0),event(2,0.1)],self.engine,ledger,manifest)
        self.assertTrue(ledger.verify())
        self.assertEqual(result["scientific_jobs_eliminated"],0)
        exported=buildmap_evidence(result)
        self.assertEqual(exported["trust"],"UNSIGNED_RESEARCH_ARTIFACT_NOT_ACCEPTANCE_EVIDENCE")
        self.assertEqual(len(exported["decisions"]),2)
if __name__=="__main__":unittest.main()
