import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g16_prepared_publication_gate import (  # noqa: E402
    CURVE_AUTHORITY,
    CURVE_NEXT_STAGE,
    CURVE_READY,
    CURVE_SCHEMA,
    G16PreparedPublicationError,
    LOCK_STATUS,
    READY,
    READY_WITH_STAND_DOWNS,
    _fp,
    build_completion,
    build_curve_lock,
    validate_completion,
    validate_curve_lock,
)


class G16PreparedPublicationTests(unittest.TestCase):
    def setUp(self):
        self.blind = {"market": "NG", "group": 16, "days": []}
        self.refined = {
            "market": "NG",
            "group": 16,
            "artifact_fingerprint": "curve-fingerprint",
            "transform_config": {"max_adjustment_fraction": 0.2},
            "days": [],
        }
        self.blind_bytes = (json.dumps(self.blind, sort_keys=True) + "\n").encode()
        self.refined_bytes = (json.dumps(self.refined, sort_keys=True) + "\n").encode()
        self.causal_completion = {"fingerprint": "causal-completion-fingerprint"}
        self.causal_artifacts = {
            "completion": self.causal_completion,
            "plan": {"plan_fingerprint": "plan-fingerprint"},
            "authorization_stream": {"stream_fingerprint": "authorization-stream-fingerprint"},
            "posterior_stream": {"stream_fingerprint": "posterior-stream-fingerprint"},
        }
        self.sources = {
            "prepared_causal_authorization": {"fingerprint": "prepared-causal-fingerprint"},
            "prepared_gate": {"fingerprint": "prepared-gate-fingerprint"},
            "prepared_index": {"fingerprint": "prepared-index-fingerprint"},
            "manifest": {"fingerprint": "manifest-fingerprint"},
            "replay": {"fingerprint": "replay-fingerprint"},
            "blind_prior": {"up": 0.4, "flat": 0.2, "down": 0.4},
            "causal_artifacts": self.causal_artifacts,
            "blind_forecast": self.blind,
            "blind_safe_state": {"fingerprint": "blind-safe-fingerprint"},
            "registry_source": {"fingerprint": "registry-fingerprint"},
            "shadow_plan": self.causal_artifacts["plan"],
            "posterior_stream": self.causal_artifacts["posterior_stream"],
            "refined_curve": self.refined,
            "blind_file_bytes": self.blind_bytes,
            "refined_file_bytes": self.refined_bytes,
        }
        self.curve_authorization = {
            "schema": CURVE_SCHEMA,
            "market": "NG",
            "group": 16,
            "status": CURVE_READY,
            "authority": CURVE_AUTHORITY,
            "prepared_causal_authorization_fingerprint": "prepared-causal-fingerprint",
            "prepared_replay_gate_fingerprint": "prepared-gate-fingerprint",
            "replay_fingerprint": "replay-fingerprint",
            "manifest_fingerprint": "manifest-fingerprint",
            "prepared_corpus_fingerprint": "prepared-corpus-fingerprint",
            "blind_prior_fingerprint": "blind-prior-fingerprint",
            "blind_forecast_fingerprint": "blind-forecast-fingerprint",
            "blind_forecast_sha256": self._sha(self.blind_bytes),
            "plan_fingerprint": "plan-fingerprint",
            "authorization_stream_fingerprint": "authorization-stream-fingerprint",
            "posterior_stream_fingerprint": "posterior-stream-fingerprint",
            "refined_curve_fingerprint": self.refined["artifact_fingerprint"],
            "transform_config": copy.deepcopy(self.refined["transform_config"]),
            "registered_candidate_ids": ["lesson-1"],
            "used_candidate_ids": ["lesson-1"],
            "n_days": 11,
            "n_posterior_outputs": 11,
            "n_curve_outputs_used": 11,
            "upstream_stand_down_days": [],
            "curve_stand_down_days": [],
            "all_stand_down_days": [],
            "actual_g16_outcomes_used": False,
            "g16_scoring_authorized": False,
            "paid_live_data_assumed": False,
            "random_shuffle_used": False,
            "one_signal_authority_preserved": True,
            "blind_forecast_immutable": True,
            "may_change_g16_blind_prior": False,
            "may_change_g16_blind_forecast": False,
            "may_change_posterior": False,
            "may_select_lessons_from_g16_outcomes": False,
            "may_update_ng_brain": False,
            "execution_authority": False,
            "cme_event_contracts_mode": "SHADOW",
            "brokerage_contract": "tastytrade_not_ibkr",
            "options_lane_started": False,
            "next_permitted_stage": CURVE_NEXT_STAGE,
        }
        self._refingerprint(self.curve_authorization)

    @staticmethod
    def _sha(value):
        import hashlib
        return hashlib.sha256(value).hexdigest()

    @staticmethod
    def _refingerprint(value, field="fingerprint"):
        value.pop(field, None)
        value[field] = _fp(value)

    def build_lock(self):
        with patch("ng_g16_prepared_publication_gate.validate_curve_authorization"):
            return build_curve_lock(
                curve_authorization=self.curve_authorization,
                **self.sources,
            )

    def exact_completion(self, lock, *, stand_down_days=None):
        stand_down_days = list(stand_down_days or [])
        return {
            "completion_fingerprint": "exact-publication-fingerprint",
            "status": (
                "EXACT_G16_PUBLICATION_COMPLETE_WITH_STAND_DOWNS"
                if stand_down_days
                else "EXACT_G16_PUBLICATION_COMPLETE"
            ),
            "exact_causal_pipeline_fingerprint": self.causal_completion["fingerprint"],
            "replay_fingerprint": lock["replay_fingerprint"],
            "manifest_fingerprint": lock["manifest_fingerprint"],
            "prepared_corpus_fingerprint": lock["prepared_corpus_fingerprint"],
            "blind_prior_fingerprint": lock["blind_prior_fingerprint"],
            "blind_safe_state_fingerprint": "blind-safe-fingerprint",
            "g15_lesson_adjudication_fingerprint": "g15-adjudication-fingerprint",
            "g15_lesson_registry_fingerprint": "g15-registry-fingerprint",
            "plan_fingerprint": lock["plan_fingerprint"],
            "authorization_stream_fingerprint": lock["authorization_stream_fingerprint"],
            "posterior_stream_fingerprint": lock["posterior_stream_fingerprint"],
            "blind_forecast_sha256": lock["blind_forecast_sha256"],
            "refined_forecast_sha256": lock["refined_forecast_sha256"],
            "refined_curve_fingerprint": lock["refined_curve_fingerprint"],
            "actual_sha256": "actual-sha256",
            "actual_core_fingerprint": "actual-core-fingerprint",
            "blind_score_fingerprint": "blind-score-fingerprint",
            "refined_score_fingerprint": "refined-score-fingerprint",
            "comparison_fingerprint": "comparison-fingerprint",
            "chronological_validation_fingerprint": "chronology-fingerprint",
            "stand_down_days": stand_down_days,
            "renders": {
                "blind": {"filename": "g16_mbo_blind_continuous.png"},
                "refined": {"filename": "g16_mbo_refined_continuous.png"},
            },
            "post_g16_shadow_registry": {"candidate_count": 0},
            "authorized_next_stages": [
                "POST_G16_BASELINE_ONLY_OR_NEW_PRE_REGISTERED_DISCOVERY"
            ],
            "actual_g16_outcomes_used": True,
            "random_shuffle_used": False,
        }

    def build_final(self, lock=None, exact=None):
        lock = lock or self.build_lock()
        exact = exact or self.exact_completion(lock)
        kwargs = {
            "curve_lock": lock,
            "curve_authorization": self.curve_authorization,
            **self.sources,
            "adjudication": {},
            "actual": {},
            "blind_score": {},
            "refined_score": {},
            "comparison": {},
            "chronology": {},
            "blind_rt": {},
            "refined_rt": {},
            "actual_file_bytes": b"actual",
            "blind_png": Path("g16_mbo_blind_continuous.png"),
            "refined_png": Path("g16_mbo_refined_continuous.png"),
        }
        with patch("ng_g16_prepared_publication_gate.validate_curve_authorization"), patch(
            "ng_g16_prepared_publication_gate.build_exact_publication_completion",
            return_value=exact,
        ), patch("ng_g16_prepared_publication_gate.validate_exact_publication_completion"):
            return build_completion(**kwargs)

    def test_curve_lock_is_outcome_blind_and_opens_only_fixed_scoring(self):
        lock = self.build_lock()
        self.assertEqual(lock["status"], LOCK_STATUS)
        self.assertFalse(lock["actual_g16_outcomes_used"])
        self.assertTrue(lock["fixed_scoring_may_begin"])
        self.assertTrue(lock["curve_locked_before_fixed_scoring"])

    def test_curve_lock_binds_exact_refined_file_bytes(self):
        broken = dict(self.sources)
        broken_refined = copy.deepcopy(self.refined)
        broken_refined["artifact_fingerprint"] = "other-curve"
        broken["refined_file_bytes"] = (
            json.dumps(broken_refined, sort_keys=True) + "\n"
        ).encode()
        with patch("ng_g16_prepared_publication_gate.validate_curve_authorization"):
            with self.assertRaises(G16PreparedPublicationError):
                build_curve_lock(curve_authorization=self.curve_authorization, **broken)

    def test_curve_lock_rejects_outcome_leak_even_if_refingerprinted(self):
        broken = copy.deepcopy(self.curve_authorization)
        broken["actual_g16_outcomes_used"] = True
        self._refingerprint(broken)
        with patch("ng_g16_prepared_publication_gate.validate_curve_authorization"):
            with self.assertRaises(G16PreparedPublicationError):
                build_curve_lock(curve_authorization=broken, **self.sources)

    def test_curve_lock_rejects_early_scoring_authority(self):
        broken = copy.deepcopy(self.curve_authorization)
        broken["g16_scoring_authorized"] = True
        self._refingerprint(broken)
        with patch("ng_g16_prepared_publication_gate.validate_curve_authorization"):
            with self.assertRaises(G16PreparedPublicationError):
                build_curve_lock(curve_authorization=broken, **self.sources)

    def test_curve_lock_rejects_next_stage_substitution(self):
        broken = copy.deepcopy(self.curve_authorization)
        broken["next_permitted_stage"] = "SCORE_NOW"
        self._refingerprint(broken)
        with patch("ng_g16_prepared_publication_gate.validate_curve_authorization"):
            with self.assertRaises(G16PreparedPublicationError):
                build_curve_lock(curve_authorization=broken, **self.sources)

    def test_curve_lock_tamper_is_detected(self):
        lock = self.build_lock()
        lock["refined_forecast_sha256"] = "0" * 64
        with self.assertRaises(G16PreparedPublicationError):
            validate_curve_lock(lock)

    def test_complete_prepared_publication(self):
        result = self.build_final()
        self.assertEqual(result["status"], READY)
        self.assertTrue(result["curve_locked_before_fixed_scoring"])
        self.assertTrue(result["prepared_replay_provenance_preserved_through_scoring"])
        self.assertTrue(result["actual_g16_outcomes_used"])

    def test_missing_or_wrong_curve_lock_blocks_publication(self):
        lock = self.build_lock()
        lock["replay_fingerprint"] = "wrong"
        self._refingerprint(lock, "lock_fingerprint")
        with self.assertRaises(G16PreparedPublicationError):
            self.build_final(lock=lock)

    def test_exact_publication_cannot_substitute_replay(self):
        lock = self.build_lock()
        exact = self.exact_completion(lock)
        exact["replay_fingerprint"] = "wrong"
        with self.assertRaises(G16PreparedPublicationError):
            self.build_final(lock=lock, exact=exact)

    def test_exact_publication_cannot_substitute_refined_curve(self):
        lock = self.build_lock()
        exact = self.exact_completion(lock)
        exact["refined_curve_fingerprint"] = "wrong"
        with self.assertRaises(G16PreparedPublicationError):
            self.build_final(lock=lock, exact=exact)

    def test_curve_only_stand_down_is_propagated(self):
        self.curve_authorization["all_stand_down_days"] = ["20260329"]
        self.curve_authorization["curve_stand_down_days"] = ["20260329"]
        self.curve_authorization[
            "status"
        ] = "EXACT_G16_PREPARED_CURVE_AUTHORIZED_WITH_STAND_DOWNS"
        self._refingerprint(self.curve_authorization)
        lock = self.build_lock()
        result = self.build_final(lock=lock, exact=self.exact_completion(lock))
        self.assertEqual(result["status"], READY_WITH_STAND_DOWNS)
        self.assertEqual(result["stand_down_days"], ["20260329"])

    def test_publication_stand_down_is_unionized(self):
        lock = self.build_lock()
        result = self.build_final(
            lock=lock,
            exact=self.exact_completion(lock, stand_down_days=["20260401"]),
        )
        self.assertEqual(result["status"], READY_WITH_STAND_DOWNS)
        self.assertEqual(result["stand_down_days"], ["20260401"])

    def test_inputs_remain_immutable(self):
        before = copy.deepcopy((self.curve_authorization, self.sources))
        self.build_final()
        self.assertEqual((self.curve_authorization, self.sources), before)

    def test_completion_tamper_is_detected(self):
        result = self.build_final()
        result["actual_sha256"] = "wrong"
        with self.assertRaises(G16PreparedPublicationError):
            validate_completion(result)

    def test_brain_execution_and_options_remain_disabled(self):
        result = self.build_final()
        self.assertFalse(result["may_update_ng_brain"])
        self.assertFalse(result["execution_authority"])
        self.assertFalse(result["options_lane_started"])
        self.assertFalse(result["options_implementation_authorized"])

    def test_brokerage_and_cme_contracts_are_locked(self):
        result = self.build_final()
        self.assertEqual(result["brokerage_contract"], "tastytrade_not_ibkr")
        self.assertEqual(result["cme_event_contracts_mode"], "SHADOW")

    def test_random_shuffle_remains_forbidden(self):
        result = self.build_final()
        self.assertFalse(result["random_shuffle_used"])

    def test_completion_is_deterministic(self):
        self.assertEqual(self.build_final(), self.build_final())


if __name__ == "__main__":
    unittest.main()
