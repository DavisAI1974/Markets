import sys, importlib.util, json, os, io, contextlib, types, subprocess
spec = importlib.util.spec_from_file_location('srv', '/home/user/Markets/research/kalshi/frankie_boss/operations/serverless_reading_endpoint.py'); SRV = importlib.util.module_from_spec(spec); spec.loader.exec_module(SRV)
class R: returncode = 0; stdout = json.dumps({'id': 'abcdef123456'}); stderr = ''
SRV.subprocess.run = lambda cmd, **k: R()          # the real ctl() runs; only the binary is faked
os.chdir(sys.argv[1]); os.environ['HF_PROBE'] = 'hf_probe_secret_value_123'; os.environ['RUNPOD_API_KEY'] = 'k' * 30
args = types.SimpleNamespace(name='n', gpu='NVIDIA L40S', workers_max=1, seqs_per_worker=1, idle_timeout=120, execution_timeout=100, network_volume='', data_centers='', hf_token_env='HF_PROBE', work_dir='work-probe')
out = io.StringIO()
with contextlib.redirect_stdout(out): SRV.create(args)
text = out.getvalue()
print('HF token value printed on stdout by ctl():', 'hf_probe_secret_value_123' in text)
print('the line:', [l[:120] for l in text.splitlines() if 'HF_TOKEN=' in l])
