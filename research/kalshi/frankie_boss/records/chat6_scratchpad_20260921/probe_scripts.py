import sys, importlib.util, json, os, argparse
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path); m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m); return m
SSM = load('ssm_run_sh', '/home/user/Markets/deploy/aws/ssm_run_sh.py')
SRV = load('serverless_reading_endpoint', '/home/user/Markets/research/kalshi/frankie_boss/operations/serverless_reading_endpoint.py')
def probe(label, fn):
    try: print(f'[{label}] ->', fn())
    except SystemExit as e: print(f'[{label}] SystemExit({e.code!r})')
    except Exception as e: print(f'[{label}] RAISES {type(e).__name__}: {str(e)[:140]}')
print('== ssm_run_sh.preamble')
probe('MAP_URL with = & % ?', lambda: repr(SSM.preamble(['MAP_URL=https://b.s3.amazonaws.com/k?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Signature=ab%2Fcd'])))
probe('empty value', lambda: repr(SSM.preamble(['DAY='])))
probe('no equals', lambda: SSM.preamble(['DAY']))
probe('single quote in value', lambda: SSM.preamble(["X=it's"]))
probe('newline in value', lambda: SSM.preamble(['X=a\nb']))
probe('carriage return in value (NOT refused)', lambda: repr(SSM.preamble(['X=a\rb'])))
probe('backslash and $ in value (literal in single quotes)', lambda: repr(SSM.preamble(['X=$HOME\\n'])))
probe('bad name 1X', lambda: SSM.preamble(['1X=a']))
probe('name with dash', lambda: SSM.preamble(['A-B=a']))
probe('empty name', lambda: SSM.preamble(['=a']))
probe('no variables', lambda: repr(SSM.preamble([])))
print('== ssm_run_sh.main argument validation (before boto3 is imported)')
def run_main(argv):
    sys.argv = ['ssm_run_sh.py'] + argv
    return SSM.main()
probe('bad instance', lambda: run_main(['--instance', 'i-XYZ', '--script', 'x.sh']))
probe('bad region', lambda: run_main(['--instance', 'i-0123456789abcdef0', '--region', 'US-EAST-1', '--script', 'x.sh']))
probe('timeout 0', lambda: run_main(['--instance', 'i-0123456789abcdef0', '--script', 'x.sh', '--timeout', '0']))
probe('timeout 172801', lambda: run_main(['--instance', 'i-0123456789abcdef0', '--script', 'x.sh', '--timeout', '172801']))
probe('valid args reach the boto3 import (no boto3 here)', lambda: run_main(['--instance', 'i-035994afa8bdf66a5', '--region', 'us-east-1', '--script', '/home/user/Markets/deploy/aws/box/frankie_box_push_response.sh', '--set', 'DAY=20211003']))
print('== serverless_reading_endpoint')
probe('scrub', lambda: SRV.scrub({'env': [{'key': 'HF_TOKEN', 'value': 'x'}], 'apiKey': 'k', 'id': 'abc', 'workers': [{'authToken': 't', 'gpu': 'H100'}]}))
probe('pinned_env(2) keys', lambda: sorted(SRV.pinned_env(2).items()))
captured = {}
def fake_ctl(*args, check=True, capture=True):
    captured['args'] = list(args); return 0, json.dumps({'id': 'k1sqt0haffm61y', 'name': 'x', 'env': [{'key': 'a', 'value': 'b'}]})
SRV.ctl = fake_ctl
def parse(argv):
    sys.argv = ['x', '--action', 'create'] + argv
    p = argparse.ArgumentParser(); [p.add_argument(*a, **k) for a, k in (
        (('--action',), dict(choices=('help','inspect','create','verify'), required=True)), (('--endpoint',), dict(default='')), (('--name',), dict(default='frankie-reading-granite42')),
        (('--gpu',), dict(default=SRV.H100_TIERS)), (('--seqs-per-worker',), dict(type=int, default=2)), (('--workers-max',), dict(type=int, default=16)),
        (('--idle-timeout',), dict(type=int, default=120)), (('--execution-timeout',), dict(type=int, default=SRV.EXECUTION_TIMEOUT_S_DEFAULT)),
        (('--network-volume',), dict(default='')), (('--data-centers',), dict(default='')), (('--hf-token-env',), dict(default='')), (('--wait-seconds',), dict(type=int, default=1500)), (('--work-dir',), dict(default='work/serverless-reading')))]
    return p.parse_args(sys.argv[1:])
os.chdir('/tmp/claude-0/-home-user-Markets/b59e958a-d4f5-5c90-a4be-2dee99555f15/scratchpad')
a = parse(['--work-dir', 'work-probe', '--workers-max', '8', '--seqs-per-worker', '2'])
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf): SRV.create(a)
cmd = captured['args']
print('create cmd gpu-id flags:', [(cmd[i], cmd[i+1]) for i, x in enumerate(cmd) if x == '--gpu-id'])
print('create cmd --env count:', cmd.count('--env'), '; --network-volume-id present:', '--network-volume-id' in cmd, '; --data-center-ids present:', '--data-center-ids' in cmd)
print('create cmd MAX_NUM_SEQS:', [e for e in cmd if e.startswith('MAX_NUM_SEQS=')], 'workers-max:', cmd[cmd.index('--workers-max')+1])
print('receipt written:', os.path.exists('work-probe/serverless-reading-endpoint.json'), '; HF_TOKEN in receipt env:', 'HF_TOKEN' in json.load(open('work-probe/serverless-reading-endpoint.json'))['env'])
print('stdout mentions not-passed tiers:', 'not passed: NVIDIA H100 NVL, NVIDIA H100 PCIe' in buf.getvalue())
probe('create --gpu "" refuses', lambda: SRV.create(parse(['--gpu', '', '--work-dir', 'work-probe'])))
probe('create --gpu " , " refuses', lambda: SRV.create(parse(['--gpu', ' , ', '--work-dir', 'work-probe'])))
probe('create --workers-max 0 refuses', lambda: SRV.create(parse(['--workers-max', '0', '--work-dir', 'work-probe'])))
with contextlib.redirect_stdout(io.StringIO()): SRV.create(parse(['--gpu', ' NVIDIA L40S ', '--work-dir', 'work-probe']))
print('single gpu with spaces ->', [(cmd[i+1]) for i, x in enumerate(captured['args']) if x == '--gpu-id'])
os.environ['HF_TOKEN_PROBE'] = 'hf_secret_probe'
with contextlib.redirect_stdout(buf): SRV.create(parse(['--hf-token-env', 'HF_TOKEN_PROBE', '--work-dir', 'work-probe']))
print('HF token: in cmd env flags:', any(e == 'HF_TOKEN=hf_secret_probe' for e in captured['args']), '; leaked to receipt env:', 'HF_TOKEN' in json.load(open('work-probe/serverless-reading-endpoint.json'))['env'], '; leaked to stdout:', 'hf_secret_probe' in buf.getvalue())
# verify body shape via a fake api
calls = []
def fake_api(key, method, path, body=None, timeout=60):
    calls.append((method, path, body))
    if path.endswith('/run'): return 200, {'id': 'job1', 'status': 'IN_QUEUE'}
    if '/status/' in path: return 200, {'status': 'COMPLETED', 'output': [{'object': 'chat.completion', 'model': SRV.SERVED_MODEL_NAME, 'choices': []}], 'delayTime': 1, 'executionTime': 2, 'workerId': 'w'}
    return 200, {'workers': {}}
SRV.api = fake_api; SRV.time.sleep = lambda s: None
with contextlib.redirect_stdout(io.StringIO()):
    probe('verify exits 0 on the box shape', lambda: SRV.verify('k' * 30, 'k1sqt0haffm61y', 60))
print('verify /run body:', json.dumps(calls[0][2], sort_keys=True))
calls.clear()
def fake_api2(key, method, path, body=None, timeout=60):
    calls.append(path)
    if path.endswith('/run'): return 200, {'id': 'job1', 'status': 'IN_QUEUE'}
    if '/status/' in path: return 200, {'status': 'COMPLETED', 'output': {'object': 'chat.completion', 'model': 'other-name'}}
    return 200, {}
SRV.api = fake_api2
with contextlib.redirect_stdout(io.StringIO()):
    probe('verify exits 2 when the served name differs', lambda: SRV.verify('k' * 30, 'k1sqt0haffm61y', 60))
probe('main refuses a short RUNPOD_API_KEY', lambda: (os.environ.__setitem__('RUNPOD_API_KEY', 'short'), sys.__setattr__('argv', ['x', '--action', 'help']), SRV.main()))
probe('main refuses inspect without --endpoint', lambda: (os.environ.__setitem__('RUNPOD_API_KEY', 'k' * 30), sys.__setattr__('argv', ['x', '--action', 'inspect']), SRV.main()))
probe('main refuses an uppercase endpoint id', lambda: (sys.__setattr__('argv', ['x', '--action', 'verify', '--endpoint', 'ABCDEF12']), SRV.main()))
