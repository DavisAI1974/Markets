"""Audit the Sunday restoration manifest for independent hashes of every bulk object.

This is read-only. It does not restore, upload, download or open any market journal.
A bulk file is acceptable only when its exact original path has a 64-hex SHA-256
in either the file row itself or an independently recorded pinned/secondary witness.
Path and byte count alone are never sufficient for result-bearing restoration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

SHA256 = re.compile(r'[0-9a-f]{64}')


def _digest(value):
    return value if isinstance(value, str) and SHA256.fullmatch(value) else None


def audit(manifest):
    if type(manifest) is not dict or manifest.get('schema') != 'FRANKIE_SUNDAY_RESTORATION_MANIFEST_V1':
        raise ValueError('reviewed Sunday restoration manifest required')
    files = manifest.get('files')
    if type(files) is not list:
        raise ValueError('restoration manifest files list required')

    independent = {}
    for collection in ('pinned_files', 'secondary_pins'):
        rows = manifest.get(collection, [])
        if type(rows) is not list:
            raise ValueError(collection+' must be a list')
        for row in rows:
            if type(row) is not dict or type(row.get('path')) is not str:
                raise ValueError('invalid '+collection+' row')
            digest = _digest(row.get('sha256'))
            if digest is not None:
                independent.setdefault(Path(row['path']).as_posix().lower(), set()).add(digest)

    bulk = []
    gaps = []
    conflicts = []
    for row in files:
        if type(row) is not dict or type(row.get('original_path')) is not str or type(row.get('in_git')) is not bool:
            raise ValueError('invalid restoration file row')
        if row['in_git']:
            continue
        path = Path(row['original_path']).as_posix().lower()
        row_digest = _digest(row.get('sha256'))
        witness_digests = independent.get(path, set())
        candidates = set(witness_digests)
        if row_digest is not None:
            candidates.add(row_digest)
        record = dict(original_path=row['original_path'], bytes=row.get('bytes'),
            row_sha256=row_digest, witness_sha256s=sorted(witness_digests))
        bulk.append(record)
        if not candidates:
            gaps.append(record)
        elif len(candidates) != 1:
            conflicts.append(dict(record, candidate_sha256s=sorted(candidates)))

    expected_bulk = manifest.get('files_bulk')
    if type(expected_bulk) is int and expected_bulk != len(bulk):
        raise ValueError('bulk file count differs from manifest summary')
    return dict(schema='FRANKIE_SUNDAY_RESTORATION_HASH_AUDIT_V1',
        bulk_files=len(bulk),hash_complete=len(bulk)-len(gaps)-len(conflicts),
        missing_hashes=gaps,conflicting_hashes=conflicts,
        passed=not gaps and not conflicts)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--out')
    args=parser.parse_args()
    result=audit(json.loads(Path(args.manifest).read_bytes()))
    raw=json.dumps(result,indent=2,sort_keys=True).encode()+b'\n'
    if args.out:
        Path(args.out).write_bytes(raw)
    print(raw.decode(),end='')
    return 0 if result['passed'] else 2


if __name__=='__main__':raise SystemExit(main())
