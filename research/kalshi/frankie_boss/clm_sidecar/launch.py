"""CLM sidecar launcher (runs on the GitHub runner): one GPU Pod, run learn.py on the dataset, collect, delete the Pod.

    python launch.py --dataset-key <s3 key from the box extract manifest> --stamp <name> [--max-minutes 150]

Runpod REST v2 (api.runpod.io, the live openapi spec): GET /v2/catalog/gpus for stock, POST /v2/pods, GET and DELETE
/v2/pods/{id}. The Pod is always deleted, on success, failure or timeout. Outputs land in S3 under
clm-sidecar/<stamp>/out/ and locally in ./clm-sidecar-out/. Standalone: nothing of Frankie/BOSS is touched.
"""
import argparse
import http.client
import json
import os
from pathlib import Path
import sys
import time
from urllib.parse import urlencode

import boto3

HERE = Path(__file__).resolve().parent
BUCKET, REGION = 'frankie-granite42-568968024170-us-east-1', 'us-east-1'
IMAGE = 'vllm/vllm-openai:latest'
# 48 GB tiers first (cheapest that fit Qwen3-8B plus the CLM heads); then the larger tiers in stock 2026-09-28 08:30Z,
# when every 48 GB tier read NONE. Known-good vLLM architectures (Ampere, Hopper) before Blackwell.
PREFERRED = ('NVIDIA L40S', 'NVIDIA RTX A6000', 'NVIDIA A40', 'NVIDIA L40', 'NVIDIA RTX 6000 Ada Generation',
             'NVIDIA A100-SXM4-80GB', 'NVIDIA A100 80GB PCIe', 'NVIDIA H100 80GB HBM3', 'NVIDIA H100 NVL',
             'NVIDIA RTX PRO 6000 Blackwell Server Edition', 'NVIDIA H200')
OUTPUTS = {'PUT_REPORT': 'report.md', 'PUT_SUMMARY': 'summary.json', 'PUT_PREDICTIONS': 'predictions.jsonl.gz',
           'PUT_RAW': 'zero_shot_raw_examples.json', 'PUT_LOG': 'pod.log', 'PUT_STATUS': 'status.json',
           'PUT_PROGRESS': 'progress.json'}
ENTRY = ('import os,urllib.request;urllib.request.urlretrieve(os.environ["BOOTSTRAP_URL"],"/tmp/b.sh");'
         'os.execvp("bash",["bash","/tmp/b.sh"])')


def api(method, path, body=None):
    connection = http.client.HTTPSConnection('api.runpod.io', timeout=30)
    try:
        connection.request(method, path, None if body is None else json.dumps(body).encode(),
                           {'Authorization': 'Bearer ' + os.environ['RUNPOD_API_KEY'], 'Accept': 'application/json',
                            'Content-Type': 'application/json'})
        response = connection.getresponse()
        return response.status, response.read(2000000)
    finally:
        connection.close()


def log_tail(pod, source, lines=15):
    """Last provider log lines (system: image pull and scheduling; container: bootstrap). Lines carrying a presigned
    URL are dropped."""
    connection = http.client.HTTPSConnection('api.runpod.io', timeout=6)
    kept = []
    try:
        connection.request('GET', '/v2/pods/%s/logs?%s' % (pod, urlencode(dict(source=source, tail=40))),
                           headers={'Authorization': 'Bearer ' + os.environ['RUNPOD_API_KEY'], 'Accept': 'text/event-stream'})
        response = connection.getresponse()
        if response.status != 200:
            return ['HTTP %d' % response.status]
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            connection.sock.settimeout(max(.05, deadline - time.monotonic()))
            raw = response.readline(65537)
            if not raw:
                break
            if raw.startswith(b'data:'):
                try:
                    line = str(json.loads(raw[5:]).get('line', ''))
                except ValueError:
                    continue
                if 'X-Amz' not in line and '_URL' not in line:
                    kept.append(line[:240])
    except (TimeoutError, OSError):
        kept.append('(log stream unavailable)')
    finally:
        connection.close()
    return kept[-lines:]


def checkpoint(s3, base, pod, info, started):
    """Greg, 2026-09-28: scheduled outputs every CHECKPOINT minutes, not only at the end."""
    runtime = info.get('runtime') if isinstance(info, dict) else None
    print('=== CHECKPOINT %s (+%d min) pod %s desired=%s runtime=%s' % (
        time.strftime('%H:%M:%SZ', time.gmtime()), (time.time() - started) // 60, pod,
        info.get('desiredStatus') if isinstance(info, dict) else info, 'up' if runtime else 'none'), flush=True)
    try:
        print('progress: %s' % s3.get_object(Bucket=BUCKET, Key='%s/out/progress.json' % base)['Body'].read().decode().strip(), flush=True)
    except Exception:  # noqa: BLE001
        print('progress: none uploaded yet', flush=True)
    for source in ('system', 'container'):
        for line in log_tail(pod, source):
            print('LOG %s %s' % (source, line), flush=True)
    return bool(runtime)


def pick_gpu():
    status, data = api('GET', '/v2/catalog/gpus?' + urlencode(dict(include='AVAILABILITY', product='POD', count=1, cloud='SECURE')))
    if status != 200:
        raise SystemExit('catalog -> HTTP %d: %s' % (status, data[:500]))
    gpus = {g['id']: g for g in json.loads(data)['gpus']}
    for gid in PREFERRED:
        g = gpus.get(gid)
        if g and g.get('secure') and (g.get('memory') or 0) >= 40 and g.get('availability') not in (None, 'NONE'):
            centers = [dc['id'] for dc in g.get('dataCenters') or [] if dc.get('availability') not in (None, 'NONE')]
            if not centers:     # run 36410448682: L40S LOW overall, no data center in stock, Pod never placed in 150 min
                print('skip %s: %s overall but no data center in stock' % (gid, g.get('availability')), flush=True)
                continue
            print('GPU %s (%s GB, %s), data centers %s' % (gid, g.get('memory'), g.get('availability'), centers), flush=True)
            return gid, centers
    raise SystemExit('no preferred GPU in stock: ' + json.dumps({k: (v.get('memory'), v.get('availability')) for k, v in gpus.items()
                                                               if (v.get('memory') or 0) >= 40}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset-key', required=True)
    parser.add_argument('--stamp', required=True)
    parser.add_argument('--max-minutes', type=int, default=150)
    parser.add_argument('--checkpoint-minutes', type=int, default=30)
    parser.add_argument('--start-minutes', type=int, default=30,
                        help='delete the Pod if it has never started by then (the 150-minute None run, 2026-09-28)')
    args = parser.parse_args()
    s3 = boto3.client('s3', region_name=REGION)
    base = 'clm-sidecar/%s' % args.stamp
    s3.head_object(Bucket=BUCKET, Key=args.dataset_key)            # the box extract uploaded it
    for name in ('learn.py', 'pod_bootstrap.sh'):
        s3.upload_file(str(HERE / name), BUCKET, '%s/code/%s' % (base, name))
    ttl = (args.max_minutes + 60) * 60
    get = lambda key: s3.generate_presigned_url('get_object', Params=dict(Bucket=BUCKET, Key=key), ExpiresIn=ttl)
    put = lambda key: s3.generate_presigned_url('put_object', Params=dict(Bucket=BUCKET, Key=key), ExpiresIn=ttl)
    env = dict(BOOTSTRAP_URL=get('%s/code/pod_bootstrap.sh' % base), LEARN_URL=get('%s/code/learn.py' % base),
               DATASET_URL=get(args.dataset_key), STAMP=args.stamp, CHECKPOINT_MINUTES=str(args.checkpoint_minutes))
    env.update({var: put('%s/out/%s' % (base, name)) for var, name in OUTPUTS.items()})
    gpu, centers = pick_gpu()
    body = dict(name='clm-sidecar-' + args.stamp, image=IMAGE, cloud='SECURE', gpu=dict(id=gpu, count=1), disk=80,
                env=env, entrypoint=['python3', '-c', ENTRY], startSsh=False, startJupyter=False)
    if centers:
        body['dataCenterIds'] = centers
    status, data = api('POST', '/v2/pods', body)
    if status not in (200, 201):
        raise SystemExit('create -> HTTP %d: %s' % (status, data[:1000].decode('utf-8', 'replace')))
    pod = json.loads(data)['id']
    Path('clm-sidecar-pod.txt').write_text(pod)           # the workflow's always() cleanup deletes it too
    print('POD %s created' % pod, flush=True)
    outcome = 'timeout'
    try:
        started = time.time()
        deadline = started + args.max_minutes * 60
        next_checkpoint, ever_up = started + args.checkpoint_minutes * 60, False
        while time.time() < deadline:
            time.sleep(60)
            try:
                marker = json.loads(s3.get_object(Bucket=BUCKET, Key='%s/out/status.json' % base)['Body'].read())
                outcome = marker.get('status', 'unknown')
                print('status marker: %s' % marker, flush=True)
                break
            except s3.exceptions.NoSuchKey:
                pass
            code, info = api('GET', '/v2/pods/' + pod)
            info = json.loads(info) if code == 200 else 'HTTP %d' % code
            if not ever_up:     # the Pod's first progress upload (stage download) proves it started, whatever the API shows
                try:
                    s3.head_object(Bucket=BUCKET, Key='%s/out/progress.json' % base)
                    ever_up = True
                except Exception:  # noqa: BLE001
                    ever_up = bool(isinstance(info, dict) and info.get('runtime'))
            print('%s pod %s: %s runtime=%s' % (time.strftime('%H:%M:%S'), pod, info.get('desiredStatus') if isinstance(info, dict) else info,
                                                'up' if ever_up else 'none'), flush=True)
            if time.time() >= next_checkpoint:
                next_checkpoint += args.checkpoint_minutes * 60
                checkpoint(s3, base, pod, info, started)
            if not ever_up and time.time() - started >= args.start_minutes * 60:
                checkpoint(s3, base, pod, info, started)
                outcome = 'never_started'
                print('Pod never started in %d min; deleting it (see the LOG lines above)' % args.start_minutes, flush=True)
                break
    finally:
        code, _ = api('DELETE', '/v2/pods/' + pod)
        print('POD %s delete -> HTTP %d' % (pod, code), flush=True)
    local = Path('clm-sidecar-out')
    local.mkdir(exist_ok=True)
    for name in OUTPUTS.values():
        try:
            s3.download_file(BUCKET, '%s/out/%s' % (base, name), str(local / name))
        except Exception as error:  # noqa: BLE001
            print('no %s: %s' % (name, str(error)[:120]))
    print('OUTCOME %s; outputs in s3://%s/%s/out/' % (outcome, BUCKET, base), flush=True)
    sys.exit(0 if outcome == 'done' else 1)


if __name__ == '__main__':
    main()
