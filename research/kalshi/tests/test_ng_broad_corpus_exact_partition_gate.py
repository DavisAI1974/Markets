from __future__ import annotations

import copy
import hashlib
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import ng_broad_corpus_exact_partition_gate as gate
import ng_broad_corpus_exact_overlap_gate as overlap
import ng_corpus_coverage_audit as coverage

DAYS = list(coverage.G15_DATES + coverage.G16_DATES)


def _identity(day: str) -> dict:
    expected = coverage.G15_CONTRACT_MAP.get(day) or coverage.G16_CONTRACT_MAP[day]
    symbol = expected["raw_symbol"]
    start = datetime(2026, 3, 1 if symbol == "NGJ26" else 20, tzinfo=timezone.utc)
    return {
        "dataset": coverage.DATASET,
        "publisher_id": 1,
        "instrument_id": expected["instrument_id"],
        "raw_symbol": symbol,
        "definition_date": start.date().isoformat(),
        "definition_start_s": start.timestamp(),
        "definition_end_s": datetime(2026, 7, 1, tzinfo=timezone.utc).timestamp(),
    }


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _entry(
    *,
    lane: str,
    day: str,
    suffix: str = "",
    start_offset: int | None = None,
    end_offset: int | None = None,
) -> dict:
    midnight = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc).timestamp()
    default_start = 60 if lane == "l1_trades" else 120
    default_end = 3600 if lane == "l1_trades" else 3540
    source_id = f"{lane}:{day}{suffix}"
    return {
        "day": day,
        "lane": lane,
        "source_id": source_id,
        "status": "PRESENT",
        "location": f"/fixture/{lane}/{day}{suffix}.jsonl",
        **_identity(day),
        "event_start_s": midnight + (default_start if start_offset is None else start_offset),
        "event_end_s": midnight + (default_end if end_offset is None else end_offset),
        "record_count": 10,
        "size_bytes": 100,
        "sha256": _sha(source_id),
        "inventory_observed_at": "2026-07-24T00:00:00Z",
    }


def _fixture() -> dict:
    l1_entries = [_entry(lane="l1_trades", day=day) for day in DAYS]
    mbo_entries = [_entry(lane="mbo", day=day) for day in DAYS]
    day_reports = []
    for day in DAYS:
        day_reports.append(
            {
                "day": day,
                "status": "READY",
                "selected_identity": _identity(day),
                "l1_source_ids": [f"l1_trades:{day}"],
                "mbo_source_ids": [f"mbo:{day}"],
            }
        )
    return {
        "schema": overlap.SCHEMA,
        "status": overlap.READY_STATUS,
        "fingerprint": "fixture-overlap",
        "broad_scope_gate_fingerprint": "fixture-broad",
        "inspection_receipt_fingerprint": "fixture-receipt",
        "catalog_fingerprint": "fixture-catalog",
        "coverage_audit_fingerprint": "fixture-audit",
        "expected_overlap_days": list(DAYS),
        "day_reports": day_reports,
        "source_broad_scope_gate": {
            "source_inspection_receipt": {
                "catalog": {
                    "corpora": [
                        {
                            "corpus_id": coverage.L1_CORPUS_ID,
                            "lane": "l1_trades",
                            "entries": l1_entries,
                        },
                        {
                            "corpus_id": coverage.MBO_CORPUS_ID,
                            "lane": "mbo",
                            "entries": mbo_entries,
                        },
                    ]
                }
            }
        },
        "actual_outcomes_used": False,
        "paid_live_data_assumed": False,
        "random_shuffle_used": False,
        "one_signal_authority_preserved": True,
        "blind_forecasts_immutable": True,
        "may_change_blind_forecast": False,
        "may_change_posterior": False,
        "may_update_ng_brain": False,
        "execution_authority": False,
        "cme_event_contracts_mode": "SHADOW",
        "brokerage_contract": "tastytrade_not_ibkr",
        "options_lane_started": False,
    }


def _corpus(source: dict, corpus_id: str) -> dict:
    return next(
        row
        for row in source["source_broad_scope_gate"]["source_inspection_receipt"]["catalog"]["corpora"]
        if row["corpus_id"] == corpus_id
    )


def _report(source: dict, day: str) -> dict:
    return next(row for row in source["day_reports"] if row["day"] == day)


class BroadCorpusExactPartitionGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = patch.object(gate.overlap, "validate_gate", side_effect=lambda value: value)
        self.validator.start()
        self.addCleanup(self.validator.stop)

    def test_ready_exact_source_partitions(self) -> None:
        result = gate.build_gate(_fixture())
        self.assertEqual(result["status"], gate.READY_STATUS)
        self.assertEqual(result["ready_days"], DAYS)
        self.assertEqual(result["blocked_days"], [])
        self.assertTrue(result["all_shared_days_exactly_partitioned"])

    def test_duplicate_bytes_same_day_block(self) -> None:
        source = _fixture()
        day = DAYS[0]
        extra = _entry(lane="l1_trades", day=day, suffix=":duplicate")
        original = _corpus(source, coverage.L1_CORPUS_ID)["entries"][0]
        extra["sha256"] = original["sha256"]
        extra["event_start_s"] = original["event_end_s"]
        extra["event_end_s"] = original["event_end_s"] + 60
        _corpus(source, coverage.L1_CORPUS_ID)["entries"].append(extra)
        _report(source, day)["l1_source_ids"].append(extra["source_id"])
        result = gate.build_gate(source)
        self.assertIn(f"{day}:L1:DUPLICATE_SOURCE_BYTES", result["blockers"])

    def test_positive_same_lane_overlap_blocks(self) -> None:
        source = _fixture()
        day = DAYS[1]
        extra = _entry(
            lane="mbo",
            day=day,
            suffix=":overlap",
            start_offset=3000,
            end_offset=4000,
        )
        _corpus(source, coverage.MBO_CORPUS_ID)["entries"].append(extra)
        _report(source, day)["mbo_source_ids"].append(extra["source_id"])
        result = gate.build_gate(source)
        self.assertIn(
            f"{day}:MBO:SAME_LANE_POSITIVE_EVENT_TIME_OVERLAP",
            result["blockers"],
        )

    def test_disjoint_same_lane_shards_are_allowed(self) -> None:
        source = _fixture()
        day = DAYS[2]
        original = next(
            row
            for row in _corpus(source, coverage.L1_CORPUS_ID)["entries"]
            if row["day"] == day
        )
        midnight = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc).timestamp()
        original["event_end_s"] = midnight + 1700
        extra = _entry(
            lane="l1_trades",
            day=day,
            suffix=":shard2",
            start_offset=1700,
            end_offset=3400,
        )
        _corpus(source, coverage.L1_CORPUS_ID)["entries"].append(extra)
        _report(source, day)["l1_source_ids"].append(extra["source_id"])
        result = gate.build_gate(source)
        self.assertEqual(result["status"], gate.READY_STATUS)
        row = next(value for value in result["day_reports"] if value["day"] == day)
        self.assertEqual(row["l1_partition"]["source_count"], 2)
        self.assertEqual(row["l1_partition"]["positive_same_lane_overlaps"], [])

    def test_duplicate_location_same_day_blocks(self) -> None:
        source = _fixture()
        day = DAYS[3]
        extra = _entry(
            lane="l1_trades",
            day=day,
            suffix=":location",
            start_offset=3600,
            end_offset=3700,
        )
        original = next(
            row
            for row in _corpus(source, coverage.L1_CORPUS_ID)["entries"]
            if row["day"] == day
        )
        extra["location"] = original["location"]
        _corpus(source, coverage.L1_CORPUS_ID)["entries"].append(extra)
        _report(source, day)["l1_source_ids"].append(extra["source_id"])
        result = gate.build_gate(source)
        self.assertIn(f"{day}:L1:DUPLICATE_SOURCE_LOCATION", result["blockers"])

    def test_source_bytes_reused_across_days_block(self) -> None:
        source = _fixture()
        rows = _corpus(source, coverage.MBO_CORPUS_ID)["entries"]
        rows[1]["sha256"] = rows[0]["sha256"]
        result = gate.build_gate(source)
        self.assertIn("SOURCE_BYTES_REUSED_ACROSS_DAYS", result["blockers"])

    def test_source_location_reused_across_days_blocks(self) -> None:
        source = _fixture()
        rows = _corpus(source, coverage.L1_CORPUS_ID)["entries"]
        rows[1]["location"] = rows[0]["location"]
        result = gate.build_gate(source)
        self.assertIn("SOURCE_LOCATION_REUSED_ACROSS_DAYS", result["blockers"])

    def test_missing_referenced_source_blocks(self) -> None:
        source = _fixture()
        day = DAYS[4]
        _report(source, day)["mbo_source_ids"] = ["mbo:missing"]
        result = gate.build_gate(source)
        self.assertIn(
            f"{day}:MBO:SOURCE_ID_NOT_FOUND_IN_INSPECTION_RECEIPT",
            result["blockers"],
        )

    def test_identity_mismatch_blocks(self) -> None:
        source = _fixture()
        day = DAYS[5]
        row = next(
            value
            for value in _corpus(source, coverage.L1_CORPUS_ID)["entries"]
            if value["day"] == day
        )
        row["publisher_id"] = 99
        result = gate.build_gate(source)
        self.assertIn(f"{day}:L1:SOURCE_IDENTITY_MISMATCH", result["blockers"])

    def test_source_is_immutable(self) -> None:
        source = _fixture()
        original = copy.deepcopy(source)
        gate.build_gate(source)
        self.assertEqual(source, original)

    def test_deterministic_output(self) -> None:
        source = _fixture()
        self.assertEqual(gate.build_gate(source), gate.build_gate(copy.deepcopy(source)))

    def test_refingerprinted_summary_tampering_rejected(self) -> None:
        result = gate.build_gate(_fixture())
        result["ready_days"] = result["ready_days"][:-1]
        result.pop("fingerprint")
        result["fingerprint"] = gate._fp(result)
        with self.assertRaises(gate.BroadCorpusExactPartitionError):
            gate.validate_gate(result)

    def test_authority_escalation_rejected(self) -> None:
        result = gate.build_gate(_fixture())
        result["options_lane_started"] = True
        result.pop("fingerprint")
        result["fingerprint"] = gate._fp(result)
        with self.assertRaises(gate.BroadCorpusExactPartitionError):
            gate.validate_gate(result)


if __name__ == "__main__":
    unittest.main()
