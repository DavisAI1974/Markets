"""Independent review admission tests: preserved outliers and no silent alias replacement."""
import tempfile
import unittest
from pathlib import Path
from adaptive_locality.core import Observation, MetricContract, LocalityError
from adaptive_locality.disk_index import DiskGridIndex
from adaptive_locality.grouping import ShadowGrouper
from adaptive_locality.outliers import OutlierRegistry
from adaptive_locality.benchmark import benchmark


def event(i, value, direction="AB"):
    return Observation(str(i),"P",{"x":float(value)},i,"synthetic",
                       order_id="order-"+str(i),direction=direction)


class LosslessReviewPolicyTests(unittest.TestCase):
    def test_original_outlier_is_not_suppressed_or_averaged(self):
        metric=MetricContract(("x",),(1,),(1,),"v1")
        with tempfile.TemporaryDirectory() as folder:
            with DiskGridIndex(Path(folder)/"index.sqlite",metric,1.,source_identity="s") as idx:
                with OutlierRegistry(Path(folder)/"review.sqlite",source_identity="s") as review:
                    g=ShadowGrouper(idx)
                    a=event(1,0)
                    g.admit(a,g.propose(a))
                    extreme=event(2,100000,"BA")
                    g.flag_outlier(extreme,review,"rare transient surge")
                    self.assertEqual(review.get("2")[0].identity(),extreme.identity())
                    self.assertEqual(review.get("2")[0].features["x"],100000.)
                    self.assertEqual(review.counts()["retained_total"],1)
                    self.assertEqual(g.snapshot()["outlier_count"],1)
                    self.assertNotIn("2",g.index_ids())
                    self.assertEqual(g.snapshot()["scientific_jobs_eliminated"],0)
                    self.assertTrue(review.verify())
                    review.review("2",state="UNDER_REVIEW",reason="inspect source",
                                  reviewer="test-reviewer")
                    review.review("2",state="RETAIN_SEPARATE",reason="different direction",
                                  reviewer="test-reviewer")
                    self.assertEqual(review.get("2")[1].review_state,"RETAIN_SEPARATE")
                    self.assertEqual(len(g.snapshot()["members"]),2)

    def test_alias_cannot_overwrite_existing_alias(self):
        metric=MetricContract(("x",),(1,),(1,),"v1")
        with tempfile.TemporaryDirectory() as folder:
            with DiskGridIndex(Path(folder)/"index.sqlite",metric,1.,source_identity="s") as idx:
                g=ShadowGrouper(idx)
                for e in (event(1,0),event(2,3),event(3,6)):
                    g.admit(e,g.propose(e))
                g.alias_view("1","2","display only")
                with self.assertRaises(LocalityError):
                    g.alias_view("1","3","should not overwrite")
                with self.assertRaises(LocalityError):
                    g.alias_view("2","3","should not chain")
                g.revert_alias("1","manual reversal")
                self.assertEqual(g.snapshot()["view_aliases"],{})
                self.assertTrue(g.verify())

    def test_bounded_benchmark_differential(self):
        report=benchmark(centers=50,queries=12)
        self.assertTrue(report["all_exact_results_match"])
        self.assertEqual(report["scientific_jobs_eliminated"],0)
        self.assertEqual(report["source"],"DETERMINISTIC_SYNTHETIC_ONLY")


if __name__=="__main__":
    unittest.main()
