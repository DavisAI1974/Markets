import json
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_historical_inventory import build_manifest  # noqa: E402
from ng_historical_manifest import G15_CONTRACT_MAP, G15_DATES, expected_g15_manifest  # noqa: E402
from ng_historical_prepare import (  # noqa: E402
    PrepareError,
    prepare_corpus,
    validate_prepared_index,
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


def build_fixture(root: Path):
    raw_paths = {}
    for index, day in enumerate(G15_DATES, 1):
        contract = G15_CONTRACT_MAP[day]
        definition_date = "2026-03-01" if day <= "20260319" else "2026-03-20"
        identity = {
            "dataset": "GLBX.MDP3",
            "publisher_id": 1,
            "instrument_id": contract["instrument_id"],
            "raw_symbol": contract["raw_symbol"],
            "definition_date": definition_date,
            "session_day": day,
        }
        trade = {
            **identity,
            "ts_event_s": float(index * 10),
            "price": 3.0,
            "size": 1,
            "side": "B",
            "sequence": 1,
        }
        mbo = {
            **identity,
            "ts_event_s": float(index * 10),
            "action": "A",
            "side": "B",
            "price": 3.0,
            "size": 1,
            "order_id": index,
            "flags": 128,
            "sequence": 1,
        }
        l1_path = root / f"l1_{day}.jsonl"
        mbo_path = root / f"mbo_{day}.jsonl"
        l1_path.write_text(json.dumps(trade) + "\n", encoding="utf-8")
        mbo_path.write_text(json.dumps(mbo) + "\n", encoding="utf-8")
        raw_paths[(day, "l1_trades")] = l1_path
        raw_paths[(day, "mbo")] = mbo_path
    manifest = build_manifest(
        l1_pattern=str(root / "l1_{day}.jsonl"),
        mbo_pattern=str(root / "mbo_{day}.jsonl"),
        publisher_id=1,
        definitions=definitions(),
    )
    return manifest, raw_paths


class PrepareTests(unittest.TestCase):
    def test_unknown_manifest_is_refused(self):
        with tempfile.TemporaryDirectory() as tempdir:
            with self.assertRaises(PrepareError):
                prepare_corpus(expected_g15_manifest(publisher_id=1), Path(tempdir) / "prepared")

    def test_ready_manifest_builds_fingerprinted_prepared_corpus(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest, _ = build_fixture(root)
            index = prepare_corpus(manifest, root / "prepared")
            validate_prepared_index(index)
            self.assertEqual(index["status"], "READY")
            self.assertEqual(index["source_count"], 26)
            self.assertEqual(len(index["prepared_corpus_fingerprint"]), 64)
            self.assertEqual(len(list((root / "prepared").glob("*.jsonl"))), 26)
            data_sources = [row for row in index["sources"] if row["source_kind"] != "definition"]
            self.assertEqual(len(data_sources), 24)
            self.assertTrue(all(row["normalization"]["raw_input_untouched"] for row in data_sources))

    def test_raw_object_change_after_inventory_is_rejected(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest, raw_paths = build_fixture(root)
            raw_paths[("20260316", "l1_trades")].write_text(
                raw_paths[("20260316", "l1_trades")].read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(PrepareError) as caught:
                prepare_corpus(manifest, root / "prepared")
            self.assertIn("raw size changed", str(caught.exception))
            self.assertFalse((root / "prepared").exists())

    def test_ready_entry_without_observed_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest, _ = build_fixture(root)
            manifest["entries"][0]["sha256"] = None
            with self.assertRaises(PrepareError) as caught:
                prepare_corpus(manifest, root / "prepared")
            self.assertIn("lacks observed size/SHA-256", str(caught.exception))

    def test_tampered_prepared_source_fails_validation(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            manifest, _ = build_fixture(root)
            index = prepare_corpus(manifest, root / "prepared")
            path = Path(next(row["path"] for row in index["sources"] if row["source_kind"] == "l1_trades"))
            path.write_text(path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
            with self.assertRaises(PrepareError):
                validate_prepared_index(index)


if __name__ == "__main__":
    unittest.main()
