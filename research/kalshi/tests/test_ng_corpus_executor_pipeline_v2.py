from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ng_corpus_executor_pipeline_arm_v2 as arm
import ng_corpus_executor_plan_compiler as base
import ng_corpus_executor_plan_compiler_v2 as compiler
import ng_historical_refinement_executor_v3 as executor
import ng_historical_refinement_readiness_v5 as readiness


class CorpusExecutorPipelineV2Tests(unittest.TestCase):
    def _compiled(self) -> tuple[dict, dict, dict[str, list[str]]]:
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            artifact_dir = root / "artifacts"
            work = root / "work"
            artifact_dir.mkdir()
            work.mkdir()
            slice_path = root / "slice.json"
            inspection_path = root / "inspection.json"
            fake_slice = {"slice_bundle_fingerprint": "slice-fingerprint"}
            fake_inspection = {"plan_fingerprint": "inspection-fingerprint"}
            with mock.patch.object(compiler, "_load", side_effect=[{"raw": "slice"}, {"raw": "plan"}]), mock.patch.object(
                base,
                "validate_inputs",
                return_value=(fake_slice, fake_inspection),
            ):
                plan, receipt = compiler.build_compiled_plan(
                    artifact_dir=artifact_dir,
                    working_directory=work,
                    slice_bundle_path=slice_path,
                    inspection_plan_path=inspection_path,
                )
            commands = {
                row["key"]: list(row["argv"])
                for row in plan["stages"]
                if row["key"] in compiler.CONFIGURED_STAGES
            }
            return copy.deepcopy(plan), copy.deepcopy(receipt), commands

    def test_compiler_uses_readiness_v5_order(self) -> None:
        plan, receipt, _ = self._compiled()
        self.assertEqual(
            [row["key"] for row in plan["stages"]],
            [spec.key for spec in readiness.STAGES],
        )
        self.assertEqual(receipt["configured_stages"], list(compiler.CONFIGURED_STAGES))
        self.assertEqual(
            list(compiler.CONFIGURED_STAGES),
            [
                "corpus_coverage",
                "basis_inventory_regeneration",
                "replay_catalog_export",
                "broad_corpus_scope",
            ],
        )

    def test_only_inspection_is_enabled_in_compiled_plan(self) -> None:
        plan, _, _ = self._compiled()
        rows = {row["key"]: row for row in plan["stages"]}
        self.assertTrue(rows["corpus_coverage"]["enabled"])
        for key in compiler.CONFIGURED_STAGES[1:]:
            self.assertFalse(rows[key]["enabled"])
        self.assertFalse(any(row["enabled"] for row in plan["stages"][4:]))

    def test_broad_command_is_bound_to_inspection_receipt(self) -> None:
        plan, _, _ = self._compiled()
        argv = next(row["argv"] for row in plan["stages"] if row["key"] == "broad_corpus_scope")
        self.assertEqual(argv[:2], ["python", "ng_broad_corpus_scope_gate.py"])
        self.assertIn("--inspection-receipt", argv)
        self.assertTrue(any(part.endswith("ng_corpus_inspection_receipt.json") for part in argv))
        self.assertTrue(any(part.endswith("ng_broad_corpus_scope_gate.json") for part in argv))

    def test_all_compiled_corpus_stages_are_pre_outcome(self) -> None:
        plan, _, _ = self._compiled()
        rows = {row["key"]: row for row in plan["stages"]}
        for key in compiler.CONFIGURED_STAGES:
            self.assertFalse(rows[key]["requires_fixed_outcomes"])
        self.assertEqual(plan["outcome_paths"], [])

    def test_compiler_receipt_tampering_is_rejected(self) -> None:
        plan, receipt, commands = self._compiled()
        receipt["configured_stages"] = list(reversed(receipt["configured_stages"]))
        receipt.pop("fingerprint")
        receipt["fingerprint"] = base._fp(receipt)
        with self.assertRaises(compiler.CorpusExecutorPlanCompilerV2Error):
            compiler.validate_receipt(receipt, plan=plan, commands=commands)

    def test_arm_enables_exactly_four_corpus_stages(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        rows = {row["key"]: row for row in armed["stages"]}
        for key in arm.ARMED_STAGES:
            self.assertTrue(rows[key]["enabled"])
        for spec in readiness.STAGES[4:]:
            self.assertFalse(rows[spec.key]["enabled"])
        self.assertEqual(arm_receipt["status"], arm.STATUS)
        self.assertTrue(arm_receipt["broad_corpus_gate_armed_before_g15"])

    def test_arm_preserves_one_stable_plan_lineage(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        self.assertEqual(arm_receipt["compiled_plan_fingerprint"], plan["fingerprint"])
        self.assertEqual(arm_receipt["armed_plan_fingerprint"], armed["fingerprint"])
        self.assertTrue(arm_receipt["single_stable_plan_for_target_and_broad_corpus_stages"])
        self.assertTrue(arm_receipt["single_stable_ledger_supported"])

    def test_arm_command_substitution_is_rejected(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        changed = copy.deepcopy(armed)
        row = next(row for row in changed["stages"] if row["key"] == "broad_corpus_scope")
        row["argv"][-1] = "/tmp/replacement.json"
        changed.pop("fingerprint")
        changed["fingerprint"] = executor.legacy_executor._fingerprint(changed)
        with self.assertRaises(arm.CorpusExecutorPipelineArmV2Error):
            arm.validate_arm_receipt(
                arm_receipt,
                compiled_plan=plan,
                compiler_receipt=receipt,
                armed_plan=changed,
            )

    def test_pre_enabled_g15_is_rejected_by_compiler_validator(self) -> None:
        plan, receipt, commands = self._compiled()
        changed = executor.configure_stage(
            plan,
            "g15_exact_replay",
            ["python", "ng_historical_replay_prepared.py"],
            enabled=True,
        )
        receipt = copy.deepcopy(receipt)
        receipt["execution_plan_fingerprint"] = changed["fingerprint"]
        receipt.pop("fingerprint")
        receipt["fingerprint"] = base._fp(receipt)
        with self.assertRaises(compiler.CorpusExecutorPlanCompilerV2Error):
            compiler.validate_receipt(receipt, plan=changed, commands=commands)

    def test_arm_receipt_authority_escalation_is_rejected(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        arm_receipt["options_lane_started"] = True
        arm_receipt.pop("fingerprint")
        arm_receipt["fingerprint"] = base._fp(arm_receipt)
        with self.assertRaises(arm.CorpusExecutorPipelineArmV2Error):
            arm.validate_arm_receipt(
                arm_receipt,
                compiled_plan=plan,
                compiler_receipt=receipt,
                armed_plan=armed,
            )

    def test_output_is_deterministic(self) -> None:
        plan, receipt, _ = self._compiled()
        self.assertEqual(arm.build_armed_plan(plan, receipt), arm.build_armed_plan(plan, receipt))

    def test_permanent_controls(self) -> None:
        plan, receipt, _ = self._compiled()
        _, result = arm.build_armed_plan(plan, receipt)
        self.assertFalse(result["actual_outcomes_used"])
        self.assertFalse(result["random_shuffle_used"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["execution_authority"])
        self.assertEqual(result["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(result["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(result["options_lane_started"])


if __name__ == "__main__":
    unittest.main()
