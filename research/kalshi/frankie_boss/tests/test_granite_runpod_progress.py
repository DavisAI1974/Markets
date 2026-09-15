"""Progress observes disk bytes without claiming hash or model readiness."""
import json
import threading

import pytest

from research.kalshi.frankie_boss.granite_runpod_progress import Progress


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


def make_progress(tmp_path, **kwargs):
    manifest = {'files': [{'path': 'model.safetensors', 'size': 100},
                          {'path': 'config.json', 'size': 20}]}
    clock, lines = Clock(), []
    progress = Progress(manifest, tmp_path, 'stage', 'a' * 32,
                        emit=lines.append, clock=clock, **kwargs)
    return progress, clock, lines, manifest['files']


def diagnostics(lines):
    return [json.loads(line.split(' ', 1)[1]) for line in lines
            if line.startswith('GRANITE_DIAGNOSTIC ')]


def test_resumed_partial_clamp_metadata_and_rename(tmp_path):
    (tmp_path / 'model.safetensors.partial').write_bytes(b'x' * 40)
    (tmp_path / 'model.safetensors.partial.json').write_text('private-url-secret')
    (tmp_path / 'other').write_bytes(b'x' * 500)
    progress, clock, lines, rows = make_progress(tmp_path)
    first = progress.snapshot()
    assert first['bytes_present'] == 40
    assert first['bytes_per_second'] == 0
    assert first['verified_file_count'] == 0
    clock.now += 5
    (tmp_path / 'model.safetensors.partial').write_bytes(b'x' * 150)
    second = progress.snapshot()
    assert second['bytes_present'] == 100
    assert second['bytes_per_second'] == 12
    (tmp_path / 'model.safetensors').write_bytes(b'x' * 100)
    clock.now += 5
    assert progress.snapshot()['bytes_per_second'] == 0
    assert progress.snapshot()['bytes_present'] == 100
    assert 'private-url-secret' not in '\n'.join(lines)


def test_full_disk_bytes_do_not_claim_ready_or_verified(tmp_path):
    progress, clock, lines, rows = make_progress(tmp_path)
    for row in rows:
        (tmp_path / row['path']).write_bytes(b'x' * row['size'])
    progress('file_verify', rows[0], 25)
    record = progress.snapshot()
    assert record['phase'] == 'file_verify'
    assert record['download_percent'] == 100
    assert record['download_percent_basis'] == 'bytes_on_disk_not_verified'
    assert record['verified_file_count'] == 0
    assert record['file_processed_bytes'] == 25
    progress('file_ready', rows[0], 100)
    progress('file_ready', rows[0], 100)
    assert progress.snapshot()['verified_file_count'] == 1


def test_stall_reposts_and_recovers_on_hash_progress(tmp_path):
    progress, clock, lines, rows = make_progress(tmp_path)
    progress('file_verify', rows[0])
    clock.now += 30
    progress.snapshot()
    assert diagnostics(lines)[-1]['reason'] == 'no_progress'
    assert diagnostics(lines)[-1]['code'] == 'possible_stall'
    clock.now += 29
    progress.snapshot()
    assert len(diagnostics(lines)) == 1
    clock.now += 1
    progress.snapshot()
    assert len(diagnostics(lines)) == 2
    progress('file_verify', rows[0], 10)
    assert diagnostics(lines)[-1]['reason'] == 'recovered'
    assert len(diagnostics(lines)) == 3
    clock.now += 29
    progress.snapshot()
    assert len(diagnostics(lines)) == 3


def test_disk_growth_and_phase_changes_recover(tmp_path):
    progress, clock, lines, rows = make_progress(tmp_path)
    progress('download_connect', rows[0])
    clock.now += 31
    progress.snapshot()
    (tmp_path / 'model.safetensors.partial').write_bytes(b'x')
    clock.now += 5
    record = progress.snapshot()
    assert diagnostics(lines)[-1]['reason'] == 'recovered'
    assert record['seconds_since_byte_progress'] == 0
    clock.now += 31
    progress.snapshot()
    progress('runtime_verify')
    assert diagnostics(lines)[-1]['reason'] == 'recovered'
    assert progress.snapshot()['phase_elapsed_seconds'] == 0


def test_failure_is_safe_and_not_relabelled_as_ready(tmp_path):
    progress, clock, lines, rows = make_progress(tmp_path)
    from urllib.error import HTTPError
    error = HTTPError('https://private/?token=SECRET', 403, 'SECRET', {}, None)
    progress.failure(error)
    diagnostic = diagnostics(lines)[-1]
    assert diagnostic['severity'] == 'error'
    assert diagnostic['reason'] == 'error'
    assert diagnostic['error_type'] == 'HTTPError'
    assert diagnostic['http_status'] == 403
    assert diagnostic['code'] == 'http_error'
    assert 'SECRET' not in '\n'.join(lines)
    assert progress.snapshot()['phase'] == 'failed'


def test_untrusted_exception_name_is_not_logged(tmp_path):
    progress, clock, lines, rows = make_progress(tmp_path)
    custom = type('SECRETVALUE', (Exception,), {})
    progress.failure(custom('SECRET'))
    assert diagnostics(lines)[-1]['error_type'] == 'Exception'
    assert 'SECRET' not in '\n'.join(lines)


def test_symlinks_do_not_count(tmp_path):
    target = tmp_path / 'outside'
    target.write_bytes(b'x' * 200)
    try:
        (tmp_path / 'model.safetensors').symlink_to(target)
    except OSError:
        pytest.skip('symlink creation unavailable')
    progress, clock, lines, rows = make_progress(tmp_path)
    assert progress.snapshot()['bytes_present'] == 0
    nested = tmp_path / 'linked'
    nested.symlink_to(tmp_path, target_is_directory=True)
    assert Progress({'files': rows}, nested, 'verify', 'local', emit=lambda _: None).snapshot()['bytes_present'] == 0


@pytest.mark.parametrize('bad', ['../secret', 'https://host/token', 'a\\b', 'a?token=x'])
def test_manifest_names_refuse_unapproved_paths(tmp_path, bad):
    with pytest.raises(ValueError):
        Progress({'files': [{'path': bad, 'size': 1}]}, tmp_path, 'stage', 'local')


def test_heartbeat_runs_without_download_callback_and_stops(tmp_path):
    emitted = threading.Event()
    lines = []
    def emit(line):
        lines.append(line)
        if len(lines) >= 2:
            emitted.set()
    progress = Progress({'files': [{'path': 'model.bin', 'size': 1}]}, tmp_path,
                        'bootstrap', 'local', emit=emit, interval=0.01)
    with progress:
        assert emitted.wait(1)
        thread = progress._thread
        assert thread.is_alive()
    assert not thread.is_alive()


def test_invalid_callback_and_clock_refused(tmp_path):
    progress, clock, lines, rows = make_progress(tmp_path)
    with pytest.raises(ValueError):
        progress('https://SECRET')
    with pytest.raises(ValueError):
        progress('download', {'path': 'unknown', 'size': 100})
    clock.now = float('nan')
    with pytest.raises(ValueError):
        progress.snapshot()


def test_progress_line_is_strict_canonical_json(tmp_path):
    progress, clock, lines, rows = make_progress(tmp_path)
    record = progress.snapshot()
    assert lines[-1] == 'GRANITE_PROGRESS ' + json.dumps(record, sort_keys=True, separators=(',', ':'), allow_nan=False)


def test_repeated_same_phase_and_zero_progress_do_not_hide_stall(tmp_path):
    progress, clock, lines, rows = make_progress(tmp_path)
    progress('health_wait')
    clock.now += 20
    progress('health_wait')
    clock.now += 10
    record = progress.snapshot()
    assert record['phase_elapsed_seconds'] == 30
    assert record['bytes_per_second'] == 0
    assert diagnostics(lines)[-1]['code'] == 'possible_stall'


def test_exception_context_reports_error_and_preserves_exception(tmp_path):
    progress, clock, lines, rows = make_progress(tmp_path)
    with pytest.raises(TimeoutError):
        with progress:
            raise TimeoutError('secret URL must stay private')
    assert not progress._thread.is_alive()
    assert diagnostics(lines)[-1]['code'] == 'timeout'
    assert 'secret URL' not in '\n'.join(lines)


def test_symlink_ancestors_are_excluded_even_without_platform_symlink_rights(tmp_path, monkeypatch):
    from pathlib import Path
    (tmp_path / 'model.safetensors').write_bytes(b'x' * 100)
    original = Path.is_symlink
    monkeypatch.setattr(Path, 'is_symlink', lambda path: path == tmp_path.parent or original(path))
    progress, clock, lines, rows = make_progress(tmp_path)
    assert progress.snapshot()['bytes_present'] == 0

