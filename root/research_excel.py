"""ROOT: the research threads put into the trade day sheets of `ROOT_dipoles_pinned.xlsx`.

Greg, 2026-11-23, on the column list put to him: "Yes make columns for each new research question and fill in data
pinned to timestamp"; "Yes to your 3 suggestions".

WHAT THIS DOES TO THE FILE, and nothing else:
1. ADDS, for each of the four trade days, a sheet "moves <trade day>" (one row per move in price: a trade leg, a
   run of the best bid, a run of the best offer) and a sheet "humps <trade day>" (one row per hump of the stored
   20-second exhaustion line), written from the stored `research-threads/research-moves-<trade day>.parquet` and
   `research-humps-<trade day>.parquet` (made with every stored line read by place on the tape).
2. EVERY ROW IS PINNED TO ITS TIMESTAMP: its own nanosecond on the received clock (written as text, 19 digits) and,
   added here for reading, the Eastern date and time of that nanosecond.
3. ADDS a sheet "RESEARCH COLUMNS": every column of the new sheets under the research question it belongs to,
   with what it holds.
4. ADDS lines to the READ ME page that say what the new sheets are. No other line of it is changed.
LEFT OUT of the "moves" sheets, on his yes: the three stored columns of the run of trades under way at a first step
(its side, its size, its number of trades). They stay in the stored table.
No other sheet is touched. Nothing is worked out: stored values are written into sheets. NO MID PRICE. The dipole
and the exhaustion are the stored crypto-formula lines made on the natural gas tape. Then everything is read back
and compared.

    python3 -m root.research_excel <the workbook> <folder holding one checkout per trade day, named <trade day>>
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import pyarrow.parquet as pq
from openpyxl import load_workbook

from root.calendar import EASTERN, NS_PER_SECOND
from root.crypto_ng_excel import DAYS, label, links_of, same, values
from root.research_threads import HUMP_ADDED, HUMP_COLUMNS, MOVE_COLUMNS

LEFT_OUT = ['run_side_at_first_step', 'run_size_at_first_step', 'run_trades_at_first_step']   # the run of trades
NANO_DIGITS = 9                                        # a nanosecond inside a second, written 000000000
PINNED = dict(moves=('first_step_received_ns', 'first_step_eastern',
                     'Added here for reading: the Eastern date and time of its first step, to the nanosecond. The '
                     'row is pinned to first_step_received_ns.'),
              humps=('began_received_ns', 'began_eastern',
                     'Added here for reading: the Eastern date and time it began, to the nanosecond. The row is '
                     'pinned to began_received_ns.'))
TABLES = dict(moves=('research-moves', MOVE_COLUMNS), humps=('research-humps', list(HUMP_COLUMNS) + HUMP_ADDED))
WHICH = 'Which line this is, and its timestamp'
QUESTIONS = dict(moves=[
    (WHICH, ['move', 'direction', 'move_start_position']),
    ('How much of a move is left at the first moment it can be known?',
     ['first_step_position', 'first_step_received_ns', 'first_step_price', 'second_step_received_ns', 'steps_in_all',
      'end_position', 'end_received_ns', 'end_price']),
    ('Do large moves come back? (Only the first step back is here: the question is NOT answered by this column.)',
     ['given_back']),
    ('The thin quote, and the best price against the whole side of the book, at the start of a move',
     ['best_bid_at_first_step', 'best_ask_at_first_step', 'best_bid_size_at_first_step', 'best_ask_size_at_first_step',
      'best_bid_orders_at_first_step', 'best_ask_orders_at_first_step', 'bid_total_size_at_first_step',
      'ask_total_size_at_first_step']),
    ('The natural gas exhaustion and dipole lines as they stood at a move\'s first step and at its end',
     ['exhaustion_20s_at_first_step', 'dipole_60s_at_first_step', 'exhaustion_20s_at_end', 'dipole_60s_at_end']),
    ('A move in the trade prints against a move in the quote: the print bouncing, or the quote really stepping?',
     ['best_bid_at_end', 'best_ask_at_end', 'best_bid_at_first_trade', 'best_ask_at_first_trade']),
    ('Does a level that was eaten lead on, and a level that was only pulled lead nowhere?',
     ['level_orders_at_turn', 'level_size_at_turn', 'level_left_by_fill', 'level_left_by_cancel',
      'level_still_resting_orders', 'level_moved_orders']),
], humps=[
    (WHICH, ['hump', 'side', 'began_received_ns', 'ended_received_ns', 'length_seconds']),
    ('Is a change in flow fresh trading, or old trades leaving the span?',
     ['how_it_began', 'how_it_ended', 'began_on', 'began_position', 'ended_on', 'trades_inside']),
    ('The dive, the flip and the tail of the exhaustion and the dipole against the price, one event at a time',
     ['furthest_flow', 'furthest_received_ns', 'first_trade_position', 'last_trade_position', 'first_trade_price',
      'last_trade_price', 'highest_trade_price', 'lowest_trade_price', 'first_trade_leg', 'last_trade_leg',
      'trade_legs_under_way']
     + [f'{what}_at_{mark}' for mark in ('began', 'furthest', 'ended') for what in ('best_bid', 'best_ask', 'dipole_60s')]),
    ('Which comes first after an event begins: the trade, or the quote stepping?', 'next_'),
    ('Is anything observable before an event begins?', 'last_'),
])
READ_ME = [
    'THE RESEARCH THREADS (added 2026-11-23; Greg: "make columns for each new research question and fill in data '
    'pinned to timestamp"). Sheets named "moves <trade day>": one row per move in price (a trade leg, a run of the '
    'best bid, a run of the best offer). Sheets named "humps <trade day>": one row per hump of the 20-second '
    'exhaustion line (the time it stays on one side of zero).',
    'The sheet "RESEARCH COLUMNS" lists every column of those sheets under the research question it belongs to. The '
    'questions are the earlier research\'s; none of its values is carried.',
    'Every row of those sheets is pinned to its timestamp: its own nanosecond on the received clock (text, 19 '
    'digits) and the Eastern time added beside it. Written from research-threads/research-moves-<trade day>.parquet '
    'and research-humps-<trade day>.parquet on each trade day\'s root-rows branch. Nothing is worked out, nothing is '
    'averaged, and no row is left out.',
    'In those sheets the exhaustion (20 seconds) and the dipole (60 seconds) are the stored crypto-formula lines '
    'made on the natural gas tape, read AT THE TICK by place on the tape: no trade that came after the tick is in a '
    'read. As stored: above zero buying, below zero selling. NO MID PRICE: the best bid and the best offer are each '
    'their own column.',
    'Left out of the "moves" sheets until Greg says: ' + ', '.join(LEFT_OUT) + ' (the run of trades under way at a '
    'first step). Yes or no cells are written TRUE or FALSE.',
]


def eastern(ns: int) -> str:
    moment = dt.datetime.fromtimestamp(ns // NS_PER_SECOND, tz=dt.timezone.utc).astimezone(EASTERN)
    return f'{moment:%Y-%m-%d %H:%M:%S}.{ns % NS_PER_SECOND:0{NANO_DIGITS}d}'


def laid_out(kind: str) -> tuple:
    """The columns of one kind of sheet in the order written, each with its question and what it holds."""
    described = dict(TABLES[kind][1])
    stamp, added, added_what = PINNED[kind]
    named = {name for _, names in QUESTIONS[kind] if not isinstance(names, str) for name in names}
    out = []
    for question, names in QUESTIONS[kind]:
        if isinstance(names, str):                     # every other stored column whose name starts this way
            names = [name for name in described if name.startswith(names) and name not in named]
        for name in names:
            out.append((question, name, described[name]))
            if name == stamp:
                out.append((question, added, added_what))
    written = [name for _, name, _ in out if name != added]
    assert len(written) == len(set(written)) and set(written) == set(described) - set(LEFT_OUT), \
        (kind, 'a stored column is under no question, or under two')
    return out


def lines_of(checkout: Path, day: str, kind: str) -> tuple:
    stem, _ = TABLES[kind]
    stamp, added, _ = PINNED[kind]
    stored = pq.read_table(checkout / 'research-threads' / f'{stem}-{day}.parquet').to_pydict()
    header = [name for _, name, _ in laid_out(kind)]
    count = len(stored[stamp])
    lines = []
    for k in range(count):
        line = []
        for name in header:
            if name == added:
                line.append(eastern(stored[stamp][k]))
            else:
                value = stored[name][k]
                line.append(str(value) if name.endswith('_ns') and value is not None else value)
        lines.append(line)
    return header, lines


def main():
    book_path, checkouts = Path(sys.argv[1]), Path(sys.argv[2])
    book = load_workbook(book_path)
    before = {sheet.title: values(sheet) for sheet in book.worksheets}
    links_before = {sheet.title: links_of(sheet) for sheet in book.worksheets}
    wanted = {}
    for day in DAYS:
        place = book.worksheets.index(book[f'crypto and ng {label(day)}'])
        for kind in TABLES:
            title = f'{kind} {label(day)}'
            assert title not in before, (title, 'is already in the file')
            header, lines = lines_of(checkouts / day, day, kind)
            place += 1
            sheet = book.create_sheet(title, place)
            sheet.append(header)
            for line in lines:
                sheet.append(line)
            wanted[title] = [header] + lines
    page = [['sheet', 'research question', 'column', 'what it holds']] + [
        [f'{kind} <trade day>', question, name, what] for kind in TABLES for question, name, what in laid_out(kind)]
    assert 'RESEARCH COLUMNS' not in before, 'RESEARCH COLUMNS is already in the file'
    columns = book.create_sheet('RESEARCH COLUMNS', book.worksheets.index(book['READ ME']) + 1)
    for line in page:
        columns.append(line)
    wanted['RESEARCH COLUMNS'] = page
    first = book['READ ME']
    for line in READ_ME:
        first.append([line])
    wanted['READ ME'] = before['READ ME'] + [[line] for line in READ_ME]
    book.save(book_path)
    del book, sheet, columns, first                    # the file as written is read back on its own

    back = load_workbook(book_path)                    # everything read back and compared
    for sheet in back.worksheets:
        got = values(sheet)
        want = wanted.get(sheet.title, before.get(sheet.title))
        assert want is not None, (sheet.title, 'a sheet nobody wrote')
        assert len(got) == len(want), (sheet.title, len(got), len(want))
        for n, (a, b) in enumerate(zip(want, got)):
            a = list(a)
            while a and a[-1] is None:
                a.pop()
            assert len(a) == len(b) and all(same(x, y) for x, y in zip(a, b)), (sheet.title, n, a, b)
        untouched = sheet.title not in wanted
        linked = links_of(sheet)
        assert linked == links_before.get(sheet.title, {}), (sheet.title, 'its links changed')
        print(f'{sheet.title}: {len(got) - 1} rows, {len(linked)} links, read back equal'
              + (' (not touched)' if untouched else ''))
    assert [s.title for s in back.worksheets if s.title not in wanted] == \
        [title for title in before if title not in wanted], 'a sheet that was there is gone'
    print('bytes', book_path.stat().st_size)


if __name__ == '__main__':
    main()
