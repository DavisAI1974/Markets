"""ROOT command line (SPEC-root.md "Commands"). Only the parts built so far are here.

    python3 -m root.run check-week 20231002 [--tape <markets-data>/data/nymex_mbo/ng_v0_oct2023] [--out <dir>]
    python3 -m root.run check-book 20231002 [--tape ...] [--out <dir>]
    python3 -m root.run build 20231002 --out <markets-data folder> [--tape ...]
    python3 -m root.run playback 20231002 [--tape ...] [--out <dir>]
    python3 -m root.run calc flow_peak 20231002 --rows <stored rows folder> --out <markets-data folder> [--tape ...]
        (calculations: flow_peak, peak_story, book_totals, quote_runs, peak_links, open_stories, refills, sweeps,
         chain_peaks)
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from root.calendar import parse_trade_day
from root import checks, part2, pin, store, tape
from root.book import check_book
from root.tape import check_week

BYTES_PER_MEGABYTE = 2 ** 20
DEFAULT_TAPE = Path(os.environ.get('MARKETS_DATA', '../markets-data')) / 'data' / 'nymex_mbo' / 'ng_v0_oct2023'


def main():
    ap = argparse.ArgumentParser(description='ROOT command line')
    sub = ap.add_subparsers(dest='command', required=True)
    cw = sub.add_parser('check-week', help='files present, fingerprints, record counts, what each record is')
    cw.add_argument('trade_day')
    cw.add_argument('--tape', type=Path, default=DEFAULT_TAPE)
    cw.add_argument('--out', type=Path, help='folder for the receipt (markets-data receipts/)')
    cb = sub.add_parser('check-book', help='the carried book against the vendor restatement; the book adds up')
    cb.add_argument('trade_day')
    cb.add_argument('--tape', type=Path, default=DEFAULT_TAPE)
    cb.add_argument('--out', type=Path, help='folder for the record (markets-data receipts/)')
    bd = sub.add_parser('build', help='one trade day: rows, book pictures, restatement table, receipt')
    bd.add_argument('trade_day')
    bd.add_argument('--tape', type=Path, default=DEFAULT_TAPE)
    bd.add_argument('--out', type=Path, required=True, help='output folder (in markets-data, never in Markets)')
    bd.add_argument('--outside', type=Path, default=pin.DEFAULT_TABLES, help='the made outside tables (section G)')
    pb = sub.add_parser('playback', help='the playback check: rows do not change when the tape is cut')
    pb.add_argument('trade_day')
    pb.add_argument('--tape', type=Path, default=DEFAULT_TAPE)
    pb.add_argument('--out', type=Path, help='folder for the record')
    ca = sub.add_parser('calc', help='part 2: one calculation on one trade day, its columns beside the stored rows')
    ca.add_argument('name', choices=sorted(part2.CALCS))
    ca.add_argument('trade_day')
    ca.add_argument('--tape', type=Path, default=DEFAULT_TAPE)
    ca.add_argument('--rows', type=Path, required=True, help='the folder of the stored rows of that trade day')
    ca.add_argument('--out', type=Path, required=True, help='output folder (in markets-data, never in Markets)')
    a = ap.parse_args()
    if a.command == 'calc':
        receipt = part2.run(a.tape, parse_trade_day(a.trade_day), a.rows, a.out, a.name)
        print(json.dumps(dict(calculation=a.name, trade_day=receipt['trade_day'], rows=receipt['rows'],
                              ticks_calculated_on=receipt['ticks_calculated_on'], counts=receipt['counts'],
                              megabytes=round(sum(f['bytes'] for f in receipt['files'] + [f for t in receipt['tables'].values()
                                                                              for f in t['files']]) / BYTES_PER_MEGABYTE, 1),
                              tables={t: v['lines'] for t, v in receipt['tables'].items()},
                              recount=receipt['checks']['recount'], playback=receipt['checks']['playback'],
                              seconds=receipt['seconds']), indent=1))
    if a.command == 'build':
        day = parse_trade_day(a.trade_day)
        receipt = store.build(a.tape, day, a.out, checker=checks.RowChecker(day), outside_tables=a.outside)
        size = lambda files: round(sum(f['bytes'] for f in files) / BYTES_PER_MEGABYTE, 1)
        print(json.dumps(dict(trade_day=receipt['trade_day'], rows=receipt['rows'], columns=receipt['columns'],
                              row_megabytes=size(receipt['row_files']),
                              book_pictures_at_trades=receipt['book_pictures_at_trades'],
                              book_picture_megabytes=size(receipt['book_picture_files']),
                              checks_passed=bool(receipt['checks']['rows']['passed'] and
                                                 receipt['checks']['accounted']['passed'] and
                                                 receipt['checks']['outside_pinned']['passed']),
                              seconds=receipt['seconds']), indent=1))
    if a.command == 'playback':
        day = parse_trade_day(a.trade_day)
        result = dict(what='ROOT playback check (criterion 8)', trade_day=day.isoformat(),
                      cuts=checks.playback(tape.read_week(a.tape, day), day))
        if a.out:
            a.out.mkdir(parents=True, exist_ok=True)
            (a.out / f'playback-{day:%Y%m%d}.json').write_text(json.dumps(result, indent=1) + '\n')
        print(json.dumps(result, indent=1))
    if a.command == 'check-book':
        day = parse_trade_day(a.trade_day)
        record = check_book(a.tape, day)
        if a.out:
            a.out.mkdir(parents=True, exist_ok=True)
            (a.out / f'check-book-{day:%Y%m%d}.json').write_text(json.dumps(record, indent=1) + '\n')
        print(json.dumps({k: record[k] for k in ('trade_day', 'all_equal', 'all_add_up', 'irregular',
                                                 'orders_resting_at_the_end', 'seconds')}, indent=1))
        for c in record['book_equals_restatement']:
            print(c['file'], 'equal' if c['equal'] else 'DIFFERS', c['orders_in_restatement'], 'orders')
        print('trades checked', record['whole_book_figures'][-1]['trades_checked'])
    if a.command == 'check-week':
        day = parse_trade_day(a.trade_day)
        receipt = check_week(a.tape, day)
        text = json.dumps(receipt, indent=1) + '\n'
        if a.out:
            a.out.mkdir(parents=True, exist_ok=True)
            (a.out / f'check-week-{day:%Y%m%d}.json').write_text(text)
        brief = {k: v for k, v in receipt.items() if k not in ('files', 'record_fields')}
        print(json.dumps(brief, indent=1))
        for f in receipt['files']:
            print(f['file'], f['records'], 'records |', f['vendor_snapshot_records'], 'vendor snapshot |',
                  f['ticks_for_this_box'])


if __name__ == '__main__':
    main()
