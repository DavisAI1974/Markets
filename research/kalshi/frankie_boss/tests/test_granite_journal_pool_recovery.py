"""The journal must drop parent SDK pools without hiding transport failures."""
import io
from types import SimpleNamespace
import pytest
from research.kalshi.frankie_boss import granite_runpod_cloud as cloud
from research.kalshi.frankie_boss import granite_runpod_cloud_control as control

class Client:
    def __init__(self):
        self.events = []
        self.body = b'{"verified":true}'
    def close(self):
        self.events.append('close')
    def get_object(self, **kwargs):
        self.events.append('get')
        return {'Body': io.BytesIO(self.body), 'ContentLength': len(self.body)}
    def put_object(self, **kwargs):
        self.events.append('put')
        self.body = kwargs['Body']

def journal(client):
    value = object.__new__(cloud.Journal)
    value.client, value.bucket, value.prefix = client, 'approved-bucket', 'exact-request/'
    return value

def isolate(monkeypatch):
    monkeypatch.setattr(control, '_IN_WORKER', False)
    def run(operation):
        previous = control._IN_WORKER
        control._IN_WORKER = True
        try:
            return operation()
        finally:
            control._IN_WORKER = previous
    monkeypatch.setattr(control, 'bounded_call', run)

def test_parent_read_pool_closed_before_isolation(monkeypatch):
    isolate(monkeypatch)
    client = Client()
    assert journal(client).get_bytes('receipt.json') == client.body
    assert client.events == ['close', 'get']

def test_write_readback_keeps_worker_pool_local(monkeypatch):
    isolate(monkeypatch)
    client = Client()
    journal(client).put_bytes('receipt.json', b'{"actual":true}', once=True)
    assert client.events == ['close', 'put', 'get']

def test_null_response_transport_failure_is_not_absence():
    class TransportFailure(Exception):
        response = None
    class Broken(Client):
        def get_object(self, **kwargs):
            raise TransportFailure('private details must not be printed')
    with pytest.raises(TransportFailure):
        journal(Broken())._get_bytes('receipt.json')

def test_verified_missing_key_is_absence():
    class Missing(Exception):
        response = {'Error': {'Code': 'NoSuchKey'}}
    class Broken(Client):
        def get_object(self, **kwargs):
            raise Missing()
    assert journal(Broken())._get_bytes('receipt.json') is None
