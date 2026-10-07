"""Publishing large files for the response push (Greg, 2026-09-28: git = code, S3 = all data).

GitHub refuses a file of 100 MB or more and a push over 2 GB. A file under 90 MB is committed as is; 90 MB up to
GZIP_TRY is committed gzipped as <name>.gz when that is under 100 MB (restore reads either form and checks the plain
sha256). Anything larger, or still 100 MB or more after gzip, is uploaded to S3 under its sha256 and committed as a
pointer <name>.s3.json (schema FRANKIE_OFFLOADED_FILE_V1: bytes, sha256, bucket, key, box_path, upload result). The
plain file always stays on the box; a failed upload is recorded in the pointer and never fails the push.

  copy SRC DST   copy a file or a tree into the push clone, writing .gz or a pointer for large files (no plain copy
                 of a large file is ever made)
  seal DST       the same, in place, for large plain files already in DST (the plain copy is removed)

Environment: DAY, CYCLE (the S3 key), OFFLOAD_BUCKET (default frankie-granite42-568968024170-us-east-1),
OFFLOAD_REGION (us-east-1). Stdout: one line per large file.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ZIP_AT = 90 * 1024 * 1024
GIT_MAX = 100 * 1024 * 1024
GZIP_TRY = 1024 * 1024 * 1024      # text over 1 GiB does not compress under 100 MB; it goes to S3 directly
SCHEMA = 'FRANKIE_OFFLOADED_FILE_V1'
CACHE = Path('/opt/frankie-box/work/offload-cache')


_BASIS = {}


def _sha256(path):
    """sha256 of a file, cached by (device, inode, size, mtime) so repeated pushes of the same file hash it once.
    NOTE (session 5): this is a skip-by-stat across processes, the shape of Greg's OPEN call (c); it predates the call
    and is kept unchanged, but every pointer now says which way its sha256 was obtained (sha256_basis: 'hashed' or
    'stat_cache:<tag>'), so a cached value is never silent. Removing the cache is one line once Greg decides."""
    info = path.stat()
    tag = '%d-%d-%d-%d' % (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    cached = CACHE / (tag + '.json')
    try:
        value = json.loads(cached.read_text())['sha256']
        _BASIS[str(path)] = 'stat_cache:' + tag
        return value
    except (OSError, ValueError, KeyError):
        pass
    _BASIS[str(path)] = 'hashed'

    with path.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()       # 4 MiB-class buffered sequential read
    if path.stat().st_mtime_ns != info.st_mtime_ns or path.stat().st_size != info.st_size:
        raise ValueError('file changed while hashing: %s' % path)
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(dict(path=str(path), sha256=digest)))
    except OSError:
        pass
    return digest


def _transport():
    """frankie_box_s3_transport beside this file (the ONE shared transport: CRT first, classic after, reason recorded)."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import frankie_box_s3_transport
    return frankie_box_s3_transport


def _upload(path, sha, size):
    bucket = os.environ.get('OFFLOAD_BUCKET', 'frankie-granite42-568968024170-us-east-1')
    region = os.environ.get('OFFLOAD_REGION', 'us-east-1')
    base = 'host-deliveries/%s/principal-response/cycle-%s' % (os.environ.get('DAY', 'unknown'), os.environ.get('CYCLE', '00'))
    result = dict(bucket=bucket, region=region, uploaded=False)
    try:
        import boto3
        s3 = boto3.client('s3', region_name=region)
        T = _transport()
    except Exception as error:        # noqa: BLE001 - the push never fails on the offload copy
        result['error'] = '%s: %s' % (type(error).__name__, str(error)[:200])
        return result
    errors, attempts = [], []
    # The box role writes host-deliveries/<day>/principal-response/cycle-<NN>/progress/ (heartbeats); the brain-files
    # prefix is tried first, the progress prefix second. The upload is frankie_box_s3_transport.upload (CRT first,
    # 128 MiB parts x 16, classic after it; transport and the fallback reason land on the pointer: Day-1 visibility).
    for key in ('%s/brain-files/%s' % (base, sha), '%s/progress/brain-files/%s' % (base, sha)):
        try:
            try:
                head = s3.head_object(Bucket=bucket, Key=key)
                if head.get('ContentLength') == size and head.get('Metadata', {}).get('sha256') == sha:
                    result.update(key=key, uploaded=True, already_present=True)
                    return result
            except Exception:         # noqa: BLE001 - absent or not readable: upload
                pass
            r = T.upload(str(path), bucket, key, region=region, sha256=sha, extra_args={'Metadata': {'sha256': sha}},
                         client=s3)
            attempts.append({k: r.get(k) for k in ('key', 'status', 'transport', 'transport_fallback', 'seconds',
                                                    'bytes_per_second', 'reason')})
            if r['status'] == 'uploaded':
                result.update(key=key, uploaded=True, transport=r['transport'],
                              transport_fallback=r['transport_fallback'], transport_attempts=attempts)
                return result
            errors.append('%s: %s (%s)' % (key, r.get('reason'), r.get('transport_fallback')))
        except Exception as error:    # noqa: BLE001
            errors.append('%s: %s' % (key, str(error)[:200]))
    result.update(error=' | '.join(errors), transport_attempts=attempts)
    return result


def _pointer(source, target, box_path):
    size = source.stat().st_size
    sha = _sha256(source)
    pointer = dict(schema=SCHEMA, name=target.name, bytes=size, sha256=sha, sha256_basis=_BASIS.get(str(source)),
                   box_path=box_path, **_upload(source, sha, size))
    out = target.with_name(target.name + '.s3.json')
    out.write_text(json.dumps(pointer, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print('offloaded (%d bytes, sha256 %s): %s -> %s; s3 %s' % (
        size, sha[:16], target.name, out.name, 'ok ' + pointer['key'] if pointer['uploaded'] else 'FAILED ' + pointer.get('error', '')))


def _gzip_fits(source, target):
    """<target>.gz of source (deterministic: no name, mtime 0); True if under GIT_MAX, else removed and False."""
    zipped = target.with_name(target.name + '.gz')
    with source.open('rb') as reader, zipped.open('wb') as raw:
        with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as writer:
            shutil.copyfileobj(reader, writer, 16 * 1024 * 1024)
    if zipped.stat().st_size < GIT_MAX:
        print('zipped for git (90 MB or more): %s -> %s %d bytes' % (target.name, zipped.name, zipped.stat().st_size))
        return True
    zipped.unlink()
    return False


def _place(source, target, box_path):
    """Put one file at target in the clone: as is, gzipped, or as an S3 pointer. Stale forms are removed."""
    size = source.stat().st_size
    for stale in (target, target.with_name(target.name + '.gz'), target.with_name(target.name + '.s3.json')):
        if stale != source and (stale.exists() or stale.is_symlink()):
            stale.unlink()
    if size < ZIP_AT:
        shutil.copy2(source, target)
        return
    if size < GZIP_TRY and _gzip_fits(source, target):
        return
    _pointer(source, target, box_path)


def _each(function, jobs):
    """function(*job) for every job, on threads (gzip/zlib, file copies and the S3 upload release the GIL), in walk
    order for errors (Greg, 2026-09-28: every 90 MB..1 GiB brain file was gzipped one after another on each push)."""
    from concurrent.futures import ThreadPoolExecutor
    if len(jobs) < 2:
        return [function(*job) for job in jobs]
    with ThreadPoolExecutor(min(16, len(jobs))) as pool:
        return list(pool.map(lambda job: function(*job), jobs))


def copy(src, dst):
    src, dst = Path(src), Path(dst)
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        _place(src, dst, str(src.resolve()))
        return
    jobs = []
    for base, dirs, names in os.walk(src):
        dirs.sort()
        rel = Path(base).relative_to(src)
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for name in sorted(names):
            path = Path(base) / name
            if path.is_file() and not path.is_symlink():
                jobs.append((path, dst / rel / name, str(path.resolve())))
    _each(_place, jobs)


def _seal_one(path):
    if path.stat().st_size < GZIP_TRY and _gzip_fits(path, path):
        path.unlink()
        return
    _pointer(path, path, None)
    path.unlink()


def seal(dst):
    jobs = []
    for base, _dirs, names in os.walk(dst):
        if '/.git' in base or base.endswith('.git'):
            continue
        for name in sorted(names):
            path = Path(base) / name
            if (path.suffix == '.gz' or name.endswith('.s3.json') or not path.is_file() or path.is_symlink()
                    or path.stat().st_size < ZIP_AT):
                continue
            jobs.append((path,))
    _each(_seal_one, jobs)


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'copy':
        copy(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == 'seal':
        seal(sys.argv[2])
    else:
        raise SystemExit('usage: copy SRC DST | seal DST')
