from __future__ import annotations

import unittest
from unittest import mock

import ng_corpus_executor_pipeline_arm_v10 as arm
import ng_corpus_executor_plan_compiler_v10 as compiler
import ng_historical_refinement_executor_v11 as executor
import ng_historical_refinement_preflight_v11 as preflight
import ng_historical_refinement_readiness_v14 as readiness


class ReadinessV14ExecutionChainTests(unittest.TestCase):
    def _minimal_plan(self) -> dict:
        stages = []
        for spec in readiness.STAGES:
            stages.append(
                {
                    "key": spec.key,
                    "enabled": False,
                    "requires_fixed_outcomes": not spec.pre_outcome,
                }
            )
        return {"stages": stages}

    def test_executor_uses_readiness_v14(self) -> None:
        self.assertEqual(readiness.SCHEMA, "ng_historical_refinement_readiness.v14")
        with executor._v14_context():
            self.assertIs(executor.legacy_executor.readiness, readiness)

    def test_executor_exposes_lock_attestation_entrypoint(self) -> None:
        self.assertEqual(
            executor.SUGGESTED_ENTRYPOINTS["g16_exact_lock_context_compilation"],
            ("python", "ng_g16_exact_context_compilation_gate.py", "lock"),
        )

    def test_executor_exposes_publication_attestation_entrypoint(self) -> None:
        self.assertEqual(
            executor.SUGGESTED_ENTRYPOINTS[
                "g16_exact_publication_context_compilation"
            ],
            ("python", "ng_g16_exact_context_compilation_gate.py", "complete"),
        )

    def test_attestations_surround_publication_boundary(self) -> None:
        keys = [spec.key for spec in readiness.STAGES]
        lock = keys.index("g16_counterfactual_curve_lock")
        lock_attestation = keys.index("g16_exact_lock_context_compilation")
        publication = keys.index("g16_counterfactual_publication")
        publication_attestation = keys.index(
            "g16_exact_publication_context_compilation"
        )
        self.assertLess(lock, lock_attestation)
        self.assertLess(lock_attestation, publication)
        self.assertLess(publication, publication_attestation)

    def test_compiler_accepts_exact_v14_boundary(self) -> None:
        plan = self._minimal_plan()
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            rows = compiler._validate_v14_boundary(plan)
        self.assertIn(compiler.G16_LOCK_ATTESTATION_STAGE, rows)
        self.assertIn(compiler.G16_PUBLICATION_ATTESTATION_STAGE, rows)

    def test_compiler_rejects_missing_lock_attestation(self) -> None:
        plan = self._minimal_plan()
        plan["stages"] = [
            row
            for row in plan["stages"]
            if row["key"] != compiler.G16_LOCK_ATTESTATION_STAGE
        ]
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            with self.assertRaises(compiler.CorpusExecutorPlanCompilerV10Error):
                compiler._validate_v14_boundary(plan)

    def test_compiler_rejects_lock_attestation_after_outcomes(self) -> None:
        plan = self._minimal_plan()
        for row in plan["stages"]:
            if row["key"] == compiler.G16_LOCK_ATTESTATION_STAGE:
                row["requires_fixed_outcomes"] = True
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            with self.assertRaises(compiler.CorpusExecutorPlanCompilerV10Error):
                compiler._validate_v14_boundary(plan)

    def test_compiler_rejects_publication_attestation_before_outcomes(self) -> None:
        plan = self._minimal_plan()
        for row in plan["stages"]:
            if row["key"] == compiler.G16_PUBLICATION_ATTESTATION_STAGE:
                row["requires_fixed_outcomes"] = False
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            with self.assertRaises(compiler.CorpusExecutorPlanCompilerV10Error):
                compiler._validate_v14_boundary(plan)

    def test_compiler_rejects_premature_attestation_activation(self) -> None:
        plan = self._minimal_plan()
        for row in plan["stages"]:
            if row["key"] == compiler.G16_LOCK_ATTESTATION_STAGE:
                row["enabled"] = True
        with mock.patch.object(compiler.executor, "validate_plan", return_value=None):
            with self.assertRaises(compiler.CorpusExecutorPlanCompilerV10Error):
                compiler._validate_v14_boundary(plan)

    def test_preflight_contract_is_v14(self) -> None:
        self.assertEqual(preflight.READINESS_CONTRACT, readiness.SCHEMA)
        self.assertEqual(
            preflight.EXECUTOR_CONTRACT,
            "ng_historical_refinement_executor_v11",
        )
        self.assertEqual(preflight.STAGE_ORDER, [spec.key for spec in readiness.STAGES])

    def test_no_options_entrypoint_is_added(self) -> None:
        self.assertFalse(
            any("option" in key.lower() for key in executor.SUGGESTED_ENTRYPOINTS)
        )

    def test_permanent_authority_wall(self) -> None:
        values = readiness._linked_fixture_chain()
        for key in (
            "g16_exact_lock_context_compilation",
            "g16_exact_publication_context_compilation",
        ):
            value = values[key]
            self.assertFalse(value["random_shuffle_used"])
            self.assertTrue(value["one_signal_authority_preserved"])
            self.assertTrue(value["blind_forecasts_immutable"])
            self.assertFalse(value["may_update_ng_brain"])
            self.assertFalse(value["execution_authority"])
            self.assertEqual(value["cme_event_contracts_mode"], "SHADOW")
            self.assertEqual(value["brokerage_contract"], "tastytrade_not_ibkr")
            self.assertFalse(value["options_lane_started"])

    def test_attestation_output_names_are_canonical(self) -> None:
        specs = {spec.key: spec for spec in readiness.STAGES}
        self.assertEqual(
            specs["g16_exact_lock_context_compilation"].filename,
            "g16_exact_lock_context_compilation_attestation.json",
        )
        self.assertEqual(
            specs["g16_exact_publication_context_compilation"].filename,
            "g16_exact_publication_context_compilation_attestation.json",
        )

    def test_arm_keeps_attestations_outside_corpus_prefix(self) -> None:
        self.assertNotIn(arm.G16_LOCK_ATTESTATION_STAGE, arm.ARMED_STAGES)
        self.assertNotIn(arm.G16_PUBLICATION_ATTESTATION_STAGE, arm.ARMED_STAGES)


if __name__ == "__main__":
    unittest.main()
