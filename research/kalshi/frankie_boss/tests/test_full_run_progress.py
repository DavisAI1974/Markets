"""New diagnostics only; no source replay, network or model inference."""
import json
import threading

import pytest

from research.kalshi.frankie_boss.full_run_progress import RunProbe


def probe(tmp_path):
    now, lines = [0.0], []
    instance = RunProbe(tmp_path, 'sun-development', sections=('4.1', '4.2'),
                        clock=lambda: now[0], emit=lines.append)
    return instance, now, lines


def test_stall_reposts_and_recovery_preserves_last_work(tmp_path):
    instance, now, _ = probe(tmp_path)
    instance.advance('frankie_calculation', completed=3, total=10, cursor=15, section='4.1')
    now[0] = 30
    warning = instance.sample()
    assert (warning['kind'], warning['code'], warning['percent'], warning['cursor']) == (
        'warning', 'possible_stall', 30, 15)
    now[0] = 59
    assert instance.sample()['kind'] == 'progress'
    now[0] = 60
    assert instance.sample()['kind'] == 'warning'
    now[0] = 61
    instance.advance('frankie_calculation', completed=4, total=10, cursor=16, section='4.1')
    events = [json.loads(row) for row in (tmp_path/'progress.jsonl').read_text().splitlines()]
    assert events[-2]['code'] == 'progress_resumed'
    assert events[-1]['completed'] == 4
    assert json.loads((tmp_path/'progress.json').read_text()) == events[-1]


def test_heartbeat_does_not_claim_work_advancement(tmp_path):
    instance, now, _ = probe(tmp_path)
    instance.advance('boss_training', completed=1, cursor=10, unit='steps')
    now[0] = 5
    value = instance.sample()
    assert value['completed'] == 1 and value['cursor'] == 10
    assert value['percent'] is None and value['seconds_without_progress'] == 5
    assert value['owner'] == 'boss'


def test_count_cursor_and_section_cannot_silently_regress(tmp_path):
    instance, _, _ = probe(tmp_path)
    instance.advance('causal_delivery', completed=2, cursor=8)
    for values in ({'completed': 1, 'cursor': 8}, {'completed': 2, 'cursor': 7},
                   {'completed': 2, 'cursor': None}, {'completed': 2, 'cursor': 8, 'section': '4.99'}):
        with pytest.raises(ValueError):
            instance.advance('causal_delivery', **values)


def test_failures_do_not_emit_exception_payloads(tmp_path):
    instance, _, lines = probe(tmp_path)
    value = instance.failure(ValueError('PRIVATE KEY OR DATA'))
    assert value['error_type'] == 'ValueError'
    assert 'PRIVATE' not in ''.join(lines) + (tmp_path/'progress.jsonl').read_text()


def test_diagnostic_reopen_preserves_events_without_claiming_resume(tmp_path):
    instance, _, _ = probe(tmp_path)
    instance.advance('checkpoint_save', completed=1, unit='outputs')
    original = (tmp_path/'progress.jsonl').read_bytes()
    with pytest.raises(FileExistsError):
        RunProbe(tmp_path, 'sun-development')
    with pytest.raises(ValueError):
        RunProbe(tmp_path, 'different', resume=True)
    resumed = RunProbe(tmp_path, 'sun-development', resume=True, emit=lambda _: None)
    assert resumed.sample()['completed'] == 0
    assert (tmp_path/'progress.jsonl').read_bytes().startswith(original)


def test_background_persistence_failure_surfaces_before_next_work(tmp_path, monkeypatch):
    instance, _, _ = probe(tmp_path)
    failed = threading.Event()
    def failure():
        failed.set()
        raise OSError('private storage location')
    instance.interval = .005
    monkeypatch.setattr(instance, 'sample', failure)
    thread = threading.Thread(target=instance._heartbeat)
    thread.start()
    assert failed.wait(1)
    thread.join(1)
    assert not thread.is_alive()
    with pytest.raises(RuntimeError, match='diagnostic persistence'):
        instance.advance('boss_training')


def test_controller_boundaries_keep_principal_ownership_separate(tmp_path):
    instance, _, _ = probe(tmp_path)
    for value in [dict(phase='source_validation'), dict(phase='native_reasoning'),
                  dict(phase='native_complete', count=3), dict(phase='critic_request'),
                  dict(phase='critic_complete'), dict(phase='output_persisted', count=3)]:
        result = instance.controller_event(dict(through_cursor=12, **value))
        assert result['owner'] != 'frankie'
    assert result['completed'] == 3 and result['cursor'] == 12


def test_complete_does_not_stall_but_does_not_advance_other_work(tmp_path):
    instance, now, _ = probe(tmp_path)
    instance.advance('complete', completed=1, total=1, unit='outputs')
    now[0] = 100
    assert instance.sample()['kind'] == 'progress'
