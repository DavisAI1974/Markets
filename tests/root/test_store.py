"""ROOT store, on the raw files held in markets-data only. Builds trade day Oct 2 twice into temporary folders."""
import datetime as dt
import os
from pathlib import Path

import pytest

from root import checks, rows, store

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get('MARKETS_DATA', REPO.parent / 'markets-data'))
TAPE = DATA / 'data' / 'nymex_mbo' / 'ng_v0_oct2023'
pytestmark = pytest.mark.skipif(not (TAPE / 'MANIFEST.json').exists(),
                                reason=f'the raw tape is not at {TAPE}; set MARKETS_DATA')
DAY = dt.date(2023, 10, 2)


@pytest.fixture(scope='module')
def built(tmp_path_factory):
    a, b = tmp_path_factory.mktemp('a'), tmp_path_factory.mktemp('b')
    return a, store.build(TAPE, DAY, a, checker=checks.RowChecker(DAY)), store.build(TAPE, DAY, b)


def test_same_result_twice(built):
    """Criterion 9: two runs on the same inputs give byte-identical stored files."""
    _, first, second = built
    for key in ('row_files', 'book_picture_files'):
        assert [(f['file'], f['sha256']) for f in first[key]] == [(f['file'], f['sha256']) for f in second[key]]
    assert first['vendor_restatement_file']['sha256'] == second['vendor_restatement_file']['sha256']


def test_the_stored_rows_are_the_rows_and_empties_are_empty(built):
    import pyarrow.parquet as pq
    folder, receipt, _ = built
    assert receipt['checks']['rows']['passed'] and receipt['checks']['accounted']['passed']
    total = 0
    for f in receipt['row_files']:
        t = pq.read_table(folder / f['file'])
        assert t.column_names == rows.NAMES
        total += t.num_rows
    assert total == receipt['rows']
    t = pq.read_table(folder / receipt['row_files'][0]['file']).to_pydict()
    k = t['action'].index('T')
    assert t['order_size_before'][k] is None and t['touched_line'][k] is None and t['left_price'][k] is None
    assert t['best_bid'][k] is not None and isinstance(t['level_emptied'][k], bool)


def test_a_book_picture_at_every_trade_and_at_the_first_and_last_row(built):
    import pyarrow.parquet as pq
    folder, receipt, _ = built
    assert receipt['book_pictures_at_trades'] == receipt['checks']['rows']['trade_rows']
    # trade day Oct 2 is the week's first: its first written row is the exchange's clear, so that picture is empty
    assert receipt['book_picture_at_first_written_row']['orders'] == 0
    last = pq.read_table(folder / receipt['book_picture_files'][-1]['file'], columns=['why']).to_pydict()['why']
    assert last[-1] == store.AT_LAST_ROW and receipt['book_picture_at_last_written_row']['orders'] == last.count(
        store.AT_LAST_ROW) > 0
    assert receipt['checks']['book_adds_up_at_every_trade']


def test_the_vendor_restatement_is_kept_and_matches(built):
    import pyarrow.parquet as pq
    folder, receipt, _ = built
    t = pq.read_table(folder / receipt['vendor_restatement_file']['file']).to_pydict()
    adds = [same for a, same in zip(t['action'], t['our_book_has_this_order_the_same']) if a == 'A']
    assert adds and all(adds) and t['action'][0] == 'R'
    assert all(c['equal'] for c in receipt['checks']['book_equals_restatement'])
