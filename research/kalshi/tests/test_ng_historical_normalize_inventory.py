import json
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_historical_inventory import (  # noqa: E402
    InventoryError,
    build_manifest,
    inspect_uri,
    validate_definitions,
)
from ng_historical_manifest import G15_CONTRACT_MAP, G15_DATES  # noqa: E402
from ng_historical_normalize import (  # noqa: E402
    NormalizeError,
    decimal_price,
    event_seconds,
    normalize_file,
    normalize_record,
)


def definitions():
    return {
        "NGJ26": {
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": 1008,
            "raw_symbol": "NGJ26",
            "definition_date": "2026-03-01",
            "definition_start_s": 0.0,
            "definition_end_s": 10_000.0,
            "observed_at": "2026-07-21T00:00:00Z",
        },
        "NGK26": {
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": 996,
            "raw_symbol": "NGK26",
            "definition_date": "2026-03-20",
            "definition_start_s": 0.0,
            "definition_end_s": 10_000.0,
            "observed_at": "2026-07-21T00:00:00Z",
        },
    }


def identity(day):
    contract = G15_CONTRACT_MAP[day]
    return {
        "dataset": "GLBX.MDP3",
        "publisher_id": 1,
        "instrument_id": contract["instrument_id"],
        "raw_symbol": contract["raw_symbol"],
        "definition_date": "2026-03-01" if day <= "20260319" else "2026-03-20",
        "session_day": day,
    }


class NormalizeTests(unittest.TestCase):
    def test_timestamp_and_price_scaling(self):
        self.assertEqual(event_seconds(1_700_000_000_000_000_000), 1_700_000_000.0)
        self.assertEqual(event_seconds(1_700_000_000_000), 1_700_000_000.0)
        self.assertEqual(decimal_price(3_123_000_000), 3.123)
        self.assertEqual(decimal_price(3.123), 3.123)

    def test_trade_and_mbo_enum_normalization(self):
        trade = normalize_record(
            {
                **identity("20260316"),
                "event_type": "trade",
                "ts_event_s": 10,
                "price": 3_111_000_000,
                "size": 2,
                "side": "Buy",
                "sequence": 1,
            },
            ingest_sequence=1,
        )
        self.assertEqual(trade["side"], "B")
        self.assertEqual(trade["price"], 3.111)
        mbo = normalize_record(
            {
                **identity("20260316"),
                "event_type": "mbo",
                "ts_event_s": 11,
                "action": "Modify",
                "side": "Ask",
                "price": 3.112,
                "size": 4,
                "order_id": 9,
                "flags": 128,
            },
            ingest_sequence=2,
        )
        self.assertEqual((mbo["action"], mbo["side"]), ("M", "A"))

    def test_ambiguous_record_is_rejected(self):
        with self.assertRaises(NormalizeError):
            normalize_record(
                {
                    **identity("20260316"),
                    "ts_event_s": 10,
                    "rtype": 0,
                    "price": 3.0,
                    "size": 1,
                    "side": "B",
                }
            )

    def test_normalize_file_rejects_backwards_source(self):
        with tempfile.TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "trade.jsonl"
            output = Path(tempdir) / "normalized.jsonl"
            rows = [
                {**identity("20260316"), "ts_event_s": 2, "price": 3.0, "size": 1, "side": "B", "sequence": 2},
                {**identity("20260316"), "ts_event_s": 1, "price": 3.0, "size": 1, "side": "B", "sequence": 1},
            ]
            source.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
            with self.assertRaises(NormalizeError):
                normalize_file(
                    source,
                    kind="trade",
                    dataset="GLBX.MDP3",
                    publisher_id=1,
                    instrument_id=1008,
                    raw_symbol="NGJ26",
                    definition_date="2026-03-01",
                    session_day="20260316",
                    output=output,
                )


class InventoryTests(unittest.TestCase):
    def test_definition_metadata_is_required_and_canonical(self):
        checked = validate_definitions(definitions(), 1)
        self.assertEqual(checked["NGJ26"]["instrument_id"], 1008)
        bad = definitions()
        bad["NGJ26"].pop("observed_at")
        with self.assertRaises(InventoryError):
            validate_definitions(bad, 1)

    def test_corrupt_identity_never_becomes_present(self):
        with tempfile.TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "trade.jsonl"
            row = {
                **identity("20260316"),
                "raw_symbol": "NGK26",
                "instrument_id": 996,
                "ts_event_s": 2,
                "price": 3.0,
                "size": 1,
                "side": "B",
                "sequence": 1,
            }
            source.write_text(json.dumps(row) + "\n", encoding="utf-8")
            entry = inspect_uri(
                str(source),
                source_kind="l1_trades",
                day="20260316",
                definition=definitions()["NGJ26"],
            )
            self.assertEqual(entry["status"], "CORRUPT")

    def test_event_outside_definition_period_is_corrupt(self):
        with tempfile.TemporaryDirectory() as tempdir:
            source = Path(tempdir) / "trade.jsonl"
            row = {
                **identity("20260316"),
                "ts_event_s": 20_000,
                "price": 3.0,
                "size": 1,
                "side": "B",
                "sequence": 1,
            }
            source.write_text(json.dumps(row) + "\n", encoding="utf-8")
            entry = inspect_uri(
                str(source),
                source_kind="l1_trades",
                day="20260316",
                definition=definitions()["NGJ26"],
            )
            self.assertEqual(entry["status"], "CORRUPT")
            self.assertIn("definition period", entry["observation_error"])

    def test_complete_fixture_manifest_becomes_ready(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            for index, day in enumerate(G15_DATES, 1):
                ident = identity(day)
                trade = {
                    **ident,
                    "ts_event_s": float(index * 10),
                    "price": 3.0,
                    "size": 1,
                    "side": "B",
                    "sequence": 1,
                }
                mbo = {
                    **ident,
                    "ts_event_s": float(index * 10),
                    "action": "A",
                    "side": "B",
                    "price": 3.0,
                    "size": 1,
                    "order_id": index,
                    "flags": 128,
                    "sequence": 1,
                }
                (root / f"l1_{day}.jsonl").write_text(json.dumps(trade) + "\n", encoding="utf-8")
                (root / f"mbo_{day}.jsonl").write_text(json.dumps(mbo) + "\n", encoding="utf-8")
            manifest = build_manifest(
                l1_pattern=str(root / "l1_{day}.jsonl"),
                mbo_pattern=str(root / "mbo_{day}.jsonl"),
                publisher_id=1,
                definitions=definitions(),
            )
            self.assertEqual(manifest["report"]["status"], "READY")
            self.assertTrue(manifest["report"]["can_replay_all_g15"])
            self.assertEqual(len(manifest["entries"]), 24)


if __name__ == "__main__":
    unittest.main()
