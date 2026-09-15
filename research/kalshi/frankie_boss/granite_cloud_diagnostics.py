"""Validate remote Granite telemetry before retaining it or formatting console output.

This module performs no I/O. Download percentages describe bytes present on disk,
not successful hash verification or service readiness.
"""
from collections import OrderedDict, deque
import copy
import hashlib
import json
import math
import re

MAX_LINE_BYTES = 8192
ROLES = {'bootstrap', 'stage', 'verify', 'controller'}
PHASES = {'bootstrap', 'download_connect', 'download', 'file_verify', 'file_ready',
          'directory_verify', 'runtime_verify', 'backend_start', 'health_wait',
          'ready', 'failed'}
ERROR_TYPES = {None, 'HTTPError', 'TimeoutError', 'ConnectionError', 'OSError',
               'ValueError', 'RuntimeError', 'Exception'}
ERROR_CODES = {'http_error', 'timeout', 'connection_error', 'io_error',
               'validation_error', 'runtime_error', 'unexpected_error'}
COMMON_FIELDS = {
    'schema', 'correlation_id', 'role', 'pid', 'phase', 'elapsed_seconds',
    'phase_elapsed_seconds', 'current_file', 'file_processed_bytes',
    'manifest_total_bytes', 'bytes_present', 'download_percent',
    'download_percent_basis', 'bytes_per_second', 'seconds_since_byte_progress',
    'verified_file_count', 'error_type', 'http_status', 'errno',
}
DIAGNOSTIC_FIELDS = {'severity', 'reason', 'code'}
PREFIXES = {b'GRANITE_PROGRESS ': ('progress', 'GRANITE_PROGRESS_V1'),
            b'GRANITE_DIAGNOSTIC ': ('diagnostic', 'GRANITE_DIAGNOSTIC_V1')}


def _refuse():
    # Never interpolate input or JSON/parser exception messages into errors.
    raise ValueError('invalid Granite telemetry') from None


def _integer(value, maximum, minimum=0):
    return type(value) is int and minimum <= value <= maximum


def _number(value, maximum):
    return type(value) in (int, float) and 0 <= value <= maximum and math.isfinite(value)


def _roster(correlation_id, manifest):
    if type(correlation_id) is not str or not re.fullmatch('[0-9a-f]{32}', correlation_id):
        _refuse()
    if type(manifest) is not dict or type(manifest.get('files')) is not list:
        _refuse()
    files = manifest['files']
    if not 1 <= len(files) <= 128:
        _refuse()
    roster = {}
    for row in files:
        if (type(row) is not dict or type(row.get('path')) is not str
                or not re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', row['path'])
                or '..' in row['path'] or row['path'] in roster
                or not _integer(row.get('size'), 10**12, 1)):
            _refuse()
        roster[row['path']] = row['size']
    return roster


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _refuse()
        result[key] = value
    return result


def parse_line(line, correlation_id, manifest):
    """Return (kind, validated record), None for other logs, or a safe ValueError.

    The caller supplies the expected launch nonce and approved manifest. No string
    from remote input is retained unless it matches an enum or approved filename.
    """
    roster = _roster(correlation_id, manifest)
    if type(line) not in (str, bytes):
        _refuse()
    try:
        raw = line.encode('utf-8') if type(line) is str else line
    except UnicodeError:
        _refuse()
    matching = next(((prefix, value) for prefix, value in PREFIXES.items()
                     if raw.startswith(prefix)), None)
    if matching is None:
        return None
    if len(raw) > MAX_LINE_BYTES:
        _refuse()
    prefix, (kind, schema) = matching
    try:
        value = json.loads(raw[len(prefix):].decode('utf-8'), object_pairs_hook=_pairs,
                           parse_constant=lambda _: _refuse())
        expected = COMMON_FIELDS | (DIAGNOSTIC_FIELDS if kind == 'diagnostic' else set())
        if type(value) is not dict or set(value) != expected:
            _refuse()
        total = sum(roster.values())
        if (value['schema'] != schema or value['correlation_id'] != correlation_id
                or value['role'] not in ROLES or value['phase'] not in PHASES
                or not _integer(value['pid'], 2**31 - 1, 1)
                or value['download_percent_basis'] != 'bytes_on_disk_not_verified'
                or not _integer(value['manifest_total_bytes'], total, total)
                or not _integer(value['bytes_present'], total)
                or not _integer(value['verified_file_count'], len(roster))
                or value['error_type'] not in ERROR_TYPES):
            _refuse()
        for field in ('elapsed_seconds', 'phase_elapsed_seconds', 'seconds_since_byte_progress'):
            if not _number(value[field], 604800):
                _refuse()
        if (not _number(value['bytes_per_second'], 10**30)
                or not _number(value['download_percent'], 100)
                or abs(value['download_percent'] - 100 * value['bytes_present'] / total) > 0.011):
            _refuse()
        name = value['current_file']
        if name is not None and name not in roster:
            _refuse()
        if not _integer(value['file_processed_bytes'], roster[name] if name else 0):
            _refuse()
        if value['http_status'] is not None and not _integer(value['http_status'], 599, 100):
            _refuse()
        if value['errno'] is not None and not _integer(value['errno'], 4095, 1):
            _refuse()
        if kind == 'diagnostic':
            allowed = {'no_progress': ('warning', {'possible_stall'}),
                       'recovered': ('info', {'progress_resumed'}),
                       'error': ('error', ERROR_CODES)}
            severity, codes = allowed[value['reason']]
            if value['severity'] != severity or value['code'] not in codes:
                _refuse()
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError):
        _refuse()
    return kind, value


class Collector:
    """Bounded per-launch telemetry, with monotonic timestamps scoped to each PID."""

    def __init__(self, correlation_id, manifest, *, history_limit=100):
        _roster(correlation_id, manifest)
        if not _integer(history_limit, 100, 1):
            raise ValueError('diagnostic history limit must be 1 through 100')
        self.correlation_id = correlation_id
        self.manifest = copy.deepcopy(manifest)
        self.latest = {}
        self.active = {}
        self.history = deque(maxlen=history_limit)
        self._seen = OrderedDict()
        self._reposts = OrderedDict()

    @staticmethod
    def _remember(cache, key, value):
        cache[key] = value
        cache.move_to_end(key)
        if len(cache) > 128:
            cache.popitem(last=False)

    def ingest(self, line):
        """Return a safe summary for a new record; repeated/stale tail reads return None."""
        parsed = parse_line(line, self.correlation_id, self.manifest)
        if parsed is None:
            return None
        kind, record = parsed
        role, pid, elapsed = record['role'], record['pid'], record['elapsed_seconds']
        key = (role, pid, kind)
        previous_time, signatures = self._seen.get(key, (-1, set()))
        signature = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).digest()
        if elapsed < previous_time:
            return None
        if elapsed == previous_time:
            if signature in signatures or len(signatures) >= 16:
                return None
            signatures = signatures | {signature}
        else:
            signatures = {signature}
        self._remember(self._seen, key, (elapsed, signatures))
        if kind == 'diagnostic':
            repost_key = (role, pid, record['phase'], record['reason'], record['code'])
            if elapsed - self._reposts.get(repost_key, -1000) < 30:
                return None
            self._remember(self._reposts, repost_key, elapsed)
            self.history.append(record)
            if record['reason'] == 'recovered':
                self.active.pop(role, None)
                for prior in list(self._reposts):
                    if prior[:2] == (role, pid) and prior != repost_key:
                        del self._reposts[prior]
            else:
                self.active[role] = record
        previous = self.latest.get(role)
        if previous is None or previous['pid'] != pid or elapsed >= previous['elapsed_seconds']:
            self.latest[role] = record
        detail = (' ' + record['severity'] + ': ' + record['code']) if kind == 'diagnostic' else ''
        filename = ' file=' + record['current_file'] if record['current_file'] else ''
        return (f"Granite {role} {record['phase']}{detail}: "
                f"{record['download_percent']:.2f}% bytes on disk (not verified); "
                f"{record['bytes_per_second']:.0f} B/s; "
                f"no byte progress {record['seconds_since_byte_progress']:.0f}s; "
                f"verified files {record['verified_file_count']}/{len(self.manifest['files'])}"
                f"{filename}")

    def export(self):
        return copy.deepcopy({'schema': 'GRANITE_DIAGNOSTICS_SNAPSHOT_V1',
                              'correlation_id': self.correlation_id,
                              'latest': self.latest,
                              'active_diagnostics': self.active,
                              'diagnostics': list(self.history)})
