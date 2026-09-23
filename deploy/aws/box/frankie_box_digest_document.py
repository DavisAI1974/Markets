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


def _copy_verified(path, output, expected):
    hashed, size = hashlib.sha256(), 0
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024*1024), b''):
            hashed.update(block); size += len(block); output.write(block)
    if dict(bytes=size, sha256=hashed.hexdigest()) != expected:
        raise ValueError('verified table changed during document assembly')


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

    def counted_structures():
        for i, row in enumerate(structures):
            key = row['action_string']
            if not isinstance(key, str):
                raise ValueError('action_string must be a string')
            db.execute('INSERT INTO families VALUES (?,1,?) ON CONFLICT(name) DO UPDATE SET count=count+1', (key,i))
            yield row
        db.commit()

    def family_rows():
        for key, count in db.execute('SELECT name,count FROM families ORDER BY count DESC,first_ordinal'):
            yield dict(action_string=key,count=count)

    def table(name, rows, context=None):
        ordinal = len(stages)
        root = scratch/('table-%04d' % ordinal)
        path = scratch/('table-%04d.txt' % ordinal)
        proof = TS.write_table(path, name, rows, root, context=context)
        original = _Rows(root/'table.sqlite')
        # Re-prove the actual block to be copied, not merely a returned success flag.
        TS.verify_table(path, name, original, root/'document-inverse', context=context)
        digest = _witness(path)
        stages.append(dict(name=name, rows=proof['rows'], path=path, digest=digest))
        return original

    try:
        table('legacy_price', prices)
        table('per_second_flow_and_roll20', per_second_rows(first,buys,sells,roll))
        book = table('legacy_book_imbalance', frames)
        table('legacy_structure_observables', counted_structures(), {'legacy_book_imbalance':book})
        table('structure_families', family_rows())
        legacy_count = len(stages)
        layer_header = None
        if bedrock_entries:
            with BedrockSources(bedrock_entries, scratch/'calculation-layers') as sources:
                layer_header = DG.bedrock_header(sources.derived, sources.layer_count, sources.verdict or {})
                for name, rows in sources.tables.items():
                    table(name, rows)
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
        # existing name. The scratch inode is retained as immutable evidence.
        os.link(stage, destination)
        _sync_directory(destination.parent)
        _save_new(scratch/'publication-receipt.json',
                  dict(schema='FRANKIE_DIGEST_PUBLICATION_V1',destination=str(destination),
                       intent=_witness(scratch/'publication-intent.json'),**_witness(destination)))
        return result
    finally:
        db.close()
