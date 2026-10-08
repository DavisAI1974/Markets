"""Atomic saves hashed ON THE WRITE STREAM; previous bytes and interrupted writes stay on disk.

Session 6 (Greg, 2026-10-08, directive 5: "we only do 1 pass. Eliminate the 2nd pass"): a published file is hashed once,
from the bytes as they are written. Before, write_chunks read every file back TWICE after writing it (the pending file,
then the published one), and the ROOT's caller hashed it a third time for its receipt; a2's 472 GB inline layer was read
back for ~25 minutes after its 63-minute write (probe PROBE_20261008.md). Now: sha256 + byte count accumulate while the
chunks are written, fsync, replace, one stat (the published size must equal the bytes written), and the witness is handed
to frankie_box_filehash's per-process cache (remember), so every later witness(path) of the same unchanged file in this
process is the write's own value with no read. The returned {bytes, sha256} is the same value the read-backs produced
(the same bytes), so no receipt field changes. FRANKIE_DURABLE_READBACK=on restores the two read-back passes exactly as
before (a reversible switch; nothing else about the file or its name changes).
"""
import hashlib
import json
import os
from pathlib import Path
import uuid


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def witness(path):
    hashed, size = hashlib.sha256(), 0
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            hashed.update(block)
            size += len(block)
    return dict(bytes=size, sha256=hashed.hexdigest())


def _filehash():
    try:
        import frankie_box_filehash as F
    except ImportError:
        try:
            from deploy.aws.box import frankie_box_filehash as F
        except ImportError:
            return None
    return F


def readback_on():
    """The two read-back passes of the earlier write_chunks (off by default since 2026-10-08; FRANKIE_DURABLE_READBACK=on)."""
    return os.environ.get('FRANKIE_DURABLE_READBACK', 'off') == 'on'


def write_chunks(path, chunks):
    """Publish only complete bytes. Failed pending files are deliberately retained. Returns {bytes, sha256} of the
    published file, computed on the write stream (one pass over the bytes); the value is remembered for
    frankie_box_filehash.witness so no caller reads the file again for the same witness."""
    path = Path(path)
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError('durable artifact path traverses a symbolic link')
    missing = []
    parent = path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(exist_ok=True)
        sync_directory(directory.parent)
    pending = path.with_name(path.name + '.pending-' + uuid.uuid4().hex)
    hashed, size = hashlib.sha256(), 0
    with pending.open('xb') as output:
        for block in chunks:
            output.write(block)
            hashed.update(block)
            size += len(block)
        output.flush()
        os.fsync(output.fileno())
    expected = dict(bytes=size, sha256=hashed.hexdigest())
    readback = readback_on()
    if readback and witness(pending) != expected:
        raise ValueError('durable artifact readback differs')
    if not readback and os.stat(pending).st_size != size:
        raise ValueError('durable artifact size on disk differs from the bytes written')
    if path.exists():
        cache = _filehash()
        previous = cache.witness(path) if cache is not None else witness(path)   # cached when this process wrote it
        retained = path.with_name(path.name + '.retained-' + previous['sha256'])
        if retained.exists():
            if witness(retained) != previous:
                raise ValueError('retained artifact differs from its content hash')
        else:
            os.link(path, retained)
        sync_directory(path.parent)
    os.replace(pending, path)
    sync_directory(path.parent)
    if readback:
        if witness(path) != expected:
            raise ValueError('published durable artifact differs')
    elif os.stat(path).st_size != size:
        raise ValueError('published durable artifact size differs from the bytes written')
    cache = _filehash()
    if cache is not None and hasattr(cache, 'remember'):
        cache.remember(path, expected)
    return expected


def write_bytes(path, data):
    return write_chunks(path, (data,))


def write_text(path, text):
    return write_bytes(path, text.encode('utf-8'))


def write_json(path, value):
    encoder = json.JSONEncoder(indent=1, sort_keys=True, default=str)
    def chunks():
        for chunk in encoder.iterencode(value):
            yield chunk.encode('utf-8')
        yield b'\n'
    return write_chunks(path, chunks())
