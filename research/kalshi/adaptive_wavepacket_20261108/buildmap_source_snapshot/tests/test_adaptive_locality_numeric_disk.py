"""Standalone, synthetic-only numeric, disk, and lossless outlier guarantees."""
import math
import random
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

from adaptive_locality.core import Observation, MetricContract, LocalityError
from adaptive_locality.advanced import localized_weights
from adaptive_locality.disk_index import DiskGridIndex
from adaptive_locality.grouping import ShadowGrouper
from adaptive_locality.outliers import OutlierRegistry


def obs(i,x,y=0.,family="P",direction="AB"):
    return Observation(str(i),family,{"x":float(x),"y":float(y)},i,"synthetic",
                       order_id="order-"+str(i),member_id="member-"+str(i),
                       direction=direction)


class NumericDiskAndOutlierTests(unittest.TestCase):
    def setUp(self):
        self.metric=MetricContract(("x","y"),(1.,1.),(1.,1.),"v")

    def test_observation_original_features_are_immutable(self):
        original={"x":1.,"y":2.}
        event=Observation("e","P",original,1,"source")
        original["x"]=10.
        self.assertEqual(event.features["x"],1.)
        with self.assertRaises(TypeError):
            event.features["x"]=4.
        with self.assertRaises(FrozenInstanceError):
            event.family="X"
        self.assertEqual(event.identity(),Observation("e","P",{"x":1.,"y":2.},1,"source").identity())

    def test_metric_large_finite_values_and_nonfinite_abstention(self):
        a=obs(1,1e200)
        b=obs(2,-1e200)
        self.assertAlmostEqual(self.metric.distance(a,b)/2e200,1.)
        with self.assertRaises(LocalityError):
            self.metric.distance(obs(1,1e308),obs(2,-1e308))
        with self.assertRaises(LocalityError):
            MetricContract(("x",),(0.,),(1.,),"bad")
        with self.assertRaises(LocalityError):
            self.metric.vector(Observation("missing","P",{"x":1.},1,"s"))
        stable=localized_weights(obs(3,0),[obs(1,1e200),obs(2,1e200)],self.metric,1.)
        self.assertEqual(stable["status"],"ABSTAIN_NUMERIC")

    def test_disk_index_differential_with_out_of_order_candidates(self):
        rng=random.Random(42)
        centers=[obs(i,rng.uniform(-10,10),rng.uniform(-10,10),
                     "P" if i%3 else "X","AB" if i%4 else "BA")
                 for i in range(1,101)]
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"centers.sqlite"
            with DiskGridIndex(path,self.metric,2.,source_identity="source") as ix:
                for center in centers:
                    ix.add(center)
                self.assertEqual(ix.count,len(centers))
                for n in range(101,141):
                    target=obs(n,rng.uniform(-10,10),rng.uniform(-10,10),
                               "P" if n%2 else "X","AB" if n%3 else "BA")
                    expected=sorted(
                        [(self.metric.distance(target,c),c.event_id)
                         for c in centers
                         if c.family==target.family and c.direction==target.direction
                         and c.event_clock<=target.event_clock
                         and self.metric.distance(target,c)<=2.],
                        key=lambda pair:(pair[0],pair[1]))[:8]
                    actual=ix.candidates(target,max_neighbors=8)
                    self.assertEqual([(h.distance,h.center_id) for h in actual],expected)
                self.assertEqual(ix.add(centers[0]),"EXISTS")
                ix.retire(centers[0].event_id,"review")
                self.assertIsNone(ix.get(centers[0].event_id))
                with self.assertRaises(LocalityError):
                    ix.restore(replace(centers[0],direction="changed"))
                ix.restore(centers[0])
                self.assertEqual(ix.get(centers[0].event_id).identity(),centers[0].identity())
            with DiskGridIndex(path,self.metric,2.,source_identity="source") as recovered:
                self.assertEqual(recovered.count,100)
            with self.assertRaises(LocalityError):
                with DiskGridIndex(path,self.metric,2.,source_identity="wrong"):
                    pass

    def test_outliers_retained_original_no_averaging_or_flattening(self):
        with tempfile.TemporaryDirectory() as folder:
            with DiskGridIndex(Path(folder)/"idx.db",self.metric,1.,
                               source_identity="src") as index:
                with OutlierRegistry(Path(folder)/"review.db",source_identity="src") as reviews:
                    g=ShadowGrouper(index)
                    first=obs(1,0.)
                    g.admit(first,g.propose(first))
                    outlier=obs(2,1e6,direction="BA")
                    self.assertEqual(g.flag_outlier(outlier,reviews,"rare directional spike"),
                                     "RETAINED_FOR_REVIEW")
                    self.assertEqual(g.snapshot()["outlier_count"],1)
                    self.assertEqual(g.snapshot()["discarded"],0)
                    self.assertEqual(g.snapshot()["averaged"],0)
                    self.assertEqual(g.snapshot()["flattened"],0)
                    original,record=reviews.get(outlier.event_id)
                    self.assertEqual(original.identity(),outlier.identity())
                    self.assertEqual(dict(original.features),dict(outlier.features))
                    self.assertEqual(original.order_id,outlier.order_id)
                    self.assertEqual(original.member_id,outlier.member_id)
                    self.assertEqual(original.direction,"BA")
                    self.assertEqual(record.review_state,"AWAITING_REVIEW")
                    reviews.review(outlier.event_id,state="UNDER_REVIEW",
                                   reason="investigate original microstructure",
                                   reviewer="analyst")
                    reviews.review(outlier.event_id,state="RETAIN_SEPARATE",
                                   reason="preserve distinct event",
                                   reviewer="analyst")
                    self.assertTrue(reviews.verify())
                    self.assertEqual(reviews.counts()["retained_total"],1)
                    self.assertEqual(reviews.counts()["states"],{"RETAIN_SEPARATE":1})
                    self.assertTrue(g.verify())
                    second=obs(3,0.2)
                    proposal=g.propose(second)
                    self.assertEqual(proposal.status,"ASSIGN_SHADOW_ONLY")
                    g.admit(second,proposal)
                    self.assertEqual(g.snapshot()["members"]["3"]["center_id"],"1")
                    self.assertEqual(len(g.snapshot()["members"]),3)
                    with self.assertRaises(LocalityError):
                        reviews.flag(replace(outlier,member_id="altered"),"different")
                    with self.assertRaises(LocalityError):
                        g.admit(obs(4,0.1),g.propose(obs(4,0.1,direction="BA")))
                    self.assertEqual(g.snapshot()["scientific_jobs_eliminated"],0)


if __name__=="__main__":
    unittest.main()
