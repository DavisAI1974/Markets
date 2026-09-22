import json

import pytest

from research.kalshi.frankie_boss.operations import day_pipeline as dp


CONFIG = dict(python='py', ssm_run='ssm.py', ec2_host='ec2.py', instance='i-1', region='us-east-2',
              stage_block_sources='stage.py', upload_restore_set='upload.py', block='B', archive='A', bucket='b',
              blocks_dir='blocks', restore_prefix='frankie/days',
              host_scripts=dict(ingest='ingest.ps1', schedule_prefixes='prefix.ps1', cycles='cycles.ps1'))
OUT = {
    # The real final line of stage_block_sources.py: total_mbo_records, not records. 57027 is the
    # 20211003 Sunday reopen, the count the gold-standard first run reduced.
    'stage.py': json.dumps(dict(status='block_sources_staged', manifest='blocks/m.json', manifest_hash='h'*64,
                                total_mbo_records=57027)),
    'start': 'state=running\nSSM Online: True',
    'ingest.ps1': 'PIPELINE_RECEIPT ' + json.dumps(dict(journal_count=57027, journal_hash='j'*64, compact_sha256='c'*64,
                                                       worker_cpus=list(range(1, 32)), wall_seconds=120.0, worker_cpu_seconds=2100.0)),
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


def test_resume_restarts_stopped_host_without_rewriting_start_receipt(tmp_path):
    calls = []
    pipeline = dp.DayPipeline(CONFIG, '20211003', runner=runner(calls), runs_root=tmp_path)
    pipeline.resume(until='host-start')
    original = pipeline.path('host-start').read_bytes()
    pipeline.ensure_host_online()
    assert calls[-1][-1] == 'start'
    assert pipeline.path('host-start').read_bytes() == original


def test_cleanup_stops_ingest_in_its_own_region_even_if_native_stop_fails(tmp_path):
    calls = []
    def run(argv, *, timeout):
        calls.append(argv)
        return (1, 'failed') if 'i-1' in argv else (0, 'state=stopped')
    config = dict(CONFIG, ingest_runner=dict(instance='i-32', region='us-east-1'))
    pipeline = dp.DayPipeline(config, '20211003', runner=run, runs_root=tmp_path)
    with pytest.raises(dp.StageRefused, match='host stop failed'):
        pipeline.stop_compute()
    assert len(calls) == 2
    assert 'i-32' in calls[1] and 'us-east-1' in calls[1]
    assert json.loads((pipeline.directory / 'ingest-runner-stop.json').read_bytes())['stopped']


def test_chain_holds_before_the_result_bearing_stage_then_resumes_under_the_exact_go(tmp_path):
    calls = []
    pipeline = dp.DayPipeline(dict(CONFIG, ingest_on='host'), '20211004', runner=runner(calls), runs_root=tmp_path, now=lambda: 1.)
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


def test_two_cycle_batch_does_not_admit_packaging_and_full_resume_finishes(tmp_path):
    calls = []
    run = runner(calls)
    def batch_runner(argv, *, timeout):
        if 'cycles.ps1' in argv and 'CycleLimit=2' in argv:
            calls.append(argv)
            return 0, 'PIPELINE_RECEIPT ' + json.dumps(dict(
                status='requested_cycles_complete', cycles_completed=2, cycles_total=19,
                requested_cycles=2, day='20211003'))
        return run(argv, timeout=timeout)
    pipeline = dp.DayPipeline(dict(CONFIG, ingest_on='host'), '20211003',
                             runner=batch_runner, runs_root=tmp_path, cycle_limit=2)
    result = pipeline.resume(go='h'*64)
    assert result['cycles'] == 'partial' and 'package-upload' not in result
    assert pipeline.receipt('cycles') is None
    with pytest.raises(dp.StageRefused, match='needs the cycles receipt'):
        pipeline.run_stage('package-upload')
    resumed = dp.DayPipeline(dict(CONFIG, ingest_on='host'), '20211003',
                            runner=batch_runner, runs_root=tmp_path)
    assert resumed.resume(go='h'*64)['cycles'] == 'done'
    assert resumed.receipt('cycles')['gate']['cycles_completed'] == 19


def test_ingest_on_the_runner_is_only_ever_recorded_never_run_over_ssm(tmp_path):
    calls = []
    pipeline = dp.DayPipeline(CONFIG, '20211004', runner=runner(calls), runs_root=tmp_path)
    with pytest.raises(dp.StageRefused, match='record its receipt with --record ingest'):
        pipeline.resume()
    assert pipeline.receipt('host-start') and not any('ingest.ps1' in argv for argv in calls)
    host = dp.DayPipeline(dict(CONFIG, ingest_on='host'), '20211005', runner=runner(calls), runs_root=tmp_path)
    host.resume(until='ingest')
    assert host.receipt('ingest')['gate']['parallelism'] == 17.5


def test_failed_stage_keeps_earlier_receipts_and_the_host_stop_always_runs(tmp_path):
    calls = []
    pipeline = dp.DayPipeline(dict(CONFIG, ingest_on='host'), '20211004', runner=runner(calls, failing=('ingest.ps1',)), runs_root=tmp_path)
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
        completion_digest='d'*64, compact_sha256='c'*64, github_run_id='34962256086',
        parent_cpu=0, worker_cpus=[1, 2, 3], wall_seconds=715.19, worker_cpu_seconds=2079.29)))
    assert pipeline.record_external('ingest', receipt) == 'done'
    gate = pipeline.receipt('ingest')['gate']
    assert (gate['journal_count'], gate['journal_hash'], gate['compact_sha256'], gate['journal_entries']) == (57027, 'j'*64, 'c'*64, 114054)
    assert gate['worker_cpus'] == [1, 2, 3] and gate['parallelism'] == 2.907
    collapsed = tmp_path / 'collapsed.json'
    collapsed.write_text(json.dumps(dict(json.loads(receipt.read_text()), worker_cpus=list(range(1, 32)),
                                         wall_seconds=2100.0, worker_cpu_seconds=2079.29)))
    third = dp.DayPipeline(CONFIG, '20211006', runner=runner(calls), runs_root=tmp_path)
    third.resume(until='host-start')
    with pytest.raises(dp.StageRefused, match='collapsed: 0.99 CPUs busy for 31'):
        third.record_external('ingest', collapsed)
    assert pipeline.record_external('ingest', receipt) == 'present'
    receipt.write_text(json.dumps(dict(schema='FRANKIE_COMBINED_JOURNAL_EXECUTION_V1', status='attention')))
    other = dp.DayPipeline(CONFIG, '20211005', runner=runner(calls), runs_root=tmp_path)
    other.resume(until='host-start')
    with pytest.raises(dp.StageRefused, match='not a verified'):
        other.record_external('ingest', receipt)


def test_host_stages_carry_the_day_and_the_declared_host_variables(tmp_path):
    calls = []
    variables = dict(ToolsRoot='C:\\tools\\Markets', RunRoot='D:\\frankie\\runs', Python='D:\\py\\python.exe')
    pipeline = dp.DayPipeline(dict(CONFIG, ingest_on='host', host_variables=variables), '20211004',
                              runner=runner(calls), runs_root=tmp_path, now=lambda: 1.)
    pipeline.resume(until='schedule-prefixes')
    for script in ('ingest.ps1', 'prefix.ps1'):
        argv = next(a for a in calls if script in a)
        pairs = [argv[i + 1] for i, part in enumerate(argv) if part == '--set']
        assert pairs == ['Day=20211004', 'Python=D:\\py\\python.exe', 'RunRoot=D:\\frankie\\runs',
                         'ToolsRoot=C:\\tools\\Markets'] + (['CycleLimit=19'] if script == 'prefix.ps1' else [])
    # The script file is still named verbatim: the day reaches it only as a --set value.
    argv = next(a for a in calls if 'prefix.ps1' in a)
    carriers = [part for part in argv if '20211004' in part]
    assert carriers == ['Day=20211004'] and argv[argv.index('--script') + 1] == 'prefix.ps1'


def test_a_stage_whose_host_script_is_not_declared_is_refused_by_name(tmp_path):
    calls = []
    scripts = dict(CONFIG['host_scripts'], ingest=None)
    pipeline = dp.DayPipeline(dict(CONFIG, ingest_on='host', host_scripts=scripts), '20211004',
                              runner=runner(calls), runs_root=tmp_path)
    with pytest.raises(dp.StageRefused, match='declares no host script for ingest'):
        pipeline.resume()
    assert pipeline.receipt('host-start') and not any('ingest' in ' '.join(argv) for argv in calls)


def test_the_staged_record_count_is_read_from_the_line_the_tool_really_prints(tmp_path):
    pipeline = dp.DayPipeline(CONFIG, '20211004', runs_root=tmp_path)
    line = json.dumps(dict(status='block_sources_staged', manifest='m.json', manifest_hash='h'*64,
                           total_mbo_records=6471475))
    assert pipeline.gate_of('stage-sources', line)['records'] == 6471475
    # A null count used to be recorded and pass require(), because a present key is not a value.
    with pytest.raises(dp.StageRefused, match='no source record count'):
        pipeline.gate_of('stage-sources', json.dumps(dict(status='block_sources_staged', manifest='m.json',
                                                          manifest_hash='h'*64)))


def test_an_ingest_receipt_for_another_days_reduction_is_refused_on_the_count(tmp_path):
    calls = []
    pipeline = dp.DayPipeline(CONFIG, '20211004', runner=runner(calls), runs_root=tmp_path)
    pipeline.resume(until='host-start')
    assert pipeline.receipt('stage-sources')['gate']['records'] == 57027
    other_day = tmp_path / 'other.json'
    other_day.write_text(json.dumps(dict(schema='FRANKIE_COMBINED_JOURNAL_EXECUTION_V1', status='verified',
        source_records=1994358, completion=dict(count=1994358, head_hash='j'*64), compact_sha256='c'*64,
        parent_cpu=0, worker_cpus=[1, 2, 3], wall_seconds=715.19, worker_cpu_seconds=2079.29)))
    # The journal job is pinned to one snapshot request, so this receipt is verified, self-consistent
    # and about the wrong source. Only the staged count sees it.
    with pytest.raises(dp.StageRefused, match='reduced 1994358 records; 20211004 staged 57027'):
        pipeline.record_external('ingest', other_day)
    assert pipeline.receipt('ingest') is None
    matching = tmp_path / 'matching.json'
    matching.write_text(json.dumps(dict(schema='FRANKIE_COMBINED_JOURNAL_EXECUTION_V1', status='verified',
        source_records=57027, completion=dict(count=57027, head_hash='j'*64), compact_sha256='c'*64,
        parent_cpu=0, worker_cpus=[1, 2, 3], wall_seconds=715.19, worker_cpu_seconds=2079.29)))
    assert pipeline.record_external('ingest', matching) == 'done'


def test_the_host_ingest_path_is_reconciled_on_the_same_count(tmp_path):
    calls = []
    wrong = dict(OUT, **{'ingest.ps1': 'PIPELINE_RECEIPT ' + json.dumps(dict(
        journal_count=1994358, journal_hash='j'*64, compact_sha256='c'*64,
        worker_cpus=list(range(1, 32)), wall_seconds=120.0, worker_cpu_seconds=2100.0))})

    def run(argv, *, timeout):
        calls.append(argv)
        return 0, wrong[next(k for k in wrong if k in argv)]

    pipeline = dp.DayPipeline(dict(CONFIG, ingest_on='host'), '20211004', runner=run, runs_root=tmp_path)
    with pytest.raises(dp.StageRefused, match='reduced 1994358 records; 20211004 staged 57027'):
        pipeline.resume()
    assert pipeline.receipt('ingest') is None


def test_cycle_limit_seam_gates_the_prefix_count_and_refuses_out_of_range_limits(tmp_path):
    # The pre-existing seam (ship finding, 2026-09-20): a batch smaller than the day needs only as many prefixes as
    # cycles it runs, never fewer; the limit itself is 1..19.
    for bad in (0, 20, '2', None):
        with pytest.raises(ValueError, match='cycle_limit must be from 1 through 19'):
            dp.DayPipeline(dict(CONFIG, ingest_on='host'), '20211003', runner=runner([]), runs_root=tmp_path, cycle_limit=bad)
    pipeline = dp.DayPipeline(dict(CONFIG, ingest_on='host', minimum_prefixes=19), '20211003', runner=runner([]),
                             runs_root=tmp_path, cycle_limit=2)
    assert pipeline.cycle_limit == 2
    with pytest.raises(dp.StageRefused, match='prefix'):
        pipeline.gate_of('schedule-prefixes', 'PIPELINE_RECEIPT ' + json.dumps(dict(prefix_count=1, prefixes_sha256='a' * 64)))
    gate = pipeline.gate_of('schedule-prefixes', 'PIPELINE_RECEIPT ' + json.dumps(dict(prefix_count=2, prefixes_sha256='a' * 64)))
    assert gate['prefix_count'] == 2
    full = dp.DayPipeline(dict(CONFIG, ingest_on='host', minimum_prefixes=19), '20211003', runner=runner([]), runs_root=tmp_path)
    with pytest.raises(dp.StageRefused, match='prefix'):
        full.gate_of('schedule-prefixes', 'PIPELINE_RECEIPT ' + json.dumps(dict(prefix_count=2, prefixes_sha256='a' * 64)))


def test_declared_schedule_controls_cycle_bounds_and_default(tmp_path):
    declaration = dict(trading_day='20211004', step_count=23, source_record_count=2032203,
                       source_manifest_hash='a'*64, schedule_sha256='b'*64)
    config = dict(CONFIG, trading_day_schedule=declaration)
    pipeline = dp.DayPipeline(config, '20211004', runs_root=tmp_path)
    assert pipeline.cycle_limit == pipeline.cycle_count == 23
    assert 'CycleLimit=23' in pipeline.commands()['cycles']
    assert dp.DayPipeline(config, '20211004', cycle_limit=1).cycle_limit == 1
    with pytest.raises(ValueError, match='declared schedule'):
        dp.DayPipeline(config, '20211004', cycle_limit=24)
    with pytest.raises(ValueError, match='pinned day'):
        dp.DayPipeline(config, '20211003')


def test_trading_day_does_not_dispatch_utc_restage(tmp_path):
    calls = []
    config = dict(CONFIG, trading_day_schedule=dict(trading_day='20211004', step_count=2,
        source_record_count=2032203, source_manifest_hash='a'*64, schedule_sha256='b'*64))
    pipeline = dp.DayPipeline(config, '20211004', runner=runner(calls), runs_root=tmp_path)
    with pytest.raises(dp.StageRefused, match='no UTC restaging'):
        pipeline.run_stage('stage-sources')
    assert calls == []


def test_trading_day_receipt_uses_records_not_paired_journal_entries(tmp_path):
    config = dict(CONFIG, trading_day_schedule=dict(trading_day='20211004', step_count=2,
        source_record_count=2032203, source_manifest_hash='a'*64, schedule_sha256='b'*64))
    pipeline = dp.DayPipeline(config, '20211004', runs_root=tmp_path)
    pipeline.write('stage-sources', dict(manifest='m.json', manifest_hash='a'*64, records=2032203), command=[])
    pipeline.write('host-start', dict(ssm_online=True), command=[])
    path = tmp_path / 'ingest.json'
    value = dict(schema='BOSS_BLOCK_INGESTION_RECEIPT_V1', writer='compact', session_policy='cme_trading_day',
        trading_day='20211004', manifest_hash='a'*64, record_count=2032203, journal_count=4064406,
        journal_hash='c'*64, journal_sha256='d'*64, sessions=[dict(session_id='20211004')])
    path.write_text(json.dumps(dict(value, trading_day='20211003')))
    with pytest.raises(dp.StageRefused, match='declared trading day'):
        pipeline.record_external('ingest', path)
    assert pipeline.receipt('ingest') is None
    path.write_text(json.dumps(value))
    assert pipeline.record_external('ingest', path) == 'done'
    gate = pipeline.receipt('ingest')['gate']
    assert gate['journal_count'] == 2032203 and gate['journal_entries'] == 4064406
