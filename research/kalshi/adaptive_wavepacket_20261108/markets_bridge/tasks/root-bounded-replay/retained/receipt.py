from datetime import datetime, timezone
from importlib.metadata import version
import hashlib
import json
import os
from pathlib import Path
import platform

root = Path.cwd()
target = Path('/mnt/e/Markets-family-research-handoff/research/kalshi/adaptive_wavepacket_20261108/markets_bridge/tasks/root-bounded-replay/receipt.json')
out = root / 'out'
modes = dict(replica_shards='sharded', single_replay='single-ready', single_replay_resumed='resumed-save')

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def timing(path):
    values = {}
    for line in path.read_text().splitlines():
        parts = line.lstrip().rsplit(': ', 1)
        if len(parts) == 2:
            values[parts[0]] = parts[1]
    if values['Exit status'] != '0':
        raise ValueError(path)
    elapsed = values['Elapsed (wall clock) time (h:mm:ss or m:ss)']
    wall = sum(float(v) * 60**i for i, v in enumerate(reversed(elapsed.split(':'))))
    return dict(wall_seconds=round(wall,2),
                cpu_seconds=round(float(values['User time (seconds)']) + float(values['System time (seconds)']),2),
                max_single_process_rss_kib=int(values['Maximum resident set size (kbytes)']))

comparison = {mode: json.loads((out / name / 'spool-comparison.json').read_bytes()) for mode,name in modes.items()}
reference = comparison['replica_shards']
if any(row != reference for row in comparison.values()):
    raise ValueError('ordered spools differ')
data = json.loads((root / '20231018-input-receipt.json').read_bytes())
tape = [json.loads(line) for line in (root / '20231018-input.jsonl').read_bytes().splitlines()]
derive = json.loads((out / 'sharded/work/derive.json').read_bytes())
adapter='research/ng_exhaustion_mbo_v4_state_adapter_20260820.py'
stats = {
    'root_runtime_git_commit':'db96f24f3260bf0d70c763b297c2ba9b84f571a6',
    'root_adapter_git_commit':'af36937d1e478831d4c7bc612c98d969e9a0848b',
    'root_adapter_sha256':sha(root / 'root-producers' / adapter),
    'native_git_commit':'2ebb8ce8ef4834545ad99a4ecdff50c18c5b3134',
    'native_adapter_sha256':sha(root / 'producers' / adapter),
    'tape_git_commit':'1d15dc6f1b5bbb1fabb6389d18e8bedba2b77202',
    'utc_member':data['source']['file'],
    'source_member_sha256':data['source']['sha256'],
    'prefix_sha256':data['sha256'],
    'journal_sha256':derive['rows']['sha256'],
    'journal_head':derive['rows']['head'],
    'first_ts_recv_ns':tape[0]['ts_recv'],
    'last_ts_recv_ns':tape[-1]['ts_recv'],
    'opening_reset_records':data['resets'],
    'environment':dict(platform='WSL2 Ubuntu on ext4', cpus=len(os.sched_getaffinity(0)),
                       physical_cores=4, python=platform.python_version(),
                       packages={p:version(p) for p in ('torch','numpy','cloudpickle','databento-dbn','zstandard')}),
    'measurement_scope':'Fresh offline ROOT legacy stages, including one separate spool digest read. GNU time RSS is the heaviest single process. Native, rich teacher, and model fitting are outside the timing.',
    'measurements':{mode:timing(out / (name+'.time')) for mode,name in list(modes.items())[:2]},
    'root':reference,
    'recovery':dict(mode='single_replay', saved_next_input=2999, saved_input_spool_byte_offset=2085164,
                    ordered_spools_identical=True, included_in_wall_comparison=False),
    'sqlite':dict(**json.loads((out/'sqlite-check.json').read_bytes()), integrity_check='ok',
                  sha256=sha(out/'checked-clock.sqlite')),
    'native':dict(status='blocked_before_replay', pre_traversal_gates='passed',
                  completed_groups=0, required_distinct_cores=8, available_distinct_cores=4),
}
with target.open('x', encoding='utf-8') as stream:
    json.dump(stats, stream, indent=2)
    stream.write('\n')