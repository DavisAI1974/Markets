import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g16_historical_replay import (  # noqa: E402
    CANONICAL_DATES,
    _fixture_catalog,
    _fixture_inventory,
    _sha,
    _sha256,
    build_manifest,
    prepare_corpus,
)
from ng_g16_prepared_replay_gate import (  # noqa: E402
    EXPECTED_SOURCE_COUNT,
    G16PreparedReplayGateError,
    STATUS_READY,
    run_gate,
    validate_gate_artifact,
    validate_prepared_lineage,
)


class G16PreparedReplayGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        inventory, definition = _fixture_inventory(self.root)
        catalog = _fixture_catalog(inventory, definition)
        self.manifest = build_manifest(inventory, catalog)
        self.prepared = prepare_corpus(self.manifest, self.root / "prepared")
        self.prior = {"up": 0.4, "flat": 0.2, "down": 0.4}

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def refingerprint_prepared(value):
        value.pop("prepared_corpus_fingerprint", None)
        value["prepared_corpus_fingerprint"] = _sha(value)

    @staticmethod
    def refingerprint_replay(value):
        value.pop("fingerprint", None)
        value["fingerprint"] = _sha(value)

    @staticmethod
    def refingerprint_gate(value):
        value.pop("fingerprint", None)
        value["fingerprint"] = _sha(value)

    def rewrite_source(self, source, rows):
        path = Path(source["path"])
        path.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n", encoding="utf-8")
        source["size_bytes"] = path.stat().st_size
        source["sha256"] = _sha256(path)
        self.refingerprint_prepared(self.prepared)

    def test_valid_exact_prepared_replay_gate(self):
        replay, completion = run_gate(self.prepared, self.manifest, self.prior)
        self.assertEqual(completion["status"], STATUS_READY)
        self.assertEqual(completion["prepared_source_count"], EXPECTED_SOURCE_COUNT)
        self.assertEqual(completion["n_feature_states"], len(CANONICAL_DATES))
        self.assertEqual(completion["replay_fingerprint"], replay["fingerprint"])

    def test_sources_and_prior_remain_immutable(self):
        before = copy.deepcopy((self.prepared, self.manifest, self.prior))
        run_gate(self.prepared, self.manifest, self.prior)
        self.assertEqual((self.prepared, self.manifest, self.prior), before)

    def test_prepared_path_must_remain_inside_output_dir(self):
        broken = copy.deepcopy(self.prepared)
        source = next(row for row in broken["sources"] if row["source_kind"] == "l1_trades")
        outside = self.root / "outside.jsonl"
        shutil.copy2(source["path"], outside)
        source["path"] = str(outside)
        source["size_bytes"] = outside.stat().st_size
        source["sha256"] = _sha256(outside)
        self.refingerprint_prepared(broken)
        with self.assertRaises(G16PreparedReplayGateError):
            validate_prepared_lineage(broken, self.manifest)

    def test_manifest_entry_fingerprint_tamper_is_rejected(self):
        broken = copy.deepcopy(self.prepared)
        source = next(row for row in broken["sources"] if row["source_kind"] == "mbo")
        source["manifest_entry_fingerprint"] = "0" * 64
        self.refingerprint_prepared(broken)
        with self.assertRaises(G16PreparedReplayGateError):
            validate_prepared_lineage(broken, self.manifest)

    def test_raw_hash_lineage_tamper_is_rejected(self):
        broken = copy.deepcopy(self.prepared)
        source = next(row for row in broken["sources"] if row["source_kind"] == "l1_trades")
        source["raw_sha256"] = "f" * 64
        self.refingerprint_prepared(broken)
        with self.assertRaises(G16PreparedReplayGateError):
            validate_prepared_lineage(broken, self.manifest)

    def test_normalized_session_day_tamper_is_rejected_after_refingerprint(self):
        source = next(row for row in self.prepared["sources"] if row["source_kind"] == "l1_trades")
        rows = [json.loads(line) for line in Path(source["path"]).read_text(encoding="utf-8").splitlines()]
        for row in rows:
            row["session_day"] = CANONICAL_DATES[1]
        self.rewrite_source(source, rows)
        with self.assertRaises(G16PreparedReplayGateError):
            validate_prepared_lineage(self.prepared, self.manifest)

    def test_normalized_identity_tamper_is_rejected_after_refingerprint(self):
        source = next(row for row in self.prepared["sources"] if row["source_kind"] == "l1_trades")
        rows = [json.loads(line) for line in Path(source["path"]).read_text(encoding="utf-8").splitlines()]
        for row in rows:
            row["raw_symbol"] = "NGJ26"
        self.rewrite_source(source, rows)
        with self.assertRaises(G16PreparedReplayGateError):
            validate_prepared_lineage(self.prepared, self.manifest)

    def test_backward_normalized_source_is_rejected(self):
        source = next(row for row in self.prepared["sources"] if row["source_kind"] == "l1_trades")
        rows = [json.loads(line) for line in Path(source["path"]).read_text(encoding="utf-8").splitlines()]
        rows[0], rows[1] = rows[1], rows[0]
        self.rewrite_source(source, rows)
        with self.assertRaises(G16PreparedReplayGateError):
            validate_prepared_lineage(self.prepared, self.manifest)

    def test_definition_identity_tamper_is_rejected(self):
        source = next(row for row in self.prepared["sources"] if row["source_kind"] == "definition")
        rows = [json.loads(line) for line in Path(source["path"]).read_text(encoding="utf-8").splitlines()]
        rows[0]["instrument_id"] = 1008
        self.rewrite_source(source, rows)
        with self.assertRaises(G16PreparedReplayGateError):
            validate_prepared_lineage(self.prepared, self.manifest)

    def test_processed_record_tamper_is_rejected_even_after_refingerprint(self):
        replay, completion = run_gate(self.prepared, self.manifest, self.prior)
        replay["processed_records"]["trade"] += 1
        self.refingerprint_replay(replay)
        with self.assertRaises(G16PreparedReplayGateError):
            validate_gate_artifact(
                completion,
                prepared_index=self.prepared,
                manifest=self.manifest,
                replay=replay,
                blind_prior=self.prior,
            )

    def test_completed_boundary_tamper_is_rejected_even_after_refingerprint(self):
        replay, completion = run_gate(self.prepared, self.manifest, self.prior)
        replay["completed_mbo_event_boundaries"] += 1
        self.refingerprint_replay(replay)
        with self.assertRaises(G16PreparedReplayGateError):
            validate_gate_artifact(
                completion,
                prepared_index=self.prepared,
                manifest=self.manifest,
                replay=replay,
                blind_prior=self.prior,
            )

    def test_hidden_sequence_gap_is_rejected(self):
        replay, completion = run_gate(self.prepared, self.manifest, self.prior)
        replay["sequence_gaps"] = [{"source_id": "synthetic", "missing": 1}]
        self.refingerprint_replay(replay)
        with self.assertRaises(G16PreparedReplayGateError):
            validate_gate_artifact(
                completion,
                prepared_index=self.prepared,
                manifest=self.manifest,
                replay=replay,
                blind_prior=self.prior,
            )

    def test_completion_link_tamper_is_rejected_after_refingerprint(self):
        replay, completion = run_gate(self.prepared, self.manifest, self.prior)
        completion["prepared_source_fingerprints"][0] = "1" * 64
        self.refingerprint_gate(completion)
        with self.assertRaises(G16PreparedReplayGateError):
            validate_gate_artifact(
                completion,
                prepared_index=self.prepared,
                manifest=self.manifest,
                replay=replay,
                blind_prior=self.prior,
            )

    def test_authority_escalation_is_rejected_after_refingerprint(self):
        replay, completion = run_gate(self.prepared, self.manifest, self.prior)
        completion["execution_authority"] = True
        self.refingerprint_gate(completion)
        with self.assertRaises(G16PreparedReplayGateError):
            validate_gate_artifact(
                completion,
                prepared_index=self.prepared,
                manifest=self.manifest,
                replay=replay,
                blind_prior=self.prior,
            )

    def test_deterministic_gate_artifact(self):
        replay_one, completion_one = run_gate(self.prepared, self.manifest, self.prior)
        replay_two, completion_two = run_gate(self.prepared, self.manifest, self.prior)
        self.assertEqual(replay_one, replay_two)
        self.assertEqual(completion_one, completion_two)

    def test_permanent_shadow_tastytrade_and_no_options_controls(self):
        _, completion = run_gate(self.prepared, self.manifest, self.prior)
        self.assertFalse(completion["actual_outcomes_used"])
        self.assertFalse(completion["paid_live_data_assumed"])
        self.assertFalse(completion["random_shuffle_used"])
        self.assertTrue(completion["one_signal_authority_preserved"])
        self.assertTrue(completion["blind_forecast_immutable"])
        self.assertFalse(completion["may_change_g16_blind_prior"])
        self.assertFalse(completion["may_change_posterior"])
        self.assertFalse(completion["may_update_ng_brain"])
        self.assertFalse(completion["execution_authority"])
        self.assertEqual(completion["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(completion["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertFalse(completion["options_lane_started"])


if __name__ == "__main__":
    unittest.main()
