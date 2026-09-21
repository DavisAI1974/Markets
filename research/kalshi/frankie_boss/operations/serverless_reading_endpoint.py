"""RunPod serverless endpoint for Frankie's READING lane (Greg, 2026-09-21: "park the reading part" on serverless),
driven by runpodctl the way the RunPod skills prescribe (runpod/golden-paths/20-model-caching-endpoint.md: the Hub
vLLM worker + `--model-reference` host-side cache; never hand-rolled rest.runpod.io/v1 creates).

The retained Pod (one L40S, one sequence, ~20 output tokens per second) stays the BOSS for the writing. The reading is
163 independent parts plus the merge groups, so it fans out over serverless vLLM workers serving the SAME pinned
checkpoint (repository + revision from granite_artifacts_manifest.json), the same context (131,072), bfloat16, chunked
prefill, one full-context sequence per worker, under the retained served model name (OPENAI_SERVED_MODEL_NAME_OVERRIDE),
so every part's answer carries the identity the receipts expect. Nothing here touches the retained Pod.

Actions (RUNPOD_API_KEY in the environment; runpodctl on PATH; the key is never printed):
  help       read-only: runpodctl version, `serverless create --help`, the Hub vLLM worker listing, GPU list with
             prices and availability. The binary is authoritative for flags; read this BEFORE a create.
  inspect    read-only: `serverless get <id>` (workers stripped of env) and `/health`.
  create     Greg's word (billable): `runpodctl serverless create --hub-id runpod-workers/worker-vllm --model-reference
             https://huggingface.co/<repo>:<revision> --gpu-id ... --env ... --workers-min 0 --workers-max N
             --scale-by requests --scale-threshold 1 --idle-timeout ... --execution-timeout ...`; prints the endpoint id
             and the box configuration; receipt under --work-dir.
  verify     a REAL request through the same shape the box sends (openai_route + openai_input, async /run + /status,
             never /runsync or the sync OpenAI route: 524 on a cold worker), printed with usage; the golden loop's
             "up != ready" step. Cold start of the first worker is minutes (image pull + 17.6 GB checkpoint load).
No delete action exists here (Greg's word, by hand: `runpodctl serverless delete <id>`).
"""
from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

API = 'api.runpod.ai'
MANIFEST = Path(__file__).resolve().parents[1] / 'granite_artifacts_manifest.json'
SERVED_MODEL_NAME = 'granite42-smoke'          # the retained identity's served name (granite_retained_lifecycle)
CONTEXT = 131072
HUB_WORKER = 'runpod-workers/worker-vllm'
EXECUTION_TIMEOUT_S_DEFAULT = 4 * 3600         # one uncapped part is ~36 min on an L40S; a ceiling on wall time, never a cap on output


def pins():
    manifest = json.loads(MANIFEST.read_text())
    return manifest['repository'], manifest['revision']


def pinned_env():
    repo, rev = pins()
    return {
        'MODEL_NAME': repo, 'MODEL_REVISION': rev, 'TOKENIZER_NAME': repo, 'TOKENIZER_REVISION': rev,
        'DTYPE': 'bfloat16', 'MAX_MODEL_LEN': str(CONTEXT), 'GPU_MEMORY_UTILIZATION': '0.9',
        'MAX_NUM_SEQS': '1', 'ENABLE_CHUNKED_PREFILL': 'True', 'MAX_NUM_BATCHED_TOKENS': '2048',
        'MAX_CONCURRENCY': '1', 'OPENAI_SERVED_MODEL_NAME_OVERRIDE': SERVED_MODEL_NAME,
        'ENABLE_PREFIX_CACHING': 'False', 'TRUST_REMOTE_CODE': 'False',
    }


def scrub(value):
    if isinstance(value, dict):
        return {k: ('<scrubbed>' if re.search('key|token|secret|password|auth|env', k, re.I) else scrub(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value


def ctl(*args, check=True, capture=True):
    """runpodctl: JSON on stdout, a coded JSON error on stderr with a nonzero exit (never printed with the key)."""
    cmd = ['runpodctl', *args]
    print('$', ' '.join(cmd), flush=True)
    r = subprocess.run(cmd, capture_output=capture, text=True)
    if capture:
        out = r.stdout.strip(); err = r.stderr.strip()
        key = os.environ.get('RUNPOD_API_KEY', '')
        if key and (key in out or key in err):
            raise SystemExit('credential echo in runpodctl output; refused')
        if err:
            print(err[:3000], file=sys.stderr, flush=True)
        if r.returncode and check:
            raise SystemExit(f'runpodctl {args[0]} {args[1] if len(args) > 1 else ""} exit {r.returncode}')
        return r.returncode, out
    if r.returncode and check:
        raise SystemExit(f'runpodctl exit {r.returncode}')
    return r.returncode, ''


def api(key, method, path, body=None, timeout=60):
    connection = http.client.HTTPSConnection(API, timeout=timeout)
    try:
        raw = None if body is None else json.dumps(body, allow_nan=False).encode()
        headers = {'Authorization': 'Bearer ' + key, 'Accept': 'application/json'}
        if raw is not None:
            headers['Content-Type'] = 'application/json'
        connection.request(method, path, raw, headers)
        response = connection.getresponse()
        data = response.read(8 * 1024 * 1024)
        text = data.decode('utf-8', errors='replace')
        if key in text:
            raise SystemExit('credential echo in an API response; refused')
        try:
            return response.status, json.loads(data) if data else None
        except ValueError:
            return response.status, text[:2000]
    finally:
        connection.close()


def help_action():
    ctl('version', check=False)
    ctl('serverless', 'create', '--help', check=False)
    code, out = ctl('hub', 'search', 'vllm', '--type', 'SERVERLESS', check=False)
    print(out[:6000])
    code, out = ctl('gpu', 'list', check=False)
    try:
        rows = json.loads(out)
        rows = rows if isinstance(rows, list) else rows.get('data') or rows.get('gpus') or []
        print('%-40s %6s %12s %12s %s' % ('id', 'GiB', 'secure$/h', 'community$/h', 'stock'))
        for g in rows:
            print('%-40s %6s %12s %12s %s' % (g.get('id'), g.get('memoryInGb'), g.get('securePricePerHr'), g.get('communityPricePerHr'), g.get('stockStatus')))
    except Exception:
        print(out[:6000])


def inspect(key, endpoint):
    code, out = ctl('serverless', 'get', endpoint, check=False)
    try:
        print(json.dumps(scrub(json.loads(out)), indent=1, sort_keys=True)[:6000])
    except Exception:
        print(out[:3000])
    ctl('serverless', 'health', endpoint, check=False)
    status, data = api(key, 'GET', f'/v2/{endpoint}/health')
    print(f'/health HTTP {status}:', json.dumps(data)[:1000])


def create(args):
    repo, rev = pins()
    gpus = [g.strip() for g in args.gpu.split(',') if g.strip()]
    if not gpus or args.workers_max < 1:
        raise SystemExit('--gpu and --workers-max >= 1 are required')
    cmd = ['serverless', 'create', '--name', args.name, '--hub-id', HUB_WORKER,
           '--model-reference', f'https://huggingface.co/{repo}:{rev}',
           '--workers-min', '0', '--workers-max', str(args.workers_max),
           '--scale-by', 'requests', '--scale-threshold', '1',
           '--idle-timeout', str(args.idle_timeout), '--execution-timeout', str(args.execution_timeout)]
    for g in gpus:
        cmd += ['--gpu-id', g]
    env = pinned_env()
    if args.hf_token_env and os.environ.get(args.hf_token_env):
        env['HF_TOKEN'] = os.environ[args.hf_token_env]          # only if the operator says the repo needs it; never printed
    for k, v in env.items():
        cmd += ['--env', f'{k}={v}']
    if args.network_volume:
        cmd += ['--network-volume-id', args.network_volume]
    if args.data_centers:
        cmd += ['--data-center-ids', args.data_centers]
    code, out = ctl(*cmd)
    try:
        created = json.loads(out)
    except ValueError:
        raise SystemExit(f'create returned no JSON: {out[:500]}')
    endpoint_id = created.get('id')
    if not endpoint_id:
        raise SystemExit(f'create returned no id: {json.dumps(scrub(created))[:800]}')
    box = dict(schema='FRANKIE_BOX_SERVERLESS_READING_V1', endpoint_id=endpoint_id, workers=int(args.workers_max),
               gpu_type_ids=gpus, model_repository=repo, model_revision=rev, served_model_name=SERVED_MODEL_NAME,
               context=CONTEXT, execution_timeout_ms=int(args.execution_timeout) * 1000)
    receipt = dict(schema='FRANKIE_SERVERLESS_READING_ENDPOINT_RECEIPT_V1', at=time.time(), hub_worker=HUB_WORKER,
                   model_reference=f'https://huggingface.co/{repo}:{rev}', endpoint=scrub(created),
                   env={k: v for k, v in env.items() if k != 'HF_TOKEN'}, box_config=box)
    work = Path(args.work_dir); work.mkdir(parents=True, exist_ok=True)
    (work / 'serverless-reading-endpoint.json').write_text(json.dumps(receipt, indent=1, sort_keys=True) + '\n')
    print('endpoint created:', endpoint_id)
    print('box config (frankie_box_serverless_config.sh ACTION=write): ENDPOINT_ID=%s WORKERS=%d GPU=%s' % (endpoint_id, int(args.workers_max), ','.join(gpus)))
    print(json.dumps(box, sort_keys=True))


def verify(key, endpoint, wait_seconds):
    """The golden loop's real request: the exact body shape the box sends, async, polled; prints the answer and usage."""
    chat = dict(model=SERVED_MODEL_NAME, messages=[dict(role='user', content='Reply with the single word READY and nothing else.')],
                temperature=0, max_tokens=64, stream=False, chat_template_kwargs=dict(enable_thinking=False))
    body = dict(input=dict(openai_route='/v1/chat/completions', openai_input=chat), policy=dict(executionTimeout=600000))
    status, reply = api(key, 'POST', f'/v2/{endpoint}/run', body)
    if status != 200 or not isinstance(reply, dict) or not reply.get('id'):
        raise SystemExit(f'/run HTTP {status}: {json.dumps(reply)[:500]}')
    job = reply['id']
    print('submitted job', job, reply.get('status'))
    started = time.time(); last = None
    while time.time() - started < wait_seconds:
        status, state = api(key, 'GET', f'/v2/{endpoint}/status/{job}')
        phase = (state or {}).get('status') if isinstance(state, dict) else None
        if phase != last:
            hs, health = api(key, 'GET', f'/v2/{endpoint}/health')
            print(f'+{time.time() - started:.0f}s {phase}; health {json.dumps(health)[:300]}', flush=True)
            last = phase
        if phase == 'COMPLETED':
            output = state.get('output')
            if isinstance(output, list) and len(output) == 1:
                output = output[0]
            ok = isinstance(output, dict) and output.get('object') == 'chat.completion' and output.get('model') == SERVED_MODEL_NAME
            print('output:', json.dumps(output)[:1500])
            print('delayTime', state.get('delayTime'), 'ms; executionTime', state.get('executionTime'), 'ms; worker', state.get('workerId'))
            print('VERIFY:', 'OK (chat.completion under the served name; the box parser accepts this shape)' if ok else 'SHAPE DIFFERS from what the box parser expects')
            raise SystemExit(0 if ok else 2)
        if phase in ('FAILED', 'CANCELLED', 'TIMED_OUT'):
            raise SystemExit(f'job {phase}: {json.dumps(state)[:800]}')
        time.sleep(10)
    raise SystemExit(f'verify wait of {wait_seconds}s exhausted; job {job} still {last} (a cold first worker can take minutes; re-run verify)')


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--action', choices=('help', 'inspect', 'create', 'verify'), required=True)
    p.add_argument('--endpoint', default='')
    p.add_argument('--name', default='frankie-reading-granite42')
    p.add_argument('--gpu', default='NVIDIA L40S')
    p.add_argument('--workers-max', type=int, default=16)
    p.add_argument('--idle-timeout', type=int, default=120)
    p.add_argument('--execution-timeout', type=int, default=EXECUTION_TIMEOUT_S_DEFAULT, help='seconds')
    p.add_argument('--network-volume', default='')
    p.add_argument('--data-centers', default='')
    p.add_argument('--hf-token-env', default='')
    p.add_argument('--wait-seconds', type=int, default=1500)
    p.add_argument('--work-dir', default='work/serverless-reading')
    args = p.parse_args()
    key = os.environ.get('RUNPOD_API_KEY', '').strip()
    if not re.fullmatch('[A-Za-z0-9_-]{20,256}', key):
        raise SystemExit('RUNPOD_API_KEY missing or not a key shape')
    if args.action == 'help':
        help_action()
    elif args.action == 'inspect':
        if not re.fullmatch('[a-z0-9]{6,40}', args.endpoint):
            raise SystemExit('--endpoint id required')
        inspect(key, args.endpoint)
    elif args.action == 'verify':
        if not re.fullmatch('[a-z0-9]{6,40}', args.endpoint):
            raise SystemExit('--endpoint id required')
        verify(key, args.endpoint, args.wait_seconds)
    else:
        create(args)


if __name__ == '__main__':
    main()
