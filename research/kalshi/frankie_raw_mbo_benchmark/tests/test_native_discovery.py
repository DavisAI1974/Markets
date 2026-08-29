"""Tests for section 4.15 open-world cluster and new-structure discovery."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_discovery import (
    INCREMENTAL,
    RETROSPECTIVE,
    UNASSIGNED,
    DiscoveryCalculator,
    DiscoveryError,
    FeatureSchema,
)


def schema(**overrides) -> FeatureSchema:
    base = dict(
        version="v1",
        feature_names=("depletion", "refill"),
        scaling={"depletion": (0.0, 10.0), "refill": (0.0, 10.0)},
        distance="EUCLIDEAN_ON_SCALED_FEATURES",
        radius=1.0,
        seed=0,
        mode=INCREMENTAL,
    )
    base.update(overrides)
    return FeatureSchema(**base)


class FeatureSchemaTest(unittest.TestCase):
    def test_forbidden_features_are_rejected_at_construction(self) -> None:
        """Before any data is seen, not merely at scoring time."""
        for name in (
            "outcome_size",
            "step1_membership",
            "reveal_flag",
            "score_value",
            "realized_move",
            "future_return",
            "target_label",
            "settle_price",
            "pnl_bps",
        ):
            with self.subTest(feature=name):
                with self.assertRaises(DiscoveryError):
                    schema(feature_names=(name,), scaling={name: (0.0, 1.0)})

    def test_the_error_names_the_offending_fragment(self) -> None:
        with self.assertRaises(DiscoveryError) as ctx:
            schema(feature_names=("later_response",), scaling={"later_response": (0.0, 1.0)})
        self.assertIn("response", str(ctx.exception))

    def test_ordinary_microstructure_features_are_allowed(self) -> None:
        s = schema(
            feature_names=("volume_ahead", "queue_movement", "spread_raw"),
            scaling={"volume_ahead": (0.0, 1.0), "queue_movement": (0.0, 1.0), "spread_raw": (0.0, 1.0)},
        )
        self.assertEqual(len(s.feature_names), 3)

    def test_schema_hash_is_stable_and_sensitive(self) -> None:
        self.assertEqual(schema().schema_hash, schema().schema_hash)
        self.assertNotEqual(schema().schema_hash, schema(radius=2.0).schema_hash)
        self.assertNotEqual(schema().schema_hash, schema(seed=1).schema_hash)
        self.assertNotEqual(schema().schema_hash, schema(mode=RETROSPECTIVE).schema_hash)

    def test_mode_is_explicit_and_validated(self) -> None:
        self.assertEqual(schema(mode=RETROSPECTIVE).mode, RETROSPECTIVE)
        with self.assertRaises(DiscoveryError):
            schema(mode="WHATEVER")

    def test_missing_scaling_or_duplicate_or_empty_features_are_refused(self) -> None:
        with self.assertRaises(DiscoveryError):
            schema(feature_names=("a",), scaling={})
        with self.assertRaises(DiscoveryError):
            schema(feature_names=("a", "a"), scaling={"a": (0.0, 1.0)})
        with self.assertRaises(DiscoveryError):
            schema(feature_names=(), scaling={})

    def test_nonpositive_scale_or_radius_is_refused(self) -> None:
        with self.assertRaises(DiscoveryError):
            schema(scaling={"depletion": (0.0, 0.0), "refill": (0.0, 1.0)})
        with self.assertRaises(DiscoveryError):
            schema(radius=0)

    def test_undeclared_or_missing_member_features_are_refused(self) -> None:
        s = schema()
        with self.assertRaises(DiscoveryError):
            s.vector({"depletion": 1.0})
        with self.assertRaises(DiscoveryError):
            s.vector({"depletion": 1.0, "refill": 1.0, "sneaky_outcome": 1.0})


class DiscoveryCalculatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = DiscoveryCalculator(schema())

    def assign(self, member_id: str, depletion: float, refill: float, recv_ns: int = 1_000):
        return self.calc.assign(
            member_id=member_id, features={"depletion": depletion, "refill": refill}, recv_ns=recv_ns
        )

    def test_near_members_join_and_far_members_found_new_clusters(self) -> None:
        first = self.assign("m1", 0.0, 0.0)
        near = self.assign("m2", 1.0, 0.0)
        far = self.assign("m3", 100.0, 0.0)
        self.assertTrue(first["founded_new_cluster"])
        self.assertFalse(near["founded_new_cluster"])
        self.assertTrue(far["founded_new_cluster"])
        self.assertEqual(self.calc.cluster_count, 2)

    def test_every_assignment_carries_distance_and_support(self) -> None:
        self.assign("m1", 0.0, 0.0)
        record = self.assign("m2", 5.0, 0.0)
        self.assertIn("distance", record)
        self.assertAlmostEqual(record["distance"], 0.5)
        self.assertEqual(record["support_at_assignment"], 2)
        self.assertEqual(record["schema_hash"], self.calc.schema.schema_hash)

    def test_singletons_are_an_outcome_not_an_exception(self) -> None:
        self.assign("m1", 0.0, 0.0)
        self.assign("m2", 100.0, 0.0)
        self.assertEqual(self.calc.singleton_count, 2)

    def test_the_cluster_count_is_not_chosen_in_advance(self) -> None:
        for index in range(8):
            self.assign(f"m{index}", index * 50.0, 0.0)
        self.assertEqual(self.calc.cluster_count, 8)

    def test_unassigned_members_are_preserved(self) -> None:
        record = self.calc.record_unassigned(member_id="m9", reason="feature unavailable", recv_ns=1)
        self.assertEqual(record["cluster_id"], UNASSIGNED)
        self.assertEqual(len(self.calc.unassigned), 1)
        self.assertEqual(self.calc.summary()["unassigned_count"], 1)

    def test_splits_and_merges_are_recorded(self) -> None:
        self.assign("m1", 0.0, 0.0)
        self.assign("m2", 100.0, 0.0)
        self.calc.note_split(parent_cluster_id="C000000")
        self.calc.merge(source_cluster_id="C000001", target_cluster_id="C000000")
        self.assertEqual(self.calc.summary()["splits"], 1)
        self.assertEqual(self.calc.summary()["merges"], 1)
        self.assertEqual(self.calc.cluster_count, 1)

    def test_invalid_split_or_merge_is_refused(self) -> None:
        self.assign("m1", 0.0, 0.0)
        with self.assertRaises(DiscoveryError):
            self.calc.note_split(parent_cluster_id="ghost")
        with self.assertRaises(DiscoveryError):
            self.calc.merge(source_cluster_id="C000000", target_cluster_id="C000000")

    def test_a_cluster_cannot_be_described_before_discovery_is_frozen(self) -> None:
        """Section 4.15 inverts the usual rule: an average is illegal until frozen."""
        self.assign("m1", 0.0, 0.0)
        with self.assertRaises(DiscoveryError):
            self.calc.cluster_summary()

    def test_freezing_permits_description_and_blocks_further_assignment(self) -> None:
        self.assign("m1", 0.0, 0.0)
        receipt = self.calc.freeze()
        self.assertTrue(receipt["frozen"])
        self.assertIn("membership_hash", receipt)
        rows = self.calc.cluster_summary()
        self.assertEqual(len(rows), 1)
        with self.assertRaises(DiscoveryError):
            self.assign("m2", 0.0, 0.0)
        with self.assertRaises(DiscoveryError):
            self.calc.record_unassigned(member_id="m3", reason="late", recv_ns=1)

    def test_cluster_summary_keeps_exemplar_and_boundary_members_beside_the_centroid(self) -> None:
        self.assign("m1", 0.0, 0.0)
        self.assign("m2", 1.0, 0.0)
        self.assign("m3", 9.0, 0.0)
        self.calc.freeze()
        row = self.calc.cluster_summary()[0]
        self.assertIsNotNone(row["nearest_exemplar"])
        self.assertIsNotNone(row["boundary_member"])
        self.assertNotEqual(row["nearest_exemplar"], row["boundary_member"])
        self.assertEqual(len(row["member_ids"]), 3)

    def test_prevalence_is_labelled_a_rate_not_a_mean(self) -> None:
        self.assign("m1", 0.0, 0.0)
        self.assign("m2", 100.0, 0.0)
        self.calc.freeze()
        for row in self.calc.cluster_summary():
            self.assertAlmostEqual(row["prevalence"], 0.5)
            self.assertTrue(row["prevalence_is_a_rate_not_a_mean"])

    def test_membership_hash_changes_with_membership(self) -> None:
        self.assign("m1", 0.0, 0.0)
        first = self.calc.freeze()["membership_hash"]
        other = DiscoveryCalculator(schema())
        other.assign(member_id="m1", features={"depletion": 0.0, "refill": 0.0}, recv_ns=1)
        other.assign(member_id="m2", features={"depletion": 0.0, "refill": 0.0}, recv_ns=1)
        self.assertNotEqual(first, other.freeze()["membership_hash"])

    def test_summary_declares_the_mode_and_the_guards(self) -> None:
        summary = self.calc.summary()
        self.assertEqual(summary["section"], "4.15")
        self.assertEqual(summary["mode"], INCREMENTAL)
        self.assertIn("before any", summary["leak_guard"])
        self.assertIn("frozen", summary["average_rule"])

    def test_retrospective_mode_travels_with_the_output(self) -> None:
        calc = DiscoveryCalculator(schema(mode=RETROSPECTIVE))
        record = calc.assign(member_id="m1", features={"depletion": 0.0, "refill": 0.0}, recv_ns=1)
        self.assertEqual(record["mode"], RETROSPECTIVE)
        calc.freeze()
        self.assertEqual(calc.cluster_summary()[0]["mode"], RETROSPECTIVE)


if __name__ == "__main__":
    unittest.main()
