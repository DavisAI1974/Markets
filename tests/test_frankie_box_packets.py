"""The two packets Frankie's cycle-0 analysis asked for (frankie_box_compare, frankie_box_receipts): the comparison packet
puts every derived pin layer beside the frozen learned-structure files the brain carries; the session receipts packet
renders the session's own provider invocations, what it read and the wall it kept. Synthetic work and brain directories."""
import importlib.util
import json
from pathlib import Path

BOX = Path(__file__).resolve().parents[1] / 'deploy' / 'aws' / 'box'


def load(name):
    spec = importlib.util.spec_from_file_location(name, BOX / f'{name}.py')
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


compare, receipts = load('frankie_box_compare'), load('frankie_box_receipts')
FROZEN = ('learned_d_structures_and_families', 'learned_dipoles_and_geometry', 'historical_timing_lifespan_context')


def work_dir(tmp_path):
    work = tmp_path / 'work'
    (work / 'derived').mkdir(parents=True)
    layers = dict(legacy_price=dict(status='derived', producer='adapter', reason=None, sha256='a' * 64, bytes=10, path='x'),
                  legacy_per_second_roll20=dict(status='derived', producer='roll20', reason=None, sha256='b' * 64, bytes=10, path='y'),
                  ghost_layer=dict(status='could_not', producer=None, reason='no producer in the pin derives this layer; NO_PRODUCER_FOUND', sha256='c' * 64, bytes=1, path='z'))
    (work / 'derive.json').write_text(json.dumps(dict(pin_group='legacy_observable_crosswalk', rows=dict(count=3262), input_records=1958, f_last_groups=27, failure_count=0, layers=layers)))
    (work / 'derived' / 'legacy_price.json').write_text(json.dumps(dict(status='derived', producer='adapter', count=4, first=[1], last=[2])))
    (work / 'derived' / 'legacy_per_second_roll20.json').write_text(json.dumps(dict(status='derived', producer='roll20', series=[None, 0.5, 0.25])))
    return work


def brain_dir(tmp_path):
    brain = tmp_path / 'brain' / 'frozen-learned-structure'
    brain.mkdir(parents=True)
    study = json.dumps(dict(families=[1, 2, 3], geometry=dict(a=1), note='x')).encode()
    (brain / 'research__STUDY.json').write_bytes(study)
    (brain / 'research__NOTES.md').write_bytes(b'# Study\n\n## Families\n\ntext\n')
    import hashlib
    entries = [dict(name='research__STUDY.json', source='research/STUDY.json', bytes=len(study), sha256=hashlib.sha256(study).hexdigest(), layers=['learned_d_structures_and_families', 'learned_dipoles_and_geometry'], delivered_prefix=hashlib.sha256(study).hexdigest()[:12], include=True),
               dict(name='research__NOTES.md', source='research/NOTES.md', bytes=27, sha256=hashlib.sha256(b'# Study\n\n## Families\n\ntext\n').hexdigest(), layers=['learned_d_structures_and_families'], delivered_prefix='000000000000', include=False, reason='the checkout bytes do not match the delivered digest prefix; excluded unless include is set true')]
    (brain / 'MANIFEST.json').write_text(json.dumps(dict(schema='FRANKIE_BOX_BRAIN_FROZEN_ENTRY_V1', at=1.0, historical_prompt='/r/historical-prompt.md', layers=sorted(FROZEN[:2]), entries=entries)))
    return tmp_path / 'brain'


def test_comparison_packet_puts_every_pin_layer_beside_every_frozen_layer(tmp_path):
    work, brain = work_dir(tmp_path), brain_dir(tmp_path)
    report = compare.write(work, brain, FROZEN)
    assert report['schema'] == compare.SCHEMA and report['counts'] == dict(pin_layers=3, derived=2, frozen_layers=3, frozen_files_delivered=3, frozen_files_carried=2)
    d = report['derived']['layers']
    assert d['legacy_price']['count'] == 4 and d['legacy_per_second_roll20']['count'] == 3 and d['ghost_layer']['status'] == 'could_not'
    f = report['frozen']
    assert [e['source'] for e in f['learned_d_structures_and_families']] == ['research/STUDY.json', 'research/NOTES.md']
    assert f['learned_d_structures_and_families'][0]['content']['kind'] == 'json object' and f['learned_d_structures_and_families'][0]['content']['keys'][0] == dict(key='families', type='list', length=3)
    assert f['learned_d_structures_and_families'][1]['include'] is False and 'content' not in f['learned_d_structures_and_families'][1]
    assert f['historical_timing_lifespan_context'] == []
    md = (work / 'comparison.md').read_text()
    assert '| legacy_price | derived | 4 |' in md and '### historical_timing_lifespan_context' in md and 'no file delivered for this layer' in md
    assert 'json object: families[3], geometry[1], note' in md and 'YOUR JUDGEMENT' in md and (work / 'comparison.json').is_file()


def test_comparison_packet_without_a_frozen_entry_says_so(tmp_path):
    work = work_dir(tmp_path)
    report = compare.build(work, tmp_path / 'no-brain', FROZEN)
    assert report['frozen_manifest'] is None and all(v == [] for v in report['frozen'].values()) and report['counts']['frozen_files_carried'] == 0


def session_dirs(tmp_path):
    work = tmp_path / 'work'
    for lane, name, extra in (('boss-jobs', 'j1', dict(pod_id='pod', job_id='9' * 64)), ('serverless-jobs', 'read-0000', dict(endpoint_id='ep'))):
        d = work / lane / name
        d.mkdir(parents=True)
        (d / 'request.json').write_text(json.dumps(dict(name='write-analysis' if lane == 'boss-jobs' else 'read-0000', body_sha256='d' * 64, body_bytes=1000, estimated_input_tokens=500, max_tokens=1000, served_model_name='granite42-smoke', **extra)))
        (d / 'outcome.json').write_text(json.dumps(dict(model='granite42-smoke', usage=dict(prompt_tokens=500, completion_tokens=200), incomplete=False, error=None, seconds=12.4, runpod_job_id='rp-1' if lane == 'serverless-jobs' else None, worker_id='w1' if lane == 'serverless-jobs' else None)))
        (d / 'result.json').write_bytes(b'{"choices": []}')
    notes = work / 'notes-abc-unbounded'
    notes.mkdir()
    (notes / 'note-0000.md').write_text('n')
    (work / 'merges').mkdir()
    (work / 'merges' / 'merge-0-0000.md').write_text('m')
    (work / 'merged-notes.md').write_text('merged')
    (work / 'reading.json').write_text(json.dumps(dict(corpus=dict(bytes=5, sha256='e' * 64, path='/c'), corpus_sha256='e' * 64, parts=4, lane=dict(serverless='ep', workers=8), merged=dict(bytes=6, sha256='f' * 64))))
    (work / 'reading-plan.json').write_text(json.dumps(dict(notes_dir=str(notes), chunk_bytes=140000, part_input_tokens=87000)))
    (work / 'verify.json').write_text(json.dumps(dict(request_sha256='1' * 64, request_id='run-cycle-00', cycle_index=0, as_of=100, learning_cutoff_ns=200, source_hash='2' * 64, input_hash='3' * 64, input_hash_sources={'3' * 64: ['manifest_base64']}, prompt=dict(bytes=7, sha256='4' * 64, path='/p'), session_id='sess')))
    (work / 'labels.json').write_text(json.dumps(dict(available_ns=150, gap=1, path='/l', labels=[dict(previous_ns=0, next_ns=10, available_ns=120, evidence_hash='5' * 64), dict(previous_ns=10, next_ns=20, available_ns=190, evidence_hash='6' * 64)])))
    ledger = tmp_path / 'reading-ledger.json'
    ledger.write_text(json.dumps(dict(values={'a': 1, 'b': 2}, cycles={'00': {}})))
    return work, ledger


def test_session_receipts_packet_carries_invocations_reading_and_the_wall(tmp_path):
    work, ledger = session_dirs(tmp_path)
    report = receipts.write(work, ledger)
    inv = report['provider_invocations']
    assert [i['lane'] for i in inv] == ['boss', 'serverless'] and inv[0]['job_id'] == '9' * 64 and inv[1]['runpod_job_id'] == 'rp-1' and inv[0]['result']['bytes'] == 15
    assert inv[0]['usage'] == dict(prompt_tokens=500, completion_tokens=200) and inv[0]['request_sha256'] == 'd' * 64
    k = report['knowledge_retrieval']
    assert k['parts'] == 4 and len(k['notes']) == 1 and len(k['merges']) == 1 and k['reading_ledger'] == dict(values=2, cycles=['00']) and k['merged']['sha256'] == 'f' * 64
    w = report['answer_wall']
    assert w['as_of'] == 100 and w['learning_cutoff_ns'] == 200 and w['labels']['count'] == 2 and w['labels']['all_available_at_or_before_cutoff'] is True
    md = (work / 'session-receipts.md').read_text()
    assert '| boss | write-analysis | dddddddddddddddd |' in md and '2 serverless' not in md and 'Answer wall' in md and 'learning cutoff 200' in md
    assert (work / 'session-receipts.json').is_file()


def test_session_receipts_packet_on_an_empty_work_directory(tmp_path):
    work = tmp_path / 'w'
    work.mkdir()
    report = receipts.build(work)
    assert report['provider_invocations'] == [] and report['knowledge_retrieval']['notes'] == [] and report['answer_wall']['labels']['count'] == 0
    assert 'Provider invocations (0' in receipts.render(report)
