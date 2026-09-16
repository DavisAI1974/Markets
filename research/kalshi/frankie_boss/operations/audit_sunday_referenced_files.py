"""Every file the Sunday host will READ must be in the restoration manifest (or its addendum).

Walks the host configuration, the closed-source lineage (each link's recovery receipt), the
19-prefix witness manifest and every witness it names, plus the small files source() opens in the
source directory, and reports every referenced file that no manifest row covers. The third restore
proof on the host (2026-09-16) failed on one such file: the second lineage link's recovery receipt,
729 bytes, which no one had listed.

    python operations/audit_sunday_referenced_files.py --configuration <host configuration json> [--json out]
Exit 1 when anything referenced is uncovered. Reads only; never touches the run directory.
"""
import argparse
import json
import os
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent / 'sunday_20260915_package'
SOURCE_DIRECTORY_FILES = ('completion.json', 'builder-checkpoint.c15.json', 'ingestion-receipt.json',
                          'recovery-receipt.json', 'scope.json')


def _key(path):
    return os.path.normcase(os.path.normpath(str(path)))


def covered_paths(package=PACKAGE):
    """Manifest and addendum rows by path; declared_absent rows are covered by DECLARATION, flagged so."""
    rows = json.loads((package / 'RESTORATION_MANIFEST.json').read_bytes())['files']
    for addendum in sorted(package.glob('RESTORATION_MANIFEST_ADDENDUM_*.json')):
        body = json.loads(addendum.read_bytes())
        rows = rows + body['files'] + [dict(r, declared_absent=True) for r in body.get('declared_absent', [])]
    return {_key(r['original_path']): r for r in rows}


def referenced_files(configuration):
    refs = []

    def walk(value, where):
        if isinstance(value, dict):
            if isinstance(value.get('path'), str):
                refs.append((where, value['path']))
            for key, item in value.items():
                walk(item, where + '.' + key)
        elif isinstance(value, list):
            for index, item in enumerate(value):
                walk(item, f'{where}[{index}]')
        elif isinstance(value, str) and len(value) > 3 and value[1:3] == ':\\':
            refs.append((where, value))

    walk(configuration, 'configuration')
    host = configuration['host_runtime']
    for name in ('source_lineage', 'prefix_manifest'):
        witness = host.get(name)
        if witness and Path(witness['path']).is_file():
            walk(json.loads(Path(witness['path']).read_bytes()), name)
    manifest = host.get('prefix_manifest')
    if manifest and Path(manifest['path']).is_file():
        for entry in json.loads(Path(manifest['path']).read_bytes()).get('witnesses', []):
            if Path(entry['path']).is_file():
                walk(json.loads(Path(entry['path']).read_bytes()), 'prefix_witness:' + Path(entry['path']).name)
    source = Path(configuration['source_directory'])
    for name in SOURCE_DIRECTORY_FILES:
        refs.append(('source_directory', str(source / name)))
    return refs


def audit(configuration, package=PACKAGE):
    covered = covered_paths(package)
    seen, uncovered, declared_absent = set(), [], []
    for where, path in referenced_files(configuration):
        key = _key(path)
        if key in seen:
            continue
        seen.add(key)
        if Path(path).is_dir():
            continue
        row = covered.get(key)
        if row is not None and row.get('declared_absent'):
            declared_absent.append(dict(where=where, path=path, reason=row.get('reason')))
            continue
        if row is not None:
            continue
        present = Path(path).is_file()
        uncovered.append(dict(where=where, path=path, present_here=present,
                              bytes=Path(path).stat().st_size if present else None))
    return dict(schema='FRANKIE_SUNDAY_REFERENCED_FILES_AUDIT_V1', referenced=len(seen),
                covered=len(seen) - len(uncovered) - len(declared_absent), declared_absent=declared_absent,
                uncovered=uncovered, passed=not uncovered)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--json')
    args = parser.parse_args()
    result = audit(json.loads(Path(args.configuration).read_bytes()))
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k != 'uncovered'}))
    for row in result['uncovered']:
        print(json.dumps(row))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
