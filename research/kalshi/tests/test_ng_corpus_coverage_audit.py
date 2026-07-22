from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

KALSHI = Path(__file__).resolve().parents[1]
if str(KALSHI) not in sys.path:
    sys.path.insert(0, str(KALSHI))

import ng_corpus_coverage_audit as audit


class CorpusCoverageAuditTests(unittest.TestCase):
    def test_unknown_template_never_invents_presence(self) -> None:
        value = audit.build_audit(
            audit.expected_catalog_template(publisher_id=7)
        )
        self.assertEqual(value["status"], "UNKNOWN")
        self.assertEqual(
            value["exact_intersections"]["g15"]["status"], "UNKNOWN"
        )
        self.assertEqual(
            value["exact_intersections"]["g16"]["status"], "UNKNOWN"
        )
        self.assertFalse(value["paid_live_data_assumed"])

    def test_exact_targets_ready_while_broad_inventory_unverified(self) -> None:
        value = audit.build_audit(audit._fixture(complete=False))
        self.assertEqual(
            value["status"],
            "G15_G16_EXACT_READY_BROAD_COVERAGE_UNVERIFIED",
        )
        self.assertTrue(
            value["exact_intersections"]["g15"]["can_run_exact_replay"]
        )
        self.assertTrue(
            value["exact_intersections"]["g16"]["can_run_exact_replay"]
        )
        self.assertTrue(
            all(row["status"] == "PARTIAL" for row in value["corpus_layout"])
        )

    def test_declared_complete_inventory_and_exact_targets_ready(self) -> None:
        value = audit.build_audit(audit._fixture(complete=True))
        self.assertEqual(
            value["status"], "FULL_CORPUS_AND_G15_G16_EXACT_READY"
        )
        self.assertTrue(
            all(
                row["status"] == "VERIFIED_COMPLETE"
                for row in value["corpus_layout"]
            )
        )
        audit.validate_audit(value)

    def test_wrong_g15_preroll_l1_basis_blocks_exact_replay(self) -> None:
        catalog = audit._fixture()
        l1 = catalog["corpora"][0]
        row = next(
            row for row in l1["entries"] if row["day"] == "20260316"
        )
        row["raw_symbol"] = "NGK26"
        row["instrument_id"] = 996
        catalog.pop("catalog_fingerprint")
        catalog["catalog_fingerprint"] = audit._fp(catalog)

        value = audit.build_audit(catalog)
        day = next(
            row
            for row in value["exact_intersections"]["g15"]["day_reports"]
            if row["day"] == "20260316"
        )
        self.assertEqual(day["blocker"], "WRONG_BASIS_PRESENT")
        self.assertFalse(
            value["exact_intersections"]["g15"]["can_run_exact_replay"]
        )

    def test_definition_or_publisher_mismatch_blocks_pair(self) -> None:
        catalog = audit._fixture()
        mbo = catalog["corpora"][1]
        row = next(
            row for row in mbo["entries"] if row["day"] == "20260401"
        )
        row["publisher_id"] = 9
        catalog.pop("catalog_fingerprint")
        catalog["catalog_fingerprint"] = audit._fp(catalog)

        value = audit.build_audit(catalog)
        day = next(
            row
            for row in value["exact_intersections"]["g16"]["day_reports"]
            if row["day"] == "20260401"
        )
        self.assertEqual(
            day["blocker"], "IDENTITY_OR_EVENT_TIME_MISMATCH"
        )

    def test_non_overlapping_event_time_blocks_pair(self) -> None:
        catalog = audit._fixture()
        mbo_row = next(
            row
            for row in catalog["corpora"][1]["entries"]
            if row["day"] == "20260330"
        )
        mbo_row["event_start_s"] = mbo_row["definition_end_s"] - 10.0
        mbo_row["event_end_s"] = mbo_row["definition_end_s"]
        l1_row = next(
            row
            for row in catalog["corpora"][0]["entries"]
            if row["day"] == "20260330"
        )
        l1_row["event_end_s"] = l1_row["event_start_s"] + 5.0
        catalog.pop("catalog_fingerprint")
        catalog["catalog_fingerprint"] = audit._fp(catalog)

        value = audit.build_audit(catalog)
        day = next(
            row
            for row in value["exact_intersections"]["g16"]["day_reports"]
            if row["day"] == "20260330"
        )
        self.assertEqual(
            day["blocker"], "IDENTITY_OR_EVENT_TIME_MISMATCH"
        )

    def test_unknown_source_is_not_present(self) -> None:
        catalog = audit._fixture()
        row = next(
            row
            for row in catalog["corpora"][1]["entries"]
            if row["day"] == "20260324"
        )
        row["status"] = "UNKNOWN"
        catalog["corpora"][1]["inventory_complete"] = False
        catalog.pop("catalog_fingerprint")
        catalog["catalog_fingerprint"] = audit._fp(catalog)

        value = audit.build_audit(catalog)
        day = next(
            row
            for row in value["exact_intersections"]["g15"]["day_reports"]
            if row["day"] == "20260324"
        )
        self.assertEqual(day["status"], "UNKNOWN")
        self.assertEqual(day["blocker"], "UNINSPECTED_SOURCE")

    def test_duplicate_source_id_blocks_catalog(self) -> None:
        catalog = audit._fixture()
        catalog["corpora"][1]["entries"][0]["source_id"] = (
            catalog["corpora"][0]["entries"][0]["source_id"]
        )
        catalog.pop("catalog_fingerprint")
        catalog["catalog_fingerprint"] = audit._fp(catalog)

        value = audit.build_audit(catalog)
        self.assertEqual(value["status"], "BLOCKED")
        errors = [
            error
            for row in value["corpus_layout"]
            for error in row["validation_errors"]
        ]
        self.assertTrue(
            any("duplicate source_id" in error for error in errors)
        )

    def test_contradictory_complete_claim_is_visible(self) -> None:
        catalog = audit._fixture()
        catalog["corpora"][0]["observed_object_count"] -= 1
        catalog.pop("catalog_fingerprint")
        catalog["catalog_fingerprint"] = audit._fp(catalog)

        value = audit.build_audit(catalog)
        l1 = next(
            row
            for row in value["corpus_layout"]
            if row["corpus_id"] == audit.L1_CORPUS_ID
        )
        self.assertEqual(l1["status"], "CONTRADICTORY_COMPLETE_CLAIM")

    def test_wrong_declared_window_blocks_layout(self) -> None:
        catalog = audit._fixture()
        catalog["corpora"][1]["declared_window"]["start"] = "2026-04-01"
        catalog.pop("catalog_fingerprint")
        catalog["catalog_fingerprint"] = audit._fp(catalog)

        value = audit.build_audit(catalog)
        self.assertEqual(value["status"], "BLOCKED")
        self.assertTrue(
            any(
                "declared window" in error
                for error in value["structural_errors"]
            )
        )

    def test_catalog_tampering_is_rejected(self) -> None:
        catalog = audit._fixture()
        catalog["corpora"][0]["entries"][0]["record_count"] += 1
        with self.assertRaises(audit.CorpusCoverageError):
            audit.build_audit(catalog)

    def test_audit_tampering_is_rejected(self) -> None:
        value = audit.build_audit(audit._fixture())
        value["exact_intersections"]["g15"]["ready_days"].pop()
        value.pop("fingerprint")
        value["fingerprint"] = audit._fp(value)
        with self.assertRaises(audit.CorpusCoverageError):
            audit.validate_audit(value)

    def test_causal_authority_flags_are_permanently_disabled(self) -> None:
        catalog = audit._fixture()
        fields = (
            "actual_outcomes_used",
            "paid_live_data_assumed",
            "may_update_ng_brain",
            "may_change_blind_forecast",
            "execution_authority",
        )
        for field in fields:
            bad = copy.deepcopy(catalog)
            bad[field] = True
            bad.pop("catalog_fingerprint")
            bad["catalog_fingerprint"] = audit._fp(bad)
            with self.subTest(field=field), self.assertRaises(
                audit.CorpusCoverageError
            ):
                audit.build_audit(bad)

        value = audit.build_audit(catalog)
        self.assertFalse(value["options_lane_started"])
        self.assertEqual(value["cme_event_contracts_mode"], "SHADOW")

    def test_longest_exact_overlap_is_selected_deterministically(self) -> None:
        catalog = audit._fixture()
        day = "20260320"
        extra = copy.deepcopy(
            next(
                row
                for row in catalog["corpora"][0]["entries"]
                if row["day"] == day
            )
        )
        extra["source_id"] = "l1-extra-short"
        extra["location"] = "s3://observed/l1-extra-short"
        extra["event_start_s"] += 100.0
        extra["event_end_s"] -= 100.0
        catalog["corpora"][0]["entries"].append(extra)
        corpus = catalog["corpora"][0]
        corpus["expected_object_count"] += 1
        corpus["observed_object_count"] += 1
        catalog.pop("catalog_fingerprint")
        catalog["catalog_fingerprint"] = audit._fp(catalog)

        value = audit.build_audit(catalog)
        report = next(
            row
            for row in value["exact_intersections"]["g15"]["day_reports"]
            if row["day"] == day
        )
        self.assertNotEqual(
            report["selected_pair"]["l1_source_id"], "l1-extra-short"
        )
        self.assertEqual(report["multiple_compatible_pairs"], 1)

    def test_source_input_is_not_mutated(self) -> None:
        catalog = audit._fixture()
        before = json.dumps(catalog, sort_keys=True)
        audit.build_audit(catalog)
        self.assertEqual(json.dumps(catalog, sort_keys=True), before)

    def test_missing_required_corpus_blocks(self) -> None:
        catalog = audit._fixture()
        catalog["corpora"] = catalog["corpora"][:1]
        catalog.pop("catalog_fingerprint")
        catalog["catalog_fingerprint"] = audit._fp(catalog)

        value = audit.build_audit(catalog)
        self.assertEqual(value["status"], "BLOCKED")
        self.assertTrue(
            any(
                "missing required corpora" in error
                for error in value["structural_errors"]
            )
        )


if __name__ == "__main__":
    unittest.main()
