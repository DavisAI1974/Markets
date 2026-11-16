"""ROOT `sheet`: writes the workbook from the stored rows. One sheet per trade day, one row per tick.

Specification: SPEC-root.md (approved by Greg, 2026-11-16), "The workbook" and criterion 11. The stored rows (Parquet)
are the exact record; the sheet is written from them and says the same. This part can write a short stretch (to
measure the size before the full workbook is written) or a whole trade day.

How a stored value is written, so that the sheet never changes it:
- A time in nanoseconds and an order number are written as TEXT. Excel keeps a number only to about 15 digits, and
  these have 19; written as numbers they would be silently rounded.
- Any other whole number is written as a number, unless it is too large for Excel to hold exactly (the tape's "no
  price" value is): then it is written as text, digit for digit.
- A decimal is written as a number, yes/no as TRUE/FALSE, text as text.
- An empty field is an empty cell: never 0 and never blank text.
The workbook has three sheets: READ ME FIRST, COLUMNS (every column in plain words) and the trade day.

    python3 -m root.sheet 20231002 --rows <stored rows folder> --out <file.xlsx> [--from-eastern 09:00 --count 20000]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from root import rows as R
from root.calendar import eastern, parse_trade_day, to_ns, trade_day_bounds

EXCEL_EXACT_WHOLE_NUMBER = 2 ** 53        # Excel holds a whole number exactly only below this
EXCEL_ROWS = 2 ** 20                      # the most rows one Excel sheet holds
AS_TEXT = {name for name in R.NAMES if name.endswith('_time_ns') or name.endswith('_known_from_ns')} | {'order_number'}
README_SHEET, COLUMNS_SHEET = 'READ ME FIRST', 'COLUMNS'
SHOWN_TO_FRANKIE = 'yes'                  # every column is shown to Frankie unless Greg marks it otherwise


def as_cell(name: str, value):
    """One stored value as the sheet holds it (see the module text)."""
    if value is None or isinstance(value, (bool, float, str)):
        return value
    if name in AS_TEXT or abs(value) >= EXCEL_EXACT_WHOLE_NUMBER:
        return str(value)
    return value


def from_cell(name: str, value, kind):
    """A cell read back as the stored value (criterion 11). `kind` is the stored column's type as text."""
    if value is None:
        return None
    if kind == 'int64':
        return int(value)
    if kind == 'double':
        return float(value)
    return value


def stored(rows_folder: Path, trade_day: dt.date, start_ns: int | None, count: int | None):
    """The stored rows of a trade day's box in tape order, as lists in column order; optionally only the first
    `count` rows at or after an exchange time. Yields (column names, column types) first."""
    import pyarrow.parquet as pq
    files = sorted(Path(rows_folder).glob(f'rows-{trade_day:%Y%m%d}-part*.parquet'))
    if not files:
        raise FileNotFoundError(f'no stored rows of {trade_day} in {rows_folder}')
    schema = pq.read_schema(files[0])
    if schema.names != R.NAMES:
        raise ValueError(f'the stored rows in {rows_folder} do not have the columns of this build')
    yield schema.names, [str(t) for t in schema.types]
    given = 0
    for f in files:
        table = pq.read_table(f, filters=None if start_ns is None else [('exchange_time_ns', '>=', start_ns)])
        for batch in table.to_batches():
            columns = [c.to_pylist() for c in batch.columns]
            for row in zip(*columns):
                if count is not None and given >= count:
                    return
                given += 1
                yield row


def write(rows_folder: Path, trade_day: dt.date, out: Path, readme: Path | None = None, start_ns: int | None = None,
          count: int | None = None) -> dict:
    """Write the workbook and read the trade day's sheet back against the stored rows (criterion 11)."""
    import time
    from openpyxl import Workbook, load_workbook
    started = time.monotonic()
    source = stored(rows_folder, trade_day, start_ns, count)
    names, kinds = next(source)
    wb = Workbook(write_only=True)
    page = wb.create_sheet(README_SHEET)
    if count is not None:
        page.append([f'THIS FILE IS A SHORT STRETCH, written to measure the size of the workbook: {count} rows of '
                     f'trade day {trade_day}. It is not the full trade day.'])
    for line in ([] if readme is None else readme.read_text().split('\n---\n', 1)[-1].splitlines()):
        page.append([line])
    listing = wb.create_sheet(COLUMNS_SHEET)
    listing.append(['Section', 'Column', 'What it is', 'How it is written in this sheet', 'Shown to Frankie'])
    for (section, name, what), kind in zip(R.COLUMNS, kinds):
        how = ('text (19 digits; Excel would round it as a number)' if name in AS_TEXT else
               {'int64': 'whole number', 'double': 'decimal', 'bool': 'TRUE or FALSE'}.get(kind, 'text'))
        listing.append([section, name, what, how, SHOWN_TO_FRANKIE])
    sheet = wb.create_sheet(f'{trade_day:%Y-%m-%d}')
    sheet.append(names)
    written, kept = 0, []
    for row in source:
        if written + 1 >= EXCEL_ROWS:
            raise ValueError(f'trade day {trade_day} has more rows than one Excel sheet holds')
        sheet.append([as_cell(n, v) for n, v in zip(names, row)])
        kept.append(row)
        written += 1
    wb.save(out)
    wrote_seconds = time.monotonic() - started

    # criterion 11: the sheet says the same as the stored rows
    back = load_workbook(out, read_only=True)[f'{trade_day:%Y-%m-%d}'].iter_rows(values_only=True)
    if list(next(back)) != names:
        raise AssertionError('the sheet header differs from the stored columns')
    read = 0
    for want, got in zip(kept, back):
        got = tuple(got) + (None,) * (len(names) - len(got))     # the reader leaves off empty cells at a row's end
        got = tuple(from_cell(n, v, k) for n, v, k in zip(names, got, kinds))
        if got != tuple(want):
            bad = next(n for n, a, b in zip(names, got, want) if a != b)
            raise AssertionError(f'sheet row {read + 1} differs from the stored row in {bad}')
        read += 1
    if read != written or next(back, None) is not None:
        raise AssertionError('the sheet row count differs from the stored row count')
    size = out.stat().st_size
    opens, halts = trade_day_bounds(trade_day)
    return dict(what='ROOT sheet', trade_day=trade_day.isoformat(), file=out.name, bytes=size, rows=written,
                columns=len(names), bytes_per_row=round(size / written, 1),
                first_row_exchange_time_ns=kept[0][R.INDEX['exchange_time_ns']],
                last_row_exchange_time_ns=kept[-1][R.INDEX['exchange_time_ns']],
                sheet_equals_stored_rows=True, rows_read_back=read,
                seconds_to_write=round(wrote_seconds, 1), seconds_in_all=round(time.monotonic() - started, 1))


def main():
    ap = argparse.ArgumentParser(description='ROOT sheet: the workbook from the stored rows')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True, help='the folder of stored rows (a root-rows branch)')
    ap.add_argument('--out', type=Path, required=True, help='the workbook to write (in markets-data, never Markets)')
    ap.add_argument('--readme', type=Path, help='WORKBOOK_README_PAGE.md, the text of the first sheet')
    ap.add_argument('--from-eastern', help='a short stretch: start at this Eastern time on the trade day\'s date, HH:MM')
    ap.add_argument('--count', type=int, help='a short stretch: this many rows')
    a = ap.parse_args()
    day = parse_trade_day(a.trade_day)
    start = None
    if a.from_eastern:
        start = to_ns(eastern(day, dt.time.fromisoformat(a.from_eastern)))
    print(json.dumps(write(a.rows, day, a.out, a.readme, start, a.count), indent=1))


if __name__ == '__main__':
    main()
