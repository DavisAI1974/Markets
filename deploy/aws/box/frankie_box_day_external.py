"""Frankie's 13 points, attached to each trading day (FRANKIE_DAY_EXTERNAL_V1), on Frankie's box. Greg, 2026-09-29:
"everyone who sees his ingest should see these data points too"; "we should somehow still attach whatever doesn't get
run with this tues and wed to their historical data". Builder and reader:
research/kalshi/frankie_boss/operations/frankie_day_external.py. Plan: HISTORICAL_DATA_PLAN_20260929.md.

ACTION=build, per day of DAYS:
  1. fetch, through the presigned map (MAP_URL), the day-history objects the day needs (frankie/day_history/<run>/...:
     calendar, cot store, storage, consensus captures of the day's prints, weather obs of the day's months, the MOS raw
     files covering it, the day's EIA-930 files, manifest.json) and the curve's native files of the day's two UTC
     partitions (nymex/ng_fut_parent_v0/{definition,statistics,mbo}/native/...), into /opt/frankie-box/work/day-external/
     <RUN>/src/<the S3 key>; the day-history files are checked against its manifest.json, the curve files against the
     curve pull's manifests (a file no manifest names is used and listed `unverified`);
  2. build the day file /opt/frankie-box/work/day-external/<RUN>/<day>/day-external.json and its receipt
     day-external-receipt.json (sha256, bytes, the S3 key, every input with its sha256, the missing list);
  3. ATTACH it (nothing copied, hard links only):
       beside the day's sealed ingest: <ingest dir>/day-external.json + day-external-receipt.json, when exactly one sealed
         ingest of the day exists (ingestion-receipt.json with trading_day = the day); none or more than one: listed,
         linked later with ACTION=link;
       under the day key on S3: frankie/day_external/<day>/day-external.json + day-external-receipt.json, through the
         presigned PUT slots of the map (the box writes nothing to S3 itself); a slot not presigned: listed;
       in Frankie's brain as a LISTED attachment (not his reasoning, not read into his corpus): <BRAIN>/<day>-external/
         MANIFEST.json naming the file, its sha256 and its S3 key (the brain loader reads only cycle/lessons entries,
         so the attachment is found by its day key and never enters the corpus).
ACTION=link: step 3 only, for an existing RUN (after an ingest seals).
Nothing here edits a pinned file, a sealed journal, a receipt of the ingest, or an existing brain entry.
"""
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

BOX = Path('/opt/frankie-box')
WORK = BOX / 'work'
OUT = WORK / 'day-external'
CURVE = 'nymex/ng_fut_parent_v0'
S3_DAY = 'frankie/day_external/{day}/{name}'
FILE, RECEIPT = 'day-external.json', 'day-external-receipt.json'
RECEIPT_SCHEMA = 'FRANKIE_DAY_EXTERNAL_RECEIPT_V1'


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 24), b''):
            h.update(block)
    return h.hexdigest()


def ymd(day):
    return dt.date(int(day[:4]), int(day[4:6]), int(day[6:]))


def wanted_keys(day, keys, history_prefix, prints):
    """The keys of the map one trading day needs."""
    d = ymd(day)
    months = {(d - dt.timedelta(days=k)).strftime('%Y%m') for k in range(0, 12)}
    parts = [(d - dt.timedelta(days=1)).strftime('%Y%m%d'), day]
    out = []
    for k in keys:
        if k.startswith('put:'):
            continue
        if k.startswith(history_prefix + '/'):
            rel = k[len(history_prefix) + 1:]
            fam = rel.split('/', 1)[0]
            name = rel.rsplit('/', 1)[-1]
            if rel in ('manifest.json',) or rel.endswith('/receipt.json') or fam in ('calendar', 'storage'):
                out.append(k)
            elif fam == 'cot' and rel.startswith('cot/store/') and name.endswith('.json'):
                out.append(k)
            elif fam == 'consensus' and any('/%s/' % p in '/' + rel or rel.endswith('/%s.json' % p) for p in prints):
                out.append(k)
            elif fam == 'weather_obs' and name.rsplit('_', 1)[-1].split('.')[0] in months:
                out.append(k)
            elif fam == 'mos' and rel.startswith('mos/raw/'):
                bits = name[:-len('.json')].split('_')
                if len(bits) == 4 and bits[2] <= d.isoformat() <= bits[3]:
                    out.append(k)
            elif fam == 'eia930' and rel.startswith('eia930/%s/' % d.isoformat()):
                out.append(k)
        elif k.startswith(CURVE + '/'):
            if '/manifests/' in k or any(k.endswith('glbx-mdp3-%s.%s.dbn.zst' % (p, s)) for p in parts
                                         for s in ('definition', 'statistics', 'mbo')):
                out.append(k)
    return sorted(set(out))


def fetch(keys, url_map, src, listing):
    for k in keys:
        dest = src / k
        entry = url_map[k]
        if dest.is_file() and dest.stat().st_size == entry.get('bytes'):
            listing.append(dict(key=k, status='present'))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = Path(str(dest) + '.part')
        r = subprocess.run(['curl', '-fsS', '--proto', '=https', '-L', '--retry', '5', '--retry-delay', '5', '-o', str(part),
                            '--url', entry['url']])
        if r.returncode != 0 or part.stat().st_size != entry.get('bytes'):
            listing.append(dict(key=k, status='failed', returncode=r.returncode))
            continue
        os.replace(part, dest)
        listing.append(dict(key=k, status='downloaded', bytes=entry.get('bytes')))


def verify_curve(src, listing):
    """Each curve native file against the curve pull's manifests (key -> sha256)."""
    named = {}
    for m in glob.glob(str(src / CURVE / '*' / 'manifests' / '*.json')):
        for o in json.loads(Path(m).read_bytes()).get('objects', []):
            named[o['key']] = o['sha256']
    out = []
    for p in sorted(glob.glob(str(src / CURVE / '*' / 'native' / '*.dbn.zst'))):
        key = str(Path(p).relative_to(src))
        have = sha256_file(p)
        want = named.get(key)
        status = 'verified' if want == have else ('unverified: no manifest names it' if want is None else 'MISMATCH')
        out.append(dict(key=key, sha256=have, status=status))
        if status == 'MISMATCH':
            raise SystemExit('%s differs from its curve manifest sha256; refused' % key)
    listing.extend(out)
    return out


def build_day(job):
    sys.path.insert(0, job['code_root'])
    from research.kalshi.frankie_boss.operations.frankie_day_external import Build, check_day_file
    day, run_dir = job['day'], Path(job['run_dir'])
    target = run_dir / day
    target.mkdir(parents=True, exist_ok=False)
    t0 = time.time()
    body = Build(job['src'], job['history_prefix'], day).run(with_curve=True, src_curve=str(Path(job['src']) / CURVE))
    check_day_file(body)
    raw = json.dumps(body, separators=(',', ':'), sort_keys=True).encode()
    with open(target / FILE, 'xb') as f:
        f.write(raw)
    receipt = dict(schema=RECEIPT_SCHEMA, trading_day=day, file=FILE, bytes=len(raw),
                   sha256=hashlib.sha256(raw).hexdigest(), s3_key=S3_DAY.format(day=day, name=FILE),
                   s3_receipt_key=S3_DAY.format(day=day, name=RECEIPT), markets_sha=job['markets_sha'], run=job['run'],
                   history_prefix=job['history_prefix'], built_seconds=round(time.time() - t0, 1),
                   points={k: len(v['rows']) for k, v in body['points'].items()}, missing=body['missing'],
                   inputs=body['inputs'], curve_verification=job['curve_verification'],
                   reader='research/kalshi/frankie_boss/operations/frankie_day_external.py AsOfReader',
                   guard='time only: every row has published_ns < halt_ns (checked before writing)')
    (target / RECEIPT).write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding='utf-8')
    return dict(day=day, path=str(target / FILE), sha256=receipt['sha256'], bytes=len(raw), points=receipt['points'],
                missing=len(body['missing']))


def sealed_ingests(day):
    found = []
    for r in sorted(glob.glob(str(WORK / ('ingest-%s-ingest-*' % day) / 'ingestion-receipt.json'))):
        try:
            if json.loads(Path(r).read_bytes()).get('trading_day') == day:
                found.append(Path(r).parent)
        except Exception:
            continue
    return found


def attach(day, run_dir, url_map, brain, results):
    """Link beside the sealed ingest, upload under the day key, list in the brain. Every outcome listed."""
    source = run_dir / day / FILE
    receipt = run_dir / day / RECEIPT
    if not source.is_file():
        results.append(dict(day=day, step='attach', status='no day file in this run'))
        return
    digest = json.loads(receipt.read_bytes())['sha256']
    if sha256_file(source) != digest:
        raise SystemExit('%s differs from its receipt; refused' % source)
    ingests = sealed_ingests(day)
    if len(ingests) != 1:
        results.append(dict(day=day, step='ingest', status='not linked', reason='%d sealed ingests of the day (%s); link '
                            'with ACTION=link once exactly one exists' % (len(ingests), [str(i) for i in ingests])))
    else:
        for name, path in ((FILE, source), (RECEIPT, receipt)):
            dest = ingests[0] / name
            if dest.exists():
                same = sha256_file(dest) == sha256_file(path)
                results.append(dict(day=day, step='ingest', file=str(dest), status='present' if same else 'REFUSED: a '
                                    'different file is already beside the ingest; not overwritten'))
                continue
            os.link(path, dest)
            results.append(dict(day=day, step='ingest', file=str(dest), status='linked'))
    for name, path in ((FILE, source), (RECEIPT, receipt)):
        key = S3_DAY.format(day=day, name=name)
        slot = url_map.get('put:' + key)
        if not slot:
            results.append(dict(day=day, step='s3', key=key, status='no upload slot presigned (already on S3, or not asked)'))
            continue
        r = subprocess.run(['curl', '-fsS', '--proto', '=https', '-X', 'PUT', '--upload-file', str(path), '--url', slot['url']])
        results.append(dict(day=day, step='s3', key=key, status='uploaded' if r.returncode == 0 else 'failed',
                            returncode=r.returncode))
    if brain:
        entry = Path(brain) / ('%s-external' % day)
        manifest = entry / 'MANIFEST.json'
        doc = dict(schema='FRANKIE_BOX_BRAIN_ATTACHMENT_V1', day=day, entry_kind='attachment',
                   note="Frankie's 13 historical data points of the day, ATTACHED by day key; not his reasoning, not read "
                        'into his corpus (the brain loader reads only cycle and lessons entries); every reader of the '
                        'ingest finds it by this key, the ingest directory or the S3 key',
                   attachments=[dict(name=FILE, sha256=digest, bytes=source.stat().st_size,
                                     s3_key=S3_DAY.format(day=day, name=FILE), s3_receipt_key=S3_DAY.format(day=day, name=RECEIPT),
                                     run_copy=str(source), ingest_copies=[str(i / FILE) for i in ingests])],
                   at=time.time())
        if manifest.is_file():
            old = json.loads(manifest.read_bytes())
            if any(a.get('sha256') == digest for a in old.get('attachments', [])):
                results.append(dict(day=day, step='brain', status='present', entry=str(entry)))
                return
            doc['attachments'] = old.get('attachments', []) + doc['attachments']
        entry.mkdir(parents=True, exist_ok=True)
        tmp = entry / 'MANIFEST.json.tmp'
        tmp.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding='utf-8')
        os.replace(tmp, manifest)
        results.append(dict(day=day, step='brain', status='listed', entry=str(entry)))
    else:
        results.append(dict(day=day, step='brain', status='no BRAIN given; listed here only'))


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--action', choices=('build', 'link'), required=True)
    p.add_argument('--code-root', required=True)
    p.add_argument('--markets-sha', required=True)
    p.add_argument('--days', required=True)
    p.add_argument('--run', required=True)
    p.add_argument('--history-run', required=True, help='the day_history GitHub run id (frankie/day_history/<id>)')
    p.add_argument('--map', default='')
    p.add_argument('--brain', default='')
    p.add_argument('--workers', type=int, default=2)
    a = p.parse_args()
    days = sorted({d for d in a.days.split(',') if d})
    if any(not (len(d) == 8 and d.isdigit()) for d in days):
        raise SystemExit('DAYS must be YYYYMMDD values')
    sys.path.insert(0, a.code_root)
    from research.kalshi.frankie_boss.operations.fetch_day_history import storage_prints_around
    url_map = json.loads(Path(a.map).read_bytes()) if a.map else {}
    run_dir = OUT / a.run
    history_prefix = 'frankie/day_history/%s' % a.history_run
    record = dict(schema='FRANKIE_DAY_EXTERNAL_RUN_V1', action=a.action, run=a.run, days=days, markets_sha=a.markets_sha,
                  history_prefix=history_prefix, at=time.time(), fetch=[], curve=[], built=[], attach=[])
    if a.action == 'build':
        if run_dir.exists():
            raise SystemExit('%s exists: a build RUN is fresh (ACTION=link reuses one)' % run_dir)
        src = run_dir / 'src'
        src.mkdir(parents=True)
        for day in days:
            prints = sorted({x['release_et'][:10] for x in storage_prints_around(ymd(day))})
            keys = wanted_keys(day, url_map, history_prefix, prints)
            print('### %s: %d objects to fetch' % (day, len(keys)), flush=True)
            fetch(keys, url_map, src, record['fetch'])
        curve = verify_curve(src, record['curve'])
        jobs = [dict(day=d, run_dir=str(run_dir), src=str(src), history_prefix=history_prefix, code_root=a.code_root,
                     markets_sha=a.markets_sha, run=a.run, curve_verification=curve) for d in days]
        with ProcessPoolExecutor(max_workers=max(1, min(a.workers, len(days)))) as pool:
            for r in pool.map(build_day, jobs):
                record['built'].append(r)
                print(json.dumps(r), flush=True)
    elif not run_dir.is_dir():
        raise SystemExit('%s is not an existing run' % run_dir)
    for day in days:
        attach(day, run_dir, url_map, a.brain, record['attach'])
    name = run_dir / ('run-%s-%d.json' % (a.action, int(time.time())))
    name.write_text(json.dumps(record, indent=1, sort_keys=True), encoding='utf-8')
    print('### RUN RECORD', name)
    print(json.dumps(dict(built=record['built'], attach=record['attach'],
                          fetch_failed=[f for f in record['fetch'] if f['status'] == 'failed'],
                          curve=[(c['key'], c['status']) for c in record['curve']]), indent=1), flush=True)
    bad = [f for f in record['fetch'] if f['status'] == 'failed'] + [x for x in record['attach'] if 'REFUSED' in x['status']]
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
