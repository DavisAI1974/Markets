"""Section 4.4's mirror key and matcher: one mechanical definition, one implementation.

Note what these tests do NOT assert. An earlier version pinned "4.4 and 4.12 are
different axes" as fact; the contract does not settle that, so enforcing it here would
have been a ruling nobody made, recorded where something enforces it.

The matcher tests below are written against D-16, so most of them run a matcher that pairs
NOTHING and then assert the artifact is still diagnosable. That is deliberate: the delivered
run (33605852433) formed 0 pairs across 1,692 strata with 3,454 excluded members and no
reason counter, and a test suite that only exercises the happy path would have passed on it.
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark import native_dipole, native_mirror
from research.kalshi.frankie_raw_mbo_benchmark.native_mirror import (
    COORDINATE_ABSENT,
    COUNTERPART_EXHAUSTED,
    DISTANCE_ABOVE_BOUND,
    NOT_OFFERED_TO_MATCHER,
    NO_COUNTERPART_IN_SCOPE,
    SELF_MIRROR,
    UNMATCHED_REASONS,
    MatchScope,
    MirrorError,
    MirrorMatcher,
)
from research.kalshi.frankie_raw_mbo_benchmark.a_memory_member_first_recalculation_20260828 import (
    discovery_contract,
    mirror_identity as a_memory_mirror_identity,
)

SIDE_STRINGS = (
    "A", "B", "N", "AB", "BA", "ABBN", "BAAN", "AAAA", "BBBB", "NNN", "", "ABNBAN",
)


SCOPE = MatchScope(
    source_day="20211004",
    source_role="HELD_OUT_BLIND",
    continuity_segment=18904,
    family_id="ow-40540069fe5aeddc127b",
    session_phase="RTH",
)
OTHER_DAY = MatchScope(
    source_day="20211005",
    source_role="HELD_OUT_BLIND",
    continuity_segment=18904,
    family_id="ow-40540069fe5aeddc127b",
    session_phase="RTH",
)


def matcher(bound: float = 1_000.0) -> MirrorMatcher:
    return MirrorMatcher(coordinate_name="birth_recv_ns", distance_bound=bound)


class MirrorIdentityTest(unittest.TestCase):
    def test_the_mirror_is_the_side_swapped_side_string(self) -> None:
        self.assertEqual(native_mirror.mirror_identity("ABBN")["mirror_side_string"], "BAAN")

    def test_a_pair_resolves_to_one_key_from_either_end(self) -> None:
        """What makes it a pair KEY rather than two labels for two structures."""
        left = native_mirror.mirror_identity("ABBN")
        right = native_mirror.mirror_identity("BAAN")
        self.assertEqual(left["mirror_pair_key"], right["mirror_pair_key"])
        self.assertEqual(left["mirror_pair_key"], "ABBN|BAAN")
        self.assertNotEqual(left["orientation"], right["orientation"])

    def test_orientation_is_canonical_for_the_lexicographically_first_member(self) -> None:
        self.assertEqual(native_mirror.mirror_identity("ABBN")["orientation"], native_mirror.CANONICAL)
        self.assertEqual(native_mirror.mirror_identity("BAAN")["orientation"], native_mirror.MIRROR)

    def test_unsided_characters_pass_through_rather_than_raising(self) -> None:
        """D60: an unsided or novel row is characterized, never dropped."""
        self.assertEqual(native_mirror.mirror_identity("NNN")["mirror_side_string"], "NNN")
        self.assertEqual(native_mirror.mirror_identity("NNN")["orientation"], native_mirror.CANONICAL)

    def test_swapping_twice_returns_the_original(self) -> None:
        for sides in SIDE_STRINGS:
            with self.subTest(sides=sides):
                once = native_mirror.mirror_identity(sides)["mirror_side_string"]
                twice = native_mirror.mirror_identity(once)["mirror_side_string"]
                self.assertEqual(twice, sides)


class OneDefinitionTest(unittest.TestCase):
    def test_the_a_memory_recalculation_delegates_rather_than_reimplementing(self) -> None:
        for sides in SIDE_STRINGS:
            with self.subTest(sides=sides):
                self.assertEqual(
                    a_memory_mirror_identity(sides), native_mirror.mirror_identity(sides)
                )


class ScopeTest(unittest.TestCase):
    """4.4's pair key is member-level. Whether it is also 4.12's orientation is unruled."""

    def test_the_pair_key_does_not_borrow_4_12_s_vocabulary(self) -> None:
        """Not a claim that they are different axes - only that this module does not decide."""
        self.assertNotIn("SAME", native_mirror.VALID_ORIENTATIONS)
        self.assertNotIn("FLIP", native_mirror.VALID_ORIENTATIONS)

    def test_section_4_12_still_carries_its_contract_orientation(self) -> None:
        """Contract 4.12: "`SAME` and `FLIP` orientations never pool"."""
        self.assertEqual(native_dipole.VALID_ORIENTATIONS, frozenset({"SAME", "FLIP"}))

    def test_the_frozen_transition_orientation_uses_the_same_words(self) -> None:
        self.assertEqual(discovery_contract()["transition_orientation_seeds"], ["SAME", "FLIP"])


class ZeroPairDiagnosisTest(unittest.TestCase):
    """D-16: a run that pairs nothing must still say why, per reason, with distances.

    Every test here ends with `pairs_formed == 0`, which is the delivered run's outcome.
    What separates these from the delivered artifact is everything ELSE the summary carries.
    """

    def test_zero_pairs_still_reports_a_populated_reason_breakdown(self) -> None:
        m = matcher()
        m.offer(member_id="s0", sides="AB", coordinate=0, scope=SCOPE)
        m.offer(member_id="s1", sides="BA", coordinate=9_000, scope=SCOPE)
        m.offer(member_id="s2", sides="NNN", coordinate=5, scope=SCOPE)
        m.offer(member_id="s3", sides="AAB", coordinate=None, scope=SCOPE)
        m.offer(member_id="s4", sides="ABBB", coordinate=7, scope=SCOPE)
        m.finalize()
        summary = m.summary()
        self.assertEqual(summary["pairs_formed"], 0)
        self.assertEqual(
            summary["unmatched_reason_counts"],
            {
                NOT_OFFERED_TO_MATCHER: 0,
                COORDINATE_ABSENT: 1,
                SELF_MIRROR: 1,
                NO_COUNTERPART_IN_SCOPE: 1,
                DISTANCE_ABOVE_BOUND: 2,
                COUNTERPART_EXHAUSTED: 0,
            },
        )

    def test_zero_pairs_still_reports_the_near_miss_distance_distribution(self) -> None:
        """"Zero pairs, and here is how close they came" is the deliverable."""
        m = matcher()
        for index, coordinate in enumerate((0, 5_000, 20_000)):
            m.offer(member_id=f"a{index}", sides="AB", coordinate=coordinate, scope=SCOPE)
        m.offer(member_id="b0", sides="BA", coordinate=40_000, scope=SCOPE)
        m.finalize()
        near = m.summary()["unmatched_nearest_candidate_distance"]
        self.assertEqual(m.summary()["pairs_formed"], 0)
        self.assertEqual(near["n"], 4)
        self.assertEqual(near["minimum"], 20_000.0)
        self.assertEqual(near["maximum"], 40_000.0)
        self.assertIsNotNone(near["p50"])

    def test_every_declared_reason_is_present_even_at_zero_occurrences(self) -> None:
        """An unmatched reason with no occurrences is still a declared reason.

        A count of zero says the branch was reachable and never fired. An absent key says
        nothing at all, and the two were indistinguishable in the delivered artifact.
        """
        m = matcher()
        m.finalize()
        counts = m.summary()["unmatched_reason_counts"]
        self.assertEqual(sorted(counts), sorted(UNMATCHED_REASONS))
        self.assertEqual(set(counts.values()), {0})

    def test_a_matcher_that_was_never_invoked_says_so_rather_than_reporting_zero_pairs(self) -> None:
        """The delivered run's actual condition: 3,454 members existed, none was offered."""
        m = matcher()
        for index in range(3):
            m.withhold(
                member_id=f"stage{index}",
                sides="AB",
                scope=SCOPE,
                note="4.12 withheld the stage: NO_PREDECESSOR, so no orientation exists",
            )
        m.finalize()
        summary = m.summary()
        self.assertFalse(summary["matcher_invoked"])
        self.assertEqual(summary["members_withheld"], 3)
        self.assertEqual(summary["unmatched_reason_counts"][NOT_OFFERED_TO_MATCHER], 3)
        self.assertEqual(
            m.unmatched[0]["producer_note"],
            "4.12 withheld the stage: NO_PREDECESSOR, so no orientation exists",
        )

    def test_never_invoked_and_invoked_finding_nothing_are_different_answers(self) -> None:
        """Frankie's three questions, and the first two of them must not collide."""
        withheld = matcher()
        withheld.withhold(member_id="x", sides="AB", scope=SCOPE, note="never handed over")
        withheld.finalize()
        invoked = matcher()
        invoked.offer(member_id="x", sides="AB", coordinate=1, scope=SCOPE)
        invoked.finalize()
        self.assertEqual(withheld.summary()["pairs_formed"], invoked.summary()["pairs_formed"])
        self.assertNotEqual(
            withheld.summary()["unmatched_reason_counts"],
            invoked.summary()["unmatched_reason_counts"],
        )
        self.assertEqual(invoked.summary()["unmatched_reason_counts"][NO_COUNTERPART_IN_SCOPE], 1)

    def test_section_4_4_contributes_averaged_rows_even_with_no_pairs(self) -> None:
        """The delivered artifact's other half: 4.4 emitted no rows of its own at all."""
        m = matcher()
        m.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        m.finalize()
        rows = m.companion_rows()
        self.assertTrue(rows)
        distance_rows = [r for r in rows if r["measure"] == "matching_distance"]
        self.assertEqual(distance_rows[0]["value"]["n"], 0)
        self.assertEqual(distance_rows[0]["excluded_missing_members"], 1)


class UnmatchedReasonTest(unittest.TestCase):
    def test_no_counterpart_in_scope_is_not_a_distance_failure(self) -> None:
        m = matcher()
        m.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        m.finalize()
        self.assertEqual(m.unmatched[0]["unmatched_reason"], NO_COUNTERPART_IN_SCOPE)
        self.assertIsNone(
            m.unmatched[0]["nearest_candidate_distance"],
            "no comparison happened, so there is no distance; zero would be a perfect match",
        )

    def test_a_member_with_no_counterpart_contributes_no_distance_rather_than_a_zero(self) -> None:
        """The measure must EXCLUDE it. A zero distance reads as a perfect match on every
        quantile, and it is the shape that would make a matcher pairing nothing look like a
        matcher pairing everything exactly."""
        m = matcher()
        m.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        m.finalize()
        near = m.summary()["unmatched_nearest_candidate_distance"]
        self.assertEqual(near["n"], 0)
        self.assertIsNone(near["minimum"])
        (row,) = [
            r for r in m.companion_rows() if r["measure"] == "unmatched_nearest_candidate_distance"
        ]
        self.assertEqual(row["value"]["n"], 0)
        self.assertEqual(row["excluded_missing_members"], 1)

    def test_a_counterpart_outside_the_bound_reports_the_distance_it_missed_by(self) -> None:
        m = matcher(bound=100.0)
        m.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        m.offer(member_id="b", sides="BA", coordinate=101, scope=SCOPE)
        m.finalize()
        reasons = {row["member_id"]: row["unmatched_reason"] for row in m.unmatched}
        self.assertEqual(reasons, {"a": DISTANCE_ABOVE_BOUND, "b": DISTANCE_ABOVE_BOUND})
        self.assertEqual({row["nearest_candidate_distance"] for row in m.unmatched}, {101.0})

    def test_an_in_bound_counterpart_already_committed_is_an_attribution_result(self) -> None:
        """Blaming the bound for a contest over attribution argues for widening a good bound."""
        m = matcher(bound=1_000.0)
        m.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        m.offer(member_id="b", sides="BA", coordinate=10, scope=SCOPE)
        m.offer(member_id="c", sides="AB", coordinate=20, scope=SCOPE)
        m.finalize()
        (row,) = m.unmatched
        self.assertEqual(row["member_id"], "c")
        self.assertEqual(row["unmatched_reason"], COUNTERPART_EXHAUSTED)
        self.assertEqual(row["nearest_committed_in_bound_distance"], 10.0)
        self.assertIsNone(row["nearest_free_candidate_distance"])

    def test_a_member_with_no_coordinate_is_counted_and_never_placed_at_zero(self) -> None:
        """An absent covariate is excluded and counted; zero is a position on the axis."""
        m = matcher()
        m.offer(member_id="a", sides="AB", coordinate=None, scope=SCOPE)
        m.offer(member_id="b", sides="BA", coordinate=0, scope=SCOPE)
        m.finalize()
        self.assertEqual(m.summary()["pairs_formed"], 0)
        reasons = {row["member_id"]: row["unmatched_reason"] for row in m.unmatched}
        self.assertEqual(reasons["a"], COORDINATE_ABSENT)
        self.assertIsNone([r for r in m.unmatched if r["member_id"] == "a"][0]["coordinate"])

    def test_a_side_string_that_is_its_own_mirror_is_declared_unpairable(self) -> None:
        """`NNN` mirrors to `NNN`; pairing them would make a pair of two CANONICAL halves."""
        m = matcher()
        m.offer(member_id="a", sides="NNN", coordinate=0, scope=SCOPE)
        m.offer(member_id="b", sides="NNN", coordinate=1, scope=SCOPE)
        m.finalize()
        self.assertEqual(m.summary()["unmatched_reason_counts"][SELF_MIRROR], 2)
        self.assertEqual(m.summary()["pairs_formed"], 0)

    def test_the_diagnosis_does_not_depend_on_which_half_arrived_first(self) -> None:
        """Without a symmetric consideration record the earlier member reports no counterpart."""
        first = matcher(bound=10.0)
        first.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        first.offer(member_id="b", sides="BA", coordinate=500, scope=SCOPE)
        first.finalize()
        second = matcher(bound=10.0)
        second.offer(member_id="b", sides="BA", coordinate=500, scope=SCOPE)
        second.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        second.finalize()
        self.assertEqual(
            {r["member_id"]: r["unmatched_reason"] for r in first.unmatched},
            {r["member_id"]: r["unmatched_reason"] for r in second.unmatched},
        )
        self.assertEqual(
            first.summary()["unmatched_reason_counts"], second.summary()["unmatched_reason_counts"]
        )
        self.assertEqual(first.summary()["unmatched_reason_counts"][DISTANCE_ABOVE_BOUND], 2)


class AccountingTest(unittest.TestCase):
    """The reason vocabulary is closed by arithmetic, not by having thought hard enough."""

    def test_every_member_seen_is_either_paired_or_carries_one_reason(self) -> None:
        m = matcher(bound=50.0)
        m.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        m.offer(member_id="b", sides="BA", coordinate=10, scope=SCOPE)
        m.offer(member_id="c", sides="AB", coordinate=9_000, scope=SCOPE)
        m.offer(member_id="d", sides="NNN", coordinate=1, scope=SCOPE)
        m.withhold(member_id="e", sides="AB", scope=SCOPE, note="producer declined")
        m.finalize()
        summary = m.summary()
        self.assertEqual(
            summary["members_seen"],
            2 * summary["pairs_formed"] + sum(summary["unmatched_reason_counts"].values()),
        )
        self.assertEqual(len(m.unmatched), summary["members_unmatched"])

    def test_a_member_that_leaves_the_population_unaccounted_fails_the_run(self) -> None:
        """Mutation check: the identity is enforced, not merely satisfied by construction."""
        m = matcher()
        m.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        m.members_seen += 1
        with self.assertRaises(MirrorError):
            m.finalize()

    def test_days_and_scopes_do_not_pair_across(self) -> None:
        m = matcher()
        m.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        m.offer(member_id="b", sides="BA", coordinate=0, scope=OTHER_DAY)
        m.finalize()
        self.assertEqual(m.summary()["pairs_formed"], 0)
        self.assertEqual(m.summary()["unmatched_reason_counts"][NO_COUNTERPART_IN_SCOPE], 2)

    def test_offering_or_withholding_after_finalize_is_refused(self) -> None:
        m = matcher()
        m.finalize()
        with self.assertRaises(MirrorError):
            m.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        with self.assertRaises(MirrorError):
            m.withhold(member_id="a", sides="AB", scope=SCOPE, note="late")
        with self.assertRaises(MirrorError):
            m.finalize()

    def test_a_withheld_member_without_a_stated_reason_is_refused(self) -> None:
        m = matcher()
        with self.assertRaises(MirrorError):
            m.withhold(member_id="a", sides="AB", scope=SCOPE, note="   ")


class FormedPairTest(unittest.TestCase):
    def test_a_pair_carries_its_id_both_members_and_the_exact_difference(self) -> None:
        m = matcher()
        m.offer(member_id="a", sides="AB", coordinate=100, scope=SCOPE)
        m.offer(member_id="b", sides="BA", coordinate=40, scope=SCOPE)
        m.finalize()
        (pair,) = m.pairs
        self.assertEqual(pair["pair_id"], 0)
        self.assertEqual(pair["canonical_member_id"], "a")
        self.assertEqual(pair["mirror_member_id"], "b")
        self.assertEqual(pair["exact_difference"], 60.0)
        self.assertEqual(pair["matching_distance"], 60.0)

    def test_the_exact_difference_is_oriented_by_the_pair_key_not_by_arrival(self) -> None:
        """A sign that flips with input order is noise wearing a measurement's name."""
        forward = matcher()
        forward.offer(member_id="a", sides="AB", coordinate=100, scope=SCOPE)
        forward.offer(member_id="b", sides="BA", coordinate=40, scope=SCOPE)
        reverse = matcher()
        reverse.offer(member_id="b", sides="BA", coordinate=40, scope=SCOPE)
        reverse.offer(member_id="a", sides="AB", coordinate=100, scope=SCOPE)
        self.assertEqual(forward.pairs[0]["exact_difference"], reverse.pairs[0]["exact_difference"])

    def test_the_nearest_admissible_counterpart_wins(self) -> None:
        m = matcher()
        m.offer(member_id="far", sides="BA", coordinate=0, scope=SCOPE)
        m.offer(member_id="near", sides="BA", coordinate=90, scope=SCOPE)
        m.offer(member_id="a", sides="AB", coordinate=100, scope=SCOPE)
        m.finalize()
        self.assertEqual(m.pairs[0]["mirror_member_id"], "near")
        self.assertEqual(m.pairs[0]["matching_distance"], 10.0)

    def test_attribution_is_one_to_one_and_the_multiplicity_is_stated(self) -> None:
        """D-3's lesson applied before the fact: the multiplicity is a field, not a division."""
        m = matcher()
        m.offer(member_id="b", sides="BA", coordinate=0, scope=SCOPE)
        for index in range(3):
            m.offer(member_id=f"a{index}", sides="AB", coordinate=index, scope=SCOPE)
        m.finalize()
        summary = m.summary()
        self.assertEqual(summary["pairs_formed"], 1)
        self.assertEqual(summary["matching_rule"]["attributions_per_member"], 1)
        self.assertEqual(m.pairs[0]["attributions_per_member"], 1)
        self.assertEqual(summary["unmatched_reason_counts"][COUNTERPART_EXHAUSTED], 2)

    def test_the_pair_stratum_is_neither_half_s_orientation(self) -> None:
        """A pair spans the one dimension a mirror must span; it does not pool the two halves."""
        m = matcher()
        m.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        m.offer(member_id="b", sides="BA", coordinate=1, scope=SCOPE)
        m.finalize()
        self.assertEqual(m.pairs[0]["stratum"]["side_orientation"], native_mirror.PAIRED)
        self.assertNotIn(native_mirror.PAIRED, native_mirror.VALID_ORIENTATIONS)


class DeclarationTest(unittest.TestCase):
    """D-16's second half: 4.4 was the only estimand whose rule could not be read off output."""

    def test_the_matching_rule_is_readable_from_the_summary(self) -> None:
        m = matcher(bound=250.0)
        rule = m.summary()["matching_rule"]
        self.assertEqual(rule["coordinate_name"], "birth_recv_ns")
        self.assertEqual(rule["distance_bound"], 250.0)
        self.assertIn("birth_recv_ns", rule["distance_formula"])
        self.assertEqual(rule["attribution"], "ONE_TO_ONE")
        self.assertIn("source_day", rule["scope_fields"])

    def test_the_bound_and_the_coordinate_travel_on_every_row(self) -> None:
        """A caveat that lives only in the summary expires when a row is read alone."""
        m = matcher(bound=250.0)
        m.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        m.offer(member_id="b", sides="BA", coordinate=1, scope=SCOPE)
        m.offer(member_id="c", sides="AB", coordinate=99_999, scope=SCOPE)
        m.finalize()
        for row in m.pairs + m.unmatched:
            with self.subTest(row=row.get("pair_id", row.get("member_id"))):
                self.assertEqual(row["distance_bound"], 250.0)
                self.assertEqual(row["coordinate_name"], "birth_recv_ns")
                self.assertEqual(row["matching_rule"], native_mirror.MATCHING_RULE_ID)

    def test_the_distance_measure_declares_its_missingness_rule(self) -> None:
        m = matcher()
        m.offer(member_id="a", sides="AB", coordinate=0, scope=SCOPE)
        m.finalize()
        row = [r for r in m.companion_rows() if r["measure"] == "unmatched_nearest_candidate_distance"][0]
        self.assertIn("never entered as a distance of zero", row["declaration"]["missingness_rule"])

    def test_an_unnamed_coordinate_or_negative_bound_is_refused(self) -> None:
        with self.assertRaises(MirrorError):
            MirrorMatcher(coordinate_name="  ", distance_bound=1.0)
        with self.assertRaises(MirrorError):
            MirrorMatcher(coordinate_name="birth_recv_ns", distance_bound=-1.0)

if __name__ == "__main__":
    unittest.main()
