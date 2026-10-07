"""ONE shared S3 transport for Frankie's box (Greg, 2026-10-07 night session 5: "the aws tool upgrades that root got from
the deep dive" in every piece). Standard library only at import (boto3 / awscrt are imported inside the calls that use
them), so a POSIX wrapper's inline Python, the ingest tool and the offload can all import it from the dispatched
checkout: `sys.path.insert(0, <checkout>/deploy/aws/box); import frankie_box_s3_transport as T`.

THE INTERFACE (every call returns one receipt dict, schema FRANKIE_S3_TRANSPORT_V1; it never raises for a transfer
outcome, only for a caller error such as a destination outside its directory):

  fetch_url(url, dest, *, expected_bytes, expected_sha256=None, range_streams=15, ranges=None, probe_dir=None, say=print,
            on_bytes=None)
      A presigned GET (the box's role reads nothing in S3 itself). Above RANGED_ABOVE (64 MiB) with range_streams > 1:
      concurrent 16 MiB byte-range GETs written at their offsets into <dest>.part; at or below it: one stream with
      HTTP-range resume after a dropped connection. The sha256 is computed IN ORDER WHILE THE BYTES LAND (an ordered
      hand-off of finished ranges, at most `window` ranges held), so the partition is read and hashed ONCE, never
      re-read from disk. Then bytes and sha256 are compared with the expected values: equal -> <dest>.part renamed to
      <dest> (create-only: a file that appeared at <dest> meanwhile is never overwritten, the download is kept aside as
      .part.late-<ts>); different -> kept aside as .part.rejected-<ts>. `ranges` = a ThreadPoolExecutor the caller
      shares between members (the NIC budget is not multiplied); None = one of its own, ended before return.
      on_bytes(n) hears every n bytes landed (a caller's aggregate WorkProbe over several members).
  download(bucket, key, dest, *, region, expected_bytes=None, expected_sha256=None, client=None)
      A signed GET through boto3: the CRT transfer client first (awscrt==0.31.2 in /opt/frankie-box/venv; 128 MiB parts,
      concurrency 16), the classic multipart client after it (16 MiB parts, 15 streams), the REASON the CRT was not
      used or failed on the receipt (`transport_fallback`). boto3 writes the file itself, so the sha256 is one
      sequential read after it (`hash_pass: after_download`, 4 MiB reads). Same create-only and keep-aside rules.
  upload(path, bucket, key, *, region, sha256=None, extra_args=None, client=None)
      A signed PUT through boto3, CRT first (128 MiB parts, concurrency 16) then classic (same sizes), the fallback
      reason on the receipt. The caller decides whether the object may be written (head check, If-None-Match).

  Receipt fields (additive; consumers read only what they know): schema, op, dest/path, bucket/key or url_host, status
  ('restored'|'uploaded'|'refused'), reason (when refused), bytes, sha256, expected_bytes, expected_sha256, transport
  ('ranged-<N>x16MiB'|'single-stream'|'crt'|'classic'), transport_fallback (None or why), hash_pass ('in_stream'|
  'after_download'|'given'|'read_once'), seconds, bytes_per_second, retries (list of {range|offset, attempt, error}),
  stalls (list of report-only stall notes: no byte moved for STALL_SECONDS; nothing is stopped), kept_aside.

PROBES: with probe_dir, a FRANKIE_WORK_PROBE_V1 progress.json (frankie_box_progress.Probe when importable, else the same
schema written here) carries stage 'fetch:<name>', completed/total in bytes, refreshed at most every 15 s; the stage
heartbeat (frankie_box_stage_progress) reads it and computes units/min and its own report-only 600 s stall flag.

BOUNDED: every network read has a 120 s socket timeout and at most `attempts` tries per range (backoff 5..60 s); a stalled
transfer therefore ends as 'refused' with its reason, never as a hang. Nothing here deletes or overwrites anything.
Placement: the calling thread's CPU affinity is inherited (the caller runs inside its booking: taskset).
Re-hash rule (Greg's open call (c), not decided): nothing here skips a hash because a file's stat is unchanged.
"""
import hashlib
import json
import os
import threading
import time

SCHEMA = 'FRANKIE_S3_TRANSPORT_V1'
RANGE_BYTES = 16 << 20
RANGED_ABOVE = 64 << 20
RANGE_STREAMS = 15
READ_CHUNK = 4 << 20                 # large sequential reads (the box's read-ahead is 4 MiB)
CRT_PART = 128 << 20
CRT_CONCURRENCY = 16
CLASSIC_DOWNLOAD = dict(multipart_threshold=64 << 20, multipart_chunksize=16 << 20, max_concurrency=15)
CLASSIC_UPLOAD = dict(multipart_threshold=64 << 20, multipart_chunksize=128 << 20, max_concurrency=16)
STALL_SECONDS = 600
SOCKET_TIMEOUT = 120
ATTEMPTS = 6


def _receipt(op, **fields):
    return dict(schema=SCHEMA, op=op, at=round(time.time(), 3), retries=[], stalls=[], transport_fallback=None,
                kept_aside=None, **fields)


def sha256_file(path):
    """sha256 of a file in 4 MiB reads (one sequential pass)."""
    h = hashlib.sha256()
    with open(path, 'rb', buffering=0) as f:
        for block in iter(lambda: f.read(READ_CHUNK), b''):
            h.update(block)
    return h.hexdigest()


class _Probe:
    """A FRANKIE_WORK_PROBE_V1 progress.json (frankie_box_progress.Probe when importable; the same schema otherwise)."""

    def __init__(self, directory, stage, total):
        self.stage, self.total, self.inner, self.directory = stage, total, None, directory
        if not directory:
            return
        try:
            import frankie_box_progress
            self.inner = frankie_box_progress.Probe(directory)
        except Exception:  # noqa: BLE001 - the probe never changes the transfer
            self.inner = None
        self.last = 0.0
        self.lock = threading.Lock()

    def update(self, done, state='running', force=False):
        if not self.directory:
            return
        try:
            done = min(int(done), self.total) if self.total is not None else int(done)
            if self.inner is not None:
                self.inner.update(self.stage, done, self.total, state=state, force=force)
                return
            with self.lock:
                now = time.monotonic()
                if not force and now - self.last < 15:
                    return
                value = dict(schema='FRANKIE_WORK_PROBE_V1', request_sha256=None, phase=None, stage=self.stage,
                             completed=done, total=self.total, in_flight=0, failed=0, state=state, at=time.time(),
                             percent=round(100 * done / self.total, 2) if self.total else None, pid=os.getpid(),
                             process_token=None)
                os.makedirs(self.directory, exist_ok=True)
                path = os.path.join(self.directory, 'progress.json')
                with open(path + '.pending', 'w', encoding='utf-8') as f:
                    f.write(json.dumps(value, sort_keys=True) + '\n')
                os.replace(path + '.pending', path)
                self.last = now
        except Exception:  # noqa: BLE001
            pass


WorkProbe = _Probe        # public name: a caller's aggregate probe (e.g. one per fetched block, fed by on_bytes)


class _Watch:
    """Bytes moved, the probe and the report-only stall note (no byte for STALL_SECONDS: noted once per stall)."""

    def __init__(self, receipt, probe, say, name, on_bytes=None):
        self.receipt, self.probe, self.say, self.name, self.on_bytes = receipt, probe, say, name, on_bytes
        self.done, self.moved, self.noted = 0, time.monotonic(), False
        self.lock, self.stop = threading.Lock(), threading.Event()
        self.thread = threading.Thread(target=self._loop, name='transport-watch', daemon=True)
        self.thread.start()

    def add(self, n):
        with self.lock:
            self.done += n
            self.moved, self.noted = time.monotonic(), False
        self.probe.update(self.done)
        if self.on_bytes is not None:
            try:
                self.on_bytes(n)
            except Exception:  # noqa: BLE001 - a caller's counter never changes the transfer
                pass

    def _loop(self):
        while not self.stop.wait(15):
            with self.lock:
                idle = time.monotonic() - self.moved
                if idle >= STALL_SECONDS and not self.noted:
                    self.noted = True
                    note = dict(at=round(time.time(), 1), bytes_done=self.done, idle_s=round(idle),
                                rule='report-only: no byte moved for %d s; the socket timeout and the bounded retries '
                                     'end the transfer if it does not recover' % STALL_SECONDS)
                    self.receipt['stalls'].append(note)
                    self.say('   STALLED %s: %s' % (self.name, json.dumps(note)))

    def end(self, state):
        self.stop.set()
        self.thread.join(timeout=20)
        self.probe.update(self.done, state=state, force=True)


class _OrderedHash:
    """sha256 over ranges handed in any order, consumed strictly in order; at most `window` ranges ahead are admitted."""

    def __init__(self, window):
        self.h, self.next, self.held, self.window = hashlib.sha256(), 0, {}, max(1, window)
        self.cv, self.failed = threading.Condition(), False

    def admit(self, index):
        with self.cv:
            while not self.failed and index - self.next >= self.window:
                self.cv.wait(5)
            return not self.failed

    def add(self, index, data):
        with self.cv:
            self.held[index] = data
            while self.next in self.held:
                self.h.update(self.held.pop(self.next))
                self.next += 1
            self.cv.notify_all()

    def fail(self):
        with self.cv:
            self.failed = True
            self.cv.notify_all()


def _settle(receipt, part, dest, got_bytes, got_sha, expected_bytes, expected_sha256, say, name, started):
    """Compare, then rename create-only or keep aside; the receipt's status and reason."""
    receipt.update(bytes=got_bytes, sha256=got_sha, seconds=round(time.time() - started, 3))
    if receipt['seconds'] > 0:
        receipt['bytes_per_second'] = round(got_bytes / receipt['seconds'])
    if (expected_bytes is not None and got_bytes != expected_bytes) or (expected_sha256 and got_sha != expected_sha256):
        aside = part + '.rejected-%d' % int(time.time())
        os.replace(part, aside)
        receipt.update(status='refused', kept_aside=aside,
                       reason='bytes or sha256 differ from the expected values; the bytes are kept aside')
        say('REFUSED (digest):', name)
        return receipt
    if os.path.exists(dest):
        aside = part + '.late-%d' % int(time.time())
        os.replace(part, aside)
        receipt.update(status='refused', kept_aside=aside,
                       reason='a file appeared at the destination during the download; not overwritten')
        say('REFUSED (late):', name)
        return receipt
    os.replace(part, dest)
    receipt['status'] = 'restored'
    return receipt


def _get(url, headers):
    import urllib.request
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=SOCKET_TIMEOUT)


def fetch_url(url, dest, *, expected_bytes, expected_sha256=None, range_streams=RANGE_STREAMS, ranges=None,
              probe_dir=None, say=print, attempts=ATTEMPTS, range_bytes=RANGE_BYTES, ranged_above=RANGED_ABOVE,
              window=None, on_bytes=None):
    """See the module docstring. `expected_bytes` is required: the object size the manifest/map declares."""
    if type(expected_bytes) is not int or expected_bytes < 0:
        raise ValueError('expected_bytes (the declared size) required')
    name = os.path.basename(dest)
    host = url.split('?', 1)[0].split('/')[2] if '://' in url else None
    receipt = _receipt('fetch_url', dest=str(dest), url_host=host, expected_bytes=expected_bytes,
                       expected_sha256=expected_sha256, hash_pass='in_stream')
    part, started = str(dest) + '.part', time.time()
    probe = _Probe(probe_dir, 'fetch:' + name, expected_bytes)
    watch = _Watch(receipt, probe, say, name, on_bytes)
    state = 'failed'
    try:
        ranged = expected_bytes > ranged_above and range_streams > 1
        if ranged:
            receipt['transport'] = 'ranged-%dx%dMiB' % (range_streams, range_bytes >> 20)
            ok, sha = _ranged(url, part, expected_bytes, range_bytes, range_streams, ranges, window, attempts,
                              receipt, watch, say, name)
        else:
            receipt['transport'] = 'single-stream'
            ok, sha = _single(url, part, expected_bytes, attempts, receipt, watch, say, name)
        if not ok:
            receipt.update(status='refused', reason='download failed after the bounded retries (see retries)',
                           seconds=round(time.time() - started, 3), bytes=watch.done)
            say('REFUSED (download):', name)
            return receipt
        _settle(receipt, part, str(dest), os.path.getsize(part), sha, expected_bytes, expected_sha256, say, name, started)
        state = 'complete' if receipt['status'] == 'restored' else 'refused'
        return receipt
    finally:
        watch.end(state)


def _ranged(url, part, size, range_bytes, streams, shared, window, attempts, receipt, watch, say, name):
    from concurrent.futures import ThreadPoolExecutor
    count = (size + range_bytes - 1) // range_bytes
    order = _OrderedHash(window or streams + 4)
    fd = os.open(part, os.O_RDWR | os.O_CREAT | os.O_TRUNC, 0o644)
    lock = threading.Lock()

    def one(i):
        if not order.admit(i):
            return False
        start, end = i * range_bytes, min(size, (i + 1) * range_bytes) - 1
        for attempt in range(attempts):
            try:
                with _get(url, {'Range': 'bytes=%d-%d' % (start, end)}) as r:
                    if r.status != 206:
                        raise OSError('HTTP %s, not 206 Partial Content' % r.status)
                    data = r.read()
                if len(data) != end - start + 1:
                    raise OSError('short range: %d of %d bytes' % (len(data), end - start + 1))
                os.pwrite(fd, data, start)
                watch.add(len(data))
                order.add(i, data)
                return True
            except Exception as error:  # noqa: BLE001 - retried, then the range is a failure on the receipt
                with lock:
                    receipt['retries'].append(dict(range=i, attempt=attempt + 1, error='%s: %s' % (
                        type(error).__name__, str(error)[:160])))
                say('   retry %d range %d of %s: %s' % (attempt + 1, i, name, error))
            time.sleep(min(60, 5 * (attempt + 1)))
        order.fail()
        return False

    own = shared is None
    pool = ThreadPoolExecutor(max(1, streams), thread_name_prefix='range') if own else shared
    try:
        ok = all(list(pool.map(one, range(count))))
        os.fsync(fd)
    finally:
        os.close(fd)
        if own:
            pool.shutdown(wait=True)
    return ok and order.next == count, order.h.hexdigest()


def _single(url, part, size, attempts, receipt, watch, say, name):
    h, have = hashlib.sha256(), 0
    with open(part, 'wb', buffering=0) as f:
        for attempt in range(attempts):
            try:
                headers = {'Range': 'bytes=%d-' % have} if have else {}
                if have >= size:
                    break
                with _get(url, headers) as r:
                    if have and r.status != 206:
                        raise OSError('resume refused: HTTP %s, not 206' % r.status)
                    for block in iter(lambda: r.read(READ_CHUNK), b''):
                        f.write(block)
                        h.update(block)
                        have += len(block)
                        watch.add(len(block))
                break
            except Exception as error:  # noqa: BLE001 - resumed from the bytes already hashed
                receipt['retries'].append(dict(offset=have, attempt=attempt + 1,
                                               error='%s: %s' % (type(error).__name__, str(error)[:160])))
                say('   retry %d of %s at byte %d: %s' % (attempt + 1, name, have, error))
                time.sleep(min(60, 5 * (attempt + 1)))
        else:
            return False, h.hexdigest()
        os.fsync(f.fileno())
    return True, h.hexdigest()


def _configs(kind):
    """[(label, TransferConfig)]: CRT first when awscrt imports, then classic; and the reason CRT is absent (or None)."""
    from boto3.s3.transfer import TransferConfig
    classic = CLASSIC_DOWNLOAD if kind == 'download' else CLASSIC_UPLOAD
    configs, why = [('classic', TransferConfig(**classic))], None
    try:
        import awscrt  # noqa: F401
        configs.insert(0, ('crt', TransferConfig(preferred_transfer_client='crt', multipart_threshold=64 << 20,
                                                 multipart_chunksize=CRT_PART, max_concurrency=CRT_CONCURRENCY)))
    except Exception as error:  # noqa: BLE001 - no awscrt in this interpreter: classic only, the reason recorded
        why = 'awscrt not importable (%s: %s); classic client' % (type(error).__name__, str(error)[:120])
    return configs, why


def _run_configs(receipt, kind, call):
    """call(config) for CRT then classic; the transport used and every fallback reason on the receipt; True if one did."""
    try:
        configs, why = _configs(kind)
    except Exception as error:  # noqa: BLE001 - no boto3: nothing to try
        receipt.update(transport=None, transport_fallback='boto3 not importable (%s: %s)' % (
            type(error).__name__, str(error)[:120]))
        return False
    reasons = [why] if why else []
    for label, config in configs:
        try:
            call(config)
            receipt['transport'] = label
            receipt['transport_fallback'] = '; '.join(reasons) or None
            return True
        except Exception as error:  # noqa: BLE001 - the next client; every reason kept
            reasons.append('%s failed (%s: %s)' % (label, type(error).__name__, str(error)[:200]))
    receipt.update(transport=None, transport_fallback='; '.join(reasons))
    return False


def download(bucket, key, dest, *, region, expected_bytes=None, expected_sha256=None, client=None, say=print):
    """See the module docstring."""
    name, started = os.path.basename(dest), time.time()
    receipt = _receipt('download', dest=str(dest), bucket=bucket, key=key, region=region, expected_bytes=expected_bytes,
                       expected_sha256=expected_sha256, hash_pass='after_download')
    part = str(dest) + '.part'
    try:
        import boto3
        s3 = client or boto3.client('s3', region_name=region)
    except Exception as error:  # noqa: BLE001
        receipt.update(status='refused', reason='no S3 client (%s: %s)' % (type(error).__name__, str(error)[:160]))
        return receipt
    if not _run_configs(receipt, 'download', lambda config: s3.download_file(bucket, key, part, Config=config)):
        receipt.update(status='refused', reason='every transfer client failed (see transport_fallback)',
                       seconds=round(time.time() - started, 3))
        say('REFUSED (download):', name)
        return receipt
    return _settle(receipt, part, str(dest), os.path.getsize(part), sha256_file(part), expected_bytes, expected_sha256,
                   say, name, started)


def upload(path, bucket, key, *, region, sha256=None, extra_args=None, client=None):
    """See the module docstring."""
    started = time.time()
    size = os.path.getsize(path)
    receipt = _receipt('upload', path=str(path), bucket=bucket, key=key, region=region, bytes=size, sha256=sha256,
                       hash_pass='given' if sha256 else None)
    try:
        import boto3
        s3 = client or boto3.client('s3', region_name=region)
    except Exception as error:  # noqa: BLE001
        receipt.update(status='refused', reason='no S3 client (%s: %s)' % (type(error).__name__, str(error)[:160]))
        return receipt
    ok = _run_configs(receipt, 'upload', lambda config: s3.upload_file(str(path), bucket, key, ExtraArgs=extra_args or {},
                                                                       Config=config))
    receipt.update(status='uploaded' if ok else 'refused', seconds=round(time.time() - started, 3))
    if not ok:
        receipt['reason'] = 'every transfer client failed (see transport_fallback)'
    elif receipt['seconds'] > 0:
        receipt['bytes_per_second'] = round(size / receipt['seconds'])
    return receipt
