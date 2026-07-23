from __future__ import annotations

import copy
import unittest

import ng_g15_counterfactual_attribution as attribution_module
import ng_g15_counterfactual_lesson_gate as subject
import ng_g15_lesson_adjudication as adjudication_module
from ng_historical_manifest import G15_DATES
from ng_rt_refiner import refine_feature_state


class CounterfactualLessonGateTests(unittest.TestCase):
    def fixture(self):
        anchor = attribution_module._fixture_anchor()
        states = [
            attribution_module._fixture_state(day, index + 1)
            for index, day in enumerate(G15_DATES)
        ]
        refine_stream = {
            "schema": "ng_rt_refine_stream.v1",
            "market": "NG",
            "group": 15,
            "authority": "REFINE_POSTERIOR_STREAM_ONLY",
            "execution_authority": False,
            "anchor_fingerprint": anchor["anchor_fingerprint"],
            "n_outputs": len(states),
            "outputs": [refine_feature_state(state, anchor) for state in states],
        }
        replay = {
            "streams": [{"states": states}],
            "fingerprint": attribution_module._fingerprint(states),
        }
        attribution = attribution_module.build_report(
            replay, anchor, refine_stream
        )
        audit, _, comparison = adjudication_module._fixture()
        return replay, anchor, refine_stream, attribution, audit, comparison

    def build(self):
        values = self.fixture()
        return values, subject.build_gate(*values)

    def test_builds_exact_six_factor_proposal_set(self):
        _, result = self.build()
        self.assertEqual(result["factor_count"], 6)
        self.assertEqual(result["proposal_count"], 6)
        self.assertEqual(
            {row["factor"] for row in result["derived_proposals"]["proposals"]},
            set(attribution_module.FACTORS),
        )

    def test_support_days_are_derived_from_counterfactual_rows(self):
        values, result = self.build()
        attribution = values[3]
        for proposal in result["derived_proposals"]["proposals"]:
            expected = subject._expected_support_days(
                attribution, proposal["factor"]
            )
            self.assertEqual(proposal["supporting_g15_days"], expected)
            self.assertIs(proposal["may_select_support_after_scoring"], False)

    def test_derived_proposals_use_canonical_contract(self):
        values, result = self.build()
        adjudication_module.validate_unscored_proposals(
            result["derived_proposals"],
            audit_fingerprint=values[4]["audit_fingerprint"],
        )

    def test_embedded_adjudication_uses_canonical_contract(self):
        _, result = self.build()
        adjudication_module.validate_adjudication(result["adjudication"])
        self.assertEqual(
            result["adjudicated_count"], result["proposal_count"]
        )

    def test_registry_contains_only_counterfactual_candidates(self):
        _, result = self.build()
        proposals = {
            row["id"] for row in result["derived_proposals"]["proposals"]
        }
        candidates = {
            row["proposal_id"]
            for row in result["adjudication"]["g16_shadow_registry"][
                "candidates"
            ]
        }
        self.assertTrue(candidates.issubset(proposals))
        self.assertEqual(
            result["g16_shadow_candidate_count"], len(candidates)
        )
        counterfactual_fingerprint = result["source"][
            "counterfactual_fingerprint"
        ]
        registry = result["adjudication"]["g16_shadow_registry"]
        self.assertEqual(
            registry["source_counterfactual_fingerprint"],
            counterfactual_fingerprint,
        )
        self.assertTrue(
            all(
                row["source_counterfactual_fingerprint"]
                == counterfactual_fingerprint
                for row in registry["candidates"]
            )
        )

    def test_comparison_cannot_select_counterfactual_support_days(self):
        values = list(self.fixture())
        original_days = {
            row["factor"]: list(row["supporting_g15_days"])
            for row in values[3]["lesson_proposals"]
        }
        for day in values[5]["days"]:
            day["path_mae_improvement_usd"] = -100.0
            day["endpoint_improvement_usd"] = -100.0
        values[5].pop("artifact_fingerprint")
        values[5]["artifact_fingerprint"] = subject._fingerprint(values[5])
        result = subject.build_gate(*values)
        observed_days = {
            row["factor"]: row["supporting_g15_days"]
            for row in result["derived_proposals"]["proposals"]
        }
        self.assertEqual(observed_days, original_days)
        self.assertEqual(result["g16_shadow_candidate_count"], 0)

    def test_refingerprinted_attribution_support_tampering_is_rejected(self):
        values = list(self.fixture())
        values[3]["lesson_proposals"][0]["supporting_g15_days"] = []
        values[3].pop("fingerprint")
        values[3]["fingerprint"] = attribution_module._fingerprint(values[3])
        with self.assertRaises(subject.CounterfactualLessonGateError):
            subject.build_gate(*values)

    def test_refingerprinted_factor_row_tampering_is_rejected(self):
        values = list(self.fixture())
        values[3]["rows"][0]["factors"][0]["changed_posterior"] = False
        values[3].pop("fingerprint")
        values[3]["fingerprint"] = attribution_module._fingerprint(values[3])
        with self.assertRaises(subject.CounterfactualLessonGateError):
            subject.build_gate(*values)

    def test_comparison_fingerprint_tampering_is_rejected(self):
        values = list(self.fixture())
        values[5]["days"][0]["path_mae_improvement_usd"] += 1.0
        with self.assertRaises(subject.CounterfactualLessonGateError):
            subject.build_gate(*values)

    def test_audit_fingerprint_tampering_is_rejected(self):
        values = list(self.fixture())
        values[4]["days"][0]["n_completed_states"] += 1
        with self.assertRaises(subject.CounterfactualLessonGateError):
            subject.build_gate(*values)

    def test_gate_tampering_is_rejected_after_refingerprinting(self):
        values, result = self.build()
        result["derived_proposals"]["proposals"][0][
            "supporting_g15_days"
        ] = []
        result.pop("fingerprint")
        result["fingerprint"] = subject._fingerprint(result)
        with self.assertRaises(Exception):
            subject.validate_gate(
                result,
                replay=values[0],
                anchor=values[1],
                refine_stream=values[2],
                attribution=values[3],
                audit=values[4],
                comparison=values[5],
            )

    def test_stand_down_days_are_preserved(self):
        values = list(self.fixture())
        values[4]["days"][0]["stand_down_reasons"] = {
            "collector_skipped_records": 1
        }
        values[4].pop("audit_fingerprint")
        values[4]["audit_fingerprint"] = subject._fingerprint(values[4])
        result = subject.build_gate(*values)
        self.assertIn(G15_DATES[0], result["stand_down_days"])
        self.assertIn("WITH_STAND_DOWNS", result["status"])

    def test_inputs_remain_immutable(self):
        values = self.fixture()
        before = copy.deepcopy(values)
        subject.build_gate(*values)
        self.assertEqual(values, before)

    def test_deterministic_output(self):
        values = self.fixture()
        first = subject.build_gate(*values)
        second = subject.build_gate(*copy.deepcopy(values))
        self.assertEqual(first, second)

    def test_permanent_authority_controls(self):
        _, result = self.build()
        self.assertIs(result["actual_g15_outcomes_used"], True)
        for field in (
            "actual_g16_outcomes_used",
            "random_shuffle_used",
            "may_change_blind_prior",
            "may_change_posterior",
            "may_select_lessons_from_g15_scores",
            "may_update_ng_brain",
            "execution_authority",
            "options_lane_started",
        ):
            self.assertIs(result[field], False)
        self.assertIs(result["one_signal_authority_preserved"], True)
        self.assertIs(result["blind_forecasts_immutable"], True)
        self.assertEqual(result["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(
            result["brokerage_contract"], "tastytrade_not_ibkr"
        )


if __name__ == "__main__":
    unittest.main()
