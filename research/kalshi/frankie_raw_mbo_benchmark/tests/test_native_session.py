"""Tests for section 2 continuity segmentation and trading-day assignment (D6a).

The boundary rule is taken from the CME contract spec - Sunday-Friday 17:00-16:00 CT with a
60-minute halt beginning 16:00 CT, Monday-Friday - not inferred from our own tape. The
roster exemplars are used one by one as a CHECK on that rule, never as its basis, and never
pooled.
"""
from __future__ import annotations

import unittest
from datetime import date, datetime, time, timezone

from research.kalshi.frankie_raw_mbo_benchmark import native_session

from research.kalshi.frankie_raw_mbo_benchmark.native_session import (
    CLOSE_LOCAL_TIME,
    EXCHANGE_TZ_NAME,
    NS_PER_SECOND,
    REOPEN_LOCAL_TIME,
    CARRIED_PHASES,
    POST_CLOSE,
    POST_SETTLEMENT,
    PRE_OPEN,
    PRE_SETTLEMENT,
    SETTLEMENT,
    SETTLEMENT_END_ET,
    SETTLEMENT_START_ET,
    SETTLEMENT_TZ_NAME,
    SessionError,
    SessionSegmenter,
    close_instant_ns,
    continuity_segment,
    phase_within,
    segment_of,
    segment_stream,
    group_event_ns,
    reopen_instant_ns,
    session_open_ns,
    session_phase,
    settlement_window_ns,
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

    def test_each_roster_close_group_lands_after_its_own_close(self):
        for label, at in (
            ("20211001", FRIDAY_CLOSE_1001),
            ("20211004", WITHDRAWAL_1004),
            ("20211005", WITHDRAWAL_1005),
        ):
            with self.subTest(day=label):
                self.assertGreaterEqual(at, close_instant_ns(trade_day(at)))

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
    """The halt is expressed as POST_CLOSE, not as a second overlapping flag.

    A `in_halt_window` helper existed here and was removed under review: it tested the local
    clock alone, so it read True at 16:30 CT on a SATURDAY, contradicting `session_phase`
    for the same instant. Two fields in one output dict disagreeing about the same fact is
    the shape of the S109 `session_b_share` defect - both present, both plausible, silently
    incompatible. These tests pin the behaviour so it cannot come back."""

    def test_halt_is_half_open_on_the_close(self):
        day = date(2021, 10, 4)
        self.assertEqual(session_phase(close_instant_ns(day)), POST_CLOSE)
        self.assertNotEqual(session_phase(close_instant_ns(day) - 1), POST_CLOSE)

    def test_halt_is_half_open_on_the_reopen(self):
        day = date(2021, 10, 4)
        self.assertNotEqual(session_phase(reopen_instant_ns(day)), POST_CLOSE)
        self.assertEqual(session_phase(reopen_instant_ns(day) - 1), POST_CLOSE)

    def test_the_weekend_clock_hour_is_not_a_halt(self):
        """16:30 CT on a Saturday is not the daily halt - the book has been down since
        Friday. A local-clock test cannot tell these apart; the trade date can."""
        saturday_1630_ct = ns("2021-10-02T21:30:00Z")
        self.assertEqual(session_phase(saturday_1630_ct), PRE_OPEN)


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


class SettlementWindowTest(unittest.TestCase):
    """14:28:00-14:30:00 ET, per the NYMEX Energy Futures Daily Settlement Procedure."""

    def test_window_times_and_zone_match_the_procedure(self):
        self.assertEqual((SETTLEMENT_START_ET.hour, SETTLEMENT_START_ET.minute), (14, 28))
        self.assertEqual((SETTLEMENT_END_ET.hour, SETTLEMENT_END_ET.minute), (14, 30))
        self.assertEqual(SETTLEMENT_TZ_NAME, "America/New_York")

    def test_window_is_exactly_two_minutes(self):
        start, end = settlement_window_ns(date(2021, 10, 4))
        self.assertEqual(end - start, 120 * NS_PER_SECOND)

    def test_window_is_resolved_in_eastern_not_converted_from_central(self):
        """The session is defined in CT and settlement in ET. Resolving each in its own
        stated zone is what stops one drifting when the other is edited."""
        start, _ = settlement_window_ns(date(2021, 10, 4))
        utc = datetime.fromtimestamp(start // NS_PER_SECOND, tz=timezone.utc)
        self.assertEqual((utc.hour, utc.minute), (18, 28))


class SessionPhaseTest(unittest.TestCase):
    """D6b. Every boundary is exchange-stated; none is fitted to our tape."""

    def test_settlement_window_is_half_open(self):
        start, end = settlement_window_ns(date(2021, 10, 4))
        self.assertEqual(session_phase(start - 1), PRE_SETTLEMENT)
        self.assertEqual(session_phase(start), SETTLEMENT)
        self.assertEqual(session_phase(end - 1), SETTLEMENT)
        self.assertEqual(session_phase(end), POST_SETTLEMENT)

    def test_close_ends_the_session_and_reopen_starts_the_next(self):
        close = close_instant_ns(date(2021, 10, 4))
        self.assertEqual(session_phase(close - 1), POST_SETTLEMENT)
        self.assertEqual(session_phase(close), POST_CLOSE)
        self.assertEqual(session_phase(reopen_instant_ns(date(2021, 10, 4))), PRE_SETTLEMENT)

    def test_each_roster_close_group_is_post_close(self):
        for label, at in (
            ("20211001", FRIDAY_CLOSE_1001),
            ("20211004", WITHDRAWAL_1004),
            ("20211005", WITHDRAWAL_1005),
        ):
            with self.subTest(day=label):
                self.assertEqual(session_phase(at), POST_CLOSE)

    def test_weekend_gap_is_pre_open_not_a_trading_phase(self):
        """Saturday carries Monday's trade date, but the book is down - it must not be
        labelled as part of Monday's session."""
        saturday = ns("2021-10-02T17:00:00Z")
        self.assertEqual(trade_day(saturday), date(2021, 10, 4))
        self.assertEqual(session_phase(saturday), PRE_OPEN)

    def test_sunday_reopen_starts_mondays_session(self):
        opened = session_open_ns(date(2021, 10, 4))
        self.assertEqual(session_phase(opened - 1), PRE_OPEN)
        self.assertEqual(session_phase(opened), PRE_SETTLEMENT)

    def test_a_full_trade_date_visits_every_phase_in_order(self):
        """The phases partition the trade date - the gap D6b was open on."""
        day = date(2021, 10, 5)
        start, end = settlement_window_ns(day)
        marks = [
            (session_open_ns(day), PRE_SETTLEMENT),
            (start, SETTLEMENT),
            (end, POST_SETTLEMENT),
            (close_instant_ns(day), POST_CLOSE),
        ]
        self.assertEqual([session_phase(at) for at, _ in marks], [want for _, want in marks])
        self.assertEqual([at for at, _ in marks], sorted(at for at, _ in marks))
        for at, _ in marks:
            self.assertEqual(trade_day(at), day)

    def test_the_instant_before_a_midweek_open_belongs_to_the_prior_date(self):
        """There is no PRE_OPEN on a normal weekday: the hour before Tuesday's session is
        Monday's POST_CLOSE, because the halt belongs to the date it closes."""
        opened = session_open_ns(date(2021, 10, 5))
        self.assertEqual(session_phase(opened - 1), POST_CLOSE)
        self.assertEqual(trade_day(opened - 1), date(2021, 10, 4))

    def test_pre_open_appears_only_when_the_gap_exceeds_the_daily_halt(self):
        """PRE_OPEN is the weekend (and, once wired, holiday) signature - a ~49h censoring
        gap rather than a 1h one."""
        weekend = ns("2021-10-02T17:00:00Z")
        self.assertEqual(session_phase(weekend), PRE_OPEN)
        midweek_halt = close_instant_ns(date(2021, 10, 4)) + 1800 * NS_PER_SECOND
        self.assertEqual(session_phase(midweek_halt), POST_CLOSE)

    def test_carried_phases_are_a_starting_point_not_a_validator(self):
        """Open-world rule: nothing may reject a phase that is not carried."""
        key_like = {"session_phase": "A_PHASE_NOBODY_HAS_NAMED_YET"}
        self.assertNotIn(key_like["session_phase"], CARRIED_PHASES)
        self.assertEqual(len(set(CARRIED_PHASES)), len(CARRIED_PHASES))


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
        self.assertEqual(out["session_phase"], POST_CLOSE)
        self.assertNotIn("in_halt_window", out)
        self.assertEqual(out["continuity_segment"], continuity_segment(WITHDRAWAL_1004))

    def test_group_without_raw_actions_is_refused(self):
        with self.assertRaises(SessionError):
            group_event_ns({"raw_actions": []})
        with self.assertRaises(SessionError):
            group_event_ns({})

    def test_segmentation_reads_event_time_not_receive_time(self):
        close = close_instant_ns(date(2021, 10, 4))
        straddler = {"raw_actions": [{"ts_event_ns": close - 1, "ts_recv_ns": close + 250_000_000}]}
        self.assertEqual(
            SessionSegmenter().assign_group(straddler)["session_phase"], POST_SETTLEMENT
        )

    def test_precomputed_trade_date_helpers_agree_with_the_single_argument_ones(self):
        """The streaming path resolves the trade date once and passes it down; that shortcut
        must not be able to drift from the standalone functions."""
        for at in (FRIDAY_CLOSE_1001, WITHDRAWAL_1004, WITHDRAWAL_1005,
                   ns("2021-10-02T17:00:00Z"), ns("2021-10-04T18:29:00Z")):
            with self.subTest(at=at):
                day = trade_day(at)
                self.assertEqual(phase_within(at, day), session_phase(at))
                self.assertEqual(segment_of(day), continuity_segment(at))

    def test_segment_stream_is_lazy(self):
        """4.26M groups must not be materialized into a list."""
        import types
        out = segment_stream(iter([group(WITHDRAWAL_1004)]))
        self.assertIsInstance(out, types.GeneratorType)
        self.assertEqual([row["trade_day"] for row in out], ["20211004"])


if __name__ == "__main__":
    unittest.main()


class ExchangeHolidayCalendarTests(unittest.TestCase):
    """The CME trading-day schedule (Greg, 2026-08-29: 'we follow cme trading day schedule').

    Every expectation here is an exchange fact, never a property of our tape.
    """

    def test_full_closure_is_not_a_trading_day(self):
        # Good Friday 2026-04-03 and Christmas 2026-12-25: no Globex session at all.
        self.assertFalse(native_session.is_trading_day(date(2026, 4, 3)))
        self.assertFalse(native_session.is_trading_day(date(2026, 12, 25)))

    def test_partial_and_early_close_remain_trading_days(self):
        # A partial session is NOT a business day for settlement counting, but the book
        # opens, so it IS a trade date. Conflating the two would move segments by a day.
        self.assertTrue(native_session.is_trading_day(date(2026, 1, 19)))   # MLK, partial
        self.assertTrue(native_session.is_trading_day(date(2026, 11, 27)))  # day after TG
        self.assertEqual(
            native_session.holiday_class(date(2026, 1, 19)), native_session.PARTIAL_SESSION
        )
        self.assertEqual(
            native_session.holiday_class(date(2026, 11, 27)), native_session.EARLY_CLOSE
        )

    def test_ordinary_day_has_no_holiday_class(self):
        self.assertIsNone(native_session.holiday_class(date(2021, 10, 4)))

    def test_trade_day_skips_a_full_closure(self):
        # 10:00 CT on Good Friday 2026-04-03 is inside no session; the next trade date is
        # Monday the 6th, reached by the same loop that skips the weekend.
        ts = native_session._local_instant_ns(date(2026, 4, 3), time(10, 0))
        self.assertEqual(native_session.trade_day(ts), date(2026, 4, 6))

    def test_christmas_evening_reopen_carries_the_next_trade_date(self):
        # Christmas 2024-12-25 was a Wednesday full closure whose 17:00 CT reopen belongs to
        # the 26th. This must fall out of the existing reopen rule, not a holiday clause.
        ts = native_session._local_instant_ns(date(2024, 12, 25), time(18, 0))
        self.assertEqual(native_session.trade_day(ts), date(2024, 12, 26))

    def test_phase_refuses_on_a_shortened_session(self):
        # No source records the shortened close time, and a partial session has no
        # settlement cycle. Answering from ordinary hours would be plausible and wrong.
        mlk = date(2026, 1, 19)
        ts = native_session._local_instant_ns(mlk, time(10, 0))
        with self.assertRaises(native_session.SessionError) as caught:
            native_session.phase_within(ts, mlk)
        self.assertIn("partial_session", str(caught.exception))

    def test_roster_window_is_unaffected(self):
        # The launch roster spans 2021-10-01..10-05 and contains no holiday, so nothing
        # here changes any value the run actually uses.
        for dom in (1, 2, 3, 4, 5):
            self.assertIsNone(native_session.holiday_class(date(2021, 10, dom)))
        ts = native_session._local_instant_ns(date(2021, 10, 4), time(10, 0))
        self.assertEqual(native_session.trade_day(ts), date(2021, 10, 4))
        self.assertEqual(
            native_session.phase_within(ts, date(2021, 10, 4)),
            native_session.PRE_SETTLEMENT,
        )
