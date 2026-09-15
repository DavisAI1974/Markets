"""Independent Sunday snapshot verification. Never publishes local launch gates."""
import argparse
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict
import hashlib
import importlib
import json
import multiprocessing
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import time
import types

sys.dont_write_bytecode = True
PACKAGE = 'research.kalshi.frankie_boss'
ADAPTER = 'ng_exhaustion_mbo_v4_state_adapter_20260820.py'
CODE_FILES = tuple(name + '.py' for name in (
    'c15_builder', 'c15_observer', 'c15_journal', 'c15_registry', 'causal_prefix',
    'causal_prefix_records', 'causal_packet', 'mbo_resume_state',
    'source_conformance', 'selected_source_scope', 'raw_mbo_source_manifest')) + (ADAPTER,)
REQUIRED = ('source.sqlite', 'checkpoint.json', 'checkpoint-receipt.json', 'manifest.json') + tuple(
    'code/' + name for name in CODE_FILES)
EXPECTED = dict(journal_count=114054, next_cursor=57027,
    sha256='750dbb3c63ab672614323dca0dd7f363847ea78aa8a489d0f0b84afe8f00bcf7',
    state_hash='d46ec93352cfa63fab20e260bb608b0b76e71e5ca10cacd952de6b912bea2d64',
    scope_hash='7460b51959b35bd079e5e3c31012a6694388c2ff7a26e6f56af6ef30d008caa2',
    journal_hash='d8de0394367b66ea034d2553c3dd45fb7b1ae2b3c92724f8817627118f173500',
    source_prefix_hash='39270e89d94b62be8274ac406bbb8130d4c6cf5df011bf2373a5002e7a5f6699')


def sha256(path, emit=None):
    digest, count, last = hashlib.sha256(), 0, time.monotonic()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
            count += len(chunk)
            if emit and time.monotonic() - last >= 10:
                emit(dict(phase='physical_hash', file=Path(path).name, bytes=count))
                last = time.monotonic()
    return digest.hexdigest()


def verify_files(root, material, required, emit):
    files = material['files']
    if not isinstance(files, dict) or not set(required).issubset(files):
        raise ValueError('bundle is missing required pinned files')
    for name, pin in files.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts or '\\' in name or ':' in name:
            raise ValueError('unsafe bundle member name')
        path = root.joinpath(*relative.parts)
        if (path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve())
                or type(pin['bytes']) is not int or path.stat().st_size != pin['bytes']
                or sha256(path, emit) != pin['sha256']):
            raise ValueError('bundle member bytes differ: ' + name)


def load_code(code, destination):
    """Preserve source bytes and expected paths; do not execute package __init__."""
    package = destination / 'research' / 'kalshi' / 'frankie_boss'
    package.mkdir(parents=True, exist_ok=False)
    for name in CODE_FILES:
        target = destination / 'research' / name if name == ADAPTER else package / name
        shutil.copyfile(code / name, target)
    return bind_code(destination)


def bind_code(destination):
    package = destination / 'research' / 'kalshi' / 'frankie_boss'
    for name, path in [('research', destination / 'research'),
                       ('research.kalshi', destination / 'research' / 'kalshi'),
                       (PACKAGE, package)]:
        if name in sys.modules:
            raise ValueError('verification requires an isolated Python process')
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules[name] = module
    return importlib.import_module(PACKAGE + '.source_conformance')


def worker_init(runtime):
    global worker_journal
    bind_code(Path(runtime))
    worker_journal = importlib.import_module(PACKAGE + '.c15_journal')


def verify_row(row, previous, count):
    """Exact per-row predicates from original EvidenceJournal.entries()."""
    ordinal, kind, body, digest = row
    module = worker_journal
    envelope = module.unpack(json.loads(body))
    if (body != module.canonical_bytes(module.pack(envelope))
            or ordinal != count or envelope['ordinal'] != ordinal
            or envelope['schema'] != module.SCHEMA or envelope['kind'] != kind
            or envelope['previous_hash'] != previous
            or module.evidence_hash(envelope) != digest):
        raise ValueError('evidence journal continuity or hash mismatch')
    return envelope


def parallel_entries(journal, pool, workers, journal_module):
    """Bounded work queue; result order and chain boundaries remain sequential."""
    rows = iter(journal.connection.execute('SELECT ordinal,kind,body,digest FROM entries ORDER BY ordinal'))
    pending = deque()
    previous, submitted, delivered = journal_module.evidence_hash(dict(schema=journal_module.SCHEMA)), 0, 0

    def submit_next():
        nonlocal previous, submitted
        row = next(rows, None)
        if row is None:
            return False
        pending.append(pool.submit(verify_row, row, previous, submitted))
        previous, submitted = row[3], submitted + 1
        return True

    for _ in range(2 * workers):
        if not submit_next():
            break
    while pending:
        envelope = pending.popleft().result()
        delivered += 1
        yield envelope
        submit_next()
    if delivered != journal.count or previous != journal.head_hash:
        raise ValueError('evidence journal changed during iteration')
    # Strengthen change detection after the cursor releases its read snapshot.
    tail = journal.connection.execute('SELECT ordinal,digest FROM entries ORDER BY ordinal DESC LIMIT 1').fetchone()
    actual_tail = (tail[0] + 1, tail[1]) if tail else (0, journal_module.evidence_hash(dict(schema=journal_module.SCHEMA)))
    if actual_tail != (journal.count, journal.head_hash):
        raise ValueError('evidence journal changed during iteration')


def verify_state(database, state, scope, modules, emit, workers=1):
    """Original restore/conformance; exact row predicates run on ordered workers."""
    if type(workers) is not int or workers < 1:
        raise ValueError('positive verification worker count required')
    journal_module = importlib.import_module(PACKAGE + '.c15_journal')
    builder_module = importlib.import_module(PACKAGE + '.c15_builder')
    original_entries = journal_module.EvidenceJournal.entries
    phase = 'journal_restore'

    def counted_entries(journal):
        count, last = 0, time.monotonic()
        emit(dict(phase=phase, status='pass_started', entries=0, total=state['journal_count']))
        for entry in parallel_entries(journal, pool, workers, journal_module):
            count += 1
            if count % 1000 == 0 or time.monotonic() - last >= 10:
                emit(dict(phase=phase, status='advancing', entries=count, total=state['journal_count']))
                last = time.monotonic()
            yield entry
        emit(dict(phase=phase, status='pass_complete', entries=count, total=state['journal_count']))

    runtime = Path(modules.__file__).parents[3]
    pool = ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'),
        initializer=worker_init, initargs=(str(runtime),))
    journal_module.EvidenceJournal.entries = counted_entries
    builder = None
    try:
        builder = builder_module.C15Builder.restore(scope, database, state, expected_hash=state['state_hash'])
        # C15Builder.restore executes the original full journal pass plus exact
        # adapter/prefix roundtrip. The second pass is the original complete().
        builder.journal.connection.execute('PRAGMA query_only=1')
        driver = modules.SourceConformanceDriver.__new__(modules.SourceConformanceDriver)
        driver._builder = builder
        driver._stopped = driver._completed = driver._closed = False
        phase = 'source_conformance'
        return driver.complete()
    finally:
        journal_module.EvidenceJournal.entries = original_entries
        if builder is not None:
            builder.journal.close()
        pool.shutdown(wait=True, cancel_futures=True)


def write_once(path, value):
    with path.open('xb') as stream:
        stream.write(json.dumps(value, sort_keys=True, separators=(',', ':')).encode())
        stream.flush()
        os.fsync(stream.fileno())


def run(bundle, output, workers):
    bundle, output = bundle.resolve(), output.resolve()
    if output == bundle or output.is_relative_to(bundle) or bundle.is_relative_to(output):
        raise ValueError('bundle and output must be separate directories')
    output.mkdir(parents=True, exist_ok=False)
    started = time.time()

    def emit(value):
        print(json.dumps(dict(value, unix=time.time()), sort_keys=True), flush=True)

    try:
        material = json.loads((bundle / 'bundle-manifest.json').read_bytes())
        emit(dict(phase='bundle_validation', status='started'))
        verify_files(bundle, material, REQUIRED, emit)
        # An online backup is a standalone database. Sidecars must not secretly
        # supply extra evidence that is absent from the manifest's physical pin.
        if any((bundle / ('source.sqlite' + suffix)).exists() for suffix in ('-wal', '-shm', '-journal')):
            raise ValueError('snapshot has unexpected SQLite sidecars')
        checkpoint_raw = (bundle / 'checkpoint.json').read_bytes()
        checkpoint_receipt = json.loads((bundle / 'checkpoint-receipt.json').read_bytes())
        if any(checkpoint_receipt.get(key) != value for key, value in EXPECTED.items()):
            raise ValueError('checkpoint differs from independently pinned terminal source')
        if hashlib.sha256(checkpoint_raw).hexdigest() != EXPECTED['sha256']:
            raise ValueError('checkpoint bytes differ from terminal pin')
        modules = load_code(bundle / 'code', output / 'runtime')
        journal = importlib.import_module(PACKAGE + '.c15_journal')
        selected = importlib.import_module(PACKAGE + '.selected_source_scope')
        manifest = json.loads((bundle / 'manifest.json').read_bytes())
        scope = selected.source_scope(manifest, expected_manifest_hash=manifest['manifest_hash'])
        state = journal.unpack(json.loads(checkpoint_raw))
        if (state['state_hash'] != EXPECTED['state_hash']
                or state['journal_count'] != EXPECTED['journal_count']
                or state['journal_hash'] != EXPECTED['journal_hash']
                or scope.genesis_hash() != EXPECTED['scope_hash']):
            raise ValueError('terminal state differs from checkpoint receipt')
        emit(dict(phase='parallel_verification', worker_processes=workers, parent_processes=1,
                  max_in_flight_rows=workers * 2))
        completion = verify_state(bundle / 'source.sqlite', state, scope, modules, emit, workers)
        expected_completion = dict(schema='BOSS_SOURCE_CONFORMANCE_V1', scope_kind=scope.kind.value,
            scope_hash=EXPECTED['scope_hash'], record_count=57027, member_counts=(57027,),
            group_count=43569, source_prefix_hash=EXPECTED['source_prefix_hash'],
            journal_count=EXPECTED['journal_count'], journal_hash=EXPECTED['journal_hash'],
            builder_state_hash=EXPECTED['state_hash'])
        if asdict(completion) != expected_completion:
            raise ValueError('verified completion differs from full Sunday terminal identity')
        physical = sha256(bundle / 'source.sqlite', emit)
        if physical != material['files']['source.sqlite']['sha256']:
            raise ValueError('snapshot physical bytes changed during verification')
        receipt = dict(schema='GITHUB_INDEPENDENT_SOURCE_VERIFICATION_V1', status='verified',
            gate_authority=False, model_calls=0, started_unix=started, completed_unix=time.time(),
            verification_method='ORIGINAL_C15_RESTORE_AND_CONFORMANCE_WITH_ORDERED_PARALLEL_EXACT_ROW_CHECKS',
            worker_processes=workers, max_in_flight_rows=workers * 2,
            verified_journal_passes=2, completion=asdict(completion), completion_digest=completion.digest,
            snapshot_sha256=physical, snapshot_bytes=material['files']['source.sqlite']['bytes'],
            checkpoint_sha256=EXPECTED['sha256'], checkpoint_state_hash=EXPECTED['state_hash'],
            bundle_manifest_sha256=sha256(bundle / 'bundle-manifest.json'),
            runner_sha256=sha256(Path(__file__)), code_files={
                name: material['files']['code/' + name] for name in CODE_FILES},
            python=sys.version, workflow_run_id=os.environ.get('GITHUB_RUN_ID'),
            workflow_run_attempt=os.environ.get('GITHUB_RUN_ATTEMPT'))
        write_once(output / 'verification-receipt.json', receipt)
        emit(dict(phase='verified', completion_digest=completion.digest, gate_authority=False))
        return receipt
    except BaseException as exc:
        write_once(output / 'verification-failure.json', dict(schema='GITHUB_INDEPENDENT_SOURCE_VERIFICATION_FAILURE_V1',
            error_type=type(exc).__name__, message=str(exc), gate_authority=False, unix=time.time()))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=max(1, (os.cpu_count() or 1) - 1))
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('--workers must be positive')
    run(args.bundle_dir, args.output_dir, args.workers)
