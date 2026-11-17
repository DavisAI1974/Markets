"""Standalone differential, fault/recovery, boundary, and identity tests.

All events are synthetic. Nothing is connected or counted as real-market science.
"""
import random
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace

from adaptive_locality.core import Observation, MetricContract, LocalityError, LocalityConfig, LocalityEngine
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
        # E-8: direction is an exact filter by default, exactly as on DiskGridIndex.
        self.assertEqual(index.candidates(b), ())
        self.assertEqual(index.candidates(b, same_direction=False)[0].center_id, "a")
        self.assertEqual(index.candidates(b, same_direction=False)[0].evidence_identity, a.identity())
        index.retire("a", "manual reversible review")
        self.assertEqual(index.candidates(b, same_direction=False), ())
        with self.assertRaises(LocalityError):
            index.restore(replace(a, direction="BA"))
        index.restore(a)
        self.assertEqual(index.candidates(b, same_direction=False)[0].center_id, "a")
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
                    b.retry("g", token, now=7, reason="synthetic worker released the lease")
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




def boundary_pair():
    """E-1: distance is exactly the radius, yet the centre sits one grid cell beyond the (-1,0,1) fan."""
    metric = MetricContract(("x",), (1,), (1,), "boundary-v1")
    center = Observation("c", "P", {"x": 1 - 2 ** -53}, 1, "synthetic", direction="AB")
    query = Observation("q", "P", {"x": 2.0}, 2, "synthetic", direction="AB")
    return metric, center, query


class IndexReviewFixTests(unittest.TestCase):
    """Index findings E-1, E-6, E-8 on the in-memory ExactGridIndex."""

    def setUp(self):
        self.metric = MetricContract(("x", "y"), (1, 1), (1, 1), "frozen-v1")

    def test_e1_exact_radius_boundary_hit_matches_engine(self):
        metric, center, query = boundary_pair()
        self.assertEqual(metric.distance(query, center), 1.0)
        engine = LocalityEngine(metric, LocalityConfig(1.0, 0.5))
        engine.admit(center, engine.propose(center))
        self.assertEqual(engine.propose(query).status, "PROPOSE_ONLY")
        index = ExactGridIndex(metric, 1.0)
        index.add(center)
        hits = index.candidates(query)
        self.assertEqual([(h.center_id, h.distance) for h in hits], [("c", 1.0)])
        # mirrored pair: query near the upper boundary, centre two cells up
        mirrored_center = Observation("c2", "P", {"x": 2.0}, 1, "synthetic", direction="AB")
        mirrored_query = Observation("q2", "P", {"x": 1 - 2 ** -53}, 2, "synthetic", direction="AB")
        index2 = ExactGridIndex(metric, 1.0)
        index2.add(mirrored_center)
        self.assertEqual([h.center_id for h in index2.candidates(mirrored_query)], ["c2"])

    def test_e1_randomized_differential_includes_boundary_pairs(self):
        randomizer = random.Random(99)
        for radius in (0.5, 1.0, 3.0):
            index = ExactGridIndex(self.metric, radius)
            centers = [obs(i, randomizer.uniform(-5, 5), randomizer.uniform(-5, 5)) for i in range(120)]
            # exact-boundary centres: sit at integer grid multiples minus one ulp
            centers.append(Observation("edge-lo", "P", {"x": radius * (1 - 2 ** -53), "y": 0.0}, 1, "synthetic", direction="AB"))
            centers.append(Observation("edge-hi", "P", {"x": 2 * radius, "y": 0.0}, 1, "synthetic", direction="AB"))
            for center in centers:
                index.add(center)
            targets = [obs(10000 + j, randomizer.uniform(-5, 5), randomizer.uniform(-5, 5)) for j in range(40)]
            targets.append(Observation("tq-lo", "P", {"x": 2 * radius, "y": 0.0}, 10050, "synthetic", direction="AB"))
            targets.append(Observation("tq-hi", "P", {"x": radius * (1 - 2 ** -53), "y": 0.0}, 10051, "synthetic", direction="AB"))
            for target in targets:
                actual = [(h.center_id, h.distance) for h in index.candidates(target)]
                expected = sorted(
                    [(c.event_id, self.metric.distance(target, c)) for c in centers
                     if c.family == target.family and c.direction == target.direction
                     and c.event_clock <= target.event_clock
                     and self.metric.distance(target, c) <= radius],
                    key=lambda item: (item[1], item[0]))
                self.assertEqual(actual, expected)

    def test_e6_candidate_report_discloses_truncation(self):
        index = ExactGridIndex(self.metric, 1.0)
        for i in range(5):
            index.add(obs(i, 0.1 * i))
        query = obs(100, 0.0)
        report = index.candidate_report(query, max_neighbors=2)
        self.assertEqual(len(report["hits"]), 2)
        self.assertEqual(report["total_in_radius"], 5)
        self.assertTrue(report["truncated"])
        self.assertEqual(report["revision"], index.revision)
        full = index.candidate_report(query)
        self.assertEqual(len(full["hits"]), 5)
        self.assertFalse(full["truncated"])
        self.assertEqual(index.candidates(query, max_neighbors=2), report["hits"])

    def test_e8_direction_and_historical_filters_match_disk_semantics(self):
        index = ExactGridIndex(self.metric, 1.0)
        same = obs(1, 0.0)
        other = Observation("2", "P", {"x": 0.0, "y": 0.0}, 2, "synthetic", direction="BA")
        future = Observation("3", "P", {"x": 0.0, "y": 0.0}, 50, "synthetic", direction="AB")
        cross = obs(4, 0.0, family="X")
        for center in (same, other, future, cross):
            index.add(center)
        query = obs(10, 0.0)
        self.assertEqual([h.center_id for h in index.candidates(query)], ["1"])
        self.assertEqual([h.center_id for h in index.candidates(query, same_direction=False)], ["1", "2"])
        self.assertEqual([h.center_id for h in index.candidates(query, historical_only=False)], ["1", "3"])
        self.assertEqual([h.center_id for h in index.candidates(query, allow_cross_family=True)], ["1", "4"])
        self.assertEqual([h.center_id for h in index.candidates(
            query, same_direction=False, historical_only=False, allow_cross_family=True)], ["1", "2", "3", "4"])

    def test_e8_streaming_fallback_honours_same_filters(self):
        metric = MetricContract(tuple("abcdef"), (1,) * 6, (1,) * 6, "v")
        index = ExactGridIndex(metric, 1.0, max_cells=20)
        self.assertFalse(index.indexed)
        base = dict.fromkeys(metric.features, 0.)
        index.add(Observation("a", "P", base, 1, "s", direction="AB"))
        index.add(Observation("b", "P", base, 2, "s", direction="BA"))
        index.add(Observation("c", "X", base, 3, "s", direction="AB"))
        query = Observation("q", "P", base, 9, "s", direction="AB")
        self.assertEqual([h.center_id for h in index.candidates(query)], ["a"])
        self.assertEqual([h.center_id for h in index.candidates(query, allow_cross_family=True)], ["a", "c"])
        report = index.candidate_report(query, same_direction=False, allow_cross_family=True, max_neighbors=1)
        self.assertEqual(report["total_in_radius"], 3)
        self.assertTrue(report["truncated"])


class QueueAndCacheReviewFixTests(unittest.TestCase):
    """Findings E-5 and E-15 plus the missing queue/cache tests from the review."""

    def test_e5_retry_requires_reason_and_history_records_each_action(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "q.sqlite"
            g = ReadyGroup("g", "s", "f", ("e",), "P", "AB")
            with DurableShadowQueue(path, source_identity="s", contract_identity="c") as q:
                self.assertEqual(q.submit(g), "QUEUED")
                _, first_token = q.lease(now=1, duration=5)
                with self.assertRaises(TypeError):  # reason is a required keyword
                    q.retry("g", first_token, now=2)
                with self.assertRaises(LocalityError):  # and must be non-empty
                    q.retry("g", first_token, now=2, reason="")
                q.retry("g", first_token, now=2, reason="worker released lease for review")
                _, token = q.lease(now=3, duration=1)
                self.assertIsNone(q.lease(now=3.5, duration=1))
                _, token = q.lease(now=10, duration=5)  # sweep expires the old lease first
                self.assertEqual(q.complete("g", token, now=11, verified_identity=g.identity(),
                                            result_identity="artifact"), "COMPLETED")
                actions = [row["action"] for row in q.history("g")]
                self.assertEqual(actions, ["SUBMIT", "LEASE", "RETRY", "LEASE", "EXPIRE", "LEASE", "COMPLETE"])
                retry_row = q.history("g")[2]
                self.assertEqual(retry_row["reason"], "worker released lease for review")
                self.assertEqual(retry_row["now"], 2)
                self.assertEqual(retry_row["token_prefix"], first_token[:8])
                self.assertEqual(len(retry_row["token_prefix"]), 8)
                snap = q.snapshot()
                self.assertEqual(snap["groups"][0]["attempts"], 3)
                self.assertIsNone(snap["groups"][0]["lease_until"])
                self.assertEqual(snap["max_attempts"], 8)

    def test_e5_exhausted_after_max_attempts_is_retained_with_reason(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "q.sqlite"
            g = ReadyGroup("g", "s", "f", ("e",), "P", "AB")
            with DurableShadowQueue(path, source_identity="s", contract_identity="c", max_attempts=2) as q:
                q.submit(g)
                _, token = q.lease(now=1, duration=5)
                q.retry("g", token, now=2, reason="first failure")
                _, token = q.lease(now=3, duration=5)
                q.retry("g", token, now=4, reason="second failure")
                self.assertIsNone(q.lease(now=5, duration=5))
                row = q.snapshot()["groups"][0]
                self.assertEqual(row["state"], "exhausted")
                self.assertEqual(row["attempts"], 2)
                self.assertEqual(row["last_reason"], "second failure")
                self.assertEqual(q.history("g")[-1]["action"], "EXHAUST")
                self.assertEqual(q.submit(g), "EXHAUSTED")
                # an exhausted row no longer blocks capacity but is still retained
                self.assertEqual(q.submit(ReadyGroup("h", "s", "f", ("e2",), "P", "AB")), "QUEUED")
                self.assertEqual(q.snapshot()["scientific_jobs_eliminated"], 0)

    def test_e5_expiry_sweep_can_exhaust(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "q.sqlite"
            g = ReadyGroup("g", "s", "f", ("e",), "P", "AB")
            with DurableShadowQueue(path, source_identity="s", contract_identity="c", max_attempts=1) as q:
                q.submit(g)
                q.lease(now=1, duration=1)
                self.assertIsNone(q.lease(now=5, duration=1))
                row = q.snapshot()["groups"][0]
                self.assertEqual(row["state"], "exhausted")
                self.assertIn("expired", row["last_reason"])
                self.assertEqual([r["action"] for r in q.history("g")], ["SUBMIT", "LEASE", "EXPIRE", "EXHAUST"])

    def test_missing_queue_paths_complete_pending_stale_retry_conflicting_result(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "q.sqlite"
            g = ReadyGroup("g", "s", "f", ("e",), "P", "AB")
            with DurableShadowQueue(path, source_identity="s", contract_identity="c") as q:
                q.submit(g)
                with self.assertRaises(LocalityError):  # complete() on a pending row
                    q.complete("g", "nolease", now=1, verified_identity=g.identity(), result_identity="r")
                _, token = q.lease(now=1, duration=5)
                with self.assertRaises(LocalityError):  # stale token
                    q.retry("g", "stale-token", now=2, reason="stale")
                with self.assertRaises(LocalityError):  # expired token
                    q.retry("g", token, now=7, reason="late")
                _, token = q.lease(now=8, duration=5)
                self.assertEqual(q.complete("g", token, now=9, verified_identity=g.identity(),
                                            result_identity="r1"), "COMPLETED")
                self.assertEqual(q.complete("g", token, now=9, verified_identity=g.identity(),
                                            result_identity="r1"), "ALREADY_COMPLETED")
                with self.assertRaises(LocalityError):  # conflicting result identity
                    q.complete("g", token, now=9, verified_identity=g.identity(), result_identity="r2")

    def test_e15_cache_requires_counter_and_identical_reput_is_idempotent(self):
        with tempfile.TemporaryDirectory() as folder:
            cache = OfflineCache(folder)
            key = CacheKey("source", "input", "metric", "policy", "code", "P", "AB", "raw")
            with self.assertRaises(LocalityError):
                cache.put(key, {"result": [1]})  # counter missing
            with self.assertRaises(LocalityError):
                cache.put(key, {"scientific_jobs_eliminated": 1, "result": [1]})
            payload = {"scientific_jobs_eliminated": 0, "result": [1, 2]}
            first = cache.put(key, payload)
            self.assertEqual(len(first), 64)
            self.assertEqual(cache.put(key, dict(payload)), "ALREADY_PRESENT")
            with self.assertRaises(LocalityError):
                cache.put(key, {"scientific_jobs_eliminated": 0, "result": [3]})
            self.assertEqual(cache.get(key)["result"], [1, 2])

    def test_cache_key_missing_field_rejected(self):
        with self.assertRaises(LocalityError):
            CacheKey("", "input", "metric", "policy", "code", "P", "AB", "raw")
        with self.assertRaises(LocalityError):
            CacheKey("source", "input", "metric", "policy", "code", "P", None, "raw")


if __name__ == "__main__":
    unittest.main()
