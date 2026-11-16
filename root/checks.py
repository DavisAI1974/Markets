"""ROOT `checks`: the success criteria of SPEC-root.md, made on the real rows as they are built.

A failed check stops the run with its reason (CheckFailed). Nothing here uses a later tick to judge an earlier one
except where the criterion itself is about the whole record (one history per order; counts).
"""
from __future__ import annotations

import collections
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
            sizes = [] if text == R.NO_ORDERS else [int(part.split('|')[1]) for part in text.split(';')]
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


def flow_peak(row_files, calc_files, trade_day: dt.date, table_files=None, rows_folder=None) -> dict:
    """The check of the calculation `flow_peak`: every one of its columns worked out again from the stored rows by a
    whole-column method that shares nothing with the tick-by-tick code, and compared on every row. The traded sizes
    come from running totals; the peaks from the runs of equal flow; a peak's standing and how long it had been the
    highest from the full list of moments at which the flow changed (trades arriving and trades turning 20 seconds
    old). Rows of no trade day must hold empty cells."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from root.calcs import flow_peak as F
    from root.calendar import TRADE_DAY
    span = F.FLOW_SPAN_NS
    rows = pa.concat_tables([pq.read_table(f, columns=['position_on_tape', 'received_time_ns', 'action', 'side',
                                                       'size', 'row_label', 'trade_day']) for f in row_files])
    calc = pa.concat_tables([pq.read_table(f) for f in calc_files])
    need(rows.num_rows == calc.num_rows, 'the calculation files and the row files hold different numbers of rows')
    need(rows.column('position_on_tape').equals(calc.column('position_on_tape')), 'positions differ from the rows')
    text = lambda name: np.array(rows.column(name).to_pylist(), dtype=object)
    in_day = (text('row_label') == TRADE_DAY) & (text('trade_day') == trade_day.isoformat())
    got = {name: np.array(calc.column(name).to_pylist(), dtype=object) for name in F.NAMES}
    for name in F.NAMES:
        need(all(v is None for v in got[name][~in_day]), f'{name} is filled on a row of no trade day')
    d = np.flatnonzero(in_day)
    got = {name: values[d] for name, values in got.items()}
    position = rows.column('position_on_tape').to_numpy()[d]
    r = rows.column('received_time_ns').to_numpy()[d]
    need(bool(np.all(np.diff(r) >= 0)), 'the received time goes backwards inside the trade day')
    trade = text('action')[d] == F.TRADE.decode()
    side = text('side')[d]
    size = rows.column('size').to_numpy()[d].astype(np.int64)

    # the traded sizes of the last 20 seconds, from running totals
    first_inside = np.searchsorted(r, r - span, side='right')

    def last_20s(mask):
        running = np.cumsum(np.where(mask, size, 0))
        return running - np.concatenate(([0], running))[first_inside], running
    bought, bought_running = last_20s(trade & (side == F.BUY.decode()))
    sold, sold_running = last_20s(trade & (side == F.SELL.decode()))
    no_side, _ = last_20s(trade & (side != F.BUY.decode()) & (side != F.SELL.decode()))
    for name, expected in (('flow_bought_20s', bought), ('flow_sold_20s', sold), ('flow_no_side_20s', no_side)):
        need(got[name].tolist() == expected.tolist(), f'{name} differs from the recount')
    both = bought + sold
    flow = [(int(b) - int(s)) / int(t) if t else None for b, s, t in zip(bought, sold, both)]
    need(got['flow_20s'].tolist() == flow, 'flow_20s differs from the recount')

    # the peaks, from the runs of equal flow: a run is a high when the flow rose into it (from a smaller size, from
    # the other side, or from no flow) and after it the flow is smaller, on the other side, or gone
    a, t = np.abs(bought - sold), both
    g = np.sign(bought - sold)
    starts = np.flatnonzero(np.concatenate(([True], (a[1:] * t[:-1] != a[:-1] * t[1:]) | (g[1:] != g[:-1]) |
                                            ((t[1:] > 0) != (t[:-1] > 0)))))
    ra, rt, rg = a[starts], t[starts], g[starts]
    rose = (ra > 0) & np.concatenate(([True], (rt[:-1] == 0) | (rg[1:] != rg[:-1]) |
                                      (ra[1:] * rt[:-1] > ra[:-1] * rt[1:])))
    fell = np.concatenate(((rt[1:] == 0) | (rg[1:] != rg[:-1]) | (ra[1:] * rt[:-1] < ra[:-1] * rt[1:]), [False]))
    runs = np.flatnonzero(rose & fell)
    high, known = starts[runs], starts[runs + 1]
    known_rows = np.flatnonzero(np.array([v is not None for v in got['peak_high_position']]))
    need(known_rows.tolist() == known.tolist(), 'the rows where a peak becomes known differ from the recount')
    for name in F.NAMES:
        if name.startswith('peak_') and name not in ('peak_highest_since_open', 'peak_since_previous_peak_ns'):
            unknown = np.ones(len(d), bool)
            unknown[known] = False
            need(all(v is None for v in got[name][unknown]), f'{name} is filled on a row where no peak became known')
    need(got['peak_high_position'][known].tolist() == position[high].tolist(), 'the tick of the high differs')
    need(got['peak_high_received_time_ns'][known].tolist() == r[high].tolist(), 'the time of the high differs')
    need(got['peak_side'][known].tolist() == [F.BUY_TEXT if b > s else F.SELL_TEXT
                                              for b, s in zip(bought[high], sold[high])], 'the side of a peak differs')
    need(got['peak_size'][known].tolist() == [int(x) / int(y) for x, y in zip(a[high], t[high])],
         'the size of a peak differs')
    gaps = [None] + np.diff(r[high]).tolist() if len(high) else []
    need(got['peak_since_previous_peak_ns'][known].tolist() == gaps, 'the time since the peak before differs')

    # every moment the flow changed: each tick, and each moment between ticks at which a trade turned 20 seconds old
    left = np.unique(r[trade] + span)
    left = left[(left < r[-1]) & ~np.isin(left, r)]
    row_at = np.searchsorted(r, left, side='right') - 1
    gone = np.searchsorted(r, left - span, side='right')
    left_b = bought_running[row_at] - np.concatenate(([0], bought_running))[gone]
    left_s = sold_running[row_at] - np.concatenate(([0], sold_running))[gone]
    when = np.concatenate((r, left))
    order = np.argsort(when, kind='stable')
    when = when[order]
    sa = np.concatenate((a, np.abs(left_b - left_s)))[order]
    st = np.concatenate((t, left_b + left_s))[order]
    state_of_row = np.empty(len(when), np.int64)
    state_of_row[order] = np.arange(len(when))
    state_of_row = state_of_row[:len(r)]
    seg = np.flatnonzero(np.concatenate(([True], (sa[1:] * st[:-1] != sa[:-1] * st[1:]) | ((st[1:] > 0) != (st[:-1] > 0)))))
    seg_of_state = np.cumsum(np.concatenate(([True], (sa[1:] * st[:-1] != sa[:-1] * st[1:]) |
                                             ((st[1:] > 0) != (st[:-1] > 0))))) - 1
    ga, gt, begins = sa[seg], st[seg], when[seg]
    ends = np.concatenate((begins[1:], [when[-1]]))
    first_flow_at = int(begins[np.flatnonzero(gt > 0)[0]]) if (gt > 0).any() else None
    standing, highest_for, since_open = [], [], []
    for h, k in zip(high.tolist(), known.tolist()):
        va, vt, at = int(a[h]), int(t[h]), int(r[k])
        lasted = np.clip(np.minimum(ends, at) - begins, 0, None)
        total = int(lasted[gt > 0].sum())
        standing.append(int(lasted[(gt > 0) & (ga * vt < va * gt)].sum()) / total if total else None)
        own = int(seg_of_state[state_of_row[h]])
        larger = np.flatnonzero((gt[:own] > 0) & (ga[:own] * vt > va * gt[:own]))
        since_open.append(len(larger) == 0)
        highest_for.append(int(r[h]) - (first_flow_at if len(larger) == 0 else int(ends[larger[-1]])))
    need(got['peak_standing_so_far'][known].tolist() == standing, 'the standing of a peak differs from the recount')
    need(got['peak_highest_for_ns'][known].tolist() == highest_for, 'how long a peak had been the highest differs')
    need(got['peak_highest_since_open'][known].tolist() == since_open, 'highest since the open differs')
    return dict(passed=True, rows_compared=int(rows.num_rows), trade_day_rows=int(len(d)),
                rows_of_no_trade_day_all_empty=int((~in_day).sum()), peaks_compared=int(len(known)),
                moments_the_flow_changed=int(len(seg)),
                method='whole-column recount from the stored rows; shares no code with the tick-by-tick calculation')


def peak_story(row_files, calc_files, trade_day: dt.date, table_files=None, rows_folder=None) -> dict:
    """The check of the calculation `peak_story`: every fact worked out again, peak by peak, from the stored rows
    and the already checked flow columns, by looking ahead along whole columns (the calculation itself only ever
    looks at the tick in front of it). The two must give the same facts, in the same order, with the same values;
    the same count on every row; and the same peaks still open at the last tick."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from fractions import Fraction
    from root.calcs import flow_peak as F
    from root.calcs import peak_story as P
    from root.calendar import TRADE_DAY
    day = f'{trade_day:%Y%m%d}'
    rows = pa.concat_tables([pq.read_table(f, columns=['position_on_tape', 'received_time_ns', 'action', 'price',
                                                       'row_label', 'trade_day']) for f in row_files])
    flow_files = sorted(Path(rows_folder).glob(f'calc-flow_peak-{day}-part*.parquet'))
    need(len(flow_files) == len(row_files), 'the stored flow columns (calculation flow_peak) are not beside the rows')
    flow = pa.concat_tables([pq.read_table(f, columns=['position_on_tape', 'flow_bought_20s', 'flow_sold_20s',
                                                       'peak_high_position']) for f in flow_files])
    calc = pa.concat_tables([pq.read_table(f) for f in calc_files])
    need(rows.column('position_on_tape').equals(calc.column('position_on_tape')) and
         rows.column('position_on_tape').equals(flow.column('position_on_tape')), 'positions differ from the rows')
    text = lambda name: np.array(rows.column(name).to_pylist(), dtype=object)
    in_day = (text('row_label') == TRADE_DAY) & (text('trade_day') == trade_day.isoformat())
    known_count = np.array(calc.column('peak_facts_known').to_pylist(), dtype=object)
    need(all(v is None for v in known_count[~in_day]), 'peak_facts_known is filled on a row of no trade day')
    d = np.flatnonzero(in_day)
    n = len(d)
    position = rows.column('position_on_tape').to_numpy()[d]
    r = rows.column('received_time_ns').to_numpy()[d]
    trade = text('action')[d] == F.TRADE.decode()
    price = rows.column('price').to_numpy()[d].astype(np.int64)
    bought = np.array(flow.column('flow_bought_20s').to_pylist(), dtype=object)[d].astype(np.int64)
    sold = np.array(flow.column('flow_sold_20s').to_pylist(), dtype=object)[d].astype(np.int64)
    high_position = np.array(flow.column('peak_high_position').to_pylist(), dtype=object)[d]
    known = np.flatnonzero(np.array([v is not None for v in high_position]))
    high = np.searchsorted(position, high_position[known].astype(np.int64))
    need(position[high].tolist() == high_position[known].tolist(), 'a high names a tick with no row')
    diff, total = bought - sold, bought + sold
    last_trade = np.maximum.accumulate(np.where(trade, np.arange(n), -1))
    price_now = [None if k < 0 else int(price[k]) for k in last_trade.tolist()]
    least, most = np.iinfo(np.int64).min, np.iinfo(np.int64).max
    up, down = np.where(trade, price, least), np.where(trade, price, most)
    at_zero = {s: np.flatnonzero((total == 0) | (s * diff <= 0)) for s in (1, -1)}
    on_side = {s: np.flatnonzero((total > 0) & (s * diff > 0)) for s in (1, -1)}
    names = P.FACT_NAMES
    at = {name: k for k, name in enumerate(names)}

    def first_at_or_after(where, start):
        k = np.searchsorted(where, start)
        return int(where[k]) if k < len(where) else n

    expected, still_open, before = [], [], -1
    for h, k in zip(high.tolist(), known.tolist()):
        s = 1 if diff[h] > 0 else -1
        va, vt = int(abs(diff[h])), int(total[h])
        zero = first_at_or_after(at_zero[s], h + 1)
        num, den = (s * diff[h + 1:zero]).astype(np.int64), total[h + 1:zero]
        over = np.flatnonzero(num * vt > va * den)
        beaten = h + 1 + int(over[0]) if len(over) else None
        stop = beaten if beaten is not None else zero
        ratio = num[:stop - h - 1] / den[:stop - h - 1]
        floor = np.minimum.accumulate(np.concatenate(([va / vt], ratio)))
        lows = (h + 1 + np.flatnonzero(ratio < floor[:-1])).tolist()
        share = lambda i: None if total[i] == 0 else Fraction(int(s * diff[i]) * vt, int(total[i]) * va)
        moments = [(i, P.NEW_LOW) for i in lows]
        back = None
        if beaten is not None:
            moments.append((beaten, P.BEATEN))
        elif zero < n:
            moments.append((zero, P.REACHED_ZERO))
            back = first_at_or_after(on_side[s], zero + 1)
            if back < n:
                moments.append((back, P.CAME_BACK))
        end = max([k] + [i for i, _ in moments])
        top = np.maximum.accumulate(up[h:end + 1])
        bottom = np.minimum.accumulate(down[h:end + 1])

        def line(i, kind):
            row = [None] * len(names)
            row[at['known_position']], row[at['known_received_time_ns']] = int(position[i]), int(r[i])
            row[at['peak_high_position']], row[at['fact']] = int(position[h]), kind
            row[at['since_high_ns']] = int(r[i] - r[h])
            row[at['price_at_high']], row[at['price_now']] = price_now[h], price_now[i]
            row[at['highest_price_since_high']] = None if top[i - h] == least else int(top[i - h])
            row[at['lowest_price_since_high']] = None if bottom[i - h] == most else int(bottom[i - h])
            return row
        row = line(k, P.BUILD_UP)
        if h > before + 1:
            span = slice(before + 1, h)
            on_its_side = s * np.where(total[span] > 0, diff[span] / np.maximum(total[span], 1), 0.0)
            low = before + 1 + int(np.flatnonzero(on_its_side == on_its_side.min())[-1])
            row[at['low_position']] = int(position[low])
            row[at['low_size']] = None if total[low] == 0 else abs(int(diff[low]) / int(total[low]))
            row[at['low_flow']] = None if total[low] == 0 else int(diff[low]) / int(total[low])
            row[at['low_to_high_ns']], row[at['low_price']] = int(r[h] - r[low]), price_now[low]
        expected.append((int(position[k]), 0, int(position[h]), tuple(row)))
        lowest = Fraction(1)
        for i, kind in moments:
            row, here = line(i, kind), share(i)
            row[at['share_of_peak_left']] = None if here is None else float(here)
            if kind == P.NEW_LOW:
                lowest = here
            if kind != P.CAME_BACK:
                row[at['lowest_share_so_far']] = float(lowest)
            else:
                row[at['away_ns']] = int(r[i] - r[zero])
                seen_up, seen_down = up[zero:i + 1].max(), down[zero:i + 1].min()
                row[at['highest_price_since_zero']] = None if seen_up == least else int(seen_up)
                row[at['lowest_price_since_zero']] = None if seen_down == most else int(seen_down)
            expected.append((int(position[i]), 1, int(position[h]), tuple(row)))
        if beaten is None and (zero >= n or back >= n):
            still_open.append((int(position[h]), zero < n, float(lowest)))
        before = h
    expected = [row for _, _, _, row in sorted(expected, key=lambda e: e[:3])]
    facts = pa.concat_tables([pq.read_table(f) for f in table_files['facts']])
    got = list(zip(*[facts.column(name).to_pylist() for name in names]))
    for a, b in zip(got, expected):
        need(a == b, f'a fact differs from the recount: stored {dict(zip(names, a))}, recount {dict(zip(names, b))}')
    need(len(got) == len(expected), f'{len(got)} facts stored, {len(expected)} in the recount')
    per_row = collections.Counter(row[at['known_position']] for row in expected)
    need(known_count[d].tolist() == [per_row.get(int(p), 0) for p in position],
         'the count of facts known on a row differs from the recount')
    left = pa.concat_tables([pq.read_table(f) for f in table_files['open-at-the-end']])
    need(sorted(zip(*[left.column(c).to_pylist() for c in P.OPEN_COLUMNS])) == sorted(still_open),
         'the peaks still open at the last tick differ from the recount')
    kinds = collections.Counter(row[at['fact']] for row in expected)
    return dict(passed=True, peaks=int(len(known)), facts_compared=len(expected), facts_by_kind=dict(kinds),
                most_facts_on_one_tick=max(per_row.values()) if per_row else 0,
                peaks_still_open_at_the_last_tick=len(still_open),
                method='every fact found again by looking ahead along whole columns of the stored rows; shares no '
                       'code with the tick-by-tick calculation')


KNOWN_AT_A_TICK = {'facts'}            # the tables whose lines each carry the tick at which they became known
CALC_CHECKS = {'flow_peak': flow_peak, 'peak_story': peak_story}


def playback_cuts(name: str, full: list, tables: dict) -> dict:
    """Where, besides the middle tick, a calculation's playback is cut: a tick chosen to fall inside something
    still unfolding. Given as {why: the position of the last tick given}."""
    if name == 'flow_peak':
        from root.calcs import flow_peak as F
        at = F.NAMES.index('peak_high_position')
        highs = [values[at] for _, values in full if values[at] is not None]
        return {'the high of the middle peak': highs[len(highs) // HALVE]} if highs else {}
    facts = tables.get('facts', [])
    return {'the tick the middle fact became known': facts[len(facts) // HALVE][0]} if facts else {}
