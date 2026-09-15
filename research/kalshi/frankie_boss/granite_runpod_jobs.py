"""Persistent, at-most-once backend dispatch behind bounded HTTP job operations.

The process lock lives as long as any worker. SQLite FULL commits bind acceptance,
dispatch intent, and exact raw result. A lost dispatch is never replayed.
"""
from contextlib import contextmanager
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time

SCHEMA = 'GRANITE_DURABLE_JOB_V1'
SPOOL = '/opt/ml/granite-jobs-v1'
MAX_REQUEST = 1024 * 1024
MAX_RESPONSE = 4 * 1024 * 1024


class JobConflict(ValueError):
    pass


class JobStoreBusy(RuntimeError):
    pass


def backend_connect():
    connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=10)
    try:
        connection.connect()
        connection.sock.settimeout(None)
        return connection
    except BaseException:
        connection.close()
        raise


def backend_execute(connection, body):
    # Called only after the durable dispatch intent commit. Any exception from
    # here is ambiguous, even one that happens before request() writes a byte.
    connection.request('POST', '/v1/chat/completions', body,
                       {'Content-Type': 'application/json', 'Content-Length': str(len(body)),
                        'Connection': 'close'})
    response = connection.getresponse()
    lengths = response.headers.get_all('Content-Length', [])
    if (response.headers.get_all('Transfer-Encoding') or response.headers.get_all('Content-Encoding')
            or len(lengths) != 1 or not re.fullmatch('[0-9]{1,10}', lengths[0])
            or int(lengths[0]) > MAX_RESPONSE):
        raise ValueError('unbounded backend result')
    raw = response.read(int(lengths[0]))
    if len(raw) != int(lengths[0]):
        raise ValueError('incomplete backend result')
    return response.status, raw


class JobStore:
    def __init__(self, directory=SPOOL, *, connect=backend_connect,
                 execute=backend_execute, thread_factory=threading.Thread, secret=b''):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.directory.is_symlink():
            raise ValueError('job spool symlink refused')
        self.path = self.directory / 'jobs.sqlite'
        if self.path.is_symlink() or (self.directory / 'owner.lock').is_symlink():
            raise ValueError('job state symlink refused')
        self._owner = open(self.directory / 'owner.lock', 'a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self._owner.seek(0)
                # Lock beyond EOF is permitted; do not modify another owner's file.
                msvcrt.locking(self._owner.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._owner.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            self._owner.close()
            raise JobStoreBusy('durable job spool already owned') from None
        self._mutex = threading.RLock()
        self._threads = set()
        self._closed = False
        self.connect, self.execute, self.thread_factory = connect, execute, thread_factory
        self.secret = secret
        try:
            with self._db() as db:
                db.execute('PRAGMA journal_mode=WAL')
                db.execute('''CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY, request_sha256 TEXT NOT NULL, body BLOB NOT NULL,
                    state TEXT NOT NULL, accepted_at REAL NOT NULL, updated_at REAL NOT NULL,
                    dispatch_at REAL, result_status INTEGER, result BLOB,
                    result_sha256 TEXT, result_bytes INTEGER)''')
                db.execute("UPDATE jobs SET state='ambiguous',updated_at=? WHERE state='running'", (time.time(),))
                db.execute("UPDATE jobs SET state='not_dispatched',updated_at=? WHERE state='accepted'", (time.time(),))
            if os.name == 'posix':
                os.chmod(self.path, 0o600)
                descriptor = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY)
                try: os.fsync(descriptor)
                finally: os.close(descriptor)
        except BaseException:
            self._owner.close()
            raise

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.row_factory = sqlite3.Row
        try:
            db.execute('PRAGMA synchronous=FULL')
            with db:
                yield db
        finally:
            db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        with self._mutex:
            self._closed = True
            threads = list(self._threads)
        # No timer may release the ownership lock while a worker can dispatch.
        # Deployment workers are daemon threads; process termination releases
        # the OS lock and restart classifies their persisted intent ambiguous.
        for thread in threads:
            thread.join()
        self._owner.close()

    @staticmethod
    def _identity(job_id):
        if type(job_id) is not str or not re.fullmatch('[0-9a-f]{64}', job_id):
            raise ValueError('64 lowercase hex job id required')

    def status(self, job_id):
        self._identity(job_id)
        with self._db() as db:
            row = db.execute('SELECT * FROM jobs WHERE job_id=?', (job_id,)).fetchone()
        if row is None:
            return None
        value = dict(schema=SCHEMA, job_id=job_id, request_sha256=row['request_sha256'],
                     state=row['state'], accepted_at=row['accepted_at'], updated_at=row['updated_at'])
        if row['dispatch_at'] is not None:
            value['dispatch_at'] = row['dispatch_at']
        if row['state'] == 'completed':
            value.update({name: row[name] for name in ('result_status', 'result_sha256', 'result_bytes')})
        return value

    def result(self, job_id):
        self._identity(job_id)
        with self._db() as db:
            row = db.execute('SELECT state,result,result_sha256,result_bytes FROM jobs WHERE job_id=?', (job_id,)).fetchone()
        if row is None or row['state'] != 'completed':
            return None
        raw = bytes(row['result'])
        if len(raw) != row['result_bytes'] or hashlib.sha256(raw).hexdigest() != row['result_sha256']:
            raise ValueError('persisted job result corruption')
        return raw

    def _state(self, job_id, state):
        with self._db() as db:
            db.execute('UPDATE jobs SET state=?,updated_at=? WHERE job_id=?', (state, time.time(), job_id))

    def submit(self, job_id, request_sha256, body):
        self._identity(job_id)
        if (type(body) is not bytes or not 0 < len(body) <= MAX_REQUEST
                or hashlib.sha256(body).hexdigest() != request_sha256):
            raise ValueError('exact bounded request hash required')
        with self._mutex:
            if self._closed:
                raise RuntimeError('job spool closing')
            with self._db() as db:
                row = db.execute('SELECT * FROM jobs WHERE job_id=?', (job_id,)).fetchone()
                if row is not None and (row['request_sha256'] != request_sha256 or bytes(row['body']) != body):
                    raise JobConflict('job identity already binds different bytes')
                if row is not None and row['state'] != 'not_dispatched':
                    return self.status(job_id)
                now = time.time()
                if row is None:
                    db.execute('INSERT INTO jobs(job_id,request_sha256,body,state,accepted_at,updated_at) VALUES(?,?,?,?,?,?)',
                               (job_id, request_sha256, body, 'accepted', now, now))
                else:
                    db.execute("UPDATE jobs SET state='accepted',updated_at=? WHERE job_id=?", (now, job_id))
            # Acceptance has committed before any scheduling or HTTP reply.
            thread = None
            try:
                thread = self.thread_factory(target=self._work, args=(job_id, body), daemon=True)
                self._threads.add(thread)
                thread.start()
            except Exception:
                if thread is not None:
                    self._threads.discard(thread)
                self._state(job_id, 'not_dispatched')
            return self.status(job_id)

    def _work(self, job_id, body):
        connection = None
        dispatched = False
        try:
            connection = self.connect()
            with self._db() as db:
                now = time.time()
                db.execute("UPDATE jobs SET state='running',dispatch_at=?,updated_at=? WHERE job_id=?", (now, now, job_id))
            dispatched = True
            status, raw = self.execute(connection, body)
            if type(status) is not int or not 100 <= status <= 599 or type(raw) is not bytes or len(raw) > MAX_RESPONSE:
                raise ValueError('invalid backend result')
            # Credential text is never durable, including escaped JSON strings.
            decoded = raw.decode('utf-8', errors='replace')
            decoded = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1], 16)), decoded)
            if self.secret and self.secret.decode('ascii') in decoded:
                self._state(job_id, 'failed')
                return
            with self._db() as db:
                db.execute("UPDATE jobs SET state='completed',updated_at=?,result_status=?,result=?,result_sha256=?,result_bytes=? WHERE job_id=?",
                           (time.time(), status, raw, hashlib.sha256(raw).hexdigest(), len(raw), job_id))
        except Exception:
            # Even failure to record an outcome must not make dispatch repeatable.
            try: self._state(job_id, 'ambiguous' if dispatched else 'not_dispatched')
            except Exception: pass
        finally:
            if connection is not None:
                connection.close()
            with self._mutex:
                self._threads.discard(threading.current_thread())
