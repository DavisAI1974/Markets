"""Publish exact admitted request bytes as an immutable, authenticated Git archive.

The archive parent must exist. Publication uses POSIX directory descriptors and
no-follow opens; this writer performs no key lookup, network access or dispatch.
An incomplete archive is retained for diagnosis and is never repaired in place.
"""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat

SCHEMA = 'FRANKIE_GIT_REQUEST_ARCHIVE_V1'

INTENT_NAME = 'intent.json'
CIPHERTEXT_NAME = 'request.enc'
ENVELOPE_NAME = 'envelope.json'
PENDING_NAME = 'envelope.json.pending'
INTENT_SCHEMA = 'FRANKIE_GIT_REQUEST_ARCHIVE_INTENT_V1'
RECEIPT_SCHEMA = 'FRANKIE_GIT_REQUEST_ARCHIVE_WRITTEN_V1'


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')


@contextmanager
def _directory(directory):
    path = Path(directory)
    if '..' in path.parts:
        raise ValueError('archive path traversal refused')
    path = Path(os.path.abspath(path))
    if not path.name:
        raise ValueError('explicit archive directory required')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent = os.open(path.anchor, flags)
    leaf = None
    try:
        for part in path.parent.parts[1:]:
            next_fd = os.open(part, flags, dir_fd=parent)
            os.close(parent)
            parent = next_fd
        try:
            os.mkdir(path.name, mode=0o700, dir_fd=parent)
            created = True
            os.fsync(parent)
        except FileExistsError:
            created = False
        leaf = os.open(path.name, flags, dir_fd=parent)
        yield leaf, created
    finally:
        if leaf is not None:
            os.close(leaf)
        os.close(parent)


def _write_new(directory_fd, name, raw):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                 0o600, dir_fd=directory_fd)
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError('archive write did not progress')
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(directory_fd)


def _publish_envelope(directory_fd, raw):
    # A failed envelope write or fsync must not expose a reader-visible manifest.
    _write_new(directory_fd, PENDING_NAME, raw)
    os.link(PENDING_NAME, ENVELOPE_NAME, src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd, follow_symlinks=False)
    os.fsync(directory_fd)
    # Retain the staged envelope as evidence; publication never deletes a file.


def _read(directory_fd, name, limit, *, links=1):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != links or info.st_size > limit:
            raise ValueError('ordinary bounded archive file required')
        chunks = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(fd, min(remaining, 1024 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b''.join(chunks)
        if len(raw) > limit or len(raw) != info.st_size:
            raise ValueError('archive file changed while reading')
        return raw
    finally:
        os.close(fd)


def _intent(envelope, envelope_raw, request_bytes, ciphertext_bytes):
    return dict(schema=INTENT_SCHEMA, envelope=envelope,
                envelope_sha256=_sha(envelope_raw), request_bytes=request_bytes,
                ciphertext_bytes=ciphertext_bytes)


def _receipt(envelope, envelope_raw, request_bytes):
    return dict(schema=RECEIPT_SCHEMA, request_sha256=envelope['request_sha256'],
                request_bytes=request_bytes, ciphertext_sha256=envelope['ciphertext_sha256'],
                envelope_sha256=_sha(envelope_raw))


def _replay(directory_fd, body, expected, key, parameter, region, aesgcm):
    if set(os.listdir(directory_fd)) != {INTENT_NAME, CIPHERTEXT_NAME, ENVELOPE_NAME, PENDING_NAME}:
        raise ValueError('incomplete or foreign archive refused')
    published = os.stat(ENVELOPE_NAME, dir_fd=directory_fd, follow_symlinks=False)
    staged = os.stat(PENDING_NAME, dir_fd=directory_fd, follow_symlinks=False)
    shared = (published.st_dev, published.st_ino) == (staged.st_dev, staged.st_ino)
    # Git does not preserve hardlinks: a later checkout has two ordinary files.
    links = 2 if shared else 1
    if (not stat.S_ISREG(published.st_mode) or not stat.S_ISREG(staged.st_mode)
            or published.st_nlink != links or staged.st_nlink != links):
        raise ValueError('archive publication link differs')
    envelope_raw = _read(directory_fd, ENVELOPE_NAME, 4096, links=links)
    if _read(directory_fd, PENDING_NAME, 4096, links=links) != envelope_raw:
        raise ValueError('archive staged envelope differs')
    envelope = json.loads(envelope_raw)
    if (type(envelope) is not dict or set(envelope) != {
            'schema', 'request_sha256', 'ciphertext_sha256', 'nonce_hex',
            'key_parameter', 'key_region'}
            or envelope['schema'] != SCHEMA or envelope['request_sha256'] != expected
            or envelope['key_parameter'] != parameter or envelope['key_region'] != region
            or type(envelope['nonce_hex']) is not str
            or not re.fullmatch(r'[0-9a-f]{24}', envelope['nonce_hex'])
            or envelope_raw != _json(envelope)):
        raise ValueError('archive metadata differs')
    ciphertext = _read(directory_fd, CIPHERTEXT_NAME, len(body) + 16)
    if len(ciphertext) != len(body) + 16 or _sha(ciphertext) != envelope['ciphertext_sha256']:
        raise ValueError('archive ciphertext differs')
    intent_raw = _read(directory_fd, INTENT_NAME, 8192)
    if intent_raw != _json(_intent(envelope, envelope_raw, len(body), len(ciphertext))):
        raise ValueError('archive intent differs')
    restored = aesgcm(key).decrypt(bytes.fromhex(envelope['nonce_hex']), ciphertext,
                                  expected.encode('ascii'))
    if restored != body or _sha(restored) != expected:
        raise ValueError('archive plaintext differs')
    # A prior publication may have linked the envelope before a directory fsync
    # failed. Authenticate first, then establish durability before claiming replay.
    for name in (INTENT_NAME, CIPHERTEXT_NAME, PENDING_NAME, ENVELOPE_NAME):
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory_fd)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise ValueError('ordinary archive file required for durability')
            os.fsync(fd)
        finally:
            os.close(fd)
    os.fsync(directory_fd)
    return _receipt(envelope, envelope_raw, len(body))


def write_request_archive(directory, body: bytes, expected_sha256: str, *,
                          key: bytes, key_parameter: str, key_region='us-east-2'):
    """Create once or authenticate an exact completed replay; preserve all failures.

    Returns public hashes and byte counts only. Existing archives must carry this
    writer's durable intent; legacy two-file archives remain readable through the
    existing reader but are not silently adopted or rewritten by this writer.
    """
    if (type(body) is not bytes or type(key) is not bytes or len(key) != 32
            or type(expected_sha256) is not str
            or not re.fullmatch(r'[0-9a-f]{64}', expected_sha256)
            or _sha(body) != expected_sha256
            or type(key_parameter) is not str
            or not re.fullmatch(r'/markets/frankie/request-transport/[A-Za-z0-9_-]{1,80}',
                                key_parameter)
            or key_region != 'us-east-2'):
        raise ValueError('exact request bytes, digest and private transport binding required')
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        # All public inputs and cryptographic construction are checked before mkdir.
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, body, expected_sha256.encode('ascii'))
        envelope = dict(schema=SCHEMA, request_sha256=expected_sha256,
                        ciphertext_sha256=_sha(ciphertext), nonce_hex=nonce.hex(),
                        key_parameter=key_parameter, key_region=key_region)
        envelope_raw = _json(envelope)
        intent_raw = _json(_intent(envelope, envelope_raw, len(body), len(ciphertext)))
        with _directory(directory) as (directory_fd, created):
            if not created:
                return _replay(directory_fd, body, expected_sha256, key,
                               key_parameter, key_region, AESGCM)
            _write_new(directory_fd, INTENT_NAME, intent_raw)
            _write_new(directory_fd, CIPHERTEXT_NAME, ciphertext)
            _publish_envelope(directory_fd, envelope_raw)
            return _replay(directory_fd, body, expected_sha256, key,
                           key_parameter, key_region, AESGCM)
    except Exception:
        # Never propagate cryptography, filesystem or parser errors carrying inputs.
        raise ValueError('private Git request archive publication or replay refused') from None
