"""Tests for section 2 continuity segmentation and trading-day assignment (D6a).

The boundary rule is taken from the CME contract spec - Sunday-Friday 17:00-16:00 CT with a
60-minute halt beginning 16:00 CT, Monday-Friday - not inferred from our own tape. The
roster exemplars are used one by one as a CHECK on that rule, never as its basis, and never
pooled.
"""
from __future__ import annotations

import unittest
from datetime import date, datetime, timezone

from research.kalshi.frankie_raw_mbo_benchmark.native_session import (
    CLOSE_LOCAL_TIME,
    EXCHANGE_TZ_NAME,
    NS_PER_SECOND,
    REOPEN_LOCAL_TIME,
    SessionError,
    SessionSegmenter,
    close_instant_ns,
    continuity_segment,
    group_event_ns,
    in_halt_window,
    reopen_instant_ns,
    trade_day,
)


def ns(iso: str) -> int:
    head, _, frac = iso.rstrip("Z").partition(".")
    whole = int(datetime.fromisoformat(head).replace(tzinfo=timezone.utc).timestamp())
    return whole * NS_PER_SECOND + (int(frac.ljust(9, "0")) if frac else 0)


def group(ts_event_ns: int) -> dict:
    return {"raw_actions": [{"ts_event_ns": ts_event_ns, "ts_recv_ns": ts_event_ns + 157_000_000}]}


# Roster exemplars, named individually.
FRIDAY_CLOSE_1001 = ns("2021-10-01T21:00:00.253186799Z")
WITHDRAWAL_1004 = ns("2021-10-04T21:00:00.078569755Z")
WITHDRAWAL_1005 = ns("2021-10-05T21:00:00.078400519Z")


class ExchangeScheduleTest(unittest.TestCase):
    """The rule as CME states it, before any of our data is consulted."""

    def test_close_is_1600_ct_and_reopen_is_1700_ct(self):
        self.assertEqual((CLOSE_LOCAL_TIME.hour, CLOSE_LOCAL_TIME.minute), (16, 0))
        self.assertEqual((REOPEN_LOCAL_TIME.hour, REOPEN_LOCAL_TIME.minute), (17, 0))
        self.assertEqual(EXCHANGE_TZ_NAME, "America/Chicago")

    def test_halt_is_exactly_sixty_minutes(self):
        day = date(2021, 10, 4)
        self.assertEqual(reopen_instant_ns(day) - close_instant_ns(day), 3600 * NS_PER_SECOND)

    def test_close_is_2100_utc_under_cdt(self):
        for day in (date(2021, 10, 1), date(2021, 10, 4), date(2021, 10, 5)):
            utc = datetime.fromtimestamp(close_instant_ns(day) // NS_PER_SECOND, tz=timezone.utc)
            self.assertEqual((utc.hour, utc.minute), (21, 0), f"{day}")

    def test_close_moves_to_2200_utc_after_dst_ends(self):
        """Why the rule is exchange-local. A literal 21:00 UTC constant reproduces this
        roster and is then silently one hour wrong from 2021-11-07."""
        utc = datetime.fromtimestamp(
            close_instant_ns(date(2021, 11, 8)) // NS_PER_SECOND, tz=timezone.utc
        )
        self.assertEqual((utc.hour, utc.minute), (22, 0))


class RosterCheckTest(unittest.TestCase):
    """Our tape checked against the exchange rule, day by day."""

    def test_each_roster_close_group_lands_in_the_halt_window(self):
        for label, at in (
            ("20211001", FRIDAY_CLOSE_1001),
            ("20211004", WITHDRAWAL_1004),
            ("20211005", WITHDRAWAL_1005),
        ):
            with self.subTest(day=label):
                self.assertTrue(in_halt_window(at))

    def test_sunday_has_no_close(self):
        """20211003 is a Sunday; CME halts Monday-Friday only, so the one roster day with no
        close group is the one the exchange says should not have one."""
        self.assertEqual(date(2021, 10, 3).weekday(), 6)
        self.assertEqual(trade_day(close_instant_ns(date(2021, 10, 3))), date(2021, 10, 4))

    def test_every_roster_day_maps_to_a_weekday_trade_date(self):
        for label, at in (
            ("20211001", FRIDAY_CLOSE_1001),
            ("20211004", WITHDRAWAL_1004),
            ("20211005", WITHDRAWAL_1005),
        ):
            with self.subTest(day=label):
                self.assertEqual(trade_day(at).strftime("%Y%m%d"), label)


class HaltWindowTest(unittest.TestCase):
    def test_window_is_half_open_on_the_close(self):
        day = date(2021, 10, 4)
        self.assertTrue(in_halt_window(close_instant_ns(day)))
        self.assertFalse(in_halt_window(close_instant_ns(day) - 1))

    def test_window_is_half_open_on_the_reopen(self):
        day = date(2021, 10, 4)
        self.assertFalse(in_halt_window(reopen_instant_ns(day)))
        self.assertTrue(in_halt_window(reopen_instant_ns(day) - 1))


class TradeDayTest(unittest.TestCase):
    """The CME trade date: 17:00 CT on the previous calendar day through 16:00 CT."""

    def test_date_rolls_at_the_1700_ct_reopen_not_at_midnight(self):
        reopen = reopen_instant_ns(date(2021, 10, 4))
        self.assertEqual(trade_day(reopen - 1), date(2021, 10, 4))
        self.assertEqual(trade_day(reopen), date(2021, 10, 5))

    def test_midnight_ct_is_not_a_boundary(self):
        """HE1..HE24 would roll here. The exchange does not."""
        self.assertEqual(trade_day(ns("2021-10-05T04:59:59Z")), date(2021, 10, 5))
        self.assertEqual(trade_day(ns("2021-10-05T05:00:00Z")), date(2021, 10, 5))

    def test_close_and_halt_hour_stay_on_the_outgoing_date(self):
        self.assertEqual(trade_day(WITHDRAWAL_1004), date(2021, 10, 4))
        self.assertEqual(trade_day(close_instant_ns(date(2021, 10, 4)) + 1), date(2021, 10, 4))

    def test_sunday_reopen_carries_mondays_date_by_definition(self):
        """The S104 Sunday fold and the CME rule are the same rule, not an exception."""
        self.assertEqual(trade_day(reopen_instant_ns(date(2021, 10, 3))), date(2021, 10, 4))
        self.assertEqual(trade_day(ns("2021-10-03T23:00:00Z")), date(2021, 10, 4))

    def test_no_trade_date_falls_on_a_weekend(self):
        for at in (
            ns("2021-10-01T23:00:00Z"),
            ns("2021-10-02T12:00:00Z"),
            ns("2021-10-03T12:00:00Z"),
        ):
            with self.subTest(at=at):
                self.assertLess(trade_day(at).weekday(), 5)

    def test_friday_session_keeps_fridays_date(self):
        self.assertEqual(trade_day(FRIDAY_CLOSE_1001), date(2021, 10, 1))


class ContinuitySegmentTest(unittest.TestCase):
    def test_segment_runs_reopen_to_close(self):
        """The withdrawal group is the terminal event of the session it liquidates, not the
        first event of the next one."""
        self.assertEqual(
            continuity_segment(WITHDRAWAL_1004),
            continuity_segment(ns("2021-10-04T13:00:00Z")),
        )

    def test_segment_is_the_trade_date_ordinal(self):
        """One CME trade date is exactly one continuous book, so they are not two anchors."""
        for at in (FRIDAY_CLOSE_1001, WITHDRAWAL_1004, WITHDRAWAL_1005):
            with self.subTest(at=at):
                self.assertEqual(
                    continuity_segment(at),
                    (trade_day(at) - date(1970, 1, 1)).days,
                )

    def test_weekend_is_one_segment_not_three(self):
        """Friday close to Sunday reopen is a single ~49h censoring gap."""
        self.assertEqual(
            continuity_segment(ns("2021-10-03T23:00:00Z")),
            continuity_segment(WITHDRAWAL_1004),
        )

    def test_reopen_opens_a_new_segment(self):
        reopen = reopen_instant_ns(date(2021, 10, 4))
        self.assertEqual(continuity_segment(reopen) - continuity_segment(reopen - 1), 1)

    def test_overnight_leg_stays_in_one_segment(self):
        self.assertEqual(
            continuity_segment(ns("2021-10-04T23:00:00Z")),
            continuity_segment(ns("2021-10-05T14:30:00Z")),
        )

    def test_ordinal_is_absolute_not_run_relative(self):
        self.assertEqual(
            SessionSegmenter().assign(WITHDRAWAL_1005)["continuity_segment"],
            continuity_segment(WITHDRAWAL_1005),
        )


class SegmenterTest(unittest.TestCase):
    def test_refuses_non_monotonic_event_times(self):
        segmenter = SessionSegmenter()
        segmenter.assign(WITHDRAWAL_1005)
        with self.assertRaises(SessionError):
            segmenter.assign(WITHDRAWAL_1004)

    def test_counts_boundaries_crossed(self):
        segmenter = SessionSegmenter()
        for at in (
            ns("2021-10-04T20:00:00Z"),
            WITHDRAWAL_1004,
            ns("2021-10-04T23:00:00Z"),
            WITHDRAWAL_1005,
        ):
            segmenter.assign(at)
        self.assertEqual(segmenter.boundaries_crossed, 1)

    def test_assign_group_reports_all_three_fields(self):
        out = SessionSegmenter().assign_group(group(WITHDRAWAL_1004))
        self.assertEqual(out["trade_day"], "20211004")
        self.assertTrue(out["in_halt_window"])
        self.assertEqual(out["continuity_segment"], continuity_segment(WITHDRAWAL_1004))

    def test_group_without_raw_actions_is_refused(self):
        with self.assertRaises(SessionError):
            group_event_ns({"raw_actions": []})
        with self.assertRaises(SessionError):
            group_event_ns({})

    def test_segmentation_reads_event_time_not_receive_time(self):
        close = close_instant_ns(date(2021, 10, 4))
        straddler = {"raw_actions": [{"ts_event_ns": close - 1, "ts_recv_ns": close + 250_000_000}]}
        self.assertFalse(SessionSegmenter().assign_group(straddler)["in_halt_window"])


if __name__ == "__main__":
    unittest.main()
