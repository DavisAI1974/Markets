"""ROOT: the trade day sheets of `ROOT_dipoles_pinned.xlsx` brought up to date.

Greg, 2026-11-18: "Bring back the program and just designate it crypto and ng ... its crypto outputs if are any will
now go into our excel sheet. They would be for observation or verification purpose only". Greg, 2026-11-23, on
being put what the file holds and what it does not: "Yes".

WHAT THIS DOES TO THE FILE, and nothing else:
1. ADDS a sheet "crypto and ng <trade day>" for each of the four trade days: one row per trade of the crypto and
   ng program, read from the stored `crypto-ng-tick/crypto-ng-tick-program-trades-<trade day>.parquet`. Beside
   the program's own columns: the price it was bought at and the price it was sold at, each the price of the
   trade ON THE TAPE that filled it there (`crypto-ng-tick-tape-trades-<trade day>.parquet`, looked up by the
   stored position; empty where the trade ended at no tick, because nothing traded there), the EXHAUSTION LINE as
   it stood at its start (the stored 20-second line, `crypto-ng-tick-line-20s-<trade day>.parquet`, at the read
   the program's own `onset_read_20s` points to: that column is the number of a read, not a value), and the
   picture drawn for it where one is stored. A buy is bought at its start and sold at its end; a sell is sold at its start and
   bought at its end.
   LEFT OUT until Greg says: `program_open_px`, `program_close_px`, `program_gross_bps`, `program_net_bps` and
   `program_swing_bps` (made from the mid price: his word of 2026-11-23, nothing of the mid goes in a sheet) and
   `program_close_maker` (the program's fee mark).
2. TAKES OUT of each "peaks <trade day>" sheet the two columns that name a page of exhaustion pictures (`sheet`,
   `panel`): those pages were deleted on his word on 2026-11-18. Every other value of those sheets stays.
3. WRITES THE READ ME PAGE AGAIN, so it says what the file holds now.
The "dipoles <trade day>" sheets are not touched. Nothing is worked out: stored values are written into sheets.
OBSERVATION AND VERIFICATION ONLY: nothing here is a signal or an input. Then everything is read back and compared.

    python3 -m root.crypto_ng_excel <the workbook> <folder holding one checkout per trade day, named <trade day>>
"""
from __future__ import annotations

import datetime as dt
import subprocess
import sys
from pathlib import Path

import pyarrow.parquet as pq
from openpyxl import load_workbook

from root.calendar import EASTERN, NS_PER_SECOND
from root.crypto_ng_tick import TRADE_COLUMNS

DAYS = ['20231002', '20231003', '20231017', '20231018']                # the four trade days, and no other
LEFT_OUT = ['program_open_px', 'program_close_px', 'program_gross_bps', 'program_net_bps', 'program_swing_bps',
            'program_close_maker']                                     # mid price figures and the fee mark
PAGE_COLUMNS = ['sheet', 'panel']                                      # the peaks sheets' pointers to deleted pages
PICTURES = ['trade-renders-quotes-test', 'trade-renders']              # where a trade's picture is stored, newest first
LINK = 'https://github.com/DavisAI1974/markets-data/blob/root-rows-{day}/{folder}/{name}'
SIDES = dict(buy=('start', 'end'), sell=('end', 'start'))              # where it was bought, where it was sold
CLOSE = 1e-12                                                          # Excel keeps a decimal to about 15 digits
ADDED = [('start_eastern', 'Added here for reading: the Eastern date and time of its start, to the second.'),
         ('exhaustion_20s_at_start', 'THE EXHAUSTION LINE as it stood at its start: bought minus sold over bought plus '
          'sold over the trades of the last 20 seconds, at the read made as the trade that filled it was received '
          '(the stored line, looked up by onset_read_20s). As stored: above zero buying, below zero selling; NOT '
          'turned to the trade\'s side. The trade that filled it is in it, and that trade is on the other side '
          'from the program\'s own. Empty where nothing with a side had traded in the 20 seconds.'),
         ('bought_price', 'The price it was bought at, in dollars: the price of the trade on the tape that filled it '
          'there. A buy is bought at its start, a sell at its end. Empty where it ended at no tick or is still open.'),
         ('sold_price', 'The price it was sold at, in dollars: the price of the trade on the tape that filled it '
          'there. A sell is sold at its start, a buy at its end. Empty where it ended at no tick or is still open.'),
         ('picture', 'The picture drawn for this trade, where one is stored. Tap it to open it on GitHub.')]
READ_ME = [
    'Native\'s dipoles pinned to their birth seconds on OUR tape; every exhaustion peak (the 20-second peaks); and '
    'every trade of the crypto and ng program.',
    'Sheets named "dipoles <trade day>": one row per dipole. Sheets named "peaks <trade day>": one row per '
    'exhaustion peak (the 20-second peaks). Sheets named "crypto and ng <trade day>": one row per trade of the '
    'crypto and ng program.',
    'CRYPTO AND NG is the July 2026 crypto trading program run on the natural gas tape as it was, at the nanosecond '
    '(Greg, 2026-11-18). Its sheets are for OBSERVATION AND VERIFICATION ONLY: never a signal, never an input.',
    'Tap the name in the picture column to open that picture on GitHub (that trade day\'s root-rows branch).',
    'Written from renders/dipoles-pinned-<trade day>.parquet and, in crypto-ng-tick/, the stored program-trades, '
    'tape-trades and line-20s tables of each trade day (the exact record). Nothing is worked out and nothing is '
    'averaged.',
    'The peaks sheets were written on 2026-11-17 from the index of the exhaustion peak pages. Those pages and their '
    'index were deleted on 2026-11-18 (Greg), so the two columns that named a page were taken out on 2026-11-23. The '
    'rows stay as the record of the 20-second peaks.',
    'born_eastern, high_eastern and start_eastern are added here for reading; exhaustion_20s_at_start, bought_price, '
    'sold_price and picture are stored values looked up for the trade and are explained below; every other column '
    'is the stored value.',
    'NO MID PRICE IS IN THIS FILE (Greg, 2026-11-23). Left out of the crypto and ng sheets until he says: '
    + ', '.join(LEFT_OUT[:-1]) + ' (the program\'s own figures, made from the mid price) and ' + LEFT_OUT[-1]
    + ' (its fee mark).',
    'DIPOLE AND EXHAUSTION ARE THE CRYPTO FORMULAS (Greg, 2026-11-23): bought minus sold over bought plus sold, over '
    'the trades of the last 60 seconds (dipole) and of the last 20 seconds (exhaustion), read at the nanosecond. '
    'exhaustion_20s_at_start is the stored 20-second line at the trade\'s start (onset_read_20s is only the number '
    'of that read). program_dive_depth, program_lean_flip and program_lean_close are the program\'s own reads of '
    'the 60-second line.',
    'Times ending _ns are written as text (19 digits; Excel would round them as numbers). Empty cells are empty: '
    'never zero.',
    'Excel keeps a decimal to about 15 digits, so a decimal here can differ from the stored value in its last digit. '
    'The stored files are the exact record.',
    'A trade day runs 6 pm Eastern the evening before to 5 pm Eastern on the named date.',
    'THE COLUMNS OF THE CRYPTO AND NG SHEETS:',
]


def label(day: str) -> str:
    return f'{day[:4]}-{day[4:6]}-{day[6:]}'


def eastern(ns: int) -> str:
    moment = dt.datetime.fromtimestamp(ns // NS_PER_SECOND, tz=dt.timezone.utc).astimezone(EASTERN)
    return moment.strftime('%Y-%m-%d %H:%M:%S')


def pictures_stored(checkout: Path, day: str) -> dict:
    """The picture stored for each trade of the program, by its file name, read from the branch's own list of
    files (names only). Where a trade has two, the newest folder's is taken."""
    names = subprocess.run(['git', '-C', str(checkout), 'ls-tree', '-r', '--name-only', 'HEAD'], capture_output=True,
                           text=True, check=True).stdout.split()
    found = {}
    for folder in reversed(PICTURES):
        for name in names:
            if name.startswith(f'{folder}/trade-render-{day}-') and name.endswith('.png'):
                found[int(name.rsplit('-', 1)[-1].split('.')[0])] = (folder, name.split('/')[-1])
    return found


def trade_lines(checkout: Path, day: str) -> tuple:
    """The header and the lines of one trade day's sheet, and the place of each picture's link."""
    tick = checkout / 'crypto-ng-tick'
    stored = pq.read_table(tick / f'crypto-ng-tick-program-trades-{day}.parquet')
    known = [name for name, _ in TRADE_COLUMNS]
    assert stored.column_names == known, (day, 'the stored trades do not hold the columns the program writes')
    tape = pq.read_table(tick / f'crypto-ng-tick-tape-trades-{day}.parquet', columns=['position_on_tape', 'price'])
    price = dict(zip(tape['position_on_tape'].to_pylist(), tape['price'].to_pylist()))
    line = pq.read_table(tick / f'crypto-ng-tick-line-20s-{day}.parquet',
                         columns=['read', 'moment_received_ns', 'position_on_tape', 'flow']).to_pylist()
    kept = [name for name in known if name not in LEFT_OUT]
    header = [ADDED[0][0]] + kept + [name for name, _ in ADDED[1:]]
    drawn = pictures_stored(checkout, day)
    lines, links = [], {}
    for k, t in enumerate(stored.to_pylist()):
        at = dict(start=price[t['onset_position_on_tape']],
                  end=price[t['end_position_on_tape']] if t['end_position_on_tape'] is not None else None)
        bought, sold = (at[where] for where in SIDES[t['side']])
        read = line[t['onset_read_20s']]               # the read the program itself names, and it must be that trade's
        assert (read['read'], read['moment_received_ns'], read['position_on_tape']) == \
            (t['onset_read_20s'], t['onset_received_ns'], t['onset_position_on_tape']), (day, t['trade'], read)
        folder, name = drawn.get(t['trade'], (None, None))
        if name:
            links[k] = LINK.format(day=day, folder=folder, name=name)
        lines.append([eastern(t['onset_received_ns'])]
                     + [str(t[n]) if n.endswith('_ns') and t[n] is not None else t[n] for n in kept]
                     + [read['flow'], bought, sold, name])
    return header, lines, links


def same(want, got) -> bool:
    if isinstance(want, float) and isinstance(got, (int, float)):
        return abs(want - got) <= CLOSE * max(1.0, abs(want))
    return want == got


def values(sheet) -> list:
    """Every line of a sheet as it stands, each cut after its last filled cell."""
    out = []
    for row in sheet.iter_rows(values_only=True):
        row = list(row)
        while row and row[-1] is None:
            row.pop()
        out.append(row)
    return out


def links_of(sheet) -> dict:
    """Every link of a sheet: the cell it sits on and where it opens."""
    return {cell.coordinate: cell.hyperlink.target for row in sheet.iter_rows() for cell in row
            if cell.hyperlink is not None}


def main():
    book_path, checkouts = Path(sys.argv[1]), Path(sys.argv[2])
    book = load_workbook(book_path)
    before = {sheet.title: values(sheet) for sheet in book.worksheets}
    links_before = {sheet.title: links_of(sheet) for sheet in book.worksheets}
    wanted, links_wanted = {}, {}
    for day in DAYS:
        peaks = book[f'peaks {label(day)}']
        head = before[peaks.title][0]
        assert head[-len(PAGE_COLUMNS):] == PAGE_COLUMNS, (day, 'the peaks sheet does not end with the page columns')
        keep = len(head) - len(PAGE_COLUMNS)
        place = book.worksheets.index(peaks)
        book.remove(peaks)                             # written again without its last two columns and their links
        again = book.create_sheet(peaks.title, place)
        wanted[again.title] = [row[:keep] for row in before[peaks.title]]
        for row in wanted[again.title]:
            again.append(row)
        header, lines, links = trade_lines(checkouts / day, day)
        sheet = book.create_sheet(f'crypto and ng {label(day)}', place + 1)
        sheet.append(header)
        for k, line in enumerate(lines):
            sheet.append(line)
            if k in links:
                sheet.cell(row=sheet.max_row, column=len(header)).hyperlink = links[k]
        wanted[sheet.title] = [header] + lines
        links_wanted[sheet.title] = sorted(links.values())
        links_wanted[again.title] = []                 # the peaks sheets' links went with the page columns
    first = book['READ ME']
    first.delete_rows(1, first.max_row)
    described = dict(TRADE_COLUMNS)
    page = READ_ME + [f'{name}: {what}' for name, what in ADDED[:1]] + \
        [f'{name}: {described[name]}' for name, _ in TRADE_COLUMNS if name not in LEFT_OUT] + \
        [f'{name}: {what}' for name, what in ADDED[1:]]
    for line in page:
        first.append([line])
    wanted['READ ME'] = [[line] for line in page]
    book.save(book_path)

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
        if untouched:
            assert linked == links_before[sheet.title], (sheet.title, 'its links changed')
        else:
            assert sorted(linked.values()) == links_wanted.get(sheet.title, []), (sheet.title, 'its links are not right')
        print(f'{sheet.title}: {len(got) - 1} rows, {len(linked)} links, read back equal'
              + (' (not touched)' if untouched else ''))
    assert [s.title for s in back.worksheets if s.title not in wanted] == \
        [title for title in before if title not in wanted], 'a sheet that was there is gone'
    print('bytes', book_path.stat().st_size)


if __name__ == '__main__':
    main()
