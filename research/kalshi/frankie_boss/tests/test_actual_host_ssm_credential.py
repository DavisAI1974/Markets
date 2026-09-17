import json
from pathlib import Path

import pytest

from research.kalshi.frankie_boss.operations import run_actual_sunday as actual


class SSM:
    def __init__(self, value='k' * 40, kind='SecureString'):
        self.value, self.kind, self.calls = value, kind, []

    def get_parameter(self, **kwargs):
        self.calls.append(kwargs)
        return {'Parameter': {'Type': self.kind, 'Value': self.value}}


def host(tmp_path, monkeypatch, client):
    import boto3
    monkeypatch.setattr(boto3, 'client', lambda *a, **kw: client)
    h = actual.ActualHost.__new__(actual.ActualHost)
    h.host = {'pod_credential_ssm': {'name': '/markets/pod-service', 'region': 'us-east-2',
                                    'trigger_directory': str(tmp_path)}}
    return h


def write_trigger(tmp_path, request_hash, schema, **fields):
    directory = tmp_path / request_hash
    directory.mkdir(exist_ok=True)
    (directory / (schema + '.json')).write_text(json.dumps(dict(schema=schema, **fields)))


def test_ssm_key_is_read_once_for_multiple_cycles_and_never_written(tmp_path, monkeypatch):
    client = SSM()
    h = host(tmp_path, monkeypatch, client)
    for request_id in ('a' * 64, 'b' * 64):
        write_trigger(tmp_path, request_id, 'FRANKIE_ACTUAL_EXECUTE_V1',
                      readiness_directory='ready', service_pins_sha256='c' * 64)
        key, trigger = h.read_execution_trigger('FRANKIE_ACTUAL_EXECUTE_V1',
                     ('readiness_directory', 'service_pins_sha256'), request_id)
        assert key == client.value
        assert 'service_key' not in trigger
    assert client.calls == [{'Name': '/markets/pod-service', 'WithDecryption': True}]
    assert all(client.value not in p.read_text() for p in tmp_path.rglob('*.json'))


@pytest.mark.parametrize('value,kind', [('short', 'SecureString'), ('k'*40, 'String')])
def test_bad_ssm_parameter_refuses_without_disclosing_value(tmp_path, monkeypatch, value, kind):
    h = host(tmp_path, monkeypatch, SSM(value, kind))
    write_trigger(tmp_path, 'a'*64, 'FRANKIE_ACTUAL_RESUME_JOB_V1',
                  request_id='a'*64, service_pins_sha256='c'*64)
    with pytest.raises(ValueError) as error:
        h.read_execution_trigger('FRANKIE_ACTUAL_RESUME_JOB_V1',
                                 ('request_id', 'service_pins_sha256'), 'a'*64)
    assert value not in str(error.value)


def test_a_credential_in_the_readiness_trigger_is_refused_before_ssm(tmp_path, monkeypatch):
    client = SSM()
    h = host(tmp_path, monkeypatch, client)
    write_trigger(tmp_path, 'a'*64, 'FRANKIE_ACTUAL_EXECUTE_V1', service_key=client.value,
                  readiness_directory='ready', service_pins_sha256='c'*64)
    with pytest.raises(ValueError):
        h.read_execution_trigger('FRANKIE_ACTUAL_EXECUTE_V1',
                                 ('readiness_directory', 'service_pins_sha256'), 'a'*64)
    assert client.calls == []


def test_unconfigured_host_keeps_existing_stdin_protocol(monkeypatch):
    h = actual.ActualHost.__new__(actual.ActualHost)
    h.host = {}
    expected = ('private', {'schema': 'example'})
    monkeypatch.setattr(actual, 'read_trigger', lambda *a: expected)
    assert h.read_execution_trigger('example', (), 'a'*64) == expected
