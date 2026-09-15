"""One scoped smoke controller or independent GitHub-runner watchdog."""
from dataclasses import asdict
import hashlib
import http.client
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import time
import urllib.parse

from . import granite_runpod_admission as admission
from . import granite_runpod_package as package
from . import granite_runpod_probe as probe
from . import granite_run_artifacts as artifacts
from . import granite_runpod_cloud_control as control

BASE = '8aba96aa46ee95b410496f9e3154fb2d96395f56'
BUNDLE_SHA = '32312f5334efa8f002df30482fd1823d9b2b49ae0484f9ccf2798de37378b24c'
ADMISSION_SHA = '3af163e3732cc0fc586164a4f5981870dfdbadb0616393d64506fe5557b5ef7c'
ROOT = Path(__file__).parent
OUT = Path('work/cloud-receipts')


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


class Journal:
    def __init__(self):
        import boto3
        from botocore.config import Config
        config = Config(connect_timeout=5, read_timeout=10,
                        retries={'total_max_attempts': 1, 'mode': 'standard'})
        account = boto3.client('sts', region_name='us-east-1', config=config).get_caller_identity()['Account']
        self.client = boto3.client('s3', region_name='us-east-1', config=config)
        self.bucket = artifacts.ensure_scoped_bucket(self.client, account)
        self.client.close()  # No connected HTTP pool is inherited by isolated calls.
        run_id = os.environ['GITHUB_RUN_ID']
        if not run_id.isascii() or not run_id.isdecimal():
            raise ValueError('GitHub run identity required')
        self.prefix = 'runpod-smoke/' + run_id + '/'

    def put_bytes(self, name, data, *, once=False):
        return control.bounded_call(lambda: self._put_bytes(name, data, once=once))

    def _put_bytes(self, name, data, *, once=False):
        if not name or '..' in name or name.startswith('/') or len(data) > 1048576:
            raise ValueError('journal bounds')
        kwargs = {'IfNoneMatch': '*'} if once else {}
        self.client.put_object(Bucket=self.bucket, Key=self.prefix + name,
                               Body=data, ServerSideEncryption='AES256', **kwargs)
        if self.get_bytes(name) != data:
            raise ValueError('journal readback mismatch')

    def get_bytes(self, name):
        return control.bounded_call(lambda: self._get_bytes(name))

    def _get_bytes(self, name):
        try:
            result = self.client.get_object(Bucket=self.bucket, Key=self.prefix + name)
        except Exception as error:
            if getattr(error, 'response', {}).get('Error', {}).get('Code') == 'NoSuchKey':
                return None
            raise
        with result['Body'] as body:
            if result['ContentLength'] > 1048576:
                raise ValueError('oversized journal object')
            data = body.read(1048577)
            if len(data) != result['ContentLength']:
                raise ValueError('incomplete journal object')
            return data

    def put(self, name, value, *, once=False):
        self.put_bytes(name, canonical(value), once=once)

    def get(self, name):
        raw = self.get_bytes(name)
        return None if raw is None else artifacts.strict_json(raw)


def save(name, value):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_bytes(canonical(value))


def bootstrap_command(rows, bundle_sha, bucket, directory=package.ROOT):
    """Private AWS downloads followed by the unchanged pre-import verifier."""
    roster = rows + [{'path': 'runpod_bundle.json', 'size': None, 'sha256': bundle_sha}]
    prefix = f'''import hashlib,http.client,json,os,pathlib,shutil,signal,urllib.parse
p=pathlib.Path({directory!r})
for parent in (p,*p.parents):
 if parent.is_symlink(): raise SystemExit('bootstrap symlink refused')
p.mkdir(parents=True,exist_ok=True)
urls=json.loads(os.environ.pop('RP_BOOTSTRAP_URLS'))
rows={roster!r}
if set(urls)!={{row['path'] for row in rows}}: raise SystemExit('bootstrap URL roster differs')
def expired(*args): raise TimeoutError('bootstrap download deadline')
signal.signal(signal.SIGALRM,expired)
signal.alarm(60)
for row in rows:
 u=urllib.parse.urlsplit(urls[row['path']])
 if u.scheme!='https' or u.hostname not in ({(bucket + '.s3.amazonaws.com')!r},{(bucket + '.s3.us-east-1.amazonaws.com')!r}) or u.port not in (None,443) or u.username or u.fragment: raise SystemExit('bootstrap origin refused')
 c=http.client.HTTPSConnection(u.hostname,timeout=10)
 try:
  c.request('GET',u.path+'?'+u.query,headers={{'Connection':'close'}})
  response=c.getresponse()
  data=response.read(65537)
  if response.status!=200 or len(data)>65536 or (row['size'] is not None and len(data)!=row['size']) or hashlib.sha256(data).hexdigest()!=row['sha256']: raise SystemExit('bootstrap byte mismatch')
  with (p/row['path']).open('xb') as file: file.write(data)
 finally: c.close()
signal.alarm(0)
free=shutil.disk_usage(p).free
if free < 17592970510+5000000000: raise SystemExit('insufficient model disk')
print('GRANITE_DISK '+json.dumps({{'free_bytes':free,'required_bytes':22592970510}}),flush=True)
'''
    code = prefix + package.preexec_code(rows, bundle_sha, directory=directory)
    return 'python3 -c ' + shlex.quote('exec(bytes.fromhex(' + repr(code.encode().hex()) + ').decode())')


def stage_bootstrap(journal):
    source = Path('work/cloud-bootstrap-source')
    destination = Path('work/cloud-bootstrap')
    source.mkdir(parents=True, exist_ok=True)
    for name in package.FILES:
        data = subprocess.run(['git', 'show', BASE + ':research/kalshi/frankie_boss/' + name],
                              check=True, capture_output=True, timeout=10).stdout
        (source / name).write_bytes(data)
    receipt = package.package(source, destination)
    if receipt['bundle_sha256'] != BUNDLE_SHA:
        raise ValueError('reviewed bootstrap changed')
    urls = {}
    for name in (*package.FILES, 'runpod_bundle.json'):
        key = 'bootstrap/' + name
        journal.put_bytes(key, (destination / name).read_bytes(), once=True)
        urls[name] = journal.client.generate_presigned_url('get_object',
            Params={'Bucket': journal.bucket, 'Key': journal.prefix + key}, ExpiresIn=900)
    save('staging.json', {'bundle_sha256': BUNDLE_SHA, 'files': receipt['files'], 'readback_verified': True})
    return receipt, urls


def watchdog(journal, api):
    wait_until = time.time() + 180
    intent = None
    while time.time() < wait_until:
        journal.put('watchdog-ready.json', {'at': time.time()})
        intent = journal.get('intent.json')
        if intent is not None:
            control.validate_intent(intent)
            break
        time.sleep(3)
    if intent is None:
        raise ValueError('no launch intent; watchdog exited without resources')
    digest = hashlib.sha256(canonical(intent)).hexdigest()
    result = {'status': 'not_checked'}
    pod_id = None
    def remember(discovered_id):
        nonlocal pod_id
        pod_id = discovered_id
        save('watchdog-owned-pod.json', {'id': pod_id})
    while time.time() < intent['deadline'] + 30:
        finished = None
        if time.time() < intent['deadline'] - 120:
            try:
                journal.put('armed.json', {'intent_sha256': digest, 'at': time.time()})
                registered = journal.get('pod.json')
                if registered:
                    pod_id = registered['id']
                finished = journal.get('controller-finished.json')
            except Exception:
                pass  # Once armed, S3 loss must not prevent independent termination.
        if finished or time.time() >= intent['deadline'] - 120:
            try:
                result = control.cleanup_once(api, intent, pod_id, remember)
                if result.get('pod_id'):
                    pod_id = result['pod_id']
                save('watchdog-cleanup.json', result)
                try:
                    journal.put('watchdog-cleanup.json', result)
                except Exception:
                    pass
                if result['status'] == 'confirmed_absent':
                    # Before the creation window closes, a delayed create can still arrive.
                    if finished and finished.get('creation_closed') is True:
                        return result
                    if time.time() >= intent['deadline']:
                        return result
            except Exception as error:
                result = {'status': 'unresolved', 'error_type': type(error).__name__}
                save('watchdog-cleanup.json', result)
        time.sleep(5)
    if result.get('status') != 'confirmed_absent':
        raise RuntimeError('independent cleanup unresolved')
    return result


def finish(journal, api, intent, creation_closed, pod_id):
    try:
        journal.put('controller-finished.json', {'creation_closed': creation_closed})
    except Exception:
        pass
    if pod_id is None:
        # Only the watchdog reconciles a lost create response, so it retains the ID.
        result = {'status': 'deferred_to_watchdog', 'pod_id': None}
        save('controller-cleanup.json', result)
        return result
    try:
        result = control.cleanup_once(api, intent, pod_id)
        save('controller-cleanup.json', result)
        try:
            journal.put('controller-cleanup.json', result)
        except Exception:
            pass
        return result
    except Exception as error:
        result = {'status': 'unresolved', 'error_type': type(error).__name__}
        save('controller-cleanup.json', result)
        return result


def startup_logs(api, pod_id):
    return control.bounded_call(lambda: _startup_logs(api, pod_id), seconds=10)


def _startup_logs(api, pod_id):
    connection = http.client.HTTPSConnection('api.runpod.io', timeout=4)
    records = {}
    deadline = time.monotonic() + 8
    try:
        connection.request('GET', '/v2/pods/' + pod_id + '/logs?source=container&tail=500',
                           headers={'Authorization': 'Bearer ' + api.key, 'Accept': 'text/event-stream'})
        response = connection.getresponse()
        if response.status != 200:
            return records
        total = 0
        while time.monotonic() < deadline and total < 1048576:
            raw = response.readline(65537)
            if not raw or len(raw) > 65536:
                break
            total += len(raw)
            if not raw.startswith(b'data:'):
                continue
            value = json.loads(raw[5:])
            line = value.get('line', '')
            for prefix, key in [('GRANITE_RUNPOD_STARTUP ', 'startup'), ('GRANITE_DISK ', 'disk')]:
                if line.startswith(prefix):
                    records[key] = artifacts.strict_json(line[len(prefix):].encode())
            if set(records) == {'startup', 'disk'}:
                break
    except (TimeoutError, OSError):
        pass
    finally:
        connection.close()
    return records


def validate_runtime(records, admitted):
    startup = records['startup']['startup']
    facts = startup['runtime']
    if (startup['image_digest'] != control.granite_runpod.startup.IMAGE_DIGEST
            or startup['mount']['manifest_sha256'] != admitted['model_manifest_sha256']
            or any(facts['packages'].get(k) != v for k, v in admission.TOKENIZER_VERSIONS.items())
            or facts['gpu_count'] != 1 or 'L40S' not in facts['gpu']
            or facts['gpu_total_memory'] < 45000000000
            or startup['environment']['GRANITE_MAX_MODEL_LEN'] != '4096'
            or startup['environment']['GRANITE_SERVED_MODEL'] != 'granite42-smoke'
            or records['disk']['free_bytes'] < 22592970510):
        raise ValueError('hosted runtime differs from admission')


def controller(journal, api):
    if os.environ['GITHUB_RUN_ATTEMPT'] != '1':
        raise ValueError('controller rerun refused')
    if journal.get('intent.json') is not None:
        raise ValueError('launch intent already consumed')
    admitted_raw = (ROOT / 'runpod_cloud_admission.json').read_bytes()
    admitted = artifacts.strict_json(admitted_raw)
    admission.validate_receipt(admitted, ADMISSION_SHA)
    until = time.time() + 120
    while time.time() < until:
        ready = journal.get('watchdog-ready.json')
        if ready and 0 <= time.time() - ready.get('at', 0) < 20:
            break
        time.sleep(3)
    else:
        raise ValueError('independent watchdog unavailable')
    receipt, urls = stage_bootstrap(journal)
    nonce = secrets.token_hex(16)
    started = int(time.time())
    intent = {'schema': 'GRANITE_CLOUD_INTENT_V1', 'nonce': nonce,
              'name': 'granite-smoke-' + nonce, 'image': control.granite_runpod.IMAGE,
              'start': started, 'deadline': started + 600}
    journal.put('intent.json', intent, once=True)
    save('intent.json', intent)
    for _ in range(12):
        armed = journal.get('armed.json')
        if armed:
            control.assert_creation_window(intent, armed, time.time())
            break
        time.sleep(3)
    else:
        raise ValueError('watchdog did not arm')
    api_key = secrets.token_urlsafe(40)
    environment = json.loads((ROOT / 'runpod_cloud_environment.json').read_text())
    command = bootstrap_command(receipt['files'], BUNDLE_SHA, journal.bucket)
    environment.update({'SUPERVISOR_PROGRAM__APP_COMMAND': command,
        'RUNPOD_SUPERVISOR_COMMAND_SHA256': hashlib.sha256(command.encode()).hexdigest(),
        'RUNPOD_GRANITE_API_KEY': api_key, 'RUNPOD_GRANITE_LIFETIME_SECONDS': '480',
        'RP_BOOTSTRAP_URLS': json.dumps(urls), 'RUNPOD_SMOKE_OWNER': nonce})
    body = {'name': intent['name'], 'image': intent['image'], 'cloud': 'SECURE',
            'gpu': {'id': 'NVIDIA L40S', 'count': 1, 'minCudaVersion': '13.0',
                    'minRamPerGpu': 64, 'minVcpuCountPerGpu': 8},
            'dataCenterIds': ['US-MO-1', 'US-TX-4', 'US-TX-3'], 'disk': 100,
            'mounts': {'persistent': {'path': '/opt/ml', 'size': 50}},
            'ports': ['8081/http'], 'env': environment, 'startSsh': False, 'startJupyter': False}
    creation_closed = False
    pod_id = None
    outcome = {'outcome': 'incomplete'}
    try:
        control.assert_creation_window(intent, journal.get('armed.json'), time.time())
        pod = api.request('POST', '/v2/pods', body)
        creation_closed = True
        if not control.owned_pod(pod, intent):
            raise ValueError('created Pod identity differs')
        pod_id = pod['id']
        save('pod.json', {'id': pod_id, 'name': pod['name'], 'cost': pod.get('cost')})
        journal.put('pod.json', {'id': pod_id}, once=True)
        if type(pod.get('cost')) not in (int, float) or not 0 < pod['cost'] <= 1.25:
            raise ValueError('actual hourly price outside approved smoke envelope')
        records = {}
        while time.time() < intent['deadline'] - 210:
            current = api.request('GET', '/v2/pods/' + pod_id)
            if not control.owned_pod(current, intent):
                raise ValueError('Pod identity changed')
            records.update(startup_logs(api, pod_id))
            if set(records) == {'startup', 'disk'}:
                validate_runtime(records, admitted)
                try:
                    status, data = probe.https_exchange(pod_id, 'GET', '/health', b'', api_key, 5)
                    if status == 200 and data == b'{"status":"ok"}':
                        break
                except Exception:
                    pass  # Readiness may lag startup verification; inference is not retried.
            time.sleep(5)
        else:
            raise TimeoutError('startup incomplete in ten-minute window')
        if time.time() >= intent['deadline'] - 210:
            raise TimeoutError('insufficient probe and cleanup time')
        save('runtime.json', records)
        journal.put('runtime.json', records)
        journal_path = (OUT / 'probe.sqlite').resolve()
        def exchange(pod_id, method, path, body, key, timeout):
            if method == 'POST':
                # The existing probe has committed FULL-sync SQLite before this callback.
                journal.put_bytes('probe.sqlite', journal_path.read_bytes(), once=True)
                if time.time() >= intent['deadline'] - 180:
                    raise TimeoutError('inference deadline')
            return probe.https_exchange(pod_id, method, path, body, key, timeout)
        result = probe.run_probe(pod_id=pod_id, expected_pod_id=pod_id,
            admission_receipt=admitted, expected_admission_sha256=ADMISSION_SHA,
            journal_path=journal_path, api_key=api_key, exchange=exchange)
        outcome = asdict(result)
        journal.put_bytes('probe-completed.sqlite', journal_path.read_bytes())
        journal.put('probe.json', outcome)
        save('probe.json', outcome)
    finally:
        cleanup_result = finish(journal, api, intent, creation_closed, pod_id)
    return completed_outcome(outcome, cleanup_result)


def completed_outcome(outcome, cleanup_result):
    if outcome.get('outcome') != 'completed':
        raise RuntimeError('hosted smoke incomplete')
    if cleanup_result.get('status') != 'confirmed_absent':
        raise RuntimeError('hosted response received but cleanup unresolved')
    return outcome


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    mode = sys.argv[1] if len(sys.argv) == 2 else ''
    if mode not in ('controller', 'watchdog'):
        raise ValueError('explicit mode required')
    try:
        result = globals()[mode](Journal(), control.Runpod(os.environ['RUNPOD_API_KEY']))
        print('GRANITE_CLOUD_RESULT ' + json.dumps({'mode': mode, 'status': 'completed'}), flush=True)
    except Exception as error:
        save(mode + '-failure.json', {'error_type': type(error).__name__})
        print('GRANITE_CLOUD_FAILURE ' + json.dumps({'mode': mode, 'error_type': type(error).__name__}), flush=True)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
