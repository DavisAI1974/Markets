import copy
import sys
import tempfile
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g16_blind_wall import G16_DATES  # noqa: E402
from ng_g16_exact_causal_pipeline import (  # noqa: E402
    G16ExactCausalPipelineError,
    _fp,
    build_exact_causal_pipeline,
    validate_pipeline_artifacts,
)
from ng_g16_historical_replay import (  # noqa: E402
    _fixture_catalog,
    _fixture_inventory,
    build_manifest,
    prepare_corpus,
    replay_prepared,
)
from ng_g16_shadow_gate import (  # noqa: E402
    _fixture_blind_state,
    _fixture_forecast,
    _fixture_registry,
)
from ng_rt_feature_state import feature_fingerprint  # noqa: E402


class G16ExactCausalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        inventory, definition = _fixture_inventory(self.root)
        manifest = build_manifest(inventory, _fixture_catalog(inventory, definition))
        prepared = prepare_corpus(manifest, self.root / "prepared")
        self.prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
        self.replay = replay_prepared(prepared, manifest, self.prior)
        self.forecast = _fixture_forecast()
        self.safe_state = _fixture_blind_state()
        self.registry = _fixture_registry()

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def refingerprint_replay(replay):
        replay.pop("fingerprint", None)
        replay["fingerprint"] = _fp(replay)

    @staticmethod
    def all_states(replay):
        return [state for stream in replay["streams"] for state in stream["states"]]

    def build(self):
        return build_exact_causal_pipeline(
            self.replay,
            self.prior,
            self.forecast,
            self.safe_state,
            self.registry,
        )

    def test_complete_exact_pipeline_covers_all_g16_days(self):
        artifacts = self.build()
        completion = artifacts["completion"]
        self.assertEqual(list(completion["days"]), list(G16_DATES))
        self.assertEqual(completion["n_days"], len(G16_DATES))
        self.assertEqual(completion["n_states"], completion["n_outputs"])
        self.assertEqual(completion["next_permitted_stage"], "OUTCOME_BLIND_G16_CURVE_ADAPTER")

    def test_all_candidates_are_pre_requested_without_g16_outcomes(self):
        artifacts = self.build()
        expected = artifacts["plan"]["candidate_ids"]
        self.assertTrue(expected)
        for token in artifacts["authorization_stream"]["authorizations"]:
            self.assertEqual(token["authorized_candidate_ids"], expected)
        self.assertEqual(
            artifacts["completion"]["candidate_request_policy"],
            "ALL_PRE_REGISTERED_CANDIDATES_ON_EVERY_STATE_BEFORE_G16_OUTCOME_ACCESS",
        )
        self.assertFalse(artifacts["completion"]["actual_g16_outcomes_used"])

    def test_sources_are_immutable(self):
        before = copy.deepcopy((self.replay, self.prior, self.forecast, self.safe_state, self.registry))
        self.build()
        self.assertEqual((self.replay, self.prior, self.forecast, self.safe_state, self.registry), before)

    def test_locked_prior_mismatch_is_rejected(self):
        with self.assertRaises(G16ExactCausalPipelineError):
            build_exact_causal_pipeline(
                self.replay,
                {"up": 0.5, "flat": 0.2, "down": 0.3},
                self.forecast,
                self.safe_state,
                self.registry,
            )

    def test_replay_fingerprint_tamper_is_rejected(self):
        broken = copy.deepcopy(self.replay)
        broken["processed_records"]["trade"] += 1
        with self.assertRaises(G16ExactCausalPipelineError):
            build_exact_causal_pipeline(broken, self.prior, self.forecast, self.safe_state, self.registry)

    def test_replay_must_remain_single_exact_contract_stream(self):
        broken = copy.deepcopy(self.replay)
        broken["streams"].append(copy.deepcopy(broken["streams"][0]))
        self.refingerprint_replay(broken)
        with self.assertRaises(G16ExactCausalPipelineError):
            build_exact_causal_pipeline(broken, self.prior, self.forecast, self.safe_state, self.registry)

    def test_feature_state_must_reference_locked_prior(self):
        broken = copy.deepcopy(self.replay)
        state = self.all_states(broken)[0]
        state["blind_prior_fingerprint"] = "0" * 64
        state["feature_fingerprint"] = feature_fingerprint(state)
        self.refingerprint_replay(broken)
        with self.assertRaises(G16ExactCausalPipelineError):
            build_exact_causal_pipeline(broken, self.prior, self.forecast, self.safe_state, self.registry)

    def test_backward_state_order_is_rejected(self):
        broken = copy.deepcopy(self.replay)
        states = broken["streams"][0]["states"]
        states[0], states[1] = states[1], states[0]
        self.refingerprint_replay(broken)
        with self.assertRaises(G16ExactCausalPipelineError):
            build_exact_causal_pipeline(broken, self.prior, self.forecast, self.safe_state, self.registry)

    def test_no_registered_candidates_blocks_g16_start(self):
        registry = copy.deepcopy(self.registry)
        registry["candidates"] = []
        registry["candidate_count"] = 0
        registry["gate"]["g16_refinement_authorized"] = False
        registry.pop("registry_fingerprint", None)
        registry["registry_fingerprint"] = _fp(registry)
        with self.assertRaises(G16ExactCausalPipelineError):
            build_exact_causal_pipeline(self.replay, self.prior, self.forecast, self.safe_state, registry)

    def test_blind_forecast_outcome_leak_is_rejected(self):
        forecast = copy.deepcopy(self.forecast)
        forecast["days"][0]["actual_move_usd"] = 100
        with self.assertRaises(G16ExactCausalPipelineError):
            build_exact_causal_pipeline(self.replay, self.prior, forecast, self.safe_state, self.registry)

    def test_day_audit_quantifies_causal_evidence_availability(self):
        completion = self.build()["completion"]
        for day in G16_DATES:
            row = completion["days"][day]
            self.assertGreater(row["n_states"], 0)
            self.assertIn("signed_flow", row["evidence_available_counts"])
            self.assertIn("queue", row["evidence_available_counts"])
            self.assertIn("activity", row["evidence_available_counts"])
            self.assertIn("price_efficiency", row["evidence_available_counts"])
            self.assertTrue(row["strongest_output_fingerprint"])

    def test_visible_stand_down_propagates_to_completion(self):
        broken = copy.deepcopy(self.replay)
        state = self.all_states(broken)[0]
        state["availability"]["refine_update_allowed"] = False
        state["availability"]["flow_update_allowed"] = False
        state["availability"]["queue_update_allowed"] = False
        state["availability"]["stand_down_reasons"] = ["fixture_quality_stand_down"]
        state["feature_fingerprint"] = feature_fingerprint(state)
        broken["stand_down_days"] = [state["session_day"]]
        broken["status"] = "READY_WITH_STAND_DOWNS"
        self.refingerprint_replay(broken)
        artifacts = build_exact_causal_pipeline(
            broken,
            self.prior,
            self.forecast,
            self.safe_state,
            self.registry,
        )
        self.assertEqual(artifacts["completion"]["status"], "READY_WITH_STAND_DOWNS")
        self.assertIn(state["session_day"], artifacts["completion"]["stand_down_days"])
        output = artifacts["posterior_stream"]["outputs"][0]
        self.assertEqual(output["posterior"], output["blind_prior"])

    def test_completion_tamper_is_detected(self):
        artifacts = self.build()
        artifacts["completion"]["n_states"] += 1
        with self.assertRaises(G16ExactCausalPipelineError):
            validate_pipeline_artifacts(
                artifacts,
                replay=self.replay,
                blind_prior=self.prior,
                blind_forecast=self.forecast,
                blind_safe_state=self.safe_state,
                registry_source=self.registry,
            )

    def test_posterior_provenance_tamper_is_detected(self):
        artifacts = self.build()
        output = artifacts["posterior_stream"]["outputs"][0]
        output["provenance"]["feature_fingerprint"] = "f" * 64
        output.pop("output_fingerprint", None)
        output["output_fingerprint"] = _fp(output)
        stream = artifacts["posterior_stream"]
        stream.pop("stream_fingerprint", None)
        stream["stream_fingerprint"] = _fp(stream)
        with self.assertRaises(G16ExactCausalPipelineError):
            validate_pipeline_artifacts(
                artifacts,
                replay=self.replay,
                blind_prior=self.prior,
                blind_forecast=self.forecast,
                blind_safe_state=self.safe_state,
                registry_source=self.registry,
            )

    def test_permanent_shadow_no_brain_no_execution_authority(self):
        artifacts = self.build()
        completion = artifacts["completion"]
        for field in (
            "actual_g16_outcomes_used",
            "g16_scoring_authorized",
            "paid_live_data_assumed",
            "may_update_ng_brain",
            "may_change_g16_blind_prior",
            "may_change_g16_blind_forecast",
            "may_select_lessons_from_g16_outcomes",
            "execution_authority",
        ):
            self.assertFalse(completion[field])


if __name__ == "__main__":
    unittest.main()
