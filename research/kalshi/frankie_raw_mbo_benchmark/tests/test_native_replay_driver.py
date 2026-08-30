"""Tests for the traversal driver.

The driver had no tests: it imported cleanly and nothing ran it. These start at the riskiest
point - does a pass execute end to end at all - rather than at the edges.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from research.kalshi.frankie_raw_mbo_benchmark import native_candidate as nc
from research.kalshi.frankie_raw_mbo_benchmark import native_candidate_adapter as nca
from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import (
    ACCEPTED,
    NativeCalculationRun,
    RunIdentity,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_replay_driver import (
    ExchangeSessionRule,
    NativeReplayDriver,
    ReplayDriverError,
    SessionMark,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_session import (
    NS_PER_SECOND,
    POST_CLOSE,
    PRE_SETTLEMENT,
    SETTLEMENT,
)

SOURCE = "s3://bucket/nymex/ng_mbo_5y_v0/native/20211004/part-0.dbn.zst"
F_LAST = 128


def at(iso: str) -> int:
    return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp()) * NS_PER_SECOND


def record(*, seq: int, event_ns: int, order_id: int, action: str = "A", side: str = "B",
           last: bool = True) -> dict:
    return {
        "instrument_id": 42,
        "publisher_id": 1,
        "channel_id": 0,
        "order_id": order_id,
        "action": action,
        "side": side,
        "price": 3_500_000_000,
        "size": 5,
        "flags": F_LAST if last else 0,
        "sequence": seq,
        "ts_event": event_ns,
        "ts_recv": event_ns + 150_000,
        "ts_in_delta": 0,
        "source_dbn_object": SOURCE,
        "source_dbn_sha256": "0" * 64,
    }


class NeverInvoke:
    def should_invoke(self, **_kwargs) -> bool:
        return False


def make_driver(cadence=None, *, total_mbo_records: int = 3) -> NativeReplayDriver:
    identity = RunIdentity(
        run_id="driver-1",
        arm="A_CLEAN",
        mission_sha256="a" * 64,
        calculation_contract_sha256="b" * 64,
        knowledge_manifest_hash="c" * 64,
        source_manifest_hash="d" * 64,
        total_mbo_records=total_mbo_records,
        code_commit="deadbeef",
    )
    run = NativeCalculationRun(
        identity,
        replenishment_horizon_ns=1_000,
        response_horizons_ns=(100,),
        response_horizon_version="hv1",
        response_value_names=("price_response",),
    )
    return NativeReplayDriver(
        identity=identity,
        session_rule=ExchangeSessionRule(),
        cadence=cadence or NeverInvoke(),
        run=run,
    )


class ExchangeSessionRuleTest(unittest.TestCase):
    def test_it_keys_on_event_time_not_receive_time(self):
        """The two clocks disagree across a boundary, and D6 says the exchange fact wins.

        An earlier draft of SessionRule offered only recv_ns, which would have keyed session
        membership on the feed's serialization rather than on the market.
        """
        close = at("2021-10-04T21:00:00")
        rule = ExchangeSessionRule()
        before = rule.classify(
            event_ns=close - 1, recv_ns=close + NS_PER_SECOND, source_day="20211004", previous=None
        )
        self.assertNotEqual(before.session_phase, POST_CLOSE)

    def test_it_reports_the_phases_the_exchange_defines(self):
        rule = ExchangeSessionRule()
        for iso, want in (
            ("2021-10-04T13:00:00", PRE_SETTLEMENT),
            ("2021-10-04T18:29:00", SETTLEMENT),
            ("2021-10-04T21:30:00", POST_CLOSE),
        ):
            with self.subTest(iso=iso):
                mark = rule.classify(
                    event_ns=at(iso), recv_ns=at(iso), source_day="20211004", previous=None
                )
                self.assertEqual(mark.session_phase, want)

    def test_a_new_trade_date_starts_a_new_segment(self):
        rule = ExchangeSessionRule()
        monday = rule.classify(
            event_ns=at("2021-10-04T13:00:00"), recv_ns=0, source_day="20211004", previous=None
        )
        tuesday = rule.classify(
            event_ns=at("2021-10-05T13:00:00"), recv_ns=0, source_day="20211005", previous=monday
        )
        self.assertTrue(tuesday.starts_new_segment)
        self.assertEqual(tuesday.continuity_segment, monday.continuity_segment + 1)

    def test_the_same_trade_date_does_not(self):
        rule = ExchangeSessionRule()
        first = rule.classify(
            event_ns=at("2021-10-04T13:00:00"), recv_ns=0, source_day="20211004", previous=None
        )
        second = rule.classify(
            event_ns=at("2021-10-04T18:29:00"), recv_ns=0, source_day="20211004", previous=first
        )
        self.assertFalse(second.starts_new_segment)


class TraversalTest(unittest.TestCase):
    """Does a pass run end to end. It never had before."""

    def test_a_pass_over_three_groups_is_accepted(self):
        driver = make_driver()
        base = at("2021-10-04T13:00:00")
        driver.consume(
            record(seq=i, event_ns=base + i * NS_PER_SECOND, order_id=100 + i)
            for i in range(3)
        )
        result = driver.finalize()
        self.assertEqual(result["verdict"], ACCEPTED, result["failed_gates"])
        self.assertEqual(result["traversal"]["groups_seen"], 3)
        self.assertEqual(result["traversal"]["session_rule"], "ExchangeSessionRule")

    def test_the_traversal_satisfies_the_session_reconciliation_gate(self):
        """The gate that rejects a constant phase must pass on the real rule."""
        driver = make_driver()
        base = at("2021-10-04T13:00:00")
        driver.consume(
            record(seq=i, event_ns=base + i * NS_PER_SECOND, order_id=200 + i)
            for i in range(3)
        )
        sessions = driver.finalize()["layers"]["reconciliation_receipt"]["session_assignment"]
        self.assertEqual(sessions["assignments_observed"], 3)
        self.assertEqual(sessions["phase_mismatches"], 0)
        self.assertEqual(sessions["segment_mismatches"], 0)

    def test_a_span_crossing_the_settlement_window_records_both_phases(self):
        driver = make_driver(total_mbo_records=2)
        for i, iso in enumerate(("2021-10-04T18:27:00", "2021-10-04T18:29:00")):
            driver.consume([record(seq=i, event_ns=at(iso), order_id=300 + i)])
        self.assertEqual(driver.current_mark.session_phase, SETTLEMENT)
        self.assertEqual(driver.finalize()["verdict"], ACCEPTED)

    def test_receive_time_moving_backwards_is_refused(self):
        driver = make_driver()
        base = at("2021-10-04T13:00:00")
        driver.consume([record(seq=0, event_ns=base, order_id=400)])
        with self.assertRaises(ReplayDriverError):
            driver.consume([record(seq=1, event_ns=base - NS_PER_SECOND, order_id=401)])

    def test_a_record_without_a_source_object_is_refused(self):
        driver = make_driver()
        bad = record(seq=0, event_ns=at("2021-10-04T13:00:00"), order_id=500)
        del bad["source_dbn_object"]
        with self.assertRaises(ReplayDriverError):
            driver.consume([bad])


class LegacyRowRetentionTest(unittest.TestCase):
    """D60: the driver used to bind the adapter's legacy rows to `_` and throw them away.

    Those rows carry the projected ten-level MBP-10 depth at every trade and at group end, and
    `legacy_observable_crosswalk` is a CAUSAL_STREAM_REQUIRED registry group whose
    `legacy_book_imbalance` cannot be computed from anything else the traversal keeps. Greg:
    "i don't care about memory. restore every piece... let him figure out what he uses but he
    has to see everything." These tests exist so nobody has to audit for this drop again.
    """

    def _run(self, sink=None):
        driver = make_driver()
        driver.legacy_sink = sink
        base = at("2021-10-04T13:00:00")
        driver.consume(
            record(seq=i, event_ns=base + i * NS_PER_SECOND, order_id=300 + i, action="T")
            for i in range(3)
        )
        return driver, driver.finalize()

    def test_every_legacy_row_the_adapter_emits_is_retained_verbatim(self):
        driver, result = self._run()
        seen = result["traversal"]["legacy_rows_seen"]
        self.assertGreater(seen, 0, "the fixture stopped producing legacy rows")
        self.assertEqual(result["traversal"]["legacy_rows_retained"], seen,
                         "retained must equal seen; anything less is a silent drop")
        self.assertEqual(len(driver.counters.legacy_rows), seen)

    def test_a_retained_row_still_carries_its_depth_ladder(self):
        # Retaining a truncated row would satisfy a count and lose the reason to keep it.
        driver, _ = self._run()
        row = driver.counters.legacy_rows[0]
        for field in ("bid_px_00", "bid_sz_00", "bid_ct_00", "ask_px_09", "ask_sz_09", "ask_ct_09"):
            self.assertIn(field, row, f"the ten-level ladder lost {field}")
        self.assertEqual(row["census_view"], "LEGACY_CONTROL")

    def test_a_sink_streams_the_rows_without_replacing_retention(self):
        streamed = []
        driver, result = self._run(sink=streamed.append)
        self.assertEqual(len(streamed), result["traversal"]["legacy_rows_seen"])
        self.assertEqual(len(driver.counters.legacy_rows), len(streamed),
                         "a sink is a second home, never a substitute for keeping them")
        self.assertTrue(result["traversal"]["legacy_rows_streamed"])


class CadenceTest(unittest.TestCase):
    def test_cutoffs_carry_the_session_context_they_were_taken_at(self):
        class Always:
            def should_invoke(self, **_kwargs) -> bool:
                return True

        driver = make_driver(cadence=Always())
        driver.consume([record(seq=0, event_ns=at("2021-10-04T18:29:00"), order_id=600)])
        cutoff = driver.counters.invocation_cutoffs[0]
        self.assertEqual(cutoff["session_phase"], SETTLEMENT)
        self.assertEqual(cutoff["source_day"], "20211004")


if __name__ == "__main__":
    unittest.main()


class CanonicalFamilyIdentityTest(unittest.TestCase):
    """The driver must not hold a second opinion about family identity.

    `a_memory_member_first_recalculation_20260828` ran the full roster into 4,758 candidate
    families and keyed `family_id` on `candidate_family_id`. An earlier version of the
    driver used the bare action string, which is a different vocabulary over the same data -
    nothing would have failed, the strata would simply have been cut differently here than
    in the run this one has to reconcile against.
    """

    @staticmethod
    def _canonical(actions):
        from research.kalshi.frankie_raw_mbo_benchmark.a_memory_member_first_recalculation_20260828 import (
            describe_structure,
        )
        return describe_structure(actions)["candidate_family_id"]

    def test_the_driver_uses_the_canonical_candidate_family_id(self):
        actions = [
            {"action": "A", "side": "B", "price_raw": 3_500_000_000, "order_id": 11},
            {"action": "N", "side": "N", "price_raw": None, "order_id": 0},
        ]
        self.assertEqual(NativeReplayDriver._family_id(actions), self._canonical(actions))

    def test_the_family_id_is_not_the_bare_action_string(self):
        actions = [{"action": "A", "side": "B", "price_raw": 1, "order_id": 11}]
        self.assertNotEqual(NativeReplayDriver._family_id(actions), "A")

    def test_structurally_different_groups_with_the_same_actions_differ(self):
        """The action string alone cannot tell these apart; the canonical descriptor can."""
        one_price = [
            {"action": "A", "side": "B", "price_raw": 100, "order_id": 1},
            {"action": "A", "side": "B", "price_raw": 100, "order_id": 2},
        ]
        two_prices = [
            {"action": "A", "side": "B", "price_raw": 100, "order_id": 1},
            {"action": "A", "side": "B", "price_raw": 200, "order_id": 2},
        ]
        self.assertNotEqual(
            NativeReplayDriver._family_id(one_price),
            NativeReplayDriver._family_id(two_prices),
        )


class Roll20IsFedByTheTraversalTest(unittest.TestCase):
    """BUILT, WIRED and FED are three different states. These prove the third.

    `legacy_per_second_roll20` is a CAUSAL_STREAM_REQUIRED layer, so the binner is not an
    option the driver may be constructed without - it is fed on every pass, from the legacy
    rows the traversal already retains. Asserting the attribute exists would only prove the
    first state; these assert volumes and counts that can only appear if rows actually
    reached it.
    """

    def _priced(self, *, seq, event_ns, order_id, action, side, price):
        row = record(seq=seq, event_ns=event_ns, order_id=order_id, action=action, side=side)
        row["price"] = price
        return row

    def test_the_binner_sees_every_legacy_row_the_traversal_retained(self):
        driver = make_driver()
        base = at("2021-10-04T13:00:00")
        driver.consume(
            record(seq=i, event_ns=base + i * NS_PER_SECOND, order_id=300 + i, action="T")
            for i in range(3)
        )
        result = driver.finalize()
        self.assertGreater(result["traversal"]["legacy_rows_seen"], 0)
        self.assertEqual(driver.roll20.rows_seen, result["traversal"]["legacy_rows_seen"],
                         "a row retained but not binned is the drop D60 exists to stop")

    def test_a_trade_above_the_mid_reaches_the_binner_as_buy_volume(self):
        driver = make_driver()
        base = at("2021-10-04T13:00:00")
        driver.consume([
            self._priced(seq=0, event_ns=base, order_id=400, action="A", side="B",
                         price=3_499_000_000),
            self._priced(seq=1, event_ns=base + NS_PER_SECOND, order_id=401, action="A",
                         side="A", price=3_501_000_000),
            self._priced(seq=2, event_ns=base + 2 * NS_PER_SECOND, order_id=402, action="T",
                         side="B", price=3_500_500_000),
        ])
        driver.finalize()
        buys, sells, _ = driver.roll20.series()
        self.assertGreater(sum(buys), 0.0, "the trade never reached the binner")
        self.assertEqual(sum(sells), 0.0)

    def test_the_traversal_reports_the_roll20_summary_and_its_crosswalk(self):
        driver = make_driver()
        base = at("2021-10-04T13:00:00")
        driver.consume(
            record(seq=i, event_ns=base + i * NS_PER_SECOND, order_id=500 + i, action="T")
            for i in range(3)
        )
        result = driver.finalize()
        summary = result["traversal"]["legacy_per_second_roll20"]
        self.assertEqual(summary["clock"], "ts_recv")
        self.assertEqual(len(summary["crosswalk_state_hash"]), 64)
        self.assertEqual(summary["rows_seen"], result["traversal"]["legacy_rows_seen"])


class FedSectionsTest(unittest.TestCase):
    """T1: 4.8, 4.9, 4.13 and 4.14 report on rows that actually arrived.

    All four were built, tested and closed at their boundaries, and `native_group_adapters`
    was imported by its own test and nothing else - so the traversal reported these sections
    off an EMPTY ingest while every gate passed. A gate cannot catch that: zero strata over
    no members is well formed, and it is exactly what a real absence looks like.

    So these tests assert counts that cannot appear unless rows were folded in, and
    `test_an_unconsumed_pass_reports_zero_everywhere` proves the assertions discriminate
    rather than passing on any input at all.
    """

    GROUPS = (
        (("T", "A", 701, False), ("F", "A", 702, False),
         ("C", "A", 702, False), ("A", "B", 703, True)),
        (("A", "B", 704, False), ("M", "B", 704, False),
         ("C", "B", 705, False), ("T", "A", 706, True)),
    )

    def _run(self):
        driver = make_driver(total_mbo_records=8)
        base = at("2021-10-04T13:00:00")
        seq = 0
        for group_index, group in enumerate(self.GROUPS):
            batch = []
            for offset, (action, side, order_id, last) in enumerate(group):
                batch.append(record(
                    seq=seq,
                    event_ns=base + (group_index * 10 + offset) * NS_PER_SECOND,
                    order_id=order_id, action=action, side=side, last=last,
                ))
                seq += 1
            driver.consume(batch)
        return driver, driver.finalize()

    def test_the_traversal_reports_what_each_section_received(self):
        """The ingest count is emitted, not inferred from the measures above it."""
        _, result = self._run()
        self.assertEqual(result["verdict"], ACCEPTED, result["failed_gates"])
        self.assertEqual(result["traversal"]["sections_fed"], {
            "4.8_absorption_runways": 2,
            "4.9_ladder_transitions": 4,
            "4.13_lineage_nodes_added": 6,
            "4.13_lineage_nodes_observed": 6,
            "4.14_recurrence_sequences": 2,
            "candidate_unit_events": 0,
            "4.10_4.11_4.12_episode_rows": 0,
            "4.16_response_tracks": 0,
            "4.7_replenishment_observations": 2,
            "4.6_queue_rows_applied": 8,
            "4.6_queue_terminals": 0,
            "candidates_without_stratum": 0,
        })

    def test_the_queue_lane_applies_every_row_and_emits_no_terminal_it_did_not_see(self):
        """4.6 reads what the BOOK did, so its ingest is rows applied, not groups closed.

        Terminals are zero here on purpose and the number is load-bearing: this fixture
        cancels order ids that were never added, so no lifecycle was ever born and none can
        resolve. A lane that emitted a terminal for an unborn order would be inventing the
        member row the exact ledger is built from. The add-then-cancel case is tested
        separately, where a terminal MUST appear.
        """
        _, result = self._run()
        fed = result["traversal"]["sections_fed"]
        self.assertEqual(fed["4.6_queue_rows_applied"], 8)
        self.assertEqual(fed["4.6_queue_terminals"], 0)
        report = result["traversal"]["queue_observation"]
        self.assertEqual(report["queue_scope"], "BIRTH_GROUP_STRATUM")
        self.assertEqual(report["open_tracked_orders"], 0)
        self.assertEqual(report["instruments"], [42])

    def test_a_lifecycle_that_resolves_inside_a_group_reaches_the_exact_ledger(self):
        """The one assertion that fails if `feed_group`'s return is dropped.

        A dropped return costs nothing visible: the calculator still censors at the boundary,
        the stratified averages still print, and the member row beneath them is simply gone.
        So this asserts the exact row - with the basis that decided FILLED against CANCELLED -
        is in the lifecycle ledger, not that a count went up.
        """
        driver = make_driver(total_mbo_records=4)
        base = at("2021-10-04T13:00:00")
        groups = (
            (("A", 811, False), ("T", 812, True)),
            (("A", 813, False), ("C", 811, True)),
        )
        seq = 0
        for group_index, group in enumerate(groups):
            batch = []
            for offset, (action, order_id, last) in enumerate(group):
                batch.append(record(
                    seq=seq,
                    event_ns=base + (group_index * 10 + offset) * NS_PER_SECOND,
                    order_id=order_id, action=action, side="B", last=last,
                ))
                seq += 1
            driver.consume(batch)
        result = driver.finalize()

        self.assertEqual(result["traversal"]["sections_fed"]["4.6_queue_terminals"], 1)
        rows = [row for row in result["layers"]["exact_lifecycle_and_runway_ledger"]["rows"]
                if row.get("emitting_section") == "queue"
                and row.get("emitted_on") == "GROUP_CLOSE"]
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["terminal_basis"], "NO_OWN_FILL_PENDING_AT_REMOVAL")
        self.assertEqual(row["queue_scope"], "BIRTH_GROUP_STRATUM")
        # Born in group 1, ended in group 2. Equal indexes would mean the adapter had been
        # rebuilt between groups, which reports every order as front-of-queue.
        self.assertLess(row["birth_group_index"], row["terminal_group_index"])

    def test_every_fed_section_produces_averaged_companions(self):
        """Before the wiring each of these was zero, and the run was still ACCEPTED."""
        _, result = self._run()
        sections = [row.get("section") for row in result["layers"]["averaged_companions"]["rows"]]
        for section in ("4.8", "4.9", "4.13", "4.14"):
            with self.subTest(section=section):
                self.assertGreater(sections.count(section), 0)

    def test_absorption_classifies_a_disposition_it_could_not_have_invented(self):
        """4.8's disposition needs traded and withdrawn depletion kept apart, per group."""
        _, result = self._run()
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"]["section_summaries"]["4.8"]
        self.assertEqual(summary["runways_scored"], 2)
        self.assertEqual(sum(summary["disposition_counts"].values()), 2)

    def test_lineage_depth_advances_past_the_root(self):
        """Depth above zero is only reachable if a parent was in the graph when a child came.

        This is the assertion that would have caught the group-local unit being wrong: with
        a within-group graph, or with the graph never fed, `observed_max_depth` stays 0 and
        the depth distribution has one entry.
        """
        _, result = self._run()
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"]["section_summaries"]["4.13"]
        self.assertEqual(summary["observed_max_depth"], 1)
        self.assertEqual(summary["role_counts"], {"ROOT": 2, "DESCENDANT": 4})
        depths = {row["depth"]: row["count"]
                  for row in result["layers"]["open_world_indexes"]["lineage_depth_distribution"]}
        self.assertEqual(depths, {0: 2, 1: 4})

    def test_lineage_separates_termination_from_censoring(self):
        """4.13 requires the two be distinct, and OPEN would have erased both.

        A node is observed once, when its status is finally known - so a node whose stage
        ended reads TERMINATED and one still open at stream end reads CENSORED_STREAM_END.
        Observing at creation would have reported every node OPEN with no stage duration.
        """
        _, result = self._run()
        statuses = result["layers"]["exact_lifecycle_and_runway_ledger"]["section_summaries"]["4.13"]["status_counts"]
        self.assertEqual(statuses["TERMINATED"], 2)
        self.assertEqual(statuses["CENSORED_STREAM_END"], 4)
        self.assertEqual(statuses["OPEN"], 0, "a node observed as OPEN was never given a terminal status")

    def test_recurrence_records_transition_edges_with_denominators(self):
        """An edge needs two occurrences in one sequence, so it cannot appear on an empty ingest."""
        _, result = self._run()
        edges = result["layers"]["open_world_indexes"]["transition_edges"]
        self.assertGreater(len(edges), 0)
        for edge in edges:
            self.assertEqual(edge["statistic_kind"], "CONDITIONAL_PROBABILITY")
            self.assertFalse(edge["is_arithmetic_mean"])
            self.assertGreater(edge["outgoing_denominator"], 0)

    def test_the_ladder_transition_carries_its_group_local_scope(self):
        """D53's declared cost travels ON the value, never in prose alone."""
        driver, _ = self._run()
        ladder_rows = [r for r in driver.counters.lifecycle_rows if r["emitting_section"] == "ladder"]
        self.assertEqual(len(ladder_rows), 4)
        for row in ladder_rows:
            self.assertEqual(row["ladder_scope"], "GROUP_LOCAL_DELTA")

    def test_every_fed_row_is_retained_beneath_its_summary(self):
        """D60 and section 6: an average with no member under it is not evidence."""
        driver, result = self._run()
        kept = {row["emitting_section"] for row in driver.counters.lifecycle_rows}
        for section in ("recurrence", "ladder", "absorption", "lineage"):
            with self.subTest(section=section):
                self.assertIn(section, kept)
        self.assertEqual(
            result["traversal"]["lifecycle_rows_retained"], len(driver.counters.lifecycle_rows)
        )

    def test_an_unconsumed_pass_reports_zero_everywhere(self):
        """Proves the assertions above discriminate. Without this they could pass on anything."""
        # A run identity needs a positive record count, so the pass is set up exactly as the
        # fed one and simply consumes nothing. The verdict is not asserted - an unfed pass
        # SHOULD fail its coverage gate - only that the four sections report no ingest.
        driver = make_driver(total_mbo_records=8)
        result = driver.finalize()
        self.assertEqual(result["traversal"]["sections_fed"], {
            "4.8_absorption_runways": 0,
            "4.9_ladder_transitions": 0,
            "4.13_lineage_nodes_added": 0,
            "4.13_lineage_nodes_observed": 0,
            "4.14_recurrence_sequences": 0,
            "candidate_unit_events": 0,
            "4.10_4.11_4.12_episode_rows": 0,
            "4.16_response_tracks": 0,
            "4.7_replenishment_observations": 0,
            "4.6_queue_rows_applied": 0,
            "4.6_queue_terminals": 0,
            "candidates_without_stratum": 0,
        })
        sections = [row.get("section") for row in result["layers"]["averaged_companions"]["rows"]]
        for section in ("4.8", "4.9", "4.13", "4.14"):
            with self.subTest(section=section):
                self.assertEqual(sections.count(section), 0)

    def test_the_lineage_signature_and_segment_scope_are_declared_in_the_output(self):
        """A stratum axis left implicit makes two definitions look like one population."""
        _, result = self._run()
        self.assertEqual(result["traversal"]["lineage_signature"], "ORDER_ID_LINEAGE_V1")
        self.assertEqual(result["traversal"]["lineage_segment_scope"], "ONE_CONTINUITY_SEGMENT")


class CandidateUnitFedTest(unittest.TestCase):
    """D66's second unit, fed by the traversal from real legacy rows - not just callable.

    `native_candidate` is exercised directly by its own tests. This asserts the thing those
    cannot: that the DRIVER reaches it, from the roll20 substrate it recreates out of the
    adapter's legacy control rows, on completed seconds only. Built-and-tested and fed are
    different states, and the gap between them is what left eleven sections reporting on an
    empty ingest.
    """

    BOOK = ((1, "B", 3_499_000_000), (2, "A", 3_501_000_000))
    MID = 3_500_000_000
    SPIKE_SECOND = 200
    SPAN = 400

    def _stream(self):
        base = at("2021-10-04T13:00:00")
        seq = 0
        for order_id, side, price in self.BOOK:
            row = record(seq=seq, event_ns=base, order_id=order_id, action="A",
                         side=side, last=False)
            row["price"] = price
            yield row
            seq += 1
        for offset in range(1, self.SPAN):
            # Alternating one-lot buys and sells keep trailing imbalance near zero, so the
            # trailing bar sits low and the injected burst is the only real peak.
            buy = offset % 2 == 0
            row = record(seq=seq, event_ns=base + offset * NS_PER_SECOND, order_id=1000 + offset,
                         action="T", side="A" if buy else "B", last=True)
            row["price"] = self.MID + (500_000 if buy else -500_000)
            row["size"] = 100 if offset == self.SPIKE_SECOND else 1
            yield row
            seq += 1

    def _run(self):
        driver = make_driver(total_mbo_records=self.SPAN + 1)
        driver.candidate_warmup_seconds = 60
        # The production floor is 600 finite observations behind the trailing bar; this
        # fixture is 400 seconds, so the floor is scaled to it rather than relaxed in the
        # detector. `AdversarialReviewRegressionTest.test_f6` pins the production value.
        driver.candidate_min_observations = 30
        driver.detector = driver._new_detector(0)
        driver.consume(self._stream())
        return driver, driver.finalize()

    def test_the_traversal_detects_candidates_from_its_own_roll20_substrate(self):
        driver, result = self._run()
        self.assertGreater(
            result["traversal"]["sections_fed"]["candidate_unit_events"], 0,
            "the detector is wired but nothing reached it",
        )
        self.assertEqual(
            result["traversal"]["sections_fed"]["candidate_unit_events"],
            driver.counters.candidates_detected,
        )

    def test_the_injected_burst_is_among_the_detected_events(self):
        """A candidate the fixture put there, found through the whole chain end to end."""
        driver, _ = self._run()
        seconds = [
            row["event_second"]
            for row in driver.counters.lifecycle_rows
            if row["emitting_section"] == "candidate"
        ]
        self.assertTrue(seconds, "no candidate rows were retained")
        base_second = at("2021-10-04T13:00:00") // NS_PER_SECOND
        spike = base_second + self.SPIKE_SECOND
        self.assertTrue(
            any(abs(s - spike) <= nc.REFRACTORY for s in seconds),
            f"the burst at {spike} produced no candidate within a refractory window of it",
        )

    def test_every_detected_candidate_is_retained_with_both_clocks(self):
        driver, _ = self._run()
        rows = [r for r in driver.counters.lifecycle_rows if r["emitting_section"] == "candidate"]
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(second=row["event_second"]):
                self.assertGreater(row["available_second"], row["event_second"])
                self.assertIn(row["polarity"], (-1, 0, 1))
                self.assertEqual(row["threshold_rule"], nc.TRAILING_QUANTILE)

    def test_a_segment_that_found_nothing_still_reports_a_summary(self):
        """Absence is a result about that segment, not an omission from the output."""
        driver = make_driver()
        driver.consume(
            record(seq=i, event_ns=at("2021-10-04T13:00:00") + i * NS_PER_SECOND,
                   order_id=700 + i)
            for i in range(3)
        )
        result = driver.finalize()
        summaries = result["traversal"]["candidate_detection"]
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["candidates_emitted"], 0)
        self.assertEqual(summaries[0]["unit"], "DIPOLE_FLOW_EVENT")

    def test_no_candidate_is_judged_on_a_second_still_receiving_trades(self):
        """A second is judged only once the stream has moved past it.

        Judging the current second would read a partial bin as a finished one - smaller than
        the truth, present, typed, and wrong. The invariant: every emitted candidate's event
        second is strictly behind the last second the traversal had seen.
        """
        driver, _ = self._run()
        rows = [r for r in driver.counters.lifecycle_rows if r["emitting_section"] == "candidate"]
        last_seen = driver._last_complete_second
        self.assertIsNotNone(last_seen)
        for row in rows:
            with self.subTest(second=row["event_second"]):
                self.assertLessEqual(row["event_second"], last_seen)


class CandidateEpisodeFedTest(CandidateUnitFedTest):
    """4.10, 4.11 and 4.12 on the candidate unit, fed by the traversal.

    Two bursts, not one: 4.12's orientation is polarity against the LATEST PREDECESSOR, so a
    single candidate has nothing to be SAME or FLIP against and its dipole path is correctly
    WITHHELD rather than given a fabricated orientation. A one-candidate fixture therefore
    proves 4.10 and 4.11 and says nothing about 4.12, which is why this subclass exists.
    """

    SECOND_SPIKE = 320

    def _stream(self):
        for row in super()._stream():
            offset = (int(row["ts_event"]) - at("2021-10-04T13:00:00")) // NS_PER_SECOND
            if offset == self.SECOND_SPIKE and row["action"] == "T":
                row["size"] = 100
            yield row

    def test_the_runway_carries_a_content_derived_open_world_state(self):
        """A flow spike is not P/O/S/X, and forcing it into one would read as a confirmation."""
        _, result = self._run()
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"]["section_summaries"]["4.10"]
        self.assertGreater(summary["runways_opened"], 0)
        self.assertGreater(summary["open_world_state_count"], 0)

    def test_recognition_is_honestly_h_plus_n_and_never_backdated(self):
        """PRIOR is unreachable for a candidate whose birth IS its own detection."""
        _, result = self._run()
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"]["section_summaries"]["4.11"]
        self.assertEqual(summary["outcome_counts"]["PRIOR"], 0)
        self.assertGreater(summary["outcome_counts"]["H+N"], 0)
        episodes = result["traversal"]["candidate_episodes"][0]
        self.assertFalse(episodes["prior_reachable"])

    def test_the_second_candidate_has_a_predecessor_so_4_12_gets_a_path(self):
        _, result = self._run()
        episodes = result["traversal"]["candidate_episodes"][0]
        self.assertGreaterEqual(
            episodes["orientation_counts"]["SAME"] + episodes["orientation_counts"]["FLIP"], 1,
            "no candidate found a predecessor; 4.12 cannot be exercised by this fixture",
        )
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"]["section_summaries"]["4.12"]
        self.assertGreater(summary["paths_seen"], 0)
        self.assertGreater(summary["stages_seen"], 0)

    def test_a_first_candidate_never_receives_a_fabricated_orientation(self):
        _, result = self._run()
        episodes = result["traversal"]["candidate_episodes"][0]
        self.assertEqual(episodes["orientation_counts"]["NO_PREDECESSOR"], 1)
        self.assertEqual(episodes["dipole_paths_withheld_no_predecessor"], 1)


class FullDepthRetentionTest(unittest.TestCase):
    """D60/D61: the frame's full-depth book must reach the member row and 4.12's stages.

    Greg: "mbo is deeper than 10 levels isn't it?" It is - market-by-order is every resting
    order at every level, and MBP-10 is a ten-level aggregate of it. Two defects followed
    from that question:

    1. `_on_group` copied a HARDCODED list of eleven frame keys into the member row, written
       against the base adapter's frame. `FullCaptureAdapter` adds five more, including
       `book_full` - which is exactly what D61 exists to restore - and every one was dropped
       one line after being restored. Second time this shape has occurred.
    2. 4.12's stage depths were read off the ten-level legacy projection while the full book
       sat in the same frame, and prices were cast with `int(3.499)` = 3.
    """

    LEVELS = 14

    def _run(self):
        driver = make_driver(total_mbo_records=self.LEVELS * 2)
        base = at("2021-10-04T13:00:00")
        rows, seq = [], 0
        for level in range(self.LEVELS):
            for side, price in (
                ("B", 3_499_000_000 - level * 1_000_000),
                ("A", 3_501_000_000 + level * 1_000_000),
            ):
                row = record(seq=seq, event_ns=base, order_id=100 + seq, action="A",
                             side=side, last=False)
                row["price"] = price
                row["size"] = 3
                rows.append(row)
                seq += 1
        rows[-1]["flags"] = F_LAST
        driver.consume(rows)
        return driver, driver.finalize()

    def test_every_frame_key_reaches_the_member_row(self):
        """No hardcoded list. A key a future adapter adds arrives instead of vanishing."""
        driver, result = self._run()
        carried = set(result["traversal"]["frame_keys_carried"])
        for restored in ("book_full", "activity_full", "integrity_delta", "capture_observations"):
            with self.subTest(key=restored):
                self.assertIn(restored, carried, f"{restored} was restored by D61 and dropped")

    def test_the_full_book_is_deeper_than_the_ten_level_projection(self):
        """The measurement behind the fix, kept as the instance."""
        driver, _ = self._run()
        book = driver.counters.member_rows[-1]["book_full"]
        self.assertEqual(book["bid_price_level_count_full"], self.LEVELS)
        self.assertGreater(book["bid_depth_full"], book["bid_depth_n"])
        self.assertEqual(book["bid_depth_n"], 30)      # ten levels x 3
        self.assertEqual(book["bid_depth_full"], 42)   # fourteen levels x 3

    def test_the_book_state_the_dipole_sees_is_the_full_book(self):
        driver, _ = self._run()
        state = driver._latest_book
        self.assertEqual(state.depth_scope, "FULL_BOOK")
        self.assertEqual(state.bid_level_count, self.LEVELS)
        self.assertEqual(state.bid_depth, 42)

    def test_a_price_is_not_truncated_to_whole_dollars(self):
        """`int(3.499)` was 3 - three orders of magnitude wrong, silently, on every stage."""
        driver, _ = self._run()
        self.assertGreater(driver._latest_book.price_raw, 1_000_000_000)

    def test_the_ten_level_fallback_declares_itself(self):
        """A caller with only the legacy row gets a value that says what it is."""
        driver, _ = self._run()
        legacy = [r for r in driver.counters.legacy_rows if r.get("bid_px_00")]
        if legacy:
            projected = nca.BookState.from_legacy_row(legacy[-1])
            self.assertEqual(projected.depth_scope, "TOP_TEN_PROJECTION")


class ResponseTableFedTest(CandidateEpisodeFedTest):
    """4.16 on the same candidate unit, fed by the traversal."""

    def test_a_track_opens_for_every_candidate(self):
        _, result = self._run()
        fed = result["traversal"]["sections_fed"]
        self.assertEqual(fed["4.16_response_tracks"], fed["candidate_unit_events"])
        self.assertGreater(fed["4.16_response_tracks"], 0)

    def test_every_horizon_carries_its_own_at_risk_denominator(self):
        """4.16's requirement, and the reason a pooled denominator would be wrong."""
        _, result = self._run()
        rows = result["layers"]["exact_lifecycle_and_runway_ledger"]["response_at_risk_table"]
        self.assertTrue(rows)
        for row in rows:
            with self.subTest(horizon=row["horizon_ns"]):
                self.assertTrue(row["denominator_is_horizon_specific"])
                self.assertEqual(
                    row["entered_at_risk"],
                    row["observed"] + row["censored_before_horizon"] + row["still_pending"],
                    "a track left the at-risk set without being observed or censored",
                )

    def test_the_stratum_declares_no_clustering_rather_than_leaving_it_blank(self):
        """D5 keeps discovery out of this run; blank would read as 'not recorded'."""
        _, result = self._run()
        rows = result["layers"]["exact_lifecycle_and_runway_ledger"]["response_at_risk_table"]
        for row in rows:
            self.assertEqual(row["stratum"]["cluster_version"], "NO_CLUSTERING_D5")

    def test_the_starting_liquidity_regime_is_threshold_free(self):
        """It is a stratum axis, so a fitted bar here would silently decide comparability."""
        _, result = self._run()
        rows = result["layers"]["exact_lifecycle_and_runway_ledger"]["response_at_risk_table"]
        allowed = {
            "EMPTY_BOOK", "ONE_SIDED_BID", "ONE_SIDED_ASK",
            "DEPTH_SKEW_BID", "DEPTH_SKEW_ASK", "DEPTH_EVEN",
        }
        for row in rows:
            self.assertIn(row["stratum"]["starting_liquidity_regime"], allowed)

    def test_a_response_is_measured_from_the_first_lawful_instant(self):
        """Not from the spike. A response measured from a moment nobody could have acted on
        is not a response anyone could have captured."""
        driver, _ = self._run()
        candidates = [
            r for r in driver.counters.lifecycle_rows if r["emitting_section"] == "candidate"
        ]
        self.assertTrue(candidates)
        for row in candidates:
            self.assertGreater(row["available_second"], row["event_second"])


class ReplenishmentObservationFedTest(unittest.TestCase):
    """4.7's observation half, fed by the traversal.

    The maturation half was already wired - `replenishment.advance` ran on every group - so
    the section looked live while nothing had ever told the calculator that a removal or a
    refill happened. It was maturing horizons for episodes that were never opened. That is
    the sharpest form of built-and-unfed: not silent, but plausibly busy.
    """

    def _run(self):
        driver = make_driver(total_mbo_records=8)
        base = at("2021-10-04T13:00:00")
        rows, seq = [], 0

        def add(action, side, price, order_id, offset, last, size=5):
            nonlocal seq
            row = record(seq=seq, event_ns=base + offset * NS_PER_SECOND, order_id=order_id,
                         action=action, side=side, last=last)
            row["price"] = price
            row["size"] = size
            rows.append(row)
            seq += 1

        # Rest a bid, cancel it (a REMOVAL opens an episode), then refill the same price.
        add("A", "B", 3_499_000_000, 10, 0, False)
        add("A", "A", 3_501_000_000, 11, 0, True)
        add("C", "B", 3_499_000_000, 10, 1, True)
        add("A", "B", 3_499_000_000, 12, 2, True)
        driver.consume(rows)
        return driver, driver.finalize()

    def test_the_calculator_is_told_that_a_removal_happened(self):
        _, result = self._run()
        self.assertGreater(
            result["traversal"]["sections_fed"]["4.7_replenishment_observations"], 0
        )
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"]["section_summaries"]["4.7"]
        self.assertGreater(
            summary["episodes_opened"], 0,
            "horizons were maturing for episodes nobody ever opened",
        )

    def test_every_observation_is_retained_beneath_its_summary(self):
        driver, _ = self._run()
        kept = [
            row for row in driver.counters.lifecycle_rows
            if row["emitting_section"] == "replenishment"
            and row["emitted_on"] == "GROUP_CLOSE"
        ]
        self.assertTrue(kept, "the observation rows were dropped on the way back")

    def test_the_observer_reports_its_own_tick_neighbourhood(self):
        """The one declared choice in 4.7: what separates SAME_PRICE from NEIGHBORING_PRICE."""
        _, result = self._run()
        summary = result["traversal"]["replenishment_observation"]
        self.assertIn("groups_observed", summary)
        self.assertGreater(summary["groups_observed"], 0)


class CandidateSeamRegressionTest(unittest.TestCase):
    """The two seam defects an adversarial re-review found, both in the driver wiring.

    The detector-side fixes were all correct; these were in how the driver fed it, which is
    exactly the class of defect a module-level review cannot see.
    """

    def test_the_candidate_lane_uses_the_run_s_real_continuity_segments(self):
        """It used a counter of its own, so the lane landed in strata nothing else shared.

        `segment_of` returns an absolute trade-date ordinal. The driver seeded the detector
        with 0 and advanced it as `segment + 1`, so on a Friday/Monday stream the true
        segments are 18908 and 18911 while candidates were stamped 0 and 18909 - neither of
        which exists. 4.10, 4.11, 4.12 and 4.16 all stratify on it, so any join by segment
        returned empty. Wrong on the FIRST segment of every run, not only across a weekend.
        """
        driver = make_driver(total_mbo_records=6)
        for day in ("2021-10-08", "2021-10-11"):
            base = at(f"{day}T13:00:00")
            driver.consume(
                record(seq=i, event_ns=base + i * NS_PER_SECOND, order_id=500 + i)
                for i in range(3)
            )
        result = driver.finalize()
        member = {row["continuity_segment"] for row in driver.counters.member_rows}
        detector = {s["continuity_segment"] for s in result["traversal"]["candidate_detection"]}
        self.assertEqual(member, {18908, 18911}, "the fixture stopped crossing a weekend")
        self.assertTrue(
            detector.issubset(member),
            f"candidate lane is in segments {detector - member} that no member row shares",
        )

    def test_a_pass_that_consumed_nothing_reports_no_candidate_lane(self):
        """The detector is built from the first real mark, so an empty pass has none.

        Reporting a summary for a lane that never opened would be an empty stratum dressed
        as an observation.
        """
        driver = make_driver(total_mbo_records=8)
        result = driver.finalize()
        self.assertEqual(result["traversal"]["candidate_detection"], [])
        self.assertEqual(result["traversal"]["sections_fed"]["candidate_unit_events"], 0)

    def test_a_clock_that_moves_backwards_fails_at_the_seam(self):
        """Under EVENT_CLOCK, real MBO reorders event times against receive order.

        Receive order stays monotone, so the existing guard passes; the second derived from
        EVENT time goes backwards and the detector's contiguity check fires - hours into a
        run, from inside a module three files from the cause. It now fails here, naming the
        clock, which is where the choice was made.
        """
        from research.kalshi.frankie_raw_mbo_benchmark import native_roll20

        identity = RunIdentity(
            run_id="event-clock", arm="A_CLEAN", mission_sha256="a" * 64,
            calculation_contract_sha256="b" * 64, knowledge_manifest_hash="c" * 64,
            source_manifest_hash="d" * 64, total_mbo_records=4, code_commit="deadbeef",
        )
        run = NativeCalculationRun(
            identity, replenishment_horizon_ns=1_000, response_horizons_ns=(100,),
            response_horizon_version="hv1", response_value_names=("price_response",),
        )
        driver = NativeReplayDriver(
            identity=identity, session_rule=ExchangeSessionRule(), cadence=NeverInvoke(),
            run=run, roll20_clock=native_roll20.EVENT_CLOCK,
        )
        base = at("2021-10-04T13:00:00")
        first = record(seq=0, event_ns=base + 20 * NS_PER_SECOND, order_id=1)
        driver.consume([first])
        # Receive time still advances; EVENT time steps back three seconds.
        second = record(seq=1, event_ns=base + 17 * NS_PER_SECOND, order_id=2)
        second["ts_recv"] = first["ts_recv"] + NS_PER_SECOND
        with self.assertRaises(ReplayDriverError) as caught:
            driver.consume([second])
        self.assertIn("ts_event", str(caught.exception))
