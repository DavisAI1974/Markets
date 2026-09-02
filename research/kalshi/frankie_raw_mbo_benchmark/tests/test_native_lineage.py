"""Tests for section 4.13 chain families and D-depth lineages."""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark.native_lineage import (
    CENSORED_SEGMENT_END,
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

    def censored_root(self, node_id: str, entered_recv_ns: int, status: str = CENSORED_STREAM_END):
        """A censored stage as the traversal actually produces one: NO exit time.

        `exited_recv_ns` is stamped by a node's own successor, so the census of censored
        stages - the ones that never got a successor - is exactly the census of nodes without
        one. Building a censored node WITH an exit is what the old tests did, and it is why
        D-9 survived a green suite: the fabricated field made the broken predicate look fed.
        """
        node = self.graph.add(
            node_id=node_id,
            parent_id=None,
            transition_type="BIRTH",
            side_orientation="B",
            entered_recv_ns=entered_recv_ns,
        )
        node.status = status
        return node

    def test_terminated_and_censored_stages_never_pool(self) -> None:
        terminated = self.graph.add(
            node_id="t", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        terminated.exited_recv_ns = 500
        terminated.status = TERMINATED
        censored = self.censored_root("c", 0)
        self.calc.observe_node(terminated, self.graph, **CTX)
        self.calc.observe_node(censored, self.graph, censoring_recv_ns=900, **CTX)
        self.assertEqual(sum(r["value"]["n"] for r in self.calc.stage_duration.rows()), 1)
        self.assertEqual(sum(r["value"]["n"] for r in self.calc.censored_stage_age.rows()), 1)

    def test_a_censored_stage_is_aged_on_the_censoring_clock(self) -> None:
        """D-9. The censored channel excluded 100% of the censored population.

        `censored_stage_age_ns` read n=0 across all 17 strata with 21,651 excluded while the
        section's own status counts said 21,603 were CENSORED_STREAM_END. The cause is that
        the age was read off `stage_duration_ns`, which is `exited_recv_ns - entered_recv_ns`,
        and only a successor writes `exited_recv_ns` - so a censored stage could not have one
        by definition. 4.6 does not have the hole because its caller passes the boundary time
        in at the moment it censors; 4.13 now takes the same input.
        """
        node = self.censored_root("c", 1_000)
        self.calc.observe_node(node, self.graph, censoring_recv_ns=5_000, **CTX)
        rows = self.calc.censored_stage_age.rows()
        self.assertEqual(sum(r["value"]["n"] for r in rows), 1)
        self.assertEqual(max(r["value"]["maximum"] for r in rows), 4_000.0)
        self.assertEqual(sum(r["excluded_missing_members"] for r in rows), 0)

    def test_every_censored_stage_reaches_the_censored_channel(self) -> None:
        """The D-9 shape at scale: censored nodes many, censored observations none.

        Sixteen censored roots and one terminated stage, the same ratio the Sunday run had.
        The old predicate put all sixteen in `excluded_missing_members` and left the measure
        empty, so the assertion that catches it is n against the censored population, not
        n against zero.
        """
        for index in range(16):
            node = self.censored_root(f"c{index}", index * 10)
            self.calc.observe_node(node, self.graph, censoring_recv_ns=10_000, **CTX)
        terminated = self.graph.add(
            node_id="t", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        terminated.exited_recv_ns = 400
        terminated.status = TERMINATED
        self.calc.observe_node(terminated, self.graph, censoring_recv_ns=10_000, **CTX)

        summary = self.calc.summary()
        coverage = summary["censored_stage_age_coverage"]
        self.assertEqual(coverage["censored_stages_seen"], 16)
        self.assertEqual(coverage["censored_stage_age_observed"], 16)
        self.assertEqual(coverage["censored_stage_age_unmeasurable_no_censoring_clock"], 0)
        self.assertEqual(
            sum(r["value"]["n"] for r in self.calc.censored_stage_age.rows()),
            summary["status_counts"][CENSORED_STREAM_END],
            "the censored channel must observe the population it declares",
        )
        # The terminated stage is still excluded from the censored channel, and the censored
        # ones from stage_duration: fixing the hole must not merge the two populations.
        self.assertEqual(sum(r["value"]["n"] for r in self.calc.stage_duration.rows()), 1)

    def test_a_censoring_with_no_clock_is_counted_and_never_zeroed(self) -> None:
        """An absence is excluded and counted; a zero would say censored at the entry instant.

        This is the branch that is still live in the traversal until `_close_lineage` passes
        its boundary `recv_ns` through, so it has to be visible in the summary rather than
        silently absorbed by the per-stratum exclusion count.
        """
        node = self.censored_root("c", 1_000, status=CENSORED_SEGMENT_END)
        self.calc.observe_node(node, self.graph, **CTX)
        rows = self.calc.censored_stage_age.rows()
        self.assertEqual(sum(r["value"]["n"] for r in rows), 0, "no age may be invented")
        self.assertEqual(sum(r["excluded_missing_members"] for r in rows), 1)
        coverage = self.calc.summary()["censored_stage_age_coverage"]
        self.assertEqual(coverage["censored_stages_seen"], 1)
        self.assertEqual(coverage["censored_stage_age_observed"], 0)
        self.assertEqual(coverage["censored_stage_age_unmeasurable_no_censoring_clock"], 1)

    def test_a_censoring_before_the_stage_it_censors_is_refused(self) -> None:
        node = self.censored_root("c", 5_000)
        with self.assertRaises(LineageError):
            self.calc.observe_node(node, self.graph, censoring_recv_ns=4_999, **CTX)

    def test_a_stage_that_ended_cannot_be_censored(self) -> None:
        """An exit means a qualifying successor took over, which is what TERMINATED means.

        Refused loudly rather than excluded, because an exclusion here is indistinguishable
        from the ordinary no-clock case and would put an ended stage in the censored count.
        """
        node = self.censored_root("c", 0)
        node.exited_recv_ns = 900
        with self.assertRaises(LineageError):
            self.calc.observe_node(node, self.graph, censoring_recv_ns=1_500, **CTX)

    def test_a_terminated_stage_without_an_exit_is_refused(self) -> None:
        node = self.graph.add(
            node_id="t", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        node.status = TERMINATED
        with self.assertRaises(LineageError):
            self.calc.observe_node(node, self.graph, **CTX)

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

    def test_the_two_root_counts_are_named_and_reconcile(self) -> None:
        """D-15. `d0_roots` 21,296 sat beside `role_counts.ROOT` 21,344 with nothing naming
        the 48 between them.

        They are two populations, not one number twice: every parentless node, and 4.13's D0
        class of a root with NO qualifying successor. The gap is `roots_with_a_qualifying
        _successor`, which is now counted in its own right so the identity is a check rather
        than a definition.
        """
        parent = self.graph.add(
            node_id="p", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        child = self.graph.add(
            node_id="k", parent_id="p", transition_type="EXTEND", side_orientation="B", entered_recv_ns=100
        )
        parent.status = TERMINATED
        child.status = CENSORED_STREAM_END
        lonely = [self.censored_root(f"r{i}", i * 10) for i in range(2)]
        for node in (parent, child, *lonely):
            self.calc.observe_node(node, self.graph, censoring_recv_ns=1_000, **CTX)

        summary = self.calc.summary()
        reconciliation = summary["root_reconciliation"]
        self.assertEqual(reconciliation["roots_total"], 3)
        self.assertEqual(reconciliation["d0_roots"], 2)
        self.assertEqual(reconciliation["roots_with_a_qualifying_successor"], 1)
        self.assertTrue(reconciliation["identity_holds"])
        self.assertEqual(reconciliation["roots_total"], summary["role_counts"][ROOT])
        self.assertEqual(reconciliation["d0_roots_means"], "ROOTS_WITH_NO_QUALIFYING_SUCCESSOR")
        self.assertEqual(reconciliation["roots_total_means"], "EVERY_NODE_WITH_NO_PARENT")

    def test_the_depth_zero_row_is_every_root_not_the_d0_class(self) -> None:
        """The other half of D-15: two different things are both called D0.

        The depth distribution's D0 row counted 21,344 - every depth-zero node - while
        `d0_roots` counted the 21,296 childless ones, and the label alone could not tell them
        apart. The distribution row now declares its population, and the exact gap between
        the two is the roots that acquired a successor.
        """
        parent = self.graph.add(
            node_id="p", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        child = self.graph.add(
            node_id="k", parent_id="p", transition_type="EXTEND", side_orientation="B", entered_recv_ns=100
        )
        parent.status = TERMINATED
        child.status = CENSORED_STREAM_END
        for node in (parent, child, self.censored_root("r0", 0), self.censored_root("r1", 5)):
            self.calc.observe_node(node, self.graph, censoring_recv_ns=1_000, **CTX)

        summary = self.calc.summary()
        d0_row = next(r for r in summary["depth_distribution"] if r["depth"] == 0)
        self.assertEqual(d0_row["depth_label"], "D0")
        self.assertEqual(d0_row["count"], 3)
        self.assertEqual(d0_row["counted_population"], "every node at this exact depth")
        self.assertEqual(summary["d0_roots"], 2)
        self.assertTrue(summary["root_reconciliation"]["depth0_equals_roots_total"])
        self.assertEqual(
            d0_row["count"] - summary["d0_roots"],
            summary["root_reconciliation"]["roots_with_a_qualifying_successor"],
        )

    def test_the_root_gap_is_not_the_terminated_count_below_depth_one(self) -> None:
        """The 48 coincidence was a property of that day, not an identity.

        On the Sunday run the root gap equalled `status_counts.TERMINATED` only because
        observed max depth was 1, so every parent happened to be a root. With a D2 chain a
        descendant is a parent too, and defining `d0_roots` as ROOT minus TERMINATED - the
        arithmetic the gap invites - would then be wrong by exactly the deep parents.
        """
        n0 = self.graph.add(
            node_id="n0", parent_id=None, transition_type="BIRTH", side_orientation="B", entered_recv_ns=0
        )
        n1 = self.graph.add(
            node_id="n1", parent_id="n0", transition_type="EXTEND", side_orientation="B", entered_recv_ns=100
        )
        n2 = self.graph.add(
            node_id="n2", parent_id="n1", transition_type="EXTEND", side_orientation="B", entered_recv_ns=200
        )
        n0.status = TERMINATED
        n1.status = TERMINATED
        n2.status = CENSORED_STREAM_END
        for node in (n0, n1, n2, self.censored_root("r0", 0), self.censored_root("r1", 5)):
            self.calc.observe_node(node, self.graph, censoring_recv_ns=1_000, **CTX)

        summary = self.calc.summary()
        reconciliation = summary["root_reconciliation"]
        self.assertEqual(summary["observed_max_depth"], 2)
        self.assertEqual(reconciliation["roots_total"], 3)
        self.assertEqual(reconciliation["d0_roots"], 2)
        self.assertEqual(reconciliation["roots_with_a_qualifying_successor"], 1)
        self.assertEqual(reconciliation["nodes_with_a_qualifying_successor"], 2)
        self.assertEqual(summary["status_counts"][TERMINATED], 2)
        self.assertTrue(reconciliation["terminated_equals_nodes_with_a_successor"])
        self.assertNotEqual(
            reconciliation["roots_with_a_qualifying_successor"],
            summary["status_counts"][TERMINATED],
            "ROOT minus TERMINATED is not d0_roots once a descendant has a child",
        )
        self.assertTrue(reconciliation["identity_holds"])

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
