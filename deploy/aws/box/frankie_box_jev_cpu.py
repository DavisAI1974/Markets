"""Owner-local Jev CPU turn. Explicit pinned request/config only; never provisions a runtime.

One held day lane owns material, blind seal, scientific result and both deliveries.
Call through the existing day child boundary; stdout and receipt.json are stage evidence.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import time
import urllib.parse

from frankie_box_durable import witness, write_bytes, write_json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def pinned(pin):
    path = Path(pin['path'])
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('owner-local pin must be an absolute non-symlink path')
    if witness(path) != {k: pin[k] for k in ('bytes', 'sha256')}:
        raise ValueError('retained Jev input changed: ' + str(path))
    return path


def pin(path):
    return dict(path=str(path), **witness(path))


def retain(path, data):
    path = Path(path)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('retained Jev artifact differs; explicit owner recovery required: ' + str(path))
    else:
        write_bytes(path, data)
    return pin(path)


def retain_json(path, value):
    return retain(path, canonical(value))


def sealed_claims(path, seal_path):
    """Read back the consuming owner's seal, claims, source material and input binding."""
    path, seal_path = Path(path), Path(seal_path)
    seal = json.loads(seal_path.read_bytes())
    if seal.get('schema') != 'JEV_CPU_BLIND_SEAL_V1' or not seal.get('blind_before_frankie'):
        raise ValueError('Jev claims require a consuming-owner blind seal')
    if pinned(seal['claims']) != path or pinned(seal['material']) is None:
        raise ValueError('Jev seal names another claim object')
    if seal['owner'].get('shared_market_context') is not None:
        pinned(seal['owner']['shared_market_context'])
    claims = json.loads(path.read_bytes())
    state = json.loads(Path(seal['state_path']).read_bytes())
    if (claims.get('day') != seal['owner']['day'] or claims.get('stamp') != seal['owner']['stamp']
            or claims.get('blind', {}).get('frankie_read') is not False
            or state.get('cpu_owner') != seal['owner']
            or hashlib.sha256(canonical(state['inputs'])).hexdigest() != seal['inputs_sha256']
            or state.get('claims_filed', {}).get('sha256') != seal['claims']['sha256']
            or state.get('claims_filed', {}).get('bytes') != seal['claims']['bytes']
            or state.get('prepared_claims', {}).get('text', '').encode() != path.read_bytes()):
        raise ValueError('Jev blind seal/state/source identity differs')
    return pin(seal_path)



def peer_brain_sources(brain, day, stamp):
    """Read only Jev-only knowledge from the existing owner-version snapshots."""
    import frankie_box_lane_state as LS
    import frankie_box_experiment_review as REVIEW
    roots = LS.knowledge_roots(brain)
    corrections = REVIEW.corrections(roots)
    selected, seen = [], set()
    kinds = {'entries': 'JEV_BRAIN_ENTRY_V1', 'lessons': 'JEV_LESSONS_V1'}
    for root in roots:
        for manifest_path in sorted((Path(root) / 'jev-peer').glob('*/MANIFEST.json')):
            manifest = json.loads(manifest_path.read_bytes())
            if manifest.get('schema') != 'JEV_PEER_KNOWLEDGE_V1' or manifest.get('audience') != 'jev':
                raise ValueError('Jev peer knowledge has no explicit Jev-only audience')
            for item in manifest['entries']:
                if Path(item['name']).name != item['name'] or item['kind'] not in kinds:
                    raise ValueError('Jev peer knowledge has an invalid member')
                path = pinned(dict(path=str(manifest_path.parent / item['name']),
                                   bytes=item['bytes'], sha256=item['sha256']))
                body = json.loads(path.read_bytes())
                kind, schema = item['kind'], kinds[item['kind']]
                if (body.get('schema') != schema or body.get('author') != 'jev'
                        or body.get('day') != manifest['day'] or body.get('stamp') != manifest['stamp']):
                    raise ValueError('Jev peer knowledge differs from its bound identity/type')
                if body.get('day') == day and body.get('stamp') == stamp:
                    continue  # this exact turn's publication is not a new prior input on resume
                current = REVIEW.current_document(dict(pin(path), content=body), corrections, brain, day=day, stage='jev')
                if current['content'].get('schema') != schema:
                    raise ValueError('checked Jev replacement changed knowledge type')
                key = (kind, current['sha256'])
                if key in seen:
                    continue  # same exact publication mirrored, never two observations
                seen.add(key)
                selected.append(dict(kind=kind, key='jev-peer:' + current['sha256'],
                                     **{k: current[k] for k in ('path', 'bytes', 'sha256')}))
    return selected


def publish_peer_brain(brain, owner, own_entry, lesson):
    """Publish Jev-only generated knowledge, manifest LAST; never admit it to Frankie's corpus."""
    day, stamp = owner['day'], owner['stamp']
    directory = brain / 'jev-peer' / (day + '-' + stamp)
    entries = []
    documents = []
    for name, source, kind, schema in (
            ('own-entry.json', own_entry, 'entries', 'JEV_BRAIN_ENTRY_V1'),
            ('teacher-lesson.json', lesson, 'lessons', 'JEV_LESSONS_V1')):
        raw = Path(source).read_bytes()
        body = json.loads(raw)
        if (body.get('schema') != schema or body.get('author') != 'jev'
                or body.get('day') != day or body.get('stamp') != stamp):
            raise ValueError('Jev-only publication source identity differs')
        copied = retain(directory / name, raw)
        entries.append(dict(name=name, bytes=copied['bytes'], sha256=copied['sha256'], kind=kind, source=str(source)))
        documents.append(body)
    if documents[0]['claims_sha256'] != documents[1]['claims_sha256']:
        raise ValueError('Jev-only entry and scientific lesson refer to different sealed claims')
    # The generic brain entry glob never descends into jev-peer. Both complete exact
    # members precede this immutable manifest; interrupted copies are not published.
    manifest = dict(schema='JEV_PEER_KNOWLEDGE_V1', audience='jev', day=day, stamp=stamp, owner=owner,
                    entries=entries, claims_sha256=documents[0]['claims_sha256'])
    return retain_json(directory / 'MANIFEST.json', manifest)


def execute(request_path):
    request_path = Path(request_path).resolve()
    request = json.loads(request_path.read_bytes())
    if request.get('schema') != 'JEV_CPU_REQUEST_V1':
        raise ValueError('expected JEV_CPU_REQUEST_V1')
    for key in ('run', 'day', 'stamp', 'attempt', 'owner', 'host', 'plan_sha256', 'slot_booking',
                'cpus', 'source', 'save_marker', 'classroom_receipt', 'search', 'brain', 'jev_brain',
                'runtime', 'output', 'report_number', 'day_role'):
        if key not in request:
            raise ValueError('Jev request lacks ' + key)
    if request['day_role'] != 'discovery':
        raise ValueError('Jev CPU is only the authorized discovery classroom-arm route')
    if type(request['report_number']) is not int or request['report_number'] <= 0:
        raise ValueError('Jev needs the existing positive day report number')
    if (request['host'] != os.uname().nodename or len(request['cpus']) != 16
            or len(set(request['cpus'])) != 16 or not str(request['day']).isdigit()
            or len(request['day']) != 8 or not request['attempt'] or not request['stamp']):
        raise ValueError('Jev request lacks the original host/day/attempt/exact 16 CPUs')
    if any('/' in request[k] or request[k] in ('.', '..') for k in ('run', 'stamp', 'attempt')):
        raise ValueError('Jev run/stamp/attempt must be path-free identities')
    import frankie_box_cores as C
    booking, why = C.held_booking(request['slot_booking'])
    if (booking is None or booking['run'] != request['run'] or booking['day'] != request['day']
            or booking['cpus'] != request['cpus'] or booking['commit'] != request['source']['commit']):
        raise ValueError('Jev requires its exact live held day booking: ' + str(why))
    if set(os.sched_getaffinity(0)) != set(request['cpus']):
        raise ValueError('Jev must enter through the original held 16-CPU child wrapper')
    if (os.environ.get('MARKETS_SHA') != request['source']['commit']
            or Path(os.environ.get('CODE_ROOT', '')).resolve() != Path(request['source']['code_root']).resolve()):
        raise ValueError('Jev must run from its retained staged source')
    out = Path(request['output'])
    brain, jev_brain = Path(request['brain']), Path(request['jev_brain'])
    if not all(p.is_absolute() and not any(q.is_symlink() for q in (p, *p.parents))
               for p in (out, brain, jev_brain)):
        raise ValueError('Jev output/brains require exact owner-local absolute paths')
    out.mkdir(parents=True, exist_ok=True)
    with (out / '.lock').open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return _run(request, request_path, out, brain, jev_brain)


def _run(request, request_path, out, brain, jev_brain):
    from research.kalshi.frankie_boss.clm_sidecar import sit_in as SI
    import frankie_box_granite_meeting as transport
    import frankie_box_scientific_teacher as ST
    import frankie_box_experiment_review as REVIEW
    import frankie_box_lane_state as LS
    runtime_path = pinned(request['runtime'])
    runtime = json.loads(runtime_path.read_bytes())
    if runtime.get('schema') != 'JEV_CPU_RUNTIME_V1' or runtime.get('engine') != 'llama.cpp-cpu':
        raise ValueError('Jev needs an explicitly pinned CPU runtime, not legacy Pod/model labels')
    for key in ('binary', 'model', 'model_name', 'cpus', 'context_size', 'max_output_tokens',
                'min_output_tokens', 'token_margin', 'piece_chars', 'process_seconds', 'completion'):
        if key not in runtime:
            raise ValueError('Jev runtime choice is unset: ' + key)
    binary, model = pinned(runtime['binary']), pinned(runtime['model'])
    cpus = runtime['cpus']
    if (not cpus or len(set(cpus)) != len(cpus) or not set(cpus) <= set(request['cpus'][1:])
            or not set(cpus) <= os.sched_getaffinity(0)):
        raise ValueError('Jev runtime CPUs must be an explicit worker subset of the held day lane')
    for key in ('context_size', 'max_output_tokens', 'min_output_tokens', 'token_margin', 'piece_chars', 'process_seconds'):
        if type(runtime[key]) is not int or runtime[key] <= 0:
            raise ValueError('positive explicit Jev runtime value required: ' + key)
    if runtime['max_output_tokens'] < runtime['min_output_tokens']:
        raise ValueError('Jev output budgets disagree')
    if runtime['completion'] not in (dict(comparison='required', unparsed='requires_review'),
                                      dict(comparison='required', unparsed='listed')):
        raise ValueError('explicit Jev completion policy required; comparison must complete')
    classroom_path = pinned(request['classroom_receipt'])
    classroom = json.loads(classroom_path.read_bytes())
    if classroom.get('day') != request['day'] or classroom.get('status') not in ('done', 'complete'):
        raise ValueError('Jev needs the owning day completed classroom receipt')
    material_pin = classroom['jev_material']
    material_path = pinned(material_pin)
    material_request = json.loads(material_path.read_bytes())
    attachment = material_request['attachment']
    if ('dipole_classroom' not in attachment or
            set(attachment) - {'dipole_classroom', 'dipole_external', 'experiment_directive'}):
        raise ValueError('Jev material contains ungoverned attachments')
    search_path = pinned(request['search'])
    search_manifest = json.loads(search_path.read_bytes())
    if search_manifest.get('day') != request['day']:
        raise ValueError('Jev science must use this owning day search')
    identity = dict(request, request_pin=pin(request_path), client=pin(SI.__file__), helper=pin(__file__),
                    transport=pin(transport.__file__), classroom_session=classroom.get('stand_ins'))
    stopped = []
    signal.signal(signal.SIGTERM, lambda *_: stopped.append('signal'))
    def check_save():
        if stopped or Path(request['save_marker']).is_file():
            raise SystemExit(75)
    shared_context, shared_market_source = None, None
    if classroom.get('shared_market') is not None:
        # The cutoff is the classroom's own explicit teacher binding (source_hash/as_of/through_cursor),
        # never a Frankie target selection. Any disposition at that instant is carried, thinner.
        import frankie_box_adviser_market as AM
        bound = attachment['dipole_classroom']['binding']
        adviser = AM.AdviserMarketContext(classroom['shared_market']['identity'], day=request['day'],
            source_hash=bound['source_hash'], as_of=bound['as_of'], through_cursor=bound['through_cursor'])
        context_path = out / 'shared-market-context.json'
        supplied = request.get('shared_market_context')   # optional: an earlier piece's retained read of the same cutoff
        if context_path.is_file():
            shared_context = AM.load_context(context_path, identity=adviser.reader.identity, scope=adviser.scope)
            shared_market_source = 'retained in this Jev output'
        elif supplied is not None:
            shared_context = AM.load_context(pinned(supplied), identity=adviser.reader.identity, scope=adviser.scope)
            shared_market_source = 'supplied retained read of the same source and cutoff: ' + supplied['path']
        else:
            shared_context = adviser.read(check_save=check_save)
            shared_market_source = 'read by this Jev piece from the owner-local shared reader'
        AM.retain_context(context_path, shared_context)
        identity.update(shared_market_context=pin(context_path), adviser_market_reader=pin(AM.__file__))
    else:
        shared_market_source = ('classroom receipt carries no shared market summary (legacy source); '
                                'Jev material bytes unchanged')
    retain_json(out / 'owner.json', identity)
    state_path = out / 'state.json'
    seal_path, claims_path = out / 'claims-seal.json', out / 'claims.json'
    server = None
    owner_affinity = os.sched_getaffinity(0)
    def start_server():
        nonlocal server
        check_save()
        if server is None:
            # The reusable transport inherits this exact worker-only affinity; no new booking.
            os.sched_setaffinity(0, set(cpus))
            for name in ('OMP_NUM_THREADS', 'MKL_NUM_THREADS', 'OPENBLAS_NUM_THREADS'):
                os.environ[name] = str(len(cpus))
            server = transport.LlamaServer(binary, model,
                dict(threads=len(cpus), context_size=runtime['context_size'], max_meeting_seconds=runtime['process_seconds'],
                     cpu_only=True),
                deadline=time.monotonic() + runtime['process_seconds'], evidence_dir=out / 'runtime-evidence')
            server.start()
        return server
    def local_put(url, data):
        parsed = urllib.parse.urlsplit(url)
        path = Path(urllib.parse.unquote(parsed.path))
        if (parsed.scheme != 'file' or parsed.netloc or '..' in path.parts
                or not path.is_absolute() or not any(path.resolve().is_relative_to(p.resolve()) for p in (out, jev_brain))):
            raise ValueError('CPU Jev artifacts stay under the bound owner output/brain')
        retain(path, data)
        return 200  # same client transport interface; durable local readback, not HTTP
    def seal_claims(data, state):
        if claims_path.read_bytes() != data:
            raise ValueError('consumer readback differs from Jev prepared claims')
        seal = dict(schema='JEV_CPU_BLIND_SEAL_V1', owner=identity, claims=pin(claims_path), material=material_pin,
                    inputs_sha256=hashlib.sha256(canonical(state['inputs'])).hexdigest(), state_path=str(state_path),
                    blind_before_frankie=True)
        if not seal_path.exists() and ('frankie_input' in state or 'frankie_read_at' in state or 'compared' in state):
            raise ValueError('cannot invent a blind seal after Frankie was accessed')
        retain_json(seal_path, seal)
        sealed_claims(claims_path, seal_path)
    def frankie_bundle():
        sealed_claims(claims_path, seal_path)
        paths = {'ledgers': classroom_path.parent / 'ledgers.json', 'receipt': classroom_path,
                 'external_ledgers': classroom_path.parent / 'external-code-answers.json',
                 'analysis': classroom_path.parents[2] / 'out' / 'analysis.md'}
        files, unavailable = {}, []
        required = {'ledgers', 'receipt'}
        if classroom.get('schema') == 'FRANKIE_EXPERIMENT_CLASSROOM_RECEIPT_V2':
            required.add('external_ledgers')
        for name, path in paths.items():
            if name in required and not path.is_file():
                raise ValueError('completed classroom lost required Jev comparison evidence: ' + str(path))
            if path.is_file():
                files[name] = dict(pin(path), text=path.read_text())
            else:
                unavailable.append(dict(item=name, path=str(path), reason='not produced'))
        return dict(schema='JEV_FRANKIE_OUTPUTS_V1', day=request['day'], stamp=request['stamp'], files=files,
                    unavailable=unavailable)
    material = dict(schema='JEV_DAY_MATERIAL_V1', day=request['day'], stamp=request['stamp'], day_role='discovery',
                    material=dict(material_pin, source='governed classroom request', **attachment), survivors=None,
                    unavailable=[dict(item='survivors', reason='only survivors already in the governed classroom material apply')])
    if shared_context is not None:
        material['material']['shared_market_context'] = shared_context
    material_file = out / 'material.json'
    retain_json(material_file, material)
    config_path = out / 'client-config.json'
    if config_path.exists():
        config = json.loads(config_path.read_bytes())
    else:
        previous = []
        selected = set()
        for source in peer_brain_sources(brain, request['day'], request['stamp']) + (request.get('prior_brain') or []):
            path = pinned(source)
            if source.get('kind') not in ('entries', 'lessons'):
                raise ValueError('prior Jev brain source must be an own entry or teacher lesson')
            identity_key = (source['kind'], source['sha256'])
            if identity_key in selected:
                continue
            selected.add(identity_key)
            previous.append(dict(kind=source['kind'], key=source.get('key') or str(path),
                                 url=path.as_uri(), **witness(path)))
        own_name = request['day'] + '-' + request['stamp'] + '.json'
        for kind in ('entries', 'lessons'):
            for path in sorted((jev_brain / kind).glob('*.json')):
                if path.name == own_name:
                    continue
                member = witness(path)
                identity_key = (kind, member['sha256'])
                if identity_key in selected:
                    continue
                selected.add(identity_key)
                previous.append(dict(kind=kind, key=str(path), url=path.as_uri(), **member))
        config = dict(material=[material_file.as_uri()], frankie=[], brain=previous,
                      brain_entry=dict(key=own_name, url=(jev_brain / 'entries' / own_name).as_uri()),
                      lessons_key=str(jev_brain / 'lessons' / own_name),
                      **{k: (out / filename).as_uri() for k, filename in (
                          ('claims', 'claims.json'), ('comparison', 'comparison.json'), ('report', 'report.md'),
                          ('transcript', 'transcript.jsonl.gz'), ('receipt', 'client-receipt.json'))})
        retain_json(config_path, config)
    selected_brain = []
    for source in config['brain']:
        path = Path(urllib.parse.unquote(urllib.parse.urlsplit(source['url']).path))
        pinned(dict(path=str(path), bytes=source['bytes'], sha256=source['sha256']))
        selected_brain.append(dict(path=str(path), sha256=source['sha256'], content=json.loads(path.read_bytes())))
    REVIEW.require_current(selected_brain, REVIEW.corrections(LS.knowledge_roots(brain)))
    SI.STATE_PATH, SI.JEV_MODEL = str(state_path), runtime['model_name']
    SI.JEV_CONTEXT, SI.JEV_PIECE_CHARS = runtime['context_size'], runtime['piece_chars']
    SI.JEV_PROMPT_CHARS = runtime['context_size'] * 16  # splitting hint only; exact tokenizer always controls room
    SI.LOCAL = dict(identity=identity, put=local_put, seal=seal_claims, frankie=frankie_bundle, check_save=check_save,
                    count_tokens=lambda messages: start_server().count_tokens(messages),
                    chat=lambda body: start_server()._post('/v1/chat/completions', json.loads(body), 'jev-chat')[1],
                    **{k: runtime[k] for k in ('max_output_tokens', 'min_output_tokens', 'token_margin')})
    os.environ.update(DAY=request['day'], STAMP=request['stamp'])
    try:
        check_save()
        client = SI.main(config)
    finally:
        if server is not None:
            server.stop()
            server.attempt_record('end', 'stopped', role='Jev CPU transport; not a Granite meeting')
        os.sched_setaffinity(0, owner_affinity)  # scientific teacher returns to the original 15+1 lane
    check_save()
    retained_state = json.loads(state_path.read_bytes())
    if (out / 'comparison.json').read_bytes() != retained_state['prepared_comparison']['text'].encode():
        raise ValueError('retained Jev comparison differs from its prepared bytes')
    entry_path = jev_brain / 'entries' / (request['day'] + '-' + request['stamp'] + '.json')
    if witness(entry_path) != {k: retained_state['brain_written'][k] for k in ('bytes', 'sha256')}:
        raise ValueError('retained Jev own brain entry differs')
    if client['call_accounting']['intents_without_reply']:
        raise ValueError('Jev still has unresolved model request intents')
    doc = ST.jev_claims(claims_path, seal_path=seal_path)
    days = ST.load_searches([search_path.parent])
    scientific_dir = out / 'scientific'
    operation, frozen = ST.freeze_operation(doc, days, scientific_dir, brain)
    result_path = scientific_dir / 'jev' / (request['day'] + '-' + request['stamp'] + '.json')
    if not result_path.exists():
        records = frozen['selection']['reproduction_records']
        native = {d['day']: ST.completed_native_evidence(d, scientific_dir) for d in days}
        results = ST.test(doc, days, records_dir=Path(records['directory']), records_selection=records['files'])
        ST.write(doc, days, results, scientific_dir, brain_dir=brain, native=native, operation=operation, publish=False)
    lesson = json.loads(result_path.read_bytes())
    REVIEW._validate_operation(REVIEW._transition_operation(operation, lesson), lesson)
    REVIEW.require_current([dict(path=str(result_path), sha256=witness(result_path)['sha256'], content=lesson)],
                           REVIEW.corrections(LS.knowledge_roots(brain)))
    # Exact result replay repairs either delivery; it never reruns completed science.
    delivery = retain(jev_brain / 'lessons' / result_path.name, result_path.read_bytes())
    ST.publish_lessons(result_path, brain_dir=brain)
    frankie_knowledge = brain / (request['day'] + '-jev-tested') / 'stage-knowledge.json'
    knowledge = json.loads(frankie_knowledge.read_bytes())
    if not any(s.get('sha256') == delivery['sha256'] and s.get('bytes') == delivery['bytes']
               for s in knowledge.get('sources', [])):
        raise ValueError('Frankie publication does not contain the exact Jev lesson')
    # Use the actual Jev next-turn reader for readback; no model call or assertion of inference.
    _, consumed = SI.load_brain(dict(brain=[dict(kind='lessons', key=delivery['path'],
        url=Path(delivery['path']).as_uri(), bytes=delivery['bytes'], sha256=delivery['sha256'])]), request['day'])
    peer_publication = publish_peer_brain(brain, identity, entry_path, result_path)
    deliveries = dict(peer_publication=peer_publication, jev=dict(lesson=delivery, reader=pin(SI.__file__), readback=consumed),
                      frankie=dict(knowledge=pin(frankie_knowledge), lesson=pin(result_path)),
                      rule='available immediately; readback is not a new model/native-learning cycle')
    retain_json(out / 'deliveries.json', deliveries)
    pending = []
    if not client['comparison_available']:
        pending.append('comparison unavailable')
    comparison = json.loads((out / 'comparison.json').read_bytes())
    if runtime['completion']['unparsed'] == 'requires_review':
        if client['unparsed']:
            pending.append('unparsed claims retained; owner disposition required')
        if comparison.get('unparsed'):
            pending.append('unparsed comparison retained; owner disposition required')
    from research.kalshi.frankie_boss.clm_sidecar import jev_report
    numbered = jev_report.render(request['report_number'], 'original held day report number', request['day'],
        request['stamp'], 'waiting: ' + '; '.join(pending) if pending else 'sealed, tested, both lessons delivered',
        out, None, cpu=True)
    numbered += ('\n## Scientific result and delivery readback\n\n```json\n' +
                 json.dumps(dict(result=pin(result_path), deliveries=deliveries), sort_keys=True, indent=2) +
                 '\n```\n').encode()
    report = retain(out / ('jev-report-%04d.md' % request['report_number']), numbered)
    import frankie_box_adviser_market as AM
    client_report = client.get('workflow_report') or {}
    workflow_report = AM.workflow_report('jev', context=shared_context,
        inputs=dict(material=pin(material_file), material_source='governed classroom request',
                    attachments=sorted(attachment), classroom_receipt=pin(classroom_path),
                    search_manifest=pin(search_path), runtime=pin(runtime_path),
                    shared_market_context_source=shared_market_source,
                    brain_sources=len(config['brain']), cutoff_origin='classroom teacher binding (source_hash/as_of/through_cursor)'),
        use=dict(material_text=client_report.get('use'),
                 withheld=['Frankie classroom outputs until the blind seal (JEV_WALL)',
                           'search survivors (only survivors already in the governed material apply)',
                           'teacher answers, grades, claims and private reasoning (never in the picture)'],
                 caps=dict(context_size=runtime['context_size'], max_output_tokens=runtime['max_output_tokens'],
                           min_output_tokens=runtime['min_output_tokens'], token_margin=runtime['token_margin'],
                           piece_chars=runtime['piece_chars'],
                           rule='a prompt without output room refuses (Incomplete); nothing is cut to fit'),
                 model_calls=client.get('call_accounting'), cpus=cpus),
        outputs=dict(claims_seal=pin(seal_path), claims=pin(claims_path), comparison=pin(out / 'comparison.json'),
                     scientific_result=pin(result_path), deliveries=deliveries, report=report,
                     waits=pending, status='waiting' if pending else 'done'))
    receipt = dict(schema='JEV_CPU_RECEIPT_V1', status='waiting' if pending else 'done', owner=identity,
                   claims_seal=pin(seal_path), scientific_result=pin(result_path), deliveries=deliveries,
                   client_receipt=pin(out / 'client-receipt.json'), report=report,
                   report_number=request['report_number'], pending=pending,
                   unparsed=dict(claims=client['unparsed'], comparison=len(comparison.get('unparsed') or [])),
                   workflow_report=workflow_report)
    write_json(out / 'receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = execute(args.request)
    except (Exception, SystemExit) as error:
        request = json.loads(args.request.read_bytes())
        out = Path(request['output'])
        state_path = out / 'state.json'
        state = json.loads(state_path.read_bytes()) if state_path.exists() else {}
        uncertain = [dict(phase=phase, index=i, request_sha256=c['request_sha256'], status=c['status'])
                     for phase, calls in state.get('calls', {}).items() for i, c in enumerate(calls)
                     if c['status'] != 'replied']
        marker = Path(request['save_marker'])
        saved = isinstance(error, SystemExit) and error.code == 75 and not uncertain
        import frankie_box_cores as C
        result = dict(schema='JEV_CPU_STATUS_V1', status='saved' if saved else 'waiting',
                      child=dict(pid=os.getpid(), start=C.start_time(os.getpid())),
                      request=pin(args.request), owner=state.get('cpu_owner'), reason=repr(error),
                      state=pin(state_path) if state_path.exists() else None, unresolved_calls=uncertain,
                      save_marker=pin(marker) if marker.is_file() else None,
                      rule='no model request is retried or erased; owner review resolves uncertainty')
        # A refused/stale invocation never rewrites a completed scientific/day receipt.
        if out.is_dir() and not isinstance(error, BlockingIOError):
            owner_path = out / 'owner.json'
            if result['owner'] is None and owner_path.exists():
                result['owner'] = json.loads(owner_path.read_bytes())
            if (owner_path.exists() and
                    json.loads(owner_path.read_bytes()).get('request_pin') == result['request']):
                write_json(out / 'status.json', result)
        print(json.dumps(result, sort_keys=True), flush=True)
        raise SystemExit(75 if saved else 5)
    print(json.dumps(result, sort_keys=True), flush=True)
    raise SystemExit(0 if result['status'] == 'done' else 5)


if __name__ == '__main__':
    main()
