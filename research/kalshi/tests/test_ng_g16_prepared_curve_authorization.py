import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

from ng_g16_curve_adapter import CurveConfig, build_refined_forecast  # noqa: E402
from ng_g16_exact_causal_pipeline import (  # noqa: E402
    _retime_fixture,
    build_exact_causal_pipeline,
)
from ng_g16_historical_replay import (  # noqa: E402
    CANONICAL_DATES,
    _fixture_catalog,
    _fixture_inventory,
    build_manifest,
    prepare_corpus,
)
from ng_g16_prepared_causal_authorization import (  # noqa: E402
    build_authorization as build_causal_authorization,
)
from ng_g16_prepared_curve_authorization import (  # noqa: E402
    G16PreparedCurveAuthorizationError,
    NEXT_STAGE,
    STATUS_READY,
    STATUS_STAND_DOWNS,
    _fp,
    build_authorization,
    validate_curve_authorization,
)
from ng_g16_prepared_replay_gate import run_gate  # noqa: E402
from ng_g16_shadow_gate import (  # noqa: E402
    _fixture_blind_state,
    _fixture_forecast,
    _fixture_registry,
)


class G16PreparedCurveAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        inventory, definition = _fixture_inventory(root)
        self.manifest = build_manifest(inventory, _fixture_catalog(inventory, definition))
        self.prepared = prepare_corpus(self.manifest, root / "prepared")
        self.prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
        self.replay, self.prepared_gate = run_gate(self.prepared, self.manifest, self.prior)
        _retime_fixture(self.replay)
        self.prepared_gate["replay_fingerprint"] = self.replay["fingerprint"]
        self._refingerprint(self.prepared_gate)
        self.forecast = _fixture_forecast()
        self.blind_state = _fixture_blind_state()
        self.registry = _fixture_registry()
        self.causal = build_exact_causal_pipeline(
            self.replay,
            self.prior,
            self.forecast,
            self.blind_state,
            self.registry,
        )
        self.causal_authorization = build_causal_authorization(
            prepared_gate=self.prepared_gate,
            prepared_index=self.prepared,
            manifest=self.manifest,
            replay=self.replay,
            blind_prior=self.prior,
            causal_artifacts=self.causal,
            blind_forecast=self.forecast,
            blind_safe_state=self.blind_state,
            registry_source=self.registry,
        )
        self.blind_bytes = (json.dumps(self.forecast, sort_keys=True) + "\n").encode("utf-8")
        self.refined = build_refined_forecast(
            self.forecast,
            self.causal["plan"],
            self.causal["posterior_stream"],
            blind_file_bytes=self.blind_bytes,
            config=CurveConfig(),
        )

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _refingerprint(value):
        value.pop("fingerprint", None)
        value["fingerprint"] = _fp(value)

    @staticmethod
    def _refingerprint_curve(value):
        value.pop("artifact_fingerprint", None)
        value["artifact_fingerprint"] = _fp(value)

    def _kwargs(self, **overrides):
        values = {
            "prepared_causal_authorization": self.causal_authorization,
            "prepared_gate": self.prepared_gate,
            "prepared_index": self.prepared,
            "manifest": self.manifest,
            "replay": self.replay,
            "blind_prior": self.prior,
            "causal_artifacts": self.causal,
            "blind_forecast": self.forecast,
            "blind_safe_state": self.blind_state,
            "registry_source": self.registry,
            "shadow_plan": self.causal["plan"],
            "posterior_stream": self.causal["posterior_stream"],
            "refined_curve": self.refined,
            "blind_file_bytes": self.blind_bytes,
        }
        values.update(overrides)
        return values

    def _build(self, **overrides):
        return build_authorization(**self._kwargs(**overrides))

    def _validate(self, result, **overrides):
        validate_curve_authorization(result, **self._kwargs(**overrides))

    def test_valid_exact_prepared_curve_authorization(self):
        result = self._build()
        self.assertEqual(result["status"], STATUS_READY)
        self.assertEqual(result["n_days"], len(CANONICAL_DATES))
        self.assertEqual(result["next_permitted_stage"], NEXT_STAGE)
        self.assertFalse(result["g16_scoring_authorized"])

    def test_all_inputs_remain_immutable(self):
        before = copy.deepcopy(self._kwargs())
        self._build()
        self.assertEqual(self._kwargs(), before)

    def test_upstream_authorization_tamper_is_rejected(self):
        broken = copy.deepcopy(self.causal_authorization)
        broken["fingerprint"] = "0" * 64
        with self.assertRaises(G16PreparedCurveAuthorizationError):
            self._build(prepared_causal_authorization=broken)

    def test_refined_curve_must_be_exactly_reproducible(self):
        broken = copy.deepcopy(self.refined)
        broken["days"][0]["guess_curve"][-1][1] += 1
        self._refingerprint_curve(broken)
        with self.assertRaises(G16PreparedCurveAuthorizationError):
            self._build(refined_curve=broken)

    def test_transform_config_tamper_is_rejected(self):
        broken = copy.deepcopy(self.refined)
        broken["transform_config"]["max_adjustment_fraction"] = 0.25
        self._refingerprint_curve(broken)
        with self.assertRaises(G16PreparedCurveAuthorizationError):
            self._build(refined_curve=broken)

    def test_blind_file_byte_substitution_is_rejected(self):
        with self.assertRaises(G16PreparedCurveAuthorizationError):
            self._build(blind_file_bytes=self.blind_bytes + b" ")

    def test_plan_substitution_is_rejected(self):
        broken = copy.deepcopy(self.causal["plan"])
        broken["plan_fingerprint"] = "1" * 64
        with self.assertRaises(G16PreparedCurveAuthorizationError):
            self._build(shadow_plan=broken)

    def test_posterior_stream_substitution_is_rejected(self):
        broken = copy.deepcopy(self.causal["posterior_stream"])
        broken["stream_fingerprint"] = "2" * 64
        with self.assertRaises(G16PreparedCurveAuthorizationError):
            self._build(posterior_stream=broken)

    def test_unknown_candidate_use_is_rejected_after_refingerprint(self):
        broken = copy.deepcopy(self.refined)
        audit = broken["days"][0]["refinement_audit"]
        audit["authorized_candidate_ids_used"] = ["post_outcome_candidate"]
        audit.pop("audit_fingerprint", None)
        audit["audit_fingerprint"] = _fp(audit)
        self._refingerprint_curve(broken)
        with patch("ng_g16_prepared_curve_authorization._reproduce_curve"):
            with self.assertRaises(G16PreparedCurveAuthorizationError):
                self._build(refined_curve=broken)

    def test_unknown_posterior_output_reference_is_rejected(self):
        broken = copy.deepcopy(self.refined)
        audit = broken["days"][0]["refinement_audit"]
        audit["source_output_fingerprints"] = ["3" * 64]
        audit.pop("audit_fingerprint", None)
        audit["audit_fingerprint"] = _fp(audit)
        self._refingerprint_curve(broken)
        with patch("ng_g16_prepared_curve_authorization._reproduce_curve"):
            with self.assertRaises(G16PreparedCurveAuthorizationError):
                self._build(refined_curve=broken)

    def test_output_count_mismatch_is_rejected(self):
        broken = copy.deepcopy(self.refined)
        audit = broken["days"][0]["refinement_audit"]
        audit["outputs_seen"] += 1
        audit.pop("audit_fingerprint", None)
        audit["audit_fingerprint"] = _fp(audit)
        self._refingerprint_curve(broken)
        with patch("ng_g16_prepared_curve_authorization._reproduce_curve"):
            with self.assertRaises(G16PreparedCurveAuthorizationError):
                self._build(refined_curve=broken)

    def test_curve_stand_downs_are_visible(self):
        with patch(
            "ng_g16_prepared_curve_authorization._cross_chain_checks",
            return_value=([], [CANONICAL_DATES[0]], 0),
        ):
            result = self._build()
        self.assertEqual(result["status"], STATUS_STAND_DOWNS)
        self.assertEqual(result["curve_stand_down_days"], [CANONICAL_DATES[0]])

    def test_authorization_link_tamper_is_rejected_after_refingerprint(self):
        result = self._build()
        result["refined_curve_fingerprint"] = "4" * 64
        self._refingerprint(result)
        with self.assertRaises(G16PreparedCurveAuthorizationError):
            self._validate(result)

    def test_scoring_brain_execution_and_options_remain_disabled(self):
        for field in (
            "g16_scoring_authorized",
            "may_update_ng_brain",
            "execution_authority",
            "options_lane_started",
        ):
            result = self._build()
            result[field] = True
            self._refingerprint(result)
            with self.assertRaises(G16PreparedCurveAuthorizationError):
                self._validate(result)

    def test_brokerage_and_cme_modes_are_locked(self):
        result = self._build()
        result["brokerage_contract"] = "ibkr"
        self._refingerprint(result)
        with self.assertRaises(G16PreparedCurveAuthorizationError):
            self._validate(result)
        result = self._build()
        result["cme_event_contracts_mode"] = "LIVE"
        self._refingerprint(result)
        with self.assertRaises(G16PreparedCurveAuthorizationError):
            self._validate(result)

    def test_deterministic_authorization(self):
        self.assertEqual(self._build(), self._build())


if __name__ == "__main__":
    unittest.main()
