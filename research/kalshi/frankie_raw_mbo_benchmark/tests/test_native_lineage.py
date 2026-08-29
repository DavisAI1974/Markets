"""Tests for section 4.13 chain families and D-depth lineages."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_lineage import (
    CENSORED_STREAM_END,
    DESCENDANT,
    OPEN,
    ROOT,
    TERMINATED,
    LineageCalculator,
    LineageError,
    LineageGraph,
)

CTX = dict(
    source_day="20211004",
    source_role="HELD_OUT_BLIND",
    continuity_segment=0,
    session_phase="RTH",
)


class LineageGraphTest(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = LineageGraph(lineage_signature="sig1")

    def test_a_root_is_depth_zero(self) -> None:
        node = self.graph.add(
            node_id="a", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=1_000
        )
        self.assertEqual(node.depth, 0)
        self.assertEqual(node.depth_label, "D0")
        self.assertEqual(node.role, ROOT)

    def test_depth_increments_and_has_no_ceiling(self) -> None:
        """Section 4.13 imposes no maximum depth; clipping would hide deep chains."""
        self.graph.add(
            node_id="n0", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        for index in range(1, 25):
            self.graph.add(
                node_id=f"n{index}",
                parent_id=f"n{index - 1}",
                transition_type="EXTEND",
                side_orientation="B",
                entered_recv_ns=index * 100,
            )
        self.assertEqual(self.graph.max_depth, 24)
        self.assertEqual(self.graph.nodes["n24"].depth_label, "D24")

    def test_a_d0_root_has_no_qualifying_successor(self) -> None:
        self.graph.add(
            node_id="a", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        self.assertTrue(self.graph.is_d0_root("a"))
        self.graph.add(
            node_id="b", parent_id="a", transition_type="EXTEND", side_orientation="B", entered_recv_ns=10
        )
        self.assertFalse(self.graph.is_d0_root("a"), "a root with a successor is no longer D0")

    def test_interstage_delay_is_measured_from_the_parent(self) -> None:
        self.graph.add(
            node_id="a", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=1_000
        )
        self.graph.add(
            node_id="b", parent_id="a", transition_type="EXTEND", side_orientation="B", entered_recv_ns=1_700
        )
        self.assertEqual(self.graph.interstage_delay_ns("b"), 700)
        self.assertIsNone(self.graph.interstage_delay_ns("a"))

    def test_adding_a_child_closes_the_parent_stage(self) -> None:
        self.graph.add(
            node_id="a", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=1_000
        )
        self.graph.add(
            node_id="b", parent_id="a", transition_type="EXTEND", side_orientation="B", entered_recv_ns=1_700
        )
        self.assertEqual(self.graph.nodes["a"].stage_duration_ns, 700)

    def test_a_child_before_its_parent_is_refused(self) -> None:
        self.graph.add(
            node_id="a", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=1_000
        )
        with self.assertRaises(LineageError):
            self.graph.add(
                node_id="b", parent_id="a", transition_type="EXTEND", side_orientation="B", entered_recv_ns=900
            )

    def test_unknown_parent_or_duplicate_node_is_refused(self) -> None:
        with self.assertRaises(LineageError):
            self.graph.add(
                node_id="b", parent_id="ghost", transition_type="X", side_orientation="B", entered_recv_ns=1
            )
        self.graph.add(
            node_id="a", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=1
        )
        with self.assertRaises(LineageError):
            self.graph.add(
                node_id="a", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=2
            )


class LineageCalculatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.calc = LineageCalculator()
        self.graph = LineageGraph(lineage_signature="sig1")

    def chain(self, depth: int, status: str = TERMINATED):
        nodes = []
        previous = None
        for index in range(depth + 1):
            node = self.graph.add(
                node_id=f"n{index}",
                parent_id=previous,
                transition_type="BIRTH" if previous is None else "EXTEND",
                side_orientation="B",
                entered_recv_ns=index * 100,
            )
            previous = node.node_id
            nodes.append(node)
        nodes[-1].exited_recv_ns = (depth + 1) * 100
        for node in nodes:
            node.status = status
        return nodes

    def test_depth_is_a_distribution_of_exact_integers_never_a_mean(self) -> None:
        for node in self.chain(2):
            self.calc.observe_node(node, self.graph, **CTX)
        distribution = self.calc.depth_distribution()
        self.assertEqual([row["depth"] for row in distribution], [0, 1, 2])
        self.assertEqual([row["depth_label"] for row in distribution], ["D0", "D1", "D2"])
        self.assertTrue(all(row["share_is_a_rate_not_a_mean"] for row in distribution))

    def test_there_is_no_mean_depth_anywhere(self) -> None:
        forbidden = {"mean_depth", "average_depth", "depth_mean"}
        self.assertEqual(forbidden & set(dir(self.calc)), set())

    def test_roots_and_descendants_never_pool(self) -> None:
        for node in self.chain(1):
            self.calc.observe_node(node, self.graph, **CTX)
        roles = {r["stratum"]["subfamily_id"] for r in self.calc.interstage_delay.rows()}
        self.assertTrue(any("role=ROOT" in s for s in roles))
        self.assertTrue(any("role=DESCENDANT" in s for s in roles))

    def test_depth_and_status_are_in_the_stratum_key(self) -> None:
        for node in self.chain(1):
            self.calc.observe_node(node, self.graph, **CTX)
        subfamilies = {r["stratum"]["subfamily_id"] for r in self.calc.interstage_delay.rows()}
        self.assertTrue(any("depth=0" in s and "status=TERMINATED" in s for s in subfamilies))
        self.assertTrue(any("depth=1" in s for s in subfamilies))

    def test_roots_are_excluded_from_interstage_delay_and_counted(self) -> None:
        nodes = self.chain(1)
        for node in nodes:
            self.calc.observe_node(node, self.graph, **CTX)
        rows = {r["stratum"]["subfamily_id"]: r for r in self.calc.interstage_delay.rows()}
        root_row = next(r for k, r in rows.items() if "role=ROOT" in k)
        self.assertEqual(root_row["value"]["n"], 0)
        self.assertEqual(root_row["excluded_missing_members"], 1)

    def test_descendant_interstage_delay_is_recorded(self) -> None:
        for node in self.chain(1):
            self.calc.observe_node(node, self.graph, **CTX)
        rows = {r["stratum"]["subfamily_id"]: r for r in self.calc.interstage_delay.rows()}
        child = next(r for k, r in rows.items() if "role=DESCENDANT" in k)
        self.assertEqual(child["value"]["maximum"], 100.0)

    def test_terminated_and_censored_stages_never_pool(self) -> None:
        terminated = self.graph.add(
            node_id="t", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        terminated.exited_recv_ns = 500
        terminated.status = TERMINATED
        censored = self.graph.add(
            node_id="c", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        censored.exited_recv_ns = 900
        censored.status = CENSORED_STREAM_END
        self.calc.observe_node(terminated, self.graph, **CTX)
        self.calc.observe_node(censored, self.graph, **CTX)
        self.assertEqual(sum(r["value"]["n"] for r in self.calc.stage_duration.rows()), 1)
        self.assertEqual(sum(r["value"]["n"] for r in self.calc.censored_stage_age.rows()), 1)

    def test_an_open_stage_contributes_to_neither_duration_measure(self) -> None:
        node = self.graph.add(
            node_id="o", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        node.status = OPEN
        self.calc.observe_node(node, self.graph, **CTX)
        self.assertEqual(sum(r["value"]["n"] for r in self.calc.stage_duration.rows()), 0)
        self.assertEqual(sum(r["value"]["n"] for r in self.calc.censored_stage_age.rows()), 0)

    def test_an_unknown_status_is_refused(self) -> None:
        node = self.graph.add(
            node_id="x", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        node.status = "PROBABLY_DONE"
        with self.assertRaises(LineageError):
            self.calc.observe_node(node, self.graph, **CTX)

    def test_summary_reports_no_imposed_maximum_depth(self) -> None:
        for node in self.chain(3):
            self.calc.observe_node(node, self.graph, **CTX)
        summary = self.calc.summary()
        self.assertEqual(summary["section"], "4.13")
        self.assertIsNone(summary["maximum_depth_imposed"])
        self.assertEqual(summary["observed_max_depth"], 3)
        self.assertEqual(summary["role_counts"][ROOT], 1)
        self.assertEqual(summary["role_counts"][DESCENDANT], 3)

    def test_days_do_not_pool(self) -> None:
        node = self.graph.add(
            node_id="a", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        node.status = TERMINATED
        node.exited_recv_ns = 100
        self.calc.observe_node(node, self.graph, **{**CTX, "source_day": "20211004"})
        self.calc.observe_node(node, self.graph, **{**CTX, "source_day": "20211005"})
        self.assertEqual(self.calc.stage_duration.stratum_count, 2)


if __name__ == "__main__":
    unittest.main()
