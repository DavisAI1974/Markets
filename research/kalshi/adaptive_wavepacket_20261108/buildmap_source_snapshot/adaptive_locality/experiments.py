"""Comparable exact-scope shadow metrics and fail-closed promotion decisions."""
from dataclasses import dataclass
from .core import LocalityError

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
            "safe_to_promote":False,
            "reason":"manual scientific approval and complete provenance required"}
