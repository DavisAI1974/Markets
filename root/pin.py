"""ROOT `pin`: section G of a row. The 13 outside data points, pinned onto every tick row.

Specification: SPEC-outside.md (approved by Greg, 2026-11-16), "What it produces" item 2, and SPEC-root.md section G
and criterion 7. The values come from the tables `root/outside.py` makes (markets-data
`data/outside/ng_oct2023/made/`), each checked against its fingerprint in that folder's receipt before it is read.

How a value gets onto a row:
- Most figures: the latest value that had become known at or before the row's RECEIVED time. A value holds until the
  next one replaces it. Each such group carries its own `..._known_from_ns` column, so the row itself shows when the
  value it carries became known.
- The figures made once per trade day (the forecast X02, the disagreement between models X09, the sessions since
  the front contract expired X06): on every row of that trade day, known from its open, and EMPTY on a row that
  belongs to no trade day (the 5 pm to 6 pm stretches, the Sunday start-up).
A row is pinned by what the row itself says (its received time and its trade-day label), never by which box wrote
it, so a stretch written by two boxes comes out the same in both. Nothing from a later tick is used.
An empty value is None: never 0 and never blank text.
"""
from __future__ import annotations

import bisect
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path

from root.outside import CITY_WEIGHTS, UNWEIGHTED_CITIES

SECTION = 'G. The 13 outside data points'
WHOLE, DECIMAL, WORDS = 'whole number', 'decimal', 'text'
DEFAULT_TABLES = Path(os.environ.get('MARKETS_DATA', '../markets-data')) / 'data' / 'outside' / 'ng_oct2023' / 'made'
NYMEX_GAS, ICE_HENRY_HUB = '023651', '023391'       # CFTC contract codes, as in the original (labels, not numbers)
FORECAST_FIGURES = (('GFS D+0', 'gfs_today'), ('NAM D+0', 'nam_today'), ('GFS D+1', 'gfs_next_day'),
                    ('MEX D+3', 'extended_gfs_three_days_on'))
USED = 'yes'


def _positioning(point: str, name: str, code: str, three_year: bool) -> dict:
    fields = [
        (f'{point}_{name}_report_date', 'report_date', WORDS, 'The date of the weekly positioning report on this row.'),
        (f'{point}_{name}_funds_long', 'managed_money_long', WHOLE, 'Managed-money long contracts, as published.'),
        (f'{point}_{name}_funds_short', 'managed_money_short', WHOLE, 'Managed-money short contracts, as published.'),
        (f'{point}_{name}_funds_net', 'managed_money_net', WHOLE, 'Long minus short.'),
        (f'{point}_{name}_net_standing_1y', 'standing_1y', DECIMAL, 'Where this net stands among the reports of the '
         'last year, in percent.'),
        (f'{point}_{name}_reports_in_1y', 'reports_in_1y', WHOLE, 'How many reports that one-year standing rests on.'),
    ]
    if three_year:
        fields += [
            ('x03_nymex_net_change_on_week', 'net_change_on_week', WHOLE, 'This report\'s net minus the report '
             'before.'),
            ('x04_nymex_net_standing_3y', 'standing_3y', DECIMAL, 'Where this net stands among the reports of the last '
             'three years, in percent.'),
            ('x04_nymex_reports_in_3y', 'reports_in_3y', WHOLE, 'How many reports that three-year standing rests on.'),
        ]
    return dict(table='positioning.csv', where=('contract_code', code), known=f'{point}_{name}_known_from_ns',
                fields=fields)


def _shape(kind: str, table: str, what: str) -> dict:
    p = f'x13_curve_{kind}'
    return dict(table=table, where=None, known=f'{p}_known_from_ns', fields=[
        (f'{p}_front_symbol', 'front_symbol', WORDS, f'The front contract month of the curve from {what}.'),
        (f'{p}_next_symbol', 'next_symbol', WORDS, 'The next contract month that has a price.'),
        (f'{p}_front', 'front', DECIMAL, 'The front month price, dollars.'),
        (f'{p}_next', 'next', DECIMAL, 'The next month price, dollars.'),
        (f'{p}_far', 'far', DECIMAL, 'The far month price, dollars.'),
        (f'{p}_far_rank', 'far_rank', WHOLE, 'Which month, counted from the front, the far month is.'),
        (f'{p}_slope_to_next', 'slope_to_next', DECIMAL, 'Next month minus front month.'),
        (f'{p}_slope_to_far', 'slope_to_far', DECIMAL, 'Far month minus front month.'),
        (f'{p}_curvature', 'curvature', DECIMAL, 'The middle month against the line from front to far, as in the '
         'original.'),
        (f'{p}_front_minus_next', 'front_minus_next', DECIMAL, 'Front month minus next month.'),
        (f'{p}_regime', 'regime', WORDS, 'Contango or backwardation, by the sign of front minus next.'),
        (f'{p}_months_priced', 'months_priced', WHOLE, 'How many of the nearest contract months had a price.'),
    ])


# Figures taken as the latest value known at or before the row's received time.
AS_OF = [
    _positioning('x01', 'nymex', NYMEX_GAS, True),
    _positioning('x08', 'ice', ICE_HENRY_HUB, False),
    dict(table='grid_us48.csv', where=None, known='x05_x07_grid_known_from_ns', fields=[
        ('x05_x07_grid_hour_utc', 'period_utc', WORDS, 'The hour (UTC) the grid figures on this row are for.'),
        ('x05_us48_wind_mwh', 'wind_mwh', DECIMAL, 'US48 wind generation in that hour, megawatt-hours.'),
        ('x07_us48_gas_mwh', 'gas_mwh', DECIMAL, 'US48 generation from natural gas in that hour, megawatt-hours.'),
        ('x07_gas_burn_estimate_bcfd', 'est_gas_burn_bcfd_rate', DECIMAL, 'Gas burned for power, estimated from the '
         'gas generation of that hour as a daily rate (an estimate; the conversion is declared).'),
    ]),
    dict(table='weather_gas_day.csv', where=None, known='x10_gas_day_known_from_ns', fields=[
        ('x10_gas_day', 'gas_day', WORDS, 'The latest finished gas day (10 am Eastern to 10 am Eastern), by the date '
         'it starts.'),
        ('x10_gas_weighted_hdd', 'gw_hdd', DECIMAL, 'Observed gas-weighted heating degree days of that gas day.'),
        ('x10_gas_weighted_cdd', 'gw_cdd', DECIMAL, 'Observed gas-weighted cooling degree days of that gas day.'),
        ('x10_gas_weighted_precip_in', 'gw_precip_in', DECIMAL, 'Gas-weighted precipitation of that gas day, inches.'),
        ('x10_gas_weighted_wind_knots', 'gw_wind_knots', DECIMAL, 'Gas-weighted wind speed of that gas day, knots.'),
        ('x10_hdd_one_gas_day_before', 'gw_hdd_1_gas_days_before', DECIMAL, 'Carry-over: the heating degree days of '
         'the gas day before.'),
        ('x10_hdd_two_gas_days_before', 'gw_hdd_2_gas_days_before', DECIMAL, 'Carry-over: the heating degree days '
         'two gas days before.'),
        ('x10_cities_present', 'cities_present', WHOLE, 'How many of the 16 weighted cities had readings.'),
        ('x10_weight_covered', 'weight_covered', DECIMAL, 'The share of the weights those cities carry.'),
        ('x10_cities_missing', 'cities_missing', WORDS, 'The weighted cities with no reading that gas day.'),
    ]),
    dict(table='storage_weekly.csv', where=None, known='x11_storage_known_from_ns', fields=[
        ('x11_storage_week_ending', 'week_ending', WORDS, 'The week the storage report on this row is for.'),
        ('x11_storage_level_first_print_bcf', 'level_first_print_bcf', DECIMAL, 'Gas in storage as first printed, '
         'billion cubic feet.'),
        ('x11_storage_change_bcf', 'change_from_first_prints_bcf', DECIMAL, 'This first print minus the first print '
         'of the week before.'),
        ('x11_storage_vs_5yr_bcf', 'vs_5yr_bcf', DECIMAL, 'The level minus the mean of the same week in the five '
         'years before.'),
        ('x11_storage_vs_5yr_rule', 'vs_5yr_rule', WORDS, 'Which rule made the five-year comparison.'),
        ('x11_storage_prior_5y_levels', 'same_week_prior_5y_levels', WORDS, 'The five prior-year levels it used.'),
    ]),
    dict(table='storage_estimate.csv', where=None, known='x12_estimate_known_from_ns', fields=[
        ('x12_estimate_week_ending', 'week_ending', WORDS, 'The week the estimate row is for.'),
        ('x12_street_estimate_bcf', 'estimate_bcf', DECIMAL, 'The street estimate of the weekly change.'),
        ('x12_actual_change_bcf', 'actual_change_from_first_prints_bcf', DECIMAL, 'The actual weekly change, from '
         'first prints.'),
        ('x12_surprise_bcf', 'surprise_bcf', DECIMAL, 'Actual minus estimate.'),
        ('x12_estimate_missing_reason', 'estimate_missing_reason', WORDS, 'Why the estimate is empty, when it is.'),
    ]),
    _shape('settled', 'curve_settled_shape.csv', 'settlement prices'),
    _shape('traded', 'curve_traded_shape.csv.gz', 'last trades'),
]
AS_OF += [dict(table='weather_hourly_city.csv', where=('city', city), known=f'x10_temp_{city.lower()}_known_from_ns',
               fields=[(f'x10_temp_f_{city.lower()}', 'tmpf', DECIMAL, f'The latest routine hourly temperature '
                        f'reading for {city}, Fahrenheit. It holds until the next reading is known; a missing hour '
                        f'stays missing, so check the known-from time beside it.')])
          for city in list(CITY_WEIGHTS) + list(UNWEIGHTED_CITIES)]

# Figures made once per trade day: on every row of that trade day, empty on a row of no trade day.
DAY_KNOWN = 'x02_x06_x09_known_from_ns'
PER_TRADE_DAY = [
    dict(table='expiry.csv', where=None, pick=None, fields=[
        ('x06_sessions_since_front_expiry', 'sessions_since_front_expiry', WHOLE, 'Trading sessions since the front '
         'contract last expired.'),
        ('x06_last_expired_symbol', 'last_expired_symbol', WORDS, 'The contract that last expired.'),
        ('x06_last_expiry_date', 'last_expiry_date', WORDS, 'The date it expired.'),
    ]),
    dict(table='forecast_disagreement.csv', where=('used_on_rows', USED), pick=None, fields=[
        ('x09_models_run_utc', 'runtime_utc', WORDS, 'The model run (shared by GFS and NAM) the disagreement is '
         'taken from: the last one known before the trade day opened.'),
        ('x09_models_largest_gap_hdd', 'max_abs_spread_gw_hdd', DECIMAL, 'The largest gap between GFS and NAM in '
         'gas-weighted heating degree days over the days forecast.'),
        ('x09_models_gap_at_days_ahead', 'at_horizon_days', WHOLE, 'How many days ahead that largest gap is.'),
        ('x09_models_gap_by_days_ahead', 'spreads_by_horizon', WORDS, 'Every gap underneath: [days ahead, GFS minus '
         'NAM, cities].'),
    ]),
]
PER_TRADE_DAY += [dict(table='forecast_on_row.csv', where=('figure', figure), pick=figure, fields=[
    (f'x02_forecast_{name}_hdd', 'gw_hdd', DECIMAL, f'Forecast gas-weighted heating degree days, {figure} (model and '
     f'days ahead of the trade day\'s date), from the last run known before the trade day opened.'),
    (f'x02_forecast_{name}_run_utc', 'runtime_utc_used', WORDS, 'The model run it came from.'),
    (f'x02_forecast_{name}_cities', 'cities_high_low_hdd', WORDS, 'Underneath: each city as city|forecast '
     'high|forecast low|heating degree days, cities separated by ;'),
    (f'x02_forecast_{name}_empty_reason', 'empty_reason', WORDS, 'Why the figure is empty, when it is.'),
]) for figure, name in FORECAST_FIGURES]

COLUMNS = []
for _g in AS_OF:
    COLUMNS.append((SECTION, _g['known'], 'When the figures beside it became known (UTC nanoseconds): at or before '
                    'this row\'s received time.', WHOLE))
    COLUMNS += [(SECTION, name, what, kind) for name, _, kind, what in _g['fields']]
COLUMNS.append((SECTION, DAY_KNOWN, 'When the once-per-trade-day figures (forecast, disagreement between models, '
                'sessions since expiry) became known: the open of this row\'s trade day. Empty with them on a row '
                'of no trade day.', WHOLE))
for _g in PER_TRADE_DAY:
    COLUMNS += [(SECTION, name, what, kind) for name, _, kind, what in _g['fields']]
NAMES = [name for _, name, _, _ in COLUMNS]
TEXT = {name for _, name, _, kind in COLUMNS if kind == WORDS}
DECIMALS = {name for _, name, _, kind in COLUMNS if kind == DECIMAL}


def convert(text: str, kind: str):
    """A table cell as a value: empty stays empty (None), never 0 and never blank text."""
    if text == '':
        return None
    return text if kind == WORDS else int(text) if kind == WHOLE else float(text)


def read_table(folder: Path, name: str, fingerprint: str | None = None) -> list[dict]:
    """Every row of one made table, in the table's own order. With a fingerprint, the file is refused if it differs."""
    raw = (Path(folder) / name).read_bytes()
    if fingerprint is not None and hashlib.sha256(raw).hexdigest() != fingerprint:
        raise ValueError(f'{name} differs from its fingerprint in the outside receipt; refusing to read it')
    text = (gzip.decompress(raw) if name.endswith('.gz') else raw).decode()
    return list(csv.DictReader(io.StringIO(text)))


def chosen(rows: list[dict], where) -> list[dict]:
    return rows if where is None else [r for r in rows if r[where[0]] == where[1]]


class Pins:
    """The made tables, ready to give section G of any row. `at(received_ns, trade_day)` is section G in COLUMNS
    order; `trade_day` is the row's own trade-day label ('YYYY-MM-DD') or None on a stretch or start-up row."""

    def __init__(self, folder: Path = DEFAULT_TABLES):
        self.folder = Path(folder)
        receipt = json.loads((self.folder / 'RECEIPT.json').read_text())
        self.cut = receipt['cut_ns']
        prints = {t['table']: t['sha256'] for t in receipt['tables']}
        self.tables_read = {}
        tables = {}

        def table(name):
            if name not in tables:
                tables[name] = read_table(self.folder, name, prints[name])
                self.tables_read[name] = prints[name]
            return tables[name]

        self.groups = []                      # (known times, the values at each, how many columns)
        for g in AS_OF:
            rows = chosen(table(g['table']), g['where'])
            known = [int(r['known_from_ns']) for r in rows]
            if known != sorted(known):
                raise ValueError(f"{g['table']} is not in the order its values became known")
            values = [[int(r['known_from_ns'])] + [convert(r[col], kind) for _, col, kind, _ in g['fields']]
                      for r in rows]
            self.groups.append((known, values, [None] * len(values[0])))
        self.by_day, opens = {}, {}
        for g in PER_TRADE_DAY:
            for r in chosen(table(g['table']), g['where']):
                day = r['trade_day']
                if g['pick'] is not None:      # a forecast figure is known from the open, like the expiry count
                    if int(r['known_from_ns']) != opens[day]:
                        raise ValueError(f"{g['table']}: {day} is not stamped at the trade day's open")
                elif g['table'] == 'expiry.csv':
                    opens[day] = int(r['known_from_ns'])
                elif int(r['known_from_ns']) > opens[day]:
                    raise ValueError(f"{g['table']}: the value for {day} was not known at the open")
                self.by_day.setdefault(day, [opens[day]]).extend(convert(r[col], kind) for _, col, kind, _ in
                                                                 g['fields'])
        width = len(NAMES) - sum(len(empty) for _, _, empty in self.groups)
        for day, values in self.by_day.items():
            if len(values) != width:
                raise ValueError(f'the once-per-trade-day figures of {day} are not complete')
        self.no_day = [None] * width
        self.held, self.held_from, self.held_to = None, None, None

    def at(self, received_ns: int, trade_day: str | None) -> list:
        if received_ns >= self.cut:
            raise ValueError(f'a row received at {received_ns} is past what the outside tables hold ({self.cut})')
        if self.held is None or not self.held_from <= received_ns < self.held_to:
            out, start, end = [], None, self.cut
            for known, values, empty in self.groups:
                k = bisect.bisect_right(known, received_ns)
                if k:
                    out += values[k - 1]
                    start = known[k - 1] if start is None else max(start, known[k - 1])
                else:
                    out += empty
                if k < len(known):
                    end = min(end, known[k])
            # held for every received time from the newest value in use up to the next value of any group
            self.held, self.held_from, self.held_to = out, (received_ns if start is None else start), end
        return self.held + (self.no_day if trade_day is None else self.by_day[trade_day])
