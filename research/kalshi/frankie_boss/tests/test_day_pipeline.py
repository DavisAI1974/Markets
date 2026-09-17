import json

import pytest

from research.kalshi.frankie_boss.operations import day_pipeline as dp


CONFIG = dict(python='py', ssm_run='ssm.py', ec2_host='ec2.py', instance='i-1', region='us-east-2',
              stage_block_sources='stage.py', upload_restore_set='upload.py', block='B', archive='A', bucket='b',
              blocks_dir='blocks', restore_prefix='frankie/days',
              host_scripts=dict(ingest='ingest.ps1', schedule_prefixes='prefix.ps1', cycles='cycles.ps1'))
OUT = {
    'stage.py': json.dumps(dict(status='block_sources_staged', manifest='blocks/m.json', manifest_hash='h'*64, records=6470000)),
    'start': 'state=running\nSSM Online: True',
    'ingest.ps1': 'PIPELINE_RECEIPT ' + json.dumps(dict(journal_count=57027, journal_hash='j'*64, compact_sha256='c'*64)),
    'prefix.ps1': 'PIPELINE_RECEIPT ' + json.dumps(dict(prefix_count=19, prefixes_sha256='p'*64)),
    'cycles.ps1': 'PIPELINE_RECEIPT ' + json.dumps(dict(cycles_completed=19, cycles_total=19)),
    'upload.py': json.dumps(dict(upload_manifest_sha256='u'*64)),
    'snapshot': 'snapshot snap-0123 of vol-1 (xvdf) started\nsnapshot snap-0123 completed, 200 GiB volume',
    'stop': 'state=stopped',
}


def runner(calls, failing=()):
    def run(argv, *, timeout):
        calls.append(argv)
        key = next((k for k in OUT if k in argv), None)
        if key in failing:
            return 1, 'boom'
        return 0, OUT[key]
    return run


def test_chain_holds_before_the_result_bearing_stage_then_resumes_under_the_exact_go(tmp_path):
    calls = []
    pipeline = dp.DayPipeline(CONFIG, '20211004', runner=runner(calls), runs_root=tmp_path, now=lambda: 1.)
    assert pipeline.resume() == {s: 'done' for s in dp.STAGES[:4]} | {'cycles': 'hold'}
    assert (tmp_path / '20211004' / '04-cycles.HOLD.json').exists() and not pipeline.path('cycles').exists()
    with pytest.raises(dp.StageRefused, match='needs the cycles receipt'):
        pipeline.run_stage('package-upload')
    before = len(calls)
    assert pipeline.resume(go='x'*64)['cycles'] == 'hold'       # a wrong hash is not a go
    assert len(calls) == before                                  # and nothing re-ran
    outcome = pipeline.resume(go='h'*64)
    assert outcome == {s: 'present' for s in dp.STAGES[:4]} | {s: 'done' for s in dp.STAGES[4:]}
    receipts = [pipeline.receipt(s) for s in dp.STAGES]
    assert all(r['gate'][name] is not None for r, s in zip(receipts, dp.STAGES) for name in dp.GATES[s])
    assert receipts[1]['previous_receipt_sha256'] == dp.hashlib.sha256(dp.canonical(receipts[0])).hexdigest()
    assert pipeline.resume(go='h'*64) == {s: 'present' for s in dp.STAGES}   # idempotent: no command runs again
    assert len(calls) == 7


def test_failed_stage_keeps_earlier_receipts_and_the_host_stop_always_runs(tmp_path):
    calls = []
    pipeline = dp.DayPipeline(CONFIG, '20211004', runner=runner(calls, failing=('ingest.ps1',)), runs_root=tmp_path)
    with pytest.raises(dp.StageRefused, match='ingest exited 1'):
        pipeline.resume()
    assert pipeline.receipt('host-start') and pipeline.receipt('ingest') is None
    pipeline.host_stop()
    assert json.loads((tmp_path / '20211004' / 'host-stop.json').read_bytes())['stopped'] is True
    with pytest.raises(dp.StageRefused, match='incomplete'):
        pipeline.gate_of('cycles', 'PIPELINE_RECEIPT {"cycles_completed": 3, "cycles_total": 19}')


def test_ingest_is_recorded_from_the_journal_stack_verification_receipt(tmp_path):
    calls = []
    pipeline = dp.DayPipeline(CONFIG, '20211004', runner=runner(calls), runs_root=tmp_path)
    pipeline.resume(until='host-start')
    receipt = tmp_path / 'verification-receipt.json'
    receipt.write_text(json.dumps(dict(schema='FRANKIE_COMBINED_JOURNAL_EXECUTION_V1', status='verified',
        source_records=57027, journal_entries=114054, completion=dict(count=57027, head_hash='j'*64, digest='d'*64),
        completion_digest='d'*64, compact_sha256='c'*64, github_run_id='34962256086')))
    assert pipeline.record_external('ingest', receipt) == 'done'
    gate = pipeline.receipt('ingest')['gate']
    assert (gate['journal_count'], gate['journal_hash'], gate['compact_sha256'], gate['journal_entries']) == (57027, 'j'*64, 'c'*64, 114054)
    assert pipeline.record_external('ingest', receipt) == 'present'
    receipt.write_text(json.dumps(dict(schema='FRANKIE_COMBINED_JOURNAL_EXECUTION_V1', status='attention')))
    other = dp.DayPipeline(CONFIG, '20211005', runner=runner(calls), runs_root=tmp_path)
    other.resume(until='host-start')
    with pytest.raises(dp.StageRefused, match='not a verified'):
        other.record_external('ingest', receipt)
