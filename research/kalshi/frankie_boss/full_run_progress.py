"""Observe the full Frankie run without calculating or filtering market evidence.

These diagnostics are operational observations, not proof of principal authorship.
The existing source, causal-stream and principal-output receipts remain authoritative.
"""
import json
import math
import os
from pathlib import Path
import re
import threading
import time

try:
    from .runtime_resource_probe import memory_snapshot
except ImportError:
    from runtime_resource_probe import memory_snapshot

PHASES = {
    'data_delivery': 'transport', 'input_inventory': 'transport',
    'causal_delivery': 'transport', 'frankie_calculation': 'frankie',
    'boss_reasoning': 'boss', 'boss_training': 'boss', 'granite_request': 'granite',
    'checkpoint_save': 'transport',
    'output_persistence': 'transport', 'readback': 'transport', 'complete': 'coordinator',
}
UNITS = {'bytes', 'records', 'groups', 'planes', 'sections', 'requests', 'outputs', 'steps'}
TRAINING_STAGES = {
    'prepare_start', 'prepare_complete', 'causal_scan_complete', 'forward_start',
    'forward_complete', 'loss_complete', 'backward_start', 'backward_complete',
    'optimizer_start', 'optimizer_complete', 'step_complete', 'step_failed',
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class RunProbe:
    """Per-process heartbeat plus durable latest observation and append-only events.

    Resume reopens the same run's diagnostics; it does not mark work complete or
    decide which model calls can be repeated. Existing operation journals do that.
    """
    def __init__(self, directory, run_id, *, sections=(), interval=5,
                 stall_seconds=30, clock=time.monotonic, emit=print, resume=False):
        if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', run_id):
            raise ValueError('explicit safe run identity required')
        if any(type(n) not in (int, float) or not math.isfinite(n) or n <= 0
               for n in (interval, stall_seconds)):
            raise ValueError('positive finite diagnostic timing required')
        if (type(sections) is not tuple or len(set(sections)) != len(sections)
                or any(type(s) is not str or not re.fullmatch(r'4\.[0-9]{1,3}[a-z]?', s) for s in sections)):
            raise ValueError('exact calculation section identities required')
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.run_id, self.sections = run_id, sections
        self.interval, self.stall_seconds, self.clock, self.emit = interval, stall_seconds, clock, emit
        self._lock, self._stop = threading.RLock(), threading.Event()
        self._thread = None
        self._heartbeat_error = None
        self._heartbeat_exception = None
        self._started = self._phase_at = self._advance_at = self._sample_at = self.clock()
        self._warned_at, self._stalled = None, False
        self._state = dict(phase='data_delivery', owner='transport', completed=0,
                           total=None, unit='bytes', cursor=None, section=None)
        self._previous_count = 0
        checkpoint = self.directory/'progress.json'
        if resume:
            old = json.loads(checkpoint.read_text(encoding='utf-8'))
            if old.get('schema') != 'FRANKIE_RUN_PROGRESS_V1' or old.get('run_id') != run_id:
                raise ValueError('diagnostic checkpoint belongs to another run')
        elif checkpoint.exists() or (self.directory/'progress.jsonl').exists():
            raise FileExistsError('diagnostic run already exists; explicit resume required')

    def _write(self, kind, code=None, error_type=None):
        now = self.clock()
        state = self._state
        elapsed = max(0, now-self._sample_at)
        rate = max(0, state['completed']-self._previous_count)/elapsed if elapsed else 0
        value = dict(schema='FRANKIE_RUN_PROGRESS_V1', run_id=self.run_id,
            pid=os.getpid(), kind=kind, code=code, error_type=error_type,
            elapsed_seconds=max(0, now-self._started),
            phase_elapsed_seconds=max(0, now-self._phase_at),
            seconds_without_progress=max(0, now-self._advance_at),
            units_per_second=rate, **state)
        value['percent'] = (100*state['completed']/state['total']) if state['total'] else None
        data = canonical(value)
        with (self.directory/'progress.jsonl').open('ab') as stream:
            stream.write(data+b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        temporary = self.directory/('progress-'+str(os.getpid())+'.tmp')
        with temporary.open('wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.replace(temporary, self.directory/'progress.json')
        except OSError as error:
            # The append-only event above is already fsynced. A Windows reader
            # can deny replacement of the advisory latest snapshot temporarily.
            if getattr(error, 'winerror', None) not in (5, 32, 33):
                raise
            warning = dict(value, kind='warning', code='latest_snapshot_unavailable',
                           diagnostic_error=self._safe_error(error, 'latest_snapshot'))
            with (self.directory/'progress.jsonl').open('ab') as stream:
                stream.write(canonical(warning)+b'\n')
                stream.flush()
                os.fsync(stream.fileno())
        self._previous_count, self._sample_at = state['completed'], now
        line = 'FRANKIE_PROGRESS '+data.decode()
        if self.emit is print:
            print(line, flush=True)
        else:
            self.emit(line)
        return value

    def advance(self, phase, *, completed=0, total=None, unit='groups', cursor=None, section=None):
        self.check_health()
        if phase not in PHASES or unit not in UNITS:
            raise ValueError('unknown run progress phase or unit')
        if (type(completed) is not int or completed < 0
                or (total is not None and (type(total) is not int or total < completed))
                or (cursor is not None and (type(cursor) is not int or cursor < 0))
                or (section is not None and section not in self.sections)):
            raise ValueError('invalid progress counts, cursor or section')
        with self._lock:
            old = self._state
            changed = (phase, unit, section) != (old['phase'], old['unit'], old['section'])
            if not changed and (completed < old['completed'] or
                    (old['cursor'] is not None and (cursor is None or cursor < old['cursor']))):
                raise ValueError('progress regressed within a phase')
            moved = changed or completed > old['completed'] or cursor != old['cursor']
            if moved:
                self._advance_at = self.clock()
            if changed:
                self._phase_at = self.clock()
                self._previous_count = completed
            self._state = dict(phase=phase, owner=PHASES[phase], completed=completed,
                               total=total, unit=unit, cursor=cursor, section=section)
            if moved and self._stalled:
                self._stalled, self._warned_at = False, None
                self._write('recovery', 'progress_resumed')
            return self._write('progress')

    def sample(self):
        with self._lock:
            now = self.clock()
            if (self._state['phase'] != 'complete' and now-self._advance_at >= self.stall_seconds
                    and (self._warned_at is None or now-self._warned_at >= self.stall_seconds)):
                self._stalled, self._warned_at = True, now
                return self._write('warning', 'possible_stall')
            return self._write('progress')

    def failure(self, error):
        choices = ((TimeoutError, 'TimeoutError'), (ConnectionError, 'ConnectionError'),
                   (OSError, 'OSError'), (ValueError, 'ValueError'), (RuntimeError, 'RuntimeError'))
        safe_type = next((name for kind, name in choices if isinstance(error, kind)), 'Exception')
        with self._lock:
            return self._write('error', 'operation_failed', safe_type)

    def training_event(self, value):
        """Persist safe native-step substage/resource telemetry, never exception text."""
        if type(value) is not dict or value.get('stage') not in TRAINING_STAGES:
            raise ValueError('known native training diagnostic stage required')
        request_id = value.get('request_id')
        if type(request_id) is not str or not 1 <= len(request_id) <= 256:
            raise ValueError('bounded training request identity required')
        elapsed = value.get('elapsed_seconds')
        if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError('finite nonnegative training elapsed time required')
        safe = dict(schema='FRANKIE_NATIVE_TRAINING_DIAGNOSTIC_V1', run_id=self.run_id,
            pid=os.getpid(), request_id=request_id, stage=value['stage'], elapsed_seconds=elapsed)
        for name in ('context_rows', 'losses', 'masked_labels'):
            item = value.get(name)
            if item is not None:
                if type(item) is not int or item < 0:
                    raise ValueError('nonnegative bounded training diagnostic count required')
                safe[name] = item
        error_type = value.get('error_type')
        if error_type is not None:
            if type(error_type) is not str or not re.fullmatch(r'[A-Za-z0-9_.]{1,128}', error_type):
                raise ValueError('safe training error type required')
            safe['error_type'] = error_type
        safe.update(memory_snapshot())
        data = canonical(safe)
        try:
            with (self.directory/'native-training.jsonl').open('ab') as stream:
                stream.write(data+b'\n');stream.flush();os.fsync(stream.fileno())
            line = 'FRANKIE_TRAINING_PROGRESS '+data.decode()
            if self.emit is print: print(line, flush=True)
            else: self.emit(line)
        except OSError:
            pass  # Advisory diagnostics can never change training authority or outcome.
        return safe

    def _heartbeat(self):
        while not self._stop.wait(self.interval):
            try:
                self.sample()
            except Exception as error:
                self._heartbeat_exception = error
                self._heartbeat_error = self._safe_error(error, 'heartbeat')
                try:
                    with (self.directory/'diagnostic-failure.json').open('wb') as stream:
                        stream.write(canonical(dict(run_id=self.run_id, error=self._heartbeat_error)))
                        stream.flush()
                        os.fsync(stream.fileno())
                except OSError:
                    pass  # The retained exception still reaches the owner.
                self._stop.set()

    @staticmethod
    def _safe_error(error, phase):
        return dict(error_type=type(error).__name__, errno=getattr(error, 'errno', None),
                    winerror=getattr(error, 'winerror', None), phase=phase)

    def check_health(self):
        if self._heartbeat_error:
            raise RuntimeError('run diagnostic persistence failed') from self._heartbeat_exception

    def controller_event(self, value):
        """Observe controller boundaries; durable journals still decide reuse."""
        phase = value['phase']
        cursor = value.get('through_cursor')
        if phase == 'request_failed':
            return self.failure(RuntimeError())
        mapping = {
            'source_validation': ('causal_delivery', 0, None, 'groups'),
            'native_reasoning': ('boss_reasoning', 0, None, 'outputs'),
            'native_complete': ('boss_reasoning', value.get('count', 0), value.get('count'), 'outputs'),
            'critic_request': ('granite_request', 0, 1, 'requests'),
            'critic_complete': ('granite_request', 1, 1, 'requests'),
            'output_persisted': ('output_persistence', value.get('count', 0), value.get('count'), 'outputs'),
            'completed_result_reused': ('output_persistence', 0, None, 'outputs'),
        }
        target, completed, total, unit = mapping[phase]
        return self.advance(target, completed=completed, total=total, unit=unit, cursor=cursor)

    def __enter__(self):
        if self._thread is not None:
            raise RuntimeError('diagnostic context already started')
        self.sample()
        self._thread = threading.Thread(target=self._heartbeat, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, kind, error, traceback):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1)
        if error is not None:
            self.failure(error)
        else:
            self.check_health()
            self.sample()
        return False
