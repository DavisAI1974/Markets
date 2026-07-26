import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

import ng_g15_prepared_normalized_identity_guard as guard  # noqa: E402
import ng_historical_refinement_executor_v27 as executor  # noqa: E402
import ng_historical_refinement_readiness_v31 as readiness  # noqa: E402
from ng_historical_manifest import G15_CONTRACT_MAP, G15_DATES, SOURCE_KINDS  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PreparedIdentityFixture:
    def __init__(self, root: Path):
        self.root = root
        definitions = {
            "NGJ26": {
                "dataset": "GLBX.MDP3",
                "publisher_id": 1,
                "instrument_id": 1008,
                "raw_symbol": "NGJ26",
                "definition_date": "2026-03-01",
                "definition_start_s": 0.0,
                "definition_end_s": 1000.0,
            },
            "NGK26": {
                "dataset": "GLBX.MDP3",
                "publisher_id": 1,
                "instrument_id": 996,
                "raw_symbol": "NGK26",
                "definition_date": "2026-03-20",
                "definition_start_s": 0.0,
                "definition_end_s": 1000.0,
            },
        }
        entries = []
        sources = []
        for symbol, definition in definitions.items():
            day = G15_DATES[0] if symbol == "NGJ26" else "20260320"
            row = {
                "schema": "ng_normalized_event.v1",
                "event_type": "definition",
                **{name: definition[name] for name in (
                    "dataset", "publisher_id", "instrument_id", "raw_symbol", "definition_date"
                )},
                "session_day": day,
                "ts_event_s": 0.0,
                "source_sequence": 1,
                "ingest_sequence": 1,
            }
            path = root / f"definition_{symbol}.jsonl"
            path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
            sources.append(
                {
                    "day": day,
                    "source_kind": "definition",
                    "event_type": "definition",
                    "path": str(path),
                    "record_count": 1,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )

        for day in G15_DATES:
            contract = G15_CONTRACT_MAP[day]
            definition = definitions[contract["raw_symbol"]]
            for lane in SOURCE_KINDS:
                event_type = "trade" if lane == "l1_trades" else "mbo"
                ts = float(10 + len(entries))
                entry = {
                    "day": day,
                    "source_kind": lane,
                    "status": "PRESENT",
                    "dataset": "GLBX.MDP3",
                    "publisher_id": 1,
                    "instrument_id": contract["instrument_id"],
                    "raw_symbol": contract["raw_symbol"],
                    "definition_date": definition["definition_date"],
                    "definition_start_s": 0.0,
                    "definition_end_s": 1000.0,
                    "event_start_s": ts,
                    "event_end_s": ts,
                }
                entries.append(entry)
                row = {
                    "schema": "ng_normalized_event.v1",
                    "event_type": event_type,
                    "dataset": entry["dataset"],
                    "publisher_id": 1,
                    "instrument_id": entry["instrument_id"],
                    "raw_symbol": entry["raw_symbol"],
                    "definition_date": entry["definition_date"],
                    "session_day": day,
                    "ts_event_s": ts,
                    "source_sequence": 1,
                    "ingest_sequence": 1,
                }
                if event_type == "trade":
                    row.update(price=3.0, size=1, side="B")
                else:
                    row.update(action="A", side="B", size=1, order_id=1, price=3.0, flags=1)
                path = root / f"{day}_{lane}.jsonl"
                path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
                sources.append(
                    {
                        "day": day,
                        "source_kind": lane,
                        "event_type": event_type,
                        "path": str(path),
                        "record_count": 1,
                        "event_start_s": ts,
                        "event_end_s": ts,
                        "size_bytes": path.stat().st_size,
                        "sha256": sha256(path),
                    }
                )

        self.bridge = {
            "fingerprint": "b" * 64,
            "manifest": {"definitions": definitions, "entries": entries},
        }
        self.prepared = {
            "prepared_corpus_fingerprint": "p" * 64,
            "source_count": len(sources),
            "sources": sources,
        }

    def rewrite_row(self, day: str, lane: str, update):
        source = next(
            row for row in self.prepared["sources"]
            if row.get("day") == day and row.get("source_kind") == lane
        )
        path = Path(source["path"])
        row = json.loads(path.read_text(encoding="utf-8"))
        update(row)
        path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
        source["size_bytes"] = path.stat().st_size
        source["sha256"] = sha256(path)


class PreparedNormalizedIdentityGuardTests(unittest.TestCase):
    def build(self, fixture):
        with mock.patch.object(guard, "validate_bridge_output"), mock.patch.object(
            guard, "validate_prepared_index"
        ):
            return guard.build_guard(fixture.bridge, fixture.prepared)

    def test_valid_prepared_corpus_is_attested(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PreparedIdentityFixture(Path(temporary))
            result = self.build(fixture)
            self.assertEqual(result["status"], guard.READY)
            self.assertEqual(result["source_count"], 26)
            self.assertTrue(result["all_rows_match_exact_manifest_identity"])
            self.assertTrue(result["definitions_precede_trade_and_mbo_replay"])

    def test_missing_publisher_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PreparedIdentityFixture(Path(temporary))
            fixture.rewrite_row(G15_DATES[0], "l1_trades", lambda row: row.pop("publisher_id"))
            result = self.build(fixture)
            self.assertEqual(result["status"], guard.BLOCKED)
            self.assertTrue(any("PUBLISHER" in item or "INVALID" in item for item in result["blockers"]))

    def test_event_outside_definition_period_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PreparedIdentityFixture(Path(temporary))
            fixture.rewrite_row(G15_DATES[0], "mbo", lambda row: row.__setitem__("ts_event_s", 1001.0))
            result = self.build(fixture)
            self.assertIn("EVENT_OUTSIDE_DEFINITION_PERIOD:1", result["blockers"])

    def test_wrong_lane_event_type_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PreparedIdentityFixture(Path(temporary))
            fixture.rewrite_row(G15_DATES[0], "l1_trades", lambda row: row.__setitem__("event_type", "mbo"))
            result = self.build(fixture)
            self.assertIn("NORMALIZED_EVENT_TYPE_MISMATCH:1", result["blockers"])

    def test_missing_definition_source_blocks(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PreparedIdentityFixture(Path(temporary))
            fixture.prepared["sources"] = [
                row for row in fixture.prepared["sources"]
                if not (row.get("source_kind") == "definition" and row.get("day") == G15_DATES[0])
            ]
            fixture.prepared["source_count"] = len(fixture.prepared["sources"])
            result = self.build(fixture)
            self.assertIn("PREPARED_DEFINITION_SOURCE_COUNT_MISMATCH", result["blockers"])
            self.assertIn("DEFINITION_NOT_PREPARED_BEFORE_LANE", result["blockers"])

    def test_inputs_remain_immutable(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PreparedIdentityFixture(Path(temporary))
            before = copy.deepcopy((fixture.bridge, fixture.prepared))
            self.build(fixture)
            self.assertEqual((fixture.bridge, fixture.prepared), before)

    def test_refingerprinted_authority_escalation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = PreparedIdentityFixture(Path(temporary))
            result = self.build(fixture)
            result["execution_authority"] = True
            result.pop("fingerprint")
            result["fingerprint"] = guard._fingerprint(result)
            with self.assertRaises(guard.PreparedNormalizedIdentityGuardError):
                guard.validate_guard(result, verify_files=False)


class ReadinessV31Tests(unittest.TestCase):
    def test_stage_is_between_catalog_and_replay(self):
        keys = [spec.key for spec in readiness.STAGES]
        index = keys.index("g15_prepared_normalized_identity")
        self.assertEqual(keys[index - 1 : index + 2], [
            "replay_catalog_export", "g15_prepared_normalized_identity", "g15_exact_replay"
        ])
        self.assertTrue(readiness.STAGES[index].pre_outcome)

    def test_readiness_selftest(self):
        self.assertEqual(readiness.selftest(), 0)

    def test_executor_uses_v31_guard_entrypoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = executor.build_plan(root / "artifacts", root)
            keys = [step["key"] for step in plan["stages"]]
            index = keys.index("g15_prepared_normalized_identity")
            self.assertEqual(
                plan["stages"][index]["suggested_entrypoint"],
                ["python", "ng_g15_prepared_normalized_identity_guard.py", "build"],
            )
            self.assertFalse(plan["stages"][index]["requires_fixed_outcomes"])
            self.assertFalse(plan["random_shuffle_used"])
            self.assertFalse(plan["may_update_ng_brain"])
            self.assertEqual(plan["cme_event_contracts_mode"], "SHADOW")
            self.assertEqual(plan["brokerage_contract"], "tastytrade_not_ibkr")
            self.assertFalse(plan["options_lane_started"])

    def test_removed_guard_stage_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            plan = executor.build_plan(root / "artifacts", root)
            plan["stages"] = [
                step for step in plan["stages"]
                if step["key"] != "g15_prepared_normalized_identity"
            ]
            plan.pop("fingerprint", None)
            with self.assertRaises(executor.HistoricalRefinementExecutionError):
                executor.validate_plan(plan)


if __name__ == "__main__":
    unittest.main()
