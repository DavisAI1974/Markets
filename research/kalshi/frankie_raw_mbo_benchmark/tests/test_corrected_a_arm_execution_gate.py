from __future__ import annotations

import copy
import unittest

from research.kalshi.frankie_raw_mbo_benchmark.corrected_a_arm_execution_gate_20260828 import (
    CorrectedExecutionGateError,
    canonical_hash,
    validate_first_lock_and_freeze,
    validate_principal_execution,
    validate_rt_surface_inventory,
)


SHA = "a" * 64
OTHER_SHA = "b" * 64


def surface_inventory() -> dict[str, object]:
    ids = [
        "candidate_contradiction_memory",
        "causal_history_all_scales",
        "current_brain_and_learned_knowledge",
        "current_causal_operating_state",
        "day_specific_forecast_context",
        "forecast_scenarios_and_disconfirmers",
        "frozen_rt_state",
        "full_bigsuite",
        "full_raw_mbo_events",
        "full_source_catalog_and_availability",
        "fundamentals_and_storage",
        "historical_analogs_and_calibration",
        "market_mechanics_state",
        "power_stack_and_generation",
        "provisional_capabilities",
        "rt_on_demand_evidence_scout",
        "selected_exemplars_falsifiers_negatives",
        "source_integrity_and_clocks",
        "step1_revealed_retrospective_evidence",
        "step1_structural_census_methodology",
        "structure_lifecycle",
        "synchronized_curve_and_roll",
        "top20_book_and_fifo",
        "weather_forward_forcing",
    ]
    rows = []
    required = {
        "current_causal_operating_state",
        "full_raw_mbo_events",
        "full_source_catalog_and_availability",
        "market_mechanics_state",
        "source_integrity_and_clocks",
        "structure_lifecycle",
        "top20_book_and_fifo",
    }
    for surface_id in ids:
        if surface_id == "step1_revealed_retrospective_evidence":
            rows.append(
                {
                    "surface_id": surface_id,
                    "route": "SEALED",
                    "availability": "SEALED",
                    "required_for_principal": False,
                    "model_visible": False,
                    "evidence_receipt_sha256": None,
                }
            )
        elif surface_id == "frozen_rt_state":
            rows.append(
                {
                    "surface_id": surface_id,
                    "route": "PENDING",
                    "availability": "PENDING",
                    "required_for_principal": False,
                    "model_visible": False,
                    "evidence_receipt_sha256": None,
                }
            )
        else:
            is_required = surface_id in required
            rows.append(
                {
                    "surface_id": surface_id,
                    "route": "DIRECT" if is_required else "TOOL_ACCESSIBLE",
                    "availability": "AVAILABLE" if is_required else "UNKNOWN",
                    "required_for_principal": is_required,
                    "model_visible": is_required,
                    "evidence_receipt_sha256": SHA if is_required else None,
                }
            )
    value = {
        "schema": "FRANKIE_NATIVE_RAW_MBO_RT_SURFACE_INVENTORY_V1",
        "arm": "A_MEMORY",
        "role": "REAL_TIME_FRANKIE",
        "surfaces": rows,
        "inventory_hash": "",
    }
    value["inventory_hash"] = canonical_hash(value, omit="inventory_hash")
    return value


def principal_execution() -> dict[str, object]:
    value = {
        "schema": "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_EXECUTION_V1",
        "run_id": "corrected-a-memory-1",
        "arm": "A_MEMORY",
        "role": "REAL_TIME_FRANKIE",
        "provider": "provider",
        "requested_model": "frankie-requested",
        "served_model": "frankie-served",
        "principal_invocation_id": "invocation-1",
        "actual_principal_invocation": True,
        "controller_only": False,
        "profile_id": "RT_A_MEMORY_SECOND_PASS",
        "mission_sha256": SHA,
        "calculation_contract_sha256": SHA,
        "knowledge_manifest_hash": SHA,
        "context_bundle_sha256": SHA,
        "model_visible_context_sha256": SHA,
        "serialized_principal_input_sha256": SHA,
        "knowledge_use_receipt_sha256": SHA,
        "surface_inventory_hash": SHA,
        "calculation_receipt_sha256": SHA,
        "pre_call_checkpoint_hash": SHA,
        "post_call_checkpoint_hash": OTHER_SHA,
        "usage": {
            "input_tokens": 100,
            "output_tokens": 20,
            "total_tokens": 120,
            "provider_usage_receipt_sha256": SHA,
        },
        "response": {
            "response_id": "response-1",
            "response_sha256": SHA,
            "output_sha256": OTHER_SHA,
            "analysis_author": "REAL_TIME_FRANKIE",
        },
        "execution_receipt_hash": "",
    }
    value["execution_receipt_hash"] = canonical_hash(
        value, omit="execution_receipt_hash"
    )
    return value


class CorrectedAArmExecutionGateTests(unittest.TestCase):
    def test_accepts_complete_open_world_rt_surface_inventory(self) -> None:
        receipt = validate_rt_surface_inventory(surface_inventory(), arm="A_MEMORY")
        self.assertEqual(receipt["surface_count"], 24)
        self.assertTrue(receipt["step1_sealed"])
        self.assertTrue(receipt["native_full_mbo_available"])

    def test_rejects_missing_surface_identity(self) -> None:
        value = surface_inventory()
        value["surfaces"] = value["surfaces"][:-1]
        value["inventory_hash"] = canonical_hash(value, omit="inventory_hash")
        with self.assertRaisesRegex(CorrectedExecutionGateError, "24 exact surface"):
            validate_rt_surface_inventory(value, arm="A_MEMORY")

    def test_rejects_required_native_surface_marked_dormant(self) -> None:
        value = surface_inventory()
        row = next(
            row for row in value["surfaces"] if row["surface_id"] == "full_raw_mbo_events"
        )
        row.update(route="DORMANT", availability="UNAVAILABLE", model_visible=False)
        value["inventory_hash"] = canonical_hash(value, omit="inventory_hash")
        with self.assertRaisesRegex(CorrectedExecutionGateError, "required surface"):
            validate_rt_surface_inventory(value, arm="A_MEMORY")

    def test_rejects_step1_visibility(self) -> None:
        value = surface_inventory()
        row = next(
            row
            for row in value["surfaces"]
            if row["surface_id"] == "step1_revealed_retrospective_evidence"
        )
        row.update(route="DIRECT", availability="AVAILABLE", model_visible=True)
        value["inventory_hash"] = canonical_hash(value, omit="inventory_hash")
        with self.assertRaisesRegex(CorrectedExecutionGateError, "Step-1"):
            validate_rt_surface_inventory(value, arm="A_MEMORY")

    def test_accepts_fully_bound_actual_principal_execution(self) -> None:
        value = principal_execution()
        receipt = validate_principal_execution(
            value,
            expected_arm="A_MEMORY",
            expected_role="REAL_TIME_FRANKIE",
            expected_mission_sha256=SHA,
            expected_calculation_contract_sha256=SHA,
            expected_surface_inventory_hash=SHA,
        )
        self.assertEqual(receipt["response_output_sha256"], OTHER_SHA)

    def test_rejects_controller_only_execution(self) -> None:
        value = principal_execution()
        value["actual_principal_invocation"] = False
        value["controller_only"] = True
        value["execution_receipt_hash"] = canonical_hash(
            value, omit="execution_receipt_hash"
        )
        with self.assertRaisesRegex(CorrectedExecutionGateError, "principal invocation"):
            validate_principal_execution(
                value,
                expected_arm="A_MEMORY",
                expected_role="REAL_TIME_FRANKIE",
                expected_mission_sha256=SHA,
                expected_calculation_contract_sha256=SHA,
                expected_surface_inventory_hash=SHA,
            )

    def test_rejects_missing_or_zero_usage(self) -> None:
        value = principal_execution()
        value["usage"]["input_tokens"] = 0
        value["usage"]["total_tokens"] = 20
        value["execution_receipt_hash"] = canonical_hash(
            value, omit="execution_receipt_hash"
        )
        with self.assertRaisesRegex(CorrectedExecutionGateError, "token usage"):
            validate_principal_execution(
                value,
                expected_arm="A_MEMORY",
                expected_role="REAL_TIME_FRANKIE",
                expected_mission_sha256=SHA,
                expected_calculation_contract_sha256=SHA,
                expected_surface_inventory_hash=SHA,
            )

    def test_rejects_mission_or_surface_drift(self) -> None:
        value = principal_execution()
        with self.assertRaisesRegex(CorrectedExecutionGateError, "mission"):
            validate_principal_execution(
                value,
                expected_arm="A_MEMORY",
                expected_role="REAL_TIME_FRANKIE",
                expected_mission_sha256=OTHER_SHA,
                expected_calculation_contract_sha256=SHA,
                expected_surface_inventory_hash=SHA,
            )

    def test_first_lock_and_freeze_must_bind_principal_output(self) -> None:
        execution = principal_execution()
        first_lock = {
            "schema": "FRANKIE_NATIVE_RAW_MBO_RT_FIRST_LOCK_V1",
            "run_id": execution["run_id"],
            "execution_receipt_hash": execution["execution_receipt_hash"],
            "principal_response_id": execution["response"]["response_id"],
            "principal_output_sha256": execution["response"]["output_sha256"],
            "output_validation_receipt_sha256": SHA,
            "principal_output_locked": True,
            "controller_summary_locked": False,
            "first_lock_hash": "",
        }
        first_lock["first_lock_hash"] = canonical_hash(first_lock, omit="first_lock_hash")
        freeze = {
            "schema": "FRANKIE_NATIVE_RAW_MBO_RT_FREEZE_V1",
            "run_id": execution["run_id"],
            "first_lock_hash": first_lock["first_lock_hash"],
            "principal_output_sha256": execution["response"]["output_sha256"],
            "one_way_handoff_not_yet_created": True,
            "freeze_hash": "",
        }
        freeze["freeze_hash"] = canonical_hash(freeze, omit="freeze_hash")
        receipt = validate_first_lock_and_freeze(execution, first_lock, freeze)
        self.assertEqual(receipt["locked_output_sha256"], OTHER_SHA)

    def test_rejects_controller_summary_lock(self) -> None:
        execution = principal_execution()
        first_lock = {
            "schema": "FRANKIE_NATIVE_RAW_MBO_RT_FIRST_LOCK_V1",
            "run_id": execution["run_id"],
            "execution_receipt_hash": execution["execution_receipt_hash"],
            "principal_response_id": execution["response"]["response_id"],
            "principal_output_sha256": execution["response"]["output_sha256"],
            "output_validation_receipt_sha256": SHA,
            "principal_output_locked": False,
            "controller_summary_locked": True,
            "first_lock_hash": "",
        }
        first_lock["first_lock_hash"] = canonical_hash(first_lock, omit="first_lock_hash")
        freeze = {
            "schema": "FRANKIE_NATIVE_RAW_MBO_RT_FREEZE_V1",
            "run_id": execution["run_id"],
            "first_lock_hash": first_lock["first_lock_hash"],
            "principal_output_sha256": execution["response"]["output_sha256"],
            "one_way_handoff_not_yet_created": True,
            "freeze_hash": "",
        }
        freeze["freeze_hash"] = canonical_hash(freeze, omit="freeze_hash")
        with self.assertRaisesRegex(CorrectedExecutionGateError, "controller summary"):
            validate_first_lock_and_freeze(execution, first_lock, freeze)


if __name__ == "__main__":
    unittest.main()
