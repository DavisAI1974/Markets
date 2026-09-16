import json

import pytest

from research.kalshi.frankie_boss.full_run_progress import RunProbe
from research.kalshi.frankie_boss.runtime_resource_probe import host_snapshot, memory_snapshot


def test_training_event_persists_only_safe_scalar_diagnostics(tmp_path):
    emitted=[]
    probe=RunProbe(tmp_path,'new-run',emit=emitted.append)
    value=probe.training_event(dict(request_id='new-run-cycle-00',stage='forward_start',
        elapsed_seconds=12.5,context_rows=4096))
    assert value['schema']=='FRANKIE_NATIVE_TRAINING_DIAGNOSTIC_V1'
    assert value['stage']=='forward_start'
    assert value['context_rows']==4096
    assert 'message' not in value and 'exception' not in value and 'traceback' not in value
    lines=(tmp_path/'native-training.jsonl').read_text(encoding='utf-8').splitlines()
    assert len(lines)==1 and json.loads(lines[0])==value
    assert emitted and emitted[-1].startswith('FRANKIE_TRAINING_PROGRESS ')


def test_training_event_rejects_unbounded_or_unknown_fields(tmp_path):
    probe=RunProbe(tmp_path,'new-run',emit=lambda _:None)
    with pytest.raises(ValueError,match='stage'):
        probe.training_event(dict(request_id='new-run-cycle-00',stage='tensor_dump',elapsed_seconds=1.0))
    with pytest.raises(ValueError,match='elapsed'):
        probe.training_event(dict(request_id='new-run-cycle-00',stage='forward_start',elapsed_seconds=-1.0))


def test_resource_probe_returns_only_nonnegative_scalar_memory_and_host_facts():
    memory=memory_snapshot()
    for value in memory.values():
        assert type(value) is int and value>=0
    host=host_snapshot()
    assert type(host['logical_cpus']) in (int,type(None))
    assert isinstance(host['cpu_model'],str)
    for name in ('process_rss_bytes','process_peak_rss_bytes','process_private_bytes',
                 'system_memory_total_bytes','system_memory_available_bytes'):
        if name in host:
            assert type(host[name]) is int and host[name]>=0
