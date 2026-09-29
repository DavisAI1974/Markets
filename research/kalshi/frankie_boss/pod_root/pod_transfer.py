"""Byte transport for the Pod ROOT path (SPEC-pod-day-runner.md): presigned S3 PUT/GET, 4 GiB chunks, a zstd tar stream
with a sha256 manifest of every file, and the unpack + verify the box runs before a ROOT is placed.

Stdlib + zstandard (the box venv's pin zstandard==0.25.0); loaded by path (no package import: the frankie_boss package
__init__ pulls torch). Used by three callers, each with the same functions:
  the box (frankie_box_pod_root.py): export a sealed ingest's files to presigned PUT slots; import a Pod's ROOT;
  the Pod / worker agent (pod_agent.py): download a day's inputs; pack and upload the ROOT output;
  nothing here holds a credential: every URL is presigned by the runner that holds the AWS keys.

Why chunks: one presigned PUT carries at most 5 GB (S3's single-PUT limit); a ROOT output or a journal can be larger, so
every stream is cut into CHUNK_BYTES (4 GiB) objects, each PUT whole with its Content-Length, each with its own sha256.
NO DATA DROPPED: pack walks every regular file and directory under the named trees (symlinks and special files refuse
the pack, never skipped); verify compares the whole set both ways (missing and extra) plus bytes and sha256 per file.
"""
import hashlib
import http.client
import io
import json
import os
import tarfile
import time
from pathlib import Path
from urllib.parse import urlsplit

CHUNK_BYTES = 4 * 1024 ** 3          # under S3's 5 GB single-PUT limit
BLOCK = 8 * 1024 * 1024
TRANSFER_SCHEMA = 'FRANKIE_POD_ROOT_TRANSFER_V1'


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while block := f.read(64 * 1024 * 1024):
            h.update(block)
    return h.hexdigest()


def _connection(url, timeout=900):
    u = urlsplit(url)
    cls = http.client.HTTPSConnection if u.scheme == 'https' else http.client.HTTPConnection
    return cls(u.hostname, u.port, timeout=timeout, blocksize=BLOCK), (u.path or '/') + ('?' + u.query if u.query else '')


class _Slice(io.RawIOBase):
    """length bytes of a file from offset, hashed as they are read (the body of one PUT)."""
    def __init__(self, path, offset, length):
        self.f = open(path, 'rb')
        self.f.seek(offset)
        self.left = length
        self.h = hashlib.sha256()

    def readable(self):
        return True

    def read(self, n=-1):
        if self.left <= 0:
            return b''
        n = self.left if n is None or n < 0 else min(n, self.left)
        data = self.f.read(n)
        if not data:
            raise IOError('file ended before the declared range')
        self.left -= len(data)
        self.h.update(data)
        return data

    def close(self):
        self.f.close()
        super().close()


def put_range(url, path, offset=0, length=None, retries=6, headers=None):
    """PUT length bytes of path (from offset) to a presigned URL; returns their sha256. Retried whole on any failure."""
    if length is None:
        length = os.stat(path).st_size - offset
    error = None
    for attempt in range(retries):
        body = _Slice(path, offset, length)
        try:
            conn, target = _connection(url)
            conn.request('PUT', target, body=body if length else b'',
                         headers={'Content-Length': str(length), **(headers or {})})
            response = conn.getresponse()
            text = response.read(400)
            conn.close()
            if response.status in (200, 201):
                return body.h.hexdigest() if length else hashlib.sha256(b'').hexdigest()
            error = 'HTTP %d %s' % (response.status, text[:300])
            if response.status in (403, 412):          # expired / refused / precondition: a retry cannot help
                break
        except (OSError, http.client.HTTPException) as e:
            error = '%s: %s' % (type(e).__name__, e)
        finally:
            body.close()
        time.sleep(min(60, 2 ** attempt))
    raise IOError('PUT failed after %d attempt(s): %s' % (attempt + 1, error))


def put_bytes(url, data, retries=6, headers=None):
    error = None
    for attempt in range(retries):
        try:
            conn, target = _connection(url)
            conn.request('PUT', target, body=data, headers={'Content-Length': str(len(data)), **(headers or {})})
            response = conn.getresponse()
            text = response.read(400)
            conn.close()
            if response.status in (200, 201):
                return hashlib.sha256(data).hexdigest()
            error = 'HTTP %d %s' % (response.status, text[:300])
            if response.status in (403, 412):
                break
        except (OSError, http.client.HTTPException) as e:
            error = '%s: %s' % (type(e).__name__, e)
        time.sleep(min(60, 2 ** attempt))
    raise IOError('PUT failed: %s' % error)


def get_bytes(url, retries=6, limit=None):
    error = None
    for attempt in range(retries):
        try:
            conn, target = _connection(url, timeout=120)
            conn.request('GET', target)
            response = conn.getresponse()
            data = response.read() if limit is None else response.read(limit)
            conn.close()
            if response.status == 200:
                return data
            error = 'HTTP %d %s' % (response.status, data[:300])
            if response.status in (403, 404):
                break
        except (OSError, http.client.HTTPException) as e:
            error = '%s: %s' % (type(e).__name__, e)
        time.sleep(min(60, 2 ** attempt))
    raise IOError('GET failed: %s' % error)


def get_to_file(url, path, expect_bytes, retries=8):
    """GET a presigned object into path (via path.part, resumed by HTTP Range after a cut); returns (bytes, sha256)."""
    path = Path(path)
    part = path.with_name(path.name + '.part')
    error = None
    for attempt in range(retries):
        have = part.stat().st_size if part.exists() else 0
        if have > expect_bytes:
            part.unlink()
            have = 0
        try:
            if have < expect_bytes or expect_bytes == 0:
                conn, target = _connection(url)
                conn.request('GET', target, headers={'Range': 'bytes=%d-' % have} if have else {})
                response = conn.getresponse()
                if response.status not in (200, 206):
                    error = 'HTTP %d %s' % (response.status, response.read(300))
                    conn.close()
                    if response.status in (403, 404):
                        break
                    raise IOError(error)
                mode = 'ab' if (have and response.status == 206) else 'wb'
                with open(part, mode) as out:
                    while block := response.read(BLOCK):
                        out.write(block)
                conn.close()
            got = part.stat().st_size
            if got != expect_bytes:
                raise IOError('%s: %d bytes, %d expected' % (path, got, expect_bytes))
            digest = sha256_file(part)
            os.replace(part, path)
            return got, digest
        except (OSError, http.client.HTTPException) as e:
            error = '%s: %s' % (type(e).__name__, e)
            time.sleep(min(60, 2 ** attempt))
    raise IOError('GET %s failed: %s' % (path, error))


def get_parts_to_file(parts, path):
    """Several presigned part objects concatenated into one file, in order; returns (bytes, sha256 of the whole)."""
    path = Path(path)
    if len(parts) == 1:                              # one object (an S3 copy of the whole file): straight into place
        return get_to_file(parts[0]['url'], path, parts[0]['bytes'])
    h, total = hashlib.sha256(), 0
    tmp = path.with_name(path.name + '.assembling')
    with open(tmp, 'wb') as out:
        for i, p in enumerate(parts):
            piece = path.with_name('%s.piece-%04d' % (path.name, i))
            n, _ = get_to_file(p['url'], piece, p['bytes'])
            with open(piece, 'rb') as f:
                while block := f.read(BLOCK):
                    out.write(block)
                    h.update(block)
            total += n
            piece.unlink()
    os.replace(tmp, path)
    return total, h.hexdigest()


def plan_parts(size, chunk=CHUNK_BYTES):
    """[(offset, length)] covering size bytes in chunk pieces (one empty piece for an empty file)."""
    if size == 0:
        return [(0, 0)]
    return [(o, min(chunk, size - o)) for o in range(0, size, chunk)]


# ------------------------------------------------------------------------------------------------ the chunked stream

class ChunkWriter(io.RawIOBase):
    """A write-only stream cut into chunk files under spool/, each uploaded (upload(index, path) -> sha256) and deleted
    as soon as it is full; at most one chunk on disk at a time."""
    def __init__(self, spool, upload, chunk=CHUNK_BYTES):
        self.spool, self.upload, self.chunk = Path(spool), upload, chunk
        self.spool.mkdir(parents=True, exist_ok=True)
        self.index, self.f, self.n, self.h = 0, None, 0, None
        self.chunks = []

    def writable(self):
        return True

    def _open(self):
        self.f = open(self.spool / ('chunk-%04d' % self.index), 'wb')
        self.n, self.h = 0, hashlib.sha256()

    def _finish(self):
        self.f.close()
        path = self.spool / ('chunk-%04d' % self.index)
        sent = self.upload(self.index, path)
        if sent != self.h.hexdigest():
            raise IOError('chunk %d: uploaded bytes hash %s, written %s' % (self.index, sent, self.h.hexdigest()))
        self.chunks.append(dict(index=self.index, bytes=self.n, sha256=self.h.hexdigest()))
        path.unlink()
        self.index += 1
        self.f = None

    def write(self, data):
        data = memoryview(data)
        written = 0
        while written < len(data):
            if self.f is None:
                self._open()
            take = min(len(data) - written, self.chunk - self.n)
            piece = data[written:written + take]
            self.f.write(piece)
            self.h.update(piece)
            self.n += take
            written += take
            if self.n == self.chunk:
                self._finish()
        return written

    def close(self):
        if not self.closed:
            if self.f is not None and self.n:
                self._finish()
            elif self.f is not None:
                self.f.close()
                (self.spool / ('chunk-%04d' % self.index)).unlink()
        super().close()


class ChunkReader(io.RawIOBase):
    """The chunks read back in order from presigned GETs; each chunk's bytes and sha256 checked when it ends."""
    def __init__(self, chunks):
        self.chunks = list(chunks)           # [{url, bytes, sha256}]
        self.i, self.response, self.conn, self.left, self.h = -1, None, None, 0, None
        self.read_chunks = []

    def readable(self):
        return True

    def _next(self):
        if self.h is not None:
            c = self.chunks[self.i]
            if self.h.hexdigest() != c['sha256']:
                raise IOError('chunk %d sha256 %s differs from the manifest %s' % (self.i, self.h.hexdigest(), c['sha256']))
            self.read_chunks.append(dict(index=self.i, bytes=c['bytes'], sha256=c['sha256']))
            self.h = None
        if self.conn is not None:
            self.conn.close()
            self.conn = None
        if self.i + 1 >= len(self.chunks):
            self.i = len(self.chunks)
            self.response = None
            return False
        self.i += 1
        c = self.chunks[self.i]
        self.conn, target = _connection(c['url'])
        self.conn.request('GET', target)
        self.response = self.conn.getresponse()
        if self.response.status != 200:
            raise IOError('chunk %d GET HTTP %d' % (self.i, self.response.status))
        self.left, self.h = c['bytes'], hashlib.sha256()
        return True

    def read(self, n=-1):
        while True:
            if self.response is None and not self._next():
                return b''
            if self.left == 0:
                if not self._next():
                    return b''
                continue
            want = self.left if n is None or n < 0 else min(n, self.left)
            data = self.response.read(min(want, BLOCK))
            if not data:
                raise IOError('chunk %d ended %d bytes early' % (self.i, self.left))
            self.left -= len(data)
            self.h.update(data)
            return data

    def finish(self):
        """After the tar end: the last chunk's hash is checked and every chunk was read whole."""
        while self.read(BLOCK):
            pass
        if len(self.read_chunks) != len(self.chunks):
            raise IOError('%d of %d chunks read' % (len(self.read_chunks), len(self.chunks)))


class _HashingFile(io.RawIOBase):
    def __init__(self, path):
        self.f = open(path, 'rb')
        self.h = hashlib.sha256()
        self.n = 0

    def readable(self):
        return True

    def read(self, n=-1):
        data = self.f.read(n)
        self.h.update(data)
        self.n += len(data)
        return data

    def close(self):
        self.f.close()
        super().close()


def pack(trees, writer, level=3, threads=2):
    """Every directory and regular file of each (arcname, directory) as one zstd-compressed tar stream into writer.
    Returns (files, dirs): files = [{path, bytes, sha256}] hashed from the bytes that went into the tar."""
    import zstandard
    files, dirs = [], []
    cctx = zstandard.ZstdCompressor(level=level, threads=threads)
    with cctx.stream_writer(writer, closefd=False) as zw:
        with tarfile.open(fileobj=zw, mode='w|', format=tarfile.PAX_FORMAT) as tar:
            for arc, top in trees:
                top = Path(top)
                if not top.is_dir():
                    continue
                for base, subdirs, names in os.walk(top, followlinks=False):
                    subdirs.sort()
                    rel = Path(base).relative_to(top)
                    arcdir = arc if str(rel) == '.' else '%s/%s' % (arc, rel.as_posix())
                    tar.add(base, arcname=arcdir, recursive=False)
                    dirs.append(arcdir)
                    for d in subdirs:
                        if os.path.islink(os.path.join(base, d)):
                            raise ValueError('a symlink in the tree is refused (never followed, never skipped): %s/%s' % (base, d))
                    for name in sorted(names):
                        path = os.path.join(base, name)
                        st = os.lstat(path)
                        if not os.path.isfile(path) or os.path.islink(path):
                            raise ValueError('only regular files are packed; refused: %s' % path)
                        info = tar.gettarinfo(path, arcname='%s/%s' % (arcdir, name))
                        src = _HashingFile(path)
                        try:
                            tar.addfile(info, src)
                        finally:
                            src.close()
                        if src.n != st.st_size:
                            raise IOError('%s changed while packed (%d of %d bytes)' % (path, src.n, st.st_size))
                        files.append(dict(path='%s/%s' % (arcdir, name), bytes=src.n, sha256=src.h.hexdigest()))
    writer.close()
    return files, dirs


def unpack(reader, dest):
    """The zstd tar stream extracted under dest (tarfile's 'data' filter: no absolute paths, no links out)."""
    import zstandard
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=False)
    dctx = zstandard.ZstdDecompressor()
    with dctx.stream_reader(reader, read_across_frames=True, closefd=False) as zr:
        with tarfile.open(fileobj=zr, mode='r|') as tar:
            tar.extractall(dest, filter='data')
    if hasattr(reader, 'finish'):
        reader.finish()


def verify(dest, files, dirs):
    """Every manifest file present with its bytes and sha256, every manifest directory present, nothing else there.
    Returns dict(files_checked, bytes_checked, problems=[...]); an empty problems list is the only pass."""
    dest = Path(dest)
    want = {f['path']: f for f in files}
    problems, checked, total = [], 0, 0
    seen_files, seen_dirs = set(), set()
    for base, subdirs, names in os.walk(dest, followlinks=False):
        rel = Path(base).relative_to(dest).as_posix()
        if rel != '.':
            seen_dirs.add(rel)
        for name in names:
            path = os.path.join(base, name)
            arc = ('%s/%s' % (rel, name)) if rel != '.' else name
            seen_files.add(arc)
            f = want.get(arc)
            if f is None:
                problems.append(dict(path=arc, problem='extra file not in the manifest'))
                continue
            size = os.lstat(path).st_size
            if size != f['bytes']:
                problems.append(dict(path=arc, problem='bytes %d, manifest %d' % (size, f['bytes'])))
                continue
            digest = sha256_file(path)
            if digest != f['sha256']:
                problems.append(dict(path=arc, problem='sha256 %s, manifest %s' % (digest, f['sha256'])))
                continue
            checked += 1
            total += size
    for arc in sorted(set(want) - seen_files):
        problems.append(dict(path=arc, problem='missing'))
    for arc in sorted(set(dirs) - seen_dirs):
        problems.append(dict(path=arc, problem='directory missing'))
    return dict(files_checked=checked, bytes_checked=total, files_in_manifest=len(want), problems=problems)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))
