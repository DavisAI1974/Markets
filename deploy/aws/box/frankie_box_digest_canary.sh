# Digest reading canary (Greg, 2026-09-28: "measure a slice, extrapolate"; the standing 1-2 minute canary rule).
# Read-only on Frankie's files. Measures, for the Monday derivation digest:
#   1. tokens per byte: the pinned Granite tokenizer on SLICES 4 MB slices spaced evenly from start to end;
#   2. only with READ=part: one real reading-sized part on the serverless reading endpoint (the box's own request shape,
#      OpenAI route, async /run + /status), output capped at MAX_TOKENS: prefill time, output tokens per second, finish
#      reason. Greg: Granite runs on a regular Pod, never the serverless lane, so the default is READ=tokens (no call).
# and prints the extrapolation to the whole digest.
# Inputs: DIGEST (default: the Monday ROOT digest), SLICES (default 3), READ (tokens|part, default tokens),
# PART_TOKENS (default 87000), MAX_TOKENS (default 4096, READ=part only).
# Writes only /opt/frankie-box/work/digest-canary/<UTC stamp>/. READ=tokens bills nothing.
set -eu
export DIGEST="${DIGEST:-/opt/frankie-box/work/monday-calculations/full-20211004-20260927-r1-48/work/derivation-digest-full.md}"
export PART_TOKENS="${PART_TOKENS:-87000}" MAX_TOKENS="${MAX_TOKENS:-4096}" SLICES="${SLICES:-3}" READ="${READ:-tokens}"
case "$READ" in tokens|part) ;; *) echo "READ must be tokens or part"; exit 2;; esac
case "$SLICES" in ''|*[!0-9]*) echo "SLICES must be a positive integer"; exit 2;; esac
exec nice -n 5 /opt/frankie-box/venv/bin/python -B - <<'PY'
import hashlib, http.client, json, os, re, time
from pathlib import Path
import boto3
from tokenizers import Tokenizer

DIGEST, PART, CAP = Path(os.environ['DIGEST']), int(os.environ['PART_TOKENS']), int(os.environ['MAX_TOKENS'])
NSLICES = max(1, int(os.environ['SLICES']))
OUT = Path('/opt/frankie-box/work/digest-canary') / time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
OUT.mkdir(parents=True)
raw = Path('/opt/frankie-box/tmp/granite_tokenizer.json').read_bytes()
if not hashlib.sha256(raw).hexdigest().startswith('883975314d587437'):
    raise SystemExit('pinned Granite tokenizer differs')
tok = Tokenizer.from_str(raw.decode())
size = DIGEST.stat().st_size
sha = hashlib.sha256()
with DIGEST.open('rb') as handle:
    for block in iter(lambda: handle.read(8 << 20), b''):
        sha.update(block)
digest_sha = sha.hexdigest()
report = dict(schema='FRANKIE_DIGEST_CANARY_V1', digest=str(DIGEST), digest_bytes=size, digest_sha256=digest_sha,
              part_tokens=PART, read=os.environ['READ'], slices=[])
print('digest', DIGEST, size, 'bytes sha256', digest_sha, flush=True)
SLICE = 4 * 1024 * 1024
span = max(0, size - SLICE)
offsets = [0] if NSLICES == 1 else [span * i // (NSLICES - 1) for i in range(NSLICES)]
with DIGEST.open('rb') as handle:
    for index, offset in enumerate(offsets):
        handle.seek(offset)
        text = handle.read(SLICE).decode('utf-8', errors='replace')
        t0 = time.time()
        n = len(tok.encode(text, add_special_tokens=False).ids)
        report['slices'].append(dict(label='slice-%d' % index, offset=offset, bytes=min(SLICE, size), tokens=n,
                                     tokens_per_byte=round(n / min(SLICE, size), 4), encode_seconds=round(time.time() - t0, 2)))
        print('slice', report['slices'][-1], flush=True)
tpb = sum(s['tokens'] for s in report['slices']) / sum(s['bytes'] for s in report['slices'])
report['tokens_per_byte'] = round(tpb, 4)
report['digest_tokens_estimate'] = int(size * tpb)
report['parts_estimate'] = int(size * tpb / PART) + 1

if os.environ['READ'] != 'part':
    (OUT / 'canary.json').write_text(json.dumps(report, indent=1, sort_keys=True))
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(0)

# one real part on the reading endpoint: the first PART tokens of the digest under a reading instruction
cfg = json.loads(Path('/opt/frankie-box/serverless.json').read_text()) if Path('/opt/frankie-box/serverless.json').exists() else {}
endpoint = cfg.get('endpoint_id') or 'k1sqt0haffm61y'
key = boto3.client('ssm', region_name='us-east-2').get_parameter(Name='/markets/frankie/runpod-serverless',
                                                                 WithDecryption=True)['Parameter']['Value'].strip()
with DIGEST.open('rb') as handle:
    head = handle.read(int(PART / tpb * 1.05)).decode('utf-8', errors='ignore')
ids = tok.encode(head, add_special_tokens=False).ids[:PART - 400]
chunk = tok.decode(ids)
prompt = ('You are reading one part of your own derivation digest for the Monday 2021-10-04 trading day. '
          'Write your reading notes for this part: every finding, number, relation and open question it carries.\n\n' + chunk)
input_tokens = len(tok.encode(prompt, add_special_tokens=False).ids)
chat = dict(model='granite42-smoke', messages=[dict(role='user', content=prompt)], temperature=0, max_tokens=CAP,
            stream=False, chat_template_kwargs=dict(enable_thinking=False))
body = json.dumps(dict(input=dict(openai_route='/v1/chat/completions', openai_input=chat),
                       policy=dict(executionTimeout=1800000))).encode()

def call(method, path, payload=None):
    c = http.client.HTTPSConnection('api.runpod.ai', timeout=120)
    c.request(method, path, payload, {'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    r = c.getresponse()
    data = r.read()
    try:
        return r.status, json.loads(data)
    except ValueError:
        return r.status, data[:300].decode(errors='replace')

t0 = time.time()
status, reply = call('POST', '/v2/%s/run' % endpoint, body)
if status != 200 or not isinstance(reply, dict) or 'id' not in reply:
    raise SystemExit('run refused: HTTP %s %s' % (status, str(reply)[:200]))
job = reply['id']
state = {}
while time.time() - t0 < 1500:
    time.sleep(5)
    status, state = call('GET', '/v2/%s/status/%s' % (endpoint, job))
    if isinstance(state, dict) and state.get('status') in ('COMPLETED', 'FAILED', 'CANCELLED', 'TIMED_OUT'):
        break
wall = time.time() - t0
output = state.get('output') if isinstance(state, dict) else None
if isinstance(output, list) and len(output) == 1:
    output = output[0]
usage = (output or {}).get('usage', {}) if isinstance(output, dict) else {}
finish = ((output or {}).get('choices') or [{}])[0].get('finish_reason') if isinstance(output, dict) else None
execution_ms, delay_ms = (state or {}).get('executionTime'), (state or {}).get('delayTime')
completion = usage.get('completion_tokens')
report['read'] = dict(endpoint=endpoint, job=job, status=(state or {}).get('status'), input_tokens_local=input_tokens,
                      usage=usage, finish_reason=finish, execution_ms=execution_ms, delay_ms=delay_ms, wall_seconds=round(wall, 1),
                      output_tokens_per_second=round(completion / (execution_ms / 1000), 1) if completion and execution_ms else None)
(OUT / 'canary.json').write_text(json.dumps(report, indent=1, sort_keys=True))
print(json.dumps(report, sort_keys=True))
PY
