"""Frankie's 13 points, attached to each trading day (FRANKIE_DAY_EXTERNAL_V1), on Frankie's box. Greg, 2026-09-29:
"everyone who sees his ingest should see these data points too"; "we should somehow still attach whatever doesn't get
run with this tues and wed to their historical data". Builder and reader:
research/kalshi/frankie_boss/operations/frankie_day_external.py. Plan: HISTORICAL_DATA_PLAN_20260929.md.

ACTION=build, per day of DAYS:
  1. fetch, through the presigned map (MAP_URL), the day-history objects the day needs (frankie/day_history/<run>/...:
     calendar, cot store, storage, weather obs of the day's months, the MOS raw files covering it, the day's EIA-930
     files, the as_printed storage report and street estimate (fetch_day_history.py as-printed; a family of its own,
     usually HISTORY_FAMILY_RUNS as_printed=<id>), manifest.json) and the curve's native files of the day's two UTC
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
Parallel (Greg 2026-10-07, every piece uses the lane's CPUs): the objects of ALL the days are fetched once (the union of
the days' keys, each key once) through FETCH_STREAMS concurrent presigned GETs (default 16; S3 scales by parallel
requests); the curve files are hashed by the lane's CPUs side by side; the days are built side by side, one process per
day, WORKERS of them (0 or unset: every CPU this process may run on, os.sched_getaffinity). Values, hashes, the receipt
and the 99 mapping are the same as a serial run: only the order of the work changes, and listings are sorted by key.
Every day file carries Frankie's 13 points mapped to the 99 (POINT_REGISTRY_MAP of the builder, closest entry with its
reason; Greg 2026-10-07) and every row one reader stamp, published_ns = max(event_time_ns, publication), a row with no
event time of its own at 14:00 ET of the trading day; the receipt repeats the map, the rule and the code sha256s.
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

BOX = Path('/opt/frankie-box')
WORK = BOX / 'work'
OUT = WORK / 'day-external'
CURVE = 'nymex/ng_fut_parent_v0'
S3_DAY = 'frankie/day_external/{day}/{name}'
FILE, RECEIPT = 'day-external.json', 'day-external-receipt.json'
RECEIPT_SCHEMA = 'FRANKIE_DAY_EXTERNAL_RECEIPT_V1'
CODE_FILES = ('research/kalshi/frankie_boss/operations/frankie_day_external.py',
              'research/kalshi/frankie_boss/operations/fetch_day_history.py', 'deploy/aws/box/frankie_box_day_external.py')


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 24), b''):
            h.update(block)
    return h.hexdigest()


def _lane_pin():
    """frankie_box_lane_pin (the shared lane placement), beside this file."""
    try:
        import frankie_box_lane_pin as LP
    except ImportError:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import frankie_box_lane_pin as LP
    return LP


def lane_cpus():
    """How many CPUs the held lane has (FRANKIE_LANE_CPUS / FRANKIE_BOOKED_CPUS within this process's affinity, else the
    affinity: frankie_box_lane_pin.lane_cpus), else os.cpu_count()."""
    try:
        return max(1, len(_lane_pin().lane_cpus()))
    except Exception:  # noqa: BLE001
        return max(1, os.cpu_count() or 1)


def ymd(day):
    return dt.date(int(day[:4]), int(day[4:6]), int(day[6:]))


# the builder's families (Build.FAMILIES): 'consensus' is no longer read; its captures reach the day file through the
# as_printed family (fetch_day_history.py as-printed), values only
FAMILIES = ('calendar', 'cot', 'storage', 'weather_obs', 'mos', 'eia930', 'as_printed')


def family_prefixes(history_prefix, eia930_prefix=None, overrides=None):
    """family -> the day_history prefix it is read from: history_prefix, except eia930 (eia930_prefix) and overrides."""
    fam = {f: history_prefix for f in FAMILIES}
    if eia930_prefix:
        fam['eia930'] = eia930_prefix
    fam.update({f: v for f, v in (overrides or {}).items() if f in fam and v})
    return fam


def wanted_keys(day, keys, history_prefix, prints, eia930_prefix=None, overrides=None):
    """The keys of the map one trading day needs. A family taken from another day_history run (eia930_prefix, the
    overrides) is read from that run only: its files, its receipt, the run's manifest; never from history_prefix."""
    d = ymd(day)
    fam_of = family_prefixes(history_prefix, eia930_prefix, overrides)
    prefixes = sorted(set(fam_of.values()) | {history_prefix}, key=len, reverse=True)
    months = {(d - dt.timedelta(days=k)).strftime('%Y%m') for k in range(0, 12)}
    parts = [(d - dt.timedelta(days=1)).strftime('%Y%m%d'), day]
    out = []
    for k in keys:
        if k.startswith('put:'):
            continue
        prefix = next((x for x in prefixes if k.startswith(x + '/')), None)
        if prefix is not None:
            rel = k[len(prefix) + 1:]
            fam = rel.split('/', 1)[0]
            name = rel.rsplit('/', 1)[-1]
            if rel == 'manifest.json':
                out.append(k)
            elif fam_of.get(fam) != prefix:
                continue
            elif rel.endswith('/receipt.json') or fam in ('calendar', 'storage', 'as_printed'):
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


FETCH_STREAMS = int(os.environ.get('FETCH_STREAMS') or 16)   # concurrent object GETs (S3 guidance: parallel requests)
# A large object (the curve's MBO/statistics partitions) is pulled as concurrent byte-range GETs of the same presigned URL,
# each range written at its offset into <dest>.part (aws-storage skill, S3 byte-range fetches: 8-16 MB ranges; the
# ingest fetch's and the journal pull's pattern, frankie_box_ingest_block.sh). Small objects keep the one curl stream.
# The bytes land at the same offsets: the size check here and the curve manifest sha256 check (verify_curve) and the
# history manifest check (the builder) are unchanged. RANGE_STREAMS=1 restores the one-stream download.
RANGE_BYTES = 16 << 20
RANGED_ABOVE = 64 << 20
RANGE_STREAMS = int(os.environ.get('RANGE_STREAMS') or 15)


def _ranged_get(url, part, size, streams=None):
    """0 when every range of [0, size) arrived whole (HTTP 206, exact length) and was written at its offset, else 1."""
    import random
    import urllib.request
    streams = max(1, streams or RANGE_STREAMS)
    fd = os.open(str(part), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        os.ftruncate(fd, size)

        def one(i):
            start, end = i * RANGE_BYTES, min(size, (i + 1) * RANGE_BYTES) - 1
            for attempt in range(6):
                try:
                    request = urllib.request.Request(url, headers={'Range': 'bytes=%d-%d' % (start, end)})
                    with urllib.request.urlopen(request, timeout=120) as response:
                        if response.status != 206:
                            return False
                        data = response.read()
                    if len(data) == end - start + 1:
                        os.pwrite(fd, data, start)
                        return True
                except OSError as error:
                    print('   retry %d range %d of %s: %s' % (attempt + 1, i, part.name, error), flush=True)
                time.sleep(min(60, 5 * (attempt + 1)) * (0.5 + random.random()))   # backoff with jitter (S3 503 SlowDown)
            return False
        with ThreadPoolExecutor(streams) as pool:
            ok = all(pool.map(one, range((size + RANGE_BYTES - 1) // RANGE_BYTES)))
        os.fsync(fd)
    finally:
        os.close(fd)
    return 0 if ok else 1


def _fetch_one(k, url_map, src):
    """One object of the day history through its presigned GET (curl, retries; byte ranges above RANGED_ABOVE); its
    listing entry."""
    dest = src / k
    entry = url_map[k]
    if dest.is_file() and dest.stat().st_size == entry.get('bytes'):
        return dict(key=k, status='present')
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = Path(str(dest) + '.part')
    size = entry.get('bytes')
    started = time.time()
    if isinstance(size, int) and size > RANGED_ABOVE and RANGE_STREAMS > 1:
        if part.exists():
            part.unlink()                        # a stale partial from an interrupted one-stream GET; refetched whole
        returncode, transport = _ranged_get(entry['url'], part, size), 'ranged-%d' % RANGE_STREAMS
    else:
        returncode = subprocess.run(['curl', '-fsS', '--proto', '=https', '-L', '--retry', '5', '--retry-delay', '5',
                                     '-o', str(part), '--url', entry['url']]).returncode
        transport = 'curl'
    if returncode != 0 or not part.is_file() or part.stat().st_size != size:
        return dict(key=k, status='failed', returncode=returncode, transport=transport)
    os.replace(part, dest)
    return dict(key=k, status='downloaded', bytes=size, transport=transport, seconds=round(time.time() - started, 1))


def fetch(keys, url_map, src, listing, workers=FETCH_STREAMS):
    """Every key once, `workers` presigned GETs at a time (S3 serves parallel requests; one GET per object at a time was
    the stage's wall clock); the listing is sorted by key whatever order the GETs finish in."""
    keys = sorted(set(keys))
    out = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(keys) or 1))) as pool:
        futures = [pool.submit(_fetch_one, k, url_map, src) for k in keys]
        for i, fut in enumerate(as_completed(futures), 1):
            out.append(fut.result())
            try:                                 # the stage heartbeat (frankie_box_stage_progress); never changes the stage
                import frankie_box_stage_progress as _SP
                _SP.report_phase('external: fetching day-history objects', units_done=i, units_total=len(keys),
                                 unit='objects', every=10)
            except Exception:  # noqa: BLE001
                pass
    listing.extend(sorted(out, key=lambda x: x['key']))


def verify_curve(src, listing, workers=None):
    """Each curve native file against the curve pull's manifests (key -> sha256); the files are hashed side by side by
    the lane's CPUs (hashlib releases the GIL), the result is in path order as before."""
    named = {}
    for m in glob.glob(str(src / CURVE / '*' / 'manifests' / '*.json')):
        for o in json.loads(Path(m).read_bytes()).get('objects', []):
            named[o['key']] = o['sha256']
    out = []
    paths = sorted(glob.glob(str(src / CURVE / '*' / 'native' / '*.dbn.zst')))
    with _lane_pin().executor('thread', max(1, min(workers or lane_cpus(), len(paths) or 1))) as pool:
        digests = list(pool.map(sha256_file, paths))       # each hashing thread pinned to its lane CPU; path order kept
    for p, have in zip(paths, digests):
        key = str(Path(p).relative_to(src))
        want = named.get(key)
        status = 'verified' if want == have else ('unverified: no manifest names it' if want is None else 'MISMATCH')
        out.append(dict(key=key, sha256=have, status=status))
        if status == 'MISMATCH':
            raise SystemExit('%s differs from its curve manifest sha256; refused' % key)
    listing.extend(out)
    return out


def build_day(job):
    sys.path.insert(0, job['code_root'])
    from research.kalshi.frankie_boss.operations.frankie_day_external import (Build, check_day_file, POINT_REGISTRY_MAP,
                                                                              DEFAULT_PLACEMENT_ET, DEFAULT_PLACEMENT_NOTE)
    day, run_dir = job['day'], Path(job['run_dir'])
    target = run_dir / day
    target.mkdir(parents=True, exist_ok=False)
    t0 = time.time()
    body = Build(job['src'], job['history_prefix'], day, job.get('eia930_prefix'), job.get('overrides')).run(with_curve=True, src_curve=str(Path(job['src']) / CURVE))
    check_day_file(body)
    raw = json.dumps(body, separators=(',', ':'), sort_keys=True).encode()
    with open(target / FILE, 'xb') as f:
        f.write(raw)
    receipt = dict(schema=RECEIPT_SCHEMA, trading_day=day, file=FILE, bytes=len(raw),
                   sha256=hashlib.sha256(raw).hexdigest(), s3_key=S3_DAY.format(day=day, name=FILE),
                   s3_receipt_key=S3_DAY.format(day=day, name=RECEIPT), markets_sha=job['markets_sha'], run=job['run'],
                   history_prefix=job['history_prefix'], eia930_history_prefix=job.get('eia930_prefix') or job['history_prefix'],
                   family_history_prefixes=family_prefixes(job['history_prefix'], job.get('eia930_prefix'),
                                                           job.get('overrides')),
                   built_seconds=round(time.time() - t0, 1),
                   points={k: len(v['rows']) for k, v in body['points'].items()}, missing=body['missing'],
                   inputs=body['inputs'], curve_verification=job['curve_verification'],
                   reader='research/kalshi/frankie_boss/operations/frankie_day_external.py AsOfReader',
                   guard='time only: every row has published_ns < halt_ns (checked before writing)',
                   point_registry_map=POINT_REGISTRY_MAP,
                   reader_stamp_rule='published_ns = max(event_time_ns, publication); a row with no event time of its '
                                     'own sits at %02d:%02d ET of the trading day (%s) unless published later'
                                     % (DEFAULT_PLACEMENT_ET + (DEFAULT_PLACEMENT_NOTE,)),
                   point_mappings={k: dict(registry_entries=v.get('registry_entries'), mapping=v.get('registry_mapping'),
                                           event_time_basis=v.get('event_time_basis'), rows=len(v['rows']))
                                   for k, v in body['points'].items()},
                   code_sha256={rel: sha256_file(Path(job['code_root']) / rel) for rel in CODE_FILES})
    (target / RECEIPT).write_text(json.dumps(receipt, indent=1, sort_keys=True), encoding='utf-8')
    return dict(day=day, path=str(target / FILE), sha256=receipt['sha256'], bytes=len(raw), points=receipt['points'],
                missing=len(body['missing']))


def _set_aside_day(job):
    """Before a day whose builder process died is built again: its half-built <run>/<day>/ directory (build_day creates
    it exclusively) is renamed <day>.lost-<ms>, never deleted, so the redo builds the day from nothing."""
    target = Path(job['run_dir']) / job['day']
    if target.exists():
        os.replace(target, target.with_name('%s.lost-%d' % (job['day'], int(time.time() * 1000))))


def sealed_ingests(day):
    found = []
    # the box's own ingests (ingest-<day>-ingest-*) and the GitHub-runner ingests pulled onto the box
    # (ingest-<day>-gh-*); a pulled directory counts once it carries completion.json (a partial pull is not sealed)
    rs = sorted(glob.glob(str(WORK / ('ingest-%s-ingest-*' % day) / 'ingestion-receipt.json')))
    rs += sorted(r for r in glob.glob(str(WORK / ('ingest-%s-gh-*' % day) / 'ingestion-receipt.json'))
                 if (Path(r).parent / 'completion.json').is_file())
    for r in rs:
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
    p.add_argument('--eia930-history-run', default='', help='optional day_history run id the eia930 family is read from')
    p.add_argument('--family-history-runs', default='', help='optional family=<run id>,... read from other day_history runs')
    p.add_argument('--map', default='')
    p.add_argument('--brain', default='')
    p.add_argument('--workers', type=int, default=0, help='days built side by side (0: every CPU of the lane)')
    p.add_argument('--fetch-workers', type=int, default=FETCH_STREAMS, help='presigned GETs at a time (FETCH_STREAMS)')
    a = p.parse_args()
    days = sorted({d for d in a.days.split(',') if d})
    workers = a.workers if a.workers > 0 else lane_cpus()
    if any(not (len(d) == 8 and d.isdigit()) for d in days):
        raise SystemExit('DAYS must be YYYYMMDD values')
    sys.path.insert(0, a.code_root)
    from research.kalshi.frankie_boss.operations.fetch_day_history import storage_prints_around
    url_map = json.loads(Path(a.map).read_bytes()) if a.map else {}
    run_dir = OUT / a.run
    history_prefix = 'frankie/day_history/%s' % a.history_run
    eia930_prefix = 'frankie/day_history/%s' % (a.eia930_history_run or a.history_run)
    overrides = {}
    for item in [x for x in a.family_history_runs.split(',') if x]:
        fam, _, rid = item.partition('=')
        if fam not in FAMILIES or not rid.isalnum():
            raise SystemExit('--family-history-runs: family=<run id> (letters and digits) with a family of %s' % (FAMILIES,))
        overrides[fam] = 'frankie/day_history/%s' % rid
    record = dict(schema='FRANKIE_DAY_EXTERNAL_RUN_V1', action=a.action, run=a.run, days=days, markets_sha=a.markets_sha,
                  workers=workers, fetch_workers=a.fetch_workers,
                  history_prefix=history_prefix, eia930_history_prefix=eia930_prefix,
                  family_history_prefixes=family_prefixes(history_prefix, eia930_prefix, overrides), at=time.time(), fetch=[], curve=[], built=[], attach=[])
    if a.action == 'build':
        if run_dir.exists():
            raise SystemExit('%s exists: a build RUN is fresh (ACTION=link reuses one)' % run_dir)
        src = run_dir / 'src'
        src.mkdir(parents=True)
        union = set()
        for day in days:
            prints = sorted({x['release_et'][:10] for x in storage_prints_around(ymd(day))})
            keys = wanted_keys(day, url_map, history_prefix, prints, eia930_prefix, overrides)
            print('### %s: %d objects needed' % (day, len(keys)), flush=True)
            union.update(keys)
        print('### %d distinct objects for %d days, %d GETs at a time' % (len(union), len(days), a.fetch_workers), flush=True)
        fetch(union, url_map, src, record['fetch'], a.fetch_workers)
        curve = verify_curve(src, record['curve'], workers)
        jobs = [dict(day=d, run_dir=str(run_dir), src=str(src), history_prefix=history_prefix, eia930_prefix=eia930_prefix,
                     overrides=overrides, code_root=a.code_root,
                     markets_sha=a.markets_sha, run=a.run, curve_verification=curve) for d in days]
        record['cpu_placement'] = _lane_pin().record(max(1, min(workers, len(days))),
                                                     what='day builders, one pinned process per day; curve hashing threads')
        record['cpu_placement']['pool_recovery'] = dict(worker_deaths=[], redone=[])
        # in day order whatever order they finish; pinned; a dead builder's day is set aside (never deleted) and built
        # again, never a hang or a stopped stage (frankie_box_lane_pin.ordered_map)
        for _, r in _lane_pin().ordered_map(build_day, jobs, max(1, min(workers, len(days))), on_retry=_set_aside_day,
                                            report=record['cpu_placement']['pool_recovery']):
            record['built'].append(r)
            print(json.dumps(r), flush=True)
            try:                                     # the stage heartbeat (frankie_box_stage_progress); never changes the stage
                import frankie_box_stage_progress as _SP
                _SP.report_phase('external: day files built', units_done=len(record['built']), units_total=len(jobs), unit='days')
            except Exception:  # noqa: BLE001
                pass

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
