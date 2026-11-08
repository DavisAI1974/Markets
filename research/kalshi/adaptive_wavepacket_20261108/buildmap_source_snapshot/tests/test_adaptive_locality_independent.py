"""Standalone differential, fault/recovery, boundary, and identity tests.

All events are synthetic. Nothing is connected or counted as real-market science.
"""
import random
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace

from adaptive_locality.core import Observation, MetricContract, LocalityError
from adaptive_locality.index import ExactGridIndex
from adaptive_locality.contracts import Calibration, FeatureSpec
from adaptive_locality.queue import ReadyGroup
from adaptive_locality.durable_queue import DurableShadowQueue
from adaptive_locality.result_cache import CacheKey, OfflineCache
from adaptive_locality.graph_boundary import Edge, FluxDomain, total_mass, stable_explicit_dt
from adaptive_locality.boundary_validation import checked_step, graph_energy


def obs(i, x, y=0.0, family="P"):
    return Observation(str(i), family, {"x": float(x), "y": float(y)}, i, "synthetic",
                       order_id="order" + str(i), direction="AB")


class IndependentComponentsTests(unittest.TestCase):
    def setUp(self):
        self.metric = MetricContract(("x", "y"), (1, 1), (1, 1), "frozen-v1")

    def test_exact_grid_matches_full_scan_randomized(self):
        randomizer = random.Random(27)
        for radius in (0.01, 0.2, 2.0):
            index = ExactGridIndex(self.metric, radius)
            centers = [obs(i, randomizer.uniform(-10, 10), randomizer.uniform(-10, 10),
                           "P" if i % 3 else "X") for i in range(250)]
            for center in centers:
                self.assertEqual(index.add(center), "ADDED")
                self.assertEqual(index.add(center), "EXISTS")
            for j in range(60):
                target = obs(10000 + j, randomizer.uniform(-10, 10),
                             randomizer.uniform(-10, 10), "P" if j % 2 else "X")
                actual = [(h.center_id, h.distance) for h in index.candidates(target)]
                expected = sorted(
                    [(center.event_id, self.metric.distance(target, center))
                     for center in centers if center.family == target.family
                     and self.metric.distance(target, center) <= radius],
                    key=lambda item: (item[1], item[0]))
                self.assertEqual(actual, expected)

    def test_dimension_fallback_direction_identity_and_restore(self):
        metric = MetricContract(tuple("abcdefgh"), (1,) * 8, (1,) * 8, "v")
        index = ExactGridIndex(metric, 1.0, max_cells=20)
        self.assertFalse(index.indexed)
        a = Observation("a", "P", dict.fromkeys(metric.features, 0.), 1, "source", direction="AB")
        b = Observation("b", "P", dict.fromkeys(metric.features, 0.), 2, "source", direction="BA")
        index.add(a)
        self.assertEqual(index.candidates(b)[0].center_id, "a")
        self.assertEqual(index.candidates(b)[0].evidence_identity, a.identity())
        index.retire("a", "manual reversible review")
        self.assertEqual(index.candidates(b), ())
        with self.assertRaises(LocalityError):
            index.restore(replace(a, direction="BA"))
        index.restore(a)
        self.assertEqual(index.candidates(b)[0].center_id, "a")
        with self.assertRaises(LocalityError):
            index.add(replace(a, direction="BA"))

    def test_historical_calibration_fail_closed(self):
        calibration = Calibration("source", "schema", 10, "version",
                                  (FeatureSpec("x", "ticks", 2, 1),
                                   FeatureSpec("y", "units", 1, 0)))
        self.assertEqual(calibration.metric().identity(), calibration.metric().identity())
        calibration.validate_history([obs(1, 2), obs(2, 4)])
        with self.assertRaises(LocalityError):
            calibration.validate_history([obs(11, 2)])
        with self.assertRaises(LocalityError):
            calibration.validate_history([obs(1, 2), obs(1, 3)])
        with self.assertRaises(LocalityError):
            Calibration("s", "v", 1, "x", (FeatureSpec("order_id", "id", 1, 1),))
        with self.assertRaises(LocalityError):
            calibration.validate_observation(Observation("bad", "P", {"x": 1}, 1, "source"))

    def test_sqlite_queue_recovery_lease_fencing_and_idempotency(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "queue.sqlite"
            group = ReadyGroup("g", "src", "features", ("event-1",), "P", "AB")
            other = ReadyGroup("h", "src", "features", ("event-2",), "P", "BA")
            with DurableShadowQueue(path, source_identity="src",
                                    contract_identity="v1", capacity=1) as q:
                self.assertEqual(q.submit(group), "QUEUED")
                self.assertEqual(q.submit(group), "ALREADY_PENDING")
                self.assertEqual(q.submit(other), "BACKPRESSURE")
                leased, token = q.lease(now=10, duration=5)
                self.assertEqual(leased, group)
            with DurableShadowQueue(path, source_identity="src",
                                    contract_identity="v1", capacity=1) as q:
                leased, new_token = q.lease(now=15, duration=5)
                self.assertEqual(leased, group)
                with self.assertRaises(LocalityError):
                    q.complete("g", token, now=16, verified_identity=group.identity(),
                               result_identity="artifact")
                self.assertEqual(q.complete("g", new_token, now=16,
                                             verified_identity=group.identity(),
                                             result_identity="artifact"), "COMPLETED")
                self.assertEqual(q.submit(group), "ALREADY_COMPLETED")
                self.assertEqual(q.submit(other), "QUEUED")
                with self.assertRaises(LocalityError):
                    q.submit(replace(group, direction="BA"))
                self.assertEqual(q.snapshot()["scientific_jobs_eliminated"], 0)
            with self.assertRaises(LocalityError):
                with DurableShadowQueue(path, source_identity="wrong",
                                        contract_identity="v1", capacity=1):
                    pass

    def test_two_connections_claim_at_most_once_per_lease(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "q.sqlite"
            with DurableShadowQueue(path, source_identity="s", contract_identity="c") as a:
                with DurableShadowQueue(path, source_identity="s", contract_identity="c") as b:
                    g = ReadyGroup("g", "s", "f", ("e",), "P", "AB")
                    a.submit(g)
                    self.assertIsNotNone(a.lease(now=1, duration=5))
                    self.assertIsNone(b.lease(now=2, duration=5))
                    claimed, token = b.lease(now=6, duration=5)
                    self.assertEqual(claimed, g)
                    b.retry("g", token, now=7)
                    self.assertIsNotNone(a.lease(now=8, duration=5))

    def test_cache_full_identity_and_tampering(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = OfflineCache(folder)
            key = CacheKey("source", "input", "metric", "policy", "code", "P", "AB", "raw")
            cache.put(key, {"scientific_jobs_eliminated": 0, "result": [1, 2]})
            self.assertEqual(cache.get(key)["result"], [1, 2])
            with self.assertRaises(LocalityError):
                cache.put(key, {"result": []})
            with self.assertRaises(LocalityError):
                cache.get(replace(key, direction="BA"))
            path = cache._path(key)
            path.write_text('{"incomplete":true}')
            with self.assertRaises(LocalityError):
                cache.get(key)

    def test_diffusion_conserves_mass_and_dissipates_graph_energy(self):
        domain = FluxDomain({"a": 1., "b": 1., "c": 1.},
                            (Edge("a", "b", 1.), Edge("b", "c", 1.)),
                            ("a", "c"))
        field = {"a": 1., "b": 0., "c": 0.}
        limit = stable_explicit_dt(domain)
        with self.assertRaises(LocalityError):
            checked_step(domain, field, limit * 1.01)
        previous_mass = total_mass(domain, field)
        previous_energy = graph_energy(domain, field)
        for _ in range(100):
            field = checked_step(domain, field, limit / 2)
            self.assertAlmostEqual(total_mass(domain, field), previous_mass)
            current_energy = graph_energy(domain, field)
            self.assertLessEqual(current_energy, previous_energy + 1e-12)
            previous_energy = current_energy
        self.assertAlmostEqual(field["a"], field["b"], places=5)
        self.assertAlmostEqual(field["b"], field["c"], places=5)


if __name__ == "__main__":
    unittest.main()
