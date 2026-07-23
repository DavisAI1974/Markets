from __future__ import annotations

import copy
import unittest

import ng_g15_counterfactual_attribution as subject
from ng_historical_manifest import G15_DATES
from ng_rt_feature_state import feature_fingerprint
from ng_rt_refiner import output_fingerprint, refine_feature_state


class CounterfactualAttributionTests(unittest.TestCase):
    def fixture(self):
        anchor = subject._fixture_anchor()
        states = [
            subject._fixture_state(day, index + 1)
            for index, day in enumerate(G15_DATES)
        ]
        stream = {
            "schema": "ng_rt_refine_stream.v1",
            "market": "NG",
            "group": 15,
            "authority": "REFINE_POSTERIOR_STREAM_ONLY",
            "execution_authority": False,
            "anchor_fingerprint": anchor["anchor_fingerprint"],
            "n_outputs": len(states),
            "outputs": [
                refine_feature_state(state, anchor) for state in states
            ],
        }
        replay = {
            "streams": [{"states": states}],
            "fingerprint": subject._fingerprint(states),
        }
        return replay, anchor, stream

    def test_builds_all_six_factor_decompositions(self):
        replay, anchor, stream = self.fixture()
        report = subject.build_report(replay, anchor, stream)
        self.assertEqual(report["factors"], list(subject.FACTORS))
        self.assertEqual(report["n_days"], len(G15_DATES))
        self.assertEqual(report["n_states"], len(G15_DATES))
        self.assertEqual(set(report["overall"]), set(subject.FACTORS))
        self.assertEqual(len(report["rows"][0]["factors"]), 6)

    def test_each_requested_factor_has_a_measured_effect(self):
        replay, anchor, stream = self.fixture()
        report = subject.build_report(replay, anchor, stream)
        for factor in subject.FACTORS:
            with self.subTest(factor=factor):
                self.assertGreater(
                    report["overall"][factor]["changed_states"], 0
                )
                self.assertGreater(
                    report["overall"][factor]["posterior_l1_effect_sum"],
                    0.0,
                )

    def test_effect_direction_is_full_minus_neutral(self):
        replay, anchor, stream = self.fixture()
        report = subject.build_report(replay, anchor, stream)
        row = report["rows"][0]
        state = replay["streams"][0]["states"][0]
        full = stream["outputs"][0]
        neutral = refine_feature_state(
            subject.neutralize_factor(state, "signed_flow"), anchor
        )
        expected = subject._direction(full["posterior"]) - subject._direction(
            neutral["posterior"]
        )
        measured = next(
            item for item in row["factors"] if item["factor"] == "signed_flow"
        )
        self.assertAlmostEqual(
            measured["direction_effect_full_minus_neutral"],
            expected,
            places=9,
        )

    def test_neutralization_does_not_mutate_source(self):
        replay, _, _ = self.fixture()
        state = replay["streams"][0]["states"][0]
        before = copy.deepcopy(state)
        for factor in subject.FACTORS:
            neutral = subject.neutralize_factor(state, factor)
            self.assertNotEqual(
                neutral["feature_fingerprint"], state["feature_fingerprint"]
            )
            self.assertEqual(state, before)

    def test_stand_down_is_visible_and_prior_is_unchanged(self):
        replay, anchor, stream = self.fixture()
        state = replay["streams"][0]["states"][0]
        state["availability"] = {
            "flow_update_allowed": False,
            "queue_update_allowed": False,
            "refine_update_allowed": False,
            "stand_down_reasons": ["collector_skipped_records"],
        }
        state["feature_fingerprint"] = feature_fingerprint(state)
        stream["outputs"][0] = refine_feature_state(state, anchor)
        report = subject.build_report(replay, anchor, stream)
        self.assertEqual(report["status"], "READY_WITH_STAND_DOWNS")
        self.assertIn(G15_DATES[0], report["stand_down_days"])
        self.assertEqual(
            stream["outputs"][0]["posterior"],
            stream["outputs"][0]["blind_prior"],
        )
        self.assertTrue(
            all(
                not item["changed_posterior"]
                for item in report["rows"][0]["factors"]
            )
        )

    def test_missing_canonical_day_is_rejected(self):
        replay, anchor, stream = self.fixture()
        replay["streams"][0]["states"].pop()
        stream["outputs"].pop()
        stream["n_outputs"] -= 1
        with self.assertRaises(subject.CounterfactualAttributionError):
            subject.build_report(replay, anchor, stream)

    def test_backward_refine_chronology_is_rejected(self):
        replay, anchor, stream = self.fixture()
        stream["outputs"][0], stream["outputs"][1] = (
            stream["outputs"][1],
            stream["outputs"][0],
        )
        with self.assertRaises(subject.CounterfactualAttributionError):
            subject.build_report(replay, anchor, stream)

    def test_duplicate_feature_state_is_rejected(self):
        replay, anchor, stream = self.fixture()
        replay["streams"][0]["states"][1] = copy.deepcopy(
            replay["streams"][0]["states"][0]
        )
        with self.assertRaises(subject.CounterfactualAttributionError):
            subject.build_report(replay, anchor, stream)

    def test_refine_output_must_reproduce_exactly(self):
        replay, anchor, stream = self.fixture()
        output = stream["outputs"][0]
        output["posterior"]["up"] += 0.01
        output["posterior"]["down"] -= 0.01
        output["output_fingerprint"] = output_fingerprint(output)
        with self.assertRaises(subject.CounterfactualAttributionError):
            subject.build_report(replay, anchor, stream)

    def test_refine_output_coverage_must_be_one_to_one(self):
        replay, anchor, stream = self.fixture()
        stream["outputs"].pop()
        stream["n_outputs"] -= 1
        with self.assertRaises(subject.CounterfactualAttributionError):
            subject.build_report(replay, anchor, stream)

    def test_report_tampering_is_rejected_after_refingerprinting(self):
        replay, anchor, stream = self.fixture()
        report = subject.build_report(replay, anchor, stream)
        report["rows"][0]["factors"][0][
            "direction_effect_full_minus_neutral"
        ] += 0.25
        report.pop("fingerprint")
        report["fingerprint"] = subject._fingerprint(report)
        with self.assertRaises(subject.CounterfactualAttributionError):
            subject.validate_report(
                report,
                replay=replay,
                anchor=anchor,
                refine_stream=stream,
            )

    def test_lesson_proposals_are_unscored_and_cannot_rewrite_brain(self):
        replay, anchor, stream = self.fixture()
        report = subject.build_report(replay, anchor, stream)
        self.assertTrue(report["lesson_proposals"])
        for proposal in report["lesson_proposals"]:
            self.assertEqual(proposal["status"], "UNSCORED_CANDIDATE")
            self.assertIs(proposal["may_update_ng_brain"], False)
            self.assertIn(
                "chronological forward test on G16 using only pre-cutoff information",
                proposal["required_validation"],
            )

    def test_inputs_remain_immutable(self):
        replay, anchor, stream = self.fixture()
        before = copy.deepcopy((replay, anchor, stream))
        subject.build_report(replay, anchor, stream)
        self.assertEqual((replay, anchor, stream), before)

    def test_deterministic_output(self):
        replay, anchor, stream = self.fixture()
        first = subject.build_report(replay, anchor, stream)
        second = subject.build_report(
            copy.deepcopy(replay),
            copy.deepcopy(anchor),
            copy.deepcopy(stream),
        )
        self.assertEqual(first, second)

    def test_permanent_authority_controls(self):
        replay, anchor, stream = self.fixture()
        report = subject.build_report(replay, anchor, stream)
        for field in (
            "actual_outcomes_used",
            "random_shuffle_used",
            "may_change_blind_prior",
            "may_change_posterior",
            "may_update_ng_brain",
            "execution_authority",
            "options_lane_started",
        ):
            self.assertIs(report[field], False)
        self.assertIs(report["one_signal_authority_preserved"], True)
        self.assertIs(report["blind_forecast_immutable"], True)
        self.assertEqual(report["cme_event_contracts_mode"], "SHADOW")
        self.assertEqual(
            report["brokerage_contract"], "tastytrade_not_ibkr"
        )


if __name__ == "__main__":
    unittest.main()
