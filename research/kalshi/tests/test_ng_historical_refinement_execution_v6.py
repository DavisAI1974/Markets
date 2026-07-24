from __future__ import annotations

import copy
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import ng_corpus_executor_pipeline_arm_v3 as arm
import ng_corpus_executor_plan_compiler as fingerprinting
import ng_corpus_executor_plan_compiler_v3 as compiler
import ng_historical_refinement_executor_v4 as executor
import ng_historical_refinement_preflight as legacy_preflight
import ng_historical_refinement_preflight_v4 as preflight
import ng_historical_refinement_readiness_v6 as readiness


class HistoricalRefinementExecutionV6Tests(unittest.TestCase):
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

    def _base_preflight(self, plan: dict, *, stage: str = "broad_corpus_exact_overlap") -> dict:
        value = {
            "schema": legacy_preflight.SCHEMA,
            "status": "PREFLIGHT_PASSED",
            "plan_fingerprint": plan["fingerprint"],
            "executor_result": {"status": "CONFIGURATION_REQUIRED", "stage": stage},
            "pre_alignment_gate": {"status": "ALIGNED"},
            "post_alignment_gate": {"status": "ALIGNED"},
            "blockers": [],
            "stand_downs": [],
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_forecasts_immutable": True,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
        }
        value["fingerprint"] = legacy_preflight._fingerprint(value)
        return value

    def test_executor_uses_readiness_v6_and_overlap_entrypoint(self) -> None:
        self.assertEqual(readiness.SCHEMA, "ng_historical_refinement_readiness.v6")
        self.assertEqual(
            executor.SUGGESTED_ENTRYPOINTS["broad_corpus_exact_overlap"],
            ("python", "ng_broad_corpus_exact_overlap_gate.py"),
        )
        order = [spec.key for spec in readiness.STAGES]
        self.assertLess(order.index("broad_corpus_scope"), order.index("broad_corpus_exact_overlap"))
        self.assertLess(order.index("broad_corpus_exact_overlap"), order.index("g15_exact_replay"))

    def test_executor_plan_contains_exact_overlap_before_g15(self) -> None:
        root = self._root()
        plan = executor.build_plan(root / "artifacts", root / "work")
        executor.validate_plan(plan)
        keys = [row["key"] for row in plan["stages"]]
        self.assertEqual(keys, [spec.key for spec in readiness.STAGES])
        self.assertLess(keys.index("broad_corpus_exact_overlap"), keys.index("g15_exact_replay"))

    def test_readiness_v5_plan_is_rejected(self) -> None:
        root = self._root()
        plan = executor.build_plan(root / "artifacts", root / "work")
        plan["stages"] = [row for row in plan["stages"] if row["key"] != "broad_corpus_exact_overlap"]
        plan.pop("fingerprint")
        plan["fingerprint"] = executor.legacy_executor._fingerprint(plan)
        with self.assertRaises(Exception):
            executor.validate_plan(plan)

    def test_compiler_configures_five_pre_outcome_stages(self) -> None:
        plan, receipt, commands = self._compiled()
        self.assertEqual(receipt["configured_stages"], list(compiler.CONFIGURED_STAGES))
        self.assertEqual(len(compiler.CONFIGURED_STAGES), 5)
        rows = {row["key"]: row for row in plan["stages"]}
        self.assertTrue(rows["corpus_coverage"]["enabled"])
        for key in compiler.CONFIGURED_STAGES[1:]:
            self.assertFalse(rows[key]["enabled"])
        for key in compiler.CONFIGURED_STAGES:
            self.assertFalse(rows[key]["requires_fixed_outcomes"])
        self.assertEqual(rows["broad_corpus_exact_overlap"]["argv"], commands["broad_corpus_exact_overlap"])

    def test_overlap_command_is_bound_to_broad_scope_output(self) -> None:
        plan, _, _ = self._compiled()
        row = next(row for row in plan["stages"] if row["key"] == "broad_corpus_exact_overlap")
        argv = row["argv"]
        self.assertIn("--broad-scope-gate", argv)
        self.assertIn("ng_broad_corpus_scope_gate.json", " ".join(argv))
        self.assertIn("ng_broad_corpus_exact_overlap_gate.json", " ".join(argv))

    def test_compiler_rejects_overlap_command_substitution(self) -> None:
        plan, receipt, commands = self._compiled()
        tampered = copy.deepcopy(plan)
        row = next(row for row in tampered["stages"] if row["key"] == "broad_corpus_exact_overlap")
        row["argv"][-1] = "/tmp/replacement.json"
        tampered.pop("fingerprint")
        tampered["fingerprint"] = executor.legacy_executor._fingerprint(tampered)
        with self.assertRaises(Exception):
            compiler.validate_receipt(receipt, plan=tampered, commands=commands)

    def test_compiler_rejects_refingerprinted_overlap_requirement_removal(self) -> None:
        plan, receipt, commands = self._compiled()
        changed = copy.deepcopy(receipt)
        changed["broad_corpus_exact_overlap_gate_required"] = False
        changed.pop("fingerprint")
        changed["fingerprint"] = fingerprinting._fp(changed)
        with self.assertRaises(compiler.CorpusExecutorPlanCompilerV3Error):
            compiler.validate_receipt(changed, plan=plan, commands=commands)

    def test_arm_enables_only_five_corpus_stages(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        rows = {row["key"]: row for row in armed["stages"]}
        for key in arm.ARMED_STAGES:
            self.assertTrue(rows[key]["enabled"])
        for spec in readiness.STAGES[len(arm.ARMED_STAGES) :]:
            self.assertFalse(rows[spec.key]["enabled"])
        self.assertEqual(arm_receipt["stage_order_prefix"], list(arm.ARMED_STAGES))
        self.assertTrue(arm_receipt["broad_exact_overlap_gate_armed_before_g15"])

    def test_arm_preserves_stable_deterministic_plan(self) -> None:
        plan, receipt, _ = self._compiled()
        first_plan, first_receipt = arm.build_armed_plan(plan, receipt)
        second_plan, second_receipt = arm.build_armed_plan(plan, receipt)
        self.assertEqual(first_plan, second_plan)
        self.assertEqual(first_receipt, second_receipt)

    def test_arm_rejects_refingerprinted_options_escalation(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        changed = copy.deepcopy(arm_receipt)
        changed["options_lane_started"] = True
        changed.pop("fingerprint")
        changed["fingerprint"] = fingerprinting._fp(changed)
        with self.assertRaises(arm.CorpusExecutorPipelineArmV3Error):
            arm.validate_arm_receipt(
                changed,
                compiled_plan=plan,
                compiler_receipt=receipt,
                armed_plan=armed,
            )

    def test_preflight_contract_is_readiness_v6(self) -> None:
        self.assertEqual(preflight.READINESS_CONTRACT, readiness.SCHEMA)
        self.assertEqual(preflight.EXECUTOR_CONTRACT, "ng_historical_refinement_executor_v4")
        self.assertLess(
            preflight.STAGE_ORDER.index("broad_corpus_scope"),
            preflight.STAGE_ORDER.index("broad_corpus_exact_overlap"),
        )
        self.assertLess(
            preflight.STAGE_ORDER.index("broad_corpus_exact_overlap"),
            preflight.STAGE_ORDER.index("g15_exact_replay"),
        )

    def test_preflight_embeds_and_validates_exact_overlap_plan(self) -> None:
        root = self._root()
        plan = executor.build_plan(root / "artifacts", root / "work")
        base = self._base_preflight(plan)
        with mock.patch.object(legacy_preflight, "validate_receipt", return_value=None):
            result = preflight._finalize(plan, base)
        self.assertTrue(result["execution_plan_v6_validated"])
        self.assertTrue(result["broad_corpus_scope_required"])
        self.assertTrue(result["broad_corpus_exact_overlap_required"])
        self.assertEqual(result["execution_plan_snapshot"], plan)

    def test_preflight_rejects_refingerprinted_overlap_requirement_removal(self) -> None:
        root = self._root()
        plan = executor.build_plan(root / "artifacts", root / "work")
        base = self._base_preflight(plan)
        with mock.patch.object(legacy_preflight, "validate_receipt", return_value=None):
            result = preflight._finalize(plan, base)
        result["broad_corpus_exact_overlap_required"] = False
        result.pop("fingerprint")
        result["fingerprint"] = legacy_preflight._fingerprint(result)
        with self.assertRaises(preflight.HistoricalRefinementPreflightV4Error):
            preflight.validate_receipt(result)

    def test_preflight_rejects_unknown_executor_stage(self) -> None:
        root = self._root()
        plan = executor.build_plan(root / "artifacts", root / "work")
        base = self._base_preflight(plan)
        with mock.patch.object(legacy_preflight, "validate_receipt", return_value=None):
            result = preflight._finalize(plan, base)
        result["executor_result"]["stage"] = "options_implementation"
        result.pop("fingerprint")
        result["fingerprint"] = legacy_preflight._fingerprint(result)
        with self.assertRaises(preflight.HistoricalRefinementPreflightV4Error):
            preflight.validate_receipt(result)

    def test_permanent_authority_contract(self) -> None:
        plan, receipt, _ = self._compiled()
        armed, arm_receipt = arm.build_armed_plan(plan, receipt)
        self.assertFalse(receipt["actual_outcomes_used"])
        self.assertFalse(receipt["paid_live_data_assumed"])
        self.assertFalse(receipt["random_shuffle_used"])
        self.assertTrue(receipt["blind_forecasts_immutable"])
        self.assertFalse(receipt["may_update_ng_brain"])
        self.assertFalse(receipt["execution_authority"])
        self.assertEqual(receipt["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(receipt["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(receipt["options_lane_started"])
        self.assertEqual(arm_receipt["armed_plan_fingerprint"], armed["fingerprint"])


if __name__ == "__main__":
    unittest.main()
