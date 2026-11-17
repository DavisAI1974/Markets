"""Part 2, piece 2: what each peak did before and after. Real tape only. The full recount of every fact is the
check run inside `root.run calc` on a whole trade day; here the facts are read on a short real stretch."""
import datetime as dt
import itertools
import os
from pathlib import Path

from root import part2, tape
from root.calcs import peak_story as P

TAPE = Path(os.environ.get('MARKETS_DATA', '../markets-data')) / 'data' / 'nymex_mbo' / 'ng_v0_oct2023'
DAY = dt.date(2023, 10, 2)
STRETCH = 60000                  # the first ticks of trade day Oct 2 read here


def test_every_fact_is_known_after_its_high_and_a_story_ends_once():
    week = tape.read_week(TAPE, DAY)
    tables = {}
    out = list(P.calculate(itertools.islice(part2.gated(week, DAY), STRETCH), {}, tables))
    facts = [dict(zip(P.FACT_NAMES, row)) for row in tables['facts']]
    assert facts and sum(values[0] for _, values in out) == len(facts)
    by_peak = {}
    for f in facts:
        assert f['known_position'] > f['peak_high_position'] and f['since_high_ns'] >= 0
        assert f['fact'] in P.KINDS
        by_peak.setdefault(f['peak_high_position'], []).append(f)
    for story in by_peak.values():
        kinds = [f['fact'] for f in story]
        assert kinds[0] == P.BUILD_UP and kinds.count(P.BUILD_UP) == 1
        assert kinds.count(P.BEATEN) + kinds.count(P.CAME_BACK) <= 1          # a story ends once
        if P.CAME_BACK in kinds:
            assert kinds[-1] == P.CAME_BACK and kinds[-2] == P.REACHED_ZERO
        if P.BEATEN in kinds:
            assert kinds[-1] == P.BEATEN and P.REACHED_ZERO not in kinds
        lows = [f['share_of_peak_left'] for f in story if f['fact'] == P.NEW_LOW]
        assert lows == sorted(lows, reverse=True) and all(0 < x < 1 for x in lows)     # each one lower than the last
        for f in story:
            if f['fact'] == P.REACHED_ZERO:
                assert f['share_of_peak_left'] is None or f['share_of_peak_left'] <= 0
            if f['fact'] == P.BEATEN:
                assert f['share_of_peak_left'] > 1
