import copy
import pytest
import os
import time

from research.kalshi.frankie_boss import granite_runpod_cloud_control as control


def intent():
    nonce = 'a' * 32
    return dict(schema='GRANITE_CLOUD_INTENT_V1', nonce=nonce,
                name='granite-smoke-' + nonce, image=control.granite_runpod.IMAGE,
                start=1000, deadline=1600)


def pod():
    item = intent()
    return dict(id='abc123', name=item['name'], image=item['image'],
                env={'RUNPOD_SMOKE_OWNER': item['nonce']})


def test_unrelated_pods_are_never_deleted():
    calls = []
    class API:
        def request(self, method, path, body=None):
            calls.append((method, path))
            other = pod()
            other['env'] = {}
            return {'pods': [other]}
    assert control.cleanup_once(API(), intent())['status'] == 'absent_in_inventory'
    assert calls == [('GET', '/v2/pods')]


def test_delete_requires_followup_absence():
    calls = []
    class API:
        def request(self, method, path, body=None):
            calls.append((method, path))
            if path == '/v2/pods':
                return {'pods': [pod()]}
            if method == 'DELETE':
                return None
            if len(calls) == 4:
                raise control.ProviderError(404)
            return pod()
    assert control.cleanup_once(API(), intent()) == {'status': 'confirmed_absent', 'pod_id': 'abc123'}
    assert [m for m, _ in calls] == ['GET', 'GET', 'DELETE', 'GET']


def test_forbidden_read_is_not_absence():
    class API:
        def request(self, *args):
            raise control.ProviderError(403)
    with pytest.raises(control.ProviderError):
        control.cleanup_once(API(), intent())


def test_cleanup_accepts_provider_documented_underscore_id():
    item = pod()
    item['id'] = 'pod_abc123'
    calls = []
    class API:
        def request(self, method, path, body=None):
            calls.append((method, path))
            assert path == '/v2/pods/pod_abc123'
            if len(calls) == 4:
                raise control.ProviderError(404)
            return item if method == 'GET' else None
    assert control.cleanup_once(API(), intent(), item['id'])['status'] == 'confirmed_absent'


@pytest.mark.parametrize('pod_id', ['../pods', 'abc?x=1', 'abc/def'])
def test_unsafe_id_refused_before_control_io(pod_id):
    class API:
        def request(self, *args):
            pytest.fail('unsafe path reached API')
    with pytest.raises(ValueError):
        control.cleanup_once(API(), intent(), pod_id)


def test_identity_change_refuses_delete():
    class API:
        def request(self, method, path, body=None):
            assert method == 'GET'
            if path == '/v2/pods':
                return {'pods': [pod()]}
            changed = pod()
            changed['image'] = 'other'
            return changed
    with pytest.raises(ValueError):
        control.cleanup_once(API(), intent())


def test_duplicate_ownership_is_ambiguous():
    class API:
        def request(self, *args):
            return {'pods': [pod(), pod()]}
    with pytest.raises(ValueError):
        control.cleanup_once(API(), intent())


@pytest.mark.parametrize('field,value', [('deadline', 1700), ('nonce', 'bad'), ('image', 'other')])
def test_bad_intent_refused_before_io(field, value):
    item = intent()
    item[field] = value
    class API:
        def request(self, *args):
            pytest.fail('I/O before intent validation')
    with pytest.raises(ValueError):
        control.cleanup_once(API(), item)


def test_creation_requires_fresh_matching_watchdog_arm():
    import hashlib
    import json
    item = intent()
    digest = hashlib.sha256(json.dumps(item, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    control.assert_creation_window(item, {'intent_sha256': digest, 'at': 1000}, 1001)
    for armed, now in [({}, 1001), ({'intent_sha256': digest, 'at': 1000}, 1021),
                       ({'intent_sha256': digest, 'at': 1420}, 1420)]:
        with pytest.raises(ValueError):
            control.assert_creation_window(item, armed, now)


@pytest.mark.skipif(os.name != 'posix', reason='production isolation requires Linux fork')
def test_stalled_operation_is_killed_with_wall_deadline(tmp_path):
    marker = tmp_path / 'late-network-side-effect'
    def stalled():
        time.sleep(1)
        marker.write_text('should never execute')
    start = time.monotonic()
    with pytest.raises(TimeoutError):
        control.bounded_call(stalled, seconds=0.1)
    assert time.monotonic() - start < 0.9
    time.sleep(1.1)
    assert not marker.exists()


@pytest.mark.skipif(os.name != 'posix', reason='production isolation requires Linux fork')
def test_isolated_result_larger_than_pipe_buffer_and_provider_error():
    assert control.bounded_call(lambda: b'x' * 1048576) == b'x' * 1048576
    def forbidden():
        raise control.ProviderError(403)
    with pytest.raises(control.ProviderError) as error:
        control.bounded_call(forbidden)
    assert error.value.status == 403
