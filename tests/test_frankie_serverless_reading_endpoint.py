"""serverless_reading_endpoint.py: the create action's guards, proven without network (fakes for runpodctl and REST).

/ship 2026-09-21 chat 6: the argv print leaked --env HF_TOKEN (Prove-It), create had no same-name check (endpoint
k1sqt0haffm61y is live, so a repeat dispatch would bill a second one), and workers/seqs had no ceiling. No market data.
"""
import importlib.util
import io
import json
import sys
import types
from contextlib import redirect_stdout
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / 'research' / 'kalshi' / 'frankie_boss' / 'operations' / 'serverless_reading_endpoint.py'


@pytest.fixture
def mod(monkeypatch):
    spec = importlib.util.spec_from_file_location('serverless_reading_endpoint_under_test', SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, 'pins', lambda: ('ibm-granite/granite-4.2-8b', 'f8de16cdcdbc6c779ca517604e050d82cc119e44'))
    monkeypatch.setenv('RUNPOD_API_KEY', 'rpa_' + 'k' * 46)
    return m


def args(m, **over):
    base = dict(name='frankie-reading-granite42', gpu='NVIDIA H100 80GB HBM3,NVIDIA H100 NVL', workers_max=8, seqs_per_worker=2,
                idle_timeout=120, execution_timeout=14400, network_volume='', data_centers='', hf_token_env='',
                work_dir=str(over.pop('work_dir')), confirm='')
    base.update(over)
    return types.SimpleNamespace(**base)


def fake_ctl_factory(calls):
    def fake_run(cmd, capture_output=True, text=True):
        calls.append(list(cmd))
        return types.SimpleNamespace(returncode=0, stdout=json.dumps({'id': 'abcdef123456'}), stderr='')
    return fake_run


def test_create_never_prints_the_hf_token(mod, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(mod.subprocess, 'run', fake_ctl_factory(calls))
    monkeypatch.setattr(mod, 'api', lambda key, method, path, body=None, timeout=60: (200, []))
    monkeypatch.setenv('HF_TOKEN_FOR_TEST', 'hf_' + 'S' * 30)
    out = io.StringIO()
    with redirect_stdout(out):
        mod.create(args(mod, work_dir=tmp_path, hf_token_env='HF_TOKEN_FOR_TEST'))
    assert 'hf_' + 'S' * 30 not in out.getvalue()
    assert any('HF_TOKEN=' + 'hf_' + 'S' * 30 in c for c in calls[-1]), 'the token still reaches runpodctl itself'
    receipt = json.loads((tmp_path / 'serverless-reading-endpoint.json').read_text())
    assert 'HF_TOKEN' not in receipt['env']


def test_create_refuses_a_same_named_endpoint_unless_confirmed(mod, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(mod.subprocess, 'run', fake_ctl_factory(calls))
    monkeypatch.setattr(mod, 'api', lambda key, method, path, body=None, timeout=60: (200, [{'id': 'k1sqt0haffm61y', 'name': 'frankie-reading-granite42'}]))
    with pytest.raises(SystemExit) as e:
        mod.create(args(mod, work_dir=tmp_path))
    assert 'k1sqt0haffm61y' in str(e.value)
    assert not any(c[:3] == ['runpodctl', 'serverless', 'create'] for c in calls)
    mod.create(args(mod, work_dir=tmp_path, confirm='create-another'))
    assert any(c[:3] == ['runpodctl', 'serverless', 'create'] for c in calls)


def test_create_refuses_when_the_endpoint_list_cannot_be_read(mod, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(mod.subprocess, 'run', fake_ctl_factory(calls))
    monkeypatch.setattr(mod, 'api', lambda key, method, path, body=None, timeout=60: (401, 'nope'))
    with pytest.raises(SystemExit):
        mod.create(args(mod, work_dir=tmp_path))
    assert calls == []


@pytest.mark.parametrize('over', [dict(workers_max=0), dict(workers_max=17), dict(seqs_per_worker=0), dict(seqs_per_worker=3)])
def test_create_caps_workers_and_seqs(mod, monkeypatch, tmp_path, over):
    monkeypatch.setattr(mod.subprocess, 'run', fake_ctl_factory([]))
    monkeypatch.setattr(mod, 'api', lambda key, method, path, body=None, timeout=60: (200, []))
    with pytest.raises(SystemExit):
        mod.create(args(mod, work_dir=tmp_path, **over))


def test_create_passes_exactly_one_gpu_id_and_records_the_rest(mod, monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(mod.subprocess, 'run', fake_ctl_factory(calls))
    monkeypatch.setattr(mod, 'api', lambda key, method, path, body=None, timeout=60: (200, []))
    with redirect_stdout(io.StringIO()):
        mod.create(args(mod, work_dir=tmp_path))
    cmd = calls[-1]
    assert cmd.count('--gpu-id') == 1 and cmd[cmd.index('--gpu-id') + 1] == 'NVIDIA H100 80GB HBM3'
    receipt = json.loads((tmp_path / 'serverless-reading-endpoint.json').read_text())
    assert receipt['box_config']['gpu_type_ids'] == ['NVIDIA H100 80GB HBM3', 'NVIDIA H100 NVL']
    assert '--workers-min' in cmd and cmd[cmd.index('--workers-min') + 1] == '0'
