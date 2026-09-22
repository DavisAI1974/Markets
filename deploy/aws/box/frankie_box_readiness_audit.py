"""Read-only box evidence audit. No keys, process signals, source writes or replay."""
import hashlib
import json
import os
from pathlib import Path
import sqlite3

ROOT = Path('/opt/frankie-box')
WORK = ROOT / 'work' / 'ingest-20211004-ingest-1790057801'


def emit(kind, value):
    print(json.dumps(dict(audit=kind, value=value), sort_keys=True), flush=True)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    processes = {}
    for path in Path('/proc').glob('[0-9]*'):
        try:
            args = (path / 'cmdline').read_bytes().split(b'\0')
            stat = (path / 'stat').read_text().rsplit(')', 1)[1].split()
            processes[int(path.name)] = dict(parent=int(stat[1]), cpu_ticks=int(stat[11])+int(stat[12]),
                ingest=any(arg.endswith(b'/operations/ingest_block_sources.py') for arg in args),
                helper=any(b'multiprocessing.spawn' in arg for arg in args))
        except (OSError, ValueError, IndexError):
            pass
    roots = {pid for pid, p in processes.items() if p['ingest']}
    descendants = set(roots)
    while True:
        extra = {pid for pid, p in processes.items() if p['parent'] in descendants} - descendants
        if not extra:
            break
        descendants.update(extra)
    emit('processes', dict(logical_cpus=os.cpu_count(), ingest_pids=sorted(roots),
         ingest_tree={pid: processes[pid] for pid in sorted(descendants)},
         remaining_multiprocessing_helpers=[pid for pid, p in processes.items() if p['helper']]))
    progress = WORK / 'progress.jsonl'
    last = {}
    if progress.is_file():
        with progress.open() as handle:
            for line in handle:
                try:
                    event = json.loads(line)
                    last[event.get('phase', 'unknown')] = event
                except json.JSONDecodeError:
                    pass
    emit('last_progress_by_phase', last)
    journal = WORK / 'journal.compact.sqlite'
    if journal.is_file():
        with sqlite3.connect(journal.resolve().as_uri() + '?mode=ro', uri=True) as db:
            db.execute('PRAGMA query_only=ON')
            rows = db.execute('SELECT count(*),sum(count),min(count),max(count),sum(length(body)),max(length(body)) FROM blocks').fetchone()
            seal = db.execute('SELECT format,count,head FROM seal').fetchall()
        emit('compact_container', dict(path=str(journal), file_bytes=journal.stat().st_size,
            boxes=rows[0], journal_rows=rows[1], min_rows_per_box=rows[2], max_rows_per_box=rows[3],
            body_bytes=rows[4], max_body_bytes=rows[5], seal=seal,
            completion_present=(WORK/'completion.json').is_file(),
            ingestion_receipt_present=(WORK/'ingestion-receipt.json').is_file()))
    for manifest_path in sorted((ROOT / 'brain').glob('*/MANIFEST.json')):
        body = json.loads(manifest_path.read_bytes())
        entries = []
        for entry in body.get('entries', []):
            name = entry.get('name', '')
            path = manifest_path.parent / name
            if path.resolve().parent != manifest_path.parent.resolve():
                entries.append(dict(name=name, refused='not an immediate brain member'))
                continue
            exists = path.is_file()
            entries.append(dict(name=name, include=entry.get('include'), exists=exists,
                bytes=path.stat().st_size if exists else None,
                hash_matches=sha(path)==entry.get('sha256') if exists else False))
        emit('brain_manifest', dict(path=str(manifest_path), schema=body.get('schema'), cycle=body.get('cycle'),
            sha256=sha(manifest_path), entries=entries,
            selected_by_existing_earlier_cycle_gate_for_cycle_zero=False if manifest_path.parent.name.startswith('cycle-') else None))
    request_path = ROOT / 'request' / 'session-request.json'
    if request_path.is_file():
        request = json.loads(request_path.read_bytes())
        contract = request.get('attachment', {}).get('feedback_contract', {})
        sessions = [x.get('session', {}) for x in contract.get('sessions', [])]
        emit('retained_request', dict(path=str(request_path), sha256=sha(request_path), request_id=request.get('request_id'),
            cycle_index=contract.get('cycle_index'), trading_day=contract.get('trading_day'),
            contract_sha256=contract.get('contract_sha256'),
            sessions=[{k: x.get(k) for k in ('session_id','prior_close','opening','event_cutoff_ns','receive_cutoff_ns')} for x in sessions]))
    for path in sorted((ROOT / 'receipts').glob('friday-anchor-*.json')):
        body = json.loads(path.read_bytes())
        emit('friday_anchor_receipt', dict(path=str(path), sha256=sha(path),
            fields={k: v for k,v in body.items() if k in
                ('anchor','halt_ns','instrument_id','zstd_frames','decoded_sha256','file','records','trades','rule')}))
    for path in (ROOT/'session'/'work'/'verify.json', ROOT/'session'/'work'/'reading.json'):
        if path.is_file():
            body = json.loads(path.read_bytes())
            emit('retained_session_receipt', dict(path=str(path), sha256=sha(path),
                fields={k:v for k,v in body.items() if k in
                    ('schema','request_id','request_sha256','cycle_index','session_id','brain_members','corpus_identity')}))


if __name__ == '__main__':
    main()
