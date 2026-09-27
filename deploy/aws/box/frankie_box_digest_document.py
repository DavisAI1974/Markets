"""Stream a complete exact DIGEST_V6 document and publish only verified bytes."""
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3

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


TABLE_SAVE_SCHEMA = 'FRANKIE_DIGEST_TABLE_SAVE_V1'


def _code_identity():
    """The serializer and renderer bytes a saved table was written by; any change there refuses reuse."""
    return {Path(m.__file__).name: hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest() for m in (TS, DG)}


def _canonical(value):
    return json.loads(json.dumps(value, sort_keys=True))


def _saved_table(scratch, ordinal, key):
    """Save point for reruns: the table at this ordinal that an earlier digest attempt of this calculation root wrote,
    proved and receipted with exactly this key (name, inputs, serializer code). Its bytes are hashed again while the
    document is assembled (_copy_verified), so a changed file refuses there."""
    for receipt in sorted(scratch.parent.glob('.digest-*/table-%04d.save.json' % ordinal)):
        if receipt.parent == scratch:
            continue
        try:
            value = json.loads(receipt.read_bytes())
        except (OSError, ValueError):
            continue
        path = Path(value.get('path') or '')
        if (value.get('schema') == TABLE_SAVE_SCHEMA and value.get('key') == key
                and path.parent == receipt.parent and path.name == 'table-%04d.txt' % ordinal and path.is_file()
                and path.stat().st_size == (value.get('digest') or {}).get('bytes')):
            return dict(name=value['name'], rows=value['rows'], path=path, digest=value['digest'], saved=str(receipt))
    return None


def _save_table(scratch, ordinal, key, entry):
    _save_new(scratch/('table-%04d.save.json' % ordinal),
              dict(schema=TABLE_SAVE_SCHEMA, key=key, name=entry['name'], rows=entry['rows'],
                   path=str(entry['path']), digest=entry['digest']))


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


def write_digest(destination, receipt, layers, prices, frames, structures, roll, first, buys, sells,
                 *, bedrock_entries, scratch_directory):
    """Fresh destination only; all scratch retained, even after publication failure.

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
    reusing = {'legacy': True}

    def table(name, rows, context=None):
        ordinal = len(stages)
        root = scratch/('table-%04d' % ordinal)
        path = scratch/('table-%04d.txt' % ordinal)
        key = _canonical(dict(kind='legacy', name=name, context=sorted(context or {}), code=code))
        # Legacy tables are reused only as an unbroken prefix, so a context table is always the one actually used.
        saved = _saved_table(scratch, ordinal, key) if reusing['legacy'] else None
        if saved is not None and (Path(saved['path']).parent/('table-%04d' % ordinal)/'table.sqlite').is_file():
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
        _save_table(scratch, ordinal, key, stages[-1])
        return original

    # The bedrock sources (layer preparation and member merge, on the pinned helpers) are independent of the five
    # sequential legacy tables: build them on a thread while the legacy tables are written, then join.
    import threading
    built = {}
    def build_sources():
        try:
            built['sources'] = BedrockSources(bedrock_entries, scratch/'calculation-layers')
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
                from frankie_box_projection import Workers,save
                workers = Workers()
                try:
                    save(scratch/'table-workers.json',workers.receipt())
                    # A bedrock table's inputs are the pinned layer files (by sha256) and its query over them.
                    layers_identity = {n: {k: e.get(k) for k in ('bytes', 'sha256')} for n, e in bedrock_entries.items()}
                    jobs,planned=[],[]
                    for name,rows in sources.tables.items():
                        if type(rows).__name__=='_Members':
                            spec=dict(kind='members',database=str(sources.root/'sources.sqlite'))
                        else:
                            spec=dict(kind='rows',database=str(sources.root/'sources.sqlite'),
                                      query=rows.query,parameters=rows.parameters,
                                      excluded=getattr(rows,'excluded',None))
                        ordinal=len(stages)+len(planned)
                        key=_canonical(dict(kind='bedrock',name=name,code=code,layers=layers_identity,
                                            spec={k:v for k,v in spec.items() if k!='database'}))
                        saved=_saved_table(scratch,ordinal,key)
                        planned.append((ordinal,key,saved))
                        if saved is None:
                            jobs.append((ordinal,name,spec,str(scratch)))
                    done=workers.ordered(_bedrock_table_job,jobs)
                    for ordinal,key,saved in planned:
                        if saved is not None:
                            stages.append(dict(name=saved['name'],rows=saved['rows'],path=Path(saved['path']),digest=saved['digest']))
                            continue
                        entry=next(done)
                        entry['path']=Path(entry['path'])
                        stages.append(entry)
                        _save_table(scratch,ordinal,key,entry)
                finally:
                    workers.close()
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
