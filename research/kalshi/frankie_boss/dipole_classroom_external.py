"""The BOSS teacher's EXTERNAL section of the Dipole classroom: Frankie's 13 historical data points beside the 19 Dipole
columns (Greg, 2026-09-29: "we should be able to unlock classroom and teachers for today. We're the ones who made the
locks"; FRANKIE_DATA_WISHLIST_20260929.md; HISTORICAL_DATA_PLAN_20260929.md sections 4 and 7).

ADDITIVE ONLY. Nothing in the 19-column / 171-pair classroom (dipole_classroom*.py, pinned by the Monday/Sunday runs) is
edited, imported for mutation, or re-derived here: this module reads the classroom SOURCE snapshot's rows (cursor,
ts_recv_ns, the 19 components) and the day file, and builds a separate key beside the 19/171 key. The existing grade on
the 19/171 is computed from its own package exactly as before (dipole_classroom_v2.py carries it untouched).

THE DAY FILE (FRANKIE_DAY_EXTERNAL_V1, operations/frankie_day_external.py) is read in ONE place, open_day_external(): its
bytes are checked against the sha256 given (a mismatch is refused), its trading day against the classroom's day, and it is
read only through that module's AsOfReader at the classroom cutoff (the teacher's as_of: the last Dipole row's time). A
value published after the cutoff is never read (it is counted as not yet known). Each Dipole row takes, per series, the
LATEST value stamped at or before the row's own ts_recv_ns (np.searchsorted over the stamps the reader handed out at the
cutoff); every aligned value's stamp is checked against its row's time and a later stamp is a hard error.

WHAT THE SECTION HOLDS (the teacher key; the TEACH pre-message shows all of it):
  - per point (Greg's 13 in his order, less point 6: the squeeze points are DEFERRED by Greg, listed under `deferred`,
    not missing): its day-file tables (rows known at the cutoff, rows not yet known, source,
    vintage, native resolution, the file's own note) and every missing entry of the day file that names it (listed with
    the day and reason, never a reason to skip);
  - per series (the search's own series list, operations/frankie_day_external.SEARCH_SERIES, plus the hourly station
    temperatures the search also takes): every value known at the cutoff with its publication time and its whole source
    row; the value in force at the open; every value published in the day; first and last; lowest and highest with their
    times; the publication times in the day; how each Dipole row saw it (state counts over the rows, the terminal state,
    the first-to-last PRESENT direction, and the segments: each run of rows that saw one value, by cursor);
  - relationships in the SAME shapes the classroom uses for its 171 pairs: for every series against each of the 19 Dipole
    columns, and against every other series: the direction relation, Pearson over the rows where both are PRESENT with
    its present-overlap count (MIN_PEARSON_PRESENT_OVERLAP floor, ZERO_VARIANCE when every overlapping value is identical,
    checked exactly before any floating sum), and the co-movement counts (DIPOLE_PAIR_CO_MOVEMENT_COUNTS_V1: every state
    pairing across the rows; over consecutive both-PRESENT rows how many steps moved the same way, the opposite way, one
    side only, or neither). Counts and per-pair coefficients only; nothing averaged across pairs (D37).
A series the day file does not carry is kept, every row MISSING with the file's own reason, so the pair set never
depends on what arrived. Point 12 (the storage estimate) has no numeric series yet (the file lists the extractor as not
built); its captures are carried whole in its point entry.

GRADE (deterministic, host side): fact components are compared exactly (counts, states, directions, every known value and
its time, first/last/extremes); relationship claims are checked against the key's direction relation, with the key's
coefficient and counts carried beside each; the point review is checked for its series, tables and missing count. The
correction turn, acknowledgement and completion use the classroom's own acknowledgement and resolution validators.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping

from . import dipole_classroom as classroom
from .c15_journal import evidence_hash
from .c15_normalizer import COLUMNS

KEY_SCHEMA = 'DIPOLE_CLASSROOM_EXTERNAL_KEY_V1'
MESSAGE_SCHEMA = 'DIPOLE_CLASSROOM_EXTERNAL_PRE_MESSAGE_V1'
BINDING_SCHEMA = 'DIPOLE_CLASSROOM_EXTERNAL_BINDING_V1'
VISIBLE_SCHEMA = 'DIPOLE_CLASSROOM_EXTERNAL_MODEL_VISIBLE_V1'
TEACHBACK_SCHEMA = 'DIPOLE_CLASSROOM_EXTERNAL_TEACHBACK_V1'
GRADE_SCHEMA = 'DIPOLE_CLASSROOM_EXTERNAL_POST_GRADE_V1'
CORRECTION_SCHEMA = 'FRANKIE_DIPOLE_CLASSROOM_EXTERNAL_CORRECTION_REQUEST_V1'
COMPLETION_SCHEMA = 'DIPOLE_CLASSROOM_EXTERNAL_COMPLETION_V1'
PRIOR_SCHEMA = 'DIPOLE_CLASSROOM_EXTERNAL_PRIOR_CORRECTION_SUMMARY_V1'
NOVEL_SCHEMA = 'FRANKIE_DIPOLE_EXTERNAL_NOVEL_FINDING_V1'
SECTION_RECEIPT_SCHEMA = 'DIPOLE_CLASSROOM_EXTERNAL_SECTION_RECEIPT_V1'
DAY_EXTERNAL_SCHEMA = 'FRANKIE_DAY_EXTERNAL_V1'
DAY_EXTERNAL_MODULE = Path(__file__).resolve().parent / 'operations' / 'frankie_day_external.py'
SECTION_DIR, SECTION_FILE, SECTION_RECEIPT = 'external-section', 'host-dipole-external-section.json', 'receipt.json'

MIN_PEARSON_PRESENT_OVERLAP = classroom.MIN_PEARSON_PRESENT_OVERLAP
STATES = ('PRESENT', 'MISSING', 'INVALID', 'ABLATED')          # TargetState order (dipole_target.py)
PRESENT, MISSING, INVALID = 0, 1, 2
NOT_YET = 'NO_VALUE_PUBLISHED_AT_OR_BEFORE_THE_ROW_TIME'
STATION_PREFIX = 'weather.tmpf.'
NARRATIVE = ('explanation', 'why', 'market_behavior', 'fifo_full_book_order_link', 'evidence', 'uncertainty')
FACT_FIELDS = ('values_known', 'known_before_open', 'published_in_day', 'not_yet_known_in_table', 'in_force_at_open',
               'first_in_day', 'last_in_day', 'lowest_in_day', 'highest_in_day', 'publication_times_in_day',
               'known_state_counts')

# Greg's 13, in his order, less point 6 (deferred, below) (FRANKIE_DATA_WISHLIST_20260929.md; the day-file table names of HISTORICAL_DATA_PLAN section 7).
# series: names from frankie_day_external.SEARCH_SERIES (a trailing * takes every series with that prefix).
# missing: the day file's missing-list names that concern the point (a trailing * is a prefix).
POINTS = (
    dict(point_id=1, name='cot.managed_money_net_pctile_1y', tables=('cot.023651',),
         series=('cot.managed_money_net_pctile_1y',), missing=('cot', 'cot.023651')),
    dict(point_id=2, name='weather_forecast.forecast_gw_hdd', tables=('mos.gw_by_cycle', 'mos.raw'),
         series=('mos.GFS.gw_hdd_D', 'mos.NAM.gw_hdd_D', 'mos.GFS.gw_hdd_D1', 'mos.MEX.gw_hdd_D3'), missing=('mos', 'mos.*')),
    dict(point_id=3, name='cot.managed_money_net_chg_wow', tables=('cot.023651',),
         series=('cot.managed_money_net_chg_wow',), missing=('cot', 'cot.023651')),
    dict(point_id=4, name='cot.managed_money_net_pctile_3y', tables=('cot.023651',),
         series=('cot.managed_money_net_pctile_3y',), missing=('cot', 'cot.023651')),
    dict(point_id=5, name='grid_stack.bas.US48.wind_mwh', tables=('eia930.us48', 'eia930.hourly'),
         series=('eia930.US48.wind_mwh',), missing=('eia930', 'eia930.*')),
    dict(point_id=7, name='grid_stack.bas.US48.est_gas_burn_bcfd', tables=('eia930.us48', 'eia930.hourly'),
         series=('eia930.US48.est_gas_burn_bcfd_rate',), missing=('eia930', 'eia930.*')),
    dict(point_id=8, name='cot.ice.ld1.managed_money_net_pctile_1y', tables=('cot.023391',),
         series=('cot.ice.ld1.managed_money_net_pctile_1y',), missing=('cot', 'cot.023391')),
    dict(point_id=9, name='model_disagreement.summary.max_abs_spread_gw_hdd', tables=('mos.disagreement_by_cycle',),
         series=('mos.max_abs_spread_gw_hdd',), missing=('mos', 'mos.*')),
    dict(point_id=10, name='weather.gw_hdd (observed)', tables=('weather.gw_daily', 'weather.obs_hourly'),
         series=('weather.gw_hdd', STATION_PREFIX + '*'), missing=('weather', 'weather.*')),
    dict(point_id=11, name='EIA weekly storage (level, weekly change, vs 5-year)', tables=('storage.weekly',),
         series=('storage.level_bcf', 'storage.weekly_chg_bcf', 'storage.vs_5yr_bcf'), missing=('storage', 'storage.weekly')),
    dict(point_id=12, name='storage estimate vs actual', tables=('storage.estimate_captures', 'storage.weekly'),
         series=(), missing=('estimate', 'storage.estimate', 'storage.estimate_captures')),
    dict(point_id=13, name='the futures curve shape',
         tables=('curve.definitions', 'curve.statistics', 'curve.trades', 'curve.settled_shape', 'curve.traded_shape'),
         series=('curve.settled.*', 'curve.traded.*'), missing=('curve', 'curve.*')),
)
# DEFERRED by Greg (2026-09-29: "Right now we're not worried about squeeze. We can do that later."): the squeeze_watch
# points are left out of this section for now, not missing. Point 6 (squeeze_watch.sessions_since_prompt_expiry, the day
# file's calendar table) and the front-next spread change (squeeze_watch.calendar_front_next_spread_chg_3d) are not read;
# the key lists them under `deferred` with Greg's words, and a missing-list entry that concerns only them is listed there.
DEFERRED = dict(
    reason="Greg, 2026-09-29: \"Right now we're not worried about squeeze. We can do that later.\"",
    points=(dict(point_id=6, name='squeeze_watch.sessions_since_prompt_expiry',
                 tables=('calendar.sessions_since_prompt_expiry',)),
            dict(point_id=None, name='squeeze_watch.calendar_front_next_spread_chg_3d', tables=())),
    series=('calendar.sessions_since_prompt_expiry',), tables=('calendar.sessions_since_prompt_expiry',),
    missing=('calendar', 'calendar.*', 'squeeze_watch.*'))
ROWS_CARRIED_WHOLE = ('storage.estimate_captures',)   # point 12 has no numeric series: its captures are carried whole


class DayExternalRefused(ValueError):
    """The day file is absent, differs from the sha256 given, or belongs to another trading day."""


class AsOfViolation(ValueError):
    """A value stamped after its Dipole row's time reached the row (never expected; a hard error, never filtered)."""


def _np():
    import numpy
    return numpy


def _sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def _canon(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _finite(value, counter):
    """A non-finite float (the day file's JSON may carry NaN/Infinity) written as its text ('nan', 'inf', '-inf'), counted:
    the classroom's canonical JSON refuses non-finite numbers, and the value is kept, not dropped."""
    if isinstance(value, float) and not math.isfinite(value):
        counter[0] += 1
        return repr(value)
    if isinstance(value, list):
        return [_finite(v, counter) for v in value]
    if isinstance(value, dict):
        return {k: _finite(v, counter) for k, v in value.items()}
    return value


# ---------------------------------------------------------------------------------------------- the ONE adapter
def load_day_external_module(path=DAY_EXTERNAL_MODULE):
    """operations/frankie_day_external.py, loaded from this checkout (the operations directory is not a package)."""
    path = Path(path)
    if not path.is_file():
        raise DayExternalRefused(f'{path} is not in this checkout: the day-file reader is required')
    name = 'frankie_day_external'
    if name in sys.modules and getattr(sys.modules[name], '__file__', None) == str(path):
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if getattr(module, 'SCHEMA', None) != DAY_EXTERNAL_SCHEMA or not hasattr(module, 'AsOfReader'):
        raise DayExternalRefused(f'{path} is not the {DAY_EXTERNAL_SCHEMA} reader')
    return module


def open_day_external(day_file, sha256, cutoff_ns, *, trading_day):
    """THE ONE PLACE the classroom meets FRANKIE_DAY_EXTERNAL_V1. Returns (module, reader, descriptor). The file's bytes
    must equal sha256; its trading day must be the classroom's; the reader runs the file's staging check and refuses any
    request past cutoff_ns."""
    path = Path(day_file)
    if not path.is_file():
        raise DayExternalRefused(f'no day file at {path}')
    raw = path.read_bytes()
    got = _sha256_bytes(raw)
    if type(sha256) is not str or got != sha256:
        raise DayExternalRefused(f'{path} has sha256 {got}, not the {sha256} given; refused')
    body = json.loads(raw)
    if body.get('schema') != DAY_EXTERNAL_SCHEMA:
        raise DayExternalRefused(f'{path} is not a {DAY_EXTERNAL_SCHEMA} document')
    if str(body.get('trading_day')) != str(trading_day):
        raise DayExternalRefused(f'{path} is trading day {body.get("trading_day")}, not {trading_day}; refused')
    dx = load_day_external_module()
    reader = dx.AsOfReader(body, int(cutoff_ns))                 # check_day_file runs here (StagingRefused on a bad file)
    descriptor = dict(path=str(path), sha256=got, bytes=len(raw), schema=body['schema'], trading_day=body['trading_day'],
                      open_ns=body['open_ns'], halt_ns=body['halt_ns'], open_utc=body.get('open_utc'),
                      halt_utc=body.get('halt_utc'), built_utc=body.get('built_utc'),
                      history_prefix=body.get('history_prefix'), inputs=len(body.get('inputs') or ()),
                      guard=body.get('guard'), reader='operations/frankie_day_external.AsOfReader',
                      reader_cutoff_ns=int(cutoff_ns))
    return dx, reader, descriptor


def locate_beside_ingest(ingestion_receipt_path):
    """(day file, sha256 from its day-external receipt) hard-linked beside a sealed ingest, or (None, reason)."""
    directory = Path(ingestion_receipt_path).parent
    path, receipt = directory / 'day-external.json', directory / 'day-external-receipt.json'
    if not path.is_file():
        return None, f'no day-external.json beside the sealed ingest {directory}'
    if not receipt.is_file():
        return None, f'day-external.json beside {directory} has no day-external-receipt.json'
    return (path, json.loads(receipt.read_bytes())['sha256']), None


def resolve_day_file(day_file, sha256, ingestion_receipt_path=None):
    """The day file and the sha256 it must have. An explicit path and sha256 are used as given (a receipt beside the file
    must agree); without them, the file beside the sealed ingest and its receipt's sha256. Returns (path, sha, source) or
    raises DayExternalRefused naming what is absent."""
    if day_file is None and sha256 is None:
        if ingestion_receipt_path is None:
            raise DayExternalRefused('no day file given and no sealed ingest to find it beside')
        found, reason = locate_beside_ingest(ingestion_receipt_path)
        if found is None:
            raise DayExternalRefused(reason)
        return found[0], found[1], 'beside the sealed ingest (its day-external-receipt.json sha256)'
    if day_file is None or sha256 is None:
        raise DayExternalRefused('the day file path and its sha256 are given together')
    receipt = Path(day_file).parent / 'day-external-receipt.json'
    if receipt.is_file() and json.loads(receipt.read_bytes()).get('sha256') != sha256:
        raise DayExternalRefused(f'{receipt} names another sha256 than the one given; refused')
    return Path(day_file), sha256, 'given'


# ---------------------------------------------------------------------------------------------- the rows and series
def dipole_arrays(snapshot: Mapping[str, Any]) -> dict:
    """The classroom source snapshot's rows as arrays (cursor, ts_recv_ns, per column a state code and a value)."""
    np = _np()
    if snapshot.get('schema') != classroom.SOURCE_SCHEMA or tuple(snapshot.get('coverage_columns') or ()) != tuple(COLUMNS):
        raise ValueError('a complete Dipole classroom source snapshot is required')
    rows = snapshot['rows']
    n = len(rows)
    if n == 0:
        raise ValueError('the snapshot holds no Dipole row')
    cursors = np.empty(n, dtype=np.int64)
    ts = np.empty(n, dtype=np.int64)
    codes = {c: np.empty(n, dtype=np.int8) for c in COLUMNS}
    values = {c: np.full(n, np.nan, dtype=np.float64) for c in COLUMNS}
    index = {s: i for i, s in enumerate(STATES)}
    for k, row in enumerate(rows):
        cursors[k] = row['cursor']
        ts[k] = row['ts_recv_ns']
        for j, comp in enumerate(row['components']):
            name = COLUMNS[j]
            if comp['name'] != name:
                raise ValueError('teacher row column order changed')
            code = index[comp['state']]
            codes[name][k] = code
            if code == PRESENT:
                values[name][k] = float(comp['value'])
    if n > 1 and not bool(np.all(np.diff(cursors) > 0)):
        raise ValueError('snapshot cursors must be strictly increasing')
    return dict(cursors=cursors, ts=ts, codes=codes, values=values, n=n)


def _state_of(value):
    """(state code, numeric value or None, reason or None) of one published value."""
    if value is None:
        return MISSING, None, 'VALUE_IS_NULL_IN_DAY_FILE'
    if isinstance(value, bool):
        return INVALID, None, f'NOT_NUMERIC: {value!r}'
    if isinstance(value, (int, float)):
        v = float(value)
        return (PRESENT, v, None) if math.isfinite(v) else (INVALID, None, f'NOT_FINITE: {value!r}')
    if isinstance(value, str):
        try:
            v = float(value)
        except ValueError:
            return INVALID, None, f'NOT_NUMERIC: {value!r}'
        return (PRESENT, v, None) if math.isfinite(v) else (INVALID, None, f'NOT_FINITE: {value!r}')
    return INVALID, None, f'NOT_NUMERIC: {type(value).__name__}'


def _known(stamp, raw_value, row):
    code, value, reason = _state_of(raw_value)
    return dict(published_ns=int(stamp), state=STATES[code], value=value, raw_value=raw_value, reason=reason, row=row)


def read_series(dx, reader) -> tuple[list, list]:
    """Every series the search takes, read through the reader at its cutoff: (series, absent). A series whose point is
    not in the day file is kept with no known value and its reason (every row will read MISSING)."""
    body, cutoff = reader.body, reader.cutoff
    series, absent = [], []
    for name, point, column, where in dx.SEARCH_SERIES:
        if _matches(name, DEFERRED['series']):
            continue                                   # deferred by Greg (squeeze), listed under key['deferred']
        entry = dict(name=name, table=point, column=column, where=where, known=[], not_yet_known_in_table=None,
                     absent_reason=None)
        if point not in body['points']:
            entry['absent_reason'] = f'POINT_NOT_IN_DAY_FILE: {point}'
            absent.append(dict(series=name, table=point, reason='the table is not in the day file (see its missing list)'))
            series.append(entry)
            continue
        t = reader.until(point, cutoff)
        cols = t['columns']
        if column not in cols:
            entry['absent_reason'] = f'COLUMN_NOT_IN_TABLE: {column}'
            absent.append(dict(series=name, table=point, reason=f'column {column} is not in the table'))
            series.append(entry)
            continue
        i, j = cols.index('published_ns'), cols.index(column)
        rows = t['rows']
        if where:
            rows = [r for r in rows if all(r[cols.index(k)] == v for k, v in where.items())]
        order = sorted(range(len(rows)), key=lambda q: rows[q][i])    # stable: the file's order within one stamp
        entry['known'] = [_known(rows[q][i], rows[q][j], dict(zip(cols, rows[q]))) for q in order]
        entry['not_yet_known_in_table'] = t['not_yet_known']
        if not entry['known']:
            absent.append(dict(series=name, table=point, reason='no row known at the cutoff'))
        series.append(entry)
    obs = 'weather.obs_hourly'
    if obs in body['points']:
        t = reader.until(obs, cutoff)
        cols = t['columns']
        if 'tmpf' in cols and 'station' in cols:
            i, s, k = cols.index('published_ns'), cols.index('station'), cols.index('tmpf')
            by = {}
            for r in t['rows']:
                by.setdefault(r[s], []).append(r)
            for station in sorted(by, key=str):
                rows = sorted(by[station], key=lambda r: r[i])
                series.append(dict(name=STATION_PREFIX + str(station), table=obs, column='tmpf',
                                   where={'station': station}, known=[_known(r[i], r[k], dict(zip(cols, r))) for r in rows],
                                   not_yet_known_in_table=t['not_yet_known'], absent_reason=None))
        else:
            absent.append(dict(series=STATION_PREFIX + '*', table=obs, reason='the observation table has no tmpf/station column'))
    else:
        absent.append(dict(series=STATION_PREFIX + '*', table=obs, reason='the table is not in the day file (see its missing list)'))
    return series, absent


def _align(np, entry, dip):
    """Per Dipole row: the index of the latest known value stamped at or before the row's time (-1: none yet)."""
    known = entry['known']
    n = dip['n']
    if not known:
        return np.full(n, -1, dtype=np.int64)
    stamps = np.array([k['published_ns'] for k in known], dtype=np.int64)
    idx = np.searchsorted(stamps, dip['ts'], side='right') - 1
    seen = idx >= 0
    if bool(np.any(stamps[idx[seen]] > dip['ts'][seen])):
        raise AsOfViolation(f'{entry["name"]}: a value stamped after its row reached the row')
    return idx


def _ledger(np, entry, idx):
    known = entry['known']
    codes_known = np.array([STATES.index(k['state']) for k in known], dtype=np.int8) if known else np.zeros(0, np.int8)
    vals_known = np.array([k['value'] if k['value'] is not None else np.nan for k in known], dtype=np.float64) \
        if known else np.zeros(0, np.float64)
    seen = idx >= 0
    codes = np.full(idx.shape, MISSING, dtype=np.int8)
    values = np.full(idx.shape, np.nan, dtype=np.float64)
    codes[seen] = codes_known[idx[seen]]
    values[seen] = vals_known[idx[seen]]
    return codes, values


def _direction(np, codes, values):
    present = np.flatnonzero(codes == PRESENT)
    if present.size < 2:                    # one PRESENT row: first and last are the same cursor
        return 'INSUFFICIENT'
    a, b = values[present[0]], values[present[-1]]
    return 'RISE' if b > a else ('FALL' if b < a else 'FLAT')


def _segments(np, entry, idx, dip):
    """Each run of consecutive rows that saw one known value (or none yet): lossless given the rows' cursors."""
    n = dip['n']
    cuts = np.flatnonzero(np.diff(idx)) + 1
    starts = [0] + cuts.tolist()
    ends = cuts.tolist() + [n]
    out = []
    for a, b in zip(starts, ends):
        k = int(idx[a])
        item = dict(first_cursor=int(dip['cursors'][a]), last_cursor=int(dip['cursors'][b - 1]), rows=int(b - a),
                    first_row_ts_recv_ns=int(dip['ts'][a]))
        if k < 0:
            item.update(known_index=None, published_ns=None, state='MISSING', value=None,
                        reason=entry['absent_reason'] or NOT_YET)
        else:
            v = entry['known'][k]
            item.update(known_index=k, published_ns=v['published_ns'], state=v['state'], value=v['value'], reason=v['reason'])
        out.append(item)
    return out


def _point_value(v):
    return None if v is None else dict(published_ns=v['published_ns'], state=v['state'], value=v['value'])


def _facts(entry, open_ns):
    known = entry['known']
    before = [k for k in known if k['published_ns'] < open_ns]
    during = [k for k in known if k['published_ns'] >= open_ns]
    in_force = before[-1] if before else None
    window = ([in_force] if in_force else []) + during
    numeric = [k for k in window if k['state'] == 'PRESENT']
    lowest = min(numeric, key=lambda k: (k['value'], k['published_ns'])) if numeric else None
    highest = max(numeric, key=lambda k: (k['value'], -k['published_ns'])) if numeric else None
    counts = {s: sum(k['state'] == s for k in known) for s in STATES}
    return dict(values_known=len(known), known_before_open=len(before), published_in_day=len(during),
                not_yet_known_in_table=entry['not_yet_known_in_table'], in_force_at_open=_point_value(in_force),
                first_in_day=_point_value(window[0] if window else None),
                last_in_day=_point_value(window[-1] if window else None),
                lowest_in_day=_point_value(lowest), highest_in_day=_point_value(highest),
                publication_times_in_day=[k['published_ns'] for k in during], known_state_counts=counts)


# ---------------------------------------------------------------------------------------------- pairs (the 171 shapes)
def _pearson(np, x, y):
    n = int(x.size)
    if n < MIN_PEARSON_PRESENT_OVERLAP:
        return {'present_overlap': n, 'pearson': None,
                'reason': f'FEWER_THAN_{MIN_PEARSON_PRESENT_OVERLAP}_OVERLAPPING_PRESENT_VALUES'}
    if bool(np.all(x == x[0])) or bool(np.all(y == y[0])):
        return {'present_overlap': n, 'pearson': None, 'reason': 'ZERO_VARIANCE'}
    dx, dy = x - x.mean(), y - y.mean()
    vx, vy = float(np.dot(dx, dx)), float(np.dot(dy, dy))
    if vx == 0 or vy == 0:
        return {'present_overlap': n, 'pearson': None, 'reason': 'ZERO_VARIANCE'}
    return {'present_overlap': n, 'pearson': float(np.dot(dx, dy) / math.sqrt(vx * vy)), 'reason': None}


def _co_movement(np, ca, cb, x, y):
    n_rows = int(ca.size)
    counts = np.bincount(ca.astype(np.int64) * 4 + cb.astype(np.int64), minlength=16)
    state_pairs = {STATES[i // 4] + '|' + STATES[i % 4]: int(c) for i, c in enumerate(counts.tolist()) if c}
    sx, sy = np.sign(np.diff(x)), np.sign(np.diff(y))
    mx, my = sx != 0, sy != 0
    steps = {'same_direction': int(np.sum(mx & my & (sx == sy))), 'opposite_direction': int(np.sum(mx & my & (sx != sy))),
             'left_moved_only': int(np.sum(mx & ~my)), 'right_moved_only': int(np.sum(~mx & my)),
             'neither_moved': int(np.sum(~mx & ~my))}
    both = int(x.size)
    return {'schema': classroom.CO_MOVEMENT_SCHEMA, 'aligned_cursors': n_rows, 'ledger_lengths': [n_rows, n_rows],
            'unpaired_cursors': 0, 'misaligned_cursors': 0, 'state_pairs': dict(sorted(state_pairs.items())),
            'both_present': both, 'steps_between_consecutive_both_present': max(both - 1, 0), 'steps': steps}


def _relation(a, b):
    if a in ('RISE', 'FALL') and b in ('RISE', 'FALL'):
        return 'SAME_DIRECTION' if a == b else 'OPPOSITE_DIRECTION'
    return 'UNRESOLVED'


def _pair(np, left, right, kind, la, ra):
    (ca, va, da), (cb, vb, db) = la, ra
    both = (ca == PRESENT) & (cb == PRESENT)
    x, y = va[both], vb[both]
    return {'left': left, 'right': right, 'kind': kind, 'direction_relation': _relation(da, db),
            'correlation': _pearson(np, x, y), 'co_movement': _co_movement(np, ca, cb, x, y),
            'interpretation_limit': 'DESCRIPTIVE_WITHIN_CAUSAL_WINDOW_NOT_CAUSATION_OR_FUTURE_PREDICTION'}


# ---------------------------------------------------------------------------------------------- the key
def _matches(name, patterns):
    return any(name == p or (p.endswith('*') and name.startswith(p[:-1])) for p in patterns)


def build_external_key(snapshot: Mapping[str, Any], day_file, day_file_sha256, *, trading_day) -> dict:
    """The BOSS teacher's external section for one classroom window (the snapshot's rows, cutoff = its as_of)."""
    np = _np()
    dip = dipole_arrays(snapshot)
    cutoff = int(snapshot['as_of'])
    dx, reader, descriptor = open_day_external(day_file, day_file_sha256, cutoff, trading_day=trading_day)
    body = reader.body
    open_ns = int(body['open_ns'])
    series, absent = read_series(dx, reader)
    names = [s['name'] for s in series]
    if len(set(names)) != len(names):
        raise ValueError('duplicate series names in the day file reading')

    ledgers, out_series = {}, []
    for entry in series:
        idx = _align(np, entry, dip)
        codes, values = _ledger(np, entry, idx)
        direction = _direction(np, codes, values)
        ledgers[entry['name']] = (codes, values, direction)
        segments = _segments(np, entry, idx, dip)
        counts = {s: int(np.sum(codes == i)) for i, s in enumerate(STATES)}
        nonpresent = {}
        for seg in segments:
            if seg['state'] != 'PRESENT':
                key = seg['state'] + '|' + str(seg['reason'])
                nonpresent[key] = nonpresent.get(key, 0) + seg['rows']
        last = segments[-1]
        point_ids = [p['point_id'] for p in POINTS if _matches(entry['name'], p['series'])]
        out_series.append(dict(
            name=entry['name'], point_ids=point_ids, table=entry['table'], column=entry['column'], where=entry['where'],
            absent_reason=entry['absent_reason'], facts=_facts(entry, open_ns),
            known_values=[dict(published_ns=k['published_ns'], state=k['state'], value=k['value'], raw_value=k['raw_value'],
                               reason=k['reason'], row=k['row']) for k in entry['known']],
            alignment=dict(rows=dip['n'], state_counts=counts, nonpresent_rows_by_reason=dict(sorted(nonpresent.items())),
                           terminal_state=last['state'], terminal_value=last['value'], terminal_reason=last['reason'],
                           first_to_last_present_direction=direction, segments=segments)))

    dipole_dirs, dipole_ledgers = {}, {}
    for c in COLUMNS:
        d = _direction(np, dip['codes'][c], dip['values'][c])
        dipole_dirs[c] = d
        dipole_ledgers[c] = (dip['codes'][c], dip['values'][c], d)
    scan = []
    for e in names:                                       # each series against the 19 Dipole columns, in column order
        for c in COLUMNS:
            scan.append(_pair(np, e, c, 'EXTERNAL_DIPOLE', ledgers[e], dipole_ledgers[c]))
    for i, a in enumerate(names):                         # each series against every later series
        for b in names[i + 1:]:
            scan.append(_pair(np, a, b, 'EXTERNAL_EXTERNAL', ledgers[a], ledgers[b]))

    tables = {}
    for tname, t in body['points'].items():
        if tname in DEFERRED['tables']:
            continue                                   # deferred by Greg (squeeze): not read
        view = reader.until(tname, cutoff)
        i = view['columns'].index('published_ns')
        stamps = [r[i] for r in view['rows']]
        during = [s for s in stamps if s >= open_ns]
        info = dict(name=tname, rows_known=len(view['rows']), not_yet_known=view['not_yet_known'],
                    known_before_open=len(stamps) - len(during), published_in_day=len(during),
                    first_published_ns=min(stamps) if stamps else None, last_published_ns=max(stamps) if stamps else None,
                    columns=list(view['columns']), source=t.get('source'), vintage=t.get('vintage'),
                    native_resolution=t.get('native_resolution'), note=t.get('note'), after_halt=t.get('after_halt'))
        if tname in ROWS_CARRIED_WHOLE:
            info['rows'] = [dict(zip(view['columns'], r)) for r in view['rows']]
        tables[tname] = info
    missing = list(body.get('missing') or ())
    deferred_missing = [m for m in missing if _matches(str(m.get('point')), DEFERRED['missing'])]
    assigned = {id(m) for m in deferred_missing}
    points = []
    for p in POINTS:
        mine = [m for m in missing if _matches(str(m.get('point')), p['missing'])]
        assigned.update(id(m) for m in mine)
        points.append(dict(point_id=p['point_id'], name=p['name'],
                           series=[n for n in names if _matches(n, p['series'])],
                           series_patterns=list(p['series']),
                           tables=[tables.get(t, dict(name=t, absent=True, reason='not in the day file (see missing)'))
                                   for t in p['tables']],
                           missing=mine))
    unassigned_series = [n for n in names if not any(_matches(n, p['series']) for p in POINTS)]
    body_out = dict(
        schema=KEY_SCHEMA, request_id=snapshot['request_id'], cycle_index=snapshot['cycle_index'],
        source_snapshot_hash=snapshot['source_snapshot_hash'], teacher_attachment_hash=snapshot['teacher_attachment_hash'],
        trading_day=str(trading_day), cutoff_ns=cutoff, open_ns=open_ns, halt_ns=int(body['halt_ns']),
        rows=dip['n'], first_cursor=int(dip['cursors'][0]), last_cursor=int(dip['cursors'][-1]),
        first_row_ts_recv_ns=int(dip['ts'][0]), last_row_ts_recv_ns=int(dip['ts'][-1]),
        day_file=descriptor, points=points, point_count=len(POINTS),
        missing_not_assigned=[m for m in missing if id(m) not in assigned],
        deferred=dict(reason=DEFERRED['reason'], points=[dict(p, tables=list(p['tables'])) for p in DEFERRED['points']],
                      series=list(DEFERRED['series']), tables_not_read=[t for t in DEFERRED['tables'] if t in body['points']],
                      missing_entries_listed_here=deferred_missing,
                      note='left out of the classroom and the teacher\'s external section for now; not missing'),
        tables_not_in_a_point=sorted(t for t in tables if not any(t in p['tables'] for p in POINTS)),
        series_absent=absent, series_not_in_a_point=unassigned_series,
        series=out_series, series_count=len(out_series), dipole_directions=dipole_dirs,
        relationship_scan=scan, relationship_pairs_scanned=len(scan),
        external_dipole_pairs=len(names) * len(COLUMNS), external_external_pairs=len(names) * (len(names) - 1) // 2,
        min_pearson_present_overlap=MIN_PEARSON_PRESENT_OVERLAP,
        as_of_rule=('one read of the day file through AsOfReader.until at the classroom cutoff (the last Dipole row\'s '
                    'time); each Dipole row takes, per series, the latest value stamped at or before the row\'s own '
                    'ts_recv_ns; every aligned stamp is checked against its row; a value published after the cutoff '
                    'is counted in not_yet_known and never read'),
        causality_rule='OBSERVATION_INTERPRETATION_HYPOTHESIS_MUST_REMAIN_DISTINCT; NO FUTURE_OUTCOME CLAIM',
        additive_rule='the 19-column / 171-pair classroom key, pre-message and grade are not changed by this section')
    counter = [0]
    body_out = _finite(json.loads(json.dumps(body_out)), counter)   # native JSON types, non-finite floats as text
    body_out['non_finite_values_written_as_text'] = counter[0]
    body_out = json.loads(_canon(body_out))               # the hash is over what is written
    body_out['external_key_hash'] = evidence_hash(body_out)
    return body_out


def verify_external_key(key: Mapping[str, Any]) -> dict:
    if key.get('schema') != KEY_SCHEMA:
        raise ValueError('an external classroom key is required')
    if evidence_hash({k: v for k, v in key.items() if k != 'external_key_hash'}) != key.get('external_key_hash'):
        raise ValueError('the external classroom key changed')
    return dict(key)


def ensure_external_section(directory, snapshot, day_file, day_file_sha256, *, trading_day, built_by, extra=None):
    """The section, built ONCE per teacher rows directory: read and verified when it exists (same snapshot, same day
    file), built and written otherwise. Returns (key, receipt)."""
    directory = Path(directory) / SECTION_DIR
    path, receipt_path = directory / SECTION_FILE, directory / SECTION_RECEIPT
    if path.exists():
        receipt = json.loads(receipt_path.read_bytes())
        raw = path.read_bytes()
        if _sha256_bytes(raw) != receipt.get('section_sha256'):
            raise ValueError(f'{path} differs from its receipt; refused')
        if receipt.get('day_file_sha256') != day_file_sha256:
            raise DayExternalRefused(f'{path} was built from day file {receipt.get("day_file_sha256")}, not {day_file_sha256}')
        key = verify_external_key(json.loads(raw))
        if key['source_snapshot_hash'] != snapshot['source_snapshot_hash']:
            raise ValueError(f'{path} was built from another Dipole snapshot; refused')
        return key, dict(receipt, reused=True)
    key = build_external_key(snapshot, day_file, day_file_sha256, trading_day=trading_day)
    directory.mkdir(parents=True, exist_ok=True)
    raw = _canon(key).encode('utf-8')
    with path.open('xb') as f:
        f.write(raw)
    receipt = dict(schema=SECTION_RECEIPT_SCHEMA, trading_day=str(trading_day), built_by=built_by,
                   section_file=SECTION_FILE, section_sha256=_sha256_bytes(raw), section_bytes=len(raw),
                   external_key_hash=key['external_key_hash'], source_snapshot_hash=key['source_snapshot_hash'],
                   teacher_attachment_hash=key['teacher_attachment_hash'], day_file=key['day_file']['path'],
                   day_file_sha256=day_file_sha256, cutoff_ns=key['cutoff_ns'], rows=key['rows'],
                   series=key['series_count'], relationship_pairs=key['relationship_pairs_scanned'],
                   missing_listed=sum(len(p['missing']) for p in key['points']) + len(key['missing_not_assigned']),
                   series_absent=len(key['series_absent']), **(extra or {}))
    with receipt_path.open('x') as f:
        f.write(json.dumps(receipt, indent=1, sort_keys=True))
    return key, dict(receipt, reused=False)


# ---------------------------------------------------------------------------------------------- the pre-message
def prior_external_summary(grade):
    """WHERE Frankie was corrected on the previous day's external section, never the key (rule R10)."""
    if grade is None:
        return None
    if grade.get('schema') != GRADE_SCHEMA:
        raise ValueError('prior external correction must be an external post-grade')
    ids = list(grade.get('correction_ids') or ())
    return {'schema': PRIOR_SCHEMA, 'post_grade_hash': grade.get('post_grade_hash'), 'correction_ids': ids,
            'correction_count': len(ids), 'prior_cycle_mastered': grade.get('mastered') is True,
            'guidance': 'These identifiers mark prior-day misunderstandings only; recompute this day from its own evidence.'}


def _visible_series(s, mode):
    base = dict(name=s['name'], point_ids=s['point_ids'], table=s['table'], column=s['column'], where=s['where'],
                absent_reason=s['absent_reason'])
    if mode == 'TEACH':
        return dict(base, facts=s['facts'], known_values=s['known_values'], alignment=s['alignment'])
    if mode == 'GUIDED':
        return dict(base, known_values=s['known_values'], alignment=dict(segments=s['alignment']['segments'],
                                                                         rows=s['alignment']['rows']))
    return base


def build_external_pre_message(key, *, mode, prior_grade=None):
    key = verify_external_key(key)
    if mode not in classroom._MODES:
        raise ValueError('known classroom mode required')
    teach = mode == 'TEACH'
    body = dict(
        schema=MESSAGE_SCHEMA, request_id=key['request_id'], cycle_index=key['cycle_index'], mode=mode,
        external_key_hash=key['external_key_hash'], trading_day=key['trading_day'], day_file=key['day_file'],
        cutoff_ns=key['cutoff_ns'], open_ns=key['open_ns'], halt_ns=key['halt_ns'], rows=key['rows'],
        first_cursor=key['first_cursor'], last_cursor=key['last_cursor'],
        points=key['points'] if teach else [dict(point_id=p['point_id'], name=p['name'], series=p['series'],
                                                  missing=p['missing']) for p in key['points']],
        missing_not_assigned=key['missing_not_assigned'], deferred=key['deferred'], series_absent=key['series_absent'],
        series_not_in_a_point=key['series_not_in_a_point'], tables_not_in_a_point=key['tables_not_in_a_point'],
        series=[_visible_series(s, mode) for s in key['series']], series_count=key['series_count'],
        dipole_columns=list(COLUMNS),
        relationship_pairs=[[p['left'], p['right']] for p in key['relationship_scan']],
        relationship_pairs_required=key['relationship_pairs_scanned'],
        relationship_review=key['relationship_scan'] if teach else None,
        prior_cycle_correction=prior_external_summary(prior_grade), as_of_rule=key['as_of_rule'],
        teacher_opening=('Beside the 19 Dipole dimensions, this section teaches Frankie\'s historical data points (Greg\'s 13, the squeeze '
                         'points deferred) for '
                         'this trading day: every value known at this classroom\'s cutoff with the time it became public, '
                         'the value each Dipole row saw at its own time, and how each series relates to each Dipole column '
                         'and to every other series. A value not yet published at a row\'s time is MISSING for that row. '
                         'Missing values are listed with their reason; nothing is dropped. The squeeze points are deferred by Greg '
                         '(listed under deferred), not missing.'),
        relationship_instruction=(f'Consider all {key["relationship_pairs_scanned"]} external pairs ({key["external_dipole_pairs"]} '
                                  f'series x Dipole, {key["external_external_pairs"]} series x series). Pearson is reported only '
                                  f'with at least {MIN_PEARSON_PRESENT_OVERLAP} rows where both are PRESENT and nonzero variance; '
                                  'beside it each pair carries its co-movement COUNTS. Both are descriptive, not causation or a '
                                  'future outcome; each pair is read on its own, never flattened into one number across pairs.'),
        future_wall='DO_NOT_CLAIM_OR_USE_ANY_OUTCOME_OR_VALUE_NOT_PUBLISHED_AT_THIS_CUTOFF')
    body['teacher_message_hash'] = evidence_hash(body)
    return body


def build_external_binding(key, pre, *, v1_binding):
    body = dict(schema=BINDING_SCHEMA, request_id=key['request_id'], cycle_index=key['cycle_index'], mode=pre['mode'],
                v1_classroom_binding_hash=v1_binding['classroom_binding_hash'],
                v1_source_snapshot_hash=v1_binding['source_snapshot_hash'], external_key_hash=key['external_key_hash'],
                external_message_hash=pre['teacher_message_hash'], day_file_sha256=key['day_file']['sha256'],
                series_count=key['series_count'], point_count=key['point_count'],
                relationship_pairs_required=key['relationship_pairs_scanned'])
    if body['v1_source_snapshot_hash'] != key['source_snapshot_hash']:
        raise ValueError('the external section was built from another Dipole snapshot than the classroom package')
    body['external_binding_hash'] = evidence_hash(body)
    return body


def model_visible_external(binding, pre):
    value = dict(schema=VISIBLE_SCHEMA, binding=binding, pre_message=pre, audit_key_object_withheld=True,
                 coverage_invariant='EVERY_POINT_BUT_THE_DEFERRED_SQUEEZE_POINTS_EVERY_SERIES_EVERY_EXTERNAL_PAIR',
                 required_response_ledgers=dict(
                     external_teachback='EVERY_SERIES_WITH_ITS_FACTS_AND_THE_POINT_REVIEW',
                     external_value_review='EVERY_KNOWN_VALUE_OF_EVERY_SERIES',
                     external_relationship_scan=pre['relationship_pairs_required'],
                     external_novel_findings='ZERO_OR_MORE_HYPOTHESES_AFTER_REQUIRED_COVERAGE'))
    value['model_visible_hash'] = evidence_hash(value)
    return value


# ---------------------------------------------------------------------------------------------- validation and grade
LEDGERS = ('external_teachback', 'external_value_review', 'external_relationship_scan', 'external_novel_findings')
COMPONENT_FIELDS = {'name', 'state_counts', 'terminal_state', 'direction', 'facts', *NARRATIVE}
POINT_FIELDS = {'point_id', 'name', 'series', 'tables', 'missing_count', 'review'}


def _text(value, label):
    if type(value) is not str or not value.strip():
        raise ValueError(f'{label} must be nonempty text')
    return value


def validate_external_ledgers(ledgers, pre):
    """Shape of Frankie's external answers against the pre-message: every series in order, every known value, every
    pair in canonical order, every point of the section (Greg's 13 less the deferred point 6). Raises ValueError."""
    if type(ledgers) is not dict or set(ledgers) != set(LEDGERS):
        raise ValueError('the external ledgers differ from the contract')
    tb = ledgers['external_teachback']
    if tb.get('schema') != TEACHBACK_SCHEMA or tb.get('teacher_message_hash') != pre['teacher_message_hash']:
        raise ValueError('the external teach-back belongs to another message')
    if tb.get('future_outcome_claimed') is not False:
        raise ValueError('the external teach-back may not claim a future outcome')
    names = [s['name'] for s in pre['series']]
    comps = tb.get('components')
    if type(comps) is not list or [c.get('name') for c in comps] != names:
        raise ValueError('the external teach-back must cover every series in order')
    for c in comps:
        if set(c) != COMPONENT_FIELDS or c['terminal_state'] not in STATES or c['direction'] not in classroom._DIRECTIONS:
            raise ValueError(f'external component {c.get("name")} fields differ from the contract')
        for field in NARRATIVE:
            _text(c[field], f'external {c["name"]} {field}')
        if type(c['facts']) is not dict or set(c['facts']) != set(FACT_FIELDS):
            raise ValueError(f'external component {c["name"]} facts differ from the contract')
    points = tb.get('point_review')
    if type(points) is not list or [p.get('point_id') for p in points] != [p['point_id'] for p in pre['points']]:
        raise ValueError('the external teach-back must review every point of the section in order')
    for p in points:
        if set(p) != POINT_FIELDS:
            raise ValueError(f'external point {p.get("point_id")} fields differ')
        _text(p['review'], f'external point {p["point_id"]} review')
    for field in ('cycle_summary', 'correlation_review'):
        _text(tb.get(field), field)
    if type(tb.get('unresolved_questions')) is not list:
        raise ValueError('unresolved_questions must be a list')
    if tb.get('relationship_pairs_considered') != pre['relationship_pairs_required']:
        raise ValueError('Frankie must consider every external pair')
    review = ledgers['external_value_review']
    if type(review) is not list or [r.get('name') for r in review] != names:
        raise ValueError('the external value review must cover every series in order')
    for r in review:
        if type(r.get('values')) is not list or set(r) != {'name', 'values'}:
            raise ValueError(f'external value review {r.get("name")} fields differ')
        for v in r['values']:
            if type(v) is not dict or set(v) != {'published_ns', 'state', 'value', 'explanation'} or v['state'] not in STATES:
                raise ValueError(f'external value review {r["name"]} item fields differ')
            _text(v['explanation'], 'external value explanation')
    scan = ledgers['external_relationship_scan']
    if type(scan) is not list or [[p.get('left'), p.get('right')] for p in scan] != pre['relationship_pairs']:
        raise ValueError('the external relationship scan must keep the canonical pair order')
    for p in scan:
        if set(p) != {'left', 'right', 'direction_relation', 'correlation_interpretation', 'developing_structure'}:
            raise ValueError('external relationship scan fields differ')
        if p['direction_relation'] not in ('SAME_DIRECTION', 'OPPOSITE_DIRECTION', 'UNRESOLVED'):
            raise ValueError('external relationship outside the governed vocabulary')
        _text(p['correlation_interpretation'], 'external correlation interpretation')
        if p['developing_structure'] is not None:
            _text(p['developing_structure'], 'external developing structure')
    pairs = {tuple(p) for p in pre['relationship_pairs']}
    for f in ledgers['external_novel_findings']:
        if type(f) is not dict or set(f) != {'schema', 'finding_id', 'premise', 'why_novel', 'evidence_refs',
                                             'future_outcome_claimed'} or f['schema'] != NOVEL_SCHEMA:
            raise ValueError('external novel finding fields differ')
        if f['future_outcome_claimed'] is not False:
            raise ValueError('an external novel finding may not claim a future outcome')
        for ref in f['evidence_refs']:
            if (ref.get('left'), ref.get('right')) not in pairs:
                raise ValueError('an external novel finding cites a pair that is not in the scan')
    return dict(series=len(names), values=sum(len(r['values']) for r in review), pairs=len(scan),
                points=len(points), novel_findings=len(ledgers['external_novel_findings']))


def _same(a, b):
    return _canon(a) == _canon(b)


def grade_external(key, ledgers):
    """Point-by-point exact grade of the external section. Returns the post-grade (correction ids, data review items)."""
    key = verify_external_key(key)
    tb = ledgers['external_teachback']
    by_name = {s['name']: s for s in key['series']}
    pairs = {(p['left'], p['right']): p for p in key['relationship_scan']}
    corrections, items, component_grades, value_grades, relationship_grades, point_grades = [], [], [], [], [], []

    def correct(cid, message, **data):
        corrections.append(cid)
        items.append(dict(correction_id=cid, message=message, **data))

    for c in tb['components']:
        s = by_name[c['name']]
        a = s['alignment']
        checks = dict(state_counts=_same(c['state_counts'], a['state_counts']),
                      terminal_state=c['terminal_state'] == a['terminal_state'],
                      direction=c['direction'] == a['first_to_last_present_direction'],
                      **{f'facts.{f}': _same(c['facts'].get(f), s['facts'][f]) for f in FACT_FIELDS})
        wrong = sorted(k for k, ok in checks.items() if not ok)
        if wrong:
            correct('external-component:' + s['name'], f'{s["name"]}: {", ".join(wrong)} differ from the day file',
                    series=s['name'], expected=dict(state_counts=a['state_counts'], terminal_state=a['terminal_state'],
                                                    direction=a['first_to_last_present_direction'], facts=s['facts']))
        component_grades.append(dict(name=s['name'], checks=checks, correct=not wrong))
    for r in ledgers['external_value_review']:
        s = by_name[r['name']]
        want = [(k['published_ns'], k['state'], k['value']) for k in s['known_values']]
        got = [(v['published_ns'], v['state'], v['value']) for v in r['values']]
        ok = _same(got, want)
        if not ok:
            correct('external-values:' + s['name'], f'{s["name"]}: the known values differ from the day file '
                    f'({len(want)} expected, {len(got)} given)', series=s['name'],
                    expected=[dict(published_ns=p, state=st, value=v) for p, st, v in want])
        value_grades.append(dict(name=s['name'], expected=len(want), claimed=len(got), correct=ok))
    for p in ledgers['external_relationship_scan']:
        k = pairs[(p['left'], p['right'])]
        ok = p['direction_relation'] == k['direction_relation']
        if not ok:
            correct(f'external-relationship:{p["left"]}:{p["right"]}',
                    f'the exact directional relation is {k["direction_relation"]}, not {p["direction_relation"]}',
                    left=p['left'], right=p['right'], actual_relation=k['direction_relation'],
                    correlation=k['correlation'], co_movement=k['co_movement'])
        relationship_grades.append(dict(left=p['left'], right=p['right'], kind=k['kind'], claimed=p['direction_relation'],
                                        actual=k['direction_relation'], correct=ok, correlation=k['correlation'],
                                        co_movement=k['co_movement'], developing_structure=p['developing_structure']))
    for claimed, actual in zip(tb['point_review'], key['points']):
        want_tables = [dict(name=t['name'], rows_known=t.get('rows_known'), not_yet_known=t.get('not_yet_known'))
                       for t in actual['tables']]
        checks = dict(name=claimed['name'] == actual['name'], series=_same(claimed['series'], actual['series']),
                      tables=_same(claimed['tables'], want_tables), missing_count=claimed['missing_count'] == len(actual['missing']))
        wrong = sorted(k for k, ok in checks.items() if not ok)
        if wrong:
            correct(f'external-point:{actual["point_id"]}', f'point {actual["point_id"]}: {", ".join(wrong)} differ',
                    point_id=actual['point_id'], expected=dict(name=actual['name'], series=actual['series'],
                                                               tables=want_tables, missing=actual['missing']))
        point_grades.append(dict(point_id=actual['point_id'], checks=checks, correct=not wrong))
    corrections = list(dict.fromkeys(corrections))
    body = dict(schema=GRADE_SCHEMA, request_id=key['request_id'], cycle_index=key['cycle_index'],
                external_key_hash=key['external_key_hash'], teachback_hash=evidence_hash(ledgers),
                series_checked=len(component_grades), values_checked=sum(g['expected'] for g in value_grades),
                relationship_pairs_checked=len(relationship_grades), points_checked=len(point_grades),
                component_grades=component_grades, value_grades=value_grades, relationship_grades=relationship_grades,
                point_grades=point_grades, correction_ids=corrections, data_review_items=items,
                facts_correct=all(g['correct'] for g in component_grades) and all(g['correct'] for g in value_grades),
                relationships_correct=all(g['correct'] for g in relationship_grades),
                points_correct=all(g['correct'] for g in point_grades), mastered=not corrections,
                novel_findings_filed=len(ledgers['external_novel_findings']),
                unresolved_questions_reported=list(tb['unresolved_questions']),
                teacher_closing=('Every series, every known value, all external pairs and every point of the section were checked '
                                 'exactly against the day file read at this cutoff. The section is complete only when every '
                                 'correction is acknowledged and resolved.'))
    body = json.loads(_canon(body))
    body['post_grade_hash'] = evidence_hash(body)
    return body


def correction_request(*, original_request_sha256, session_id, model_identity, grade):
    if type(original_request_sha256) is not str or len(original_request_sha256) != 64:
        raise ValueError('original request sha256 required')
    if grade.get('schema') != GRADE_SCHEMA:
        raise ValueError('an external post-grade is required')
    body = dict(schema=CORRECTION_SCHEMA, original_request_sha256=original_request_sha256, session_id=session_id,
                model_identity_as_reported_by_session=model_identity, post_grade=grade,
                post_grade_hash=grade['post_grade_hash'], correction_ids=list(grade['correction_ids']),
                data_review_items=list(grade['data_review_items']),
                instruction=('The BOSS teacher\'s point-by-point correction of your external-section record. Stay in this '
                             'session, read every correction, resolve every correction_id with one '
                             '{correction_id, corrected_understanding} in correction_resolutions (an empty list when there '
                             'are none), state any remaining disagreement, and return dipole_acknowledgement.'))
    body['request_sha256'] = evidence_hash(body)
    return body


def finish_external(*, binding, key, pre, ledgers, grade, correction, reply, initial_session_id, model_identity):
    """Acknowledgement (the classroom's own validators) and the external completion. Raises on an unresolved correction."""
    from .dipole_classroom_resolution import validate_correction_resolutions
    if reply.get('session_id') != initial_session_id or reply.get('model_identity_as_reported_by_session') != model_identity:
        raise ValueError('the external correction must return from the same session')
    if reply.get('request_sha256') != correction['request_sha256']:
        raise ValueError('the external correction response belongs to another correction request')
    raw = reply.get('dipole_acknowledgement')
    base = classroom.validate_acknowledgement(raw, grade, session_id=initial_session_id)
    ack = validate_correction_resolutions(raw, grade, base)
    if ack['remaining_disagreements']:
        raise ValueError('the external section cannot be complete with an unresolved disagreement')
    audit = dict(every_series_covered=len(ledgers['external_teachback']['components']) == key['series_count'],
                 every_value_reviewed=grade['values_checked'] == sum(len(s['known_values']) for s in key['series']),
                 every_pair_reviewed=len(ledgers['external_relationship_scan']) == key['relationship_pairs_scanned'],
                 all_points_reviewed=len(ledgers['external_teachback']['point_review']) == key['point_count'],
                 every_correction_resolved=set(ack['resolved_correction_ids']) == set(grade['correction_ids']),
                 unresolved_disagreements=0)
    if not all(v for k, v in audit.items() if k != 'unresolved_disagreements'):
        raise ValueError('external section coverage incomplete: ' + json.dumps(audit, sort_keys=True))
    body = dict(schema=COMPLETION_SCHEMA, request_id=binding['request_id'], cycle_index=binding['cycle_index'],
                mode=binding['mode'], external_binding_hash=binding['external_binding_hash'],
                external_key_hash=key['external_key_hash'], teacher_message_hash=pre['teacher_message_hash'],
                post_grade_hash=grade['post_grade_hash'], ack_hash=ack['ack_hash'], mastered=grade['mastered'],
                acknowledged=True, series_count=key['series_count'], point_count=key['point_count'],
                relationship_pairs_reviewed=key['relationship_pairs_scanned'], day_file_sha256=key['day_file']['sha256'],
                teacher_complete=True, audit=audit)
    body['completion_hash'] = evidence_hash(body)
    return ack, body


def render_markdown(ledgers, grade=None):
    """Frankie's external teach-back, human-readable (every value is in the value review, not repeated here)."""
    def cell(text):
        return str(text).replace('\r', ' ').replace('\n', ' ').replace('|', '\\|').replace('```', "'''")
    tb = ledgers['external_teachback']
    lines = ['# Dipole classroom, external section: Frankie\'s historical data points (Frankie\'s code; no model)', '',
             f'Teacher message {tb["teacher_message_hash"]}; {len(tb["components"])} series; '
             f'{sum(len(r["values"]) for r in ledgers["external_value_review"])} known values reviewed; '
             f'{len(ledgers["external_relationship_scan"])} pairs; {len(ledgers["external_novel_findings"])} hypotheses filed.', '',
             '## Cycle summary', '', tb['cycle_summary'], '', '## Correlation review', '', tb['correlation_review'], '',
             '## Unresolved questions', '']
    lines += [f'- {cell(q)}' for q in tb['unresolved_questions']] or ['- none']
    lines += ['', '## The points (Greg\'s 13; point 6 and the squeeze spread change deferred by Greg)', '']
    for p in tb['point_review']:
        lines += [f'### {p["point_id"]}. {cell(p["name"])}', '', cell(p['review']), '']
    lines += ['## Series', '']
    for c in tb['components']:
        lines += [f'### {c["name"]}', '', f'state_counts {json.dumps(c["state_counts"], sort_keys=True)}; terminal '
                  f'{c["terminal_state"]}; direction {c["direction"]}', '']
        lines += [f'- {f}: {cell(c[f])}' for f in NARRATIVE] + ['']
    lines += ['## External relationship scan', '', '| left | right | relation | interpretation |', '|---|---|---|---|']
    lines += [f'| {p["left"]} | {p["right"]} | {p["direction_relation"]} | {cell(p["correlation_interpretation"])} |'
              for p in ledgers['external_relationship_scan']]
    lines += ['', '## Hypotheses filed', '']
    for f in ledgers['external_novel_findings']:
        lines += [f'- {cell(f["finding_id"])}: {cell(f["premise"])}']
    if not ledgers['external_novel_findings']:
        lines.append('none filed')
    if grade is not None:
        lines += ['', f'Host grade (on record): {len(grade["correction_ids"])} correction ids; mastered {grade["mastered"]}.']
    return '\n'.join(lines) + '\n'
