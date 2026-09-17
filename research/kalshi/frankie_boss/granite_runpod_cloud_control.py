"""Scoped control-plane and cleanup helpers for a single hosted smoke."""
import hashlib
import http.client
import json
import re
import multiprocessing
import pickle
import socket
import time

from . import granite_runpod


_IN_WORKER = False


def bounded_call(operation, seconds=12):
    """Linux runner: isolate DNS, SDK calls and body reads in a killable child.

    The IPC channel carries only this process's own result, never external pickle.
    A timed-out POST remains ambiguous at the provider; callers must reconcile it.
    """
    global _IN_WORKER
    if _IN_WORKER:
        return operation()
    context = multiprocessing.get_context('fork')  # Fail closed on other platforms.
    reader, writer = socket.socketpair()
    def worker():
        global _IN_WORKER
        _IN_WORKER = True
        reader.close()
        try:
            result = ('ok', operation())
        except ProviderError as error:
            result = ('provider', error.status)
        except ValueError as error:
            result = ('value', str(error))
        except BaseException as error:
            detail = type(error).__name__
            if isinstance(error, AttributeError):
                # Retain code locations only; exception arguments and object
                # representations can contain credentials or request content.
                frames = []
                trace = error.__traceback__
                while trace is not None and len(frames) < 16:
                    frame = trace.tb_frame
                    module = frame.f_globals.get('__name__', '')
                    function = frame.f_code.co_name
                    if (isinstance(module, str) and re.fullmatch(r'[A-Za-z0-9_.]+', module)
                            and re.fullmatch(r'[A-Za-z0-9_<>]+', function)):
                        frames.append(dict(module=module, function=function, line=trace.tb_lineno))
                    trace = trace.tb_next
                attribute = getattr(error, 'name', None)
                if isinstance(attribute, str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,63}', attribute):
                    detail += ' missing_attribute=' + attribute
                detail += ' object_type=' + type(getattr(error, 'obj', None)).__name__
                detail += ' code_locations=' + json.dumps(frames, sort_keys=True)
            result = ('error', detail)
        try:
            writer.sendall(pickle.dumps(result))
        finally:
            writer.close()
    process = context.Process(target=worker, daemon=True)
    deadline = time.monotonic() + seconds
    try:
        process.start()
        writer.close()
        chunks = []
        total = 0
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('cloud operation wall deadline')
            reader.settimeout(remaining)
            chunk = reader.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > 4194304:
                raise ValueError('oversized isolated result')
        kind, result = pickle.loads(b''.join(chunks))
        if kind == 'provider':
            raise ProviderError(result)
        if kind == 'value':
            raise ValueError(result)
        if kind != 'ok':
            raise RuntimeError('isolated operation failed: ' + result)
        return result
    finally:
        reader.close()
        writer.close()
        if process.pid is not None:
            process.join(timeout=0.05)
            if process.is_alive():
                process.kill()
                process.join(timeout=0.5)


class ProviderError(RuntimeError):
    def __init__(self, status):
        self.status = status
        super().__init__('Runpod request failed: HTTP ' + str(status))


class Runpod:
    def __init__(self, key):
        if not isinstance(key, str) or not key.strip():
            raise ValueError('Runpod credential required')
        self.key = key

    def request(self, method, path, body=None):
        return bounded_call(lambda: self._request(method, path, body))

    def _request(self, method, path, body=None):
        if method not in ('GET', 'POST', 'DELETE') or not path.startswith('/v2/'):
            raise ValueError('control-plane request refused')
        connection = http.client.HTTPSConnection('api.runpod.io', timeout=10)
        try:
            raw = None if body is None else json.dumps(body, allow_nan=False).encode()
            connection.request(method, path, raw, {
                'Authorization': 'Bearer ' + self.key, 'Accept': 'application/json',
                'Content-Type': 'application/json',
            })
            response = connection.getresponse()
            data = response.read(1048577)
            if response.status not in (200, 201, 204):
                raise ProviderError(response.status)
            if len(data) > 1048576:
                raise ValueError('oversized control response')
            return json.loads(data) if data else None
        finally:
            connection.close()


def validate_intent(intent):
    nonce = intent.get('nonce', '') if type(intent) is dict else ''
    accepted_names = {'granite-smoke-' + nonce, 'granite-smoke-' + nonce + '-migration'}
    if (type(intent) is not dict or intent.get('schema') != 'GRANITE_CLOUD_INTENT_V1'
            or not re.fullmatch(r'[0-9a-f]{32}', nonce)
            or intent.get('name') not in accepted_names
            or intent.get('image') != granite_runpod.IMAGE
            or type(intent.get('start')) not in (int, float)
            or type(intent.get('deadline')) not in (int, float)
            or intent['deadline'] - intent['start'] not in (600, 900, 1200, 1800)
            or intent.get('cleanup_mode', 'terminate') not in ('terminate', 'stop_retain')):
        raise ValueError('invalid immutable launch intent')
    return intent


def owned_pod(pod, intent):
    validate_intent(intent)
    return (type(pod) is dict and pod.get('name') == intent['name']
            and pod.get('image') == intent['image']
            and pod.get('env', {}).get('RUNPOD_SMOKE_OWNER') == intent['nonce']
            and re.fullmatch(r'[A-Za-z0-9_-]{1,128}', pod.get('id', '')) is not None)


def find_owned(api, intent):
    validate_intent(intent)
    rows = api.request('GET', '/v2/pods')['pods']
    if type(rows) is not list:
        raise ValueError('invalid inventory')
    matches = [pod for pod in rows if owned_pod(pod, intent)]
    if len(matches) > 1:
        raise ValueError('ambiguous launch ownership')
    return matches[0] if matches else None


def cleanup_once(api, intent, pod_id=None, on_discovered=None):
    validate_intent(intent)
    if pod_id is not None:
        if not isinstance(pod_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', pod_id):
            raise ValueError('invalid registered Pod ID')
        try:
            pod = api.request('GET', '/v2/pods/' + pod_id)
        except ProviderError as error:
            if error.status == 404:
                return {'status': 'confirmed_absent', 'pod_id': pod_id}
            raise
        if not owned_pod(pod, intent):
            raise ValueError('registered resource identity changed')
    else:
        pod = find_owned(api, intent)
    if pod is None:
        return {'status': 'absent_in_inventory', 'pod_id': None}
    if on_discovered is not None:
        on_discovered(pod['id'])  # Keep ownership evidence even when later I/O fails.
    path = '/v2/pods/' + pod['id']
    # Recheck exact identity immediately before deletion.
    try:
        current = api.request('GET', path)
    except ProviderError as error:
        if error.status == 404:
            return {'status': 'confirmed_absent', 'pod_id': pod['id']}
        raise
    if not owned_pod(current, intent):
        raise ValueError('resource identity changed')
    try:
        api.request('DELETE', path)
    except ProviderError as error:
        if error.status != 404:
            raise
    try:
        api.request('GET', path)
    except ProviderError as error:
        if error.status == 404:
            return {'status': 'confirmed_absent', 'pod_id': pod['id']}
        raise
    return {'status': 'termination_pending', 'pod_id': pod['id']}


def assert_creation_window(intent, armed, now):
    validate_intent(intent)
    digest = hashlib.sha256(json.dumps(intent, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if (type(armed) is not dict or armed.get('intent_sha256') != digest
            or not intent['start'] <= now < intent['deadline'] - 180
            or not 0 <= now - armed.get('at', 0) <= 20):
        raise ValueError('fresh watchdog arm and creation window required')
