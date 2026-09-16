"""Hash-pinned inventory and small-file package of the lawful 2026-09-15 Sunday configuration.

Reads the actual host configuration, follows every path witness (path + sha256) including the
secondary pins inside the prefix manifest and the retained-recovery witness, recomputes every
hash on disk, and copies the small files into the repository under a mirrored layout. Bulk
files (journals, snapshots, checkpoints, the 29 MB calculation result) are hashed and listed
for object storage, never committed. Nothing under E: or C: is written.

Restoration is checked by hash, not by eye: a restored tree is lawful only when every entry
in RESTORATION_MANIFEST.json matches. Usage (Windows workstation that holds the E: runtime):
    python research/kalshi/frankie_boss/operations/sunday_restoration_package.py
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

CONFIGURATION = Path('E:/Codex/Frankie-BOSS-20260915/sunday-launch-20260915/actual-host-final-configuration.json')
RUNTIME = Path('E:/Codex/Frankie-BOSS-20260915')
ROOT = Path(__file__).resolve().parents[1] / 'sunday_20260915_package'
# Short mirror roots: Windows git refuses paths over 260 characters without core.longpaths.
MIRROR = {RUNTIME.as_posix(): 'FB', 'C:/Users/A/Documents/Codex': 'C_Codex'}
TOP_LIMIT, DIR_LIMIT, HASH_LIMIT = 8_000_000, 2_000_000, 1_500_000_000
LAWFUL_COMMIT = '050c5056c3657a954d6a3ee17f3a216999930768'
LAWFUL_BRANCH = 'codex/sunday-runtime-grid-fix-20260915'


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(1 << 22), b''):
            digest.update(chunk)
    return digest.hexdigest()


def is_path(value):
    return isinstance(value, str) and len(value) > 2 and value[1] == ':' and value[2] in ('/', chr(92))


def witnesses(value, key, pinned, dirs, scalars):
    if isinstance(value, dict) and 'path' in value and 'sha256' in value:
        pinned.append(dict(key=key, **{k: value[k] for k in ('path', 'sha256', 'bytes') if k in value}))
    elif isinstance(value, dict):
        for name, item in value.items():
            witnesses(item, key + '/' + name, pinned, dirs, scalars)
    elif is_path(value):
        dirs.append(dict(key=key, path=value))
    else:
        scalars[key] = value


def mirror(path):
    posix = Path(path).as_posix()
    for prefix, short in MIRROR.items():
        if posix.startswith(prefix + '/'):
            return ROOT / short / posix[len(prefix) + 1:]
    raise ValueError('path outside the known runtime roots: ' + posix)


def main():
    configuration = json.loads(CONFIGURATION.read_bytes())
    pinned, dirs, scalars = [], [], {}
    witnesses(configuration, '', pinned, dirs, scalars)
    for row in pinned:
        path = Path(row['path'])
        row['exists'] = path.is_file()
        if row['exists']:
            row['bytes_on_disk'] = path.stat().st_size
            row['sha256_on_disk'] = sha256(path) if row['bytes_on_disk'] <= HASH_LIMIT else None
            row['matches_pin'] = (row['sha256_on_disk'] == row['sha256']) if row['sha256_on_disk'] else 'deferred'
    secondary = []
    for name in ('/host_runtime/prefix_manifest', '/host_runtime/retained_preparation_recovery'):
        row = next(r for r in pinned if r['key'] == name)
        inner_pins = []
        witnesses(json.loads(Path(row['path']).read_bytes()), '', inner_pins, [], {})
        for pin in inner_pins:
            path = Path(pin['path'])
            pin.update(via=name, exists=path.is_file())
            if pin['exists'] and path.stat().st_size <= HASH_LIMIT:
                pin['matches_pin'] = sha256(path) == pin['sha256']
            secondary.append(pin)
    mismatches = [r for r in pinned + secondary if r.get('matches_pin') is False]
    if mismatches:
        raise SystemExit('pin mismatch on disk: ' + json.dumps(mismatches))
    by_key = {d['key']: Path(d['path']) for d in dirs}
    for row in dirs:
        path = Path(row['path'])
        row['kind'] = 'dir' if path.is_dir() else ('file' if path.is_file() else 'missing')
        if path.is_dir():
            files = [f for f in path.rglob('*') if f.is_file()]
            row['file_count'], row['total_bytes'] = len(files), sum(f.stat().st_size for f in files)
    wanted = {CONFIGURATION: 'configuration'}
    for row in pinned + secondary:
        path = Path(row['path'])
        if path.is_file():
            wanted[path] = 'pinned' if path.stat().st_size <= TOP_LIMIT else 'pinned-bulk'
    for key, limit, skip in (('/host_runtime/prefixes_directory', DIR_LIMIT, ()), ('/schedule_directory', DIR_LIMIT, ()),
                             ('/host_runtime/tokenizer_directory', TOP_LIMIT, ()), ('/run_directory', DIR_LIMIT, ()),
                             ('/source_directory', DIR_LIMIT, ('checkpoints', 'progress'))):
        for f in by_key[key].rglob('*'):
            if f.is_file() and not any(part in skip for part in f.relative_to(by_key[key]).parts):
                wanted.setdefault(f, 'directory-input' if f.stat().st_size <= limit else 'directory-bulk')
    for extra in (RUNTIME / 'closed-source-lineage-20260915', RUNTIME / 'source-execution-20260915' / 'actual-first-cutoff-capacity'):
        for f in extra.rglob('*'):
            if f.is_file():
                wanted.setdefault(f, 'lineage' if f.stat().st_size <= DIR_LIMIT else 'lineage-bulk')
    if ROOT.exists():
        shutil.rmtree(ROOT)
    rows, copied = [], 0
    for source, reason in sorted(wanted.items()):
        size, target, in_git = source.stat().st_size, mirror(source), not reason.endswith('bulk')
        row = dict(original_path=source.as_posix(), bytes=size, reason=reason, in_git=in_git,
                   git_path=target.relative_to(ROOT.parents[3]).as_posix() if in_git else None,
                   sha256=sha256(source) if (in_git or size <= HASH_LIMIT) else None)
        if in_git:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            if sha256(target) != row['sha256']:
                raise SystemExit('copy differs from source: ' + row['original_path'])
            copied += size
        rows.append(row)
    manifest = dict(schema='FRANKIE_SUNDAY_RESTORATION_MANIFEST_V1', configuration=CONFIGURATION.as_posix(),
                    configuration_sha256=sha256(CONFIGURATION), mirror_roots=MIRROR,
                    lawful_boss_commit=LAWFUL_COMMIT, lawful_boss_branch=LAWFUL_BRANCH, run_id=scalars.get('/run_id'),
                    files_in_git=sum(r['in_git'] for r in rows), bytes_in_git=copied,
                    files_bulk=sum(not r['in_git'] for r in rows), bytes_bulk=sum(r['bytes'] for r in rows if not r['in_git']),
                    pinned_files=pinned, secondary_pins=secondary, directory_inputs=dirs, scalars=scalars, files=rows)
    (ROOT / 'RESTORATION_MANIFEST.json').write_bytes(json.dumps(manifest, indent=1, sort_keys=True, default=str).encode())
    print(json.dumps({k: manifest[k] for k in ('files_in_git', 'bytes_in_git', 'files_bulk', 'bytes_bulk')}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
