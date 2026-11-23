"""ROOT: the information measure, made from our ticks. The formula is the crypto operator's own, unchanged.

Greg, 2026-11-23: "do the codex calc if it's valuable"; then, on how it is to be made: "I mean tick values to get to
a second or whatever timeframe we need to get to." So the measure is made the way Codex's reanalysis made it, but
its inputs are built up from every trade at its own nanosecond, not taken from a ready-made one-second table.

WHAT CODEX'S PROGRAM DID (markets-data `codex/research-union-four-days-20261109`,
`reanalysis-20261109/analyze.py`, read for its code only; no result of it is carried): it wrote no formula. It
loaded the crypto information dipole operator (`odcore/info_dipole.py`, pinned as git blob
`c04751cbe5f92952e33328f6c04fcae6392e05e5`; the functions used here are the same lines in today's file) and called
`signed_flow_features(bought, sold)` on TWENTY ONE-SECOND PIECES: the size bought and the size sold in each. Out
come five figures, and Codex kept two more beside them:

- `imb_level`: bought minus sold over bought plus sold over the twenty pieces. This is the exhaustion line's figure.
- `ent_dipole`: the entropy of the bought pieces minus the entropy of the sold pieces, over their sum.
- `C_signed`: THE INFORMATION RATIO: the mean of the two entropies over the information the two lists share,
  signed by the side that leads. Where the two lists share nothing the bottom is the operator's smallest number
  and the ratio is huge: made by the division, not by the market. How often that is, is the thread's question.
- `mi_flow`: the shared information of the later ten pieces minus that of the earlier ten, signed the same way.
- `imb_flow`: the lean of the later ten pieces minus the lean of the earlier ten.
- `log_signed_C` (Codex's): the sign of the ratio times the logarithm of one plus its size.
- `mi_level` (Codex's): the information the twenty bought pieces and the twenty sold pieces share.

HOW IT IS MADE HERE. One line for every read of the stored 20-second exhaustion line (a trade with a side was
received, or trades left the 20 seconds at a moment with no tick), in the stored order, keyed by the read's own
number. At a read made at the moment M the pieces are counted BACK FROM M, never cut on the clock: a trade received
at R is inside the span while M minus R is less than 20 seconds, and it sits in the piece numbered by the whole
seconds of M minus R (the newest piece holds a trade received less than one second before M; a trade received
exactly one second before sits in the next). The operator is given the pieces oldest first, because its two halves
depend on the order. A read made at a trade holds every trade up to and including that one on the tape; a read of
trades leaving holds no trade received after that moment. A trade the tape gives no side for is in neither list.
Sizes are lots. Only this trade day's trades are read, through the rows gate.

LIMIT, said to Greg: between two reads a trade can pass from one piece into the next with nothing new traded. The
first figure cannot change then; the others can. The measure is read only where the stored line is read.

NOT DIPOLE, NOT EXHAUSTION: this is the information measure. It is in no sheet until decided with Greg.

    python3 -m root.info_measure 20231017 --rows <folder of the trade day's stored files> --out <folder>
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import math
import time
from pathlib import Path

import numpy as np

from odcore import info_dipole
from root import checks, store, tape
from root.calendar import NS_PER_SECOND, parse_trade_day

READS = ['received_time_ns', 'action', 'side', 'size']
TRADE, BUY, SELL = 'T', 'B', 'A'                       # the tape's codes, as the rows store them
PIECES = 20                                            # Codex's own: twenty pieces
PIECE_NS = NS_PER_SECOND                               # Codex's own: each piece is one second long
SPAN_NS = PIECES * PIECE_NS                            # together the 20 seconds of the exhaustion line
RECEIVED = 'a trade was received'                      # the stored line's own word for a read made at a trade
LINE_FILE = 'crypto-ng-tick-line-20s'                  # the stored exhaustion line: its reads are where this is read
LINE_READS = ['read', 'moment_received_ns', 'what', 'position_on_tape', 'bought', 'sold', 'flow', 'nothing_traded']
CLOSE = 1e-9                                           # a check only: how near the first figure must be to the line
ROUNDING = 1e-12                                       # Codex's own: shared information this small is rounding
PIECE_DIGITS = 2                                       # a piece's number in its column name, written 01 to 20
OPERATOR_FILE = Path(info_dipole.__file__)
CODEX_PINNED_OPERATOR = 'c04751cbe5f92952e33328f6c04fcae6392e05e5'   # the git blob Codex's program loaded
OPERATOR_BLOB = '6a62f4d7491c02bee3af840ad7f736453fff892a'           # the operator file this may run on: the one
# compared, in the session of 2026-11-23, with the copy Codex pinned (one phrase of a comment differs; the three
# formula functions and the smallest number are the same lines) and with its first version of 2026-06-22
FIGURES = [
    ('imb_level', 'The operator\'s first figure: bought minus sold over bought plus sold, over the twenty pieces. '
     'Checked equal to the stored exhaustion line at every read.'),
    ('ent_dipole', 'The entropy of the twenty bought pieces minus the entropy of the twenty sold pieces, over their '
     'sum. An entropy here is of the sizes sorted into classes, as the operator does it.'),
    ('C_signed', 'THE INFORMATION RATIO: the mean of the two entropies over the information the two lists share, '
     'signed by the side that leads. Huge where the two lists share nothing: made by the division.'),
    ('mi_flow', 'The shared information of the later ten pieces minus that of the earlier ten, signed by the side '
     'that leads.'),
    ('imb_flow', 'The lean (bought minus sold over bought plus sold) of the later ten pieces minus the lean of the '
     'earlier ten.'),
]
COLUMNS = [
    ('read', 'The number of the read of the stored exhaustion line this line belongs to.'),
    ('moment_received_ns', 'The moment of that read on the received clock, to the nanosecond.'),
    ('what', 'What changed the stored line at that read: a trade was received, or trades left the span.'),
    ('position_on_tape', 'The trade received: its position on the tape. Empty when the read is trades leaving.'),
    ('bought', 'Size bought inside the 20 seconds after this read, as stored (the bought pieces add up to it).'),
    ('sold', 'Size sold inside the 20 seconds after this read, as stored (the sold pieces add up to it).'),
] + FIGURES + [
    ('log_signed_C', 'Codex\'s form of the ratio: its sign times the logarithm of one plus its size.'),
    ('mi_level', 'The information the twenty bought pieces and the twenty sold pieces share (the bottom of the '
     'ratio before the operator\'s smallest number is added).'),
    ('pieces_with_buying', 'How many of the twenty pieces hold any buying.'),
    ('pieces_with_selling', 'How many of the twenty pieces hold any selling.'),
    ('pieces_with_a_trade', 'How many of the twenty pieces hold any trade with a side.'),
] + [(f'{side}_piece_{k + 1:0{PIECE_DIGITS}d}', f'Size {side} in piece {k + 1} of twenty (piece 1 is the oldest): the '
      f'trades received at least {PIECES - k - 1} and less than {PIECES - k} seconds before the read.')
     for side in ('bought', 'sold') for k in range(PIECES)]
NAMES = [name for name, _ in COLUMNS]
TEXT = {'what'}


def blob(raw: bytes) -> str:
    return hashlib.sha1(b'blob %d\0' % len(raw) + raw).hexdigest()


def the_trades(rows_folder: Path, trade_day) -> dict:
    """The trades the tape gives a side for, in tape order, through the rows gate."""
    position, received, buy, size = [], [], [], []
    for at, (moment, action, side, lots) in tape.rows_for_calculations(rows_folder, trade_day, READS):
        if action == TRADE and side in (BUY, SELL):
            position.append(at); received.append(moment); buy.append(side == BUY); size.append(lots)
    checks.need(position, 'no trade with a side on this trade day')
    return dict(position=np.array(position, np.int64), received=np.array(received, np.int64),
                buy=np.array(buy, bool), size=np.array(size, np.int64))


def the_line(rows_folder: Path, day: str) -> dict:
    import pyarrow.parquet as pq
    path = rows_folder / 'crypto-ng-tick' / f'{LINE_FILE}-{day}.parquet'
    checks.need(path.is_file(), f'{path.name} is not beside the rows')
    held = pq.read_table(path, columns=LINE_READS).to_pydict()
    checks.need(held['read'] == list(range(len(held['read']))), 'the stored reads are not numbered in order')
    return held


def run(trade_day, rows_folder: Path, out: Path) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    out.mkdir(parents=True, exist_ok=True)
    checks.need(blob(OPERATOR_FILE.read_bytes()) == OPERATOR_BLOB,
                'odcore/info_dipole.py is not the operator file that was compared with the copy Codex pinned')
    t, line = the_trades(rows_folder, trade_day), the_line(rows_folder, day)
    n, reads = len(t['position']), len(line['read'])
    table = {name: [] for name in NAMES}
    tally = collections.defaultdict(lambda: collections.defaultdict(int))
    lo = hi = 0                                        # the trades inside the span are those from lo up to hi
    for r in range(reads):
        moment, at_trade = line['moment_received_ns'][r], line['what'][r] == RECEIVED
        if at_trade:
            checks.need(hi < n and int(t['position'][hi]) == line['position_on_tape'][r]
                        and int(t['received'][hi]) == moment, f'read {r}: its trade is not the next trade on the tape')
            hi += 1
        else:
            checks.need(line['position_on_tape'][r] is None and (hi == n or int(t['received'][hi]) > moment),
                        f'read {r}: a read of trades leaving holds a trade that had not been read')
        while lo < hi and int(t['received'][lo]) + SPAN_NS <= moment:
            lo += 1
        age = moment - t['received'][lo:hi]
        checks.need(bool(np.all((age >= 0) & (age < SPAN_NS))), f'read {r}: a trade outside the 20 seconds')
        piece = PIECES - 1 - age // PIECE_NS           # oldest piece first, as the operator wants it
        is_buy, lots = t['buy'][lo:hi], t['size'][lo:hi]
        bought = np.bincount(piece[is_buy], weights=lots[is_buy], minlength=PIECES)
        sold = np.bincount(piece[~is_buy], weights=lots[~is_buy], minlength=PIECES)
        checks.need(int(bought.sum()) == line['bought'][r] and int(sold.sum()) == line['sold'][r],
                    f'read {r}: the pieces do not add up to the stored bought and sold')
        made = info_dipole.signed_flow_features(bought, sold)
        checks.need((made is None) == bool(line['nothing_traded'][r]),
                    f'read {r}: the operator and the stored line disagree on whether anything traded')
        row = dict(read=r, moment_received_ns=moment, what=line['what'][r], position_on_tape=line['position_on_tape'][r],
                   bought=line['bought'][r], sold=line['sold'][r],
                   pieces_with_buying=int((bought > 0).sum()), pieces_with_selling=int((sold > 0).sum()),
                   pieces_with_a_trade=int(((bought + sold) > 0).sum()))
        for side, values in (('bought', bought), ('sold', sold)):
            for k in range(PIECES):
                row[f'{side}_piece_{k + 1:0{PIECE_DIGITS}d}'] = int(values[k])
        tally['reads'][line['what'][r]] += 1
        if made is None:
            tally['figures']['none: nothing with a side traded in the 20 seconds'] += 1
        else:
            checks.need(abs(made['imb_level'] - line['flow'][r]) <= CLOSE,
                        f'read {r}: the first figure is not the stored exhaustion line')
            shared = float(info_dipole.mutual_info(bought, sold))
            ratio = float(made['C_signed'])
            row.update({name: float(made[name]) for name, _ in FIGURES}, mi_level=shared,
                       log_signed_C=math.copysign(math.log1p(abs(ratio)), ratio))
            one_sided = not line['bought'][r] or not line['sold'][r]
            tally['figures']['made'] += 1
            tally['pieces holding a trade, of twenty'][f'{row["pieces_with_a_trade"]:0{PIECE_DIGITS}d}'] += 1
            tally['the shared information'][
                ('exactly zero' if shared == 0 else 'not zero, and smaller than rounding' if shared < ROUNDING
                 else 'above zero')
                + ('; all the trading on one side' if one_sided else '; trading on both sides')] += 1
        for name in NAMES:
            table[name].append(row.get(name))
    checks.need(hi == n, 'a trade with a side is on the tape and in no read of the stored line')
    counts = dict(trade_day=trade_day.isoformat(), trades_with_a_side=n, reads_of_the_stored_exhaustion_line=reads,
                  **{name: dict(sorted(got.items())) for name, got in tally.items()})
    count_name = f'INFO-MEASURE-COUNT-{day}.json'
    (out / count_name).write_text(json.dumps(counts, indent=1) + '\n')
    name = f'info-measure-{day}.parquet'
    pq.write_table(pa.Table.from_arrays([pa.array(table[c], type=pa.string() if c in TEXT else None) for c in NAMES],
                                        names=NAMES), out / name, compression='zstd',
                   compression_level=store.ZSTD_LEVEL)
    files = []
    for file_name, rows in ((name, reads), (count_name, None)):
        raw = (out / file_name).read_bytes()
        files.append(dict(file=file_name, rows=rows, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    receipt = dict(
        what='The information measure, made from our ticks: the crypto information dipole operator called on twenty '
             'one-second pieces counted back from each read of the stored exhaustion line',
        asked='Greg, 2026-11-23: "do the codex calc if it\'s valuable"; "I mean tick values to get to a second or '
              'whatever timeframe we need to get to"',
        use='THE INFORMATION MEASURE. Not the dipole and not the exhaustion. In no sheet until decided with Greg.',
        trade_day=trade_day.isoformat(),
        the_operator=dict(file='odcore/info_dipole.py', git_blob_id=blob(OPERATOR_FILE.read_bytes()),
                          called='signed_flow_features(bought, sold) and mutual_info(bought, sold), unchanged',
                          codex_pinned_git_blob_id=CODEX_PINNED_OPERATOR,
                          compared='the job refuses any operator file but this one. Compared in the session of '
                                   '2026-11-23: against the copy Codex pinned, one phrase of a comment differs; the '
                                   'functions shannon, mutual_info and signed_flow_features and the smallest number '
                                   'are the same lines, and the same lines as the first version of 2026-06-22 '
                                   '(Markets 21ec02f). NOT compared: the original dipole scripts outside this '
                                   'repository.',
                          codex_program='markets-data codex/research-union-four-days-20261109, '
                                        'reanalysis-20261109/analyze.py (read for its code; no result carried)'),
        how_the_pieces_are_cut=dict(
            pieces=PIECES, seconds_each=PIECE_NS // NS_PER_SECOND,
            rule='at a read made at the moment M a trade received at R is inside while M minus R is less than 20 '
                 'seconds; it is in the piece numbered by the whole seconds of M minus R, counted back from the '
                 'read, and the operator is given the pieces oldest first. Nothing is cut on the clock.',
            which_trades='a read made at a trade holds every trade with a side up to and including that one on the '
                         'tape; a read of trades leaving holds no trade received after its moment. A trade the tape '
                         'gives no side for is in neither list. Sizes are lots.'),
        read_from=[f'rows-{day}-part*.parquet (through the rows gate)', f'crypto-ng-tick/{LINE_FILE}-{day}.parquet'],
        columns=[dict(column=c, what=w) for c, w in COLUMNS],
        counts=counts,
        checks=dict(passed=True,
                    what='every read made at a trade is the next trade with a side on the tape, at its own '
                         'nanosecond; no read of trades leaving holds a trade not yet read; every trade inside a '
                         'read is less than 20 seconds old; at every read the twenty bought pieces add up to the '
                         'stored bought and the twenty sold pieces to the stored sold; the operator gives nothing '
                         'exactly where the stored line says nothing traded; the first figure equals the stored '
                         'exhaustion line at every read; every trade with a side is in a read; the operator file is the one that was compared with the copy Codex pinned'),
        files=files, seconds=round(time.monotonic() - started, 1))
    (out / f'INFO-MEASURE-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='The information measure, made from our ticks')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--keep-cpus', action='store_true', help='accepted for the pod runner; this program uses one CPU')
    a = ap.parse_args()
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'counts', 'checks', 'seconds')}, indent=1))


if __name__ == '__main__':
    main()
