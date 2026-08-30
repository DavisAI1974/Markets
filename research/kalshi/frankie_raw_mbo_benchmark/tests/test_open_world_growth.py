"""The carried vocabulary is where discovery starts, not what it is validated against.

Named families, P/O/S/X, the runway phases, D0-D5 and the three pressure dispositions are
all a starting point. Richer data is expected to produce states, phases, depths and
mechanisms nobody has named. These tests exist because the failure they guard against is
silent: a novel structure rounded into the nearest carried label looks like a confirmation
of the label rather than a discovery.
"""
from __future__ import annotations

import unittest

from research.kalshi.frankie_raw_mbo_benchmark import native_exhaustion as ex
from research.kalshi.frankie_raw_mbo_benchmark.native_absorption import (
    ABSORBED_WITHOUT_PRICE_MOVE,
    AbsorptionCalculator,
    RunwayPressure,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_discovery import (
    INCREMENTAL,
    DiscoveryCalculator,
    FeatureSchema,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_lineage import (
    TERMINATED,
    LineageCalculator,
    LineageGraph,
)


class DepthGrowsWithoutLimitTest(unittest.TestCase):
    def test_depth_far_beyond_d5_is_recorded_as_itself(self) -> None:
        graph = LineageGraph(lineage_signature="deep")
        graph.add(node_id="n0", parent_id=None, transition_type="BIRTH",
                  side_orientation="B", entered_recv_ns=0)
        for index in range(1, 41):
            graph.add(node_id=f"n{index}", parent_id=f"n{index - 1}", transition_type="EXTEND",
                      side_orientation="B", entered_recv_ns=index * 10)
        self.assertEqual(graph.max_depth, 40)
        self.assertEqual(graph.nodes["n40"].depth_label, "D40")

    def test_the_summary_states_that_no_maximum_is_imposed(self) -> None:
        calc = LineageCalculator()
        graph = LineageGraph(lineage_signature="deep")
        node = graph.add(node_id="a", parent_id=None, transition_type="BIRTH",
                         side_orientation="B", entered_recv_ns=0)
        node.status = TERMINATED
        node.exited_recv_ns = 10
        calc.observe_node(node, graph, source_day="20211004", source_role="SCORED_FINDINGS_DAY",
                          continuity_segment=0, session_phase="RTH")
        self.assertIsNone(calc.summary()["maximum_depth_imposed"])

    def test_depths_beyond_the_carried_range_get_their_own_strata(self) -> None:
        """A D9 is not folded into D5; depth is in the stratum key as an exact integer."""
        calc = LineageCalculator()
        graph = LineageGraph(lineage_signature="deep")
        previous = None
        for index in range(10):
            node = graph.add(node_id=f"n{index}", parent_id=previous, transition_type="EXTEND",
                             side_orientation="B", entered_recv_ns=index * 10)
            previous = node.node_id
        for node in graph.nodes.values():
            node.status = TERMINATED
            if node.exited_recv_ns is None:
                node.exited_recv_ns = 999
            calc.observe_node(node, graph, source_day="20211004",
                              source_role="SCORED_FINDINGS_DAY", continuity_segment=0,
                              session_phase="RTH")
        depths = {row["depth"] for row in calc.depth_distribution()}
        self.assertEqual(depths, set(range(10)))


class StateVocabularyGrowsTest(unittest.TestCase):
    def setUp(self) -> None:
        ex.DISCOVERED_NAMED_STATES.clear()

    def test_an_unmatched_structure_still_gets_a_stable_identity(self) -> None:
        first = ex.resolve_state_id(None, ["AN", "TFM", "NOVEL"])
        second = ex.resolve_state_id(None, ["AN", "TFM", "NOVEL"])
        self.assertEqual(first, second)
        self.assertTrue(first.startswith("OW_"))

    def test_a_recurring_structure_can_earn_a_durable_name(self) -> None:
        identity = ex.register_discovered_state("cascade_reload", ["TFFCC", "AN", "TFCN"])
        self.assertEqual(identity, "DS_cascade_reload")
        self.assertEqual(ex.resolve_state_id("cascade_reload", []), "DS_cascade_reload")
        self.assertEqual(ex.resolve_state_id("DS_cascade_reload", []), "DS_cascade_reload")

    def test_a_discovered_name_cannot_masquerade_as_a_carried_seed(self) -> None:
        with self.assertRaises(ex.ExhaustionError):
            ex.register_discovered_state("P", ["AN"])

    def test_rebinding_a_discovered_name_to_another_shape_is_refused(self) -> None:
        ex.register_discovered_state("reload", ["A", "B"])
        with self.assertRaises(ex.ExhaustionError):
            ex.register_discovered_state("reload", ["C", "D"])

    def test_an_unregistered_name_is_refused_so_a_typo_is_not_a_new_state(self) -> None:
        with self.assertRaises(ex.ExhaustionError):
            ex.resolve_state_id("casacde_reload", ["AN"])

    def test_carried_seeds_still_pass_through(self) -> None:
        for seed in ("P", "O", "S", "X"):
            self.assertEqual(ex.resolve_state_id(seed, []), seed)


class LandmarkVocabularyGrowsTest(unittest.TestCase):
    """The carried landmarks are a crosswalk, exactly as SEED_STATES is."""

    def setUp(self) -> None:
        for name in list(ex.DISCOVERED_LANDMARKS):
            ex.LANDMARK_INDEX.pop(name, None)
            ex.DISCOVERED_LANDMARKS.pop(name, None)

    @staticmethod
    def _open(calc, candidate_id: str) -> None:
        calc.open_runway(candidate_id=candidate_id, instrument_id=42, side="B",
                         source_day="20211004", source_role="SCORED_FINDINGS_DAY",
                         continuity_segment=0, family_id="F", session_phase="RTH",
                         searched_coverage_ns=10, opened_recv_ns=1_000, seed_state="P")

    def test_a_novel_landmark_can_be_inserted_between_carried_ones(self) -> None:
        position = ex.register_discovered_landmark(
            "REARM", after=ex.T0, before=ex.ENDPOINT_ONSET
        )
        self.assertGreater(position, ex.LANDMARK_INDEX[ex.T0])
        self.assertLess(position, ex.LANDMARK_INDEX[ex.ENDPOINT_ONSET])

    def test_a_runway_can_traverse_a_discovered_landmark(self) -> None:
        ex.register_discovered_landmark("REARM", after=ex.T0, before=ex.ENDPOINT_ONSET)
        calc = ex.ExhaustionCalculator()
        self._open(calc, "c1")
        calc.mark_landmark("c1", ex.T0, 1_100)
        calc.mark_landmark("c1", "REARM", 1_300)
        calc.mark_landmark("c1", ex.ENDPOINT_ONSET, 1_400)
        row = calc.complete("c1", recv_ns=1_500)
        self.assertIn("REARM", [seg["landmark"] for seg in row["segments"]])

    def test_a_discovered_landmark_keeps_ordering_checkable(self) -> None:
        ex.register_discovered_landmark("REARM", after=ex.T0, before=ex.ENDPOINT_ONSET)
        calc = ex.ExhaustionCalculator()
        self._open(calc, "c2")
        calc.mark_landmark("c2", ex.ENDPOINT_ONSET, 1_100)
        with self.assertRaises(ex.ExhaustionError):
            calc.mark_landmark("c2", "REARM", 1_200)

    def test_an_unregistered_landmark_is_refused_with_the_remedy_named(self) -> None:
        calc = ex.ExhaustionCalculator()
        self._open(calc, "c3")
        with self.assertRaisesRegex(ex.ExhaustionError, "register_discovered_landmark"):
            calc.mark_landmark("c3", "SOMETHING_NEW", 1_100)

    def test_registering_the_same_landmark_twice_is_idempotent(self) -> None:
        a = ex.register_discovered_landmark("REARM", after=ex.T0, before=ex.ENDPOINT_ONSET)
        b = ex.register_discovered_landmark("REARM", after=ex.T0, before=ex.ENDPOINT_ONSET)
        self.assertEqual(a, b)

    def test_moving_a_registered_landmark_is_refused(self) -> None:
        ex.register_discovered_landmark("REARM", after=ex.T0, before=ex.ENDPOINT_ONSET)
        with self.assertRaises(ex.ExhaustionError):
            ex.register_discovered_landmark(
                "REARM", after=ex.ENDPOINT_ONSET, before=ex.ENDPOINT_CONFIRMATION
            )


class DispositionVocabularyGrowsTest(unittest.TestCase):
    @staticmethod
    def runway(**overrides) -> RunwayPressure:
        base = dict(
            runway_id="r1", instrument_id=42, side="B", source_day="20211004",
            source_role="SCORED_FINDINGS_DAY", continuity_segment=0, family_id="F",
            session_phase="RTH", opened_recv_ns=1_000, closed_recv_ns=2_000,
            traded_quantity=10, withdrawn_quantity=0, same_side_replacement_quantity=0,
            opposite_side_retreat_quantity=0, depth_at_open=100, surviving_depth=90,
            price_at_open_raw=1000, price_at_close_raw=1000, order_ids_at_open=5,
            order_ids_at_close=4, order_ids_persisting=3,
        )
        base.update(overrides)
        return RunwayPressure(**base)

    def test_a_novel_mechanism_is_not_rounded_to_a_carried_label(self) -> None:
        plain = self.runway()
        self.assertEqual(plain.disposition, ABSORBED_WITHOUT_PRICE_MOVE)
        novel = self.runway(discovered_disposition="rotated_without_depletion")
        self.assertEqual(novel.disposition, "OW_DISPOSITION_rotated_without_depletion")
        self.assertTrue(novel.is_discovered_disposition)

    def test_discovered_dispositions_are_counted_separately(self) -> None:
        calc = AbsorptionCalculator()
        calc.score(self.runway())
        calc.score(self.runway(discovered_disposition="rotated_without_depletion"))
        summary = calc.summary()
        self.assertEqual(summary["disposition_counts"][ABSORBED_WITHOUT_PRICE_MOVE], 1)
        self.assertEqual(
            summary["discovered_disposition_counts"]["OW_DISPOSITION_rotated_without_depletion"], 1
        )

    def test_a_discovered_disposition_gets_its_own_stratum(self) -> None:
        calc = AbsorptionCalculator()
        calc.score(self.runway())
        calc.score(self.runway(discovered_disposition="rotated_without_depletion"))
        subfamilies = {r["stratum"]["subfamily_id"] for r in calc.price_response.rows()}
        self.assertEqual(len(subfamilies), 2)


class ClusterCountIsNotChosenInAdvanceTest(unittest.TestCase):
    def test_the_data_decides_how_many_clusters_there_are(self) -> None:
        schema = FeatureSchema(
            version="v1", feature_names=("x",), scaling={"x": (0.0, 1.0)},
            distance="EUCLIDEAN_ON_SCALED_FEATURES", radius=1.0, seed=0, mode=INCREMENTAL,
        )
        calc = DiscoveryCalculator(schema)
        for index in range(40):
            calc.assign(member_id=f"m{index}", features={"x": index * 10.0}, recv_ns=index)
        self.assertEqual(calc.cluster_count, 40)

    def test_nothing_caps_the_family_or_cluster_count(self) -> None:
        import inspect
        from research.kalshi.frankie_raw_mbo_benchmark import native_discovery
        source = inspect.getsource(native_discovery)
        for forbidden in ("n_clusters", "max_clusters", "MAX_CLUSTERS", "max_families"):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
