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
    _retime_fixture,
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
from ng_g16_shadow_gate import _fixture_blind_state, _fixture_forecast, _fixture_registry  # noqa: E402
from ng_rt_feature_state import feature_fingerprint  # noqa: E402


class G16ExactCausalPipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        inventory, definition = _fixture_inventory(root)
        manifest = build_manifest(inventory, _fixture_catalog(inventory, definition))
        prepared = prepare_corpus(manifest, root / "prepared")
        self.prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
        self.replay = replay_prepared(prepared, manifest, self.prior)
        _retime_fixture(self.replay)
        self.forecast = _fixture_forecast()
        self.safe = _fixture_blind_state()
        self.registry = _fixture_registry()

    def tearDown(self):
        self.temp.cleanup()

    def build(self, replay=None, prior=None, forecast=None, registry=None):
        return build_exact_causal_pipeline(
            replay or self.replay,
            prior or self.prior,
            forecast or self.forecast,
            self.safe,
            registry or self.registry,
        )

    @staticmethod
    def states(replay):
        return [row for stream in replay["streams"] for row in stream["states"]]

    @staticmethod
    def refingerprint(replay):
        replay.pop("fingerprint", None)
        replay["fingerprint"] = _fp(replay)

    def test_complete_pipeline_covers_all_days(self):
        result = self.build()
        completion = result["completion"]
        self.assertEqual(list(completion["days"]), list(G16_DATES))
        self.assertEqual(completion["n_states"], completion["n_outputs"])
        self.assertEqual(completion["next_permitted_stage"], "OUTCOME_BLIND_G16_CURVE_ADAPTER")

    def test_all_candidates_are_pre_requested(self):
        result = self.build()
        expected = result["plan"]["candidate_ids"]
        self.assertTrue(expected)
        self.assertTrue(all(row["authorized_candidate_ids"] == expected for row in result["authorization_stream"]["authorizations"]))
        self.assertFalse(result["completion"]["actual_g16_outcomes_used"])

    def test_sources_are_immutable(self):
        before = copy.deepcopy((self.replay, self.prior, self.forecast, self.safe, self.registry))
        self.build()
        self.assertEqual((self.replay, self.prior, self.forecast, self.safe, self.registry), before)

    def test_locked_prior_mismatch_is_rejected(self):
        with self.assertRaises(G16ExactCausalPipelineError):
            self.build(prior={"up": 0.5, "flat": 0.2, "down": 0.3})

    def test_replay_tamper_is_rejected(self):
        broken = copy.deepcopy(self.replay)
        broken["processed_records"]["trade"] += 1
        with self.assertRaises(G16ExactCausalPipelineError):
            self.build(replay=broken)

    def test_multiple_contract_streams_are_rejected(self):
        broken = copy.deepcopy(self.replay)
        broken["streams"].append(copy.deepcopy(broken["streams"][0]))
        self.refingerprint(broken)
        with self.assertRaises(G16ExactCausalPipelineError):
            self.build(replay=broken)

    def test_feature_prior_mismatch_is_rejected(self):
        broken = copy.deepcopy(self.replay)
        state = self.states(broken)[0]
        state["blind_prior_fingerprint"] = "0" * 64
        state["feature_fingerprint"] = feature_fingerprint(state)
        self.refingerprint(broken)
        with self.assertRaises(G16ExactCausalPipelineError):
            self.build(replay=broken)

    def test_backward_state_order_is_rejected(self):
        broken = copy.deepcopy(self.replay)
        broken["streams"][0]["states"][0:2] = reversed(broken["streams"][0]["states"][0:2])
        self.refingerprint(broken)
        with self.assertRaises(G16ExactCausalPipelineError):
            self.build(replay=broken)

    def test_empty_registry_blocks_g16(self):
        registry = copy.deepcopy(self.registry)
        registry["candidates"] = []
        registry["candidate_count"] = 0
        registry["gate"]["g16_refinement_authorized"] = False
        registry.pop("registry_fingerprint", None)
        registry["registry_fingerprint"] = _fp(registry)
        with self.assertRaises(G16ExactCausalPipelineError):
            self.build(registry=registry)

    def test_blind_forecast_outcome_leak_is_rejected(self):
        forecast = copy.deepcopy(self.forecast)
        forecast["days"][0]["actual_move_usd"] = 100
        with self.assertRaises(G16ExactCausalPipelineError):
            self.build(forecast=forecast)

    def test_audit_exposes_evidence_and_contributions(self):
        days = self.build()["completion"]["days"]
        for day in G16_DATES:
            self.assertGreater(days[day]["n_states"], 0)
            self.assertIn("signed_flow", days[day]["evidence_available_counts"])
            self.assertIn("queue", days[day]["evidence_available_counts"])
            self.assertTrue(days[day]["strongest_output_fingerprint"])

    def test_stand_down_is_visible_and_prior_is_unchanged(self):
        broken = copy.deepcopy(self.replay)
        state = self.states(broken)[0]
        state["availability"].update(refine_update_allowed=False, flow_update_allowed=False, queue_update_allowed=False)
        state["availability"]["stand_down_reasons"] = ["fixture_quality"]
        state["feature_fingerprint"] = feature_fingerprint(state)
        broken["stand_down_days"] = [state["session_day"]]
        broken["status"] = "READY_WITH_STAND_DOWNS"
        self.refingerprint(broken)
        result = self.build(replay=broken)
        self.assertEqual(result["completion"]["status"], "READY_WITH_STAND_DOWNS")
        output = result["posterior_stream"]["outputs"][0]
        self.assertEqual(output["posterior"], output["blind_prior"])

    def test_completion_tamper_is_detected(self):
        result = self.build()
        result["completion"]["n_states"] += 1
        with self.assertRaises(G16ExactCausalPipelineError):
            validate_pipeline_artifacts(result, replay=self.replay, blind_prior=self.prior, blind_forecast=self.forecast, blind_safe_state=self.safe, registry_source=self.registry)

    def test_posterior_provenance_tamper_is_detected(self):
        result = self.build()
        output = result["posterior_stream"]["outputs"][0]
        output["provenance"]["feature_fingerprint"] = "f" * 64
        output.pop("output_fingerprint", None)
        output["output_fingerprint"] = _fp(output)
        stream = result["posterior_stream"]
        stream.pop("stream_fingerprint", None)
        stream["stream_fingerprint"] = _fp(stream)
        with self.assertRaises(G16ExactCausalPipelineError):
            validate_pipeline_artifacts(result, replay=self.replay, blind_prior=self.prior, blind_forecast=self.forecast, blind_safe_state=self.safe, registry_source=self.registry)

    def test_authorization_candidate_tamper_is_detected(self):
        result = self.build()
        token = result["authorization_stream"]["authorizations"][0]
        token["authorized_candidate_ids"] = []
        token["baseline_microstructure_only"] = True
        token.pop("authorization_fingerprint", None)
        token["authorization_fingerprint"] = _fp(token)
        auth = result["authorization_stream"]
        auth.pop("stream_fingerprint", None)
        auth["stream_fingerprint"] = _fp(auth)
        posterior = result["posterior_stream"]
        posterior["authorization_stream_fingerprint"] = auth["stream_fingerprint"]
        posterior.pop("stream_fingerprint", None)
        posterior["stream_fingerprint"] = _fp(posterior)
        completion = result["completion"]
        completion["authorization_stream_fingerprint"] = auth["stream_fingerprint"]
        completion["posterior_stream_fingerprint"] = posterior["stream_fingerprint"]
        completion.pop("fingerprint", None)
        completion["fingerprint"] = _fp(completion)
        with self.assertRaises(G16ExactCausalPipelineError):
            validate_pipeline_artifacts(result, replay=self.replay, blind_prior=self.prior, blind_forecast=self.forecast, blind_safe_state=self.safe, registry_source=self.registry)

    def test_recomputed_audit_tamper_is_detected(self):
        result = self.build()
        day = G16_DATES[0]
        row = result["completion"]["days"][day]
        row["max_posterior_shift_tv"] += 0.1
        row.pop("day_audit_fingerprint", None)
        row["day_audit_fingerprint"] = _fp(row)
        completion = result["completion"]
        completion.pop("fingerprint", None)
        completion["fingerprint"] = _fp(completion)
        with self.assertRaises(G16ExactCausalPipelineError):
            validate_pipeline_artifacts(result, replay=self.replay, blind_prior=self.prior, blind_forecast=self.forecast, blind_safe_state=self.safe, registry_source=self.registry)

    def test_registry_provenance_tamper_is_detected(self):
        result = self.build()
        completion = result["completion"]
        completion["lesson_registry_fingerprint"] = "e" * 64
        completion.pop("fingerprint", None)
        completion["fingerprint"] = _fp(completion)
        with self.assertRaises(G16ExactCausalPipelineError):
            validate_pipeline_artifacts(result, replay=self.replay, blind_prior=self.prior, blind_forecast=self.forecast, blind_safe_state=self.safe, registry_source=self.registry)

    def test_permanent_shadow_authority(self):
        completion = self.build()["completion"]
        for field in ("actual_g16_outcomes_used", "g16_scoring_authorized", "paid_live_data_assumed", "may_update_ng_brain", "may_change_g16_blind_prior", "may_change_g16_blind_forecast", "may_select_lessons_from_g16_outcomes", "execution_authority"):
            self.assertFalse(completion[field])


if __name__ == "__main__":
    unittest.main()
