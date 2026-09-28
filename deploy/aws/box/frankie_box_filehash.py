"""One sha256 per file per process (Greg, 2026-09-28: no pass that is not needed, nothing on one CPU that need not be).

The principal session hashes the same multi-GB files many times in one run (the derivation digest through witness(),
the classroom cache identity, the writing inputs and the docs index; the bedrock layer files through every docs()
call). A sha256 is sequential, so it cannot be spread over CPUs; instead each file is hashed once and the value is
reused while the file is unchanged: the key is (resolved path, device, inode, size, mtime_ns, ctime_ns), the file is
streamed (never held whole) and a file that changes while it is hashed is refused. Same values as hashing again.
"""
import hashlib
import os
from pathlib import Path
import threading

_CACHE = {}
_LOCK = threading.Lock()


def _key(path):
    info = os.stat(path)
    return (str(Path(path).resolve()), info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def witness(path):
    """{bytes, sha256} of the file, streamed; hashed once per unchanged file."""
    key = _key(path)
    with _LOCK:
        hit = _CACHE.get(key)
    if hit is not None:
        return dict(hit)
    hashed, size = hashlib.sha256(), 0
    with open(path, 'rb') as source:
        for block in iter(lambda: source.read(1 << 24), b''):
            hashed.update(block)
            size += len(block)
    if _key(path) != key or size != key[3]:
        raise ValueError(f'file changed while it was hashed: {path}')
    value = dict(bytes=size, sha256=hashed.hexdigest())
    with _LOCK:
        _CACHE[key] = value
    return dict(value)


def sha256_file(path):
    return witness(path)['sha256']
