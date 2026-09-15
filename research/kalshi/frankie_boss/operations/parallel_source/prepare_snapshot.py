"""Create an independent SQLite backup; never mutate the live source journal."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tarfile
import time

ROOT = Path(__file__).parent
SOURCE = ROOT.parent/'source-recovery-resume-20260915'
REPO = Path('C:/Users/A/Documents/Codex/2026-09-14/latest-addendum-host-controls-completed-launch-2/work/Markets-full-frankie')
CODE = '35982ac7d42b546446038866299c23ca4fc50edc'
CHECKPOINT = SOURCE/'checkpoints/000032-cursor-57027.c15.json'
EXPECTED_CHECKPOINT = '750dbb3c63ab672614323dca0dd7f363847ea78aa8a489d0f0b84afe8f00bcf7'
BUNDLE = ROOT/'bundle'

def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())

def progress(phase, **values):
    record = dict(phase=phase, at=time.time(), pid=os.getpid(), **values)
    temporary = ROOT/'snapshot-progress.next.json'
    temporary.write_text(json.dumps(record), encoding='utf-8')
    os.replace(temporary, ROOT/'snapshot-progress.json')

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def main():
    write(ROOT/'snapshot-process.json', dict(pid=os.getpid(), started_at=time.time()))
    if subprocess.check_output(['git','-C',str(REPO),'rev-parse','HEAD'], text=True).strip() != CODE:
        raise ValueError('frozen source code commit changed')
    if sha(CHECKPOINT) != EXPECTED_CHECKPOINT:
        raise ValueError('terminal checkpoint changed')
    witness = json.loads(CHECKPOINT.with_name(CHECKPOINT.name+'.receipt.json').read_bytes())
    if (witness['journal_count'], witness['next_cursor']) != (114054, 57027):
        raise ValueError('terminal checkpoint denominator differs')
    BUNDLE.mkdir(exist_ok=False)
    shutil.copyfile(CHECKPOINT, BUNDLE/'checkpoint.json')
    shutil.copyfile(CHECKPOINT.with_name(CHECKPOINT.name+'.receipt.json'), BUNDLE/'checkpoint-receipt.json')
    origin = ROOT.parent/'source-execution-20260915'
    for name in ('manifest.json','scope.json','extraction-pin.json'):
        shutil.copyfile(origin/name, BUNDLE/name)
    # Preserve raw CRLF code bytes: these are part of C15 implementation identity.
    names = ('c15_builder.py','c15_observer.py','c15_journal.py','c15_registry.py',
        'causal_prefix.py','causal_prefix_records.py','causal_packet.py','mbo_resume_state.py',
        'source_conformance.py','selected_source_scope.py','raw_mbo_source_manifest.py')
    paths = [REPO/'research/kalshi/frankie_boss'/name for name in names]
    paths.append(REPO/'research/ng_exhaustion_mbo_v4_state_adapter_20260820.py')
    code_rows = []
    for path in paths:
        target = BUNDLE/'code'/path.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        code_rows.append(dict(path=target.relative_to(BUNDLE).as_posix(), bytes=target.stat().st_size, sha256=sha(target)))
    write(BUNDLE/'code-manifest.json', dict(code_commit=CODE, files=code_rows))
    progress('sqlite_backup')
    source = sqlite3.connect((SOURCE/'source.sqlite').as_uri()+'?mode=ro', uri=True, timeout=5)
    source.execute('PRAGMA query_only=ON')
    destination = sqlite3.connect(BUNDLE/'source.sqlite')
    last = [0.0]
    def observed(status, remaining, total):
        if time.monotonic()-last[0] >= 5 or remaining == 0:
            progress('sqlite_backup', remaining_pages=remaining, total_pages=total)
            last[0] = time.monotonic()
    try:
        source.backup(destination, pages=4096, progress=observed, sleep=0.05)
        tail = destination.execute('SELECT ordinal,kind,digest FROM entries ORDER BY ordinal DESC LIMIT 1').fetchone()
        if tail != (witness['journal_count']-1, 'APPLIED', witness['journal_hash']):
            raise ValueError('snapshot tail differs from independent checkpoint')
    finally:
        destination.close()
        source.close()
    progress('snapshot_hash')
    files = {}
    for path in sorted(BUNDLE.rglob('*')):
        if path.is_file():
            files[path.relative_to(BUNDLE).as_posix()] = dict(bytes=path.stat().st_size, sha256=sha(path))
    manifest = dict(schema='FRANKIE_PARALLEL_SOURCE_SNAPSHOT_V1', code_commit=CODE,
        checkpoint_sha256=EXPECTED_CHECKPOINT, journal_count=witness['journal_count'],
        journal_hash=witness['journal_hash'], state_hash=witness['state_hash'], files=files,
        capture='SQLite online backup from read-only connection; includes committed WAL',
        source_directory=str(SOURCE), source_worker_preserved=True)
    write(BUNDLE/'bundle-manifest.json', manifest)
    progress('compressing_snapshot')
    archive = ROOT/'source-snapshot.tar.gz'
    with tarfile.open(archive, 'x:gz', compresslevel=1) as output:
        output.add(BUNDLE, arcname='bundle')
    progress('archive_hash', archive_bytes=archive.stat().st_size)
    write(ROOT/'snapshot-ready.json', dict(schema='FRANKIE_PARALLEL_SNAPSHOT_READY_V1',
        archive=str(archive), bytes=archive.stat().st_size, sha256=sha(archive),
        bundle_manifest_sha256=sha(BUNDLE/'bundle-manifest.json'),
        checkpoint_sha256=EXPECTED_CHECKPOINT, journal_count=witness['journal_count'],
        journal_hash=witness['journal_hash'], at=time.time()))
    progress('ready', archive_bytes=archive.stat().st_size)

if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        write(ROOT/'snapshot-failure.json', dict(error_type=type(error).__name__, at=time.time()))
        raise
