import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g15_exact_replay_completion import (  # noqa: E402
    READY,
    READY_WITH_STAND_DOWNS,
    ExactReplayCompletionError,
    _fixture,
    build_completion,
    validate_completion,
)
from ng_rt_feature_state import feature_fingerprint  # noqa: E402


class ExactReplayCompletionTests(unittest.TestCase):
    def setUp(self):
        self.bridge, self.prepared, self.replay, self.anchor, self.prior = _fixture()

    def build(self, **overrides):
        values = {
            "bridge": self.bridge,
            "prepared_index": self.prepared,
            "replay": self.replay,
            "anchor": self.anchor,
            "blind_prior": self.prior,
            "verify_prepared_files": False,
        }
        values.update(overrides)
        return build_completion(**values)

    def test_exact_chain_authorizes_g15_shadow_refinement(self):
        result = self.build()
        self.assertEqual(result["status"], READY)
        self.assertEqual(
            [row["date"] for row in result["days"]],
            [
                "20260315",
                "20260316",
                "20260317",
                "20260318",
                "20260319",
                "20260320",
                "20260322",
                "20260323",
                "20260324",
                "20260325",
                "20260326",
                "20260327",
            ],
        )
        self.assertTrue(result["g15_shadow_refinement_authorized"])
        self.assertFalse(result["g16_authorized"])
        validate_completion(result)

    def test_sources_remain_immutable(self):
        before = copy.deepcopy((self.bridge, self.prepared, self.replay, self.anchor, self.prior))
        self.build()
        self.assertEqual((self.bridge, self.prepared, self.replay, self.anchor, self.prior), before)

    def test_bridge_must_be_exact_basis_ready(self):
        bad = copy.deepcopy(self.bridge)
        bad["manifest"]["basis_status"] = "MBO_SPECIFIC_LEG_READY_L1_BASIS_BLOCKED"
        with self.assertRaises(ExactReplayCompletionError):
            self.build(bridge=bad)

    def test_prepared_manifest_must_match_bridge(self):
        from ng_g15_exact_replay_completion import _fingerprint

        bad = copy.deepcopy(self.prepared)
        bad["manifest_fingerprint"] = "0" * 64
        payload = dict(bad)
        payload.pop("prepared_corpus_fingerprint", None)
        bad["prepared_corpus_fingerprint"] = _fingerprint(payload)
        with self.assertRaises(ExactReplayCompletionError):
            self.build(prepared_index=bad)

    def test_prepared_source_count_must_be_26(self):
        from ng_g15_exact_replay_completion import _fingerprint

        bad = copy.deepcopy(self.prepared)
        bad["source_count"] = 25
        payload = dict(bad)
        payload.pop("prepared_corpus_fingerprint", None)
        bad["prepared_corpus_fingerprint"] = _fingerprint(payload)
        with self.assertRaises(ExactReplayCompletionError):
            self.build(prepared_index=bad)

    def test_replay_must_match_prepared_corpus(self):
        bad = copy.deepcopy(self.replay)
        bad["prepared_corpus_fingerprint"] = "f" * 64
        with self.assertRaises(ExactReplayCompletionError):
            self.build(replay=bad)

    def test_replay_must_use_locked_blind_prior(self):
        with self.assertRaises(ExactReplayCompletionError):
            self.build(blind_prior={"up": 0.7, "flat": 0.1, "down": 0.2})

    def test_missing_session_state_blocks(self):
        bad = copy.deepcopy(self.replay)
        stream = bad["streams"][0]
        stream["states"] = [
            state for state in stream["states"] if state["session_day"] != "20260318"
        ]
        stream["n_states"] = len(stream["states"])
        bad["completed_mbo_event_boundaries"] -= 1
        with self.assertRaisesRegex(ExactReplayCompletionError, "20260318"):
            self.build(replay=bad)

    def test_duplicate_records_block(self):
        bad = copy.deepcopy(self.replay)
        bad["duplicate_records"] = [
            {"event_type": "trade", "raw_symbol": "NGJ26", "ts_event_s": 1100.0}
        ]
        with self.assertRaisesRegex(ExactReplayCompletionError, "duplicate"):
            self.build(replay=bad)

    def test_hidden_sequence_gap_blocks(self):
        bad = copy.deepcopy(self.replay)
        bad["sequence_gaps"] = [{"raw_symbol": "NGJ26", "missing_count": 1}]
        with self.assertRaisesRegex(ExactReplayCompletionError, "visible collector stand-down"):
            self.build(replay=bad)

    def test_visible_sequence_gap_is_ready_with_stand_downs(self):
        bad = copy.deepcopy(self.replay)
        bad["sequence_gaps"] = [{"raw_symbol": "NGJ26", "missing_count": 1}]
        state = bad["streams"][0]["states"][0]
        state["availability"] = {
            "flow_update_allowed": False,
            "queue_update_allowed": False,
            "refine_update_allowed": False,
            "stand_down_reasons": ["collector_skipped_records"],
        }
        state["feature_fingerprint"] = feature_fingerprint(state)
        result = self.build(replay=bad)
        self.assertEqual(result["status"], READY_WITH_STAND_DOWNS)
        self.assertGreater(result["stand_down_event_count"], 0)

    def test_pre_anchor_state_blocks(self):
        bad = copy.deepcopy(self.replay)
        state = bad["streams"][0]["states"][0]
        state["as_of_event_s"] = 950.0
        state["decision_cutoff_s"] = 950.0
        state["feature_fingerprint"] = feature_fingerprint(state)
        with self.assertRaises(ExactReplayCompletionError):
            self.build(replay=bad)

    def test_wrong_contract_state_blocks(self):
        bad = copy.deepcopy(self.replay)
        state = bad["streams"][0]["states"][0]
        state["instrument"]["instrument_id"] = 996
        state["instrument"]["raw_symbol"] = "NGK26"
        state["feature_fingerprint"] = feature_fingerprint(state)
        with self.assertRaises(ExactReplayCompletionError):
            self.build(replay=bad)

    def test_completion_tampering_is_rejected(self):
        result = self.build()
        result["g16_authorized"] = True
        with self.assertRaises(ExactReplayCompletionError):
            validate_completion(result)

    def test_completion_never_gains_outcome_brain_or_execution_authority(self):
        result = self.build()
        self.assertFalse(result["actual_outcomes_used"])
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["may_change_blind_prior"])
        self.assertFalse(result["may_change_blind_forecast"])
        self.assertFalse(result["may_change_posterior"])
        self.assertFalse(result["execution_authority"])


if __name__ == "__main__":
    unittest.main()
