"""ROOT command line (SPEC-root.md "Commands"). Only the parts built so far are here.

    python3 -m root.run check-week 20231002 [--tape <markets-data>/data/nymex_mbo/ng_v0_oct2023] [--out <dir>]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from root.calendar import parse_trade_day
from root.tape import check_week

DEFAULT_TAPE = Path(os.environ.get('MARKETS_DATA', '../markets-data')) / 'data' / 'nymex_mbo' / 'ng_v0_oct2023'


def main():
    ap = argparse.ArgumentParser(description='ROOT command line')
    sub = ap.add_subparsers(dest='command', required=True)
    cw = sub.add_parser('check-week', help='files present, fingerprints, record counts, what each record is')
    cw.add_argument('trade_day')
    cw.add_argument('--tape', type=Path, default=DEFAULT_TAPE)
    cw.add_argument('--out', type=Path, help='folder for the receipt (markets-data receipts/)')
    a = ap.parse_args()
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
