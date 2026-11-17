"""ROOT: the missing two hours of the trade legs (6 pm to 8 pm Eastern) on trade days Oct 2 and Oct 17.

Greg, 2026-11-17: "So build the missing hrs exactly how we built the current data for the other hours", and of the
old program, which stops at 8 pm on those two trade days: "Then change it. It's something we made and we can change
it. It's not a gate we can't get around. Finish the data".

How the old legs were made (markets-data run 42571551209, Markets `43e4d2bd` `event_chronology.py`): the two rule
functions `price_stretches` and `print_legs` of Markets `0408df44` `continue_trade_chronology.py` ("maximal
same-sign distinct-print steps; turning stretches belong to both"), run over the trade day's trade prints in tape
order. Its trade list came from the stored grouped stream, which on Oct 2 and Oct 17 starts at 00:00 UTC (8 pm
Eastern) because the earlier UTC file was not fed in, and `event_common.py` set that 8 pm start by hand.

What is changed, and only this: the trade list starts at 6 pm, read from the stored rows through the rows gate (the
same tape). The two rule functions are the old ones, loaded byte for byte from that commit (fingerprint checked)
and run unchanged.

The check, before anything is written: on the hours the old record covers, the new trade list must be the old one,
trade for trade (exchange time, received time, price, size, order, side, and the time the trade's exchange event was
complete, which the old record calls `available_ns`), and every old leg after the first must come out again with
the same trades, direction and price change. The old first leg is cut at 8 pm, so it may differ.

What is kept (valid data is never discarded; old and new side by side):
- the old legs and trades stay as they are;
- written here: the trades before 8 pm, the price stretches and the legs that hold any trade before 8 pm (the leg
  that crosses 8 pm is the whole leg, and names the old leg 0 that holds its part from 8 pm).
Numbering: stretches and legs are counted from 6 pm here; the old record counts from 8 pm. Positions are ROOT's
places on the tape for the week, not the old adapter's cursors; the old group numbers have no counterpart and are
not written.

    python3 -m root.trade_legs 20231002 --rows <stored rows folder> --out <folder>
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import time
import urllib.request
from pathlib import Path

from root import checks, store, tape
from root.calendar import parse_trade_day

RULE_COMMIT = '0408df44c4f106f7fda4ac4b92ae622d7d34cd7b'
RULE_FILE = 'tasks/family-research-20261022/continue_trade_chronology.py'
RULE_SHA256 = 'db51ff08447b2ed1c4bca3f0c559fef9a7b0394a0a164434224afcb87faedda1'
OLD_COMMIT = '15fbf2acd11365cb00893a919ec83e00b4df209f'          # markets-data main, where the old legs are kept
OLD_FOLDER = ('tasks/family-research-20261022/claude-independent-research-20261113/source-artifacts/'
              'tasks/family-research-20261022/combined-events/run-42571551209-1/events-{day}')
OLD_SHA256 = {'20231002': dict(legs='af766f0bf330ef9d8d23e7453ddae5260c87adf18ac244de50b99fdfc03f0896',
                               trades='a10f5928b0df415260bd93a1bf4475abf1aa6be1c49776553c1a5be80805f243'),
              '20231017': dict(legs='4710ae6660e82c2a29fb60d12e725f901bbdffdc0bbabfc4dd31b3196f89e3f1',
                               trades='e9be9e78167e719a8b2070a041da297fe8f1aec5e98a9baa74a06341e0601854'),
              # the two trade days whose earlier record starts at 6 pm (read by the check of `leg_peaks`)
              '20231003': dict(legs='fcf15d94b62d94a03c120f11ff8b3015846adcb0c1af725e2cc644bf782a91fb',
                               trades='02c01d9bd080c89a34e0915a53221ebf6e92dbc8bad27211abe8cb6fec37dc5b'),
              '20231018': dict(legs='e2dbb0cb31ba8c64e52329f019deac366990702bd012a6dd33ac79fdcdaa5065',
                               trades='eb274a3e9d81c1589a1038a96b6097f9f6dac2ef34f1ef9407d522d532696977')}
RAW = 'https://raw.githubusercontent.com/DavisAI1974/{repo}/{commit}/{path}'
AGENT = 'curl/8'
READS = ['action', 'side', 'price', 'size', 'order_number', 'exchange_time_ns', 'received_time_ns',
         'ends_exchange_event']
TRADE = 'T'
OLD_START_NS = {'20231002': 1696204800 * 10 ** 9, '20231017': 1697500800 * 10 ** 9}   # 00:00 UTC, 8 pm Eastern
ENDPOINT = 'observed same-sign print-step leg; not natural event death'      # the old record's own words


def fetch(repo: str, commit: str, path: str, sha256: str) -> bytes:
    ask = urllib.request.Request(RAW.format(repo=repo, commit=commit, path=path), headers={'User-Agent': AGENT})
    with urllib.request.urlopen(ask, timeout=180) as answer:
        raw = answer.read()
    checks.need(hashlib.sha256(raw).hexdigest() == sha256, f'{path}: not the file pinned')
    return raw


def old_rule() -> dict:
    """The two rule functions, taken out of the old file and run as they are."""
    source = fetch('Markets', RULE_COMMIT, RULE_FILE, RULE_SHA256).decode()
    tree = ast.parse(source)
    keep = [node for node in tree.body if isinstance(node, ast.FunctionDef)
            and node.name in ('price_stretches', 'print_legs')]
    checks.need(len(keep) == 2, 'the two rule functions are not in the pinned file')
    space = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), RULE_FILE, 'exec'), space)
    return space


def trades_of(rows_folder: Path, trade_day) -> list:
    """Every trade print of the trade day in tape order, with the time its exchange event was complete (the
    received time of the first tick at or after it that carries the exchange's end-of-event flag)."""
    out, waiting = [], []
    for position, (action, side, price, size, order, exchange, received, ends) in \
            tape.rows_for_calculations(rows_folder, trade_day, READS):
        if action == TRADE:
            trade = dict(position=position, event_ns=exchange, receive_ns=received, price_raw=price, size=size,
                         order_id=order, aggressor_side=side, available_ns=None, event_end_position=None)
            out.append(trade)
            waiting.append(trade)
        if ends:
            for trade in waiting:
                trade.update(available_ns=received, event_end_position=position)
            waiting = []
    checks.need(not waiting, 'a trade at the end of the trade day has no end of its exchange event')
    return out


def run(trade_day, rows_folder: Path, out: Path) -> dict:
    import pyarrow as pa
    import pyarrow.parquet as pq
    started = time.monotonic()
    day = f'{trade_day:%Y%m%d}'
    checks.need(day in OLD_START_NS, 'only trade days Oct 2 and Oct 17 miss their first two hours')
    out.mkdir(parents=True, exist_ok=True)
    rule = old_rule()
    trades = trades_of(rows_folder, trade_day)
    prices = [t['price_raw'] for t in trades]
    stretches, member = rule['price_stretches'](prices)
    legs, leg_member = rule['print_legs'](stretches)

    old = {name: pq.read_table(io.BytesIO(fetch('markets-data', OLD_COMMIT,
                                                OLD_FOLDER.format(day=day) + f'/a-{what}.parquet',
                                                OLD_SHA256[day][name]))).to_pylist()
           for name, what in (('trades', 'trades'), ('legs', 'print-legs'))}
    before = sum(1 for t in trades if t['receive_ns'] < OLD_START_NS[day])
    checks.need(len(trades) - before == len(old['trades']),
                f'{len(trades) - before} trades from 8 pm; the old record holds {len(old["trades"])}')
    same = ('event_ns', 'receive_ns', 'price_raw', 'size', 'order_id', 'aggressor_side', 'available_ns')
    for k, was in enumerate(old['trades']):
        now = trades[before + k]
        checks.need(all(now[f] == was[f] for f in same), f'old trade {k} differs from the tape\'s trade')
    new_leg = {(leg['first_trade'], leg['last_trade'], leg['step_sign']): leg for leg in
               ({**leg, 'first_trade': stretches[leg['first_stretch_ordinal']]['first_trade_ordinal'],
                 'last_trade': stretches[leg['last_stretch_ordinal']]['last_trade_ordinal']} for leg in legs)}
    matched = 0
    for was in old['legs'][1:]:
        key = (was['first_trade'] + before, was['last_trade'] + before, was['step_sign'])
        checks.need(key in new_leg, f'old leg {was["leg_ordinal"]} does not come out again')
        checks.need(prices[key[1]] - prices[key[0]] == was['raw_price_change'],
                    f'old leg {was["leg_ordinal"]}: the price change differs')
        matched += 1

    def clocks(i, prefix):
        t = trades[i]
        return {f'{prefix}_position': t['position'], f'{prefix}_event_end_position': t['event_end_position'],
                f'{prefix}_event_ns': t['event_ns'], f'{prefix}_receive_ns': t['receive_ns'],
                f'{prefix}_available_ns': t['available_ns']}
    seam_old = old['legs'][0]
    leg_rows = []
    for leg in legs:
        lo = stretches[leg['first_stretch_ordinal']]['first_trade_ordinal']
        hi = stretches[leg['last_stretch_ordinal']]['last_trade_ordinal']
        if lo >= before:
            continue
        crosses = hi >= before
        holds_old = crosses and seam_old['first_trade'] + before <= hi and seam_old['step_sign'] == leg['step_sign']
        leg_rows.append(dict(
            leg_ordinal_from_6pm=leg['leg_ordinal'], first_stretch_ordinal=leg['first_stretch_ordinal'],
            last_stretch_ordinal=leg['last_stretch_ordinal'], step_sign=leg['step_sign'], trade_day=day,
            first_trade_from_6pm=lo, last_trade_from_6pm=hi, **clocks(lo, 'first'), **clocks(hi, 'last'),
            duration_receive_ns=trades[hi]['receive_ns'] - trades[lo]['receive_ns'],
            duration_event_ns=trades[hi]['event_ns'] - trades[lo]['event_ns'],
            raw_price_change=prices[hi] - prices[lo], left_boundary=lo == 0, right_boundary=hi == len(trades) - 1,
            crosses_8pm=crosses, old_leg_holding_its_part_from_8pm=seam_old['leg_ordinal'] if holds_old else None,
            endpoint=ENDPOINT))
    stretch_rows = [dict(stretch_ordinal_from_6pm=s['stretch_ordinal'], price_raw=s['price_raw'],
                         first_trade_from_6pm=s['first_trade_ordinal'], last_trade_from_6pm=s['last_trade_ordinal'],
                         incoming_step_raw=s['incoming_step_raw'], outgoing_step_raw=s['outgoing_step_raw'],
                         print_direction_turn=s['print_direction_turn'], crosses_8pm=s['last_trade_ordinal'] >= before,
                         overlapping_leg_ordinals_from_6pm=leg_member[s['stretch_ordinal']])
                    for s in stretches if s['first_trade_ordinal'] < before]
    trade_rows = [dict(trade_from_6pm=i, **{k: v for k, v in trades[i].items()},
                       stretch_ordinal_from_6pm=member[i],
                       overlapping_leg_ordinals_from_6pm=leg_member[member[i]]) for i in range(before)]
    files = []
    for name, lines in (('trades', trade_rows), ('stretches', stretch_rows), ('legs', leg_rows)):
        path = out / f'trade-legs-6pm-to-8pm-{name}-{day}.parquet'
        pq.write_table(pa.Table.from_pylist(lines), path, compression='zstd', compression_level=store.ZSTD_LEVEL)
        raw = path.read_bytes()
        files.append(dict(file=path.name, rows=len(lines), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest()))
    receipt = dict(
        what='The trade legs of 6 pm to 8 pm Eastern, made by the old rule from the trade day\'s first trade',
        decided='Greg, 2026-11-17: "build the mossing hrs exactly how we built the current data"; "Then change it '
                '... Finish the data"', trade_day=trade_day.isoformat(),
        rule=dict(commit=RULE_COMMIT, file=RULE_FILE, sha256=RULE_SHA256, functions=['price_stretches', 'print_legs']),
        old_record=dict(commit=OLD_COMMIT, folder=OLD_FOLDER.format(day=day), sha256=OLD_SHA256[day],
                        trades=len(old['trades']), legs=len(old['legs'])),
        trades_in_the_trade_day=len(trades), trades_before_8pm=before, stretches_from_6pm=len(stretches),
        legs_from_6pm=len(legs), legs_written=len(leg_rows), stretches_written=len(stretch_rows),
        checks=dict(passed=True, old_trades_compared=len(old['trades']), old_legs_compared=matched,
                    what='every old trade is the tape\'s trade at the same place from 8 pm (clocks, price, size, '
                         'order, side, time its event was complete); every old leg after the first comes out again '
                         'with the same trades, direction and price change'),
        kept_beside='the old legs and trades are kept as they are; the old first leg, cut at 8 pm, is named on the '
                    'whole leg that crosses 8 pm',
        files=files, seconds=round(time.monotonic() - started, 1))
    (out / f'TRADE-LEGS-{day}.json').write_text(json.dumps(receipt, indent=1) + '\n')
    return receipt


def main():
    ap = argparse.ArgumentParser(description='the missing two hours of the trade legs')
    ap.add_argument('trade_day')
    ap.add_argument('--rows', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    a = ap.parse_args()
    receipt = run(parse_trade_day(a.trade_day), a.rows, a.out)
    print(json.dumps({k: receipt[k] for k in ('trade_day', 'trades_before_8pm', 'legs_written', 'checks',
                                              'seconds')}, indent=1))


if __name__ == '__main__':
    main()
