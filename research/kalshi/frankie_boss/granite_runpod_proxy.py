"""Bounded text-only Granite proxy. Publish only port8081 through Runpod HTTPS."""
import hmac
import http.client
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import math
import os
import re
import socket
import threading
import time

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
    deadline = min(time.monotonic() + BACKEND_SECONDS, client_deadline)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError()
    connection = http.client.HTTPConnection('127.0.0.1', BACKEND_PORT, timeout=remaining)
    timer = None
    try:
        connection.connect()
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
        if len(raw) != size or time.monotonic() >= deadline:
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


class _Server(HTTPServer):
    request_queue_size = 5

    def handle_error(self, request, client_address):
        pass  # Never emit request or exception data to stderr.


def make_server(secret, address=('0.0.0.0', 8081), *, model):
    """Address is a local-test seam; main fixes deployment port and host."""
    if type(secret) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', secret):
        raise ValueError('required proxy secret invalid')
    if type(model) is not str or not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', model):
        raise ValueError('required served model invalid')
    server = _Server(address, _Handler)
    server.secret = secret.encode('ascii')
    server.authorization = b'Bearer ' + server.secret
    server.model = model
    return server


def main():
    with make_server(os.environ.get('RUNPOD_GRANITE_API_KEY'),
                     model=os.environ.get('GRANITE_SERVED_MODEL')) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
