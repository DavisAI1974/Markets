"""Secret-free observations of local staging progress; never a readiness verifier."""
import json
import math
import os
from pathlib import Path
import re
import stat
import threading
import time


PHASES = frozenset(('bootstrap', 'download_connect', 'download', 'file_verify',
                    'file_ready', 'directory_verify', 'runtime_verify',
                    'backend_start', 'health_wait', 'ready', 'failed'))
STALL_PHASES = PHASES - {'bootstrap', 'file_ready', 'ready', 'failed'}
ROLES = frozenset(('bootstrap', 'stage', 'verify', 'controller'))


class Progress:
    """Use as callback and context manager; snapshot() needs no heartbeat thread.

    Disk counts include an expected basename or its .partial sibling, clamped to
    expected size. They do not establish hash validity. Only caller file_ready
    events increase verified_file_count. Diagnostics observe possible stalls;
    they never restart work, extend deadlines, or infer model readiness.
    """

    def __init__(self, manifest, directory, role, correlation_id, emit=print,
                 clock=time.monotonic, interval=5, stall_seconds=30):
        if role not in ROLES or not isinstance(correlation_id, str) or (
                correlation_id != 'local' and not re.fullmatch('[0-9a-f]{32}', correlation_id)):
            raise ValueError('invalid progress identity')
        rows = manifest.get('files') if type(manifest) is dict else None
        if type(rows) is not list or not 1 <= len(rows) <= 128:
            raise ValueError('bounded progress manifest required')
        self._sizes = {}
        for row in rows:
            if type(row) is not dict:
                raise ValueError('invalid progress manifest row')
            name, size = row.get('path'), row.get('size')
            if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,127}', name)
                    or '..' in name or name in self._sizes
                    or type(size) is not int or not 0 < size <= 10**12):
                raise ValueError('invalid progress manifest row')
            self._sizes[name] = size
        for value in (interval, stall_seconds):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError('positive finite progress interval required')
        if not callable(emit) or not callable(clock):
            raise ValueError('progress emitter and clock required')
        self.directory = Path(directory)
        self.role, self.correlation_id = role, correlation_id
        self.emit, self.clock = emit, clock
        self.interval, self.stall_seconds = float(interval), float(stall_seconds)
        self._lock, self._stop = threading.RLock(), threading.Event()
        self._thread = None
        self._started = self._now()
        self._phase_at = self._sample_at = self._last_byte_at = self._last_advance_at = self._started
        self._phase, self._file, self._processed = 'bootstrap', None, 0
        self._verified = set()
        self._previous = self._disk_sizes()
        self._stalled = False
        self._last_warning = None
        self._error = {'error_type': None, 'http_status': None, 'errno': None}

    def _now(self):
        now = self.clock()
        if type(now) not in (int, float) or not math.isfinite(now):
            raise ValueError('finite progress clock required')
        return float(now)

    def _disk_sizes(self):
        values = dict.fromkeys(self._sizes, 0)
        try:
            if any(parent.is_symlink() for parent in (self.directory, *self.directory.parents)):
                return values
        except OSError:
            return values
        for name, expected in self._sizes.items():
            observed = 0
            for suffix in ('', '.partial'):
                try:
                    info = (self.directory / (name + suffix)).lstat()
                    if stat.S_ISREG(info.st_mode):
                        observed = max(observed, min(expected, max(0, info.st_size)))
                except OSError:
                    pass
            values[name] = observed
        return values

    def _write(self, prefix, record):
        line = prefix + ' ' + json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if self.emit is print:
            print(line, flush=True)
        else:
            self.emit(line)

    def _diagnostic(self, record, severity, reason, code):
        self._write('GRANITE_DIAGNOSTIC', dict(record, schema='GRANITE_DIAGNOSTIC_V1',
                    severity=severity, reason=reason, code=code))

    def _record(self, now, advanced=False):
        sizes = self._disk_sizes()
        growth = sum(max(0, size - self._previous[name]) for name, size in sizes.items())
        duration = max(0, now - self._sample_at)
        if growth:
            self._last_byte_at = now
            advanced = True
        if advanced:
            self._last_advance_at = now
        total = sum(self._sizes.values())
        present = sum(sizes.values())
        record = dict(schema='GRANITE_PROGRESS_V1', correlation_id=self.correlation_id,
            role=self.role, pid=os.getpid(), phase=self._phase,
            elapsed_seconds=max(0, now - self._started),
            phase_elapsed_seconds=max(0, now - self._phase_at),
            current_file=self._file, file_processed_bytes=self._processed,
            manifest_total_bytes=total, bytes_present=present,
            download_percent=round(100 * present / total, 6),
            download_percent_basis='bytes_on_disk_not_verified',
            bytes_per_second=round(growth / duration, 6) if duration > 0 else 0.0,
            seconds_since_byte_progress=max(0, now - self._last_byte_at),
            verified_file_count=len(self._verified), **self._error)
        self._previous, self._sample_at = sizes, now
        if advanced and self._stalled and self._phase != 'failed':
            self._stalled = False
            self._last_warning = None
            self._diagnostic(record, 'info', 'recovered', 'progress_resumed')
        if (self._phase in STALL_PHASES and now - self._last_advance_at >= self.stall_seconds
                and (self._last_warning is None or now - self._last_warning >= self.stall_seconds)):
            self._stalled, self._last_warning = True, now
            self._diagnostic(record, 'warning', 'no_progress', 'possible_stall')
        return record

    def snapshot(self):
        """Emit and return one current observation without starting a thread."""
        with self._lock:
            record = self._record(self._now())
            self._write('GRANITE_PROGRESS', record)
            return record

    def __call__(self, phase, row=None, processed=0):
        if phase not in PHASES:
            raise ValueError('invalid progress phase')
        name = row.get('path') if type(row) is dict else row
        if name is not None and (not isinstance(name, str) or name not in self._sizes):
            raise ValueError('unapproved progress file')
        if type(processed) is not int or processed < 0:
            raise ValueError('nonnegative processed bytes required')
        processed = min(processed, self._sizes[name]) if name is not None else 0
        with self._lock:
            now = self._now()
            changed = (phase, name) != (self._phase, self._file)
            advanced = changed or processed > self._processed
            if changed:
                self._phase_at = now
            self._phase, self._file, self._processed = phase, name, processed
            if phase == 'file_ready' and name is not None:
                advanced = advanced or name not in self._verified
                self._verified.add(name)
            # Byte callbacks can be frequent: do not stat or emit per chunk.
            if advanced:
                self._last_advance_at = now
            if changed or self._stalled:
                record = self._record(now, advanced)
                self._write('GRANITE_PROGRESS', record)

    def failure(self, error):
        """Fixed diagnostic fields only; never use exception text or arbitrary codes."""
        # Import inside this method keeps the heartbeat's startup dependency small.
        from urllib.error import HTTPError
        choices = ((HTTPError, 'HTTPError', 'http_error'),
                   (TimeoutError, 'TimeoutError', 'timeout'),
                   (ConnectionError, 'ConnectionError', 'connection_error'),
                   (OSError, 'OSError', 'io_error'), (ValueError, 'ValueError', 'validation_error'),
                   (RuntimeError, 'RuntimeError', 'runtime_error'))
        kind, code = 'Exception', 'unexpected_error'
        for expected, safe_name, safe_code in choices:
            if isinstance(error, expected):
                kind, code = safe_name, safe_code
                break
        status = error.code if isinstance(error, HTTPError) else None
        status = status if type(status) is int and 100 <= status <= 599 else None
        number = error.errno if isinstance(error, OSError) else None
        number = number if type(number) is int and 1 <= number <= 4095 else None
        with self._lock:
            now = self._now()
            self._phase, self._phase_at = 'failed', now
            self._error = {'error_type': kind, 'http_status': status, 'errno': number}
            record = self._record(now)
            self._diagnostic(record, 'error', 'error', code)
            self._write('GRANITE_PROGRESS', record)

    fail = failure

    def _heartbeat(self):
        while not self._stop.wait(self.interval):
            self.snapshot()

    def __enter__(self):
        if self._thread is not None:
            raise RuntimeError('progress context cannot be reused')
        self.snapshot()
        self._thread = threading.Thread(target=self._heartbeat, name='granite-progress', daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, error, traceback):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        if error is not None:
            self.failure(error)
        else:
            self.snapshot()
        return False
