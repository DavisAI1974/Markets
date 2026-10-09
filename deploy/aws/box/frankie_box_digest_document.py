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


CLAIM_TAIL = 64 << 10


def _stat_claim(path):
    """A file's identity for 'unchanged since it was proved' (one pass, 2026-10-09): inode, size, mtime_ns and the
    sha256 of its last 64 KiB (one 64 KiB read; the file claims' rule without the filesystem name: a save receipt and
    its table sit in the same scratch)."""
    info = os.stat(path)
    with Path(path).open('rb') as handle:
        handle.seek(max(0, info.st_size - CLAIM_TAIL))
        tail = handle.read()
    return dict(ino=info.st_ino, size=info.st_size, mtime_ns=info.st_mtime_ns,
                tail_sha256=hashlib.sha256(tail).hexdigest())


def _claim_holds(path, claim):
    try:
        return isinstance(claim, dict) and _stat_claim(path) == claim
    except OSError:
        return False


def _saved_table(scratch, ordinal, key, context=False):
    """Save point for reruns: the table at this ordinal that an earlier digest attempt of this calculation root wrote,
    proved and receipted with exactly this key (name, inputs, code). One pass (2026-10-09): a receipt that carries the
    table's stat claim (_stat_claim, written when it was proved) is taken while the claim holds, one 64 KiB read, never
    a whole re-hash; an older receipt without one is hashed whole as before. The same for a legacy table's context
    database. Otherwise the next candidate is tried or the table is rebuilt. Its bytes are read once more only by the
    assembly copy into digest.pending (hashed there, compared with the receipt's digest when it has one)."""
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
            digest = value.get('digest')
            if value.get('claim') is not None:
                if not _claim_holds(path, value['claim']) or (digest is not None and digest.get('bytes') != value['claim']['size']):
                    continue
            elif _witness(path) != digest:
                continue
            database = None
            if context:
                database = path.parent/('table-%04d' % ordinal)/'table.sqlite'
                if not database.is_file():
                    continue
                if value.get('context_claim') is not None:
                    if not _claim_holds(database, value['context_claim']):
                        continue
                elif _witness(database) != value.get('context'):
                    continue
        except (OSError, ValueError, TypeError, AttributeError):
            continue
        return dict(name=value['name'], rows=value['rows'], path=path, digest=digest, claim=value.get('claim'),
                    context_claim=value.get('context_claim') if context else None, saved=str(receipt))
    return None


def _save_table(scratch, ordinal, key, entry, context=None, context_claim=None):
    """The table's save receipt: its digest when known (None for a serial table: its bytes are hashed once, by the
    assembly copy), and its stat claim, which a rerun takes instead of re-hashing it (_saved_table)."""
    _save_new(scratch/('table-%04d.save.json' % ordinal),
              dict(schema=TABLE_SAVE_SCHEMA, key=key, name=entry['name'], rows=entry['rows'],
                   path=str(entry['path']), digest=entry.get('digest'), claim=_stat_claim(entry['path']),
                   context=context, context_claim=context_claim))


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


PENDING_NAME = 'digest.pending'
PENDING_RECORD = 'pending.json'
PENDING_SCHEMA = 'FRANKIE_DIGEST_PENDING_V1'
COPY_BLOCK = 4 << 20


def _resumable_sha256(state=None, length=0):
    """frankie_box_boss_session._ResumableSha256 (OpenSSL's running state, checked once per process against hashlib),
    or None when the library is not there (then digest.pending is hashed with hashlib and a rerun cannot adopt it)."""
    module, _ = _topology_helpers()
    if module is None or not hasattr(module, '_sha256_library'):
        return None
    library = module._sha256_library()
    if library is None:
        return None
    return module._ResumableSha256(library, None if state is None else bytes.fromhex(state), length)


class _Assembly:
    """digest.pending, built ONCE in table order (one pass, Greg 2026-10-09; the live box: a full-depth frames table of
    hundreds of GB, 719 GB free on the root volume). Before this every table was written to its own scratch file and
    then copied whole into digest.pending, so the biggest table stood on disk twice. Now:
      - the header goes in first; each table follows at its turn (table order), after its separator;
      - a table written by the parallel writer is written STRAIGHT into digest.pending at its turn (a _Slot handed to
        frankie_box_digest_parallel.write_table_parallel(into=...)): its parts are appended and deleted one by one and
        its inverse proof reads it there, so its bytes exist once on disk;
      - a serial (or bedrock) table file is copied in by the appender thread at its turn, hashed as it is copied (its one
        read); a file of FRANKIE_DIGEST_KEEP_TABLE_BYTES (1 GiB) or more is removed as soon as its bytes are recorded in
        digest.pending (resumable hash: the record is its save point), else after the publication;
      - every byte is hashed as written (the staged witness, no read-back), with OpenSSL's resumable SHA-256, and after
        each table the record pending.json is saved (each table's start, end, bytes, sha256, the hasher's state at its
        end and the sha256 of the 64 KiB before its end). A rerun (a new .digest-<uuid> scratch) ADOPTS the earlier
        unpublished digest.pending with one rename on the same filesystem: every recorded table whose key matches,
        in order, is kept as it stands (never rebuilt, never copied), the file is truncated after the last kept one and
        the hash continues from its state; a table copied but not yet proved is proved in place (_Slot.saved_copy).
        A published pending (publication-intent.json beside it, or a second link) is never adopted."""

    def __init__(self, scratch, header, separator, notes, place=None):
        import threading
        self.scratch, self.path, self.record = Path(scratch), Path(scratch) / PENDING_NAME, Path(scratch) / PENDING_RECORD
        self.header, self.separator, self.notes, self.place = header, separator, notes, place
        self.cond = threading.Condition()
        self.entries, self.ready, self.adopted = [], {}, []
        self.next, self.owner, self.error, self.closed, self.cut = 0, None, None, False, False
        self.handle, self.hasher, self.size, self.tail, self.header_state = None, None, 0, b'', None
        self.resumable = _resumable_sha256() is not None
        if not self._adopt():
            self._fresh()
        self.thread = threading.Thread(target=self._appender, name='digest-assembly', daemon=True)
        self.thread.start()

    # ---- the file
    def _fresh(self):
        self.handle = self.path.open('xb')
        self.hasher = _resumable_sha256() or hashlib.sha256()
        self._write_raw(self.header)
        self._sync()
        self.header_state = self._state()
        self._save_record()

    def _state(self):
        return self.hasher.state().hex() if hasattr(self.hasher, 'state') else None

    def _write_raw(self, data):
        if data:
            self.handle.write(data)
            self.hasher.update(data)
            self.size += len(data)
            self.tail = data[-CLAIM_TAIL:] if len(data) >= CLAIM_TAIL else (self.tail + data)[-CLAIM_TAIL:]

    def _sync(self):
        self.handle.flush()
        os.fsync(self.handle.fileno())

    def _entry(self, **fields):
        return dict(fields, end=self.size, state=self._state(), tail_sha256=hashlib.sha256(self.tail).hexdigest())

    def _save_record(self, entries=None):
        body = dict(schema=PENDING_SCHEMA, at=__import__('time').time(), resumable=self._state() is not None,
                    header=dict(bytes=len(self.header), sha256=hashlib.sha256(self.header).hexdigest(),
                                state=self.header_state),
                    entries=list(self.entries if entries is None else entries))
        pending = self.record.with_name(PENDING_RECORD + '.tmp')
        with pending.open('w', encoding='utf-8') as output:
            json.dump(body, output, sort_keys=True, separators=(',', ':'))
            output.flush()
            os.fsync(output.fileno())
        os.replace(pending, self.record)

    def _adopt(self):
        """The earlier attempt's unpublished digest.pending with the most recorded tables still intact (see the class)."""
        if not self.resumable:
            return False
        want, best = hashlib.sha256(self.header).hexdigest(), None
        for record in sorted(self.scratch.parent.glob('.digest-*/' + PENDING_RECORD)):
            other = record.parent
            if other == self.scratch or other.is_symlink() or any((other / n).exists() for n in
                                                                    ('publication-intent.json', 'publication-receipt.json')):
                continue
            try:
                value = json.loads(record.read_bytes())
                pending = other / PENDING_NAME
                info = os.lstat(pending)
                if (value.get('schema') != PENDING_SCHEMA or not value.get('resumable')
                        or (value.get('header') or {}).get('sha256') != want or not value['header'].get('state')
                        or not os.path.isfile(pending) or os.path.islink(pending) or info.st_nlink != 1
                        or info.st_dev != os.stat(self.scratch).st_dev):
                    continue
                kept = []
                with pending.open('rb') as handle:
                    for number, entry in enumerate(value.get('entries') or []):
                        if entry.get('ordinal') != number or not entry.get('state') or entry['end'] > info.st_size:
                            break
                        handle.seek(max(0, entry['end'] - CLAIM_TAIL))
                        if hashlib.sha256(handle.read(entry['end'] - max(0, entry['end'] - CLAIM_TAIL))).hexdigest() \
                                != entry.get('tail_sha256'):
                            break
                        kept.append(entry)
                        if entry.get('status') != 'verified':
                            break                 # a copied table is the last one its attempt wrote
            except (OSError, ValueError, TypeError, KeyError, AttributeError):
                continue
            if best is None or len(kept) > len(best[2]):
                best = (other, value, kept)
        if best is None:
            return False
        other, value, kept = best
        os.rename(other / PENDING_NAME, self.path)
        self.handle = self.path.open('r+b')
        self.header_state, self.adopted = value['header']['state'], kept
        _save_new(self.scratch / 'pending-adopted.json',
                  dict(schema='FRANKIE_DIGEST_PENDING_ADOPTED_V1', moved_from=str(other / PENDING_NAME),
                       tables=[dict(ordinal=e['ordinal'], name=e['name'], status=e['status'], bytes=e['bytes'])
                               for e in kept]))
        self.notes.append('digest.pending adopted from %s: %d recorded tables kept while their keys match (%s)'
                          % (other, len(kept), ', '.join('%s %s' % (e['name'], e['status']) for e in kept) or 'none'))
        return True

    def _prepare(self, keep_through=None):
        """Before the first write of this attempt into an adopted pending: truncate after the last kept table (or the
        slot's own copied table) and continue the hash from its recorded state; the rest of the adoption is dropped."""
        if self.hasher is not None:
            return
        last = keep_through or (self.entries[-1] if self.entries else None)
        end = last['end'] if last else len(self.header)
        state = last['state'] if last else self.header_state
        self.handle.truncate(end)
        self.handle.seek(max(0, end - CLAIM_TAIL))
        self.tail = self.handle.read(end - max(0, end - CLAIM_TAIL))
        self.handle.seek(end)
        os.fsync(self.handle.fileno())
        self.hasher, self.size = _resumable_sha256(state, end), end
        self.adopted, self.cut = [], True
        if not keep_through:
            self._save_record()

    # ---- the order
    def accept(self, ordinal, key):
        """The adopted pending's proved table at this ordinal (same name/key, every earlier one taken) as its stage, or
        None. A copied-but-unproved table stays for its slot (no cut); anything else ends the adoption here."""
        with self.cond:
            entry = self.adopted[0] if self.adopted else None
            if (entry is None or self.cut or self.next != ordinal or entry['ordinal'] != ordinal
                    or entry.get('key') != _canonical(key)):
                self.cut = True
                return None
            if entry.get('status') != 'verified':
                return None
            context = entry.get('context')
            if context is not None and not _claim_holds(context.get('path') or '', context.get('claim')):
                self.cut = True
                return None
            self.adopted.pop(0)
            self.entries.append(entry)
            self.next = ordinal + 1
            return entry

    def saved_copy(self, ordinal, key):
        with self.cond:
            entry = self.adopted[0] if self.adopted else None
            if (entry is not None and not self.cut and self.next == ordinal and entry['ordinal'] == ordinal
                    and entry.get('key') == _canonical(key) and entry.get('status') == 'copied'):
                return entry
            return None

    def offer(self, ordinal, stage):
        """A proved table file for its turn (the appender thread copies it in)."""
        with self.cond:
            self.ready[ordinal] = stage
            self.cond.notify_all()

    def _wait_turn(self, ordinal):
        with self.cond:
            while not (self.next == ordinal and self.owner is None):
                if self.error is not None or self.closed:
                    raise RuntimeError('digest assembly stopped before table %d: %s' % (ordinal, self.error or 'closed'))
                self.cond.wait(5.0)
            self.owner = ordinal

    def _done(self, entry):
        with self.cond:
            self.entries.append(entry)
            self._save_record()
            self.next, self.owner = entry['ordinal'] + 1, None
            self.cond.notify_all()
        if entry.get('path') and self._state() is not None:
            # its bytes are in digest.pending and recorded there (the rerun's save point): a big table file goes now
            _remove_published_tables([entry])

    def fail(self, error):
        with self.cond:
            if self.error is None:
                self.error = error
            self.cond.notify_all()

    def _appender(self):
        if self.place is not None:
            try:
                _pin_thread({self.place['side']})
            except OSError:
                pass
        while True:
            with self.cond:
                while not (self.closed or self.error is not None or (self.next in self.ready and self.owner is None)):
                    self.cond.wait(5.0)
                if self.closed or self.error is not None:
                    return
                ordinal = self.next
                stage = self.ready.pop(ordinal)
                self.owner = ordinal
            try:
                self._done(self._append_file(ordinal, stage))
            except BaseException as error:  # noqa: BLE001 - the digest fails with it (finish raises it)
                self.fail(error)
                return

    def _append_file(self, ordinal, stage):
        """One table file into digest.pending: its one read, hashed as copied, checked unchanged across the copy."""
        self._prepare()
        path = Path(stage['path'])

        def unchanged():
            if stage.get('identity') is not None:
                return TS._identity(path) == stage['identity']
            return stage.get('claim') is None or _claim_holds(path, stage['claim'])
        if not unchanged():
            raise ValueError('proved table changed before its byte witness')
        self._write_raw(self.separator(ordinal))
        start, hashed, size = self.size, hashlib.sha256(), 0
        with path.open('rb') as source:
            for block in iter(lambda: source.read(COPY_BLOCK), b''):
                self._write_raw(block)
                hashed.update(block)
                size += len(block)
        witness = dict(bytes=size, sha256=hashed.hexdigest())
        if (stage.get('digest') is not None and stage['digest'] != witness) or not unchanged():
            raise ValueError('verified table changed during document assembly')
        self._sync()
        return self._entry(ordinal=ordinal, name=stage['name'], key=_canonical(stage['key']), rows=stage['rows'],
                           start=start, status='verified', context=stage.get('context'), path=str(path), **witness)

    def slot(self, ordinal, name, key):
        return _Slot(self, ordinal, name, key)

    def finish(self, total):
        """Every table in: the staged witness (bytes, sha256 of every byte written, no read-back) and the entries."""
        with self.cond:
            while self.next < total:
                if self.error is not None or self.closed:
                    raise self.error if isinstance(self.error, BaseException) else RuntimeError('digest assembly closed')
                self.cond.wait(5.0)
            if self.error is not None:
                raise self.error
        self._prepare()
        self._sync()
        return dict(bytes=self.size, sha256=self.hasher.hexdigest()), list(self.entries)

    def close(self):
        with self.cond:
            self.closed = True
            self.cond.notify_all()
        self.thread.join(60)
        if self.handle is not None:
            self.handle.close()


class _Slot:
    """A parallel table's place in digest.pending (frankie_box_digest_parallel.write_table_parallel(into=...)): acquire()
    waits for its turn and writes its separator (or, for a copy an adopted pending already holds, keeps those bytes);
    write/sync are the table's bytes; mark_copied records the copied table (a rerun proves it in place); release records
    it proved and passes the turn on."""

    def __init__(self, assembly, ordinal, name, key):
        self.assembly, self.ordinal, self.name, self.key = assembly, ordinal, name, _canonical(key)
        self.path = assembly.path
        self.saved_copy = assembly.saved_copy(ordinal, key)
        self.start, self.held, self.copied = None, False, None

    def acquire(self, keep_saved=False):
        """The table's turn. keep_saved: the writer proves the copy the adopted pending holds (its saved copy pass
        matched saved_copy); otherwise any such bytes are dropped (truncated) and the table is written afresh."""
        a = self.assembly
        a._wait_turn(self.ordinal)
        self.held = True
        if not keep_saved:
            self.saved_copy = None
        if self.saved_copy is not None:
            a._prepare(keep_through=self.saved_copy)
            self.start, self.copied = self.saved_copy['start'], self.saved_copy
        else:
            a._prepare()
            a._write_raw(a.separator(self.ordinal))
            self.start = a.size

    def write(self, data):
        self.assembly._write_raw(data)

    def sync(self):
        self.assembly._sync()

    def mark_copied(self, copied):
        a = self.assembly
        a._sync()
        if a.size != self.start + copied['bytes']:
            raise ValueError('table %s: %d bytes in digest.pending, the copy wrote %d' % (self.name, a.size - self.start,
                                                                                          copied['bytes']))
        self.copied = a._entry(ordinal=self.ordinal, name=self.name, key=self.key, rows=None, start=self.start,
                               status='copied', context=None, path=None, bytes=copied['bytes'], sha256=copied['sha256'])
        with a.cond:
            a._save_record(a.entries + [self.copied])

    def release(self, rows, context):
        if self.copied is None:
            raise ValueError('table %s was proved without its copy' % self.name)
        self.assembly._done(dict(self.copied, rows=rows, status='verified', context=context))


KEEP_TABLE_SETTING = 'FRANKIE_DIGEST_KEEP_TABLE_BYTES'
KEEP_TABLE_BYTES = 1 << 30           # a table file this big is removed once its bytes are in the published digest
PARTS_SETTING = 'FRANKIE_DIGEST_PARTS_DIR'
ARCHIVE_ROOT = '/opt/frankie-box/archive'   # frankie_box_root_move.ARCHIVE_ROOT (FRANKIE_ARCHIVE_ROOT overrides)
PARTS_PEAK_FACTOR = 1.5              # planning bound: the parts' row text (at most the spool) + the plan pass's cells


def _remove_published_tables(entries):
    """After the publication (one copy of every byte, 2026-10-09): a table FILE copied into the digest that is
    FRANKIE_DIGEST_KEEP_TABLE_BYTES (1 GiB) or larger is removed with its save receipt (its bytes are the published
    digest's; a rerun of a published digest returns early, frankie_box_render_digest.already_rendered). Smaller ones
    stay as save points. Returns what was removed; never raises."""
    keep = int(os.environ.get(KEEP_TABLE_SETTING) or KEEP_TABLE_BYTES)
    removed = []
    for entry in entries:
        path = Path(entry['path']) if entry.get('path') else None
        try:
            if path is None or not path.is_file() or path.stat().st_size < keep:
                continue
            (path.parent / (path.stem + '.save.json')).unlink(missing_ok=True)
            path.unlink()
            removed.append(dict(path=str(path), bytes=entry['bytes']))
        except OSError as error:
            removed.append(dict(path=str(path), error=str(error)))
    return removed


def _disk_plan(scratch, reserve, spools):
    """Where the parallel tables' parts go, checked against free space at the start (2026-10-09, the live box: the root
    volume 719 GB free, the archive volume 1.6 TB, the full-depth frames spool 496.7 GB). spools: {ordinal: the closed
    spool a parallel table reads}. With the table written straight into digest.pending and each part deleted as it is
    appended, the peak on the parts' volume is the final pass (the parts' row text, at most the spool's bytes, plus the
    plan pass's cells): planning bound PARTS_PEAK_FACTOR x the spool bytes; digest.pending (on the scratch volume, the
    destination's: published by link) needs at most the spool bytes plus the small tables. FRANKIE_DIGEST_PARTS_DIR
    names the parts' volume explicitly; otherwise the scratch when the bound fits there (or an earlier attempt's parts
    of these tables with the final pass saved are there: resumed, never moved across volumes; earlier progress short of
    that is left behind when the parts go elsewhere), else the archive volume (FRANKIE_ARCHIVE_ROOT,
    default /opt/frankie-box/archive, <it>/digest-parts/<root tag>/<scratch name>) when the bound fits there, else the
    scratch (the writer then stops lawfully before the reserve, every pass saved). Returns the plan (bytes named)."""
    import shutil
    spool_bytes = sum(os.stat(path).st_size for path in spools.values())
    bound = int(PARTS_PEAK_FACTOR * spool_bytes)
    free_scratch = shutil.disk_usage(scratch).free
    tag = hashlib.sha256(str(Path(scratch).parent).encode()).hexdigest()[:16]
    plan = dict(spool_bytes=spool_bytes, parts_peak_bound=bound, digest_pending_bound=spool_bytes, reserve=reserve,
                scratch=str(scratch), free_scratch=free_scratch, rule=PARTS_PEAK_FACTOR)
    explicit = os.environ.get(PARTS_SETTING)
    def final_saved(directory):
        # an earlier attempt's table whose final pass is saved: its part rows already stand on this volume (the peak is
        # behind it; the copy into digest.pending consumes them one by one), so it is resumed where it is
        try:
            import pickle
            return 'final' in (pickle.loads((directory / 'passes.pkl').read_bytes()).get('passes') or {})
        except Exception:  # noqa: BLE001 - no usable save point: the parts may be placed afresh
            return False
    progress = [str(d) for ordinal in spools for d in Path(scratch).parent.glob('.digest-*/table-%04d.parallel' % ordinal)
                if final_saved(d)]
    archive = Path(os.environ.get('FRANKIE_ARCHIVE_ROOT') or ARCHIVE_ROOT)
    if explicit:
        base, basis = Path(explicit) / tag / Path(scratch).name, PARTS_SETTING
    elif not spools or free_scratch - reserve >= bound:
        base, basis = Path(scratch), 'the bound fits on the scratch volume'
    elif progress:
        base, basis = Path(scratch), ('an earlier attempt\'s parts of these tables, final pass saved, are on the scratch '
                                      'volume (%s): resumed there, the copy consumes them' % progress)
    else:
        try:
            free_archive = shutil.disk_usage(archive).free if archive.is_dir() else 0
            other = archive.is_dir() and os.stat(archive).st_dev != os.stat(scratch).st_dev
        except OSError:
            free_archive, other = 0, False
        plan['free_archive'] = free_archive
        if other and free_archive - reserve >= bound:
            base, basis = archive / 'digest-parts' / tag / Path(scratch).name, 'auto: the archive volume (the bound does not fit on the scratch volume)'
        else:
            base, basis = Path(scratch), 'the bound fits nowhere: on the scratch volume; the writer stops before the reserve'
    if base != Path(scratch):
        base.mkdir(parents=True, exist_ok=True)
        plan['free_parts'] = shutil.disk_usage(base).free
    plan.update(parts_base=str(base), basis=basis,
                need=dict(scratch_volume=spool_bytes if base != Path(scratch) else bound,
                          parts_volume=bound if base != Path(scratch) else 0))
    return plan


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
    """Fresh destination only; all scratch retained, even after publication failure (one exception, 2026-10-09: a
    table FILE of FRANKIE_DIGEST_KEEP_TABLE_BYTES, 1 GiB, or more is removed after the publication, its bytes being the
    published digest's; _remove_published_tables).

    One pass (2026-10-09): digest.pending is built once, in table order, by _Assembly (see it): a parallel table is
    written straight into it from its parts (no table file: its bytes exist once on disk), a table file is copied in
    at its turn (its one read), every byte hashed as written; a rerun adopts an unpublished digest.pending of an earlier
    attempt (one rename) and keeps every recorded table whose key matches. _disk_plan places the parallel tables' parts
    (the scratch volume, FRANKIE_DIGEST_PARTS_DIR, or the archive volume when the scratch volume cannot hold them) and
    records the bytes it planned against the free space at the start.

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
    builder, failed, assembly = None, True, None

    def separator(ordinal):
        # what stands before table `ordinal` in the document: nothing before the first, the bedrock heading before the
        # first bedrock table, else one newline (exactly the assembly order every earlier digest used)
        if ordinal == 0:
            return b''
        if ordinal == LEGACY_TABLES and bedrock_entries and bedrock['header'] is not None:
            return bedrock['header'].encode('utf-8')
        return b'\n'

    # ---- legacy save points: an unbroken prefix, looked up in ordinal order (as the serial order did): a table the
    # adopted digest.pending already holds (no file, nothing copied), else a receipted table file of an earlier attempt
    rows_of = [lambda: prices, lambda: per_second_rows(first,buys,sells,roll), lambda: frames,
               counted_structures, family_rows]
    names = ['legacy_price', 'per_second_flow_and_roll20', 'legacy_book_imbalance', 'legacy_structure_observables',
             'structure_families']
    context_of = [None, None, None, ('legacy_book_imbalance',), None]
    contexts = {}
    reused = 0

    def finish_serial(ordinal, name, key, rows, path, root, identity):
        # one pass: no byte witness of the table here (the assembly copy hashes it, its one read); the save receipt
        # carries its stat claim, which a rerun takes instead of re-hashing it
        if TS._identity(path) != identity:
            raise ValueError('proved table changed before its byte witness')
        context = dict(path=str(root/'table.sqlite'), claim=_stat_claim(root/'table.sqlite'))
        legacy_stages[ordinal] = dict(name=name, rows=rows, path=path, digest=None)
        _save_table(scratch, ordinal, key, legacy_stages[ordinal], context_claim=context['claim'])
        assembly.offer(ordinal, dict(legacy_stages[ordinal], identity=identity, key=key, context=context))

    def serial_table(ordinal, name, rows, context):
        root = scratch/('table-%04d' % ordinal)
        path = scratch/('table-%04d.txt' % ordinal)
        key = legacy_key(name, context, code, legacy_inputs)
        entry = timed(ordinal, name, 'serial')
        proof = TS.write_table(path, name, rows, root, context=context)
        if TS._identity(path) != proof['verified_identity']:
            raise ValueError('proved table changed before its byte witness')
        entry['ended'] = time.time()
        # the save receipt and the hand-over to the assembly on a side thread; the main thread goes on
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
        return _Rows(root/'table.sqlite'), _stat_claim(root/'table.sqlite')

    def context_job(ordinal, name, specs):
        columns = cross_columns_of(name)
        return context_db(ordinal, name, PP.cross_context(specs, columns, helper_cpus, pool=pool) if columns else (),
                          'parallel-context')

    def parallel_table(ordinal, name, rows, specs, context_future, fused=None, parts_base=None):
        # A big legacy table read from a closed RowSpool (the frame sections make legacy_book_imbalance hundreds of GB
        # on a full day) is written by the parallel table writer: the same bytes and inverse proof as TS.write_table over
        # the same rows (frankie_box_digest_parallel), each helper reading its own line range of the spool (never held
        # whole). Every field and row is kept; nothing is reduced. Session 6 (Greg: "We stream the data in and get 32
        # CPUs and workers on this job"): under FRANKIE_DIGEST_DECODES <= 4 (default 2; PP.pass_modes) the cross-table
        # context is collected by the writer's own snapshot decode (fused: a Future resolved from inside the writer)
        # instead of a decode of its own; the writer's other reductions (canonical_verify at 3, one_decode at 2) are
        # the same setting's; which ran and the scratch bytes are on the proof's `passes`, copied to the timeline.
        # One pass (2026-10-09): the table is written STRAIGHT into digest.pending at its turn (into=the assembly's
        # slot) and proved there; no table file, so its bytes exist once; its parts live under parts_base (the scratch,
        # or FRANKIE_DIGEST_PARTS_DIR / the archive volume when the scratch volume cannot hold them: _disk_plan).
        entry = timed(ordinal, name, 'parallel')
        path = scratch/('table-%04d.txt' % ordinal)          # never created with into; the writer's name for the table
        key = legacy_key(name, None, code, legacy_inputs)
        # the context columns are handed over whether or not they are fused (the writer fuses only under its
        # setting; given them it counts the separate cross-context decode on its proof: source_decodes 5 at =5)
        columns = cross_columns_of(name) or None

        def on_cross(context_rows):
            try:
                fused.set_result(context_db(ordinal, name, context_rows, 'parallel-context (fused into the snapshot pass)'))
            except BaseException as error:  # noqa: BLE001 - the waiting serial table sees the error, never a hang
                fused.set_exception(error)
                raise
        slot = assembly.slot(ordinal, name, key)
        try:
            proof = PP.write_table_parallel(path, name, specs, Path(parts_base or scratch)/('table-%04d.parallel' % ordinal),
                                            helper_cpus, reserve=reserve, pool=pool, cross_columns=columns,
                                            on_cross=on_cross if fused is not None else None, into=slot)
            if proof['rows'] != len(rows):
                raise ValueError('parallel legacy table rows differ from the spool count')
            if not slot.held:
                raise ValueError('parallel legacy table %s was never written into digest.pending' % name)
            _, context_claim = (fused if fused is not None else context_future).result()
        except BaseException as error:
            if fused is not None and not fused.done():
                fused.set_exception(error)
            assembly.fail(error)
            raise
        slot.release(proof['rows'], dict(path=str(scratch/('table-%04d' % ordinal)/'table.sqlite'), claim=context_claim))
        legacy_stages[ordinal] = dict(name=name, rows=proof['rows'], path=None,
                                      digest=dict(bytes=proof['bytes'], sha256=proof['sha256']))
        entry['passes'] = proof.get('passes')          # the writer's pass reductions, on the proof's timeline
        entry['in_pending'] = dict(start=proof.get('start'), bytes=proof['bytes'])
        entry['ended'] = time.time()

    def bedrock_table(index, ordinal, name, spec, key):
        # Every bedrock table is written by the parallel writer on the shared helpers (same bytes as write_table; Greg
        # 2026-09-28: no table runs for hours on one core), TABLE_THREADS tables at once. The parts come from the table's
        # specs at the part count every earlier digest used, never from the CPU list.
        entry = timed(ordinal, name, 'parallel-bedrock')
        path = scratch / ('table-%04d.txt' % ordinal)
        proof = PP.write_table_parallel(path, name, PP.split_specs(spec, parts), scratch / ('table-%04d' % ordinal),
                                        helper_cpus, reserve=reserve, pool=pool)
        if TS._identity(path) != proof['verified_identity']:
            raise ValueError('proved table changed before its byte witness')
        # one pass: the table's witness is the writer's write-stream hash (an older copy save point lacks it: read)
        digest = {k: proof[k] for k in ('bytes', 'sha256')} if 'sha256' in proof else _witness(path)
        bedrock['stages'][index] = dict(name=name, rows=proof['rows'], path=path, digest=digest)
        _save_table(scratch, ordinal, key, bedrock['stages'][index])
        assembly.offer(ordinal, dict(bedrock['stages'][index], identity=proof['verified_identity'], key=key, context=None))
        entry['passes'] = proof.get('passes')          # session 9: the pass reductions and the per-part chunk progress
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
                held = assembly.accept(ordinal, key)
                if held is not None:
                    bedrock['stages'][index] = dict(name=held['name'], rows=held['rows'], path=None,
                                                    digest=dict(bytes=held['bytes'], sha256=held['sha256']))
                    timeline.append(dict(ordinal=ordinal, name=name, mode='reused (in the adopted digest.pending)'))
                    continue
                saved = _saved_table(scratch, ordinal, key)
                if saved is not None:
                    bedrock['stages'][index] = dict(name=saved['name'], rows=saved['rows'], path=Path(saved['path']),
                                                    digest=saved['digest'])
                    assembly.offer(ordinal, dict(bedrock['stages'][index], claim=saved['claim'], key=key, context=None))
                    timeline.append(dict(ordinal=ordinal, name=name, mode='reused', saved=saved['saved']))
                    continue
                bedrock['futures'].append(bedrock_jobs.submit(bedrock_table, index, ordinal, name, spec, key))
        except BaseException as error:
            built['error'] = error
    try:
        assembly = _Assembly(scratch, DG.digest_header(receipt).encode('utf-8'), separator, notes, place)
        for ordinal, name in enumerate(names):
            key = legacy_key(name, context_of[ordinal], code, legacy_inputs)
            held = assembly.accept(ordinal, key)
            if held is not None and held.get('context'):
                legacy_stages[ordinal] = dict(name=held['name'], rows=held['rows'], path=None,
                                              digest=dict(bytes=held['bytes'], sha256=held['sha256']))
                contexts[name] = _Rows(held['context']['path'])
                timeline.append(dict(ordinal=ordinal, name=name, mode='reused (in the adopted digest.pending)'))
                reused += 1
                continue
            saved = _saved_table(scratch, ordinal, key, context=True)
            if saved is None:
                break
            database = Path(saved['path']).parent/('table-%04d' % ordinal)/'table.sqlite'
            legacy_stages[ordinal] = dict(name=saved['name'], rows=saved['rows'], path=Path(saved['path']), digest=saved['digest'])
            contexts[name] = _Rows(database)
            assembly.offer(ordinal, dict(legacy_stages[ordinal], claim=saved['claim'], key=key,
                                         context=dict(path=str(database),
                                                      claim=saved.get('context_claim') or _stat_claim(database))))
            timeline.append(dict(ordinal=ordinal, name=name, mode='reused', saved=saved['saved']))
            reused += 1

        builder = threading.Thread(target=build_sources, name='bedrock-sources') if bedrock_entries else None
        if builder is not None:
            builder.start()
        # ---- the legacy tables after the saved prefix: the parallel ones (and their contexts, first) to the side
        # threads now; then the serial ones on the main thread in ordinal order
        rows = {ordinal: rows_of[ordinal]() for ordinal in range(reused, LEGACY_TABLES)}
        parallel = {ordinal for ordinal in rows
                    if context_of[ordinal] is None and _parallel_spool(rows[ordinal]) and parts > 1}
        disk = _disk_plan(scratch, reserve, {ordinal: rows[ordinal].path for ordinal in sorted(parallel)})
        notes.append('disk plan: ' + json.dumps(disk, sort_keys=True))
        print('DIGEST disk plan ' + json.dumps(disk, sort_keys=True), flush=True)
        fuse = PP.pass_modes()['fuse_context']
        for ordinal in sorted(parallel):
            specs = PP.spool_specs(rows[ordinal].path, parts)
            if fuse and cross_columns_of(names[ordinal]):
                from concurrent.futures import Future
                fused = Future()                 # resolved by the writer's snapshot pass (parallel_table.on_cross)
                contexts[names[ordinal]] = fused
                futures.append(side.submit(parallel_table, ordinal, names[ordinal], rows[ordinal], specs, None, fused,
                                           disk['parts_base']))
                continue
            context_future = side.submit(context_job, ordinal, names[ordinal], specs)
            contexts[names[ordinal]] = context_future
            futures.append(context_future)
            futures.append(side.submit(parallel_table, ordinal, names[ordinal], rows[ordinal], specs, context_future,
                                       None, disk['parts_base']))
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
        # every table is in digest.pending, in order, each byte hashed as it was written
        staged, entries = assembly.finish(len(stages))
        if [e['ordinal'] for e in entries] != list(range(len(stages))):
            raise ValueError('digest.pending does not hold every table in order')
        assembly.close()
        stage = scratch/PENDING_NAME
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
                      **staged, tables=[dict(name=e['name'], rows=e['rows'], bytes=e['bytes'], sha256=e['sha256'])
                                        for e in entries],
                      scratch_directory=str(scratch), disk=disk,
                      cpu_schedule=dict(schema='FRANKIE_DIGEST_CPU_SCHEDULE_V1', placement=place, parts=parts,
                                        table_threads=table_threads, helpers=pool.record(), notes=list(notes),
                                        timeline=sorted(timeline, key=lambda e: (e['ordinal'], e['name'])),
                                        stage_witness='hashed as written, table by table into digest.pending (a '
                                        'parallel table straight from its parts; read back once only under '
                                        'FRANKIE_DURABLE_READBACK=on); the intent and the publication reuse it for the '
                                        'same unchanged inode'))
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
        result['removed_after_publication'] = _remove_published_tables(entries)
        failed = False
        return result
    finally:
        # every side thread and table job ends before this returns or raises (a finished table keeps its save point
        # for a rerun; queued bedrock tables are not started after a failure); the assembly is stopped first so no
        # thread waits for a turn that will not come
        if assembly is not None:
            if failed:
                assembly.fail(RuntimeError('the digest stopped'))
            assembly.close()
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
