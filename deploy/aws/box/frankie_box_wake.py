"""Event-driven waits for the run chain (Greg, 2026-10-09: "Stop coding in wait times. We are moving quickly through this
and that is slowing us down and causing problems").

No fixed sleep and no poll interval on a hand-off. A process that waits on another process blocks on a primitive that
wakes the instant something it depends on changes, then re-checks its own condition:

  - inotify on directories (Linux): a file written, replaced (os.replace = IN_MOVED_TO), created or removed there;
  - a pidfd per process (Linux >= 5.3): readable the instant that process exits;
  - the queue's WAKE directory (<queue>/wake): a hand-off that changes state anywhere on the box writes one small file
    there (notify), so every waiter on the box wakes at once. Writers notify only on a real state change (a new stage
    status, a queue entry's state, a save marker), never on a waiter's own repeated 'waiting' record, so a waiter never
    wakes itself in a loop.

The usage that cannot miss a wake: build the Waiter FIRST, then check the condition, then wait; check again after every
wake (a wake is a hint, never the condition itself). A Waiter that gained a watch on a directory created since its last
wait returns at once, so a file written into a new directory is never missed.

A timeout is only ever a process's own lifetime bound (a worker's MAX_SECONDS), never a poll interval.

CLI (shell wrappers that have a checkout): `python frankie_box_wake.py pids-exit [--bound S] PID...` blocks until every
pid has exited (exit 0) or the bound passed (exit 1, the live pids printed); `notify DIR TOPIC` writes one wake file.
"""
import ctypes
import ctypes.util
import errno
import json
import os
import select
import struct
import sys
import time
from pathlib import Path

IN_MODIFY = 0x2                 # opt-in only (Waiter(modify=True)): a file written in place through a held handle
IN_ATTRIB, IN_CLOSE_WRITE, IN_MOVED_FROM, IN_MOVED_TO = 0x4, 0x8, 0x40, 0x80
IN_CREATE, IN_DELETE, IN_DELETE_SELF, IN_MOVE_SELF = 0x100, 0x200, 0x400, 0x800
IN_ONLYDIR = 0x01000000
IN_CLOEXEC, IN_NONBLOCK = 0o2000000, 0o4000
MASK = IN_ATTRIB | IN_CLOSE_WRITE | IN_MOVED_FROM | IN_MOVED_TO | IN_CREATE | IN_DELETE | IN_DELETE_SELF | IN_MOVE_SELF
SYS_PIDFD_OPEN = 434            # the same number on x86_64 and aarch64

_libc = None


def _lib():
    global _libc
    if _libc is None:
        try:
            _libc = ctypes.CDLL(ctypes.util.find_library('c') or 'libc.so.6', use_errno=True)
            _libc.inotify_init1  # noqa: B018 - the attribute lookup proves the call exists
        except (OSError, AttributeError):
            _libc = False
    return _libc


def pidfd(pid):
    """A pidfd for pid (readable once it exits), or None when the pid is already gone. Raises OSError when the kernel
    offers no pidfd (then the caller has no event for that pid and says so)."""
    try:
        if hasattr(os, 'pidfd_open'):
            return os.pidfd_open(int(pid))
        lib = _lib()
        if not lib:
            raise OSError(errno.ENOSYS, 'no libc for pidfd_open')
        fd = lib.syscall(SYS_PIDFD_OPEN, ctypes.c_int(int(pid)), ctypes.c_uint(0))
        if fd < 0:
            raise OSError(ctypes.get_errno(), os.strerror(ctypes.get_errno()))
        return fd
    except ProcessLookupError:
        return None
    except OSError as error:
        if error.errno == errno.ESRCH:
            return None
        raise


def alive(pid):
    """True while the pid runs (a zombie, exited but not yet reaped by its parent, counts as gone)."""
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    try:
        with open('/proc/%d/stat' % int(pid), 'rb') as f:
            return f.read().rsplit(b')', 1)[1].split()[0] != b'Z'
    except (OSError, IndexError):
        return True


class Waiter:
    """Blocks until a watched directory changes or a watched pid exits (or the optional lifetime timeout). Build it before
    checking the condition it guards; wait(); check again."""

    def __init__(self, dirs=(), pids=(), modify=False):
        self.fd, self.watched, self.missing, self.pids, self.fresh, self.exited = None, {}, [], {}, False, set()
        self.mask = MASK | (IN_MODIFY if modify else 0)   # modify: also wake when a file there grows (a log written live)
        self.fired = set()                         # the watched directories that had an event (cleared by the caller)
        lib = _lib()
        if lib:
            fd = lib.inotify_init1(IN_CLOEXEC | IN_NONBLOCK)
            if fd >= 0:
                self.fd = fd
        for d in dirs:
            self.watch_dir(d)
        for p in pids:
            self.watch_pid(p)

    def watch_dir(self, path):
        path = str(path)
        if path in self.watched or self.fd is None:
            return
        wd = _lib().inotify_add_watch(self.fd, path.encode(), self.mask | IN_ONLYDIR)
        if wd >= 0:
            self.watched[path] = wd
            if path in self.missing:
                self.missing.remove(path)
                self.fresh = True                  # it appeared since the last wait: the caller re-checks first
            return
        if path not in self.missing:
            self.missing.append(path)
            parent = str(Path(path).parent)        # its creation wakes the waiter; the next wait adds the watch
            if parent != path:
                self.watch_dir(parent)

    def watch_pid(self, pid):
        if pid is None or int(pid) in self.pids:
            return
        try:
            fd = pidfd(pid)
        except OSError:
            fd = -1                                # no pidfd on this kernel: that exit has no event (named by caller)
        if fd is None:
            self.fresh = True                      # already gone: the caller re-checks at once
            return
        self.pids[int(pid)] = fd

    def wait(self, timeout=None):
        """True when woken by an event, False at the timeout. Without inotify (not a Linux box) a wait is one second, the
        only fixed interval left anywhere, and only off the box."""
        for path in list(self.missing):
            self.watch_dir(path)
        if self.fresh:
            self.fresh = False
            return True
        if self.fd is None:
            time.sleep(min(1.0, timeout) if timeout is not None else 1.0)
            return True
        poll = select.poll()
        poll.register(self.fd, select.POLLIN)
        for fd in self.pids.values():
            if fd >= 0:
                poll.register(fd, select.POLLIN)
        ms = None if timeout is None else max(0, int(timeout * 1000))
        events = poll.poll(ms)
        self._drain()
        for pid, fd in list(self.pids.items()):
            if fd >= 0 and any(e[0] == fd for e in events):
                os.close(fd)
                del self.pids[pid]
                self.exited.add(pid)
        return bool(events)

    def _drain(self):
        while True:
            try:
                data = os.read(self.fd, 65536)
            except BlockingIOError:
                return
            except OSError:
                return
            if not data:
                return
            offset = 0
            while offset + 16 <= len(data):        # struct inotify_event: wd, mask, cookie, len, name[len]
                wd, mask, _cookie, size = struct.unpack_from('iIII', data, offset)
                offset += 16 + size
                for path, w in self.watched.items():
                    if w == wd:
                        self.fired.add(path)
                if mask & (IN_DELETE_SELF | IN_MOVE_SELF):
                    for path, w in list(self.watched.items()):
                        if w == wd:
                            del self.watched[path]
                            self.missing.append(path)

    def close(self):
        for fd in self.pids.values():
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self.pids = {}
        if self.fd is not None:
            try:
                os.close(self.fd)
            except OSError:
                pass
            self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def __del__(self):
        try:
            self.close()
        except Exception:  # noqa: BLE001 - interpreter shutdown
            pass


class FileLatch:
    """`.set` becomes True the instant `path` exists, with no thread and no poll (a classroom forks only when it runs one
    thread, so a watcher thread is not an option there). inotify on the file's directory with O_ASYNC: the kernel sends
    SIGIO to this process on any event there and the handler re-checks the file (a wake is a hint, never the
    condition). Reading `.set` costs no syscall. Armed BEFORE the first check, so a file written at any moment is seen.
    Owner process only: a forked child builds its own latch (the inherited descriptor signals the parent). Without
    inotify (not a Linux box) `.set` is a stat per read. close() ends the signals and restores the previous handler."""

    def __init__(self, path):
        import fcntl
        import signal
        self.path, self.owner, self._set = Path(path), os.getpid(), False
        self.waiter, self.previous = Waiter([self.path.parent]), None
        if self.waiter.fd is not None:
            self.previous = signal.signal(signal.SIGIO, self._on_signal)
            fcntl.fcntl(self.waiter.fd, fcntl.F_SETOWN, self.owner)
            fcntl.fcntl(self.waiter.fd, fcntl.F_SETFL, fcntl.fcntl(self.waiter.fd, fcntl.F_GETFL) | os.O_ASYNC)
        self._check()

    def _check(self):
        if self.waiter.fd is None:
            return
        self.waiter._drain()
        for missing in list(self.waiter.missing):      # the directory appeared: watch it (its file may already be there)
            self.waiter.watch_dir(missing)
        if self.path.exists():
            self._set = True

    def _on_signal(self, signum, frame):
        if os.getpid() == self.owner and self.waiter.fd is not None:
            self._check()
        previous = self.previous
        if callable(previous) and previous is not self._on_signal:
            previous(signum, frame)

    @property
    def set(self):
        if self.waiter.fd is None:
            return self._set or self.path.exists()
        return self._set

    def close(self):
        import signal
        if os.getpid() != self.owner:
            return
        had_fd = self.waiter.fd is not None
        self.waiter.close()
        if had_fd:
            signal.signal(signal.SIGIO, self.previous if self.previous is not None else signal.SIG_DFL)


def notify(wake_dir, topic='any', **facts):
    """One wake file in wake_dir (atomic replace = IN_MOVED_TO): every waiter on the box watching it re-checks. Never
    raises: a hand-off never fails for want of a wake."""
    try:
        wake_dir = Path(wake_dir)
        wake_dir.mkdir(parents=True, exist_ok=True)
        name = ''.join(c if c.isalnum() or c in '-_.' else '_' for c in str(topic))[:96] or 'any'
        tmp = wake_dir / ('.%s.%d.%d.tmp' % (name, os.getpid(), time.monotonic_ns()))
        tmp.write_text(json.dumps(dict(topic=topic, pid=os.getpid(), at=time.time(), **facts), sort_keys=True,
                                  default=str) + '\n', encoding='utf-8')
        os.replace(tmp, wake_dir / name)
    except OSError:
        pass


def wait_pids_exit(pids, bound=None):
    """Block until every pid has exited (returns []) or `bound` seconds passed (returns the live pids). bound None = no
    bound. Event-driven: one pidfd per pid; a pid without a pidfd is re-checked on each other pid's exit and at the bound."""
    left = [int(p) for p in pids if alive(p)]
    deadline = None if bound is None else time.monotonic() + float(bound)
    with Waiter(pids=left) as w:
        while True:
            left = [p for p in left if p not in w.exited and alive(p)]
            if not left:
                return []
            if not any(p in w.pids and w.pids[p] >= 0 for p in left):
                # no pidfd for what remains (an old kernel): the only check left is the bound itself
                if deadline is None:
                    raise OSError('no pidfd on this kernel for pids %s and no bound given' % left)
                time.sleep(max(0.0, deadline - time.monotonic()))
                return [p for p in left if p not in w.exited and alive(p)]
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                return left
            w.wait(remaining)


def main(argv):
    if len(argv) >= 2 and argv[1] == 'pids-exit':
        args, bound = argv[2:], None
        if args[:1] == ['--bound']:
            bound, args = float(args[1]), args[2:]
        left = wait_pids_exit([int(a) for a in args if a.strip()], bound)
        if left:
            print(' '.join(str(p) for p in left))
            return 1
        return 0
    if len(argv) == 4 and argv[1] == 'notify':
        notify(argv[2], argv[3])
        return 0
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
