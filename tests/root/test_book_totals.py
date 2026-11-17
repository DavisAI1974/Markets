"""Part 2, Step 2 piece C: the book running totals. Real stored rows only. The full recount of every column, the
foundation's total sizes and the fill messages are the check run inside `root.run calc` on a whole trade day; here
the totals are read on a short real stretch."""
import datetime as dt
import itertools
import os
from pathlib import Path

import pytest

from root import tape
from root.calcs import book_totals as B

DAY = dt.date(2023, 10, 2)
ROWS = Path(os.environ.get('ROOT_ROWS', Path(__file__).resolve().parents[3])) / f'rows-{DAY:%Y%m%d}'
pytestmark = pytest.mark.skipif(not ROWS.is_dir(), reason=f'the stored rows of trade day {DAY} are not at {ROWS}; '
                                                          f'set ROOT_ROWS')
STRETCH = 60000                  # the first ticks of trade day Oct 2 read here


def test_the_side_total_is_its_size_at_the_open_plus_added_minus_pulled_minus_filled():
    extra = ['bid_total_size', 'ask_total_size']
    ticks = list(itertools.islice(tape.rows_for_calculations(ROWS, DAY, B.READS + extra), STRETCH))
    out = list(B.calculate((position, row[:len(B.READS)]) for position, row in ticks))
    at = {name: k for k, name in enumerate(B.NAMES)}
    assert len(out) == len(ticks) == STRETCH
    opens = {}
    for (position, row), (out_position, v) in zip(ticks, out):
        assert position == out_position
        for side, total in zip(B.SIDES.values(), row[len(B.READS):]):
            net = v[at[f'{side}_added']] - v[at[f'{side}_pulled']] - v[at[f'{side}_filled']]
            assert total - net == opens.setdefault(side, total - net)
            assert v[at[f'{side}_refilled']] <= v[at[f'{side}_added']]
            for part, whole in (('added_at_best', 'added'), ('pulled_at_best', 'pulled'), ('filled_at_best', 'filled'),
                                ('moved_from_best', 'moved'), ('moved_to_best', 'moved'),
                                ('refilled_at_best', 'refilled'), ('filled_no_side', 'filled')):
                assert v[at[f'{side}_{part}']] <= v[at[f'{side}_{whole}']]
    first, last = out[0][1], out[-1][1]
    assert all(a <= b for a, b in zip(first, last)) and sum(last) > sum(first)      # running totals only grow


def test_a_row_outside_the_rule_stops_the_run():
    """The refusal fires on a real row: a row of the Sunday start-up, where the exchange clears the book."""
    import pyarrow.parquet as pq
    from root import rows as R
    table = pq.read_table(tape.stored_row_files(ROWS, DAY)[0], columns=['position_on_tape'] + B.READS).slice(0, STRETCH)
    cleared = [row for row in zip(*[table.column(c).to_pylist() for c in ['position_on_tape'] + B.READS])
               if row[1 + B.READS.index('what_happened')] == R.CLEARED]
    if not cleared:
        pytest.skip('no clear among the first stored rows of this trade day')
    with pytest.raises(ValueError, match='outside the rule'):
        B.BookTotals().tick(*cleared[0])
