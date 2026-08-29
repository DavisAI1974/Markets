"""Tests for section 4.14 recurrence, bursts, and transition graphs."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_recurrence import (
    Occurrence,
    RecurrenceCalculator,
    RecurrenceError,
    TransitionGraph,
    burst_view,
    homogeneous_runs,
    interarrival_gaps,
)

CTX = dict(
    source_day="20211004",
    source_role="HELD_OUT_BLIND",
    family_id="TFCN",
    side_orientation="B",
    session_phase="RTH",
)


def occ(node: str, recv_ns: int, segment: int = 0, order_id: int | None = None) -> Occurrence:
    return Occurrence(node=node, recv_ns=recv_ns, continuity_segment=segment, order_id=order_id)


class RunsAndGapsTest(unittest.TestCase):
    def test_maximal_homogeneous_runs(self) -> None:
        runs = homogeneous_runs([occ("A", 0), occ("A", 10), occ("B", 20), occ("A", 30)])
        self.assertEqual([(r.node, r.length) for r in runs], [("A", 2), ("B", 1), ("A", 1)])
        self.assertEqual(runs[0].duration_ns, 10)

    def test_a_run_never_spans_a_continuity_boundary(self) -> None:
        """The gap across a boundary was never observed; a bridging run would claim it."""
        runs = homogeneous_runs([occ("A", 0, segment=0), occ("A", 10, segment=1)])
        self.assertEqual(len(runs), 2)
        self.assertEqual([r.continuity_segment for r in runs], [0, 1])

    def test_gaps_are_exact_and_never_cross_a_boundary(self) -> None:
        gaps = interarrival_gaps([occ("A", 0), occ("B", 25), occ("C", 40, segment=1)])
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["gap_ns"], 25)
        self.assertEqual(gaps[0]["from_node"], "A")
        self.assertEqual(gaps[0]["to_node"], "B")

    def test_a_single_occurrence_has_no_gaps(self) -> None:
        self.assertEqual(interarrival_gaps([occ("A", 0)]), [])


class BurstViewTest(unittest.TestCase):
    def setUp(self) -> None:
        self.gaps = interarrival_gaps([occ("A", 0), occ("A", 5), occ("A", 500), occ("A", 505)])

    def test_a_burst_view_labels_gaps_and_gates_nothing(self) -> None:
        """Section 4.14: a threshold is a descriptive view, never a membership gate."""
        view = burst_view(self.gaps, threshold_ns=10, version="v1")
        self.assertFalse(view["is_membership_gate"])
        self.assertEqual(view["gap_count"], len(self.gaps), "no gap was removed")
        self.assertEqual(view["in_burst_count"], 2)

    def test_changing_the_threshold_changes_labels_not_the_population(self) -> None:
        loose = burst_view(self.gaps, threshold_ns=1_000, version="v2")
        tight = burst_view(self.gaps, threshold_ns=10, version="v1")
        self.assertEqual(loose["gap_count"], tight["gap_count"])
        self.assertNotEqual(loose["in_burst_count"], tight["in_burst_count"])

    def test_the_threshold_version_travels_with_the_output(self) -> None:
        view = burst_view(self.gaps, threshold_ns=10, version="v1")
        self.assertEqual(view["threshold_version"], "v1")
        self.assertEqual(view["threshold_ns"], 10)

    def test_the_burst_share_is_labelled_a_rate(self) -> None:
        view = burst_view(self.gaps, threshold_ns=10, version="v1")
        self.assertTrue(view["share_is_a_rate_not_a_mean"])

    def test_a_nonpositive_threshold_is_refused(self) -> None:
        with self.assertRaises(RecurrenceError):
            burst_view(self.gaps, threshold_ns=0, version="v1")


class TransitionGraphTest(unittest.TestCase):
    def test_edges_carry_counts_and_their_own_denominator(self) -> None:
        graph = TransitionGraph()
        graph.add_edge("A", "B")
        graph.add_edge("A", "B")
        graph.add_edge("A", "C")
        rows = {(r["from_node"], r["to_node"]): r for r in graph.rows()}
        ab = rows[("A", "B")]
        self.assertEqual(ab["transition_count"], 2)
        self.assertEqual(ab["outgoing_denominator"], 3)
        self.assertAlmostEqual(ab["conditional_probability"], 2 / 3)

    def test_a_conditional_probability_is_not_labelled_a_mean(self) -> None:
        """Section 4.14 forbids mislabeling probabilities as averages."""
        graph = TransitionGraph()
        graph.add_edge("A", "B")
        row = graph.rows()[0]
        self.assertEqual(row["statistic_kind"], "CONDITIONAL_PROBABILITY")
        self.assertFalse(row["is_arithmetic_mean"])

    def test_outgoing_probabilities_sum_to_one_per_source(self) -> None:
        graph = TransitionGraph()
        graph.add_edge("A", "B", 3)
        graph.add_edge("A", "C", 1)
        total = sum(r["conditional_probability"] for r in graph.rows() if r["from_node"] == "A")
        self.assertAlmostEqual(total, 1.0)


class RecurrenceCalculatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = RecurrenceCalculator()

    def test_runs_and_gaps_are_accumulated_per_node(self) -> None:
        self.calc.observe_sequence([occ("A", 0), occ("A", 10), occ("B", 40)], **CTX)
        rows = {r["stratum"]["subfamily_id"]: r["value"] for r in self.calc.run_length.rows()}
        self.assertEqual(rows["node=A"]["maximum"], 2.0)
        self.assertEqual(rows["node=B"]["maximum"], 1.0)

    def test_gaps_are_attributed_to_the_destination_node(self) -> None:
        self.calc.observe_sequence([occ("A", 0), occ("B", 40)], **CTX)
        rows = {r["stratum"]["subfamily_id"]: r["value"] for r in self.calc.interarrival_gap.rows()}
        self.assertEqual(rows["node=B"]["maximum"], 40.0)

    def test_unordered_occurrences_are_refused(self) -> None:
        with self.assertRaises(RecurrenceError):
            self.calc.observe_sequence([occ("A", 100), occ("B", 10)], **CTX)

    def test_boundary_restarts_are_counted_and_excluded_from_gaps(self) -> None:
        self.calc.observe_sequence([occ("A", 0, segment=0), occ("A", 10, segment=1)], **CTX)
        self.assertEqual(self.calc.summary()["boundary_restarts"], 1)
        gap_rows = self.calc.interarrival_gap.rows()
        self.assertEqual(sum(r["value"]["n"] for r in gap_rows), 0)
        self.assertEqual(sum(r["excluded_missing_members"] for r in gap_rows), 1)

    def test_segments_do_not_pool(self) -> None:
        self.calc.observe_sequence([occ("A", 0, segment=0), occ("A", 10, segment=1)], **CTX)
        segments = {r["stratum"]["continuity_segment"] for r in self.calc.run_length.rows()}
        self.assertEqual(segments, {0, 1})

    def test_single_occurrence_run_has_zero_duration_which_is_an_observation(self) -> None:
        self.calc.observe_sequence([occ("A", 5)], **CTX)
        row = self.calc.run_duration.rows()[0]
        self.assertEqual(row["value"]["n"], 1)
        self.assertEqual(row["value"]["maximum"], 0.0)

    def test_transition_edges_are_built_from_the_sequence(self) -> None:
        self.calc.observe_sequence([occ("A", 0), occ("B", 10), occ("A", 20), occ("B", 30)], **CTX)
        edges = {(r["from_node"], r["to_node"]): r for r in self.calc.summary()["transition_edges"]}
        self.assertEqual(edges[("A", "B")]["transition_count"], 2)
        self.assertEqual(edges[("B", "A")]["transition_count"], 1)

    def test_same_order_paths_are_tracked(self) -> None:
        self.calc.observe_sequence(
            [occ("A", 0, order_id=7), occ("B", 10, order_id=7), occ("A", 20, order_id=8)], **CTX
        )
        summary = self.calc.summary()
        self.assertEqual(summary["same_order_paths"], 2)
        self.assertEqual(summary["multi_occurrence_order_paths"], 1)

    def test_days_do_not_pool(self) -> None:
        self.calc.observe_sequence([occ("A", 0)], **{**CTX, "source_day": "20211004"})
        self.calc.observe_sequence([occ("A", 0)], **{**CTX, "source_day": "20211005"})
        self.assertEqual(self.calc.run_length.stratum_count, 2)

    def test_summary_names_the_canonical_evidence(self) -> None:
        self.calc.observe_sequence([occ("A", 0), occ("A", 10)], **CTX)
        summary = self.calc.summary()
        self.assertEqual(summary["section"], "4.14")
        self.assertEqual(summary["canonical_evidence"], "THRESHOLD_FREE_EXACT_GAPS")
        self.assertEqual(summary["occurrences_seen"], 2)


if __name__ == "__main__":
    unittest.main()
