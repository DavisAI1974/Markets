from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ng_corpus_executor_pipeline_arm_v5 as arm
import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v5 as compiler
import ng_historical_refinement_executor_v6 as executor
import ng_historical_refinement_readiness_v8 as readiness


class CorpusExecutionV8Tests(unittest.TestCase):
    def _root(self) -> Path:
        return Path(tempfile.mkdtemp())

    def _compiled(self) -> tuple[dict, dict, dict[str, list[str]]]:
        root = self._root()
        slice_path = root / "slice.json"
        inspection_path = root / "inspection.json"
        slice_path.write_text("{}\n", encoding="utf-8")
        inspection_path.write_text("{}\n", encoding="utf-8")
        with mock.patch.object(
            compiler.fingerprinting,
            "validate_inputs",
            return_value=(
                {"slice_bundle_fingerprint": "slice-fingerprint"},
                {"plan_fingerprint": "inspection-fingerprint"},
            ),
        ):
            plan, receipt = compiler.build_compiled_plan(
                artifact_dir=root / "artifacts",
                working_directory=root / "work",
                slice_bundle_path=slice_path,
                inspection_plan_path=inspection_path,
            )
        return plan, receipt, compiler._commands(root / "artifacts", slice_path, inspection_path)

    def test_compiler_binds_exact_readiness_v8_stage_contract(self) -> None:
        plan, receipt, _ = self._compiled()
        keys = [row["key"] for row in plan["stages"]]
        self.assertEqual(keys, [spec.key for spec in readiness.STAGES])
        self.assertEqual(receipt["readiness_contract"], readiness.SCHEMA)
        self.assertLess(keys.index("g15_exact_replay"), keys.index(compiler.WINDOW_STAGE))
        self.assertLess(keys.index(compiler.WINDOW_STAGE), keys.index("g15_exact_refinement"))

    def test_compiler_configures_only_six_pre_outcome_corpus_stages(self) -> None:
        plan, receipt, commands = self._compiled()
        rows = {row["key"]: row for row in plan["stages"]}
        self.assertEqual(receipt["configured_stages"], list(compiler.CONFIGURED_STAGES))
        self.assertEqual(len(compiler.CONFIGURED_STAGES), 6)
        self.assertTrue(rows["corpus_coverage"]["enabled"])
        for key in compiler.CONFIGURED_STAGES[1:]:
            self.assertFalse(rows[key]["enabled"])
        for key in compiler.CONFIGURED_STAGES:
            self.assertFalse(rows[key]["requires_fixed_outcomes"])
            self.assertEqual(rows[key]["argv"], commands[key])
        self.assertFalse(rows[compiler.WINDOW_STAGE]["enabled"])
        self.assertFalse(rows[compiler.WINDOW_STAGE]["requires_fixed_outcomes"])

    def test_compiler_rejects_readiness_v7_plan_without_window_stage(self) -> None:
        plan, receipt, commands = self._compiled()
        changed = copy.deepcopy(plan)
        changed["stages"] = [row for row in changed["stages"] if row["key"] != compiler.WINDOW_STAGE]
        changed.pop("fingerprint")
        changed["fingerprint"] = executor.legacy_executor._fingerprint(changed)
        with self.assertRaises(Exception):
            compiler.validate_receipt(receipt, plan=changed, commands=commands)

    def test_compiler_rejects_replay_window_requirement_removal(self) -> None:
        plan, receipt, commands = self._compiled()
        changed = copy.deepcopy(receipt)
        changed["exact_g15_replay_window_authorization_required"] = False
        changed.pop("fingerprint")
        changed["fingerprint"] = fingerprinting._fp(changed)
        with self.assertRaises(compiler.CorpusExecutorPlanCompilerV5Error):
            compiler.validate_receipt(changed, plan=plan, commands=commands)

    def test_arm_enables_only_corpus_prefix(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        rows = {row["key"]: row for row in armed["stages"]}
        for key in arm.ARMED_STAGES:
            self.assertTrue(rows[key]["enabled"])
        for spec in readiness.STAGES[len(arm.ARMED_STAGES):]:
            self.assertFalse(rows[spec.key]["enabled"])
        self.assertEqual(arm_receipt["stage_order_prefix"], list(arm.ARMED_STAGES))

    def test_arm_keeps_replay_window_disabled_before_g15_replay(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        rows = {row["key"]: row for row in armed["stages"]}
        self.assertFalse(rows["g15_exact_replay"]["enabled"])
        self.assertFalse(rows[arm.WINDOW_STAGE]["enabled"])
        self.assertFalse(rows["g15_exact_refinement"]["enabled"])
        self.assertTrue(arm_receipt["exact_g15_replay_window_authorization_required_before_refinement"])
        self.assertFalse(arm_receipt["exact_g15_replay_window_stage_enabled"])

    def test_arm_is_deterministic(self) -> None:
        plan, receipt, _ = self._compiled()
        first = arm.build_armed_plan(plan, receipt)
        second = arm.build_armed_plan(plan, receipt)
        self.assertEqual(first, second)

    def test_arm_rejects_refingerprinted_window_activation(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        changed = copy.deepcopy(armed)
        row = next(row for row in changed["stages"] if row["key"] == arm.WINDOW_STAGE)
        row["enabled"] = True
        changed.pop("fingerprint")
        changed["fingerprint"] = executor.legacy_executor._fingerprint(changed)
        with self.assertRaises(Exception):
            arm.validate_arm_receipt(
                arm_receipt,
                compiled_plan=plan,
                compiler_receipt=receipt,
                armed_plan=changed,
            )

    def test_arm_rejects_refingerprinted_options_escalation(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        changed = copy.deepcopy(arm_receipt)
        changed["options_lane_started"] = True
        changed.pop("fingerprint")
        changed["fingerprint"] = fingerprinting._fp(changed)
        with self.assertRaises(arm.CorpusExecutorPipelineArmV5Error):
            arm.validate_arm_receipt(
                changed,
                compiled_plan=plan,
                compiler_receipt=receipt,
                armed_plan=armed,
            )

    def test_permanent_authority_and_historical_first_contract(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        self.assertEqual(plan["outcome_paths"], [])
        for value in (receipt, arm_receipt):
            self.assertFalse(value["actual_outcomes_used"])
            self.assertFalse(value["paid_live_data_assumed"])
            self.assertFalse(value["random_shuffle_used"])
            self.assertTrue(value["one_signal_authority_preserved"])
            self.assertTrue(value["blind_forecasts_immutable"])
            self.assertFalse(value["may_update_ng_brain"])
            self.assertFalse(value["execution_authority"])
            self.assertEqual(value["cme_event_contracts_mode"], "SHADOW")
            self.assertEqual(value["brokerage_contract"], "tastytrade_not_ibkr")
            self.assertFalse(value["options_lane_started"])
        self.assertEqual(arm_receipt["armed_plan_fingerprint"], armed["fingerprint"])


if __name__ == "__main__":
    unittest.main()
