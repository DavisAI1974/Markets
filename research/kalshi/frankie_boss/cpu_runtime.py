"""Explicit CPU execution policy for native Frankie/BOSS hosts.

This module changes only execution parallelism. It does not change market inputs,
feature calculations, model planes, evidence selection, learning objectives, or
optimizer ordering. Journal verification and PyTorch training are separate budgets.

Call configure_cpu_runtime() before constructing/restoring a BossTrainingCheckpoint.
A retained checkpoint created under a different PyTorch thread count must be migrated
explicitly; callers must not silently change it in place.
"""
from dataclasses import dataclass, asdict
import os
from pathlib import Path
import platform

JOURNAL_WORKER_ENV = "FRANKIE_JOURNAL_VERIFY_WORKERS"
TORCH_INTRAOP_ENV = "FRANKIE_TORCH_INTRAOP_THREADS"
TORCH_INTEROP_ENV = "FRANKIE_TORCH_INTEROP_THREADS"


@dataclass(frozen=True)
class CpuRuntimePolicy:
    journal_verify_workers: int
    torch_intraop_threads: int
    torch_interop_threads: int = 1
    worker_internal_threads: int = 1

    def __post_init__(self):
        for name, value in asdict(self).items():
            if type(value) is not int or value < 1:
                raise ValueError(f"{name} must be a positive integer")
        if self.journal_verify_workers > 256 or self.torch_intraop_threads > 256:
            raise ValueError("CPU parallelism above 256 requires an explicit architecture review")
        if self.worker_internal_threads != 1:
            raise ValueError("journal verification workers must remain single-threaded internally")


def cpu_model():
    """Best-effort stable CPU model string for the run identity receipt."""
    path = Path("/proc/cpuinfo")
    if path.is_file():
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.lower().startswith("model name") and ":" in line:
                value = line.split(":", 1)[1].strip()
                if value:
                    return value
    value = platform.processor().strip()
    return value or platform.machine() or "unknown"


def _environment_int(name):
    raw = os.environ.get(name)
    if raw is None:
        raise RuntimeError(f"explicit {name} is required")
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < 1:
        raise RuntimeError(f"{name} must be positive")
    return value


def policy_from_environment():
    """No hidden production defaults: benchmarked values must be supplied explicitly."""
    return CpuRuntimePolicy(
        journal_verify_workers=_environment_int(JOURNAL_WORKER_ENV),
        torch_intraop_threads=_environment_int(TORCH_INTRAOP_ENV),
        torch_interop_threads=_environment_int(TORCH_INTEROP_ENV),
        worker_internal_threads=1,
    )


def configure_cpu_runtime(policy):
    """Apply native-host CPU policy before model/checkpoint construction.

    Do not globally set OMP/MKL/OpenBLAS to one here: that would also throttle the
    native trainer. VerifiedJournalReader caps only its own child processes.
    """
    if not isinstance(policy, CpuRuntimePolicy):
        raise ValueError("CpuRuntimePolicy required")
    available = os.cpu_count()
    required = max(policy.journal_verify_workers, policy.torch_intraop_threads)
    if available is None or available < required:
        raise RuntimeError(f"host exposes {available!r} logical CPUs; policy requires at least {required}")
    os.environ[JOURNAL_WORKER_ENV] = str(policy.journal_verify_workers)
    os.environ[TORCH_INTRAOP_ENV] = str(policy.torch_intraop_threads)
    os.environ[TORCH_INTEROP_ENV] = str(policy.torch_interop_threads)
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
    return dict(schema="FRANKIE_CPU_RUNTIME_POLICY_V2", **asdict(policy),
                host_logical_cpus=available, host_cpu_model=cpu_model(),
                torch_version=str(torch.__version__),
                torch_num_threads=torch.get_num_threads(),
                torch_num_interop_threads=torch.get_num_interop_threads())
