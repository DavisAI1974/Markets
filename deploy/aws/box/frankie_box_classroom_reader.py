"""Frankie's own sealed-day reading for SOCRATIC/VERIFY, before host grading.

Reuses the pinned measurement mathematics, with separate learner state and cache.
This supplies evidence for accumulated-knowledge recognition, not an independent
scientific verification of the same code on the same bytes. No host answers enter.
"""
import hashlib
import json
import os
import pickle
from pathlib import Path


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def producer_hashes():
    root = Path(__file__).resolve().parents[3]
    paths = ['deploy/aws/box/frankie_box_classroom_reader.py',
             'deploy/aws/box/frankie_box_experiment_teacher.py']
    paths += ['research/kalshi/frankie_boss/' + name + '.py' for name in (
        'parallel_teacher', 'parallel_journal', 'teacher_changes', 'c15_teacher_r3',
        'c15_teacher', 'c15_normalizer_r3', 'c15_normalizer', 'dipole_target',
        'frankie_journal_reader', 'compact_journal', 'c15_journal', 'dipole_classroom')]
    return {p: sha256(root / p) for p in paths}


def read_day(day, calculations, binding, *, day_file, day_sha256, save_requested):
    """Use ROOT's sealed source descriptor; never accept a teacher snapshot/key/path."""
    import frankie_box_experiment_teacher as T
    from research.kalshi.frankie_boss import dipole_classroom as DC
    from research.kalshi.frankie_boss.parallel_teacher import _save_raw_state, _load_raw_state

    calculations = Path(calculations)
    root_receipt = json.loads((calculations / 'calculations-receipt.json').read_bytes())
    source_path = calculations / 'source-binding.json'
    if root_receipt.get('day') != day or sha256(source_path) != root_receipt['source_binding']['sha256']:
        raise ValueError('learner source differs from the completed ROOT binding')
    source = json.loads(source_path.read_bytes())
    ingest = source['ingestion_receipt']
    receipt_path = Path(ingest['path'])
    if sha256(receipt_path) != ingest['sha256']:
        raise ValueError('learner ingestion receipt changed')
    rc = json.loads(receipt_path.read_bytes())
    if (rc['trading_day'] != day or rc['record_count'] - 1 != binding['through_cursor'] or
            rc['source_prefix_hash'] != binding['source_hash']):
        raise ValueError('learner source and classroom do not name the same sealed day')
    # The existing whole-day route is exact. Do not silently trim to a guessed prefix.
    cpus = sorted(os.sched_getaffinity(0))
    if len(cpus) != 16:
        raise ValueError('learner walk requires its owning held 16-CPU lane')
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
    if pin.exists():
        if _load_raw_state(pin) != identity:
            raise ValueError('retained learner reading belongs to different inputs/code')
    else:
        _save_raw_state(pin, identity)
    result_path = directory / 'receipt.json'
    if not result_path.exists():
        environment = {k: os.environ.get(k) for k in ('FRANKIE_WALK_CACHE', 'FRANKIE_TEACHER_CHANGES')}
        try:
            code = T._teach(day, receipt_path, ingest['sha256'], 15, day_file, day_sha256,
                            save_requested=save_requested, learner_binding=own, learner_directory=directory)
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
    witness = dict(schema='FRANKIE_LEARNER_READING_V1', author='frankie',
        source_binding_sha256=identity['source_binding_sha256'], ingestion_receipt=ingest,
        receipt=dict(path=str(result_path), sha256=sha256(result_path)),
        source_snapshot_hash=snapshot['source_snapshot_hash'], producers=own['producers'],
        walk_seconds=result['walk_seconds'], seconds=result['seconds'],
        independent_scientific_verification=False,
        purpose='current evidence for accumulated-knowledge recognition before host grading')
    return snapshot, witness
