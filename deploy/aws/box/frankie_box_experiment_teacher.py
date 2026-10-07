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

Missing coverage (Greg, 2026-10-07): a missing operand blocks only the equation that needs it, never the day. A journal
without the full-book observation, or a day on which no original APPLIED operand reaches the pinned equation, publishes a
receipt with status equation_not_run (exit 5) and no rows file; the export and the search list the Dipole rows missing
and the day goes on. Nothing is invented. Every receipt carries the piece's workflow_report (inputs / use / outputs)
for the one-day inspection reporter (frankie_box_workflow_inspection.py).
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


def _publish(out, result):
    """The step's receipt, complete or not at all; then the directory entry is durable."""
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


def workflow_report(result, *, receipt_path, rc, external, market, equation, workers, exit_code):
    """The piece's inputs / use / outputs record for the one-day review (Greg, 2026-10-07; schema shared with the
    adviser pieces so frankie_box_workflow_inspection projects it). Inputs: the sealed journal and its receipt, the
    day file, the shared ROOT identity. Use: which operands entered the pinned R3 equation (the original APPLIED
    payloads of the contiguous adapter-cursor prefix), every instant listed without that operand, the external section
    state, the whole-day context. Outputs: the rows file, the attachment, this receipt, the exit code. A row in the
    rows file is the teacher's measured output; it is not proof that the classroom or the search consumed it."""
    identity = result.get('shared_market_identity')
    read = result.get('shared_market_read') or {}
    return dict(schema='FRANKIE_PIECE_WORKFLOW_REPORT_V1', piece='teacher',
                inputs=dict(day=result['day'],
                            ingestion_receipt=dict(path=str(receipt_path), sha256=result['ingestion_receipt']['sha256']),
                            journal=dict(path=str(Path(receipt_path).parent / rc['journal_file']), bytes=rc['journal_bytes'],
                                         sha256=rc['journal_sha256'], journal_count=rc['journal_count'],
                                         record_count=rc['record_count'], observation_mode=rc.get('observation_mode'),
                                         source_binding='BOSS_BLOCK_INGESTION_RECEIPT_V1 of this trading day, bytes and '
                                                        'sha256 checked before the walk'),
                            day_file={k: external.get(k) for k in ('path', 'sha256', 'found', 'status', 'reason') if k in external},
                            entity=result.get('entity'),
                            calculations=(identity or {}).get('calculations'),
                            shared_market_picture=(None if identity is None else dict(
                                identity=identity, read_complete=read.get('complete'),
                                coverage=read.get('coverage'), basis='SharedMarketTimeline.iter_applied over the same '
                                                                    'sealed journal; complete means source exhaustion only')),
                            shared_market_dispositions=(None if identity is None else dict(
                                arithmetic=read.get('arithmetic'), journal=read.get('journal'),
                                integrity_failure=read.get('integrity_failure'), stopped=read.get('stopped'))),
                            experiment_directive=(result.get('experiment_directive') or {}).get('sha256'),
                            workers=workers),
                use=dict(equation='the pinned JournalTeacherR3 row pass (c15_teacher_r3 + teacher_changes), unchanged: '
                                  'original APPLIED payloads with every adapter cursor from zero, the whole day as context',
                         operands_entered=(dict(rows=equation['rows'], through_applied_cursor=equation['through_applied_cursor'])
                                           if equation is not None else dict(rows=result.get('rows'), basis='parallel journal prefix')),
                         instants_without_operand=(dict(count=len(equation['absent']), ended_at=equation['ended_at'],
                                                        listed_in='shared_market_arithmetic.absent')
                                                   if equation is not None else None),
                         thinner_picture=(dict(absent_layers=(read.get('coverage') or {}).get('absent_layers'),
                                               rule=read.get('completeness')) if read else None),
                         external_section=external.get('status'),
                         through_cursor=result.get('through_cursor'), as_of=result.get('as_of'),
                         skipped=result.get('equation_not_run'),
                         walk_seconds=result.get('walk_seconds'), phase_timings=result.get('phase_timings'),
                         sealed_journal_verification=dict(
                             teacher='bytes and sha256 measured here against the ingestion receipt (phase verify_sealed_journal)',
                             shared_reader=read.get('input_verification') if read else None,
                             rule='one full hash per process; the compact reader still verifies the chained head hash on read'),
                         model_calls=0),
                outputs=dict(status=result.get('status', 'rows_published'), exit_code=exit_code,
                             rows_file=result.get('rows_file'), attachment_file=result.get('attachment_file'),
                             rows=result.get('rows'), entity_rows=result.get('entity_rows'),
                             external_section=external, receipt='receipt.json in the same directory',
                             brain='filed by the orchestrator beside this receipt (teacher-knowledge.json -> <brain>/<day>-teacher) '
                                   'before the classroom; recorded there, not here',
                             waits=[]),
                rule='recorded inputs, use and outputs of this piece for the one-day review; a measured row is not proof '
                     'of downstream consumption; missing evidence means unknown, never zero')


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
    # Where the time goes (Greg, 2026-10-07: keep the instrumentation that shows it): seconds per phase of this
    # step, recorded in the receipt as phase_timings. Diagnostic only; never an identity, never a gate.
    phases, phase_started = {}, [time.time()]
    def phase(name):
        now = time.time()
        phases[name] = round(phases.get(name, 0.0) + now - phase_started[0], 3)
        phase_started[0] = now
    if _sha256(receipt_path) != receipt_sha256:
        raise SystemExit('the ingestion receipt differs from the sha256 given')
    phase('verify_ingestion_receipt')
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
    # A journal written without the full-book observation (observation none) carries no operand for this equation;
    # the day is not refused: the step publishes an equation_not_run receipt below, after the retained-receipt checks.
    journal = receipt_path.parent / rc['journal_file']
    journal_witness = dict(bytes=journal.stat().st_size, sha256=_sha256(journal))
    if journal_witness != dict(bytes=rc['journal_bytes'], sha256=rc['journal_sha256']):
        raise SystemExit('the sealed journal differs from its ingestion receipt')
    phase('verify_sealed_journal')
    market = None
    if calculations is not None or shared_market_policy is not None:
        from frankie_box_market_timeline import SCHEMA, SharedMarketTimeline
        if calculations is None or shared_market_policy != SCHEMA:
            raise ValueError('shared teacher requires calculations and its exact versioned policy together')
        # The witness just measured is handed to the shared reader so the sealed journal (tens of GB on a big day)
        # is not hashed a second time in this process; the reader re-reads it itself if the witness differs.
        market = SharedMarketTimeline(calculations, day=day, workers=workers, input_witness=journal_witness)
        phase('open_shared_picture')
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
    # A retained equation_not_run receipt (no rows file) is not a duplicate publication: the walk is attempted
    # again below; the same source gives the same explicit result, a repaired source may now carry the operand.
    if (out / ROWS_FILE).exists():
        status = (retained_receipt or {}).get('external_section', {}).get('status')
        retry_publication = retained_receipt is None or status in ('failed', 'refused')
        if not retry_publication:
            raise SystemExit('%s already holds the Dipole rows of %s (duplicate data declines)' % (out, day))
        if not ((out / 'teacher-raw-state.pkl').is_file() and
                (out / 'teacher-attachment-state.pkl').is_file()):
            raise ValueError('teacher publication is incomplete without its saved calculation state; preserved')
    out.mkdir(parents=True, exist_ok=True)
    phase('retained_receipt_checks')
    if rc.get('observation_mode') == 'none':
        # Greg, 2026-10-07: a missing operand blocks only the equation that needs it, never the day. The teacher
        # reads the full-book observation; this journal has none, so the Dipole rows are not computed and the day
        # goes on without them (the export and the search list them missing). Nothing is invented.
        reason = ('this journal was written without the full-book observation (observation none); the teacher reads the '
                  'observation, so its equation has no operand on this day; observation_replay would have to be wired '
                  'into the walk first (listed, not run)')
        result = dict(schema='FRANKIE_EXPERIMENT_TEACHER_ROWS_V1', day=day, status='equation_not_run',
                      equation_not_run=dict(reason=reason, operand='full-book observation', rows=0),
                      ingestion_receipt=dict(path=str(receipt_path), sha256=receipt_sha256), rows=0, processed=0,
                      entity_rows=0, through_cursor=rc['record_count'] - 1, model_calls=0, phase_timings=phases,
                      external_section=dict(external, listed='no external section built: the rows it aligns to were not computed'),
                      experiment_directive=directive_witness(),
                      shared_market_identity=market.identity if market is not None else None,
                      shared_market_read=None,
                      shared_market_use=('not read here: the walk that consumes the shared picture did not run; every other '
                                         'consumer opens the same ROOT with its own reader') if market is not None else None)
        if learner_binding is not None:
            result.update(learner_binding=learner_binding, evidence_seat='frankie', independent_scientific_verification=False)
        result['workflow_report'] = workflow_report(result, receipt_path=receipt_path, rc=rc, external=external, market=market,
                                                    equation=None, workers=workers, exit_code=5)
        _publish(out, result)
        print(json.dumps(result, sort_keys=True), flush=True)
        return 5
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
    phase('first_input_entity')
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
    shared_read = None
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
        phase('raw_pass_rows')
        if not rows:
            # No original APPLIED operand reached the equation on the whole day (every INPUT failed, unpaired or
            # unreadable, or the adapter-cursor prefix ended at zero). The pinned PT.finish requires a nonempty
            # complete prefix; that is the equation's refusal, not the day's. The shared read, with every instant
            # listed, is retained in shared-market-state.pkl; the receipt below says so and the day goes on.
            equation_not_run = dict(reason='no original APPLIED operand on the whole day; the pinned equation (PT.finish) '
                                           'requires a nonempty complete prefix, so no Dipole row is computed or invented',
                                    operand='original APPLIED payload (contiguous adapter-cursor prefix)', rows=0,
                                    processed=processed)
        else:
            equation_not_run = None
            as_of = max(r[4] for r in rows)
            if learner_binding is not None and as_of != bound:
                raise ValueError('learner reading does not end at its requested whole-day cutoff')
            spec = [(cursor, True, h) for cursor, h in sorted(hashes.items())]
            attachment = PT.finish(teacher, rows, processed, hashes, spec, source_manifest_hash=rc['manifest_hash'],
                                   recovery_path=out / 'teacher-attachment-state.pkl',
                                   save_requested=save_requested)
            phase('finish_attachment')
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
            phase('close_walk')
    if equation_not_run is not None:
        result = dict(schema='FRANKIE_EXPERIMENT_TEACHER_ROWS_V1', day=day, status='equation_not_run',
                      equation_not_run=equation_not_run, entity=list(entity),
                      ingestion_receipt=dict(path=str(receipt_path), sha256=receipt_sha256), rows=0, processed=processed,
                      entity_rows=0, through_cursor=through, walk_seconds=round(walked, 1),
                      seconds=round(time.time() - started, 1), model_calls=0, experiment_directive=directive_witness(),
                      phase_timings=phases,
                      external_section=dict(external, listed='no external section built: the rows it aligns to were not computed'))
        if market is not None:
            result.update(shared_market_identity=market.identity, shared_market_read=shared_read,
                          shared_market_arithmetic=shared_read.get('equation'),
                          shared_market_use='full picture read and every instant listed (shared_market_arithmetic); the '
                                            'existing equation had no operand, so no row was computed or invented')
        if learner_binding is not None:
            result.update(learner_binding=learner_binding, evidence_seat='frankie', independent_scientific_verification=False)
        result['workflow_report'] = workflow_report(result, receipt_path=receipt_path, rc=rc, external=external, market=market,
                                                    equation=(shared_read or {}).get('equation') if market is not None else None,
                                                    workers=workers, exit_code=5)
        _publish(out, result)
        print(json.dumps(result, sort_keys=True), flush=True)
        return 5
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
    phase('snapshot_rows_attachment')
    result = dict(schema='FRANKIE_EXPERIMENT_TEACHER_ROWS_V1', day=day, request_id=request_id, entity=list(entity),
                  ingestion_receipt=dict(path=str(receipt_path), sha256=receipt_sha256), rows=len(rows), processed=processed,
                  entity_rows=len(hashes), as_of=as_of, through_cursor=through, walk_seconds=round(walked, 1),
                  seconds=round(time.time() - started, 1), rows_file=dict(file=ROWS_FILE, sha256=_sha256(out / ROWS_FILE)),
                  attachment_file=dict(file='teacher-attachment.pkl', sha256=_sha256(out / 'teacher-attachment.pkl')),
                  model_calls=0, caveat='whole-day context: the exact-row check in finish compares the rows with themselves',
                  experiment_directive=directive_witness(), phase_timings=phases)
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
        phase('external_section')
    result['external_section'] = external
    result['status'] = 'rows_published'
    result['workflow_report'] = workflow_report(result, receipt_path=receipt_path, rc=rc, external=external, market=market,
                                                equation=(shared_read or {}).get('equation') if market is not None else None,
                                                workers=workers, exit_code=code)
    _publish(out, result)
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
