from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI = Path(__file__).resolve().parents[1]
if str(KALSHI) not in sys.path:
    sys.path.insert(0, str(KALSHI))

import ng_corpus_coverage_audit as coverage
import ng_corpus_definition_byte_binding_gate as gate
import ng_corpus_inspection as inspection
import ng_corpus_inventory_plan_compiler as compiler


class CorpusDefinitionByteBindingGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    @staticmethod
    def _row(lane: str, *, size: int = 1) -> dict:
        if lane == "l1_trades":
            return {
                "event_type": "trade",
                "ts_event_s": 10.0,
                "source_sequence": 1,
                "price": 3.0,
                "size": size,
                "side": "B",
            }
        return {
            "event_type": "mbo",
            "ts_event_s": 10.0,
            "source_sequence": 1,
            "price": 3.0,
            "size": size,
            "side": "B",
            "action": "A",
            "order_id": 100,
        }

    def _source(self, source_id: str, lane: str) -> tuple[Path, dict]:
        path = self.root / f"{source_id}.jsonl"
        path.write_text(json.dumps(self._row(lane)) + "\n", encoding="utf-8")
        raw = path.read_bytes()
        definition = inspection.definition_observation(
            dataset=inspection.DATASET,
            publisher_id=1,
            instrument_id=996,
            raw_symbol="NGK26",
            definition_date="20260330",
            definition_start_s=0.0,
            definition_end_s=100.0,
            observed_from=f"s3://definitions/{source_id}.dbn",
            observed_at="2026-07-24T00:00:00Z",
            source_sha256=hashlib.sha256(raw).hexdigest(),
            source_size_bytes=len(raw),
        )
        return path, definition

    def _artifacts(
        self,
        *,
        mutate_l1_after_definition: bool = False,
        missing_mbo: bool = False,
    ) -> tuple[dict, dict]:
        l1_path, l1_definition = self._source("l1", "l1_trades")
        mbo_path, mbo_definition = self._source("mbo", "mbo")
        if mutate_l1_after_definition:
            l1_path.write_text(
                json.dumps(self._row("l1_trades", size=2)) + "\n",
                encoding="utf-8",
            )
        if missing_mbo:
            mbo_path.unlink()
        spec = {
            "schema": compiler.SPEC_SCHEMA,
            "allowed_roots": [str(self.root)],
            "inventory_observed_at": "2026-07-24T00:00:00Z",
            "corpora": [
                {
                    "corpus_id": coverage.L1_CORPUS_ID,
                    "publisher_id": 1,
                    "expected_days": ["20260330"],
                    "expected_object_count": 1,
                    "inventory_scope_verified": True,
                    "inventory_complete_asserted": True,
                    "sources": [
                        {
                            "source_id": "l1",
                            "day": "20260330",
                            "location": "s3://bucket/l1",
                            "materialized_path": str(l1_path),
                            "definition": l1_definition,
                        }
                    ],
                },
                {
                    "corpus_id": coverage.MBO_CORPUS_ID,
                    "publisher_id": 1,
                    "expected_days": ["20260330"],
                    "expected_object_count": 1,
                    "inventory_scope_verified": True,
                    "inventory_complete_asserted": True,
                    "sources": [
                        {
                            "source_id": "mbo",
                            "day": "20260330",
                            "location": "s3://bucket/mbo",
                            "materialized_path": str(mbo_path),
                            "definition": mbo_definition,
                        }
                    ],
                },
            ],
            **gate._authority_fields(),
        }
        plan, compiler_receipt = compiler.build_compiled_plan(
            spec, spec_dir=self.root
        )
        _, _, inspection_receipt = inspection.build_catalog(plan)
        return compiler_receipt, inspection_receipt

    def test_ready_when_every_present_object_matches_definition_bytes(self) -> None:
        compiler_receipt, inspection_receipt = self._artifacts()
        result = gate.build_gate(compiler_receipt, inspection_receipt)
        self.assertEqual(result["status"], gate.READY_STATUS)
        self.assertEqual(result["source_count"], 2)
        self.assertEqual(result["byte_bound_source_count"], 2)
        self.assertFalse(result["stand_down_required"])
        self.assertTrue(
            all(row["byte_identity_matches_definition"] for row in result["bindings"])
        )

    def test_changed_materialized_bytes_fail_closed(self) -> None:
        compiler_receipt, inspection_receipt = self._artifacts(
            mutate_l1_after_definition=True
        )
        self.assertEqual(inspection_receipt["source_statuses"]["l1"], "PRESENT")
        result = gate.build_gate(compiler_receipt, inspection_receipt)
        self.assertEqual(result["status"], gate.BLOCKED_STATUS)
        self.assertTrue(result["stand_down_required"])
        self.assertIn("l1:SOURCE_SHA256_MISMATCH", result["blockers"])

    def test_missing_materialized_object_remains_visible(self) -> None:
        compiler_receipt, inspection_receipt = self._artifacts(missing_mbo=True)
        result = gate.build_gate(compiler_receipt, inspection_receipt)
        self.assertEqual(result["status"], gate.BLOCKED_STATUS)
        self.assertIn("mbo:INSPECTION_STATUS_MISSING", result["blockers"])
        mbo = next(row for row in result["bindings"] if row["source_id"] == "mbo")
        self.assertFalse(mbo["byte_identity_matches_definition"])

    def test_inspection_from_different_plan_is_rejected(self) -> None:
        compiler_receipt, _ = self._artifacts()
        other_compiler, other_inspection = self._artifacts()
        other_plan = other_compiler["compiled_plan"]
        other_plan["corpora"][0]["sources"][0]["location"] = "s3://other/l1"
        other_plan.pop("plan_fingerprint")
        other_plan["plan_fingerprint"] = inspection._fp(other_plan)
        _, _, different_receipt = inspection.build_catalog(other_plan)
        with self.assertRaises(gate.CorpusDefinitionByteBindingError):
            gate.build_gate(compiler_receipt, different_receipt)
        self.assertIsInstance(other_inspection, dict)

    def test_gate_tampering_is_rejected_after_refingerprint(self) -> None:
        compiler_receipt, inspection_receipt = self._artifacts()
        result = gate.build_gate(compiler_receipt, inspection_receipt)
        result["bindings"][0]["byte_identity_matches_definition"] = False
        result["bindings"][0].pop("binding_fingerprint")
        result["bindings"][0]["binding_fingerprint"] = gate._fp(
            result["bindings"][0]
        )
        result.pop("fingerprint")
        result["fingerprint"] = gate._fp(result)
        with self.assertRaises(gate.CorpusDefinitionByteBindingError):
            gate.validate_gate(result)

    def test_nested_inspection_tampering_is_rejected(self) -> None:
        compiler_receipt, inspection_receipt = self._artifacts()
        result = gate.build_gate(compiler_receipt, inspection_receipt)
        result["inspection_receipt"]["source_statuses"]["l1"] = "MISSING"
        result["inspection_receipt"].pop("receipt_fingerprint")
        result["inspection_receipt"]["receipt_fingerprint"] = inspection._fp(
            result["inspection_receipt"]
        )
        result.pop("fingerprint")
        result["fingerprint"] = gate._fp(result)
        with self.assertRaises(Exception):
            gate.validate_gate(result)

    def test_authority_escalation_is_rejected(self) -> None:
        compiler_receipt, inspection_receipt = self._artifacts()
        result = gate.build_gate(compiler_receipt, inspection_receipt)
        result["options_lane_started"] = True
        result.pop("fingerprint")
        result["fingerprint"] = gate._fp(result)
        with self.assertRaises(gate.CorpusDefinitionByteBindingError):
            gate.validate_gate(result)

    def test_inputs_are_not_mutated(self) -> None:
        compiler_receipt, inspection_receipt = self._artifacts()
        compiler_before = copy.deepcopy(compiler_receipt)
        inspection_before = copy.deepcopy(inspection_receipt)
        gate.build_gate(compiler_receipt, inspection_receipt)
        self.assertEqual(compiler_receipt, compiler_before)
        self.assertEqual(inspection_receipt, inspection_before)

    def test_output_is_deterministic(self) -> None:
        compiler_receipt, inspection_receipt = self._artifacts()
        first = gate.build_gate(compiler_receipt, inspection_receipt)
        second = gate.build_gate(compiler_receipt, inspection_receipt)
        self.assertEqual(first, second)

    def test_permanent_authority_wall(self) -> None:
        compiler_receipt, inspection_receipt = self._artifacts()
        result = gate.build_gate(compiler_receipt, inspection_receipt)
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
            self.assertFalse(result[field])
        self.assertTrue(result["one_signal_authority_preserved"])
        self.assertTrue(result["blind_forecasts_immutable"])
        self.assertEqual(result["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(result["brokerage_contract"], "tastytrade_not_ibkr")


if __name__ == "__main__":
    unittest.main()
