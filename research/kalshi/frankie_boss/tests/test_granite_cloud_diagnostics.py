import json

import pytest

from research.kalshi.frankie_boss import granite_cloud_diagnostics as diagnostics


OWNER = 'a' * 32
MANIFEST = {'files': [{'path': 'model.safetensors', 'size': 1000}]}


def record(**changes):
    value = dict(schema='GRANITE_PROGRESS_V1', correlation_id=OWNER, role='stage',
                 pid=123, phase='download', elapsed_seconds=60,
                 phase_elapsed_seconds=60, current_file='model.safetensors',
                 file_processed_bytes=500, manifest_total_bytes=1000,
                 bytes_present=500, download_percent=50,
                 download_percent_basis='bytes_on_disk_not_verified',
                 bytes_per_second=10, seconds_since_byte_progress=0,
                 verified_file_count=0, error_type=None, http_status=None, errno=None)
    value.update(changes)
    return value


def line(value):
    prefix = 'GRANITE_DIAGNOSTIC ' if value['schema'] == 'GRANITE_DIAGNOSTIC_V1' else 'GRANITE_PROGRESS '
    return prefix + json.dumps(value)


def diagnostic(elapsed=60, reason='no_progress', severity='warning'):
    return record(schema='GRANITE_DIAGNOSTIC_V1', elapsed_seconds=elapsed,
                  phase_elapsed_seconds=elapsed, reason=reason, severity=severity,
                  code='progress_resumed' if reason == 'recovered' else 'possible_stall',
                  seconds_since_byte_progress=30 if reason == 'no_progress' else 0)


def test_validated_progress_and_summary_do_not_claim_verified_download():
    collector = diagnostics.Collector(OWNER, MANIFEST)
    summary = collector.ingest(line(record()))
    assert '50' in summary and 'not verified' in summary
    snapshot = collector.export()
    assert snapshot['latest']['stage']['bytes_present'] == 500
    snapshot['latest']['stage']['bytes_present'] = 0
    assert collector.export()['latest']['stage']['bytes_present'] == 500


@pytest.mark.parametrize('changes', [
    {'correlation_id': 'b' * 32}, {'api_key': 'private-secret'},
    {'current_file': 'https://example.invalid/private-secret'},
    {'phase': 'private-secret'}, {'role': 'private-secret'},
    {'elapsed_seconds': float('nan')}, {'bytes_present': 1001},
    {'manifest_total_bytes': 2000}, {'download_percent': 100},
    {'file_processed_bytes': 1001}, {'verified_file_count': 2},
    {'pid': True}, {'seconds_since_byte_progress': -1},
])
def test_untrusted_fields_are_rejected_without_echoing_values(changes):
    with pytest.raises(ValueError) as error:
        diagnostics.parse_line(line(record(**changes)), OWNER, MANIFEST)
    assert 'private-secret' not in str(error.value)


def test_malformed_oversized_and_duplicate_json_are_refused():
    for malformed in ['GRANITE_PROGRESS {', 'GRANITE_PROGRESS ' + 'x' * 8192,
                      line(record()).replace('"pid": 123', '"pid": 123, "pid": 124'),
                      b'GRANITE_PROGRESS \xff']:
        with pytest.raises(ValueError):
            diagnostics.parse_line(malformed, OWNER, MANIFEST)
    assert diagnostics.parse_line('ordinary log with private-secret', OWNER, MANIFEST) is None


def test_reposts_survive_duplicate_tail_reads_and_recovery_clears_active_diagnostic():
    collector = diagnostics.Collector(OWNER, MANIFEST)
    warning = line(diagnostic())
    assert collector.ingest(warning) is not None
    assert collector.ingest(warning) is None
    assert collector.ingest(line(diagnostic(elapsed=90))) is not None
    assert collector.ingest(line(diagnostic(elapsed=120, reason='recovered', severity='info'))) is not None
    snapshot = collector.export()
    assert [item['reason'] for item in snapshot['diagnostics']] == ['no_progress', 'no_progress', 'recovered']
    assert snapshot['active_diagnostics'] == {}
    assert collector.ingest(warning) is None


def test_diagnostic_history_and_latest_roles_are_bounded():
    collector = diagnostics.Collector(OWNER, MANIFEST, history_limit=3)
    for elapsed in range(30, 301, 30):
        collector.ingest(line(diagnostic(elapsed)))
    snapshot = collector.export()
    assert len(snapshot['diagnostics']) == 3
    assert snapshot['diagnostics'][-1]['elapsed_seconds'] == 300
    assert len(snapshot['latest']) == 1


def test_frequent_duplicate_reason_is_rate_limited_but_error_and_recovery_are_immediate():
    collector = diagnostics.Collector(OWNER, MANIFEST)
    assert collector.ingest(line(diagnostic(60)))
    assert collector.ingest(line(diagnostic(61))) is None
    assert collector.ingest(line(diagnostic(90)))
    failed = diagnostic(91, reason='error', severity='error')
    failed.update(code='timeout', error_type='TimeoutError')
    assert collector.ingest(line(failed))
    assert collector.ingest(line(diagnostic(92, reason='recovered', severity='info')))


def test_rejected_line_does_not_mutate_collector():
    collector = diagnostics.Collector(OWNER, MANIFEST)
    collector.ingest(line(record()))
    before = collector.export()
    with pytest.raises(ValueError):
        collector.ingest(line(record(error='private-secret')))
    assert collector.export() == before


def test_same_timestamp_phase_changes_and_distinct_errors_are_preserved():
    collector = diagnostics.Collector(OWNER, MANIFEST)
    first = line(record(phase='download'))
    second = line(record(phase='file_verify'))
    assert collector.ingest(first)
    assert collector.ingest(second)
    assert collector.ingest(first) is None
    assert collector.ingest(line(diagnostic()))
    failed = diagnostic(reason='error', severity='error')
    failed.update(code='timeout', error_type='TimeoutError')
    assert collector.ingest(line(failed))
    assert collector.export()['active_diagnostics']['stage']['reason'] == 'error'


def test_actual_producer_records_survive_consumer_and_redact_exception_text(tmp_path):
    from urllib.error import HTTPError
    from research.kalshi.frankie_boss.granite_runpod_progress import Progress
    emitted = []
    clock = [0]
    producer = Progress(MANIFEST, tmp_path, 'stage', OWNER,
                        emit=emitted.append, clock=lambda: clock[0])
    producer('download', 'model.safetensors')
    clock[0] = 30
    producer.snapshot()
    clock[0] = 60
    producer.snapshot()
    (tmp_path / 'model.safetensors.partial').write_bytes(b'x' * 500)
    clock[0] = 61
    producer.snapshot()
    producer.failure(HTTPError('https://example.invalid/private-secret', 403,
                               'private-secret', {}, None))
    collector = diagnostics.Collector(OWNER, MANIFEST)
    for entry in emitted:
        collector.ingest(entry)
    exported = collector.export()
    assert [item['reason'] for item in exported['diagnostics']] == [
        'no_progress', 'no_progress', 'recovered', 'error']
    assert exported['active_diagnostics']['stage']['http_status'] == 403
    assert 'private-secret' not in json.dumps(exported)
