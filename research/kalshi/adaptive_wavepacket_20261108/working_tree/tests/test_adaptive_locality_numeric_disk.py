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


class DiskIndexReviewFixTests(unittest.TestCase):
    """Disk index findings E-1, E-2, E-6, E-9 and the missing-coverage tests."""

    def setUp(self):
        self.metric=MetricContract(("x","y"),(1.,1.),(1.,1.),"v")

    def test_e1_exact_radius_boundary_hit(self):
        metric=MetricContract(("x",),(1,),(1,),"boundary-v1")
        center=Observation("c","P",{"x":1-2**-53},1,"synthetic",direction="AB")
        query=Observation("q","P",{"x":2.0},2,"synthetic",direction="AB")
        self.assertEqual(metric.distance(query,center),1.0)
        with tempfile.TemporaryDirectory() as folder:
            with DiskGridIndex(Path(folder)/"i.db",metric,1.0,source_identity="s") as ix:
                ix.add(center)
                self.assertEqual([(h.center_id,h.distance) for h in ix.candidates(query)],[("c",1.0)])
            with DiskGridIndex(Path(folder)/"j.db",metric,1.0,source_identity="s") as ix:
                ix.add(Observation("c2","P",{"x":2.0},1,"synthetic",direction="AB"))
                mirrored=Observation("q2","P",{"x":1-2**-53},2,"synthetic",direction="AB")
                self.assertEqual([h.center_id for h in ix.candidates(mirrored)],["c2"])

    def test_e1_randomized_differential_with_boundary_pairs(self):
        rng=random.Random(7)
        for radius in (0.5,1.0,2.5):
            centers=[obs(i,rng.uniform(-6,6),rng.uniform(-6,6),"P" if i%3 else "X","AB" if i%4 else "BA")
                     for i in range(1,91)]
            centers.append(Observation("edge-lo","P",{"x":radius*(1-2**-53),"y":0.},1,"synthetic",direction="AB"))
            centers.append(Observation("edge-hi","P",{"x":2*radius,"y":0.},1,"synthetic",direction="AB"))
            targets=[obs(n,rng.uniform(-6,6),rng.uniform(-6,6),"P" if n%2 else "X","AB" if n%3 else "BA")
                     for n in range(100,130)]
            targets.append(Observation("tq-lo","P",{"x":2*radius,"y":0.},200,"synthetic",direction="AB"))
            targets.append(Observation("tq-hi","P",{"x":radius*(1-2**-53),"y":0.},201,"synthetic",direction="AB"))
            with tempfile.TemporaryDirectory() as folder:
                with DiskGridIndex(Path(folder)/"c.db",self.metric,radius,source_identity="s") as ix:
                    for c in centers:
                        ix.add(c)
                    for target in targets:
                        expected=sorted([(self.metric.distance(target,c),c.event_id) for c in centers
                                         if c.family==target.family and c.direction==target.direction
                                         and c.event_clock<=target.event_clock
                                         and self.metric.distance(target,c)<=radius])
                        actual=[(h.distance,h.center_id) for h in ix.candidates(target,max_neighbors=4096)]
                        self.assertEqual(actual,expected)

    def test_e2_restore_keeps_retirement_reason_and_history(self):
        with tempfile.TemporaryDirectory() as folder:
            with DiskGridIndex(Path(folder)/"i.db",self.metric,1.,source_identity="s") as ix:
                a=obs(1,0.)
                ix.add(a)
                ix.retire("1","manual review: suspected duplicate feed")
                ix.restore(a)
                self.assertIsNotNone(ix.get("1"))
                rows=ix.history("1")
                self.assertEqual([r["action"] for r in rows],["RETIRE","RESTORE"])
                self.assertEqual(rows[0]["reason"],"manual review: suspected duplicate feed")
                self.assertEqual(rows[1]["reason"],"manual review: suspected duplicate feed")
                self.assertLess(rows[0]["revision"],rows[1]["revision"])
                self.assertEqual(rows[0]["seq"]+1,rows[1]["seq"])
                stored=ix.db.execute("SELECT reason FROM centers WHERE event_id='1'").fetchone()[0]
                self.assertEqual(stored,"manual review: suspected duplicate feed")
                self.assertEqual(ix.history("missing"),())

    def test_e6_candidate_report_truncation_disclosed(self):
        with tempfile.TemporaryDirectory() as folder:
            with DiskGridIndex(Path(folder)/"i.db",self.metric,1.,source_identity="s") as ix:
                for i in range(1,6):
                    ix.add(obs(i,0.1*i))
                query=obs(50,0.)
                report=ix.candidate_report(query,max_neighbors=2)
                self.assertEqual(len(report["hits"]),2)
                self.assertEqual(report["total_in_radius"],5)
                self.assertTrue(report["truncated"])
                self.assertEqual(report["revision"],ix.revision)
                self.assertEqual(ix.candidates(query,max_neighbors=2),report["hits"])
                full=ix.candidate_report(query,max_neighbors=64)
                self.assertFalse(full["truncated"])
                self.assertEqual(len(full["hits"]),5)

    def test_e9_candidate_read_is_transactional_and_reports_revision(self):
        with tempfile.TemporaryDirectory() as folder:
            with DiskGridIndex(Path(folder)/"i.db",self.metric,1.,source_identity="s") as ix:
                ix.add(obs(1,0.))
                self.assertFalse(ix.db.in_transaction)
                report=ix.candidate_report(obs(9,0.))
                self.assertFalse(ix.db.in_transaction)
                self.assertEqual(report["revision"],1)
                ix.add(obs(2,0.))
                self.assertEqual(ix.candidate_report(obs(9,0.))["revision"],2)

    def test_streaming_fallback_above_grid_dimension_limit(self):
        metric=MetricContract(tuple("abcdef"),(1.,)*6,(1.,)*6,"v6")
        base=dict.fromkeys(metric.features,0.)
        with tempfile.TemporaryDirectory() as folder:
            with DiskGridIndex(Path(folder)/"i.db",metric,1.,source_identity="s") as ix:
                self.assertFalse(ix.indexed)
                ix.add(Observation("a","P",base,1,"s",direction="AB"))
                ix.add(Observation("b","X",base,2,"s",direction="AB"))
                query=Observation("q","P",base,5,"s",direction="AB")
                self.assertEqual([h.center_id for h in ix.candidates(query)],["a"])
                self.assertEqual([h.center_id for h in ix.candidates(query,allow_cross_family=True)],["a","b"])
                self.assertFalse(ix.snapshot()["grid_accelerated"])

    def test_metric_and_radius_mismatch_on_reopen(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"i.db"
            with DiskGridIndex(path,self.metric,1.,source_identity="s"):
                pass
            with self.assertRaises(LocalityError):
                with DiskGridIndex(path,self.metric,2.,source_identity="s"):
                    pass
            other=MetricContract(("x","y"),(1.,2.),(1.,1.),"v")
            with self.assertRaises(LocalityError):
                with DiskGridIndex(path,other,1.,source_identity="s"):
                    pass


class GroupingReviewFixTests(unittest.TestCase):
    """Grouping findings E-4 and E-16."""

    def setUp(self):
        self.metric=MetricContract(("x","y"),(1.,1.),(1.,1.),"v")

    def test_e4_refusals_are_ledgered_before_raising(self):
        with tempfile.TemporaryDirectory() as folder:
            with DiskGridIndex(Path(folder)/"i.db",self.metric,1.,source_identity="s") as ix:
                g=ShadowGrouper(ix)
                first=obs(5,0.)
                g.admit(first,g.propose(first))
                with self.assertRaises(LocalityError):
                    g.propose(obs(3,0.))  # non-monotone ordering
                with self.assertRaises(LocalityError):
                    g.propose(replace(first,member_id="tampered"))  # conflicting evidence
                refused=[e for e in g.snapshot()["entries"] if e["kind"]=="REFUSED"]
                self.assertEqual(len(refused),2)
                self.assertEqual(refused[0]["payload"]["event_id"],"3")
                self.assertIn("ordering",refused[0]["payload"]["reason"])
                self.assertEqual(refused[1]["payload"]["event_id"],"5")
                self.assertEqual(g.snapshot()["refused"],2)
                self.assertTrue(g.verify())
                self.assertEqual(len(g.snapshot()["entries"]),g.snapshot()["ledger_count"])

    def test_e4_proposal_carries_alternatives_from_candidate_report(self):
        with tempfile.TemporaryDirectory() as folder:
            with DiskGridIndex(Path(folder)/"i.db",self.metric,1.,source_identity="s") as ix:
                g=ShadowGrouper(ix,alternatives=2)
                for i in range(1,5):
                    e=obs(i,float(i)*3)  # four isolated centres
                    g.admit(e,g.propose(e))
                for i,x in ((10,0.5),(11,0.4),(12,0.3),(13,0.6)):
                    ix.add(Observation(str(i),"P",{"x":x,"y":0.},i,"synthetic",direction="AB"))
                query=obs(20,0.)
                proposal=g.propose(query)
                self.assertEqual(proposal.status,"ASSIGN_SHADOW_ONLY")
                self.assertEqual(proposal.center_id,"12")
                self.assertEqual([c for c,_ in proposal.alternatives],["11","10"])
                self.assertEqual(proposal.total_in_radius,4)
                self.assertTrue(proposal.truncated)
                g.admit(query,proposal)
                self.assertEqual(g.snapshot()["members"]["20"]["center_id"],"12")

    def test_e4_snapshot_recover_round_trip_and_chain_verification(self):
        with tempfile.TemporaryDirectory() as folder:
            with DiskGridIndex(Path(folder)/"i.db",self.metric,1.,source_identity="s") as ix:
                g=ShadowGrouper(ix)
                for e in (obs(1,0.),obs(2,0.2),obs(3,5.),obs(4,9.)):
                    g.admit(e,g.propose(e))
                g.alias_view("3","4","display only")
                with self.assertRaises(LocalityError):
                    g.propose(obs(0,0.))  # a REFUSED entry must survive the round trip
                snap=g.snapshot()
                restored=ShadowGrouper.recover(ix,snap)
                self.assertEqual(restored.snapshot(),snap)
                self.assertTrue(restored.verify())
                nxt=obs(5,0.1)
                self.assertEqual(restored.propose(nxt).center_id,"1")
                with self.assertRaises(LocalityError):
                    restored.propose(obs(3,7.))  # last_order restored: clock 3 is not after 4
                self.assertEqual(restored.snapshot()["refused"],snap["refused"]+1)
                bad=dict(snap,entries=[dict(e,payload=dict(e["payload"],event_id="x")) for e in snap["entries"]])
                with self.assertRaises(LocalityError):
                    ShadowGrouper.recover(ix,bad)
                with self.assertRaises(LocalityError):
                    ShadowGrouper.recover(ix,dict(snap,source_identity="other"))

    def test_e16_counters_are_derived_from_ledger_kinds(self):
        with tempfile.TemporaryDirectory() as folder:
            with DiskGridIndex(Path(folder)/"i.db",self.metric,1.,source_identity="s") as ix:
                g=ShadowGrouper(ix)
                g.admit(obs(1,0.),g.propose(obs(1,0.)))
                snap=g.snapshot()
                self.assertEqual(snap["discarded"],0)
                self.assertEqual(snap["averaged"],0)
                self.assertEqual(snap["flattened"],0)
                self.assertEqual(snap["refused"],0)
                self.assertEqual(snap["counter_derivation"],"derived from ledger kinds")
                self.assertEqual(snap["ledger_kind_counts"],{"ADMIT_SHADOW_ONLY":1})
                g._log("DISCARD",{"event_id":"synthetic-proof","reason":"test only"})
                self.assertEqual(g.snapshot()["discarded"],1)


if __name__=="__main__":
    unittest.main()
