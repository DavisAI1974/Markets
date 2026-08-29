"""Tests for the traversal driver.

The driver had no tests: it imported cleanly and nothing ran it. These start at the riskiest
point - does a pass execute end to end at all - rather than at the edges.
"""
from __future__ import annotations

import unittest
from datetime import datetime, timezone

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
