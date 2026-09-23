"""Build the Monday cycle-0 actual host configuration on the box (FRANKIE_BOSS_ACTUAL_HOST_CONFIGURATION_V1).

Starts from the first Monday run's final configuration (committed) and replaces every path and identity with the
Monday ones: the prepared schedule/prefixes/contract, Frankie's retained principal inputs, the box's producers
checkout as the receiver (its commit read, not assumed), the stacked_v2 context on the 131,072 service context,
a fresh run id, and a native runtime policy whose versions and capacity are MEASURED here. Writes one new file.
"""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import re
import subprocess

REPOSITORY = Path(__file__).resolve().parents[3]
BASE = REPOSITORY / ('research/kalshi/frankie_boss/sunday_20260915_package/FB/sunday-launch-20260915/'
                     'actual-host-final-configuration.json')
TOKENIZER_DIR = REPOSITORY / ('research/kalshi/frankie_boss/sunday_20260915_package/C_Codex/2026-09-14/'
                              'if-you-mean-claude-code-a/work/verified-tokenizer')
RECEIVER = Path('/opt/frankie-box/producers')
PARENT = Path('/opt/frankie-box/work/monday-run-config')
RUNS = Path('/opt/frankie-box/work/runs')


def pin(path):
    raw = Path(path).read_bytes()
    return dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def build(prepared_path, principal_path, commit, run_id, output_root, completion_ref):
    output = Path(output_root)
    if output.parent != PARENT or not re.fullmatch('[A-Za-z0-9_-]{1,96}', output.name) or output.exists():
        raise ValueError('fresh named output under ' + str(PARENT))
    if not re.fullmatch('[A-Za-z0-9_.-]{8,96}', run_id) or (RUNS / run_id).exists():
        raise ValueError('fresh run id required')
    base = json.loads(BASE.read_bytes())
    prepared = json.loads(Path(prepared_path).read_bytes())
    principal = json.loads(Path(principal_path).read_bytes())
    receiver_commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=RECEIVER, text=True).strip()
    import numpy
    import torch
    memory_total = os.sysconf('SC_PAGE_SIZE') * os.sysconf('SC_PHYS_PAGES')
    host = dict(base['host_runtime'])
    for key in ('retained_preparation_recovery', 'source_lineage', 'development_limitations', 'prefix_seeds',
                'source_progress'):
        host.pop(key, None)
    host.update(prepared['host_runtime'])
    host.update(boss_commit=commit, repository=str(REPOSITORY), context_encoding='stacked_v2', service_context=131072,
                transport_protocol='jobs_v1', output_budget='remaining_context', tokenizer_directory=str(TOKENIZER_DIR),
                completion_workflow_ref=completion_ref, state_defects_and_gaps_reported=[])
    config = {k: v for k, v in base.items() if k != 'host_runtime'}
    config.update({k: v for k, v in prepared.items() if k != 'host_runtime'})
    config.update(schema='FRANKIE_BOSS_ACTUAL_HOST_CONFIGURATION_V1', run_id=run_id, run_directory=str(RUNS / run_id),
                  model_calls_performed=False, training_updates_performed=False, host_runtime=host,
                  memory=principal['memory'], mapping=principal['mapping'],
                  retained_witnesses=principal['retained_witnesses'], delivery_receipt=principal['delivery_receipt'],
                  calculation_result=principal['calculation_result'],
                  receiver_root=str(RECEIVER), receiver_commit=receiver_commit,
                  native_host_runtime=dict(schema='FRANKIE_NATIVE_HOST_POLICY_V1', parent_run_id=base['run_id'],
                      numeric_identity='NEW', python_version=platform.python_version(),
                      torch_version=str(torch.__version__), numpy_version=numpy.__version__,
                      torch_intraop_threads=8, torch_interop_threads=1, deterministic_algorithms=True,
                      minimum_logical_cpus=os.cpu_count(), minimum_memory_bytes=memory_total))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(mode=0o700)
    path = output / 'actual-host-configuration.json'
    with open(path, 'xb') as f:
        f.write(json.dumps(config, sort_keys=True, indent=1).encode())
    return dict(configuration=pin(path), run_id=run_id, run_directory=config['run_directory'],
                receiver_commit=receiver_commit, native_host_runtime=config['native_host_runtime'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('prepared', 'principal', 'commit', 'run-id', 'output-root', 'completion-ref'):
        parser.add_argument('--' + name, required=True)
    a = parser.parse_args()
    print(json.dumps(build(a.prepared, a.principal, a.commit, a.run_id, a.output_root, a.completion_ref),
                     sort_keys=True), flush=True)


if __name__ == '__main__':
    main()
