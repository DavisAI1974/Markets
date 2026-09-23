"""Small, local work probes. Counts are stage-local, never an ETA or a resume cursor."""
import json
import os
from pathlib import Path
import threading
import time


def process_token(pid):
    """Linux boot + process start ticks: a reused PID is not the original worker."""
    try:
        stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        if stat[0] in ('Z', 'X'):
            return None
        return Path('/proc/sys/kernel/random/boot_id').read_text().strip() + ':' + stat[19]
    except (OSError, IndexError):
        return None


class Probe:
    def __init__(self, directory, request_sha256=None, phase=None):
        self.directory = Path(directory)
        self.request_sha256, self.phase = request_sha256, phase
        self.pid = os.getpid()
        self.token = process_token(self.pid)
        self.lock = threading.RLock()
        self.last = 0.0
        self.checkpoints = {}

    def update(self, stage, completed=0, total=None, *, in_flight=0, failed=0,
               state='running', force=True):
        with self.lock:
            now = time.monotonic()
            if not force and now - self.last < 15:
                return
            if (type(completed) is not int or completed < 0
                    or total is not None and (type(total) is not int or total < completed)):
                raise ValueError('measured nonnegative counts required')
            value = dict(schema='FRANKIE_WORK_PROBE_V1', request_sha256=self.request_sha256,
                         phase=self.phase, stage=stage, completed=completed, total=total,
                         percent=round(100 * completed / total, 2) if total else None,
                         in_flight=in_flight, failed=failed, state=state, at=time.time(),
                         pid=self.pid, process_token=self.token)
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / 'progress.json'
            temporary = path.with_suffix('.pending')
            temporary.write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')
            os.replace(temporary, path)
            self.last = now

    def checkpoint(self, event, name):
        """Observe existing cache validation, never expose prompts or answer payloads."""
        with self.lock:
            self.checkpoints[event] = self.checkpoints.get(event, 0) + 1
            value = dict(request_sha256=self.request_sha256, pid=self.pid, process_token=self.token,
                         counts=dict(self.checkpoints), last_event=event, name=Path(name).name, at=time.time())
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / 'checkpoints.json'
            temporary = path.with_suffix('.pending')
            temporary.write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')
            os.replace(temporary, path)

    def track(self, records, total, stage):
        """Yield every input unchanged; count only after its consumer returns."""
        done = 0
        self.update(stage, total=total)
        for record in records:
            yield record
            done += 1
            self.update(stage, done, total, force=False)
        self.update(stage, done, total, state='complete' if done == total else 'count_mismatch')


def for_session(session):
    probe = getattr(session, '_work_probe', None)
    if probe is None:
        directory = getattr(session, 'dir', session.work)
        probe = Probe(directory)
        session._work_probe = probe
    probe.request_sha256 = getattr(session, 'request_sha256', None)
    probe.phase = getattr(session, '_probe_phase', None)
    return probe


def snapshot(directory, request_sha256=None, phase=None):
    """Read-only; distinguish worker liveness from a heartbeat process being alive."""
    try:
        value = json.loads((Path(directory) / 'progress.json').read_text(encoding='utf-8'))
        if (value.get('schema') != 'FRANKIE_WORK_PROBE_V1'
                or request_sha256 is not None and value.get('request_sha256') != request_sha256
                or phase is not None and value.get('phase') != phase):
            return dict(status='identity_or_phase_mismatch')
        pid = value.get('pid')
        if type(pid) is not int or pid <= 0:
            return dict(status='invalid')
        current = process_token(pid)
        value['process_alive'] = current == value['process_token'] if value.get('process_token') else None
        value['progress_age_seconds'] = max(0, round(time.time() - value['at'], 1))
        try:
            saved = json.loads((Path(directory) / 'checkpoints.json').read_text(encoding='utf-8'))
            if all(saved.get(k) == value.get(k) for k in ('request_sha256', 'pid', 'process_token')):
                value['checkpoints'] = saved
        except (OSError, ValueError, TypeError):
            pass
        return value
    except (OSError, ValueError, TypeError, KeyError):
        return dict(status='unavailable')
