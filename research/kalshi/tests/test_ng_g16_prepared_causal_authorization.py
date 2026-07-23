import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

KALSHI_DIR = Path(__file__).resolve().parents[1]
if str(KALSHI_DIR) not in sys.path:
    sys.path.insert(0, str(KALSHI_DIR))

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
    G16PreparedCausalAuthorizationError,
    STATUS_READY,
    STATUS_STAND_DOWNS,
    _fp,
    build_authorization,
    validate_authorization,
)
from ng_g16_prepared_replay_gate import run_gate  # noqa: E402
from ng_g16_shadow_gate import (  # noqa: E402
    _fixture_blind_state,
    _fixture_forecast,
    _fixture_registry,
)


class G16PreparedCausalAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        inventory, definition = _fixture_inventory(root)
        self.manifest = build_manifest(inventory, _fixture_catalog(inventory, definition))
        self.prepared = prepare_corpus(self.manifest, root / "prepared")
        self.prior = {"up": 0.4, "flat": 0.2, "down": 0.4}
        self.replay, self.prepared_gate = run_gate(
            self.prepared, self.manifest, self.prior
        )
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

    def tearDown(self):
        self.temp.cleanup()

    @staticmethod
    def _refingerprint(value):
        value.pop("fingerprint", None)
        value["fingerprint"] = _fp(value)

    def _build(self, **overrides):
        values = {
            "prepared_gate": self.prepared_gate,
            "prepared_index": self.prepared,
            "manifest": self.manifest,
            "replay": self.replay,
            "blind_prior": self.prior,
            "causal_artifacts": self.causal,
            "blind_forecast": self.forecast,
            "blind_safe_state": self.blind_state,
            "registry_source": self.registry,
        }
        values.update(overrides)
        return build_authorization(**values)

    def _validate(self, authorization, **overrides):
        values = {
            "prepared_gate": self.prepared_gate,
            "prepared_index": self.prepared,
            "manifest": self.manifest,
            "replay": self.replay,
            "blind_prior": self.prior,
            "causal_artifacts": self.causal,
            "blind_forecast": self.forecast,
            "blind_safe_state": self.blind_state,
            "registry_source": self.registry,
        }
        values.update(overrides)
        validate_authorization(authorization, **values)

    def test_valid_exact_prepared_causal_authorization(self):
        result = self._build()
        self.assertEqual(result["status"], STATUS_READY)
        self.assertEqual(result["prepared_source_count"], 23)
        self.assertEqual(result["n_feature_states"], result["n_posterior_outputs"])
        self.assertEqual(result["n_days"], len(CANONICAL_DATES))

    def test_all_sources_remain_immutable(self):
        before = copy.deepcopy(
            (
                self.prepared_gate,
                self.prepared,
                self.manifest,
                self.replay,
                self.prior,
                self.causal,
                self.forecast,
                self.blind_state,
                self.registry,
            )
        )
        self._build()
        after = (
            self.prepared_gate,
            self.prepared,
            self.manifest,
            self.replay,
            self.prior,
            self.causal,
            self.forecast,
            self.blind_state,
            self.registry,
        )
        self.assertEqual(after, before)

    def test_prepared_gate_fingerprint_tamper_is_rejected(self):
        broken = copy.deepcopy(self.prepared_gate)
        broken["fingerprint"] = "0" * 64
        with self.assertRaises(G16PreparedCausalAuthorizationError):
            self._build(prepared_gate=broken)

    def test_prepared_source_link_tamper_is_rejected_after_refingerprint(self):
        broken = copy.deepcopy(self.prepared_gate)
        broken["prepared_source_fingerprints"][0] = "1" * 64
        self._refingerprint(broken)
        with self.assertRaises(G16PreparedCausalAuthorizationError):
            self._build(prepared_gate=broken)

    def test_replay_substitution_is_rejected_after_refingerprint(self):
        broken = copy.deepcopy(self.replay)
        broken["unexpected_marker"] = "different replay"
        self._refingerprint(broken)
        with self.assertRaises(G16PreparedCausalAuthorizationError):
            self._build(replay=broken)

    def test_causal_replay_link_tamper_is_rejected_after_refingerprint(self):
        broken = copy.deepcopy(self.causal)
        broken["completion"]["replay_fingerprint"] = "2" * 64
        self._refingerprint(broken["completion"])
        with self.assertRaises(G16PreparedCausalAuthorizationError):
            self._build(causal_artifacts=broken)

    def test_causal_candidate_set_cannot_be_changed_after_refingerprint(self):
        broken = copy.deepcopy(self.causal)
        broken["completion"]["candidate_ids"] = ["post_outcome_candidate"]
        self._refingerprint(broken["completion"])
        with self.assertRaises(G16PreparedCausalAuthorizationError):
            self._build(causal_artifacts=broken)

    def test_authorization_prepared_source_tamper_is_rejected_after_refingerprint(self):
        result = self._build()
        result["prepared_source_fingerprints"][0] = "3" * 64
        self._refingerprint(result)
        with self.assertRaises(G16PreparedCausalAuthorizationError):
            self._validate(result)

    def test_authorization_candidate_tamper_is_rejected_after_refingerprint(self):
        result = self._build()
        result["candidate_ids"] = ["late_selected_candidate"]
        self._refingerprint(result)
        with self.assertRaises(G16PreparedCausalAuthorizationError):
            self._validate(result)

    def test_authorization_state_count_tamper_is_rejected_after_refingerprint(self):
        result = self._build()
        result["n_feature_states"] += 1
        self._refingerprint(result)
        with self.assertRaises(G16PreparedCausalAuthorizationError):
            self._validate(result)

    def test_random_shuffle_or_execution_authority_is_rejected(self):
        for field in ("random_shuffle_used", "execution_authority"):
            result = self._build()
            result[field] = True
            self._refingerprint(result)
            with self.assertRaises(G16PreparedCausalAuthorizationError):
                self._validate(result)

    def test_brokerage_and_cme_modes_are_locked(self):
        result = self._build()
        result["brokerage_contract"] = "ibkr"
        self._refingerprint(result)
        with self.assertRaises(G16PreparedCausalAuthorizationError):
            self._validate(result)
        result = self._build()
        result["cme_event_contracts_mode"] = "LIVE"
        self._refingerprint(result)
        with self.assertRaises(G16PreparedCausalAuthorizationError):
            self._validate(result)

    def test_options_lane_remains_unstarted(self):
        result = self._build()
        result["options_lane_started"] = True
        self._refingerprint(result)
        with self.assertRaises(G16PreparedCausalAuthorizationError):
            self._validate(result)

    def test_stand_downs_from_both_chains_are_unionized(self):
        prepared_gate = copy.deepcopy(self.prepared_gate)
        prepared_gate["stand_down_days"] = [CANONICAL_DATES[0]]
        causal_completion = copy.deepcopy(self.causal["completion"])
        causal_completion["stand_down_days"] = [CANONICAL_DATES[1]]
        causal = copy.deepcopy(self.causal)
        causal["completion"] = causal_completion
        with patch(
            "ng_g16_prepared_causal_authorization._validate_upstream",
            return_value=causal_completion,
        ), patch(
            "ng_g16_prepared_causal_authorization._cross_chain_checks"
        ):
            result = build_authorization(
                prepared_gate=prepared_gate,
                prepared_index=self.prepared,
                manifest=self.manifest,
                replay=self.replay,
                blind_prior=self.prior,
                causal_artifacts=causal,
                blind_forecast=self.forecast,
                blind_safe_state=self.blind_state,
                registry_source=self.registry,
            )
        self.assertEqual(result["status"], STATUS_STAND_DOWNS)
        self.assertEqual(
            result["all_stand_down_days"],
            [CANONICAL_DATES[0], CANONICAL_DATES[1]],
        )

    def test_deterministic_authorization(self):
        self.assertEqual(self._build(), self._build())


if __name__ == "__main__":
    unittest.main()
