"""Small state exchange through the existing controller; journals/ROOT directories remain on their owner.

The SSM instance role has no S3/SendCommand grants. Workers use controller-issued presigned mailboxes,
and the controller delivers requests to the main box. Only the main box owns queue/claim mutations.
"""
import base64
import fcntl
import hashlib
import json
import os
import time
import uuid
import urllib.request
import urllib.error
from pathlib import Path

BRAIN = Path('/opt/frankie-box/brain')
STATE = Path('/opt/frankie-box/work/lane-state')


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.pending')
    with open(tmp, 'w') as handle:
        handle.write(json.dumps(body, sort_keys=True, indent=1) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def pack_file(path):
    p = Path(path)
    raw = p.read_bytes()
    return dict(path=str(p), sha256=digest(raw), bytes=len(raw), data=base64.b64encode(raw).decode())


def restore_file(rec, roots):
    p = Path(rec['path'])
    if '..' in p.parts or not any(p.is_relative_to(r) for r in roots):
        raise ValueError('state path outside permitted roots: %s' % p)
    if any(part.is_symlink() for part in (p, *p.parents)):
        raise ValueError('state path contains a symbolic link: %s' % p)
    raw = base64.b64decode(rec['data'], validate=True)
    if len(raw) != rec['bytes'] or digest(raw) != rec['sha256']:
        raise ValueError('state bytes/hash differ: %s' % p)
    if p.exists() and p.read_bytes() == raw:
        return
    if p.exists() and p.name != 'MANIFEST.json' and p.name != 'index.json':
        raise ValueError('different retained state at %s; not overwritten' % p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + '.incoming')
    tmp.write_bytes(raw)
    os.replace(tmp, p)


def snapshot(brain=BRAIN, owner=None):
    """Exact generated knowledge; raw/digest sources stay local as owner-qualified pointers, without truncation."""
    import frankie_box_brain as BR
    owner = owner or os.environ.get('FRANKIE_LANE_OWNER', 'main')
    files, pointers = [], []
    for _, manifest, directory in BR.entries_before(brain, 'snapshot'):
        # Packaging records are evidence locations, not fabricated lessons.
        for e in manifest.get('entries', []):
            if not e.get('include'):
                continue  # host-only grades/answer keys are never shared as learner knowledge
            p = directory / e['name']
            if not p.is_file():
                raise FileNotFoundError('published knowledge source missing: %s' % p)
            if p.stat().st_size != e['bytes'] or BR._file_sha256(p) != e['sha256']:
                raise ValueError('published knowledge source differs from manifest: %s' % p)
            if e.get('kind') == 'derivation digest' or p.name.startswith('derivation-digest'):
                pointers.append(dict(owner=owner, path=str(p), bytes=p.stat().st_size, sha256=BR._file_sha256(p)))
                continue
            files.append(pack_file(p))
        # Publish a separate transport manifest: never rewrite the source brain manifest.
        published = dict(manifest, entries=[e for e in manifest.get('entries', [])
                                             if any(f['path'] == str(directory / e['name']) for f in files)])
        raw = (json.dumps(published, sort_keys=True, indent=1) + '\n').encode()
        files.append(dict(path=str(directory / 'MANIFEST.json'), bytes=len(raw), sha256=digest(raw),
                          data=base64.b64encode(raw).decode()))
    school = Path(brain) / 'school'
    for p in sorted(school.glob('*.json')):
        files.append(pack_file(p))
    version = digest(json.dumps(dict(files=[(f['path'], f['sha256']) for f in files],
                                    pointers=pointers), sort_keys=True).encode())
    return dict(owner=owner, version=version, files=files, large_source_pointers=pointers)


def merge_snapshot(doc, brain=BRAIN):
    """Imported entries use their own namespace; owner's canonical brain entries are never overwritten."""
    owner = digest(doc['owner'].encode())
    version = digest(json.dumps(dict(files=[(f['path'], f['sha256']) for f in doc['files']],
                                    pointers=doc['large_source_pointers']), sort_keys=True).encode())
    if version != doc['version']:
        raise ValueError('knowledge version does not bind the published files/pointers')
    owner_root = STATE / 'knowledge' / owner
    root = owner_root / 'versions' / doc['version'] / 'brain'
    for f in doc['files']:
        original = Path(f['path'])
        rel = original.relative_to(BRAIN)
        local = root / rel
        restore_file(dict(f, path=str(local)), [root])
    write(owner_root / 'version.json',
          dict({k: doc[k] for k in ('owner', 'version', 'large_source_pointers')}, root=str(root)))


def knowledge_roots(brain=BRAIN):
    """Only each owner's published version; old immutable versions remain available for receipt replay."""
    return [Path(brain)] + [Path(v['root']) for v in knowledge_versions()]


def knowledge_versions():
    return [json.loads(p.read_bytes()) for p in sorted((STATE / 'knowledge').glob('*/version.json'))]


def recover_request():
    config = os.environ.get('FRANKIE_LANE_MAILBOX')
    if not config:
        return
    pending = Path(config).with_name('rpc-pending.json')
    prior = json.loads(pending.read_bytes()) if pending.exists() else {}
    if prior.get('waiting'):
        body = dict(prior['body'])
        body.pop('id')
        op = body.pop('op')
        return dict(op=op, result=request(op, **body))


def request(op, **payload):
    """One durable mailbox request. A controller outage leaves the held day waiting on the same box/lane."""
    config = os.environ.get('FRANKIE_LANE_MAILBOX')
    if not config:
        raise RuntimeError('remote lane mailbox not configured')
    pending = Path(config).with_name('rpc-pending.json')
    prior = json.loads(pending.read_bytes()) if pending.exists() else {}
    operation = dict(op=op, **payload)
    if prior.get('waiting'):
        body = prior.get('body')
        if body is None or {k: v for k, v in body.items() if k != 'id'} != operation:
            raise RuntimeError('an interrupted lane request must finish before a different operation')
    else:
        body = dict(id=uuid.uuid4().hex, **operation)
    ident = body['id']
    raw = json.dumps(body, sort_keys=True).encode()
    write(pending, dict(id=ident, op=op, body=body, at=time.time(), waiting=True, uploaded=False))
    def check_save():
        path = os.environ.get('FRANKIE_LANE_STOP_FILE')
        if path and Path(path).exists():
            raise SystemExit(75)  # the complete request is durable; resume replays the same id
    while True:
        check_save()
        cfg = json.loads(Path(config).read_bytes())
        try:
            urllib.request.urlopen(urllib.request.Request(cfg['request_put'], raw, method='PUT'), timeout=120).close()
            break
        except urllib.error.HTTPError as error:
            if error.code not in (403, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(5)  # controller renews signed slots; ownership is retained while unavailable
    write(pending, dict(id=ident, op=op, body=body, at=time.time(), waiting=True, uploaded=True))
    while True:
        check_save()
        cfg = json.loads(Path(config).read_bytes())
        try:
            response = json.loads(urllib.request.urlopen(cfg['response_get'], timeout=120).read())
            if response.get('id') == ident:
                write(pending, dict(id=ident, waiting=False))
                if response.get('error'):
                    raise RuntimeError(response['error'])
                return response['result']
        except urllib.error.HTTPError as error:
            if error.code not in (403, 404, 500, 502, 503, 504):
                raise
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(5)


def boundary(day, stage, publish=True):
    """Before the next dependent step: publish own knowledge and pull peers' newest legal completed stages."""
    if os.environ.get('FRANKIE_LANE_MAILBOX'):
        result = request('sync', day=day, stage=stage,
                         knowledge=snapshot() if publish else None,
                         run=os.environ['FRANKIE_LANE_RUN'], where=os.environ['FRANKIE_LANE_OWNER'])
        for doc in result.get('knowledge', []):
            if doc['owner'] != os.environ['FRANKIE_LANE_OWNER']:
                merge_snapshot(doc)
    versions = knowledge_versions()
    witness = dict(day=day, stage=stage, consumed=versions, at=time.time())
    write(STATE / 'consumed' / day / (stage + '.json'), witness)
    return witness


def visible_knowledge(day, stage, brain=BRAIN):
    """Read imported knowledge as structured input, excluding this day's later stages and unfrozen confirmation."""
    import frankie_box_brain as BR
    before = {'root': -20, 'teacher': -10, 'classroom': 0, 'search': 10,
              'lessons': 20, 'exchange': 40, 'voice': 40, 'school': 50}.get(stage, 100)
    out = []
    seen = set()
    for root in knowledge_roots(brain):
        for label, m, d in BR.entries_before(root, '00', day=day):
            parsed = BR.parse_entry_name(d.name)
            eday, kind = parsed
            if eday == day and BR.DAY_KINDS.get(kind, 0) > before:
                continue
            if (kind == 'confirmation' or (eday and eday[:4] in ('2024', '2025'))) and day[:4] in ('2021', '2022', '2023'):
                continue
            for e in m.get('entries', []):
                if not e.get('include') or not e['name'].endswith('.json'):
                    continue
                p = d / e['name']
                raw = p.read_bytes()
                if digest(raw) != e['sha256']:
                    raise ValueError('knowledge source hash mismatch: %s' % p)
                if e['sha256'] in seen:
                    continue
                seen.add(e['sha256'])
                out.append(dict(label=label, day=eday, kind=kind, path=str(p), sha256=e['sha256'], content=json.loads(raw)))
    return out


def learner_school(day, brain=BRAIN):
    """Actual school documents from local and peer owners, through the existing causal school reader."""
    import frankie_box_brain as BR
    loaded, listed, seen = [], [], set()
    for root in knowledge_roots(brain):
        rows, missing = BR.school_rows(root, before_day=day)
        listed.extend(missing)
        for row, doc in rows:
            if row['sha256'] not in seen:
                seen.add(row['sha256'])
                loaded.append((dict(row, owner_root=str(root)), doc))
    return loaded, listed


def coordinate(body, code_root, commit):
    """Main-box side; the existing ROOT claim and FIFO class line remain authoritative."""
    ident = body['id']
    if len(ident) != 32 or any(c not in '0123456789abcdef' for c in ident):
        raise ValueError('invalid coordination request identity')
    directory = STATE / 'rpc'
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / (ident + '.lock'), 'a') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        return _coordinate(body, code_root, commit)


def _coordinate(body, code_root, commit):
    import frankie_box_experiment as X
    import frankie_box_frankie_queue as Q
    import frankie_box_root_claims as C
    run, day, where = body['run'], body['day'], body['where']
    held = C.holder(run, day)
    if not held or held['where'] != where or held['attempt'] != body.get('attempt'):
        raise ValueError('lane request does not own this day')
    prior_response = STATE / 'rpc' / (body['id'] + '.json')
    if prior_response.exists():
        return json.loads(prior_response.read_bytes())
    plan = Q._plan_of(run)
    entry = next(e for e in plan['days'] if e['day'] == day)
    op = body['op']
    result = {}
    if op == 'day_resume':
        result = dict(done=bool((held.get('done') or {}).get('lane_complete')), attempt=held['attempt'])
    elif op == 'sync':
        if body.get('knowledge'):
            doc = body['knowledge']
            if doc['owner'] != where:
                raise ValueError('knowledge owner differs from claim')
            merge_snapshot(doc)
            write(STATE / 'publications' / (where.replace(':', '_') + '.json'), doc)
        result['knowledge'] = [snapshot(owner='main')] + [json.loads(p.read_bytes())
                                 for p in sorted((STATE / 'publications').glob('*.json'))]
    elif op == 'class_take':
        x, why = Q.enqueue('class', run, day, commit, code_root, X.plan_digest(plan), body['settings'],
                          dict(owner=where, remote=True), 'remote held day')
        if x is None:
            raise ValueError(why)
        with Q.locked():
            doc = Q.load('class')
            x = Q.find(doc, x['seq'])
            if x['state'] == 'done' and x.get('remote_owner') == where:
                result = dict(waiting=False, previous=[None, None, 'class already complete'],
                              school_day=x['school_day'], files=[])
            elif Q.front(doc)['seq'] != x['seq']:
                result = dict(waiting=True, reason='earlier class has not completed')
            elif x['state'] == 'running' and x.get('remote_owner') != where:
                result = dict(waiting=True, reason='class is owned by another runner')
            else:
                previous, reason = Q._take_class(doc, x, commit)
                if reason:
                    raise ValueError(reason)
                x['remote_owner'] = where
                Q.save('class', doc)
                files = []
                if previous[0]:
                    for name in ('completion.json', 'history.json', 'post-grade.json',
                                 'external-history.json', 'external-post-grade.json'):
                        p = Path(previous[0]) / name
                        if p.is_file():
                            files.append(pack_file(p))
                result = dict(waiting=False, previous=list(previous[:3]), school_day=x['school_day'], files=files)
    elif op == 'class_done':
        classroom = Path(body['classroom'])
        for f in body.get('files', []):
            if Path(f['path']).name not in ('completion.json', 'history.json', 'post-grade.json',
                                            'external-history.json', 'external-post-grade.json'):
                raise ValueError('not classroom carry state')
            if Path(f['path']).parent != classroom or not classroom.is_relative_to(X.ROOTS):
                raise ValueError('carry state does not belong to the retained classroom')
            restore_file(f, [X.ROOTS])
        with Q.locked():
            doc = Q.load('class')
            x = next(e for e in doc['entries'] if e['run'] == run and e['day'] == day)
            if x.get('remote_owner') != where:
                raise ValueError('class not held by this remote owner')
            if x['state'] == 'done':
                return dict(id=body['id'], result=dict(done=True))
            x.update(state='done', classroom=body['classroom'], done_seq=doc['next_done_seq'],
                     done_at=time.time(), done_utc=Q.utc(), reason=None)
            doc['next_done_seq'] += 1
            Q.save('class', doc)
        result = dict(done=True)
        Q.kick('class', code_root, commit, Q.SETTINGS['queue_worker_seconds'],
               Q.SETTINGS['queue_poll_seconds'], by='remote class completed')
    elif op == 'day_done':
        # Exact small stage receipts, never ROOT spools or journal transfers.
        discovery_days = [e['day'] for e in plan['days'] if e['role'] == 'discovery']
        batch = ('discovery-%02d' % (discovery_days.index(day) // X.BATCH + 1)) if day in discovery_days else None
        published = []
        root_receipt = None
        for f in body['receipts']:
            original = Path(f['path'])
            relative = original.relative_to(X.RUNS / run)
            parts = relative.parts
            day_receipt = len(parts) == 3 and parts[:2] == ('days', day) and original.suffix == '.json'
            teacher_receipt = parts == ('batches', 'day-' + day, 'teacher.json')
            batch_receipt = bool(batch and parts == ('batches', batch, 'lessons.json'))
            if not (day_receipt or teacher_receipt or batch_receipt):
                raise ValueError('completion receipt is outside this owned day')
            retained = STATE / 'lane-receipts' / digest(where.encode()) / run / day / relative
            restore_file(dict(f, path=str(retained)), [STATE / 'lane-receipts'])
            receipt = json.loads(retained.read_bytes())
            expected_key = batch if batch_receipt else ('day-' + day if teacher_receipt else day)
            if receipt.get('schema') != 'FRANKIE_EXPERIMENT_STEP_V1' or receipt.get('run') != run or \
                    receipt.get('key') != expected_key or receipt.get('stage') != original.stem or \
                    receipt.get('plan_sha256') != X.plan_digest(plan):
                raise ValueError('completion receipt identity differs from this retained plan/day/stage')
            receipt.update(remote_owner=where, remote_attempt=held['attempt'], remote_source_sha256=f['sha256'])
            target = original
            if batch_receipt:
                # This lane tested the listed searches; it cannot complete another lane's shared batch.
                target = X.RUNS / run / 'days' / day / 'lessons.json'
                receipt.update(key=day, remote_batch_key=batch)
            if receipt['stage'] == 'root':
                if receipt.get('status') not in X.FINISHED or receipt.get('calculations') != body['calculations'] or \
                        receipt.get('receipt_sha256') != body['receipt_sha256']:
                    raise ValueError('ROOT completion differs from the day_done binding')
                receipt.update(status='reused', remote_calculations=True, owner=where, attempt=held['attempt'], day=day)
                root_receipt = receipt
            published.append((target, receipt))
        if root_receipt is None:
            raise ValueError('day_done requires the actual ROOT stage receipt')
        for target, receipt in published:
            prior = json.loads(target.read_bytes()) if target.exists() else None
            if prior and prior.get('remote_owner') and (prior['remote_owner'], prior.get('remote_attempt')) != \
                    (where, held['attempt']):
                raise ValueError('completion would overwrite another retained owner/attempt')
            if prior and not prior.get('remote_owner') and prior.get('status') in X.FINISHED:
                if receipt['stage'] in ('fetch', 'ingest', 'external'):
                    continue  # the main box already owns these exact prepared inputs; retain its local receipt
                raise ValueError('completion would overwrite an independently finished local stage')
            write(target, receipt)
        ok, why = C.done(run, day, where, held['attempt'], body['calculations'], body['receipt_sha256'],
                         lane_complete=True, owner=where)
        if not ok and why != 'already done':
            raise ValueError(why)
        with Q.locked():
            doc = Q.load('root')
            x = next(e for e in doc['entries'] if e['run'] == run and e['day'] == day)
            x.update(state='done', finish=dict(state='finished'), done_by=where, where=where,
                     calculations=body['calculations'], done_utc=Q.utc())
            Q.save('root', doc)
        result = dict(done=True)
    else:
        raise ValueError('unknown coordination operation %s' % op)
    response = dict(id=body['id'], result=result)
    write(prior_response, response)
    return response
