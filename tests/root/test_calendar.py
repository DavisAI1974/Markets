"""The trade-day calendar, on real dates."""
import datetime as dt

from root.calendar import parse_trade_day, to_ns, trade_day_bounds


def utc(*a):
    return to_ns(dt.datetime(*a, tzinfo=dt.timezone.utc))


def test_trade_day_in_daylight_time():
    # Trade day Monday Oct 2, 2023: 6 pm Eastern Sunday Oct 1 (22:00 UTC) to 5 pm Eastern Monday (21:00 UTC).
    assert trade_day_bounds(dt.date(2023, 10, 2)) == (utc(2023, 10, 1, 22), utc(2023, 10, 2, 21))


def test_trade_day_in_standard_time():
    assert trade_day_bounds(dt.date(2024, 1, 9)) == (utc(2024, 1, 8, 23), utc(2024, 1, 9, 22))


def test_the_five_to_six_stretch_belongs_to_no_trade_day():
    _, halt = trade_day_bounds(dt.date(2023, 10, 2))
    opens, _ = trade_day_bounds(dt.date(2023, 10, 3))
    assert opens - halt == 3600 * 10 ** 9


def test_parse_trade_day():
    assert parse_trade_day('20231017') == parse_trade_day('2023-10-17') == dt.date(2023, 10, 17)
