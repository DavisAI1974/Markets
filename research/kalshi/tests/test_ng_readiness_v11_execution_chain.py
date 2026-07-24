from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ng_corpus_executor_pipeline_arm_v8 as arm
import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v8 as compiler
import ng_historical_refinement_executor_v8 as executor_v10
import ng_historical_refinement_executor_v9 as executor
import ng_historical_refinement_preflight_v9 as preflight
import ng_historical_refinement_readiness_v11 as readiness


class ReadinessV11ExecutionChainTests(unittest.TestCase):
    def _root(self) -> Path:
        return Path(tempfile.mkdtemp())

    def _compiled(self) -> tuple[dict, dict, dict[str, list[str]]]:
        root = self._root()
        slice_path = root / "slice.json"
        inspection_path = root / "inspection.json"
        slice_path.write_text("{}\n", encoding="utf-8")
        inspection_path.write_text("{}\n", encoding="utf-8")
        with mock.patch.object(
            compiler.v7.v6.fingerprinting,
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
        return (
            plan,
            receipt,
            compiler._commands(root / "artifacts", slice_path, inspection_path),
        )

    def test_executor_uses_exact_readiness_v11_stage_contract(self) -> None:
        root = self._root()
        plan = executor.build_plan(root / "artifacts", root / "work")
        self.assertEqual(
            [row["key"] for row in plan["stages"]],
            [spec.key for spec in readiness.STAGES],
        )
        self.assertEqual(
            executor.SUGGESTED_ENTRYPOINTS[
                compiler.G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE
            ],
            ("python", "ng_g16_exact_counterfactual_causal_authorization.py"),
        )

    def test_executor_rejects_readiness_v10_plan_without_exact_causal_join(self) -> None:
        root = self._root()
        old_plan = executor_v10.build_plan(root / "artifacts", root / "work")
        with self.assertRaises(Exception):
            executor.validate_plan(old_plan)

    def test_compiler_binds_exact_causal_join_before_curve(self) -> None:
        plan, receipt, _ = self._compiled()
        keys = [row["key"] for row in plan["stages"]]
        self.assertEqual(keys, [spec.key for spec in readiness.STAGES])
        self.assertEqual(receipt["readiness_contract"], readiness.SCHEMA)
        self.assertLess(
            keys.index("g16_counterfactual_causal_authorization"),
            keys.index(compiler.G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE),
        )
        self.assertLess(
            keys.index(compiler.G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE),
            keys.index("g16_prepared_curve_authorization"),
        )
        self.assertLess(
            keys.index("g16_prepared_curve_authorization"),
            keys.index("g16_counterfactual_curve_authorization"),
        )

    def test_compiler_keeps_exact_causal_join_disabled_and_pre_outcome(self) -> None:
        plan, receipt, _ = self._compiled()
        rows = {row["key"]: row for row in plan["stages"]}
        row = rows[compiler.G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE]
        self.assertFalse(row["enabled"])
        self.assertFalse(row["requires_fixed_outcomes"])
        self.assertTrue(
            receipt["g16_exact_counterfactual_causal_authorization_required"]
        )
        self.assertFalse(receipt["g16_exact_counterfactual_causal_stage_enabled"])

    def test_compiler_rejects_removed_exact_causal_join_stage(self) -> None:
        plan, receipt, commands = self._compiled()
        changed = copy.deepcopy(plan)
        changed["stages"] = [
            row
            for row in changed["stages"]
            if row["key"] != compiler.G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE
        ]
        changed.pop("fingerprint")
        changed["fingerprint"] = executor.legacy_executor._fingerprint(changed)
        with self.assertRaises(Exception):
            compiler.validate_receipt(receipt, plan=changed, commands=commands)

    def test_compiler_rejects_refingerprinted_exact_causal_requirement_removal(self) -> None:
        plan, receipt, commands = self._compiled()
        changed = copy.deepcopy(receipt)
        changed[
            "g16_exact_replay_provenance_must_join_counterfactual_lineage"
        ] = False
        changed.pop("fingerprint")
        changed["fingerprint"] = fingerprinting._fp(changed)
        with self.assertRaises(compiler.CorpusExecutorPlanCompilerV8Error):
            compiler.validate_receipt(changed, plan=plan, commands=commands)

    def test_arm_enables_only_six_corpus_stages(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        rows = {row["key"]: row for row in armed["stages"]}
        for key in arm.ARMED_STAGES:
            self.assertTrue(rows[key]["enabled"])
        for spec in readiness.STAGES[len(arm.ARMED_STAGES) :]:
            self.assertFalse(rows[spec.key]["enabled"])
        self.assertEqual(arm_receipt["stage_order_prefix"], list(arm.ARMED_STAGES))

    def test_arm_keeps_exact_causal_and_curve_stages_disabled(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        rows = {row["key"]: row for row in armed["stages"]}
        for key in (
            "g16_counterfactual_causal_authorization",
            arm.G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE,
            "g16_prepared_curve_authorization",
            "g16_counterfactual_curve_authorization",
        ):
            self.assertFalse(rows[key]["enabled"])
        self.assertTrue(
            arm_receipt[
                "g16_exact_counterfactual_causal_authorization_required_before_curve"
            ]
        )
        self.assertFalse(
            arm_receipt["g16_exact_counterfactual_causal_stage_enabled"]
        )

    def test_arm_rejects_refingerprinted_exact_causal_activation(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        changed = copy.deepcopy(armed)
        row = next(
            row
            for row in changed["stages"]
            if row["key"] == arm.G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE
        )
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

    def test_arm_is_deterministic(self) -> None:
        plan, receipt, _ = self._compiled()
        self.assertEqual(
            arm.build_armed_plan(plan, receipt),
            arm.build_armed_plan(plan, receipt),
        )

    def test_preflight_binds_executor_and_readiness_v11(self) -> None:
        self.assertEqual(
            preflight.EXECUTOR_CONTRACT,
            "ng_historical_refinement_executor_v9",
        )
        self.assertEqual(preflight.READINESS_CONTRACT, readiness.SCHEMA)
        self.assertEqual(
            preflight.STAGE_ORDER,
            [spec.key for spec in readiness.STAGES],
        )

    def test_exact_causal_and_curve_boundary_remains_pre_outcome(self) -> None:
        rows = {row["key"]: row for row in preflight.STAGE_CONTRACT}
        for key in (
            "g16_exact_partition_replay_authorization",
            "g16_exact_causal",
            "g16_prepared_causal_authorization",
            "g16_counterfactual_causal_authorization",
            compiler.G16_EXACT_COUNTERFACTUAL_CAUSAL_STAGE,
            "g16_prepared_curve_authorization",
            "g16_counterfactual_curve_authorization",
        ):
            self.assertTrue(rows[key]["pre_outcome"])

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
        self.assertEqual(
            arm_receipt["armed_plan_fingerprint"], armed["fingerprint"]
        )


if __name__ == "__main__":
    unittest.main()
