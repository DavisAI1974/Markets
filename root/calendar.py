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


# ---------------------------------------------------------------- labels, the week, the files a trade day needs
TRADE_DAY = 'trade day'
STRETCH = '5 pm to 6 pm stretch'
STARTUP = 'Sunday start-up'
SUNDAY = 6                               # weekday number of Sunday (Monday = 0)
FIRST_TRADE_WEEKDAY, LAST_TRADE_WEEKDAY = 0, 4    # trade days are Monday to Friday


def label(exchange_ns: int) -> tuple[str, dt.date | None]:
    """The label of a moment, decided by exchange time (SPEC-root.md assumption 1): (trade day, its date), the 5 pm
    to 6 pm stretch (None), or the exchange's Sunday start-up before 5 pm Sunday (None). Refuses a moment that would
    belong to a Saturday or Sunday trade day: there are none."""
    moment = dt.datetime.fromtimestamp(exchange_ns // NS_PER_SECOND, tz=dt.timezone.utc).astimezone(EASTERN)
    moment = moment.replace(microsecond=0)
    wall = moment.timetz().replace(tzinfo=None)
    if HALT_EASTERN <= wall < OPEN_EASTERN:
        return STRETCH, None
    if moment.weekday() == SUNDAY and wall < HALT_EASTERN:
        return STARTUP, None
    day = moment.date() + dt.timedelta(days=1) if wall >= OPEN_EASTERN else moment.date()
    if not FIRST_TRADE_WEEKDAY <= day.weekday() <= LAST_TRADE_WEEKDAY:
        raise ValueError(f'{moment.isoformat()} would belong to trade day {day}, which is not a weekday')
    return TRADE_DAY, day


def week_sunday(trade_day: dt.date) -> dt.date:
    """The Sunday whose start-up opens the week of a trade day (the book is the week, seated at that start-up)."""
    if not FIRST_TRADE_WEEKDAY <= trade_day.weekday() <= LAST_TRADE_WEEKDAY:
        raise ValueError(f'{trade_day} is not a trade day')
    return trade_day - dt.timedelta(days=trade_day.weekday() + 1)


def clock_days_needed(trade_day: dt.date) -> list[dt.date]:
    """The UTC clock days whose raw files a trade day needs: from its week's Sunday through the UTC clock day that
    holds 6 pm Eastern on the trade day's date (the end of the stretch after it)."""
    start = week_sunday(trade_day)
    end_ns = to_ns(eastern(trade_day, OPEN_EASTERN))
    end = dt.datetime.fromtimestamp(end_ns // NS_PER_SECOND, tz=dt.timezone.utc).date()
    return [start + dt.timedelta(days=k) for k in range((end - start).days + 1)]
