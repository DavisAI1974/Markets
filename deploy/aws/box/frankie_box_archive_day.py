"""Move a SEALED ingest day off a box into S3, verified, so its space can be reused (Greg, 2026-09-29: "as box space opens
up, clean trash and move important data to S3 before the space is refilled"). Called by frankie_box_archive_day.sh.

  plan     read-only: the sealed directory's every file (bytes, sha256, mode, mtime), directory and symlink; the S3 layout;
           the exact presign string for the upload dispatch; receipt action=plan
  upload   every slot PUT through the presigned map (MAP_URL); the bytes sent are hashed as they go and must equal the
           plan's; the archive manifest is the LAST object, written only when every data object is proven; receipt
  verify   every object read back by presigned GET (streamed, nothing written), per-object and per-file sha256 against the
           manifest, the object set exactly the manifest's; the local directory (if still here) compared by stat; receipt
  restore  the read path: every file downloaded into WORK/.archive-restore-<name>/, each sha256 checked, modes, mtimes,
           directories and symlinks as recorded, then renamed whole into WORK/<name> (create-only); receipt
There is NO delete action: removing the local directory is a separate later step on Greg's word.

Layout (s3://<bucket>/frankie/ingest/<day>/box-<directory name>/): objects/0000 .. objects/<N-1> then archive-manifest.json.
Each regular file is cut into 4 GiB pieces (pod_transfer.plan_parts; S3's single PUT limit is 5 GB); an empty file is one
empty object; files in sorted path order, pieces in offset order, one numbered slot per piece. Why numbered slots and not
one key per file name: the slot COUNT is all the workflow needs (presign putarchive:<prefix>:<N>, one short item), so a day
with thousands of files never overflows the dispatch input, and no file name can collide with the manifest. The manifest
maps every path to its pieces (index, key, offset, bytes, sha256) plus the whole-file sha256.
NO DATA DROPPED: every regular file, directory and symlink (its target recorded, never followed) is in the manifest; a
socket, fifo or device refuses the directory. Refused: no sealed ingestion-receipt.json of the named day, a journal whose
sha256 differs from its receipt, a deferred conformance not yet run (ALLOW_UNCONFORMED=1 overrides, recorded), a directory
a running process has open, Monday 20211004 (the gold standard: never touched), anything changed since the plan.
Nothing deleted, nothing overwritten (an S3 object already there is never rewritten: the presign step skips it and upload
proves it by GET against the plan before the manifest is written; every PUT is signed with If-None-Match: *, so S3 itself
refuses an overwrite). No credential here: every URL is presigned by the
runner. Stdlib only (pod_transfer is stdlib at import), loaded by path.
"""
import hashlib
import http.client
import json
import os
import re
import socket
import stat
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'research' / 'kalshi' / 'frankie_boss' / 'pod_root'))
import pod_transfer as T                  # noqa: E402  (the byte transport: 4 GiB pieces, presigned PUT/GET, retries)

ROOT = Path('/opt/frankie-box'); WORK = ROOT / 'work'; RECEIPTS = ROOT / 'receipts'
BUCKET = 'bento-568968024170-us-east-2-an'
INGEST_SCHEMA = 'BOSS_BLOCK_INGESTION_RECEIPT_V1'
MANIFEST_SCHEMA = 'FRANKIE_BOX_INGEST_ARCHIVE_V1'
RECEIPT_SCHEMA = 'FRANKIE_BOX_INGEST_ARCHIVE_RECEIPT_V1'
MANIFEST_NAME = 'archive-manifest.json'
NAME = re.compile(r'ingest-([0-9]{8})-[A-Za-z0-9_-]+')
GOLD = '20211004'
E = os.environ


def say(*a):
    print(*a, flush=True)


def refuse(why):
    say('REFUSED: ' + why)
    raise SystemExit(2)


def utc():
    return time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())


def instance_id():
    try:
        return Path('/var/lib/cloud/data/instance-id').read_text().strip()
    except OSError:
        return None


def target(directory):
    """(directory, day, S3 prefix) for WORK/ingest-<day>-<name>, validated."""
    d = Path(directory.rstrip('/'))
    m = NAME.fullmatch(d.name)
    if d.parent != WORK or not m:
        refuse('DIRECTORY must be %s/ingest-<YYYYMMDD>-<[A-Za-z0-9_-]+>' % WORK)
    if m.group(1) == GOLD:
        refuse('Monday 20211004 is the gold standard: never touched')
    return d, m.group(1), 'frankie/ingest/%s/box-%s/' % (m.group(1), d.name)


def sealed(d, day):
    """The day's ingestion receipt (the seal); refuses an unsealed or foreign directory."""
    if os.path.islink(d) or not d.is_dir():
        refuse('%s is not a directory on this box' % d)
    try:
        receipt = json.loads((d / 'ingestion-receipt.json').read_bytes())
    except (OSError, ValueError) as e:
        refuse('%s has no readable ingestion-receipt.json (unsealed): %s' % (d, e))
    bad = [k for k, ok in (('schema', receipt.get('schema') == INGEST_SCHEMA), ('trading_day', str(receipt.get('trading_day')) == day),
                           ('completion.json', (d / 'completion.json').is_file()),
                           ('journal_file', (d / str(receipt.get('journal_file'))).is_file())) if not ok]
    if bad:
        refuse('%s is not a sealed ingest of %s (%s)' % (d, day, ', '.join(bad)))
    if (d / str(receipt['journal_file'])).stat().st_size != receipt.get('journal_bytes'):
        refuse('the journal bytes differ from the receipt')
    unconformed = receipt.get('conformance') == 'deferred' and not (d / 'conformance.json').is_file()
    if unconformed and E.get('ALLOW_UNCONFORMED') != '1':
        refuse('the conformance is deferred and conformance.json is not written yet (a later conform would add a file the '
               'archive lacks): run the conform first, or ALLOW_UNCONFORMED=1')
    return dict(schema=receipt['schema'], trading_day=day, writer=receipt.get('writer'), journal_file=receipt['journal_file'],
                journal_sha256=receipt.get('journal_sha256'), journal_bytes=receipt.get('journal_bytes'),
                record_count=receipt.get('record_count'), journal_count=receipt.get('journal_count'),
                conformance=receipt.get('conformance'), conformance_json=(d / 'conformance.json').is_file(),
                receipt_sha256=T.sha256_file(d / 'ingestion-receipt.json'), unconformed_allowed=unconformed)


def open_by(d):
    """Every process holding a file under d open (fd, cwd or a mapping); [] = none. Reads /proc as root."""
    base, hits = str(d) + '/', []
    for p in Path('/proc').iterdir():
        if not p.name.isdigit() or int(p.name) == os.getpid():
            continue
        paths, cmd = set(), ''
        try:                                         # each source read on its own: a process that ends meanwhile is skipped
            fds = list((p / 'fd').iterdir())
        except OSError:
            fds = []
        for link in fds + [p / 'cwd']:
            try:
                paths.add(os.readlink(link))
            except OSError:
                pass
        try:
            paths.update(line.split(None, 5)[5].strip() for line in (p / 'maps').read_text().splitlines() if len(line.split(None, 5)) == 6)
            cmd = (p / 'cmdline').read_bytes().replace(b'\0', b' ').decode(errors='replace').strip()
        except OSError:
            pass
        mine = sorted(x for x in paths if x == str(d) or x.startswith(base))
        if mine:
            hits.append(dict(pid=int(p.name), cmd=cmd[:200], paths=mine[:5]))
    return hits


def not_open(d):
    hits = open_by(d)
    if hits:
        for h in hits:
            say('   open: pid %d %s %s' % (h['pid'], h['cmd'], h['paths']))
        refuse('%d running process(es) hold files under %s open' % (len(hits), d))


def walk(d):
    """(files, dirs, symlinks) under d, sorted; files carry bytes, mode, mtime_ns (no hash). Special files refuse."""
    files, dirs, links = [], [], []
    for base, subdirs, names in os.walk(d, followlinks=False):
        subdirs.sort()
        rel = Path(base).relative_to(d).as_posix()
        for name in sorted(subdirs + names):
            path = os.path.join(base, name)
            arc = name if rel == '.' else '%s/%s' % (rel, name)
            st = os.lstat(path)
            if stat.S_ISLNK(st.st_mode):
                links.append(dict(path=arc, target=os.readlink(path)))
            elif stat.S_ISDIR(st.st_mode):
                dirs.append(dict(path=arc, mode=stat.S_IMODE(st.st_mode)))
            elif stat.S_ISREG(st.st_mode):
                files.append(dict(path=arc, bytes=st.st_size, mode=stat.S_IMODE(st.st_mode), mtime_ns=st.st_mtime_ns))
            else:
                refuse('%s is not a regular file, directory or symlink (never skipped): mode %o' % (path, st.st_mode))
        subdirs[:] = [s for s in subdirs if not os.path.islink(os.path.join(base, s))]    # a linked directory: recorded, not followed
    return files, dirs, links


def layout(files, prefix):
    """Assign every file's pieces a numbered slot, in path then offset order."""
    i = 0
    for f in files:
        f['parts'] = []
        for offset, length in T.plan_parts(f['bytes']):
            f['parts'].append(dict(index=i, key='%sobjects/%04d' % (prefix, i), offset=offset, bytes=length))
            i += 1
    return i


def hash_file(d, f):
    """Whole-file and per-piece sha256 in one sequential read."""
    whole = hashlib.sha256()
    with open(d / f['path'], 'rb') as src:
        for p in f['parts']:
            h, n = hashlib.sha256(), p['bytes']
            while n:
                block = src.read(min(n, T.BLOCK))
                if not block:
                    raise IOError('%s ended early' % f['path'])
                h.update(block); whole.update(block); n -= len(block)
            p['sha256'] = h.hexdigest()
        if src.read(1):
            raise IOError('%s grew while hashed' % f['path'])
    f['sha256'] = whole.hexdigest()
    return f


def get_hash(url, expect):
    """sha256 of a presigned object, streamed (nothing written); retried whole."""
    error = None
    for attempt in range(6):
        try:
            conn, path = T._connection(url)
            conn.request('GET', path)
            r = conn.getresponse()
            if r.status != 200:
                error = 'HTTP %d' % r.status
                conn.close()
                if r.status in (403, 404):
                    break
                raise IOError(error)
            h, n = hashlib.sha256(), 0
            while block := r.read(T.BLOCK):
                h.update(block); n += len(block)
            conn.close()
            if n != expect:
                raise IOError('%d bytes, %d expected' % (n, expect))
            return h.hexdigest()
        except (OSError, http.client.HTTPException) as e:
            error = '%s: %s' % (type(e).__name__, e)
            time.sleep(min(60, 2 ** attempt))
    raise IOError('GET failed: %s' % error)


def slice_hash(path, offset, length):
    h = hashlib.sha256()
    with open(path, 'rb') as src:
        src.seek(offset)
        while length:
            block = src.read(min(length, T.BLOCK))
            if not block:
                raise IOError('%s ended early' % path)
            h.update(block); length -= len(block)
    return h.hexdigest()


def load_map():
    url = E.get('MAP_URL', '')
    if not re.match(r'https://[^/]+\.amazonaws\.com/', url):
        refuse('MAP_URL (the dispatch presign) is required')
    return json.loads(T.get_bytes(url))


def write_receipt(day, record):
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    path = RECEIPTS / ('archive-%s-%s.json' % (day, utc()))
    with open(path, 'x') as out:            # create-only
        json.dump(record, out, indent=1, sort_keys=True)
    say('RECEIPT %s' % path)
    return path


def base_record(action, d, day, prefix):
    return dict(schema=RECEIPT_SCHEMA, action=action, day=day, directory=str(d), bucket=BUCKET, prefix=prefix,
                instance=instance_id(), host=socket.gethostname(), markets_sha=E.get('MARKETS_SHA'), at=utc(), at_unix=int(time.time()))


def shape(files, dirs, links):
    """What must not change between plan and upload: every path with its bytes, mode and mtime; dirs; symlink targets."""
    return dict(files=[(f['path'], f['bytes'], f['mode'], f['mtime_ns']) for f in files],
                dirs=[(x['path'], x['mode']) for x in dirs], links=[(x['path'], x['target']) for x in links])


def plan(d, day, prefix, workers):
    seal = sealed(d, day)
    not_open(d)
    files, dirs, links = walk(d)
    n = layout(files, prefix)
    t0 = time.time()
    with ThreadPoolExecutor(workers) as ex:
        files = list(ex.map(lambda f: hash_file(d, f), files))
    journal = next(f for f in files if f['path'] == seal['journal_file'])
    if journal['sha256'] != seal['journal_sha256']:
        refuse('the journal sha256 %s differs from its receipt %s' % (journal['sha256'], seal['journal_sha256']))
    total = sum(f['bytes'] for f in files)
    say('### %s: %d files, %d bytes, %d directories, %d symlinks, %d data objects + %s (hashed in %.0f s)'
        % (d, len(files), total, len(dirs), len(links), n, MANIFEST_NAME, time.time() - t0))
    for f in files:
        say('   %s %d %s parts=%d' % (f['path'], f['bytes'], f['sha256'], len(f['parts'])))
    for x in links:
        say('   symlink %s -> %s' % (x['path'], x['target']))
    for x in dirs:
        say('   dir %s' % x['path'])
    presign = 'putarchive:%s/%s:%d getprefix:%s/%s' % (BUCKET, prefix, n, BUCKET, prefix)
    rec = dict(base_record('plan', d, day, prefix), ingestion=seal, files=files, dirs=dirs, symlinks=links, objects=n,
               file_count=len(files), bytes=total, presign=presign, hash_seconds=round(time.time() - t0, 1))
    write_receipt(day, rec)
    say('PRESIGN %s' % presign)
    say('upload dispatch: script=deploy/aws/box/frankie_box_archive_day.sh variables="ACTION=upload DIRECTORY=%s" '
        'presign="%s" presign_hours=6 timeout=10800' % (d, presign))
    return 0


def latest_plan(d, day):
    best = None
    for p in sorted(RECEIPTS.glob('archive-%s-*.json' % day)):
        try:
            r = json.loads(p.read_bytes())
        except (OSError, ValueError):
            continue
        if r.get('schema') == RECEIPT_SCHEMA and r.get('action') == 'plan' and r.get('directory') == str(d) \
                and (best is None or r['at_unix'] >= best[1]['at_unix']):
            best = (p, r)
    if best is None:
        refuse('no ACTION=plan receipt for %s under %s: plan first' % (d, RECEIPTS))
    return best


def upload(d, day, prefix, workers):
    seal = sealed(d, day)
    not_open(d)
    plan_path, p = latest_plan(d, day)
    files, dirs, links = walk(d)
    if shape(files, dirs, links) != shape(p['files'], p['dirs'], p['symlinks']) or seal != p['ingestion']:
        refuse('the directory changed since the plan %s: plan again' % plan_path)
    files = p['files']
    m = load_map()
    mkey = prefix + MANIFEST_NAME
    if mkey in m or 'put:' + mkey not in m:
        refuse('the map holds no upload slot for %s (the archive is complete, or the presign is not the plan\'s): %s'
               % (mkey, 'object exists: run ACTION=verify' if mkey in m else 'presign ' + p['presign']))
    slots = {k[4:] for k in m if k.startswith('put:' + prefix + 'objects/')} | {k for k in m if k.startswith(prefix + 'objects/')}
    want = {q['key'] for f in files for q in f['parts']}
    if slots != want:
        refuse('the presigned objects differ from the plan: %d missing, %d extra (presign %s)'
               % (len(want - slots), len(slots - want), p['presign']))
    jobs = [(f, q) for f in files for q in f['parts']]
    t0 = time.time()

    def one(job):
        f, q = job
        path = d / f['path']
        try:
            if 'put:' + q['key'] in m:
                slot = m['put:' + q['key']]
                sent = T.put_range(slot['url'], path, q['offset'], q['bytes'], headers=slot.get('headers'))
                return dict(index=q['index'], how='sent', sha256=sent, ok=sent == q['sha256'])
            have = m[q['key']]               # already in S3 (an earlier attempt): proven by GET, never rewritten
            got = get_hash(have['url'], q['bytes']) if have['bytes'] == q['bytes'] else 'bytes %d' % have['bytes']
            local = slice_hash(path, q['offset'], q['bytes'])
            return dict(index=q['index'], how='present', sha256=got, local_sha256=local, ok=got == q['sha256'] == local)
        except (OSError, http.client.HTTPException) as e:     # one piece's failure is recorded; the next dispatch resumes
            return dict(index=q['index'], how='failed', sha256='%s: %s' % (type(e).__name__, e), ok=False)

    results = []
    with ThreadPoolExecutor(workers) as ex:
        for r in ex.map(one, jobs):
            results.append(r)
            say('   object %04d %s %s' % (r['index'], r['how'], 'ok' if r['ok'] else 'DIFFERS %s' % r['sha256']))
    bad = [r for r in results if not r['ok']]
    after = walk(d)
    changed = shape(*after) != shape(p['files'], p['dirs'], p['symlinks'])
    rec = dict(base_record('upload', d, day, prefix), plan_receipt=str(plan_path), objects=results,
               sent=sum(1 for r in results if r['how'] == 'sent'), present=sum(1 for r in results if r['how'] == 'present'),
               bytes=sum(f['bytes'] for f in files), seconds=round(time.time() - t0, 1), changed_during_upload=changed)
    if bad or changed:
        rec.update(status='refused', reason='%d object(s) differ from the plan%s; NO manifest written'
                   % (len(bad), ', the directory changed during the upload' if changed else ''))
        write_receipt(day, rec)
        refuse(rec['reason'])
    manifest = dict(schema=MANIFEST_SCHEMA, day=day, directory=str(d), name=d.name, bucket=BUCKET, prefix=prefix,
                    instance=instance_id(), host=socket.gethostname(), ingestion=seal, files=files, dirs=dirs, symlinks=links,
                    file_count=len(files), bytes=sum(f['bytes'] for f in files), objects=len(jobs),
                    plan_receipt=str(plan_path), markets_sha=E.get('MARKETS_SHA'), created=utc())
    body = json.dumps(manifest, indent=1, sort_keys=True).encode()
    T.put_bytes(m['put:' + mkey]['url'], body, headers=m['put:' + mkey].get('headers'))   # If-None-Match: * (signed)
    rec.update(status='uploaded', manifest_key=mkey, manifest_sha256=hashlib.sha256(body).hexdigest(), manifest_bytes=len(body))
    write_receipt(day, rec)
    say('UPLOADED %s: %d files, %d bytes, %d objects (%d sent, %d already there) + %s sha256 %s in %.0f s'
        % (d, len(files), manifest['bytes'], len(jobs), rec['sent'], rec['present'], mkey, rec['manifest_sha256'], rec['seconds']))
    say('verify dispatch: script=deploy/aws/box/frankie_box_archive_day.sh variables="ACTION=verify DIRECTORY=%s" '
        'presign="getprefix:%s/%s" presign_hours=6 timeout=10800' % (d, BUCKET, prefix))
    return 0


def read_manifest(prefix, d, m):
    mkey = prefix + MANIFEST_NAME
    if mkey not in m:
        refuse('no %s in the map (not archived, or the dispatch lacks presign getprefix:%s/%s)' % (mkey, BUCKET, prefix))
    body = T.get_bytes(m[mkey]['url'])
    man = json.loads(body)
    if man.get('schema') != MANIFEST_SCHEMA or man.get('name') != d.name or man.get('prefix') != prefix:
        refuse('%s is not the archive manifest of %s' % (mkey, d.name))
    return man, hashlib.sha256(body).hexdigest()


def verify(d, day, prefix, workers):
    m = load_map()
    man, msha = read_manifest(prefix, d, m)
    problems = []
    listed = {k for k in m if k.startswith(prefix) and not k.startswith('put:')}
    want = {q['key'] for f in man['files'] for q in f['parts']} | {prefix + MANIFEST_NAME}
    problems += [dict(key=k, problem='in S3, not in the manifest') for k in sorted(listed - want)]
    problems += [dict(key=k, problem='in the manifest, not in S3') for k in sorted(want - listed)]
    t0 = time.time()

    def one(f):
        whole, out = hashlib.sha256(), []
        for q in f['parts']:
            o = m.get(q['key'])
            if o is None:
                return [dict(path=f['path'], problem='object %s missing' % q['key'])]
            if o['bytes'] != q['bytes']:
                return [dict(path=f['path'], problem='object %s bytes %d, manifest %d' % (q['key'], o['bytes'], q['bytes']))]
            h, n = hashlib.sha256(), 0
            try:
                conn, path = T._connection(o['url'])
                conn.request('GET', path)
                r = conn.getresponse()
                if r.status != 200:
                    conn.close()
                    return [dict(path=f['path'], problem='object %s GET HTTP %d' % (q['key'], r.status))]
                while block := r.read(T.BLOCK):
                    h.update(block); whole.update(block); n += len(block)
                conn.close()
            except (OSError, http.client.HTTPException) as e:   # recorded as a problem; verify is re-run, never assumed
                return [dict(path=f['path'], problem='object %s GET %s: %s' % (q['key'], type(e).__name__, e))]
            if n != q['bytes'] or h.hexdigest() != q['sha256']:
                out.append(dict(path=f['path'], problem='object %s read %d bytes sha256 %s, manifest %d %s'
                                % (q['key'], n, h.hexdigest(), q['bytes'], q['sha256'])))
        if not out and whole.hexdigest() != f['sha256']:
            out.append(dict(path=f['path'], problem='file sha256 %s, manifest %s' % (whole.hexdigest(), f['sha256'])))
        say('   %s %d %s' % (f['path'], f['bytes'], 'ok' if not out else 'DIFFERS'))
        return out

    with ThreadPoolExecutor(workers) as ex:
        for out in ex.map(one, man['files']):
            problems += out
    local = 'absent'
    if d.is_dir():                                   # the source still here: compared by stat (it was hashed at plan and upload)
        files, dirs, links = walk(d)
        same = shape(files, dirs, links) == shape(man['files'], man['dirs'], man['symlinks'])
        local = 'same' if same else 'DIFFERS'
        if not same:
            problems.append(dict(path=str(d), problem='the local directory differs from the manifest (paths, bytes, modes or mtimes)'))
    uploads = []
    for p in sorted(RECEIPTS.glob('archive-%s-*.json' % day)):
        try:
            r = json.loads(p.read_bytes())
        except (OSError, ValueError):
            continue
        if r.get('action') == 'upload' and r.get('status') == 'uploaded' and r.get('prefix') == prefix:
            uploads.append(r.get('manifest_sha256'))
    if uploads and msha not in uploads:
        problems.append(dict(key=prefix + MANIFEST_NAME, problem='manifest sha256 %s is not the one this box uploaded %s' % (msha, uploads)))
    ok = not problems
    rec = dict(base_record('verify', d, day, prefix), status='verified' if ok else 'DIFFERS', manifest_sha256=msha,
               files_checked=len(man['files']), bytes_checked=sum(f['bytes'] for f in man['files']), objects=len(want),
               local=local, upload_receipts_on_box=len(uploads), problems=problems, seconds=round(time.time() - t0, 1))
    write_receipt(day, rec)
    for x in problems:
        say('   PROBLEM %s' % json.dumps(x, sort_keys=True))
    say('%s %s: %d files, %d bytes, %d objects read back (local %s)'
        % ('VERIFIED' if ok else 'DIFFERS', prefix, len(man['files']), rec['bytes_checked'], len(want), local))
    return 0 if ok else 3


def other_sealed(day):
    out = []
    for r in sorted(WORK.glob('ingest-*/ingestion-receipt.json')):
        try:
            x = json.loads(r.read_bytes())
        except (OSError, ValueError):
            continue
        if x.get('schema') == INGEST_SCHEMA and str(x.get('trading_day')) == day:
            out.append(str(r.parent))
    return out


def restore(d, day, prefix, workers):
    if os.path.lexists(d):
        refuse('%s exists (never overwritten)' % d)
    have = other_sealed(day)
    if have:
        refuse('the day already has a sealed ingest on this box: %s (a duplicate declines the run)' % ', '.join(have))
    m = load_map()
    man, msha = read_manifest(prefix, d, m)
    missing = [q['key'] for f in man['files'] for q in f['parts'] if q['key'] not in m]
    if missing:
        refuse('%d object(s) of the manifest are not in the map: %s' % (len(missing), missing[:5]))
    stage = WORK / ('.archive-restore-' + d.name)       # a dot name: no ingest-* glob sees it
    free = os.statvfs(WORK).f_bavail * os.statvfs(WORK).f_frsize
    if free < man['bytes'] + T.CHUNK_BYTES:
        refuse('%d bytes free under %s, %d needed (the day + one piece)' % (free, WORK, man['bytes'] + T.CHUNK_BYTES))
    stage.mkdir(exist_ok=True)
    for x in man['dirs']:
        (stage / x['path']).mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    def one(f):
        path = stage / f['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size == f['bytes'] and T.sha256_file(path) == f['sha256']:
            return f['path'], 'present', None             # an earlier attempt's finished file
        parts = [dict(url=m[q['key']]['url'], bytes=q['bytes']) for q in f['parts']]
        n, digest = T.get_parts_to_file(parts, path)
        if n != f['bytes'] or digest != f['sha256']:
            return f['path'], 'DIFFERS', '%d bytes sha256 %s, manifest %d %s' % (n, digest, f['bytes'], f['sha256'])
        return f['path'], 'restored', None

    results = []
    with ThreadPoolExecutor(workers) as ex:
        for r in ex.map(one, man['files']):
            results.append(r)
            say('   %s %s%s' % (r[1], r[0], (' ' + r[2]) if r[2] else ''))
    bad = [r for r in results if r[1] == 'DIFFERS']
    rec = dict(base_record('restore', d, day, prefix), manifest_sha256=msha, staged=str(stage), files=len(results),
               bytes=man['bytes'], problems=[dict(path=r[0], problem=r[2]) for r in bad], seconds=round(time.time() - t0, 1))
    if bad:
        write_receipt(day, dict(rec, status='DIFFERS'))
        refuse('%d file(s) differ from the manifest; the staging directory %s is kept' % (len(bad), stage))
    for x in man['symlinks']:
        if not os.path.lexists(stage / x['path']):
            os.symlink(x['target'], stage / x['path'])
    for f in man['files']:
        os.chmod(stage / f['path'], f['mode'])
        os.utime(stage / f['path'], ns=(f['mtime_ns'], f['mtime_ns']))
    for x in sorted(man['dirs'], key=lambda x: -x['path'].count('/')):
        os.chmod(stage / x['path'], x['mode'])
    files, dirs, links = walk(stage)
    if shape(files, dirs, links) != shape(man['files'], man['dirs'], man['symlinks']):
        write_receipt(day, dict(rec, status='DIFFERS', reason='the staged tree differs from the manifest'))
        refuse('the staged tree differs from the manifest; %s is kept' % stage)
    if other_sealed(day) or os.path.lexists(d):
        refuse('a sealed ingest of the day or the target appeared meanwhile; %s is kept' % stage)
    os.rename(stage, d)                                 # the whole directory at once, create-only
    write_receipt(day, dict(rec, status='restored', directory=str(d)))
    say('RESTORED %s: %d files, %d bytes, every sha256 equal to the manifest' % (d, len(results), man['bytes']))
    return 0


def main():
    action = E.get('ACTION', 'plan')
    workers = int(E.get('PARALLEL', '4'))
    d, day, prefix = target(E.get('DIRECTORY', ''))
    say('### archive %s %s -> s3://%s/%s (parallel %d)' % (action, d, BUCKET, prefix, workers))
    free = os.statvfs(WORK)
    say('### free under %s: %d bytes' % (WORK, free.f_bavail * free.f_frsize))
    fn = dict(plan=plan, upload=upload, verify=verify, restore=restore).get(action)
    if fn is None:
        refuse('ACTION must be plan, upload, verify or restore')
    return fn(d, day, prefix, workers)


if __name__ == '__main__':
    sys.exit(main())
