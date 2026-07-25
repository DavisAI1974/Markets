from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

import ng_corpus_executor_pipeline_arm_v11 as arm
import ng_corpus_executor_plan_compiler_v11 as compiler
import ng_historical_refinement_executor_v12 as executor
import ng_historical_refinement_readiness_v15 as readiness


class CorpusExecutionV15Tests(unittest.TestCase):
    def _commands(self) -> dict[str, list[str]]:
        return compiler._commands(
            Path("renders/ng_refine_s95"),
            Path("renders/ng_refine_s95/ng_target_day_slice_bundle.json"),
            Path("renders/ng_refine_s95/ng_corpus_inspection_plan.json"),
        )

    def _minimal_plan(self) -> dict:
        commands = self._commands()
        rows = []
        for spec in readiness.STAGES:
            rows.append(
                {
                    "key": spec.key,
                    "enabled": False,
                    "requires_fixed_outcomes": not spec.pre_outcome,
                    "argv": list(commands.get(spec.key) or []),
                }
            )
        return {"stages": rows}

    def test_compiler_targets_readiness_v15(self) -> None:
        self.assertEqual(compiler.SCHEMA, "ng_corpus_executor_plan_compiler.v11")
        self.assertEqual(readiness.SCHEMA, "ng_historical_refinement_readiness.v15")
        with compiler._v15_context():
            self.assertIs(compiler.v10.readiness, readiness)
            self.assertIs(compiler.v10.executor, executor)
            self.assertEqual(compiler.v6.CONFIGURED_STAGES, compiler.CONFIGURED_STAGES)

    def test_definition_byte_binding_is_second_configured_stage(self) -> None:
        self.assertEqual(
            compiler.CONFIGURED_STAGES,
            (
                "corpus_coverage",
                "corpus_definition_byte_binding",
                "basis_inventory_regeneration",
                "replay_catalog_export",
                "broad_corpus_scope",
                "broad_corpus_exact_overlap",
                "broad_corpus_exact_partition",
            ),
        )
        keys = [spec.key for spec in readiness.STAGES]
        self.assertEqual(list(compiler.CONFIGURED_STAGES), keys[:7])

    def test_binding_command_uses_canonical_receipts_and_output(self) -> None:
        argv = self._commands()[compiler.DEFINITION_BYTE_BINDING_STAGE]
        self.assertEqual(
            argv[:3],
            ["python", "ng_corpus_definition_byte_binding_gate.py", "build"],
        )
        self.assertTrue(argv[4].endswith("ng_corpus_inventory_plan_compiler.json"))
        self.assertTrue(argv[6].endswith("ng_corpus_inspection_receipt.json"))
        self.assertTrue(argv[8].endswith("ng_corpus_definition_byte_binding_gate.json"))

    def test_compiler_accepts_exact_v15_boundary(self) -> None:
        plan = self._minimal_plan()
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            rows = compiler._validate_v15_boundary(plan, self._commands())
        self.assertIn(compiler.DEFINITION_BYTE_BINDING_STAGE, rows)

    def test_compiler_rejects_missing_binding_stage(self) -> None:
        plan = self._minimal_plan()
        plan["stages"] = [
            row
            for row in plan["stages"]
            if row["key"] != compiler.DEFINITION_BYTE_BINDING_STAGE
        ]
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            with self.assertRaises(compiler.CorpusExecutorPlanCompilerV11Error):
                compiler._validate_v15_boundary(plan, self._commands())

    def test_compiler_rejects_premature_binding_activation(self) -> None:
        plan = self._minimal_plan()
        for row in plan["stages"]:
            if row["key"] == compiler.DEFINITION_BYTE_BINDING_STAGE:
                row["enabled"] = True
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            with self.assertRaises(compiler.CorpusExecutorPlanCompilerV11Error):
                compiler._validate_v15_boundary(plan, self._commands())

    def test_compiler_rejects_post_outcome_binding(self) -> None:
        plan = self._minimal_plan()
        for row in plan["stages"]:
            if row["key"] == compiler.DEFINITION_BYTE_BINDING_STAGE:
                row["requires_fixed_outcomes"] = True
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            with self.assertRaises(compiler.CorpusExecutorPlanCompilerV11Error):
                compiler._validate_v15_boundary(plan, self._commands())

    def test_compiler_rejects_binding_command_substitution(self) -> None:
        plan = self._minimal_plan()
        for row in plan["stages"]:
            if row["key"] == compiler.DEFINITION_BYTE_BINDING_STAGE:
                row["argv"] = ["python", "wrong.py"]
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            with self.assertRaises(compiler.CorpusExecutorPlanCompilerV11Error):
                compiler._validate_v15_boundary(plan, self._commands())

    def test_arm_uses_exact_seven_stage_prefix(self) -> None:
        self.assertEqual(arm.ARMED_STAGES, compiler.CONFIGURED_STAGES)
        keys = [spec.key for spec in readiness.STAGES]
        self.assertEqual(list(arm.ARMED_STAGES), keys[:7])
        with arm._v15_context():
            self.assertEqual(arm.v6.ARMED_STAGES, arm.ARMED_STAGES)
            self.assertIs(arm.v10.compiler, compiler)
            self.assertIs(arm.v10.readiness, readiness)

    def test_arm_receipt_rejects_refingerprinted_binding_summary(self) -> None:
        value = {
            "schema": arm.SCHEMA,
            "status": arm.STATUS,
            "pipeline_arm_v10_fingerprint": "base",
            "readiness_contract": readiness.SCHEMA,
            "readiness_stage_contract_fingerprint": compiler.fingerprinting._fp(
                [spec.key for spec in readiness.STAGES]
            ),
            "seven_stage_corpus_prefix_armed": True,
            "corpus_definition_byte_binding_required_before_basis_regeneration": True,
            "corpus_definition_byte_binding_stage_present": True,
            "corpus_definition_byte_binding_stage_enabled": False,
            "corpus_definition_byte_binding_stage_pre_outcome": True,
            "inspection_only_route_rejected": True,
            "after_corpus_coverage": "RUN_DEFINITION_BYTE_BINDING_BEFORE_BASIS_REGENERATION",
            "after_corpus_definition_byte_binding": "RUN_BASIS_REGENERATION_ONLY_IF_DEFINITION_BYTES_BOUND",
        }
        value["fingerprint"] = compiler.fingerprinting._fp(value)
        with self.assertRaises(arm.CorpusExecutorPipelineArmV11Error):
            arm.validate_arm_receipt(
                value,
                compiled_plan={},
                compiler_receipt={},
                armed_plan={},
            )

    def test_permanent_authority_wall_and_no_options(self) -> None:
        gate = readiness._linked_fixture_chain()["corpus_definition_byte_binding"]
        for field in (
            "actual_outcomes_used",
            "paid_live_data_assumed",
            "random_shuffle_used",
            "may_change_blind_forecast",
            "may_change_posterior",
            "may_update_ng_brain",
            "execution_authority",
            "options_lane_started",
        ):
            self.assertFalse(gate[field])
        self.assertTrue(gate["one_signal_authority_preserved"])
        self.assertTrue(gate["blind_forecasts_immutable"])
        self.assertEqual(gate["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(gate["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(
            any("option" in key.lower() for key in executor.SUGGESTED_ENTRYPOINTS)
        )


if __name__ == "__main__":
    unittest.main()
