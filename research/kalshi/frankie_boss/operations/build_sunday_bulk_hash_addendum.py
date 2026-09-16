"""Generate a bulk-hash addendum for unhashed Sunday restoration objects.

Run only on the source workstation that holds the reviewed closed files. The
original restoration manifest is never edited. For every result-bearing bulk row
that lacks a SHA-256 in both its row and pinned/secondary witnesses, this script:

1. requires the original path to exist as a regular file;
2. requires SQLite sidecars (-wal, -shm, -journal) to be absent;
3. records size/mtime;
4. computes SHA-256 twice from independent full-file reads;
5. rechecks size/mtime and sidecars;
6. refuses any movement or digest disagreement.

The resulting JSON is evidence for restoration only; it performs no upload and
opens no SQLite connection.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import time

SHA256 = re.compile(r'[0-9a-f]{64}')
SCHEMA = 'FRANKIE_SUNDAY_BULK_HASH_ADDENDUM_V1'


def sha256(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(16*1024*1024),b''):
            digest.update(block)
    return digest.hexdigest()


def _known_hashes(manifest):
    result={}
    for collection in ('pinned_files','secondary_pins'):
        for row in manifest.get(collection,[]):
            value=row.get('sha256') if isinstance(row,dict) else None
            path=row.get('path') if isinstance(row,dict) else None
            if isinstance(path,str) and isinstance(value,str) and SHA256.fullmatch(value):
                result.setdefault(Path(path).as_posix().lower(),set()).add(value)
    return result


def _sidecars(path):
    return [Path(str(path)+suffix) for suffix in ('-wal','-shm','-journal')]


def build(manifest):
    if type(manifest) is not dict or manifest.get('schema')!='FRANKIE_SUNDAY_RESTORATION_MANIFEST_V1':
        raise ValueError('reviewed Sunday restoration manifest required')
    known=_known_hashes(manifest)
    missing=[]
    for row in manifest.get('files',[]):
        if type(row) is not dict or row.get('in_git') is not False:
            continue
        path=row.get('original_path');value=row.get('sha256')
        if type(path) is not str:
            raise ValueError('bulk row path required')
        key=Path(path).as_posix().lower()
        row_hash=value if isinstance(value,str) and SHA256.fullmatch(value) else None
        if row_hash is None and not known.get(key):
            missing.append(row)
    if not missing:
        raise ValueError('manifest has no bulk hash gaps to close')

    rows=[]
    for row in missing:
        path=Path(row['original_path'])
        if not path.is_file():
            raise FileNotFoundError('missing bulk source file: '+str(path))
        sidecars=_sidecars(path)
        if any(item.exists() for item in sidecars):
            raise RuntimeError('SQLite sidecar exists; source must be closed: '+str(path))
        before=path.stat()
        if type(row.get('bytes')) is int and before.st_size!=row['bytes']:
            raise RuntimeError('bulk source byte count differs from manifest: '+str(path))
        first=sha256(path)
        if any(item.exists() for item in sidecars):
            raise RuntimeError('SQLite sidecar appeared during first hash: '+str(path))
        middle=path.stat()
        second=sha256(path)
        after=path.stat()
        if any(item.exists() for item in sidecars):
            raise RuntimeError('SQLite sidecar appeared during verification: '+str(path))
        if first!=second:
            raise RuntimeError('bulk source changed between independent SHA-256 reads: '+str(path))
        identity=lambda stat:(stat.st_size,stat.st_mtime_ns)
        if identity(before)!=identity(middle) or identity(before)!=identity(after):
            raise RuntimeError('bulk source metadata changed during verification: '+str(path))
        rows.append(dict(path=str(path),bytes=before.st_size,sha256=first,
            closed=True,sidecars_absent=True,verified_full_reads=2,
            mtime_ns=before.st_mtime_ns))

    return dict(schema=SCHEMA,
        manifest_configuration_sha256=manifest['configuration_sha256'],
        manifest_content_sha256=None,files=rows,
        generated_unix_ns=time.time_ns(),generator_pid=os.getpid())


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--out',required=True)
    args=parser.parse_args()
    manifest_path=Path(args.manifest)
    raw=manifest_path.read_bytes();manifest=json.loads(raw)
    result=build(manifest)
    result['manifest_content_sha256']=hashlib.sha256(raw).hexdigest()
    encoded=json.dumps(result,indent=2,sort_keys=True).encode()+b'\n'
    out=Path(args.out)
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('xb') as stream:
        stream.write(encoded);stream.flush();os.fsync(stream.fileno())
    print(json.dumps(dict(schema=SCHEMA,files=len(result['files']),out=str(out),
        addendum_sha256=hashlib.sha256(encoded).hexdigest())))
    return 0


if __name__=='__main__':raise SystemExit(main())
