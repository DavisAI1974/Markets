"""The teacher HUB core (Greg, 2026-10-09 session 12, HUB DESIGN at the top of CLAUDE.md): one hub per day, a spoke to each
workflow piece (root, teacher, classroom, exchange, jev, school, forecaster), every spoke read-calc-write under ONE TURN
LOCK: one piece in or out at a time; a waiter is recorded by name and woken event-driven when the holder releases; never
timed out, never killed; a second lap only when a piece added something new.

Standard library only (plus the box's own stdlib-only waker, frankie_box_wake.py, beside this file). POSIX box (Linux:
inotify + pidfd). Not wired into any chain: a spoke calls it.

LAYOUT: <hub_root>/<run>/<day>/
  hub.json          schema FRANKIE_HUB_V1: run, day, created_utc, pinned_sources {name: {path, sha256, bytes}}, round
                    (int, starts 1), pieces (workflow order), laps [lap records], pin_differences [..], done (bool).
  pieces/<p>.json   written only by piece <p> under its turn. Top of the file is the CURRENT round:
                    {"piece", "schema": "FRANKIE_HUB_PIECE_V1", "round", "written_utc", "additions": [...]}
                    and "rounds": the PRIOR rounds, oldest first, each {"round", "written_utc", "additions"} (the
                    history lives in the same file; no per-round files). A second write in the same round EXTENDS that
                    round's additions (nothing is replaced or lost) and is recorded as such.
  turn.lock         the atomic take (the record written whole to a temp file, then link()ed to turn.lock: EEXIST when
                    held, the same exclusivity as O_CREAT|O_EXCL, never half-written): {piece, pid, pid_start, token,
                    since_utc}.
  turn.json         the lock record: {holder, holder_pid, holder_pid_start, since_utc, token, waiters: [{piece, since_utc,
                    pid, pid_start, ticket, ordered}]}.
  turn.meta         an empty file flock()ed (opened read-only, so it never wakes a watcher) for the microseconds a
                    turn.json read-modify-write takes; the kernel releases it if its process dies.
  events.jsonl      one line per take / release / wait / wake / takeover / waiter-gone / write / lap / open /
                    pin-difference / error. Every failure is an 'error' event AND a raised HubError: never a silent None.

AN ADDITION: a dict with at least {"kind": str, "content_sha256": str} and EITHER
  {"path": absolute path, "bytes": int, "sha256": str}  a file the piece wrote; the hub never copies it and never reads
                                                         its contents (a stat confirms it exists at that size), OR
  {"value": JSON}                                        a value carried inline.
  "known_by" (a clock) is carried when the piece gives one. Any other key is carried as given. No provenance machinery:
  the piece's name at the top of its file is enough. Helpers: value_addition(), file_addition(), value_sha256().

THE SPOKE CONTRACT (each piece, each round):
  token = take_turn(hub_dir, piece, pid)    blocks, event-driven, until this piece holds the turn
  view  = read(hub_dir, piece, token, since_round=None)   hub.json + every piece's additions AS REFERENCES
  ... calc: the piece opens whatever referenced files it needs itself (the hub never reads file contents) ...
  write(hub_dir, piece, token, additions)   atomic; an empty list when the piece has nothing new this round
  release(hub_dir, piece, token)            the next waiter (FIFO) wakes the instant the lock goes
  or, the same in one block: `with turn(hub_dir, piece) as token: ...`
Then whoever closes the lap calls next_lap(hub_dir) -> True while any piece added a content_sha256 the hub had not seen in
an earlier round (content fixed point, not a size rule). It closes the lap, records new hashes per piece and any piece
that took no turn this round (listed, never a refusal), increments round, and marks done=true at the fixed point.

THE WAIT (no fixed sleep, no timed poll, no bounded wait, no timeout anywhere): a waiter appends itself to turn.json's
waiters, then blocks in frankie_box_wake.Waiter (inotify on the hub directory: turn.lock's removal and turn.json's replace
wake it; a pidfd on the holder and on every waiter ahead of it: their exit wakes it). Every wake is a hint: it re-checks
under the flock. It takes the turn when the lock is free and it is the first LIVE eligible waiter in FIFO order. A holder
whose pid is gone (crashed, SIGKILLed; pid identity = pid + its /proc start time, so a reused pid is not mistaken for the
holder) is taken over with a 'takeover' event naming the dead piece; a waiter whose pid is gone is pruned with a
'waiter-gone' event. take_turn(ordered=True) additionally waits until every piece before it in the workflow order has
written the current round (the pieces/ directory is watched too). A waiter interrupted by a signal removes itself and
records 'wait-abandoned'. Without inotify or pidfd (not the box) take_turn raises before waiting, recorded, rather than
fall back to a timed poll.

PINS: open_hub on an existing hub compares the pins BY CONTENT (sha256; bytes when no sha256 is known). A difference is
recorded in hub.json pin_differences and as an event, never a refusal; the hub keeps the pins it was opened on.

CLI: python3 frankie_box_hub.py {open,status,take,release,write,read,next-lap} (--hub-dir, or --hub-root --run --day).
  open     --pins <json file {name: {path, sha256, bytes}}> [--pieces a,b,c] [--hash-missing]   prints the hub dir
  take     --piece P [--pid PID] [--ordered]     blocks until held; prints {"token": ...}. PID defaults to the CALLER'S
           parent (the shell step that runs the piece), since this CLI process exits at once; pass the long-lived pid
           (inside $(...) the parent is a subshell that exits at once: there, always pass --pid $$).
  write    --piece P --token T --additions <json file: a list of additions>
  read     --piece P --token T [--since-round N]
  release  --piece P --token T
  next-lap [--token T]                           prints {"another_lap": bool, "round": n}
  status                                         prints the probe dict
Exit 0 on success, 1 on a HubError (its message as JSON on stderr), 2 on usage.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import frankie_box_wake as W  # noqa: E402 - the box's stdlib-only event waker, beside this file

HUB_SCHEMA = 'FRANKIE_HUB_V1'
PIECE_SCHEMA = 'FRANKIE_HUB_PIECE_V1'
DEFAULT_PIECES = ('root', 'teacher', 'classroom', 'exchange', 'jev', 'school', 'forecaster')


class HubError(Exception):
    """Every hub failure: recorded as an 'error' event first, then raised with its facts."""

    def __init__(self, message, **facts):
        super().__init__(message)
        self.facts = dict(facts, message=message)


def utc(t=None):
    t = time.time() if t is None else t
    return time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(t)) + ('.%06dZ' % int((t % 1) * 1e6))


def value_sha256(value):
    """The content hash of a JSON value: sha256 of its canonical JSON (sorted keys, no spaces, UTF-8)."""
    text = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def value_addition(kind, value, known_by=None, **extra):
    a = dict(extra, kind=kind, value=value, content_sha256=value_sha256(value))
    if known_by is not None:
        a['known_by'] = known_by
    return a


def file_addition(kind, path, sha256, bytes_=None, known_by=None, **extra):
    """A file the piece wrote. sha256 is the piece's own hash of the file (the hub never reads the contents); bytes
    defaults to a stat."""
    path = os.path.abspath(str(path))
    a = dict(extra, kind=kind, path=path, sha256=sha256, content_sha256=sha256,
             bytes=int(bytes_) if bytes_ is not None else os.stat(path).st_size)
    if known_by is not None:
        a['known_by'] = known_by
    return a


# ---------------------------------------------------------------------------------------------------------------- disk

def _dump(path, doc):
    """Atomic: temp file in the same directory, fsync, rename."""
    path = Path(path)
    tmp = path.parent / ('.%s.%d.%s.tmp' % (path.name, os.getpid(), uuid.uuid4().hex[:8]))
    with open(tmp, 'w', encoding='utf-8') as f:
        f.write(json.dumps(doc, indent=1, sort_keys=False, default=str) + '\n')
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _load(path, default=None):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def event(hub_dir, kind, piece=None, **facts):
    """One line in events.jsonl (O_APPEND, one write: lines from many processes never interleave)."""
    line = dict(utc=utc(), t_ns=time.time_ns(), pid=os.getpid(), event=kind, piece=piece, **facts)
    data = (json.dumps(line, sort_keys=True, default=str) + '\n').encode('utf-8')
    fd = os.open(str(Path(hub_dir) / 'events.jsonl'), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    return line


def _fail(hub_dir, message, piece=None, **facts):
    try:
        event(hub_dir, 'error', piece, message=message, **facts)
    except OSError as error:            # the event log itself is unwritable: the raise still names both
        facts['event_log_error'] = str(error)
    raise HubError(message, piece=piece, hub_dir=str(hub_dir), **facts)


@contextlib.contextmanager
def _meta(hub_dir):
    """The short exclusive flock around a turn.json read-modify-write. Opened READ-ONLY: its close is IN_CLOSE_NOWRITE,
    which no watcher listens for, so taking it never wakes a waiter (a write-open would wake every waiter on every check)."""
    path = Path(hub_dir) / 'turn.meta'
    if not path.exists():
        os.close(os.open(str(path), os.O_WRONLY | os.O_CREAT, 0o644))
    fd = os.open(str(path), os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)                    # closing the descriptor releases the flock


def _pid_start(pid):
    """The process start time (clock ticks since boot, /proc/<pid>/stat field 22), or None when the pid is gone or
    /proc is absent. pid + start time names one process; a reused pid has another start time."""
    try:
        with open('/proc/%d/stat' % int(pid), 'rb') as f:
            fields = f.read().rsplit(b')', 1)[1].split()
        return fields[19].decode() if fields[0] != b'Z' else None
    except (OSError, IndexError, ValueError):
        return None


def _live(pid, start):
    if pid is None or not W.alive(pid):
        return False
    now = _pid_start(pid)
    return start is None or now is None or now == start


def _safe_name(hub_root, label, value):
    value = str(value)
    if not value or '/' in value or value in ('.', '..') or '\0' in value:
        raise HubError('%s %r is not a single path component' % (label, value), hub_root=str(hub_root))
    return value


def hub_dir_of(hub_root, run, day):
    return Path(hub_root) / _safe_name(hub_root, 'run', run) / _safe_name(hub_root, 'day', day)


def _hub(hub_dir):
    doc = _load(Path(hub_dir) / 'hub.json')
    if doc is None:
        raise HubError('no hub.json: the hub was never opened', hub_dir=str(hub_dir))
    return doc


def _turn(hub_dir):
    return _load(Path(hub_dir) / 'turn.json', {}) or {}


def _empty_turn():
    return dict(holder=None, holder_pid=None, holder_pid_start=None, since_utc=None, token=None, waiters=[])


# ---------------------------------------------------------------------------------------------------------------- open

def _pin_key(pin):
    if not isinstance(pin, dict):
        return ('value', json.dumps(pin, sort_keys=True, default=str))
    if pin.get('sha256'):
        return ('sha256', pin['sha256'])
    if pin.get('bytes') is not None:
        return ('bytes', pin['bytes'])
    return ('unknown', None)


def _normal_pins(pinned_sources, hash_missing):
    pins = {}
    for name, pin in (pinned_sources or {}).items():
        pin = dict(pin) if isinstance(pin, dict) else dict(path=str(pin))
        path = pin.get('path')
        if path:
            pin['path'] = os.path.abspath(str(path))
            if pin.get('bytes') is None or (hash_missing and not pin.get('sha256')):
                try:
                    if hash_missing and not pin.get('sha256'):
                        import frankie_box_filehash as FH
                        pin.update(FH.witness(pin['path']))
                    else:
                        pin['bytes'] = os.stat(pin['path']).st_size
                except OSError as error:
                    pin['unreadable'] = str(error)      # listed on the pin, never a refusal
        pins[str(name)] = pin
    return pins


def open_hub(hub_root, run, day, pinned_sources, pieces=None, hash_missing=False):
    """Create the day's hub, or reuse the existing one. Returns the hub directory (a Path). On reuse the pins are
    compared by content and every difference is recorded (pin_differences + an event), never refused."""
    hub_dir = hub_dir_of(hub_root, run, day)
    (hub_dir / 'pieces').mkdir(parents=True, exist_ok=True)
    pins = _normal_pins(pinned_sources, hash_missing)
    order = list(pieces) if pieces else list(DEFAULT_PIECES)
    for p in order:
        _safe_name(hub_root, 'piece', p)
    with _meta(hub_dir):
        doc = _load(hub_dir / 'hub.json')
        if doc is None:
            doc = dict(schema=HUB_SCHEMA, run=str(run), day=str(day), created_utc=utc(), pinned_sources=pins, round=1,
                       pieces=order, laps=[], pin_differences=[], done=False)
            _dump(hub_dir / 'hub.json', doc)
            if not (hub_dir / 'turn.json').exists():
                _dump(hub_dir / 'turn.json', _empty_turn())
            event(hub_dir, 'open', None, created=True, round=1, pieces=order, pins=sorted(pins))
            return hub_dir
        differences = []
        old = doc.get('pinned_sources') or {}
        for name in sorted(set(old) | set(pins)):
            if name not in pins:
                continue                                 # a reopen that does not restate a pin changes nothing
            if name not in old:
                differences.append(dict(name=name, was=None, now=pins[name], reason='pin not in the hub when opened'))
            elif _pin_key(old[name]) != _pin_key(pins[name]):
                differences.append(dict(name=name, was=old[name], now=pins[name], reason='content differs'))
        if pieces and list(pieces) != doc.get('pieces'):
            differences.append(dict(name='pieces', was=doc.get('pieces'), now=list(pieces),
                                    reason='piece order differs; the hub keeps its own'))
        if differences:
            stamp = utc()
            doc.setdefault('pin_differences', []).extend(dict(d, utc=stamp, pid=os.getpid()) for d in differences)
            _dump(hub_dir / 'hub.json', doc)
            for d in differences:
                event(hub_dir, 'pin-difference', None, **d)
        event(hub_dir, 'open', None, created=False, round=doc.get('round'), differences=len(differences))
    return hub_dir


# ---------------------------------------------------------------------------------------------------------------- turn

def _check_piece(hub_dir, piece):
    order = _hub(hub_dir).get('pieces') or []
    if piece not in order:
        _fail(hub_dir, 'piece %r is not one of this hub\'s pieces %s' % (piece, order), piece)
    return order


def _round_written(hub_dir, piece, rnd):
    doc = _load(Path(hub_dir) / 'pieces' / ('%s.json' % piece))
    return bool(doc) and doc.get('round') == rnd


def _eligible(hub_dir, w, hub_doc):
    if not w.get('ordered'):
        return True
    order, rnd = hub_doc.get('pieces') or [], hub_doc.get('round')
    before = order[:order.index(w['piece'])] if w['piece'] in order else []
    return all(_round_written(hub_dir, p, rnd) for p in before)


def _reap(hub_dir, turn, lock):
    """Under the flock: take over a dead holder's turn and prune dead waiters, each with an event. Returns
    (turn, lock, changed)."""
    changed = False
    if lock is not None and not _live(lock.get('pid'), lock.get('pid_start')):
        try:
            os.unlink(Path(hub_dir) / 'turn.lock')
        except FileNotFoundError:
            pass
        event(hub_dir, 'takeover', lock.get('piece'), dead_pid=lock.get('pid'), dead_token=lock.get('token'),
              held_since=lock.get('since_utc'), by_pid=os.getpid(),
              reason='holder pid gone (crashed or killed); its turn is released for the next waiter')
        turn.update(holder=None, holder_pid=None, holder_pid_start=None, since_utc=None, token=None)
        lock, changed = None, True
    keep = []
    for w in turn.get('waiters') or []:
        if _live(w.get('pid'), w.get('pid_start')):
            keep.append(w)
        else:
            event(hub_dir, 'waiter-gone', w.get('piece'), dead_pid=w.get('pid'), waiting_since=w.get('since_utc'),
                  ticket=w.get('ticket'))
            changed = True
    turn['waiters'] = keep
    return turn, lock, changed


def _read_lock(hub_dir):
    return _load(Path(hub_dir) / 'turn.lock')


def _create_lock(hub_dir, record):
    """The atomic take: the record is written whole to a temp file, then hard-linked to turn.lock (link() fails with
    EEXIST when the lock exists, the same exclusivity as O_CREAT|O_EXCL, and a reader never sees a half-written lock).
    True when taken, False when the lock already existed."""
    tmp = Path(hub_dir) / ('.turn.lock.%d.%s.tmp' % (os.getpid(), uuid.uuid4().hex[:8]))
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        os.write(fd, (json.dumps(record) + '\n').encode('utf-8'))
        os.fsync(fd)
    finally:
        os.close(fd)
    try:
        os.link(tmp, Path(hub_dir) / 'turn.lock')
        return True
    except FileExistsError:
        return False
    finally:
        os.unlink(tmp)


def take_turn(hub_dir, piece, pid=None, ordered=False):
    """Block (event-driven, never timed) until `piece` holds the hub's one turn; return the turn token. pid is the
    process whose life holds the turn (default this process); if it dies, the next waiter takes the turn over."""
    hub_dir = Path(hub_dir)
    _check_piece(hub_dir, piece)
    pid = int(pid) if pid is not None else os.getpid()
    start = _pid_start(pid)
    if not W.alive(pid):
        _fail(hub_dir, 'pid %d named as the turn holder is not running' % pid, piece, holder_pid=pid)
    ticket = uuid.uuid4().hex
    me = dict(piece=piece, since_utc=utc(), pid=pid, pid_start=start, ticket=ticket, ordered=bool(ordered))
    waiter = W.Waiter([hub_dir, hub_dir / 'pieces'])     # built BEFORE the first check, so no release can be missed
    if waiter.fd is None:
        waiter.close()
        _fail(hub_dir, 'no inotify on this host: the hub will not fall back to a timed poll', piece)
    try:
        probe = W.pidfd(os.getpid())
        if probe is not None:
            os.close(probe)
    except OSError as error:
        waiter.close()
        _fail(hub_dir, 'no pidfd on this host (%s): a crashed holder could not wake its waiters' % error, piece)
    waited, enrolled = False, False
    try:
        while True:
            with _meta(hub_dir):
                turn = _turn(hub_dir) or _empty_turn()
                lock = _read_lock(hub_dir)
                turn, lock, changed = _reap(hub_dir, turn, lock)
                if lock is not None and lock.get('piece') == piece and lock.get('pid') == pid and not enrolled:
                    event(hub_dir, 'take-held', piece, token=lock.get('token'), note='this piece and pid already hold it')
                    if changed:
                        _dump(hub_dir / 'turn.json', turn)
                    return lock['token']
                if not enrolled:
                    turn.setdefault('waiters', []).append(me)
                    enrolled, changed = True, True
                hub_doc = _hub(hub_dir)
                eligible = [w for w in turn['waiters'] if _eligible(hub_dir, w, hub_doc)]
                if lock is None and eligible and eligible[0]['ticket'] == ticket:
                    token = uuid.uuid4().hex
                    record = dict(piece=piece, pid=pid, pid_start=start, token=token, since_utc=utc())
                    if not _create_lock(hub_dir, record):  # cannot happen under the flock; listed if it ever does
                        event(hub_dir, 'error', piece, message='turn.lock appeared under the flock; re-checking')
                        continue
                    turn['waiters'] = [w for w in turn['waiters'] if w['ticket'] != ticket]
                    turn.update(holder=piece, holder_pid=pid, holder_pid_start=start, since_utc=record['since_utc'],
                                token=token)
                    _dump(hub_dir / 'turn.json', turn)
                    now = time.time_ns()
                    if waited:
                        released_ns = _last_release_ns(hub_dir)
                        event(hub_dir, 'wake', piece, ticket=ticket,
                              after_release_ns=(now - released_ns) if released_ns else None,
                              waited_since=me['since_utc'])
                    event(hub_dir, 'take', piece, token=token, holder_pid=pid, round=hub_doc.get('round'),
                          waited=waited, ordered=bool(ordered))
                    return token
                if changed:
                    _dump(hub_dir / 'turn.json', turn)
                ahead = []
                for w in turn['waiters']:
                    if w['ticket'] == ticket:
                        break
                    ahead.append(w)
                if not waited:
                    waited = True
                    reason = ('held by %s' % lock.get('piece')) if lock else (
                        'earlier pieces have not written this round' if not _eligible(hub_dir, me, hub_doc)
                        else 'behind earlier waiters')
                    event(hub_dir, 'wait', piece, ticket=ticket, holder=(lock or {}).get('piece'),
                          holder_pid=(lock or {}).get('pid'), position=len(ahead) + 1,
                          ahead=[w['piece'] for w in ahead], reason=reason, ordered=bool(ordered))
                watch = ([lock.get('pid')] if lock else []) + [w.get('pid') for w in ahead]
            for p in watch:
                if p is not None:
                    waiter.watch_pid(p)
            waiter.wait()                               # no timeout: a release, a write or an exit wakes it
            waiter.fired.clear()
    except BaseException as error:
        if enrolled and not isinstance(error, HubError):
            try:
                with _meta(hub_dir):
                    turn = _turn(hub_dir)
                    if any(w.get('ticket') == ticket for w in turn.get('waiters') or []):
                        turn['waiters'] = [w for w in turn['waiters'] if w.get('ticket') != ticket]
                        _dump(hub_dir / 'turn.json', turn)
                        event(hub_dir, 'wait-abandoned', piece, ticket=ticket, reason=repr(error))
            except OSError:
                pass
        raise
    finally:
        waiter.close()


def _last_release_ns(hub_dir):
    """The t_ns of the newest release/takeover event (read from the log's tail), for the wake latency."""
    try:
        with open(Path(hub_dir) / 'events.jsonl', 'rb') as f:
            end = f.seek(0, os.SEEK_END)
            f.seek(max(0, end - 65536))
            tail = f.read().splitlines()
    except OSError:
        return None
    for raw in reversed(tail):
        try:
            line = json.loads(raw)
        except ValueError:
            continue
        if line.get('event') in ('release', 'takeover'):
            return line.get('t_ns')
    return None


def _holder(hub_dir, piece, token, action):
    lock = _read_lock(hub_dir)
    if lock is None:
        _fail(hub_dir, '%s by %s without the turn: nobody holds it' % (action, piece), piece, token=token)
    if lock.get('piece') != piece or lock.get('token') != token:
        _fail(hub_dir, '%s by %s refused: the turn is held by %s with another token' % (action, piece, lock.get('piece')),
              piece, token=token, holder=lock.get('piece'), holder_pid=lock.get('pid'))
    return lock


def release(hub_dir, piece, token, reason=None):
    """Give the turn back. The next live waiter in FIFO order wakes the instant the lock goes (inotify)."""
    hub_dir = Path(hub_dir)
    with _meta(hub_dir):
        lock = _holder(hub_dir, piece, token, 'release')
        turn = _turn(hub_dir) or _empty_turn()
        os.unlink(hub_dir / 'turn.lock')
        turn.update(holder=None, holder_pid=None, holder_pid_start=None, since_utc=None, token=None)
        hub_doc = _hub(hub_dir)
        live = [w for w in turn.get('waiters') or [] if _live(w.get('pid'), w.get('pid_start'))]
        nxt = next((w for w in live if _eligible(hub_dir, w, hub_doc)), None)
        event(hub_dir, 'release', piece, token=token, held_since=lock.get('since_utc'),
              next_waiter=(nxt or {}).get('piece'), next_pid=(nxt or {}).get('pid'),
              waiters=[w.get('piece') for w in live], reason=reason)
        _dump(hub_dir / 'turn.json', turn)              # the replace (IN_MOVED_TO) and the unlink both wake waiters


@contextlib.contextmanager
def turn(hub_dir, piece, pid=None, ordered=False):
    """`with turn(hub_dir, piece) as token:` take, run the block, release (also when the block raises; the error is named
    in the release event)."""
    token = take_turn(hub_dir, piece, pid=pid, ordered=ordered)
    try:
        yield token
    except BaseException as error:
        release(hub_dir, piece, token, reason='block raised: %r' % (error,))
        raise
    release(hub_dir, piece, token)


# ----------------------------------------------------------------------------------------------------------- read/write

def _piece_doc(hub_dir, piece):
    return _load(Path(hub_dir) / 'pieces' / ('%s.json' % piece))


def _rounds_of(doc):
    """Every round of a piece file, oldest first: the prior rounds then the current one."""
    if not doc:
        return []
    current = dict(round=doc.get('round'), written_utc=doc.get('written_utc'), additions=doc.get('additions') or [])
    return list(doc.get('rounds') or []) + [current]


def read(hub_dir, piece, token, since_round=None):
    """The hub's current set, as references (paths, hashes, values); no file content is read or copied.
    since_round=n returns only rounds after n (a delta)."""
    hub_dir = Path(hub_dir)
    _holder(hub_dir, piece, token, 'read')
    hub_doc = _hub(hub_dir)
    pieces = {}
    for p in hub_doc.get('pieces') or []:
        rounds = [r for r in _rounds_of(_piece_doc(hub_dir, p))
                  if since_round is None or (r.get('round') or 0) > int(since_round)]
        pieces[p] = dict(rounds=rounds)
    return dict(hub=hub_doc, pieces=pieces, since_round=since_round, read_utc=utc())


def _problems(additions):
    out = []
    if not isinstance(additions, list):
        return ['additions must be a list, got %s' % type(additions).__name__]
    for i, a in enumerate(additions):
        if not isinstance(a, dict):
            out.append('[%d] is not a dict' % i)
            continue
        if not isinstance(a.get('kind'), str) or not a['kind']:
            out.append('[%d] kind must be a non-empty str' % i)
        if not isinstance(a.get('content_sha256'), str) or not a['content_sha256']:
            out.append('[%d] content_sha256 must be a non-empty str' % i)
        has_path, has_value = 'path' in a, 'value' in a
        if has_path == has_value:
            out.append('[%d] needs exactly one of path (a file) or value (JSON)' % i)
        if has_path:
            if not isinstance(a['path'], str) or not os.path.isabs(a['path']):
                out.append('[%d] path must be absolute' % i)
            elif not isinstance(a.get('bytes'), int) or not isinstance(a.get('sha256'), str):
                out.append('[%d] a file addition carries bytes (int) and sha256 (str)' % i)
            else:
                try:
                    size = os.stat(a['path']).st_size     # metadata only: the hub never reads the contents
                    if size != a['bytes']:
                        out.append('[%d] %s is %d bytes, the addition says %d' % (i, a['path'], size, a['bytes']))
                except OSError as error:
                    out.append('[%d] %s: %s' % (i, a['path'], error))
        if has_value:
            try:
                json.dumps(a['value'])
            except (TypeError, ValueError) as error:
                out.append('[%d] value is not JSON: %s' % (i, error))
    return out


def write(hub_dir, piece, token, additions):
    """Write this piece's additions for the current round (atomic temp + rename). The prior rounds move under "rounds";
    a second write in the same round extends that round's list. Returns the piece file's path."""
    hub_dir = Path(hub_dir)
    _holder(hub_dir, piece, token, 'write')
    problems = _problems(additions)
    if problems:
        _fail(hub_dir, 'write by %s refused: %d malformed additions' % (piece, len(problems)), piece, problems=problems)
    rnd = _hub(hub_dir).get('round')
    path = hub_dir / 'pieces' / ('%s.json' % piece)
    doc = _piece_doc(hub_dir, piece)
    extended = False
    if doc and doc.get('round') == rnd:
        current = list(doc.get('additions') or []) + list(additions)
        prior, extended = list(doc.get('rounds') or []), True
    else:
        current = list(additions)
        prior = _rounds_of(doc)
    new = dict(piece=piece, schema=PIECE_SCHEMA, round=rnd, written_utc=utc(), additions=current, rounds=prior)
    _dump(path, new)
    event(hub_dir, 'write', piece, round=rnd, additions=len(additions), round_total=len(current), extended=extended,
          kinds=sorted({a['kind'] for a in additions}))
    return path


# ----------------------------------------------------------------------------------------------------------------- laps

def next_lap(hub_dir, token=None):
    """Close the current lap. Records, per piece, the content hashes it added this round that the hub had not seen in
    any earlier round, and the pieces that took no turn this round (listed, not refused). Increments round. Returns
    True when another lap is needed (any new hash), False at the content fixed point (hub done=true). If a piece holds
    the turn, its token is required (the lap must not close under a write)."""
    hub_dir = Path(hub_dir)
    with _meta(hub_dir):
        lock = _read_lock(hub_dir)
        if lock is not None and _live(lock.get('pid'), lock.get('pid_start')) and lock.get('token') != token:
            _fail(hub_dir, 'next_lap while %s holds the turn (pass its token, or let it release)' % lock.get('piece'),
                  None, holder=lock.get('piece'))
        doc = _hub(hub_dir)
        rnd = doc.get('round')
        seen, current = set(), {}
        for p in doc.get('pieces') or []:
            for r in _rounds_of(_piece_doc(hub_dir, p)):
                hashes = [a.get('content_sha256') for a in r.get('additions') or []]
                if r.get('round') == rnd:
                    current[p] = hashes
                elif (r.get('round') or 0) < rnd:
                    seen.update(hashes)
        new_by_piece, counted = {}, set()
        for p in doc.get('pieces') or []:
            fresh = [h for h in current.get(p, []) if h not in seen and h not in counted]
            counted.update(fresh)
            new_by_piece[p] = fresh
        another = any(new_by_piece.values())
        missing = [p for p in doc.get('pieces') or [] if p not in current]
        lap = dict(round=rnd, closed_utc=utc(), wrote=[p for p in doc.get('pieces') or [] if p in current],
                   missing_turns=missing, new_by_piece=new_by_piece, new_total=len(counted), another_lap=another)
        doc.setdefault('laps', []).append(lap)
        doc['round'] = rnd + 1
        doc['done'] = not another
        if not another:
            doc['fixed_point_round'] = rnd
        _dump(hub_dir / 'hub.json', doc)
        event(hub_dir, 'lap', None, **lap)
    return another


# --------------------------------------------------------------------------------------------------------------- status

def status(hub_dir):
    hub_dir = Path(hub_dir)
    doc = _hub(hub_dir)
    turn_doc = _turn(hub_dir)
    lock = _read_lock(hub_dir)
    last_lap = (doc.get('laps') or [None])[-1]
    pieces = {}
    for p in doc.get('pieces') or []:
        pd = _piece_doc(hub_dir, p)
        rounds = _rounds_of(pd)
        pieces[p] = dict(last_round=(pd or {}).get('round'), last_round_additions=len((pd or {}).get('additions') or []),
                         total_additions=sum(len(r.get('additions') or []) for r in rounds),
                         rounds_written=[r.get('round') for r in rounds],
                         new_hashes_last_lap=len(((last_lap or {}).get('new_by_piece') or {}).get(p, [])))
    rnd = doc.get('round')
    return dict(hub_dir=str(hub_dir), run=doc.get('run'), day=doc.get('day'), round=rnd, done=doc.get('done'),
                holder=(lock or {}).get('piece'), holder_pid=(lock or {}).get('pid'),
                holder_alive=None if lock is None else _live(lock.get('pid'), lock.get('pid_start')),
                holder_since=(lock or {}).get('since_utc'),
                waiters=[dict(piece=w.get('piece'), since_utc=w.get('since_utc'), pid=w.get('pid'),
                              alive=_live(w.get('pid'), w.get('pid_start')), ordered=w.get('ordered'))
                         for w in turn_doc.get('waiters') or []],
                next_in_order=next((p for p in doc.get('pieces') or [] if not _round_written(hub_dir, p, rnd)), None),
                laps=len(doc.get('laps') or []), last_lap=last_lap, pieces=pieces,
                pin_differences=len(doc.get('pin_differences') or []))


# ------------------------------------------------------------------------------------------------------------------ CLI

def _hub_dir_arg(a):
    if a.hub_dir:
        return Path(a.hub_dir)
    if not (a.hub_root and a.run and a.day):
        raise HubError('give --hub-dir, or --hub-root --run --day')
    return hub_dir_of(a.hub_root, a.run, a.day)


def main(argv=None):
    ap = argparse.ArgumentParser(description='The teacher hub core (frankie_box_hub.py).')
    ap.add_argument('command', choices=['open', 'status', 'take', 'release', 'write', 'read', 'next-lap'])
    ap.add_argument('--hub-dir')
    ap.add_argument('--hub-root')
    ap.add_argument('--run')
    ap.add_argument('--day')
    ap.add_argument('--piece')
    ap.add_argument('--pid', type=int)
    ap.add_argument('--token')
    ap.add_argument('--ordered', action='store_true')
    ap.add_argument('--pins', help='JSON file {name: {path, sha256, bytes}}')
    ap.add_argument('--pieces', help='comma-separated workflow order (default %s)' % ','.join(DEFAULT_PIECES))
    ap.add_argument('--hash-missing', action='store_true', help='hash pins given without a sha256')
    ap.add_argument('--additions', help='JSON file: a list of additions')
    ap.add_argument('--since-round', type=int)
    a = ap.parse_args(argv)
    try:
        if a.command == 'open':
            if not (a.hub_root and a.run and a.day):
                raise HubError('open needs --hub-root --run --day')
            try:
                pins = json.loads(Path(a.pins).read_text(encoding='utf-8')) if a.pins else {}
            except (OSError, ValueError) as error:
                raise HubError('the pins file %s is unreadable: %s' % (a.pins, error))
            pieces = [p for p in a.pieces.split(',') if p] if a.pieces else None
            print(open_hub(a.hub_root, a.run, a.day, pins, pieces, hash_missing=a.hash_missing))
            return 0
        hub_dir = _hub_dir_arg(a)
        if a.command == 'status':
            print(json.dumps(status(hub_dir), indent=1, default=str))
            return 0
        if a.command == 'next-lap':
            another = next_lap(hub_dir, a.token)
            print(json.dumps(dict(another_lap=another, round=_hub(hub_dir).get('round'))))
            return 0
        if not a.piece:
            raise HubError('%s needs --piece' % a.command)
        if a.command == 'take':
            pid = a.pid if a.pid is not None else os.getppid()   # this CLI exits at once; its caller holds the turn
            print(json.dumps(dict(token=take_turn(hub_dir, a.piece, pid=pid, ordered=a.ordered), holder_pid=pid)))
            return 0
        if not a.token:
            raise HubError('%s needs --token' % a.command)
        if a.command == 'release':
            release(hub_dir, a.piece, a.token)
        elif a.command == 'write':
            if not a.additions:
                raise HubError('write needs --additions <json file>')
            _holder(hub_dir, a.piece, a.token, 'write')
            try:
                additions = json.loads(Path(a.additions).read_text(encoding='utf-8'))
            except (OSError, ValueError) as error:
                _fail(hub_dir, 'write by %s: the additions file %s is unreadable: %s' % (a.piece, a.additions, error),
                      a.piece)
            print(write(hub_dir, a.piece, a.token, additions))
        elif a.command == 'read':
            print(json.dumps(read(hub_dir, a.piece, a.token, a.since_round), indent=1, default=str))
        return 0
    except HubError as error:
        print(json.dumps(dict(error=str(error), **{k: v for k, v in error.facts.items() if k != 'message'}),
                         default=str), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
