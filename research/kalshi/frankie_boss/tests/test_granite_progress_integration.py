"""Real downloader/files/progress with synthetic HTTP responses; no remote I/O."""
import hashlib
import io
import json

import pytest

from research.kalshi.frankie_boss import granite_run_artifacts as artifacts
from research.kalshi.frankie_boss.granite_cloud_diagnostics import Collector
from research.kalshi.frankie_boss.granite_runpod_progress import Progress


OWNER = 'd' * 32
CONTENT = b'abcdefghijkl'
ROW = {'path': 'config.json', 'size': len(CONTENT),
       'sha256': hashlib.sha256(CONTENT).hexdigest()}
MANIFEST = {'files': [ROW]}
ETAG = '"immutable-v1"'


class Response(io.BytesIO):
    def __init__(self, body, *, status=200, headers=None, interrupt_after=None):
        super().__init__(body)
        self.status = status
        self.headers = {'ETag': ETAG, **(headers or {})}
        self.interrupt_after = interrupt_after

    def read(self, size=-1):
        if self.interrupt_after is not None:
            if self.tell() >= self.interrupt_after:
                raise ConnectionError('synthetic transport interruption')
            size = min(size, self.interrupt_after - self.tell())
        return super().read(size)


def observer(tmp_path):
    emitted, callbacks = [], []
    progress = Progress(MANIFEST, tmp_path, 'stage', OWNER,
                        emit=emitted.append, clock=lambda: 100.0)

    def callback(phase, row=None, processed=0):
        callbacks.append((phase, None if row is None else row['path'], processed))
        progress(phase, row, processed)

    return progress, callback, callbacks, emitted


def test_interrupted_download_persists_partial_then_resumes_range_and_etag(tmp_path):
    calls = []
    progress, callback, callbacks, emitted = observer(tmp_path)

    def opener(request, timeout):
        calls.append(dict(request.header_items()))
        assert request.full_url == artifacts.download_url(ROW)
        assert timeout == 60
        if len(calls) == 1:
            assert request.get_header('Range') is None
            return Response(CONTENT, interrupt_after=4)
        assert request.get_header('Range') == 'bytes=4-'
        assert request.get_header('If-range') == ETAG
        return Response(CONTENT[4:], status=206,
                        headers={'Content-Range': 'bytes 4-11/12'})

    with pytest.raises(ConnectionError):
        artifacts.download_file(ROW, tmp_path, opener=opener, progress=callback)
    partial = tmp_path / 'config.json.partial'
    metadata = tmp_path / 'config.json.partial.json'
    assert partial.read_bytes() == CONTENT[:4]
    assert json.loads(metadata.read_bytes()) == {
        'url': artifacts.download_url(ROW), 'etag': ETAG,
        'size': len(CONTENT), 'sha256': ROW['sha256']}
    assert not (tmp_path / 'config.json').exists()
    assert not any(phase == 'file_ready' for phase, _, _ in callbacks)

    path = artifacts.download_file(ROW, tmp_path, opener=opener, progress=callback)
    assert path.read_bytes() == CONTENT
    assert not partial.exists() and not metadata.exists()
    assert len(calls) == 2
    verify = [event for event in callbacks if event[0] == 'file_verify']
    assert verify == [('file_verify', 'config.json', 0),
                      ('file_verify', 'config.json', len(CONTENT))]
    assert callbacks[-1] == ('file_ready', 'config.json', len(CONTENT))
    assert progress.snapshot()['verified_file_count'] == 1

    # Reusing a completed file still verifies its hash and never calls HTTP.
    callbacks.clear()
    artifacts.download_file(ROW, tmp_path,
        opener=lambda *a, **kw: pytest.fail('completed file must not be downloaded again'),
        progress=callback)
    assert [event[0] for event in callbacks] == ['file_verify', 'file_verify', 'file_ready']
    collector = Collector(OWNER, MANIFEST)
    for entry in emitted:
        collector.ingest(entry)
    assert collector.export()['latest']['stage']['verified_file_count'] == 1


def test_full_partial_is_rehashed_and_promoted_without_http(tmp_path):
    progress, callback, callbacks, _ = observer(tmp_path)
    with pytest.raises(ConnectionError):
        artifacts.download_file(ROW, tmp_path,
            opener=lambda *a, **kw: Response(CONTENT, interrupt_after=len(CONTENT)),
            progress=callback)
    assert (tmp_path / 'config.json.partial').read_bytes() == CONTENT
    assert progress.snapshot()['verified_file_count'] == 0
    callbacks.clear()
    path = artifacts.download_file(ROW, tmp_path,
        opener=lambda *a, **kw: pytest.fail('complete partial needs only local verification'),
        progress=callback)
    assert path.read_bytes() == CONTENT
    assert [event[0] for event in callbacks] == ['file_verify', 'file_verify', 'file_ready']
    assert progress.snapshot()['verified_file_count'] == 1


def test_checksum_failure_never_reports_ready_even_with_all_bytes_on_disk(tmp_path):
    progress, callback, callbacks, emitted = observer(tmp_path)
    with pytest.raises(ValueError, match='size/hash mismatch') as error:
        artifacts.download_file(ROW, tmp_path,
            opener=lambda *a, **kw: Response(b'X' * len(CONTENT)), progress=callback)
    progress.failure(error.value)
    assert (tmp_path / 'config.json.partial').read_bytes() == b'X' * len(CONTENT)
    assert not (tmp_path / 'config.json').exists()
    assert any(phase == 'file_verify' for phase, _, _ in callbacks)
    assert not any(phase == 'file_ready' for phase, _, _ in callbacks)
    snapshot = progress.snapshot()
    assert snapshot['download_percent'] == 100
    assert snapshot['verified_file_count'] == 0
    collector = Collector(OWNER, MANIFEST)
    for entry in emitted:
        collector.ingest(entry)
    failure = collector.export()['active_diagnostics']['stage']
    assert failure['code'] == 'validation_error'
    assert failure['phase'] == 'failed'
    assert failure['download_percent_basis'] == 'bytes_on_disk_not_verified'
