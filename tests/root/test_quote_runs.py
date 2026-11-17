"""Part 2, Step 2 piece I, first part: the runs of the best bid and of the best ask. Real stored rows only. The
full recount of every fact from the foundation's marks is the check run inside `root.run calc` on a whole trade
day; here the facts are read on a short real stretch."""
import datetime as dt
import itertools
import os
from pathlib import Path

import pytest

from root import tape
from root.calcs import quote_runs as Q

DAY = dt.date(2023, 10, 2)
ROWS = Path(os.environ.get('ROOT_ROWS', Path(__file__).resolve().parents[3])) / f'rows-{DAY:%Y%m%d}'
pytestmark = pytest.mark.skipif(not ROWS.is_dir(), reason=f'the stored rows of trade day {DAY} are not at {ROWS}; '
                                                          f'set ROOT_ROWS')
STRETCH = 60000                  # the first ticks of trade day Oct 2 read here


def test_every_move_of_a_best_price_is_one_turn_of_one_run_and_a_step_back_starts_the_next():
    ticks = list(itertools.islice(tape.rows_for_calculations(ROWS, DAY, Q.READS), STRETCH))
    tables = {}
    out = list(Q.calculate(iter(ticks), {}, tables))
    facts = [dict(zip(Q.FACT_NAMES, row)) for row in tables['facts']]
    assert facts and sum(values[-1] for _, values in out) == len(facts)
    best = {Q.BEST_BID: Q.READS.index('best_bid'), Q.BEST_ASK: Q.READS.index('best_ask')}
    for quote, column in best.items():
        prices = [row[column] for _, row in ticks]
        moves = sum(1 for a, b in zip(prices, prices[1:]) if a != b)
        mine = [f for f in facts if f['quote'] == quote]
        assert moves == sum(1 for f in mine if f['fact'] in (Q.STARTED, Q.FURTHER))       # one turn per move
        runs = {}
        for f in mine:
            assert f['known_position'] >= f['run_start_position'] and f['since_run_start_ns'] >= 0
            assert f['price_now'] != f['price_before_tick']
            runs.setdefault(f['run_start_position'], []).append(f)
        ordered = sorted(runs)
        for start, following in zip(ordered, ordered[1:] + [None]):
            story = runs[start]
            kinds = [f['fact'] for f in story]
            assert kinds[0] == Q.STARTED and kinds.count(Q.STARTED) == 1 and story[0]['known_position'] == start
            assert kinds.count(Q.STEP_BACK) == (0 if following is None else 1)
            sign = 1 if story[0]['direction'] == Q.UP else -1
            for f in story:
                assert f['direction'] == story[0]['direction'] and sign * f['distance'] > 0
            if following is not None:                      # the step back is the same tick the next run starts at,
                back = story[-1]                           # and it comes first on that tick
                assert back['fact'] == Q.STEP_BACK and back['known_position'] == following
                assert sign * back['step_back'] < 0 and back['moves'] == len(story) - 1
                assert runs[following][0]['direction'] != story[0]['direction']
                order = [(f['run_start_position'], f['fact']) for f in mine if f['known_position'] == following]
                assert order == [(start, Q.STEP_BACK), (following, Q.STARTED)]
    still = tables['open-at-the-end']
    assert {line[0] for line in still} <= set(Q.QUOTES) and len(still) == len({line[0] for line in still})
