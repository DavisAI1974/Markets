import sys, importlib.util, json, os, io, contextlib, types
spec = importlib.util.spec_from_file_location('srv', '/home/user/Markets/research/kalshi/frankie_boss/operations/serverless_reading_endpoint.py'); SRV = importlib.util.module_from_spec(spec); spec.loader.exec_module(SRV)
seen = []
SRV.ctl = lambda *a, **k: (seen.append(list(a)), (0, json.dumps({'id': 'abcdef123456'})))[1]
os.chdir(sys.argv[1])
for gpu in (' NVIDIA L40S ', 'NVIDIA H100 NVL,,NVIDIA H100 PCIe', 'a,b,c'):
    seen.clear(); args = types.SimpleNamespace(name='n', gpu=gpu, workers_max=4, seqs_per_worker=1, idle_timeout=120, execution_timeout=100, network_volume='', data_centers='', hf_token_env='', work_dir='work-probe')
    out = io.StringIO()
    with contextlib.redirect_stdout(out): SRV.create(args)
    cmd = seen[0]; print(repr(gpu), '-> --gpu-id', repr(cmd[cmd.index('--gpu-id') + 1]), '| count of --gpu-id flags:', cmd.count('--gpu-id'), '| box gpu_type_ids:', json.load(open('work-probe/serverless-reading-endpoint.json'))['box_config']['gpu_type_ids'])
