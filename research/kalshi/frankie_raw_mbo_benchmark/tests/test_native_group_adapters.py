"""Tests for the section-4 group adapters (D53: the F_LAST group is the unit).

These pin the CONSTRUCTION choices, not just that the code runs. Each choice is one the
module could have made differently, and a silent change to any of them would re-cut every
stratum downstream without failing anything - which is the defect shape this tree keeps
finding (S108 off-instrument, S109 `session_b_share`, the 2026-08-29 `_family_id` split).
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark import native_group_adapters as ga
from research.kalshi.frankie_raw_mbo_benchmark.native_absorption import (
    AbsorptionCalculator,
    RunwayPressure,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_ladder import LadderCalculator
from research.kalshi.frankie_raw_mbo_benchmark.native_lineage import LineageGraph
from research.kalshi.frankie_raw_mbo_benchmark.native_recurrence import RecurrenceCalculator


def ctx(**over):
    base = dict(
        group_index=0,
        source_day="20211001",
        source_role="SCORED_FINDINGS_DAY",
        continuity_segment=18901,
        session_phase="PRE_SETTLEMENT",
        family_id="ow-abc",
        side_orientation="B",
        event_ns=90,
        recv_ns=130,
        instrument_id=42,
    )
    base.update(over)
    return ga.GroupContext(**base)


def row(action, side, order_id, price, size, recv):
    return {
        "action": action,
        "side": side,
        "order_id": order_id,
        "price_raw": price,
        "size": size,
        "ts_recv_ns": recv,
        "ts_event_ns": recv - 10,
    }


CASCADE = [
    row("F", "B", 11, 3000, 5, 100),
    row("F", "B", 12, 3000, 3, 110),
    row("C", "A", 13, 3010, 4, 120),
    row("A", "B", 14, 2999, 7, 130),
]


class GuardTests(unittest.TestCase):
    def test_empty_group_is_refused_everywhere(self):
        for fn in (ga.occurrences, ga.ladder_transitions):
            with self.assertRaises(ga.GroupAdapterError):
                fn([], ctx())
        with self.assertRaises(ga.GroupAdapterError):
            ga.runway_pressure_fields([], ctx())

    def test_negative_size_raises_rather_than_clamping(self):
        # max(0, size) would turn a malformed row into a silent zero: present, typed, in
        # range and wrong. The adapter refuses instead.
        bad = [row("F", "B", 11, 3000, -1, 100)]
        with self.assertRaises(ga.GroupAdapterError):
            ga.runway_pressure_fields(bad, ctx())

    def test_sentinel_price_is_dropped_not_treated_as_a_level(self):
        rows = [row("A", "B", 11, ga.PRICE_SENTINEL_ABS, 5, 100)]
        self.assertEqual(ga.ladder_transitions(rows, ctx()), {})


class RecurrenceConstructionTests(unittest.TestCase):
    def test_node_label_keeps_the_two_sides_apart(self):
        # A cancel on the bid and a cancel on the ask must be different nodes. Collapsing
        # them pools two sides at construction time, where no later check could see it.
        nodes = [o.node for o in ga.occurrences(CASCADE, ctx())]
        self.assertEqual(nodes, ["F|B", "F|B", "C|A", "A|B"])

    def test_one_occurrence_per_action_in_tape_order(self):
        occ = ga.occurrences(CASCADE, ctx())
        self.assertEqual(len(occ), len(CASCADE))
        self.assertEqual([o.recv_ns for o in occ], [100, 110, 120, 130])

    def test_feeds_the_real_calculator(self):
        out = RecurrenceCalculator().observe_sequence(
            ga.occurrences(CASCADE, ctx()),
            source_day="20211001",
            source_role="SCORED_FINDINGS_DAY",
            family_id="ow-abc",
            side_orientation="B",
            session_phase="PRE_SETTLEMENT",
        )
        runs = {r["node"]: r["length"] for r in out["runs"]}
        self.assertEqual(runs["F|B"], 2)  # the two consecutive fills are one run
        self.assertEqual(out["gap_count"], 3)


class LadderConstructionTests(unittest.TestCase):
    def test_before_is_consumed_depth_and_after_is_left_depth(self):
        trans = ga.ladder_transitions(CASCADE, ctx())
        bid = trans["B"]
        # Consumed: two fills at 3000 totalling 8. Left: one add at 2999 of 7.
        self.assertEqual(dict(bid.before.depth_by_price), {3000: 8})
        self.assertEqual(dict(bid.after.depth_by_price), {2999: 7})

    def test_sides_never_mix(self):
        trans = ga.ladder_transitions(CASCADE, ctx())
        self.assertEqual(set(trans), {"B", "A"})
        self.assertEqual(dict(trans["A"].before.depth_by_price), {3010: 4})
        self.assertEqual(dict(trans["A"].after.depth_by_price), {})

    def test_unsided_rows_are_dropped_not_assigned(self):
        # Databento's 'N' side is the tape declining to state a side. Assigning it to one
        # would fabricate the very fact that is missing.
        rows = list(CASCADE) + [row("C", "N", 99, 3005, 50, 140)]
        trans = ga.ladder_transitions(rows, ctx())
        self.assertNotIn(50, dict(trans["B"].before.depth_by_price).values())
        self.assertNotIn(50, dict(trans["A"].before.depth_by_price).values())

    def test_feeds_the_real_calculator_and_births_deaths_are_set_differences(self):
        calc = LadderCalculator()
        out = calc.observe(
            ga.ladder_transitions(CASCADE, ctx())["B"],
            source_day="20211001",
            source_role="SCORED_FINDINGS_DAY",
            continuity_segment=18901,
            family_id="ow-abc",
            session_phase="PRE_SETTLEMENT",
        )
        self.assertEqual(out["level_births"], [2999])
        self.assertEqual(out["level_deaths"], [3000])

    def test_scope_is_declared_as_a_constant_not_only_in_prose(self):
        # S114: a caveat that lives only in a docstring is a caveat that expires.
        self.assertEqual(ga.LADDER_SCOPE, "GROUP_LOCAL_DELTA")


class AbsorptionConstructionTests(unittest.TestCase):
    def test_traded_and_withdrawn_are_never_summed_into_one_depletion(self):
        f = ga.runway_pressure_fields(CASCADE, ctx())
        self.assertEqual(f["traded_quantity"], 8)
        self.assertEqual(f["withdrawn_quantity"], 4)
        self.assertIn("traded_quantity", f)
        self.assertIn("withdrawn_quantity", f)

    def test_opposite_side_retreat_is_measured_against_the_group_orientation(self):
        f = ga.runway_pressure_fields(CASCADE, ctx(side_orientation="B"))
        self.assertEqual(f["opposite_side_retreat_quantity"], 4)  # the ask cancel
        self.assertEqual(f["same_side_replacement_quantity"], 7)  # the bid add
        flipped = ga.runway_pressure_fields(CASCADE, ctx(side_orientation="A"))
        self.assertEqual(flipped["same_side_replacement_quantity"], 0)

    def test_feeds_the_real_calculator(self):
        f = ga.runway_pressure_fields(CASCADE, ctx())
        pressure = RunwayPressure(
            runway_id=ctx().candidate_id,
            instrument_id=42,
            side="B",
            source_day="20211001",
            source_role="SCORED_FINDINGS_DAY",
            continuity_segment=18901,
            family_id="ow-abc",
            session_phase="PRE_SETTLEMENT",
            opened_recv_ns=90,
            closed_recv_ns=130,
            **f,
        )
        out = AbsorptionCalculator().score(pressure)
        self.assertEqual(out["traded_quantity"], 8)
        self.assertEqual(out["withdrawn_quantity"], 4)
        self.assertTrue(out["price_moved"])


class LineageConstructionTests(unittest.TestCase):
    """`lineage_additions` returns argument sets, never constructed nodes with a depth.

    `LineageGraph` derives depth from the parent it holds. Setting depth here too would be a
    second opinion about one fact, and two vocabularies over one quantity do not fail - they
    just disagree. That is the `_family_id` defect of 2026-08-29.
    """

    def test_no_addition_ever_carries_a_depth(self):
        for add in ga.lineage_additions(CASCADE, ctx(), seen_order_ids={}):
            self.assertNotIn("depth", add)

    def test_initiator_is_a_root_and_the_rest_hang_off_it(self):
        adds = ga.lineage_additions(CASCADE, ctx(), seen_order_ids={})
        self.assertEqual(adds[0]["node_id"], "ord-11")
        self.assertIsNone(adds[0]["parent_id"])
        self.assertEqual([a["parent_id"] for a in adds[1:]], ["ord-11"] * 3)

    def test_an_order_id_already_seen_is_not_re_issued(self):
        adds = ga.lineage_additions(
            CASCADE, ctx(), seen_order_ids={11: "ord-11", 12: "ord-12"}
        )
        self.assertEqual([a["node_id"] for a in adds], ["ord-13", "ord-14"])

    def test_the_graph_owns_depth_and_it_accumulates_across_groups(self):
        # The whole reason lineage is cross-group: within one cascade the observable causal
        # structure is one level deep, so a within-group lineage would report max_depth 1
        # forever and read as a measurement rather than an artifact of the unit.
        graph = LineageGraph(lineage_signature="ow-abc")
        for add in ga.lineage_additions(CASCADE, ctx(), seen_order_ids={}):
            graph.add(**add)
        seen = {11: "ord-11", 12: "ord-12", 13: "ord-13", 14: "ord-14"}
        second = [row("F", "B", 14, 2999, 2, 200), row("A", "B", 21, 2998, 4, 210)]
        for add in ga.lineage_additions(second, ctx(group_index=1), seen_order_ids=seen):
            node = graph.add(**add)
            self.assertEqual(node.node_id, "ord-21")
            self.assertEqual(node.parent_id, "ord-14")
            # ord-14 was itself a child, so its child is deeper than the first group reached.
            self.assertEqual(node.depth, 2)
        self.assertEqual(graph.max_depth, 2)


class CandidateIdentityTests(unittest.TestCase):
    def test_candidate_id_is_absolute_so_overlapping_runs_agree(self):
        self.assertEqual(ctx(group_index=7).candidate_id, "grp-20211001-7")

    def test_context_is_frozen(self):
        with self.assertRaises(Exception):
            ctx().continuity_segment = 1


if __name__ == "__main__":
    unittest.main()


class LineageInitiatorTest(unittest.TestCase):
    """A group whose first row names no order id must not orphan its own parent.

    Found by WIRING this adapter rather than by reading it. The first version took
    `actions[0]["order_id"]` as the initiator, and Databento writes `order_id` 0 on rows that
    do not identify a resting order - so any group opening on such a row parented every new
    id on `ord-0`, a node nobody ever added, and `LineageGraph.add` raised. It would have
    killed the traversal on real tape at the first such group, which is a large share of
    them. Built and unfed is not the same as built and correct.
    """

    def test_a_group_opening_on_an_anonymous_row_roots_on_its_first_named_order(self):
        actions = [
            {"action": "T", "side": "A", "order_id": 0, "size": 3, "price_raw": 3_500_000_000,
             "ts_recv_ns": 10},
            {"action": "F", "side": "A", "order_id": 811, "size": 3, "price_raw": 3_500_000_000,
             "ts_recv_ns": 11},
            {"action": "C", "side": "A", "order_id": 812, "size": 1, "price_raw": 3_500_000_000,
             "ts_recv_ns": 12},
        ]
        adds = ga.lineage_additions(actions, ctx(), seen_order_ids={})
        graph = LineageGraph(lineage_signature="ow-abc")
        for add in adds:
            graph.add(**add)          # the assertion: this used to raise on ord-0
        self.assertEqual([a["node_id"] for a in adds], ["ord-811", "ord-812"])
        self.assertIsNone(adds[0]["parent_id"])
        self.assertEqual(adds[1]["parent_id"], "ord-811")

    def test_a_group_naming_no_order_at_all_contributes_no_lineage(self):
        """An absence is recorded as one, not filled with an invented node."""
        actions = [
            {"action": "T", "side": "A", "order_id": 0, "size": 3, "price_raw": 3_500_000_000,
             "ts_recv_ns": 10},
            {"action": "T", "side": "B", "order_id": 0, "size": 2, "price_raw": 3_500_000_000,
             "ts_recv_ns": 11},
        ]
        self.assertEqual(ga.lineage_additions(actions, ctx(), seen_order_ids={}), [])
