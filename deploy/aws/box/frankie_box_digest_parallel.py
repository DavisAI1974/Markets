"""Parallel DIGEST_V6 table writer: the same bytes as frankie_box_digest_stream.write_table, built on many cores.

The serial writer runs four passes over a table on one core (snapshot, plan, emit, inverse verify). Each pass is
split here into contiguous row ranges ("parts") on pinned helper processes. What crosses a part boundary is small and
exact: the planner's and the verifier's row-to-row state (previous row, last value / integer / list head per column),
and the table-wide facts (column order, derived and constant columns, scales, dictionary counts and first-occurrence
numbering, separator). The coordinator folds those in part order, so every cell, the header and the dictionary are
what the serial writer produces. frankie_box_digest_stream and frankie_box_digest_render are not modified.

Row sources are described, not passed: ('members', database, group keys) or ('rows', database, query, parameters,
excluded, start, count), so each helper reads its own range of a finished sources.sqlite read-only.
"""
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
import copy
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import re
import shutil
import sqlite3
import sys
import zlib

BOX = Path(__file__).resolve().parent
if str(BOX) not in sys.path:
    sys.path.insert(0, str(BOX))
import frankie_box_digest_render as DG  # noqa: E402
import frankie_box_digest_stream as TS  # noqa: E402


# ---- helpers ------------------------------------------------------------------------------------------------------

def _init(box, cpus):
    if box not in sys.path:
        sys.path.insert(0, box)
    cpu = cpus.get()
    os.sched_setaffinity(0, {cpu})


def _pool(cpus):
    context = multiprocessing.get_context('spawn')
    queue = context.Queue()
    for cpu in cpus:
        queue.put(cpu)
    return ProcessPoolExecutor(max_workers=len(cpus), mp_context=context, initializer=_init,
                               initargs=(str(BOX), queue))


def _readonly(path):
    import frankie_box_digest_sources as S
    db = sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)
    db.execute('PRAGMA cache_size=-65536')
    db.create_collation('group_order', S._compare_groups)
    return db


def _source_rows(spec):
    """The rows of one part, exactly as _bedrock_table_job would produce them for the whole table."""
    import frankie_box_digest_sources as S
    if spec['kind'] == 'inline':          # rows given in the spec itself (comparisons against the serial writer)
        yield from spec['rows']
        return
    db = _readonly(spec['database'])
    try:
        if spec['kind'] == 'members':
            for key in spec['keys']:
                flat = {}
                for column, payload in db.execute(
                        'SELECT column_name,payload FROM members WHERE group_key=? ORDER BY ordinal', (key,)):
                    flat[column] = DG._spell(S._decoded(payload))
                yield DG._nest(flat)
            return
        excluded = spec['excluded']
        cursor = db.execute(spec['query'], tuple(spec['parameters']))
        for _ in range(spec['start']):
            if cursor.fetchone() is None:
                raise ValueError('rows part starts beyond the table')
        for _ in range(spec['count']):
            fetched = cursor.fetchone()
            if fetched is None:
                raise ValueError('rows part shorter than planned')
            row = S._decoded(fetched[0])
            yield {c: DG._spell(v) for c, v in row.items() if c not in excluded} if excluded is not None else row
    finally:
        db.close()


def _fold(state, flat):
    last_values, last_ints, last_lists = state
    for c, v in flat.items():
        last_values[c] = v
        if isinstance(v, int) and not isinstance(v, bool):
            last_ints[c] = v
        if DG._int_list(v):
            last_lists[c] = v[0]


def _part_db(directory):
    return sqlite3.connect(Path(directory) / 'part.sqlite')


# ---- phase 1: snapshot ---------------------------------------------------------------------------------------------

def _snapshot(job):
    spec, directory = job
    Path(directory).mkdir(parents=True, exist_ok=False)
    db = _part_db(directory)
    db.execute('PRAGMA cache_size=-65536')
    db.executescript('''
        CREATE TABLE source (ordinal INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE plans (ordinal INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE final (ordinal INTEGER PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE frequency (key TEXT PRIMARY KEY, count INTEGER NOT NULL, first INTEGER NOT NULL);
    ''')
    columns, n, first, last = {}, 0, None, None
    state = ({}, {}, {})
    for n, row in enumerate(_source_rows(spec), 1):
        row = dict(row)
        flat = DG._flatten(row)
        for column in flat:
            if not column or column[0] in '=^' or any(c in column for c in ('\t', '\n', '=', ' ')):
                raise ValueError(f'column name {column!r} cannot be spelled in a table header')
            columns.setdefault(column, None)
        db.execute('INSERT INTO source VALUES (?, ?)', (n - 1, TS._dump(row)))
        if first is None:
            first = flat
        last = flat
        _fold(state, flat)
    db.commit()
    db.close()
    return dict(columns=list(columns), n=n, first=first, last=last, state=state)


# ---- phase 2: plan cells, derived and constant flags ---------------------------------------------------------------

def _plan(job):
    directory, columns, seed, first = job
    prev, values, integers, lists = seed[0], dict(seed[1]), dict(seed[2]), dict(seed[3])
    derived = {c: True for c in columns}
    constant = {c: True for c in columns}
    db = _part_db(directory)
    for i, row in enumerate(TS._rows(db, 'source')):
        flat = DG._flatten(row)
        cells = DG._plan_row(flat, columns, prev, values, integers, lists)
        db.execute('INSERT INTO plans VALUES (?, ?)', (i, TS._dump(cells)))
        for j, c in enumerate(columns):
            derived[c] = derived[c] and cells[j][1] == '='
            constant[c] = constant[c] and c in flat and c in first and DG._same(flat[c], first[c])
        prev = flat
    db.commit()
    db.close()
    return derived, constant


# ---- phase 3: dictionary counts and scales -------------------------------------------------------------------------

def _count(job):
    directory, kept = job
    scale_state = {j: [DG.SCALE_MAX, False] for j in kept}
    db = _part_db(directory)
    position = 0
    for cells in TS._rows(db, 'plans'):
        for j in kept:
            kind, text = cells[j]
            if kind != 'lit':
                key = json.dumps(text) if kind == 'str' else text
                db.execute('INSERT INTO frequency(key, count, first) VALUES (?, 1, ?) '
                           'ON CONFLICT(key) DO UPDATE SET count=count+1', (key, position))
                position += 1
            elif DG._INT_CELL.fullmatch(text):
                k, _ = scale_state[j]
                value, z = abs(int(text)), 0
                if value:
                    while value % 10 == 0 and z < k:
                        value //= 10
                        z += 1
                    k = min(k, z)
                scale_state[j] = [k, True]
    db.commit()
    db.close()
    return scale_state


# ---- phase 4: final cells with the global dictionary ---------------------------------------------------------------

def _final(job):
    directory, kept, columns, scales, dictionary = job
    db = _part_db(directory)
    lookup = sqlite3.connect(Path(dictionary).resolve().as_uri() + '?mode=ro', uri=True)
    has_space = False
    for i, cells in enumerate(TS._rows(db, 'plans')):
        out = []
        for j in kept:
            kind, text = cells[j]
            if kind == 'lit':
                scale = scales.get(columns[j])
                out.append(DG._scaled(text, scale) if scale and DG._INT_CELL.fullmatch(text) else text)
                continue
            key = json.dumps(text) if kind == 'str' else text
            count, number = lookup.execute('SELECT count, number FROM frequency WHERE key=?', (key,)).fetchone()
            if count >= 2:
                out.append('@%d' % number)
            elif kind == 'str':
                out.append('S' + text if '\t' not in text and '\n' not in text else 'J' + key)
            else:
                out.append('J' + text)
        out = DG._collapse(out)
        has_space = has_space or any(' ' in cell for cell in out)
        db.execute('INSERT INTO final VALUES (?, ?)', (i, TS._dump(out)))
    db.commit()
    db.close()
    lookup.close()
    return has_space


def _emit(job):
    directory, sep = job
    db = _part_db(directory)
    path = Path(directory) / 'rows.txt'
    with path.open('x', encoding='utf-8', newline='\n') as handle:
        for cells in TS._rows(db, 'final'):
            handle.write(sep.join(cells) + '\n')
        handle.flush()
        os.fsync(handle.fileno())
    db.close()
    return path.stat().st_size


# ---- phase 5: inverse verification, per part ------------------------------------------------------------------------

def _verify(job):
    (path, offset, length, count, directory, header, dictionary, seed) = job
    name, columns, whole, kept, constants, scales, sep = header
    db = _part_db(directory)
    lookup = sqlite3.connect(Path(dictionary).resolve().as_uri() + '?mode=ro', uri=True)
    prev_row, prev_values, prev_ints, prev_lists = seed[0], dict(seed[1]), dict(seed[2]), dict(seed[3])
    expected = TS._rows(db, 'source')
    with Path(path).open('rb') as handle:
        handle.seek(offset)
        segment = handle.read(length).decode('utf-8')
    lines = segment.split('\n')
    if lines[-1] != '' or len(lines) - 1 != count:
        raise ValueError('table part line count differs')
    for i, line in enumerate(lines[:-1]):
        cells = TS._expanded(line, sep, kept)
        row = copy.deepcopy(constants)
        derived_cols = {c for c, mark in whole.items() if mark == '='}
        positional, paired = {}, {}
        for c, cell in zip(kept, cells):
            if cell == '?':
                continue
            if cell == DG.NONE:
                v = None
            elif cell == DG.TRUE:
                v = True
            elif cell == DG.FALSE:
                v = False
            elif cell == '=':
                derived_cols.add(c)
                continue
            elif cell == DG.SAME:
                v = copy.deepcopy(prev_values[c])
            elif cell.startswith('@'):
                entry = lookup.execute('SELECT payload FROM dictionary WHERE number=?', (int(cell[1:]),)).fetchone()
                if entry is None:
                    raise ValueError('unknown dictionary entry')
                v = json.loads(entry[0])
            elif cell.startswith('S'):
                v = cell[1:]
            elif cell.startswith('J'):
                v = json.loads(cell[1:])
            elif cell.startswith('U'):
                v = tuple(json.loads(cell[1:]))
            elif cell.startswith('K'):
                positional[c] = [int(x) for x in cell[1:].split(',')] if cell[1:] else []
                continue
            elif cell.startswith('I'):
                parts = cell[1:].split(',')
                start = prev_lists[c] + int(parts[0]) if parts[0][:1] in '+-' and isinstance(prev_lists.get(c), int) else int(parts[0])
                v = [start]
                for delta in parts[1:]:
                    v.append(v[-1] + int(delta))
            elif cell.startswith('~'):
                paired[c] = int(cell[1:])
                continue
            elif cell == 'nan':
                v = float('nan')
            elif re.fullmatch(r'-?\d+/\d+', cell):
                num, _, den = cell.partition('/')
                v = float(int(num)) / float(int(den))
            elif cell.startswith('+') or (cell.startswith('-') and c.endswith(DG.DELTA_KEYS) and isinstance(prev_ints.get(c), int) and re.fullmatch(r'-\d+', cell)):
                v = prev_ints[c] + int(cell) * scales.get(c, 1)
            elif re.fullmatch(r'-?\d+', cell):
                v = int(cell) * scales.get(c, 1)
            else:
                v = float(cell)
            row[c] = v
        for c, offset_value in paired.items():
            if DG.PAIRED[c] not in row:
                raise ValueError('paired column absent')
            row[c] = row[DG.PAIRED[c]] + offset_value
        for c, positions in positional.items():
            row[c] = [row['order_ids'][position] for position in positions]
        for c in DG._derived_order(columns):
            if c in derived_cols:
                value = DG._recompute(row, c, prev_row)
                if c.startswith(('action_counts.', 'side_counts.')) and value == 0:
                    continue
                row[c] = value
        try:
            original = next(expected)
        except StopIteration as error:
            raise ValueError('source rows shorter than table part') from error
        if not DG._same(DG._unflatten(row), dict(original)):
            raise ValueError(f'table {name} part row {i} does not round-trip')
        for c, v in row.items():
            prev_values[c] = v
            if isinstance(v, int) and not isinstance(v, bool):
                prev_ints[c] = v
            if DG._int_list(v):
                prev_lists[c] = v[0]
        prev_row = row
    if next(expected, None) is not None:
        raise ValueError('source rows longer than table part')
    db.close()
    lookup.close()
    return count


# ---- coordinator ---------------------------------------------------------------------------------------------------

def write_table_parallel(destination, name, specs, scratch_directory, cpus, progress=None):
    """specs: ordered part row sources (see _source_rows). Same bytes and proof as TS.write_table (no context)."""
    destination = Path(destination)
    scratch = Path(scratch_directory)
    scratch.mkdir(parents=True, exist_ok=False)
    note = progress or (lambda *a: None)
    with _pool(cpus) as pool, destination.open('x', encoding='utf-8', newline='\n') as handle:
        parts = [scratch / ('part-%04d' % i) for i in range(len(specs))]
        note(name, 'snapshot')
        snaps = list(pool.map(_snapshot, [(spec, str(p)) for spec, p in zip(specs, parts)]))
        columns = {}
        for s in snaps:
            for c in s['columns']:
                columns.setdefault(c, None)
        columns = list(columns)
        n = sum(s['n'] for s in snaps)
        first = next((s['first'] for s in snaps if s['n']), None) or {}
        seeds, state, prev = [], ({}, {}, {}), None
        for s in snaps:
            seeds.append((prev, dict(state[0]), dict(state[1]), dict(state[2])))
            if s['n']:
                state[0].update(s['state'][0]); state[1].update(s['state'][1]); state[2].update(s['state'][2])
                prev = s['last']
        note(name, 'plan')
        flags = list(pool.map(_plan, [(str(p), columns, seed, first) for p, seed in zip(parts, seeds)]))
        derived = {c: all(f[0][c] for f in flags) for c in columns}
        constant = {c: all(f[1][c] for f in flags) for c in columns}
        whole = {c: '=' if derived[c] else '^' for c in columns if n and (derived[c] or constant[c])}
        kept = [j for j, c in enumerate(columns) if c not in whole]
        note(name, 'count')
        scale_parts = list(pool.map(_count, [(str(p), kept) for p in parts]))
        scale_state = {j: [min(s[j][0] for s in scale_parts), any(s[j][1] for s in scale_parts)] for j in kept}
        scales = {columns[j]: 10 ** k for j, (k, seen) in scale_state.items() if seen and k >= DG.SCALE_MIN}
        dictionary = scratch / 'dictionary.sqlite'
        g = sqlite3.connect(dictionary)
        g.execute('CREATE TABLE frequency (key TEXT PRIMARY KEY, count INTEGER NOT NULL, number INTEGER UNIQUE)')
        for p in parts:
            g.execute('ATTACH DATABASE ? AS part', (str(p / 'part.sqlite'),))
            g.execute('INSERT INTO frequency(key, count) SELECT key, count FROM part.frequency WHERE true '
                      'ON CONFLICT(key) DO UPDATE SET count=count+excluded.count')
            g.commit()
            g.execute('DETACH DATABASE part')
        number = 0
        for p in parts:   # numbering in first-occurrence order over the whole table, as the serial pass assigns it
            g.execute('ATTACH DATABASE ? AS part', (str(p / 'part.sqlite'),))
            g.execute('CREATE TEMP TABLE fresh (seq INTEGER PRIMARY KEY, key TEXT NOT NULL)')
            g.execute('INSERT INTO fresh(key) SELECT q.key FROM part.frequency q JOIN frequency f ON f.key=q.key '
                      'WHERE f.count >= 2 AND f.number IS NULL ORDER BY q.first')
            g.execute('CREATE UNIQUE INDEX temp.fresh_key ON fresh(key)')
            g.execute('UPDATE frequency SET number = ? + (SELECT seq FROM fresh WHERE fresh.key=frequency.key) - 1 '
                      'WHERE key IN (SELECT key FROM fresh)', (number,))
            number += g.execute('SELECT count(*) FROM fresh').fetchone()[0]
            g.execute('DROP TABLE fresh')
            g.commit()
            g.execute('DETACH DATABASE part')
        g.close()
        note(name, 'final')
        spaces = list(pool.map(_final, [(str(p), kept, columns, scales, str(dictionary)) for p in parts]))
        sep = '\t' if any(spaces) else ' '
        note(name, 'emit')
        sizes = list(pool.map(_emit, [(str(p), sep) for p in parts]))
        handle.write(f'### table {name}: {n} rows, sep={"space" if sep == " " else "tab"}, columns: ')
        handle.write('\t'.join(whole.get(c, '') + c for c in columns) + '\n')
        constants = [c for c in columns if whole.get(c) == '^']
        if constants:
            handle.write('constants: ')
            for i, c in enumerate(constants):
                value = first[c]
                text = ('U' + json.dumps(list(value), separators=(',', ':'), sort_keys=True)) if isinstance(value, tuple) else json.dumps(value, separators=(',', ':'), sort_keys=True)
                handle.write(('\t' if i else '') + c + '=' + text)
            handle.write('\n')
        if scales:
            handle.write('scales: ' + '\t'.join('%s=%d' % (c, k) for c, k in scales.items()) + '\n')
        g = sqlite3.connect(dictionary)
        found = False
        for number_, key in g.execute('SELECT number, key FROM frequency WHERE number IS NOT NULL ORDER BY number'):
            handle.write(('\t' if found else 'dictionary: ') + '@%d=%s' % (number_, key))
            found = True
        g.close()
        if found:
            handle.write('\n')
        handle.flush()
        offset = destination.stat().st_size     # header bytes; the part rows follow in order
        offsets = []
        for p, size in zip(parts, sizes):
            offsets.append(offset)
            offset += size
            with (p / 'rows.txt').open('rb') as chunk:
                handle.flush()
                shutil.copyfileobj(chunk, handle.buffer, 1 << 22)
        handle.flush()
        os.fsync(handle.fileno())
    before = TS._identity(destination)
    # Inverse proof: the header and dictionary are parsed from the written file into their own database, then every
    # part's rows are parsed back from the file at their byte offsets and compared with the part's source rows.
    note(name, 'verify')
    inverse = scratch / 'inverse'
    inverse.mkdir()
    vdb = sqlite3.connect(inverse / 'table.sqlite')
    with destination.open(encoding='utf-8', newline='') as reader:
        tokens = TS._Tokens(reader)
        head, _ = tokens.take()
        m = re.fullmatch(r'### table (\S+): (\d+) rows, sep=(space|tab), columns: (.*)', head)
        if m is None or m.group(1) != name or int(m.group(2)) != n:
            raise ValueError('table header/name mismatch')
        vsep = ' ' if m.group(3) == 'space' else '\t'
        declared = m.group(4).split('\t') if m.group(4) else []
        vcolumns = [c.lstrip('=^') for c in declared]
        vwhole = {c.lstrip('=^'): c[0] for c in declared if c[:1] in '=^'}
        vkept = [c for c in vcolumns if c not in vwhole]
        vconstants, vscales = {}, {}
        if tokens.starts('constants: '):
            tokens.skip('constants: ')
            line, _ = tokens.take()
            for item in line.split('\t'):
                k, _, value = item.partition('=')
                vconstants[k] = tuple(json.loads(value[1:])) if value.startswith('U') else json.loads(value)
        if tokens.starts('scales: '):
            tokens.skip('scales: ')
            line, _ = tokens.take()
            for item in line.split('\t'):
                k, _, value = item.partition('=')
                vscales[k] = int(value)
        vdb.execute('CREATE TABLE dictionary (number INTEGER PRIMARY KEY, payload TEXT NOT NULL)')
        if tokens.starts('dictionary: '):
            tokens.skip('dictionary: ')
            count = 0
            while True:
                item, delimiter = tokens.take('\t\n')
                k, equal, value = item.partition('=')
                if not equal or k != '@%d' % count:
                    raise ValueError('dictionary numbering mismatch')
                json.loads(value)
                vdb.execute('INSERT INTO dictionary VALUES (?, ?)', (count, value))
                count += 1
                if delimiter == '\n':
                    break
        vdb.commit()
    vdb.close()
    if any(mark == '=' and (name, c) in DG.CROSS_DERIVED for c, mark in vwhole.items()):
        raise ValueError('cross-table derived tables are not written in parallel')
    header = (name, vcolumns, vwhole, vkept, vconstants, vscales, vsep)
    total = destination.stat().st_size
    if offsets and offsets[0] + sum(sizes) != total:
        raise ValueError('table parts do not end the file')
    jobs = [(str(destination), off, size, s['n'], str(p), header, str(inverse / 'table.sqlite'), seed)
            for off, size, s, p, seed in zip(offsets, sizes, snaps, parts, seeds)]
    verified = sum(pool_map_verify(jobs, cpus))
    if TS._identity(destination) != before:
        raise ValueError('table changed during inverse proof')
    if verified != n:
        raise ValueError('verified table count mismatch')
    return dict(path=str(destination), rows=n, verified=True, verified_identity=before,
                scratch_directory=str(scratch), parts=len(specs))


def pool_map_verify(jobs, cpus):
    with _pool(cpus) as pool:
        return list(pool.map(_verify, jobs))


# ---- splitting a table into parts ----------------------------------------------------------------------------------

def split_specs(spec, parts):
    """spec as _bedrock_table_job receives it: {kind: members|rows, database, query, parameters, excluded}."""
    db = _readonly(spec['database'])
    try:
        if spec['kind'] == 'members':
            keys = [k for (k,) in db.execute('SELECT key FROM groups ORDER BY value COLLATE group_order')]
            size = max(1, -(-len(keys) // parts))
            return [dict(kind='members', database=spec['database'], keys=keys[i:i + size])
                    for i in range(0, len(keys), size)] or [dict(kind='members', database=spec['database'], keys=[])]
        query, parameters = spec['query'], list(spec['parameters'])
        total = db.execute('SELECT count(*) FROM (' + query + ')', tuple(parameters)).fetchone()[0]
        prefix, order = 'SELECT payload FROM rows WHERE ', ' ORDER BY ordinal'
        if not (query.startswith(prefix) and query.endswith(order)) or total < 2 * parts:
            return [dict(kind='rows', database=spec['database'], query=query, parameters=parameters,
                         excluded=spec['excluded'], start=0, count=total)]
        # Keyset ranges over the same ordered rows: each part reads only its own ordinals.
        ordinals = [o for (o,) in db.execute(query.replace('SELECT payload', 'SELECT ordinal', 1), tuple(parameters))]
        size = -(-total // parts)
        ranged = query[:-len(order)] + ' AND ordinal BETWEEN ? AND ?' + order
        return [dict(kind='rows', database=spec['database'], query=ranged,
                     parameters=parameters + [ordinals[i], ordinals[min(i + size, total) - 1]],
                     excluded=spec['excluded'], start=0, count=min(size, total - i))
                for i in range(0, total, size)]
    finally:
        db.close()


# ---- reuse of a finished sources.sqlite ---------------------------------------------------------------------------

SOURCES_SAVE_SCHEMA = 'FRANKIE_SOURCES_SAVE_V1'


def sources_code():
    """The code whose change could change sources.sqlite or the rows read from it: the merge (MERGE_CODE, which also
    covers layer preparation), the per-layer copy, the row queries and readers. BedrockSources.__init__ is not keyed
    here: since b35e79b7 it differs only by the save-point identity it passes to _merge_sharded (2026-09-27)."""
    import hashlib
    import inspect
    import frankie_box_digest_sources as S
    code = dict(S.merge_shard_key([])['code'])
    for name, function in (('BedrockSources._merge', S.BedrockSources._merge), ('BedrockSources._rows', S.BedrockSources._rows),
                           ('_Rows', S._Rows), ('_Members', S._Members), ('_compare_groups', S._compare_groups),
                           ('_reusable_prepared', S._reusable_prepared)):
        code[name] = hashlib.sha256(inspect.getsource(function).encode()).hexdigest()
    return code


def sources_key(entries):
    identity = [[i, name, pin.get('sha256')] for i, (name, pin) in enumerate(entries.items())]
    return json.loads(json.dumps(dict(schema=SOURCES_SAVE_SCHEMA, layers=identity, code=sources_code())))


def saved_sources(entries, layers_root):
    """A finished sources.sqlite an earlier digest attempt of this calculation root left, receipted with this key and
    unchanged since (bytes and mtime), or None."""
    key = sources_key(entries)
    for receipt in sorted(Path(layers_root).parent.parent.glob('.digest-*/calculation-layers/sources.save.json')):
        try:
            value = json.loads(receipt.read_bytes())
            path = Path(value['path'])
            info = path.stat()
            if (value.get('key') == key and path.parent == receipt.parent and path.name == 'sources.sqlite'
                    and not path.is_symlink() and info.st_size == value['bytes'] and info.st_mtime_ns == value['mtime_ns']
                    and not (path.parent / 'sources.sqlite-journal').exists()):
                return path.parent
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return None


def _file_witness(path):
    digest, size = hashlib.sha256(), 0
    with open(path, 'rb') as reader:
        while chunk := reader.read(8 << 20):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def _published_meta(name, pin, receipts, witness):
    """The metadata fields of a published gzip-json layer, by the walk _prepare_published uses (small metadata members
    decompressed, row arrays located from the range receipts, never inflated); the pin's bytes and sha256 checked."""
    import frankie_box_digest_sources as S
    size, sha = witness.result()
    if size != pin['bytes'] or sha != pin['sha256']:
        raise ValueError('compressed projected layer witness differs')
    path = Path(pin['path'])
    projection = path.resolve().parent.parent
    if projection not in receipts:
        receipts[projection] = S._range_receipts(projection)
    document, _ = S._published_layout(path, name, receipts[projection])
    return {key: document[key] for key in sorted(document) if key in S.META_FIELDS}


def _plain_meta(pin):
    """The metadata fields of a plain (not gzip-json) pinned layer, streamed (row arrays skipped), bytes and sha256
    checked against the pin: the same fields BedrockSources._read keeps (last duplicate key wins)."""
    import frankie_box_digest_sources as S
    if pin.get('encoding') is not None:
        raise ValueError('unknown projected layer encoding')
    digest, size = hashlib.sha256(), 0
    with open(pin['path'], 'rb') as reader:
        while chunk := reader.read(1 << 20):
            digest.update(chunk)
            size += len(chunk)
    if size != pin['bytes'] or digest.hexdigest() != pin['sha256']:
        raise ValueError('pinned layer bytes or sha256 differ')
    metadata = {}
    with open(pin['path'], encoding='utf-8') as handle:
        parser = S._JSON(handle)
        parser.expect('{')
        if parser.peek() != '}':
            while True:
                key = parser.value()
                parser.expect(':')
                if key in S.META_FIELDS:
                    metadata[key] = parser.value()
                else:
                    parser.skip()
                if parser.peek() == '}':
                    break
                parser.expect(',')
    return metadata


class ReopenedSources:
    """The table registry of BedrockSources over an existing finished sources.sqlite, read-only: the same table
    names, order, queries and row readers, and the same header facts (derived, layer_count, verdict)."""
    def __init__(self, entries, root):
        import frankie_box_digest_sources as S
        self.root = Path(root)
        self.db = sqlite3.connect((self.root / 'sources.sqlite').resolve().as_uri() + '?mode=ro', uri=True,
                                  check_same_thread=False)
        self.db.execute('PRAGMA cache_size=-65536')
        self.db.create_collation('group_order', S._compare_groups)
        self.tables, self.verdict, self._references = {}, {}, {}
        self.layer_count, self.derived = len(entries), 0
        metadata, first_verdict = [], False
        recorded = {ordinal: json.loads(zlib.decompress(p) if isinstance(p, bytes) else p)
                    for ordinal, p in self.db.execute('SELECT ordinal, payload FROM layer_index')}
        receipts, found = {}, {}
        for index, pin in enumerate(entries.values()):
            if pin.get('encoding') == 'gzip-json':
                found[index] = S._reusable_prepared(index, pin, self.root)
        with ThreadPoolExecutor(8) as pool:     # pin witnesses of the layers without a receipt, hashed in parallel
            hashes = {index: pool.submit(_file_witness, pin['path']) for index, pin in enumerate(entries.values())
                      if index in found and found[index] is None}
        for index, (name, pin) in enumerate(entries.items()):
            if pin.get('encoding') == 'gzip-json':
                # no receipt in reach: the same layout walk ROOT prepared it with (metadata members only)
                meta = found[index]['meta'] if found[index] is not None else _published_meta(name, pin, receipts, hashes[index])
            else:
                # plain layers were prepared in place (no receipt); their metadata is re-read from the pinned file
                meta = _plain_meta(pin)
            row = recorded.get(index) or {}
            mine = dict(layer=name, status=meta.get('status'), reason=meta.get('reason'), producer=meta.get('producer'),
                        member_paths=' '.join(meta.get('member_paths') or []),
                        lifecycle_sections=' '.join(meta.get('lifecycle_sections') or []),
                        section_counts=json.dumps(meta.get('section_counts') or {}, separators=(',', ':'), sort_keys=True),
                        count=meta.get('count'), partial=' '.join(p['section'] for p in (meta.get('partial') or [])))
            if any(row.get(k) != v for k, v in mine.items()):
                raise ValueError('layer %d (%s) metadata differs from the finished sources layer_index' % (index, name))
            metadata.append(meta)
            if isinstance(meta.get('traversal'), dict) and not first_verdict:
                self.verdict = meta['traversal']
                first_verdict = True
            self.derived += meta.get('status') == 'derived'
        if first_verdict:
            self.tables['bedrock.run'] = S._Rows(self.db, 'SELECT payload FROM run')
        self.tables['bedrock.layers'] = S._Rows(self.db, 'SELECT payload FROM layer_index ORDER BY ordinal')
        if self.db.execute('SELECT 1 FROM groups LIMIT 1').fetchone():
            self.tables['bedrock.members'] = S._Members(self.db)
        sections = {}
        for index, meta in enumerate(metadata):
            if meta.get('status') != 'derived':
                continue
            for section in meta.get('lifecycle_sections') or []:
                rows = self._rows(index, 'lifecycle_rows', section)
                if section not in sections and len(rows):
                    sections[section] = rows
        for section in sorted(sections):
            self.tables[f'bedrock.lifecycle.{section}'] = sections[section]
        for index, meta in enumerate(metadata):
            section = meta.get('section')
            if meta.get('status') != 'derived' or not section:
                continue
            for field, prefix in (('companion_rows', 'companions'), ('declarations', 'declarations'),
                                  ('first_last_pairs', 'first_last')):
                rows = self._rows(index, field)
                if len(rows):
                    self.tables[f'bedrock.{prefix}.{section}'] = rows
            if meta.get('matching_rule'):
                self.tables[f'bedrock.matching_rule.{section}'] = self._rows(index, 'matching_rule')

    def _rows(self, index, field, section=None):
        import frankie_box_digest_sources as S
        return S.BedrockSources._rows(self, index, field, section)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
