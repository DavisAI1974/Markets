"""ROOT rows, on the raw files held in markets-data only (no made-up message, ever). Every check sees every row of a
whole box (root.checks.RowChecker); nothing is sampled."""
import datetime as dt
import os
from pathlib import Path

import pytest

from root import checks, rows, tape
from root.calendar import STARTUP, STRETCH, TRADE_DAY

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get('MARKETS_DATA', REPO.parent / 'markets-data'))
TAPE = DATA / 'data' / 'nymex_mbo' / 'ng_v0_oct2023'
pytestmark = pytest.mark.skipif(not (TAPE / 'MANIFEST.json').exists(),
                                reason=f'the raw tape is not at {TAPE}; set MARKETS_DATA')
DAYS = [dt.date(2023, 10, d) for d in (2, 3, 17, 18)]
I = rows.INDEX


@pytest.fixture(scope='module')
def walked():
    out = {}
    for day in DAYS:
        week = tape.read_week(TAPE, day)
        checker, walk = checks.RowChecker(day), rows.Walk(week, day)
        for r in walk:
            checker.see(r)
        out[day] = dict(checker=checker, result=checker.result(),
                        accounted=checks.accounted(week, day, walk.stats, checker.result()))
    return out


def test_every_row_passes_and_every_record_is_accounted_for(walked):
    """Criteria 1, 2, 5 and 6 on every row of all four boxes."""
    for w in walked.values():
        assert w['result']['passed'] and w['accounted']['passed']
        assert w['result']['trade_rows_in_the_trade_day'] > 0
        assert w['result']['orders_ended'] <= w['result']['orders_seen']


def test_only_the_first_trade_day_of_a_week_writes_the_sunday_start_up(walked):
    assert STARTUP in walked[DAYS[0]]['result']['rows_by_label']
    for day in DAYS[1:]:
        assert set(walked[day]['result']['rows_by_label']) == {TRADE_DAY, STRETCH}


def test_the_shared_stretch_is_the_same_rows_in_both_boxes(walked):
    """The 5 pm to 6 pm stretch between two built trade days is written by both boxes and must be identical."""
    for first, second in ((DAYS[0], DAYS[1]), (DAYS[2], DAYS[3])):
        a = {r[I['position_on_tape']]: r for r in walked[first]['checker'].stretch_rows}
        b = {r[I['position_on_tape']]: r for r in walked[second]['checker'].stretch_rows}
        shared = set(a) & set(b)
        assert shared and all(a[p] == b[p] for p in shared)


def test_orders_from_before_the_written_record_exist_only_in_the_second_week(walked):
    before = {d: walked[d]['result']['rows_of_orders_from_before_the_written_record'] for d in DAYS}
    assert before[DAYS[0]] == before[DAYS[1]] == 0 and before[DAYS[2]] > 0


def test_playback_rows_do_not_change_when_the_tape_is_cut():
    """Criterion 8 at four cuts: inside an exchange event, across 6 pm, across the file boundary, across 5 pm."""
    day = DAYS[1]
    cuts = checks.playback(tape.read_week(TAPE, day), day)
    assert len(cuts) >= 3 and all(c['identical'] and c['rows_compared'] > 0 for c in cuts)
