from __future__ import annotations

import copy
import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_ingestion_layer_registry import (
    HARD_MINIMUM_CONCRETE_LAYER_COUNT,
    IngestionLayerGateError,
    canonical_hash,
    load_registry,
    validate_causal_group_delivery_receipt,
    validate_pre_call_receipt,
    validate_registry,
)


SHA = "a" * 64


def complete_pre_call_receipt(arm: str = "A_MEMORY") -> dict[str, object]:
    registry = load_registry()
    rows = []
    for group in registry["groups"]:
        policy = group["policy"]
        for entry in group["entries"]:
            applicable = arm in group["arms"]
            if not applicable:
                status = "NOT_APPLICABLE"
                visible = False
                evidence_hash = None
            elif policy in {"STATIC_REQUIRED_INPUT", "ARM_REQUIRED_INPUT"}:
                status = "AVAILABLE"
                visible = True
                evidence_hash = SHA
            elif policy == "CAUSAL_STREAM_REQUIRED":
                status = "READY_CAUSAL_STREAM"
                visible = False
                evidence_hash = SHA
            elif policy == "SEALED_FOR_A_SCOPE":
                status = "SEALED"
                visible = False
                evidence_hash = SHA
            elif policy == "PROVISIONAL_SHADOW":
                status = "SHADOW_DISABLED"
                visible = False
                evidence_hash = SHA
            elif policy == "APPEND_ONLY_OUTPUT":
                status = "PENDING"
                visible = False
                evidence_hash = None
            else:  # pragma: no cover - registry validation owns policy vocabulary
                raise AssertionError(policy)
            rows.append(
                {
                    "layer_id": entry["layer_id"],
                    "status": status,
                    "model_visible": visible,
                    "evidence_receipt_sha256": evidence_hash,
                }
            )
    receipt = {
        "schema": "FRANKIE_NATIVE_RAW_MBO_PRE_CALL_LAYER_RECEIPT_V1",
        "run_id": "corrected-a-memory-1",
        "arm": arm,
        "stage": "PRE_CALL",
        "registry_sha256": registry["registry_sha256"],
        "layers": rows,
        "receipt_sha256": "",
    }
    receipt["receipt_sha256"] = canonical_hash(receipt, omit="receipt_sha256")
    return receipt


def complete_group_delivery_receipt(arm: str = "A_MEMORY") -> dict[str, object]:
    registry = load_registry()
    layer_ids = []
    for group in registry["groups"]:
        if group["policy"] == "CAUSAL_STREAM_REQUIRED" and arm in group["arms"]:
            layer_ids.extend(entry["layer_id"] for entry in group["entries"])
    value = {
        "schema": "FRANKIE_NATIVE_RAW_MBO_CAUSAL_GROUP_DELIVERY_V1",
        "run_id": "corrected-a-memory-1",
        "arm": arm,
        "registry_sha256": registry["registry_sha256"],
        "group_id": 123,
        "group_sha256": SHA,
        "f_last_closed": True,
        "clocks": {
            "event_time_ns": 100,
            "receive_time_ns": 110,
            "availability_time_ns": 110,
            "decision_time_ns": 111,
        },
        "delivered_layers": [
            {
                "layer_id": layer_id,
                "model_visible": True,
                "evidence_receipt_sha256": SHA,
            }
            for layer_id in layer_ids
        ],
        "previous_delivery_receipt_sha256": SHA,
        "receipt_sha256": "",
    }
    value["receipt_sha256"] = canonical_hash(value, omit="receipt_sha256")
    return value


class NativeIngestionLayerRegistryTests(unittest.TestCase):
    def test_registry_enforces_hard_floor_without_placeholders(self) -> None:
        receipt = validate_registry(load_registry())
        self.assertEqual(HARD_MINIMUM_CONCRETE_LAYER_COUNT, 90)
        self.assertEqual(receipt["hard_minimum_concrete_layer_count"], 90)
        self.assertEqual(receipt["concrete_layer_count"], 99)
        self.assertEqual(receipt["a_clean_applicable_layer_count"], 96)
        self.assertEqual(receipt["a_memory_applicable_layer_count"], 98)
        self.assertEqual(receipt["placeholder_layer_ids"], [])

    def test_v3_derived_layers_are_the_carryforward_and_the_proposal_lineage(self) -> None:
        """Was `test_only_corrected_extra_agent_carryforward_is_v3_derived` until 2026-09-02.

        Greg's ruling that the proposal lineage goes in WHOLE (DROP_IN_S121 item zero) binds the
        two `_V3_V4_` brain trade-proposal addenda into `learned_structure_proposal_index_material`,
        which therefore carries V3-derived material and is flagged as such. Sorted, because the
        validator returns the ids sorted.
        """
        receipt = validate_registry(load_registry())
        self.assertEqual(
            receipt["v3_derived_layer_ids"],
            [
                "extra_agent_corrected_information_and_gap_diagnoses",
                "learned_structure_proposal_index_material",
            ],
        )

    def test_no_layer_carries_the_retired_four_helper_architecture(self) -> None:
        """D64: the four helpers are out of everything Frankie can see.

        Asserted over layer IDS AND descriptions, not just ids, because the architecture
        lived in the DESCRIPTION of `extra_agent_four_helper_architecture_roles` - the three
        V3 files it pointed at contain no helper text at all. An id-only check would have
        passed on a layer still telling Frankie to read them as a helper architecture.
        """
        registry = load_registry()
        offenders = [
            entry["layer_id"]
            for group in registry["groups"]
            for entry in group["entries"]
            if "helper" in (entry["layer_id"] + " " + entry["description"]).lower()
        ]
        self.assertEqual(offenders, [])
        self.assertEqual(
            [g["group_id"] for g in registry["groups"] if "helper" in g["group_id"]], []
        )

    def test_exact_nine_answer_layers_are_stage_sealed(self) -> None:
        receipt = validate_registry(load_registry())
        self.assertEqual(receipt["sealed_layer_count"], 9)
        self.assertEqual(
            set(receipt["sealed_layer_ids"]),
            {
                "later_outcome_reveal",
                "target_ground_truth_onset_time",
                "step1_existing_october_seconds",
                "step1_populations",
                "step1_crosswalks",
                "step1_target_membership_receipts",
                "step1_labels_and_classifications",
                "step1_result_prefixes",
                "step1_reconciliation_outputs",
            },
        )

    def test_complete_pre_call_receipt_passes_and_seals_answer_wall(self) -> None:
        receipt = validate_pre_call_receipt(complete_pre_call_receipt())
        self.assertGreaterEqual(receipt["registered_layer_count"], 90)
        self.assertEqual(receipt["sealed_layer_count"], 9)
        self.assertTrue(receipt["answer_wall_sealed"])
        self.assertTrue(receipt["all_required_inputs_available"])

    def test_causal_group_delivery_activates_every_stream_layer_at_f_last(self) -> None:
        receipt = validate_causal_group_delivery_receipt(
            complete_group_delivery_receipt()
        )
        self.assertTrue(receipt["f_last_closed"])
        self.assertTrue(receipt["all_causal_layers_delivered"])
        self.assertIn("fifo_queues", receipt["delivered_layer_ids"])

    def test_causal_group_delivery_rejects_missing_fifo(self) -> None:
        value = complete_group_delivery_receipt()
        value["delivered_layers"] = [
            row for row in value["delivered_layers"] if row["layer_id"] != "fifo_queues"
        ]
        value["receipt_sha256"] = canonical_hash(value, omit="receipt_sha256")
        with self.assertRaisesRegex(IngestionLayerGateError, "complete causal layer set"):
            validate_causal_group_delivery_receipt(value)

    def test_causal_group_delivery_rejects_open_group(self) -> None:
        value = complete_group_delivery_receipt()
        value["f_last_closed"] = False
        value["receipt_sha256"] = canonical_hash(value, omit="receipt_sha256")
        with self.assertRaisesRegex(IngestionLayerGateError, "F_LAST"):
            validate_causal_group_delivery_receipt(value)

    def test_missing_layer_fails_even_when_floor_would_still_be_met(self) -> None:
        value = complete_pre_call_receipt()
        value["layers"] = value["layers"][:-1]
        value["receipt_sha256"] = canonical_hash(value, omit="receipt_sha256")
        with self.assertRaisesRegex(IngestionLayerGateError, "complete registry"):
            validate_pre_call_receipt(value)

    def test_required_input_cannot_be_unavailable(self) -> None:
        value = complete_pre_call_receipt()
        row = next(
            row for row in value["layers"] if row["layer_id"] == "fifo_queues"
        )
        row.update(status="UNAVAILABLE", model_visible=False)
        value["receipt_sha256"] = canonical_hash(value, omit="receipt_sha256")
        with self.assertRaisesRegex(IngestionLayerGateError, "required input"):
            validate_pre_call_receipt(value)

    def test_sealed_answer_layer_cannot_be_model_visible(self) -> None:
        value = complete_pre_call_receipt()
        row = next(
            row
            for row in value["layers"]
            if row["layer_id"] == "step1_target_membership_receipts"
        )
        row.update(status="AVAILABLE", model_visible=True)
        value["receipt_sha256"] = canonical_hash(value, omit="receipt_sha256")
        with self.assertRaisesRegex(IngestionLayerGateError, "sealed layer"):
            validate_pre_call_receipt(value)

    def test_registry_cannot_be_reduced_below_hard_floor(self) -> None:
        value = copy.deepcopy(load_registry())
        remaining = HARD_MINIMUM_CONCRETE_LAYER_COUNT - 1
        for group in value["groups"]:
            kept = min(len(group["entries"]), remaining)
            group["entries"] = group["entries"][:kept]
            remaining -= kept
        value["groups"] = [group for group in value["groups"] if group["entries"]]
        value["registry_sha256"] = canonical_hash(value, omit="registry_sha256")
        with self.assertRaisesRegex(IngestionLayerGateError, "hard floor of 90"):
            validate_registry(value)


if __name__ == "__main__":
    unittest.main()
