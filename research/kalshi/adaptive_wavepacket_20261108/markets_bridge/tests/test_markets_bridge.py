"""Markets bridge tests: estimator declaration and the mandatory leakage gate.

Run from the Markets root:
    PYTHONPATH=.:research/kalshi/adaptive_wavepacket_20261108/working_tree:research/kalshi/adaptive_wavepacket_20261108/working_tree/tests \
      python3 -m unittest discover -s research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tests -p 'test_*.py'

All data is synthetic and bounded; nothing is market data and nothing is a
scientific acceptance.
"""
import math
import unittest

try:
    import numpy  # noqa: F401
    import scipy  # noqa: F401
    HAVE_NUMERIC = True
except ImportError:  # pragma: no cover
    HAVE_NUMERIC = False

from adaptive_locality.information import RawMember, RawFrame, FixedBins, derive_information
from adaptive_locality.coupling import discover_coupling, chronological_partition
from test_adaptive_locality_coupling import synthetic_series
from test_adaptive_locality_geometry_validation import original_series


@unittest.skipUnless(HAVE_NUMERIC, "numpy/scipy required for the Markets estimators")
class EstimatorBridgeTests(unittest.TestCase):
    def test_both_estimators_cover_the_same_admitted_frames_with_distinct_identities(self):
        from research.kalshi.adaptive_wavepacket_20261108.markets_bridge.estimators import (
            estimator_bridge, derive_information_continuous)
        raw, bins, _ = original_series(60)
        bridge = estimator_bridge(raw, bins)
        self.assertTrue(bridge["ready_clocks_agree"])
        self.assertNotEqual(bridge["identities"]["frozen-bin"], bridge["identities"]["vasicek-ksg"])
        self.assertEqual(bridge["identities"]["frozen-bin"], bins.identity())
        d = bridge["frozen-bin"][0]
        c = bridge["vasicek-ksg"][0]
        self.assertEqual(d.raw_identity, c.raw_identity)
        self.assertEqual(d.raw_evidence_ids, c.raw_evidence_ids)
        self.assertEqual(d.fisher_proxy, c.fisher_proxy)          # same frozen-bin proxy
        self.assertNotEqual(d.entropy, c.entropy)                  # discrete vs differential
        self.assertEqual(c.calibration_identity, bridge["identities"]["vasicek-ksg"])
        self.assertEqual(bridge["scientific_jobs_eliminated"], 0)
        # Review-required frames stay review-required under the continuous estimator.
        from dataclasses import replace
        unusual = replace(raw[0].samples[0], value=50.)
        bad = replace(raw[0], samples=(unusual,) + raw[0].samples[1:])
        self.assertEqual(derive_information_continuous(bad, bins).status, "REVIEW_REQUIRED")

    def test_continuous_series_runs_through_the_five_step_probe_without_mixing(self):
        from research.kalshi.adaptive_wavepacket_20261108.markets_bridge.estimators import estimator_bridge
        raw, bins, _ = original_series(90)
        bridge = estimator_bridge(raw, bins)
        report = discover_coupling(bridge["vasicek-ksg"])
        self.assertEqual(report["calibration_identity"], bridge["identities"]["vasicek-ksg"])
        self.assertEqual(report["result_count"], 2)
        from adaptive_locality.core import LocalityError
        with self.assertRaises(LocalityError):
            discover_coupling(bridge["frozen-bin"][:45] + bridge["vasicek-ksg"][45:])

    def test_vasicek_entropy_of_a_gaussian_quantile_sample_is_near_closed_form(self):
        from research.kalshi.adaptive_wavepacket_20261108.markets_bridge.estimators import (
            derive_information_continuous)
        import statistics
        normal = statistics.NormalDist(0., 1.)
        edges = tuple(round(-6. + 0.5 * i, 10) for i in range(25))
        bins = FixedBins("gauss", "wide", (("a", edges), ("b", edges)))
        members = []
        for i in range(2000):
            v = normal.inv_cdf((i + 0.5) / 2000)
            for node in ("a", "b"):
                members.append(RawMember(f"m-{node}-{i}", str(i), node, v, "quantile"))
        info = derive_information_continuous(RawFrame(1, "gauss", tuple(members)), bins)
        self.assertEqual(info.status, "READY")
        expected = 0.5 * math.log(2 * math.pi * math.e)   # 1.4189
        self.assertAlmostEqual(dict(info.entropy)["a"], expected, delta=0.05)


@unittest.skipUnless(HAVE_NUMERIC, "numpy required for odcore.leakage")
class LeakageGateTests(unittest.TestCase):
    def setUp(self):
        self.frames = synthetic_series(n=120)
        self.lag = chronological_partition(len(self.frames))[0]
        self.idxs = list(range(self.lag + 5, len(self.frames) - 2, 7))

    def test_operator_rows_pass_both_gates(self):
        from research.kalshi.adaptive_wavepacket_20261108.markets_bridge.leakage_gate import (
            operator_row_signal, frame_permutation_gate, odcore_gate)
        for lag in (0, self.lag):
            with self.subTest(lag=lag):
                signal = operator_row_signal("a", "b", lag)
                ok, fails = frame_permutation_gate(self.frames, signal, self.idxs)
                self.assertTrue(ok, fails)
                ok, fails = odcore_gate(self.frames, "a", "b", signal, self.idxs)
                self.assertTrue(ok, fails)

    def test_training_coefficients_pass_both_gates(self):
        from research.kalshi.adaptive_wavepacket_20261108.markets_bridge.leakage_gate import (
            training_coefficients_signal, frame_permutation_gate, odcore_gate)
        signal = training_coefficients_signal("a", "b")
        idxs = [i for i in self.idxs if i >= 2 * 9 + self.lag + 6]
        self.assertTrue(idxs)
        ok, fails = frame_permutation_gate(self.frames, signal, idxs)
        self.assertTrue(ok, fails)
        ok, fails = odcore_gate(self.frames, "a", "b", signal, idxs)
        self.assertTrue(ok, fails)

    def test_a_leaking_signal_is_caught_by_both_gates(self):
        from research.kalshi.adaptive_wavepacket_20261108.markets_bridge.leakage_gate import (
            leaking_signal, frame_permutation_gate, odcore_gate)
        signal = leaking_signal("a")
        ok, fails = frame_permutation_gate(self.frames, signal, self.idxs)
        self.assertFalse(ok)
        self.assertTrue(fails)
        ok, fails = odcore_gate(self.frames, "a", "b", signal, self.idxs)
        self.assertFalse(ok)
        self.assertTrue(fails)


if __name__ == "__main__":
    unittest.main()
