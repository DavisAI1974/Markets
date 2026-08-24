from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from research.kalshi.frankie_v4_authority_runtime_validation_20260824 import (
    H_RUNTIME_MODULES,
    I_AUTHORITY_RECORDS,
    validate_v4_authority_runtime,
)
from research.kalshi.frankie_v4_governing_runtime_execution_20260824 import (
    execute_v4_governing_prefix,
    validate_v4_governing_runtime_receipt,
)
from research.kalshi.frankie_causal_operational_context_20260824 import (
    CausalDecisionStateSnapshotAdapter,
    RegistryCoverageOracle,
)
from research.kalshi.frankie_full_stack_runtime_contracts_20260824 import CausalPrefixBinding


class V4AuthorityRuntimeValidationTest(unittest.TestCase):
    def test_all_h_modules_and_i_records_are_executably_validated(self) -> None:
        repo = Path(__file__).resolve().parents[3]
        receipt = validate_v4_authority_runtime(repo)
        self.assertEqual(len(H_RUNTIME_MODULES), 15)
        self.assertEqual(len(I_AUTHORITY_RECORDS), 7)
        self.assertEqual(receipt["h_module_count"], 15)
        self.assertEqual(receipt["i_record_count"], 7)
        self.assertTrue(receipt["all_required_api_symbols_callable"])
        self.assertTrue(receipt["all_declared_receipt_hashes_current"])
        self.assertEqual(
            {row["disposition"] for row in receipt["h_modules"]},
            {"PREFLIGHT_API_SURFACE_ONLY_NOT_OPERATIONAL_PROOF"},
        )
        self.assertTrue(receipt["operational_execution_required_per_prefix"])
        self.assertEqual(len(receipt["receipt_hash"]), 64)

    def test_every_h_module_has_per_prefix_execution_or_executable_supersession(self) -> None:
        paths = tuple(f"block_{b}.field_{i}" for b in range(44) for i in range(44))
        snapshot = CausalDecisionStateSnapshotAdapter(
            RegistryCoverageOracle.create(
                paths=paths, source_ids=("fixture",), source_hashes=("1" * 64,)
            )
        ).snapshot(
            run_id="run-h", decision_day="20211001", evaluated_at=10.0,
            canonical_state={"block_0": {"field_0": 1}},
            canonical_source_id="fixture", canonical_source_sha256="2" * 64,
        )
        binding = CausalPrefixBinding(
            run_id="run-h", causal_cutoff=10.0, event_known_by=9.0,
            causal_prefix_hash="3" * 64, state_prefix_hash="4" * 64,
            knowledge_manifest_hash="5" * 64,
        )
        result = lambda probabilities: SimpleNamespace(
            synthesis=SimpleNamespace(probabilities=probabilities)
        )
        paired = SimpleNamespace(
            answer_revealed=False,
            identical_prefix_proof=SimpleNamespace(proved=True, proof_hash="6" * 64),
            control=result((0.6, 0.4)), combined=result((0.7, 0.3)),
        )
        receipt = execute_v4_governing_prefix(
            binding=binding, snapshot=snapshot, paired=paired,
            source_object_id="object", source_object_sha256="7" * 64,
            source_commit="8" * 40,
        )
        self.assertEqual(receipt["module_count"], 15)
        self.assertEqual({row["module"] for row in receipt["modules"]}, {name for name, _ in H_RUNTIME_MODULES})
        self.assertNotIn("DIRECT_MODULE_IMPORT_AND_API_VALIDATED", {row["disposition"] for row in receipt["modules"]})
        self.assertEqual(
            receipt["disposition_counts"],
            {
                "DIRECT_OPERATIONAL_EXECUTION": 11,
                "SUPERSEDED_BY_CORRECTED_RUNTIME_EQUIVALENCE": 4,
            },
        )
        self.assertEqual(len(receipt["module_identity_hash"]), 64)
        self.assertEqual(validate_v4_governing_runtime_receipt(receipt), receipt)
        self.assertEqual(len(receipt["receipt_hash"]), 64)

        drifted = {**receipt, "modules": receipt["modules"][:-1], "module_count": 14}
        with self.assertRaises(ValueError):
            validate_v4_governing_runtime_receipt(drifted)


if __name__ == "__main__":
    unittest.main()
