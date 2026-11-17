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


def _stored(row_files, calc_files, columns):
    """The stored rows (the named columns) and a calculation's stored columns, with the rows of the trade day."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    rows = pa.concat_tables([pq.read_table(f, columns=['position_on_tape', 'row_label', 'trade_day'] + columns)
                             for f in row_files])
    calc = pa.concat_tables([pq.read_table(f) for f in calc_files])
    need(rows.column('position_on_tape').equals(calc.column('position_on_tape')), 'positions differ from the rows')
    return rows, calc


def book_totals(row_files, calc_files, trade_day: dt.date, table_files=None, rows_folder=None) -> dict:
    """The check of the calculation `book_totals`, three ways, on every row of the trade day:
    1. every running total worked out again from whole columns (the fills of each exchange event gathered first,
       then laid on the rows; "at the best price" taken from the count of better levels on the row, which the
       calculation does not read);
    2. the foundation's own whole-side sizes: on every row the bid (ask) total size equals its size at the open
       plus added minus pulled minus filled;
    3. the size filled equals the size of the tape's fill messages, one for one."""
    import numpy as np
    import pyarrow.compute as pc
    from root.calcs import book_totals as B
    rows, calc = _stored(row_files, calc_files, [
        'action', 'side', 'size', 'order_number', 'exchange_event', 'what_happened', 'order_size_before',
        'order_size_after', 'levels_from_best', 'touched_price', 'left_price', 'left_line_orders_after', 'best_bid',
        'best_ask', 'bid_total_size', 'ask_total_size'])
    text = lambda name: np.array(rows.column(name).to_pylist(), dtype=object)
    in_day = (text('row_label') == TRADE_DAY) & (text('trade_day') == trade_day.isoformat())
    got = {name: np.array(calc.column(name).to_pylist(), dtype=object) for name in B.NAMES}
    for name in B.NAMES:
        need(all(v is None for v in got[name][~in_day]), f'{name} is filled on a row of no trade day')
    d = np.flatnonzero(in_day)
    n = len(d)
    whole = lambda name: pc.fill_null(rows.column(name), -1).to_numpy().astype(np.int64)      # -1 where empty
    number = lambda name: whole(name)[d]
    action, side, what = text('action')[d], text('side')[d], text('what_happened')[d]
    need(set(what.tolist()) <= set(B.CHANGES) | {R.NO_CHANGE}, 'a row outside the rule of book_totals')
    size, order, event = number('size'), number('order_number'), number('exchange_event')
    before, after = number('order_size_before'), number('order_size_after')
    better, touched, left = number('levels_from_best'), number('touched_price'), number('left_price')
    change = np.isin(what, B.CHANGES)
    need(bool(np.isin(side[change], list(B.SIDES)).all()), 'an order changed with no side on the row')

    # the fills of each exchange event, gathered first; then each laid on its order's first row after them
    filled_by, last_fill = {}, {}
    for i in np.flatnonzero(action == B.FILL).tolist():
        key = (int(event[i]), int(order[i]))
        entry = filled_by.setdefault(key, [0, 0])
        entry[0] += int(size[i])
        entry[1] += 0 if side[i] in B.SIDES else int(size[i])
        last_fill[key] = i
    fill, no_side, shown = np.zeros(n, np.int64), np.zeros(n, np.int64), set()
    for i in np.flatnonzero(change).tolist():
        key = (int(event[i]), int(order[i]))
        if key in filled_by and key not in shown and i > last_fill[key]:
            fill[i], no_side[i] = filled_by[key]
            shown.add(key)
    waiting = sum(v[0] for k, v in filled_by.items() if k not in shown)
    need(not ((fill == 0) & np.isin(what, (R.SHRANK_BY_FILL, R.LEFT_BY_FILL))).any(),
         'a row says "by fill" with no fill message before it in its exchange event')

    had = np.where(what == R.JOINED, 0, before)
    remains = had - fill
    added, pulled = np.clip(after - remains, 0, None) * change, np.clip(remains - after, 0, None) * change
    moving = what == R.LOST_PLACE_PRICE
    moved = np.where(moving, np.minimum(np.clip(remains, 0, None), after), 0)
    refilled = np.where(fill > 0, np.minimum(added, fill), 0)
    # at the best price, from the count of better levels just before the tick (on a price change that count is
    # for the price joined; the price left was the best when it equals the best price on the row before)
    at_best = better == 0
    out = {}
    for code, name in B.SIDES.items():
        mine = change & (side == code)
        best_all = whole('best_bid' if code == B.BID else 'best_ask')
        need(not moving[0], 'the first tick of the trade day changes a price: the best price before it is not known')
        best_row_before = np.concatenate(([-1], best_all[d[1:] - 1]))
        left_best = np.where(moving, left == best_row_before, at_best)
        toward = (left > touched) if code == B.BID else (left < touched)       # the line left was the better one
        emptied = number('left_line_orders_after') == 0
        joins_best = np.where(moving, better - (toward & emptied) == 0, at_best)
        for key, each in (('added', added), ('pulled', pulled), ('filled', fill), ('moved', moved),
                          ('added_at_best', added * joins_best), ('pulled_at_best', pulled * left_best),
                          ('filled_at_best', fill * left_best), ('moved_from_best', moved * left_best),
                          ('moved_to_best', moved * joins_best), ('refilled', refilled),
                          ('refilled_at_best', refilled * joins_best), ('filled_no_side', no_side)):
            out[f'{name}_{key}'] = np.cumsum(np.where(mine, each, 0))
    for name in B.NAMES:
        need(got[name][d].tolist() == out[name].tolist(), f'{name} differs from the recount')

    # the foundation's whole-side sizes
    opens = {}
    for name in B.SIDES.values():
        total = whole(f'{name}_total_size')
        net = out[f'{name}_added'] - out[f'{name}_pulled'] - out[f'{name}_filled']
        opens[name] = int(total[d[0]] - net[0])
        need((total[d] == opens[name] + net).all(), f'the {name} total size is not its size at the open plus added '
                                                  f'minus pulled minus filled on every row')
        if d[0]:
            need(int(total[d[0] - 1]) == opens[name], f'the {name} size at the open is not the book just before it')
    fill_messages = int(size[action == B.FILL].sum())
    counted = int(out['bid_filled'][-1] + out['ask_filled'][-1])
    need(counted + waiting == fill_messages, 'the size filled is not the size of the fill messages')
    return dict(passed=True, rows_compared=int(rows.num_rows), trade_day_rows=n,
                rows_of_no_trade_day_all_empty=int((~in_day).sum()), columns_compared=len(B.NAMES),
                size_at_the_open=opens, total_size_identity_holds_on_every_row=True,
                size_of_fill_messages=fill_messages, size_counted_as_filled=counted,
                size_of_fills_waiting_at_the_last_tick=int(waiting),
                rows_where_a_fill_was_put_back=int(((fill > 0) & (added > 0)).sum()),
                rows_where_more_left_than_was_filled=int(((fill > 0) & (pulled > 0)).sum()),
                method='whole-column recount from the stored rows, with the best price taken from the count of '
                       'better levels; the foundation\'s total sizes; the fill messages. Shares no code with the '
                       'tick-by-tick calculation')


def quote_runs(row_files, calc_files, trade_day: dt.date, table_files=None, rows_folder=None) -> dict:
    """The check of the calculation `quote_runs`: every run found again from the foundation's own marks of a best
    price moving (the calculation reads only the best-price columns and never the marks), along whole columns.
    The two must give the same facts in the same order with the same values, the same run in progress on every
    row, and the same runs still going at the last tick."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from root.calcs import quote_runs as Q
    marks = {Q.BEST_BID: ('best_bid_moved_from', 'best_bid_moved_to'),
             Q.BEST_ASK: ('best_ask_moved_from', 'best_ask_moved_to')}
    rows, calc = _stored(row_files, calc_files, ['received_time_ns', 'gap'] + [c for m in marks.values() for c in m])
    text = lambda name: np.array(rows.column(name).to_pylist(), dtype=object)
    in_day = (text('row_label') == TRADE_DAY) & (text('trade_day') == trade_day.isoformat())
    got = {name: np.array(calc.column(name).to_pylist(), dtype=object) for name in Q.NAMES}
    for name in Q.NAMES:
        need(all(v is None for v in got[name][~in_day]), f'{name} is filled on a row of no trade day')
    d = np.flatnonzero(in_day)
    n = len(d)
    position = rows.column('position_on_tape').to_numpy()[d]
    r = rows.column('received_time_ns').to_numpy()[d]
    gap = text('gap')[d]
    names = Q.FACT_NAMES
    expected, still_going, on_first_tick = [], [], 0
    for q_index, quote in enumerate(Q.QUOTES):
        frm, to = (text(c)[d] for c in marks[quote])
        m = np.flatnonzero(np.array([v is not None for v in to]))
        need(all(v is not None for v in frm[m]), 'a mark of a best price moving has no price it moved from')
        on_first_tick += int(len(m) > 0 and m[0] == 0)
        m = m[m > 0]                                   # a move made by the first tick starts from before the trade day
        f, t = frm[m].astype(np.int64), to[m].astype(np.int64)
        need((f[1:] == t[:-1]).all(), f'the marks of the {quote} do not follow on from each other')
        up = t > f
        need((t != f).all(), f'a mark of the {quote} moving names the same price twice')
        new = np.concatenate(([True], up[1:] != up[:-1])) if len(m) else np.zeros(0, bool)
        first = np.flatnonzero(new)                    # the first move of each run
        run_of = np.cumsum(new) - 1
        start_move = first[run_of] if len(m) else first
        key = quote.split()[-1]
        columns = {name: [None] * n for name, _ in Q.RUN_FIGURES}
        last = np.searchsorted(m, np.arange(n), side='right') - 1
        for i in np.flatnonzero(last >= 0).tolist():
            k = int(last[i])
            s = int(start_move[k])
            columns['run_start_position'][i] = int(position[m[s]])
            columns['run_direction'][i] = Q.UP if up[s] else Q.DOWN
            columns['run_price_before'][i] = int(f[s])
            columns['run_moves'][i] = k - s + 1
            columns['run_distance'][i] = int(t[k] - f[s])
            columns['run_since_start_ns'][i] = int(r[i] - r[m[s]])
        for name, values in columns.items():
            need(got[f'{key}_{name}'][d].tolist() == values, f'{key}_{name} differs from the recount')

        def line(k, s, kind, far, moves, back=None):
            i = int(m[k])
            row = dict.fromkeys(names)
            row.update(known_position=int(position[i]), known_received_time_ns=int(r[i]), quote=quote,
                       run_start_position=int(position[m[s]]), fact=kind, direction=Q.UP if up[s] else Q.DOWN,
                       price_before_run=int(f[s]), price_before_tick=int(f[k]), price_now=int(t[k]),
                       furthest_price=int(far), moves=moves, distance=int(far - f[s]),
                       since_run_start_ns=int(r[i] - r[m[s]]),
                       since_previous_move_ns=int(r[i] - r[m[k - 1]]) if k else None, gap_now=gap[i])
            if back:
                row.update(step_back=int(t[k] - far), since_furthest_ns=int(r[i] - r[m[k - 1]]))
            return tuple(row[name] for name in names)
        for k in range(len(m)):
            s = int(start_move[k])
            if new[k]:
                if k:
                    before = int(start_move[k - 1])
                    expected.append((int(position[m[k]]), q_index, 0, line(k, before, Q.STEP_BACK, t[k - 1],
                                                                           k - before, back=True)))
                expected.append((int(position[m[k]]), q_index, 1, line(k, s, Q.STARTED, t[k], 1)))
            else:
                expected.append((int(position[m[k]]), q_index, 1, line(k, s, Q.FURTHER, t[k], k - s + 1)))
        if len(m):
            s = int(first[-1])
            still_going.append((quote, int(position[m[s]]), Q.UP if up[s] else Q.DOWN, int(f[s]), int(t[-1]),
                                len(m) - s))
    expected = [row for _, _, _, row in sorted(expected, key=lambda e: e[:3])]
    facts = pa.concat_tables([pq.read_table(f) for f in table_files['facts']])
    stored = list(zip(*[facts.column(name).to_pylist() for name in names]))
    for a, b in zip(stored, expected):
        need(a == b, f'a fact differs from the recount: stored {dict(zip(names, a))}, recount {dict(zip(names, b))}')
    need(len(stored) == len(expected), f'{len(stored)} facts stored, {len(expected)} in the recount')
    at = names.index('known_position')
    per_row = collections.Counter(row[at] for row in expected)
    need(got['quote_run_facts_known'][d].tolist() == [per_row.get(int(p), 0) for p in position],
         'the count of facts known on a row differs from the recount')
    left = pa.concat_tables([pq.read_table(f) for f in table_files['open-at-the-end']])
    need(sorted(zip(*[left.column(c).to_pylist() for c in Q.OPEN_COLUMNS])) == sorted(still_going),
         'the runs still going at the last tick differ from the recount')
    kinds = collections.Counter((row[names.index('quote')], row[names.index('fact')]) for row in expected)
    return dict(passed=True, trade_day_rows=n, rows_of_no_trade_day_all_empty=int((~in_day).sum()),
                facts_compared=len(expected), facts_by_kind={f'{q}: {k}': v for (q, k), v in sorted(kinds.items())},
                most_facts_on_one_tick=max(per_row.values()) if per_row else 0,
                moves_made_by_the_first_tick_of_the_trade_day=on_first_tick,
                runs_still_going_at_the_last_tick=len(still_going),
                method='every run found again from the foundation\'s marks of a best price moving, along whole '
                       'columns; the calculation reads the best-price columns and never the marks')


def _peaks_as_stored(rows_folder, trade_day: dt.date, positions):
    """The peaks of a trade day read from the stored (and already checked) outputs of pieces 1 and 2, in the order
    they became known: for each, the row it became known on, its high, side, size, the time and price of its high,
    and the rows on which its story reached zero and ended (None where it did not) with how it ended."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from root.calcs import peak_story as P
    day = f'{trade_day:%Y%m%d}'
    flow_files = sorted(Path(rows_folder).glob(f'calc-flow_peak-{day}-part*.parquet'))
    fact_files = sorted(Path(rows_folder).glob(f'calc-peak_story-facts-{day}-part*.parquet'))
    need(flow_files and fact_files, 'the stored outputs of flow_peak and peak_story are not beside the rows')
    flow = pa.concat_tables([pq.read_table(f, columns=['position_on_tape', 'peak_side', 'peak_size',
                                                       'peak_high_position', 'peak_high_received_time_ns'])
                             for f in flow_files]).to_pydict()
    facts = pa.concat_tables([pq.read_table(f, columns=['known_position', 'peak_high_position', 'fact',
                                                        'price_at_high']) for f in fact_files]).to_pydict()
    row_of = {int(p): k for k, p in enumerate(positions)}
    price, zero, end = {}, {}, {}
    for at, high, kind, at_high in zip(facts['known_position'], facts['peak_high_position'], facts['fact'],
                                       facts['price_at_high']):
        if kind == P.BUILD_UP:
            price[high] = at_high
        elif kind == P.REACHED_ZERO:
            zero[high] = row_of[at]
        elif kind in (P.CAME_BACK, P.BEATEN):
            end[high] = (row_of[at], kind)
    peaks = [dict(known=row_of[at], high=high, side=side, size=size, high_at=high_at, price=price[high],
                  zero=zero.get(high), end=end.get(high, (None, None))[0], how=end.get(high, (None, None))[1])
             for at, high, side, size, high_at in zip(flow['position_on_tape'], flow['peak_high_position'],
                                                      flow['peak_side'], flow['peak_size'],
                                                      flow['peak_high_received_time_ns']) if high is not None]
    need(len(peaks) == len(price), 'the stored peaks and the stored build-up facts are not the same peaks')
    return peaks


def peak_links(row_files, calc_files, trade_day: dt.date, table_files=None, rows_folder=None) -> dict:
    """The check of the calculation `peak_links`: every link worked out again from the stored outputs of pieces 1
    and 2 as whole tables (the calculation follows the peaks tick by tick and reads no stored file): which peaks
    came before each one, whether their stories had ended by then, and how many peaks became known inside each
    story. The facts, the count on every row and the peaks still open at the last tick must all be equal."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from root.calcs import peak_links as L
    rows, calc = _stored(row_files, calc_files, ['received_time_ns'])
    text = lambda name: np.array(rows.column(name).to_pylist(), dtype=object)
    in_day = (text('row_label') == TRADE_DAY) & (text('trade_day') == trade_day.isoformat())
    count = np.array(calc.column('peak_link_facts_known').to_pylist(), dtype=object)
    need(all(v is None for v in count[~in_day]), 'peak_link_facts_known is filled on a row of no trade day')
    d = np.flatnonzero(in_day)
    position = rows.column('position_on_tape').to_numpy()[d]
    r = rows.column('received_time_ns').to_numpy()[d]
    peaks = _peaks_as_stored(rows_folder, trade_day, position)
    known = np.array([p['known'] for p in peaks])
    need((np.diff(known) > 0).all(), 'two peaks became known on one tick')
    names = L.FACT_NAMES
    expected, still_open, last, most = [], [], {}, 0

    def line(kind, p, row):
        out = dict.fromkeys(names)
        out.update(known_position=int(position[row]), known_received_time_ns=int(r[row]),
                   peak_high_position=p['high'], fact=kind, side=p['side'], price_at_high=p['price'])
        return out
    for j, p in enumerate(peaks):
        out, missing = line(L.KNOWN, p, p['known']), []
        other = [side for side in last if side != p['side']]
        for key, earlier, why in (('same_side', last.get(p['side']), L.NO_SAME),
                                  ('other_side', last[other[0]] if other else None, L.NO_OTHER)):
            if earlier is None:
                missing.append(why)
                continue
            out[f'{key}_high_position'] = earlier['high']
            out[f'{key}_high_to_high_ns'] = p['high_at'] - earlier['high_at']
            out[f'{key}_price_at_high'] = earlier['price']
            out[f'{key}_story_open'] = earlier['end'] is None or earlier['end'] > p['known']
        if j:
            out.update(before_high_position=peaks[j - 1]['high'], before_same_side=peaks[j - 1]['side'] == p['side'])
        out['no_link_because'] = '; '.join(missing) if missing else None
        expected.append((p['known'], 1, j, tuple(out[name] for name in names)))
        last[p['side']] = p
        # the peaks that became known after this one and before its story ended (not on the tick it ended)
        until = len(d) if p['end'] is None else p['end']
        later = int(np.searchsorted(known, until, side='left')) - (j + 1)
        first = peaks[j + 1]['high'] if later else None
        if p['end'] is None:
            still_open.append((p['high'], later, first))
        else:
            out = line(L.ENDED, p, p['end'])
            out.update(ended_by=p['how'], later_peaks_while_open=later, first_later_high_position=first)
            expected.append((p['end'], 0, j, tuple(out[name] for name in names)))
            most = max(most, later)
    expected = [row for _, _, _, row in sorted(expected, key=lambda e: e[:3])]
    facts = pa.concat_tables([pq.read_table(f) for f in table_files['facts']])
    stored = list(zip(*[facts.column(name).to_pylist() for name in names]))
    for a, b in zip(stored, expected):
        need(a == b, f'a fact differs from the recount: stored {dict(zip(names, a))}, recount {dict(zip(names, b))}')
    need(len(stored) == len(expected), f'{len(stored)} facts stored, {len(expected)} in the recount')
    per_row = collections.Counter(row[0] for row in expected)
    need(count[d].tolist() == [per_row.get(int(p), 0) for p in position],
         'the count of facts known on a row differs from the recount')
    left = pa.concat_tables([pq.read_table(f) for f in table_files['open-at-the-end']])
    need(sorted(zip(*[left.column(c).to_pylist() for c in L.OPEN_COLUMNS])) == sorted(still_open),
         'the peaks still open at the last tick differ from the recount')
    at = {name: k for k, name in enumerate(names)}
    known_lines = [row for row in expected if row[at['fact']] == L.KNOWN]
    return dict(passed=True, peaks=len(peaks), facts_compared=len(expected),
                peak_before_on_the_same_side=sum(1 for row in known_lines if row[at['before_same_side']]),
                peak_before_on_the_other_side=sum(1 for row in known_lines if row[at['before_same_side']] is False),
                peaks_known_while_the_peak_before_was_still_open=sum(
                    1 for j, p in enumerate(peaks) if j and (peaks[j - 1]['end'] is None or
                                                             peaks[j - 1]['end'] > p['known'])),
                stories_with_a_later_peak_inside=sum(1 for row in expected if row[at['later_peaks_while_open']]),
                most_later_peaks_while_one_story_was_open=most,
                peaks_still_open_at_the_last_tick=len(still_open),
                method='every link worked out again from the stored outputs of pieces 1 and 2 as whole tables; '
                       'shares no code with the tick-by-tick calculation')


def open_stories(row_files, calc_files, trade_day: dt.date, table_files=None, rows_folder=None) -> dict:
    """The check of the calculation `open_stories`: every column worked out again from the stored outputs of
    pieces 1 and 2. Each peak's story is a stretch of rows (from the row it became known on to the row before the
    one it ended on); the counts are running sums of where stretches start and stop, and the oldest, newest and
    largest open peak are found by laying the stretches over the rows in order."""
    import numpy as np
    from root.calcs import open_stories as O
    rows, calc = _stored(row_files, calc_files, [])
    text = lambda name: np.array(rows.column(name).to_pylist(), dtype=object)
    in_day = (text('row_label') == TRADE_DAY) & (text('trade_day') == trade_day.isoformat())
    got = {name: np.array(calc.column(name).to_pylist(), dtype=object) for name in O.NAMES}
    for name in O.NAMES:
        need(all(v is None for v in got[name][~in_day]), f'{name} is filled on a row of no trade day')
    d = np.flatnonzero(in_day)
    n = len(d)
    position = rows.column('position_on_tape').to_numpy()[d]
    peaks = _peaks_as_stored(rows_folder, trade_day, position)
    most = {}
    for side in O.SIDES:
        mine = [p for p in peaks if p['side'] == side]
        step, past = np.zeros(n + 1, np.int64), np.zeros(n + 1, np.int64)
        for p in mine:
            until = n if p['end'] is None else p['end']
            step[p['known']] += 1
            step[until] -= 1
            if p['zero'] is not None:
                past[p['zero']] += 1
                past[until] -= 1
        counted = np.cumsum(step)[:n]
        need(got[f'{side}_open_stories'][d].tolist() == counted.tolist(), f'{side}_open_stories differs')
        need(got[f'{side}_open_stories_past_zero'][d].tolist() == np.cumsum(past)[:n].tolist(),
             f'{side}_open_stories_past_zero differs')
        most[side] = int(counted.max()) if n else 0
        # laid over the rows in order, the last one laid on a row is the one that shows there
        for key, order in (('oldest', sorted(mine, key=lambda p: -p['known'])),
                           ('newest', sorted(mine, key=lambda p: p['known'])),
                           ('largest', sorted(mine, key=lambda p: (p['size'], -p['known'])))):
            shows = np.full(n, -1, np.int64)
            for p in order:
                shows[p['known']:n if p['end'] is None else p['end']] = p['high']
            need(got[f'{side}_{key}_open_high_position'][d].tolist() == [None if v < 0 else v for v in shows.tolist()],
                 f'{side}_{key}_open_high_position differs from the recount')
    return dict(passed=True, trade_day_rows=n, rows_of_no_trade_day_all_empty=int((~in_day).sum()),
                columns_compared=len(O.NAMES), peaks=len(peaks),
                most_stories_open_at_one_tick=most,
                method='each story laid over the rows as a stretch, from the stored outputs of pieces 1 and 2; '
                       'shares no code with the tick-by-tick calculation')


def _facts_equal(table_files, names, expected, what='fact'):
    """The stored lines of a table against the recount: the same lines, in the same order, with the same values."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pa.concat_tables([pq.read_table(f) for f in table_files])
    stored = list(zip(*[table.column(name).to_pylist() for name in names]))
    for a, b in zip(stored, expected):
        need(a == b, f'a {what} differs from the recount: stored {dict(zip(names, a))}, recount {dict(zip(names, b))}')
    need(len(stored) == len(expected), f'{len(stored)} {what}s stored, {len(expected)} in the recount')


def refills(row_files, calc_files, trade_day: dt.date, table_files=None, rows_folder=None) -> dict:
    """The check of the calculation `refills` (addition L), along whole columns:
    1. every fact found again: the fill messages of each exchange event are gathered first and each laid on its
       order's row (the calculation meets them tick by tick), and the figures an order carries "so far" are
       running sums taken after sorting the filled rows by order;
    2. the size put back, added up for each side, equals the last value of that side's `refilled` running total in
       the stored (and already checked) book totals."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from root.calcs import refills as L
    rows, calc = _stored(row_files, calc_files, list(L.READS))
    text = lambda name: np.array(rows.column(name).to_pylist(), dtype=object)
    in_day = (text('row_label') == TRADE_DAY) & (text('trade_day') == trade_day.isoformat())
    count = np.array(calc.column('refill_facts_known').to_pylist(), dtype=object)
    need(all(v is None for v in count[~in_day]), 'refill_facts_known is filled on a row of no trade day')
    d = np.flatnonzero(in_day)
    n = len(d)
    as_is = lambda name: text(name)[d]                                 # empty stays empty
    number = lambda name: np.array([-1 if v is None else v for v in as_is(name)], dtype=np.int64)
    position = rows.column('position_on_tape').to_numpy()[d]
    action, side, what = as_is('action'), as_is('side'), as_is('what_happened')
    received, size, order, event = (number(c) for c in ('received_time_ns', 'size', 'order_number', 'exchange_event'))
    before, after = number('order_size_before'), number('order_size_after')
    resting = np.isin(what, L.CHANGES)

    # the fills of each exchange event, gathered first; then each laid on its order's first row after them
    filled_by, last_fill = {}, {}
    for i in np.flatnonzero(action == L.FILL).tolist():
        key = (int(event[i]), int(order[i]))
        filled_by[key] = filled_by.get(key, 0) + int(size[i])
        last_fill[key] = i
    fill, shown = np.zeros(n, np.int64), set()
    for i in np.flatnonzero(resting).tolist():
        key = (int(event[i]), int(order[i]))
        if key in filled_by and key not in shown and i > last_fill[key]:
            fill[i] = filled_by[key]
            shown.add(key)
    waiting = len(filled_by) - len(shown)

    back = after - (before - fill)                                     # what the row shows above what the fill left
    moved = what == R.LOST_PLACE_PRICE
    is_fact = (fill > 0) & ((back > 0) | moved)
    put_back = np.where(fill > 0, np.minimum(np.clip(back, 0, None), fill), 0)

    # an order's figures so far: the filled rows sorted by order (tape order kept inside an order), running sums
    filled_rows = np.flatnonzero(fill > 0)
    by_order = filled_rows[np.argsort(order[filled_rows], kind='stable')]
    filled_so_far, times = np.zeros(n, np.int64), np.zeros(n, np.int64)
    if len(by_order):
        first_of_order = np.concatenate(([True], order[by_order][1:] != order[by_order][:-1]))
        group_start = np.flatnonzero(first_of_order)[np.cumsum(first_of_order) - 1]

        def running(values):
            total = np.cumsum(values)
            return total - np.where(group_start > 0, total[group_start - 1], 0)
        filled_so_far[by_order] = running(fill[by_order])
        times[by_order] = running((back[by_order] > 0).astype(np.int64))

    names = L.FACT_NAMES
    touched, left, levels = as_is('touched_price'), as_is('left_price'), as_is('levels_from_best')
    entered = [as_is(c) for c in ('first_entered_exchange_time_ns', 'first_entered_received_time_ns',
                                  'entered_before_written_record')]
    expected, by_side = [], dict.fromkeys(L.SIDES.values(), 0)
    for i in np.flatnonzero(is_fact).tolist():
        row = dict.fromkeys(names)
        row.update(known_position=int(position[i]), known_received_time_ns=int(received[i]),
                   order_number=int(order[i]), fact=what[i], side=L.SIDES[side[i]],
                   price=left[i] if moved[i] else touched[i], price_after=touched[i], levels_from_best=levels[i],
                   size_filled=int(fill[i]), size_before=int(before[i]), size_after=int(after[i]),
                   size_put_back=int(put_back[i]), same_size_or_larger=bool(after[i] >= before[i]),
                   times_put_back_so_far=int(times[i]), size_filled_so_far=int(filled_so_far[i]),
                   first_entered_exchange_time_ns=entered[0][i], first_entered_received_time_ns=entered[1][i],
                   entered_before_written_record=entered[2][i])
        by_side[L.SIDES[side[i]]] += int(put_back[i])
        expected.append(tuple(row[name] for name in names))
    _facts_equal(table_files['facts'], names, expected)
    per_row = collections.Counter(row[0] for row in expected)
    need(count[d].tolist() == [per_row.get(int(p), 0) for p in position],
         'the count of facts known on a row differs from the recount')

    # the stored book totals: each side's size put back so far, at the last tick of the trade day
    total_files = sorted(Path(rows_folder).glob(f'calc-book_totals-{trade_day:%Y%m%d}-part*.parquet'))
    need(total_files, 'the stored book totals are not beside the rows')
    totals = pa.concat_tables([pq.read_table(f, columns=['position_on_tape'] + [f'{name}_refilled'
                                                                              for name in L.SIDES.values()])
                               for f in total_files])
    need(totals.column('position_on_tape').to_pylist() == rows.column('position_on_tape').to_pylist(),
         'the stored book totals are not on the same rows')
    in_totals = {name: totals.column(f'{name}_refilled')[int(d[-1])].as_py() for name in L.SIDES.values()}
    for name in L.SIDES.values():
        need(in_totals[name] == by_side[name], f'the {name} size put back ({by_side[name]}) is not the refilled '
                                              f'total of the stored book totals ({in_totals[name]})')
    at = {name: k for k, name in enumerate(names)}
    kinds = collections.Counter(row[at['fact']] for row in expected)
    per_order = collections.Counter(row[at['order_number']] for row in expected if row[at['size_put_back']])
    return dict(passed=True, trade_day_rows=n, rows_of_no_trade_day_all_empty=int((~in_day).sum()),
                facts_compared=len(expected), facts_by_what_happened=dict(sorted(kinds.items())),
                facts_with_size_put_back=sum(1 for row in expected if row[at['size_put_back']]),
                facts_same_size_or_larger=sum(1 for row in expected if row[at['same_size_or_larger']]),
                orders_with_size_put_back=len(per_order),
                most_times_on_one_order=max(per_order.values()) if per_order else 0,
                size_put_back=by_side, refilled_in_the_stored_book_totals=in_totals,
                fills_waiting_for_their_row_at_the_last_tick=waiting,
                method='the fill messages of each exchange event gathered first and laid on the rows; the figures '
                       'so far by sorting the filled rows by order; the size put back against the stored book '
                       'totals. Shares no code with the tick-by-tick calculation')


def sweeps(row_files, calc_files, trade_day: dt.date, table_files=None, rows_folder=None) -> dict:
    """The check of the calculation `sweeps` (addition M), along whole columns:
    1. the rows are grouped by the exchange event label; every group that holds a trade must end on the tick with
       the exchange's end mark and carry no end mark before it; its figures are taken from the group as a whole
       (the calculation builds them tick by tick), and "a best price moved" from the best-price columns either
       side of the group (the calculation reads the marks of a best price moving);
    2. the touches from where the stored gap goes to zero or below and where it comes back above."""
    import numpy as np
    import pyarrow as pa
    import pyarrow.parquet as pq
    from root.calcs import sweeps as S
    from root.outside import UNDEFINED_PRICE
    rows, calc = _stored(row_files, calc_files, ['received_time_ns', 'action', 'side', 'price', 'size',
                                                 'order_number', 'exchange_event', 'ends_exchange_event',
                                                 'best_bid', 'best_ask', 'gap'])
    text = lambda name: np.array(rows.column(name).to_pylist(), dtype=object)
    in_day = (text('row_label') == TRADE_DAY) & (text('trade_day') == trade_day.isoformat())
    count = np.array(calc.column('sweep_facts_known').to_pylist(), dtype=object)
    need(all(v is None for v in count[~in_day]), 'sweep_facts_known is filled on a row of no trade day')
    d = np.flatnonzero(in_day)
    n = len(d)
    need(bool((np.diff(d) == 1).all()), 'the rows of the trade day are not one unbroken stretch')
    best_all = {name: text(name) for name in ('best_bid', 'best_ask')}
    for name in ('best_bid', 'best_ask', 'gap'):
        need(all(v is not None for v in text(name)[d]), f'{name} is empty on a row of the trade day')
    whole = lambda name: np.array(text(name)[d].tolist(), dtype=np.int64)
    position = rows.column('position_on_tape').to_numpy()[d]
    action, side = text('action')[d], text('side')[d]
    received, price, size, order, event = (whole(c) for c in ('received_time_ns', 'price', 'size', 'order_number',
                                                              'exchange_event'))
    ends = np.array(text('ends_exchange_event')[d].tolist(), dtype=bool)
    best = {name: whole(name) for name in ('best_bid', 'best_ask')}
    gap = whole('gap')
    is_trade, is_fill = action == S.TRADE, action == S.FILL
    names = S.FACT_NAMES

    def line(kind, i):
        row = dict.fromkeys(names)
        row.update(known_position=int(position[i]), known_received_time_ns=int(received[i]), fact=kind,
                   gap_now=int(gap[i]))
        return row
    expected = []                                      # (row, order on the tick, the line)
    starts = np.flatnonzero(np.concatenate(([True], event[1:] != event[:-1])))
    stops = np.concatenate((starts[1:], [n]))
    with_trade = np.flatnonzero(np.add.reduceat(is_trade.astype(np.int64), starts) > 0)
    no_fill = several_sides = most_levels = 0
    for g in with_trade.tolist():
        a, b = int(starts[g]), int(stops[g])
        need(bool(ends[b - 1]) and not ends[a:b - 1].any(),
             f'the exchange event at position {int(event[a])} holds a trade and does not end on its one end mark')
        t, f = a + np.flatnonzero(is_trade[a:b]), a + np.flatnonzero(is_fill[a:b])
        sides = ''.join(dict.fromkeys(side[t].tolist()))
        by = {code: int(size[t][side[t] == code].sum()) for code in (S.BUY, S.SELL)}
        traded = int(size[t].sum())
        row = line(S.EVENT, b - 1)
        row.update(event_position=int(event[a]), first_trade_position=int(position[t[0]]),
                   first_trade_received_time_ns=int(received[t[0]]),
                   since_first_trade_ns=int(received[b - 1] - received[t[0]]), ticks_in_event=b - a,
                   aggressor_sides=sides, trades=len(t), size_traded=traded, size_bought=by[S.BUY],
                   size_sold=by[S.SELL], size_no_side=traded - by[S.BUY] - by[S.SELL],
                   first_trade_price=int(price[t[0]]), last_trade_price=int(price[t[-1]]), fill_messages=len(f),
                   orders_filled=len(set(order[f].tolist())), size_of_fills=int(size[f].sum()),
                   price_levels_filled=len(set(price[f].tolist())),
                   first_fill_price=int(price[f[0]]) if len(f) else None,
                   last_fill_price=int(price[f[-1]]) if len(f) else None)
        for name in ('best_bid', 'best_ask'):
            just_before = best_all[name][d[a] - 1] if d[a] else None
            need(just_before is not None, f'no {name} on the row before the exchange event at {int(event[a])}')
            along = np.concatenate(([just_before], best[name][a:b])).astype(np.int64)
            row.update({f'{name}_moved': bool((along[1:] != along[:-1]).any()), f'{name}_before': int(just_before),
                        f'{name}_after': int(best[name][b - 1])})
        expected.append((b - 1, 0, tuple(row[name] for name in names)))
        no_fill += not len(f)
        several_sides += len(sides) > 1
        most_levels = max(most_levels, row['price_levels_filled'])

    # the quote touching or crossing: where the gap goes to zero or below, and where it comes back above
    at_or_through = gap <= 0
    was = np.concatenate(([False], at_or_through[:-1]))
    began, parted = np.flatnonzero(at_or_through & ~was), np.flatnonzero(~at_or_through & was)
    for i in began.tolist():
        expected.append((i, 1, tuple(line(S.TOUCHED, i)[name] for name in names)))
    for i, since in zip(parted.tolist(), began.tolist()):
        need(since < i, 'the quote parted before it touched')
        row = line(S.PARTED, i)
        row.update(touched_position=int(position[since]), lasted_ns=int(received[i] - received[since]),
                   ticks_lasted=i - since, lowest_gap=int(gap[since:i].min()))
        expected.append((i, 1, tuple(row[name] for name in names)))
    still = ([(int(position[began[-1]]), n - int(began[-1]), int(gap[began[-1]:].min()))]
             if n and at_or_through[-1] else [])
    expected = [row for _, _, row in sorted(expected, key=lambda e: e[:2])]
    _facts_equal(table_files['facts'], names, expected)
    per_row = collections.Counter(row[0] for row in expected)
    need(count[d].tolist() == [per_row.get(int(p), 0) for p in position],
         'the count of facts known on a row differs from the recount')
    left = pa.concat_tables([pq.read_table(f) for f in table_files['open-at-the-end']])
    need(sorted(zip(*[left.column(c).to_pylist() for c in S.OPEN_COLUMNS])) == still,
         'the touch still standing at the last tick differs from the recount')
    kinds = collections.Counter(row[names.index('fact')] for row in expected)
    return dict(passed=True, trade_day_rows=n, rows_of_no_trade_day_all_empty=int((~in_day).sum()),
                facts_compared=len(expected), facts_by_kind=dict(sorted(kinds.items())),
                most_facts_on_one_tick=max(per_row.values()) if per_row else 0,
                trade_events_with_no_fill_message=int(no_fill),
                trade_events_with_more_than_one_trade_side=int(several_sides),
                most_price_levels_filled_in_one_event=int(most_levels),
                ticks_with_the_quote_touching_or_crossed=int(at_or_through.sum()),
                touching_or_crossed_at_the_last_tick=len(still),
                touching_or_crossed_at_the_first_tick=bool(n and at_or_through[0]),
                first_tick_is_inside_an_event_that_began_before_the_trade_day=bool(n and event[0] != position[0]),
                trade_or_fill_rows_with_the_tapes_no_price_value=int(((is_trade | is_fill) &
                                                                      (price == UNDEFINED_PRICE)).sum()),
                method='the rows grouped by exchange event and each group taken as a whole; a best price moving '
                       'from the best-price columns; the touches from the stored gap. Shares no code with the '
                       'tick-by-tick calculation')


KNOWN_AT_A_TICK = {'facts'}            # the tables whose lines each carry the tick at which they became known
CALC_CHECKS = {'flow_peak': flow_peak, 'peak_story': peak_story, 'book_totals': book_totals,
               'quote_runs': quote_runs, 'peak_links': peak_links, 'open_stories': open_stories,
               'refills': refills, 'sweeps': sweeps}


def playback_cuts(name: str, full: list, tables: dict) -> dict:
    """Where, besides the middle tick, a calculation's playback is cut: a tick chosen to fall inside something
    still unfolding. Given as {why: the position of the last tick given}."""
    if name == 'flow_peak':
        from root.calcs import flow_peak as F
        at = F.NAMES.index('peak_high_position')
        highs = [values[at] for _, values in full if values[at] is not None]
        return {'the high of the middle peak': highs[len(highs) // HALVE]} if highs else {}
    if name == 'book_totals':
        from root.calcs import book_totals as B
        columns = [B.NAMES.index(f'{side}_filled') for side in B.SIDES.values()]
        shown = [k for k in range(1, len(full)) if any(full[k][1][c] != full[k - 1][1][c] for c in columns)]
        return ({'inside an exchange event, after a fill message and before the row where the book shows it':
                 full[shown[len(shown) // HALVE] - 1][0]} if shown else {})
    if name == 'open_stories':
        from root.calcs import open_stories as O
        step = len(O.FIGURES)
        open_now = [sum(values[k * step] for k in range(len(O.SIDES))) for _, values in full]
        return {'the tick with the most stories open': full[open_now.index(max(open_now))][0]} if full else {}
    facts = tables.get('facts', [])
    if name == 'refills':                              # the tick before the order's own row is still inside the
        if not facts:                                  # exchange event that filled it: its fill is waiting
            return {}
        positions = [position for position, _ in full]
        shown = positions.index(facts[len(facts) // HALVE][0])
        return ({'inside an exchange event, after a fill message and before the row where the book shows it':
                 positions[shown - 1]} if shown else {})
    if name == 'sweeps':
        from root.calcs import sweeps as S
        kind, known = S.FACT_NAMES.index('fact'), S.FACT_NAMES.index('known_position')
        first_trade, touched = S.FACT_NAMES.index('first_trade_position'), S.FACT_NAMES.index('touched_position')
        unfolding = [fact[first_trade] for fact in facts if fact[kind] == S.EVENT and fact[first_trade] != fact[known]]
        touching = [fact[touched] for fact in facts if fact[kind] == S.PARTED]
        cuts = {}
        if unfolding:
            cuts['inside an exchange event, on its first trade and before its end mark'] = unfolding[len(unfolding) // HALVE]
        if touching:
            cuts['while the quote is touching or crossed'] = touching[len(touching) // HALVE]
        return cuts
    if name == 'quote_runs':
        from root.calcs import quote_runs as Q
        at = Q.FACT_NAMES.index('fact')
        backs = [fact[0] for fact in facts if fact[at] == Q.STEP_BACK]
        return {'a tick that ends one run and starts the next': backs[len(backs) // HALVE]} if backs else {}
    return {'the tick the middle fact became known': facts[len(facts) // HALVE][0]} if facts else {}
