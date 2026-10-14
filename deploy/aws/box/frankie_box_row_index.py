"""Owner-local JSONL offsets learned during an already required read.

The index is a transport aid, never evidence or a replacement for source-pin checks.
It binds the source pin and exact local file identity, and is atomically replaced.
Offsets use eight bytes per row; decoded scientific values are never retained here.
"""
from array import array
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile


def file_identity(path):
    stat = Path(path).stat()
    return dict(device=stat.st_dev, inode=stat.st_ino, bytes=stat.st_size,
                mtime_ns=stat.st_mtime_ns, ctime_ns=stat.st_ctime_ns)


class RowIndex:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __init__(self, pin):
        self.source = Path(pin['path'])
        self.identity = dict(path=str(self.source), sha256=pin.get('sha256'),
                             pinned_bytes=pin.get('bytes'), stat=file_identity(self.source))
        key = hashlib.sha256(json.dumps(self.identity, sort_keys=True).encode()).hexdigest()
        self.path = self.source.parent / '.frankie-row-index' / (key + '.offsets')
        self.offsets = array('Q', [0])
        self.dirty = False
        try:
            with self.path.open('rb') as handle:
                header = json.loads(handle.readline())
                body = handle.read()
            if (header.get('identity') == self.identity and header.get('byteorder') == sys.byteorder
                    and header.get('sha256') == hashlib.sha256(body).hexdigest()
                    and len(body) % self.offsets.itemsize == 0):
                offsets = array('Q')
                offsets.frombytes(body)
                if offsets and offsets[0] == 0 and offsets[-1] <= self.identity['stat']['bytes']:
                    self.offsets = offsets
        except (OSError, ValueError, TypeError, AttributeError):
            pass                         # a derived index can always be rebuilt on the required read

    def position(self, ordinal):
        return self.offsets[ordinal] if 0 <= ordinal < len(self.offsets) else None

    def observe(self, ordinal, offset, length):
        if ordinal < 0 or length <= 0:
            return
        if ordinal < len(self.offsets) - 1:
            if self.offsets[ordinal] != offset or self.offsets[ordinal + 1] != offset + length:
                raise ValueError('source row differs from its owner-local offset index')
        elif ordinal == len(self.offsets) - 1 and self.offsets[-1] == offset:
            self.offsets.append(offset + length)
            self.dirty = True
        # A resumed read can begin beyond the indexed prefix. It does not invent skipped offsets.

    def close(self):
        if not self.dirty:
            return
        pending = None
        try:
            if file_identity(self.source) != self.identity['stat']:
                return
            self.path.parent.mkdir(exist_ok=True)
            # Serialize only publication, never the source read. A shorter concurrent reader
            # must not overwrite a longer prefix another consumer has already learned.
            import fcntl
            with self.path.with_suffix('.lock').open('a+b') as lock:
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                if self.path.exists():
                    with self.path.open('rb') as current:
                        header = json.loads(current.readline())
                        current_body = current.read()
                    if (header.get('identity') == self.identity
                            and header.get('sha256') == hashlib.sha256(current_body).hexdigest()
                            and header.get('rows', -1) >= len(self.offsets) - 1):
                        return
                body = self.offsets.tobytes()
                header = dict(identity=self.identity, byteorder=sys.byteorder, rows=len(self.offsets) - 1,
                              sha256=hashlib.sha256(body).hexdigest())
                with tempfile.NamedTemporaryFile(dir=self.path.parent, prefix='pending-', delete=False) as out:
                    pending = Path(out.name)
                    out.write((json.dumps(header, sort_keys=True) + '\n').encode())
                    out.write(body)
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(pending, self.path)
                self.dirty = False
        except (OSError, ValueError, TypeError, AttributeError):
            pass                         # inability to save an acceleration index is not lost evidence
        finally:
            if pending is not None:
                pending.unlink(missing_ok=True)
