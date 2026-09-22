"""Derive ONE TRADING DAY's source manifest from a staged block manifest, with no AWS call.

The trading day is the unit (Greg, 2026-09-22: "A Monday trading day starts at 6 pm on Sun and ends at 5 pm on Mon for
23 hrs. There is no more 'Sunday'."); the block's files are UTC partitions. The staged manifest already measured, per
partition, the records before and at/after the halt (`sessions[].before_halt/after_halt`, decoded at staging). Under the
trading-day policy a partition's pre-halt records belong to its own date and its post-halt records to the next date,
both rolled to Monday when they land on a weekend (the same rule as ingest_block_sources.session_policy). So a trading
day D takes, from each partition, the pre-halt records labelled D plus the post-halt records labelled D.

A partition whose contribution is its WHOLE file is a full member; one whose contribution is exactly its pre-halt
records (a leading take) is a partial member (`partial_members`, which ingest_block_sources stops at and verifies at
the boundary). A contribution that would be a TAIL (post-halt records only, the prior partition of a weekday) is refused
here: that day is ingested from the whole block, not by itself. The members keep their sha256 and size (the whole file),
`mbo_records` becomes the take, and the manifest hash is recomputed by raw_mbo_source_manifest.manifest_hash.

    python operations/derive_trading_day_manifest.py --block-manifest blocks/BLOCK_20211004_20211006_SOURCE_MANIFEST.json \
        --trading-day 20211004 --out blocks/BLOCK_20211004_SOURCE_MANIFEST.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'research' / 'kalshi' / 'frankie_boss'))
from raw_mbo_source_manifest import manifest_hash  # noqa: E402
from research.kalshi.frankie_boss.block_source_scope import block_source_scope  # noqa: E402


def _roll(day):
    """A date on Saturday or Sunday is Monday's trading day (the CME week; holidays not modelled)."""
    if day.weekday() >= 5:
        day += dt.timedelta(days=7 - day.weekday())
    return day


def contributions(block, trading_day):
    """Per partition, in replay order: (session entry, records this trading day takes, kind) with kind in
    whole | leading | tail | none."""
    target = dt.datetime.strptime(trading_day, '%Y%m%d').date()
    out = []
    for entry in block['sessions']:
        day = dt.datetime.strptime(entry['day_utc'], '%Y%m%d').date()
        before = entry['before_halt'] if _roll(day) == target else 0
        after = entry['after_halt'] if _roll(day + dt.timedelta(days=1)) == target else 0
        take = before + after
        if take == 0:
            kind = 'none'
        elif take == entry['mbo_records']:
            kind = 'whole'
        elif after == 0:
            kind = 'leading'
        else:
            kind = 'tail'
        out.append((entry, take, kind))
    return out


def derive(block, trading_day):
    if block.get('schema') != 'BOSS_BLOCK_SOURCE_MANIFEST_V1' or manifest_hash(block) != block.get('manifest_hash'):
        raise ValueError('a hash-bound block source manifest is required')
    if any(s['mbo_records'] != s['before_halt'] + s['after_halt'] for s in block['sessions']):
        raise ValueError('the block manifest sessions do not reconcile to their partitions')
    by_key = {s['member_key']: s for s in block['sources']}
    sources, sessions, partial = [], [], []
    for entry, take, kind in contributions(block, trading_day):
        if kind == 'none':
            continue
        if kind == 'tail':
            raise ValueError(f'{entry["member_key"]} contributes a tail (post-halt records only) to {trading_day}; '
                             'a tail take is not supported by itself: ingest that day from the whole block')
        member = dict(by_key[entry['member_key']])
        member['member_index'] = len(sources)
        if kind == 'leading':
            partial.append(dict(member_key=member['member_key'], partition_mbo_records=member['mbo_records'], take=take,
                                reason='records before the 21:00Z halt belong to this trading day; the rest are the next day'))
            member['mbo_records'] = take
        sources.append(member)
        sessions.append(dict(entry))
    if not sources:
        raise ValueError(f'no partition of the block contributes to trading day {trading_day}')
    body = {k: v for k, v in block.items() if k not in ('manifest_hash', 'sources', 'sessions', 'total_mbo_records', 'block')}
    body.update(block=trading_day, trading_day=trading_day, sources=sources, sessions=sessions,
                total_mbo_records=sum(s['mbo_records'] for s in sources), partial_members=partial,
                derived_from=dict(block=block['block'], manifest_hash=block['manifest_hash']),
                derived_unix=int(time.time()), ingested=False, scheduled=False, prefixes_built=False)
    body['manifest_hash'] = manifest_hash(body)
    block_source_scope(body, expected_manifest_hash=body['manifest_hash'])      # the validator's word, before anything is written
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--block-manifest', required=True)
    parser.add_argument('--trading-day', required=True, help='YYYYMMDD, the trade date')
    parser.add_argument('--out', required=True, help='written once; an existing file is never overwritten')
    args = parser.parse_args()
    body = derive(json.loads(Path(args.block_manifest).read_bytes()), args.trading_day)
    raw = json.dumps(body, indent=2, sort_keys=True).encode() + b'\n'
    with Path(args.out).open('xb') as stream:
        stream.write(raw)
    print(json.dumps(dict(status='trading_day_manifest_derived', trading_day=args.trading_day, out=args.out,
                          members=[(s['member_key'], s['mbo_records']) for s in body['sources']],
                          total_mbo_records=body['total_mbo_records'], partial_members=body['partial_members'],
                          manifest_hash=body['manifest_hash'])))


if __name__ == '__main__':
    main()
