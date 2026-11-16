"""The exchange's times for ROOT: the trade day, the 5 pm to 6 pm Eastern stretch, the settlement window.

A TRADE DAY runs 6:00 pm Eastern the evening before to 5:00 pm Eastern on the named date. Tuesday's trade day is
6 pm Monday to 5 pm Tuesday. The hour from 5 pm to 6 pm Eastern belongs to no trade day; it is its own marked stretch.
Times are UTC nanoseconds. Eastern time is taken from the IANA zone, so daylight and standard time are both right.
Every number here is declared in root/DECLARED_CONSTANTS.md.
"""
from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo('America/New_York')
OPEN_EASTERN = dt.time(18, 0)            # the trade day opens 6:00 pm Eastern the evening before
HALT_EASTERN = dt.time(17, 0)            # and halts 5:00 pm Eastern on the named date
SETTLE_FROM_EASTERN = dt.time(14, 28)    # NYMEX natural gas settlement window, 2:28 pm
SETTLE_TO_EASTERN = dt.time(14, 30)      # to 2:30 pm Eastern

NS_PER_SECOND = 10 ** 9


def to_ns(moment: dt.datetime) -> int:
    """UTC nanoseconds of a time-zone-aware moment (exact; no float)."""
    if moment.tzinfo is None:
        raise ValueError('a moment without a time zone has no defined UTC time')
    epoch = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    delta = moment - epoch
    return (delta.days * 86400 + delta.seconds) * NS_PER_SECOND + delta.microseconds * 1000


def eastern(day: dt.date, at: dt.time) -> dt.datetime:
    return dt.datetime.combine(day, at, tzinfo=EASTERN)


def trade_day_bounds(trade_day: dt.date) -> tuple[int, int]:
    """[open, halt) of a trade day in UTC nanoseconds: 6 pm Eastern the evening before to 5 pm Eastern."""
    opens = eastern(trade_day - dt.timedelta(days=1), OPEN_EASTERN)
    halts = eastern(trade_day, HALT_EASTERN)
    return to_ns(opens), to_ns(halts)


def eastern_text(ns: int) -> str:
    """A UTC nanosecond time written in Eastern time, to the second, with its offset (a label, never an input)."""
    moment = dt.datetime.fromtimestamp(ns // NS_PER_SECOND, tz=dt.timezone.utc).astimezone(EASTERN)
    return moment.isoformat()


def parse_trade_day(text: str) -> dt.date:
    """A trade day written YYYYMMDD or YYYY-MM-DD."""
    text = text.replace('-', '')
    return dt.date(int(text[:4]), int(text[4:6]), int(text[6:8]))
