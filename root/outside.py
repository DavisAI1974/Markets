"""ROOT `outside` part: the 13 outside data points for the four trade days, made from the published source files.

Specification: markets-data `.../root-redesign-20261116/SPEC-outside.md` (approved by Greg, 2026-11-16). The 13 are
the same as in the original files (Markets 7f34afa: frankie_day_external.py and the feeds it called), with four fixes
and kept simple for this first ROOT part. Every formula carried from the original names it.

This module makes one plain table per point, each row with the time its value became known (`known_from_ns`, UTC
nanoseconds; `known_from_eastern` is the same time written in Eastern time, a label only). Pinning the values onto
the tick rows is done later from these same tables: at a tick, the latest row known at or before the tick's received
time. Nothing is estimated or filled in: a value that cannot be made is empty and its reason is in the receipt.

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

from root.calendar import EASTERN, eastern, eastern_text, parse_trade_day, to_ns, trade_day_bounds

# ---------------------------------------------------------------- declared constants (root/DECLARED_CONSTANTS.md)
TRADE_DAYS = ('2023-10-02', '2023-10-03', '2023-10-17', '2023-10-18')
NS_PER_MINUTE = 60 * 10 ** 9
DAYS_PER_WEEK = 7
MONTHS_PER_YEAR = 12
FRIDAY, SATURDAY, SUNDAY = 4, 5, 6                     # weekday numbers (Monday = 0)
GZIP_LEVEL = 9
NS_PER_HOUR = 60 * NS_PER_MINUTE

# Positioning (cot_feed.py).
POSITIONING_CODES = ('023651', '023391', '023392', '0233AG', '0233AH')
WINDOW_1Y_DAYS, MIN_REPORTS_1Y = 365, 45
WINDOW_3Y_DAYS, MIN_REPORTS_3Y = 1095, 140
WEEK_STEP_MIN_DAYS, WEEK_STEP_MAX_DAYS = 5, 10        # the change on the week only against a normal weekly step
PERCENT = 100.0
TIE_WEIGHT = 0.5                                       # cot_feed: a tie in the window counts half
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
HIGH_LOW_MIDPOINT = 2.0                                # the original forecast day temperature: (high + low) / 2
READING_LAG_NS = 10 * NS_PER_MINUTE                    # a station reading is public 10 minutes after its time
READINGS_LOOKBACK_NS = 72 * NS_PER_HOUR                # readings kept from 72 hours before each trade day opens
GAS_DAY_START_EASTERN = dt.time(10, 0)                 # fix 3: the gas day runs 10 am Eastern to 10 am Eastern
CARRY_OVER_GAS_DAYS = 2                                # fix 3: heating degree days of each of the two gas days before
GAS_DAYS_FROM = dt.date(2023, 9, 20)                   # gas days made: from here (carry-over for Oct 2 needs Sep 29)
TRACE_PRECIP_IN = 0.001                                # a trace of rain counts 0.001 inch, as nws_temp_feed
FORECAST_TZ = 'America/Chicago'                        # the original forecast describes the calendar date in Central
FORECAST_LAG_NS = int(4.5 * NS_PER_HOUR)               # a model run is public 4.5 hours after it starts
FORECAST_MIN_TEMPS = {'GFS': 5, 'NAM': 5, 'MEX': 2}    # forecast temperatures needed inside a date to use it
FORECAST_ON_ROW = (('GFS', 0), ('NAM', 0), ('GFS', 1), ('MEX', 3))   # the four forecast figures of the original
DISAGREEMENT_HORIZONS = 8                              # target dates D .. D+7

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


def standing(value, window) -> float:
    """cot_feed._percentile_of: where a value stands in its window, 0 to 100, ties counted half."""
    below = sum(1 for w in window if w < value)
    equal = sum(1 for w in window if w == value)
    return PERCENT * (below + TIE_WEIGHT * equal) / len(window)


POSITIONING_COLUMNS = ['known_from_ns', 'known_from_eastern', 'known_from_basis', 'contract_code', 'market_name',
                       'report_date', 'open_interest', 'managed_money_long', 'managed_money_short',
                       'managed_money_net', 'net_change_on_week', 'standing_1y', 'reports_in_1y',
                       'standing_3y', 'reports_in_3y', 'source_file']


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
            stand = []
            for days, minimum in ((WINDOW_1Y_DAYS, MIN_REPORTS_1Y), (WINDOW_3Y_DAYS, MIN_REPORTS_3Y)):
                start = day - dt.timedelta(days=days)
                window = [w['long'] - w['short'] for d, w in series[:i + 1]
                          if start <= d <= day and w['long'] is not None and w['short'] is not None]
                value = None if net is None or len(window) < minimum else round(standing(net, window), 2)
                stand += [value, len(window)]
            known = to_ns(positioning_release(day))
            out.append(known_cols(known) + ['rule: Friday after the report date 15:30 Eastern, holiday-shifted',
                                            code, r['name'], day.isoformat(), r['oi'], r['long'], r['short'], net,
                                            change] + stand + [r['stored']])
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


def forecasts(src: Sources, trade_days, last_halt: int):
    from zoneinfo import ZoneInfo
    central = ZoneInfo(FORECAST_TZ)
    city_rows, columns = [], None
    runs = defaultdict(dict)          # (model, runtime) -> {city: {ftime: tmp}}
    for stored, model, rows in forecast_files(src):
        if rows and columns is None:
            columns = list(rows[0].keys())
        for r in rows:
            known = utc_ns(r['runtime'], '%Y-%m-%d %H:%M:%S') + FORECAST_LAG_NS
            if known >= last_halt:
                continue
            city_rows.append(known_cols(known) + [r.get(c, '') for c in columns] + [stored])
            tmp = number(r.get('tmp'))
            if tmp is not None:
                runs[(model, r['runtime'])].setdefault(r['station'][1:], {})[r['ftime']] = tmp
    col = {c: len(KNOWN_COLUMNS) + i for i, c in enumerate(columns)}
    city_rows.sort(key=lambda x: (x[0], x[col['model']], x[col['station']], x[col['ftime']]))

    def central_date(ftime):
        return dt.datetime.strptime(ftime, '%Y-%m-%d %H:%M:%S').replace(tzinfo=dt.timezone.utc).astimezone(
            central).date()

    by_run = {}                       # (model, runtime, target date) -> (gw_hdd, gw_cdd, cities, coverage, missing, hdd by city)
    gw_rows = []
    for (model, runtime), cities in sorted(runs.items()):
        known = utc_ns(runtime, '%Y-%m-%d %H:%M:%S') + FORECAST_LAG_NS
        targets = sorted({central_date(ft) for fc in cities.values() for ft in fc})
        for target in targets:
            hdd, cdd = {}, {}
            for city, fc in cities.items():
                temps = [t for ft, t in fc.items() if central_date(ft) == target]
                if len(temps) >= FORECAST_MIN_TEMPS[model]:
                    hdd[city], cdd[city] = degree_days((max(temps) + min(temps)) / HIGH_LOW_MIDPOINT)
            gw_hdd, cover = weighted(hdd)
            if gw_hdd is None:
                continue
            gw_cdd, _ = weighted(cdd)
            missing = sorted(c for c in CITY_WEIGHTS if c not in hdd)
            by_run[(model, runtime, target)] = (round(gw_hdd, 3), hdd)
            gw_rows.append(known_cols(known) + [model, runtime, target.isoformat(), round(gw_hdd, 3),
                                                round(gw_cdd, 3), len([c for c in hdd if c in CITY_WEIGHTS]),
                                                round(cover, 4), ' '.join(missing)])

    on_row, disagreement = [], []
    for day in trade_days:
        opens, _ = trade_day_bounds(day)
        for model, horizon in FORECAST_ON_ROW:
            target = day + dt.timedelta(days=horizon)
            chosen = [rt for (m, rt, t) in by_run if m == model and t == target
                      and utc_ns(rt, '%Y-%m-%d %H:%M:%S') + FORECAST_LAG_NS < opens]
            if not chosen:
                on_row.append(known_cols(opens) + [day.isoformat(), f'{model} D+{horizon}', model, horizon,
                                                   target.isoformat(), None, None,
                                                   'no run with this target was known before the trade day opened'])
                continue
            rt = max(chosen)
            on_row.append(known_cols(opens) + [day.isoformat(), f'{model} D+{horizon}', model, horizon,
                                               target.isoformat(), rt, by_run[(model, rt, target)][0], ''])
        shared = sorted({rt for (m, rt, t) in by_run if m == 'GFS'} & {rt for (m, rt, t) in by_run if m == 'NAM'})
        for rt in shared:
            known = utc_ns(rt, '%Y-%m-%d %H:%M:%S') + FORECAST_LAG_NS
            spreads = []
            for h in range(DISAGREEMENT_HORIZONS):
                target = day + dt.timedelta(days=h)
                a, b = by_run.get(('GFS', rt, target)), by_run.get(('NAM', rt, target))
                if not a or not b:
                    continue
                common = sorted(c for c in a[1] if c in b[1] and c in CITY_SHARE)
                total = sum(CITY_SHARE[c] for c in common)
                if total <= 0:
                    continue
                ga = sum(CITY_SHARE[c] * a[1][c] for c in common) / total
                gb = sum(CITY_SHARE[c] * b[1][c] for c in common) / total
                spreads.append((h, round(ga - gb, 3), len(common)))
            if spreads:
                top = max(spreads, key=lambda x: abs(x[1]))
                disagreement.append(known_cols(known) + [day.isoformat(), rt, abs(top[1]), top[0],
                                                         json.dumps(spreads), False])
        before = [r for r in disagreement if r[2] == day.isoformat() and r[0] < opens]
        if before:
            max(before, key=lambda r: r[0])[-1] = True
    return dict(columns=columns, city=city_rows, gw=gw_rows, on_row=on_row, disagreement=disagreement)


# ---------------------------------------------------------------- X10: observed weather (fix 3)
def readings(src: Sources, stored: str):
    lines = [ln for ln in src.text(stored).splitlines() if not ln.startswith('#')]
    reader = csv.reader(lines, delimiter='\t', quoting=csv.QUOTE_NONE)
    header = next(reader)
    return header, [dict(zip(header, r)) for r in reader]


def weather(src: Sources, trade_days, last_halt: int):
    spans = [(trade_day_bounds(d)[0] - READINGS_LOOKBACK_NS, trade_day_bounds(d)[1]) for d in trade_days]
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

    gas_days = []
    g = GAS_DAYS_FROM
    while True:
        end = to_ns(eastern(g + dt.timedelta(days=1), GAS_DAY_START_EASTERN))
        if end + READING_LAG_NS >= last_halt:
            break
        gas_days.append(g)
        g += dt.timedelta(days=1)

    per_city = {}
    city_rows = []
    for city in list(CITY_WEIGHTS) + list(UNWEIGHTED_CITIES):
        stored = f'raw/weather_obs/asos_{city}_routine_20230901_20231101.tsv.gz'
        _, rows = readings(src, stored)
        stamped = sorted(((utc_ns(r['valid'], '%Y-%m-%d %H:%M'), r) for r in rows), key=lambda x: x[0])
        times = [t for t, _ in stamped]
        for g in gas_days:
            lo = to_ns(eastern(g, GAS_DAY_START_EASTERN))
            hi = to_ns(eastern(g + dt.timedelta(days=1), GAS_DAY_START_EASTERN))
            inside = [r for _, r in stamped[bisect.bisect_left(times, lo):bisect.bisect_left(times, hi)]]
            temps = [x for x in (number(r['tmpf']) for r in inside) if x is not None]
            winds = [x for x in (number(r['sknt']) for r in inside) if x is not None]
            rain = [TRACE_PRECIP_IN if r['p01i'].strip() == 'T' else number(r['p01i']) for r in inside]
            rain = [x for x in rain if x is not None]
            mean = None if not temps else sum(temps) / len(temps)
            hdd, cdd = (None, None) if mean is None else degree_days(mean)
            wind = None if not winds else sum(winds) / len(winds)
            per_city[(city, g)] = dict(hdd=hdd, cdd=cdd, wind=wind, rain=sum(rain) if rain else None)
            city_rows.append(known_cols(hi + READING_LAG_NS) + [
                g.isoformat(), city, None if city not in CITY_SHARE else round(CITY_SHARE[city], 6), len(inside),
                len(temps),
                None if mean is None else round(mean, 2), None if hdd is None else round(hdd, 2),
                None if cdd is None else round(cdd, 2), None if wind is None else round(wind, 2),
                None if not rain else round(sum(rain), 3), stored])

    day_rows, by_day = [], {}
    for g in gas_days:
        hi = to_ns(eastern(g + dt.timedelta(days=1), GAS_DAY_START_EASTERN))
        figures = {}
        for key in ('hdd', 'cdd', 'wind', 'rain'):
            figures[key], cover = weighted({c: per_city[(c, g)][key] for c in CITY_WEIGHTS})
            if key == 'hdd':
                coverage = cover
        present = [c for c in CITY_WEIGHTS if per_city[(c, g)]['hdd'] is not None]
        by_day[g] = None if figures['hdd'] is None else round(figures['hdd'], 3)
        carry = [by_day.get(g - dt.timedelta(days=k)) for k in range(1, CARRY_OVER_GAS_DAYS + 1)]
        day_rows.append(known_cols(hi + READING_LAG_NS) + [
            g.isoformat(), by_day[g], None if figures['cdd'] is None else round(figures['cdd'], 3),
            None if figures['rain'] is None else round(figures['rain'], 4),
            None if figures['wind'] is None else round(figures['wind'], 2)] + carry + [
            len(present), round(coverage, 4), ' '.join(c for c in CITY_WEIGHTS if c not in present)])
    return dict(header=header, readings=reading_rows, city=city_rows, day=day_rows)


# ---------------------------------------------------------------- X05, X07: wind and gas burned for power
def grid(src: Sources, last_halt: int):
    every, us48 = [], defaultdict(dict)
    for stored in src.listed('raw/eia930/api/'):
        page = json.loads(src.text(stored))['response']['data']
        route = 'fuel-type-data' if 'fuel-type-data' in stored else 'region-data'
        for r in page:
            known = utc_ns(r['period'], '%Y-%m-%dT%H') + GRID_LAG_NS
            if known >= last_halt:
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


def curve(src: Sources, last_halt: int):
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
    defs = sorted(d for d in defs if d[0] < last_halt)
    def_rows = [known_cols(d[0]) + list(d[1:]) for d in defs]

    stats, trades = [], []
    for stored, a in records('statistics'):
        for r in a:
            t = int(r['ts_recv'])
            if t >= last_halt:
                continue
            p = int(r['price'])
            stats.append((t, int(r['ts_event']), int(r['ts_ref']), int(r['instrument_id']), int(r['stat_type']),
                          None if p == UNDEFINED_PRICE else p / PRICE_SCALE, int(r['quantity']),
                          int(r['update_action']), int(r['stat_flags']), stored))
    for stored, a in records('trades'):
        for r in a:
            t = int(r['ts_recv'])
            if t >= last_halt:
                continue
            p = int(r['price'])
            trades.append((t, int(r['ts_event']), int(r['instrument_id']),
                           None if p == UNDEFINED_PRICE else p / PRICE_SCALE, int(r['size']), r['side'].decode(),
                           stored))
    stats.sort(key=lambda x: (x[0], x[3], x[4]))
    trades.sort(key=lambda x: (x[0], x[2]))

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


# ---------------------------------------------------------------- writing
SHAPE_COLUMNS = ['known_from_ns', 'known_from_eastern', 'front_symbol', 'next_symbol', 'front', 'next', 'far_rank',
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


def empty_count(rows, columns, which) -> int:
    idx = [columns.index(c) for c in which]
    return sum(1 for r in rows for i in idx if r[i] is None)


def build(src_folder: Path, out: Path, trade_days=TRADE_DAYS) -> dict:
    src = Sources(src_folder)
    days = [parse_trade_day(d) for d in trade_days]
    last_halt = max(trade_day_bounds(d)[1] for d in days)
    out.mkdir(parents=True, exist_ok=True)
    tables, empty = [], []

    pos = [r for r in positioning(src) if r[0] < last_halt]
    tables.append(write_table(out, 'positioning.csv', POSITIONING_COLUMNS, pos))
    empty.append(dict(table='positioning.csv', reason='standing left empty while the window holds fewer reports '
                      'than the minimum (45 for one year, 140 for three)',
                      cells=empty_count(pos, POSITIONING_COLUMNS, ['standing_1y', 'standing_3y'])))

    fc = forecasts(src, days, last_halt)
    tables.append(write_table(out, 'forecast_city_runs.csv',
                              ['known_from_ns', 'known_from_eastern'] + fc['columns'] + ['source_file'], fc['city'],
                              zipped=True))
    tables.append(write_table(out, 'forecast_gas_weighted.csv',
                              ['known_from_ns', 'known_from_eastern', 'model', 'runtime_utc', 'target_date_central',
                               'gw_hdd', 'gw_cdd', 'cities', 'weight_covered', 'cities_missing'], fc['gw']))
    on_cols = ['known_from_ns', 'known_from_eastern', 'trade_day', 'figure', 'model', 'horizon_days',
               'target_date_central', 'runtime_utc_used', 'gw_hdd', 'empty_reason']
    tables.append(write_table(out, 'forecast_on_row.csv', on_cols, fc['on_row']))
    tables.append(write_table(out, 'forecast_disagreement.csv',
                              ['known_from_ns', 'known_from_eastern', 'trade_day', 'runtime_utc',
                               'max_abs_spread_gw_hdd', 'at_horizon_days', 'spreads_by_horizon',
                               'used_on_rows'], fc['disagreement']))

    wx = weather(src, days, last_halt)
    tables.append(write_table(out, 'weather_readings.csv',
                              ['known_from_ns', 'known_from_eastern'] + wx['header'] + ['source_file'],
                              wx['readings'], zipped=True))
    city_cols = ['known_from_ns', 'known_from_eastern', 'gas_day', 'city', 'weight', 'routine_readings',
                 'readings_with_temperature', 'mean_temperature_f', 'hdd', 'cdd', 'mean_wind_knots', 'precip_in',
                 'source_file']
    tables.append(write_table(out, 'weather_gas_day_city.csv', city_cols, wx['city']))
    day_cols = ['known_from_ns', 'known_from_eastern', 'gas_day', 'gw_hdd', 'gw_cdd', 'gw_precip_in',
                'gw_wind_knots'] + [f'gw_hdd_{k}_gas_days_before' for k in range(1, CARRY_OVER_GAS_DAYS + 1)] + [
                'cities_present', 'weight_covered', 'cities_missing']
    tables.append(write_table(out, 'weather_gas_day.csv', day_cols, wx['day']))

    gr = grid(src, last_halt)
    tables.append(write_table(out, 'grid_hourly_all.csv',
                              ['known_from_ns', 'known_from_eastern', 'period_utc', 'respondent', 'table',
                               'fuel_or_type', 'name', 'value', 'units', 'source_file'], gr['every'], zipped=True))
    tables.append(write_table(out, 'grid_us48.csv', ['known_from_ns', 'known_from_eastern', 'period_utc',
                                                     'wind_mwh', 'gas_mwh', 'est_gas_burn_bcfd_rate'], gr['us48']))

    tables.append(write_table(out, 'expiry.csv', ['known_from_ns', 'known_from_eastern', 'trade_day',
                                                  'sessions_since_front_expiry', 'last_expired_symbol',
                                                  'last_expiry_date'], expiry(days)))

    cv = curve(src, last_halt)
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

    receipt = dict(
        what='ROOT outside part: the 13 outside data points as tables, each row with the time its value became known',
        specification='SPEC-outside.md (approved 2026-11-16)', trade_days=list(trade_days),
        last_halt_ns=last_halt, last_halt_eastern=eastern_text(last_halt),
        rule_for_rows='only values known before the last trade day halts; the source files hold the rest',
        inputs=sorted({(r['stored'], r['sha256']) for r in src.read_log}), tables=tables, empty=empty,
        not_made=[dict(points='X11, X12', reason='storage tables wait for Greg\'s word on adding a reader for the '
                       'EIA .xls files (SPEC-outside.md asks first)')])
    receipt['inputs'] = [dict(stored=s, sha256=h) for s, h in receipt['inputs']]
    (out / 'RECEIPT.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


WORKBOOK_SHEETS = (   # (sheet, table, what it is); the larger tables stay as files only, named on the first sheet
    ('Positioning', 'positioning.csv', 'X01, X03, X04, X08: managed-money positioning, every weekly report'),
    ('Forecast on row', 'forecast_on_row.csv', 'X02: the four forecast figures each trade day shows (kept simple)'),
    ('Forecast runs', 'forecast_gas_weighted.csv', 'X02: every model run, gas-weighted, by target date'),
    ('Disagreement', 'forecast_disagreement.csv', 'X09: GFS minus NAM per shared run; the one used is marked'),
    ('Weather gas day', 'weather_gas_day.csv', 'X10: observed gas-weighted figures per gas day (fix 3)'),
    ('Weather by city', 'weather_gas_day_city.csv', 'X10 underneath: each city per gas day'),
    ('Grid US48', 'grid_us48.csv', 'X05, X07: US48 wind and the gas-burn estimate, by hour'),
    ('Expiry', 'expiry.csv', 'X06: sessions since the front contract expired'),
    ('Curve settled', 'curve_settled_shape.csv', 'X13: the curve shape from settlement prices'),
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
            ['Storage (X11) and the storage estimate (X12) are not made yet; see RECEIPT.json.'],
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
