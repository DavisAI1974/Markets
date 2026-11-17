"""Checks of ROOT's `pin` part (section G) on the real made tables. No made-up data. The check of every stored row
(criterion 7) is `root.checks.pinned`, run inside every build; these read the tables only."""
import datetime as dt
import os
from pathlib import Path

import pytest

from root import pin
from root.calendar import HALT_EASTERN, eastern, to_ns

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get('MARKETS_DATA', REPO.parent / 'markets-data'))
MADE = DATA / 'data' / 'outside' / 'ng_oct2023' / 'made'
pytestmark = pytest.mark.skipif(not (MADE / 'RECEIPT.json').exists(), reason=f'the made tables are not at {MADE}')


def test_the_reports_the_four_trade_days_carry():
    """SPEC-outside.md: trade days Oct 2 and 3 carry the storage week ending Sep 22 and the positioning report dated
    Sep 26; Oct 17 and 18 carry the week ending Oct 6 and the report dated Oct 10. The expiry count is 3, 4, 14, 15."""
    pins = pin.Pins(MADE)
    i = {name: k for k, name in enumerate(pin.NAMES)}
    want = {'2023-10-02': ('2023-09-22', '2023-09-26', 3), '2023-10-03': ('2023-09-22', '2023-09-26', 4),
            '2023-10-17': ('2023-10-06', '2023-10-10', 14), '2023-10-18': ('2023-10-06', '2023-10-10', 15)}
    for day, (week, report, sessions) in want.items():
        g = pins.at(to_ns(eastern(dt.date.fromisoformat(day), dt.time(12))), day)
        assert (g[i['x11_storage_week_ending']], g[i['x01_nymex_report_date']],
                g[i['x06_sessions_since_front_expiry']]) == (week, report, sessions)


def test_a_row_of_no_trade_day_has_no_once_per_trade_day_figure_and_a_late_row_is_refused():
    pins = pin.Pins(MADE)
    stretch = to_ns(eastern(dt.date(2023, 10, 2), HALT_EASTERN))
    g = dict(zip(pin.NAMES, pins.at(stretch, None)))
    assert g[pin.DAY_KNOWN] is None and g['x06_sessions_since_front_expiry'] is None
    assert g['x02_forecast_gfs_today_hdd'] is None and g['x11_storage_week_ending'] == '2023-09-22'
    with pytest.raises(ValueError):
        pins.at(pins.cut, None)
