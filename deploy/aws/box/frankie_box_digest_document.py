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


def write_digest(destination, receipt, layers, prices, frames, structures, roll, first, buys, sells,
                 *, bedrock_entries, scratch_directory, disk_reserve=None):
    """Fresh destination only; all scratch retained, even after publication failure.

    disk_reserve: the bytes the parallel table writer keeps free on the scratch filesystem (a setting: the argument,
    else FRANKIE_DIGEST_DISK_RESERVE, else frankie_box_digest_parallel.DISK_RESERVE, 32 GiB on the box).

    Caller-owned flow arrays remain a separate memory boundary. Production layer
    files are independently pinned; only table/column metadata and one row/cell
    are retained in Python. No compatibility renderer/parser materializes tables.
    """
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
    stages = []

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
    reusing = {'legacy': True}

    def table(name, rows, context=None):
        ordinal = len(stages)
        if context is None and _parallel_spool(rows) and len(helper_cpus) > 1:
            return parallel_table(ordinal, name, rows)
        root = scratch/('table-%04d' % ordinal)
        path = scratch/('table-%04d.txt' % ordinal)
        key = legacy_key(name, context, code, legacy_inputs)
        # Legacy tables are reused only as an unbroken prefix, so a context table is always the one actually used.
        saved = _saved_table(scratch, ordinal, key, context=True) if reusing['legacy'] else None
        if saved is not None:
            stages.append(dict(name=saved['name'], rows=saved['rows'], path=Path(saved['path']), digest=saved['digest']))
            return _Rows(Path(saved['path']).parent/('table-%04d' % ordinal)/'table.sqlite')
        reusing['legacy'] = False
        proof = TS.write_table(path, name, rows, root, context=context)
        original = _Rows(root/'table.sqlite')
        # Bind write_table's actual inverse proof to unchanged bytes; assembly
        # independently hashes those bytes while copying.
        digest = _witness(path)
        if TS._identity(path) != proof['verified_identity']:
            raise ValueError('proved table changed before its byte witness')
        stages.append(dict(name=name, rows=proof['rows'], path=path, digest=digest))
        _save_table(scratch, ordinal, key, stages[-1], context=_witness(root/'table.sqlite'))
        return original

    # A big legacy table read from a closed RowSpool (the frame sections make legacy_book_imbalance hundreds of GB on a
    # full day) is written by the parallel table writer on the booked lane's CPUs, as the bedrock tables are: the same
    # bytes and inverse proof as TS.write_table over the same rows (frankie_box_digest_parallel), each helper reading its
    # own line range of the spool (never held whole). Every field and row is kept; nothing is reduced. Its save point and
    # its cross-table context (the columns a later table derives from it, DG.CROSS_DERIVED) are kept as the serial
    # table's are, so the structures table that follows reads the same context values.
    import frankie_box_digest_parallel as PP
    lane = lane_cpus()
    helper_cpus = lane[1:] if len(lane) > 1 else lane

    def parallel_table(ordinal, name, rows):
        root = scratch/('table-%04d' % ordinal)
        path = scratch/('table-%04d.txt' % ordinal)
        key = legacy_key(name, None, code, legacy_inputs)
        saved = _saved_table(scratch, ordinal, key, context=True) if reusing['legacy'] else None
        if saved is not None:
            stages.append(dict(name=saved['name'], rows=saved['rows'], path=Path(saved['path']), digest=saved['digest']))
            return _Rows(Path(saved['path']).parent/('table-%04d' % ordinal)/'table.sqlite')
        reusing['legacy'] = False
        specs = PP.spool_specs(rows.path, len(helper_cpus))
        reserve = disk_reserve if disk_reserve is not None else int(os.environ.get('FRANKIE_DIGEST_DISK_RESERVE', PP.DISK_RESERVE))
        proof = PP.write_table_parallel(path, name, specs, scratch/('table-%04d.parallel' % ordinal), helper_cpus,
                                        reserve=reserve)
        if proof['rows'] != len(rows):
            raise ValueError('parallel legacy table rows differ from the spool count')
        digest = _witness(path)
        if TS._identity(path) != proof['verified_identity']:
            raise ValueError('proved table changed before its byte witness')
        # the context database in the serial writer's form (table 'source', TS._dump rows) holding the columns later
        # tables derive from this one; empty when none does
        columns = sorted({col for (_, _), (source, col) in DG.CROSS_DERIVED.items() if source == name})
        root.mkdir(parents=True, exist_ok=False)
        db = sqlite3.connect(root/'table.sqlite')
        try:
            db.execute('CREATE TABLE source (ordinal INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
            if columns:
                for i, row in enumerate(PP.cross_context(specs, columns, helper_cpus)):
                    db.execute('INSERT INTO source VALUES (?, ?)', (i, TS._dump(row)))
            db.commit()
        finally:
            db.close()
        stages.append(dict(name=name, rows=proof['rows'], path=path, digest=digest))
        _save_table(scratch, ordinal, key, stages[-1], context=_witness(root/'table.sqlite'))
        return _Rows(root/'table.sqlite')

    # The bedrock sources (layer preparation and member merge, on the pinned helpers) are independent of the five
    # sequential legacy tables: build them on a thread while the legacy tables are written, then join.
    import threading
    built = {}
    def build_sources():
        try:
            built['sources'] = open_sources(bedrock_entries, scratch/'calculation-layers')
        except BaseException as error:
            built['error'] = error
    builder = threading.Thread(target=build_sources, name='bedrock-sources') if bedrock_entries else None
    if builder is not None:
        builder.start()
    try:
        try:
            table('legacy_price', prices)
            table('per_second_flow_and_roll20', per_second_rows(first,buys,sells,roll))
            book = table('legacy_book_imbalance', frames)
            table('legacy_structure_observables', counted_structures(), {'legacy_book_imbalance':book})
            table('structure_families', family_rows())
        finally:
            if builder is not None:
                builder.join()
                if 'error' in built:
                    raise built['error']
        legacy_count = len(stages)
        layer_header = None
        if bedrock_entries:
            with built.pop('sources') as sources:
                layer_header = DG.bedrock_header(sources.derived, sources.layer_count, sources.verdict or {})
                import frankie_box_digest_parallel as P
                # Every bedrock table is written by the parallel writer on the helper cores (same bytes as write_table;
                # Greg 2026-09-28: no table runs for hours on one core). Finished tables are reused from their save points.
                # every CPU but 0-1 (Greg, 2026-09-28: pin workers to CPUs so none sit idle; was 2-15 only). The bytes do
                # not depend on the count: the parts come from the table's specs, not from the CPU list.
                cpus = helper_cpus             # the booked lane after its coordinator CPU (16 or 32 booked)
                layers_identity = layers_identity_of(bedrock_entries)
                for name, rows in sources.tables.items():
                    spec = bedrock_spec(rows, sources.root)
                    ordinal = len(stages)
                    key = bedrock_key(name, code, layers_identity, spec)
                    saved = _saved_table(scratch, ordinal, key)
                    if saved is not None:
                        stages.append(dict(name=saved['name'], rows=saved['rows'], path=Path(saved['path']), digest=saved['digest']))
                        continue
                    path = scratch / ('table-%04d.txt' % ordinal)
                    reserve = disk_reserve if disk_reserve is not None else int(os.environ.get('FRANKIE_DIGEST_DISK_RESERVE', P.DISK_RESERVE))
                    proof = P.write_table_parallel(path, name, P.split_specs(spec, len(cpus)),
                                                   scratch / ('table-%04d' % ordinal), cpus, reserve=reserve)
                    digest = _witness(path)
                    if TS._identity(path) != proof['verified_identity']:
                        raise ValueError('proved table changed before its byte witness')
                    stages.append(dict(name=name, rows=proof['rows'], path=path, digest=digest))
                    _save_table(scratch, ordinal, key, stages[-1])
        stage = scratch/'digest.pending'
        with stage.open('xb') as output:
            output.write(DG.digest_header(receipt).encode('utf-8'))
            for i, entry in enumerate(stages):
                if i == legacy_count and layer_header is not None:
                    output.write(layer_header.encode('utf-8'))
                elif i:
                    output.write(b'\n')
                _copy_verified(entry['path'], output, entry['digest'])
            output.flush()
            os.fsync(output.fileno())
        result = dict(schema='FRANKIE_STREAMED_DIGEST_V1', path=str(destination), verified=True,
                      **_witness(stage), tables=[dict(name=e['name'],rows=e['rows'],**e['digest']) for e in stages],
                      scratch_directory=str(scratch))
        _save_new(scratch/'verification-receipt.json', result)
        _save_new(scratch/'publication-intent.json',
                  dict(schema='FRANKIE_DIGEST_PUBLICATION_INTENT_V1',source=str(stage),destination=str(destination),
                       proof=_witness(scratch/'verification-receipt.json'),**_witness(stage)))
        # Same-filesystem link creates the public name atomically and refuses an
        # existing name. The verified scratch inode is retained as evidence.
        os.link(stage, destination)
        _sync_directory(destination.parent)
        _save_new(scratch/'publication-receipt.json',
                  dict(schema='FRANKIE_DIGEST_PUBLICATION_V1',destination=str(destination),
                       intent=_witness(scratch/'publication-intent.json'),**_witness(destination)))
        return result
    finally:
        if built.get('sources') is not None:
            built.pop('sources').close()
        db.close()
