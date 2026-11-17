"""Comparable exact-scope shadow metrics and fail-closed promotion decisions."""
from dataclasses import dataclass
import math
from .core import LocalityError


def _count(value) -> bool:
    return type(value) is int  # bool is an int subclass and is rejected


def _seconds(value) -> bool:
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

@dataclass(frozen=True)
class Workload:
    source_identity:str
    data_identity:str
    environment_identity:str
    original_jobs:int
    completed_jobs:int
    distinct_pairs:int
    cpu_seconds:float
    elapsed_seconds:float
    bytes_read:int
    output_identity:str
    def __post_init__(self):
        if not all((self.source_identity,self.data_identity,self.environment_identity,self.output_identity)):
            raise LocalityError("missing workload identity")
        # E-12: counters are plain ints (no bool); runtimes are finite numbers (no bool/NaN/inf).
        if not all(_count(x) for x in (self.original_jobs,self.completed_jobs,self.distinct_pairs,self.bytes_read)):
            raise LocalityError("workload counters must be plain integers")
        if not _seconds(self.cpu_seconds) or not _seconds(self.elapsed_seconds):
            raise LocalityError("workload runtimes must be finite numbers")
        if min(self.original_jobs,self.completed_jobs,self.distinct_pairs,self.bytes_read)<0:
            raise LocalityError("negative counters")
        if not 0<=self.completed_jobs<=self.original_jobs:
            raise LocalityError("invalid completed jobs")
        if self.cpu_seconds<0 or self.elapsed_seconds<0:
            raise LocalityError("negative runtime")

def compare_workloads(baseline:Workload,candidate:Workload)->dict:
    comparable=(baseline.data_identity==candidate.data_identity
                and baseline.environment_identity==candidate.environment_identity)
    exact_outputs=baseline.output_identity==candidate.output_identity
    return {"comparable":comparable,"exact_output_identity":exact_outputs,
            "source_changed":baseline.source_identity!=candidate.source_identity,
            "elapsed_delta_seconds":candidate.elapsed_seconds-baseline.elapsed_seconds if comparable else None,
            "cpu_delta_seconds":candidate.cpu_seconds-baseline.cpu_seconds if comparable else None,
            "jobs_delta":candidate.original_jobs-baseline.original_jobs if comparable else None,
            "distinct_pairs":{"baseline":baseline.distinct_pairs,"candidate":candidate.distinct_pairs},
            "bytes_read":{"baseline":baseline.bytes_read,"candidate":candidate.bytes_read},
            "distinct_pairs_delta":candidate.distinct_pairs-baseline.distinct_pairs if comparable else None,
            "bytes_read_delta":candidate.bytes_read-baseline.bytes_read if comparable else None,
            "safe_to_promote":False,
            "reason":"manual scientific approval and complete provenance required"}
