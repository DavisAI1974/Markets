import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

import ng_g15_replay_manifest_bridge as bridge  # noqa: E402
from ng_g15_corpus_basis_gate import evaluate_manifest  # noqa: E402


def resign_catalog(catalog):
    catalog.pop("fingerprint", None)
    catalog["fingerprint"] = bridge._sha(catalog)
    return catalog


class ReplayManifestBridgeTests(unittest.TestCase):
    def setUp(self):
        self.inventory = bridge._fixture_inventory()
        self.catalog = bridge._fixture_catalog(self.inventory)

    def test_unknown_template_never_invents_presence(self):
        template = bridge.build_catalog_template(self.inventory)
        self.assertEqual(template["status"], "UNKNOWN")
        self.assertEqual(len(template["sources"]), 24)
        self.assertTrue(all(row["status"] == "UNKNOWN" for row in template["sources"]))
        self.assertTrue(all(row["location"] is None for row in template["sources"]))
        self.assertFalse(template["execution_authority"])

    def test_wrong_basis_inventory_is_rejected(self):
        bad = bridge._fixture_inventory(wrong_pre_roll=True)
        catalog = bridge._fixture_catalog(bad)
        with self.assertRaises(bridge.ReplayManifestBridgeError):
            bridge.build_replay_manifest(bad, catalog)

    def test_ready_catalog_builds_canonical_ready_manifest(self):
        result = bridge.build_replay_manifest(self.inventory, self.catalog)
        self.assertEqual(result["status"], "READY")
        self.assertEqual(result["manifest_report"]["status"], "READY")
        self.assertEqual(len(result["manifest"]["entries"]), 24)
        self.assertTrue(result["manifest"]["remote_inventory_verified"])

    def test_anchor_is_excluded_from_replay_entries(self):
        result = bridge.build_replay_manifest(self.inventory, self.catalog)
        self.assertEqual(result["anchor_date_excluded_from_replay"], "20260313")
        self.assertNotIn("20260313", {row["day"] for row in result["manifest"]["entries"]})

    def test_source_catalog_missing_lane_is_rejected(self):
        bad = copy.deepcopy(self.catalog)
        bad["sources"].pop()
        resign_catalog(bad)
        with self.assertRaises(bridge.ReplayManifestBridgeError):
            bridge.build_replay_manifest(self.inventory, bad)

    def test_duplicate_lane_is_rejected(self):
        bad = copy.deepcopy(self.catalog)
        bad["sources"].append(copy.deepcopy(bad["sources"][0]))
        resign_catalog(bad)
        with self.assertRaises(bridge.ReplayManifestBridgeError):
            bridge.build_replay_manifest(self.inventory, bad)

    def test_wrong_instrument_is_rejected(self):
        bad = copy.deepcopy(self.catalog)
        bad["sources"][0]["instrument_id"] = 996
        resign_catalog(bad)
        with self.assertRaises(bridge.ReplayManifestBridgeError):
            bridge.build_replay_manifest(self.inventory, bad)

    def test_basis_row_fingerprint_mismatch_is_rejected(self):
        bad = copy.deepcopy(self.catalog)
        bad["sources"][0]["basis_row_fingerprint"] = "0" * 64
        resign_catalog(bad)
        with self.assertRaises(bridge.ReplayManifestBridgeError):
            bridge.build_replay_manifest(self.inventory, bad)

    def test_definition_period_mismatch_is_rejected(self):
        bad = copy.deepcopy(self.catalog)
        bad["sources"][0]["definition_end_s"] -= 1
        resign_catalog(bad)
        with self.assertRaises(bridge.ReplayManifestBridgeError):
            bridge.build_replay_manifest(self.inventory, bad)

    def test_nonoverlapping_sources_are_rejected(self):
        bad = copy.deepcopy(self.catalog)
        day = bad["sources"][0]["day"]
        rows = [row for row in bad["sources"] if row["day"] == day]
        rows[0]["event_end_s"] = rows[0]["event_start_s"] + 1
        rows[1]["event_start_s"] = rows[0]["event_end_s"] + 1

        inventory = copy.deepcopy(self.inventory)
        target = next(row for row in inventory if str(row["date"]) == day)
        target.pop("l1_first_event_s", None)
        target.pop("l1_last_event_s", None)
        target.pop("mbo_first_event_s", None)
        target.pop("mbo_last_event_s", None)
        report = evaluate_manifest(copy.deepcopy(inventory))
        bad["basis_inventory_fingerprint"] = bridge._sha(inventory)
        bad["basis_report_fingerprint"] = report["fingerprint"]
        basis_by_day = {str(row["date"]): row for row in inventory}
        for source in bad["sources"]:
            source["basis_row_fingerprint"] = bridge._sha(basis_by_day[source["day"]])
        resign_catalog(bad)
        with self.assertRaises(bridge.ReplayManifestBridgeError):
            bridge.build_replay_manifest(inventory, bad)

    def test_record_count_must_match_basis_inventory(self):
        bad = copy.deepcopy(self.catalog)
        bad["sources"][0]["record_count"] += 1
        resign_catalog(bad)
        with self.assertRaises(bridge.ReplayManifestBridgeError):
            bridge.build_replay_manifest(self.inventory, bad)

    def test_catalog_tampering_is_rejected(self):
        bad = copy.deepcopy(self.catalog)
        bad["sources"][0]["location"] = "file:///tampered"
        with self.assertRaises(bridge.ReplayManifestBridgeError):
            bridge.build_replay_manifest(self.inventory, bad)

    def test_output_tampering_is_rejected(self):
        result = bridge.build_replay_manifest(self.inventory, self.catalog)
        result["manifest"]["entries"][0]["location"] = "file:///tampered"
        with self.assertRaises(bridge.ReplayManifestBridgeError):
            bridge.validate_bridge_output(
                result,
                inventory=self.inventory,
                source_catalog=self.catalog,
            )

    def test_source_inputs_are_immutable(self):
        inventory_before = copy.deepcopy(self.inventory)
        catalog_before = copy.deepcopy(self.catalog)
        bridge.build_replay_manifest(self.inventory, self.catalog)
        self.assertEqual(self.inventory, inventory_before)
        self.assertEqual(self.catalog, catalog_before)

    def test_authority_is_permanently_disabled(self):
        result = bridge.build_replay_manifest(self.inventory, self.catalog)
        self.assertFalse(result["actual_outcomes_used"])
        self.assertFalse(result["may_change_blind_forecast"])
        self.assertFalse(result["may_change_posterior"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["execution_authority"])
        self.assertFalse(result["manifest"]["execution_authority"])


if __name__ == "__main__":
    unittest.main()
