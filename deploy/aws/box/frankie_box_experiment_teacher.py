"""The teacher-only step: the Dipole teacher's rows for ONE day, without a launch (research/kalshi/frankie_boss/
TEACHER_ONLY_CALL_MAP_20260929.md; SPEC-experiment-orchestrator.md "The teacher's Dipole rows: 1 day in 5"; Greg,
2026-09-29: the classroom arm runs on days 1 and 2 and needs these rows the same night).

The same calls the launch makes, in the pattern concurrent_teacher._run already uses (a teacher-only process): the day's
sealed journal read in place (its bytes and sha256 checked against its ingestion receipt), the parallel journal prefix,
JournalTeacherR3 with the teacher changes (all levels, the whole day, unknown trades carried), row_pass, finish with the
whole day as the context, then dipole_classroom.snapshot_teacher_attachment and sunday_execution._save. No model, no Pod,
no Granite; nothing pinned is edited (context_session, c15_teacher_r3, the normalizers and teacher_changes are called).
The entity is the day's own instrument (the first INPUT record's publisher and instrument; the launch hard-coded the
2021-10 front month 111313), with the NG tick 0.001 = 1,000,000 raw. The walk cache is a per-day scratch directory, never
inside the sealed ingest.
Writes /opt/frankie-box/work/experiment-teacher-rows/<day>/: host-dipole-classroom-source.c15.json (the rows the search
and the classroom read), teacher-attachment.pkl (the attachment the classroom package is built from), receipt.json.
A day whose rows exist declines (duplicate data). Caveat kept from the call map: with the whole day as the context the
exact-row check in finish compares the rows with themselves.
"""
import argparse
import hashlib
import json
import os
import pickle
import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
OUT = Path('/opt/frankie-box/work/experiment-teacher-rows')
ROWS_FILE = 'host-dipole-classroom-source.c15.json'
NG_TICK_RAW = 1_000_000            # NG tick 0.001 in the DBN fixed-point price (1e-9)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(64 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def teach(day, receipt_path, receipt_sha256, workers):
    receipt_path = Path(receipt_path)
    if _sha256(receipt_path) != receipt_sha256:
        raise SystemExit('the ingestion receipt differs from the sha256 given')
    rc = json.loads(receipt_path.read_bytes())
    if rc.get('schema') != 'BOSS_BLOCK_INGESTION_RECEIPT_V1' or rc.get('writer') != 'compact' or rc.get('trading_day') != day:
        raise SystemExit('a compact BOSS_BLOCK_INGESTION_RECEIPT_V1 of trading day %s is required' % day)
    if rc.get('observation_mode') == 'none':
        raise SystemExit('this journal was written without the full-book observation (observation none); the teacher reads '
                         'the observation, so this day needs observation_replay wired into the walk first (listed, not run)')
    journal = receipt_path.parent / rc['journal_file']
    if journal.stat().st_size != rc['journal_bytes'] or _sha256(journal) != rc['journal_sha256']:
        raise SystemExit('the sealed journal differs from its ingestion receipt')
    out = OUT / day
    if (out / ROWS_FILE).exists():
        raise SystemExit('%s already holds the Dipole rows of %s (duplicate data declines)' % (out, day))
    out.mkdir(parents=True, exist_ok=True)
    os.environ['FRANKIE_WALK_CACHE'] = str(out / 'walk-cache')       # never inside the sealed ingest directory
    os.environ.setdefault('FRANKIE_TEACHER_CHANGES', '1')

    from research.kalshi.frankie_boss import parallel_journal as PJ, context_session as CS, c15_teacher_r3 as T
    from research.kalshi.frankie_boss import parallel_teacher as PT, teacher_changes as TC, dipole_classroom as DC
    from research.kalshi.frankie_boss import sunday_execution as SE
    from research.kalshi.frankie_boss.c15_normalizer_r3 import IdentityNormalizerR3
    from research.kalshi.frankie_boss.frankie_journal_reader import FrankieCompactReader
    from research.kalshi.frankie_boss.compact_journal import CompactReader
    from research.kalshi.frankie_boss.c15_journal import unpack

    # the day's own entity: the first INPUT record's (publisher, instrument)
    entity = None
    with CompactReader(journal, expected_count=rc['journal_count'], expected_head_hash=rc['journal_hash']) as first_reader:
        for ordinal, kind, body, digest in first_reader.rows():
            if kind == 'INPUT':
                record = unpack(json.loads(body))['payload']['record']
                entity = (int(record['publisher_id']), int(record['instrument_id']))
                break
    if entity is None:
        raise SystemExit('the journal holds no INPUT record')
    started = time.time()
    TC.install_binding()
    teacher = T.JournalTeacherR3({entity[1]: NG_TICK_RAW}, normalizer=IdentityNormalizerR3((entity[1],)))
    reader = FrankieCompactReader(journal, expected_count=rc['journal_count'], expected_head_hash=rc['journal_hash'],
                                  workers=workers)
    builder = SimpleNamespace(journal=reader, _failed=False, chain=SimpleNamespace(next_cursor=rc['record_count']))
    through = rc['record_count'] - 1
    bound = int(time.time() * 1e9)                   # as_of in row_pass is only an upper bound; the day's max is taken below
    PJ._SERIAL = CS.journal_prefix
    PJ._ENTITY[0] = entity
    h0 = T.evidence_hash
    T.evidence_hash = PJ._chain_hash_factory(h0)
    TC.apply()
    try:
        evidence = PJ.parallel_journal_prefix(builder, through, None)
        rows, processed, hashes = PT.row_pass(teacher, evidence, as_of=bound, source_manifest_hash=rc['manifest_hash'])
        walked = time.time() - started
        as_of = max(r[4] for r in rows)
        spec = [(cursor, True, h) for cursor, h in sorted(hashes.items())]
        attachment = PT.finish(teacher, rows, processed, hashes, spec, source_manifest_hash=rc['manifest_hash'])
    finally:
        TC.restore()
        T.evidence_hash = h0
        PJ._ENTITY[0] = None
        PJ._CANONICAL.clear()
        PJ._SUBSETS.clear()
        reader.close()
    request_id = 'experiment-%s-cycle-00' % day
    source = DC.snapshot_teacher_attachment(attachment, request_id=request_id, cycle_index=0, cycle_count=1,
                                            source_hash=rc['source_prefix_hash'], as_of=as_of, through_cursor=through)
    with (out / 'teacher-attachment.pkl').open('xb') as f:
        pickle.dump(dict(attachment=attachment, request_id=request_id, source_hash=rc['source_prefix_hash'], as_of=as_of,
                         through_cursor=through, entity=entity), f, protocol=pickle.HIGHEST_PROTOCOL)
    SE._save(out / ROWS_FILE, source)
    result = dict(schema='FRANKIE_EXPERIMENT_TEACHER_ROWS_V1', day=day, request_id=request_id, entity=list(entity),
                  ingestion_receipt=dict(path=str(receipt_path), sha256=receipt_sha256), rows=len(rows), processed=processed,
                  entity_rows=len(hashes), as_of=as_of, through_cursor=through, walk_seconds=round(walked, 1),
                  seconds=round(time.time() - started, 1), rows_file=dict(file=ROWS_FILE, sha256=_sha256(out / ROWS_FILE)),
                  attachment_file=dict(file='teacher-attachment.pkl', sha256=_sha256(out / 'teacher-attachment.pkl')),
                  model_calls=0, caveat='whole-day context: the exact-row check in finish compares the rows with themselves')
    (out / 'receipt.json').write_text(json.dumps(result, indent=1, sort_keys=True))
    print(json.dumps(result, sort_keys=True), flush=True)
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--day', required=True)
    p.add_argument('--ingestion-receipt', required=True)
    p.add_argument('--ingestion-receipt-sha256', required=True)
    p.add_argument('--workers', type=int, default=8)
    a = p.parse_args()
    return teach(a.day, a.ingestion_receipt, a.ingestion_receipt_sha256, a.workers)


if __name__ == '__main__':
    sys.exit(main())
