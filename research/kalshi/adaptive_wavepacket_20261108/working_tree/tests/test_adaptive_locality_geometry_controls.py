"""CPU-bounded predictive/null experiments: never causal or physical evidence."""
import math
import random
import tempfile
import unittest
from pathlib import Path

from adaptive_locality.core import LocalityError
from adaptive_locality.geometry_validation import (
    geometric_predictive_controls,_directional_terms)
from adaptive_locality.research_holds import (
    ResearchHoldRegistry,preserve_geometric_predictive_controls)
from test_adaptive_locality_coupling import frame
from test_adaptive_locality_geometry_validation import original_series


def candidate_series(seed=9, *, mode="coupled", n=160):
    """Synthetic labeled series; independent seeds are tests, not science."""
    rng=random.Random(seed)
    series=[]
    ha=1.2
    for t in range(n):
        hb=1.1+0.29*math.sin(0.17*t)+0.21*math.cos(0.29*t)+0.16*(rng.random()-.5)
        fia=0.5+0.17*math.sin(0.11*t)
        fib=0.7+0.13*math.cos(0.21*t)
        mi=0.20+0.03*math.sin(0.31*t)
        if mode=="independent":
            ha=1.0+0.21*(rng.random()-.5)+0.08*math.sin(0.32*t)
        if mode=="equal-marginal":
            hb=ha
        series.append(frame(t,ha,hb,fia,fib,mi,source=f"synthetic-{seed}-{mode}"))
        if mode in ("coupled","regime-switch"):
            sign=1 if mode=="coupled" or t<90 else -1
            ha+=0.018*(-0.6*ha+sign*0.90*ha*hb+0.03*fia)
    return tuple(series)


class GeometricPredictionControlsTests(unittest.TestCase):
    def test_past_only_geometry_and_exact_match_null_indexing(self):
        data=candidate_series()
        row=_directional_terms(data,20,"a","b",lag=7)
        self.assertAlmostEqual(row[4],
                         dict(data[20].entropy)["a"]*dict(data[13].entropy)["b"])
        with self.assertRaises(LocalityError):
            _directional_terms(data,2,"a","b",lag=7)
        with self.assertRaises(LocalityError):
            _directional_terms(data,2,"a","b",lag=-1)
        report=geometric_predictive_controls(data,"a","b")
        self.assertEqual(report["original_frame_count"],len(data))
        self.assertEqual(report["scientific_jobs_eliminated"],0)
        self.assertEqual(report["frames_dropped"],0)
        self.assertTrue(all(len(s.original_training_frame_identities)==
                            int((len(data)-1)*fraction)-report["past_lag"]
                            for s,fraction in zip(report["splits"],report["split_fractions"])))
        self.assertTrue(all(s.original_testing_frame_identities[-1]==data[-1].raw_identity
                            for s in report["splits"]))

    def test_known_directional_term_is_detectable_as_association_not_causality(self):
        report=geometric_predictive_controls(candidate_series(17),"a","b")
        self.assertEqual(report["status"],"CONSISTENT_MULTISPLIT_ASSOCIATION_REVIEW_ONLY")
        self.assertEqual(report["held_split_count"],0)
        self.assertTrue(all(s.geometry_gain>0.5 for s in report["splits"]))
        self.assertTrue(all(s.geometry_gain>s.past_donor_gain+0.05 for s in report["splits"]))
        self.assertFalse(report["physical_boundary_condition_supported"])

    def test_nested_quadratic_term_adds_future_information_in_known_toy(self):
        # Separately test an explicitly quadratic generative term, not a
        # static Ha²=(HaHb)² algebraic identity. No physical/causal claim.
        rng=random.Random(19)
        frames=[]
        ha=0.85
        for t in range(200):
            hb=0.65+0.95*rng.random()+0.07*math.sin(0.19*t)
            fia=0.55+0.18*math.sin(0.13*t)
            fib=0.45+0.11*math.cos(0.27*t)
            mi=0.2+0.03*math.sin(0.29*t)
            frames.append(frame(t,ha,hb,fia,fib,mi,
                                source="known-quadratic-synthetic"))
            ab=ha*hb
            ha+=0.015*(0.11-0.36*ha+0.08*fia+0.17*ab+0.08*ab*ab)
        report=geometric_predictive_controls(tuple(frames),"a","b")
        supported=[s for s in report["splits"]
                   if s.quadratic_additional_support is True]
        self.assertGreater(len(supported),0)
        self.assertTrue(all(s.quadratic_vs_linear_gain>0.5 for s in supported))
        self.assertTrue(all(s.linear_interaction_holdout_sse>
                            s.geometry_holdout_sse for s in supported))
        self.assertEqual(report["scientific_jobs_eliminated"],0)

    def test_independent_seeds_do_not_become_universal_coupling(self):
        for seed in (2,7,13,23):
            with self.subTest(seed=seed):
                data=candidate_series(seed,mode="independent")
                report=geometric_predictive_controls(data,"a","b")
                self.assertNotEqual(report["status"],
                                    "CONSISTENT_MULTISPLIT_ASSOCIATION_REVIEW_ONLY")
                self.assertEqual(report["scientific_jobs_eliminated"],0)

    def test_equal_marginal_rank_degeneracy_and_regime_shift_not_discarded(self):
        equal=geometric_predictive_controls(candidate_series(8,mode="equal-marginal"),
                                           "a","b")
        self.assertEqual(equal["status"],"RESEARCH_HOLD")
        self.assertGreater(equal["held_split_count"],0)
        self.assertEqual(len(equal["preserved_frame_identities"]),160)
        changed=geometric_predictive_controls(candidate_series(8,mode="regime-switch"),
                                             "a","b")
        self.assertNotEqual(changed["status"],
                            "CONSISTENT_MULTISPLIT_ASSOCIATION_REVIEW_ONLY")
        self.assertEqual(changed["frames_dropped"],0)

    def test_all_splits_archive_complete_originals_and_reopen(self):
        raw,bins,info=original_series(96)
        report=geometric_predictive_controls(info,"a","b")
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"controls.sqlite"
            with ResearchHoldRegistry(path,source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as store:
                receipt=preserve_geometric_predictive_controls(
                    report,info,raw,bins,store,archive_name="predictive-with-all-raw")
                self.assertEqual(receipt["retained_full_raw_frames"],len(raw))
                self.assertEqual(receipt["retained_predictive_splits"],3)
                self.assertEqual(receipt["cases"],3)
                self.assertEqual(store.counts()["cases"],3)
                original=store.read_archive("predictive-with-all-raw")["records"]
                self.assertEqual(len(original),len(raw)+1)
                self.assertEqual(original[-1]["kind"],"PREDICTIVE_CONTROL_REPORT")
                self.assertEqual(original[0]["raw_frame"]["samples"][0]["direction"],"AB")
                self.assertTrue(store.verify())
                for case in receipt["research_case_ids"]:
                    self.assertEqual(store.get(case)["scientific_jobs_eliminated"],0)
            with ResearchHoldRegistry(path,source_identity="geometry-raw",
                                      contract_identity=bins.identity()) as store:
                self.assertEqual(store.read_archive("predictive-with-all-raw")["records"],
                                 original)
                self.assertTrue(store.verify())


if __name__=="__main__":
    unittest.main()
