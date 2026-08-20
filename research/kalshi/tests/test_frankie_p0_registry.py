from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from frankie_p0_registry import (  # noqa: E402
    ENTRY_SPECS,
    EVIDENCE_SCHEMA_VERSION,
    REQUIRED_EVIDENCE_TYPES,
    audit_p0_registry,
    evaluate_p0_readiness,
)


def sha(value):
    payload = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def hashed_receipt(core, hash_field="receipt_hash"):
    return {**core, hash_field: sha(core)}


def evidence_bundle():
    marker = {
        "candidate_artifact_sha256": "1" * 64,
        "baseline_artifact_sha256": "2" * 64,
        "runner_commit_sha256": "3" * 64,
        "evaluator_artifact_sha256": "4" * 64,
        "evaluation_plan_sha256": "5" * 64,
    }
    row_hash = "6" * 64
    source_receipts = {
        "HELD_OUT_PERFORMANCE": hashed_receipt(
            {
                "verdict": "PASS",
                "row_hash": row_hash,
                "case_count": 2,
                "declared_seeds": [101, 202],
            }
        ),
        "CALIBRATION": hashed_receipt(
            {
                "verdict": "PASS",
                "row_hash": row_hash,
                "metrics": {"ALL": {"rows": 4}},
            }
        ),
        "CONTAMINATION": hashed_receipt(
            {"verdict": "PASS", "row_hash": row_hash, "trial_count": 4}
        ),
        "RETENTION": hashed_receipt(
            {
                "verdict": "PASS",
                "matrix_hash": row_hash,
                "cells": [{"suite_id": "protected", "stratum": "all", "row_count": 4}],
            }
        ),
        "EVALUATOR_INDEPENDENCE": hashed_receipt(
            {
                "verdict": "JUDGE_AUTHORITY_RETAINED",
                "case_set_hash": row_hash,
                "cases": 4,
            },
            "canary_hash",
        ),
        "BYTE_EXACT_LIVE_ROLLBACK": hashed_receipt(
            {
                "verdict": "PASS",
                "artifact_count": 1,
                "changed_artifact_count": 1,
                "artifacts": [
                    {
                        "artifact_id": "weights",
                        "before_hash": "7" * 64,
                        "candidate_hash": "8" * 64,
                        "restored_hash": "7" * 64,
                        "candidate_changed": True,
                    }
                ],
            }
        ),
    }
    source_validators = {
        "HELD_OUT_PERFORMANCE": "frankie_market_p0_controls.evaluate_paired_repeated_seed_gate",
        "CALIBRATION": "frankie_market_p0_controls.evaluate_calibration_selective_gate",
        "CONTAMINATION": "frankie_market_p0_controls.evaluate_planted_null_contamination_gate",
        "RETENTION": "frankie_market_p0_controls.evaluate_retention_matrix",
        "EVALUATOR_INDEPENDENCE": "frankie_evaluation_controls.evaluate_judge_independence_canary",
        "BYTE_EXACT_LIVE_ROLLBACK": "frankie_market_p0_controls.validate_byte_exact_rollback",
    }
    origins = {
        "HELD_OUT_PERFORMANCE": "EXECUTED_HELD_OUT_ARTIFACTS",
        "CALIBRATION": "EXECUTED_HELD_OUT_ARTIFACTS",
        "CONTAMINATION": "EXECUTED_PLANTED_NULL_ARTIFACTS",
        "RETENTION": "EXECUTED_PROTECTED_SUITE_ARTIFACTS",
        "EVALUATOR_INDEPENDENCE": "EXECUTED_LOCKED_EVALUATOR_ARTIFACTS",
        "BYTE_EXACT_LIVE_ROLLBACK": "EXECUTED_LIVE_ROLLBACK_ARTIFACTS",
    }
    type_fields = {
        "HELD_OUT_PERFORMANCE": {
            "held_out": True,
            "selection_blinded": True,
            "paired_control": True,
            "matched_budget": True,
            "forward_chronological": True,
        },
        "CALIBRATION": {
            "declared_strata_complete": True,
            "calibration_gate_passed": True,
            "selective_risk_gate_passed": True,
        },
        "CONTAMINATION": {
            "planted_null_gate_passed": True,
            "adaptive_search_blinded_to_planted_nulls": True,
            "declared_channel_audit_passed": True,
        },
        "RETENTION": {
            "protected_matrix_complete": True,
            "retention_gate_passed": True,
        },
        "EVALUATOR_INDEPENDENCE": {
            "evaluator_independent": True,
            "evaluator_locked_before_reveal": True,
            "objective_grading": True,
        },
        "BYTE_EXACT_LIVE_ROLLBACK": {
            "byte_exact": True,
            "nonvacuous_mutation": True,
            "live_rollback_executed": True,
            "restored_artifact_count": 1,
        },
    }
    result = []
    for evidence_type in REQUIRED_EVIDENCE_TYPES:
        source = source_receipts[evidence_type]
        core = {
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "evidence_type": evidence_type,
            "evidence_origin": origins[evidence_type],
            "passed": True,
            "attestation_only": False,
            **marker,
            "evidence_artifact_sha256": sha(source),
            "row_count": 1 if evidence_type == "BYTE_EXACT_LIVE_ROLLBACK" else 4,
            "executed_at": "2026-08-20T12:00:00Z",
            "source_validator_entry_point": source_validators[evidence_type],
            "source_receipt": source,
            **type_fields[evidence_type],
        }
        result.append(hashed_receipt(core))
    return result


class FrankieP0RegistryTests(unittest.TestCase):
    def test_inventory_is_exact_hash_bound_and_non_authorizing(self):
        receipt = audit_p0_registry()
        self.assertEqual(receipt["status"], "COMPONENT_CONTRACT_READY")
        self.assertTrue(receipt["component_contract_ready"])
        self.assertEqual(receipt["entry_point_count"], len(ENTRY_SPECS))
        self.assertEqual(
            receipt["classification_counts"],
            {
                classification: sum(
                    entry["classification"] == classification for entry in ENTRY_SPECS
                )
                for classification in ("BENCHMARK", "HELPER", "RUNTIME_LOOP", "VALIDATOR")
            },
        )
        self.assertEqual(receipt["missing_entry_points"], [])
        self.assertEqual(receipt["extra_entry_points"], [])
        self.assertEqual(receipt["unhashed_entry_points"], [])
        self.assertEqual(receipt["module_hash_mismatches"], [])
        for entry in receipt["entries"]:
            self.assertRegex(entry["module_content_sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(entry["entry_point_binding_sha256"], r"^[0-9a-f]{64}$")
            self.assertTrue(entry["paper_derived_mechanisms"])
            self.assertTrue(entry["frankie_added_mechanisms"])
            self.assertTrue(entry["required_matched_controls"])
            self.assertTrue(entry["required_gates"])
            self.assertFalse(entry["performance_evidence"])
            self.assertFalse(entry["execution"])
            self.assertFalse(entry["apply"])
            self.assertFalse(entry["promotion"])

    def test_diagnostic_inventory_detects_missing_extra_and_unhashed_surfaces(self):
        discovered = {}
        for entry in ENTRY_SPECS:
            discovered.setdefault(entry["module"], []).append(entry["entry_point"])
        removed = discovered["frankie_cognitive_p0_loops.py"].pop()
        discovered["frankie_gdl_p0_controls.py"].append("quietly_added_runtime")
        receipt = audit_p0_registry(
            discovered_entry_points=discovered,
            expected_module_hashes={"frankie_cognitive_p0_loops.py": ""},
        )
        self.assertFalse(receipt["component_contract_ready"])
        self.assertIn(
            f"frankie_cognitive_p0_loops.py:{removed}",
            receipt["missing_entry_points"],
        )
        self.assertIn(
            "frankie_gdl_p0_controls.py:quietly_added_runtime",
            receipt["extra_entry_points"],
        )
        self.assertTrue(
            all(
                key.startswith("frankie_cognitive_p0_loops.py:")
                for key in receipt["unhashed_entry_points"]
            )
        )

    def test_component_contract_can_pass_while_empirical_readiness_is_blocked(self):
        readiness = evaluate_p0_readiness()
        self.assertTrue(readiness["component_contract_ready"])
        self.assertFalse(readiness["empirical_evidence_ready"])
        self.assertFalse(readiness["composite_readiness_passed"])
        self.assertEqual(set(readiness["missing_evidence_types"]), set(REQUIRED_EVIDENCE_TYPES))
        self.assertFalse(readiness["performance_evidence"])

    def test_declared_hashes_and_roles_without_verified_source_receipts_do_not_pass(self):
        declarations = []
        for evidence_type in REQUIRED_EVIDENCE_TYPES:
            core = {
                "schema_version": EVIDENCE_SCHEMA_VERSION,
                "evidence_type": evidence_type,
                "passed": True,
                "attestation_only": False,
                "candidate_artifact_sha256": "1" * 64,
                "baseline_artifact_sha256": "2" * 64,
                "runner_commit_sha256": "3" * 64,
                "evaluator_artifact_sha256": "4" * 64,
                "evaluation_plan_sha256": "5" * 64,
                "evidence_artifact_sha256": "6" * 64,
                "row_count": 10,
                "executed_at": "2026-08-20T12:00:00Z",
            }
            declarations.append(hashed_receipt(core))
        readiness = evaluate_p0_readiness(declarations)
        self.assertFalse(readiness["empirical_evidence_ready"])
        self.assertTrue(
            all(
                any("source_receipt" in issue for issue in value["issues"])
                for value in readiness["evidence_status"].values()
            )
        )

    def test_every_bound_evidence_type_is_required_and_authority_stays_false(self):
        bundle = evidence_bundle()
        readiness = evaluate_p0_readiness(bundle)
        self.assertTrue(readiness["empirical_evidence_ready"])
        self.assertTrue(readiness["composite_readiness_passed"])
        self.assertEqual(
            readiness["status"],
            "EMPIRICAL_GATES_READY_USER_AUTHORIZATION_REQUIRED",
        )
        self.assertFalse(readiness["execution"])
        self.assertFalse(readiness["apply"])
        self.assertFalse(readiness["promotion"])
        self.assertTrue(readiness["user_authorization_required"])
        for evidence_type in REQUIRED_EVIDENCE_TYPES:
            incomplete = [
                receipt for receipt in bundle if receipt["evidence_type"] != evidence_type
            ]
            self.assertFalse(evaluate_p0_readiness(incomplete)["composite_readiness_passed"])

    def test_tampered_source_or_cross_binding_fails_closed(self):
        source_tamper = evidence_bundle()
        source_tamper[0]["source_receipt"]["case_count"] = 99
        source_tamper[0]["receipt_hash"] = sha(
            {key: value for key, value in source_tamper[0].items() if key != "receipt_hash"}
        )
        self.assertFalse(evaluate_p0_readiness(source_tamper)["empirical_evidence_ready"])

        binding_tamper = evidence_bundle()
        binding_tamper[1]["candidate_artifact_sha256"] = "9" * 64
        binding_tamper[1]["receipt_hash"] = sha(
            {key: value for key, value in binding_tamper[1].items() if key != "receipt_hash"}
        )
        result = evaluate_p0_readiness(binding_tamper)
        self.assertFalse(result["empirical_evidence_ready"])
        self.assertEqual(result["cross_binding_mismatches"], ["candidate_artifact_sha256"])


if __name__ == "__main__":
    unittest.main()
