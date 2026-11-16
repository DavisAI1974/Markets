"""Geometric operator identities are diagnostics, not proof of coupling."""
import unittest
from dataclasses import replace
from adaptive_locality.core import LocalityError
from adaptive_locality.geometry_probe import geometric_dipole_probe
from test_adaptive_locality_coupling import frame


def series(n=100, *, equal=False):
    data=[]
    for t in range(n):
        ha=0.8+0.01*t
        hb=ha if equal else 1.0
        data.append(frame(t,ha,hb,0.3,0.4,0.1))
    return tuple(data)


class OperatorGeometryTests(unittest.TestCase):
    def test_quadratic_curve_detected_without_flattenting(self):
        data=series()
        result=geometric_dipole_probe(data,"a","b",tolerance=1e-8)
        # Hb=1 throughout; Ha²=(Ha*Hb)² is an algebraic tautology.
        self.assertEqual(result["status"],"RESEARCH_HOLD")
        self.assertIn("CONSTANT_TRAIN_DONOR_HB",result["algebraic_degeneracy_flags"])
        self.assertIn("ALGEBRAIC_REPARAMETERIZATION",result["reason"])
        self.assertEqual(result["original_frame_count"],len(data))
        self.assertEqual(result["preserved_frame_identities"],
                         tuple(f.raw_identity for f in data))
        self.assertEqual(result["frames_dropped"],0)
        self.assertEqual(result["scientific_jobs_eliminated"],0)
        self.assertFalse(result["averaged_or_flattened_original_data"])
        self.assertFalse(result["physical_boundary_condition_supported"])
        self.assertTrue(result["identity_is_algebra_not_coupling"])
        self.assertLess(result["quadratic_holdout_sse"],1e-14)
        self.assertEqual(result["research_review_count"],0)
        self.assertEqual(tuple(p.clock for p in result["points"]),tuple(range(len(data))))

    def test_equal_entropy_identity_is_not_a_coupling_law(self):
        data=series(equal=True)
        result=geometric_dipole_probe(data,"a","b")
        self.assertEqual(result["status"],"RESEARCH_HOLD")
        self.assertIn("LINEAR_BASELINE",result["reason"])
        self.assertTrue(all(p.squared_entropy_difference == 0 for p in result["points"]))
        self.assertEqual(result["frames_dropped"],0)
        self.assertTrue(result["identity_is_algebra_not_coupling"])

    def test_rank_deficiency_remains_available_for_investigation(self):
        data=tuple(frame(t,0.7,0.9,0.1,0.2,0.3) for t in range(70))
        result=geometric_dipole_probe(data,"a","b")
        self.assertEqual(result["status"],"RESEARCH_HOLD")
        self.assertIn("RANK_OR_NUMERICAL",result["reason"])
        self.assertEqual(len(result["points"]),len(data))
        self.assertEqual(result["preserved_frame_identities"],
                         tuple(f.raw_identity for f in data))
        self.assertEqual(result["frames_dropped"],0)
        self.assertIsNone(result["quadratic_coefficients"])

    def test_transient_outlier_kept_and_tagged(self):
        data=list(series())
        changed=data[-4]
        data[-4]=replace(changed,entropy=(("a",6.4),("b",1.0)))
        result=geometric_dipole_probe(tuple(data),"a","b",tolerance=0.01)
        target=result["points"][-4]
        self.assertEqual(target.raw_identity,changed.raw_identity)
        self.assertEqual(target.ha,6.4)
        self.assertEqual(target.hb,1.0)
        self.assertEqual(target.status,"RESEARCH_REVIEW_OUTLIER")
        self.assertGreater(result["research_review_count"],0)
        self.assertEqual(result["frames_dropped"],0)
        self.assertEqual(result["scientific_jobs_eliminated"],0)

    def test_missing_or_stale_series_fails_closed(self):
        data=series()
        with self.assertRaises(LocalityError):
            geometric_dipole_probe(data,"a","a")
        with self.assertRaises(LocalityError):
            geometric_dipole_probe(tuple(reversed(data)),"a","b")
        with self.assertRaises(LocalityError):
            geometric_dipole_probe(data[:5],"a","b")


if __name__=="__main__":
    unittest.main()
