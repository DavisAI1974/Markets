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


def _row(section, measure, *, n, lo, hi, total=None):
    """A stratum row shaped like the runner's own averaged companions.

    `sum` is derived from the midpoint when not given, so most cases need only a range.
    An unpopulated stratum carries no bounds at all (`lo=hi=None`) and therefore no `sum` -
    deriving one from absent bounds is how a fixture invents a measurement the run never
    made, which is the exact error class this module exists to catch.
    """
    if total is None:
        total = None if lo is None or hi is None else (lo + hi) / 2 * n
    return {
        "section": section,
        "measure": measure,
        "value": {"n": n, "minimum": lo, "maximum": hi, "sum": total},
    }


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


class RegisterTests(unittest.TestCase):
    def test_the_shipped_register_is_wellformed(self):
        self.assertTrue(SHARED_ESTIMANDS)
        for entry in SHARED_ESTIMANDS:
            self.assertGreaterEqual(len(entry["members"]), 2, entry["estimand"])
            self.assertIn("basis", entry)

    def test_a_single_member_entry_is_refused(self):
        with self.assertRaises(AgreementError):
            compare([], [{"estimand": "x", "members": (("4.9", "m"),), "bounds": (-1, 1),
                          "max_mean_divergence": 0.1, "max_extreme_share_divergence": 0.1}])

    def test_a_malformed_entry_is_refused(self):
        with self.assertRaises(AgreementError):
            compare([], [{"estimand": "x", "members": (("4.9", "m"), ("4.12", "n"))}])

    def test_an_empty_register_passes_and_says_so(self):
        passed, detail = gate_detail(compare([], []))
        self.assertTrue(passed)
        self.assertIn("no shared estimands", detail)


if __name__ == "__main__":
    unittest.main()
