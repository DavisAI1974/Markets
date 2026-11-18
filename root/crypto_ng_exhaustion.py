"""ROOT: the natural gas exhaustion render, made the way the crypto one was made (the "crypto and ng" program).

Greg, 2026-11-18: "Whatever crypto did to generate those renders do that. If one of the calcs was a 20 sec. Use it
just like crypto did ... I want everything in our new exhaustion calc to be exactly like the old calc"; "The only
difference between the two should be that was crypto and we're doing ng"; "Bring back the program and just
designate it crypto and ng ... its crypto outputs ... for observation or verification purpose only".

WHAT IT DOES, step for step as the July script did (Markets `75b15fa`, `research/shape_s71/regroup2.py`):
1. THE GRID. The trade day's ticks are put on a grid of tenths of a second on the received clock, starting at the
   open of the trade day. Size bought and size sold by aggressors are summed in each tenth; the mid price and the
   sizes at the best prices take the last value in each tenth and are carried forward. (The Kraken collector made
   its records the same way, on its own receive clock.) A trade the tape gives no side for is in neither figure.
2. THE TRADES. The crypto trading program, untouched (`crypto_ng/program/`), is run on that grid with the natural
   gas row (`crypto_ng/ng.py`). Each trade it makes has an onset (the tenth of a second it was filled in), an end
   and a side.
3. THE 20-SECOND LINE. At every tenth of a second: bought minus sold over bought plus sold, over the last 200
   tenths, that one included. Where nothing traded in those 20 seconds the July line is 0; a mark beside it says
   "nothing traded", so the empty is kept too.
4. THE ARC of one trade: that line from 45 seconds before its onset to 60 seconds after, turned so that "with the
   trade" is up. A trade whose 105 seconds do not fit inside the trade day has no arc, as in July.

LEFT OUT ON GREG'S WORD (2026-11-18): the winner and loser labels; the average line of each kind; the short or
long split ("We will want to do our trades individually and see how they separate organically"; "see how the long
and short prints behave but not give them that label prior to run"). So nothing here is averaged, no kind is put
on a trade, and each trade's length is a number on its own line.

WHAT IS WRITTEN (all for observation and verification only; never a signal, never an input):
- `crypto-ng-grid-<trade day>.parquet`: one line per tenth of a second: what traded in it, the mid, the 20-second
  line with its "nothing traded" mark, and the turn finder's own 60-second lean.
- `crypto-ng-program-trades-<trade day>.parquet`: one line per trade of the program, with every column the
  program itself writes (named `program_...`), its onset, its end, its length, and where its arc is drawn.
- `crypto-ng-arcs-<trade day>.parquet`: every trade's own arc, 1,051 readings.
- NO PICTURE IN THE DATA RUN (Greg, 2026-11-18: "Run the entire trade day amount of trades but individually ...
  That is initial data output run. Once its done then we print exhaustion render for the one trade"). A picture
  is printed afterwards from the stored arcs, for the trade asked for: ONE PICTURE FOR ONE TRADE, ONE GRAPH IN IT
  ("Each trade should have its own exhaustion graph. No more than one graph per render"), named
  `crypto-ng-exhaustion-<trade day>-trade-NNNNN.png`.
- `CRYPTO-NG-EXHAUSTION-<trade day>.json`: the receipt: counts, the row used, the program's fingerprints, the
  checks, every file's fingerprint.

The ticks reach this only through `tape.rows_for_calculations()`: the four trade days, nothing from outside them.

    python3 -m root.crypto_ng_exhaustion 20231002 --rows <stored rows folder> --out <folder>
        the data run: every trade of the trade day, each worked out and stored on its own; no picture
    python3 -m root.crypto_ng_exhaustion 20231002 --rows <...> --out <folder of the data run> --moment <ns>
        prints the one graph of the program's trade that was under way at that moment on the received clock
        (when it held no trade then: the next trade to start), from the stored arcs; nothing is worked out again
    python3 -m root.crypto_ng_exhaustion 20231002 --rows <...> --out <folder of the data run> --trade <number>
        the same for a trade named by its number
"""
from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import json
import time
from pathlib import Path

import numpy as np

from crypto_ng import ng
from root import checks, store, tape
from root.calendar import NS_PER_SECOND, eastern_text, parse_trade_day, trade_day_bounds

READS = ['received_time_ns', 'action', 'side', 'size', 'best_bid', 'best_ask', 'best_bid_size', 'best_ask_size']
TRADE, BUY, SELL = 'T', 'B', 'A'                       # the tape's codes, as the rows store them
CELL_NS = NS_PER_SECOND // ng.CPS                      # one tenth of a second
SPAN_CELLS = ng.SMOOTH_SEC * ng.CPS                    # the 20-second line: 200 tenths
PRICE_UNIT = 10 ** 9                                   # the tape's prices are in billionths of a dollar
HALVE = 2                                              # a mid price is halfway between the best bid and best ask
PROGRAM = Path(ng.__file__).parent / 'program'
PROGRAM_FILES = ('flip_detector.py', 'swing_maker.py', 'info_dipole.py', 'platform.py')
SIDE_TEXT = {1: 'buy', -1: 'sell'}                     # the program's +1 (it bought) and -1 (it sold)
CLOCK = slice(11, 19)                                  # the hour, minute and second inside an Eastern time text
GRAPH_INCHES = (7.2, 4.5)                              # drawing only: one trade's own graph, to be read on a phone
DPI = 100
FLOW_LIMIT = 1.08                                      # the flow runs from -1 to 1; the graph shows a little more
BIG, SMALL, LINE, THIN, FAINT = 10, 8, 1.4, 0.8, 0.25  # drawing only: two letter sizes, two line widths, the grid
TRADE_DIGITS = 5                                       # a trade's number in its picture's name, written 00000

GRID_COLUMNS = [
    ('cell', 'The tenth of a second, counted from the open of the trade day (0 is the first).'),
    ('cell_end_received_ns', 'The end of that tenth of a second on the received clock: everything in it is known then.'),
    ('bought', 'Size bought by aggressors in this tenth of a second.'),
    ('sold', 'Size sold by aggressors in this tenth of a second.'),
    ('no_side', 'Size traded in it that the tape gives no side for. In neither figure above.'),
    ('trades', 'How many trades printed in it.'),
    ('mid', 'The mid price (dollars): the last one in this tenth of a second, carried forward when there is none.'),
    ('best_bid_size', 'The size at the best bid, taken the same way.'),
    ('best_ask_size', 'The size at the best ask, taken the same way.'),
    ('flow_20s_crypto', 'THE EXHAUSTION LINE, as crypto made it: bought minus sold over bought plus sold, over the '
     'last 200 tenths of a second, this one included. 0 where nothing with a side traded in them (the July rule).'),
    ('nothing_traded_20s', 'Yes where nothing with a side traded in those 20 seconds: the 0 beside it is the July '
     'rule and not a reading.'),
    ('lean_60s', 'The turn finder\'s own lean: the same figure over the last 600 tenths of a second (60 seconds).'),
]
TRADE_COLUMNS = [
    ('trade', 'The number of this trade of the crypto and ng program, in the order they were made. A label only.'),
    ('side', 'buy or sell: the side the program took.'),
    ('turn_cell', 'The tenth of a second in which the turn finder marked the turn this trade was made on.'),
    ('turn_received_ns', 'The end of that tenth of a second.'),
    ('lean_furthest_cell', 'The tenth of a second at which the 60-second lean stood furthest before it turned.'),
    ('onset_cell', 'THE ONSET: the tenth of a second in which the trade was filled (the first trade on the other '
     'side after the turn). 0 on the arc.'),
    ('onset_received_ns', 'The end of that tenth of a second.'),
    ('end_cell', 'The tenth of a second in which the trade ended.'),
    ('end_received_ns', 'The end of that tenth of a second.'),
    ('length_seconds', 'From the onset to the end, in seconds. A measured number; no short or long label is made.'),
    ('program_open_px', 'The program\'s own entry price: the mid with the half spread added or taken off.'),
    ('program_close_px', 'The program\'s own exit price.'),
    ('program_close_maker', 'The program\'s own mark: yes when it counted the exit as filled at its own quote.'),
    ('program_gross_bps', 'The program\'s own result in hundredths of a percent, before its fees. Observation only.'),
    ('program_net_bps', 'The same after the program\'s fee settings (the Kraken ones: 0 and 5). Observation only. '
     'No winner or loser is made from it and nothing is drawn or coloured by it.'),
    ('program_swing_bps', 'The program\'s own figure: how far the mid moved from the turn to the end.'),
    ('program_size', 'The program\'s size figure (1 throughout: the sizing step is not part of this path).'),
    ('program_lean_exit', 'The program\'s own mark (its lean exit is off on this path).'),
    ('program_stop_exit', 'The program\'s own mark (the natural gas row has no stop).'),
    ('program_dive_depth', 'Written by the program beside each trade: the size of the 60-second lean at its furthest.'),
    ('program_lean_flip', 'Written by the program: the lean at the turn, measured with the trade before.'),
    ('program_lean_close', 'Written by the program: the lean at the end, measured with this trade.'),
    ('program_dipole_class', 'Written by the program: its divergence read at the turn.'),
    ('program_rev_conv', 'Written by the program: the figure that read gives.'),
    ('arc_stored', 'Yes when the 45 seconds before and the 60 after fit inside the trade day, so the arc exists.'),
    ('arc_has_nothing_traded', 'Yes when some tenth of a second of the arc had nothing traded in its 20 seconds.'),
]
GRID_NAMES, TRADE_NAMES = [n for n, _ in GRID_COLUMNS], [n for n, _ in TRADE_COLUMNS]


def blob(raw: bytes) -> str:
    return hashlib.sha1(b'blob %d\0' % len(raw) + raw).hexdigest()


def read(rows_folder: Path, trade_day) -> dict:
    """The trade day's ticks as whole columns, through the stored-rows gate."""
    out = {name: [] for name in ['position'] + READS}
    for position, row in tape.rows_for_calculations(rows_folder, trade_day, READS):
        out['position'].append(position)
        for name, value in zip(READS, row):
            out[name].append(value)
    return out


def number(values) -> np.ndarray:
    return np.array([np.nan if v is None else v for v in values], float)


def grid(t: dict, opens: int) -> dict:
    """Step 1: the ticks on a grid of tenths of a second on the received clock."""
    received = np.array(t['received_time_ns'], np.int64)
    checks.need(len(received) and received[0] >= opens, 'a tick was received before the open of the trade day')
    checks.need(bool(np.all(np.diff(received) >= 0)), 'the received time goes backwards: no grid can be made on it')
    cell = (received - opens) // CELL_NS
    n = int(cell[-1]) + 1
    action, side = np.array(t['action'], object), np.array(t['side'], object)
    size = number(t['size'])
    trade = action == TRADE
    summed = lambda which: np.bincount(cell[which], weights=size[which], minlength=n)
    bid, ask = number(t['best_bid']), number(t['best_ask'])
    both = ~np.isnan(bid) & ~np.isnan(ask)             # the collector wrote a record only with both sides standing
    checks.need(bool(both.any()), 'no tick of the trade day has both a best bid and a best ask')
    last = lambda x: ng.last_in(n, cell[both], x[both])
    return dict(n=n, cell=cell, received=received, trade=trade, side=side, size=size,
                buy=summed(trade & (side == BUY)), sell=summed(trade & (side == SELL)),
                no_side=summed(trade & (side != BUY) & (side != SELL)),
                trades=np.bincount(cell[trade], minlength=n),
                mid=last((bid + ask) / HALVE / PRICE_UNIT), spread=last((ask - bid) / PRICE_UNIT),
                bid_size=last(number(t['best_bid_size'])), ask_size=last(number(t['best_ask_size'])))


def recount(g: dict, opens: int, imb: np.ndarray):
    """The second method for the 20-second line: every sided trade walked once in the order received, each kept
    for exactly 20 seconds from the start of its own tenth of a second; the line read at the end of every tenth."""
    sided = g['trade'] & ((g['side'] == BUY) | (g['side'] == SELL))
    trades = list(zip(g['received'][sided].tolist(), (g['side'][sided] == BUY).tolist(), g['size'][sided].tolist()))
    window, bought, sold, k = collections.deque(), 0.0, 0.0, 0
    for c in range(g['n']):
        end = opens + (c + 1) * CELL_NS
        while k < len(trades) and trades[k][0] < end:
            window.append(trades[k])
            bought, sold, k = bought + trades[k][2] * trades[k][1], sold + trades[k][2] * (not trades[k][1]), k + 1
        while window and window[0][0] < end - SPAN_CELLS * CELL_NS:
            _, was_buy, was = window.popleft()
            bought, sold = bought - was * was_buy, sold - was * (not was_buy)
        want = (bought - sold) / (bought + sold) if bought + sold > 0 else 0.0
        checks.need(want == imb[c], f'the 20-second line at tenth of a second {c} differs from the recount')
    checks.need(k == len(trades), 'a trade was received after the last tenth of a second')
    return dict(passed=True, tenths_of_a_second=g['n'], sided_trades=len(trades),
                what='the 20-second line at the end of every tenth of a second, from one walk along the sided trades')


def against_stored_flow(rows_folder: Path, day: str, t: dict, g: dict, opens: int) -> dict:
    """The new line against the stored `flow_20s` of piece 1, wherever the two must agree. The stored flow is read
    at a tick and holds the trades of the 20 seconds up to that tick; the grid's holds the trades of the 200
    tenths up to the end of the tick's tenth. They hold the same trades when the tick is the last of its tenth and
    no sided trade lies in the sliver between the two starts."""
    import pyarrow.parquet as pq
    files = sorted(Path(rows_folder).glob(f'calc-flow_peak-{day}-part*.parquet'))
    checks.need(files, 'the stored flow of piece 1 is not beside the rows')
    stored = {}
    for path in files:
        table = pq.read_table(path, columns=['position_on_tape', 'flow_bought_20s', 'flow_sold_20s'])
        for position, bought, sold in zip(*(table.column(c).to_pylist() for c in table.column_names)):
            stored[position] = (bought, sold)
    cum = lambda x: np.concatenate([[0.], np.cumsum(x)])
    cb, cs = cum(g['buy']), cum(g['sell'])
    sided = g['trade'] & ((g['side'] == BUY) | (g['side'] == SELL))
    at = g['received'][sided]
    last_of_cell = np.flatnonzero(np.append(np.diff(g['cell']) > 0, True))
    span = SPAN_CELLS * CELL_NS
    compared = sliver = 0
    for i in last_of_cell.tolist():
        c, r = int(g['cell'][i]), int(g['received'][i])
        end = opens + (c + 1) * CELL_NS
        if np.searchsorted(at, end - span, 'left') > np.searchsorted(at, r - span, 'right'):
            sliver += 1
            continue
        lo = max(c + 1 - SPAN_CELLS, 0)
        checks.need(stored[t['position'][i]] == (cb[c + 1] - cb[lo], cs[c + 1] - cs[lo]),
                    f'the tick at position {t["position"][i]}: the stored 20-second flow and the grid differ')
        compared += 1
    return dict(passed=True, ticks_compared=compared, ticks_with_a_trade_in_the_sliver_not_compared=sliver,
                what='bought and sold over the 20 seconds: the stored flow_peak values at the last tick of each '
                     'tenth of a second against the grid, wherever both hold the same trades')


def draw_trade(job) -> tuple:
    """One trade, one picture, one graph: `job` is (file path, title, the arc, seconds from the onset to the end)."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    path, title, arc, to_end = job
    x = (np.arange(ng.PRE + ng.POST + 1) - ng.PRE) / ng.CPS
    figure, axis = plt.subplots(figsize=GRAPH_INCHES)
    axis.plot(x, arc, color='#1f618d', lw=LINE, label='the 20-second flow, turned to the trade\'s side')
    axis.axvline(0, color='black', ls='--', lw=THIN, label='the onset (the trade was filled)')
    if to_end <= ng.POST_SEC:
        axis.axvline(to_end, color='#b03a2e', ls=':', lw=LINE, label='where this trade ended')
    axis.axhline(0, color='gray', lw=THIN)
    axis.set_ylim(-FLOW_LIMIT, FLOW_LIMIT)
    axis.set_xlabel('seconds relative to onset (t=0)')
    axis.set_ylabel('flow (up = with the trade)')
    axis.set_title(title, fontsize=BIG)
    axis.legend(fontsize=SMALL, loc='lower left')
    axis.grid(alpha=FAINT)
    figure.tight_layout()
    figure.savefig(path, dpi=DPI)
    plt.close(figure)
    raw = Path(path).read_bytes()
    return Path(path).name, len(raw), hashlib.sha256(raw).hexdigest()


def save(out: Path, name: str, columns: dict, types: dict) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    table = pa.Table.from_arrays([pa.array(v, type=types.get(k)) for k, v in columns.items()], names=list(columns))
    pq.write_table(table, out / name, compression='zstd', compression_level=store.ZSTD_LEVEL)
    raw = (out / name).read_bytes()
    return dict(file=name, rows=table.num_rows, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def run(trade_day, rows_folder: Path, out: Path) -> dict:
    import pyarrow as pa
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    opens, _ = trade_day_bounds(trade_day)
    t = read(rows_folder, trade_day)
    g = grid(t, opens)
    n = g['n']
    hs = ng.half_spread_bps(g['mid'], g['spread'])
    res, desc, flips, imb, lean = ng.run(g['mid'], g['buy'], g['sell'], g['bid_size'], g['ask_size'], hs)
    check_line = recount(g, opens, imb)
    check_stored = against_stored_flow(rows_folder, day, t, g, opens)
    quiet = ng.rolling_imb(g['buy'] + g['sell'], np.zeros(n), ng.SMOOTH_SEC) == 0   # nothing traded in the 20 s
    end_of = lambda cell: int(opens + (int(cell) + 1) * CELL_NS)
    files = [save(out, f'crypto-ng-grid-{day}.parquet', dict(zip(GRID_NAMES, [
        np.arange(n), opens + (np.arange(n, dtype=np.int64) + 1) * CELL_NS, g['buy'].astype(np.int64),
        g['sell'].astype(np.int64), g['no_side'].astype(np.int64), g['trades'].astype(np.int64), g['mid'],
        g['bid_size'], g['ask_size'], imb, quiet, lean])), {})]

    pivot = {int(c): int(p) for c, p, _ in flips}
    arcs, lines, kept = [], [], []
    left_out = collections.Counter()
    for k, (leg, d) in enumerate(zip(res.legs, desc)):
        o, c = int(leg.open_idx), int(leg.close_idx)
        arc = ng.arc(imb, leg, n)
        if arc is None:
            left_out['its end is not after its onset' if c <= o else
                     'the 45 seconds before its onset reach before the open of the trade day' if o - ng.PRE < 0 else
                     'the 60 seconds after its onset reach past the last tenth of a second'] += 1
        else:
            kept.append(k)
            arcs.append(arc)
        lines.append((
            k, SIDE_TEXT[int(leg.side)], int(leg.flip_idx), end_of(leg.flip_idx), pivot.get(int(leg.flip_idx)), o,
            end_of(o), c, end_of(c), (c - o) / ng.CPS, float(leg.open_px), float(leg.close_px),
            bool(leg.close_maker), float(leg.gross_bps), float(leg.net_bps), float(leg.swing_bps), float(leg.size),
            bool(leg.lean_exit), bool(leg.stop_exit), d['dive_depth'], d['lean_flip'], d['lean_close'],
            d['dipole_class'], d['rev_conv'], arc is not None,
            None if arc is None else bool(quiet[o - ng.PRE:o + ng.POST + 1].any())))
    text = {'side', 'program_dipole_class'}
    files.append(save(out, f'crypto-ng-program-trades-{day}.parquet',
                      dict(zip(TRADE_NAMES, map(list, zip(*lines)) if lines else [[] for _ in TRADE_NAMES])),
                      {name: pa.string() for name in text}))
    f = {name: k for k, name in enumerate(TRADE_NAMES)}
    files.append(save(out, f'crypto-ng-arcs-{day}.parquet', dict(
        trade=kept, onset_cell=[lines[k][f['onset_cell']] for k in kept],
        seconds_from_onset_of_first_reading=[-float(ng.PRE_SEC)] * len(kept),
        arc_with_trade_flow=[a.tolist() for a in arcs],
        arc_nothing_traded=[quiet[lines[k][f['onset_cell']] - ng.PRE:lines[k][f['onset_cell']] + ng.POST + 1].tolist()
                            for k in kept]), {}))

    sided = g['trade'] & ((g['side'] == BUY) | (g['side'] == SELL))
    receipt = dict(
        what='The natural gas exhaustion render made the way the crypto one was made: the crypto and ng program',
        asked='Greg, 2026-11-18: "I want everything in our new exhaustion calc to be exactly like the old calc"; '
              '"Bring back the program and just designate it crypto and ng"',
        use='OBSERVATION AND VERIFICATION ONLY. Never a signal, never an input to another calculation.',
        left_out_on_his_word=['the winner and loser labels', 'the average line of each kind',
                              'the short or long split (each trade\'s length is a stored number, no label)'],
        pictures='None in this run (Greg, 2026-11-18: "That is initial data output run"). A trade\'s graph is printed '
                 'afterwards from the stored arcs: one picture for one trade, one graph in it ("Each trade should '
                 'have its own exhaustion graph. No more than one graph per render"), named '
                 'crypto-ng-exhaustion-<trade day>-trade-NNNNN.png.',
        trade_day=trade_day.isoformat(),
        program=dict(source='DavisAI1974/Markets 75b15fa10193fab218b6469e5e5f0f49359880e1 (2026-07-07)',
                     git_blob_ids={name: blob((PROGRAM / name).read_bytes()) for name in PROGRAM_FILES},
                     natural_gas_row=dataclasses.asdict(ng.NG), half_spread_bps=hs,
                     turn_finder_lean_tenths_of_a_second=ng.WFLIP, line_tenths_of_a_second=SPAN_CELLS,
                     arc_seconds_before_and_after=[ng.PRE_SEC, ng.POST_SEC]),
        grid_columns=[dict(column=c, what=w) for c, w in GRID_COLUMNS],
        trade_columns=[dict(column=c, what=w) for c, w in TRADE_COLUMNS],
        counts=dict(
            ticks=len(t['position']), tenths_of_a_second=n,
            tenths_of_a_second_with_a_trade=int((g['trades'] > 0).sum()),
            tenths_of_a_second_with_nothing_traded_in_their_20_seconds=int(quiet.sum()),
            trades_on_the_tape=int(g['trade'].sum()), trades_the_tape_gives_no_side_for=int((g['trade'] & ~sided).sum()),
            size_the_tape_gives_no_side_for=int(g['no_side'].sum()),
            turns_found=len(flips),
            turns_marked_in_a_tenth_of_a_second_with_no_trade=sum(1 for c, _, _ in flips
                                                                  if g['buy'][int(c)] + g['sell'][int(c)] == 0),
            turns_filled=int(round(res.fill_rate * max(1, len(flips)))) if res.legs else 0,
            program_trades=len(res.legs), program_trades_with_an_arc=len(kept),
            program_trades_with_no_arc=dict(left_out),
            arcs_holding_a_stretch_where_nothing_traded=sum(1 for line in lines if line[f['arc_has_nothing_traded']]),
            program_exits_it_did_not_count_as_filled_at_its_quote=int(res.n_taker_closes) if res.legs else 0,
            pictures_in_this_run=0),
        built_in='Every onset holds a trade against the trade\'s own side (the program is filled by the next trade '
                 'on the other side), so every arc steps down at 0 and back up 20 seconds later. A turn is marked '
                 'only after recent trading has moved the trade\'s way, so the rise into 0 is partly made by how '
                 'the trades are chosen. On thin tape a turn can be marked when old trades drop out of the 60 '
                 'seconds with nothing new traded: counted above, nothing filtered.',
        checks=dict(the_line_recounted=check_line, against_the_stored_flow=check_stored),
        files=files, seconds=round(time.monotonic() - started, 1))
    (out / f'CRYPTO-NG-EXHAUSTION-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def print_one(trade_day, out: Path, moment=None, trade=None) -> dict:
    """One trade's own exhaustion graph, printed from what the data run stored in `out`. The trade is named by its
    number, or by a moment on the received clock: the trade under way then (onset at or before it, end after it);
    when the program held no trade at that moment, the next trade to start. A trade with no stored arc cannot be
    printed and the run says so."""
    import pyarrow.parquet as pq
    day = f'{trade_day:%Y%m%d}'
    trades = pq.read_table(out / f'crypto-ng-program-trades-{day}.parquet').to_pylist()
    checks.need(trades, 'the data run stored no trade of the program for this trade day')
    if trade is None:
        under_way = [t for t in trades if t['onset_received_ns'] <= moment < t['end_received_ns']]
        later = [t for t in trades if t['onset_received_ns'] > moment]
        checks.need(under_way or later, 'no trade of the program was under way at that moment and none started after')
        chosen, why = ((under_way[0], 'the trade under way at that moment') if under_way else
                       (later[0], 'the program held no trade at that moment: the next trade to start'))
    else:
        named = [t for t in trades if t['trade'] == trade]
        checks.need(named, f'the program made no trade numbered {trade} on this trade day')
        chosen, why = named[0], 'named by its number'
    checks.need(chosen['arc_stored'], f'trade {chosen["trade"]} has no stored arc: its 105 seconds do not fit')
    arcs = pq.read_table(out / f'crypto-ng-arcs-{day}.parquet', filters=[('trade', '=', chosen['trade'])]).to_pylist()
    checks.need(len(arcs) == 1, f'trade {chosen["trade"]}: its stored arc was not found')
    name = f'crypto-ng-exhaustion-{day}-trade-{chosen["trade"]:0{TRADE_DIGITS}d}.png'
    title = (f'Crypto and ng program, natural gas, trade day {trade_day:%a %b %d, %Y}. Trade {chosen["trade"]}: the '
             f'program\'s {chosen["side"]},\nonset {eastern_text(chosen["onset_received_ns"])[CLOCK]} Eastern, lasted '
             f'{chosen["length_seconds"]:,.1f} s. Its own exhaustion arc; nothing averaged.')
    _, size, sha = draw_trade((str(out / name), title, np.array(arcs[0]['arc_with_trade_flow']),
                               chosen['length_seconds']))
    receipt = dict(what='One trade\'s own exhaustion graph, printed from the stored arcs of the data run',
                   asked='Greg, 2026-11-18: "Each trade should have its own exhaustion graph. No more than one graph '
                         'per render"',
                   trade_day=trade_day.isoformat(), asked_for=dict(moment_received_ns=moment, trade=trade),
                   chosen=why, trade={k: chosen[k] for k in ('trade', 'side', 'onset_received_ns', 'end_received_ns',
                                                            'length_seconds')},
                   onset_eastern=eastern_text(chosen['onset_received_ns']),
                   end_eastern=eastern_text(chosen['end_received_ns']),
                   files=[dict(file=name, bytes=size, sha256=sha)])
    (out / f'CRYPTO-NG-RENDER-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='The natural gas exhaustion render, the crypto and ng program')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--moment', type=int, help='print the graph of the trade under way at this received time (ns)')
    ap.add_argument('--trade', type=int, help='print the graph of the trade with this number')
    a = ap.parse_args()
    if a.moment is not None or a.trade is not None:
        print(json.dumps(print_one(parse_trade_day(a.trade_day), a.out, a.moment, a.trade), indent=1))
        return
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'checks', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
