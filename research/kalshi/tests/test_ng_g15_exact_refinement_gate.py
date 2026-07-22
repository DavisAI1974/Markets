import copy
import sys
import unittest
from pathlib import Path

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

import ng_g15_exact_refinement_gate as gate


def refingerprint(value, field):
    value.pop(field, None)
    value[field] = gate._fingerprint(value)


class ExactRefinementGateTests(unittest.TestCase):
    def setUp(self):
        self.completion, self.pipeline, self.blind = gate._fixture()

    def build(self):
        return gate.build_authorization(
            completion=self.completion,
            pipeline=self.pipeline,
            blind_forecast_bytes=self.blind,
        )

    def test_valid_exact_pipeline_is_authorized(self):
        result = self.build()
        self.assertEqual(result["status"], gate.READY)
        self.assertEqual(result["days"], list(gate.G15_DATES))
        self.assertFalse(result["g16_authorized"])

    def test_source_artifacts_are_immutable(self):
        before = copy.deepcopy((self.completion, self.pipeline))
        self.build()
        self.assertEqual((self.completion, self.pipeline), before)

    def test_non_exact_completion_is_rejected(self):
        self.completion["basis_status"] = "MBO_SPECIFIC_LEG_READY_L1_BASIS_BLOCKED"
        refingerprint(self.completion, "completion_fingerprint")
        with self.assertRaisesRegex(gate.ExactRefinementAuthorizationError, "exact matched"):
            self.build()

    def test_completion_tampering_is_rejected(self):
        self.completion["prepared_source_count"] = 25
        with self.assertRaisesRegex(gate.ExactRefinementAuthorizationError, "completion fingerprint"):
            self.build()

    def test_pipeline_replay_must_match_completion(self):
        self.pipeline["replay"]["extra"] = "different"
        refingerprint(self.pipeline, "pipeline_fingerprint")
        with self.assertRaisesRegex(gate.ExactRefinementAuthorizationError, "pipeline replay differs"):
            self.build()

    def test_prepared_corpus_mismatch_is_rejected(self):
        self.pipeline["replay"]["prepared_corpus_fingerprint"] = "other"
        self.completion["replay_fingerprint"] = gate._fingerprint(self.pipeline["replay"])
        refingerprint(self.completion, "completion_fingerprint")
        refingerprint(self.pipeline, "pipeline_fingerprint")
        with self.assertRaisesRegex(gate.ExactRefinementAuthorizationError, "different prepared corpus"):
            self.build()

    def test_blind_forecast_hash_mismatch_is_rejected(self):
        with self.assertRaisesRegex(gate.ExactRefinementAuthorizationError, "different blind forecast"):
            gate.build_authorization(
                completion=self.completion,
                pipeline=self.pipeline,
                blind_forecast_bytes=b"changed\n",
            )

    def test_blind_before_after_mismatch_is_rejected(self):
        self.pipeline["blind_forecast"]["sha256_after"] = "different"
        refingerprint(self.pipeline, "pipeline_fingerprint")
        with self.assertRaisesRegex(gate.ExactRefinementAuthorizationError, "before/after"):
            self.build()

    def test_refine_output_count_must_match_exact_states(self):
        self.pipeline["refine_stream"]["outputs"].pop()
        self.pipeline["refine_stream"]["n_outputs"] -= 1
        refingerprint(self.pipeline, "pipeline_fingerprint")
        with self.assertRaisesRegex(gate.ExactRefinementAuthorizationError, "exact feature-state count"):
            self.build()

    def test_feature_fingerprint_mapping_is_one_to_one(self):
        first = self.pipeline["refine_stream"]["outputs"][0]
        first["feature_fingerprint"] = "wrong-feature"
        refingerprint(first, "output_fingerprint")
        refingerprint(self.pipeline, "pipeline_fingerprint")
        with self.assertRaisesRegex(gate.ExactRefinementAuthorizationError, "one-to-one"):
            self.build()

    def test_missing_g15_day_is_rejected(self):
        output = self.pipeline["refine_stream"]["outputs"][-1]
        output["session_day"] = gate.G15_DATES[-2]
        refingerprint(output, "output_fingerprint")
        refingerprint(self.pipeline, "pipeline_fingerprint")
        with self.assertRaisesRegex(gate.ExactRefinementAuthorizationError, "missing G15 days"):
            self.build()

    def test_daily_audit_must_remain_outcome_blind(self):
        self.pipeline["daily_audit"]["days"][0]["outcome_scored"] = True
        refingerprint(self.pipeline["daily_audit"], "audit_fingerprint")
        self.pipeline["lesson_proposals"]["source_audit_fingerprint"] = self.pipeline["daily_audit"]["audit_fingerprint"]
        refingerprint(self.pipeline["lesson_proposals"], "proposal_fingerprint")
        refingerprint(self.pipeline, "pipeline_fingerprint")
        with self.assertRaisesRegex(gate.ExactRefinementAuthorizationError, "cannot contain outcome"):
            self.build()

    def test_lessons_cannot_update_brain(self):
        self.pipeline["lesson_proposals"]["may_update_ng_brain"] = True
        refingerprint(self.pipeline["lesson_proposals"], "proposal_fingerprint")
        refingerprint(self.pipeline, "pipeline_fingerprint")
        with self.assertRaisesRegex(gate.ExactRefinementAuthorizationError, "cannot update"):
            self.build()

    def test_stand_down_completion_produces_visible_status(self):
        self.completion["status"] = "EXACT_CAUSAL_REPLAY_READY_WITH_STAND_DOWNS"
        self.completion["days"][0]["stand_down_reasons"] = {"collector_skipped_records": 1}
        refingerprint(self.completion, "completion_fingerprint")
        result = self.build()
        self.assertEqual(result["status"], gate.READY_WITH_STAND_DOWNS)
        self.assertEqual(result["stand_down_days"], [gate.G15_DATES[0]])

    def test_authorization_tampering_is_rejected(self):
        result = self.build()
        result["g16_authorized"] = True
        with self.assertRaisesRegex(gate.ExactRefinementAuthorizationError, "authorization fingerprint"):
            gate.validate_authorization(result)


if __name__ == "__main__":
    unittest.main()
