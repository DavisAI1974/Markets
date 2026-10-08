"""Stream a complete exact DIGEST_V6 document and publish only verified bytes."""
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import sys

import frankie_box_digest_render as DG
import frankie_box_digest_stream as TS
from frankie_box_digest_sources import BedrockSources


def _safe(path):
    path = Path(path).absolute()
    if '..' in path.parts or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('digest evidence path must not traverse links or parents')
    return path


def _witness(path):
    hashed, size = hashlib.sha256(), 0
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            hashed.update(block)
            size += len(block)
    return dict(bytes=size, sha256=hashed.hexdigest())


def _sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _save_new(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as output:
        json.dump(value, output, sort_keys=True, separators=(',', ':'))
        output.flush()
        os.fsync(output.fileno())
    _sync_directory(Path(path).parent)


class _Rows:
    """Replay the codec's exact private snapshot without an in-memory context."""
    def __init__(self, database):
        self.database = Path(database)

    def __iter__(self):
        db = sqlite3.connect(self.database.resolve().as_uri() + '?mode=ro', uri=True)
        try:
            yield from TS._rows(db, 'source')
        finally:
            db.close()


PARALLEL_SPOOL_MIN_BYTES = 64 << 20


def _parallel_spool(rows):
    """A closed legacy RowSpool big enough for the parallel table writer. By type name: the ROOT loads
    frankie_box_bedrock by path (boss_session._box_module), so its RowSpool class is not the imported module's."""
    return (type(rows).__name__ == 'RowSpool' and hasattr(rows, 'path') and getattr(rows, '_writer', None) is not None
            and rows._writer.closed and len(rows) > 0
            and Path(rows.path).stat().st_size >= PARALLEL_SPOOL_MIN_BYTES)


def lane_cpus():
    """The booked lane's CPUs (16 or 32), never the host count: FRANKIE_LANE_CPUS or FRANKIE_BOOKED_CPUS (cores'
    cpu_list) intersected with this process's affinity; the affinity alone when neither names a CPU of it."""
    affinity = set(os.sched_getaffinity(0))
    for name in ('FRANKIE_LANE_CPUS', 'FRANKIE_BOOKED_CPUS'):
        listed = set()
        try:
            for part in (os.environ.get(name) or '').split(','):
                if part.strip():
                    low, _, high = part.strip().partition('-')
                    listed.update(range(int(low), int(high or low) + 1))
        except ValueError:
            continue
        if listed & affinity:
            return sorted(listed & affinity)
    return sorted(affinity)


def per_second_rows(first, buys, sells, roll, window=20):
    """Same cumulative floating-point arithmetic as the compatibility renderer."""
    if len(buys) != len(sells) or len(buys) != len(roll) or window < 1:
        raise ValueError('flow array lengths/window differ')
    cb, cs = deque([0.0]), deque([0.0])
    for t in range(len(buys)):
        cb.append(cb[-1] + buys[t])
        cs.append(cs[-1] + sells[t])
        if len(cb) > window + 1:
            cb.popleft(); cs.popleft()
        b, s = cb[-1] - cb[0], cs[-1] - cs[0]
        z = b + s
        if z > 0:
            n, d = b - s, z
            frac = ('%d/%d' % (int(n), int(d))) if float(n).is_integer() and float(d).is_integer() else '%r/%r' % (n,d)
            if not (isinstance(roll[t], float) and float(n)/float(d) == roll[t]):
                raise ValueError('roll20 fraction does not reproduce producer float')
        else:
            frac = None
            if not (isinstance(roll[t], float) and math.isnan(roll[t])):
                raise ValueError('roll20 expected undefined')
        yield dict(second=first+t, buy=buys[t], sell=sells[t], roll20=frac)


TABLE_SAVE_SCHEMA = 'FRANKIE_DIGEST_TABLE_SAVE_V2'   # V2: every module that shapes a table, the inputs, sha256-checked reuse


def _code_identity():
    """The code whose change could change a table's bytes: the serializer and renderer (the format), and the code that
    produces the rows (the row readers over sources.sqlite, the per-second rows, the bedrock job transform, the parallel
    row reader). Orchestration (document assembly, save lookup, the parallel coordinator's scheduling) is not keyed, so
    a fix there reuses every finished table; the parallel writer's bytes equal write_table's by construction."""
    import inspect
    import frankie_box_digest_sources as S
    import frankie_box_digest_parallel as P
    code = {Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (TS, DG)}
    for name, obj in (('sources._Rows', S._Rows), ('sources._Members', S._Members), ('sources._decoded', S._decoded),
                      ('sources._compare_groups', S._compare_groups), ('sources.BedrockSources._rows', S.BedrockSources._rows),
                      ('document.per_second_rows', per_second_rows), ('document._bedrock_table_job', _bedrock_table_job),
                      ('parallel._source_rows', P._source_rows)):
        code[name] = hashlib.sha256(inspect.getsource(obj).encode()).hexdigest()
    # the member path correction the parallel row reader applies (a module constant, so not in _source_rows' source)
    code['parallel.MEMBER_LIST_PATHS'] = hashlib.sha256(json.dumps(sorted(P.MEMBER_LIST_PATHS.items())).encode()).hexdigest()
    return code


def _canonical(value):
    return json.loads(json.dumps(value, sort_keys=True))


# A legacy table is written by TS.write_table from the legacy layers: only the codec, the renderer and the per-second rows
# reach its bytes. The bedrock row readers in _code_identity key the bedrock tables only (2026-09-28: the members reader
# changed and must not rebuild the five legacy save points).
LEGACY_CODE = ('frankie_box_digest_stream.py', 'frankie_box_digest_render.py', 'document.per_second_rows')


def legacy_key(name, context, code, inputs):
    return _canonical(dict(kind='legacy', name=name, context=sorted(context or {}), code={k: code[k] for k in LEGACY_CODE},
                           inputs=inputs))


def _key_matches(stored, key):
    """A receipt's key equals this key. A legacy receipt written before legacy_key carries the whole code identity; it
    matches when its legacy code entries (and everything else) do."""
    if stored == key:
        return True
    if not (isinstance(stored, dict) and isinstance(key, dict) and key.get('kind') == 'legacy' and stored.get('kind') == 'legacy'
            and isinstance(stored.get('code'), dict) and all(k in stored['code'] for k in LEGACY_CODE)):
        return False
    return dict(stored, code={k: stored['code'][k] for k in LEGACY_CODE}) == key


def _saved_table(scratch, ordinal, key, context=False):
    """Save point for reruns: the table at this ordinal that an earlier digest attempt of this calculation root wrote,
    proved and receipted with exactly this key (name, inputs, code). A candidate is used only if its bytes (and, for a
    legacy table, its context database) hash to the receipt; otherwise the next candidate is tried or the table is
    rebuilt. Assembly hashes the reused bytes once more (_copy_verified)."""
    for receipt in sorted(scratch.parent.glob('.digest-*/table-%04d.save.json' % ordinal)):
        if receipt.parent == scratch:
            continue
        try:
            value = json.loads(receipt.read_bytes())
            if value.get('schema') != TABLE_SAVE_SCHEMA or not _key_matches(value.get('key'), key):
                continue
            path = _safe(value.get('path') or '')
            if path.parent != _safe(receipt.parent) or path.name != 'table-%04d.txt' % ordinal or not path.is_file():
                continue
            if _witness(path) != value.get('digest'):
                continue
            if context:
                database = path.parent/('table-%04d' % ordinal)/'table.sqlite'
                if not database.is_file() or _witness(database) != value.get('context'):
                    continue
        except (OSError, ValueError, TypeError, AttributeError):
            continue
        return dict(name=value['name'], rows=value['rows'], path=path, digest=value['digest'], saved=str(receipt))
    return None


def _save_table(scratch, ordinal, key, entry, context=None):
    _save_new(scratch/('table-%04d.save.json' % ordinal),
              dict(schema=TABLE_SAVE_SCHEMA, key=key, name=entry['name'], rows=entry['rows'],
                   path=str(entry['path']), digest=entry['digest'], context=context))


def _copy_verified(path, output, expected):
    """Copy a proved table into output, hashing what is read; output is a file or a _HashingWriter."""
    hashed, size = hashlib.sha256(), 0
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            hashed.update(block); size += len(block); output.write(block)
    if dict(bytes=size, sha256=hashed.hexdigest()) != expected:
        raise ValueError('verified table changed during document assembly')


def _bedrock_table_job(job):
    ordinal,name,spec,scratch = job
    import frankie_box_digest_sources as S
    scratch = Path(scratch)
    root,path = scratch/('table-%04d' % ordinal),scratch/('table-%04d.txt' % ordinal)
    db = sqlite3.connect(Path(spec['database']).resolve().as_uri()+'?mode=ro',uri=True)
    db.execute('PRAGMA cache_size=-2048')
    db.execute('PRAGMA temp_store=FILE')
    db.create_collation('group_order',S._compare_groups)
    try:
        if spec['kind']=='members':
            rows = S._Members(db)
        else:
            transform = None
            if spec['excluded'] is not None:
                transform = lambda row:{c:DG._spell(v) for c,v in row.items() if c not in spec['excluded']}
            rows = S._Rows(db,spec['query'],spec['parameters'],transform)
        proof = TS.write_table(path,name,rows,root)
        # write_table inverse-proves the actual emitted bytes. Copy-time hashing
        # below binds that proof to the same unmodified table; no second inverse.
        digest = _witness(path)
        if TS._identity(path) != proof['verified_identity']:
            raise ValueError('proved table changed before its byte witness')
        return dict(name=name,rows=proof['rows'],path=str(path),digest=digest)
    finally:
        db.close()


def bedrock_spec(rows, root):
    if type(rows).__name__ == '_Members':
        return dict(kind='members', database=str(Path(root) / 'sources.sqlite'))
    return dict(kind='rows', database=str(Path(root) / 'sources.sqlite'), query=rows.query,
                parameters=rows.parameters, excluded=getattr(rows, 'excluded', None))


def bedrock_key(name, code, layers_identity, spec):
    return _canonical(dict(kind='bedrock', name=name, code=code, layers=layers_identity,
                           spec={k: v for k, v in spec.items() if k != 'database'}))


def layers_identity_of(bedrock_entries):
    return {n: {k: e.get(k) for k in ('bytes', 'sha256')} for n, e in bedrock_entries.items()}


def open_sources(bedrock_entries, layers_root):
    """A finished sources.sqlite a stopped attempt of this calculation root left (receipted, unchanged) is reopened
    read-only; otherwise the sources are built."""
    import frankie_box_digest_parallel as P
    saved = P.saved_sources(bedrock_entries, layers_root)
    if saved is not None:
        return P.ReopenedSources(bedrock_entries, saved)
    return BedrockSources(bedrock_entries, layers_root)


class _HashingWriter:
    """The staged digest's writer: every byte handed to the file is also hashed, in the same order, so the stage's
    witness is known when the copy ends; the one read-back of the staged file is then compared with it."""
    def __init__(self, output):
        self.output, self.hasher, self.size = output, hashlib.sha256(), 0

    def write(self, data):
        self.output.write(data)
        self.hasher.update(data)
        self.size += len(data)

    def witness(self):
        return dict(bytes=self.size, sha256=self.hasher.hexdigest())


def _inode(path):
    """A file's identity for 'unchanged since its witness': device, inode, size and modification time (a hard link
    changes the link count and ctime only)."""
    info = os.stat(path)
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


LEGACY_TABLES = 5            # the legacy tables, always written: ordinals 0-4; the bedrock tables follow from 5
TABLE_THREADS = 4            # bedrock tables written at once on the shared helpers (FRANKIE_DIGEST_TABLE_THREADS)

# Greg, 2026-10-08, verbatim: "no! There we go dropping data like I said not to. We stream the data in and get 32 CPUs
# and workers on this job." Every frames row is rendered whole (the full depth, every price level and order id, the
# group's INPUT records): no top-ten form, no truncation, no sampling. The work is the HOW: one streamed decode of the
# frames spool on the booked lane (see the session-6 ROOT-dedupe record in E2E_ONE_DAY_20231018.md).


def _pin_thread(cpus):
    """Pin the calling thread (a Linux thread id; a new thread inherits its creator's CPUs) to cpus."""
    import threading
    os.sched_setaffinity(threading.get_native_id(), set(cpus))


def _topology_helpers():
    """cpu_topology and core_groups from frankie_box_boss_session (imported, never copied): the loaded module when the
    ROOT already holds it, else imported; (None, reason) when it cannot be imported."""
    for name in ('frankie_box_boss_session', 'deploy.aws.box.frankie_box_boss_session', '__main__'):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, 'cpu_topology') and hasattr(module, 'core_groups'):
            return module, None
    try:
        import frankie_box_boss_session as module
    except ImportError as error:
        return None, 'frankie_box_boss_session not importable (%s)' % error
    return module, None


def cpu_placement(lane):
    """Where the digest runs on the booked lane (Greg, 2026-10-07: every process pinned, nothing idle). The coordinator
    core is the physical core of lane[0]: the main thread (the serial tables: TS.write_table is one Python thread) is
    pinned to lane[0]; the coordinator-side threads (each parallel table's merge, copy and witness, the cross context,
    the bedrock sources build) to lane[0]'s second hardware thread; the shared helpers take one CPU each of every other
    core, one thread per core first, then the second threads. Without a readable topology: main on lane[0], side
    threads with it, helpers lane[1:]. Placement only: no byte, order or hash depends on it."""
    coordinator, cores, basis = lane[0], None, None
    module, problem = _topology_helpers()
    if module is not None:
        topology = module.cpu_topology(lane)
        if topology is not None:
            cores = module.core_groups(lane, topology)
        else:
            problem = 'sysfs topology unreadable'
    if cores:
        own = next(group for group in cores if coordinator in group)
        side = [cpu for cpu in own if cpu != coordinator]
        rest = [group for group in cores if group is not own]
        helpers = [group[0] for group in rest] + [cpu for group in rest for cpu in group[1:]]
        basis = ('physical cores: the coordinator core %s holds the main thread (%d) and the side threads (%s); one '
                 'helper per hardware thread of the other %d cores, first threads first'
                 % (own, coordinator, side[0] if side else coordinator, len(rest)))
    else:
        side, helpers = [], list(lane[1:])
        basis = 'booked list order (%s): main and side threads on %d, helpers the rest' % (problem, coordinator)
    if not helpers:
        helpers = list(lane)
    return dict(lane=list(lane), coordinator=coordinator, side=side[0] if side else coordinator, helpers=helpers,
                basis=basis)


def write_digest(destination, receipt, layers, prices, frames, structures, roll, first, buys, sells,
                 *, bedrock_entries, scratch_directory, disk_reserve=None):
    """Fresh destination only; all scratch retained, even after publication failure.

    disk_reserve: the bytes the parallel table writer keeps free on the scratch filesystem (a setting: the argument,
    else FRANKIE_DIGEST_DISK_RESERVE, else frankie_box_digest_parallel.DISK_RESERVE, 32 GiB on the box).

    Caller-owned flow arrays remain a separate memory boundary. Production layer
    files are independently pinned; only table/column metadata and one row/cell
    are retained in Python. No compatibility renderer/parser materializes tables.

    Schedule (Greg, 2026-10-07: the steps run at once on every booked CPU, every process pinned). Each table keeps its
    ordinal, its rows, its writer and its save point; only WHEN it is written changes, so the document (assembled in
    ordinal order) is the same bytes:
      - the save points are looked up first, in ordinal order, as an unbroken legacy prefix (as before);
      - every legacy table read from a big closed spool (legacy_book_imbalance) is written by the parallel writer on the
        shared pinned helpers in a side thread, its cross-table context (the columns legacy_structure_observables
        derives from it) built at the same time and first, from the same spool ranges;
      - the main thread (lane[0]) writes the serial tables in ordinal order, starting legacy_structure_observables as
        soon as that context exists instead of after the whole book table; table witnesses and save receipts are
        written by side threads;
      - the bedrock sources are built on a side thread from the start, and every bedrock table is written as soon as
        they exist, TABLE_THREADS at once, on the same helpers, beside the legacy tables;
      - the staged document is hashed as it is written and read back once (the intent and publication receipts reuse
        that witness for the same unchanged inode instead of reading the whole document twice more).
    A dead helper never stops a pass (frankie_box_digest_parallel.PinnedPool)."""
    import threading
    import time
    from concurrent.futures import ThreadPoolExecutor, wait as wait_all
    destination, scratch = _safe(destination), _safe(scratch_directory)
    if destination.exists():
        raise FileExistsError('existing digest evidence preserved')
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch.mkdir(parents=True, exist_ok=False, mode=0o700)
    db = sqlite3.connect(scratch/'families.sqlite')
    db.execute('PRAGMA cache_size=-2048')
    db.execute('PRAGMA temp_store=FILE')
    db.execute('PRAGMA mmap_size=0')
    db.execute('CREATE TABLE families (name TEXT PRIMARY KEY, count INTEGER, first_ordinal INTEGER)')

    counted = {}

    def counted_structures():
        for i, row in enumerate(structures):
            key = row['action_string']
            if not isinstance(key, str):
                raise ValueError('action_string must be a string')
            db.execute('INSERT INTO families VALUES (?,1,?) ON CONFLICT(name) DO UPDATE SET count=count+1', (key,i))
            yield row
        db.commit()
        counted['done'] = True

    def family_rows():
        # the families come from the structures pass; when that table was reused from a save point, count them here
        if not counted.get('done'):
            for _ in counted_structures():
                pass
        for key, count in db.execute('SELECT name,count FROM families ORDER BY count DESC,first_ordinal'):
            yield dict(action_string=key,count=count)

    code = _code_identity()
    # The legacy tables' inputs are the legacy layer files the derivation receipt witnessed (prices, frames, structures
    # and the per-second series are read from them), so their sha256s key every legacy table.
    legacy_inputs = {name: entry.get('sha256') for name, entry in sorted((receipt.get('layers') or {}).items())
                     if not entry.get('bedrock')}

    import frankie_box_digest_parallel as PP
    lane = lane_cpus()
    place = cpu_placement(lane)
    helper_cpus = place['helpers']
    # The part count every earlier digest used (one part per CPU of lane[1:]): the parts are positions in the rows, the
    # bytes do not depend on them, and keeping the count keeps every part spec (and its pass save point key) as before.
    parts = len(lane) - 1 if len(lane) > 1 else len(lane)
    reserve = disk_reserve if disk_reserve is not None else int(os.environ.get('FRANKIE_DIGEST_DISK_RESERVE', PP.DISK_RESERVE))
    table_threads = max(1, int(os.environ.get('FRANKIE_DIGEST_TABLE_THREADS') or TABLE_THREADS))
    notes, timeline = [], []

    def timed(ordinal, name, mode):
        entry = dict(ordinal=ordinal, name=name, mode=mode, started=time.time(), ended=None,
                     cpus=[place['coordinator']] if mode == 'serial' else
                     [place['side']] + list(helper_cpus) if mode.startswith('parallel') else [place['side']])
        timeline.append(entry)
        return entry

    original_affinity = os.sched_getaffinity(0)
    _pin_thread({place['coordinator']})
    pool = PP.PinnedPool(helper_cpus, label='digest table helpers', note=notes.append)
    side = ThreadPoolExecutor(max_workers=8, thread_name_prefix='digest-side', initializer=_pin_thread,
                              initargs=({place['side']},))
    bedrock_jobs = ThreadPoolExecutor(max_workers=table_threads, thread_name_prefix='digest-bedrock',
                                      initializer=_pin_thread, initargs=({place['side']},))
    futures = []
    legacy_stages = [None] * LEGACY_TABLES
    built, bedrock = {}, dict(stages=[], header=None, futures=[])

    # ---- legacy save points: an unbroken prefix, looked up in ordinal order (as the serial order did)
    rows_of = [lambda: prices, lambda: per_second_rows(first,buys,sells,roll), lambda: frames,
               counted_structures, family_rows]
    names = ['legacy_price', 'per_second_flow_and_roll20', 'legacy_book_imbalance', 'legacy_structure_observables',
             'structure_families']
    context_of = [None, None, None, ('legacy_book_imbalance',), None]
    contexts = {}
    reused = 0
    for ordinal, name in enumerate(names):
        saved = _saved_table(scratch, ordinal, legacy_key(name, context_of[ordinal], code, legacy_inputs), context=True)
        if saved is None:
            break
        legacy_stages[ordinal] = dict(name=saved['name'], rows=saved['rows'], path=Path(saved['path']), digest=saved['digest'])
        contexts[name] = _Rows(Path(saved['path']).parent/('table-%04d' % ordinal)/'table.sqlite')
        timeline.append(dict(ordinal=ordinal, name=name, mode='reused', saved=saved['saved']))
        reused += 1

    def finish_serial(ordinal, name, key, rows, path, root, identity):
        digest = _witness(path)
        if TS._identity(path) != identity:
            raise ValueError('proved table changed before its byte witness')
        legacy_stages[ordinal] = dict(name=name, rows=rows, path=path, digest=digest)
        _save_table(scratch, ordinal, key, legacy_stages[ordinal], context=_witness(root/'table.sqlite'))

    def serial_table(ordinal, name, rows, context):
        root = scratch/('table-%04d' % ordinal)
        path = scratch/('table-%04d.txt' % ordinal)
        key = legacy_key(name, context, code, legacy_inputs)
        entry = timed(ordinal, name, 'serial')
        proof = TS.write_table(path, name, rows, root, context=context)
        if TS._identity(path) != proof['verified_identity']:
            raise ValueError('proved table changed before its byte witness')
        entry['ended'] = time.time()
        # the byte witness and save receipt bind the same unchanged file on a side thread; the main thread goes on
        futures.append(side.submit(finish_serial, ordinal, name, key, proof['rows'], path, root, proof['verified_identity']))
        return _Rows(root/'table.sqlite')

    def cross_columns_of(name):
        return sorted({col for (_, _), (source, col) in DG.CROSS_DERIVED.items() if source == name})

    def context_db(ordinal, name, context_rows, mode):
        # the context database in the serial writer's form (table 'source', TS._dump rows) holding the columns later
        # tables derive from this one; empty when none does
        entry = timed(ordinal, name + ' (context)', mode)
        root = scratch/('table-%04d' % ordinal)
        root.mkdir(parents=True, exist_ok=False)
        cdb = sqlite3.connect(root/'table.sqlite')
        try:
            cdb.execute('CREATE TABLE source (ordinal INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
            for i, row in enumerate(context_rows):
                cdb.execute('INSERT INTO source VALUES (?, ?)', (i, TS._dump(row)))
            cdb.commit()
        finally:
            cdb.close()
        entry['ended'] = time.time()
        return _Rows(root/'table.sqlite'), _witness(root/'table.sqlite')

    def context_job(ordinal, name, specs):
        columns = cross_columns_of(name)
        return context_db(ordinal, name, PP.cross_context(specs, columns, helper_cpus, pool=pool) if columns else (),
                          'parallel-context')

    def parallel_table(ordinal, name, rows, specs, context_future, fused=None):
        # A big legacy table read from a closed RowSpool (the frame sections make legacy_book_imbalance hundreds of GB
        # on a full day) is written by the parallel table writer: the same bytes and inverse proof as TS.write_table over
        # the same rows (frankie_box_digest_parallel), each helper reading its own line range of the spool (never held
        # whole). Every field and row is kept; nothing is reduced. Session 6 (Greg: "We stream the data in and get 32
        # CPUs and workers on this job"): with FRANKIE_DIGEST_FUSE_CONTEXT=on the cross-table context is collected by
        # the writer's own snapshot decode (fused: a Future resolved from inside the writer) instead of a decode of its
        # own; the writer's other reductions (one_decode, canonical_verify) are its run settings (PP.PASS_SETTINGS).
        entry = timed(ordinal, name, 'parallel')
        path = scratch/('table-%04d.txt' % ordinal)
        key = legacy_key(name, None, code, legacy_inputs)
        columns = cross_columns_of(name) if fused is not None else None

        def on_cross(context_rows):
            try:
                fused.set_result(context_db(ordinal, name, context_rows, 'parallel-context (fused into the snapshot pass)'))
            except BaseException as error:  # noqa: BLE001 - the waiting serial table sees the error, never a hang
                fused.set_exception(error)
                raise
        try:
            proof = PP.write_table_parallel(path, name, specs, scratch/('table-%04d.parallel' % ordinal), helper_cpus,
                                            reserve=reserve, pool=pool, cross_columns=columns,
                                            on_cross=on_cross if fused is not None else None)
        except BaseException as error:
            if fused is not None and not fused.done():
                fused.set_exception(error)
            raise
        if proof['rows'] != len(rows):
            raise ValueError('parallel legacy table rows differ from the spool count')
        digest = _witness(path)
        if TS._identity(path) != proof['verified_identity']:
            raise ValueError('proved table changed before its byte witness')
        _, context_witness = (fused if fused is not None else context_future).result()
        legacy_stages[ordinal] = dict(name=name, rows=proof['rows'], path=path, digest=digest)
        _save_table(scratch, ordinal, key, legacy_stages[ordinal], context=context_witness)
        entry['passes'] = proof.get('passes')          # the writer's pass reductions, on the proof's timeline
        entry['ended'] = time.time()

    def bedrock_table(index, ordinal, name, spec, key):
        # Every bedrock table is written by the parallel writer on the shared helpers (same bytes as write_table; Greg
        # 2026-09-28: no table runs for hours on one core), TABLE_THREADS tables at once. The parts come from the table's
        # specs at the part count every earlier digest used, never from the CPU list.
        entry = timed(ordinal, name, 'parallel-bedrock')
        path = scratch / ('table-%04d.txt' % ordinal)
        proof = PP.write_table_parallel(path, name, PP.split_specs(spec, parts), scratch / ('table-%04d' % ordinal),
                                        helper_cpus, reserve=reserve, pool=pool)
        digest = _witness(path)
        if TS._identity(path) != proof['verified_identity']:
            raise ValueError('proved table changed before its byte witness')
        bedrock['stages'][index] = dict(name=name, rows=proof['rows'], path=path, digest=digest)
        _save_table(scratch, ordinal, key, bedrock['stages'][index])
        entry['ended'] = time.time()

    # The bedrock sources (layer preparation and member merge, on the pinned helpers) are independent of the legacy
    # tables: built on a side thread from the start; each bedrock table is queued as soon as they exist.
    def build_sources():
        try:
            _pin_thread({place['side']})
            sources = built['sources'] = open_sources(bedrock_entries, scratch/'calculation-layers')
            bedrock['header'] = DG.bedrock_header(sources.derived, sources.layer_count, sources.verdict or {})
            layers_identity = layers_identity_of(bedrock_entries)
            tables = list(sources.tables.items())
            bedrock['stages'] = [None] * len(tables)
            for index, (name, rows) in enumerate(tables):
                ordinal = LEGACY_TABLES + index
                spec = bedrock_spec(rows, sources.root)
                key = bedrock_key(name, code, layers_identity, spec)
                saved = _saved_table(scratch, ordinal, key)
                if saved is not None:
                    bedrock['stages'][index] = dict(name=saved['name'], rows=saved['rows'], path=Path(saved['path']),
                                                    digest=saved['digest'])
                    timeline.append(dict(ordinal=ordinal, name=name, mode='reused', saved=saved['saved']))
                    continue
                bedrock['futures'].append(bedrock_jobs.submit(bedrock_table, index, ordinal, name, spec, key))
        except BaseException as error:
            built['error'] = error
    builder = threading.Thread(target=build_sources, name='bedrock-sources') if bedrock_entries else None
    failed = True
    try:
        if builder is not None:
            builder.start()
        # ---- the legacy tables after the saved prefix: the parallel ones (and their contexts, first) to the side
        # threads now; then the serial ones on the main thread in ordinal order
        rows = {ordinal: rows_of[ordinal]() for ordinal in range(reused, LEGACY_TABLES)}
        parallel = {ordinal for ordinal in rows
                    if context_of[ordinal] is None and _parallel_spool(rows[ordinal]) and parts > 1}
        fuse = PP.pass_modes()['fuse_context']
        for ordinal in sorted(parallel):
            specs = PP.spool_specs(rows[ordinal].path, parts)
            if fuse and cross_columns_of(names[ordinal]):
                from concurrent.futures import Future
                fused = Future()                 # resolved by the writer's snapshot pass (parallel_table.on_cross)
                contexts[names[ordinal]] = fused
                futures.append(side.submit(parallel_table, ordinal, names[ordinal], rows[ordinal], specs, None, fused))
                continue
            context_future = side.submit(context_job, ordinal, names[ordinal], specs)
            contexts[names[ordinal]] = context_future
            futures.append(context_future)
            futures.append(side.submit(parallel_table, ordinal, names[ordinal], rows[ordinal], specs, context_future))
        for ordinal in sorted(set(rows) - parallel):
            context = None
            if context_of[ordinal] is not None:
                context = {}
                for source in context_of[ordinal]:
                    held = contexts[source]
                    context[source] = held.result()[0] if hasattr(held, 'result') else held
            made = serial_table(ordinal, names[ordinal], rows[ordinal], context)
            contexts[names[ordinal]] = made
        if builder is not None:
            builder.join()
            if 'error' in built:
                raise built['error']
        for future in list(futures) + list(bedrock['futures']):
            future.result()
        stages = list(legacy_stages) + list(bedrock['stages'])
        if any(entry is None for entry in stages):
            raise ValueError('a digest table has no proved stage')
        legacy_count = LEGACY_TABLES
        layer_header = bedrock['header'] if bedrock_entries else None
        stage = scratch/'digest.pending'
        with stage.open('xb') as output:
            sink = _HashingWriter(output)
            sink.write(DG.digest_header(receipt).encode('utf-8'))
            for i, entry in enumerate(stages):
                if i == legacy_count and layer_header is not None:
                    sink.write(layer_header.encode('utf-8'))
                elif i:
                    sink.write(b'\n')
                _copy_verified(entry['path'], sink, entry['digest'])
            output.flush()
            os.fsync(output.fileno())
        staged = sink.witness()
        # session 6 (Greg, 2026-10-08: "we only do 1 pass"): the staged document's witness is its write-stream hash; the
        # read-back pass is kept only under FRANKIE_DURABLE_READBACK=on (frankie_box_durable's switch), otherwise the
        # size on disk is checked against the bytes written. The published inode is remembered by frankie_box_filehash
        # so the ROOT's receipt pin and _measure_digest cost no read of the digest either.
        if os.environ.get('FRANKIE_DURABLE_READBACK', 'off') == 'on':
            if _witness(stage) != staged:
                raise ValueError('staged digest read back differs from the bytes written')
        elif os.stat(stage).st_size != staged['bytes']:
            raise ValueError('staged digest size on disk differs from the bytes written')
        staged_inode = _inode(stage)
        result = dict(schema='FRANKIE_STREAMED_DIGEST_V1', path=str(destination), verified=True,
                      **staged, tables=[dict(name=e['name'],rows=e['rows'],**e['digest']) for e in stages],
                      scratch_directory=str(scratch),
                      cpu_schedule=dict(schema='FRANKIE_DIGEST_CPU_SCHEDULE_V1', placement=place, parts=parts,
                                        table_threads=table_threads, helpers=pool.record(), notes=list(notes),
                                        timeline=sorted(timeline, key=lambda e: (e['ordinal'], e['name'])),
                                        stage_witness='hashed as written (read back once only under '
                                        'FRANKIE_DURABLE_READBACK=on; session 6); the intent and the publication '
                                        'reuse it for the same unchanged inode'))
        _save_new(scratch/'verification-receipt.json', result)
        if _inode(stage) != staged_inode:
            raise ValueError('staged digest changed after its witness')
        _save_new(scratch/'publication-intent.json',
                  dict(schema='FRANKIE_DIGEST_PUBLICATION_INTENT_V1',source=str(stage),destination=str(destination),
                       proof=_witness(scratch/'verification-receipt.json'),**staged))
        # Same-filesystem link creates the public name atomically and refuses an
        # existing name. The verified scratch inode is retained as evidence.
        os.link(stage, destination)
        _sync_directory(destination.parent)
        if _inode(destination) != staged_inode:
            raise ValueError('published digest is not the verified staged inode')
        try:
            import frankie_box_filehash
            frankie_box_filehash.remember(destination, staged)      # session 6: no later witness() reads the digest
        except (ImportError, AttributeError):
            pass
        _save_new(scratch/'publication-receipt.json',
                  dict(schema='FRANKIE_DIGEST_PUBLICATION_V1',destination=str(destination),
                       intent=_witness(scratch/'publication-intent.json'),**staged,
                       witness_basis='the verified staged inode (device, inode, bytes, mtime unchanged since its '
                                     'read-back); the same bytes are not read a third time'))
        failed = False
        return result
    finally:
        # every side thread and table job ends before this returns or raises (a finished table keeps its save point
        # for a rerun; queued bedrock tables are not started after a failure)
        if builder is not None and builder.is_alive():
            builder.join()
        side.shutdown(wait=True, cancel_futures=failed)
        bedrock_jobs.shutdown(wait=True, cancel_futures=failed)
        wait_all(list(futures) + list(bedrock['futures']))
        pool.close()
        if built.get('sources') is not None:
            built.pop('sources').close()
        db.close()
        os.sched_setaffinity(threading.get_native_id(), original_affinity)
