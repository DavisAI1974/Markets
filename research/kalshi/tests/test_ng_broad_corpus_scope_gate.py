from __future__ import annotations

import copy
import hashlib
import unittest
from datetime import date, timedelta

import ng_broad_corpus_scope_gate as gate


class BroadCorpusScopeGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_receipt_validator = gate.inspection.validate_receipt
        self.original_audit_validator = gate.coverage.validate_audit
        self.original_audit_builder = gate.coverage.build_audit
        gate.inspection.validate_receipt = lambda value: value
        gate.coverage.validate_audit = lambda value: value
        gate.coverage.build_audit = lambda catalog: copy.deepcopy(catalog["_audit"])

    def tearDown(self) -> None:
        gate.inspection.validate_receipt = self.original_receipt_validator
        gate.coverage.validate_audit = self.original_audit_validator
        gate.coverage.build_audit = self.original_audit_builder

    @staticmethod
    def _days(start: str, end_exclusive: str) -> list[str]:
        current = date.fromisoformat(start)
        end = date.fromisoformat(end_exclusive)
        result = []
        while current < end:
            if current.weekday() < 5:
                result.append(current.strftime("%Y%m%d"))
            current += timedelta(days=1)
        return result

    @staticmethod
    def _entry(corpus_id: str, lane: str, day: str, publisher_id: int = 1) -> dict:
        target = gate.coverage.G15_CONTRACT_MAP.get(day) or gate.coverage.G16_CONTRACT_MAP.get(day)
        if target:
            symbol = target["raw_symbol"]
            instrument = target["instrument_id"]
        else:
            symbol = "NGZ25" if day < "20260101" else "NGK26"
            instrument = 900 if day < "20260101" else 996
        event_start = float(date(int(day[:4]), int(day[4:6]), int(day[6:8])).toordinal() * 86400)
        source_id = f"{corpus_id}:{lane}:{day}:{symbol}"
        return {
            "day": day,
            "lane": lane,
            "source_id": source_id,
            "status": "PRESENT",
            "location": f"s3://verified/{source_id}.dbn",
            "dataset": gate.coverage.DATASET,
            "publisher_id": publisher_id,
            "instrument_id": instrument,
            "raw_symbol": symbol,
            "definition_date": day,
            "definition_start_s": event_start - 100.0,
            "definition_end_s": event_start + 1000.0,
            "event_start_s": event_start,
            "event_end_s": event_start + 500.0,
            "record_count": 10,
            "size_bytes": 100,
            "sha256": hashlib.sha256(source_id.encode()).hexdigest(),
            "inventory_observed_at": "2026-07-24T00:00:00Z",
        }

    def _receipt(self) -> dict:
        corpora = []
        reports = []
        target_days = set(gate.coverage.G15_DATES + gate.coverage.G16_DATES)
        for corpus_id, spec in gate.coverage.EXPECTED_WINDOWS.items():
            expected_days = sorted(set(self._days(spec["start"], spec["end_exclusive"])) | target_days)
            entries = [self._entry(corpus_id, spec["lane"], day) for day in expected_days]
            corpora.append(
                {
                    "corpus_id": corpus_id,
                    "lane": spec["lane"],
                    "declared_window": {"start": spec["start"], "end_exclusive": spec["end_exclusive"]},
                    "publisher_id": 1,
                    "remote_inventory_verified": True,
                    "inventory_complete": True,
                    "expected_object_count": len(entries),
                    "observed_object_count": len(entries),
                    "expected_days": expected_days,
                    "inventory_observed_at": "2026-07-24T00:00:00Z",
                    "entries": entries,
                }
            )
            reports.append(
                {
                    "corpus_id": corpus_id,
                    "status": "VERIFIED_COMPLETE",
                    "validation_errors": [],
                }
            )
        audit = {
            "status": "FULL_CORPUS_AND_G15_G16_EXACT_READY",
            "fingerprint": "audit-fingerprint",
            "corpus_layout": reports,
            "exact_intersections": {
                "g15": {"status": "MATCHED_L1_MBO_READY", "ready_days": list(gate.coverage.G15_DATES)},
                "g16": {"status": "MATCHED_L1_MBO_READY", "ready_days": list(gate.coverage.G16_DATES)},
            },
        }
        catalog = {
            "catalog_fingerprint": "catalog-fingerprint",
            "corpora": corpora,
            "_audit": copy.deepcopy(audit),
        }
        return {
            "receipt_fingerprint": "receipt-fingerprint",
            "catalog": catalog,
            "audit": audit,
        }

    def test_complete_broad_scope_is_ready(self) -> None:
        result = gate.build_gate(self._receipt())
        self.assertEqual(result["status"], gate.READY_STATUS)
        self.assertTrue(result["broad_l1_one_year_verified"])
        self.assertTrue(result["broad_mbo_spring_summer_verified"])
        self.assertEqual(result["aligned_publisher_ids"], [1])
        self.assertEqual(result["blockers"], [])

    def test_target_days_alone_cannot_satisfy_broad_scope(self) -> None:
        receipt = self._receipt()
        for corpus in receipt["catalog"]["corpora"]:
            corpus["expected_days"] = list(gate.coverage.G15_DATES + gate.coverage.G16_DATES)
            corpus["entries"] = [
                self._entry(corpus["corpus_id"], corpus["lane"], day)
                for day in corpus["expected_days"]
            ]
            corpus["expected_object_count"] = len(corpus["entries"])
            corpus["observed_object_count"] = len(corpus["entries"])
        receipt["catalog"]["_audit"] = copy.deepcopy(receipt["audit"])
        result = gate.build_gate(receipt)
        self.assertEqual(result["status"], gate.BLOCKED_STATUS)
        self.assertTrue(any("EXPECTED_DAY_SET_TOO_SMALL" in blocker for blocker in result["blockers"]))

    def test_window_edge_gap_blocks_scope(self) -> None:
        receipt = self._receipt()
        corpus = receipt["catalog"]["corpora"][0]
        corpus["expected_days"] = corpus["expected_days"][15:]
        allowed = set(corpus["expected_days"])
        corpus["entries"] = [row for row in corpus["entries"] if row["day"] in allowed]
        corpus["expected_object_count"] = len(corpus["entries"])
        corpus["observed_object_count"] = len(corpus["entries"])
        result = gate.build_gate(receipt)
        self.assertIn("l1_dense_one_year:WINDOW_START_NOT_COVERED", result["blockers"])

    def test_cross_corpus_publisher_mismatch_blocks(self) -> None:
        receipt = self._receipt()
        mbo = receipt["catalog"]["corpora"][1]
        for row in mbo["entries"]:
            row["publisher_id"] = 2
        result = gate.build_gate(receipt)
        self.assertIn("CROSS_CORPUS_PUBLISHER_MISMATCH", result["blockers"])

    def test_non_exact_symbol_fails_closed(self) -> None:
        receipt = self._receipt()
        receipt["catalog"]["corpora"][0]["entries"][0]["raw_symbol"] = "NG.n.0"
        with self.assertRaises(gate.BroadCorpusScopeError):
            gate.build_gate(receipt)

    def test_missing_object_fails_closed(self) -> None:
        receipt = self._receipt()
        receipt["catalog"]["corpora"][0]["entries"][0]["status"] = "MISSING"
        with self.assertRaises(gate.BroadCorpusScopeError):
            gate.build_gate(receipt)

    def test_exact_intersection_must_remain_ready(self) -> None:
        receipt = self._receipt()
        receipt["audit"]["exact_intersections"]["g16"]["status"] = "UNKNOWN"
        receipt["catalog"]["_audit"] = copy.deepcopy(receipt["audit"])
        result = gate.build_gate(receipt)
        self.assertIn("G16_EXACT_INTERSECTION_NOT_READY", result["blockers"])

    def test_refingerprinted_summary_tampering_is_rejected(self) -> None:
        result = gate.build_gate(self._receipt())
        result["corpus_scopes"][0]["expected_day_count"] -= 1
        result.pop("fingerprint")
        result["fingerprint"] = gate._fp(result)
        with self.assertRaises(gate.BroadCorpusScopeError):
            gate.validate_gate(result)

    def test_authority_escalation_is_rejected(self) -> None:
        result = gate.build_gate(self._receipt())
        result["options_lane_started"] = True
        result.pop("fingerprint")
        result["fingerprint"] = gate._fp(result)
        with self.assertRaises(gate.BroadCorpusScopeError):
            gate.validate_gate(result)

    def test_sources_are_not_mutated(self) -> None:
        receipt = self._receipt()
        before = copy.deepcopy(receipt)
        gate.build_gate(receipt)
        self.assertEqual(receipt, before)

    def test_output_is_deterministic(self) -> None:
        receipt = self._receipt()
        self.assertEqual(gate.build_gate(receipt), gate.build_gate(receipt))

    def test_permanent_authority_contract(self) -> None:
        result = gate.build_gate(self._receipt())
        self.assertFalse(result["actual_outcomes_used"])
        self.assertFalse(result["random_shuffle_used"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["execution_authority"])
        self.assertEqual(result["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(result["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(result["options_lane_started"])


if __name__ == "__main__":
    unittest.main()
