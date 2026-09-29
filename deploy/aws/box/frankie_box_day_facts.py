"""Per-day facts of candidate trading days, and the staged BLOCK manifests they need, on Frankie's box (Greg, 2026-09-29:
"we have to start picking closely matched Tue and Wed ... I'd like to have 30 days when we're done"; "The historical
data days should be in aws"). research/kalshi/frankie_boss/DAY_SELECTION_20260929.md says why and what for.

READ-ONLY on everything that exists. It never ingests, never touches a journal, a receipt or a run directory, writes
nothing to S3 and makes no model call. What it writes:
  /opt/frankie-box/data/block_<block>/glbx-mdp3-<day>.mbo.dbn.zst   the partitions (new files only: an existing file with
      the committed sha256 is kept, the same file under another block_* is hard-linked, a missing one is downloaded
      through the presigned map; a DIFFERENT file at the destination is never overwritten, it is listed). This is the
      directory frankie_box_ingest_block.sh ACTION=fetch reads, so the ingest later finds or links them.
  /opt/frankie-box/work/day-facts/<RUN>/  (created fresh; an existing RUN is refused)
      days/<day>.json                         the day's facts (below)
      blocks/BLOCK_<block>_SOURCE_MANIFEST.json  the staged block manifest (BOSS_BLOCK_SOURCE_MANIFEST_V1, the same body
          operations/stage_block_sources.py writes, counts from ITS count_records, unchanged), to be committed and then
          derived per day by operations/derive_trading_day_manifest.py in the container (no AWS there)
      receipt.json                            every partition, day and block with its status; everything listed, nothing
                                              dropped
Everything written is also printed, so the job log carries it whole (ssm_run_sh.py reports part by part).

Partitions come from the COMMITTED canonical object manifest of the 5-year pull
(research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json: key, bytes, sha256 per UTC partition). The
workflow presigns those keys (frankie_box_run.yml presign=<bucket>/<key> ...); the box role reads nothing in S3 itself.
Nothing here touches Databento.

A trading day D (Tue-Fri) = the records at or after the 17:00 ET halt of the prior calendar day's partition (the tail)
plus the records before the halt of D's own partition (the head); the halt is 17:00 America/New_York in UTC, per day
(21:00Z under EDT, 22:00Z under EST). A block = the partitions from the day before its first day to its last day, in
one week; every partition of a block must share one halt hour (the manifest carries one).

Per day facts (every figure its own; nothing averaged, nothing pooled across days):
  records (tail + head) reconciled to the staging counts; instrument ids per part (a day whose two parts carry different
  instruments crosses a roll of the volume-continuous series and is FLAGGED, not dropped); whether the tail partition
  opens with Databento's F_SNAPSHOT book (the warm-start opening book); per action counts; trades (action T), volume,
  aggressor side split; trade prices: first, last, high, low, range; per ET hour: records, trades, volume, high, low;
  the largest 1-minute trade-price range and its minute; the three largest gaps between consecutive records of the day
  (the halt-to-reopen gap included, each listed with its times); F_BAD_TS_RECV and F_MAYBE_BAD_BOOK counts; the DBN
  metadata header (symbols, stype, the continuous symbol's mapping) of both partitions.

THE WALL (spec "Days"; R15): discovery = 2021-2023, confirmation = 2024-2025 (the orchestrator's ROLE_OF_YEAR). A
confirmation day is REFUSED (listed) unless CONFIRMATION=staging-only, and then only the staging counts run (records
before/after the halt: what a manifest needs), never the facts pass: no price, trade or book fact of a confirmation day
is read until the survivor list is frozen. Greg's answer of 2026-09-29 (all years 2021-2026 alike for SELECTION) is
recorded in DAY_SELECTION_20260929.md; a full-facts mode for 2024-2025 days is not part of this script (open there).
"""
import argparse
import datetime as dt
import glob
import hashlib
import io
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from contextlib import ExitStack
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
BOX = Path('/opt/frankie-box')
CANONICAL = 'research/kalshi/NG_EXHAUSTION_MBO_5Y_CANONICAL_OBJECT_MANIFEST_20260822.json'
BLOCKS_DIR = 'research/kalshi/frankie_boss/blocks'
SCHEMA_FACTS = 'FRANKIE_DAY_FACTS_V1'
UNDEF_PRICE = 9223372036854775807
F_LAST, F_SNAPSHOT, F_BAD_TS_RECV, F_MAYBE_BAD_BOOK = 0x80, 0x20, 0x08, 0x04


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''):
            h.update(b)
    return h.hexdigest()


def ymd(day):
    return dt.date(int(day[:4]), int(day[4:6]), int(day[6:]))


def halt_utc_hour(day):
    """17:00 America/New_York on `day`, as a UTC hour (21 under EDT, 22 under EST)."""
    from zoneinfo import ZoneInfo
    local = dt.datetime(*ymd(day).timetuple()[:3], 17, tzinfo=ZoneInfo('America/New_York'))
    utc = local.astimezone(dt.timezone.utc)
    if utc.date() != ymd(day) or utc.minute:
        raise ValueError(f'the 17:00 ET halt of {day} is not a whole UTC hour of the same date')
    return utc.hour


def roll(day):
    """A date on Saturday or Sunday is Monday's trading day (ingest_block_sources.session_policy's rule)."""
    if day.weekday() >= 5:
        day += dt.timedelta(days=7 - day.weekday())
    return day


def plan_blocks(days):
    """Group the trading days into blocks: one per ISO week, partitions from the day before the week's first day to its
    last day (consecutive calendar days, all weekdays for Tue-Fri days)."""
    weeks = {}
    for day in days:
        d = ymd(day)
        if d.weekday() not in (1, 2, 3, 4):
            raise SystemExit(f'{day} is not Tuesday-Friday: this tool stages midweek days (a Monday opens on a Sunday partition)')
        weeks.setdefault(d.isocalendar()[:2], []).append(day)
    blocks = []
    for key in sorted(weeks):
        members = sorted(weeks[key])
        first, last = ymd(members[0]) - dt.timedelta(days=1), ymd(members[-1])
        parts, cur = [], first
        while cur <= last:
            parts.append(cur.strftime('%Y%m%d'))
            cur += dt.timedelta(days=1)
        blocks.append(dict(block=f'{parts[0]}_{parts[-1]}', partitions=parts, days=members))
    return blocks


def facts_of_partition(path, day, halt_hour, wanted):
    """One pass over the partition: per trading-day label (only the labels in `wanted`), every fact listed in the module
    docstring. The label rule is the ingest's: before the partition date's halt -> the partition date, else the next
    date, both rolled to Monday."""
    import databento_dbn as dbn
    import zstandard as zstd
    from zoneinfo import ZoneInfo
    from mbo_source import _decompressed
    eastern = ZoneInfo('America/New_York')
    pday = ymd(day)
    halt = int(dt.datetime(pday.year, pday.month, pday.day, halt_hour, tzinfo=dt.timezone.utc).timestamp()) * 10**9
    labels = (roll(pday).strftime('%Y%m%d'), roll(pday + dt.timedelta(days=1)).strftime('%Y%m%d'))
    out = {}

    def part(label):
        if label not in out:
            out[label] = dict(records=0, first_ts_recv_ns=None, last_ts_recv_ns=None, actions={}, instruments={},
                              trades=0, volume=0, side_trades={}, side_volume={}, undefined_price_trades=0,
                              first_trade=None, last_trade=None, high=None, low=None, hours={}, minutes={},
                              snapshot_records=0, bad_ts_recv=0, maybe_bad_book=0, first_record_snapshot=None,
                              gaps=[], _prev=None)
        return out[label]

    with ExitStack() as stack, open(path, 'rb') as raw:
        stream = _decompressed(io.BytesIO(raw.read()), zstd, stack)
        decoder = dbn.DBNDecoder(upgrade_policy=dbn.VersionUpgradePolicy.AS_IS)
        metadata = None
        for chunk in iter(lambda: stream.read(1 << 20), b''):
            for record in decoder.write_and_decode(chunk):
                if type(record) is dbn.Metadata:
                    metadata = record
                    continue
                if type(record) is not dbn.MBOMsg:
                    raise ValueError('non-MBO record in declared MBO source; no record is skipped')
                ts = int(record.ts_recv)
                label = labels[0] if ts < halt else labels[1]
                if label not in wanted:
                    continue
                p = part(label)
                flags = int(record.flags)
                p['records'] += 1
                if p['first_ts_recv_ns'] is None:
                    p['first_ts_recv_ns'] = ts
                    p['first_record_snapshot'] = bool(flags & F_SNAPSHOT)
                p['last_ts_recv_ns'] = ts
                prev = p['_prev']
                if prev is not None and ts - prev > 0:
                    gap = ts - prev
                    gaps = p['gaps']
                    if len(gaps) < 4 or gap > gaps[-1][0]:
                        gaps.append((gap, prev, ts))
                        gaps.sort(reverse=True)
                        del gaps[4:]
                p['_prev'] = ts
                action, side = str(record.action), str(record.side)
                p['actions'][action] = p['actions'].get(action, 0) + 1
                iid = str(int(record.instrument_id))
                p['instruments'][iid] = p['instruments'].get(iid, 0) + 1
                p['snapshot_records'] += bool(flags & F_SNAPSHOT)
                p['bad_ts_recv'] += bool(flags & F_BAD_TS_RECV)
                p['maybe_bad_book'] += bool(flags & F_MAYBE_BAD_BOOK)
                moment = dt.datetime.fromtimestamp(ts // 10**9, tz=dt.timezone.utc).astimezone(eastern)
                hour = moment.strftime('%Y-%m-%d %H')
                h = p['hours'].setdefault(hour, dict(records=0, trades=0, volume=0, high=None, low=None))
                h['records'] += 1
                if action != 'T':
                    continue
                size = int(record.size)
                p['trades'] += 1
                p['volume'] += size
                h['trades'] += 1
                h['volume'] += size
                p['side_trades'][side] = p['side_trades'].get(side, 0) + 1
                p['side_volume'][side] = p['side_volume'].get(side, 0) + size
                price = int(record.price)
                if price == UNDEF_PRICE:
                    p['undefined_price_trades'] += 1
                    continue
                if p['first_trade'] is None:
                    p['first_trade'] = dict(price=price, ts_recv_ns=ts)
                p['last_trade'] = dict(price=price, ts_recv_ns=ts)
                p['high'] = price if p['high'] is None else max(p['high'], price)
                p['low'] = price if p['low'] is None else min(p['low'], price)
                h['high'] = price if h['high'] is None else max(h['high'], price)
                h['low'] = price if h['low'] is None else min(h['low'], price)
                minute = moment.strftime('%Y-%m-%d %H:%M')
                m = p['minutes'].get(minute)
                p['minutes'][minute] = [price, price] if m is None else [max(m[0], price), min(m[1], price)]
        if decoder.buffer() or metadata is None:
            raise ValueError('complete MBO source with one metadata header required')
    mapping = None
    try:
        mapping = {str(k): [dict((str(a), str(b)) for a, b in (iv.items() if hasattr(iv, 'items') else vars(iv).items()))
                            for iv in v] for k, v in dict(metadata.mappings).items()}
    except Exception as exc:      # listed, never a failure: the instrument ids per record are the fact that counts
        mapping = dict(unreadable=repr(exc))
    for p in out.values():
        del p['_prev']
        p['gaps'] = [dict(seconds=round(g / 1e9, 3), after_ts_recv_ns=a, before_ts_recv_ns=b) for g, a, b in p['gaps']]
        wide = max(p['minutes'].items(), key=lambda kv: kv[1][0] - kv[1][1]) if p['minutes'] else None
        p['max_1min_range'] = dict(minute_et=wide[0], high=wide[1][0], low=wide[1][1]) if wide else None
        del p['minutes']
    return dict(partition=day, halt_utc_hour=halt_hour, labels=out,
                metadata=dict(dataset=str(getattr(metadata, 'dataset', '')), stype_in=str(getattr(metadata, 'stype_in', '')),
                              stype_out=str(getattr(metadata, 'stype_out', '')), symbols=[str(s) for s in metadata.symbols],
                              mappings=mapping))


def stage_counts(path, day, halt_hour):
    """The staging tool's own count (operations/stage_block_sources.count_records, unchanged): the manifest's numbers."""
    from research.kalshi.frankie_boss.operations.stage_block_sources import count_records
    with open(path, 'rb') as f:
        return count_records(f.read(), day, halt_hour)


def work_partition(job):
    """A worker: staging counts always; the facts pass only when the job asks for it (discovery days)."""
    try:
        counts = stage_counts(job['path'], job['partition'], job['halt'])
        facts = facts_of_partition(job['path'], job['partition'], job['halt'], set(job['wanted'])) if job['wanted'] else None
        return dict(job, status='decoded', counts=counts, facts=facts)
    except Exception as exc:
        return dict(job, status='decode_failed', error=repr(exc))


def price_dollars(value):
    return None if value is None else round(value / 1e9, 6)


def day_facts(day, tail, head, tail_counts, head_counts):
    """Join the two parts of trading day `day` (tail from the prior partition, head from its own) in time order."""
    parts = [x for x in (tail, head) if x]
    rec = dict(records=sum(x['records'] for x in parts), tail_records=tail['records'] if tail else 0,
               head_records=head['records'] if head else 0)
    staged = (tail_counts['after_halt'] if tail_counts else 0) + (head_counts['before_halt'] if head_counts else 0)
    trades = [x for x in parts if x['first_trade']]
    first, last = (trades[0]['first_trade'] if trades else None), (trades[-1]['last_trade'] if trades else None)
    highs = [x['high'] for x in parts if x['high'] is not None]
    lows = [x['low'] for x in parts if x['low'] is not None]
    hi, lo = (max(highs) if highs else None), (min(lows) if lows else None)
    hours = {}
    for x in parts:
        for k, v in x['hours'].items():
            h = hours.setdefault(k, dict(records=0, trades=0, volume=0, high=None, low=None))
            h['records'] += v['records']; h['trades'] += v['trades']; h['volume'] += v['volume']
            for key, fn in (('high', max), ('low', min)):
                if v[key] is not None:
                    h[key] = v[key] if h[key] is None else fn(h[key], v[key])
    add = lambda field: {k: sum(x[field].get(k, 0) for x in parts) for k in sorted({k for x in parts for k in x[field]})}
    wides = [x['max_1min_range'] for x in parts if x['max_1min_range']]
    wide = max(wides, key=lambda w: w['high'] - w['low']) if wides else None
    instruments = [dict(part=name, instruments=x['instruments']) for name, x in (('tail', tail), ('head', head)) if x]
    ids = {k for x in parts for k in x['instruments']}
    return dict(
        schema=SCHEMA_FACTS, trading_day=day, weekday=ymd(day).strftime('%a'), **rec,
        staged_records=staged, records_reconcile=rec['records'] == staged,
        instruments=instruments, single_instrument=len(ids) == 1,
        tail_opens_with_snapshot=tail['first_record_snapshot'] if tail else None,
        actions=add('actions'), trades=sum(x['trades'] for x in parts), volume=sum(x['volume'] for x in parts),
        side_trades=add('side_trades'), side_volume=add('side_volume'),
        undefined_price_trades=sum(x['undefined_price_trades'] for x in parts),
        first_trade=dict(price=price_dollars(first['price']), ts_recv_ns=first['ts_recv_ns']) if first else None,
        last_trade=dict(price=price_dollars(last['price']), ts_recv_ns=last['ts_recv_ns']) if last else None,
        high=price_dollars(hi), low=price_dollars(lo), range=price_dollars(hi - lo) if highs and lows else None,
        close_minus_open=price_dollars(last['price'] - first['price']) if first and last else None,
        per_hour_et=[dict(hour=k, records=v['records'], trades=v['trades'], volume=v['volume'],
                          high=price_dollars(v['high']), low=price_dollars(v['low'])) for k, v in sorted(hours.items())],
        max_1min_range=dict(minute_et=wide['minute_et'], high=price_dollars(wide['high']), low=price_dollars(wide['low']),
                            range=price_dollars(wide['high'] - wide['low'])) if wide else None,
        largest_gaps=sorted((g for x in parts for g in x['gaps']), key=lambda g: -g['seconds'])[:3],
        snapshot_records=sum(x['snapshot_records'] for x in parts), bad_ts_recv=sum(x['bad_ts_recv'] for x in parts),
        maybe_bad_book=sum(x['maybe_bad_book'] for x in parts))


def fetch(member, canonical, data_dir, url_map, receipt):
    """The partition at data_dir/<member>: present (sha checked), linked from another block_* dir, or downloaded."""
    name = f'glbx-mdp3-{member}.mbo.dbn.zst'
    obj = canonical.get(member)
    if obj is None:
        receipt.append(dict(partition=member, status='not_in_canonical_manifest'))
        return None
    dest = data_dir / name
    if dest.exists():
        if dest.stat().st_size == obj['bytes'] and sha256_file(dest) == obj['sha256']:
            receipt.append(dict(partition=member, status='present', key=obj['key'])); return dest
        receipt.append(dict(partition=member, status='refused', reason='a different file is at the destination; not '
                            'overwritten', key=obj['key'])); return None
    for other in sorted(glob.glob(str(BOX / 'data' / 'block_*' / name))):
        if os.path.getsize(other) == obj['bytes'] and sha256_file(other) == obj['sha256']:
            os.link(other, dest)
            receipt.append(dict(partition=member, status='linked', linked_from=other, key=obj['key'])); return dest
    entry = url_map.get(obj['key']) or next((v for k, v in url_map.items() if k.endswith('/' + name)), None)
    if entry is None:
        receipt.append(dict(partition=member, status='refused', reason='not in the presigned map', key=obj['key'])); return None
    url = entry.get('url', '')
    if not (url.startswith('https://') and '.amazonaws.com/' in url.split('?', 1)[0]):
        receipt.append(dict(partition=member, status='refused', reason='map entry is not an https amazonaws URL')); return None
    part = Path(str(dest) + '.part')
    t0 = time.time()
    r = subprocess.run(['curl', '-fsS', '--proto', '=https', '-L', '--retry', '5', '--retry-delay', '5', '-C', '-',
                        '-o', str(part), '--url', url])
    if r.returncode != 0:
        receipt.append(dict(partition=member, status='refused', reason='download failed', returncode=r.returncode)); return None
    got = sha256_file(part)
    if part.stat().st_size != obj['bytes'] or got != obj['sha256']:
        os.replace(part, str(part) + f'.rejected-{int(time.time())}')
        receipt.append(dict(partition=member, status='refused', reason='digest differs from the canonical manifest',
                            sha256=got)); return None
    if dest.exists():
        os.replace(part, str(part) + f'.late-{int(time.time())}')
        receipt.append(dict(partition=member, status='refused', reason='a file appeared at the destination')); return None
    os.replace(part, dest)
    receipt.append(dict(partition=member, status='downloaded', key=obj['key'], seconds=round(time.time() - t0, 1)))
    return dest


def block_manifest(block, sessions, canonical, bucket):
    """The staged block manifest, in stage_block_sources.main()'s body shape (plus each session's archive_key, since the
    partitions stay at their archive keys: the box has no S3 write, so nothing is copied under frankie/)."""
    from raw_mbo_source_manifest import manifest_hash
    halts = {s['halt_utc_hour'] for s in sessions}
    if len(halts) != 1:
        raise ValueError(f'block {block} crosses a clock change (halt hours {sorted(halts)}); split it')
    sources, entries = [], []
    for index, s in enumerate(sessions):
        obj = canonical[s['partition']]
        name = f"glbx-mdp3-{s['partition']}.mbo.dbn.zst"
        sources.append(dict(member_index=index, member_key=name, sha256=obj['sha256'], size_bytes=obj['bytes'],
                            mbo_records=s['counts']['mbo_records']))
        entries.append(dict(member_key=name, day_utc=s['partition'], archive_key=obj['key'], **s['counts']))
    body = dict(schema='BOSS_BLOCK_SOURCE_MANIFEST_V1', source_kind='NATIVE_DBN_MBO', role='HELD_OUT_BLIND_BLOCK',
                member_seams_close_groups=all(x['last_record_f_last'] for x in entries[:-1]),
                halt_boundaries_close_groups=all(x['halt_boundary_f_last'] in (True, None) for x in entries),
                causal_clock='ts_recv_ns', sampled=False, canonical_source_rewritten=False, block=block, bucket=bucket,
                prefix='nymex/ng_mbo_5y_v0/native', archive_prefix='nymex/ng_mbo_5y_v0/native',
                halt_utc_hour=halts.pop(), sources=sources, sessions=entries,
                total_mbo_records=sum(x['mbo_records'] for x in sources),
                staged_unix=int(time.time()), staged_by='deploy/aws/box/frankie_box_day_facts.py (presigned GET of the '
                'archive keys, counts by stage_block_sources.count_records; no S3 copy)',
                ingested=False, scheduled=False, prefixes_built=False, model_calls=0)
    body['manifest_hash'] = manifest_hash(body)
    return body


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--code-root', required=True)
    p.add_argument('--days', required=True, help='comma list of trading days YYYYMMDD (Tue-Fri)')
    p.add_argument('--run', required=True)
    p.add_argument('--map', default='', help='the downloaded presigned map JSON (absent: only present/linked partitions)')
    p.add_argument('--workers', type=int, default=6)
    p.add_argument('--confirmation', choices=('refuse', 'staging-only'), default='refuse')
    a = p.parse_args()
    code = Path(a.code_root)
    for entry in (str(code), str(code / 'research' / 'kalshi' / 'frankie_boss')):
        sys.path.insert(0, entry)
    from frankie_box_experiment import ROLE_OF_YEAR          # the orchestrator's wall, one definition
    manifest = json.loads((code / CANONICAL).read_bytes())
    canonical = {o['key'].split('glbx-mdp3-')[1][:8]: o for o in manifest['canonical_dbn_objects']}
    days = sorted(set(d.strip() for d in a.days.split(',') if d.strip()))
    if any(len(d) != 8 or not d.isdigit() for d in days):
        raise SystemExit('DAYS must be YYYYMMDD values')
    out = BOX / 'work' / 'day-facts' / a.run
    if not a.run.replace('-', '').replace('_', '').isalnum() or out.exists():
        raise SystemExit(f'RUN must be a fresh [A-Za-z0-9_-] name ({out} exists or the name is bad)')
    url_map = json.loads(Path(a.map).read_bytes()) if a.map else {}
    (out / 'days').mkdir(parents=True)
    (out / 'blocks').mkdir()
    receipt = dict(schema='FRANKIE_DAY_FACTS_RUN_V1', run=a.run, at=time.time(), code_root=str(code),
                   days=days, confirmation=a.confirmation, partitions=[], refused_days=[], blocks=[], days_written=[])
    roles = {d: ROLE_OF_YEAR.get(ymd(d).year, 'outside the assigned years') for d in days}
    admitted = []
    for d in days:
        if roles[d] == 'confirmation' and a.confirmation == 'refuse':
            receipt['refused_days'].append(dict(day=d, reason='confirmation day (R15): untouched until the survivor list is '
                                                'frozen; CONFIRMATION=staging-only reads its record counts only, on Greg\'s word'))
        else:
            admitted.append(d)
    blocks = plan_blocks(admitted) if admitted else []
    jobs = []
    for b in blocks:
        data_dir = BOX / 'data' / f"block_{b['block']}"
        data_dir.mkdir(parents=True, exist_ok=True)
        b['halts'] = {m: halt_utc_hour(m) for m in b['partitions']}
        for m in b['partitions']:
            path = fetch(m, canonical, data_dir, url_map, receipt['partitions'])
            nxt = (ymd(m) + dt.timedelta(days=1)).strftime('%Y%m%d')
            # the facts pass reads only discovery days: the labels a partition carries for admitted non-confirmation days
            wanted = [x for x in (m, nxt) if x in b['days'] and roles[x] != 'confirmation']
            if path is not None:
                jobs.append(dict(block=b['block'], partition=m, path=str(path), halt=b['halts'][m], wanted=wanted))
    results = {}
    with ProcessPoolExecutor(max_workers=max(1, a.workers)) as pool:
        for r in pool.map(work_partition, jobs):
            results[(r['block'], r['partition'])] = r
            print(json.dumps(dict(partition=r['partition'], block=r['block'], status=r['status'],
                                  counts=r.get('counts'), error=r.get('error'))), flush=True)
    for b in blocks:
        got = [results.get((b['block'], m)) for m in b['partitions']]
        committed = [d for d in b['days'] if (code / BLOCKS_DIR / f'BLOCK_{d}_SOURCE_MANIFEST.json').exists()]
        status = dict(block=b['block'], partitions=b['partitions'], days=b['days'])
        if any(g is None or g['status'] != 'decoded' for g in got):
            status.update(manifest='not_written', reason='a partition is missing or failed to decode (listed above)')
        elif len(committed) == len(b['days']):
            status.update(manifest='not_written', reason='every day of the block already has a committed per-day manifest')
        else:
            try:
                body = block_manifest(b['block'], [dict(partition=g['partition'], halt_utc_hour=g['halt'],
                                                        counts=g['counts']) for g in got], canonical, manifest['bucket'])
            except ValueError as exc:
                body = None
                status.update(manifest='not_written', reason=str(exc))
        if status.get('manifest') is None:
            path = out / 'blocks' / f"BLOCK_{b['block']}_SOURCE_MANIFEST.json"
            path.write_text(json.dumps(body, indent=1, sort_keys=True), encoding='utf-8')
            status.update(manifest=str(path), manifest_hash=body['manifest_hash'], total_mbo_records=body['total_mbo_records'])
            print(f'### BLOCK MANIFEST {path.name}')
            print(json.dumps(body, indent=1, sort_keys=True), flush=True)
        receipt['blocks'].append(status)
        for d in b['days']:
            if roles[d] == 'confirmation':
                receipt['days_written'].append(dict(day=d, status='counts_only', reason='CONFIRMATION=staging-only: '
                                                    'record counts for the block manifest, no facts'))
                continue
            prior = (ymd(d) - dt.timedelta(days=1)).strftime('%Y%m%d')
            t, h = results.get((b['block'], prior)), results.get((b['block'], d))
            if not (t and h and t['status'] == 'decoded' and h['status'] == 'decoded'):
                receipt['days_written'].append(dict(day=d, status='not_written', reason='a partition of the day is missing '
                                                    'or failed (listed)'))
                continue
            facts = day_facts(d, t['facts']['labels'].get(d), h['facts']['labels'].get(d), t['counts'], h['counts'])
            facts.update(role=roles[d], partitions=[dict(partition=x['partition'], key=canonical[x['partition']]['key'],
                                                         sha256=canonical[x['partition']]['sha256'],
                                                         halt_utc_hour=x['halt']) for x in (t, h)],
                         metadata=[t['facts']['metadata'], h['facts']['metadata']])
            path = out / 'days' / f'{d}.json'
            path.write_text(json.dumps(facts, indent=1, sort_keys=True), encoding='utf-8')
            receipt['days_written'].append(dict(day=d, status='written', path=str(path),
                                                records_reconcile=facts['records_reconcile'],
                                                single_instrument=facts['single_instrument']))
            print(f'### DAY FACTS {d}')
            print(json.dumps(facts, sort_keys=True), flush=True)
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding='utf-8')
    print('### RECEIPT')
    print(json.dumps(receipt, indent=1, sort_keys=True), flush=True)
    bad = [x for x in receipt['partitions'] if x['status'] == 'refused'] + \
          [x for x in receipt['days_written'] if x['status'] not in ('written', 'counts_only')]
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
