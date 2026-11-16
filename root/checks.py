"""ROOT `checks`: the success criteria of SPEC-root.md, made on the real rows as they are built.

A failed check stops the run with its reason (CheckFailed). Nothing here uses a later tick to judge an earlier one
except where the criterion itself is about the whole record (one history per order; counts).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

from root import pin
from root import rows as R
from root import tape
from root.book import TRADE
from root.calendar import STRETCH, TRADE_DAY, label, trade_day_bounds

I = R.INDEX
ORDER_FIELDS = ('order_size_before', 'order_size_after', 'orders_ahead_before', 'size_ahead_before', 'life_step',
                'first_entered_position', 'first_entered_exchange_time_ns', 'took_place_exchange_time_ns',
                'rested_exchange_ns', 'rested_is_at_least', 'entered_before_written_record')
ENDINGS = (R.LEFT_BY_CANCEL, R.LEFT_BY_FILL)
FIRST = object()
HALVE = 2                          # the playback cut inside an exchange event is taken at the middle such trade


class CheckFailed(AssertionError):
    pass


def need(condition, *reason):
    if not condition:
        raise CheckFailed(' '.join(str(x) for x in reason))


class RowChecker:
    """Sees every row of one trade day's box, in order. Criteria 2 (the cut), 5 (one history per order), and that
    each row is consistent with itself: empties are empty, the line on the row adds up, a best-price move is marked
    exactly when the best price changes, and "by fill" follows a fill of that order in the same exchange event."""

    def __init__(self, trade_day: dt.date):
        self.day = trade_day
        self.seen, self.ended, self.fills = {}, set(), {}
        self.previous = {'bid': FIRST, 'ask': FIRST}
        self.rows = self.trade_rows = self.trade_rows_in_trade_day = self.before_record = 0
        self.labels = {}
        self.stretch_rows = []
        self.last_position = None

    def see(self, r):
        self.rows += 1
        need(len(r) == len(R.NAMES), 'a row has', len(r), 'fields')
        te, action, oid, pos = r[I['exchange_time_ns']], r[I['action']], r[I['order_number']], r[I['position_on_tape']]
        what = r[I['what_happened']]
        need(self.last_position is None or pos > self.last_position, 'rows out of tape order at', pos)
        self.last_position = pos
        tag, named = label(te)
        need(r[I['row_label']] == tag, 'wrong label at', pos)
        need(r[I['trade_day']] == (self.day.isoformat() if tag == TRADE_DAY else None), 'wrong trade day at', pos)
        need(tag != TRADE_DAY or named == self.day, 'a row of another trade day at', pos)
        self.labels[tag] = self.labels.get(tag, 0) + 1
        if tag == STRETCH:
            self.stretch_rows.append(r)
        if action == TRADE.decode():
            self.trade_rows += 1
            self.trade_rows_in_trade_day += tag == TRADE_DAY
        if action in ('T', 'N', 'R') or what == R.NOT_APPLIED:
            need(all(r[I[f]] is None for f in ORDER_FIELDS), 'a field that should be empty is filled at', pos)
            need(r[I['touched_price']] is None and r[I['touched_line']] is None, 'a line on a row with none at', pos)
        if what != R.LOST_PLACE_PRICE:
            need(r[I['left_price']] is None and r[I['left_line_size_before']] is None, 'a left line at', pos)
        text = r[I['touched_line']]
        if text is not None:
            sizes = [int(part.split('|')[1]) for part in text.split(';')] if text else []
            need(sum(sizes) == r[I['touched_line_size_after']] and len(sizes) == r[I['touched_line_orders_after']],
                 'the line on the row does not add up at', pos)
        for side in ('bid', 'ask'):
            now, moved_to = r[I[f'best_{side}']], r[I[f'best_{side}_moved_to']]
            moved = r[I[f'best_{side}_moved_from']] is not None or moved_to is not None
            if self.previous[side] is not FIRST:
                need(moved == (now != self.previous[side]), 'best', side, 'move mark wrong at', pos)
            if moved:
                need(moved_to == now and r[I[f'best_{side}_moved_from']] != now, 'best', side, 'move wrong at', pos)
            self.previous[side] = now
        if r[I['best_bid']] is not None and r[I['best_ask']] is not None:
            need(r[I['gap']] == r[I['best_ask']] - r[I['best_bid']], 'gap wrong at', pos)
        if action in ('A', 'C', 'M', 'F') and what != R.NOT_APPLIED and r[I['life_step']] is not None:
            need(oid not in self.ended, 'a row after the order ended at', pos)
            step = r[I['life_step']]
            if oid in self.seen:
                need(step == self.seen[oid][0] + 1 and r[I['previous_step_position']] == self.seen[oid][1],
                     'steps of order', oid, 'not consecutive at', pos)
            elif what == R.JOINED:
                need(step == 1 and r[I['first_entered_position']] == pos, 'a joined row that is not step 1 at', pos)
            else:
                need(step > 1 and r[I['first_entered_position']] < pos, 'an unknown order mid-life at', pos)
            self.seen[oid] = (step, pos)
            if what in ENDINGS:
                self.ended.add(oid)
                need(r[I['order_size_after']] == 0, 'an order left with size at', pos)
            self.before_record += bool(r[I['entered_before_written_record']])
        event = r[I['exchange_event']]
        if action == 'F':
            self.fills.setdefault(event, set()).add(oid)
        if what in (R.LEFT_BY_FILL, R.SHRANK_BY_FILL):
            need(oid in self.fills.get(event, ()), 'by fill without a fill in the event at', pos)
        if what in (R.LEFT_BY_CANCEL, R.SHRANK):
            need(oid not in self.fills.get(event, ()), 'a fill in the event but not marked by fill at', pos)
        if r[I['ends_exchange_event']]:
            self.fills.pop(event, None)

    def result(self) -> dict:
        return dict(passed=True, rows_seen=self.rows, rows_by_label=dict(sorted(self.labels.items())),
                    trade_rows=self.trade_rows, trade_rows_in_the_trade_day=self.trade_rows_in_trade_day,
                    orders_seen=len(self.seen), orders_ended=len(self.ended),
                    orders_still_resting_or_running_on=len(self.seen) - len(self.ended),
                    rows_of_orders_from_before_the_written_record=self.before_record)


def independent_counts(week, trade_day: dt.date) -> dict:
    """Counts made straight from the raw files, not from the walk (criteria 1 and 6): records per file, the vendor
    restatement records, and the trade messages inside the box's written span and inside the trade day."""
    lo, hi = R.written_span(trade_day)
    opens, halts = trade_day_bounds(trade_day)
    out = dict(records=0, vendor_restatement_records=0, ticks=0, written=0, trade_messages_written=0,
               trade_messages_in_the_trade_day=0)
    for f in week:
        t = f.records[f.vendor_snapshot:]
        te = t['ts_event']
        written = (te < hi) if lo is None else ((te >= lo) & (te < hi))
        trades = t['action'] == TRADE
        out['records'] += len(f.records)
        out['vendor_restatement_records'] += f.vendor_snapshot
        out['ticks'] += len(t)
        out['written'] += int(written.sum())
        out['trade_messages_written'] += int((written & trades).sum())
        out['trade_messages_in_the_trade_day'] += int((trades & (te >= opens) & (te < halts)).sum())
    return out


def accounted(week, trade_day, walk_stats: dict, row_result: dict) -> dict:
    """Criterion 1 (every record accounted for) and criterion 6 (the trades are all there)."""
    ind = independent_counts(week, trade_day)
    c = walk_stats['counts']
    walked = dict(written=c.get('written', 0), warm_up=c.get('warm-up', 0), shelved=c.get('shelved', 0))
    need(ind['records'] == walked['written'] + walked['warm_up'] + walked['shelved'] +
         ind['vendor_restatement_records'], 'records are not all accounted for', ind, walked)
    need(ind['written'] == walked['written'] == row_result['rows_seen'], 'written rows differ from the tape count')
    need(ind['trade_messages_written'] == row_result['trade_rows'], 'trade rows differ from the tape count')
    need(ind['trade_messages_in_the_trade_day'] == row_result['trade_rows_in_the_trade_day'],
         'trade rows in the trade day differ from the tape count')
    return dict(passed=True, from_the_raw_files=ind, from_the_walk=walked)


def playback(week, trade_day: dt.date) -> list:
    """Criterion 8: with the tape cut off at a tick, every row up to that tick is identical to the same row of the
    full run. Cuts: inside an exchange event, across 6 pm (the open), across the vendor's file boundary, across
    5 pm (the halt)."""
    opens, halts = trade_day_bounds(trade_day)
    last_bit = tape.flag_bits()['F_LAST']
    cuts = {}                                   # description -> (file index, ticks kept in that file)
    for k, f in enumerate(week):
        t = f.records[f.vendor_snapshot:]
        te = t['ts_event']
        for name, at in (('across 6 pm Eastern, the open', opens), ('across 5 pm Eastern, the halt', halts)):
            hit = (te >= at).nonzero()[0]
            if name not in cuts and len(hit):
                cuts[name] = (k, int(hit[0]) + 1)
        inside = ((t['action'] == TRADE) & (te >= opens) & (te < halts) & ((t['flags'] & last_bit) == 0)).nonzero()[0]
        if 'inside an exchange event' not in cuts and len(inside):
            cuts['inside an exchange event'] = (k, int(inside[len(inside) // HALVE]) + 1)
    cuts['across the vendor file boundary'] = (len(week) - 1, 1)
    wanted = {}
    for name, (k, kept) in cuts.items():
        wanted.setdefault((k, kept), []).append(name)

    def digests(files, marks=None):
        """The running fingerprint of the rows; with `marks`, its value when the walk passes each marked tick."""
        h, out, count = hashlib.sha256(), {}, 0
        ends = {}
        if marks:
            base = 0
            for k, f in enumerate(files):
                for (fk, kept) in marks:
                    if fk == k:
                        ends[base + kept - 1] = (fk, kept)
                base += len(f.records) - f.vendor_snapshot
        pending = sorted(ends)
        for r in R.build(files, trade_day):
            pos = r[I['position_on_tape']]
            while pending and pending[0] < pos:
                out[ends[pending.pop(0)]] = (h.hexdigest(), count)
            h.update(repr(r).encode())
            count += 1
        while pending:
            out[ends[pending.pop(0)]] = (h.hexdigest(), count)
        return h.hexdigest(), count, out

    _, _, full = digests(week, wanted)
    results = []
    for (k, kept), names in sorted(wanted.items()):
        f = week[k]
        short = week[:k] + [tape.WeekFile(f.day, f.name, f.sha256, f.records[:f.vendor_snapshot + kept],
                                          f.vendor_snapshot, f.instrument_ids, f.mappings)]
        digest, count, _ = digests(short)
        want_digest, want_count = full[(k, kept)]
        # the cut run's last row may be the cut tick itself; the full run's fingerprint is taken after that tick
        need((digest, count) == (want_digest, want_count), 'playback differs at the cut', names)
        results.append(dict(cut=' and '.join(names), raw_file=f.name, rows_compared=count, identical=True))
    return results


def pinned(row_files, tables_folder) -> dict:
    """Criterion 7, read back from the STORED rows and the made outside tables, by a whole-column lookup that does not
    use the pinning code's own per-row lookup: on every row, each outside figure became known at or before the row's
    received time and is the latest such value; the once-per-trade-day figures are those of the row's own trade day,
    known from its open, and empty on a row of no trade day. Every row and every section G column is compared."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    folder = Path(tables_folder)
    receipt = json.loads((folder / 'RECEIPT.json').read_text())
    prints = {t['table']: t['sha256'] for t in receipt['tables']}
    stored = pa.concat_tables([pq.read_table(f) for f in row_files])
    received = stored.column('received_time_ns').to_numpy()
    need(int(received.max()) < receipt['cut_ns'], 'a row was received after everything the outside tables hold')
    kinds = {pin.WHOLE: pa.int64(), pin.DECIMAL: pa.float64(), pin.WORDS: pa.string()}
    tables, empty_rows = {}, {}

    def table(name):
        if name not in tables:
            tables[name] = pin.read_table(folder, name, prints[name])
        return tables[name]

    def same(column, expected):
        need(stored.column(column).combine_chunks().equals(expected), 'section G differs from the tables in', column)
        empty_rows[column] = stored.column(column).null_count

    for g in pin.AS_OF:
        rows = pin.chosen(table(g['table']), g['where'])
        known = np.array([int(r['known_from_ns']) for r in rows], dtype=np.int64)
        need(bool((np.diff(known) >= 0).all()), g['table'], 'is not in the order its values became known')
        latest = np.searchsorted(known, received, side='right') - 1     # the last value known at or before the row
        take = pa.array(latest, mask=latest < 0)                         # empty where nothing was known yet
        same(g['known'], pa.array(known).take(take))
        for name, col, kind, _ in g['fields']:
            same(name, pa.array([pin.convert(r[col], kind) for r in rows], type=kinds[kind]).take(take))

    days = stored.column('trade_day').combine_chunks()
    names = sorted(pc.unique(days.drop_null()).to_pylist())
    which = pc.index_in(days, value_set=pa.array(names, type=pa.string()))
    opens = {r['trade_day']: int(r['known_from_ns']) for r in table('expiry.csv')}
    same(pin.DAY_KNOWN, pa.array([opens[d] for d in names], type=pa.int64()).take(which))
    known_at = stored.column(pin.DAY_KNOWN).combine_chunks().fill_null(0).to_numpy()
    need(bool((known_at <= received).all()), 'a once-per-trade-day figure is on a row received before its open')
    for g in pin.PER_TRADE_DAY:
        by_day = {r['trade_day']: r for r in pin.chosen(table(g['table']), g['where'])}
        need(all(int(by_day[d]['known_from_ns']) <= opens[d] for d in names), g['table'], 'was not known at the open')
        for name, col, kind, _ in g['fields']:
            same(name, pa.array([pin.convert(by_day[d][col], kind) for d in names], type=kinds[kind]).take(which))
    need(set(empty_rows) == set(pin.NAMES), 'a section G column was not compared')
    return dict(passed=True, rows_compared=stored.num_rows, columns_compared=len(empty_rows),
                rows_of_no_trade_day=days.null_count, trade_days_on_the_rows=names,
                tables_hold_everything_known_before=receipt['cut_eastern'],
                rows_where_a_column_is_empty={c: n for c, n in empty_rows.items() if n})
