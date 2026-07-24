from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import ng_historical_refinement_readiness_v6 as readiness


class HistoricalRefinementReadinessV6Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.overrides = {spec.key: (lambda value: None) for spec in readiness.STAGES}

    def _write_chain(self) -> dict[str, dict]:
        values = readiness._linked_fixture_chain()
        for spec in readiness.STAGES:
            readiness._atomic_json(self.root / spec.filename, values[spec.key])
        return values

    def test_exact_overlap_stage_precedes_g15_replay(self) -> None:
        order = [spec.key for spec in readiness.STAGES]
        self.assertLess(order.index("broad_corpus_scope"), order.index("broad_corpus_exact_overlap"))
        self.assertLess(order.index("broad_corpus_exact_overlap"), order.index("g15_exact_replay"))
        overlap = next(spec for spec in readiness.STAGES if spec.key == "broad_corpus_exact_overlap")
        self.assertTrue(overlap.pre_outcome)

    def test_complete_chain_reports_v6(self) -> None:
        self._write_chain()
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        self.assertEqual(
            report["status"], "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V6"
        )
        self.assertTrue(report["broad_corpus_exact_overlap_verified"])
        self.assertIn("broad_corpus_exact_overlap", report["ready_stages"])

    def test_missing_overlap_blocks_g15(self) -> None:
        self._write_chain()
        overlap = next(spec for spec in readiness.STAGES if spec.key == "broad_corpus_exact_overlap")
        (self.root / overlap.filename).unlink()
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        self.assertEqual(report["first_blocking_stage"], "broad_corpus_exact_overlap")
        g15 = next(row for row in report["stages"] if row["key"] == "g15_exact_replay")
        self.assertEqual(g15["effective_status"], "BLOCKED_BY_UPSTREAM")
        self.assertFalse(report["broad_corpus_exact_overlap_verified"])

    def test_refingerprinted_broad_scope_link_substitution_blocks(self) -> None:
        values = self._write_chain()
        spec = next(spec for spec in readiness.STAGES if spec.key == "broad_corpus_exact_overlap")
        value = copy.deepcopy(values[spec.key])
        value["broad_scope_gate_fingerprint"] = "replacement-broad-scope"
        value.pop(spec.fingerprint_field)
        value[spec.fingerprint_field] = readiness._fingerprint(value)
        readiness._atomic_json(self.root / spec.filename, value)
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        row = next(item for item in report["stages"] if item["key"] == spec.key)
        self.assertEqual(row["effective_status"], "INVALID")
        self.assertTrue(any("provenance link mismatch" in item for item in row["blockers"]))

    def test_coverage_audit_link_is_mandatory(self) -> None:
        values = self._write_chain()
        spec = next(spec for spec in readiness.STAGES if spec.key == "broad_corpus_exact_overlap")
        value = copy.deepcopy(values[spec.key])
        value["coverage_audit_fingerprint"] = "replacement-audit"
        value.pop(spec.fingerprint_field)
        value[spec.fingerprint_field] = readiness._fingerprint(value)
        readiness._atomic_json(self.root / spec.filename, value)
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        row = next(item for item in report["stages"] if item["key"] == spec.key)
        self.assertEqual(row["effective_status"], "INVALID")

    def test_legacy_v5_schema_is_rejected(self) -> None:
        self._write_chain()
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        report["schema"] = "ng_historical_refinement_readiness.v5"
        report.pop("fingerprint")
        report["fingerprint"] = readiness._fingerprint(report)
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness.validate_readiness_report(report)

    def test_refingerprinted_overlap_summary_tampering_is_rejected(self) -> None:
        self._write_chain()
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        report["broad_corpus_exact_overlap_verified"] = False
        report.pop("fingerprint")
        report["fingerprint"] = readiness._fingerprint(report)
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness.validate_readiness_report(report)

    def test_authority_escalation_is_rejected(self) -> None:
        self._write_chain()
        report = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        report["options_lane_started"] = True
        report.pop("fingerprint")
        report["fingerprint"] = readiness._fingerprint(report)
        with self.assertRaises(readiness.HistoricalRefinementReadinessError):
            readiness.validate_readiness_report(report)

    def test_report_is_deterministic(self) -> None:
        self._write_chain()
        first = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        second = readiness.build_readiness_report(
            self.root, validator_overrides=self.overrides
        )
        self.assertEqual(first, second)

    def test_fixed_outcome_boundary_remains_after_g15_lock(self) -> None:
        order = [spec.key for spec in readiness.STAGES]
        lock = next(spec for spec in readiness.STAGES if spec.key == "g15_counterfactual_scoring_lock")
        score = next(spec for spec in readiness.STAGES if spec.key == "g15_counterfactual_score_gate")
        self.assertTrue(lock.pre_outcome)
        self.assertFalse(score.pre_outcome)
        self.assertLess(order.index(lock.key), order.index(score.key))
        self.assertLess(order.index("broad_corpus_exact_overlap"), order.index(lock.key))


if __name__ == "__main__":
    unittest.main()
