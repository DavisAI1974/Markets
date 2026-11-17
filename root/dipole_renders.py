"""ROOT: Native's dipoles pinned to their timestamps on OUR tape, and one render for each (Step 2, piece H, the
dipoles).

Greg, 2026-11-17: "You need to pin the dipoles to their timestamps and then see what there's to see. I know that
they do the dipole dive like before so do that for me. Pin the dipoles and then do the renders after you do."

THE PIN. One line per dipole of Native's stored record whose birth second lies inside the trade day, saying what
OUR tape holds at that second: the ticks of the birth second, the trades in it (how many, bought, sold, no side),
our own 20-second flow once the birth second is done and one second earlier, the seconds since the dipole before
and to the dipole after, and Native's own figures for the dipole beside them. Nothing of Native is worked out
again. The birth is in the past when Native makes it known; this table describes the past and is not a signal.

THE RENDERS. One picture per pinned dipole, none selected. Each runs from the birth of the dipole before to the
birth of the dipole after (the first from the first tick of the trade day, the last to the last tick), so no span
of time is chosen. Three panels on one clock, in seconds from the birth:
- the price: the best bid and best ask at every tick, and every trade print;
- the flow lean: our 20-second flow at every tick, and beside it the flow with no window (the size of the run of
  trades on one side, above zero for buying and below for selling);
- the size standing at the best bid and at the best ask.
Marked: the birth (0), the time Native made the dipole known, and the high of every 20-second peak in the stretch.
A render is a way of seeing. Nothing in it is averaged, ranked or fitted, and no dipole is named a kind of dipole.

Claude's calls in the build (his to correct): the birth second is read on the received clock, as Native's record
gives it; a dipole whose birth second is outside the trade day is listed in the receipt and not pinned.

    python3 -m root.dipole_renders 20231002 --rows <stored rows folder> --out <folder>
"""
from __future__ import annotations

import argparse
import bisect
import gzip
import hashlib
import json
import multiprocessing
import os
import time
from pathlib import Path

from root import checks, store, tape
from root import trade_legs as TL
from root.calcs import flow_peak, in_play
from root.calendar import NS_PER_SECOND, eastern_text, parse_trade_day, trade_day_bounds

READS = ['received_time_ns', 'action', 'side', 'size', 'price', 'best_bid', 'best_ask', 'best_bid_size',
         'best_ask_size']
TRADE = 'T'
SIDE = {'B': flow_peak.BUY_TEXT, 'A': flow_peak.SELL_TEXT}
PRICE_UNIT = 10 ** 9                                   # the tape's prices are in billionths of a dollar
PIN_COLUMNS = [
    ('dipole', 'Native\'s candidate number. A label only.'),
    ('native_polarity', 'Native\'s polarity: +1 net buying, -1 net selling.'),
    ('native_birth_ns', 'Native\'s birth time: the start of the birth second, on the received clock.'),
    ('native_known_second_ns', 'The start of the second in which Native made the dipole known.'),
    ('native_magnitude', 'Native\'s magnitude.'),
    ('native_threshold', 'The level Native required.'),
    ('native_baseline', 'Native\'s baseline.'),
    ('native_prominence', 'Native\'s prominence.'),
    ('first_position_in_birth_second', 'The first tick received in the birth second. A label only. Empty when no '
     'tick was received in it.'),
    ('last_position_in_birth_second', 'The last tick received in the birth second. A label only.'),
    ('ticks_in_birth_second', 'How many ticks were received in the birth second.'),
    ('trades_in_birth_second', 'How many trades printed in the birth second.'),
    ('bought_in_birth_second', 'Size bought by aggressors in the birth second.'),
    ('sold_in_birth_second', 'Size sold by aggressors in the birth second.'),
    ('no_side_in_birth_second', 'Size traded in the birth second that the tape gives no side for.'),
    ('our_flow_bought_20s_after', 'OUR 20-second flow as it stood on the last tick received before the end of the '
     'birth second: size bought.'),
    ('our_flow_sold_20s_after', 'The same: size sold.'),
    ('our_flow_fully_one_sided_after', 'Yes when that flow is all on one side. Empty when there is no flow.'),
    ('our_flow_on_native_side_after', 'Yes when that flow leans the way Native\'s polarity says.'),
    ('our_flow_bought_20s_before', 'OUR 20-second flow on the last tick received before the birth second: bought.'),
    ('our_flow_sold_20s_before', 'The same: size sold.'),
    ('seconds_since_dipole_before', 'From the birth of the dipole before to this birth. Empty on the first.'),
    ('seconds_to_dipole_after', 'From this birth to the birth of the dipole after. Empty on the last.'),
    ('render', 'The picture of this dipole.'),
]
PIN_NAMES = [name for name, _ in PIN_COLUMNS]


def native(rows_folder: Path, day: str) -> list:
    """Native's dipoles for the trade day, from the stored copy of its episode lines beside the rows."""
    lines = gzip.decompress((rows_folder / f'native-episodes-{day}.jsonl.gz').read_bytes()).decode().splitlines()
    by_id = {}
    for line in lines:
        row = json.loads(line)
        d = by_id.setdefault(row['candidate_id'], dict(id=row['candidate_id']))
        if 'birth_recv_ns' in row:
            d.update(birth=row['birth_recv_ns'], known=row['recognized_recv_ns'])
        candidate = row.get('candidate') or {}
        for key in ('polarity', 'magnitude', 'threshold', 'baseline', 'prominence'):
            if key in candidate:
                d[key] = candidate[key]
    return sorted((d for d in by_id.values() if 'birth' in d), key=lambda d: d['birth'])


def forward(rows_folder: Path, trade_day) -> dict:
    """The trade day's ticks as whole columns, with our own 20-second flow worked out forward by piece 1's code."""
    out = {name: [] for name in ['position', 'bought', 'sold'] + READS}
    flow = flow_peak.FlowPeak()
    for position, row in tape.rows_for_calculations(rows_folder, trade_day, READS):
        received, action, side, size = row[:4]
        values = flow.tick(position, received, (action or '').encode(), (side or '').encode(), size)
        out['position'].append(position)
        out['bought'].append(values[0])
        out['sold'].append(values[1])
        for name, value in zip(READS, row):
            out[name].append(value)
    return out


def pin(day: str, dipoles: list, t: dict, opens: int, halts: int) -> tuple:
    r = t['received_time_ns']
    inside = [d for d in dipoles if opens <= d['birth'] < halts]
    outside = [dict(dipole=d['id'], native_birth_ns=d['birth'], why='its birth second is outside the trade day')
               for d in dipoles if not opens <= d['birth'] < halts]
    lines = []
    for k, d in enumerate(inside):
        lo, hi = bisect.bisect_left(r, d['birth']), bisect.bisect_left(r, d['birth'] + NS_PER_SECOND)
        prints = [i for i in range(lo, hi) if t['action'][i] == TRADE]
        size_of = lambda code: sum(t['size'][i] for i in prints if (t['side'][i] if t['side'][i] in SIDE else 'N') == code)
        after = (t['bought'][hi - 1], t['sold'][hi - 1]) if hi else (None, None)
        before = (t['bought'][lo - 1], t['sold'][lo - 1]) if lo else (None, None)
        has = after[0] is not None and after[0] + after[1] > 0
        lines.append((
            d['id'], d.get('polarity'), d['birth'], d['known'], d.get('magnitude'), d.get('threshold'),
            d.get('baseline'), d.get('prominence'), t['position'][lo] if hi > lo else None,
            t['position'][hi - 1] if hi > lo else None, hi - lo, len(prints), size_of('B'), size_of('A'),
            size_of('N'), after[0], after[1],
            (after[0] == 0 or after[1] == 0) if has else None,
            ((after[0] > after[1]) == (d.get('polarity') == 1) and after[0] != after[1]) if has else None,
            before[0], before[1],
            None if k == 0 else (d['birth'] - inside[k - 1]['birth']) // NS_PER_SECOND,
            None if k + 1 == len(inside) else (inside[k + 1]['birth'] - d['birth']) // NS_PER_SECOND,
            f'dipole-render-{day}-{k:04d}.png'))
    return inside, lines, outside


def recount(t: dict, inside: list, lines: list):
    """The second method for the pin: the birth second's ticks and trades counted by walking the ticks once, in
    order, against the births in order; our flow there taken from the same walk."""
    f = {name: k for k, name in enumerate(PIN_NAMES)}
    r = t['received_time_ns']
    k, n = 0, len(r)
    for d, line in zip(inside, lines):
        while k < n and r[k] < d['birth']:
            k += 1
        ticks = trades = 0
        j = k
        while j < n and r[j] < d['birth'] + NS_PER_SECOND:
            ticks += 1
            trades += t['action'][j] == TRADE
            j += 1
        checks.need((ticks, trades) == (line[f['ticks_in_birth_second']], line[f['trades_in_birth_second']]),
                    f'{d["id"]}: the ticks and trades of its birth second differ from the recount')
        checks.need((t['bought'][j - 1], t['sold'][j - 1]) == (line[f['our_flow_bought_20s_after']],
                                                             line[f['our_flow_sold_20s_after']]) if j else True,
                    f'{d["id"]}: our flow after its birth second differs from the recount')


WORK = {}


def draw(job) -> tuple:
    """One picture. `job` is (file path, title, birth ns, known ns, first tick, one past the last tick)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    path, title, birth, known, lo, hi = job
    t = WORK['ticks']
    x = [(t['received_time_ns'][i] - birth) / NS_PER_SECOND for i in range(lo, hi)]
    figure, (top, middle, bottom) = plt.subplots(3, 1, figsize=(9, 8.5), sharex=True,
                                                 gridspec_kw=dict(height_ratios=(3, 2, 1.4)))
    top.step(x, [t['best_ask'][i] / PRICE_UNIT for i in range(lo, hi)], where='post', color='#b0413e', lw=0.9,
             label='best ask')
    top.step(x, [t['best_bid'][i] / PRICE_UNIT for i in range(lo, hi)], where='post', color='#2f6f4f', lw=0.9,
             label='best bid')
    for code, colour, name in (('B', '#2f6f4f', 'bought'), ('A', '#b0413e', 'sold')):
        at = [i for i in range(lo, hi) if t['action'][i] == TRADE and t['side'][i] == code]
        top.scatter([x[i - lo] for i in at], [t['price'][i] / PRICE_UNIT for i in at], s=9, color=colour, zorder=3,
                    label=f'trade, {name}')
    top.set_ylabel('price')
    top.legend(loc='upper left', fontsize=7, ncol=4)
    lean = [None if t['bought'][i] + t['sold'][i] == 0 else
            (t['bought'][i] - t['sold'][i]) / (t['bought'][i] + t['sold'][i]) for i in range(lo, hi)]
    middle.step(x, [float('nan') if v is None else v for v in lean], where='post', color='#d98a00', lw=1.0,
                label='20-second flow lean')
    middle.axhline(0, color='0.6', lw=0.6)
    middle.set_ylim(-1.08, 1.08)
    middle.set_ylabel('flow lean (20 seconds)')
    run, side, size = [], None, 0
    for i in range(lo, hi):
        if t['action'][i] == TRADE and t['side'][i] in SIDE:
            size = size + t['size'][i] if t['side'][i] == side else t['size'][i]
            side = t['side'][i]
        run.append(0 if side is None else size if side == 'B' else -size)
    other = middle.twinx()
    other.step(x, run, where='post', color='#4a4a8a', lw=0.8, alpha=0.8, label='run of trades on one side')
    other.set_ylabel('flow with no window (lots)')
    for high in WORK['highs'][bisect.bisect_left(WORK['highs'], t['received_time_ns'][lo]):
                              bisect.bisect_right(WORK['highs'], t['received_time_ns'][hi - 1])]:
        middle.axvline((high - birth) / NS_PER_SECOND, color='#d98a00', lw=0.4, alpha=0.5)
    bottom.step(x, [t['best_ask_size'][i] for i in range(lo, hi)], where='post', color='#b0413e', lw=0.8,
                label='size at the best ask')
    bottom.step(x, [t['best_bid_size'][i] for i in range(lo, hi)], where='post', color='#2f6f4f', lw=0.8,
                label='size at the best bid')
    bottom.set_ylabel('lots at the best price')
    bottom.set_xlabel('seconds from the dipole\'s birth')
    bottom.legend(loc='upper left', fontsize=7, ncol=2)
    for axis in (top, middle, bottom):
        axis.axvline(0, color='black', lw=0.9)
        axis.axvline((known - birth) / NS_PER_SECOND, color='black', lw=0.7, ls=':')
        axis.grid(alpha=0.25)
    figure.suptitle(title, fontsize=9)
    figure.tight_layout()
    figure.savefig(path, dpi=80)
    plt.close(figure)
    raw = Path(path).read_bytes()
    return Path(path).name, len(raw), hashlib.sha256(raw).hexdigest()


PANELS_ACROSS, PANELS_DOWN = 5, 8                      # one page of exhaustion peaks: 40 small panels
PER_PAGE = PANELS_ACROSS * PANELS_DOWN
TICK = 10 ** 6                                         # one price tick of this contract, in the tape's units


def draw_sheet(job) -> tuple:
    """One page of exhaustion peaks. `job` is (file path, title, the peaks of the page); a peak is (first tick,
    one past the last tick, the tick of its high, +1 for a buy peak or -1 for a sell peak, its label)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    path, title, peaks = job
    t = WORK['ticks']
    figure, axes = plt.subplots(PANELS_DOWN, PANELS_ACROSS, figsize=(12, 16))
    for axis, peak in zip(axes.flat, peaks + [None] * (PER_PAGE - len(peaks))):
        axis.tick_params(labelsize=5, length=2)
        if peak is None:
            axis.axis('off')
            continue
        lo, hi, high, sign, label = peak
        at = t['received_time_ns'][high]
        x = [(t['received_time_ns'][i] - at) / NS_PER_SECOND for i in range(lo, hi)]
        lean = [float('nan') if t['bought'][i] + t['sold'][i] == 0 else
                sign * (t['bought'][i] - t['sold'][i]) / (t['bought'][i] + t['sold'][i]) for i in range(lo, hi)]
        axis.step(x, lean, where='post', color='#d98a00', lw=0.8)
        axis.axhline(0, color='0.7', lw=0.4)
        axis.axvline(0, color='black', lw=0.5)
        axis.set_ylim(-1.08, 1.08)
        price = axis.twinx()
        start = WORK['last_print'][high]
        price.step(x, [float('nan') if WORK['last_print'][i] is None or start is None else
                       sign * (WORK['last_print'][i] - start) / TICK for i in range(lo, hi)],
                   where='post', color='black', lw=0.6)
        price.tick_params(labelsize=5, length=2)
        axis.set_title(label, fontsize=5.5, pad=2)
    figure.suptitle(title, fontsize=9)
    figure.tight_layout(rect=(0, 0, 1, 0.975))
    figure.savefig(path, dpi=80)
    plt.close(figure)
    raw = Path(path).read_bytes()
    return Path(path).name, len(raw), hashlib.sha256(raw).hexdigest()


def helper(cpus, ticks, highs, last_print):
    os.sched_setaffinity(0, {cpus.get()})              # each helper on its own CPU
    WORK.update(ticks=ticks, highs=highs, last_print=last_print)


def run(trade_day, rows_folder: Path, out: Path) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    opens, halts = trade_day_bounds(trade_day)
    t = forward(rows_folder, trade_day)
    inside, lines, outside = pin(day, native(rows_folder, day), t, opens, halts)
    recount(t, inside, lines)
    stored = checks._peaks_as_stored(rows_folder, trade_day, t['position'])
    highs = sorted(p['high_at'] for p in stored)
    last_print, seen = [], None
    for action, price in zip(t['action'], t['price']):
        seen = price if action == TRADE else seen
        last_print.append(seen)
    row_of = {position: k for k, position in enumerate(t['position'])}
    # the exhaustion peaks (piece 1's 20-second peaks), every one, in the order of their highs: each from the high
    # of the peak before it to the end of its own story, so no span of time is chosen
    panels, index, before = [], [], 0
    for n, peak in enumerate(sorted(stored, key=lambda p: row_of[p['high']])):
        high = row_of[peak['high']]
        end = len(t['position']) if peak['end'] is None else peak['end'] + 1
        buy = peak['side'] == flow_peak.BUY_TEXT
        lots = abs(t['bought'][high] - t['sold'][high])
        span = (t['received_time_ns'][end - 1] - t['received_time_ns'][before]) / NS_PER_SECOND
        page = f'exhaustion-sheet-{day}-{n // PER_PAGE:03d}.png'
        panels.append((before, end, high, 1 if buy else -1,
                       f'{eastern_text(peak["high_at"])[11:19]} {peak["side"]} {lots} lots, {span:.0f}s, '
                       f'{peak["how"] or "still open"}'))
        index.append((peak['high'], peak['side'], lots, peak['how'], page, n % PER_PAGE + 1))
        before = high
    sheet_jobs = [(str(out / f'exhaustion-sheet-{day}-{k // PER_PAGE:03d}.png'),
                   f'Exhaustion peaks (20-second flow), trade day {trade_day.isoformat()}, page '
                   f'{k // PER_PAGE + 1}: every peak in the order of their highs, none left out. Orange: the flow '
                   f'lean turned so the peak\'s side is up. Black: the last print, in ticks from the print at the '
                   f'high, turned the same way.\nEach panel runs from the high of the peak before to the end of this '
                   f'peak\'s story; the line at 0 is the high. Label: time of the high (Eastern), side, bought minus '
                   f'sold at the high, seconds shown, how the story ended.', panels[k:k + PER_PAGE])
                  for k in range(0, len(panels), PER_PAGE)]
    r, f = t['received_time_ns'], {name: k for k, name in enumerate(PIN_NAMES)}
    jobs = []
    for k, (d, line) in enumerate(zip(inside, lines)):
        lo = 0 if k == 0 else bisect.bisect_left(r, inside[k - 1]['birth'])
        hi = len(r) if k + 1 == len(inside) else bisect.bisect_left(r, inside[k + 1]['birth'] + NS_PER_SECOND)
        if hi - lo < 2:
            continue
        after = (line[f['our_flow_bought_20s_after']], line[f['our_flow_sold_20s_after']])
        title = (f'Native dipole {d["id"]}, trade day {trade_day.isoformat()}: born {eastern_text(d["birth"])} '
                 f'Eastern, polarity {d.get("polarity")}\n'
                 f'in its birth second: {line[f["trades_in_birth_second"]]} trades (bought '
                 f'{line[f["bought_in_birth_second"]]}, sold {line[f["sold_in_birth_second"]]}); our 20-second flow '
                 f'after it: bought {after[0]}, sold {after[1]}\n'
                 f'solid line: the birth. dotted line: Native made it known. thin orange lines: highs of '
                 f'20-second peaks. From the dipole before to the dipole after.')
        jobs.append((str(out / line[f['render']]), title, d['birth'], d['known'], lo, hi))
    # the pod pins this program to one CPU; the drawing is spread over every CPU the pod has, one helper pinned
    # to each (asking for all of them leaves exactly the ones the pod is allowed)
    os.sched_setaffinity(0, range(os.cpu_count()))
    cpus = multiprocessing.Manager().Queue()
    mine = sorted(os.sched_getaffinity(0))
    for cpu in mine:
        cpus.put(cpu)
    with multiprocessing.Pool(len(mine), initializer=helper, initargs=(cpus, t, highs, last_print)) as pool:
        drawn = pool.map(draw, jobs, chunksize=8)
        sheets = pool.map(draw_sheet, sheet_jobs, chunksize=2)
    pq.write_table(pa.Table.from_arrays(
        [pa.array(list(c), type=pa.string() if name in ('dipole', 'render') else None)
         for name, c in zip(PIN_NAMES, zip(*lines))], names=PIN_NAMES),
        out / f'dipoles-pinned-{day}.parquet', compression='zstd', compression_level=store.ZSTD_LEVEL)
    raw = (out / f'dipoles-pinned-{day}.parquet').read_bytes()
    files = [dict(file=f'dipoles-pinned-{day}.parquet', rows=len(lines), bytes=len(raw),
                  sha256=hashlib.sha256(raw).hexdigest())]
    files += [dict(file=name, bytes=size, sha256=sha) for name, size, sha in drawn + sheets]
    names = ['peak_high_position', 'peak_side', 'bought_minus_sold_at_high', 'story_ended_by', 'sheet', 'panel']
    pq.write_table(pa.Table.from_arrays([pa.array(list(c)) for c in zip(*index)], names=names),
                   out / f'exhaustion-sheets-index-{day}.parquet', compression='zstd')
    raw = (out / f'exhaustion-sheets-index-{day}.parquet').read_bytes()
    files.append(dict(file=f'exhaustion-sheets-index-{day}.parquet', rows=len(index), bytes=len(raw),
                      sha256=hashlib.sha256(raw).hexdigest()))
    count = lambda name, test: sum(1 for line in lines if test(line[f[name]]))
    receipt = dict(
        what='Native\'s dipoles pinned to their birth seconds on our tape, and one render for each',
        asked='Greg, 2026-11-17: "Pin the dipoles and then do the renders after you do"',
        trade_day=trade_day.isoformat(), columns=[dict(column=c, what=w) for c, w in PIN_COLUMNS],
        counts=dict(dipoles_pinned=len(lines), renders=len(drawn), dipoles_not_pinned=len(outside),
                    exhaustion_peaks_drawn=len(panels), exhaustion_sheets=len(sheets),
                    no_trade_in_the_birth_second=count('trades_in_birth_second', lambda v: v == 0),
                    our_flow_fully_one_sided_after_the_birth_second=count('our_flow_fully_one_sided_after',
                                                                          lambda v: v is True),
                    our_flow_not_fully_one_sided_after_the_birth_second=count('our_flow_fully_one_sided_after',
                                                                              lambda v: v is False),
                    native_threshold_exactly_1=count('native_threshold', lambda v: v == 1.0),
                    born_exactly_45_seconds_after_the_one_before=count('seconds_since_dipole_before',
                                                                       lambda v: v == 45)),
        dipoles_not_pinned=outside,
        render='one picture per pinned dipole, none selected, from the birth of the dipole before to the birth of '
               'the dipole after; price (best bid, best ask, every trade), our 20-second flow lean with the flow '
               'with no window beside it, the size at the best bid and best ask',
        exhaustion_sheets='every 20-second peak of the trade day as its own small panel, 40 to a page, in the order '
                          'of their highs: the flow lean and the last print, both turned so the peak\'s side is up, '
                          'from the high of the peak before to the end of the peak\'s own story. The index file '
                          'names the page and panel of every peak',
        checks=dict(passed=True, dipoles_compared=len(lines),
                    what='the ticks and trades of every birth second, and our flow after it, counted again by one '
                         'walk along the ticks in order'),
        files=files, seconds=round(time.monotonic() - started, 1))
    (out / f'DIPOLE-RENDERS-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='Native\'s dipoles pinned to our tape, and one render for each')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
