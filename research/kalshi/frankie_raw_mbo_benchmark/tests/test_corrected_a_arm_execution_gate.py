from __future__ import annotations

import copy
import unittest

from research.kalshi.frankie_raw_mbo_benchmark.corrected_a_arm_execution_gate_20260828 import (
    SURFACE_IDS,
    CorrectedExecutionGateError,
    canonical_hash,
    validate_first_lock_and_freeze,
    validate_principal_execution,
    validate_rt_surface_inventory,
)


SHA = "a" * 64
OTHER_SHA = "b" * 64


def surface_inventory() -> dict[str, object]:
    from research.kalshi.frankie_raw_mbo_benchmark.corrected_a_arm_execution_gate_20260828 import (
        MANDATORY_NATIVE_RT_SURFACES,
        SEALED_SURFACES,
        SURFACE_IDS,
    )

    rows = []
    for surface_id in sorted(SURFACE_IDS):
        if surface_id in SEALED_SURFACES:
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
            continue
        is_required = surface_id in MANDATORY_NATIVE_RT_SURFACES
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


def _expected() -> dict[str, object]:
    return {
        "expected_arm": "A_MEMORY",
        "expected_role": "REAL_TIME_FRANKIE",
        "expected_mission_sha256": SHA,
        "expected_calculation_contract_sha256": SHA,
        "expected_surface_inventory_hash": SHA,
    }


def principal_execution() -> dict[str, object]:
    value = {
        "schema": "FRANKIE_NATIVE_RAW_MBO_PRINCIPAL_EXECUTION_V1",
        "run_id": "corrected-a-memory-1",
        "arm": "A_MEMORY",
        "role": "REAL_TIME_FRANKIE",
        "principal": "gpt-5.6-sol",
        "spawn_request_path": "forecasts/frankie/spawn_request_0001.json",
        "spawn_request_sha256": SHA,
        "principal_artifact_path": "forecasts/frankie/principal_findings_0001.json",
        "principal_artifact_sha256": OTHER_SHA,
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
        "artifact": {
            "artifact_path": "forecasts/frankie/principal_findings_0001.json",
            "artifact_sha256": OTHER_SHA,
            "findings_sha256": SHA,
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
        self.assertEqual(receipt["surface_count"], len(SURFACE_IDS))
        self.assertTrue(receipt["step1_sealed"])
        self.assertTrue(receipt["native_full_mbo_available"])

    def test_rejects_missing_surface_identity(self) -> None:
        value = surface_inventory()
        value["surfaces"] = value["surfaces"][:-1]
        value["inventory_hash"] = canonical_hash(value, omit="inventory_hash")
        with self.assertRaisesRegex(CorrectedExecutionGateError, f"{len(SURFACE_IDS)} exact surface"):
            validate_rt_surface_inventory(value, arm="A_MEMORY")

    def test_rejects_required_native_surface_marked_dormant(self) -> None:
        value = surface_inventory()
        row = next(
            row for row in value["surfaces"] if row["surface_id"] == "aggressor_and_native_signed_flow"
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
            if row["surface_id"] == "step1_populations"
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
        self.assertEqual(receipt["principal_findings_sha256"], SHA)

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

    def test_rejects_an_artifact_that_is_its_own_request(self) -> None:
        # A run that returned its own input produced no findings. There is no provider to
        # attest anything in an agent-session run, so this identity IS the proof.
        value = principal_execution()
        value["principal_artifact_sha256"] = value["spawn_request_sha256"]
        value["artifact"]["artifact_sha256"] = value["spawn_request_sha256"]
        value["execution_receipt_hash"] = canonical_hash(value, omit="execution_receipt_hash")
        with self.assertRaisesRegex(CorrectedExecutionGateError, "returned its own input"):
            validate_principal_execution(
                value, **_expected())

    def test_rejects_an_artifact_block_naming_a_different_path(self) -> None:
        value = principal_execution()
        value["artifact"]["artifact_path"] = "forecasts/frankie/somewhere_else.json"
        value["execution_receipt_hash"] = canonical_hash(value, omit="execution_receipt_hash")
        with self.assertRaisesRegex(CorrectedExecutionGateError, "different paths"):
            validate_principal_execution(value, **_expected())

    def test_a_missing_artifact_hash_is_refused(self) -> None:
        # The file-based replacement for the old zero-token-usage check. A run with no
        # artifact hash is a run with nothing to bind to, which is not a run.
        value = principal_execution()
        value["principal_artifact_sha256"] = ""
        value["execution_receipt_hash"] = canonical_hash(
            value, omit="execution_receipt_hash"
        )
        with self.assertRaises(CorrectedExecutionGateError):
            validate_principal_execution(value, **_expected())

    def test_a_provider_shaped_execution_record_is_REFUSED(self) -> None:
        """The regression guard for the correction that kept having to be repeated.

        The gate used to REQUIRE `provider`, `served_model`, `principal_invocation_id` and
        reconciling token `usage`. In an agent-session run none of those exist, so the check
        rejected the correct procedure and admitted only an API run. This pins the reverse:
        an API-shaped record is now refused outright, so the old architecture cannot quietly
        return through a record that still carries it.
        """
        value = principal_execution()
        value["provider"] = "openai"
        value["usage"] = {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}
        value["execution_receipt_hash"] = canonical_hash(
            value, omit="execution_receipt_hash"
        )
        with self.assertRaises(CorrectedExecutionGateError):
            validate_principal_execution(value, **_expected())

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
            "principal_artifact_path": execution["artifact"]["artifact_path"],
            "principal_findings_sha256": execution["artifact"]["findings_sha256"],
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
            "principal_findings_sha256": execution["artifact"]["findings_sha256"],
            "one_way_handoff_not_yet_created": True,
            "freeze_hash": "",
        }
        freeze["freeze_hash"] = canonical_hash(freeze, omit="freeze_hash")
        receipt = validate_first_lock_and_freeze(execution, first_lock, freeze)
        self.assertEqual(receipt["locked_findings_sha256"], SHA)

    def test_rejects_controller_summary_lock(self) -> None:
        execution = principal_execution()
        first_lock = {
            "schema": "FRANKIE_NATIVE_RAW_MBO_RT_FIRST_LOCK_V1",
            "run_id": execution["run_id"],
            "execution_receipt_hash": execution["execution_receipt_hash"],
            "principal_artifact_path": execution["artifact"]["artifact_path"],
            "principal_findings_sha256": execution["artifact"]["findings_sha256"],
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
            "principal_findings_sha256": execution["artifact"]["findings_sha256"],
            "one_way_handoff_not_yet_created": True,
            "freeze_hash": "",
        }
        freeze["freeze_hash"] = canonical_hash(freeze, omit="freeze_hash")
        with self.assertRaisesRegex(CorrectedExecutionGateError, "controller summary"):
            validate_first_lock_and_freeze(execution, first_lock, freeze)


if __name__ == "__main__":
    unittest.main()


class GateSurfacesTrackTheRegistryTest(unittest.TestCase):
    """The gate's surfaces are the registry's layers. Drift must fail here, not at run time."""

    CONTROL_GROUPS = {"binding_common_controls", "a_clean_overlay", "a_memory_overlay"}
    REGISTRY = (
        "research/kalshi/agents/frankie_native_raw_mbo_ingestion_layer_registry_20260828.json"
    )

    @classmethod
    def setUpClass(cls) -> None:
        import json
        from pathlib import Path

        registry = json.loads(Path(cls.REGISTRY).read_text(encoding="utf-8"))
        cls.registry = registry
        groups = [g for g in registry["groups"] if g["group_id"] not in cls.CONTROL_GROUPS]
        cls.layers = {e["layer_id"] for g in groups for e in g["entries"]}
        cls.stream_required = {
            e["layer_id"]
            for g in groups
            if g["policy"] == "CAUSAL_STREAM_REQUIRED"
            for e in g["entries"]
        }
        cls.sealed = {
            e["layer_id"]
            for g in groups
            if g["policy"] == "SEALED_FOR_A_SCOPE"
            for e in g["entries"]
        }

    def test_surface_ids_equal_the_registry_layers(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark import (
            corrected_a_arm_execution_gate_20260828 as gate,
        )

        self.assertEqual(
            gate.SURFACE_IDS,
            self.layers,
            "gate surfaces drifted from the registry; regenerate rather than editing by hand",
        )

    def test_there_are_ninety_one_concrete_layers(self) -> None:
        """Was 97: 93 inventory bullets + 4 helper roles.

        D64 removed the four helper roles, the carryforward helper-architecture layer and
        the helper-evidence movie output, so 91. 90 is the declared floor, not the count -
        and the margin is now nine, which is worth knowing before anything else is removed.
        """
        self.assertEqual(len(self.layers), 91)
        self.assertGreaterEqual(
            len(self.layers), self.registry["hard_minimum_concrete_layer_count"]
        )

    def test_the_superseded_october_vocabulary_is_gone(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark import (
            corrected_a_arm_execution_gate_20260828 as gate,
        )

        for stale in (
            "top20_book_and_fifo",
            "weather_forward_forcing",
            "fundamentals_and_storage",
            "power_stack_and_generation",
            "full_bigsuite",
            "frozen_rt_state",
        ):
            self.assertNotIn(stale, gate.SURFACE_IDS)

    def test_mandatory_surfaces_come_from_the_stream_required_policy(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark import (
            corrected_a_arm_execution_gate_20260828 as gate,
        )

        self.assertEqual(gate.MANDATORY_NATIVE_RT_SURFACES, self.stream_required)
        self.assertTrue(gate.MANDATORY_NATIVE_RT_SURFACES <= gate.SURFACE_IDS)
        self.assertEqual(len(gate.MANDATORY_NATIVE_RT_SURFACES), 55)

    def test_every_sealed_layer_is_checked_not_one_representative(self) -> None:
        """The old gate verified a single surface, so any other sealed breach passed."""
        from research.kalshi.frankie_raw_mbo_benchmark import (
            corrected_a_arm_execution_gate_20260828 as gate,
        )

        self.assertEqual(gate.SEALED_SURFACES, self.sealed)
        self.assertEqual(len(gate.SEALED_SURFACES), 9)
        self.assertFalse(gate.SEALED_SURFACES & gate.MANDATORY_NATIVE_RT_SURFACES)

    def test_a_breach_on_any_sealed_layer_is_rejected(self) -> None:
        from research.kalshi.frankie_raw_mbo_benchmark import (
            corrected_a_arm_execution_gate_20260828 as gate,
        )

        for surface_id in sorted(gate.SEALED_SURFACES):
            with self.subTest(surface=surface_id):
                value = surface_inventory()
                row = next(r for r in value["surfaces"] if r["surface_id"] == surface_id)
                row.update(route="DIRECT", availability="AVAILABLE", model_visible=True)
                value["inventory_hash"] = canonical_hash(value, omit="inventory_hash")
                with self.assertRaisesRegex(CorrectedExecutionGateError, "not fully sealed"):
                    validate_rt_surface_inventory(value, arm="A_MEMORY")
