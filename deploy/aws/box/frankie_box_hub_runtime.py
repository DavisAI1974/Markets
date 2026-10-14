"""Owner-local hub binding for the existing experiment stages.

One lock binds inputs and publishes outputs; native calculation runs outside it.
The native stage checkpoints remain authoritative. A hub operation is complete
only after its native receipt is complete and its bound inputs remain current.
No process is launched by importing or constructing this adapter.
"""
import contextlib
import fcntl
import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path

import frankie_box_hub as H
import frankie_box_hub_spokes as S

STAGES = ('root', 'teacher', 'classroom', 'data', 'search', 'batch_lessons',
          'frankie_lessons', 'exchange', 'jev', 'voice', 'school', 'reports')
REQUIRES = {
    'root': (), 'teacher': ('root',), 'classroom': ('root', 'teacher'),
    'data': ('root', 'teacher'), 'search': ('data',),
    'batch_lessons': ('search',), 'frankie_lessons': ('classroom', 'search'),
    'exchange': ('teacher', 'classroom', 'search', 'batch_lessons', 'frankie_lessons'),
    'jev': ('classroom', 'search', 'exchange'), 'voice': ('exchange', 'jev'),
    'school': ('classroom', 'exchange', 'jev', 'voice'),
    'reports': ('root', 'teacher', 'classroom', 'exchange', 'jev', 'voice', 'school'),
}
PUBLICATION_PIECE = {'batch_lessons': 'teacher-2', 'frankie_lessons': 'teacher-2', 'voice': 'exchange'}
_LOCAL = threading.local()
_DOCTORS = {}
_DOCTOR_LOCK = threading.Lock()


def parallel_cpus(cores, booking):
    """Disjoint classroom / teacher-then-search CPUs within one live booking.

    Physical sibling groups remain together. A small booking with only one
    group stays sequential; no extra CPUs are requested.
    """
    held, _ = cores.held_booking(booking)
    if held is None:
        return None
    groups = [[c for c in group if c in held['cpus']] for group in cores.core_map()['cores']]
    lanes = [[], []]
    for group in (g for g in groups if g):
        lanes[0 if len(lanes[0]) <= len(lanes[1]) else 1].extend(group)
    return lanes if all(lanes) else None


def _state(hub):
    return H._load(hub / 'runtime.json', {'schema': 'FRANKIE_HUB_RUNTIME_V1', 'operations': {}})


def _signature(additions):
    return H.value_sha256(sorted((a['kind'], H.addition_key(a), a['content_sha256']) for a in additions))


def _stat(path):
    s = os.stat(path)
    return [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def _reader_document():
    path = getattr(_LOCAL, 'reader', None) or os.environ.get('FRANKIE_HUB_INPUTS')
    return (H._load(path) or {}) if path else {}


def active_pid(operation):
    for pid_key, start_key in (('child_pid', 'child_pid_start'), ('pid', 'pid_start')):
        if H._live(operation.get(pid_key), operation.get(start_key)):
            return operation[pid_key]
    return None


def voice_passed(receipt):
    """The queue's existing nonblocking meeting contract, shared with the hub."""
    from frankie_box_experiment import FINISHED
    return bool(receipt and (receipt.get('status') in FINISHED or (
        receipt.get('status') == 'waiting' and receipt.get('non_blocking')
        and receipt.get('meeting_status') in ('refused', 'inputs_only', 'runtime_failed', 'remote_pending'))))


def owner_finished(runtime):
    """Only the exact native owner can declare the day terminal.

    Reports may exist before a correction finishes, and some native routes do
    not publish a reports hub operation. Neither fact is a completion signal.
    """
    owner = runtime.get('owner') or {}
    if not all(owner.get(k) for k in ('run', 'day', 'attempt')):
        return False
    marker = runtime.get('marker') or owner.get('marker')
    if marker and Path(marker).exists():
        return False
    operations = runtime.get('operations') or {}
    for operation in operations.values():
        if (operation.get('status') != 'complete' or operation.get('recovery_pending')
                or operation.get('blocked_signature') or operation.get('changed_inputs')
                or active_pid(operation) is not None):
            return False
        if any(operations.get(piece, {}).get('signature') != signature
               for piece, signature in (operation.get('inputs') or {}).items()):
            return False
    queue = Path('/opt/frankie-box/work/frankie-queue/root.json')
    for path in runtime.get('recovery_watch', []):
        if Path(path).name == 'root.json':
            queue = Path(path)
            break
    document = H._load(queue) or {}
    entries = [entry for entry in document.get('entries', [])
               if entry.get('run') == owner['run'] and entry.get('day') == owner['day']]
    if len(entries) != 1:
        return False
    entry = entries[0]
    return ((entry.get('owner') or {}).get('attempt') == owner['attempt']
            and entry.get('state') == 'done'
            and (entry.get('finish') or {}).get('state') == 'finished'
            and not entry.get('save_request'))


def attach_child(pid):
    reader = getattr(_LOCAL, 'reader', None)
    if not reader:
        return
    hub = Path(reader).parent.parent
    with H.turn(hub, H.CLEAN_PIECE):
        doc = H._load(reader)
        state = _state(hub)
        state['operations'][doc['piece']].update(child_pid=pid, child_pid_start=H._pid_start(pid) if pid else None)
        H._dump(hub / 'runtime.json', state)


def bound_path(path, *, required=False):
    """Resolve a native file input from the current hub lease, preserving its identity.

    Native products are immutable publications; the hub prevents deletion while
    leased. The exact path is preserved because source identities include it.
    """
    requested = os.path.abspath(str(path))
    doc = _reader_document()
    for addition in doc.get('inputs', []):
        if addition.get('path') == requested:
            if _stat(requested) != addition['stat']:
                raise ValueError('hub input changed after binding: ' + requested)
            return Path(addition['path'])
    if required and doc:
        raise ValueError('native input is not in the bound hub set: ' + requested)
    return Path(path)


def child_environment(env):
    """Resolve real native environment inputs from the merged leased hub set."""
    reader = getattr(_LOCAL, 'reader', None)
    if not reader:
        return {}
    doc = _reader_document()
    # The native selector has resolved correction chains and its role walls at
    # this boundary. Bind those exact selected files too; never choose a newer
    # directory or add an unselected lesson to the native invocation.
    selected = [p for p in str(env.get('LESSONS') or '').split(',') if p]
    known = {a.get('path') for a in doc.get('inputs', [])}
    additions = []
    for path in selected:
        path = os.path.abspath(path)
        if path not in known:
            addition = S._file_addition('selected lesson ' + path, 'file', 'native lesson selector', path, hash_max=None)
            if addition is None:
                raise ValueError('selected native lesson missing: ' + path)
            additions.append(dict(addition, key=path, stat=_stat(path)))
    if additions:
        hub = Path(reader).parent.parent
        with H.turn(hub, H.CLEAN_PIECE):
            doc = H._load(reader)
            doc['inputs'].extend(additions)
            H._dump(reader, doc)
    inputs = doc.get('inputs', [])
    result = {'FRANKIE_HUB_INPUTS': str(reader)}
    slots = {'CALCULATIONS': ('ROOT calculations-receipt.json', True),
             'TEACHER_ROWS': ('teacher rows_file', False),
             'TEACHER': ('teacher rows_file', True),
             'SEARCH_DIR': ('search MANIFEST.json', True)}
    for variable, (name, directory) in slots.items():
        if variable not in env:
            continue
        addition = next((a for a in inputs if a.get('name') == name), None)
        if addition is None:
            continue                    # streaming blocks bind in the native block loop
        selected = bound_path(addition['path'], required=True)
        requested = Path(env[variable])
        if directory or requested.is_dir():
            selected = selected.parent
        if selected.resolve() != requested.resolve():
            raise ValueError('%s differs from its bound hub source' % variable)
        result[variable] = str(selected)
    if env.get('LESSONS'):
        result['LESSONS'] = ','.join(str(bound_path(p)) for p in str(env['LESSONS']).split(',') if p)
    return result


def _start_doctor(run, hub):
    if not run.owner or run.save_requested():
        return
    with _DOCTOR_LOCK:
        process = _DOCTORS.get(str(hub))
        if process is not None and process.poll() is None:
            return
        directory = hub.parent / (hub.name + '.doctor')
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / 'doctor.lock').open('a+') as lock:
            try:
                fcntl.flock(lock.fileno(), fcntl.LOCK_SH | fcntl.LOCK_NB)
            except OSError:
                return                  # another owner process already has the doctor
        with (directory / 'runtime.log').open('ab') as log:
            _DOCTORS[str(hub)] = subprocess.Popen(
                [sys.executable, '-B', str(run.box / 'frankie_box_hub_doctor.py'), 'watch', '--hub-dir', str(hub)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                start_new_session=True, close_fds=True)


def sources(run, entry):
    day = entry['day']
    receipt = run.receipt('root', day) or {}
    attempt = run.owned_attempt or (run.owner or {}).get('attempt')
    root = Path(receipt['calculations']) if receipt.get('calculations') else None
    if attempt:
        import frankie_box_experiment as X
        owned = X.ROOTS / attempt
        if root is not None and root.resolve() != owned.resolve():
            raise ValueError('hub ROOT differs from the retained owner attempt')
        root = owned
    if root is None:
        raise ValueError('hub needs the exact retained ROOT attempt; no latest-attempt selection')
    out = S.day_sources(day, run.plan['run'], attempt=root,
                        roots={'repo': run.code_root, 'runs': run.dir.parent,
                               'brain': run.plan.get('brain') or S.DEFAULT_ROOTS['brain']})
    if entry.get('teacher_rows') and (Path(entry['teacher_rows']) / S.ROWS_FILE).is_file():
        out['rows'] = Path(entry['teacher_rows'])
    if out.get('ingest') is None:
        ingest = run.receipt('ingest', day) or {}
        if ingest.get('ingest'):
            out['ingest'] = Path(ingest['ingest'])
            out['ingest_receipt'] = out['ingest'] / 'ingestion-receipt.json'
    # Jev is selected from the day receipt/request, never a newest-directory scan.
    jev = run.receipt('jev', day) or {}
    out['jev_out'] = Path(jev['output']) if jev.get('output') else None
    out['jev_request'] = Path(jev['request']) if isinstance(jev.get('request'), str) else None
    # Checked successors may live beside, rather than inside, the original day
    # directory. Native receipts choose their exact output; no directory scan.
    exchange = run.receipt('exchange', day) or {}
    if exchange.get('frankie_view'):
        out['exchange'] = Path(exchange['frankie_view']).parent
    voice = run.receipt('voice', day) or {}
    if voice.get('meeting'):
        out['meeting'] = Path(voice['meeting']).parent
    classroom = run.receipt('classroom', day) or {}
    if classroom.get('classroom'):
        out['classroom'] = Path(classroom['classroom'])
    return out


def _native_publications(stage, source, receipt):
    """Native products only; the spoke inspection inventory remains broader.

    Follow producer output pins, never progress/status globs or attempt/out.
    Native source-identity receipts are retained where the scientific reader pins
    them. Operational receipts that merely describe an output are not operands.
    """
    additions = []

    def file(name, path, pin=None, kind='file'):
        if path is None:
            return
        addition = S._file_addition(name, kind, stage, path, pin=pin, hash_max=None)
        if addition is None and pin and pin.get('sha256'):
            raise ValueError('native publication pin names a missing product: ' + str(path))
        if addition is not None:
            additions.append(addition)

    def pinned(name, pin, base):
        if not isinstance(pin, dict):
            return
        value = pin.get('path') or pin.get('file') or pin.get('name')
        if value:
            path = Path(value)
            file(name, path if path.is_absolute() else Path(base) / path, pin)

    def brain(directory, prefix):
        if not directory:
            return
        directory = Path(directory)
        manifest = S._json(directory / 'MANIFEST.json') or {}
        for pin in manifest.get('entries', []):
            pinned(prefix + ' ' + str(pin.get('name')), pin, directory)

    visited = set()

    def teacher_product(path, rows, pin=None):
        path, rows = Path(path), Path(rows)
        if str(path) in visited:
            return
        visited.add(str(path))
        # Identity and content directories are part of the slot, so metadata.json
        # and 00.json from distinct key identities cannot collide.
        file('teacher ' + path.relative_to(rows).as_posix(), path, pin)
        doc = S._json(path) or {}
        schema = doc.get('schema')
        if schema == 'FRANKIE_SHARED_TEACHER_KEY_V1':
            children = [doc.get('metadata')] + list(doc.get('ledgers') or [])
        elif schema == 'FRANKIE_TEACHER_JOINED_RECORDS_V1':
            children = [doc.get('header_record')] + [p.get('pin') for p in doc.get('parts', [])]
        elif schema == 'FRANKIE_TEACHER_RECORD_STORE_V1':
            for role in ('data', 'index'):
                target = doc.get(role) or {}
                value = target.get('path')
                if value:
                    target_path = Path(value)
                    if not target_path.is_absolute():
                        target_path = path.parent / target_path
                    file('teacher ' + target_path.relative_to(rows).as_posix(), target_path, target)
            return
        else:
            return
        for child in children:
            if child and child.get('path'):
                target = Path(child['path'])
                teacher_product(target if target.is_absolute() else path.parent / target, rows, child)

    if stage == 'root':
        root = Path(source['attempt'])
        document = S._json(root / 'calculations-receipt.json') or {}
        derive = S._json(root / 'work' / 'derive.json') or {}
        for name in ('calculations-receipt.json', 'source-binding.json'):
            file('ROOT ' + name, root / name, kind='receipt')
        for name in ('calculation_pins', 'external_computation', 'derivation', 'digest'):
            pinned('ROOT ' + name, document.get(name), root)
        for name, pin in (document.get('shared_market_sources') or {}).items():
            if (pin or {}).get('status') != 'absent':
                pinned('ROOT ' + name + ' spool', pin, root)
        pinned('ROOT INPUT spool', (derive.get('rows') or {}).get('record_spool'), root)
        native = derive.get('bedrock') if isinstance(derive.get('bedrock'), dict) else {}
        for name, pin in (native.get('ledgers') or {}).items():
            pinned('ROOT native ledger ' + name, pin, root)
        for name in ('result', 'receipt'):
            pinned('ROOT native ' + name, native.get(name), root)
        for name, pin in (derive.get('layers') or {}).items():
            pinned('ROOT layer ' + name, pin, root)
        file('ROOT native-layer-records.json', root / 'work' / 'native-layer-records.json')
    elif stage == 'teacher':
        rows = Path(source['rows'])
        document = S._json(rows / 'receipt.json') or {}
        file('teacher receipt.json', rows / 'receipt.json', kind='receipt')
        for name in ('rows_file', 'rows_sidecar', 'attachment_file', 'teacher_second_set', 'classroom_carry'):
            pin = document.get(name)
            pinned('teacher ' + name, pin, rows)
            path = S._pin_path(pin, rows)
            if path is not None and path.suffix == '.json' and name == 'teacher_second_set':
                teacher_product(path if path.is_absolute() else rows / path, rows, pin)
        for name in ('teacher-state-split.json', 'teacher-second-set-mismatches.jsonl',
                     'teacher-book-event-differences.jsonl', 'teacher-reconciliation-differences.jsonl',
                     'teacher-account.json', 'teacher-account.md', 'shared-market-context.json'):
            file('teacher ' + name, rows / name)
        if (rows / 'teacher-key.json').is_file():
            teacher_product(rows / 'teacher-key.json', rows)
        section = S._json(rows / 'external-section' / 'receipt.json') or {}
        if section.get('section_file'):
            file('teacher external-section/' + section['section_file'],
                 rows / 'external-section' / section['section_file'],
                 dict(bytes=section.get('section_bytes'), sha256=section.get('section_sha256')))
        brain(Path(source['brain']) / (source['day'] + '-teacher'), 'teacher knowledge')
    elif stage == 'classroom':
        directory = Path(source['classroom'])
        document = S._json(directory / 'receipt.json') or {}
        pins = (document.get('outputs') or {}).get('pinned') or {}
        for name, pin in pins.items():
            pinned('classroom ' + name, dict(pin, path=pin.get('path') or name), directory)
        if not pins:
            # Compatibility for retained classrooms predating output pin maps.
            # These are native result names, never a directory-wide inventory.
            for name in set(S._REPORT_JSON) | {
                    'history.json', 'external-history.json', 'teachback.json', 'learner-knowledge.json',
                    'external-novel-findings.json', 'classroom.md', 'classroom-external.md', 'transcript.md',
                    'native-entry-arithmetic.json', 'exhaustion-d-facts.json', 'package.second_set.json',
                    'package.second_set.jsonl', 'package.external.binding.json'} | {
                    'package.' + part + '.c15.json' for part in ('source', 'teacher_key', 'pre_message', 'binding')}:
                file('classroom ' + name, directory / name)
        pinned('classroom jev material', document.get('jev_material'), directory)
        brain(document.get('brain_entry'), 'classroom knowledge')
    elif stage in ('data', 'search'):
        if receipt.get('target'):
            directory = Path(receipt['target'])
            file(stage + ' MANIFEST.json', directory / 'MANIFEST.json',
                 dict(sha256=receipt.get('manifest_sha256')))
            document = S._json(directory / 'MANIFEST.json') or {}
            if stage == 'search':
                for pin in (document.get('couplings') or {}).get('parts', []):
                    pinned('search ' + str(pin.get('path')), pin, directory)
                pinned('search discovery index', (document.get('discovery') or {}).get('index'), directory)
            else:
                for pin in document.get('files', []):
                    relative = str(pin.get('stage')) + '/' + str(pin.get('path'))
                    pinned('data ' + relative, dict(pin, path=relative), directory)
    elif stage in ('batch_lessons', 'frankie_lessons'):
        # The native receipt selects the lesson files for this operation. Do not
        # adopt another seat's files merely because they share a lesson directory.
        selected = list(receipt.get('lessons') or [])
        for call in receipt.get('calls') or []:
            selected.extend(call.get('reused') or [])
            for operation in (call.get('receipt') or {}).get('operations', []):
                if operation.get('lessons'):
                    selected.append(operation['lessons'])
        for value in selected:
            path = Path(value['path'] if isinstance(value, dict) else value)
            try:
                name = path.relative_to(Path(source['lessons'])).as_posix()
            except ValueError:
                name = str(path)
            file(stage + ' ' + name, path, value if isinstance(value, dict) else None)
    elif stage == 'exchange':
        directory = Path(source['exchange'])
        document = S._json(directory / 'receipt.json') or {}
        for key, name in (('exchange', 'exchange.json'), ('frankie_view', 'exchange-frankie.json')):
            pin = document.get(key)
            if pin:
                pinned('exchange ' + name, pin, directory)
            else:
                file('exchange ' + name, directory / name)
        brain(document.get('brain_entry'), 'exchange knowledge')
    elif stage == 'voice' and receipt.get('status') in ('done', 'reused'):
        directory = Path(source['meeting'])
        document = S._json(directory / 'receipt.json') or {}
        file('exchange meeting meeting.json', directory / 'meeting.json', document.get('record'))
        brain((document.get('brain_entry') or {}).get('path'), 'meeting knowledge')
    elif stage == 'jev':
        directory = source.get('jev_out')
        if directory:
            directory = Path(directory)
            document = S._json(directory / 'receipt.json') or {}
            for name in ('claims_seal', 'scientific_result'):
                pinned('jev ' + name, document.get(name), directory)
            for name in ('claims.json', 'comparison.json'):
                file('jev ' + name, directory / name)
        brain(Path(source['brain']) / (source['day'] + '-jev-tested'), 'jev checked knowledge')
    elif stage == 'school':
        file('school day ' + source['day'], Path(source['brain']) / 'school' / (source['day'] + '.json'))
    elif stage == 'reports':
        directory = source.get('reports_dir')
        if directory:
            document = S._json(Path(directory) / 'receipts' / source['run'] / (source['day'] + '.json')) or {}
            written = document.get('written') or {}
            for name, path in written.items() if isinstance(written, dict) else []:
                if isinstance(path, str):
                    file('report ' + name, path)
    return additions


def _outputs(stage, source, receipt):
    additions = _native_publications(stage, source, receipt)
    # All current products retain their stable logical slot when paths change.
    additions = [dict(a, key=a['name']) for a in additions]
    summary = {k: receipt.get(k) for k in ('status', 'reason', 'target', 'classroom', 'exchange',
                                   'frankie_view', 'exchange_sha256', 'manifest_sha256', 'request', 'output',
                                   'non_blocking', 'meeting_status')
               if receipt.get(k) is not None}
    if summary.get('status') == 'reused':
        summary['status'] = 'done'
    if summary.get('status') == 'done':
        summary.pop('reason', None)
    additions.append(H.value_addition('stage-result', summary, key=stage))
    return additions


def _receipt(run, entry, stage):
    key = entry['day']
    actual = stage
    if stage == 'teacher':
        key = 'day-' + key
    elif stage == 'batch_lessons':
        actual, key = 'lessons', run.batch_of(key)
    receipt = run.receipt(actual, key) if key else None
    if stage == 'teacher' and receipt is None:
        batch = run.batch_of(entry['day'])
        candidate = run.receipt('teacher', batch) if batch else None
        if candidate and entry['day'] not in (candidate.get('refused_days') or {}) and entry['day'] not in (
                candidate.get('waiting') or []):
            days = [d.get('day') if isinstance(d, dict) else d for d in candidate.get('days', [])]
            if entry['day'] in days:
                receipt = candidate
    return receipt


def ensure(run, entry):
    """Import completed native publications without rebuilding retained work."""
    source = sources(run, entry)
    hub = H.open_hub(run.dir / 'hub', run.plan['run'], entry['day'], {},
                     pieces=list(STAGES), prerequisites={p: [] for p in STAGES})
    before = _state(hub)
    adopted = {}
    for stage in STAGES:
        if stage in before['operations']:
            continue
        receipt = _receipt(run, entry, stage)
        if receipt and _completed(stage, receipt, source):
            adopted[stage] = _outputs(stage, source, receipt)     # I/O outside the turn
    with H.turn(hub, H.CLEAN_PIECE):
        state = _state(hub)
        if state.get('attempt') and state['attempt'] != str(source['attempt']):
            raise ValueError('hub belongs to another retained ROOT attempt')
        state.update(attempt=str(source['attempt']), marker=str(run.stop_marker or ''),
                     owner=dict(run.owner or {}), recovery_watch=[
                         str(Path('/opt/frankie-box/work/frankie-queue') / (line + '.json'))
                         for line in ('root', 'class')] + ['/opt/frankie-box/code/current'])
        H._dump(hub / 'runtime.json', state)
    for stage, additions in adopted.items():
        with H.turn(hub, stage) as token:
            state = _state(hub)
            if stage in state['operations']:
                continue
            # No calculation is run during adoption. Native identity/readiness
            # checks still run when the operation is requested below.
            H.write(hub, stage, token, additions)
            state['operations'][stage] = dict(status='complete', adopted=True,
                signature=_signature(additions), outputs=additions, inputs={}, pid=None)
            H._dump(hub / 'runtime.json', state)
    return hub, source


def _completed(stage, receipt, source):
    status = receipt.get('status')
    if stage == 'voice':
        return voice_passed(receipt)
    if stage == 'teacher' and (source['day'] in (receipt.get('refused_days') or {}) or
                               source['day'] in (receipt.get('waiting') or []) or
                               source['day'] in (receipt.get('root_waiting') or {})):
        return False
    if status in ('done', 'reused'):
        return True
    if stage == 'teacher' and status == 'skipped':
        # Native teacher uses skipped for already available whole-day rows.
        return (Path(source['rows']) / 'receipt.json').is_file()
    if not receipt.get('reason'):
        return False
    if status == 'not_run':
        return stage in ('search', 'exchange', 'jev', 'voice', 'batch_lessons', 'frankie_lessons')
    return status == 'skipped' and stage in (
        'classroom', 'batch_lessons', 'frankie_lessons', 'exchange', 'jev', 'voice', 'school', 'reports')


def _ready(state, required):
    return [p for p in required if state['operations'].get(p, {}).get('status') != 'complete']


def await_prerequisites(run, entry, required):
    """Wait only for live producers; a failed/saved producer remains recovery work."""
    import frankie_box_wake as W
    hub, _ = ensure(run, entry)
    paths = [hub]
    if run.stop_marker:
        paths.append(Path(run.stop_marker).parent)
    waiter = W.Waiter(paths)
    try:
        while True:
            run.check_save()
            state = _state(hub)
            missing = _ready(state, required)
            if not missing:
                return None
            operations = [state['operations'].get(p, {}) for p in missing]
            if any(o.get('status') != 'running' or active_pid(o) is None for o in operations):
                return dict(status='waiting', hub_pending=True,
                            reason='hub producer needs recovery: ' + ', '.join(missing))
            for operation in operations:
                waiter.watch_pid(active_pid(operation))
            waiter.wait()
            waiter.fired.clear()
    finally:
        waiter.close()


def run_stage(run, entry, stage, calculate):
    """Execute one native stage with durable binding and atomic hub publication.

    A waiting/saved/failed result never satisfies a prerequisite except the
    native queue's explicit nonblocking meeting outcomes. Different operations
    can calculate concurrently, but a duplicate operation cannot.
    """
    run.check_save()
    hub, source = ensure(run, entry)
    required = REQUIRES.get(stage, ())
    # Streaming block lessons have their own sealed per-block prerequisites.
    # Their native loop binds each block and never exposes a partial day as done.
    if stage == 'classroom' and run.sealed_blocks(entry['day'], any_state=True):
        required = ('root',)
    reader = hub / 'readers' / (stage + '-' + uuid.uuid4().hex + '.json')
    with H.turn(hub, H.CLEAN_PIECE):
        state = _state(hub)
        missing = _ready(state, required)
        if missing:
            return dict(status='waiting', hub_pending=True,
                        reason='hub prerequisites incomplete: ' + ', '.join(missing))
        old = state['operations'].get(stage) or {}
        if old.get('status') == 'running' and active_pid(old) is not None:
            return dict(status='waiting', hub_pending=True,
                        reason='hub operation already running: ' + stage)
        if old.get('reader'):
            with contextlib.suppress(FileNotFoundError):
                Path(old['reader']).unlink()
        bindings = {p: state['operations'][p]['signature'] for p in required}
        inputs = [a for p in required for a in state['operations'][p]['outputs']]
        inputs = [dict(a, stat=_stat(a['path'])) if a.get('path') else dict(a) for a in inputs]
        reader.parent.mkdir(exist_ok=True)
        H._dump(reader, dict(piece=stage, pid=os.getpid(), inputs=inputs,
                            role=stage, native_role_and_lesson_filters=True))
        state['operations'][stage] = dict(old, status='running', pid=os.getpid(),
            pid_start=H._pid_start(os.getpid()), inputs=bindings, reader=str(reader),
            started_utc=H.utc(), checkpoint='native stage checkpoint', recovery_pending=False)
        H._dump(hub / 'runtime.json', state)
        H.event(hub, 'operation-start', stage, inputs=bindings, reader=str(reader))
    _start_doctor(run, hub)
    previous_reader = getattr(_LOCAL, 'reader', None)
    _LOCAL.reader = reader
    result = None
    failure = None
    additions = None
    try:
        result = calculate()
        additions = (_outputs(stage, sources(run, entry), result)
                     if result and _completed(stage, result, source) else None)
        return result
    except BaseException as error:
        failure = error
        raise
    finally:
        _LOCAL.reader = previous_reader
        with H.turn(hub, stage) as token:
            state = _state(hub)
            operation = state['operations'][stage]
            status = (result or {}).get('status', 'failed')
            saved = run.save_requested() or (isinstance(failure, SystemExit) and failure.code == 75)
            changed = [p for p, signature in bindings.items()
                       if state['operations'].get(p, {}).get('signature') != signature]
            if additions is not None and operation.get('blocked_signature') == _signature(additions):
                changed.append('native publication still awaits its checked successor')
            inputs = (H._load(reader) or {}).get('inputs', inputs)
            for addition in inputs:
                if addition.get('path'):
                    try:
                        if _stat(addition['path']) != addition['stat']:
                            changed.append(addition['path'])
                    except OSError:
                        changed.append(addition['path'])
            complete = failure is None and additions is not None and not changed
            if complete:
                try:
                    H.write(hub, stage, token, additions)
                except BaseException as error:
                    operation.update(status='failed', pid=None, child_pid=None, recovery_pending=True,
                                     reason='hub publication failed: ' + str(error), ended_utc=H.utc())
                    H._dump(hub / 'runtime.json', state)
                    with contextlib.suppress(FileNotFoundError):
                        reader.unlink()
                    raise
                operation.update(status='complete', signature=_signature(additions), outputs=additions,
                                 completed_utc=H.utc(), recovery_pending=False, blocked_signature=None,
                                 changed_inputs=[])
            else:
                operation.update(status='saved' if saved else 'waiting' if status == 'waiting' else 'failed',
                    recovery_pending=not saved and status != 'waiting',
                    reason=str(failure) if failure else (result or {}).get('reason'), changed_inputs=changed)
                if changed and result is not None:
                    if additions is not None:
                        operation['blocked_signature'] = _signature(additions)
                    result.update(status='waiting', reason='hub bound inputs changed; native successor required: ' +
                                  ', '.join(changed), hub_pending=True)
                    operation.update(status='waiting', recovery_pending=False)
            operation.update(pid=None, child_pid=None, child_pid_start=None, ended_utc=H.utc())
            H._dump(hub / 'runtime.json', state)
            with contextlib.suppress(FileNotFoundError):
                reader.unlink()
            H.event(hub, 'operation-end', stage, status=operation['status'], changed_inputs=changed,
                    recovery_pending=operation['recovery_pending'])
