"""ROOT: one event, four graphs on one clock (Greg, 2026-11-18: "Go on the four graph picture").

For one stretch of one trade day, four SEPARATE graphs stacked on one time axis of real timestamps, no lines laid
over each other:
1. THE TRADE PRICE CURVE: the price of every trade, drawn smooth through them (drawing only; every trade is a dot).
2. THE DIPOLE at the tick: the run of trades under way against the run before it.
3. THE EXHAUSTION at the tick: each run of trades on one side as it builds trade by trade.
4. THE EXHAUSTION LINE: the 20-second flow, at every moment it changes.

WHERE THE PICTURE STARTS AND ENDS is said by the data (Greg, 2026-11-18: "We need the data to be telling us what
those times are"): it holds, whole, every hump of the 20-second line that the stretch asked for touches
(`root/crypto_ng_tick.py`, `whole_humps`). Nothing is worked out here: every value is read from an output already
stored for the trade day (`tick-renders/tick-dipole-*`, `crypto-ng-tick/crypto-ng-tick-line-20s-*` and
`crypto-ng-tick/crypto-ng-tick-tape-trades-*`). Nothing is averaged, typed or labelled.

    python3 -m root.four_graphs 20231017 --rows <folder of the trade day's stored files> --out <folder> \
        --stretch <from ns>-<to ns>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from root import checks
from root import tick_renders as TR
from root.calendar import parse_trade_day, trade_day_bounds
from root.crypto_ng_tick import clock, clock_text, whole_humps

FOUR_INCHES = (7.2, 14.5)                              # drawing only: four graphs, to be read on a phone
FOUR_GRAPHS = 4


def draw(path: Path, title: str, t: dict, line_at: np.ndarray, line: np.ndarray, mark=None) -> dict:
    """`mark`, when given, is called with the four graphs once they are drawn, to mark an event on them."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(FOUR_GRAPHS, 1, figsize=FOUR_INCHES, sharex=True, gridspec_kw={'hspace': TR.GAP})
    price, dipole, exhaustion, flow = axes
    at = [clock(int(v)) for v in t['received']]
    TR.smooth(price, t['received'], t['price'])
    price.set_title('1. THE TRADE PRICE CURVE, drawn smooth: through every trade, nothing averaged', loc='left',
                    fontsize=TR.BIG)
    dipole.step(at, t['dipole'], where='post', color='#1f618d', lw=1)
    dipole.axhline(0, color='#aab7b8', lw=TR.THIN)
    dipole.set_ylim(-TR.LEAN_LIMIT, TR.LEAN_LIMIT)
    dipole.set_ylabel('buying against selling\n(+1 all buying, -1 all selling)')
    dipole.set_title('2. THE DIPOLE, at the tick: the run of trades under way against the run before it', loc='left',
                     fontsize=TR.BIG)
    exhaustion.step(at, t['exhaustion'], where='post', color='#17202a', lw=1)
    highs = [k for k, high in enumerate(t['high']) if high]
    exhaustion.scatter([at[k] for k in highs], [t['exhaustion'][k] for k in highs], s=TR.HIGH_DOT, color='#ca6f1e',
                       zorder=TR.ON_TOP, label='the high of a run (its last trade)')
    exhaustion.axhline(0, color='#aab7b8', lw=TR.THIN)
    exhaustion.set_ylabel('lots in the run\n(buying up, selling down)')
    exhaustion.set_title('3. THE EXHAUSTION, at the tick: each run of trades on one side, built trade by trade',
                         loc='left', fontsize=TR.BIG)
    exhaustion.legend(fontsize=TR.TINY, loc='best')
    flow.step([clock(int(v)) for v in line_at], line, where='post', color='#1f618d', lw=1)
    flow.axhline(0, color='#aab7b8', lw=TR.THIN)
    flow.set_ylim(-TR.LEAN_LIMIT, TR.LEAN_LIMIT)
    flow.set_ylabel('bought minus sold over both\n(+1 all buying, -1 all selling)')
    flow.set_title('4. THE EXHAUSTION LINE: the 20-second flow, at every moment it changes', loc='left',
                   fontsize=TR.BIG)
    if mark is not None:
        mark(axes)
    for axis in axes:
        axis.grid(alpha=TR.FAINT)
        axis.tick_params(labelsize=TR.SMALL)
    flow.set_xlabel('Eastern time (the received clock)')
    figure.suptitle(title, fontsize=TR.BIG - 1, y=TR.TITLE_AT)
    figure.autofmt_xdate(rotation=TR.TILT)
    figure.savefig(path, dpi=TR.DPI, bbox_inches='tight')
    plt.close(figure)
    raw = path.read_bytes()
    return dict(file=path.name, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def run(trade_day, rows_folder: Path, out: Path, asked_first: int, asked_last: int) -> dict:
    import pyarrow.parquet as pq
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    opens, closes = trade_day_bounds(trade_day)
    checks.need(asked_first < asked_last, 'the stretch ends before it starts')
    stored = pq.read_table(rows_folder / 'crypto-ng-tick' / f'crypto-ng-tick-line-20s-{day}.parquet',
                           columns=['moment_received_ns', 'flow'])
    moments = stored.column('moment_received_ns').to_numpy()
    values = np.array([np.nan if v is None else v for v in stored.column('flow').to_pylist()], float)
    first, last = whole_humps(moments, values, asked_first, asked_last, opens, closes)   # the line sets the edges
    a = max(int(np.searchsorted(moments, first, 'right')) - 1, 0)
    b = int(np.searchsorted(moments, last, 'right'))
    checks.need(b > a, 'the stored line has no read inside this stretch')
    line_at = np.r_[np.maximum(moments[a:b], first), last]
    line = np.r_[values[a:b], values[b - 1]]

    trades = pq.read_table(rows_folder / 'crypto-ng-tick' / f'crypto-ng-tick-tape-trades-{day}.parquet',
                           columns=['position_on_tape', 'received_time_ns', 'price']).to_pydict()
    inside = [k for k, at in enumerate(trades['received_time_ns']) if first <= at <= last]
    checks.need(inside, 'no trade on the tape inside this stretch')
    position = np.array([trades['position_on_tape'][k] for k in inside], np.int64)
    ticks = pq.read_table(rows_folder / 'tick-renders' / f'tick-dipole-{day}.parquet',
                          columns=['position_on_tape', 'dipole_at_tick', 'exhaustion_at_tick', 'run_high']).to_pydict()
    where = np.searchsorted(np.array(ticks['position_on_tape'], np.int64), position)
    checks.need(all(ticks['position_on_tape'][k] == p for k, p in zip(where.tolist(), position.tolist())),
                'a trade of the stretch has no line in the stored dipole at the tick')
    empty = lambda v: float('nan') if v is None else v
    t = dict(received=[trades['received_time_ns'][k] for k in inside], price=[trades['price'][k] for k in inside],
             dipole=[empty(ticks['dipole_at_tick'][k]) for k in where.tolist()],
             exhaustion=[empty(ticks['exhaustion_at_tick'][k]) for k in where.tolist()],
             high=[bool(ticks['run_high'][k]) for k in where.tolist()])
    title = (f'Trade day {trade_day:%a %b %d, %Y}. One event, four graphs on one clock.\nAsked for: '
             f'{clock_text(asked_first)} to {clock_text(asked_last)} Eastern.\nDrawn: {clock_text(first)} to '
             f'{clock_text(last)}: every hump of the 20-second line it touches, whole.\n{len(inside)} trades. '
             f'Nothing averaged. Every trade at its own nanosecond.')
    stem = f'{day}-stretch-{asked_first}-{asked_last}'
    files = [draw(out / f'four-graphs-{stem}.png', title, t, line_at, line)]
    receipt = dict(what='One event, four separate graphs on one clock: the trade price curve, the dipole at the '
                        'tick, the exhaustion at the tick and the 20-second exhaustion line',
                   asked='Greg, 2026-11-18: "Go on the four graph picture"',
                   trade_day=trade_day.isoformat(),
                   asked_for=dict(first_received_ns=asked_first, last_received_ns=asked_last),
                   edges='set by the data: every hump of the 20-second line the asked stretch touches, whole',
                   drawn=dict(first_received_ns=int(first), last_received_ns=int(last), first_eastern=clock_text(first),
                              last_eastern=clock_text(last), trades=len(inside), reads_of_the_line=int(b - a)),
                   read_from=[f'tick-renders/tick-dipole-{day}.parquet',
                              f'crypto-ng-tick/crypto-ng-tick-line-20s-{day}.parquet',
                              f'crypto-ng-tick/crypto-ng-tick-tape-trades-{day}.parquet'],
                   nothing_applied='Nothing is worked out, averaged, typed or labelled: stored values, drawn.',
                   files=files)
    (out / f'FOUR-GRAPHS-{stem}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='One event, four graphs on one clock')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--stretch', required=True, help='<from ns>-<to ns> on the received clock')
    a = ap.parse_args()
    first, last = (int(v) for v in a.stretch.split('-'))
    print(json.dumps(run(parse_trade_day(a.trade_day), a.rows, a.out, first, last), indent=1))


if __name__ == '__main__':
    main()
