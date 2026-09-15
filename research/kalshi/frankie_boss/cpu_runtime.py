"""Explicit CPU execution policy for Frankie/BOSS hosts.

This module changes only execution parallelism. It does not change market inputs,
feature calculations, model planes, evidence selection, learning objectives, or
checkpoint contents beyond the already-recorded runtime thread identity.

Call configure_cpu_runtime() before constructing/restoring a BossTrainingCheckpoint.
A retained checkpoint created under a different PyTorch thread count must be migrated
explicitly; callers must not silently change it in place.
"""
from dataclasses import dataclass, asdict
import os

DEFAULT_CPU_WORKERS = 32


@dataclass(frozen=True)
class CpuRuntimePolicy:
    workers: int = DEFAULT_CPU_WORKERS
    torch_intraop_threads: int = DEFAULT_CPU_WORKERS
    torch_interop_threads: int = 1
    worker_internal_threads: int = 1

    def __post_init__(self):
        for name, value in asdict(self).items():
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.workers > 256 or self.torch_intraop_threads > 256:
            raise ValueError("CPU parallelism above 256 requires an explicit architecture review")


def configure_cpu_runtime(policy=None):
    """Apply the host CPU policy before model/checkpoint construction.

    Journal verification workers read FRANKIE_CPU_WORKERS. The native PyTorch model
    remains one causally ordered model/optimizer state, using intra-op CPU parallelism
    rather than unsafe concurrent optimizer writers. This preserves the exact learning
    order while using the available CPU cores.
    """
    policy = CpuRuntimePolicy() if policy is None else policy
    if not isinstance(policy, CpuRuntimePolicy):
        raise ValueError("CpuRuntimePolicy required")
    os.environ["FRANKIE_CPU_WORKERS"] = str(policy.workers)
    import torch
    torch.set_num_threads(policy.torch_intraop_threads)
    try:
        torch.set_num_interop_threads(policy.torch_interop_threads)
    except RuntimeError as exc:
        raise RuntimeError("CPU policy must be applied before PyTorch inter-op work starts") from exc
    if torch.get_num_threads() != policy.torch_intraop_threads:
        raise RuntimeError("PyTorch intra-op thread policy was not applied")
    if torch.get_num_interop_threads() != policy.torch_interop_threads:
        raise RuntimeError("PyTorch inter-op thread policy was not applied")
    return dict(schema="FRANKIE_CPU_RUNTIME_POLICY_V1", **asdict(policy),
                torch_num_threads=torch.get_num_threads(),
                torch_num_interop_threads=torch.get_num_interop_threads())
