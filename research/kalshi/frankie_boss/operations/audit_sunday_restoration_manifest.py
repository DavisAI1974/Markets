"""Audit the Sunday restoration manifest for independent hashes of every bulk object.

This is read-only. It does not restore, upload, download or open any market journal.
A bulk file is acceptable only when its exact original path has one unambiguous
64-hex SHA-256 in the manifest, a pinned/secondary witness, or a separately
attested bulk-hash addendum. Path and byte count alone are never sufficient.

The original restoration manifest is immutable evidence. Missing hashes are closed
by an addendum produced from the closed source workstation, never by editing that
manifest in place.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

SHA256 = re.compile(r'[0-9a-f]{64}')
ADDENDUM_SCHEMA = 'FRANKIE_SUNDAY_BULK_HASH_ADDENDUM_V1'


def _digest(value):
    return value if isinstance(value, str) and SHA256.fullmatch(value) else None


def _addendum_hashes(addendum, manifest):
    if addendum is None:
        return {}
    if type(addendum) is not dict or addendum.get('schema') != ADDENDUM_SCHEMA:
        raise ValueError('reviewed Sunday bulk-hash addendum required')
    if addendum.get('manifest_configuration_sha256') != manifest.get('configuration_sha256'):
        raise ValueError('bulk-hash addendum belongs to another restoration manifest')
    rows = addendum.get('files')
    if type(rows) is not list or not rows:
        raise ValueError('bulk-hash addendum files required')
    result = {}
    for row in rows:
        if (type(row) is not dict or type(row.get('path')) is not str
                or type(row.get('bytes')) is not int or row['bytes'] < 0):
            raise ValueError('invalid bulk-hash addendum row')
        digest = _digest(row.get('sha256'))
        if digest is None:
            raise ValueError('bulk-hash addendum requires exact SHA-256')
        if row.get('closed') is not True or row.get('sidecars_absent') is not True:
            raise ValueError('bulk-hash addendum requires closed file and absent SQLite sidecars')
        key = Path(row['path']).as_posix().lower()
        if key in result and result[key] != (row['bytes'], digest):
            raise ValueError('conflicting duplicate bulk-hash addendum row')
        result[key] = (row['bytes'], digest)
    return result


def audit(manifest, addendum=None):
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

    additions = _addendum_hashes(addendum, manifest)
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
        addendum_record = additions.get(path)
        addendum_digest = None
        if addendum_record is not None:
            addendum_bytes, addendum_digest = addendum_record
            if type(row.get('bytes')) is int and addendum_bytes != row['bytes']:
                raise ValueError('bulk-hash addendum byte count differs from manifest')
        candidates = set(witness_digests)
        if row_digest is not None:
            candidates.add(row_digest)
        if addendum_digest is not None:
            candidates.add(addendum_digest)
        record = dict(original_path=row['original_path'], bytes=row.get('bytes'),
            row_sha256=row_digest, witness_sha256s=sorted(witness_digests),
            addendum_sha256=addendum_digest)
        bulk.append(record)
        if not candidates:
            gaps.append(record)
        elif len(candidates) != 1:
            conflicts.append(dict(record, candidate_sha256s=sorted(candidates)))

    bulk_paths = {Path(row['original_path']).as_posix().lower() for row in bulk}
    extras = sorted(path for path in additions if path not in bulk_paths)
    if extras:
        raise ValueError('bulk-hash addendum contains paths outside manifest bulk set')
    expected_bulk = manifest.get('files_bulk')
    if type(expected_bulk) is int and expected_bulk != len(bulk):
        raise ValueError('bulk file count differs from manifest summary')
    return dict(schema='FRANKIE_SUNDAY_RESTORATION_HASH_AUDIT_V2',
        bulk_files=len(bulk),hash_complete=len(bulk)-len(gaps)-len(conflicts),
        addendum_files=len(additions),missing_hashes=gaps,conflicting_hashes=conflicts,
        passed=not gaps and not conflicts)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--bulk-hash-addendum')
    parser.add_argument('--out')
    args=parser.parse_args()
    manifest=json.loads(Path(args.manifest).read_bytes())
    addendum=(json.loads(Path(args.bulk_hash_addendum).read_bytes())
              if args.bulk_hash_addendum else None)
    result=audit(manifest,addendum)
    raw=json.dumps(result,indent=2,sort_keys=True).encode()+b'\n'
    if args.out:
        Path(args.out).write_bytes(raw)
    print(raw.decode(),end='')
    return 0 if result['passed'] else 2


if __name__=='__main__':raise SystemExit(main())
