"""Preserve only prior receipt-listed loose files as Git-sized binary parts.

No archive extraction or frozen database hashing. Deletion is a separate explicit
PowerShell step after --verify-pushed produces the byte-checked candidate list.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'artifacts/recovered-c-drive/20261022'
OUT = BASE / 'git-preserved-local-files-v1'
PART_BYTES = 64 * 1024 * 1024
REMOTE_REF = 'refs/heads/claude/kalshi-s79-kickoff-ij8t9o'


def relative(path):
    resolved = path.resolve()
    assert resolved.is_relative_to(ROOT.resolve()) and resolved != ROOT.resolve()
    return resolved.relative_to(ROOT.resolve()).as_posix()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def prepare():
    receipt = json.loads((BASE / 'relocation-receipt.json').read_text())
    selected = [r for r in receipt['files'] if r['disposition'] in
                ['existing_bytecode_off_C', 'preserved_existing_bulk_archive_off_C_not_new_document']]
    OUT.mkdir(exist_ok=True)
    index = []
    for i, row in enumerate(selected):
        source = ROOT / row['destination']
        assert relative(source) == row['destination'] and source.is_file() and not source.is_symlink()
        stat = source.stat()
        stem = f'{i:02d}-{source.name}'
        parts = []
        with source.open('rb') as handle:
            offset = 0
            while data := handle.read(PART_BYTES):
                path = OUT / f'{stem}.part{len(parts):04d}.bin'
                path.write_bytes(data)
                digest = hashlib.sha256(data).hexdigest()
                assert path.stat().st_size == len(data)
                assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
                parts.append(dict(file=relative(path), offset=offset, bytes=len(data), sha256=digest))
                offset += len(data)
        assert offset == stat.st_size and source.stat().st_mtime_ns == stat.st_mtime_ns
        manifest = dict(original_C_path=row['original_C_path'], prior_loose_path=relative(source),
                        bytes=stat.st_size, prior_loose_mtime_ns=stat.st_mtime_ns, parts=parts,
                        preservation='Concatenate parts in listed order for identical original compressed/file bytes; no extraction or recompression')
        manifest_path = OUT / f'{stem}.manifest.json'
        save(manifest_path, manifest)
        index.append(dict(manifest=relative(manifest_path), prior_loose_path=relative(source),
                          bytes=stat.st_size, part_count=len(parts)))
        print(json.dumps(dict(prepared=source.name, bytes=stat.st_size, parts=len(parts))), flush=True)
    save(OUT / 'index.json', dict(original_receipt='artifacts/recovered-c-drive/20261022/relocation-receipt.json',
                                  files=index, total_bytes=sum(r['bytes'] for r in index),
                                  total_parts=sum(r['part_count'] for r in index),
                                  deletion_status='NOT_DELETED; push and verify first'))


def verify_pushed():
    remote_sha = subprocess.check_output(['git', 'ls-remote', 'origin', REMOTE_REF], cwd=ROOT, text=True).split()[0]
    tracked = set(subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', remote_sha, '--', relative(OUT)],
                                        cwd=ROOT, text=True).splitlines())
    index = json.loads((OUT / 'index.json').read_text())
    assert relative(OUT / 'index.json') in tracked
    for file in [relative(OUT / 'index.json')] + [r['manifest'] for r in index['files']]:
        assert file in tracked
        # Manifests are Git text; honor the checkout's declared CRLF/LF filter.
        # Binary parts below must instead match without any filter.
        local_blob = subprocess.check_output(['git', 'hash-object', '--path=' + file, str(ROOT / file)], cwd=ROOT, text=True).strip()
        remote_blob = subprocess.check_output(['git', 'rev-parse', remote_sha + ':' + file], cwd=ROOT, text=True).strip()
        assert local_blob == remote_blob
    candidates = []
    for entry in index['files']:
        assert entry['manifest'] in tracked
        manifest = json.loads((ROOT / entry['manifest']).read_text())
        source = ROOT / manifest['prior_loose_path']
        assert relative(source) == manifest['prior_loose_path']
        assert source.stat().st_size == manifest['bytes']
        assert source.stat().st_mtime_ns == manifest['prior_loose_mtime_ns']
        offset = 0
        with source.open('rb') as handle:
            for part in manifest['parts']:
                assert part['file'] in tracked and part['offset'] == offset
                path = ROOT / part['file']
                assert relative(path) == part['file']
                data = path.read_bytes()
                assert len(data) == part['bytes'] and hashlib.sha256(data).hexdigest() == part['sha256']
                assert handle.read(part['bytes']) == data
                # Worktree bytes must be the exact Git blob reached by the remote ref.
                local_blob = subprocess.check_output(['git', 'hash-object', '--no-filters', str(path)], cwd=ROOT, text=True).strip()
                remote_blob = subprocess.check_output(['git', 'rev-parse', remote_sha + ':' + part['file']], cwd=ROOT, text=True).strip()
                assert local_blob == remote_blob
                offset += len(data)
            assert handle.read(1) == b'' and offset == manifest['bytes']
        candidates.append(dict(path=relative(source), bytes=offset, manifest=entry['manifest']))
    save(OUT / 'verified-deletion-candidates.json', dict(
        status='ALL_PARTS_AND_MANIFESTS_PUSHED_AND_BYTE_EQUAL_TO_LOOSE_ORIGINALS',
        remote_ref=REMOTE_REF, remote_commit=remote_sha, files=candidates,
        total_bytes=sum(x['bytes'] for x in candidates),
        verification='new part SHA256, Git blob equality to remote-reachable tree, ordered byte comparison with prior loose originals',
        original_frozen_database_rehash=False, original_archives_extracted=False))
    print(json.dumps(dict(remote_commit=remote_sha, verified_files=len(candidates), bytes=sum(x['bytes'] for x in candidates))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'verify-pushed'])
    args = parser.parse_args()
    prepare() if args.action == 'prepare' else verify_pushed()
