from __future__ import annotations

import copy
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

import ng_broad_corpus_exact_overlap_gate as gate
import ng_broad_corpus_scope_gate as broad
import ng_corpus_coverage_audit as coverage


DAYS = list(coverage.G15_DATES + coverage.G16_DATES)


def _identity(symbol: str) -> tuple[int, str, float, float]:
    if symbol == "NGJ26":
        return (
            1008,
            "2026-03-01",
            datetime(2026, 3, 1, tzinfo=timezone.utc).timestamp(),
            datetime(2026, 5, 1, tzinfo=timezone.utc).timestamp(),
        )
    return (
        996,
        "2026-03-20",
        datetime(2026, 3, 20, tzinfo=timezone.utc).timestamp(),
        datetime(2026, 5, 1, tzinfo=timezone.utc).timestamp(),
    )


def _entry(*, lane: str, day: str, symbol: str | None = None, suffix: str = "") -> dict:
    expected = coverage.G15_CONTRACT_MAP.get(day) or coverage.G16_CONTRACT_MAP[day]
    symbol = symbol or expected["raw_symbol"]
    instrument_id, definition_date, definition_start, definition_end = _identity(symbol)
    midnight = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc).timestamp()
    offset = 60 if lane == "l1_trades" else 120
    return {
        "day": day,
        "lane": lane,
        "source_id": f"{lane}:{day}:{symbol}{suffix}",
        "status": "PRESENT",
        "location": f"/fixture/{lane}/{day}-{symbol}{suffix}.jsonl",
        "dataset": coverage.DATASET,
        "publisher_id": 1,
        "instrument_id": instrument_id,
        "raw_symbol": symbol,
        "definition_date": definition_date,
        "definition_start_s": definition_start,
        "definition_end_s": definition_end,
        "event_start_s": midnight + offset,
        "event_end_s": midnight + 3600 - offset,
        "record_count": 10,
        "size_bytes": 100,
        "sha256": ("a" if lane == "l1_trades" else "b") * 64,
        "inventory_observed_at": "2026-07-24T00:00:00Z",
    }


def _fixture() -> dict:
    corpora = []
    for corpus_id, lane in (
        (coverage.L1_CORPUS_ID, "l1_trades"),
        (coverage.MBO_CORPUS_ID, "mbo"),
    ):
        corpora.append(
            {
                "corpus_id": corpus_id,
                "lane": lane,
                "declared_window": {
                    "start": coverage.EXPECTED_WINDOWS[corpus_id]["start"],
                    "end_exclusive": coverage.EXPECTED_WINDOWS[corpus_id]["end_exclusive"],
                },
                "expected_days": list(DAYS),
                "entries": [_entry(lane=lane, day=day) for day in DAYS],
            }
        )
    return {
        "status": broad.READY_STATUS,
        "fingerprint": "fixture-broad",
        "inspection_receipt_fingerprint": "fixture-receipt",
        "catalog_fingerprint": "fixture-catalog",
        "coverage_audit_fingerprint": "fixture-audit",
        "source_inspection_receipt": {"catalog": {"corpora": corpora}},
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
        for row in source["source_inspection_receipt"]["catalog"]["corpora"]
        if row["corpus_id"] == corpus_id
    )


def _row(source: dict, corpus_id: str, day: str) -> dict:
    return next(row for row in _corpus(source, corpus_id)["entries"] if row["day"] == day)


class BroadCorpusExactOverlapGateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = patch.object(gate.broad, "validate_gate", side_effect=lambda value: value)
        self.validator.start()
        self.addCleanup(self.validator.stop)

    def test_ready_full_shared_window(self) -> None:
        result = gate.build_gate(_fixture())
        self.assertEqual(result["status"], gate.READY_STATUS)
        self.assertEqual(result["ready_days"], DAYS)
        self.assertEqual(result["blocked_days"], [])
        self.assertEqual(result["contract_transition_count"], 1)
        self.assertTrue(result["g15_g16_days_included"])

    def test_missing_l1_expected_day_blocks(self) -> None:
        source = _fixture()
        _corpus(source, coverage.L1_CORPUS_ID)["expected_days"].remove(DAYS[-1])
        result = gate.build_gate(source)
        self.assertIn("MBO_EXPECTED_DAYS_MISSING_FROM_L1_EXPECTED_DAYS", result["blockers"])

    def test_definition_mismatch_blocks(self) -> None:
        source = _fixture()
        day = DAYS[2]
        _row(source, coverage.MBO_CORPUS_ID, day)["definition_end_s"] += 1
        result = gate.build_gate(source)
        self.assertIn(f"{day}:NO_EXACT_IDENTITY_EVENT_TIME_OVERLAP", result["blockers"])

    def test_no_event_time_overlap_blocks(self) -> None:
        source = _fixture()
        day = DAYS[3]
        row = _row(source, coverage.MBO_CORPUS_ID, day)
        midnight = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc).timestamp()
        row["event_start_s"] = midnight + 5000
        row["event_end_s"] = midnight + 6000
        result = gate.build_gate(source)
        self.assertIn(f"{day}:NO_EXACT_IDENTITY_EVENT_TIME_OVERLAP", result["blockers"])

    def test_ambiguous_identity_partitions_block(self) -> None:
        source = _fixture()
        day = DAYS[4]
        _corpus(source, coverage.L1_CORPUS_ID)["entries"].append(
            _entry(lane="l1_trades", day=day, symbol="NGK26", suffix=":extra")
        )
        _corpus(source, coverage.MBO_CORPUS_ID)["entries"].append(
            _entry(lane="mbo", day=day, symbol="NGK26", suffix=":extra")
        )
        result = gate.build_gate(source)
        self.assertIn(f"{day}:AMBIGUOUS_EXACT_IDENTITY_PARTITIONS", result["blockers"])

    def test_extra_wrong_basis_source_blocks(self) -> None:
        source = _fixture()
        day = DAYS[5]
        _corpus(source, coverage.L1_CORPUS_ID)["entries"].append(
            _entry(lane="l1_trades", day=day, symbol="NGJ26", suffix=":wrong")
        )
        result = gate.build_gate(source)
        self.assertIn(f"{day}:EXTRA_L1_WRONG_BASIS_SOURCE", result["blockers"])

    def test_same_identity_source_without_overlap_blocks(self) -> None:
        source = _fixture()
        day = DAYS[6]
        extra = _entry(lane="l1_trades", day=day, suffix=":late")
        midnight = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc).timestamp()
        extra["event_start_s"] = midnight + 5000
        extra["event_end_s"] = midnight + 6000
        _corpus(source, coverage.L1_CORPUS_ID)["entries"].append(extra)
        result = gate.build_gate(source)
        self.assertIn(f"{day}:L1_SOURCE_WITHOUT_MBO_EVENT_OVERLAP", result["blockers"])

    def test_contract_identity_reversion_blocks(self) -> None:
        source = _fixture()
        day = DAYS[-1]
        for corpus_id in (coverage.L1_CORPUS_ID, coverage.MBO_CORPUS_ID):
            corpus = _corpus(source, corpus_id)
            corpus["entries"] = [row for row in corpus["entries"] if row["day"] != day]
            corpus["entries"].append(_entry(lane=corpus["lane"], day=day, symbol="NGJ26"))
        result = gate.build_gate(source)
        self.assertIn("IDENTITY_REAPPEARED_AFTER_CONTRACT_TRANSITION", result["blockers"])

    def test_event_range_must_stay_in_declared_utc_day(self) -> None:
        source = _fixture()
        day = DAYS[7]
        row = _row(source, coverage.MBO_CORPUS_ID, day)
        midnight = datetime.strptime(day, "%Y%m%d").replace(tzinfo=timezone.utc).timestamp()
        row["event_end_s"] = midnight + 86400
        result = gate.build_gate(source)
        self.assertTrue(any("does not stay inside UTC day" in value for value in result["blockers"]))

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
        with self.assertRaises(gate.BroadCorpusExactOverlapError):
            gate.validate_gate(result)

    def test_authority_escalation_rejected(self) -> None:
        result = gate.build_gate(_fixture())
        result["options_lane_started"] = True
        result.pop("fingerprint")
        result["fingerprint"] = gate._fp(result)
        with self.assertRaises(gate.BroadCorpusExactOverlapError):
            gate.validate_gate(result)


if __name__ == "__main__":
    unittest.main()
