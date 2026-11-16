"""ROOT `store`: writes one trade day's rows, the book pictures, the vendor-restatement table and the receipt.

Specification: SPEC-root.md (approved by Greg, 2026-11-16), part `store` (assumption 2: the rows are stored as data
files, Parquet, as the exact record; the workbook is written from them). One walk of the week makes everything:
- `rows-<trade day>-partNNN.parquet`: one row per written tick, one column per field (rows.COLUMNS), in tape order;
- `book-pictures-<trade day>-partNNN.parquet`: every order of the whole book, in book order, at every trade message,
  at the first written row and at the last one; with the rows the complete book at any written tick is exact;
- `vendor-restatements-<trade day>.parquet`: the vendor's opening restatement of every later raw file, never applied,
  with whether our carried book has the same order;
- `RECEIPT.json`: counts, the fingerprint of every input and output, and the result of every check made in the walk.
An empty field is stored as empty (null): never 0 and never blank text. Output goes to markets-data, never Markets.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from root import checks
from root import rows as rows_part
from root import tape
from root.book import ADD, ASK, BID, TRADE

ROWS_PER_PART = 2 ** 18            # rows per stored part file: keeps every file well under GitHub's file limit
PICTURE_ROWS_PER_PART = 2 ** 22    # book-picture rows per stored part file (they compress far more than rows)
ZSTD_LEVEL = 9                     # compression of the stored files; the content is unchanged
TEXT = {'action', 'side', 'row_label', 'trade_day', 'raw_file', 'raw_file_fingerprint', 'contract', 'what_happened',
        'irregular', 'touched_line'}
YES_NO = {'ends_exchange_event', 'in_settlement_window', 'entered_before_written_record', 'rested_is_at_least',
          'best_bid_front_is_at_least', 'best_ask_front_is_at_least', 'level_appeared', 'level_emptied',
          'front_of_line_changed'}
PICTURE_COLUMNS = ['picture_position', 'why', 'side', 'price', 'place_in_line', 'order_number', 'size',
                   'first_entered_exchange_time_ns', 'first_entered_received_time_ns',
                   'took_place_exchange_time_ns', 'took_place_received_time_ns', 'carried_over_weekend',
                   'entered_before_written_record']
PICTURE_TEXT = {'why', 'side'}
PICTURE_YES_NO = {'carried_over_weekend', 'entered_before_written_record'}
AT_TRADE, AT_FIRST_ROW, AT_LAST_ROW = 'trade', 'first written row', 'last written row'
RESTATEMENT_COLUMNS = ['raw_file', 'record_in_file', 'exchange_time_ns', 'received_time_ns', 'action', 'side',
                       'price', 'size', 'order_number', 'flags', 'sequence_number', 'our_book_has_this_order_the_same']


def schema(columns, text, yes_no):
    import pyarrow as pa
    return pa.schema([(c, pa.string() if c in text else pa.bool_() if c in yes_no else pa.int64()) for c in columns])


class Parts:
    """Writes a table as numbered Parquet part files, deterministically, and keeps each file's fingerprint."""

    def __init__(self, folder: Path, stem: str, table_schema, rows_per_part: int):
        self.folder, self.stem, self.schema, self.limit = folder, stem, table_schema, rows_per_part
        self.columns = [[] for _ in table_schema.names]
        self.held = self.written = 0
        self.files = []

    def add(self, row):
        for column, value in zip(self.columns, row):
            column.append(value)
        self.held += 1
        if self.held >= self.limit:
            self.flush()

    def flush(self):
        import pyarrow as pa
        import pyarrow.parquet as pq
        if not self.held:
            return
        name = f'{self.stem}-part{len(self.files):03d}.parquet'
        table = pa.Table.from_arrays([pa.array(c, type=t) for c, t in zip(self.columns, self.schema.types)],
                                     schema=self.schema)
        pq.write_table(table, self.folder / name, compression='zstd', compression_level=ZSTD_LEVEL,
                       use_dictionary=True, write_statistics=True, version='2.6', data_page_version='2.0')
        raw = (self.folder / name).read_bytes()
        self.files.append(dict(file=name, rows=self.held, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
        self.written += self.held
        self.columns = [[] for _ in self.schema.names]
        self.held = 0


def picture(book, position: int, why: str, out: Parts) -> dict:
    """Write every order of the whole book in book order (bids from the best down, asks from the best up, each line
    front first). Returns a fresh count of the book made from the picture itself (criterion 4)."""
    fresh = {}
    for side, prices in ((BID, reversed(book.sides[BID].prices)), (ASK, book.sides[ASK].prices)):
        size = orders = levels = 0
        lines = book.sides[side].lines
        letter = side.decode()
        for price in prices:
            levels += 1
            for place, o in enumerate(lines[price].orders.values()):
                out.add((position, why, letter, price, place, o.id, o.size, o.entered_event, o.entered_recv,
                         o.placed_event, o.placed_recv, o.carried_over_weekend, not o.entered_written))
                size += o.size
                orders += 1
        fresh[letter] = dict(size=size, orders=orders, levels=levels)
    return fresh


def build(tape_folder: Path, trade_day: dt.date, out: Path, checker=None) -> dict:
    """One trade day: walk its week once and write the rows, the book pictures, the restatement table and the
    receipt into `out`. `checker`, when given, sees every row (root.checks)."""
    import time
    started = time.monotonic()
    out.mkdir(parents=True, exist_ok=True)
    week = tape.read_week(tape_folder, trade_day)
    day = f'{trade_day:%Y%m%d}'
    row_parts = Parts(out, f'rows-{day}', schema(rows_part.NAMES, TEXT, YES_NO), ROWS_PER_PART)
    pic_parts = Parts(out, f'book-pictures-{day}', schema(PICTURE_COLUMNS, PICTURE_TEXT, PICTURE_YES_NO),
                      PICTURE_ROWS_PER_PART)
    I = rows_part.INDEX
    pictures = dict(trade=0, adds_up=True)
    def orders_in(fresh):
        return sum(side['orders'] for side in fresh.values())

    def at_last(book, position):
        pictures['last_written_row'] = dict(position=position,
                                            orders=orders_in(picture(book, position, AT_LAST_ROW, pic_parts)))

    walk = rows_part.Walk(week, trade_day, on_last_written=at_last)
    last_row_position = None
    for row in walk:
        position = row[I['position_on_tape']]
        if last_row_position is None:      # on the week's first trade day this row is the exchange's clear: 0 orders
            pictures['first_written_row'] = dict(
                position=position, orders=orders_in(picture(walk.book, position, AT_FIRST_ROW, pic_parts)))
        if row[I['action']] == TRADE.decode():
            fresh = picture(walk.book, position, AT_TRADE, pic_parts)
            pictures['trade'] += 1
            if fresh != walk.book.figures():
                pictures['adds_up'] = False
        if checker is not None:
            checker.see(row)
        row_parts.add(row)
        last_row_position = position
    row_parts.flush()
    pic_parts.flush()

    # the vendor's restatements: kept in their own table, compared, never applied
    import pyarrow as pa
    import pyarrow.parquet as pq
    restated = [[] for _ in RESTATEMENT_COLUMNS]
    for f, same in walk.restatements:
        c = tape.columns(f.records[:f.vendor_snapshot])
        for k in range(f.vendor_snapshot):
            values = (f.name, k, c['ts_event'][k], c['ts_recv'][k], c['action'][k].decode(), c['side'][k].decode(),
                      c['price'][k], c['size'][k], c['order_id'][k], c['flags'][k], c['sequence'][k],
                      None if c['action'][k] != ADD else c['order_id'][k] in same)
            for column, value in zip(restated, values):
                column.append(value)
    r_schema = schema(RESTATEMENT_COLUMNS, {'raw_file', 'action', 'side'}, {'our_book_has_this_order_the_same'})
    r_name = f'vendor-restatements-{day}.parquet'
    pq.write_table(pa.Table.from_arrays([pa.array(c, type=t) for c, t in zip(restated, r_schema.types)],
                                        schema=r_schema), out / r_name, compression='zstd',
                   compression_level=ZSTD_LEVEL, version='2.6', data_page_version='2.0')
    r_raw = (out / r_name).read_bytes()

    if not all(r['equal'] for r in walk.compared):
        raise checks.CheckFailed(f'the carried book differs from the vendor restatement: {walk.compared}')
    if not pictures['adds_up']:
        raise checks.CheckFailed('the running whole-book figures differ from a fresh count at a trade')
    receipt = dict(
        what='ROOT build of one trade day: rows, book pictures, vendor restatements',
        specification='SPEC-root.md (approved 2026-11-16)', trade_day=trade_day.isoformat(),
        inputs=[dict(file=f.name, sha256=f.sha256, records=len(f.records), vendor_restatement_records=f.vendor_snapshot)
                for f in week],
        columns=len(rows_part.NAMES), rows=row_parts.written, row_files=row_parts.files,
        book_picture_rows=pic_parts.written, book_pictures_at_trades=pictures['trade'],
        book_picture_at_first_written_row=pictures.get('first_written_row'),
        book_picture_at_last_written_row=pictures.get('last_written_row'),
        book_picture_files=pic_parts.files,
        vendor_restatement_file=dict(file=r_name, rows=len(restated[0]), bytes=len(r_raw),
                                     sha256=hashlib.sha256(r_raw).hexdigest()),
        walk=walk.stats,
        checks=dict(book_equals_restatement=[dict(r, file=f.name) for (f, _), r in zip(walk.restatements,
                                                                                         walk.compared)],
                    book_adds_up_at_every_trade=pictures['adds_up'],
                    rows=(checker.result() if checker is not None else None),
                    accounted=(checks.accounted(week, trade_day, walk.stats, checker.result())
                               if checker is not None else None)),
        empty_fields='stored as empty (null): never 0, never blank text; a calculation skips them',
        seconds=round(time.monotonic() - started, 1))
    (out / 'RECEIPT.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt
