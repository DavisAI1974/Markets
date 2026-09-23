"""Isolated contract tests: no package conftest, cloud, keys, or production files."""
import hashlib
import importlib.util
import json
from pathlib import Path
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'research/kalshi/frankie_boss'
KEY = bytes(range(32))
PARAMETER = '/markets/frankie/request-transport/isolated_fixture'
BODY = b'{ "request_id": "fixture-only", "ts_event": 1633309200123456789, "marker": "PRIVATE_FIXTURE_TEXT_17493" }\n'
SHA = hashlib.sha256(BODY).hexdigest()
FILES = {'intent.json', 'request.enc', 'envelope.json', 'envelope.json.pending'}


def module(name):
    spec = importlib.util.spec_from_file_location(name, DIRECTORY / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.fixture
def writer():
    return module('git_request_archive_writer')


def write(writer, directory, **changes):
    args = dict(body=BODY, expected_sha256=SHA, key=KEY,
                key_parameter=PARAMETER, key_region='us-east-2')
    args.update(changes)
    return writer.write_request_archive(directory, **args)


def snapshot(directory):
    return {p.name: p.read_bytes() for p in directory.iterdir() if p.is_file()}


def assert_private(directory, error=None):
    for raw in snapshot(directory).values():
        assert BODY not in raw
        assert b'PRIVATE_FIXTURE_TEXT_17493' not in raw
        assert KEY not in raw
        assert KEY.hex().encode() not in raw
    if error is not None:
        text = str(error)
        assert 'PRIVATE_FIXTURE_TEXT_17493' not in text
        assert KEY.hex() not in text
        assert repr(KEY) not in text


class FakeSSM:
    def __init__(self, key=KEY):
        self.key = key
        self.calls = []

    def get_parameter(self, **kwargs):
        self.calls.append(kwargs)
        return dict(Parameter=dict(Type='SecureString', Value=self.key.hex()))


def test_real_reader_roundtrip_keeps_raw_json_nanoseconds_and_no_plaintext(writer, tmp_path):
    directory = tmp_path / 'archive'
    receipt = write(writer, directory)
    client = FakeSSM()
    restored = module('git_request_archive').read_request_archive(directory, SHA, client)
    assert restored == BODY
    assert b'1633309200123456789' in restored
    assert client.calls == [dict(Name=PARAMETER, WithDecryption=True)]
    files = snapshot(directory)
    assert set(files) == FILES
    envelope = json.loads(files['envelope.json'])
    assert set(envelope) == {'schema', 'request_sha256', 'ciphertext_sha256',
                             'nonce_hex', 'key_parameter', 'key_region'}
    assert envelope['schema'] == 'FRANKIE_GIT_REQUEST_ARCHIVE_V1'
    assert envelope['key_parameter'] == PARAMETER
    assert envelope['key_region'] == 'us-east-2'
    assert envelope['request_sha256'] == SHA
    assert len(bytes.fromhex(envelope['nonce_hex'])) == 12
    assert receipt == dict(schema='FRANKIE_GIT_REQUEST_ARCHIVE_WRITTEN_V1',
                          request_sha256=SHA, request_bytes=len(BODY),
                          ciphertext_sha256=hashlib.sha256(files['request.enc']).hexdigest(),
                          envelope_sha256=hashlib.sha256(files['envelope.json']).hexdigest())
    assert envelope['ciphertext_sha256'] == receipt['ciphertext_sha256']
    final_stat = (directory/'envelope.json').stat()
    pending_stat = (directory/'envelope.json.pending').stat()
    assert (final_stat.st_dev, final_stat.st_ino) == (pending_stat.st_dev, pending_stat.st_ino)
    assert final_stat.st_nlink == pending_stat.st_nlink == 2
    assert files['envelope.json.pending'] == files['envelope.json']
    assert_private(directory)


def test_nonce_is_fresh_for_each_new_archive(writer, tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    write(writer, first)
    write(writer, second)
    a, b = json.loads((first/'envelope.json').read_bytes()), json.loads((second/'envelope.json').read_bytes())
    assert a['nonce_hex'] != b['nonce_hex']
    assert (first/'request.enc').read_bytes() != (second/'request.enc').read_bytes()
    for directory in (first, second):
        assert module('git_request_archive').read_request_archive(directory, SHA, FakeSSM()) == BODY


@pytest.mark.parametrize('changes', [
    {'body': BODY.decode()}, {'body': bytearray(BODY)}, {'body': b'different'},
    {'expected_sha256': SHA.upper()}, {'expected_sha256': '0'*63},
    {'expected_sha256': '0'*64}, {'expected_sha256': None},
    {'key': b'x'*31}, {'key': b'x'*33}, {'key': KEY.hex()}, {'key': bytearray(KEY)},
    {'key_parameter': '/unrelated/secret'}, {'key_parameter': PARAMETER+'/child'},
    {'key_parameter': '/markets/frankie/request-transport/'},
    {'key_parameter': '/markets/frankie/request-transport/'+'a'*81},
    {'key_parameter': PARAMETER+'\n'}, {'key_parameter': None},
    {'key_region': 'us-east-1'}, {'key_region': None},
])
def test_invalid_input_refused_before_any_directory_creation(writer, tmp_path, changes):
    directory = tmp_path / 'archive'
    with pytest.raises((ValueError, TypeError)) as error:
        write(writer, directory, **changes)
    assert not directory.exists()
    assert list(tmp_path.iterdir()) == []
    assert 'PRIVATE_FIXTURE_TEXT_17493' not in str(error.value)
    assert KEY.hex() not in str(error.value)


def test_complete_verified_replay_returns_same_receipt_without_changing_files(writer, tmp_path):
    directory = tmp_path / 'archive'
    first = write(writer, directory)
    before = snapshot(directory)
    stats = {p.name: (p.stat().st_ino, p.stat().st_mtime_ns) for p in directory.iterdir()}
    assert write(writer, directory) == first
    assert snapshot(directory) == before
    assert {p.name: (p.stat().st_ino, p.stat().st_mtime_ns) for p in directory.iterdir()} == stats


@pytest.mark.parametrize('changes', [
    dict(body=BODY+b' ', expected_sha256=hashlib.sha256(BODY+b' ').hexdigest()),
    dict(key=b'Z'*32),
    dict(key_parameter='/markets/frankie/request-transport/different'),
    dict(key_region='us-east-1'),
])
def test_replay_cannot_change_request_key_or_metadata(writer, tmp_path, changes):
    directory = tmp_path / 'archive'
    write(writer, directory)
    before = snapshot(directory)
    with pytest.raises((ValueError, FileExistsError)) as error:
        write(writer, directory, **changes)
    assert snapshot(directory) == before
    assert_private(directory, error.value)


@pytest.mark.parametrize('name', ['intent.json', 'request.enc', 'envelope.json', 'envelope.json.pending'])
def test_corrupted_retained_file_refuses_without_repair(writer, tmp_path, name):
    directory = tmp_path / 'archive'
    write(writer, directory)
    path = directory/name
    raw = path.read_bytes()
    path.write_bytes(bytes([raw[0] ^ 1])+raw[1:])
    before = snapshot(directory)
    with pytest.raises((ValueError, FileExistsError)) as error:
        write(writer, directory)
    assert snapshot(directory) == before
    assert_private(directory, error.value)


@pytest.mark.parametrize('name', ['intent.json', 'request.enc', 'envelope.json', 'envelope.json.pending'])
def test_missing_retained_file_refuses_without_reconstruction(writer, tmp_path, name):
    directory = tmp_path / 'archive'
    write(writer, directory)
    (directory/name).unlink()
    before = snapshot(directory)
    with pytest.raises((ValueError, FileExistsError)):
        write(writer, directory)
    assert snapshot(directory) == before


def test_foreign_extra_file_refuses_without_deleting_anything(writer, tmp_path):
    directory = tmp_path / 'archive'
    write(writer, directory)
    (directory/'foreign').write_bytes(b'preserve foreign evidence')
    before = snapshot(directory)
    with pytest.raises((ValueError, FileExistsError)):
        write(writer, directory)
    assert snapshot(directory) == before


@pytest.mark.parametrize('boundary', ['before-ciphertext', 'after-ciphertext', 'before-envelope'])
def test_publication_interruption_retains_intent_and_refuses_retry(writer, tmp_path, monkeypatch, boundary):
    directory = tmp_path / 'archive'
    original = writer._write_new
    def interrupted(fd, name, raw):
        if boundary == 'before-ciphertext' and name == 'request.enc':
            raise OSError('fixture interruption')
        if boundary == 'before-envelope' and name == 'envelope.json.pending':
            raise OSError('fixture interruption')
        result = original(fd, name, raw)
        if boundary == 'after-ciphertext' and name == 'request.enc':
            raise OSError('fixture interruption')
        return result
    monkeypatch.setattr(writer, '_write_new', interrupted)
    with pytest.raises(ValueError, match='private Git request archive'):
        write(writer, directory)
    assert (directory/'intent.json').is_file()
    assert not (directory/'envelope.json').exists()
    before = snapshot(directory)
    monkeypatch.setattr(writer, '_write_new', original)
    with pytest.raises((ValueError, FileExistsError)):
        write(writer, directory)
    assert snapshot(directory) == before
    assert_private(directory)


@pytest.mark.parametrize('kind', ['existing-empty', 'existing-file', 'missing-parent', 'parent-traversal'])
def test_unsafe_or_foreign_directory_refused(writer, tmp_path, kind):
    directory = tmp_path/'archive'
    if kind == 'existing-empty':
        directory.mkdir()
    elif kind == 'existing-file':
        directory.write_bytes(b'foreign evidence')
    elif kind == 'missing-parent':
        directory = tmp_path/'missing'/'archive'
    else:
        directory = tmp_path/'child'/'..'/'archive'
        (tmp_path/'child').mkdir()
    with pytest.raises((ValueError, OSError)):
        write(writer, directory)
    if kind == 'existing-file':
        assert directory.read_bytes() == b'foreign evidence'
    else:
        assert not (tmp_path/'archive'/'envelope.json').exists()
    assert not (tmp_path/'missing').exists()


@pytest.mark.parametrize('where', ['ancestor', 'directory', 'intent.json', 'request.enc', 'envelope.json', 'envelope.json.pending'])
def test_symlinks_are_refused_and_target_bytes_unchanged(writer, tmp_path, where):
    target = tmp_path/'target'
    target.mkdir()
    if where == 'ancestor':
        (tmp_path/'alias').symlink_to(target, target_is_directory=True)
        directory = tmp_path/'alias'/'archive'
        before = snapshot(target)
    elif where == 'directory':
        directory = tmp_path/'archive'
        directory.symlink_to(target, target_is_directory=True)
        before = snapshot(target)
    else:
        directory = tmp_path/'archive'
        write(writer, directory)
        source = directory/where
        saved = target/'saved'
        saved.write_bytes(source.read_bytes())
        source.unlink()
        source.symlink_to(saved)
        before = snapshot(target)
    with pytest.raises((ValueError, OSError)):
        write(writer, directory)
    assert snapshot(target) == before
    assert not (target/'archive').exists()


def test_concurrent_attempt_cannot_publish_into_inflight_archive(writer, tmp_path, monkeypatch):
    directory = tmp_path/'archive'
    entered, release = threading.Event(), threading.Event()
    original = writer._write_new
    def paused(fd, name, raw):
        if name == 'intent.json':
            entered.set()
            if not release.wait(10):
                raise RuntimeError('fixture barrier timed out')
        return original(fd, name, raw)
    monkeypatch.setattr(writer, '_write_new', paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(write, writer, directory)
        try:
            assert entered.wait(10)
            with pytest.raises((ValueError, FileExistsError)):
                write(writer, directory)
            assert list(directory.iterdir()) == []
        finally:
            release.set()
        receipt = first.result(timeout=10)
    assert receipt['request_sha256'] == SHA
    assert module('git_request_archive').read_request_archive(directory, SHA, FakeSSM()) == BODY
    assert set(snapshot(directory)) == FILES


def test_git_checkout_replay_accepts_separate_regular_envelope_files_without_writes(writer, tmp_path):
    original = tmp_path/'original'
    expected = write(writer, original)
    checkout = tmp_path/'checkout'
    checkout.mkdir()
    # Git checkout preserves file bytes, not hardlink identity.
    for name, raw in snapshot(original).items():
        (checkout/name).write_bytes(raw)
    final_stat = (checkout/'envelope.json').stat()
    pending_stat = (checkout/'envelope.json.pending').stat()
    assert final_stat.st_ino != pending_stat.st_ino
    assert final_stat.st_nlink == pending_stat.st_nlink == 1
    before = snapshot(checkout)
    stats = {p.name: (p.stat().st_ino, p.stat().st_mtime_ns) for p in checkout.iterdir()}
    assert write(writer, checkout) == expected
    assert snapshot(checkout) == before
    assert {p.name: (p.stat().st_ino, p.stat().st_mtime_ns) for p in checkout.iterdir()} == stats
    assert module('git_request_archive').read_request_archive(checkout, SHA, FakeSSM()) == BODY


def test_git_checkout_replay_refuses_changed_pending_envelope(writer, tmp_path):
    original = tmp_path/'original'
    write(writer, original)
    checkout = tmp_path/'checkout'
    checkout.mkdir()
    for name, raw in snapshot(original).items():
        (checkout/name).write_bytes(raw)
    pending = checkout/'envelope.json.pending'
    pending.write_bytes(pending.read_bytes()+b'\n')
    before = snapshot(checkout)
    with pytest.raises((ValueError, FileExistsError)):
        write(writer, checkout)
    assert snapshot(checkout) == before


def fail_final_publication_sync(writer, directory, monkeypatch):
    """Leave complete bytes but inject failure before final directory durability."""
    import os
    import stat
    original = writer.os.fsync
    hit = []
    def interrupted(fd):
        if (stat.S_ISDIR(os.fstat(fd).st_mode)
                and (directory/'envelope.json').exists()):
            hit.append(True)
            raise OSError('fixture final publication sync failure')
        return original(fd)
    monkeypatch.setattr(writer.os, 'fsync', interrupted)
    with pytest.raises(ValueError, match='private Git request archive'):
        write(writer, directory)
    assert hit == [True]
    assert set(snapshot(directory)) == FILES
    monkeypatch.setattr(writer.os, 'fsync', original)
    return original


def sync_target(fd, directory):
    import os
    import stat
    if stat.S_ISDIR(os.fstat(fd).st_mode):
        return 'archive-directory'
    # This suite runs in isolated Linux CI; every descriptor belongs to tmp_path.
    path = Path(os.readlink('/proc/self/fd/'+str(fd)))
    assert path.parent == directory
    return path.name


def test_post_link_sync_failure_replay_syncs_verified_files_then_directory(writer, tmp_path, monkeypatch):
    directory = tmp_path/'archive'
    original = fail_final_publication_sync(writer, directory, monkeypatch)
    before = snapshot(directory)
    calls = []
    def recorded(fd):
        calls.append(sync_target(fd, directory))
        return original(fd)
    monkeypatch.setattr(writer.os, 'fsync', recorded)
    result = write(writer, directory)
    assert result['request_sha256'] == SHA
    assert FILES <= set(calls)
    assert calls[-1] == 'archive-directory'
    assert snapshot(directory) == before
    assert module('git_request_archive').read_request_archive(directory, SHA, FakeSSM()) == BODY


@pytest.mark.parametrize('target', ['request.enc', 'envelope.json.pending', 'archive-directory'])
def test_post_link_sync_failure_replay_cannot_succeed_if_resync_fails(writer, tmp_path, monkeypatch, target):
    directory = tmp_path/'archive'
    original = fail_final_publication_sync(writer, directory, monkeypatch)
    before = snapshot(directory)
    hit = []
    def interrupted(fd):
        if sync_target(fd, directory) == target:
            hit.append(True)
            raise OSError('fixture replay durability failure')
        return original(fd)
    monkeypatch.setattr(writer.os, 'fsync', interrupted)
    with pytest.raises(ValueError, match='private Git request archive'):
        write(writer, directory)
    assert hit
    assert snapshot(directory) == before
    assert_private(directory)
