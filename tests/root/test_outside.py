"""Checks of ROOT's `outside` part on the real source files (SPEC-outside.md). No made-up data: every test reads the
source folder of markets-data. Set MARKETS_DATA to that repository; it defaults to a sibling checkout."""
import ast
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import shutil
import zipfile
from pathlib import Path

import pytest

from root.calendar import eastern, to_ns, trade_day_bounds
from root import outside

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get('MARKETS_DATA', REPO.parent / 'markets-data'))
SRC = DATA / 'data' / 'outside' / 'ng_oct2023'
TAPE = DATA / 'data' / 'nymex_mbo' / 'ng_v0_oct2023'
pytestmark = pytest.mark.skipif(not (SRC / 'MANIFEST.json').exists(),
                                reason=f'the outside source files are not at {SRC}; set MARKETS_DATA')


def table(folder, name):
    path = folder / name
    raw = gzip.decompress(path.read_bytes()) if name.endswith('.gz') else path.read_bytes()
    return list(csv.DictReader(io.StringIO(raw.decode())))


@pytest.fixture(scope='module')
def made(tmp_path_factory):
    first = tmp_path_factory.mktemp('first')
    second = tmp_path_factory.mktemp('second')
    return first, outside.build(SRC, first), outside.build(SRC, second)


def test_same_result_twice(made):
    _, a, b = made
    assert [(t['table'], t['sha256']) for t in a['tables']] == [(t['table'], t['sha256']) for t in b['tables']]


def test_every_empty_cell_has_a_reason(made):
    _, receipt, _ = made
    for e in receipt['empty']:
        assert e['reason'], e['table']


def test_every_input_matches_its_fingerprint(made):
    _, receipt, _ = made
    manifest = {f['stored']: f['stored_sha256'] for f in json.loads((SRC / 'MANIFEST.json').read_text())['files']}
    assert receipt['inputs'] and all(manifest[i['stored']] == i['sha256'] for i in receipt['inputs'])


def test_a_changed_fingerprint_is_refused(tmp_path):
    shutil.copy(SRC / 'MANIFEST.json', tmp_path / 'MANIFEST.json')
    m = json.loads((tmp_path / 'MANIFEST.json').read_text())
    stored = 'raw/cot/fut_disagg_txt_2023.zip'
    (tmp_path / stored).parent.mkdir(parents=True)
    shutil.copy(SRC / stored, tmp_path / stored)
    next(f for f in m['files'] if f['stored'] == stored)['stored_sha256'] = '0' * 64
    (tmp_path / 'MANIFEST.json').write_text(json.dumps(m))
    with pytest.raises(ValueError, match='differs from its fingerprint'):
        outside.Sources(tmp_path).bytes(stored)


def test_a_withheld_file_is_refused(tmp_path):
    shutil.copy(SRC / 'MANIFEST.json', tmp_path / 'MANIFEST.json')
    with pytest.raises(FileNotFoundError):
        outside.Sources(tmp_path).bytes('raw/cot/fut_disagg_txt_2023.zip')


def test_nothing_known_after_the_last_halt(made):
    folder, receipt, _ = made
    for t in receipt['tables']:
        assert all(int(r['known_from_ns']) < receipt['last_halt_ns'] for r in table(folder, t['table'])), t['table']


def test_positioning_matches_the_cftc_file(made):
    folder, _, _ = made
    with zipfile.ZipFile(SRC / 'raw/cot/fut_disagg_txt_2023.zip') as zf:
        cftc = [r for r in csv.DictReader(io.TextIOWrapper(zf.open('f_year.txt'), encoding='latin-1'))
                if r['CFTC_Contract_Market_Code'].strip() == '023651']
    rows = {r['report_date']: r for r in table(folder, 'positioning.csv') if r['contract_code'] == '023651'}
    _, last_halt = trade_day_bounds(dt.date.fromisoformat(outside.TRADE_DAYS[-1]))
    cftc = [r for r in cftc if to_ns(outside.positioning_release(
        dt.date.fromisoformat(r['Report_Date_as_YYYY-MM-DD']))) < last_halt]
    assert len(cftc) > 30
    for r in cftc:
        mine = rows[r['Report_Date_as_YYYY-MM-DD']]
        assert int(mine['managed_money_long']) == int(r['M_Money_Positions_Long_All'])
        assert int(mine['managed_money_short']) == int(r['M_Money_Positions_Short_All'])
        assert int(mine['managed_money_net']) == int(mine['managed_money_long']) - int(mine['managed_money_short'])


def test_positioning_release_rule():
    assert outside.positioning_release(dt.date(2023, 9, 26)) == eastern(dt.date(2023, 9, 29), dt.time(15, 30))
    # New Year's Day 2021 was a Friday: the release moves to Monday.
    assert outside.positioning_release(dt.date(2020, 12, 29)) == eastern(dt.date(2021, 1, 4), dt.time(15, 30))


def test_standing_is_empty_on_a_short_window(made):
    folder, _, _ = made
    for r in table(folder, 'positioning.csv'):
        assert (r['standing_1y'] == '') == (int(r['reports_in_1y']) < outside.MIN_REPORTS_1Y)
        assert (r['standing_3y'] == '') == (int(r['reports_in_3y']) < outside.MIN_REPORTS_3Y)


def test_sessions_since_expiry(made):
    folder, _, _ = made
    got = {r['trade_day']: (int(r['sessions_since_front_expiry']), r['last_expired_symbol'], r['last_expiry_date'])
           for r in table(folder, 'expiry.csv')}
    assert got == {'2023-10-02': (3, 'NGV23', '2023-09-27'), '2023-10-03': (4, 'NGV23', '2023-09-27'),
                   '2023-10-17': (14, 'NGV23', '2023-09-27'), '2023-10-18': (15, 'NGV23', '2023-09-27')}


def test_forecast_on_row_is_the_last_run_known_before_the_open(made):
    folder, _, _ = made
    gw = table(folder, 'forecast_gas_weighted.csv')
    for r in table(folder, 'forecast_on_row.csv'):
        opens, _ = trade_day_bounds(dt.date.fromisoformat(r['trade_day']))
        known = [g for g in gw if g['model'] == r['model'] and g['target_date_central'] == r['target_date_central']
                 and int(g['known_from_ns']) < opens]
        assert known, r
        last = max(known, key=lambda g: g['runtime_utc'])
        assert (r['runtime_utc_used'], r['gw_hdd']) == (last['runtime_utc'], last['gw_hdd'])


def test_a_missing_hour_stays_missing(made):
    """Boston has no routine reading at 12:00 UTC on Oct 2, 2023 (inside gas day Oct 1)."""
    folder, _, _ = made
    bos = next(r for r in table(folder, 'weather_gas_day_city.csv') if r['city'] == 'BOS' and r['gas_day'] == '2023-10-01')
    assert bos['routine_readings'] == '23'
    day = next(r for r in table(folder, 'weather_gas_day.csv') if r['gas_day'] == '2023-10-01')
    assert int(day['known_from_ns']) == to_ns(eastern(dt.date(2023, 10, 2), dt.time(10, 10)))


def test_carry_over_is_the_gas_days_before(made):
    folder, _, _ = made
    rows = table(folder, 'weather_gas_day.csv')
    by = {r['gas_day']: r['gw_hdd'] for r in rows}
    for r in rows:
        g = dt.date.fromisoformat(r['gas_day'])
        for k in (1, 2):
            assert r[f'gw_hdd_{k}_gas_days_before'] == by.get((g - dt.timedelta(days=k)).isoformat(), '')


def test_gas_burn_formula_and_every_us48_hour(made):
    folder, _, _ = made
    rows = table(folder, 'grid_us48.csv')
    for r in rows:
        if r['gas_mwh']:
            assert float(r['est_gas_burn_bcfd_rate']) == round(float(r['gas_mwh']) * 24 * 7900 / 1.035e9, 3)
    hours = {r['period_utc'] for r in rows}
    first = dt.datetime(2023, 9, 23)
    want = {(first + dt.timedelta(hours=h)).strftime('%Y-%m-%dT%H') for h in range(len(rows))}
    assert hours == want


def test_curve_front_trades_equal_the_order_tape(made):
    if not (TAPE / 'NG_v0_mbo_20231002.dbn.zst').exists():
        pytest.skip('order tape not held')
    import databento as db
    folder, _, _ = made
    tape = db.DBNStore.from_file(TAPE / 'NG_v0_mbo_20231002.dbn.zst').to_ndarray()
    front = int(tape['instrument_id'][len(tape) // 2])
    on_tape = int(((tape['action'] == b'T') & (tape['instrument_id'] == front)).sum())
    in_curve = sum(1 for r in table(folder, 'curve_trades.csv.gz')
                   if r['instrument_id'] == str(front) and r['source_file'].endswith('20231002.dbn.zst'))
    assert on_tape == in_curve


def test_settled_shape_at_each_open_is_the_previous_settlement(made):
    folder, _, _ = made
    rows = table(folder, 'curve_settled_shape.csv')
    stats = table(folder, 'curve_statistics.csv.gz')
    for day in outside.TRADE_DAYS:
        opens, _ = trade_day_bounds(dt.date.fromisoformat(day))
        known = [r for r in rows if int(r['known_from_ns']) < opens]
        assert known and known[-1]['front_symbol'] == 'NGX3'
        settles = [s for s in stats if s['raw_symbol'] == 'NGX3' and s['stat_type'] == '3' and s['price']
                   and int(s['known_from_ns']) < opens]
        assert float(known[-1]['front']) == round(float(settles[-1]['price']), 4)


def test_no_hidden_numbers():
    """Every number written into any ROOT module (every root/*.py) is a declared constant, a position in a record, a
    rounding width, or a calendar fact inside the functions named in root/DECLARED_CONSTANTS.md."""
    declared = (REPO / 'root' / 'DECLARED_CONSTANTS.md').read_text()
    exempt_functions = {'us_federal_holidays', 'nth', 'observed', 'to_ns'}
    for name in exempt_functions:
        assert f'`{name}`' in declared
    for path in sorted(str(f.relative_to(REPO)) for f in (REPO / 'root').glob('*.py')):
        tree = ast.parse((REPO / path).read_text())
        parents = {c: n for n in ast.walk(tree) for c in ast.iter_child_nodes(n)}
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and type(node.value) in (int, float)) or node.value in (0, 1):
                continue
            chain, p = [], node
            while p in parents:
                p = parents[p]
                chain.append(p)
            funcs = [c.name for c in chain if isinstance(c, ast.FunctionDef)]
            parent = parents[node]
            if not funcs and isinstance(chain[-2], (ast.Assign, ast.AnnAssign)):
                name = chain[-2].targets[0] if isinstance(chain[-2], ast.Assign) else chain[-2].target
                names = [e.id for e in getattr(name, 'elts', [name])]
                assert all(n.isupper() and f'`{n}`' in declared for n in names), (path, node.lineno, names)
                continue
            if isinstance(parent, (ast.Slice, ast.Subscript)) or (isinstance(parent, ast.UnaryOp) and
                                                                   isinstance(parents[parent], ast.Subscript)):
                continue
            if isinstance(parent, ast.Call) and getattr(parent.func, 'id', '') == 'round' and node is parent.args[-1]:
                continue
            if set(funcs) & exempt_functions:
                continue
            raise AssertionError(f'{path}:{node.lineno}: the number {node.value} is not declared')


# ---------------------------------------------------------------- X11, X12: storage
def test_storage_first_print_on_the_two_reports_the_trade_days_use(made):
    folder, _, _ = made
    rows = {r['week_ending']: r for r in table(folder, 'storage_weekly.csv')}
    assert (rows['2023-09-22']['level_first_print_bcf'], rows['2023-09-22']['change_from_first_prints_bcf'],
            rows['2023-09-22']['known_from_eastern']) == ('3359.0', '90.0', '2023-09-28T10:30:00-04:00')
    assert (rows['2023-10-06']['level_first_print_bcf'], rows['2023-10-06']['change_from_first_prints_bcf'],
            rows['2023-10-06']['known_from_eastern']) == ('3529.0', '84.0', '2023-10-12T10:30:00-04:00')


def test_storage_level_is_the_first_print_not_the_revised_one(made):
    """Fix 1: the week ending 2023-01-20 was first printed at 2,729 and later revised to 2,734."""
    folder, _, _ = made
    src = outside.Sources(SRC)
    mode, sheets = outside.xls_sheets(src, 'raw/storage/ngshistory.xls')
    head, cols = outside.labelled(sheets[outside.STORAGE_HISTORY_SHEET], outside.STORAGE_WEEK)
    history = {w: v[cols[outside.STORAGE_TOTAL]]
               for w, v in outside.dated_rows(sheets[outside.STORAGE_HISTORY_SHEET], mode, head)}
    rows = {r['week_ending']: r for r in table(folder, 'storage_weekly.csv')}
    assert history[dt.date(2023, 1, 20)] == 2734.0
    assert rows['2023-01-20']['level_first_print_bcf'] == '2729.0'


def test_storage_five_year_rule_as_in_the_original(made):
    folder, _, _ = made
    rows = table(folder, 'storage_weekly.csv')
    for r in rows:
        listed = [float(x.split(': ')[1]) for x in r['same_week_prior_5y_levels'].split('; ')] \
            if r['same_week_prior_5y_levels'] else []
        if r['vs_5yr_bcf']:
            assert len(listed) == outside.FIVE_YEAR_PRIOR_YEARS
            assert float(r['vs_5yr_bcf']) == round(float(r['level_first_print_bcf']) - sum(listed) / len(listed), 1)
        else:
            assert len(listed) < outside.FIVE_YEAR_PRIOR_YEARS, r['week_ending']
    sep22 = next(r for r in rows if r['week_ending'] == '2023-09-22')
    assert [int(x.split(':')[0]) for x in sep22['same_week_prior_5y_levels'].split('; ')] == [2018, 2019, 2020, 2021,
                                                                                               2022]


def test_storage_change_differs_from_the_eia_figure_only_after_a_revision(made):
    _, receipt, _ = made
    checks = receipt['storage_checks']
    assert checks['history_file_equals_api_series_weeks'] == 480
    differs = {d['week_ending']: d for d in checks['change_from_first_prints_differs_from_eia_current_net_change']}
    assert (differs['2023-01-27']['change_from_first_prints_bcf'],
            differs['2023-01-27']['eia_current_net_change_bcf']) == (-146.0, -151.0)
    assert not {'2023-09-15', '2023-09-22', '2023-09-29', '2023-10-06'} & set(differs)


def test_storage_estimate_is_empty_with_its_reason(made):
    folder, _, _ = made
    weekly = {r['week_ending']: r['change_from_first_prints_bcf'] for r in table(folder, 'storage_weekly.csv')}
    for r in table(folder, 'storage_estimate.csv'):
        assert r['estimate_bcf'] == '' and r['surprise_bcf'] == '' and r['estimate_missing_reason']
        assert r['actual_change_from_first_prints_bcf'] == weekly[r['week_ending']]


def test_storage_report_each_trade_day_carries(made):
    folder, _, _ = made
    rows = table(folder, 'storage_weekly.csv')
    known = sorted((int(r['known_from_ns']), r['week_ending']) for r in rows)
    expected = {'2023-10-02': '2023-09-22', '2023-10-03': '2023-09-22', '2023-10-17': '2023-10-06',
                '2023-10-18': '2023-10-06'}
    for day, week in expected.items():
        opens, halts = trade_day_bounds(dt.date.fromisoformat(day))
        assert [w for t, w in known if t <= opens][-1] == week
        assert not [w for t, w in known if opens < t <= halts]
