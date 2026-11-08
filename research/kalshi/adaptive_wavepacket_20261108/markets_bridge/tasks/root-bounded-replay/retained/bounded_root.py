import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

code = Path(__file__).resolve().parent
sys.path[:0] = [str(code), str(code / 'deploy/aws/box'), str(code / 'research/kalshi')]

def main():
    p = argparse.ArgumentParser()
    p.add_argument('day')
    p.add_argument('output', type=Path)
    p.add_argument('--prepare', action='store_true')
    p.add_argument('--save', action='store_true')
    p.add_argument('--native', action='store_true')
    p.add_argument('--variant', choices=('baseline','candidate'), default='baseline')
    args = p.parse_args()
    work = args.output.resolve()
    journal = code / f'{args.day}.sqlite'
    from research.kalshi.frankie_boss.c15_journal import EvidenceJournal
    from research.kalshi.frankie_boss.parallel_teacher import TeacherSaved
    from research.kalshi.frankie_boss.mbo_source import MboSourcePin, runtime_hash

    def sha(path):
        with path.open('rb') as f:
            return hashlib.file_digest(f, 'sha256').hexdigest()

    if args.prepare:
        manifest = json.loads((code / f'{args.day}-input-receipt.json').read_bytes())
        source = code / f'{args.day}-input.jsonl'
        assert sha(source) == manifest['sha256']
        db = EvidenceJournal(journal, create=True)
        dbn_pin = MboSourcePin(3, runtime_hash())
        for line in source.open('rb'):
            record = json.loads(line)
            record['dbn_wire_bytes'] = base64.b64decode(record.pop('dbn_wire_b64'), validate=True)
            assert record['dbn_length'] * 4 == len(record['dbn_wire_bytes'])
            record['dbn_extraction_hash'] = dbn_pin.digest
            db.append('INPUT', {'observation': record})
        assert db.count == manifest['rows']
        print(json.dumps(dict(records=db.count, head=db.head_hash, journal_sha256=sha(journal))))
        db.close()
        raise SystemExit

    os.environ['FRANKIE_BOX_ROOT'] = str(work / 'box')
    os.environ['FRANKIE_ROOT_LAYER_SPOOLS'] = 'reference'
    import frankie_box_boss_session as root
    root.PRODUCERS = code / (('producers' if args.native else 'root-producers') +
                             ('-candidate' if args.variant == 'candidate' else ''))
    if args.native:
        # Keep the ROOT process separate from this benchmark's Native producer revision.
        os.environ['FRANKIE_ROOT_NATIVE_OVERLAP'] = 'off'
    session = root.Session(work, args.day, '00', 'offline-prefix')
    session.requested_data_workers = len(os.sched_getaffinity(0)) - 1
    pin_path = code / 'research/kalshi/frankie_boss/knowledge/CYCLE_CALCULATION_PINS.json'
    pin = dict(next(x for x in json.loads(pin_path.read_bytes())['pins'] if 0 in x['cycles']))
    pin['cycle_index'] = 0
    pin['bedrock_layers'] = [layer for entry in pin.get('bedrock', []) for layer in entry['registry_layers']]
    pin['pins_witness'] = dict(path=str(pin_path), bytes=pin_path.stat().st_size, sha256=sha(pin_path))
    session._pin = lambda: pin
    from types import SimpleNamespace
    db = EvidenceJournal(journal)
    container = dict(path=str(journal), bytes=journal.stat().st_size, sha256=sha(journal))
    source = SimpleNamespace(container=container)
    manifest = json.loads((code / f'{args.day}-input-receipt.json').read_bytes())
    source_witness = dict(tape=manifest['source'], prefix_rows=manifest['rows'], prefix_sha256=manifest['sha256'])
    pin['source_binding'] = source_witness
    session.source_binding = dict(container=container, journal_count=db.count, journal_hash=db.head_hash,
                                  record_count=manifest['rows'], source=source_witness)
    db.close()
    if args.native:
        session.source_binding.update(day=args.day)
    calls = 0
    def stop():
        nonlocal calls
        if not args.save or not (session.work / 'derived/.rows/structures.jsonl').exists():
            return False
        calls += 1
        return calls == session.source_binding['journal_count'] // 2

    try:
        receipt = session.derive(source=source, retain_frame_sections=True, bedrock=args.native,
                                 digest=False, recovery=True, save_requested=stop,
                                 bedrock_off_cause={'kind':'caller_override'})
    except TeacherSaved as exc:
        if not args.save:
            raise
        print(exc, flush=True)
        raise SystemExit
    assert not args.save
    if receipt['failure_count']:
        raise RuntimeError(f"Producer returned {receipt['failure_count']} failures")
    result = dict(input_records=receipt['input_records'], frames=receipt['f_last_groups'],
                  retained=receipt['root_processes'], files={})
    for path in sorted((session.work / 'derived/.rows').glob('*.jsonl')):
        if path.name.startswith('input-'):
            continue
        result['files'][path.name] = dict(bytes=path.stat().st_size, sha256=sha(path))
    (work / 'spool-comparison.json').write_text(json.dumps(result,indent=2))
    print(result, flush=True)

if __name__ == '__main__':
    main()
