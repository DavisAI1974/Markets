import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_historical_inventory import build_manifest  # noqa: E402
from ng_historical_manifest import G15_CONTRACT_MAP, G15_DATES  # noqa: E402
from ng_historical_prepare import prepare_corpus  # noqa: E402
from ng_historical_replay_prepared import (  # noqa: E402
    PreparedReplayError,
    prepared_source_paths,
    replay_prepared_index,
)


def canonical_fingerprint(value):
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
    for position, day in enumerate(G15_DATES, 1):
        contract = G15_CONTRACT_MAP[day]
        definition_date = "2026-03-01" if contract["raw_symbol"] == "NGJ26" else "2026-03-20"
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
            "ts_event_s": float(position * 10),
            "price": 3.0,
            "size": 1,
            "side": "B",
            "sequence": 1,
        }
        mbo = {
            **identity,
            "ts_event_s": float(position * 10),
            "action": "A",
            "side": "B",
            "price": 3.0,
            "size": 1,
            "order_id": position,
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
    index = prepare_corpus(manifest, root / "prepared")
    return manifest, index


def resign(index):
    payload = dict(index)
    payload.pop("prepared_corpus_fingerprint", None)
    index["prepared_corpus_fingerprint"] = canonical_fingerprint(payload)


class PreparedReplayTests(unittest.TestCase):
    def test_index_replays_all_sources_without_manual_input_list(self):
        with tempfile.TemporaryDirectory() as tempdir:
            manifest, index = build_fixture(Path(tempdir))
            prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
            original = copy.deepcopy(prior)
            result = replay_prepared_index(index, manifest=manifest, blind_prior=prior)
            self.assertEqual(result["prepared_source_count"], 26)
            self.assertEqual(result["completed_mbo_event_boundaries"], len(G15_DATES))
            self.assertEqual(result["processed_records"], {"trade": 12, "mbo": 12, "definition": 2})
            self.assertEqual(prior, original)

    def test_manifest_fingerprint_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tempdir:
            manifest, index = build_fixture(Path(tempdir))
            changed = copy.deepcopy(manifest)
            changed["note"] = "different observed inventory"
            with self.assertRaises(PreparedReplayError):
                replay_prepared_index(
                    index,
                    manifest=changed,
                    blind_prior={"up": 0.4, "flat": 0.2, "down": 0.4},
                )

    def test_missing_canonical_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tempdir:
            _, index = build_fixture(Path(tempdir))
            index["sources"] = [
                row for row in index["sources"]
                if not (row["day"] == "20260316" and row["source_kind"] == "mbo")
            ]
            index["source_count"] = len(index["sources"])
            resign(index)
            with self.assertRaises(PreparedReplayError) as caught:
                prepared_source_paths(index)
            self.assertIn("coverage mismatch", str(caught.exception))

    def test_duplicate_lane_is_rejected(self):
        with tempfile.TemporaryDirectory() as tempdir:
            _, index = build_fixture(Path(tempdir))
            source = next(row for row in index["sources"] if row["source_kind"] == "l1_trades")
            duplicate = copy.deepcopy(source)
            duplicate_path = Path(index["output_dir"]) / "duplicate.jsonl"
            duplicate_path.write_bytes(Path(source["path"]).read_bytes())
            duplicate["path"] = str(duplicate_path)
            duplicate["size_bytes"] = duplicate_path.stat().st_size
            duplicate["sha256"] = hashlib.sha256(duplicate_path.read_bytes()).hexdigest()
            index["sources"].append(duplicate)
            index["source_count"] = len(index["sources"])
            resign(index)
            with self.assertRaises(PreparedReplayError) as caught:
                prepared_source_paths(index)
            self.assertIn("duplicate prepared source", str(caught.exception))

    def test_source_outside_declared_output_dir_is_rejected(self):
        with tempfile.TemporaryDirectory() as tempdir:
            root = Path(tempdir)
            _, index = build_fixture(root)
            source = next(row for row in index["sources"] if row["source_kind"] == "mbo")
            external = root / "external.jsonl"
            external.write_bytes(Path(source["path"]).read_bytes())
            source["path"] = str(external)
            source["size_bytes"] = external.stat().st_size
            source["sha256"] = hashlib.sha256(external.read_bytes()).hexdigest()
            resign(index)
            with self.assertRaises(PreparedReplayError) as caught:
                prepared_source_paths(index)
            self.assertIn("escapes output_dir", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
