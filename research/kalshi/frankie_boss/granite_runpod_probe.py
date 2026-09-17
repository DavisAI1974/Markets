"""One durable host smoke attempt; no allocation, cleanup or command-line entrypoint."""
import base64
from contextlib import closing
from dataclasses import asdict, dataclass
import hashlib
import http.client
import json
from pathlib import Path
import re
import socket
import sqlite3
import ssl
import threading
import time

from . import granite_runpod_admission as admission
from . import granite_run_artifacts as artifacts
from .granite_sagemaker import _final_text

MAX_RESPONSE = 65536


def _remaining(deadline):
    value = deadline - time.monotonic()
    if value <= 0:
        raise TimeoutError('probe budget exhausted')
    return value


def _shutdown(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


MAX_PROBE_BODY_BYTES = 4096  # HTTP body BYTES of the fixed smoke probe request; not a token context


def https_exchange(pod_id, method, path, body, key, timeout):
    """Fixed public Runpod route; stdlib DNS may return after timeout, never sends late."""
    if (not re.fullmatch(r'[a-z0-9]{1,64}', pod_id)
            or type(key) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', key)
            or (method, path) not in (('GET', '/health'), ('POST', '/v1/chat/completions'))
            or type(body) is not bytes or len(body) > MAX_PROBE_BODY_BYTES
            or not 0 < timeout <= 80):
        raise ValueError('fixed probe transport contract required')
    deadline = time.monotonic() + timeout
    context = ssl.create_default_context()
    connection = http.client.HTTPSConnection(pod_id + '-8081.proxy.runpod.net', 443,
                                            timeout=_remaining(deadline), context=context)
    timer = None
    try:
        connection.connect()
        timer = threading.Timer(_remaining(deadline), _shutdown, (connection.sock,))
        timer.daemon = True
        timer.start()
        connection.request(method, path, body, {'Authorization': 'Bearer ' + key,
            'Content-Type': 'application/json', 'Content-Length': str(len(body)), 'Connection': 'close'})
        response = connection.getresponse()
        sizes = response.headers.get_all('Content-Length', [])
        if (len(sizes) != 1 or not re.fullmatch(r'[0-9]{1,10}', sizes[0])
                or response.headers.get_all('Transfer-Encoding')
                or response.headers.get_all('Content-Encoding')
                or response.getheader('Content-Type', '').split(';')[0].strip().lower() != 'application/json'):
            raise ValueError('bounded JSON response required')
        size = int(sizes[0])
        if size > MAX_RESPONSE:
            raise ValueError('response bound')
        body = response.read(size)
        if len(body) != size:
            raise ValueError('short response')
        _remaining(deadline)
        return response.status, body
    finally:
        if timer is not None:
            timer.cancel()
        connection.close()


@dataclass(frozen=True)
class ProbeReceipt:
    pod_id: str
    admission_sha256: str
    request_sha256: str
    health_checks: int
    attempted: bool
    outcome: str
    response_base64: str | None = None


def run_probe(*, pod_id, expected_pod_id, admission_receipt, expected_admission_sha256,
              journal_path, api_key, exchange=None):
    """Caller must pin actual approved Pod and preserve the same durable host journal."""
    deadline = time.monotonic() + 90
    if (type(pod_id) is not str or not re.fullmatch(r'[a-z0-9]{1,64}', pod_id)
            or pod_id != expected_pod_id):
        raise ValueError('independently approved Pod identity required')
    if type(api_key) is not str or not re.fullmatch(r'[A-Za-z0-9_-]{32,256}', api_key):
        raise ValueError('required proxy key invalid')
    # Freeze caller-owned input before validation and before any asynchronous I/O.
    admitted = artifacts.strict_json(artifacts.canonical(admission_receipt))
    body = admission.validate_receipt(admitted, expected_admission_sha256)
    request = artifacts.strict_json(body)
    request_hash = hashlib.sha256(body).hexdigest()
    path = Path(journal_path)
    if not path.is_absolute() or path.is_symlink() or (path.exists() and not path.is_file()):
        raise ValueError('absolute durable journal file required')
    exchange = exchange or https_exchange
    checks = 0
    with closing(sqlite3.connect(path, timeout=0)) as db:
        db.execute('PRAGMA journal_mode=DELETE')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('CREATE TABLE IF NOT EXISTS attempts (pod_id TEXT PRIMARY KEY, '
                   'request_sha256 TEXT NOT NULL, admission_sha256 TEXT NOT NULL, outcome TEXT)')
        db.commit()
        if db.execute('SELECT 1 FROM attempts WHERE pod_id=?', (pod_id,)).fetchone():
            raise ValueError('Pod inference attempt already consumed')
        for _ in range(3):
            try:
                budget = min(5, _remaining(deadline))
                checks += 1
                status, health = exchange(pod_id, 'GET', '/health', b'', api_key, budget)
                _remaining(deadline)
                if type(status) is int and status == 200 and health == b'{"status":"ok"}':
                    break
            except Exception:
                pass
        else:
            return ProbeReceipt(pod_id, expected_admission_sha256, request_hash,
                                checks, False, 'health_unavailable')
        # FULL synchronous commit happens before inference I/O. Unique Pod ID
        # makes racing invocations lose before POST, including changed receipts.
        try:
            db.execute('INSERT INTO attempts VALUES (?, ?, ?, NULL)',
                       (pod_id, request_hash, expected_admission_sha256))
            db.commit()
        except sqlite3.IntegrityError:
            raise ValueError('Pod inference attempt already consumed') from None
        outcome, encoded = 'transport_error', None
        try:
            status, raw = exchange(pod_id, 'POST', '/v1/chat/completions', body,
                                   api_key, min(80, _remaining(deadline)))
            _remaining(deadline)
            outcome = 'response_refused'
            if (type(status) is int and status == 200 and type(raw) is bytes
                    and len(raw) <= MAX_RESPONSE and api_key.encode() not in raw):
                text = _final_text(raw, request['model'])
                response = artifacts.strict_json(raw)
                if api_key in json.dumps(response, ensure_ascii=False):
                    raise ValueError('credential echo')
                usage = response.get('usage')
                if (type(usage) is dict and all(type(usage.get(k)) is int for k in
                        ('prompt_tokens', 'completion_tokens', 'total_tokens'))
                        and usage['prompt_tokens'] == admitted['input_tokens']
                        and 1 <= usage['completion_tokens'] <= admitted['output_tokens']
                        and usage['total_tokens'] == usage['prompt_tokens'] + usage['completion_tokens']
                        and usage['total_tokens'] <= admitted['context'] and text.rstrip() == 'READY'):
                    outcome, encoded = 'completed', base64.b64encode(raw).decode('ascii')
        except Exception:
            pass  # Fixed outcome only: never persist exception text or provider error bytes.
        receipt = ProbeReceipt(pod_id, expected_admission_sha256, request_hash,
                               checks, True, outcome, encoded)
        db.execute('UPDATE attempts SET outcome=? WHERE pod_id=?',
                   (artifacts.canonical(asdict(receipt)).decode(), pod_id))
        db.commit()
        return receipt
