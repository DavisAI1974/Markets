"""Frankie's own sealed-day reading for SOCRATIC/VERIFY, before host grading.

Reuses the pinned measurement mathematics, with separate learner state and cache.
This supplies evidence for accumulated-knowledge recognition, not an independent
scientific verification of the same code on the same bytes. No host answers enter.

Missing-coverage rule (Greg, 2026-10-07): this reader adds no coverage gate of its own.
Every refusal below is an identity, integrity, lane or cutoff mismatch, named as such.
Which layers and inputs the shared read held is reported beside its source exhaustion in
the witness (`coverage`), never used to reject the day. Which input dispositions the
walk's equations can calculate on is the core teacher's (`frankie_box_experiment_teacher`,
`SharedMarketTimeline.iter_applied`) boundary, not decided here.
"""
import hashlib
import json
import os
import pickle
from pathlib import Path

COVERAGE_ABSENT = 'FRANKIE_CLASSROOM_COVERAGE_V1/no_shared_read'


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def producer_hashes():
    root = Path(__file__).resolve().parents[3]
    paths = ['deploy/aws/box/frankie_box_classroom_reader.py',
             'deploy/aws/box/frankie_box_classroom_code.py',
             'deploy/aws/box/frankie_box_experiment_teacher.py',
             'deploy/aws/box/frankie_box_market_timeline.py']
    paths += ['research/kalshi/frankie_boss/' + name + '.py' for name in (
        'parallel_teacher', 'parallel_journal', 'teacher_changes', 'c15_teacher_r3',
        'c15_teacher', 'c15_normalizer_r3', 'c15_normalizer', 'dipole_target',
        'frankie_journal_reader', 'compact_journal', 'c15_journal', 'dipole_classroom')]
    return {p: sha256(root / p) for p in paths}


def _teacher_walk(teacher_rows, teacher_body, *, day, ingest, own, shared_policy):
    """(receipt, receipt path) of the host teacher's completed walk when it IS the walk this learner reading would make
    (Greg, 2026-10-09: one pass; a SOCRATIC/VERIFY day reads the source once): same day, same sealed ingestion receipt,
    the shared market read when the ROOT carries the policy, rows published (no equation_not_run), the attachment body
    in hand whose sha256 the classroom checked against this receipt, and the learner binding's as_of / through_cursor /
    source_hash equal to the walk's (as_of only bounds the evidence, `future teacher evidence`; it never enters a value,
    so the attachment the learner walk would compute is this one). Else None (the learner walks the day itself)."""
    if teacher_rows is None or not isinstance(teacher_body, dict) or 'attachment' not in teacher_body:
        return None
    path = Path(teacher_rows) / 'receipt.json'
    try:
        receipt = json.loads(path.read_bytes())
    except (OSError, ValueError):
        return None
    if (receipt.get('schema') != 'FRANKIE_EXPERIMENT_TEACHER_ROWS_V1' or receipt.get('day') != day
            or receipt.get('learner_binding') is not None or receipt.get('status') != 'rows_published'
            or receipt.get('equation_not_run') or (receipt.get('ingestion_receipt') or {}).get('sha256') != ingest['sha256']
            or receipt.get('as_of') != own['as_of'] or receipt.get('through_cursor') != own['through_cursor']
            or teacher_body.get('as_of') != own['as_of'] or teacher_body.get('through_cursor') != own['through_cursor']
            or teacher_body.get('source_hash') != own['source_hash']
            or (shared_policy and receipt.get('shared_market_read') is None)):
        return None
    return receipt, path


def read_day(day, calculations, binding, *, day_file, day_sha256, save_requested, teacher_rows=None,
             teacher_body=None):
    """Use ROOT's sealed source descriptor; never accept a teacher snapshot/key/path.

    One pass (Greg, 2026-10-09: "shares the ONE pass and makes no walk of its own"): when the host teacher's completed
    walk is the walk this reading would make (_teacher_walk), the learner snapshot is built from that walk's attachment
    under the learner binding (the same pinned function, DC.snapshot_teacher_attachment, the walk path applies to its
    own attachment); the teacher KEY and the host answers are never read. Otherwise the learner walks the day itself."""
    import frankie_box_experiment_teacher as T
    from research.kalshi.frankie_boss import dipole_classroom as DC
    from research.kalshi.frankie_boss.parallel_teacher import _save_raw_state, _load_raw_state

    calculations = Path(calculations)
    root_receipt = json.loads((calculations / 'calculations-receipt.json').read_bytes())
    source_path = calculations / 'source-binding.json'
    if root_receipt.get('day') != day or sha256(source_path) != root_receipt['source_binding']['sha256']:
        raise ValueError('identity: learner source differs from the completed ROOT binding')
    source = json.loads(source_path.read_bytes())
    ingest = source['ingestion_receipt']
    receipt_path = Path(ingest['path'])
    if sha256(receipt_path) != ingest['sha256']:
        raise ValueError('integrity: learner ingestion receipt changed')
    rc = json.loads(receipt_path.read_bytes())
    if (rc['trading_day'] != day or rc['record_count'] - 1 != binding['through_cursor'] or
            rc['source_prefix_hash'] != binding['source_hash']):
        # The sealed INPUT count includes failed inputs: this names the classroom's source and
        # whole-day causal cutoff, not a requirement that every input applied or every layer exists.
        raise ValueError('identity: learner source and classroom do not name the same sealed day and whole-day cutoff')
    # The existing whole-day route is exact. Do not silently trim to a guessed prefix.
    cpus = sorted(os.sched_getaffinity(0))
    import frankie_box_classroom_code as K
    booked = K.lane_cpus()
    # the booked length (the day's 32 CPUs, or a 16-CPU lane): the walk runs on its own held booking, nothing smaller
    lane_refusal = (None if len(cpus) in (16, 32) and cpus == booked else
                    'lane: learner walk requires its owning held booking (16 or 32 CPUs, the affinity equal to '
                    'the booked list); affinity %d CPUs, booked %d' % (len(cpus), len(booked)))
    own = {k: binding[k] for k in ('source_hash', 'as_of', 'through_cursor', 'request_id',
                                  'cycle_index', 'cycle_count')}
    if own['cycle_index'] != 0 or own['cycle_count'] != 1:
        raise ValueError('learner day reader requires the existing single whole-day cycle')
    own['producers'] = producer_hashes()
    directory = calculations / 'work' / 'classroom' / 'learner-reading'
    directory.mkdir(parents=True, exist_ok=True)
    identity = dict(day=day, source_binding_sha256=sha256(source_path), learner_binding=own,
                    day_file=str(day_file), day_sha256=day_sha256)
    pin = directory / 'input-state.pkl'
    pin_created = not pin.exists()
    if pin.exists():
        if _load_raw_state(pin) != identity:
            raise ValueError('retained learner reading belongs to different inputs/code')
    else:
        _save_raw_state(pin, identity)
    result_path = directory / 'receipt.json'
    shared_walk = (None if result_path.exists() else
                   _teacher_walk(teacher_rows, teacher_body, day=day, ingest=ingest, own=own,
                                 shared_policy=bool(source.get('shared_market_policy'))))
    if shared_walk is not None:
        result, teacher_receipt_path = shared_walk
        snapshot = DC.snapshot_teacher_attachment(teacher_body['attachment'],
            **{k: own[k] for k in ('request_id', 'cycle_index', 'cycle_count', 'source_hash', 'as_of', 'through_cursor')})
        shared_read = result.get('shared_market_read')
        coverage = (K.coverage_disposition(shared_read, journal_count=rc.get('journal_count'),
                                           record_count=rc.get('record_count'))
                    if shared_read is not None else
                    dict(schema=COVERAGE_ABSENT, reason='legacy no-policy source: the walk read the sealed journal directly'))
        witness = dict(schema='FRANKIE_LEARNER_READING_V1', author='frankie',
            source_binding_sha256=identity['source_binding_sha256'], ingestion_receipt=ingest,
            receipt=dict(path=str(teacher_receipt_path), sha256=sha256(teacher_receipt_path)),
            source_snapshot_hash=snapshot['source_snapshot_hash'], producers=own['producers'],
            walk_seconds=0.0, seconds=0.0, shared_market_read=shared_read,
            shared_market_use=result.get('shared_market_use'),
            shared_market_arithmetic=result.get('shared_market_arithmetic'),
            coverage=coverage, lane=dict(cpus=cpus, count=len(cpus), expected=len(booked)),
            walked_now=False, retained_receipt_reused=False, identity_pin_created_now=pin_created,
            walk_basis=('one pass (Greg, 2026-10-09): the host teacher\'s completed walk of this day (%s) is the walk this '
                        'reading would make (same sealed source, equation, cutoff); its attachment snapshotted under the '
                        'learner binding; no second walk of the source' % teacher_receipt_path),
            independent_scientific_verification=False,
            purpose='current evidence for accumulated-knowledge recognition before host grading')
        return snapshot, witness
    walked_now = not result_path.exists()
    if walked_now and lane_refusal is not None:
        raise ValueError(lane_refusal)          # the lane rule binds the walk; the shared walk above makes none
    if walked_now:
        environment = {k: os.environ.get(k) for k in ('FRANKIE_WALK_CACHE', 'FRANKIE_TEACHER_CHANGES')}
        try:
            code = T._teach(day, receipt_path, ingest['sha256'], max(1, len(booked) - 1), day_file, day_sha256,
                            save_requested=save_requested, learner_binding=own, learner_directory=directory,
                            calculations=calculations if source.get('shared_market_policy') else None,
                            shared_market_policy=(source.get('shared_market_policy') or {}).get('schema'))
            if code:
                raise ValueError('learner reading did not finish: exit %s' % code)
        finally:
            for name, value in environment.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
    result = json.loads(result_path.read_bytes())
    if (result.get('evidence_seat') != 'frankie' or result.get('learner_binding') != own or
            result.get('ingestion_receipt', {}).get('sha256') != ingest['sha256']):
        raise ValueError('retained learner receipt has another seat/source/binding')
    attachment_path = directory / result['attachment_file']['file']
    if sha256(attachment_path) != result['attachment_file']['sha256']:
        raise ValueError('learner attachment changed; completed work preserved')
    # This pickle is exclusively the learner's new calculation, never teacher_rows.
    with attachment_path.open('rb') as stream:
        own_result = pickle.load(stream)
    snapshot = DC.snapshot_teacher_attachment(own_result['attachment'],
        **{k: own[k] for k in ('request_id', 'cycle_index', 'cycle_count', 'source_hash', 'as_of', 'through_cursor')})
    shared_read = result.get('shared_market_read')
    if shared_read is not None:
        import frankie_box_classroom_code as K
        coverage = K.coverage_disposition(shared_read, journal_count=rc.get('journal_count'),
                                          record_count=rc.get('record_count'))
    else:
        coverage = dict(schema=COVERAGE_ABSENT, reason='legacy no-policy source: the walk read the sealed journal directly')
    witness = dict(schema='FRANKIE_LEARNER_READING_V1', author='frankie',
        source_binding_sha256=identity['source_binding_sha256'], ingestion_receipt=ingest,
        receipt=dict(path=str(result_path), sha256=sha256(result_path)),
        source_snapshot_hash=snapshot['source_snapshot_hash'], producers=own['producers'],
        walk_seconds=result['walk_seconds'], seconds=result['seconds'],
        shared_market_read=shared_read, shared_market_use=result.get('shared_market_use'),
        shared_market_arithmetic=result.get('shared_market_arithmetic'),
        coverage=coverage,
        # the lane this reading ran on (the walk refuses above unless it is its held 16- or 32-CPU booking) and whether the
        # walk was computed now or a retained receipt was reused; both for the one-day inspection report
        lane=dict(cpus=cpus, count=len(cpus), expected=len(booked)),
        walked_now=walked_now, retained_receipt_reused=not walked_now, identity_pin_created_now=pin_created,
        independent_scientific_verification=False,
        purpose='current evidence for accumulated-knowledge recognition before host grading')
    return snapshot, witness
