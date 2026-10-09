"""The teacher's rows published per SEALED BLOCK while the walk goes on (Greg, 2026-10-09: "Can we start sending data
out as it's coming in? That's the advantage of this. You don't have to wait for full data to come in.").

A block is a span of the day's receive clock (the rows' ts_recv_ns). The schedule is one setting,
FRANKIE_BLOCK_SCHEDULE_MINUTES: a comma list of minutes whose last value repeats ("5,30": the first block five minutes, the
canary, then thirty-minute blocks), the default when unset; "0": no blocks, the whole-day publication exactly as before
(a manifest of sealed blocks already standing is continued whatever the setting says). The clock starts
at the trading day's open (18:00 America/New_York of the prior calendar day, the trading-day standard); block k ends at
open + the first k lengths.

SEALED means: every row known by the block's end clock is in it and nothing later leaks in. The rows are taken in cursor
order and the test is on the running maximum of their receive clocks (clock_event_known_by): a block closes at the first
row whose running maximum reaches its end clock, so every row inside it was received before the end. A row that arrives
later in cursor order with an earlier receive clock (none expected: the journal is in receive order) is listed on the
block it lands in (late_rows), never moved or dropped. A span with no rows is sealed empty, so block n always names the
same clock span.

The rows sidecar (host-dipole-classroom-source.c15.rows.jsonl) is APPENDED block by block: line 1 a header written when
the first block is opened, then each block's lines, so the final file is exactly the header followed by every block's
bytes. Each seal writes <rows_dir>/blocks/<n>.json (FRANKIE_TEACHER_BLOCK_V1: its row cursor range, clock range, rows,
the sidecar byte range and the sha256 of those bytes, its parts by reference, the carried state) and replaces
<rows_dir>/teacher-blocks.json (FRANKIE_TEACHER_BLOCKS_V1, the manifest: the schedule, the sealed blocks in order, the
walk's cursor, complete false until the teacher's final publication sets it true with the receipt's pins), both atomic
(temp, fsync, rename, directory fsync), then one event line in <rows_dir>/teacher-blocks.events.jsonl and a wake on the
box's wake directory (frankie_box_wake.notify) so a reader waiting on the blocks wakes the moment one is sealed.

This module decides boundaries and writes; it never computes a row. The teacher (frankie_box_experiment_teacher._BlockFeed)
builds each line exactly as its whole-day sidecar writer does. A resumed teacher reopens the manifest: the sealed blocks
stand (immutable), any bytes past the last seal are cut back, and sealing continues from the next block.
"""
import hashlib
import json
import os
import time
from pathlib import Path

SETTING = 'FRANKIE_BLOCK_SCHEDULE_MINUTES'
STANDARD = '5,30'                       # the schedule Greg named: the five-minute canary, then thirty-minute blocks
MANIFEST_FILE = 'teacher-blocks.json'
BLOCKS_DIR = 'blocks'
EVENTS_FILE = 'teacher-blocks.events.jsonl'
MANIFEST_SCHEMA = 'FRANKIE_TEACHER_BLOCKS_V1'
BLOCK_SCHEMA = 'FRANKIE_TEACHER_BLOCK_V1'
NS_PER_MINUTE = 60_000_000_000
TRADING_DAY_OPEN = (18, 'America/New_York')      # a trading day opens 18:00 ET the prior calendar day (Greg, 2026-09-22)


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def schedule_setting(environ=None):
    """(minutes tuple or None, record). Unset or empty: STANDARD ("5,30", Greg 2026-10-09); '0': None (the whole-day
    publication, exactly as before); else a comma list of positive minutes, the last repeating. A malformed value raises
    (named)."""
    environ = os.environ if environ is None else environ
    raw = environ.get(SETTING)
    text = (raw or '').strip()
    if text == '0':
        return None, dict(setting=SETTING, value=raw, outcome='off',
                          rule='0: the whole-day publication, exactly as before')
    if text == '' or text.lower() == 'standard':
        text = STANDARD
    try:
        minutes = tuple(float(part) for part in text.split(','))
    except ValueError:
        raise ValueError('%s=%r is not a comma list of minutes (e.g. %s)' % (SETTING, raw, STANDARD))
    if not minutes or any(not (m > 0) for m in minutes):
        raise ValueError('%s=%r: every block length must be a positive number of minutes' % (SETTING, raw))
    minutes = tuple(int(m) if m == int(m) else m for m in minutes)
    return minutes, dict(setting=SETTING, value=raw, outcome='on', minutes=list(minutes),
                         rule='first block %s min, then %s-min blocks (the last length repeats)' % (minutes[0], minutes[-1]))


def trading_day_open_ns(day):
    """The trading day's open on the receive clock: 18:00 America/New_York of the calendar day before `day` (YYYYMMDD),
    in ns since the epoch. (value, basis) or (None, why)."""
    try:
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        hour, zone = TRADING_DAY_OPEN
        trade = datetime.strptime(str(day), '%Y%m%d')
        opened = (trade - timedelta(days=1)).replace(hour=hour, tzinfo=ZoneInfo(zone))
        return int(opened.timestamp()) * 1_000_000_000, 'trading-day open %s %s %02d:00 (%s)' % (
            zone, opened.strftime('%Y-%m-%d'), hour, opened.astimezone(ZoneInfo('UTC')).strftime('%Y-%m-%dT%H:%M:%SZ'))
    except Exception as error:  # noqa: BLE001 - the caller falls back to the first row's clock (named)
        return None, 'no trading-day open for %r (%s: %s)' % (day, type(error).__name__, error)


class Schedule:
    def __init__(self, minutes):
        self.minutes = tuple(minutes)
        self.lengths = tuple(int(round(m * NS_PER_MINUTE)) for m in self.minutes)

    def length(self, index):
        """The length (ns) of block `index` (1-based)."""
        return self.lengths[min(index, len(self.lengths)) - 1]

    def record(self):
        return dict(minutes=list(self.minutes), lengths_ns=list(self.lengths),
                    rule='block 1 is %s min, every later block %s min (the last listed length repeats)' % (
                        self.minutes[0], self.minutes[-1]))


class Cutter:
    """Block boundaries on the receive clock, rows offered in cursor order. offer() returns the blocks the row closed
    (each a dict); close() closes the open one as the day's last."""

    def __init__(self, schedule, origin_ns, *, index=1, start_cursor=0, start_ns=None, known_by=None, lock=None):
        self.schedule = schedule
        self.origin = origin_ns
        self.index = index
        self.start_cursor = start_cursor
        self.start_ns = origin_ns if start_ns is None else start_ns
        self.end_ns = self.start_ns + schedule.length(index)
        self.known_by = known_by                  # the running max of the receive clock over every row offered so far
        self.lock = lock                           # known_by through the last closed block (its teacher as_of)
        self._open()

    def _open(self):
        self.rows, self.first_clock, self.last_clock, self.late = 0, None, None, []

    def state(self):
        return dict(origin_ns=self.origin, index=self.index, start_cursor=self.start_cursor, start_ns=self.start_ns,
                    end_ns=self.end_ns, known_by=self.known_by, lock=self.lock)

    def _close(self, end_cursor, final=False):
        block = dict(index=self.index, cursor_range=[self.start_cursor, end_cursor], rows=end_cursor - self.start_cursor,
                     clock_range=[self.start_ns, self.end_ns], first_row_clock=self.first_clock,
                     last_row_clock=self.last_clock, known_by=self.known_by,
                     teacher_as_of=self.known_by if self.rows else self.lock, late_rows=self.late, final=final)
        self.lock = block['teacher_as_of']
        self.index += 1
        self.start_cursor = end_cursor
        self.start_ns = self.end_ns
        self.end_ns = self.start_ns + self.schedule.length(self.index)
        self._open()
        return block

    def offer(self, cursor, recv_ns):
        if cursor != self.start_cursor + self.rows:
            raise ValueError('block rows must be offered in cursor order: expected %d, got %d'
                             % (self.start_cursor + self.rows, cursor))
        closed = []
        known = recv_ns if self.known_by is None else max(self.known_by, recv_ns)
        while known >= self.end_ns:
            closed.append(self._close(cursor))
        self.known_by = known
        if recv_ns < self.start_ns:
            self.late.append(dict(cursor=cursor, ts_recv_ns=recv_ns, block_start_ns=self.start_ns))
        if self.first_clock is None:
            self.first_clock = recv_ns
        self.last_clock = recv_ns
        self.rows += 1
        return closed

    def close(self):
        return self._close(self.start_cursor + self.rows, final=True)


def _fsync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json_atomic(path, doc):
    """temp, fsync, rename, directory fsync; returns (bytes, sha256)."""
    path = Path(path)
    data = (json.dumps(doc, indent=1, sort_keys=True, default=str) + '\n').encode()
    pending = path.with_name('.%s.%d.pending' % (path.name, os.getpid()))
    with pending.open('wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(pending, path)
    _fsync_dir(path.parent)
    return len(data), hashlib.sha256(data).hexdigest()


def read_manifest(rows_dir):
    path = Path(rows_dir) / MANIFEST_FILE
    if not path.is_file():
        return None
    return json.loads(path.read_bytes())


class BlockSealer:
    """The sidecar appended per block, blocks/<n>.json and the manifest. Opened once per teacher process; a manifest left
    by an earlier process of the same day is continued (its sealed blocks stand)."""

    def __init__(self, rows_dir, *, day, schedule, origin_ns, origin_basis, header, sidecar_name, log=print,
                 wake_dir=None, setting=None):
        self.dir = Path(rows_dir)
        self.blocks_dir = self.dir / BLOCKS_DIR
        self.sidecar = self.dir / sidecar_name
        self.log, self.wake_dir, self.day = log, wake_dir, day
        self.notes = []
        self.blocks_dir.mkdir(parents=True, exist_ok=True)
        header_bytes = (json.dumps(header, allow_nan=False) + '\n').encode()
        manifest = read_manifest(self.dir)
        if manifest is not None:
            if manifest.get('schema') != MANIFEST_SCHEMA or manifest.get('day') != day:
                raise ValueError('%s holds a manifest of another day or schema; preserved' % (self.dir / MANIFEST_FILE))
            self.manifest = manifest
            if list(manifest['schedule']['minutes']) != list(schedule.minutes):
                self.notes.append('the schedule %s of the sealed blocks stands (the setting now says %s)' % (
                    manifest['schedule']['minutes'], list(schedule.minutes)))
            self.schedule = Schedule(manifest['schedule']['minutes'])
            if hashlib.sha256(header_bytes).hexdigest() != manifest['header']['sha256']:
                self.notes.append('the sidecar header of the sealed blocks stands (this process would write %s)'
                                  % hashlib.sha256(header_bytes).hexdigest())
            size = self.sidecar.stat().st_size if self.sidecar.is_file() else -1
            sealed = manifest['sealed_bytes']
            if size < sealed:
                raise ValueError('the rows sidecar %s holds %d bytes, fewer than the %d its sealed blocks pin; preserved'
                                 % (self.sidecar, size, sealed))
            if size > sealed:
                with self.sidecar.open('r+b') as handle:          # bytes written past the last seal: never sealed
                    handle.truncate(sealed)
                    handle.flush()
                    os.fsync(handle.fileno())
                self.notes.append('%d unsealed byte(s) past the last seal cut back' % (size - sealed))
            manifest.update(status='complete' if manifest.get('complete') else 'sealing', resumed_utc=utc(),
                            resumes=int(manifest.get('resumes') or 0) + 1)
            manifest.setdefault('notes', []).extend(self.notes)
            self._write_manifest()
            self._event('resumed', next_block=len(manifest['blocks']) + 1, next_cursor=manifest['next_cursor'],
                        notes=self.notes)
        else:
            self.schedule = schedule
            pending = self.sidecar.with_name(self.sidecar.name + '.pending')
            with pending.open('wb') as handle:
                handle.write(header_bytes)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(pending, self.sidecar)
            _fsync_dir(self.dir)
            self.manifest = dict(
                schema=MANIFEST_SCHEMA, day=day, rows_dir=str(self.dir), sidecar=sidecar_name, setting=setting,
                schedule=dict(self.schedule.record(), origin_ns=origin_ns, origin_basis=origin_basis,
                              clock='clock_receive_time (each row\'s ts_recv_ns); a block closes at the first row whose '
                                    'running maximum (clock_event_known_by) reaches its end clock'),
                header=dict(bytes=[0, len(header_bytes)], sha256=hashlib.sha256(header_bytes).hexdigest()),
                blocks=[], sealed_bytes=len(header_bytes), next_cursor=0, cutter=None, walk_cursor=None,
                status='sealing', complete=False, created_utc=utc(), updated_utc=utc(), notes=[],
                rule='the sidecar is the header followed by every sealed block\'s bytes, in order; a sealed block never '
                     'changes; complete is set by the teacher\'s final publication with its receipt pins')
            self._write_manifest()
            self._event('opened', origin_ns=origin_ns, origin_basis=origin_basis, schedule=list(schedule.minutes))
        self.handle = None

    # -- state
    @property
    def complete(self):
        return bool(self.manifest.get('complete'))

    @property
    def next_cursor(self):
        return self.manifest['next_cursor']

    def cutter(self, origin_ns):
        state = self.manifest.get('cutter')
        if state:
            return Cutter(self.schedule, state['origin_ns'], index=state['index'], start_cursor=state['start_cursor'],
                          start_ns=state['start_ns'], known_by=state['known_by'], lock=state['lock'])
        return Cutter(self.schedule, self.manifest['schedule'].get('origin_ns', origin_ns))

    def _write_manifest(self):
        self.manifest['updated_utc'] = utc()
        return write_json_atomic(self.dir / MANIFEST_FILE, self.manifest)

    def _event(self, kind, **facts):
        line = dict(event=kind, day=self.day, at_utc=utc(), **facts)
        data = (json.dumps(line, sort_keys=True, default=str) + '\n').encode()
        with (self.dir / EVENTS_FILE).open('ab') as handle:
            handle.write(data)
            handle.flush()
        try:
            self.log('TEACHER_BLOCK %s' % json.dumps(line, sort_keys=True, default=str))
        except Exception:  # noqa: BLE001 - the event line is on disk
            pass
        if self.wake_dir is not None:
            try:
                import frankie_box_wake as W
                W.notify(self.wake_dir, 'teacher-blocks-%s' % self.day, event=kind, block=facts.get('index'))
            except Exception:  # noqa: BLE001 - the manifest's rename already wakes a waiter on the rows directory
                pass

    # -- sealing
    def seal(self, block, lines, extra=None, cutter_state=None, walk_cursor=None):
        """Append the block's lines (bytes, each ending in a newline) to the sidecar, write blocks/<n>.json and the
        manifest. Returns the manifest's entry for the block."""
        began = time.monotonic()
        index = block['index']
        if index != len(self.manifest['blocks']) + 1:
            raise ValueError('block %d sealed out of order (%d sealed)' % (index, len(self.manifest['blocks'])))
        if block['cursor_range'][0] != self.manifest['next_cursor']:
            raise ValueError('block %d starts at cursor %d; the sealed blocks end at %d'
                             % (index, block['cursor_range'][0], self.manifest['next_cursor']))
        if self.handle is None:
            self.handle = self.sidecar.open('ab')
        start = self.manifest['sealed_bytes']
        if self.handle.tell() != start:
            raise ValueError('the rows sidecar is at byte %d, the sealed blocks end at %d' % (self.handle.tell(), start))
        digest, count = hashlib.sha256(), 0
        for data in lines:
            digest.update(data)
            self.handle.write(data)
            count += 1
        self.handle.flush()
        os.fsync(self.handle.fileno())
        end = self.handle.tell()
        doc = dict(schema=BLOCK_SCHEMA, day=self.day, **block,
                   sidecar=dict(file=self.sidecar.name, bytes=[start, end], sha256=digest.hexdigest(), lines=count,
                                rule='the bytes [start, end) of the rows sidecar: this block\'s rows, one JSON line each'),
                   **(extra or {}), written_utc=utc())
        doc['seal_seconds'] = round(time.monotonic() - began, 3)
        name = '%d.json' % index
        size, sha = write_json_atomic(self.blocks_dir / name, doc)
        entry = dict(index=index, file='%s/%s' % (BLOCKS_DIR, name), sha256=sha, bytes=size,
                     cursor_range=block['cursor_range'], clock_range=block['clock_range'], rows=block['rows'],
                     lines=count, sidecar_bytes=[start, end], sidecar_sha256=doc['sidecar']['sha256'],
                     teacher_as_of=block['teacher_as_of'], final=block.get('final', False))
        self.manifest['blocks'].append(entry)
        self.manifest.update(sealed_bytes=end, next_cursor=block['cursor_range'][1], cutter=cutter_state,
                             walk_cursor=walk_cursor if walk_cursor is not None else self.manifest.get('walk_cursor'))
        self._write_manifest()
        self._event('sealed', index=index, cursor_range=block['cursor_range'], clock_range=block['clock_range'],
                    rows=block['rows'], lines=count, sidecar_bytes=[start, end], sha256=doc['sidecar']['sha256'],
                    seal_seconds=doc['seal_seconds'], final=block.get('final', False))
        return entry

    def sealed_pin(self):
        """The sealed blocks as one pin (for the receipt): sha256 over every block entry's sha256 and sidecar sha256."""
        digest = hashlib.sha256()
        for entry in self.manifest['blocks']:
            digest.update(('%d %s %s\n' % (entry['index'], entry['sha256'], entry['sidecar_sha256'])).encode())
        return dict(manifest=MANIFEST_FILE, schema=MANIFEST_SCHEMA, blocks=len(self.manifest['blocks']),
                    sealed_bytes=self.manifest['sealed_bytes'], blocks_sha256=digest.hexdigest(),
                    schedule=self.manifest['schedule'], header=self.manifest['header'],
                    rule='blocks_sha256 = sha256 of the lines "<index> <block json sha256> <sidecar bytes sha256>\\n"')

    def finish(self, status, *, complete, **facts):
        """The manifest's last state: complete (the final publication, with its pins), or a stop (saved / stopped /
        equation_not_run) a waiter reads."""
        if self.handle is not None:
            self.handle.close()
            self.handle = None
        self.manifest.update(status=status, complete=bool(complete), **facts)
        self._write_manifest()
        self._event(status, complete=bool(complete), blocks=len(self.manifest['blocks']),
                    **{k: v for k, v in facts.items() if k in ('reason', 'walk_cursor')})

    def note_walk(self, cursor):
        self.manifest['walk_cursor'] = cursor
