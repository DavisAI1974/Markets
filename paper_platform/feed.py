"""Deliver every original DBN record in source order, including vendor restatements."""
from __future__ import annotations

from datetime import date
from pathlib import Path
import time

from root import tape
from root.book import ASK, BID, Book, compare_with_restatement
from root.calendar import clock_days_needed, label, trade_day_bounds


class HistoricalFeed:
    """One fresh book per session. Replay sessions seat it from the exchange's Sunday clear."""

    def __init__(self, folder: Path, trade_day: date):
        self.trade_day = trade_day
        self.week = tape.read_week(folder, trade_day)
        manifest = tape.TapeFolder(folder)
        for day in clock_days_needed(trade_day):
            entry = manifest.entry(day)
            if (entry['schema'], entry['dataset'], entry['symbol']) != ('mbo', 'GLBX.MDP3', 'NG.v.0'):
                raise ValueError(f"{day}: expected purchased NG.v.0 GLBX.MDP3 MBO")
            if entry.get('expected_records', entry['records']) != entry['records']:
                raise ValueError(f"{day}: archive record counts disagree")
        self.sources = [
            dict(file=f.name, sha256=f.sha256, records=len(f.records), utc_file_date=f.day.isoformat(),
                 instrument_ids=f.instrument_ids)
            for f in self.week
        ]

    def messages(self, *, paced=False):
        """Fresh independent iterator. Wall time affects delivery pace only, never signal eligibility."""
        book = Book()
        flags = tape.flag_bits()
        position = 0
        cursor = 0
        event_start = 0
        opens, halts = trade_day_bounds(self.trade_day)
        clock_origin = tape_origin = None
        for file in self.week:
            if file.vendor_snapshot:
                comparison = compare_with_restatement(book, file.records[:file.vendor_snapshot])
                if not comparison['equal']:
                    raise ValueError(f'{file.name}: carried book differs from opening restatement')
            for index, record in enumerate(file.records):
                fields = {k: record[k].item() for k in record.dtype.names}
                exchange = fields['ts_event']
                received = fields['ts_recv']
                snapshot = index < file.vendor_snapshot
                eligible = not snapshot and opens <= exchange < halts
                if paced and eligible:
                    if clock_origin is None:
                        clock_origin = time.monotonic_ns()
                        tape_origin = received
                    wait = (clock_origin + received - tape_origin - time.monotonic_ns()) / 1e9
                    if wait > 0:
                        time.sleep(wait)
                local_ns = time.time_ns()
                order_change = None
                entered_levels = {}
                if snapshot:
                    period, named = tape.VENDOR_SNAPSHOT, None
                    tick_position = group = None
                else:
                    period, named = label(exchange)
                    tick_position, group = position, event_start
                    oid = fields['order_id']
                    prior = book.orders.get(oid)
                    old = (prior.price, prior.size, prior.side.decode(), prior.entered_pos) if prior else None
                    filled = book.filled_in_event.get(oid, 0)
                    before = (book.best(BID), book.best(ASK))
                    notes = book.apply(fields['action'], fields['side'], fields['price'], fields['size'],
                               fields['order_id'], fields['flags'], exchange, received, fields['sequence'],
                               position, carried=bool(fields['flags'] & flags['F_SNAPSHOT']), written=eligible)
                    after = book.orders.get(oid)
                    new = (after.price, after.size, after.side.decode(), after.entered_pos) if after else None
                    order_change = dict(old=old, new=new, filled_in_event=filled, notes=notes)
                    for side, was in zip((BID, ASK), before):
                        best = book.best(side)
                        if best is not None and best != was:
                            entered_levels[side.decode()] = tuple(book.sides[side].lines[best].orders)
                    position += 1
                    if fields['flags'] & flags['F_LAST']:
                        event_start = position
                fields['action'] = fields['action'].decode('ascii')
                fields['side'] = fields['side'].decode('ascii')
                yield dict(cursor=cursor, source_sha256=file.sha256, record_index=index,
                           raw=fields, received_by_replay_ns=local_ns, period=period,
                           trade_day=named.isoformat() if named else None, in_session=eligible,
                           position_on_tape=tick_position, event_start_position=group,
                           order_change=order_change, entered_levels=entered_levels,
                           best_bid=book.best(BID), best_ask=book.best(ASK))
                cursor += 1

