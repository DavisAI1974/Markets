"""Tests for section 4.11 prebirth prediction and continuous H+N recognition."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_recognition import (
    CENSORED_OUTCOME,
    HORIZON,
    MISSED,
    PRIOR,
    T0,
    CandidateRecognition,
    RecognitionCalculator,
    RecognitionError,
)


def candidate(**overrides) -> CandidateRecognition:
    base = dict(
        candidate_id="c1",
        source_day="20211004",
        source_role="HELD_OUT_BLIND",
        continuity_segment=0,
        family_id="TFCN",
        side="B",
        session_phase="RTH",
        birth_recv_ns=1_000,
    )
    base.update(overrides)
    return CandidateRecognition(**base)


class CandidateRecognitionTest(unittest.TestCase):
    def test_a_call_before_birth_is_prior_with_positive_lead(self) -> None:
        c = candidate()
        self.assertEqual(c.record_call(recv_ns=600), PRIOR)
        self.assertEqual(c.lead_ns, 400)
        self.assertTrue(c.detected)

    def test_a_call_at_birth_is_t0(self) -> None:
        c = candidate()
        self.assertEqual(c.record_call(recv_ns=1_000), T0)
        self.assertEqual(c.lead_ns, 0)

    def test_a_call_after_birth_is_a_horizon_with_negative_lead(self) -> None:
        c = candidate()
        self.assertEqual(c.record_call(recv_ns=1_900), HORIZON)
        self.assertEqual(c.lead_ns, -900)

    def test_the_first_call_stands_and_a_better_one_cannot_replace_it(self) -> None:
        """Section 2: a later, better-looking recognition may not replace the first call."""
        c = candidate()
        c.record_call(recv_ns=1_900)
        self.assertEqual(c.record_call(recv_ns=500), HORIZON, "the H+N call stands")
        self.assertEqual(c.recognized_recv_ns, 1_900)
        self.assertEqual(c.superseded_attempts, 1, "the re-call attempt is visible in the record")

    def test_missed_and_censored_cannot_overwrite_a_call(self) -> None:
        c = candidate()
        c.record_call(recv_ns=1_000)
        with self.assertRaises(RecognitionError):
            c.mark_missed()
        with self.assertRaises(RecognitionError):
            c.mark_censored()

    def test_failed_states_are_preserved(self) -> None:
        c = candidate()
        c.note_failed_state(label="ambiguous_precursor", recv_ns=400, reason="refill matched removal")
        c.record_call(recv_ns=900)
        row = c.as_dict()
        self.assertEqual(row["failed_state_count"], 1)
        self.assertEqual(row["failed_states"][0]["reason"], "refill matched removal")

    def test_an_unrecognized_candidate_has_no_lead(self) -> None:
        c = candidate()
        c.mark_missed()
        self.assertIsNone(c.lead_ns)
        self.assertFalse(c.detected)


class RecognitionCalculatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = RecognitionCalculator()

    def test_a_candidate_with_no_outcome_cannot_be_recorded(self) -> None:
        """Leaving it out of the population is the failure mode; refuse it."""
        with self.assertRaises(RecognitionError):
            self.calc.record(candidate())

    def test_outcome_classes_never_pool(self) -> None:
        for index, recv in enumerate((600, 1_000, 1_900)):
            c = candidate(candidate_id=f"c{index}")
            c.record_call(recv_ns=recv)
            self.calc.record(c)
        subfamilies = {r["stratum"]["subfamily_id"] for r in self.calc.failed_states.rows()}
        self.assertEqual(
            subfamilies, {f"outcome={PRIOR}", f"outcome={T0}", f"outcome={HORIZON}"}
        )

    def test_prior_leads_and_horizon_delays_are_separate_measures(self) -> None:
        early = candidate(candidate_id="a")
        early.record_call(recv_ns=600)
        late = candidate(candidate_id="b")
        late.record_call(recv_ns=1_900)
        self.calc.record(early)
        self.calc.record(late)
        self.assertEqual(self.calc.prior_lead.rows()[0]["value"]["maximum"], 400.0)
        self.assertEqual(self.calc.horizon_delay.rows()[0]["value"]["maximum"], 900.0)

    def test_missed_and_censored_members_stay_in_the_population(self) -> None:
        detected = candidate(candidate_id="a")
        detected.record_call(recv_ns=600)
        missed = candidate(candidate_id="b")
        missed.mark_missed()
        censored = candidate(candidate_id="c")
        censored.mark_censored()
        for c in (detected, missed, censored):
            self.calc.record(c)
        report = self.calc.population_report()
        self.assertEqual(len(report), 1, "one population stratum, all outcomes inside it")
        row = report[0]
        self.assertEqual(row["population_denominator"], 3)
        self.assertEqual(row["detected_count"], 1)
        self.assertEqual(row["undetected_count"], 2)
        self.assertAlmostEqual(row["detection_share"], 1 / 3)
        self.assertEqual(row["outcome_counts"][MISSED], 1)
        self.assertEqual(row["outcome_counts"][CENSORED_OUTCOME], 1)

    def test_the_population_row_warns_against_the_detected_only_reading(self) -> None:
        """The exact error section 4.11 names is called out on the row itself."""
        detected = candidate(candidate_id="a")
        detected.record_call(recv_ns=600)
        missed = candidate(candidate_id="b")
        missed.mark_missed()
        self.calc.record(detected)
        self.calc.record(missed)
        row = self.calc.population_report()[0]
        self.assertIn("1 of 2", row["warning"])
        self.assertIn("not the population detection time", row["warning"])
        self.assertTrue(row["detection_share_is_a_rate_not_a_mean"])

    def test_there_is_no_bare_detection_time_mean_on_the_calculator(self) -> None:
        forbidden = {"mean_detection_time", "average_lead", "detection_time_mean", "mean_lead"}
        self.assertEqual(forbidden & set(dir(self.calc)), set())

    def test_population_strata_do_not_pool_across_days(self) -> None:
        for day in ("20211004", "20211005"):
            c = candidate(candidate_id=f"c{day}", source_day=day)
            c.record_call(recv_ns=600)
            self.calc.record(c)
        report = self.calc.population_report()
        self.assertEqual({r["stratum"]["source_day"] for r in report}, {"20211004", "20211005"})

    def test_population_key_ignores_outcome_so_the_denominator_spans_all_outcomes(self) -> None:
        detected = candidate(candidate_id="a")
        detected.record_call(recv_ns=600)
        missed = candidate(candidate_id="b")
        missed.mark_missed()
        self.calc.record(detected)
        self.calc.record(missed)
        self.assertEqual(len(self.calc.population_report()), 1)

    def test_every_candidate_contributes_a_failed_state_observation(self) -> None:
        missed = candidate(candidate_id="b")
        missed.note_failed_state(label="x", recv_ns=1, reason="y")
        missed.mark_missed()
        self.calc.record(missed)
        self.assertEqual(self.calc.failed_states.rows()[0]["value"]["maximum"], 1.0)

    def test_summary_carries_the_population_and_the_first_call_rule(self) -> None:
        detected = candidate(candidate_id="a")
        detected.record_call(recv_ns=600)
        detected.record_call(recv_ns=100)
        missed = candidate(candidate_id="b")
        missed.mark_missed()
        self.calc.record(detected)
        self.calc.record(missed)
        summary = self.calc.summary()
        self.assertEqual(summary["section"], "4.11")
        self.assertEqual(summary["candidates_recorded"], 2)
        self.assertEqual(summary["detected_count"], 1)
        self.assertEqual(summary["undetected_count"], 1)
        self.assertEqual(summary["superseded_call_attempts"], 1)
        self.assertIn("first lawful call", summary["first_call_rule"])


if __name__ == "__main__":
    unittest.main()
