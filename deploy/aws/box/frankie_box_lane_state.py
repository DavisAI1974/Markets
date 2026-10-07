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


CLASSROOM_CARRY = ('completion.json', 'history.json', 'post-grade.json', 'receipt.json')
EXTERNAL_CARRY = ('external-history.json', 'external-post-grade.json')


def pack_classroom_carry(directory):
    """Host continuation only; learner visibility still goes through the classroom's R10 projection."""
    directory = Path(directory)
    receipt = json.loads((directory / 'receipt.json').read_bytes())
    if receipt.get('status') != 'complete':
        raise ValueError('previous classroom has no complete receipt: %s' % directory)
    names = list(CLASSROOM_CARRY)
    external = [(directory / name).is_file() for name in EXTERNAL_CARRY]
    if receipt.get('schema') == 'FRANKIE_EXPERIMENT_CLASSROOM_RECEIPT_V2' or any(external):
        names.extend(EXTERNAL_CARRY)  # an incomplete pair is never mistaken for a pre-V2 classroom
    files = [pack_file(directory / name) for name in names]
    completion = json.loads((directory / 'completion.json').read_bytes())
    history = json.loads((directory / 'history.json').read_bytes())
    grade = json.loads((directory / 'post-grade.json').read_bytes())
    if not history or history[-1] != completion or not completion.get('completion_hash') or \
            receipt.get('completion_hash') != completion['completion_hash'] or \
            completion.get('post_grade_hash') != grade.get('post_grade_hash'):
        raise ValueError('previous classroom completion/history differs from its receipt')
    if 'external-history.json' in names:
        history = json.loads((directory / 'external-history.json').read_bytes())
        grade = json.loads((directory / 'external-post-grade.json').read_bytes())
        if not history or (receipt.get('external') or {}).get('completion_hash') != history[-1].get('completion_hash') or \
                history[-1].get('post_grade_hash') != grade.get('post_grade_hash'):
            raise ValueError('previous external classroom history/grade differs from its receipt')
    return files


def restore_classroom_carry(directory, files, roots, day=None):
    directory = Path(directory)
    names = [Path(f['path']).name for f in files]
    if len(set(names)) != len(names) or not set(CLASSROOM_CARRY) <= set(names) or \
            not set(names) <= set(CLASSROOM_CARRY + EXTERNAL_CARRY):
        raise ValueError('incomplete or unexpected classroom carry files')
    for f in files:
        if Path(f['path']).parent != directory:
            raise ValueError('carry state does not belong to the named classroom')
    receipt_file = next(f for f in files if Path(f['path']).name == 'receipt.json')
    receipt = json.loads(base64.b64decode(receipt_file['data'], validate=True))
    if receipt.get('status') != 'complete' or day is not None and receipt.get('day') != day:
        raise ValueError('classroom carry has no completed receipt for the requested trading day')
    if (receipt.get('schema') == 'FRANKIE_EXPERIMENT_CLASSROOM_RECEIPT_V2' or set(names) & set(EXTERNAL_CARRY)) and \
            not set(EXTERNAL_CARRY) <= set(names):
        raise ValueError('incomplete external classroom carry pair')
    # Publish the completion receipt last so a partial transfer cannot appear complete.
    for f in sorted(files, key=lambda f: Path(f['path']).name == 'receipt.json'):
        restore_file(f, roots)
    pack_classroom_carry(directory)
    receipt = json.loads((directory / 'receipt.json').read_bytes())
    return receipt


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
    # Correction links travel with both complete lesson objects. Research evidence keeps its
    # owner-qualified witness; it is not copied through the learner answer wall.
    import frankie_box_experiment_review as REVIEW
    correction_files = {}
    for correction in REVIEW.corrections([brain]).values():
        for key in ('record', 'original', 'replacement'):
            pin = correction[key]
            correction_files[pin['path']] = pin
    for path, pin in sorted(correction_files.items()):
        packed = pack_file(Path(path))
        if any(packed[k] != pin[k] for k in ('bytes', 'sha256')):
            raise ValueError('correction changed while preparing lane publication')
        files.append(packed)
    version = digest(json.dumps(dict(files=[(f['path'], f['sha256']) for f in files],
                                    pointers=pointers, source_brain=str(brain)), sort_keys=True).encode())
    return dict(owner=owner, version=version, source_brain=str(brain), files=files, large_source_pointers=pointers)


def merge_snapshot(doc, brain=BRAIN):
    """Imported entries use their own namespace; owner's canonical brain entries are never overwritten."""
    owner = digest(doc['owner'].encode())
    binding = dict(files=[(f['path'], f['sha256']) for f in doc['files']], pointers=doc['large_source_pointers'])
    if 'source_brain' in doc:
        binding['source_brain'] = doc['source_brain']
    version = digest(json.dumps(binding, sort_keys=True).encode())
    if version != doc['version']:
        raise ValueError('knowledge version does not bind the published files/pointers')
    owner_root = STATE / 'knowledge' / owner
    root = owner_root / 'versions' / doc['version'] / 'brain'
    for f in doc['files']:
        original = Path(f['path'])
        rel = original.relative_to(Path(doc.get('source_brain') or BRAIN))
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


def boundary(day, stage, publish=True, brain=BRAIN):
    """Before the next dependent step: publish own knowledge and pull peers' newest legal completed stages."""
    if os.environ.get('FRANKIE_LANE_MAILBOX'):
        result = request('sync', day=day, stage=stage,
                         knowledge=snapshot(brain=brain) if publish else None,
                         run=os.environ['FRANKIE_LANE_RUN'], where=os.environ['FRANKIE_LANE_OWNER'])
        for doc in result.get('knowledge', []):
            if doc['owner'] != os.environ['FRANKIE_LANE_OWNER']:
                merge_snapshot(doc, brain=brain)
    versions = knowledge_versions()
    witness = dict(day=day, stage=stage, brain=str(brain), available_versions=versions, at=time.time(),
                   treatment='transport availability only; actual learner inputs are recorded by the reader')
    write(STATE / 'consumed' / day / (stage + '.json'), witness)
    return witness


def learner_knowledge(day, stage, brain=BRAIN, *, classroom_mode=None):
    """Pin whole legal documents, including reconsideration and completed_native_evidence.

    Preserve every unaffected field. Explicit researched corrections deliver complete successors;
    older/unresolved competing lessons remain. Stage/answer walls also cover correction availability.
    """
    import frankie_box_brain as BR
    before = {'root': -20, 'teacher': -10, 'classroom': 0, 'search': 10,
              'lessons': 20, 'exchange': 40, 'voice': 40, 'meeting': 45, 'school': 50}.get(stage, 100)
    out, listed = [], []
    seen = set()
    versions = knowledge_versions()
    import frankie_box_experiment_review as REVIEW
    records = REVIEW.corrections([brain] + [v['root'] for v in versions])
    for root in [Path(brain)] + [Path(v['root']) for v in versions]:
        for label, m, d in BR.entries_before(root, '00', day=day):
            parsed = BR.parse_entry_name(d.name)
            eday, kind = parsed
            reason = None
            if eday == day and stage == 'classroom' and kind == 'teacher' and classroom_mode != 'TEACH':
                reason = 'current-day teacher measurements contain answers withheld by this classroom mode'
            elif eday == day and (BR.DAY_KINDS.get(kind, 0) > before or
                                  kind.isdigit() and before <= 0):
                reason = 'this day classroom answers or later-stage findings are not available at this boundary'
            if reason:
                listed.append(dict(label=label, path=str(d), reason=reason))
                continue
            for e in m.get('entries', []):
                if not e.get('include'):
                    listed.append(dict(label=label, name=e['name'], reason='excluded by the source manifest'))
                    continue
                p = d / e['name']
                if not p.is_file():
                    raise FileNotFoundError('included learner knowledge is missing: %s' % p)
                if p.stat().st_size != e['bytes'] or BR._file_sha256(p) != e['sha256']:
                    raise ValueError('knowledge source hash mismatch: %s' % p)
                if not e['name'].endswith('.json'):
                    listed.append(dict(label=label, path=str(p), sha256=e['sha256'], bytes=e['bytes'],
                                       reason='retained text evidence; no structured learner calculation consumes this format'))
                    continue
                content = json.loads(p.read_bytes())
                delivered = REVIEW.current_document(dict(label=label, day=eday, kind=kind, path=str(p),
                    bytes=e['bytes'], sha256=e['sha256'], content=content), records, brain, day=day, stage=stage)
                if delivered['sha256'] in seen:
                    listed.append(dict(label=label, path=delivered['path'], sha256=delivered['sha256'],
                                       reason='identical delivered bytes already supplied'))
                    continue
                seen.add(delivered['sha256'])
                out.append(delivered)
    return dict(documents=out, listed=listed, versions=versions)


def visible_knowledge(day, stage, brain=BRAIN):
    return learner_knowledge(day, stage, brain)['documents']


def require_current_selection(path, brain=BRAIN):
    """A frozen owner selection needs a checked successor when its actual inputs were corrected."""
    import frankie_box_experiment_review as REVIEW
    records = REVIEW.corrections(knowledge_roots(brain))
    if records and Path(path).is_file():
        REVIEW.require_current(REVIEW.frozen_documents(path), records)


def import_meeting_record(exchange_path, record_path, expected_sha256):
    """Explicit owner-side return of a runner artifact; no dispatch, download or model call."""
    import frankie_box_brain as BR
    import frankie_box_granite_meeting as GM
    import frankie_box_experiment as X
    from frankie_box_durable import write_bytes, write_json
    exchange_path, record_path = Path(exchange_path), Path(record_path)
    exchange = json.loads(exchange_path.read_bytes())
    day, run = str(exchange.get('day')), exchange.get('run')
    import re
    if not re.fullmatch(r'[0-9]{8}', day) or not isinstance(run, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', run):
        raise ValueError('returned meeting needs the original run/day identity')
    owner = Path('/opt/frankie-box/work/experiment') / run
    target = BR.meeting_directory(exchange_path, owner_dir=owner)
    successor = target != owner / 'meeting' / day
    plan = json.loads((owner / 'plan.json').read_bytes())
    if plan.get('schema') != X.SCHEMA or plan.get('run') != run or not any(e.get('day') == day for e in plan.get('days', [])):
        raise ValueError('returned meeting is outside the retained plan')
    plan_sha = X.plan_digest(plan)
    def read_step(stage, required=False):
        path = owner / 'days' / day / (stage + '.json')
        if not path.is_file() and not required:
            return None
        value = json.loads(path.read_bytes())
        if (value.get('schema') != 'FRANKIE_EXPERIMENT_STEP_V1' or value.get('run') != run
                or value.get('key') != day or value.get('stage') != stage or value.get('plan_sha256') != plan_sha):
            raise ValueError('retained %s step differs from the original run/day/plan' % stage)
        return value
    root = read_step('root', required=True)
    if root.get('status') not in ('done', 'reused'):
        raise ValueError('returned meeting needs the owning completed ROOT')
    if root.get('remote_calculations'):
        raise ValueError('return the meeting on its owning lane; this box only holds a remote ROOT receipt')
    exchange_step = read_step('exchange', required=True)
    exchange_receipt = json.loads((exchange_path.parent / 'receipt.json').read_bytes())
    if (exchange_step.get('status') not in ('done', 'reused')
            or exchange_receipt.get('schema') != ('FRANKIE_EXCHANGE_SUCCESSOR_RECEIPT_V1' if successor
                                                 else 'FRANKIE_EXPERIMENT_EXCHANGE_RECEIPT_V1')
            or exchange_receipt.get('status') != 'complete' or exchange_receipt.get('run') != run
            or str(exchange_receipt.get('day')) != day
            or (not successor and exchange_receipt.get('exchange_hash') != exchange.get('exchange_hash'))):
        raise ValueError('returned meeting needs the original completed exchange receipt')
    if successor and (exchange_step.get('successor_inputs') != exchange_receipt.get('replacement_inputs')
                      or exchange_step.get('exchange_sha256') != digest(exchange_path.read_bytes())):
        raise ValueError('returned successor meeting differs from the current exchange input binding')
    for field, name in (('frankie_view', 'exchange-frankie.json'), ('exchange', 'exchange.json')):
        source = exchange_path.parent / name
        pin = exchange_receipt.get('full' if successor and field == 'exchange' else field) or {}
        source_raw = source.read_bytes()
        if (pin.get('path') != str(source) or exchange_step.get(field) != str(source)
                or pin.get('bytes') != len(source_raw) or pin.get('sha256') != digest(source_raw)):
            raise ValueError('original exchange %s differs from its retained source pin' % field)
    import frankie_box_experiment_review as REVIEW
    REVIEW.require_current([dict(exchange_receipt['frankie_view'], content=exchange)],
                           REVIEW.corrections(knowledge_roots(plan.get('brain') or BRAIN)))
    raw = record_path.read_bytes()
    if digest(raw) != expected_sha256:
        raise ValueError('returned meeting differs from the supplied artifact hash')
    record = BR.read_meeting_record(record_path, exchange_path=exchange_path,
                                    expected_sha256=expected_sha256, complete=False)
    if any(p.is_symlink() for p in (target, *target.parents)):
        raise ValueError('returned meeting output traverses a symbolic link')
    target.mkdir(parents=True, exist_ok=True)
    lock_path = target / '.meeting.lock'
    if lock_path.is_symlink():
        raise ValueError('meeting lock is a symbolic link')
    with lock_path.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if read_step('exchange', required=True) != exchange_step:
            raise ValueError('owning exchange changed before meeting import; returned bytes preserved')
        output = target / 'meeting.json'
        step = read_step('voice')
        reports = read_step('reports')
        refresh_reports = bool(reports and (reports.get('status') == 'done' or reports.get('meeting_refresh_pending')))
        classroom = read_step('classroom') if refresh_reports else None
        if refresh_reports and not (classroom and classroom.get('classroom')):
            raise ValueError('completed reports have no retained classroom to refresh')
        prior_receipt = target / 'receipt.json'
        if prior_receipt.is_file():
            retained_receipt = json.loads(prior_receipt.read_bytes())
            if retained_receipt.get('status') == 'complete':
                retained = BR.read_meeting_for_exchange(exchange_path, owner_dir=owner)
                if record['status'] != 'complete' or retained['receipt']['record']['sha256'] != expected_sha256:
                    raise ValueError('a completed meeting receipt cannot be downgraded or re-pinned')
        if step and step.get('status') in ('done', 'reused') and step.get('meeting_sha256') != expected_sha256:
            raise ValueError('returned meeting differs from the completed voice step')
        if output.is_file():
            prior = BR.read_meeting_record(output, exchange_path=exchange_path, complete=False)
            if prior['status'] == 'complete' and output.read_bytes() != raw:
                raise ValueError('a different completed meeting is already retained')
        if not output.is_file() or output.read_bytes() != raw:
            write_bytes(output, raw)
        if record['status'] == 'complete':
            receipt = GM.publish_meeting_record(exchange_path, target, plan.get('brain') or BRAIN, include_inputs=False)
        else:
            receipt = dict(schema=GM.RECEIPT_SCHEMA, day=day, status=record['status'],
                           record=GM.witness_file(output), refused_to_run=record.get('refused_to_run') or [],
                           model_calls=record.get('model_calls', 0), publication='none')
            write_json(target / 'receipt.json', receipt)
        # Reconcile a prior non-blocking disposition; keep plan/CPU/owner identity intact.
        if read_step('exchange', required=True) != exchange_step:
            raise ValueError('owning exchange changed during meeting import; publication retained without step reassignment')
        step_path = owner / 'days' / day / 'voice.json'
        if step is not None:
            step.update(status='done' if record['status'] == 'complete' else 'waiting',
                        meeting_status=record['status'], meeting=str(output), meeting_sha256=expected_sha256,
                        model_calls=receipt.get('model_calls', 0), receipt=str(target / 'receipt.json'),
                        publication=receipt.get('publication'), brain_entry=receipt.get('brain_entry'),
                        counts=receipt.get('counts'), refused_to_run=receipt.get('refused_to_run') or [],
                        non_blocking=record['status'] != 'complete', not_wired=False,
                        reason=None if record['status'] == 'complete' else 'returned meeting did not call the model')
            write_json(step_path, step)
        if refresh_reports:
            # A done class never re-enters the queue. Revise its existing numbered reports here.
            import frankie_box_experiment_day_reports as R
            entry = next(e for e in plan['days'] if e['day'] == day)
            reports['meeting_refresh_pending'] = True
            write_json(owner / 'days' / day / 'reports.json', reports)
            refreshed = R.run(day, classroom['classroom'], run, X.REPORTS, entry['cls'],
                              classroom.get('reason') if classroom.get('status') == 'refused' else None,
                              exchange=exchange_step['exchange'], return_receipt=True)
            reports.update(status='failed' if refreshed['problems'] else 'done', meeting=refreshed['meeting'],
                           reports=refreshed['reports'], problems=refreshed['problems'],
                           report_number=refreshed['report_number'], meeting_refresh_pending=bool(refreshed['problems']))
            write_json(owner / 'days' / day / 'reports.json', reports)
            if refreshed['problems']:
                raise ValueError('returned meeting retained; report refresh needs recovery: %s' % refreshed['problems'])
    return receipt


def learner_school(day, brain=BRAIN, versions=None, *, stage='classroom'):
    """All completed experiment classes are eligible in workflow order, regardless of trading date or old role (Greg 2026-10-06)."""
    import frankie_box_brain as BR
    loaded, listed, seen = [], [], set()
    versions = knowledge_versions() if versions is None else versions
    import frankie_box_experiment_review as REVIEW
    records = REVIEW.corrections([brain] + [v['root'] for v in versions])
    for root in [Path(brain)] + [Path(v['root']) for v in versions]:
        try:
            index = BR._school_index(root)['rows']
        except (OSError, ValueError) as error:
            listed.append(dict(row=None, reason='school index could not be read: %s' % error))
            continue
        eligible = []
        for row in index:
            school_day = str(row.get('day'))
            if school_day == day:
                listed.append(dict(row=row, reason='this classroom cannot consume its own end-of-day school answers'))
            else:
                eligible.append(row)
        rows, missing = BR.school_rows(root, pinned=eligible)
        listed.extend(missing)
        for row, doc in rows:
            delivered = REVIEW.current_document(dict(path=str(root / BR.SCHOOL_DIR / row['file']),
                sha256=row['sha256'], content=doc), records, brain, day=day, stage=stage)
            if delivered['sha256'] not in seen:
                seen.add(delivered['sha256'])
                loaded.append((dict(row, owner_root=str(root), path=delivered['path'],
                    sha256=delivered['sha256'], corrections_applied=delivered.get('corrections_applied', [])),
                    delivered['content']))
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
    request_sha256 = digest(json.dumps(body, sort_keys=True, separators=(',', ':')).encode())
    request_path = STATE / 'rpc' / (body['id'] + '.request.json')
    prior_response = STATE / 'rpc' / (body['id'] + '.json')
    if request_path.exists():
        retained = json.loads(request_path.read_bytes())
        if retained.get('request_sha256') != request_sha256 or retained.get('body') != body:
            raise ValueError('coordination request ID reused with a different or unbound payload; retained intent preserved')
    elif prior_response.exists():
        raise ValueError('legacy coordination result has no retained request binding; preserved for explicit recovery')
    else:
        # coordinate() holds the existing per-ID lock. Pin intent before any side effect.
        write(request_path, dict(request_sha256=request_sha256, body=body))
    if prior_response.exists():
        response = json.loads(prior_response.read_bytes())
        if response.get('request_sha256') != request_sha256 or response.get('id') != body['id']:
            raise ValueError('coordination result differs from its retained request binding; preserved')
        return response
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
        result['knowledge'] = [snapshot(brain=plan.get('brain') or BRAIN, owner='main')] + [json.loads(p.read_bytes())
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
                previous = Q.previous_for(doc, x, plan)
                result = dict(waiting=False, previous=list(previous[:3]),
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
                files = pack_classroom_carry(previous[0]) if previous[0] else []
                result = dict(waiting=False, previous=list(previous[:3]), school_day=x['school_day'], files=files)
    elif op == 'class_done':
        classroom = Path(body['classroom'])
        with Q.locked():
            doc = Q.load('class')
            x = next(e for e in doc['entries'] if e['run'] == run and e['day'] == day)
            if x.get('remote_owner') != where:
                raise ValueError('class not held by this remote owner')
            restore_classroom_carry(classroom, body.get('files', []), [X.ROOTS], day=day)
            if x['state'] != 'done':
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
    response = dict(id=body['id'], request_sha256=request_sha256, result=result)
    write(prior_response, response)
    return response


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Return a pinned Granite record to its owning experiment lane')
    parser.add_argument('--import-meeting', required=True, metavar='RECORD')
    parser.add_argument('--record-sha256', required=True)
    parser.add_argument('--exchange', required=True, help='original owner-local exchange-frankie.json')
    args = parser.parse_args()
    print(json.dumps(import_meeting_record(args.exchange, args.import_meeting, args.record_sha256), sort_keys=True))
