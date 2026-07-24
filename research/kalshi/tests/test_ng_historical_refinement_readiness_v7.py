from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import ng_historical_refinement_readiness_v7 as readiness


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


class HistoricalRefinementReadinessV7Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}

    def _complete(self, root: Path) -> tuple[dict, dict[str, dict]]:
        values = readiness._linked_fixture_chain()
        for spec in readiness.STAGES:
            _write(root / spec.filename, values[spec.key])
        report = readiness.build_readiness_report(
            root, validator_overrides=self.overrides
        )
        return report, values

    def test_stage_order_places_partition_before_g15(self) -> None:
        order = [spec.key for spec in readiness.STAGES]
        self.assertEqual(
            order[:6],
            [
                "corpus_coverage",
                "basis_inventory_regeneration",
                "replay_catalog_export",
                "broad_corpus_scope",
                "broad_corpus_exact_overlap",
                "broad_corpus_exact_partition",
            ],
        )
        self.assertLess(
            order.index("broad_corpus_exact_partition"),
            order.index("g15_exact_replay"),
        )

    def test_complete_chain_reports_v7(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            report, _ = self._complete(Path(tempdir))
        self.assertEqual(
            report["status"],
            "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V7",
        )
        self.assertTrue(report["broad_corpus_exact_partition_verified"])

    def test_missing_partition_blocks_g15(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            report, _ = self._complete(root)
            self.assertIn("g15_exact_replay", report["ready_stages"])
            (root / "ng_broad_corpus_exact_partition_gate.json").unlink()
            blocked = readiness.build_readiness_report(
                root, validator_overrides=self.overrides
            )
        self.assertEqual(
            blocked["first_blocking_stage"],
            "broad_corpus_exact_partition",
        )
        g15 = next(
            row for row in blocked["stages"] if row["key"] == "g15_exact_replay"
        )
        self.assertEqual(g15["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_partition_link_substitution_invalidates_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            _, values = self._complete(root)
            partition = copy.deepcopy(values["broad_corpus_exact_partition"])
            partition["exact_overlap_gate_fingerprint"] = "replacement"
            _write(root / "ng_broad_corpus_exact_partition_gate.json", partition)
            report = readiness.build_readiness_report(
                root, validator_overrides=self.overrides
            )
        row = next(
            value
            for value in report["stages"]
            if value["key"] == "broad_corpus_exact_partition"
        )
        self.assertEqual(row["effective_status"], "INVALID")
        self.assertNotIn("g15_exact_replay", report["ready_stages"])

    def test_v6_stage_order_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            report, _ = self._complete(Path(tempdir))
        tampered = copy.deepcopy(report)
        tampered["stage_order"].remove("broad_corpus_exact_partition")
        tampered["stages"] = [
            row
            for row in tampered["stages"]
            if row["key"] != "broad_corpus_exact_partition"
        ]
        tampered["ready_stages"].remove("broad_corpus_exact_partition")
        tampered["ready_stage_count"] -= 1
        tampered["broad_corpus_exact_partition_verified"] = False
        tampered.pop("fingerprint")
        tampered["fingerprint"] = readiness._fingerprint(tampered)
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness.validate_readiness_report(tampered)

    def test_authority_escalation_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            report, _ = self._complete(Path(tempdir))
        tampered = copy.deepcopy(report)
        tampered["options_lane_started"] = True
        tampered.pop("fingerprint")
        tampered["fingerprint"] = readiness._fingerprint(tampered)
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness.validate_readiness_report(tampered)

    def test_report_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            first, _ = self._complete(root)
            second = readiness.build_readiness_report(
                root, validator_overrides=self.overrides
            )
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
