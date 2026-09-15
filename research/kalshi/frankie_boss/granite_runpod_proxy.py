"""Bounded text-only Granite proxy. Publish only port8081 through Runpod HTTPS."""
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
import re
import socket
import threading
import time
try:
    from .granite_runpod_jobs import JobStore, JobConflict, SPOOL
except ImportError:
    from granite_runpod_jobs import JobStore, JobConflict, SPOOL

BACKEND_PORT = 8080
MAX_REQUEST = 1024 * 1024
MAX_RESPONSE = 4 * 1024 * 1024
BACKEND_SECONDS = 80
CLIENT_SECONDS = 90
CLIENT_IDLE_SECONDS = 5


def _stop(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            raise ValueError('duplicate key')
        value[key] = item
    return value


def _json(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite')))


def _chat(raw, model):
    data = _json(raw)
    allowed = {'model', 'messages', 'max_tokens', 'temperature', 'top_p', 'seed',
               'stream', 'chat_template_kwargs'}
    if type(data) is not dict or set(data) - allowed or data.get('model') != model:
        raise ValueError('chat contract')
    if data.get('stream', False) is not False:
        raise ValueError('streaming unsupported')
    template = data.get('chat_template_kwargs')
    if (type(template) is not dict or set(template) != {'enable_thinking'}
            or template['enable_thinking'] is not False):
        raise ValueError('thinking must be disabled')
    n = data.get('max_tokens')
    if type(n) is not int or not 1 <= n <= 1200:
        raise ValueError('token bound')
    if type(data.get('temperature')) not in (int, float) or data['temperature'] != 0:
        raise ValueError('deterministic temperature required')
    if 'seed' in data and (type(data['seed']) is not int or not 0 <= data['seed'] < 2**63):
        raise ValueError('seed bound')
    if 'top_p' in data and (type(data['top_p']) not in (float, int)
                           or not math.isfinite(data['top_p']) or not 0 < data['top_p'] <= 1):
        raise ValueError('top_p bound')
    messages = data.get('messages')
    if type(messages) is not list or not 1 <= len(messages) <= 256:
        raise ValueError('message bound')
    for message in messages:
        if (type(message) is not dict or set(message) != {'role', 'content'}
                or message['role'] not in ('system', 'user', 'assistant')
                or type(message['content']) is not str):
            raise ValueError('text-only messages required')


def _length(headers, limit, *, optional=False):
    values = headers.get_all('Content-Length', [])
    if headers.get_all('Transfer-Encoding') or headers.get_all('Content-Encoding'):
        raise ValueError('encoded body')
    if not values and optional:
        return 0
    if len(values) != 1 or not re.fullmatch(r'[0-9]{1,10}', values[0]):
        raise ValueError('ambiguous body length')
    size = int(values[0])
    if size > limit:
        raise OverflowError('body bound')
    return size


def _backend(method, path, body, client_deadline):
    deadline = None if client_deadline is None else min(time.monotonic() + BACKEND_SECONDS, client_deadline)
    remaining = 10 if deadline is None else deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError()
    connection = http.client.HTTPConnection('127.0.0.1', BACKEND_PORT, timeout=remaining)
    timer = None
    try:
        connection.connect()
        if deadline is None:
            connection.sock.settimeout(None)
        else:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError()
            timer = threading.Timer(remaining, _stop, (connection.sock,))
            timer.daemon = True
            timer.start()
        connection.request(method, path, body, {'Content-Type': 'application/json',
                                               'Content-Length': str(len(body)), 'Connection': 'close'})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('upstream status')
        size = _length(response.headers, 1024 if method == 'GET' else MAX_RESPONSE)
        raw = response.read(size)
        if len(raw) != size or (deadline is not None and time.monotonic() >= deadline):
            raise ValueError('incomplete upstream')
        if method == 'GET':
            return b'{"status":"ok"}'
        if response.getheader('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            raise ValueError('upstream content type')
        if type(_json(raw)) is not dict:
            raise ValueError('upstream object required')
        return raw
    finally:
        if timer is not None:
            timer.cancel()
        connection.close()


class _Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def setup(self):
        self.request.settimeout(CLIENT_IDLE_SECONDS)
        super().setup()
        self._deadline = time.monotonic() + CLIENT_SECONDS
        self._timer = threading.Timer(CLIENT_SECONDS, _stop, (self.connection,))
        self._timer.daemon = True
        self._timer.start()

    def finish(self):
        self._timer.cancel()
        super().finish()

    def log_message(self, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        self._reply(code, b'{"error":"request refused"}')

    def _reply(self, code, body):
        self.close_connection = True
        try:
            self.send_response_only(code)
            for key, value in [('Content-Type', 'application/json'), ('Content-Length', str(len(body))),
                               ('Connection', 'close'), ('Cache-Control', 'no-store'),
                               ('X-Content-Type-Options', 'nosniff')]:
                self.send_header(key, value)
            self.end_headers()
            if getattr(self, 'command', None) != 'HEAD':
                self.wfile.write(body)
        except OSError:
            pass

    def do_GET(self):
        self.do_POST()

    def do_POST(self):
        if sum(len(k) + len(v) for k, v in self.headers.items()) > 16384:
            return self._reply(431, b'{"error":"request refused"}')
        auth = self.headers.get_all('Authorization', [])
        supplied = auth[0].encode('utf-8') if len(auth) == 1 else b''
        if not hmac.compare_digest(supplied, self.server.authorization):
            return self._reply(401, b'{"error":"unauthorized"}')
        health = self.command == 'GET' and self.path == '/health'
        if self.server.jobs is not None and not health:
            return self._job_request()
        if not health and (self.command != 'POST' or self.path != '/v1/chat/completions'):
            return self._reply(404, b'{"error":"request refused"}')
        try:
            size = _length(self.headers, MAX_REQUEST, optional=health)
            if health and size != 0:
                raise ValueError('health body')
            if not health and self.headers.get_all('Content-Type') != ['application/json']:
                raise ValueError('content type')
            if self.headers.get_all('Expect'):
                raise ValueError('expect unsupported')
            body = self.rfile.read(size)
            if len(body) != size:
                raise ValueError('short request')
            if not health:
                _chat(body, self.server.model)
                if self.server.open_ended:
                    # Only an authenticated, fully received and validated body
                    # selects open decode. Header/body ingress remains bounded.
                    self._timer.cancel()
                    self._deadline = None
                    self.connection.settimeout(None)
        except OverflowError:
            return self._reply(413, b'{"error":"request refused"}')
        except (ValueError, OSError, RecursionError):
            return self._reply(400, b'{"error":"request refused"}')
        try:
            result = _backend(self.command, self.path, body, self._deadline)
            if self.server.secret in result:
                raise ValueError('credential echo')
        except (OSError, ValueError, http.client.HTTPException, RecursionError, OverflowError):
            return self._reply(503 if health else 502, b'{"error":"upstream unavailable"}')
        self._reply(200, result)

    def _job_request(self):
        match = re.fullmatch(r'/v1/jobs/([0-9a-f]{64})(/result)?', self.path)
        if (match is None or self.command not in ('POST', 'GET')
                or (self.command == 'POST' and match[2])):
            return self._reply(404, b'{"error":"request refused"}')
        job_id, result_path = match.groups()
        try:
            size = _length(self.headers, MAX_REQUEST, optional=self.command == 'GET')
            if self.headers.get_all('Expect') or (self.command == 'GET' and size):
                raise ValueError('job request framing')
            if self.command == 'POST':
                if self.headers.get_all('Content-Type') != ['application/json']:
                    raise ValueError('job content type')
                hashes = self.headers.get_all('X-Granite-Request-SHA256', [])
                if len(hashes) != 1 or not re.fullmatch('[0-9a-f]{64}', hashes[0]):
                    raise ValueError('job request hash required')
                body = self.rfile.read(size)
                if len(body) != size:
                    raise ValueError('short job request')
                _chat(body, self.server.model)
                # Never persist the credential even if accidentally included in
                # JSON escapes. Auth itself stays outside the durable model body.
                if self.server.secret.decode('ascii') in json.dumps(_json(body), ensure_ascii=False):
                    raise ValueError('credential body refused')
                control = self.server.jobs.submit(job_id, hashes[0], body)
                return self._reply(202, json.dumps(control, separators=(',', ':')).encode())
            control = self.server.jobs.status(job_id)
            if control is None:
                return self._reply(404, b'{"error":"unknown job"}')
            if result_path and control['state'] == 'completed':
                return self._reply(200, self.server.jobs.result(job_id))
            self._reply(202 if result_path else 200, json.dumps(control, separators=(',', ':')).encode())
        except JobConflict:
            self._reply(409, b'{"error":"job identity conflict"}')
        except OverflowError:
            self._reply(413, b'{"error":"request refused"}')
        except (ValueError, OSError, RecursionError):
            self._reply(400, b'{"error":"request refused"}')
        except Exception:
            self._reply(503, b'{"error":"job storage unavailable"}')


class _Server(ThreadingHTTPServer):
    request_queue_size = 5

    def handle_error(self, request, client_address):
        pass  # Never emit request or exception data to stderr.

    def server_close(self):
        super().server_close()
        if getattr(self, 'jobs', None) is not None:
            self.jobs.close()


def make_server(secret, address=('0.0.0.0', 8081), *, model, open_ended=False,
                transport_protocol='direct_v1', spool=SPOOL):
    """Address is a local-test seam; main fixes deployment port and host."""
    if type(secret) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', secret):
        raise ValueError('required proxy secret invalid')
    if type(model) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', model):
        raise ValueError('required served model invalid')
    if type(open_ended) is not bool:
        raise ValueError('explicit proxy runtime mode required')
    if transport_protocol not in ('direct_v1', 'jobs_v1'):
        raise ValueError('explicit proxy transport protocol required')
    server = _Server(address, _Handler)
    server.secret = secret.encode('ascii')
    server.authorization = b'Bearer ' + server.secret
    server.model = model
    server.open_ended = open_ended
    server.jobs = None
    try:
        if transport_protocol == 'jobs_v1':
            server.jobs = JobStore(spool, secret=server.secret)
    except BaseException:
        server.server_close()
        raise
    return server


def main():
    with make_server(os.environ.get('RUNPOD_GRANITE_API_KEY'),
                     model=os.environ.get('GRANITE_SERVED_MODEL'),
                     transport_protocol=os.environ.get('GRANITE_TRANSPORT_PROTOCOL', 'direct_v1'),
                     open_ended=os.environ.get('RUNPOD_GRANITE_LIFETIME_SECONDS') == 'none') as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
