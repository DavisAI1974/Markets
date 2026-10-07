"""Owner-local Jev CPU turn. Explicit pinned request/config only; never provisions a runtime.

One held day lane owns material, blind seal, scientific result and both deliveries.
Call through the existing day child boundary; stdout and receipt.json are stage evidence.

Runtime (Greg, 2026-10-07: "Use the same weight code and setup as Granite so that way it can automatically improve";
then: Jev uses GRANITE'S settings, ALL of them): Jev binds to THE shared runtime definition of the meeting,
`frankie_box_granite_meeting.local_runtime` over knowledge/GRANITE_MEETING_RUNTIME_V1.json (llama.cpp b11440 llama-server
+ IBM Granite 4.2 3B Q4_K_M, installed once on the owning box, CPU only, the same LlamaServer transport and gate). Every
runtime row is read from that one definition at call time: weights, build, runtime path, sampling (temperature, top_p),
context size, max output per call, the per-call input token cap, the per-call transport ceiling, the per-process time
ceiling, and the completion/refusal behaviour (no call over the cap, nothing truncated; what cannot complete is listed
open, never invented). Rows Granite does not carry are DERIVED from Granite's own values in bind_runtime (one line each),
never pinned separately. So any change to Granite's setup changes Jev automatically; there is no Jev proposal, approval
or runtime file. The only visible refusal is the shared runtime being absent or its pins/files not matching.

Placement (Greg, 2026-10-07: "Jev is set up just like the rest of the workflow"): an ordinary stage of the day on that
day's held lane, on ONE worker CPU (never the coordinator), claimed in the CPU ledger when the stage runs and released
when it ends (frankie_box_cores.STAGE_CPUS / claim_step); threads = 1 on that CPU. No separate box, host, lane or block
of workers. Jev's walls are unchanged: blind before any Frankie output, claims sealed before comparison, private peer
namespace. Nothing here keys on how many days a run holds.
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

SHARED_RUNTIME = 'frankie_box_granite_meeting.local_runtime'     # the ONE runtime definition Jev binds to (Greg, 2026-10-07)
JEV_CPUS = 1          # Greg, 2026-10-07: one worker CPU of the day's held lane while the stage runs (frankie_box_cores.STAGE_CPUS)
JEV_THREADS = 1       # one thread on that one CPU (Greg's placement decision; the only runtime row not read from Granite)
PIECE_CHARS_PER_TOKEN = 2   # derived row: piece_chars = Granite's input_token_cap_per_call x 2 (below the client's 3-chars-
                            # per-token hint, so a piece plus its instruction fits under the cap; the exact tokenizer decides)
COMPLETION = dict(comparison='required', unparsed='listed')   # Granite's: what cannot complete stays listed open, the
                            # record completes with it visible; Jev's comparison wall (seal before comparison) stays required
REBOOK_FIELDS = ('slot_booking', 'cpus', 'output', 'rebook')   # what a REBOOK successor of a request may change


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def bind_runtime(config_path, transport, shared=None):
    """(runtime, refusals): every runtime row from the shared Granite definition the meeting uses. `config_path` is the
    request's pinned GRANITE_MEETING_RUNTIME_V1.json (the staged one the meeting reads); `shared` the request's
    shared_runtime binding (binary/model it was dispatched with). Refusals: the definition unreadable or not the staged
    one, the shared runtime's gate (blank pin, unconfirmed parameters, a missing or differing binary/model/extracted
    file), or a request naming another binary/model. Nothing else refuses; nothing is installed or started here."""
    try:
        config, config_pin = transport.load_config(config_path)
    except (OSError, ValueError) as error:
        return None, ['the shared Granite runtime definition is unreadable: %s: %s' % (type(error).__name__, error)]
    refusals = []
    if Path(config_path).resolve() != Path(transport.CONFIG).resolve():
        refusals.append('Jev binds the staged definition the meeting reads (%s), not %s' % (transport.CONFIG, config_path))
    local = transport.local_runtime(config)
    refusals.extend('shared Granite runtime: ' + r for r in local['reasons'])
    for key in ('binary', 'model'):
        given = (shared or {}).get(key)
        if given is not None and str(given) != local[key]:
            refusals.append('the request names another %s (%s) than the shared Granite runtime (%s); one definition only'
                            % (key, given, local[key]))
    if refusals:
        return None, refusals
    params = local['parameters']
    cap, ctx, out = (int(params['input_token_cap_per_call']), int(params['context_size']),
                     int(params['max_output_tokens_per_turn']))
    runtime = dict(
        definition=SHARED_RUNTIME, config=config_pin, release=local['release'], pins_sha256=local['pins_sha256'],
        model_identity=local['model_identity'], quantization=local['quantization'], binary=local['binary'],
        model=local['model'], setup_provenance=local['setup_provenance'], granite_parameters=params,
        # the transport gets Granite's parameter rows verbatim; threads is Greg's one-CPU placement (JEV_THREADS)
        server_params=dict(params, threads=JEV_THREADS, cpu_only=True),
        threads=JEV_THREADS, temperature=params['temperature'], top_p=params['top_p'], context_size=ctx,
        max_output_tokens=out, input_token_cap=cap,
        min_output_tokens=out,                 # derived: Granite always reserves its full per-call output
        token_margin=ctx - cap - out,          # derived: the Jev client's room rule then refuses any prompt over Granite's cap
        piece_chars=cap * PIECE_CHARS_PER_TOKEN,
        call_seconds=float(params.get('call_ceiling_seconds') or transport.CALL_CEILING_SECONDS),
        process_seconds=float(params['max_meeting_seconds']), completion=COMPLETION,
        bound=dict(
            granite=['weights', 'build', 'runtime path', 'temperature', 'top_p', 'context_size',
                     'max_output_tokens_per_turn', 'input_token_cap_per_call', 'call ceiling (CALL_CEILING_SECONDS unless '
                     'the definition sets call_ceiling_seconds)', 'max_meeting_seconds (per-process ceiling)',
                     'completion/refusal (no call over the cap, nothing truncated, open items listed)'],
            derived=dict(min_output_tokens='= max_output_tokens_per_turn',
                         token_margin='= context_size - input_token_cap_per_call - max_output_tokens_per_turn',
                         piece_chars='= input_token_cap_per_call x %d' % PIECE_CHARS_PER_TOKEN),
            placement=dict(cpus='%d worker CPU of the day\'s held lane (cores STAGE_CPUS claim)' % JEV_CPUS,
                           threads=JEV_THREADS)))
    return runtime, []


def request_chain(request_path, request):
    """[pin of this request, its predecessor's, ..., the original's] for a REBOOK successor chain (Run.jev_rebooked writes
    jev-request-<stamp>.rebook<n>.json beside the original, create-only); [pin] for an original. Each link names its
    predecessor by exact pin, differs from it only in REBOOK_FIELDS, records the booking/CPUs it replaced, and keeps the
    predecessor's output (the resume of retained progress) or takes <output>.rebook<n> (nothing retained there)."""
    chain, current, seen = [pin(request_path)], request, set()
    while current.get('rebook') is not None:
        link = current['rebook']
        if not isinstance(link, dict) or not isinstance(link.get('of'), dict):
            raise ValueError('Jev REBOOK successor names no exact predecessor pin')
        previous_path = pinned(link['of'])
        if str(previous_path) in seen:
            raise ValueError('Jev REBOOK chain loops at %s' % previous_path)
        seen.add(str(previous_path))
        previous = json.loads(previous_path.read_bytes())
        if previous.get('schema') != 'JEV_CPU_REQUEST_V1':
            raise ValueError('Jev REBOOK predecessor is not a JEV_CPU_REQUEST_V1: %s' % previous_path)
        differ = sorted(k for k in set(current) | set(previous) if current.get(k) != previous.get(k))
        if set(differ) - set(REBOOK_FIELDS):
            raise ValueError('Jev REBOOK successor differs from its predecessor in %s, not the booking/CPUs alone'
                             % ', '.join(sorted(set(differ) - set(REBOOK_FIELDS))))
        if (link.get('previous_booking'), link.get('previous_cpus')) != (previous.get('slot_booking'), previous.get('cpus')):
            raise ValueError('Jev REBOOK successor records another replaced booking than its predecessor binds')
        if current.get('output') not in (previous.get('output'), '%s.rebook%s' % (previous.get('output'), link.get('n'))):
            raise ValueError('Jev REBOOK successor output is neither its predecessor\'s nor <output>.rebook<n>')
        chain.append(pin(previous_path))
        current = previous
    return chain


def _comparable(identity):
    """The owner identity without what a REBOOK legitimately changes (booking, lane CPUs, the request pin/record, the
    one claimed runtime CPU)."""
    body = {k: v for k, v in identity.items() if k not in REBOOK_FIELDS + ('request_pin',)}
    if isinstance(body.get('shared_runtime'), dict):
        body['shared_runtime'] = {k: v for k, v in body['shared_runtime'].items() if k != 'cpus'}
    return body


def bind_owner(out, identity, chain):
    """(identity, rebook record): owner.json written once. A REBOOK successor whose output holds the ORIGINAL owner (the
    retained progress of an earlier request of its chain) resumes under that retained identity unchanged (the state's
    cpu_owner and the claims seal stay valid), when everything but the booking/CPUs equals it; the resume is recorded in
    rebook-<n>.json beside it. Anything else that differs is refused (explicit owner recovery)."""
    owner_path = out / 'owner.json'
    if owner_path.is_file():
        retained = json.loads(owner_path.read_bytes())
        if retained.get('request_pin') != chain[0] and retained.get('request_pin') in chain[1:]:
            if _comparable(retained) != _comparable(identity):
                keys = sorted(k for k in set(_comparable(retained)) | set(_comparable(identity))
                              if _comparable(retained).get(k) != _comparable(identity).get(k))
                raise ValueError('retained Jev owner differs beyond the REBOOK booking/CPUs (%s); explicit owner recovery '
                                 'required' % ', '.join(keys))
            n = (identity.get('rebook') or {}).get('n')
            record = retain_json(out / ('rebook-%s.json' % n), dict(
                schema='JEV_CPU_REBOOK_RESUME_V1', request=chain[0], chain=chain, owner_request_pin=retained['request_pin'],
                booking=identity.get('slot_booking'), lane_cpus=identity.get('cpus'),
                runtime_cpus=(identity.get('shared_runtime') or {}).get('cpus'),
                rule='the retained owner identity, state, seal and calls stand unchanged; only the held lane differs'))
            return retained, record
    retain_json(owner_path, identity)
    return identity, None


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
    # Greg, 2026-10-07: Jev is an ordinary stage of the day: ONE worker CPU of the day's held lane, claimed in the ledger
    # for this step (frankie_box_cores.cmd_run_step), never the coordinator (parent) CPU, never a CPU outside the lane
    affinity = sorted(os.sched_getaffinity(0))
    # the claim this wrapper made for this process (FRANKIE_STEP_CLAIM); its pid is recorded right after the spawn, so it
    # is either not yet written or this process
    claims = [c for c in booking.get('steps') or [] if c.get('stage') == 'jev' and sorted(c.get('cpus') or []) == affinity
              and c.get('claim_id') == os.environ.get('FRANKIE_STEP_CLAIM')
              and (c.get('pid') is None or c['pid'].get('pid') == os.getpid())]
    if (len(affinity) != JEV_CPUS or not set(affinity) <= set(request['cpus']) or booking['parent_cpu'] in affinity
            or len(claims) != 1):
        raise ValueError('Jev must enter through its stage claim of %d worker CPU of the held day lane (cores run --inside '
                         '--stage jev); affinity %s, lane %s, parent %s, claims %d'
                         % (JEV_CPUS, affinity, request['cpus'], booking['parent_cpu'], len(claims)))
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
    runtime, refusals = bind_runtime(runtime_path, transport, request.get('shared_runtime'))
    if refusals:
        # visible on status.json through main(): the day waits on the shared runtime (absent / pins differing), never
        # runs past it; there is no Jev-specific approval
        raise ValueError('Jev runtime refused (shared Granite runtime): ' + '; '.join(refusals))
    binary, model = Path(runtime['binary']), Path(runtime['model'])
    cpus = sorted(os.sched_getaffinity(0))        # the stage claim's one worker CPU (checked in execute)
    chain = request_chain(request_path, request)
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
                    transport=pin(transport.__file__), classroom_session=classroom.get('stand_ins'),
                    shared_runtime=dict(definition=SHARED_RUNTIME, config=runtime['config'], binary=runtime['binary'],
                                        model=runtime['model'], pins_sha256=runtime['pins_sha256'], release=runtime['release'],
                                        model_identity=runtime['model_identity'], parameters=runtime['granite_parameters'],
                                        derived=runtime['bound']['derived'], cpus=cpus, threads=runtime['threads']))
    timings = {}
    phase_started = time.time()
    def phase(name):
        nonlocal phase_started
        now = time.time()
        timings[name] = round(now - phase_started, 3)
        phase_started = now
    stopped = []
    signal.signal(signal.SIGTERM, lambda *_: stopped.append('signal'))
    def check_save():
        if stopped or Path(request['save_marker']).is_file():
            raise SystemExit(75)
    shared_context, shared_market_source, reuse_listed = None, None, None
    if classroom.get('shared_market') is not None:
        # The cutoff is the classroom's own explicit teacher binding (source_hash/as_of/through_cursor),
        # never a Frankie target selection. Any disposition at that instant is carried, thinner.
        import frankie_box_adviser_market as AM
        bound = attachment['dipole_classroom']['binding']
        adviser = AM.AdviserMarketContext(classroom['shared_market']['identity'], day=request['day'],
            source_hash=bound['source_hash'], as_of=bound['as_of'], through_cursor=bound['through_cursor'])
        context_path = out / 'shared-market-context.json'
        supplied = request.get('shared_market_context')   # optional: an earlier piece's retained read of the same cutoff
        # Reuse before re-reading (efficiency, 2026-10-07): the day's exchange retained its read of the same source at
        # the teachers' cutoff (<run>/exchange/<day>/shared-market-context.json); when its identity and scope are this
        # cutoff's, one full ordered walk of the day is saved. A different scope or an unreadable file falls through
        # to a fresh read, and the reason is recorded; nothing is assumed.
        # <run>/days/<day>/jev/<stamp>: parents[3] is the run directory (parents[2] named <run>/days, a path that never exists)
        exchange_retained = out.parents[3] / 'exchange' / request['day'] / 'shared-market-context.json'
        if context_path.is_file():
            shared_context = AM.load_context(context_path, identity=adviser.reader.identity, scope=adviser.scope)
            shared_market_source = 'retained in this Jev output'
        elif supplied is not None:
            shared_context = AM.load_context(pinned(supplied), identity=adviser.reader.identity, scope=adviser.scope)
            shared_market_source = 'supplied retained read of the same source and cutoff: ' + supplied['path']
        else:
            shared_context = None
            if exchange_retained.is_file():
                try:
                    shared_context = AM.load_context(exchange_retained, identity=adviser.reader.identity, scope=adviser.scope)
                    shared_market_source = 'reused the exchange\'s retained read of the same source and cutoff: ' + str(exchange_retained)
                except ValueError as error:
                    reuse_listed = 'exchange retained context not reusable (%s); fresh read' % error
            else:
                reuse_listed = 'no exchange retained context at %s; fresh read' % exchange_retained
            if shared_context is None:
                shared_context = adviser.read(check_save=check_save)
                shared_market_source = 'read by this Jev piece from the owner-local shared reader'
        AM.retain_context(context_path, shared_context)
        # the owner identity carries the retained context PIN (stable across attempts); where the bytes came from on
        # this attempt (fresh read, exchange reuse, retained) is receipt information, never identity
        identity.update(shared_market_context=pin(context_path), adviser_market_reader=pin(AM.__file__))
    else:
        shared_market_source = ('classroom receipt carries no shared market summary (legacy source); '
                                'Jev material bytes unchanged')
    phase('shared_market_context')
    identity, rebook = bind_owner(out, identity, chain)
    state_path = out / 'state.json'
    seal_path, claims_path = out / 'claims-seal.json', out / 'claims.json'
    server = None
    def start_server():
        nonlocal server
        check_save()
        if server is None:
            # The SAME transport as the meeting (frankie_box_granite_meeting.LlamaServer) with Granite's parameter rows
            # verbatim (context, caps, sampling, ceilings), the shared binary and model, on the stage claim's one worker
            # CPU (the inherited affinity; no new booking) with one thread, under Granite's per-process ceiling.
            server = transport.LlamaServer(binary, model, runtime['server_params'],
                deadline=time.monotonic() + runtime['process_seconds'], evidence_dir=out / 'runtime-evidence')
            server.start()
            phase('server_start')
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
    SI.STATE_PATH, SI.JEV_MODEL = str(state_path), runtime['model_identity'] or 'Granite 4.2 3B'
    SI.JEV_CONTEXT, SI.JEV_PIECE_CHARS = runtime['context_size'], runtime['piece_chars']
    SI.JEV_PROMPT_CHARS = runtime['context_size'] * 16  # splitting hint only; exact tokenizer always controls room
    SI.LOCAL = dict(identity=identity, put=local_put, seal=seal_claims, frankie=frankie_bundle, check_save=check_save,
                    count_tokens=lambda messages: start_server().count_tokens(messages),
                    # Granite's sampling rows on every call (temperature, top_p); the client's body otherwise as recorded
                    chat=lambda body: start_server()._post('/v1/chat/completions', dict(
                        json.loads(body), temperature=runtime['temperature'], top_p=runtime['top_p']), 'jev-chat')[1],
                    **{k: runtime[k] for k in ('max_output_tokens', 'min_output_tokens', 'token_margin')})
    os.environ.update(DAY=request['day'], STAMP=request['stamp'])
    phase('inputs')
    try:
        check_save()
        client = SI.main(config)
    finally:
        if server is not None:
            server.stop()
            server.attempt_record('end', 'stopped', role='Jev CPU transport; not a Granite meeting')
    phase('student_claims_and_comparison')
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
    # Granite's completion: unparsed answers are retained whole and LISTED (receipt.unparsed and the report); the day
    # completes with them visible, nothing invented and nothing dropped
    from research.kalshi.frankie_boss.clm_sidecar import jev_report
    numbered = jev_report.render(request['report_number'], 'original held day report number', request['day'],
        request['stamp'], 'waiting: ' + '; '.join(pending) if pending else 'sealed, tested, both lessons delivered',
        out, None, cpu=True)
    numbered += ('\n## Scientific result and delivery readback\n\n```json\n' +
                 json.dumps(dict(result=pin(result_path), deliveries=deliveries), sort_keys=True, indent=2) +
                 '\n```\n').encode()
    report = retain(out / ('jev-report-%04d.md' % request['report_number']), numbered)
    phase('science_and_delivery')
    import frankie_box_adviser_market as AM
    client_report = client.get('workflow_report') or {}
    workflow_report = AM.workflow_report('jev', context=shared_context,
        consumer=dict(brain='Jev-only peer knowledge and prior entries/lessons: %d sources (never Frankie\'s brain)' % len(config['brain'])
                            if config['brain'] else None,
                      knowledge=None, lessons=None, carry=None,
                      directive=('experiment_directive attachment of the governed material'
                                 if attachment.get('experiment_directive') is not None else None),
                      walls='blind seal before any Frankie output (JEV_WALL); comparison never in his brain; no Frankie answers, '
                            'grades or private reasoning in the material',
                      outputs=dict(claims='claims.json (sealed)', comparison='comparison.json', scientific_result=str(result_path),
                                   report=report.get('path'))),
        inputs=dict(material=pin(material_file), material_source='governed classroom request',
                    attachments=sorted(attachment), classroom_receipt=pin(classroom_path),
                    search_manifest=pin(search_path), runtime=pin(runtime_path),
                    shared_runtime=identity['shared_runtime'], request_chain=chain, rebook_resume=rebook,
                    shared_market_context_source=shared_market_source, shared_market_reuse_listed=reuse_listed if classroom.get('shared_market') is not None else None,
                    brain_sources=len(config['brain']), cutoff_origin='classroom teacher binding (source_hash/as_of/through_cursor)'),
        use=dict(material_text=client_report.get('use'),
                 withheld=['Frankie classroom outputs until the blind seal (JEV_WALL)',
                           'search survivors (only survivors already in the governed material apply)',
                           'teacher answers, grades, claims and private reasoning (never in the picture)'],
                 caps=dict(context_size=runtime['context_size'], max_output_tokens=runtime['max_output_tokens'],
                           min_output_tokens=runtime['min_output_tokens'], token_margin=runtime['token_margin'],
                           piece_chars=runtime['piece_chars'], call_seconds=runtime['call_seconds'],
                           process_seconds=runtime['process_seconds'], completion=runtime['completion'],
                           input_token_cap=runtime['input_token_cap'], temperature=runtime['temperature'],
                           top_p=runtime['top_p'], bound=runtime['bound'],
                           rule='a prompt over Granite\'s per-call input cap is never sent: it is regenerated from halves; '
                                'nothing is cut to fit'),
                 model_calls=client.get('call_accounting'), cpus=cpus, threads=runtime['threads'],
                 host_cpu=transport.host_cpu(), timings=timings,
                 picture_tokens=(client_report.get('use') or {}).get('picture_tokens')),
        outputs=dict(claims_seal=pin(seal_path), claims=pin(claims_path), comparison=pin(out / 'comparison.json'),
                     scientific_result=pin(result_path), deliveries=deliveries, report=report,
                     waits=pending, status='waiting' if pending else 'done'))
    receipt = dict(schema='JEV_CPU_RECEIPT_V1', status='waiting' if pending else 'done', owner=identity,
                   request_chain=chain, rebook_resume=rebook, runtime_cpus=cpus,
                   claims_seal=pin(seal_path), scientific_result=pin(result_path), deliveries=deliveries,
                   client_receipt=pin(out / 'client-receipt.json'), report=report,
                   report_number=request['report_number'], pending=pending,
                   unparsed=dict(claims=client['unparsed'], comparison=len(comparison.get('unparsed') or [])),
                   workflow_report=workflow_report)
    write_json(out / 'receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--request', type=Path, help='the immutable JEV_CPU_REQUEST_V1 of the day')
    args = parser.parse_args()
    if args.request is None:
        parser.error('--request is required')
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
            try:
                chain = request_chain(args.request.resolve(), request)
            except (OSError, ValueError, KeyError):
                chain = [result['request']]
            if (owner_path.exists() and
                    json.loads(owner_path.read_bytes()).get('request_pin') in chain + [result['request']]):
                result['request_chain'] = chain   # a REBOOK successor resuming the retained owner of its chain
                write_json(out / 'status.json', result)
        print(json.dumps(result, sort_keys=True), flush=True)
        raise SystemExit(75 if saved else 5)
    print(json.dumps(result, sort_keys=True), flush=True)
    raise SystemExit(0 if result['status'] == 'done' else 5)


if __name__ == '__main__':
    main()
