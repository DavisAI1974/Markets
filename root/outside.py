"""ROOT `outside` part: the 13 outside data points for the four trade days, made from the published source files.

Specification: markets-data `.../root-redesign-20261116/SPEC-outside.md` (approved by Greg, 2026-11-16). The 13 are
the same as in the original files (Markets 7f34afa: frankie_day_external.py and the feeds it called), with four fixes
and kept simple for this first ROOT part. Every formula carried from the original names it.

This module makes one plain table per point, each row with the time its value became known (`known_from_ns`, UTC
nanoseconds; `known_from_eastern` is the same time written in Eastern time, a label only). Pinning the values onto
the tick rows is done later from these same tables: at a tick, the latest row known at or before the tick's received
time. Nothing is estimated or filled in: a value that cannot be made is empty and its reason is in the receipt.

Changed 2026-11-17 on Greg's word ("take out all.of the other averages"; "ZERO WINDOWS"; "The temp changes are what
drive market price in rt markets!! We have hourly temps available for each day. Use them"): no fund standing over a
window; no gas-day temperature, degree day, wind or rain figure (the gas day is a label on each reading); no forecast
high-low midpoint (every run, every forecast hour); the storage five-year comparison stays in its table as
information only and never goes on a row or into a calculation.

Inputs: the source folder `data/outside/ng_oct2023/` of markets-data, every file checked against its MANIFEST.json
fingerprint before it is read.

    python3 -m root.outside --src <markets-data>/data/outside/ng_oct2023 --out <dir>
"""
from __future__ import annotations

import argparse
import bisect
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import re
import zipfile
from collections import defaultdict
from pathlib import Path

from root.calendar import (EASTERN, OPEN_EASTERN, eastern, eastern_text, parse_trade_day, to_ns,
                           trade_day_bounds)

# ---------------------------------------------------------------- declared constants (root/DECLARED_CONSTANTS.md)
TRADE_DAYS = ('2023-10-02', '2023-10-03', '2023-10-17', '2023-10-18')
NS_PER_SECOND = 10 ** 9
NS_PER_MINUTE = 60 * NS_PER_SECOND
DAYS_PER_WEEK = 7
MONTHS_PER_YEAR = 12
FRIDAY, SATURDAY, SUNDAY = 4, 5, 6                     # weekday numbers (Monday = 0)
GZIP_LEVEL = 9
NS_PER_HOUR = 60 * NS_PER_MINUTE

# Positioning (cot_feed.py).
POSITIONING_CODES = ('023651', '023391', '023392', '0233AG', '0233AH')
WEEK_STEP_MIN_DAYS, WEEK_STEP_MAX_DAYS = 5, 10        # the change on the week only against a normal weekly step
FEDERAL_HOLIDAY_JUNETEENTH_FROM = 2021                 # Juneteenth is a federal holiday from 2021
POSITIONING_RELEASE_EASTERN = dt.time(15, 30)          # Friday after the report date, 3:30 pm Eastern

# Weather (nws_temp_feed.py): the 16 cities and their weights, and two unweighted cities shown on the row.
CITY_WEIGHTS = {'NYC': 0.12, 'BOS': 0.05, 'PHL': 0.05, 'DCA': 0.05, 'ORD': 0.10, 'DTW': 0.05, 'MSP': 0.045,
                'STL': 0.035, 'IAH': 0.07, 'DFW': 0.065, 'ATL': 0.055, 'DEN': 0.035, 'PHX': 0.045, 'LAX': 0.055,
                'SFO': 0.03, 'SEA': 0.035}
TOTAL_RAW_WEIGHT = sum(CITY_WEIGHTS.values())
CITY_SHARE = {c: w / TOTAL_RAW_WEIGHT for c, w in CITY_WEIGHTS.items()}    # nws_temp_feed.station_weights: sum to 1
UNWEIGHTED_CITIES = ('AUS', 'SAT')
DEGREE_DAY_BASE_F = 65.0
READING_LAG_NS = 10 * NS_PER_MINUTE                    # a station reading is public 10 minutes after its time
READINGS_LOOKBACK_NS = 72 * NS_PER_HOUR                # readings kept from 72 hours before each trade day opens
GAS_DAY_START_EASTERN = dt.time(10, 0)                 # fix 3: the gas day runs 10 am Eastern to 10 am Eastern
TRACE_PRECIP_IN = 0.001                                # a trace of rain counts 0.001 inch, as nws_temp_feed
FORECAST_TZ = 'America/Chicago'                        # the original forecast describes the calendar date in Central
FORECAST_LAG_NS = int(4.5 * NS_PER_HOUR)               # a model run is public 4.5 hours after it starts
FORECAST_POINTS = {'GFS': 21, 'NAM': 21, 'MEX': 15}   # forecast hours each model's run gives (product facts; checked)

# Grid (grid_stack / frankie_day_external.py).
GRID_LAG_NS = 2 * NS_PER_HOUR                          # an hour's figure is public 2 hours after its stamp
HOURS_PER_DAY = 24
HEAT_RATE_BTU_PER_KWH = 7900                           # gas burn estimate: MWh x 24 x 7,900 / 1.035e9 (grid_stack's
GAS_BURN_DIVISOR = 1.035e9                             # stated method; an estimate, named so in the table)

# Contract calendar (flow_calendar.py).
NG_LAST_TRADE_BUSINESS_DAYS = 3                        # NG expires 3 business days before the delivery month
MONTH_CODES = 'FGHJKMNQUVXZ'
EXPIRY_SEARCH_MONTHS_AHEAD = 2                         # flow_calendar: look from two delivery months ahead, stepping back

# Curve (frankie_day_external.py, forward_curve.py).
UNDEFINED_PRICE = 2 ** 63 - 1
PRICE_SCALE = 10 ** 9
SETTLEMENT_STAT_TYPE = 3
CURVE_MONTHS = 12
OUTRIGHT = re.compile(r'^NG[FGHJKMNQUVXZ]\d{1,2}$')
SHAPE_NEEDS_MONTHS = 2                                 # forward_curve: no shape without the front two months
TWO_DIGIT_YEAR = 100

# Storage (frankie_day_external.py storage / estimate; fix 1 and fix 2).
STORAGE_RELEASE_EASTERN = dt.time(10, 30)              # the weekly storage report: Thursday 10:30 am Eastern (rule)
STORAGE_RELEASE_DAYS_AFTER_WEEK = 6                    # the Thursday after the week ending Friday
FIVE_YEAR_PRIOR_YEARS = 5                              # the same week in each of the five prior calendar years
STORAGE_TOTAL = 'Total Lower 48'                       # the column labels read from the EIA workbooks
STORAGE_WEEK = 'Week ending'
STORAGE_REGIONS = ('East Region', 'Midwest Region', 'Mountain Region', 'Pacific Region', 'South Central Region',
                   'Salt', 'NonSalt')
STORAGE_NOTE = 'Explanation'
STORAGE_HISTORY_SHEET = 'html_report_history'
STORAGE_CHANGES_SHEET = 'weekly_net_changes'
ESTIMATE_MISSING = ('the street estimate is on saved web pages (web.archive.org), which the cloud environment cannot '
                    'reach; left for the later update (SPEC-outside.md, kept simple)')


def rows_end(trade_day: dt.date) -> int:
    """The end of the rows written for a trade day: 6 pm Eastern on its date, the end of the 5 pm to 6 pm stretch that
    follows it. The tables hold every value known before this moment and nothing from after it; a row received at or
    after it is refused by the pinning (root.pin), never given a stale value."""
    return to_ns(eastern(trade_day, OPEN_EASTERN))


def clock_day_of(stored: str) -> dt.date:
    return dt.datetime.strptime(stored.rsplit('_', 1)[1][:8], '%Y%m%d').date()


def held_blocks(clock_days) -> dict:
    """Number the runs of held clock-day files that follow on from each other (the next calendar day, or Friday to
    Sunday). Last prices are not carried across a gap: a month enters again when it next has a price."""
    block, out, prev = 0, {}, None
    for d in sorted(set(clock_days)):
        if prev is not None and not (d - prev == dt.timedelta(days=1) or (prev.weekday() == FRIDAY and
                                                                           d.weekday() == SUNDAY)):
            block += 1
        out[d], prev = block, d
    return out


# ---------------------------------------------------------------- reading the source files
class Sources:
    """The source folder with its manifest. Every read checks the stored file's fingerprint first."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.manifest = json.loads((self.folder / 'MANIFEST.json').read_text())
        self.by_path = {f['stored']: f for f in self.manifest['files']}
        self.read_log = []

    def bytes(self, stored: str) -> bytes:
        entry = self.by_path.get(stored)
        if entry is None:
            raise FileNotFoundError(f'{stored} is not in the source manifest')
        raw = (self.folder / stored).read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry['stored_sha256']:
            raise ValueError(f'{stored} differs from its fingerprint in the source manifest; refusing to read it')
        self.read_log.append(dict(stored=stored, sha256=entry['stored_sha256']))
        return gzip.decompress(raw) if entry['stored_as'].startswith('gzip') else raw

    def text(self, stored: str) -> str:
        return self.bytes(stored).decode('utf-8', 'replace')

    def listed(self, prefix: str) -> list[str]:
        return sorted(p for p in self.by_path if p.startswith(prefix))


KNOWN_COLUMNS = ['known_from_ns', 'known_from_eastern']


def known_cols(ns: int) -> list:
    return [ns, eastern_text(ns)]


def utc_ns(text: str, fmt: str) -> int:
    return to_ns(dt.datetime.strptime(text, fmt).replace(tzinfo=dt.timezone.utc))


def number(text):
    """A published number, or None when the source has none (never 0)."""
    if text is None:
        return None
    s = str(text).strip().replace(',', '')
    if s in ('', 'M', '.', 'na', 'n/a', 'None'):
        return None
    try:
        return float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------- X01, X03, X04, X08: positioning
def us_federal_holidays(year: int) -> set:
    """Observed US federal holidays (cot_feed.us_federal_holidays)."""
    def nth(month, weekday, n):
        if n > 0:
            d = dt.date(year, month, 1)
            return d + dt.timedelta(days=(weekday - d.weekday()) % 7 + 7 * (n - 1))
        d = dt.date(year, month, 28)
        while (d + dt.timedelta(days=7)).month == month:
            d += dt.timedelta(days=7)
        return d - dt.timedelta(days=(d.weekday() - weekday) % 7)

    def observed(d):
        return d - dt.timedelta(days=1) if d.weekday() == 5 else d + dt.timedelta(days=1) if d.weekday() == 6 else d
    days = {observed(dt.date(year, 1, 1)), nth(1, 0, 3), nth(2, 0, 3), nth(5, 0, -1), observed(dt.date(year, 7, 4)),
            nth(9, 0, 1), nth(10, 0, 2), observed(dt.date(year, 11, 11)), nth(11, 3, 4),
            observed(dt.date(year, 12, 25))}
    if year >= FEDERAL_HOLIDAY_JUNETEENTH_FROM:
        days.add(observed(dt.date(year, 6, 19)))
    return days


def positioning_release(report_date: dt.date) -> dt.datetime:
    """cot_feed._derived_publication: the first Friday strictly after the report date, 3:30 pm Eastern, a business day
    later for each federal holiday from the day after the report date to that Friday. A rule, not a record."""
    ahead = (FRIDAY - report_date.weekday()) % DAYS_PER_WEEK or DAYS_PER_WEEK
    nominal = report_date + dt.timedelta(days=ahead)
    holidays = us_federal_holidays(report_date.year) | us_federal_holidays(nominal.year)

    def business(d):
        return d.weekday() < SATURDAY and d not in holidays
    n = sum(1 for k in range(1, ahead + 1) if report_date + dt.timedelta(days=k) in holidays)
    pub = nominal
    for _ in range(n):
        pub += dt.timedelta(days=1)
        while not business(pub):
            pub += dt.timedelta(days=1)
    while not business(pub):
        pub += dt.timedelta(days=1)
    return eastern(pub, POSITIONING_RELEASE_EASTERN)


POSITIONING_COLUMNS = ['known_from_ns', 'known_from_eastern', 'known_from_basis', 'contract_code', 'market_name',
                       'report_date', 'open_interest', 'managed_money_long', 'managed_money_short',
                       'managed_money_net', 'net_change_on_week', 'source_file']


def positioning(src: Sources) -> list[list]:
    rows_by_code = defaultdict(dict)
    for stored in src.listed('raw/cot/fut_disagg_txt_'):
        with zipfile.ZipFile(io.BytesIO(src.bytes(stored))) as zf:
            for name in sorted(n for n in zf.namelist() if n.lower().endswith('.txt')):
                reader = csv.DictReader(io.TextIOWrapper(zf.open(name), encoding='utf-8', errors='replace',
                                                         newline=''))
                for r in reader:
                    code = r['CFTC_Contract_Market_Code'].strip()
                    if code not in POSITIONING_CODES:
                        continue
                    day = dt.date.fromisoformat(r['Report_Date_as_YYYY-MM-DD'].strip())
                    if day in rows_by_code[code]:
                        continue
                    long_, short = number(r['M_Money_Positions_Long_All']), number(r['M_Money_Positions_Short_All'])
                    oi = number(r['Open_Interest_All'])
                    rows_by_code[code][day] = dict(
                        name=r['Market_and_Exchange_Names'].strip(), oi=None if oi is None else int(oi),
                        long=None if long_ is None else int(long_), short=None if short is None else int(short),
                        stored=stored)
    out = []
    for code in POSITIONING_CODES:
        series = sorted(rows_by_code[code].items())
        for i, (day, r) in enumerate(series):
            net = None if r['long'] is None or r['short'] is None else r['long'] - r['short']
            change = None
            if i and net is not None:
                prev_day, prev = series[i - 1]
                prev_net = None if prev['long'] is None or prev['short'] is None else prev['long'] - prev['short']
                if prev_net is not None and WEEK_STEP_MIN_DAYS <= (day - prev_day).days <= WEEK_STEP_MAX_DAYS:
                    change = net - prev_net
            known = to_ns(positioning_release(day))
            out.append(known_cols(known) + ['rule: Friday after the report date 15:30 Eastern, holiday-shifted',
                                            code, r['name'], day.isoformat(), r['oi'], r['long'], r['short'], net,
                                            change, r['stored']])
    return out


# ---------------------------------------------------------------- X02, X09: forecasts
def forecast_files(src: Sources):
    for stored in src.listed('raw/mos/'):
        model = Path(stored).name.split('_')[1]
        rows = list(csv.DictReader(io.StringIO(src.text(stored))))
        yield stored, model, rows


def degree_days(mean_f: float) -> tuple[float, float]:
    return max(0.0, DEGREE_DAY_BASE_F - mean_f), max(0.0, mean_f - DEGREE_DAY_BASE_F)


def weighted(values: dict) -> tuple:
    """Combine city values with the original weights, spread over the cities present; (value, weight sum)."""
    present = {c: v for c, v in values.items() if c in CITY_SHARE and v is not None}
    total = sum(CITY_SHARE[c] for c in present)
    if total <= 0:
        return None, 0.0
    return sum(CITY_SHARE[c] * v for c, v in present.items()) / total, total


def forecasts(src: Sources, trade_days, cut: int):
    """Every model run, hour by hour (Greg, 2026-11-17: no averaged temperatures; "We have hourly temps available for
    each day. Use them"). For each run and each forecast hour it gives, the cities' forecast temperatures weighted
    together (the weights spread over the cities present). No high, no low, no midpoint. A run is known 4.5 hours after
    it starts; every run is kept, and the rows show the latest run as known at their tick, so each new run shows at
    its own tick."""
    city_rows, columns = [], None
    runs = defaultdict(dict)          # (model, runtime) -> {ftime: {city: tmp}}
    for stored, model, rows in forecast_files(src):
        if rows and columns is None:
            columns = list(rows[0].keys())
        for r in rows:
            known = utc_ns(r['runtime'], '%Y-%m-%d %H:%M:%S') + FORECAST_LAG_NS
            if known >= cut:
                continue
            city_rows.append(known_cols(known) + [r.get(c, '') for c in columns] + [stored])
            runs[(model, r['runtime'])].setdefault(r['ftime'], {})
            tmp = number(r.get('tmp'))
            if tmp is not None:
                runs[(model, r['runtime'])][r['ftime']][r['station'][1:]] = tmp
    col = {c: len(KNOWN_COLUMNS) + i for i, c in enumerate(columns)}
    city_rows.sort(key=lambda x: (x[0], x[col['model']], x[col['station']], x[col['ftime']]))

    hourly, wide = [], {model: [] for model in FORECAST_POINTS}
    weighted_at = {}                  # (model, runtime, ftime) -> {city: tmp} of the weighted cities
    for (model, runtime), points in sorted(runs.items()):
        known = utc_ns(runtime, '%Y-%m-%d %H:%M:%S') + FORECAST_LAG_NS
        ftimes = sorted(points)
        if len(ftimes) != FORECAST_POINTS[model]:
            raise ValueError(f'{model} run {runtime} gives {len(ftimes)} forecast hours, not {FORECAST_POINTS[model]}')
        line = known_cols(known) + [runtime]
        for k, ftime in enumerate(ftimes, 1):
            temps = {c: t for c, t in points[ftime].items() if c in CITY_SHARE}
            weighted_at[(model, runtime, ftime)] = temps
            gw, cover = weighted(temps)
            missing = sorted(c for c in CITY_WEIGHTS if c not in temps)
            hourly.append(known_cols(known) + [model, runtime, k, ftime, None if gw is None else round(gw, 3),
                                               len(temps), round(cover, 4), ' '.join(missing)])
            line += [ftime, None if gw is None else round(gw, 3)]
        wide[model].append(line)

    gaps = []                         # GFS minus NAM, forecast hour by forecast hour, on the cities both have
    shared = sorted({rt for (m, rt) in runs if m == 'GFS'} & {rt for (m, rt) in runs if m == 'NAM'})
    for runtime in shared:
        known = utc_ns(runtime, '%Y-%m-%d %H:%M:%S') + FORECAST_LAG_NS
        line = known_cols(known) + [runtime]
        for ftime in sorted(runs[('GFS', runtime)]):
            a = weighted_at[('GFS', runtime, ftime)]
            b = weighted_at.get(('NAM', runtime, ftime), {})
            common = {c for c in a if c in b}
            ga, _ = weighted({c: a[c] for c in common})
            gb, _ = weighted({c: b[c] for c in common})
            line += [ftime, None if ga is None or gb is None else round(ga - gb, 3), len(common)]
        gaps.append(line)
    return dict(columns=columns, city=city_rows, hourly=hourly, wide=wide, gaps=gaps)


# ---------------------------------------------------------------- X10: observed weather (fix 3)
def readings(src: Sources, stored: str):
    lines = [ln for ln in src.text(stored).splitlines() if not ln.startswith('#')]
    reader = csv.reader(lines, delimiter='\t', quoting=csv.QUOTE_NONE)
    header = next(reader)
    return header, [dict(zip(header, r)) for r in reader]


def gas_day_of(valid_ns: int) -> str:
    """The gas day a reading belongs to, by the date it starts (10 am Eastern to 10 am Eastern). A label only (Greg,
    2026-11-17: the gas day is kept as a descriptor; no gas-day temperature is made or used)."""
    from zoneinfo import ZoneInfo
    local = dt.datetime.fromtimestamp(valid_ns // NS_PER_SECOND, tz=ZoneInfo('America/New_York'))
    start = local.date() if local.time() >= GAS_DAY_START_EASTERN else local.date() - dt.timedelta(days=1)
    return start.isoformat()


def weather(src: Sources, trade_days, cut: int):
    """Observed weather hour by hour (Greg, 2026-11-17: "The temp changes are what drive market price in rt
    markets!! We have hourly temps available for each day. Use them"). Every reading is kept; each city's routine
    hourly reading (temperature, wind, precipitation) is written as it was reported, with the gas day as a label; and
    at every time a new routine reading becomes known, the cities' latest readings weighted together, with the heating
    and cooling degrees of that weighted temperature (from 65 F). Nothing is averaged over time."""
    spans = [(trade_day_bounds(d)[0] - READINGS_LOOKBACK_NS, rows_end(d)) for d in trade_days]
    reading_rows, header = [], None
    for city in list(CITY_WEIGHTS) + list(UNWEIGHTED_CITIES):
        stored = f'raw/weather_obs/asos_{city}_20230901_20231101.tsv.gz'
        h, rows = readings(src, stored)
        header = header or h
        for r in rows:
            t = utc_ns(r['valid'], '%Y-%m-%d %H:%M')
            known = t + READING_LAG_NS
            if any(lo <= t and known < hi for lo, hi in spans):
                reading_rows.append(known_cols(known) + [r.get(c, '') for c in header] + [stored])
    reading_rows.sort(key=lambda x: (x[0], x[2]))

    hourly_rows, events = [], []
    for city in list(CITY_WEIGHTS) + list(UNWEIGHTED_CITIES):
        stored = f'raw/weather_obs/asos_{city}_routine_20230901_20231101.tsv.gz'
        _, rows = readings(src, stored)
        for r in rows:
            t = utc_ns(r['valid'], '%Y-%m-%d %H:%M')
            if not any(lo <= t and t + READING_LAG_NS < hi for lo, hi in spans):
                continue
            rain = TRACE_PRECIP_IN if r['p01i'].strip() == 'T' else number(r['p01i'])
            values = dict(tmpf=number(r['tmpf']), sknt=number(r['sknt']), p01i=rain)
            hourly_rows.append(known_cols(t + READING_LAG_NS) + [city, r['valid'], gas_day_of(t), values['tmpf'],
                                                                 values['sknt'], values['p01i'], stored])
            if city in CITY_SHARE:
                events.append((t + READING_LAG_NS, city, r['valid'], values))
    hourly_rows.sort(key=lambda x: (x[0], x[2]))

    events.sort(key=lambda e: (e[0], e[1]))
    latest = {key: {} for key in ('tmpf', 'sknt', 'p01i')}      # field -> city -> (value, the reading's time)
    weighted_rows = []
    for k, (known, city, valid, values) in enumerate(events):
        for key, value in values.items():
            if value is not None:
                latest[key][city] = (value, valid)
        if k + 1 < len(events) and events[k + 1][0] == known:
            continue                                            # every reading known at this time first
        gw = {}
        for key in latest:
            gw[key], _ = weighted({c: v for c, (v, _) in latest[key].items()})
        temps = latest['tmpf']
        _, cover = weighted({c: v for c, (v, _) in temps.items()})
        heating, cooling = (None, None) if gw['tmpf'] is None else degree_days(gw['tmpf'])
        weighted_rows.append(known_cols(known) + [
            None if gw['tmpf'] is None else round(gw['tmpf'], 3), None if heating is None else round(heating, 3),
            None if cooling is None else round(cooling, 3), None if gw['sknt'] is None else round(gw['sknt'], 3),
            None if gw['p01i'] is None else round(gw['p01i'], 4), len(temps), round(cover, 4),
            ' '.join(c for c in CITY_WEIGHTS if c not in temps),
            min((v for _, v in temps.values()), default=None)])
    return dict(header=header, readings=reading_rows, hourly=hourly_rows, weighted=weighted_rows)


# ---------------------------------------------------------------- X05, X07: wind and gas burned for power
def grid(src: Sources, cut: int):
    every, us48 = [], defaultdict(dict)
    for stored in src.listed('raw/eia930/api/'):
        page = json.loads(src.text(stored))['response']['data']
        route = 'fuel-type-data' if 'fuel-type-data' in stored else 'region-data'
        for r in page:
            known = utc_ns(r['period'], '%Y-%m-%dT%H') + GRID_LAG_NS
            if known >= cut:
                continue
            kind = r.get('fueltype') or r.get('type')
            every.append(known_cols(known) + [r['period'], r['respondent'], route, kind,
                                              r.get('type-name'), r.get('value'), r.get('value-units'), stored])
            if r['respondent'] == 'US48' and route == 'fuel-type-data' and kind in ('WND', 'NG'):
                us48[r['period']][kind] = number(r.get('value'))
    every.sort(key=lambda x: (x[0], x[3], x[4], str(x[5])))
    rows = []
    for period in sorted(us48):
        gas = us48[period].get('NG')
        burn = None if gas is None else round(gas * HOURS_PER_DAY * HEAT_RATE_BTU_PER_KWH / GAS_BURN_DIVISOR, 3)
        rows.append(known_cols(utc_ns(period, '%Y-%m-%dT%H') + GRID_LAG_NS) + [period, us48[period].get('WND'), gas,
                                                                               burn])
    return dict(every=every, us48=rows)


# ---------------------------------------------------------------- X06: sessions since the front contract expired
def business_day(d: dt.date) -> bool:
    """Monday to Friday. No CME holiday falls between Sep 27 and Oct 18, 2023 (Columbus Day, Oct 9, trades)."""
    return d.weekday() < SATURDAY


def ng_expiry(year: int, month: int) -> dt.date:
    """flow_calendar.ng_expiry: 3 business days before the first calendar day of the delivery month."""
    cur, count = dt.date(year, month, 1), 0
    while count < NG_LAST_TRADE_BUSINESS_DAYS:
        cur -= dt.timedelta(days=1)
        count += business_day(cur)
    return cur


def expiry(trade_days):
    rows = []
    for day in trade_days:
        y, m = day.year, day.month + EXPIRY_SEARCH_MONTHS_AHEAD
        if m > MONTHS_PER_YEAR:
            m, y = m - MONTHS_PER_YEAR, y + 1
        while ng_expiry(y, m) >= day:
            m -= 1
            if m == 0:
                m, y = MONTHS_PER_YEAR, y - 1
        exp = ng_expiry(y, m)
        sessions = sum(business_day(exp + dt.timedelta(days=k)) for k in range(1, (day - exp).days + 1))
        opens, _ = trade_day_bounds(day)
        rows.append(known_cols(opens) + [day.isoformat(), sessions, 'NG%s%02d' % (MONTH_CODES[m - 1], y % TWO_DIGIT_YEAR),
                                         exp.isoformat()])
    return rows


# ---------------------------------------------------------------- X13: the futures curve
def curve_shape(prices: dict, by_expiry: list, symbols: dict, t: int):
    """forward_curve.curve_features over the 12 nearest live months that have a price (frankie_day_external.shape)."""
    live = []
    for exp, iid in by_expiry:
        if exp > t and iid in prices:
            live.append(iid)
            if len(live) == CURVE_MONTHS:
                break
    if len(live) < SHAPE_NEEDS_MONTHS:
        return None
    closes = [prices[i] for i in live]
    front, c1, back = closes[0], closes[1], closes[-1]
    last = len(closes) - 1                               # the far month's rank
    mid = len(closes) // SHAPE_NEEDS_MONTHS              # forward_curve: the middle rank, ranks[len(ranks) // 2]
    chord = front + (back - front) * (mid / last)
    slope_1 = c1 - front
    regime = 'backwardation' if slope_1 < 0 else 'contango' if slope_1 > 0 else 'flat'
    return [symbols[live[0]], symbols[live[1]], round(front, 4), round(c1, 4), last, round(back, 4),
            round(slope_1, 4), round(back - front, 4), round(closes[mid] - chord, 4),
            round(round(front, 4) - round(c1, 4), 4), regime, len(closes)]


def curve(src: Sources, cut: int):
    import databento as db
    import warnings
    warnings.filterwarnings('ignore', module='databento')

    def records(schema):
        for stored in src.listed(f'raw/curve/NG_FUT_{schema}_'):
            data = src.bytes(stored)
            store = db.DBNStore.from_bytes(data)
            yield stored, store.to_ndarray()

    defs = []
    for stored, a in records('definition'):
        for r in a:
            defs.append((int(r['ts_recv']), int(r['instrument_id']), r['raw_symbol'].decode(),
                         r['instrument_class'].decode(), int(r['expiration']), stored))
    defs = sorted(d for d in defs if d[0] < cut)
    def_rows = [known_cols(d[0]) + list(d[1:]) for d in defs]

    stats, trades = [], []
    for stored, a in records('statistics'):
        for r in a:
            t = int(r['ts_recv'])
            if t >= cut:
                continue
            p = int(r['price'])
            stats.append((t, int(r['ts_event']), int(r['ts_ref']), int(r['instrument_id']), int(r['stat_type']),
                          None if p == UNDEFINED_PRICE else p / PRICE_SCALE, int(r['quantity']),
                          int(r['update_action']), int(r['stat_flags']), stored))
    for stored, a in records('trades'):
        for r in a:
            t = int(r['ts_recv'])
            if t >= cut:
                continue
            p = int(r['price'])
            trades.append((t, int(r['ts_event']), int(r['instrument_id']),
                           None if p == UNDEFINED_PRICE else p / PRICE_SCALE, int(r['size']), r['side'].decode(),
                           stored))
    stats.sort(key=lambda x: x[0])                    # a stable sort: records sharing a time keep the tape's order
    trades.sort(key=lambda x: x[0])

    def walk(events, keep):
        """Definitions and price events in time order: a month counts once its definition is known. Prices start
        fresh at a gap in the held files."""
        symbols, expiry_of, prices, out, last = {}, {}, {}, [], None
        by_expiry, i = [], 0
        blocks = held_blocks(clock_day_of(e[-1]) for e in events)
        block = None
        for e in events:
            if blocks[clock_day_of(e[-1])] != block:
                block, prices, last = blocks[clock_day_of(e[-1])], {}, None
            while i < len(defs) and defs[i][0] <= e[0]:
                _, iid, sym, cls, exp, _ = defs[i]
                if OUTRIGHT.match(sym) and iid not in expiry_of:
                    expiry_of[iid] = exp
                    bisect.insort(by_expiry, (exp, iid))
                symbols[iid] = sym
                i += 1
            iid, price = keep(e)
            if iid is None or iid not in expiry_of or price is None:
                continue
            prices[iid] = price
            shape = curve_shape(prices, by_expiry, symbols, e[0])
            if shape is not None and shape != last:
                out.append(known_cols(e[0]) + shape)
                last = shape
        return out, symbols

    settled, symbols = walk(stats, lambda s: (s[3], s[5]) if s[4] == SETTLEMENT_STAT_TYPE else (None, None))
    traded, _ = walk(trades, lambda r: (r[2], r[3]))
    name = {d[1]: d[2] for d in defs}
    stat_rows = [known_cols(s[0]) + [s[1], s[2], s[3], name.get(s[3], '')] + list(s[4:]) for s in stats]
    trade_rows = [known_cols(r[0]) + [r[1], r[2], name.get(r[2], '')] + list(r[3:]) for r in trades]
    return dict(definitions=def_rows, statistics=stat_rows, trades=trade_rows, settled=settled, traded=traded)


# ---------------------------------------------------------------- X11, X12: storage (fix 1, fix 2, fix 4)
def xls_sheets(src: Sources, stored: str):
    """The sheets of an EIA .xls workbook, read from the fingerprint-checked bytes, with the book's date mode."""
    import xlrd
    book = xlrd.open_workbook(file_contents=src.bytes(stored))
    return book.datemode, {s.name: s for s in book.sheets()}


def labelled(sheet, label: str) -> tuple[int, dict]:
    """The row that carries `label`, and every column label of that row (columns are found by label, not position)."""
    for r in range(sheet.nrows):
        values = [str(v).strip() for v in sheet.row_values(r)]
        if label in values:
            return r, {v: c for c, v in enumerate(values) if v}
    raise ValueError(f'sheet {sheet.name!r} has no row labelled {label!r}')


def dated_rows(sheet, datemode: int, after: int):
    """(week ending, row values) for each row below `after` that carries a date cell (the week-ending date)."""
    import xlrd
    for r in range(after + 1, sheet.nrows):
        cells = sheet.row(r)
        for c in cells:
            if c.ctype == xlrd.XL_CELL_DATE:
                yield xlrd.xldate_as_datetime(c.value, datemode).date(), sheet.row_values(r)
                break


def storage_release(week: dt.date) -> int:
    """frankie_day_external storage: Thursday 10:30 am Eastern after the week ending. A rule, not a record."""
    return to_ns(eastern(week + dt.timedelta(days=STORAGE_RELEASE_DAYS_AFTER_WEEK), STORAGE_RELEASE_EASTERN))


STORAGE_COLUMNS = (['known_from_ns', 'known_from_eastern', 'known_from_basis', 'week_ending',
                    'level_first_print_bcf', 'change_from_first_prints_bcf', 'vs_5yr_bcf', 'vs_5yr_rule',
                    'same_week_prior_5y_levels'] +
                   [f'first_print_{r.lower().replace(" ", "_")}_bcf' for r in STORAGE_REGIONS] +
                   ['eia_note', 'source_file'])
ESTIMATE_COLUMNS = ['known_from_ns', 'known_from_eastern', 'known_from_basis', 'print_date', 'week_ending',
                    'estimate_bcf', 'actual_change_from_first_prints_bcf', 'surprise_bcf', 'estimate_missing_reason']


def storage(src: Sources, cut: int) -> dict:
    """X11 and X12. Fix 1: the level is the EIA's original estimate before any revision (revisions.xls holds it for
    every week from 2015-06-19). The change on the week is this week's first print minus the week before's first
    print; it is not called "as printed", because in the week after a revision the printed change used the revised
    figure. The five-year comparison keeps the original's fallback exactly: the level minus the mean of the same ISO
    week number in each of the five prior calendar years, from the EIA history file, all five listed beside it, and
    empty unless all five exist. Fix 2: the street estimate stays empty with its reason (kept simple)."""
    rev_file, hist_file = 'raw/storage/revisions.xls', 'raw/storage/ngshistory.xls'
    api_files = src.listed('raw/storage/api/')
    mode, sheets = xls_sheets(src, rev_file)
    first = {}
    for sheet in sheets.values():
        try:
            head, cols = labelled(sheet, STORAGE_WEEK)
        except ValueError:
            continue
        for week, v in dated_rows(sheet, mode, head):
            first[week] = dict(total=number(v[cols[STORAGE_TOTAL]]),
                               regions=[number(v[cols[r]]) for r in STORAGE_REGIONS],
                               note=str(v[cols[STORAGE_NOTE]]).strip() or None)
    if not first:
        raise ValueError(f'{rev_file} holds no week of first prints')

    mode, sheets = xls_sheets(src, hist_file)
    head, cols = labelled(sheets[STORAGE_HISTORY_SHEET], STORAGE_WEEK)
    history = {w: number(v[cols[STORAGE_TOTAL]]) for w, v in dated_rows(sheets[STORAGE_HISTORY_SHEET], mode, head)}
    head, cols = labelled(sheets[STORAGE_CHANGES_SHEET], STORAGE_TOTAL)
    eia_change = {w: number(v[cols[STORAGE_TOTAL]]) for w, v in dated_rows(sheets[STORAGE_CHANGES_SHEET], mode, head)}

    # The original read the same levels from the EIA API series; the spec reads the history file. They must agree.
    api = {}
    for stored in api_files:
        for r in json.loads(src.text(stored))['response']['data']:
            api[dt.date.fromisoformat(r['period'])] = number(r['value'])
    differ = sorted(w.isoformat() for w in set(api) & set(history) if api[w] != history[w])
    if differ:
        raise ValueError(f'the EIA history file and the API series disagree on {len(differ)} weeks, first {differ[:3]}')

    weekly, estimate, change_differs = [], [], []
    for week in sorted(first):
        known = storage_release(week)
        if known >= cut:
            continue
        row, prev = first[week], first.get(week - dt.timedelta(days=DAYS_PER_WEEK))
        level = row['total']
        change = None if prev is None or level is None or prev['total'] is None else level - prev['total']
        iso = week.isocalendar()[1]
        prior = sorted((w.year, v) for w, v in history.items()
                       if w.isocalendar()[1] == iso and week.year - FIVE_YEAR_PRIOR_YEARS <= w.year < week.year)
        whole = len(prior) == FIVE_YEAR_PRIOR_YEARS and level is not None and all(v is not None for _, v in prior)
        vs5 = round(level - sum(v for _, v in prior) / len(prior), 1) if whole else None
        listed = '; '.join(f'{y}: {v:g}' for y, v in prior) or None
        basis = 'rule: Thursday after the week ending, 10:30 Eastern'
        weekly.append(known_cols(known) + [basis, week.isoformat(), level, change, vs5,
                                           'fallback: same ISO week, five prior calendar years, EIA history file',
                                           listed] + row['regions'] + [row['note'], rev_file])
        thursday = week + dt.timedelta(days=STORAGE_RELEASE_DAYS_AFTER_WEEK)
        estimate.append(known_cols(known) + [basis, thursday.isoformat(), week.isoformat(), None, change, None,
                                             ESTIMATE_MISSING])
        if change is not None and eia_change.get(week) is not None and change != eia_change[week]:
            change_differs.append(dict(week_ending=week.isoformat(), change_from_first_prints_bcf=change,
                                       eia_current_net_change_bcf=eia_change[week]))
    return dict(weekly=weekly, estimate=estimate, change_differs=change_differs,
                api_weeks_compared=len(set(api) & set(history)), source_files=[rev_file, hist_file] + api_files)


# ---------------------------------------------------------------- writing
SHAPE_COLUMNS =['known_from_ns', 'known_from_eastern', 'front_symbol', 'next_symbol', 'front', 'next', 'far_rank',
                 'far', 'slope_to_next', 'slope_to_far', 'curvature', 'front_minus_next', 'regime', 'months_priced']


def cell(v):
    if v is None:
        return ''
    if isinstance(v, bool):
        return 'yes' if v else 'no'
    if isinstance(v, float):
        return repr(v)
    return str(v)


def write_table(out: Path, name: str, columns: list, rows: list, zipped: bool = False) -> dict:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator='\n')
    w.writerow(columns)
    for r in rows:
        if len(r) != len(columns):
            raise ValueError(f'{name}: a row has {len(r)} values for {len(columns)} columns')
        w.writerow([cell(v) for v in r])
    raw = buf.getvalue().encode('utf-8')
    if zipped:
        z = io.BytesIO()
        with gzip.GzipFile(fileobj=z, mode='wb', mtime=0, compresslevel=GZIP_LEVEL, filename='') as fh:
            fh.write(raw)
        raw, name = z.getvalue(), name + '.gz'
    (out / name).write_bytes(raw)
    return dict(table=name, rows=len(rows), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def empty_cells(folder: Path, table: str) -> dict:
    """Empty cells per column of a written table (criterion 2: every empty value is counted and explained)."""
    raw = (folder / table).read_bytes()
    text = (gzip.decompress(raw) if table.endswith('.gz') else raw).decode()
    reader = csv.reader(io.StringIO(text))
    header = next(reader)
    counts = [0] * len(header)
    for r in reader:
        for i, v in enumerate(r):
            counts[i] += v == ''
    return {c: n for c, n in zip(header, counts) if n}


EMPTY_REASONS = {
    'positioning.csv': 'change on the week: no report 5 to 10 days earlier',
    'forecast_city_runs.csv.gz': 'the forecast product does not give that figure for that hour (as served)',
    'forecast_hourly.csv': 'cities_missing is empty when no city is missing; gw_tmp_f: no weighted city has a forecast '
                           'temperature at that hour',
    'forecast_gap_gfs_nam.csv': 'the gap: NAM gives no forecast at that hour, or no city is in both',
    'weather_readings.csv.gz': 'the station did not report that field in that reading (as served)',
    'weather_hourly_city.csv': 'the routine hourly reading carries no temperature, wind or precipitation (as served)',
    'weather_hourly_weighted.csv': 'cities_missing is empty when no city is missing; a figure: no weighted city has '
                                   'reported it yet in the span',
    'grid_hourly_all.csv.gz': 'the EIA gives no value for that hour (as served)',
    'curve_definitions.csv.gz': '', 'curve_statistics.csv.gz': 'price: the statistic has no price (a quantity only); '
                                                                'raw_symbol: no definition known for that instrument',
    'curve_trades.csv.gz': 'raw_symbol: no definition known for that instrument',
    'storage_weekly.csv': 'change: no first print for the week before (the first prints start 2015-06-19); vs_5yr and '
                          '(INFORMATION ONLY, never on the rows or in a calculation: Greg 2026-11-17) '
                          'the prior levels: fewer than five prior calendar years carry that ISO week number (week 53); '
                          'eia_note: the EIA wrote no note for that week',
    'storage_estimate.csv': 'estimate and surprise: the street estimate is not held (estimate_missing_reason); actual: '
                            'no first print for the week before',
}


def build(src_folder: Path, out: Path, trade_days=TRADE_DAYS) -> dict:
    src = Sources(src_folder)
    days = [parse_trade_day(d) for d in trade_days]
    cut = max(rows_end(d) for d in days)
    out.mkdir(parents=True, exist_ok=True)
    tables, empty = [], []

    pos = [r for r in positioning(src) if r[0] < cut]
    tables.append(write_table(out, 'positioning.csv', POSITIONING_COLUMNS, pos))

    fc = forecasts(src, days, cut)
    tables.append(write_table(out, 'forecast_city_runs.csv',
                              ['known_from_ns', 'known_from_eastern'] + fc['columns'] + ['source_file'], fc['city'],
                              zipped=True))
    tables.append(write_table(out, 'forecast_hourly.csv',
                              ['known_from_ns', 'known_from_eastern', 'model', 'runtime_utc', 'point', 'ftime_utc',
                               'gw_tmp_f', 'cities', 'weight_covered', 'cities_missing'], fc['hourly']))
    for model, points in FORECAST_POINTS.items():
        tables.append(write_table(out, f'forecast_on_row_{model.lower()}.csv',
                                  ['known_from_ns', 'known_from_eastern', 'runtime_utc'] +
                                  [f'{what}_{k}' for k in range(1, points + 1) for what in ('ftime_utc', 'gw_tmp_f')],
                                  fc['wide'][model]))
    tables.append(write_table(out, 'forecast_gap_gfs_nam.csv',
                              ['known_from_ns', 'known_from_eastern', 'runtime_utc'] +
                              [f'{what}_{k}' for k in range(1, FORECAST_POINTS['GFS'] + 1)
                               for what in ('ftime_utc', 'gfs_minus_nam_f', 'cities')], fc['gaps']))

    wx = weather(src, days, cut)
    tables.append(write_table(out, 'weather_readings.csv',
                              ['known_from_ns', 'known_from_eastern'] + wx['header'] + ['source_file'],
                              wx['readings'], zipped=True))
    tables.append(write_table(out, 'weather_hourly_city.csv', ['known_from_ns', 'known_from_eastern', 'city', 'valid',
                                                               'gas_day', 'tmpf', 'sknt', 'p01i', 'source_file'],
                              wx['hourly']))
    tables.append(write_table(out, 'weather_hourly_weighted.csv',
                              ['known_from_ns', 'known_from_eastern', 'gw_tmp_f', 'gw_heating_degrees_f',
                               'gw_cooling_degrees_f', 'gw_wind_knots', 'gw_precip_in', 'cities_present',
                               'weight_covered', 'cities_missing', 'oldest_temperature_reading'], wx['weighted']))

    gr = grid(src, cut)
    tables.append(write_table(out, 'grid_hourly_all.csv',
                              ['known_from_ns', 'known_from_eastern', 'period_utc', 'respondent', 'table',
                               'fuel_or_type', 'name', 'value', 'units', 'source_file'], gr['every'], zipped=True))
    tables.append(write_table(out, 'grid_us48.csv', ['known_from_ns', 'known_from_eastern', 'period_utc',
                                                     'wind_mwh', 'gas_mwh', 'est_gas_burn_bcfd_rate'], gr['us48']))

    tables.append(write_table(out, 'expiry.csv', ['known_from_ns', 'known_from_eastern', 'trade_day',
                                                  'sessions_since_front_expiry', 'last_expired_symbol',
                                                  'last_expiry_date'], expiry(days)))

    cv = curve(src, cut)
    tables.append(write_table(out, 'curve_definitions.csv', ['known_from_ns', 'known_from_eastern', 'instrument_id',
                                                             'raw_symbol', 'instrument_class', 'expiration_ns',
                                                             'source_file'], cv['definitions'], zipped=True))
    tables.append(write_table(out, 'curve_statistics.csv', ['known_from_ns', 'known_from_eastern', 'ts_event',
                                                            'ts_ref', 'instrument_id', 'raw_symbol', 'stat_type',
                                                            'price', 'quantity', 'update_action', 'stat_flags',
                                                            'source_file'], cv['statistics'], zipped=True))
    tables.append(write_table(out, 'curve_trades.csv', ['known_from_ns', 'known_from_eastern', 'ts_event',
                                                        'instrument_id', 'raw_symbol', 'price', 'size', 'side',
                                                        'source_file'], cv['trades'], zipped=True))
    tables.append(write_table(out, 'curve_settled_shape.csv', SHAPE_COLUMNS, cv['settled']))
    tables.append(write_table(out, 'curve_traded_shape.csv', SHAPE_COLUMNS, cv['traded'], zipped=True))

    st = storage(src, cut)
    tables.append(write_table(out, 'storage_weekly.csv', STORAGE_COLUMNS, st['weekly']))
    tables.append(write_table(out, 'storage_estimate.csv', ESTIMATE_COLUMNS, st['estimate']))

    for t in tables:
        cells = empty_cells(out, t['table'])
        if cells:
            empty.append(dict(table=t['table'], cells_by_column=cells, reason=EMPTY_REASONS.get(t['table'], '')))
    receipt = dict(
        what='ROOT outside part: the 13 outside data points as tables, each row with the time its value became known',
        specification='SPEC-outside.md (approved 2026-11-16)', trade_days=list(trade_days),
        cut_ns=cut, cut_eastern=eastern_text(cut),
        rule_for_rows='only values known before 6 pm Eastern on the last trade day (the end of the last written row); '
                      'the pinning refuses a row received at or after it; the source files hold the rest',
        inputs=sorted({(r['stored'], r['sha256']) for r in src.read_log}), tables=tables, empty=empty,
        storage_checks=dict(
            history_file_equals_api_series_weeks=st['api_weeks_compared'],
            change_from_first_prints_differs_from_eia_current_net_change=st['change_differs'],
            note='the EIA current net change is a later figure and is not put on any row; a difference is the week '
                 'after a revision, when the printed change used the revised level of the week before'),
        not_made=[dict(points='X12 street estimate', reason=ESTIMATE_MISSING)])
    receipt['inputs'] = [dict(stored=s, sha256=h) for s, h in receipt['inputs']]
    (out / 'RECEIPT.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


WORKBOOK_SHEETS = (   # (sheet, table, what it is); the larger tables stay as files only, named on the first sheet
    ('Positioning', 'positioning.csv', 'X01, X03, X04, X08: managed-money positioning, every weekly report'),
    ('Forecast hourly', 'forecast_hourly.csv', 'X02: every model run, each forecast hour, cities weighted'),
    ('Forecast GFS', 'forecast_on_row_gfs.csv', 'X02: each GFS run as the rows show it, hour by hour'),
    ('Forecast NAM', 'forecast_on_row_nam.csv', 'X02: each NAM run as the rows show it, hour by hour'),
    ('Forecast MEX', 'forecast_on_row_mex.csv', 'X02: each extended GFS run as the rows show it, hour by hour'),
    ('GFS minus NAM', 'forecast_gap_gfs_nam.csv', 'X09: GFS minus NAM per shared run, hour by hour'),
    ('Weather weighted', 'weather_hourly_weighted.csv', 'X10: the cities\' latest hourly readings weighted, at '
     'every new reading'),
    ('Grid US48', 'grid_us48.csv', 'X05, X07: US48 wind and the gas-burn estimate, by hour'),
    ('Expiry', 'expiry.csv', 'X06: sessions since the front contract expired'),
    ('Curve settled', 'curve_settled_shape.csv', 'X13: the curve shape from settlement prices'),
    ('Storage', 'storage_weekly.csv', 'X11: weekly storage as first printed, with the regions underneath (fix 1)'),
    ('Storage estimate', 'storage_estimate.csv', 'X12: estimate against actual; the estimate is not held yet'),
)


def write_workbook(out: Path, receipt: dict) -> Path:
    """A small workbook of the point tables, separate from the four trade-day sheets (SPEC-outside.md call 6)."""
    from openpyxl import Workbook
    wb = Workbook(write_only=True)
    first = wb.create_sheet('READ ME FIRST')
    for line in (
            ['The 13 outside data points as tables, before they are pinned onto the tick rows.'],
            ['Each row carries known_from: the moment its value became known. On a tick row the value shown is the '
             'latest one known by that tick.'],
            ['Specification: SPEC-outside.md (approved 2026-11-16). Values only up to the halt of the last trade day.'],
            ['An empty cell is a value the source does not have. Nothing is estimated or filled in.'],
            ['Every cell is written as text, exactly as in the table files, so long numbers keep every digit.'],
            ['The street estimate of storage (X12) is not held yet; its column is empty with the reason.'],
            [],
            ['Sheet', 'Table file', 'What it is']):
        first.append(line)
    for sheet, name, what in WORKBOOK_SHEETS:
        first.append([sheet, name, what])
    first.append([])
    first.append(['Larger tables, kept as files beside this workbook:'])
    shown = {name for _, name, _ in WORKBOOK_SHEETS}
    for t in receipt['tables']:
        if t['table'] not in shown:
            first.append(['', t['table'], f"{t['rows']} rows"])
    for sheet, name, _ in WORKBOOK_SHEETS:
        ws = wb.create_sheet(sheet)
        for r in csv.reader(io.StringIO((out / name).read_text())):
            ws.append(r)
    path = out / 'outside_tables.xlsx'
    wb.save(path)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--src', required=True, help='the source folder data/outside/ng_oct2023 of markets-data')
    ap.add_argument('--out', required=True)
    args = ap.parse_args()
    receipt = build(Path(args.src), Path(args.out))
    write_workbook(Path(args.out), receipt)
    for t in receipt['tables']:
        print(f"{t['table']:34s} {t['rows']:>8d} rows  {t['bytes']:>10d} bytes")


if __name__ == '__main__':
    main()
