"""The horizontal gate, tested against the defect that got past all eight vertical ones.

Run 33605852433 passed every section-6 gate while 4.9 and 4.12 computed the same estimand
and disagreed structurally. Every existing gate checks a section against ITSELF, and a
one-sided book is self-consistent - present, typed, in range, and wrong. These tests pin the
real numbers so the gate cannot be quietly loosened past them.
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_cross_section_agreement import (
    AgreementError,
    SHARED_ESTIMANDS,
    compare,
    gate_detail,
)


def _row(section, measure, *, n, lo, hi, total=None, squares=None):
    """A stratum row shaped like the runner's own averaged companions.

    `sum` is derived from the midpoint when not given, so most cases need only a range.
    An unpopulated stratum carries no bounds at all (`lo=hi=None`) and therefore no `sum` -
    deriving one from absent bounds is how a fixture invents a measurement the run never
    made, which is the exact error class this module exists to catch.
    """
    if total is None:
        total = None if lo is None or hi is None else (lo + hi) / 2 * n
    if squares is None and lo is not None and hi is not None:
        # Members at the midpoint unless the caller says otherwise, matching how `total` is
        # derived. A fixture must never omit sum_of_squares by accident, because omitting it
        # is what silently disables the one statistic that cannot be cancelled.
        squares = ((lo + hi) / 2) ** 2 * n
    value = {"n": n, "minimum": lo, "maximum": hi, "sum": total}
    if squares is not None:
        value["sum_of_squares"] = squares
    return {"section": section, "measure": measure, "value": value}


class TheRealDefectTests(unittest.TestCase):
    """Reproduced from run 33605852433's actual shape, not from an invented one."""

    def _sunday_shaped(self):
        rows = []
        # 4.9: 90 members pinned at +1.0 and 62 at -1.0 across pure strata, plus two mixed.
        for _ in range(9):
            rows.append(_row("4.9", "relative_imbalance", n=10, lo=1.0, hi=1.0))
        for _ in range(6):
            rows.append(_row("4.9", "relative_imbalance", n=10, lo=-1.0, hi=-1.0))
        rows.append(_row("4.9", "relative_imbalance", n=2, lo=-0.3, hi=0.3, total=0.0))
        # 4.12: the same formula, never near a bound.
        for _ in range(50):
            rows.append(_row("4.12", "normalized_imbalance", n=69, lo=0.0116, hi=0.1109))
        return rows

    def test_the_gate_fails_where_all_eight_vertical_gates_passed(self):
        passed, detail = gate_detail(compare(self._sunday_shaped()))
        self.assertFalse(passed)
        self.assertIn("relative_book_imbalance", detail)
        self.assertIn("sitting at the bounds", detail)

    def test_the_extreme_share_is_what_separates_them(self):
        verdict = compare(self._sunday_shaped())[0]
        nine = verdict["observed"]["4.9:relative_imbalance"]
        twelve = verdict["observed"]["4.12:normalized_imbalance"]
        self.assertGreater(nine["extreme_share"], 0.95)
        self.assertEqual(twelve["extreme_share"], 0.0)

    def test_a_range_check_alone_would_not_have_caught_it(self):
        """The reason the test is distributional: 4.9's range CONTAINS 4.12's."""
        verdict = compare(self._sunday_shaped())[0]
        nine = verdict["observed"]["4.9:relative_imbalance"]
        twelve = verdict["observed"]["4.12:normalized_imbalance"]
        self.assertLessEqual(nine["minimum"], twelve["minimum"])
        self.assertGreaterEqual(nine["maximum"], twelve["maximum"])
        self.assertFalse(verdict["agreed"])


class AgreementTests(unittest.TestCase):
    def test_two_sections_computing_the_same_thing_pass(self):
        rows = ([_row("4.9", "relative_imbalance", n=500, lo=0.01, hi=0.11)] * 5 +
                [_row("4.12", "normalized_imbalance", n=500, lo=0.01, hi=0.11)] * 5)
        passed, detail = gate_detail(compare(rows))
        self.assertTrue(passed, detail)
        self.assertIn("agree", detail)

    def test_silence_is_not_agreement_once_the_estimand_is_plainly_exercised(self):
        """The 4.2 shape: one section speaks at volume, its declared counterpart is silent."""
        rows = [_row("4.12", "normalized_imbalance", n=500, lo=0.01, hi=0.11)] * 5
        passed, detail = gate_detail(compare(rows))
        self.assertFalse(passed)
        self.assertIn("produced no populated stratum", detail)

    def test_silence_on_a_short_slice_is_recorded_and_does_not_reject(self):
        """A three-group fixture does not exercise 4.12 at all, and that is not a defect.

        The distinction is the declared per-estimand threshold, not a judgement call at read
        time - and the absence is still REPORTED, so tolerating it never means hiding it.
        """
        rows = [_row("4.12", "normalized_imbalance", n=10, lo=0.01, hi=0.11)] * 5
        passed, detail = gate_detail(compare(rows))
        self.assertTrue(passed, detail)
        self.assertIn("NOTED", detail)
        self.assertIn("produced no populated stratum", detail)

    def test_every_member_silent_is_a_coverage_question_not_a_disagreement(self):
        """Nothing computed the estimand, so nothing disagreed about it."""
        passed, detail = gate_detail(compare([]))
        self.assertTrue(passed, detail)

    def test_an_empty_stratum_does_not_count_as_a_population(self):
        rows = ([_row("4.9", "relative_imbalance", n=0, lo=None, hi=None)] +
                [_row("4.12", "normalized_imbalance", n=500, lo=0.01, hi=0.11)] * 5)
        passed, _ = gate_detail(compare(rows))
        self.assertFalse(passed)

    def test_the_mean_is_population_weighted_not_a_mean_of_means(self):
        # One stratum of 1,000 at 0.10 and one of 1 at 0.90. A mean of means says 0.50;
        # the population-weighted mean says ~0.1008. Weighting a stratum of one the same as
        # a stratum of a thousand is the error this whole programme keeps finding.
        rows = [_row("4.9", "relative_imbalance", n=1000, lo=0.10, hi=0.10),
                _row("4.9", "relative_imbalance", n=1, lo=0.90, hi=0.90),
                _row("4.12", "normalized_imbalance", n=1001, lo=0.10, hi=0.10, total=100.9)]
        verdict = compare(rows)[0]
        self.assertAlmostEqual(verdict["observed"]["4.9:relative_imbalance"]["mean"], 0.1008, places=3)
        self.assertTrue(verdict["agreed"])

    def test_a_mixed_stratum_contributes_no_extremes_rather_than_an_estimate(self):
        rows = ([_row("4.9", "relative_imbalance", n=100, lo=-1.0, hi=1.0, total=0.0)] +
                [_row("4.12", "normalized_imbalance", n=100, lo=-1.0, hi=1.0, total=0.0)])
        verdict = compare(rows)[0]
        self.assertEqual(verdict["observed"]["4.9:relative_imbalance"]["extreme_share"], 0.0)
        self.assertTrue(verdict["agreed"])


class EvasionTests(unittest.TestCase):
    """Each of these PASSED an earlier version of this gate. They are the review's exploits."""

    def test_a_sign_symmetric_pinned_section_cannot_hide_behind_a_zero_mean(self):
        """1,998 of 2,000 readings at a bound, split evenly, so mean and extreme share are 0."""
        rows = [
            _row("4.9", "relative_imbalance", n=1000, lo=0.0, hi=1.0, total=999.0, squares=999.0),
            _row("4.9", "relative_imbalance", n=1000, lo=-1.0, hi=0.0, total=-999.0, squares=999.0),
            _row("4.12", "normalized_imbalance", n=3454, lo=0.0116, hi=0.1109,
                 total=103.6, squares=3.9),
        ]
        verdict = compare(rows)[0]
        self.assertEqual(verdict["observed"]["4.9:relative_imbalance"]["extreme_share"], 0.0)
        self.assertAlmostEqual(verdict["observed"]["4.9:relative_imbalance"]["mean"], 0.0)
        passed, detail = gate_detail(compare(rows))
        self.assertFalse(passed, "mean and extreme share both cancel; only E[x^2] survives")
        self.assertIn("second moment", detail)

    def test_one_straddling_stratum_is_enough_to_defeat_the_extreme_share(self):
        """No contamination needed: 77 at +1 and 77 at -1 in a single stratum."""
        rows = [
            _row("4.9", "relative_imbalance", n=154, lo=-1.0, hi=1.0, total=0.0, squares=154.0),
            _row("4.12", "normalized_imbalance", n=3454, lo=0.0116, hi=0.1109,
                 total=103.6, squares=3.9),
        ]
        self.assertFalse(gate_detail(compare(rows))[0])

    def test_a_population_with_no_numerator_is_refused_not_read_as_zero(self):
        """Skipping the sum while counting n made every such section agree at exactly 0.0."""
        with self.assertRaises(AgreementError):
            compare([
                {"section": "4.9", "measure": "relative_imbalance",
                 "value": {"n": 1000, "minimum": 0.9, "maximum": 1.0}},
                _row("4.12", "normalized_imbalance", n=1000, lo=-0.02, hi=0.02, total=0.0),
            ])

    def test_a_handful_of_legitimate_one_sided_readings_does_not_reject_the_run(self):
        """A book with a genuinely empty ask yields +1.0, and four of them is not a defect."""
        rows = [
            _row("4.9", "relative_imbalance", n=4, lo=1.0, hi=1.0, total=4.0),
            _row("4.12", "normalized_imbalance", n=120000, lo=-0.4, hi=0.4,
                 total=2400.0, squares=9600.0),
        ]
        passed, detail = gate_detail(compare(rows))
        self.assertTrue(passed, detail)
        self.assertIn("comparison floor", detail)

    def test_values_outside_their_own_declared_bounds_are_a_defect_on_their_face(self):
        rows = [
            _row("4.9", "relative_imbalance", n=1000, lo=-7.0, hi=7.0, total=0.0, squares=0.5),
            _row("4.12", "normalized_imbalance", n=1000, lo=-0.02, hi=0.02, total=0.0, squares=0.5),
        ]
        passed, detail = gate_detail(compare(rows))
        self.assertFalse(passed)
        self.assertIn("outside its declared bounds", detail)

    def test_reversed_bounds_are_refused_rather_than_silently_disabling_the_check(self):
        with self.assertRaises(AgreementError):
            compare([], [{"estimand": "x", "members": (("a", "m"), ("b", "m")),
                          "bounds": (1.0, -1.0), "max_mean_divergence": 0.1,
                          "max_second_moment_divergence": 0.1,
                          "max_extreme_share_divergence": 0.1}])

    def test_a_ratio_or_survival_measure_is_counted_not_read_as_absent(self):
        """RATIO_PAIR and SURVIVAL rows carry no top-level `n`; reading it alone blinds the gate."""
        rows = [
            {"section": "4.9", "measure": "relative_imbalance",
             "value": {"total_observations": 500, "sum": 400.0, "sum_of_squares": 380.0,
                       "minimum": 0.5, "maximum": 1.0}},
            {"section": "4.12", "measure": "normalized_imbalance",
             "value": {"member_ratio_distribution": {"n": 500}, "sum": 25.0,
                       "sum_of_squares": 1.5, "minimum": 0.01, "maximum": 0.11}},
        ]
        verdict = compare(rows)[0]
        self.assertEqual(verdict["observed"]["4.9:relative_imbalance"]["n"], 500)
        self.assertEqual(verdict["observed"]["4.12:normalized_imbalance"]["n"], 500)
        self.assertFalse(verdict["agreed"])


class ToleranceBoundaryTests(unittest.TestCase):
    """Each tolerance is asserted by a pair that straddles it, so it cannot be widened quietly."""

    def _pair(self, mean_a, mean_b, sq_a=None, sq_b=None, n=5000):
        return [
            _row("4.9", "relative_imbalance", n=n, lo=mean_a, hi=mean_a,
                 total=mean_a * n, squares=(sq_a if sq_a is not None else mean_a ** 2) * n),
            _row("4.12", "normalized_imbalance", n=n, lo=mean_b, hi=mean_b,
                 total=mean_b * n, squares=(sq_b if sq_b is not None else mean_b ** 2) * n),
        ]

    def test_the_mean_divergence_check_is_load_bearing(self):
        """Deleting this branch used to leave the whole suite green."""
        rows = self._pair(0.30, 0.20, sq_a=0.09, sq_b=0.09)
        passed, detail = gate_detail(compare(rows))
        self.assertFalse(passed)
        self.assertIn("means differ", detail)
        self.assertNotIn("second moment", detail, "isolate the mean: moments are equal here")

    def test_the_mean_tolerance_sits_exactly_where_it_is_declared(self):
        self.assertTrue(gate_detail(compare(self._pair(0.30, 0.255, sq_a=0.09, sq_b=0.09)))[0])
        self.assertFalse(gate_detail(compare(self._pair(0.30, 0.245, sq_a=0.09, sq_b=0.09)))[0])

    def test_the_second_moment_tolerance_sits_exactly_where_it_is_declared(self):
        self.assertTrue(gate_detail(compare(self._pair(0.30, 0.30, sq_a=0.14, sq_b=0.09)))[0])
        self.assertFalse(gate_detail(compare(self._pair(0.30, 0.30, sq_a=0.20, sq_b=0.09)))[0])

    def test_the_extreme_tolerance_is_not_a_free_parameter(self):
        """Widening EXTREME_TOLERANCE must change which strata count as pinned."""
        near = [_row("4.9", "relative_imbalance", n=5000, lo=0.95, hi=0.95,
                     total=4750.0, squares=4512.5),
                _row("4.12", "normalized_imbalance", n=5000, lo=0.95, hi=0.95,
                     total=4750.0, squares=4512.5)]
        self.assertEqual(compare(near)[0]["observed"]["4.9:relative_imbalance"]["extreme_share"],
                         0.0, "0.95 is 2.5% of span from the bound, outside a 1% tolerance")


class RegisterTests(unittest.TestCase):
    def test_the_shipped_register_is_wellformed(self):
        self.assertTrue(SHARED_ESTIMANDS)
        for entry in SHARED_ESTIMANDS:
            self.assertGreaterEqual(len(entry["members"]), 2, entry["estimand"])
            self.assertIn("basis", entry)

    def test_every_registered_member_names_a_measure_that_actually_exists(self):
        """A typo in a register entry makes both members absent, which passes silently."""
        from research.kalshi.frankie_raw_mbo_benchmark.tests.test_native_calculation_runner import (
            make_run,
        )
        run = make_run()
        available = set()
        for label, section in run.sections.items():
            for measure in getattr(section, "measures", ()):
                available.add((label, measure.name))
        for entry in SHARED_ESTIMANDS:
            for member in entry["members"]:
                with self.subTest(estimand=entry["estimand"], member=member):
                    self.assertIn(tuple(member), available)

    def test_a_single_member_entry_is_refused(self):
        with self.assertRaises(AgreementError):
            compare([], [{"estimand": "x", "members": (("4.9", "m"),), "bounds": (-1, 1),
                          "max_mean_divergence": 0.1, "max_second_moment_divergence": 0.1,
                          "max_extreme_share_divergence": 0.1}])

    def test_a_malformed_entry_is_refused(self):
        with self.assertRaises(AgreementError):
            compare([], [{"estimand": "x", "members": (("4.9", "m"), ("4.12", "n"))}])

    def test_an_empty_register_passes_and_says_so(self):
        passed, detail = gate_detail(compare([], []))
        self.assertTrue(passed)
        self.assertIn("no shared estimands", detail)


if __name__ == "__main__":
    unittest.main()
