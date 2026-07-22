import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_product_lag import (  # noqa: E402
    MEASURED,
    NO_WINDOW,
    ProductLagError,
    build_registry,
    lookup_lag,
    make_observation,
    validate_lookup,
    validate_observation,
    validate_registry,
)


def lag_key(**overrides):
    key = {
        "venue": "kalshi",
        "product": "NG event contract",
        "series": "KXNG",
        "contract": "KXNG-26MAR18",
        "strike": "3.25",
        "liquidity_bucket": "medium",
        "move_size_bucket": "small",
        "time_of_day_bucket": "us_morning",
        "regime": "shoulder_contango",
    }
    key.update(overrides)
    return key


def quality(**overrides):
    result = {
        "leader_event_valid": True,
        "follower_event_valid": True,
        "exact_definition_match": True,
        "sequence_complete": True,
        "executable_book_observed": True,
    }
    result.update(overrides)
    return result


def observation(index, *, key=None, q=None, first_ms=None, completion=True):
    leader = float(index * 10)
    first = float(first_ms if first_ms is not None else 100 + index * 10)
    return make_observation(
        observation_id=f"obs-{index}",
        key=key or lag_key(),
        leader_event_s=leader,
        follower_first_reprice_s=leader + first / 1000.0,
        follower_completion_s=None if not completion else leader + (first + 300) / 1000.0,
        quality=q or quality(),
        source_fingerprints=[f"source-{index}"],
    )


class ProductLagTests(unittest.TestCase):
    def test_exact_key_returns_measured_window(self):
        registry = build_registry([observation(i) for i in range(1, 7)], min_samples=5)
        result = lookup_lag(registry, key=lag_key(), as_of_s=100.0)
        self.assertEqual(result["status"], MEASURED)
        self.assertEqual(result["eligible_pre_cutoff_observations"], 6)
        self.assertIsNotNone(result["first_reprice_window"])
        self.assertFalse(result["fallback_used"])

    def test_missing_exact_key_returns_no_window(self):
        registry = build_registry([observation(i) for i in range(1, 7)], min_samples=5)
        result = lookup_lag(registry, key=lag_key(strike="3.50"), as_of_s=100.0)
        self.assertEqual(result["status"], NO_WINDOW)
        self.assertIn("NO_EXACT_KEY_HISTORY", result["reasons"])

    def test_single_dimension_mismatch_never_falls_back(self):
        registry = build_registry([observation(i) for i in range(1, 7)], min_samples=5)
        result = lookup_lag(registry, key=lag_key(liquidity_bucket="thin"), as_of_s=100.0)
        self.assertEqual(result["status"], NO_WINDOW)
        self.assertFalse(result["fallback_used"])

    def test_historical_lookup_excludes_future_observations(self):
        registry = build_registry([observation(i) for i in range(1, 7)], min_samples=3)
        result = lookup_lag(registry, key=lag_key(), as_of_s=35.0)
        self.assertEqual(result["eligible_pre_cutoff_observations"], 3)
        self.assertEqual(result["status"], MEASURED)
        self.assertEqual(len(result["observation_fingerprints"]), 3)

    def test_insufficient_pre_cutoff_samples_returns_no_window(self):
        registry = build_registry([observation(i) for i in range(1, 7)], min_samples=5)
        result = lookup_lag(registry, key=lag_key(), as_of_s=35.0)
        self.assertEqual(result["status"], NO_WINDOW)
        self.assertIn("INSUFFICIENT_PRE_CUTOFF_SAMPLES", result["reasons"])
        self.assertIsNone(result["first_reprice_window"])

    def test_bad_quality_is_recorded_but_not_usable(self):
        rows = [observation(i) for i in range(1, 5)]
        rows.append(observation(5, q=quality(sequence_complete=False)))
        registry = build_registry(rows, min_samples=5)
        group = registry["groups"][0]
        self.assertEqual(group["total_observations"], 5)
        self.assertEqual(group["usable_observations"], 4)
        self.assertEqual(group["status"], NO_WINDOW)

    def test_follower_cannot_precede_leader(self):
        with self.assertRaises(ProductLagError):
            make_observation(
                observation_id="bad",
                key=lag_key(),
                leader_event_s=10.0,
                follower_first_reprice_s=9.0,
                quality=quality(),
            )

    def test_duplicate_observation_id_is_rejected(self):
        row = observation(1)
        with self.assertRaises(ProductLagError):
            build_registry([row, copy.deepcopy(row)], min_samples=1)

    def test_observation_tampering_is_rejected(self):
        row = observation(1)
        row["first_reprice_lag_ms"] = 999.0
        with self.assertRaises(ProductLagError):
            validate_observation(row)

    def test_registry_tampering_is_rejected(self):
        registry = build_registry([observation(i) for i in range(1, 7)], min_samples=5)
        registry["groups"][0]["status"] = NO_WINDOW
        with self.assertRaises(ProductLagError):
            validate_registry(registry)

    def test_lookup_tampering_is_rejected(self):
        registry = build_registry([observation(i) for i in range(1, 7)], min_samples=5)
        result = lookup_lag(registry, key=lag_key(), as_of_s=100.0)
        result["fallback_used"] = True
        with self.assertRaises(ProductLagError):
            validate_lookup(result)

    def test_missing_completion_keeps_first_reprice_window(self):
        rows = [observation(i, completion=False) for i in range(1, 6)]
        registry = build_registry(rows, min_samples=5)
        result = lookup_lag(registry, key=lag_key(), as_of_s=100.0)
        self.assertEqual(result["status"], MEASURED)
        self.assertIsNotNone(result["first_reprice_window"])
        self.assertIsNone(result["completion_window"])

    def test_sources_are_immutable(self):
        rows = [observation(i) for i in range(1, 7)]
        original = copy.deepcopy(rows)
        registry = build_registry(rows, min_samples=5)
        lookup_lag(registry, key=lag_key(), as_of_s=100.0)
        self.assertEqual(rows, original)

    def test_deterministic_fingerprints(self):
        rows = [observation(i) for i in range(1, 7)]
        first = build_registry(rows, min_samples=5)
        second = build_registry(reversed(rows), min_samples=5)
        self.assertEqual(first["fingerprint"], second["fingerprint"])
        one = lookup_lag(first, key=lag_key(), as_of_s=100.0)
        two = lookup_lag(second, key=lag_key(), as_of_s=100.0)
        self.assertEqual(one["fingerprint"], two["fingerprint"])

    def test_all_artifacts_remain_research_only(self):
        rows = [observation(i) for i in range(1, 7)]
        registry = build_registry(rows, min_samples=5)
        result = lookup_lag(registry, key=lag_key(), as_of_s=100.0)
        self.assertFalse(registry["execution_authority"])
        self.assertFalse(registry["may_update_ng_brain"])
        self.assertTrue(registry["no_universal_lag"])
        self.assertFalse(result["execution_authority"])
        self.assertFalse(result["may_update_ng_brain"])


if __name__ == "__main__":
    unittest.main()
