"""Atomic, read-back-verified saves; previous bytes and interrupted writes stay on disk."""
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


def write_chunks(path, chunks):
    """Publish only complete bytes. Failed pending files are deliberately retained."""
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
    if witness(pending) != expected:
        raise ValueError('durable artifact readback differs')
    if path.exists():
        previous = witness(path)
        retained = path.with_name(path.name + '.retained-' + previous['sha256'])
        if retained.exists():
            if witness(retained) != previous:
                raise ValueError('retained artifact differs from its content hash')
        else:
            os.link(path, retained)
        sync_directory(path.parent)
    os.replace(pending, path)
    sync_directory(path.parent)
    if witness(path) != expected:
        raise ValueError('published durable artifact differs')
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
