from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path

import ng_historical_refinement_executor_v3 as executor
import ng_historical_refinement_readiness_v4 as v4
import ng_historical_refinement_readiness_v5 as readiness


class HistoricalRefinementReadinessV5Tests(unittest.TestCase):
    def _write_chain(self, root: Path) -> dict[str, dict]:
        values = readiness._linked_fixture_chain()
        for spec in readiness.STAGES:
            readiness._atomic_json(root / spec.filename, values[spec.key])
        return values

    @staticmethod
    def _overrides() -> dict:
        return {spec.key: (lambda value: None) for spec in readiness.STAGES}

    def test_broad_scope_is_between_export_and_g15_replay(self) -> None:
        order = [spec.key for spec in readiness.STAGES]
        self.assertEqual(
            order[:5],
            [
                "corpus_coverage",
                "basis_inventory_regeneration",
                "replay_catalog_export",
                "broad_corpus_scope",
                "g15_exact_replay",
            ],
        )
        self.assertTrue(next(spec for spec in readiness.STAGES if spec.key == "broad_corpus_scope").pre_outcome)

    def test_missing_broad_gate_blocks_g15(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self._write_chain(root)
            (root / "ng_broad_corpus_scope_gate.json").unlink()
            report = readiness.build_readiness_report(root, validator_overrides=self._overrides())
            self.assertEqual(report["first_blocking_stage"], "broad_corpus_scope")
            self.assertFalse(report["broad_corpus_verified"])
            g15 = next(row for row in report["stages"] if row["key"] == "g15_exact_replay")
            self.assertEqual(g15["effective_status"], "BLOCKED_BY_UPSTREAM")

    def test_complete_chain_requires_v5_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self._write_chain(root)
            report = readiness.build_readiness_report(root, validator_overrides=self._overrides())
            self.assertEqual(report["status"], "G15_G16_COUNTERFACTUAL_PUBLICATION_COMPLETE_V5")
            self.assertTrue(report["broad_corpus_verified"])
            self.assertEqual(report["ready_stage_count"], len(readiness.STAGES))

    def test_coverage_fingerprint_substitution_blocks_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            values = self._write_chain(root)
            broad_spec = next(spec for spec in readiness.STAGES if spec.key == "broad_corpus_scope")
            broad = copy.deepcopy(values["broad_corpus_scope"])
            broad["coverage_audit_fingerprint"] = "replacement-audit"
            broad.pop(broad_spec.fingerprint_field)
            broad[broad_spec.fingerprint_field] = readiness._fingerprint(broad)
            readiness._atomic_json(root / broad_spec.filename, broad)
            report = readiness.build_readiness_report(root, validator_overrides=self._overrides())
            row = next(row for row in report["stages"] if row["key"] == "broad_corpus_scope")
            self.assertEqual(row["effective_status"], "INVALID")
            self.assertEqual(report["first_blocking_stage"], "broad_corpus_scope")

    def test_v4_report_does_not_validate_as_v5(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            overrides = {spec.key: (lambda value: None) for spec in v4.STAGES}
            values = v4._linked_fixture_chain()
            for spec in v4.STAGES:
                v4._atomic_json(root / spec.filename, values[spec.key])
            report = v4.build_readiness_report(root, validator_overrides=overrides)
            with self.assertRaises(readiness.HistoricalRefinementReadinessError):
                readiness.validate_readiness_report(report)

    def test_executor_v3_plan_contains_broad_stage(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            plan = executor.build_plan(root / "artifacts", root / "work")
            executor.validate_plan(plan)
            order = [row["key"] for row in plan["stages"]]
            self.assertEqual(order, [spec.key for spec in readiness.STAGES])
            broad = next(row for row in plan["stages"] if row["key"] == "broad_corpus_scope")
            self.assertFalse(broad["enabled"])
            self.assertFalse(broad["requires_fixed_outcomes"])

    def test_executor_has_broad_gate_entrypoint(self) -> None:
        self.assertEqual(
            executor.SUGGESTED_ENTRYPOINTS["broad_corpus_scope"],
            ("python", "ng_broad_corpus_scope_gate.py"),
        )

    def test_broad_stage_remains_pre_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            plan = executor.build_plan(root / "artifacts", root / "work")
            broad = next(row for row in plan["stages"] if row["key"] == "broad_corpus_scope")
            self.assertFalse(broad["requires_fixed_outcomes"])
            self.assertNotIn("broad_corpus_scope", plan.get("outcome_paths") or [])

    def test_report_authority_escalation_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self._write_chain(root)
            report = readiness.build_readiness_report(root, validator_overrides=self._overrides())
            report["options_lane_started"] = True
            report.pop("fingerprint")
            report["fingerprint"] = readiness._fingerprint(report)
            with self.assertRaises(readiness.HistoricalRefinementReadinessError):
                readiness.validate_readiness_report(report)

    def test_report_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self._write_chain(root)
            first = readiness.build_readiness_report(root, validator_overrides=self._overrides())
            second = readiness.build_readiness_report(root, validator_overrides=self._overrides())
            self.assertEqual(first, second)

    def test_permanent_controls_remain_locked(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            self._write_chain(root)
            report = readiness.build_readiness_report(root, validator_overrides=self._overrides())
            self.assertFalse(report["random_shuffle_used"])
            self.assertFalse(report["may_update_ng_brain"])
            self.assertFalse(report["execution_authority"])
            self.assertEqual(report["cme_event_contracts_mode"], "SHADOW")
            self.assertEqual(report["brokerage_contract"], "tastytrade_not_ibkr")
            self.assertFalse(report["options_lane_started"])


if __name__ == "__main__":
    unittest.main()
