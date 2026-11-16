"""ROOT book, on the raw files held in markets-data only (no made-up message, ever)."""
import datetime as dt
import os
from pathlib import Path

import pytest

from root import book, tape
from root.calendar import STARTUP, label

REPO = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get('MARKETS_DATA', REPO.parent / 'markets-data'))
TAPE = DATA / 'data' / 'nymex_mbo' / 'ng_v0_oct2023'
pytestmark = pytest.mark.skipif(not (TAPE / 'MANIFEST.json').exists(),
                                reason=f'the raw tape is not at {TAPE}; set MARKETS_DATA')


@pytest.fixture(scope='module')
def records():
    return {d: book.check_book(TAPE, d) for d in (dt.date(2023, 10, 3), dt.date(2023, 10, 18))}


def test_the_carried_book_equals_the_vendor_restatement_at_every_later_file(records):
    """Criterion 3, at all five file boundaries of the two weeks."""
    seen = []
    for r in records.values():
        for c in r['book_equals_restatement']:
            seen.append(c['file'])
            assert c['equal'], c
            assert c['orders_in_restatement'] == c['orders_in_our_book'] > 0
    assert len(seen) == 5


def test_the_book_adds_up_at_every_boundary_and_every_trade(records):
    """Criterion 4."""
    for r in records.values():
        assert r['all_add_up']
        assert r['whole_book_figures'][-1]['trades_checked'] > 0


def test_every_trade_message_of_the_week_was_checked(records):
    week = tape.read_week(TAPE, dt.date(2023, 10, 3))
    trades = sum(int((f.records[f.vendor_snapshot:]['action'] == book.TRADE).sum()) for f in week)
    assert records[dt.date(2023, 10, 3)]['whole_book_figures'][-1]['trades_checked'] == trades


def test_no_message_was_left_unapplied(records):
    for r in records.values():
        assert not [reason for reason in r['irregular'] if reason.startswith('not applied')]
        assert 'a cancel for more than was resting' not in r['irregular']


def test_the_sequence_number_goes_backwards_only_inside_the_sunday_start_up():
    week = tape.read_week(TAPE, dt.date(2023, 10, 3))
    last, outside, inside = None, 0, 0
    for f in week:
        c = tape.columns(f.records[f.vendor_snapshot:])
        for sq, te in zip(c['sequence'], c['ts_event']):
            if last is not None and sq < last:
                if label(te)[0] == STARTUP:
                    inside += 1
                else:
                    outside += 1
            last = sq
    assert outside == 0 and inside > 0


def test_a_restatement_is_never_applied_to_the_book():
    """The Oct 3 file's restatement was received at 8 pm Eastern; an order from the Sunday start-up still resting
    then keeps its Sunday times in our book (applying the restatement would not change them, but re-seating would)."""
    week = tape.read_week(TAPE, dt.date(2023, 10, 3))
    b, _, _ = book.carry_week(week)
    carried = [o for o in b.orders.values() if o.carried_over_weekend]
    assert carried and all(label(o.entered_event)[0] == STARTUP for o in carried)
    assert all(o.placed_event <= o.entered_event or o.steps > 1 for o in carried)
