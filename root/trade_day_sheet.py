"""ROOT: ONE SHEET FOR EACH TRADE DAY in `ROOT_dipoles_pinned.xlsx`. Everything is a column on that sheet.

Greg, 2026-11-23: "Keep the trade day data on one sheet. Can't we make additional columns instead of new sheets? I'm
afraid the new sheets won't be used."

WHAT THE FILE HOLDS AFTER THIS: a READ ME page, a COLUMNS page, and ONE sheet "trade day <trade day>" for each of
the four trade days. On that sheet:
- EVERY TRADE ON THE TAPE IS A ROW, in tape order, pinned to its own nanosecond (text, 19 digits) with the Eastern
  time beside it.
- EVERYTHING ELSE IS A BLOCK OF COLUMNS, filled in on the row at its own timestamp: a move in price where it takes
  its first step, a hump of the exhaustion line where it begins, a trade of the crypto and ng program where it
  starts, one of Native's dipoles at its birth second, a 20-second peak at its high. What sits on a trade's own
  tick is on that trade's row.
- WHAT HAPPENS WHERE NO TRADE SITS (the quote stepping with no trade, a hump beginning as old trades leave the 20
  seconds, Native's birth second) has its own row at its own timestamp, so nothing is moved off its time. Two
  things of one kind on one tick: the second has the row under it.
The earlier separate sheets (dipoles, peaks, crypto and ng, moves, humps) are taken into it, every value and every
picture link, and are no longer separate sheets. Nothing is worked out: stored values are written or looked up at a
tick by place on the tape. NO MID PRICE. Then everything is read back and compared.

    python3 -m root.trade_day_sheet <the workbook> <folder holding one checkout per trade day> <peak research folder>
"""
from __future__ import annotations

import collections
import datetime as dt
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

from root.calendar import EASTERN, NS_PER_SECOND
from root.crypto_ng_excel import ADDED as PROGRAM_ADDED
from root.crypto_ng_excel import DAYS, label, links_of, same, values
from root.crypto_ng_tick import TRADE_COLUMNS
from root.research_excel import DIVISION, LEFT_OUT, MEASURE, MEASURE_QUESTION, NANO_DIGITS, PINNED, laid_out, lines_of
from root.research_threads import standing

KEY = [('received_ns', 'THE TIMESTAMP THIS ROW IS PINNED TO: its nanosecond on the received clock (text, 19 digits).'),
       ('eastern', 'Added for reading: the Eastern date and time of that nanosecond.'),
       ('position_on_tape', 'The tick this row sits on: its position on the tape. Empty where the row is a moment '
        'with no tick (old trades leaving the 20 seconds; the start of one of Native\'s birth seconds).'),
       ('on_this_row', 'Which things sit on this row: trade, move, hump, program trade, native dipole, peak.')]
TRADE = [
    ('side', 'buy or sell: the tape\'s own aggressor side. Empty when the tape gives none.'),
    ('size', 'Its size, in lots.'),
    ('price', 'Its price, in dollars.'),
    ('exhaustion_20s_before', 'THE EXHAUSTION LINE just before this trade was received (stored).'),
    ('exhaustion_20s', 'THE EXHAUSTION LINE at this trade: bought minus sold over bought plus sold, the trades of the '
     'last 20 seconds, this trade in it; read at the tick by place on the tape. Above zero buying, below selling.'),
    ('dipole_60s', 'THE DIPOLE LINE at this trade: the same figure over the last 60 seconds, read the same way.'),
    ('program_trade_under_way', 'The trade of the crypto and ng program under way as this trade was received.'),
    ('starts_program_trade', 'The trade of the program this trade started (it filled it).'),
    ('ends_program_trade', 'The trade of the program this trade ended.'),
]
FRAME = 'E2'                                           # the header row and the four key columns stay in view
STORED = dict(side='side', size='size', price='price', exhaustion_20s_before='flow_20s_before',
              program_trade_under_way='program_trade_under_way', starts_program_trade='starts_program_trade',
              ends_program_trade='ends_program_trade')
OLD = dict(program=('crypto and ng', 'start_eastern', 'onset_received_ns', 'onset_position_on_tape'),
           native_dipole=('dipoles', 'born_eastern', 'native_birth_ns', None),
           peak=('peaks', 'high_eastern', None, 'peak_high_position'))
WORDS = dict(trade='trade', move='move', hump='hump', program='program trade', native_dipole='native dipole', peak='peak')
RECORD = dict(native_dipole='NATIVE\'S RECORD of one of its dipoles, pinned to its birth second on our tape. A record '
                            'only: Native is built on fixed windows and is not used in our work.',
              peak='A 20-SECOND PEAK. A record only: the 20-second peak family is out of every calculation (Greg, '
                   '2026-11-18).')
READ_ME = [
    'ONE SHEET FOR EACH TRADE DAY (Greg, 2026-11-23: "Keep the trade day data on one sheet. Can\'t we make additional '
    'columns instead of new sheets?"). Sheets named "trade day <trade day>". The page COLUMNS lists every column, the '
    'block it belongs to, the research question it answers and what it holds.',
    'EVERY TRADE ON THE TAPE IS A ROW, in tape order. Every row is PINNED TO ITS TIMESTAMP: received_ns is its own '
    'nanosecond (text, 19 digits; Excel would round it as a number) and eastern is the same moment for reading.',
    'EVERYTHING ELSE IS A BLOCK OF COLUMNS on that sheet, filled in on the row at its own timestamp. The column names '
    'start with the block: trade. (the trade and the lines at it), move. (a move in price: a trade leg, a run of the '
    'best bid, a run of the best offer; on the row of its first step), hump. (a hump of the 20-second exhaustion '
    'line; on the row where it began), program. (a trade of the crypto and ng program; on the row of its start), '
    'native_dipole. (one of Native\'s dipoles; at the start of its birth second), peak. (a 20-second peak; on the '
    'row of its high). The column on_this_row says which of them a row holds.',
    'A ROW WITH NO TRADE IN IT is something that happened where no trade sits: the quote stepping with no trade, a '
    'hump beginning as old trades left the 20 seconds, Native\'s birth second. It has its own row at its own '
    'timestamp so nothing is moved off its time. Where two things of one kind sit on one tick, the second has the '
    'row under it.',
    'DIPOLE AND EXHAUSTION ARE THE CRYPTO FORMULAS made on the natural gas tape (Greg, 2026-11-23): bought minus sold '
    'over bought plus sold, over the trades of the last 60 seconds (dipole) and the last 20 seconds (exhaustion), '
    'read at the tick by place on the tape: no trade that came after the tick is in a read. Above zero buying, '
    'below zero selling. NO MID PRICE IS IN THIS FILE: the best bid and the best offer are each their own column. No '
    'crypto market data is in it.',
    'THE INFORMATION MEASURE (columns with info_ in the name; Greg: "If we can use the codex info now then do it") is '
    'Codex\'s measure: the crypto information dipole operator on twenty one-second pieces counted back from the '
    'read. It is NOT the dipole and NOT the exhaustion. WHERE info_ratio_made_by_division IS TRUE the ratio is made '
    'by the division (all the trading of the 20 seconds was on one side) and its size says nothing. Not yet compared '
    'with the original dipole equations (on the list of further research).',
    'THE program. COLUMNS are the July 2026 crypto trading program run on the natural gas tape: OBSERVATION AND '
    'VERIFICATION ONLY. Its mid-price figures and fee mark are left out. THE native_dipole. AND peak. COLUMNS are '
    'records only. Left out of the move. columns until Greg says: ' + ', '.join(LEFT_OUT) + '.',
    'Tap a name in program.picture or native_dipole.render to open that picture on GitHub.',
    'Written from the stored tables of each trade day\'s root-rows branch (crypto-ng-tick/, research-threads/, '
    'info-measure/) and from the earlier sheets of this file, which are taken into the trade day sheets whole. '
    'Nothing is worked out, nothing is averaged, and no row is left out. Empty cells are empty: never zero. Yes or no '
    'cells are TRUE or FALSE. Excel keeps a decimal to about 15 digits; the stored files are the exact record.',
    'A trade day runs 6 pm Eastern the evening before to 5 pm Eastern on the named date. The research questions are '
    'the earlier research\'s; none of its values is carried. The counts read from these tables are leads: no test of '
    'chance has been made.',
]


def eastern(ns: int) -> str:
    moment = dt.datetime.fromtimestamp(ns // NS_PER_SECOND, tz=dt.timezone.utc).astimezone(EASTERN)
    return f'{moment:%Y-%m-%d %H:%M:%S}.{ns % NS_PER_SECOND:0{NANO_DIGITS}d}'


def a_line(folder: Path, name: str, day: str) -> dict:
    held = pq.read_table(folder / 'crypto-ng-tick' / f'{name}-{day}.parquet',
                         columns=['moment_received_ns', 'what', 'position_on_tape', 'flow']).to_pydict()
    return dict(moments=np.array(held['moment_received_ns'], np.int64), what=held['what'],
                position=held['position_on_tape'], flow=held['flow'])


def trade_block(folder: Path, day: str) -> tuple:
    """Every trade on the tape with the two lines and the measure at its own tick."""
    t = pq.read_table(folder / 'crypto-ng-tick' / f'crypto-ng-tick-tape-trades-{day}.parquet').to_pydict()
    line, lean = a_line(folder, 'crypto-ng-tick-line-20s', day), a_line(folder, 'crypto-ng-tick-lean-60s', day)
    measure = pq.read_table(folder / 'info-measure' / f'info-measure-{day}.parquet',
                            columns=[source for _, source, _ in MEASURE]).to_pydict()
    names = [name for name, _ in TRADE] + [name for name, _, _ in MEASURE] + [DIVISION[0]]
    out = []
    for k in range(len(t['position_on_tape'])):
        at, place = t['received_time_ns'][k], t['position_on_tape'][k]
        r, r60 = standing(line, at, place), standing(lean, at, place)
        row = {name: t[source][k] for name, source in STORED.items()}
        row['exhaustion_20s'] = line['flow'][r] if r >= 0 else None
        row['dipole_60s'] = lean['flow'][r60] if r60 >= 0 else None
        if t['read_20s'][k] is not None:               # a trade with a side: the read is its own
            assert r == t['read_20s'][k] and same(row['exhaustion_20s'], t['flow_20s_at'][k]) \
                if row['exhaustion_20s'] is not None else t['flow_20s_at'][k] is None, (day, k, 'not the trade\'s read')
        if r >= 0:
            for name, source, _ in MEASURE:
                row[name] = measure[source][r]
            shared = measure['mi_level'][r]
            row[DIVISION[0]] = None if shared is None else shared == 0
        out.append((at, place, [row.get(name) for name in names], None))
    return names, out


def research_block(folder: Path, day: str, kind: str) -> tuple:
    """The moves or the humps as written into their earlier sheets, each with its own timestamp and tick."""
    header, lines = lines_of(folder, day, kind)
    stamp, added, _ = PINNED[kind]
    keep = [k for k, name in enumerate(header) if name != added]
    where = header.index('first_step_position' if kind == 'moves' else 'began_position')
    return [header[k] for k in keep], [(int(line[header.index(stamp)]), line[where], [line[k] for k in keep], None)
                                       for line in lines]


def old_block(book, day: str, kind: str, when: dict) -> tuple:
    """One of the earlier sheets of the file, taken whole: every value and every picture link."""
    title, reading, stamp, tick = OLD[kind]
    sheet = book[f'{title} {label(day)}']
    rows, links = values(sheet), links_of(sheet)
    header = rows[0]
    keep = [k for k, name in enumerate(header) if name != reading]
    out = []
    for n, row in enumerate(rows[1:], start=FIRST_DATA_ROW):
        row = row + [None] * (len(header) - len(row))
        place = row[header.index(tick)] if tick else None
        at = int(row[header.index(stamp)]) if stamp else when[place]
        link = [links.get(f'{get_column_letter(k + 1)}{n}') for k in keep]
        out.append((at, place, [row[k] for k in keep], link))
    return [header[k] for k in keep], out


FIRST_DATA_ROW = 2                                     # a sheet's first row is its header


def one_day(book, folder: Path, day: str, peaks_folder: Path) -> tuple:
    when = dict(zip(*(pq.read_table(peaks_folder / f'peaks-by-place-in-the-move-{day}.parquet',
                                    columns=['peak_high_position', 'peak_high_received_time_ns']).to_pydict().values())))
    blocks = collections.OrderedDict()
    blocks['trade'] = trade_block(folder, day)
    blocks['move'] = research_block(folder, day, 'moves')
    blocks['hump'] = research_block(folder, day, 'humps')
    for kind in OLD:
        blocks[kind] = old_block(book, day, kind, when)
    header = [name for name, _ in KEY]
    start = {}
    for kind, (names, _) in blocks.items():
        start[kind] = len(header)
        header += [f'{kind}.{name}' for name in names]
    rows = collections.defaultdict(list)               # a timestamp and tick -> the rows that sit there
    for kind, (names, items) in blocks.items():
        for at, place, cells, links in items:
            here = rows[(at, place)]
            row = next((r for r in here if kind not in r), None)
            if row is None:
                row = {}
                here.append(row)
            row[kind] = (cells, links)
    lines, linked = [], {}
    for (at, place) in sorted(rows, key=lambda key: (key[0], key[1] is not None, key[1] or 0)):
        for row in rows[(at, place)]:
            line = [str(at), eastern(at), place, ' + '.join(WORDS[kind] for kind in blocks if kind in row)] \
                + [None] * (len(header) - len(KEY))
            for kind, (cells, links) in row.items():
                line[start[kind]:start[kind] + len(cells)] = cells
                for k, link in enumerate(links or []):
                    if link:
                        linked[(len(lines) + FIRST_DATA_ROW, start[kind] + k + 1)] = link
            lines.append(line)
    counts = {kind: len(items) for kind, (_, items) in blocks.items()}
    return header, lines, linked, counts


def described(day_header: list) -> list:
    """The COLUMNS page: every column, its block, the research question it belongs to and what it holds."""
    what = {name: ('', text) for name, text in KEY}
    for name, text in TRADE:
        what[f'trade.{name}'] = ('The trade price curve, and the natural gas exhaustion and dipole at every trade', text)
    for name, _, text in list(MEASURE) + [(DIVISION[0], None, DIVISION[1])]:
        what[f'trade.{name}'] = (MEASURE_QUESTION, 'At this trade, read at its tick. ' + text)
    for kind, block in (('moves', 'move'), ('humps', 'hump')):
        for question, name, text in laid_out(kind):
            what[f'{block}.{name}'] = (question, text)
    program = dict(TRADE_COLUMNS)
    program.update(dict(PROGRAM_ADDED))
    out = [['column', 'block', 'research question', 'what it holds']]
    for name in day_header:
        block = name.split('.')[0] if '.' in name else 'the row'
        if name in what:
            question, text = what[name]
        elif block == 'program':
            question, text = 'The crypto and ng program\'s own trades (observation and verification only)', \
                program.get(name.split('.', 1)[1], '')
        else:
            question, text = RECORD[block], 'As stored for it (see the READ ME page).'
        out.append([name, block, question, text])
    return out


def write(sheet, lines: list, linked: dict = None):
    """Only the filled cells are written, so an empty cell is truly empty."""
    for n, line in enumerate(lines, start=1):
        for k, value in enumerate(line, start=1):
            if value is not None:
                sheet.cell(row=n, column=k, value=value)
    for (n, k), link in (linked or {}).items():
        sheet.cell(row=n, column=k).hyperlink = link


def main():
    book_path, checkouts, peaks_folder = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    old = load_workbook(book_path)
    new = Workbook()
    new.remove(new.active)
    wanted, links_wanted, header = {}, {}, None
    made = {}
    for day in DAYS:
        header, lines, linked, counts = one_day(old, checkouts / day, day, peaks_folder)
        made[day] = (header, lines, linked, counts)
    pages = {'READ ME': [[line] for line in READ_ME], 'COLUMNS': described(header)}
    for title, page in pages.items():
        write(new.create_sheet(title), page)
        wanted[title], links_wanted[title] = page, []
    for day, (header, lines, linked, counts) in made.items():
        title = f'trade day {label(day)}'
        sheet = new.create_sheet(title)
        write(sheet, [header] + lines, linked)
        sheet.freeze_panes = FRAME
        wanted[title], links_wanted[title] = [header] + lines, sorted(linked.values())
        was = sorted(target for kind in OLD for target in links_of(old[f'{OLD[kind][0]} {label(day)}']).values())
        assert links_wanted[title] == was, (day, 'a picture link of the earlier sheets is not in the trade day sheet')
        print(f'{title}: {len(lines)} rows, {len(header)} columns; in it: '
              + ', '.join(f'{n} {WORDS[kind]}s' for kind, n in counts.items()))
    del old
    new.save(book_path)
    del new, made

    back = load_workbook(book_path)                    # everything read back and compared
    assert [s.title for s in back.worksheets] == list(wanted), 'the sheets are not the ones written'
    for sheet in back.worksheets:
        got, want = values(sheet), wanted[sheet.title]
        assert len(got) == len(want), (sheet.title, len(got), len(want))
        for n, (a, b) in enumerate(zip(want, got)):
            a = list(a)
            while a and a[-1] is None:
                a.pop()
            assert len(a) == len(b) and all(same(x, y) for x, y in zip(a, b)), (sheet.title, n)
        assert sorted(links_of(sheet).values()) == links_wanted[sheet.title], (sheet.title, 'its links are not right')
        print(f'{sheet.title}: {len(got) - 1} rows read back equal, {len(links_wanted[sheet.title])} links')
    print('bytes', book_path.stat().st_size)


if __name__ == '__main__':
    main()
