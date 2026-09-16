"""Explicit numeric/runtime policy for a NEW Frankie native-host run identity.

The failed Sunday checkpoint already binds Python, torch, numpy, intra-op thread
count and deterministic-algorithm mode. A rerun that changes any of them is a new
numeric identity. This module makes that change explicit before model/checkpoint
construction; it does not change market data, model architecture or objectives.
"""
from __future__ import annotations

import platform
import sys

from .runtime_resource_probe import host_snapshot

SCHEMA = 'FRANKIE_NATIVE_HOST_POLICY_V1'


def _positive(value, name):
    if type(value) is not int or value < 1:
        raise ValueError(name+' must be a positive integer')
    return value


def apply_native_runtime_policy(configuration):
    """Validate and apply an explicitly declared new-run CPU/toolchain policy."""
    policy = configuration.get('native_host_runtime')
    if type(policy) is not dict or policy.get('schema') != SCHEMA:
        raise ValueError('explicit native_host_runtime policy required')
    required = {'schema','parent_run_id','numeric_identity','python_version','torch_version','numpy_version',
                'torch_intraop_threads','torch_interop_threads','deterministic_algorithms',
                'minimum_logical_cpus','minimum_memory_bytes'}
    if set(policy) != required:
        raise ValueError('native host policy fields differ from reviewed schema')
    if policy['numeric_identity'] != 'NEW' or configuration.get('run_id') == policy['parent_run_id']:
        raise ValueError('rerun must declare a new numeric and run identity')
    if platform.python_version() != policy['python_version']:
        raise RuntimeError('Python version differs from declared native runtime')

    import numpy as np
    import torch
    if str(torch.__version__) != policy['torch_version'] or np.__version__ != policy['numpy_version']:
        raise RuntimeError('torch/numpy versions differ from declared native runtime')
    intra = _positive(policy['torch_intraop_threads'], 'torch_intraop_threads')
    inter = _positive(policy['torch_interop_threads'], 'torch_interop_threads')
    if type(policy['deterministic_algorithms']) is not bool:
        raise ValueError('deterministic_algorithms must be boolean')
    snapshot = host_snapshot()
    minimum_cpus = _positive(policy['minimum_logical_cpus'], 'minimum_logical_cpus')
    minimum_memory = _positive(policy['minimum_memory_bytes'], 'minimum_memory_bytes')
    if snapshot.get('logical_cpus') is None or snapshot['logical_cpus'] < minimum_cpus:
        raise RuntimeError('native host exposes fewer logical CPUs than declared minimum')
    if snapshot.get('system_memory_total_bytes') is None or snapshot['system_memory_total_bytes'] < minimum_memory:
        raise RuntimeError('native host exposes less memory than declared minimum')
    if intra > snapshot['logical_cpus']:
        raise RuntimeError('native intra-op thread count exceeds visible logical CPUs')

    torch.set_num_threads(intra)
    try:
        torch.set_num_interop_threads(inter)
    except RuntimeError as exc:
        raise RuntimeError('native runtime policy must be applied before torch inter-op work') from exc
    torch.use_deterministic_algorithms(policy['deterministic_algorithms'])
    if (torch.get_num_threads() != intra or torch.get_num_interop_threads() != inter
            or torch.are_deterministic_algorithms_enabled() != policy['deterministic_algorithms']):
        raise RuntimeError('declared native runtime policy was not applied exactly')

    # Persist only resume-stable host facts here. Dynamic available memory/RSS is
    # recorded separately by the per-step resource diagnostics.
    stable_host = {name:snapshot.get(name) for name in
        ('platform_system','platform_release','platform_machine','logical_cpus','cpu_model','system_memory_total_bytes')}
    return dict(schema='FRANKIE_NATIVE_HOST_RUNTIME_IDENTITY_V1', parent_run_id=policy['parent_run_id'],
        run_id=configuration['run_id'], numeric_identity='NEW', python=sys.version,
        python_version=platform.python_version(), torch=str(torch.__version__), numpy=np.__version__,
        torch_intraop_threads=torch.get_num_threads(), torch_interop_threads=torch.get_num_interop_threads(),
        deterministic_algorithms=torch.are_deterministic_algorithms_enabled(), **stable_host)
