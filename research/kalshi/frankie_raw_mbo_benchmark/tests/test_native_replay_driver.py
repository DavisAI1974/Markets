"""Tests for the traversal driver.

The driver had no tests: it imported cleanly and nothing ran it. These start at the riskiest
point - does a pass execute end to end at all - rather than at the edges.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

from research.kalshi.frankie_raw_mbo_benchmark import native_candidate as nc
from research.kalshi.frankie_raw_mbo_benchmark import native_candidate_adapter as nca
from research.kalshi.frankie_raw_mbo_benchmark import native_roll20
from research.kalshi.frankie_raw_mbo_benchmark.native_calculation_runner import (
    ACCEPTED,
    NativeCalculationRun,
    RunIdentity,
)
from research.kalshi.frankie_raw_mbo_benchmark.native_response import (
    FLOW_RESPONSE,
    FULL_BOOK_RESPONSE,
    PRICE_RESPONSE,
    QUEUE_RESPONSE,
    horizons_for_version,
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


def make_driver(
    cadence=None,
    *,
    total_mbo_records: int = 3,
    response_horizons_ns: tuple[int, ...] = (100,),
    response_horizon_version: str = "hv1",
    response_value_names: tuple[str, ...] = ("price_response",),
    emit_change_points: bool = False,
) -> NativeReplayDriver:
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
        response_horizons_ns=response_horizons_ns,
        response_horizon_version=response_horizon_version,
        response_value_names=response_value_names,
    )
    return NativeReplayDriver(
        identity=identity,
        session_rule=ExchangeSessionRule(),
        cadence=cadence or NeverInvoke(),
        run=run,
        emit_change_points=emit_change_points,
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


class FlowSubstrateIsFedByTheTraversalTest(unittest.TestCase):
    """Section 4.0 is FED, not merely built and mapped.

    Frankie's item (a): the per-second substrate the detector and 4.12 run on was a counters
    block with no section beneath it. S119's own recorded lesson is that a calculator's unit
    tests pass while the driver never calls it, so these run the REAL traversal and assert
    counts that cannot appear unless completed seconds actually reached the section, then
    reconcile the section against the traversal's own binner, which is the check that says
    the census is over the substrate the detector consumed and not a second derivation.
    """

    def _priced(self, *, seq, event_ns, order_id, action, side, price):
        row = record(seq=seq, event_ns=event_ns, order_id=order_id, action=action, side=side)
        row["price"] = price
        return row

    def _run(self):
        # Four groups at seconds 0, 1, 2 and 5: a bid, an ask, a trade above the mid, and a
        # trailing add whose only job is to move the stream past second 4. Judged: seconds
        # 0-4, five of them, with the trade making second 2 a BUY. Second 5 is never judged.
        driver = make_driver(total_mbo_records=4)
        base = at("2021-10-04T13:00:00")
        driver.consume([
            self._priced(seq=0, event_ns=base, order_id=400, action="A", side="B",
                         price=3_499_000_000),
            self._priced(seq=1, event_ns=base + NS_PER_SECOND, order_id=401, action="A",
                         side="A", price=3_501_000_000),
            self._priced(seq=2, event_ns=base + 2 * NS_PER_SECOND, order_id=402, action="T",
                         side="B", price=3_500_500_000),
            self._priced(seq=3, event_ns=base + 5 * NS_PER_SECOND, order_id=403, action="A",
                         side="B", price=3_499_000_000),
        ])
        result = driver.finalize()
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"][
            "section_summaries"]["4.0"]
        return driver, result, summary

    def _flow_rows(self, driver, occasion):
        return [r for r in driver.counters.lifecycle_rows
                if r["emitting_section"] == "flow_substrate" and r["emitted_on"] == occasion]

    def test_completed_seconds_reach_the_section(self):
        driver, result, summary = self._run()
        self.assertEqual(result["traversal"]["sections_fed"]["4.0_flow_seconds_completed"], 5)
        self.assertEqual(driver.counters.flow_seconds_completed, 5)
        self.assertEqual(summary["seconds_completed"], 5)
        self.assertEqual(summary["census_denominator"], 5)
        self.assertEqual(sum(summary["census"].values()), 5)

    def test_the_buy_second_is_classified_by_the_midpoint_rule(self):
        _, _, summary = self._run()
        self.assertEqual(summary["census"]["BUY"], 1)
        self.assertEqual(summary["census"]["SELL"], 0)
        self.assertEqual(summary["census"]["NO_DIRECTION"], 4)
        self.assertEqual(summary["no_direction_reasons"]["NO_TRADES"], 4)
        self.assertFalse(summary["tape_side_field_consulted"])
        self.assertEqual(summary["classification_rule"], native_roll20.CALCULATION)

    def test_the_window_direction_census_is_a_section_output_with_a_denominator(self):
        """The share Frankie reconstructed from traversal counters, now a share with its n."""
        _, _, summary = self._run()
        # The trade at second 2 sits in the trailing window of seconds 2, 3 and 4.
        self.assertEqual(summary["window_census"], {"LONG": 3, "SHORT": 0, "NO_DIRECTION": 2})
        self.assertAlmostEqual(summary["window_census_shares"]["NO_DIRECTION"], 0.4)

    def test_the_section_reconciles_with_the_traversal_binner(self):
        """Two computations of one number that are never compared are two numbers."""
        _, result, summary = self._run()
        roll = result["traversal"]["legacy_per_second_roll20"]
        dispositions = summary["trade_dispositions"]
        self.assertEqual(summary["rows_observed"], roll["rows_seen"])
        self.assertEqual(dispositions["at_mid"], roll["excluded_at_mid"])
        self.assertEqual(dispositions["no_quote"], roll["excluded_no_quote"])
        self.assertEqual(dispositions["unusable"], roll["excluded_unusable_price_or_size"])
        self.assertEqual(
            dispositions["buy"] + dispositions["sell"] + dispositions["at_mid"]
            + dispositions["no_quote"],
            roll["trades_seen"],
        )
        self.assertEqual(summary["volume_reconciliations"], 5)
        self.assertEqual(summary["boundary_skew_seconds"], 0)

    def test_averaged_rows_carry_the_denominator_and_a_full_declaration(self):
        _, result, _ = self._run()
        rows = [r for r in result["layers"]["averaged_companions"]["rows"]
                if r["section"] == "4.0"]
        buy = [r for r in rows if r["measure"] == "second_class_share_BUY"]
        self.assertEqual(len(buy), 1, "one day, one segment, one phase: one stratum")
        self.assertEqual(buy[0]["value"]["n"], 5)
        self.assertEqual(buy[0]["value"]["sum"], 1.0)
        self.assertAlmostEqual(buy[0]["value"]["arithmetic_mean"], 0.2)
        self.assertEqual(buy[0]["excluded_missing_members"], 0)
        declaration = buy[0]["declaration"]
        for field in ("numerator_formula", "population", "causal_cutoff", "status",
                      "missingness_rule"):
            self.assertTrue(declaration[field], field)
        self.assertIn(native_roll20.CALCULATION, declaration["numerator_formula"])
        self.assertEqual(buy[0]["stratum"]["session_phase"], PRE_SETTLEMENT)

    def test_every_completed_second_is_retained_as_an_exact_row(self):
        driver, _, _ = self._run()
        complete = self._flow_rows(driver, "SECOND_COMPLETE")
        self.assertEqual(len(complete), 5)
        by_second = sorted(complete, key=lambda r: r["second"])
        self.assertEqual([r["classification"] for r in by_second],
                         ["NO_DIRECTION", "NO_DIRECTION", "BUY", "NO_DIRECTION",
                          "NO_DIRECTION"])
        buy = by_second[2]
        self.assertEqual(buy["buy_volume"], 5.0)
        self.assertEqual(buy["buy_trades"], 1)
        self.assertIsNotNone(buy["last_quote"])
        self.assertEqual(buy["window_direction"], "LONG")
        self.assertEqual(buy["polarity"], 1)

    def test_the_last_second_is_incomplete_at_stream_end_not_dropped(self):
        """D60: a second the traversal never judged is retained and counted, never lost."""
        driver, _, summary = self._run()
        incomplete = self._flow_rows(driver, "STREAM_END")
        self.assertEqual(len(incomplete), 1)
        self.assertEqual(incomplete[0]["status"], "INCOMPLETE_STREAM_END")
        self.assertIsNone(incomplete[0]["classification"])
        self.assertEqual(summary["seconds_incomplete"], 1)
        self.assertEqual(summary["census_denominator"], 5, "outside the denominator")

    def test_a_second_is_filed_under_its_own_phase_not_the_next_group_s(self):
        """D75's shape, refused at the per-second level.

        Two groups bracket the settlement window's open: the first at 14:27:59 ET, the
        second at 14:28:02 ET. The three seconds the second group completes straddle the
        boundary, and the group that completed them sits INSIDE the window. Filing them
        under that group's phase would put a PRE_SETTLEMENT second in the SETTLEMENT
        stratum, which is exactly the off-by-one 4.12 carried for a full run.
        """
        driver = make_driver(total_mbo_records=2)
        first = at("2021-10-04T18:27:59")
        driver.consume([
            record(seq=0, event_ns=first, order_id=1),
            record(seq=1, event_ns=first + 3 * NS_PER_SECOND, order_id=2),
        ])
        driver.finalize()
        self.assertEqual(driver.current_mark.session_phase, SETTLEMENT)
        rows = sorted(self._flow_rows(driver, "SECOND_COMPLETE"), key=lambda r: r["second"])
        self.assertEqual([r["session_phase"] for r in rows],
                         [PRE_SETTLEMENT, SETTLEMENT, SETTLEMENT])

    def test_the_clock_is_the_traversal_s_declaration(self):
        """One declaration point. A driver on the event clock puts 4.0 on the event clock."""
        identity = RunIdentity(
            run_id="event-clock-4-0", arm="A_CLEAN", mission_sha256="a" * 64,
            calculation_contract_sha256="b" * 64, knowledge_manifest_hash="c" * 64,
            source_manifest_hash="d" * 64, total_mbo_records=1, code_commit="deadbeef",
        )
        run = NativeCalculationRun(
            identity, replenishment_horizon_ns=1_000, response_horizons_ns=(100,),
            response_horizon_version="hv1", response_value_names=("price_response",),
        )
        driver = NativeReplayDriver(
            identity=identity, session_rule=ExchangeSessionRule(), cadence=NeverInvoke(),
            run=run, roll20_clock=native_roll20.EVENT_CLOCK,
        )
        self.assertEqual(driver.run.flow_substrate.clock, native_roll20.EVENT_CLOCK)
        self.assertEqual(driver.roll20.clock, driver.run.flow_substrate.clock)


class FieldCensusCoversTheTraversalTest(unittest.TestCase):
    """F-10: the census sees every member row the traversal writes, and names the book.

    A calculator's tests passing while the driver never calls it is S119's recorded mistake;
    this is the driver-level proof, on a real traversal with a real reconstructed book.
    """

    def _run(self):
        # A resting bid and ask FIRST, so `book_full` carries a ladder with leaves to name;
        # three trades alone leave the book empty and a census of an empty book names no
        # level fields, which would make this test pass or fail on the fixture, not the code.
        driver = make_driver(total_mbo_records=4)
        base = at("2021-10-04T13:00:00")
        bid = record(seq=0, event_ns=base, order_id=400, action="A", side="B")
        bid["price"] = 3_499_000_000
        ask = record(seq=1, event_ns=base + NS_PER_SECOND, order_id=401, action="A", side="A")
        ask["price"] = 3_501_000_000
        trades = [
            record(seq=2 + i, event_ns=base + (2 + i) * NS_PER_SECOND, order_id=300 + i,
                   action="T")
            for i in range(2)
        ]
        driver.consume([bid, ask, *trades])
        return driver.finalize()

    def test_every_member_row_is_censused(self):
        layer = self._run()["layers"]["exact_member_ledger"]
        self.assertGreater(layer["exact_member_rows"], 0, "the fixture wrote no members")
        self.assertEqual(layer["field_census"]["rows_observed"], layer["exact_member_rows"])
        self.assertTrue(layer["field_census_covers_every_member_row"])

    def test_the_census_names_the_full_book_by_field_not_by_position(self):
        census = self._run()["layers"]["exact_member_ledger"]["field_census"]
        paths = {f["field"] for f in census["fields"]}
        self.assertIn("book_full", paths)
        for leaf in ("book_full.bid_levels_full[].price", "book_full.bid_levels_full[].size",
                     "book_full.ask_levels_full[].price"):
            self.assertIn(leaf, paths, f"{leaf} missing; the book is not being censused")
        self.assertFalse([p for p in paths if "[0]" in p], "positions leaked into the census")

    def test_the_census_is_json_serialisable_inside_the_result(self):
        import json
        json.dumps(self._run()["layers"]["exact_member_ledger"]["field_census"])


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
            # Seconds 3 through 12: the first group closes at second 3, the second at 13,
            # and a second is judged only once the stream has moved past it.
            "4.0_flow_seconds_completed": 10,
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
            # Ten completed seconds lie between the two group closes; each one is judged
            # by the detector and accounted by 4.0b, whether or not it produced anything.
            "4.0b_detector_seconds_accounted": 10,
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

    def test_the_ladder_transition_declares_which_substrate_it_measured(self):
        """D53's declared cost travels ON the value, never in prose alone - and D-5.

        Once a full book has been seen, 4.9 measures the BOOK, which is its contract; before
        the first book arrives there is nothing to compare against and it falls back to the
        group-local delta. Both readings occur in one run and are never interchangeable, so
        each row says which one it is.
        """
        driver, _ = self._run()
        ladder_rows = [r for r in driver.counters.lifecycle_rows if r["emitting_section"] == "ladder"]
        self.assertEqual(len(ladder_rows), 4)
        scopes = [row["ladder_scope"] for row in ladder_rows]
        self.assertEqual(scopes[:2], ["GROUP_LOCAL_DELTA"] * 2)
        self.assertEqual(set(scopes[2:]), {"FULL_BOOK_TRANSITION"})

    def test_the_full_book_reading_emits_both_sides_even_when_one_is_untouched(self):
        """D-5. An empty ask is a fact about the book; an absent ask is a missing opposite.

        `relative_imbalance` takes the opposite side's depth from the OTHER transition, so a
        dropped side leaves it with nothing to divide by - which is how 152 of 154 readings
        on the real run came out at exactly +/-1.0.
        """
        driver, _ = self._run()
        full = [r for r in driver.counters.lifecycle_rows
                if r["emitting_section"] == "ladder" and r["ladder_scope"] == "FULL_BOOK_TRANSITION"]
        by_recv = {}
        for row in full:
            by_recv.setdefault(row["recv_ns"], set()).add(row["side"])
        for recv, sides in by_recv.items():
            self.assertEqual(sides, {"B", "A"}, f"one side missing at {recv}")

    def test_every_fed_row_is_retained_beneath_its_summary(self):
        """D60 and section 6: an average with no member under it is not evidence."""
        driver, result = self._run()
        kept = {row["emitting_section"] for row in driver.counters.lifecycle_rows}
        for section in ("recurrence", "ladder", "absorption", "lineage", "flow_substrate"):
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
            "4.0_flow_seconds_completed": 0,
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
            "4.0b_detector_seconds_accounted": 0,
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


class DarkSectionRegressionTest(FedSectionsTest):
    """Two sections were BUILT and reached nothing. That is the shape to regress against.

    4.2 existed as a contract line and no module; 4.4 had a working matcher and was absent
    from the runner's section map entirely, the numbering jumping 4.2 straight to 4.5. Both
    produced a clean, accepted run while a section of the contract sat dark, which is why a
    passing verdict is not evidence that a section ran.
    """

    def test_the_book_reaches_the_section_whose_job_is_to_summarise_it(self):
        driver, result = self._run()
        self.assertGreater(driver.counters.book_snapshots_summarised, 0)
        rows = [r for r in result["layers"]["averaged_companions"]["rows"]
                if r["section"] == "4.2"]
        self.assertTrue(rows, "4.2 emitted no averaged rows; book_full has no consumer again")

    def test_the_mirror_matcher_is_actually_called(self):
        driver, result = self._run()
        self.assertGreater(driver.counters.mirror_members_offered, 0)
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"][
            "section_summaries"]["4.4"]
        self.assertTrue(summary["matcher_invoked"])
        self.assertEqual(summary["unmatched_reason_counts"]["NOT_OFFERED_TO_MATCHER"], 0)

    def test_pairing_nothing_still_produces_a_diagnosis(self):
        """The whole point of D-16: the diagnosis is needed precisely when nothing matched."""
        _, result = self._run()
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"][
            "section_summaries"]["4.4"]
        self.assertEqual(summary["pairs_formed"], 0)
        self.assertEqual(sum(summary["unmatched_reason_counts"].values()),
                         summary["members_seen"],
                         "every member must leave with a reason, or the population shrank")
        rows = [r for r in result["layers"]["averaged_companions"]["rows"]
                if r["section"] == "4.4"]
        self.assertTrue(rows, "no averaged rows at zero pairs is the delivered defect")

    def test_every_registered_section_contributes_or_is_accounted_for(self):
        """A section in the map with no rows and no summary is dark and would go unnoticed."""
        _, result = self._run()
        summaries = result["layers"]["exact_lifecycle_and_runway_ledger"]["section_summaries"]
        rows = {r["section"] for r in result["layers"]["averaged_companions"]["rows"]}
        for section in ("4.0", "4.0b", "4.2", "4.4", "4.5", "4.8", "4.9", "4.13", "4.14"):
            with self.subTest(section=section):
                self.assertTrue(section in summaries or section in rows,
                                f"{section} produced neither a summary nor an averaged row")

    def test_the_per_second_substrate_reaches_section_4_0(self):
        """Frankie's item (a): the substrate was a counters block, not a section.

        The detector and 4.12 ran on `legacy_per_second_roll20` with no declaration, stratum,
        denominator or gate beneath it. This asserts the DRIVER hands completed seconds to
        the section - a calculator's own tests cannot show that, which is S119's recorded
        lesson - and that what it received equals what it summarised.
        """
        driver, result = self._run()
        fed = result["traversal"]["sections_fed"]["4.0_flow_seconds_completed"]
        self.assertGreater(fed, 0)
        self.assertEqual(driver.counters.flow_seconds_completed, fed)
        rows = [r for r in result["layers"]["averaged_companions"]["rows"]
                if r["section"] == "4.0"]
        self.assertTrue(rows, "4.0 emitted no averaged rows; the substrate is a counters "
                              "block again")
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"][
            "section_summaries"]["4.0"]
        self.assertEqual(summary["seconds_completed"], fed)
        self.assertEqual(sum(summary["census"].values()), fed)


class DetectorCoverageFedTest(CandidateUnitFedTest):
    """4.0b through the DRIVER, on a tape that both promotes and rejects.

    The section accounts for the selection function that creates the 4.10-4.12/4.16
    population, and its unit tests drive the detector directly. This proves the traversal
    feeds it - every second, after the detector judged that second - because a correct
    calculator nothing calls reports an exact zero, which is what seven of S119's sixteen
    defects were. The fixture is the candidate one: the tiny fixtures produce no candidates
    and would make every promotion assertion vacuous.
    """

    def _summary(self, result):
        return result["layers"]["exact_lifecycle_and_runway_ledger"]["section_summaries"]["4.0b"]

    def test_the_section_is_fed_and_sees_both_promotions_and_rejections(self):
        driver, result = self._run()
        self.assertGreater(driver.counters.detector_seconds_accounted, 0,
                           "4.0b is wired and nothing reached it")
        self.assertEqual(
            result["traversal"]["sections_fed"]["4.0b_detector_seconds_accounted"],
            driver.counters.detector_seconds_accounted,
        )
        summary = self._summary(result)
        self.assertEqual(summary["status"], "FED_BY_THE_TRAVERSAL")
        self.assertGreater(summary["promoted"], 0)
        self.assertGreater(summary["rejected_total"], 0)
        # Which reason fires is a property of the tape, not of the wiring: this fixture's
        # alternating one-lot tape sums every 20-second window to exactly zero, so its
        # rejections are zero-magnitude ones and the bar is never the reason. What the wiring
        # owes is that every rejection has a NAMED reason and the names are the detector's.
        reasons = summary["rejected_by_reason"]
        self.assertEqual(tuple(reasons), (
            "rejected_zero_magnitude", "rejected_below_threshold", "rejected_not_local_max",
            "rejected_in_refractory", "rejected_in_refractory_at_release",
            "suppressed_by_prominence",
        ))
        self.assertEqual(sum(reasons.values()), summary["rejected_total"])
        self.assertTrue(any(reasons.values()))
        self.assertEqual(summary["promoted"],
                         result["traversal"]["sections_fed"]["candidate_unit_events"])

    def test_the_summary_reconciles_with_the_detectors_own_block(self):
        """`traversal.candidate_detection` is the detector's word; 4.0b must say the same."""
        _, result = self._run()
        summary = self._summary(result)
        blocks = result["traversal"]["candidate_detection"]
        self.assertTrue(blocks)
        for name in ("seconds_observed", "seconds_judged", "seconds_in_warmup",
                     "seconds_without_finite_flow"):
            with self.subTest(counter=name):
                self.assertEqual(summary[name], sum(b[name] for b in blocks))
        self.assertEqual(summary["promoted"], sum(b["candidates_emitted"] for b in blocks))
        for reason, count in summary["rejected_by_reason"].items():
            with self.subTest(reason=reason):
                self.assertEqual(count, sum(b[reason] for b in blocks))

    def test_every_downstream_rate_gets_its_denominator(self):
        _, result = self._run()
        summary = self._summary(result)
        rate = summary["promotion_rate"]
        self.assertEqual(rate["numerator"], summary["promoted"])
        self.assertEqual(rate["denominator"], summary["considered"])
        self.assertEqual(summary["considered"],
                         summary["promoted"] + summary["rejected_total"]
                         + summary["candidates_pending_in_window"])
        self.assertEqual(summary["seconds_judged"],
                         summary["searched_seconds"] + summary["seconds_in_warmup"])
        self.assertTrue(summary["partition_identity"]["segments_verified"] >= 1)

    def test_the_averaged_rows_carry_the_parameters_and_a_declaration(self):
        _, result = self._run()
        rows = [r for r in result["layers"]["averaged_companions"]["rows"]
                if r["section"] == "4.0b"]
        self.assertTrue(rows, "4.0b emitted no averaged rows; the search is dark again")
        for row in rows:
            with self.subTest(measure=row["measure"], phase=row["stratum"]["session_phase"]):
                self.assertEqual(row["kind"], "COUNT_PARTITION")
                self.assertEqual(row["stratum"]["source_day"], "20211004")
                self.assertEqual(row["stratum"]["family_id"], "ALL_FAMILIES_DETECTOR_SEARCH")
                params = row["value"]["detector_parameters"]
                self.assertEqual(params["refractory_seconds"], nc.REFRACTORY)
                self.assertEqual(params["warmup_seconds"], 60)
                self.assertEqual(params["min_threshold_observations"], 30)
                self.assertTrue(row["value"]["parameter_signature"])
                self.assertNotIn("arithmetic_mean", row["value"])
                for field_name in ("numerator_formula", "population", "causal_cutoff",
                                   "status", "missingness_rule"):
                    self.assertTrue(row["declaration"][field_name])

    def test_the_reconciliation_row_is_retained_beneath_the_summary(self):
        driver, _ = self._run()
        rows = [r for r in driver.counters.lifecycle_rows
                if r["emitting_section"] == "detector_coverage"]
        self.assertTrue(rows, "the close returned a row and nothing kept it")
        for row in rows:
            self.assertTrue(row["partition_identity_holds"])
            self.assertTrue(row["reconciled_with_detector"])
            self.assertIn(row["emitted_on"], ("SEGMENT_CLOSE", "STREAM_END"))
        self.assertEqual(rows[-1]["emitted_on"], "STREAM_END")
        self.assertEqual(rows[-1]["detector_counters"]["candidates_pending_in_window"], 0)

    def test_a_run_carrying_the_section_is_still_accepted(self):
        _, result = self._run()
        self.assertEqual(result["verdict"], ACCEPTED, result["failed_gates"])

    def test_an_unfed_pass_declares_itself(self):
        """Same section, no tape: the declaration, not a zero that reads like a finding."""
        driver = make_driver()
        result = driver.finalize()
        self.assertEqual(self._summary(result)["status"], "NOT_FED_BY_THE_TRAVERSAL")
        self.assertEqual(result["traversal"]["sections_fed"]["4.0b_detector_seconds_accounted"], 0)


class ResponseChannelWiringTest(unittest.TestCase):
    """D-10. 4.16 emitted 1 of 7 channels, and three of the missing four were already in hand.

    Flow, full-book depth and queue depth all sat in the traversal at the same instant the
    price did; the feed carried a single integer, so there was nowhere to put them. This runs
    the real traversal with all four declared and asserts they arrive - a section that
    CONSTRUCTS with four channels and is fed one is the defect wearing a new shape.
    """

    def _run_with_channels(self):
        driver = make_driver(
            total_mbo_records=8,
            response_horizons_ns=horizons_for_version("a-arm-h2"),
            response_horizon_version="a-arm-h2",
            response_value_names=(
                PRICE_RESPONSE, FLOW_RESPONSE, FULL_BOOK_RESPONSE, QUEUE_RESPONSE),
        )
        base = at("2021-10-04T13:00:00")
        seq = 0
        for group_index, group in enumerate(FedSectionsTest.GROUPS):
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

    def test_all_four_feedable_channels_reach_the_section(self):
        _, result = self._run_with_channels()
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"][
            "section_summaries"]["4.16"]
        self.assertEqual(
            list(summary["value_names"]),
            [PRICE_RESPONSE, FLOW_RESPONSE, FULL_BOOK_RESPONSE, QUEUE_RESPONSE],
        )

    def test_the_sub_second_horizons_are_present_beneath_the_frozen_three(self):
        """F-36: price response is already zero at the median by one second."""
        _, result = self._run_with_channels()
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"][
            "section_summaries"]["4.16"]
        horizons = list(summary["horizons_ns"])
        self.assertEqual(horizons[-3:], [1_000_000_000, 10_000_000_000, 60_000_000_000],
                         "the frozen a-arm-h1 rungs must survive unchanged")
        self.assertTrue([h for h in horizons if h < 1_000_000_000])

    def test_a_run_with_every_channel_declared_is_still_accepted(self):
        _, result = self._run_with_channels()
        self.assertEqual(result["verdict"], ACCEPTED, result["failed_gates"])


class ChangePointsAreDrivenByEventsTest(unittest.TestCase):
    """4.16's event-driven half, wired at the DRIVER because that is where it was missing.

    `observe_change_point` was correct and had no caller anywhere - the eighth instance of
    the shape S119 closed seven of. S119's own recorded mistake was a finalize wired into
    the wrong loop, whose tests passed because they called the calculator directly, so
    every assertion here goes through `driver.consume`.
    """

    def _run(self, *, emit: bool, records: int = 3):
        driver = make_driver(total_mbo_records=records, emit_change_points=emit)
        base = at("2021-10-04T13:00:00")
        driver.consume(
            record(seq=i, event_ns=base + i * NS_PER_SECOND, order_id=300 + i, action="T")
            for i in range(records)
        )
        return driver, driver.finalize()

    def _summary(self, result):
        return (result["layers"]["exact_lifecycle_and_runway_ledger"]
                ["section_summaries"]["4.16"]["event_driven_change_points"])

    def test_unfed_it_declares_itself_rather_than_reporting_a_bare_zero(self):
        """A zero and an absence are indistinguishable, which is the whole S119 finding."""
        _, result = self._run(emit=False)
        summary = self._summary(result)
        self.assertEqual(summary["observed"], 0)
        self.assertEqual(summary["status"], "NOT_FED_BY_THE_TRAVERSAL")

    def test_the_flag_is_off_by_default_because_it_is_a_size_decision(self):
        driver = make_driver()
        self.assertFalse(driver.emit_change_points)

    def test_a_repeated_state_emits_no_change_point(self):
        """The trigger is an EVENT. A constant tape must produce no change points at all.

        Firing per second instead would make this a fourth fixed cadence, retaining
        (open tracks x seconds) under D60 to record readings the horizons already carry.
        """
        driver, _ = self._run(emit=True, records=5)
        seen = driver.responses.state_fingerprint()
        self.assertEqual(driver._last_change_point_state in (None, seen), True)
        self.assertEqual(driver.run.response.change_points_observed, 0)

    def test_the_fingerprint_moves_when_the_observable_state_moves(self):
        """If the fingerprint cannot change, nothing downstream of it can ever fire.

        D23 applied to the trigger itself: a condition that cannot change state carries no
        information, whatever form it is written in - which is exactly how 4.16's
        `starting_liquidity_regime` came to read the same value on all 84 at-risk rows.
        """
        driver, _ = self._run(emit=True)
        first = driver.responses.state_fingerprint()
        driver.responses.note_state(
            driver._latest_book, signed_flow_lots=(driver._last_signed_flow or 0) + 7
        )
        self.assertNotEqual(first, driver.responses.state_fingerprint())


class ChangePointsActuallyFireTest(ResponseTableFedTest):
    """The test that matters: the guard PRODUCING its output, not merely staying silent.

    The tests above prove change points do not fire on a constant tape. That is the
    negative half, and S113's NC-3 is the reason it is not enough - a guard whose firing
    branch never executed was never tested. This fixture detects real candidates, so 4.16
    tracks are actually open and there is something for a change point to be written to;
    the small fixtures open none, which would make `observe_change_point` a no-op loop over
    an empty dict and every assertion about it vacuously true.
    """

    def _drive(self, *, emit: bool):
        driver = make_driver(total_mbo_records=self.SPAN + 1, emit_change_points=emit)
        driver.candidate_warmup_seconds = 60
        driver.candidate_min_observations = 30
        driver.detector = driver._new_detector(0)
        driver.consume(self._stream())
        result = driver.finalize()
        summary = (result["layers"]["exact_lifecycle_and_runway_ledger"]
                   ["section_summaries"]["4.16"])
        return result, summary

    def test_tracks_are_open_so_the_assertion_is_not_vacuous(self):
        _, summary = self._drive(emit=False)
        self.assertGreater(summary["tracks_opened"], 0)

    def test_fed_it_fires_and_says_so(self):
        _, summary = self._drive(emit=True)
        points = summary["event_driven_change_points"]
        self.assertGreater(points["observed"], 0, "wired but nothing reached it")
        self.assertEqual(points["status"], "FED_BY_THE_TRAVERSAL")

    def test_unfed_the_same_tape_reports_the_declaration_not_a_zero(self):
        """Same records, same candidates - the ONLY difference is the flag.

        Holding the tape constant is what makes this a measurement of the wiring rather
        than of the fixture.
        """
        _, summary = self._drive(emit=False)
        points = summary["event_driven_change_points"]
        self.assertEqual(points["observed"], 0)
        self.assertEqual(points["status"], "NOT_FED_BY_THE_TRAVERSAL")

    def test_feeding_change_points_does_not_change_the_verdict(self):
        """A retained observation must not be able to reject a run that would be accepted.

        `finalize` is not idempotent - calling it twice raises out of the mirror - so the
        verdict is taken from the result each drive already produced.
        """
        off, _ = self._drive(emit=False)
        on, _ = self._drive(emit=True)
        self.assertEqual(off["verdict"], on["verdict"])
        self.assertEqual(off["failed_gates"], on["failed_gates"])


class ExitStratumReachesTheLedgerTest(unittest.TestCase):
    """F-17 through the DRIVER: an order born in one group and cancelled in the next.

    The calculator tests prove the exit view is filed when TOLD the exit context. This proves
    the adapter TELLS it - passes the terminal group's family and phase - which is the wiring
    a calculator-level test cannot see, and the shape S119's own recorded mistake took.

    Its own two-group stream, because the shared fixtures only ever censor 4.6 at stream
    end: an order that never dies inside a group has no exit stratum by construction, so a
    test on that tape would be vacuous whichever way the wiring went.
    """

    def _run(self):
        driver = make_driver(total_mbo_records=2)
        base = at("2021-10-04T13:00:00")
        driver.consume([
            record(seq=0, event_ns=base, order_id=900, action="A", side="B", last=True),
            record(seq=1, event_ns=base + NS_PER_SECOND, order_id=900, action="C", side="B",
                   last=True),
        ])
        return driver, driver.finalize()

    def test_the_cancel_in_the_second_group_carries_that_group_as_its_exit(self):
        driver, _ = self._run()
        rows = [r for r in driver.counters.lifecycle_rows
                if r.get("emitting_section") == "queue" and r.get("terminal_status")
                and r.get("emitted_on") != "STREAM_END"]
        self.assertTrue(rows, "the cancel produced no mid-stream 4.6 terminal row")
        row = rows[0]
        self.assertTrue(row["exit_stratum_available"], "the adapter did not pass the "
                                                        "terminal group's context")
        self.assertIsNotNone(row["exit_family_id"])
        self.assertEqual(row["stratum_basis"], "BIRTH_STAMPED", "birth stays primary")
        self.assertIn("birth_family_id", row)

    def test_the_exit_view_is_fed_by_the_traversal(self):
        """Not the label on the row - the section summary says the exit view received it."""
        driver, result = self._run()
        summary = result["layers"]["exact_lifecycle_and_runway_ledger"]["section_summaries"]["4.6"]
        self.assertGreaterEqual(summary["exit_view"]["filed"], 1)



class QueueTerminalJoinsReplenishmentEpisodeTest(ExitStratumReachesTheLedgerTest):
    """F-18 join 5 through the DRIVER: a cancel that empties a level is BOTH a 4.6 terminal
    and a 4.7 removal, and the two rows must carry the same key.

    Reuses the two-record add-then-cancel tape: order 900 is the only order at its level,
    so its cancel depletes the level and 4.7 opens an episode on exactly that instant.
    """

    def test_the_terminal_key_is_among_the_episode_keys(self):
        driver, _ = self._run()
        terminals = {r["level_event_key_at_exit"] for r in driver.counters.lifecycle_rows
                     if r.get("emitting_section") == "queue"
                     and r.get("level_event_key_at_exit")}
        episodes = {r["level_event_key"] for r in driver.counters.lifecycle_rows
                    if r.get("emitting_section") == "replenishment"
                    and r.get("level_event_key")}
        self.assertTrue(terminals, "no 4.6 terminal carried a level key")
        self.assertTrue(episodes, "no 4.7 episode row carried a level key")
        self.assertTrue(terminals & episodes,
                        f"no 4.6 terminal joins a 4.7 episode: {terminals} vs {episodes}")
