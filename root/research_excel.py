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
from root.research_threads import HUMP_ADDED, HUMP_COLUMNS, MOVE_COLUMNS, TRADE_READ, standing

LEFT_OUT = ['run_side_at_first_step', 'run_size_at_first_step', 'run_trades_at_first_step']   # the run of trades
NANO_DIGITS = 9                                        # a nanosecond inside a second, written 000000000
PINNED = dict(moves=('first_step_received_ns', 'first_step_eastern',
                     'Added here for reading: the Eastern date and time of its first step, to the nanosecond. The '
                     'row is pinned to first_step_received_ns.'),
              humps=('began_received_ns', 'began_eastern',
                     'Added here for reading: the Eastern date and time it began, to the nanosecond. The row is '
                     'pinned to began_received_ns.'))
LINE_FILE, MEASURE_FILE = 'crypto-ng-tick-line-20s', 'info-measure'   # the stored exhaustion line; the stored measure
SIGN = dict(buy=1, sell=-1)                            # a buying hump stands above zero, a selling hump below
MOMENTS = dict(moves=['first_step', 'end'], humps=['began', 'furthest', 'ended'])   # where the measure is read
MEASURE = [
    ('info_ratio', 'C_signed', 'THE INFORMATION RATIO (the operator\'s C_signed): the mean of the entropy of the '
     'twenty bought pieces and the entropy of the twenty sold pieces, over the information the two lists share, '
     'signed by the side that leads. HUGE WHERE info_ratio_made_by_division IS TRUE: do not read its size there.'),
    ('info_ratio_log', 'log_signed_C', 'Codex\'s form of the ratio: its sign times the logarithm of one plus its size.'),
    ('info_shared', 'mi_level', 'The information the twenty bought pieces and the twenty sold pieces share (the '
     'bottom of the ratio). Zero where all the trading of the 20 seconds is on one side.'),
    ('info_entropy_lean', 'ent_dipole', 'The operator\'s ent_dipole: the entropy of the bought pieces minus the '
     'entropy of the sold pieces, over their sum.'),
    ('info_flow', 'mi_flow', 'The operator\'s mi_flow: the shared information of the later ten pieces minus that of '
     'the earlier ten, signed by the side that leads.'),
    ('info_lean_change', 'imb_flow', 'The operator\'s imb_flow: bought minus sold over bought plus sold of the later '
     'ten seconds, minus the same of the earlier ten.'),
    ('info_pieces_with_a_trade', 'pieces_with_a_trade', 'How many of the twenty one-second pieces hold any trade '
     'with a side. A figure standing on one or two pieces stands on very little.'),
]
DIVISION = ('info_ratio_made_by_division', 'TRUE where the two lists share exactly nothing (all the trading of the 20 '
            'seconds is on one side): there the ratio is a number over the operator\'s smallest number, made by the '
            'division and not by the market. FALSE otherwise. Empty where nothing with a side traded.')
MEASURE_QUESTION = ('Codex\'s question: are large information ratios real, or made by thin trading? THE INFORMATION '
                    'MEASURE: the crypto information dipole operator on twenty one-second pieces counted back from '
                    'the read. NOT the dipole and NOT the exhaustion. Not yet compared with the original equations.')
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
    'THE INFORMATION MEASURE (added 2026-11-23; Greg: "If we can use the codex info now then do it"). The columns '
    'named info_... in the "moves" and "humps" sheets are Codex\'s information measure: the crypto information '
    'dipole operator (odcore/info_dipole.py, called unchanged) on twenty one-second pieces of bought and sold size '
    'counted back from the read, looked up from info-measure/info-measure-<trade day>.parquet at the same tick as '
    'the exhaustion beside it. It is NOT the dipole and NOT the exhaustion. WHERE info_ratio_made_by_division IS '
    'TRUE the ratio is made by the division (all the trading of the 20 seconds was on one side) and its size says '
    'nothing. Not yet compared with the original dipole equations (set aside for further research).',
]


def eastern(ns: int) -> str:
    moment = dt.datetime.fromtimestamp(ns // NS_PER_SECOND, tz=dt.timezone.utc).astimezone(EASTERN)
    return f'{moment:%Y-%m-%d %H:%M:%S}.{ns % NS_PER_SECOND:0{NANO_DIGITS}d}'


def laid_out(kind: str) -> tuple:
    """The columns of one kind of sheet in the order written, each with its question and what it holds."""
    described = dict(TABLES[kind][1])
    stamp, added, added_what = PINNED[kind]
    extra = [(f'{name}_at_{mark}', f'At its {mark.replace("_", " ")}, read at that tick (the read of the stored '
              f'exhaustion line standing there, by place on the tape). {what}')
             for mark in MOMENTS[kind] for name, what in [(n, w) for n, _, w in MEASURE] + [DIVISION]]
    described.update(extra)
    named = {name for _, names in QUESTIONS[kind] if not isinstance(names, str) for name in names}
    out = []
    for question, names in QUESTIONS[kind]:
        if isinstance(names, str):                     # every other stored column whose name starts this way
            names = [name for name in described if name.startswith(names) and name not in named]
        for name in names:
            out.append((question, name, described[name]))
            if name == stamp:
                out.append((question, added, added_what))
    out += [(MEASURE_QUESTION, name, what) for name, what in extra]
    written = [name for _, name, _ in out if name != added]
    assert len(written) == len(set(written)) and set(written) == set(described) - set(LEFT_OUT), \
        (kind, 'a stored column is under no question, or under two')
    return out


def measure_at(checkout: Path, day: str, kind: str, stored: dict) -> dict:
    """The stored information measure looked up at each line's moments: at the read of the stored exhaustion line
    standing at that tick, found by place on the tape. A look-up of stored values; nothing is worked out."""
    import numpy as np
    line = pq.read_table(checkout / 'crypto-ng-tick' / f'{LINE_FILE}-{day}.parquet',
                         columns=['moment_received_ns', 'what', 'position_on_tape', 'flow']).to_pydict()
    line = dict(moments=np.array(line['moment_received_ns'], np.int64), what=line['what'],
                position=line['position_on_tape'], flow=line['flow'])
    measure = pq.read_table(checkout / 'info-measure' / f'{MEASURE_FILE}-{day}.parquet',
                            columns=['read'] + [name for _, name, _ in MEASURE]).to_pydict()
    assert measure['read'] == list(range(len(line['flow']))), (day, 'the measure is not one line per read of the line')
    count = len(next(iter(stored.values())))
    out = {f'{name}_at_{mark}': [None] * count for mark in MOMENTS[kind] for name in [n for n, _, _ in MEASURE] + [DIVISION[0]]}

    def at_moment(at: int, fits) -> int:
        a, b = (int(np.searchsorted(line['moments'], at, edge)) for edge in ('left', 'right'))
        return next((r for r in range(a, b) if fits(r)), None)

    for k in range(count):
        reads = {}
        if kind == 'moves':
            for mark, when, where in (('first_step', 'first_step_received_ns', 'first_step_position'),
                                      ('end', 'end_received_ns', 'end_position')):
                if stored[when][k] is not None:
                    reads[mark] = standing(line, stored[when][k], stored[where][k])
                    value = line['flow'][reads[mark]] if reads[mark] >= 0 else None
                    assert same(value, stored[f'exhaustion_20s_at_{mark}'][k]) if value is not None else \
                        stored[f'exhaustion_20s_at_{mark}'][k] is None, (day, kind, k, mark, 'not the read the table used')
        else:
            sign = SIGN[stored['side'][k]]
            first = at_moment(stored['began_received_ns'][k],
                              lambda r: line['flow'][r] is not None and line['flow'][r] * sign > 0)
            reads['began'] = first
            reads['furthest'] = at_moment(stored['furthest_received_ns'][k],
                                          lambda r: r >= first and line['flow'][r] == stored['furthest_flow'][k])
            if stored['ended_received_ns'][k] is not None:
                reads['ended'] = at_moment(stored['ended_received_ns'][k],
                                           lambda r: line['flow'][r] is None or line['flow'][r] * sign <= 0)
            assert all(r is not None for r in reads.values()), (day, kind, k, 'a moment of a hump is no read of the line')
            assert (line['position'][first] if line['what'][first] == TRADE_READ else None) == stored['began_position'][k]
        for mark, r in reads.items():
            if r is None or r < 0:
                continue
            for name, source, _ in MEASURE:
                out[f'{name}_at_{mark}'][k] = measure[source][r]
            shared = measure['mi_level'][r]
            out[f'{DIVISION[0]}_at_{mark}'][k] = None if shared is None else shared == 0
    return out


def lines_of(checkout: Path, day: str, kind: str) -> tuple:
    stem, _ = TABLES[kind]
    stamp, added, _ = PINNED[kind]
    stored = pq.read_table(checkout / 'research-threads' / f'{stem}-{day}.parquet').to_pydict()
    stored.update(measure_at(checkout, day, kind, stored))
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
            if title in before:                        # written again whole when it is already there
                book.remove(book[title])
            header, lines = lines_of(checkouts / day, day, kind)
            place += 1
            sheet = book.create_sheet(title, place)
            sheet.append(header)
            for line in lines:
                sheet.append(line)
            wanted[title] = [header] + lines
    page = [['sheet', 'research question', 'column', 'what it holds']] + [
        [f'{kind} <trade day>', question, name, what] for kind in TABLES for question, name, what in laid_out(kind)]
    if 'RESEARCH COLUMNS' in before:
        book.remove(book['RESEARCH COLUMNS'])
    columns = book.create_sheet('RESEARCH COLUMNS', book.worksheets.index(book['READ ME']) + 1)
    for line in page:
        columns.append(line)
    wanted['RESEARCH COLUMNS'] = page
    first = book['READ ME']
    new = [line for line in READ_ME if [line] not in before['READ ME']]   # a line already there is not added twice
    for line in new:
        first.append([line])
    wanted['READ ME'] = before['READ ME'] + [[line] for line in new]
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
