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


def _sha256(path):
    """sha256 of a file, cached by (device, inode, size, mtime) so repeated pushes of the same file hash it once."""
    info = path.stat()
    tag = '%d-%d-%d-%d' % (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)
    cached = CACHE / (tag + '.json')
    try:
        return json.loads(cached.read_text())['sha256']
    except (OSError, ValueError, KeyError):
        pass
    with path.open('rb') as handle:
        digest = hashlib.file_digest(handle, 'sha256').hexdigest()
    if path.stat().st_mtime_ns != info.st_mtime_ns or path.stat().st_size != info.st_size:
        raise ValueError('file changed while hashing: %s' % path)
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(dict(path=str(path), sha256=digest)))
    except OSError:
        pass
    return digest


def _upload(path, sha, size):
    bucket = os.environ.get('OFFLOAD_BUCKET', 'frankie-granite42-568968024170-us-east-1')
    region = os.environ.get('OFFLOAD_REGION', 'us-east-1')
    base = 'host-deliveries/%s/principal-response/cycle-%s' % (os.environ.get('DAY', 'unknown'), os.environ.get('CYCLE', '00'))
    result = dict(bucket=bucket, region=region, uploaded=False)
    try:
        import boto3
        from boto3.s3.transfer import TransferConfig
        s3 = boto3.client('s3', region_name=region)
    except Exception as error:        # noqa: BLE001 - the push never fails on the offload copy
        result['error'] = '%s: %s' % (type(error).__name__, str(error)[:200])
        return result
    errors = []
    # The box role writes host-deliveries/<day>/principal-response/cycle-<NN>/progress/ (heartbeats); the brain-files
    # prefix is tried first, the progress prefix second.
    for key in ('%s/brain-files/%s' % (base, sha), '%s/progress/brain-files/%s' % (base, sha)):
        try:
            try:
                head = s3.head_object(Bucket=bucket, Key=key)
                if head.get('ContentLength') == size and head.get('Metadata', {}).get('sha256') == sha:
                    result.update(key=key, uploaded=True, already_present=True)
                    return result
            except Exception:         # noqa: BLE001 - absent or not readable: upload
                pass
            s3.upload_file(str(path), bucket, key, ExtraArgs={'Metadata': {'sha256': sha}},
                           Config=TransferConfig(multipart_chunksize=128 * 1024 * 1024, max_concurrency=16))
            result.update(key=key, uploaded=True)
            return result
        except Exception as error:    # noqa: BLE001
            errors.append('%s: %s' % (key, str(error)[:200]))
    result['error'] = ' | '.join(errors)
    return result


def _pointer(source, target, box_path):
    size = source.stat().st_size
    sha = _sha256(source)
    pointer = dict(schema=SCHEMA, name=target.name, bytes=size, sha256=sha, box_path=box_path, **_upload(source, sha, size))
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


def copy(src, dst):
    src, dst = Path(src), Path(dst)
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        _place(src, dst, str(src.resolve()))
        return
    for base, dirs, names in os.walk(src):
        dirs.sort()
        rel = Path(base).relative_to(src)
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for name in sorted(names):
            path = Path(base) / name
            if path.is_file() and not path.is_symlink():
                _place(path, dst / rel / name, str(path.resolve()))


def seal(dst):
    for base, _dirs, names in os.walk(dst):
        if '/.git' in base or base.endswith('.git'):
            continue
        for name in sorted(names):
            path = Path(base) / name
            if (path.suffix == '.gz' or name.endswith('.s3.json') or not path.is_file() or path.is_symlink()
                    or path.stat().st_size < ZIP_AT):
                continue
            if path.stat().st_size < GZIP_TRY and _gzip_fits(path, path):
                path.unlink()
                continue
            _pointer(path, path, None)
            path.unlink()


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == 'copy':
        copy(sys.argv[2], sys.argv[3])
    elif len(sys.argv) == 3 and sys.argv[1] == 'seal':
        seal(sys.argv[2])
    else:
        raise SystemExit('usage: copy SRC DST | seal DST')
