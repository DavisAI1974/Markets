"""Upload only the pinned snapshot using a memory-only, encrypted S3 capability."""
import base64
import hashlib
import http.client
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit, parse_qs
import zipfile

ROOT = Path(__file__).parent
REPO = 'DavisAI1974/Markets'
LOCAL_REPO = Path('C:/Users/A/Documents/Codex/2026-09-14/latest-addendum-host-controls-completed-launch-2/work/Markets-full-frankie')
PRIVATE = Path('C:/Users/A/Documents/Codex/2026-09-15/first-run-using-agent-skills-continue/work/bootstrap-jobs/recipient-private.pem')

def api(path):
    result = subprocess.run(['gh','api','repos/'+REPO+'/'+path], capture_output=True, check=True)
    return json.loads(result.stdout)

def write(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())

def progress(**values):
    value = dict(pid=os.getpid(), at=time.time(), **values)
    temp = ROOT/'upload-progress.next.json'
    temp.write_text(json.dumps(value), encoding='utf-8')
    os.replace(temp, ROOT/'upload-progress.json')

def main(run_id):
    ready = json.loads((ROOT/'snapshot-ready.json').read_bytes())
    publication = json.loads((ROOT/'publication.json').read_bytes())
    run = api('actions/runs/'+run_id)
    if (run['head_sha'] != publication['commit']
            or run['path'] != '.github/workflows/frankie_parallel_source.yml'):
        raise ValueError('GitHub run identity differs from published verification code')
    write(ROOT/'upload-process.json', dict(pid=os.getpid(), run_id=run_id, head_sha=run['head_sha']))
    name = 'parallel-source-upload-capability-'+run_id
    while True:
        artifacts = api('actions/runs/'+run_id+'/artifacts')['artifacts']
        selected = [item for item in artifacts if item['name'] == name and not item['expired']]
        if selected:
            if len(selected) != 1:
                raise ValueError('ambiguous encrypted capability artifact')
            break
        if api('actions/runs/'+run_id)['status'] == 'completed':
            raise ValueError('GitHub job ended before capability was available')
        progress(phase='waiting_for_encrypted_capability', run_id=run_id)
        time.sleep(15)
    raw = subprocess.run(['gh','api','repos/'+REPO+'/actions/artifacts/'+str(selected[0]['id'])+'/zip'],
        capture_output=True, check=True).stdout
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if archive.namelist() != ['upload-capability.encrypted.json']:
            raise ValueError('unexpected encrypted capability artifact')
        envelope = json.loads(archive.read('upload-capability.encrypted.json'))
    spec = importlib.util.spec_from_file_location('stage_crypto', LOCAL_REPO/'research/kalshi/frankie_boss/granite_request_stage.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    from cryptography.hazmat.primitives import serialization
    private_key = serialization.load_pem_private_key(PRIVATE.read_bytes(), password=None)
    receipt = module.decrypt_receipt(envelope, private_key, ready['sha256'])
    expected_key = 'nymex/ng_mbo_5y_v0/frankie/parallel_source_verification/'+ready['sha256']+'.tar.gz'
    parsed = urlsplit(receipt['url'])
    required_headers = {'content-length': str(ready['bytes']),
        'content-type': 'application/gzip', 'if-none-match': '*',
        'x-amz-checksum-sha256': base64.b64encode(bytes.fromhex(ready['sha256'])).decode(),
        'x-amz-server-side-encryption': 'AES256'}
    signed_headers = set(parse_qs(parsed.query).get('X-Amz-SignedHeaders', [''])[0].split(';'))
    if (receipt['method'] != 'PUT' or receipt['key'] != expected_key
            or receipt['bucket'] != 'bento-568968024170-us-east-2-an'
            or parsed.scheme != 'https'
            or parsed.hostname != 'bento-568968024170-us-east-2-an.s3.us-east-2.amazonaws.com'
            or parsed.path != '/'+expected_key
            or receipt['expires_at'] <= time.time()+60
            or receipt['headers'] != required_headers
            or not set(required_headers) <= signed_headers):
        raise ValueError('upload capability does not match exact snapshot')
    path = Path(ready['archive'])
    if path.stat().st_size != ready['bytes']:
        raise ValueError('snapshot archive size changed')
    # Intent survives interruption; remote worker always validates uploaded SHA itself.
    write(ROOT/'upload-intent.json', dict(run_id=run_id, key=expected_key,
        bytes=ready['bytes'], sha256=ready['sha256'], at=time.time()))
    connection = http.client.HTTPSConnection(parsed.hostname, timeout=120)
    digest = hashlib.sha256()
    sent = 0
    try:
        connection.putrequest('PUT', parsed.path+'?'+parsed.query)
        for key, value in receipt['headers'].items():
            connection.putheader(key, value)
        connection.endheaders()
        last = 0.0
        with path.open('rb') as source:
            while chunk := source.read(4*1024**2):
                digest.update(chunk)
                connection.send(chunk)
                sent += len(chunk)
                if time.monotonic()-last >= 5:
                    progress(phase='uploading_snapshot', run_id=run_id, sent_bytes=sent, total_bytes=ready['bytes'])
                    last = time.monotonic()
        response = connection.getresponse()
        response.read(4096)
        if (response.status not in (200,204,412) or digest.hexdigest() != ready['sha256']
                or sent != ready['bytes']):
            raise ValueError('snapshot upload needs reconciliation')
        write(ROOT/'upload-receipt.json', dict(run_id=run_id, http_status=response.status,
            bytes=sent, sha256=digest.hexdigest(), status='uploaded' if response.status != 412 else 'existing_requires_remote_validation', at=time.time()))
        progress(phase='upload_returned', run_id=run_id, sent_bytes=sent, total_bytes=ready['bytes'])
    finally:
        connection.close()

if __name__ == '__main__':
    try:
        main(sys.argv[1])
    except BaseException as error:
        if not (ROOT/'upload-failure.json').exists():
            write(ROOT/'upload-failure.json', dict(error_type=type(error).__name__, at=time.time()))
        print('Snapshot uploader needs attention: '+type(error).__name__, flush=True)
        raise SystemExit(1) from None
