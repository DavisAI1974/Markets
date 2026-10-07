"""The teacher-only step: the Dipole teacher's rows for ONE day, without a launch (research/kalshi/frankie_boss/
TEACHER_ONLY_CALL_MAP_20260929.md; SPEC-experiment-orchestrator.md "The teacher's Dipole rows: 1 day in 5"; Greg,
2026-09-29: the classroom arm runs on days 1 and 2 and needs these rows the same night).

The same calls the launch makes, in the pattern concurrent_teacher._run already uses (a teacher-only process): the day's
sealed journal read in place (its bytes and sha256 checked against its ingestion receipt), the parallel journal prefix,
JournalTeacherR3 with the teacher changes (all levels, the whole day, unknown trades carried), row_pass, finish with the
whole day as the context, then dipole_classroom.snapshot_teacher_attachment and sunday_execution._save. No model, no Pod,
no Granite. Greg authorized save/restore-only teacher hooks on 2026-10-06; calculation definitions remain unchanged.
The entity is the day's own instrument (the first INPUT record's publisher and instrument; the launch hard-coded the
2021-10 front month 111313), with the NG tick 0.001 = 1,000,000 raw. The walk cache is a per-day scratch directory, never
inside the sealed ingest.
Writes /opt/frankie-box/work/experiment-teacher-rows/<day>/: host-dipole-classroom-source.c15.json (the rows the search
and the classroom read), teacher-attachment.pkl (the attachment the classroom package is built from), receipt.json.
A day whose rows exist declines (duplicate data). Caveat kept from the call map: with the whole day as the context the
exact-row check in finish compares the rows with themselves.

Frankie's historical data points (Greg, 2026-09-29; research/kalshi/frankie_boss/dipole_classroom_external.py): the day
file (FRANKIE_DAY_EXTERNAL_V1) is read the same way every reader of the ingest reads it: given as --day-external +
--day-external-sha256 (checked BEFORE the walk; a mismatch is refused), or taken from beside the sealed ingest (its
day-external-receipt.json sha256 must match the bytes). After the rows, the BOSS teacher's external section is built once
into <out>/external-section/ (the rows' as-of alignment, the facts of every point, the pairs in the classroom's shapes)
through operations/frankie_day_external.AsOfReader at the rows' cutoff. No day file beside the ingest: listed in the
receipt, the rows stand (the classroom V2 builds the section when the file is there). A file beside the ingest that
differs from its receipt, or a section that fails, is listed in the receipt; the rows stand and the step exits 4.
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



def directive_witness():
    """The experiment's directive (Greg, 2026-09-29), named in this step's record: what the run is shooting for.
    research/kalshi/frankie_boss/knowledge/EXPERIMENT_DIRECTIVE_V1.json, whole text in the receipt."""
    path = Path(__file__).resolve().parents[3] / 'research/kalshi/frankie_boss/knowledge/EXPERIMENT_DIRECTIVE_V1.json'
    data = path.read_bytes()
    return dict(path=str(path), sha256=hashlib.sha256(data).hexdigest(), directive=json.loads(data))

def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(64 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def teach(day, receipt_path, receipt_sha256, workers, day_external=None, day_external_sha256=None,
          *, calculations=None, shared_market_policy=None):
    # Keep the cooperative handler through publication too: an orderly stop must not
    # leave a completed attachment without its rows/external section/completion receipt.
    import signal
    requested = [False]
    def request_save(*_):
        requested[0] = True
    def save_requested():
        stop_file = os.environ.get('FRANKIE_LANE_STOP_FILE')
        return requested[0] or bool(stop_file and Path(stop_file).exists())
    previous_signal = signal.signal(signal.SIGTERM, request_save)
    try:
        return _teach(day, receipt_path, receipt_sha256, workers, day_external,
                      day_external_sha256, save_requested=save_requested, calculations=calculations,
                      shared_market_policy=shared_market_policy)
    finally:
        signal.signal(signal.SIGTERM, previous_signal)


def _teach(day, receipt_path, receipt_sha256, workers, day_external=None, day_external_sha256=None,
           *, save_requested, learner_binding=None, learner_directory=None,
           calculations=None, shared_market_policy=None):
    receipt_path = Path(receipt_path)
    if _sha256(receipt_path) != receipt_sha256:
        raise SystemExit('the ingestion receipt differs from the sha256 given')
    from research.kalshi.frankie_boss import dipole_classroom_external as EXT
    try:
        day_file, day_sha, day_source = EXT.resolve_day_file(day_external, day_external_sha256, receipt_path)
    except EXT.DayExternalRefused as error:
        if day_external is not None:
            raise SystemExit('the day file of the historical data points: %s' % error)
        day_file = None
        external = dict(status='absent', reason=str(error),
                        listed='no external section built here; the classroom V2 builds it when the day file is there')
    if day_file is not None:
        if _sha256(day_file) != day_sha:
            if day_external is not None:
                raise SystemExit('the day file %s differs from the sha256 %s given; refused' % (day_file, day_sha))
            external = dict(status='refused', path=str(day_file), sha256_expected=day_sha,
                            reason='the day file beside the ingest differs from its day-external-receipt.json sha256')
        else:
            external = dict(path=str(day_file), sha256=day_sha, found=day_source)
    rc = json.loads(receipt_path.read_bytes())
    if rc.get('schema') != 'BOSS_BLOCK_INGESTION_RECEIPT_V1' or rc.get('writer') != 'compact' or rc.get('trading_day') != day:
        raise SystemExit('a compact BOSS_BLOCK_INGESTION_RECEIPT_V1 of trading day %s is required' % day)
    if rc.get('observation_mode') == 'none':
        raise SystemExit('this journal was written without the full-book observation (observation none); the teacher reads '
                         'the observation, so this day needs observation_replay wired into the walk first (listed, not run)')
    journal = receipt_path.parent / rc['journal_file']
    if journal.stat().st_size != rc['journal_bytes'] or _sha256(journal) != rc['journal_sha256']:
        raise SystemExit('the sealed journal differs from its ingestion receipt')
    market = None
    if calculations is not None or shared_market_policy is not None:
        from frankie_box_market_timeline import SCHEMA, SharedMarketTimeline
        if calculations is None or shared_market_policy != SCHEMA:
            raise ValueError('shared teacher requires calculations and its exact versioned policy together')
        market = SharedMarketTimeline(calculations, day=day, workers=workers)
        if (market.source['ingestion_receipt']['sha256'] != receipt_sha256
                or market.input_pin['sha256'] != rc['journal_sha256']):
            raise ValueError('teacher and shared picture have different sealed evidence')
        shared_external = market.source.get('external') or {}
        if ((shared_external.get('sha256') if shared_external.get('status') == 'attached' else None)
                != external.get('sha256')):
            raise ValueError('teacher and shared picture have different external publications')
    out = OUT / day
    if learner_binding is not None:
        # The learner owns a separate calculation and recovery namespace. It may reuse the
        # measurement functions, never the host's completed measurements or walk state.
        if learner_directory is None or Path(learner_directory).resolve() == out.resolve():
            raise ValueError('learner reading requires its own output directory')
        if (learner_binding['through_cursor'] != rc['record_count'] - 1 or
                learner_binding['source_hash'] != rc['source_prefix_hash']):
            raise ValueError('learner binding does not name this complete sealed day')
        out = Path(learner_directory)
    retained_receipt_path = out / 'receipt.json'
    retained_receipt = (json.loads(retained_receipt_path.read_bytes())
                        if retained_receipt_path.exists() else None)
    if retained_receipt is not None:
        if (retained_receipt.get('schema') != 'FRANKIE_EXPERIMENT_TEACHER_ROWS_V1' or
                retained_receipt.get('day') != day or
                retained_receipt.get('learner_binding') != learner_binding or
                retained_receipt.get('shared_market_identity') != (market.identity if market else None) or
                retained_receipt.get('ingestion_receipt', {}).get('sha256') != receipt_sha256):
            raise ValueError('retained teacher receipt belongs to another day or ingestion; preserved')
        old_external = retained_receipt.get('external_section', {})
        old_sha = old_external.get('sha256') or old_external.get('sha256_expected')
        current_sha = external.get('sha256') or external.get('sha256_expected')
        if old_sha is not None and old_sha != current_sha:
            raise ValueError('retained teacher external input identity changed; preserved')
    if (out / ROWS_FILE).exists():
        status = (retained_receipt or {}).get('external_section', {}).get('status')
        retry_publication = retained_receipt is None or status in ('failed', 'refused')
        if not retry_publication:
            raise SystemExit('%s already holds the Dipole rows of %s (duplicate data declines)' % (out, day))
        if not ((out / 'teacher-raw-state.pkl').is_file() and
                (out / 'teacher-attachment-state.pkl').is_file()):
            raise ValueError('teacher publication is incomplete without its saved calculation state; preserved')
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
    bound = (learner_binding['as_of'] if learner_binding is not None else int(time.time() * 1e9))
    PJ._SERIAL = CS.journal_prefix
    PJ._ENTITY[0] = entity
    h0 = T.evidence_hash
    T.evidence_hash = PJ._chain_hash_factory(h0)
    TC.apply()
    evidence = None
    market_state = out / 'shared-market-state.pkl'
    # The pinned R3 equation's operands are the original APPLIED payloads with every adapter
    # cursor from zero (c15_teacher_r3.iter_raw). It runs on exactly that prefix. An instant
    # without its operand (failed, unpaired, unreadable, or past a cursor gap) is listed here
    # with its ordinal; it is not skipped silently, not given an invented row, and it never
    # removes the instant from the shared picture other consumers read.
    equation = dict(rows=0, through_applied_cursor=None, absent=[], ended_at=None,
                    rule='existing equation on its original contiguous operands only; no derived substitute')
    def shared_evidence():
        pictures = market.iter_applied()
        expected = 0
        try:
            for item in pictures:
                at = item['picture']['at']
                if item['arithmetic']['status'] != 'present':
                    equation['absent'].append(dict(input_journal_ordinal=at['input_journal_ordinal'],
                                                   adapter_cursor=at['adapter_cursor'], input_cursor=at['input_cursor'],
                                                   reason=item['arithmetic']['reason']))
                    continue
                if equation['ended_at'] is not None:
                    equation['absent'].append(dict(input_journal_ordinal=at['input_journal_ordinal'],
                                                   adapter_cursor=at['adapter_cursor'], input_cursor=at['input_cursor'],
                                                   reason='after_equation_prefix_end'))
                    continue
                if item['evidence'].get('cursor') != expected:
                    # The pinned equation would refuse here ('complete prefix requires every cursor
                    # from zero'). Its prefix ends; the reader keeps presenting every later instant.
                    equation['ended_at'] = dict(input_journal_ordinal=at['input_journal_ordinal'],
                                                adapter_cursor=at['adapter_cursor'], expected_adapter_cursor=expected,
                                                reason='adapter cursor gap before this APPLIED; the equation needs every cursor from zero')
                    equation['absent'].append(dict(input_journal_ordinal=at['input_journal_ordinal'],
                                                   adapter_cursor=at['adapter_cursor'], input_cursor=at['input_cursor'],
                                                   reason='after_equation_prefix_end'))
                    continue
                expected += 1
                equation['rows'] += 1
                equation['through_applied_cursor'] = item['evidence']['cursor']
                # Both existing equations see the identical richer current input.
                # Their raw argument/hash and numerical formulas remain unchanged.
                teacher.market_picture = item['picture']
                teacher.control.market_picture = item['picture']
                teacher.raw_teacher.market_picture = item['picture']
                yield item['evidence']
        finally:
            pictures.close()
            PT._save_raw_state(market_state, dict(market.report, equation=dict(equation)))
    try:
        evidence = shared_evidence() if market else PJ.parallel_journal_prefix(builder, through, None)
        rows, processed, hashes = PT.row_pass(teacher, evidence, as_of=bound, source_manifest_hash=rc['manifest_hash'],
            recovery_path=out / 'teacher-raw-state.pkl',
            recovery_identity=dict(receipt_sha256=receipt_sha256, journal_sha256=rc['journal_sha256'],
                                   journal_count=rc['journal_count'], journal_hash=rc['journal_hash'], through=through,
                                   **({'learner_binding': learner_binding} if learner_binding is not None else {}),
                                   **({'shared_market_identity': market.identity} if market is not None else {})),
            save_requested=save_requested, retain_dstate=True)
        if market is not None:
            # A completed raw recovery may reuse its saved read. Never describe an
            # unstarted current iterator as a fresh complete evidence delivery.
            shared_read = PT._load_raw_state(market_state) if market_state.exists() else None
            if not shared_read or shared_read.get('identity') != market.identity or not shared_read.get('complete'):
                raise ValueError('completed teacher raw state lacks its matching complete shared read; preserved')
        if save_requested():
            raise PT.TeacherSaved('teacher raw pass saved; attachment assembly has not started')
        walked = time.time() - started
        as_of = max(r[4] for r in rows)
        if learner_binding is not None and as_of != bound:
            raise ValueError('learner reading does not end at its requested whole-day cutoff')
        spec = [(cursor, True, h) for cursor, h in sorted(hashes.items())]
        attachment = PT.finish(teacher, rows, processed, hashes, spec, source_manifest_hash=rc['manifest_hash'],
                               recovery_path=out / 'teacher-attachment-state.pkl',
                               save_requested=save_requested)
    finally:
        try:
            # Closing a paused walk drains already submitted block workers and their
            # existing durable caches before the journal reader/process is released.
            if evidence is not None:
                evidence.close()
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
    attachment_path = out / 'teacher-attachment.pkl'
    body = dict(attachment=attachment, request_id=request_id, source_hash=rc['source_prefix_hash'], as_of=as_of,
                through_cursor=through, entity=entity)
    if attachment_path.exists():
        with attachment_path.open('rb') as f:
            retained = pickle.load(f)
        if any(retained[key] != body[key] for key in body if key != 'attachment') or \
                DC.snapshot_teacher_attachment(retained['attachment'], request_id=request_id, cycle_index=0,
                    cycle_count=1, source_hash=rc['source_prefix_hash'], as_of=as_of, through_cursor=through) != source:
            raise ValueError('retained teacher attachment differs; publication preserved for recovery')
    else:
        temporary = attachment_path.with_name(attachment_path.name + '.pending')
        with temporary.open('wb') as f:
            pickle.dump(body, f, protocol=pickle.HIGHEST_PROTOCOL)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, attachment_path)
    SE._save(out / ROWS_FILE, source)
    result = dict(schema='FRANKIE_EXPERIMENT_TEACHER_ROWS_V1', day=day, request_id=request_id, entity=list(entity),
                  ingestion_receipt=dict(path=str(receipt_path), sha256=receipt_sha256), rows=len(rows), processed=processed,
                  entity_rows=len(hashes), as_of=as_of, through_cursor=through, walk_seconds=round(walked, 1),
                  seconds=round(time.time() - started, 1), rows_file=dict(file=ROWS_FILE, sha256=_sha256(out / ROWS_FILE)),
                  attachment_file=dict(file='teacher-attachment.pkl', sha256=_sha256(out / 'teacher-attachment.pkl')),
                  model_calls=0, caveat='whole-day context: the exact-row check in finish compares the rows with themselves',
                  experiment_directive=directive_witness())
    if market is not None:
        result.update(shared_market_identity=market.identity, shared_market_read=shared_read,
                      shared_market_arithmetic=shared_read.get('equation'),
                      shared_market_use='full current picture exposed to both raw teachers at every computed row; existing '
                                        'equations use original APPLIED fields on their contiguous prefix; instants without '
                                        'that operand are listed in shared_market_arithmetic, never invented or dropped '
                                        'from the shared picture; shared_market_read.complete means source exhaustion only')
    if learner_binding is not None:
        result.update(learner_binding=learner_binding, evidence_seat='frankie',
                      independent_scientific_verification=False)
    code = 4 if external.get('status') == 'refused' else 0
    if learner_binding is None and external.get('status') not in ('absent', 'refused'):
        try:
            key, section = EXT.ensure_external_section(out, source, external['path'], external['sha256'], trading_day=day,
                                                       built_by='teacher-only step')
            external.update(status='built' if not section['reused'] else 'reused', section=section)
        except Exception as error:                 # listed; the rows stand; the classroom V2 refuses with the same error
            external.update(status='failed', error='%s: %s' % (type(error).__name__, error))
            code = 4
    result['external_section'] = external
    temporary = out / 'receipt.json.pending'
    with temporary.open('w') as f:
        json.dump(result, f, indent=1, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, out / 'receipt.json')
    directory_fd = os.open(out, os.O_RDONLY)
    try:
        os.fsync(directory_fd)
    finally:
        os.close(directory_fd)
    print(json.dumps(result, sort_keys=True), flush=True)
    return code


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--day', required=True)
    p.add_argument('--ingestion-receipt', required=True)
    p.add_argument('--ingestion-receipt-sha256', required=True)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--day-external', help='the day file (FRANKIE_DAY_EXTERNAL_V1); default: beside the sealed ingest')
    p.add_argument('--day-external-sha256', help='its sha256 (given together with --day-external; a mismatch is refused)')
    p.add_argument('--calculations', help='owner-local ROOT of the same sealed source')
    p.add_argument('--shared-market-policy', choices=['FRANKIE_SHARED_MARKET_TIMELINE_V1'])
    a = p.parse_args()
    if (a.day_external is None) != (a.day_external_sha256 is None):
        p.error('--day-external and --day-external-sha256 are given together')
    return teach(a.day, a.ingestion_receipt, a.ingestion_receipt_sha256, a.workers, a.day_external, a.day_external_sha256,
                 calculations=a.calculations, shared_market_policy=a.shared_market_policy)


if __name__ == '__main__':
    sys.exit(main())
