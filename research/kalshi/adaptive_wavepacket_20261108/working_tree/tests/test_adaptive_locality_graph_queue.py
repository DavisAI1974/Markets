import unittest
from adaptive_locality.core import LocalityError
from adaptive_locality.graph_boundary import Edge,FluxDomain,divergence,conservative_step,total_mass,stable_explicit_dt
from adaptive_locality.queue import ReadyGroup,ShadowQueue

class GraphAndQueueTests(unittest.TestCase):
    def test_reflecting_flux_conserves_mass(self):
        domain=FluxDomain({"a":1.0,"b":2.0},(Edge("a","b",1.0),),("a","b"))
        initial={"a":1.0,"b":0.0}
        next_state=conservative_step(domain,initial,0.1)
        self.assertAlmostEqual(total_mass(domain,initial),total_mass(domain,next_state))
        self.assertGreater(stable_explicit_dt(domain),0)
    def test_outward_flux_removes_mass(self):
        domain=FluxDomain({"a":1.0,"b":1.0},(Edge("a","b",1.0),),("a",))
        first={"a":1.0,"b":1.0}
        second=conservative_step(domain,first,0.1,{"a":0.5})
        self.assertAlmostEqual(total_mass(domain,first)-total_mass(domain,second),0.05)
        with self.assertRaises(LocalityError): conservative_step(domain,first,0.1,{"b":1})
    def test_queue_recovery_and_conflict(self):
        q=ShadowQueue(capacity=1)
        g=ReadyGroup("g","src","features",("e1",),"P","AB")
        self.assertEqual(q.submit(g),"QUEUED")
        self.assertEqual(q.submit(g),"ALREADY_PENDING")
        self.assertEqual(q.submit(ReadyGroup("other","src","features",("e2",),"P","AB")),"BACKPRESSURE")
        restored=ShadowQueue.recover(q.snapshot())
        self.assertEqual(restored.preview(),(g,))
        restored.mark_completed("g",g.identity())
        self.assertEqual(restored.submit(g),"ALREADY_COMPLETED")
        with self.assertRaises(LocalityError):
            restored.submit(ReadyGroup("g","different","features",("e1",),"P","AB"))
if __name__=="__main__":unittest.main()
