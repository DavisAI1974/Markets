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

import ng_corpus_inspection as inspect


class CorpusInspectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.definition = inspect.definition_observation(
            dataset=inspect.DATASET,
            publisher_id=1,
            instrument_id=996,
            raw_symbol="NGK26",
            definition_date="2026-03-01",
            definition_start_s=1.0,
            definition_end_s=1000.0,
            observed_from="s3://observed/definition.dbn",
            observed_at="2026-07-22T00:00:00Z",
            source_sha256="a" * 64,
            source_size_bytes=10,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _write(self, name: str, rows: list[dict]) -> Path:
        path = self.root / name
        path.write_text(
            "".join(json.dumps(row) + "\n" for row in rows),
            encoding="utf-8",
        )
        return path

    def _plan(
        self,
        *,
        path: Path | None,
        lane: str = "l1_trades",
        definition=None,
    ) -> dict:
        plan = inspect.plan_template(allowed_roots=[str(self.root)])
        corpus = plan["corpora"][0 if lane == "l1_trades" else 1]
        corpus["sources"].append(
            {
                "source_id": f"source-{lane}",
                "location": f"s3://observed/{lane}.dbn",
                "materialized_path": None if path is None else str(path),
                "day": "20260330",
                "lane": lane,
                "definition": copy.deepcopy(definition or self.definition),
                "inventory_observed_at": "2026-07-22T00:00:00Z",
            }
        )
        plan.pop("plan_fingerprint")
        plan["plan_fingerprint"] = inspect._fp(plan)
        return plan

    @staticmethod
    def _trades() -> list[dict]:
        return [
            {
                "event_type": "trade",
                "ts_event_s": 10.0,
                "source_sequence": 1,
                "price": 3.0,
                "size": 1,
                "side": "B",
            },
            {
                "event_type": "trade",
                "ts_event_s": 20.0,
                "source_sequence": 2,
                "price": 3.1,
                "size": 1,
                "side": "A",
            },
        ]

    def test_template_never_asserts_presence(self) -> None:
        plan = inspect.plan_template(allowed_roots=[str(self.root)])
        self.assertFalse(plan["remote_presence_inferred"])
        self.assertTrue(
            all(
                not corpus["inventory_complete_asserted"]
                for corpus in plan["corpora"]
            )
        )
        self.assertTrue(
            all(corpus["sources"] == [] for corpus in plan["corpora"])
        )

    def test_present_file_is_hashed_and_identity_bound(self) -> None:
        path = self._write("trades.jsonl", self._trades())
        catalog, _, receipt = inspect.build_catalog(self._plan(path=path))
        row = catalog["corpora"][0]["entries"][0]
        self.assertEqual(row["status"], "PRESENT")
        self.assertEqual(row["raw_symbol"], "NGK26")
        self.assertEqual(row["instrument_id"], 996)
        self.assertEqual(row["record_count"], 2)
        self.assertEqual(
            row["sha256"], hashlib.sha256(path.read_bytes()).hexdigest()
        )
        self.assertEqual(receipt["present_count"], 1)

    def test_missing_file_is_visible(self) -> None:
        path = self.root / "missing.jsonl"
        catalog, _, receipt = inspect.build_catalog(self._plan(path=path))
        row = catalog["corpora"][0]["entries"][0]
        self.assertEqual(row["status"], "MISSING")
        self.assertEqual(receipt["missing_count"], 1)

    def test_unmaterialized_remote_object_remains_unknown(self) -> None:
        catalog, _, receipt = inspect.build_catalog(self._plan(path=None))
        row = catalog["corpora"][0]["entries"][0]
        self.assertEqual(row["status"], "UNKNOWN")
        self.assertEqual(receipt["unknown_count"], 1)

    def test_decoded_identity_contradiction_is_corrupt(self) -> None:
        rows = self._trades()
        rows[0]["raw_symbol"] = "NGJ26"
        path = self._write("mixed.jsonl", rows)
        catalog, _, _ = inspect.build_catalog(self._plan(path=path))
        self.assertEqual(
            catalog["corpora"][0]["entries"][0]["status"], "CORRUPT"
        )

    def test_out_of_definition_event_is_corrupt(self) -> None:
        rows = self._trades()
        rows[-1]["ts_event_s"] = 1001.0
        path = self._write("late.jsonl", rows)
        catalog, _, _ = inspect.build_catalog(self._plan(path=path))
        self.assertEqual(
            catalog["corpora"][0]["entries"][0]["status"], "CORRUPT"
        )

    def test_backward_source_is_corrupt(self) -> None:
        rows = self._trades()
        rows[1]["ts_event_s"] = 5.0
        path = self._write("backward.jsonl", rows)
        catalog, _, _ = inspect.build_catalog(self._plan(path=path))
        self.assertEqual(
            catalog["corpora"][0]["entries"][0]["status"], "CORRUPT"
        )

    def test_filename_is_not_identity_evidence(self) -> None:
        path = self._write("NGJ26_wrong_name.jsonl", self._trades())
        catalog, _, _ = inspect.build_catalog(self._plan(path=path))
        row = catalog["corpora"][0]["entries"][0]
        self.assertEqual(row["raw_symbol"], "NGK26")
        self.assertFalse(row["identity_inferred_from_filename"])

    def test_source_bytes_are_unchanged(self) -> None:
        path = self._write("stable.jsonl", self._trades())
        before = path.read_bytes()
        inspect.build_catalog(self._plan(path=path))
        self.assertEqual(path.read_bytes(), before)

    def test_path_escape_is_rejected(self) -> None:
        outside = Path(self.tmp.name).parent / "outside.jsonl"
        outside.write_text(
            json.dumps(self._trades()[0]) + "\n", encoding="utf-8"
        )
        try:
            with self.assertRaises(inspect.CorpusInspectionError):
                inspect.build_catalog(self._plan(path=outside))
        finally:
            outside.unlink(missing_ok=True)

    def test_plan_tampering_is_rejected(self) -> None:
        path = self._write("tamper.jsonl", self._trades())
        plan = self._plan(path=path)
        plan["corpora"][0]["sources"][0]["day"] = "20260401"
        with self.assertRaises(inspect.CorpusInspectionError):
            inspect.build_catalog(plan)

    def test_definition_tampering_is_rejected(self) -> None:
        bad = copy.deepcopy(self.definition)
        bad["instrument_id"] = 1008
        path = self._write("definition_tamper.jsonl", self._trades())
        with self.assertRaises(inspect.CorpusInspectionError):
            inspect.build_catalog(self._plan(path=path, definition=bad))

    def test_complete_inventory_requires_explicit_scope_count_and_days(self) -> None:
        path = self._write("complete.jsonl", self._trades())
        plan = self._plan(path=path)
        corpus = plan["corpora"][0]
        corpus["inventory_scope_verified"] = True
        corpus["inventory_complete_asserted"] = True
        corpus["expected_days"] = ["20260330"]
        corpus["expected_object_count"] = 1
        plan.pop("plan_fingerprint")
        plan["plan_fingerprint"] = inspect._fp(plan)
        catalog, _, _ = inspect.build_catalog(plan)
        self.assertTrue(catalog["corpora"][0]["inventory_complete"])
        self.assertFalse(catalog["corpora"][1]["inventory_complete"])

    def test_receipt_tampering_is_rejected_even_after_refingerprint(self) -> None:
        path = self._write("receipt.jsonl", self._trades())
        _, _, receipt = inspect.build_catalog(self._plan(path=path))
        receipt["source_statuses"]["source-l1_trades"] = "MISSING"
        receipt.pop("receipt_fingerprint")
        receipt["receipt_fingerprint"] = inspect._fp(receipt)
        with self.assertRaises(inspect.CorpusInspectionError):
            inspect.validate_receipt(receipt)

    def test_authority_flags_are_permanently_disabled(self) -> None:
        path = self._write("authority.jsonl", self._trades())
        _, _, receipt = inspect.build_catalog(self._plan(path=path))
        for field in (
            "actual_outcomes_used",
            "paid_live_data_assumed",
            "may_update_ng_brain",
            "may_change_blind_forecast",
            "may_change_posterior",
            "execution_authority",
        ):
            self.assertFalse(receipt[field])
        self.assertEqual(
            receipt["brokerage_contract"], "tastytrade_not_ibkr"
        )
        self.assertEqual(receipt["cme_event_contracts_mode"], "SHADOW")
        self.assertFalse(receipt["options_lane_started"])


if __name__ == "__main__":
    unittest.main()
