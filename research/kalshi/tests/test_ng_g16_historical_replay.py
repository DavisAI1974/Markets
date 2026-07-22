import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g16_historical_replay import (  # noqa: E402
    CANONICAL_DATES,
    INSTRUMENT_ID,
    RAW_SYMBOL,
    G16HistoricalReplayError,
    _fixture_catalog,
    _fixture_inventory,
    _sha,
    _sha256,
    build_catalog_template,
    build_manifest,
    prepare_corpus,
    replay_prepared,
    validate_manifest,
    validate_prepared_index,
    validate_replay_output,
)


class G16HistoricalReplayTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.inventory, self.definition = _fixture_inventory(self.root)
        self.catalog = _fixture_catalog(self.inventory, self.definition)
        self.prior = {"up": 0.4, "flat": 0.2, "down": 0.4}

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def refingerprint(value, field="fingerprint"):
        value.pop(field, None)
        value[field] = _sha(value)

    def test_unknown_template_never_invents_presence(self):
        template = build_catalog_template(self.inventory)
        self.assertEqual(template["status"], "UNKNOWN")
        self.assertIsNone(template["definition"])
        self.assertEqual(len(template["sources"]), len(CANONICAL_DATES) * 2)
        self.assertTrue(all(row["status"] == "UNKNOWN" for row in template["sources"]))
        self.assertFalse(template["paid_live_data_assumed"])

    def test_manifest_requires_matched_basis(self):
        broken = copy.deepcopy(self.inventory)
        broken[0]["l1_instrument_id"] = [1008]
        broken[0]["l1_raw_symbol"] = "NGJ26"
        broken[0]["l1_basis_correct"] = False
        catalog = _fixture_catalog(broken, self.definition)
        with self.assertRaises(G16HistoricalReplayError):
            build_manifest(broken, catalog)

    def test_manifest_has_exact_22_lanes_and_one_definition(self):
        manifest = build_manifest(self.inventory, self.catalog)
        report = validate_manifest(manifest)
        self.assertEqual(report["status"], "READY")
        self.assertTrue(report["can_replay_all_g16"])
        self.assertEqual(len(manifest["entries"]), 22)
        self.assertEqual(manifest["definition"]["raw_symbol"], RAW_SYMBOL)
        self.assertEqual(manifest["definition"]["instrument_id"], INSTRUMENT_ID)

    def test_duplicate_or_missing_catalog_lane_is_rejected(self):
        duplicate = copy.deepcopy(self.catalog)
        duplicate["sources"].append(copy.deepcopy(duplicate["sources"][0]))
        self.refingerprint(duplicate)
        with self.assertRaises(G16HistoricalReplayError):
            build_manifest(self.inventory, duplicate)

        missing = copy.deepcopy(self.catalog)
        missing["sources"].pop()
        self.refingerprint(missing)
        with self.assertRaises(G16HistoricalReplayError):
            build_manifest(self.inventory, missing)

    def test_wrong_contract_or_definition_is_rejected(self):
        wrong_source = copy.deepcopy(self.catalog)
        wrong_source["sources"][0]["raw_symbol"] = "NGJ26"
        self.refingerprint(wrong_source)
        with self.assertRaises(G16HistoricalReplayError):
            build_manifest(self.inventory, wrong_source)

        wrong_definition = copy.deepcopy(self.catalog)
        wrong_definition["definition"]["instrument_id"] = 1008
        self.refingerprint(wrong_definition)
        with self.assertRaises(G16HistoricalReplayError):
            build_manifest(self.inventory, wrong_definition)

    def test_catalog_event_range_must_match_basis_inventory(self):
        shifted = copy.deepcopy(self.catalog)
        shifted["sources"][0]["event_start_s"] += 1
        self.refingerprint(shifted)
        with self.assertRaises(G16HistoricalReplayError):
            build_manifest(self.inventory, shifted)

    def test_prepare_and_replay_all_11_days(self):
        manifest = build_manifest(self.inventory, self.catalog)
        prepared = prepare_corpus(manifest, self.root / "prepared")
        validate_prepared_index(prepared)
        result = replay_prepared(prepared, manifest, self.prior)
        validate_replay_output(result)
        states = [state for stream in result["streams"] for state in stream["states"]]
        self.assertEqual(sorted({state["session_day"] for state in states}), sorted(CANONICAL_DATES))
        self.assertEqual(result["completed_mbo_event_boundaries"], len(CANONICAL_DATES))
        self.assertEqual(result["processed_records"]["trade"], len(CANONICAL_DATES) * 6)
        self.assertEqual(result["source_count"], 23)

    def test_blind_prior_and_sources_are_immutable(self):
        inventory_before = copy.deepcopy(self.inventory)
        catalog_before = copy.deepcopy(self.catalog)
        prior_before = copy.deepcopy(self.prior)
        manifest = build_manifest(self.inventory, self.catalog)
        prepared = prepare_corpus(manifest, self.root / "prepared")
        replay_prepared(prepared, manifest, self.prior)
        self.assertEqual(self.inventory, inventory_before)
        self.assertEqual(self.catalog, catalog_before)
        self.assertEqual(self.prior, prior_before)

    def test_raw_file_tamper_blocks_preparation(self):
        manifest = build_manifest(self.inventory, self.catalog)
        first_path = Path(self.inventory[0]["_fixture_paths"]["l1_trades"])
        first_path.write_text(first_path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
        with self.assertRaises(G16HistoricalReplayError):
            prepare_corpus(manifest, self.root / "prepared")

    def test_prepared_file_tamper_blocks_replay(self):
        manifest = build_manifest(self.inventory, self.catalog)
        prepared = prepare_corpus(manifest, self.root / "prepared")
        path = Path(prepared["sources"][1]["path"])
        path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        with self.assertRaises(G16HistoricalReplayError):
            replay_prepared(prepared, manifest, self.prior)

    def test_backward_raw_source_is_rejected_during_normalization(self):
        path = Path(self.inventory[0]["_fixture_paths"]["l1_trades"])
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        rows[0], rows[1] = rows[1], rows[0]
        path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        self.inventory[0]["l1_bytes"] = path.stat().st_size
        self.catalog = _fixture_catalog(self.inventory, self.definition)
        manifest = build_manifest(self.inventory, self.catalog)
        with self.assertRaises(Exception):
            prepare_corpus(manifest, self.root / "prepared")

    def test_missing_f_last_blocks_complete_session_coverage(self):
        path = Path(self.inventory[-1]["_fixture_paths"]["mbo"])
        row = json.loads(path.read_text(encoding="utf-8"))
        row["flags"] = 0
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
        self.inventory[-1]["mbo_bytes"] = path.stat().st_size
        self.catalog = _fixture_catalog(self.inventory, self.definition)
        manifest = build_manifest(self.inventory, self.catalog)
        prepared = prepare_corpus(manifest, self.root / "prepared")
        with self.assertRaises(G16HistoricalReplayError):
            replay_prepared(prepared, manifest, self.prior)

    def test_queue_stand_down_remains_visible(self):
        stood_down = copy.deepcopy(self.inventory)
        stood_down[3]["queue_usable"] = False
        catalog = _fixture_catalog(stood_down, self.definition)
        manifest = build_manifest(stood_down, catalog)
        prepared = prepare_corpus(manifest, self.root / "prepared")
        result = replay_prepared(prepared, manifest, self.prior)
        self.assertEqual(result["status"], "READY_WITH_STAND_DOWNS")
        self.assertIn(CANONICAL_DATES[3], result["queue_stand_down_days"])
        self.assertIn(CANONICAL_DATES[3], result["stand_down_days"])

    def test_output_tamper_is_detected(self):
        manifest = build_manifest(self.inventory, self.catalog)
        prepared = prepare_corpus(manifest, self.root / "prepared")
        result = replay_prepared(prepared, manifest, self.prior)
        result["processed_records"]["trade"] += 1
        with self.assertRaises(G16HistoricalReplayError):
            validate_replay_output(result)

    def test_permanent_shadow_and_no_outcome_authority(self):
        manifest = build_manifest(self.inventory, self.catalog)
        prepared = prepare_corpus(manifest, self.root / "prepared")
        result = replay_prepared(prepared, manifest, self.prior)
        for artifact in (manifest, prepared, result):
            self.assertFalse(artifact["actual_outcomes_used"])
            self.assertFalse(artifact["paid_live_data_assumed"])
            self.assertFalse(artifact["may_change_g16_blind_prior"])
            self.assertFalse(artifact["may_update_ng_brain"])
            self.assertFalse(artifact["execution_authority"])


if __name__ == "__main__":
    unittest.main()
